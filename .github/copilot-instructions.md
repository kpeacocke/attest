# Attest Copilot Instructions

## Project Focus

Attest is an Ansible-native compliance-as-code framework in early bootstrap.
Keep implementation and documentation honest about current maturity.
Do not present planned capabilities as already shipped.

## Architecture First

Attest follows four layers with stable contracts:

1. Policy layer: parse, validate, resolve, and plan.
2. Resource layer: gather structured facts with per-host, per-run caching.
3. Engine or runner layer: evaluate controls deterministically and apply waivers.
4. Reporting layer: emit canonical JSON first, then derived formats.

Design and refactors should preserve those boundaries.
Avoid cross-layer shortcuts such as resource code formatting reports or CLI code embedding evaluation logic.
When adding implementation beyond the current bootstrap, place modules in the planned package layout described in `docs/design/architecture.md`.

## Engineering Rules

- Use Australian English in user-facing text, docs, comments, and error messages.
- Keep outputs deterministic: sort stable collections, avoid hidden global state, and make report fields diff-friendly.
- Reference requirement IDs from `docs/requirements/requirements.md` in substantial design, code, and documentation changes.
- Prefer small, typed, testable units over large orchestration functions.
- Preserve the bootstrap reality of the CLI: new commands should delegate into modules rather than accumulating more logic in `src/attest/cli.py`.

## Quality Gates

- Use Poetry commands for local verification.
- For Python changes, run the smallest relevant test set first, then `poetry run pytest` when feasible.
- Run `poetry run ruff check .` after Python edits and fix newly introduced issues.
- Treat Pylance diagnostics as first-class feedback for type safety, imports, and unreachable code.
- Treat Snyk and SonarQube findings as required review signals for changed code and dependency updates.
- If you introduce or change dependencies, prefer the safest minimal option and document why.

## Security and Evidence

- Assume Attest will process sensitive compliance evidence.
- Redact secrets, tokens, and high-risk command output from reports, fixtures, logs, and examples.
- Avoid shell injection risks, unsafe path handling, and broad exception swallowing.
- Do not suppress security findings without a concrete rationale in code or the pull request.

## Documentation Discipline

- Update docs when behaviour, architecture, or workflow meaningfully changes.
- Keep `README.md`, `docs/design/architecture.md`, and `docs/requirements/requirements.md` aligned with implementation reality.
- Prefer linking to the architecture and requirements docs instead of duplicating long explanations.

## Repo Areas

- `src/attest/`: Python product code.
- `tests/`: pytest coverage for behaviour and regressions.
- `collections/`: Ansible-facing collections and roles.
- `docs/`: architecture, requirements, roadmap, and contributor-facing documentation.
- `.github/`: CI, templates, Copilot instructions, and custom agents.

## Working Style

- Make the smallest coherent change that solves the problem at the architectural layer where it belongs.
- If a change conflicts with the current architecture docs, update the docs in the same change.
- If a task is still pre-implementation design, keep the outcome as docs, schema, or tests rather than speculative product code.