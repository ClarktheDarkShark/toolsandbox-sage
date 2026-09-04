# Chapter 3 Methodology Agent Handoff - 2026-05-29

> **SUPERSEDED — ARCHIVAL HANDOFF.** Commands and source paths below describe a
> retired development tree and are not runnable publication instructions. See
> [current_state.md](current_state.md).

This file is for a new agent whose job is to support Chapter 3 methodology
writing for the SAGE praxis. The agent should become fluent in the validated
ToolSandbox SAGE implementation, the self-evolving Praxis pipeline, the
evidence boundary, and the figures/tables/pseudocode needed for a dissertation
methodology chapter.

This agent is not primarily the CyberGym/tau3 engineering agent. The companion
engineering handoff is:

- `docs/sage_protocol/cybergym_tau3_generalization_handoff_20260529.md`

Use that file when portability work succeeds or when Chapter 3 needs to state
limitations and future-work requirements.

## Mission

Prepare Chapter 3 methodology materials around the strongest ToolSandbox SAGE
implementation while remaining ready to incorporate a later, improved portable
implementation if the CyberGym/tau3 engineering agent produces a cleaner and
more general result.

The methodology agent must be able to produce:

- prose for Chapter 3,
- diagrams,
- tables,
- pseudocode,
- run-configuration descriptions,
- threat-to-validity and leakage-control sections,
- safety and side-effect-control sections,
- dashboard/evidence explanations,
- and a clear explanation of what SAGE is and is not.

## Current Provisional Primary SAGE Implementation

The current provisional primary implementation for Chapter 3 is the native
ToolSandbox self-evolving Praxis implementation:

- Runner: `scripts/run_sage_protocol.py`
- Policy preset: `--sage-policy self-evolving-praxis`
- Full-dataset build mode: `online_build_full`
- Reusable SAGE core: `src/sage_ts/`
- ToolSandbox SAGE execution adapter: `src/sage_research/toolsandbox/sage_run_adapter.py`
- ToolSandbox integration: `src/sage_research/toolsandbox/integration.py`
- Tool generation: `src/sage_ts/generation/tool_generator.py`
- Tool validation: `src/sage_ts/validation/`
- Registry/manifests: `src/sage_ts/registry/manifest.py`
- Actor/tool-use policy: `src/sage_research/toolsandbox/openai_roles.py`
- Dashboard: `src/sage_ts/dashboard/task_compare_template.py`
- Methodology setup note: `docs/sage_protocol/chapter3_sage_methodology_working_setup.md`

This is the implementation that demonstrated the strongest 250/500 ToolSandbox
successes. It is stronger than prompt-only import-agent mode because it has the
full SAGE lifecycle: deterministic gap detection, live helper generation,
validation/repair, registry storage, routing, same-task fair chance/retry,
natural helper calls, contribution accounting, and lifecycle decisions.

The strongest current broad500 evidence is:

- Run: `outputs/self_evolving_sage/formal500_live_generation_v71_clean_repro/online_build_500_20260514_204356`
- Canonical/reference: `0.656799 -> 0.854188`
- Canonical delta/lift: `+0.197389`, `+30.05%`
- Outcome/task completion: `0.494746 -> 0.880845`
- Outcome delta/lift: `+0.386099`, `+78.04%`
- Controls: `500 cached / 0 fresh`
- SAGE task cache: off
- OpenAI response cache: disabled
- Starting generated registry: empty/absent
- Accepted live-born helpers: `16`
- Naturally called generated-tool scenarios: `297`
- Generated-tool failures: `0`
- Runtime exceptions: `0`
- Caveat: one strict helper-contract side-effect preservation near miss on a
  read-only reminder-search task. No state mutation occurred, but a protected
  final claim should repair or adjudicate this before final claim promotion.

The prior v70 broad500 remains important because it had zero helper
side-effect incidents:

- Run: `outputs/self_evolving_sage/formal500_live_generation_v70_jit_birth_retry_repair/online_build_500_20260513_174839`
- Canonical/reference: `0.656799 -> 0.827506`
- Canonical delta/lift: `+0.170706`, `+25.99%`
- Outcome/task completion: `0.494746 -> 0.872782`
- Outcome delta/lift: `+0.378036`, `+76.41%`
- Runtime/helper incidents: `0 / 0`

Treat v71 as the provisional highest-performing implementation and v70 as the
clean safety-reference implementation until a new controlled bake-off says
otherwise.

## Do Not Finalize "Best Implementation" Without A Bake-Off

Before making a final claim about which implementation is best for Chapter 3/4,
run a controlled ToolSandbox bake-off over the most promising current variants.
The bake-off is required because CyberGym/tau3 work added generalization logic
that may or may not improve ToolSandbox.

Use this rule:

- 20-task diagnostic first.
- If positive and safe, 60-task validation.
- If still positive and safe, 500-task broad validation.
- Optional 250-task scale probe can be inserted before 500 if cost/time risk is
  high.

Every bake-off arm must use:

- same manifest/order,
- same actor model,
- same user model,
- same baseline cache policy,
- fresh SAGE arm,
- SAGE task cache off,
- OpenAI response cache disabled,
- no diagnostic force-call env vars,
- generation on for self-evolving arms,
- dashboard opened at run start,
- contribution audit after run.

Baseline/control arms should use per-task cache wherever eligible. Do not rerun
fresh baselines unnecessarily.

## Candidate Implementations To Compare

At minimum, compare these variants.

### Candidate A: Native ToolSandbox Praxis, Mini Generation

This approximates the known v70/v71 successful path.

- Runner: `scripts/run_sage_protocol.py`
- Policy: `--sage-policy self-evolving-praxis`
- Actor/user: `gpt-4o-mini`
- Generation model: `gpt-4o-mini`
- Expected behavior: closest to the validated high-lift runs.

### Candidate B: Native ToolSandbox Praxis, Stronger Generation

This tests whether the later CyberGym/tau3 lesson about candidate quality helps
ToolSandbox without changing the actor.

- Runner: `scripts/run_sage_protocol.py`
- Policy: `--sage-policy self-evolving-praxis`
- Actor/user: `gpt-4o-mini`
- Generation model: `gpt-5`
- Expected behavior: potentially better helper generation/repair, but must be
  tested for safety, latency, and over-generation.

### Candidate C: Current Native ToolSandbox Praxis With Latest Code

This is the current checkout's native ToolSandbox implementation after later
generalization work. It may overlap with A/B, but record it explicitly as
"current native implementation." Use whichever generation model is being
considered for Chapter 4.

### Candidate D: Standalone/Import-Agent ToolSandbox Path

This tests whether the portable `sage_agent` implementation is competitive on
ToolSandbox.

- Runner: `scripts/run_sage_agent_smoke.py`
- Dataset: `toolsandbox`
- Generator: `openai`
- Actor model: `gpt-4o-mini`
- It must be audited with `scripts/audit_sage_import_readiness.py`.
- Only consider it a primary candidate if gains are generated-helper-attributed
  and callable/structured helper usage is real, not prompt-only guidance.

If this path shows weaker ToolSandbox lift or prompt-only behavior, document it
as portability/future-work, not as the Chapter 3 primary SAGE.

### Candidate E: Future Successful CyberGym/tau3 Generalized Version

If the CyberGym/tau3 engineering agent produces a new general SAGE lifecycle
repair, incorporate it only after it passes:

1. CyberGym/tau3 improvement with generated-tool-attributed gains,
2. ToolSandbox 20/60 no-regression check,
3. ToolSandbox 500 if it appears stronger than v71,
4. same safety/leakage/cache requirements as the native ToolSandbox runs.

Do not replace the primary SAGE with a portability variant merely because it is
architecturally attractive. It must preserve or improve the ToolSandbox result.

## Bake-Off Manifest Setup

The sealed formal manifests expose `full_benchmark`. For small bake-off runs,
derive experimental manifests under `artifacts/`; do not edit protected
manifest files.

Create 20-task and 60-task derived manifests:

```bash
PYTHONPATH=src:. python - <<'PY'
import json
from pathlib import Path

src = Path("docs/sage_protocol/manifests/v2_1_formal_500.json")
payload = json.loads(src.read_text())
full = payload["splits"]["full_benchmark"]

for split_name, n in [("mechanism_40", 20), ("mechanism_60", 60)]:
    out = Path(f"artifacts/chapter3_methodology_bakeoff/toolsandbox_{n}.json")
    derived = dict(payload)
    derived["splits"] = {split_name: full[:n]}
    derived["metadata"] = {
        **payload.get("metadata", {}),
        "derived_for": "Chapter 3 SAGE implementation bake-off",
        "source_manifest": str(src),
        "source_split": "full_benchmark",
        "task_count": n,
        "split_name": split_name,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(derived, indent=2) + "\n")
    print(out)
PY
```

For 500, use the original formal500 manifest:

- `docs/sage_protocol/manifests/v2_1_formal_500.json`
- mode: `online_build_500`

For the future whole-dataset run:

- `docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`
- mode: `online_build_full`
- use the then-current whole-dataset preflight (launcher since removed)

## Candidate A/B/C Run Commands

20-task diagnostic:

```bash
PYTHONPATH=src:. SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY=1 \
TOOLSANDBOX_RAPID_CACHE_MODE=read_only \
TOOLSANDBOX_RAPID_CACHE_PATH=".secrets/rapid_api_cache.json" \
python scripts/run_sage_protocol.py \
  --mode mechanism_40 \
  --manifest artifacts/chapter3_methodology_bakeoff/toolsandbox_20.json \
  --registry-dir artifacts/chapter3_methodology_bakeoff/<VARIANT>_registry20 \
  --sage-policy self-evolving-praxis \
  --agent gpt-4o-mini \
  --user gpt-4o-mini \
  --generation-model <gpt-4o-mini-or-gpt-5> \
  --generation on \
  --disable-openai-response-cache \
  --cache-mode off \
  --control-cache use-if-eligible \
  --control-cache-root artifacts/baselines/control_task_baselines \
  --routing-evidence-mode disabled \
  --freeze-toolsandbox-clock \
  --dashboard-port 62624 \
  --output-root outputs/chapter3_methodology_bakeoff/<VARIANT>_20 \
  --artifact-root artifacts/chapter3_methodology_bakeoff/<VARIANT>_20_artifacts
```

60-task validation:

```bash
PYTHONPATH=src:. SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY=1 \
TOOLSANDBOX_RAPID_CACHE_MODE=read_only \
TOOLSANDBOX_RAPID_CACHE_PATH=".secrets/rapid_api_cache.json" \
python scripts/run_sage_protocol.py \
  --mode mechanism_60 \
  --manifest artifacts/chapter3_methodology_bakeoff/toolsandbox_60.json \
  --registry-dir artifacts/chapter3_methodology_bakeoff/<VARIANT>_registry60 \
  --sage-policy self-evolving-praxis \
  --agent gpt-4o-mini \
  --user gpt-4o-mini \
  --generation-model <gpt-4o-mini-or-gpt-5> \
  --generation on \
  --disable-openai-response-cache \
  --cache-mode off \
  --control-cache use-if-eligible \
  --control-cache-root artifacts/baselines/control_task_baselines \
  --routing-evidence-mode disabled \
  --freeze-toolsandbox-clock \
  --dashboard-port 62624 \
  --output-root outputs/chapter3_methodology_bakeoff/<VARIANT>_60 \
  --artifact-root artifacts/chapter3_methodology_bakeoff/<VARIANT>_60_artifacts
```

500-task validation, only if 60 is promising:

```bash
PYTHONPATH=src:. SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY=1 \
TOOLSANDBOX_RAPID_CACHE_MODE=read_only \
TOOLSANDBOX_RAPID_CACHE_PATH=".secrets/rapid_api_cache.json" \
python scripts/run_sage_protocol.py \
  --mode online_build_500 \
  --manifest docs/sage_protocol/manifests/v2_1_formal_500.json \
  --registry-dir artifacts/chapter3_methodology_bakeoff/<VARIANT>_registry500 \
  --sage-policy self-evolving-praxis \
  --agent gpt-4o-mini \
  --user gpt-4o-mini \
  --generation-model <gpt-4o-mini-or-gpt-5> \
  --generation on \
  --disable-openai-response-cache \
  --cache-mode off \
  --control-cache use-if-eligible \
  --control-cache-root artifacts/baselines/control_task_baselines \
  --routing-evidence-mode disabled \
  --freeze-toolsandbox-clock \
  --dashboard-port 62624 \
  --output-root outputs/chapter3_methodology_bakeoff/<VARIANT>_500 \
  --artifact-root artifacts/chapter3_methodology_bakeoff/<VARIANT>_500_artifacts
```

Replace `<VARIANT>` with names such as:

- `native_praxis_mini_generation`
- `native_praxis_gpt5_generation`
- `current_native_generalized`

## Candidate D Import-Agent Commands

20-task portable ToolSandbox diagnostic:

```bash
PYTHONPATH=src:. python scripts/run_sage_agent_smoke.py \
  --dataset toolsandbox \
  --limit 20 \
  --model gpt-4o-mini \
  --generator openai \
  --baseline llm \
  --baseline-cache use-if-eligible \
  --baseline-cache-path artifacts/sage_agent_baseline_cache.json \
  --registry-dir artifacts/chapter3_methodology_bakeoff/import_agent_toolsandbox_registry20 \
  --output-root outputs/chapter3_methodology_bakeoff \
  --run-id import_agent_toolsandbox20_$(date +%Y%m%d_%H%M%S) \
  --dashboard-port 62624 \
  --reset-registry
```

Audit:

```bash
PYTHONPATH=src:. python scripts/audit_sage_import_readiness.py \
  --run-dir <RUN_DIR> \
  --require-attributed-gains \
  --require-callable-tool-gains
```

Only scale the import-agent path if the audit confirms callable generated-tool
gains. If the path only uses prompt guidance, classify it as portability
infrastructure, not the primary SAGE methodology implementation.

## OpenAI API Setup

Do not print secrets.

Check whether the key is present:

```bash
python - <<'PY'
import os
print("OPENAI_API_KEY present:", bool(os.environ.get("OPENAI_API_KEY")))
PY
```

If absent, the key has previously been available through a sibling env file:

```bash
set -a
source ../Hey_Alfredv2/.env
set +a
python - <<'PY'
import os
print("OPENAI_API_KEY present:", bool(os.environ.get("OPENAI_API_KEY")))
PY
```

Sanity check:

```bash
python - <<'PY'
from openai import OpenAI
client = OpenAI()
models = client.models.list()
print("openai_ok", bool(models.data))
PY
```

## Metrics The Methodology Agent Must Collect

For each bake-off run, create a row with:

- implementation variant,
- code commit,
- run path,
- dashboard path,
- manifest path and hash,
- sample size,
- actor model,
- user model,
- generation model,
- baseline cache cached/fresh counts,
- SAGE cache status,
- OpenAI response cache status,
- score/canonical baseline,
- score/canonical SAGE,
- score delta and lift,
- outcome baseline,
- outcome SAGE,
- outcome delta and lift,
- tools born,
- tools accepted,
- tools rejected,
- tools repaired,
- tools naturally called,
- generated-tool-attributed gains,
- generated-tool-attributed regressions,
- runtime exceptions,
- helper runtime failures,
- helper side-effect incidents,
- decision: keep/refine/park/scale.

Do not choose the winner by score alone. The primary implementation must show
tool-driven lift and safe behavior.

## Expected Chapter 3 Content

The methodology agent should prepare these sections.

### 1. Research Design Overview

Explain SAGE as a self-evolving tool-use system evaluated in ToolSandbox. State
that the primary intervention is not a new static prompt but a lifecycle that
generates, validates, stores, routes, and evaluates reusable deterministic
helpers.

### 2. System Architecture

Describe the major components:

- task runner,
- baseline/control arm,
- SAGE arm,
- gap detector,
- helper generator,
- static/schema/runtime validator,
- safety checker,
- registry,
- router,
- actor bridge,
- contribution logger,
- dashboard/exporter.

### 3. SAGE Pipeline

Include step-by-step pipeline prose and pseudocode:

1. Load sealed task manifest.
2. Run or retrieve baseline control.
3. Run SAGE with current registry.
4. Expose a small relevant helper bundle.
5. Actor attempts task.
6. If a gap appears, generate candidate helper.
7. Validate helper.
8. Repair helper if needed.
9. Store accepted helper with metadata and hash.
10. Give same-task fair chance where permitted.
11. Route helper into later tasks.
12. Record gains, regressions, calls, VNC, and safety.
13. Retain, refine, park, or scale helper.

### 4. Tool Generation Methodology

Explain that helpers are side-effect-free deterministic tools. They prepare
values, select records, normalize timestamps/units, construct action arguments,
detect insufficient information, or summarize visible evidence. Original
ToolSandbox side-effect tools still execute state changes.

### 5. Validation And Repair

Explain compile checks, schema checks, negative examples, side-effect
preservation, callability checks, output-shape checks, and final-answer-ready
checks.

### 6. Leakage And Cache Controls

State:

- hidden labels and expected answers are not used for unseen evaluation;
- generated tools must not encode scenario IDs or answer strings;
- baseline/control cache is control-only;
- SAGE arms are fresh;
- OpenAI response cache disabled for evidence arms;
- RapidAPI cache is external-service fixture cache, not task-answer evidence;
- force-call diagnostics are not promotion evidence.

### 7. Evaluation Metrics

Define:

- canonical/reference score,
- outcome/task-completion score,
- exact success,
- generated-tool visibility,
- generated-tool calls,
- visible-not-called,
- called-subset outcome,
- generated-tool-attributed gains/regressions,
- runtime exceptions,
- helper side-effect incidents,
- baseline cache cached/fresh counts.

Outcome/task completion is primary. Canonical/reference is secondary but must be
reported because it is part of the original benchmark.

### 8. Statistical Plan

Prepare paired analysis language:

- paired task comparison,
- paired bootstrap confidence intervals,
- paired permutation/randomization tests,
- gain/regression/preserved counts,
- cache-variance sensitivity for cached controls.

### 9. Limitations And Scope

State clearly:

- ToolSandbox primary result uses a deep integration path.
- Import-agent portability is promising but not yet the primary evidence.
- CyberGym and tau3 show that new environments need callable helper integration
  and official scorer feedback to reproduce ToolSandbox-style lift.
- In production, hidden truth labels are not available; SAGE needs feedback
  channels such as task success/failure, official scorer output, user feedback,
  or environment telemetry.

## Required Figures

Prepare these figures as editable SVG/HTML where practical, plus PNG exports
for the dissertation draft:

1. Full SAGE + ToolSandbox architecture.
2. SAGE internal component diagram.
3. Tool generation, validation, repair, and registry lifecycle loop.
4. Evidence ladder from seed/dev diagnostics to 20/60/250/500/full validation.
5. Control-cache and SAGE-fresh evaluation discipline.
6. Generated-tool contribution flow: visible -> called -> outcome gain.
7. Portability boundary: native ToolSandbox integration vs import-agent mode.
8. One-page professional SAGE infographic.

Existing figure files:

- `docs/sage_protocol/figures/sage_peer_review_methodology_figure.svg`
- `docs/sage_protocol/figures/sage_peer_review_methodology_figure.png`
- `docs/sage_protocol/figures/sage_self_evolution_loop_publication.html`

When updating one figure format, update the companion formats.

## Required Tables

Prepare these tables:

1. Implementation variants and decision table.
2. Best 250/500 evidence table.
3. Bake-off 20/60/500 results table.
4. Helper lifecycle table.
5. Leakage-control table.
6. Cache-policy table.
7. Safety incidents and runtime exceptions table.
8. Dataset portability status table.
9. Chapter 3 definitions/glossary table.

Use color/status indicators in draft tables where useful:

- Green: validated/primary.
- Yellow: promising/needs review.
- Red: blocked or not scale-ready.
- Gray: diagnostic only.

## How To Incorporate A Later CyberGym/tau3 Success

If the engineering agent succeeds on CyberGym/tau3, do not immediately replace
the primary methodology.

Follow this process:

1. Read the new report and run artifacts.
2. Confirm the gains are generated-tool-attributed.
3. Confirm the implementation is general, not hard-coded to dataset answers.
4. Run ToolSandbox 20 and 60 no-regression checks.
5. If stronger than v71 on 60, run ToolSandbox 500.
6. If ToolSandbox 500 is equal or better and safety remains clean, update this
   handoff and Chapter 3 to make the new version the primary SAGE.
7. If it improves portability but not ToolSandbox, document it as an extension
   layer or future-work variant.

## Working Files To Maintain

Create or update these as the methodology work progresses:

- `docs/sage_protocol/chapter3_sage_methodology_system_architecture_v061.md`
- `docs/sage_protocol/chapter3_sage_methodology_working_setup.md`
- `docs/sage_protocol/chapter3_methodology_figures.md`
- `docs/sage_protocol/chapter3_methodology_agent_work_log_20260529.md`
- `docs/sage_protocol/run_ledger.md`
- `docs/sage_protocol/current_state.md`

Use a run card format for bake-off runs:

```text
### Run Card - <timestamp> - <variant>

- Branch:
- Commit:
- Implementation:
- Hypothesis:
- Command:
- Manifest:
- Sample:
- Models:
- Cache policy:
- Dashboard:
- Results:
- Tool-attributed gains:
- Tool-attributed regressions:
- Safety:
- Decision:
- Chapter 3 implication:
```

## Validation Before Delivering Chapter 3 Materials

Run:

```bash
git diff --check
```

For code touched by methodology setup:

```bash
python -m py_compile scripts/run_sage_protocol.py
```

For dashboard/standalone/import-agent material:

```bash
PYTHONPATH=src:. pytest tests/unit/test_sage_agent_standalone.py tests/unit/test_rapid_api_cache.py -q
```

If figures are updated, open the HTML/SVG/PNG in the browser and verify text
alignment, readable font size, and no overlapping elements.

## Current Bottom Line

Until a controlled bake-off proves otherwise, the correct primary SAGE for
Chapter 3 is:

```text
Native ToolSandbox self-evolving Praxis:
scripts/run_sage_protocol.py
--sage-policy self-evolving-praxis
generation-enabled online_build_* / online_build_full modes
ToolSandbox bridge + validation + registry lifecycle
```

The strongest evidence version is v71 broad500, with v70 retained as the clean
safety-reference run. The methodology should present the portable import-agent,
CyberGym, and tau3 work as important generalization and limitation evidence
unless or until those paths beat or match v71 under the bake-off protocol.
