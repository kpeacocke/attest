"""Tests for engine evaluator pipeline and caching (REQ-2.3, REQ-3.1)."""

from __future__ import annotations

from attest.engine.evaluator import evaluate_controls
from attest.engine.result import ControlStatus
from attest.policy import schemas as policy_schemas
from attest.policy.schemas import Control
from attest.resources.builtin import build_builtin_registry


def _control(
    *, control_id: str, resource: str, operator: str, expected: object, params: dict | None = None
) -> Control:
    return Control(
        id=control_id,
        title=f"Control {control_id}",
        tests=[
            policy_schemas.TestAssertion(
                name="test",
                resource=resource,
                operator=operator,
                expected=expected,
                params=params or {},
            )
        ],
    )


class TestEvaluator:
    def test_pass_for_known_resource(self) -> None:
        controls = [
            _control(
                control_id="OS-001",
                resource="os_facts",
                operator="exists",
                expected=None,
                params={"field": "system"},
            )
        ]

        results, cache_stats = evaluate_controls(
            host="localhost",
            controls=controls,
            registry=build_builtin_registry(),
        )

        assert results[0].status == ControlStatus.PASS
        # One miss for applicability context (os_facts {}) and one for test params.
        assert cache_stats["misses"] == 2

    def test_error_for_unknown_resource(self) -> None:
        controls = [
            _control(
                control_id="X-001",
                resource="sshd_config",
                operator="eq",
                expected="no",
            )
        ]

        results, _ = evaluate_controls(
            host="localhost",
            controls=controls,
            registry=build_builtin_registry(),
        )

        assert results[0].status == ControlStatus.ERROR
        assert "not implemented" in results[0].tests[0].message

    def test_cache_hits_for_repeated_query(self) -> None:
        controls = [
            _control(
                control_id="OS-001",
                resource="os_facts",
                operator="exists",
                expected=None,
                params={"field": "system"},
            ),
            _control(
                control_id="OS-002",
                resource="os_facts",
                operator="exists",
                expected=None,
                params={"field": "system"},
            ),
        ]

        _, cache_stats = evaluate_controls(
            host="localhost",
            controls=controls,
            registry=build_builtin_registry(),
        )

        # Misses: applicability context + first test resource query.
        assert cache_stats["misses"] == 2
        assert cache_stats["hits"] == 1

    def test_only_if_false_skips_control(self) -> None:
        control = _control(
            control_id="OS-003",
            resource="os_facts",
            operator="exists",
            expected=None,
            params={"field": "system"},
        )
        control.only_if = "system == 'DefinitelyNotThisOS'"

        results, _ = evaluate_controls(
            host="localhost",
            controls=[control],
            registry=build_builtin_registry(),
        )

        assert results[0].status == ControlStatus.SKIP
        assert "only_if not satisfied" in results[0].skip_reason

    def test_skip_if_true_skips_control(self) -> None:
        control = _control(
            control_id="OS-004",
            resource="os_facts",
            operator="exists",
            expected=None,
            params={"field": "system"},
        )
        control.skip_if = "host == 'localhost'"

        results, _ = evaluate_controls(
            host="localhost",
            controls=[control],
            registry=build_builtin_registry(),
        )

        assert results[0].status == ControlStatus.SKIP
        assert "skip_if matched" in results[0].skip_reason

    def test_invalid_predicate_produces_error(self) -> None:
        control = _control(
            control_id="OS-005",
            resource="os_facts",
            operator="exists",
            expected=None,
            params={"field": "system"},
        )
        control.only_if = "unknown_variable == 1"

        results, _ = evaluate_controls(
            host="localhost",
            controls=[control],
            registry=build_builtin_registry(),
        )

        assert results[0].status == ControlStatus.ERROR
        assert "predicate error" in results[0].skip_reason
