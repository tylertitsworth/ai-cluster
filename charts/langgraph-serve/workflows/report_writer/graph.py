"""Graph builder for the report writer swarm.

START -> orchestrator -> writers (parallel fan-out) -> editor -> END

The writers node is a single graph node that internally spawns N Ray actors
in parallel, one per section assigned by the orchestrator.
"""

import asyncio
import json
import logging

import ray
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, MessagesState, StateGraph
from utils import ContextMode, make_actor, make_blocking_node, make_streaming_node, strip_think

logger = logging.getLogger(__name__)

WriterActor = make_actor("WriterActor", has_tools=True)


def _parse_sections(content: str) -> list[dict]:
    """Extract the JSON section list from the orchestrator's output."""
    clean = strip_think(content).strip()
    start = clean.find("[")
    end = clean.rfind("]")
    if start == -1 or end == -1:
        return [{"title": "Full Report", "brief": clean}]
    try:
        return json.loads(clean[start:end + 1])
    except json.JSONDecodeError:
        return [{"title": "Full Report", "brief": clean}]


def build_graph(
    orchestrator_actor, editor_actor,
    provider, model, writer_prompt, tools,
    num_writers=2, checkpointer=None, streaming=False,
):
    """Build the report writer graph with dynamic writer fan-out."""

    make = make_streaming_node if streaming else make_blocking_node
    orchestrate = make(orchestrator_actor, "orchestrator", context_mode=ContextMode.FULL)
    edit = make(editor_actor, "editor", context_mode=ContextMode.FULL)

    if streaming:
        async def write_sections(state: MessagesState):
            writer_ref = get_stream_writer()
            sections = _parse_sections(state["messages"][-1].content)[:num_writers]

            writers = [
                WriterActor.remote(provider, model, writer_prompt, tools)
                for _ in sections
            ]

            async def run_writer(actor, section):
                title = section.get("title", "Section")
                brief = section.get("brief", "")
                assignment = f"## {title}\n{brief}"
                msgs = [HumanMessage(content=assignment)]
                accumulated = None
                in_think = False
                for ref in actor.stream_call.remote(msgs):
                    chunk = await ref
                    accumulated = chunk if accumulated is None else accumulated + chunk
                    if chunk.content:
                        text = chunk.content
                        while text:
                            if in_think:
                                end_idx = text.find("</think>")
                                if end_idx != -1:
                                    text = text[end_idx + 8:]
                                    in_think = False
                                else:
                                    break
                            else:
                                start_idx = text.find("<think>")
                                if start_idx != -1:
                                    before = text[:start_idx]
                                    if before:
                                        writer_ref({"node": f"writer:{title}", "token": before})
                                    text = text[start_idx + 7:]
                                    in_think = True
                                else:
                                    writer_ref({"node": f"writer:{title}", "token": text})
                                    break
                writer_ref({"node": "writers", "token": f"\n--- Section '{title}' complete ---\n"})
                return title, accumulated

            try:
                results = await asyncio.gather(
                    *[run_writer(w, s) for w, s in zip(writers, sections)],
                    return_exceptions=True,
                )
            finally:
                for w in writers:
                    ray.kill(w)

            parts = []
            for r in results:
                if isinstance(r, Exception):
                    logger.error("Writer actor failed: %s", r)
                elif r[1]:
                    parts.append(f"## {r[0]}\n\n{strip_think(r[1].content)}")
            combined = "\n\n".join(parts) or "All writers failed to produce content."
            return {"messages": [AIMessage(content=combined)]}
    else:
        async def write_sections(state: MessagesState):
            sections = _parse_sections(state["messages"][-1].content)[:num_writers]

            writers = [
                WriterActor.remote(provider, model, writer_prompt, tools)
                for _ in sections
            ]

            async def run_writer(actor, section):
                title = section.get("title", "Section")
                brief = section.get("brief", "")
                assignment = f"## {title}\n{brief}"
                msgs = [HumanMessage(content=assignment)]
                result = await actor.call.remote(msgs)
                return title, result

            try:
                results = await asyncio.gather(
                    *[run_writer(w, s) for w, s in zip(writers, sections)],
                    return_exceptions=True,
                )
            finally:
                for w in writers:
                    ray.kill(w)

            parts = []
            for r in results:
                if isinstance(r, Exception):
                    logger.error("Writer actor failed: %s", r)
                elif r[1]:
                    parts.append(f"## {r[0]}\n\n{strip_think(r[1].content)}")
            combined = "\n\n".join(parts) or "All writers failed to produce content."
            return {"messages": [AIMessage(content=combined)]}

    graph = StateGraph(MessagesState)
    graph.add_node("orchestrator", orchestrate)
    graph.add_node("writers", write_sections)
    graph.add_node("editor", edit)

    graph.add_edge(START, "orchestrator")
    graph.add_edge("orchestrator", "writers")
    graph.add_edge("writers", "editor")
    graph.add_edge("editor", END)

    return graph.compile(checkpointer=checkpointer)
