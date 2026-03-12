"""Canonical JSON report schema and writer (REQ-4.1).

The canonical report is the source of truth; all other formats are derived
from it.  Field ordering is deterministic for stable diff comparisons (REQ-7.4).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from attest.engine.result import ControlResult, ControlStatus
from attest.policy.schemas import Control, Profile
from attest.redaction import Redactor

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


def _evidence_entry(e: Any, redactor: Redactor) -> dict[str, Any]:
    actual = redactor.redact(e.actual)
    message = redactor.redact(e.message) if isinstance(e.message, str) else e.message
    return {
        "name": e.name,
        "resource": e.resource,
        "operator": e.operator,
        "expected": e.expected,
        "actual": actual,
        "status": e.status.value,
        "message": message,
    }


def _truncate_value(value: Any, max_string_length: int) -> Any:
    """Truncate strings recursively for deterministic bounded evidence output."""
    if max_string_length <= 0:
        return value

    if isinstance(value, str):
        if len(value) <= max_string_length:
            return value
        return value[:max_string_length] + "...[TRUNCATED]"

    if isinstance(value, dict):
        return {k: _truncate_value(v, max_string_length) for k, v in value.items()}

    if isinstance(value, list):
        return [_truncate_value(item, max_string_length) for item in value]

    if isinstance(value, tuple):
        return tuple(_truncate_value(item, max_string_length) for item in value)

    return value


def _control_entry(
    result: ControlResult,
    ctrl: Control | None,
    redactor: Redactor,
    summary_only_resources: set[str],
    summary_only_tests: set[str],
    max_string_length: int,
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
    if result.waiver is not None:
        entry["waiver"] = result.waiver
    if result.waiver_expired:
        entry["waiver_expired"] = True
    if result.overlay_source:
        entry["overlay_source"] = result.overlay_source
    if result.original_impact is not None:
        entry["original_impact"] = result.original_impact
    tests: list[dict[str, Any]] = []
    for evidence in result.tests:
        evidence_entry = _evidence_entry(evidence, redactor)
        if evidence.resource in summary_only_resources or evidence.name in summary_only_tests:
            evidence_entry["actual"] = "[SUMMARY_ONLY]"
            evidence_entry["message"] = "Evidence omitted in summary-only mode."
        else:
            evidence_entry["actual"] = _truncate_value(
                evidence_entry.get("actual"), max_string_length
            )
            evidence_entry["message"] = _truncate_value(
                evidence_entry.get("message"), max_string_length
            )
        tests.append(evidence_entry)
    entry["tests"] = tests
    return entry


def build_report(
    profile: Profile,
    controls: list[Control],
    results: list[ControlResult],
    *,
    run_id: str | None = None,
    host: str = "localhost",
    redactor: Redactor | None = None,
    max_string_length: int = 4096,
    summary_only_resources: Iterable[str] | None = None,
    summary_only_tests: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Build the canonical JSON report dict.

    Results and controls are sorted by control ID for deterministic output (REQ-7.4).
    Evidence is redacted by default using the built-in Redactor (REQ-4.3).
    Pass ``redactor=Redactor([])`` to disable redaction.
    """
    redactor = redactor if redactor is not None else Redactor()
    summary_only_resources_set = set(summary_only_resources or [])
    summary_only_tests_set = set(summary_only_tests or [])
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
        "results": [
            _control_entry(
                r,
                controls_by_id.get(r.control_id),
                redactor,
                summary_only_resources_set,
                summary_only_tests_set,
                max_string_length,
            )
            for r in sorted_results
        ],
    }


def write_report(report: dict[str, Any], path: str) -> None:
    """Write canonical JSON report to a file path."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=False, ensure_ascii=False)
        fh.write("\n")
