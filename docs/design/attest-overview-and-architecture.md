# Attest overview and architecture

Attest is an Ansible-native compliance-as-code framework. It treats compliance checks as executable code, version-controlled alongside infrastructure, enabling continuous compliance verification and automated audit reporting.

## Design principles

1. **Ansible-native first** — Leverage Ansible directly; no proprietary DSL or runtime
2. **Deterministic and auditable** — Same input always produces same output; full evidence chains
3. **Composable** — Profiles, controls, and tests are modular and reusable
4. **Infrastructure-as-code** — Compliance logic is versioned, reviewed, and deployed like code
5. **Continuous** — Enable ongoing compliance verification, not point-in-time snapshots

## The problem

High-level compliance challenges Attest addresses:

1. **Disconnected workflow** — Compliance tools don't integrate with infrastructure-as-code practices
2. **Manual and intermittent** — Audits are labour-intensive point-in-time events
3. **Poor traceability** — Hard to version, review, and track changes to compliance rules
4. **Limited evidence** — Reports lack the audit trails and evidence chains needed for compliance workflows

## Ansible integration

Attest is built **on** Ansible, not **around** it:

- **Profiles and controls are Ansible-compatible YAML** — No new syntax to learn
- **Tests use Ansible facts** — Access system state via `ansible_local`, registered variables, or custom fact modules
- **Conditions evaluated against Ansible inventory** — Use host/group variables, dynamic groups, and standard Ansible filtering
- **Runs via Ansible playbooks or native Ansible roles** — Integrate with existing automation
- **Evidence captures Ansible fact values and test results** — Full audit trail

## Target audience

- **Infrastructure and platform teams** automating compliance as part of infrastructure-as-code
- **DevOps engineers** embedding compliance gates in CI/CD pipelines
- **Security and compliance practitioners** who need auditable, evidence-rich workflows
- **Ansible practitioners** wanting to extend existing automation with compliance verification

## Core concept

Attest allows compliance practitioners and security teams to:

1. Define compliance profiles and controls declaratively (YAML)
2. Run audits automatically against target inventories
3. Produce deterministic, auditable reports with evidence
4. Track compliance state over time (baselines and drift)
5. Manage exceptions (waivers) with expiry and justification

## Architecture layers

### Policy layer

- **Profiles**: Container for related controls with metadata (`profile.yml`)
- **Controls**: Individual compliance checks with impact, applicability, and tests
  - **Tests**: Executable assertions that check a condition against infrastructure. A test inspects Ansible facts (e.g., configuration files, system state) and compares them against expected values. Multiple tests per control allow comprehensive validation.
- See [REQ-1: Policy and content](../requirements/requirements.md#req-1-policy-and-content)

**Example:**

```yaml
name: linux-hardening
title: Linux Hardening
summary: Core Linux security controls
controls:
  - id: LH-001
    title: SSH root login disabled
    impact: 1.0
    tests:
      - condition: ansible_local.sshd_config.permit_root_login == 'no'
        expected: true
        evidence: "SSH sshd_config permit_root_login value"
```

Each control can have multiple tests; all must pass for the control to pass.

### Execution layer

- **Resources**: Ansible-based fact-gathering and condition evaluation
  - Runs Ansible fact modules to collect system state
  - Stores facts in `ansible_local` for test evaluation
  - Supports custom fact modules for domain-specific data
- **Evaluation engine**: Executes controls against target systems
  - Iterates through profiles and controls
  - Evaluates each test condition against collected facts
  - Produces result immediately (PASS/FAIL/SKIP/ERROR)
  - Records all facts and results for evidence/audit trail
- See [REQ-2: Resources (facts collection)](../requirements/requirements.md#req-2-resources-facts-collection)

### Reporting layer

- **Result semantics**: PASS/FAIL/SKIP/ERROR/WAIVED with deterministic output
  - **PASS**: All tests passed
  - **FAIL**: One or more tests failed
  - **SKIP**: Control not applicable (pre-flight checks failed)
  - **ERROR**: Unrecoverable error during test execution
  - **WAIVED**: Control failing but exception (waiver) granted
- **Output formats**: Canonical JSON, JUnit XML, Markdown
  - JSON: Machine-readable, includes full evidence
  - JUnit: CI/CD pipeline integration (fail builds)
  - Markdown: Human-readable reports
- **Evidence capture**: Assertion results and supporting data
  - Every test result includes the condition, expected value, actual value, and collected fact
  - Enables audit trail and root cause analysis
- See [REQ-4: Reporting and evidence](../requirements/requirements.md#req-4-reporting-and-evidence)

### State management

- **Baselines**: Known-good snapshots for comparison
  - First run establishes a baseline of all control results
  - Can be re-established after approved changes
  - Enables "drift since last baseline" reporting
- **Drift detection**: Identify changes since last baseline
  - Compare current run results to baseline
  - Report on controls that changed (PASS→FAIL, new failures, waivers expiring, etc.)
  - Useful for continuous compliance monitoring
- **Waivers**: Managed exceptions with expiry and justification
  - Acknowledge known issues with business justification
  - Automatic expiry prevents indefinite exceptions
  - Tracked separately from actual failures
- See [REQ-6: Baselines and drift](../requirements/requirements.md#req-6-baselines-and-drift)

## Beta phase 2: operator UI experience

Attest remains terminal-first for core execution, with a focused UX uplift in beta phase 2:

- Better CLI ergonomics and error messages for day-to-day use
- Triage-first Markdown report layout for operators and reviewers
- Optional static HTML viewer generated from canonical JSON for offline audit review

Beta phase 2 also introduces a compliance operations dashboard track:

- Hosted posture and trend analytics across runs
- Waiver governance board with owner and expiry visibility
- Framework rollups (NIST, CIS, STIG) with evidence drill-down
- Audit pack export and operational alerting

This phase is specified in [REQ-8: Operator experience](../requirements/requirements.md#req-8-operator-experience-ui-and-ux) and [REQ-9: Compliance dashboarding](../requirements/requirements.md#req-9-compliance-dashboarding), and sequenced in the [Roadmap](../roadmap/roadmap.md).

## Scope for v0.1-beta

**In scope:**

- Declarative profiles and controls
- Core Linux resources
- Standardised outcomes with evidence
- Waivers with expiry and justification
- Canonical JSON + JUnit + Markdown outputs
- Basic baseline + diff (drift)

**Out of scope (beta):**

- Windows resources
- Cloud/API resources
- Cryptographic signing/verification

For complete scope details, see [Requirements](../requirements/requirements.md).

## Project tooling

Attest uses GitHub-native tools exclusively:

- **GitHub Issues** for bug tracking and feature requests
- **GitHub Projects** for milestone planning and roadmap tracking
- **GitHub Discussions** for RFC-style design discussions
- **GitHub Actions** for CI/CD automation
- **Snyk** for automated security scanning
- **SonarQube** for code quality and technical debt analysis

See [Contributing guide](../../CONTRIBUTING.md) for workflow details.

## Related documents

- [Technical architecture](architecture.md) — Detailed layer design, code structure, and data flows
- [Requirements](../requirements/requirements.md) — Detailed v0.1-beta requirements
- [Roadmap](../roadmap/roadmap.md) — Development milestones
- [Contributing](../../CONTRIBUTING.md) — How to contribute
