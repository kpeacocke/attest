"""Result types and control status semantics for the evaluation engine (REQ-3.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ControlStatus(str, Enum):
    """Canonical outcome for a single control evaluation."""

    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    ERROR = "ERROR"
    WAIVED = "WAIVED"


@dataclass
class TestEvidence:
    """Evidence produced by evaluating one test assertion."""

    __test__ = False

    name: str
    resource: str
    operator: str
    expected: Any
    actual: Any
    status: ControlStatus
    message: str = ""


@dataclass
class ControlResult:
    """Aggregated result for one control on one host."""

    control_id: str
    status: ControlStatus
    tests: list[TestEvidence] = field(default_factory=list)
    skip_reason: str = ""
    waiver_id: str | None = None

    # Overlay provenance fields (REQ-4.1) — set when the control was modified.
    overlay_source: str | None = None
    original_impact: float | None = None
