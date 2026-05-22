# SAGE Standalone Live Environment Audit

Status: experimental standalone-agent validation, not protected final-claim evidence.

Date: 2026-05-21

## Purpose

This audit verifies that the standalone SAGE package can run against live environment
adapters with a real baseline arm and a real SAGE arm, while preserving the
environment-neutral self-evolution contract. The current focus was a generic
failure-to-redesign lifecycle repair discovered through CyberGym: weak helpers
were being labeled as needing refinement, but they were not being meaningfully
redesigned, parked, or removed from routing.

## Generic Lifecycle Change

The repair is not CyberGym-specific. SAGE now treats repeated weak natural reuse
as a lifecycle signal:

- helpers are still retained when natural reuse is strong;
- helpers with weak natural reuse are marked for refinement;
- if repair produces no distinct implementation, SAGE counts that as a failed
  redesign attempt;
- after repeated failed redesign attempts and enough weak-use evidence, SAGE
  parks the helper so routers stop exposing it;
- once parked, the gap is reopened so a replacement design can be generated;
- generic candidate-planner helpers now have a wider adaptive repair template
  that remains side-effect-free and validates as one top-level helper function.

This policy is based on observed helper performance and repair outcomes, not on
scenario IDs, labels, hidden answers, or benchmark-specific facts.

## CyberGym-Driven Generalization Update

CyberGym continues to be used as the hard test case because it combines visible
source artifacts, expensive submit-side execution, sparse successes, and many
failed candidate strings. The latest repair keeps that pressure but moves the
implementation into environment-neutral SAGE mechanisms:

- adaptive candidate-portfolio helpers synthesize visible literals,
  source-boundary values, structured-format cues, execution feedback, and
  generic parser/numeric/binary seeds;
- gated format-edge helpers are born only after multiple generic candidate
  planners already exist and a recurring visible format cue appears;
- same-task gap processing stops after a born or refined helper succeeds on the
  task that exposed the gap;
- existing helpers are refined only after enough natural-use evidence shows weak
  value;
- each task has a small helper-birth budget so one expensive environment task
  cannot consume the whole generation budget.

These changes do not reference CyberGym task IDs, hidden PoCs, labels, expected
answers, or CyberGym-only benchmark facts. They are controller, generator, and
adapter-interface policies that future source-artifact or candidate-submission
environments can reuse.

## Live Checks

| Run | Environment | Requested | Baseline | SAGE | Result |
| --- | --- | ---: | ---: | ---: | --- |
| `minigrid_lifecycle_repair_smoke12_20260521` | MiniGrid | 12 | 4/12 | 12/12 | high-performing helper kept/scaled |
| `cybergym_live40_llm_vs_sage_20260521_164912` | CyberGym live | 40 | 3/40 | 4/40 | before-case: weak tools correctly diagnosed as refine |
| `cybergym_lifecycle_redesign_check4_20260521` | CyberGym live | 4 | 0/4 | 0/4 | post-patch: weak helper generated a distinct accepted redesign |
| `toolsandbox_lifecycle_repair_smoke3_20260521` | ToolSandbox adapter smoke | 2 available | 0/2 smoke | 2/2 | selector retained; no false parking |
| `cybergym_lift_candidate_feedback_v3_20_20260521` | CyberGym live | 20 | 1/20 cached LLM baseline | 4/20 | larger signal: seven helpers born, four repairs, late-batch lift emerged |
| `minigrid_lift_maintenance_12_20260521` | MiniGrid | 12 | 4/12 LLM baseline | 12/12 | maintenance check: generic lifecycle changes preserved MiniGrid lift |
| `toolsandbox_lift_maintenance_3_20260521_smoke` | ToolSandbox adapter smoke | 3 requested, 2 available | 0/2 smoke | 2/2 | maintenance check: same-task birth and reuse still work |
| `toolsandbox_verify40_self_evolving_policy_20260521` | ToolSandbox protocol | 40 | score 0.647929; outcome 0.473734 | score 0.874999; outcome 0.907297 | high-lift self-evolving Praxis stack preserved on real ToolSandbox |
| `final_agent_cybergym_live40_20260521` | CyberGym live | 40 | 1/40 cached LLM baseline | 4/40 | live portability lift; low absolute success remains future-work target |
| `minigrid_live40_20260521` | MiniGrid | 40 | 21/40 LLM baseline | 40/40 | maintained strong third-environment performance |
| `bbh_live40_20260521` | BIG-Bench Hard | 40 | 16/40 LLM exact-answer baseline | 40/40 | fourth benchmark; reusable symbolic exact-answer helper generalized across four public task families |
| `budgeted_lifecycle_tty4_20260521` | CyberGym live fixed-side | 4 | 0/4 cached LLM baseline | 1/4 | latest general lifecycle repair preserved success while reducing helper churn |
| `budgeted_lifecycle_minigrid12_20260521` | MiniGrid | 12 | 0/12 adapter smoke | 12/12 | latest lifecycle repair preserved grid helper success |
| `budgeted_lifecycle_bbh12_20260521` | BIG-Bench Hard | 12 | 0/12 adapter smoke | 12/12 | latest lifecycle repair preserved symbolic helper success |

The completed CyberGym 40 run is the live stress case that exposed the lifecycle
issue. The 4-task post-patch run is the bounded verification that the generic
redesign path now fires without spending another full 40-task submission budget.
The later 8-task CyberGym checks were not long enough to judge the evolving
registry: both showed one SAGE success, but the 20-task follow-up showed the
useful signal emerging only after multiple birth, repair, and reuse cycles. The
20-task run is therefore the current minimum useful CyberGym signal for this
line of work.

## Audit Artifact

Machine-readable audit:

- `artifacts/sage_agent_standalone/run_audit_lifecycle_redesign_checks.json`

The audit passed for:

- `outputs/sage_agent_standalone/minigrid_lifecycle_repair_smoke12_20260521`
- `outputs/cybergym_live_sage/cybergym_lifecycle_redesign_check4_20260521`
- `outputs/cybergym_live_sage/cybergym_live40_llm_vs_sage_20260521_164912`
- `outputs/cybergym_live_sage/cybergym_lift_candidate_feedback_v3_20_20260521`
- `outputs/sage_agent_standalone/minigrid_lift_maintenance_12_20260521`
- `outputs/sage_agent_standalone/toolsandbox_lift_maintenance_3_20260521_smoke`

Additional hashes:

- CyberGym 20 batched summary SHA-256:
  `01ea9a4ea84ac0086ea758ee6a96fe24a423aa6a6a44fef60a9a84187bf04d2d`.
- CyberGym baseline cache SHA-256:
  `64f7a49421730d029783fcb66bb3e7f0cedd6ce74f60e86550586d37fe10945a`.
- MiniGrid maintenance summary SHA-256:
  `5a5c0af188ee31773e251963fbb3888fcbb7ec84d6a5fad2d043ef43c5979b95`.
- ToolSandbox maintenance summary SHA-256:
  `fea45a95f1cb6c211ef2d01afbd57a969fb925393be79045e73aa60895a45841`.
- Four-environment live40 summary SHA-256:
  `5987f4c09d845ac34c9c89e9acb8139cc5e116a0d2774ab0b978fc526065a2b2`.
- Budgeted lifecycle generalization audit SHA-256:
  `2ee196755eb2747e36da232ed4a0ecf3c67acbf9c1651a1b2d64aab3f43fa086`.
- Latest fixed-side CyberGym budgeted lifecycle summary SHA-256:
  `f3916ebee4c640b3f682d4d74bae28055ca6cbf8adb0d7caf76ddaa303d8a3b6`.

## Dashboard Paths

- MiniGrid: `outputs/sage_agent_standalone/minigrid_lifecycle_repair_smoke12_20260521/dashboard/task_compare.html`
- CyberGym 40 before-case: `outputs/cybergym_live_sage/cybergym_live40_llm_vs_sage_20260521_164912/dashboard/task_compare.html`
- CyberGym redesign check: `outputs/cybergym_live_sage/cybergym_lifecycle_redesign_check4_20260521/dashboard/task_compare.html`
- ToolSandbox smoke: `outputs/sage_agent_standalone/toolsandbox_lifecycle_repair_smoke3_20260521/dashboard/task_compare.html`
- CyberGym 20 candidate-feedback check: `outputs/cybergym_live_sage/cybergym_lift_candidate_feedback_v3_20_20260521/dashboard/task_compare.html`
- MiniGrid maintenance: `outputs/sage_agent_standalone/minigrid_lift_maintenance_12_20260521/dashboard/task_compare.html`
- ToolSandbox maintenance: `outputs/sage_agent_standalone/toolsandbox_lift_maintenance_3_20260521_smoke/dashboard/task_compare.html`
- ToolSandbox live40: `outputs/sage_agent_standalone/toolsandbox_verify40_self_evolving_policy_20260521/mechanism_40_20260521_175250/dashboard/task_compare.html`
- CyberGym live40: `outputs/cybergym_live_sage/final_agent_cybergym_live40_20260521/dashboard/task_compare.html`
- MiniGrid live40: `outputs/sage_agent_standalone/minigrid_live40_20260521/dashboard/task_compare.html`
- BIG-Bench Hard live40: `outputs/sage_agent_standalone/bbh_live40_20260521/dashboard/task_compare.html`
- Latest CyberGym lifecycle repair: `outputs/cybergym_live_sage/budgeted_lifecycle_tty4_20260521/dashboard/task_compare.html`
- Latest MiniGrid maintenance: `outputs/sage_agent_standalone/budgeted_lifecycle_minigrid12_20260521/dashboard/task_compare.html`
- Latest BIG-Bench Hard maintenance: `outputs/sage_agent_standalone/budgeted_lifecycle_bbh12_20260521/dashboard/task_compare.html`

## Caveats

CyberGym runs use real generated task directories, real `submit.sh`, and the
local live `/submit-vul` service. They are still not official final CyberGym
benchmark evidence because fix-side verification is not yet run. The 20-task
candidate-feedback run used a cached LLM baseline for all 20 controls and fresh
SAGE execution. ToolSandbox smoke is an adapter lifecycle check, not the
protected ToolSandbox benchmark protocol.

The BIG-Bench Hard 40-task run intentionally produced only one generated helper.
That is not evidence of weak adaptation in this case: the sampled BBH split was
balanced across four public task families, and one symbolic exact-answer helper
passed validation and solved all four deterministic visible formats. If future
BBH work targets broader language, commonsense, or multi-choice tasks, the
adapter should expose those public families as separate gap types so SAGE can
birth additional helper families where a single deterministic parser is no
longer sufficient.

## Validation

Validation run after the lifecycle and candidate-portfolio changes:

- Python compile checks for standalone SAGE modules and live-run scripts.
- Ruff check.
- Unit tests: `21 passed`.
- `git diff --check`.
- Standalone run audit passed for CyberGym live, MiniGrid, and BIG-Bench Hard
  checks. The audit remains strict for CyberGym live comparisons and now
  classifies non-CyberGym adapter smoke baselines as non-claim lifecycle checks
  instead of treating them as CyberGym-style LLM baselines.
