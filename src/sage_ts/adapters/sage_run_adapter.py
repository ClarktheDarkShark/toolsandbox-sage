"""ToolSandbox runner with accepted SAGE registry tools injected."""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path

from sage_ts.adapters.toolsandbox_adapter import (
    EventHook,
    ProgressHook,
    ToolSandboxRunConfig,
    run_scenario_sequence,
)
from sage_ts.adequacy.inadequacy_classifier import classify_scenario_observations
from sage_ts.orchestration.checkpoints import append_jsonl
from sage_ts.orchestration.online_birth import (
    GeneratedToolFactory,
    OnlineBirthController,
)
from sage_ts.registry.store import RegistryStore
from sage_ts.runtime.base_toolset import UPSTREAM_POLICY
from sage_ts.runtime.toolsandbox_integration import (
    route_registry_entries,
    with_registry_tools,
)
from tool_sandbox.common.scenario import Scenario


def _reuse_log_tools(output_directory: Path, scenario_name: str) -> list[str]:
    path = output_directory / "reuse_events.jsonl"
    if not path.exists():
        return []
    tools: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("scenario") != scenario_name:
            continue
        tool_name = event.get("tool_name")
        if isinstance(tool_name, str) and tool_name not in tools:
            tools.append(tool_name)
    return tools


def _selection_log_rows(output_directory: Path) -> list[dict[str, object]]:
    path = output_directory / "scenario_tool_selection.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _conversation_generated_tool_attempts(
    output_directory: Path,
    scenario_name: str,
    generated_tools: list[str],
) -> tuple[list[str], list[str]]:
    """Return generated tools attempted in the transcript, including failures."""
    generated_tool_set = set(generated_tools)
    if not generated_tool_set:
        return [], []
    path = output_directory / "trajectories" / scenario_name / "conversation.json"
    if not path.exists():
        return [], []
    try:
        messages = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [], []
    if not isinstance(messages, list):
        return [], []

    attempted: list[str] = []
    failed: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    continue
                function = tool_call.get("function")
                if not isinstance(function, dict):
                    continue
                tool_name = function.get("name")
                if isinstance(tool_name, str) and tool_name in generated_tool_set:
                    if tool_name not in attempted:
                        attempted.append(tool_name)
        if message.get("role") == "tool":
            tool_name = message.get("name")
            if not isinstance(tool_name, str) or tool_name not in generated_tool_set:
                continue
            if tool_name not in attempted:
                attempted.append(tool_name)
            content = str(message.get("content", ""))
            if (
                "Error:" in content
                or content.startswith(("TypeError", "ValueError", "ValidationError"))
                or "Traceback" in content
            ) and tool_name not in failed:
                failed.append(tool_name)
    return attempted, failed


def _parse_tool_message_content(raw_content: object) -> object:
    if isinstance(raw_content, (dict, list, int, float, bool)) or raw_content is None:
        return raw_content
    if not isinstance(raw_content, str):
        return None
    text = raw_content.strip()
    if not text:
        return ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return text


def _conversation_generated_tool_results(
    output_directory: Path,
    scenario_name: str,
    generated_tools: list[str],
) -> dict[str, list[object]]:
    generated_tool_set = set(generated_tools)
    if not generated_tool_set:
        return {}
    path = output_directory / "trajectories" / scenario_name / "conversation.json"
    if not path.exists():
        return {}
    try:
        messages = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(messages, list):
        return {}

    results: dict[str, list[object]] = {}
    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("role") != "tool":
            continue
        tool_name = message.get("name")
        if not isinstance(tool_name, str) or tool_name not in generated_tool_set:
            continue
        results.setdefault(tool_name, []).append(
            _parse_tool_message_content(message.get("content"))
        )
    return results


def _helper_requires_side_effect_followup(helper_outputs: list[object]) -> bool:
    if not helper_outputs:
        return True
    requires_followup = False
    saw_explicit_flag = False
    for item in helper_outputs:
        if not isinstance(item, dict):
            requires_followup = True
            continue
        if "should_call_add_reminder" in item:
            saw_explicit_flag = True
            if bool(item.get("should_call_add_reminder")):
                requires_followup = True
        elif "should_call" in item:
            saw_explicit_flag = True
            if bool(item.get("should_call")):
                requires_followup = True
        else:
            requires_followup = True
    if saw_explicit_flag:
        return requires_followup
    return True


def _helper_forbids_side_effect_followup(helper_outputs: list[object]) -> bool:
    if not helper_outputs:
        return False
    saw_explicit_flag = False
    for item in helper_outputs:
        if not isinstance(item, dict):
            continue
        if "should_call_add_reminder" in item:
            saw_explicit_flag = True
            if bool(item.get("should_call_add_reminder")):
                return False
        elif "should_call" in item:
            saw_explicit_flag = True
            if bool(item.get("should_call")):
                return False
    return saw_explicit_flag


def _assistant_tool_names(message: dict[str, object]) -> list[str]:
    names: list[str] = []
    tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list):
        return names
    for tool_call in tool_calls:
        if not isinstance(tool_call, dict):
            continue
        function = tool_call.get("function")
        if not isinstance(function, dict):
            continue
        tool_name = function.get("name")
        if isinstance(tool_name, str):
            names.append(tool_name)
    return names


def _next_assistant_tool_names(
    messages: list[object],
    *,
    start_index: int,
) -> list[str]:
    for lookahead in messages[start_index + 1 :]:
        if not isinstance(lookahead, dict):
            continue
        if lookahead.get("role") == "user":
            return []
        if lookahead.get("role") == "assistant" and lookahead.get("tool_calls"):
            return _assistant_tool_names(lookahead)
    return []


def _side_effect_followup_failures(
    messages: list[object],
    *,
    helper_name: str,
    required_original_tool_calls: tuple[str, ...],
) -> bool:
    """Return True when a helper's declared follow-up contract is violated.

    Abstaining helpers should not trigger their side-effect tool directly, but
    they may resolve missing prerequisites first and call the side-effect later.
    """

    if not required_original_tool_calls:
        return False
    saw_helper_result = False
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        if message.get("role") != "tool" or message.get("name") != helper_name:
            continue
        saw_helper_result = True
        output = _parse_tool_message_content(message.get("content"))
        next_tools = set(_next_assistant_tool_names(messages, start_index=index))
        required = set(required_original_tool_calls)
        if isinstance(output, dict):
            if (
                output.get("should_call_add_reminder") is False
                or output.get("should_call") is False
            ):
                if required & next_tools:
                    return True
                continue
            if (
                output.get("should_call_add_reminder") is True
                or output.get("should_call") is True
            ):
                if not (required & next_tools):
                    return True
                continue
        later_tools: set[str] = set()
        for later in messages[index + 1 :]:
            if isinstance(later, dict) and later.get("role") == "assistant":
                later_tools.update(_assistant_tool_names(later))
        if not (required & later_tools):
            return True
    return not saw_helper_result


@dataclass(frozen=True)
class SageRunConfig:
    agent: str
    user: str
    scenario_names: tuple[str, ...]
    output_dir: Path
    registry_dir: Path
    run_type: str = "sage_online"
    recurrence_threshold: int = 2
    base_tool_policy: str = UPSTREAM_POLICY
    resume_from_dir: Path | None = None


def run_sage_with_registry(
    config: SageRunConfig,
    *,
    generator: GeneratedToolFactory | None = None,
    progress_hook: ProgressHook | None = None,
    event_hook: EventHook | None = None,
) -> Path:
    """Run ToolSandbox scenarios with accepted generated tools available."""
    store = RegistryStore(config.registry_dir)
    registry_tools = sorted(store.load_entries())
    visible_generated_by_scenario: dict[str, list[str]] = {}
    called_generated_by_scenario: dict[str, list[str]] = {}
    selection_context_by_scenario: dict[str, dict[str, object]] = {}

    birth_controller: OnlineBirthController | None = None
    registry_load_logged = False
    mutate_registry_reuse_counts = generator is not None

    def transform(name: str, scenario: Scenario, output_directory: Path) -> Scenario:
        nonlocal birth_controller, registry_load_logged
        if generator is not None and birth_controller is None:

            def birth_event_hook(event: str, payload: dict[str, object]) -> None:
                if event_hook is not None:
                    event_hook(event, output_directory, payload)

            birth_controller = OnlineBirthController(
                store=store,
                generator=generator,
                output_dir=output_directory,
                recurrence_threshold=config.recurrence_threshold,
                event_hook=birth_event_hook,
            )
        if not registry_load_logged:
            append_jsonl(
                output_directory / "sage_run_events.jsonl",
                {
                    "event": "registry_load",
                    "registry_dir": str(config.registry_dir),
                    "registry_tools": registry_tools,
                    "registry_size": len(registry_tools),
                    "base_tool_policy": config.base_tool_policy,
                    "generation_enabled": generator is not None,
                },
            )
            if event_hook is not None:
                event_hook(
                    "registry_loaded",
                    output_directory,
                    {
                        "registry_dir": str(config.registry_dir),
                        "registry_tools": registry_tools,
                        "registry_size": len(registry_tools),
                        "base_tool_policy": config.base_tool_policy,
                        "generation_enabled": generator is not None,
                    },
                )
            registry_load_logged = True

        def record_reuse(tool_name: str) -> None:
            if mutate_registry_reuse_counts:
                store.record_reuse(tool_name)
            called = called_generated_by_scenario.setdefault(name, [])
            if tool_name not in called:
                called.append(tool_name)
            append_jsonl(
                output_directory / "reuse_events.jsonl",
                {
                    "scenario": name,
                    "tool_name": tool_name,
                    "event": "generated_tool_invoked",
                },
            )
            if event_hook is not None:
                event_hook(
                    "tool_reused",
                    output_directory,
                    {
                        "scenario": name,
                        "tool_name": tool_name,
                        "registry_dir": str(config.registry_dir),
                    },
                )

        loaded_entries = store.load_entries()
        retained_tools_loaded = sorted(loaded_entries)
        available_base_tools = set(
            scenario.starting_context.get_available_tools(scrambling_allowed=False)
        )
        _routed_entries, routing_decisions = route_registry_entries(
            loaded_entries,
            name,
            available_base_tools=available_base_tools,
        )
        visibility_by_tool = {
            tool_name: (decision.visible, decision.reason)
            for tool_name, decision in routing_decisions.items()
        }
        shortlisted_generated_tools = [
            tool_name
            for tool_name, (is_visible, _reason) in visibility_by_tool.items()
            if is_visible
        ]
        filtered_out_generated_tools = [
            tool_name
            for tool_name in retained_tools_loaded
            if tool_name not in set(shortlisted_generated_tools)
        ]
        filtered_out_reasons = {
            tool_name: visibility_by_tool.get(
                tool_name, (False, "scenario_relevance_filter")
            )[1]
            for tool_name in filtered_out_generated_tools
        }
        original_tool_order = list(scenario.starting_context.name_to_tool)
        enhanced = with_registry_tools(
            scenario,
            store,
            on_reuse=record_reuse,
            scenario_name=name,
        )
        enhanced_tool_order = list(enhanced.starting_context.name_to_tool)
        available_tools = set(
            enhanced.starting_context.get_available_tools(scrambling_allowed=False)
        )
        generated_tools = [
            tool_name
            for tool_name in sorted(store.load_entries())
            if tool_name in available_tools
        ]
        visible_generated_by_scenario[name] = generated_tools
        priority_injection_changed_tool_order = bool(
            generated_tools
            and enhanced_tool_order[: len(generated_tools)] == generated_tools
            and enhanced_tool_order != original_tool_order
        )
        selection_context_by_scenario[name] = {
            "retained_tools_loaded": retained_tools_loaded,
            "filtered_out_generated_tools": filtered_out_generated_tools,
            "filtered_out_reasons": filtered_out_reasons,
            "shortlisted_generated_tools": shortlisted_generated_tools,
            "priority_injection_changed_tool_order": (
                priority_injection_changed_tool_order
            ),
            "relevance_gating_hid_retained_tool": bool(filtered_out_generated_tools),
        }
        append_jsonl(
            output_directory / "scenario_tool_visibility.jsonl",
            {
                "scenario": name,
                "base_tool_policy": config.base_tool_policy,
                "retained_tools_loaded": retained_tools_loaded,
                "filtered_out_generated_tools": filtered_out_generated_tools,
                "filtered_out_reasons": filtered_out_reasons,
                "shortlisted_generated_tools": shortlisted_generated_tools,
                "priority_injection_changed_tool_order": (
                    priority_injection_changed_tool_order
                ),
                "relevance_gating_hid_retained_tool": bool(
                    filtered_out_generated_tools
                ),
                "routing_decisions": {
                    tool_name: decision.to_json()
                    for tool_name, decision in routing_decisions.items()
                },
                "tool_allow_list": list(
                    enhanced.starting_context.tool_allow_list or []
                ),
                "available_tools": sorted(
                    enhanced.starting_context.get_available_tools(
                        scrambling_allowed=False
                    )
                ),
                "generated_tools": generated_tools,
            },
        )
        return enhanced

    def after_result(
        name: str,
        scenario: Scenario,
        result: dict[str, object],
        output_directory: Path,
    ) -> dict[str, object]:
        generated_visible = visible_generated_by_scenario.get(name, [])
        generated_called = list(called_generated_by_scenario.get(name, []))
        for tool_name in _reuse_log_tools(output_directory, name):
            if tool_name not in generated_called:
                generated_called.append(tool_name)
        generated_attempted, generated_failed = _conversation_generated_tool_attempts(
            output_directory,
            name,
            generated_visible,
        )
        generated_not_called = [
            tool for tool in generated_visible if tool not in set(generated_called)
        ]
        generated_not_attempted = [
            tool for tool in generated_visible if tool not in set(generated_attempted)
        ]
        raw_similarity = result.get("similarity", 0.0)
        try:
            similarity = (
                float(raw_similarity)
                if isinstance(raw_similarity, (int, float, str))
                else 0.0
            )
        except ValueError:
            similarity = 0.0
        raw_outcome_similarity = result.get("outcome_similarity")
        try:
            outcome_similarity = (
                float(raw_outcome_similarity)
                if isinstance(raw_outcome_similarity, (int, float, str))
                else None
            )
        except ValueError:
            outcome_similarity = None
        selection_status = (
            "generated_tool_called"
            if generated_called
            else "generated_tool_attempt_failed"
            if generated_failed
            else "generated_tool_attempted_without_success"
            if generated_attempted
            else "generated_tool_visible_not_called"
            if generated_visible
            else "no_visible_generated_tools"
        )
        if generated_called:
            selection_reason = "retained_tool_invoked"
        elif generated_failed:
            selection_reason = "retained_tool_call_failed"
        elif generated_attempted:
            selection_reason = "retained_tool_attempted_without_success_trace"
        elif generated_visible:
            selection_reason = "retained_tool_visible_but_model_did_not_call_it"
        else:
            selection_reason = "no_retained_tool_visible_after_relevance_filter"
        context = selection_context_by_scenario.get(name, {})
        selection_record = {
            "scenario": name,
            "base_tool_policy": config.base_tool_policy,
            "retained_tools_loaded": context.get("retained_tools_loaded", []),
            "filtered_out_generated_tools": context.get(
                "filtered_out_generated_tools", []
            ),
            "filtered_out_reasons": context.get("filtered_out_reasons", {}),
            "shortlisted_generated_tools": context.get(
                "shortlisted_generated_tools", generated_visible
            ),
            "chosen_retained_tool": (
                generated_called[0]
                if generated_called
                else generated_attempted[0]
                if generated_attempted
                else None
            ),
            "priority_injection_changed_tool_order": context.get(
                "priority_injection_changed_tool_order", False
            ),
            "relevance_gating_hid_retained_tool": context.get(
                "relevance_gating_hid_retained_tool", False
            ),
            "generated_tools_visible": generated_visible,
            "generated_tools_attempted": generated_attempted,
            "generated_tools_failed": generated_failed,
            "generated_tools_called": generated_called,
            "generated_tools_not_called": generated_not_called,
            "generated_tools_not_attempted": generated_not_attempted,
            "visible_generated_tool_count": len(generated_visible),
            "attempted_generated_tool_count": len(generated_attempted),
            "failed_generated_tool_count": len(generated_failed),
            "called_generated_tool_count": len(generated_called),
            "selection_status": selection_status,
            "selection_reason": selection_reason,
            "not_called_reason": None
            if generated_called or generated_attempted or not generated_visible
            else "model_did_not_call_retained_tool",
            "similarity": similarity,
            "outcome_similarity": outcome_similarity,
            "exception_type": result.get("exception_type"),
            "failure_after_selection": similarity < 1.0
            or bool(result.get("exception_type")),
            "failure_after_outcome_selection": (
                outcome_similarity is not None and outcome_similarity < 1.0
            )
            or bool(result.get("exception_type")),
        }
        append_jsonl(
            output_directory / "scenario_tool_selection.jsonl",
            selection_record,
        )
        append_jsonl(output_directory / "selection_trace.jsonl", selection_record)
        # Side-effect preservation check: for helpers with required_original_tool_calls,
        # verify those tool names appear in the downstream conversation trajectory.
        side_effect_failures: list[str] = []
        if generated_called:
            loaded_entries_for_check = store.load_entries()
            conv_path = output_directory / "trajectories" / name / "conversation.json"
            conv_messages: list[object] = []
            if conv_path.exists():
                try:
                    conv_messages = json.loads(conv_path.read_text(encoding="utf-8"))
                    if not isinstance(conv_messages, list):
                        conv_messages = []
                except Exception:
                    pass
            for helper_name in generated_called:
                entry = loaded_entries_for_check.get(helper_name)
                if entry is None:
                    continue
                required = tuple(entry.tool.spec.required_original_tool_calls)
                if _side_effect_followup_failures(
                    conv_messages,
                    helper_name=helper_name,
                    required_original_tool_calls=required,
                ):
                    side_effect_failures.append(helper_name)
        if side_effect_failures:
            result["side_effect_preservation_failures"] = side_effect_failures
            append_jsonl(
                output_directory / "side_effect_preservation_report.jsonl",
                {
                    "scenario": name,
                    "side_effect_preservation_failures": side_effect_failures,
                    "generated_tools_called": generated_called,
                },
            )

        if birth_controller is None:
            return result
        observations = classify_scenario_observations(name, scenario, result)
        for observation in observations:
            if event_hook is not None:
                event_hook(
                    "inadequacy_detected",
                    output_directory,
                    observation.to_json(),
                )
            birth_controller.observe(observation)
        result["sage_observations"] = [item.to_json() for item in observations]
        return result

    output_directory = run_scenario_sequence(
        ToolSandboxRunConfig(
            agent=config.agent,
            user=config.user,
            scenario_names=config.scenario_names,
            output_dir=config.output_dir,
            processes=1,
            run_type=config.run_type,
            base_tool_policy=config.base_tool_policy,
            resume_from_dir=config.resume_from_dir,
        ),
        scenario_transform=transform,
        result_hook=after_result,
        progress_hook=progress_hook,
        event_hook=event_hook,
    )
    final_registry_tools = sorted(store.load_entries())
    append_jsonl(
        output_directory / "sage_run_events.jsonl",
        {
            "event": "run_finished",
            "registry_dir": str(config.registry_dir),
            "registry_tools": registry_tools,
            "final_registry_tools": final_registry_tools,
            "final_registry_size": len(final_registry_tools),
        },
    )
    selection_rows = _selection_log_rows(output_directory)
    selection_summary = {
        "scenario_count": len(config.scenario_names),
        "registry_dir": str(config.registry_dir),
        "registry_tools": registry_tools,
        "final_registry_tools": final_registry_tools,
        "generated_tool_visible_scenarios": sum(
            1 for row in selection_rows if row.get("generated_tools_visible")
        ),
        "generated_tool_called_scenarios": sum(
            1 for row in selection_rows if row.get("generated_tools_called")
        ),
        "generated_tool_attempted_scenarios": sum(
            1 for row in selection_rows if row.get("generated_tools_attempted")
        ),
        "generated_tool_failed_scenarios": sum(
            1 for row in selection_rows if row.get("generated_tools_failed")
        ),
        "relevance_gate_hidden_scenarios": sum(
            1 for row in selection_rows if row.get("relevance_gating_hid_retained_tool")
        ),
    }
    (output_directory / "selection_summary.json").write_text(
        json.dumps(selection_summary, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_directory
