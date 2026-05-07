# Chapter 3 Methodology Preparation

Decision label: `chapter 3 methodology package ready`

## Framing

SAGE is the research system. The coding agent is a development assistant used to implement, audit, and operate the experimental pipeline. Dissertation language should attribute the method, tool lifecycle, routing policy, validation gates, and statistical comparisons to SAGE and the protocol, not to the external coding assistant.

Outcome/task-completion is the primary endpoint. Canonical/reference similarity is secondary and must be reported honestly, especially where deterministic helpers substitute intermediate routes.

## Methodology Section Map

| Chapter 3 Section | Implementation / Artifact | Methodological Claim | Caveat |
|---|---|---|---|
| Task cohort construction | `src/sage_ts/config/splits.py`, `src/sage_ts/evaluation/task_strata.py`, `docs/sage_protocol/manifests/`, `artifacts/summaries/*/cohort_manifest.json` | Cohorts are manifest-defined and quality-gated to avoid near-duplicate dominance. | Task-family taxonomy is a protocol-defined heuristic. |
| Control/baseline arm | `scripts/run_sage_protocol.py`, `src/sage_ts/evaluation/control_baseline_cache.py` | Control is run or reused task-by-task from eligible cached baseline values. | Cached controls can be score-complete but trace-incomplete. |
| SAGE arm | `src/sage_ts/adapters/sage_run_adapter.py`, `src/sage_ts/runtime/toolsandbox_integration.py` | SAGE uses a registry-bounded helper portfolio and original ToolSandbox tools. | Frozen final runs must use generation OFF. |
| Generated-tool lifecycle | `src/sage_ts/generation/`, `src/sage_ts/validation/`, `src/sage_ts/registry/manifest.py` | Tools pass schema/static/live validation before registry acceptance. | Generated-but-uncalled is a diagnosis, not no-value evidence. |
| Candidate validation gates | `src/sage_ts/validation/sandbox_validator.py`, `src/sage_ts/validation/live_candidate_check.py`, `src/sage_ts/validation/output_normalization.py` | Candidate specs must include triggers, abstention, ambiguity behavior, side-effect preservation, and route-accounting when relevant. | Earlier campaigns had evolving gates; final claims use frozen registries. |
| Routing and bounded exposure | `src/sage_ts/runtime/routing_scorer.py` | Helpers are exposed by trigger/family fit, negative triggers, evidence, fair-chance logic, and context budget. | Final frozen runs must pin or disable contribution evidence to avoid mtime dependence. |
| Feedback packets | `src/sage_ts/evaluation/feedback_packets.py`, `scripts/export_v2_6_feedback_packets.py` | Per-task feedback records trace summaries, helper calls, routing decisions, scores, safety, and missing deterministic steps. | Cached-control trace completeness must be read from `control_trace_completeness`. |
| Contribution analysis | `src/sage_ts/evaluation/helper_contribution.py`, `helper_contribution_summary.json` | Helper visible/called/VNC and called-subset deltas are exported for tool-driven interpretation. | Called-subset estimates are descriptive and may be sparse. |
| Safety checks | side-effect preservation reports, minefield/outcome checks, runtime exception counts | Final claims require zero runtime exceptions and zero helper side-effect incidents. | Negative/insufficient-information tasks require abstention/clarification behavior. |
| Cache policy | OpenAI response cache in `src/sage_ts/cache/openai_response_cache.py`; task-level control cache in `src/sage_ts/evaluation/control_baseline_cache.py` | Provider-response caching and task-level baseline caching are separate mechanisms. | SAGE/candidate arms are not treated as cached claim evidence. |
| Cohort quality gates | `src/sage_ts/evaluation/task_strata.py::cohort_policy_report` | Cohorts can be blocked for low quality, near-duplicate dominance, or contamination. | Diagnostic overrides must not be used for final claims. |
| Statistical comparison plan | `scripts/write_final_statistical_analysis.py`, `docs/sage_protocol/final_statistical_analysis_report.md` | Use paired scenario-level deltas, bootstrap CIs, and paired randomization tests. | Cache variance is summarized separately and not folded into the primary bootstrap. |
| Limitations and non-claims | `docs/sage_protocol/final_limitations_and_future_work.md` | Best3 broad claim and V2.6 secondary evidence are separated. | V2.6 is non-harmful/variance-limited at current-code 500 and below the 10% broad gap target. |

## Definitions To Include

| Term | Dissertation Definition |
|---|---|
| Outcome/task-completion score | Final answer or final-state task success score. Primary endpoint. |
| Canonical/reference similarity | Similarity to expected benchmark route or milestone behavior. Secondary endpoint. |
| Exact success | Scenario-level exact/canonical score threshold used in reports; report source must be specified. |
| Generated helper | Deterministic tool produced by SAGE from shortfall evidence and accepted by validation gates. |
| Frozen registry | Registry used with generation OFF for validation; no tool birth or registry mutation during the run. |
| No-current-helper-fit | Protocol heuristic indicating no loaded current helper matches expected helper-fit taxonomy for the scenario. It is a coverage proxy, not proof no helper could exist. |
| Visible-not-called | Helper was exposed to the acting model but not called. This diagnoses adoption/routing/affordance/value uncertainty. |
| Route mismatch | Canonical route divergence that may occur when deterministic helper substitution preserves outcome. |
| Side-effect incident | Helper behavior that risks or violates downstream side-effect preservation. |
| Runtime exception | Execution failure during control or SAGE run. Final claim runs require zero. |

## Diagrams Needed

- Full SAGE pipeline diagram: manifest -> control cache planning -> control arm -> SAGE arm -> scoring -> dashboard/report.
- Generated-tool lifecycle diagram: shortfall cluster -> spec -> validation -> candidate registry -> routing -> contribution -> frozen evaluation.
- Evidence separation table: best3 broad claim, V2.6 matched gap closure, current-code original250, current-code 500, deferred 1032.
- Cache-policy table: OpenAI response cache vs task-level control baseline cache vs fresh runs.
- Metric definitions table: outcome, canonical, exact success, no-current-helper-fit, VNC, called-subset contribution.
- Safety table: runtime exceptions, helper side-effect incidents, minefield/insufficient-information guardrails.
- Claim-boundary table: what is claimed, what is secondary evidence, what is not claimed.

## Recommended Chapter 3 Structure

1. Research system overview: SAGE as self-evolving deterministic helper system.
2. Task environment: ToolSandbox scenarios, manifests, task-family stratification.
3. Experimental arms: control/baseline, frozen SAGE, generation-enabled discovery.
4. Tool lifecycle: shortfall clustering, generation, validation, repair, promotion/freeze.
5. Runtime routing: bounded helper exposure and final-run evidence pinning/disablement.
6. Metrics: outcome primary, canonical secondary, exact success, helper-fit, contribution.
7. Safety: side-effect preservation, insufficient-information abstention, runtime exception tracking.
8. Caching and reproducibility: OpenAI response cache, task-level control cache, trace completeness labels.
9. Statistical analysis: paired deltas, bootstrap CIs, randomization tests, cache variance caveat.
10. Evidence boundaries: best3 broad validation versus V2.6 secondary/candidate validation.
11. Limitations and non-claims.

## Tables To Generate For Dissertation Draft

| Table | Source |
|---|---|
| Final registry table with hashes | `docs/sage_protocol/final_evidence_index.md` |
| Formal best3 scale results | `docs/sage_protocol/final_claim_summary.md` |
| Current-code V2.6 matched results | `docs/sage_protocol/v2_6_current_code_evidence_synthesis.md` |
| Statistical interval table | `docs/sage_protocol/final_statistical_analysis_report.md` |
| Cache trace-completeness table | `docs/sage_protocol/final_run_readiness_report.md` |
| Heuristics version table | `docs/sage_protocol/protocol_heuristics_v1.json` |
| Limitations/non-claims table | `docs/sage_protocol/final_limitations_and_future_work.md` |

## Chapter 3 Readiness Verdict

The methodology package is ready for drafting with caveats preserved. The final-run procedure should be described as requiring preflight checks, frozen registries, generation OFF, explicit routing evidence mode, control-cache accounting, contribution export, dashboard export, and post-run statistical analysis.
