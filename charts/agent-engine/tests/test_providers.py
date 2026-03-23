"""Tests for engine.providers.resolve_provider and resolve_agent_config."""

import pytest

from engine.providers import resolve_agent_config, resolve_provider

SAMPLE_CONFIG = {
    "providers": {
        "openai": {"base_url": "http://api.example.com/v1", "api_key": "sk-test", "model": "gpt-4"},
        "ollama": {"base_url": "http://ollama:11434/v1", "api_key": "none", "model": "llama3"},
    },
    "agents": {
        "investigator": {"provider": "openai", "prompt": "investigator", "tools": ["k8s-reader"]},
        "writer": {"provider": "ollama", "prompt": "writer"},
    },
    "_prompts": {
        "investigator": "You are an investigator.",
        "writer": "You are a writer.",
    },
}


def test_resolve_provider_basic():
    cfg = resolve_provider("openai", SAMPLE_CONFIG)
    assert cfg["base_url"] == "http://api.example.com/v1"
    assert cfg["api_key"] == "sk-test"
    assert cfg["model"] == "gpt-4"


def test_resolve_provider_env_expansion(monkeypatch):
    monkeypatch.setenv("TEST_URL", "https://expanded.example/v1")
    workflow = {
        "providers": {
            "custom": {
                "base_url": "${TEST_URL}",
                "api_key": "k",
                "model": "m",
            }
        }
    }
    cfg = resolve_provider("custom", workflow)
    assert cfg["base_url"] == "https://expanded.example/v1"


def test_resolve_provider_unknown():
    with pytest.raises(ValueError, match="Provider 'nonexistent' not found"):
        resolve_provider("nonexistent", SAMPLE_CONFIG)


def test_resolve_provider_with_overrides():
    cfg = resolve_provider("openai", SAMPLE_CONFIG, overrides={"model": "gpt-5"})
    assert cfg["model"] == "gpt-5"
    assert cfg["base_url"] == "http://api.example.com/v1"


def test_resolve_agent_config_basic():
    out = resolve_agent_config("investigator", SAMPLE_CONFIG)
    assert out["provider_config"]["model"] == "gpt-4"
    assert out["provider_config"]["base_url"] == "http://api.example.com/v1"
    assert out["system_prompt"] == "You are an investigator."
    assert out["tool_names"] == ["k8s-reader"]


def test_resolve_agent_config_global_override():
    out = resolve_agent_config(
        "investigator",
        SAMPLE_CONFIG,
        overrides={"model": "override-model"},
    )
    assert out["provider_config"]["model"] == "override-model"


def test_resolve_agent_config_agent_specific_override():
    out_inv = resolve_agent_config(
        "investigator",
        SAMPLE_CONFIG,
        overrides={"investigator:model": "special"},
    )
    out_writer = resolve_agent_config("writer", SAMPLE_CONFIG, overrides={"investigator:model": "special"})
    assert out_inv["provider_config"]["model"] == "special"
    assert out_writer["provider_config"]["model"] == "llama3"


def test_resolve_agent_config_priority():
    out = resolve_agent_config(
        "investigator",
        SAMPLE_CONFIG,
        overrides={"model": "global", "investigator:model": "specific"},
    )
    assert out["provider_config"]["model"] == "specific"


def test_resolve_agent_config_missing_prompt():
    bad = {
        **SAMPLE_CONFIG,
        "agents": {
            "broken": {"provider": "openai", "prompt": "nonexistent"},
        },
    }
    with pytest.raises(ValueError, match="Prompt 'nonexistent' not found"):
        resolve_agent_config("broken", bad)
