# V2 Architecture Readiness 20 Report

## Objective
Verify the repaired V2 architecture end to end before any larger V2 campaign.

## Preconditions
- Contribution export: ready.
- Promotion gate: ready.
- Failure memory integration: ready.
- Runtime routing scorer: ready.
- Shortfall-cluster birth: ready.
- Active/candidate registry check-only: PASS.
- Cohort quality gate: PASS.
- `--allow-low-quality-cohort`: not used.

## Manifest And Cohort
- Manifest: `artifacts/summaries/v2_architecture_readiness_20/cohort_manifest.json`
- Diversity report: `artifacts/summaries/v2_architecture_readiness_20/cohort_diversity_report.json`
- Scenario count: `20`
- Distinct base task families: `15`
- Largest duplicate family size: `2`
- No-current-helper-fit share: `0.4`

## Run
- Run root: `outputs/v2_architecture_readiness_20/mechanism_40_20260503_194428/`
- Log: `artifacts/summaries/v2_architecture_readiness_20/run_with_conda_key.log`
- Dashboard: `outputs/v2_architecture_readiness_20/mechanism_40_20260503_194428/dashboard/index.html`
- Task focus dashboard: `outputs/v2_architecture_readiness_20/mechanism_40_20260503_194428/dashboard/task_focus.html`
- Candidate registry: `artifacts/registry_candidates/v2_architecture_readiness_20/registry_manifest.json`
- Helper contribution: `outputs/v2_architecture_readiness_20/mechanism_40_20260503_194428/helper_contribution_summary.json`
- Promotion gate result: `artifacts/summaries/v2_architecture_readiness_20/promotion_gate_result.json`

## Command
```bash
conda run -n lifelong bash -lc 'export PYTHONPATH=src:.; python scripts/run_sage_protocol.py --manifest artifacts/summaries/v2_architecture_readiness_20/cohort_manifest.json --mode mechanism_40 --registry-dir artifacts/registry_candidates/v2_architecture_readiness_20 --output-root outputs/v2_architecture_readiness_20 --artifact-root artifacts --generation on --parallel-arms'
```

## Metrics
- Canonical mean: control `0.8921`, SAGE `0.8289`, delta `-0.0631`.
- Outcome mean: control `0.5606`, SAGE `0.5043`, delta `-0.0563`.
- Exact successes: control `3`, SAGE `2`, delta `-1`.
- Canonical gains/regressions/preserved: `6 / 8 / 6`.
- Outcome gains/regressions/preserved: `2 / 5 / 11`.
- Runtime exceptions: `0`.
- Side-effect preservation rows/incidents: `0`.

## Tool Birth And Validation
- Tools proposed: `5`.
- Tools accepted: `0`.
- Tools rejected: `5`.
- Rejections:
  - `select_record_by_timestamp_extreme`: `missing_downstream_tool_preservation` twice.
  - `select_contact_field_by_constraint`: `unresolved_failure_memory:search_filter_missing_tie_behavior`.
  - `next_service_tool_call`: `missing_decisive_positive_triggers` twice.

## Routing And Adoption
- Selection visible scenarios: `15`.
- Selection called scenarios: `6`.
- Visible-not-called scenarios: `9`.
- Failed helper attempts: `0`.
- Accepted-but-uncalled tools: none, because no new tools were accepted.
- `prepare_reminder_creation_args`: visible `5`, called `0`, visible-not-called `5`.
- `resolve_search_window_or_bounds`: visible `12`, called `6`, visible-not-called `6`, called-subset outcome delta `+0.0778`, called-subset canonical delta `-0.0272`.

## Contribution Export Assessment
The helper contribution export worked and produced called, visible-not-called, hidden/no-call, side-effect, runtime, registry size, runtime bundle, and accepted-but-uncalled evidence.

## Promotion Gate Assessment
Promotion gate worked and blocked promotion:
- `prepare_reminder_creation_args`: missing shortfall-cluster evidence, no later-task calls, visible-not-called rate too high.
- `resolve_search_window_or_bounds`: missing shortfall-cluster evidence.

## Failure Memory Assessment
Failure memory affected gating as intended:
- `select_contact_field_by_constraint` was rejected for unresolved `search_filter_missing_tie_behavior`.

## Runtime Routing Assessment
Generic routing ran and logged routing decisions. However, retained-helper visibility is still too broad for this readiness cohort, especially `prepare_reminder_creation_args` visible-but-uncalled in all 5 visible scenarios. Runtime routing needs another repair to use promotion/contribution evidence and cluster evidence to suppress legacy helpers with poor recent adoption.

## Cluster Birth Assessment
Cluster-aware birth ran, but generated candidates did not satisfy the strengthened contract. This is correct gate behavior, but the generator/observation path still fails to produce valid side-effect-preserving and trigger-complete specs from clusters.

## Interpretation
The repaired architecture executed safely and produced the right evidence artifacts, but readiness-20 did not pass. The system is not ready for the full V2 campaign because the generation/cluster-birth path produced no accepted tools and runtime routing still exposed low-value retained helpers.

Primary blocker: cluster birth/generation quality. Secondary blocker: runtime routing should incorporate recent contribution/promotion evidence to reduce visible-not-called pollution.

## Tests
- `PYTHONPATH=src:. pytest tests/unit/test_helper_contribution.py tests/unit/test_promotion_gate.py tests/unit/test_failure_memory_integration.py tests/unit/test_runtime_routing_scorer.py tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py -q`
- Result: `73 passed`.
- `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_architecture_readiness_20/registry_manifest.json`
- Result: PASS.

## Decision Label
not ready: repair cluster birth
