import json
import threading
import time
from pathlib import Path
from typing import Any

import config


class ShortTermMemory:
    """Redis-backed short-term memory with a JSON file fallback."""

    def __init__(
        self,
        redis_url: str = None,
        fallback_path: str = None,
        ttl_seconds: int = None,
        max_turns: int = None,
        key_prefix: str = "multi_agent_mcp",
    ):
        self.redis_url = redis_url or config.REDIS_URL
        self.fallback_path = Path(fallback_path or config.SHORT_TERM_MEMORY_FALLBACK_PATH)
        self.ttl_seconds = ttl_seconds or config.SHORT_TERM_MEMORY_TTL_SECONDS
        self.max_turns = max_turns or config.SHORT_TERM_MEMORY_MAX_TURNS
        self.key_prefix = key_prefix
        self._redis = None
        self._redis_checked = False
        self._lock = threading.Lock()
        self.fallback_path.parent.mkdir(parents=True, exist_ok=True)

    def _full_key(self, key: str) -> str:
        return f"{self.key_prefix}:{key}"

    def _get_redis(self):
        if self._redis_checked:
            return self._redis

        self._redis_checked = True
        try:
            import redis

            client = redis.Redis.from_url(self.redis_url, decode_responses=True)
            client.ping()
            self._redis = client
        except Exception:
            self._redis = None
        return self._redis

    def _read_fallback(self) -> dict[str, Any]:
        if not self.fallback_path.exists():
            return {}
        try:
            data = json.loads(self.fallback_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

        now = time.time()
        changed = False
        for key in list(data.keys()):
            expires_at = data[key].get("expires_at")
            if expires_at and expires_at <= now:
                data.pop(key, None)
                changed = True
        if changed:
            self._write_fallback(data)
        return data

    def _write_fallback(self, data: dict[str, Any]) -> None:
        self.fallback_path.parent.mkdir(parents=True, exist_ok=True)
        self.fallback_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_json(self, key: str, default=None):
        full_key = self._full_key(key)
        client = self._get_redis()
        if client is not None:
            raw = client.get(full_key)
            if raw is None:
                return default
            try:
                return json.loads(raw)
            except Exception:
                return default

        with self._lock:
            data = self._read_fallback()
            item = data.get(full_key)
            return item.get("value", default) if item else default

    def set_json(self, key: str, value, ttl_seconds: int = None) -> None:
        full_key = self._full_key(key)
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds
        client = self._get_redis()
        if client is not None:
            if ttl:
                client.set(full_key, json.dumps(value, ensure_ascii=False), ex=ttl)
            else:
                client.set(full_key, json.dumps(value, ensure_ascii=False))
            return

        with self._lock:
            data = self._read_fallback()
            data[full_key] = {"value": value, "expires_at": time.time() + ttl if ttl else None}
            self._write_fallback(data)

    def delete(self, key: str) -> None:
        full_key = self._full_key(key)
        client = self._get_redis()
        if client is not None:
            client.delete(full_key)
            return

        with self._lock:
            data = self._read_fallback()
            data.pop(full_key, None)
            self._write_fallback(data)

    def append_list(self, key: str, value, max_items: int = None, ttl_seconds: int = None) -> list:
        items = self.get_json(key, default=[])
        if not isinstance(items, list):
            items = []
        items.append(value)
        limit = max_items or self.max_turns
        items = items[-limit:]
        self.set_json(key, items, ttl_seconds=ttl_seconds)
        return items

    def add_message(self, session_id: str, role: str, content: str) -> None:
        message = {"role": role, "content": content, "timestamp": int(time.time())}
        self.append_list(f"sessions:{session_id}:messages", message, max_items=self.max_turns)

    def get_history(self, session_id: str, last_n: int = None) -> list[dict]:
        history = self.get_json(f"sessions:{session_id}:messages", default=[])
        if not isinstance(history, list):
            return []
        return history[-last_n:] if last_n else history
