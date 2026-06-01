import re
from datetime import datetime, timedelta

import config


def _mock_order(order_id: str, user_id: str = "") -> dict:
    normalized = (order_id or "").upper()
    if not normalized:
        normalized = "ORD-20260510-001"
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
