"""Aggregate test results into a control-level status (REQ-3.1)."""

from __future__ import annotations

from attest.engine.result import ControlResult, ControlStatus, TestEvidence


def aggregate(control_id: str, test_evidence: list[TestEvidence]) -> ControlResult:
    """Apply aggregation rules to produce a single ControlResult.

    Rules (REQ-3.1):
    - Any FAIL  → FAIL
    - Any ERROR (no FAIL) → ERROR
    - All PASS  → PASS
    """
    if not test_evidence:
        return ControlResult(
            control_id=control_id,
            status=ControlStatus.ERROR,
            tests=[],
            skip_reason="No test evidence was produced.",
        )

    statuses = {e.status for e in test_evidence}

    if ControlStatus.FAIL in statuses:
        final = ControlStatus.FAIL
    elif ControlStatus.ERROR in statuses:
        final = ControlStatus.ERROR
    else:
        final = ControlStatus.PASS

    return ControlResult(control_id=control_id, status=final, tests=list(test_evidence))
