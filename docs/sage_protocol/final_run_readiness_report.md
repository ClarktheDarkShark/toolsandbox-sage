# Final-Run Readiness Report

Decision label: `ARCHIVAL_READINESS_RECORD; superseded by strict fresh-control publication protocol`

> Historical note (updated 2026-09-01): this report records the earlier
> hardening stage. Current publication runs use `--control-cache off`, reject
> partial resumes, and no longer accept routing-evidence CLI options. See the
> publication cleanup and Chapter 4 rerun-readiness documents for the current
> protocol.

## Executive Summary

The pre-final hardening pass converted the final audit findings into executable guardrails and dissertation-facing artifacts. Large final benchmarks were not run.

Readiness status:

- Final frozen runs now have an explicit preflight script: `scripts/preflight_final_run.py`.
- `scripts/run_sage_protocol.py` now blocks diagnostic force-call leakage in frozen modes and records run-affecting `SAGE_*` environment variables in `protocol_manifest.json`.
- Runtime routing no longer has to depend on mtime-selected helper-contribution evidence for final runs. Routing evidence can be explicitly `disabled` or `pinned`, and frozen modes resolve the runner default to `disabled`.
- Cached-control feedback is now labeled as `score_complete_trace_incomplete` when aggregate scores exist but synthetic cached rows lack historical trajectories.
- A statistical analysis script/report now produces paired bootstrap intervals and paired randomization tests from existing artifacts.
- Methodology-critical heuristics are versioned in `docs/sage_protocol/protocol_heuristics_v1.json`.

## Files Changed

- `scripts/run_sage_protocol.py`
- `scripts/preflight_final_run.py`
- `scripts/write_final_statistical_analysis.py`
- `src/sage_ts/runtime/routing_scorer.py`
- `src/sage_ts/evaluation/feedback_packets.py`
- `tests/unit/test_runtime_routing_scorer.py`
- `tests/unit/test_v2_6_feedback_packets.py`
- `tests/unit/test_final_run_preflight.py`
- `docs/sage_protocol/final_run_preflight_config.json`
- `docs/sage_protocol/protocol_heuristics_v1.json`
- `docs/sage_protocol/final_statistical_analysis_report.md`
- `docs/sage_protocol/chapter3_sage_methodology_system_architecture_v061.md`
- `docs/sage_protocol/v2_6_feedback_packet_schema.md`
- `docs/sage_protocol/current_state.md`
- `docs/sage_protocol/run_ledger.md`
- `docs/sage_protocol/final_evidence_index.md`
- `docs/sage_protocol/final_limitations_and_future_work.md`
- `README.md`

## Final-Run Preflight

Preflight command pattern:

```bash
PYTHONPATH=src:. python scripts/preflight_final_run.py \
  --manifest <manifest.json> \
  --mode validate_250 \
  --registry-dir artifacts/registry_frozen_best3_claim \
  --output-root outputs/<future_run_root> \
  --generation off \
  --control-cache off
```

The preflight fails fast on:

- dirty or unknown git state unless `--allow-dirty` is explicitly used for development checks
- protected registry SHA mismatch
- unlisted or ambiguous registry selection
- frozen final mode with generation enabled
- diagnostic force-call environment variables unless `--diagnostic-mode` is selected
- low-quality cohort override
- missing required manifest fields or missing split
- missing output-root parent path
- missing versioned methodology heuristic file

Development validation command used while report changes were in progress:

```bash
PYTHONPATH=src:. python scripts/preflight_final_run.py \
  --manifest artifacts/summaries/v2_formal250_clean_20260504_034104/cohort_manifest.json \
  --mode validate_250 \
  --registry-dir artifacts/registry_frozen_best3_claim \
  --output-root outputs/final_preflight_probe \
  --generation off \
  --control-cache off \
  --allow-dirty \
  --report /tmp/sage_final_preflight_dev.json
```

Result: PASS. The only reason `--allow-dirty` was needed was that this readiness package was not yet committed.

## Routing Evidence Policy

The former auto/latest and pinned routing-evidence CLI path described by this
historical report was removed during publication cleanup. Current execution
does not consult mtime-selected helper-contribution artifacts.

## Diagnostic Force-Call Guardrail

Frozen final modes now fail if any of these are set without explicit diagnostic allowance:

- `SAGE_DIAGNOSTIC_FORCE_TOOL_NAME`
- `SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_ERROR`
- `SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_BASE_TOOL`

Diagnostic force-call remains available for tool-callability experiments, but it cannot silently leak into claim runs.

## Cache And Feedback Trace Completeness

Task-level control cache reuse remains score-complete for paired metrics. However, synthetic cached-control rows may lack historical trajectories. Feedback packets now include:

- `control_trace_completeness.status = trace_complete`
- `control_trace_completeness.status = score_complete_trace_incomplete`
- `control_trace_completeness.status = trace_unknown_or_missing`

Trace-audited feedback exports were written under `artifacts/summaries/v2_6_feedback_packets_trace_audit/` for current-code original250, current-code 500, and formal250 best3 evidence.

Trace-incomplete control packet counts:

| Run | Packets | Score-Complete Trace-Incomplete Controls | Share |
|---|---:|---:|---:|
| current-code original250 best3 | 250 | 209 | 83.6% |
| current-code original250 expanded | 250 | 250 | 100.0% |
| current-code 500 best3 | 500 | 435 | 87.0% |
| current-code 500 expanded | 500 | 467 | 93.4% |
| formal250 best3 | 250 | 0 | 0.0% |

Interpretation: cached-control score arithmetic is usable; trace-level feedback from cached controls must be treated as incomplete unless a trajectory exists.

## Statistical Readiness

Generated artifacts:

- Report: `docs/sage_protocol/final_statistical_analysis_report.md`
- JSON: `artifacts/summaries/final_statistical_analysis/analysis.json`

The script computes:

- paired outcome/task-completion deltas
- paired canonical/reference deltas
- paired exact-success deltas
- paired bootstrap confidence intervals
- paired randomization/permutation tests
- helper visible/called/VNC summaries where available
- no-current-helper-fit comparison for current-code V2.6 vs best3
- cache-source summaries with conservative caveat

Current caveat: the bootstrap intervals condition on stored baseline artifacts. Cached-control stochastic variance is summarized but not folded into the primary interval.

## Validation Commands

Run before commit:

```bash
PYTHONPATH=src:. pytest tests/unit/test_runtime_routing_scorer.py tests/unit/test_v2_6_feedback_packets.py tests/unit/test_final_run_preflight.py -q
PYTHONPATH=src:. python scripts/write_final_statistical_analysis.py
PYTHONPATH=src:. python scripts/preflight_final_run.py ... --allow-dirty --report /tmp/sage_final_preflight_dev.json
```

Results:

- Focused preflight/routing/feedback tests: `36 passed`.
- Statistical dry run: PASS.
- Development preflight: PASS.

Full targeted validation:

```bash
PYTHONPATH=src:. python scripts/migrate_registry.py --check-only \
  artifacts/registry_frozen_best3_claim/registry_manifest.json \
  artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json
PYTHONPATH=src:. pytest tests/unit/test_runtime_routing_scorer.py tests/unit/test_helper_contribution.py tests/unit/test_control_baseline_cache.py tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py tests/unit/test_v2_6_feedback_packets.py tests/unit/test_final_run_preflight.py -q
PYTHONPATH=src:. python scripts/write_final_statistical_analysis.py
git diff --check
```

Results:

- Registry check: PASS, 2 registries scanned, 9 active entries PASS, 0 FAIL.
- Targeted tests: `132 passed`, 2 external-library deprecation warnings.
- Statistical dry run and artifact path check: PASS.
- `git diff --check`: PASS.

## Remaining Caveats

- Best3 remains the broad protected claim portfolio.
- V2.6 expanded contact-scalar remains secondary/candidate evidence, not an unconditional broad replacement.
- The current-code 500 gap reduction remains below the 10% target.
- Cached-control trace incompleteness must be disclosed in Chapter 3 and any future tool-birth interpretation.
- Some methodology heuristics remain code-defined and version-documented rather than fully config-driven.

## Next Action Sequence

1. Run final registry checks and targeted tests.
2. Run `git diff --check`.
3. Commit and push the readiness package.
4. Run clean-tree final preflight with report output outside the repo, for both best3 and expanded registries if both are candidates for future final runs.
5. Only after those pass, schedule any final complete benchmark runs.
