"""Environment-neutral dashboard export for standalone SAGE runs."""

from __future__ import annotations

import html
import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

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
    if registry_path and registry_path.exists():
        shutil.copyfile(registry_path, output_dir / "registry.json")
    index_path = dashboard_dir / "index.html"
    index_path.write_text(_dashboard_html(data_payload), encoding="utf-8")
    return index_path


def _read_registry_payload(registry_path: Path | None) -> dict[str, Any]:
    if registry_path is None or not registry_path.exists():
        return {"schema_version": 1, "tools": {}}
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"schema_version": 1, "tools": {}}


def _dashboard_html(payload: dict[str, Any]) -> str:
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
    <h1>SAGE Standalone Dashboard</h1>
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
    const tasks = events.filter((event) => event.event === "task");
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
      if (!base) return "n/a";
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
      const first = related.find((event) => event.event === "task") || {{}};
      const retry = related.find((event) => event.event === "birth_task_retry");
      if (first.success) return {{ label: "success", className: "green" }};
      if (retry?.success) return {{ label: "retry success", className: "green" }};
      if (retry && !retry.success) return {{ label: "retry failed", className: "red" }};
      return {{ label: "needs helper", className: "red" }};
    }}
    function renderHeader() {{
      document.getElementById("subtitle").textContent =
        `${{summary.environment || "unknown"}} · ${{summary.model || "unknown model"}} · ` +
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
      document.getElementById("metrics").innerHTML = [
        metric("Baseline success", `${{baseline.tasks_succeeded || 0}}/${{baseline.tasks_seen || 0}}`, pct(baseline.tasks_succeeded || 0, baseline.tasks_seen || 0)),
        metric("Tasks succeeded", `${{summary.tasks_succeeded || 0}}/${{summary.tasks_seen || 0}}`, successRate, "good"),
        metric("Absolute lift", pp(delta), "SAGE success rate minus baseline", delta >= 0 ? "good" : "bad"),
        metric("Relative lift", liftPercent(baseRate, sageRate), baseRate ? "versus no-helper baseline" : "baseline was zero", baseRate ? "good" : "warn"),
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
