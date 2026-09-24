import json
from pathlib import Path
from queue import Queue

import pytest

from sage_ts.orchestration.self_evolution_reflection import (
    FRESH_CONTROL_COMPLETE_EVENT,
    FRESH_CONTROL_ROW_EVENT,
    SelfEvolutionReflectionController,
    _online_feedback_outcome_with_source,
)
from sage_ts.registry.store import RegistryStore


@pytest.mark.parametrize(
    ("row", "expected", "expected_source"),
    [
        pytest.param(
            {
                "outcome_similarity": 0.75,
                "online_feedback_outcome_similarity": None,
            },
            0.75,
            "audited_outcome_fallback",
            id="null-paper-feedback-falls-back",
        ),
        pytest.param(
            {"outcome_similarity": 0.75},
            0.75,
            "audited_outcome_fallback",
            id="missing-paper-feedback-falls-back",
        ),
        pytest.param(
            {
                "outcome_similarity": 0.75,
                "online_feedback_outcome_similarity": 0.0,
            },
            0.0,
            "paper_era_online_feedback",
            id="zero-paper-feedback-is-preserved",
        ),
        pytest.param(
            {
                "outcome_similarity": 0.25,
                "online_feedback_outcome_similarity": 0.75,
            },
            0.75,
            "paper_era_online_feedback",
            id="nonzero-paper-feedback-is-preserved",
        ),
        pytest.param(
            {
                "outcome_similarity": None,
                "online_feedback_outcome_similarity": None,
            },
            None,
            "unavailable",
            id="both-outcomes-unavailable",
        ),
    ],
)
def test_online_feedback_outcome_fallback(
    row: dict[str, object], expected: object, expected_source: str
) -> None:
    assert _online_feedback_outcome_with_source(row) == (expected, expected_source)


def _fresh_control_queue(*rows: dict[str, object]) -> Queue:
    channel: Queue = Queue()
    for row in rows:
        channel.put(
            {
                "event": FRESH_CONTROL_ROW_EVENT,
                "scenario": row["name"],
                "row": {"llm_cached_call_count": 0, **row},
            }
        )
    channel.put({"event": FRESH_CONTROL_COMPLETE_EVENT, "scenario_count": len(rows)})
    return channel


def _controller(
    tmp_path: Path,
    *control_rows: dict[str, object],
    pulse_interval: int = 1,
    min_pulse_tasks: int = 1,
) -> SelfEvolutionReflectionController:
    return SelfEvolutionReflectionController(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=tmp_path / "run",
        fresh_control_channel=_fresh_control_queue(*control_rows),
        pulse_interval=pulse_interval,
        min_pulse_tasks=min_pulse_tasks,
    )


def test_reflection_records_off_track_pulse_without_stopping(tmp_path: Path) -> None:
    controller = _controller(
        tmp_path,
        {
            "name": "search_phone_number_with_name",
            "similarity": 1.0,
            "outcome_similarity": 1.0,
        },
    )

    controller.assess_scenario(
        scenario_name="search_phone_number_with_name",
        result={"similarity": 0.0, "outcome_similarity": 0.0},
        selection_record={
            "generated_tools_visible": [],
            "generated_tools_called": [],
            "generated_tools_attempted": [],
            "generated_tools_failed": [],
        },
        side_effect_failures=[],
    )
    controller.assert_fresh_control_complete(("search_phone_number_with_name",))

    state = json.loads(
        (tmp_path / "run" / "self_evolution_reflection_state.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["completed_count"] == 1
    assert state["cache_hits"] == 0


def test_reflection_flags_sparse_positive_tool(tmp_path: Path) -> None:
    controller = _controller(
        tmp_path,
        {
            "name": "update_contact_relationship_with_relationship",
            "similarity": 0.0,
            "outcome_similarity": 0.0,
        },
    )

    controller.assess_scenario(
        scenario_name="update_contact_relationship_with_relationship",
        result={"similarity": 1.0, "outcome_similarity": 1.0},
        selection_record={
            "generated_tools_visible": ["plan_contact_relationship_batch_update"],
            "generated_tools_called": ["plan_contact_relationship_batch_update"],
            "generated_tools_attempted": ["plan_contact_relationship_batch_update"],
            "generated_tools_failed": [],
        },
        side_effect_failures=[],
    )
    controller.assert_fresh_control_complete(
        ("update_contact_relationship_with_relationship",)
    )

    lifecycle = json.loads(
        (tmp_path / "registry" / "tool_lifecycle.json").read_text(encoding="utf-8")
    )
    decision = lifecycle["tool_lifecycle"]["plan_contact_relationship_batch_update"]
    assert decision["decision"] == "keep_sparse_positive"
    assert decision["called_count"] == 1


def test_reflection_routes_repairs_harmful_calls_without_global_retirement(
    tmp_path: Path,
) -> None:
    controller = _controller(
        tmp_path,
        {
            "name": "add_reminder_content_and_week_delta_and_time",
            "similarity": 1.0,
            "outcome_similarity": 1.0,
        },
    )

    controller.assess_scenario(
        scenario_name="add_reminder_content_and_week_delta_and_time",
        result={"similarity": 0.25, "outcome_similarity": 0.0},
        selection_record={
            "generated_tools_visible": ["relative_day_time_to_timestamp"],
            "generated_tools_called": ["relative_day_time_to_timestamp"],
            "generated_tools_attempted": ["relative_day_time_to_timestamp"],
            "generated_tools_failed": [],
        },
        side_effect_failures=[],
    )
    controller.assert_fresh_control_complete(
        ("add_reminder_content_and_week_delta_and_time",)
    )

    lifecycle = json.loads(
        (tmp_path / "registry" / "tool_lifecycle.json").read_text(encoding="utf-8")
    )
    decision = lifecycle["tool_lifecycle"]["relative_day_time_to_timestamp"]
    assert decision["decision"] == "needs_route_repair"
    assert decision["harmful_called_count"] == 1


def test_reflection_keeps_positive_tool_with_side_effect_audit(
    tmp_path: Path,
) -> None:
    controller = _controller(
        tmp_path,
        {
            "name": "add_reminder_content_and_week_delta_and_time",
            "similarity": 0.0,
            "outcome_similarity": 0.0,
        },
    )

    controller.assess_scenario(
        scenario_name="add_reminder_content_and_week_delta_and_time",
        result={"similarity": 1.0, "outcome_similarity": 1.0},
        selection_record={
            "generated_tools_visible": ["prepare_reminder_creation_args"],
            "generated_tools_called": ["prepare_reminder_creation_args"],
            "generated_tools_attempted": ["prepare_reminder_creation_args"],
            "generated_tools_failed": [],
        },
        side_effect_failures=["prepare_reminder_creation_args"],
    )
    controller.assert_fresh_control_complete(
        ("add_reminder_content_and_week_delta_and_time",)
    )

    lifecycle = json.loads(
        (tmp_path / "registry" / "tool_lifecycle.json").read_text(encoding="utf-8")
    )
    decision = lifecycle["tool_lifecycle"]["prepare_reminder_creation_args"]
    assert decision["decision"] == "retain_with_safety_audit"
    assert decision["side_effect_incident_count"] == 1

    actions = [
        json.loads(line)
        for line in (tmp_path / "run" / "self_evolution_tool_lifecycle.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert actions == [
        {
            "tool_name": "prepare_reminder_creation_args",
            "decision": "needs_safety_audit",
            "reason": "side_effect_preservation_audit",
            "scenario": "add_reminder_content_and_week_delta_and_time",
        }
    ]


def test_reflection_keeps_neutral_tool_with_side_effect_audit(
    tmp_path: Path,
) -> None:
    controller = _controller(
        tmp_path,
        {
            "name": "add_reminder_content_and_date_and_time",
            "similarity": 1.0,
            "outcome_similarity": 1.0,
        },
    )

    controller.assess_scenario(
        scenario_name="add_reminder_content_and_date_and_time",
        result={"similarity": 1.0, "outcome_similarity": 1.0},
        selection_record={
            "generated_tools_visible": ["prepare_reminder_creation_args"],
            "generated_tools_called": ["prepare_reminder_creation_args"],
            "generated_tools_attempted": ["prepare_reminder_creation_args"],
            "generated_tools_failed": [],
        },
        side_effect_failures=["prepare_reminder_creation_args"],
    )
    controller.assert_fresh_control_complete(
        ("add_reminder_content_and_date_and_time",)
    )

    lifecycle = json.loads(
        (tmp_path / "registry" / "tool_lifecycle.json").read_text(encoding="utf-8")
    )
    decision = lifecycle["tool_lifecycle"]["prepare_reminder_creation_args"]
    assert decision["decision"] == "retain_with_safety_audit"
    assert (
        decision["decision_reason"] == "positive_called_subset_with_side_effect_audit"
    )
    assert decision["side_effect_incident_count"] == 1


def test_strict_reflection_uses_exact_same_run_control_without_cache(
    tmp_path: Path,
) -> None:
    scenario_name = "search_phone_number_with_name"
    controller = SelfEvolutionReflectionController.from_env(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=tmp_path / "run",
        fresh_control_channel=_fresh_control_queue(
            {
                "name": scenario_name,
                "similarity": 0.25,
                "outcome_similarity": 0.5,
            }
        ),
    )

    controller.assess_scenario(
        scenario_name=scenario_name,
        result={"similarity": 0.75, "outcome_similarity": 1.0},
        selection_record={
            "generated_tools_visible": [],
            "generated_tools_called": [],
            "generated_tools_attempted": [],
            "generated_tools_failed": [],
        },
        side_effect_failures=[],
    )
    controller.assert_fresh_control_complete((scenario_name,))

    feedback = json.loads(
        (tmp_path / "run" / "self_evolution_task_feedback.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    assert not hasattr(controller, "control_cache")
    assert feedback["control_source"] == "same_run_fresh"
    assert feedback["control_score"] == 0.25
    assert feedback["control_outcome"] == 0.5
    assert feedback["score_delta"] == 0.5
    assert feedback["outcome_delta"] == 0.5
    assert feedback["control_cache_hit"] is False


def test_strict_reflection_rejects_duplicate_fresh_control_use(
    tmp_path: Path,
) -> None:
    scenario_name = "search_phone_number_with_name"
    controller = _controller(
        tmp_path,
        {
            "name": scenario_name,
            "similarity": 0.25,
            "outcome_similarity": 0.5,
        },
    )
    kwargs = {
        "scenario_name": scenario_name,
        "result": {"similarity": 0.75, "outcome_similarity": 1.0},
        "selection_record": {},
        "side_effect_failures": [],
    }

    controller.assess_scenario(**kwargs)
    with pytest.raises(ValueError, match="Duplicate same-run fresh control"):
        controller.assess_scenario(**kwargs)


def test_reflection_uses_paper_feedback_signal_not_reporting_outcome(
    tmp_path: Path,
) -> None:
    scenario_name = "search_phone_number_with_name"
    controller = _controller(
        tmp_path,
        {
            "name": scenario_name,
            "similarity": 0.25,
            "outcome_similarity": 1.0,
            "online_feedback_outcome_similarity": 0.25,
        },
    )

    controller.assess_scenario(
        scenario_name=scenario_name,
        result={
            "similarity": 0.75,
            "outcome_similarity": 0.0,
            "online_feedback_outcome_similarity": 0.75,
        },
        selection_record={},
        side_effect_failures=[],
    )

    feedback = json.loads(
        (tmp_path / "run" / "self_evolution_task_feedback.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    assert feedback["control_outcome"] == 0.25
    assert feedback["control_outcome_source"] == "paper_era_online_feedback"
    assert feedback["candidate_outcome"] == 0.75
    assert feedback["candidate_outcome_source"] == "paper_era_online_feedback"
    assert feedback["outcome_delta"] == 0.5


def test_reflection_records_audited_fallback_outcome_sources(tmp_path: Path) -> None:
    scenario_name = "search_phone_number_with_name"
    controller = _controller(
        tmp_path,
        {
            "name": scenario_name,
            "similarity": 0.25,
            "outcome_similarity": 0.25,
            "online_feedback_outcome_similarity": None,
        },
    )

    controller.assess_scenario(
        scenario_name=scenario_name,
        result={
            "similarity": 0.75,
            "outcome_similarity": 0.75,
            "online_feedback_outcome_similarity": None,
        },
        selection_record={},
        side_effect_failures=[],
    )

    feedback = json.loads(
        (tmp_path / "run" / "self_evolution_task_feedback.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    assert feedback["control_outcome"] == 0.25
    assert feedback["control_outcome_source"] == "audited_outcome_fallback"
    assert feedback["candidate_outcome"] == 0.75
    assert feedback["candidate_outcome_source"] == "audited_outcome_fallback"
    assert feedback["outcome_delta"] == 0.5


def test_reflection_records_unavailable_outcome_sources(tmp_path: Path) -> None:
    scenario_name = "search_phone_number_with_name"
    controller = _controller(
        tmp_path,
        {
            "name": scenario_name,
            "similarity": 0.25,
            "outcome_similarity": None,
            "online_feedback_outcome_similarity": None,
        },
    )

    controller.assess_scenario(
        scenario_name=scenario_name,
        result={
            "similarity": 0.75,
            "outcome_similarity": None,
            "online_feedback_outcome_similarity": None,
        },
        selection_record={},
        side_effect_failures=[],
    )

    feedback = json.loads(
        (tmp_path / "run" / "self_evolution_task_feedback.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    assert feedback["control_outcome"] is None
    assert feedback["control_outcome_source"] == "unavailable"
    assert feedback["candidate_outcome"] is None
    assert feedback["candidate_outcome_source"] == "unavailable"
    assert feedback["outcome_delta"] is None


def test_strict_reflection_consumes_ordered_streamed_control_rows(
    tmp_path: Path,
) -> None:
    scenario_name = "search_phone_number_with_name"
    channel: Queue[dict[str, object]] = Queue()
    channel.put(
        {
            "event": "fresh_control_row",
            "scenario": scenario_name,
            "row": {
                "name": scenario_name,
                "similarity": 0.25,
                "outcome_similarity": 0.5,
                "online_feedback_outcome_similarity": 0.5,
                "llm_cached_call_count": 0,
            },
        }
    )
    channel.put({"event": "fresh_control_complete", "scenario_count": 1})
    controller = SelfEvolutionReflectionController.from_env(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=tmp_path / "run",
        fresh_control_channel=channel,
    )

    controller.assess_scenario(
        scenario_name=scenario_name,
        result={
            "similarity": 0.75,
            "outcome_similarity": 1.0,
            "online_feedback_outcome_similarity": 1.0,
        },
        selection_record={},
        side_effect_failures=[],
    )
    controller.assert_fresh_control_complete((scenario_name,))

    assert controller.fresh_control_stream_complete is True
    assert controller.fresh_control_consumed == {scenario_name}
