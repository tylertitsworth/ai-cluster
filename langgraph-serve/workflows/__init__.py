"""Workflow registry. Each workflow lives in its own file or package in this directory.

To add a new workflow:
  1. Create a new file or package (e.g. workflows/my_workflow.py or workflows/my_workflow/)
  2. Define async def run(base_url, model, query, thread_id, checkpointer) -> str
  3. Define async def stream(base_url, model, query, thread_id, checkpointer) -> yields dicts
  4. Import and register both in WORKFLOWS below.
"""

from workflows import example
from workflows import service_debugger

WORKFLOWS = {
    "example": {"run": example.run, "stream": example.stream},
    "service-debugger": {"run": service_debugger.run, "stream": service_debugger.stream},
}
