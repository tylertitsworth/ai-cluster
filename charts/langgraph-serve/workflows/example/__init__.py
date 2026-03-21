"""Example workflow: summarizer distills input, executor uses tools.

START -> summarizer -> executor <-> tools -> END
"""

import operator
from typing import Annotated

from actors import ToolActor
from langgraph.graph import END, START, MessagesState, StateGraph
from tools import TOOLS
from utils import make_actor, make_blocking_node, make_streaming_node
from workflow import Workflow

SummarizerActor = make_actor("SummarizerActor")
ExecutorActor = make_actor("ExecutorActor", has_tools=True)

MAX_TOOL_ROUNDS = 10


class ExampleState(MessagesState):
    tool_rounds: Annotated[int, operator.add]


class ExampleWorkflow(Workflow):
    name = "example"
    cli_meta = {
        "nodes": {
            "summarizer": "cyan",
            "executor": "green",
        },
        "hidden_nodes": ["tools"],
    }

    def build(self, provider, model, prompts, tools, checkpointer=None, streaming=False, **kwargs):
        summarizer = SummarizerActor.remote(provider, model, prompts["summarizer"])
        executor = ExecutorActor.remote(provider, model, prompts["executor"], TOOLS)
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


workflow = ExampleWorkflow()
