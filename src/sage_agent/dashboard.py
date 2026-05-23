"""Environment-neutral dashboard export for standalone SAGE runs."""

from __future__ import annotations

import html
import json
import shutil
import socket
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import quote

from sage_agent.controller import SAGERunSummary


def write_standalone_dashboard(
    summary: SAGERunSummary,
    output_dir: Path,
    *,
    registry_path: Path | None = None,
    baseline: dict[str, Any] | None = None,
    run_metadata: dict[str, Any] | None = None,
) -> Path:
    """Write a self-contained dashboard for any standalone SAGE adapter."""

    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir = output_dir / "dashboard"
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    summary_payload = asdict(summary)
    registry_payload = _read_registry_payload(registry_path)
    data_payload = {
        "summary": summary_payload,
        "registry": registry_payload,
        "baseline": baseline or {},
        "run_metadata": run_metadata or {},
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "dashboard_data.json").write_text(
        json.dumps(data_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    (dashboard_dir / "task_compare_data.json").write_text(
        json.dumps(data_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    (dashboard_dir / "dashboard_data.json").write_text(
        json.dumps(data_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    if registry_path and registry_path.exists():
        shutil.copyfile(registry_path, output_dir / "registry.json")
    index_path = dashboard_dir / "index.html"
    task_compare_path = dashboard_dir / "task_compare.html"
    rendered = _dashboard_html(data_payload)
    index_path.write_text(rendered, encoding="utf-8")
    task_compare_path.write_text(rendered, encoding="utf-8")
    return task_compare_path


def open_standalone_dashboard(index_path: Path, *, port: int = 62630) -> str:
    """Open a standalone dashboard through a repo-root static server."""

    ensure_standalone_dashboard_server(port=port)
    repo_root = _repo_root()
    try:
        relative = index_path.resolve().relative_to(repo_root)
    except ValueError:
        relative = index_path.resolve()
    url = f"http://127.0.0.1:{port}/{quote(str(relative), safe='/')}"
    subprocess.Popen(
        ["open", url],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return url


def ensure_standalone_dashboard_server(*, port: int = 62630) -> None:
    """Start a repo-root static server if the requested port is unused."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        if sock.connect_ex(("127.0.0.1", port)) == 0:
            return
    subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port)],
        cwd=_repo_root(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_registry_payload(registry_path: Path | None) -> dict[str, Any]:
    if registry_path is None or not registry_path.exists():
        return {"schema_version": 1, "tools": {}}
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"schema_version": 1, "tools": {}}


def _dashboard_html(payload: dict[str, Any]) -> str:
    embedded = html.escape(json.dumps(payload), quote=False)
    template = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Task Compare - SAGE Standalone</title>
  <style>
    :root {
      --bg: #0b1118;
      --panel: #111a24;
      --panel2: #172332;
      --panel3: #0f1722;
      --line: #2b3a4d;
      --text: #e7edf5;
      --muted: #93a4b8;
      --green: #41d996;
      --red: #ff6b73;
      --amber: #ffc857;
      --blue: #77bdff;
      --shadow: rgba(0, 0, 0, .35);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    button, input { font: inherit; }
    header {
      border-bottom: 1px solid var(--line);
      background: var(--panel);
      padding: 18px 22px 14px;
      position: relative;
      z-index: 5;
    }
    h1 { margin: 0; font-size: 22px; letter-spacing: 0; }
    h2 { margin: 0; font-size: 19px; letter-spacing: 0; }
    h3 { margin: 0 0 10px; font-size: 15px; }
    .title-line {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
    }
    .env-badge {
      border: 1px solid #3f80bd;
      background: #102c45;
      color: #bfeaff;
      border-radius: 999px;
      padding: 5px 10px;
      font-size: 12px;
      font-weight: 900;
      letter-spacing: .04em;
      text-transform: uppercase;
    }
    .header-row {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: flex-start;
    }
    .dashboard-switch {
      flex: 0 0 auto;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--panel2);
      color: var(--blue);
      padding: 7px 10px;
      font-size: 12px;
      font-weight: 800;
      min-width: 140px;
      text-align: center;
    }
    .subtitle {
      color: var(--muted);
      font-size: 13px;
      margin-top: 5px;
      overflow-wrap: anywhere;
    }
    .run-progress {
      display: inline-flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: 10px;
      margin-top: 12px;
      border: 1px solid var(--line);
      background: var(--panel2);
      border-radius: 999px;
      padding: 7px 12px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.2;
      box-shadow: 0 8px 22px var(--shadow);
    }
    .run-progress .label {
      color: var(--muted);
      font-size: 10px;
      font-weight: 800;
      letter-spacing: .1em;
      text-transform: uppercase;
    }
    .run-progress strong {
      color: var(--text);
      font-size: 15px;
      font-variant-numeric: tabular-nums;
    }
    .run-stage {
      display: block;
      margin-top: 7px;
      color: var(--blue);
      font-size: 12px;
      font-weight: 700;
      max-width: 980px;
      overflow-wrap: anywhere;
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(3, minmax(180px, 1fr));
      gap: 10px;
      margin-top: 10px;
      max-width: 960px;
    }
    .metric {
      border: 1px solid var(--line);
      background: var(--panel2);
      border-radius: 8px;
      padding: 10px 12px;
      min-height: 78px;
      box-shadow: 0 8px 22px var(--shadow);
    }
    .metric.clickable {
      cursor: pointer;
      border-color: #3f80bd;
      background: #162a3d;
    }
    .label {
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .08em;
      text-transform: uppercase;
    }
    .value {
      font-size: 24px;
      font-weight: 800;
      margin-top: 8px;
      font-variant-numeric: tabular-nums;
      overflow-wrap: anywhere;
    }
    .hint {
      color: var(--muted);
      font-size: 12px;
      margin-top: 4px;
      line-height: 1.3;
    }
    .good { color: var(--green); }
    .bad { color: var(--red); }
    .warn { color: var(--amber); }
    main {
      display: grid;
      grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
      min-height: calc(100vh - 150px);
    }
    aside {
      border-right: 1px solid var(--line);
      background: #0d151f;
      padding: 14px;
      position: sticky;
      top: 12px;
      align-self: start;
      height: calc(100vh - 24px);
      overflow: auto;
    }
    .detail-wrap {
      padding: 18px 20px 32px;
      min-width: 0;
    }
    .search {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 9px 10px;
      background: var(--panel);
      color: var(--text);
      margin-bottom: 10px;
    }
    .task-list {
      display: grid;
      gap: 6px;
    }
    .task-btn {
      width: 100%;
      text-align: left;
      border: 1px solid transparent;
      background: transparent;
      border-radius: 7px;
      padding: 8px;
      cursor: pointer;
      color: var(--text);
    }
    .task-btn:hover,
    .task-btn.active {
      background: #162a3d;
      border-color: #3f80bd;
    }
    .task-name {
      font-size: 13px;
      font-weight: 750;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: normal;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      line-height: 1.25;
    }
    .task-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      color: var(--muted);
      font-size: 11px;
      margin-top: 3px;
      font-variant-numeric: tabular-nums;
    }
    .meta-label {
      color: var(--muted);
      font-size: 9px;
      font-weight: 800;
      letter-spacing: .06em;
      text-transform: uppercase;
    }
    .tool-badges {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      margin-top: 6px;
      min-height: 18px;
    }
    .tool-chip {
      border: 1px solid #345371;
      background: #102033;
      color: #b7c9de;
      border-radius: 999px;
      padding: 2px 7px;
      font-size: 11px;
      font-weight: 750;
      line-height: 1.25;
      max-width: 100%;
      overflow-wrap: anywhere;
    }
    .tool-chip.born { color: var(--amber); border-color: #927525; background: #2a2310; }
    .tool-chip.called { color: var(--green); border-color: #227a50; background: #0d271d; }
    .tool-chip.failed { color: var(--red); border-color: #8e3c45; background: #2b1418; }
    .task-hero {
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      padding: 16px;
      margin: 18px 0 12px;
      box-shadow: 0 8px 22px var(--shadow);
    }
    .task-title-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
    }
    .task-title {
      font-size: 24px;
      line-height: 1.1;
      font-weight: 850;
      overflow-wrap: anywhere;
    }
    .task-id {
      color: var(--muted);
      margin-top: 4px;
      font-size: 13px;
      overflow-wrap: anywhere;
    }
    .tag-row {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 12px;
    }
    .tag {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 8px;
      color: var(--muted);
      background: var(--panel2);
      font-size: 11px;
      font-weight: 800;
      overflow-wrap: anywhere;
      max-width: 100%;
    }
    .tag.good { color: var(--green); border-color: #227a50; }
    .tag.bad { color: var(--red); border-color: #8e3c45; }
    .tag.warn { color: var(--amber); border-color: #927525; }
    .task-metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(150px, 1fr));
      gap: 10px;
      margin: 10px 0 12px;
    }
    .section {
      border: 1px solid var(--line);
      background: var(--panel3);
      border-radius: 8px;
      padding: 14px;
      margin-top: 14px;
    }
    .section-title {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 10px;
    }
    .split {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .transaction {
      border: 1px solid var(--line);
      background: #0b131d;
      border-radius: 8px;
      padding: 12px;
      min-width: 0;
    }
    .transcript {
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }
    .msg {
      border: 1px solid #28435c;
      background: #0e1a27;
      border-radius: 7px;
      padding: 9px;
      color: #dbe8f6;
      font-size: 12px;
      line-height: 1.45;
      overflow-wrap: anywhere;
      white-space: pre-wrap;
    }
    .msg.tool {
      border-color: #3a6c8d;
      background: #102437;
    }
    details {
      border: 1px solid var(--line);
      background: #0b131d;
      border-radius: 8px;
      padding: 9px 10px;
      margin-top: 8px;
    }
    summary {
      cursor: pointer;
      color: var(--blue);
      font-weight: 750;
      font-size: 12px;
    }
    pre {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      margin: 10px 0 0;
      color: #dce7f3;
      font-size: 12px;
      line-height: 1.45;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 8px;
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }
    th {
      color: var(--muted);
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: .1em;
    }
    @media (max-width: 1100px) {
      header { position: relative; }
      .metrics, .task-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      main { grid-template-columns: 1fr; }
      aside { position: relative; height: auto; top: 0; border-right: 0; border-bottom: 1px solid var(--line); }
      .split { grid-template-columns: 1fr; }
    }
    @media (max-width: 640px) {
      .metrics, .task-metrics { grid-template-columns: 1fr; }
      .header-row, .task-title-row { flex-direction: column; }
    }
  </style>
</head>
<body>
  <script id="sage-data" type="application/json">__SAGE_DATA__</script>
  <header>
    <div class="header-row">
      <div>
        <div class="title-line">
          <h1>Task Compare</h1>
          <span class="env-badge" id="envBadge">Environment</span>
        </div>
        <div class="subtitle" id="subtitle"></div>
        <div class="run-progress" id="runProgress"></div>
      </div>
      <div class="dashboard-switch">Universal SAGE</div>
    </div>
    <section class="metrics" id="metrics"></section>
  </header>
  <main>
    <aside>
      <input class="search" id="search" placeholder="Filter tasks" />
      <div class="task-list" id="taskList"></div>
    </aside>
    <section class="detail-wrap" id="detail"></section>
  </main>
  <script>
    let payload = JSON.parse(document.getElementById("sage-data").textContent);
    let summary = {};
    let registry = {};
    let baseline = {};
    let runMetadata = {};
    let events = [];
    let registryTools = {};
    let baselineResults = [];
    let baselineByTask = new Map();
    let tasks = [];
    let selectedTaskId = "";
    let lastPayloadText = JSON.stringify(payload);

    function applyPayload(nextPayload) {
      payload = nextPayload || {};
      summary = payload.summary || {};
      registry = payload.registry || {};
      baseline = payload.baseline || {};
      runMetadata = payload.run_metadata || {};
      events = summary.events || [];
      registryTools = registry.tools || {};
      baselineResults = baseline.results || [];
      baselineByTask = new Map(baselineResults.map((item) => [item.task_id, item]));
      const taskEvents = events.filter((event) =>
        event.event === "task" || event.event === "task_result"
      );
      const retryEvents = events.filter((event) =>
        event.event === "birth_task_retry" || event.event === "refined_tool_task_retry"
      );
      const taskIds = [];
      for (const item of [...baselineResults, ...taskEvents, ...retryEvents]) {
        if (item.task_id && !taskIds.includes(item.task_id)) taskIds.push(item.task_id);
      }
      tasks = taskIds.map((taskId, index) => {
        const related = events.filter((candidate) => candidate.task_id === taskId);
        const initial = [...related].reverse().find((event) =>
          event.event === "task" || event.event === "task_result"
        );
        const retries = related.filter((event) =>
          event.event === "birth_task_retry" || event.event === "refined_tool_task_retry"
        );
        const successfulRetry = [...retries].reverse().find((event) => event.success === true);
        const retry = successfulRetry || [...retries].reverse()[0] || null;
        const base = baselineByTask.get(taskId) || null;
        const final = retry || initial || {
          event: "task",
          task_id: taskId,
          name: base?.name || taskId,
          success: false,
          score: 0,
          outcome_score: 0,
          visible_helpers: [],
          transcript: [],
          tool_uses: [],
          artifacts: {},
        };
        return {
          ...final,
          display_index: index + 1,
          baseline: base,
          related,
          initial_attempt: initial || null,
          retry_result: retry || null,
        };
      });
      if (!selectedTaskId || !tasks.some((task) => task.task_id === selectedTaskId)) {
        selectedTaskId = tasks[0]?.task_id || "";
      }
    }

    function esc(value) {
      return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[ch]));
    }
    function num(value, fallback = 0) {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : fallback;
    }
    function mean(values) {
      const valid = values.map((value) => num(value, NaN)).filter((value) => Number.isFinite(value));
      return valid.length ? valid.reduce((a, b) => a + b, 0) / valid.length : 0;
    }
    function fmt(value, digits = 3) {
      return num(value).toFixed(digits);
    }
    const ZERO_BASELINE_LIFT_FLOOR = 0.1;
    function pct(value, digits = 1) {
      const parsed = Number(value);
      if (!Number.isFinite(parsed)) return "n/a";
      const sign = parsed > 0 ? "+" : "";
      return `${sign}${(parsed * 100).toFixed(digits)}%`;
    }
    function liftPct(value, approximate = false, digits = 1) {
      const rendered = pct(value, digits);
      return approximate && rendered !== "n/a" ? `~${rendered}` : rendered;
    }
    function deltaText(value, digits = 3) {
      const sign = value >= 0 ? "+" : "";
      return `${sign}${num(value).toFixed(digits)}`;
    }
    function scoreOf(record) {
      if (!record) return 0;
      if (record.score !== undefined) return num(record.score);
      return record.success ? 1 : 0;
    }
    function outcomeOf(record) {
      if (!record) return 0;
      if (record.outcome_score !== undefined && record.outcome_score !== null) {
        return num(record.outcome_score);
      }
      return scoreOf(record);
    }
    function relativeLift(delta, baseline) {
      if (!Number.isFinite(delta) || !Number.isFinite(baseline)) return null;
      if (Math.abs(baseline) > 1e-12) return delta / baseline;
      if (Math.abs(delta) <= 1e-12) return 0;
      return delta / ZERO_BASELINE_LIFT_FLOOR;
    }
    function approximateZeroBaselineLift(delta, baseline) {
      return Number.isFinite(delta) && Number.isFinite(baseline) && Math.abs(baseline) <= 1e-12 && Math.abs(delta) > 1e-12;
    }
    function liftHint(delta, baseline, unit) {
      if (approximateZeroBaselineLift(delta, baseline)) {
        return `approx using 0.100 floor; true baseline is 0; ${deltaText(delta)} ${unit} absolute lift`;
      }
      return `${deltaText(delta)} ${unit} delta`;
    }
    function taskName(task) {
      return task.name || task.baseline?.name || task.task_id || "task";
    }
    function envDisplayName(value) {
      const raw = String(value || "unknown").trim();
      const normalized = raw.toLowerCase().replaceAll("_", "-");
      if (normalized.includes("toolsandbox")) return "ToolSandbox";
      if (normalized.includes("cybergym")) return "CyberGym";
      if (normalized.includes("minigrid")) return "MiniGrid";
      return raw ? raw.replaceAll("-", " ") : "Unknown";
    }
    function getRunStats() {
      const baselineScore = mean(baselineResults.map(scoreOf));
      const sageScore = mean(tasks.map(scoreOf));
      const baselineOutcome = mean(baselineResults.map(outcomeOf));
      const sageOutcome = mean(tasks.map(outcomeOf));
      const requested = num(runMetadata.requested_limit, 0);
      const total = Math.max(
        summary.tasks_seen || 0,
        baseline.tasks_seen || 0,
        tasks.length,
        baselineResults.length,
        requested,
      );
      const paired = Math.min(summary.tasks_seen || tasks.length, baseline.tasks_seen || baselineResults.length || tasks.length);
      return {
        baselineScore,
        sageScore,
        scoreDelta: sageScore - baselineScore,
        scoreLift: relativeLift(sageScore - baselineScore, baselineScore),
        baselineOutcome,
        sageOutcome,
        outcomeDelta: sageOutcome - baselineOutcome,
        outcomeLift: relativeLift(sageOutcome - baselineOutcome, baselineOutcome),
        total,
        paired,
      };
    }
    function metric(label, value, hint, cls = "", clickable = false) {
      return `<article class="metric ${clickable ? "clickable" : ""}" ${clickable ? 'id="toolsMetric"' : ""}>
        <div class="label">${esc(label)}</div>
        <div class="value ${cls}">${esc(value)}</div>
        <div class="hint">${esc(hint)}</div>
      </article>`;
    }
    function toolEventsForTask(task) {
      const names = new Map();
      for (const event of task.related || []) {
        for (const helper of event.visible_helpers || []) names.set(helper, "visible");
        if (event.tool_name) {
          const kind = event.event === "tool_birth"
            ? "born"
            : event.event === "tool_refinement"
              ? "repair"
              : event.event.includes("retry")
                ? "called"
                : event.accepted === false
                  ? "failed"
                  : "visible";
          names.set(event.tool_name, kind);
        }
      }
      for (const use of task.tool_uses || []) {
        if (use.generated_helper && use.tool_name) {
          names.set(use.tool_name, use.success === false ? "failed" : "called");
        }
      }
      return [...names.entries()].map(([tool, kind]) => ({ tool, kind }));
    }
    function renderHeader() {
      const stats = getRunStats();
      const status = runMetadata.status || (runMetadata.benchmark_ready === false ? "probe" : "complete");
      const currentStatus = runMetadata.current_status || {};
      const stageText = currentStatus.stage
        ? `${String(currentStatus.stage).replaceAll("_", " ")}${currentStatus.batch ? ` · batch ${currentStatus.batch}` : ""}${currentStatus.message ? ` · ${currentStatus.message}` : ""}`
        : "";
      const environmentName = envDisplayName(summary.environment);
      document.title = `Task Compare - ${environmentName} - SAGE`;
      document.getElementById("envBadge").textContent = environmentName;
      document.getElementById("subtitle").textContent =
        `${status} · ${summary.model || "model"} · ` +
        `${stats.paired}/${stats.total} matched tasks` +
        (stageText ? ` · ${stageText}` : "");
      document.getElementById("runProgress").innerHTML =
        `<span class="label">Run Progress</span><strong>${stats.paired}/${stats.total}</strong>` +
        `<span>baseline ${baseline.tasks_seen || baselineResults.length}/${stats.total} · ` +
        `SAGE ${summary.tasks_seen || tasks.length}/${stats.total}</span>` +
        (stageText ? `<span class="run-stage">${esc(stageText)}</span>` : "");
      document.getElementById("metrics").innerHTML = [
        metric("Baseline Score", fmt(stats.baselineScore), `${baselineResults.length} paired score tasks`),
        metric("SAGE Score", fmt(stats.sageScore), `${tasks.length} paired score tasks`),
        metric("Score Lift", liftPct(stats.scoreLift, approximateZeroBaselineLift(stats.scoreDelta, stats.baselineScore)), liftHint(stats.scoreDelta, stats.baselineScore, "score"), stats.scoreDelta >= 0 ? "good" : "bad"),
        metric("Baseline Outcome", fmt(stats.baselineOutcome), `${baselineResults.length} paired outcome tasks`),
        metric("SAGE Outcome", fmt(stats.sageOutcome), `${tasks.length} paired outcome tasks`),
        metric("Outcome Lift", liftPct(stats.outcomeLift, approximateZeroBaselineLift(stats.outcomeDelta, stats.baselineOutcome)), liftHint(stats.outcomeDelta, stats.baselineOutcome, "outcome"), stats.outcomeDelta >= 0 ? "good" : "bad"),
        metric(
          "Tools Born / Used",
          `${summary.tools_born || 0} / ${Object.values(registryTools).filter((record) => (record.uses || 0) > 0).length}`,
          `${Object.keys(registryTools).length} registry tools; click for contribution`,
          "warn",
          true,
        ),
      ].join("");
      document.getElementById("toolsMetric")?.addEventListener("click", () => {
        document.getElementById("registrySection")?.scrollIntoView({ behavior: "smooth" });
      });
    }
    function renderTaskList() {
      const query = document.getElementById("search").value.toLowerCase();
      const filtered = tasks.filter((task) => `${task.task_id} ${taskName(task)}`.toLowerCase().includes(query));
      document.getElementById("taskList").innerHTML = filtered.map((task) => {
        const base = task.baseline;
        const scoreDelta = scoreOf(task) - scoreOf(base);
        const outcomeDelta = outcomeOf(task) - outcomeOf(base);
        const toolBadges = toolEventsForTask(task).slice(0, 3).map((item) =>
          `<span class="tool-chip ${esc(item.kind)}">${esc(item.kind)} · ${esc(item.tool.replaceAll("_", " "))}</span>`
        ).join("");
        const more = toolEventsForTask(task).length > 3
          ? `<span class="tool-chip">+${toolEventsForTask(task).length - 3}</span>`
          : "";
        return `<button class="task-btn ${task.task_id === selectedTaskId ? "active" : ""}" data-task-id="${esc(task.task_id)}">
          <div class="task-name">${task.display_index}. ${esc(taskName(task))}</div>
          <div class="task-meta">
            <span><span class="meta-label">Score</span> <span class="${scoreDelta >= 0 ? "good" : "bad"}">${deltaText(scoreDelta)}</span></span>
            <span><span class="meta-label">Outcome</span> <span class="${outcomeDelta >= 0 ? "good" : "bad"}">${deltaText(outcomeDelta)}</span></span>
          </div>
          <div class="tool-badges">${toolBadges}${more}</div>
        </button>`;
      }).join("") || "<div class='subtitle'>No matching tasks.</div>";
      for (const button of document.querySelectorAll(".task-btn")) {
        button.addEventListener("click", () => {
          selectedTaskId = button.dataset.taskId;
          renderTaskList();
          renderDetail();
        });
      }
    }
    function renderDetail() {
      const task = tasks.find((item) => item.task_id === selectedTaskId) || tasks[0];
      if (!task) {
        document.getElementById("detail").innerHTML = "<section class='task-hero'><h2>No task data recorded</h2></section>";
        return;
      }
      const base = task.baseline;
      const scoreDelta = scoreOf(task) - scoreOf(base);
      const outcomeDelta = outcomeOf(task) - outcomeOf(base);
      const toolEvents = toolEventsForTask(task);
      const statusClass = task.success ? "good" : "bad";
      document.getElementById("detail").innerHTML = `
        <section class="task-hero">
          <div class="task-title-row">
            <div>
              <div class="task-title">${esc(taskName(task))}</div>
              <div class="task-id">${esc(task.task_id)}</div>
            </div>
            <span class="tag ${statusClass}">${task.success ? "SAGE success" : "SAGE incomplete"}</span>
          </div>
          <div class="tag-row">
            <span class="tag">environment: ${esc(envDisplayName(summary.environment))}</span>
            <span class="tag">mode: ${esc(runMetadata.execution_mode || "unknown")}</span>
            <span class="tag ${summary.integrity_passed ? "good" : "bad"}">integrity ${summary.integrity_passed ? "passed" : "blocked"}</span>
          </div>
        </section>
        <section class="task-metrics">
          ${metric("Baseline Score", fmt(scoreOf(base)), base ? "baseline task" : "missing baseline")}
          ${metric("SAGE Score", fmt(scoreOf(task)), "SAGE task")}
          ${metric("Score Lift", deltaText(scoreDelta), "task score delta", scoreDelta >= 0 ? "good" : "bad")}
          ${metric("Outcome Lift", deltaText(outcomeDelta), "task outcome delta", outcomeDelta >= 0 ? "good" : "bad")}
        </section>
        <section class="section">
          <div class="section-title"><h2>Generated Tool Events On This Task</h2></div>
          <div class="tool-badges">
            ${toolEvents.length ? toolEvents.map((item) => `<span class="tool-chip ${esc(item.kind)}">${esc(item.kind)} · ${esc(item.tool.replaceAll("_", " "))}</span>`).join("") : "<span class='tool-chip'>no generated helper recorded</span>"}
          </div>
        </section>
        <section class="section">
          <div class="section-title"><h2>Task Evidence And Scores</h2></div>
          <div class="split">
            ${scoreCard("Baseline", base)}
            ${scoreCard("SAGE", task)}
          </div>
        </section>
        <section class="section">
          <div class="section-title"><h2>Full Transaction</h2></div>
          <p class="subtitle">
            Baseline policy: ${esc(baseline.policy || "not recorded")}${baseline.comparison_valid === false ? " · probe baseline, not benchmark control" : ""}.
            ${baseline.comparison_note ? esc(baseline.comparison_note) : ""}
          </p>
          <div class="split">
            ${transactionCard("Baseline", base)}
            ${transactionCard("SAGE", task)}
          </div>
        </section>
        <section class="section">
          <div class="section-title"><h2>Task Event Timeline</h2></div>
          ${task.related.map(renderEvent).join("")}
        </section>
        <section class="section" id="registrySection">
          <div class="section-title"><h2>Generated Tool Registry</h2></div>
          ${registryTable()}
        </section>
      `;
    }
    function scoreCard(label, record) {
      if (!record) {
        return `<div class="transaction"><h3>${esc(label)}</h3><p class="subtitle">No record exported.</p></div>`;
      }
      return `<div class="transaction">
        <h3>${esc(label)}</h3>
        <table>
          <tr><th>Success</th><td>${esc(Boolean(record.success))}</td></tr>
          <tr><th>Score</th><td>${fmt(scoreOf(record))}</td></tr>
          <tr><th>Outcome</th><td>${fmt(outcomeOf(record))}</td></tr>
          ${record.error ? `<tr><th>Error</th><td>${esc(record.error)}</td></tr>` : ""}
        </table>
      </div>`;
    }
    function transactionCard(label, record) {
      if (!record) {
        return `<div class="transaction"><h3>${esc(label)}</h3><p class="subtitle">No transaction exported.</p></div>`;
      }
      const transcript = record.transcript || [];
      const toolUses = record.tool_uses || [];
      const attempts = record.artifacts?.attempts || [];
      const plannedActions = record.artifacts?.planned_actions || [];
      const actionSummary = plannedActions.length
        ? `<div class="msg tool">Actions executed: ${esc(plannedActions.join(" -> "))}<br>steps ${esc(record.artifacts?.steps ?? plannedActions.length)} · reward ${esc(record.artifacts?.reward ?? "not recorded")}</div>`
        : "";
      return `<div class="transaction">
        <h3>${esc(label)}</h3>
        <div class="transcript">
          ${transcript.length ? transcript.map((line, index) => `<div class="msg">${index + 1}. ${esc(line)}</div>`).join("") : "<div class='msg'>No transcript messages exported.</div>"}
          ${actionSummary}
          ${toolUses.map((use, index) => `<div class="msg tool">${index + 1}. TOOL ${esc(use.tool_name)} · success ${esc(use.success)}<br>${esc(compactJson(use.arguments))}<br>${esc(compactJson(use.result))}</div>`).join("")}
          ${attempts.map((attempt, index) => `<div class="msg tool">${index + 1}. ATTEMPT ${esc(attempt.candidate_index ?? index)} · exit ${esc(attempt.exit_code ?? "n/a")} · len ${esc(attempt.poc_length ?? "n/a")}<br>${esc(attempt.output_excerpt || attempt.error || "")}</div>`).join("")}
        </div>
        <details><summary>Raw ${esc(label)} record</summary><pre>${esc(JSON.stringify(record, null, 2))}</pre></details>
      </div>`;
    }
    function compactJson(value) {
      if (value === undefined || value === null || value === "") return "";
      const rendered = JSON.stringify(value);
      return rendered && rendered.length > 260 ? `${rendered.slice(0, 260)}...` : rendered;
    }
    function renderEvent(event) {
      const title = (event.event || "event").replaceAll("_", " ");
      const cls = event.success === true || event.accepted === true ? "good" : event.success === false || event.accepted === false ? "bad" : "warn";
      return `<details>
        <summary><span class="${cls}">${esc(title)}</span> ${esc(event.tool_name || event.gap_key || "")}</summary>
        <pre>${esc(JSON.stringify(event, null, 2))}</pre>
      </details>`;
    }
    function registryTable() {
      const rows = Object.entries(registryTools);
      if (!rows.length) return "<p class='subtitle'>No generated tools retained.</p>";
      return `<table><thead><tr><th>Tool</th><th>Family</th><th>Uses</th><th>Successes</th><th>Decision</th></tr></thead><tbody>
        ${rows.map(([name, record]) => {
          const spec = record.candidate?.spec || {};
          const lifecycle = (summary.lifecycle_decisions || []).find((row) => row.tool_name === name) || {};
          return `<tr>
            <td>${esc(name)}</td>
            <td>${esc(spec.family || "")}</td>
            <td>${esc(record.uses || 0)}</td>
            <td>${esc(record.successes || 0)}</td>
            <td>${esc(lifecycle.decision || "watch")}</td>
          </tr>`;
        }).join("")}
      </tbody></table>`;
    }
    function renderAll() {
      renderHeader();
      renderTaskList();
      renderDetail();
    }
    function captureScrollState() {
      return {
        windowX: window.scrollX,
        windowY: window.scrollY,
        asideY: document.querySelector("aside")?.scrollTop || 0,
      };
    }
    function restoreScrollState(state) {
      requestAnimationFrame(() => {
        const aside = document.querySelector("aside");
        if (aside) aside.scrollTop = state.asideY;
        window.scrollTo(state.windowX, state.windowY);
      });
    }
    async function refreshDashboardData() {
      try {
        const response = await fetch(`task_compare_data.json?ts=${Date.now()}`, { cache: "no-store" });
        if (!response.ok) return;
        const nextPayload = await response.json();
        const nextText = JSON.stringify(nextPayload);
        if (nextText === lastPayloadText) return;
        const scrollState = captureScrollState();
        lastPayloadText = nextText;
        applyPayload(nextPayload);
        renderAll();
        restoreScrollState(scrollState);
      } catch (error) {
        // File URLs and stale static servers can reject fetches. The embedded
        // snapshot still renders, so refresh failure is non-fatal.
      }
    }
    document.getElementById("search").addEventListener("input", renderTaskList);
    applyPayload(payload);
    renderAll();
    setInterval(refreshDashboardData, 2500);
  </script>
</body>
</html>
"""
    return template.replace("__SAGE_DATA__", embedded)


def _legacy_dashboard_html(payload: dict[str, Any]) -> str:
    embedded = html.escape(json.dumps(payload), quote=False)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SAGE Standalone Dashboard</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #08111d;
      --panel: #101c2b;
      --panel-2: #15263a;
      --line: #2d4562;
      --text: #eef5ff;
      --muted: #9fb1c8;
      --cyan: #36c2ff;
      --green: #40e68d;
      --yellow: #ffd45c;
      --red: #ff667a;
      --purple: #a88cff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: radial-gradient(circle at top left, #10233a 0, var(--bg) 42rem);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
    }}
    header {{
      padding: 28px 34px 18px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{ margin: 0; font-size: clamp(30px, 4vw, 54px); letter-spacing: 0; }}
    h2 {{ margin: 0 0 14px; font-size: 22px; }}
    h3 {{ margin: 0; font-size: 18px; }}
    .title-line {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 12px;
    }}
    .env-badge {{
      border: 1px solid var(--cyan);
      background: rgba(54, 194, 255, .12);
      color: #bfeaff;
      border-radius: 999px;
      padding: 7px 12px;
      font-size: 13px;
      font-weight: 900;
      letter-spacing: .05em;
      text-transform: uppercase;
    }}
    .subtitle {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 17px;
      line-height: 1.4;
    }}
    .badge-row {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }}
    .badge {{
      border: 1px solid var(--line);
      background: rgba(21, 38, 58, 0.82);
      border-radius: 999px;
      color: var(--muted);
      padding: 8px 12px;
      font-size: 13px;
      font-weight: 800;
      letter-spacing: .04em;
      text-transform: uppercase;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(260px, 360px) minmax(0, 1fr);
      min-height: calc(100vh - 156px);
    }}
    aside {{
      border-right: 1px solid var(--line);
      padding: 20px;
      position: sticky;
      top: 0;
      height: calc(100vh - 156px);
      overflow: auto;
    }}
    main {{ padding: 20px; min-width: 0; }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(160px, 1fr));
      gap: 14px;
      margin-bottom: 20px;
    }}
    .metric {{
      background: rgba(16, 28, 43, .92);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 18px;
      min-height: 118px;
    }}
    .metric .label {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 900;
      letter-spacing: .12em;
      text-transform: uppercase;
    }}
    .metric .value {{
      margin-top: 12px;
      font-size: 38px;
      line-height: 1;
      font-weight: 900;
    }}
    .metric .note {{ margin-top: 8px; color: var(--muted); font-size: 14px; }}
    .good {{ color: var(--green); }}
    .warn {{ color: var(--yellow); }}
    .bad {{ color: var(--red); }}
    .panel {{
      background: rgba(16, 28, 43, .88);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 20px;
      margin-bottom: 18px;
      box-shadow: 0 18px 52px rgba(0, 0, 0, .26);
    }}
    .panel.warning {{
      border-color: rgba(255, 212, 92, .56);
      background: linear-gradient(135deg, rgba(255, 212, 92, .13), rgba(16, 28, 43, .9) 46%);
    }}
    .task-list {{ display: grid; gap: 10px; }}
    .task-btn {{
      width: 100%;
      border: 1px solid transparent;
      background: transparent;
      color: var(--text);
      border-radius: 11px;
      padding: 12px;
      text-align: left;
      cursor: pointer;
    }}
    .task-btn:hover, .task-btn.active {{
      border-color: var(--cyan);
      background: rgba(54, 194, 255, .12);
    }}
    .task-name {{
      font-weight: 900;
      overflow-wrap: anywhere;
      line-height: 1.22;
    }}
    .task-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      max-width: 100%;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 5px 8px;
      color: var(--muted);
      background: rgba(21, 38, 58, .74);
      font-size: 12px;
      font-weight: 800;
      overflow-wrap: anywhere;
    }}
    .pill.green {{ color: var(--green); border-color: rgba(64, 230, 141, .5); }}
    .pill.yellow {{ color: var(--yellow); border-color: rgba(255, 212, 92, .55); }}
    .pill.red {{ color: var(--red); border-color: rgba(255, 102, 122, .55); }}
    .pill.cyan {{ color: #bfeaff; border-color: rgba(54, 194, 255, .55); }}
    .split {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }}
    .event {{
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 14px;
      margin-top: 10px;
      background: rgba(8, 17, 29, .5);
    }}
    .event-title {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      font-weight: 900;
    }}
    .event pre, .code {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      border: 1px solid var(--line);
      background: #07101b;
      color: #d8e8ff;
      border-radius: 10px;
      padding: 12px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      line-height: 1.45;
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 10px 8px;
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }}
    th {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .1em;
    }}
    details {{ margin-top: 10px; }}
    summary {{ cursor: pointer; color: #bfeaff; font-weight: 800; }}
    @media (max-width: 1000px) {{
      .layout {{ grid-template-columns: 1fr; }}
      aside {{ position: relative; height: auto; border-right: 0; border-bottom: 1px solid var(--line); }}
      .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .split {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 620px) {{
      header {{ padding: 22px; }}
      main, aside {{ padding: 14px; }}
      .metrics {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <script id="sage-data" type="application/json">{embedded}</script>
  <header>
    <div class="title-line">
      <h1>SAGE Standalone Dashboard</h1>
      <span class="env-badge" id="envBadge"></span>
    </div>
    <div class="subtitle" id="subtitle"></div>
    <div class="badge-row" id="badges"></div>
  </header>
  <section class="layout">
    <aside>
      <h2>Tasks</h2>
      <div class="task-list" id="taskList"></div>
    </aside>
    <main>
      <section class="metrics" id="metrics"></section>
      <section class="panel warning" id="runMode"></section>
      <section class="panel" id="taskDetail"></section>
      <section class="split">
        <div class="panel">
          <h2>Generated Helper Lifecycle</h2>
          <div id="lifecycle"></div>
        </div>
        <div class="panel">
          <h2>Registry Tools</h2>
          <div id="registry"></div>
        </div>
      </section>
      <section class="panel">
        <h2>Full Event Timeline</h2>
        <div id="timeline"></div>
      </section>
    </main>
  </section>
  <script>
    const payload = JSON.parse(document.getElementById("sage-data").textContent);
    const summary = payload.summary || {{}};
    const registry = payload.registry || {{}};
    const baseline = payload.baseline || {{}};
    const runMetadata = payload.run_metadata || {{}};
    const events = summary.events || [];
    const tasks = events.filter((event) => event.event === "task" || event.event === "task_result");
    let selectedTaskId = tasks[0]?.task_id || "";

    function pct(n, d) {{
      if (!d) return "0.0%";
      return `${{((n / d) * 100).toFixed(1)}}%`;
    }}
    function statusClass(value) {{
      return value ? "green" : "red";
    }}
    function rate(successes, total) {{
      return total ? successes / total : 0;
    }}
    function pp(value) {{
      const sign = value >= 0 ? "+" : "";
      return `${{sign}}${{(value * 100).toFixed(1)}} pp`;
    }}
    function liftPercent(base, candidate) {{
      if (!base && candidate) return `~${{((candidate / 0.1) * 100).toFixed(1)}}%`;
      if (!base) return "0.0%";
      const value = (candidate - base) / base;
      const sign = value >= 0 ? "+" : "";
      return `${{sign}}${{(value * 100).toFixed(1)}}%`;
    }}
    function esc(value) {{
      return String(value ?? "").replace(/[&<>"']/g, (ch) => ({{
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }}[ch]));
    }}
    function jsonBlock(value) {{
      return `<pre>${{esc(JSON.stringify(value, null, 2))}}</pre>`;
    }}
    function envDisplayName(value) {{
      const raw = String(value || "unknown").trim();
      const normalized = raw.toLowerCase().replaceAll("_", "-");
      if (normalized.includes("toolsandbox")) return "ToolSandbox";
      if (normalized.includes("cybergym")) return "CyberGym";
      if (normalized.includes("minigrid")) return "MiniGrid";
      return raw ? raw.replaceAll("-", " ") : "Unknown";
    }}
    function taskEvents(taskId) {{
      return events.filter((event) => event.task_id === taskId);
    }}
    function helperNamesForTask(taskId) {{
      const names = new Set();
      for (const event of taskEvents(taskId)) {{
        for (const name of event.visible_helpers || []) names.add(name);
        if (event.tool_name) names.add(event.tool_name);
      }}
      return [...names];
    }}
    function taskStatus(taskId) {{
      const related = taskEvents(taskId);
      const first = related.find((event) => event.event === "task" || event.event === "task_result") || {{}};
      const retry = related.find((event) => event.event === "birth_task_retry");
      if (first.success) return {{ label: "success", className: "green" }};
      if (retry?.success) return {{ label: "retry success", className: "green" }};
      if (retry && !retry.success) return {{ label: "retry failed", className: "red" }};
      return {{ label: "needs helper", className: "red" }};
    }}
    function renderHeader() {{
      const environmentName = envDisplayName(summary.environment);
      document.title = `SAGE Standalone Dashboard - ${{environmentName}}`;
      document.getElementById("envBadge").textContent = environmentName;
      document.getElementById("subtitle").textContent =
        `${{summary.model || "unknown model"}} · ` +
        `${{summary.tasks_seen || 0}} tasks · ${{summary.registry_path || "no registry"}}`;
      const badges = [
        `integrity ${{summary.integrity_passed ? "passed" : "blocked"}}`,
        `${{summary.integrity_issues || 0}} integrity issues`,
        `${{summary.gaps_observed || 0}} gaps observed`,
        `${{summary.tools_accepted || 0}} helpers accepted`,
        `baseline ${{baseline.policy || "not recorded"}}`,
        `mode ${{runMetadata.execution_mode || "not recorded"}}`,
      ];
      document.getElementById("badges").innerHTML = badges
        .map((badge) => `<span class="badge">${{esc(badge)}}</span>`)
        .join("");
    }}
    function metric(label, value, note, cls = "") {{
      return `<article class="metric">
        <div class="label">${{esc(label)}}</div>
        <div class="value ${{cls}}">${{esc(value)}}</div>
        <div class="note">${{esc(note)}}</div>
      </article>`;
    }}
    function renderMetrics() {{
      const successRate = pct(summary.tasks_succeeded || 0, summary.tasks_seen || 0);
      const baseRate = rate(baseline.tasks_succeeded || 0, baseline.tasks_seen || 0);
      const sageRate = rate(summary.tasks_succeeded || 0, summary.tasks_seen || 0);
      const delta = sageRate - baseRate;
      const comparisonValid = baseline.comparison_valid !== false;
      document.getElementById("metrics").innerHTML = [
        metric(
          comparisonValid ? "Baseline success" : "Probe baseline",
          `${{baseline.tasks_succeeded || 0}}/${{baseline.tasks_seen || 0}}`,
          comparisonValid ? pct(baseline.tasks_succeeded || 0, baseline.tasks_seen || 0) : "not a benchmark control",
          comparisonValid ? "" : "warn",
        ),
        metric("Tasks succeeded", `${{summary.tasks_succeeded || 0}}/${{summary.tasks_seen || 0}}`, successRate, "good"),
        metric(
          "Absolute lift",
          comparisonValid ? pp(delta) : "n/a",
          comparisonValid ? "SAGE success rate minus baseline" : "probe baseline is not comparable evidence",
          comparisonValid ? (delta >= 0 ? "good" : "bad") : "warn",
        ),
        metric(
          "Relative lift",
          comparisonValid ? liftPercent(baseRate, sageRate) : "n/a",
          comparisonValid
            ? (baseRate ? "versus no-helper baseline" : `approx using 0.100 floor; true baseline is 0; ${{pp(delta)}} absolute lift`)
            : "use a matched benchmark run for lift",
          comparisonValid ? (delta > 0 ? "good" : baseRate ? "" : "warn") : "warn",
        ),
        metric("Gaps observed", summary.gaps_observed || 0, "adapter-normalized gap signals", "warn"),
        metric("Tools born", summary.tools_born || 0, `${{summary.tools_accepted || 0}} accepted · ${{summary.tools_rejected || 0}} rejected`, "warn"),
        metric("Tools reused", summary.tools_reused || 0, "natural calls plus birth-task retry use", "good"),
        metric("Birth retries", summary.birth_task_retries || 0, `${{summary.birth_task_retry_successes || 0}} succeeded`, "cyan"),
        metric("Repairs", summary.repair_attempts || 0, "candidate validation repair attempts", "cyan"),
        metric("Integrity", summary.integrity_passed ? "PASS" : "BLOCK", `${{summary.integrity_issues || 0}} issues`, summary.integrity_passed ? "good" : "bad"),
        metric("Registry", Object.keys(registry.tools || {{}}).length, "stored generated helpers", "warn"),
      ].join("");
    }}
    function renderRunMode() {{
      const ready = Boolean(runMetadata.benchmark_ready);
      const notes = runMetadata.setup_notes || [];
      const available = runMetadata.available_tasks ?? "unknown";
      const comparisonNote = baseline.comparison_note || "";
      document.getElementById("runMode").innerHTML = `
        <div style="display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap">
          <div>
            <h2>Run Mode</h2>
            <div class="subtitle">${{esc(runMetadata.execution_mode || "not recorded")}}</div>
          </div>
          <span class="pill ${{ready ? "green" : "yellow"}}">${{ready ? "benchmark-ready" : "probe / not benchmark evidence"}}</span>
        </div>
        <div class="badge-row">
          <span class="pill">available tasks: ${{esc(available)}}</span>
          <span class="pill">requested: ${{esc(runMetadata.requested_limit ?? "unknown")}}</span>
          <span class="pill">task generator: ${{esc(runMetadata.real_task_generator_used ?? false)}}</span>
          <span class="pill">verifier: ${{esc(runMetadata.real_poc_verifier_used ?? false)}}</span>
          <span class="pill">server: ${{esc(runMetadata.real_submission_server_used ?? false)}}</span>
        </div>
        <p class="subtitle">${{esc(runMetadata.interpretation || "No interpretation recorded.")}}</p>
        ${{comparisonNote ? `<p class="subtitle"><strong>Baseline note:</strong> ${{esc(comparisonNote)}}</p>` : ""}}
        ${{notes.length ? `<ul>${{notes.map((note) => `<li>${{esc(note)}}</li>`).join("")}}</ul>` : ""}}
      `;
    }}
    function renderTaskList() {{
      document.getElementById("taskList").innerHTML = tasks.map((task, index) => {{
        const helpers = helperNamesForTask(task.task_id);
        const status = taskStatus(task.task_id);
        return `<button class="task-btn ${{task.task_id === selectedTaskId ? "active" : ""}}" data-task-id="${{esc(task.task_id)}}">
          <div class="task-name">${{index + 1}}. ${{esc(task.task_id)}}</div>
          <div class="task-meta">
            <span class="pill ${{status.className}}">${{status.label}}</span>
            ${{helpers.slice(0, 2).map((name) => `<span class="pill cyan">${{esc(name)}}</span>`).join("")}}
            ${{helpers.length > 2 ? `<span class="pill">+${{helpers.length - 2}}</span>` : ""}}
          </div>
        </button>`;
      }}).join("") || "<p class='subtitle'>No task events recorded.</p>";
      for (const button of document.querySelectorAll(".task-btn")) {{
        button.addEventListener("click", () => {{
          selectedTaskId = button.dataset.taskId;
          renderTaskList();
          renderTaskDetail();
        }});
      }}
    }}
    function renderTaskDetail() {{
      if (!selectedTaskId) {{
        document.getElementById("taskDetail").innerHTML = "<h2>No task selected</h2>";
        return;
      }}
      const related = taskEvents(selectedTaskId);
      const first = related[0] || {{}};
      const helpers = helperNamesForTask(selectedTaskId);
      const status = taskStatus(selectedTaskId);
      document.getElementById("taskDetail").innerHTML = `
        <div style="display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap">
          <div>
            <h2>${{esc(selectedTaskId)}}</h2>
            <div class="subtitle">Task-level SAGE event view, derived from generic run events.</div>
          </div>
          <span class="pill ${{status.className}}">${{status.label}}</span>
        </div>
        <div class="badge-row">
          ${{helpers.map((name) => `<span class="pill cyan">${{esc(name)}}</span>`).join("") || "<span class='pill'>no helper routed</span>"}}
        </div>
        <div id="taskEvents">
          ${{related.map(renderEvent).join("")}}
        </div>`;
    }}
    function renderEvent(event) {{
      const label = event.event || "event";
      const cls = label === "task" ? (event.success ? "green" : "red") : label.includes("tool") ? "yellow" : "cyan";
      return `<article class="event">
        <div class="event-title">
          <span>${{esc(label.replaceAll("_", " "))}}</span>
          <span class="pill ${{cls}}">${{esc(event.tool_name || event.gap_key || event.task_id || "")}}</span>
        </div>
        <details>
          <summary>Event JSON</summary>
          ${{jsonBlock(event)}}
        </details>
      </article>`;
    }}
    function renderLifecycle() {{
      const rows = summary.lifecycle_decisions || [];
      if (!rows.length) {{
        document.getElementById("lifecycle").innerHTML = "<p class='subtitle'>No helper lifecycle decisions yet.</p>";
        return;
      }}
      document.getElementById("lifecycle").innerHTML = `<table>
        <thead><tr><th>Tool</th><th>Decision</th><th>Use</th><th>Reason</th></tr></thead>
        <tbody>${{rows.map((row) => `<tr>
          <td>${{esc(row.tool_name)}}</td>
          <td><span class="pill ${{row.decision === "scale" || row.decision === "keep" ? "green" : "yellow"}}">${{esc(row.decision)}}</span></td>
          <td>${{esc(row.successes)}}/${{esc(row.uses)}} · ${{pct(row.successes, row.uses)}}</td>
          <td>${{esc(row.reason)}}</td>
        </tr>`).join("")}}</tbody>
      </table>`;
    }}
    function renderRegistry() {{
      const tools = registry.tools || {{}};
      const rows = Object.entries(tools);
      if (!rows.length) {{
        document.getElementById("registry").innerHTML = "<p class='subtitle'>No registry tools stored.</p>";
        return;
      }}
      document.getElementById("registry").innerHTML = rows.map(([name, record]) => {{
        const candidate = record.candidate || {{}};
        const spec = candidate.spec || {{}};
        return `<article class="event">
          <div class="event-title">
            <span>${{esc(name)}}</span>
            <span class="pill green">${{esc(spec.family || "helper")}}</span>
          </div>
          <p class="subtitle">${{esc(spec.description || "")}}</p>
          <div class="badge-row">
            <span class="pill">${{esc(record.birth_environment || "")}}</span>
            <span class="pill">${{esc(record.birth_gap_key || "")}}</span>
            <span class="pill">${{esc(record.uses || 0)}} uses</span>
            <span class="pill">${{esc(record.code_hash || "").slice(0, 12)}}</span>
          </div>
          <details><summary>Code</summary><pre>${{esc(candidate.code || "")}}</pre></details>
        </article>`;
      }}).join("");
    }}
    function renderTimeline() {{
      document.getElementById("timeline").innerHTML = events.map(renderEvent).join("") ||
        "<p class='subtitle'>No events recorded.</p>";
    }}
    renderHeader();
    renderMetrics();
    renderRunMode();
    renderTaskList();
    renderTaskDetail();
    renderLifecycle();
    renderRegistry();
    renderTimeline();
  </script>
</body>
</html>
"""
