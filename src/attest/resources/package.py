"""Package resource (REQ-2.2): installed state and version lookup."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from attest.resources.interfaces import ResourceResult


class PackageResource:
    """Query package installed state and version on Linux hosts."""

    def query(self, params: dict[str, Any]) -> ResourceResult:
        package_name = params.get("name")
        if not isinstance(package_name, str) or not package_name.strip():
            return ResourceResult(
                data=None,
                errors=["'package' resource requires a non-empty 'name' parameter."],
                timings={},
            )

        if shutil.which("dpkg-query"):
            return self._query_dpkg(package_name)

        if shutil.which("rpm"):
            return self._query_rpm(package_name)

        return ResourceResult(
            data=None,
            errors=["No supported package query tool found (expected dpkg-query or rpm)."],
            timings={},
        )

    def _query_dpkg(self, package_name: str) -> ResourceResult:
        cmd = ["dpkg-query", "-W", "-f=${Status} ${Version}", package_name]
        completed = subprocess.run(cmd, text=True, capture_output=True, check=False)

        if completed.returncode != 0:
            return ResourceResult(data={"installed": False, "version": None}, errors=[], timings={})

        output = completed.stdout.strip()
        installed = output.startswith("install ok installed")
        version = output.split()[-1] if output else None
        return ResourceResult(
            data={"installed": installed, "version": version},
            errors=[],
            timings={},
        )

    def _query_rpm(self, package_name: str) -> ResourceResult:
        cmd = ["rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}", package_name]
        completed = subprocess.run(cmd, text=True, capture_output=True, check=False)

        if completed.returncode != 0:
            return ResourceResult(data={"installed": False, "version": None}, errors=[], timings={})

        version = completed.stdout.strip() or None
        return ResourceResult(
            data={"installed": True, "version": version},
            errors=[],
            timings={},
        )
