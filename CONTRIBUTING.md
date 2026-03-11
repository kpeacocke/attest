# Contributing to Attest

Thanks for considering contributing. Attest is in early development, so there's lots to build and we welcome all forms of help.

## How to contribute

**No contribution is too small.** We welcome:

- **Bug reports** — Found something broken? [Open an issue](https://github.com/TODO/issues)
- **Feature ideas** — Have a suggestion? [Start a discussion](https://github.com/TODO/discussions)
- **Documentation improvements** — Spotted unclear sections? PRs welcome
- **Test coverage** — Improve reliability with new tests
- **Code** — Implement features, fix bugs, refactor

## Getting started

### Before you start

1. Read the [Overview and architecture](docs/design/attest-overview-and-architecture.md) to understand the design
2. Check [Requirements](docs/requirements/requirements.md) to see what's in v0.1-beta scope
3. Browse [GitHub Issues](https://github.com/TODO/issues) to find open work or propose something new

### Setting up for development

```bash
git clone <repo>
cd attest
poetry install

# Verify setup
poetry run attest --help
poetry run pytest
poetry run ruff check .
```

Prefer container-based development? Open the repository in the dev container defined in `.devcontainer/devcontainer.json`.
It includes a minimal extension set with Python, Ruff, Snyk, and SonarQube support.
The dev container builds from a project Dockerfile and uses Python 3.14 to match project requirements.
Dependencies are installed automatically on first create and re-synchronised when `poetry.lock` changes.

### Before submitting a pull request

- Run tests: `poetry run pytest`
- Run linting: `poetry run ruff check .`
- Update docs if behaviour changes
- Link to related issue(s) in your PR description
- Ensure Australian English spelling (organisation, behaviour, prioritise, etc.)
- Address any Snyk or SonarQube issues flagged by CI

## Workflow and traceability

We use GitHub Issues as our source of truth:

1. Create or discuss in **GitHub Issues** for bugs and features
2. Reference the related requirement ID from [Requirements](docs/requirements/requirements.md) (e.g., REQ-1.1)
3. Create a branch and open a PR, linking the issue
4. PR title should reference the issue: `Fix: sudo control test (Closes #42)`
5. Merge closes the issue automatically

This keeps everything in one place and makes it easy to audit who changed what and why.

## Quality gates

All PRs must pass:

- **Tests** — `poetry run pytest`
- **Linting** — `poetry run ruff check .`
- **Security** — Snyk scans for vulnerabilities
- **Code quality** — SonarQube analysis
- **Documentation** — Updated if behaviour changes

CI runs these automatically. If something fails, we'll help you fix it.
The Python job also publishes a coverage report for SonarQube ingestion.

Repository CI expects these credentials or variables for full assurance coverage:

- `SNYK_TOKEN` secret
- `SNYK_ORG` variable (optional)
- `SONAR_TOKEN` secret
- `SONAR_PROJECT_KEY` variable
- `SONAR_HOST_URL` variable for SonarQube Server, or `SONAR_ORGANIZATION` for SonarCloud

When those values are not configured, CI still enforces Ruff and pytest and reports the assurance scans as skipped.
The CI workflow also runs on a weekly schedule to catch drift in dependencies and scanner findings.

## Where to find help

- **Questions about Attest?** Use [GitHub Discussions](https://github.com/TODO/discussions)
- **Need clarification on requirements?** Check [Requirements](docs/requirements/requirements.md) or ask in Discussions
- **Stuck on setup?** Open an issue with the `help wanted` label
- **Design questions?** Start a discussion or comment on related issues

## Development setup details

Prereqs:

- Python 3.14
- Poetry
- Docker Desktop (optional, for dev container workflow)
- Node.js 20.12.0+ (optional, required for SonarQube analysis and Snyk scanning)

Common tasks:

```bash
# Run all checks locally (before pushing)
poetry run pytest --cov=attest --cov-report=xml:coverage.xml && poetry run ruff check .

# Run specific test
poetry run pytest tests/test_smoke.py::test_version_exits_zero

# Generate coverage XML for SonarQube-compatible local review
poetry run pytest --cov=attest --cov-report=xml:coverage.xml

# Format code (if supported)
poetry run ruff check . --fix
```

### Copilot and agent workflow

Shared AI guidance for this repository lives under `.github/`:

- `.github/copilot-instructions.md` for project-wide rules
- `.github/instructions/` for file-scoped guidance
- `.github/agents/` for task-specific custom agents

These files are expected to reinforce, not replace, the architecture and requirements documents.
If you change project structure, quality gates, or contributor workflow, update the relevant customisation files in the same pull request.

### VS Code tooling troubleshooting

If you develop locally (not in dev container), install these tools on your host:

**Snyk CLI** — Required for Snyk vulnerability scanning.

On Windows:
```powershell
# Option 1: Using winget (recommended)
winget install Snyk.Snyk

# Option 2: Using Chocolatey
choco install snyk

# Verify
snyk --version
```

On macOS:
```bash
brew install snyk
snyk --version
```

On Linux:
```bash
npm install -g snyk
snyk --version
```

**Fixing "snyk-win.exe not found" error in VS Code:**

If the Snyk extension shows `ENOENT` error trying to launch `snyk-win.exe`:

1. Uninstall the Snyk extension from your local VS Code
2. Delete this folder (if it exists):
   ```
   C:\Users\<username>\AppData\Local\snyk\vscode-cli
   ```
3. Reinstall the Snyk extension
4. Reload VS Code
5. Optional: In VS Code User Settings, add:
   ```json
   {
     "snyk.path": "snyk"
   }
   ```
   This tells it to use a globally installed Snyk CLI instead of the bundled one.

**Developing in dev container:**

All tooling (Node.js, Snyk CLI, Python, Poetry) is pre-installed.
No additional setup required beyond opening in the dev container.
