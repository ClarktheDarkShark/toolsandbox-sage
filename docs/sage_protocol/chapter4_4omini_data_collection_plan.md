# Chapter 4 Strict Fresh-Control Evidence Collection Plan

## Status and Superseded Campaign

This plan supersedes the control policy used by the July 2026 campaign
`chapter4_final_claim_10x_20260730`. The preserved July results remain available
for audit and sensitivity analysis, but they are not final hypothesis evidence.

The corrected-tree strict sample 03 has passed the engineering integrity and
outcome-only release gate. The final ten-online/ten-frozen manifest is prepared
and verified at
`artifacts/chapter4_evidence/chapter4_strict_fresh_control_10x_20260902/campaign_manifest.json`.
No campaign arm has been executed; explicit researcher approval remains the
only outstanding launch gate.

The historical cache contained 1,182 complete records for 1,032 unique tasks:
957 tasks had one record and 75 tasks had three records. Compatible records for
the 75 triplicated tasks were averaged. Those hybrid values supplied the
reported control rows and were also read by online self-evolution reflection.
The original one-record-per-task v140 snapshot has outcome mean
`0.4528026204750015`; substituting it in the historical H2 point-estimate
calculation increases the relative lift from about 73.9% to about 75.7%.
Therefore, the hybrid did not inflate the headline point estimate. However,
that sensitivity calculation does not repair provenance, unequal replication,
cache-conditioned online decisions, intervals, randomization tests, or H1/H3.
All three hypothesis decisions are pending the campaign defined here.

## Purpose

This campaign collects the evidence needed to test the three Chapter 4
hypotheses using the current SAGE implementation and `gpt-4o-mini`. The design
separates online self-evolution from frozen-registry reuse while preserving a
fresh matched non-learning baseline for every benchmark task.

The evidence configuration requires:

- `gpt-4o-mini` for the baseline actor, SAGE actor, user simulator, and
  tool-generation model;
- model-authored generated tools with complete/native-action delegation;
- an empty independent registry at the beginning of every online-build run;
- generated-tool birth, validation, storage, natural routing, calls, and reuse;
- bridge completions disabled;
- scenario-name birth and routing disabled;
- diagnostic force-call variables absent;
- no SAGE task cache;
- no persistent repository whole-response replay cache;
- no persistent generated-output replay cache; preserve the validated
  generator's nonpersistent within-run contract-and-repair-analysis memoization;
- separately record OpenAI-managed prompt-prefix cached input tokens for every
  model call and reconcile raw events exactly with task and arm totals;
- no control baseline cache construction or lookup;
- complete control-arm execution before the SAGE arm;
- exactly one same-run fresh control row per task for online reflection, with
  missing, duplicate, or mismatched rows treated as fatal protocol errors;
- no parallel execution of control and SAGE arms;
- the fixed 1,032-task ToolSandbox manifest and task order.

## Replication Design

The campaign contains ten independent online-build replications and ten paired
frozen-registry replications.

Each online-build replication starts with an empty registry and runs the full
ToolSandbox dataset. Each resulting registry is copied into its matched frozen
run. The frozen run uses the same model, manifest, task order, clock, and
strict fresh-control policy, but disables generation, candidate repair, and
online reflection.

This design produces:

- 10 independently generated registries;
- 10,320 matched benchmark task pairs with descriptive route-compatibility output;
- 8,000 matched task pairs with an explicit ToolSandbox outcome evaluator;
- 10 paired online/frozen registry comparisons for gain-retention analysis.

Ten independent replications are required for the run-level sensitivity
analysis. With only five consistently positive run-level differences, the
smallest possible two-sided exact sign-flip p-value is .0625. With ten
consistently positive replications, the corresponding minimum is .00195.

## Baseline Policy

Control result reuse is prohibited. Every online and frozen arm must execute a
new complete non-learning control before executing its SAGE condition. The
runner must not construct or read `ControlBaselineCache`, and the run manifest
must record `control_cache=off` and `fresh_control_required=true`.

For online runs, self-evolution reflection receives an immutable map built only
from the just-completed same-run control arm. The map must contain exactly one
row for each of the 1,032 task names. It must be fully consumed one-to-one by
the 1,032 online task reflections. Missing rows, duplicate rows, task-name
mismatches, extra rows, or partial consumption invalidate the run.

The original v140 records and expanded 1,182-record cache are historical audit
inputs only. They are prohibited as execution inputs for this campaign.

The read-only RapidAPI fixture is a frozen external-service benchmark input,
not a task-result, model-response, prompt, or control cache. The public,
sanitized runtime copy has required SHA-256
`eae0a6ab7d2ee5dd272612a0b5ce44d85af34cd1297ff662007260941192322f`;
the launcher must fail before task execution if the file is missing, writable
mode is requested, or its content hash differs.

## Preparation, Verification, and Approval Boundary

Preparation creates ten queued online/frozen pairs without launching API-backed
work:

```bash
PYTHONPATH=src:. python scripts/run_chapter4_evidence_campaign.py prepare \
  --campaign-id chapter4_strict_fresh_control_10x_20260902 \
  --expected-online-runs 10 \
  --sample-validation-report outputs/publication_validation/publication_validation_20260902_strict_sample03/native_action/online_build_full_20260902_071820/publication_validation_report.json \
  --max-parallel 10
```

The preparer rejects a dirty Git tree, a failing or modified sample report,
any benchmark or fixture hash mismatch, and any replication count other than
exactly ten online plus ten frozen runs.

Verify the resulting manifest before execution:

```bash
PYTHONPATH=src:. python scripts/run_chapter4_evidence_campaign.py verify \
  --campaign-manifest artifacts/chapter4_evidence/chapter4_strict_fresh_control_10x_20260902/campaign_manifest.json
```

Preparation and verification do not authorize the final experiment. The run
command must not be issued until the researcher reviews the code cleanup,
single-sample validation, input hashes, and prepared manifest and then gives
explicit approval. After approval, execution additionally requires the
launcher's `--approve-execution` acknowledgement. This document intentionally
does not present that command as a current action.

The scheduler enforces a hard maximum of ten concurrent full runs. Each frozen
run is eligible only after its paired online registry is complete and verified.
The campaign is restartable only at the completed-arm boundary: verified arms
may be skipped after an orchestration restart, but partial task rows may not be
resumed or reused. A failed or interrupted arm is preserved for review and
requires an explicit decision before any new arm is scheduled.

Every completed arm must pass `scripts/verify_publication_run.py` before the
campaign marks it complete. Verification requires 1,032 unique control rows and
1,032 unique candidate rows in the identical pinned task order, zero cached
control tasks, zero SAGE task-result reuse, zero persistent repository
whole-response replay, the pinned read-only fixture, and the declared reflection
policy. Provider-managed prompt-prefix computation is recorded separately and
does not replay a stored response.

## Dashboard

After an approved and complete rerun, the campaign evidence dashboard will be:

`outputs/chapter4_evidence/chapter4_strict_fresh_control_10x_20260902/dashboard/chapter4_evidence.html`

The dashboard refreshes from run artifacts while the campaign is active. It
shows:

- hypothesis thresholds, observed values, confidence intervals, and decisions;
- overall matched baseline and SAGE performance;
- task-paired and run-level statistical evidence;
- research-integrity safeguards and observed incidents;
- generated tools accepted and reused;
- natural generated-tool calls;
- called-task gains, preserved outcomes, and regressions;
- generated-tool failure scenarios;
- run-level outcome variation;
- top generated-tool contributions;
- links to every completed Task Compare dashboard.

Every main metric is selectable. Its drilldown provides the metric definition,
formula, sample size, uncertainty estimate, per-run evidence, or tool
provenance as applicable.

## Hypothesis Metrics

Hypothesis 1 uses frozen-registry gain retention:

`(frozen SAGE outcome - baseline outcome) / (online SAGE outcome - baseline outcome)`

The target is at least 80 percent.

Hypothesis 2 uses overall relative task-completion lift:

`(SAGE outcome - baseline outcome) / baseline outcome`

The target is at least 10 percent.

Hypothesis 3 uses the same relative outcome lift formula on the matched subset
where at least one generated tool was naturally called. The target is at least
30 percent.

Outcome/task completion is the sole paper performance endpoint and the sole
performance basis for release decisions. Canonical/reference similarity may be
retained as descriptive ToolSandbox audit output but is never a hypothesis or
release gate. Time, LLM-call count, and token count are not Chapter 4 hypothesis
metrics and are not displayed in the evidence dashboard.

## Statistical Analysis

The confirmatory export uses:

- paired task-level mean differences;
- 10,000 paired bootstrap samples for 95 percent confidence intervals;
- 20,000 paired sign-flip randomization samples when exact enumeration is not
  feasible;
- exact run-level sign-flip analysis for the ten independent registry
  replications;
- run-cluster bootstrap sensitivity;
- gain, regression, and preserved counts;
- a generated-tool-called matched subset;
- paired online/frozen bootstrap analysis for gain retention.

The dashboard does not rescore or modify run results. It derives all values from
preserved protocol manifests, paired comparisons, Task Compare data, registry
manifests, and contribution summaries.

## Single-Sample Validation Is Not Confirmatory Evidence

Sample 03 completed the required 1,032-task strict fresh-control engineering
validation: both arms finished all 1,032 tasks, the strict verifier passed, and
outcome increased from `0.5087366331780064` to `0.7986035515693737` across
800 outcome-scored matched tasks. The absolute increase was
`0.2898669183913673`, relative lift was `56.97779548144769%`, and exact
outcome successes increased from `220` to `443`. The paired outcome counts
were `413` gains, `283` preserved, and `104` regressions. Verification found
zero runtime exceptions, zero cached control tasks, zero repository
whole-response replay, and same-run-fresh reflection.

A single stochastic sample cannot estimate
run-level variation, support the planned run-level sign-flip test, replace ten
independently evolved registries, or accept/reject H1, H2, or H3. Its result
is reported separately from the Chapter 4 confirmatory analysis in
`publication_validation_sample03_report.md`.

## Publication Replacement Rule

The historical July tables remain labeled archival until all ten new online
runs and all ten paired frozen runs pass verification. Only then may the paper
renderer consume the new structured evidence file and replace the historical
point estimates, intervals, tests, lifecycle summaries, and hypothesis
decisions. Failed or incomplete arms are preserved and reported; they are not
silently retried or excluded.
