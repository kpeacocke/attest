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


class TestForEachEvaluator:
    """REQ-3.4: declarative for_each iteration in TestAssertion."""

    def _registry_with(self, **name_to_data: object) -> object:
        """Build a minimal ResourceRegistry backed by simple in-memory data."""
        from attest.resources.interfaces import ResourceRegistry, ResourceResult

        class _StaticHandler:
            def __init__(self, data: object) -> None:
                self._data = data

            def query(self, params: dict) -> ResourceResult:
                return ResourceResult(data=self._data, errors=[], timings={})

        registry = ResourceRegistry()
        for name, data in name_to_data.items():
            registry.register(name, _StaticHandler(data))
        # Always add os_facts for applicability context.
        if "os_facts" not in name_to_data:
            registry.register("os_facts", _StaticHandler({"system": "Linux"}))
        return registry

    def _for_each_control(
        self,
        *,
        control_id: str = "FE-001",
        collection_resource: str,
        collection_data: object,
        test_resource: str,
        operator: str,
        expected: object,
        for_each_item_key: str = "item",
    ) -> tuple[Control, object]:
        registry = self._registry_with(
            **{collection_resource: collection_data, test_resource: expected},
        )
        control = Control(
            id=control_id,
            title=f"ForEach Control {control_id}",
            tests=[
                policy_schemas.TestAssertion(
                    name="loop-test",
                    resource=test_resource,
                    operator=operator,
                    expected=expected,
                    for_each=collection_resource,
                    for_each_item_key=for_each_item_key,
                )
            ],
        )
        return control, registry

    def test_iterates_over_list_and_emits_per_item_evidence(self) -> None:
        from attest.resources.interfaces import ResourceRegistry, ResourceResult

        class _EchoHandler:
            """Returns the 'item' param as data, always passes eq check."""

            def query(self, params: dict) -> ResourceResult:
                return ResourceResult(data=params.get("item"), errors=[], timings={})

        registry = ResourceRegistry()
        registry.register("os_facts", _EchoHandler())
        registry.register(
            "items_collection",
            type("_H", (), {"query": lambda self, p: ResourceResult(data=["a", "b", "c"])})(),
        )
        registry.register("echo", _EchoHandler())

        control = Control(
            id="FE-001",
            title="ForEach Echo",
            tests=[
                policy_schemas.TestAssertion(
                    name="check-item",
                    resource="echo",
                    operator="exists",
                    expected=None,
                    for_each="items_collection",
                    for_each_item_key="item",
                )
            ],
        )

        results, _ = evaluate_controls(
            host="localhost",
            controls=[control],
            registry=registry,
        )

        assert results[0].status == ControlStatus.PASS
        # Three items → three evidence entries
        assert len(results[0].tests) == 3
        assert results[0].tests[0].name == "check-item[0]"
        assert results[0].tests[1].name == "check-item[1]"
        assert results[0].tests[2].name == "check-item[2]"

    def test_empty_collection_produces_skip_evidence(self) -> None:
        from attest.resources.interfaces import ResourceRegistry, ResourceResult

        registry = ResourceRegistry()
        registry.register(
            "os_facts",
            type("H", (), {"query": lambda s, p: ResourceResult(data={"system": "Linux"})})(),
        )
        registry.register(
            "empty_list", type("H", (), {"query": lambda s, p: ResourceResult(data=[])})()
        )
        registry.register(
            "echo", type("H", (), {"query": lambda s, p: ResourceResult(data=p.get("item"))})()
        )

        control = Control(
            id="FE-002",
            title="ForEach Empty",
            tests=[
                policy_schemas.TestAssertion(
                    name="check-empty",
                    resource="echo",
                    operator="exists",
                    expected=None,
                    for_each="empty_list",
                )
            ],
        )

        results, _ = evaluate_controls(
            host="localhost",
            controls=[control],
            registry=registry,
        )

        assert results[0].status == ControlStatus.SKIP
        assert len(results[0].tests) == 1
        assert "empty" in results[0].tests[0].message

    def test_collection_resource_error_propagates(self) -> None:
        from attest.resources.interfaces import ResourceRegistry, ResourceResult

        registry = ResourceRegistry()
        registry.register(
            "os_facts",
            type("H", (), {"query": lambda s, p: ResourceResult(data={"system": "Linux"})})(),
        )
        registry.register(
            "broken_collection",
            type(
                "H",
                (),
                {"query": lambda s, p: ResourceResult(data=None, errors=["connection refused"])},
            )(),
        )
        registry.register("echo", type("H", (), {"query": lambda s, p: ResourceResult(data="x")})())

        control = Control(
            id="FE-003",
            title="ForEach Error",
            tests=[
                policy_schemas.TestAssertion(
                    name="check-error",
                    resource="echo",
                    operator="exists",
                    expected=None,
                    for_each="broken_collection",
                )
            ],
        )

        results, _ = evaluate_controls(
            host="localhost",
            controls=[control],
            registry=registry,
        )

        assert results[0].status == ControlStatus.ERROR
        assert "connection refused" in results[0].tests[0].message

    def test_collection_returning_non_list_produces_error(self) -> None:
        from attest.resources.interfaces import ResourceRegistry, ResourceResult

        registry = ResourceRegistry()
        registry.register(
            "os_facts",
            type("H", (), {"query": lambda s, p: ResourceResult(data={"system": "Linux"})})(),
        )
        registry.register(
            "scalar_resource",
            type("H", (), {"query": lambda s, p: ResourceResult(data="not-a-list")})(),
        )
        registry.register("echo", type("H", (), {"query": lambda s, p: ResourceResult(data="x")})())

        control = Control(
            id="FE-004",
            title="ForEach Scalar Error",
            tests=[
                policy_schemas.TestAssertion(
                    name="check-scalar",
                    resource="echo",
                    operator="exists",
                    expected=None,
                    for_each="scalar_resource",
                )
            ],
        )

        results, _ = evaluate_controls(
            host="localhost",
            controls=[control],
            registry=registry,
        )

        assert results[0].status == ControlStatus.ERROR
        assert "must return a list" in results[0].tests[0].message


class TestOverlayProvenanceInEvaluator:
    """REQ-4.1: overlay provenance is propagated from Control to ControlResult."""

    def _static_registry(self) -> object:
        from attest.resources.interfaces import ResourceRegistry, ResourceResult

        class _OsHandler:
            def query(self, params: dict) -> ResourceResult:
                return ResourceResult(data={"system": "Linux"}, errors=[], timings={})

        class _PassHandler:
            def query(self, params: dict) -> ResourceResult:
                return ResourceResult(data=True, errors=[], timings={})

        registry = ResourceRegistry()
        registry.register("os_facts", _OsHandler())
        registry.register("file", _PassHandler())
        return registry

    def test_overlay_source_propagated_to_result(self) -> None:
        from attest.policy import schemas as ps

        ctrl = Control(
            id="OV-001",
            title="Overlaid control",
            tests=[ps.TestAssertion(name="t", resource="file", operator="exists", expected=None)],
        )
        ctrl.overlay_source = "hardening-overlay"
        ctrl.original_impact = 0.3

        results, _ = evaluate_controls(
            host="localhost",
            controls=[ctrl],
            registry=self._static_registry(),
        )

        assert results[0].overlay_source == "hardening-overlay"

    def test_original_impact_propagated_to_result(self) -> None:
        from attest.policy import schemas as ps

        ctrl = Control(
            id="OV-002",
            title="Overlaid control",
            impact=0.9,
            tests=[ps.TestAssertion(name="t", resource="file", operator="exists", expected=None)],
        )
        ctrl.overlay_source = "cis-overlay"
        ctrl.original_impact = 0.5

        results, _ = evaluate_controls(
            host="localhost",
            controls=[ctrl],
            registry=self._static_registry(),
        )

        assert results[0].original_impact == 0.5

    def test_no_overlay_source_leaves_fields_none(self) -> None:
        from attest.policy import schemas as ps

        ctrl = Control(
            id="BASE-001",
            title="Base control",
            tests=[ps.TestAssertion(name="t", resource="file", operator="exists", expected=None)],
        )

        results, _ = evaluate_controls(
            host="localhost",
            controls=[ctrl],
            registry=self._static_registry(),
        )

        assert results[0].overlay_source is None
        assert results[0].original_impact is None
