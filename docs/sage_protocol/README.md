# SAGE Protocol Documentation

This directory contains the active publication protocol plus preserved
development records. Start with `current_state.md`; do not infer current policy
from a file merely because it remains in the repository.

## Active Publication Documents

- `current_state.md` — current release status, blockers, and approval boundary.
- `00_global_working_agreement.md` — rules that govern every active run.
- `publication_execution_policy_20260903.json` — machine-readable execution,
  concurrency, dashboard, outcome, and actor-selection contract.
- `publication_release_manifest_20260903.json` — active content-addressed v4
  publication release chain.
- `historical_outcome_rescore_v4_summary.json` — compact, independently checked
  terminal-trajectory rescore and per-arm timezone provenance.
- `publication_validation_thresholds_v4.json` — active outcome-only engineering
  validation thresholds.
- `publication_input_manifest_20260901.json` — immutable benchmark, fixture, and
  checkpoint inputs.
- `publication_checkpoint_amendment_20260902.json` — correction to the frozen
  checkpoint's generator-memoization policy.
- `chapter4_4omini_data_collection_plan.md` — pending-rerun evidence plan.
- `chapter4_results_completed.tex` — intentionally result-free Chapter 4
  scaffold until the approved campaign completes.
- `publication_cleanup_audit_20260901.md` — preserved discovery audit. It is
  historical evidence, not current execution guidance.

The v4 evaluator, rescore summary, thresholds, and extending release manifest
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
- Every live pair opens its verified, current-run Task Compare view in the
  external/default browser before either model process starts.
- A generated tool may safely complete the requested action directly; no
  visible native-tool follow-up is required.
- Final-state, minefield, allow-list, runtime, provenance, and correct
  abstention checks remain mandatory.
- No full run begins without explicit researcher approval.

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
