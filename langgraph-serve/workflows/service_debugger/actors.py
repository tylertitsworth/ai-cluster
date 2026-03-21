"""Service Debugger actors — workflow-specific Ray actor types."""

import logging

import ray
from langchain_core.messages import SystemMessage


@ray.remote(num_cpus=0)
class InvestigatorActor:
    """Read-only K8s investigation. Ephemeral — one per request."""

    def __init__(self, base_url: str, model: str, system_prompt: str, tools: list):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("InvestigatorActor")

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
class FixerActor:
    """Proposes K8s fix commands without executing them. Ephemeral — one per request."""

    def __init__(self, base_url: str, model: str, system_prompt: str):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("FixerActor")

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
class GuardrailsActor:
    """Evaluates proposed commands for safety. Ephemeral — one per request."""

    def __init__(self, base_url: str, model: str, system_prompt: str):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("GuardrailsActor")

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
class K8sExecutorActor:
    """Executes approved K8s commands via read-write MCP tools. Ephemeral — one per request."""

    def __init__(self, base_url: str, model: str, system_prompt: str, tools: list):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("K8sExecutorActor")

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
