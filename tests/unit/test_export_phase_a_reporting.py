from __future__ import annotations

import json
from pathlib import Path

from scripts.export_phase_a_reporting import emit_phase_a_reports


def _scenario_row(
    name: str, similarity: float, outcome_similarity: float
) -> dict[str, object]:
    return {
        "name": name,
        "categories": ["STATE_DEPENDENCY"],
        "traceback": None,
        "exception_type": None,
        "milestone_similarity": similarity,
        "minefield_similarity": 0.0,
        "similarity": similarity,
        "turn_count": 3,
        "milestone_mapping": {},
        "minefield_mapping": {},
        "outcome_similarity": outcome_similarity,
        "outcome_milestone_similarity": outcome_similarity,
        "outcome_minefield_similarity": 0.0,
        "outcome_check_count": 2,
        "outcome_checks": [],
    }


def _write_summary(root: Path, rows: list[dict[str, object]]) -> None:
    payload = {
        "scenario_count": len(rows),
        "status": "complete",
        "per_scenario_results": rows,
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "result_summary.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def test_emit_phase_a_reports_generates_spine_artifacts(tmp_path: Path) -> None:
    control = tmp_path / "control"
    candidate = tmp_path / "candidate"
    protocol_root = tmp_path / "protocol"
    output_root = tmp_path / "phase_A_reports"

    control_rows = [
        _scenario_row("task_alpha", 0.70, 0.70),
        _scenario_row("task_beta", 0.50, 0.50),
    ]
    candidate_rows = [
        _scenario_row("task_alpha", 0.80, 0.80),
        _scenario_row("task_beta", 0.90, 0.90),
    ]
    _write_summary(control, control_rows)
    _write_summary(candidate, candidate_rows)

    candidate_selection = candidate / "scenario_tool_selection.jsonl"
    candidate_selection.write_text(
        "\n".join(
            json.dumps(
                {
                    "scenario": row["name"],
                    "selection_status": "generated_tool_called",
                    "generated_tools_visible": ["prepare_reminder_creation_args"],
                    "generated_tools_attempted": ["prepare_reminder_creation_args"],
                    "generated_tools_called": ["prepare_reminder_creation_args"],
                    "generated_tools_not_called": [],
                    "filtered_out_generated_tools": [],
                }
            )
            for row in candidate_rows
        )
        + "\n",
        encoding="utf-8",
    )
    (candidate / "reuse_events.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "tool_name": "prepare_reminder_creation_args",
                    "scenario": "task_alpha",
                }
            )
            for _ in candidate_rows
        )
        + "\n",
        encoding="utf-8",
    )
    (candidate / "side_effect_preservation_report.jsonl").write_text(
        json.dumps({"scenario": "task_alpha", "preserves": True}) + "\n",
        encoding="utf-8",
    )
    for row in control_rows:
        scenario = str(row["name"])
        (control / "trajectories" / scenario).mkdir(parents=True, exist_ok=True)
        (candidate / "trajectories" / scenario).mkdir(parents=True, exist_ok=True)
        transcript = [
            {"role": "assistant", "content": f"before {scenario}"},
            {"role": "assistant", "content": f"final {scenario}"},
        ]
        (control / "trajectories" / scenario / "conversation.json").write_text(
            json.dumps(transcript, indent=2) + "\n", encoding="utf-8"
        )
        (candidate / "trajectories" / scenario / "conversation.json").write_text(
            json.dumps(transcript, indent=2) + "\n", encoding="utf-8"
        )

    protocol_root.mkdir(parents=True, exist_ok=True)
    (protocol_root / "protocol_manifest.json").write_text(
        json.dumps(
            {
                "mode": "transfer_40",
                "generation_enabled": False,
                "control_dir": str(control),
                "candidate_dir": str(candidate),
                "registry_dir": str(tmp_path / "registry"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = emit_phase_a_reports(
        protocol_root=tmp_path / "protocol", output_dir=output_root
    )
    required = [
        "protocol_manifest.json",
        "canonical_score.json",
        "final_task_success_score.json",
        "exact_success.json",
        "gains_regressions_preserved.json",
        "tool_visibility_and_call_report.json",
        "tool_applicable_subset_report.json",
        "non_applicable_subset_report.json",
        "route_mismatch_report.json",
        "runtime_exceptions.json",
        "side_effect_preservation_report.jsonl",
        "confidence_intervals.json",
        "adjudication_packet.jsonl",
    ]
    artifact_paths = {Path(path).name for path in payload["artifact_paths"]}
    for name in required:
        assert (output_root / name).exists()
        assert name in artifact_paths

    canonical = json.loads(
        (output_root / "canonical_score.json").read_text(encoding="utf-8")
    )
    assert canonical["control"]["mean_similarity"] == 0.6
    assert canonical["candidate"]["mean_similarity"] == 0.8500000000000001
    assert canonical["delta"] == 0.2500000000000001
