"""Group resource (REQ-2.2): query group account information."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from attest.resources.interfaces import ResourceResult


class GroupResource:
    """Query local group accounts with gid and member list."""

    def query(self, params: dict[str, Any]) -> ResourceResult:
        groupname = params.get("name")
        field = params.get("field")

        if groupname is not None and (not isinstance(groupname, str) or not groupname.strip()):
            return ResourceResult(
                data=None,
                errors=["'group' resource parameter 'name' must be a non-empty string."],
                timings={},
            )

        if not shutil.which("getent"):
            return ResourceResult(
                data=None,
                errors=["'getent' command is not available on this host."],
                timings={},
            )

        if groupname is None:
            return ResourceResult(
                data=None,
                errors=["'group' resource requires a 'name' parameter."],
                timings={},
            )

        completed = subprocess.run(
            ["getent", "group", groupname],
            text=True,
            capture_output=True,
            check=False,
        )

        if completed.returncode != 0:
            return ResourceResult(
                data={
                    "exists": False,
                    "gid": None,
                    "members": [],
                },
                errors=[],
                timings={},
            )

        group_data = self._parse_group_line(completed.stdout.strip())
        if group_data is None:
            return ResourceResult(
                data=None,
                errors=["Failed to parse getent group output."],
                timings={},
            )

        group_data["exists"] = True

        if isinstance(field, str):
            return ResourceResult(data=group_data.get(field), errors=[], timings={})
        return ResourceResult(data=group_data, errors=[], timings={})

    def _parse_group_line(self, line: str) -> dict[str, object] | None:
        # Format: groupname:password:gid:members
        parts = line.split(":")
        if len(parts) < 4:
            return None

        try:
            gid = int(parts[2])
        except (ValueError, IndexError):
            return None

        members_str = parts[3].strip()
        members = [m.strip() for m in members_str.split(",") if m.strip()]

        return {
            "gid": gid,
            "members": sorted(members),
        }
