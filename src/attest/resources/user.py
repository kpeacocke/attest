"""User resource (REQ-2.2): query user account information."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from attest.resources.interfaces import ResourceResult


class UserResource:
    """Query local user accounts with uid, gid, shell, and home directory."""

    def query(self, params: dict[str, Any]) -> ResourceResult:
        username = params.get("name")
        field = params.get("field")

        if username is not None and (not isinstance(username, str) or not username.strip()):
            return ResourceResult(
                data=None,
                errors=["'user' resource parameter 'name' must be a non-empty string."],
                timings={},
            )

        if not shutil.which("getent"):
            return ResourceResult(
                data=None,
                errors=["'getent' command is not available on this host."],
                timings={},
            )

        if username is None:
            return ResourceResult(
                data=None,
                errors=["'user' resource requires a 'name' parameter."],
                timings={},
            )

        completed = subprocess.run(
            ["getent", "passwd", username],
            text=True,
            capture_output=True,
            check=False,
        )

        if completed.returncode != 0:
            return ResourceResult(
                data={
                    "exists": False,
                    "uid": None,
                    "gid": None,
                    "shell": None,
                    "home": None,
                    "groups": [],
                },
                errors=[],
                timings={},
            )

        user_data = self._parse_passwd_line(completed.stdout.strip())
        if user_data is None:
            return ResourceResult(
                data=None,
                errors=["Failed to parse getent passwd output."],
                timings={},
            )

        user_data["exists"] = True
        user_data["groups"] = self._get_group_membership(username)

        if isinstance(field, str):
            return ResourceResult(data=user_data.get(field), errors=[], timings={})
        return ResourceResult(data=user_data, errors=[], timings={})

    def _parse_passwd_line(self, line: str) -> dict[str, object] | None:
        # Format: username:password:uid:gid:gecos:home:shell
        parts = line.split(":")
        if len(parts) < 7:
            return None

        try:
            uid = int(parts[2])
            gid = int(parts[3])
        except (ValueError, IndexError):
            return None

        return {
            "uid": uid,
            "gid": gid,
            "shell": parts[6],
            "home": parts[5],
        }

    def _get_group_membership(self, username: str) -> list[str]:
        completed = subprocess.run(
            ["groups", username],
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            return []

        output = completed.stdout.strip()
        if ":" not in output:
            return []

        groups_part = output.split(":", 1)[1].strip()
        return sorted(groups_part.split())
