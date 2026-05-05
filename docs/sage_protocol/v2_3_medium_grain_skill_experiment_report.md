# V2.3 Medium-Grain Skill Experiment Report

## Objective

Test whether SAGE can generate a larger deterministic medium-grain helper that compresses visible-record constraint normalization, target selection, ambiguity handling, and downstream action-argument preparation, while preserving final ToolSandbox side-effect calls.

## Files Changed

- `src/sage_ts/experiments/v2_flags.py`
- `src/sage_ts/evaluation/task_strata.py`
- `src/sage_ts/adequacy/inadequacy_classifier.py`
- `src/sage_ts/orchestration/online_birth.py`
- `src/sage_ts/generation/tool_generator.py`
- `src/sage_ts/runtime/toolsandbox_integration.py`
- `src/sage_ts/adapters/openai_toolsandbox_roles.py`
- `src/sage_ts/validation/live_candidate_check.py`
- `src/sage_ts/validation/output_normalization.py`
- `scripts/build_v2_3_medium_grain_artifacts.py`
- `tests/unit/test_live_candidate_check.py`
- `tests/unit/test_output_normalization.py`
- `tests/unit/test_online_birth.py`
- `tests/unit/test_openai_selector_actor_policy.py`
- `tests/unit/test_state_helper_guidance.py`
- `tests/unit/test_task_strata.py`
- `tests/unit/test_tool_generator.py`

## Protected Assets

- Frozen best3 registry untouched: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Masked best3 during discovery: `relative_day_time_to_timestamp`, `resolve_search_window_or_bounds`, `select_record_by_timestamp_extreme`
- Confirmed V2.2 `days_between_timestamps` was not included in the discovery registry.

## Experiment Design

- Initial discovery60 manifest: `artifacts/summaries/v2_3_medium_grain_20260505_175722/cohort_manifest.json`
- Initial candidate registry: `artifacts/registry_candidates/v2_3_medium_grain_20260505_175722/registry_manifest.json`
- Initial discovery60 run: `outputs/v2_3_medium_grain_discovery60_20260505_175722/mechanism_60_20260505_175755`
- Balanced diagnostic20 manifest: `artifacts/summaries/v2_3_medium_grain_diag20_20260505_183020/cohort_manifest.json`
- Accepted-candidate registry: `artifacts/registry_candidates/v2_3_medium_grain_diag20_20260505_184209/registry_manifest.json`
- Accepted-candidate registry SHA-256: `e9176beca3d8f0a95d97de09242cff9f718e050c341c8c90a022e4e87c262f1c`
- Diagnostic20 acceptance run: `outputs/v2_3_medium_grain_diag20_20260505_184209/mechanism_60_20260505_184213`
- Force-call diagnostic20 run: `outputs/v2_3_medium_grain_force20_20260505_184848/mechanism_60_20260505_184852`

The initial 60-run used recurrence threshold `3`, which produced too-early births from near-duplicate phone lookup variants. The repair diagnostic used recurrence threshold `10` and a quality-gated balanced 20-scenario manifest so the candidate had diverse shortfall evidence before post-birth reuse.

## Repairs Made

- Added the `medium_grain_skills` V2 experiment flag.
- Added medium-grain inadequacy observations for `constraint_to_action_planner`.
- Added generator prompt guidance for flat, callable inputs: `records`, `match_field`, `match_value`, `action_type`, `update_fields`, `return_field`.
- Added downstream-preservation prompt guidance so generated specs include original side-effect tools.
- Added runtime docstring/affordance guidance for medium-grain composite helpers.
- Added trace bridging so `records` can be filled from prior visible search/get results.
- Fixed live validation so positive examples that abstain are rejected as unusable.
- Added composite output normalization for safe `value`, `safety_notes`, and ambiguity/tie outputs.
- Added tests for medium-grain generation guidance, actor policy, trace bridging, live validation, and output normalization.

## Initial Discovery60 Results

- Cohort quality: `PASS`
- Outcome delta: `-0.0006`
- Canonical delta: `0.0031`
- Exact success delta: `2`
- Runtime exceptions: control `0`, candidate `0`
- Accepted tools: `[]`
- Births: `constraint_to_action_planner` proposed twice, accepted `0` times
- Key failure: first candidate had useful live behavior but static validation rejected it for brittle exact-output mismatches; second candidate failed downstream-preservation metadata.

## Diagnostic20 Acceptance Results

- Cohort quality: `PASS`
- Generation: `ON`
- Recurrence threshold: `10`
- Outcome delta: `0.1715`
- Canonical delta: `0.0085`
- Exact success delta: `1`
- Protocol gate: `True`
- Route-mismatch qualified: `True`
- Accepted tools: `['constraint_to_action_planner']`
- Candidate visible/called/VNC: `6 / 0 / 6`
- Runtime incidents: `0`
- Side-effect incidents: `0`

Interpretation: the framework repair succeeded at generating and validating a medium-grain candidate, but it was accepted-but-uncalled. Aggregate lift in this diagnostic cannot be counted as tool-driven.

## Force-Call Diagnostic Results

- Generation: `OFF`
- Forced tool: `constraint_to_action_planner`
- Force condition: after `search_contacts`
- Outcome delta: `-0.1497`
- Canonical delta: `-0.0807`
- Exact success delta: `-1`
- Protocol gate: `False`
- Visible/called/VNC: `15 / 13 / 2`
- Called-subset outcome delta: `-0.13126404560161367`
- Called-subset canonical delta: `-0.13004658549699968`
- Called-subset outcome gains/regressions/preserved: `3 / 7 / 3`
- Runtime incidents: `0`
- Side-effect incidents: `9`

Interpretation: the tool is callable, but force-call evidence is negative. It reduced outcome and canonical scores, and side-effect-preservation reporting found incidents because the tool mixes answer-only and side-effect action modes in one broad contract.

## Tests Run

- `PYTHONPATH=src:. pytest tests/unit/test_openai_selector_actor_policy.py tests/unit/test_state_helper_guidance.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py tests/unit/test_live_candidate_check.py tests/unit/test_output_normalization.py -q` -> `127 passed`
- `PYTHONPATH=src:. python -m py_compile scripts/build_v2_3_medium_grain_artifacts.py` -> PASS
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_3_medium_grain_diag20_20260505_184209/registry_manifest.json` -> PASS
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_2_new_toolset/registry_manifest.json` -> PASS
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_frozen_best3_claim/registry_manifest.json` -> PASS

## Dashboard URLs

- Initial discovery60 dashboard: `http://127.0.0.1:5602/outputs/v2_3_medium_grain_discovery60_20260505_175722/mechanism_60_20260505_175755/dashboard/index.html`
- Initial discovery60 task focus: `http://127.0.0.1:5602/outputs/v2_3_medium_grain_discovery60_20260505_175722/mechanism_60_20260505_175755/dashboard/task_focus.html`
- Diagnostic20 dashboard: `http://127.0.0.1:5604/outputs/v2_3_medium_grain_diag20_20260505_184209/mechanism_60_20260505_184213/dashboard/index.html`
- Diagnostic20 task focus: `http://127.0.0.1:5604/outputs/v2_3_medium_grain_diag20_20260505_184209/mechanism_60_20260505_184213/dashboard/task_focus.html`
- Force20 dashboard: `http://127.0.0.1:5605/outputs/v2_3_medium_grain_force20_20260505_184848/mechanism_60_20260505_184852/dashboard/index.html`
- Force20 task focus: `http://127.0.0.1:5605/outputs/v2_3_medium_grain_force20_20260505_184848/mechanism_60_20260505_184852/dashboard/task_focus.html`

## Comparison Against Lightweight Helpers

Medium-grain validation and callability are achievable after the repair, but the tested broad constraint/action planner is more fragile than the narrower successful helpers. It creates a harder acting-model decision surface and a side-effect-accounting problem when one tool handles both answer-only lookup and side-effect preparation.

## Candidate Fate

- `constraint_to_action_planner`: park.
- Confirmation60: not justified.
- Promotion: not justified.
- Reason: accepted-but-uncalled naturally; force-called subset was outcome-negative and produced side-effect-preservation incidents.

## Exact Next Action

Continue masked-best3 discovery on a different non-best3 cluster, or redesign medium-grain skills only if the contract separates answer-only workflows from side-effect workflows and can prove natural/fair calls without side-effect incidents.

## Decision Label

`medium-grain skill concept negative`
