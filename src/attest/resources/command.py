"""Command resource (REQ-2.2) with conservative execution defaults."""

from __future__ import annotations

import subprocess
from typing import Any

from attest.resources.interfaces import ResourceResult


class CommandResource:
    """Execute a local command and return structured rc/stdout/stderr."""

    def query(self, params: dict[str, Any]) -> ResourceResult:
        command = params.get("command")
        if not isinstance(command, str) or not command.strip():
            return ResourceResult(
                data=None,
                errors=["'command' resource requires a non-empty 'command' parameter."],
                timings={},
            )

        timeout = params.get("timeout", 10)
        try:
            timeout_s = int(timeout)
        except (TypeError, ValueError):
            timeout_s = 10

        try:
            completed = subprocess.run(
                command,
                shell=True,
                text=True,
                capture_output=True,
                timeout=max(1, timeout_s),
                check=False,
            )
            data = {
                "rc": completed.returncode,
                "stdout": completed.stdout[:4096],
                "stderr": completed.stderr[:4096],
            }
            field = params.get("field")
            if isinstance(field, str):
                return ResourceResult(data=data.get(field), errors=[], timings={})
            return ResourceResult(data=data, errors=[], timings={})
        except subprocess.TimeoutExpired:
            return ResourceResult(
                data=None, errors=[f"Command timed out after {timeout_s}s."], timings={}
            )
