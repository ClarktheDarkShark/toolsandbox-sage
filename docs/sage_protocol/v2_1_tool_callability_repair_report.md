# V2.1 Tool Callability Repair Report

## Objective
Repair generated candidate callability so newly tested tools are not dismissed as `missing_required_helper_input` when the issue is reasonably fixable. Preserve the frozen best3 registry.

## Files Changed
- `src/sage_ts/runtime/toolsandbox_integration.py`
- `src/sage_ts/runtime/routing_scorer.py`
- `src/sage_ts/generation/tool_generator.py`
- `src/sage_ts/adequacy/inadequacy_classifier.py`
- `src/sage_ts/validation/schema_check.py`
- `tests/unit/test_state_helper_guidance.py`
- `tests/unit/test_runtime_routing_scorer.py`
- `tests/unit/test_generated_tool_lifecycle.py`

## What Was Fixed
- Optional helper filter inputs such as `constraints` now default safely to `{}` when omitted by the acting model.
- Exposed signatures now mark these optional helper inputs with defaults.
- Generated recency/action selector prompts now require omitted `constraints` to be treated as `{}`.
- Search/filter action helpers now get explicit usage guidance: call after original search results are visible and before modify/remove/send actions.
- Recency/action selectors are hidden on non-recency contact-only tasks to reduce visible-not-called pollution.
- Safe generated-code builtins now include `all` and `any`.
- One-of-many downstream routing is supported for action selectors that return a single downstream ToolSandbox tool.
- Post-selection argument preparers can chain selected records from previous helper traces and safely abstain on missing update fields.

## Tests Run
- `PYTHONPATH=src:. pytest tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py tests/unit/test_openai_toolsandbox_roles.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_state_helper_guidance.py tests/unit/test_generated_tool_lifecycle.py -q`
- Result: `104 passed`.
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_1_tool_expansion_retry12_tiecontract_20260504_213000/registry_manifest.json`
- Result: `PASS`, 5 active entries, 0 FAIL.

## Verification Runs
### Force-Call Diagnostic After Constraints Fix
- Run: `outputs/v2_1_tool_expansion_select_action_force_search_reminder12_constraintsfix_20260504_223500/mechanism_12_20260504_210829`
- Dashboard: `http://127.0.0.1:5520/outputs/v2_1_tool_expansion_select_action_force_search_reminder12_constraintsfix_20260504_223500/mechanism_12_20260504_210829/dashboard/index.html`
- Task focus: `http://127.0.0.1:5520/outputs/v2_1_tool_expansion_select_action_force_search_reminder12_constraintsfix_20260504_223500/mechanism_12_20260504_210829/dashboard/task_focus.html`
- Outcome delta: `+0.2223`
- Canonical delta: `+0.1471`
- Exact success delta: `+2`
- `select_action_target_by_recency`: visible/called/VNC/failed `9 / 5 / 4 / 0`
- Called-subset outcome delta: `+0.6798`
- Called-subset canonical delta: `+0.3064`
- Runtime exceptions: `0`
- Side-effect incidents: `0`
- Protocol gate: `PASS`

### Natural No-Force Diagnostic After Affordance Fix
- Run: `outputs/v2_1_tool_expansion_select_action_natural12_affordancefix_20260504_231000/mechanism_12_20260504_211708`
- Dashboard: `http://127.0.0.1:5520/outputs/v2_1_tool_expansion_select_action_natural12_affordancefix_20260504_231000/mechanism_12_20260504_211708/dashboard/index.html`
- Task focus: `http://127.0.0.1:5520/outputs/v2_1_tool_expansion_select_action_natural12_affordancefix_20260504_231000/mechanism_12_20260504_211708/dashboard/task_focus.html`
- Outcome delta: `+0.1167`
- Canonical delta: `+0.0511`
- Exact success delta: `+1`
- `select_action_target_by_recency`: visible/called/VNC/failed `5 / 3 / 2 / 0`
- Called-subset outcome delta: `+0.4828`
- Called-subset canonical delta: `+0.1913`
- Runtime exceptions: `0`
- Side-effect incidents: `0`
- Protocol gate: `PASS`

## Interpretation
The original blocker was not that the selector concept was uncallable. It was a framework contract/affordance issue: generated selector code required `constraints` even though the acting model reasonably omitted it when there were no extra constraints. After the default and affordance repair, force-call produced valid selected records and natural adoption occurred on relevant held-out cases.

`prepare_side_effect_args_from_selected_record` remains visible but naturally uncalled in this cohort. It should not be promoted from this evidence. The stronger candidate is `select_action_target_by_recency`, which now has natural calls, positive called-subset outcome, no runtime failures, and no side-effect incidents.

## Decision Label
`candidate ready for confirmation60`

## Exact Next Action
Run a frozen confirmation-60 comparing frozen best3 only vs best3 plus `select_action_target_by_recency`, generation OFF, quality-gated manifest, contribution export active, and no edits during the run. Promote only if the candidate is additive over frozen best3 with real calls and no side-effect/runtime harm.
