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
- **Flexible delivery** — Ship as installable packages and official containers, with Compose-first hosted startup

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

**Early bootstrap.** Architecture and docs in place. Implementation intentionally minimal. [Current roadmap →](docs/roadmap/roadmap.md)

Delivery model is defined as **packages + official containers**. Compose is the first hosted deployment target.

## Quick start

```bash
git clone <repo>
cd attest
poetry install
poetry run attest --help
```

See the [full documentation](docs/index.md) for examples, architecture, and how to contribute.

## Contributing

Attest is actively being built. We welcome:

- Bug reports and feature requests ([GitHub Issues](https://github.com/TODO/issues))
- Design feedback and discussions ([GitHub Discussions](https://github.com/TODO/discussions))
- Code contributions ([Contributing guide](CONTRIBUTING.md))

See [CONTRIBUTING.md](CONTRIBUTING.md) for workflow and guidelines.

## Licence

MIT — see [LICENSE](LICENSE).
