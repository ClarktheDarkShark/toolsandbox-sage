# V2.5 Micro Value Test Report

## Objective
Test V2.5 foundry candidates for callability, adoption, safety, and additive-over-best3 potential before any additive60 run.

## Files Changed
- `scripts/build_v2_5_tool_foundry_artifacts.py`
- `src/sage_ts/adequacy/candidate_gate.py`
- `src/sage_ts/runtime/routing_scorer.py`
- `src/sage_ts/runtime/toolsandbox_integration.py`
- `src/sage_ts/adapters/openai_toolsandbox_roles.py`
- `tests/unit/test_candidate_gate.py`
- `tests/unit/test_runtime_routing_scorer.py`
- `tests/unit/test_openai_toolsandbox_roles.py`

## Machine Summary
- `artifacts/summaries/v2_5_tool_foundry_loop2_3_micro_summary/summary.json`

## Candidate 1: `format_calculated_distance_km`
- Registry: `artifacts/summaries/v2_5_tool_foundry_v2_5_loop2_distance_unitsafe_fixedfmt_20260506_124758/candidate_batch_registry/registry_manifest.json`
- Natural micro run: `outputs/v2_5_micro_distance_unitsafe_routingfix_cached_20260506_125948/mechanism_40_20260506_125953`
- Dashboards: `http://127.0.0.1:5633/outputs/v2_5_micro_distance_unitsafe_routingfix_cached_20260506_125948/mechanism_40_20260506_125953/dashboard/index.html`, `http://127.0.0.1:5633/outputs/v2_5_micro_distance_unitsafe_routingfix_cached_20260506_125948/mechanism_40_20260506_125953/dashboard/task_focus.html`
- Candidate vs control outcome delta: `+0.2643`; canonical delta: `+0.0743`; exact successes: `4 -> 7`.
- Helper visible/called/VNC: `4 / 4 / 0`.
- Called-subset outcome delta: `+0.5556`; canonical delta: `+0.0072`.
- Best3+distance vs best3-only same-manifest outcome delta: `+0.0447`; gains/regressions/preserved: `4 / 2 / 8`.
- Runtime/side-effect incidents: `0 / 0`.
- Decision: micro-positive but narrow. Keep as candidate evidence; do not claim gap closure from this alone.

## Insufficient-Information Distance Finding
The insufficient-information distance cases are rubric-compliant abstain/clarification tasks. Computing distance when current location is unavailable is a minefield action. The repaired routing hides derived calculators with required original producer calls on insufficient-information tasks, and `format_calculated_distance_km` was hidden on those negatives in the repaired runs.

## Candidate 2: `resolve_location_lookup_field`
- Registry: `artifacts/summaries/v2_5_tool_foundry_v2_5_loop3_location_bridge_20260506_132151/candidate_batch_registry/registry_manifest.json`
- Natural policy-repair run: `outputs/v2_5_micro_location_field_policyrepair_cached_20260506_133006/mechanism_40_20260506_133010`
- Dashboards: `http://127.0.0.1:5636/outputs/v2_5_micro_location_field_policyrepair_cached_20260506_133006/mechanism_40_20260506_133010/dashboard/index.html`, `http://127.0.0.1:5636/outputs/v2_5_micro_location_field_policyrepair_cached_20260506_133006/mechanism_40_20260506_133010/dashboard/task_focus.html`
- Natural visible/called/VNC: `4 / 1 / 3`; called-subset outcome delta: `0.0`; canonical delta: `+0.0548`.
- Force-after-lookup run: `outputs/v2_5_micro_location_field_force_after_lookup_20260506_133440/mechanism_40_20260506_133444`
- Dashboards: `http://127.0.0.1:5637/outputs/v2_5_micro_location_field_force_after_lookup_20260506_133440/mechanism_40_20260506_133444/dashboard/index.html`, `http://127.0.0.1:5637/outputs/v2_5_micro_location_field_force_after_lookup_20260506_133440/mechanism_40_20260506_133444/dashboard/task_focus.html`
- Force visible/called/VNC: `4 / 4 / 0`; called-subset outcome delta: `0.0`; canonical delta: `+0.0368`.
- Runtime/side-effect incidents: `0 / 0`.
- Trace diagnosis: callability was fixed. The remaining failure is value/output alignment. Address lookup returns `One Apple Park Way...` while the target expects `Apple Park 1 Apple Park Way... United States`; phone values are extracted correctly but the actor reformats `+14089961010` as `+1 (408) 996-1010`, so primary outcome stays 0 despite canonical gain.
- Decision: park current location-field design as canonical-only/value failure.

## Framework Repairs Proven
- Candidate gate now accepts derived calculators that preserve deterministic original producer calls such as `calculate_*` and `convert_*`.
- Runtime routing hides derived calculators on insufficient-information minefield tasks.
- Runtime routing prevents derived calculators with original producer calls from broad triggerless exposure.
- Runtime bridge can autofill a single dict payload input even when scalar selector inputs are also present.
- Runtime bridge wraps scalar original tool results as `{"result": value}`.
- Derived actor policy now recognizes one payload input plus scalar selector inputs.

## Decision Label
`continue gap-closure loop`

## Exact Next Action
Do not run additive60 for `resolve_location_lookup_field`. Preserve `format_calculated_distance_km` as narrow micro-positive evidence, then continue the foundry loop with the next materially different high-gap design. The next best target is a safe direct-side-effect argument-preparation design with scalar inputs, distinct from the parked selected-record-only side-effect prep lane.

## Candidate 3: `prepare_direct_contact_action_kwargs`
- Registry: `artifacts/summaries/v2_5_tool_foundry_v2_5_loop4_direct_aliasfix_20260506_134732/candidate_batch_registry/registry_manifest.json`
- Natural micro run: `outputs/v2_5_micro_direct_action_cached_20260506_134827/mechanism_40_20260506_134832`
- Dashboards: `http://127.0.0.1:5638/outputs/v2_5_micro_direct_action_cached_20260506_134827/mechanism_40_20260506_134832/dashboard/index.html`, `http://127.0.0.1:5638/outputs/v2_5_micro_direct_action_cached_20260506_134827/mechanism_40_20260506_134832/dashboard/task_focus.html`
- Natural visible/called/VNC: `8 / 0 / 8`; VNC called-subset proxy outcome `-0.0798`; aggregate lift was not tool-driven.
- Force run: `outputs/v2_5_micro_direct_action_force_20260506_135241/mechanism_40_20260506_135245`
- Dashboards: `http://127.0.0.1:5639/outputs/v2_5_micro_direct_action_force_20260506_135241/mechanism_40_20260506_135245/dashboard/index.html`, `http://127.0.0.1:5639/outputs/v2_5_micro_direct_action_force_20260506_135241/mechanism_40_20260506_135245/dashboard/task_focus.html`
- Force visible/called/VNC: `8 / 8 / 0`; calls supplied `{}` and returned `missing_required_helper_inputs`.
- Force called-subset outcome delta: `-0.1155`; canonical delta: `-0.0933`.
- Runtime/side-effect incidents: `0 / 1`.
- Decision: park this dict-payload design. Do not park the full direct-side-effect cluster; try a materially different flat-scalar interface if this lane is revisited.

## Updated Decision Label
`continue gap-closure loop`
