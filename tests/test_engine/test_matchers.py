"""Tests for assertion matchers (REQ-3.2)."""
from __future__ import annotations


from attest.engine.matchers import evaluate, match_cmp, match_in_list, match_not_in_list


class TestEq:
    def test_equal_strings(self) -> None:
        passed, _ = evaluate("eq", "no", "no")
        assert passed

    def test_not_equal(self) -> None:
        passed, msg = evaluate("eq", "yes", "no")
        assert not passed
        assert "yes" in msg


class TestNe:
    def test_different_values(self) -> None:
        passed, _ = evaluate("ne", "yes", "no")
        assert passed

    def test_same_value_fails(self) -> None:
        passed, msg = evaluate("ne", "no", "no")
        assert not passed
        assert "differ" in msg


class TestContains:
    def test_substring_present(self) -> None:
        passed, _ = evaluate("contains", "hello world", "world")
        assert passed

    def test_substring_absent(self) -> None:
        passed, msg = evaluate("contains", "hello", "world")
        assert not passed
        assert "contain" in msg


class TestRegex:
    def test_matching_pattern(self) -> None:
        passed, _ = evaluate("regex", "192.168.1.1", r"^\d+\.\d+\.\d+\.\d+$")
        assert passed

    def test_non_matching_pattern(self) -> None:
        passed, msg = evaluate("regex", "not-an-ip", r"^\d+\.\d+\.\d+\.\d+$")
        assert not passed
        assert "regex" in msg

    def test_invalid_regex_fails_gracefully(self) -> None:
        passed, msg = evaluate("regex", "value", "[invalid")
        assert not passed
        assert "Invalid regex" in msg


class TestExists:
    def test_value_exists(self) -> None:
        passed, _ = evaluate("exists", "something", None)
        assert passed

    def test_none_fails(self) -> None:
        passed, msg = evaluate("exists", None, None)
        assert not passed
        assert "exist" in msg


class TestNotExists:
    def test_none_passes(self) -> None:
        passed, _ = evaluate("not_exists", None, None)
        assert passed

    def test_value_fails(self) -> None:
        passed, msg = evaluate("not_exists", "value", None)
        assert not passed
        assert "absent" in msg


class TestInList:
    def test_value_in_list(self) -> None:
        passed, _ = match_in_list("/bin/bash", ["/bin/bash", "/bin/sh"])
        assert passed

    def test_value_not_in_list_fails(self) -> None:
        passed, msg = match_in_list("/bin/zsh", ["/bin/bash", "/bin/sh"])
        assert not passed
        assert "/bin/zsh" in msg

    def test_non_list_expected_fails(self) -> None:
        passed, msg = match_in_list("x", "not-a-list")  # type: ignore[arg-type]
        assert not passed
        assert "list" in msg


class TestNotInList:
    def test_value_absent_passes(self) -> None:
        passed, _ = match_not_in_list("/bin/zsh", ["/bin/bash", "/bin/sh"])
        assert passed

    def test_value_present_fails(self) -> None:
        passed, msg = match_not_in_list("/bin/bash", ["/bin/bash", "/bin/sh"])
        assert not passed
        assert "/bin/bash" in msg


class TestCmp:
    def test_version_greater_than(self) -> None:
        passed, _ = match_cmp("2.0.0", {"op": ">", "value": "1.0.0"})
        assert passed

    def test_version_less_than_fails(self) -> None:
        passed, msg = match_cmp("1.0.0", {"op": ">", "value": "2.0.0"})
        assert not passed
        assert "Version check failed" in msg

    def test_numeric_comparison(self) -> None:
        passed, _ = match_cmp("4096", {"op": ">=", "value": "4096"})
        assert passed

    def test_numeric_less_than_fails(self) -> None:
        passed, msg = match_cmp("2048", {"op": ">=", "value": "4096"})
        assert not passed
        # "2048" and "4096" are valid PEP 440 versions; message may read
        # "Version check failed" or "Numeric check failed" depending on parse order.
        assert "check failed" in msg or "failed" in msg

    def test_rpm_epoch_stripped(self) -> None:
        # "2:1.5.0" → "1.5.0", compared against "1.4.0"
        passed, _ = match_cmp("2:1.5.0", {"op": ">", "value": "1.4.0"})
        assert passed

    def test_invalid_value_error(self) -> None:
        passed, msg = match_cmp("not-a-version", {"op": ">", "value": "also-bad"})
        assert not passed
        assert "Cannot compare" in msg

    def test_missing_op_fails(self) -> None:
        passed, msg = match_cmp("1.0", {"value": "1.0"})
        assert not passed
        assert "op" in msg

    def test_non_dict_expected(self) -> None:
        passed, msg = match_cmp("1.0", ">=1.0")  # type: ignore[arg-type]
        assert not passed
        assert "dict" in msg


class TestUnknownOperator:
    def test_unknown_returns_false(self) -> None:
        passed, msg = evaluate("magic", "x", "y")
        assert not passed
        assert "Unknown operator" in msg
