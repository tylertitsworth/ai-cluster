"""Shared fixtures for agent-engine integration tests.

Mocks Ray actors, MCP tools, and placement groups so tests run locally
without any infrastructure dependencies.
"""

import asyncio
import json
import os
import sys
import tempfile
import types
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

AGENT_ENGINE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_ENGINE_ROOT))

# ---------------------------------------------------------------------------
# Install stub modules for ray, openai, mcp BEFORE any engine code imports.
# These are replaced by proper mocks in fixtures, but the stubs prevent
# ImportError at module load time.
# ---------------------------------------------------------------------------

if "ray" not in sys.modules:
    _ray = types.ModuleType("ray")
    _ray.remote = lambda *a, **kw: (lambda cls: cls) if not a else a[0]
    _ray.kill = lambda *a, **kw: None
    _ray.get = lambda ref, **kw: ref
    _ray.ObjectRef = object
    _ray_util = types.ModuleType("ray.util")
    _ray_util.placement_group = lambda **kw: MagicMock()
    _ray_util.remove_placement_group = lambda pg: None
    _ray.util = _ray_util
    sys.modules["ray"] = _ray
    sys.modules["ray.util"] = _ray_util
    _ray_serve = types.ModuleType("ray.serve")
    _ray_serve.deployment = lambda *a, **kw: (lambda cls: cls)
    _ray_serve.ingress = lambda app: (lambda cls: cls)
    sys.modules["ray.serve"] = _ray_serve

if "openai" not in sys.modules:
    _openai = types.ModuleType("openai")
    _openai.AsyncOpenAI = MagicMock
    _openai.NOT_GIVEN = object()
    _openai.RateLimitError = type("RateLimitError", (Exception,), {})
    _openai.APITimeoutError = type("APITimeoutError", (Exception,), {})
    _openai.APIConnectionError = type("APIConnectionError", (Exception,), {})
    sys.modules["openai"] = _openai

if "mcp" not in sys.modules:
    _mcp = types.ModuleType("mcp")
    _mcp.ClientSession = MagicMock
    sys.modules["mcp"] = _mcp
    _mcp_client = types.ModuleType("mcp.client")
    sys.modules["mcp.client"] = _mcp_client
    _mcp_http = types.ModuleType("mcp.client.streamable_http")
    _mcp_http.streamablehttp_client = MagicMock
    sys.modules["mcp.client.streamable_http"] = _mcp_http

if "watchfiles" not in sys.modules:
    _wf = types.ModuleType("watchfiles")
    _wf.awatch = MagicMock
    sys.modules["watchfiles"] = _wf

import pytest


# ---------------------------------------------------------------------------
# Mock Agent — simulates LLM responses based on system prompt keywords
# ---------------------------------------------------------------------------

def _tool_call_response(name: str, arguments: str, call_id: str = "call_1"):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        ],
    }


class _RemoteCall:
    """Wraps an async method to support Ray's actor.method.remote() pattern.

    In real Ray, actor.method.remote() returns an ObjectRef (awaitable).
    This mock returns the coroutine directly so `await actor.execute.remote(msgs)` works.
    """

    def __init__(self, coro_func, instance):
        self._func = coro_func
        self._instance = instance

    def remote(self, *args, **kwargs):
        return self._func(self._instance, *args, **kwargs)


async def _to_awaitable(value):
    """Wrap a value in a coroutine so it can be awaited (mimics Ray ObjectRef)."""
    return value


class _RemoteStreamCall:
    """Wraps an async generator to support Ray's actor.method.remote() pattern.

    Ray streaming actors yield ObjectRefs that must be awaited.
    This wrapper yields coroutines wrapping each value so `await chunk_ref` works.
    """

    def __init__(self, gen_func, instance):
        self._func = gen_func
        self._instance = instance

    def remote(self, *args, **kwargs):
        async def _wrap():
            async for item in self._func(self._instance, *args, **kwargs):
                yield _to_awaitable(item)
        return _wrap()


class MockAgent:
    """Fake Agent actor that returns canned responses based on prompt keywords.

    Supports the Ray actor calling pattern: actor.execute.remote(messages)
    """

    def __init__(self, provider_config, system_prompt, tool_schemas=None):
        self.provider_config = provider_config
        self.system_prompt = system_prompt or ""
        self.tool_schemas = tool_schemas
        self.call_count = 0
        self.messages_log: list[list[dict]] = []
        self.execute = _RemoteCall(MockAgent._execute_impl, self)
        self.stream_execute = _RemoteStreamCall(MockAgent._stream_execute_impl, self)

    async def _execute_impl(self, messages):
        self.call_count += 1
        self.messages_log.append(list(messages))
        return self._respond(messages)

    async def _stream_execute_impl(self, messages):
        self.call_count += 1
        self.messages_log.append(list(messages))
        response = self._respond(messages)
        if response.get("content"):
            yield {"type": "delta", "content": response["content"]}
        yield {"type": "message", **response}

    def _respond(self, messages):
        prompt_lower = self.system_prompt.lower()
        last_content = messages[-1].get("content", "") if messages else ""

        if "investigator" in prompt_lower:
            if self.call_count <= 1 and self.tool_schemas:
                return _tool_call_response("get_pods", '{"namespace": "default"}')
            if "STATUS: FIXED" in (last_content or ""):
                return {"role": "assistant", "content": "Verified. STATUS: FIXED", "tool_calls": None}
            return {"role": "assistant", "content": "Found issue. STATUS: NEEDS_FIX", "tool_calls": None}

        if "fixer" in prompt_lower:
            return {"role": "assistant", "content": "Proposed fix: scale replicas to 2", "tool_calls": None}

        if "guardrails" in prompt_lower:
            if hasattr(self, "_force_unsafe") and self._force_unsafe > 0:
                self._force_unsafe -= 1
                return {"role": "assistant", "content": "VERDICT: UNSAFE — risky operation", "tool_calls": None}
            return {"role": "assistant", "content": "VERDICT: SAFE — non-destructive change", "tool_calls": None}

        if "executor" in prompt_lower:
            if self.call_count <= 1 and self.tool_schemas:
                return _tool_call_response("apply_patch", '{"resource": "deployment/web"}')
            return {"role": "assistant", "content": "Fix applied successfully. STATUS: FIXED", "tool_calls": None}

        if "summarizer" in prompt_lower:
            return {"role": "assistant", "content": "Summary: user wants to check pod status", "tool_calls": None}

        if "orchestrator" in prompt_lower:
            n = 3
            for msg in messages:
                c = msg.get("content", "")
                if "num_sections" in c:
                    try:
                        n = int(c.split("num_sections")[1].strip().split()[0].strip("=:"))
                    except (ValueError, IndexError):
                        pass
            sections = [{"title": f"Section {i+1}", "brief": f"Cover topic {i+1}"} for i in range(n)]
            return {"role": "assistant", "content": json.dumps(sections), "tool_calls": None}

        if "writer" in prompt_lower:
            if self.call_count <= 1 and self.tool_schemas:
                return _tool_call_response("tavily_search", '{"query": "test topic"}')
            return {"role": "assistant", "content": "Researched section content with citations.", "tool_calls": None}

        if "editor" in prompt_lower:
            return {"role": "assistant", "content": "# Final Report\n\nEdited and assembled.", "tool_calls": None}

        if "reviewer" in prompt_lower or "_reviewer" in prompt_lower:
            return {"role": "assistant", "content": "DONE", "tool_calls": None}

        if "judge" in prompt_lower or "_judge" in prompt_lower:
            return {"role": "assistant", "content": "Branch 1 is best.\n\nReproduced content.", "tool_calls": None}

        return {"role": "assistant", "content": f"Response from agent (call #{self.call_count})", "tool_calls": None}

    @classmethod
    def options(cls, **kwargs):
        return cls

    @classmethod
    def remote(cls, provider_config, system_prompt, tool_schemas=None):
        return cls(provider_config, system_prompt, tool_schemas)


# ---------------------------------------------------------------------------
# Mock ToolManager — returns predefined schemas and tool results
# ---------------------------------------------------------------------------

class MockToolManager:
    """Fake ToolManager that returns canned tool results."""

    def __init__(self, tools_config=None):
        self._config = tools_config or {}
        self._schemas = [
            {
                "type": "function",
                "function": {
                    "name": "get_pods",
                    "description": "List Kubernetes pods",
                    "parameters": {"type": "object", "properties": {"namespace": {"type": "string"}}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "apply_patch",
                    "description": "Apply a patch to a K8s resource",
                    "parameters": {"type": "object", "properties": {"resource": {"type": "string"}}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tavily_search",
                    "description": "Web search",
                    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
                },
            },
        ]
        self._group_map = {
            "k8s-reader": {"get_pods"},
            "k8s-writer": {"apply_patch", "get_pods"},
            "tavily": {"tavily_search"},
            "context7": set(),
        }
        self.calls: list[dict] = []

    async def connect_all(self):
        pass

    def get_schemas(self):
        return list(self._schemas)

    def get_function_names_for_groups(self, group_names):
        result = set()
        for g in group_names:
            result.update(self._group_map.get(g, set()))
        return result

    async def execute(self, tool_calls):
        results = []
        for tc in tool_calls:
            fn_name = tc.get("function", {}).get("name", "unknown")
            self.calls.append(tc)
            results.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "content": f"Tool '{fn_name}' result: success",
            })
        return results

    async def close(self):
        pass


# ---------------------------------------------------------------------------
# Mock Ray — no-op placement groups, kill, etc.
# ---------------------------------------------------------------------------

class MockPlacementGroup:
    def ready(self):
        return True


class MockRay:
    """Minimal mock of the ray module for executor tests."""

    class util:
        @staticmethod
        def placement_group(**kwargs):
            return MockPlacementGroup()

        @staticmethod
        def remove_placement_group(pg):
            pass

    @staticmethod
    def get(ref, timeout=None):
        return ref

    @staticmethod
    def kill(actor):
        pass

    ObjectRef = object


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path):
    """Temporary SQLite database path for checkpoint tests."""
    return str(tmp_path / "test_checkpoints.db")


@pytest.fixture
def sample_workflow_config():
    """Minimal workflow config for unit tests."""
    return {
        "name": "test-workflow",
        "description": "Test workflow",
        "tier": "default",
        "isolation": "per-invocation",
        "providers": {
            "test": {
                "base_url": "http://localhost:8000/v1",
                "api_key": "test-key",
                "model": "test-model",
            }
        },
        "tools": {},
        "agents": {
            "agent_a": {"provider": "test", "prompt": "agent_a"},
            "agent_b": {"provider": "test", "prompt": "agent_b"},
        },
        "params": {},
        "_prompts": {
            "agent_a": "You are agent A.",
            "agent_b": "You are agent B.",
        },
        "flow": [
            {"step": "agent_a"},
            {"step": "agent_b"},
        ],
    }


@pytest.fixture
def service_debugger_config():
    """Config mimicking the service-debugger workflow for executor tests."""
    return {
        "name": "service-debugger",
        "tier": "k8s-access",
        "isolation": "per-invocation",
        "providers": {
            "openai": {"base_url": "http://fake:8000/v1", "api_key": "k", "model": "gpt-test"},
        },
        "tools": {
            "k8s-reader": {"type": "mcp", "url": "http://fake:8080"},
            "k8s-writer": {"type": "mcp", "url": "http://fake:8081"},
        },
        "agents": {
            "investigator": {"provider": "openai", "prompt": "investigator", "tools": ["k8s-reader"]},
            "fixer": {"provider": "openai", "prompt": "fixer"},
            "guardrails": {"provider": "openai", "prompt": "guardrails"},
            "executor": {"provider": "openai", "prompt": "executor", "tools": ["k8s-writer"]},
        },
        "params": {},
        "_prompts": {
            "investigator": "You are an investigator agent.",
            "fixer": "You are a fixer agent.",
            "guardrails": "You are a guardrails agent.",
            "executor": "You are an executor agent.",
        },
        "flow": [
            {"loop": {
                "max": 5,
                "steps": [
                    {"step": "investigator", "tool_loop": 10},
                    {"route": {"STATUS: FIXED": "end", "STATUS: UNFIXABLE": "end", "default": "continue"}},
                    {"step": "fixer"},
                    {"review": {"reviewer": "guardrails", "reject": "VERDICT: UNSAFE", "max_retries": 2}},
                    {"step": "executor", "tool_loop": 10},
                ],
            }}
        ],
    }


@pytest.fixture
def report_writer_config():
    """Config mimicking the report-writer workflow for executor tests."""
    return {
        "name": "report-writer",
        "tier": "web-research",
        "isolation": "per-invocation",
        "providers": {
            "openai": {"base_url": "http://fake:8000/v1", "api_key": "k", "model": "gpt-test"},
        },
        "tools": {
            "tavily": {"type": "mcp", "url": "http://fake:8082"},
            "context7": {"type": "mcp", "url": "http://fake:8083"},
        },
        "agents": {
            "orchestrator": {"provider": "openai", "prompt": "orchestrator"},
            "writer": {"provider": "openai", "prompt": "writer", "tools": ["tavily", "context7"]},
            "editor": {"provider": "openai", "prompt": "editor"},
        },
        "params": {
            "num_sections": {"type": "integer", "default": 3, "min": 1, "max": 20},
        },
        "_prompts": {
            "orchestrator": "You are an orchestrator agent.",
            "writer": "You are a writer agent.",
            "editor": "You are an editor agent.",
        },
        "flow": [
            {"step": "orchestrator"},
            {"parallel": {"agent": "writer", "count": "{num_sections}", "tool_loop": 5, "resolve": "concatenate"}},
            {"step": "editor"},
        ],
    }


@pytest.fixture
def mock_ray():
    """Patch ray module in executor with MockRay."""
    mock = MockRay()
    with patch("engine.executor.ray", mock):
        yield mock


@pytest.fixture
def mock_agent_class():
    """Patch Agent class in executor with MockAgent."""
    with patch("engine.executor.Agent", MockAgent):
        yield MockAgent


@pytest.fixture
def mock_tool_manager():
    """Patch ToolManager in executor with MockToolManager."""
    with patch("engine.executor.ToolManager", MockToolManager):
        yield MockToolManager
