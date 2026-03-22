"""Shared fixtures for agent-engine tests.

Tests run without Ray, without MCP servers, and without LLM providers.
All external dependencies are mocked via fixtures.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

ENGINE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE_ROOT))

os.environ.setdefault("WORKFLOWS_DIR", str(ENGINE_ROOT / "workflows"))
os.environ.setdefault("PROMPTS_DIR", str(ENGINE_ROOT / "prompts"))


@pytest.fixture
def sample_workflow_config():
    """A minimal valid workflow config dict (as loaded by the registry)."""
    return {
        "name": "test-workflow",
        "description": "A test workflow",
        "tier": "default",
        "providers": {
            "openai": {
                "base_url": "http://localhost:8000/v1",
                "api_key": "test-key",
                "model": "test-model",
            },
        },
        "tools": {},
        "agents": {
            "writer": {
                "provider": "openai",
                "prompt": "writer",
                "tools": [],
            },
            "reviewer": {
                "provider": "openai",
                "prompt": "reviewer",
                "tools": [],
            },
        },
        "params": {
            "count": {
                "type": "integer",
                "default": 3,
                "min": 1,
                "max": 10,
            },
        },
        "flow": [{"step": "writer"}],
        "_prompts": {
            "writer": "You are a writer.",
            "reviewer": "You are a reviewer.",
        },
        "_source": "test",
    }


@pytest.fixture
def sample_workflow_with_tools():
    """A workflow config with MCP tool groups."""
    return {
        "name": "tool-workflow",
        "description": "Workflow with tools",
        "tier": "default",
        "providers": {
            "openai": {
                "base_url": "http://localhost:8000/v1",
                "api_key": "test-key",
                "model": "test-model",
            },
        },
        "tools": {
            "search": {"type": "mcp", "url": "http://search:8080"},
            "k8s": {"type": "mcp", "url": "http://k8s:8080"},
        },
        "agents": {
            "researcher": {
                "provider": "openai",
                "prompt": "researcher",
                "tools": ["search"],
            },
            "admin": {
                "provider": "openai",
                "prompt": "admin",
                "tools": ["search", "k8s"],
            },
            "writer": {
                "provider": "openai",
                "prompt": "writer",
                "tools": [],
            },
        },
        "params": {},
        "flow": [{"step": "researcher"}],
        "_prompts": {
            "researcher": "You research things.",
            "admin": "You admin things.",
            "writer": "You write things.",
        },
        "_source": "test",
    }


@pytest.fixture
def tmp_db(tmp_path):
    """Path to a temporary SQLite database file."""
    return str(tmp_path / "test_checkpoints.db")


@pytest.fixture
def tmp_workflows_dir(tmp_path):
    """A temporary directory with sample workflow YAML files."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir()

    (wf_dir / "example.yaml").write_text(
        """
name: example
description: Test example
tier: default
providers:
  openai:
    base_url: http://localhost:8000/v1
    api_key: test
    model: test
agents:
  summarizer:
    provider: openai
    prompt: summarizer
flow:
  - step: summarizer
"""
    )

    prompts_dir = tmp_path / "prompts" / "example"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "summarizer.txt").write_text("You summarize things.")

    return tmp_path
