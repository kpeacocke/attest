"""Sysctl resource (REQ-2.2): kernel parameter value lookup."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from attest.resources.interfaces import ResourceResult


class SysctlResource:
    """Query kernel sysctl values with `sysctl -n`."""

    def query(self, params: dict[str, Any]) -> ResourceResult:
        key = params.get("key")
        if not isinstance(key, str) or not key.strip():
            return ResourceResult(
                data=None,
                errors=["'sysctl' resource requires a non-empty 'key' parameter."],
                timings={},
            )

        if not shutil.which("sysctl"):
            return ResourceResult(
                data=None,
                errors=["'sysctl' command is not available on this host."],
                timings={},
            )

        completed = subprocess.run(
            ["sysctl", "-n", key],
            text=True,
            capture_output=True,
            check=False,
        )

        if completed.returncode != 0:
            stderr = completed.stderr.strip() or "Unknown sysctl query failure."
            return ResourceResult(data=None, errors=[stderr], timings={})

        value = completed.stdout.strip()
        return ResourceResult(data=value, errors=[], timings={})
