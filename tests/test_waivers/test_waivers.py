"""Tests for waiver schema and applier (REQ-5.1, REQ-5.2)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from attest.engine.result import ControlResult, ControlStatus
from attest.waivers.applier import apply_waivers
from attest.waivers.schema import Waiver, load_waivers


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

    def test_single_control_id_is_normalised(self) -> None:
        waiver = Waiver.model_validate(
            {
                "id": "W-002",
                "control_id": "X-009",
                "justification": "Needed",
                "expiry": str(date.today()),
            }
        )
        assert waiver.control_ids == ["X-009"]

    def test_empty_justification_is_rejected(self) -> None:
        with pytest.raises(Exception):
            Waiver.model_validate(
                {
                    "id": "W-003",
                    "control_ids": ["X-001"],
                    "justification": "",
                    "expiry": str(date.today()),
                }
            )

    def test_load_waivers_from_top_level_key(self, tmp_path: Path) -> None:
        waiver_path = tmp_path / "waivers.yml"
        waiver_path.write_text(
            """
waivers:
  - id: W-010
    control_id: X-001
    justification: Approved exception
    owner: platform
    expiry: 2099-01-01
""".lstrip(),
            encoding="utf-8",
        )

        waivers = load_waivers(waiver_path)
        assert len(waivers) == 1
        assert waivers[0].control_ids == ["X-001"]


class TestApplyWaivers:
    def test_active_waiver_converts_fail_to_waived(self) -> None:
        waiver = _waiver(date.today() + timedelta(days=30))
        results = apply_waivers([_fail_result()], [waiver])
        assert results[0].status == ControlStatus.WAIVED
        assert results[0].waiver_id == "W-001"
        assert results[0].waiver is not None
        assert results[0].waiver["id"] == "W-001"

    def test_expired_waiver_keeps_fail_with_message(self) -> None:
        waiver = _waiver(date(2020, 1, 1))
        results = apply_waivers([_fail_result()], [waiver])
        assert results[0].status == ControlStatus.FAIL
        assert "waiver expired" in results[0].skip_reason
        assert results[0].waiver_expired is True

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
