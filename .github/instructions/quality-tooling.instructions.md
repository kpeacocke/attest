---
description: "Use when editing CI workflows, pyproject settings, security policy, dev container setup, dependency definitions, or quality gates. Covers pytest, Ruff, Pylance, Snyk, and SonarQube expectations."
applyTo: ".github/workflows/**/*.yml, pyproject.toml, poetry.lock, .devcontainer/**, .vscode/**, SECURITY.md"
---

# Quality and Tooling Guidance

- Keep local and CI quality gates aligned: pytest and Ruff are mandatory, and Snyk plus SonarQube should remain first-class checks.
- Prefer targeted commands in automation, but keep one clear full-project path for contributors: `poetry install`, `poetry run ruff check .`, `poetry run pytest`.
- Preserve Python 3.14 compatibility unless a deliberate version policy change is documented.
- If adding Snyk or SonarQube workflow steps, fail safely when credentials are absent and document required secrets or environment variables.
- Keep static analysis noise low. Tooling changes should reduce false positives, not mask real issues.
- Treat Pylance diagnostics as part of the editing loop even if they are not enforced in CI yet.