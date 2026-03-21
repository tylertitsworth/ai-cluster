"""Graph builder and routing logic for the service debugger workflow.

MCP tool execution uses langgraph.prebuilt.ToolNode (in-process) instead of
Ray actors because MCP tool objects hold session references that can't survive
Ray serialization. Agent LLM calls still dispatch to Ray actors.
"""

import operator
from typing import Annotated

from langchain_core.messages import AIMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from utils import ContextMode, make_blocking_node, make_streaming_node, strip_think

MAX_TOOL_CALLS_PER_AGENT = 5


MAX_GUARDRAILS_RETRIES = 2


class ServiceDebuggerState(MessagesState):
    iteration_count: Annotated[int, operator.add]
    guardrails_rejections: Annotated[int, operator.add]


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------

def investigator_route(state: ServiceDebuggerState):
    raw = state["messages"][-1].content if state["messages"] else ""
    content = strip_think(raw)
    if "STATUS: FIXED" in content or "STATUS: UNFIXABLE" in content:
        return END
    return "fixer"


def guardrails_route(state: ServiceDebuggerState):
    raw = state["messages"][-1].content if state["messages"] else ""
    content = strip_think(raw)
    if "VERDICT: UNSAFE" in content:
        rejections = state.get("guardrails_rejections", 0)
        if rejections >= MAX_GUARDRAILS_RETRIES:
            return "investigator"
        return "guardrails_rejected"
    return "k8s_executor"


def _count_consecutive_tool_rounds(messages) -> int:
    count = 0
    for msg in reversed(messages):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            count += 1
        elif msg.type == "tool":
            continue
        else:
            break
    return count


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(
    investigator_actor, fixer_actor, guardrails_actor, executor_actor,
    ro_tools, rw_tools, checkpointer=None, streaming=False,
    max_iterations=5,
):
    """Wire the four agents into the debugging loop."""
    ro_tool_node = ToolNode(ro_tools, handle_tool_errors=True)
    rw_tool_node = ToolNode(rw_tools, handle_tool_errors=True)

    make = make_streaming_node if streaming else make_blocking_node
    investigate = make(investigator_actor, "investigator", context_mode=ContextMode.SUMMARY)
    fix = make(fixer_actor, "fixer", context_mode=ContextMode.SUMMARY)
    guard = make(guardrails_actor, "guardrails", context_mode=ContextMode.SUMMARY)
    execute = make(executor_actor, "k8s_executor", context_mode=ContextMode.NONE)

    def investigate_should_continue(state: ServiceDebuggerState):
        last = state["messages"][-1]
        if not (hasattr(last, "tool_calls") and last.tool_calls):
            return "investigate_route"
        if _count_consecutive_tool_rounds(state["messages"]) >= MAX_TOOL_CALLS_PER_AGENT:
            return "investigate_route"
        return "investigate_tools"

    async def investigate_route_node(state: ServiceDebuggerState):
        count = state.get("iteration_count", 0) + 1
        if count > max_iterations:
            msg = (
                f"Investigation loop reached the maximum of {max_iterations} "
                "iterations without resolving the issue. STATUS: UNFIXABLE"
            )
            if streaming:
                get_stream_writer()({"node": "investigator", "token": msg})
            return {
                "iteration_count": 1,
                "messages": [AIMessage(content=msg)],
            }
        return {"iteration_count": 1}

    async def guardrails_rejected_node(state: ServiceDebuggerState):
        """Bump rejection counter when guardrails says UNSAFE, then retry fixer."""
        return {"guardrails_rejections": 1}

    def execute_should_continue(state: ServiceDebuggerState):
        last = state["messages"][-1]
        if not (hasattr(last, "tool_calls") and last.tool_calls):
            return "investigator"
        if _count_consecutive_tool_rounds(state["messages"]) >= MAX_TOOL_CALLS_PER_AGENT:
            return "investigator"
        return "execute_tools"

    graph = StateGraph(ServiceDebuggerState)

    graph.add_node("investigator", investigate)
    graph.add_node("investigate_tools", ro_tool_node)
    graph.add_node("investigate_route", investigate_route_node)
    graph.add_node("fixer", fix)
    graph.add_node("guardrails", guard)
    graph.add_node("guardrails_rejected", guardrails_rejected_node)
    graph.add_node("k8s_executor", execute)
    graph.add_node("execute_tools", rw_tool_node)

    graph.add_edge(START, "investigator")
    graph.add_conditional_edges(
        "investigator", investigate_should_continue,
        ["investigate_tools", "investigate_route"],
    )
    graph.add_edge("investigate_tools", "investigator")
    graph.add_conditional_edges(
        "investigate_route", investigator_route, ["fixer", END],
    )
    graph.add_edge("fixer", "guardrails")
    graph.add_conditional_edges(
        "guardrails", guardrails_route,
        ["k8s_executor", "guardrails_rejected", "investigator"],
    )
    graph.add_edge("guardrails_rejected", "fixer")
    graph.add_conditional_edges(
        "k8s_executor", execute_should_continue,
        ["execute_tools", "investigator"],
    )
    graph.add_edge("execute_tools", "k8s_executor")

    return graph.compile(checkpointer=checkpointer)
