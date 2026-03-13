"""Single-file offline HTML report viewer (REQ-8.3)."""

from __future__ import annotations

import json
from html import escape
from typing import Any

_STATUS_ORDER = ["PASS", "FAIL", "ERROR", "SKIP", "WAIVED"]
_TAG_NAMESPACE_ORDER = ["all", "nist", "cis_level", "stig_severity", "custom"]

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="utf-8">
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<title>__TITLE__</title>
	<style>
		:root {
			color-scheme: light;
			--bg: #f7f2e8;
			--panel: #fffaf1;
			--panel-strong: #f1e3c6;
			--ink: #1f1a14;
			--muted: #6a5f52;
			--accent: #7d4e1d;
			--pass: #285943;
			--fail: #9e2a2b;
			--error: #7a1f5c;
			--skip: #7f6f1f;
			--waived: #1f5c7a;
			--border: #d8c7aa;
			--shadow: 0 18px 40px rgba(47, 31, 15, 0.12);
			--mono: "Iosevka", "SFMono-Regular", Consolas, monospace;
			--sans: "Source Sans 3", "Segoe UI", sans-serif;
		}

		* { box-sizing: border-box; }
		body {
			margin: 0;
			font-family: var(--sans);
			color: var(--ink);
			background:
				radial-gradient(circle at top right, rgba(125, 78, 29, 0.18), transparent 30%),
				linear-gradient(180deg, #f4ecdd 0%, var(--bg) 100%);
		}
		.shell {
			width: min(1200px, calc(100vw - 32px));
			margin: 24px auto 48px;
		}
		.hero {
			padding: 28px;
			border: 1px solid var(--border);
			border-radius: 24px;
			background: linear-gradient(140deg, rgba(255,250,241,0.96), rgba(241,227,198,0.92));
			box-shadow: var(--shadow);
		}
		.eyebrow {
			margin: 0 0 8px;
			text-transform: uppercase;
			letter-spacing: 0.12em;
			font-size: 0.78rem;
			color: var(--accent);
		}
		h1 { margin: 0; font-size: clamp(2rem, 4vw, 3.4rem); line-height: 0.95; }
		.meta {
			margin-top: 18px;
			display: grid;
			gap: 12px;
			grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		}
		.meta-card, .stats-card, .filters, .results {
			background: var(--panel);
			border: 1px solid var(--border);
			border-radius: 20px;
			box-shadow: var(--shadow);
		}
		.meta-card, .stats-card { padding: 16px 18px; }
		.meta-label, .filter-label { font-size: 0.82rem; color: var(--muted); display: block; margin-bottom: 6px; }
		.meta-value { font-size: 1rem; font-weight: 700; word-break: break-word; }
		.grid {
			margin-top: 22px;
			display: grid;
			gap: 18px;
		}
		.stats { grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); }
		.stats-card strong { display: block; font-size: 1.8rem; margin-top: 8px; }
		.stats-card[data-status="PASS"] strong { color: var(--pass); }
		.stats-card[data-status="FAIL"] strong { color: var(--fail); }
		.stats-card[data-status="ERROR"] strong { color: var(--error); }
		.stats-card[data-status="SKIP"] strong { color: var(--skip); }
		.stats-card[data-status="WAIVED"] strong { color: var(--waived); }
		.filters { padding: 18px; }
		.filter-grid { display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
		.filter-grid input, .filter-grid select {
			width: 100%;
			padding: 11px 12px;
			border: 1px solid var(--border);
			border-radius: 12px;
			background: #fffdf8;
			color: var(--ink);
			font: inherit;
		}
		.filter-note { margin: 14px 0 0; color: var(--muted); font-size: 0.92rem; }
		.results { padding: 18px; }
		.result-list { display: grid; gap: 14px; }
		.result-card {
			border: 1px solid var(--border);
			border-radius: 16px;
			background: #fffdf8;
			padding: 18px;
		}
		.result-top { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; justify-content: space-between; }
		.result-title { margin: 0; font-size: 1.1rem; }
		.badge {
			display: inline-flex;
			align-items: center;
			gap: 6px;
			padding: 6px 10px;
			border-radius: 999px;
			font-size: 0.83rem;
			font-weight: 700;
			letter-spacing: 0.02em;
			border: 1px solid currentColor;
		}
		.badge.pass { color: var(--pass); }
		.badge.fail { color: var(--fail); }
		.badge.error { color: var(--error); }
		.badge.skip { color: var(--skip); }
		.badge.waived { color: var(--waived); }
		.subtle { color: var(--muted); }
		.result-meta { display: flex; gap: 14px; flex-wrap: wrap; margin: 10px 0 0; color: var(--muted); font-size: 0.95rem; }
		.evidence { margin: 14px 0 0; padding-left: 18px; }
		.evidence li { margin-bottom: 8px; }
		code { font-family: var(--mono); font-size: 0.9em; }
		.tag-row { margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; }
		.tag {
			border-radius: 999px;
			background: var(--panel-strong);
			padding: 5px 10px;
			font-size: 0.82rem;
			color: var(--accent);
		}
		.empty { padding: 24px; text-align: center; color: var(--muted); }
		@media (max-width: 720px) {
			.shell { width: min(100vw - 20px, 1200px); margin-top: 12px; }
			.hero { padding: 20px; border-radius: 18px; }
			.results, .filters { padding: 14px; }
		}
	</style>
</head>
<body>
	<div class="shell">
		<section class="hero">
			<p class="eyebrow">Attest offline viewer</p>
			<h1 id="report-title"></h1>
			<div class="meta" id="meta"></div>
		</section>

		<section class="grid stats" id="stats"></section>

		<section class="filters">
			<div class="filter-grid">
				<label>
					<span class="filter-label">Status</span>
					<select id="status-filter"></select>
				</label>
				<label>
					<span class="filter-label">Control ID</span>
					<input id="control-filter" type="search" placeholder="Search control IDs or titles">
				</label>
				<label>
					<span class="filter-label">Host</span>
					<select id="host-filter"></select>
				</label>
				<label>
					<span class="filter-label">Framework tag namespace</span>
					<select id="namespace-filter"></select>
				</label>
			</div>
			<p class="filter-note">Filtering is client-side only. Result order remains the canonical JSON order.</p>
		</section>

		<section class="results">
			<div class="result-list" id="result-list"></div>
			<div class="empty" id="empty-state" hidden>No controls match the active filters.</div>
		</section>
	</div>

	<script>
		const viewerData = __REPORT_JSON__;

		const titleEl = document.getElementById("report-title");
		const metaEl = document.getElementById("meta");
		const statsEl = document.getElementById("stats");
		const resultListEl = document.getElementById("result-list");
		const emptyStateEl = document.getElementById("empty-state");
		const statusFilterEl = document.getElementById("status-filter");
		const controlFilterEl = document.getElementById("control-filter");
		const hostFilterEl = document.getElementById("host-filter");
		const namespaceFilterEl = document.getElementById("namespace-filter");

		function escapeHtml(value) {
			return String(value)
				.replace(/&/g, "&amp;")
				.replace(/</g, "&lt;")
				.replace(/>/g, "&gt;")
				.replace(/\"/g, "&quot;")
				.replace(/'/g, "&#39;");
		}

		function renderMeta() {
			const profile = viewerData.profile || {};
			titleEl.textContent = profile.title || profile.name || "Attest report";
			const items = [
				["Profile", (profile.name || "-") + (profile.version ? " v" + profile.version : "")],
				["Host", viewerData.host || "unknown"],
				["Run ID", viewerData.run_id || "-"],
				["Timestamp", viewerData.timestamp || "-"],
			];
			metaEl.innerHTML = items.map(([label, value]) => `
				<div class="meta-card">
					<span class="meta-label">${escapeHtml(label)}</span>
					<div class="meta-value">${escapeHtml(value)}</div>
				</div>
			`).join("");
		}

		function renderStats() {
			const counts = (viewerData.summary && viewerData.summary.counts) || {};
			const risk = (viewerData.summary && viewerData.summary.risk_score) || 0;
			const cards = viewerData.filter_options.statuses.map((status) => `
				<div class="stats-card" data-status="${status}">
					<span class="meta-label">${status}</span>
					<strong>${counts[status] || 0}</strong>
				</div>
			`);
			cards.push(`
				<div class="stats-card">
					<span class="meta-label">Risk score</span>
					<strong>${escapeHtml(risk)}</strong>
				</div>
			`);
			statsEl.innerHTML = cards.join("");
		}

		function populateSelect(selectEl, options, selected) {
			selectEl.innerHTML = options
				.map((value) => `<option value="${escapeHtml(value)}"${value === selected ? " selected" : ""}>${escapeHtml(value)}</option>`)
				.join("");
		}

		function initialFilters() {
			populateSelect(statusFilterEl, ["all", ...viewerData.filter_options.statuses], "all");
			populateSelect(hostFilterEl, viewerData.filter_options.hosts, viewerData.host);
			populateSelect(namespaceFilterEl, viewerData.filter_options.tag_namespaces, "all");
			controlFilterEl.value = "";
		}

		function testItems(result) {
			const tests = Array.isArray(result.tests) ? result.tests : [];
			if (!tests.length) {
				return "<li class=\"subtle\">No test evidence recorded.</li>";
			}
			return tests.map((test) => `
				<li>
					<strong>${escapeHtml(test.name || "unnamed")}</strong>
					<span class="subtle">${escapeHtml(test.status || "unknown")}</span>
					<div><code>expected=${escapeHtml(test.expected ?? "")}</code> <code>actual=${escapeHtml(test.actual ?? "")}</code></div>
					${test.message ? `<div class="subtle">${escapeHtml(test.message)}</div>` : ""}
				</li>
			`).join("");
		}

		function tagItems(result) {
			const tags = result.tags || {};
			const namespace = namespaceFilterEl.value;
			const entries = [];
			for (const [key, value] of Object.entries(tags)) {
				if (namespace !== "all" && key !== namespace) {
					continue;
				}
				if (Array.isArray(value)) {
					for (const item of value) {
						entries.push(`<span class=\"tag\">${escapeHtml(key + ": " + item)}</span>`);
					}
				} else if (value !== null && value !== undefined && value !== "") {
					entries.push(`<span class=\"tag\">${escapeHtml(key + ": " + value)}</span>`);
				}
			}
			return entries.join("");
		}

		function matchesFilters(result) {
			const status = statusFilterEl.value;
			const controlQuery = controlFilterEl.value.trim().toLowerCase();
			const host = hostFilterEl.value;
			const namespace = namespaceFilterEl.value;
			const resultHost = result.host || viewerData.host;

			if (status !== "all" && result.status !== status) {
				return false;
			}
			if (host !== "all" && resultHost !== host) {
				return false;
			}
			if (controlQuery) {
				const haystack = `${result.control_id || ""} ${result.title || ""}`.toLowerCase();
				if (!haystack.includes(controlQuery)) {
					return false;
				}
			}
			if (namespace !== "all") {
				const tags = result.tags || {};
				const value = tags[namespace];
				if (value === undefined || value === null || value === "" || (Array.isArray(value) && !value.length)) {
					return false;
				}
			}
			return true;
		}

		function renderResults() {
			const filtered = viewerData.results.filter(matchesFilters);
			resultListEl.innerHTML = filtered.map((result) => {
				const statusClass = String(result.status || "unknown").toLowerCase();
				const tags = tagItems(result);
				return `
					<article class="result-card">
						<div class="result-top">
							<div>
								<h2 class="result-title">${escapeHtml(result.control_id || "unknown")} - ${escapeHtml(result.title || "Untitled control")}</h2>
								<div class="result-meta">
									<span>Host: ${escapeHtml(result.host || viewerData.host)}</span>
									<span>Impact: ${escapeHtml(result.impact ?? "-")}</span>
									${result.waiver_id ? `<span>Waiver: ${escapeHtml(result.waiver_id)}</span>` : ""}
								</div>
							</div>
							<span class="badge ${statusClass}">${escapeHtml(result.status || "UNKNOWN")}</span>
						</div>
						${result.skip_reason ? `<p class="subtle">${escapeHtml(result.skip_reason)}</p>` : ""}
						${tags ? `<div class="tag-row">${tags}</div>` : ""}
						<ul class="evidence">${testItems(result)}</ul>
					</article>
				`;
			}).join("");
			emptyStateEl.hidden = filtered.length !== 0;
		}

		function wireFilters() {
			for (const element of [statusFilterEl, controlFilterEl, hostFilterEl, namespaceFilterEl]) {
				element.addEventListener("input", renderResults);
				element.addEventListener("change", renderResults);
			}
		}

		renderMeta();
		renderStats();
		initialFilters();
		wireFilters();
		renderResults();
	</script>
</body>
</html>
"""


def _normalise_host(report: dict[str, Any]) -> str:
    host = report.get("host", "unknown")
    return host if isinstance(host, str) and host else "unknown"


def _viewer_payload(report: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic payload for the offline viewer from canonical JSON."""
    host = _normalise_host(report)
    return {
        "schema_version": report.get("schema_version", "1.0"),
        "run_id": report.get("run_id", ""),
        "timestamp": report.get("timestamp", ""),
        "profile": report.get("profile", {}),
        "host": host,
        "summary": report.get("summary", {}),
        "tag_summaries": report.get("tag_summaries", {}),
        "results": list(report.get("results", [])),
        "filter_options": {
            "statuses": _STATUS_ORDER,
            "hosts": [host],
            "tag_namespaces": _TAG_NAMESPACE_ORDER,
        },
    }


def build_html(report: dict[str, Any]) -> str:
    """Build a deterministic single-file HTML viewer from a canonical report."""
    payload = _viewer_payload(report)
    report_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    title = escape(
        str(
            payload.get("profile", {}).get("title")
            or payload.get("profile", {}).get("name")
            or "Attest report"
        )
    )
    return _HTML_TEMPLATE.replace("__TITLE__", title).replace("__REPORT_JSON__", report_json)


def write_html(report: dict[str, Any], path: str) -> None:
    """Write the offline HTML viewer to disk."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_html(report))
        fh.write("\n")
