"""Service Debugger workflow — diagnose and fix broken K8s services.

Four-agent loop:
  Investigator (read-only) -> Fixer (proposes) -> Guardrails (validates) -> Executor (applies)
  Then back to Investigator to verify. Stops when Investigator reports FIXED or UNFIXABLE.
"""

import asyncio

from utils import make_actor
from workflow import Workflow
from workflows.service_debugger.graph import build_graph
from workflows.service_debugger.mcp import K8S_MCP_RO_URL, K8S_MCP_RW_URL, load_mcp_tools

InvestigatorActor = make_actor("InvestigatorActor", has_tools=True)
FixerActor = make_actor("FixerActor")
GuardrailsActor = make_actor("GuardrailsActor")
K8sExecutorActor = make_actor("K8sExecutorActor", has_tools=True)

MAX_ITERATIONS = 5


class ServiceDebuggerWorkflow(Workflow):
    name = "service-debugger"
    cli_meta = {
        "nodes": {
            "investigator": "blue",
            "fixer": "magenta",
            "guardrails": "yellow",
            "k8s_executor": "red",
        },
        "hidden_nodes": ["investigate_tools", "execute_tools", "guardrails_rejected"],
    }
    recursion_limit = MAX_ITERATIONS * 30

    async def get_tools(self):
        (ro_tools, ro_client), (rw_tools, rw_client) = await asyncio.gather(
            load_mcp_tools(K8S_MCP_RO_URL),
            load_mcp_tools(K8S_MCP_RW_URL),
        )
        return {
            "ro": ro_tools,
            "rw": rw_tools,
            "_clients": [ro_client, rw_client],
        }

    def build(self, provider, model, prompts, tools, checkpointer=None, streaming=False, **kwargs):
        ro_tools = tools["ro"]
        rw_tools = tools["rw"]
        investigator = InvestigatorActor.remote(
            provider, model, prompts["investigator"], ro_tools,
        )
        fixer = FixerActor.remote(provider, model, prompts["fixer"])
        guardrails = GuardrailsActor.remote(provider, model, prompts["guardrails"])
        executor = K8sExecutorActor.remote(
            provider, model, prompts["executor"], rw_tools,
        )
        compiled = build_graph(
            investigator, fixer, guardrails, executor,
            ro_tools, rw_tools, checkpointer, streaming,
            max_iterations=MAX_ITERATIONS,
        )
        return compiled, [investigator, fixer, guardrails, executor]


workflow = ServiceDebuggerWorkflow()
