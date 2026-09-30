"""Compare package and CLI container outputs for a deterministic profile (REQ-10.5)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from difflib import unified_diff
from pathlib import Path
from typing import Any

REPORT_JSON = "report.json"


def _normalise(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalise(item)
            for key, item in value.items()
            if key not in {"run_id", "timestamp", "generated_at", "latest_run_id", "freshness_seconds"}
        }
    if isinstance(value, list):
        return [_normalise(item) for item in value]
    return value


def _run(*args: str, env: dict[str, str] | None = None) -> None:
    subprocess.run(args, check=True, text=True, env=env)


def _volatile_values(value: Any) -> set[str]:
    if isinstance(value, dict):
        values = {
            str(item)
            for key, item in value.items()
            if key in {"run_id", "timestamp", "generated_at", "latest_run_id"} and item
        }
        for item in value.values():
            values.update(_volatile_values(item))
        return values
    if isinstance(value, list):
        return set().union(*(_volatile_values(item) for item in value))
    return set()


def _normalised_text(path: Path, report: dict[str, Any], dashboard: dict[str, Any]) -> str:
    text = path.read_text(encoding="utf-8")
    for value in sorted(_volatile_values(report) | _volatile_values(dashboard), key=len, reverse=True):
        text = text.replace(value, "[VOLATILE]")
    return text


def main() -> None:
    package_cli = shutil.which("attest")
    if package_cli is None:
        raise RuntimeError("Install the Attest wheel or run this check inside 'poetry run'.")

    image = os.environ.get("ATTEST_CLI_IMAGE", "attest-cli:scan")
    with tempfile.TemporaryDirectory(prefix="attest-parity-") as temporary:
        root = Path(temporary)
        profile = root / "profile"
        profile.mkdir()
        (profile / "controls").mkdir()
        (profile / "profile.yml").write_text(
            "name: parity\ntitle: Package and container parity\nversion: 1.0.0\n",
            encoding="utf-8",
        )
        (profile / "controls" / "file.yml").write_text(
            "id: PARITY-1\ntitle: Missing test file\n"
            "tests:\n  - name: absent path\n    resource: file\n"
            "    operator: eq\n    expected: false\n"
            "    params:\n      path: /tmp/attest-parity-missing\n      field: exists\n",
            encoding="utf-8",
        )

        package_out = root / "package"
        container_out = root / "container"
        package_out.mkdir()
        container_out.mkdir()
        container_out.chmod(0o777)

        formats = ["json", "junit", "markdown", "summary", "html"]
        format_args = [part for format_name in formats for part in ("--format", format_name)]
        _run(package_cli, "run", str(profile), "--out", str(package_out), "--host", "parity", *format_args)
        _run(
            "docker", "run", "--rm", "--mount", f"type=bind,source={profile},target=/input,readonly",
            "--mount", f"type=bind,source={container_out},target=/out",
            image, "run", "/input", "--out", "/out", "--host", "parity", *format_args,
        )

        package_report = json.loads((package_out / REPORT_JSON).read_text(encoding="utf-8"))
        container_report = json.loads((container_out / REPORT_JSON).read_text(encoding="utf-8"))
        assert _normalise(package_report) == _normalise(container_report)

        for package_dir, report in ((package_out, package_report), (container_out, container_report)):
            if package_dir == package_out:
                _run(package_cli, "dashboard", "build", str(package_dir / REPORT_JSON), "--out", str(package_dir))
            else:
                _run(
                    "docker", "run", "--rm",
                    "--mount", f"type=bind,source={package_dir},target=/out",
                    image, "dashboard", "build", "/out/report.json", "--out", "/out",
                )

        package_dashboard = json.loads((package_out / "dashboard.json").read_text(encoding="utf-8"))
        container_dashboard = json.loads((container_out / "dashboard.json").read_text(encoding="utf-8"))
        assert _normalise(package_dashboard) == _normalise(container_dashboard)

        for name in ("attest-summary.json", "dashboard-alerts.json", "dashboard-slo.json"):
            package_data = json.loads((package_out / name).read_text(encoding="utf-8"))
            container_data = json.loads((container_out / name).read_text(encoding="utf-8"))
            assert _normalise(package_data) == _normalise(container_data), name

        for name in ("report.xml", "report.md", "report.html", "dashboard.html"):
            package_text = _normalised_text(package_out / name, package_report, package_dashboard)
            container_text = _normalised_text(container_out / name, container_report, container_dashboard)
            if package_text != container_text:
                difference = unified_diff(package_text.splitlines(), container_text.splitlines())
                raise AssertionError(f"{name} parity mismatch:\n" + "\n".join(list(difference)[:24]))

        compose = Path(__file__).resolve().parents[1] / "compose.yaml"
        compose_args = ("docker", "compose", "-p", root.name, "-f", str(compose))
        compose_env = {
            **os.environ,
            "ATTEST_DASHBOARD_DIR": str(container_out),
            "ATTEST_DASHBOARD_IMAGE": os.environ.get("ATTEST_DASHBOARD_IMAGE", "attest-dashboard:scan"),
            "ATTEST_DASHBOARD_PORT": "0",
        }
        try:
            _run(*compose_args, "up", "--detach", "--wait", "--wait-timeout", "60", env=compose_env)
        finally:
            _run(*compose_args, "down", env=compose_env)

    print("Package and container report parity passed.")


if __name__ == "__main__":
    main()