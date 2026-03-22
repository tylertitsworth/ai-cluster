# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "rich", "click"]
# ///
"""CLI for the Agent Engine.

Usage:
  uv run cli.py run "Research quantum computing trends"
  uv run cli.py run -w report-writer -P num_sections=5 "AI in healthcare"
  uv run cli.py run -t my-session --provider openai "Continue our discussion"
  uv run cli.py run --race 3 --judge "accuracy and clarity" "Explain RLHF"
  uv run cli.py run --review --max-iterations 5 "Write a blog post about LLMs"
  uv run cli.py workflows
  uv run cli.py workflow report-writer
  uv run cli.py resume <thread-id>
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
    "success": "bold green",
    "warn": "bold yellow",
}
console = Console(theme=Theme(BASE_STYLES))

DEFAULT_URL = os.environ.get("AGENT_ENGINE_URL", "https://agent-engine.tail79a5c8.ts.net/serve")

AGENT_COLORS = [
    "bright_blue",
    "bright_magenta",
    "bright_green",
    "bright_cyan",
    "bright_yellow",
    "bright_red",
    "blue",
    "magenta",
    "green",
    "cyan",
]


def _agent_color(agent: str, color_map: dict) -> str:
    """Return a color for an agent, assigning one from the palette if new."""
    if agent not in color_map:
        color_map[agent] = AGENT_COLORS[len(color_map) % len(AGENT_COLORS)]
    return color_map[agent]


def _session_thread_id() -> str:
    """Stable thread ID derived from the current TTY session."""
    tty = os.environ.get("TTY") or (os.ttyname(sys.stdin.fileno()) if sys.stdin.isatty() else None)
    pid = os.getppid()
    seed = f"{tty}-{pid}" if tty else str(pid)
    return hashlib.sha256(seed.encode()).hexdigest()[:16]


def _parse_params(param_tuples: tuple) -> dict:
    """Parse key=value param tuples, coercing numeric values."""
    params = {}
    for p in param_tuples:
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
    return params


def _parse_agent_overrides(agent_tuples: tuple) -> dict[str, str]:
    """Parse -A flag values into flat agent_overrides for the engine.

    Formats:
      key=value          → global override {"key": "value"}
      agent:key=value    → agent-specific {"agent:key": "value"}
    """
    overrides: dict[str, str] = {}
    for a in agent_tuples:
        if "=" not in a:
            console.print(f"[error]Invalid agent override '{a}', expected [agent:]key=value[/error]")
            sys.exit(1)
        if ":" in a:
            agent_part, kv = a.split(":", 1)
            if "=" not in kv:
                console.print(f"[error]Invalid agent override '{a}', expected agent:key=value[/error]")
                sys.exit(1)
            k, v = kv.split("=", 1)
            overrides[f"{agent_part}:{k}"] = v
        else:
            k, v = a.split("=", 1)
            overrides[k] = v
    return overrides


def _render_event(event: dict, current_agent: str | None, con: Console, color_map: dict) -> str | None:
    """Render a streaming SSE event. Returns the current agent name for line continuity."""
    event_type = event.get("type", "")
    agent = event.get("agent", event.get("node", "unknown"))

    if event_type == "step_start":
        if current_agent is not None:
            con.print()
        color = _agent_color(agent, color_map)
        con.print(f"\n[{color}][{agent}][/{color}]")
        return agent

    if event_type == "token":
        if agent != current_agent:
            if current_agent is not None:
                con.print()
            color = _agent_color(agent, color_map)
            con.print(f"[{color}][{agent}][/{color}] ", end="")
            current_agent = agent
        con.print(escape(event.get("token", "")), end="")
        return current_agent

    if event_type == "researching":
        if current_agent is not None:
            con.print()
            current_agent = None
        queries = event.get("queries", [])
        con.print(f"  [dim]→ researching: {' | '.join(queries)}[/dim]")
        return None

    if event_type == "content":
        if current_agent is not None:
            con.print()
            current_agent = None
        color = _agent_color(agent, color_map)
        con.print(f"[{color}][{agent}][/{color}] {escape(event.get('content', ''))}")
        return None

    if event_type == "route":
        if current_agent is not None:
            con.print()
            current_agent = None
        matched = event.get("matched", "")
        next_node = event.get("next", "")
        con.print(f"  [dim]↳ route: {matched} → {next_node}[/dim]")
        return None

    if event_type == "loop_iteration":
        if current_agent is not None:
            con.print()
            current_agent = None
        iteration = event.get("iteration", "?")
        total = event.get("max", "?")
        con.print(f"  [dim]↳ loop: iteration {iteration}/{total}[/dim]")
        return None

    if event_type == "step_end":
        return current_agent

    if event_type == "error":
        if current_agent is not None:
            con.print()
            current_agent = None
        con.print(f"  [error]✗ error: {escape(event.get('message', str(event)))}[/error]")
        return None

    if event_type == "complete":
        if current_agent is not None:
            con.print()
            current_agent = None
        result = event.get("result", "")
        if result:
            color = _agent_color(agent, color_map)
            con.print(f"\n[{color}][result][/{color}] {escape(result)}")
        return None

    return current_agent


def _stream_sse(url: str, endpoint: str, payload: dict) -> None:
    """POST to an SSE endpoint and render events."""
    color_map: dict[str, str] = {}
    current_agent = None
    try:
        with httpx.stream(
            "POST",
            f"{url}{endpoint}",
            json=payload,
            verify=False,
            timeout=httpx.Timeout(connect=10, read=300, write=10, pool=10),
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                event = json.loads(data)
                current_agent = _render_event(event, current_agent, console, color_map)
        if current_agent is not None:
            console.print()
    except httpx.HTTPStatusError as e:
        console.print(f"\n[error]Request failed ({e.response.status_code}): {e.response.text}[/error]")
        sys.exit(1)
    except httpx.HTTPError as e:
        console.print(f"\n[error]Request failed: {e}[/error]")
        sys.exit(1)


@click.group()
@click.option("--url", default=DEFAULT_URL, envvar="AGENT_ENGINE_URL", help="Service base URL")
@click.pass_context
def cli(ctx, url):
    ctx.ensure_object(dict)
    ctx.obj["url"] = url.rstrip("/")


@cli.command()
@click.argument("query")
@click.option("--workflow", "-w", "workflow_name", default="example", show_default=True, help="Pre-registered workflow name")
@click.option("--thread", "-t", default=None, help="Thread ID for conversation memory")
@click.option("--no-cache", is_flag=True, help="Use a fresh random thread ID")
@click.option("--provider", default=None, help="LLM provider override for all agents")
@click.option("--model", default=None, help="Model override for all agents")
@click.option("--param", "-P", multiple=True, metavar="KEY=VALUE", help="Workflow parameter (repeatable)")
@click.option("--agent", "-A", multiple=True, metavar="[AGENT:]KEY=VALUE", help="Agent config override (repeatable)")
@click.option("--race", "-r", default=None, type=int, metavar="N", help="Run N copies in parallel and judge results")
@click.option("--review", is_flag=True, help="Wrap workflow in a review loop")
@click.option("--ralph", default=None, type=int, metavar="N", help="Task-list progression (max N tasks)")
@click.option("--judge", default=None, metavar="CRITERIA", help="Judging criteria for meta-operators")
@click.option("--max-iterations", default=3, show_default=True, type=int, help="Max iterations for review/ralph")
@click.pass_context
def run(ctx, query, workflow_name, thread, no_cache, provider, model, param, agent, race, review, ralph, judge, max_iterations):
    """Send a query and stream the response."""
    url = ctx.obj["url"]

    if thread:
        thread_id = thread
    elif no_cache:
        thread_id = str(uuid.uuid4())
    else:
        thread_id = _session_thread_id()

    params = _parse_params(param)
    agent_overrides = _parse_agent_overrides(agent)
    if provider:
        agent_overrides["provider"] = provider
    if model:
        agent_overrides["model"] = model

    operators = []
    if race:
        operators.append({"type": "race", "count": race})
    if review:
        operators.append({"type": "review", "max": max_iterations})
    if ralph:
        operators.append({"type": "ralph", "max": ralph})
    if judge:
        for op in operators:
            op["judge_criteria"] = judge

    info_parts = [f"thread: {thread_id}", f"workflow: {workflow_name}"]
    if provider:
        info_parts.append(f"provider: {provider}")
    if model:
        info_parts.append(f"model: {model}")
    if params:
        info_parts.append(f"params: {params}")
    if operators:
        info_parts.append(f"operators: {[o['type'] for o in operators]}")
    console.print(f"[info]{' | '.join(info_parts)}[/info]")

    payload: dict = {
        "workflow": workflow_name,
        "query": query,
        "thread_id": thread_id,
    }
    if params:
        payload["params"] = params
    if agent_overrides:
        payload["agent_overrides"] = agent_overrides
    if operators:
        payload["operators"] = operators

    _stream_sse(url, "/stream", payload)


@cli.command()
@click.pass_context
def workflows(ctx):
    """List available workflows with their parameters."""
    url = ctx.obj["url"]
    try:
        resp = httpx.get(f"{url}/workflows", verify=False, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as e:
        console.print(f"[error]Failed to list workflows: {e}[/error]")
        sys.exit(1)

    wf_map = data.get("workflows", {})
    if not wf_map:
        console.print("[info]No workflows registered.[/info]")
        return

    console.print("\n[bold]Available workflows:[/bold]")
    for name, details in wf_map.items():
        description = details.get("description", "")
        tier = details.get("tier", "")
        wf_params = details.get("params", {})

        title = f"  [bold]{name}[/bold]"
        if description:
            title += f" — {description}"
        if tier:
            title += f" [dim][tier: {tier}][/dim]"
        console.print(title)

        if wf_params:
            for param_name, param_info in wf_params.items():
                if isinstance(param_info, dict):
                    ptype = param_info.get("type", "")
                    pdefault = param_info.get("default", "")
                    pdesc = param_info.get("description", "")
                    parts = [f"    [dim]{param_name:<14}{ptype:<10}"]
                    if pdefault != "":
                        parts.append(f"default={pdefault:<6}")
                    if pdesc:
                        parts.append(f"  {pdesc}")
                    console.print("".join(parts) + "[/dim]")
                else:
                    console.print(f"    [dim]{param_name}: {param_info}[/dim]")
        else:
            console.print("    [dim]params: (none)[/dim]")
        console.print()


@cli.command(name="workflow")
@click.argument("name")
@click.pass_context
def workflow_detail(ctx, name):
    """Show detailed info about a workflow."""
    url = ctx.obj["url"]
    try:
        resp = httpx.get(f"{url}/workflows/{name}", verify=False, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            console.print(f"[error]Workflow '{name}' not found.[/error]")
        else:
            console.print(f"[error]Failed to get workflow: {e}[/error]")
        sys.exit(1)
    except httpx.HTTPError as e:
        console.print(f"[error]Failed to get workflow: {e}[/error]")
        sys.exit(1)

    wf_name = data.get("name", name)
    description = data.get("description", "")
    tier = data.get("tier", "")
    agents = data.get("agents", [])

    title = f"\n[bold]{wf_name}[/bold]"
    if description:
        title += f" — {description}"
    console.print(title)

    if tier:
        console.print(f"  [dim]tier: {tier}[/dim]")

    if agents:
        console.print("  [dim]agents:[/dim]")
        if isinstance(agents, dict):
            for ag_name, ag_info in agents.items():
                ag_provider = ag_info.get("provider", "") if isinstance(ag_info, dict) else ""
                ag_tools = ag_info.get("tools", []) if isinstance(ag_info, dict) else []
                line = f"    [dim]{ag_name:<16}{ag_provider}"
                if ag_tools:
                    line += f"  tools: [{', '.join(ag_tools)}]"
                console.print(line + "[/dim]")
        else:
            for ag in agents:
                console.print(f"    [dim]{ag}[/dim]")


@cli.command()
@click.argument("thread_id")
@click.pass_context
def resume(ctx, thread_id):
    """Resume a checkpointed workflow thread."""
    url = ctx.obj["url"]

    console.print(f"[info]Resuming thread: {thread_id}[/info]")

    _stream_sse(url, "/resume", {"thread_id": thread_id})


if __name__ == "__main__":
    cli()
