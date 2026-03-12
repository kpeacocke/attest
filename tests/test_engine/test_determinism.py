"""Determinism tests for the evaluation engine and canonical report (REQ-3.3, REQ-7.4).

Verifies that identical profile inputs produce equivalent canonical JSON in
both local and job execution contexts.
"""

from __future__ import annotations

import json

from attest.engine.evaluator import evaluate_controls
from attest.policy import schemas as ps
from attest.policy.schemas import Control, ControlTags, Profile
from attest.redaction import Redactor
from attest.report.canonical import build_report
from attest.resources.interfaces import ResourceRegistry, ResourceResult


def _static_registry(*resource_names: str, data: object = True) -> ResourceRegistry:
    """Build a registry where every listed resource always returns *data*."""

    class _Handler:
        def __init__(self, value: object) -> None:
            self._value = value

        def query(self, params: dict) -> ResourceResult:
            return ResourceResult(data=self._value, errors=[], timings={})

    registry = ResourceRegistry()
    registry.register("os_facts", _Handler({"system": "Linux"}))
    for name in resource_names:
        registry.register(name, _Handler(data))
    return registry


def _controls() -> list[Control]:
    return [
        Control(
            id="DET-001",
            title="Determinism test control A",
            impact=0.7,
            tags=ControlTags(nist=["AC-3"], cis_level=1),
            tests=[ps.TestAssertion(name="t1", resource="file", operator="exists", expected=None)],
        ),
        Control(
            id="DET-002",
            title="Determinism test control B",
            impact=0.5,
            tests=[ps.TestAssertion(name="t2", resource="file", operator="eq", expected=True)],
        ),
    ]


def _profile() -> Profile:
    return Profile(name="det-profile", title="Determinism Profile", version="1.0.0")


class TestEvaluationDeterminism:
    """REQ-3.3: identical inputs → identical evaluation outcomes."""

    def test_same_inputs_produce_same_control_order(self) -> None:
        registry = _static_registry("file")
        controls = _controls()

        results_a, _ = evaluate_controls(host="localhost", controls=controls, registry=registry)
        results_b, _ = evaluate_controls(host="localhost", controls=controls, registry=registry)

        assert [r.control_id for r in results_a] == [r.control_id for r in results_b]

    def test_same_inputs_produce_same_statuses(self) -> None:
        registry = _static_registry("file")
        controls = _controls()

        results_a, _ = evaluate_controls(host="localhost", controls=controls, registry=registry)
        results_b, _ = evaluate_controls(host="localhost", controls=controls, registry=registry)

        statuses_a = [r.status for r in results_a]
        statuses_b = [r.status for r in results_b]
        assert statuses_a == statuses_b

    def test_control_ids_are_sorted_in_results(self) -> None:
        """Results must be sorted by control_id for stable diff comparisons (REQ-7.4)."""
        registry = _static_registry("file")
        # Provide controls in reverse order to confirm sorting.
        controls = list(reversed(_controls()))

        results, _ = evaluate_controls(host="localhost", controls=controls, registry=registry)

        ids = [r.control_id for r in results]
        assert ids == sorted(ids)


class TestCanonicalReportDeterminism:
    """REQ-3.3: canonical JSON is structurally equivalent across two runs with same inputs."""

    def _build(self, run_id: str) -> dict:
        registry = _static_registry("file")
        controls = _controls()
        results, _ = evaluate_controls(host="localhost", controls=controls, registry=registry)
        return build_report(
            _profile(),
            controls,
            results,
            run_id=run_id,
            redactor=Redactor([]),
        )

    def test_same_run_id_produces_stable_structure(self) -> None:
        """With the same run_id, all fields except timestamp should be identical."""
        report_a = self._build("fixed-run-id")
        report_b = self._build("fixed-run-id")

        # Normalise timestamps before comparing.
        report_a["timestamp"] = report_b["timestamp"] = "NORMALISED"

        assert json.dumps(report_a, sort_keys=True) == json.dumps(report_b, sort_keys=True)

    def test_results_sorted_by_control_id(self) -> None:
        report = self._build("test")
        ids = [r["control_id"] for r in report["results"]]
        assert ids == sorted(ids)

    def test_tag_summaries_keys_are_sorted(self) -> None:
        report = self._build("test")
        nist_keys = list(report["tag_summaries"]["nist"].keys())
        assert nist_keys == sorted(nist_keys)

    def test_local_and_job_context_equivalent(self) -> None:
        """Simulates local vs job execution: same profile on same host should match (REQ-3.3)."""
        registry = _static_registry("file")
        controls = _controls()

        # Simulate two independent evaluations (e.g. local dev vs CI job).
        results_local, _ = evaluate_controls(host="ci-host", controls=controls, registry=registry)
        results_job, _ = evaluate_controls(host="ci-host", controls=controls, registry=registry)

        local_report = build_report(
            _profile(), controls, results_local, run_id="r1", redactor=Redactor([])
        )
        job_report = build_report(
            _profile(), controls, results_job, run_id="r1", redactor=Redactor([])
        )

        # Normalise timestamps.
        local_report["timestamp"] = job_report["timestamp"] = "NORMALISED"

        assert json.dumps(local_report, sort_keys=True) == json.dumps(job_report, sort_keys=True)
