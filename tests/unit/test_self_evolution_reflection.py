import json
from pathlib import Path
from queue import Empty, Queue

import pytest

from sage_ts.orchestration.self_evolution_reflection import (
    FRESH_CONTROL_COMPLETE_EVENT,
    FRESH_CONTROL_ERROR_EVENT,
    FRESH_CONTROL_ROW_EVENT,
    FRESH_CONTROL_WAIT_TIMEOUT_SECONDS,
    SelfEvolutionReflectionController,
)
from sage_ts.registry.store import RegistryStore
from sage_ts.runtime.base_toolset import UPSTREAM_POLICY
from tool_sandbox.common.execution_context import ExecutionContext
from tool_sandbox.common.scenario import Scenario


def _scenario() -> Scenario:
    return Scenario(starting_context=ExecutionContext())


def test_reflection_records_off_track_pulse_without_stopping(tmp_path: Path) -> None:
    scenario_name = "search_phone_number_with_name"
    controller = _outcome_only_controller(
        tmp_path,
        scenario_name=scenario_name,
        control_similarity=1.0,
        control_outcome=1.0,
    )

    controller.assess_scenario(
        scenario_name=scenario_name,
        baseline_scenario=_scenario(),
        result={"similarity": 0.0, "outcome_similarity": 0.0},
        selection_record={
            "generated_tools_visible": [],
            "generated_tools_called": [],
            "generated_tools_attempted": [],
            "generated_tools_failed": [],
        },
        side_effect_failures=[],
    )

    state = json.loads(
        (tmp_path / "run" / "self_evolution_reflection_state.json").read_text(
            encoding="utf-8"
        )
    )
    feedback = json.loads(
        (tmp_path / "run" / "self_evolution_task_feedback.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    assert state["completed_count"] == 1
    assert state["cache_hits"] == 0
    assert state["runtime_exceptions"] == 0
    assert feedback["exception_type"] is None


def test_reflection_propagates_runtime_exception_to_feedback_and_state(
    tmp_path: Path,
) -> None:
    scenario_name = "runtime_failure"
    controller = _outcome_only_controller(
        tmp_path,
        scenario_name=scenario_name,
        control_similarity=1.0,
        control_outcome=1.0,
    )

    controller.assess_scenario(
        scenario_name=scenario_name,
        baseline_scenario=_scenario(),
        result={
            "similarity": 0.0,
            "outcome_similarity": 0.0,
            "exception_type": "RuntimeError",
        },
        selection_record={},
        side_effect_failures=[],
    )

    feedback = json.loads(
        (tmp_path / "run" / "self_evolution_task_feedback.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    state = json.loads(
        (tmp_path / "run" / "self_evolution_reflection_state.json").read_text(
            encoding="utf-8"
        )
    )

    assert controller.runtime_exceptions == 1
    assert feedback["exception_type"] == "RuntimeError"
    assert state["runtime_exceptions"] == 1
    assert "runtime_exceptions_present" in state["last_pulse"]["off_track_reasons"]


def test_reflection_flags_sparse_positive_tool(tmp_path: Path) -> None:
    scenario_name = "update_contact_relationship_with_relationship"
    controller = _outcome_only_controller(
        tmp_path,
        scenario_name=scenario_name,
        control_similarity=0.0,
        control_outcome=0.0,
    )

    controller.assess_scenario(
        scenario_name=scenario_name,
        baseline_scenario=_scenario(),
        result={"similarity": 1.0, "outcome_similarity": 1.0},
        selection_record={
            "generated_tools_visible": ["plan_contact_relationship_batch_update"],
            "generated_tools_called": ["plan_contact_relationship_batch_update"],
            "generated_tools_attempted": ["plan_contact_relationship_batch_update"],
            "generated_tools_failed": [],
        },
        side_effect_failures=[],
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
    scenario_name = "add_reminder_content_and_week_delta_and_time"
    controller = _outcome_only_controller(
        tmp_path,
        scenario_name=scenario_name,
        control_similarity=1.0,
        control_outcome=1.0,
    )

    controller.assess_scenario(
        scenario_name=scenario_name,
        baseline_scenario=_scenario(),
        result={"similarity": 0.25, "outcome_similarity": 0.0},
        selection_record={
            "generated_tools_visible": ["relative_day_time_to_timestamp"],
            "generated_tools_called": ["relative_day_time_to_timestamp"],
            "generated_tools_attempted": ["relative_day_time_to_timestamp"],
            "generated_tools_failed": [],
        },
        side_effect_failures=[],
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
    scenario_name = "add_reminder_content_and_week_delta_and_time"
    controller = _outcome_only_controller(
        tmp_path,
        scenario_name=scenario_name,
        control_similarity=0.0,
        control_outcome=0.0,
    )

    controller.assess_scenario(
        scenario_name=scenario_name,
        baseline_scenario=_scenario(),
        result={"similarity": 1.0, "outcome_similarity": 1.0},
        selection_record={
            "generated_tools_visible": ["prepare_reminder_creation_args"],
            "generated_tools_called": ["prepare_reminder_creation_args"],
            "generated_tools_attempted": ["prepare_reminder_creation_args"],
            "generated_tools_failed": [],
        },
        side_effect_failures=["prepare_reminder_creation_args"],
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
    scenario_name = "add_reminder_content_and_date_and_time"
    controller = _outcome_only_controller(
        tmp_path,
        scenario_name=scenario_name,
        control_similarity=1.0,
        control_outcome=1.0,
    )

    controller.assess_scenario(
        scenario_name=scenario_name,
        baseline_scenario=_scenario(),
        result={"similarity": 1.0, "outcome_similarity": 1.0},
        selection_record={
            "generated_tools_visible": ["prepare_reminder_creation_args"],
            "generated_tools_called": ["prepare_reminder_creation_args"],
            "generated_tools_attempted": ["prepare_reminder_creation_args"],
            "generated_tools_failed": [],
        },
        side_effect_failures=["prepare_reminder_creation_args"],
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


def test_reflection_hydrates_feedback_on_resume(tmp_path: Path) -> None:
    first_scenario = "search_message_with_recency_latest"
    second_scenario = "search_message_with_recency_oldest"
    output_dir = tmp_path / "run"
    output_dir.mkdir()
    prior_feedback = {
        "event": "self_evolution_task_assessed",
        "scenario": first_scenario,
        "base_family": first_scenario,
        "completed_count": 1,
        "control_source": "same_run_fresh",
        "control_cache_eligible": False,
        "control_cache_hit": False,
        "control_score": 0.0,
        "candidate_score": 1.0,
        "score_delta": 1.0,
        "control_outcome": 0.0,
        "candidate_outcome": 1.0,
        "outcome_delta": 1.0,
        "generated_tools_visible": ["select_message_content_by_recency"],
        "generated_tools_called": ["select_message_content_by_recency"],
        "generated_tools_attempted": ["select_message_content_by_recency"],
        "generated_tools_failed": [],
        "side_effect_failures": [],
    }
    (output_dir / "self_evolution_task_feedback.jsonl").write_text(
        json.dumps(prior_feedback) + "\n",
        encoding="utf-8",
    )
    controller = SelfEvolutionReflectionController(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=output_dir,
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        fresh_control_rows={
            first_scenario: {
                "name": first_scenario,
                "similarity": 0.0,
                "outcome_similarity": 0.0,
            },
            second_scenario: {
                "name": second_scenario,
                "similarity": 0.0,
                "outcome_similarity": 0.0,
            },
        },
        require_fresh_control=True,
        pulse_interval=2,
        min_pulse_tasks=1,
    )

    controller._hydrate_from_existing_feedback()
    assert controller.completed_count == 1
    assert controller.cache_hit_count == 0

    controller.assess_scenario(
        scenario_name=second_scenario,
        baseline_scenario=_scenario(),
        result={"similarity": 1.0, "outcome_similarity": 1.0},
        selection_record={
            "generated_tools_visible": ["select_message_content_by_recency"],
            "generated_tools_called": ["select_message_content_by_recency"],
            "generated_tools_attempted": ["select_message_content_by_recency"],
            "generated_tools_failed": [],
        },
        side_effect_failures=[],
    )

    lifecycle = json.loads(
        (tmp_path / "registry" / "tool_lifecycle.json").read_text(encoding="utf-8")
    )
    stats = lifecycle["tool_lifecycle"]["select_message_content_by_recency"]
    assert stats["called_count"] == 2
    assert stats["decision"] == "retain"


def test_strict_reflection_uses_exact_same_run_control_without_cache(
    tmp_path: Path,
) -> None:
    scenario_name = "search_phone_number_with_name"
    controller = SelfEvolutionReflectionController.from_env(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=tmp_path / "run",
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        fresh_control_rows={
            scenario_name: {
                "name": scenario_name,
                "similarity": 0.25,
                "outcome_similarity": 0.5,
                "llm_cached_call_count": 0,
            }
        },
        require_fresh_control=True,
    )

    controller.assess_scenario(
        scenario_name=scenario_name,
        baseline_scenario=_scenario(),
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
    controller = SelfEvolutionReflectionController(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=tmp_path / "run",
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        fresh_control_rows={
            scenario_name: {
                "name": scenario_name,
                "similarity": 0.25,
                "outcome_similarity": 0.5,
            }
        },
        require_fresh_control=True,
    )
    kwargs = {
        "scenario_name": scenario_name,
        "baseline_scenario": _scenario(),
        "result": {"similarity": 0.75, "outcome_similarity": 1.0},
        "selection_record": {},
        "side_effect_failures": [],
    }

    controller.assess_scenario(**kwargs)
    with pytest.raises(ValueError, match="Duplicate same-run fresh control"):
        controller.assess_scenario(**kwargs)


def _outcome_only_controller(
    tmp_path: Path,
    *,
    scenario_name: str,
    control_similarity: float,
    control_outcome: float | None,
) -> SelfEvolutionReflectionController:
    return SelfEvolutionReflectionController(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=tmp_path / "run",
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        fresh_control_rows={
            scenario_name: {
                "name": scenario_name,
                "similarity": control_similarity,
                "outcome_similarity": control_outcome,
            }
        },
        require_fresh_control=True,
        pulse_interval=1,
        min_pulse_tasks=1,
    )


def test_reflection_lifecycle_ignores_canonical_regression_when_outcome_improves(
    tmp_path: Path,
) -> None:
    scenario_name = "outcome_improvement"
    controller = _outcome_only_controller(
        tmp_path,
        scenario_name=scenario_name,
        control_similarity=1.0,
        control_outcome=0.0,
    )

    controller.assess_scenario(
        scenario_name=scenario_name,
        baseline_scenario=_scenario(),
        result={"similarity": 0.0, "outcome_similarity": 1.0},
        selection_record={
            "generated_tools_visible": ["helper"],
            "generated_tools_called": ["helper"],
            "generated_tools_attempted": ["helper"],
            "generated_tools_failed": [],
        },
        side_effect_failures=[],
    )

    lifecycle = json.loads(
        (tmp_path / "registry" / "tool_lifecycle.json").read_text(encoding="utf-8")
    )["tool_lifecycle"]["helper"]
    assert lifecycle["called_score_delta_mean"] == -1.0
    assert lifecycle["called_outcome_delta_mean"] == 1.0
    assert lifecycle["decision"] == "keep_sparse_positive"
    assert lifecycle["harmful_called_count"] == 0


def test_reflection_lifecycle_uses_outcome_regression_despite_canonical_gain(
    tmp_path: Path,
) -> None:
    scenario_name = "outcome_regression"
    controller = _outcome_only_controller(
        tmp_path,
        scenario_name=scenario_name,
        control_similarity=0.0,
        control_outcome=1.0,
    )

    controller.assess_scenario(
        scenario_name=scenario_name,
        baseline_scenario=_scenario(),
        result={"similarity": 1.0, "outcome_similarity": 0.0},
        selection_record={
            "generated_tools_visible": ["helper"],
            "generated_tools_called": ["helper"],
            "generated_tools_attempted": ["helper"],
            "generated_tools_failed": [],
        },
        side_effect_failures=[],
    )

    lifecycle = json.loads(
        (tmp_path / "registry" / "tool_lifecycle.json").read_text(encoding="utf-8")
    )["tool_lifecycle"]["helper"]
    assert lifecycle["called_score_delta_mean"] == 1.0
    assert lifecycle["called_outcome_delta_mean"] == -1.0
    assert lifecycle["decision"] == "needs_route_repair"
    assert lifecycle["harmful_called_count"] == 1


def test_reflection_pulse_does_not_accept_canonical_gain_without_outcome_lift(
    tmp_path: Path,
) -> None:
    scenario_name = "neutral_outcome"
    controller = _outcome_only_controller(
        tmp_path,
        scenario_name=scenario_name,
        control_similarity=0.0,
        control_outcome=1.0,
    )

    controller.assess_scenario(
        scenario_name=scenario_name,
        baseline_scenario=_scenario(),
        result={"similarity": 1.0, "outcome_similarity": 1.0},
        selection_record={},
        side_effect_failures=[],
    )

    pulse = json.loads(
        (tmp_path / "run" / "self_evolution_reflections.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    assert pulse["score_delta_mean"] == 1.0
    assert pulse["outcome_delta_mean"] == 0.0
    assert pulse["on_track"] is False
    assert pulse["off_track_reasons"] == ["pulse_lift_below_threshold"]


@pytest.mark.parametrize("missing_arm", ["control", "candidate"])
def test_reflection_requires_non_null_outcomes(
    tmp_path: Path,
    missing_arm: str,
) -> None:
    scenario_name = f"missing_{missing_arm}_outcome"
    controller = _outcome_only_controller(
        tmp_path,
        scenario_name=scenario_name,
        control_similarity=0.0,
        control_outcome=None if missing_arm == "control" else 0.0,
    )

    with pytest.raises(ValueError, match="requires non-null matched control"):
        controller.assess_scenario(
            scenario_name=scenario_name,
            baseline_scenario=_scenario(),
            result={
                "similarity": 1.0,
                "outcome_similarity": None if missing_arm == "candidate" else 1.0,
            },
            selection_record={},
            side_effect_failures=[],
        )


def test_resumed_reflection_ignores_changed_canonical_value_when_outcome_matches(
    tmp_path: Path,
) -> None:
    scenario_name = "resumed_task"
    output_dir = tmp_path / "run"
    output_dir.mkdir()
    feedback = {
        "event": "self_evolution_task_assessed",
        "scenario": scenario_name,
        "control_source": "same_run_fresh",
        "control_cache_eligible": False,
        "control_cache_hit": False,
        "control_score": 0.0,
        "candidate_score": 1.0,
        "score_delta": 1.0,
        "control_outcome": 0.5,
        "candidate_outcome": 1.0,
        "outcome_delta": 0.5,
        "generated_tools_visible": [],
        "generated_tools_called": [],
        "generated_tools_attempted": [],
        "generated_tools_failed": [],
        "side_effect_failures": [],
    }
    (output_dir / "self_evolution_task_feedback.jsonl").write_text(
        json.dumps(feedback) + "\n",
        encoding="utf-8",
    )

    controller = SelfEvolutionReflectionController.from_env(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=output_dir,
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        fresh_control_rows={
            scenario_name: {
                "name": scenario_name,
                "similarity": 1.0,
                "outcome_similarity": 0.5,
            }
        },
        require_fresh_control=True,
    )

    assert controller.completed_count == 1
    assert controller.fresh_control_consumed == {scenario_name}


def _streamed_control_row(
    scenario_name: str,
    *,
    similarity: float = 0.25,
    outcome_similarity: float = 0.5,
) -> dict[str, object]:
    return {
        "event": FRESH_CONTROL_ROW_EVENT,
        "scenario": scenario_name,
        "row": {
            "name": scenario_name,
            "similarity": similarity,
            "outcome_similarity": outcome_similarity,
            "llm_cached_call_count": 0,
        },
    }


def _streaming_controller(
    tmp_path: Path,
    channel: Queue[object],
) -> SelfEvolutionReflectionController:
    return SelfEvolutionReflectionController.from_env(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=tmp_path / "run",
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        require_fresh_control=True,
        fresh_control_channel=channel,
    )


def test_strict_streamed_reflection_consumes_exact_row_and_terminal(
    tmp_path: Path,
) -> None:
    scenario_name = "search_phone_number_with_name"
    channel: Queue[object] = Queue()
    channel.put(_streamed_control_row(scenario_name))
    channel.put({"event": FRESH_CONTROL_COMPLETE_EVENT})

    controller = _streaming_controller(tmp_path, channel)
    controller.assess_scenario(
        scenario_name=scenario_name,
        baseline_scenario=_scenario(),
        result={"similarity": 0.75, "outcome_similarity": 1.0},
        selection_record={},
        side_effect_failures=[],
    )
    controller.assert_fresh_control_complete((scenario_name,))

    feedback = json.loads(
        (tmp_path / "run" / "self_evolution_task_feedback.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    assert controller.fresh_control_stream_complete is True
    assert controller.fresh_control_consumed == {scenario_name}
    assert feedback["control_source"] == "same_run_fresh"
    assert feedback["control_score"] == 0.25
    assert feedback["control_outcome"] == 0.5


@pytest.mark.parametrize(
    ("message", "match"),
    [
        (
            {"event": FRESH_CONTROL_ERROR_EVENT, "error": "control crashed"},
            "producer failed: control crashed",
        ),
        (
            _streamed_control_row("unexpected_task"),
            "Out-of-order streamed same-run fresh control",
        ),
        (
            {"event": FRESH_CONTROL_COMPLETE_EVENT},
            "Missing streamed same-run fresh control observation",
        ),
        (
            {
                **_streamed_control_row("expected_task"),
                "row": {
                    "name": "expected_task",
                    "similarity": 1.0,
                    "outcome_similarity": 1.0,
                    "llm_cached_call_count": 1,
                },
            },
            "contains repository whole-response replay",
        ),
    ],
)
def test_strict_streamed_reflection_fails_closed_before_expected_row(
    tmp_path: Path,
    message: dict[str, object],
    match: str,
) -> None:
    channel: Queue[object] = Queue()
    channel.put(message)
    controller = _streaming_controller(tmp_path, channel)

    with pytest.raises(ValueError, match=match):
        controller.assess_scenario(
            scenario_name="expected_task",
            baseline_scenario=_scenario(),
            result={"similarity": 1.0, "outcome_similarity": 1.0},
            selection_record={},
            side_effect_failures=[],
        )


def test_strict_streamed_reflection_rejects_duplicate_row_message(
    tmp_path: Path,
) -> None:
    channel: Queue[object] = Queue()
    channel.put(_streamed_control_row("task_a"))
    channel.put(_streamed_control_row("task_a"))
    controller = _streaming_controller(tmp_path, channel)
    common = {
        "baseline_scenario": _scenario(),
        "result": {"similarity": 1.0, "outcome_similarity": 1.0},
        "selection_record": {},
        "side_effect_failures": [],
    }

    controller.assess_scenario(scenario_name="task_a", **common)
    with pytest.raises(ValueError, match="Duplicate streamed same-run fresh control"):
        controller.assess_scenario(scenario_name="task_b", **common)


def test_strict_streamed_reflection_requires_terminal_after_exact_rows(
    tmp_path: Path,
) -> None:
    channel: Queue[object] = Queue()
    channel.put(_streamed_control_row("task_a"))
    channel.put(_streamed_control_row("unexpected_extra"))
    controller = _streaming_controller(tmp_path, channel)
    controller.assess_scenario(
        scenario_name="task_a",
        baseline_scenario=_scenario(),
        result={"similarity": 1.0, "outcome_similarity": 1.0},
        selection_record={},
        side_effect_failures=[],
    )

    with pytest.raises(
        ValueError, match="Unexpected streamed same-run fresh control row"
    ):
        controller.assert_fresh_control_complete(("task_a",))


def test_strict_streamed_reflection_timeout_fails_closed_immediately(
    tmp_path: Path,
) -> None:
    observed_timeouts: list[float] = []

    class ImmediatelyEmptyChannel:
        def get(self, *, timeout: float) -> object:
            observed_timeouts.append(timeout)
            raise Empty

    controller = _streaming_controller(
        tmp_path,
        ImmediatelyEmptyChannel(),  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="Timed out waiting.*'missing_task'"):
        controller.assess_scenario(
            scenario_name="missing_task",
            baseline_scenario=_scenario(),
            result={"similarity": 1.0, "outcome_similarity": 1.0},
            selection_record={},
            side_effect_failures=[],
        )
    assert observed_timeouts == [FRESH_CONTROL_WAIT_TIMEOUT_SECONDS]
