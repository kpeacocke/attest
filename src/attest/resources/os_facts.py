"""Local OS fact resource (REQ-2.2: os facts helper)."""

from __future__ import annotations

import platform
from typing import Any

from attest.resources.interfaces import ResourceResult


class OsFactsResource:
    """Collect basic OS/distribution facts from the local host."""

    def query(self, params: dict[str, Any]) -> ResourceResult:
        data = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        }

        field = params.get("field")
        if isinstance(field, str):
            return ResourceResult(data=data.get(field), errors=[], timings={})
        return ResourceResult(data=data, errors=[], timings={})
