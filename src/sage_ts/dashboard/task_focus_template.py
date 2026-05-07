"""Static task-focused dashboard template."""

from __future__ import annotations

TASK_FOCUS_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Task Focus — SAGE</title>
  <style>
    :root {
      --bg: #07101f; --panel: #0d1c38; --border: #1c3460;
      --text: #e8f0ff; --muted: #7a90bc;
      --blue: #78c8ff; --good: #56d084; --bad: #ff6568; --warn: #ffd26a; --tool: #56c8b0;
      --hh: 130px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: var(--bg); color: var(--text); font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; font-size: 14px; line-height: 1.45; overflow: hidden; }
    a { color: var(--muted); text-decoration: none; } a:hover { color: var(--blue); }

    /* ── Header ── */
    header { height: var(--hh); background: rgba(7,16,31,.97); border-bottom: 1px solid var(--border); padding: 10px 16px 8px; position: sticky; top: 0; z-index: 10; display: flex; flex-direction: column; gap: 6px; }
    .h-row { display: flex; align-items: center; gap: 12px; }
    h1 { font-size: 20px; font-weight: 900; letter-spacing: -.05em; }
    #subtitle { color: var(--muted); font-size: 11px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .arm-bar { display: flex; gap: 5px; }
    .arm-btn { padding: 3px 12px; border: 1px solid var(--border); border-radius: 999px; background: transparent; color: var(--muted); cursor: pointer; font: inherit; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: .1em; }
    .arm-btn:hover { border-color: var(--blue); color: var(--text); }
    .arm-btn.active { border-color: var(--blue); color: var(--blue); background: rgba(120,200,255,.1); }
    #topMetrics { display: flex; gap: 7px; }
    .metric { flex: 1; border: 1px solid var(--border); border-radius: 9px; padding: 5px 9px; background: rgba(13,28,56,.7); min-width: 0; }
    .mlabel { color: var(--muted); font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: .12em; }
    .mvalue { font-size: 16px; font-weight: 900; margin-top: 1px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .mnote { font-size: 10px; color: var(--muted); }
    .mvalue.good { color: var(--good); } .mvalue.bad { color: var(--bad); }

    /* ── Layout ── */
    main { display: grid; grid-template-columns: 230px 1fr; height: calc(100vh - var(--hh)); overflow: hidden; }

    /* ── Sidebar ── */
    aside { border-right: 1px solid var(--border); overflow-y: auto; background: rgba(7,16,31,.95); }
    .task { display: block; width: 100%; border: 0; border-top: 1px solid rgba(28,52,96,.5); border-left: 2px solid transparent; text-align: left; background: transparent; padding: 8px 11px; cursor: pointer; color: var(--text); font: inherit; }
    .task:hover { background: rgba(120,200,255,.05); }
    .task.selected { background: rgba(120,200,255,.09); border-left-color: var(--blue); }
    .task.running { opacity: .75; }
    .t-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
    .t-title { display: block; min-width: 0; margin-top: 5px; }
    .task-num { flex: 0 0 auto; border: 1px solid rgba(120,200,255,.35); border-radius: 999px; padding: 1px 6px; color: var(--blue); font-size: 9px; font-weight: 900; letter-spacing: .04em; line-height: 1.25; white-space: nowrap; }
    .t-name { display: block; font-size: 11px; line-height: 1.32; overflow-wrap: break-word; word-break: normal; }
    .status-pair { display: flex; gap: 4px; flex-wrap: wrap; justify-content: flex-end; }
    .status-pair .pill { font-size: 9px; padding: 1px 5px; }
    .pill { border: 1px solid var(--border); border-radius: 999px; padding: 1px 6px; font-size: 10px; color: var(--muted); white-space: nowrap; }
    .pill.complete { color: var(--good); border-color: rgba(86,208,132,.35); }
    .pill.running { color: var(--warn); border-color: rgba(255,210,106,.35); }
    .pill.good { color: var(--good); border-color: rgba(86,208,132,.35); }
    .pill.bad { color: var(--bad); border-color: rgba(255,101,104,.35); }
    .score-pair { display: flex; gap: 4px; margin-top: 3px; }
    .sc { font-size: 10px; padding: 1px 5px; border-radius: 4px; border: 1px solid var(--border); color: var(--muted); }
    .sc.hit { border-color: rgba(86,200,176,.45); color: var(--tool); }
    .t-score { font-size: 10px; color: var(--muted); margin-top: 2px; }
    .tbadge { display: inline-block; margin-top: 3px; border: 1px solid rgba(86,200,176,.4); border-radius: 999px; padding: 1px 6px; color: var(--tool); font-size: 10px; }

    /* ── Detail pane ── */
    section.detail { display: flex; flex-direction: column; overflow: hidden; min-width: 0; }
    #detailHead { padding: 12px 16px 10px; border-bottom: 1px solid var(--border); background: rgba(10,18,36,.65); flex-shrink: 0; overflow-y: auto; max-height: 34%; }
    .d-title { font-size: 18px; font-weight: 900; letter-spacing: -.03em; margin-bottom: 7px; overflow-wrap: anywhere; display: flex; align-items: baseline; gap: 9px; flex-wrap: wrap; }
    .detail-task-num { border: 1px solid rgba(120,200,255,.4); border-radius: 999px; padding: 2px 8px; color: var(--blue); font-size: 10px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; white-space: nowrap; }
    .comparison { display: flex; align-items: center; gap: 7px; margin-bottom: 7px; flex-wrap: wrap; }
    .cmp { border: 1px solid var(--border); border-radius: 8px; padding: 5px 10px; text-align: center; }
    .cmp.sage { border-color: rgba(86,200,176,.4); }
    .cmp.good { border-color: rgba(86,208,132,.4); } .cmp.good .cv { color: var(--good); }
    .cmp.bad { border-color: rgba(255,101,104,.4); } .cmp.bad .cv { color: var(--bad); }
    .cv { font-size: 15px; font-weight: 900; }
    .cmp-sep { color: var(--muted); font-size: 14px; }
    .tags { display: flex; flex-wrap: wrap; gap: 5px; margin: 5px 0; }
    .card { border: 1px solid var(--border); border-radius: 8px; padding: 7px 9px; background: rgba(13,28,56,.6); }

    /* ── Evaluation ── */
    #milestones { padding: 7px 16px 8px; border-bottom: 1px solid var(--border); flex-shrink: 0; max-height: 28%; overflow-y: auto; }
    .sec-head { font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: .12em; color: var(--muted); margin-bottom: 5px; }
    .eval-top { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-bottom: 8px; }
    .eval-metric { border: 1px solid var(--border); border-radius: 8px; padding: 7px 9px; background: rgba(13,28,56,.6); min-width: 0; }
    .eval-metric .big { font-size: 16px; font-weight: 900; }
    .eval-metric .note { font-size: 10px; color: var(--muted); margin-top: 2px; }
    .eval-list { display: flex; flex-direction: column; gap: 6px; }
    .check { border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: rgba(13,28,56,.52); }
    .check.good { border-color: rgba(86,208,132,.35); }
    .check.bad { border-color: rgba(255,101,104,.35); }
    .check.warn { border-color: rgba(255,210,106,.35); }
    .check-head { display: grid; grid-template-columns: 120px 1fr auto; gap: 8px; align-items: center; padding: 6px 9px; background: rgba(255,255,255,.02); }
    .check-kind { font-size: 10px; text-transform: uppercase; letter-spacing: .1em; color: var(--muted); }
    .check-label { font-size: 11px; font-weight: 700; overflow-wrap: anywhere; }
    .check-score { font-size: 10px; color: var(--muted); white-space: nowrap; }
    .check-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0; border-top: 1px solid rgba(28,52,96,.65); }
    .check-col { min-width: 0; padding: 7px 9px; }
    .check-col + .check-col { border-left: 1px solid rgba(28,52,96,.65); }
    .check-col-head { font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: .12em; color: var(--muted); margin-bottom: 4px; }
    .check-line { font-size: 11px; line-height: 1.4; overflow-wrap: anywhere; }
    .check-line + .check-line { margin-top: 3px; }
    .check-line.expected { color: var(--muted); font-family: ui-monospace, monospace; }
    .check-line.observed { color: var(--text); }
    .paired-eval-top { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-bottom: 8px; }
    .paired-run-card { border: 1px solid var(--border); border-radius: 8px; background: rgba(13,28,56,.6); overflow: hidden; min-width: 0; }
    .paired-run-card.missing { opacity: .7; }
    .paired-run-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 7px 9px; background: rgba(255,255,255,.02); border-bottom: 1px solid rgba(28,52,96,.65); }
    .paired-run-title { font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: .12em; color: var(--muted); }
    .paired-run-status { font-size: 10px; color: var(--muted); }
    .paired-run-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; padding: 8px; }
    .paired-mini { border: 1px solid rgba(28,52,96,.65); border-radius: 7px; padding: 6px 7px; min-width: 0; }
    .paired-mini .mlabel { font-size: 8px; }
    .paired-mini .mvalue { font-size: 13px; }
    .paired-mini .mnote { font-size: 9px; }
    .paired-check-list { display: flex; flex-direction: column; gap: 6px; }
    .paired-check { border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: rgba(13,28,56,.52); }
    .paired-check.good { border-color: rgba(86,208,132,.35); }
    .paired-check.bad { border-color: rgba(255,101,104,.35); }
    .paired-check.warn { border-color: rgba(255,210,106,.35); }
    .paired-check-head { display: grid; grid-template-columns: 120px 1fr; gap: 8px; align-items: center; padding: 6px 9px; background: rgba(255,255,255,.02); }
    .paired-check-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.1fr); border-top: 1px solid rgba(28,52,96,.65); }
    .pair-cell { min-width: 0; padding: 7px 9px; }
    .pair-cell + .pair-cell { border-left: 1px solid rgba(28,52,96,.65); }
    .pair-status { display: inline-block; margin-bottom: 4px; padding: 1px 6px; border: 1px solid var(--border); border-radius: 999px; font-size: 9px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }
    .pair-status.good { color: var(--good); border-color: rgba(86,208,132,.35); }
    .pair-status.bad { color: var(--bad); border-color: rgba(255,101,104,.35); }
    .pair-status.warn { color: var(--warn); border-color: rgba(255,210,106,.35); }
    .empty-mini { color: var(--muted); font-size: 11px; }

    /* ── Chat ── */
    #chatWrap { flex: 1; overflow-y: auto; min-height: 0; }
    #chat { padding: 12px 16px 24px; }
    .msg { display: flex; margin: 7px 0; }
    .msg.user { justify-content: flex-start; }
    .msg.assistant { justify-content: flex-end; }
    .msg.tool { justify-content: flex-start; }
    .bubble { max-width: min(780px, 90%); border: 1px solid var(--border); border-radius: 13px; padding: 8px 12px; background: rgba(13,28,56,.85); }
    .msg.assistant .bubble { background: rgba(20,64,108,.72); border-color: rgba(120,200,255,.28); }
    .msg.tool .bubble { background: rgba(12,44,40,.82); border-color: rgba(86,200,176,.32); }
    .msg.uses-tool .bubble { box-shadow: 0 0 0 2px rgba(86,200,176,.28); }
    .msg-lbl { font-size: 9px; color: var(--muted); margin-bottom: 3px; text-transform: uppercase; letter-spacing: .08em; }
    .paired-chat { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; align-items: start; }
    .chat-lane { min-width: 0; border: 1px solid var(--border); border-radius: 10px; background: rgba(13,28,56,.42); overflow: hidden; }
    .chat-lane-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 8px 10px; border-bottom: 1px solid rgba(28,52,96,.65); background: rgba(255,255,255,.02); }
    .chat-lane-body { padding: 8px 10px 12px; }
    .chat-lane .msg { margin: 6px 0; }
    .chat-lane .bubble { max-width: 100%; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; font-size: 12px; line-height: 1.45; }
    .empty { margin: 28px auto; max-width: 480px; border: 1px dashed var(--border); border-radius: 13px; padding: 20px; color: var(--muted); text-align: center; font-size: 12px; }
    .waiting { color: var(--warn); }

    @media (max-width: 720px) {
      main { grid-template-columns: 1fr; height: auto; overflow: auto; }
      aside { max-height: 36vh; border-right: 0; border-bottom: 1px solid var(--border); }
      section.detail { height: 64vh; }
      #topMetrics { flex-wrap: wrap; }
      .eval-top, .check-grid, .paired-eval-top, .paired-check-grid, .paired-chat { grid-template-columns: 1fr; }
      .check-head, .paired-check-head, .paired-run-metrics { grid-template-columns: 1fr; }
      .check-col + .check-col, .pair-cell + .pair-cell { border-left: 0; border-top: 1px solid rgba(28,52,96,.65); }
    }
  </style>
</head>
<body>
  <header>
    <div class="h-row">
      <h1>Task Focus</h1>
      <span id="subtitle">Loading…</span>
      <div class="arm-bar">
        <button class="arm-btn" data-arm="control">Baseline</button>
        <button class="arm-btn active" data-arm="paired">Paired</button>
        <button class="arm-btn" data-arm="candidate">SAGE</button>
      </div>
      <a href="index.html" style="font-size:11px;white-space:nowrap">main ↗</a>
    </div>
    <div id="topMetrics"></div>
  </header>
  <main>
    <aside><div id="taskList"></div></aside>
    <section class="detail">
      <div id="detailHead"></div>
      <div id="milestones"></div>
      <div id="chatWrap"><div id="chat"></div></div>
    </section>
  </main>
  <script>
    let data = null, arm = "paired", selectedId = null;
    let _renderedCount = {}, _chatFor = null;

    const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":'&#39;'}[c]));
    const present = n => n !== null && n !== undefined && n !== "" && Number.isFinite(Number(n));
    const fmt = (n, d=3) => present(n) ? Number(n).toFixed(d) : "—";
    const fmtD = n => { if (!present(n)) return "—"; const v=Number(n); return (v>0?"+":"")+v.toFixed(3); };
    const fmtPct = n => { if (!present(n)) return "—"; const v=Number(n); return (v>0?"+":"")+v.toFixed(1)+"%"; };

    /* Return the list of visible entries for the current arm */
    function entries() {
      if (!data) return [];
      if (arm === "paired") return data.pairs || [];
      return (data.tasks || []).filter(t => t.phase === arm);
    }

    /* Return the currently focused entry */
    function current() {
      const list = entries();
      if (selectedId) { const f = list.find(e => e.id === selectedId); if (f) return f; }
      const aid = data?.active_task_id;
      if (aid) {
        const f = list.find(e => e.id === aid ||
          (arm === "paired" && (e.candidate?.id === aid || e.control?.id === aid)));
        if (f) return f;
      }
      return list[list.length - 1] || null;
    }

    /* Return the single-task object for a given entry, respecting current arm. */
    function taskOf(entry) {
      if (!entry) return null;
      if (entry.phase) return entry;  // already a single-arm task
      if (arm === "control") return entry.control || null;
      return entry.candidate || null;
    }

    function pairedTasks(entry) {
      if (!entry || entry.phase) return {control: null, candidate: null};
      return {
        control: entry.control || null,
        candidate: entry.candidate || null,
      };
    }

    function displayIndexOf(entry) {
      const value = entry?.display_index ?? entry?.candidate?.display_index ?? entry?.control?.display_index;
      const n = Number(value);
      return Number.isFinite(n) && n > 0 ? n : null;
    }

    function taskNumberHtml(entry, cls="task-num") {
      const n = displayIndexOf(entry);
      return n ? `<span class="${cls}">Task ${esc(String(n))}</span>` : "";
    }

    function taskTitleHtml(entry, title) {
      return `<span class="t-name">${esc(title || "")}</span>`;
    }

    function detailTitleHtml(entry, title) {
      return `${taskNumberHtml(entry, "detail-task-num")}<span>${esc(title || "")}</span>`;
    }

    function armProgressFor(name, fallbackDone) {
      const p = data?.arm_progress?.[name] || {};
      const done = Number.isFinite(Number(p.completed_count)) ? Number(p.completed_count) : Number(fallbackDone || 0);
      const total = Number.isFinite(Number(p.scenario_count)) && Number(p.scenario_count) > 0 ? Number(p.scenario_count) : Number(data?.summary?.scenario_count || 0);
      return {
        done,
        total,
        status: p.status || (done && total && done >= total ? "complete" : "pending"),
      };
    }

    function progressText(p) {
      return `${p.done}/${p.total || "?"}`;
    }

    /* ── Top metrics ── */
    function renderTop() {
      const s = data?.summary || {};
      const model = data?.model_metadata?.agent?.resolved_model || data?.agent;
      document.getElementById("subtitle").textContent =
        [data?.mode, data?.phase, data?.status, model].filter(Boolean).join(" · ");
      document.querySelectorAll(".arm-btn").forEach(b => b.classList.toggle("active", b.dataset.arm === arm));

      let cards;
      if (arm === "paired") {
        const c = Number(s.balanced_control_mean_similarity), sg = Number(s.balanced_candidate_mean_similarity);
        const d = Number.isFinite(c) && Number.isFinite(sg) ? sg - c : null;
        const oc = s.balanced_control_mean_outcome_similarity;
        const os = s.balanced_candidate_mean_outcome_similarity;
        const od = present(oc) && present(os) ? Number(os) - Number(oc) : null;
        const lift = s.balanced_lift_percent;
        const balancedDone = s.balanced_completed || 0;
        const cp = armProgressFor("control", s.control_completed);
        const sp = armProgressFor("candidate", s.candidate_completed);
        cards = [
          {l:"Baseline Score", v:fmt(c), n:`${balancedDone} paired done`},
          {l:"SAGE Score", v:fmt(sg), n:`${balancedDone} paired done`},
          {l:"Delta", v:fmtD(d), n:d===null?"":d>0?"improvement":d<0?"regression":"no change", cls:d===null?"":d>0?"good":d<0?"bad":""},
          {l:"Lift", v:fmtPct(lift), n:"vs baseline", cls:present(lift) && Number(lift)>0?"good":present(lift) && Number(lift)<0?"bad":""},
          ...(od===null?[]:[{l:"Outcome Delta", v:fmtD(od), n:`${fmt(oc)} → ${fmt(os)}`, cls:od>0?"good":od<0?"bad":""}]),
          {l:"Tools", v:`${s.accepted_tools||0} born`, n:`${s.reuse_count||0} reuse · ${s.generated_tool_attempted_scenarios||0} attempts · ${s.generated_tool_called_scenarios||0} called · ${s.generated_tool_failed_scenarios||0} failed`},
          {l:"Baseline Progress", v:progressText(cp), n:cp.status},
          {l:"SAGE Progress", v:progressText(sp), n:sp.status},
        ];
      } else if (arm === "candidate") {
        const sp = armProgressFor("candidate", s.candidate_completed);
        cards = [
          {l:"SAGE Score", v:fmt(s.candidate_mean_similarity), n:`${s.candidate_completed||0} done`},
          {l:"Tools Born", v:`${s.accepted_tools||0}`, n:"accepted"},
          {l:"Reuse Calls", v:`${s.reuse_count||0}`, n:"generated tool uses"},
          {l:"Tool Attempts", v:`${s.generated_tool_attempted_scenarios||0}`, n:`${s.generated_tool_called_scenarios||0} called · ${s.generated_tool_failed_scenarios||0} failed`},
          {l:"Turns", v:`${s.current_turns||0}`, n:"total"},
          {l:"SAGE Progress", v:progressText(sp), n:sp.status},
        ];
      } else {
        const cp = armProgressFor("control", s.control_completed);
        cards = [
          {l:"Baseline Score", v:fmt(s.control_mean_similarity), n:`${s.control_completed||0} done`},
          {l:"Turns", v:`${s.current_turns||0}`, n:"total"},
          {l:"Baseline Progress", v:progressText(cp), n:cp.status},
          {l:"Exceptions", v:`${s.current_exceptions||0}`, n:"errors"},
          {l:"Status", v:esc(data?.status||"—"), n:esc(data?.phase||"")},
        ];
      }
      document.getElementById("topMetrics").innerHTML = cards.map(({l,v,n,cls}) =>
        `<div class="metric"><div class="mlabel">${esc(l)}</div><div class="mvalue ${cls||""}">${esc(v)}</div><div class="mnote">${esc(n||"")}</div></div>`
      ).join("");
    }

    /* ── Task list ── */
    function renderList() {
      const list = entries(), cur = current();
      document.getElementById("taskList").innerHTML = list.map(entry => {
        const sel = entry.id === cur?.id;
        if (!entry.phase) {
          /* Paired entry */
          const c = entry.control || {}, s = entry.candidate || {};
          const tools = s.generated_tools || [];
          const cStatus = c.status || "pending";
          const sStatus = s.status || "pending";
          return `<button class="task${sel?" selected":""}" data-id="${esc(entry.id)}">
            <div class="t-row">${taskNumberHtml(entry)}<span class="status-pair"><span class="pill ${esc(cStatus)}">B ${esc(cStatus)}</span><span class="pill ${esc(sStatus)}">S ${esc(sStatus)}</span></span></div>
            <div class="t-title">${taskTitleHtml(entry, entry.short_name||entry.scenario)}</div>
            <div class="score-pair">
              <span class="sc">B ${fmt(c.similarity)}</span>
              <span class="sc${tools.length?" hit":""}">S ${fmt(s.similarity)}</span>
            </div>
            ${tools.map(t=>`<span class="tbadge">${esc(t)}</span>`).join("")}
          </button>`;
        }
        /* Single-arm entry */
        return `<button class="task${sel?" selected":""}${entry.status==="running"?" running":""}" data-id="${esc(entry.id)}">
          <div class="t-row">${taskNumberHtml(entry)}<span class="pill ${esc(entry.status)}">${esc(entry.status)}</span></div>
          <div class="t-title">${taskTitleHtml(entry, entry.short_name||entry.scenario)}</div>
          <div class="t-score">score ${fmt(entry.similarity)} · ${entry.turn_count||"—"} turns</div>
          ${(entry.generated_tools||[]).map(t=>`<span class="tbadge">${esc(t)}</span>`).join("")}
        </button>`;
      }).join("");
    }

    /* ── Evaluation ── */
    function checkTone(check) {
      if (check.status === "matched" || check.status === "clear") return "good";
      if (check.status === "partial") return "warn";
      return "bad";
    }

    function checkStatusLabel(check) {
      if (check.kind === "forbidden") return check.status === "clear" ? "clear" : "triggered";
      if (check.status === "matched") return "matched";
      if (check.status === "partial") return "partial";
      if (check.status === "pending") return "pending";
      return "missed";
    }

    function evaluationSummaryHtml(ev) {
      const finalNote = ev.blocked_by_guardrail ? "guardrail triggered" : "scored from required checks";
      const guardrailState = ev.forbidden_total ? `${ev.forbidden_triggered}/${ev.forbidden_total} triggered` : "none";
      const requiredState = ev.required_total ? `${ev.required_passed}/${ev.required_total} matched` : "none";
      return `
        <div class="eval-top">
          <div class="eval-metric"><div class="sec-head">Final</div><div class="big">${esc(fmt(ev.final_score))}</div><div class="note">${esc(finalNote)}</div></div>
          <div class="eval-metric"><div class="sec-head">Required</div><div class="big">${esc(fmt(ev.required_score))}</div><div class="note">${esc(requiredState)}</div></div>
          <div class="eval-metric"><div class="sec-head">Forbidden</div><div class="big">${esc(fmt(ev.forbidden_score))}</div><div class="note">${esc(guardrailState)}</div></div>
        </div>`;
    }

    function singleEvaluationHtml(task) {
      const ev = task?.evaluation;
      if (!ev) return "<div class='empty'>No evaluation data captured</div>";
      const checks = ev.checks || [];
      if (!checks.length) {
        return `${evaluationSummaryHtml(ev)}<div class="empty">No check-level details were captured for this scenario</div>`;
      }
      return `
        ${evaluationSummaryHtml(ev)}
        <div class="eval-list">${checks.map(check => `
          <div class="check ${checkTone(check)}">
            <div class="check-head">
              <div class="check-kind">${esc(check.kind === "forbidden" ? `Forbidden ${check.index}` : `Required ${check.index}`)}</div>
              <div class="check-label">${esc(check.label || "")}</div>
              <div class="check-score">${esc(checkStatusLabel(check))}${check.score !== null && check.score !== undefined ? ` · ${fmt(check.score)}` : ""}</div>
            </div>
            <div class="check-grid">
              <div class="check-col">
                <div class="check-col-head">Model Provided</div>
                ${(check.observed || []).map(line => `<div class="check-line observed">${esc(line)}</div>`).join("")}
              </div>
              <div class="check-col">
                <div class="check-col-head">${check.kind === "forbidden" ? "Should Avoid" : "Correct Answer"}</div>
                ${(check.expected || []).map(line => `<div class="check-line expected">${esc(line)}</div>`).join("")}
              </div>
            </div>
          </div>`).join("")}
        </div>`;
    }

    function renderEvaluation(task) {
      document.getElementById("milestones").innerHTML = singleEvaluationHtml(task);
    }

    function dedupe(lines) {
      const out = [];
      (lines || []).forEach(line => {
        if (line && !out.includes(line)) out.push(line);
      });
      return out;
    }

    function pairedRunSummaryHtml(label, task) {
      if (!task) {
        return `<div class="paired-run-card missing">
          <div class="paired-run-head"><div class="paired-run-title">${esc(label)}</div><div class="paired-run-status">missing</div></div>
          <div class="pair-cell empty-mini">No run data loaded for this arm</div>
        </div>`;
      }
      const ev = task.evaluation;
      if (!ev) {
        return `<div class="paired-run-card">
          <div class="paired-run-head"><div class="paired-run-title">${esc(label)}</div><div class="paired-run-status">${esc(task.status || "pending")}</div></div>
          <div class="pair-cell empty-mini">No evaluation data captured</div>
        </div>`;
      }
      const requiredState = ev.required_total ? `${ev.required_passed}/${ev.required_total}` : "0/0";
      const forbiddenState = ev.forbidden_total ? `${ev.forbidden_triggered}/${ev.forbidden_total}` : "0/0";
      return `<div class="paired-run-card">
        <div class="paired-run-head">
          <div class="paired-run-title">${esc(label)}</div>
          <div class="paired-run-status">${esc(task.status || "pending")} · ${esc(String(task.turn_count ?? "—"))} turns</div>
        </div>
        <div class="paired-run-metrics">
          <div class="paired-mini"><div class="mlabel">Final</div><div class="mvalue">${esc(fmt(ev.final_score))}</div><div class="mnote">${ev.blocked_by_guardrail ? "guardrail" : "score"}</div></div>
          <div class="paired-mini"><div class="mlabel">Required</div><div class="mvalue">${esc(fmt(ev.required_score))}</div><div class="mnote">${esc(requiredState)}</div></div>
          <div class="paired-mini"><div class="mlabel">Forbidden</div><div class="mvalue">${esc(fmt(ev.forbidden_score))}</div><div class="mnote">${esc(forbiddenState)}</div></div>
        </div>
      </div>`;
    }

    function pairedEvaluationHtml(entry) {
      const {control, candidate} = pairedTasks(entry);
      if (!control && !candidate) return "<div class='empty'>No paired evaluation data captured</div>";
      const controlChecks = control?.evaluation?.checks || [];
      const candidateChecks = candidate?.evaluation?.checks || [];
      const checkMap = new Map();
      controlChecks.forEach(check => {
        checkMap.set(`${check.kind}:${check.index}`, {ref: check, control: check, candidate: null});
      });
      candidateChecks.forEach(check => {
        const key = `${check.kind}:${check.index}`;
        const current = checkMap.get(key) || {ref: check, control: null, candidate: null};
        current.ref = current.ref || check;
        current.candidate = check;
        checkMap.set(key, current);
      });
      const rows = Array.from(checkMap.values()).sort((a, b) => {
        const aKind = a.ref?.kind === "forbidden" ? 1 : 0;
        const bKind = b.ref?.kind === "forbidden" ? 1 : 0;
        return aKind - bKind || (a.ref?.index || 0) - (b.ref?.index || 0);
      });
      const checksHtml = rows.length ? rows.map(row => {
        const ref = row.ref || row.control || row.candidate || {};
        const targetLines = dedupe([...(row.control?.expected || []), ...(row.candidate?.expected || [])]);
        const rowTone = row.candidate ? checkTone(row.candidate) : row.control ? checkTone(row.control) : "bad";
        return `<div class="paired-check ${rowTone}">
          <div class="paired-check-head">
            <div class="check-kind">${esc(ref.kind === "forbidden" ? `Forbidden ${ref.index}` : `Required ${ref.index}`)}</div>
            <div class="check-label">${esc(ref.label || "")}</div>
          </div>
          <div class="paired-check-grid">
            <div class="pair-cell">
              <div class="check-col-head">Baseline</div>
              ${row.control ? `<div class="pair-status ${checkTone(row.control)}">${esc(checkStatusLabel(row.control))}${row.control.score !== null && row.control.score !== undefined ? ` · ${fmt(row.control.score)}` : ""}</div>` : `<div class="empty-mini">No check captured</div>`}
              ${row.control ? (row.control.observed || []).map(line => `<div class="check-line observed">${esc(line)}</div>`).join("") : ""}
            </div>
            <div class="pair-cell">
              <div class="check-col-head">SAGE</div>
              ${row.candidate ? `<div class="pair-status ${checkTone(row.candidate)}">${esc(checkStatusLabel(row.candidate))}${row.candidate.score !== null && row.candidate.score !== undefined ? ` · ${fmt(row.candidate.score)}` : ""}</div>` : `<div class="empty-mini">No check captured</div>`}
              ${row.candidate ? (row.candidate.observed || []).map(line => `<div class="check-line observed">${esc(line)}</div>`).join("") : ""}
            </div>
            <div class="pair-cell">
              <div class="check-col-head">${ref.kind === "forbidden" ? "Should Avoid" : "Correct Answer"}</div>
              ${(targetLines.length ? targetLines : ["No check target captured"]).map(line => `<div class="check-line expected">${esc(line)}</div>`).join("")}
            </div>
          </div>
        </div>`;
      }).join("") : `<div class="empty">No check-level details were captured for this scenario</div>`;
      return `
        <div class="paired-eval-top">
          ${pairedRunSummaryHtml("Baseline", control)}
          ${pairedRunSummaryHtml("SAGE", candidate)}
        </div>
        <div class="paired-check-list">${checksHtml}</div>`;
    }

    /* ── Detail head ── */
    function renderDetail() {
      const entry = current(), task = taskOf(entry);
      const dh = document.getElementById("detailHead");

      if (entry && !entry.phase) {
        const {control, candidate} = pairedTasks(entry);
        if (!control && !candidate) {
          dh.innerHTML = `<div class="d-title">${detailTitleHtml(entry, entry.scenario||"")}</div><div class="empty waiting">No paired run data loaded yet</div>`;
          document.getElementById("milestones").innerHTML = "";
          return;
        }
        const c = control || {}, s = candidate || {};
        const d = (c.similarity!=null&&s.similarity!=null) ? Number(s.similarity)-Number(c.similarity) : null;
        const od = (present(c.outcome_similarity)&&present(s.outcome_similarity)) ? Number(s.outcome_similarity)-Number(c.outcome_similarity) : null;
        const dc = d===null?"":d>0?"good":d<0?"bad":"";
        const cats = dedupe([...(c.categories || []), ...(s.categories || [])]);
        dh.innerHTML = `
          <div class="d-title">${detailTitleHtml(entry, entry.short_name||entry.scenario)}</div>
          <div class="comparison">
            <div class="cmp"><div class="mlabel">Baseline</div><div class="cv">${fmt(c.similarity)}</div>${present(c.outcome_similarity)?`<div class="tiny">outcome ${fmt(c.outcome_similarity)}</div>`:""}</div>
            <div class="cmp-sep">→</div>
            <div class="cmp sage"><div class="mlabel">SAGE</div><div class="cv">${fmt(s.similarity)}</div>
              ${present(s.outcome_similarity)?`<div class="tiny">outcome ${fmt(s.outcome_similarity)}</div>`:""}
              ${(s.generated_tools||[]).map(t=>`<span class="tbadge">⚡ ${esc(t)}</span>`).join("")}
            </div>
            ${d!==null?`<div class="cmp ${dc}"><div class="mlabel">Δ</div><div class="cv">${fmtD(d)}</div>${od!==null?`<div class="tiny">outcome ${fmtD(od)}</div>`:""}</div>`:""}
          </div>
          <div class="tags">
            ${cats.map(c=>`<span class="pill">${esc(c)}</span>`).join("")}
            <span class="pill">baseline ${esc(c.status || "pending")}</span>
            <span class="pill">sage ${esc(s.status || "pending")}</span>
            <span class="pill">baseline ${esc(String(c.turn_count ?? "—"))} turns</span>
            <span class="pill">sage ${esc(String(s.turn_count ?? "—"))} turns</span>
          </div>`;
        document.getElementById("milestones").innerHTML = pairedEvaluationHtml(entry);
        return;
      }

      if (!task) {
        dh.innerHTML = "<div class='empty'>Select a task from the list</div>";
        document.getElementById("milestones").innerHTML = "";
        return;
      }

      const o = task.outcome || {};
      const sim = task.similarity ?? o.similarity;
      const scoreClass = Number.isFinite(Number(sim)) ? (Number(sim) >= .999 ? "good" : "bad") : "";
      const cats = (task.categories||[]).map(c=>`<span class="pill">${esc(c)}</span>`).join("");
      const outcome = present(task.outcome_similarity) ? `<span class="pill">outcome ${fmt(task.outcome_similarity)}</span>` : "";
      dh.innerHTML = `
        <div class="d-title">${detailTitleHtml(task, task.short_name||task.scenario)}</div>
        <div class="tags">${cats}<span class="pill ${scoreClass}">score ${fmt(sim)}</span>${outcome}<span class="pill">${task.turn_count||"—"} turns</span></div>`;

      renderEvaluation(task);
    }

    function messageHtml(m) {
      return `<div class="msg ${m.role}${m.uses_generated_tool?" uses-tool":""}">
        <div class="bubble">
          <div class="msg-lbl">${esc((m.index+1)+" · "+m.label)}</div>
          ${(m.generated_tools||[]).map(t=>`<span class="tbadge">⚡ ${esc(t)}</span>`).join("")}
          <pre>${esc(m.content||"[empty]")}</pre>
        </div>
      </div>`;
    }

    function pairedChatLaneHtml(label, task, emptyMessage) {
      const status = task?.status || "pending";
      const turnText = task ? `${task.turn_count ?? "—"} turns` : "";
      const body = task?.messages?.length
        ? task.messages.map(messageHtml).join("")
        : `<div class="empty-mini">${esc(emptyMessage)}</div>`;
      return `<div class="chat-lane">
        <div class="chat-lane-head">
          <div class="paired-run-title">${esc(label)}</div>
          <div class="paired-run-status">${esc(status)}${turnText ? ` · ${esc(turnText)}` : ""}</div>
        </div>
        <div class="chat-lane-body">${body}</div>
      </div>`;
    }

    /* ── Chat ── */
    function renderChat() {
      const entry = current(), task = taskOf(entry);
      const chatEl = document.getElementById("chat"), wrap = document.getElementById("chatWrap");

      if (entry && !entry.phase) {
        const {control, candidate} = pairedTasks(entry);
        _chatFor = entry.id || null;
        chatEl.innerHTML = `<div class="paired-chat">
          ${pairedChatLaneHtml("Baseline", control, control ? "No messages recorded" : "Baseline run data is missing")}
          ${pairedChatLaneHtml("SAGE", candidate, candidate ? "No messages recorded" : "SAGE run data is missing")}
        </div>`;
        return;
      }

      const tid = task?.id || null, msgs = task?.messages || [];
      if (tid !== _chatFor) {
        chatEl.innerHTML = "";
        _renderedCount[tid] = 0;
        _chatFor = tid;
      }

      if (!msgs.length) {
        if (!chatEl.children.length) {
          if (task?.status === "running") {
            chatEl.innerHTML = "<div class='empty waiting'>Scenario running — messages will appear as turns complete…</div>";
          } else if (!task) {
            chatEl.innerHTML = "<div class='empty waiting'>No run data loaded yet</div>";
          } else {
            chatEl.innerHTML = "<div class='empty'>No messages recorded</div>";
          }
        }
        return;
      }

      chatEl.querySelector(".empty")?.remove();
      const prev = _renderedCount[tid] || 0;
      const newMsgs = msgs.slice(prev);
      if (!newMsgs.length) return;

      const atBottom = wrap.scrollHeight - wrap.scrollTop - wrap.clientHeight < 80;
      newMsgs.forEach(m => {
        chatEl.insertAdjacentHTML("beforeend", messageHtml(m));
      });
      _renderedCount[tid] = msgs.length;
      if (atBottom) wrap.scrollTop = wrap.scrollHeight;
    }

    function captureScroll() {
      const aside = document.querySelector("aside");
      const chat = document.getElementById("chatWrap");
      const head = document.getElementById("detailHead");
      const milestones = document.getElementById("milestones");
      return {
        taskId: current()?.id || null,
        asideTop: aside?.scrollTop || 0,
        chatTop: chat?.scrollTop || 0,
        chatAtBottom: chat ? chat.scrollHeight - chat.scrollTop - chat.clientHeight < 80 : true,
        headTop: head?.scrollTop || 0,
        milestonesTop: milestones?.scrollTop || 0,
      };
    }

    function restoreScroll(snapshot) {
      if (!snapshot || snapshot.taskId !== (current()?.id || null)) return;
      const aside = document.querySelector("aside");
      const chat = document.getElementById("chatWrap");
      const head = document.getElementById("detailHead");
      const milestones = document.getElementById("milestones");
      if (aside) aside.scrollTop = snapshot.asideTop;
      if (head) head.scrollTop = snapshot.headTop;
      if (milestones) milestones.scrollTop = snapshot.milestonesTop;
      if (chat && !snapshot.chatAtBottom) chat.scrollTop = snapshot.chatTop;
    }

    function render() {
      const scroll = captureScroll();
      renderTop();
      renderList();
      renderDetail();
      renderChat();
      requestAnimationFrame(() => restoreScroll(scroll));
    }

    async function refresh() {
      try {
        const r = await fetch(`task_focus_data.json?ts=${Date.now()}`, {cache:"no-store"});
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        data = await r.json();
        render();
      } catch(e) {
        document.getElementById("chat").innerHTML = `<div class="empty">Data unavailable: ${esc(e.message)}</div>`;
      }
    }

    document.querySelector(".arm-bar").addEventListener("click", e => {
      const b = e.target.closest("[data-arm]");
      if (!b || b.dataset.arm === arm) return;
      arm = b.dataset.arm; selectedId = null; _renderedCount = {}; _chatFor = null;
      render();
    });

    document.getElementById("taskList").addEventListener("click", e => {
      const b = e.target.closest("button.task");
      if (!b) return;
      if (b.dataset.id !== selectedId) { selectedId = b.dataset.id; _chatFor = null; }
      render();
    });

    refresh();
    setInterval(refresh, 3000);
  </script>
</body>
</html>
"""
