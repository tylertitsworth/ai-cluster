"""Unified Ray actor for LLM inference via any OpenAI-compatible provider.

Created per workflow invocation, placed in a placement group for pod isolation.
Tool schemas are forwarded to the LLM's tools= parameter; actual tool execution
happens in the engine process because MCP sessions hold connection state that
cannot survive Ray serialization.
"""

import asyncio
import logging
import os

import openai
import ray

ACTOR_CPU = float(os.environ.get("ACTOR_CPU", "0.1"))

_MAX_RETRIES = 2
_RETRY_BACKOFF_S = 5
_TRANSIENT_ERRORS = (
    openai.RateLimitError,
    openai.APITimeoutError,
    openai.APIConnectionError,
)


@ray.remote(num_cpus=ACTOR_CPU)
class Agent:
    """Unified agent actor. Calls any OpenAI-compatible LLM provider.

    Created per workflow invocation, placed in a placement group for pod isolation.
    Tool schemas are passed for the LLM's tools= parameter, but actual tool
    execution happens in the engine process (not here) because MCP sessions
    hold connection state that can't survive Ray serialization.
    """

    def __init__(
        self,
        provider_config: dict,
        system_prompt: str,
        tool_schemas: list | None = None,
    ):
        """Initialise the actor.

        Args:
            provider_config: Dict with keys ``base_url``, ``api_key``, ``model``.
            system_prompt: System message prepended to every conversation.
            tool_schemas: Optional list of OpenAI tool-schema dicts passed as
                ``tools=`` on every LLM call.
        """
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.client = openai.AsyncOpenAI(
            base_url=provider_config["base_url"],
            api_key=provider_config["api_key"],
        )
        self.model = provider_config["model"]
        self.system_prompt = system_prompt
        self.tool_schemas = tool_schemas or None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_messages(self, messages: list[dict]) -> list[dict]:
        return [{"role": "system", "content": self.system_prompt}] + messages

    def _log_usage(self, usage) -> None:
        if usage:
            self.logger.info(
                "tokens: prompt=%d completion=%d total=%d",
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.total_tokens,
            )

    # ------------------------------------------------------------------
    # Non-streaming call
    # ------------------------------------------------------------------

    async def execute(self, messages: list[dict]) -> dict:
        """Call the LLM and return the full response message as a dict.

        Retries up to ``_MAX_RETRIES`` times on transient errors (rate limits,
        timeouts, connection failures). Returns an error dict instead of raising
        so the engine can surface the failure cleanly.
        """
        full_messages = self._build_messages(messages)
        tools_param = self.tool_schemas if self.tool_schemas else openai.NOT_GIVEN

        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = await self.client.chat.completions.create(
                    model=self.model,
                    messages=full_messages,
                    tools=tools_param,
                )
                msg = resp.choices[0].message
                self._log_usage(resp.usage)
                if msg.content:
                    self.logger.info("content: %.500s", msg.content)
                if msg.tool_calls:
                    self.logger.info(
                        "tool_calls: %s",
                        [tc.function.name for tc in msg.tool_calls],
                    )
                return msg.model_dump()

            except _TRANSIENT_ERRORS as e:
                if attempt < _MAX_RETRIES:
                    self.logger.warning(
                        "Transient error (attempt %d/%d), retrying in %ds: %s",
                        attempt + 1,
                        _MAX_RETRIES + 1,
                        _RETRY_BACKOFF_S,
                        e,
                    )
                    await asyncio.sleep(_RETRY_BACKOFF_S)
                else:
                    self.logger.error(
                        "LLM call failed after %d attempts: %s",
                        _MAX_RETRIES + 1,
                        e,
                    )
                    return {
                        "role": "assistant",
                        "content": (
                            f"ERROR: LLM call failed after {_MAX_RETRIES + 1}"
                            f" attempts: {e}"
                        ),
                        "tool_calls": None,
                    }

            except Exception as e:
                self.logger.error("Unexpected error in execute: %s", e)
                return {
                    "role": "assistant",
                    "content": f"ERROR: {e}",
                    "tool_calls": None,
                }

    # ------------------------------------------------------------------
    # Streaming call
    # ------------------------------------------------------------------

    async def stream_execute(self, messages: list[dict]):
        """Stream the LLM response, yielding deltas and a final complete message.

        Yields:
            ``{"type": "delta", "content": "<token>"}`` — content token chunks.
            ``{"type": "delta", "tool_calls": [...]}`` — partial tool-call state
                after each tool-call chunk arrives.
            ``{"type": "message", "role": "assistant", "content": ...,
               "tool_calls": ...}`` — the single final dict sent after the stream
                ends, containing the fully accumulated response.

        Retries on transient errors only when no content has been yielded yet
        (mid-stream retries would leave the consumer with an incomplete buffer).
        """
        full_messages = self._build_messages(messages)
        tools_param = self.tool_schemas if self.tool_schemas else openai.NOT_GIVEN

        for attempt in range(_MAX_RETRIES + 1):
            if attempt > 0:
                await asyncio.sleep(_RETRY_BACKOFF_S)

            content_acc = ""
            # index -> {id, type, function: {name, arguments}}
            tool_calls_acc: dict[int, dict] = {}
            yielded_anything = False

            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=full_messages,
                    tools=tools_param,
                    stream=True,
                )

                async for chunk in response:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta

                    if delta.content:
                        content_acc += delta.content
                        yielded_anything = True
                        yield {"type": "delta", "content": delta.content}

                    if delta.tool_calls:
                        for tc_chunk in delta.tool_calls:
                            idx = tc_chunk.index
                            if idx not in tool_calls_acc:
                                tool_calls_acc[idx] = {
                                    "id": tc_chunk.id or "",
                                    "type": "function",
                                    "function": {
                                        "name": (
                                            tc_chunk.function.name or ""
                                            if tc_chunk.function
                                            else ""
                                        ),
                                        "arguments": (
                                            tc_chunk.function.arguments or ""
                                            if tc_chunk.function
                                            else ""
                                        ),
                                    },
                                }
                            else:
                                if tc_chunk.id:
                                    tool_calls_acc[idx]["id"] = tc_chunk.id
                                if tc_chunk.function:
                                    if tc_chunk.function.name:
                                        tool_calls_acc[idx]["function"][
                                            "name"
                                        ] += tc_chunk.function.name
                                    if tc_chunk.function.arguments:
                                        tool_calls_acc[idx]["function"][
                                            "arguments"
                                        ] += tc_chunk.function.arguments

                        yielded_anything = True
                        yield {
                            "type": "delta",
                            "tool_calls": [
                                {"index": i, **tc}
                                for i, tc in sorted(tool_calls_acc.items())
                            ],
                        }

                # Build the complete accumulated tool_calls list (sorted by index).
                tool_calls_list: list[dict] = [
                    tool_calls_acc[i] for i in sorted(tool_calls_acc)
                ]

                if content_acc:
                    self.logger.info("content: %.500s", content_acc)
                if tool_calls_list:
                    self.logger.info(
                        "tool_calls: %s",
                        [tc["function"]["name"] for tc in tool_calls_list],
                    )

                yield {
                    "type": "message",
                    "role": "assistant",
                    "content": content_acc or None,
                    "tool_calls": tool_calls_list or None,
                }
                return  # success — exit retry loop

            except _TRANSIENT_ERRORS as e:
                if yielded_anything:
                    # Cannot restart cleanly once tokens have been sent downstream.
                    self.logger.error("Transient error mid-stream (no retry): %s", e)
                    yield {
                        "type": "message",
                        "role": "assistant",
                        "content": f"ERROR: stream interrupted: {e}",
                        "tool_calls": None,
                    }
                    return

                if attempt < _MAX_RETRIES:
                    self.logger.warning(
                        "Transient stream error (attempt %d/%d), retrying in %ds: %s",
                        attempt + 1,
                        _MAX_RETRIES + 1,
                        _RETRY_BACKOFF_S,
                        e,
                    )
                else:
                    self.logger.error(
                        "LLM stream failed after %d attempts: %s",
                        _MAX_RETRIES + 1,
                        e,
                    )
                    yield {
                        "type": "message",
                        "role": "assistant",
                        "content": (
                            f"ERROR: LLM stream failed after {_MAX_RETRIES + 1}"
                            f" attempts: {e}"
                        ),
                        "tool_calls": None,
                    }
                    return

            except Exception as e:
                self.logger.error("Unexpected error in stream_execute: %s", e)
                yield {
                    "type": "message",
                    "role": "assistant",
                    "content": f"ERROR: {e}",
                    "tool_calls": None,
                }
                return
