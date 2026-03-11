"""SSH daemon configuration parser resource (REQ-2.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from attest.resources.interfaces import ResourceResult


class SshConfigResource:
    """Parse sshd_config-style key/value directives for structured assertions."""

    def query(self, params: dict[str, Any]) -> ResourceResult:
        raw_path = params.get("path", "/etc/ssh/sshd_config")
        if not isinstance(raw_path, str) or not raw_path.strip():
            return ResourceResult(
                data=None,
                errors=["'ssh_config' resource requires a non-empty 'path' parameter."],
                timings={},
            )

        path = Path(raw_path)
        if not path.exists():
            return ResourceResult(
                data=None,
                errors=[f"SSH config file '{raw_path}' does not exist."],
                timings={},
            )

        try:
            parsed = self._parse(path.read_text(encoding="utf-8"))
        except OSError as exc:
            return ResourceResult(
                data=None,
                errors=[f"Failed to read SSH config '{raw_path}': {exc}"],
                timings={},
            )

        field = params.get("field")
        if isinstance(field, str):
            return ResourceResult(data=parsed.get(field.lower()), errors=[], timings={})
        return ResourceResult(data=parsed, errors=[], timings={})

    @staticmethod
    def _parse(content: str) -> dict[str, str]:
        parsed: dict[str, str] = {}
        in_match_block = False

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if line.lower().startswith("match "):
                in_match_block = True
                continue

            if in_match_block:
                # Skip match-specific overrides; top-level defaults stay deterministic.
                continue

            if "#" in line:
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue

            parts = line.split(None, 1)
            if len(parts) != 2:
                continue

            key, value = parts
            parsed[key.lower()] = value.strip()

        return parsed
