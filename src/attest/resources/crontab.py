"""Crontab resource (REQ-2.2): query user and system crontab entries."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from attest.resources.interfaces import ResourceResult


class CrontabResource:
    """Query user and system crontab entries deterministically."""

    def query(self, params: dict[str, Any]) -> ResourceResult:
        username = params.get("username")
        search_field = params.get("search")
        field = params.get("field")

        if username is not None and (not isinstance(username, str) or not username.strip()):
            return ResourceResult(
                data=None,
                errors=["'crontab' resource parameter 'username' must be a non-empty string."],
                timings={},
            )

        user_crontabs = self._read_user_crontabs(username)
        system_crontabs = self._read_system_crontabs()

        all_entries = sorted(
            user_crontabs + system_crontabs, key=lambda e: (e["source"], e["line"])
        )

        if search_field is not None and isinstance(search_field, str):
            all_entries = [e for e in all_entries if search_field.lower() in e["full_line"].lower()]

        data = {
            "entries": all_entries,
            "count": len(all_entries),
            "user_count": len(user_crontabs),
            "system_count": len(system_crontabs),
        }

        if isinstance(field, str):
            return ResourceResult(data=data.get(field), errors=[], timings={})
        return ResourceResult(data=data, errors=[], timings={})

    def _read_user_crontabs(self, username: str | None) -> list[dict[str, object]]:
        entries: list[dict[str, object]] = []

        if username is not None:
            usernames = [username]
        else:
            usernames = self._list_crontab_users()

        for user in usernames:
            crontab_entries = self._read_user_crontab(user)
            entries.extend(crontab_entries)

        return entries

    def _read_user_crontab(self, username: str) -> list[dict[str, object]]:
        entries: list[dict[str, object]] = []
        completed = subprocess.run(
            ["crontab", "-u", username, "-l"],
            text=True,
            capture_output=True,
            check=False,
        )

        if completed.returncode != 0:
            return entries

        for line_num, line in enumerate(completed.stdout.splitlines(), 1):
            cleaned = line.rstrip()
            if cleaned and not cleaned.lstrip().startswith("#"):
                entries.append(
                    {
                        "source": f"user:{username}",
                        "username": username,
                        "type": "user",
                        "line": line_num,
                        "full_line": cleaned,
                    }
                )

        return entries

    def _list_crontab_users(self) -> list[str]:
        users: list[str] = []
        spool_path = Path("/var/spool/cron/crontabs")
        if spool_path.exists():
            try:
                for item in sorted(spool_path.iterdir()):
                    if item.is_file():
                        users.append(item.name)
            except OSError:
                pass
        return users

    def _iter_cron_files(self, cron_dir: Path) -> list[Path]:
        """Return sorted regular files in a cron directory, or an empty list on errors."""
        try:
            return [path for path in sorted(cron_dir.glob("*")) if path.is_file()]
        except OSError:
            return []

    def _read_cron_file_entries(self, cron_dir: Path, cron_file: Path) -> list[dict[str, object]]:
        """Parse one cron file into deterministic entry rows."""
        try:
            content = cron_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []

        entries: list[dict[str, object]] = []
        for line_num, line in enumerate(content.splitlines(), 1):
            cleaned = line.rstrip()
            if cleaned and not cleaned.lstrip().startswith("#"):
                entries.append(
                    {
                        "source": f"system:{cron_file.name}",
                        "filename": cron_file.name,
                        "directory": str(cron_dir),
                        "type": "system",
                        "line": line_num,
                        "full_line": cleaned,
                    }
                )
        return entries

    def _read_system_crontabs(self) -> list[dict[str, object]]:
        entries: list[dict[str, object]] = []
        cron_dirs = [
            Path("/etc/cron.d"),
            Path("/etc/cron.daily"),
            Path("/etc/cron.hourly"),
            Path("/etc/cron.monthly"),
            Path("/etc/cron.weekly"),
        ]

        for cron_dir in cron_dirs:
            if not cron_dir.exists():
                continue

            for cron_file in self._iter_cron_files(cron_dir):
                entries.extend(self._read_cron_file_entries(cron_dir, cron_file))

        return entries
