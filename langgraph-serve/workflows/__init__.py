"""Workflow registry. Each workflow lives in its own file in this package.

To add a new workflow:
  1. Create a new file in this folder (e.g. workflows/my_workflow.py)
  2. Define async def run(base_url, model, query, thread_id, checkpointer) -> str
  3. Define async def stream(base_url, model, query, thread_id, checkpointer) -> yields dicts
  4. Import and register both in WORKFLOWS below.
"""

from workflows import example

WORKFLOWS = {
    "example": {"run": example.run, "stream": example.stream},
}
