# Current Publication State

Last updated: 2026-09-04.

## Status

The publication cleanup, protocol correction, and v4 release-input chain are
complete. No current-release full validation run, selector comparison, or
confirmatory paper campaign has started. Live execution still requires explicit
researcher approval.

The July campaign, the early phase/final reports, the v061 materials, and
publication validation samples 01--03 are archival development records. They
are not current release evidence and must not supply paper values, release
thresholds, or control rows. In particular, sample 03 covered only the older
partial outcome-evaluator surface and did not use the current concurrent-pair
protocol.

The route-independent v4 evaluator and timezone-aware historical rescore passed
independent checks. Their identities and outcome-only engineering floor are
frozen in the
[`v4 rescore summary`](historical_outcome_rescore_v4_summary.json),
[`v4 thresholds`](publication_validation_thresholds_v4.json), and
[`2026-09-03 release manifest`](publication_release_manifest_20260903.json).
The rescore uses New York for the baseline and replications 6--10 and Los
Angeles for replications 1--5, as inferred independently from each arm's raw
valid time-conversion traces. It remains a terminal-trajectory historical
reference only: it does not repair the superseded campaign's cache, online
feedback, tool-birth, routing, or lifecycle confounding and is not confirmatory
evidence.

## Active Performance Contract

Outcome/task-completion similarity is the sole publication performance
endpoint. Every task in both arms must receive an outcome from the same frozen,
route-independent evaluator. Route similarity, native-tool sequence,
generated-tool counts, selection counts, and reuse counts are diagnostics; they
do not pass or fail a publication claim or release gate.

A validated generated tool may be the terminal action when it produces the
correct final state. No separate visible native-tool follow-up is required.
Final-state correctness, minefield checks, allow-list enforcement, runtime
safety, and correct abstention remain mandatory.

## Active Execution Contract

The sole publication launcher is `scripts/run_native_action_4omini_ab.sh`, backed by
`scripts/run_sage_protocol.py`. Strict publication execution requires:

- the pinned benchmark order, fixed clock, environment, and read-only external
  fixture;
- no control-result cache, task-result cache, stored whole-response replay,
  persistent generated-output replay, partial-row resume, or cross-run failure
  memory;
- a clean Git tree and the validated publication environment;
- complete task and model-call provenance; and
- a Task Compare dashboard whose served root and bytes are verified and opened
  in the external/default browser before the first model request for each live
  pair.

The ordinary publication comparison runs a fresh non-learning control and the
policy-selection SAGE arm concurrently in isolated child processes. Online
reflection consumes the same-run control row at the matching task boundary and
fails closed on missing, duplicate, out-of-order, extra, or unconsumed rows.

The actor-selection experiment contains two live concurrent pairs:

1. fresh non-learning control versus policy-selection SAGE; and
2. fresh independent non-learning control versus `sage_auto_selection`.

The second pair starts only after the policy arm has captured the exact
per-task actor-ready inventory needed for matched auto replay. Its fresh control
runs concurrently with auto but does not influence auto's inventory or
execution. The experiment produces three Task Compare views: control versus
policy, independent control versus auto, and policy versus auto. The first two
open before their pair's first model request; the causal policy-versus-auto view
opens after both treatment arms finish.

## Next Authorized Steps

1. Complete the final static, focused, packaging, link, and publication-input
   checks against the frozen v4 chain.
2. Present the frozen release and pilot plan for researcher review.
3. Only after approval, run the sealed representative selector pilot.
4. Only after a passing pilot and separate explicit approval, run the complete
   matched comparison and then prepare the paper campaign manifest.

Preparation and verification are not execution authorization. Failed or
interrupted arms are preserved for review and are never silently replaced.

## Active Documents

- `README.md`
- `docs/sage_protocol/00_global_working_agreement.md`
- `docs/sage_protocol/README.md`
- `docs/sage_protocol/publication_execution_policy_20260903.json`
- `docs/sage_protocol/publication_release_manifest_20260903.json`
- `docs/sage_protocol/historical_outcome_rescore_v4_summary.json`
- `docs/sage_protocol/publication_validation_thresholds_v4.json`
- `docs/sage_protocol/publication_input_manifest_20260901.json`
- `docs/sage_protocol/publication_checkpoint_amendment_20260902.json`
- `docs/sage_protocol/publication_cleanup_audit_20260901.md` (historical audit
  evidence only; not an execution guide)
- `docs/sage_protocol/chapter4_4omini_data_collection_plan.md`
- `docs/sage_protocol/chapter4_results_completed.tex` (pending-rerun scaffold)

## Decision

`READY_FOR_RESEARCHER_REVIEW_AFTER_FINAL_CHECKS; DO_NOT_START_SELECTOR_PILOT_OR_FULL_RUN_WITHOUT_EXPLICIT_RESEARCHER_APPROVAL`
