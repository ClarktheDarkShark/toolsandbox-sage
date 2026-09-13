# mypy: ignore-errors
import json
from pathlib import Path

import pytest

from sage_ts.adapters.toolsandbox_adapter import (
    ToolSandboxRunConfig,
    run_scenario_sequence,
    write_run_manifest,
)
from tool_sandbox.common.execution_context import ExecutionContext
from tool_sandbox.common.scenario import Scenario


def test_write_run_manifest(tmp_path: Path) -> None:
    config = ToolSandboxRunConfig(
        agent="Unhelpful",
        user="GPT_4_o_2024_05_13",
        scenario_names=("wifi_off",),
        output_dir=tmp_path,
    )

    path = write_run_manifest(config)
    text = path.read_text(encoding="utf-8")

    assert "wifi_off" in text
    assert "baseline" in text


def test_write_run_manifest_records_native_toolsandbox_actor(tmp_path: Path) -> None:
    config = ToolSandboxRunConfig(
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        scenario_names=("wifi_off",),
        output_dir=tmp_path,
        agent_runtime="toolsandbox_native",
    )

    payload = json.loads(write_run_manifest(config).read_text(encoding="utf-8"))

    assert payload["agent_runtime"] == "toolsandbox_native"
    assert payload["actor_selection_mode"] == "toolsandbox_native"


def test_run_scenario_sequence_continues_after_transform_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    scenario_name = "toy_birth"
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )
    output_dir = tmp_path / "outputs"

    def fake_resolve_scenarios(
        *_args: object, **_kwargs: object
    ) -> dict[str, Scenario]:
        return {scenario_name: scenario}

    events: list[tuple[str, str]] = []

    def fake_event_hook(
        event: str, _output_dir: Path, payload: dict[str, object]
    ) -> None:
        events.append((event, str(payload.get("scenario"))))

    def fake_transform(_name: str, _base: Scenario, _path: Path) -> Scenario:
        raise RuntimeError("transform failed")

    def fake_run_one_scenario(
        _name: str,
        _scenario: Scenario,
        *,
        agent: str,
        agent_runtime: str,
        user: str,
        output_directory: Path,
    ) -> dict[str, object]:
        assert agent == "Unhelpful"
        assert agent_runtime == "sage_wrapped"
        assert user == "GPT_4_o_2024_05_13"
        assert str(output_directory).startswith(str(output_dir))
        assert output_directory.name.startswith(
            "baseline_agent_Unhelpful_user_GPT_4_o_2024_05_13"
        )
        return {
            "name": _name,
            "categories": [],
            "traceback": None,
            "exception_type": None,
            "milestone_similarity": 0,
            "minefield_similarity": 0,
            "similarity": 1.0,
            "turn_count": 1,
            "milestone_mapping": {},
            "minefield_mapping": {},
            "outcome_similarity": 1.0,
            "outcome_milestone_similarity": 1.0,
            "outcome_minefield_similarity": 1.0,
            "outcome_check_count": 1,
            "outcome_checks": [],
        }

    monkeypatch.setattr(
        "sage_ts.adapters.toolsandbox_adapter.resolve_scenarios", fake_resolve_scenarios
    )
    monkeypatch.setattr(
        "sage_ts.adapters.toolsandbox_adapter.run_one_scenario", fake_run_one_scenario
    )

    output_directory = run_scenario_sequence(
        ToolSandboxRunConfig(
            agent="Unhelpful",
            user="GPT_4_o_2024_05_13",
            scenario_names=(scenario_name,),
            output_dir=output_dir,
        ),
        scenario_transform=fake_transform,
        event_hook=fake_event_hook,
    )
    assert output_directory.name.startswith(
        "baseline_agent_Unhelpful_user_GPT_4_o_2024_05_13"
    )

    assert ("scenario_transform_failed", scenario_name) in events
    assert (output_directory / "scenario_transform_failures.jsonl").is_file()
    assert any(event == "scenario_finished" for event, _ in events)
    summary = json.loads(
        (output_directory / "result_summary.json").read_text(encoding="utf-8")
    )
    assert summary["per_scenario_results"][0]["name"] == scenario_name


def test_run_scenario_sequence_aborts_after_transform_failure_when_strict(
    tmp_path: Path,
    monkeypatch,
) -> None:
    scenario_name = "toy_birth"
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )
    ran_scenario = False

    monkeypatch.setattr(
        "sage_ts.adapters.toolsandbox_adapter.resolve_scenarios",
        lambda *_args, **_kwargs: {scenario_name: scenario},
    )

    def fake_transform(_name: str, _base: Scenario, _path: Path) -> Scenario:
        raise RuntimeError("transform failed")

    def fake_run_one_scenario(*_args: object, **_kwargs: object) -> dict[str, object]:
        nonlocal ran_scenario
        ran_scenario = True
        return {}

    monkeypatch.setattr(
        "sage_ts.adapters.toolsandbox_adapter.run_one_scenario",
        fake_run_one_scenario,
    )

    with pytest.raises(RuntimeError, match="transform failed"):
        run_scenario_sequence(
            ToolSandboxRunConfig(
                agent="Unhelpful",
                user="GPT_4_o_2024_05_13",
                scenario_names=(scenario_name,),
                output_dir=tmp_path / "outputs",
                fail_on_scenario_transform_error=True,
            ),
            scenario_transform=fake_transform,
        )

    assert ran_scenario is False
    failure_files = list(
        (tmp_path / "outputs").glob("*/scenario_transform_failures.jsonl")
    )
    assert len(failure_files) == 1
    failure = json.loads(failure_files[0].read_text(encoding="utf-8"))
    assert failure["event"] == "scenario_transform_failed"
    assert failure["scenario"] == scenario_name


def test_run_scenario_sequence_resume_completed_limit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    scenario_names = ("task_a", "task_b", "task_c")
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )
    resume_dir = tmp_path / "resume"
    resume_dir.mkdir()
    (resume_dir / "live_result_summary.json").write_text(
        json.dumps(
            {
                "status": "running",
                "scenario_count": 3,
                "per_scenario_results": [
                    {
                        "name": "task_a",
                        "categories": [],
                        "similarity": 1.0,
                        "milestone_similarity": 1.0,
                        "minefield_similarity": 1.0,
                        "turn_count": 1,
                        "traceback": None,
                        "exception_type": None,
                    },
                    {
                        "name": "task_b",
                        "categories": [],
                        "similarity": 0.0,
                        "milestone_similarity": 0.0,
                        "minefield_similarity": 0.0,
                        "turn_count": 1,
                        "traceback": None,
                        "exception_type": None,
                    },
                    {
                        "name": "task_c",
                        "categories": [],
                        "similarity": 0.0,
                        "milestone_similarity": 0.0,
                        "minefield_similarity": 0.0,
                        "turn_count": 1,
                        "traceback": None,
                        "exception_type": None,
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (resume_dir / "scenario_tool_selection.jsonl").write_text(
        json.dumps({"scenario": "task_a", "status": "retained"})
        + "\n"
        + json.dumps({"scenario": "task_b", "status": "excluded"})
        + "\n",
        encoding="utf-8",
    )
    (resume_dir / "self_evolution_tool_repair_requests.jsonl").write_text(
        json.dumps({"request_id": "keep", "trigger_completed_count": 1})
        + "\n"
        + json.dumps({"request_id": "drop", "trigger_completed_count": 2})
        + "\n",
        encoding="utf-8",
    )
    (resume_dir / "self_evolution_tool_repair_acknowledgements.jsonl").write_text(
        json.dumps({"request_id": "keep", "acknowledged_after_completed_count": 1})
        + "\n"
        + json.dumps({"request_id": "drop", "acknowledged_after_completed_count": 2})
        + "\n",
        encoding="utf-8",
    )
    (resume_dir / "post_deployment_repair_state.json").write_text(
        json.dumps({"unsafe_after_rewind": True}) + "\n",
        encoding="utf-8",
    )
    (resume_dir / "trajectories" / "task_a").mkdir(parents=True)
    (resume_dir / "trajectories" / "task_a" / "conversation.json").write_text(
        "[]\n",
        encoding="utf-8",
    )
    (resume_dir / "trajectories" / "task_b").mkdir(parents=True)
    (resume_dir / "trajectories" / "task_b" / "conversation.json").write_text(
        "[]\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sage_ts.adapters.toolsandbox_adapter.resolve_scenarios",
        lambda **_kwargs: {name: scenario for name in scenario_names},
    )
    calls: list[str] = []

    def fake_run_one_scenario(
        name: str,
        _scenario: Scenario,
        *,
        agent: str,
        agent_runtime: str,
        user: str,
        output_directory: Path,
    ) -> dict[str, object]:
        calls.append(name)
        assert agent_runtime == "sage_wrapped"
        return {
            "name": name,
            "categories": [],
            "traceback": None,
            "exception_type": None,
            "milestone_similarity": 0,
            "minefield_similarity": 0,
            "similarity": 1.0,
            "turn_count": 1,
            "milestone_mapping": {},
            "minefield_mapping": {},
        }

    monkeypatch.setattr(
        "sage_ts.adapters.toolsandbox_adapter.run_one_scenario",
        fake_run_one_scenario,
    )

    output_directory = run_scenario_sequence(
        ToolSandboxRunConfig(
            agent="Unhelpful",
            user="GPT_4_o_2024_05_13",
            scenario_names=scenario_names,
            output_dir=tmp_path / "outputs",
            resume_from_dir=resume_dir,
            resume_completed_limit=1,
        )
    )

    summary = json.loads(
        (output_directory / "result_summary.json").read_text(encoding="utf-8")
    )
    assert [row["name"] for row in summary["per_scenario_results"]] == [
        "task_a",
        "task_b",
        "task_c",
    ]
    assert calls == ["task_b", "task_c"]
    copied_selection = (output_directory / "scenario_tool_selection.jsonl").read_text(
        encoding="utf-8"
    )
    assert "task_a" in copied_selection
    assert "task_b" not in copied_selection
    assert (output_directory / "trajectories" / "task_a").exists()
    assert not (output_directory / "trajectories" / "task_b").exists()
    copied_requests = (
        output_directory / "self_evolution_tool_repair_requests.jsonl"
    ).read_text(encoding="utf-8")
    copied_acknowledgements = (
        output_directory / "self_evolution_tool_repair_acknowledgements.jsonl"
    ).read_text(encoding="utf-8")
    assert '"keep"' in copied_requests
    assert '"drop"' not in copied_requests
    assert '"keep"' in copied_acknowledgements
    assert '"drop"' not in copied_acknowledgements
    assert not (output_directory / "post_deployment_repair_state.json").exists()
