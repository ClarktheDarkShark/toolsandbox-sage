# SAGE CyberGym/tau3 Generalization Handoff - 2026-05-29

This is the turnover file for the next agent continuing SAGE portability and
generalization work on CyberGym and tau3. It is intentionally operational. Read
this file first, keep it open while working, and append working notes to the log
section at the end so state is easy to recover after interruptions.

This work is experimental engineering, not protected final-claim evidence.

## Primary Objective

Continue improving SAGE so it generalizes beyond ToolSandbox while preserving
the core behavior that made the ToolSandbox 250/500 runs successful:

1. Detect deterministic gaps from visible task context and visible failure
   traces.
2. Generate real reusable helper tools, preferably Python callables or
   equivalent structured helpers that the host loop can actually call.
3. Validate and repair helpers before trusting them.
4. Store accepted helpers in a registry with hashes, metadata, routing
   criteria, use counts, success counts, regressions, and lifecycle status.
5. Route a small relevant helper bundle into later tasks.
6. Track whether gains are generated-tool-attributed, not merely stochastic LLM
   variance.
7. Retire, quarantine, or refine helpers that are called repeatedly without
   paired gains or that cause regressions.

The goal is not to hand-code CyberGym or tau3 answers. The goal is to discover
what helper classes actually improve those environments, then back-port the
successful mechanism into environment-general SAGE behavior.

It is acceptable, and encouraged, to create dataset-specific prototype tools at
first to learn what works. Those prototypes are diagnostics. The final
framework changes should be general: e.g., "visible record disambiguation,"
"exact action-argument repair," "public execution-search candidate planning,"
"source-family candidate-budget allocation," "failure-turn replay validation,"
not "solve tau3 task 18" or "solve arvo:62707."

## Non-Negotiable Research Constraints

- Do not inspect hidden labels, expected answers, reference PoCs, private scorer
  internals, hidden benchmark facts, or fixed-side behavior during candidate
  discovery.
- Do not encode scenario IDs, expected answers, task-specific strings, or known
  successful payloads into generated helpers.
- Do not count force-calls, hardwired calls, prompt-only guidance, or random
  paired variance as SAGE tool-generation evidence.
- A gain counts as SAGE-generated-tool evidence only when an accepted generated
  helper was visible and called, bridged into an action, or used in a same-task
  retry that directly constrained the successful outcome.
- SAGE arms must be live and fresh. Do not use a SAGE task cache as evidence.
- Baseline/control arms should use valid per-task caches whenever available.
  Fresh baseline records should be written back to the cache.
- Always open the dashboard at run start unless debugging a non-run command.
- Monitor the dashboard and console while runs proceed. Stop early only for
  clear safety, leakage, infrastructure, or off-track reasons, then repair and
  rerun.
- Use `gpt-4o-mini` for live task actors unless a specific ablation says
  otherwise. Use stronger GPT-5 only for helper generation and helper repair
  when candidate quality is the tested bottleneck.
- Runtime exceptions and helper side-effect incidents should remain zero.

## Environment Setup

Repository root:

```bash
cd "/Users/christopherclark/Library/Mobile Documents/com~apple~CloudDocs/_Chris_Docs/Coding/toolsandbox-sage"
```

Always set Python path:

```bash
export PYTHONPATH=src:.
```

OpenAI API key:

- Do not print the key.
- First check whether it is already exported:

```bash
python - <<'PY'
import os
print("OPENAI_API_KEY present:", bool(os.environ.get("OPENAI_API_KEY")))
PY
```

- If it is absent, the key has previously been available from a sibling env
  file. Try:

```bash
set -a
source ../Hey_Alfredv2/.env
set +a
python - <<'PY'
import os
print("OPENAI_API_KEY present:", bool(os.environ.get("OPENAI_API_KEY")))
PY
```

- If that path is unavailable, locate local env files without printing secrets:

```bash
find .. -maxdepth 4 -name ".env" -print
```

Basic API sanity check, still without printing secrets:

```bash
python - <<'PY'
from openai import OpenAI
client = OpenAI()
models = client.models.list()
print("openai_ok", bool(models.data))
PY
```

Process hygiene:

- This thread has repeatedly hit the 60 open exec-process warning. Before
  launching long runs, check for stale run processes:

```bash
ps -axo pid,etime,command | rg "run_(tau3|cybergym|sage_protocol)|prepare_toolsandbox|python scripts" | sed -n '1,120p'
```

- Do not kill active runs blindly. If a process is clearly stale, record the PID
  and reason in the working log before terminating it.

## Current Best ToolSandbox Reference

ToolSandbox remains the known-good SAGE implementation and the benchmark for
what "full SAGE" means.

Key evidence:

- `outputs/self_evolving_sage/formal500_live_generation_v71_clean_repro/online_build_500_20260514_204356`
  - 500 tasks.
  - Canonical score: `0.656799 -> 0.854188`, lift `+30.05%`.
  - Outcome score: `0.494746 -> 0.880845`, lift `+78.04%`.
  - Empty starting registry.
  - 16 accepted live-born helpers.
  - 297 naturally called generated-tool scenarios.
  - 0 generated-tool failures.
  - 0 runtime exceptions.
  - Caveat: one strict helper-contract side-effect preservation near miss on a
    read-only reminder-search task, with no state mutation.

- `outputs/self_evolving_sage/formal500_live_generation_v70_jit_birth_retry_repair/online_build_500_20260513_174839`
  - 500 tasks.
  - Canonical score: `0.656799 -> 0.827506`, lift `+25.99%`.
  - Outcome score: `0.494746 -> 0.872782`, lift `+76.41%`.
  - 0 runtime/helper incidents.

Chapter 3 current working setup:

- `docs/sage_protocol/chapter3_sage_methodology_working_setup.md`

Whole-dataset ToolSandbox preflight:

```bash
PYTHONPATH=src:. python scripts/prepare_toolsandbox_full_self_evolving_run.py
```

Current preflight status from 2026-05-29:

- Manifest: `docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`
- Split: `full_benchmark`
- Scenario count: `1032`
- Registry starts empty: `true`
- Baseline cache: `688 cached / 344 fresh`
- RapidAPI cache present, hash recorded
- SAGE task cache off
- OpenAI response cache disabled
- Execution/user model: `gpt-4o-mini`
- Generation/repair model: `gpt-5`
- Policy: `self-evolving-praxis`

Do not modify protected final evidence while doing CyberGym/tau3 work.

## Core Files To Know

General SAGE package and import-agent work:

- `src/sage_agent/interfaces.py`
- `src/sage_agent/controller.py`
- `src/sage_agent/import_agent.py`
- `src/sage_agent/import_runner.py`
- `src/sage_agent/gap_mining.py`
- `src/sage_agent/generators.py`
- `src/sage_agent/registry.py`
- `src/sage_agent/validation.py`
- `src/sage_agent/dashboard.py`
- `src/sage_agent/adapters/cybergym_live.py`

ToolSandbox high-lift runtime:

- `scripts/run_sage_protocol.py`
- `scripts/prepare_toolsandbox_full_self_evolving_run.py`
- `src/sage_ts/adapters/sage_run_adapter.py`
- `src/sage_ts/runtime/toolsandbox_integration.py`
- `src/sage_ts/generation/tool_generator.py`
- `src/sage_ts/validation/`
- `src/sage_ts/registry/manifest.py`
- `src/sage_ts/adapters/openai_toolsandbox_roles.py`
- `src/sage_ts/dashboard/task_compare_template.py`

CyberGym runners:

- `scripts/run_cybergym_live_batched_sage.py`
- `scripts/run_cybergym_live_sage.py`

tau3 runners and diagnostics:

- `scripts/run_tau3_sageagent_parity.py`
- `scripts/run_sage_official_live.py`
- `scripts/prototype_tau3_candidate_tools.py`
- `artifacts/tau3_manual_helper_registry_v1/sage_registry.json`

Audit and methodology:

- `scripts/audit_sage_import_readiness.py`
- `docs/sage_protocol/cybergym_public_execution_search_gap_closure_20260523.md`
- `docs/sage_protocol/tau3_sageagent_parity_repair_20260527.md`
- `docs/sage_protocol/tau3_final_attempt_framework_report_20260528.md`
- `docs/sage_protocol/current_state.md`
- `docs/sage_protocol/run_ledger.md`
- `README.md`

## What We Learned: ToolSandbox

The ToolSandbox lift did not come from generic prompting. It came from deep
integration:

- SAGE could see task text, visible tool outputs, and failures.
- SAGE generated real helper tools, not only policy notes.
- Helpers were side-effect-free and final-action-ready where possible.
- The actor saw a small relevant helper bundle.
- Same-task retry allowed newly born helpers to fix the task that exposed the
  gap.
- The bridge policy made helper outputs actionable without turning helpers into
  side-effect executors.
- Contribution tracking separated actual helper-driven wins from random paired
  variance.
- Weak helpers were refined, parked, or replaced.

When porting SAGE to a new dataset, the key question is not "can SAGE write a
prompt?" It is:

Can the host loop expose generated helpers as callable deterministic support at
the point where the actor makes the next action or answer decision?

If not, SAGE will often degrade into prompt guidance, and the measured lift will
not be comparable to the ToolSandbox result.

## What We Learned: CyberGym

CyberGym is a source/execution-search benchmark. Early SAGE could detect weak
candidates, birth helpers, and route helpers, but the helper class was too
shallow. Static string planners were not enough.

Successful direction:

- Generate a `public_local_search_candidate_planner`-style helper.
- Let the adapter run bounded public vulnerable-side execution search using
  visible public task artifacts, generated probes, public seeds, and public
  runtime/source cues.
- Submit only discovered candidate artifacts through the normal official
  `submit.sh` verifier.
- Enable fixed-side verification for scoring.
- Cache public task materialization and Docker images to avoid repeated large
  downloads. This is environment setup cache, not task-answer cache.

Important CyberGym results:

- `outputs/cybergym_live_sage/cybergym_public_search_validcache_first20_20260523`
  - Baseline `1/20`, SAGE `7/20`.
  - Tools born/accepted/reused: `19 / 19 / 221`.
  - Integrity issues: `0`.
  - Fixed-side verification enabled.

- `outputs/cybergym_live_sage/cybergym_public_search_validcache_first40_20260523`
  - Baseline `1/40`, SAGE `10/40`.
  - Baseline cache: `40 cached / 0 fresh`.
  - Tools born/accepted/reused: `21 / 21 / 399`.
  - Integrity issues: `0`.
  - Fixed-side verification enabled.

- `outputs/cybergym_live_sage/cybergym_source_guided_budget_first40_v2_20260523`
  - Baseline `1/40`, SAGE `12/40`.
  - Source-guided candidate-budget allocation improved first40 by +2 wins.
  - Baseline cache: `40 cached / 0 fresh`.
  - Integrity issues: `0`.
  - Fixed-side verification enabled.

- `outputs/cybergym_live_sage/cybergym_source_family_offset20_20260523`
  - Baseline `0/20`, SAGE `5/20`.
  - Improved harder offset20 from prior `3/20` to `5/20`.
  - Showed later-window evolution continued after source-family specialist
    birth path.

Remaining CyberGym blocker:

- SAGE improves CyberGym, but later/harder tasks still flatten.
- The bottleneck is source-family specialist quality and candidate-budget
  allocation, not basic helper visibility.
- Need better family-specific candidate strategies discovered from visible
  source/runtime cues, while remaining label-free.

CyberGym caution:

- Avoid downloading tasks/images repeatedly. Use `--task-dir-cache-root`,
  `--skip-existing-images`, and do not clear images unless disk pressure
  requires it.
- `--require-existing-images` is diagnostic speed mode only; do not use it for
  formal evidence because it changes sampling by local image availability.
- Fixed-side verification must be enabled for credible CyberGym scoring.

## What We Learned: tau3

tau3 is similar to ToolSandbox in that it is a tool-use/dialogue benchmark, but
the host harness owns the simulator, official tools, and dialogue loop. This
exposed a SAGE portability gap.

Initial import-agent mode mostly injected prompt guidance. That was not full
SAGE. Prompt guidance can perturb the actor and can hurt outcomes. It does not
prove SAGE tool generation.

Major tau3 findings:

- `SAGEImportAgent` needs to expose generated helpers as actual callable tools
  or equivalent structured helper calls, not just system-prompt text.
- Broad "policy/planning" helpers over-route and are often not the real gap.
- The strongest tau3 helper classes are medium-grain deterministic tools:
  visible record selectors, option selectors, exact action-argument builders,
  payment/total repair tools, policy guards, entitlement lookups, no-op/repeat
  side-effect guards, and final-answer aggregation helpers.
- tau3 needs failure-turn replay validation: run a candidate helper on the exact
  transcript slice before the failed action and verify it produces the right
  next action, abstain decision, or read-only lookup.
- Newly accepted helpers should be shadowed until they drive a same-task retry
  win or pass replay validation.
- Any helper-attributed regression should quarantine the helper until repaired.

Important tau3 runs and outcomes:

- `outputs/sage_official_live/import_agent_tau3_airline_official40_20260524`
  and related import-mode runs:
  - Showed the runner could execute tau3, but prompt/helper guidance was weak.
  - One run had baseline `16/40`, SAGE `12/40`: SAGE hurt because helpers were
    mostly prompt policy guidance.

- `outputs/sage_official_live/tau3_sageagent_guarded_retained20_20260527_01`
  - Valid tasks: `18`.
  - Baseline successes: `7`.
  - SAGE successes: `9`.
  - Generated-tool-attributed gains: `3`.
  - Generated-tool-attributed regressions: `1`.
  - Tools born: `24`, accepted: `4`, reused: `304`.
  - Birth-task retries: `5`, retry successes: `2`.
  - Meaningful but not scale-ready because of the regression.

- `outputs/sage_official_live/tau3_sageagent_fresh20_option_repair_v6_20260527_01`
  - Requested tasks: `20`.
  - Valid non-infra tasks: `15`.
  - Baseline successes: `6`.
  - SAGE successes: `8`.
  - Generated-tool-attributed gains: `1`.
  - Generated-tool-attributed regressions: `0`.
  - Tools born: `28`, accepted: `17`, reused: `252`.
  - Cleaner contribution signal but not enough to scale.

- `outputs/sage_official_live/tau3_sageagent_episode_compiler20_v29_lifecycle_rescue_20260527_01`
  - SAGE `7/20` vs baseline `8/20`.
  - Created many helpers but 0/10 retry successes.
  - Diagnosed missing deterministic control points and weak validation.

- `outputs/sage_official_live/tau3_sageagent_replay_helpers20_v17_positive_route_floor_20260528_01`
  - Early stopped; route floor alone did not recover stable lift.

- Best complete recent tau3 run noted in the final framework report:
  - `tau3_sageagent_replay_helpers20_v4_bounded_20260528_01`
  - 20 tasks, baseline `8/20`, SAGE `9/20`, three gains, two regressions.
  - Not stable enough for 40/100.

Manual tau3 prototype tools:

- File: `scripts/prototype_tau3_candidate_tools.py`
- Registry: `artifacts/tau3_manual_helper_registry_v1/sage_registry.json`
- Prototypes:
  1. `repair_booking_payment_and_passengers`
  2. `plan_cabin_change_batch_from_visible_records`
  3. `summarize_refunds_from_visible_tool_results`
  4. `guard_cancellation_policy_from_visible_record`

These passed replay checks and exposed what useful tau3 helpers should look
like. They should be treated as diagnostic examples, not final answer maps.

Remaining tau3 blocker:

- SAGE can birth, accept, route, and execute helpers.
- It still generates too many broad helpers and not enough exact
  failure-turn, final-action-ready tools.
- The host loop can be over-perturbed by weak helper exposure.
- Candidate acceptance lacks sufficiently strict replay validation around
  exact next action, abstain, and state-transition behavior.

## Recommended Next Technical Direction

Focus on a general "failure-turn replay and action-spec helper" lifecycle.

1. Mine failures into concrete, medium-grain gap types:
   - visible option selection
   - visible record disambiguation
   - exact payment/total repair
   - required-field completion
   - action precondition guard
   - no-op/repeated side-effect guard
   - entitlement/policy lookup from visible records
   - final-answer aggregation from visible tool results
   - source-family candidate strategy for CyberGym-like tasks

2. Generate helpers that return structured outputs:
   - `status`: `ready | abstain | missing_info | unsafe | not_applicable`
   - `reason`
   - `next_action`: host tool name and arguments, only when safe and visible
   - `selected_record_ids`
   - `required_fields`
   - `confidence`
   - `do_not_call_reason` when abstaining

3. Validate before acceptance:
   - static compile/schema check
   - side-effect-free check
   - negative/minefield checks
   - exact failure-turn replay
   - one synthetic state-transition check where relevant
   - host-action argument check, if helper emits an action spec

4. Route conservatively:
   - expose no helper when no candidate has strong contextual match
   - avoid defaulting to broad policy/planning helpers
   - cap active helpers per task
   - require positive contribution or replay proof before high routing priority

5. Lifecycle:
   - shadow new helpers until they pass replay or birth-task retry
   - promote after helper-attributed gains
   - refine after bad args, no-op, or unhelpful output
   - quarantine after helper-attributed regression
   - park helpers that see repeated called failures without paired gains

6. Contribution accounting:
   - report baseline failed/SAGE succeeded and helper was causally used
   - separately report baseline succeeded/SAGE failed and helper was present
   - do not count prompt-only guidance as callable-helper evidence

This should be implemented in SAGE core where possible:

- `src/sage_agent/gap_mining.py`
- `src/sage_agent/generators.py`
- `src/sage_agent/validation.py`
- `src/sage_agent/controller.py`
- `src/sage_agent/import_agent.py`
- host runners only for wiring official tool loops

## Run Progression Expectations

Do not jump directly to 500. Use progressive gates.

1. 20-task diagnostic:
   - Goal: positive generated-helper-attributed gains.
   - Runtime exceptions: 0.
   - Helper-attributed regressions: ideally 0; if nonzero, diagnose and repair.
   - Dashboard must show helper births, calls, uses, outcomes, and task traces.

2. 60-task validation:
   - Required before claiming the approach is more than a tiny slice win.
   - Must show gains continue after early tasks, not only first batch.
   - Must report helper lifecycle: kept/refined/parked/quarantined.

3. 250-task scale probe:
   - Only after 60 is positive and safe.
   - Use cached baselines where available.
   - Candidate/SAGE arms fresh.
   - Monitor batch curves for flattening.

4. 500-task validation:
   - Only after 250 is positive and tool-attributed.
   - Must preserve research constraints and safety.
   - Must include statistical analysis and contribution tables if used as
     Chapter 4 evidence.

If an idea fails at 20, do not abandon after one run unless it has a decisive
safety/leakage failure. Diagnose routing, visibility, schema, callability,
helper output, and exact failure-turn usefulness. Force-call or hardwire only
for diagnosis, never for evidence.

## CyberGym Recommended Commands

Start with the current strongest general CyberGym setup.

20-task diagnostic:

```bash
PYTHONPATH=src:. python scripts/run_cybergym_live_batched_sage.py \
  --limit 20 \
  --batch-size 4 \
  --difficulty level1 \
  --model gpt-4o-mini \
  --llm-timeout 90 \
  --submit-timeout 180 \
  --fixed-side-check \
  --baseline llm \
  --baseline-cache use-if-eligible \
  --generator openai \
  --candidate-prescreen vulnerable-search \
  --candidate-strategy source-first \
  --max-candidates 8 \
  --baseline-max-candidates 8 \
  --adaptive-reserve-candidates 8 \
  --max-new-tools 24 \
  --max-new-tools-per-task 3 \
  --max-refinements 2 \
  --max-gap-signals-per-task 4 \
  --no-defer-birth-task-retries \
  --task-dir-cache-root artifacts/cybergym_task_dir_cache \
  --baseline-cache-path artifacts/cybergym_baseline_cache.json \
  --output-root outputs/cybergym_live_sage \
  --work-root outputs/cybergym_live_sage/work_current \
  --dashboard-port 62630 \
  --skip-existing-images \
  --no-clear-images \
  --run-id cybergym_generalization20_$(date +%Y%m%d_%H%M%S)
```

60-task validation:

```bash
PYTHONPATH=src:. python scripts/run_cybergym_live_batched_sage.py \
  --limit 60 \
  --batch-size 4 \
  --difficulty level1 \
  --model gpt-4o-mini \
  --llm-timeout 90 \
  --submit-timeout 180 \
  --fixed-side-check \
  --baseline llm \
  --baseline-cache use-if-eligible \
  --generator openai \
  --candidate-prescreen vulnerable-search \
  --candidate-strategy source-first \
  --max-candidates 8 \
  --baseline-max-candidates 8 \
  --adaptive-reserve-candidates 8 \
  --max-new-tools 48 \
  --max-new-tools-per-task 3 \
  --max-refinements 2 \
  --max-gap-signals-per-task 4 \
  --task-dir-cache-root artifacts/cybergym_task_dir_cache \
  --baseline-cache-path artifacts/cybergym_baseline_cache.json \
  --output-root outputs/cybergym_live_sage \
  --work-root outputs/cybergym_live_sage/work_current \
  --dashboard-port 62630 \
  --skip-existing-images \
  --no-clear-images \
  --run-id cybergym_generalization60_$(date +%Y%m%d_%H%M%S)
```

If source-family hard tasks flatten, run ablations on `--candidate-strategy`
with `context-aware`, `wide-diverse`, and `source-first`, but change one major
factor at a time and record it.

250/500:

- Use the same shape as 60.
- Increase `--limit 250` or `--limit 500`.
- Run only after positive 60-task evidence.
- Avoid `--require-existing-images` for evidence runs.
- Keep `--fixed-side-check`.

## tau3 Recommended Commands

Use the full SAGEAgent parity runner, not prompt-only import mode.

20-task diagnostic with stronger generation model:

```bash
PYTHONPATH=src:. python scripts/run_tau3_sageagent_parity.py \
  --samples 20 \
  --domain airline \
  --model gpt-4o-mini \
  --generation-model gpt-5 \
  --baseline-cache use-if-eligible \
  --dashboard-port 62630 \
  --max-helpers 32 \
  --active-helpers 5 \
  --max-tools-per-task 4 \
  --max-same-task-retries 1 \
  --max-refinements 2 \
  --transient-retries 2 \
  --generation-timeout-sec 120 \
  --source-guided-host-action-generation \
  --run-id tau3_generalization20_$(date +%Y%m%d_%H%M%S)
```

If helper outputs are not reaching the actor as callable tools or structured
action specs, stop and fix integration before scaling. Prompt-only helper text
is not enough.

Optional ablations after a 20-task baseline diagnostic:

```bash
# More conservative: SAGE shadow/replay outputs only, no direct host actions.
PYTHONPATH=src:. python scripts/run_tau3_sageagent_parity.py \
  --samples 20 --domain airline --model gpt-4o-mini --generation-model gpt-5 \
  --baseline-cache use-if-eligible --dashboard-port 62630 \
  --max-helpers 32 --active-helpers 4 --max-tools-per-task 3 \
  --max-same-task-retries 1 --max-refinements 2 \
  --source-guided-host-action-generation \
  --run-id tau3_shadow_replay20_$(date +%Y%m%d_%H%M%S)

# Direct-action ablation: only if helpers are strict, replay-validated, and
# side-effect policy is clear.
PYTHONPATH=src:. python scripts/run_tau3_sageagent_parity.py \
  --samples 20 --domain airline --model gpt-4o-mini --generation-model gpt-5 \
  --baseline-cache use-if-eligible --dashboard-port 62630 \
  --max-helpers 32 --active-helpers 5 --max-tools-per-task 4 \
  --max-same-task-retries 1 --max-refinements 2 \
  --source-guided-host-action-generation --enable-direct-actions \
  --run-id tau3_direct_action20_$(date +%Y%m%d_%H%M%S)
```

60-task validation:

```bash
PYTHONPATH=src:. python scripts/run_tau3_sageagent_parity.py \
  --samples 60 \
  --domain airline \
  --model gpt-4o-mini \
  --generation-model gpt-5 \
  --baseline-cache use-if-eligible \
  --dashboard-port 62630 \
  --max-helpers 48 \
  --active-helpers 5 \
  --max-tools-per-task 4 \
  --max-same-task-retries 1 \
  --max-refinements 2 \
  --transient-retries 2 \
  --generation-timeout-sec 120 \
  --source-guided-host-action-generation \
  --run-id tau3_generalization60_$(date +%Y%m%d_%H%M%S)
```

Do not run tau3 250/500 until 60 shows positive generated-helper-attributed
gains and no unresolved helper-attributed regressions.

## ToolSandbox Maintenance Commands

Before declaring any general SAGE modification successful, verify ToolSandbox
did not regress.

Quick preflight:

```bash
PYTHONPATH=src:. python scripts/prepare_toolsandbox_full_self_evolving_run.py
```

Small maintenance run, using the proven policy. The sealed formal manifests in
`docs/sage_protocol/manifests/` currently expose `full_benchmark`; do not edit
those files. For a 60-task maintenance check, create a derived experimental
manifest under `artifacts/`:

```bash
python - <<'PY'
import json
from pathlib import Path
src = Path("docs/sage_protocol/manifests/v2_1_formal_500.json")
dst = Path("artifacts/self_evolving_sage/toolsandbox_maintenance60_manifest.json")
payload = json.loads(src.read_text())
full = payload["splits"]["full_benchmark"]
payload["splits"] = {"online_build_60": full[:60]}
payload["metadata"] = {
    **payload.get("metadata", {}),
    "derived_for": "ToolSandbox maintenance60 SAGE generalization check",
    "source_manifest": str(src),
    "source_split": "full_benchmark",
    "task_count": 60,
}
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(json.dumps(payload, indent=2) + "\n")
print(dst)
PY
```

Then run:

```bash
PYTHONPATH=src:. SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY=1 \
TOOLSANDBOX_RAPID_CACHE_MODE=read_only \
TOOLSANDBOX_RAPID_CACHE_PATH=".secrets/rapid_api_cache.json" \
python scripts/run_sage_protocol.py \
  --mode online_build_60 \
  --manifest artifacts/self_evolving_sage/toolsandbox_maintenance60_manifest.json \
  --registry-dir artifacts/self_evolving_sage/toolsandbox_maintenance60_registry \
  --sage-policy self-evolving-praxis \
  --agent gpt-4o-mini \
  --user gpt-4o-mini \
  --generation-model gpt-5 \
  --generation on \
  --disable-openai-response-cache \
  --cache-mode off \
  --control-cache use-if-eligible \
  --routing-evidence-mode disabled \
  --freeze-toolsandbox-clock \
  --dashboard-port 62624 \
  --output-root outputs/self_evolving_sage/toolsandbox_maintenance60 \
  --artifact-root artifacts/self_evolving_sage/toolsandbox_maintenance60_artifacts
```

## Dashboard Requirements

Every run should open a dashboard at start. If it does not:

1. Verify `--no-dashboard-open` is not set.
2. Verify the run wrote `dashboard/task_compare.html` or `dashboard/index.html`.
3. Start or reuse the local dashboard server if needed.
4. Record the dashboard URL in the working log.

Dashboards must show:

- environment name
- total/completed task count
- baseline score/success
- SAGE score/success
- score lift and outcome/task-completion lift
- tools born/accepted/reused/called
- generated-tool events per task
- full transaction or enough task trace to explain a gain/regression
- contribution attribution
- cache status for baseline controls

If dashboard data is incomplete, fix dashboard/export code before relying on
that run for decisions.

## Manual Prototype Policy

Manual prototypes are allowed for diagnosis. Use them aggressively when stuck.

Permitted:

- Inspect a handful of failed tasks and visible traces.
- Write candidate helper tools yourself.
- Run replay checks on visible transcript slices.
- Force-expose or force-call helpers on tiny diagnostics to test latent value.
- Use the result to define a general helper class and generator/validator
  requirement.

Not permitted as evidence:

- Hard-coding task IDs, labels, expected answers, reference PoCs, hidden facts,
  or successful payloads.
- Counting manual force-call success as promotion evidence.
- Scaling a manually seeded registry without clearly labeling it as seeded
  diagnostic evidence.

When a manual tool works, immediately answer:

1. What visible cues should have caused SAGE to identify this gap?
2. What helper schema should SAGE have generated?
3. What validation/replay test would have proven it before live use?
4. What routing features should expose it later?
5. What lifecycle metric should promote/refine/park it?

## Success Criteria

An approach is promising only if:

- It improves task completion/outcome over matched baseline.
- The improvement is generated-tool-attributed, not just random paired
  variance.
- Natural helper calls or structured helper bridges occur.
- Runtime exceptions are zero.
- Helper side-effect incidents are zero.
- No leakage or label-peeking occurs.
- No severe helper-attributed regressions remain unresolved.
- ToolSandbox maintenance remains strong.
- CyberGym/tau3 improvements are framed as general SAGE capabilities, not
  dataset-specific answer hacks.

Target progression:

- CyberGym: reproduce at least the `12/40` source-guided result, then improve
  the harder offset/later windows. Scale to 60, then 250/500 only after positive
  tool-attributed evidence.
- tau3: achieve a clean 20-task run with positive generated-helper-attributed
  lift and zero helper-attributed regressions. Then run 60. Do not scale to
  250/500 until 60 is clean.
- ToolSandbox: preserve high-lift behavior on 60 or 100 maintenance checks, then
  prepare whole-dataset execution through `online_build_full`.

## Validation Commands

Run after meaningful code changes:

```bash
python -m py_compile \
  src/sage_agent/controller.py \
  src/sage_agent/import_agent.py \
  src/sage_agent/gap_mining.py \
  src/sage_agent/generators.py \
  src/sage_agent/registry.py \
  src/sage_agent/validation.py \
  scripts/run_cybergym_live_batched_sage.py \
  scripts/run_tau3_sageagent_parity.py \
  scripts/run_sage_protocol.py
```

```bash
PYTHONPATH=src:. pytest tests/unit/test_sage_agent_standalone.py -q
```

Focused CyberGym tests:

```bash
PYTHONPATH=src:. pytest tests/unit/test_sage_agent_standalone.py -q \
  -k "public_local_search or source_family or public_search_budget or vulnerable_search or materialized_task_cache"
```

Repository hygiene:

```bash
git diff --check
```

Use `scripts/audit_sage_import_readiness.py` for import-agent evidence runs:

```bash
PYTHONPATH=src:. python scripts/audit_sage_import_readiness.py \
  --run-dir <RUN_DIR> \
  --require-attributed-gains
```

For tool-capable import harnesses:

```bash
PYTHONPATH=src:. python scripts/audit_sage_import_readiness.py \
  --run-dir <RUN_DIR> \
  --require-attributed-gains \
  --require-callable-tool-gains
```

## Where To Store Work For Easy Retrieval

Append every meaningful action to the working log at the end of this file.
Use this exact run-card shape:

```text
### Run Card - <timestamp> - <short name>

- Branch:
- Commit:
- Hypothesis:
- Environment:
- Command:
- Sample/window:
- Baseline cache:
- SAGE cache:
- Model:
- Generation model:
- Dashboard:
- Results:
- Generated tools born/accepted/reused/called:
- Tool-attributed gains:
- Tool-attributed regressions:
- Runtime/helper incidents:
- Leakage/safety notes:
- Decision: keep / refine / park / scale
- Next action:
```

Also update:

- `docs/sage_protocol/current_state.md`
- `docs/sage_protocol/run_ledger.md`
- A focused report if a phase reaches a meaningful stopping point:
  - `docs/sage_protocol/cybergym_<topic>_<date>.md`
  - `docs/sage_protocol/tau3_<topic>_<date>.md`

Artifacts should remain under:

- `outputs/cybergym_live_sage/`
- `outputs/sage_official_live/`
- `outputs/self_evolving_sage/`
- `artifacts/cybergym_*`
- `artifacts/tau3_*`
- `artifacts/self_evolving_sage/`

Do not delete prior artifacts. Use timestamped run IDs.

## Current Recommended Next Action

Start with a focused tau3 repair because it is the clearest portability blocker
for "ToolSandbox-like but host-owned loop" environments.

1. Review the manual tools in `scripts/prototype_tau3_candidate_tools.py`.
2. Implement or strengthen failure-turn replay validation in SAGE core, not only
   tau3 runner code.
3. Ensure generated helpers are concrete action-spec helpers, not broad policy
   notes.
4. Run tau3 20 with `gpt-4o-mini` actor and `gpt-5` generation.
5. Require generated-tool-attributed gains and no helper-attributed regressions
   before scaling to tau3 60.
6. Run CyberGym 20/40 or 60 to confirm CyberGym gains are preserved.
7. Run ToolSandbox maintenance 60 to confirm no regression.

If tau3 remains negative after this, write a blocker report explaining whether
the blocker is host-loop integration, helper candidate quality, replay
validation, routing, lifecycle, official scorer feedback, or insufficient
visible information.

## Working Log

Append below this line. Keep entries brief but complete.

### Run Card - 2026-05-29T18:35:39-04:00 - tau3 action-spec validator first attempt

- Branch: `codex/sage-standalone-agent`
- Commit: `33d7369` plus uncommitted experimental changes
- Hypothesis: stricter core validation for action-spec helpers will force tau3 helpers to be concrete and final-action-ready.
- Environment: tau3-current-release airline via `scripts/run_tau3_sageagent_parity.py`
- Command: `PYTHONPATH=src:. python scripts/run_tau3_sageagent_parity.py --samples 20 --domain airline --model gpt-4o-mini --generation-model gpt-5 --baseline-cache use-if-eligible --dashboard-port 62630 --max-helpers 32 --active-helpers 5 --max-tools-per-task 4 --max-same-task-retries 1 --max-refinements 2 --transient-retries 2 --generation-timeout-sec 120 --source-guided-host-action-generation --run-id tau3_generalization20_20260529_183539`
- Sample/window: requested 20, stopped after 2 SAGE task records
- Baseline cache: `8/20` cached successes loaded from existing tau3 baseline cache
- SAGE cache: off/fresh SAGE helper generation
- Model: `gpt-4o-mini`
- Generation model: `gpt-5`
- Dashboard: `outputs/sage_official_live/tau3_generalization20_20260529_183539/dashboard/task_compare.html`
- Results: partial SAGE `1/2`; stopped because validator rejected a valid read-only policy lookup with unresolved side-effect preconditions
- Generated tools born/accepted/reused/called: `1 / 0 / 0 / 0`
- Tool-attributed gains: `0` in partial slice
- Tool-attributed regressions: `0` in partial slice
- Runtime/helper incidents: `0`; agent terminated PID `62497` after diagnosing validator false positive
- Leakage/safety notes: no hidden labels/scorer internals inspected
- Decision: refine
- Next action: allow read-only evidence-gathering actions with `missing_preconditions`, rerun tests, then rerun tau3 diagnostic

### Run Card - 2026-05-29T18:41:12-04:00 - tau3 action-spec validator v2 partial

- Branch: `codex/sage-standalone-agent`
- Commit: `33d7369` plus uncommitted experimental changes
- Hypothesis: action-spec validation plus `next_action` bridge support will produce cleaner generated-helper-attributed tau3 gains.
- Environment: tau3-current-release airline via `scripts/run_tau3_sageagent_parity.py`
- Command: `PYTHONPATH=src:. python scripts/run_tau3_sageagent_parity.py --samples 20 --domain airline --model gpt-4o-mini --generation-model gpt-5 --baseline-cache use-if-eligible --dashboard-port 62630 --max-helpers 32 --active-helpers 5 --max-tools-per-task 4 --max-same-task-retries 1 --max-refinements 2 --transient-retries 2 --generation-timeout-sec 120 --source-guided-host-action-generation --run-id tau3_generalization20_action_spec_v2_20260529_184112`
- Sample/window: requested 20, stopped after 7 SAGE task records
- Baseline cache: `8/20` cached successes loaded from existing tau3 baseline cache
- SAGE cache: off/fresh SAGE helper generation
- Model: `gpt-4o-mini`
- Generation model: `gpt-5`
- Dashboard: `outputs/sage_official_live/tau3_generalization20_action_spec_v2_20260529_184112/dashboard/task_compare.html`
- Results: partial SAGE controller success `3/7`; one same-task retry success; stopped due suspected runtime/generation stall before 20-task gate
- Generated tools born/accepted/reused/called: `14 / 11 / 31 / 16`
- Tool-attributed gains: approximate partial `1` (`tau3:airline:1`)
- Tool-attributed regressions: approximate partial `2` (`tau3:airline:2`, `tau3:airline:4`)
- Runtime/helper incidents: `0`; agent terminated PID `65863`; error log `artifacts/tau3_errors_20260529_185534.log`
- Leakage/safety notes: no hidden labels/scorer internals inspected; partial run is diagnostic only, not evidence
- Decision: refine
- Next action: add stricter replay/shadow routing and a tau3 gap-generation budget cap before rerunning tau3 20

### Run Card - 2026-05-29T22:08:35-04:00 - tau3 shadow safe bridge diagnostic

- Branch: `codex/sage-standalone-agent`
- Commit: `33d7369` plus uncommitted experimental changes
- Hypothesis: conservative shadow/replay helper execution with action-spec validation, stale-intent gates, bounded helper execution, and fixed contribution accounting will produce clean callable-helper-attributed tau3 gains.
- Environment: tau3-current-release airline via `scripts/run_tau3_sageagent_parity.py`
- Command: `PYTHONPATH=src:. python scripts/run_tau3_sageagent_parity.py --samples 20 --domain airline --model gpt-4o-mini --generation-model gpt-5 --baseline-cache use-if-eligible --dashboard-port 62630 --max-helpers 32 --active-helpers 4 --max-tools-per-task 3 --max-same-task-retries 1 --max-refinements 2 --max-gap-signals-per-task 4 --transient-retries 2 --tau2-timeout-sec 120 --generation-timeout-sec 120 --source-guided-host-action-generation --run-id tau3_shadow_safe20_20260529_220835`
- Sample/window: requested 20, stopped after 8 SAGE task records
- Baseline cache: `8/20` cached successes loaded from existing tau3 baseline cache
- SAGE cache: off/fresh SAGE helper generation
- Model: `gpt-4o-mini`
- Generation model: `gpt-5`
- Dashboard: `outputs/sage_official_live/tau3_shadow_safe20_20260529_220835/dashboard/task_compare.html`
- Results: partial final SAGE `6/8` vs baseline `6/8`; one final gain (`tau3:airline:1`) and one final regression (`tau3:airline:2`) in the partial slice, but the run is off-track because shadow helper outputs were executed/logged while hidden from the actor when direct actions were disabled.
- Generated tools born/accepted/reused/called: `8 / 8 / 35 / observed helper calls on deferred retries and task 7`
- Tool-attributed gains: not counted; bridge flag bug means helper outputs were not reliably visible/actionable to the actor.
- Tool-attributed regressions: `0` confirmed helper-attributed; task 2 final regression is not counted because helper outputs did not reach the initial actor decision.
- Runtime/helper incidents: `0`; terminating PID `26277` intentionally after logging off-track bridge bug.
- Leakage/safety notes: no hidden labels/scorer internals inspected; partial diagnostic only, not evidence.
- Decision: refine
- Next action: patch shadow-mode bridge so structured helper preflight outputs are shown to the actor by default, preserving direct-only shadow as an explicit ablation only.

### Run Card - 2026-05-29T22:21:24-04:00 - tau3 fixed shadow bridge partial

- Branch: `codex/sage-standalone-agent`
- Commit: `33d7369` plus uncommitted experimental changes
- Hypothesis: fixed shadow-mode preflight output injection will turn logged helper calls into actionable actor constraints and recover clean tau3 gains.
- Environment: tau3-current-release airline via `scripts/run_tau3_sageagent_parity.py`
- Command: `PYTHONPATH=src:. python scripts/run_tau3_sageagent_parity.py --samples 20 --domain airline --model gpt-4o-mini --generation-model gpt-5 --baseline-cache use-if-eligible --dashboard-port 62630 --max-helpers 32 --active-helpers 4 --max-tools-per-task 3 --max-same-task-retries 1 --max-refinements 2 --max-gap-signals-per-task 4 --transient-retries 2 --tau2-timeout-sec 120 --generation-timeout-sec 120 --source-guided-host-action-generation --run-id tau3_shadow_bridge20_20260529_222124`
- Sample/window: requested 20, stopped after 7 SAGE task records
- Baseline cache: `8/20` cached successes loaded from existing tau3 baseline cache
- SAGE cache: off/fresh SAGE helper generation
- Model: `gpt-4o-mini`
- Generation model: `gpt-5`
- Dashboard: `outputs/sage_official_live/tau3_shadow_bridge20_20260529_222124/dashboard/task_compare.html`
- Results: partial final SAGE `6/7` vs baseline `6/7`; one helper-called final gain (`tau3:airline:1`), no final helper-attributed regression, but the run is invalid for evidence because task 6 hit `tau2_runner_error:IndexError`.
- Generated tools born/accepted/reused/called: `7 / 7 / 31 / helper calls on tasks 1, 2, 3`
- Tool-attributed gains: diagnostic `1` candidate (`tau3:airline:1`) because generated helpers were called and preflight outputs reached the actor on the successful retry.
- Tool-attributed regressions: `0`
- Runtime/helper incidents: official runner `IndexError` on task 6; terminating PIDs `33023` and `38290` intentionally after logging the infrastructure retry gap.
- Leakage/safety notes: no hidden labels/scorer internals inspected; partial diagnostic only, not evidence.
- Decision: refine
- Next action: classify tau2 official runner exceptions as retryable infrastructure failures so `--transient-retries` is honored, then rerun the fixed bridge diagnostic.

### Run Card - 2026-05-29T22:31:22-04:00 - tau3 fixed bridge with runner retry partial

- Branch: `codex/sage-standalone-agent`
- Commit: `33d7369` plus uncommitted experimental changes
- Hypothesis: fixed shadow preflight plus retryable official runner exceptions will produce clean callable-helper-attributed tau3 gains.
- Environment: tau3-current-release airline via `scripts/run_tau3_sageagent_parity.py`
- Command: `PYTHONPATH=src:. python scripts/run_tau3_sageagent_parity.py --samples 20 --domain airline --model gpt-4o-mini --generation-model gpt-5 --baseline-cache use-if-eligible --dashboard-port 62630 --max-helpers 32 --active-helpers 4 --max-tools-per-task 3 --max-same-task-retries 1 --max-refinements 2 --max-gap-signals-per-task 4 --transient-retries 2 --tau2-timeout-sec 120 --generation-timeout-sec 120 --source-guided-host-action-generation --run-id tau3_shadow_bridge_retry20_20260529_223122`
- Sample/window: requested 20, stopped after 7 SAGE task records
- Baseline cache: `8/20` cached successes loaded from existing tau3 baseline cache
- SAGE cache: off/fresh SAGE helper generation
- Model: `gpt-4o-mini`
- Generation model: `gpt-5`
- Dashboard: `outputs/sage_official_live/tau3_shadow_bridge_retry20_20260529_223122/dashboard/task_compare.html`
- Results: partial final SAGE `6/7` vs baseline `6/7`; one helper-called final gain (`tau3:airline:1`), one helper-caused regression (`tau3:airline:4`).
- Generated tools born/accepted/reused/called: `5 / 5 / 24 / helper calls on tasks 1, 3, 4, 5`
- Tool-attributed gains: diagnostic `1` candidate (`tau3:airline:1`).
- Tool-attributed regressions: `1`; `prepare_visible_cancellation_refund_action_args` converted a past airline-canceled flight compensation request into `cancel_reservation(KC18K6)`, then safety guard escalated before compensation.
- Runtime/helper incidents: one retryable tau2 runner exception was retried; terminating PID `38827` intentionally after logging helper-caused regression.
- Leakage/safety notes: no hidden labels/scorer internals inspected; visible transcript only.
- Decision: refine
- Next action: add active cancellation/refund intent gating and sanitizer checks so cancellation action helpers do not route or authorize side effects for past-cancellation compensation requests.

### Run Card - 2026-05-29T22:42:18-04:00 - tau3 shadow bridge active cancellation gate

- Branch: `codex/sage-standalone-agent`
- Commit: `33d7369` plus uncommitted experimental changes
- Hypothesis: fixed shadow preflight plus active cancellation/refund intent gating will preserve helper-callable gains while preventing the compensation-as-cancellation regression.
- Environment: tau3-current-release airline via `scripts/run_tau3_sageagent_parity.py`
- Command: `PYTHONPATH=src:. python scripts/run_tau3_sageagent_parity.py --samples 20 --domain airline --model gpt-4o-mini --generation-model gpt-5 --baseline-cache use-if-eligible --dashboard-port 62630 --max-helpers 32 --active-helpers 4 --max-tools-per-task 3 --max-same-task-retries 1 --max-refinements 2 --max-gap-signals-per-task 4 --transient-retries 2 --tau2-timeout-sec 120 --generation-timeout-sec 120 --source-guided-host-action-generation --run-id tau3_shadow_cancel_gate20_20260529_224218`
- Sample/window: 20 airline tasks, first-20 order
- Baseline cache: `20/20` cached; baseline successes `8/20`
- SAGE cache: off/fresh SAGE helper generation
- Model: `gpt-4o-mini`
- Generation model: `gpt-5`
- Dashboard: `outputs/sage_official_live/tau3_shadow_cancel_gate20_20260529_224218/dashboard/task_compare.html`
- Results: final SAGE `11/20` vs baseline `8/20`; initial SAGE `9/20`; birth-task retry successes `4/8`; integrity issues `0`.
- Generated tools born/accepted/reused/called: `12 / 12 / 120 / 120 initial helper calls plus deferred retry calls`
- Tool-attributed gains: strict callable-helper gain `1` (`tau3:airline:11`, record lookup plus reservation-change helper emitted actionable lookup/update specs on successful retry). Additional final gains `tau3:airline:1`, `10`, and `13` were not counted as strict generated-tool evidence because they were stochastic or only weakly constrained by non-actionable helper outputs.
- Tool-attributed regressions: `0`; final regression `tau3:airline:2` had no helper calls/actionable helper outputs.
- Runtime/helper incidents: no final runtime/helper incidents; several tau2 official runner exceptions were retried as transient infrastructure errors.
- Leakage/safety notes: no hidden labels/scorer internals inspected. Cancellation helper no longer caused the past-cancellation compensation regression; active intent gate and sanitizer blocked side-effect authorization.
- Decision: keep / refine
- Next action: preserve fixed shadow preflight, retryable official-runner exceptions, helper timeout, contribution accounting, and active cancellation intent gate. Improve candidate quality for payment/option selection and reduce noisy record lookup over-calls before tau3 60.

### Run Card - 2026-05-29T23:12:49-04:00 - tau3 hard route gate ablation

- Branch: `codex/sage-standalone-agent`
- Commit: `33d7369` plus uncommitted experimental changes
- Hypothesis: hard-suppressing cancellation/refund helpers unless the current turn contains explicit cancel/refund intent will reduce noisy calls without hurting lift.
- Environment: tau3-current-release airline via `scripts/run_tau3_sageagent_parity.py`
- Command: `PYTHONPATH=src:. python scripts/run_tau3_sageagent_parity.py --samples 20 --domain airline --model gpt-4o-mini --generation-model gpt-5 --baseline-cache use-if-eligible --dashboard-port 62630 --max-helpers 32 --active-helpers 4 --max-tools-per-task 3 --max-same-task-retries 1 --max-refinements 2 --max-gap-signals-per-task 4 --transient-retries 2 --tau2-timeout-sec 120 --generation-timeout-sec 120 --source-guided-host-action-generation --run-id tau3_shadow_route_gate20_20260529_231249`
- Sample/window: 20 airline tasks, first-20 order
- Baseline cache: `20/20` cached; baseline successes `8/20`
- SAGE cache: off/fresh SAGE helper generation
- Model: `gpt-4o-mini`
- Generation model: `gpt-5`
- Dashboard: `outputs/sage_official_live/tau3_shadow_route_gate20_20260529_231249/dashboard/task_compare.html`
- Results: final SAGE `7/20` vs baseline `8/20`; tools born/accepted/reused `6 / 6 / 29`; birth-task retry successes `2/3`; integrity issues `0`.
- Generated tools born/accepted/reused/called: `6 / 6 / 29 / 29`
- Tool-attributed gains: `0` strict; final gains `tau3:airline:1` and `13` had no helper calls.
- Tool-attributed regressions: `0`; regressions were no-helper/stochastic.
- Runtime/helper incidents: no final helper/runtime incidents; transient tau2 runner exceptions were retried.
- Leakage/safety notes: no hidden labels/scorer internals inspected.
- Decision: park
- Next action: revert hard route skip. Keep softer past-compensation cancellation suppression plus active action sanitizer. Do not use hard route-gate result for scaling.

### Run Card - 2026-05-29T23:38:20-04:00 - tau3 wide helper pool ablation

- Branch: `codex/sage-standalone-agent`
- Commit: `33d7369` plus uncommitted experimental changes
- Hypothesis: carrying a wider retained helper pool (`12`) while exposing only `4` active helpers per turn will make payment/option helpers available when late transcript failures occur.
- Environment: tau3-current-release airline via `scripts/run_tau3_sageagent_parity.py`
- Command: `PYTHONPATH=src:. python scripts/run_tau3_sageagent_parity.py --samples 20 --domain airline --model gpt-4o-mini --generation-model gpt-5 --baseline-cache use-if-eligible --dashboard-port 62630 --max-helpers 32 --helper-pool-size 12 --active-helpers 4 --max-tools-per-task 3 --max-same-task-retries 1 --max-refinements 2 --max-gap-signals-per-task 4 --transient-retries 2 --tau2-timeout-sec 120 --generation-timeout-sec 120 --source-guided-host-action-generation --run-id tau3_shadow_pool12_20_20260529_233820`
- Sample/window: 20 airline tasks, first-20 order
- Baseline cache: `20/20` cached; baseline successes `8/20`
- SAGE cache: off/fresh SAGE helper generation
- Model: `gpt-4o-mini`
- Generation model: `gpt-5`
- Dashboard: `outputs/sage_official_live/tau3_shadow_pool12_20_20260529_233820/dashboard/task_compare.html`
- Results: final SAGE `10/20` vs baseline `8/20`; tools born/accepted/reused `13 / 13 / 78`; birth-task retry successes `1/7`; integrity issues `0`.
- Generated tools born/accepted/reused/called: `13 / 13 / 78 / 78`
- Tool-attributed gains: strict `0`; payment helper availability improved (`prepare_visible_booking_payment_action_args` called `13` times) but it produced `0` actionable outputs.
- Tool-attributed regressions: `0`; final regressions were no-helper/stochastic.
- Runtime/helper incidents: no final helper/runtime incidents; transient tau2 runner exceptions were retried.
- Leakage/safety notes: no hidden labels/scorer internals inspected.
- Decision: park as default, refine
- Next action: keep `--helper-pool-size` as an explicit ablation flag with default `0`/active-helper pool. Implement visible payment-error repair before retesting wide pool.

### Run Card - 2026-05-30T00:01:22-04:00 - tau3 payment repair invalid infra partial

- Branch: `codex/sage-standalone-agent`
- Commit: `33d7369` plus uncommitted experimental changes
- Hypothesis: visible payment-error repair attached to generated booking/payment helper calls can turn official `total price is X, but paid Y` errors into bounded exact payment repairs.
- Environment: tau3-current-release airline via `scripts/run_tau3_sageagent_parity.py`
- Command: `PYTHONPATH=src:. python scripts/run_tau3_sageagent_parity.py --samples 20 --domain airline --model gpt-4o-mini --generation-model gpt-5 --baseline-cache use-if-eligible --dashboard-port 62630 --max-helpers 32 --helper-pool-size 12 --active-helpers 4 --max-tools-per-task 3 --max-same-task-retries 1 --max-refinements 2 --max-gap-signals-per-task 4 --transient-retries 2 --tau2-timeout-sec 120 --generation-timeout-sec 120 --source-guided-host-action-generation --run-id tau3_shadow_pool12_payment_repair20_20260530_000122`
- Sample/window: requested 20, stopped after 7 SAGE task records
- Baseline cache: `20/20` cached; baseline successes in partial `6/7`
- SAGE cache: off/fresh SAGE helper generation
- Model: `gpt-4o-mini`
- Generation model: `gpt-5`
- Dashboard: `outputs/sage_official_live/tau3_shadow_pool12_payment_repair20_20260530_000122/dashboard/task_compare.html`
- Results: partial final SAGE `6/7` vs baseline `6/7`; no helpers born before stop.
- Generated tools born/accepted/reused/called: `0 / 0 / 0 / 0`
- Tool-attributed gains: `0`
- Tool-attributed regressions: `0`
- Runtime/helper incidents: task 6 exhausted all three official-runner attempts with `tau2_runner_error:IndexError`; terminating PID `83598` intentionally after logging infra invalidity.
- Leakage/safety notes: no hidden labels/scorer internals inspected; no helper evidence produced.
- Decision: rerun / infra invalid
- Next action: rerun payment repair diagnostic; if runner errors persist on fixed task windows, add invalid-infra exclusion or targeted task skip for diagnostics before judging payment repair.

### Run Card - 2026-05-30T00:06:10-04:00 - tau3 seeded payment repair diagnostic

- Branch: `codex/sage-standalone-agent`
- Commit: `33d7369` plus uncommitted experimental changes
- Hypothesis: seeding the previous wide-pool registry on payment-heavy visible task ids will show whether visible payment-error repair can make the booking/payment helper actionable.
- Environment: tau3-current-release airline via `scripts/run_tau3_sageagent_parity.py`
- Command: `PYTHONPATH=src:. python scripts/run_tau3_sageagent_parity.py --samples 4 --tau2-task-id 9 --tau2-task-id 10 --tau2-task-id 14 --tau2-task-id 15 --domain airline --model gpt-4o-mini --generation-model gpt-5 --baseline-cache use-if-eligible --dashboard-port 62630 --initial-registry outputs/sage_official_live/tau3_shadow_pool12_20_20260529_233820/sageagent_registry/sage_registry.json --max-helpers 32 --helper-pool-size 12 --active-helpers 4 --max-tools-per-task 2 --max-same-task-retries 1 --max-refinements 1 --max-gap-signals-per-task 3 --transient-retries 2 --tau2-timeout-sec 120 --generation-timeout-sec 120 --source-guided-host-action-generation --run-id tau3_payment_repair_seeded_diag4_20260530_000610`
- Sample/window: seeded diagnostic on source task ids `9`, `10`, `14`, `15`
- Baseline cache: cached
- SAGE cache: seeded registry diagnostic, not evidence
- Model: `gpt-4o-mini`
- Generation model: `gpt-5`
- Dashboard: `outputs/sage_official_live/tau3_payment_repair_seeded_diag4_20260530_000610/dashboard/task_compare.html`
- Results: stopped after 3 task records; final `0/3` in partial seeded diagnostic.
- Generated tools born/accepted/reused/called: `3 / 3 / 12 / 12` in partial seeded diagnostic
- Tool-attributed gains: `0`; payment repair did not fire because booking/payment helper was not selected in the relevant turns.
- Tool-attributed regressions: `0` evidence; diagnostic showed cancellation helper still over-selected in seeded payment contexts.
- Runtime/helper incidents: terminating PIDs `85923` and `91539` intentionally after logging failed routing diagnostic.
- Leakage/safety notes: seeded diagnostic only; no hidden labels/scorer internals inspected.
- Decision: park seeded diagnostic
- Next action: route payment-error contexts above cancellation helpers before retesting payment repair. Do not count seeded diagnostic as SAGE evidence.

### Run Card - 2026-05-30T02:20:37-04:00 - tau3 medium-grain generalization20

- Branch: `codex/sage-standalone-agent`
- Commit: `33d7369` plus uncommitted experimental changes
- Hypothesis: failure-turn replay context, medium-grain action-spec helpers, exposure-regression parking, source-trip record lookup, payment repair, and conservative per-turn routing will produce positive callable-helper lift without unresolved helper-attributed regressions.
- Environment: tau3-current-release airline via `scripts/run_tau3_sageagent_parity.py`
- Command: `PYTHONPATH=src:. python scripts/run_tau3_sageagent_parity.py --samples 20 --domain airline --model gpt-4o-mini --generation-model gpt-5 --baseline-cache use-if-eligible --dashboard-port 62639 --max-helpers 32 --active-helpers 5 --max-tools-per-task 4 --max-same-task-retries 1 --max-refinements 2 --transient-retries 2 --generation-timeout-sec 120 --source-guided-host-action-generation --run-id tau3_medium_grain_generalization20_20260530_022037`
- Sample/window: first 20 airline tasks
- Baseline cache: `20/20` cached; baseline successes `8/20`
- SAGE cache: off/fresh SAGE generation
- Model: `gpt-4o-mini`
- Generation model: `gpt-5`
- Dashboard: `outputs/sage_official_live/tau3_medium_grain_generalization20_20260530_022037/dashboard/task_compare.html`
- Results: final SAGE `12/20` vs baseline `8/20`; initial SAGE had two baseline-success failures that were rescued by deferred same-task retries; integrity issues `0`.
- Generated tools born/accepted/reused/called: `22 / 19 / 103 / 103`
- Tool-attributed gains: registry recorded `2` contribution gains on `prepare_visible_reservation_change_action_args`; additional final gains included stochastic/no-helper or weakly constrained helper contexts and should not be promoted as strict evidence.
- Tool-attributed regressions: strict final `0`; one option helper exposure regression was parked as non-actionable exposure, and rescued retries prevented final helper-attributed regression.
- Runtime/helper incidents: no helper runtime incidents; transient tau runner errors were retried.
- Leakage/safety notes: no hidden labels, expected answers, reference trajectories, or scorer internals inspected.
- Decision: keep / refine
- Next action: fix retry bundle composition and tau3 helper-pool starvation. Task `tau3:airline:8` still failed because the right record/payment/option helpers were born or available but crowded out by last-batch guard/broad helpers.

### Run Card - 2026-05-30T02:52:32-04:00 - tau3 retry-bundle task8 diagnostic

- Branch: `codex/sage-standalone-agent`
- Commit: `33d7369` plus uncommitted experimental changes
- Hypothesis: accumulating all newly born deferred-retry helpers and widening the internal tau3 helper pool will let task 8 keep record lookup, option selection, and booking/payment helpers through retry.
- Environment: tau3-current-release airline via `scripts/run_tau3_sageagent_parity.py`
- Command: `PYTHONPATH=src:. python scripts/run_tau3_sageagent_parity.py --samples 1 --tau2-task-id 8 --domain airline --model gpt-4o-mini --generation-model gpt-5 --baseline-cache use-if-eligible --dashboard-port 62640 --max-helpers 32 --active-helpers 5 --max-tools-per-task 4 --max-same-task-retries 1 --max-refinements 2 --transient-retries 2 --generation-timeout-sec 120 --source-guided-host-action-generation --run-id tau3_retry_bundle_task8_20260530_025232`
- Sample/window: single visible diagnostic task `tau3:airline:8`
- Baseline cache: cached baseline failure
- SAGE cache: off/fresh SAGE generation
- Model: `gpt-4o-mini`
- Generation model: `gpt-5`
- Dashboard: `outputs/sage_official_live/tau3_retry_bundle_task8_20260530_025232/dashboard/task_compare.html`
- Results: SAGE still failed, but the mechanism improved: retry bundle contained `prepare_visible_airline_new_booking_action_args`, `prepare_visible_booking_payment_action_args`, `prepare_visible_record_field_lookup`, and `select_visible_action_option`; record lookup scanned to `WUNA5K`, selected `HAT271` on `2024-05-26`, and payment was repaired to `174`.
- Generated tools born/accepted/reused/called: `4 / 4 / 17 / 17`
- Tool-attributed gains: `0`
- Tool-attributed regressions: `0`
- Runtime/helper incidents: one transient tau runner exception was retried; no helper exceptions.
- Leakage/safety notes: visible transcript only; no hidden data inspected.
- Decision: refine
- Next action: normalize new-booking baggage args in the official action-repair bridge. The remaining failure was copied `total_baggages=1` from the source trip when the user did not request baggage.

### Run Card - 2026-05-30T02:58:23-04:00 - tau3 baggage repair infra invalid

- Branch: `codex/sage-standalone-agent`
- Commit: `33d7369` plus uncommitted experimental changes
- Hypothesis: official action repair should rewrite copied free baggage to zero for new booking/create calls when recent user text does not request baggage.
- Environment: tau3-current-release airline via `scripts/run_tau3_sageagent_parity.py`
- Command: same task-8 diagnostic with `--dashboard-port 62641 --run-id tau3_baggage_repair_task8_20260530_025823`
- Sample/window: single visible diagnostic task `tau3:airline:8`
- Baseline cache: cached
- SAGE cache: off/fresh SAGE generation
- Model: `gpt-4o-mini`
- Generation model: `gpt-5`
- Dashboard: `outputs/sage_official_live/tau3_baggage_repair_task8_20260530_025823/dashboard/task_compare.html`
- Results: invalid infrastructure run. SAGE exhausted transient attempts with `tau2_runner_error:InternalServerError` from OpenAI/LiteLLM connection errors before helper generation or calls.
- Generated tools born/accepted/reused/called: `0 / 0 / 0 / 0`
- Tool-attributed gains: `0`
- Tool-attributed regressions: `0`
- Runtime/helper incidents: external API DNS/connectivity failure; not SAGE helper runtime.
- Leakage/safety notes: no hidden data inspected.
- Decision: rerun when API sanity check passes
- Next action: retry task 8 and then the 20-task gate after `api.openai.com` DNS/OpenAI chat sanity recovers.

### Run Card - 2026-05-30T02:59:00-04:00 - tau3 baggage repair rerun infra invalid

- Branch: `codex/sage-standalone-agent`
- Commit: `33d7369` plus uncommitted experimental changes
- Hypothesis: same as prior task-8 baggage repair diagnostic.
- Environment: tau3-current-release airline via `scripts/run_tau3_sageagent_parity.py`
- Command: same task-8 diagnostic with `--dashboard-port 62642 --transient-retries 3 --run-id tau3_baggage_repair_task8_rerun_20260530_025900`
- Sample/window: single visible diagnostic task `tau3:airline:8`
- Baseline cache: cached
- SAGE cache: off/fresh SAGE generation
- Model: `gpt-4o-mini`
- Generation model: `gpt-5`
- Dashboard: `outputs/sage_official_live/tau3_baggage_repair_task8_rerun_20260530_025900/dashboard/task_compare.html`
- Results: invalid infrastructure run. All four SAGE attempts failed with OpenAI connection errors before helper behavior could be tested. Direct `openai` and `litellm` chat sanity checks also failed with DNS resolution error for `api.openai.com`.
- Generated tools born/accepted/reused/called: `0 / 0 / 0 / 0`
- Tool-attributed gains: `0`
- Tool-attributed regressions: `0`
- Runtime/helper incidents: external API DNS/connectivity failure; not SAGE helper runtime.
- Leakage/safety notes: no hidden data inspected.
- Decision: blocked on API connectivity
- Next action: continue local validation and resume live task8/20 diagnostics once OpenAI chat sanity passes.

### Run Card - 2026-05-31T00:46:40-04:00 - tau3 no-revisit recovery gate60f

- Branch: `codex/sage-standalone-agent`
- Commit: `33d7369` plus uncommitted experimental changes
- Hypothesis: move the prior same-task retry gains into first-pass helper
  routing, action validation, and repair so tau3 can recover the `12/20`
  pattern without revisiting tasks.
- Environment: tau3-current-release airline via
  `scripts/run_tau3_sageagent_parity.py`
- Command: `PYTHONPATH=src:. python scripts/run_tau3_sageagent_parity.py --samples 60 --domain airline --model gpt-4o-mini --generation-model gpt-5 --baseline-cache use-if-eligible --dashboard-port 62746 --max-helpers 48 --active-helpers 6 --helper-pool-size 12 --max-tools-per-task 9 --max-same-task-retries 0 --max-refinements 2 --transient-retries 4 --generation-timeout-sec 120 --direct-only-shadow-helpers --enable-direct-actions --proactive-helper-bootstrap --proactive-bootstrap-limit 9 --run-id tau3_no_revisit_recovery_gate60f_20260531_001355`
- Sample/window: requested `60`; this checkout materialized first `50`
  airline tasks.
- Baseline cache: `use-if-eligible`, `50/50` cached; baseline successes
  `15/50`.
- SAGE cache: off/fresh SAGE arm.
- Model: `gpt-4o-mini`
- Generation model: `gpt-5`
- Dashboard:
  `http://127.0.0.1:62746/outputs/sage_official_live/tau3_no_revisit_recovery_gate60f_20260531_001355/dashboard/task_compare.html`
- Results: SAGE `29/50` vs baseline `15/50`; first 20 slice `15/20` vs
  baseline `8/20`; absolute lift `+14` tasks, `+28` percentage points;
  relative success lift `+93.33%`; same-task retries `0`; integrity issues `0`.
- Generated tools born/accepted/reused/called: `22 / 22 / 1162 / 1162`;
  bridge events included `144` direct helper actions, `77` official action
  repairs, and `30` final-answer repairs.
- Tool-attributed gains: paired gains on tasks
  `1, 8, 11, 12, 13, 15, 18, 26, 28, 34, 38, 40, 43, 48`.
- Tool-attributed regressions: `0` final paired losses.
- Runtime/helper incidents: `0`.
- Leakage/safety notes: no hidden labels, expected answers, reference
  trajectories, or scorer internals inspected. One earlier partial run
  `tau3_no_revisit_recovery_gate60e_20260531_000454` was intentionally stopped
  at PID `60447` after a code patch superseded the running process.
- Decision: keep / scale
- Next action: update SAGEAgent parity attribution audit/export coverage,
  inspect remaining misses for the next general helper class, then run CyberGym
  and ToolSandbox maintenance checks.

### Run Card - 2026-05-31T14:07:00-04:00 - ToolSandbox fullprefix500 reference resume

- Branch: `codex/sage-standalone-agent`
- Commit: `33d7369` plus uncommitted experimental changes
- Hypothesis: resume the correct ToolSandbox `online_build_500` prefix dataset
  for the same-dataset comparison, ignoring focused20/focused60 diagnostics
  that were previously mistaken for the active comparison run.
- Environment: ToolSandbox native self-evolving Praxis via
  `/tmp/toolsandbox-sage-local-run/scripts/run_sage_protocol.py`
- Command: launchd one-shot
  `artifacts/toolsandbox_recovery_ladder_20260531_v60/run_fullprefix500_direct_reference_launchd.sh`
  with `--mode online_build_500`, manifest
  `artifacts/toolsandbox_recovery_ladder_20260531_v60/full_standard_prefix500.json`,
  registry `artifacts/toolsandbox_recovery_ladder_20260531_v60/fullprefix500_registry_r11`,
  and resume root
  `outputs/toolsandbox_recovery_ladder_20260531_v60/fullprefix500_r11_launchd_reference_20260531_135809/online_build_500_20260531_135815`.
- Sample/window: 500-task prefix; resumed from best local partial `413/500`.
- Baseline cache: strict control cache; dashboard currently reports control
  `500/500` complete.
- SAGE cache: off/fresh SAGE arm; OpenAI response cache disabled.
- Model: `gpt-4o-mini`
- Generation model: `gpt-4o-mini`
- Dashboard:
  `http://127.0.0.1:62679/outputs/toolsandbox_recovery_ladder_20260531_v60/fullprefix500_r11_launchd_reference_20260531_140308/online_build_500_20260531_140312/dashboard/task_compare.html`
- Results: in progress at `417/500` matched tasks as of 14:07 EDT; live
  paired dashboard showed baseline score `0.685114`, SAGE score `0.898871`,
  canonical delta `+0.213756` (`+31.20%`), baseline outcome `0.521966`,
  SAGE outcome `0.888864`, outcome delta `+0.366898`.
- Generated tools born/accepted/reused/called: dashboard live summary
  `7` born/accepted, `267` reuse events, `142` generated-tool-called
  scenarios.
- Tool-attributed gains: pending final completion/export.
- Tool-attributed regressions: pending final completion/export.
- Runtime/helper incidents: live `current_exceptions=0`,
  generated-tool failures `0`, runtime incidents `0`, side-effect incidents
  `0`.
- Leakage/safety notes: correct manifest is `full_standard_prefix500.json`;
  no hidden labels or expected answers inspected. Stopped off-track focused20
  process PID `17152`, then PID `18977` after it respawned, because both used
  `focused_regression20_r12.json` / `mechanism_40` and conflicted with the
  requested fullprefix500 reference.
- Decision: keep running
- Next action: continue heartbeat monitoring with short artifact/process reads;
  when the reference reaches `500/500`, launch the same-dataset GPT-5
  generation comparison with a fresh registry and write the JSON/MD comparison.

### Run Card - 2026-05-31T14:15:46-04:00 - ToolSandbox fullprefix500 current-impl GPT-5 comparison

- Branch: `codex/sage-standalone-agent`
- Commit: `33d7369` plus uncommitted experimental changes synced into
  `/tmp/toolsandbox-sage-local-run`
- Hypothesis: compare the current implementation, including the recent
  no-revisit/helper-routing work, against the reference on the exact same
  ToolSandbox `online_build_500` prefix sample set.
- Environment: ToolSandbox native self-evolving Praxis via
  `/tmp/toolsandbox-sage-local-run/scripts/run_sage_protocol.py`
- Command: launchd one-shot
  `artifacts/toolsandbox_recovery_ladder_20260531_v60/run_fullprefix500_current_impl_gpt5_launchd.sh`
  with `--mode online_build_500`, manifest
  `artifacts/toolsandbox_recovery_ladder_20260531_v60/full_standard_prefix500.json`,
  fresh registry
  `artifacts/toolsandbox_recovery_ladder_20260531_v60/fullprefix500_current_impl_gpt5_registry_20260531_141546`,
  and output root
  `outputs/toolsandbox_recovery_ladder_20260531_v60/fullprefix500_current_impl_gpt5_20260531_141546`.
- Sample/window: same 500-task prefix manifest as the reference.
- Baseline cache: strict control cache; dashboard initialized with control
  `500/500` complete.
- SAGE cache: off/fresh SAGE arm; OpenAI response cache disabled.
- Model: `gpt-4o-mini`
- Generation model: `gpt-5`
- Dashboard:
  `http://127.0.0.1:62680/outputs/toolsandbox_recovery_ladder_20260531_v60/fullprefix500_current_impl_gpt5_20260531_141546/online_build_500_20260531_141550/dashboard/task_compare.html`
- Results: completed `500/500`; canonical score `0.711718 -> 0.904691`
  (`+27.11%` lift); outcome `0.549273 -> 0.867849`; outcome delta
  `+0.318575`. Against the gpt-4o-mini-generation reference, this was
  `+0.007570` SAGE canonical score, `+1.06` canonical-lift percentage points,
  and `+0.001689` outcome delta.
- Generated tools born/accepted/reused/called: accepted `7`; reuse `278`;
  generated-tool-called scenarios `164`.
- Tool-attributed gains: final contribution table pending deeper analysis; no
  generated-tool failed scenarios.
- Tool-attributed regressions: final contribution table pending deeper
  analysis; no runtime/side-effect incidents.
- Runtime/helper incidents: current exceptions `0`; generated-tool failed
  scenarios `0`; runtime incidents `0`; side-effect incidents `0`.
- Leakage/safety notes: same public manifest/sample set as the reference; no
  hidden labels or expected answers inspected.
- Process hygiene: stopped off-track `mechanism_60` process PID `51301`
  (`artifacts/chapter3_tool_generation_only_bakeoff/toolsandbox_formal500_order_60.json`)
  because it was not part of the fullprefix500 reference/comparison workflow
  and competed with the active GPT-5 comparison run.
- Decision: keep / analyze
- Next action: inspect helper attribution and residual misses before claiming
  a mechanism win.

### Run Card - 2026-05-31T15:16:27-04:00 - ToolSandbox fullprefix500 comparison completed

- Branch: `codex/sage-standalone-agent`
- Commit: `33d7369` plus uncommitted experimental changes synced into
  `/tmp/toolsandbox-sage-local-run`
- Hypothesis: the current implementation plus GPT-5 generation can beat the
  same-sample gpt-4o-mini-generation reference on the exact ToolSandbox
  `online_build_500` prefix.
- Environment: ToolSandbox native self-evolving Praxis via local
  `/tmp/toolsandbox-sage-local-run`
- Command: reference via
  `artifacts/toolsandbox_recovery_ladder_20260531_v60/run_fullprefix500_direct_reference_launchd.sh`;
  comparison via
  `artifacts/toolsandbox_recovery_ladder_20260531_v60/run_fullprefix500_current_impl_gpt5_launchd.sh`
- Sample/window: same 500-task prefix manifest
  `artifacts/toolsandbox_recovery_ladder_20260531_v60/full_standard_prefix500.json`
- Baseline cache: strict control cache; matched control means identical in
  final comparison.
- SAGE cache: off/fresh SAGE arms; OpenAI response cache disabled.
- Model: `gpt-4o-mini`
- Generation model: reference `gpt-4o-mini`; comparison `gpt-5`
- Dashboard:
  reference `http://127.0.0.1:62679/outputs/toolsandbox_recovery_ladder_20260531_v60/fullprefix500_r11_launchd_reference_20260531_140308/online_build_500_20260531_140312/dashboard/task_compare.html`;
  comparison `http://127.0.0.1:62680/outputs/toolsandbox_recovery_ladder_20260531_v60/fullprefix500_current_impl_gpt5_20260531_141546/online_build_500_20260531_141550/dashboard/task_compare.html`
- Results: reference canonical `0.711718 -> 0.897120` (`+26.05%` lift),
  outcome `0.549273 -> 0.866160`, outcome delta `+0.316886`;
  comparison canonical `0.711718 -> 0.904691` (`+27.11%` lift), outcome
  `0.549273 -> 0.867849`, outcome delta `+0.318575`.
- Generated tools born/accepted/reused/called: reference accepted `7`, reuse
  `356`, called scenarios `181`; comparison accepted `7`, reuse `278`, called
  scenarios `164`.
- Tool-attributed gains: pending deeper contribution-table analysis.
- Tool-attributed regressions: pending deeper contribution-table analysis.
- Runtime/helper incidents: both runs `0` current exceptions, `0`
  generated-tool failed scenarios, `0` runtime incidents, `0` side-effect
  incidents.
- Leakage/safety notes: no hidden labels or expected answers inspected; both
  used the same visible manifest/sample set.
- Decision: keep / analyze
- Next action: inspect helper-level attribution and residual misses to explain
  why the GPT-5 run gained more score with fewer calls/reuse events.
