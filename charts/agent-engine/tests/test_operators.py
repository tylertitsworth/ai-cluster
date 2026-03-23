"""Tests for engine.operators.apply_operators — meta-operator flow wrapping."""

from copy import deepcopy

from engine.operators import apply_operators

BASE_CONFIG = {
    "name": "test",
    "providers": {"openai": {"base_url": "http://x", "api_key": "k", "model": "m"}},
    "agents": {"worker": {"provider": "openai", "prompt": "worker"}},
    "_prompts": {"worker": "You work."},
    "flow": [{"step": "worker"}],
}


def test_apply_no_operators():
    cfg = deepcopy(BASE_CONFIG)
    result = apply_operators(cfg, [])
    assert result is cfg


def test_apply_review():
    out = apply_operators(
        deepcopy(BASE_CONFIG),
        [{"type": "review", "max": 3, "judge_criteria": "accuracy"}],
    )
    flow = out["flow"]
    assert "loop" in flow
    assert flow["loop"]["max"] == 3
    steps = flow["loop"]["steps"]
    assert steps[0] == [{"step": "worker"}]
    assert steps[1] == {"step": "_reviewer"}
    assert steps[2] == {
        "route": {
            "DONE": "end",
            "default": "continue",
        }
    }


def test_apply_review_injects_reviewer_agent():
    out = apply_operators(
        deepcopy(BASE_CONFIG),
        [{"type": "review", "max": 3, "judge_criteria": "accuracy"}],
    )
    assert "_reviewer" in out["agents"]
    assert "DONE" in out["_prompts"]["_reviewer"]


def test_apply_race():
    out = apply_operators(
        deepcopy(BASE_CONFIG),
        [{"type": "race", "count": 3, "judge_criteria": "best quality"}],
    )
    flow = out["flow"]
    assert "race" in flow
    race = flow["race"]
    assert race["count"] == 3
    assert race["work"] == [{"step": "worker"}]
    assert race["resolve"] == {
        "strategy": "pick",
        "judge": "_judge",
        "criteria": "best quality",
    }


def test_apply_race_injects_judge_agent():
    out = apply_operators(
        deepcopy(BASE_CONFIG),
        [{"type": "race", "count": 3, "judge_criteria": "best quality"}],
    )
    assert "_judge" in out["agents"]
    assert "_judge" in out["_prompts"]


def test_apply_ralph():
    out = apply_operators(
        deepcopy(BASE_CONFIG),
        [{"type": "ralph", "max": 5, "judge_criteria": "DONE"}],
    )
    flow = out["flow"]
    assert "ralph" in flow
    ralph = flow["ralph"]
    assert ralph["max"] == 5
    assert ralph["work"] == [{"step": "worker"}]
    assert ralph["done"] == "DONE"


def test_apply_combined_review_race():
    out = apply_operators(
        deepcopy(BASE_CONFIG),
        [
            {"type": "review", "max": 3, "judge_criteria": "accuracy"},
            {"type": "race", "count": 3, "judge_criteria": "best quality"},
        ],
    )
    assert "race" in out["flow"]
    race_work = out["flow"]["race"]["work"]
    assert "loop" in race_work
    steps = race_work["loop"]["steps"]
    assert steps[0] == [{"step": "worker"}]
    assert steps[1] == {"step": "_reviewer"}
    assert steps[2]["route"]["DONE"] == "end"


def test_apply_preserves_existing_agents():
    cfg = deepcopy(BASE_CONFIG)
    cfg["agents"]["_reviewer"] = {
        "provider": "openai",
        "prompt": "_reviewer",
        "id": "preserved",
    }
    cfg["_prompts"]["_reviewer"] = "PRESERVED_REVIEWER_PROMPT"
    out = apply_operators(
        cfg,
        [{"type": "review", "max": 3, "judge_criteria": "accuracy"}],
    )
    assert out["agents"]["_reviewer"]["id"] == "preserved"
    assert out["_prompts"]["_reviewer"] == "PRESERVED_REVIEWER_PROMPT"
