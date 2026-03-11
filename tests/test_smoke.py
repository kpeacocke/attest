"""Smoke tests and CLI exit code tests (REQ-7.2, REQ-7.3)."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from attest.cli import main


# ---------------------------------------------------------------------------
# Version command
# ---------------------------------------------------------------------------

def test_version_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["version"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "attest" in out.lower()


# ---------------------------------------------------------------------------
# Validate command (REQ-7.1, REQ-7.2)
# ---------------------------------------------------------------------------

def _make_profile_dir(tmp_path: Path, profile_yaml: str, controls: dict[str, str] | None = None) -> Path:
    (tmp_path / "profile.yml").write_text(textwrap.dedent(profile_yaml), encoding="utf-8")
    if controls:
        ctrl_dir = tmp_path / "controls"
        ctrl_dir.mkdir()
        for name, content in controls.items():
            (ctrl_dir / name).write_text(textwrap.dedent(content), encoding="utf-8")
    return tmp_path


VALID_PROFILE_YAML = """
    name: test-profile
    title: Test Profile
    version: 1.0.0
"""

VALID_CONTROL_YAML = """
    id: LH-001
    title: SSH root login disabled
    tests:
      - name: check sshd
        resource: sshd_config
        operator: eq
        expected: "no"
"""


def test_validate_valid_profile_exits_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    profile_dir = _make_profile_dir(tmp_path, VALID_PROFILE_YAML, {"lh001.yml": VALID_CONTROL_YAML})
    rc = main(["validate", str(profile_dir)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "valid" in out.lower()


def test_validate_missing_profile_dir_exits_four(tmp_path: Path) -> None:
    rc = main(["validate", str(tmp_path / "nonexistent")])
    assert rc == 4


def test_validate_invalid_schema_exits_four(tmp_path: Path) -> None:
    # Profile name with spaces → schema validation failure → exit 4.
    bad_profile = "name: INVALID NAME\ntitle: T\nversion: 1.0\n"
    profile_dir = _make_profile_dir(tmp_path, bad_profile)
    rc = main(["validate", str(profile_dir)])
    assert rc == 4


# ---------------------------------------------------------------------------
# Run command (REQ-7.1, REQ-7.2)
# ---------------------------------------------------------------------------

def test_run_exits_three_for_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Bootstrap run with controls produces ERROR (no resource layer yet) → exit 3."""
    profile_dir = _make_profile_dir(tmp_path, VALID_PROFILE_YAML, {"lh001.yml": VALID_CONTROL_YAML})
    out_dir = tmp_path / "out"
    rc = main(["run", str(profile_dir), "--out", str(out_dir)])
    # Bootstrap: all controls produce ERROR (no resource collection).
    assert rc == 3


def test_run_writes_json_and_summary(tmp_path: Path) -> None:
    profile_dir = _make_profile_dir(tmp_path, VALID_PROFILE_YAML, {"lh001.yml": VALID_CONTROL_YAML})
    out_dir = tmp_path / "out"
    main(["run", str(profile_dir), "--out", str(out_dir)])
    assert (out_dir / "report.json").exists()
    assert (out_dir / "attest-summary.json").exists()


def test_run_all_formats(tmp_path: Path) -> None:
    profile_dir = _make_profile_dir(tmp_path, VALID_PROFILE_YAML, {"lh001.yml": VALID_CONTROL_YAML})
    out_dir = tmp_path / "out"
    main(
        [
            "run", str(profile_dir),
            "--out", str(out_dir),
            "--format", "json",
            "--format", "junit",
            "--format", "markdown",
            "--format", "summary",
        ]
    )
    assert (out_dir / "report.json").exists()
    assert (out_dir / "report.xml").exists()
    assert (out_dir / "report.md").exists()
    assert (out_dir / "attest-summary.json").exists()


def test_diff_exits_four(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["diff", "a.json", "b.json"])
    assert rc == 4
