from datetime import datetime
import re
import uuid

from memory.short_term import ShortTermMemory


class TicketStore:
    def __init__(self, memory: ShortTermMemory = None):
        self.memory = memory or ShortTermMemory()

    @staticmethod
    def _ticket_key(ticket_id: str) -> str:
        return f"tickets:{ticket_id}"

    @staticmethod
    def _user_tickets_key(user_id: str) -> str:
        return f"users:{user_id}:tickets"

    @staticmethod
    def find_ticket_id(text: str) -> str:
        match = re.search(r"TK-\d{8}-[A-Z0-9]{6}", text or "", re.IGNORECASE)
        return match.group(0).upper() if match else ""

    def create(
        self,
        user_id: str,
        category: str,
        priority: str,
        summary: str,
        details: str,
    ) -> dict:
        now = datetime.now().isoformat(timespec="seconds")
        ticket_id = f"TK-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        ticket = {
            "ticket_id": ticket_id,
            "user_id": user_id or "anonymous",
            "category": category or "general",
            "priority": priority or "medium",
            "status": "created",
            "summary": summary or details[:80],
            "details": details,
            "created_at": now,
            "updated_at": now,
        }
        self.memory.set_json(self._ticket_key(ticket_id), ticket, ttl_seconds=0)
        self.memory.append_list(
            self._user_tickets_key(ticket["user_id"]),
            ticket_id,
            max_items=100,
            ttl_seconds=0,
        )
        return ticket

    def query(self, ticket_id: str) -> dict | None:
        if not ticket_id:
            return None
        return self.memory.get_json(self._ticket_key(ticket_id.upper()))

    def query_by_user(self, user_id: str) -> list[dict]:
        ticket_ids = self.memory.get_json(self._user_tickets_key(user_id or "anonymous"), default=[])
        if not isinstance(ticket_ids, list):
            return []
        return [ticket for ticket in (self.query(tid) for tid in ticket_ids) if ticket]
