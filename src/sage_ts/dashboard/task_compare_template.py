"""Task-specific comparison dashboard template."""

from __future__ import annotations

TASK_COMPARE_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Task Compare - SAGE</title>
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
      --ink: #dce7f3;
      --shadow: rgba(0, 0, 0, .35);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    button, input, select {
      font: inherit;
    }
    header {
      border-bottom: 1px solid var(--line);
      background: var(--panel);
      padding: 18px 22px 14px;
      position: sticky;
      top: 0;
      z-index: 5;
    }
    h1 {
      margin: 0;
      font-size: 22px;
      letter-spacing: 0;
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
    }
    .subtitle {
      color: var(--muted);
      font-size: 13px;
      margin-top: 5px;
      overflow-wrap: anywhere;
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(3, minmax(180px, 1fr));
      gap: 10px;
      margin-top: 10px;
      max-width: 960px;
    }
    .run-progress {
      display: inline-flex;
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
      font-size: 10px;
    }
    .run-progress strong {
      color: var(--text);
      font-size: 15px;
      font-variant-numeric: tabular-nums;
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
      grid-template-columns: minmax(220px, 300px) minmax(0, 1fr);
      min-height: calc(100vh - 150px);
    }
    aside {
      border-right: 1px solid var(--line);
      background: #0d151f;
      padding: 14px;
      position: sticky;
      top: 139px;
      height: calc(100vh - 139px);
      overflow: auto;
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
      white-space: nowrap;
    }
    .task-meta {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
      margin-top: 3px;
      font-variant-numeric: tabular-nums;
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
      background: #102337;
      color: var(--blue);
      border-radius: 999px;
      padding: 2px 6px;
      font-size: 10px;
      font-weight: 800;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .tool-chip.born {
      border-color: #8b6b20;
      background: #31250d;
      color: var(--amber);
    }
    .tool-chip.called {
      border-color: #21794e;
      background: #0d2d20;
      color: var(--green);
    }
    .tool-chip.visible {
      color: #b7c8dc;
    }
    .tool-chip.observed {
      color: var(--muted);
    }
    .detail {
      padding: 18px 22px 28px;
      overflow: hidden;
    }
    .section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 14px;
      box-shadow: 0 8px 22px var(--shadow);
    }
    .task-title {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: start;
    }
    .task-title h2 {
      margin: 0;
      font-size: 26px;
      letter-spacing: 0;
      overflow-wrap: anywhere;
    }
    .pill-row {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 10px;
    }
    .pill {
      border: 1px solid var(--line);
      background: var(--panel2);
      border-radius: 999px;
      padding: 4px 8px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }
    .compare-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(130px, 1fr));
      gap: 10px;
      margin-top: 14px;
    }
    .mini {
      border: 1px solid var(--line);
      background: var(--panel3);
      border-radius: 8px;
      padding: 11px;
      min-height: 74px;
    }
    .mini .value { font-size: 21px; }
    .split {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .transaction-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; }
    .transaction-head h3 { margin: 0; }
    .transaction-select { border: 1px solid var(--line); border-radius: 999px; background: var(--panel2); color: var(--blue); padding: 7px 10px; font-size: 12px; font-weight: 800; min-width: 150px; }
    .box {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel3);
      padding: 12px;
      min-height: 110px;
    }
    .box h3 {
      margin: 0 0 9px;
      font-size: 14px;
    }
    .small {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      font-size: 12px;
      line-height: 1.45;
      color: var(--ink);
    }
    .transcript { max-height: 640px; overflow: auto; display: grid; gap: 8px; padding-right: 4px; }
    .msg { display: flex; }
    .msg.user, .msg.system, .msg.tool { justify-content: flex-start; }
    .msg.assistant { justify-content: flex-end; }
    .bubble { max-width: min(780px, 92%); border: 1px solid var(--line); border-radius: 13px; padding: 8px 12px; background: rgba(15,23,34,.9); }
    .msg.assistant .bubble { background: rgba(24,64,103,.78); border-color: rgba(119,189,255,.3); }
    .msg.tool .bubble { background: rgba(15,23,34,.9); border-color: var(--line); }
    .msg.generated-tool .bubble { background: rgba(12,49,42,.88); border-color: rgba(65,217,150,.38); box-shadow: 0 0 0 2px rgba(65,217,150,.25); }
    .msg-lbl { color: var(--muted); font-size: 10px; font-weight: 800; margin-bottom: 4px; text-transform: uppercase; letter-spacing: .08em; }
    .tbadge { display: inline-block; margin: 0 5px 6px 0; border: 1px solid rgba(65,217,150,.45); border-radius: 999px; padding: 2px 7px; color: var(--green); font-size: 11px; font-weight: 800; }
    .empty-transcript { color: var(--muted); font-size: 13px; line-height: 1.5; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      text-align: left;
      border-bottom: 1px solid var(--line);
      padding: 9px 8px;
      vertical-align: top;
    }
    th {
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .08em;
    }
    .drawer {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, .62);
      z-index: 20;
      display: none;
    }
    .drawer.open {
      display: block;
    }
    .drawer-panel {
      margin-left: auto;
      width: min(900px, 94vw);
      height: 100%;
      background: var(--panel);
      border-left: 1px solid var(--line);
      padding: 18px;
      overflow: auto;
    }
    .drawer-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 12px;
    }
    .close {
      border: 1px solid var(--line);
      background: var(--panel2);
      border-radius: 8px;
      padding: 8px 10px;
      cursor: pointer;
    }
    a {
      color: var(--blue);
      text-decoration: none;
    }
    @media (max-width: 1100px) {
      .metrics { grid-template-columns: repeat(3, minmax(140px, 1fr)); }
      main { grid-template-columns: 1fr; }
      aside {
        position: relative;
        top: auto;
        height: auto;
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }
      .task-list {
        grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      }
    }
    @media (max-width: 760px) {
      .metrics, .compare-grid, .split, .transaction-grid { grid-template-columns: 1fr; }
      .detail { padding: 14px; }
      header { position: relative; }
      .header-row { flex-direction: column; }
    }
  </style>
</head>
<body>
  <header>
    <div class="header-row">
      <div>
        <h1>Task Compare</h1>
        <div class="subtitle" id="subtitle">Loading run data...</div>
      </div>
      <select id="dashboardSwitch" class="dashboard-switch" aria-label="Switch dashboard">
        <option value="index.html">Overview</option>
        <option value="task_focus.html">Task Focus</option>
        <option value="task_compare.html">Task Compare</option>
      </select>
    </div>
    <div class="run-progress" id="runProgress"></div>
    <div class="metrics" id="metrics"></div>
    <div class="metrics tool-metrics" id="toolMetrics"></div>
  </header>
  <main>
    <aside>
      <input id="search" class="search" placeholder="Filter tasks" />
      <div class="task-list" id="taskList"></div>
    </aside>
    <section class="detail" id="detail"></section>
  </main>
  <div class="drawer" id="toolDrawer" aria-hidden="true">
    <div class="drawer-panel">
      <div class="drawer-head">
        <div>
          <h2 style="margin:0">Generated And Retained Tools</h2>
          <div class="small" id="toolDrawerSub"></div>
        </div>
        <button class="close" id="closeTools">Close</button>
      </div>
      <div id="toolTable"></div>
    </div>
  </div>
  <script>
    const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const finite = (v) => v !== null && v !== undefined && v !== "" && Number.isFinite(Number(v));
    const pct = (v) => finite(v) ? (Number(v) * 100).toFixed(1) + "%" : "-";
    const signedPct = (v) => finite(v) ? (Number(v) >= 0 ? "+" : "") + (Number(v) * 100).toFixed(1) + "%" : "-";
    const num = (v, d = 3) => finite(v) ? Number(v).toFixed(d) : "-";
    const signedNum = (v, d = 3) => finite(v) ? (Number(v) >= 0 ? "+" : "") + Number(v).toFixed(d) : "-";
    const relLift = (delta, baseline) => finite(delta) && finite(baseline) && Number(baseline) !== 0 ? Number(delta) / Number(baseline) : null;
    const cls = (v) => Number(v || 0) > 0 ? "good" : Number(v || 0) < 0 ? "bad" : "";
    const outcome = (row) => row?.outcome_similarity ?? row?.outcome_milestone_similarity ?? null;
    function initDashboardSwitch() {
      const select = document.getElementById("dashboardSwitch");
      if (!select) return;
      const current = location.pathname.split("/").pop() || "index.html";
      select.value = current;
      select.addEventListener("change", () => {
        if (select.value && select.value !== current) location.href = select.value;
      });
    }
    const completeStatus = (row) => row?.status === "complete" || row?.status === "cached" || row?.status === "done";
    const toolEvents = (pair) => pair?.candidate?.generated_tool_events || pair?.candidate?.generated_tools?.map((tool) => ({kind: "called", tool})) || [];
    const toolEventLabel = (event) => `${event.kind || "tool"}: ${event.tool || ""}`;
    const compactToolName = (name) => String(name || "").replace(/^.*:/, "").replace(/_/g, " ");
    const mean = (values) => {
      const nums = values.filter(finite).map(Number);
      return nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : null;
    };
    const pairedMetricRows = () => pairs.filter((pair) => completeStatus(pair.control) && completeStatus(pair.candidate));
    function pairedMetrics(summary) {
      const paired = pairedMetricRows();
      const scoreRows = paired.filter((pair) => finite(pair.control?.similarity) && finite(pair.candidate?.similarity));
      const outcomeRows = paired.filter((pair) => finite(outcome(pair.control)) && finite(outcome(pair.candidate)));
      const baselineScore = mean(scoreRows.map((pair) => pair.control.similarity));
      const sageScore = mean(scoreRows.map((pair) => pair.candidate.similarity));
      const baselineOutcome = mean(outcomeRows.map((pair) => outcome(pair.control)));
      const sageOutcome = mean(outcomeRows.map((pair) => outcome(pair.candidate)));
      return {
        pairedCount: paired.length,
        scoreCount: scoreRows.length,
        outcomeCount: outcomeRows.length,
        baselineScore: baselineScore ?? summary.balanced_control_mean_similarity ?? null,
        sageScore: sageScore ?? summary.balanced_candidate_mean_similarity ?? null,
        baselineOutcome: baselineOutcome ?? summary.balanced_control_mean_outcome_similarity ?? null,
        sageOutcome: sageOutcome ?? summary.balanced_candidate_mean_outcome_similarity ?? null,
      };
    }
    let payload = null;
    let pairs = [];
    let selected = 0;
    let transactionArm = "candidate";
    let handlersBound = false;

    function metric(label, value, hint, className = "", clickable = false) {
      return `<div class="metric ${clickable ? "clickable" : ""}" ${clickable ? 'id="toolsMetric" role="button" tabindex="0"' : ""}>
        <div class="label">${esc(label)}</div>
        <div class="value ${className}">${esc(value)}</div>
        <div class="hint">${esc(hint)}</div>
      </div>`;
    }

    function maybeValue(value) {
      return value === null || value === undefined ? "n/a" : value;
    }

    function gainLossText(gains, regressions) {
      if (gains === null && regressions === null) return "n/a";
      if (gains === undefined && regressions === undefined) return "n/a";
      return `${gains ?? 0} gains / ${regressions ?? 0} regressions`;
    }

    function plannedTaskCount(summary) {
      const selected = Math.max(
        Number(summary.scenario_count || 0),
        Number(payload?.arm_progress?.control?.scenario_count || 0),
        Number(payload?.arm_progress?.candidate?.scenario_count || 0),
        Number(pairs.length || 0),
      );
      const modeMatch = String(payload?.mode || "").match(/_(\d+)$/);
      const modeCap = modeMatch ? Number(modeMatch[1]) : 0;
      return Math.max(selected, modeCap);
    }

    function renderMetrics() {
      const s = payload.summary || {};
      const tools = payload.tool_summary || {};
      const selectedTasks = Math.max(Number(s.scenario_count || 0), Number(pairs.length || 0));
      const totalTasks = plannedTaskCount(s);
      const baselineDone = s.control_completed ?? 0;
      const sageDone = s.candidate_completed ?? s.current_completed ?? 0;
      const matched = Math.min(baselineDone, sageDone);
      const paired = pairedMetrics(s);
      const baselineScore = paired.baselineScore;
      const sageScore = paired.sageScore;
      const scoreDelta = finite(baselineScore) && finite(sageScore) ? Number(sageScore) - Number(baselineScore) : null;
      const scoreLift = relLift(scoreDelta, baselineScore);
      const baselineOutcome = paired.baselineOutcome;
      const sageOutcome = paired.sageOutcome;
      const outcomeDelta = finite(baselineOutcome) && finite(sageOutcome) ? Number(sageOutcome) - Number(baselineOutcome) : null;
      const outcomeLift = relLift(outcomeDelta, baselineOutcome);
      const used = tools.called_tool_count ?? 0;
      const total = tools.registry_tool_count ?? tools.tool_count ?? 0;
      const selectedNote = selectedTasks && selectedTasks !== totalTasks ? ` · ${selectedTasks} selected/matched` : "";
      document.getElementById("runProgress").innerHTML = `<span class="label">Run Progress</span><strong>${matched || 0}/${totalTasks || 0}</strong><span>baseline ${baselineDone}/${totalTasks || 0} · SAGE ${sageDone}/${totalTasks || 0}${selectedNote}</span>`;
      document.getElementById("metrics").innerHTML = [
        metric("Baseline Score", num(baselineScore), `${paired.scoreCount || matched || 0} paired score tasks`),
        metric("SAGE Score", num(sageScore), `${paired.scoreCount || matched || 0} paired score tasks`),
        metric("Score Lift", signedPct(scoreLift), `${signedNum(scoreDelta)} score delta`, cls(scoreDelta)),
        metric("Baseline Outcome", num(baselineOutcome), `${paired.outcomeCount || 0} paired outcome tasks`),
        metric("SAGE Outcome", num(sageOutcome), `${paired.outcomeCount || 0} paired outcome tasks`),
        metric("Outcome Lift", signedPct(outcomeLift), `${signedNum(outcomeDelta)} outcome delta`, cls(outcomeDelta)),
      ].join("");
      document.getElementById("toolMetrics").innerHTML = metric("Tools Born / Used", `${tools.generated_tool_birth_count || 0} / ${used}`, `${total} registry tools; click for contribution`, "warn", true);
      const cell = document.getElementById("toolsMetric");
      cell?.addEventListener("click", openTools);
      cell?.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") openTools();
      });
    }

    function pairDelta(pair) {
      const c = pair.control || {};
      const s = pair.candidate || {};
      const scoreDelta = finite(c.similarity) && finite(s.similarity) ? Number(s.similarity) - Number(c.similarity) : null;
      const outcomeDelta = finite(outcome(c)) && finite(outcome(s)) ? Number(outcome(s)) - Number(outcome(c)) : null;
      return {scoreDelta, outcomeDelta};
    }

    function renderList() {
      const query = document.getElementById("search").value.trim().toLowerCase();
      const filtered = pairs
        .map((pair, index) => ({pair, index}))
        .filter(({pair}) => !query || String(pair.short_name || pair.scenario).toLowerCase().includes(query) || String(pair.scenario).toLowerCase().includes(query));
      document.getElementById("taskList").innerHTML = filtered.map(({pair, index}) => {
        const d = pairDelta(pair);
        const events = toolEvents(pair);
        const chips = events.slice(0, 3).map((event) => `<span class="tool-chip ${esc(event.kind)}" title="${esc(toolEventLabel(event))}">${esc(event.kind || "tool")} · ${esc(compactToolName(event.tool))}</span>`).join("");
        const overflow = events.length > 3 ? `<span class="tool-chip" title="${esc(events.slice(3).map(toolEventLabel).join("\\n"))}">+${events.length - 3}</span>` : "";
        return `<button class="task-btn ${index === selected ? "active" : ""}" data-index="${index}">
          <div class="task-name">${esc(pair.display_index || index + 1)}. ${esc(pair.short_name || pair.scenario)}</div>
          <div class="task-meta"><span class="${cls(d.scoreDelta)}">${signedNum(d.scoreDelta)}</span><span class="${cls(d.outcomeDelta)}">${signedNum(d.outcomeDelta)}</span></div>
          ${events.length ? `<div class="tool-badges">${chips}${overflow}</div>` : ""}
        </button>`;
      }).join("");
      document.querySelectorAll(".task-btn").forEach((btn) => btn.addEventListener("click", () => {
        selected = Number(btn.dataset.index);
        renderList();
        renderDetail();
      }));
    }

    function summarizeChecks(row) {
      const checks = row?.evaluation?.checks || row?.outcome_checks || [];
      if (!checks.length) return "<div class='small'>No outcome checks exported for this arm.</div>";
      return `<table><thead><tr><th>Check</th><th>Kind</th><th>Included</th><th>Score</th></tr></thead><tbody>${checks.map((check, idx) => `
        <tr><td>${idx + 1}</td><td>${esc(check.kind || "-")}</td><td>${esc(check.included)}</td><td>${num(check.score)}</td></tr>`).join("")}</tbody></table>`;
    }

    function transcriptFallback(row) {
      if (row?.control_cache_source === "cached") {
        const ids = row?.control_cache?.record_ids || [];
        return `Cached control row has no local transcript export in this run.${ids.length ? "\\nCache record IDs: " + ids.join(", ") : ""}`;
      }
      const checks = row?.outcome_checks || [];
      const observed = checks.flatMap((check) => check.observed_messages || []).slice(-3);
      return observed.join("\\n\\n") || "No transcript messages exported.";
    }

    function messageRole(message) {
      const role = String(message.role || "").toLowerCase();
      const label = String(message.label || message.sender || "").toLowerCase();
      const raw = `${role} ${label}`;
      if (role === "assistant" || raw.includes("assistant")) return "assistant";
      if (role === "user" || raw.includes("user")) return "user";
      if (role === "tool" || raw.includes("tool:")) return "tool";
      return "system";
    }

    function messageTools(message) {
      const tools = [...(message.generated_tools || [])];
      if (!tools.length && message.uses_generated_tool) {
        const label = String(message.label || "");
        const content = String(message.content || message.message || "");
        const labelMatch = label.match(/tool(?: call)?:\s*([A-Za-z0-9_]+)/i);
        const contentMatch = content.match(/^\s*([A-Za-z0-9_]+)\s*\(/);
        const tool = labelMatch?.[1] || contentMatch?.[1] || "";
        if (tool) tools.push(tool);
      }
      return tools;
    }

    function messageHtml(message) {
      const role = messageRole(message);
      const tools = messageTools(message);
      const label = message.label || message.sender || message.role || role;
      const content = message.content || message.message || "[empty]";
      return `<div class="msg ${role}${tools.length ? " generated-tool" : ""}">
        <div class="bubble">
          <div class="msg-lbl">${esc(`#${Number(message.index ?? 0) + 1} · ${label}`)}</div>
          ${tools.map((tool) => `<span class="tbadge">⚡ ${esc(tool)}</span>`).join("")}
          <pre>${esc(content)}</pre>
        </div>
      </div>`;
    }

    function transcriptHtml(row) {
      const messages = row?.messages || [];
      if (!messages.length) return `<div class="empty-transcript">${esc(transcriptFallback(row))}</div>`;
      return `<div class="transcript">${messages.map(messageHtml).join("")}</div>`;
    }

    function toolEventHtml(pair) {
      const events = toolEvents(pair);
      if (!events.length) return "<span class='small'>No generated-tool birth, visibility, or call event recorded for this task.</span>";
      return events.map((event) => `<span class="tool-chip ${esc(event.kind)}" title="${esc(toolEventLabel(event))}">${esc(event.kind || "tool")} · ${esc(event.tool || "")}</span>`).join("");
    }

    function transcriptSource(row) {
      const source = row?.transcript_source;
      if (!source) return "";
      const bits = [source.source, source.record_id ? `record ${source.record_id}` : "", source.transcript_path || ""].filter(Boolean);
      return bits.length ? `<div class="small" style="margin-bottom:8px">${esc(bits.join(" · "))}</div>` : "";
    }

    function transactionPanelHtml(control, candidate) {
      const row = transactionArm === "control" ? control : candidate;
      const title = transactionArm === "control" ? "Baseline Transaction" : "SAGE Transaction";
      return `<div class="section">
        <div class="transaction-head">
          <h3>Full Transaction</h3>
          <select id="transactionArm" class="transaction-select" aria-label="Transaction view">
            <option value="control" ${transactionArm === "control" ? "selected" : ""}>Baseline</option>
            <option value="candidate" ${transactionArm === "candidate" ? "selected" : ""}>SAGE</option>
          </select>
        </div>
        <div class="box">
          <h3>${title}</h3>
          ${transcriptSource(row)}
          ${transcriptHtml(row)}
        </div>
      </div>`;
    }

    function bindTransactionArm() {
      const select = document.getElementById("transactionArm");
      if (!select) return;
      select.addEventListener("change", () => {
        transactionArm = select.value;
        renderDetail();
      });
    }

    function renderDetail() {
      const pair = pairs[selected];
      if (!pair) {
        document.getElementById("detail").innerHTML = "<div class='section'>No task pairs exported.</div>";
        return;
      }
      const control = pair.control || {};
      const candidate = pair.candidate || {};
      const d = pairDelta(pair);
      const cats = [...new Set([...(control.categories || []), ...(candidate.categories || [])])];
      document.getElementById("detail").innerHTML = `
        <div class="section">
          <div class="task-title">
            <div>
              <h2>${esc(pair.short_name || pair.scenario)}</h2>
              <div class="small">${esc(pair.scenario)}</div>
            </div>
            <div class="small">Task ${esc(pair.display_index || selected + 1)}</div>
          </div>
          <div class="pill-row">${cats.map((cat) => `<span class="pill">${esc(cat)}</span>`).join("")}</div>
          <div class="compare-grid">
            <div class="mini"><div class="label">Baseline Score</div><div class="value">${pct(control.similarity)}</div></div>
            <div class="mini"><div class="label">SAGE Score</div><div class="value">${pct(candidate.similarity)}</div></div>
            <div class="mini"><div class="label">Score Delta</div><div class="value ${cls(d.scoreDelta)}">${signedNum(d.scoreDelta)}</div><div class="hint">${signedPct(relLift(d.scoreDelta, control.similarity))} lift</div></div>
            <div class="mini"><div class="label">Score Lift</div><div class="value ${cls(d.scoreDelta)}">${signedPct(relLift(d.scoreDelta, control.similarity))}</div><div class="hint">${signedNum(d.scoreDelta)} score delta</div></div>
            <div class="mini"><div class="label">Outcome Lift</div><div class="value ${cls(d.outcomeDelta)}">${signedPct(relLift(d.outcomeDelta, outcome(control)))}</div><div class="hint">${num(outcome(control))} -> ${num(outcome(candidate))}; delta ${signedNum(d.outcomeDelta)}</div></div>
            <div class="mini"><div class="label">Baseline Turns</div><div class="value">${esc(control.turn_count ?? "-")}</div></div>
            <div class="mini"><div class="label">SAGE Turns</div><div class="value">${esc(candidate.turn_count ?? "-")}</div></div>
            <div class="mini"><div class="label">Control Cache</div><div class="value">${esc(control.control_cache_source || "-")}</div></div>
            <div class="mini"><div class="label">SAGE Tool Events</div><div class="value">${esc(toolEvents(pair).length)}</div></div>
          </div>
        </div>
        <div class="section">
          <h3 style="margin-top:0">Generated Tool Events On This Task</h3>
          <div class="pill-row">${toolEventHtml(pair)}</div>
        </div>
        <div class="section split">
          <div class="box">
            <h3>Baseline Outcome Checks</h3>
            ${summarizeChecks(control)}
          </div>
          <div class="box">
            <h3>SAGE Outcome Checks</h3>
            ${summarizeChecks(candidate)}
          </div>
        </div>
        ${transactionPanelHtml(control, candidate)}
      `;
      bindTransactionArm();
    }

    function openTools() {
      const tools = payload.tool_summary || {};
      const rows = tools.tools || [];
      const visibilityKnown = rows.some((tool) => tool.visible_count !== null && tool.visible_count !== undefined);
      const contributionKnown = rows.some((tool) => tool.called_subset_mean_outcome_delta !== null && tool.called_subset_mean_outcome_delta !== undefined);
      document.getElementById("toolDrawerSub").textContent = `${rows.length} tools; ${tools.called_tool_count || 0} called naturally in this run.${visibilityKnown ? "" : " Visibility counts were not exported for this run."}${contributionKnown ? "" : " Contribution columns are unavailable from reuse-event fallback data."}`;
      document.getElementById("toolTable").innerHTML = `<table>
        <thead><tr><th>Tool</th><th>Origin</th><th>Visible</th><th>Called</th><th>VNC</th><th>Outcome Contribution</th><th>Score Contribution</th><th>Safety</th></tr></thead>
        <tbody>${rows.map((tool) => `<tr>
          <td><strong>${esc(tool.name)}</strong><div class="small">${esc(tool.decision || "")}</div></td>
          <td>${esc(tool.origin || "-")}</td>
          <td>${esc(maybeValue(tool.visible_count))}</td>
          <td>${esc(tool.called_count ?? 0)}</td>
          <td>${esc(maybeValue(tool.visible_not_called_count))}</td>
          <td class="${cls(tool.called_subset_mean_outcome_delta)}">${signedNum(tool.called_subset_mean_outcome_delta)}<div class="small">${esc(gainLossText(tool.outcome_gains, tool.outcome_regressions))}</div></td>
          <td class="${cls(tool.called_subset_mean_canonical_delta)}">${signedNum(tool.called_subset_mean_canonical_delta)}</td>
          <td>${esc(tool.side_effect_incident_count ?? 0)} side effects<br><span class="small">${esc(tool.runtime_incident_count ?? 0)} runtime incidents</span></td>
        </tr>`).join("")}</tbody>
      </table>`;
      document.getElementById("toolDrawer").classList.add("open");
      document.getElementById("toolDrawer").setAttribute("aria-hidden", "false");
    }

    function closeTools() {
      document.getElementById("toolDrawer").classList.remove("open");
      document.getElementById("toolDrawer").setAttribute("aria-hidden", "true");
    }

    async function refresh() {
      const response = await fetch(`task_compare_data.json?ts=${Date.now()}`, {cache: "no-store"});
      payload = await response.json();
      pairs = payload.pairs || [];
      const s = payload.summary || {};
      const baselineDone = s.control_completed ?? 0;
      const sageDone = s.candidate_completed ?? s.current_completed ?? 0;
      const matched = Math.min(baselineDone, sageDone);
      const totalTasks = plannedTaskCount(s);
      const selectedTasks = Math.max(Number(s.scenario_count || 0), Number(pairs.length || 0));
      const matchedText = selectedTasks && selectedTasks !== totalTasks ? `${matched || 0}/${totalTasks || 0} cap · ${selectedTasks} matched tasks` : `${matched || 0}/${totalTasks || 0} matched tasks`;
      document.getElementById("subtitle").textContent = `${payload.mode || "run"} · ${payload.status || "unknown"} · ${payload.agent || ""} · ${matchedText} · refreshed ${new Date().toLocaleTimeString()}`;
      if (selected >= pairs.length) selected = Math.max(0, pairs.length - 1);
      renderMetrics();
      renderList();
      renderDetail();
    }

    async function load() {
      await refresh();
      if (!handlersBound) {
        handlersBound = true;
        initDashboardSwitch();
        document.getElementById("search").addEventListener("input", renderList);
        document.getElementById("closeTools").addEventListener("click", closeTools);
        document.getElementById("toolDrawer").addEventListener("click", (event) => {
          if (event.target.id === "toolDrawer") closeTools();
        });
        window.addEventListener("keydown", (event) => {
          if (event.key === "Escape") closeTools();
        });
        window.setInterval(() => {
          refresh().catch((error) => console.error(error));
        }, 5000);
      }
    }

    load().catch((error) => {
      document.getElementById("detail").innerHTML = `<div class="section"><strong>Dashboard load failed.</strong><pre>${esc(error.stack || error.message || error)}</pre></div>`;
      console.error(error);
    });
  </script>
</body>
</html>
"""
