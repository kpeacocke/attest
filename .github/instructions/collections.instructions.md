---
description: "Use when editing Ansible collections, roles, modules, or collection-facing content under collections/. Covers contract boundaries between Ansible packaging and the Python core."
applyTo: "collections/**"
---

# Collections Guidance

- Treat the collections directory as the Ansible-facing surface, not the place for core evaluation logic.
- Keep collection code and metadata aligned with the Python architecture: collections gather facts, wrap execution, or expose reporting surfaces.
- Reuse canonical result semantics and naming from the requirements and architecture docs.
- Avoid duplicating business rules in both collection content and Python core unless a documented interface requires it.
- Document future-facing stubs clearly so contributors know whether a collection artefact is operational or planned.