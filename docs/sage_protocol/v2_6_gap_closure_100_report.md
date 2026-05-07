# V2.6 Gap Closure 100 Report

## Objective
Validate whether the expanded contact-scalar pack remains positive versus frozen best3 at 100 scenarios with generation OFF.

## Manifest
- Path: `artifacts/summaries/v2_6_gap_closure_100/cohort_manifest.json`
- SHA-256: `302b5c8da1a49a4418a8bc88ddf4eedefa4cca9a578e28220fbf2b93d6f58eef`
- Scenario count: 100
- Base families: 13
- Largest family share: 8.0%
- Cohort quality: PASS
- Role counts: contact positives 32, best3 preservation 36, negative/abstention 24, no-helper negative 8

## Registry
- Best3: `artifacts/registry_frozen_best3_claim/registry_manifest.json`, SHA `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Expanded: `artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json`, SHA `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`

## Runs
- Best3: `outputs/v2_6_gap_closure_100_best3/validate_100_20260507_014945`
- Expanded: `outputs/v2_6_gap_closure_100_expanded/validate_100_20260507_020927`
- Generation: OFF
- Control cache: 100 cached / 0 fresh for both runs
- Dashboards opened: dashboard and task-focus on ports `5677` and `5678`

## Metrics: Expanded vs Best3
- Best3 outcome: `0.6766`
- Expanded outcome: `0.7340`
- Outcome delta: `+0.0574`
- Best3 canonical: `0.8083`
- Expanded canonical: `0.8621`
- Canonical delta: `+0.0538`
- Exact successes: `29 -> 34`
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- Expanded protocol gate: PASS

## Gap Metric
- Best3 no-current-helper-fit share: `64.0%`
- Expanded no-current-helper-fit share: `40.0%`
- Matched relative reduction: `37.5%`
- This reaches the matched 100 target and the original absolute `<=40.0%` reference threshold.

## Helper Contribution
- `plan_contact_lookup_query`: visible/called/VNC `24 / 15 / 9`, called outcome `+0.6312`
- `extract_contact_field_from_search_result`: `24 / 6 / 18`, called outcome `+0.5806`
- `plan_contact_search_from_scalar_constraint`: `40 / 9 / 31`, called outcome `+0.6149`
- All new helpers had runtime incidents `0` and side-effect incidents `0`.

## Pipeline Blocker Diagnosis
- Frozen100 was positive on outcome, canonical, exact success, and gap share.
- Remaining risk for frozen250: scalar planner VNC remained high, so broad gap-enriched 250 was required.

## Decision Label
`expanded portfolio ready for 250`

## Exact Next Action
Run matched frozen250 with best3 and expanded pack, generation OFF, task-level control cache, contribution export, feedback packets, and no code edits during runs.
