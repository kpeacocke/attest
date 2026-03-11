"""JUnit XML reporter (REQ-4.2).

Produces a JUnit-compatible XML report from the canonical report dict.
One <testcase> per control; failures and skips map correctly.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any


def build_junit(report: dict[str, Any]) -> str:
    """Build a JUnit XML string from a canonical report.

    Compatible with common CI tooling (Jenkins, GitHub Actions test summary).
    """
    results = report.get("results", [])
    profile = report.get("profile", {})
    suite_name = f"{profile.get('name', 'attest')} @ {report.get('host', 'unknown')}"

    counts = report.get("summary", {}).get("counts", {})
    failures = counts.get("FAIL", 0)
    errors = counts.get("ERROR", 0)
    skipped = counts.get("SKIP", 0) + counts.get("WAIVED", 0)
    total = len(results)

    suite = ET.Element(
        "testsuite",
        attrib={
            "name": suite_name,
            "tests": str(total),
            "failures": str(failures),
            "errors": str(errors),
            "skipped": str(skipped),
            "timestamp": report.get("timestamp", ""),
        },
    )

    for result in results:
        control_id = result.get("control_id", "unknown")
        title = result.get("title", control_id)
        status = result.get("status", "ERROR")

        tc = ET.SubElement(
            suite,
            "testcase",
            attrib={
                "classname": profile.get("name", "attest"),
                "name": f"{control_id}: {title}",
            },
        )

        if status == "FAIL":
            fail_tests = [t for t in result.get("tests", []) if t.get("status") == "FAIL"]
            messages = "; ".join(
                t.get("message", "") or f"expected '{t.get('expected')}', got '{t.get('actual')}'"
                for t in fail_tests
            )
            ET.SubElement(tc, "failure", attrib={"message": messages or "Control failed."})

        elif status == "ERROR":
            error_tests = [t for t in result.get("tests", []) if t.get("status") == "ERROR"]
            messages = "; ".join(t.get("message", "evaluation error") for t in error_tests)
            ET.SubElement(tc, "error", attrib={"message": messages or "Evaluation error."})

        elif status in {"SKIP", "WAIVED"}:
            reason = result.get("skip_reason", "") or (
                f"Waived (id: {result.get('waiver_id', 'unknown')})"
                if status == "WAIVED"
                else "Control skipped."
            )
            skipped_el = ET.SubElement(tc, "skipped")
            skipped_el.text = reason

    tree = ET.ElementTree(suite)
    ET.indent(tree, space="  ")
    return ET.tostring(suite, encoding="unicode", xml_declaration=False)


def write_junit(report: dict[str, Any], path: str) -> None:
    """Write a JUnit XML report to a file path."""
    xml_content = build_junit(report)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        fh.write(xml_content)
        fh.write("\n")
