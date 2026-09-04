# Final Statistical Analysis Report

> **SUPERSEDED — ARCHIVAL ONLY.** These analyses and decisions are not current
> paper evidence and must not be copied into Chapter 4. See
> [current_state.md](current_state.md).

## Scope

This report is generated from existing paired comparison, helper-contribution, feedback-summary, and control-cache artifacts. It does not run new benchmarks and does not modify registries.

Outcome/task-completion is primary. Canonical/reference similarity is secondary. Best3 broad evidence and V2.6 expanded contact-scalar evidence are reported separately.

## Best3 Broad Evidence Versus Control

| Evidence | N | Outcome Delta | Outcome 95% Bootstrap CI | Outcome Permutation p | Canonical Delta | Exact Paired Delta | Runtime | Protocol Gate |
|---|---:|---:|---|---:|---:|---:|---:|---|
| best3_formal100_vs_control | 100 | 0.1239 | [0.0370, 0.2109] | 0.0073 | 0.0911 | 0.0700 | 0 | True |
| best3_formal250_vs_control | 250 | 0.0652 | [0.0139, 0.1159] | 0.0157 | 0.0660 | 0.0360 | 0 | True |
| best3_formal500_vs_control | 500 | 0.0532 | [0.0209, 0.0862] | 0.0009 | 0.0331 | 0.0320 | 0 | False |
| best3_formal1032_vs_control | 1032 | 0.0471 | [0.0262, 0.0683] | 0.0001 | 0.0342 | 0.0349 | 0 | False |

## V2.6 Expanded Versus Current-Code Best3

| Evidence | N | Outcome Delta | Outcome 95% Bootstrap CI | Outcome Permutation p | Canonical Delta | Exact Paired Delta | Best3 No-Fit | Expanded No-Fit | Gap Reduction |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| v2_6_current_code_original250_expanded_vs_best3 | 250 | 0.0081 | [-0.0315, 0.0483] | 0.6955 | -0.0283 | -0.0320 | 0.520 | 0.460 | 11.54% |
| v2_6_current_code_500_expanded_vs_best3 | 500 | 0.0078 | [-0.0210, 0.0362] | 0.5922 | 0.0225 | 0.0020 | 0.676 | 0.628 | 7.10% |

## Cache Variance Treatment

Primary bootstrap and permutation analyses are paired over scenario-level realized scores in the stored artifacts. Task-level cached controls are treated as fixed score-complete baseline estimates for these intervals. Control-cache reports are included in the JSON output with cached/fresh counts and cached-task variance summaries, but cache variance is not folded into the primary bootstrap interval. Interpret intervals as conditional on the stored baseline artifacts, not as a full model-stochastic uncertainty decomposition.

Cached-control feedback packets may be score-complete but trace-incomplete when the synthetic cached row has no historical conversation trajectory. This affects trace-level feedback interpretation, not score arithmetic.

## Evidence Separation

- Best3 broad evidence remains the protected primary portfolio claim.
- V2.6 expanded contact-scalar evidence is secondary: matched gap closure is strong, current-code original250/500 is non-harmful and modestly positive, and broad 500 helper-fit reduction remains below the 10% target.
- Generated-but-uncalled tools remain adoption/routing/callability diagnoses, not no-value conclusions.

## Output Artifacts

- JSON: `artifacts/summaries/final_statistical_analysis/analysis.json`
- Report generated with bootstrap iterations: `5000` and permutation iterations: `10000`.
