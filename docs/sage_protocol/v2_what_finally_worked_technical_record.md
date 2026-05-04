# What Finally Got SAGE V2 Working

- Date: 2026-05-04
- Formal 250 decision: `formal 250 passed`
- Winning commit: `39d5647 Validate SAGE v2 best3 tool portfolio`
- Evidence-lock commit: `bc8549e Lock SAGE v2 formal 250 evidence`
- Winning registry: `artifacts/registry_best3_resolve_select_relative/registry_manifest.json`
- Frozen claim registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Registry SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`

## Short Answer

The final pass came from stopping the broad "turn on every promising idea" strategy and switching to a conservative, evidence-backed three-helper portfolio with repaired routing, contribution accounting, and side-effect validation.

The final portfolio was:

1. `resolve_search_window_or_bounds`
2. `select_record_by_timestamp_extreme`
3. `relative_day_time_to_timestamp`

The broad, harmful `prepare_reminder_creation_args` helper was removed from the final validation portfolio. That was critical. It worked in narrow reminder cohorts but caused real side-effect follow-up failures in broad runs.

The final 250-task result:

- Control outcome: `0.3930079367`
- SAGE outcome: `0.4736471752`
- Outcome delta: `+0.0806392385`
- Relative outcome lift: `+20.52%`
- Reference/canonical similarity delta: `+0.0659853171`
- Exact successes: `31 -> 40`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- Route-mismatch qualification needed: `false`

## The Core Lesson

SAGE started working when the project stopped treating "accepted generated tool" as the success signal and instead required all of the following:

- The helper must be visible only in relevant tasks.
- The helper must actually be called.
- The called-helper subset must improve outcome/task completion.
- The helper must not replace required downstream side-effect tools.
- Side-effect preservation must be checked from the actual trace, not inferred from the helper spec.
- Canonical/reference scoring and outcome/task-completion scoring must be reported separately.
- Route-mismatch accounting must explain divergence without inflating canonical scores.
- A helper that works in a focused lane but harms broad validation must be suppressed from the claim registry.

The winning result was not caused by generating many tools. It was caused by retaining a small number of deterministic tools that compressed recurring failure modes and were adopted in future tasks.

## Main Code Paths That Mattered

### 1. Protocol runner and scoring/accounting

Primary file:

- `scripts/run_sage_protocol.py`

Important functions and sections:

- `_route_mismatch_qualified(comparison)`
- protocol-gate logic around outcome/canonical deltas
- control-cache planning and reporting around `plan_control_cache(...)`
- helper contribution export via `write_helper_contribution_summary(...)`
- protocol manifest fields for registry digest, generation mode, cache source, dashboard paths, and helper contribution paths

What changed conceptually:

- Outcome/task-completion became the primary metric for SAGE usefulness.
- Reference/canonical similarity remained a benchmark-reference metric.
- The runner records `route_mismatch_qualified` instead of silently treating canonical loss as task failure or silently inflating the score.
- Every run now exports `helper_contribution_summary.json`, `control_cache_report.json`, and protocol metadata needed to audit claims.
- The formal 250 did not need route-mismatch qualification because both outcome and reference/canonical similarity improved.

Why it mattered:

Before this, generated-helper routes could look worse than baseline when they bypassed expected canonical milestones. After this, the project could distinguish:

- true task failure
- valid helper substitution
- canonical-route mismatch
- final-state/task-completion success
- helper-caused regression

This kept the claim conservative while avoiding false negatives against deterministic helper paths.

### 2. Helper contribution export

Primary file:

- `src/sage_ts/evaluation/helper_contribution.py`

Important functions:

- `build_helper_contribution_summary(...)`
- `write_helper_contribution_summary(...)`

What it reports:

- visible scenarios
- called scenarios
- visible-not-called scenarios
- failed-attempt scenarios
- called-subset outcome delta
- called-subset reference/canonical delta
- visible-not-called subset deltas
- side-effect incidents
- runtime incidents
- retained-helper versus newly generated-helper contribution
- registry size and runtime bundle size
- accepted-but-uncalled tools

Why it mattered:

This was the main evidence that the formal 250 victory was tool-driven rather than aggregate model variance.

Formal 250 helper contribution:

| Helper | Visible | Called | Visible-not-called | Called outcome delta | Called reference/canonical delta | Side-effect incidents | Runtime incidents |
|---|---:|---:|---:|---:|---:|---:|---:|
| `relative_day_time_to_timestamp` | 32 | 29 | 3 | `+0.1389` | `+0.0161` | 0 | 0 |
| `resolve_search_window_or_bounds` | 72 | 42 | 30 | `+0.2480` | `+0.1616` | 0 | 0 |
| `select_record_by_timestamp_extreme` | 32 | 27 | 5 | `+0.1188` | `+0.2746` | 0 | 0 |

Aggregate helper evidence:

- Unique helper-visible scenarios: `112`
- Unique helper-called scenarios: `98`
- Called-helper subset mean outcome delta: `+0.1823`
- No-called-helper subset mean outcome delta: `-0.0061`
- Top-50 outcome gains with a called helper: `33`

This showed that the pass was concentrated where helpers were actually used.

### 3. Side-effect follow-up accounting

Primary file:

- `src/sage_ts/adapters/sage_run_adapter.py`

Important functions:

- `_conversation_generated_tool_attempts(...)`
- `_conversation_generated_tool_results(...)`
- `_helper_requires_side_effect_followup(...)`
- `_helper_forbids_side_effect_followup(...)`
- `_assistant_tool_names(...)`
- `_next_assistant_tool_names(...)`
- `_side_effect_followup_failures(...)`

The key repair was sequence-aware side-effect follow-up checking.

The earlier checker could misclassify traces because it did not distinguish these cases clearly enough:

1. Helper succeeds and says a side-effect tool should be called, but SAGE never calls it.
2. Helper abstains, SAGE asks/does a prerequisite, then later correctly calls the side-effect tool.
3. Helper abstains, but SAGE bypasses the abstention and immediately calls a side-effect tool unsafely.

The fixed logic checks assistant tool-call sequence instead of only checking whether a side-effect call appears somewhere in the transcript.

Why it mattered:

This did two things:

- It prevented false side-effect violation reports when the agent correctly handled a prerequisite before a side effect.
- It exposed real `prepare_reminder_creation_args` failures where the helper returned `should_call_add_reminder=True` but `add_reminder` was skipped or delayed incorrectly.

That evidence justified suppressing `prepare_reminder_creation_args` from the final broad portfolio.

Relevant tests:

- `tests/unit/test_sage_run_adapter.py`

Important test cases added:

- helper abstain -> prerequisite -> side-effect allowed
- helper abstain -> direct side-effect flagged
- helper success -> missing side-effect flagged

### 4. Runtime tool injection and affordance text

Primary file:

- `src/sage_ts/runtime/toolsandbox_integration.py`

Important functions:

- `compile_registry_tool(...)`
- `inject_registry_tools_into_context(...)`
- helper visibility/routing checks inside the runtime injection path
- generated helper description/affordance construction

What changed conceptually:

- Non-reminder helper instructions were repaired so they no longer described an impossible reminder-style call path using fields like `should_call_add_reminder` or generic `<tool>_kwargs` when the helper was not a reminder helper.
- Helpers were exposed only when their required downstream original ToolSandbox tools were available.
- Record-selection and search-window helpers were ordered conceptually: search-window helper first, original search tool second, selector helper third.
- Helpers were hidden or suppressed on insufficient-information and unrelated tasks.

Why it mattered:

Several earlier generated tools were accepted but not called because the model saw confusing or wrong affordance text. The tools were technically visible but not usable from the model's point of view.

The final pass required the helpers to be understandable in the exact context where the model sees them.

### 5. Runtime routing scorer

Primary file:

- `src/sage_ts/runtime/routing_scorer.py`

Important functions:

- `_latest_helper_contribution_summary(...)`
- runtime helper scoring and suppression logic

What changed conceptually:

- Tool exposure stopped being based only on broad helper-trigger strata.
- Routing considered evidence such as recent called-subset contribution, visible-not-called risk, negative triggers, failure-memory risk, and required input/tool availability.
- The runtime bundle stayed bounded.

Why it mattered:

Earlier runs had too many visible-not-called helpers. That polluted the model context and made generated tools look like noise.

The final portfolio still had some visible-not-called cases, especially for `resolve_search_window_or_bounds`, but the exposure level was controlled enough for broad validation to pass.

### 6. Task-stratum and helper-fit mapping

Primary file:

- `src/sage_ts/evaluation/task_strata.py`

Important functions:

- `base_task_family(...)`
- `classify_task_strata(...)`
- `expected_helper_fit(...)`
- `expected_birth_opportunities(...)`

What changed conceptually:

- Scenario families were mapped to expected helper-fit lanes.
- This allowed manifests and reports to identify where retained helpers should apply and where no current helper fit existed.
- It also allowed cohort quality reports to reveal whether a run was genuinely broad or inflated by near-duplicate/easy tasks.

Why it mattered:

The failed 250 with the best-two portfolio showed a coverage problem, not a stability problem. The analysis showed that many remaining failures were in relative day/time tasks. That led to testing and retaining `relative_day_time_to_timestamp`, which converted the 250 from `+6.15%` relative lift to `+20.52%` relative lift.

Key lesson:

The task-stratum reports made it clear that the next fix should be coverage of a repeated failure lane, not more tuning of the already-good helpers.

### 7. Candidate gate and generated-tool contract

Primary files:

- `src/sage_ts/adequacy/candidate_gate.py`
- `src/sage_ts/generation/tool_generator.py`
- `src/sage_ts/generation/tool_spec.py`
- `src/sage_ts/adequacy/failure_memory.py`
- `src/sage_ts/adequacy/inadequacy_classifier.py`

Important functions and concepts:

- `evaluate_candidate_gate(...)`
- `ToolGenerationRequest.prompt(...)`
- `parse_generated_tool_json(...)`
- mechanism-level failure-memory checks
- generated spec fields for triggers, abstention, side-effect preservation, canonical substitution risk, and downstream original tools

What changed conceptually:

- The generator/gate was strengthened to prefer tools that compress multiple steps and apply across task families.
- Candidate specs had to declare positive triggers, negative triggers, abstain behavior, side-effect preservation, and canonical-route substitution risk when relevant.
- Failure memory was mechanism-based, not name-based.
- Candidate repair/contract synthesis was useful in experiments, but the final winning formal run used a conservative frozen registry rather than broad online generation.

Why it mattered:

This did not directly mean every accepted new tool was useful. In fact, several accepted tools remained uncalled. The value was that the framework became able to reject thin, underspecified, or unsafe helpers and preserve only the tools with actual broad value.

### 8. Experimental matrix and conservative stack selection

Primary file:

- `scripts/run_v2_experimental_matrix20.py`

Important function:

- `_select_combined_features(...)`

What changed conceptually:

- The matrix tested ideas separately instead of assuming the combined stack was best.
- The combined stack was selected conservatively from variants that had positive outcome, real calls, acceptable visible-not-called behavior, no side-effect incidents, and no runtime incidents.
- The project stopped treating "more V2 ideas enabled" as better.

Why it mattered:

Earlier combined stacks were worse than focused variants because they increased visibility/context pollution. The final result came from selecting the smallest safe set that actually moved outcome.

### 9. Control baseline cache

Primary file:

- `src/sage_ts/evaluation/control_baseline_cache.py`

Important functions:

- `plan_control_cache(...)`
- `build_control_cache_report(...)`
- cache collection and compatibility checks

What changed conceptually:

- Control baseline runs are stored after implementation.
- Cache eligibility requires at least 3 compatible complete control runs.
- Compatibility includes scenario checksum, initial-state checksum, model/version/params, prompt hashes, runner version, scorer version, ToolSandbox version, manifest checksum, and no unresolved runtime/scoring/side-effect issue.
- Formal runs report fresh/cached/mixed control source.

Why it mattered:

This did not create the final 250 lift. The formal 100 and 250 controls were fresh because no compatible cached controls were eligible for those new manifest hashes. But the cache made future repeated baselines cheaper and gave the reports explicit cache provenance.

### 10. Dashboard/export fixes

Primary files:

- `src/sage_ts/dashboard/exporters.py`
- `src/sage_ts/dashboard/template.py`
- `src/sage_ts/dashboard/task_focus_template.py`
- `scripts/run_sage_protocol.py`

What changed conceptually:

- Every major run writes dashboard URLs and machine-readable dashboard data.
- Dashboards include cache source and generated-tool evidence.
- Runs were verified with HTTP `200` before opening.

Why it mattered:

Earlier dashboard failures made it hard to trust the reports. The final process required the two main dashboards to be present and loadable for each major run.

## What Did Not Work

### Broad-active `prepare_reminder_creation_args`

This helper was useful in focused reminder creation tests but failed broad validation.

Observed problems:

- It could return `should_call_add_reminder=True` without a correct downstream `add_reminder` call.
- It encouraged complex timing/location paths where side-effect sequencing became fragile.
- It produced real side-effect preservation failures in broad runs.

Decision:

- Suppress from final broad claim portfolio.
- Keep only as diagnostic or future repair target.

### Full combined V2 experimental stack

The combined stack did not outperform the conservative stack.

Observed problems:

- More helper visibility increased context/routing pollution.
- Accepted tools were sometimes visible but not called.
- Some candidates improved contract validity but did not improve adoption.

Decision:

- Use only the best-performing, adopted, safe helpers for formal validation.

### `days_between_timestamps`

This helper was safe but weak.

Observed problems:

- Focused evidence showed limited called-subset contribution.
- It did not address the largest remaining negative lane after the best-two 250.

Decision:

- Exclude from final broad portfolio.

### Remove-reminder recency routing patch

The patch improved visibility but not adoption enough.

Observed problems:

- `resolve_search_window_or_bounds` was visible but often not called.
- The selector could be called after the wrong search window, so sequencing remained incomplete.

Decision:

- Treat as V2.0 routing/affordance work, not part of the v1.0 claim.

## Why The Three Winning Helpers Worked

### `resolve_search_window_or_bounds`

Core value:

- Compresses current-time lookup, phrase interpretation, timestamp-bound construction, and safe search kwargs into one deterministic helper.

Failure mode addressed:

- Search tasks with phrases like yesterday, upcoming, latest, oldest, recent, or creation-recency often failed through empty searches, wrong timestamp bounds, or repeated retries.

Formal 250 contribution:

- Visible: `72`
- Called: `42`
- Called-subset outcome delta: `+0.2480`
- Called-subset reference/canonical delta: `+0.1616`
- Side-effect incidents: `0`

### `select_record_by_timestamp_extreme`

Core value:

- Selects latest/oldest record from visible records using timestamp fields.

Failure mode addressed:

- The model often searched correctly but selected the wrong record or manually compared timestamps poorly.

Formal 250 contribution:

- Visible: `32`
- Called: `27`
- Called-subset outcome delta: `+0.1188`
- Called-subset reference/canonical delta: `+0.2746`
- Side-effect incidents: `0`

### `relative_day_time_to_timestamp`

Core value:

- Converts relative local day/time into an exact Unix timestamp using current timestamp and local UTC offset.

Failure mode addressed:

- The best-two 250 failed the 10% target because relative day/time reminder tasks remained a large uncovered lane.

Formal 250 contribution:

- Visible: `32`
- Called: `29`
- Called-subset outcome delta: `+0.1389`
- Called-subset reference/canonical delta: `+0.0161`
- Side-effect incidents: `0`

Important caveat:

- This helper has weaker metadata than the two newer helpers because it is a legacy accepted helper with sparse positive/negative trigger metadata. It is frozen as-is for the v1.0 claim to avoid modifying the passed evidence. Metadata repair should happen only in a separate V2.0 candidate registry.

## Final Validation Chain

### Best-two formal 250 failed the target

Portfolio:

- `resolve_search_window_or_bounds`
- `select_record_by_timestamp_extreme`

Result:

- Relative outcome lift: `+6.15%`
- Runtime exceptions: `0`
- Side-effect incidents: `0`

Interpretation:

- The two helpers were safe and valuable but coverage was insufficient.

### Best-three formal 100 passed strongly

Portfolio:

- `relative_day_time_to_timestamp`
- `resolve_search_window_or_bounds`
- `select_record_by_timestamp_extreme`

Result:

- Outcome delta: `+0.1347`
- Relative outcome lift: `+33.58%`
- Exact successes: `16 -> 23`
- Runtime exceptions: `0`
- Side-effect incidents: `0`
- Protocol gate: PASS

### Best-three formal 250 passed

Portfolio:

- same frozen best-three registry
- generation OFF
- registry hash unchanged before/after run

Result:

- Outcome delta: `+0.0806`
- Relative outcome lift: `+20.52%`
- Reference/canonical delta: `+0.0660`
- Exact successes: `31 -> 40`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- Protocol gate: PASS

### Independent robustness 60 was positive

Result:

- Outcome delta: `+0.0612`
- Relative outcome lift: `+14.01%`
- Exact successes: `4 -> 13`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`

Caveat:

- The robustness protocol gate failed because absolute delta was below `0.08` and helper-call share was below `25%`. This was expected because the sample was deliberately independent and had `51.7%` no-current-helper-fit scenarios. It confirmed direction but does not replace the formal 250.

## Core Functions To Study First

If someone wants to understand or extend the working system, inspect these first:

1. `scripts/run_sage_protocol.py`
   - `_route_mismatch_qualified(...)`
   - control-cache planning/reporting sections
   - helper contribution export section
   - protocol gate logic

2. `src/sage_ts/evaluation/helper_contribution.py`
   - `build_helper_contribution_summary(...)`
   - `write_helper_contribution_summary(...)`

3. `src/sage_ts/adapters/sage_run_adapter.py`
   - `_conversation_generated_tool_attempts(...)`
   - `_conversation_generated_tool_results(...)`
   - `_side_effect_followup_failures(...)`
   - `_assistant_tool_names(...)`
   - `_next_assistant_tool_names(...)`

4. `src/sage_ts/runtime/toolsandbox_integration.py`
   - `compile_registry_tool(...)`
   - `inject_registry_tools_into_context(...)`
   - helper affordance/visibility logic

5. `src/sage_ts/runtime/routing_scorer.py`
   - `_latest_helper_contribution_summary(...)`
   - evidence-aware routing suppression/scoring logic

6. `src/sage_ts/evaluation/task_strata.py`
   - `base_task_family(...)`
   - `classify_task_strata(...)`
   - `expected_helper_fit(...)`
   - `expected_birth_opportunities(...)`

7. `src/sage_ts/adequacy/candidate_gate.py`
   - `evaluate_candidate_gate(...)`

8. `src/sage_ts/generation/tool_generator.py`
   - `ToolGenerationRequest.prompt(...)`
   - `parse_generated_tool_json(...)`

9. `src/sage_ts/evaluation/control_baseline_cache.py`
   - `plan_control_cache(...)`
   - `build_control_cache_report(...)`

10. `scripts/run_v2_experimental_matrix20.py`
    - `_select_combined_features(...)`

## Tests That Protected The Final Fix

Key tests:

- `tests/unit/test_sage_run_adapter.py`
- `tests/unit/test_task_strata.py`
- `tests/unit/test_candidate_gate.py`
- `tests/unit/test_tool_generator.py`
- `tests/unit/test_online_birth.py`
- `tests/unit/test_runtime_routing_scorer.py`
- `tests/unit/test_control_baseline_cache.py`
- `tests/unit/test_protocol_generation_policy.py`
- `tests/unit/test_v2_flags.py`
- `tests/unit/test_v2_matrix_selection.py`
- `tests/integration/test_toolsandbox_generated_tool_injection.py`

Final targeted validation before the v1.0 commit:

```bash
PYTHONPATH=src:. pytest tests/unit/test_sage_run_adapter.py tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_control_baseline_cache.py tests/unit/test_protocol_generation_policy.py tests/unit/test_v2_flags.py tests/unit/test_v2_matrix_selection.py -q
```

Result:

- `109 passed, 2 warnings`

Registry validation:

```bash
PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_best3_resolve_select_relative/registry_manifest.json
```

Result:

- `3 active entries pass`
- `0 active entries FAIL`

## What To Preserve

Do not modify the frozen claim registry:

- `artifacts/registry_frozen_best3_claim/registry_manifest.json`

Do not reinterpret the formal 250 after the fact. The evidence lock records:

- registry path and SHA-256
- manifest path and checksum
- summary JSON checksum
- helper contribution checksum
- protocol manifest checksum
- dashboard URLs
- generation mode OFF
- control source fresh
- cohort quality gate PASS

Use new candidate registries for V2.0 work.

## What To Improve Next

The remaining V2.0 problem is not the v1.0 best3 portfolio. The remaining problem is coverage.

Formal 250 no-current-helper-fit share:

- `44.4%`

V2.0 should focus on:

1. clustering the no-current-helper-fit regressions by mechanism
2. generating candidates from diverse clusters, not single scenario variants
3. improving adoption for visible-not-called helpers
4. testing service/precondition sequencing
5. testing contact/message constraint selection
6. testing remove/modify reminder recency workflows where search-window plus selector sequencing is still incomplete

The correct comparison for V2.0 is not baseline control alone. It should compare:

- control baseline
- frozen v1.0 best3 SAGE
- v1.0 best3 plus candidate V2.0 helper

That keeps the v1.0 claim intact while measuring whether new autonomous tool evolution adds incremental value.

## Bottom Line

SAGE finally worked because the system became evidence-bound:

- weak tools were suppressed even if they looked good in narrow tests
- helper success was measured by called-subset task outcome
- side-effect preservation was checked from trace sequence
- route mismatch was accounted for without inflating canonical score
- runtime visibility was bounded by relevance and tool availability
- the final validation used generation OFF with a frozen three-helper registry

The final evidence supports a v1.0 claim that a small retained portfolio of generated deterministic helpers can improve broad ToolSandbox task completion by more than 10% while preserving runtime stability and side-effect safety.
