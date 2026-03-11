---
description: "Use when editing Python source, tests, CLI code, schemas, evaluation logic, or report generation. Covers architecture boundaries, Ruff, pytest, Pylance, determinism, and Attest coding standards."
applyTo: "src/**/*.py, tests/**/*.py"
---

# Python Implementation Guidance

- Target Python 3.14 and follow the existing Poetry-based workflow in `pyproject.toml`.
- Keep CLI code thin. Put domain behaviour into modules that match the architecture plan in `docs/design/architecture.md`.
- Prefer explicit types, clear return contracts, and narrow data models.
- Keep data structures deterministic. Sort controls, hosts, tags, and report collections where order matters.
- Use actionable error messages that help operators and contributors fix invalid profiles, control content, or runtime failures.
- Add or update pytest coverage for each behaviour change. Smoke-only changes are not enough for new domain logic.
- Run `poetry run ruff check .` and resolve newly introduced findings.
- Keep Pylance clean in changed code: no unused imports, dead branches, accidental `Any`, or unclear optional handling.
- When adding resource, policy, engine, or reporting code, keep contracts aligned with the requirements document and architecture docs.