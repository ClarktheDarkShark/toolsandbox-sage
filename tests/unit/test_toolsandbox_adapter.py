# mypy: ignore-errors
import json
from pathlib import Path

from sage_ts.adapters.toolsandbox_adapter import (
    ToolSandboxRunConfig,
    _is_transient_model_exception,
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


def test_model_tool_argument_json_truncation_is_retryable() -> None:
    error = json.JSONDecodeError("Unterminated string", '{"query":"', 10)
    traceback_text = (
        "File 'tool_sandbox/common/message_conversion.py', line 88, "
        "in openai_tool_call_to_python_code"
    )

    assert _is_transient_model_exception(error, traceback_text)


def test_unrelated_json_decode_error_is_not_retryable() -> None:
    error = json.JSONDecodeError("Unterminated string", '{"query":"', 10)

    assert not _is_transient_model_exception(
        error,
        "File 'sage_ts/runtime/registry.py', line 1, in load_registry",
    )


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
        user: str,
        output_directory: Path,
    ) -> dict[str, object]:
        assert agent == "Unhelpful"
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
    assert any(event == "scenario_finished" for event, _ in events)
    summary = json.loads(
        (output_directory / "result_summary.json").read_text(encoding="utf-8")
    )
    assert summary["per_scenario_results"][0]["name"] == scenario_name
