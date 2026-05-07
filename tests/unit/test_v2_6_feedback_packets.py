from __future__ import annotations

import json
from pathlib import Path

from sage_ts.evaluation.feedback_packets import (
    build_feedback_packets,
    summarize_feedback_packets,
    write_feedback_packets,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_build_feedback_packets_extracts_trace_routing_and_helper_outputs(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "protocol_run"
    control_dir = run_root / "control" / "control_run"
    sage_dir = run_root / "candidate" / "sage_run"
    scenario = "search_phone_number_with_name"
    rows = [
        {
            "name": scenario,
            "categories": ["SINGLE_USER_TURN"],
            "similarity": 0.5,
            "outcome_similarity": 0.0,
            "exception_type": None,
            "turn_count": 3,
            "outcome_check_count": 1,
            "outcome_checks": [
                {
                    "kind": "answer",
                    "included": True,
                    "score": 0.0,
                    "targets": ["+15551234567"],
                }
            ],
        }
    ]
    sage_rows = [dict(rows[0], similarity=1.0, outcome_similarity=1.0, turn_count=5)]
    _write_json(control_dir / "result_summary.json", {"per_scenario_results": rows})
    _write_json(sage_dir / "result_summary.json", {"per_scenario_results": sage_rows})
    _write_json(
        run_root / "paired_comparison.json",
        {
            "deltas": [
                {
                    "scenario": scenario,
                    "control_similarity": 0.5,
                    "candidate_similarity": 1.0,
                    "delta": 0.5,
                    "control_outcome_similarity": 0.0,
                    "candidate_outcome_similarity": 1.0,
                    "outcome_delta": 1.0,
                }
            ]
        },
    )
    _write_json(
        sage_dir / "trajectories" / scenario / "conversation.json",
        [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "What is Ada's phone number?"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "plan_contact_lookup_query",
                            "arguments": '{"contact_name":"Ada","requested_field":"phone_number"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "name": "plan_contact_lookup_query",
                "content": '{"lookup_kwargs":{"name":"Ada"},"requested_field":"phone_number","abstain_reason":null}',
            },
            {"role": "assistant", "content": "Ada's phone number is +15551234567."},
        ],
    )
    _write_jsonl(
        sage_dir / "scenario_tool_selection.jsonl",
        [
            {
                "scenario": scenario,
                "generated_tools_visible": ["plan_contact_lookup_query"],
                "generated_tools_called": ["plan_contact_lookup_query"],
                "generated_tools_not_called": [],
                "generated_tools_failed": [],
                "selection_status": "generated_tool_called",
            }
        ],
    )
    _write_jsonl(
        sage_dir / "scenario_tool_visibility.jsonl",
        [
            {
                "scenario": scenario,
                "generated_tools": ["plan_contact_lookup_query"],
                "retained_tools_loaded": ["plan_contact_lookup_query"],
                "routing_decisions": {
                    "plan_contact_lookup_query": {
                        "status": "shown",
                        "reason": "generic_relevance_score_passed",
                    }
                },
            }
        ],
    )

    packets = build_feedback_packets(run_root, run_id="synthetic")

    assert len(packets) == 1
    packet = packets[0]
    assert packet["schema_version"] == "v2_6_task_feedback_packet_v1"
    assert packet["scenario"] == scenario
    assert packet["base_task_family"] == scenario
    assert packet["surface_domain"] == "contacts"
    assert packet["scores"]["gain_regression_preserved"] == "gain"
    assert packet["no_current_helper_fit"] is False
    assert packet["helper_called_tools"] == ["plan_contact_lookup_query"]
    assert packet["actual_helper_calls"][0]["arguments"]["contact_name"] == "Ada"
    assert (
        packet["actual_helper_calls"][0]["output"]["requested_field"] == "phone_number"
    )
    assert (
        packet["routing_show_hide_reasons"]["plan_contact_lookup_query"]["reason"]
        == "generic_relevance_score_passed"
    )
    assert packet["feedback_sufficiency"]["sufficient_for_tool_birth"] is True

    summary = summarize_feedback_packets(packets)
    assert summary["packet_count"] == 1
    assert summary["helper_called_packet_count"] == 1


def test_write_feedback_packets_outputs_jsonl_and_summary(tmp_path: Path) -> None:
    run_root = tmp_path / "protocol_run"
    control_dir = run_root / "control" / "control_run"
    sage_dir = run_root / "candidate" / "sage_run"
    scenario = "find_distance_with_location_name_insufficient_information"
    result = {
        "name": scenario,
        "categories": ["INSUFFICIENT_INFORMATION"],
        "similarity": 0.0,
        "outcome_similarity": 0.0,
        "exception_type": None,
        "turn_count": 2,
        "outcome_checks": [],
    }
    _write_json(control_dir / "result_summary.json", {"per_scenario_results": [result]})
    _write_json(sage_dir / "result_summary.json", {"per_scenario_results": [result]})
    _write_json(
        run_root / "paired_comparison.json",
        {
            "deltas": [
                {
                    "scenario": scenario,
                    "control_similarity": 0.0,
                    "candidate_similarity": 0.0,
                    "delta": 0.0,
                    "control_outcome_similarity": 0.0,
                    "candidate_outcome_similarity": 0.0,
                    "outcome_delta": 0.0,
                }
            ]
        },
    )
    _write_json(
        sage_dir / "trajectories" / scenario / "conversation.json",
        [{"role": "user", "content": "Find the distance."}],
    )

    path = write_feedback_packets(
        run_root, tmp_path / "feedback", run_id="distance_run"
    )

    assert path.exists()
    packet = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert (
        packet["likely_failure_mechanism"] == "safe_insufficient_information_abstention"
    )
    assert packet["feedback_sufficiency"]["identifies_negative_or_abstain_case"] is True
    assert packet["feedback_sufficiency"]["sufficient_for_tool_birth"] is True
    summary = json.loads(
        (path.parent / "feedback_summary.json").read_text(encoding="utf-8")
    )
    assert (
        summary["top_no_fit_mechanisms"]["safe_insufficient_information_abstention"]
        == 1
    )
