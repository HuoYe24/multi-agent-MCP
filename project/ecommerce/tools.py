import re
from datetime import datetime, timedelta

import config
from ecommerce.tickets import TicketStore
from mcp.registry import ToolRegistry


def _mock_order(order_id: str, user_id: str = "") -> dict:
    normalized = (order_id or "").upper()
    seed = sum(ord(ch) for ch in normalized)
    statuses = [
        ("paid", "订单已支付，等待仓库拣货。"),
        ("shipped", "订单已发货，正在运输途中。"),
        ("out_for_delivery", "包裹正在派送，预计今天送达。"),
        ("delivered", "订单已签收。"),
    ]
    status, note = statuses[seed % len(statuses)]
    created_at = datetime.now() - timedelta(days=(seed % 5) + 1)
    eta = datetime.now() + timedelta(days=max(1, seed % 4))
    return {
        "order_id": normalized,
        "user_id": user_id or "anonymous",
        "status": status,
        "status_note": note,
        "carrier": "Demo Express",
        "tracking_number": f"DE{seed:08d}",
        "created_at": created_at.isoformat(timespec="seconds"),
        "estimated_delivery": eta.date().isoformat(),
        "items": [
            {"name": "Wireless Headphones", "quantity": 1},
            {"name": "Phone Case", "quantity": 1},
        ],
    }


def infer_ticket_category(message: str) -> str:
    text = message or ""
    if any(word in text for word in ["退款", "退钱", "refund"]):
        return "refund"
    if any(word in text for word in ["退货", "换货", "售后", "repair", "return"]):
        return "after_sales"
    if any(word in text for word in ["投诉", "complaint"]):
        return "complaint"
    if any(word in text for word in ["物流", "快递", "发货", "delivery", "shipping"]):
        return "shipping"
    return "general"


def infer_priority(message: str) -> str:
    text = message or ""
    if any(word in text for word in ["诈骗", "盗刷", "账号被盗", "urgent", "紧急"]):
        return "urgent"
    if any(word in text for word in ["投诉", "超时", "一直", "严重"]):
        return "high"
    return "medium"


def find_order_id(text: str) -> str:
    match = re.search(r"(ORD|ORDER)[-_]?\d{6,}[-_]?[A-Z0-9]*", text or "", re.IGNORECASE)
    return match.group(0).upper() if match else ""


def create_ecommerce_tool_registry(ticket_store: TicketStore = None) -> ToolRegistry:
    registry = ToolRegistry()
    tickets = ticket_store or TicketStore()

    @registry.register(
        name="order_query",
        description="Query e-commerce order, shipping, and delivery status.",
        input_schema={
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Order ID, such as ORD-20260510-001"},
                "user_id": {"type": "string", "description": "Current user ID"},
            },
            "required": ["order_id"],
        },
        category="order",
    )
    def order_query(order_id: str, user_id: str = "") -> dict:
        return _mock_order(order_id, user_id)

    @registry.register(
        name="ticket_create",
        description="Create an e-commerce customer support ticket.",
        input_schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "category": {"type": "string"},
                "priority": {"type": "string"},
                "summary": {"type": "string"},
                "details": {"type": "string"},
            },
            "required": ["details"],
        },
        category="ticket",
    )
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

    @registry.register(
        name="ticket_query",
        description="Query an existing customer support ticket by ticket ID.",
        input_schema={
            "type": "object",
            "properties": {"ticket_id": {"type": "string"}},
            "required": ["ticket_id"],
        },
        category="ticket",
    )
    def ticket_query(ticket_id: str) -> dict:
        ticket = tickets.query(ticket_id)
        return ticket or {"found": False, "ticket_id": ticket_id}

    @registry.register(
        name="risk_check",
        description="Check whether an e-commerce customer service action needs manual review.",
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "amount": {"type": "number"},
                "user_id": {"type": "string"},
            },
            "required": ["action"],
        },
        category="compliance",
    )
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

    return registry
