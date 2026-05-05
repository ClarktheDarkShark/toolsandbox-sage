# Final Claim Summary

## Current Validated Portfolio
- `relative_day_time_to_timestamp`
- `resolve_search_window_or_bounds`
- `select_record_by_timestamp_extreme`

Expanded V2.1 candidates were tested and parked; frozen best3 remains the validated portfolio.

## Scale Evidence
| Scale | Outcome Control | Outcome SAGE | Delta | Relative Lift | Canonical Delta | Exact | Runtime | Side Effects | Quality | Protocol Gate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 100 | 0.4010 | 0.5357 | +0.1347 | +33.58% | +0.0911 | 16 -> 23 | 0 | 0 | pass | True |
| 250 | 0.3930 | 0.4736 | +0.0806 | +20.52% | +0.0660 | 31 -> 40 | 0 | 0 | pass | True |
| 500 | 0.4830 | 0.5523 | +0.0693 | +14.35% | +0.0331 | 60 -> 76 | 0 | 0 | pass | False |
| 1032 | 0.4324 | 0.4931 | +0.0608 | +14.05% | +0.0342 | 159 -> 195 | 0 | 0 | pass | False |

## Claim
SAGE best3 clears the primary relative task-completion lift target at 100, 250, 500, and 1,032 scenarios. The 500 and 1,032 runs do not clear the older absolute +0.08 protocol-gate threshold, so the final claim should be framed as relative outcome/task-completion success with positive canonical/reference movement, not as universal protocol-gate pass at every scale.

## Limitations
- Control-cache compatibility remained strict; scale runs used fresh controls because manifest checksums differed.
- The 1,032 full-benchmark run includes external-service lanes and should be separated from the non-external 500 evidence.
- No V2.1 generated candidate is promoted; accepted-but-uncalled or negative force-call candidates remain parked.

## Decision Label
`full-benchmark 1000+ positive; best3 remains final portfolio`
