"""Per-host per-run resource cache (REQ-2.3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from attest.resources.interfaces import ResourceResult


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0


class ResourceCache:
    """In-memory cache keyed by host, resource name, and normalised params."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str, str], ResourceResult] = {}
        self.stats = CacheStats()

    @staticmethod
    def _make_key(host: str, resource: str, params: dict[str, Any]) -> tuple[str, str, str]:
        # Deterministic key representation for diff-friendly cache behaviour.
        normalised = repr(sorted(params.items(), key=lambda item: item[0]))
        return host, resource, normalised

    def get(self, host: str, resource: str, params: dict[str, Any]) -> ResourceResult | None:
        key = self._make_key(host, resource, params)
        result = self._store.get(key)
        if result is None:
            self.stats.misses += 1
            return None

        self.stats.hits += 1
        return ResourceResult(
            data=result.data,
            errors=list(result.errors),
            timings=dict(result.timings),
            cache_hit=True,
        )

    def set(self, host: str, resource: str, params: dict[str, Any], result: ResourceResult) -> None:
        key = self._make_key(host, resource, params)
        self._store[key] = ResourceResult(
            data=result.data,
            errors=list(result.errors),
            timings=dict(result.timings),
            cache_hit=False,
        )
