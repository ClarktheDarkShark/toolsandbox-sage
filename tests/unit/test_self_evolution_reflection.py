import json
from pathlib import Path

from sage_ts.evaluation.control_baseline_cache import (
    ControlBaselineCache,
    compatibility_context,
)
from sage_ts.orchestration.self_evolution_reflection import (
    SelfEvolutionReflectionController,
)
from sage_ts.registry.store import RegistryStore
from sage_ts.runtime.base_toolset import UPSTREAM_POLICY
from tool_sandbox.common.execution_context import ExecutionContext
from tool_sandbox.common.scenario import Scenario


def _scenario() -> Scenario:
    return Scenario(starting_context=ExecutionContext())


def _add_cached_baseline(
    cache: ControlBaselineCache,
    tmp_path: Path,
    *,
    name: str,
    scenario: Scenario,
    score: float,
    outcome: float,
) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    run_dir = tmp_path / "control_run"
    trajectory_dir = run_dir / "trajectories" / name
    trajectory_dir.mkdir(parents=True, exist_ok=True)
    (trajectory_dir / "conversation.json").write_text("[]\n", encoding="utf-8")
    (trajectory_dir / "execution_context.json").write_text("{}\n", encoding="utf-8")
    context = compatibility_context(
        scenario_key=name,
        scenario=scenario,
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=manifest,
    )
    row = {
        "name": name,
        "categories": [],
        "traceback": None,
        "exception_type": None,
        "milestone_similarity": score,
        "minefield_similarity": 0,
        "similarity": score,
        "turn_count": 4,
        "milestone_mapping": {"0": score},
        "minefield_mapping": {},
        "outcome_similarity": outcome,
        "outcome_checks": [],
    }
    for _ in range(3):
        cache.add_record(
            context=context,
            result_row=row,
            run_dir=run_dir,
            manifest_path=manifest,
        )


def test_reflection_stops_off_track_pulse(tmp_path: Path) -> None:
    scenario = _scenario()
    cache = ControlBaselineCache(tmp_path / "cache")
    _add_cached_baseline(
        cache,
        tmp_path,
        name="search_phone_number_with_name",
        scenario=scenario,
        score=1.0,
        outcome=1.0,
    )
    controller = SelfEvolutionReflectionController(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=tmp_path / "run",
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        control_cache=cache,
        pulse_interval=1,
        min_pulse_tasks=1,
        stop_if_off_track=True,
    )

    decision = controller.assess_scenario(
        scenario_name="search_phone_number_with_name",
        baseline_scenario=scenario,
        result={"similarity": 0.0, "outcome_similarity": 0.0},
        selection_record={
            "generated_tools_visible": [],
            "generated_tools_called": [],
            "generated_tools_attempted": [],
            "generated_tools_failed": [],
        },
        side_effect_failures=[],
    )

    assert decision.stop_run
    state = json.loads(
        (tmp_path / "run" / "self_evolution_reflection_state.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["completed_count"] == 1
    assert state["cache_hits"] == 1


def test_reflection_flags_sparse_positive_tool(tmp_path: Path) -> None:
    scenario = _scenario()
    cache = ControlBaselineCache(tmp_path / "cache")
    _add_cached_baseline(
        cache,
        tmp_path,
        name="update_contact_relationship_with_relationship",
        scenario=scenario,
        score=0.0,
        outcome=0.0,
    )
    controller = SelfEvolutionReflectionController(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=tmp_path / "run",
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        control_cache=cache,
        pulse_interval=1,
        min_pulse_tasks=1,
        stop_if_off_track=False,
    )

    controller.assess_scenario(
        scenario_name="update_contact_relationship_with_relationship",
        baseline_scenario=scenario,
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
    scenario = _scenario()
    cache = ControlBaselineCache(tmp_path / "cache")
    _add_cached_baseline(
        cache,
        tmp_path,
        name="add_reminder_content_and_week_delta_and_time",
        scenario=scenario,
        score=1.0,
        outcome=1.0,
    )
    controller = SelfEvolutionReflectionController(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=tmp_path / "run",
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        control_cache=cache,
        pulse_interval=1,
        min_pulse_tasks=1,
        stop_if_off_track=False,
    )

    controller.assess_scenario(
        scenario_name="add_reminder_content_and_week_delta_and_time",
        baseline_scenario=scenario,
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


def test_reflection_hydrates_feedback_on_resume(tmp_path: Path) -> None:
    scenario = _scenario()
    cache = ControlBaselineCache(tmp_path / "cache")
    _add_cached_baseline(
        cache,
        tmp_path,
        name="search_message_with_recency_latest",
        scenario=scenario,
        score=0.0,
        outcome=0.0,
    )
    _add_cached_baseline(
        cache,
        tmp_path,
        name="search_message_with_recency_oldest",
        scenario=scenario,
        score=0.0,
        outcome=0.0,
    )
    output_dir = tmp_path / "run"
    output_dir.mkdir()
    prior_feedback = {
        "event": "self_evolution_task_assessed",
        "scenario": "search_message_with_recency_latest",
        "base_family": "search_message_with_recency_latest",
        "completed_count": 1,
        "control_cache_eligible": True,
        "control_cache_hit": True,
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
        control_cache=cache,
        pulse_interval=2,
        min_pulse_tasks=1,
        stop_if_off_track=False,
    )

    controller._hydrate_from_existing_feedback()
    assert controller.completed_count == 1
    assert controller.cache_hit_count == 1

    decision = controller.assess_scenario(
        scenario_name="search_message_with_recency_oldest",
        baseline_scenario=scenario,
        result={"similarity": 1.0, "outcome_similarity": 1.0},
        selection_record={
            "generated_tools_visible": ["select_message_content_by_recency"],
            "generated_tools_called": ["select_message_content_by_recency"],
            "generated_tools_attempted": ["select_message_content_by_recency"],
            "generated_tools_failed": [],
        },
        side_effect_failures=[],
    )

    assert not decision.stop_run
    lifecycle = json.loads(
        (tmp_path / "registry" / "tool_lifecycle.json").read_text(encoding="utf-8")
    )
    stats = lifecycle["tool_lifecycle"]["select_message_content_by_recency"]
    assert stats["called_count"] == 2
    assert stats["decision"] == "retain"
