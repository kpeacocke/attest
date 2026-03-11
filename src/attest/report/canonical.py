"""Canonical JSON report schema and writer (REQ-4.1).

The canonical report is the source of truth; all other formats are derived
from it.  Field ordering is deterministic for stable diff comparisons (REQ-7.4).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from attest.engine.result import ControlResult, ControlStatus
from attest.policy.schemas import Control, Profile

SCHEMA_VERSION = "1.0"

# Simple beta risk score: weighted sum of FAIL/ERROR impact values.
_STATUS_WEIGHT: dict[ControlStatus, float] = {
    ControlStatus.FAIL: 1.0,
    ControlStatus.ERROR: 0.5,
    ControlStatus.WAIVED: 0.0,
    ControlStatus.PASS: 0.0,
    ControlStatus.SKIP: 0.0,
}


def _tag_summaries(
    controls_by_id: dict[str, Control], results: list[ControlResult]
) -> dict[str, Any]:
    """Build framework tag summaries grouped by namespace (REQ-4.1)."""
    nist: dict[str, int] = {}
    cis_levels: dict[int, int] = {}
    stig_cats: dict[str, int] = {}

    passing_ids = {r.control_id for r in results if r.status == ControlStatus.PASS}

    for result in results:
        ctrl = controls_by_id.get(result.control_id)
        if ctrl is None:
            continue
        if result.status == ControlStatus.PASS:
            for nist_id in ctrl.tags.nist:
                nist[nist_id] = nist.get(nist_id, 0) + 1
            if ctrl.tags.cis_level is not None:
                cis_levels[ctrl.tags.cis_level] = cis_levels.get(ctrl.tags.cis_level, 0) + 1
            if ctrl.tags.stig_severity:
                stig_cats[ctrl.tags.stig_severity] = stig_cats.get(ctrl.tags.stig_severity, 0) + 1

    return {
        "nist": {k: nist[k] for k in sorted(nist)},
        "cis_level": {str(k): cis_levels[k] for k in sorted(cis_levels)},
        "stig_severity": {k: stig_cats[k] for k in sorted(stig_cats)},
        "passing_control_ids": sorted(passing_ids),
    }


def _evidence_entry(e: Any) -> dict[str, Any]:
    return {
        "name": e.name,
        "resource": e.resource,
        "operator": e.operator,
        "expected": e.expected,
        "actual": e.actual,
        "status": e.status.value,
        "message": e.message,
    }


def _control_entry(
    result: ControlResult,
    ctrl: Control | None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "control_id": result.control_id,
        "status": result.status.value,
    }
    if ctrl is not None:
        entry["title"] = ctrl.title
        entry["impact"] = ctrl.impact
        entry["tags"] = {
            "nist": sorted(ctrl.tags.nist),
            "cis_level": ctrl.tags.cis_level,
            "stig_severity": ctrl.tags.stig_severity,
            "custom": sorted(ctrl.tags.custom),
        }
    if result.skip_reason:
        entry["skip_reason"] = result.skip_reason
    if result.waiver_id:
        entry["waiver_id"] = result.waiver_id
    if result.overlay_source:
        entry["overlay_source"] = result.overlay_source
    if result.original_impact is not None:
        entry["original_impact"] = result.original_impact
    entry["tests"] = [_evidence_entry(e) for e in result.tests]
    return entry


def build_report(
    profile: Profile,
    controls: list[Control],
    results: list[ControlResult],
    *,
    run_id: str | None = None,
    host: str = "localhost",
) -> dict[str, Any]:
    """Build the canonical JSON report dict.

    Results and controls are sorted by control ID for deterministic output (REQ-7.4).
    """
    run_id = run_id or str(uuid.uuid4())
    timestamp = datetime.now(tz=timezone.utc).isoformat()

    controls_by_id = {c.id: c for c in controls}
    sorted_results = sorted(results, key=lambda r: r.control_id)

    # Status counts for per-host summary.
    counts: dict[str, int] = {s.value: 0 for s in ControlStatus}
    for r in sorted_results:
        counts[r.status.value] += 1

    # Beta risk score: sum of (impact × weight) for each result.
    risk_score = sum(
        (controls_by_id[r.control_id].impact if r.control_id in controls_by_id else 0.5)
        * _STATUS_WEIGHT.get(r.status, 0.0)
        for r in sorted_results
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "timestamp": timestamp,
        "profile": {
            "name": profile.name,
            "title": profile.title,
            "version": profile.version,
        },
        "host": host,
        "summary": {
            "counts": counts,
            "risk_score": round(risk_score, 4),
        },
        "tag_summaries": _tag_summaries(controls_by_id, sorted_results),
        "results": [_control_entry(r, controls_by_id.get(r.control_id)) for r in sorted_results],
    }


def write_report(report: dict[str, Any], path: str) -> None:
    """Write canonical JSON report to a file path."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=False, ensure_ascii=False)
        fh.write("\n")
