"""Meta-operator application — wraps workflow flows with review/race/ralph primitives.

Pure logic, no Ray or FastAPI dependency. Used by serve.py to process
CLI meta-operators before executing workflows.
"""

from copy import deepcopy


def apply_operators(config: dict, operators: list) -> dict:
    """Wrap a workflow config's flow in meta-operator primitives.

    Each operator in the list wraps the current flow. Operators are applied
    in order, so the last operator is the outermost wrapper.

    Args:
        config: Workflow config dict (from registry).
        operators: List of operator dicts from CLI, e.g.
            [{"type": "review", "max": 3, "judge_criteria": "accuracy"}]

    Returns:
        A new config dict with the flow wrapped. The original is not mutated.
    """
    if not operators:
        return config

    config = deepcopy(config)

    for op in operators:
        op_type = op.get("type")
        if op_type == "review":
            _apply_review(config, op)
        elif op_type == "race":
            _apply_race(config, op)
        elif op_type == "ralph":
            _apply_ralph(config, op)

    return config


def _apply_review(config: dict, op: dict):
    max_iter = op.get("max", 3)
    criteria = op.get("judge_criteria", "DONE if the output is satisfactory")

    config["flow"] = {
        "loop": {
            "max": max_iter,
            "steps": [
                config["flow"],
                {"step": "_reviewer"},
                {
                    "route": {
                        "DONE": "end",
                        "default": "continue",
                    }
                },
            ],
        }
    }

    if "_reviewer" not in config.get("agents", {}):
        first_provider = next(iter(config.get("providers", {})), "openai")
        config.setdefault("agents", {})["_reviewer"] = {
            "provider": first_provider,
            "prompt": "_reviewer",
        }
        config.setdefault("_prompts", {})["_reviewer"] = (
            f"You are a reviewer. Evaluate the previous output.\n"
            f"Criteria: {criteria}\n"
            f"If it meets criteria, respond with exactly 'DONE'.\n"
            f"If not, explain what needs improvement."
        )


def _apply_race(config: dict, op: dict):
    count = op.get("count", 3)
    criteria = op.get("judge_criteria", "best overall quality")

    config["flow"] = {
        "race": {
            "count": count,
            "work": config["flow"],
            "resolve": {
                "strategy": "pick",
                "judge": "_judge",
                "criteria": criteria,
            },
        }
    }

    if "_judge" not in config.get("agents", {}):
        first_provider = next(iter(config.get("providers", {})), "openai")
        config.setdefault("agents", {})["_judge"] = {
            "provider": first_provider,
            "prompt": "_judge",
        }
        config.setdefault("_prompts", {})["_judge"] = (
            f"You are a judge evaluating multiple responses.\n"
            f"Criteria: {criteria}\n"
            f"Select the best response and reproduce it in full."
        )


def _apply_ralph(config: dict, op: dict):
    max_tasks = op.get("max", 10)
    done_signal = op.get("judge_criteria", "DONE")

    config["flow"] = {
        "ralph": {
            "max": max_tasks,
            "work": config["flow"],
            "done": done_signal,
        }
    }
