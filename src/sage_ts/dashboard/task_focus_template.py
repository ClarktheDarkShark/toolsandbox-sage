"""Static task-focused dashboard template."""

from __future__ import annotations

TASK_FOCUS_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ToolSandbox SAGE Task Focus</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #07101f;
      --panel: #101a34;
      --panel2: #17305a;
      --line: #324775;
      --text: #edf4ff;
      --muted: #aab8da;
      --blue: #78c8ff;
      --good: #66e89b;
      --bad: #ff7c80;
      --warn: #ffd36a;
      --tool: #63d6bf;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: radial-gradient(circle at 20% 0%, #12244b 0, var(--bg) 44%);
      color: var(--text);
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      padding: 22px 28px 16px;
      border-bottom: 1px solid rgba(120, 200, 255, 0.2);
      background: rgba(7, 16, 31, 0.94);
      position: sticky;
      top: 0;
      z-index: 5;
    }
    h1 { margin: 0 0 6px; font-size: clamp(30px, 4vw, 54px); letter-spacing: -0.05em; }
    a { color: var(--blue); text-decoration: none; }
    .sub { color: var(--muted); font-size: 19px; }
    .top { display: grid; grid-template-columns: repeat(5, minmax(125px, 1fr)); gap: 12px; margin-top: 18px; }
    .metric, .card {
      border: 1px solid var(--line);
      background: rgba(23, 39, 74, 0.78);
      border-radius: 18px;
      padding: 13px 15px;
    }
    .label {
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.14em;
      font-size: 11px;
      font-weight: 800;
    }
    .metric .value { margin-top: 8px; font-size: 25px; font-weight: 850; }
    .metric .note { margin-top: 3px; color: var(--muted); font-size: 13px; }
    main {
      display: grid;
      grid-template-columns: minmax(230px, 24vw) 1fr;
      height: calc(100vh - 178px);
      overflow: hidden;
    }
    aside {
      border-right: 1px solid var(--line);
      background: rgba(9, 17, 35, 0.92);
      overflow: auto;
    }
    .task-head {
      padding: 14px;
      position: sticky;
      top: 0;
      background: rgba(9, 17, 35, 0.98);
      z-index: 2;
    }
    .toggles { display: grid; grid-template-columns: repeat(3, 1fr); gap: 7px; margin-top: 10px; }
    button {
      color: var(--text);
      border: 1px solid var(--line);
      background: rgba(23, 39, 74, 0.72);
      border-radius: 999px;
      cursor: pointer;
      font: inherit;
      font-weight: 800;
      padding: 7px 10px;
    }
    button.active { border-color: var(--tool); background: rgba(99, 214, 191, 0.18); }
    .task {
      display: block;
      width: 100%;
      border: 0;
      border-top: 1px solid rgba(50, 71, 117, 0.58);
      border-radius: 0;
      text-align: left;
      padding: 12px 14px;
      background: transparent;
    }
    .task:hover, .task.selected { background: rgba(99, 214, 191, 0.12); }
    .task .row { display: flex; justify-content: space-between; gap: 8px; margin-bottom: 7px; }
    .phase { color: var(--blue); text-transform: uppercase; letter-spacing: 0.13em; font-size: 12px; }
    .pill { border: 1px solid var(--line); border-radius: 999px; padding: 2px 8px; color: var(--muted); font-size: 12px; white-space: nowrap; }
    .pill.complete { color: var(--good); border-color: rgba(102, 232, 155, 0.42); }
    .pill.running { color: var(--warn); border-color: rgba(255, 211, 106, 0.42); }
    .task-name { line-height: 1.25; overflow-wrap: anywhere; }
    .task-meta { color: var(--muted); font-size: 12px; margin-top: 7px; }
    .tool-badge {
      display: inline-block;
      margin-top: 7px;
      border: 1px solid rgba(99, 214, 191, 0.6);
      border-radius: 999px;
      padding: 3px 8px;
      color: var(--tool);
      background: rgba(99, 214, 191, 0.13);
      font-size: 12px;
      font-weight: 850;
    }
    section.detail { overflow: auto; min-width: 0; }
    .detail-head {
      padding: 18px 24px;
      border-bottom: 1px solid var(--line);
      background: rgba(10, 18, 36, 0.62);
    }
    .detail-title { margin: 0; font-size: clamp(22px, 2.5vw, 36px); letter-spacing: -0.03em; line-height: 1.12; }
    .tags { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
    .outcome { display: grid; grid-template-columns: 0.7fr 1.1fr 1fr; gap: 10px; margin-top: 14px; }
    .card .body {
      margin-top: 7px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      max-height: 7.2em;
      overflow-y: auto;
      font-size: 14px;
      line-height: 1.35;
    }
    .good { color: var(--good); }
    .bad { color: var(--bad); }
    .muted { color: var(--muted); }
    .chat { padding: 20px 24px 34px; }
    .msg { display: flex; margin: 14px 0; }
    .msg.user { justify-content: flex-start; }
    .msg.assistant { justify-content: flex-end; }
    .msg.tool { justify-content: center; }
    .bubble {
      max-width: min(820px, 86%);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 14px 16px;
      background: rgba(17, 27, 52, 0.86);
    }
    .assistant .bubble { background: rgba(31, 80, 120, 0.68); border-color: rgba(120, 200, 255, 0.38); }
    .tool .bubble { background: rgba(21, 48, 47, 0.82); border-color: rgba(99, 214, 191, 0.42); }
    .uses-tool .bubble { box-shadow: 0 0 0 2px rgba(99, 214, 191, 0.34); }
    pre { margin: 8px 0 0; white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; line-height: 1.38; }
    .empty { margin: 44px auto; max-width: 760px; border: 1px dashed var(--line); border-radius: 22px; padding: 30px; color: var(--muted); }
    @media (max-width: 900px) {
      .top, .outcome { grid-template-columns: 1fr 1fr; }
      main { grid-template-columns: 1fr; height: auto; }
      aside { max-height: 42vh; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Task Focus</h1>
    <div class="sub"><span id="subtitle">Loading...</span> · <a href="index.html">main dashboard</a></div>
    <div class="top" id="top"></div>
  </header>
  <main>
    <aside>
      <div class="task-head">
        <div class="label" id="taskCount">Tasks</div>
        <div class="toggles">
          <button data-filter="candidate" class="active">SAGE</button>
          <button data-filter="control">Control</button>
          <button data-filter="all">All</button>
        </div>
      </div>
      <div id="taskList"></div>
    </aside>
    <section class="detail" id="detail">
      <div class="detail-head" id="detailHead"></div>
      <div class="chat" id="chat"></div>
    </section>
  </main>
  <script>
    let data = null;
    let filter = localStorage.getItem("sageTaskFocusFilter") || "candidate";
    let selected = null;
    const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const fmt = (n, d = 3) => Number.isFinite(Number(n)) ? Number(n).toFixed(d) : "-";
    function visibleTasks() {
      const tasks = data?.tasks || [];
      return tasks.filter(t => filter === "all" || t.phase === filter);
    }
    function currentTask() {
      const tasks = visibleTasks();
      return tasks.find(t => t.id === selected) || tasks.find(t => t.id === data?.active_task_id) || tasks[tasks.length - 1];
    }
    function renderTop() {
      const s = data?.summary || {};
      document.getElementById("subtitle").textContent = `${data?.mode || "run"} · ${data?.phase || "-"} · ${data?.status || "-"} · ${data?.agent || ""}`;
      document.getElementById("top").innerHTML = [
        ["Phase", data?.phase || "-", data?.status || "-"],
        ["Progress", `${s.current_completed || 0}/${s.scenario_count || "?"}`, "current phase"],
        ["Mean Score", fmt(s.current_mean_similarity), "similarity so far"],
        ["Turns", s.current_turns || 0, "current phase"],
        ["Tool Evolution", `${s.accepted_tools || 0} accepted`, `${s.reuse_count || 0} reuse calls`],
      ].map(([label, value, note]) => `<div class="metric"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div><div class="note">${esc(note)}</div></div>`).join("");
    }
    function renderList() {
      const tasks = visibleTasks();
      document.querySelectorAll(".toggles button").forEach(b => b.classList.toggle("active", b.dataset.filter === filter));
      document.getElementById("taskCount").textContent = `${filter === "all" ? "All" : filter.toUpperCase()} Tasks (${tasks.length})`;
      document.getElementById("taskList").innerHTML = tasks.map((t, i) => `
        <button class="task ${t.id === currentTask()?.id ? "selected" : ""}" data-id="${esc(t.id)}">
          <div class="row"><span class="phase">${esc(t.phase)}</span><span class="pill ${esc(t.status)}">${esc(t.status)}</span></div>
          <div class="task-name">${i + 1}. ${esc(t.short_name || t.scenario)}</div>
          <div class="task-meta">score ${fmt(t.similarity)} · ${t.message_count || 0} messages</div>
          ${(t.generated_tools || []).map(tool => `<span class="tool-badge">generated: ${esc(tool)}</span>`).join("")}
        </button>`).join("");
    }
    function renderDetail() {
      const task = currentTask();
      if (!task) {
        document.getElementById("detailHead").innerHTML = "<div class='empty'>Waiting for task data...</div>";
        document.getElementById("chat").innerHTML = "";
        return;
      }
      selected = task.id;
      const o = task.outcome || {};
      const correctness = o.correctness_label === "correct" ? "good" : o.correctness_label === "pending" ? "" : "bad";
      const expected = (o.expected_answers || []).join("\n\n") || o.expected_note || "State-scored target; inspect messages and tool evidence.";
      const agent = o.agent_result_summary || o.agent_final_answer || "not available yet";
      document.getElementById("detailHead").innerHTML = `
        <h2 class="detail-title">${esc(task.short_name || task.scenario)}</h2>
        <div class="tags">
          <span class="pill ${esc(task.status)}">${esc(task.status)}</span>
          <span class="pill">score ${fmt(task.similarity)}</span>
          <span class="pill">${task.turn_count || "-"} turns</span>
          ${(task.categories || []).map(c => `<span class="pill">${esc(c)}</span>`).join("")}
        </div>
        <div class="outcome">
          <div class="card"><div class="label">Correctness</div><div class="body ${correctness}">${esc(o.correctness_label || "pending")} · score ${fmt(o.similarity)}</div></div>
          <div class="card"><div class="label">Agent Result</div><div class="body">${esc(agent)}</div></div>
          <div class="card"><div class="label">Expected / Target</div><div class="body muted">${esc(expected)}</div></div>
        </div>`;
      const messages = task.messages || [];
      document.getElementById("chat").innerHTML = messages.length ? messages.map(m => `
        <div class="msg ${esc(m.role)} ${m.uses_generated_tool ? "uses-tool" : ""}">
          <div class="bubble">
            <div class="label">${esc((m.index + 1) + " · " + m.label)}</div>
            ${(m.generated_tools || []).map(tool => `<div class="tool-badge">generated tool used: ${esc(tool)}</div>`).join("")}
            <pre>${esc(m.content || "[empty message]")}</pre>
          </div>
        </div>`).join("") : "<div class='empty'>Waiting for task messages...</div>";
    }
    function render() { renderTop(); renderList(); renderDetail(); }
    async function refresh() {
      try {
        const response = await fetch(`task_focus_data.json?ts=${Date.now()}`, { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        data = await response.json();
        render();
      } catch (error) {
        document.getElementById("chat").innerHTML = `<div class="empty">Task focus data unavailable: ${esc(error.message)}</div>`;
      }
    }
    document.querySelector(".toggles").addEventListener("click", e => {
      const b = e.target.closest("button");
      if (!b) return;
      filter = b.dataset.filter || "candidate";
      localStorage.setItem("sageTaskFocusFilter", filter);
      selected = null;
      render();
    });
    document.getElementById("taskList").addEventListener("click", e => {
      const b = e.target.closest("button.task");
      if (!b) return;
      selected = b.dataset.id;
      render();
    });
    refresh();
    setInterval(refresh, 3000);
  </script>
</body>
</html>
"""
