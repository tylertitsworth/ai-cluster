"""Service Debugger workflow — diagnose and fix broken K8s services.

Four-agent loop:
  Investigator (read-only) -> Fixer (proposes) -> Guardrails (validates) -> Executor (applies)
  Then back to Investigator to verify. Stops when Investigator reports FIXED.
"""

import os

import ray
from actors import (
    FixerActor,
    GuardrailsActor,
    InvestigatorActor,
    K8sExecutorActor,
    ToolActor,
)
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, MessagesState, StateGraph

K8S_MCP_RO_URL = os.environ.get(
    "K8S_MCP_RO_URL",
    "http://kubernetes-mcp-server.kubernetes-mcp.svc.cluster.local:8080/mcp",
)
K8S_MCP_RW_URL = os.environ.get(
    "K8S_MCP_RW_URL",
    "http://kubernetes-mcp-server-rw.kubernetes-mcp.svc.cluster.local:8080/mcp",
)

MAX_ITERATIONS = 5

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

INVESTIGATOR_PROMPT = """\
You are an Investigator agent for Kubernetes services. You have read-only
access to a Kubernetes cluster via MCP tools (pods, logs, events, resources).

Given a service name, investigate what is wrong:
1. List pods, check their status and recent events
2. Read logs from failing containers
3. Check the service, deployment, and ingress resources
4. Look for common issues: CrashLoopBackOff, ImagePullBackOff, OOMKilled,
   misconfigured probes, missing ConfigMaps/Secrets, resource limits

After investigation, end your response with exactly one of:
  STATUS: NEEDS_FIX — if you found an issue that needs fixing
  STATUS: FIXED — if the service is now healthy after a prior fix was applied
"""

FIXER_PROMPT = """\
You are a Fixer agent. You receive diagnostic information from the Investigator
about a broken Kubernetes service.

Propose specific kubectl or Kubernetes API commands to fix the issue. Be precise
about namespaces, resource names, and field paths. Do NOT execute anything —
just describe what commands should be run and why.

Format your proposed commands clearly, one per line, prefixed with $.
"""

GUARDRAILS_PROMPT = """\
You are a Guardrails agent. You receive proposed fix commands from the Fixer
and must evaluate whether they are safe to execute.

Check for:
1. Commands that could affect services OTHER than the target service
2. Destructive operations (delete namespace, delete PVC, scale to 0 on
   unrelated deployments)
3. Commands that could cause cascading failures
4. Missing namespace scoping that could hit the wrong resources

End your response with exactly one of:
  VERDICT: SAFE — commands are scoped correctly and safe to execute
  VERDICT: UNSAFE — explain what is dangerous and suggest alternatives
"""

EXECUTOR_PROMPT = """\
You are an Executor agent. You have read-write access to a Kubernetes cluster
via MCP tools. Execute ONLY the approved commands described in the conversation.
Do not improvise additional changes. Report what you did and the result.
"""


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------

def investigator_route(state: MessagesState):
    content = state["messages"][-1].content if state["messages"] else ""
    if "STATUS: FIXED" in content:
        return END
    return "fixer"


def guardrails_route(state: MessagesState):
    content = state["messages"][-1].content if state["messages"] else ""
    if "VERDICT: UNSAFE" in content:
        return "investigator"
    return "k8s_executor"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

async def _load_mcp_tools(url: str):
    """Load LangChain tools from an MCP server endpoint."""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(
        {"k8s": {"url": url, "transport": "streamable_http"}}
    )
    await client.__aenter__()
    tools = client.get_tools()
    return tools, client


def _build_graph(
    investigator_actor, fixer_actor, guardrails_actor, executor_actor,
    ro_tool_actor, rw_tool_actor, checkpointer=None,
):
    """Wire the four agents into the debugging loop."""

    async def investigate(state: MessagesState):
        response = await investigator_actor.call.remote(state["messages"])
        return {"messages": [response]}

    async def investigate_tools(state: MessagesState):
        results = await ro_tool_actor.call.remote(state["messages"][-1].tool_calls)
        return {"messages": results}

    def investigate_should_continue(state: MessagesState):
        if state["messages"][-1].tool_calls:
            return "investigate_tools"
        return "investigate_route"

    async def investigate_route_node(state: MessagesState):
        return state

    async def fix(state: MessagesState):
        response = await fixer_actor.call.remote(state["messages"])
        return {"messages": [response]}

    async def guard(state: MessagesState):
        response = await guardrails_actor.call.remote(state["messages"])
        return {"messages": [response]}

    async def execute(state: MessagesState):
        response = await executor_actor.call.remote(state["messages"])
        return {"messages": [response]}

    async def execute_tools(state: MessagesState):
        results = await rw_tool_actor.call.remote(state["messages"][-1].tool_calls)
        return {"messages": results}

    def execute_should_continue(state: MessagesState):
        if state["messages"][-1].tool_calls:
            return "execute_tools"
        return "investigator"

    graph = StateGraph(MessagesState)

    graph.add_node("investigator", investigate)
    graph.add_node("investigate_tools", investigate_tools)
    graph.add_node("investigate_route", investigate_route_node)
    graph.add_node("fixer", fix)
    graph.add_node("guardrails", guard)
    graph.add_node("k8s_executor", execute)
    graph.add_node("execute_tools", execute_tools)

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
        "guardrails", guardrails_route, ["k8s_executor", "investigator"],
    )
    graph.add_conditional_edges(
        "k8s_executor", execute_should_continue,
        ["execute_tools", "investigator"],
    )
    graph.add_edge("execute_tools", "k8s_executor")

    return graph.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Public API — run() and stream()
# ---------------------------------------------------------------------------

async def run(base_url: str, model: str, query: str, thread_id: str, checkpointer) -> str:
    ro_tools, ro_client = await _load_mcp_tools(K8S_MCP_RO_URL)
    rw_tools, rw_client = await _load_mcp_tools(K8S_MCP_RW_URL)

    investigator = InvestigatorActor.remote(base_url, model, INVESTIGATOR_PROMPT, ro_tools)
    fixer = FixerActor.remote(base_url, model, FIXER_PROMPT)
    guardrails = GuardrailsActor.remote(base_url, model, GUARDRAILS_PROMPT)
    executor = K8sExecutorActor.remote(base_url, model, EXECUTOR_PROMPT, rw_tools)
    ro_tool_actor = ToolActor.remote(ro_tools)
    rw_tool_actor = ToolActor.remote(rw_tools)

    actors = [investigator, fixer, guardrails, executor, ro_tool_actor, rw_tool_actor]

    try:
        compiled = _build_graph(
            investigator, fixer, guardrails, executor,
            ro_tool_actor, rw_tool_actor, checkpointer,
        )
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": MAX_ITERATIONS * 10}
        result = await compiled.ainvoke(
            {"messages": [HumanMessage(content=query)]}, config,
        )
        return result["messages"][-1].content
    finally:
        for actor in actors:
            ray.kill(actor)
        await ro_client.__aexit__(None, None, None)
        await rw_client.__aexit__(None, None, None)


async def stream(base_url: str, model: str, query: str, thread_id: str, checkpointer):
    ro_tools, ro_client = await _load_mcp_tools(K8S_MCP_RO_URL)
    rw_tools, rw_client = await _load_mcp_tools(K8S_MCP_RW_URL)

    investigator = InvestigatorActor.remote(base_url, model, INVESTIGATOR_PROMPT, ro_tools)
    fixer = FixerActor.remote(base_url, model, FIXER_PROMPT)
    guardrails = GuardrailsActor.remote(base_url, model, GUARDRAILS_PROMPT)
    executor = K8sExecutorActor.remote(base_url, model, EXECUTOR_PROMPT, rw_tools)
    ro_tool_actor = ToolActor.remote(ro_tools)
    rw_tool_actor = ToolActor.remote(rw_tools)

    actors = [investigator, fixer, guardrails, executor, ro_tool_actor, rw_tool_actor]

    try:
        compiled = _build_graph(
            investigator, fixer, guardrails, executor,
            ro_tool_actor, rw_tool_actor, checkpointer,
        )
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": MAX_ITERATIONS * 10}

        async for chunk in compiled.astream(
            {"messages": [HumanMessage(content=query)]},
            config,
            stream_mode="updates",
        ):
            for node_name, update in chunk.items():
                messages = update.get("messages", [])
                for msg in messages:
                    if not isinstance(msg, AIMessage):
                        continue
                    if msg.tool_calls:
                        yield {
                            "node": node_name,
                            "tool_calls": [
                                {"name": tc["name"], "args": tc["args"]}
                                for tc in msg.tool_calls
                            ],
                        }
                    elif msg.content:
                        yield {"node": node_name, "content": msg.content}
    finally:
        for actor in actors:
            ray.kill(actor)
        await ro_client.__aexit__(None, None, None)
        await rw_client.__aexit__(None, None, None)
