from typing import Any

import httpx

import config
from core.observability import start_span
from mcp_bridge.registry import ToolRegistry


class MCPHttpClient:
    """Synchronous JSON-RPC client for the local MCP tool server."""

    def __init__(
        self,
        server_url: str = None,
        timeout_seconds: float = None,
        fallback_registry: ToolRegistry = None,
    ):
        self.server_url = server_url or config.MCP_SERVER_URL
        self.timeout_seconds = timeout_seconds or config.MCP_CLIENT_TIMEOUT_SECONDS
        self.fallback_registry = fallback_registry

    def _request(self, method: str, params: dict[str, Any] = None) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {},
        }
        response = httpx.post(
            self.server_url,
            json=payload,
            timeout=float(self.timeout_seconds),
        )
        response.raise_for_status()
        data = response.json()
        if data.get("error"):
            raise RuntimeError(data["error"].get("message", data["error"]))
        return data.get("result")

    def list_tools(self, category: str = None) -> list[dict[str, Any]]:
        try:
            with start_span("mcp.client.request", {"mcp.method": "tools/list"}):
                return self._request("tools/list", {"category": category})
        except Exception:
            if self.fallback_registry:
                return self.fallback_registry.list_tools(category=category)
            return []

    def call_tool(self, name: str, arguments: dict[str, Any] = None) -> dict[str, Any]:
        try:
            with start_span("mcp.client.request", {"mcp.method": "tools/call", "mcp.tool": name}):
                return self._request(
                    "tools/call",
                    {"name": name, "arguments": arguments or {}},
                )
        except Exception as exc:
            if self.fallback_registry:
                return self.fallback_registry.call_tool(name, arguments or {}).to_dict()
            return {"tool_name": name, "success": False, "error": str(exc)}
