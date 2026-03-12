"""Evaluation pipeline for controls (REQ-3.1, REQ-3.2, REQ-3.4)."""

from __future__ import annotations

from typing import Any

from attest.engine.applicability import evaluate_applicability
from attest.engine.aggregator import aggregate
from attest.engine.cache import ResourceCache
from attest.engine.matchers import evaluate as evaluate_matcher
from attest.engine.result import ControlResult, ControlStatus, TestEvidence
from attest.policy.schemas import Control, TestAssertion
from attest.resources.interfaces import ResourceRegistry


def _test_status_from_passed(passed: bool) -> ControlStatus:
    return ControlStatus.PASS if passed else ControlStatus.FAIL


def _evaluate_single_test(
    *,
    test: TestAssertion,
    params: dict[str, Any],
    host: str,
    registry: ResourceRegistry,
    cache: ResourceCache,
    label_suffix: str = "",
) -> TestEvidence:
    """Evaluate one test against a single resource call."""
    cached = cache.get(host, test.resource, params)
    if cached is not None:
        resource_result = cached
    else:
        resource_result = registry.query(test.resource, params)
        cache.set(host, test.resource, params, resource_result)

    name = test.name + label_suffix

    if resource_result.errors:
        return TestEvidence(
            name=name,
            resource=test.resource,
            operator=test.operator,
            expected=test.expected,
            actual=None,
            status=ControlStatus.ERROR,
            message="; ".join(resource_result.errors),
        )

    actual_value = resource_result.data

    try:
        passed, message = evaluate_matcher(test.operator, actual_value, test.expected)
    except Exception as exc:
        return TestEvidence(
            name=name,
            resource=test.resource,
            operator=test.operator,
            expected=test.expected,
            actual=actual_value,
            status=ControlStatus.ERROR,
            message=f"Matcher execution error: {exc}",
        )

    return TestEvidence(
        name=name,
        resource=test.resource,
        operator=test.operator,
        expected=test.expected,
        actual=actual_value,
        status=_test_status_from_passed(passed),
        message=message,
    )


def _evaluate_for_each(
    *,
    test: TestAssertion,
    host: str,
    registry: ResourceRegistry,
    cache: ResourceCache,
) -> list[TestEvidence]:
    """Expand a for_each test into per-item TestEvidence entries (REQ-3.4).

    If the collection resource returns an empty list, one SKIP evidence entry is
    emitted so the control knows iteration ran but found nothing.
    """
    collection_params = dict(test.for_each_params)
    collection_resource = test.for_each  # validated non-None by caller

    cached = cache.get(host, collection_resource, collection_params)  # type: ignore[arg-type]
    if cached is not None:
        collection_result = cached
    else:
        collection_result = registry.query(collection_resource, collection_params)  # type: ignore[arg-type]
        cache.set(host, collection_resource, collection_params, collection_result)  # type: ignore[arg-type]

    if collection_result.errors:
        return [
            TestEvidence(
                name=test.name,
                resource=collection_resource,  # type: ignore[arg-type]
                operator=test.operator,
                expected=test.expected,
                actual=None,
                status=ControlStatus.ERROR,
                message=f"for_each collection error: {'; '.join(collection_result.errors)}",
            )
        ]

    items = collection_result.data
    if not isinstance(items, list):
        return [
            TestEvidence(
                name=test.name,
                resource=collection_resource,  # type: ignore[arg-type]
                operator=test.operator,
                expected=test.expected,
                actual=items,
                status=ControlStatus.ERROR,
                message=(
                    f"for_each resource '{collection_resource}' must return a list,"
                    f" got {type(items).__name__}."
                ),
            )
        ]

    if not items:
        return [
            TestEvidence(
                name=test.name,
                resource=test.resource,
                operator=test.operator,
                expected=test.expected,
                actual=None,
                status=ControlStatus.SKIP,
                message="for_each collection is empty; no items to evaluate.",
            )
        ]

    evidence: list[TestEvidence] = []
    for i, item in enumerate(items):
        item_params = dict(test.params)
        item_params[test.for_each_item_key] = item
        evidence.append(
            _evaluate_single_test(
                test=test,
                params=item_params,
                host=host,
                registry=registry,
                cache=cache,
                label_suffix=f"[{i}]",
            )
        )
    return evidence


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
            if test.for_each is not None:
                test_evidence.extend(
                    _evaluate_for_each(
                        test=test,
                        host=host,
                        registry=registry,
                        cache=cache,
                    )
                )
            else:
                test_evidence.append(
                    _evaluate_single_test(
                        test=test,
                        params=dict(test.params),
                        host=host,
                        registry=registry,
                        cache=cache,
                    )
                )

        ctrl_result = aggregate(control.id, test_evidence)
        # Copy overlay provenance from control to result (REQ-4.1).
        if control.overlay_source is not None:
            ctrl_result.overlay_source = control.overlay_source
            ctrl_result.original_impact = control.original_impact
        control_results.append(ctrl_result)

    return control_results, {"hits": cache.stats.hits, "misses": cache.stats.misses}
