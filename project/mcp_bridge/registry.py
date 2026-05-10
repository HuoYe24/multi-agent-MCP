from dataclasses import dataclass, field
from datetime import datetime
import time
from typing import Any, Callable


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Any]
    category: str = "general"


@dataclass
class ToolCallResult:
    tool_name: str
    success: bool
    result: Any = None
    error: str = ""
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._call_log: list[ToolCallResult] = []

    def register(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        category: str = "general",
    ):
        def decorator(func: Callable[..., Any]):
            self._tools[name] = ToolDefinition(
                name=name,
                description=description,
                input_schema=input_schema,
                handler=func,
                category=category,
            )
            return func

        return decorator

    def list_tools(self, category: str = None) -> list[dict[str, Any]]:
        tools = []
        for tool in self._tools.values():
            if category and tool.category != category:
                continue
            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.input_schema,
                    "category": tool.category,
                }
            )
        return tools

    def _validate_required(self, tool: ToolDefinition, arguments: dict[str, Any]) -> str:
        required = tool.input_schema.get("required", [])
        missing = [name for name in required if not arguments.get(name)]
        if missing:
            return f"Missing required arguments: {', '.join(missing)}"
        return ""

    def call_tool(self, name: str, arguments: dict[str, Any] = None) -> ToolCallResult:
        arguments = arguments or {}
        tool = self._tools.get(name)
        if tool is None:
            result = ToolCallResult(
                tool_name=name,
                success=False,
                error=f"Tool '{name}' not found.",
            )
            self._call_log.append(result)
            return result

        validation_error = self._validate_required(tool, arguments)
        if validation_error:
            result = ToolCallResult(tool_name=name, success=False, error=validation_error)
            self._call_log.append(result)
            return result

        start = time.time()
        try:
            output = tool.handler(**arguments)
            result = ToolCallResult(
                tool_name=name,
                success=True,
                result=output,
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as exc:
            result = ToolCallResult(
                tool_name=name,
                success=False,
                error=str(exc),
                duration_ms=(time.time() - start) * 1000,
            )

        self._call_log.append(result)
        return result

    def handle_jsonrpc(self, request: dict[str, Any]) -> dict[str, Any]:
        method = request.get("method", "")
        params = request.get("params", {}) or {}
        request_id = request.get("id", 1)

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": self.list_tools(category=params.get("category")),
            }

        if method == "tools/call":
            call_result = self.call_tool(
                params.get("name", ""),
                params.get("arguments", {}) or {},
            )
            return {"jsonrpc": "2.0", "id": request_id, "result": call_result.to_dict()}

        if method == "ping":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"status": "ok"}}

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    def get_call_log(self, last_n: int = 100) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self._call_log[-last_n:]]
