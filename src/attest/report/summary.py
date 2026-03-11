"""Summary artefact generator — attest-summary.json (REQ-4.4)."""

from __future__ import annotations

import json
from typing import Any


def build_summary(report: dict[str, Any]) -> dict[str, Any]:
    """Extract a small deterministic summary from the canonical report.

    Fields are stable and documented (REQ-4.4).
    """
    counts = report.get("summary", {}).get("counts", {})
    return {
        "schema_version": report.get("schema_version", "1.0"),
        "run_id": report.get("run_id", ""),
        "timestamp": report.get("timestamp", ""),
        "profile": report.get("profile", {}),
        "host": report.get("host", ""),
        "fail_count": counts.get("FAIL", 0),
        "error_count": counts.get("ERROR", 0),
        "waived_count": counts.get("WAIVED", 0),
        "pass_count": counts.get("PASS", 0),
        "skip_count": counts.get("SKIP", 0),
        "risk_score": report.get("summary", {}).get("risk_score", 0.0),
    }


def write_summary(summary: dict[str, Any], path: str) -> None:
    """Write the summary artefact to a file path."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=False, ensure_ascii=False)
        fh.write("\n")
