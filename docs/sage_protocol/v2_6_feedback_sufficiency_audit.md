# V2.6 Feedback Sufficiency Audit

## Objective
Determine whether current SAGE artifacts contain enough structured task feedback to drive cross-task tool birth instead of one-off helper ideas.

## Files Changed
- `src/sage_ts/evaluation/feedback_packets.py`
- `scripts/export_v2_6_feedback_packets.py`
- `tests/unit/test_v2_6_feedback_packets.py`
- `docs/sage_protocol/v2_6_feedback_packet_schema.md`
- `artifacts/summaries/v2_6_feedback_packets/*/task_feedback.jsonl`
- `artifacts/summaries/v2_6_feedback_packets/*/feedback_summary.json`

## Feedback Packet Export Commands
```bash
PYTHONPATH=src:. python scripts/export_v2_6_feedback_packets.py \
  --run-root outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428 --run-id v2_formal100_best3 \
  --run-root outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222 --run-id v2_formal250_best3 \
  --run-root outputs/v2_1_formal500_best3_parallel_20260504_232126/full_benchmark_20260504_232130 --run-id v2_formal500_best3 \
  --run-root outputs/v2_1_formal1000_best3_full_20260505_004901/full_benchmark_20260505_004905 --run-id v2_formal1032_best3 \
  --output-root artifacts/summaries/v2_6_feedback_packets

PYTHONPATH=src:. python scripts/export_v2_6_feedback_packets.py \
  --run-root outputs/v2_5_gap_closure250_pack2_contact_best3_20260506_205033/validate_250_20260506_205037 --run-id v2_5_broad250_best3_contact_manifest \
  --run-root outputs/v2_5_gap_closure250_pack2_contact_pack_20260506_210835/validate_250_20260506_210840 --run-id v2_5_broad250_contact_pack \
  --run-root outputs/v2_5_contact_routing_repair20_pack_20260506_220717/mechanism_40_20260506_220721 --run-id v2_5_contact_routing_repair20 \
  --run-root outputs/v2_6_contact_pack_rerun_best3/validate_100_20260507_000133 --run-id v2_6_contact_rerun100_best3 \
  --run-root outputs/v2_6_contact_pack_rerun_pack/validate_100_20260507_002045 --run-id v2_6_contact_rerun100_pack \
  --output-root artifacts/summaries/v2_6_feedback_packets
```

## Source Runs Audited
| Run id | Packets | No-current-helper-fit | Feedback insufficient | Top no-fit mechanisms |
| --- | ---: | ---: | ---: | --- |
| `v2_formal100_best3` | 100 | 31.0% | 5 | unclassified 23, contact 5, insufficient-info 3 |
| `v2_formal250_best3` | 250 | 52.0% | 8 | insufficient-info 48, unclassified 43, contact 39 |
| `v2_formal500_best3` | 500 | 67.6% | 8 | insufficient-info 119, contact 107, unclassified 96, external 16 |
| `v2_formal1032_best3` | 1032 | 69.8% | 24 | insufficient-info 224, contact 184, unclassified 184, external 128 |
| `v2_5_broad250_contact_pack` | 250 | 46.0% | 8 | insufficient-info 48, unclassified 39, contact 24 |
| `v2_6_contact_rerun100_best3` | 100 | 48.0% | 0 | contact 36, insufficient-info 12 |
| `v2_6_contact_rerun100_pack` | 100 | 24.0% | 0 | contact 12, insufficient-info 12 |

## Sufficiency Findings
- The new packets identify task identity, task strata, surface domain, control/SAGE trace summaries, helper visibility/calls/VNC, helper arguments/outputs, route show/hide reasons, safety incidents, no-current-helper-fit, missing deterministic intermediate step, and likely failure mechanism.
- Feedback is sufficient for contact lookup and external answer-resolution candidate design because it identifies required inputs, outputs, direct-route weakness, adoption evidence, and negatives.
- Feedback is sufficient for insufficient-information analysis, but not as a normal helper-promotion lane. Prior `detect_missing_information_before_minefield` diagnostics showed natural calls, yet helper calls on location insufficient-information cases still triggered minefield/canonical penalties. This points to actor-policy/routing behavior, not a promoted helper.
- Remaining `no_current_helper_fit_unclassified` packets still need better mechanism labels, especially device-service and holiday/calendar families. The packet records contain enough scenario/family/surface information to build abstraction packets, but the classifier should be improved in future loops.

## User-Flagged Minefield Case
The dashboard task `find_distance_with_location_name_insufficient_information` is correctly classified as `safe_insufficient_information_abstention`. The candidate trace that computed a numeric distance despite current location being unavailable is a rubric-compliant zero because `calculate_lat_lon_distance` is a forbidden minefield action in that scenario. This reinforces that insufficient-information handling should prevent unsafe downstream computation, not merely format a computed result.

## Pipeline Blocker Diagnosis
- Feedback insufficiency: mostly repaired for the audited runs.
- Bad shortfall clustering: still present for `no_current_helper_fit_unclassified` device/calendar/service lanes.
- Wrong abstraction packet: insufficient-information should be an actor-policy packet, not a standard callable helper packet.
- Tool hidden by routing: repaired for contact false exposure; still requires monitoring.
- Tool too narrow to affect broad 250: confirmed for contact pack alone and distance formatter.

## Decision Label
`feedback sufficient for tool birth`

## Exact Next Action
Use enriched feedback packets to build cross-task abstraction packets and avoid generating another narrow single-lane helper unless it can prove additive value over best3.
