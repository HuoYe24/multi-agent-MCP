import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sys.path.insert(0, os.path.dirname(__file__))

from fastmcp import FastMCP

import config

mcp = FastMCP(
    "compliance-server",
    instructions="E-commerce compliance risk checks for customer service actions.",
)


@mcp.tool()
def risk_check(action: str, amount: float = 0.0, user_id: str = "") -> dict:
    risk_level = "low"
    if action in {"refund", "compensation"} and amount >= 500:
        risk_level = "medium"
    if amount >= 2000:
        risk_level = "high"
    return {
        "store": config.ECOMMERCE_DEFAULT_STORE_NAME,
        "user_id": user_id or "anonymous",
        "action": action,
        "amount": amount,
        "risk_level": risk_level,
        "requires_manual_review": risk_level == "high",
    }


if __name__ == "__main__":
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    mcp.run(transport=transport, host=config.MCP_SERVER_HOST, port=8767)
