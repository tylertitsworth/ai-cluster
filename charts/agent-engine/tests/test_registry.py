"""Tests for WorkflowRegistry — loading, validation, and param handling."""

import os

import pytest


class TestWorkflowLoading:
    def test_loads_workflows_from_directory(self, tmp_workflows_dir):
        os.environ["WORKFLOWS_DIR"] = str(tmp_workflows_dir / "workflows")
        os.environ["PROMPTS_DIR"] = str(tmp_workflows_dir / "prompts")

        from engine.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        assert "example" in registry.workflows

    def test_loads_prompts_for_workflow(self, tmp_workflows_dir):
        os.environ["WORKFLOWS_DIR"] = str(tmp_workflows_dir / "workflows")
        os.environ["PROMPTS_DIR"] = str(tmp_workflows_dir / "prompts")

        from engine.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        config = registry.get("example")
        assert config is not None
        assert "summarizer" in config["_prompts"]
        assert "summarize" in config["_prompts"]["summarizer"].lower()

    def test_rejects_invalid_yaml(self, tmp_workflows_dir):
        bad_file = tmp_workflows_dir / "workflows" / "bad.yaml"
        bad_file.write_text("name: bad\n")  # missing agents and flow

        os.environ["WORKFLOWS_DIR"] = str(tmp_workflows_dir / "workflows")
        os.environ["PROMPTS_DIR"] = str(tmp_workflows_dir / "prompts")

        from engine.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        assert registry.get("bad") is None
        assert "example" in registry.workflows  # valid one still loaded

    def test_list_workflows_returns_metadata(self, tmp_workflows_dir):
        os.environ["WORKFLOWS_DIR"] = str(tmp_workflows_dir / "workflows")
        os.environ["PROMPTS_DIR"] = str(tmp_workflows_dir / "prompts")

        from engine.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        listing = registry.list_workflows()
        assert "example" in listing
        assert "description" in listing["example"]
        assert "tier" in listing["example"]
        assert "agents" in listing["example"]


class TestParamValidation:
    def test_applies_defaults(self, sample_workflow_config):
        from engine.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        registry.workflows["test-workflow"] = sample_workflow_config

        resolved, errors = registry.validate_params("test-workflow", {})
        assert errors == []
        assert resolved["count"] == 3

    def test_validates_integer_type(self, sample_workflow_config):
        from engine.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        registry.workflows["test-workflow"] = sample_workflow_config

        resolved, errors = registry.validate_params("test-workflow", {"count": "5"})
        assert errors == []
        assert resolved["count"] == 5
        assert isinstance(resolved["count"], int)

    def test_rejects_out_of_range(self, sample_workflow_config):
        from engine.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        registry.workflows["test-workflow"] = sample_workflow_config

        _, errors = registry.validate_params("test-workflow", {"count": 99})
        assert len(errors) > 0
        assert "maximum" in errors[0].lower() or "above" in errors[0].lower()

    def test_passes_through_extra_params(self, sample_workflow_config):
        from engine.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        registry.workflows["test-workflow"] = sample_workflow_config

        resolved, errors = registry.validate_params(
            "test-workflow", {"count": 5, "provider": "ollama"}
        )
        assert errors == []
        assert resolved["provider"] == "ollama"

    def test_rejects_invalid_choices(self):
        from engine.registry import WorkflowRegistry

        registry = WorkflowRegistry()
        registry.workflows["choice-test"] = {
            "name": "choice-test",
            "params": {
                "depth": {
                    "type": "string",
                    "default": "overview",
                    "choices": ["overview", "detailed"],
                }
            },
        }

        _, errors = registry.validate_params("choice-test", {"depth": "invalid"})
        assert len(errors) > 0
