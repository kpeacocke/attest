# Operator workflows

This guide covers end-to-end workflows for running Attest locally and in CI pipelines.
Each workflow is designed for daily engineering use as part of a compliance-as-code practice.

Related requirements: REQ-7.1, REQ-7.2, REQ-8.1, REQ-8.4.

---

## Prerequisites

Install Attest via Poetry (development) or pip (release):

```bash
# Development
poetry install

# Release (once published)
pip install attest
```

Verify the installation:

```bash
attest version
# attest 0.1.0
```

---

## Workflow 1: First run

This workflow runs a compliance profile against the local host and reviews the report artefacts.

**Step 1 - Validate the profile before running:**

```bash
attest validate ./profiles/my-profile/
# Profile 'my-profile' v1.0.0 is valid (12 controls).
```

Exit code 0 means the profile schema and controls loaded cleanly.
Exit code 4 means there is a schema or configuration error - the error message will point to the specific problem.

**Step 2 - Run the profile:**

```bash
attest run ./profiles/my-profile/ --out ./reports/
```

By default, Attest emits `report.json` and `attest-summary.json` in the output directory.

To emit all supported formats in one invocation (REQ-4.2):

```bash
attest run ./profiles/my-profile/ --out ./reports/ \
  --format json \
  --format junit \
  --format markdown \
  --format summary
```

Expected output artefacts:

| File | Description |
|------|-------------|
| `report.json` | Canonical JSON report (all evidence) |
| `report.xml` | JUnit XML for CI tooling |
| `report.md` | Markdown summary for human review |
| `attest-summary.json` | Small deterministic summary for pipeline gating |

**Step 3 - Check the exit code:**

| Exit code | Meaning |
|-----------|---------|
| 0 | All controls PASS (WAIVED controls are allowed) |
| 2 | One or more controls FAIL |
| 3 | One or more controls ERROR (could not be evaluated) |
| 4 | Validation or configuration error |

**Step 4 - Review the summary:**

```bash
cat reports/attest-summary.json
```

The summary includes: run id, profile, host, counts by status, and a risk score.

---

## Workflow 2: Triage failures

When a run exits with code 2 (FAIL), Attest prints actionable failure details directly to the terminal.

**Reading terminal output:**

```
Failures on localhost:
  [C-001] SSH root login disabled (impact=0.9)
    - check sshd: expected='no' got='yes'
      Expected 'no', got 'yes'. (PermitRootLogin sshd_config)
```

Each failure shows:

- Control ID and title
- Impact score (0.0 - 1.0; higher = more critical)
- Per-test: the assertion name, expected value, and observed value
- An optional message with remediation context

**Reading the Markdown report:**

Open `reports/report.md` in a Markdown viewer or render it in your CI pipeline.

The report starts with an executive summary including:

- Status counts table
- Risk score
- Top failing controls by impact (up to 5)

Below the summary are expanded failure sections with per-test evidence, grouped by control.

**Filtering failures by impact:**

Use `jq` to list failing controls sorted by impact:

```bash
jq '[.results[] | select(.status=="FAIL")] | sort_by(-.impact) | .[] | {id:.control_id, title, impact}' \
  reports/report.json
```

**Checking for ERROR controls:**

```bash
jq '[.results[] | select(.status=="ERROR")] | .[] | {id:.control_id, title}' \
  reports/report.json
```

An ERROR usually means a resource was unavailable (e.g. an unknown resource type).
Review the `tests[].message` field for the specific cause.

---

## Workflow 3: Manage waivers

Waivers record accepted exceptions to compliance controls. They have an expiry date and justification.

**Waiver file format:**

Create a `waivers.yml` in the profile directory (or pass `--waivers <path>`):

```yaml
waivers:
  - id: W-001
    control_id: C-002
    justification: Accepted pending patching window - tracked in JIRA-1234
    owner: platform-team
    expiry: 2026-12-31
    reference: https://jira.example.com/browse/JIRA-1234
```

Multiple control IDs can share a waiver:

```yaml
waivers:
  - id: W-002
    control_ids:
      - C-003
      - C-004
    justification: Legacy system - migrating Q1 2027
    owner: infra-team
    expiry: 2027-03-31
```

**Running with waivers:**

Attest auto-discovers `waivers.yml` in the profile directory:

```bash
attest run ./profiles/my-profile/ --out ./reports/
```

Or specify a path explicitly:

```bash
attest run ./profiles/my-profile/ --out ./reports/ --waivers ./waivers/prod.yml
```

**Waiver behaviour:**

| Waiver state | Control status | Exit code impact |
|-------------|----------------|-----------------|
| Active (not expired) | WAIVED | 0 (no impact) |
| Expired | FAIL with `waiver_expired: true` | 2 |

**Expired waiver warnings:**

The Markdown report has a dedicated "Expired waivers - policy breach" section that is visually distinct.
Renew or remediate expired waivers immediately - they are counted as FAILs and will drive exit code 2.

**Checking waiver status from JSON:**

```bash
# List WAIVED controls with waiver ID
jq '[.results[] | select(.status=="WAIVED")] | .[] | {id:.control_id, waiver:.waiver_id}' \
  reports/report.json

# List expired waivers
jq '[.results[] | select(.waiver_expired==true)] | .[] | {id:.control_id, waiver:.waiver_id}' \
  reports/report.json
```

---

## Workflow 4: Compare against baseline (drift detection)

Use `attest diff` to detect drift between a known-good baseline run and a current run.

**Step 1 - Save a baseline:**

Run Attest and keep the `report.json` as your baseline:

```bash
attest run ./profiles/my-profile/ --out ./baselines/2026-03-12/
# Produces baselines/2026-03-12/report.json
```

**Step 2 - Run a current check:**

```bash
attest run ./profiles/my-profile/ --out ./reports/current/
```

**Step 3 - Diff the two reports:**

```bash
attest diff ./baselines/2026-03-12/report.json ./reports/current/report.json --out ./reports/diff/
```

Output artefacts:

| File | Description |
|------|-------------|
| `diff.json` | Machine-readable diff (new failures, new passes, waiver changes) |
| `diff.md` | Markdown diff summary for human review |

**Exit codes for `attest diff`:**

| Exit code | Meaning |
|-----------|---------|
| 0 | No new failures or errors since baseline |
| 2 | New failures detected since baseline |
| 3 | New errors detected since baseline |
| 4 | Input or configuration error |

**Reading the diff JSON:**

```bash
jq '.new_failures' reports/diff/diff.json
jq '.new_passes' reports/diff/diff.json
jq '.waiver_changes' reports/diff/diff.json
```

---

## CI usage

### GitHub Actions example

```yaml
- name: Run Attest
  run: |
    attest run ./profiles/hardening/ \
      --out ./attest-reports/ \
      --format json \
      --format junit \
      --format markdown \
      --format summary

- name: Upload Attest reports
  uses: actions/upload-artifact@v4
  if: always()
  with:
    name: attest-reports
    path: attest-reports/

- name: Publish JUnit results
  uses: actions/publish-unit-test-results@v3
  if: always()
  with:
    files: attest-reports/report.xml
```

The exit code from `attest run` will fail the step on FAIL (exit 2) or ERROR (exit 3).
Use `if: always()` on report upload steps to collect artefacts even when controls fail.

### Using `attest-summary.json` as a pipeline gate

```bash
FAIL_COUNT=$(jq '.fail_count' attest-reports/attest-summary.json)
if [ "$FAIL_COUNT" -gt "0" ]; then
  echo "Compliance failures detected: $FAIL_COUNT"
  exit 2
fi
```

---

## Further reading

- [Architecture overview](../design/architecture.md)
- [Requirements](../requirements/requirements.md)
- [Roadmap](../roadmap/roadmap.md)
