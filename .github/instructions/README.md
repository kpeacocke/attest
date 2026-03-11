# Attest Copilot Instruction Structure

This directory defines how Copilot should behave across the Attest workspace.

## Layering Model

1. Workspace-wide baseline: [.github/copilot-instructions.md](../copilot-instructions.md)
2. Scoped overlays: `*.instructions.md` files in this directory using `applyTo`
3. Task-specific guidance: agent files in [.github/agents](../agents)

For quick selection guidance, see [.github/agents/README.md](../agents/README.md).

The baseline establishes architecture, quality, security, and documentation guardrails.
Scoped files then add path-specific constraints without overriding the core architectural model.

## Scoped Files

- `collections.instructions.md`: rules for Ansible collection-facing content under `collections/**`
- `docs.instructions.md`: rules for Markdown docs and contributor-facing text
- `python.instructions.md`: rules for Python implementation and tests
- `quality-tooling.instructions.md`: rules for CI and tooling configuration
- `security.instructions.md`: rules for secure coding and scan expectations

## Design Principles

- Keep guidance honest to Attest's bootstrap maturity.
- Preserve the four-layer architecture boundaries.
- Prefer deterministic behaviour and diff-friendly outputs.
- Use requirement IDs from `docs/requirements/requirements.md` for substantial changes.
- Use Australian English in user-facing content.

## Maintenance

- Update scoped instructions when repository conventions change.
- Keep this document aligned with `.github/copilot-instructions.md` and agent definitions.
- Avoid duplicating long policy text across files; link to source guidance instead.