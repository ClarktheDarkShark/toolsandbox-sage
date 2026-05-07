# V2.5 Gap Closure 250 Report

## Design
- Candidate pack: best3 plus `plan_contact_lookup_query`, `extract_contact_field_from_search_result`.
- Registry: `artifacts/registry_candidates/v2_5_additive_toolset/registry_manifest.json`
- Registry SHA-256: `835b1ab6524b27ad33591a57b9154dc1d89edbc6b1655f3431b1173fd74a0c48`
- Protected best3 registry unchanged: `artifacts/registry_frozen_best3_claim/registry_manifest.json`, SHA-256 `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Manifest: `artifacts/summaries/v2_formal250_clean_20260504_034104/cohort_manifest.json`
- Manifest SHA-256: `c7ec4010f8fc3ea3ca1f914b8d5a980f70e51494c75cc3d9f9148b0b3604a47e`
- Cohort quality: `pass`; scenarios `250`; largest family share `0.032`; no low-quality override.
- Degradation analysis artifact: `artifacts/summaries/v2_5_pack2_contact_degradation_analysis_250/analysis.json`
- Summary artifact: `artifacts/summaries/v2_5_candidate_pack2_contact_lookup_summary/summary.json`

## Commands
```bash
OPENAI_API_KEY="$KEY" SAGE_V2_EXPERIMENT_FEATURES=grading_accounting,live_validation,candidate_repair,contract_synthesis,evidence_routing PYTHONPATH=src:. python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_formal250_clean_20260504_034104/cohort_manifest.json --mode validate_250 --registry-dir artifacts/registry_frozen_best3_claim --generation off --parallel-arms --control-cache use-if-eligible --output-root outputs/v2_5_gap_closure250_pack2_contact_best3_20260506_205033 --dashboard-port 5667
OPENAI_API_KEY="$KEY" SAGE_V2_EXPERIMENT_FEATURES=grading_accounting,live_validation,candidate_repair,contract_synthesis,evidence_routing PYTHONPATH=src:. python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_formal250_clean_20260504_034104/cohort_manifest.json --mode validate_250 --registry-dir artifacts/registry_candidates/v2_5_additive_toolset --generation off --parallel-arms --control-cache use-if-eligible --output-root outputs/v2_5_gap_closure250_pack2_contact_pack_20260506_210835 --dashboard-port 5668
```

## Runs And Dashboards
- Best3 run: `outputs/v2_5_gap_closure250_pack2_contact_best3_20260506_205033/validate_250_20260506_205037`
- Best3 dashboards: `http://127.0.0.1:5667/outputs/v2_5_gap_closure250_pack2_contact_best3_20260506_205033/validate_250_20260506_205037/dashboard/index.html`, `http://127.0.0.1:5667/outputs/v2_5_gap_closure250_pack2_contact_best3_20260506_205033/validate_250_20260506_205037/dashboard/task_focus.html`
- Pack run: `outputs/v2_5_gap_closure250_pack2_contact_pack_20260506_210835/validate_250_20260506_210840`
- Pack dashboards: `http://127.0.0.1:5668/outputs/v2_5_gap_closure250_pack2_contact_pack_20260506_210835/validate_250_20260506_210840/dashboard/index.html`, `http://127.0.0.1:5668/outputs/v2_5_gap_closure250_pack2_contact_pack_20260506_210835/validate_250_20260506_210840/dashboard/task_focus.html`
- Control cache best3: mixed `211 cached / 39 fresh`.
- Control cache pack: cached `250 cached / 0 fresh`; the best3 run filled the remaining compatible controls first.

## Metrics Versus Control
- Best3 outcome: `0.5626`; control `0.4070`; delta `+0.1556`; canonical delta `+0.0561`; exact delta `+19`; runtime `0`; protocol `PASS`.
- Pack outcome: `0.5637`; control `0.4001`; delta `+0.1636`; canonical delta `+0.0656`; exact delta `+27`; runtime `0`; protocol `PASS`.

## Direct Pack Vs Best3
- Compared scored overlap: `202` scenarios.
- Best3 outcome: `0.5626`.
- Pack outcome: `0.5637`.
- Outcome delta: `+0.0011`.
- Canonical delta: `+0.0156`.
- Exact successes: `68 -> 72`.
- Outcome gains/regressions/preserved: `51 / 56 / 95`.
- Runtime exceptions: `0`.
- Helper side-effect incidents: `0`.

## Gap Metric
- Registry-aware static best3 no-current-helper-fit share on this manifest: `52.0%` (`130 / 250`).
- Registry-aware static pack no-current-helper-fit share on this manifest: `46.0%` (`115 / 250`).
- Relative reduction on this manifest: `11.54%`.
- Against the original formal-250 reference of `44.4%`, the pack does not reach the absolute `<=40.0%` target; therefore this is validated lane progress, not final campaign completion.

## Intended Contact-Lookup Lane
- Contact lookup scenarios: `15`.
- Best3 outcome: `0.5629`.
- Pack outcome: `0.7796`.
- Contact-lane outcome delta: `+0.2167`.
- Contact-lane canonical delta: `+0.2054`.
- Contact-lane exact successes: `8 -> 11`.
- Contact-lane gains/regressions/preserved: `6 / 2 / 7`.

## Helper Contribution
- `plan_contact_lookup_query` visible/called/VNC: `26 / 11 / 15`; failed attempts `0`.
- Planner called-subset outcome vs control: `+0.6563`; canonical `+0.0937`; outcome gains/regressions/preserved `10 / 1 / 0`.
- `extract_contact_field_from_search_result` visible/called/VNC: `15 / 7 / 8`; failed attempts `0`.
- Extractor called-subset outcome vs control: `+0.6762`; canonical `-0.0598`; outcome gains/regressions/preserved `6 / 1 / 0`.
- Extractor route-mismatch accounting: helper-substitution likely because outcome was strongly positive while canonical was negative.
- Side-effect/runtime incidents for new helpers: `0 / 0`.

## Why The Broad 250 Looks Worse Than Smaller Runs
- Dilution: the broad 250 contains only `15` contact-lookup opportunities, while the 100 contact pack had `24`; the helper effect is real but diluted in aggregate.
- Lower adoption density: planner calls dropped from `19/24` in confirmation60 and `18/28` in frozen100 to `11/26` in broad250. Extractor calls dropped from `11/24` in confirmation60 and `8/24` in frozen100 to `7/15` in broad250.
- Cross-lane interference: unrelated best3 lanes averaged `-0.0127` pack-vs-best3 outcome on 112 scored scenarios; negative/no-helper lanes averaged `-0.0213` on 56 scenarios. These regressions are not caused by failed contact tool calls, but by broader runtime bundle/context/routing variance.
- False exposure: planner was visible on some `all_tools` non-contact scenarios, contributing VNC noise. The VNC subset was not catastrophic, but it indicates routing should require stronger contact-lookup trigger evidence outside the intended family.
- Variant coverage: the formal 250 lacked `search_relationship_with_phone_number`; the tool pack only got `search_name_with_relationship` and `search_phone_number_with_name` coverage. This limits measured gap closure despite the candidate design covering the broader mechanism.

## Decision
Candidate Pack 2 validates the contact-lookup mechanism but does not fully complete the V2.5 gap-closure campaign. Keep the pack as a confirmed candidate lane. Next work should either tighten routing to reduce cross-lane exposure or add another non-overlapping candidate lane before scaling any expanded portfolio as a final replacement for best3.

## Decision Label
`continue gap-closure loop`

## Post-250 Routing Repair
After the broad250 analysis, routing was repaired so explicit positive triggers/applicable task families are authoritative. A generated helper with an explicit contract no longer falls back to broad provisional birth-family visibility when the scenario does not match its triggers or families.

### Verification
- Route probe artifact: `artifacts/summaries/v2_5_contact_routing_contract_repair/route_probe.json`.
- Diagnostic manifest: `artifacts/summaries/v2_5_contact_routing_repair20/cohort_manifest.json`; quality `pass`; 6 contact positives and 14 non-contact/negative cases.
- Diagnostic run: `outputs/v2_5_contact_routing_repair20_pack_20260506_220717/mechanism_40_20260506_220721`.
- Dashboards: `http://127.0.0.1:5669/outputs/v2_5_contact_routing_repair20_pack_20260506_220717/mechanism_40_20260506_220721/dashboard/index.html`, `http://127.0.0.1:5669/outputs/v2_5_contact_routing_repair20_pack_20260506_220717/mechanism_40_20260506_220721/dashboard/task_focus.html`.
- Control cache: `20 cached / 0 fresh`.
- Outcome delta vs control: `+0.2699`; canonical delta `+0.0837`; exact delta `+3`; runtime `0`; protocol `PASS`.
- `plan_contact_lookup_query` visible/called/VNC/hidden: `6 / 5 / 1 / 14`; called-subset outcome `+0.5012`; side-effect/runtime `0 / 0`.
- `extract_contact_field_from_search_result` visible/called/VNC/hidden: `6 / 3 / 3 / 14`; called-subset outcome `+0.4375`; side-effect/runtime `0 / 0`.

### Tests
- Focused routing tests: `73 passed`.
- Full targeted suite: `154 passed, 2 warnings`.
- Candidate pack registry check-only: PASS, 5 active entries.

### Interpretation
The broad250 degradation mechanism was confirmed and repaired: false visibility on unrelated `all_tools` scenarios is now blocked while contact-positive exposure is preserved. This should reduce cross-lane context pollution in the next candidate-pack validation run.
