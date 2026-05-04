# V2 Formal 250 Metric Audit Report

- Updated: `2026-05-04T07:02:15.534203`
- Decision label: `metrics verified`

## Direct Calculation

- Control outcome: `0.3930079367`
- SAGE outcome: `0.4736471752`
- Outcome delta: `0.4736471752 - 0.3930079367 = 0.0806392385`
- Relative outcome lift: `0.0806392385 / 0.3930079367 = 20.52%`
- Control reference/canonical similarity: `0.6658983202`
- SAGE reference/canonical similarity: `0.7318836373`
- Reference/canonical delta: `0.0659853171`
- Exact success delta: `31 -> 40` = `+9`

## Count Audit

- Total paired scenarios: `250`
- Reference/canonical rows with delta: `250`
- Reference/canonical gains/regressions/preserved recomputed: `102 / 53 / 95`
- Reported gains/regressions/preserved: `102 / 53 / 95`
- Outcome rows with non-null outcome delta: `202`
- Outcome gains/regressions/preserved recomputed: `73 / 40 / 89`
- Reported outcome gains/regressions/preserved: `73 / 40 / 89`

The outcome gain/regression/preserved counts sum to `202`, not `250`, because only `202` scenarios exported an included outcome/task-completion check. The remaining `48` scenarios still contribute to reference/canonical similarity but have `outcome_delta = null`; this is expected filtering, not a metric arithmetic bug.

## Protocol Gate And Interval

- Protocol gate result: `True`
- Protocol gate reasons: `[]`
- Route-mismatch-qualified: `False`
- Approximate paired 95% CI for mean outcome delta across non-null outcome rows: `[0.016657, 0.144622]`

## Rounding

Displayed values in reports are rounded. The unrounded relative lift is `0.20518475819339366`, displayed as `20.52%`.

Decision label: `metrics verified`
