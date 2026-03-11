"""Evaluation pipeline for controls (REQ-3.1, REQ-3.2)."""

from __future__ import annotations

from attest.engine.applicability import evaluate_applicability
from attest.engine.aggregator import aggregate
from attest.engine.cache import ResourceCache
from attest.engine.matchers import evaluate as evaluate_matcher
from attest.engine.result import ControlResult, ControlStatus, TestEvidence
from attest.policy.schemas import Control
from attest.resources.interfaces import ResourceRegistry


def _test_status_from_passed(passed: bool) -> ControlStatus:
    return ControlStatus.PASS if passed else ControlStatus.FAIL


def evaluate_controls(
    *,
    host: str,
    controls: list[Control],
    registry: ResourceRegistry,
    cache: ResourceCache | None = None,
) -> tuple[list[ControlResult], dict[str, int]]:
    """Evaluate all controls for a single host.

    Returns (results, cache_stats_dict).
    """
    cache = cache or ResourceCache()
    control_results: list[ControlResult] = []

    # Build a deterministic predicate context from host label + os_facts.
    os_context: dict[str, object] = {"host": host}
    os_cached = cache.get(host, "os_facts", {})
    if os_cached is not None:
        os_result = os_cached
    else:
        os_result = registry.query("os_facts", {})
        cache.set(host, "os_facts", {}, os_result)

    if isinstance(os_result.data, dict):
        for key, value in sorted(os_result.data.items(), key=lambda item: item[0]):
            os_context[str(key)] = value

    for control in sorted(controls, key=lambda c: c.id):
        decision = evaluate_applicability(
            only_if=control.only_if,
            skip_if=control.skip_if,
            variables=os_context,
        )
        if decision.error:
            control_results.append(
                ControlResult(
                    control_id=control.id,
                    status=ControlStatus.ERROR,
                    tests=[],
                    skip_reason=decision.error,
                )
            )
            continue
        if not decision.applicable:
            control_results.append(
                ControlResult(
                    control_id=control.id,
                    status=ControlStatus.SKIP,
                    tests=[],
                    skip_reason=decision.reason,
                )
            )
            continue

        test_evidence: list[TestEvidence] = []

        for test in control.tests:
            params = dict(test.params)

            cached = cache.get(host, test.resource, params)
            if cached is not None:
                resource_result = cached
            else:
                resource_result = registry.query(test.resource, params)
                cache.set(host, test.resource, params, resource_result)

            if resource_result.errors:
                test_evidence.append(
                    TestEvidence(
                        name=test.name,
                        resource=test.resource,
                        operator=test.operator,
                        expected=test.expected,
                        actual=None,
                        status=ControlStatus.ERROR,
                        message="; ".join(resource_result.errors),
                    )
                )
                continue

            actual_value = resource_result.data

            try:
                passed, message = evaluate_matcher(test.operator, actual_value, test.expected)
            except Exception as exc:  # Defensive safety boundary for malformed matcher inputs.
                test_evidence.append(
                    TestEvidence(
                        name=test.name,
                        resource=test.resource,
                        operator=test.operator,
                        expected=test.expected,
                        actual=actual_value,
                        status=ControlStatus.ERROR,
                        message=f"Matcher execution error: {exc}",
                    )
                )
                continue

            test_evidence.append(
                TestEvidence(
                    name=test.name,
                    resource=test.resource,
                    operator=test.operator,
                    expected=test.expected,
                    actual=actual_value,
                    status=_test_status_from_passed(passed),
                    message=message,
                )
            )

        control_results.append(aggregate(control.id, test_evidence))

    return control_results, {"hits": cache.stats.hits, "misses": cache.stats.misses}
