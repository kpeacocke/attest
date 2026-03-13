"""Tests for JUnit and Markdown reporters (REQ-4.2, REQ-7.3, REQ-8.2)."""

from __future__ import annotations

from attest.engine import result as engine_result
from attest.engine.result import ControlResult, ControlStatus
from attest.policy import schemas as policy_schemas
from attest.policy.schemas import Control, Profile
from attest.report.canonical import build_report
from attest.report.junit import build_junit
from attest.report.markdown import build_markdown
from attest.report.summary import build_summary


def _base_report(status: ControlStatus = ControlStatus.PASS) -> dict:
    profile = Profile(name="p", title="P", version="1.0")
    ctrl = Control(
        id="X-001",
        title="Test",
        tests=[policy_schemas.TestAssertion(name="t", resource="r", operator="eq", expected="x")],
    )
    result = ControlResult(
        control_id="X-001",
        status=status,
        tests=[
            engine_result.TestEvidence(
                name="t",
                resource="r",
                operator="eq",
                expected="x",
                actual="x" if status == ControlStatus.PASS else "y",
                status=status,
                message="" if status == ControlStatus.PASS else "Expected 'x', got 'y'.",
            )
        ],
    )
    return build_report(profile, [ctrl], [result], run_id="test-run")


class TestJUnit:
    def test_pass_produces_testcase(self) -> None:
        xml = build_junit(_base_report(ControlStatus.PASS))
        assert "<testcase" in xml
        # The <testsuite> element has a 'failures' attribute; check the element is absent.
        assert "<failure" not in xml

    def test_fail_produces_failure_element(self) -> None:
        xml = build_junit(_base_report(ControlStatus.FAIL))
        assert "<failure" in xml

    def test_error_produces_error_element(self) -> None:
        xml = build_junit(_base_report(ControlStatus.ERROR))
        assert "<error" in xml

    def test_skip_produces_skipped_element(self) -> None:
        xml = build_junit(_base_report(ControlStatus.SKIP))
        assert "<skipped" in xml


class TestMarkdown:
    def test_contains_summary_table(self) -> None:
        md = build_markdown(_base_report(ControlStatus.PASS))
        assert "| PASS |" in md

    def test_failures_section(self) -> None:
        md = build_markdown(_base_report(ControlStatus.FAIL))
        assert "## Failures" in md
        assert "X-001" in md

    def test_pass_no_failures_section(self) -> None:
        md = build_markdown(_base_report(ControlStatus.PASS))
        assert "## Failures" not in md

    def test_failures_section_shows_impact(self) -> None:
        """REQ-8.2: impact is shown for each failing control (triage readability)."""
        md = build_markdown(_base_report(ControlStatus.FAIL))
        assert "impact:" in md

    def test_failures_section_shows_host(self) -> None:
        """REQ-8.2: host context is shown in the failures section header."""
        md = build_markdown(_base_report(ControlStatus.FAIL))
        assert "host:" in md

    def test_top_failing_controls_in_summary(self) -> None:
        """REQ-8.2: executive summary includes top failing controls table."""
        md = build_markdown(_base_report(ControlStatus.FAIL))
        assert "Top failing controls" in md

    def test_no_top_failures_when_all_pass(self) -> None:
        """REQ-8.2: top failures section absent when there are no failures."""
        md = build_markdown(_base_report(ControlStatus.PASS))
        assert "Top failing controls" not in md


class TestSummary:
    def test_summary_fields_present(self) -> None:
        summary = build_summary(_base_report(ControlStatus.FAIL))
        assert "fail_count" in summary
        assert summary["fail_count"] == 1
        assert summary["pass_count"] == 0
        assert "risk_score" in summary
        assert "run_id" in summary


class TestSingleRunAllReporters:
    """REQ-4.2: all reporters can be generated from a single canonical report dict."""

    def test_all_reporters_accept_same_report(self) -> None:
        """JUnit, Markdown, and Summary all consume the same canonical dict without error."""
        report = _base_report(ControlStatus.FAIL)

        junit_xml = build_junit(report)
        markdown_text = build_markdown(report)
        summary_dict = build_summary(report)

        assert "<testsuite" in junit_xml
        assert "# Attest Run Report" in markdown_text
        assert "fail_count" in summary_dict

    def test_reporters_do_not_mutate_canonical_report(self) -> None:
        """Calling reporters must not mutate the canonical report dict (REQ-7.4)."""
        import copy

        report = _base_report(ControlStatus.PASS)
        original = copy.deepcopy(report)

        build_junit(report)
        build_markdown(report)
        build_summary(report)

        assert report == original


class TestMarkdownExpiredWaivers:
    """REQ-8.2: expired waivers are visually distinct in Markdown output."""

    def _expired_waiver_report(self) -> dict:
        """Build a report where one control has an expired waiver (status=FAIL, waiver_expired)."""
        profile = Profile(name="p", title="P", version="1.0")
        ctrl = Control(
            id="EW-001",
            title="Expired waiver test",
            impact=0.8,
            tests=[
                policy_schemas.TestAssertion(name="t", resource="r", operator="eq", expected="x")
            ],
        )
        result = ControlResult(
            control_id="EW-001",
            status=ControlStatus.FAIL,
            waiver_id="W-EXP",
            waiver_expired=True,
            skip_reason="waiver expired (waiver id: W-EXP)",
            tests=[
                engine_result.TestEvidence(
                    name="t",
                    resource="r",
                    operator="eq",
                    expected="x",
                    actual="y",
                    status=ControlStatus.FAIL,
                    message="Expected 'x', got 'y'.",
                )
            ],
        )
        return build_report(profile, [ctrl], [result], run_id="exp-run")

    def test_expired_waiver_section_present(self) -> None:
        """REQ-8.2: expired waivers get their own section."""
        md = build_markdown(self._expired_waiver_report())
        assert "Expired waivers" in md

    def test_expired_waiver_not_in_regular_failures(self) -> None:
        """REQ-8.2: expired waivers are kept out of the generic Failures section."""
        md = build_markdown(self._expired_waiver_report())
        assert "## Failures" not in md

    def test_expired_waiver_policy_breach_warning(self) -> None:
        """REQ-8.2: expired waiver section includes policy breach guidance."""
        md = build_markdown(self._expired_waiver_report())
        assert "policy breach" in md.lower()

    def test_expired_waiver_shows_waiver_id(self) -> None:
        md = build_markdown(self._expired_waiver_report())
        assert "W-EXP" in md


class TestReportSchemaContract:
    """REQ-7.3: canonical report has stable, documented schema fields."""

    def test_required_fields_present(self) -> None:
        """All REQ-4.1 mandatory schema fields are present in the canonical report."""
        report = _base_report(ControlStatus.PASS)
        for field in (
            "schema_version",
            "run_id",
            "timestamp",
            "host",
            "profile",
            "summary",
            "results",
            "tag_summaries",
        ):
            assert field in report, f"Missing required field: {field}"

    def test_schema_version_is_string(self) -> None:
        report = _base_report(ControlStatus.PASS)
        assert isinstance(report["schema_version"], str)

    def test_summary_has_counts_and_risk_score(self) -> None:
        report = _base_report(ControlStatus.PASS)
        assert "counts" in report["summary"]
        assert "risk_score" in report["summary"]

    def test_results_entries_have_required_fields(self) -> None:
        report = _base_report(ControlStatus.FAIL)
        for entry in report["results"]:
            for field in ("control_id", "status", "impact", "tests"):
                assert field in entry, f"Result entry missing: {field}"


class TestSummaryDeterminism:
    """REQ-7.4: summary artefact fields are in stable, documented order."""

    def test_summary_key_order_is_stable(self) -> None:
        """build_summary returns the same keys in the same order on repeated calls."""
        report = _base_report(ControlStatus.FAIL)
        keys_a = list(build_summary(report).keys())
        keys_b = list(build_summary(report).keys())
        assert keys_a == keys_b

    def test_summary_contains_all_documented_fields(self) -> None:
        """REQ-4.4: all documented summary fields are present."""
        summary = build_summary(_base_report(ControlStatus.PASS))
        for field in (
            "schema_version",
            "run_id",
            "timestamp",
            "profile",
            "host",
            "fail_count",
            "error_count",
            "waived_count",
            "pass_count",
            "skip_count",
            "risk_score",
        ):
            assert field in summary, f"Summary missing documented field: {field}"
