"""Graph builder for the report writer swarm.

START -> orchestrator -> writers (parallel fan-out) -> editor -> END

The writers node is a single graph node that internally spawns N Ray actors
in parallel, one per section assigned by the orchestrator.
"""

import asyncio
import json

import ray
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, MessagesState, StateGraph
from utils import ContextMode, make_actor, make_blocking_node, make_streaming_node, strip_think

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
                assignment = f"## {section['title']}\n{section['brief']}"
                msgs = [HumanMessage(content=assignment)]
                accumulated = None
                for ref in actor.stream_call.remote(msgs):
                    chunk = await ref
                    accumulated = chunk if accumulated is None else accumulated + chunk
                    if chunk.content:
                        clean = strip_think(chunk.content)
                        if clean:
                            writer_ref({"node": f"writer:{section['title']}", "token": clean})
                writer_ref({"node": "writers", "token": f"\n--- Section '{section['title']}' complete ---\n"})
                return section["title"], accumulated

            results = await asyncio.gather(*[
                run_writer(w, s) for w, s in zip(writers, sections)
            ])

            for w in writers:
                ray.kill(w)

            parts = [f"## {title}\n\n{strip_think(msg.content)}" for title, msg in results if msg]
            combined = "\n\n".join(parts)
            return {"messages": [AIMessage(content=combined)]}
    else:
        async def write_sections(state: MessagesState):
            sections = _parse_sections(state["messages"][-1].content)[:num_writers]

            writers = [
                WriterActor.remote(provider, model, writer_prompt, tools)
                for _ in sections
            ]

            async def run_writer(actor, section):
                assignment = f"## {section['title']}\n{section['brief']}"
                msgs = [HumanMessage(content=assignment)]
                result = await actor.call.remote(msgs)
                return section["title"], result

            results = await asyncio.gather(*[
                run_writer(w, s) for w, s in zip(writers, sections)
            ])

            for w in writers:
                ray.kill(w)

            parts = [f"## {title}\n\n{strip_think(msg.content)}" for title, msg in results if msg]
            combined = "\n\n".join(parts)
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
