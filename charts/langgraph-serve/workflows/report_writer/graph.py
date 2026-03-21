"""Graph builder for the report writer swarm.

START -> orchestrator -> writers (parallel fan-out) -> editor -> END

The writers node is a single graph node that internally spawns N Ray actors
in parallel, one per section assigned by the orchestrator.

Writers have a tool execution loop: the LLM call happens in a Ray actor,
but tool execution happens locally in the graph process because MCP tools
hold session references that can't survive Ray serialization.
"""

import asyncio
import json
import logging

import ray
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, MessagesState, StateGraph
from utils import ContextMode, make_actor, make_blocking_node, make_streaming_node, strip_think

logger = logging.getLogger(__name__)

WriterActor = make_actor("WriterActor", has_tools=True, num_cpus=0)

MAX_TOOL_ROUNDS = 5


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


def _has_tool_calls(msg) -> bool:
    return hasattr(msg, "tool_calls") and bool(msg.tool_calls)


async def _execute_tools_local(tool_calls, tools_by_name):
    """Execute tool calls in the graph process (not in Ray actors).

    MCP tools hold session state that can't survive Ray serialization,
    so tool execution must happen here where the sessions are alive.
    """
    results = []
    for tc in tool_calls:
        tool = tools_by_name.get(tc["name"])
        if tool is None:
            logger.warning("Writer requested unknown tool '%s'", tc["name"])
            results.append(ToolMessage(
                content=f"Error: unknown tool '{tc['name']}'",
                tool_call_id=tc["id"],
            ))
            continue
        try:
            output = await tool.ainvoke(tc["args"])
            logger.info("tool %s(%s) -> %d chars", tc["name"], tc["args"], len(str(output)))
            results.append(ToolMessage(content=str(output), tool_call_id=tc["id"]))
        except Exception as e:
            logger.error("tool '%s' raised: %s", tc["name"], e)
            results.append(ToolMessage(
                content=f"Error: tool '{tc['name']}' failed: {e}",
                tool_call_id=tc["id"],
            ))
    return results


def build_graph(
    orchestrator_actor, editor_actor,
    provider, model, writer_prompt, tools,
    num_writers=2, checkpointer=None, streaming=False,
):
    """Build the report writer graph with dynamic writer fan-out."""

    tools_by_name = {t.name: t for t in tools} if tools else {}

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

                for _round in range(MAX_TOOL_ROUNDS + 1):
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

                    if not _has_tool_calls(accumulated):
                        break

                    tool_names = [tc["name"] for tc in accumulated.tool_calls]
                    writer_ref({"node": f"writer:{title}", "token": f"\n[Researching: {', '.join(tool_names)}]\n"})
                    tool_results = await _execute_tools_local(accumulated.tool_calls, tools_by_name)
                    msgs = msgs + [accumulated] + tool_results

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

                result = None
                for _round in range(MAX_TOOL_ROUNDS + 1):
                    result = await actor.call.remote(msgs)
                    if not _has_tool_calls(result):
                        break
                    tool_results = await _execute_tools_local(result.tool_calls, tools_by_name)
                    msgs = msgs + [result] + tool_results

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
