"""Workflow registry. Each workflow lives in its own package in this directory.

To add a new workflow:
  1. Create a new package (e.g. workflows/my_workflow/)
  2. Define async def run(provider, model, query, thread_id, checkpointer, **kwargs) -> str
  3. Define async def stream(provider, model, query, thread_id, checkpointer, **kwargs) -> yields dicts
  4. Define CLI_META dict with node styles, hidden nodes, and optional prefix_styles
  5. Import and register run, stream, and CLI_META in WORKFLOWS below.
"""

from workflows import example
from workflows import report_writer
from workflows import service_debugger

WORKFLOWS = {
    "example": {"run": example.run, "stream": example.stream, "cli_meta": example.CLI_META},
    "report-writer": {"run": report_writer.run, "stream": report_writer.stream, "cli_meta": report_writer.CLI_META},
    "service-debugger": {"run": service_debugger.run, "stream": service_debugger.stream, "cli_meta": service_debugger.CLI_META},
}
