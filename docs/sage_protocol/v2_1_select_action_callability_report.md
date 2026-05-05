# V2.1 Select Action Target Callability Report

## Objective
Finish the `select_action_target_by_recency` callability work and decide whether it is a real candidate, a routing problem, or a concept to park. Frozen best3 evidence and registry were not modified.

## Files Changed
- `src/sage_ts/runtime/toolsandbox_integration.py`
- `src/sage_ts/runtime/routing_scorer.py`
- `src/sage_ts/generation/tool_generator.py`
- `src/sage_ts/adequacy/inadequacy_classifier.py`
- `src/sage_ts/validation/schema_check.py`
- `tests/unit/test_state_helper_guidance.py`
- `tests/unit/test_runtime_routing_scorer.py`
- `tests/unit/test_generated_tool_lifecycle.py`
- Reports/state: `docs/sage_protocol/current_state.md`, `docs/sage_protocol/run_ledger.md`, `docs/sage_protocol/v2_1_tool_callability_repair_report.md`, this report.

## Tests Run
- `PYTHONPATH=src:. pytest tests/unit/test_runtime_routing_scorer.py tests/unit/test_state_helper_guidance.py -q` -> `24 passed`
- `PYTHONPATH=src:. pytest tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py tests/unit/test_openai_toolsandbox_roles.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_state_helper_guidance.py tests/unit/test_generated_tool_lifecycle.py -q` -> `105 passed`
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_1_tool_expansion_retry12_tiecontract_20260504_213000/registry_manifest.json` -> PASS
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_1_select_action_confirmation60_20260504_232500/registry_manifest.json` -> PASS

## Registry
- Source candidate registry: `artifacts/registry_candidates/v2_1_tool_expansion_retry12_tiecontract_20260504_213000/registry_manifest.json`
- Confirmation registry: `artifacts/registry_candidates/v2_1_select_action_confirmation60_20260504_232500/registry_manifest.json`
- Confirmation registry SHA-256: `854ac053d6e3c0e96751cf3eddecd26f987f1d50484c68ea45cd3cd20ac82303`
- Confirmation entries: best3 plus `select_action_target_by_recency`
- Frozen best3 registry modified: `no`

## Repairs Made
- Added safe optional defaults for helper inputs such as `constraints={}` so valid calls do not fail with `missing_required_helper_inputs`.
- Exposed optional defaults in generated ToolSandbox signatures.
- Updated generator and inadequacy prompts to require omitted constraints to mean `{}`.
- Added explicit search/filter action-selector usage guidance: call after original search returns visible records and before modify/remove/send actions.
- Added routing suppression for recency-action selectors on non-recency tasks.
- Added routing suppression for side-effect selectors on insufficient-information tasks.
- Allowed safe generated-code builtins `all` and `any`.
- Preserved one-of-many downstream routing for selectors returning one downstream ToolSandbox action.

## Diagnostic Commands
- Force-call after search:
  - `SAGE_DIAGNOSTIC_FORCE_TOOL_NAME=select_action_target_by_recency SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_BASE_TOOL=search_reminder ... python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_1_tool_expansion_retry12_tiecontract_20260504_213000/cohort_manifest.json --mode mechanism_12 --registry-dir artifacts/registry_candidates/v2_1_tool_expansion_retry12_tiecontract_20260504_213000 --generation off --parallel-arms --control-cache use-if-eligible --output-root outputs/v2_1_tool_expansion_select_action_force_search_reminder12_constraintsfix_20260504_223500`
- Natural fair-chance diagnostic:
  - `python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_1_tool_expansion_retry12_tiecontract_20260504_213000/cohort_manifest.json --mode mechanism_12 --registry-dir artifacts/registry_candidates/v2_1_tool_expansion_retry12_tiecontract_20260504_213000 --generation off --parallel-arms --control-cache use-if-eligible --output-root outputs/v2_1_tool_expansion_select_action_natural12_affordancefix_20260504_231000`
- Confirmation60 rerun after insufficient-info suppression:
  - `python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_1_tool_expansion_discovery60_20260504_191835/cohort_manifest.json --mode mechanism_60 --registry-dir artifacts/registry_candidates/v2_1_select_action_confirmation60_20260504_232500 --generation off --parallel-arms --control-cache use-if-eligible --output-root outputs/v2_1_select_action_confirmation60_insufficientfix_20260504_234500`

## Force-Call Evidence
Run: `outputs/v2_1_tool_expansion_select_action_force_search_reminder12_constraintsfix_20260504_223500/mechanism_12_20260504_210829`

- Outcome delta: `+0.2223`
- Canonical delta: `+0.1471`
- Exact success delta: `+2`
- Visible/called/VNC/failed: `9 / 5 / 4 / 0`
- Called-subset outcome delta: `+0.6798`
- Called-subset canonical delta: `+0.3064`
- Runtime exceptions: `0`
- Side-effect incidents: `0`
- Result: force-call proved the helper was callable and could return usable selected records after optional-default repair.

## Natural Fair-Chance Evidence
Run: `outputs/v2_1_tool_expansion_select_action_natural12_affordancefix_20260504_231000/mechanism_12_20260504_211708`

- Outcome delta: `+0.1167`
- Canonical delta: `+0.0511`
- Exact success delta: `+1`
- Visible/called/VNC/failed: `5 / 3 / 2 / 0`
- Called-subset outcome delta: `+0.4828`
- Called-subset canonical delta: `+0.1913`
- Runtime exceptions: `0`
- Side-effect incidents: `0`
- Negative behavior: non-recency contact/search tasks were hidden after routing repair.
- Result: natural adoption occurred in the small fair-chance diagnostic.

## Confirmation60 Evidence
Run: `outputs/v2_1_select_action_confirmation60_insufficientfix_20260504_234500/mechanism_60_20260504_213336`

- Dashboard: `http://127.0.0.1:5520/outputs/v2_1_select_action_confirmation60_insufficientfix_20260504_234500/mechanism_60_20260504_213336/dashboard/index.html`
- Task focus: `http://127.0.0.1:5520/outputs/v2_1_select_action_confirmation60_insufficientfix_20260504_234500/mechanism_60_20260504_213336/dashboard/task_focus.html`
- Cohort quality: `pass`
- Control source: `mixed`, cached `36`, fresh `24`
- Overall outcome delta: `+0.0907`
- Overall canonical delta: `+0.0612`
- Exact success delta: `+6`
- Runtime exceptions: `0`
- Side-effect incidents: `0`
- Protocol gate: `PASS`

`select_action_target_by_recency` contribution:
- Visible/called/VNC/failed: `5 / 2 / 3 / 0`
- Called scenarios: `remove_reminder_with_recency_latest_alt`, `remove_reminder_with_recency_latest_alt_3_distraction_tools`
- Called-subset outcome delta: `-0.1667`
- Called-subset canonical delta: `+0.1111`
- Called-subset gains/regressions/preserved: outcome `0 / 1 / 1`, canonical `1 / 1 / 0`
- Side-effect incidents: `0`
- Runtime incidents: `0`

Comparison note:
- The earlier V2.1 best3-only 60 on this manifest reported outcome delta `+0.1543` and exact `6 -> 10`.
- Best3 plus selector confirmation reported outcome delta `+0.0907` and exact `7 -> 17` against a different mixed/fresh control draw.
- The selector itself did not show additive called-subset value; existing best3 helpers, especially `select_record_by_timestamp_extreme`, remain stronger on this lane.

## Helper Call Trace Examples
### `remove_reminder_with_recency_latest_alt`
Arguments passed:
```json
{
  "records": [
    {"reminder_id": "8f5b6fc6-1c25-5467-91ba-d4d1e17c7129", "content": "Look for Company SF tickets", "reminder_timestamp": 1777858608.613345},
    {"reminder_id": "da2b856e-9390-511f-bcbe-7005f72cbf5e", "content": "Buy tickets for Merrily next week", "reminder_timestamp": 1777944948.613351}
  ],
  "timestamp_key": "reminder_timestamp",
  "selection_mode": "latest",
  "action_type": "remove_reminder"
}
```
Helper output:
```json
{
  "selected_id": "da2b856e-9390-511f-bcbe-7005f72cbf5e",
  "selected_index": 1,
  "selected_timestamp": 1777944948.613351,
  "downstream_tool_name": "remove_reminder",
  "tie_candidates": [],
  "abstain_reason": ""
}
```
Downstream side effect:
- `remove_reminder({"reminder_id": "da2b856e-9390-511f-bcbe-7005f72cbf5e"})`
- Side-effect preservation: no incident.

### `remove_reminder_with_recency_latest_alt_3_distraction_tools`
Arguments and output were equivalent: selected the latest reminder timestamp and preserved `remove_reminder` downstream. No abstain and no side-effect incident.

## Abstain Reasons
- Confirmation called cases: no abstain; `abstain_reason` was empty.
- Failed attempts: `0`.
- Prior `missing_required_helper_inputs` was resolved by optional `constraints={}` defaults.

## Root Cause Classification
- Initial blocker: schema/interface callability issue. `constraints` was semantically optional but generated as a required positional argument.
- Secondary blocker: routing/negative-case issue. Side-effect selector was visible in insufficient-information tasks before suppression.
- Final blocker: concept/additive-value issue. Once calls were valid and safe, confirmation called-subset outcome was negative and the candidate did not add value beyond best3.

## Decision Label
`candidate concept negative; park candidate`

## Exact Next Action
Do not promote `select_action_target_by_recency`. Keep the framework callability repairs. Park this candidate and mine the next uncovered cluster, with priority on helpers that are not redundant with `select_record_by_timestamp_extreme` and that have positive confirmation called-subset outcome over frozen best3.
