"""Static HTML shell for the H1/H2/H3/H4 pilot dashboard."""

HYPOTHESIS_PILOT_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>SAGE H1/H2/H3/H4 Pilot</title>
  <style>
    :root {
      --bg: #071016;
      --panel: #0d1922;
      --panel-2: #11222d;
      --line: #263946;
      --text: #e9f2f5;
      --muted: #9eb0ba;
      --cyan: #58d4dd;
      --green: #75d59b;
      --amber: #f3c870;
      --red: #ff8c8c;
      --blue: #91bfff;
      --shadow: 0 20px 55px rgba(0, 0, 0, .28);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--text);
      background:
        radial-gradient(circle at 8% -5%, rgba(38, 117, 130, .28), transparent 34rem),
        radial-gradient(circle at 100% 0%, rgba(41, 70, 112, .20), transparent 30rem),
        var(--bg);
      font: 15px/1.5 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    a { color: var(--cyan); text-underline-offset: 3px; }
    a:hover { color: #a1f3f5; }
    .wrap { width: min(1440px, calc(100% - 36px)); margin: 0 auto; padding: 34px 0 60px; }
    .topbar { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-bottom: 18px; }
    .eyebrow { color: var(--cyan); font-size: 12px; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; }
    .stamp { color: var(--muted); font-size: 12px; text-align: right; }
    .hero {
      border: 1px solid #30505d;
      border-radius: 18px;
      padding: clamp(22px, 4vw, 42px);
      background: linear-gradient(135deg, rgba(22, 55, 67, .86), rgba(12, 25, 34, .96));
      box-shadow: var(--shadow);
    }
    .hero-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 30px; }
    h1 { font-size: clamp(30px, 5vw, 56px); line-height: 1.03; margin: 7px 0 14px; letter-spacing: -.035em; }
    .subtitle { max-width: 870px; color: #c8d8de; font-size: 17px; margin: 0; }
    .warning {
      margin-top: 24px;
      padding: 14px 16px;
      border-left: 4px solid var(--amber);
      background: rgba(243, 200, 112, .08);
      color: #f5dfb2;
      border-radius: 5px 10px 10px 5px;
    }
    .status {
      flex: 0 0 auto;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 7px 12px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: .08em;
      text-transform: uppercase;
      white-space: nowrap;
    }
    .status.running { color: var(--blue); border-color: rgba(145, 191, 255, .55); background: rgba(145, 191, 255, .08); }
    .status.observed, .status.pass { color: var(--green); border-color: rgba(117, 213, 155, .5); background: rgba(117, 213, 155, .08); }
    .status.failed, .status.failed-integrity, .status.fail { color: var(--red); border-color: rgba(255, 140, 140, .52); background: rgba(255, 140, 140, .08); }
    .status.pending { color: var(--amber); border-color: rgba(243, 200, 112, .48); background: rgba(243, 200, 112, .07); }
    .progress { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin: 22px 0 0; }
    .progress div { border-top: 3px solid var(--line); padding-top: 8px; color: var(--muted); font-size: 12px; }
    .progress .done { border-color: var(--green); color: #ccebd6; }
    .progress .active { border-color: var(--blue); color: #cddfff; }
    .section-title { margin: 38px 0 13px; font-size: 13px; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }
    .hypotheses { display: grid; gap: 18px; }
    .card { border: 1px solid var(--line); border-radius: 15px; background: rgba(13, 25, 34, .94); box-shadow: var(--shadow); overflow: hidden; }
    .card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; padding: 22px 24px 18px; border-bottom: 1px solid var(--line); }
    .h-label { color: var(--cyan); font-weight: 850; font-size: 13px; letter-spacing: .12em; }
    .exploratory-badge { display: inline-block; margin-left: 8px; padding: 3px 8px; border: 1px solid rgba(243, 200, 112, .52); border-radius: 999px; background: rgba(243, 200, 112, .08); color: var(--amber); font-size: 10px; font-weight: 850; letter-spacing: .08em; text-transform: uppercase; vertical-align: 1px; }
    .card.exploratory { border-color: rgba(243, 200, 112, .42); }
    h2 { font-size: 21px; margin: 4px 0 0; letter-spacing: -.014em; }
    .card-body { padding: 22px 24px 24px; }
    .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(155px, 1fr)); gap: 10px; }
    .metric { min-height: 92px; padding: 14px; border: 1px solid #223540; border-radius: 11px; background: var(--panel-2); }
    .metric .label { color: var(--muted); font-size: 12px; margin-bottom: 7px; }
    .metric .value { font-size: 24px; line-height: 1.15; font-weight: 790; font-variant-numeric: tabular-nums; letter-spacing: -.02em; overflow-wrap: anywhere; }
    .metric .note { color: var(--muted); font-size: 11px; margin-top: 6px; }
    .subgrid { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(270px, .75fr); gap: 14px; margin-top: 14px; }
    .subpanel { border: 1px solid #223540; border-radius: 11px; padding: 15px; background: rgba(7, 16, 22, .42); }
    .subpanel h3 { margin: 0 0 10px; font-size: 13px; text-transform: uppercase; letter-spacing: .09em; color: var(--muted); }
    .descriptive-panel { margin-top: 14px; border-color: rgba(145, 191, 255, .42); background: rgba(32, 62, 93, .16); }
    .descriptive-badge { display: inline-block; margin-left: 7px; padding: 2px 7px; border: 1px solid rgba(145, 191, 255, .52); border-radius: 999px; color: var(--blue); font-size: 9px; font-weight: 850; letter-spacing: .07em; vertical-align: 1px; }
    .descriptive-note { margin: 10px 0 0; color: var(--muted); font-size: 12px; }
    [hidden] { display: none !important; }
    .integrity-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }
    .integrity-list li { display: grid; grid-template-columns: 18px 1fr; gap: 8px; align-items: start; color: #c9d8de; }
    .integrity-list .mark { font-weight: 900; }
    .integrity-list .ok { color: var(--green); }
    .integrity-list .bad { color: var(--red); }
    .integrity-list .wait { color: var(--amber); }
    .detail { color: var(--muted); font-size: 12px; display: block; margin-top: 2px; }
    .method { color: #c4d3d8; margin: 0; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; overflow-wrap: anywhere; }
    .artifacts { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 10px; }
    .artifact { border: 1px solid var(--line); border-radius: 11px; padding: 14px; background: var(--panel); }
    .artifact a { font-weight: 750; }
    .artifact .meta { margin-top: 5px; color: var(--muted); font-size: 11px; }
    .empty { color: var(--muted); font-style: italic; }
    footer { margin-top: 30px; padding-top: 18px; border-top: 1px solid var(--line); color: var(--muted); font-size: 12px; }
    @media (max-width: 760px) {
      .wrap { width: min(100% - 22px, 1440px); padding-top: 20px; }
      .hero-row, .card-head { display: block; }
      .status { display: inline-block; margin-top: 14px; }
      .progress { grid-template-columns: 1fr 1fr; }
      .subgrid { grid-template-columns: 1fr; }
      .stamp { display: none; }
    }
  </style>
</head>
<body>
  <main class="wrap">
    <div class="topbar">
      <div class="eyebrow">SAGE · Hypothesis pilot + exploratory alternate</div>
      <div class="stamp" id="generated-at"></div>
    </div>
    <section class="hero">
      <div class="hero-row">
        <div>
          <div class="eyebrow">PILOT — NOT CONFIRMATORY</div>
          <h1>H1 / H2 / H3 / H4 Pilot</h1>
          <p class="subtitle" id="pilot-subtitle"></p>
        </div>
        <div class="status pending" id="overall-status">Pending</div>
      </div>
      <div class="warning"><strong>Interpretation boundary.</strong> This dashboard reports one pilot execution. It can test the protocol and estimate direction and magnitude, but it cannot establish hypothesis support across independent registry replications. H4 is an exploratory alternate, not a confirmatory hypothesis result.</div>
      <div class="progress" id="progress"></div>
    </section>

    <div class="section-title">Pilot estimates</div>
    <section class="hypotheses">
      <article class="card" id="h1-card">
        <div class="card-head">
          <div><div class="h-label">H1</div><h2>Blind functional validity of accepted tools</h2></div>
          <div class="status pending" id="h1-status">Pending</div>
        </div>
        <div class="card-body">
          <div class="metrics" id="h1-metrics"></div>
          <div class="subgrid">
            <div class="subpanel"><h3>Interpretation</h3><p class="method" id="h1-method"></p></div>
            <div class="subpanel"><h3>Integrity</h3><ul class="integrity-list" id="h1-integrity"></ul></div>
          </div>
        </div>
      </article>

      <article class="card" id="h2-card">
        <div class="card-head">
          <div><div class="h-label">H2</div><h2>Ten independently evolved SAGE registries outperform control</h2></div>
          <div class="status pending" id="h2-status">Pending</div>
        </div>
        <div class="card-body">
          <div class="metrics" id="h2-metrics"></div>
          <div class="subgrid">
            <div class="subpanel"><h3>Estimand</h3><p class="method" id="h2-method"></p></div>
            <div class="subpanel"><h3>Integrity</h3><ul class="integrity-list" id="h2-integrity"></ul></div>
          </div>
          <div class="subpanel descriptive-panel" id="h2-canonical-panel" hidden><h3>ToolSandbox canonical similarity <span class="descriptive-badge">Descriptive only · not primary</span></h3><div class="metrics" id="h2-canonical-metrics"></div><p class="descriptive-note">Shown for context only. SAGE v9 mean outcome score remains the primary endpoint; canonical similarity is not used in the pilot gate.</p></div>
        </div>
      </article>

      <article class="card" id="h3-card">
        <div class="card-head">
          <div><div class="h-label">H3</div><h2>Randomized frozen-registry availability improves outcome over registry-masked SAGE</h2></div>
          <div class="status pending" id="h3-status">Pending</div>
        </div>
        <div class="card-body">
          <div class="metrics" id="h3-metrics"></div>
          <div class="subgrid">
            <div class="subpanel"><h3>Randomization and estimand</h3><p class="method" id="h3-method"></p><p class="mono" id="h3-allocation"></p></div>
            <div class="subpanel"><h3>Integrity</h3><ul class="integrity-list" id="h3-integrity"></ul></div>
          </div>
          <div class="subpanel descriptive-panel" id="h3-canonical-panel" hidden><h3>ToolSandbox canonical similarity <span class="descriptive-badge">Descriptive only · not primary</span></h3><div class="metrics" id="h3-canonical-metrics"></div><p class="descriptive-note">Shown for context only. SAGE v9 mean outcome score remains the primary endpoint; canonical similarity is not used in the pilot gate.</p></div>
        </div>
      </article>

      <article class="card exploratory" id="h4-card">
        <div class="card-head">
          <div><div class="h-label">H4 <span class="exploratory-badge">Exploratory alternate</span></div><h2>Frozen registry built on randomized disjoint discovery half improves mean outcome over registry-masked SAGE on held-out half</h2></div>
          <div class="status pending" id="h4-status">Pending</div>
        </div>
        <div class="card-body">
          <div class="metrics" id="h4-metrics"></div>
          <div class="subgrid">
            <div class="subpanel"><h3>Disjoint split and estimand</h3><p class="method" id="h4-method"></p><p class="mono" id="h4-split"></p></div>
            <div class="subpanel"><h3>Integrity</h3><ul class="integrity-list" id="h4-integrity"></ul></div>
          </div>
          <div class="subpanel descriptive-panel" id="h4-canonical-panel" hidden><h3>ToolSandbox canonical similarity <span class="descriptive-badge">Descriptive only · not primary</span></h3><div class="metrics" id="h4-canonical-metrics"></div><p class="descriptive-note">Shown for context only. SAGE v9 mean outcome score remains the primary endpoint; canonical similarity is not used in the pilot gate.</p></div>
        </div>
      </article>
    </section>

    <div class="section-title">Preserved evidence</div>
    <section class="artifacts" id="artifacts"></section>
    <footer id="footer"></footer>
  </main>
  <script id="pilot-data" type="application/json">__PILOT_DATA__</script>
  <script>
    (() => {
      const data = JSON.parse(document.getElementById('pilot-data').textContent);
      const q = (id) => document.getElementById(id);
      const finite = (x) => typeof x === 'number' && Number.isFinite(x);
      const score = (x) => finite(x) ? x.toFixed(3) : '—';
      const signed = (x) => finite(x) ? `${x > 0 ? '+' : ''}${x.toFixed(3)}` : '—';
      const pct = (x, sign=false) => finite(x) ? `${sign && x > 0 ? '+' : ''}${(100 * x).toFixed(1)}%` : '—';
      const count = (x) => Number.isInteger(x) ? x.toLocaleString() : '—';
      const ci = (x) => Array.isArray(x) && finite(x[0]) && finite(x[1]) ? `[${signed(x[0])}, ${signed(x[1])}]` : '—';
      const pval = (x) => !finite(x) ? '—' : x < .001 ? 'p < .001' : `p = ${x.toFixed(3).replace(/^0/, '')}`;
      const words = (x) => String(x || 'pending').toLowerCase().replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
      const esc = (x) => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
      const statusLabel = (raw, integrity) => {
        if (integrity === 'fail') return 'Failed integrity';
        const value = String(raw || 'pending').toLowerCase().replaceAll('_', '-');
        if (['complete', 'completed', 'observed', 'pass'].includes(value)) return 'Observed';
        if (value === 'failed-integrity') return 'Failed integrity';
        if (value === 'failed') return 'Failed';
        if (value === 'running') return 'Running';
        return 'Pending';
      };
      const setStatus = (id, raw, integrity) => {
        const node = q(id);
        const label = statusLabel(raw, integrity);
        node.textContent = label;
        node.className = `status ${label.toLowerCase().replaceAll(' ', '-')}`;
      };
      const metric = (label, value, note='') => `<div class="metric"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div>${note ? `<div class="note">${esc(note)}</div>` : ''}</div>`;
      const renderIntegrity = (id, integrity={}) => {
        const checks = Array.isArray(integrity.checks) ? integrity.checks : [];
        q(id).innerHTML = checks.length ? checks.map(item => {
          const status = item.status || 'pending';
          const symbol = status === 'pass' ? '✓' : status === 'fail' ? '×' : '·';
          const klass = status === 'pass' ? 'ok' : status === 'fail' ? 'bad' : 'wait';
          return `<li><span class="mark ${klass}">${symbol}</span><span>${esc(item.label)}${item.detail ? `<span class="detail">${esc(item.detail)}</span>` : ''}</span></li>`;
        }).join('') : '<li class="empty">Integrity checks not yet recorded.</li>';
      };
      const renderCanonical = (panelId, metricsId, canonical, config) => {
        if (!canonical || canonical.role !== 'descriptive_not_primary') return;
        q(panelId).hidden = false;
        q(metricsId).innerHTML = [
          metric(config.treatmentLabel, score(canonical[config.treatmentKey]), config.treatmentNote),
          metric(config.baselineLabel, score(canonical[config.baselineKey]), config.baselineNote),
          metric('Descriptive mean difference', signed(canonical.mean_difference), config.differenceNote)
        ].join('');
      };

      q('generated-at').textContent = `Rendered ${data.generated_at || '—'}`;
      q('pilot-subtitle').textContent = `${data.pilot_id || 'Unnamed pilot'} · ${data.study_label || 'one complete run'}`;
      setStatus('overall-status', data.status, data.integrity_status);
      const stages = ['Protocol locked', 'Online build + control', 'Blind audit', 'Randomized frozen test', 'Exploratory split-half alternate'];
      const stage = Number.isInteger(data.progress_stage) ? data.progress_stage : 0;
      q('progress').innerHTML = stages.map((name, i) => `<div class="${i < stage ? 'done' : i === stage && data.status === 'running' ? 'active' : ''}">${i + 1}. ${name}</div>`).join('');

      const h1 = data.h1 || {};
      setStatus('h1-status', h1.status, h1.integrity?.status);
      q('h1-metrics').innerHTML = [
        metric('Blind cases passed', `${count(h1.blind_cases_passed)} / ${count(h1.blind_cases_total)}`, 'post-freeze cases only'),
        metric('Case-weighted pass rate', pct(h1.case_weighted_pass_rate)),
        metric('Tools evaluated', `${count(h1.evaluated_tools)} / ${count(h1.accepted_tools)}`, 'accepted frozen tools'),
        metric('Tool coverage', pct(h1.tool_coverage_rate)),
        metric('Tool-weighted pass rate', pct(h1.tool_weighted_pass_rate), 'each tool weighted equally'),
        metric('Exact two-sided 95% CP lower bound', pct(h1.clopper_pearson_lower_bound), 'tool-level; descriptive, not a gate'),
        metric('H1 pilot gate outcome', words(h1.pilot_gate_outcome), h1.pilot_gate_label || 'PENDING')
      ].join('');
      q('h1-method').textContent = h1.method_note || 'Post-freeze blind cases are evaluated without using these cases for generation, repair, or admission. Case-weighted and tool-weighted summaries are reported separately.';
      renderIntegrity('h1-integrity', h1.integrity);

      const h2 = data.h2 || {};
      setStatus('h2-status', h2.status, h2.integrity?.status);
      q('h2-metrics').innerHTML = [
        metric('Fresh control mean', score(h2.control_mean), 'mean outcome score'),
        metric('Integrated SAGE mean', score(h2.integrated_sage_mean), 'mean outcome score'),
        metric('Raw mean difference', signed(h2.mean_difference), 'SAGE − control'),
        metric('Relative lift', pct(h2.relative_lift, true), 'relative to control'),
        metric('95% two-way run/task CI', ci(h2.cluster_ci_95), 'mean score difference'),
        metric('Independent registry runs', count(h2.independent_registry_runs), `${count(h2.tasks)} matched task observations`),
        metric('Paper decision', h2.paper_decision ? words(h2.paper_decision) : words(h2.pilot_gate_outcome), h2.pilot_gate_label || 'PENDING')
      ].join('');
      q('h2-method').textContent = h2.method_note || 'The primary pilot estimand is the intention-to-treat difference in mean outcome score, integrated SAGE minus fresh control. The confidence interval clusters the benchmark variants by original task stem.';
      renderIntegrity('h2-integrity', h2.integrity);
      const h2Canonical = h2.descriptive_canonical_similarity;
      renderCanonical('h2-canonical-panel', 'h2-canonical-metrics', h2Canonical, {
        treatmentKey: 'integrated_sage_mean', treatmentLabel: 'Integrated SAGE canonical mean', treatmentNote: `${count(h2Canonical?.tasks)} task rows`,
        baselineKey: 'control_mean', baselineLabel: 'Control canonical mean', baselineNote: `${count(h2Canonical?.tasks)} task rows`,
        differenceNote: 'SAGE − control; descriptive only'
      });

      const h3 = data.h3 || {};
      setStatus('h3-status', h3.status, h3.integrity?.status);
      q('h3-metrics').innerHTML = [
        metric('Registry available mean', score(h3.registry_available_mean), 'assigned available'),
        metric('Registry masked mean', score(h3.registry_masked_mean), 'assigned masked'),
        metric('ITT mean difference', signed(h3.itt_mean_difference), 'available − masked'),
        metric('95% cluster CI', ci(h3.cluster_ci_95), `${count(h3.stem_clusters)} task-stem clusters`),
        metric('Randomization p-value', pval(h3.p_value), h3.p_value_note || 'restricted randomization test'),
        metric('Allocation', `${count(h3.available_tasks)} / ${count(h3.masked_tasks)}`, 'available / masked tasks'),
        metric('H3 pilot gate outcome', words(h3.pilot_gate_outcome), h3.pilot_gate_label || 'PENDING')
      ].join('');
      q('h3-method').textContent = h3.method_note || 'The intention-to-treat contrast follows the frozen allocation, whether or not an assigned-available task ultimately called a generated tool. Inference preserves task-stem clustering.';
      const alloc = h3.allocation || {};
      q('h3-allocation').textContent = `seed: ${alloc.seed ?? '—'} · sha256: ${alloc.sha256 || '—'}${alloc.stratification ? ` · ${alloc.stratification}` : ''}`;
      renderIntegrity('h3-integrity', h3.integrity);
      const h3Canonical = h3.descriptive_canonical_similarity;
      renderCanonical('h3-canonical-panel', 'h3-canonical-metrics', h3Canonical, {
        treatmentKey: 'registry_available_mean', treatmentLabel: 'Available canonical mean', treatmentNote: `${count(h3Canonical?.available_tasks)} assigned tasks`,
        baselineKey: 'registry_masked_mean', baselineLabel: 'Masked canonical mean', baselineNote: `${count(h3Canonical?.masked_tasks)} assigned tasks`,
        differenceNote: 'available − masked; descriptive only'
      });

      const h4 = data.h4 || {};
      setStatus('h4-status', h4.status, h4.integrity?.status);
      q('h4-metrics').innerHTML = [
        metric('Discovery partition', `${count(h4.discovery_tasks)} tasks`, `${count(h4.discovery_stems)} task stems`),
        metric('Held-out partition', `${count(h4.heldout_tasks)} tasks`, `${count(h4.heldout_stems)} task stems`),
        metric('Frozen registry available mean', score(h4.frozen_available_mean), 'held-out half'),
        metric('Registry masked mean', score(h4.registry_masked_mean), 'held-out half'),
        metric('Raw mean difference', signed(h4.mean_difference), 'available − masked'),
        metric('Relative lift', pct(h4.relative_lift, true), 'relative to registry-masked'),
        metric('95% cluster CI', ci(h4.cluster_ci_95), `${count(h4.heldout_stems)} held-out task-stem clusters`),
        metric('H4 pilot gate outcome', words(h4.pilot_gate_outcome), h4.pilot_gate_label || 'PENDING')
      ].join('');
      q('h4-method').textContent = h4.method_note || 'Exploratory alternate: the registry is built only on the randomized discovery half, frozen, and evaluated against registry-masked SAGE only on the disjoint held-out half. This estimate is pilot evidence, not a confirmatory result.';
      q('h4-split').textContent = `split seed: ${h4.split_seed ?? '—'} · sha256: ${h4.split_sha256 || '—'}`;
      renderIntegrity('h4-integrity', h4.integrity);
      const h4Canonical = h4.descriptive_canonical_similarity;
      renderCanonical('h4-canonical-panel', 'h4-canonical-metrics', h4Canonical, {
        treatmentKey: 'registry_available_mean', treatmentLabel: 'Available canonical mean', treatmentNote: `${count(h4Canonical?.available_tasks)} held-out tasks`,
        baselineKey: 'registry_masked_mean', baselineLabel: 'Masked canonical mean', baselineNote: `${count(h4Canonical?.masked_tasks)} held-out tasks`,
        differenceNote: 'available − masked; descriptive only'
      });

      const artifacts = Array.isArray(data.artifacts) ? data.artifacts : [];
      q('artifacts').innerHTML = artifacts.length ? artifacts.map(item => `<div class="artifact"><a href="${esc(item.href)}">${esc(item.label)}</a><div class="meta">${esc(item.kind || 'artifact')}${item.exists === false ? ' · expected / not yet present' : ''}</div></div>`).join('') : '<div class="empty">No artifact links recorded yet.</div>';
      q('footer').textContent = `Schema ${data.schema_version || '—'} · source manifest ${data.source_manifest_sha256 || '—'} · statuses describe this pilot only; they are not confirmatory hypothesis decisions.`;
    })();
  </script>
</body>
</html>
"""
