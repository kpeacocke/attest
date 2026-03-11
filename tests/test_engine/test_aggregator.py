"""Tests for aggregator (REQ-3.1 aggregation rules)."""
from __future__ import annotations

from attest.engine.aggregator import aggregate
from attest.engine.result import ControlStatus, TestEvidence


def _evidence(status: ControlStatus, name: str = "t") -> TestEvidence:
    return TestEvidence(
        name=name,
        resource="r",
        operator="eq",
        expected="x",
        actual="x",
        status=status,
    )


class TestAggregate:
    def test_all_pass(self) -> None:
        result = aggregate(
            "X-001",
            [_evidence(ControlStatus.PASS, "t1"), _evidence(ControlStatus.PASS, "t2")],
        )
        assert result.status == ControlStatus.PASS

    def test_any_fail_yields_fail(self) -> None:
        result = aggregate(
            "X-001",
            [_evidence(ControlStatus.PASS), _evidence(ControlStatus.FAIL)],
        )
        assert result.status == ControlStatus.FAIL

    def test_error_without_fail_yields_error(self) -> None:
        result = aggregate(
            "X-001",
            [_evidence(ControlStatus.PASS), _evidence(ControlStatus.ERROR)],
        )
        assert result.status == ControlStatus.ERROR

    def test_fail_overrides_error(self) -> None:
        result = aggregate(
            "X-001",
            [_evidence(ControlStatus.ERROR), _evidence(ControlStatus.FAIL)],
        )
        assert result.status == ControlStatus.FAIL

    def test_empty_evidence_yields_error(self) -> None:
        result = aggregate("X-001", [])
        assert result.status == ControlStatus.ERROR
        assert "No test evidence" in result.skip_reason
