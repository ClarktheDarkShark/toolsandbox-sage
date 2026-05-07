# V2.5 Confirmation60 Pack Report

## Design
- Manifest: `artifacts/summaries/v2_5_candidate_pack1_distance_confirmation60/cohort_manifest.json`
- Cohort quality: `pass`
- Registry: `artifacts/registry_candidates/v2_5_candidate_pack1_distance/registry_manifest.json`
- Registry SHA-256: `d599a8e56f024f978bcb572ca0df12abb4a4d2196639becf64ef826cbf5f73f4`
- Best3 run: `outputs/v2_5_confirmation60_pack1_best3_20260506_152240/mechanism_60_20260506_152245`
- Pack run: `outputs/v2_5_confirmation60_pack1_distance_20260506_154608/mechanism_60_20260506_154613`
- Best3 dashboards: `http://127.0.0.1:5644/outputs/v2_5_confirmation60_pack1_best3_20260506_152240/mechanism_60_20260506_152245/dashboard/index.html`, `http://127.0.0.1:5644/outputs/v2_5_confirmation60_pack1_best3_20260506_152240/mechanism_60_20260506_152245/dashboard/task_focus.html`
- Pack dashboards: `http://127.0.0.1:5645/outputs/v2_5_confirmation60_pack1_distance_20260506_154608/mechanism_60_20260506_154613/dashboard/index.html`, `http://127.0.0.1:5645/outputs/v2_5_confirmation60_pack1_distance_20260506_154608/mechanism_60_20260506_154613/dashboard/task_focus.html`
- Control cache best3: mixed (20 cached / 40 fresh), hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- Control cache pack: mixed (22 cached / 38 fresh), hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`

## Metrics
- Best3 outcome: `0.4272`
- Pack outcome: `0.5068`
- Pack vs best3 outcome delta: `+0.0796`
- Best3 canonical: `0.7876`
- Pack canonical: `0.7707`
- Pack vs best3 canonical delta: `-0.0170`
- Exact successes best3 / pack: `10 / 10`
- Protocol gate best3 / pack: `False / True`
- Runtime exceptions best3 / pack: `0 / 0`

## Gap Metric
- Best3 no-current-helper-fit proxy: `0.600`
- Expanded no-current-helper-fit proxy: `0.483`
- Relative gap reduction proxy: `19.44%`

## New Helper Contribution
- `format_calculated_distance_km` visible/called/VNC: `8 / 7 / 1`
- Called-subset outcome delta vs control: `+0.0000`
- Called-subset canonical delta vs control: `+0.0282`
- Called-subset outcome delta vs best3: `+0.1429`
- Called-subset canonical delta vs best3: `+0.0581`
- Pack-vs-best3 called gains/regressions/preserved: `2 / 1 / 4`
- Side-effect/runtime incidents: `0 / 0`

## Interpretation
The pack confirmation is positive enough to scale to frozen100: the expanded pack beat best3 on overall outcome, passed the protocol gate where best3 did not, reduced the no-current-helper-fit proxy by more than 10%, and the new helper was naturally called with zero side-effect/runtime incidents. The called-subset was positive against best3 but neutral against control, so frozen100 must verify that the effect persists and is not only manifest/model variance.

## Decision Label
`expanded portfolio ready for 100`

# Candidate Pack 2 Confirmation60: Contact Lookup Planner + Extractor

## Design
- Manifest: `artifacts/summaries/v2_5_candidate_pack2_contact_lookup_additive60/cohort_manifest.json`
- Registry: `artifacts/registry_candidates/v2_5_additive_toolset/registry_manifest.json`
- Registry SHA-256: `835b1ab6524b27ad33591a57b9154dc1d89edbc6b1655f3431b1173fd74a0c48`
- Best3 run after answer-retention repair: `outputs/v2_5_confirmation60_pack2_contact_best3_retentionfix_20260506_193957/validate_60_20260506_194002`
- Pack run after answer-retention repair: `outputs/v2_5_confirmation60_pack2_contact_pack_retentionfix_20260506_195414/mechanism_60_20260506_195420`
- Dashboards opened: best3 `http://127.0.0.1:5663/.../dashboard/index.html` and task focus; pack `http://127.0.0.1:5664/.../dashboard/index.html` and task focus.
- Control cache: best3 mixed `41 cached / 19 fresh`; pack mixed `52 cached / 8 fresh`.

## Metrics
- Best3 outcome: `0.7173`
- Pack outcome: `0.7811`
- Direct pack vs best3 outcome delta: `+0.0638`
- Direct pack vs best3 canonical delta: `+0.0694`
- Direct exact successes: `29 -> 33`
- Direct gains/regressions/preserved: `15 / 6 / 29`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`

## Contact Helper Contribution
- `plan_contact_lookup_query` visible/called/VNC: `24 / 19 / 5`
- Planner called-subset outcome vs control: `+0.5975`; outcome gains/regressions/preserved `15 / 2 / 2`.
- `extract_contact_field_from_search_result` visible/called/VNC: `24 / 11 / 13`
- Extractor called-subset outcome vs control: `+0.6401`; outcome gains/regressions/preserved `9 / 1 / 1`.

## Interpretation
The first additive60 pass understated tool value because the acting model sometimes answered correctly, then a brief acknowledgement response replaced the final scored answer. The deterministic answer-retention repair changed this from a scoring artifact into a fair task-completion measurement. After that repair, the contact lookup pack had natural calls, positive called-subset outcome, zero runtime incidents, and zero side-effect incidents.

## Decision Label
`expanded portfolio ready for 100`
