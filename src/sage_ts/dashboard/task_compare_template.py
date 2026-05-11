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
    button, input {
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
    .subtitle {
      color: var(--muted);
      font-size: 13px;
      margin-top: 5px;
      overflow-wrap: anywhere;
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(6, minmax(140px, 1fr));
      gap: 10px;
      margin-top: 14px;
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
      .metrics, .compare-grid, .split { grid-template-columns: 1fr; }
      .detail { padding: 14px; }
      header { position: relative; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Task Compare</h1>
    <div class="subtitle" id="subtitle">Loading run data...</div>
    <div class="metrics" id="metrics"></div>
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
    const completeStatus = (row) => row?.status === "complete" || row?.status === "cached" || row?.status === "done";
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
    let handlersBound = false;

    function metric(label, value, hint, className = "", clickable = false) {
      return `<div class="metric ${clickable ? "clickable" : ""}" ${clickable ? 'id="toolsMetric" role="button" tabindex="0"' : ""}>
        <div class="label">${esc(label)}</div>
        <div class="value ${className}">${esc(value)}</div>
        <div class="hint">${esc(hint)}</div>
      </div>`;
    }

    function renderMetrics() {
      const s = payload.summary || {};
      const tools = payload.tool_summary || {};
      const totalTasks = s.scenario_count ?? pairs.length ?? 0;
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
      document.getElementById("metrics").innerHTML = [
        metric("Run Progress", `${matched || 0}/${totalTasks || 0}`, `paired complete; baseline ${baselineDone}/${totalTasks || 0} · SAGE ${sageDone}/${totalTasks || 0}`),
        metric("Baseline Score", num(baselineScore), `${paired.scoreCount || matched || 0} paired score tasks`),
        metric("SAGE Score", num(sageScore), `${paired.scoreCount || matched || 0} paired score tasks`),
        metric("Score Delta", signedNum(scoreDelta), "absolute score change", cls(scoreDelta)),
        metric("Score Lift", signedPct(scoreLift), `${signedNum(scoreDelta)} score delta`, cls(scoreDelta)),
        metric("Baseline Outcome", num(baselineOutcome), `${paired.outcomeCount || 0} paired outcome tasks`),
        metric("SAGE Outcome", num(sageOutcome), `${paired.outcomeCount || 0} paired outcome tasks`),
        metric("Outcome Lift", signedPct(outcomeLift), `${signedNum(outcomeDelta)} outcome delta`, cls(outcomeDelta)),
        metric("Tools Born / Used", `${tools.generated_tool_birth_count || 0} / ${used}`, `${total} registry tools; click for contribution`, "warn", true),
      ].join("");
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
        return `<button class="task-btn ${index === selected ? "active" : ""}" data-index="${index}">
          <div class="task-name">${esc(pair.display_index || index + 1)}. ${esc(pair.short_name || pair.scenario)}</div>
          <div class="task-meta"><span class="${cls(d.scoreDelta)}">${signedNum(d.scoreDelta)}</span><span class="${cls(d.outcomeDelta)}">${signedNum(d.outcomeDelta)}</span></div>
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

    function finalMessages(row) {
      const messages = row?.messages || [];
      const selectedMessages = messages.slice(-4).map((message) => {
        const sender = message.sender || message.role || "-";
        const content = message.content || message.message || "";
        return `${sender}: ${content}`;
      });
      if (!selectedMessages.length) {
        const checks = row?.outcome_checks || [];
        const observed = checks.flatMap((check) => check.observed_messages || []).slice(-3);
        if (observed.length) return observed.join("\n\n");
      }
      return selectedMessages.join("\n\n") || "No transcript messages exported.";
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
            <div class="mini"><div class="label">SAGE Tools</div><div class="value">${esc((candidate.generated_tools || []).length)}</div></div>
          </div>
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
        <div class="section split">
          <div class="box">
            <h3>Baseline Final Evidence</h3>
            <pre>${esc(finalMessages(control))}</pre>
          </div>
          <div class="box">
            <h3>SAGE Final Evidence</h3>
            <pre>${esc(finalMessages(candidate))}</pre>
          </div>
        </div>
        <div class="section">
          <h3 style="margin-top:0">Generated Tools Used On This Task</h3>
          <div class="pill-row">${(candidate.generated_tools || []).length ? candidate.generated_tools.map((tool) => `<span class="pill">${esc(tool)}</span>`).join("") : "<span class='small'>No generated or retained helper recorded for this task.</span>"}</div>
        </div>
      `;
    }

    function openTools() {
      const tools = payload.tool_summary || {};
      const rows = tools.tools || [];
      document.getElementById("toolDrawerSub").textContent = `${rows.length} tools; ${tools.called_tool_count || 0} called naturally in this run.`;
      document.getElementById("toolTable").innerHTML = `<table>
        <thead><tr><th>Tool</th><th>Origin</th><th>Visible</th><th>Called</th><th>VNC</th><th>Outcome Contribution</th><th>Score Contribution</th><th>Safety</th></tr></thead>
        <tbody>${rows.map((tool) => `<tr>
          <td><strong>${esc(tool.name)}</strong><div class="small">${esc(tool.decision || "")}</div></td>
          <td>${esc(tool.origin || "-")}</td>
          <td>${esc(tool.visible_count ?? 0)}</td>
          <td>${esc(tool.called_count ?? 0)}</td>
          <td>${esc(tool.visible_not_called_count ?? 0)}</td>
          <td class="${cls(tool.called_subset_mean_outcome_delta)}">${signedNum(tool.called_subset_mean_outcome_delta)}<div class="small">${esc(tool.outcome_gains ?? 0)} gains / ${esc(tool.outcome_regressions ?? 0)} regressions</div></td>
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
      const totalTasks = s.scenario_count ?? pairs.length ?? 0;
      document.getElementById("subtitle").textContent = `${payload.mode || "run"} · ${payload.status || "unknown"} · ${payload.agent || ""} · ${matched || 0}/${totalTasks || 0} matched tasks · refreshed ${new Date().toLocaleTimeString()}`;
      if (selected >= pairs.length) selected = Math.max(0, pairs.length - 1);
      renderMetrics();
      renderList();
      renderDetail();
    }

    async function load() {
      await refresh();
      if (!handlersBound) {
        handlersBound = true;
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
