# V2.3 Medium-Grain Candidate Triage

## Candidate

- Tool: `constraint_to_action_planner`
- Registry: `artifacts/registry_candidates/v2_3_medium_grain_diag20_20260505_184209/registry_manifest.json`
- Registry SHA-256: `e9176beca3d8f0a95d97de09242cff9f718e050c341c8c90a022e4e87c262f1c`
- Family: `composite_workflow_helper`
- Generated from cluster: `composite:constraint_to_action_planner`
- Status: parked

## Validation

- Static/schema validation: PASS after framework repair
- Runtime smoke: PASS
- Live validation: PASS with warning `live_missing_expected_milestone_calls_replaced`
- Negative applicability: PASS in validation examples

## Natural Adoption

- Run: `outputs/v2_3_medium_grain_diag20_20260505_184209/mechanism_60_20260505_184213`
- Visible/called/VNC: `6 / 0 / 6`
- Natural calls: `0`
- Accepted-but-uncalled: yes

## Force-Call Evidence

- Run: `outputs/v2_3_medium_grain_force20_20260505_184848/mechanism_60_20260505_184852`
- Visible/called/VNC: `15 / 13 / 2`
- Called-subset outcome delta: `-0.13126404560161367`
- Called-subset canonical delta: `-0.13004658549699968`
- Outcome gains/regressions/preserved: `3 / 7 / 3`
- Runtime incidents: `0`
- Side-effect incidents: `9`

## Interpretation

The candidate is not merely a routing casualty. Force-call made it callable and frequently called, but the called subset was harmful. The broad medium-grain contract mixes answer-only lookup, selection, and side-effect argument preparation. That makes the tool attractive in too many contexts and creates side-effect-preservation failures when expected downstream action semantics do not match the actual task.

## Tests Run

- Targeted V2.3 unit suite: `127 passed`
- Artifact builder compile: PASS
- Candidate, V2.2 new-toolset, and frozen best3 registry check-only: PASS

## Decision Label

`medium-grain skill concept negative`

## Exact Next Action

Do not run confirmation60. Park `constraint_to_action_planner`. If medium-grain skills are revisited, require narrower contracts that separate answer-only resolvers from side-effect action planners and prove positive called-subset outcome before confirmation.
