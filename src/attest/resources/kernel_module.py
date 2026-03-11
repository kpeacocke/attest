"""Kernel module resource (REQ-2.2): query loaded and available kernel modules."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from attest.resources.interfaces import ResourceResult


class KernelModuleResource:
    """Query loaded kernel modules and module blacklist status."""

    def query(self, params: dict[str, Any]) -> ResourceResult:
        name = params.get("name")
        field = params.get("field")

        if name is not None and (not isinstance(name, str) or not name.strip()):
            return ResourceResult(
                data=None,
                errors=["'kernel_module' resource parameter 'name' must be a non-empty string."],
                timings={},
            )

        if not shutil.which("lsmod"):
            return ResourceResult(
                data=None,
                errors=["'lsmod' command is not available on this host."],
                timings={},
            )

        completed = subprocess.run(
            ["lsmod"],
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or "lsmod failed"
            return ResourceResult(data=None, errors=[stderr], timings={})

        loaded_modules = self._parse_lsmod_output(completed.stdout)
        blacklist = self._read_module_blacklist()

        if name is not None:
            is_loaded = name in loaded_modules
            is_blacklisted = name in blacklist
            data = {
                "loaded": is_loaded,
                "blacklisted": is_blacklisted,
                "module_name": name,
            }
            return ResourceResult(data=data, errors=[], timings={})

        data = {
            "loaded_modules": sorted(loaded_modules),
            "loaded_count": len(loaded_modules),
            "blacklisted_modules": sorted(blacklist),
            "blacklisted_count": len(blacklist),
        }

        if isinstance(field, str):
            return ResourceResult(data=data.get(field), errors=[], timings={})
        return ResourceResult(data=data, errors=[], timings={})

    def _parse_lsmod_output(self, output: str) -> set[str]:
        modules: set[str] = set()
        for raw_line in output.splitlines()[1:]:  # Skip header
            line = raw_line.strip()
            if not line:
                continue

            parts = line.split(None, 1)
            if len(parts) >= 1:
                modules.add(parts[0])
        return modules

    def _read_module_blacklist(self) -> set[str]:
        blacklist: set[str] = set()
        blacklist_paths = [
            "/etc/modprobe.d/blacklist.conf",
            "/etc/modprobe.d/blacklist-oss.conf",
            "/etc/modprobe.d/blacklist-framebuffer.conf",
        ]

        for path_str in blacklist_paths:
            try:
                content = open(path_str, "r", encoding="utf-8").read()
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith("blacklist "):
                        module_name = line.split(None, 1)[1].strip()
                        blacklist.add(module_name)
            except (FileNotFoundError, IOError, OSError, IndexError):
                pass

        return blacklist
