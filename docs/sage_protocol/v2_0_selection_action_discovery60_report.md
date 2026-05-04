# V2.0 Selection-Action Discovery60 Report

## Objective
Run a V2.0 discovery phase on selection-action uncovered lanes while preserving the locked frozen best3 claim registry. Dependency/precondition was parked before this phase.

## Files Changed
- `src/sage_ts/adapters/openai_toolsandbox_roles.py`: added diagnostic force-after-base-tool support for safe post-search selector force tests.
- `src/sage_ts/runtime/toolsandbox_integration.py`: explicit diagnostic force can override name-specific visible-not-called suppression.
- `tests/unit/test_openai_toolsandbox_roles.py`: coverage for force-after-prior-tool-call helper.
- `tests/unit/test_runtime_routing_scorer.py`: coverage for diagnostic override of name-specific VNC suppression.
- `docs/sage_protocol/v2_0_selection_action_discovery60_report.md`
- `docs/sage_protocol/v2_0_selection_action_candidate_triage.md`
- `docs/sage_protocol/current_state.md`
- `docs/sage_protocol/run_ledger.md`

## Cohort
- Manifest: `artifacts/summaries/v2_0_selection_action_discovery60_20260504_183108/cohort_manifest.json`
- Diversity report: `artifacts/summaries/v2_0_selection_action_discovery60_20260504_183108/cohort_diversity_report.json`
- Scenario count: `60`
- Role split: `20 early_cluster_positive`, `25 held_out_reuse`, `15 negative_or_ambiguity`
- Cohort quality: `pass`
- Distinct base families: `25`
- Largest family share: `8.33%`
- No-current-helper-fit share: `55.00%`
- Frozen best3 registry preserved: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Candidate registry: `artifacts/registry_candidates/v2_0_selection_action_discovery60_20260504_183108`

## Commands Run
- Registry checks:
  - `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_frozen_best3_claim/registry_manifest.json`
  - `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_0_selection_action_discovery60_20260504_183108/registry_manifest.json`
- Arm A best3-only:
  - `python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_0_selection_action_discovery60_20260504_183108/cohort_manifest.json --mode mechanism_60 --registry-dir artifacts/registry_frozen_best3_claim --generation off --parallel-arms --control-cache use-if-eligible ...`
- Arm B discovery:
  - `SAGE_V2_EXPERIMENT_FEATURES=candidate_repair,contract_synthesis,evidence_routing,grading_accounting,live_validation python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_0_selection_action_discovery60_20260504_183108/cohort_manifest.json --mode mechanism_60 --registry-dir artifacts/registry_candidates/v2_0_selection_action_discovery60_20260504_183108 --generation on --parallel-arms --control-cache use-if-eligible ...`
- Selector force diagnostic:
  - `SAGE_DIAGNOSTIC_FORCE_TOOL_NAME=select_contact_field_by_constraint SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_BASE_TOOL=search_contacts python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_0_selection_action_discovery60_20260504_183108/v2_0_selection_action_selector_force20_20260504_190448/cohort_manifest.json --mode mechanism_12 --registry-dir artifacts/registry_candidates/v2_0_selection_action_selector_force20_20260504_190448 --generation off --parallel-arms --control-cache use-if-eligible ...`
- Tests:
  - `PYTHONPATH=src:. pytest tests/unit/test_openai_toolsandbox_roles.py tests/unit/test_runtime_routing_scorer.py -q` -> `14 passed`
  - `PYTHONPATH=src:. pytest tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py tests/unit/test_openai_toolsandbox_roles.py tests/unit/test_runtime_routing_scorer.py -q` -> `87 passed`

## Arm A: Frozen Best3 Baseline
- Run: `outputs/v2_0_selection_action_best3_60_20260504_183302/mechanism_60_20260504_183306`
- Dashboard: `http://127.0.0.1:5520/outputs/v2_0_selection_action_best3_60_20260504_183302/mechanism_60_20260504_183306/dashboard/index.html`
- Task focus: `http://127.0.0.1:5520/outputs/v2_0_selection_action_best3_60_20260504_183302/mechanism_60_20260504_183306/dashboard/task_focus.html`
- Control cache: `fresh`, cached `0`, fresh `60`
- Outcome delta: `0.0989`
- Relative outcome lift: `18.96%`
- Canonical/reference delta: `0.1147`
- Exact successes: `4 -> 8`
- Canonical gains/regressions/preserved: `29 / 16 / 15`
- Outcome gains/regressions/preserved: `20 / 14 / 19`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- Protocol gate: `True`

## Arm B: V2.0 Discovery
- Run: `outputs/v2_0_selection_action_discovery60_run_20260504_184633/mechanism_60_20260504_184638`
- Dashboard: `http://127.0.0.1:5520/outputs/v2_0_selection_action_discovery60_run_20260504_184633/mechanism_60_20260504_184638/dashboard/index.html`
- Task focus: `http://127.0.0.1:5520/outputs/v2_0_selection_action_discovery60_run_20260504_184633/mechanism_60_20260504_184638/dashboard/task_focus.html`
- Generation: `on`
- Control cache: `fresh`, cached `0`, fresh `60`
- Outcome delta: `0.0245`
- Relative outcome lift: `4.35%`
- Canonical/reference delta: `0.0552`
- Exact successes: `5 -> 9`
- Canonical gains/regressions/preserved: `30 / 14 / 16`
- Outcome gains/regressions/preserved: `19 / 13 / 21`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- Protocol gate: `False`; reasons `['confirmation_outcome_delta_below_0_08']`

## Candidate Birth and Adoption
- Generated/accepted candidate: `select_contact_field_by_constraint`
- Natural visibility/call/VNC: `2 / 0 / 2`
- Accepted-but-uncalled: `['select_contact_field_by_constraint']`
- Candidate status: `diagnostic_only`
- Live validation: accepted with warning `live_missing_expected_milestone_calls_replaced`; grading accounting recorded this as route-accounting, not final-state failure.

## Force-Call Diagnostic
- Run: `outputs/v2_0_selection_action_selector_force20_20260504_190448/mechanism_12_20260504_190512`
- Dashboard: `http://127.0.0.1:5520/outputs/v2_0_selection_action_selector_force20_20260504_190448/mechanism_12_20260504_190512/dashboard/index.html`
- Task focus: `http://127.0.0.1:5520/outputs/v2_0_selection_action_selector_force20_20260504_190448/mechanism_12_20260504_190512/dashboard/task_focus.html`
- Force condition: only after `search_contacts` had already been called.
- Selector visible/called/VNC: `8 / 4 / 4`
- Called-subset outcome delta: `-0.0132`
- Called-subset canonical delta: `0.0020`
- Overall force outcome delta: `-0.1074`
- Overall force canonical delta: `-0.0904`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`

## Interpretation
Frozen best3 remained strong on this selection/action-heavy manifest. Discovery did not improve over best3 and produced one diagnostic-only selector that was naturally uncalled. The force-after-search diagnostic gave the tool a fair opportunity and showed slightly negative called-subset outcome with no safety incident. This is evidence to park this specific generated selector, not evidence to promote it or run confirmation60.

## Decision Label
`candidate concept negative`

## Exact Next Action
Park `select_contact_field_by_constraint` for claim-grade promotion. Mine the next uncovered no-current-helper-fit cluster, prioritizing clusters that can produce non-diagnostic, multi-family candidates with simple scalar/list inputs and actual later-task adoption.
