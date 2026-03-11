# Attest technical architecture

This document describes the technical architecture of Attest, designed for v0.1-beta implementation and beyond. It's written for implementers, core contributors, and architects.

For a high-level overview, see [Attest overview and architecture](attest-overview-and-architecture.md).

## Design approach

Attest is built in **four distinct layers**, each with clear responsibility boundaries and stable contracts between them. This design enables:

- **Parallel development** — Teams can work on different layers independently
- **Testability** — Each layer can be tested in isolation
- **Extensibility** — New resources, reporters, and features can be added without rewriting core logic
- **Maintainability** — Changes are localized to their layer

## Architecture layers

Attest's execution pipeline flows through these layers:

```text
Policy layer (parse/validate) → 
Resource layer (gather facts) → 
Engine/runner layer (evaluate) → 
Reporting layer (output reports)
```

Each layer produces a well-defined contract that the next layer consumes.

### 1) Policy layer — Parse and prepare

**Responsibility:**

- Parse profiles and controls from YAML
- Validate schemas (profile title, control IDs, test syntax, etc.)
- Resolve applicability (`only_if`/`skip_if` conditions)
- Load inputs (CLI flags, survey vars, inventory vars, profile defaults) with priority ordering
- Resolve dependencies and generate a lockfile
- Generate an execution plan

**Key inputs:**

- `profile.yml` — Profile metadata, inputs definition, dependencies
- `controls/*.yml` — Individual control definitions and tests
- `waivers.yml` — Exceptions with expiry and justification
- CLI arguments, inventory variables

**Key outputs:**

- Validated, typed execution plan
- Resolved control list (sorted deterministically)
- Lockfile for reproducible runs
- Applicability decisions (which controls apply to which hosts)

**Contract guarantees:**

- Identical inputs → identical execution plan (deterministic)
- Invalid profiles/controls fail fast with actionable errors
- All required inputs are validated before execution

**Example:**

```text
Input: profile.yml + linux-inventory.yml
Validation: ✓ schema OK, ✓ all controls have IDs, ✓ required inputs provided
Output: execution plan with 12 controls, 24 hosts, 5 waivers
```

### 2) Resource layer — Gather system facts

**Responsibility:**

- Collect structured facts from target systems
- Provide a consistent interface for the Engine to query system state
- Cache results (same resource query per host per run returns cached result)
- Handle errors gracefully (resource failures don't stop execution)

**Contract:**

Each resource returns:

```json
{
  "data": { /* structured fact object */ },
  "errors": [ /* error messages if any */ ],
  "timings": { /* query duration */ }
}
```

**Beta resource set:**

- `file` — File existence, permissions, ownership, content matching
- `package` — Package installation and version
- `service` — Service status and enablement
- `sysctl` — Kernel parameter values
- `command` — Command execution and output
- `port` — Network port listening state
- `os_facts` — Basic OS/distribution information

**Example:**

```text
Query: file(path=/etc/sudoers, provides: is_read_only)
Host: web-01
Response: { "data": { "is_read_only": true }, "errors": [], "timings": { "query_ms": 12 } }
Cached: Yes (same query won't re-run on same host)
```

**Performance requirement:**

- All resource queries must be cacheable per host per run
- Caching strategy: results are cached in memory during a run; subsequent identical queries return immediately

### 3) Engine/runner layer — Evaluate controls

**Responsibility:**

- Execute the evaluation pipeline
- Evaluate each control's tests against gathered facts
- Aggregate test results into control status
- Determine if a control is applicable
- Apply waivers (exceptions) to failing controls
- Capture evidence and redact sensitive data
- Build the canonical report

**Execution pipeline (per control):**

1. **Check applicability** — Evaluate `only_if` / `skip_if` conditions
   - If not applicable → status = SKIP (with reason)
   - Otherwise → proceed

2. **Query resources** — Gather facts needed for this control's tests
   - Uses Resource layer (results are cached)
   - If a resource fails → test status = ERROR

3. **Evaluate tests** — Run each test's assertion against gathered facts
   - PASS: assertion evaluates to true
   - FAIL: assertion evaluates to false
   - ERROR: exception during evaluation

4. **Aggregate control status** — Combine all test results
   - If any test FAILs → control status = FAIL
   - If all tests PASS → control status = PASS
   - If any test ERROR (and no FAIL) → control status = ERROR
   - If control skipped → control status = SKIP

5. **Apply waivers** — Check if a failing control has an active waiver
   - If control FAILs but has active waiver (not expired) → status = WAIVED
   - Otherwise → status unchanged

6. **Capture evidence** — Record facts and test results for audit trail
   - What was checked (test name, assertion)
   - What was found (actual value from facts)
   - What was expected
   - Did it match?

**Result semantics:**

- **PASS** — All assertions passed; control is in compliance
- **FAIL** — At least one assertion failed; control is out of compliance
- **SKIP** — Control not applicable to this host/system
- **ERROR** — Unrecoverable error during evaluation (resource failure, syntax error)
- **WAIVED** — Control is failing but exception granted (justification and expiry recorded)

**Execution modes:**

- **CLI mode** — Run locally, output reports to stdout or file
- **Job mode** — Run in orchestration context (Ansible, AAP), write reports to designated directory for artefact collection

**Example:**

```text
Control: SSH root login disabled

Test 1: Check sshd config PermitRootLogin setting
  - Resource query: sshd_config()
  - Assertion: ansible_local.sshd.permit_root_login == 'no'
  - Result: PASS (fact value is 'no')

Test 2: Verify SSH service is running
  - Resource query: service(name='sshd')
  - Assertion: service.state == 'running'
  - Result: PASS (service is running)

Control status: PASS (all tests passed)
```

### 4) Reporting layer — Generate output formats

**Responsibility:**

- Transform the canonical JSON report into user-facing formats
- Generate compliance summaries and artifacts
- Support integration with CI/CD systems

**Source of truth:**

Canonical JSON report — machine-readable, contains all evidence, full audit trail.

**Output formats:**

- **Canonical JSON** (source of truth)
  - Complete report with all controls, tests, evidence, timings
  - Schema is versioned; used by all derivations
  - Deterministic field ordering for stable diffs

- **JUnit XML**
  - CI/CD integration (fail builds on test failures)
  - One test case per control
  - Failures and skips map correctly

- **Markdown summary**
  - Human-readable report
  - Statistics (pass/fail/skip counts, impact summary)
  - Failure details with evidence

- **Summary artefact** (`attest-summary.json`)
  - Lightweight JSON for dashboards
  - Control counts, host summary, top failures
  - Suitable for downstream compliance workflows

**Example:**

Canonical JSON snippet:

```json
{
  "schema_version": "1.0",
  "profile": "linux-hardening",
  "timestamp": "2026-03-10T14:22:15Z",
  "results": [
    {
      "control_id": "LH-001",
      "status": "PASS",
      "tests": [
        {
          "name": "SSH root login disabled",
          "assertion": "sshd.permit_root_login == 'no'",
          "actual": "no",
          "expected": "no",
          "result": "PASS"
        }
      ]
    }
  ]
}
```

---

## Code structure and organisation

### Repository layout (single-repo)

**Python (product logic):**

```text
src/attest/
  ├── policy/
  │   ├── loader.py       (YAML parsing)
  │   ├── schemas.py      (Pydantic schemas for validation)
  │   ├── validator.py    (profile/control validation)
  │   └── resolver.py     (dependency resolution, lockfile)
  ├── resources/
  │   ├── interfaces.py   (resource contract definitions)
  │   ├── file.py         (file resource implementation)
  │   ├── package.py      (package resource implementation)
  │   └── ... (other resources)
  ├── engine/
  │   ├── evaluator.py    (core evaluation engine)
  │   ├── cache.py        (resource result caching)
  │   ├── applicability.py (only_if/skip_if evaluation)
  │   └── aggregator.py   (test/control result aggregation)
  ├── report/
  │   ├── canonical.py    (canonical JSON schema and writer)
  │   ├── junit.py        (JUnit XML reporter)
  │   ├── markdown.py     (Markdown reporter)
  │   └── summary.py      (summary artefact generator)
  ├── waivers/
  │   ├── schema.py       (waiver validation)
  │   └── applier.py      (apply waivers to results)
  ├── diff/
  │   ├── baseline.py     (baseline storage and loading)
  │   └── differ.py       (compute drift between runs)
  ├── cli.py             (command-line interface)
  └── __init__.py

tests/
  ├── test_policy/       (policy module tests)
  ├── test_resources/    (resource module tests)
  ├── test_engine/       (evaluation engine tests)
  ├── test_report/       (reporting tests)
  └── test_smoke.py      (integration smoke tests)
```

**Ansible (future-facing; may be stubs in beta):**

```text
collections/attest.resources/
  └── plugins/modules/  (Ansible modules for custom facts)

collections/attest.runner/
  └── roles/           (Ansible roles wrapping attest CLI)

collections/attest.reporters/
  └── plugins/callbacks/ (Ansible callback for reporting)
```

**Documentation:**

```text
docs/
  ├── index.md                              (docs hub)
  ├── design/
  │   ├── attest-overview-and-architecture.md (high-level overview)
  │   └── architecture.md                   (this file)
  ├── requirements/requirements.md          (REQ-1, REQ-2, etc.)
  └── roadmap/roadmap.md                   (milestones)
```

---

## Data flow (end-to-end example)

Running: `attest run linux-hardening -i inventory.yml -o report.json`

1. **Policy layer**
   - Parse `profile.yml`, `controls/*.yml`, `waivers.yml`
   - Parse CLI inputs and inventory
   - Validate everything
   - Output: execution plan with 12 controls, 8 hosts

2. **Resource layer** (per host)
   - Host: web-01
   - Query: file, package, service, sysctl for controls applicable to this host
   - Results cached for the run
   - If a query fails → record error (but continue)

3. **Engine/runner layer** (per control per host)
   - Evaluate all tests for each control
   - Aggregate results
   - Check waivers
   - Build result entry: `{ control_id, status, tests[], evidence }`

4. **Reporting layer**
   - Output: `report.json` (canonical JSON)
   - Derive: `report.xml` (JUnit)
   - Derive: `report.md` (Markdown summary)
   - Derive: `attest-summary.json`

---

## Determinism and reproducibility

**Determinism is non-negotiable** because drift reporting depends on identical inputs producing identical outputs.

**What must be deterministic:**

- Profiles, controls, and tests are sorted consistently (by ID, alphabetically)
- Hosts are sorted consistently
- File paths are normalised
- Test assertions always evaluate identically
- Report schema is versioned and immutable

**What may vary:**

- Timestamps (`timestamp` field is explicitly variable)
- Run IDs (can be randomised)
- Execution duration (recorded but not part of output stability)
- Host IP addresses (system facts, not under Attest control)

**Example:**

```text
Run 1: attest run profile.yml -i hosts.txt
Output: report.json contains control LH-001 as test #1

Run 2: attest run profile.yml -i hosts.txt (same inputs)
Output: report.json contains control LH-001 as test #1

Diff: Only `timestamp` differs; everything else is identical
→ Drift detection can safely compare outputs
```

---

## Scope for v0.1-beta

See [Scope for v0.1-beta](attest-overview-and-architecture.md#scope-for-v01-beta) in the overview document. The architecture described here covers all in-scope layers for beta.

---

## Quality and testing

**Testing strategy:**

- **Unit tests** — Test each layer in isolation (mocked dependencies)
- **Integration tests** — Test layer contracts with real implementations
- **Smoke tests** — End-to-end tests with sample profiles

**Quality gates (CI):**

- All tests pass: `pytest`
- Code quality: `ruff check .`, Snyk security scans, SonarQube analysis
- Documentation is updated if behaviour changes

---

## Related documents

- [Attest overview and architecture](attest-overview-and-architecture.md) — High-level design and principles
- [Requirements](../requirements/requirements.md) — Functional and non-functional requirements (REQ-1 through REQ-9)
- [Roadmap](../roadmap/roadmap.md) — Development milestones and sequencing
- [Contributing](../../CONTRIBUTING.md) — How to implement
