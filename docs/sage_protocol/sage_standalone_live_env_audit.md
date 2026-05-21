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

## Dashboard Paths

- MiniGrid: `outputs/sage_agent_standalone/minigrid_lifecycle_repair_smoke12_20260521/dashboard/task_compare.html`
- CyberGym 40 before-case: `outputs/cybergym_live_sage/cybergym_live40_llm_vs_sage_20260521_164912/dashboard/task_compare.html`
- CyberGym redesign check: `outputs/cybergym_live_sage/cybergym_lifecycle_redesign_check4_20260521/dashboard/task_compare.html`
- ToolSandbox smoke: `outputs/sage_agent_standalone/toolsandbox_lifecycle_repair_smoke3_20260521/dashboard/task_compare.html`
- CyberGym 20 candidate-feedback check: `outputs/cybergym_live_sage/cybergym_lift_candidate_feedback_v3_20_20260521/dashboard/task_compare.html`
- MiniGrid maintenance: `outputs/sage_agent_standalone/minigrid_lift_maintenance_12_20260521/dashboard/task_compare.html`
- ToolSandbox maintenance: `outputs/sage_agent_standalone/toolsandbox_lift_maintenance_3_20260521_smoke/dashboard/task_compare.html`

## Caveats

CyberGym runs use real generated task directories, real `submit.sh`, and the
local live `/submit-vul` service. They are still not official final CyberGym
benchmark evidence because fix-side verification is not yet run. The 20-task
candidate-feedback run used a cached LLM baseline for all 20 controls and fresh
SAGE execution. ToolSandbox smoke is an adapter lifecycle check, not the
protected ToolSandbox benchmark protocol.

## Validation

Validation run after the change:

- Python compile checks for standalone SAGE modules and live-run scripts.
- Ruff check and format check.
- Unit tests: `27 passed`.
- `git diff --check`.
- Standalone run audit passed for MiniGrid and CyberGym live checks.
