"""Diff engine for canonical reports (REQ-6.2)."""

from __future__ import annotations

import json
from typing import Any


def _index_results(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for result in report.get("results", []):
        control_id = result.get("control_id")
        if isinstance(control_id, str) and control_id:
            indexed[control_id] = result
    return indexed


def diff_reports(report_a: dict[str, Any], report_b: dict[str, Any]) -> dict[str, Any]:
    """Compute deterministic diff between two canonical reports."""
    a_index = _index_results(report_a)
    b_index = _index_results(report_b)

    all_ids = sorted(set(a_index) | set(b_index))

    new_failures: list[str] = []
    new_passes: list[str] = []
    new_skips: list[str] = []
    new_errors: list[str] = []
    waiver_changes: list[dict[str, str]] = []
    status_changes: list[dict[str, str]] = []

    for control_id in all_ids:
        old = a_index.get(control_id)
        new = b_index.get(control_id)

        old_status = str(old.get("status")) if old else "ABSENT"
        new_status = str(new.get("status")) if new else "ABSENT"

        if old_status != new_status:
            status_changes.append({"control_id": control_id, "from": old_status, "to": new_status})

        if new_status == "FAIL" and old_status != "FAIL":
            new_failures.append(control_id)
        if new_status == "PASS" and old_status != "PASS":
            new_passes.append(control_id)
        if new_status == "SKIP" and old_status != "SKIP":
            new_skips.append(control_id)
        if new_status == "ERROR" and old_status != "ERROR":
            new_errors.append(control_id)

        old_waiver = str(old.get("waiver_id", "")) if old else ""
        new_waiver = str(new.get("waiver_id", "")) if new else ""
        if old_waiver != new_waiver:
            waiver_changes.append(
                {
                    "control_id": control_id,
                    "from": old_waiver or "none",
                    "to": new_waiver or "none",
                }
            )

    return {
        "schema_version": "1.0",
        "baseline_run_id": report_a.get("run_id", ""),
        "current_run_id": report_b.get("run_id", ""),
        "new_failures": sorted(new_failures),
        "new_passes": sorted(new_passes),
        "new_skips": sorted(new_skips),
        "new_errors": sorted(new_errors),
        "waiver_changes": sorted(waiver_changes, key=lambda x: x["control_id"]),
        "status_changes": sorted(status_changes, key=lambda x: x["control_id"]),
    }


def build_markdown_diff(diff: dict[str, Any]) -> str:
    """Build a Markdown summary for a report diff."""
    lines: list[str] = []
    lines.append("# Attest Drift Report")
    lines.append("")
    lines.append(f"**Baseline run:** {diff.get('baseline_run_id', '')}  ")
    lines.append(f"**Current run:** {diff.get('current_run_id', '')}  ")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- New failures: {len(diff.get('new_failures', []))}")
    lines.append(f"- New passes: {len(diff.get('new_passes', []))}")
    lines.append(f"- New skips: {len(diff.get('new_skips', []))}")
    lines.append(f"- New errors: {len(diff.get('new_errors', []))}")
    lines.append(f"- Waiver changes: {len(diff.get('waiver_changes', []))}")
    lines.append("")

    def _section(title: str, items: list[str]) -> None:
        if not items:
            return
        lines.append(f"## {title}")
        lines.append("")
        for item in items:
            lines.append(f"- {item}")
        lines.append("")

    _section("New failures", list(diff.get("new_failures", [])))
    _section("New passes", list(diff.get("new_passes", [])))
    _section("New skips", list(diff.get("new_skips", [])))
    _section("New errors", list(diff.get("new_errors", [])))

    waiver_changes = list(diff.get("waiver_changes", []))
    if waiver_changes:
        lines.append("## Waiver changes")
        lines.append("")
        for row in waiver_changes:
            lines.append(f"- {row['control_id']}: {row['from']} -> {row['to']}")
        lines.append("")

    return "\n".join(lines)


def write_json_diff(diff: dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(diff, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def write_markdown_diff(diff: dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_markdown_diff(diff))
        fh.write("\n")
