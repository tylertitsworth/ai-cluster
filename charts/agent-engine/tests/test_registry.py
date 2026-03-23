"""Tests for engine.registry.WorkflowRegistry."""

from pathlib import Path

import yaml

from engine.registry import WorkflowRegistry

_SOURCE_DIR = Path(__file__).resolve().parent.parent


def test_load_workflows_from_source_tree():
    registry = WorkflowRegistry()
    names = set(registry.workflows.keys())
    assert names == {"example", "service-debugger", "report-writer"}


def test_load_prompts():
    registry = WorkflowRegistry()
    wf = registry.get("report-writer")
    assert wf is not None
    prompts = wf.get("_prompts", {})
    assert set(prompts.keys()) >= {"orchestrator", "writer", "editor"}
    for key in ("orchestrator", "writer", "editor"):
        assert prompts[key].strip()


def test_validation_missing_name():
    registry = WorkflowRegistry()
    errors = registry._validate({}, Path("test.yaml"))
    assert "Missing required field: name" in errors


def test_validation_missing_agents():
    registry = WorkflowRegistry()
    errors = registry._validate({"name": "x", "flow": []}, Path("test.yaml"))
    assert "Missing required field: agents" in errors


def test_validation_missing_flow():
    registry = WorkflowRegistry()
    errors = registry._validate({"name": "x", "agents": {}}, Path("test.yaml"))
    assert "Missing required field: flow" in errors


def test_validation_unknown_tool_ref():
    registry = WorkflowRegistry()
    config = {
        "name": "bad-tools",
        "agents": {
            "agent1": {
                "provider": "openai",
                "prompt": "p1",
                "tools": ["nonexistent"],
            }
        },
        "flow": [],
        "tools": {},
    }
    errors = registry._validate(config, Path("bad.yaml"))
    assert any("unknown tool 'nonexistent'" in e for e in errors)


def test_validation_invalid_param_type():
    registry = WorkflowRegistry()
    config = {
        "name": "bad-params",
        "agents": {},
        "flow": [],
        "params": {"p": {"type": "invalid"}},
    }
    errors = registry._validate(config, Path("bad.yaml"))
    assert any("invalid type" in e and "invalid" in e for e in errors)


def test_validate_params_defaults():
    registry = WorkflowRegistry()
    resolved, errors = registry.validate_params("report-writer", {})
    assert errors == []
    assert resolved.get("num_sections") == 3


def test_validate_params_type_coercion():
    registry = WorkflowRegistry()
    resolved, errors = registry.validate_params("report-writer", {"num_sections": "5"})
    assert errors == []
    assert resolved.get("num_sections") == 5
    assert isinstance(resolved.get("num_sections"), int)


def test_validate_params_range_check():
    registry = WorkflowRegistry()
    registry.workflows["_range_test"] = {
        "name": "_range_test",
        "params": {"n": {"type": "integer", "min": 1, "max": 20}},
    }
    resolved, errors = registry.validate_params("_range_test", {"n": 25})
    assert any("above maximum" in e for e in errors)
    assert resolved.get("n") == 25


def test_validate_params_choices():
    registry = WorkflowRegistry()
    registry.workflows["_choices_test"] = {
        "name": "_choices_test",
        "params": {"pick": {"type": "string", "choices": ["a", "b"]}},
    }
    resolved, errors = registry.validate_params("_choices_test", {"pick": "c"})
    assert any("must be one of" in e for e in errors)


def test_list_workflows():
    registry = WorkflowRegistry()
    listing = registry.list_workflows()
    for name in ("example", "service-debugger", "report-writer"):
        assert name in listing
        meta = listing[name]
        assert "description" in meta
        assert "tier" in meta
        assert "params" in meta
        assert "agents" in meta
        assert isinstance(meta["agents"], list)


def test_validation_with_tmp_path_yaml(tmp_path):
    """Invalid YAML on disk: _validate via loaded dict mirrors file-driven errors."""
    bad_file = tmp_path / "broken.yaml"
    bad_file.write_text(yaml.dump({"flow": [], "agents": {}}))
    config = yaml.safe_load(bad_file.read_text())
    registry = WorkflowRegistry()
    errors = registry._validate(config, bad_file)
    assert "Missing required field: name" in errors
