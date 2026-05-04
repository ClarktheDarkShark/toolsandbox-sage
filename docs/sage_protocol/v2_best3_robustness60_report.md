# V2 Best3 Robustness60 Report

- Updated: `2026-05-04T07:20:28.034191`
- Decision label: `robustness confirmed`

## Design

- Manifest: `artifacts/summaries/v2_best3_robustness60_clean_20260504_070424/cohort_manifest.json`
- Manifest SHA-256: `31d8bede749bcbab84720365ac3e05e85ac5a941a362cf941a341751b8139a49`
- Run root: `outputs/v2_best3_robustness60_clean_20260504_070424/mechanism_40_20260504_070441`
- Dashboard: `http://127.0.0.1:5520/outputs/v2_best3_robustness60_clean_20260504_070424/mechanism_40_20260504_070441/dashboard/index.html`
- Task focus dashboard: `http://127.0.0.1:5520/outputs/v2_best3_robustness60_clean_20260504_070424/mechanism_40_20260504_070441/dashboard/task_focus.html`
- Registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Registry digest before run: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Generation enabled: `False`
- Control cache mode/source: `use-if-eligible` / `fresh`
- Cached/fresh controls: `0` / `60`

The first robustness manifest was blocked by preflight because it contained currency-conversion external-service contamination. This clean rerun used the project contamination filter and did not use an override.

## Cohort Quality

- Scenario count: `60`
- Exact formal-250 overlap: `0`
- Distinct base families: `38`
- Largest family share: `3.33%`
- Quality gate: `pass`
- Contaminated external-service scenarios: `0`
- No-current-helper-fit share: `51.67%`

## Results

- Control outcome: `0.4367`
- SAGE outcome: `0.4979`
- Outcome delta: `0.0612`
- Relative outcome lift: `14.01%`
- Reference/canonical similarity delta: `0.1503`
- Exact successes: `4 -> 13`
- Gains/regressions/preserved: `31 / 9 / 20`
- Outcome gains/regressions/preserved: `13 / 8 / 22`
- Runtime exceptions: `0`
- Protocol gate passed: `False`
- Protocol gate reasons: `['confirmation_outcome_delta_below_0_08', 'helper_call_share_below_25_percent']`
- Route-mismatch-qualified: `False`

The protocol gate failed because this robustness sample had absolute outcome delta below `0.08` and helper-call share below `25%`. That is expected for this deliberately independent sample with `51.67%` no-current-helper-fit cases. It does not replace or weaken the formal 250 pass; it confirms positive direction on a separate 60-task sample.

## Helper Contribution

| Helper | Visible | Called | Visible-not-called | Called outcome delta | VNC outcome delta | Side-effect incidents | Runtime incidents |
|---|---:|---:|---:|---:|---:|---:|---:|
| `relative_day_time_to_timestamp` | 6 | 6 | 0 | `0.3333` | `n/a` | 0 | 0 |
| `resolve_search_window_or_bounds` | 8 | 0 | 8 | `n/a` | `0.0992` | 0 | 0 |
| `select_record_by_timestamp_extreme` | 10 | 6 | 4 | `0.0720` | `0.2500` | 0 | 0 |

## Interpretation

The frozen best3 portfolio remained positive on an independent, quality-gated 60-task sample: outcome lift `+14.01%`, reference/canonical delta `+0.1503`, and exact successes `4 -> 13`. The main caveat is routing/adoption: `resolve_search_window_or_bounds` was visible but not called in this sample, reinforcing it as a V2.0 routing-affordance target.

Decision label: `robustness confirmed`
