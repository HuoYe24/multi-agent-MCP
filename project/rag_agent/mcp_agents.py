"""MCP Agent nodes — specialized agents for e-commerce customer service."""

from langchain_core.messages import AIMessage

from .graph_state import State
from ecommerce.compliance import review_customer_service_response
from ecommerce.tickets import TicketStore
from ecommerce.tools import find_order_id


def _call_mcp_tool(tools, name, args):
    """Call an MCP tool by name from the LangChain tools list."""
    for t in tools or []:
        if t.name == name:
            try:
                return t.invoke(args)
            except Exception as e:
                return {"success": False, "error": str(e), "result": None}
    return {"success": False, "error": f"Tool '{name}' not available", "result": None}


def order_query_agent(state, llm=None, mcp_langchain_tools=None, working_memory=None):
    """Dedicated agent for order/shipping queries."""
    last_message = state["messages"][-1]
    message = str(last_message.content or "")
    user_id = state.get("user_id", "anonymous")
    order_id = find_order_id(message)
    if not order_id:
        for item in reversed(state.get("recent_history", [])):
            order_id = find_order_id(str(item.get("content", "")))
            if order_id:
                break
    if not order_id:
        return {"messages": [AIMessage(content="请提供订单号，例如 `ORD-20260510-001`，我才能帮你查询物流和订单状态。")]}
    result = _call_mcp_tool(mcp_langchain_tools, "order_query", {"order_id": order_id, "user_id": user_id})
    if not result.get("success", True):
        return {"messages": [AIMessage(content=f"订单查询失败：{result.get('error', '工具暂不可用')}")]}
    order = result.get("result", result) if isinstance(result, dict) else result
    if working_memory:
        working_memory.update(user_id, {"last_order_id": order_id, "last_route": "order_query"})
    status_labels = {"paid": "✅ 已支付，等待拣货", "shipped": "🚚 已发货，运输中", "out_for_delivery": "📬 派送中", "delivered": "📦 已签收", "unknown": "❓ 状态未知"}
    status_text = status_labels.get(order.get("status", ""), order.get("status", "未知"))
    items_text = ", ".join(i.get("name", "") for i in order.get("items", []))
    order_info = f"""📦 **订单 {order.get('order_id', order_id)}**

状态：{status_text}
说明：{order.get('status_note', '')}
承运商：{order.get('carrier', '')}
运单号：{order.get('tracking_number', '')}
预计送达：{order.get('estimated_delivery', '')}
商品：{items_text}"""
    review = review_customer_service_response(order_info)
    return {"messages": [AIMessage(content=review["sanitized_content"])]}


def ticket_agent(state, llm=None, mcp_langchain_tools=None, working_memory=None):
    """Dedicated agent for ticket create/query."""
    last_message = state["messages"][-1]
    message = str(last_message.content or "")
    user_id = state.get("user_id", "anonymous")
    ticket_id = TicketStore.find_ticket_id(message)
    if ticket_id:
        result = _call_mcp_tool(mcp_langchain_tools, "ticket_query", {"ticket_id": ticket_id})
        if not result.get("success", True):
            return {"messages": [AIMessage(content=f"工单查询失败：{result.get('error', '工具暂不可用')}")]}
        ticket = result.get("result", result) if isinstance(result, dict) else result
        if isinstance(ticket, dict) and ticket.get("found") is False:
            return {"messages": [AIMessage(content=f"没有查到工单 `{ticket_id}`，请确认工单号是否正确。")]}
        return {"messages": [AIMessage(content=_format_ticket(ticket))]}
    category = state.get("ticket_category", "") or _infer_category(message)
    priority = state.get("ticket_priority", "") or _infer_priority(message)
    result = _call_mcp_tool(mcp_langchain_tools, "ticket_create", {"user_id": user_id, "category": category, "priority": priority, "summary": message[:80], "details": message})
    if not result.get("success", True):
        return {"messages": [AIMessage(content=f"工单创建失败：{result.get('error', '工具暂不可用')}")]}
    ticket = result.get("result", result) if isinstance(result, dict) else result
    if working_memory:
        tid = ticket.get("ticket_id", "") if isinstance(ticket, dict) else ""
        working_memory.update(user_id, {"last_ticket_id": tid, "last_route": "ticket_support"})
    return {"messages": [AIMessage(content=_format_ticket(ticket))]}


def compliance_agent(state, llm=None, mcp_langchain_tools=None):
    """Dedicated agent for compliance review."""
    last_message = state["messages"][-1]
    message = str(last_message.content or "")
    user_id = state.get("user_id", "anonymous")
    review = review_customer_service_response(message)
    result = _call_mcp_tool(mcp_langchain_tools, "risk_check", {"action": "customer_message_review", "user_id": user_id})
    if not review["passed"]:
        content = """⚠️ 这类表达可能包含不合规承诺或隐私风险，我不能按原样处理。

我可以继续帮你按平台规则查询订单、创建售后工单，或根据知识库解释退换货政策。"""
    elif isinstance(result, dict) and result.get("requires_manual_review"):
        content = "🛡️ 这个请求需要人工客服复核。我可以先为你创建售后工单，方便后续跟进。"
    else:
        content = "✅ 我会按平台客服规范处理：不泄露隐私信息，不承诺超出规则的退款或赔偿，并在需要时转交人工客服复核。"
    return {"messages": [AIMessage(content=content)]}


def _format_ticket(ticket):
    if not isinstance(ticket, dict):
        return f"工单信息：{ticket}"
    priority_label = {"low": "普通", "medium": "中等", "high": "高", "urgent": "紧急"}
    status_label = {"created": "已创建", "processing": "处理中", "resolved": "已解决", "closed": "已关闭"}
    return f"""🎫 **工单 {ticket.get('ticket_id', '')}**

类型：{ticket.get('category', '')}
优先级：{priority_label.get(ticket.get('priority', ''), ticket.get('priority', '中等'))}
状态：{status_label.get(ticket.get('status', ''), ticket.get('status', '已创建'))}
摘要：{ticket.get('summary', '')}

客服会根据工单继续处理，请保留工单号方便后续查询。"""


def _infer_category(text):
    t = text or ""
    if any(w in t for w in ["退款", "refund"]): return "refund"
    if any(w in t for w in ["退货", "换货", "售后", "return"]): return "after_sales"
    if any(w in t for w in ["投诉", "complaint"]): return "complaint"
    if any(w in t for w in ["物流", "快递", "发货", "delivery"]): return "shipping"
    return "general"


def _infer_priority(text):
    t = text or ""
    if any(w in t for w in ["诈骗", "盗刷", "紧急", "urgent"]): return "urgent"
    if any(w in t for w in ["投诉", "超时", "严重"]): return "high"
    return "medium"
