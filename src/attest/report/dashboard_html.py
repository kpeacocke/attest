"""Dashboard HTML renderer for offline and hosted modes (REQ-9.1)."""

from __future__ import annotations

import json
from html import escape
from typing import Any

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__</title>
  <style>
    :root {
      --bg: #f6f1e7;
      --panel: #fffaf0;
      --panel-2: #efe4cf;
      --ink: #1f1a12;
      --muted: #6f6657;
      --accent: #8a5a23;
      --pass: #29553d;
      --fail: #8f2b2b;
      --error: #6f2260;
      --skip: #7a6a1f;
      --waived: #215a78;
      --border: #d7c7a9;
      --mono: "Iosevka", Consolas, monospace;
      --sans: "Source Sans 3", "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top right, rgba(138,90,35,0.17), transparent 33%),
        linear-gradient(180deg, #f4ecdc 0%, var(--bg) 100%);
      font-family: var(--sans);
    }
    .shell { width: min(1220px, calc(100vw - 24px)); margin: 16px auto 36px; }
    .hero, .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px;
      margin-bottom: 14px;
      box-shadow: 0 12px 26px rgba(50, 33, 15, 0.09);
    }
    .hero h1 { margin: 0; font-size: clamp(1.8rem, 3.2vw, 2.6rem); }
    .hero p { margin: 8px 0 0; color: var(--muted); }
    .kpis { display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); margin-top: 12px; }
    .kpi { border: 1px solid var(--border); border-radius: 12px; background: #fffdf7; padding: 10px; }
    .kpi strong { display: block; font-size: 1.5rem; }
    .kpi.pass strong { color: var(--pass); }
    .kpi.fail strong { color: var(--fail); }
    .kpi.error strong { color: var(--error); }
    .kpi.skip strong { color: var(--skip); }
    .kpi.waived strong { color: var(--waived); }
    .tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
    .tab { border: 1px solid var(--border); border-radius: 999px; padding: 8px 12px; background: #fffdf8; cursor: pointer; font-weight: 700; }
    .tab.active { background: var(--panel-2); color: var(--accent); }
    .view { display: none; }
    .view.active { display: block; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 8px; border-bottom: 1px solid var(--border); vertical-align: top; }
    th { color: var(--muted); font-size: 0.86rem; }
    .badge { border: 1px solid currentColor; border-radius: 999px; padding: 3px 8px; font-size: 0.76rem; font-weight: 700; }
    .badge.PASS { color: var(--pass); }
    .badge.FAIL { color: var(--fail); }
    .badge.ERROR { color: var(--error); }
    .badge.SKIP { color: var(--skip); }
    .badge.WAIVED { color: var(--waived); }
    .filters { display: grid; gap: 8px; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); margin-bottom: 12px; }
    .filters input, .filters select { width: 100%; padding: 8px; border: 1px solid var(--border); border-radius: 10px; background: #fffdf8; }
    .mono { font-family: var(--mono); font-size: 0.88rem; }
    .muted { color: var(--muted); }
    .link { color: var(--accent); text-decoration: none; }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <h1 id="title">Attest Dashboard</h1>
      <p id="subtitle"></p>
      <div class="kpis" id="kpis"></div>
    </section>

    <section class="panel">
      <div class="tabs" id="tabs"></div>

      <div id="view-posture" class="view active">
        <h2>Posture trends</h2>
        <table>
          <thead>
            <tr><th>Timestamp</th><th>Run</th><th>Profile</th><th>Host</th><th>PASS</th><th>FAIL</th><th>ERROR</th><th>Risk</th></tr>
          </thead>
          <tbody id="posture-rows"></tbody>
        </table>
      </div>

      <div id="view-frameworks" class="view">
        <h2>Framework rollups</h2>
        <div id="framework-content"></div>
      </div>

      <div id="view-waivers" class="view">
        <h2>Waiver governance board</h2>
        <div class="filters">
          <input id="waiver-owner" placeholder="Owner filter">
          <input id="waiver-control" placeholder="Control ID filter">
          <select id="waiver-state">
            <option value="all">All states</option>
            <option value="active">Active</option>
            <option value="expiring">Expiring</option>
            <option value="expired">Expired</option>
          </select>
        </div>
        <table>
          <thead>
            <tr><th>State</th><th>Waiver</th><th>Control</th><th>Owner</th><th>Host</th><th>Expiry</th><th>Days</th></tr>
          </thead>
          <tbody id="waiver-rows"></tbody>
        </table>
      </div>

      <div id="view-triage" class="view">
        <h2>Triage acceleration</h2>
        <h3>Top regressions</h3>
        <table>
          <thead>
            <tr><th>Control</th><th>Title</th><th>Impact</th><th>Host breadth</th><th>Score</th><th>Evidence</th></tr>
          </thead>
          <tbody id="regression-rows"></tbody>
        </table>
        <h3>Changed since last good run</h3>
        <table>
          <thead>
            <tr><th>Control</th><th>From</th><th>To</th></tr>
          </thead>
          <tbody id="changed-rows"></tbody>
        </table>
      </div>

      <div id="view-alerts" class="view">
        <h2>Operational alerts</h2>
        <table>
          <thead>
            <tr><th>Type</th><th>Severity</th><th>Details</th><th>Link</th></tr>
          </thead>
          <tbody id="alert-rows"></tbody>
        </table>
      </div>

      <div id="view-evidence" class="view">
        <h2>Control evidence drill-down</h2>
        <div class="filters">
          <select id="status-filter"></select>
          <input id="control-filter" placeholder="Control ID or title">
          <select id="host-filter"></select>
          <select id="tag-filter"></select>
        </div>
        <table>
          <thead>
            <tr><th>Control</th><th>Status</th><th>Host</th><th>Impact</th><th>Evidence</th></tr>
          </thead>
          <tbody id="evidence-rows"></tbody>
        </table>
      </div>
    </section>
  </div>

  <script>
    const data = __DATA__;

    function esc(v) {
      return String(v)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function byId(id) { return document.getElementById(id); }

    function initTabs() {
      const views = [
        ["posture", "Posture"],
        ["frameworks", "Frameworks"],
        ["waivers", "Waivers"],
        ["triage", "Triage"],
        ["alerts", "Alerts"],
        ["evidence", "Evidence"],
      ];
      byId("tabs").innerHTML = views.map(([id, label], idx) => `<button class=\"tab ${idx===0?"active":""}\" data-view=\"${id}\">${label}</button>`).join("");
      document.querySelectorAll(".tab").forEach((btn) => {
        btn.addEventListener("click", () => {
          document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
          btn.classList.add("active");
          document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
          byId(`view-${btn.dataset.view}`).classList.add("active");
        });
      });
    }

    function renderHeader() {
      const latest = data.runs[data.runs.length - 1] || {};
      byId("title").textContent = `Attest Dashboard - ${latest.profile?.title || latest.profile?.name || "Unknown profile"}`;
      byId("subtitle").textContent = `Latest run ${latest.run_id || ""} on ${latest.host || "unknown"} at ${latest.timestamp || ""}`;
      const counts = latest.summary?.counts || {};
      const kpis = ["PASS", "FAIL", "ERROR", "SKIP", "WAIVED"].map((s) => `<div class=\"kpi ${s.toLowerCase()}\"><div class=\"muted\">${s}</div><strong>${counts[s] || 0}</strong></div>`);
      kpis.push(`<div class=\"kpi\"><div class=\"muted\">Risk</div><strong>${latest.summary?.risk_score || 0}</strong></div>`);
      byId("kpis").innerHTML = kpis.join("");
    }

    function renderPosture() {
      const rows = data.posture_trends?.series || [];
      byId("posture-rows").innerHTML = rows.map((r) => `
+        <tr>
+          <td class=\"mono\">${esc(r.timestamp)}</td>
+          <td class=\"mono\">${esc(r.run_id)}</td>
+          <td>${esc(r.profile)}</td>
+          <td>${esc(r.host)}</td>
+          <td>${esc(r.counts?.PASS || 0)}</td>
+          <td>${esc(r.counts?.FAIL || 0)}</td>
+          <td>${esc(r.counts?.ERROR || 0)}</td>
+          <td>${esc(r.risk_score || 0)}</td>
+        </tr>
+      `).join("");
    }

    function renderFrameworks() {
      const roll = data.framework_rollups || {};
      function section(title, rows, key) {
        const body = rows.map((r) => `<tr><td>${esc(r[key])}</td><td>${esc(r.counts.PASS)}</td><td>${esc(r.counts.FAIL)}</td><td>${esc(r.counts.ERROR)}</td><td>${esc(r.pass_rate)}</td></tr>`).join("");
        return `
+          <h3>${title}</h3>
+          <table>
+            <thead><tr><th>${key}</th><th>PASS</th><th>FAIL</th><th>ERROR</th><th>Pass rate</th></tr></thead>
+            <tbody>${body || "<tr><td colspan='5' class='muted'>No mapped controls</td></tr>"}</tbody>
+          </table>
+        `;
      }
      byId("framework-content").innerHTML =
        section("NIST families", roll.nist?.families || [], "family") +
        section("CIS levels", roll.cis_level?.levels || [], "level") +
        section("STIG severity", roll.stig_severity?.levels || [], "severity");
    }

    function collectWaivers() {
      const board = data.waiver_board || {};
      const rows = [];
      for (const state of ["active", "expiring", "expired"]) {
        for (const r of board[state] || []) {
          rows.push({ state, ...r });
        }
      }
      return rows;
    }

    function renderWaivers() {
      const ownerQ = byId("waiver-owner").value.trim().toLowerCase();
      const controlQ = byId("waiver-control").value.trim().toLowerCase();
      const state = byId("waiver-state").value;
      const filtered = collectWaivers().filter((r) => {
        if (state !== "all" && r.state !== state) return false;
        if (ownerQ && !String(r.owner || "").toLowerCase().includes(ownerQ)) return false;
        if (controlQ && !String(r.control_id || "").toLowerCase().includes(controlQ)) return false;
        return true;
      });
      byId("waiver-rows").innerHTML = filtered.map((r) => `
+        <tr id=\"waiver-${esc(r.waiver_id)}\">
+          <td>${esc(r.state)}</td>
+          <td class=\"mono\">${esc(r.waiver_id)}</td>
+          <td class=\"mono\">${esc(r.control_id)}</td>
+          <td>${esc(r.owner)}</td>
+          <td>${esc(r.host)}</td>
+          <td class=\"mono\">${esc(r.expiry)}</td>
+          <td>${esc(r.days_to_expiry)}</td>
+        </tr>
+      `).join("");
    }

    function renderTriage() {
      const regs = data.triage?.top_regressions || [];
      byId("regression-rows").innerHTML = regs.map((r) => `
+        <tr>
+          <td class=\"mono\">${esc(r.control_id)}</td>
+          <td>${esc(r.title || "")}</td>
+          <td>${esc(r.impact)}</td>
+          <td>${esc(r.host_breadth)}</td>
+          <td>${esc(r.score)}</td>
+          <td><a class=\"link\" href=\"${esc(r.evidence_anchor)}\">open</a></td>
+        </tr>
+      `).join("");

      const changed = data.triage?.changed_since_last_good || [];
      byId("changed-rows").innerHTML = changed.map((r) => `
+        <tr><td class=\"mono\">${esc(r.control_id)}</td><td>${esc(r.from)}</td><td>${esc(r.to)}</td></tr>
+      `).join("");
    }

    function renderAlerts() {
      const alerts = data.alerts?.alerts || [];
      byId("alert-rows").innerHTML = alerts.map((a) => `
+        <tr>
+          <td>${esc(a.type)}</td>
+          <td>${esc(a.severity)}</td>
+          <td class=\"mono\">${esc(a.control_id || a.waiver_id || `${a.from || ""} -> ${a.to || ""}`)}</td>
+          <td><a class=\"link\" href=\"${esc(a.link || "#") }\">open</a></td>
+        </tr>
+      `).join("");
    }

    function evidenceRows() {
      const latest = data.runs[data.runs.length - 1] || { results: [] };
      return latest.results || [];
    }

    function renderEvidence() {
      const status = byId("status-filter").value;
      const controlQ = byId("control-filter").value.trim().toLowerCase();
      const host = byId("host-filter").value;
      const ns = byId("tag-filter").value;
      const rows = evidenceRows().filter((r) => {
        if (status !== "all" && r.status !== status) return false;
        if (host !== "all" && (r.host || data.runs[data.runs.length - 1]?.host) !== host) return false;
        if (controlQ) {
          const t = `${r.control_id || ""} ${r.title || ""}`.toLowerCase();
          if (!t.includes(controlQ)) return false;
        }
        if (ns !== "all") {
          const tags = r.tags || {};
          const v = tags[ns];
          if (v === undefined || v === null || v === "" || (Array.isArray(v) && v.length === 0)) return false;
        }
        return true;
      });

      byId("evidence-rows").innerHTML = rows.map((r) => {
        const tests = (r.tests || []).slice(0, 2).map((t) => `${t.name}: expected=${t.expected} actual=${t.actual}`).join(" | ");
        return `
+          <tr id=\"control-${esc(r.control_id)}\">
+            <td class=\"mono\">${esc(r.control_id)}</td>
+            <td><span class=\"badge ${esc(r.status)}\">${esc(r.status)}</span></td>
+            <td>${esc(r.host || data.runs[data.runs.length - 1]?.host || "unknown")}</td>
+            <td>${esc(r.impact ?? "-")}</td>
+            <td class=\"mono\">${esc(tests || "no evidence")}</td>
+          </tr>
+        `;
      }).join("");
    }

    function initEvidenceFilters() {
      const latest = data.runs[data.runs.length - 1] || {};
      const host = latest.host || "unknown";
      byId("status-filter").innerHTML = ["all", "PASS", "FAIL", "ERROR", "SKIP", "WAIVED"].map((s) => `<option value=\"${s}\">${s}</option>`).join("");
      byId("host-filter").innerHTML = [`<option value=\"all\">all</option>`, `<option value=\"${esc(host)}\">${esc(host)}</option>`].join("");
      byId("tag-filter").innerHTML = ["all", "nist", "cis_level", "stig_severity", "custom"].map((s) => `<option value=\"${s}\">${s}</option>`).join("");
      ["status-filter", "control-filter", "host-filter", "tag-filter"].forEach((id) => {
        byId(id).addEventListener("input", renderEvidence);
        byId(id).addEventListener("change", renderEvidence);
      });
    }

    function initWaiverFilters() {
      ["waiver-owner", "waiver-control", "waiver-state"].forEach((id) => {
        byId(id).addEventListener("input", renderWaivers);
        byId(id).addEventListener("change", renderWaivers);
      });
    }

    initTabs();
    renderHeader();
    renderPosture();
    renderFrameworks();
    renderTriage();
    renderAlerts();
    initEvidenceFilters();
    initWaiverFilters();
    renderWaivers();
    renderEvidence();
  </script>
</body>
</html>
"""


def build_dashboard_html(dataset: dict[str, Any], *, title: str = "Attest Dashboard") -> str:
    payload = json.dumps(dataset, ensure_ascii=True, separators=(",", ":"))
    return _HTML_TEMPLATE.replace("__TITLE__", escape(title)).replace("__DATA__", payload)


def write_dashboard_html(
    dataset: dict[str, Any], path: str, *, title: str = "Attest Dashboard"
) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_dashboard_html(dataset, title=title))
        fh.write("\n")
