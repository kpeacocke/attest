"""Assertion matchers for the evaluation engine (REQ-3.2).

Each matcher returns (passed: bool, message: str).
Failures produce structured evidence: observed, expected, operator, and message.
"""

from __future__ import annotations

import re
from typing import Any

from packaging.version import InvalidVersion, Version


def _to_version(value: Any) -> Version | None:
    """Try to parse value as a PEP 440 version; return None on failure."""
    try:
        return Version(str(value))
    except InvalidVersion:
        return None


def _to_number(value: Any) -> float | None:
    """Try to parse value as a float; return None on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Individual matcher functions: (actual, expected) -> (passed, message)
# ---------------------------------------------------------------------------


def match_eq(actual: Any, expected: Any) -> tuple[bool, str]:
    passed = str(actual) == str(expected)
    if passed:
        return True, ""
    return False, f"Expected '{expected}', got '{actual}'."


def match_ne(actual: Any, expected: Any) -> tuple[bool, str]:
    passed = str(actual) != str(expected)
    if passed:
        return True, ""
    return False, f"Expected value to differ from '{expected}', but it matched."


def match_contains(actual: Any, expected: Any) -> tuple[bool, str]:
    passed = str(expected) in str(actual)
    if passed:
        return True, ""
    return False, f"Expected '{actual}' to contain '{expected}'."


def match_regex(actual: Any, expected: Any) -> tuple[bool, str]:
    try:
        passed = bool(re.search(str(expected), str(actual)))
    except re.error as exc:
        return False, f"Invalid regex '{expected}': {exc}."
    if passed:
        return True, ""
    return False, f"Expected '{actual}' to match regex '{expected}'."


def match_exists(actual: Any, _expected: Any = None) -> tuple[bool, str]:
    passed = actual is not None
    if passed:
        return True, ""
    return False, "Expected value to exist, but it was None."


def match_not_exists(actual: Any, _expected: Any = None) -> tuple[bool, str]:
    passed = actual is None
    if passed:
        return True, ""
    return False, f"Expected value to be absent, but got '{actual}'."


def match_in_list(actual: Any, expected: list[Any]) -> tuple[bool, str]:
    """Assert actual is one of the values in expected list."""
    if not isinstance(expected, list):
        return False, f"'in_list' expected a list, got {type(expected).__name__}."
    passed = actual in expected
    if passed:
        return True, ""
    return False, f"Expected '{actual}' to be one of {expected}."


def match_not_in_list(actual: Any, expected: list[Any]) -> tuple[bool, str]:
    """Assert actual is not in the expected list."""
    if not isinstance(expected, list):
        return False, f"'not_in_list' expected a list, got {type(expected).__name__}."
    passed = actual not in expected
    if passed:
        return True, ""
    return False, f"Expected '{actual}' to not be in {expected}."


_CMP_OPS = {"<", "<=", ">", ">=", "==", "!="}


def match_cmp(actual: Any, expected: Any) -> tuple[bool, str]:
    """Version-aware and numeric comparison.

    expected must be a dict: {"op": "<|<=|>|>=|==|!=", "value": "..."}
    Supports PEP 440 version strings and numeric values (REQ-3.2).
    RPM epoch notation (e.g. "2:1.0-1") is normalised by stripping the epoch prefix.
    """
    if not isinstance(expected, dict):
        return False, (
            f"'cmp' expected a dict with 'op' and 'value', got {type(expected).__name__}."
        )

    op = expected.get("op")
    cmp_value = expected.get("value")

    if op not in _CMP_OPS:
        return False, f"'cmp' op '{op}' is not valid; must be one of {sorted(_CMP_OPS)}."

    # Normalise RPM epoch notation (e.g. "2:1.0-1" -> "1.0-1").
    def _strip_rpm_epoch(v: str) -> str:
        parts = str(v).split(":", 1)
        return parts[1] if len(parts) == 2 and parts[0].isdigit() else str(v)

    actual_str = _strip_rpm_epoch(str(actual)) if actual is not None else ""
    cmp_str = _strip_rpm_epoch(str(cmp_value))

    # Try version comparison first.
    actual_ver = _to_version(actual_str)
    cmp_ver = _to_version(cmp_str)

    if actual_ver is not None and cmp_ver is not None:
        ops_map = {
            "<": actual_ver < cmp_ver,
            "<=": actual_ver <= cmp_ver,
            ">": actual_ver > cmp_ver,
            ">=": actual_ver >= cmp_ver,
            "==": actual_ver == cmp_ver,
            "!=": actual_ver != cmp_ver,
        }
        passed = ops_map[op]  # type: ignore[literal-required]
        if passed:
            return True, ""
        return False, f"Version check failed: '{actual_str}' {op} '{cmp_str}' is false."

    # Try numeric comparison.
    actual_num = _to_number(actual_str)
    cmp_num = _to_number(cmp_str)

    if actual_num is not None and cmp_num is not None:
        num_ops = {
            "<": actual_num < cmp_num,
            "<=": actual_num <= cmp_num,
            ">": actual_num > cmp_num,
            ">=": actual_num >= cmp_num,
            "==": actual_num == cmp_num,
            "!=": actual_num != cmp_num,
        }
        passed = num_ops[op]  # type: ignore[literal-required]
        if passed:
            return True, ""
        return False, f"Numeric check failed: '{actual_str}' {op} '{cmp_str}' is false."

    return False, (
        f"Cannot compare '{actual_str}' {op} '{cmp_str}': "
        "neither value could be parsed as a version or number."
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_MATCHERS = {
    "eq": match_eq,
    "ne": match_ne,
    "contains": match_contains,
    "regex": match_regex,
    "exists": match_exists,
    "not_exists": match_not_exists,
    "in_list": match_in_list,
    "not_in_list": match_not_in_list,
    "cmp": match_cmp,
}


def evaluate(operator: str, actual: Any, expected: Any) -> tuple[bool, str]:
    """Dispatch to the appropriate matcher.

    Returns (passed, message). Unknown operators return (False, error message).
    """
    fn = _MATCHERS.get(operator)
    if fn is None:
        return False, f"Unknown operator '{operator}'."
    return fn(actual, expected)
