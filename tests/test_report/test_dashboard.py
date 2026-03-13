"""Tests for dashboard analytics and viewer outputs (REQ-9.1 to REQ-9.8)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from attest.report.dashboard import (
    build_alerts,
    build_audit_pack,
    build_dashboard_dataset,
    evaluate_slos,
)
from attest.report.dashboard_html import build_dashboard_html


def _result(
    control_id: str,
    status: str,
    *,
    impact: float = 0.5,
    nist: list[str] | None = None,
    cis_level: int | None = None,
    stig: str | None = None,
    waiver: dict | None = None,
    waiver_id: str | None = None,
    waiver_expired: bool = False,
) -> dict:
    row = {
        "control_id": control_id,
        "title": f"Control {control_id}",
        "status": status,
        "impact": impact,
        "tags": {
            "nist": nist or [],
            "cis_level": cis_level,
            "stig_severity": stig,
            "custom": [],
        },
        "tests": [
            {
                "name": "check",
                "status": status,
                "expected": "x",
                "actual": "y",
                "message": "mismatch",
            }
        ],
    }
    if waiver is not None:
        row["waiver"] = waiver
    if waiver_id:
        row["waiver_id"] = waiver_id
    if waiver_expired:
        row["waiver_expired"] = True
    return row


def _run(
    run_id: str, timestamp: str, *, risk: float, results: list[dict], host: str = "host-a"
) -> dict:
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    error_count = sum(1 for r in results if r["status"] == "ERROR")
    skip_count = sum(1 for r in results if r["status"] == "SKIP")
    waived_count = sum(1 for r in results if r["status"] == "WAIVED")
    return {
        "run_id": run_id,
        "timestamp": timestamp,
        "profile": {"name": "bench", "title": "Benchmark", "version": "1.0"},
        "host": host,
        "environment": "prod",
        "summary": {
            "counts": {
                "PASS": pass_count,
                "FAIL": fail_count,
                "ERROR": error_count,
                "SKIP": skip_count,
                "WAIVED": waived_count,
            },
            "risk_score": risk,
        },
        "results": results,
    }


class TestDashboardDataset:
    def test_build_dataset_contains_required_sections(self) -> None:
        now = datetime.now(tz=timezone.utc)
        reports = [
            _run(
                "r1",
                (now - timedelta(minutes=5)).isoformat(),
                risk=0.1,
                results=[_result("C-1", "PASS", nist=["AC-3"], cis_level=1, stig="CAT II")],
            ),
            _run(
                "r2",
                now.isoformat(),
                risk=1.2,
                results=[
                    _result("C-1", "FAIL", impact=0.95, nist=["AC-3"], cis_level=1, stig="CAT II")
                ],
            ),
        ]

        dataset = build_dashboard_dataset(reports)
        assert dataset["latest_run_id"] == "r2"
        assert "posture_trends" in dataset
        assert "waiver_board" in dataset
        assert "framework_rollups" in dataset
        assert "triage" in dataset

    def test_waiver_board_classifies_expiring_and_expired(self) -> None:
        now = datetime.now(tz=timezone.utc)
        reports = [
            _run(
                "r2",
                now.isoformat(),
                risk=0.2,
                results=[
                    _result(
                        "C-1",
                        "WAIVED",
                        waiver={
                            "id": "W-A",
                            "owner": "team-a",
                            "expiry": (now + timedelta(days=5)).isoformat(),
                        },
                        waiver_id="W-A",
                    ),
                    _result(
                        "C-2",
                        "FAIL",
                        waiver={
                            "id": "W-B",
                            "owner": "team-b",
                            "expiry": (now - timedelta(days=1)).isoformat(),
                        },
                        waiver_id="W-B",
                        waiver_expired=True,
                    ),
                ],
            )
        ]

        board = build_dashboard_dataset(reports)["waiver_board"]
        assert any(row["waiver_id"] == "W-A" for row in board["expiring"])
        assert any(row["waiver_id"] == "W-B" for row in board["expired"])

    def test_top_regressions_ranked_by_score(self) -> None:
        now = datetime.now(tz=timezone.utc)
        reports = [
            _run(
                "r1",
                (now - timedelta(minutes=10)).isoformat(),
                risk=0.0,
                results=[
                    _result("C-1", "PASS", impact=0.95),
                    _result("C-2", "PASS", impact=0.5),
                ],
            ),
            _run(
                "r2",
                now.isoformat(),
                risk=1.0,
                results=[
                    _result("C-1", "FAIL", impact=0.95),
                    _result("C-2", "FAIL", impact=0.5),
                ],
            ),
        ]

        top = build_dashboard_dataset(reports)["triage"]["top_regressions"]
        assert top[0]["control_id"] == "C-1"
        assert top[0]["score"] >= top[1]["score"]


class TestDashboardExportsAndAlerts:
    def test_build_audit_pack_applies_scope(self) -> None:
        now = datetime.now(tz=timezone.utc)
        dataset = build_dashboard_dataset(
            [_run("r1", now.isoformat(), risk=0.1, results=[_result("C-1", "PASS", nist=["AC-3"])])]
        )

        pack = build_audit_pack(dataset, framework="nist")
        assert pack["scope"]["framework"] == "nist"
        assert pack["runs"][0]["results"][0]["control_id"] == "C-1"

    def test_build_alerts_contains_risk_spike(self) -> None:
        now = datetime.now(tz=timezone.utc)
        dataset = build_dashboard_dataset(
            [
                _run(
                    "r1",
                    (now - timedelta(minutes=5)).isoformat(),
                    risk=0.1,
                    results=[_result("C-1", "PASS")],
                ),
                _run(
                    "r2", now.isoformat(), risk=1.0, results=[_result("C-1", "FAIL", impact=0.95)]
                ),
            ]
        )
        alerts = build_alerts(dataset, risk_spike_threshold=0.5)
        types = {row["type"] for row in alerts["alerts"]}
        assert "risk_score_spike" in types
        assert "new_critical_failure" in types

    def test_slo_report_shape(self) -> None:
        now = datetime.now(tz=timezone.utc)
        dataset = build_dashboard_dataset(
            [
                _run("r1", now.isoformat(), risk=0.1, results=[_result("C-1", "PASS")]),
            ]
        )
        slo = evaluate_slos(dataset)
        assert "metrics" in slo
        assert "targets" in slo
        assert "passes" in slo


class TestDashboardHtml:
    def test_html_contains_required_views(self) -> None:
        now = datetime.now(tz=timezone.utc)
        dataset = build_dashboard_dataset(
            [
                _run("r1", now.isoformat(), risk=0.1, results=[_result("C-1", "PASS")]),
            ]
        )
        html = build_dashboard_html(dataset)
        assert "Posture trends" in html
        assert "Waiver governance board" in html
        assert "Control evidence drill-down" in html
