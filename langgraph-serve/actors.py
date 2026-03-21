"""Shared Ray actor base types — generic building blocks for any workflow.

Each actor instance runs in its own Ray process. Workflow-specific actors
should be defined in their own workflow package (e.g. workflows/service_debugger/actors.py).
"""

import logging

import ray
from langchain_core.messages import SystemMessage, ToolMessage


@ray.remote(num_cpus=0)
class SummarizerActor:
    """LLM agent without tools. Ephemeral — one per request."""

    def __init__(self, base_url: str, model: str, system_prompt: str):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("SummarizerActor")

        from langchain_ollama import ChatOllama

        self.llm = ChatOllama(base_url=base_url, model=model)
        self.system_prompt = system_prompt

    def call(self, messages: list):
        response = self.llm.invoke(
            [SystemMessage(content=self.system_prompt)] + messages
        )
        tokens = response.usage_metadata or {}
        self.logger.info("tokens=%s\n%s", tokens, response.content)
        return response


@ray.remote(num_cpus=0)
class ExecutorActor:
    """LLM agent with tools. Ephemeral — one per request."""

    def __init__(self, base_url: str, model: str, system_prompt: str, tools: list):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("ExecutorActor")

        from langchain_ollama import ChatOllama

        llm = ChatOllama(base_url=base_url, model=model)
        self.llm = llm.bind_tools(tools)
        self.system_prompt = system_prompt

    def call(self, messages: list):
        response = self.llm.invoke(
            [SystemMessage(content=self.system_prompt)] + messages
        )
        tokens = response.usage_metadata or {}
        if response.content:
            self.logger.info("tokens=%s\n%s", tokens, response.content)
        if response.tool_calls:
            calls = [{"name": tc["name"], "args": tc["args"]} for tc in response.tool_calls]
            self.logger.info("tool_calls=%s", calls)
        return response


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
            output = fn.invoke(tc["args"])
            self.logger.info("%s(%s) -> %s", tc["name"], tc["args"], output)
            results.append(ToolMessage(content=str(output), tool_call_id=tc["id"]))
        return results
