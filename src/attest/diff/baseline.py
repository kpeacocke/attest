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


def resolve_baseline_path(store_dir: Path, identifier: str) -> Path:
    """Resolve a baseline by explicit file path stem, name, or run id."""
    direct = store_dir / f"{identifier}.json"
    if direct.exists():
        return direct

    for candidate in sorted(store_dir.glob("*.json")):
        try:
            report = load_report(candidate)
        except (OSError, ValueError):
            continue
        if str(report.get("run_id", "")) == identifier:
            return candidate

    raise FileNotFoundError(f"Baseline '{identifier}' was not found in store '{store_dir}'.")


def load_baseline(store_dir: Path, identifier: str) -> dict[str, Any]:
    """Load a baseline report by saved name or run id."""
    return load_report(resolve_baseline_path(store_dir, identifier))


def load_report(path: Path) -> dict[str, Any]:
    """Load a canonical report from JSON file path."""
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Report file '{path}' is not a JSON object.")
    return data
