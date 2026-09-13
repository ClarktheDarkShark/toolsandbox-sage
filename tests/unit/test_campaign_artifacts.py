import json
from pathlib import Path
from typing import cast

from sage_ts.campaign.artifacts import append_event, read_jsonl
from sage_ts.orchestration.online_birth import (
    GeneratedToolFactory,
    OnlineBirthController,
)
from sage_ts.registry.store import RegistryStore

POST_DEPLOYMENT_LIFECYCLE_EVENTS = (
    "post_deployment_tool_repair_queued",
    "post_deployment_public_contract_failure",
    "post_deployment_tool_repair_started",
    "post_deployment_tool_repair_attempted",
    "post_deployment_tool_repair_attempt_failed",
    "post_deployment_tool_repair_accepted",
    "post_deployment_tool_repair_deferred",
    "post_deployment_tool_repair_stale",
    "post_deployment_tool_repair_retired",
    "post_deployment_tool_repair_acknowledged",
    "post_deployment_tool_repair_acknowledgement_failed",
    "post_deployment_tool_repair_transaction_recovered",
    "post_deployment_tool_canary_observed",
    "post_deployment_tool_canary_out_of_family_call_ignored",
    "post_deployment_tool_canary_promoted",
    "post_deployment_tool_canary_retired",
)


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


def test_online_birth_post_deployment_events_append_without_hook_failures(
    tmp_path: Path,
) -> None:
    campaign_root = tmp_path / "campaign"
    output_dir = tmp_path / "run"
    output_dir.mkdir()
    controller = OnlineBirthController(
        store=RegistryStore(tmp_path / "registry"),
        generator=cast(GeneratedToolFactory, object()),
        output_dir=output_dir,
        failure_memory_path=None,
        event_hook=lambda event, payload: append_event(
            event,
            payload,
            root=campaign_root,
        ),
    )

    for event in POST_DEPLOYMENT_LIFECYCLE_EVENTS:
        controller._event(event, {"tool_name": "generated_helper"})

    rows = read_jsonl(campaign_root / "events" / "latest.jsonl")
    assert [row["event"] for row in rows] == list(POST_DEPLOYMENT_LIFECYCLE_EVENTS)
    run_events = read_jsonl(output_dir / "sage_run_events.jsonl")
    assert not any(
        row.get("event") == "campaign_event_hook_failed" for row in run_events
    )
