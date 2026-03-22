import logging
import os
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

WORKFLOWS_DIR = Path(os.environ.get("WORKFLOWS_DIR", "/workflows"))
PROMPTS_DIR = Path(os.environ.get("PROMPTS_DIR", "/prompts"))

# Also check source tree for local development
_SOURCE_DIR = Path(__file__).resolve().parent.parent


class WorkflowRegistry:
    """Loads and manages workflow configs from YAML files.

    Hot-reloads when ConfigMap-mounted files change (via watch()).
    Each workflow config includes resolved prompt text.
    """

    def __init__(self):
        self.workflows: dict[str, dict] = {}
        self._load_all()

    def _load_all(self):
        """Load all workflow YAML files and their prompts."""
        loaded = {}

        # Load from ConfigMap mount first
        for yaml_file in WORKFLOWS_DIR.glob("*.yaml"):
            try:
                config = self._load_workflow(yaml_file)
                if config:
                    loaded[config["name"]] = config
            except Exception:
                logger.exception("Failed to load workflow from %s", yaml_file)

        # Fallback: load from source tree (for local dev)
        workflows_src = _SOURCE_DIR / "workflows"
        if workflows_src.is_dir():
            for yaml_file in workflows_src.glob("*.yaml"):
                try:
                    config = self._load_workflow(yaml_file)
                    if config and config["name"] not in loaded:
                        loaded[config["name"]] = config
                except Exception:
                    logger.exception("Failed to load workflow from %s", yaml_file)

        self.workflows = loaded
        logger.info("Loaded %d workflows: %s", len(loaded), list(loaded.keys()))

    def _load_workflow(self, path: Path) -> dict | None:
        """Load a single workflow YAML file. Returns None if invalid."""
        config = yaml.safe_load(path.read_text())
        errors = self._validate(config, path)
        if errors:
            for e in errors:
                logger.error("Validation error in %s: %s", path, e)
            return None
        config["_prompts"] = self._load_prompts(config["name"])
        config["_source"] = str(path)
        return config

    def _load_prompts(self, workflow_name: str) -> dict[str, str]:
        """Load prompt .txt files for a workflow."""
        prompts = {}

        # Check ConfigMap mount
        k8s_dir = PROMPTS_DIR / workflow_name
        if k8s_dir.is_dir():
            for f in k8s_dir.glob("*.txt"):
                prompts[f.stem] = f.read_text().strip()

        # Fallback to source tree
        for variant in (workflow_name, workflow_name.replace("-", "_")):
            src_dir = _SOURCE_DIR / "prompts" / variant
            if src_dir.is_dir():
                for f in src_dir.glob("*.txt"):
                    if f.stem not in prompts:
                        prompts[f.stem] = f.read_text().strip()

        return prompts

    def _validate(self, config: dict, path: Path) -> list[str]:
        """Validate a workflow config. Returns list of error messages."""
        errors = []
        if not isinstance(config, dict):
            return [f"Expected dict, got {type(config).__name__}"]

        # Required fields
        if "name" not in config:
            errors.append("Missing required field: name")
        if "agents" not in config:
            errors.append("Missing required field: agents")
        if "flow" not in config:
            errors.append("Missing required field: flow")

        if errors:
            return errors  # can't validate further without these

        # Validate agent references in flow
        agent_names = set(config.get("agents", {}).keys())
        tool_names = set(config.get("tools", {}).keys())

        # Check that agents reference valid tools
        for agent_name, agent_config in config.get("agents", {}).items():
            for tool_ref in agent_config.get("tools", []):
                if tool_ref not in tool_names:
                    errors.append(f"Agent '{agent_name}' references unknown tool '{tool_ref}'")
            if "provider" not in agent_config:
                errors.append(f"Agent '{agent_name}' missing required field: provider")
            if "prompt" not in agent_config:
                errors.append(f"Agent '{agent_name}' missing required field: prompt")

        # Validate isolation
        isolation = config.get("isolation")
        if isolation is not None and isolation not in ("per-invocation", "per-branch"):
            errors.append(f"Invalid isolation mode: '{isolation}'. Must be 'per-invocation' or 'per-branch'.")

        # Validate params
        for param_name, param_config in config.get("params", {}).items():
            if "type" not in param_config:
                errors.append(f"Param '{param_name}' missing required field: type")
            if param_config.get("type") not in ("string", "integer", "float", "boolean"):
                errors.append(f"Param '{param_name}' has invalid type: {param_config.get('type')}")

        return errors

    async def watch(self):
        """Background task: reload workflows when ConfigMap volumes update."""
        try:
            from watchfiles import awatch
        except ImportError:
            logger.warning("watchfiles not installed, hot-reload disabled")
            return

        watch_paths = [p for p in [WORKFLOWS_DIR, PROMPTS_DIR] if p.is_dir()]
        if not watch_paths:
            logger.warning("No watch paths found, hot-reload disabled")
            return

        logger.info("Watching for workflow changes: %s", watch_paths)
        async for changes in awatch(*watch_paths):
            logger.info("Detected config changes: %s", changes)
            self._load_all()

    def get(self, name: str) -> dict | None:
        """Get a workflow config by name."""
        return self.workflows.get(name)

    def list_workflows(self) -> dict:
        """Return metadata for all workflows (for /workflows endpoint)."""
        result = {}
        for name, config in self.workflows.items():
            result[name] = {
                "description": config.get("description", ""),
                "tier": config.get("tier", "default"),
                "params": config.get("params", {}),
                "agents": list(config.get("agents", {}).keys()),
            }
        return result

    def validate_params(self, workflow_name: str, params: dict) -> tuple[dict, list[str]]:
        """Validate and apply defaults for workflow params.

        Returns (resolved_params, errors).
        """
        config = self.workflows.get(workflow_name)
        if not config:
            return params, [f"Unknown workflow: {workflow_name}"]

        declared = config.get("params", {})
        resolved = {}
        errors = []

        # Apply defaults and validate
        for param_name, param_def in declared.items():
            if param_name in params:
                value = params[param_name]
                # Type coercion
                param_type = param_def.get("type", "string")
                try:
                    if param_type == "integer":
                        value = int(value)
                        if "min" in param_def and value < param_def["min"]:
                            errors.append(f"Param '{param_name}' below minimum {param_def['min']}")
                        if "max" in param_def and value > param_def["max"]:
                            errors.append(f"Param '{param_name}' above maximum {param_def['max']}")
                    elif param_type == "float":
                        value = float(value)
                    elif param_type == "boolean":
                        value = str(value).lower() in ("true", "1", "yes")
                    if "choices" in param_def and value not in param_def["choices"]:
                        errors.append(f"Param '{param_name}' must be one of {param_def['choices']}")
                except (ValueError, TypeError) as e:
                    errors.append(f"Param '{param_name}' invalid: {e}")
                    continue
                resolved[param_name] = value
            elif "default" in param_def:
                resolved[param_name] = param_def["default"]
            elif param_def.get("required", False):
                errors.append(f"Missing required param: {param_name}")

        # Pass through any extra params (like provider, model overrides)
        for k, v in params.items():
            if k not in resolved:
                resolved[k] = v

        return resolved, errors
