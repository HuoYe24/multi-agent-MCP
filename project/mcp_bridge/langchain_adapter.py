import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import List

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

import config

logger = logging.getLogger(__name__)


class MCPToolsAdapter:
    """Adapter that uses MultiServerMCPClient to expose FastMCP tools as LangChain tools.

    Supports two transport modes:
    - ``http``: Connect to an already-running FastMCP server (streamable-http mode).
    - ``stdio``: Spawn the FastMCP server as a child process via stdin/stdout.

    Usage:
        adapter = MCPToolsAdapter()
        mcp_tools = adapter.get_tools_sync()  # sync call, safe at startup
        # mcp_tools is a list of langchain BaseTool objects
    """

    def __init__(
        self,
        transport: str = "http",
        server_url: str | None = None,
        server_script: str | None = None,
    ):
        self.transport = transport
        self.server_url = server_url or config.MCP_SERVER_URL
        self.server_script = server_script or str(
            Path(__file__).resolve().parent.parent / "mcp_fastmcp_server.py"
        )
        self._client: MultiServerMCPClient | None = None

    def _build_connection(self) -> dict:
        if self.transport == "http":
            return {
                "transport": "http",
                "url": self.server_url,
            }
        elif self.transport == "stdio":
            return {
                "transport": "stdio",
                "command": sys.executable,
                "args": [self.server_script, "stdio"],
            }
        elif self.transport == "sse":
            sse_url = self.server_url.replace("/mcp", "/sse")
            return {
                "transport": "sse",
                "url": sse_url,
            }
        else:
            raise ValueError(f"Unsupported transport: {self.transport}")

    async def get_tools_async(self) -> List[BaseTool]:
        """Connect to the FastMCP server and return tools as LangChain tools (async)."""
        connection = self._build_connection()
        self._client = MultiServerMCPClient(
            {"ecommerce": connection},
            tool_name_prefix=False,
        )
        logger.info(
            "Connecting to FastMCP server via %s transport...", self.transport
        )
        tools = await self._client.get_tools()
        logger.info("Loaded %d MCP tools as LangChain tools", len(tools))
        return tools

    def get_tools_sync(self) -> List[BaseTool]:
        """Synchronous wrapper — safe to call at application startup."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            # Already in an async context — create a new loop in a thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._run_async_in_new_loop)
                return future.result()
        else:
            return self._run_async_in_new_loop()

    def _run_async_in_new_loop(self) -> List[BaseTool]:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.get_tools_async())
        finally:
            loop.close()

    async def close(self):
        """Release any resources held by the client."""
        self._client = None
