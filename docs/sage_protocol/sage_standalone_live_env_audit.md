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

The completed CyberGym 40 run is the live stress case that exposed the lifecycle
issue. The 4-task post-patch run is the bounded verification that the generic
redesign path now fires without spending another full 40-task submission budget.

## Audit Artifact

Machine-readable audit:

- `artifacts/sage_agent_standalone/run_audit_lifecycle_redesign_checks.json`

The audit passed for:

- `outputs/sage_agent_standalone/minigrid_lifecycle_repair_smoke12_20260521`
- `outputs/cybergym_live_sage/cybergym_lifecycle_redesign_check4_20260521`
- `outputs/cybergym_live_sage/cybergym_live40_llm_vs_sage_20260521_164912`

## Dashboard Paths

- MiniGrid: `outputs/sage_agent_standalone/minigrid_lifecycle_repair_smoke12_20260521/dashboard/task_compare.html`
- CyberGym 40 before-case: `outputs/cybergym_live_sage/cybergym_live40_llm_vs_sage_20260521_164912/dashboard/task_compare.html`
- CyberGym redesign check: `outputs/cybergym_live_sage/cybergym_lifecycle_redesign_check4_20260521/dashboard/task_compare.html`
- ToolSandbox smoke: `outputs/sage_agent_standalone/toolsandbox_lifecycle_repair_smoke3_20260521/dashboard/task_compare.html`

## Caveats

CyberGym runs use real generated task directories, real `submit.sh`, and the
local PoC database, but they are still not official final CyberGym benchmark
evidence because fix-side verification is not yet run. ToolSandbox smoke is an
adapter lifecycle check, not the protected ToolSandbox benchmark protocol.

## Validation

Validation run after the change:

- Python compile checks for standalone SAGE modules and live-run scripts.
- Ruff check and format check.
- Unit tests: `27 passed`.
- `git diff --check`.
- Standalone run audit passed for MiniGrid and CyberGym live checks.
