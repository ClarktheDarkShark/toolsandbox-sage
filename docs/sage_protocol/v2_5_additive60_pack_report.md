# V2.5 Additive60 Pack Report

## Design
- Manifest: `artifacts/summaries/v2_5_candidate_pack1_distance_additive60/cohort_manifest.json`
- Best3 run: `outputs/v2_5_additive60_pack1_best3_20260506_144550/mechanism_60_20260506_144554`
- Pack run: `outputs/v2_5_additive60_pack1_distance_20260506_150042/mechanism_60_20260506_150047`
- Best3 dashboard: `http://127.0.0.1:5642/outputs/v2_5_additive60_pack1_best3_20260506_144550/mechanism_60_20260506_144554/dashboard/index.html`
- Pack dashboard: `http://127.0.0.1:5643/outputs/v2_5_additive60_pack1_distance_20260506_150042/mechanism_60_20260506_150047/dashboard/index.html`
- Control cache best3: mixed (52 cached / 8 fresh), hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- Control cache pack: mixed (54 cached / 6 fresh), hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`

## Metrics
- Best3 outcome: `0.4437`
- Pack outcome: `0.5923`
- Pack vs best3 outcome delta: `+0.1486`
- Best3 canonical: `0.8453`
- Pack canonical: `0.7941`
- Pack vs best3 canonical delta: `-0.0512`
- Best3 no-current-helper-fit proxy: `0.600`
- Expanded no-current-helper-fit proxy: `0.467`
- Relative gap reduction proxy: `22.22%`

## New Helper Contribution
- `format_calculated_distance_km` visible/called/VNC: `9 / 8 / 1`
- Called-subset outcome delta: `+0.3125`
- Called-subset canonical delta: `-0.0164`
- Called-subset gains/regressions/preserved: `3 / 0 / 5`
- Side-effect/runtime incidents: `0 / 0`

## Route Mismatch
Canonical decreased versus best3 while outcome increased. This is a route/accounting issue to carry into confirmation60, not a hidden outcome failure. The helper preserves `calculate_lat_lon_distance` and only formats the final answer.

## Decision Label
`candidate pack ready for confirmation60`
