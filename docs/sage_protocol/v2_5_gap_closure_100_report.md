# V2.5 Gap Closure 100 Report

## Design
- Manifest: `artifacts/summaries/v2_5_gap_closure_100_pack1_distance/cohort_manifest.json`
- Cohort quality: `pass`
- External-service contamination: `42` scenarios; `--allow-contaminated-preflight` was required because the candidate lane is distance/location-service based. No low-quality override was used.
- Registry: `artifacts/registry_candidates/v2_5_candidate_pack1_distance_frozen/registry_manifest.json`
- Registry SHA-256: `d599a8e56f024f978bcb572ca0df12abb4a4d2196639becf64ef826cbf5f73f4`
- Best3 run: `outputs/v2_5_gap_closure_100_best3_20260506_161059/validate_100_20260506_161104`
- Pack run: `outputs/v2_5_gap_closure_100_distance_20260506_164021/validate_100_20260506_164026`
- Best3 dashboards: `http://127.0.0.1:5646/outputs/v2_5_gap_closure_100_best3_20260506_161059/validate_100_20260506_161104/dashboard/index.html`, `http://127.0.0.1:5646/outputs/v2_5_gap_closure_100_best3_20260506_161059/validate_100_20260506_161104/dashboard/task_focus.html`
- Pack dashboards: `http://127.0.0.1:5647/outputs/v2_5_gap_closure_100_distance_20260506_164021/validate_100_20260506_164026/dashboard/index.html`, `http://127.0.0.1:5647/outputs/v2_5_gap_closure_100_distance_20260506_164021/validate_100_20260506_164026/dashboard/task_focus.html`
- Control cache best3: mixed (55 cached / 45 fresh), hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- Control cache pack: mixed (58 cached / 42 fresh), hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`

## Metrics
- Best3 outcome: `0.5181`
- Pack outcome: `0.5120`
- Pack vs best3 outcome delta: `-0.0061`
- Best3 canonical: `0.7902`
- Pack canonical: `0.7844`
- Pack vs best3 canonical delta: `-0.0059`
- Exact successes best3 / pack: `20 / 18`
- Runtime exceptions best3 / pack: `0 / 0`

## Gap Closure
- Best3 no-current-helper-fit proxy: `0.640`
- Expanded no-current-helper-fit proxy: `0.570`
- Relative gap reduction proxy: `10.94%`
- The 10% proxy target was met at 100, but the performance guardrail was not met because overall outcome and exact successes decreased versus best3.

## New Helper Contribution
- `format_calculated_distance_km` visible/called/VNC: `16 / 7 / 9`
- Called-subset outcome delta vs control: `+0.1429`
- Called-subset outcome delta vs best3: `+0.1429`
- Pack-vs-best3 called gains/regressions/preserved: `3 / 0 / 4`
- Helper side-effect/runtime incidents: `0 / 0`

## Decision
Do not run frozen250 for Candidate Pack 1. The distance helper is real and useful on called distance cases, but the distance-only pack is not additive enough at frozen100: overall outcome decreased by `-0.0061`, exact successes decreased by `2`, and visible-not-called was `9`.

## Decision Label
`continue gap-closure loop`
