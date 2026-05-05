# V2.2 Selector Actor-Policy Diagnostic20 Report

## Objective

Test whether a bounded actor-policy/routing intervention can make the acting model naturally call `select_visible_record_by_constraints` when visible records and a matching constraint-selection task are present.

## Protected Assets

- Frozen best3 registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Frozen best3 modified: `no`
- Masked best3 tools: `relative_day_time_to_timestamp`, `resolve_search_window_or_bounds`, `select_record_by_timestamp_extreme`
- Confirmed V2.2 registry left unchanged: `artifacts/registry_candidates/v2_2_new_toolset/registry_manifest.json`

## Files Changed

- `src/sage_ts/adapters/openai_toolsandbox_roles.py`
- `src/sage_ts/runtime/routing_scorer.py`
- `tests/unit/test_openai_selector_actor_policy.py`
- `tests/unit/test_runtime_routing_scorer.py`
- `scripts/build_v2_2_loop2_artifacts.py`

## Cohort

- Manifest: `artifacts/summaries/v2_2_loop2_20260505_164027/selector_actor_policy20_manifest.json`
- Diversity report: `artifacts/summaries/v2_2_loop2_20260505_164027/selector_actor_policy20_diversity_report.json`
- Cohort quality: `PASS`
- Scenarios: `20`
- Distinct base task families: `10`
- Largest family share: `0.10`
- Roles: selector positives plus negative/no-helper cases

## Command

```bash
PYTHONPATH=src:. OPENAI_API_KEY=<env> python scripts/run_v2_micro_experiment.py \
  --manifest artifacts/summaries/v2_2_loop2_20260505_164027/selector_actor_policy20_manifest.json \
  --registry artifacts/registry_candidates/v2_2_selector_actor_policy20_20260505_164027/registry_manifest.json \
  --output-root outputs/v2_2_selector_actor_policy20_rerun_20260505_155948 \
  --generation-mode off \
  --control-cache use-if-eligible
```

## Dashboards

- Dashboard: `http://127.0.0.1:5594/outputs/v2_2_selector_actor_policy20_rerun_20260505_155948/mechanism_40_20260505_155951/dashboard/index.html`
- Task focus: `http://127.0.0.1:5594/outputs/v2_2_selector_actor_policy20_rerun_20260505_155948/mechanism_40_20260505_155951/dashboard/task_focus.html`

## Results

| Metric | Value |
| --- | ---: |
| Run | `outputs/v2_2_selector_actor_policy20_rerun_20260505_155948/mechanism_40_20260505_155951` |
| Outcome delta | `-0.0263` |
| Canonical/reference delta | `-0.0172` |
| Exact successes | `2 -> 2` |
| Runtime exceptions | `0` |
| Helper side-effect incidents | `0` |
| Protocol gate | `FAIL` |

## Helper Adoption

| Helper | Visible | Called | Visible-not-called | Failed attempts | Called-subset outcome |
| --- | ---: | ---: | ---: | ---: | ---: |
| `select_visible_record_by_constraints` | `16` | `0` | `16` | `0` | n/a |

Routing exposure was repaired: the helper was visible on the relevant selector cases. Natural adoption still stayed at zero. Trace review indicates the direct base-tool route often returned one obvious record or scalar answer, so the model continued manually answering rather than calling the helper.

## Decision

The selector lane is parked for now. The blocker is no longer hidden routing suppression; it is natural adoption/value under the current actor policy. A deeper actor-policy redesign could revisit this later, but Loop 2 should not promote or confirm the selector.

## Decision Label

`selector lane parked`
