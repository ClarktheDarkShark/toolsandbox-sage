import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import sage_ts.campaign.artifacts as campaign_artifacts
from sage_ts.campaign.artifacts import append_event, read_jsonl


def test_read_jsonl_tolerates_only_an_unterminated_live_tail(tmp_path: Path) -> None:
    path = tmp_path / "live.jsonl"
    path.write_text('{"complete": true}\n{"partial":', encoding="utf-8")

    assert read_jsonl(path) == [{"complete": True}]

    path.write_text('{"complete": true}\nnot-json\n', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        read_jsonl(path)


def test_concurrent_event_appends_remain_complete_and_consistently_ordered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(campaign_artifacts, "git_value", lambda *_args: "git")

    def write_event(index: int) -> None:
        append_event(
            "scenario_finished",
            {"sequence": index, "payload": "x" * 50_000},
            root=tmp_path,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(write_event, range(40)))

    latest_rows = read_jsonl(tmp_path / "events" / "latest.jsonl")
    dated_paths = list((tmp_path / "events").glob("[0-9]*.jsonl"))
    assert len(dated_paths) == 1
    dated_rows = read_jsonl(dated_paths[0])
    assert [row["sequence"] for row in latest_rows] == [
        row["sequence"] for row in dated_rows
    ]
    assert sorted(row["sequence"] for row in latest_rows) == list(range(40))


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


def test_native_action_birth_stop_is_valid_campaign_event(tmp_path: Path) -> None:
    row = append_event(
        "jit_proactive_birth_stopped_after_action_tool",
        {"tool_name": "complete_action"},
        root=tmp_path,
    )

    assert row["event"] == "jit_proactive_birth_stopped_after_action_tool"
    latest = tmp_path / "events" / "latest.jsonl"
    assert json.loads(latest.read_text(encoding="utf-8"))["tool_name"] == (
        "complete_action"
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
