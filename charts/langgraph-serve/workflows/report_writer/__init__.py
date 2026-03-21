"""Report Writer Swarm — parallel research and writing with fan-out/fan-in.

Orchestrator decomposes topic -> N Writers research in parallel -> Editor assembles final report.
"""

import logging
import time

import ray
from langchain_core.messages import HumanMessage
from utils import load_prompt, make_actor, run_workflow, stream_workflow
from workflows.report_writer.graph import build_graph
from workflows.report_writer.mcp import load_all_tools

CLI_META = {
    "nodes": {
        "orchestrator": "bright_blue",
        "writers": "bright_magenta",
        "editor": "bright_green",
    },
    "hidden_nodes": [],
    "prefix_styles": {"writer:": "writers"},
}

OrchestratorActor = make_actor("OrchestratorActor")
EditorActor = make_actor("EditorActor")

_DEFAULT_ORCHESTRATOR = "You are a Report Orchestrator. Output a JSON array of section assignments."
_DEFAULT_WRITER = "You are a Research Writer. Write the assigned section using your tools."
_DEFAULT_EDITOR = "You are a Report Editor. Assemble sections into a polished report."

ORCHESTRATOR_PROMPT = load_prompt("report-writer", "orchestrator", _DEFAULT_ORCHESTRATOR)
WRITER_PROMPT = load_prompt("report-writer", "writer", _DEFAULT_WRITER)
EDITOR_PROMPT = load_prompt("report-writer", "editor", _DEFAULT_EDITOR)

logger = logging.getLogger(__name__)

_cached_tools = None
_cache_ts = 0.0
_CACHE_TTL = 300


async def _get_tools():
    global _cached_tools, _cache_ts
    now = time.monotonic()
    if _cached_tools is None or now - _cache_ts > _CACHE_TTL:
        try:
            _cached_tools = await load_all_tools()
            _cache_ts = now
        except Exception:
            _cached_tools = None
            logger.exception("Failed to connect to research tool servers")
            raise
    return _cached_tools


def _build(provider, model, tools, num_writers=2, checkpointer=None, streaming=False):
    orchestrator_prompt = ORCHESTRATOR_PROMPT.replace("{num_sections}", str(num_writers))
    orchestrator = OrchestratorActor.remote(provider, model, orchestrator_prompt)
    editor_prompt = EDITOR_PROMPT
    editor = EditorActor.remote(provider, model, editor_prompt)

    compiled = build_graph(
        orchestrator, editor,
        provider, model, WRITER_PROMPT, tools,
        num_writers=num_writers,
        checkpointer=checkpointer,
        streaming=streaming,
    )
    return compiled, [orchestrator, editor]


async def run(provider: str, model: str, query: str, thread_id: str, checkpointer, writers: int = 2) -> str:
    tools = await _get_tools()
    return await run_workflow(
        lambda **kw: _build(provider, model, tools, num_writers=writers, **kw),
        query, thread_id, checkpointer,
    )


async def stream(provider: str, model: str, query: str, thread_id: str, checkpointer, writers: int = 2):
    tools = await _get_tools()
    async for event in stream_workflow(
        lambda **kw: _build(provider, model, tools, num_writers=writers, **kw),
        query, thread_id, checkpointer,
    ):
        yield event
