"""Tool loading for the report writer workflow — Tavily web search + Context7."""

import os


CONTEXT7_MCP_URL = os.environ.get(
    "CONTEXT7_MCP_URL",
    "https://mcp.context7.com/mcp",
)


def load_search_tools():
    """Load Tavily web search as a LangChain tool."""
    from langchain_tavily import TavilySearch

    return [TavilySearch(max_results=3)]


async def load_context7_tools():
    """Load Context7 documentation lookup tools via MCP."""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(
        {"context7": {"url": CONTEXT7_MCP_URL, "transport": "streamable_http"}}
    )
    tools = await client.get_tools()
    return tools, client


async def load_all_tools():
    """Load all research tools (search + context7). Returns a flat list."""
    search_tools = load_search_tools()
    context7_tools, _ = await load_context7_tools()
    return search_tools + context7_tools
