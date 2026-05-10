import itertools
from typing import Any

import httpx

import config
from core.observability import start_span
from mcp.registry import ToolRegistry


class MCPHttpClient:
    """Small JSON-RPC client for the project MCP tool server."""

    _ids = itertools.count(1)

    def __init__(
        self,
        server_url: str = None,
        timeout_seconds: float = None,
        fallback_registry: ToolRegistry = None,
    ):
        self.server_url = server_url or config.MCP_SERVER_URL
        self.timeout_seconds = timeout_seconds or config.MCP_CLIENT_TIMEOUT_SECONDS
        self.fallback_registry = fallback_registry

    def _request(self, method: str, params: dict[str, Any] = None) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": next(self._ids),
            "method": method,
            "params": params or {},
        }
        with start_span("mcp.client.request", {"mcp.method": method}):
            response = httpx.post(self.server_url, json=payload, timeout=self.timeout_seconds)
            response.raise_for_status()
            return response.json()

    def list_tools(self, category: str = None) -> list[dict[str, Any]]:
        try:
            data = self._request("tools/list", {"category": category} if category else {})
            return data.get("result", [])
        except Exception:
            if self.fallback_registry:
                return self.fallback_registry.list_tools(category=category)
            return []

    def call_tool(self, name: str, arguments: dict[str, Any] = None) -> dict[str, Any]:
        try:
            data = self._request("tools/call", {"name": name, "arguments": arguments or {}})
            result = data.get("result", {})
            if result:
                return result
            if data.get("error"):
                return {"tool_name": name, "success": False, "error": data["error"].get("message", "")}
        except Exception as exc:
            if self.fallback_registry:
                return self.fallback_registry.call_tool(name, arguments or {}).to_dict()
            return {"tool_name": name, "success": False, "error": str(exc)}

        return {"tool_name": name, "success": False, "error": "Empty MCP response."}
