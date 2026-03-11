# Roadmap

This roadmap outlines milestones and sequencing for Attest.

Milestone planning and tracking is managed via **GitHub Projects** and **GitHub Issues**.

## v0.1-beta (current focus)

Initial MVP with core compliance capabilities:

### Phase 1: Core policy model

- Implement `profile.yml`, control schema, and profile overlays ([REQ-1](requirements/requirements.md#req-1-policy-and-content))
- Basic validation and error handling
- Example profiles and controls

### Phase 2: Execution and evaluation

- Expanded Linux resource set: file, mount, package, service, user, group, process, kernel_module, auditd, crontab, sysctl, command, port ([REQ-2](requirements/requirements.md#req-2-resources-facts-collection))
- Structured config file parsers: json_file, yaml_file, ini_file ([REQ-2](requirements/requirements.md#req-24-structured-config-file-parsers))
- Control evaluation engine with loop/iteration support ([REQ-3](requirements/requirements.md#req-3-evaluation-engine))
- Deterministic result semantics

### Phase 3: Reporting

- JSON, JUnit, and Markdown output formats ([REQ-4](requirements/requirements.md#req-4-reporting-and-evidence))
- Framework tag summaries (NIST, CIS, STIG) in reports
- Evidence capture, redaction, and linking
- Report determinism validation

### Phase 4: State management

- Baseline snapshots ([REQ-6](requirements/requirements.md#req-6-baselines-and-drift))
- Basic drift detection
- Waiver management with expiry

### Phase 5: Operator UI experience and documentation (beta phase 2)

- Terminal-first UX refinements: clearer validation errors, actionable remediation hints, and predictable output grouping by host and control ([REQ-8](requirements/requirements.md#req-8-operator-experience-ui-and-ux))
- Report readability improvements: triage-first Markdown layout and stable canonical JSON navigation fields ([REQ-8](requirements/requirements.md#req-8-operator-experience-ui-and-ux))
- Documentation uplift: task-based operator guides and CI examples for day-2 use ([REQ-8](requirements/requirements.md#req-8-operator-experience-ui-and-ux))
- Success metrics tracked against competitor baseline (triage speed, audit pack turnaround, waiver miss rate) ([REQ-8](requirements/requirements.md#req-85-operator-success-metrics-competitor-benchmark))

### Phase 6: Compliance operations dashboard (beta phase 2)

- Launch dashboard product model: offline single-file viewer plus hosted continuous dashboard mode ([REQ-9](requirements/requirements.md#req-9-compliance-dashboarding))
- Implement posture and trend analytics with baseline regression detection ([REQ-9](requirements/requirements.md#req-9-compliance-dashboarding))
- Deliver waiver governance board with owner and expiry workflows ([REQ-9](requirements/requirements.md#req-9-compliance-dashboarding))
- Deliver framework rollups for NIST, CIS, and STIG with drill-down evidence ([REQ-9](requirements/requirements.md#req-9-compliance-dashboarding))
- Add triage acceleration views (top regressions, changed-since-last-good, direct evidence path) ([REQ-9](requirements/requirements.md#req-9-compliance-dashboarding))
- Add audit pack export and alert integrations for operational response ([REQ-9](requirements/requirements.md#req-9-compliance-dashboarding))
- Enforce dashboard SLOs for load latency and data freshness ([REQ-9](requirements/requirements.md#req-9-compliance-dashboarding))

### Phase 7: Distribution and containerisation (beta phase 2)

- Ship versioned package releases for CLI/runtime use in local and CI workflows ([REQ-10](requirements/requirements.md#req-10-packaging-and-container-delivery))
- Publish official container images for CLI and hosted dashboard components ([REQ-10](requirements/requirements.md#req-10-packaging-and-container-delivery))
- Deliver Compose-first reference deployment (`compose.yaml`) for hosted mode startup ([REQ-10](requirements/requirements.md#req-10-packaging-and-container-delivery))
- Enforce image security and provenance gates (Snyk scan, digest/SBOM metadata) in release workflow ([REQ-10](requirements/requirements.md#req-10-packaging-and-container-delivery))
- Validate runtime parity between package mode and container mode outputs ([REQ-10](requirements/requirements.md#req-10-packaging-and-container-delivery))

For detailed requirements breakdown, see [Requirements](requirements/requirements.md).

## Tooling and quality gates

All development follows these quality gates:

- **Snyk** security scanning (no high/critical vulnerabilities in first-party code)
- **SonarQube** quality analysis (maintain healthy technical debt ratio)
- **GitHub Actions** CI/CD (all tests and lints must pass)

## Future work (post-beta)

- Windows resource support
- Cloud/API resource modules
- Cryptographic signing and verification
- Distributed compliance ingestion
- Advanced drift analytics
- **XCCDF / STIG content import** — ingest DISA STIG XCCDF bundles and map controls to Attest profiles; enables reuse of official STIG content without manual porting
- **Profile distribution** — resolve and install profiles from GitHub repositories or an Attest-native registry; analogous to InSpec Supermarket or Ansible Galaxy
- **HTTP and host resources** — endpoint reachability, TLS verification, HTTP response testing for network compliance auditing

This document will be expanded as the roadmap evolves.
