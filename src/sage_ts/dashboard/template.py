"""Static ToolSandbox SAGE dashboard template."""

from __future__ import annotations

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ToolSandbox SAGE Dashboard</title>
  <style>
    :root {
      --bg: #070d1a;
      --panel: #111936;
      --panel2: #16254a;
      --line: #2d4075;
      --text: #edf3ff;
      --muted: #a8b5dc;
      --blue: #67c2ff;
      --green: #56e39f;
      --red: #ff7373;
      --yellow: #ffd166;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: radial-gradient(circle at top left, #10234e 0, var(--bg) 38rem);
      color: var(--text);
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    .wrap { max-width: 1500px; margin: 0 auto; padding: 34px; }
    h1 { margin: 0 0 8px; font-size: clamp(34px, 5vw, 66px); letter-spacing: -0.05em; }
    h2 { margin: 0 0 18px; color: var(--muted); font-size: 18px; letter-spacing: .16em; text-transform: uppercase; }
    a { color: var(--blue); text-decoration: none; }
    .sub { color: var(--muted); font-size: 22px; margin-bottom: 26px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; }
    .card, .panel {
      background: linear-gradient(180deg, rgba(23,35,75,.96), rgba(15,22,49,.96));
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: 0 18px 60px rgba(0,0,0,.22);
    }
    .card { padding: 18px 20px; min-height: 118px; }
    .card .label { color: var(--muted); font-size: 13px; letter-spacing: .14em; text-transform: uppercase; }
    .card .value { font-size: clamp(28px, 4.2vw, 38px); font-weight: 800; margin: 12px 0 6px; letter-spacing: -0.04em; }
    .card .hint { color: var(--muted); font-size: 15px; line-height: 1.35; }
    .good { color: var(--green); }
    .bad { color: var(--red); }
    .warn { color: var(--yellow); }
    .panel { margin-top: 22px; padding: 24px 28px; }
    .chips { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }
    .chip {
      border: 1px solid var(--line);
      background: #0d1630;
      color: var(--muted);
      border-radius: 999px;
      padding: 9px 14px;
      font-weight: 700;
    }
    .timeline { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
    .step {
      border: 1px solid var(--line);
      background: #0b132a;
      border-radius: 16px;
      padding: 16px;
      color: var(--muted);
    }
    .step.active { border-color: var(--blue); background: #0c2642; color: var(--text); }
    .step.done { border-color: rgba(86,227,159,.55); }
    table { width: 100%; border-collapse: collapse; overflow: hidden; }
    th, td { padding: 12px 10px; border-bottom: 1px solid rgba(83,103,164,.25); text-align: left; vertical-align: top; }
    th { color: var(--muted); font-size: 13px; letter-spacing: .12em; text-transform: uppercase; position: sticky; top: 0; background: #101936; z-index: 1; }
    tr.gain td:first-child { border-left: 4px solid var(--green); }
    tr.regression td:first-child { border-left: 4px solid var(--red); }
    tr.preserved td:first-child { border-left: 4px solid var(--line); }
    .table-wrap { max-height: 760px; overflow: auto; border: 1px solid rgba(83,103,164,.35); border-radius: 18px; }
    .scenario-name { font-weight: 800; max-width: 520px; overflow-wrap: anywhere; }
    .tiny { color: var(--muted); font-size: 13px; margin-top: 5px; }
    .score { font-variant-numeric: tabular-nums; font-weight: 800; }
    .event-list { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
    .triple { display: grid; grid-template-columns: 1.1fr 1fr 1fr; gap: 18px; }
    .mini-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; }
    .kv {
      border: 1px solid rgba(83,103,164,.35);
      border-radius: 14px;
      background: #0b132a;
      padding: 12px;
    }
    .kv b { display: block; color: var(--muted); font-size: 12px; letter-spacing: .12em; text-transform: uppercase; margin-bottom: 6px; }
    .kv span { font-size: 18px; font-weight: 800; overflow-wrap: anywhere; }
    .plan-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      border-bottom: 1px solid rgba(83,103,164,.22);
      padding: 9px 0;
    }
    .plan-row:last-child { border-bottom: 0; }
    .status-pill { border-radius: 999px; padding: 3px 8px; font-size: 12px; background: #0b132a; color: var(--muted); white-space: nowrap; }
    .status-pill.completed { color: var(--green); }
    .status-pill.in_progress { color: var(--yellow); }
    .status-pill.blocked { color: var(--red); }
    .event {
      border: 1px solid rgba(83,103,164,.35);
      background: #0b132a;
      border-radius: 16px;
      padding: 14px;
      margin-bottom: 10px;
    }
    .event strong { display: block; margin-bottom: 4px; }
    .toolbar { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-bottom: 14px; }
    .links { display: flex; gap: 12px; flex-wrap: wrap; margin: 0 0 22px; }
    .btn {
      border: 1px solid var(--line);
      background: #0d1630;
      color: var(--blue);
      border-radius: 999px;
      padding: 10px 15px;
      font-weight: 800;
    }
    .topbar {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
    }
    .dashboard-switch {
      flex: 0 0 auto;
      min-width: 150px;
      border-radius: 999px;
      font-size: 13px;
      font-weight: 800;
      color: var(--blue);
      background: #0d1630;
    }
    input, select {
      background: #0b132a;
      color: var(--text);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px 12px;
      font-size: 15px;
    }
    input { min-width: 320px; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    @media (max-width: 950px) {
      .timeline, .event-list, .triple { grid-template-columns: 1fr; }
      .wrap { padding: 22px; }
      .topbar { flex-direction: column; }
    }
    @media (max-width: 560px) {
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main class="wrap">
    <div class="topbar">
      <div>
        <h1>ToolSandbox SAGE</h1>
        <div class="sub" id="subtitle">Loading dashboard data...</div>
      </div>
      <select id="dashboardSwitch" class="dashboard-switch" aria-label="Switch dashboard">
        <option value="index.html">Overview</option>
        <option value="task_focus.html">Task Focus</option>
        <option value="task_compare.html">Task Compare</option>
      </select>
    </div>
    <div class="links"><a class="btn" href="task_compare.html">Task Compare</a><a class="btn" href="task_focus.html">Task Focus</a></div>
    <section class="grid" id="metricGrid"></section>
    <section class="panel">
      <h2>Run Progress</h2>
      <div class="timeline" id="timeline"></div>
      <div class="chips" id="chips"></div>
    </section>
    <section class="panel">
      <h2>Campaign Overview</h2>
      <div class="triple">
        <div><div class="mini-grid" id="campaignGrid"></div></div>
        <div><h3>Validation Ladder</h3><div id="ladderBox"></div></div>
        <div><h3>Task Plan</h3><div id="taskPlan"></div></div>
      </div>
    </section>
    <section class="panel">
      <h2>Lifecycle, Registry, Blockers</h2>
      <div class="triple">
        <div><h3>Registry Inventory</h3><div id="registryBox"></div></div>
        <div><h3>Recent Campaign Events</h3><div id="campaignEvents"></div></div>
        <div><h3>Current Blocker</h3><div id="blockerBox"></div></div>
      </div>
    </section>
    <section class="panel">
      <h2>Scenario Outcomes</h2>
      <div class="toolbar">
        <input id="search" placeholder="Filter scenarios..." />
        <select id="filter">
          <option value="all">All</option>
          <option value="gain">Gains</option>
          <option value="regression">Regressions</option>
          <option value="preserved">Preserved</option>
          <option value="reuse">Generated-tool reuse</option>
          <option value="exception">Exceptions</option>
        </select>
      </div>
      <div class="table-wrap"><table>
        <thead><tr>
          <th>Scenario</th><th>Control</th><th>SAGE</th><th>Delta</th><th>Turns</th><th>Generated Tool</th><th>Artifacts</th>
        </tr></thead>
        <tbody id="scenarioRows"></tbody>
      </table></div>
    </section>
    <section class="panel">
      <h2>Tool Evolution</h2>
      <div class="event-list">
        <div><h3>Birth / Registry Events</h3><div id="birthEvents"></div></div>
        <div><h3>Recent Reuse Events</h3><div id="reuseEvents"></div></div>
      </div>
    </section>
  </main>
  <script>
    let state = null;
    const present = (n) => n !== null && n !== undefined && n !== "" && Number.isFinite(Number(n));
    const fmt = (n, digits = 3) => present(n) ? Number(n).toFixed(digits) : "-";
    const pct = (n) => present(n) ? (Number(n) * 100).toFixed(1) + "%" : "-";
    const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    function initDashboardSwitch() {
      const select = document.getElementById("dashboardSwitch");
      if (!select) return;
      const current = location.pathname.split("/").pop() || "index.html";
      select.value = current;
      select.addEventListener("change", () => {
        if (select.value && select.value !== current) location.href = select.value;
      });
    }
    function metric(label, value, hint, cls = "") {
      return `<div class="card"><div class="label">${label}</div><div class="value ${cls}">${value}</div><div class="hint">${hint}</div></div>`;
    }
    function render(data) {
      state = data;
      document.title = `ToolSandbox SAGE · ${data.mode || "run"}`;
      const model = data.model_metadata?.agent?.resolved_model || data.agent || "";
      const modelLabel = data.model_metadata?.agent?.requested_model && data.model_metadata.agent.requested_model !== model
        ? `${data.model_metadata.agent.requested_model} → ${model}`
        : model;
      document.getElementById("subtitle").textContent = `${data.mode || "run"} · ${data.status || "unknown"} · ${modelLabel} · ${data.base_tool_policy || ""}`;
      const c = data.control || {};
      const s = data.candidate || {};
      const d = data.comparison || {};
      const deltaCls = Number(data.mean_similarity_delta || 0) >= 0 ? "good" : "bad";
      const outcomeDelta = data.mean_outcome_similarity_delta;
      const outcomeCls = Number(outcomeDelta || 0) >= 0 ? "good" : "bad";
      const completed = s.scenario_count || c.scenario_count || 0;
      const planned = data.scenario_count || "?";
      const metrics = [
        metric("Run", `${completed}/${planned}`, `${data.status || "unknown"} · ${data.phase || "waiting"}`),
        metric("Score Lift", pct(data.mean_similarity_delta || 0), `${pct(c.mean_similarity)} → ${pct(s.mean_similarity)}`, deltaCls),
        metric("Perfect Tasks", `${c.success_count || 0} → ${s.success_count || 0}`, "exact success, control → SAGE"),
        metric("Accepted Tools", s.accepted_tool_count || 0, `${(s.accepted_tools || []).join(", ") || "none yet"}`, (s.accepted_tool_count || 0) > 0 ? "good" : "warn"),
        metric("Reuse Calls", s.reuse_count || 0, `${(s.reuse_scenarios || []).length || 0} scenario-level calls`, (s.reuse_count || 0) > 0 ? "good" : "warn"),
        metric("Tool Attempts", s.generated_tool_attempted_scenarios || 0, `${s.generated_tool_called_scenarios || 0} called · ${s.generated_tool_failed_scenarios || 0} failed`, (s.generated_tool_failed_scenarios || 0) > 0 ? "bad" : ""),
        metric("Scenario Mix", `${d.gain_count || 0} / ${d.regression_count || 0}`, `gains / regressions · ${d.preserved_count || 0} preserved`, (d.gain_count || 0) >= (d.regression_count || 0) ? "good" : "bad"),
        metric("Turns", `${c.total_turns || 0} → ${s.total_turns || 0}`, "total turns, control → SAGE"),
        metric("Exceptions", `${c.exception_count || 0} → ${s.exception_count || 0}`, "control → SAGE", (s.exception_count || 0) ? "bad" : "")
      ];
      if (present(outcomeDelta)) {
        metrics.splice(2, 0, metric("Outcome Lift", pct(outcomeDelta), `${pct(c.mean_outcome_similarity)} → ${pct(s.mean_outcome_similarity)}`, outcomeCls));
      }
      document.getElementById("metricGrid").innerHTML = metrics.join("");
      renderTimeline(data);
      renderChips(data);
      renderCampaign(data);
      renderRows();
      renderEvents(data);
    }
    function renderTimeline(data) {
      const phases = ["control", "candidate", "comparison"];
      document.getElementById("timeline").innerHTML = phases.map(p => {
        const cls = data.phase === p ? "active" : phases.indexOf(p) < phases.indexOf(data.phase || "") ? "done" : "";
        const note = p === "control" ? "baseline reduced-tool run" : p === "candidate" ? "SAGE generation/reuse run" : "paired score + reuse analysis";
        return `<div class="step ${cls}"><strong>${p}</strong><div class="tiny">${note}</div></div>`;
      }).join("");
    }
    function renderChips(data) {
      const chips = [
        data.model_metadata?.agent?.resolved_model || data.agent,
        data.model_metadata?.comparison_key,
        data.user, data.base_tool_policy, `${data.scenario_count || 0} scenarios`,
        `${data.generation_enabled ? "generation on" : "generation off"}`,
        `updated ${new Date(data.updated_at || Date.now()).toLocaleTimeString()}`
      ].filter(Boolean);
      document.getElementById("chips").innerHTML = chips.map(x => `<span class="chip">${esc(x)}</span>`).join("");
    }
    function renderCampaign(data) {
      const campaign = data.campaign || {};
      const status = campaign.status || {};
      const milestones = status.milestones || {};
      document.getElementById("campaignGrid").innerHTML = [
        ["Phase", status.phase || "-"],
        ["Git", (status.git_sha || "-").slice(0, 7)],
        ["Branch", status.branch || "-"],
        ["Tool Classes", `${milestones.accepted_tool_classes || 0}/${milestones.target_tool_classes || 3}`],
        ["Categories", `${(milestones.challenge_categories || []).length}/${milestones.target_challenge_category_count || 2}`],
        ["Dashboard", milestones.dashboard_live ? "live" : "pending"]
      ].map(([k, v]) => `<div class="kv"><b>${esc(k)}</b><span>${esc(v)}</span></div>`).join("");
      const ladder = status.ladder || {};
      document.getElementById("ladderBox").innerHTML = Object.entries(ladder).map(([k, v]) => `<div class="plan-row"><span>${esc(k.replaceAll("_", " "))}</span><span class="status-pill">${esc(v)}</span></div>`).join("") || "<div class='tiny'>No ladder state yet.</div>";
      const tasks = ((campaign.task_plan || {}).tasks || []).slice(0, 10);
      document.getElementById("taskPlan").innerHTML = tasks.map(t => `<div class="plan-row"><span>${esc(t.task)}</span><span class="status-pill ${esc(t.status)}">${esc(t.status)}</span></div>`).join("") || "<div class='tiny'>No task plan yet.</div>";
      const tools = Object.entries((data.registry_manifest || {}).tools || {});
      document.getElementById("registryBox").innerHTML = tools.map(([name, entry]) => `<div class="event"><strong>${esc(name)}</strong><div>${esc(entry.tool?.spec?.family || "-")}</div><div class="tiny">reuse ${esc(entry.reuse_count || 0)} · born ${esc(entry.birth_scenario || "-")}</div></div>`).join("") || "<div class='tiny'>No accepted tools in this run registry yet.</div>";
      const events = (campaign.events || []).slice(-10).reverse();
      document.getElementById("campaignEvents").innerHTML = events.map(e => `<div class="event"><strong>${esc(e.event)}</strong><div>${esc(e.scenario || e.tool_name || e.mode || "")}</div><div class="tiny">${esc(e.timestamp || "")}</div></div>`).join("") || "<div class='tiny'>No campaign events yet.</div>";
      document.getElementById("blockerBox").innerHTML = `<div class="event"><strong>${esc(status.current_blocker || "No blocker recorded")}</strong><div class="tiny">${esc(status.next_action || "")}</div></div>`;
    }
    function renderRows() {
      if (!state) return;
      const q = document.getElementById("search").value.toLowerCase();
      const f = document.getElementById("filter").value;
      const rows = (state.scenarios || []).filter(r => {
        const hay = `${r.scenario} ${(r.categories || []).join(" ")} ${(r.reused_tools || []).join(" ")}`.toLowerCase();
        if (q && !hay.includes(q)) return false;
        if (f === "all") return true;
        if (f === "reuse") return (r.reused_tools || []).length > 0;
        if (f === "exception") return r.control_exception || r.candidate_exception;
        return r.status === f;
      });
      document.getElementById("scenarioRows").innerHTML = rows.map(r => {
        const dcls = Number(r.delta || 0) > 0 ? "good" : Number(r.delta || 0) < 0 ? "bad" : "";
        const artifacts = [r.control_trace_url ? `<a href="${r.control_trace_url}">control</a>` : "", r.candidate_trace_url ? `<a href="${r.candidate_trace_url}">sage</a>` : ""].filter(Boolean).join(" · ");
        const controlOutcome = present(r.control_outcome_similarity) ? `<div class="tiny">outcome ${pct(r.control_outcome_similarity)}</div>` : "";
        const controlCache = r.control_cache_source === "cached" ? `<div class="tiny">control source: cached</div>` : "";
        const sageOutcome = present(r.candidate_outcome_similarity) ? `<div class="tiny">outcome ${pct(r.candidate_outcome_similarity)}</div>` : "";
        const deltaOutcome = present(r.outcome_delta) ? `<div class="tiny">outcome ${fmt(r.outcome_delta, 4)}</div>` : "";
        return `<tr class="${r.status || ""}">
          <td><div class="scenario-name">${esc(r.scenario)}</div><div class="tiny">${esc((r.categories || []).join(" · "))}</div></td>
          <td class="score">${pct(r.control_similarity)}${controlOutcome}${controlCache}${r.control_exception ? `<div class="tiny bad">${esc(r.control_exception)}</div>` : ""}</td>
          <td class="score">${pct(r.candidate_similarity)}${sageOutcome}${r.candidate_exception ? `<div class="tiny bad">${esc(r.candidate_exception)}</div>` : ""}</td>
          <td class="score ${dcls}">${fmt(r.delta, 4)}${deltaOutcome}</td>
          <td>${r.control_turns ?? "-"} → ${r.candidate_turns ?? "-"}</td>
          <td>${esc((r.reused_tools || []).join(", ") || "-")}</td>
          <td>${artifacts}</td>
        </tr>`;
      }).join("");
    }
    function renderEvents(data) {
      const births = (data.birth_events || []).concat(data.run_events || []).slice(-12).reverse();
      const reuse = (data.reuse_events || []).slice(-18).reverse();
      document.getElementById("birthEvents").innerHTML = births.map(e => `<div class="event"><strong>${esc(e.event || (e.accepted ? "accepted_tool_birth" : "tool_birth"))}</strong><div>${esc(e.tool_name || e.canonical_key || "-")}</div><div class="tiny">${esc(e.birth_scenario || e.scenario || e.registry_dir || "")}</div></div>`).join("") || "<div class='tiny'>No birth or registry events yet.</div>";
      document.getElementById("reuseEvents").innerHTML = reuse.map(e => `<div class="event"><strong>${esc(e.tool_name)}</strong><div>${esc(e.scenario)}</div></div>`).join("") || "<div class='tiny'>No generated-tool reuse yet.</div>";
    }
    function captureScroll() {
      const table = document.querySelector(".table-wrap");
      return {
        x: window.scrollX,
        y: window.scrollY,
        tableTop: table?.scrollTop || 0,
      };
    }
    function restoreScroll(snapshot) {
      const table = document.querySelector(".table-wrap");
      if (table) table.scrollTop = snapshot.tableTop;
      window.scrollTo(snapshot.x, snapshot.y);
    }
    async function refresh() {
      try {
        const scroll = captureScroll();
        const res = await fetch(`data.json?ts=${Date.now()}`, { cache: "no-store" });
        if (!res.ok) throw new Error(`${res.status}`);
        render(await res.json());
        requestAnimationFrame(() => restoreScroll(scroll));
      } catch (err) {
        document.getElementById("subtitle").textContent = `Dashboard data unavailable: ${err}`;
      }
    }
    document.getElementById("search").addEventListener("input", renderRows);
    document.getElementById("filter").addEventListener("change", renderRows);
    initDashboardSwitch();
    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>
"""
