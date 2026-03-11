"""JSON file resource (REQ-2.4: structured config file parsers)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from attest.resources.interfaces import ResourceResult


class JsonFileResource:
    """Read and optionally traverse a JSON file by dotted-path query.

    Parameters
    ----------
    path : str
        Absolute or relative path to the JSON file.
    query : str, optional
        Dot-separated key path to extract a nested value, e.g. ``"foo.bar.baz"``.
        If omitted, the entire parsed document is returned.
    """

    def query(self, params: dict[str, Any]) -> ResourceResult:
        raw_path = params.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            return ResourceResult(
                data=None,
                errors=["'json_file' resource requires a non-empty 'path' parameter."],
            )

        file_path = Path(raw_path)
        try:
            text = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            return ResourceResult(
                data=None,
                errors=[f"Cannot read JSON file '{raw_path}': {exc}"],
            )

        try:
            document = json.loads(text)
        except json.JSONDecodeError as exc:
            return ResourceResult(
                data=None,
                errors=[f"JSON parse error in '{raw_path}': {exc}"],
            )

        key_path = params.get("query")
        if isinstance(key_path, str) and key_path:
            document = self._traverse(document, key_path, raw_path)
            if isinstance(document, ResourceResult):
                return document

        return ResourceResult(data=document, errors=[], timings={})

    def _traverse(self, document: Any, key_path: str, file_path: str) -> Any:
        """Walk a dot-separated key path into a JSON document."""
        current = document
        for part in key_path.split("."):
            if isinstance(current, dict):
                if part not in current:
                    return ResourceResult(
                        data=None,
                        errors=[
                            f"Key '{part}' not found in JSON path '{key_path}'"
                            f" in '{file_path}'."
                        ],
                    )
                current = current[part]
            elif isinstance(current, list):
                try:
                    index = int(part)
                except ValueError:
                    return ResourceResult(
                        data=None,
                        errors=[
                            f"Expected integer index for list, got '{part}'"
                            f" in JSON path '{key_path}' in '{file_path}'."
                        ],
                    )
                try:
                    current = current[index]
                except IndexError:
                    return ResourceResult(
                        data=None,
                        errors=[
                            f"Index {index} out of range in JSON path '{key_path}'"
                            f" in '{file_path}'."
                        ],
                    )
            else:
                return ResourceResult(
                    data=None,
                    errors=[
                        f"Cannot traverse into scalar at '{part}'"
                        f" in JSON path '{key_path}' in '{file_path}'."
                    ],
                )
        return current
