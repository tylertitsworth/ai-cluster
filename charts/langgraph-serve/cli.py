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

BASE_STYLES = {
    "error": "bold red",
    "info": "dim",
}
console = Console(theme=Theme(BASE_STYLES))

DEFAULT_URL = os.environ.get("LANGGRAPH_URL", "https://langgraph.tail79a5c8.ts.net/serve")


def _fetch_cli_meta(url: str) -> dict:
    """Fetch aggregated CLI metadata from the server's /workflows endpoint."""
    try:
        resp = httpx.get(f"{url}/workflows", verify=False, timeout=10)
        resp.raise_for_status()
        return resp.json().get("cli_meta", {})
    except httpx.HTTPError:
        return {}


def _build_render_config(cli_meta: dict) -> tuple[Console, set, set, dict]:
    """Build a themed Console and render config from workflow CLI metadata.

    Returns (console, known_nodes, hidden_nodes, prefix_styles).
    """
    styles = dict(BASE_STYLES)
    known = set()
    hidden = set()
    prefixes = {}

    for wf_meta in cli_meta.values():
        for node_name, color in wf_meta.get("nodes", {}).items():
            styles[node_name] = color
            known.add(node_name)
        hidden.update(wf_meta.get("hidden_nodes", []))
        prefixes.update(wf_meta.get("prefix_styles", {}))

    return Console(theme=Theme(styles)), known, hidden, prefixes


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
@click.option("--provider", "-p", default="ollama", type=click.Choice(["ollama", "openai"]), help="LLM provider")
@click.option("--model", "-m", default=None, help="Model name override (default: provider's default)")
@click.option("--param", "-P", multiple=True, help="Workflow param as key=value (e.g. -P key=value)")
@click.pass_context
def query(ctx, text, workflow, thread, no_cache, provider, model, param):
    """Send a query and stream the response."""
    url = ctx.obj["url"]
    if thread:
        thread_id = thread
    elif no_cache:
        thread_id = str(uuid.uuid4())
    else:
        thread_id = _session_thread_id()

    params = {}
    for p in param:
        if "=" not in p:
            console.print(f"[error]Invalid param '{p}', expected key=value[/error]")
            sys.exit(1)
        k, v = p.split("=", 1)
        try:
            v = int(v)
        except ValueError:
            try:
                v = float(v)
            except ValueError:
                pass
        params[k] = v

    info_parts = [f"thread: {thread_id}", f"provider: {provider}", f"model: {model or 'default'}"]
    if params:
        info_parts.append(f"params: {params}")
    console.print(f"[info]{' | '.join(info_parts)}[/info]")

    meta = _fetch_cli_meta(url)
    stream_console, known_nodes, hidden_nodes, prefix_styles = _build_render_config(meta)

    payload = {"workflow": workflow, "query": text, "thread_id": thread_id, "provider": provider, "params": params}
    if model:
        payload["model"] = model

    try:
        current_node = None
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
                event = json.loads(line[6:])
                current_node = _render_event(event, current_node, stream_console, known_nodes, hidden_nodes, prefix_styles)
            if current_node is not None:
                stream_console.print()
    except httpx.HTTPError as e:
        console.print(f"\n[error]Request failed: {e}[/error]")
        sys.exit(1)


def _render_event(
    event: dict,
    current_node: str | None,
    con: Console,
    known_nodes: set,
    hidden_nodes: set,
    prefix_styles: dict,
) -> str | None:
    """Render a streaming event. Returns the current node name for line continuity."""
    node = event.get("node", "unknown")

    if node in hidden_nodes:
        return current_node

    if node in known_nodes:
        style = node
    else:
        style = "info"
        for prefix, style_key in prefix_styles.items():
            if node.startswith(prefix):
                style = style_key
                break

    if "token" in event:
        if node != current_node:
            if current_node is not None:
                con.print()
            con.print(f"[{style}]\\[{node}][/{style}] ", end="")
            current_node = node
        con.print(escape(event["token"]), end="")
        return current_node

    if "tool_call" in event:
        if current_node is not None:
            con.print()
            current_node = None
        tc = event["tool_call"]
        con.print(
            f"[{style}]\\[{node}][/{style}] "
            f"calling [bold]{tc['name']}[/bold]({escape(str(tc['args']))})"
        )
        return None

    if "content" in event:
        if current_node is not None:
            con.print()
            current_node = None
        con.print(f"[{style}]\\[{node}][/{style}] {escape(event['content'])}")
        return None

    return current_node


if __name__ == "__main__":
    cli()
