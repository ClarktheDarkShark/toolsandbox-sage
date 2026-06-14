# Chapter 3 Methodology Preparation

Decision label: `chapter 3 methodology package ready`

## Framing

Dissertation language should attribute the method, tool lifecycle, routing
policy, validation gates, and statistical comparisons to SAGE and the protocol.

Outcome/task-completion is the primary endpoint. Canonical/reference similarity is secondary and must be reported honestly, especially where deterministic helpers substitute intermediate routes.

Current methodology comment: SAGE Praxis with true self-evolution working is the main SAGE system going forward for Chapter 3 drafting and future validation campaigns. This is a methodology/current-system marker, not a protected final-claim promotion.

Prepared figure package: `docs/sage_protocol/chapter3_methodology_figures.md`.

## Methodology Section Map

| Chapter 3 Section | Implementation / Artifact | Methodological Claim | Caveat |
|---|---|---|---|
| Task cohort construction | `src/sage_ts/config/splits.py`, `src/sage_ts/evaluation/task_strata.py`, `docs/sage_protocol/manifests/`, `artifacts/summaries/*/cohort_manifest.json` | Cohorts are manifest-defined and quality-gated to avoid near-duplicate dominance. | Task-family taxonomy is a protocol-defined heuristic. |
| Control/baseline arm | `scripts/run_sage_protocol.py`, `src/sage_ts/evaluation/control_baseline_cache.py` | Control is run or reused task-by-task from eligible cached baseline values. | Cached controls can be score-complete but trace-incomplete. |
| SAGE arm | `src/sage_ts/adapters/sage_run_adapter.py`, `src/sage_ts/runtime/toolsandbox_integration.py` | SAGE uses a registry-bounded helper portfolio and original ToolSandbox tools. | Frozen final runs must use generation OFF. |
| Generated-tool lifecycle | `src/sage_ts/generation/`, `src/sage_ts/validation/`, `src/sage_ts/registry/manifest.py` | Tools pass schema/static/live validation before registry acceptance. | Generated-but-uncalled is a diagnosis, not no-value evidence. |
| Candidate validation gates | `src/sage_ts/validation/sandbox_validator.py`, `src/sage_ts/validation/live_candidate_check.py`, `src/sage_ts/validation/output_normalization.py` | Candidate specs must include triggers, abstention, ambiguity behavior, side-effect preservation, and route-accounting when relevant. | Earlier campaigns had evolving gates; final claims use frozen registries. |
| Routing and bounded exposure | `src/sage_ts/runtime/routing_scorer.py` | Helpers are exposed by trigger/family fit, negative triggers, evidence, fair-chance logic, and context budget. | Final frozen runs must pin or disable contribution evidence to avoid mtime dependence. |
| Actor/checker bridge policy | `src/sage_ts/adapters/openai_toolsandbox_roles.py`, `src/sage_ts/adapters/sage_run_adapter.py` | When enabled, SAGE includes a general bridge policy that helps the actor naturally adopt retained helpers, preserve final answers after helper calls, and preserve required original ToolSandbox side effects. | This is a treatment component, not registry-only value. It must be feature-flagged, documented, and validated with zero side-effect incidents. |
| Feedback packets | `src/sage_ts/evaluation/feedback_packets.py`, `scripts/export_v2_6_feedback_packets.py` | Per-task feedback records trace summaries, helper calls, routing decisions, scores, safety, and missing deterministic steps. | Cached-control trace completeness must be read from `control_trace_completeness`. |
| Contribution analysis | `src/sage_ts/evaluation/helper_contribution.py`, `helper_contribution_summary.json` | Helper visible/called/VNC and called-subset deltas are exported for tool-driven interpretation. | Called-subset estimates are descriptive and may be sparse. |
| Safety checks | side-effect preservation reports, minefield/outcome checks, runtime exception counts | Final claims require zero runtime exceptions and zero helper side-effect incidents. | Negative/insufficient-information tasks require abstention/clarification behavior. |
| Cache policy | OpenAI response cache in `src/sage_ts/cache/openai_response_cache.py`; task-level control cache in `src/sage_ts/evaluation/control_baseline_cache.py`; external-service cache manifest in `docs/sage_protocol/praxis_external_service_cache_manifest.md` | Provider-response caching, task-level baseline caching, and external-service response fixtures are separate mechanisms. | SAGE/candidate task arms are not treated as cached claim evidence; external-service fixtures must be read-only, hash-recorded, and task-selection-neutral. |
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
| Bridge policy | General runtime policy that tells the actor how to use side-effect-free helpers without replacing required original ToolSandbox side-effect calls, and tells the checker how to verify that preservation from execution traces. |

## Praxis Bridge Policy Treatment

Praxis should be described as a candidate SAGE treatment with two separable parts:

1. A frozen helper registry, containing deterministic side-effect-free helper tools.
2. A feature-flagged actor/checker bridge policy, enabled by `SAGE_PRAXIS_BRIDGE_POLICY=combined`.

The bridge policy is not a force-call mechanism and is not allowed to inspect truth labels, expected answers, scenario IDs beyond normal manifest execution, or prior SAGE traces. It supplies general operating rules that were already part of the intended SAGE process but were not included in the earlier registry-only final-hardening isolation.

The policy includes:

- Natural helper adoption guidance for search-window, selector, derived-value, and action-preparation helpers.
- Scalar/list argument guidance so helpers are called with benchmark-visible data rather than opaque payloads.
- Final-answer retention so a useful helper result is not lost after later ToolSandbox calls.
- Temporal-anchor discipline: do not invent current timestamps, years, or timezones; use visible anchors or environment defaults, otherwise ask or abstain.
- Explicit preservation of original side-effect tools: helpers may prepare arguments, but the original ToolSandbox setter, contact, reminder, or send-message tool must still be called when the task requires a state change.
- Setter-success clarification: a `None` return from original ToolSandbox state setters is interpreted as success, not failure.
- Insufficient-information discipline: do not substitute self records, unrelated domains, broad guesses, or ambiguous search results for a missing target.
- Trace plus conversation-visible side-effect checking to avoid both missed preservation failures and checker false positives.
- Optional read-only ToolSandbox external-service response fixtures for quota-limited RapidAPI-backed tools, with cache hash and miss policy recorded. This is distinct from SAGE task caching and may not be used for scenario selection, labels, expected answers, or prior SAGE traces.

Methodology language should therefore say "Praxis combined treatment" or "Praxis registry plus bridge policy" unless an ablation has separately validated registry-only value.

Completed review result to describe only as combined-treatment evidence:

- Formal500 run: `outputs/praxis_combined_bridge_policy/formal500_full_v2_bridge_repair_rapid_cache_polars1/full_benchmark_20260511_190013`.
- Canonical/reference: `0.670025 -> 0.757369`, delta `+0.087344`, relative lift `+13.04%`.
- Outcome/task completion: `0.594872 -> 0.839943`, delta `+0.245071`, relative lift `+41.20%`.
- Runtime exceptions: `0`.
- Helper failures / side-effect incidents: `0 / 0`.
- Controls: `500 cached / 0 fresh`; candidate arm fresh; OpenAI response cache disabled; generation off; routing evidence disabled; diagnostic force env vars absent.
- External-service fixture: RapidAPI cache read-only, SHA-256 `3ed7732443c44d7d26e0f46ac32fa2e09fc773278368c6f13131021afafdbf25`.

This result can support a chapter discussion of the combined SAGE bridge policy,
but not a registry-only claim. A protected claim requires a same-runtime matched
ablation for best3, V2.6, registry-only Praxis, and combined Praxis.

### Bridge Policy Pseudocode

```text
for each sealed scenario in manifest order:
    run control arm
        if eligible baseline cache has >=3 compatible completed controls:
            reuse task-level control score and record cache provenance
        else:
            execute fresh control

    run SAGE/Praxis arm fresh
        assert generation == off
        assert candidate task cache == off
        assert OpenAI response cache == disabled
        assert external service cache == off or read_only_with_hash_recorded
        load frozen registry by hash
        route a bounded helper bundle without mtime-selected evidence

        if SAGE_PRAXIS_BRIDGE_POLICY == "combined":
            add general actor rules:
                use helpers for deterministic selection, timestamp,
                recency, precondition, or final-action preparation
                do not call helpers for irrelevant task families
                do not replace required original side-effect calls
                preserve the best final answer after helper calls
                treat original setter None return as success

        actor completes task naturally
        checker validates:
            runtime exceptions == 0
            helper runtime failures == 0
            for every helper that prepares a side effect:
                original ToolSandbox side-effect call appears later
                required arguments match the helper-prepared action
                no helper itself mutates state

    score paired outcome and canonical/reference metrics
    export dashboard, contribution, cache, and safety artifacts
```

### Claim Boundary

A clean result with this policy enabled supports a combined-treatment claim only. A registry-only claim requires the same candidate registry to reproduce without `SAGE_PRAXIS_BRIDGE_POLICY=combined` and without importing bridge/checker behavior.

## Self-Evolving SAGE Treatment

The self-evolving treatment is distinct from frozen final validation. It starts with no generated helpers, keeps generation enabled, observes task-local inadequacy signals, generates deterministic helper candidates, validates them, stores accepted helpers in a run-local registry, and routes a bounded subset naturally. It is appropriate for discovery and methodology evidence; a protected final claim still requires a later frozen-registry validation with generation off.

The current clean committed-tree experimental self-evolving broad500 reproduction is:

- Run: `outputs/self_evolving_sage/formal500_live_generation_v71_clean_repro/online_build_500_20260514_204356`.
- Canonical/reference: `0.656799 -> 0.854188`, delta `+0.197389`, lift `+30.05%`.
- Outcome/task completion: `0.494746 -> 0.880845`, delta `+0.386099`, lift `+78.04%`.
- Starting generated registry: absent/empty; generation on; `16` live-born helpers accepted; generated-tool visible/called/failed scenarios `453 / 297 / 0`.
- Controls: `500 cached / 0 fresh`; candidate/SAGE task cache off; OpenAI response cache disabled; routing evidence disabled; models all `gpt-4o-mini`.
- Clean-run caveat: runtime exceptions `0` and generated-tool failures `0`, but one helper-contract side-effect preservation failure was reported on a read-only reminder-search task. The actor did not execute the returned side-effect tool, so this is not an actual state mutation incident. It remains a strict preservation near miss and should be repaired before treating the result as protected final-claim evidence.

The prior high-lift v70 broad500 result remains useful because it had zero helper side-effect preservation reports, but it began before the relevant runtime edits were committed:

- Run: `outputs/self_evolving_sage/formal500_live_generation_v70_jit_birth_retry_repair/online_build_500_20260513_174839`.
- Canonical/reference: `0.656799 -> 0.827506`, delta `+0.170706`, lift `+25.99%`.
- Outcome/task completion: `0.494746 -> 0.872782`, delta `+0.378036`, lift `+76.41%`.
- Starting generated registry: absent/empty; generation on; `16` live-born helpers accepted; generated-tool visible/called/failed scenarios `453 / 295 / 0`.
- Controls: `500 cached / 0 fresh`; candidate/SAGE task cache off; OpenAI response cache disabled; routing evidence disabled; models all `gpt-4o-mini`.
- Safety: runtime exceptions `0`; helper side-effect incidents `0`; generated-tool failures `0`.

### Self-Evolving Loop Pseudocode

```text
for each scenario in sealed manifest order:
    prepare control
        if strict task-level baseline cache is eligible:
            reuse cached baseline score with cache provenance
        else:
            run fresh control

    prepare SAGE candidate from empty-or-current run registry
        assert generation == on
        assert candidate task cache == off
        assert OpenAI response cache == disabled
        assert routing evidence == disabled or explicitly pinned

        classify visible unlabeled task text for deterministic gaps
        if just-in-time proactive birth is enabled:
            generate candidate helper before actor routing
            validate schema, triggers, negative cases, runtime behavior,
            callability, and side-effect preservation
            if accepted:
                save helper to run-local registry
                allow fair-chance visibility on the same birth task

        route a bounded helper bundle from the registry
        actor decides naturally whether to call visible helpers
        original ToolSandbox side-effect tools still perform any state change

    after scoring:
        export helper visibility, calls, VNC, failures, contribution deltas
        update lifecycle evidence for keep/refine/park/scale decisions
        never use hidden labels, expected answers, or prior SAGE traces
```

The same-task birth rule is not a force-call mechanism. It only changes timing and fair-chance visibility: if SAGE can identify and validate the missing deterministic helper before the actor starts the task, that helper can be visible for the triggering task instead of only later tasks.

## Figure Assets Ready

| Figure | Asset |
|---|---|
| Full SAGE + ToolSandbox pipeline | `docs/sage_protocol/figures/sage_toolsandbox_system_overview.svg` |
| SAGE key components zoom-in | `docs/sage_protocol/figures/sage_internal_components_zoom.svg` |
| Tool generation, validation, and repair loop | `docs/sage_protocol/figures/sage_tool_generation_validation_repair_loop.svg` |
| Paper-ready matched-validation diagram | `docs/sage_protocol/figures/sage_peer_review_methodology_figure.svg` |

Remaining tables to draft for Chapter 3:

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
5. Runtime routing and bridge policy: bounded helper exposure, final-run evidence pinning/disablement, actor affordances, final-answer retention, and side-effect preservation.
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
