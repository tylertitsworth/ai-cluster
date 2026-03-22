"""Provider and agent config resolution from workflow YAML.

All LLM providers in this engine use the OpenAI-compatible protocol.

Typical workflow YAML shape::

    providers:
      openai:
        base_url: ${OPENAI_BASE_URL}
        api_key:  ${OPENAI_API_KEY}
        model:    gpt-4o
      local:
        base_url: http://ollama:11434/v1
        api_key:  none
        model:    llama3

    agents:
      investigator:
        provider: openai
        prompt:   investigator   # key in config["_prompts"]
        tools:    [web_search]
      writer:
        provider: local
        prompt:   writer
"""

import logging
import os
import re

logger = logging.getLogger(__name__)

_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _expand_env(value: str) -> str:
    """Replace ``${VAR}`` placeholders with values from os.environ.

    Unknown variables are left unexpanded and a warning is logged.
    """
    if not isinstance(value, str):
        return value

    def _replace(match: re.Match) -> str:
        var = match.group(1)
        resolved = os.environ.get(var)
        if resolved is None:
            logger.warning("Environment variable '%s' is not set", var)
            return match.group(0)
        return resolved

    return _ENV_VAR_RE.sub(_replace, value)


def _split_agent_overrides(overrides: dict, agent_name: str) -> dict:
    """Merge agent-specific and global overrides, with agent-specific winning.

    Keys of the form ``"agent_name:field"`` are agent-specific.  Plain keys
    (e.g. ``"model"``) are global.  Agent-specific keys take priority.
    """
    effective: dict = {}

    # First pass: collect global overrides (no colon prefix)
    for key, value in overrides.items():
        if ":" not in key:
            effective[key] = value

    # Second pass: agent-specific overrides shadow global ones
    for key, value in overrides.items():
        if ":" in key:
            prefix, field = key.split(":", 1)
            if prefix == agent_name:
                effective[field] = value

    return effective


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_provider(
    provider_name: str,
    workflow_config: dict,
    overrides: dict | None = None,
) -> dict:
    """Resolve a provider config from the workflow YAML and apply overrides.

    Args:
        provider_name: Key in ``workflow_config["providers"]``.
        workflow_config: The full loaded workflow dict (from WorkflowRegistry).
        overrides: Flat dict of field overrides.  Only the keys ``base_url``,
            ``api_key``, and ``model`` are honoured here; agent-specific
            prefixed keys (``"agent:field"``) are ignored.

    Returns:
        Dict with keys ``base_url``, ``api_key``, and ``model`` (all strings,
        env-var references expanded).

    Raises:
        ValueError: If the provider is not declared in the workflow config.
    """
    if overrides is None:
        overrides = {}

    providers = workflow_config.get("providers", {})
    if provider_name not in providers:
        available = list(providers.keys())
        raise ValueError(
            f"Provider '{provider_name}' not found in workflow config. "
            f"Available providers: {available}"
        )

    # Start from a copy so we never mutate the registry's cached config
    cfg: dict = dict(providers[provider_name])

    # Apply overrides for the three provider fields.
    # Callers pre-filter out agent-prefixed keys before passing overrides here,
    # so a plain key match is sufficient.
    for field in ("base_url", "api_key", "model"):
        if field in overrides:
            cfg[field] = overrides[field]

    return {
        "base_url": _expand_env(cfg.get("base_url", "")),
        "api_key": _expand_env(cfg.get("api_key", "")),
        "model": _expand_env(cfg.get("model", "")),
    }


def resolve_agent_config(
    agent_name: str,
    workflow_config: dict,
    overrides: dict | None = None,
) -> dict:
    """Resolve the full runtime config for a single agent.

    Override resolution order (highest → lowest priority):

    1. Agent-specific override  e.g. ``{"investigator:model": "gpt-5.4"}``
    2. Global override          e.g. ``{"model": "gpt-5.4"}``
    3. YAML default

    Args:
        agent_name: Key in ``workflow_config["agents"]``.
        workflow_config: The full loaded workflow dict (from WorkflowRegistry).
        overrides: Dict of overrides from CLI ``-A`` flags or request params.

    Returns:
        Dict with keys:

        - ``provider_config``  — output of :func:`resolve_provider`
        - ``system_prompt``    — prompt text string
        - ``tool_names``       — list of tool name strings

    Raises:
        ValueError: If the agent, provider, or prompt cannot be resolved.
    """
    if overrides is None:
        overrides = {}

    agents = workflow_config.get("agents", {})
    if agent_name not in agents:
        available = list(agents.keys())
        raise ValueError(
            f"Agent '{agent_name}' not found in workflow config. "
            f"Available agents: {available}"
        )

    agent_cfg = agents[agent_name]
    effective = _split_agent_overrides(overrides, agent_name)

    # Provider can itself be switched via override
    provider_name = effective.get("provider", agent_cfg.get("provider"))
    if not provider_name:
        raise ValueError(f"Agent '{agent_name}' has no provider configured")

    # Pass only non-prefixed effective overrides into resolve_provider so it
    # can apply model/base_url/api_key changes.
    provider_overrides = {k: v for k, v in effective.items() if ":" not in k}
    provider_config = resolve_provider(provider_name, workflow_config, provider_overrides)

    # Prompt
    prompt_key = agent_cfg.get("prompt", agent_name)
    prompts: dict[str, str] = workflow_config.get("_prompts", {})
    if prompt_key not in prompts:
        available_prompts = list(prompts.keys())
        raise ValueError(
            f"Prompt '{prompt_key}' not found for agent '{agent_name}'. "
            f"Available prompts: {available_prompts}"
        )
    system_prompt = prompts[prompt_key]

    tool_names: list[str] = agent_cfg.get("tools", [])

    logger.debug(
        "Resolved agent '%s': provider=%s model=%s tools=%s",
        agent_name,
        provider_name,
        provider_config["model"],
        tool_names,
    )

    return {
        "provider_config": provider_config,
        "system_prompt": system_prompt,
        "tool_names": tool_names,
    }
