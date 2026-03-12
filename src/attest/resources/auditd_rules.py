"""Auditd rules resource (REQ-2.2): query audit rules and configuration."""

from __future__ import annotations

import subprocess
from typing import Any

from attest.resources.interfaces import ResourceResult


class AuditdRulesResource:
    """Query auditd rules and configuration deterministically."""

    def query(self, params: dict[str, Any]) -> ResourceResult:
        search_pattern = params.get("pattern")
        field = params.get("field")

        if search_pattern is not None and (
            not isinstance(search_pattern, str) or not search_pattern.strip()
        ):
            return ResourceResult(
                data=None,
                errors=["'auditd_rules' resource parameter 'pattern' must be a non-empty string."],
                timings={},
            )

        completed = subprocess.run(
            ["auditctl", "-l"],
            text=True,
            capture_output=True,
            check=False,
        )

        if completed.returncode != 0:
            # auditctl not available or audit not enabled
            if "No such file" in completed.stderr or "command not found" in completed.stderr:
                return ResourceResult(
                    data=None,
                    errors=["auditctl command not available on this host."],
                    timings={},
                )
            return ResourceResult(
                data=None,
                errors=[f"Failed to query audit rules: {completed.stderr.strip()}"],
                timings={},
            )

        rules = self._parse_auditctl_output(completed.stdout)

        if search_pattern is not None:
            rules = [r for r in rules if search_pattern.lower() in r["raw_rule"].lower()]

        rules.sort(key=lambda r: r["raw_rule"])

        data = {
            "rules": rules,
            "count": len(rules),
        }

        if isinstance(field, str):
            return ResourceResult(data=data.get(field), errors=[], timings={})
        return ResourceResult(data=data, errors=[], timings={})

    def _parse_auditctl_output(self, output: str) -> list[dict[str, object]]:
        rules: list[dict[str, object]] = []

        for line in output.splitlines():
            line = line.rstrip()
            if not line or line.startswith("No rules"):
                continue

            rule = self._parse_rule_line(line)
            if rule:
                rules.append(rule)

        return rules

    def _parse_rule_line(self, line: str) -> dict[str, object] | None:
        """Parse a single auditctl rule line."""
        entry: dict[str, object] = {
            "raw_rule": line,
            "type": None,
            "action": None,
            "path": None,
            "syscall": None,
            "key": None,
        }

        parts = line.split()
        if not parts:
            return None

        i = 0
        while i < len(parts):
            i += self._consume_rule_part(entry, parts, i)

        return entry

    def _consume_rule_part(
        self,
        entry: dict[str, object],
        parts: list[str],
        index: int,
    ) -> int:
        """Consume one or two tokens from a parsed rule and update entry."""
        part = parts[index]
        token_map = {
            "-w": "path",
            "-k": "key",
            "-S": "syscall",
            "-a": "action",
        }

        if part in token_map and index + 1 < len(parts):
            entry[token_map[part]] = parts[index + 1]
            return 2

        # Permission flags are parsed but not stored; consume next value token.
        if part == "-p" and index + 1 < len(parts):
            return 2

        if part.startswith("-") and "=" in part:
            self._consume_kv_rule_part(entry, part)
            return 1

        return 1

    def _consume_kv_rule_part(self, entry: dict[str, object], part: str) -> None:
        """Handle --key=value style flags for selected fields."""
        key, value = part.split("=", 1)
        key_lower = key.lstrip("-").lower()
        if key_lower == "action":
            entry["action"] = value
        elif key_lower == "path":
            entry["path"] = value
        elif key_lower == "syscall":
            entry["syscall"] = value
        elif key_lower == "key":
            entry["key"] = value
