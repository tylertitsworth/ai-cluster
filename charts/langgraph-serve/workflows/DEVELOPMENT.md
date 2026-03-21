# Workflow Development Guide

This document explains how to write workflows for the LangGraph RayService.

## Architecture Overview

```
cli.py  -->  POST /stream  -->  workflow stream()  -->  LangGraph astream()
                                                           |
                                                     Ray actors (ephemeral)
```

A workflow is a Python file or package in `workflows/` that defines two async
functions and gets registered in `workflows/__init__.py`. The service handles
HTTP, memory, and lifecycle. The CLI handles presentation.

## Shared Utilities (`utils.py`)

The `utils.py` module provides everything you need to build a workflow:

| Utility | Purpose |
|---|---|
| `make_actor(name, has_tools=False)` | Create a named Ray actor class for the dashboard |
| `make_streaming_node(actor, node_name)` | Graph node that streams tokens via StreamWriter |
| `make_blocking_node(actor, node_name)` | Graph node that blocks until actor completes |
| `run_workflow(build_fn, query, thread_id, checkpointer)` | Standard invoke lifecycle |
| `stream_workflow(build_fn, query, thread_id, checkpointer)` | Standard streaming lifecycle |
| `strip_think(text)` | Remove `<think>` blocks from LLM output |
| `retry_invoke(llm, messages, logger)` | LLM invoke with retry on transient failures |
| `retry_stream(llm, messages, logger)` | LLM stream with retry on transient failures |

## Streaming Contract

The CLI expects SSE events with one of these shapes:

```python
# Agent producing text tokens (streamed incrementally)
{"node": "node_name", "token": "partial text"}

# Agent requesting a tool call
{"node": "node_name", "tool_call": {"name": "tool_name", "args": {...}}}

# Complete content block (used by /invoke path)
{"node": "node_name", "content": "The full answer."}

# Error from a failed agent
{"node": "node_name", "error": "error message"}
```

### What the streaming node factories handle automatically

When you use `make_streaming_node()` from utils, it:
- Consumes the Ray actor's `stream_call()` generator
- Filters `<think>` blocks across chunk boundaries
- Emits `token` and `tool_call` events via StreamWriter
- Catches Ray actor failures and emits an error event

You don't need to implement any of this yourself.

## File Structure

Each workflow is a file or package in `workflows/`:

```
workflows/
  __init__.py           # Registry
  DEVELOPMENT.md        # This file
  example.py            # Simple workflow (single file)
  service_debugger/     # Complex workflow (package)
    __init__.py         # run() and stream()
    graph.py            # Graph topology and routing
    prompts.py          # System prompts
    mcp.py              # External tool loading
    README.md           # Workflow documentation
```

## Required Exports

Every workflow must export two async functions:

### `run(provider, model, query, thread_id, checkpointer) -> str`

Synchronous execution. Returns the final response string. Used by
`POST /invoke`.

### `stream(provider, model, query, thread_id, checkpointer) -> AsyncGenerator`

Streaming execution. Yields event dicts. Used by `POST /stream` and the CLI.

## Writing a Workflow: Minimal Example

```python
from actors import ToolActor
from langgraph.graph import END, START, MessagesState, StateGraph
from tools import TOOLS
from utils import make_actor, make_blocking_node, make_streaming_node, run_workflow, stream_workflow

MyAgent = make_actor("MyAgent", has_tools=True)

MY_PROMPT = "You are a helpful assistant."

def _build(provider, model, checkpointer=None, streaming=False):
    agent = MyAgent.remote(provider, model, MY_PROMPT, TOOLS)
    tool_actor = ToolActor.remote(TOOLS)

    make = make_streaming_node if streaming else make_blocking_node
    agent_node = make(agent, "agent")

    async def tools(state: MessagesState):
        results = await tool_actor.call.remote(state["messages"][-1].tool_calls)
        return {"messages": results}

    def should_continue(state: MessagesState):
        if state["messages"][-1].tool_calls:
            return "tools"
        return END

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, ["tools", END])
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=checkpointer), [agent, tool_actor]

async def run(provider, model, query, thread_id, checkpointer):
    return await run_workflow(
        lambda **kw: _build(provider, model, **kw),
        query, thread_id, checkpointer,
    )

async def stream(provider, model, query, thread_id, checkpointer):
    async for event in stream_workflow(
        lambda **kw: _build(provider, model, **kw),
        query, thread_id, checkpointer,
    ):
        yield event
```

## Registering a Workflow

Add to `workflows/__init__.py`:

```python
from workflows import my_workflow

WORKFLOWS = {
    "my-workflow": {"run": my_workflow.run, "stream": my_workflow.stream},
}
```

## Creating Actors

Use `make_actor()` from utils instead of writing actor classes:

```python
from utils import make_actor

# Agent without tools (like a summarizer, evaluator, etc.)
MyAgent = make_actor("MyAgent")
actor = MyAgent.remote(provider, model, system_prompt)

# Agent with tools (like an executor, investigator, etc.)
MyToolAgent = make_actor("MyToolAgent", has_tools=True)
actor = MyToolAgent.remote(provider, model, system_prompt, tools)
```

Each `make_actor()` call creates a distinct Ray actor class that shows up
with the given name in the Ray dashboard. Actors have `call()` (blocking)
and `stream_call()` (generator) methods with built-in retry logic.

## Memory / Thread IDs

The checkpointer and thread_id are passed into your workflow by the service.
Use them when compiling the graph via the `build_fn` pattern:

```python
def _build(provider, model, checkpointer=None, streaming=False):
    # ... create actors and graph ...
    return graph.compile(checkpointer=checkpointer), actors
```

`run_workflow` and `stream_workflow` pass `checkpointer` and `streaming`
to your build function automatically.

## Adding New Tools

Define tools in `tools.py` with the `@tool` decorator and append to `TOOLS`:

```python
from langchain_core.tools import tool

@tool
def my_tool(arg: str) -> str:
    """Description shown to the LLM."""
    return do_something(arg)

TOOLS = [get_current_time, calculate, my_tool]
```

## CLI Presentation Rules

The CLI applies these rules to all workflows uniformly:

1. Only `token`, `tool_call`, and `content` events are displayed.
   `error` events are shown in red.
2. Duplicate content is deduplicated.
3. Node names are shown as colored prefixes.
4. Tool output nodes (`tools`, `investigate_tools`, `execute_tools`) are hidden.
