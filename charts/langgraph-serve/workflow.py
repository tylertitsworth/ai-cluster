"""Base class for LangGraph workflows on Ray Serve.

Subclass Workflow, implement build(), and export an instance as `workflow`
in your package's __init__.py. The registry auto-discovers it.
"""

import logging
import time

import ray
from langchain_core.messages import HumanMessage
from langgraph.errors import GraphRecursionError

from utils import load_prompts

_TOOLS_CACHE_TTL = 300

_RECURSION_MSG = (
    "The workflow reached its maximum number of steps without completing. "
    "This usually means the issue requires more investigation cycles than "
    "allowed. Please try again with a more specific query, or check the "
    "service manually."
)


class Workflow:
    """Base class for LangGraph workflows on Ray Serve.

    Subclasses must define:
        name:      Workflow identifier (used for prompt lookup and registration).
        cli_meta:  Dict with 'nodes', 'hidden_nodes', 'prefix_styles' for CLI rendering.
        build():   Wire the graph. Return (compiled_graph, actors_to_cleanup).

    Optionally override:
        get_tools():       Load MCP or other external tools (cached with TTL).
        prompts():         Custom prompt loading (default: auto-discover from .txt).
        recursion_limit:   Max LangGraph recursion steps (default 50).
    """

    name: str
    cli_meta: dict = {"nodes": {}, "hidden_nodes": [], "prefix_styles": {}}
    recursion_limit: int = 50

    _tools_cache = None
    _tools_ts: float = 0.0

    def prompts(self) -> dict[str, str]:
        """Load prompts by convention from .txt files."""
        return load_prompts(self.name)

    async def get_tools(self) -> dict:
        """Override to load MCP/external tools. Result is cached with TTL."""
        return {}

    async def _cached_tools(self) -> dict:
        now = time.monotonic()
        if self._tools_cache is None or now - self._tools_ts > _TOOLS_CACHE_TTL:
            try:
                self._tools_cache = await self.get_tools()
                self._tools_ts = now
            except Exception:
                self._tools_cache = None
                logging.getLogger(self.name).exception("Failed to load tools")
                raise
        return self._tools_cache

    def build(self, provider, model, prompts, tools, checkpointer=None, streaming=False, **kwargs):
        """Wire the graph. Return (compiled_graph, actors_to_cleanup)."""
        raise NotImplementedError

    async def run(self, provider: str, model: str, query: str, thread_id: str, checkpointer, **kwargs) -> str:
        tools = await self._cached_tools()
        prompts = self.prompts()
        compiled, actors = self.build(
            provider, model, prompts, tools,
            checkpointer=checkpointer, streaming=False, **kwargs,
        )
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": self.recursion_limit}
        try:
            result = await compiled.ainvoke(
                {"messages": [HumanMessage(content=query)]}, config,
            )
            return result["messages"][-1].content
        except GraphRecursionError:
            logging.getLogger(self.name).warning(
                "GraphRecursionError for thread %s — returning graceful message", thread_id,
            )
            return _RECURSION_MSG
        finally:
            for actor in actors:
                ray.kill(actor)

    async def stream(self, provider: str, model: str, query: str, thread_id: str, checkpointer, **kwargs):
        tools = await self._cached_tools()
        prompts = self.prompts()

        compiled, actors = self.build(
            provider, model, prompts, tools,
            checkpointer=checkpointer, streaming=True, **kwargs,
        )
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": self.recursion_limit}
        try:
            async for event in compiled.astream(
                {"messages": [HumanMessage(content=query)]},
                config,
                stream_mode="custom",
            ):
                yield event
        except GraphRecursionError:
            logging.getLogger(self.name).warning(
                "GraphRecursionError for thread %s — yielding graceful message", thread_id,
            )
            yield {"node": "system", "error": _RECURSION_MSG}
        finally:
            for actor in actors:
                ray.kill(actor)
