"""Small, explicit caches for non-live agent work.

Live database values and customer-facing responses are deliberately never cached.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from time import monotonic
from typing import Any

from agent.lang import normalize_for_retrieval


@dataclass
class _CacheEntry:
    value: list[dict[str, Any]]
    expires_at: float


class RetrievalCache:
    """In-memory short-TTL cache that can be flushed on every KB mutation."""

    def __init__(self, ttl_seconds: int = 60) -> None:
        self.ttl_seconds = ttl_seconds
        self._entries: dict[str, _CacheEntry] = {}
        self.hits = 0
        self.misses = 0

    def key(self, query: str, metadata_filter: dict[str, Any] | None, top_k: int) -> str:
        material = f"{normalize_for_retrieval(query)}|{metadata_filter or {}}|{top_k}"
        return sha256(material.encode("utf-8")).hexdigest()

    def get(self, query: str, metadata_filter: dict[str, Any] | None, top_k: int) -> list[dict[str, Any]] | None:
        key = self.key(query, metadata_filter, top_k)
        entry = self._entries.get(key)
        if entry is None or entry.expires_at <= monotonic():
            self._entries.pop(key, None)
            self.misses += 1
            return None
        self.hits += 1
        return entry.value.copy()

    def set(self, query: str, metadata_filter: dict[str, Any] | None, top_k: int, value: list[dict[str, Any]]) -> None:
        key = self.key(query, metadata_filter, top_k)
        self._entries[key] = _CacheEntry(value=value.copy(), expires_at=monotonic() + self.ttl_seconds)

    def clear(self) -> None:
        self._entries.clear()

    @property
    def entry_count(self) -> int:
        return len(self._entries)
