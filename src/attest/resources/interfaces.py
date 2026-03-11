"""Resource contracts and registry for Attest resources (REQ-2.1, REQ-2.3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Protocol


@dataclass
class ResourceResult:
    """Structured resource query result contract (REQ-2.1)."""

    data: Any = None
    errors: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    cache_hit: bool = False


class ResourceHandler(Protocol):
    """Protocol implemented by concrete resource handlers."""

    def query(self, params: dict[str, Any]) -> ResourceResult:
        """Query a resource and return structured results."""


class ResourceRegistry:
    """Lookup and invoke resource handlers by resource name."""

    def __init__(self) -> None:
        self._handlers: dict[str, ResourceHandler] = {}

    def register(self, name: str, handler: ResourceHandler) -> None:
        self._handlers[name] = handler

    def has(self, name: str) -> bool:
        return name in self._handlers

    def query(self, name: str, params: dict[str, Any]) -> ResourceResult:
        start = perf_counter()
        handler = self._handlers.get(name)
        if handler is None:
            elapsed = (perf_counter() - start) * 1000.0
            return ResourceResult(
                data=None,
                errors=[f"Resource '{name}' is not implemented."],
                timings={"query_ms": round(elapsed, 3)},
            )

        result = handler.query(params)
        if "query_ms" not in result.timings:
            result.timings["query_ms"] = round((perf_counter() - start) * 1000.0, 3)
        return result
