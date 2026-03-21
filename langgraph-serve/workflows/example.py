"""Example workflow: summarizer distills input, executor uses tools.

Uses two composable subgraphs:
  - summarizer_subgraph: single-node graph that distills user input
  - executor_subgraph: ReAct loop (executor <-> tools) until a final answer

The parent graph wires them: START -> summarizer -> executor -> END

Future workflows can import and reuse build_summarizer_subgraph /
build_executor_subgraph independently.
"""

import ray
from actors import ExecutorActor, SummarizerActor, ToolActor
from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from tools import TOOLS

SUMMARIZER_PROMPT = (
    "You are a summarizer. Read the user's message and distill it into "
    "a clear, concise task description for another agent to act on. "
    "Do not perform the task yourself — just restate what needs to be done."
)

EXECUTOR_PROMPT = (
    "You are an executor. Carry out the task described in the conversation "
    "using your available tools (current time and math). "
    "Respond with the final answer."
)


# ---------------------------------------------------------------------------
# Reusable subgraph builders
# ---------------------------------------------------------------------------

def build_summarizer_subgraph(summarizer_actor):
    """Single-node subgraph: calls the summarizer actor."""

    async def summarize(state: MessagesState):
        response = await summarizer_actor.call.remote(state["messages"])
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("summarizer", summarize)
    graph.add_edge(START, "summarizer")
    graph.add_edge("summarizer", END)
    return graph.compile()


def build_executor_subgraph(executor_actor, tool_actor):
    """ReAct loop subgraph: executor calls tools until it produces a final answer."""

    async def execute(state: MessagesState):
        response = await executor_actor.call.remote(state["messages"])
        return {"messages": [response]}

    async def tools(state: MessagesState):
        results = await tool_actor.call.remote(state["messages"][-1].tool_calls)
        return {"messages": results}

    def should_continue(state: MessagesState):
        if state["messages"][-1].tool_calls:
            return "tools"
        return END

    graph = StateGraph(MessagesState)
    graph.add_node("executor", execute)
    graph.add_node("tools", tools)
    graph.add_edge(START, "executor")
    graph.add_conditional_edges("executor", should_continue, ["tools", END])
    graph.add_edge("tools", "executor")
    return graph.compile()


# ---------------------------------------------------------------------------
# Parent graph — composes the subgraphs
# ---------------------------------------------------------------------------

def _build(base_url, model, checkpointer=None):
    """Create actors, build subgraphs, compose into parent graph."""
    summarizer = SummarizerActor.remote(base_url, model, SUMMARIZER_PROMPT)
    executor = ExecutorActor.remote(base_url, model, EXECUTOR_PROMPT, TOOLS)
    tool_actor = ToolActor.remote(TOOLS)

    summarizer_sub = build_summarizer_subgraph(summarizer)
    executor_sub = build_executor_subgraph(executor, tool_actor)

    parent = StateGraph(MessagesState)
    parent.add_node("summarizer", summarizer_sub)
    parent.add_node("executor", executor_sub)
    parent.add_edge(START, "summarizer")
    parent.add_edge("summarizer", "executor")
    parent.add_edge("executor", END)

    compiled = parent.compile(checkpointer=checkpointer)
    return compiled, [summarizer, executor, tool_actor]


async def run(base_url: str, model: str, query: str, thread_id: str, checkpointer) -> str:
    """Spin up fresh actor sandboxes, run the workflow, tear down."""
    compiled, actors = _build(base_url, model, checkpointer)
    config = {"configurable": {"thread_id": thread_id}}
    try:
        result = await compiled.ainvoke(
            {"messages": [HumanMessage(content=query)]}, config
        )
        return result["messages"][-1].content
    finally:
        for actor in actors:
            ray.kill(actor)


async def stream(base_url: str, model: str, query: str, thread_id: str, checkpointer):
    """Spin up fresh actor sandboxes, stream the workflow, tear down."""
    compiled, actors = _build(base_url, model, checkpointer)
    config = {"configurable": {"thread_id": thread_id}}
    try:
        async for chunk in compiled.astream(
            {"messages": [HumanMessage(content=query)]},
            config,
            stream_mode="updates",
        ):
            for node_name, update in chunk.items():
                messages = update.get("messages", [])
                for msg in messages:
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        yield {
                            "node": node_name,
                            "tool_calls": [
                                {"name": tc["name"], "args": tc["args"]}
                                for tc in msg.tool_calls
                            ],
                        }
                    elif hasattr(msg, "content") and msg.content:
                        yield {"node": node_name, "content": msg.content}
    finally:
        for actor in actors:
            ray.kill(actor)
