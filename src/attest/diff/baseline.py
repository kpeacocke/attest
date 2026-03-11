"""Baseline storage helpers for canonical reports (REQ-6.1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def save_baseline(report: dict[str, Any], store_dir: Path, *, name: str | None = None) -> Path:
    """Save a canonical report into a local baseline store directory."""
    store_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(report.get("run_id", "unknown"))
    base_name = name or run_id
    path = store_dir / f"{base_name}.json"
    with path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return path


def load_report(path: Path) -> dict[str, Any]:
    """Load a canonical report from JSON file path."""
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Report file '{path}' is not a JSON object.")
    return data
