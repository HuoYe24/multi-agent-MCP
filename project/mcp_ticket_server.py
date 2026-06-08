import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sys.path.insert(0, os.path.dirname(__file__))

from fastmcp import FastMCP

import config
from ecommerce.tickets import TicketStore
from ecommerce.tools import infer_ticket_category, infer_priority
from memory.short_term import ShortTermMemory

memory = ShortTermMemory(key_prefix="multi_agent_mcp_tickets")
tickets = TicketStore(memory)

mcp = FastMCP(
    "ticket-server",
    instructions="E-commerce customer support ticket management.",
)


@mcp.tool()
def ticket_create(
    details: str,
    user_id: str = "anonymous",
    category: str = "",
    priority: str = "",
    summary: str = "",
) -> dict:
    return tickets.create(
        user_id=user_id,
        category=category or infer_ticket_category(details),
        priority=priority or infer_priority(details),
        summary=summary or details[:80],
        details=details,
    )


@mcp.tool()
def ticket_query(ticket_id: str) -> dict:
    ticket = tickets.query(ticket_id)
    return ticket or {"found": False, "ticket_id": ticket_id}


if __name__ == "__main__":
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    if transport == 'stdio':
        mcp.run(transport=transport)
    else:
        mcp.run(transport=transport, host=config.MCP_SERVER_HOST, port=8766)

