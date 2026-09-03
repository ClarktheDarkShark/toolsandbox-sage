import json
from pathlib import Path

import pytest

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


@pytest.fixture(autouse=True)
def _single_record_legacy_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAGE_CONTROL_CACHE_MIN_COMPATIBLE_RUNS", "1")


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
    cache.add_record(
        context=context,
        result_row=row,
        run_dir=run_dir,
        manifest_path=manifest,
    )


def test_reflection_records_off_track_pulse_without_stopping(tmp_path: Path) -> None:
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
    )

    controller.assess_scenario(
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


def test_reflection_keeps_positive_tool_with_side_effect_audit(
    tmp_path: Path,
) -> None:
    scenario = _scenario()
    cache = ControlBaselineCache(tmp_path / "cache")
    _add_cached_baseline(
        cache,
        tmp_path,
        name="add_reminder_content_and_week_delta_and_time",
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
    )

    controller.assess_scenario(
        scenario_name="add_reminder_content_and_week_delta_and_time",
        baseline_scenario=scenario,
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
    scenario = _scenario()
    cache = ControlBaselineCache(tmp_path / "cache")
    _add_cached_baseline(
        cache,
        tmp_path,
        name="add_reminder_content_and_date_and_time",
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
    )

    controller.assess_scenario(
        scenario_name="add_reminder_content_and_date_and_time",
        baseline_scenario=scenario,
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
    )

    controller._hydrate_from_existing_feedback()
    assert controller.completed_count == 1
    assert controller.cache_hit_count == 1

    controller.assess_scenario(
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

    lifecycle = json.loads(
        (tmp_path / "registry" / "tool_lifecycle.json").read_text(encoding="utf-8")
    )
    stats = lifecycle["tool_lifecycle"]["select_message_content_by_recency"]
    assert stats["called_count"] == 2
    assert stats["decision"] == "retain"


def test_strict_reflection_uses_exact_same_run_control_without_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario_name = "search_phone_number_with_name"

    def fail_cache_construction(*_args: object, **_kwargs: object) -> None:
        pytest.fail("strict fresh-control reflection constructed ControlBaselineCache")

    monkeypatch.setattr(
        "sage_ts.orchestration.self_evolution_reflection.ControlBaselineCache",
        fail_cache_construction,
    )
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
    assert controller.control_cache is None
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
        control_cache=None,
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
