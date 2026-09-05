# Chapter 4 Outcome Evidence Collection Plan

## Status

This is the active, pending-rerun plan. No current-release full validation run,
actor-selection comparison, or confirmatory campaign has started. Publication
validation samples 01--03 and the July campaign are archival development
records, not current evidence. Execution of any full run requires explicit
researcher approval.

The route-independent v5 evaluator, timezone-aware historical rescore,
outcome-only thresholds, and release-chain hashes have passed independent
checks and are frozen in `publication_release_manifest_20260905.json`. The
historical rescore supplies only a conservative lower-envelope engineering
reference. It is not confirmatory evidence and does not repair the superseded
campaign's cache or online-lifecycle confounding.

## Sole Performance Endpoint

Outcome/task-completion similarity is the only publication performance metric.
The same frozen evaluator must return a value for every task in every compared
arm. The evaluator judges the achieved answer or final state independently of
the tool route used to reach it.

Tool visibility, selection, calls, generated-tool births, acceptance, reuse,
and route compatibility are mechanism diagnostics. They may explain an outcome
but cannot pass or fail a release or hypothesis decision.

A validated generated tool may safely complete the requested action directly.
It need not be followed by a visible native-tool call. Final-state correctness,
minefield checks, allow-list enforcement, runtime safety, and correct abstention
remain mandatory.

## Frozen Inputs

Before any model request, the release must bind and verify:

- the clean Git commit and tree;
- the publication Python environment and dependency lock;
- the complete benchmark bytes and ordered task names;
- the fixed ToolSandbox clock and timezone;
- the sanitized external-service fixture in read-only mode;
- actor, user, and generation model settings;
- retry and timeout settings;
- evaluator version, contract digest, and source digest;
- the outcome-only validation thresholds; and
- all cache, resume, diagnostic-exposure, and force-call settings.

Strict runs prohibit control-result reuse, task-result reuse, stored
whole-response replay, persistent generated-output replay, partial-row resume,
within-run generator-analysis memoization, and cross-run failure memory.
Provider-managed prompt-prefix computation is
recorded separately and is not treated as a stored model response.

## Concurrent Publication Pair

Every ordinary online or frozen publication comparison starts a fresh
non-learning control and its SAGE condition as concurrent isolated child
processes. Positive process-interval overlap, distinct process identifiers,
complete child status records, identical task order, and one-to-one outcome
coverage are required.

For online SAGE, the control streams its result at each matching task boundary.
SAGE waits when necessary and consumes exactly one same-run control row for
that task. Missing, duplicate, out-of-order, extra, or unconsumed rows fail the
run. Online runs start from an empty registry.

A frozen-registry run copies only the registry produced by its verified paired
online run. Generation, candidate repair, and online reflection are disabled,
but its fresh control and frozen SAGE arm still run concurrently.

## Matched Actor-Selection Experiment

The actor-selection experiment tests model selection from the exact
SAGE-routed inventory. It contains two live concurrent pairs:

1. a fresh non-learning control with policy-selection SAGE; and
2. a fresh independent non-learning control with `sage_auto_selection`.

The policy arm captures the exact actor-ready state for each task after
same-task tool birth, including native and generated schemas and their order.
For this selector experiment only, the policy arm is an inventory donor. Its
runtime integrity gate must pass, while the ordinary control-versus-policy
outcome-threshold result and reasons are recorded as diagnostics rather than
used to stop the matched auto comparison. Ordinary non-donor publication runs
continue to apply the frozen outcome-performance thresholds.
After that authority exists, the auto replay restores and verifies those bytes
for the matching task. Auto generation, reflection, and lifecycle mutation are
disabled so that policy and auto receive the same inventory. The second pair's
fresh control runs concurrently with auto and has no path into auto's inventory
or execution.

Every auto actor request must record `choice_mode="auto"`, omit a named
`tool_choice`, and bind the exact native and generated schema bundle sent to the
model. Before the complete comparison can be proposed, the pilot auto arm must
call a generated tool in at least one scenario and must have zero generated-tool
execution-failure scenarios. This is a mechanism eligibility check that the
selection treatment was exercised and stable; it is not an outcome-performance
gate and imposes no policy-versus-auto outcome threshold.

The auto arm preserves every model-returned parallel tool call without
response postprocessing or truncation. ToolSandbox applies one symmetric
all-arm ordering rule: validate every distinct call-content order, deduplicate
only execution-equivalent permutations of identical call contents, and do not
treat tool-call IDs alone as distinct execution orders.

## Task Compare Requirement

Every live pair creates `dashboard/task_compare.html`, verifies that the server
root and served bytes belong to that run, records a receipt, and opens the view
in the external/default browser before either model process starts.

The actor-selection experiment produces three views:

- fresh control versus policy-selection SAGE, opened before the first pair;
- fresh independent control versus `sage_auto_selection`, opened before the
  second pair; and
- policy-selection SAGE versus `sage_auto_selection`, opened after both
  treatment arms complete.

All three views expose task outcomes, transcripts, routed schemas, and tool
execution evidence. The third view is the causal selection comparison; the two
fresh-control views show each arm's absolute outcome behavior.

## Staged Execution and Approval

The intended order is:

1. **Complete:** freeze and verify the corrected evaluator and publication
   release chain;
2. run focused tests, the full local suite, packaging checks, and clean-clone
   publication-input verification;
3. obtain researcher approval for the sealed representative selector pilot;
4. run and verify that pilot;
5. obtain separate researcher approval for a complete fresh-control validation
   and matched actor-selection comparison;
6. after a passing complete validation, prepare and verify a new paper campaign
   manifest without starting it; and
7. obtain explicit researcher approval before the confirmatory campaign.

Preparation never authorizes execution. A failed or interrupted arm and its
logs are preserved for review; it is not silently retried, excluded, or
replaced.

## Confirmatory Paper Campaign

The replacement campaign will contain ten independently evolved online
registries and ten matched frozen-registry evaluations. Each online and frozen
condition has its own concurrent fresh non-learning control. All arms use the
same frozen release inputs and complete benchmark order.

The campaign manifest may be prepared only from a passing current-release full
validation report:

```bash
make prepare-paper-rerun \
  SAMPLE_REPORT=outputs/publication_validation/<approved-run>/native_action/<protocol-run>/publication_validation_report.json \
  CAMPAIGN_ARGS='--campaign-id chapter4_outcome_rerun_<date> --expected-online-runs 10'
```

This command prepares artifacts but makes no model calls. The campaign runner's
execution acknowledgement must not be supplied until the researcher separately
approves the final run.

## Analysis and Paper Replacement

The analysis pipeline consumes only the versioned campaign manifest and its
verified raw artifacts. It will compute the preregistered outcome comparisons,
uncertainty estimates, paired gain/preserved/regression counts, frozen-registry
retention, and generated-tool-called subset. Integrity and safety findings are
reported alongside the outcomes.

The paper renderer must replace the pending scaffold mechanically from the new
structured evidence. Archived values, screenshots, and table images are never
copied forward by hand. Until every required arm verifies, Chapter 4 remains
explicitly pending and makes no hypothesis decision.

## Decision

`READY_FOR_RESEARCHER_REVIEW_AFTER_FINAL_CHECKS; DO_NOT_START_SELECTOR_PILOT_OR_FULL_RUN_WITHOUT_EXPLICIT_RESEARCHER_APPROVAL`
