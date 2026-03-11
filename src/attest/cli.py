from __future__ import annotations

import argparse
import sys

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="attest",
        description="Attest: Ansible-native compliance-as-code (bootstrap).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("version", help="Show version information.")
    sub.add_parser("validate", help="Validate a profile (not yet implemented).")
    sub.add_parser("run", help="Run a profile against a target inventory (not yet implemented).")
    sub.add_parser("diff", help="Diff two reports (not yet implemented).")

    return p

def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    p = build_parser()
    args = p.parse_args(argv)

    if args.cmd == "version":
        print("attest 0.1.0")
        return 0

    print(f"'{args.cmd}' is not implemented yet.")
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
