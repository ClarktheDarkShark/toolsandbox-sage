# V2.6 Feedback Packet Schema

Decision label: `feedback sufficient for tool birth`

`artifacts/summaries/v2_6_feedback_packets/<run_id>/task_feedback.jsonl` contains one JSON object per scenario from a completed paired protocol run.

Required fields:

- `schema_version`: currently `v2_6_task_feedback_packet_v1`.
- `run_id`, `run_root`, `control_dir`, `sage_dir`: artifact provenance.
- `scenario`, `scenario_id`, `base_task_family`, `task_strata`, `surface_domain`, `categories`: task identity and diversity labels.
- `user_request_summary`: first user request from the trace, or scenario-derived fallback.
- `expected_final_answer_or_state`: available outcome targets and included outcome checks.
- `control_trace_summary`, `sage_trace_summary`: tool-call names, arguments, output previews, final assistant preview, and turn counts.
- `control_trace_completeness`: whether the control trace is `trace_complete`, `score_complete_trace_incomplete`, or `trace_unknown_or_missing`. Cached task-level control rows remain score-complete for metric arithmetic, but may be trace-incomplete for feedback interpretation.
- `scores`: control/SAGE outcome, control/SAGE canonical, deltas, exact-success flags, and gain/regression/preserved label.
- `expected_helper_fit`, `expected_birth_opportunities`, `no_current_helper_fit`: helper coverage estimate using the existing task-strata rules and loaded registry tools when available.
- `helper_visible_tools`, `helper_called_tools`, `visible_not_called_tools`, `failed_helper_attempts`: adoption/accounting state.
- `actual_helper_calls`: captured helper call arguments and outputs from conversations.
- `abstain_reasons`: abstain/error reasons extracted from helper outputs when present.
- `routing_show_hide_reasons`: per-helper routing decision objects from `scenario_tool_visibility.jsonl`.
- `side_effect_incidents`, `runtime_exceptions`, `final_state_mismatch`: safety and scoring evidence.
- `missing_deterministic_intermediate_step`, `likely_failure_mechanism`: mechanism-level feedback for tool-birth clustering.
- `feedback_sufficiency`: booleans and missing fields indicating whether the packet can support tool generation.
- `task_focus_pair`: dashboard display/cache provenance when available.

Export command:

```bash
PYTHONPATH=src:. python scripts/export_v2_6_feedback_packets.py \
  --run-root <completed_protocol_run_root> \
  --output-root artifacts/summaries/v2_6_feedback_packets
```

This schema is artifact-only and does not modify registries or rerun model calls.
