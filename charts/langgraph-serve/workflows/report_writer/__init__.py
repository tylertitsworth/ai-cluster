"""Report Writer Swarm — parallel research and writing with fan-out/fan-in.

Orchestrator decomposes topic -> N Writers research in parallel -> Editor assembles final report.
"""

from utils import make_actor
from workflow import Workflow
from workflows.report_writer.graph import build_graph
from workflows.report_writer.mcp import load_all_tools

OrchestratorActor = make_actor("OrchestratorActor")
EditorActor = make_actor("EditorActor")


class ReportWriterWorkflow(Workflow):
    name = "report-writer"
    cli_meta = {
        "nodes": {
            "orchestrator": "bright_blue",
            "writers": "bright_magenta",
            "editor": "bright_green",
        },
        "hidden_nodes": [],
        "prefix_styles": {"writer:": "writers"},
    }

    async def get_tools(self):
        return await load_all_tools()

    def build(self, provider, model, prompts, tools, checkpointer=None, streaming=False, **kwargs):
        writers = kwargs.get("writers", 2)
        orchestrator_prompt = prompts["orchestrator"].replace("{num_sections}", str(writers))
        orchestrator = OrchestratorActor.remote(provider, model, orchestrator_prompt)
        editor = EditorActor.remote(provider, model, prompts["editor"])
        compiled = build_graph(
            orchestrator,
            editor,
            provider,
            model,
            prompts["writer"],
            tools,
            num_writers=writers,
            checkpointer=checkpointer,
            streaming=streaming,
        )
        return compiled, [orchestrator, editor]


workflow = ReportWriterWorkflow()
