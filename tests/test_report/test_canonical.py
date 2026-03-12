"""Tests for canonical report builder (REQ-4.1, REQ-7.4)."""

from __future__ import annotations

import json

import pytest


from attest.engine.result import ControlResult, ControlStatus, TestEvidence
from attest.policy.schemas import Control, ControlTags, Profile, TestAssertion
from attest.report.canonical import SCHEMA_VERSION, build_report


def _profile() -> Profile:
    return Profile(name="test-profile", title="Test", version="1.0.0")


def _control(cid: str = "LH-001", impact: float = 0.7) -> Control:
    return Control(
        id=cid,
        title="Test control",
        impact=impact,
        tags=ControlTags(nist=["AC-3"], cis_level=1),
        tests=[TestAssertion(name="t1", resource="r", operator="eq", expected="x")],
    )


def _result(cid: str = "LH-001", status: ControlStatus = ControlStatus.PASS) -> ControlResult:
    return ControlResult(
        control_id=cid,
        status=status,
        tests=[
            TestEvidence(
                name="t1",
                resource="r",
                operator="eq",
                expected="x",
                actual="x",
                status=status,
            )
        ],
    )


class TestBuildReport:
    def test_schema_version(self) -> None:
        report = build_report(_profile(), [_control()], [_result()])
        assert report["schema_version"] == SCHEMA_VERSION

    def test_results_sorted_by_control_id(self) -> None:
        controls = [_control("ZZ-001"), _control("AA-001")]
        results = [_result("ZZ-001"), _result("AA-001")]
        report = build_report(_profile(), controls, results, run_id="test-run")
        ids = [r["control_id"] for r in report["results"]]
        assert ids == ["AA-001", "ZZ-001"]

    def test_pass_counts(self) -> None:
        report = build_report(_profile(), [_control()], [_result(status=ControlStatus.PASS)])
        assert report["summary"]["counts"]["PASS"] == 1
        assert report["summary"]["counts"]["FAIL"] == 0

    def test_fail_risk_score(self) -> None:
        ctrl = _control(impact=1.0)
        result = _result(status=ControlStatus.FAIL)
        report = build_report(_profile(), [ctrl], [result])
        assert report["summary"]["risk_score"] == pytest.approx(1.0)

    def test_tag_summaries_nist(self) -> None:
        report = build_report(_profile(), [_control()], [_result(status=ControlStatus.PASS)])
        assert "AC-3" in report["tag_summaries"]["nist"]

    def test_deterministic_run_id(self) -> None:
        r1 = build_report(_profile(), [_control()], [_result()], run_id="fixed-id")
        r2 = build_report(_profile(), [_control()], [_result()], run_id="fixed-id")
        # Timestamps will differ; everything else should match.
        r1["timestamp"] = r2["timestamp"] = "T"
        assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)

    def test_overlay_provenance_in_result(self) -> None:
        result = ControlResult(
            control_id="LH-001",
            status=ControlStatus.PASS,
            tests=[],
            overlay_source="my-overlay",
            original_impact=0.5,
        )
        report = build_report(_profile(), [_control()], [result])
        entry = report["results"][0]
        assert entry["overlay_source"] == "my-overlay"
        assert entry["original_impact"] == pytest.approx(0.5)
