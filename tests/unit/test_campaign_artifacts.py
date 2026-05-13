import json
from pathlib import Path

from sage_ts.campaign.artifacts import append_event


def test_duplicate_birth_skip_is_valid_campaign_event(tmp_path: Path) -> None:
    row = append_event(
        "tool_birth_skipped_existing",
        {"tool_name": "recency_to_timestamp_bounds"},
        root=tmp_path,
    )

    assert row["event"] == "tool_birth_skipped_existing"
    latest = tmp_path / "events" / "latest.jsonl"
    assert json.loads(latest.read_text(encoding="utf-8"))["tool_name"] == (
        "recency_to_timestamp_bounds"
    )


def test_tool_repair_attempt_is_valid_campaign_event(tmp_path: Path) -> None:
    row = append_event(
        "tool_repair_attempted",
        {"tool_name": "thin_helper", "accepted": False},
        root=tmp_path,
    )

    assert row["event"] == "tool_repair_attempted"
    latest = tmp_path / "events" / "latest.jsonl"
    payload = json.loads(latest.read_text(encoding="utf-8"))
    assert payload["tool_name"] == "thin_helper"
    assert payload["accepted"] is False


def test_self_evolution_stop_recommendation_is_valid_campaign_event(
    tmp_path: Path,
) -> None:
    row = append_event(
        "self_evolution_stop_recommended",
        {"reason": "pulse_lift_below_threshold"},
        root=tmp_path,
    )

    assert row["event"] == "self_evolution_stop_recommended"
    latest = tmp_path / "events" / "latest.jsonl"
    payload = json.loads(latest.read_text(encoding="utf-8"))
    assert payload["reason"] == "pulse_lift_below_threshold"


def test_run_stopped_early_is_valid_campaign_event(tmp_path: Path) -> None:
    row = append_event(
        "run_stopped_early",
        {"completed": 12, "requested": 20},
        root=tmp_path,
    )

    assert row["event"] == "run_stopped_early"
    latest = tmp_path / "events" / "latest.jsonl"
    payload = json.loads(latest.read_text(encoding="utf-8").splitlines()[-1])
    assert payload["completed"] == 12
    assert payload["requested"] == 20
