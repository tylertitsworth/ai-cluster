"""Service Debugger workflow — diagnose and fix broken K8s services.

Four-agent loop:
  Investigator (read-only) -> Fixer (proposes) -> Guardrails (validates) -> Executor (applies)
  Then back to Investigator to verify. Stops when Investigator reports FIXED or UNFIXABLE.
"""

import asyncio
import logging
import time

from utils import make_actor, run_workflow, stream_workflow
from workflows.service_debugger.graph import build_graph
from workflows.service_debugger.mcp import K8S_MCP_RO_URL, K8S_MCP_RW_URL, load_mcp_tools
from workflows.service_debugger.prompts import (
    EXECUTOR_PROMPT,
    FIXER_PROMPT,
    GUARDRAILS_PROMPT,
    INVESTIGATOR_PROMPT,
)

CLI_META = {
    "nodes": {
        "investigator": "blue",
        "fixer": "magenta",
        "guardrails": "yellow",
        "k8s_executor": "red",
    },
    "hidden_nodes": ["investigate_tools", "execute_tools", "guardrails_rejected"],
}

InvestigatorActor = make_actor("InvestigatorActor", has_tools=True)
FixerActor = make_actor("FixerActor")
GuardrailsActor = make_actor("GuardrailsActor")
K8sExecutorActor = make_actor("K8sExecutorActor", has_tools=True)

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5

_cache = {}
_CACHE_TTL = 300


async def _get_tools():
    """Load MCP tools with caching and TTL for stale connection recovery."""
    now = time.monotonic()
    if "ro" not in _cache or now - _cache.get("_ts", 0) > _CACHE_TTL:
        try:
            (ro_tools, ro_client), (rw_tools, rw_client) = await asyncio.gather(
                load_mcp_tools(K8S_MCP_RO_URL),
                load_mcp_tools(K8S_MCP_RW_URL),
            )
        except Exception:
            _cache.clear()
            logger.exception("Failed to connect to Kubernetes MCP servers")
            raise
        _cache.update(
            ro=ro_tools, rw=rw_tools,
            ro_client=ro_client, rw_client=rw_client,
            _ts=now,
        )
    return _cache["ro"], _cache["rw"]


def _build(provider, model, ro_tools, rw_tools, checkpointer=None, streaming=False):
    investigator = InvestigatorActor.remote(provider, model, INVESTIGATOR_PROMPT, ro_tools)
    fixer = FixerActor.remote(provider, model, FIXER_PROMPT)
    guardrails = GuardrailsActor.remote(provider, model, GUARDRAILS_PROMPT)
    executor = K8sExecutorActor.remote(provider, model, EXECUTOR_PROMPT, rw_tools)

    compiled = build_graph(
        investigator, fixer, guardrails, executor,
        ro_tools, rw_tools, checkpointer, streaming,
        max_iterations=MAX_ITERATIONS,
    )
    return compiled, [investigator, fixer, guardrails, executor]


async def run(provider: str, model: str, query: str, thread_id: str, checkpointer, **kwargs) -> str:
    ro_tools, rw_tools = await _get_tools()
    return await run_workflow(
        lambda **kw: _build(provider, model, ro_tools, rw_tools, **kw),
        query, thread_id, checkpointer,
        recursion_limit=MAX_ITERATIONS * 30,
    )


async def stream(provider: str, model: str, query: str, thread_id: str, checkpointer, **kwargs):
    ro_tools, rw_tools = await _get_tools()
    async for event in stream_workflow(
        lambda **kw: _build(provider, model, ro_tools, rw_tools, **kw),
        query, thread_id, checkpointer,
        recursion_limit=MAX_ITERATIONS * 30,
    ):
        yield event
