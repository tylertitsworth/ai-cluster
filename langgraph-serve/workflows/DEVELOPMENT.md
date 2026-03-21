# Workflow Development Guide

This document explains how to write workflows that work correctly with the
LangGraph RayService and its CLI.

## Architecture Overview

```
cli.py  -->  POST /stream  -->  workflow stream()  -->  LangGraph astream()
                                                           |
                                                     Ray actors (ephemeral)
```

A workflow is a single Python file in `workflows/` that defines two async
functions and gets registered in `workflows/__init__.py`. The service handles
HTTP, memory, and lifecycle. The CLI handles presentation.

## Streaming Contract

The CLI expects a specific SSE event format. Every workflow's `stream()`
function must yield **only** dicts with one of two shapes:

```python
# Agent produced text
{"node": "node_name", "content": "The answer is 42."}

# Agent requested tool calls
{"node": "node_name", "tool_calls": [{"name": "tool_name", "args": {...}}]}
```

### What to yield

| Message type | Yield it? | Why |
|---|---|---|
| `AIMessage` with `content` | Yes | This is the agent's spoken output. |
| `AIMessage` with `tool_calls` | Yes | Shows what tool the agent is calling. |
| `HumanMessage` | No | User input — the CLI already has it. |
| `ToolMessage` | No | Raw tool output — the executor will summarize it in its final response. |

### Filtering pattern

Use this pattern in every `stream()` function to keep the output clean:

```python
from langchain_core.messages import AIMessage

async for chunk in compiled.astream(inputs, config, stream_mode="updates"):
    for node_name, update in chunk.items():
        for msg in update.get("messages", []):
            if not isinstance(msg, AIMessage):
                continue
            if msg.tool_calls:
                yield {
                    "node": node_name,
                    "tool_calls": [
                        {"name": tc["name"], "args": tc["args"]}
                        for tc in msg.tool_calls
                    ],
                }
            elif msg.content:
                yield {"node": node_name, "content": msg.content}
```

The CLI additionally deduplicates events (same content won't appear twice) and
hides `tools` node output, so workflows don't need to handle that.

## File Structure

Each workflow is a single file in `workflows/`:

```
workflows/
  __init__.py      # Registry — imports and maps workflow names
  example.py       # The example workflow
  my_workflow.py   # Your new workflow
```

## Required Exports

Every workflow file must export two async functions:

### `run(base_url, model, query, thread_id, checkpointer) -> str`

Synchronous execution. Returns the final response string. Used by
`POST /invoke`.

### `stream(base_url, model, query, thread_id, checkpointer) -> AsyncGenerator`

Streaming execution. Yields dicts matching the contract above. Used by
`POST /stream` and consumed by the CLI.

## Ephemeral Actor Pattern

Actors are created fresh for each request and killed afterwards. This gives
full isolation between requests. Follow this pattern:

```python
import ray
from actors import SummarizerActor, ExecutorActor, ToolActor

async def run(base_url, model, query, thread_id, checkpointer):
    actor_a = SomeActor.remote(base_url, model, PROMPT)
    actor_b = AnotherActor.remote(base_url, model, PROMPT, TOOLS)
    tool_actor = ToolActor.remote(TOOLS)

    try:
        compiled, ... = _build_graph(actor_a, actor_b, tool_actor, checkpointer)
        result = await compiled.ainvoke(
            {"messages": [HumanMessage(content=query)]},
            {"configurable": {"thread_id": thread_id}},
        )
        return result["messages"][-1].content
    finally:
        ray.kill(actor_a)
        ray.kill(actor_b)
        ray.kill(tool_actor)
```

The `finally` block is critical — without it, actors accumulate and leak
resources.

## Using Subgraphs

Break complex workflows into reusable subgraphs. Each subgraph is a compiled
`StateGraph` that can be added as a node in a parent graph:

```python
def build_my_subgraph(actor):
    async def my_node(state: MessagesState):
        response = await actor.call.remote(state["messages"])
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("my_node", my_node)
    graph.add_edge(START, "my_node")
    graph.add_edge("my_node", END)
    return graph.compile()

# In the parent graph:
parent = StateGraph(MessagesState)
parent.add_node("my_step", build_my_subgraph(actor))
```

Existing reusable subgraphs in `example.py`:
- `build_summarizer_subgraph(actor)` — distills user input
- `build_executor_subgraph(actor, tool_actor)` — ReAct tool-calling loop

Import and compose them in new workflows freely.

## Registering a Workflow

Add your workflow to `workflows/__init__.py`:

```python
from workflows import example, my_workflow

WORKFLOWS = {
    "example": {"run": example.run, "stream": example.stream},
    "my-workflow": {"run": my_workflow.run, "stream": my_workflow.stream},
}
```

The key becomes the `--workflow` / `-w` flag in the CLI and the `workflow`
field in the API request body.

## Memory / Thread IDs

The checkpointer and thread_id are passed into your workflow by the service.
Use them when compiling the graph:

```python
compiled = graph.compile(checkpointer=checkpointer)
config = {"configurable": {"thread_id": thread_id}}
result = await compiled.ainvoke(inputs, config)
```

Same thread_id across requests = continued conversation. The CLI defaults to
a session-stable thread ID so consecutive queries share context. Users can
pass `--no-cache` for a fresh thread or `--thread ID` for an explicit one.

## Adding New Actors

Define new actor classes in `actors.py`. Follow the conventions:

- Use `@ray.remote(num_cpus=0)` since actors are I/O-bound (waiting on Ollama)
- Call `logging.basicConfig(level=logging.INFO)` in `__init__`
- Name the logger after the class: `self.logger = logging.getLogger("MyActor")`
- Log token counts and outputs so they appear in the Ray dashboard

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

1. **Only AIMessage content and tool_calls are displayed** — tool results and
   human messages are hidden.
2. **Duplicate content is deduplicated** — if the same text appears twice
   (common with subgraphs), it shows once.
3. **Node names are shown as prefixes** — `[summarizer]`, `[executor]`, etc.
4. **Node-specific colors** — `summarizer` (cyan), `executor` (green),
   `tools` (yellow). Unknown nodes render in dim.

As long as your `stream()` yields the correct dict format, the CLI handles
the rest.
