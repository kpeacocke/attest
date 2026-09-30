# Operator workflows

This guide covers end-to-end workflows for running Attest locally and in CI pipelines.
Each workflow is designed for daily engineering use as part of a compliance-as-code practice.

Related requirements: REQ-7.1, REQ-7.2, REQ-8.1, REQ-8.3, REQ-8.4, REQ-9.1, REQ-9.2, REQ-9.3, REQ-9.4, REQ-9.5, REQ-9.6, REQ-9.7, REQ-9.8.

---

## Prerequisites

Install Attest from source with Poetry. After a version tag has been released, download its wheel and `constraints.txt` from GitHub Releases for pinned CI or local installs (REQ-10.1):

```bash
# Development
poetry install

# Release (after v0.1.0 is published)
python -m pip install --constraint constraints.txt ./attest-0.1.0-py3-none-any.whl
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

To emit all supported formats in one invocation (REQ-4.2, REQ-8.3):

```bash
attest run ./profiles/my-profile/ --out ./reports/ \
  --format json \
  --format junit \
  --format markdown \
  --format summary \
  --format html
```

Expected output artefacts:

| File | Description |
|------|-------------|
| `report.json` | Canonical JSON report (all evidence) |
| `report.xml` | JUnit XML for CI tooling |
| `report.md` | Markdown summary for human review |
| `attest-summary.json` | Small deterministic summary for pipeline gating |
| `report.html` | Single-file offline viewer with client-side filtering |

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

**Step 5 - Open the offline viewer when you need interactive review:**

Open `reports/report.html` in a browser. The viewer is a single exported artefact for offline review and sharing.

Available client-side filters:

- Status
- Control ID or title search
- Host
- Framework tag namespace (`nist`, `cis_level`, `stig_severity`, `custom`)

The viewer preserves the deterministic ordering from canonical JSON. Filtering only narrows what is shown; it does not reorder controls.

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

## Workflow 5: Build the compliance dashboard artefacts

Use `attest dashboard build` to aggregate canonical reports and generate offline and hosted dashboard outputs.

```bash
attest dashboard build ./reports/ --out ./dashboard/
```

Output artefacts:

| File | Description |
|------|-------------|
| `dashboard.json` | Aggregated dataset for posture trends, framework rollups, waivers, and triage |
| `dashboard.html` | Single-file dashboard view for operators |
| `dashboard-alerts.json` | Alert payload generated from trend and regression data |
| `dashboard-slo.json` | SLO evaluation report over latest posture signals |

The dashboard includes:

- Posture trend series by run, host, profile, and environment (REQ-9.1)
- Top regressions and changed-since-last-good triage views (REQ-9.2)
- Waiver governance board with active, expiring, and expired buckets (REQ-9.3)
- Framework rollups and coverage for NIST, CIS, and STIG tags (REQ-9.4)

---

## Workflow 6: Export evidence for auditors

Build a scoped audit pack from an existing `dashboard.json` dataset:

```bash
attest dashboard audit-pack ./dashboard/dashboard.json \
  --framework nist \
  --host prod-host-1 \
  --out ./dashboard/audit-pack.json
```

The audit pack preserves canonical evidence while narrowing scope by profile, host, environment, or framework namespace (REQ-9.5).

---

## Workflow 7: Generate and deliver compliance alerts

Create alert outputs from dashboard data:

```bash
attest dashboard alerts ./dashboard/dashboard.json --out ./dashboard/alerts.json
```

Optional Slack delivery for operations channels:

```bash
attest dashboard alerts ./dashboard/dashboard.json \
  --out ./dashboard/alerts.json \
  --slack-webhook "$SLACK_WEBHOOK_URL"
```

Alert categories include risk-score spikes, new critical failures, expired waivers, and control regressions (REQ-9.6).

---

## Workflow 8: Evaluate dashboard SLOs

Generate SLO status from dashboard posture:

```bash
attest dashboard slo ./dashboard/dashboard.json --out ./dashboard/dashboard-slo.json
```

If one or more SLO targets fail, the command exits with code `2` so CI can gate on compliance service levels (REQ-9.7).

---

## Workflow 9: Run hosted dashboard mode

Serve dashboard artefacts for local hosted operation:

```bash
attest dashboard serve ./dashboard/ --port 8080
```

Then open `http://127.0.0.1:8080/dashboard.html` for interactive use (REQ-9.8).

Hosted mode serves generated static artefacts only; rebuild with `attest dashboard build` when new reports are available.

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

## Measure operator outcomes (REQ-8.5)

Collect opt-in, anonymised baseline and current observations over comparable profile scopes and operator cohorts. Each CSV has exactly `metric,value` columns; keep operator names, hosts, control IDs, evidence and other identifiers out of these files. Record:

- `triage_seconds`: elapsed time from a failed run becoming available until the root-cause control is identified.
- `audit_pack_seconds`: elapsed time from agreeing a scoped review to completing its audit evidence pack.
- `expired_waiver_miss`: one row per expired waiver, `1` if it was not noticed before expiry or `0` if it was.

For example, with measured observations in `baseline.csv` and `current.csv`:

```csv
metric,value
triage_seconds,180
audit_pack_seconds,900
expired_waiver_miss,0
```

```bash
attest metrics baseline.csv current.csv --out operator-metrics.json
```

The deterministic JSON records sample counts, means and target results. Triage must improve by at least 50% against a non-zero baseline; average audit-pack time must be **under** 1800 seconds; the working definition of near-zero is at most 1% missed expiry events. Missing observations produce `null` target results, not a pass. The command reports measurements but does not invent a baseline, automatically track user activity, or prove an improvement from a tiny sample. Collect enough real observations before claiming REQ-8.5 acceptance. Invalid input exits with code `4`.

---

## Package and container delivery (REQ-10.1 to REQ-10.4)

The tag-triggered package release workflow requires a tag matching `pyproject.toml` (for example `v0.1.0`), a configured `SNYK_TOKEN` repository secret, and GitHub Actions permission to publish GHCR images. It tests the package, scans both images for critical vulnerabilities before publishing, and uploads wheel, source archive, runtime constraints, checksums and image digests to GitHub Releases. Image SBOM attestations are attached to the digest-pinned GHCR images. Release notes link to the [changelog](../../CHANGELOG.md). Do not create a release tag until the secret and registry permissions are ready. Newly published GHCR packages may require a registry login or a visibility change before operators can pull them.

After a release, run the CLI with a versioned image and a mounted profile directory:

```bash
docker run --rm --read-only -v "$PWD:/work" ghcr.io/kpeacocke/attest:v0.1.0 version
```

The hosted dashboard currently serves **prebuilt** artefacts from a read-only mounted directory. Build them first from canonical reports, then start the Compose reference (REQ-10.3):

```bash
attest dashboard build ./reports/report.json --out ./dashboard
export ATTEST_DASHBOARD_DIR="$PWD/dashboard"
docker compose up -d
docker compose ps
# Open http://localhost:8080/dashboard.html after the dashboard service is healthy.
docker compose down
```

For a local image build before the first published tag, run `docker build --target dashboard -t attest-dashboard:local .` and set `ATTEST_DASHBOARD_IMAGE=attest-dashboard:local` before `docker compose up -d`. Set `ATTEST_DASHBOARD_PORT` to change the host port. The mounted directory is the current hosted data store; Compose does not add continuous report ingestion or a database.
Compose binds the dashboard to localhost by default. Do not expose this HTTP endpoint directly to untrusted networks; put an authenticated TLS reverse proxy in front of it when remote access is required. The package/container parity check compares canonical, JUnit, Markdown, HTML and dashboard exports while excluding generated run IDs, timestamps and time-derived freshness durations (REQ-10.5).

---

## Further reading

- [Architecture overview](../design/architecture.md)
- [Requirements](../requirements/requirements.md)
- [Roadmap](../roadmap/roadmap.md)
