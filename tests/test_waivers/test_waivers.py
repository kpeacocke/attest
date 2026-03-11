"""Tests for waiver schema and applier (REQ-5.1, REQ-5.2)."""
from __future__ import annotations

from datetime import date, timedelta


from attest.engine.result import ControlResult, ControlStatus
from attest.waivers.applier import apply_waivers
from attest.waivers.schema import Waiver


def _waiver(expiry: date, control_ids: list[str] | None = None) -> Waiver:
    return Waiver(
        id="W-001",
        control_ids=control_ids or ["X-001"],
        justification="Justified",
        expiry=expiry,
    )


def _fail_result(cid: str = "X-001") -> ControlResult:
    return ControlResult(control_id=cid, status=ControlStatus.FAIL)


class TestWaiverSchema:
    def test_active_waiver(self) -> None:
        w = _waiver(date.today() + timedelta(days=30))
        assert w.is_active()
        assert not w.is_expired()

    def test_expired_waiver(self) -> None:
        w = _waiver(date(2020, 1, 1))
        assert w.is_expired()
        assert not w.is_active()

    def test_waiver_on_expiry_day_is_active(self) -> None:
        today = date.today()
        w = _waiver(today)
        assert w.is_active()


class TestApplyWaivers:
    def test_active_waiver_converts_fail_to_waived(self) -> None:
        waiver = _waiver(date.today() + timedelta(days=30))
        results = apply_waivers([_fail_result()], [waiver])
        assert results[0].status == ControlStatus.WAIVED
        assert results[0].waiver_id == "W-001"

    def test_expired_waiver_keeps_fail_with_message(self) -> None:
        waiver = _waiver(date(2020, 1, 1))
        results = apply_waivers([_fail_result()], [waiver])
        assert results[0].status == ControlStatus.FAIL
        assert "waiver expired" in results[0].skip_reason

    def test_pass_not_modified_by_waiver(self) -> None:
        waiver = _waiver(date.today() + timedelta(days=30))
        result = ControlResult(control_id="X-001", status=ControlStatus.PASS)
        results = apply_waivers([result], [waiver])
        assert results[0].status == ControlStatus.PASS

    def test_waiver_applies_to_correct_control_only(self) -> None:
        waiver = _waiver(date.today() + timedelta(days=30), control_ids=["X-001"])
        results = apply_waivers(
            [_fail_result("X-001"), _fail_result("Y-001")],
            [waiver],
        )
        assert results[0].status == ControlStatus.WAIVED
        assert results[1].status == ControlStatus.FAIL
