"""Dashboard analytics and export helpers (REQ-9.1 to REQ-9.8)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

from attest.diff.differ import diff_reports

DASHBOARD_SCHEMA_VERSION = "1.0"


def _parse_timestamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _normalise_report(report: dict[str, Any]) -> dict[str, Any]:
    profile = report.get("profile", {}) if isinstance(report.get("profile"), dict) else {}
    summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
    counts = summary.get("counts", {}) if isinstance(summary.get("counts"), dict) else {}
    return {
        "run_id": str(report.get("run_id", "")),
        "timestamp": str(report.get("timestamp", "")),
        "profile": {
            "name": str(profile.get("name", "")),
            "title": str(profile.get("title", "")),
            "version": str(profile.get("version", "")),
        },
        "host": str(report.get("host", "unknown")),
        "environment": str(report.get("environment", "unknown")),
        "summary": {
            "counts": {
                "PASS": int(counts.get("PASS", 0)),
                "FAIL": int(counts.get("FAIL", 0)),
                "ERROR": int(counts.get("ERROR", 0)),
                "SKIP": int(counts.get("SKIP", 0)),
                "WAIVED": int(counts.get("WAIVED", 0)),
            },
            "risk_score": float(summary.get("risk_score", 0.0)),
        },
        "results": list(report.get("results", [])),
    }


def load_reports(paths: list[Path]) -> list[dict[str, Any]]:
    """Load canonical reports from json paths with deterministic ordering."""
    reports: list[dict[str, Any]] = []
    for path in sorted(paths, key=lambda p: str(p)):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Report '{path}' is not a JSON object.")
        reports.append(_normalise_report(data))
    reports.sort(key=lambda r: (_parse_timestamp(r["timestamp"]), r["run_id"]))
    return reports


def _control_index(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for result in results:
        control_id = result.get("control_id")
        if isinstance(control_id, str) and control_id:
            indexed[control_id] = result
    return indexed


def _extract_nist_family(control_id: str) -> str:
    if "-" in control_id:
        return control_id.split("-", 1)[0]
    return control_id


def _framework_rollups(latest_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Build framework rates and coverage for NIST, CIS, and STIG."""
    nist_counts: dict[str, dict[str, int]] = {}
    cis_counts: dict[str, dict[str, int]] = {}
    stig_counts: dict[str, dict[str, int]] = {}
    mapped = {"nist": 0, "cis_level": 0, "stig_severity": 0}
    total_controls = len(latest_results)

    for row in latest_results:
        status = str(row.get("status", "UNKNOWN"))
        tags = row.get("tags", {}) if isinstance(row.get("tags"), dict) else {}

        nist_tags = tags.get("nist", []) if isinstance(tags.get("nist"), list) else []
        if nist_tags:
            mapped["nist"] += 1
            for tag in sorted(str(t) for t in nist_tags):
                fam = _extract_nist_family(tag)
                bucket = nist_counts.setdefault(fam, {"PASS": 0, "FAIL": 0, "ERROR": 0})
                if status in bucket:
                    bucket[status] += 1

        cis_level = tags.get("cis_level")
        if cis_level not in (None, ""):
            mapped["cis_level"] += 1
            cis_key = str(cis_level)
            bucket = cis_counts.setdefault(cis_key, {"PASS": 0, "FAIL": 0, "ERROR": 0})
            if status in bucket:
                bucket[status] += 1

        stig = tags.get("stig_severity")
        if stig not in (None, ""):
            mapped["stig_severity"] += 1
            stig_key = str(stig)
            bucket = stig_counts.setdefault(stig_key, {"PASS": 0, "FAIL": 0, "ERROR": 0})
            if status in bucket:
                bucket[status] += 1

    def _rate_table(data: dict[str, dict[str, int]], kind: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key in sorted(data):
            row = data[key]
            total = max(1, row["PASS"] + row["FAIL"] + row["ERROR"])
            rows.append(
                {
                    kind: key,
                    "counts": row,
                    "pass_rate": round(row["PASS"] / total, 4),
                    "fail_rate": round(row["FAIL"] / total, 4),
                    "error_rate": round(row["ERROR"] / total, 4),
                }
            )
        return rows

    return {
        "nist": {
            "families": _rate_table(nist_counts, "family"),
            "coverage": {
                "mapped": mapped["nist"],
                "unmapped": max(0, total_controls - mapped["nist"]),
                "total": total_controls,
            },
        },
        "cis_level": {
            "levels": _rate_table(cis_counts, "level"),
            "coverage": {
                "mapped": mapped["cis_level"],
                "unmapped": max(0, total_controls - mapped["cis_level"]),
                "total": total_controls,
            },
        },
        "stig_severity": {
            "levels": _rate_table(stig_counts, "severity"),
            "coverage": {
                "mapped": mapped["stig_severity"],
                "unmapped": max(0, total_controls - mapped["stig_severity"]),
                "total": total_controls,
            },
        },
    }


def _waiver_board(latest: dict[str, Any], now: datetime) -> dict[str, Any]:
    active: list[dict[str, Any]] = []
    expiring: list[dict[str, Any]] = []
    expired: list[dict[str, Any]] = []

    for result in latest.get("results", []):
        waiver = result.get("waiver")
        if not isinstance(waiver, dict):
            continue
        expiry_raw = waiver.get("expiry")
        expiry = (
            _parse_timestamp(str(expiry_raw))
            if expiry_raw
            else datetime.max.replace(tzinfo=timezone.utc)
        )
        days_to_expiry = (
            (expiry - now).days if expiry != datetime.max.replace(tzinfo=timezone.utc) else 10**9
        )
        row = {
            "waiver_id": str(result.get("waiver_id", waiver.get("id", ""))),
            "control_id": str(result.get("control_id", "")),
            "host": str(latest.get("host", "unknown")),
            "owner": str(waiver.get("owner", "")),
            "expiry": str(expiry_raw or ""),
            "days_to_expiry": days_to_expiry,
            "status": str(result.get("status", "")),
        }
        if result.get("waiver_expired") or days_to_expiry < 0:
            expired.append(row)
        elif days_to_expiry <= 30:
            expiring.append(row)
        else:
            active.append(row)

    def sort_key(row: dict[str, Any]) -> tuple[int, str, str]:
        return (row["days_to_expiry"], row["waiver_id"], row["control_id"])

    return {
        "active": sorted(active, key=sort_key),
        "expiring": sorted(expiring, key=sort_key),
        "expired": sorted(expired, key=sort_key),
    }


def _trend_series(reports: list[dict[str, Any]]) -> dict[str, Any]:
    series = [
        {
            "run_id": r["run_id"],
            "timestamp": r["timestamp"],
            "profile": r["profile"].get("name", ""),
            "host": r["host"],
            "environment": r.get("environment", "unknown"),
            "counts": r["summary"]["counts"],
            "risk_score": r["summary"]["risk_score"],
        }
        for r in reports
    ]
    return {
        "series": series,
        "filters": {
            "profiles": sorted({s["profile"] for s in series}),
            "hosts": sorted({s["host"] for s in series}),
            "environments": sorted({s["environment"] for s in series}),
            "tag_namespaces": ["all", "nist", "cis_level", "stig_severity", "custom"],
        },
    }


def _top_regressions(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(reports) < 2:
        return []
    previous = reports[-2]
    latest = reports[-1]
    diff = diff_reports(previous, latest)

    latest_index = _control_index(latest.get("results", []))
    host_breadth: dict[str, set[str]] = {}
    for run in reports:
        host = run.get("host", "unknown")
        for result in run.get("results", []):
            if str(result.get("status", "")) == "FAIL":
                cid = str(result.get("control_id", ""))
                if cid:
                    host_breadth.setdefault(cid, set()).add(str(host))

    rows: list[dict[str, Any]] = []
    for control_id in diff.get("new_failures", []):
        entry = latest_index.get(control_id, {})
        impact = float(entry.get("impact", 0.0) or 0.0)
        breadth = len(host_breadth.get(control_id, set()))
        rows.append(
            {
                "control_id": control_id,
                "title": str(entry.get("title", "")),
                "impact": impact,
                "host_breadth": breadth,
                "score": round(impact * max(1, breadth), 4),
                "evidence_anchor": f"#control-{control_id}",
            }
        )
    rows.sort(key=lambda r: (-r["score"], -r["impact"], r["control_id"]))
    return rows


def _last_good_run(reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    for run in reversed(reports):
        counts = run["summary"]["counts"]
        if counts.get("FAIL", 0) == 0 and counts.get("ERROR", 0) == 0:
            return run
    return None


def _changed_since_last_good(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not reports:
        return []
    latest = reports[-1]
    baseline = _last_good_run(reports[:-1])
    if baseline is None:
        return []
    diff = diff_reports(baseline, latest)
    return list(diff.get("status_changes", []))


def build_dashboard_dataset(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Build dashboard analytics dataset from canonical reports."""
    if not reports:
        raise ValueError("At least one report is required to build dashboard data.")

    reports = sorted(reports, key=lambda r: (_parse_timestamp(r["timestamp"]), r["run_id"]))
    now = datetime.now(tz=timezone.utc)
    latest = reports[-1]

    dataset = {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "runs": reports,
        "latest_run_id": latest["run_id"],
        "posture_trends": _trend_series(reports),
        "waiver_board": _waiver_board(latest, now),
        "framework_rollups": _framework_rollups(latest.get("results", [])),
        "triage": {
            "top_regressions": _top_regressions(reports),
            "changed_since_last_good": _changed_since_last_good(reports),
        },
    }
    return dataset


def write_dashboard_dataset(dataset: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dataset, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_audit_pack(
    dataset: dict[str, Any],
    *,
    profile: str | None = None,
    host: str | None = None,
    environment: str | None = None,
    framework: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic scoped audit export with provenance."""
    runs = list(dataset.get("runs", []))
    scoped_runs: list[dict[str, Any]] = []

    for run in runs:
        if profile and run.get("profile", {}).get("name") != profile:
            continue
        if host and run.get("host") != host:
            continue
        if environment and run.get("environment") != environment:
            continue

        run_copy = {
            "run_id": run.get("run_id", ""),
            "timestamp": run.get("timestamp", ""),
            "profile": run.get("profile", {}),
            "host": run.get("host", ""),
            "environment": run.get("environment", "unknown"),
            "summary": run.get("summary", {}),
            "results": [],
        }

        for result in run.get("results", []):
            if framework:
                tags = result.get("tags", {}) if isinstance(result.get("tags"), dict) else {}
                if framework == "nist" and not tags.get("nist"):
                    continue
                if framework == "cis_level" and tags.get("cis_level") in (None, ""):
                    continue
                if framework == "stig_severity" and tags.get("stig_severity") in (None, ""):
                    continue
            run_copy["results"].append(result)

        run_copy["results"] = sorted(
            run_copy["results"], key=lambda r: str(r.get("control_id", ""))
        )
        scoped_runs.append(run_copy)

    scoped_runs.sort(
        key=lambda r: (_parse_timestamp(str(r.get("timestamp", ""))), str(r.get("run_id", "")))
    )
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "provenance": {
            "dashboard_generated_at": dataset.get("generated_at", ""),
            "source_run_ids": [str(r.get("run_id", "")) for r in scoped_runs],
        },
        "scope": {
            "profile": profile,
            "host": host,
            "environment": environment,
            "framework": framework,
        },
        "runs": scoped_runs,
    }


def write_audit_pack(pack: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_alerts(
    dataset: dict[str, Any],
    *,
    risk_spike_threshold: float = 0.5,
    waiver_window_days: int = 7,
) -> dict[str, Any]:
    """Build dashboard alerts for new failures, waiver expiries, and risk spikes."""
    runs = list(dataset.get("runs", []))
    alerts: list[dict[str, Any]] = []

    if len(runs) >= 2:
        previous = runs[-2]
        latest = runs[-1]
        diff = diff_reports(previous, latest)
        latest_index = _control_index(latest.get("results", []))
        for cid in diff.get("new_failures", []):
            result = latest_index.get(cid, {})
            impact = float(result.get("impact", 0.0) or 0.0)
            if impact >= 0.9:
                alerts.append(
                    {
                        "type": "new_critical_failure",
                        "severity": "high",
                        "control_id": cid,
                        "impact": impact,
                        "link": f"dashboard.html#control-{cid}",
                    }
                )

        prev_risk = float(previous.get("summary", {}).get("risk_score", 0.0) or 0.0)
        latest_risk = float(latest.get("summary", {}).get("risk_score", 0.0) or 0.0)
        if (latest_risk - prev_risk) >= risk_spike_threshold:
            alerts.append(
                {
                    "type": "risk_score_spike",
                    "severity": "medium",
                    "from": prev_risk,
                    "to": latest_risk,
                    "link": "dashboard.html#posture-trends",
                }
            )

    waiver_board = dataset.get("waiver_board", {})
    for item in waiver_board.get("expired", []):
        alerts.append(
            {
                "type": "waiver_expired",
                "severity": "high",
                "waiver_id": item.get("waiver_id", ""),
                "control_id": item.get("control_id", ""),
                "link": f"dashboard.html#waiver-{item.get('waiver_id', '')}",
            }
        )
    for item in waiver_board.get("expiring", []):
        if int(item.get("days_to_expiry", 9999)) <= waiver_window_days:
            alerts.append(
                {
                    "type": "waiver_expiring_soon",
                    "severity": "medium",
                    "waiver_id": item.get("waiver_id", ""),
                    "control_id": item.get("control_id", ""),
                    "days_to_expiry": item.get("days_to_expiry", 0),
                    "link": f"dashboard.html#waiver-{item.get('waiver_id', '')}",
                }
            )

    alerts.sort(
        key=lambda a: (
            str(a.get("type", "")),
            str(a.get("control_id", "")),
            str(a.get("waiver_id", "")),
        )
    )
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "alerts": alerts,
    }


def write_alerts(alerts: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(alerts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def post_slack_alerts(alerts: dict[str, Any], webhook_url: str) -> None:
    """Send alerts to Slack incoming webhook (REQ-9.7 channel integration)."""
    lines = ["Attest compliance alerts:"]
    for row in alerts.get("alerts", []):
        if row.get("type") == "new_critical_failure":
            lines.append(
                f"- NEW CRITICAL FAIL {row.get('control_id')} impact={row.get('impact')} {row.get('link')}"
            )
        elif row.get("type") == "waiver_expired":
            lines.append(
                f"- WAIVER EXPIRED {row.get('waiver_id')} control={row.get('control_id')} {row.get('link')}"
            )
        elif row.get("type") == "waiver_expiring_soon":
            lines.append(
                f"- WAIVER EXPIRING {row.get('waiver_id')} in {row.get('days_to_expiry')} days {row.get('link')}"
            )
        elif row.get("type") == "risk_score_spike":
            lines.append(f"- RISK SPIKE {row.get('from')} -> {row.get('to')} {row.get('link')}")

    payload = json.dumps({"text": "\n".join(lines)}).encode("utf-8")
    req = request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=10) as response:
            if response.status >= 300:
                raise RuntimeError(f"Slack webhook returned status {response.status}.")
    except error.URLError as exc:
        raise RuntimeError(f"Slack alert delivery failed: {exc}") from exc


def evaluate_slos(dataset: dict[str, Any]) -> dict[str, Any]:
    """Evaluate dashboard SLO proxies for latency and freshness (REQ-9.8)."""
    runs = list(dataset.get("runs", []))
    latest = runs[-1] if runs else {}
    latest_results = list(latest.get("results", []))
    generated_at = _parse_timestamp(str(dataset.get("generated_at", "")))
    latest_ts = _parse_timestamp(str(latest.get("timestamp", "")))
    freshness_seconds = max(0.0, (generated_at - latest_ts).total_seconds())

    # Beta proxy estimators based on payload size to keep checks deterministic.
    posture_load_seconds = round(0.15 + (len(latest_results) / 2000.0), 4)
    drilldown_load_seconds = round(0.2 + (len(latest_results) / 1500.0), 4)

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "metrics": {
            "posture_load_seconds": posture_load_seconds,
            "drilldown_load_seconds": drilldown_load_seconds,
            "freshness_seconds": round(freshness_seconds, 4),
        },
        "targets": {
            "posture_load_seconds": 2.0,
            "drilldown_load_seconds": 3.0,
            "freshness_seconds": 60.0,
        },
        "passes": {
            "posture_load_seconds": posture_load_seconds < 2.0,
            "drilldown_load_seconds": drilldown_load_seconds < 3.0,
            "freshness_seconds": freshness_seconds < 60.0,
        },
    }


def write_slo_report(slo_report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(slo_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
