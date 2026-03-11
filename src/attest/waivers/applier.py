"""Apply waivers to control results (REQ-5.2)."""

from __future__ import annotations

from datetime import date

from attest.engine.result import ControlResult, ControlStatus
from attest.waivers.schema import Waiver


def apply_waivers(
    results: list[ControlResult],
    waivers: list[Waiver],
    as_of: date | None = None,
) -> list[ControlResult]:
    """Apply waivers to a list of ControlResults.

    REQ-5.2 semantics:
    - Active waiver on a FAIL → WAIVED (waiver_id recorded).
    - Expired waiver on a FAIL → FAIL with message "waiver expired" appended.
    - PASS, SKIP, ERROR controls are not modified by waivers.
    """
    waiver_index: dict[str, list[Waiver]] = {}
    for w in waivers:
        for cid in w.control_ids:
            waiver_index.setdefault(cid, []).append(w)

    updated: list[ControlResult] = []
    for result in results:
        matching = waiver_index.get(result.control_id, [])
        if result.status == ControlStatus.FAIL and matching:
            active = [w for w in matching if w.is_active(as_of)]
            expired = [w for w in matching if w.is_expired(as_of)]

            if active:
                # Use the first active waiver (sorted by expiry descending for stability).
                best = sorted(active, key=lambda w: w.expiry, reverse=True)[0]
                result = ControlResult(
                    control_id=result.control_id,
                    status=ControlStatus.WAIVED,
                    tests=result.tests,
                    waiver_id=best.id,
                    overlay_source=result.overlay_source,
                    original_impact=result.original_impact,
                )
            elif expired:
                # Surface expired waiver explicitly as a FAIL with a flag message.
                best_expired = sorted(expired, key=lambda w: w.expiry, reverse=True)[0]
                result = ControlResult(
                    control_id=result.control_id,
                    status=ControlStatus.FAIL,
                    tests=result.tests,
                    skip_reason=f"waiver expired (waiver id: {best_expired.id})",
                    overlay_source=result.overlay_source,
                    original_impact=result.original_impact,
                )

        updated.append(result)

    return updated
