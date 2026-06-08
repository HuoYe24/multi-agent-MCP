import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sys.path.insert(0, os.path.dirname(__file__))

from fastmcp import FastMCP
from datetime import datetime

import config
from ecommerce.compliance import review_customer_service_response
from ecommerce.tickets import TicketStore
from ecommerce.tools import (
    _mock_order,
    find_order_id,
    infer_ticket_category,
    infer_priority,
)
from memory.short_term import ShortTermMemory


memory = ShortTermMemory(key_prefix="multi_agent_mcp_tools")
tickets = TicketStore(memory)

# Note: FastMCP v3.x no longer accepts host/port in constructor.
# Pass them to run() or set FASTMCP_HOST / FASTMCP_PORT env vars.
mcp = FastMCP(
    "multi-agent-mcp-server",
    instructions="E-commerce customer service tools for order tracking, ticket management, and compliance risk checks.",
)


@mcp.tool()
def order_query(order_id: str, user_id: str = "") -> dict:
    """Query e-commerce order, shipping, and delivery status.

    Args:
        order_id: Order ID, such as ORD-20260510-001
        user_id: Current user ID
    """
    return _mock_order(order_id, user_id)


@mcp.tool()
def ticket_create(
    details: str,
    user_id: str = "anonymous",
    category: str = "",
    priority: str = "",
    summary: str = "",
) -> dict:
    """Create an e-commerce customer support ticket.

    Args:
        details: Customer issue description
        user_id: Current user ID
        category: Ticket category (refund, after_sales, complaint, shipping, general)
        priority: Priority level (urgent, high, medium)
        summary: Brief summary of the issue
    """
    return tickets.create(
        user_id=user_id,
        category=category or infer_ticket_category(details),
        priority=priority or infer_priority(details),
        summary=summary or details[:80],
        details=details,
    )


@mcp.tool()
def ticket_query(ticket_id: str) -> dict:
    """Query an existing customer support ticket by ticket ID.

    Args:
        ticket_id: Ticket ID, such as TK-20260510-XXXXXX
    """
    ticket = tickets.query(ticket_id)
    return ticket or {"found": False, "ticket_id": ticket_id}


@mcp.tool()
def risk_check(action: str, amount: float = 0.0, user_id: str = "") -> dict:
    """Check whether an e-commerce customer service action needs manual review.

    Args:
        action: Action to check (refund, compensation, customer_message_review)
        amount: Monetary amount involved
        user_id: Current user ID
    """
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
    print(f"Starting FastMCP server with '{transport}' transport...")
    if transport == 'stdio':
        mcp.run(transport=transport)
    else:
        mcp.run(transport=transport, host=config.MCP_SERVER_HOST, port=config.MCP_SERVER_PORT)

