# V2 Best3 Helper Contribution Audit

- Updated: `2026-05-04T07:02:15.534203`
- Decision label: `helper contribution verified`

## Aggregate Tool-Driven Evidence

- Unique helper-visible scenarios: `112`
- Unique helper-called scenarios: `98`
- Unique visible-not-called scenarios: `14`
- Called-helper subset mean outcome delta: `0.1823`
- No-called-helper subset mean outcome delta: `-0.0061`
- Called-helper outcome gains/regressions/preserved: `46 / 17 / 30`
- Top-50 outcome gains with a called helper: `33`
- Formal 250 no-current-helper-fit share: `0.444`

## Per-Helper Contribution

| Helper | Visible | Called | Visible-not-called | Called outcome delta | Called reference/canonical delta | VNC outcome delta | Side-effect incidents | Runtime incidents |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `relative_day_time_to_timestamp` | 32 | 29 | 3 | `0.1389` | `0.0161` | `n/a` | 0 | 0 |
| `resolve_search_window_or_bounds` | 72 | 42 | 30 | `0.2480` | `0.1616` | `-0.0526` | 0 | 0 |
| `select_record_by_timestamp_extreme` | 32 | 27 | 5 | `0.1188` | `0.2746` | `0.2000` | 0 | 0 |

## Interpretation

The victory is tool-driven: called-helper scenarios have a strong positive mean outcome delta, while scenarios without helper calls are roughly neutral/slightly negative. The main remaining issue is coverage: `44.4%` of the formal 250 had no current-helper fit.

Visible-not-called remains a refinement target, especially for `resolve_search_window_or_bounds` on remove-reminder/message lanes, but it did not prevent the portfolio from passing.

Decision label: `helper contribution verified`
