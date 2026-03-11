"""Tests for diff engine (REQ-6.2, REQ-7.3)."""

from __future__ import annotations

from pathlib import Path

from attest.diff.baseline import load_report, save_baseline
from attest.diff.differ import build_markdown_diff, diff_reports


def _report(run_id: str, statuses: dict[str, str], waivers: dict[str, str] | None = None) -> dict:
    waivers = waivers or {}
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "results": [
            {
                "control_id": cid,
                "status": status,
                **({"waiver_id": waivers[cid]} if cid in waivers else {}),
            }
            for cid, status in sorted(statuses.items(), key=lambda item: item[0])
        ],
    }


class TestDiffer:
    def test_new_failure_and_new_pass_detected(self) -> None:
        baseline = _report("a", {"C-1": "PASS", "C-2": "FAIL"})
        current = _report("b", {"C-1": "FAIL", "C-2": "PASS"})

        diff = diff_reports(baseline, current)

        assert diff["new_failures"] == ["C-1"]
        assert diff["new_passes"] == ["C-2"]

    def test_new_skip_and_error_detected(self) -> None:
        baseline = _report("a", {"C-1": "PASS", "C-2": "PASS"})
        current = _report("b", {"C-1": "SKIP", "C-2": "ERROR"})

        diff = diff_reports(baseline, current)

        assert diff["new_skips"] == ["C-1"]
        assert diff["new_errors"] == ["C-2"]

    def test_waiver_change_detected(self) -> None:
        baseline = _report("a", {"C-1": "FAIL"})
        current = _report("b", {"C-1": "WAIVED"}, waivers={"C-1": "W-001"})

        diff = diff_reports(baseline, current)

        assert diff["waiver_changes"] == [{"control_id": "C-1", "from": "none", "to": "W-001"}]

    def test_markdown_contains_sections(self) -> None:
        baseline = _report("a", {"C-1": "PASS"})
        current = _report("b", {"C-1": "FAIL"})
        diff = diff_reports(baseline, current)

        md = build_markdown_diff(diff)
        assert "Attest Drift Report" in md
        assert "New failures" in md


class TestBaselineStore:
    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        report = _report("run-1", {"C-1": "PASS"})
        path = save_baseline(report, tmp_path, name="baseline")

        loaded = load_report(path)
        assert loaded["run_id"] == "run-1"
        assert loaded["results"][0]["control_id"] == "C-1"
