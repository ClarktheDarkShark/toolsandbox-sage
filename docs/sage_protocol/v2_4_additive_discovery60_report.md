# V2.4 Additive Discovery60 Report

## Objective

Test exactly one non-parked additive-over-best3 cluster with best3 active: `external_service_answer_extraction`.

## Files Changed

- `src/sage_ts/adequacy/inadequacy_classifier.py`
- `src/sage_ts/evaluation/task_strata.py`
- `src/sage_ts/orchestration/online_birth.py`
- `src/sage_ts/runtime/toolsandbox_integration.py`
- `tests/unit/test_online_birth.py`
- `tests/unit/test_state_helper_guidance.py`
- `tests/unit/test_task_strata.py`
- `scripts/build_v2_4_additive_artifacts.py`
- `docs/sage_protocol/v2_4_additive_gap_atlas_report.md`

## Commands Run

- Artifact builder: `PYTHONPATH=src:. python scripts/build_v2_4_additive_artifacts.py --timestamp 20260506_095428`
- Registry check: `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_candidates/v2_4_additive_discovery60_20260506_095428/registry_manifest.json artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Tests: `PYTHONPATH=src:. pytest tests/unit/test_task_strata.py tests/unit/test_online_birth.py tests/unit/test_state_helper_guidance.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_runtime_routing_scorer.py -q`
- Discovery60 command: see `artifacts/logs/v2_4_additive_discovery60_20260506_095428/command.txt`

## Cohort And Registry

- Manifest: `artifacts/summaries/v2_4_additive_discovery60_20260506_095428/cohort_manifest.json`
- Diversity report: `artifacts/summaries/v2_4_additive_discovery60_20260506_095428/cohort_diversity_report.json`
- Cohort quality: `PASS`
- Warnings: `external_service_cases_present, no_expected_helper_fit, low_expected_helper_fit_share, generation_enabled_but_no_post_birth_reuse_opportunity`
- Candidate registry path: `artifacts/registry_candidates/v2_4_additive_discovery60_20260506_095428/registry_manifest.json`
- Candidate registry SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Frozen best3 registry SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Generation mode: `ON`
- Best3 active, not masked: `yes`
- Control cache source: `fresh`; cached `0`, fresh `60`
- Dashboard: `http://127.0.0.1:5623/outputs/v2_4_additive_discovery60_20260506_095428/mechanism_60_20260506_095500/dashboard/index.html`
- Task focus: `http://127.0.0.1:5623/outputs/v2_4_additive_discovery60_20260506_095428/mechanism_60_20260506_095500/dashboard/task_focus.html`

## Framework Repair Before Rerun

The first pass accepted `extract_service_answer_field` but the generated contract preserved placeholder `search_service_payload`, so the runtime correctly hid the helper as `blocked_by_missing_downstream_original_tool`. This exposed a framework blocker, not candidate value.

Repairs made before the fair rerun:

- Added concrete external-service answer-extraction birth evidence.
- Rejected placeholder original-tool preservation contracts mechanically.
- Allowed derived helpers with multiple concrete producer tools to route when any matching producer is available.
- Bridged list-valued producer traces into first visible dict payload for one-dict derived helpers.

## Metrics

| Metric | Value |
|---|---:|
| Canonical/reference delta | `+0.0127` |
| Outcome/task-completion delta | `+0.0031` |
| Relative outcome lift | `+1.20%` |
| Exact successes | `8 -> 7` |
| Canonical gains / regressions / preserved | `18 / 17 / 25` |
| Outcome gains / regressions / preserved | `5 / 8 / 31` |
| Runtime exceptions | `0` |
| Helper side-effect incidents | `0` |

## Candidate Birth And Adoption

| Candidate | Proposed | Accepted | Visible | Called | VNC | Failed attempts | Called-subset outcome | Called-subset canonical |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `extract_service_answer_field` | 1 | 1 | 49 | 5 | 44 | 0 | `-0.1804` | `+0.1609` |

Called-subset outcome was negative despite zero runtime and side-effect incidents. The helper mostly extracted Celsius temperature values; in Fahrenheit/time-difference tasks that was not enough to complete the task and sometimes became a misleading intermediate.

## Interpretation

This was a valid SAGE tool-birth test after the repair: a candidate was born from a recurring cluster, validated, exposed, and naturally called. It does not pass the additive gate because its called-subset outcome contribution is negative and visible-not-called pollution is high.

## Candidate Decision

`extract_service_answer_field`: parked as `candidate concept negative` for the current broad external-answer cluster. Do not run additive confirmation60.

## Decision Label

`candidate concept negative`

## Exact Next Action

Do not promote or confirm this candidate. Preserve frozen best3 as the final validated portfolio. If discovery resumes, rebuild a fresh atlas excluding this broad external-answer extraction design and only test a materially different non-parked mechanism with plausible additivity over best3.
