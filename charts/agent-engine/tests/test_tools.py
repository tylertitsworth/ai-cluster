"""Tests for tool schema conversion and group-based filtering."""

import pytest


class TestSchemaConversion:
    def test_converts_mcp_tool_to_openai_schema(self):
        from unittest.mock import MagicMock

        from engine.tools import mcp_tools_to_openai_schema

        mock_tool = MagicMock()
        mock_tool.name = "web_search"
        mock_tool.description = "Search the web"
        mock_tool.inputSchema = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
        }

        schemas = mcp_tools_to_openai_schema([mock_tool])

        assert len(schemas) == 1
        assert schemas[0]["type"] == "function"
        assert schemas[0]["function"]["name"] == "web_search"
        assert schemas[0]["function"]["description"] == "Search the web"
        assert "query" in schemas[0]["function"]["parameters"]["properties"]

    def test_handles_missing_input_schema(self):
        from unittest.mock import MagicMock

        from engine.tools import mcp_tools_to_openai_schema

        mock_tool = MagicMock()
        mock_tool.name = "simple_tool"
        mock_tool.description = ""
        mock_tool.inputSchema = None

        schemas = mcp_tools_to_openai_schema([mock_tool])

        assert schemas[0]["function"]["parameters"]["type"] == "object"


class TestToolManagerFiltering:
    def test_get_function_names_for_groups(self):
        from engine.tools import ToolManager

        manager = ToolManager({"search": {"type": "mcp"}, "k8s": {"type": "mcp"}})
        manager._group_to_fn_names = {
            "search": {"web_search", "image_search"},
            "k8s": {"get_pods", "get_services", "delete_pod"},
        }

        result = manager.get_function_names_for_groups(["search"])
        assert result == {"web_search", "image_search"}

    def test_multiple_groups_are_unioned(self):
        from engine.tools import ToolManager

        manager = ToolManager({})
        manager._group_to_fn_names = {
            "search": {"web_search"},
            "k8s": {"get_pods"},
        }

        result = manager.get_function_names_for_groups(["search", "k8s"])
        assert result == {"web_search", "get_pods"}

    def test_unknown_group_returns_empty(self):
        from engine.tools import ToolManager

        manager = ToolManager({})
        manager._group_to_fn_names = {"search": {"web_search"}}

        result = manager.get_function_names_for_groups(["nonexistent"])
        assert result == set()

    def test_empty_groups_returns_empty(self):
        from engine.tools import ToolManager

        manager = ToolManager({})
        result = manager.get_function_names_for_groups([])
        assert result == set()
