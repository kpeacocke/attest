---
description: "Use when editing README, design docs, requirements, roadmap, contributor docs, or other Markdown content. Covers Australian English, implementation honesty, traceability, and architecture alignment."
applyTo: "README.md, CONTRIBUTING.md, SECURITY.md, SUPPORT.md, CODE_OF_CONDUCT.md, GOVERNANCE.md, docs/**/*.md"
---

# Documentation Guidance

- Use Australian English consistently: organisation, behaviour, prioritise, artefact, licence when used as a noun.
- Keep bootstrap-stage wording accurate. Distinguish clearly between implemented behaviour, planned architecture, and roadmap items.
- When code changes affect behaviour or structure, update the relevant docs in the same change.
- Prefer requirement IDs such as `REQ-2.1` and links to architecture sections when describing design decisions.
- Keep examples deterministic and realistic for an Ansible-native compliance tool.
- Avoid placeholder claims such as "enterprise-ready" or "fully implemented" unless the repo genuinely supports them.