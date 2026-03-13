"""Smoke tests and CLI exit code tests (REQ-7.1, REQ-7.2, REQ-7.3, REQ-8.1)."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from attest.cli import main


def test_version_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["version"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "attest" in out.lower()


def _make_profile_dir(
    tmp_path: Path, profile_yaml: str, controls: dict[str, str] | None = None
) -> Path:
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

ERROR_CONTROL_YAML = """
    id: LH-001
    title: SSH root login disabled
    tests:
      - name: check sshd
        resource: sshd_config
        operator: eq
        expected: "no"
"""

PASSING_CONTROL_YAML = """
    id: OS-001
    title: OS facts available
    tests:
      - name: system fact exists
        resource: os_facts
        operator: exists
        params:
          field: system
"""


def test_validate_valid_profile_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    profile_dir = _make_profile_dir(tmp_path, VALID_PROFILE_YAML, {"lh001.yml": ERROR_CONTROL_YAML})
    rc = main(["validate", str(profile_dir)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "valid" in out.lower()


def test_validate_missing_profile_dir_exits_four(tmp_path: Path) -> None:
    rc = main(["validate", str(tmp_path / "nonexistent")])
    assert rc == 4


def test_validate_invalid_schema_exits_four(tmp_path: Path) -> None:
    bad_profile = "name: INVALID NAME\ntitle: T\nversion: 1.0\n"
    profile_dir = _make_profile_dir(tmp_path, bad_profile)
    rc = main(["validate", str(profile_dir)])
    assert rc == 4


def test_run_exits_three_for_unknown_resource(tmp_path: Path) -> None:
    profile_dir = _make_profile_dir(tmp_path, VALID_PROFILE_YAML, {"lh001.yml": ERROR_CONTROL_YAML})
    out_dir = tmp_path / "out"
    rc = main(["run", str(profile_dir), "--out", str(out_dir)])
    assert rc == 3


def test_run_exits_zero_for_passing_builtin_resource(tmp_path: Path) -> None:
    profile_dir = _make_profile_dir(
        tmp_path, VALID_PROFILE_YAML, {"os001.yml": PASSING_CONTROL_YAML}
    )
    out_dir = tmp_path / "out"
    rc = main(["run", str(profile_dir), "--out", str(out_dir)])
    assert rc == 0


def test_run_writes_json_and_summary(tmp_path: Path) -> None:
    profile_dir = _make_profile_dir(
        tmp_path, VALID_PROFILE_YAML, {"os001.yml": PASSING_CONTROL_YAML}
    )
    out_dir = tmp_path / "out"
    main(["run", str(profile_dir), "--out", str(out_dir)])
    assert (out_dir / "report.json").exists()
    assert (out_dir / "attest-summary.json").exists()


def test_run_all_formats(tmp_path: Path) -> None:
    profile_dir = _make_profile_dir(
        tmp_path, VALID_PROFILE_YAML, {"os001.yml": PASSING_CONTROL_YAML}
    )
    out_dir = tmp_path / "out"
    main(
        [
            "run",
            str(profile_dir),
            "--out",
            str(out_dir),
            "--format",
            "json",
            "--format",
            "junit",
            "--format",
            "markdown",
            "--format",
            "summary",
        ]
    )
    assert (out_dir / "report.json").exists()
    assert (out_dir / "report.xml").exists()
    assert (out_dir / "report.md").exists()
    assert (out_dir / "attest-summary.json").exists()


def test_run_applies_waivers_from_profile_dir(tmp_path: Path) -> None:
    failing_control_yaml = """
        id: LH-001
        title: OS fact mismatch
        tests:
          - name: check system fact
            resource: os_facts
            operator: eq
            expected: definitely-not-linux
            params:
              field: system
    """
    profile_dir = _make_profile_dir(
        tmp_path,
        VALID_PROFILE_YAML,
        {"lh001.yml": failing_control_yaml},
    )
    (profile_dir / "waivers.yml").write_text(
        textwrap.dedent(
            """
            waivers:
              - id: W-001
                control_id: LH-001
                justification: Accepted beta exception
                owner: platform
                expiry: 2099-01-01
            """
        ),
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    rc = main(["run", str(profile_dir), "--out", str(out_dir)])

    report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
    assert rc == 0
    assert report["results"][0]["status"] == "WAIVED"
    assert report["results"][0]["waiver_id"] == "W-001"


def test_run_invalid_waiver_file_exits_four(tmp_path: Path) -> None:
    profile_dir = _make_profile_dir(
        tmp_path, VALID_PROFILE_YAML, {"os001.yml": PASSING_CONTROL_YAML}
    )
    waiver_path = tmp_path / "waivers.yml"
    waiver_path.write_text("waivers: not-a-list\n", encoding="utf-8")

    rc = main(["run", str(profile_dir), "--waivers", str(waiver_path)])
    assert rc == 4


def test_diff_exits_four_for_missing_files() -> None:
    rc = main(["diff", "a.json", "b.json"])
    assert rc == 4


def test_diff_writes_outputs_and_returns_zero(tmp_path: Path) -> None:
    baseline = {
        "schema_version": "1.0",
        "run_id": "a",
        "results": [{"control_id": "C-1", "status": "PASS"}],
    }
    current = {
        "schema_version": "1.0",
        "run_id": "b",
        "results": [{"control_id": "C-1", "status": "PASS"}],
    }
    a_path = tmp_path / "a.json"
    b_path = tmp_path / "b.json"
    out_dir = tmp_path / "out"
    a_path.write_text(json.dumps(baseline), encoding="utf-8")
    b_path.write_text(json.dumps(current), encoding="utf-8")
    rc = main(["diff", str(a_path), str(b_path), "--out", str(out_dir)])
    assert rc == 0
    assert (out_dir / "diff.json").exists()
    assert (out_dir / "diff.md").exists()


def test_diff_returns_two_when_new_failures(tmp_path: Path) -> None:
    baseline = {
        "schema_version": "1.0",
        "run_id": "a",
        "results": [{"control_id": "C-1", "status": "PASS"}],
    }
    current = {
        "schema_version": "1.0",
        "run_id": "b",
        "results": [{"control_id": "C-1", "status": "FAIL"}],
    }
    a_path = tmp_path / "a.json"
    b_path = tmp_path / "b.json"
    a_path.write_text(json.dumps(baseline), encoding="utf-8")
    b_path.write_text(json.dumps(current), encoding="utf-8")
    rc = main(["diff", str(a_path), str(b_path), "--out", str(tmp_path / "out")])
    assert rc == 2


# ---------------------------------------------------------------------------
# REQ-7.1: --inventory / -i flag
# ---------------------------------------------------------------------------


def test_run_inventory_flag_sets_host_label(tmp_path: Path) -> None:
    """REQ-7.1: -i/--inventory accepted; first entry used as host label in report."""
    profile_dir = _make_profile_dir(
        tmp_path, VALID_PROFILE_YAML, {"os001.yml": PASSING_CONTROL_YAML}
    )
    out_dir = tmp_path / "out"
    rc = main(["run", str(profile_dir), "--out", str(out_dir), "-i", "myhost"])
    assert rc == 0
    report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
    assert report["host"] == "myhost"


def test_run_inventory_list_uses_first_host(tmp_path: Path) -> None:
    """REQ-7.1: comma-separated inventory uses the first entry as the run host."""
    profile_dir = _make_profile_dir(
        tmp_path, VALID_PROFILE_YAML, {"os001.yml": PASSING_CONTROL_YAML}
    )
    out_dir = tmp_path / "out"
    rc = main(["run", str(profile_dir), "--out", str(out_dir), "--inventory", "alpha,beta,gamma"])
    assert rc == 0
    report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
    assert report["host"] == "alpha"


# ---------------------------------------------------------------------------
# REQ-7.2: additional exit code scenarios
# ---------------------------------------------------------------------------


def test_run_exits_zero_for_waived_only(tmp_path: Path) -> None:
    """REQ-7.2: a run where all failures are waived exits 0 (WAIVED allowed)."""
    failing_control_yaml = """
        id: LH-002
        title: Waived failing control
        tests:
          - name: check system fact (fail)
            resource: os_facts
            operator: eq
            expected: definitely-not-linux
            params:
              field: system
    """
    profile_dir = _make_profile_dir(
        tmp_path,
        VALID_PROFILE_YAML,
        {"lh002.yml": failing_control_yaml},
    )
    (profile_dir / "waivers.yml").write_text(
        textwrap.dedent(
            """
            waivers:
              - id: W-002
                control_id: LH-002
                justification: Accepted for testing
                owner: platform
                expiry: 2099-01-01
            """
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    rc = main(["run", str(profile_dir), "--out", str(out_dir)])
    assert rc == 0


def test_run_exits_two_for_fail(tmp_path: Path) -> None:
    """REQ-7.2: any FAIL present -> exit 2."""
    failing_control_yaml = """
        id: LH-003
        title: Always fails
        tests:
          - name: impossible check
            resource: os_facts
            operator: eq
            expected: not-linux
            params:
              field: system
    """
    profile_dir = _make_profile_dir(
        tmp_path, VALID_PROFILE_YAML, {"lh003.yml": failing_control_yaml}
    )
    rc = main(["run", str(profile_dir), "--out", str(tmp_path / "out")])
    assert rc == 2


# ---------------------------------------------------------------------------
# REQ-8.1: actionable terminal output on failures
# ---------------------------------------------------------------------------


def test_run_prints_failure_details_to_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """REQ-8.1: terminal output includes control id and values on failure."""
    failing_control_yaml = """
        id: LH-004
        title: Always fails
        tests:
          - name: impossible check
            resource: os_facts
            operator: eq
            expected: not-linux
            params:
              field: system
    """
    profile_dir = _make_profile_dir(
        tmp_path, VALID_PROFILE_YAML, {"lh004.yml": failing_control_yaml}
    )
    main(["run", str(profile_dir), "--out", str(tmp_path / "out")])
    out = capsys.readouterr().out
    # Control id must appear in the terminal output for operator triage.
    assert "LH-004" in out
    # Expected value should appear for quick diagnosis.
    assert "not-linux" in out
