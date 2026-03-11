"""Process resource (REQ-2.2): query running processes on Linux hosts."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from attest.resources.interfaces import ResourceResult


class ProcessResource:
    """Query running processes with deterministic filtering and projection."""

    def query(self, params: dict[str, Any]) -> ResourceResult:
        name = params.get("name")
        pid = params.get("pid")
        field = params.get("field")

        if name is not None and (not isinstance(name, str) or not name.strip()):
            return ResourceResult(
                data=None,
                errors=["'process' resource parameter 'name' must be a non-empty string."],
                timings={},
            )

        parsed_pid = self._parse_pid(pid)
        if parsed_pid is None and pid is not None:
            return ResourceResult(
                data=None,
                errors=["'process' resource parameter 'pid' must be an integer."],
                timings={},
            )

        if not shutil.which("ps"):
            return ResourceResult(
                data=None,
                errors=["'ps' command is not available on this host."],
                timings={},
            )

        completed = subprocess.run(
            ["ps", "-eo", "pid=,user=,comm="],
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or "process listing failed"
            return ResourceResult(data=None, errors=[stderr], timings={})

        processes = self._parse_ps_output(completed.stdout)
        if name is not None:
            processes = [proc for proc in processes if proc["name"] == name]
        if parsed_pid is not None:
            processes = [proc for proc in processes if proc["pid"] == parsed_pid]

        processes.sort(key=lambda proc: (int(proc["pid"]), str(proc["name"])))

        data = {
            "exists": bool(processes),
            "count": len(processes),
            "pids": [proc["pid"] for proc in processes],
            "users": sorted({str(proc["user"]) for proc in processes}),
            "processes": processes,
        }

        if isinstance(field, str):
            return ResourceResult(data=data.get(field), errors=[], timings={})
        return ResourceResult(data=data, errors=[], timings={})

    def _parse_pid(self, pid: Any) -> int | None:
        if pid is None:
            return None
        if isinstance(pid, bool):
            return None
        if isinstance(pid, int):
            return pid
        if isinstance(pid, str) and pid.strip().isdigit():
            return int(pid.strip())
        return None

    def _parse_ps_output(self, output: str) -> list[dict[str, object]]:
        processes: list[dict[str, object]] = []
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            parts = line.split(None, 2)
            if len(parts) != 3 or not parts[0].isdigit():
                continue

            pid = int(parts[0])
            user = parts[1]
            name = parts[2]
            processes.append(
                {
                    "pid": pid,
                    "user": user,
                    "name": name,
                    "capabilities": self._read_capabilities(pid),
                }
            )
        return processes

    def _read_capabilities(self, pid: int) -> str | None:
        status_path = Path("/proc") / str(pid) / "status"
        try:
            lines = status_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return None

        for line in lines:
            if line.startswith("CapEff:"):
                return line.partition(":")[2].strip() or None
        return None
