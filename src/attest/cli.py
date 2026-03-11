"""Attest CLI — thin entry point; domain logic lives in submodules (REQ-7.1, REQ-7.2)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="attest",
        description="Attest: Ansible-native compliance-as-code.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("version", help="Show version information.")

    v = sub.add_parser("validate", help="Validate a profile directory.")
    v.add_argument("profile_dir", help="Path to the profile directory containing profile.yml.")

    r = sub.add_parser("run", help="Run a profile against a target (local host).")
    r.add_argument("profile_dir", help="Path to the profile directory containing profile.yml.")
    r.add_argument(
        "--out",
        default=".",
        help="Output directory for reports (default: current directory).",
    )
    r.add_argument(
        "--host",
        default="localhost",
        help="Host label to embed in the report (default: localhost).",
    )
    r.add_argument(
        "--format",
        dest="formats",
        action="append",
        choices=["json", "junit", "markdown", "summary"],
        default=None,
        help="Report formats to emit (may be repeated; default: json summary).",
    )

    d = sub.add_parser("diff", help="Diff two canonical JSON reports.")
    d.add_argument("report_a", help="Path to the first (baseline) report.")
    d.add_argument("report_b", help="Path to the second (current) report.")
    d.add_argument("--out", default=".", help="Output directory for diff artefacts.")

    return p


def _cmd_validate(args: argparse.Namespace) -> int:
    """Validate a profile directory (REQ-7.1)."""
    from pydantic import ValidationError

    from attest.policy.loader import LoadError, load_profile_bundle
    from attest.policy.validator import validate_bundle

    profile_dir = Path(args.profile_dir)
    try:
        profile, controls = load_profile_bundle(profile_dir)
    except LoadError as exc:
        print(f"Load error: {exc}", file=sys.stderr)
        return 4
    except ValidationError as exc:
        print(f"Schema validation error:\n{exc}", file=sys.stderr)
        return 4

    result = validate_bundle(profile, controls)
    if result.valid:
        print(
            f"Profile '{profile.name}' v{profile.version} is valid "
            f"({len(controls)} controls)."
        )
        return 0

    print(f"Validation failed ({len(result.errors)} error(s)):", file=sys.stderr)
    for err in result.errors:
        print(f"  - {err}", file=sys.stderr)
    return 4


def _cmd_run(args: argparse.Namespace) -> int:
    """Run a profile against the local host (REQ-7.1, REQ-7.2).

    This is a bootstrap implementation: resources are not yet gathered from
    a live system.  The engine evaluates controls against an empty fact set,
    which means resource-dependent tests produce ERROR status. This is the
    correct bootstrap behaviour — it exercises the full pipeline end-to-end.
    """
    from pydantic import ValidationError

    from attest.policy.loader import LoadError, load_profile_bundle
    from attest.policy.validator import validate_bundle
    from attest.report.canonical import build_report, write_report
    from attest.report.junit import write_junit
    from attest.report.markdown import write_markdown
    from attest.report.summary import build_summary, write_summary

    profile_dir = Path(args.profile_dir)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        profile, controls = load_profile_bundle(profile_dir)
    except LoadError as exc:
        print(f"Load error: {exc}", file=sys.stderr)
        return 4
    except ValidationError as exc:
        print(f"Schema validation error:\n{exc}", file=sys.stderr)
        return 4

    v_result = validate_bundle(profile, controls)
    if not v_result.valid:
        print("Profile validation failed:", file=sys.stderr)
        for err in v_result.errors:
            print(f"  - {err}", file=sys.stderr)
        return 4

    # Bootstrap: no live resources yet — produce ERROR results for all controls.
    from attest.engine.result import ControlResult, ControlStatus, TestEvidence

    results: list[ControlResult] = []
    for ctrl in controls:
        evidence = [
            TestEvidence(
                name=test.name,
                resource=test.resource,
                operator=test.operator,
                expected=test.expected,
                actual=None,
                status=ControlStatus.ERROR,
                message=(
                    "Resource collection is not implemented in this bootstrap build. "
                    "Install an Attest resource collection to gather facts."
                ),
            )
            for test in ctrl.tests
        ]
        results.append(
            ControlResult(
                control_id=ctrl.id,
                status=ControlStatus.ERROR if evidence else ControlStatus.SKIP,
                tests=evidence,
                skip_reason="" if evidence else "No tests defined.",
            )
        )

    report = build_report(profile, controls, results, host=args.host)

    formats = set(args.formats or ["json", "summary"])

    exit_code = 0
    counts = report["summary"]["counts"]
    if counts.get("FAIL", 0):
        exit_code = 2
    elif counts.get("ERROR", 0):
        exit_code = 3

    if "json" in formats:
        json_path = str(out_dir / "report.json")
        write_report(report, json_path)
        print(f"Report written: {json_path}")

    if "junit" in formats:
        junit_path = str(out_dir / "report.xml")
        write_junit(report, junit_path)
        print(f"JUnit report written: {junit_path}")

    if "markdown" in formats:
        md_path = str(out_dir / "report.md")
        write_markdown(report, md_path)
        print(f"Markdown report written: {md_path}")

    if "summary" in formats:
        summary_path = str(out_dir / "attest-summary.json")
        write_summary(build_summary(report), summary_path)
        print(f"Summary written: {summary_path}")

    # Print run summary to terminal (REQ-8.1).
    print(
        f"\nRun complete — PASS:{counts.get('PASS',0)} "
        f"FAIL:{counts.get('FAIL',0)} "
        f"ERROR:{counts.get('ERROR',0)} "
        f"SKIP:{counts.get('SKIP',0)} "
        f"WAIVED:{counts.get('WAIVED',0)}"
    )
    return exit_code


def _cmd_diff(args: argparse.Namespace) -> int:
    """Diff two canonical JSON reports (REQ-7.1) — stub."""
    print("'diff' is not yet implemented.", file=sys.stderr)
    return 4


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    p = build_parser()
    args = p.parse_args(argv)

    if args.cmd == "version":
        print("attest 0.1.0")
        return 0

    if args.cmd == "validate":
        return _cmd_validate(args)

    if args.cmd == "run":
        return _cmd_run(args)

    if args.cmd == "diff":
        return _cmd_diff(args)

    print(f"Unknown command: {args.cmd}", file=sys.stderr)
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
