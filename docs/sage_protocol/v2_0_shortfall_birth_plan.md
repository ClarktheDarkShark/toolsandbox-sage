# V2.0 Shortfall Birth Plan

- Updated: `2026-05-04T07:20:28.034191`
- Decision label: `start V2.0 candidate discovery`

## Boundary

Do not modify the frozen v1.0 best3 claim registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`. V2.0 work must use separate candidate registries and compare against the frozen best3 portfolio.

## Starting Evidence

- Formal 250 passed with relative outcome lift `20.52%`.
- Formal 250 no-current-helper-fit share: `44.40%`.
- Robustness 60 remained positive with relative outcome lift `14.01%` but had low helper-call share.

## V2.0 Focus Areas

1. Cluster the no-current-helper-fit scenarios from formal 250 and robustness 60 by failure mechanism, not by scenario name.
2. Prioritize clusters with repeated outcome regressions and available deterministic intermediate structure.
3. Generate candidate tools only from diverse clusters with positive and negative examples.
4. Keep candidates in candidate registries until they show validation proof, safe abstention, later-task adoption, and positive called-subset contribution.
5. Compare every candidate against the frozen best3 portfolio, not against a weaker baseline.

## Immediate Candidate Lanes

- Service/precondition sequencing where `next_service_tool_call` evidence exists but was not retained.
- Contact/message constraint selection where current best3 does not cover search-by-relationship or phone/name lookup failures.
- Reminder remove/modify recency workflows where `resolve_search_window_or_bounds` is visible-not-called or search-window + selector sequencing is incomplete.
- Insufficient-information handling where helpers should be hidden or abstain cleanly.

## Next Experiment

Run a V2.0 discovery-40 or discovery-60 with generation ON, candidate registry separate from the frozen best3 registry, and a manifest built primarily from no-current-helper-fit regressions plus negative cases. Do not run another formal 250 until at least one new candidate is adopted and confirmed frozen against the best3 baseline.

Decision label: `start V2.0 candidate discovery`
