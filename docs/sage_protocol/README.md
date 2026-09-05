# SAGE Protocol Documentation

This directory contains the active publication protocol plus preserved
development records. Start with `current_state.md`; do not infer current policy
from a file merely because it remains in the repository.

## Active Publication Documents

- `current_state.md` — current release status, blockers, and approval boundary.
- `00_global_working_agreement.md` — rules that govern every active run.
- `publication_execution_policy_20260904.json` — machine-readable execution,
  concurrency, dashboard, outcome, and actor-selection contract.
- `publication_release_manifest_20260905.json` — active content-addressed v5
  publication release chain.
- `production_core_manifest_20260905.json` — exact 32,540-line scientific-core
  file inventory and source checkpoint.
- `historical_outcome_rescore_v5_summary.json` — compact, independently checked
  terminal-trajectory rescore and per-arm timezone provenance.
- `publication_validation_thresholds_v5.json` — active outcome-only engineering
  validation thresholds.
- `outcome_discrepancy_resolution_v5_summary.json` — compact read-only audit
  comparing the current and historical trajectories under the same v5 evaluator,
  with content-addressed compressed raw reports and a full exact-name crosswalk.
- `publication_input_manifest_20260901.json` — immutable benchmark, fixture, and
  checkpoint inputs.
- `publication_checkpoint_amendment_20260902.json` — correction to the frozen
  checkpoint's generator-memoization policy.
- `chapter4_4omini_data_collection_plan.md` — pending-rerun evidence plan.
- `chapter4_results_completed.tex` — intentionally result-free Chapter 4
  scaffold until the approved campaign completes.
- `publication_cleanup_audit_20260901.md` — preserved discovery audit. It is
  historical evidence, not current execution guidance.

The v5 evaluator, rescore summary, thresholds, and extending release manifest
are frozen and independently checked. The historical rescore is a
terminal-trajectory reference with per-arm inferred timezones; it is not a
campaign replay, cannot repair historical online confounding, and is not
confirmatory evidence.

## Non-Negotiable Current Rules

- Outcome/task completion is the only publication performance endpoint.
- Every task in both arms is evaluated by the same frozen, route-independent
  outcome evaluator.
- Each live non-learning control and its SAGE arm run concurrently in isolated
  child processes.
- The selector experiment has two concurrent pairs and three Task Compare
  views, as frozen in the execution policy.
- Recommending its 1,032-task comparison requires the pilot auto arm to call a
  generated tool in at least one scenario with zero generated-tool execution-
  failure scenarios. This is mechanism eligibility, not outcome performance.
- Auto responses are never truncated or postprocessed. Parallel calls are
  preserved, while execution-equivalent identical-content permutations are
  deduplicated symmetrically for every arm; tool-call IDs alone do not define a
  distinct execution order.
- Every live pair opens its verified, current-run Task Compare view in the
  external/default browser before either model process starts.
- A generated tool may safely complete the requested action directly; no
  visible native-tool follow-up is required.
- Final-state, minefield, allow-list, runtime, provenance, and correct
  abstention checks remain mandatory.
- No full run begins without explicit researcher approval.
- Generator contract and repair analyses are live on every publication request;
  no within-run analysis response is memoized.

## Archival Development Records

The following retained families are prominently superseded as current protocol
or paper evidence:

- phase instructions `01_phase_A_*` through `06_phase_F_*` and all
  `phase_*_report.md` files, execution prompts, and cohort manifests;
- `final_*` reports and the former final evidence index/package;
- publication validation samples 01--03;
- v061 working-methodology documents and figures;
- pre-v4 historical outcome-rescore, threshold, and release-chain drafts; and
- older `v2*`, Praxis, standalone, CyberGym, tau, MiniGrid, BBH, and custom-task
  experiment records.

They remain available to audit development history. Their commands, paths,
metric gates, numeric values, source-tree claims, and decision labels must not
be copied into an active run or the paper. Some archival commands refer to
launchers and packages that have intentionally been removed.

## Execution Boundary

Read and acknowledge `00_global_working_agreement.md` before any phase or run.
Use only the publication launcher documented in the repository root README.
Preparation and verification may proceed without model calls; a live full run
requires explicit researcher approval. Preserve all outputs in new timestamped
directories and never overwrite an archival run.
