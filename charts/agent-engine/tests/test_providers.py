"""Tests for provider resolution and agent config override priority."""

import os

import pytest


class TestProviderResolution:
    def test_resolves_basic_provider(self, sample_workflow_config):
        from engine.providers import resolve_provider

        result = resolve_provider("openai", sample_workflow_config)
        assert result["base_url"] == "http://localhost:8000/v1"
        assert result["api_key"] == "test-key"
        assert result["model"] == "test-model"

    def test_raises_on_unknown_provider(self, sample_workflow_config):
        from engine.providers import resolve_provider

        with pytest.raises(ValueError, match="not found"):
            resolve_provider("nonexistent", sample_workflow_config)

    def test_applies_model_override(self, sample_workflow_config):
        from engine.providers import resolve_provider

        result = resolve_provider("openai", sample_workflow_config, {"model": "gpt-5"})
        assert result["model"] == "gpt-5"

    def test_expands_env_vars(self, sample_workflow_config):
        os.environ["TEST_BASE_URL"] = "http://from-env:9999/v1"
        sample_workflow_config["providers"]["openai"]["base_url"] = "${TEST_BASE_URL}"

        from engine.providers import resolve_provider

        result = resolve_provider("openai", sample_workflow_config)
        assert result["base_url"] == "http://from-env:9999/v1"
        del os.environ["TEST_BASE_URL"]


class TestAgentConfigResolution:
    def test_resolves_agent_with_prompt(self, sample_workflow_config):
        from engine.providers import resolve_agent_config

        result = resolve_agent_config("writer", sample_workflow_config)
        assert result["system_prompt"] == "You are a writer."
        assert result["provider_config"]["model"] == "test-model"
        assert result["tool_names"] == []

    def test_global_override_applies_to_all(self, sample_workflow_config):
        from engine.providers import resolve_agent_config

        result = resolve_agent_config(
            "writer", sample_workflow_config, {"model": "override-model"}
        )
        assert result["provider_config"]["model"] == "override-model"

    def test_agent_specific_override_wins(self, sample_workflow_config):
        from engine.providers import resolve_agent_config

        result = resolve_agent_config(
            "writer",
            sample_workflow_config,
            {"model": "global-model", "writer:model": "specific-model"},
        )
        assert result["provider_config"]["model"] == "specific-model"

    def test_agent_specific_doesnt_affect_other_agents(self, sample_workflow_config):
        from engine.providers import resolve_agent_config

        result = resolve_agent_config(
            "reviewer",
            sample_workflow_config,
            {"writer:model": "writer-only-model"},
        )
        assert result["provider_config"]["model"] == "test-model"

    def test_raises_on_unknown_agent(self, sample_workflow_config):
        from engine.providers import resolve_agent_config

        with pytest.raises(ValueError, match="not found"):
            resolve_agent_config("nonexistent", sample_workflow_config)

    def test_raises_on_missing_prompt(self, sample_workflow_config):
        sample_workflow_config["agents"]["noprompt"] = {
            "provider": "openai",
            "prompt": "missing_prompt",
        }
        from engine.providers import resolve_agent_config

        with pytest.raises(ValueError, match="not found"):
            resolve_agent_config("noprompt", sample_workflow_config)
