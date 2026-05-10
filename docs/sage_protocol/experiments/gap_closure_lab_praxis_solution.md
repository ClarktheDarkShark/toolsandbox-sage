# SAGE Gap-Closure Lab Praxis Solution

Experimental evidence only. This document does not modify protected final evidence.

## Result

The frozen experimental candidate `praxis_bridgepack_frozen_candidate` is the best option from the gap-closure branch to carry into later protected hardening.

- Candidate registry: `artifacts/registry_experiments/gap_closure_lab/praxis_bridgepack_frozen_candidate/registry_manifest.json`
- Candidate registry SHA-256: `7867cde8c8709f31efb02006e8c0743bbf890f2ede1519de99155e4631614349`
- Freeze manifest: `artifacts/registry_experiments/gap_closure_lab/praxis_bridgepack_frozen_candidate/candidate_freeze_manifest.json`
- Locked summary: `artifacts/experiment_manifests/gap_closure_lab/praxis_formal_validation/praxis_formal500_locked_summary.json`
- Locked summary SHA-256: `41db7fed0e0997cfb691791abca59d47941a2f076951153382b17df3242e2dcc`

The matched formal500 validation used the same formal manifest, same model key, generation disabled, per-task cached controls, fresh SAGE/candidate arms, OpenAI response cache disabled, and no code or registry changes between matched arms.

## Head-To-Head Formal500

| Arm | Registry SHA | Control outcome | Candidate outcome | Outcome lift | Exact success delta | Runtime exceptions | Helper side effects | Gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Protected best3 reference copy | `76de726d...` | `0.594872` | `0.755552` | `+0.160680` | `+104` | `0` | `0` | pass |
| V2.6 reference copy | `ab5f5c36...` | `0.594872` | `0.781781` | `+0.186909` | `+118` | `0` | `0` | pass |
| Praxis frozen BridgePack | `7867cde8...` | `0.594872` | `0.832711` | `+0.237839` | `+166` | `0` | `0` | pass |

Praxis exceeded best3 by `+0.077160` candidate outcome points and V2.6 by `+0.050930` candidate outcome points on the same formal500 manifest.

## Why This Is The Praxis Solution

The candidate combines the retained value pockets instead of treating rare helper calls as irrelevant:

- Best3-style search-window, timestamp, and record-selection helpers.
- Contact lookup and relationship/update planners.
- Reminder recency and scheduling support.
- Settings/device-state action sequencing.
- Message-recency and counterparty selection helpers.
- Send-message contact lookup/precondition support.
- Actor/router bridge repairs for natural adoption, final-answer retention, and scrambled-name execution compatibility.

The strongest called-subset signals in the Praxis formal500 run were:

| Tool | Visible | Called | Called-subset outcome delta |
| --- | ---: | ---: | ---: |
| `select_message_content_by_recency` | 52 | 13 | `+0.757545` |
| `next_weekday_time_to_timestamp` | 12 | 12 | `+0.562418` |
| `resolve_search_window_or_bounds` | 106 | 64 | `+0.431088` |
| `plan_contact_relationship_batch_update` | 19 | 19 | `+0.385314` |
| `relative_day_time_to_timestamp` | 51 | 45 | `+0.367470` |
| `plan_contact_lookup_query` | 24 | 16 | `+0.308128` |

Some retained helpers are low-frequency. They remain valuable because they close specific recurring buckets and showed positive natural-call contribution when their bucket appeared.

## Claim Boundary

This is locked matched experimental evidence on the formal manifest, not protected final-package claim evidence. The protected best3 registry and final evidence artifacts were not modified. A later final-hardening branch should review the branch-only actor/router bridge dependency, rerun or audit the exact artifacts, and only then decide whether any protected claim should be updated.

## Reproduction Command

Use the same command shape for future verification. Controls must use the per-task baseline cache; candidate/SAGE arms must remain fresh.

```bash
conda run -n lifelong bash -lc 'export PYTHONPATH=src:.; python scripts/run_sage_protocol.py \
  --mode full_benchmark \
  --manifest docs/sage_protocol/manifests/v2_1_formal_500.json \
  --registry-dir artifacts/registry_experiments/gap_closure_lab/praxis_bridgepack_frozen_candidate \
  --generation off \
  --disable-openai-response-cache \
  --cache-mode off \
  --parallel-arms \
  --control-cache use-if-eligible \
  --output-root outputs/gap_closure_lab/praxis_formal_validation/praxis_bridgepack_formal500_verify \
  --artifact-root artifacts/experiment_manifests/gap_closure_lab/praxis_formal_validation/campaign_artifacts_praxis_bridgepack_formal500_verify \
  --dashboard-port 62243'
```

## Dashboards

The run exports the standard dashboard, Task Focus dashboard, and the new Task Compare dashboard:

- `dashboard/index.html`: run overview.
- `dashboard/task_focus.html`: full task and transcript inspection.
- `dashboard/task_compare.html`: comparison-first task view with run-level score/outcome lift, a minimal task list, task-level lift details, and a clickable tools-contribution drawer.
