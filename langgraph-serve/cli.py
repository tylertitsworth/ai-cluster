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

import hashlib
import json
import os
import sys
import uuid

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

DEFAULT_URL = os.environ.get("LANGGRAPH_URL", "https://langgraph.tail79a5c8.ts.net/serve")


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


def _session_thread_id():
    """Stable thread ID derived from the current TTY session."""
    tty = os.environ.get("TTY") or os.ttyname(sys.stdin.fileno()) if sys.stdin.isatty() else None
    pid = os.getppid()
    seed = f"{tty}-{pid}" if tty else str(pid)
    return hashlib.sha256(seed.encode()).hexdigest()[:16]


@cli.command()
@click.argument("text")
@click.option("--workflow", "-w", default="example", help="Workflow name")
@click.option("--thread", "-t", default=None, help="Thread ID for conversation memory")
@click.option("--no-cache", is_flag=True, help="Use a fresh thread ID instead of the session default")
@click.pass_context
def query(ctx, text, workflow, thread, no_cache):
    """Send a query and stream the response."""
    url = ctx.obj["url"]
    if thread:
        thread_id = thread
    elif no_cache:
        thread_id = str(uuid.uuid4())
    else:
        thread_id = _session_thread_id()
    console.print(f"[info]thread: {thread_id}[/info]")
    payload = {"workflow": workflow, "query": text, "thread_id": thread_id}

    try:
        with httpx.stream(
            "POST",
            f"{url}/stream",
            json=payload,
            verify=False,
            timeout=httpx.Timeout(connect=10, read=300, write=10, pool=10),
        ) as resp:
            resp.raise_for_status()
            seen = set()
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                chunk = json.loads(line[6:])
                _render(chunk, seen)
    except httpx.HTTPError as e:
        console.print(f"[error]Request failed: {e}[/error]")
        sys.exit(1)


def _render(chunk: dict, seen: set):
    node = chunk.get("node", "unknown")
    style = node if node in ("summarizer", "executor", "tools") else "info"

    if node == "tools":
        return

    if "tool_calls" in chunk:
        for tc in chunk["tool_calls"]:
            key = f"tool:{tc['name']}:{tc['args']}"
            if key in seen:
                continue
            seen.add(key)
            console.print(
                f"[{style}]\\[{node}][/{style}] "
                f"calling [bold]{tc['name']}[/bold]({escape(str(tc['args']))})"
            )
    elif "content" in chunk:
        content = chunk["content"]
        if content in seen:
            return
        seen.add(content)
        console.print(f"[{style}]\\[{node}][/{style}] {escape(content)}")


if __name__ == "__main__":
    cli()
