# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "rich", "click"]
# ///
"""CLI for the LangGraph RayService.

Usage:
  uv run cli.py query "What is 7 factorial?"
  uv run cli.py query --workflow example --thread my-session "What time is it?"
  uv run cli.py workflows
  uv run cli.py workflows --url https://langgraph/serve
"""

import json
import os
import sys

import click
import httpx
from rich.console import Console
from rich.markup import escape
from rich.theme import Theme

theme = Theme({
    "summarizer": "cyan",
    "executor": "green",
    "tools": "yellow",
    "error": "bold red",
    "info": "dim",
})
console = Console(theme=theme)

DEFAULT_URL = os.environ.get("LANGGRAPH_URL", "https://langgraph/serve")


@click.group()
@click.option("--url", default=DEFAULT_URL, envvar="LANGGRAPH_URL", help="Service base URL")
@click.pass_context
def cli(ctx, url):
    ctx.ensure_object(dict)
    ctx.obj["url"] = url.rstrip("/")


@cli.command()
@click.pass_context
def workflows(ctx):
    """List available workflows."""
    url = ctx.obj["url"]
    try:
        resp = httpx.get(f"{url}/workflows", verify=False, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        console.print("[info]Available workflows:[/info]")
        for name in data["workflows"]:
            console.print(f"  - {name}")
    except httpx.HTTPError as e:
        console.print(f"[error]Failed to list workflows: {e}[/error]")
        sys.exit(1)


@cli.command()
@click.argument("text")
@click.option("--workflow", "-w", default="example", help="Workflow name")
@click.option("--thread", "-t", default=None, help="Thread ID for conversation memory")
@click.pass_context
def query(ctx, text, workflow, thread):
    """Send a query and stream the response."""
    url = ctx.obj["url"]
    payload = {"workflow": workflow, "query": text}
    if thread:
        payload["thread_id"] = thread

    try:
        with httpx.stream(
            "POST",
            f"{url}/stream",
            json=payload,
            verify=False,
            timeout=httpx.Timeout(connect=10, read=300, write=10, pool=10),
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                chunk = json.loads(line[6:])
                _render(chunk)
    except httpx.HTTPError as e:
        console.print(f"[error]Request failed: {e}[/error]")
        sys.exit(1)


def _render(chunk: dict):
    node = chunk.get("node", "unknown")
    style = node if node in ("summarizer", "executor", "tools") else "info"

    if "tool_calls" in chunk:
        for tc in chunk["tool_calls"]:
            console.print(
                f"[{style}][{node}][/{style}] "
                f"calling [bold]{tc['name']}[/bold]({escape(str(tc['args']))})"
            )
    elif "content" in chunk:
        console.print(f"[{style}][{node}][/{style}] {escape(chunk['content'])}")


if __name__ == "__main__":
    cli()
