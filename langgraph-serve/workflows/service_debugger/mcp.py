"""MCP tool loading for Kubernetes read-only and read-write servers."""

import os


K8S_MCP_RO_URL = os.environ.get(
    "K8S_MCP_RO_URL",
    "http://kubernetes-mcp-server.kubernetes-mcp.svc.cluster.local:8080/mcp",
)
K8S_MCP_RW_URL = os.environ.get(
    "K8S_MCP_RW_URL",
    "http://kubernetes-mcp-server-rw.kubernetes-mcp.svc.cluster.local:8080/mcp",
)


async def load_mcp_tools(url: str):
    """Load LangChain tools from an MCP server endpoint."""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(
        {"k8s": {"url": url, "transport": "streamable_http"}}
    )
    tools = await client.get_tools()
    return tools, client
