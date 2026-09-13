from __future__ import annotations

import json
from pathlib import Path

import pytest

from sage_ts.adapters.toolsandbox_adapter import _copy_resume_artifacts
from sage_ts.evaluation.control_baseline_cache import (
    ControlBaselineCache,
    compatibility_context,
)
from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily, ToolSpec
from sage_ts.orchestration.self_evolution_reflection import (
    SelfEvolutionReflectionController,
    _atomic_write_json,
)
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.registry.store import RegistryStore
from sage_ts.runtime.base_toolset import UPSTREAM_POLICY
from sage_ts.runtime.toolsandbox_integration import (
    _lifecycle_visibility_override,
    load_tool_lifecycle_routing_state,
)
from sage_ts.validation.sandbox_validator import ValidationResult
from tool_sandbox.common.execution_context import ExecutionContext
from tool_sandbox.common.scenario import Scenario


@pytest.fixture(autouse=True)
def _single_record_legacy_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAGE_CONTROL_CACHE_MIN_COMPATIBLE_RUNS", "1")


def _scenario() -> Scenario:
    return Scenario(starting_context=ExecutionContext())


def _accepted_registry_tool(tool_name: str) -> RegistryEntry:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name=tool_name,
            family=ToolFamily.CANONICALIZER,
            description="Normalize a public record selector.",
            inputs=(),
            output_annotation="str",
            generalization_rationale="Applies to repeated record-selection tasks.",
        ),
        code=f"def {tool_name}() -> str:\n    return 'normalized'\n",
    )
    return RegistryEntry.accepted(
        tool,
        ValidationResult(
            True,
            (),
            source_example_count=1,
            held_out_check_count=1,
            runtime_smoke_passed=True,
        ),
        birth_scenario="public_metadata_test",
    )


def _feedback_row(
    index: int,
    *,
    scenario: str,
    family: str,
    tool_name: str,
    called: bool,
    control_outcome: float = 0.0,
    candidate_outcome: float = 0.0,
) -> dict[str, object]:
    delta = candidate_outcome - control_outcome
    return {
        "event": "self_evolution_task_assessed",
        "scenario": scenario,
        "task_context_label": (
            f"visible_task_context(family={family}; signals=public; request='row {index}')"
        ),
        "task_family_key": family,
        "source_task_id_redacted": True,
        "base_family": family,
        "completed_count": index,
        "control_source": "same_run_fresh",
        "control_baseline_available": True,
        "control_cache_eligible": True,
        "control_cache_hit": True,
        "control_cache_reason": "exact_match",
        "control_score": control_outcome,
        "candidate_score": candidate_outcome,
        "score_delta": delta,
        "control_outcome": control_outcome,
        "control_outcome_source": "audited_outcome",
        "candidate_outcome": candidate_outcome,
        "candidate_outcome_source": "audited_outcome",
        "outcome_delta": delta,
        "candidate_success_flip": (candidate_outcome >= 1.0 and control_outcome < 1.0),
        "generated_tools_visible": [tool_name],
        "generated_tools_called": [tool_name] if called else [],
        "generated_tools_attempted": [tool_name] if called else [],
        "generated_tools_failed": [],
        "generated_tool_contract_failures": [],
        "generated_tool_versions": {tool_name: 1},
        "side_effect_failures": [],
        "exception_type": None,
        "post_deployment_repair_request_ids": [],
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _add_cached_baseline(
    cache: ControlBaselineCache,
    root: Path,
    *,
    name: str,
    scenario: Scenario,
) -> None:
    manifest = root / "manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    run_dir = root / "control"
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
    cache.add_record(
        context=context,
        result_row={
            "name": name,
            "similarity": 0.0,
            "outcome_similarity": 0.0,
            "exception_type": None,
        },
        run_dir=run_dir,
        manifest_path=manifest,
    )


def test_resume_restores_metadata_threshold_without_reemitting_request(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "run"
    output_dir.mkdir()
    tool_name = "generic_unadopted_helper"
    family = "record_selection"
    prior_rows = [
        _feedback_row(
            index,
            scenario=f"prior_{index}",
            family=family,
            tool_name=tool_name,
            called=False,
        )
        for index in range(1, 8)
    ]
    feedback_path = output_dir / "self_evolution_task_feedback.jsonl"
    _write_jsonl(feedback_path, prior_rows)
    scenario = _scenario()
    cache = ControlBaselineCache(tmp_path / "cache")
    for name in ("threshold_eight", "after_restart_nine"):
        _add_cached_baseline(cache, tmp_path, name=name, scenario=scenario)

    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_registry_tool(tool_name))
    controller = SelfEvolutionReflectionController(
        store=store,
        output_dir=output_dir,
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        control_cache=cache,
    )
    assert controller.completed_count == 7
    assert controller.tool_stats[tool_name].visible_not_called_count == 7

    controller.assess_scenario(
        scenario_name="threshold_eight",
        baseline_scenario=scenario,
        result={"similarity": 0.0, "outcome_similarity": 0.0},
        selection_record={
            "generated_tools_visible": [tool_name],
            "generated_tools_called": [],
            "generated_tools_attempted": [],
            "generated_tools_failed": [],
        },
        side_effect_failures=[],
        task_context_label="visible_task_context(family=record_selection)",
        task_family_key=family,
    )
    requests = controller.drain_pending_repair_requests()
    assert len(requests) == 1
    request_path = output_dir / "self_evolution_tool_repair_requests.jsonl"
    assert len(request_path.read_text(encoding="utf-8").splitlines()) == 1

    restarted = SelfEvolutionReflectionController(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=output_dir,
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        control_cache=cache,
    )
    assert restarted.completed_count == 8
    assert restarted.tool_stats[tool_name].visible_not_called_count == 8
    restarted.assess_scenario(
        scenario_name="after_restart_nine",
        baseline_scenario=scenario,
        result={"similarity": 0.0, "outcome_similarity": 0.0},
        selection_record={
            "generated_tools_visible": [tool_name],
            "generated_tools_called": [],
            "generated_tools_attempted": [],
            "generated_tools_failed": [],
        },
        side_effect_failures=[],
        task_context_label="visible_task_context(family=record_selection)",
        task_family_key=family,
    )

    assert restarted.completed_count == 9
    assert restarted.drain_pending_repair_requests() == ()
    assert len(request_path.read_text(encoding="utf-8").splitlines()) == 1


def test_partial_resume_preserves_harmful_family_route_suppression(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    tool_name = "generic_dependency_helper"
    family = "contact_dependency_resolution"
    rows = [
        _feedback_row(
            1,
            scenario="harmful_one",
            family=family,
            tool_name=tool_name,
            called=True,
            control_outcome=1.0,
            candidate_outcome=0.0,
        ),
        _feedback_row(
            2,
            scenario="harmful_two",
            family=family,
            tool_name=tool_name,
            called=True,
            control_outcome=1.0,
            candidate_outcome=0.0,
        ),
        _feedback_row(
            3,
            scenario="excluded_future_row",
            family="reminder_dependency_resolution",
            tool_name=tool_name,
            called=True,
            control_outcome=0.0,
            candidate_outcome=1.0,
        ),
    ]
    _write_jsonl(source / "self_evolution_task_feedback.jsonl", rows)
    (source / "live_result_summary.json").write_text(
        json.dumps(
            {"per_scenario_results": [{"name": row["scenario"]} for row in rows]}
        )
        + "\n",
        encoding="utf-8",
    )

    _copy_resume_artifacts(source, destination, completed_limit=2)
    controller = SelfEvolutionReflectionController(
        store=RegistryStore(tmp_path / "registry"),
        output_dir=destination,
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        control_cache=ControlBaselineCache(tmp_path / "cache"),
    )

    assert controller.completed_count == 2
    assert controller.bucket_stats[family]["scenario_count"] == 2
    assert controller.tool_stats[tool_name].called_count == 2
    lifecycle_state = load_tool_lifecycle_routing_state(tmp_path / "registry")
    assert lifecycle_state[tool_name]["decision"] == "needs_route_repair"
    assert _lifecycle_visibility_override(
        tool_name=tool_name,
        scenario_name=f"{family}_alt",
        lifecycle_state=lifecycle_state,
    ) == (False, "lifecycle_suppressed_harmful_called_family")


def test_full_resume_copies_durable_feedback_and_state(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    expected = {
        "self_evolution_task_feedback.jsonl": '{"event":"saved"}\n',
        "post_deployment_repair_state.json": '{"repair":"saved"}\n',
        "self_evolution_reflection_state.json": '{"reflection":"saved"}\n',
    }
    for name, content in expected.items():
        (source / name).write_text(content, encoding="utf-8")

    _copy_resume_artifacts(source, destination)

    for name, content in expected.items():
        assert (destination / name).read_text(encoding="utf-8") == content


def test_reflection_restart_fails_closed_on_malformed_feedback(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    output_dir.mkdir()
    (output_dir / "self_evolution_task_feedback.jsonl").write_text(
        '{"event":"self_evolution_task_assessed"}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Malformed task feedback journal row"):
        SelfEvolutionReflectionController(
            store=RegistryStore(tmp_path / "registry"),
            output_dir=output_dir,
            agent="gpt-4o-mini",
            user="gpt-4o-mini",
            base_tool_policy=UPSTREAM_POLICY,
            manifest_path=tmp_path / "manifest.json",
            control_cache=ControlBaselineCache(tmp_path / "cache"),
        )


def test_reflection_restores_retired_registry_entries(tmp_path: Path) -> None:
    fixture_path = (
        Path(__file__).parents[2]
        / "docs/sage_protocol/fixtures/historical_faulty_safe_action_registry.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    entry = fixture["tools"]["prepare_safe_action_or_abstain"]
    entry["retired"] = True
    registry_root = tmp_path / "registry"
    registry_root.mkdir()
    (registry_root / "registry_manifest.json").write_text(
        json.dumps({"tools": {"prepare_safe_action_or_abstain": entry}}) + "\n",
        encoding="utf-8",
    )

    controller = SelfEvolutionReflectionController(
        store=RegistryStore(registry_root),
        output_dir=tmp_path / "run",
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        base_tool_policy=UPSTREAM_POLICY,
        manifest_path=tmp_path / "manifest.json",
        control_cache=ControlBaselineCache(tmp_path / "cache"),
    )

    assert "prepare_safe_action_or_abstain" in controller.retired_this_run


def test_atomic_json_write_preserves_prior_state_on_replace_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "tool_lifecycle.json"
    target.write_text('{"old":true}\n', encoding="utf-8")

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("simulated interrupted replace")

    monkeypatch.setattr(
        "sage_ts.orchestration.self_evolution_reflection.os.replace",
        fail_replace,
    )
    with pytest.raises(OSError, match="simulated interrupted replace"):
        _atomic_write_json(target, {"new": True})

    assert target.read_text(encoding="utf-8") == '{"old":true}\n'
    assert list(tmp_path.glob(".tool_lifecycle.json.*.tmp")) == []
