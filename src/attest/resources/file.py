"""File resource (REQ-2.2: file existence and metadata subset)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from attest.resources.interfaces import ResourceResult


class FileResource:
    """Query file existence and simple metadata for a local path."""

    def query(self, params: dict[str, Any]) -> ResourceResult:
        raw_path = params.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            return ResourceResult(
                data=None, errors=["'file' resource requires a non-empty 'path' parameter."]
            )

        path = Path(raw_path)
        try:
            exists = path.exists()
            data: dict[str, Any] = {
                "exists": exists,
                "is_file": path.is_file() if exists else False,
                "is_dir": path.is_dir() if exists else False,
            }
            if exists:
                stat = path.stat()
                data["size"] = stat.st_size
                data["mode"] = oct(stat.st_mode & 0o777)
            field = params.get("field")
            if isinstance(field, str):
                return ResourceResult(data=data.get(field), errors=[], timings={})
            return ResourceResult(data=data, errors=[], timings={})
        except OSError as exc:
            return ResourceResult(
                data=None, errors=[f"File query failed for '{raw_path}': {exc}"], timings={}
            )
