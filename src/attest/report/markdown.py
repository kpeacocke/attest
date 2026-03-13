"""Markdown summary reporter (REQ-4.2, REQ-8.2)."""

from __future__ import annotations

from typing import Any

_TOP_FAILURES_LIMIT = 5


def _append_summary_section(lines: list[str], report: dict[str, Any]) -> None:
    profile = report.get("profile", {})
    host = report.get("host", "unknown")
    timestamp = report.get("timestamp", "")
    run_id = report.get("run_id", "")
    counts = report.get("summary", {}).get("counts", {})
    risk_score = report.get("summary", {}).get("risk_score", 0.0)

    lines.append("# Attest Run Report")
    lines.append("")
    lines.append(f"**Profile:** {profile.get('name', '-')} v{profile.get('version', '-')}  ")
    lines.append(f"**Host:** {host}  ")
    lines.append(f"**Run ID:** {run_id}  ")
    lines.append(f"**Timestamp:** {timestamp}  ")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Status | Count |")
    lines.append("|--------|-------|")
    for status in ("PASS", "FAIL", "ERROR", "SKIP", "WAIVED"):
        lines.append(f"| {status} | {counts.get(status, 0)} |")
    lines.append("")
    lines.append(f"**Risk score:** {risk_score}")
    lines.append("")

    _append_top_failures(lines, report.get("results", []))


def _append_top_failures(lines: list[str], results: list[dict[str, Any]]) -> None:
    """Append top failing controls by impact for quick executive scanning (REQ-8.2)."""
    # Include real failures only (not expired waivers - those get their own section).
    failures = [r for r in results if r.get("status") == "FAIL" and not r.get("waiver_expired")]
    if not failures:
        return
    top = sorted(failures, key=lambda r: r.get("impact", 0.0), reverse=True)[:_TOP_FAILURES_LIMIT]
    lines.append(f"### Top failing controls (by impact, up to {_TOP_FAILURES_LIMIT})")
    lines.append("")
    lines.append("| Control | Title | Impact |")
    lines.append("|---------|-------|--------|")
    for r in top:
        lines.append(f"| {r.get('control_id')} | {r.get('title', '')} | {r.get('impact', '-')} |")
    lines.append("")


def _append_failures_section(lines: list[str], results: list[dict[str, Any]], host: str) -> None:
    # Real failures only; expired waivers are shown in their own section.
    failures = [r for r in results if r.get("status") == "FAIL" and not r.get("waiver_expired")]
    if not failures:
        return

    lines.append("## Failures")
    lines.append("")
    for result in failures:
        impact = result.get("impact", "?")
        lines.append(
            f"### {result.get('control_id')} - {result.get('title', '')} "
            f"(host: {host}, impact: {impact})"
        )
        if result.get("skip_reason"):
            lines.append(f"> {result['skip_reason']}")
        lines.append("")
        for test in result.get("tests", []):
            if test.get("status") == "FAIL":
                lines.append(
                    f"- **{test.get('name')}**: expected `{test.get('expected')}`, "
                    f"got `{test.get('actual')}`. {test.get('message', '')}"
                )
        lines.append("")


def _append_errors_section(lines: list[str], results: list[dict[str, Any]]) -> None:
    errors = [r for r in results if r.get("status") == "ERROR"]
    if not errors:
        return

    lines.append("## Errors")
    lines.append("")
    for result in errors:
        lines.append(f"### {result.get('control_id')} - {result.get('title', '')}")
        for test in result.get("tests", []):
            if test.get("status") == "ERROR":
                lines.append(f"- **{test.get('name')}**: {test.get('message', 'evaluation error')}")
        lines.append("")


def _append_expired_waivers_section(lines: list[str], results: list[dict[str, Any]]) -> None:
    """Expired waivers are policy breaches and rendered visually distinct (REQ-8.2)."""
    expired = [r for r in results if r.get("waiver_expired")]
    if not expired:
        return

    lines.append("## Expired waivers - policy breach")
    lines.append("")
    lines.append(
        "> These controls have an expired waiver and are counted as FAIL. "
        "Renew or remediate each waiver immediately."
    )
    lines.append("")
    for result in expired:
        waiver_id = result.get("waiver_id", "unknown")
        lines.append(
            f"- **{result.get('control_id')}** - {result.get('title', '')} "
            f"(waiver: `{waiver_id}`)"
        )
    lines.append("")


def _append_waivers_section(lines: list[str], results: list[dict[str, Any]]) -> None:
    """Active (non-expired) waived controls (REQ-8.2)."""
    waivers = [r for r in results if r.get("status") == "WAIVED"]
    if not waivers:
        return

    lines.append("## Waived controls")
    lines.append("")
    for result in waivers:
        lines.append(
            f"- **{result.get('control_id')}** - {result.get('title', '')} "
            f"(waiver: `{result.get('waiver_id', 'unknown')}`)"
        )
    lines.append("")


def build_markdown(report: dict[str, Any]) -> str:
    """Build a Markdown summary from a canonical report.

    Starts with an executive summary (REQ-8.2), then failure details,
    then waived/skip sections.
    """
    results = list(report.get("results", []))
    host = report.get("host", "unknown")
    lines: list[str] = []

    _append_summary_section(lines, report)
    _append_failures_section(lines, results, host)
    _append_errors_section(lines, results)
    _append_expired_waivers_section(lines, results)
    _append_waivers_section(lines, results)

    return "\n".join(lines)


def write_markdown(report: dict[str, Any], path: str) -> None:
    """Write a Markdown report to a file path."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_markdown(report))
        fh.write("\n")
