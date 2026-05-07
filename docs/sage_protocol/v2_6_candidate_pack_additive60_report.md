# V2.6 Candidate Pack Additive60 Report

## Objective
Test whether the V2.6 expanded contact-scalar candidate pack improves over frozen best3 on a broader quality-gated 60-scenario manifest before frozen100/250.

## Candidate Pack
- Frozen best3 copied into candidate registry.
- `plan_contact_lookup_query`
- `extract_contact_field_from_search_result`
- `plan_contact_search_from_scalar_constraint`
- Registry: `artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json`
- Registry SHA-256: `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`

## Manifest
- Path: `artifacts/summaries/v2_6_candidate_pack_additive60/cohort_manifest.json`
- SHA-256: `b8e53a9f97d36a88e7d57ed52381b04c0027df520c508e727390b380d074983b`
- Scenario count: 60
- Base families: 12
- Largest family share: 13.3%
- Cohort quality: PASS

## Runs
- Best3 run: `outputs/v2_6_candidate_pack_additive60_best3/mechanism_60_20260507_012803`
- Expanded pack run: `outputs/v2_6_candidate_pack_additive60_pack/mechanism_60_20260507_013747`
- Generation: OFF
- Control cache: 60 cached / 0 fresh for both runs
- Dashboards opened: dashboard and task-focus on ports `5675` and `5676`

## Metrics: Pack vs Best3
- Best3 outcome: `0.7059`
- Pack outcome: `0.7799`
- Outcome delta: `+0.0740`
- Best3 canonical: `0.8038`
- Pack canonical: `0.8368`
- Canonical delta: `+0.0330`
- Exact successes: `14 -> 13`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- Pack protocol gate: PASS

## Helper Contribution
- `plan_contact_lookup_query`: visible/called/VNC `24 / 12 / 12`, called outcome `+0.7472`
- `extract_contact_field_from_search_result`: `24 / 7 / 17`, called outcome `+0.8945`
- `plan_contact_search_from_scalar_constraint`: `34 / 7 / 27`, called outcome `+0.7668`

## Gap Metric
- Feedback best3 no-current-helper-fit: `73.3%`
- Feedback pack no-current-helper-fit: `33.3%`
- Matched relative reduction: `54.5%`

## Pipeline Blocker Diagnosis
- Positive outcome and gap signal were strong enough to proceed.
- Exact successes regressed by one, so frozen100 was required before any claim.
- VNC remained high, especially scalar planner `27 / 34`, so broad 250 needed explicit VNC and cross-lane interference analysis.

## Decision Label
`candidate pack ready for 100`

## Exact Next Action
Run frozen100 comparing best3 and expanded contact-scalar pack on a larger quality-gated manifest.
