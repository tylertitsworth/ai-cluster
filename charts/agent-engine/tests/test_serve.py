"""Tests for serve.py meta-operator application."""

import pytest


class TestApplyOperators:
    def _apply(self, config, operators):
        from engine.operators import apply_operators

        return apply_operators(config, operators)

    def test_no_operators_returns_same_config(self, sample_workflow_config):
        result = self._apply(sample_workflow_config, [])
        assert result["flow"] == sample_workflow_config["flow"]

    def test_review_wraps_flow_in_loop(self, sample_workflow_config):
        result = self._apply(
            sample_workflow_config,
            [{"type": "review", "max": 3}],
        )
        flow = result["flow"]
        assert "loop" in flow
        assert flow["loop"]["max"] == 3
        assert "_reviewer" in result["agents"]
        assert "_reviewer" in result["_prompts"]

    def test_review_route_always_matches_on_DONE(self, sample_workflow_config):
        """The route pattern must be 'DONE' regardless of judge_criteria."""
        result = self._apply(
            sample_workflow_config,
            [{"type": "review", "max": 3, "judge_criteria": "accuracy and clarity"}],
        )
        loop_steps = result["flow"]["loop"]["steps"]
        route_step = next(s for s in loop_steps if "route" in s)
        assert "DONE" in route_step["route"]

    def test_race_wraps_flow_in_race_primitive(self, sample_workflow_config):
        result = self._apply(
            sample_workflow_config,
            [{"type": "race", "count": 3, "judge_criteria": "best quality"}],
        )
        flow = result["flow"]
        assert "race" in flow
        assert flow["race"]["count"] == 3
        assert "_judge" in result["agents"]

    def test_ralph_wraps_flow_in_ralph_primitive(self, sample_workflow_config):
        result = self._apply(
            sample_workflow_config,
            [{"type": "ralph", "max": 5, "judge_criteria": "ALL_DONE"}],
        )
        flow = result["flow"]
        assert "ralph" in flow
        assert flow["ralph"]["max"] == 5

    def test_operators_dont_mutate_original(self, sample_workflow_config):
        original_flow = sample_workflow_config["flow"]
        self._apply(
            sample_workflow_config,
            [{"type": "review", "max": 3}],
        )
        assert sample_workflow_config["flow"] == original_flow
