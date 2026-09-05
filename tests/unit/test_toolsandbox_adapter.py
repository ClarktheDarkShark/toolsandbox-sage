# mypy: ignore-errors
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)

import sage_ts.adapters.role_factory as role_factory
import sage_ts.adapters.toolsandbox_adapter as toolsandbox_adapter
from sage_ts.adapters.toolsandbox_adapter import (
    ToolSandboxRunConfig,
    run_scenario_sequence,
    write_run_manifest,
)
from tool_sandbox.common.execution_context import ExecutionContext, RoleType
from tool_sandbox.common.message_conversion import (
    Message,
    openai_tool_call_to_python_code,
)
from tool_sandbox.common.scenario import Scenario
from tool_sandbox.roles.execution_environment import (
    _execution_equivalent_message_permutations,
)


class APIConnectionError(Exception):
    pass


class _NoopRole:
    def teardown(self) -> None:
        pass


def _tool_call_message(value: int, call_id: str) -> Message:
    tool_call = ChatCompletionMessageToolCall(
        id=call_id,
        type="function",
        function=Function(name="generated_helper", arguments=f'{{"value": {value}}}'),
    )
    return Message(
        sender=RoleType.AGENT,
        recipient=RoleType.EXECUTION_ENVIRONMENT,
        content=openai_tool_call_to_python_code(
            tool_call,
            available_tool_names={"generated_helper"},
            execution_facing_tool_name=None,
        ),
        openai_tool_call_id=call_id,
        openai_function_name="generated_helper",
    )


def test_parallel_execution_collapses_only_execution_equivalent_permutations() -> None:
    first_a = _tool_call_message(1, "call_a_1")
    second_a = _tool_call_message(1, "call_a_2")
    call_b = _tool_call_message(2, "call_b")

    orderings = list(
        _execution_equivalent_message_permutations([first_a, second_a, call_b])
    )

    assert [[message.openai_tool_call_id for message in row] for row in orderings] == [
        ["call_a_1", "call_a_2", "call_b"],
        ["call_a_1", "call_b", "call_a_2"],
        ["call_b", "call_a_1", "call_a_2"],
    ]
    assert first_a.content != second_a.content
    assert orderings[0] == (first_a, second_a, call_b)


def test_ten_identical_parallel_calls_have_one_execution_ordering() -> None:
    messages = [_tool_call_message(1, f"call_{index}") for index in range(10)]

    orderings = list(_execution_equivalent_message_permutations(messages))

    assert orderings == [tuple(messages)]


def _patch_run_one_dependencies(monkeypatch) -> None:
    def make_role(*_args: object, **_kwargs: object) -> _NoopRole:
        return _NoopRole()

    def fake_outcome_score(
        _scenario: object,
        _execution_context: object,
        *,
        scenario_name: str,
    ) -> dict[str, object]:
        assert scenario_name
        return {
            "outcome_similarity": 1.0,
            "outcome_milestone_similarity": 1.0,
            "outcome_minefield_similarity": 1.0,
            "outcome_check_count": 1,
            "outcome_checks": [],
        }

    monkeypatch.setattr(toolsandbox_adapter, "make_user", make_role)
    monkeypatch.setattr(toolsandbox_adapter, "make_agent", make_role)
    monkeypatch.setattr(toolsandbox_adapter, "ExecutionEnvironment", make_role)
    monkeypatch.setattr(
        toolsandbox_adapter,
        "compute_outcome_score",
        fake_outcome_score,
    )


def _successful_scenario_result() -> SimpleNamespace:
    return SimpleNamespace(
        evaluation_result=SimpleNamespace(
            milestone_mapping={},
            minefield_mapping={},
            milestone_similarity=1.0,
            minefield_similarity=1.0,
            similarity=1.0,
            turn_count=2,
        ),
        ending_context=object(),
    )


def test_transient_api_connection_retry_is_archived_and_classified(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _patch_run_one_dependencies(monkeypatch)
    monkeypatch.setenv("SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS", "2")
    attempt_count = 0

    def play_and_evaluate(
        *,
        roles: object,
        output_directory: Path,
        scenario_name: str,
    ) -> object:
        nonlocal attempt_count
        del roles
        attempt_count += 1
        trajectory = output_directory / "trajectories" / scenario_name
        trajectory.mkdir(parents=True)
        (trajectory / "attempt.txt").write_text(str(attempt_count), encoding="utf-8")
        if attempt_count == 1:
            raise APIConnectionError("temporary model connection failure")
        return _successful_scenario_result()

    scenario = SimpleNamespace(
        categories=["unit_test"],
        max_messages=4,
        play_and_evaluate=play_and_evaluate,
    )

    result = toolsandbox_adapter.run_one_scenario(
        "api_retry",
        scenario,
        agent="agent",
        user="user",
        output_directory=tmp_path,
    )

    archive = tmp_path / "trajectories" / "api_retry__transient_retry_failed_attempt_1"
    assert attempt_count == 2
    assert result["exception_type"] is None
    assert result["transient_retry_count"] == 1
    assert result["transient_retry_archives"] == [str(archive)]
    assert (archive / "attempt.txt").read_text(encoding="utf-8") == "1"
    assert (tmp_path / "trajectories" / "api_retry" / "attempt.txt").read_text(
        encoding="utf-8"
    ) == "2"
    assert len(result["transient_retry_failures"]) == 1
    failure = result["transient_retry_failures"][0]
    assert failure["attempt"] == 1
    assert failure["exception_type"] == "APIConnectionError"
    assert failure["exception_message"] == "temporary model connection failure"
    assert (
        "APIConnectionError: temporary model connection failure" in failure["traceback"]
    )
    assert failure["archive_path"] == str(archive)
    assert failure["exception_chain_type_names"] == ["APIConnectionError"]
    assert failure["retry_reason"] == {
        "kind": "exception_chain_type",
        "identifier": "APIConnectionError",
    }


def test_transient_retry_fails_terminally_without_trajectory_archive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _patch_run_one_dependencies(monkeypatch)
    monkeypatch.setenv("SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS", "2")
    attempt_count = 0

    def play_and_evaluate(**_kwargs: object) -> object:
        nonlocal attempt_count
        attempt_count += 1
        raise APIConnectionError("failure before trajectory creation")

    scenario = SimpleNamespace(
        categories=["unit_test"],
        max_messages=4,
        play_and_evaluate=play_and_evaluate,
    )

    result = toolsandbox_adapter.run_one_scenario(
        "missing_trajectory",
        scenario,
        agent="agent",
        user="user",
        output_directory=tmp_path,
    )

    assert attempt_count == 1
    assert result["exception_type"] == "APIConnectionError"
    assert result["transient_retry_count"] == 0
    assert result["transient_retry_archives"] == []
    assert result["transient_retry_failures"][0]["archive_path"] is None
    assert result["transient_retry_failures"][0]["retry_reason"] == {
        "kind": "exception_chain_type",
        "identifier": "APIConnectionError",
    }
    assert result["outcome_evaluator_version"]
    assert len(result["outcome_evaluator_contract_sha256"]) == 64
    assert len(result["outcome_evaluator_source_sha256"]) == 64


def test_generic_connection_error_requires_an_existing_traceback_marker() -> None:
    exception = ConnectionError("generic connection failure")

    chain, reason = toolsandbox_adapter._transient_retry_evidence(
        exception,
        "Traceback: generic connection failure",
    )

    assert chain == ["ConnectionError"]
    assert reason is None

    chain, reason = toolsandbox_adapter._transient_retry_evidence(
        exception,
        "Traceback: Connection error.",
    )

    assert chain == ["ConnectionError"]
    assert reason == {
        "kind": "traceback_marker",
        "identifier": "connection_error",
    }


def test_transient_retry_evidence_has_deterministic_precedence() -> None:
    inner = APIConnectionError("inner connection failure")
    outer = RuntimeError("outer wrapper")
    outer.__cause__ = inner

    chain, reason = toolsandbox_adapter._transient_retry_evidence(
        outer,
        "Traceback also mentions RateLimitError",
    )

    assert chain == ["RuntimeError", "APIConnectionError"]
    assert reason == {
        "kind": "exception_chain_type",
        "identifier": "APIConnectionError",
    }

    chain, reason = toolsandbox_adapter._transient_retry_evidence(
        ConnectionError("generic"),
        "Traceback mentions ConnectTimeout before ReadTimeout",
    )

    assert chain == ["ConnectionError"]
    assert reason == {
        "kind": "traceback_marker",
        "identifier": "read_timeout",
    }


def test_make_agent_propagates_auto_selection_mode(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_agent(model_name: str, *, actor_selection_mode: str):
        captured.update(
            model_name=model_name,
            actor_selection_mode=actor_selection_mode,
        )
        return object()

    monkeypatch.setattr(role_factory, "ConfigurableOpenAIAgent", fake_agent)

    role_factory.make_agent("gpt-4o-mini", actor_selection_mode="auto")

    assert captured == {
        "model_name": "gpt-4o-mini",
        "actor_selection_mode": "auto",
    }


def test_make_agent_rejects_auto_for_upstream_role_alias() -> None:
    with pytest.raises(
        ValueError,
        match="ToolSandbox role alias 'GPT_4_o_2024_05_13'",
    ):
        role_factory.make_agent(
            "GPT_4_o_2024_05_13",
            actor_selection_mode="auto",
        )


def test_write_run_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TZ", "America/New_York")
    config = ToolSandboxRunConfig(
        agent="Unhelpful",
        user="GPT_4_o_2024_05_13",
        scenario_names=("wifi_off",),
        output_dir=tmp_path,
    )

    path = write_run_manifest(config)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["scenario_names"] == ["wifi_off"]
    assert payload["run_type"] == "baseline"
    assert payload["actor_selection_mode"] == "policy"
    assert payload["timezone"] == "America/New_York"
    assert payload["outcome_evaluator"]["version"]
    assert len(payload["outcome_evaluator"]["contract_sha256"]) == 64
    assert len(payload["outcome_evaluator"]["source_sha256"]) == 64


def test_write_run_manifest_records_auto_actor_selection(tmp_path: Path) -> None:
    config = ToolSandboxRunConfig(
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        scenario_names=("wifi_off",),
        output_dir=tmp_path,
        actor_selection_mode="auto",
    )

    payload = json.loads(write_run_manifest(config).read_text(encoding="utf-8"))

    assert payload["actor_selection_mode"] == "auto"


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
        actor_selection_mode: str,
        output_directory: Path,
    ) -> dict[str, object]:
        assert agent == "Unhelpful"
        assert user == "GPT_4_o_2024_05_13"
        assert actor_selection_mode == "auto"
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
            actor_selection_mode="auto",
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


def test_run_scenario_sequence_reraises_fail_closed_transform_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    scenario_name = "toy_birth"
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )

    class FailClosedTransformError(RuntimeError):
        fail_closed_scenario_transform = True

    events: list[str] = []

    monkeypatch.setattr(
        "sage_ts.adapters.toolsandbox_adapter.resolve_scenarios",
        lambda *_args, **_kwargs: {scenario_name: scenario},
    )

    def must_not_run(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("actor inference ran after a fail-closed transform error")

    monkeypatch.setattr(
        "sage_ts.adapters.toolsandbox_adapter.run_one_scenario",
        must_not_run,
    )

    def fail_closed_transform(
        _name: str,
        _base: Scenario,
        _path: Path,
    ) -> Scenario:
        raise FailClosedTransformError("inventory mismatch")

    with pytest.raises(FailClosedTransformError, match="inventory mismatch"):
        run_scenario_sequence(
            ToolSandboxRunConfig(
                agent="Unhelpful",
                user="GPT_4_o_2024_05_13",
                scenario_names=(scenario_name,),
                output_dir=tmp_path / "outputs",
            ),
            scenario_transform=fail_closed_transform,
            event_hook=lambda event, _output_dir, _payload: events.append(event),
        )

    assert "scenario_transform_failed" in events
    assert "scenario_finished" not in events


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
        user: str,
        actor_selection_mode: str,
        output_directory: Path,
    ) -> dict[str, object]:
        assert actor_selection_mode == "policy"
        calls.append(name)
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
