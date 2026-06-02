import os
import sys
from pathlib import Path
from fastmcp import FastMCP
from fastmcp.server import create_proxy

# Ensure project root is on sys.path so backends can be spawned with stdio
_proj_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_proj_root))


def create_gateway(name: str = "mcp-gateway") -> FastMCP:
    """Create and configure the MCP Gateway server.

    The Gateway mounts three backend FastMCP servers (order, ticket, compliance)
    via stdio subprocess, exposing all their tools at a single endpoint.
    """
    gateway = FastMCP(
        name,
        instructions="MCP Gateway aggregating order, ticket, and compliance services.",
    )

    gateway.mount(
        create_proxy({
            "mcpServers": {
                "order": {
                    "command": sys.executable,
                    "args": [str(_proj_root / "mcp_order_server.py"), "stdio"],
                    "transport": "stdio",
                }
            }
        })
    )

    gateway.mount(
        create_proxy({
            "mcpServers": {
                "ticket": {
                    "command": sys.executable,
                    "args": [str(_proj_root / "mcp_ticket_server.py"), "stdio"],
                    "transport": "stdio",
                }
            }
        })
    )

    gateway.mount(
        create_proxy({
            "mcpServers": {
                "compliance": {
                    "command": sys.executable,
                    "args": [str(_proj_root / "mcp_compliance_server.py"), "stdio"],
                    "transport": "stdio",
                }
            }
        })
    )

    return gateway


if __name__ == "__main__":
    import config
    gw = create_gateway()
    gw.run(transport="http", host=config.MCP_SERVER_HOST, port=9000)
