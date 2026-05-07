# V2.5 Gap Closure 100 Report

## Candidate Pack 1 Outcome
Candidate Pack 1 (`format_calculated_distance_km`) reached the gap-reduction proxy on its 100 but failed the outcome guardrail: pack outcome `0.5120` vs best3 `0.5181`, exact successes `18` vs `20`. It remains useful-but-not-promoted.

## Candidate Pack 2 Design
- Candidate pack: best3 plus `plan_contact_lookup_query`, `extract_contact_field_from_search_result`.
- Registry: `artifacts/registry_candidates/v2_5_additive_toolset/registry_manifest.json`
- Registry SHA-256: `835b1ab6524b27ad33591a57b9154dc1d89edbc6b1655f3431b1173fd74a0c48`
- Protected best3 registry unchanged: `artifacts/registry_frozen_best3_claim/registry_manifest.json`, SHA-256 `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Manifest: `artifacts/summaries/v2_5_gap_closure_100_pack2_contact/cohort_manifest.json`
- Manifest SHA-256: `da6ca97eeeac0ba2e59521d031aaf6411c1dfe6387a575701a8eb8a669885517`
- Cohort quality: `pass`; scenarios `100`; largest family share `0.08`; no low-quality override.
- Static gap files: `artifacts/summaries/v2_5_gap_closure_100_pack2_contact/static_gap_fit_best3.json`, `artifacts/summaries/v2_5_gap_closure_100_pack2_contact/static_gap_fit_pack.json`.

## Commands
```bash
OPENAI_API_KEY="$KEY" SAGE_V2_EXPERIMENT_FEATURES=grading_accounting,live_validation,candidate_repair,contract_synthesis,evidence_routing PYTHONPATH=src:. python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_5_gap_closure_100_pack2_contact/cohort_manifest.json --mode validate_100 --registry-dir artifacts/registry_frozen_best3_claim --generation off --parallel-arms --control-cache use-if-eligible --output-root outputs/v2_5_gap_closure100_pack2_contact_best3_20260506_200940 --dashboard-port 5665
OPENAI_API_KEY="$KEY" SAGE_V2_EXPERIMENT_FEATURES=grading_accounting,live_validation,candidate_repair,contract_synthesis,evidence_routing PYTHONPATH=src:. python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_5_gap_closure_100_pack2_contact/cohort_manifest.json --mode validate_100 --registry-dir artifacts/registry_candidates/v2_5_additive_toolset --generation off --parallel-arms --control-cache use-if-eligible --output-root outputs/v2_5_gap_closure100_pack2_contact_pack_20260506_202903 --dashboard-port 5666
```

## Runs And Dashboards
- Best3 run: `outputs/v2_5_gap_closure100_pack2_contact_best3_20260506_200940/validate_100_20260506_200945`
- Best3 dashboards: `http://127.0.0.1:5665/outputs/v2_5_gap_closure100_pack2_contact_best3_20260506_200940/validate_100_20260506_200945/dashboard/index.html`, `http://127.0.0.1:5665/outputs/v2_5_gap_closure100_pack2_contact_best3_20260506_200940/validate_100_20260506_200945/dashboard/task_focus.html`
- Pack run: `outputs/v2_5_gap_closure100_pack2_contact_pack_20260506_202903/validate_100_20260506_202908`
- Pack dashboards: `http://127.0.0.1:5666/outputs/v2_5_gap_closure100_pack2_contact_pack_20260506_202903/validate_100_20260506_202908/dashboard/index.html`, `http://127.0.0.1:5666/outputs/v2_5_gap_closure100_pack2_contact_pack_20260506_202903/validate_100_20260506_202908/dashboard/task_focus.html`
- Control cache best3: mixed `84 cached / 16 fresh`.
- Control cache pack: mixed `86 cached / 14 fresh`.

## Metrics
- Best3 outcome vs control: `0.6235` vs `0.3979`; delta `+0.2256`; canonical delta `+0.1138`; exact delta `+24`; runtime `0`; protocol `PASS`.
- Pack outcome vs control: `0.6490` vs `0.4195`; delta `+0.2295`; canonical delta `+0.1308`; exact delta `+26`; runtime `0`; protocol `PASS`.
- Direct pack vs best3 on same scored scenarios: outcome `0.6490` vs `0.6235`; delta `+0.0255`; canonical delta `+0.0025`; exact successes `43 -> 48`; gains/regressions/preserved `24 / 19 / 45`.
- Contact-lookup subset: best3 `0.6836`, pack `0.8363`, delta `+0.1527`; exact `16 -> 20`.
- Best3/no-helper lane interference: best3 lanes delta `-0.0243`; negative/no-helper delta `-0.0127`.

## Gap Metric
- Best3 no-current-helper-fit share: `0.48`.
- Pack no-current-helper-fit share: `0.24`.
- Relative reduction: `50.0%`.

## Helper Contribution
- `plan_contact_lookup_query` visible/called/VNC: `28 / 18 / 10`; called-subset outcome vs control `+0.6848`; gains/regressions/preserved `16 / 1 / 1`.
- `extract_contact_field_from_search_result` visible/called/VNC: `24 / 8 / 16`; called-subset outcome vs control `+0.6155`; gains/regressions/preserved `6 / 1 / 1`.
- Helper runtime/side-effect incidents: `0 / 0`.

## Decision
Candidate Pack 2 passed frozen100-style validation strongly enough to run a broad frozen250-style validation. The 100 also exposed a risk: unrelated best3/no-helper lanes showed mild negative variance/interference, so 250 must separate intended gap-lane contribution from cross-lane routing pollution.

## Decision Label
`expanded portfolio ready for 250`
