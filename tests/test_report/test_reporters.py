"""Tests for JUnit and Markdown reporters (REQ-4.2)."""

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
