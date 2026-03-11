"""Markdown summary reporter (REQ-4.2, REQ-8.2)."""
from __future__ import annotations

from typing import Any


def build_markdown(report: dict[str, Any]) -> str:
    """Build a Markdown summary from a canonical report.

    Starts with an executive summary (REQ-8.2), then failure details,
    then waived/skip sections.
    """
    profile = report.get("profile", {})
    host = report.get("host", "unknown")
    timestamp = report.get("timestamp", "")
    run_id = report.get("run_id", "")
    counts = report.get("summary", {}).get("counts", {})
    risk_score = report.get("summary", {}).get("risk_score", 0.0)
    results = report.get("results", [])

    lines: list[str] = []

    # --- Executive summary ---
    lines.append("# Attest Run Report")
    lines.append("")
    lines.append(
        f"**Profile:** {profile.get('name', '-')} v{profile.get('version', '-')}  "
    )
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

    # --- Failures ---
    failures = [r for r in results if r.get("status") == "FAIL"]
    if failures:
        lines.append("## Failures")
        lines.append("")
        for r in failures:
            lines.append(f"### {r.get('control_id')} — {r.get('title', '')}")
            if r.get("skip_reason"):
                lines.append(f"> {r['skip_reason']}")
            lines.append("")
            for t in r.get("tests", []):
                if t.get("status") == "FAIL":
                    lines.append(
                        f"- **{t.get('name')}**: expected `{t.get('expected')}`, "
                        f"got `{t.get('actual')}`. {t.get('message', '')}"
                    )
            lines.append("")

    # --- Errors ---
    errors = [r for r in results if r.get("status") == "ERROR"]
    if errors:
        lines.append("## Errors")
        lines.append("")
        for r in errors:
            lines.append(f"### {r.get('control_id')} — {r.get('title', '')}")
            for t in r.get("tests", []):
                if t.get("status") == "ERROR":
                    lines.append(f"- **{t.get('name')}**: {t.get('message', 'evaluation error')}")
            lines.append("")

    # --- Waivers ---
    waivers = [r for r in results if r.get("status") == "WAIVED"]
    if waivers:
        lines.append("## Waived controls")
        lines.append("")
        for r in waivers:
            lines.append(
                f"- **{r.get('control_id')}** — {r.get('title', '')} "
                f"(waiver: `{r.get('waiver_id', 'unknown')}`)"
            )
        lines.append("")

    return "\n".join(lines)


def write_markdown(report: dict[str, Any], path: str) -> None:
    """Write a Markdown report to a file path."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_markdown(report))
        fh.write("\n")
