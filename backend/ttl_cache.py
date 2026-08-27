"""
ttl_cache.py — Tiny async-safe TTL cache for hot search queries.

Used by the public search layer to avoid hammering BidMotors on repeated
autocomplete keystrokes (debounced 250 ms × many users).
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional, Tuple


class TTLCache:
    def __init__(self, ttl_seconds: int = 300, max_size: int = 2048):
        self.ttl = ttl_seconds
        self.max_size = max_size
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._lock = asyncio.Lock()
        self.hits = 0
        self.misses = 0

    def _now(self) -> float:
        return time.time()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._store.get(key)
            if not entry:
                self.misses += 1
                return None
            ts, val = entry
            if self._now() - ts > self.ttl:
                # expired — drop
                self._store.pop(key, None)
                self.misses += 1
                return None
            self.hits += 1
            return val

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            # Eviction: if over max_size, drop oldest 10%
            if len(self._store) >= self.max_size:
                victims = sorted(self._store.items(), key=lambda kv: kv[1][0])[: max(1, self.max_size // 10)]
                for k, _ in victims:
                    self._store.pop(k, None)
            self._store[key] = (self._now(), value)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()

    def stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        return {
            "size": len(self._store),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl,
            "hits": self.hits,
            "misses": self.misses,
            "hit_ratio": round(self.hits / total, 3) if total else 0.0,
        }
