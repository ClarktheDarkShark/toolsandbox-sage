# V2.6 Micro20 Feedback Report

## Objective
Determine whether `plan_contact_search_from_scalar_constraint` can be naturally called and improve task completion before adding it to the broader candidate pack.

## Run
- Manifest: `artifacts/summaries/v2_6_contact_scalar_search_micro20/cohort_manifest.json`
- Run root: `outputs/v2_6_contact_scalar_search_micro20_rerun/mechanism_40_20260507_011804`
- Registry: `artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json`
- Generation: OFF
- Control cache: mixed, 19 cached / 1 fresh
- Cohort quality: PASS
- Dashboards opened: dashboard and task-focus on port `5674`

## Metrics
- Outcome delta vs control: `+0.3363`
- Canonical delta vs control: `+0.1185`
- Exact successes: `3 -> 7`
- Protocol gate: PASS
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`

## Helper Evidence
- `plan_contact_search_from_scalar_constraint`: visible/called/VNC `8 / 3 / 5`
- Failed attempts: `0`
- Called-subset outcome delta: `+0.4222`
- Called-subset canonical delta: `-0.0044`
- Actual outputs included safe `search_contacts` kwargs for phone and name constraints.

## Feedback Packet Summary
- Feedback packets: `artifacts/summaries/v2_6_feedback_packets/v2_6_contact_scalar_search_micro20/task_feedback.jsonl`
- No-current-helper-fit share: `40.0%`
- Feedback insufficient count: `0`

## Pipeline Blocker Diagnosis
- Adoption is not perfect, but natural calls occurred with positive called-subset outcome.
- VNC remains a monitoring issue, not a blocker, because calls were correct and non-harmful.

## Decision Label
`candidate ready for additive60`

## Exact Next Action
Run an additive60 pack with best3, retained contact pack, and `plan_contact_search_from_scalar_constraint`.
