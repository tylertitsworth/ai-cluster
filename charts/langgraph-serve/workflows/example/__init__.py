"""Example workflow: summarizer distills input, executor uses tools.

START -> summarizer -> executor <-> tools -> END
"""

import operator
from typing import Annotated

import ray
from actors import ToolActor
from langgraph.graph import END, START, MessagesState, StateGraph
from tools import TOOLS
from utils import (
    load_prompt,
    make_actor,
    make_blocking_node,
    make_streaming_node,
    run_workflow,
    stream_workflow,
)

CLI_META = {
    "nodes": {
        "summarizer": "cyan",
        "executor": "green",
    },
    "hidden_nodes": ["tools"],
}

SummarizerActor = make_actor("SummarizerActor")
ExecutorActor = make_actor("ExecutorActor", has_tools=True)

MAX_TOOL_ROUNDS = 10

SUMMARIZER_PROMPT = load_prompt(
    "example", "summarizer",
    "You are a summarizer. Read the user's message and distill it into "
    "a clear, concise task description for another agent to act on. "
    "Do not perform the task yourself — just restate what needs to be done.",
)

EXECUTOR_PROMPT = load_prompt(
    "example", "executor",
    "You are an executor. Carry out the task described in the conversation "
    "using your available tools (current time and math). "
    "Respond with the final answer.",
)


class ExampleState(MessagesState):
    tool_rounds: Annotated[int, operator.add]


def _build(provider, model, checkpointer=None, streaming=False):
    summarizer = SummarizerActor.remote(provider, model, SUMMARIZER_PROMPT)
    executor = ExecutorActor.remote(provider, model, EXECUTOR_PROMPT, TOOLS)
    tool_actor = ToolActor.remote(TOOLS)

    make = make_streaming_node if streaming else make_blocking_node
    summarize = make(summarizer, "summarizer")
    execute = make(executor, "executor")

    async def tools(state: ExampleState):
        results = await tool_actor.call.remote(state["messages"][-1].tool_calls)
        return {"messages": results, "tool_rounds": 1}

    def should_continue(state: ExampleState):
        if state.get("tool_rounds", 0) >= MAX_TOOL_ROUNDS:
            return END
        if state["messages"][-1].tool_calls:
            return "tools"
        return END

    graph = StateGraph(ExampleState)
    graph.add_node("summarizer", summarize)
    graph.add_node("executor", execute)
    graph.add_node("tools", tools)

    graph.add_edge(START, "summarizer")
    graph.add_edge("summarizer", "executor")
    graph.add_conditional_edges("executor", should_continue, ["tools", END])
    graph.add_edge("tools", "executor")

    compiled = graph.compile(checkpointer=checkpointer)
    return compiled, [summarizer, executor, tool_actor]


async def run(provider: str, model: str, query: str, thread_id: str, checkpointer, **kwargs) -> str:
    return await run_workflow(
        lambda **kw: _build(provider, model, **kw),
        query, thread_id, checkpointer,
        recursion_limit=50,
    )


async def stream(provider: str, model: str, query: str, thread_id: str, checkpointer, **kwargs):
    async for event in stream_workflow(
        lambda **kw: _build(provider, model, **kw),
        query, thread_id, checkpointer,
        recursion_limit=50,
    ):
        yield event
