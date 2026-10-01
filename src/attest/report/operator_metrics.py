"""Opt-in operator outcome measurements for REQ-8.5."""

from __future__ import annotations

import csv
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import mean
from typing import TypedDict

METRICS = ("triage_seconds", "audit_pack_seconds", "expired_waiver_miss")


class TriageMetrics(TypedDict):
    baseline_samples: int
    current_samples: int
    baseline_mean_seconds: float | None
    current_mean_seconds: float | None
    reduction_ratio: float | None
    target_reduction_ratio: float
    meets_target: bool | None


class AuditPackMetrics(TypedDict):
    baseline_samples: int
    baseline_mean_seconds: float | None
    samples: int
    mean_seconds: float | None
    target_under_seconds: int
    meets_target: bool | None


class ExpiredWaiverMetrics(TypedDict):
    baseline_samples: int
    baseline_misses: int
    baseline_miss_rate: float | None
    samples: int
    misses: int
    miss_rate: float | None
    target_max_miss_rate: float
    meets_target: bool | None


class OperatorMetricsReport(TypedDict):
    schema_version: str
    triage: TriageMetrics
    audit_pack: AuditPackMetrics
    expired_waivers: ExpiredWaiverMetrics


def load_observations(path: Path) -> dict[str, list[float]]:
    observations: dict[str, list[float]] = {metric: [] for metric in METRICS}
    with path.open(encoding="utf-8", newline="") as source:
        rows = csv.DictReader(source)
        if rows.fieldnames != ["metric", "value"]:
            raise ValueError("Metrics CSV must contain exactly 'metric,value' columns.")
        for line_number, row in enumerate(rows, start=2):
            metric = row.get("metric")
            if metric not in observations or row.get(None):
                raise ValueError(f"Invalid metric on row {line_number}.")
            try:
                value = float(row["value"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid value on row {line_number}.") from exc
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"Metric value on row {line_number} must be finite and non-negative.")
            if metric == "expired_waiver_miss" and value not in (0, 1):
                raise ValueError(f"Expired waiver miss on row {line_number} must be 0 or 1.")
            observations[metric].append(value)
    return observations


def evaluate_operator_metrics(
    baseline: Mapping[str, Sequence[float]], current: Mapping[str, Sequence[float]]
) -> OperatorMetricsReport:
    baseline_triage = baseline["triage_seconds"]
    current_triage = current["triage_seconds"]
    baseline_audit = baseline["audit_pack_seconds"]
    audit_times = current["audit_pack_seconds"]
    baseline_waivers = baseline["expired_waiver_miss"]
    waiver_events = current["expired_waiver_miss"]

    baseline_mean = mean(baseline_triage) if baseline_triage else None
    current_mean = mean(current_triage) if current_triage else None
    reduction = (
        1 - current_mean / baseline_mean
        if baseline_mean is not None and baseline_mean > 0 and current_mean is not None
        else None
    )
    baseline_audit_mean = mean(baseline_audit) if baseline_audit else None
    audit_mean = mean(audit_times) if audit_times else None
    baseline_miss_rate = mean(baseline_waivers) if baseline_waivers else None
    miss_rate = mean(waiver_events) if waiver_events else None

    return {
        "schema_version": "1.0",
        "triage": {
            "baseline_samples": len(baseline_triage),
            "current_samples": len(current_triage),
            "baseline_mean_seconds": round(baseline_mean, 4) if baseline_mean is not None else None,
            "current_mean_seconds": round(current_mean, 4) if current_mean is not None else None,
            "reduction_ratio": round(reduction, 4) if reduction is not None else None,
            "target_reduction_ratio": 0.5,
            "meets_target": reduction >= 0.5 if reduction is not None else None,
        },
        "audit_pack": {
            "baseline_samples": len(baseline_audit),
            "baseline_mean_seconds": round(baseline_audit_mean, 4) if baseline_audit_mean is not None else None,
            "samples": len(audit_times),
            "mean_seconds": round(audit_mean, 4) if audit_mean is not None else None,
            "target_under_seconds": 1800,
            "meets_target": audit_mean < 1800 if audit_mean is not None else None,
        },
        "expired_waivers": {
            "baseline_samples": len(baseline_waivers),
            "baseline_misses": int(sum(baseline_waivers)),
            "baseline_miss_rate": round(baseline_miss_rate, 4) if baseline_miss_rate is not None else None,
            "samples": len(waiver_events),
            "misses": int(sum(waiver_events)),
            "miss_rate": round(miss_rate, 4) if miss_rate is not None else None,
            "target_max_miss_rate": 0.01,
            "meets_target": miss_rate <= 0.01 if miss_rate is not None else None,
        },
    }