# V2.0 Dependency Helper Lucrative/Force-Call Diagnostic

## Objective
Give the dependency/precondition helper lane one more fair diagnostic attempt by making the helper easier to call, then force a few post-error calls to test whether the concept has enough task value to justify further adoption repair.

This is diagnostic evidence only. It is not promotion evidence and not claim-grade validation.

## Files Changed
- `src/sage_ts/adapters/openai_toolsandbox_roles.py`
- `src/sage_ts/runtime/toolsandbox_integration.py`
- `tests/unit/test_openai_toolsandbox_roles.py`
- `tests/unit/test_runtime_routing_scorer.py`
- `docs/sage_protocol/current_state.md`
- `docs/sage_protocol/run_ledger.md`

## Diagnostic Candidate
Registry: `artifacts/registry_candidates/v2_0_dependency_lucrative20_20260504_174000/registry_manifest.json`

Candidate: `next_dependency_precondition_call`

Change from failed prior candidate:
- Replaced opaque `dependency_state: dict` input with scalar error-recovery inputs: `failed_tool_name`, `error_message`, `target_service`, `target_action`.
- Affordance shifted from abstract dependency planning to concrete post-error recovery: call immediately after a visible `PermissionError` or `ConnectionError` from an original ToolSandbox tool.
- Output remains one original ToolSandbox precondition setter plus arguments; helper still does not perform the side effect.

Validation:
- Runtime smoke: PASS
- Held-out check: PASS
- Negative applicability: PASS
- Registry check-only: PASS, 4 active entries pass

## Diagnostic Force Mode
Implemented diagnostic-only OpenAI tool forcing:
- Env: `SAGE_DIAGNOSTIC_FORCE_TOOL_NAME=<tool>`
- Env: `SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_ERROR=1`
- Behavior: force the named tool only when it is visible, has not already been called, and prior tool messages show a ToolSandbox error/precondition failure.
- This avoids forcing the helper before useful error context exists.

Also added a diagnostic-only routing override:
- If the forced tool is hidden only due to `blocked_by_visible_not_called_adoption_risk`, expose it with reason `diagnostic_force_overrode_adoption_risk`.
- This is needed because the natural diagnostic run itself creates visible-not-called evidence that would otherwise block the forced concept test.

## Tests Run
- `PYTHONPATH=src:. pytest tests/unit/test_openai_toolsandbox_roles.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py -q` -> PASS, `36 passed`.
- `PYTHONPATH=src:. pytest tests/unit/test_openai_toolsandbox_roles.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_state_helper_guidance.py tests/unit/test_runtime_routing_scorer.py -q` -> PASS, `40 passed`.
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_0_dependency_lucrative20_20260504_174000/registry_manifest.json` -> PASS.

## Natural-Adoption Run
Run root: `outputs/v2_0_dependency_lucrative20_natural_20260504_174500/mechanism_40_20260504_174438`

Dashboards:
- `http://127.0.0.1:5520/outputs/v2_0_dependency_lucrative20_natural_20260504_174500/mechanism_40_20260504_174438/dashboard/index.html`
- `http://127.0.0.1:5520/outputs/v2_0_dependency_lucrative20_natural_20260504_174500/mechanism_40_20260504_174438/dashboard/task_focus.html`

Metrics:
- Outcome delta: `+0.0552`
- Canonical delta: `+0.0681`
- Protocol gate: FAIL, `outcome_gains_do_not_exceed_regressions`
- Control cache: mixed, `15 cached / 5 fresh`
- Runtime exceptions: `0`

Helper adoption:
- `next_dependency_precondition_call`: visible `10`, called `0`, visible-not-called `10`
- `resolve_search_window_or_bounds`: visible/called `3 / 1`
- `select_record_by_timestamp_extreme`: visible/called `2 / 2`

Interpretation: scalar inputs and stronger post-error affordance were still insufficient for natural adoption.

## Forced-After-Error Run
Run root: `outputs/v2_0_dependency_lucrative20_forced2_20260504_180000/mechanism_40_20260504_175421`

Dashboards:
- `http://127.0.0.1:5520/outputs/v2_0_dependency_lucrative20_forced2_20260504_180000/mechanism_40_20260504_175421/dashboard/index.html`
- `http://127.0.0.1:5520/outputs/v2_0_dependency_lucrative20_forced2_20260504_180000/mechanism_40_20260504_175421/dashboard/task_focus.html`

Metrics:
- Outcome delta: `-0.0002`
- Canonical delta: `+0.0793`
- Protocol gate: FAIL, `non_positive_outcome_delta`, `outcome_gains_do_not_exceed_regressions`
- Outcome gains/regressions/preserved: `7 / 8 / 5`
- Runtime exceptions: `0`
- Control cache: mixed, `15 cached / 5 fresh`

Helper adoption:
- `next_dependency_precondition_call`: visible `10`, called `8`, visible-not-called `2`
- Called-subset outcome delta: `-0.0285`
- Called-subset canonical delta: `+0.0351`
- Side-effect preservation failures: `1`, on `send_message_with_contact_content_cellular_off`

Called scenarios:
- `turn_on_wifi_low_battery_mode`
- `turn_on_wifi_low_battery_mode_implicit`
- `turn_on_cellular_low_battery_mode`
- `turn_on_cellular_low_battery_mode_implicit`
- `turn_on_location_low_battery_mode`
- `turn_on_location_low_battery_mode_implicit`
- `send_message_with_contact_content_cellular_off`
- `send_message_with_contact_content_cellular_off_alt`

## Interpretation
The concept is callable when forced, so the remaining problem is not purely API/schema visibility. But forced calls did not add task-completion value:
- Net outcome was essentially flat-negative.
- Called-subset outcome was negative.
- One side-effect preservation failure appeared.
- Canonical score improved, but the project’s primary metric is outcome/task completion.

This means the dependency/precondition helper lane is not currently worth more routing repair. The direct ToolSandbox setter/getter route remains competitive or better for these tasks.

## Decision Label
`park dependency lane`

## Exact Next Action
Keep the diagnostic force-call machinery for future new-tool concept tests. Do not promote or confirm this dependency/precondition helper. Return to V2.0 shortfall mining and prioritize another no-current-helper-fit cluster with stronger forced-call upside.
