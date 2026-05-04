# V2 Reporting and Contribution Audit Report

## Objective
Audit whether reports can prove tool-driven improvement rather than overall SAGE-vs-control movement.

## Current Strengths
- Comparison reports include canonical and outcome metrics.
- Run metrics include accepted tools, visible tools, called scenarios, visible-not-called scenarios, attempted scenarios, and failed attempts.
- Dashboards expose task focus views and generated-tool usage markers.
- Cache metrics are recorded when enabled.

## Remaining Gaps
- Contribution reporting is not yet sufficient as an automatic claim-grade artifact.
- Reports need built-in called-helper subset, visible-not-called subset, hidden/no-call subset, and failed-attempt subset deltas by helper.
- Reports should explicitly separate retained-helper gains from newly generated candidate gains.
- Cost/token accounting is not yet summarized as fair compute accounting.
- Route mismatch is not consistently tied to helper-equivalence/final-state evidence in every report.

## Required Next Repair
Add a machine-readable contribution export that includes, per helper:
- visible scenarios
- called scenarios
- visible-not-called scenarios
- failed-attempt scenarios
- outcome/canonical deltas for each subset
- gains/regressions/preserved for each subset
- side-effect/runtime incidents
- accepted-but-uncalled tools
- compute/cache/token summary when available

## Decision Label
reporting needs repair
