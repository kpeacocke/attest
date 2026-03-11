# Attest requirements (v0.1-beta)

This document defines the minimum requirements for an initial public beta of **Attest** (an Ansible-native compliance-as-code framework).
Requirements are written for rapid decomposition into GitHub issues and agent work.

## Conventions

- Requirement IDs are stable and MUST be referenced by issues and pull requests (e.g. `REQ-4.1`).
- “SHALL” = required for beta; “SHOULD” = desirable for beta; “MAY” = future.
- Output determinism is a first-class requirement because drift reporting depends on it.

## Scope for v0.1-beta

### In scope

- Declarative profiles and controls
- Profile overlays and inheritance for upstream content customisation
- Expanded Linux resource set (including user, group, process, kernel_module, mount, auditd)
- Structured config file parsers (json, yaml, ini)
- Loop/iteration over resource collections
- Standardised outcomes (PASS/FAIL/SKIP/ERROR/WAIVED) with evidence
- Structured framework tag mapping (NIST 800-53, CIS Level, STIG CAT)
- Waivers with expiry and justification
- Canonical JSON report + JUnit + Markdown
- Basic baseline + diff (drift)
- A small deterministic summary artefact for pipeline/workflow gating

### Out of scope (beta)

- Windows resources
- Cloud/API resources
- OpenShift compliance ingestion
- Cryptographic signing/verification (design hooks only)

---

## REQ-1 Policy and content

### REQ-1.1 Profile schema

The system SHALL support a `profile.yml` schema with:

- `name`, `title`, `version`, `summary`, `licence`
- `supports` (platform/os applicability)
- `inputs` (typed parameters; defaults and required flags)
- `depends` (optional dependencies with version constraints)

**Acceptance:**

- Invalid profiles fail validation with actionable errors.
- Schema is versioned and published in-repo.

### REQ-1.2 Control schema

The system SHALL support controls with:

- `id` (stable), `title`, `desc`
- `impact` (0.0–1.0 or discrete levels)
- `tags` — structured, namespaced framework mappings (see below)
- `only_if` / `skip_if` applicability predicates
- `tests[]` (one or more assertions)
- `evidence` configuration
- `source` provenance block (origin, upstream id/version if applicable)

The `tags` field SHALL support structured namespace keys for compliance framework mapping:

- `nist` — NIST 800-53 control IDs (e.g. `['AC-3', 'AC-6']`)
- `cis_level` — CIS Benchmark level (e.g. `1` or `2`)
- `stig_severity` — DISA STIG CAT level (e.g. `CAT I`, `CAT II`)
- `custom` — arbitrary free-form strings for local taxonomies

Reports SHALL include framework tag summaries (e.g. "12 NIST AC controls passing").

**Acceptance:**

- Every control resolves to exactly one status: PASS/FAIL/SKIP/ERROR/WAIVED.
- Control IDs remain stable across runs and environments.
- Report summaries are grouped and counted by framework tag namespace.

### REQ-1.3 Inputs and overrides

The system SHALL support typed inputs with precedence: CLI flags override extra/survey vars, which override inventory vars, which override profile defaults.

**Acceptance:**

- Missing required inputs fail before execution.
- Type mismatches provide clear, specific error messages.

### REQ-1.4 Dependency lockfile

The system SHOULD provide a deterministic lockfile format that pins resolved dependencies and sources.

**Acceptance:**

- Resolution is deterministic (same inputs → same lockfile).
- Lockfile is human-reviewable and diff-friendly.

### REQ-1.5 Profile overlays and inheritance

The system SHALL support overlaying an upstream profile to customise controls without forking.

An overlay SHALL be able to:

- Skip specific controls from an upstream profile (`skip_control: <id>`)
- Override a control's `impact`, `tags`, or `only_if` predicate
- Add new controls to an upstream profile
- Chain multiple upstream profiles

Overlay files are separate from the upstream profile and applied at resolution time.

When multiple overlays modify the same control, the **last overlay in the chain wins**. Overlay order is determined by the order declared in the profile's `depends` list. This rule is explicit and documented so authors can reason about it without surprises.

**Acceptance:**

- An overlay that skips control `REQ-X` causes that control to be SKIP in the merged execution plan.
- An overlay that changes `impact` is visible in the report with provenance (overlay source noted).
- Upstream profile content is not modified; overlays are applied non-destructively.
- Circular overlay dependencies are detected and fail with a clear error.
- When two overlays both modify the same field on the same control, the last-in-chain overlay wins and the report records both overlay sources for that control.

---

## REQ-2 Resources (facts collection)

### REQ-2.1 Resource contract

The system SHALL define a resource contract returning:

- `data` (structured facts)
- `errors[]` (structured errors, not raw tracebacks by default)
- `timings` (durations for query/parsing)

**Acceptance:**

- Resource errors do not crash the entire run; impacted tests become ERROR.

### REQ-2.2 Core Linux resources

The system SHALL implement the following resources for beta:

**File system:**

- `file` (exists, mode, owner, group, content regex)
- `file` hash checking: compare file content against a known-good hash. SHALL support `sha256`; `md5` and `sha512` are SHOULD. Hash values may be provided inline or sourced from a manifest file. Hash checking is beta scope.
- `mount` (mount point, device, options: noexec, nosuid, nodev, etc.)

**Packages and services:**

- `package` (installed, version)
- `service` (enabled, running)

**Users and groups:**

- `user` (exists, uid, gid, shell, home directory, group membership)
- `group` (exists, gid, members)

**Kernel and OS:**

- `sysctl` (key/value)
- `kernel_module` (loaded, disabled)
- `os` facts helper

**Processes and network:**

- `process` (name, pid, user, capabilities)
- `port` (listening checks)

**Audit and scheduling:**

- `auditd_rules` (rule present, action, key)
- `crontab` (user crontabs, system cron directories)

**General purpose:**

- `command` (rc/stdout/stderr with redaction + truncation)

The `ssh_config` resource SHALL be implemented as a purpose-built parser to enable structured assertion over SSH daemon configuration keys (e.g. `PermitRootLogin`, `PasswordAuthentication`, `Protocol`). Using `file` regex for SSH configuration is explicitly not acceptable — SSH hardening controls appear in every CIS benchmark and STIG and require reliable, key-level assertions.

**Known resource gaps (post-beta):**

The following resources are not in beta scope but are documented here so consumers can plan and the `command` workaround is a conscious, temporary choice:

- `pam` — PAM module stack assertions (account lockout, password complexity via `pam_faillock`/`pam_pwquality`). Beta workaround: `file` or `ini_file`.
- `login_defs` — `/etc/login.defs` password ageing and UID/GID range assertions. Beta workaround: `ini_file`.
- `iptables` / `firewalld` — firewall rule and zone assertions. Beta workaround: `command` (fragile; acknowledged limitation).

These appear in CIS and STIG benchmarks. Their absence does not prevent beta use but requires `command`-based workarounds for affected controls.

### REQ-2.3 Resource caching

The system SHALL cache resource results per-host per-run.

**Acceptance:**

- Cache hit/miss statistics are recorded in the report.

### REQ-2.4 Structured config file parsers

The system SHALL provide purpose-built config file parser resources for common formats:

- `json_file` — parse and query JSON files by path expression
- `yaml_file` — parse and query YAML files by path expression
- `ini_file` — parse INI-style config files by section and key

These resources enable structured assertions such as:

```yaml
- resource: json_file
  path: /etc/app/config.json
  query: security.tls_version
  operator: eq
  expected: "1.3"
```

Using `file` content regex as a substitute for structured config parsing is discouraged; these resources eliminate the need.

**Acceptance:**

- Each parser handles malformed files gracefully (resource ERROR, not crash).
- Path expressions support at least one level of nesting.

---

## REQ-3 Evaluation engine

### REQ-3.1 Control evaluation semantics

The system SHALL support these control statuses:

- PASS, FAIL, SKIP (with reason), ERROR, WAIVED

**Aggregation:**

- A control FAILs if any test FAILs.
- A control ERRORs if a test cannot be evaluated due to resource/execution failure.
- A control SKIPs only when predicates exclude it (or it is explicitly skipped).

### REQ-3.2 Assertion/matcher operators

The system SHALL support at minimum:

- `eq`, `ne`
- `contains`, `regex`
- `exists`, `not_exists`
- `cmp` — version-aware and numeric comparison. SHALL support operators `<`, `<=`, `>`, `>=`, `==`, `!=`. Version strings are compared using Python's `packaging.version` (PEP 440-compatible) for package versions, and integer/float comparison for numeric values. When the value cannot be parsed as a version or number, `cmp` SHALL produce an ERROR with a clear message. RPM epoch notation (`2:1.0-1`) is SHALL for beta when evaluating package versions on RPM-based distributions.
- `in_list` — assert a value is one of a specified set (e.g. shell must be one of `/bin/bash`, `/bin/sh`)
- `not_in_list` — assert a value is not in a specified set (e.g. shell must not be `/bin/sh` or `/bin/bash`)

**Acceptance:**

- Matcher failures produce structured evidence: observed, expected, operator, message.
- `in_list` and `not_in_list` evidence includes the full list so failures are self-explanatory.

### REQ-3.3 Execution modes

The system SHALL support CLI execution.
The system SHOULD write outputs to a directory suitable for CI and AAP artefact capture.

**Acceptance:**

- Identical profile inputs yield equivalent canonical JSON in both “local” and “job” contexts.

### REQ-3.4 Loop and iteration over resource collections

The system SHALL support iterating over the results of a resource query and applying a test assertion to each item.

This enables controls such as:

- "For every user in group `sudo`, assert their shell is not `/bin/sh`"
- "For every world-writable file in `/etc`, fail"
- "For every loaded kernel module not in the allowlist, fail"

Syntax SHALL be declarative and YAML-native (no scripting language required).

Iterations SHALL contribute individual test evidence entries per item, so failures identify the specific offending item.

**Acceptance:**

- A loop over an empty collection produces SKIP (not PASS or ERROR).
  > **Design note:** This is a deliberate divergence from InSpec, which produces PASS on empty collections. Attest treats an empty collection as "nothing was checked" rather than "everything passed", which is safer for compliance auditing. Controls that legitimately have nothing to check should use `only_if` / `skip_if` predicates instead.
- Each iteration's result appears as a named evidence entry in the report.
- Loop targets are limited to resource query outputs (not arbitrary expressions) to maintain determinism.

---

## REQ-4 Reporting and evidence

### REQ-4.1 Canonical JSON report

The system SHALL emit a canonical JSON report including:

- `schema_version`
- run metadata (run id, timestamps, tool version, profile versions)
- per-host summaries (counts by status)
- per-control results (status, impact, tags)
- `tag_summaries` (framework summary counts grouped by namespace such as `nist`, `cis_level`, `stig_severity`)
- per-test evidence (redacted as required)
- timings and error summaries
- provenance fields (content origin, verification placeholders)

**Acceptance:**

- Report schema is versioned and validated in tests.
- Output ordering is deterministic for drift comparisons.
- Controls modified by a profile overlay SHALL be flagged in the report with their overlay source. If an overlay changes `impact`, the original value and the overridden value SHALL both appear. This enables auditors to identify where upstream benchmark content has been customised.

### REQ-4.2 Reporters (beta)

The system SHALL generate from canonical JSON:

- JUnit XML
- Markdown summary

**Acceptance:**

- JUnit is compatible with common CI tooling.
- Markdown is single-file and readable as an artefact.
- All configured reporters SHALL be generated in a single `attest run` invocation. Running twice to get different formats is not acceptable.

### REQ-4.3 Evidence redaction

The system SHALL redact sensitive evidence by default via:

- basic secret patterns (configurable)
- truncation limits
- optional "summary-only" mode per test/resource

**Acceptance:**

- Secrets do not appear in reports unless explicitly allowed.

### REQ-4.4 Summary artefact

The system SHALL produce a small deterministic summary file (e.g. `attest-summary.json`) containing:

- run id, timestamp
- profile ids/versions
- fail/error/waived counts
- risk score (simple beta formula is acceptable)

**Acceptance:**

- Summary fields are stable and documented.

---

## REQ-5 Waivers (exceptions)

### REQ-5.1 Waiver schema

The system SHALL support waivers with:

- `control_id` (or list)
- scope (host/group/env predicate)
- justification (required)
- owner
- expiry date
- reference link (ticket/URL)

### REQ-5.2 Waiver behaviour

The system SHALL:

- mark waived controls as WAIVED
- include waiver metadata in the report
- surface expired waivers explicitly (beta policy: expired waiver → FAIL with “waiver expired” flag)

---

## REQ-6 Baselines and drift

### REQ-6.1 Baseline store (beta)

The system SHALL support a local baseline store (directory layout is acceptable).

**Acceptance:**

- Baselines are addressable by name and/or run id.

### REQ-6.2 Diff engine

The system SHALL diff two canonical reports and emit:

- JSON diff
- Markdown diff summary

including:

- new failures, new passes
- new skips/errors
- waiver changes

**Acceptance:**

- Diff output is deterministic and test-covered.

---

## REQ-7 CLI and quality

### REQ-7.1 CLI commands

The system SHALL provide:

- `attest validate <profile_path>`
- `attest run <profile_path> -i <inventory> --out <dir>`
- `attest diff <report_a> <report_b> --out <dir>`

### REQ-7.2 Exit codes

The CLI SHALL use predictable exit codes:

- 0 = all PASS (WAIVED allowed)
- 2 = FAIL present
- 3 = ERROR present
- 4 = validation/config error

### REQ-7.3 Testing minimums

The system SHALL include unit tests for:

- schema validation
- matchers
- report schema contract
- diff logic
- CLI exit codes for common scenarios
- single-run reporter generation (all configured reporters produced by one `attest run` invocation)

### REQ-7.4 Determinism

The system SHALL ensure stable ordering for:

- hosts
- controls
- tests
- output keys where relevant

**Acceptance:**

- Running the same inputs twice yields byte-for-byte identical canonical JSON (excluding timestamps/run id), or a documented normalisation strategy.

---

## REQ-8 Operator experience (UI and UX)

### REQ-8.1 Terminal-first interaction model

The system SHALL provide a terminal-first user experience suitable for daily engineering workflows. Output SHALL be concise by default and expandable for diagnostics.

**Acceptance:**

- `attest run` outputs a clear run summary grouped by status (PASS/FAIL/SKIP/ERROR/WAIVED).
- Failures include actionable context: control id, host, assertion, observed value, expected value.
- Validation and runtime errors include remediation hints where possible.

### REQ-8.2 Human-readable report UX

The system SHALL generate Markdown output optimised for triage and audit review.

**Acceptance:**

- Markdown reports start with an executive summary (counts, risk score, top failing controls).
- Failures are grouped by control and host with direct evidence snippets.
- Waived and expired-waiver controls are visually distinct and easy to scan.

### REQ-8.3 Optional static report viewer

The system SHOULD provide an optional single-file HTML report viewer generated from canonical JSON.

The viewer is not a server product; it is an exported artefact for offline review and sharing.

**Acceptance:**

- Viewer can be generated from one command invocation alongside other reporters.
- Viewer supports filtering by status, control id, host, and framework tag namespace.
- Viewer preserves deterministic ordering from canonical JSON.

### REQ-8.4 Documentation for operator workflows

The project SHALL document end-to-end operator workflows for local use and CI usage.

**Acceptance:**

- Documentation includes "first run", "triage failures", "manage waivers", and "compare against baseline" workflows.
- Each workflow includes copy-paste command examples and expected output artefacts.
- Links between roadmap milestones and REQ-8 requirements are explicit.

### REQ-8.5 Operator success metrics (competitor benchmark)

The project SHALL define and track objective UX outcomes for beta phase 2 to validate that operator experience is better than incumbent tooling.

**Acceptance:**

- Mean time to identify root-cause controls from a failed run is reduced by at least 50% from initial baseline.
- Mean time to assemble an audit evidence pack for a scoped review is reduced to under 30 minutes.
- Expired waiver misses are reduced to near-zero through proactive visibility and alerting.

---

## REQ-9 Compliance dashboarding

### REQ-9.1 Dashboard product model

The system SHALL provide a dashboard experience for compliance operations as part of beta phase 2.

The dashboard SHALL support both:

- single-file offline viewer artefacts for sharing and audit review
- hosted dashboard mode for continuous, multi-run visibility

**Acceptance:**

- Both modes render the same canonical compliance semantics (status, evidence, waivers, framework tags).
- Users can navigate from summary to control-level evidence without leaving the dashboard context.

### REQ-9.2 Posture and trend analytics

The dashboard SHALL present posture over time, not only point-in-time runs.

**Acceptance:**

- Trend views include PASS/FAIL/SKIP/ERROR/WAIVED counts over selectable periods.
- Users can filter trends by profile, host group, environment, and framework tag namespace.
- Dashboard highlights regressions since baseline (new FAILs, new ERRORs, waiver expiry regressions).

### REQ-9.3 Waiver governance board

The dashboard SHALL make waiver lifecycle management first-class.

**Acceptance:**

- Dedicated waiver views show active, expiring, and expired waivers.
- Waivers are filterable by owner, control id, host scope, and expiry window.
- Expired waivers are visually prioritised as policy breaches.

### REQ-9.4 Framework rollups and coverage

The dashboard SHALL provide compliance-framework-centric views for NIST, CIS, and STIG mappings.

**Acceptance:**

- Framework rollups display pass/fail/error rates by mapped control families.
- Coverage view identifies mapped vs unmapped controls for each selected framework.
- Drill-down from framework family to host/control evidence is available in two clicks or fewer.

### REQ-9.5 Triage workflow acceleration

The dashboard SHALL optimise failure triage workflows for operators.

**Acceptance:**

- From a failed control tile, users can open affected hosts, latest evidence, and baseline diff directly.
- "What changed since last good run" is a first-class view, not a manual query.
- Top regressions are ranked by impact and host breadth.

### REQ-9.6 Audit pack generation and provenance

The dashboard SHALL support audit-ready exports with provenance integrity.

**Acceptance:**

- Users can export scoped audit packs by profile, framework, environment, and date range.
- Export includes run metadata, overlay provenance, waiver context, and evidence excerpts.
- Exported ordering is deterministic and reproducible from canonical JSON.

### REQ-9.7 Alerts and operational notifications

The system SHALL support operational alerting for compliance events.

**Acceptance:**

- Alerts can be configured for new critical failures, waiver expiry windows, and risk-score spikes.
- Alert payloads include direct links to the relevant dashboard drill-down view.
- Alert routing supports at least one team channel integration in beta (for example Slack or Teams).

### REQ-9.8 Dashboard performance and reliability SLOs

Dashboard responsiveness SHALL be treated as a product requirement.

**Acceptance:**

- Posture overview loads in under 2 seconds for target beta data size.
- Filtered drill-down views load in under 3 seconds for target beta data size.
- Data freshness from completed run to dashboard visibility is under 60 seconds in hosted mode.

---

## REQ-10 Packaging and container delivery

### REQ-10.1 Package distribution

Attest SHALL be distributed as installable packages for local and CI usage.

**Acceptance:**

- Python package distribution is published for the CLI/runtime components.
- Versioned releases provide reproducible installation (pinned versions and changelog reference).
- Package install path is documented for both local developer use and CI runners.

### REQ-10.2 Official container images

Attest SHALL publish official container images in addition to packages.

**Acceptance:**

- At least one official image exists for CLI execution and one for dashboard/hosted UI components.
- Images are version-tagged and include a stable tag strategy (for example `vX.Y.Z` and `latest`).
- Images run as non-root by default unless explicitly overridden.

### REQ-10.3 Compose-first deployment target

Docker Compose SHALL be the first orchestrated deployment target.

Compose deployment SHALL support the minimum beta operating model:

- dashboard service
- supporting data store/service dependencies required by hosted mode
- configuration via environment variables and mounted configuration files

**Acceptance:**

- A reference `compose.yaml` can start a functional hosted dashboard stack from official images.
- Compose startup and shutdown workflows are documented with copy-paste commands.
- Healthcheck status indicates when the stack is ready for use.

### REQ-10.4 Container security and supply-chain baseline

Container delivery SHALL satisfy minimum security and provenance controls.

**Acceptance:**

- Container images are scanned in CI with Snyk before release.
- Release metadata includes image digest references and SBOM location.
- Critical vulnerabilities in first-party image layers block release unless explicitly waived.

### REQ-10.5 Runtime parity across package and container modes

Running Attest from packages or official containers SHALL produce equivalent canonical results for identical inputs.

**Acceptance:**

- Canonical JSON outputs are equivalent across package-mode and container-mode runs (excluding timestamp/run-id fields).
- Reporter outputs (JSON/JUnit/Markdown and configured viewer/dashboard exports) are functionally equivalent across modes.
- Any intentional behaviour differences are documented and tested.

---

## Related documents

- [Attest overview and architecture](../design/attest-overview-and-architecture.md) — Design principles and architecture layers
- [Technical architecture](../design/architecture.md) — Detailed layer design, code structure, and data flows
- [Roadmap](../roadmap/roadmap.md) — Which requirements are targeted in each milestone
- [Contributing](../../CONTRIBUTING.md) — How to implement requirements and link issues
