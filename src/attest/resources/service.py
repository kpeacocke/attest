"""Service resource (REQ-2.2): enabled/running status via systemd."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from attest.resources.interfaces import ResourceResult


class ServiceResource:
    """Query systemd service state for a unit name."""

    def query(self, params: dict[str, Any]) -> ResourceResult:
        service_name = params.get("name")
        if not isinstance(service_name, str) or not service_name.strip():
            return ResourceResult(
                data=None,
                errors=["'service' resource requires a non-empty 'name' parameter."],
                timings={},
            )

        if not shutil.which("systemctl"):
            return ResourceResult(
                data=None,
                errors=["'systemctl' command is not available on this host."],
                timings={},
            )

        active_cmd = ["systemctl", "is-active", service_name]
        enabled_cmd = ["systemctl", "is-enabled", service_name]

        active = subprocess.run(active_cmd, text=True, capture_output=True, check=False)
        enabled = subprocess.run(enabled_cmd, text=True, capture_output=True, check=False)

        active_state = active.stdout.strip() if active.stdout else "unknown"
        enabled_state = enabled.stdout.strip() if enabled.stdout else "unknown"

        data = {
            "running": active.returncode == 0 and active_state == "active",
            "enabled": enabled.returncode == 0 and enabled_state == "enabled",
            "active_state": active_state,
            "enabled_state": enabled_state,
        }

        field = params.get("field")
        if isinstance(field, str):
            return ResourceResult(data=data.get(field), errors=[], timings={})

        return ResourceResult(data=data, errors=[], timings={})
