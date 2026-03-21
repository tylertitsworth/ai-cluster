"""Service Debugger workflow — diagnose and fix broken K8s services.

Four-agent loop:
  Investigator (read-only) -> Fixer (proposes) -> Guardrails (validates) -> Executor (applies)
  Then back to Investigator to verify. Stops when Investigator reports FIXED or UNFIXABLE.
"""

import ray
from workflows.service_debugger.actors import (
    FixerActor,
    GuardrailsActor,
    InvestigatorActor,
    K8sExecutorActor,
)
from langchain_core.messages import AIMessage, HumanMessage

from workflows.service_debugger.graph import build_graph
from workflows.service_debugger.mcp import K8S_MCP_RO_URL, K8S_MCP_RW_URL, load_mcp_tools
from workflows.service_debugger.prompts import (
    EXECUTOR_PROMPT,
    FIXER_PROMPT,
    GUARDRAILS_PROMPT,
    INVESTIGATOR_PROMPT,
)

MAX_ITERATIONS = 5


async def run(base_url: str, model: str, query: str, thread_id: str, checkpointer) -> str:
    """Spin up fresh actor sandboxes, run the workflow, tear down."""
    ro_tools, _ = await load_mcp_tools(K8S_MCP_RO_URL)
    rw_tools, _ = await load_mcp_tools(K8S_MCP_RW_URL)

    investigator = InvestigatorActor.remote(base_url, model, INVESTIGATOR_PROMPT, ro_tools)
    fixer = FixerActor.remote(base_url, model, FIXER_PROMPT)
    guardrails = GuardrailsActor.remote(base_url, model, GUARDRAILS_PROMPT)
    executor = K8sExecutorActor.remote(base_url, model, EXECUTOR_PROMPT, rw_tools)

    actors = [investigator, fixer, guardrails, executor]

    try:
        compiled = build_graph(
            investigator, fixer, guardrails, executor,
            ro_tools, rw_tools, checkpointer,
        )
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": MAX_ITERATIONS * 10}
        result = await compiled.ainvoke(
            {"messages": [HumanMessage(content=query)]}, config,
        )
        return result["messages"][-1].content
    finally:
        for actor in actors:
            ray.kill(actor)


async def stream(base_url: str, model: str, query: str, thread_id: str, checkpointer):
    """Spin up fresh actor sandboxes, stream the workflow, tear down."""
    ro_tools, _ = await load_mcp_tools(K8S_MCP_RO_URL)
    rw_tools, _ = await load_mcp_tools(K8S_MCP_RW_URL)

    investigator = InvestigatorActor.remote(base_url, model, INVESTIGATOR_PROMPT, ro_tools)
    fixer = FixerActor.remote(base_url, model, FIXER_PROMPT)
    guardrails = GuardrailsActor.remote(base_url, model, GUARDRAILS_PROMPT)
    executor = K8sExecutorActor.remote(base_url, model, EXECUTOR_PROMPT, rw_tools)

    actors = [investigator, fixer, guardrails, executor]

    try:
        compiled = build_graph(
            investigator, fixer, guardrails, executor,
            ro_tools, rw_tools, checkpointer,
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
                    if msg.content:
                        yield {"node": node_name, "content": msg.content}
                    if msg.tool_calls:
                        yield {
                            "node": node_name,
                            "tool_calls": [
                                {"name": tc["name"], "args": tc["args"]}
                                for tc in msg.tool_calls
                            ],
                        }
    finally:
        for actor in actors:
            ray.kill(actor)
