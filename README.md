# Attest

Attest is an **Ansible-native compliance-as-code framework** for continuous compliance verification and audit automation.

Define compliance checks in YAML, run audits at scale, and track changes over time. Get deterministic, audit-ready reports.

## Why Attest?

**The problem:** Compliance is still manual, slow, and disconnected from infrastructure code.

- ❌ Checklists drift from reality between audits
- ❌ Compliance checks live in separate tools (ticketing, spreadsheets)
- ❌ Audits are expensive point-in-time snapshots
- ❌ Hard to track who changed what in compliance rules
- ❌ No integration with infrastructure-as-code workflows

**The solution:** Treat compliance like code.

Attest lets you version compliance checks alongside infrastructure, run continuous audits, and produce audit-ready reports—all in Ansible-native YAML.

## What Attest provides

- **Declarative profiles and controls** — Version-controlled compliance rules in YAML
- **Continuous verification** — Automated audits with evidence capture and drift detection
- **Deterministic reporting** — Consistent outputs (JSON, JUnit, Markdown) suitable for compliance pipelines
- **Exception management** — Waivers with expiry and justification built in
- **Ansible-native** — No new DSL; uses Ansible facts, roles, and variables you already have
- **Local installation** — Install from source with Poetry; versioned package releases are prepared by the release workflow

## Quick example

A profile checking Linux hardening controls:

```yaml
name: linux-hardening
title: Linux Hardening Baseline
version: 1.0.0
summary: Core Linux security hardening controls

controls:
  - id: C-1
    title: sudo requires password
    description: Sudo sessions must require password authentication
    impact: 0.8
    tests:
      - name: verify sudo password requirement
        check: "get_sudoers_fact | select('requiring_password') | length > 0"
        expected: true

  - id: C-2
    title: SSH root login disabled
    description: SSH root login must be disabled
    impact: 1.0
    tests:
      - name: check sshd config
        check: "ansible_local.sshd.permit_root_login"
        expected: false
```

Run against your inventory, get evidence, track drift, manage exceptions.

## Use cases

- **Infrastructure teams** embedding compliance in Terraform/Ansible deployments
- **Platform teams** running continuous compliance across managed infrastructure
- **Security teams** automating compliance audits and drift detection
- **DevOps teams** failing deployments on compliance violations

## Status

**Early beta.** The CLI, reports, and prebuilt hosted dashboard are available; continuous hosted ingestion remains planned. [Current roadmap →](docs/roadmap/roadmap.md)

[v0.1.0](https://github.com/kpeacocke/attest/releases/tag/v0.1.0) provides a Python wheel and source archive with pinned runtime constraints, plus non-root CLI and dashboard images in GHCR. The localhost-only Compose reference serves prebuilt dashboard artefacts; it does not ingest reports continuously. See the [operator delivery workflow](docs/operator/workflows.md#package-and-container-delivery-req-101-to-req-104) for build and deployment steps.

## Quick start

```bash
git clone <repo>
cd attest
poetry install
poetry run attest --help
```

For a pinned v0.1.0 install with Python 3.14 and the GitHub CLI:

```bash
gh release download v0.1.0 -R kpeacocke/attest \
  --pattern 'attest-0.1.0-py3-none-any.whl' --pattern 'constraints.txt' --pattern 'SHA256SUMS'
sha256sum --check SHA256SUMS
python -m pip install --constraint constraints.txt ./attest-0.1.0-py3-none-any.whl
attest version
```

Pin the release tag or wheel URL and retain its `SHA256SUMS` alongside the [changelog](CHANGELOG.md) for CI installs. The wheel is published on GitHub Releases, not PyPI.

See the [full documentation](docs/index.md) for examples, architecture, and how to contribute.

## Contributing

Attest is actively being built. We welcome:

- Bug reports and feature requests ([GitHub Issues](https://github.com/TODO/issues))
- Design feedback and discussions ([GitHub Discussions](https://github.com/TODO/discussions))
- Code contributions ([Contributing guide](CONTRIBUTING.md))

See [CONTRIBUTING.md](CONTRIBUTING.md) for workflow and guidelines.

## Licence

MIT — see [LICENSE](LICENSE).
