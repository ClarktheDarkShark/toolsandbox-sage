import json
from pathlib import Path
from queue import Queue

import pytest

from sage_ts.evaluation.control_baseline_cache import (
    ControlBaselineCache,
    compatibility_context,
)
from sage_ts.orchestration.self_evolution_reflection import (
    SelfEvolutionReflectionController,
    _online_feedback_outcome,
    _online_feedback_outcome_with_source,
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


@pytest.mark.parametrize(
    ("row", "expected", "expected_source"),
    [
        pytest.param(
            {
                "outcome_similarity": 0.75,
                "online_feedback_outcome_similarity": None,
            },
            0.75,
            "audited_outcome",
            id="audited-outcome-with-null-legacy-diagnostic",
        ),
        pytest.param(
            {"outcome_similarity": 0.75},
            0.75,
            "audited_outcome",
            id="audited-outcome-without-legacy-diagnostic",
        ),
        pytest.param(
            {
                "outcome_similarity": 0.75,
                "online_feedback_outcome_similarity": 0.0,
            },
            0.75,
            "audited_outcome",
            id="audited-outcome-wins-over-zero-legacy-diagnostic",
        ),
        pytest.param(
            {
                "outcome_similarity": 0.25,
                "online_feedback_outcome_similarity": 0.75,
            },
            0.25,
            "audited_outcome",
            id="audited-outcome-wins-over-nonzero-legacy-diagnostic",
        ),
        pytest.param(
            {
                "outcome_similarity": None,
                "online_feedback_outcome_similarity": 0.75,
            },
            None,
            "unavailable",
            id="legacy-diagnostic-never-fills-missing-audited-outcome",
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
    assert _online_feedback_outcome(row) == expected
    assert _online_feedback_outcome_with_source(row) == (expected, expected_source)


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


def test_reflection_reports_outcome_only_shortfall_without_repairing_co_called_tools(
    tmp_path: Path,
) -> None:
    scenario_names = tuple(f"private_benchmark_case_{index}" for index in range(3))
    controller = SelfEvolutionReflectionController(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=tmp_path / "run",
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        control_cache=None,
        fresh_control_rows={
            name: {
                "name": name,
                "similarity": 0.0,
                "outcome_similarity": 0.0,
            }
            for name in scenario_names
        },
        require_fresh_control=True,
        pulse_interval=1,
        min_outcome_diagnostic_calls=3,
    )

    last_feedback: dict[str, object] = {}
    for scenario_name in scenario_names:
        last_feedback = controller.assess_scenario(
            scenario_name=scenario_name,
            baseline_scenario=_scenario(),
            result={"similarity": 0.25, "outcome_similarity": 0.25},
            selection_record={
                "generated_tools_visible": [
                    "generic_dependency_helper",
                    "generic_formatting_helper",
                ],
                "generated_tools_called": [
                    "generic_dependency_helper",
                    "generic_formatting_helper",
                ],
                "generated_tools_attempted": [
                    "generic_dependency_helper",
                    "generic_formatting_helper",
                ],
                "generated_tools_failed": [],
            },
            side_effect_failures=[],
            task_context_label=(
                "visible_task_context(family=dependency_resolution; "
                "signals=missing_capability; request='visible request')"
            ),
            task_family_key="dependency_resolution",
        )

    lifecycle_by_tool = json.loads(
        (tmp_path / "registry" / "tool_lifecycle.json").read_text(encoding="utf-8")
    )["tool_lifecycle"]
    for tool_name in (
        "generic_dependency_helper",
        "generic_formatting_helper",
    ):
        lifecycle = lifecycle_by_tool[tool_name]
        assert lifecycle["decision"] == "diagnostic_alarm"
        assert lifecycle["decision_reason"] == (
            "low_task_outcome_not_tool_attributable"
        )
        assert lifecycle["repair_kind"] is None
        assert lifecycle["routing_disposition"] == "unchanged"
        assert lifecycle["candidate_outcome_mean"] == 0.25
        assert lifecycle["called_outcome_delta_mean"] == 0.25
        assert lifecycle["implementation_repair_families"] == []
        assert lifecycle["outcome_shortfall_alarm_families"] == [
            "dependency_resolution"
        ]

    assert controller.drain_pending_repair_requests() == ()
    assert not controller.repair_request_path.exists()
    assert last_feedback["candidate_success_flip"] is False
    assert last_feedback["post_deployment_repair_request_ids"] == []


def test_reflection_keeps_relative_regression_as_route_repair(
    tmp_path: Path,
) -> None:
    scenario_names = tuple(f"route_case_{index}" for index in range(2))
    controller = SelfEvolutionReflectionController(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=tmp_path / "run",
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        control_cache=None,
        fresh_control_rows={
            name: {
                "name": name,
                "similarity": 1.0,
                "outcome_similarity": 1.0,
            }
            for name in scenario_names
        },
        require_fresh_control=True,
        pulse_interval=1,
        min_outcome_diagnostic_calls=2,
    )

    for scenario_name in scenario_names:
        controller.assess_scenario(
            scenario_name=scenario_name,
            baseline_scenario=_scenario(),
            result={"similarity": 0.75, "outcome_similarity": 0.75},
            selection_record={
                "generated_tools_visible": ["generic_routed_helper"],
                "generated_tools_called": ["generic_routed_helper"],
                "generated_tools_attempted": ["generic_routed_helper"],
                "generated_tools_failed": [],
            },
            side_effect_failures=[],
            task_context_label=(
                "visible_task_context(family=lookup; signals=lookup; "
                "request='visible request')"
            ),
            task_family_key="lookup",
        )

    lifecycle = json.loads(
        (tmp_path / "registry" / "tool_lifecycle.json").read_text(encoding="utf-8")
    )["tool_lifecycle"]["generic_routed_helper"]
    assert lifecycle["decision"] == "needs_route_repair"
    assert lifecycle["repair_kind"] == "routing"
    assert lifecycle["implementation_repair_families"] == []
    assert controller.drain_pending_repair_requests() == ()
    assert not controller.repair_request_path.exists()


def test_reflection_single_contract_failure_triggers_attributable_repair(
    tmp_path: Path,
) -> None:
    scenario_names = ("contract_case",)
    controller = SelfEvolutionReflectionController(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=tmp_path / "run",
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        control_cache=None,
        fresh_control_rows={
            name: {
                "name": name,
                "similarity": 0.0,
                "outcome_similarity": 0.0,
            }
            for name in scenario_names
        },
        require_fresh_control=True,
        pulse_interval=1,
    )

    for scenario_name in scenario_names:
        feedback = controller.assess_scenario(
            scenario_name=scenario_name,
            baseline_scenario=_scenario(),
            result={"similarity": 1.0, "outcome_similarity": 1.0},
            selection_record={
                "generated_tools_visible": ["generic_contract_helper"],
                "generated_tools_called": ["generic_contract_helper"],
                "generated_tools_attempted": ["generic_contract_helper"],
                "generated_tools_failed": [],
                "generated_tool_contract_failures": ["generic_contract_helper"],
            },
            side_effect_failures=[],
            task_context_label=(
                "visible_task_context(family=normalization; "
                "signals=public_contract; request='visible request')"
            ),
            task_family_key="normalization",
        )
        assert feedback["candidate_success_flip"] is True

    lifecycle = json.loads(
        (tmp_path / "registry" / "tool_lifecycle.json").read_text(encoding="utf-8")
    )["tool_lifecycle"]["generic_contract_helper"]
    assert lifecycle["decision"] == "needs_implementation_repair"
    assert lifecycle["decision_reason"] == "deterministic_public_contract_failure"
    assert lifecycle["contract_failure_count"] == 1
    assert lifecycle["success_flip_count"] == 1
    requests = controller.drain_pending_repair_requests()
    assert len(requests) == 1
    assert requests[0]["trigger_reason_codes"] == [
        "deterministic_public_contract_failure"
    ]
    assert requests[0]["public_evidence"] == {
        "called_count": 1,
        "contract_failure_count": 1,
        "failed_count": 0,
    }
    assert "post_task_scalar_outcome" not in requests[0]["evidence_policy"]["allowed"]


def test_reflection_requires_repeated_generated_tool_execution_failures(
    tmp_path: Path,
) -> None:
    scenario_names = tuple(f"execution_failure_case_{index}" for index in range(3))
    controller = SelfEvolutionReflectionController(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=tmp_path / "run",
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        control_cache=None,
        fresh_control_rows={
            name: {
                "name": name,
                "similarity": 0.5,
                "outcome_similarity": 0.5,
            }
            for name in scenario_names
        },
        require_fresh_control=True,
        pulse_interval=1,
    )

    for index, scenario_name in enumerate(scenario_names):
        feedback = controller.assess_scenario(
            scenario_name=scenario_name,
            baseline_scenario=_scenario(),
            result={"similarity": 0.5, "outcome_similarity": 0.5},
            selection_record={
                "generated_tools_visible": ["generic_runtime_helper"],
                "generated_tools_called": [],
                "generated_tools_attempted": ["generic_runtime_helper"],
                "generated_tools_failed": ["generic_runtime_helper"],
            },
            side_effect_failures=[],
            task_context_label=(
                "visible_task_context(family=runtime_transform; "
                "signals=execution; request='visible request')"
            ),
            task_family_key="runtime_transform",
        )
        expected_request_count = 1 if index == 2 else 0
        assert len(feedback["post_deployment_repair_request_ids"]) == (
            expected_request_count
        )

    lifecycle = json.loads(
        (tmp_path / "registry" / "tool_lifecycle.json").read_text(encoding="utf-8")
    )["tool_lifecycle"]["generic_runtime_helper"]
    assert lifecycle["decision"] == "needs_implementation_repair"
    assert lifecycle["decision_reason"] == ("repeated_generated_tool_execution_failure")
    assert lifecycle["failed_count"] == 3
    assert lifecycle["candidate_outcome_observation_count"] == 0

    requests = controller.drain_pending_repair_requests()
    assert len(requests) == 1
    request = requests[0]
    assert request["trigger_reason_codes"] == [
        "repeated_generated_tool_execution_failure"
    ]
    assert request["public_evidence"] == {
        "called_count": 0,
        "contract_failure_count": 0,
        "failed_count": 3,
    }


def test_generic_task_exception_does_not_retire_called_generated_tool(
    tmp_path: Path,
) -> None:
    scenario_name = "actor_failed_after_successful_tool_call"
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
                "similarity": 0.0,
                "outcome_similarity": 0.0,
            }
        },
        require_fresh_control=True,
        pulse_interval=1,
    )

    feedback = controller.assess_scenario(
        scenario_name=scenario_name,
        baseline_scenario=_scenario(),
        result={
            "similarity": 0.0,
            "outcome_similarity": 0.0,
            "exception_type": "RuntimeError",
        },
        selection_record={
            "generated_tools_visible": ["successful_helper"],
            "generated_tools_called": ["successful_helper"],
            "generated_tools_attempted": ["successful_helper"],
            "generated_tools_failed": [],
        },
        side_effect_failures=[],
        task_context_label="visible_task_context(family=generic_actor_failure)",
        task_family_key="generic_actor_failure",
    )

    assert feedback["immediate_actions"] == []
    assert controller.retired_this_run == set()
    assert controller.drain_pending_repair_requests() == ()
    lifecycle = json.loads(
        (tmp_path / "registry" / "tool_lifecycle.json").read_text(encoding="utf-8")
    )["tool_lifecycle"]["successful_helper"]
    assert lifecycle["decision"] == "diagnostic"
    assert lifecycle["implementation_repair_families"] == []


def test_three_execution_failures_across_families_trigger_one_global_repair(
    tmp_path: Path,
) -> None:
    scenario_names = tuple(f"cross_family_failure_{index}" for index in range(3))
    controller = SelfEvolutionReflectionController(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=tmp_path / "run",
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        control_cache=None,
        fresh_control_rows={
            name: {"name": name, "similarity": 0.0, "outcome_similarity": 0.0}
            for name in scenario_names
        },
        require_fresh_control=True,
        pulse_interval=1,
    )

    for index, scenario_name in enumerate(scenario_names):
        feedback = controller.assess_scenario(
            scenario_name=scenario_name,
            baseline_scenario=_scenario(),
            result={"similarity": 0.0, "outcome_similarity": 0.0},
            selection_record={
                "generated_tools_visible": ["cross_family_helper"],
                "generated_tools_called": [],
                "generated_tools_attempted": ["cross_family_helper"],
                "generated_tools_failed": ["cross_family_helper"],
            },
            side_effect_failures=[],
            task_context_label=f"visible_task_context(family=family_{index})",
            task_family_key=f"family_{index}",
        )
        assert len(feedback["post_deployment_repair_request_ids"]) == (
            1 if index == 2 else 0
        )

    requests = controller.drain_pending_repair_requests()
    assert len(requests) == 1
    assert requests[0]["target_task_family"] == "cross_family_execution_failure"
    assert requests[0]["trigger_reason_codes"] == [
        "repeated_generated_tool_execution_failure"
    ]
    assert requests[0]["public_evidence"]["failed_count"] == 3
    lifecycle = json.loads(
        (tmp_path / "registry" / "tool_lifecycle.json").read_text(encoding="utf-8")
    )["tool_lifecycle"]["cross_family_helper"]
    assert lifecycle["decision"] == "needs_implementation_repair"
    assert lifecycle["implementation_repair_families"] == [
        "cross_family_execution_failure"
    ]


def test_run_end_emits_sparse_direct_execution_failure_once(tmp_path: Path) -> None:
    scenario_name = "single_direct_execution_failure"
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
                "similarity": 0.0,
                "outcome_similarity": 0.0,
            }
        },
        require_fresh_control=True,
        pulse_interval=1,
    )
    controller.assess_scenario(
        scenario_name=scenario_name,
        baseline_scenario=_scenario(),
        result={"similarity": 0.0, "outcome_similarity": 0.0},
        selection_record={
            "generated_tools_visible": ["sparse_failure_helper"],
            "generated_tools_called": [],
            "generated_tools_attempted": ["sparse_failure_helper"],
            "generated_tools_failed": ["sparse_failure_helper"],
        },
        side_effect_failures=[],
        task_context_label="visible_task_context(family=sparse_failure)",
        task_family_key="sparse_failure",
    )

    assert controller.drain_pending_repair_requests() == ()
    requests = controller.drain_run_end_repair_requests()
    assert len(requests) == 1
    assert requests[0]["trigger_reason_codes"] == [
        "unresolved_generated_tool_execution_failure"
    ]
    assert requests[0]["public_evidence"]["failed_count"] == 1
    assert controller.drain_run_end_repair_requests() == ()


def test_repaired_version_does_not_inherit_prior_version_retirement(
    tmp_path: Path,
) -> None:
    controller = SelfEvolutionReflectionController(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=tmp_path / "run",
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        control_cache=ControlBaselineCache(tmp_path / "control_cache"),
    )
    controller.retired_this_run.add("repaired_helper")

    controller.acknowledge_repair(
        "repaired_helper",
        2,
        "repair-request-v1",
        "canary_pending",
    )

    assert "repaired_helper" not in controller.retired_this_run
    lifecycle = controller._tool_lifecycle_snapshot()["repaired_helper"]
    assert lifecycle["tool_version"] == 2
    assert lifecycle["decision"] != "parked"


def test_reflection_emits_metadata_repair_for_repeated_non_adoption(
    tmp_path: Path,
) -> None:
    scenario_names = tuple(f"private_adoption_case_{index}" for index in range(8))
    controller = SelfEvolutionReflectionController(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=tmp_path / "run",
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        control_cache=None,
        fresh_control_rows={
            name: {
                "name": name,
                "similarity": 0.0,
                "outcome_similarity": 0.0,
            }
            for name in scenario_names
        },
        require_fresh_control=True,
        pulse_interval=1,
    )

    for scenario_name in scenario_names:
        controller.assess_scenario(
            scenario_name=scenario_name,
            baseline_scenario=_scenario(),
            result={"similarity": 0.0, "outcome_similarity": 0.0},
            selection_record={
                "generated_tools_visible": ["generic_unadopted_helper"],
                "generated_tools_called": [],
                "generated_tools_attempted": [],
                "generated_tools_failed": [],
            },
            side_effect_failures=[],
            task_context_label=(
                "visible_task_context(family=record_selection; "
                "signals=selection; request='visible request')"
            ),
            task_family_key="record_selection",
        )

    lifecycle = json.loads(
        (tmp_path / "registry" / "tool_lifecycle.json").read_text(encoding="utf-8")
    )["tool_lifecycle"]["generic_unadopted_helper"]
    assert lifecycle["decision"] == "adoption_repair"
    assert lifecycle["repair_kind"] == "metadata"
    assert lifecycle["metadata_repair_families"] == ["record_selection"]

    requests = controller.drain_pending_repair_requests()
    assert len(requests) == 1
    request = requests[0]
    assert request["repair_kind"] == "metadata"
    assert request["requested_action"] == (
        "repair_public_metadata_and_revalidate_or_retire"
    )
    assert request["trigger_reason_codes"] == ["visible_repeatedly_without_adoption"]
    assert request["eligible_from_completed_count"] == 9
    assert request["public_evidence"]["visible_count"] == 8
    assert request["public_evidence"]["called_count"] == 0
    serialized_request = json.dumps(request)
    assert all(name not in serialized_request for name in scenario_names)


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


def test_reflection_uses_audited_outcome_not_legacy_paper_diagnostic(
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
                "outcome_similarity": 1.0,
                "online_feedback_outcome_similarity": 0.25,
            }
        },
        require_fresh_control=True,
    )

    controller.assess_scenario(
        scenario_name=scenario_name,
        baseline_scenario=_scenario(),
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
    assert feedback["control_outcome"] == 1.0
    assert feedback["control_outcome_source"] == "audited_outcome"
    assert feedback["candidate_outcome"] == 0.0
    assert feedback["candidate_outcome_source"] == "audited_outcome"
    assert feedback["outcome_delta"] == -1.0


def test_reflection_records_audited_outcome_sources(tmp_path: Path) -> None:
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
                "outcome_similarity": 0.25,
                "online_feedback_outcome_similarity": None,
            }
        },
        require_fresh_control=True,
    )

    controller.assess_scenario(
        scenario_name=scenario_name,
        baseline_scenario=_scenario(),
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
    assert feedback["control_outcome_source"] == "audited_outcome"
    assert feedback["candidate_outcome"] == 0.75
    assert feedback["candidate_outcome_source"] == "audited_outcome"
    assert feedback["outcome_delta"] == 0.5


def test_reflection_records_unavailable_outcome_sources(tmp_path: Path) -> None:
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
                "outcome_similarity": None,
                "online_feedback_outcome_similarity": None,
            }
        },
        require_fresh_control=True,
    )

    controller.assess_scenario(
        scenario_name=scenario_name,
        baseline_scenario=_scenario(),
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
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        require_fresh_control=True,
        fresh_control_channel=channel,
    )

    controller.assess_scenario(
        scenario_name=scenario_name,
        baseline_scenario=_scenario(),
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
