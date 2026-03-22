"""MCP tool connection management and execution.

Connects to MCP servers declared in a workflow's ``tools:`` section, converts
their tool definitions to the OpenAI function-calling schema, and routes tool
calls from the LLM back to the correct session.

Typical workflow YAML shape::

    tools:
      web_search:
        type:      mcp
        url:       http://mcp-web-search:8000/mcp
        transport: streamable_http
      code_exec:
        type:      mcp
        url:       http://mcp-code:8000/mcp
        transport: streamable_http

Usage::

    manager = ToolManager(workflow_config["tools"])
    await manager.connect_all()

    schemas = manager.get_schemas()          # pass to Agent as tool_schemas
    results = await manager.execute(calls)   # after LLM returns tool_calls

    await manager.close()
"""

import contextlib
import json
import logging
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema conversion
# ---------------------------------------------------------------------------


def mcp_tools_to_openai_schema(mcp_tools: list) -> list[dict]:
    """Convert a list of MCP tool objects to OpenAI function-calling dicts.

    Each MCP tool becomes::

        {
            "type": "function",
            "function": {
                "name":        "<tool name>",
                "description": "<tool description>",
                "parameters":  <inputSchema or empty object schema>,
            }
        }
    """
    schemas: list[dict] = []
    for tool in mcp_tools:
        parameters = tool.inputSchema if tool.inputSchema else {
            "type": "object",
            "properties": {},
        }
        schemas.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": parameters,
            },
        })
    return schemas


# ---------------------------------------------------------------------------
# Tool call execution
# ---------------------------------------------------------------------------


async def execute_tool_call(
    tool_call: dict,
    mcp_sessions: dict[str, ClientSession],
) -> dict:
    """Execute a single OpenAI-format tool call and return a tool result message.

    Args:
        tool_call: OpenAI tool call dict::

            {
                "id": "call_abc123",
                "type": "function",
                "function": {"name": "tool_name", "arguments": "{...}"}
            }

        mcp_sessions: Mapping from tool-function name → open
            :class:`mcp.ClientSession`.

    Returns:
        OpenAI tool-result message dict::

            {"role": "tool", "tool_call_id": "...", "content": "..."}

        On error the content describes the failure; the function does **not**
        raise so the engine can continue processing remaining tool calls.
    """
    call_id: str = tool_call.get("id", "")
    fn: dict = tool_call.get("function", {})
    name: str = fn.get("name", "")
    raw_args: str = fn.get("arguments", "{}")

    try:
        arguments: dict[str, Any] = json.loads(raw_args) if raw_args else {}
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse tool call arguments for '%s': %s", name, exc)
        arguments = {}

    session = mcp_sessions.get(name)
    if session is None:
        available = list(mcp_sessions.keys())
        error_msg = (
            f"Tool '{name}' not found. "
            f"Available tools: {available}"
        )
        logger.error(error_msg)
        return {"role": "tool", "tool_call_id": call_id, "content": error_msg}

    try:
        result = await session.call_tool(name, arguments)
        # result.content is a list of content blocks; join text parts
        content_parts: list[str] = []
        for block in result.content:
            if hasattr(block, "text"):
                content_parts.append(block.text)
            else:
                content_parts.append(str(block))
        content = "\n".join(content_parts)

        logger.debug("Tool '%s' returned %d content block(s)", name, len(result.content))
        return {"role": "tool", "tool_call_id": call_id, "content": content}

    except Exception as exc:
        error_msg = f"Tool '{name}' raised an error: {exc}"
        logger.error(error_msg)
        return {"role": "tool", "tool_call_id": call_id, "content": error_msg}


async def execute_tool_calls(
    tool_calls: list[dict],
    mcp_sessions: dict[str, ClientSession],
) -> list[dict]:
    """Execute multiple tool calls sequentially and return all result messages.

    Args:
        tool_calls: List of OpenAI tool call dicts (see :func:`execute_tool_call`).
        mcp_sessions: Mapping from tool-function name → open session.

    Returns:
        List of OpenAI tool-result message dicts, one per input tool call.
    """
    results: list[dict] = []
    for tc in tool_calls:
        result = await execute_tool_call(tc, mcp_sessions)
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# ToolManager
# ---------------------------------------------------------------------------


class ToolManager:
    """Manages MCP connections for all tools declared in a workflow.

    Typical lifecycle::

        manager = ToolManager(workflow_config["tools"])
        await manager.connect_all()
        try:
            schemas = manager.get_schemas()
            results = await manager.execute(tool_calls)
        finally:
            await manager.close()

    Args:
        tools_config: The ``tools:`` section of a workflow config — a dict
            mapping tool names to their config dicts (``type``, ``url``,
            ``transport``).
    """

    def __init__(self, tools_config: dict):
        self._config: dict = tools_config or {}
        self._tool_to_session: dict[str, ClientSession] = {}
        self._schemas: list[dict] = []
        self._group_to_fn_names: dict[str, set[str]] = {}
        self._exit_stack: contextlib.AsyncExitStack | None = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect_all(self) -> None:
        """Connect to every MCP server in the workflow's ``tools:`` section.

        Non-MCP tool types are skipped with a warning.  Individual connection
        failures are logged but do not abort the remaining connections.
        """
        self._exit_stack = contextlib.AsyncExitStack()
        await self._exit_stack.__aenter__()

        for tool_name, tool_config in self._config.items():
            if tool_config.get("type") != "mcp":
                logger.warning(
                    "Tool '%s' has unsupported type '%s', skipping",
                    tool_name,
                    tool_config.get("type"),
                )
                continue

            try:
                session, schemas = await self._connect_one(tool_config)
                fn_names: set[str] = set()
                for schema in schemas:
                    fn_name: str = schema["function"]["name"]
                    self._tool_to_session[fn_name] = session
                    fn_names.add(fn_name)
                self._schemas.extend(schemas)
                self._group_to_fn_names[tool_name] = fn_names
                logger.info(
                    "Tool '%s' connected: %d function(s)",
                    tool_name,
                    len(schemas),
                )
            except Exception:
                logger.exception("Failed to connect to MCP tool '%s'", tool_name)

    async def _connect_one(
        self, tool_config: dict
    ) -> tuple[ClientSession, list[dict]]:
        """Open a single MCP connection using the manager's exit stack."""
        url = tool_config["url"]
        transport = tool_config.get("transport", "streamable_http")
        logger.info("Connecting to MCP server: url=%s transport=%s", url, transport)

        read, write, _ = await self._exit_stack.enter_async_context(  # type: ignore[union-attr]
            streamablehttp_client(url)
        )
        session = await self._exit_stack.enter_async_context(  # type: ignore[union-attr]
            ClientSession(read, write)
        )
        await session.initialize()

        tools_result = await session.list_tools()
        schemas = mcp_tools_to_openai_schema(tools_result.tools)

        logger.info(
            "Connected to MCP at %s: %d tool(s) — %s",
            url,
            len(schemas),
            [s["function"]["name"] for s in schemas],
        )
        return session, schemas

    async def close(self) -> None:
        """Close all MCP connections and release resources."""
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
            self._exit_stack = None
            logger.info("ToolManager closed all MCP connections")

    # ------------------------------------------------------------------
    # Runtime interface
    # ------------------------------------------------------------------

    def get_schemas(self) -> list[dict]:
        """Return combined OpenAI tool schemas for all connected MCP tools."""
        return list(self._schemas)

    def get_function_names_for_groups(self, group_names: list[str]) -> set[str]:
        """Return the set of MCP function names belonging to the given tool groups.

        This enables per-agent tool filtering: an agent declaring
        ``tools: [k8s-reader]`` only gets the functions exposed by the
        ``k8s-reader`` MCP server, not functions from ``k8s-writer``.
        """
        result: set[str] = set()
        for group in group_names:
            fns = self._group_to_fn_names.get(group, set())
            if not fns:
                logger.warning("Tool group '%s' has no connected functions", group)
            result.update(fns)
        return result

    async def execute(self, tool_calls: list[dict]) -> list[dict]:
        """Route and execute a list of OpenAI tool calls.

        Args:
            tool_calls: Tool calls from an LLM response
                (``response["tool_calls"]``).

        Returns:
            List of OpenAI tool-result message dicts ready to append to the
            conversation history.
        """
        return await execute_tool_calls(tool_calls, self._tool_to_session)
