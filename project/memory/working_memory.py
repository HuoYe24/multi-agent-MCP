import threading
from collections import defaultdict
from datetime import datetime
from typing import Any


class WorkingMemory:
    """Request/session scoped scratchpad for agent routing and intermediate facts."""

    def __init__(self, max_entries_per_session: int = 50):
        self._store = defaultdict(list)
        self._context = defaultdict(dict)
        self._lock = threading.Lock()
        self._max_entries = max_entries_per_session

    def update(self, session_id: str, data: dict[str, Any]) -> None:
        with self._lock:
            entry = {"timestamp": datetime.now().isoformat(), "data": data}
            self._store[session_id].append(entry)
            self._store[session_id] = self._store[session_id][-self._max_entries:]
            self._context[session_id].update(data)

    def get_context(self, session_id: str) -> dict[str, Any]:
        return dict(self._context.get(session_id, {}))

    def get_history(self, session_id: str, last_n: int = 10) -> list[dict]:
        return list(self._store.get(session_id, [])[-last_n:])

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._store.pop(session_id, None)
            self._context.pop(session_id, None)
