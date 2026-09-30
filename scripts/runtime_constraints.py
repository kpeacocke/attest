"""Print pinned runtime dependencies from Poetry's lock file (REQ-10.1)."""

from __future__ import annotations

import tomllib
from pathlib import Path


def main() -> None:
    lock_path = Path(__file__).resolve().parents[1] / "poetry.lock"
    with lock_path.open("rb") as lock_file:
        packages = tomllib.load(lock_file)["package"]

    for package in sorted(packages, key=lambda item: item["name"]):
        if "main" in package["groups"] and not package["optional"]:
            print(f"{package['name']}=={package['version']}")


if __name__ == "__main__":
    main()