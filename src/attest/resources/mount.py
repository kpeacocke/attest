"""Mount resource (REQ-2.2): query mounted filesystems with options."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from attest.resources.interfaces import ResourceResult


class MountResource:
    """Query mounted filesystems with deterministic filtering by mount point or device."""

    def query(self, params: dict[str, Any]) -> ResourceResult:
        mount_point = params.get("mount_point")
        device = params.get("device")
        field = params.get("field")

        if mount_point is not None and (
            not isinstance(mount_point, str) or not mount_point.strip()
        ):
            return ResourceResult(
                data=None,
                errors=["'mount' resource parameter 'mount_point' must be a non-empty string."],
                timings={},
            )

        if device is not None and (not isinstance(device, str) or not device.strip()):
            return ResourceResult(
                data=None,
                errors=["'mount' resource parameter 'device' must be a non-empty string."],
                timings={},
            )

        if not shutil.which("mount"):
            return ResourceResult(
                data=None,
                errors=["'mount' command is not available on this host."],
                timings={},
            )

        completed = subprocess.run(
            ["mount"],
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or "mount listing failed"
            return ResourceResult(data=None, errors=[stderr], timings={})

        mounts = self._parse_mount_output(completed.stdout)
        if mount_point is not None:
            mounts = [m for m in mounts if m["mount_point"] == mount_point]
        if device is not None:
            mounts = [m for m in mounts if m["device"] == device]

        mounts.sort(key=lambda m: str(m["mount_point"]))

        data = {
            "exists": bool(mounts),
            "count": len(mounts),
            "mounts": mounts,
        }

        if isinstance(field, str):
            return ResourceResult(data=data.get(field), errors=[], timings={})
        return ResourceResult(data=data, errors=[], timings={})

    def _parse_mount_output(self, output: str) -> list[dict[str, object]]:
        mounts: list[dict[str, object]] = []
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            parts = self._parse_mount_line(line)
            if parts is not None:
                mounts.append(parts)
        return mounts

    def _parse_mount_line(self, line: str) -> dict[str, object] | None:
        # Format: device on mount_point type fstype (options)
        if " on " not in line or " type " not in line:
            return None

        before_on = line.split(" on ", 1)[0].strip()
        after_on = line.split(" on ", 1)[1]

        if " type " not in after_on:
            return None

        mount_point = after_on.split(" type ", 1)[0].strip()
        after_type = after_on.split(" type ", 1)[1]

        parts = after_type.split(None, 1)
        if len(parts) < 1:
            return None

        fstype = parts[0]
        options_str = parts[1] if len(parts) > 1 else ""

        options: list[str] = []
        if options_str.startswith("(") and options_str.endswith(")"):
            options_str = options_str[1:-1]
            options = [opt.strip() for opt in options_str.split(",")]

        has_noexec = "noexec" in options
        has_nosuid = "nosuid" in options
        has_nodev = "nodev" in options

        return {
            "device": before_on,
            "mount_point": mount_point,
            "fstype": fstype,
            "options": options,
            "has_noexec": has_noexec,
            "has_nosuid": has_nosuid,
            "has_nodev": has_nodev,
        }
