# V2 Architecture Audit Plan

## Objective
Audit whether SAGE is ready for a V2 autonomous tool-evolution campaign before launching larger 20/60/100/250 evaluations.

## Current Empirical Status
- V1 formal 100 qualified: outcome relative lift `+17.9%`, canonical relative lift `+10.3%`.
- V1 formal 250 failed primary target: outcome relative lift `+0.04%`, canonical relative lift `+5.09%`, exact success `23 -> 22`.
- Runtime stability and side-effect safety were strong: `0` runtime exceptions and `0` side-effect violations in formal 250.
- Active v1 registry: `artifacts/registry_phaseE_balanced_final/registry_manifest.json`.
- Active v1 helpers: `prepare_reminder_creation_args`, `resolve_search_window_or_bounds`.

## Known Blockers
- Large-run success was likely overestimated by earlier near-duplicate/easy-task cohorts.
- Current formal 250 had good safety but flat task-completion lift.
- Tool birth still depends heavily on scenario-derived observations and canonical keys.
- Generated candidates can be accepted diagnostically without enough proof of later adoption/value.
- Runtime exposure still contains tool-name-specific visibility logic.
- Reports expose visible/called counts, but contribution reporting is not yet sufficient for claim-grade attribution.

## Files Likely Involved
- `src/sage_ts/adequacy/inadequacy_classifier.py`
- `src/sage_ts/orchestration/online_birth.py`
- `src/sage_ts/generation/tool_generator.py`
- `src/sage_ts/generation/tool_spec.py`
- `src/sage_ts/adequacy/candidate_gate.py`
- `src/sage_ts/evaluation/task_strata.py`
- `src/sage_ts/runtime/toolsandbox_integration.py`
- `src/sage_ts/evaluation/run_metrics.py`
- `src/sage_ts/dashboard/exporters.py`
- `scripts/run_sage_protocol.py`
- `scripts/migrate_registry.py`

## Audit Phases
1. State and baseline audit.
2. Architecture depth audit.
3. Cohort quality and near-duplicate gate.
4. Generated-tool contract audit and repair.
5. Gate, failure memory, and promotion lifecycle audit.
6. Routing/runtime bundle audit.
7. Reporting/contribution audit.
8. Mini 20-scenario readiness check only after Phases 2-6 are ready.

## Stop/Go Criteria For V2 Campaign
Go only if:
- Cohort quality gate mechanically blocks low-diversity broad runs.
- Generated-tool contract requires deterministic, abstaining, side-effect-preserving, cluster-backed specs.
- Candidate/active/frozen registry lifecycle is enforced mechanically.
- Runtime exposure can route a broader candidate library without tool-name-specific pollution.
- Reports can prove whether gains are tool-driven.
- A generation-on 20-scenario readiness diagnostic passes without registry pollution.

Decision: continue architecture audit before launching V2 campaign.
