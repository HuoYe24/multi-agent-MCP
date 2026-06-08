import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sys.path.insert(0, os.path.dirname(__file__))

from fastmcp import FastMCP

import config
from ecommerce.tools import _mock_order, find_order_id

mcp = FastMCP(
    "order-server",
    instructions="E-commerce order tracking and shipping status queries.",
)


@mcp.tool()
def order_query(order_id: str, user_id: str = "") -> dict:
    """Query e-commerce order, shipping, and delivery status.

    Args:
        order_id: Order ID, such as ORD-20260510-001
        user_id: Current user ID
    """
    return _mock_order(order_id, user_id)


if __name__ == "__main__":
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    if transport == 'stdio':
        mcp.run(transport=transport)
    else:
        mcp.run(transport=transport, host=config.MCP_SERVER_HOST, port=8765)

