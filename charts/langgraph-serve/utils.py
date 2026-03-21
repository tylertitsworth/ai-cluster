"""Shared utilities for LangGraph workflows on Ray Serve.

Provides:
- load_prompt: Load prompts from ConfigMap-mounted files with fallback defaults
- strip_think: Remove <think> blocks from LLM output
- make_streaming_node / make_blocking_node: Graph node factories
- retry_invoke / retry_stream: LLM call retry helpers
- make_actor: Dynamic Ray actor class factory
- run_workflow / stream_workflow: Workflow lifecycle helpers
"""

import logging
import os
import re
import time

import ray
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.config import get_stream_writer

# ---------------------------------------------------------------------------
# Prompt loading from ConfigMap volumes
# ---------------------------------------------------------------------------

PROMPTS_DIR = os.environ.get("PROMPTS_DIR", "/prompts")


def load_prompt(workflow: str, name: str, default: str = "") -> str:
    """Load a prompt from a ConfigMap-mounted file, falling back to default.

    Prompts are mounted at PROMPTS_DIR/<workflow>/<name>.txt by K8s ConfigMaps.
    For local dev without K8s, the default value is used.
    """
    path = os.path.join(PROMPTS_DIR, workflow, f"{name}.txt")
    try:
        with open(path) as f:
            return f.read().strip()
    except FileNotFoundError:
        return default


# ---------------------------------------------------------------------------
# Think-block filtering
# ---------------------------------------------------------------------------

THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_think(text: str) -> str:
    """Remove <think>...</think> blocks. Use for routing decisions on complete text."""
    return THINK_RE.sub("", text).strip()


# ---------------------------------------------------------------------------
# LLM retry helpers
# ---------------------------------------------------------------------------

MAX_RETRIES = 2
RETRY_BACKOFF_S = 5


def retry_invoke(llm, messages, logger, max_retries=MAX_RETRIES):
    """Invoke LLM with retry on transient failures."""
    for attempt in range(max_retries + 1):
        try:
            return llm.invoke(messages)
        except Exception as e:
            if attempt < max_retries:
                logger.warning(
                    "LLM call failed (attempt %d/%d), retrying in %ds: %s",
                    attempt + 1, max_retries + 1, RETRY_BACKOFF_S, e,
                )
                time.sleep(RETRY_BACKOFF_S)
            else:
                logger.error("LLM call failed after %d attempts: %s", max_retries + 1, e)
                return AIMessage(content=f"ERROR: LLM call failed after {max_retries + 1} attempts: {e}")


def retry_stream(llm, messages, logger, max_retries=MAX_RETRIES):
    """Stream LLM with retry on transient failures. Yields chunks or a single error AIMessage."""
    for attempt in range(max_retries + 1):
        try:
            yield from llm.stream(messages)
            return
        except Exception as e:
            if attempt < max_retries:
                logger.warning(
                    "LLM stream failed (attempt %d/%d), retrying in %ds: %s",
                    attempt + 1, max_retries + 1, RETRY_BACKOFF_S, e,
                )
                time.sleep(RETRY_BACKOFF_S)
            else:
                logger.error("LLM stream failed after %d attempts: %s", max_retries + 1, e)
                yield AIMessage(content=f"ERROR: LLM call failed after {max_retries + 1} attempts: {e}")


# ---------------------------------------------------------------------------
# Graph node factories
# ---------------------------------------------------------------------------

def make_streaming_node(actor, node_name):
    """Create a graph node that streams tokens from a Ray actor via StreamWriter.

    Filters <think> blocks across chunk boundaries. Catches Ray actor failures
    and returns an error AIMessage with STATUS: UNFIXABLE.
    """

    async def node_fn(state):
        writer = get_stream_writer()
        try:
            accumulated = None
            in_think = False
            for ref in actor.stream_call.remote(state["messages"]):
                chunk = await ref
                accumulated = chunk if accumulated is None else accumulated + chunk
                if chunk.content:
                    text = chunk.content
                    while text:
                        if in_think:
                            end_idx = text.find("</think>")
                            if end_idx != -1:
                                text = text[end_idx + 8:]
                                in_think = False
                            else:
                                break
                        else:
                            start_idx = text.find("<think>")
                            if start_idx != -1:
                                before = text[:start_idx]
                                if before:
                                    writer({"node": node_name, "token": before})
                                text = text[start_idx + 7:]
                                in_think = True
                            else:
                                writer({"node": node_name, "token": text})
                                break
            if accumulated and hasattr(accumulated, "tool_calls") and accumulated.tool_calls:
                for tc in accumulated.tool_calls:
                    writer({"node": node_name, "tool_call": {"name": tc["name"], "args": tc["args"]}})
            return {"messages": [accumulated]}
        except Exception as e:
            error_msg = f"Agent {node_name} failed: {e}. STATUS: UNFIXABLE"
            writer({"node": node_name, "error": str(e)})
            return {"messages": [AIMessage(content=error_msg)]}

    return node_fn


def make_blocking_node(actor, node_name=None):
    """Create a graph node that blocks until the actor completes.

    Catches Ray actor failures and returns an error AIMessage with STATUS: UNFIXABLE.
    """
    label = node_name or "unknown"

    async def node_fn(state):
        try:
            response = await actor.call.remote(state["messages"])
            return {"messages": [response]}
        except Exception as e:
            error_msg = f"Agent {label} failed: {e}. STATUS: UNFIXABLE"
            return {"messages": [AIMessage(content=error_msg)]}

    return node_fn


# ---------------------------------------------------------------------------
# Dynamic actor factory
# ---------------------------------------------------------------------------

ACTOR_CPU = 0.25


def make_actor(class_name, has_tools=False):
    """Create a named Ray actor class that appears as class_name in the dashboard.

    Each actor requests ACTOR_CPU (0.25) so the Ray autoscaler provisions
    workers when requests arrive. A worker with 1 CPU fits ~4 actors = 1 request.

    Args:
        class_name: Name shown in Ray dashboard
        has_tools: If True, constructor accepts (provider, model, system_prompt, tools).
                   If False, constructor accepts (provider, model, system_prompt).

    Returns:
        A @ray.remote class with call() and stream_call() methods.
    """
    if has_tools:
        class _ToolActor:
            def __init__(self, provider: str, model: str, system_prompt: str, tools: list):
                logging.basicConfig(level=logging.INFO)
                self.logger = logging.getLogger(class_name)
                from llm import create_llm
                llm = create_llm(provider, model)
                self.llm = llm.bind_tools(tools)
                self.system_prompt = system_prompt

            def _messages(self, messages):
                return [SystemMessage(content=self.system_prompt)] + messages

            def call(self, messages: list):
                response = retry_invoke(self.llm, self._messages(messages), self.logger)
                if response.content:
                    self.logger.info("tokens=%s\n%s", response.usage_metadata or {}, response.content)
                if hasattr(response, "tool_calls") and response.tool_calls:
                    calls = [{"name": tc["name"], "args": tc["args"]} for tc in response.tool_calls]
                    self.logger.info("tool_calls=%s", calls)
                return response

            def stream_call(self, messages: list):
                yield from retry_stream(self.llm, self._messages(messages), self.logger)

        _ToolActor.__name__ = class_name
        _ToolActor.__qualname__ = class_name
        return ray.remote(num_cpus=ACTOR_CPU)(_ToolActor)
    else:
        class _Agent:
            def __init__(self, provider: str, model: str, system_prompt: str):
                logging.basicConfig(level=logging.INFO)
                self.logger = logging.getLogger(class_name)
                from llm import create_llm
                self.llm = create_llm(provider, model)
                self.system_prompt = system_prompt

            def _messages(self, messages):
                return [SystemMessage(content=self.system_prompt)] + messages

            def call(self, messages: list):
                response = retry_invoke(self.llm, self._messages(messages), self.logger)
                self.logger.info("tokens=%s\n%s", response.usage_metadata or {}, response.content)
                return response

            def stream_call(self, messages: list):
                yield from retry_stream(self.llm, self._messages(messages), self.logger)

        _Agent.__name__ = class_name
        _Agent.__qualname__ = class_name
        return ray.remote(num_cpus=ACTOR_CPU)(_Agent)


# ---------------------------------------------------------------------------
# Workflow lifecycle helpers
# ---------------------------------------------------------------------------

async def run_workflow(build_fn, query, thread_id, checkpointer, **config_extra):
    """Standard workflow lifecycle: build graph, invoke, cleanup actors.

    Args:
        build_fn: Callable(checkpointer, streaming=False) -> (compiled_graph, actors_list)
        query: User query string
        thread_id: Conversation thread ID
        checkpointer: LangGraph checkpointer instance
        **config_extra: Extra config keys (e.g. recursion_limit)
    """
    compiled, actors = build_fn(checkpointer=checkpointer, streaming=False)
    config = {"configurable": {"thread_id": thread_id}, **config_extra}
    try:
        result = await compiled.ainvoke(
            {"messages": [HumanMessage(content=query)]}, config,
        )
        return result["messages"][-1].content
    finally:
        for actor in actors:
            ray.kill(actor)


async def stream_workflow(build_fn, query, thread_id, checkpointer, **config_extra):
    """Standard workflow lifecycle: build graph with streaming, yield custom events, cleanup.

    Args:
        build_fn: Callable(checkpointer, streaming=True) -> (compiled_graph, actors_list)
        query: User query string
        thread_id: Conversation thread ID
        checkpointer: LangGraph checkpointer instance
        **config_extra: Extra config keys (e.g. recursion_limit)
    """
    compiled, actors = build_fn(checkpointer=checkpointer, streaming=True)
    config = {"configurable": {"thread_id": thread_id}, **config_extra}
    try:
        async for event in compiled.astream(
            {"messages": [HumanMessage(content=query)]},
            config,
            stream_mode="custom",
        ):
            yield event
    finally:
        for actor in actors:
            ray.kill(actor)
