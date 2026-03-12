"""File resource (REQ-2.2: file existence and metadata subset)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from attest.resources.interfaces import ResourceResult


class FileResource:
    """Query file existence and simple metadata for a local path."""

    def _apply_optional_hash_fields(
        self, data: dict[str, Any], params: dict[str, Any], path: Path
    ) -> None:
        """Attach hash fields when requested and supported."""
        hash_algo = params.get("hash_algorithm")
        if not hash_algo:
            return

        hash_value = self._compute_hash(path, hash_algo)
        if not hash_value:
            return

        data["hash"] = hash_value
        data["hash_algorithm"] = hash_algo
        expected_hash = params.get("expected_hash")
        if isinstance(expected_hash, str):
            data["hash_match"] = hash_value.lower() == expected_hash.lower()

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
                self._apply_optional_hash_fields(data, params, path)

            field = params.get("field")
            if isinstance(field, str):
                return ResourceResult(data=data.get(field), errors=[], timings={})
            return ResourceResult(data=data, errors=[], timings={})
        except OSError as exc:
            return ResourceResult(
                data=None, errors=[f"File query failed for '{raw_path}': {exc}"], timings={}
            )

    def _compute_hash(self, path: Path, algorithm: str) -> str | None:
        """Compute file hash using the specified algorithm."""
        algo_lower = algorithm.lower()
        if algo_lower not in {"md5", "sha256", "sha512"}:
            return None

        try:
            hasher = hashlib.new(algo_lower)
        except ValueError:
            return None

        try:
            with open(path, "rb") as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (OSError, IOError):
            return None
