# Final Code, Pipeline, and Methodology Audit

Audit date: 2026-05-07

Audit commit: `d3374eff4a9d93a76f83339ff956bf749f983546`

Scope: repository, pipeline, registries, evidence artifacts, reports, dashboards, feedback packets, routing, generation, validation, scoring, caching, and methodology readiness.

Guardrail observed: no code, registry, locked evidence, or final-package artifact changes were made. This report is the only new audit artifact.

## 1. Executive Summary

SAGE is close to a defensible final reporting state for the protected frozen best3 claim and the V2.6 contact-scalar secondary evidence, but it is not yet ready for another final complete run or doctorate-level statistical conclusion package without a small set of pre-run and pre-analysis fixes.

The locked evidence is not undermined by the audit. The fixed best3 and V2.6 registries both pass registry validation, the current-code matched reports separate best3 broad evidence from V2.6 expanded evidence, and the final claim summary correctly avoids framing the V2.6 expanded portfolio as an unconditional broad replacement.

The highest-risk issue for future final runs is that runtime routing can consult the latest helper-contribution artifact by filesystem mtime rather than a run-pinned evidence source. That can make tool exposure depend on whatever summary happened to be written last. This is acceptable for iterative diagnostics only if documented; it is not acceptable for final complete runs unless pinned, disabled, or recorded as part of the run configuration.

The second major risk is statistical/methodological: existing reports provide means, deltas, exact counts, and helper contribution summaries, but there is no clearly locked statistical analysis script/report that computes paired uncertainty intervals, paired bootstrap/permutation tests, and cache-variance handling for dissertation-level conclusions. The final narrative should not move beyond descriptive evidence until that analysis is produced.

The third major risk is that gap-closure and generated-tool adoption diagnostics still rely on hard-coded scenario-name/task-family heuristics. These are reasonable as a research system implementation, but they must be disclosed as taxonomy heuristics and not overclaimed as purely autonomous semantic discovery.

## 2. Final-Run Readiness Verdict

Verdict: conditionally ready for final reporting synthesis, not ready for additional final complete runs until high-priority reproducibility checks are fixed or explicitly frozen.

| Area | Verdict | Severity | Decision | Evidence |
|---|---|---:|---|---|
| Protected best3 registry integrity | Ready | Low | No action needed | Registry check passed for 3 active best3 entries. |
| V2.6 expanded registry integrity | Ready | Low | No action needed | Registry check passed for 6 active expanded entries. |
| Current evidence framing | Mostly ready | Medium | Should fix before final runs | `final_claim_summary.md` and `v2_6_current_code_evidence_synthesis.md` correctly preserve best3 and frame V2.6 as non-harmful but variance-limited. |
| New final complete runs | Not ready | High | Must fix before final runs | Routing evidence source is mtime-global; diagnostic-force env vars are not preflight-blocked; statistical plan is not locked. |
| Doctorate-level statistical conclusions | Not ready | Critical | Must fix before final conclusions | Existing reports lack a locked paired uncertainty analysis and cache-variance treatment. |
| Future autonomous tool expansion | Not ready for strong autonomy claims | High | Document only / Should fix before future campaigns | Generation, clustering, and helper-fit classification depend on hard-coded scenario-family logic and prompt fragments. |

## 3. Major Blockers Table

| Blocker | Severity | Decision | Why It Matters | Evidence / Files | Recommended Resolution |
|---|---:|---|---|---|---|
| Routing evidence is selected by latest artifact mtime, not by current run/registry/manifest. | High | Must fix before final runs | Final tool exposure can depend on unrelated prior diagnostics. This threatens reproducibility and can change visible/called/VNC behavior without code or registry changes. | `src/sage_ts/runtime/routing_scorer.py:16-18`, `src/sage_ts/runtime/routing_scorer.py:117-133`, `src/sage_ts/runtime/routing_scorer.py:196-242` | Add a CLI/config path for routing evidence, record it in `protocol_manifest.json`, and default final frozen runs to pinned evidence or no historical suppression. |
| Diagnostic force-call environment variables are not preflight-blocked. | High | Must fix before final runs | `SAGE_DIAGNOSTIC_FORCE_TOOL_NAME` and related vars can force helper calls. Useful for diagnostics, unsafe for claim runs if accidentally inherited. | `src/sage_ts/adapters/openai_toolsandbox_roles.py:568-596`, `src/sage_ts/runtime/toolsandbox_integration.py:1331-1344` | Add final-run preflight that fails if any `SAGE_DIAGNOSTIC_FORCE_TOOL_*` env var is set unless an explicit diagnostic mode is used. |
| Dissertation-grade statistical analysis is not locked. | Critical | Must fix before final conclusions | Means and deltas are not enough for doctorate-level claims. Need paired uncertainty, CI, hypothesis testing, and cached-control variance treatment. | `src/sage_ts/evaluation/run_metrics.py:195-334`; current reports list deltas but no locked bootstrap/permutation artifact. | Create and freeze a statistical analysis script/report that consumes `paired_comparison.json`, cache variance, and helper subsets. Include paired bootstrap CIs and sensitivity checks. |
| Cached synthetic control runs omit historical trajectories for cached-only tasks. | High | Should fix before final runs if trace-level feedback is used | Scoring is preserved, but dashboards/feedback packets may lack control trace summaries for cached tasks. This limits feedback diagnosis and Chapter 3 trace auditability. | `src/sage_ts/evaluation/control_baseline_cache.py:593-674`; feedback reads trajectories in `src/sage_ts/evaluation/feedback_packets.py:87-128` | Either archive/cache control trajectories with baseline records or state that cached-control feedback packets are score-complete but trace-incomplete. |
| Helper-fit and gap-closure metrics depend on hard-coded scenario taxonomy. | High | Should fix before final runs / Document only for existing claims | No-current-helper-fit reduction is central to V2.6 claims. The metric is useful but implementation-derived, not an independent benchmark label. | `src/sage_ts/evaluation/task_strata.py:10-111`, `src/sage_ts/evaluation/task_strata.py:308-483`, `src/sage_ts/evaluation/feedback_packets.py:403-409` | Document taxonomy as a protocol-defined heuristic. For future runs, move helper-fit rules to versioned config and hash it in reports. |
| Protocol gate still encodes older absolute thresholds not aligned with final relative-lift framing. | Medium | Should fix before final runs | Best3 500/1032 exceed relative target but fail older absolute +0.08 protocol gate in final summary. This is already disclosed but confusing. | `scripts/run_sage_protocol.py:335-398`; `final_claim_summary.md` notes 500/1032 protocol gate false. | Rename or version gates: `protocol_viability_gate_v1` versus final claim criteria. Record which gate applies per run. |
| Promotion/registry lifecycle is partly convention-driven. | Medium | Should fix before future autonomous campaigns | Candidate/active/frozen separation is documented, but run script does not make promotion decisions; manual scripts/reports drive portfolio movement. | `src/sage_ts/registry/promotion_gate.py:64-132`, `scripts/run_sage_protocol.py:1428-1434` | Add an explicit lifecycle command: validate candidate -> freeze candidate -> promote/deny with immutable report. |
| Broad autonomous generation is not yet fully general; it is guided by hard-coded prompt fragments and scenario prefixes. | High | Document only for final claim; should fix before future autonomy claims | Final best3 claim uses frozen tools, but any claim about autonomous tool birth must disclose the engineered discovery scaffolding. | `src/sage_ts/generation/tool_generator.py:45-289`, `src/sage_ts/adequacy/inadequacy_classifier.py`, `src/sage_ts/orchestration/online_birth.py` | In Chapter 3, describe SAGE as a feedback-guided generated-tool system with heuristic clustering, not a fully unguided tool inventor. |
| V2.6 expanded portfolio is positive but variance-limited. | Medium | Document only | Current-code 500 outcome is positive, but helper-fit reduction is 7.10%, below the 10% broad target; original250 exact success falls by 8. | `docs/sage_protocol/v2_6_current_code_evidence_synthesis.md`, `docs/sage_protocol/v2_6_current_code_500_matched_report.md` | Preserve final framing: best3 broad claim; V2.6 targeted gap evidence and non-harmful current-code evidence. |

## 4. Hard-Coded / Brittle Content Table

| Content | Severity | Decision | Location | Acceptable? | Notes |
|---|---:|---|---|---|---|
| Best3 and candidate registry paths in reports/build scripts | Low | Document only | `scripts/build_v2_5_tool_foundry_artifacts.py:34`, many report files | Yes for evidence locking | Hard-coded paths are acceptable in evidence-lock reports and artifact-build scripts when treated as immutable evidence references. |
| Helper-name routing triggers | High | Should fix before future runs | `src/sage_ts/evaluation/task_strata.py:24-78`, `src/sage_ts/runtime/toolsandbox_integration.py:1040-1197` | Partly | Valid for protected best3 and V2.6 fixed tools; brittle for generated tools. Move to registry metadata. |
| Scenario-name family/prefix classification | High | Should fix before future gap-closure claims | `src/sage_ts/evaluation/task_strata.py:141-177`, `src/sage_ts/adequacy/inadequacy_classifier.py` | Partly | Useful for ToolSandbox experiments; should be versioned and documented as taxonomy heuristics. |
| Fixed runtime bundle size `5` | Medium | Should fix before final runs if changing portfolio | `src/sage_ts/runtime/routing_scorer.py:16`, `scripts/run_sage_protocol.py` | Partly | Bounded exposure is good, but value should be config/manifest-backed and reported. |
| VNC/adoption thresholds | Medium | Should fix before future campaigns | `src/sage_ts/runtime/routing_scorer.py:16-18`, `src/sage_ts/registry/promotion_gate.py:13-15` | Partly | Current thresholds are reasonable but uncalibrated; expose in config/report hash. |
| Cohort quality thresholds | Medium | Document only / should version | `src/sage_ts/evaluation/task_strata.py:486-725` | Yes if documented | These are research design choices. They should appear in Chapter 3 and be hashed with manifests. |
| Protocol gate thresholds `0.08`, `1.4`, `25% called share` | Medium | Should fix before final runs | `scripts/run_sage_protocol.py:384-391` | Partly | Good for early protocol gates, but final claim uses relative lift and safety; version the gate. |
| Default model `gpt-4o-mini` and legacy `gpt-5-mini` metadata | Medium | Document only | `src/sage_ts/config/models.py:7-31` | Yes if recorded | Model choice is central methodology. Record exact requested/resolved model and date. |
| Tool-generation prompt embeds prior repair lessons and exact designs | High | Document only for current evidence; should simplify before future claims | `src/sage_ts/generation/tool_generator.py:45-289` | Partly | This is not hidden benchmark hardcoding, but it is engineered prompt scaffolding. Chapter 3 should describe prompt evolution and guardrails. |
| Diagnostic force-call environment variables | High | Must fix before final runs | `src/sage_ts/adapters/openai_toolsandbox_roles.py:568-596`, `src/sage_ts/runtime/toolsandbox_integration.py:1331-1344` | Yes only for diagnostics | Add final-run fail-fast preflight. |
| Latest helper-contribution evidence root | High | Must fix before final runs | `src/sage_ts/runtime/routing_scorer.py:16-18`, `src/sage_ts/runtime/routing_scorer.py:117-133` | No for final runs | Must be pinned or disabled. |
| ToolSandbox local offset `-4` in relative timestamp evidence | Medium | Document only / config later | `src/sage_ts/adequacy/inadequacy_classifier.py` | Partly | Fine for benchmark-specific evidence if reported; brittle for generalization. |
| Dashboard server port defaults | Low | Safe to defer | `scripts/run_sage_protocol.py:768`, `src/sage_ts/dashboard/exporters.py` | Yes | Prior 404/load issues were mostly operational; current Task Focus progress is improved. |

## 5. Architecture Limitations Table

| Limitation | Severity | Decision | Affected Area | Evidence | Impact |
|---|---:|---|---|---|---|
| Generated-tool adoption is influenced by actor-policy prompt snippets rather than only tool metadata. | High | Should fix before future campaigns | Tool calling/adoption | `src/sage_ts/adapters/openai_toolsandbox_roles.py:500-534` | Valid tools may remain uncalled if the actor policy does not make them salient at the correct turn. |
| Tool callability is only partly trace-bridged. | High | Should fix before future campaigns | Runtime bridge / callability | `src/sage_ts/evaluation/feedback_packets.py:153-186`, prior reports on missing inputs | Uncalled or failed tools cannot be classified cleanly without better argument-availability instrumentation. |
| Feedback packet sufficiency is heuristic. | Medium | Should fix before future campaigns | Feedback generation | `src/sage_ts/evaluation/feedback_packets.py:306-343` | Packets identify many missing fields, but expected outputs and side-effect guardrails can be missing in cached or negative cases. |
| Output normalization patches safety contracts after tool execution. | Medium | Document only | Validation/runtime safety | `src/sage_ts/validation/output_normalization.py:1-6`, `src/sage_ts/validation/output_normalization.py:160-236` | Good safety design, but methodology should state normalized helper outputs are part of SAGE, not raw generated code only. |
| Candidate live validation is lightweight. | Medium | Document only / enhance later | Candidate validation | `src/sage_ts/validation/live_candidate_check.py:92-159` | It catches runtime/negative/route-accounting issues but cannot prove final task value. |
| Candidate gate is strong but threshold-heavy. | Medium | Document only | Promotion/gating | `src/sage_ts/adequacy/candidate_gate.py`, `src/sage_ts/registry/promotion_gate.py` | Good for safety; may reject unconventional but useful tools unless grading accounting and final-state preservation are explicit. |
| Control response cache and baseline cache are separate systems. | Medium | Should fix before final runs | Reproducibility/cache accounting | `src/sage_ts/cache/openai_response_cache.py`, `src/sage_ts/evaluation/control_baseline_cache.py` | Need clear Chapter 3 distinction: response cache reuses exact model calls; baseline cache reuses completed control task scores. |
| Synthetic cached controls can be score-complete but trace-incomplete. | High | Should fix or document before final runs | Dashboards/feedback | `src/sage_ts/evaluation/control_baseline_cache.py:593-674` | Trace-based qualitative analyses may under-report control behavior on cached tasks. |
| No-current-helper-fit can mean multiple things. | High | Should fix before future gap closure | Gap metric | `src/sage_ts/evaluation/feedback_packets.py:403-409` | It can indicate no expected helper, hidden helper, or helper visible-not-called depending on loaded helpers and taxonomy. |
| Large artifact surface is difficult to audit manually. | Medium | Should fix before final package | Artifact management | 82 candidate registries; `outputs` is 28GB | Need final evidence index with hashes and a minimal reproducibility bundle. |

## 6. Generated-Tool Adoption and Value Diagnosis

Important rule: generated-but-uncalled is not evidence of no value. It is a diagnosis requiring routing, affordance, schema, timing, actor-policy, granularity, safety, and force-call evidence.

| Tool / Lane | Status | Likely Blocker Classification | Evidence | Current Decision |
|---|---|---|---|---|
| `relative_day_time_to_timestamp` | Protected best3 | Proven useful | Broad 100/250/500/1032 positive contribution; registry locked. | Keep protected. |
| `resolve_search_window_or_bounds` | Protected best3 | Proven useful; some VNC expected due broad opportunities | Broad positive contribution; bounded routing still needed. | Keep protected. |
| `select_record_by_timestamp_extreme` | Protected best3 | Proven useful | Strong called-subset contribution; registry locked. | Keep protected. |
| `plan_contact_search_from_scalar_constraint` | Strongest V2.6 additive candidate | Previously adoption/VNC; now naturally called at 500 | Current-code 500 visible/called/VNC `40 / 14 / 26`; direct expanded-vs-best3 called-subset outcome `+0.2649`. | Retain as V2.6 candidate evidence, not broad replacement. |
| `plan_contact_lookup_query` | Mixed V2.6 candidate | Value/interference versus best3 despite positive vs control | Current-code 500 called-subset positive vs control, but direct expanded-vs-best3 called subset `-0.2308`. | Keep in V2.6 evidence; do not overclaim broad additive value. |
| `extract_contact_field_from_search_result` | Mixed V2.6 candidate | Value/interference and two-step chain fragility | Current-code 500 direct expanded-vs-best3 called subset `-0.3333`; VNC high. | Keep as targeted evidence, cautious framing. |
| `days_between_timestamps` | Confirmed standalone, non-additive to best3 | Sparsity/overlap/interference at broad scale | Masked/narrow evidence positive; Best4 frozen100 underperformed best3. | Document only; do not promote. |
| `format_calculated_distance_km` | Micro-positive, failed frozen100 guardrail | Narrowness and insufficient-information/minefield risk | Insufficient-information distance case should abstain; computing numeric distance can trigger forbidden action. | Do not promote without safe-abstention redesign. |
| Dependency/precondition helpers | Parked | Concept/timing/safety after precondition errors; force-call negative or side-effect risky | Prior force diagnostics non-positive and/or side-effect risky. | Park unless materially redesigned. |
| Visible-record selector lane | Valid but naturally uncalled / force-positive in some cases | Actor-policy/adoption and salience, not necessarily value absence | Selector force diagnostics had positive called-subset in some runs but natural calls stayed weak. | Future actor-policy redesign needed before retest. |
| Selected-record side-effect prep / direct-action helpers | Parked | Side-effect risk, missing updates, brittle action kwargs | Dict payload supplied `{}`; flat-scalar version force-callable but outcome-negative; side-effect incident occurred in one design. | Park current designs; split into validators/extractors before any side-effect-prep retry. |
| Recency/action selector | Parked | Value failure or overlap with best3 | Callable after default repair, but not additive in confirmation. | Park. |
| Stock-symbol / external answer extraction / temperature / location-field extractors | Parked | Intermediate-only output, canonical-only, or outcome-negative value | Several called or force-called designs improved canonical but not outcome or regressed outcome. | Do not promote without task-completing output redesign. |
| Broad medium-grain constraint/action planner | Parked | Over-broad granularity and side-effect incidents | Force-call harmful with side-effect incidents. | Avoid broad side-effect planners. |

Diagnosis summary:

- The highest-value unresolved adoption blocker is not validation; it is actor-policy and routing salience for selectors and post-search helpers.
- The highest-value unresolved coverage blocker is not contact-scalar; it is the large remaining safe insufficient-information, reminder/action, service/precondition, external-service, and unclassified no-fit pool.
- The strongest V2.6 evidence is targeted gap closure and non-harmful current-code broad movement, not broad 10% helper-fit closure at 500.

## 7. Pipeline Reproducibility Risks

| Risk | Severity | Decision | Evidence | Mitigation |
|---|---:|---|---|---|
| Mtime-selected routing evidence | High | Must fix before final runs | `_latest_helper_contribution_summary()` picks newest summary under `artifacts/summaries`. | Pin routing evidence path or disable historical suppression for final runs. |
| Unblocked diagnostic force env vars | High | Must fix before final runs | Force-call vars are read at runtime without run-script preflight. | Fail final runs if `SAGE_DIAGNOSTIC_FORCE_TOOL_*` is set. |
| Cached-control trace gaps | High | Should fix before final runs | Synthetic controls copy fresh trajectories only. | Cache/copy historical trajectories or exclude cached-control traces from qualitative claims. |
| Different control cache composition across matched arms | Medium | Document only | Original250 best3 mixed `209/41`, expanded cached `250/0`; 500 best3 mixed `435/65`, expanded mixed `467/33`. | Reports already disclose. Statistical analysis should account for control baseline variance. |
| Response cache key includes registry/tool/order context, but cache artifacts can be large and split by arm. | Medium | Document only | `src/sage_ts/cache/openai_response_cache.py:172-187`, `scripts/run_sage_protocol.py:669-741` | Preserve cache manifests and stats; do not rely on cache for final statistical independence claims. |
| Protocol manifests do not record all environment variables that can affect behavior. | Medium | Should fix before final runs | Feature flags and diagnostic force envs are environment-backed. | Record relevant `SAGE_*` env vars in protocol manifest. |
| Dashboard URLs depend on local HTTP server state. | Low | Safe to defer | Prior dashboard load/404 issues; current paths are recorded. | Hash dashboard files and use static paths as primary evidence; URLs are convenience only. |
| Artifact bloat makes accidental stale-artifact use likely. | Medium | Should fix before final package | `outputs` is about 28GB; 82 candidate registry manifests exist. | Create a final minimal evidence manifest with exact files/hashes. |

## 8. Evidence and Reporting Gaps

| Gap | Severity | Decision | Current State | Required Action |
|---|---:|---|---|---|
| Paired uncertainty intervals for final claims | Critical | Must fix before final conclusions | Final reports show means/deltas but not locked CIs/p-values. | Add paired bootstrap/permutation analysis for outcome, canonical, exact success, helper-fit, and helper subsets. |
| Cache-variance accounting in final statistics | High | Must fix before final conclusions | Control cache stores per-task compatible baseline variance, but final reports do not integrate it into uncertainty. | Use cached-task variance in sensitivity analysis or document conservative treatment. |
| Static vs dynamic no-current-helper-fit definitions | High | Should fix before final runs | Reports use both static expected fit and feedback-derived dynamic fit. | Define both terms formally and use consistent labels in final claims. |
| Route-mismatch accounting scope | Medium | Should fix before final report | Route mismatch is reported in summaries; helper-level route mismatch exists in contribution summaries. | Add final table separating outcome-positive/canonical-negative cases from true failures. |
| Side-effect safety proof | Medium | Should fix before final report | Reports list incidents = 0; details are in JSONL. | Add final safety appendix listing side-effect report artifact hashes and incident counts by run. |
| Current-code matched gap250 rerun deferred | Low | Document only | Locked matched-gap evidence already exists. | Current synthesis already documents rationale; keep as limitation. |
| Expanded 1032 deferred | Low | Document only | 500 non-external provides broad evidence; 1032 includes sparse/external lanes. | Keep defer rationale in final limitations. |
| Chapter 3 diagrams/tables | Medium | Should fix before dissertation drafting | Existing images/diagrams exist but methodology map not complete. | Add pipeline diagram, lifecycle table, cache-policy table, and claim/evidence separation table. |

## 9. Cleanup and Simplification Recommendations

| Recommendation | Severity | Decision | Rationale |
|---|---:|---|---|
| Add final-run preflight script. | High | Must fix before final runs | One command should verify registry SHAs, clean/known git state, no diagnostic env vars, pinned routing evidence, cache mode, dashboard output paths, tests, and `git diff --check`. |
| Move routing evidence source to explicit CLI/config. | High | Must fix before final runs | Eliminates mtime-global artifact dependency. |
| Version helper-fit taxonomy as a JSON/YAML config. | High | Should fix before future gap-closure claims | Makes no-fit and birth-opportunity metrics auditable and hashable. |
| Split final claim criteria from early protocol gate. | Medium | Should fix before final runs | Avoids confusion between +10% relative lift claims and older +0.08 protocol gate. |
| Add statistical analysis script and frozen output report. | Critical | Must fix before final conclusions | Needed for doctoral conclusions. |
| Preserve cached-control trajectories or mark them trace-incomplete. | High | Should fix before final runs | Protects feedback-packet and dashboard interpretability. |
| Consolidate final evidence index into a machine-readable manifest. | Medium | Should fix before final package | Current markdown index is useful; a JSON manifest with hashes is easier to verify. |
| Archive or index stale candidate registries. | Low | Safe to defer | Do not delete artifacts now; mark which registries are active, protected, candidate, parked, or obsolete. |
| Document generated-tool prompt evolution. | Medium | Should fix before Chapter 3 | Prevents overclaiming autonomous generality. |
| Add adoption-failure taxonomy to contribution reports. | Medium | Safe to defer for final best3, useful for future V2.7 | Classify visible-not-called as routing, affordance, schema, or value unknown where evidence exists. |

## 10. Chapter 3 Methodology Preparation Map

| Methodology Section | Implementation / Artifact Anchors | What To Describe | Missing Item |
|---|---|---|---|
| Task cohort construction | `docs/sage_protocol/manifests/`, `src/sage_ts/evaluation/task_strata.py`, `cohort_preflight_report.json` | Manifest construction, strata, family diversity, near-duplicate controls, external contamination rules. | Versioned taxonomy table with thresholds. |
| Baseline/control arm | `scripts/run_sage_protocol.py`, `src/sage_ts/adapters/toolsandbox_adapter.py`, `src/sage_ts/evaluation/control_baseline_cache.py` | ToolSandbox control arm, task-by-task baseline cache, eligibility criteria, fresh/cached/mixed controls. | Cache-variance statistical treatment. |
| SAGE arm | `src/sage_ts/adapters/sage_run_adapter.py`, `src/sage_ts/runtime/toolsandbox_integration.py`, registries | Registry-loaded deterministic helpers, bounded exposure, generation on/off modes. | Explicit final-run env/config preflight. |
| Generated-tool lifecycle | `src/sage_ts/orchestration/online_birth.py`, `src/sage_ts/generation/tool_generator.py`, `src/sage_ts/generation/tool_spec.py` | Shortfall observation, recurring cluster birth, spec generation, repair, diagnostic-only status. | Clear statement that current generator uses heuristic feedback and engineered prompt scaffolding. |
| Candidate validation gates | `src/sage_ts/adequacy/candidate_gate.py`, `src/sage_ts/validation/sandbox_validator.py`, `src/sage_ts/validation/live_candidate_check.py`, `src/sage_ts/registry/promotion_gate.py` | Static contract, AST/schema safety, deterministic replay, held-out examples, negative examples, runtime smoke. | Lifecycle diagram from candidate to frozen registry. |
| Routing and bounded exposure | `src/sage_ts/runtime/routing_scorer.py`, `src/sage_ts/runtime/toolsandbox_integration.py`, `src/sage_ts/adapters/openai_toolsandbox_roles.py` | Positive/negative triggers, context budget, VNC risk, failure memory risk, actor-policy hints. | Pin/remove mtime-global evidence before final runs; document thresholds. |
| Feedback packets | `src/sage_ts/evaluation/feedback_packets.py`, `scripts/export_v2_6_feedback_packets.py` | Per-task feedback schema, trace summary, helper calls, missing deterministic step, sufficiency audit. | Cached-control trace completeness note. |
| Contribution analysis | `src/sage_ts/evaluation/helper_contribution.py`, `src/sage_ts/evaluation/run_metrics.py` | Visible/called/VNC, called-subset deltas, hidden subsets, accepted-but-uncalled tracking. | Add adoption-failure taxonomy and paired uncertainty. |
| Safety checks | `side_effect_preservation_report.jsonl`, `src/sage_ts/validation/output_normalization.py`, reports | Runtime exceptions, helper side-effect incidents, abstention/ambiguity normalization. | Final safety appendix with hashes. |
| Cache policy | `src/sage_ts/cache/openai_response_cache.py`, `src/sage_ts/evaluation/control_baseline_cache.py` | Exact response cache vs task-level baseline cache; compatibility keys; task-by-task reuse. | Formal statistical treatment of cached-control variance. |
| Cohort quality gates | `src/sage_ts/evaluation/task_strata.py:486-725` | Required families, family-share caps, variant caps, helper-fit warnings. | Methodology table of thresholds. |
| Statistical comparison plan | Currently mostly reports and `run_metrics.py` | Outcome primary, canonical secondary, exact success, helper-fit reduction, paired matched arms. | Dedicated statistical analysis script/report with CI/p-values. |
| Limitations and non-claims | `docs/sage_protocol/final_limitations_and_future_work.md`, `docs/sage_protocol/final_claim_summary.md` | Best3 broad claim, V2.6 targeted gap evidence, variance limits, route-mismatch/canonical caveats. | Add “not fully autonomous” and taxonomy-heuristic caveat if making tool-birth claims. |

Recommended Chapter 3 diagrams/tables:

1. Full SAGE pipeline diagram: manifest -> control cache -> control arm -> SAGE arm -> registry routing -> scoring -> contribution export -> feedback packets.
2. Generated-tool lifecycle diagram: observation -> cluster -> spec -> gate -> validation -> diagnostic/candidate/frozen -> routing -> contribution.
3. Evidence separation table: best3 broad claim, V2.6 matched gap claim, current-code matched original250, current-code 500, deferred 1032.
4. Cache-policy table: OpenAI response cache versus task baseline cache.
5. Metric definitions table: outcome/task completion, canonical/reference, exact success, route mismatch, no-current-helper-fit, visible/called/VNC.
6. Safety table: runtime exceptions, helper side-effect incidents, minefield/guardrail interpretation.

## 11. Recommended Next Action Sequence

1. Add a final-run preflight command that fails on dirty/unknown git state, registry SHA mismatch, unpinned routing evidence, diagnostic force env vars, generation accidentally on, low-quality cohort override, or missing dashboard/report paths.
2. Pin routing evidence for final runs or disable historical contribution suppression in frozen claim runs; record the choice in `protocol_manifest.json`.
3. Produce a frozen statistical analysis artifact for best3 and V2.6: paired bootstrap/permutation intervals for outcome, canonical, exact success, helper-fit share, and uncovered-gap subset, with cached-control variance sensitivity.
4. Write a short metric-definition appendix distinguishing static expected helper fit, dynamic feedback no-current-helper-fit, visible-not-called adoption gaps, and true no-helper coverage gaps.
5. Verify cached-control trace completeness. Either store cached trajectories with baseline records or explicitly label feedback packets from cached controls as trace-incomplete but score-complete.
6. Re-run only small final checks: registry check, targeted tests, `git diff --check`, evidence hash verification, dashboard file existence check, and final package path check.
7. Do not run additional 500/1032 or tool-generation campaigns until the preflight/statistical package is locked.
8. Start Chapter 3 drafting from the methodology map above, using best3 as the broad validated portfolio and V2.6 as targeted gap-closure/current-code-positive secondary evidence.
9. If future gap closure continues, prioritize non-contact no-fit lanes: safe insufficient-information detection, reminder/action workflows, and unclassified no-fit mechanisms. Treat uncalled tools as unresolved adoption/callability diagnoses, not value failures.
10. Preserve the final narrative: outcome/task completion is primary; canonical/reference is secondary; best3 broad claim is protected; V2.6 is non-harmful but variance-limited and strongest on matched gap-enriched contact-scalar cohorts.

## Audit Commands Run

```bash
git status --short
git rev-parse HEAD
PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_frozen_best3_claim/registry_manifest.json artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json
```

Registry check result: PASS, 9 active entries pass, 0 active entries fail.

No large benchmarks were run. No tests were run during this audit beyond the read-only registry check; existing current-code preflight reports record `125 passed, 2 warnings` before the matched evidence campaign.

## Final Audit Decision Label

`Should fix before final runs`
