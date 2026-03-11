---
description: "Use when changing dependency definitions, command execution, file handling, evidence capture, report content, CI security scanning, or anything with security impact. Covers Snyk, SonarQube, redaction, and safe coding expectations."
---

# Security Guidance

- Run or request Snyk scanning for new or changed first-party code and dependency updates where the tooling is available.
- Review SonarQube findings for changed files and fix newly introduced security or maintainability issues.
- Treat command execution, file parsing, and report generation as hostile-input surfaces.
- Redact or truncate secrets, credentials, tokens, private keys, and sensitive host evidence.
- Prefer safe standard-library helpers over shelling out.
- Validate paths and inputs before reading files, invoking commands, or writing artefacts.
- Do not add broad ignore rules or suppress findings unless the rationale is documented.