"""Deterministic external contracts for runner and publication provenance.

The fixtures in this module are deliberately small and synthetic.  They call
the selected checkout's real runner, campaign-artifact, checkpoint, and
environment-verification code while replacing only model/network execution,
the current clock, and Git process calls.  Nothing in this module is imported
by the production package.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Iterator


RUNNER_SHA256 = "b40856762456913a70e60270f443b91c6c32c56d6ecd7975b8c196edc968b64c"
SHELL_ENTRYPOINT_SHA256 = (
    "78811efa9f6c682c671c4664a4cf6249937591c94d4e6449df6b9ebd201f1183"
)
FIXED_NOW = datetime(2026, 9, 26, 12, 34, 56, 123456, tzinfo=timezone.utc)


class _FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz: Any = None) -> "_FrozenDateTime":
        value = cls(
            FIXED_NOW.year,
            FIXED_NOW.month,
            FIXED_NOW.day,
            FIXED_NOW.hour,
            FIXED_NOW.minute,
            FIXED_NOW.second,
            FIXED_NOW.microsecond,
            tzinfo=timezone.utc,
        )
        if tz is None:
            return value.replace(tzinfo=None)
        return value.astimezone(tz)


@contextmanager
def _patch(module: Any, **replacements: Any) -> Iterator[None]:
    prior = {name: getattr(module, name) for name in replacements}
    try:
        for name, value in replacements.items():
            setattr(module, name, value)
        yield
    finally:
        for name, value in prior.items():
            setattr(module, name, value)


@contextmanager
def _working_directory(path: Path) -> Iterator[None]:
    prior = Path.cwd()
    path.mkdir(parents=True, exist_ok=True)
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prior)


@contextmanager
def _environment(**values: str | None) -> Iterator[None]:
    prior = {name: os.environ.get(name) for name in values}
    try:
        for name, value in values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name, value in prior.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable(value: Any, replacements: tuple[tuple[str, str], ...]) -> Any:
    """Replace fixture-local absolute prefixes without changing key order."""

    if isinstance(value, str):
        for source, target in replacements:
            value = value.replace(source, target)
        return value
    if isinstance(value, dict):
        return {key: _stable(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_stable(item, replacements) for item in value]
    if isinstance(value, tuple):
        return tuple(_stable(item, replacements) for item in value)
    return value


def _text_contract(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    return {
        "relative_path": path.as_posix(),
        "byte_count": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "ends_with_newline": raw.endswith(b"\n"),
        "text": text,
    }


def _json_contract(
    path: Path, exact: Callable[[Any], dict[str, Any]]
) -> dict[str, Any]:
    contract = _text_contract(path)
    payload = json.loads(contract["text"])
    contract["top_level_key_order"] = list(payload) if isinstance(payload, dict) else []
    contract["parsed_exact"] = exact(payload)
    return contract


def _jsonl_contract(
    path: Path, exact: Callable[[Any], dict[str, Any]]
) -> dict[str, Any]:
    contract = _text_contract(path)
    rows = [json.loads(line) for line in contract["text"].splitlines() if line]
    contract["row_count"] = len(rows)
    contract["rows_exact"] = exact(rows)
    return contract


def _source_hashes(root: Path) -> dict[str, Any]:
    runner = root / "scripts" / "run_sage_protocol.py"
    shell = root / "scripts" / "run_native_action_4omini_ab.sh"
    runner_sha = _sha256(runner)
    shell_sha = _sha256(shell)
    return {
        "runner": {
            "path": "scripts/run_sage_protocol.py",
            "sha256": runner_sha,
            "expected_sha256": RUNNER_SHA256,
            "matches_frozen_reference": runner_sha == RUNNER_SHA256,
        },
        "shell_entrypoint": {
            "path": "scripts/run_native_action_4omini_ab.sh",
            "sha256": shell_sha,
            "expected_sha256": SHELL_ENTRYPOINT_SHA256,
            "matches_frozen_reference": shell_sha == SHELL_ENTRYPOINT_SHA256,
        },
    }


def assert_frozen_source_hashes(payload: dict[str, Any]) -> None:
    mismatches = [
        name
        for name, contract in payload.items()
        if contract.get("sha256") != contract.get("expected_sha256")
    ]
    if mismatches:
        raise RuntimeError(
            "frozen publication source mismatch: " + ", ".join(mismatches)
        )


def _run_manifest_contract(
    exact: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    import sage_ts.adapters.toolsandbox_adapter as adapter

    config = adapter.ToolSandboxRunConfig(
        agent="FixtureAgent",
        user="FixtureUser",
        scenario_names=("alpha_task", "beta_task"),
        output_dir=Path("manifest-output"),
        processes=1,
        run_type="sage_fixture",
        base_tool_policy="upstream",
    )
    with _patch(
        adapter,
        datetime=_FrozenDateTime,
        git_sha=lambda: "0123456789abcdef",
    ):
        path = adapter.write_run_manifest(config)
    return _json_contract(path, exact)


def _sequence_contract(
    exact: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    import sage_ts.adapters.toolsandbox_adapter as adapter

    timeline: list[dict[str, Any]] = []
    cleared: set[str] = set()
    original_live_writer = adapter.write_live_result_summary

    def fake_manifest(config: Any) -> Path:
        timeline.append(
            {"call": "write_run_manifest", "scenarios": list(config.scenario_names)}
        )
        path = config.output_dir / "sage_ts_run_manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
        return path

    def fake_base_policy(scenario: Any, policy: str) -> dict[str, Any]:
        timeline.append(
            {"call": "apply_base_tool_policy", "scenario": scenario, "policy": policy}
        )
        return {"stage": "base", "scenario": scenario}

    def transform(name: str, scenario: Any, output: Path) -> Any:
        timeline.append(
            {"call": "transform", "name": name, "input": copy.deepcopy(scenario)}
        )
        if name == "alpha_task":
            raise RuntimeError("deterministic transform failure")
        return {"stage": "transformed", "scenario": scenario["scenario"]}

    def run_one(
        name: str,
        scenario: Any,
        *,
        agent: str,
        user: str,
        output_directory: Path,
    ) -> dict[str, Any]:
        timeline.append(
            {
                "call": "run_one_scenario",
                "name": name,
                "scenario": copy.deepcopy(scenario),
                "agent": agent,
                "user": user,
                "scenario_env": os.environ.get("SAGE_TS_CURRENT_SCENARIO"),
                "order_env": os.environ.get("SAGE_TS_SCENARIO_ORDER_INDEX"),
            }
        )
        return {
            "name": name,
            "categories": [f"category_{name}"],
            "traceback": None,
            "exception_type": None,
            "similarity": 0.5 if name == "alpha_task" else 1.0,
            "turn_count": 2,
        }

    def result_hook(
        name: str, scenario: Any, result: dict[str, Any], output: Path
    ) -> dict[str, Any]:
        timeline.append(
            {
                "call": "result_hook",
                "name": name,
                "scenario": copy.deepcopy(scenario),
                "result_keys_before": list(result),
                "currently_running_exists": (
                    output / "currently_running.json"
                ).exists(),
                "scenario_env": os.environ.get("SAGE_TS_CURRENT_SCENARIO"),
                "order_env": os.environ.get("SAGE_TS_SCENARIO_ORDER_INDEX"),
            }
        )
        return {**result, "result_hook_marker": f"hooked:{name}"}

    def snapshot_usage(name: str) -> dict[str, Any]:
        timeline.append(
            {
                "call": "snapshot_scenario_usage",
                "name": name,
                "was_cleared": name in cleared,
            }
        )
        return {"llm_call_count": 10 + len(cleared), "llm_usage_fixture": name}

    def clear_usage(name: str) -> None:
        timeline.append({"call": "clear_scenario_usage", "name": name})
        cleared.add(name)

    def progress(
        output: Path, rows: list[dict[str, Any]], status: str, count: int
    ) -> None:
        timeline.append(
            {
                "call": "progress_hook",
                "status": status,
                "scenario_count": count,
                "row_names": [row.get("name") for row in rows],
                "hook_markers": [row.get("result_hook_marker") for row in rows],
                "usage_names": [row.get("llm_usage_fixture") for row in rows],
            }
        )

    def event(event_name: str, output: Path, payload: dict[str, Any]) -> None:
        stable_payload = dict(payload)
        if "error" in stable_payload:
            stable_payload["error"] = str(stable_payload["error"]).splitlines()[-1]
        timeline.append(
            {"call": "event_hook", "event": event_name, "payload": stable_payload}
        )

    def live_writer(**kwargs: Any) -> Path:
        timeline.append(
            {
                "call": "write_live_result_summary",
                "status": kwargs["status"],
                "row_names": [row.get("name") for row in kwargs["result_summary"]],
            }
        )
        return original_live_writer(**kwargs)

    def final_writer(
        *,
        result_summary: list[dict[str, Any]],
        category_summary: Any,
        output_directory: Path,
    ) -> None:
        timeline.append(
            {
                "call": "write_result_summary",
                "row_names": [row.get("name") for row in result_summary],
                "category_summary": category_summary,
            }
        )
        (output_directory / "result_summary.json").write_text(
            json.dumps({"per_scenario_results": result_summary}, indent=2) + "\n",
            encoding="utf-8",
        )

    def usage_writer(output: Path) -> None:
        timeline.append(
            {"call": "write_llm_usage_artifacts", "cleared": sorted(cleared)}
        )

    config = adapter.ToolSandboxRunConfig(
        agent="FixtureAgent",
        user="FixtureUser",
        scenario_names=("alpha_task", "beta_task"),
        output_dir=Path("sequence-output"),
        run_type="fixture",
        base_tool_policy="fixture-policy",
    )
    patches = {
        "datetime": _FrozenDateTime,
        "tqdm": lambda items, **_kwargs: items,
        "write_run_manifest": fake_manifest,
        "install_llm_usage_tracking": lambda: timeline.append(
            {"call": "install_llm_usage_tracking"}
        ),
        "reset_llm_usage": lambda **kwargs: timeline.append(
            {"call": "reset_llm_usage", "arm": kwargs.get("arm")}
        ),
        "apply_base_tool_policy": fake_base_policy,
        "run_one_scenario": run_one,
        "outcome_evaluator_manifest": lambda: {
            "version": "fixture-v1",
            "contract_sha256": "contract-fixture",
            "source_sha256": "source-fixture",
        },
        "snapshot_scenario_usage": snapshot_usage,
        "clear_scenario_usage": clear_usage,
        "write_live_result_summary": live_writer,
        "write_result_summary": final_writer,
        "get_category_summary": lambda rows: {
            "ordered_names": [row["name"] for row in rows]
        },
        "write_llm_usage_artifacts": usage_writer,
    }
    with _patch(adapter, **patches):
        output = adapter.run_scenario_sequence(
            config,
            scenarios={"beta_task": "raw-beta", "alpha_task": "raw-alpha"},
            scenario_transform=transform,
            result_hook=result_hook,
            progress_hook=progress,
            event_hook=event,
        )
    return {
        "output_directory": output.as_posix(),
        "timeline": exact(timeline),
        "final_live_summary": _json_contract(
            output / "live_result_summary.json", exact
        ),
        "final_result_summary": _json_contract(output / "result_summary.json", exact),
        "currently_running_removed": not (output / "currently_running.json").exists(),
        "usage_cleared": sorted(cleared),
    }


def _sequence_edge_contract(
    exact: Callable[[Any], dict[str, Any]],
    capture: Callable[[Callable[[], Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Freeze public hook fallback, identity, mutation, and failure behavior."""

    import sage_ts.adapters.toolsandbox_adapter as adapter

    evaluator_identity = {
        "version": "fixture-evaluator-v1",
        "contract_sha256": "fixture-evaluator-contract",
        "source_sha256": "fixture-evaluator-source",
    }

    def execute(
        case_name: str,
        *,
        result_hook_mode: str = "original",
        progress_mode: str = "observe",
    ) -> dict[str, Any]:
        timeline: list[dict[str, Any]] = []
        state: dict[str, Any] = {}
        output = Path(f"sequence-edge-{case_name}")
        config = adapter.ToolSandboxRunConfig(
            agent="FixtureAgent",
            user="FixtureUser",
            scenario_names=("edge_task",),
            output_dir=Path(f"sequence-edge-{case_name}-manifest"),
            processes=1,
            run_type="fixture_edge",
            base_tool_policy="fixture-policy",
        )

        def fake_manifest(_config: Any) -> Path:
            path = _config.output_dir / "sage_ts_run_manifest.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")
            timeline.append({"call": "write_run_manifest"})
            return path

        def run_one(
            name: str,
            scenario: Any,
            *,
            agent: str,
            user: str,
            output_directory: Path,
        ) -> dict[str, Any]:
            del agent, user, output_directory
            result = {
                "name": name,
                "categories": ["edge"],
                "similarity": 0.75,
                "turn_count": 2,
                "traceback": None,
                "exception_type": None,
                "original_marker": scenario["marker"],
            }
            state["run_result"] = result
            timeline.append(
                {
                    "call": "run_one_scenario",
                    "scenario_order_index": os.environ.get(
                        "SAGE_TS_SCENARIO_ORDER_INDEX"
                    ),
                }
            )
            return result

        def result_hook(
            name: str,
            scenario: Any,
            result: dict[str, Any],
            output_directory: Path,
        ) -> dict[str, Any] | None:
            del name, scenario, output_directory
            timeline.append(
                {
                    "call": "result_hook",
                    "input_is_run_result": result is state.get("run_result"),
                    "input_keys": list(result),
                }
            )
            if result_hook_mode == "raise":
                raise RuntimeError("fixture result-hook failure")
            if result_hook_mode == "none":
                state["hook_return"] = None
                return None
            if result_hook_mode == "empty":
                hook_return: dict[str, Any] = {}
                state["hook_return"] = hook_return
                return hook_return
            if result_hook_mode == "mutate_none":
                result["in_place_hook_marker"] = "retained"
                state["hook_return"] = None
                return None
            if result_hook_mode == "fresh_spoof":
                hook_return = {
                    "name": "fresh_spoof_result",
                    "fresh_marker": True,
                    "outcome_evaluator_version": "spoof-version",
                    "outcome_evaluator_contract_sha256": "spoof-contract",
                    "outcome_evaluator_source_sha256": "spoof-source",
                }
                state["hook_return"] = hook_return
                return hook_return
            if result_hook_mode == "fresh_omitted":
                hook_return = {
                    "name": "fresh_omitted_result",
                    "fresh_marker": True,
                }
                state["hook_return"] = hook_return
                return hook_return
            state["hook_return"] = result
            return result

        shared_rows: list[dict[str, Any]] | None = None
        injected_row: dict[str, Any] | None = None

        def progress(
            output_directory: Path,
            rows: list[dict[str, Any]],
            status: str,
            scenario_count: int,
        ) -> None:
            nonlocal shared_rows, injected_row
            del output_directory
            if shared_rows is None:
                shared_rows = rows
            call_number = 1 + sum(
                1 for item in timeline if item.get("call") == "progress_hook"
            )
            timeline.append(
                {
                    "call": "progress_hook",
                    "call_number": call_number,
                    "status": status,
                    "scenario_count": scenario_count,
                    "same_list_identity": rows is shared_rows,
                    "row_names_before": [row.get("name") for row in rows],
                    "run_result_present_by_identity": any(
                        row is state.get("run_result") for row in rows
                    ),
                    "injected_row_present_by_identity": injected_row is not None
                    and any(row is injected_row for row in rows),
                }
            )
            if progress_mode == "raise_initial" and call_number == 1:
                raise RuntimeError("fixture initial-progress failure")
            if progress_mode == "raise_per_task" and call_number == 2:
                raise RuntimeError("fixture per-task-progress failure")
            if progress_mode == "raise_final" and status == "complete":
                raise RuntimeError("fixture final-progress failure")
            if progress_mode != "mutate":
                return
            if call_number == 1:
                injected_row = {
                    "name": "progress_injected_row",
                    "categories": ["injected"],
                    "similarity": 0.125,
                    "turn_count": 0,
                }
                rows.append(injected_row)
            elif call_number == 2:
                state["run_result"]["progress_row_mutation"] = "per_task"
            elif status == "complete":
                state["run_result"]["progress_row_mutation"] = "post_final"
                rows.append({"name": "progress_post_final_row"})

        def final_writer(
            *,
            result_summary: list[dict[str, Any]],
            category_summary: Any,
            output_directory: Path,
        ) -> None:
            state["final_rows"] = result_summary
            timeline.append(
                {
                    "call": "write_result_summary",
                    "row_names": [row.get("name") for row in result_summary],
                }
            )
            (output_directory / "result_summary.json").write_text(
                json.dumps(
                    {
                        "per_scenario_results": result_summary,
                        "category_summary": category_summary,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

        def usage_writer(output_directory: Path) -> None:
            timeline.append({"call": "write_llm_usage_artifacts"})
            (output_directory / "fixture_usage.json").write_text(
                "{}\n", encoding="utf-8"
            )

        patches = {
            "datetime": _FrozenDateTime,
            "tqdm": lambda items, **_kwargs: items,
            "_output_directory": lambda _config: output,
            "write_run_manifest": fake_manifest,
            "install_llm_usage_tracking": lambda: timeline.append(
                {"call": "install_llm_usage_tracking"}
            ),
            "reset_llm_usage": lambda **_kwargs: timeline.append(
                {"call": "reset_llm_usage"}
            ),
            "apply_base_tool_policy": lambda scenario, _policy: scenario,
            "run_one_scenario": run_one,
            "outcome_evaluator_manifest": lambda: dict(evaluator_identity),
            "snapshot_scenario_usage": lambda name: {
                "llm_usage_fixture": name,
                "llm_call_count": 7,
            },
            "clear_scenario_usage": lambda name: timeline.append(
                {"call": "clear_scenario_usage", "name": name}
            ),
            "write_result_summary": final_writer,
            "get_category_summary": lambda rows: {
                "row_names": [row.get("name") for row in rows]
            },
            "write_llm_usage_artifacts": usage_writer,
        }
        with _patch(adapter, **patches):
            invocation = capture(
                lambda: str(
                    adapter.run_scenario_sequence(
                        config,
                        scenarios={"edge_task": {"marker": case_name}},
                        result_hook=result_hook,
                        progress_hook=progress,
                    )
                )
            )

        final_rows = state.get("final_rows")
        identity = {
            "summary_list_is_progress_list": final_rows is not None
            and final_rows is shared_rows,
            "summary_contains_run_result_by_identity": bool(final_rows)
            and any(row is state.get("run_result") for row in final_rows),
            "summary_contains_hook_return_by_identity": bool(final_rows)
            and any(row is state.get("hook_return") for row in final_rows),
        }
        result_path = output / "result_summary.json"
        live_path = output / "live_result_summary.json"
        current_path = output / "currently_running.json"
        return {
            "invocation": invocation,
            "timeline": timeline,
            "identity": identity,
            "closure_row_names_after_return": (
                [row.get("name") for row in shared_rows]
                if shared_rows is not None
                else None
            ),
            "closure_run_result_after_return": copy.deepcopy(state.get("run_result")),
            "result_summary": (
                json.loads(result_path.read_text(encoding="utf-8"))
                if result_path.exists()
                else None
            ),
            "live_summary": (
                json.loads(live_path.read_text(encoding="utf-8"))
                if live_path.exists()
                else None
            ),
            "currently_running_exists": current_path.exists(),
            "usage_artifact_exists": (output / "fixture_usage.json").exists(),
        }

    cases = {
        mode: execute(mode, result_hook_mode=mode)
        for mode in (
            "none",
            "empty",
            "mutate_none",
            "fresh_spoof",
            "fresh_omitted",
        )
    }
    cases["progress_mutation"] = execute("progress_mutation", progress_mode="mutate")
    cases["result_hook_exception"] = execute(
        "result_hook_exception", result_hook_mode="raise"
    )
    for stage in ("initial", "per_task", "final"):
        cases[f"progress_{stage}_exception"] = execute(
            f"progress_{stage}_exception",
            progress_mode=f"raise_{stage}",
        )
    return exact(cases)


class _FixtureRole:
    def __init__(self, label: str, timeline: list[dict[str, Any]]) -> None:
        self.label = label
        self.timeline = timeline
        timeline.append({"call": "role_created", "role": label})

    def teardown(self) -> None:
        self.timeline.append({"call": "role_teardown", "role": self.label})


class RateLimitError(Exception):
    """Named like the real transient provider exception for classifier coverage."""


class DeterministicScenarioFailure(Exception):
    pass


class _RetryScenario:
    categories = ("fixture", "retry")
    max_messages = 9

    def __init__(
        self, *, fail_count: int, terminal: bool, timeline: list[dict[str, Any]]
    ) -> None:
        self.fail_count = fail_count
        self.terminal = terminal
        self.timeline = timeline
        self.attempt = 0

    def play_and_evaluate(
        self, *, roles: Any, output_directory: Path, scenario_name: str
    ) -> Any:
        self.attempt += 1
        self.timeline.append(
            {
                "call": "play_and_evaluate",
                "scenario": scenario_name,
                "attempt": self.attempt,
                "role_count": len(roles),
            }
        )
        if self.terminal:
            raise DeterministicScenarioFailure("terminal fixture failure")
        if self.attempt <= self.fail_count:
            trajectory = output_directory / "trajectories" / scenario_name
            trajectory.mkdir(parents=True, exist_ok=True)
            (trajectory / "attempt.txt").write_text(str(self.attempt), encoding="utf-8")
            raise RateLimitError(f"transient fixture failure {self.attempt}")
        evaluation = SimpleNamespace(
            milestone_mapping={1: ("milestone", 0.75)},
            milestone_similarity=0.75,
            minefield_similarity=1.0,
            similarity=0.875,
            turn_count=3,
            minefield_mapping={2: ("minefield", 1.0)},
        )
        return SimpleNamespace(
            evaluation_result=evaluation, ending_context="ending-context"
        )


def _run_one_contract(
    root: Path, exact: Callable[[Any], dict[str, Any]]
) -> dict[str, Any]:
    import sage_ts.adapters.toolsandbox_adapter as adapter

    timeline: list[dict[str, Any]] = []

    def role_factory(label: str) -> _FixtureRole:
        return _FixtureRole(label, timeline)

    patches = {
        "make_agent": lambda name: role_factory(f"agent:{name}"),
        "make_user": lambda name: role_factory(f"user:{name}"),
        "ExecutionEnvironment": lambda: role_factory("execution_environment"),
        "compute_online_feedback_score": lambda *_args, **_kwargs: {
            "outcome_similarity": 0.625
        },
        "compute_outcome_score": lambda *_args, **_kwargs: {
            "outcome_similarity": 0.875,
            "outcome_milestone_similarity": 0.75,
            "outcome_minefield_similarity": 1.0,
            "outcome_check_count": 2,
            "outcome_checks": ["fixture"],
            "outcome_evaluator_version": "fixture-v1",
            "outcome_evaluator_contract_sha256": "fixture-contract",
            "outcome_evaluator_source_sha256": "fixture-source",
        },
        "outcome_evaluator_manifest": lambda: {
            "version": "fixture-v1",
            "contract_sha256": "fixture-contract",
            "source_sha256": "fixture-source",
        },
    }
    success_scenario = _RetryScenario(fail_count=0, terminal=False, timeline=timeline)
    retry_scenario = _RetryScenario(fail_count=2, terminal=False, timeline=timeline)
    terminal_scenario = _RetryScenario(fail_count=0, terminal=True, timeline=timeline)
    with (
        _patch(adapter, **patches),
        _environment(SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS="3"),
    ):
        success_result = adapter.run_one_scenario(
            "success_task",
            success_scenario,
            agent="FixtureAgent",
            user="FixtureUser",
            output_directory=Path("one-scenario-output"),
        )
        retry_result = adapter.run_one_scenario(
            "retry_task",
            retry_scenario,
            agent="FixtureAgent",
            user="FixtureUser",
            output_directory=Path("one-scenario-output"),
        )
        terminal_result = adapter.run_one_scenario(
            "terminal_task",
            terminal_scenario,
            agent="FixtureAgent",
            user="FixtureUser",
            output_directory=Path("one-scenario-output"),
        )
    normalized_terminal = copy.deepcopy(terminal_result)
    normalized_terminal["traceback"] = re.sub(
        r"line \d+", "line <N>", str(normalized_terminal["traceback"])
    ).replace(str(root), "<SELECTED_ROOT>")
    archives = []
    for path in sorted(
        (Path("one-scenario-output") / "trajectories").glob("retry_task__*")
    ):
        archives.append(
            {
                "name": path.name,
                "attempt_marker": (path / "attempt.txt").read_text(encoding="utf-8"),
            }
        )
    exception_matrix = {
        "named_transient": adapter._is_transient_model_exception(
            RateLimitError("rate"), "fixture traceback"
        ),
        "plain_failure": adapter._is_transient_model_exception(
            DeterministicScenarioFailure("terminal"), "fixture traceback"
        ),
        "truncated_tool_json": adapter._is_transient_model_exception(
            json.JSONDecodeError("Unterminated string", '{"query":"', 10),
            "tool_sandbox/common/message_conversion.py in openai_tool_call_to_python_code",
        ),
        "unrelated_json": adapter._is_transient_model_exception(
            json.JSONDecodeError("Unterminated string", '{"query":"', 10),
            "sage_ts/runtime/registry.py in load_registry",
        ),
    }
    return {
        "first_attempt_success_result": exact(success_result),
        "retry_result": exact(retry_result),
        "terminal_result": exact(normalized_terminal),
        "retry_archives": exact(archives),
        "role_and_attempt_timeline": exact(timeline),
        "exception_classification": exact(exception_matrix),
    }


def _campaign_contract(exact: Callable[[Any], dict[str, Any]]) -> dict[str, Any]:
    import sage_ts.campaign.artifacts as campaign

    def git_value(*args: str) -> str:
        return (
            "fixture-branch" if args == ("branch", "--show-current") else "fixture-sha"
        )

    with _patch(campaign, datetime=_FrozenDateTime, git_value=git_value):
        root = Path("campaign")
        campaign.initialize_campaign(
            root=root,
            phase="publication",
            status="active",
            dashboard_path="dashboard/chapter4.html",
        )
        campaign.append_event(
            "phase_started", {"phase": "runner_fixture", "ordinal": 1}, root=root
        )
        campaign.record_run(
            {"run_root": "run-a", "status": "running", "outcome": 0.75}, root=root
        )
        campaign.record_run(
            {"run_root": "run-b", "status": "complete", "outcome": 0.80}, root=root
        )
        campaign.record_run(
            {"run_root": "run-a", "status": "complete", "outcome": 0.79}, root=root
        )
        registry = Path("campaign-registry")
        registry.mkdir(parents=True)
        (registry / "registry_manifest.json").write_text(
            '{"tools":{"fixture_tool":{"version":1}}}\n', encoding="utf-8"
        )
        snapshot = campaign.snapshot_registry(
            registry, name="fixture_registry", root=root
        )
        try:
            campaign.append_event("not_a_real_event", root=root)
        except Exception as error:  # noqa: BLE001 - failure text is the contract.
            unknown_event = {"type": type(error).__name__, "message": str(error)}
        else:  # pragma: no cover - selected source currently rejects this.
            unknown_event = {"type": None, "message": None}
    return {
        "campaign_status": _json_contract(root / "campaign_status.json", exact),
        "task_plan": _json_contract(root / "task_plan.json", exact),
        "dated_event_ledger": _jsonl_contract(
            root / "events" / "20260926.jsonl", exact
        ),
        "latest_event_ledger": _jsonl_contract(root / "events" / "latest.jsonl", exact),
        "run_index": _json_contract(root / "run_index.json", exact),
        "registry_snapshot": _json_contract(snapshot, exact) if snapshot else None,
        "unknown_event_failure": unknown_event,
    }


def _environment_contract(
    exact: Callable[[Any], dict[str, Any]],
    capture: Callable[[Callable[[], Any]], dict[str, Any]],
) -> dict[str, Any]:
    import scripts.verify_publication_environment as verifier

    fixture = Path("environment-fixture").resolve()
    repo = fixture / "repo"
    repo.mkdir(parents=True)
    lock = repo / "requirements-publication-lock.txt"
    lock.write_text("Alpha_Package==1.2.3\nbeta.package==2.0\n", encoding="utf-8")
    lock_hash = _sha256(lock)
    import_paths = {
        "sage_ts": repo / "src" / "sage_ts" / "__init__.py",
        "tool_sandbox": repo / "tool_sandbox" / "__init__.py",
    }
    for path in import_paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    records = (
        verifier.DistributionRecord(
            name="beta.package",
            version="2.0",
            metadata_path=fixture / "site-packages" / "beta.dist-info",
        ),
        verifier.DistributionRecord(
            name="Alpha-Package",
            version="1.2.3",
            metadata_path=fixture / "site-packages" / "alpha.dist-info",
        ),
        verifier.DistributionRecord(
            name="tool_sandbox",
            version="0.0.1",
            metadata_path=repo / "tool_sandbox.egg-info",
        ),
        verifier.DistributionRecord(
            name="toolsandbox-sage",
            version="0.1.0",
            metadata_path=fixture / "site-packages" / "toolsandbox_sage.dist-info",
            direct_url_json=json.dumps(
                {"dir_info": {"editable": True}, "url": repo.as_uri()}
            ),
        ),
    )
    checker_calls: list[dict[str, Any]] = []

    def import_checker(python: str, requested_repo: Path) -> dict[str, str]:
        checker_calls.append({"python": python, "repo": str(requested_repo)})
        return {name: str(path) for name, path in import_paths.items()}

    common: dict[str, Any] = {
        "repo_root": repo,
        "expected_lock_sha256": lock_hash,
        "python_version": (3, 12, 7),
        "python_executable": str(fixture / "venv" / "bin" / "python"),
        "python_prefix": str(fixture / "venv"),
        "python_base_prefix": str(fixture / "base"),
        "python_implementation": "CPython",
        "platform_system": "Darwin",
        "platform_machine": "arm64",
        "installed_distributions": records,
        "pip_checker": lambda: "No broken requirements found.",
        "repository_import_checker": import_checker,
    }
    report = verifier.verify_environment(lock, **common)

    def failure(**updates: Any) -> dict[str, Any]:
        kwargs = {**common, **updates}
        return capture(lambda: verifier.verify_environment(lock, **kwargs))

    malformed_lock = repo / "malformed-lock.txt"
    malformed_lock.write_text("Alpha-Package>=1.2.3\n", encoding="utf-8")
    foreign = fixture / "foreign" / "sage_ts" / "__init__.py"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("", encoding="utf-8")
    sibling = fixture / "repo-sibling" / "sage_ts" / "__init__.py"
    sibling.parent.mkdir(parents=True)
    sibling.write_text("", encoding="utf-8")
    shared_prefix = fixture / "repository" / "sage_ts" / "__init__.py"
    shared_prefix.parent.mkdir(parents=True)
    shared_prefix.write_text("", encoding="utf-8")

    def editable_relationship(path: Path) -> dict[str, Any]:
        project_record = verifier.DistributionRecord(
            name="toolsandbox-sage",
            version="0.1.0",
            metadata_path=fixture / "site-packages" / "toolsandbox_sage.dist-info",
            direct_url_json=json.dumps(
                {"dir_info": {"editable": True}, "url": path.as_uri()}
            ),
        )
        try:
            result = verifier.verify_environment(
                lock,
                **{
                    **common,
                    "installed_distributions": (*records[:-1], project_record),
                },
            )
        except Exception as error:  # noqa: BLE001 - failure text is the contract.
            return {
                "status": "raised",
                "exception_type": type(error).__name__,
                "message": str(error),
            }
        return {"status": "returned", "result": result}

    editable_path_relationships = {
        "equal": editable_relationship(repo),
        "descendant": editable_relationship(repo / "nested-project"),
        "sibling": editable_relationship(fixture / "repo-sibling"),
        "shared_prefix": editable_relationship(fixture / "repository"),
    }

    failures = {
        "python_version": failure(python_version=(3, 12, 6)),
        "nonisolated_environment": failure(
            python_prefix=str(fixture / "base"),
            python_base_prefix=str(fixture / "base"),
        ),
        "platform": failure(platform_system="Linux", platform_machine="x86_64"),
        "lock_hash": failure(expected_lock_sha256="0" * 64),
        "missing_distribution": failure(installed_distributions=records[1:]),
        "version_mismatch": failure(
            installed_distributions=(
                verifier.DistributionRecord(
                    name="beta.package",
                    version="9.0",
                    metadata_path=fixture / "site-packages" / "beta.dist-info",
                ),
                *records[1:],
            )
        ),
        "unexpected_distribution": failure(
            installed_distributions=(
                *records,
                verifier.DistributionRecord(
                    name="surprise",
                    version="1.0",
                    metadata_path=fixture / "site-packages" / "surprise.dist-info",
                ),
            )
        ),
        "duplicate_distribution": failure(
            installed_distributions=(*records, records[0])
        ),
        "missing_editable_project": failure(installed_distributions=records[:-1]),
        "pip_failure": failure(
            pip_checker=lambda: (_ for _ in ()).throw(
                verifier.EnvironmentVerificationError(
                    "pip dependency check failed: fixture broken"
                )
            )
        ),
        "import_provenance": failure(
            repository_import_checker=lambda _python, _repo: {
                **{name: str(path) for name, path in import_paths.items()},
                "sage_ts": str(foreign),
            }
        ),
        "import_provenance_sibling": failure(
            repository_import_checker=lambda _python, _repo: {
                **{name: str(path) for name, path in import_paths.items()},
                "sage_ts": str(sibling),
            }
        ),
        "import_provenance_shared_prefix": failure(
            repository_import_checker=lambda _python, _repo: {
                **{name: str(path) for name, path in import_paths.items()},
                "sage_ts": str(shared_prefix),
            }
        ),
        "malformed_lock": capture(
            lambda: verifier.verify_environment(
                malformed_lock,
                **{
                    **common,
                    "expected_lock_sha256": _sha256(malformed_lock),
                },
            )
        ),
    }
    replacements = ((str(fixture), "<FIXTURE_ROOT>"),)
    normalized_report = _stable(report, replacements)
    normalized_failures = _stable(failures, replacements)
    normalized_relationships = _stable(editable_path_relationships, replacements)
    return {
        "pass_report": exact(normalized_report),
        "import_checker_calls": exact(_stable(checker_calls, replacements)),
        "failure_contracts": exact(normalized_failures),
        "editable_path_relationships": exact(normalized_relationships),
        "expected_external_distribution_lines": [
            "alpha-package==1.2.3\n",
            "beta-package==2.0\n",
        ],
    }


class _VisibleFacts:
    primary_family_key = "fixture_family"

    def routing_text(self) -> str:
        return "fixture routing text"

    def generation_label(self) -> str:
        return "fixture generation label"


class _Observation:
    def __init__(self, scenario: str) -> None:
        self.scenario = scenario

    def to_json(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "family": "fixture_family",
            "route": "repair",
        }


def _checkpoint_edge_contract(
    exact: Callable[[Any], dict[str, Any]],
    capture: Callable[[Callable[[], Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Freeze sparse checkpoint, index fallback, and I/O failure semantics."""

    import sage_ts.adapters.sage_run_adapter as sage_runner

    def inventory(root: Path) -> list[dict[str, Any]]:
        if not root.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(root.rglob("*")):
            row: dict[str, Any] = {
                "path": path.relative_to(root).as_posix(),
                "kind": "directory" if path.is_dir() else "file",
            }
            if path.is_file():
                row["text"] = path.read_text(encoding="utf-8")
            rows.append(row)
        return rows

    def execute(
        case_name: str,
        *,
        source_files: tuple[str, ...],
        order_index: str | None,
        failure: str | None = None,
    ) -> dict[str, Any]:
        output = Path(f"checkpoint-edge-{case_name}-output")
        registry = Path(f"checkpoint-edge-{case_name}-registry")
        registry.mkdir(parents=True)
        for filename in source_files:
            (registry / filename).write_text(
                json.dumps({"fixture": filename, "case": case_name}) + "\n",
                encoding="utf-8",
            )

        def invoke() -> str | None:
            result = sage_runner._snapshot_registry_checkpoint(
                output_directory=output,
                registry_dir=registry,
                scenario_name="fixture / checkpoint task",
            )
            return result.as_posix() if result is not None else None

        with _environment(SAGE_TS_SCENARIO_ORDER_INDEX=order_index):
            if failure == "copy":

                def fail_copy(*_args: Any, **_kwargs: Any) -> None:
                    raise OSError("fixture checkpoint copy failure")

                with _patch(sage_runner.shutil, copy2=fail_copy):
                    invocation = capture(invoke)
            elif failure == "write":
                original_write_text = Path.write_text

                def fail_metadata_write(path: Path, *args: Any, **kwargs: Any) -> int:
                    if path.name == "checkpoint.json":
                        raise OSError("fixture checkpoint metadata write failure")
                    return original_write_text(path, *args, **kwargs)

                with _patch(Path, write_text=fail_metadata_write):
                    invocation = capture(invoke)
            else:
                invocation = capture(invoke)
        return {
            "invocation": invocation,
            "output_inventory": inventory(output),
            "source_inventory": inventory(registry),
        }

    cases = {
        "empty_registry": execute("empty_registry", source_files=(), order_index="0"),
        "one_file_registry": execute(
            "one_file_registry",
            source_files=("registry_manifest.json",),
            order_index="4",
        ),
        "unset_order_index": execute(
            "unset_order_index",
            source_files=("tool_lifecycle.json",),
            order_index=None,
        ),
        "invalid_order_index": execute(
            "invalid_order_index",
            source_files=("registry_manifest.json", "tool_lifecycle.json"),
            order_index="not-an-integer",
        ),
        "copy_failure": execute(
            "copy_failure",
            source_files=("registry_manifest.json",),
            order_index="1",
            failure="copy",
        ),
        "metadata_write_failure": execute(
            "metadata_write_failure",
            source_files=("registry_manifest.json",),
            order_index="2",
            failure="write",
        ),
    }
    return exact(cases)


def _sage_mode_contract(
    *,
    online: bool,
    exact: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    import sage_ts.adapters.sage_run_adapter as sage_runner
    from tool_sandbox.common.execution_context import ExecutionContext
    from tool_sandbox.common.scenario import Scenario

    mode = "online" if online else "frozen"
    timeline: list[dict[str, Any]] = []
    external_events: list[dict[str, Any]] = []
    registry = Path(f"{mode}-registry")
    registry.mkdir(parents=True)
    (registry / "registry_manifest.json").write_text('{"tools":{}}\n', encoding="utf-8")
    (registry / "tool_lifecycle.json").write_text(
        '{"tool_lifecycle":{}}\n', encoding="utf-8"
    )
    scenario = Scenario(
        starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
    )
    original_checkpoint = sage_runner._snapshot_registry_checkpoint

    class FakeBirthController:
        def __init__(self, **kwargs: Any) -> None:
            timeline.append(
                {
                    "call": "birth_controller_init",
                    "recurrence_threshold": kwargs["recurrence_threshold"],
                }
            )
            self.pre_scenario_visible_observations = {"fixture_task"}

        def prime_before_scenario(self, name: str, _scenario: Any) -> list[str]:
            timeline.append({"call": "prime_before_scenario", "scenario": name})
            return ["fixture_general_tool"]

        def observe(self, observation: _Observation) -> None:
            timeline.append(
                {"call": "birth_observe", "observation": observation.to_json()}
            )

    class FakeReflection:
        @classmethod
        def from_env(cls, **_kwargs: Any) -> "FakeReflection":
            timeline.append({"call": "reflection_from_env"})
            return cls()

        def assess_scenario(self, **kwargs: Any) -> None:
            timeline.append(
                {
                    "call": "reflection_assess_scenario",
                    "scenario": kwargs["scenario_name"],
                    "selection_status": kwargs["selection_record"]["selection_status"],
                }
            )

        def assert_fresh_control_complete(self, names: tuple[str, ...]) -> None:
            timeline.append(
                {"call": "assert_fresh_control_complete", "scenarios": list(names)}
            )

    def fake_sequence(config: Any, **kwargs: Any) -> Path:
        output = Path(f"{mode}-run")
        output.mkdir(parents=True)
        os.environ["SAGE_TS_CURRENT_SCENARIO"] = "fixture_task"
        os.environ["SAGE_TS_SCENARIO_ORDER_INDEX"] = "0"
        timeline.append({"call": "sequence_transform_enter"})
        active = kwargs["scenario_transform"]("fixture_task", scenario, output)
        timeline.append({"call": "sequence_result_hook_enter"})
        result = kwargs["result_hook"](
            "fixture_task",
            active,
            {
                "name": "fixture_task",
                "similarity": 0.25,
                "outcome_similarity": 0.5,
                "online_feedback_outcome_similarity": 0.4,
                "exception_type": None,
            },
            output,
        )
        timeline.append(
            {
                "call": "sequence_result_hook_return",
                "result_keys": list(result),
                "sage_observations": result.get("sage_observations"),
            }
        )
        return output

    def checkpoint(**kwargs: Any) -> Path | None:
        result = original_checkpoint(**kwargs)
        timeline.append(
            {
                "call": "registry_checkpoint_written",
                "path": result.as_posix() if result else None,
            }
        )
        return result

    def event_hook(event: str, _output: Path, payload: dict[str, Any]) -> None:
        external_events.append({"event": event, "payload": copy.deepcopy(payload)})
        timeline.append({"call": "external_event", "event": event})

    patches = {
        "run_scenario_sequence": fake_sequence,
        "visible_task_context_from_scenario": lambda _scenario: _VisibleFacts(),
        "load_tool_lifecycle_routing_state": lambda _root: {},
        "route_registry_entries": lambda *_args, **_kwargs: ({}, {}),
        "with_registry_tools": lambda scenario, *_args, **_kwargs: scenario,
        "_snapshot_registry_checkpoint": checkpoint,
        "classify_visible_task_observations": lambda *_args: (_Observation("visible"),),
        "classify_visible_trace_observations": lambda name, *_args: (
            _Observation(name),
        ),
        "OnlineBirthController": FakeBirthController,
        "SelfEvolutionReflectionController": FakeReflection,
    }
    with _patch(sage_runner, **patches):
        output = sage_runner.run_sage_with_registry(
            sage_runner.SageRunConfig(
                agent="FixtureAgent",
                user="FixtureUser",
                scenario_names=("fixture_task",),
                output_dir=Path(f"{mode}-output"),
                registry_dir=registry,
                run_type=f"sage_{mode}",
                recurrence_threshold=2,
                manifest_path=Path("fixture-manifest.json"),
                failure_memory_path=None,
            ),
            generator=object() if online else None,
            scenarios={"fixture_task": scenario},
            event_hook=event_hook,
        )
    checkpoint_root = output / "registry_checkpoints"
    checkpoint_dirs = sorted(
        path for path in checkpoint_root.iterdir() if path.is_dir()
    )
    checkpoint_contracts = []
    for directory in checkpoint_dirs:
        checkpoint_contracts.append(
            {
                "name": directory.name,
                "metadata": _json_contract(directory / "checkpoint.json", exact),
                "registry_manifest": _json_contract(
                    directory / "registry_manifest.json", exact
                ),
                "lifecycle": _json_contract(directory / "tool_lifecycle.json", exact),
            }
        )
    return {
        "mode": mode,
        "timeline": exact(timeline),
        "external_events": exact(external_events),
        "sage_run_events": _jsonl_contract(output / "sage_run_events.jsonl", exact),
        "visibility": _jsonl_contract(output / "scenario_tool_visibility.jsonl", exact),
        "selection": _jsonl_contract(output / "scenario_tool_selection.jsonl", exact),
        "selection_summary": _json_contract(output / "selection_summary.json", exact),
        "checkpoint_contracts": checkpoint_contracts,
    }


def _sage_selection_edge_contract(
    exact: Callable[[Any], dict[str, Any]],
    capture: Callable[[Callable[[], Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Freeze nonempty generated-tool accounting and checkpoint-event failure."""

    import sage_ts.adapters.sage_run_adapter as sage_runner

    generated_names = (
        "attempted_only_tool",
        "called_tool",
        "failed_tool",
        "visible_only_tool",
    )

    class FakeContext:
        def __init__(self, tool_names: tuple[str, ...]) -> None:
            self.name_to_tool = {name: object() for name in tool_names}
            self._tool_names = tool_names
            self.tool_allow_list = list(tool_names)

        def get_available_tools(self, *, scrambling_allowed: bool) -> tuple[str, ...]:
            if scrambling_allowed:
                raise AssertionError("fixture requires unscrambled tool discovery")
            return self._tool_names

    class FakeStore:
        def __init__(self, root: Path) -> None:
            self.root = root
            self.entries = {
                name: SimpleNamespace(
                    tool=SimpleNamespace(
                        spec=SimpleNamespace(required_original_tool_calls=())
                    )
                )
                for name in generated_names
            }
            self.reuse_calls: list[str] = []

        def load_entries(self) -> dict[str, Any]:
            return dict(self.entries)

        def record_reuse(self, tool_name: str) -> None:
            self.reuse_calls.append(tool_name)

    class FakeRoutingDecision:
        visible = True
        reason = "fixture_visible"

        def __init__(self, tool_name: str) -> None:
            self.tool_name = tool_name

        def to_json(self) -> dict[str, Any]:
            return {
                "tool_name": self.tool_name,
                "visible": self.visible,
                "reason": self.reason,
            }

    def read_jsonl(path: Path) -> list[Any] | None:
        if not path.exists():
            return None
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]

    def checkpoint_inventory(output: Path) -> list[str]:
        checkpoint_root = output / "registry_checkpoints"
        if not checkpoint_root.exists():
            return []
        return [
            path.relative_to(output).as_posix()
            for path in sorted(checkpoint_root.rglob("*"))
        ]

    def execute(case_name: str, *, fail_checkpoint_event: bool) -> dict[str, Any]:
        timeline: list[dict[str, Any]] = []
        registry = Path(f"sage-selection-{case_name}-registry")
        registry.mkdir(parents=True)
        (registry / "registry_manifest.json").write_text(
            '{"tools":{"fixture":true}}\n', encoding="utf-8"
        )
        (registry / "tool_lifecycle.json").write_text(
            '{"tool_lifecycle":{"fixture":true}}\n', encoding="utf-8"
        )
        store = FakeStore(registry)
        base_scenario = SimpleNamespace(
            starting_context=FakeContext(("native_fixture_tool",))
        )
        output = Path(f"sage-selection-{case_name}-run")

        def fake_sequence(_config: Any, **kwargs: Any) -> Path:
            output.mkdir(parents=True)
            with _environment(
                SAGE_TS_CURRENT_SCENARIO="selection_task",
                SAGE_TS_SCENARIO_ORDER_INDEX="0",
            ):
                timeline.append({"call": "sequence_transform_enter"})
                active = kwargs["scenario_transform"](
                    "selection_task", base_scenario, output
                )
                timeline.append({"call": "sequence_result_hook_enter"})
                result = kwargs["result_hook"](
                    "selection_task",
                    active,
                    {
                        "name": "selection_task",
                        "similarity": 0.6,
                        "outcome_similarity": 0.8,
                        "exception_type": None,
                    },
                    output,
                )
                timeline.append(
                    {
                        "call": "sequence_result_hook_return",
                        "result_keys": list(result),
                    }
                )
            return output

        def inject_tools(
            scenario: Any,
            _store: Any,
            *,
            on_reuse: Callable[[str], None],
            **_kwargs: Any,
        ) -> Any:
            timeline.append({"call": "with_registry_tools"})
            on_reuse("called_tool")
            return SimpleNamespace(
                starting_context=FakeContext(
                    (*generated_names, *scenario.starting_context.name_to_tool)
                )
            )

        def route_entries(
            entries: dict[str, Any], *_args: Any, **_kwargs: Any
        ) -> tuple[dict[str, Any], dict[str, Any]]:
            decisions = {name: FakeRoutingDecision(name) for name in entries}
            return dict(entries), decisions

        original_append = sage_runner.append_jsonl

        def append_with_optional_failure(path: Path, payload: dict[str, Any]) -> None:
            if (
                fail_checkpoint_event
                and payload.get("event") == "registry_checkpoint_written"
            ):
                timeline.append(
                    {
                        "call": "append_jsonl_failure",
                        "path": path.as_posix(),
                        "event": payload.get("event"),
                    }
                )
                raise OSError("fixture checkpoint-event JSONL append failure")
            original_append(path, payload)

        patches = {
            "RegistryStore": lambda _root: store,
            "run_scenario_sequence": fake_sequence,
            "visible_task_context_from_scenario": lambda _scenario: _VisibleFacts(),
            "load_tool_lifecycle_routing_state": lambda _root: {},
            "route_registry_entries": route_entries,
            "with_registry_tools": inject_tools,
            "_conversation_generated_tool_attempts": (
                lambda *_args, **_kwargs: (
                    ["attempted_only_tool", "failed_tool", "called_tool"],
                    ["failed_tool"],
                )
            ),
            "_reconcile_generated_tool_calls_from_conversation": (
                lambda _output, _name, _visible, called: list(called)
            ),
            "native_action_tool_enabled": lambda _tool: True,
            "append_jsonl": append_with_optional_failure,
        }
        with _patch(sage_runner, **patches):
            invocation = capture(
                lambda: str(
                    sage_runner.run_sage_with_registry(
                        sage_runner.SageRunConfig(
                            agent="FixtureAgent",
                            user="FixtureUser",
                            scenario_names=("selection_task",),
                            output_dir=Path(f"sage-selection-{case_name}-output"),
                            registry_dir=registry,
                            run_type="sage_frozen",
                            recurrence_threshold=2,
                            manifest_path=Path("fixture-manifest.json"),
                            failure_memory_path=None,
                        ),
                        generator=None,
                        scenarios={"selection_task": base_scenario},
                    )
                )
            )
        selection_summary_path = output / "selection_summary.json"
        return {
            "invocation": invocation,
            "timeline": timeline,
            "reuse_calls": list(store.reuse_calls),
            "visibility_rows": read_jsonl(output / "scenario_tool_visibility.jsonl"),
            "selection_rows": read_jsonl(output / "scenario_tool_selection.jsonl"),
            "reuse_rows": read_jsonl(output / "reuse_events.jsonl"),
            "sage_run_events": read_jsonl(output / "sage_run_events.jsonl"),
            "selection_summary": (
                json.loads(selection_summary_path.read_text(encoding="utf-8"))
                if selection_summary_path.exists()
                else None
            ),
            "checkpoint_inventory": checkpoint_inventory(output),
        }

    return exact(
        {
            "nonempty_selection_sets": execute(
                "nonempty_selection_sets", fail_checkpoint_event=False
            ),
            "checkpoint_event_append_failure": execute(
                "checkpoint_event_append_failure", fail_checkpoint_event=True
            ),
        }
    )


def run_probe(
    root: Path,
    *,
    exact: Callable[[Any], dict[str, Any]],
    capture: Callable[[Callable[[], Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Return the complete deterministic runner/provenance snapshot."""

    source_hashes = _source_hashes(root)
    with tempfile.TemporaryDirectory(prefix="sage-runner-provenance-") as temporary:
        fixture_root = Path(temporary)
        with _working_directory(fixture_root):
            payload = {
                "run_manifest": _run_manifest_contract(exact),
                "scenario_sequence": _sequence_contract(exact),
                "scenario_sequence_edges": _sequence_edge_contract(exact, capture),
                "scenario_retry_and_terminal_failure": _run_one_contract(root, exact),
                "frozen_run_checkpoint_order": _sage_mode_contract(
                    online=False, exact=exact
                ),
                "online_run_checkpoint_order": _sage_mode_contract(
                    online=True, exact=exact
                ),
                "checkpoint_edges": _checkpoint_edge_contract(exact, capture),
                "generated_selection_edges": _sage_selection_edge_contract(
                    exact, capture
                ),
                "campaign_artifacts": _campaign_contract(exact),
                "environment_verifier": _environment_contract(exact, capture),
            }
    return {
        "contract_schema_version": 2,
        "contract_sections": ["frozen_source_hashes", *payload],
        "frozen_source_hashes": source_hashes,
        **payload,
    }
