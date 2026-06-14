"""ToolSandbox runner with accepted SAGE registry tools injected."""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from sage_ts.adapters.toolsandbox_adapter import (
    EventHook,
    ProgressHook,
    ToolSandboxRunConfig,
    run_one_scenario,
    run_scenario_sequence,
)
from sage_ts.adequacy.inadequacy_classifier import (
    classify_scenario_observations,
    classify_visible_task_observations,
    visible_task_context_from_scenario,
)
from sage_ts.generation.tool_spec import ToolFamily
from sage_ts.orchestration.checkpoints import append_jsonl
from sage_ts.orchestration.online_birth import (
    GeneratedToolFactory,
    OnlineBirthController,
    visible_context_metadata_enabled,
)
from sage_ts.orchestration.self_evolution_reflection import (
    SelfEvolutionReflectionController,
)
from sage_ts.registry.store import RegistryStore
from sage_ts.runtime.base_toolset import UPSTREAM_POLICY
from sage_ts.runtime.toolsandbox_integration import (
    load_tool_lifecycle_routing_state,
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


def _safe_checkpoint_name(scenario_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", scenario_name).strip("_")
    return slug[:120] or "scenario"


def _snapshot_registry_checkpoint(
    *,
    output_directory: Path,
    registry_dir: Path,
    scenario_name: str,
) -> Path | None:
    """Persist registry state after a scenario so resumed runs can restore it."""
    try:
        order_index = int(os.environ.get("SAGE_TS_SCENARIO_ORDER_INDEX") or "-1")
    except ValueError:
        order_index = -1
    completed_count = max(order_index + 1, 0)
    checkpoint_dir = (
        output_directory
        / "registry_checkpoints"
        / f"after_{completed_count:04d}_{_safe_checkpoint_name(scenario_name)}"
    )
    copied: list[str] = []
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("registry_manifest.json", "tool_lifecycle.json"):
        source = registry_dir / filename
        if source.exists():
            shutil.copy2(source, checkpoint_dir / filename)
            copied.append(filename)
    if not copied:
        return None
    metadata = {
        "scenario": scenario_name,
        "completed_count": completed_count,
        "registry_dir": str(registry_dir),
        "copied_files": copied,
    }
    (checkpoint_dir / "checkpoint.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return checkpoint_dir


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


def _tool_trace_events_from_execution_context(path: Path) -> list[dict[str, object]]:
    """Return actual ToolSandbox tool events from a serialized execution context."""
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    dbs = payload.get("_dbs")
    if not isinstance(dbs, dict):
        return []
    rows = dbs.get("SANDBOX")
    if not isinstance(rows, list):
        return []

    events: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_traces = row.get("tool_trace")
        if raw_traces is not None:
            trace_items = raw_traces if isinstance(raw_traces, list) else [raw_traces]
            for raw_trace in trace_items:
                trace = _parse_tool_message_content(raw_trace)
                if not isinstance(trace, dict):
                    continue
                tool_name = trace.get("tool_name")
                if not isinstance(tool_name, str) or not tool_name:
                    continue
                event = dict(trace)
                event["_sandbox_message_index"] = row.get("sandbox_message_index")
                event["_openai_function_name"] = row.get("openai_function_name")
                events.append(event)
            continue
        # Scrambled-tool settings may omit tool_trace rows for attempted calls,
        # especially failures. The execution content still contains the
        # canonical ToolSandbox callable, so preserve state-changing attempts
        # for side-effect checks.
        content = row.get("content")
        if not isinstance(content, str):
            continue
        match = re.search(r"_response\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(", content)
        if not match:
            continue
        tool_name = match.group(1)
        if not tool_name.startswith(("add_", "modify_", "remove_", "send_", "set_")):
            continue
        events.append(
            {
                "tool_name": tool_name,
                "arguments": {},
                "result": row.get("tool_call_exception"),
                "_sandbox_message_index": row.get("sandbox_message_index"),
                "_openai_function_name": row.get("openai_function_name"),
                "_call_attempt": True,
            }
        )
    return events


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


def _reconcile_generated_tool_calls_from_conversation(
    output_directory: Path,
    scenario_name: str,
    generated_tools: list[str],
    generated_called: list[str],
) -> list[str]:
    """Treat executed generated-tool result messages as generated calls.

    The primary reuse callback remains the source of record for registry reuse.
    This transcript reconciliation protects same-task retry and dashboard
    attribution when ToolSandbox serializes a generated tool result but the
    in-memory callback did not update the local scenario accounting.
    """

    if not generated_tools:
        return generated_called
    reconciled = list(generated_called)
    for tool_name in _conversation_generated_tool_results(
        output_directory,
        scenario_name,
        generated_tools,
    ):
        if tool_name not in reconciled:
            reconciled.append(tool_name)
    return reconciled


VISIBLE_NOT_CALLED_RETRY_ENV = "SAGE_SELF_EVOLVING_VISIBLE_NOT_CALLED_RETRY"
HELPER_ADOPTION_RETRY_ACTIVE_ENV = "SAGE_TS_HELPER_ADOPTION_RETRY_ACTIVE"
HELPER_ADOPTION_RETRY_TOOLS_ENV = "SAGE_TS_HELPER_ADOPTION_RETRY_TOOLS"
SIDE_EFFECT_FAIR_CHANCE_EXTRA_TURNS_ENV = "SAGE_SIDE_EFFECT_FAIR_CHANCE_EXTRA_TURNS"
HELPER_ADOPTION_RETRY_TOOL_HINTS = {
    "constraint_to_action_planner",
    "plan_contact_lookup_query",
    "plan_contact_relationship_batch_update",
    "plan_contact_update_from_id",
    "plan_device_state_action_sequence",
    "plan_message_counterparty_search",
    "prepare_location_search_args",
    "prepare_reminder_creation_args",
    "prepare_safe_action_or_abstain",
    "prepare_side_effect_args_from_selected_record",
    "relative_day_time_to_timestamp",
    "resolve_search_window_or_bounds",
    "select_action_target_by_recency",
    "select_message_counterparty_for_contact_update",
    "select_record_by_timestamp_extreme",
}
LOW_VALUE_ADOPTION_RETRY_TOOL_NAME_PARTS = (
    "search_window",
    "window_or_bounds",
    "window_bounds",
)
RECENCY_ADOPTION_RETRY_WORKFLOW_TOOLS = {
    "relative_day_time_to_timestamp",
    "resolve_search_window_or_bounds",
    "select_action_target_by_recency",
    "select_record_by_timestamp_extreme",
}


def _visible_not_called_retry_enabled() -> bool:
    raw = os.environ.get(VISIBLE_NOT_CALLED_RETRY_ENV, "0").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _helper_adoption_retry_tools(generated_visible: list[str]) -> list[str]:
    return [
        tool_name
        for tool_name in generated_visible
        if _matches_adoption_retry_hint(tool_name)
    ]


def _low_value_adoption_retry_tool(tool_name: str) -> bool:
    normalized = tool_name.lower()
    if normalized == "resolve_search_window_or_bounds":
        return False
    return any(part in normalized for part in LOW_VALUE_ADOPTION_RETRY_TOOL_NAME_PARTS)


def _matches_adoption_retry_hint(tool_name: str) -> bool:
    normalized = tool_name.lower()
    return any(
        normalized == hint or normalized.startswith(f"{hint}_v")
        for hint in HELPER_ADOPTION_RETRY_TOOL_HINTS
    )


def _helper_adoption_retry_candidates(
    generated_visible: list[str],
    generated_attempted: list[str],
    generated_failed: list[str],
) -> list[str]:
    """Return visible generated tools that deserve a bounded adoption retry.

    When no generated tool was attempted, preserve the original broad retry
    behavior. When the actor used some generated tools, keep the retry focused
    on hinted tools that remained unattempted so the retry is about generated
    tool adoption rather than giving the actor another ordinary pass.
    """

    if generated_failed:
        return []
    attempted_or_failed = set(generated_attempted) | set(generated_failed)
    unattempted = [
        tool_name
        for tool_name in generated_visible
        if tool_name not in attempted_or_failed
    ]
    if not unattempted:
        return []
    if not generated_attempted:
        return [
            tool_name
            for tool_name in unattempted
            if not _low_value_adoption_retry_tool(tool_name)
        ]
    hinted_unattempted = [
        tool_name
        for tool_name in unattempted
        if _matches_adoption_retry_hint(tool_name)
    ]
    if "resolve_search_window_or_bounds" in generated_visible and any(
        tool_name in RECENCY_ADOPTION_RETRY_WORKFLOW_TOOLS
        for tool_name in hinted_unattempted
    ):
        workflow_tools = [
            tool_name
            for tool_name in generated_visible
            if tool_name in RECENCY_ADOPTION_RETRY_WORKFLOW_TOOLS
        ]
        return workflow_tools + [
            tool_name
            for tool_name in hinted_unattempted
            if tool_name not in set(workflow_tools)
        ]
    return hinted_unattempted


def _side_effect_fair_chance_extra_turns() -> int:
    raw = os.environ.get(SIDE_EFFECT_FAIR_CHANCE_EXTRA_TURNS_ENV, "").strip()
    if not raw:
        return 0
    try:
        return max(0, min(8, int(raw)))
    except ValueError:
        return 0


def _should_retry_visible_not_called(
    *,
    generated_visible: list[str],
    generated_attempted: list[str],
    generated_failed: list[str],
    similarity: float,
    outcome_similarity: float | None,
) -> bool:
    if not _visible_not_called_retry_enabled():
        return False
    if os.environ.get(HELPER_ADOPTION_RETRY_ACTIVE_ENV, "").strip():
        return False
    if not generated_visible or generated_failed:
        return False
    retry_tools = _helper_adoption_retry_candidates(
        generated_visible,
        generated_attempted,
        generated_failed,
    )
    if not retry_tools:
        return False
    if "prepare_safe_action_or_abstain" in retry_tools:
        # Validation/abstention tools are the generated mechanism for
        # insufficient-information lanes, but retrying a full-credit no-outcome
        # row only to force a validation-tool call wastes tokens and can create
        # scorer-visible action noise. Keep the retry for failed or materially
        # incomplete attempts.
        if outcome_similarity is None:
            return similarity < 1.0
        return outcome_similarity < 0.5 or similarity < 1.0
    hinted_retry = any(
        _matches_adoption_retry_hint(tool_name) for tool_name in retry_tools
    )
    if outcome_similarity is not None:
        # Same-task adoption retry is meant to rescue failed attempts where a
        # visible generated tool was ignored. Keep high-quality partial/complete
        # outcomes, but allow a bounded retry for hinted generated tools when the
        # actor only earned tiny partial credit without using the visible tool.
        if outcome_similarity >= 0.5:
            return False
        if outcome_similarity > 0.0 and not hinted_retry:
            return False
        return similarity < 1.0 or (hinted_retry and similarity < 1.0)
    return similarity < 1.0


def _archive_helper_adoption_retry_trajectory(
    output_directory: Path,
    scenario_name: str,
) -> str | None:
    trajectory_dir = output_directory / "trajectories" / scenario_name
    if not trajectory_dir.exists():
        return None
    archive_base = trajectory_dir.with_name(
        f"{scenario_name}__helper_adoption_retry_initial_attempt"
    )
    archive_dir = archive_base
    suffix = 2
    while archive_dir.exists():
        archive_dir = archive_base.with_name(f"{archive_base.name}_{suffix}")
        suffix += 1
    shutil.move(str(trajectory_dir), str(archive_dir))
    return str(archive_dir)


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


def _side_effect_tool_name(tool_name: object, required: set[str]) -> str | None:
    if not isinstance(tool_name, str):
        return None
    name = tool_name.strip()
    if name in required and name.startswith(
        ("add_", "modify_", "remove_", "send_", "set_")
    ):
        return name
    return None


def _explicit_side_effect_calls_from_output(
    output: dict[str, object],
    *,
    required_side_effect_calls: tuple[str, ...],
) -> set[str]:
    required = set(required_side_effect_calls)
    explicit: set[str] = set()
    for key in ("downstream_tool_name", "tool_name"):
        tool_name = _side_effect_tool_name(output.get(key), required)
        if tool_name:
            explicit.add(tool_name)
    action_sequence = output.get("action_sequence")
    if isinstance(action_sequence, list):
        for action in action_sequence:
            if not isinstance(action, dict):
                continue
            tool_name = _side_effect_tool_name(action.get("tool_name"), required)
            if tool_name:
                explicit.add(tool_name)
    if "add_reminder" in required and (
        output.get("should_call_add_reminder") is True
        or isinstance(output.get("add_reminder_kwargs"), dict)
    ):
        explicit.add("add_reminder")
    return explicit


def _output_is_preparatory_search_followup(output: dict[str, object]) -> bool:
    """Return True for helper outputs that only prepare original search calls."""

    if (
        output.get("should_call_search_contacts") is True
        or output.get("should_call_search_messages") is True
    ):
        return True
    next_step = str(output.get("next_step") or "").lower()
    return "search_contacts" in next_step or "search_messages" in next_step


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


def _next_trace_tool_names(
    events: list[dict[str, object]],
    *,
    start_index: int,
) -> set[str]:
    for event in events[start_index + 1 :]:
        tool_name = event.get("tool_name")
        if isinstance(tool_name, str):
            return {tool_name}
    return set()


def _later_trace_tool_names(
    events: list[dict[str, object]],
    *,
    start_index: int,
) -> set[str]:
    later_tools: set[str] = set()
    for event in events[start_index + 1 :]:
        tool_name = event.get("tool_name")
        if isinstance(tool_name, str):
            later_tools.add(tool_name)
    return later_tools


def _side_effect_followup_failures_from_trace_events(
    events: list[dict[str, object]],
    *,
    helper_name: str,
    required_side_effect_calls: tuple[str, ...],
) -> bool:
    saw_helper_result = False
    for index, event in enumerate(events):
        if event.get("tool_name") != helper_name:
            continue
        saw_helper_result = True
        output = event.get("result")
        next_tools = _next_trace_tool_names(events, start_index=index)
        required = set(required_side_effect_calls)
        if isinstance(output, dict):
            declares_followup = any(
                key in output
                for key in (
                    "should_call_add_reminder",
                    "should_call",
                    "should_call_tool",
                    "should_call_tools",
                    "downstream_tool_name",
                    "tool_name",
                    "action_sequence",
                    "add_reminder_kwargs",
                    "downstream_tool_kwargs",
                )
            )
            if not declares_followup:
                continue
            explicit_required = _explicit_side_effect_calls_from_output(
                output,
                required_side_effect_calls=required_side_effect_calls,
            )
            if explicit_required:
                required = explicit_required
            elif _output_is_preparatory_search_followup(output):
                continue
            if (
                output.get("should_call_add_reminder") is False
                or output.get("should_call") is False
                or output.get("should_call_tool") is False
                or output.get("should_call_tools") is False
            ):
                if (
                    output.get("should_call_search_contacts") is True
                    and output.get("should_call_tools") is False
                ):
                    if required & next_tools:
                        return True
                    continue
                selection_only_bridge = (
                    isinstance(output.get("selected_record"), dict)
                    and bool(output.get("selected_record"))
                    and str(output.get("downstream_tool_name") or "")
                    in required_side_effect_calls
                    and str(output.get("final_answer_recommendation") or "").startswith(
                        "use_selected_record:"
                    )
                )
                if selection_only_bridge:
                    later_tools = _later_trace_tool_names(events, start_index=index)
                    if not (required & later_tools):
                        return True
                    continue
                if required & next_tools:
                    return True
                continue
            if (
                output.get("should_call_add_reminder") is True
                or output.get("should_call") is True
                or output.get("should_call_tool") is True
                or output.get("should_call_tools") is True
            ):
                if required & next_tools:
                    continue
                later_tools = _later_trace_tool_names(events, start_index=index)
                if required & later_tools:
                    continue
                return True
        else:
            # Scalar/extraction helpers may list downstream tools in their broad
            # preservation contract because their values can be used before a
            # later side effect. The helper output itself does not declare a
            # side-effect call, so absence of that call is not a safety incident.
            continue
        if not (required & _later_trace_tool_names(events, start_index=index)):
            return True
    return not saw_helper_result


def _side_effect_followup_failures(
    messages: list[object],
    *,
    helper_name: str,
    required_original_tool_calls: tuple[str, ...],
    actual_tool_trace_events: list[dict[str, object]] | None = None,
) -> bool:
    """Return True when a helper's declared follow-up contract is violated.

    Abstaining helpers should not trigger their side-effect tool directly, but
    they may resolve missing prerequisites first and call the side-effect later.
    """

    required_side_effect_calls = tuple(
        tool_name
        for tool_name in required_original_tool_calls
        if tool_name.startswith(("add_", "modify_", "remove_", "send_", "set_"))
    )
    if not required_side_effect_calls:
        return False
    if actual_tool_trace_events:
        trace_failure = _side_effect_followup_failures_from_trace_events(
            actual_tool_trace_events,
            helper_name=helper_name,
            required_side_effect_calls=required_side_effect_calls,
        )
        if not trace_failure:
            return False
        # ToolSandbox trace rows can omit failed original tool attempts while the
        # conversation still records the assistant tool call and tool error. Use
        # the conversation as a conservative fallback before declaring that a
        # helper failed to preserve a required downstream side-effect call.
    saw_helper_result = False
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        if message.get("role") != "tool" or message.get("name") != helper_name:
            continue
        saw_helper_result = True
        output = _parse_tool_message_content(message.get("content"))
        next_tools = set(_next_assistant_tool_names(messages, start_index=index))
        required = set(required_side_effect_calls)
        if isinstance(output, dict):
            declares_followup = any(
                key in output
                for key in (
                    "should_call_add_reminder",
                    "should_call",
                    "should_call_tool",
                    "should_call_tools",
                    "downstream_tool_name",
                    "tool_name",
                    "action_sequence",
                    "add_reminder_kwargs",
                    "downstream_tool_kwargs",
                )
            )
            if not declares_followup:
                # Scalar/extraction helpers may preserve one of several original
                # producers without preparing the final side-effect call. Do not
                # mark them unsafe simply because a side-effect tool named in the
                # broad preservation contract was not needed for this scenario.
                continue
            explicit_required = _explicit_side_effect_calls_from_output(
                output,
                required_side_effect_calls=required_side_effect_calls,
            )
            if explicit_required:
                required = explicit_required
            elif _output_is_preparatory_search_followup(output):
                continue
            if (
                output.get("should_call_add_reminder") is False
                or output.get("should_call") is False
                or output.get("should_call_tool") is False
                or output.get("should_call_tools") is False
            ):
                if (
                    output.get("should_call_search_contacts") is True
                    and output.get("should_call_tools") is False
                ):
                    if required & next_tools:
                        return True
                    continue
                selection_only_bridge = (
                    isinstance(output.get("selected_record"), dict)
                    and bool(output.get("selected_record"))
                    and str(output.get("downstream_tool_name") or "")
                    in required_side_effect_calls
                    and str(output.get("final_answer_recommendation") or "").startswith(
                        "use_selected_record:"
                    )
                )
                if selection_only_bridge:
                    bridge_followup_tools: set[str] = set()
                    for later in messages[index + 1 :]:
                        if isinstance(later, dict) and later.get("role") == "assistant":
                            bridge_followup_tools.update(_assistant_tool_names(later))
                    if not (required & bridge_followup_tools):
                        return True
                    continue
                if required & next_tools:
                    return True
                continue
            if (
                output.get("should_call_add_reminder") is True
                or output.get("should_call") is True
                or output.get("should_call_tool") is True
                or output.get("should_call_tools") is True
            ):
                if required & next_tools:
                    continue
                later_followup_tools: set[str] = set()
                for later in messages[index + 1 :]:
                    if isinstance(later, dict) and later.get("role") == "assistant":
                        later_followup_tools.update(_assistant_tool_names(later))
                if required & later_followup_tools:
                    continue
                return True
        else:
            # Non-mapping helper outputs, such as deterministic timestamp values,
            # do not declare a downstream side-effect contract.
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
    resume_completed_limit: int | None = None
    manifest_path: Path = Path("")


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
    baseline_scenario_by_name: dict[str, Scenario] = {}

    birth_controller: OnlineBirthController | None = None
    reflection_controller: SelfEvolutionReflectionController | None = None
    registry_load_logged = False
    mutate_registry_reuse_counts = generator is not None

    def transform(name: str, scenario: Scenario, output_directory: Path) -> Scenario:
        nonlocal birth_controller, registry_load_logged, reflection_controller
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
            birth_controller.prime_from_scenario_names(config.scenario_names)
        if generator is not None and reflection_controller is None:
            reflection_controller = SelfEvolutionReflectionController.from_env(
                store=store,
                output_dir=output_directory,
                agent=config.agent,
                user=config.user,
                base_tool_policy=config.base_tool_policy,
                manifest_path=config.manifest_path,
            )
        visible_task_context = (
            visible_task_context_from_scenario(scenario)
            if visible_context_metadata_enabled()
            else None
        )
        routing_context_text = (
            visible_task_context.routing_text()
            if visible_task_context is not None
            else None
        )
        routing_context_label = (
            visible_task_context.generation_label()
            if visible_task_context is not None
            else None
        )
        routing_family_key = (
            visible_task_context.primary_family_key
            if visible_task_context is not None
            else None
        )
        if birth_controller is not None:
            accepted_tools = birth_controller.prime_before_scenario(name, scenario)
            if accepted_tools:
                append_jsonl(
                    output_directory / "sage_run_events.jsonl",
                    {
                        "event": "jit_birth_tools_available_for_same_task",
                        "scenario": name,
                        "accepted_tools": accepted_tools,
                        "registry_dir": str(config.registry_dir),
                    },
                )
                if event_hook is not None:
                    event_hook(
                        "jit_birth_tools_available_for_same_task",
                        output_directory,
                        {
                            "scenario": name,
                            "accepted_tools": accepted_tools,
                            "registry_dir": str(config.registry_dir),
                        },
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

        baseline_scenario_by_name[name] = scenario

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
        lifecycle_state = load_tool_lifecycle_routing_state(store.root)
        _routed_entries, routing_decisions = route_registry_entries(
            loaded_entries,
            name,
            available_base_tools=available_base_tools,
            lifecycle_state=lifecycle_state,
            task_context_text=routing_context_text,
            task_family_key=routing_family_key,
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
            task_context_text=routing_context_text,
            task_family_key=routing_family_key,
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
        side_effect_fair_chance_tools = [
            tool_name
            for tool_name in generated_tools
            if (
                (entry := loaded_entries.get(tool_name)) is not None
                and entry.tool.spec.family != ToolFamily.VALIDATION_ABSTENTION_HELPER
                and (
                    entry.tool.spec.required_original_tool_calls
                    or entry.tool.spec.preserves_side_effect_tools
                )
            )
        ]
        extra_turns = _side_effect_fair_chance_extra_turns()
        if extra_turns and side_effect_fair_chance_tools:
            original_max_messages = int(getattr(enhanced, "max_messages", 0) or 0)
            if original_max_messages > 0:
                enhanced.max_messages = original_max_messages + extra_turns
                append_jsonl(
                    output_directory / "sage_run_events.jsonl",
                    {
                        "event": "side_effect_fair_chance_turn_extension",
                        "scenario": name,
                        "visible_tools": side_effect_fair_chance_tools,
                        "extra_turns": extra_turns,
                        "original_max_messages": original_max_messages,
                        "extended_max_messages": enhanced.max_messages,
                    },
                )
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
            "task_context_label": routing_context_label,
            "task_family_key": routing_family_key,
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
        generated_called = _reconcile_generated_tool_calls_from_conversation(
            output_directory,
            name,
            generated_visible,
            generated_called,
        )
        if generated_failed:
            failed_set = set(generated_failed)
            generated_called = [
                tool_name
                for tool_name in generated_called
                if tool_name not in failed_set
            ]
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
        if _should_retry_visible_not_called(
            generated_visible=generated_visible,
            generated_attempted=generated_attempted,
            generated_failed=generated_failed,
            similarity=similarity,
            outcome_similarity=outcome_similarity,
        ):
            initial_similarity = similarity
            initial_outcome_similarity = outcome_similarity
            retry_tools = _helper_adoption_retry_candidates(
                generated_visible,
                generated_attempted,
                generated_failed,
            )
            archive = _archive_helper_adoption_retry_trajectory(
                output_directory,
                name,
            )
            append_jsonl(
                output_directory / "sage_run_events.jsonl",
                {
                    "event": "helper_visible_not_called_same_task_retry",
                    "scenario": name,
                    "visible_tools": generated_visible,
                    "retry_tools": retry_tools,
                    "initial_similarity": initial_similarity,
                    "initial_outcome_similarity": initial_outcome_similarity,
                    "initial_trajectory_archive": archive,
                },
            )
            prior_active = os.environ.get(HELPER_ADOPTION_RETRY_ACTIVE_ENV)
            prior_tools = os.environ.get(HELPER_ADOPTION_RETRY_TOOLS_ENV)
            os.environ[HELPER_ADOPTION_RETRY_ACTIVE_ENV] = "1"
            os.environ[HELPER_ADOPTION_RETRY_TOOLS_ENV] = ",".join(retry_tools)
            try:
                called_generated_by_scenario[name] = []
                result = run_one_scenario(
                    name,
                    scenario,
                    agent=config.agent,
                    user=config.user,
                    output_directory=output_directory,
                )
            finally:
                if prior_active is None:
                    os.environ.pop(HELPER_ADOPTION_RETRY_ACTIVE_ENV, None)
                else:
                    os.environ[HELPER_ADOPTION_RETRY_ACTIVE_ENV] = prior_active
                if prior_tools is None:
                    os.environ.pop(HELPER_ADOPTION_RETRY_TOOLS_ENV, None)
                else:
                    os.environ[HELPER_ADOPTION_RETRY_TOOLS_ENV] = prior_tools
            generated_called = list(called_generated_by_scenario.get(name, []))
            for tool_name in _reuse_log_tools(output_directory, name):
                if tool_name not in generated_called:
                    generated_called.append(tool_name)
            generated_attempted, generated_failed = (
                _conversation_generated_tool_attempts(
                    output_directory,
                    name,
                    generated_visible,
                )
            )
            generated_called = _reconcile_generated_tool_calls_from_conversation(
                output_directory,
                name,
                generated_visible,
                generated_called,
            )
            if generated_failed:
                failed_set = set(generated_failed)
                generated_called = [
                    tool_name
                    for tool_name in generated_called
                    if tool_name not in failed_set
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
            append_jsonl(
                output_directory / "sage_run_events.jsonl",
                {
                    "event": "helper_visible_not_called_same_task_retry_result",
                    "scenario": name,
                    "visible_tools": generated_visible,
                    "retry_tools": retry_tools,
                    "initial_similarity": initial_similarity,
                    "initial_outcome_similarity": initial_outcome_similarity,
                    "final_called_tools": generated_called,
                    "final_attempted_tools": generated_attempted,
                    "final_failed_tools": generated_failed,
                    "final_similarity": similarity,
                    "final_outcome_similarity": outcome_similarity,
                },
            )
        generated_not_called = [
            tool for tool in generated_visible if tool not in set(generated_called)
        ]
        generated_not_attempted = [
            tool for tool in generated_visible if tool not in set(generated_attempted)
        ]
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
            actual_tool_trace_events = _tool_trace_events_from_execution_context(
                output_directory / "trajectories" / name / "execution_context.json"
            )
            for helper_name in generated_called:
                entry = loaded_entries_for_check.get(helper_name)
                if entry is None:
                    continue
                required = tuple(entry.tool.spec.required_original_tool_calls)
                if _side_effect_followup_failures(
                    conv_messages,
                    helper_name=helper_name,
                    required_original_tool_calls=required,
                    actual_tool_trace_events=actual_tool_trace_events,
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
        suppress_zero_score = os.environ.get(
            "SAGE_SELF_EVOLVING_SUPPRESS_ZERO_SCORE_TOOLS",
            "",
        ).strip().lower() in {"1", "true", "yes", "on"}
        if (
            suppress_zero_score
            and generated_called
            and similarity <= 0.0
            and not side_effect_failures
        ):
            for helper_name in generated_called:
                store.retire(helper_name)
                payload = {
                    "event": "tool_runtime_suppressed",
                    "tool_name": helper_name,
                    "scenario": name,
                    "reason": "generated_tool_called_with_zero_similarity",
                    "similarity": similarity,
                    "outcome_similarity": outcome_similarity,
                    "registry_dir": str(config.registry_dir),
                }
                append_jsonl(output_directory / "sage_run_events.jsonl", payload)
                if event_hook is not None:
                    event_hook("tool_runtime_suppressed", output_directory, payload)

        if reflection_controller is not None:
            decision = reflection_controller.assess_scenario(
                scenario_name=name,
                baseline_scenario=baseline_scenario_by_name.get(name, scenario),
                result=result,
                selection_record=selection_record,
                side_effect_failures=side_effect_failures,
                task_context_label=(
                    selection_context_by_scenario.get(name, {}).get(
                        "task_context_label"
                    )
                    if visible_context_metadata_enabled()
                    else None
                ),
                task_family_key=(
                    selection_context_by_scenario.get(name, {}).get("task_family_key")
                    if visible_context_metadata_enabled()
                    else None
                ),
            )
            if decision.stop_run:
                result["_sage_stop_run"] = True
                result["_sage_stop_reason"] = decision.reason
                payload = {
                    "event": "self_evolution_stop_recommended",
                    "scenario": name,
                    "reason": decision.reason,
                    "completed_count": reflection_controller.completed_count,
                    "registry_dir": str(config.registry_dir),
                }
                append_jsonl(output_directory / "sage_run_events.jsonl", payload)
                if event_hook is not None:
                    event_hook(
                        "self_evolution_stop_recommended",
                        output_directory,
                        payload,
                    )

        if birth_controller is None:
            checkpoint = _snapshot_registry_checkpoint(
                output_directory=output_directory,
                registry_dir=config.registry_dir,
                scenario_name=name,
            )
            if checkpoint is not None:
                append_jsonl(
                    output_directory / "sage_run_events.jsonl",
                    {
                        "event": "registry_checkpoint_written",
                        "scenario": name,
                        "checkpoint_dir": str(checkpoint),
                        "registry_dir": str(config.registry_dir),
                    },
                )
            return result
        if visible_context_metadata_enabled():
            observations = classify_visible_task_observations(name, scenario)
        else:
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
        checkpoint = _snapshot_registry_checkpoint(
            output_directory=output_directory,
            registry_dir=config.registry_dir,
            scenario_name=name,
        )
        if checkpoint is not None:
            append_jsonl(
                output_directory / "sage_run_events.jsonl",
                {
                    "event": "registry_checkpoint_written",
                    "scenario": name,
                    "checkpoint_dir": str(checkpoint),
                    "registry_dir": str(config.registry_dir),
                },
            )
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
            resume_completed_limit=config.resume_completed_limit,
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
