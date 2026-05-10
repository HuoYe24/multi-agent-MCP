import asyncio
import json
import threading
from datetime import timedelta
from typing import Any

import config
from core.observability import start_span
from mcp_bridge.registry import ToolRegistry


class MCPHttpClient:
    """Synchronous wrapper around the standard MCP Streamable HTTP client."""

    def __init__(
        self,
        server_url: str = None,
        timeout_seconds: float = None,
        fallback_registry: ToolRegistry = None,
    ):
        self.server_url = server_url or config.MCP_SERVER_URL
        self.timeout_seconds = timeout_seconds or config.MCP_CLIENT_TIMEOUT_SECONDS
        self.fallback_registry = fallback_registry

    def _run(self, async_func):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(async_func())

        result: dict[str, Any] = {}

        def run_in_thread():
            try:
                result["value"] = asyncio.run(async_func())
            except Exception as exc:
                result["error"] = exc

        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        thread.join()
        if "error" in result:
            raise result["error"]
        return result.get("value")

    async def _with_session(self, operation):
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        timeout = timedelta(seconds=float(self.timeout_seconds))
        async with streamablehttp_client(self.server_url, timeout=timeout) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await operation(session)

    @staticmethod
    def _tool_to_dict(tool) -> dict[str, Any]:
        return {
            "name": getattr(tool, "name", ""),
            "description": getattr(tool, "description", "") or "",
            "inputSchema": getattr(tool, "inputSchema", None)
            or getattr(tool, "input_schema", None)
            or {},
        }

    @staticmethod
    def _text_content(result) -> str:
        content = getattr(result, "content", []) or []
        texts = []
        for item in content:
            text = getattr(item, "text", None)
            if text:
                texts.append(text)
        return "\n".join(texts).strip()

    @classmethod
    def _structured_content(cls, result) -> Any:
        structured = getattr(result, "structuredContent", None)
        if structured is None:
            structured = getattr(result, "structured_content", None)
        if structured is not None:
            return structured

        text = cls._text_content(result)
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            return text

    def list_tools(self, category: str = None) -> list[dict[str, Any]]:
        try:
            async def operation(session):
                result = await session.list_tools()
                tools = [self._tool_to_dict(tool) for tool in getattr(result, "tools", [])]
                if not category:
                    return tools
                return [
                    tool for tool in tools
                    if category.lower() in str(tool.get("description", "")).lower()
                ]

            with start_span("mcp.client.request", {"mcp.method": "tools/list"}):
                return self._run(lambda: self._with_session(operation))
        except Exception:
            if self.fallback_registry:
                return self.fallback_registry.list_tools(category=category)
            return []

    def call_tool(self, name: str, arguments: dict[str, Any] = None) -> dict[str, Any]:
        try:
            async def operation(session):
                return await session.call_tool(name, arguments or {})

            with start_span("mcp.client.request", {"mcp.method": "tools/call", "mcp.tool": name}):
                result = self._run(lambda: self._with_session(operation))

            is_error = bool(getattr(result, "isError", False) or getattr(result, "is_error", False))
            if is_error:
                return {"tool_name": name, "success": False, "error": self._text_content(result)}

            return {
                "tool_name": name,
                "success": True,
                "result": self._structured_content(result),
            }
        except Exception as exc:
            if self.fallback_registry:
                return self.fallback_registry.call_tool(name, arguments or {}).to_dict()
            return {"tool_name": name, "success": False, "error": str(exc)}
