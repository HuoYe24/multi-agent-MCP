import os
import sys
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sys.path.insert(0, os.path.dirname(__file__))

import config
from core.observability import instrument_fastapi_app, start_span
from ecommerce.tools import create_ecommerce_tool_registry
from memory.short_term import ShortTermMemory


def create_app() -> FastAPI:
    app = FastAPI(title="Multi-Agent MCP Tool Server")
    instrument_fastapi_app(app, service_name="multi-agent-mcp-tools")

    memory = ShortTermMemory(key_prefix="multi_agent_mcp_tools")
    registry = create_ecommerce_tool_registry()

    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": "mcp-server"}

    @app.get("/tools")
    async def tools(category: str = None):
        return {"tools": registry.list_tools(category=category)}

    @app.get("/metrics")
    async def metrics():
        return {
            "tool_call_log": registry.get_call_log(last_n=50),
            "memory_backend": "redis" if memory._get_redis() is not None else "json",
        }

    @app.post("/mcp")
    async def mcp_endpoint(request: Request):
        payload = await request.json()
        with start_span("mcp.server.jsonrpc", {"mcp.method": payload.get("method", "")}):
            return JSONResponse(registry.handle_jsonrpc(payload))

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "mcp_server_app:create_app",
        host=config.MCP_SERVER_HOST,
        port=config.MCP_SERVER_PORT,
        factory=True,
    )
