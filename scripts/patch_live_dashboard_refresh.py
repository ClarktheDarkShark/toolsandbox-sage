#!/usr/bin/env python
"""Patch generated dashboard HTML during an already-running experiment.

The protocol runner may have imported dashboard templates before a source fix
was made. This script applies the same browser-side refresh hardening directly
to generated HTML files and can watch for runner rewrites.
"""

from __future__ import annotations

import argparse
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

TASK_COMPARE_TIMER_OLD = """      if (refreshTimer === null) {
        refreshTimer = window.setInterval(() => {
          refresh({preserveScroll: true}).catch((error) => console.error(error));
        }, 5000);
      }
    }

"""

TASK_COMPARE_TIMER_NEW = """      if (refreshTimer === null) {
        refreshTimer = window.setInterval(() => {
          refresh({preserveScroll: true}).catch((error) => {
            if (!isTransientDataError(error)) console.error(error);
          });
        }, 5000);
      }
    }

    function isTransientDataError(error) {
      const message = String(error?.message || error || "");
      return error instanceof SyntaxError || message.includes("empty dashboard data");
    }

    const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

    async function fetchDashboardJson(url) {
      const response = await fetch(url, {cache: "no-store"});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const text = await response.text();
      if (!text.trim()) throw new SyntaxError("empty dashboard data");
      return JSON.parse(text);
    }

"""

TASK_COMPARE_REFRESH_OLD = """    async function refresh(options = {}) {
      const scrollState = options.preserveScroll ? captureScrollState() : null;
      const response = await fetch(`task_compare_data.json?ts=${Date.now()}`, {cache: "no-store"});
      payload = await response.json();
"""

TASK_COMPARE_REFRESH_NEW = """    async function refresh(options = {}) {
      const scrollState = options.preserveScroll ? captureScrollState() : null;
      let lastError = null;
      for (let attempt = 0; attempt < 3; attempt += 1) {
        try {
          payload = await fetchDashboardJson(`task_compare_data.json?ts=${Date.now()}`);
          lastError = null;
          break;
        } catch (error) {
          lastError = error;
          if (!isTransientDataError(error)) throw error;
          await sleep(250);
        }
      }
      if (lastError) {
        if (payload && isTransientDataError(lastError)) return;
        throw lastError;
      }
"""

TASK_COMPARE_LOAD_OLD = """    load().catch((error) => {
      document.getElementById("detail").innerHTML = `<div class="section"><strong>Dashboard load failed.</strong><pre>${esc(error.stack || error.message || error)}</pre></div>`;
      console.error(error);
    });
"""

TASK_COMPARE_LOAD_NEW = """    load().catch((error) => {
      if (isTransientDataError(error)) {
        window.setTimeout(load, 1000);
        return;
      }
      document.getElementById("detail").innerHTML = `<div class="section"><strong>Dashboard load failed.</strong><pre>${esc(error.stack || error.message || error)}</pre></div>`;
      console.error(error);
    });
"""

TASK_COMPARE_TOOL_PANEL_CSS = """    .live-tool-panel {
      display: none;
      max-width: 960px;
      margin-top: 10px;
      border: 1px solid var(--line);
      background: var(--panel2);
      border-radius: 8px;
      padding: 10px 12px;
      box-shadow: 0 8px 22px var(--shadow);
    }
    .live-tool-panel.active {
      display: block;
    }
    .live-tool-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
      color: var(--muted);
      font-size: 12px;
    }
    .live-tool-head strong {
      color: var(--text);
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: .06em;
    }
    .live-tool-table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 8px;
      font-size: 12px;
      font-variant-numeric: tabular-nums;
    }
    .live-tool-table th,
    .live-tool-table td {
      border-top: 1px solid var(--line);
      padding: 6px 5px;
      text-align: left;
      vertical-align: top;
    }
    .live-tool-table th {
      color: var(--muted);
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: .06em;
    }
    .live-tool-name {
      max-width: 270px;
      overflow-wrap: anywhere;
      color: var(--ink);
      font-weight: 750;
    }
"""

TASK_COMPARE_TOOL_PANEL_JS = """    function renderToolSummaryPanel() {
      const panel = document.getElementById("liveToolPanel");
      if (!panel) return;
      const tools = payload?.tool_summary || {};
      const rows = Array.isArray(tools.tools) ? tools.tools : [];
      if (!rows.length) {
        panel.innerHTML = "";
        panel.classList.remove("active");
        return;
      }
      const topRows = rows.slice(0, 8).map((tool) => `<tr>
        <td class="live-tool-name">${esc(tool.name || "-")}<div class="small">${esc(tool.decision || "")}</div></td>
        <td>${esc(maybeValue(tool.visible_count))}</td>
        <td>${esc(tool.called_count ?? 0)}</td>
        <td class="${cls(tool.called_subset_mean_outcome_delta)}">${signedNum(tool.called_subset_mean_outcome_delta)}</td>
        <td>${esc(gainLossText(tool.outcome_gains, tool.outcome_regressions))}</td>
        <td>${esc(tool.side_effect_incident_count ?? 0)} side-effect<br><span class="small">${esc(tool.runtime_incident_count ?? 0)} runtime</span></td>
      </tr>`).join("");
      const summary = [
        `${intNum(tools.visible_tool_count ?? 0)} visible`,
        `${intNum(tools.called_tool_count ?? 0)} called`,
        `${intNum(tools.outcome_gains ?? 0)} gains`,
        `${intNum(tools.outcome_regressions ?? 0)} regressions`,
        `${intNum(tools.side_effect_incident_count ?? 0)} side-effect rows`,
        `${intNum(tools.runtime_incident_count ?? 0)} runtime incidents`,
      ].join(" / ");
      panel.innerHTML = `<div class="live-tool-head"><strong>Live Tool Contribution</strong><span>${esc(summary)}</span></div>
        <table class="live-tool-table">
          <thead><tr><th>Tool</th><th>Visible</th><th>Called</th><th>Outcome Delta</th><th>Gain / Regression</th><th>Safety</th></tr></thead>
          <tbody>${topRows}</tbody>
        </table>`;
      panel.classList.add("active");
    }

"""

INDEX_REFRESH_OLD = """        const res = await fetch(`data.json?ts=${Date.now()}`, { cache: "no-store" });
        if (!res.ok) throw new Error(`${res.status}`);
        render(await res.json());
"""

INDEX_REFRESH_NEW = """        render(await fetchDashboardJson(`data.json?ts=${Date.now()}`));
"""

INDEX_HELPER_INSERT = """    async function fetchDashboardJson(url) {
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) throw new Error(`${res.status}`);
      const text = await res.text();
      if (!text.trim()) throw new SyntaxError("empty dashboard data");
      return JSON.parse(text);
    }
"""

INDEX_CATCH_OLD = """      } catch (err) {
        document.getElementById("subtitle").textContent = `Dashboard data unavailable: ${err}`;
      }
"""

INDEX_CATCH_NEW = """      } catch (err) {
        if (!state || !(err instanceof SyntaxError)) {
          document.getElementById("subtitle").textContent = `Dashboard data unavailable: ${err}`;
        }
      }
"""

FOCUS_REFRESH_OLD = """        const r = await fetch(`task_focus_data.json?ts=${Date.now()}`, {cache:"no-store"});
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        data = await r.json();
"""

FOCUS_REFRESH_NEW = """        data = await fetchDashboardJson(`task_focus_data.json?ts=${Date.now()}`);
"""

FOCUS_HELPER_INSERT = """    async function fetchDashboardJson(url) {
      const r = await fetch(url, {cache:"no-store"});
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const text = await r.text();
      if (!text.trim()) throw new SyntaxError("empty dashboard data");
      return JSON.parse(text);
    }

"""

FOCUS_CATCH_OLD = """      } catch(e) {
        document.getElementById("chat").innerHTML = `<div class="empty">Data unavailable: ${esc(e.message)}</div>`;
      }
"""

FOCUS_CATCH_NEW = """      } catch(e) {
        if (!data || !(e instanceof SyntaxError)) {
          document.getElementById("chat").innerHTML = `<div class="empty">Data unavailable: ${esc(e.message)}</div>`;
        }
      }
"""


def _atomic_write(path: Path, text: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as handle:
        handle.write(text)
        temp = Path(handle.name)
    temp.replace(path)


def _patch_task_compare(text: str) -> str:
    if "fetchDashboardJson(`task_compare_data.json" not in text:
        text = text.replace(TASK_COMPARE_TIMER_OLD, TASK_COMPARE_TIMER_NEW)
        text = text.replace(TASK_COMPARE_REFRESH_OLD, TASK_COMPARE_REFRESH_NEW)
        text = text.replace(TASK_COMPARE_LOAD_OLD, TASK_COMPARE_LOAD_NEW)
    if ".live-tool-panel" not in text:
        text = text.replace(
            "    .run-progress {\n",
            TASK_COMPARE_TOOL_PANEL_CSS + "    .run-progress {\n",
            1,
        )
    if 'id="liveToolPanel"' not in text:
        text = text.replace(
            '    <div class="cache-panel" id="cachePanel"></div>\n',
            '    <div class="cache-panel" id="cachePanel"></div>\n    <div class="live-tool-panel" id="liveToolPanel"></div>\n',
            1,
        )
    if "function renderToolSummaryPanel()" not in text:
        text = text.replace(
            "    function maybeValue(value) {\n",
            TASK_COMPARE_TOOL_PANEL_JS + "    function maybeValue(value) {\n",
            1,
        )
    if "renderToolSummaryPanel();" not in text:
        text = text.replace(
            "      renderCachePanel();\n",
            "      renderCachePanel();\n      renderToolSummaryPanel();\n",
            1,
        )
    return text


def _patch_index(text: str) -> str:
    if "fetchDashboardJson(`data.json" not in text:
        text = text.replace(
            "    async function refresh() {\n",
            INDEX_HELPER_INSERT + "    async function refresh() {\n",
            1,
        )
        text = text.replace(INDEX_REFRESH_OLD, INDEX_REFRESH_NEW)
        text = text.replace(INDEX_CATCH_OLD, INDEX_CATCH_NEW)
    return text


def _patch_focus(text: str) -> str:
    if "fetchDashboardJson(`task_focus_data.json" not in text:
        text = text.replace(
            "    async function refresh() {\n",
            FOCUS_HELPER_INSERT + "    async function refresh() {\n",
            1,
        )
        text = text.replace(FOCUS_REFRESH_OLD, FOCUS_REFRESH_NEW)
        text = text.replace(FOCUS_CATCH_OLD, FOCUS_CATCH_NEW)
    return text


def patch_dashboard(dashboard_dir: Path) -> list[Path]:
    patchers = {
        "task_compare.html": _patch_task_compare,
        "index.html": _patch_index,
        "task_focus.html": _patch_focus,
    }
    changed: list[Path] = []
    for name, patcher in patchers.items():
        path = dashboard_dir / name
        if not path.is_file():
            continue
        old = path.read_text(encoding="utf-8")
        new = patcher(old)
        if new != old:
            _atomic_write(path, new)
            changed.append(path)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard-dir", required=True, type=Path)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=2.0)
    args = parser.parse_args()

    while True:
        changed = patch_dashboard(args.dashboard_dir)
        if changed:
            names = ", ".join(path.name for path in changed)
            print(
                f"{datetime.now(timezone.utc).isoformat()} patched {names}", flush=True
            )
        if not args.watch:
            break
        time.sleep(max(args.interval_seconds, 0.2))


if __name__ == "__main__":
    main()
