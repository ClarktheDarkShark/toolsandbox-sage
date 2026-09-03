# Claim-Grade Model-Codegen SAGE Checkpoint - 2026-06-25

This checkpoint preserves the current state after the v072 20-task diagnostic and sets up the next resume point. The next step is not a full run. The next step is four independent 20-task diagnostics launched in parallel, followed by broad framework fixes based on recurring failure classes.

## Current Methodology Boundary

The active implementation is intended to test SAGE as autonomous tool generation and reuse, not benchmark-specific orchestration.

Required boundaries for the next runs:

- Use `gpt-4o-mini` for actor, user, and generation.
- Keep `SAGE_PRAXIS_BRIDGE_POLICY=disabled`.
- Keep scenario-name birth and routing disabled.
- Keep deterministic tool code generation disabled.
- Keep synthetic generated-tool repair disabled.
- Keep same-turn/fair-chance extra turns disabled.
- Start each diagnostic with an empty registry.
- Use cached baseline controls for diagnostics.
- Do not prepopulate generated tools.
- Do not stop the 20-task diagnostics early unless the run is mechanically broken.

## Completed Diagnostic

Run:

`outputs/claim_grade_model_codegen/v072_20_visible_missing_tools/mechanism_40_20260625_094311`

Dashboard:

`http://127.0.0.1:62859/outputs/claim_grade_model_codegen/v072_20_visible_missing_tools/mechanism_40_20260625_094311/dashboard/task_compare.html`

Official paired-comparison metrics:

- Score: `0.730526 -> 0.792286`
- Score delta: `+0.061760`
- Score lift: `+8.45%`
- Outcome: `0.451162 -> 0.835641`
- Outcome delta: `+0.384479`
- Outcome lift: `+85.22%`
- Score gains/regressions: `12 / 5`
- Outcome gains/regressions: `13 / 1`
- Runtime exceptions: `0`
- Controls: `20 cached / 0 fresh`
- OpenAI response cache: disabled

Generated-tool attribution:

- Accepted tools: `12`
- Generated-tool-called scenarios: `14 / 20`
- Called-generated-tool score lift: `+17.63%`
- Called-generated-tool outcome lift: `+111.69%`
- No-visible-generated-tool score lift: `-8.80%`
- No-visible-generated-tool outcome lift: `+27.25%`

The paired comparison is the official run metric. The scenario selection log is useful for diagnosing tool visibility and calls, but it is not the final scoring source.

## Main Failure Classes To Fix

These are broad framework issues. Do not patch specific scenario names.

1. State-precondition tool generation did not converge.

`plan_device_state_action_sequence_v3` was attempted four times and accepted zero times. This affected service-disabled rows such as cellular or Wi-Fi preconditions. The fix should improve how SAGE decomposes state-repair tools into simpler model-authored tools, not reintroduce deterministic code bodies.

2. Relationship-batch tool generation did not converge.

`plan_contact_relationship_batch_update` was attempted twice and accepted zero times. The model failed on output-shape and syntax issues. The fix should improve the generated-tool contract, examples, and validation feedback for batch-selection tools generally.

3. Holiday argument-preparation did not converge.

`prepare_holiday_search_args` was attempted four times and accepted zero times. `days_between_timestamps` did work and produced correct outcomes, but canonical score dropped on some rows because expected intermediate milestone behavior was bypassed. This is mainly a generation/contract-shape problem.

4. Tool chaining is still unreliable.

`modify_reminder_with_recency_latest` exposed both a search-window tool and a timestamp selector, but the actor called only the search-window tool. The fix should improve generated-tool use sequencing and actor-facing tool guidance without granting extra turns.

5. Safe abstention needs a better actor-facing interface.

`prepare_safe_action_or_abstain` was accepted and called, but some insufficient-information rows still received low outcome values. The fix should improve how generated tools communicate visible missing capability or missing evidence to the actor. It must not use hidden labels.

## Prepared Four-Way 20-Task Diagnostic

Four deterministic, disjoint, whole-dataset 20-task manifests have been created from `docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`.

- `artifacts/claim_grade_model_codegen/parallel20_manifests_20260625/toolsandbox_parallel20_a.json`
- `artifacts/claim_grade_model_codegen/parallel20_manifests_20260625/toolsandbox_parallel20_b.json`
- `artifacts/claim_grade_model_codegen/parallel20_manifests_20260625/toolsandbox_parallel20_c.json`
- `artifacts/claim_grade_model_codegen/parallel20_manifests_20260625/toolsandbox_parallel20_d.json`

Manifest hashes:

- A: `c3075a00a556d0cbdf066c920c280c31aafac9ec0ec50b0572aa27ea60cbccfe`
- B: `c09a65e1d262b244d8140afbea9e491a693537a4cb276615411080acdcf7c07e`
- C: `74464e4fc7fcc26be834b436d4021a7b445272ed766ad2291696205fe4192638`
- D: `5cf04c11396902ac1d1b218d0b47454fcac007017b7969d5078ce68cfa9071b6`

Launch command:

```bash
bash scripts/run_claim_grade_parallel20_v073.sh
```

The script launches all four runs in parallel on dashboard ports `62860`, `62861`, `62862`, and `62863`. It writes logs under `artifacts/claim_grade_model_codegen/parallel20_v073_logs_<timestamp>/`.

After launch, find Task Compare dashboard paths with:

```bash
find outputs/claim_grade_model_codegen -path '*/dashboard/task_compare.html' | grep 'v073_parallel20'
```

## Resume Plan

1. Launch the four v073 20-task diagnostics in parallel.
2. Let all four complete.
3. Summarize official paired metrics, generated-tool-called buckets, accepted/rejected tool births, and low-outcome rows across all four runs.
4. Identify recurring failure classes that repeat across samples.
5. Apply broad framework fixes only.
6. Run the next four 20-task diagnostics in parallel.
7. When the recurring blockers are reduced, run a 60 or 250 validation.
8. Run the full dataset only after the smaller diagnostics show generated-tool-attributed success and no methodology violation.
