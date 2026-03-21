"""Shared Ray actor types.

LLM-based actors are created via utils.make_actor(). This file only contains
ToolActor which has a unique interface (no LLM, executes tool calls directly).
"""

import logging

import ray
from langchain_core.messages import ToolMessage


@ray.remote(num_cpus=0)
class ToolActor:
    """Executes tool calls in a Ray actor. Ephemeral — one per request.

    Only for tools that can survive Ray serialization (plain Python functions).
    For MCP tools, use langgraph.prebuilt.ToolNode instead.
    """

    def __init__(self, tools: list):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("ToolActor")
        self.tools_by_name = {t.name: t for t in tools}

    def call(self, tool_calls: list) -> list:
        results = []
        for tc in tool_calls:
            fn = self.tools_by_name.get(tc["name"])
            if fn is None:
                self.logger.warning("unknown tool '%s'", tc["name"])
                results.append(
                    ToolMessage(
                        content=f"Error: unknown tool '{tc['name']}'",
                        tool_call_id=tc["id"],
                    )
                )
                continue
            try:
                output = fn.invoke(tc["args"])
            except Exception as e:
                self.logger.error("tool '%s' raised: %s", tc["name"], e)
                results.append(
                    ToolMessage(
                        content=f"Error: tool '{tc['name']}' failed: {e}",
                        tool_call_id=tc["id"],
                    )
                )
                continue
            self.logger.info("%s(%s) -> %s", tc["name"], tc["args"], output)
            results.append(ToolMessage(content=str(output), tool_call_id=tc["id"]))
        return results
