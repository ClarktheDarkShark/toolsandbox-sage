"""Adapters that expose accepted SAGE helpers as ToolSandbox tools."""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
from collections.abc import Iterable, MutableMapping
from typing import Any, Callable, cast

from sage_ts.evaluation.task_strata import (
    HELPER_TRIGGERS,
    base_task_family,
    classify_task_strata,
)
from sage_ts.generation.tool_spec import ToolFamily
from sage_ts.registry.manifest import RegistryEntry, has_current_validation_proof
from sage_ts.registry.store import RegistryStore
from sage_ts.validation.schema_check import compile_generated_tool
from tool_sandbox.common import tool_conversion
from tool_sandbox.common.execution_context import ExecutionContext, RoleType
from tool_sandbox.common.scenario import Scenario
from tool_sandbox.common.tool_discovery import ToolBackend, get_scrambled_tool_names
from tool_sandbox.common.utils import add_tool_trace

tool_conversion.PYTHON_TO_JSON_TYPES.setdefault("dict", "object")
tool_conversion.PYTHON_TO_JSON_TYPES.setdefault("list", "array")

PYTHON_TYPES: dict[str, Any] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "dict": dict,
    "list": list,
}


def _google_docstring(entry: RegistryEntry) -> str:
    spec = entry.tool.spec
    description = spec.description
    if spec.tool_name in {"next_service_tool_call", "recover_from_tool_error"}:
        description = (
            f"{description} Use only for the single service you are actively "
            "trying to change. Do not call this helper for multiple alternative "
            "services in parallel. Use this helper only to prepare the next "
            "original ToolSandbox side-effect call. After calling it, execute "
            "the returned original ToolSandbox tool; do not treat the helper "
            "itself as completing the task."
        )
    lines = [description, "", "Args:"]
    for item in spec.inputs:
        lines.append(f"    {item.name}: {item.description}")
    lines.extend(["", "Returns:", f"    {spec.output_annotation}"])
    if spec.tool_name == "next_service_tool_call":
        lines.extend(
            [
                "",
                "Usage:",
                "    Use only for the single service you are actively trying to"
                " change.",
                "    Do not call this helper for multiple alternative services in"
                " parallel.",
                "    Execute only the returned ToolSandbox tool call for the"
                " chosen target service.",
                "    If the target service succeeds, answer only about that final"
                " target state unless the user asked to broaden scope.",
            ]
        )
    if spec.tool_name == "recover_from_tool_error":
        lines.extend(
            [
                "",
                "Usage:",
                "    Call this helper immediately after a ToolSandbox tool returns",
                " a PermissionError or ConnectionError about service state.",
                "    Then execute the returned original ToolSandbox tool name with",
                " the returned JSON arguments.",
                "    This helper prepares the next legal call; it does not perform",
                " the side effect itself.",
            ]
        )
    if spec.tool_name == "prepare_reminder_creation_args":
        lines.extend(
            [
                "",
                "Usage:",
                "    Use this as the normal final step immediately before",
                " add_reminder on reminder-creation tasks.",
                "    When reminder content is known and you either already have",
                " the exact reminder timestamp or enough relative-time fields,",
                " call this helper instead of assembling add_reminder arguments",
                " yourself.",
                "    Prefer resolved_reminder_timestamp whenever you have already",
                " derived the exact reminder time from current tool results or",
                " existing benchmark timestamp context.",
                "    In ToolSandbox reminder creation, plain relative times like",
                " 'tomorrow at 5 PM' mean local device time by default.",
                "    Do not ask the user whether that is in their local timezone",
                " or for a UTC offset again when the current context is already",
                " sufficient to resolve the reminder timestamp safely.",
                "    This helper prepares add_reminder_kwargs only; it does not",
                " create the reminder itself.",
                "    Set location_required to true only when the user explicitly",
                " requires the created reminder to include a location.",
                "    Set location_available to true only when coordinates are",
                " already resolved. A mentioned location that is still being",
                " looked up is location_available=False.",
                "    If optional location is unavailable or a lookup already",
                " failed, proceed without coordinates rather than blocking",
                " reminder creation.",
                "    If this helper returns should_call_add_reminder=False, do",
                " not call add_reminder yet.",
                "    If should_call_add_reminder is True, call add_reminder with",
                " add_reminder_kwargs unchanged.",
                "    If should_retry_location_lookup is True, you may retry",
                " location lookup but can also proceed with add_reminder",
                " without coordinates.",
                "    If should_call_add_reminder is False, use abstain_reason to",
                " decide whether you need clarification rather than guessing.",
            ]
        )
    return "\n".join(lines)


def compile_toolsandbox_tool(entry: RegistryEntry) -> Callable[..., Any]:
    """Compile an accepted registry entry into a ToolSandbox-visible callable."""
    return _compile_toolsandbox_tool(entry, on_reuse=None)


def _compile_toolsandbox_tool(
    entry: RegistryEntry,
    on_reuse: Callable[[str], None] | None,
) -> Callable[..., Any]:
    if entry.retired or not entry.validation.accepted:
        raise ValueError(f"registry entry is not active: {entry.tool.spec.tool_name}")
    if not has_current_validation_proof(entry):
        raise ValueError(
            "registry entry lacks current validation proof: "
            f"{entry.tool.spec.tool_name}"
        )

    compiled = compile_generated_tool(entry.tool)
    if compiled.function is None:
        raise ValueError(
            f"registry entry failed schema compilation: {entry.tool.spec.tool_name}"
        )

    raw_fn = compiled.function

    # ToolSandbox expects every successful tool call to append a tool_trace.
    # We keep this as a plain closure instead of register_as_tool so injected
    # generated helpers stay pickle-safe for scenario execution.
    _tool_name = entry.tool.spec.tool_name
    _inner = raw_fn

    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        result = _inner(*args, **kwargs)
        add_tool_trace(_wrapped, result, *args, **kwargs)
        if on_reuse is not None:
            on_reuse(_tool_name)
        return result

    _wrapped.__name__ = _tool_name
    _wrapped.__doc__ = raw_fn.__doc__
    fn = _wrapped

    # Build annotations using Python type objects.
    annotations: dict[str, Any] = {}
    for item in entry.tool.spec.inputs:
        if item.annotation in PYTHON_TYPES:
            annotations[item.name] = PYTHON_TYPES[item.annotation]
    if entry.tool.spec.output_annotation in PYTHON_TYPES:
        annotations["return"] = PYTHON_TYPES[entry.tool.spec.output_annotation]
    fn.__annotations__ = annotations
    fn.__doc__ = _google_docstring(entry)
    fn.__module__ = "sage_ts.generated_tools"

    # Set ToolSandbox tool metadata directly — avoids the register_as_tool
    # decorator which wraps the function with new_context_with_attribute, a
    # contextvars-backed context manager whose internals are not picklable by dill.
    fn.is_tool = True  # type: ignore[attr-defined]
    fn.visible_to = (RoleType.AGENT,)  # type: ignore[attr-defined]
    fn.backend = ToolBackend.DEFAULT  # type: ignore[attr-defined]

    # Rebuild the inspect.Signature so the agent role can introspect parameters.
    sig = inspect.signature(raw_fn)
    fn.__signature__ = sig.replace(  # type: ignore[attr-defined]
        parameters=[
            p.replace(annotation=annotations.get(p.name, p.annotation))
            for p in sig.parameters.values()
        ],
        return_annotation=annotations.get("return", inspect.Parameter.empty),
    )
    return fn


def inject_registry_tools_into_context(
    context: ExecutionContext,
    entries: Iterable[RegistryEntry],
    *,
    on_reuse: Callable[[str], None] | None = None,
) -> list[str]:
    """Inject accepted generated helpers into a ToolSandbox execution context."""
    injected: list[str] = []
    compiled_by_name: dict[str, Callable[..., Any]] = {}
    for entry in entries:
        tool_name = entry.tool.spec.tool_name
        if tool_name in context.name_to_tool:
            raise ValueError(f"tool name already exists in ToolSandbox: {tool_name}")
        compiled_tool = _compile_toolsandbox_tool(entry, on_reuse)
        compiled_by_name[tool_name] = compiled_tool
        console_locals = cast(
            MutableMapping[str, Any],
            context.interactive_console.locals,
        )
        console_locals[tool_name] = compiled_tool
        injected.append(tool_name)

    if injected:
        # OpenAI receives tools in dict insertion order. Put retained SAGE tools
        # first so transfer runs test whether the model will adopt them when useful.
        context.name_to_tool = {**compiled_by_name, **context.name_to_tool}
        if context.tool_allow_list is not None:
            context.tool_allow_list = injected + [
                tool for tool in context.tool_allow_list if tool not in set(injected)
            ]
        context._actual_to_scrambled_tool_name = get_scrambled_tool_names(
            context.name_to_tool.values()
        )
        context._scrambled_to_actual_tool_name = {
            value: key for key, value in context._actual_to_scrambled_tool_name.items()
        }
    return injected


def _trigger_based_visibility(
    entry: RegistryEntry,
    scenario_name: str,
) -> tuple[bool, str] | None:
    """Check positive/negative trigger tokens against scenario_name.

    Returns a visibility tuple if a trigger matches, or None if no match.
    Called as a supplementary fallback after all hardcoded route checks.
    """
    name_lower = scenario_name.lower()
    spec = entry.tool.spec
    if spec.positive_triggers:
        for token in spec.positive_triggers:
            if token.lower() in name_lower:
                return True, "positive_trigger_match"
    if spec.negative_triggers:
        for token in spec.negative_triggers:
            if token.lower() in name_lower:
                return False, "negative_trigger_suppressed"
    return None


def registry_entry_visibility_reason(
    entry: RegistryEntry,
    scenario_name: str | None,
) -> tuple[bool, str]:
    """Return whether a retained helper should be exposed and why."""
    if entry.retired or not entry.validation.accepted:
        return False, "registry_entry_not_active"
    if not has_current_validation_proof(entry):
        return False, "legacy_validation_missing_current_proof"

    if not scenario_name:
        # Allow explicit global-safe tools; suppress everything else.
        if (
            "global" in entry.tool.spec.positive_triggers
            or "all_scenarios" in entry.tool.spec.positive_triggers
        ):
            return True, "global_safe_explicit"
        return False, "missing_scenario_name_suppressed"

    name = scenario_name.lower()
    tool_name = entry.tool.spec.tool_name
    scenario_strata = set(classify_task_strata(name))
    is_insufficient = "insufficient_information" in name

    if tool_name == "relative_day_time_to_timestamp":
        if name.startswith("modify_reminder_with_recency_latest"):
            return True, "relative_time_modify_latest_reminder"
        if name.startswith("add_reminder_content_and_week_delta"):
            return True, "relative_time_add_reminder_week_delta"
        return False, "relative_time_requires_explicit_relative_datetime_task"

    if tool_name == "recency_to_timestamp_bounds":
        bounded_recency = any(
            token in name for token in ("yesterday", "today", "upcoming")
        )
        if (
            "insufficient_information" not in name
            and name.startswith("search_reminder_with_creation_recency_")
            and bounded_recency
        ):
            return True, "recency_bounds_creation_search_task"
        if name.startswith("search_message_with_recency_") and bounded_recency:
            return True, "recency_bounds_search_task"
        return False, "recency_bounds_requires_bounded_recency_task"

    if tool_name == "days_between_timestamps":
        if name.startswith("find_days_till_holiday"):
            return True, "calendar_day_distance_task"
        return False, "calendar_day_distance_requires_holiday_task"

    if tool_name == "prepare_reminder_arguments_with_optional_location":
        if is_insufficient:
            return (
                False,
                "reminder_argument_prep_suppressed_for_insufficient_information",
            )
        if "low_battery" in name:
            return (
                False,
                "reminder_argument_prep_suppressed_for_service_precondition_task",
            )
        if (
            name.startswith("add_reminder_content_and_")
            and "_time" in name
            and "_location" in name
        ):
            return True, "reminder_argument_prep_add_reminder_time_location_task"
        return False, "reminder_argument_prep_requires_add_reminder_time_location_task"

    if tool_name == "prepare_reminder_creation_args":
        if is_insufficient:
            return False, "reminder_creation_args_suppressed_insufficient_information"
        # General reminder-creation detection: scenario involves adding/creating a
        # reminder and is not a modify/search/update/delete task.
        creation_signals = ("add_reminder", "remind", "create_reminder", "set_reminder")
        suppress_signals = (
            "modify_reminder",
            "search_reminder",
            "update_reminder",
            "delete_reminder",
        )
        if any(token in name for token in suppress_signals):
            return False, "reminder_creation_args_suppressed_non_creation_task"
        if any(token in name for token in creation_signals):
            return True, "reminder_creation_args_reminder_creation_task"
        # No creation signal detected — hide (safe default).
        return False, "reminder_creation_args_no_creation_signal"

    if tool_name == "message_search_time_window":
        return False, "message_search_window_suppressed_after_focused_regression"

    if tool_name == "message_search_args_for_contact":
        return (
            False,
            "message_search_args_suppressed_schema_requires_preexisting_contact",
        )

    if entry.tool.spec.family == ToolFamily.SEARCH_FILTER_RANKING_HELPER:
        if tool_name == "select_contact_by_constraint":
            return False, "contact_selector_suppressed_visible_not_called_pollution"
        if tool_name == "select_contact_field_by_constraint":
            return (
                False,
                "contact_field_selector_suppressed_visible_not_called_pollution",
            )
        if tool_name == "select_latest_record_by_timestamp":
            if "insufficient_information" not in name and name.startswith(
                ("modify_contact_with_message_recency",)
            ):
                return True, "latest_message_record_selection_required"
            return False, "latest_record_suppressed_outside_message_search"
        if tool_name == "select_record_by_timestamp_extreme":
            if (
                "insufficient_information" not in name
                and "multiple_user_turn" not in name
                and "_alt" not in name
                and name.startswith(
                    (
                        "search_message_with_recency_latest",
                        "search_message_with_recency_oldest",
                    )
                )
            ):
                return True, "simple_message_timestamp_extreme_selection_required"
            return False, "timestamp_extreme_suppressed_outside_message_ranking_tasks"
        if tool_name == "select_self_message_by_timestamp":
            return False, "self_message_selector_suppressed_empty_input_misuse"
        return _provisional_birth_family_visibility(entry, name)

    if entry.tool.spec.family == ToolFamily.CANONICALIZER:
        return _provisional_birth_family_visibility(entry, name)

    if tool_name == "extract_stock_symbol":
        if "insufficient_information" not in name and name.startswith(
            "find_stock_symbol_with_company_name"
        ):
            return True, "stock_symbol_extraction_task"
        return False, "stock_symbol_requires_stock_lookup_task"

    # Supplementary trigger-based fallback: checked after all hardcoded routes.
    trigger_result = _trigger_based_visibility(entry, name)
    if trigger_result is not None:
        return trigger_result

    if entry.tool.spec.family != ToolFamily.STATE_PRECONDITION_HELPER:
        return _provisional_birth_family_visibility(entry, name)

    if tool_name == "next_service_enablement_action":
        return False, "state_helper_suppressed_trace_mismatch_use_tool_call_variant"

    if tool_name == "next_service_tool_call":
        if "insufficient_information" in name:
            return False, "state_helper_suppressed_for_insufficient_information"
        direct_service_prefixes = (
            "turn_on_wifi_low_battery_mode",
            "turn_on_cellular_low_battery_mode",
            "turn_on_location_low_battery_mode",
        )
        if name.startswith(direct_service_prefixes):
            return True, "state_tool_call_direct_service_precondition_task"
        if "low_battery_mode" in name:
            return True, "state_tool_call_downstream_service_precondition_task"
        return False, "state_helper_requires_direct_service_precondition_task"

    if tool_name == "recover_from_tool_error":
        if "insufficient_information" in name:
            return False, "error_recovery_suppressed_for_insufficient_information"
        if "low_battery_mode" in name:
            return True, "error_recovery_low_battery_service_precondition_task"
        return False, "error_recovery_requires_service_precondition_task"

    return False, "state_helper_requires_direct_service_state_task"


def retained_tool_visibility_policy_digest() -> str:
    """Return a digest that changes when retained-tool routing policy changes."""
    payload = {
        "policy_version": "v4_failure_driven_strata_shared_birth",
        "helper_triggers": HELPER_TRIGGERS,
        "visibility_source": inspect.getsource(registry_entry_visibility_reason),
        "provisional_source": inspect.getsource(_provisional_birth_family_visibility),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _provisional_birth_family_visibility(
    entry: RegistryEntry,
    normalized_scenario_name: str,
) -> tuple[bool, str]:
    """Expose unknown helpers by task stratum before falling back to birth family."""
    scenario_strata = set(classify_task_strata(normalized_scenario_name))
    tool_name = entry.tool.spec.tool_name
    trigger_strata = set(HELPER_TRIGGERS.get(tool_name, ()))
    if trigger_strata and scenario_strata & trigger_strata:
        return True, "provisional_helper_trigger_stratum_visibility"

    family_strata = {
        ToolFamily.CANONICALIZER: {
            "temporal_reminder_date_canonicalization",
            "holiday_calendar_business_day_logic",
        },
        ToolFamily.DERIVED_VALUE_CALCULATOR: {
            "temporal_reminder_date_canonicalization",
            "record_filtering_ranking_latest_selection",
            "holiday_calendar_business_day_logic",
            "contact_message_search_disambiguation",
            "stock_market_numeric_normalization",
        },
        ToolFamily.SEARCH_FILTER_RANKING_HELPER: {
            "contact_message_search_disambiguation",
            "record_filtering_ranking_latest_selection",
        },
        ToolFamily.STATE_PRECONDITION_HELPER: {
            "direct_state_precondition_service_enablement",
        },
        ToolFamily.COMPOSITE_WORKFLOW_HELPER: {
            "generic_multi_tool_composition",
        },
        ToolFamily.VALIDATION_ABSTENTION_HELPER: {
            "insufficient_information_clarification",
        },
    }.get(entry.tool.spec.family, set())
    birth_scenario = (entry.birth_scenario or "").lower()
    if birth_scenario:
        birth_strata = set(classify_task_strata(birth_scenario))
        shared_family_strata = scenario_strata & birth_strata & family_strata
        if shared_family_strata:
            return True, "provisional_shared_birth_stratum_visibility"

    if birth_scenario and base_task_family(birth_scenario) == base_task_family(
        normalized_scenario_name
    ):
        return True, "provisional_same_birth_family_visibility"
    return False, "unknown_helper_requires_visibility_policy"


def registry_entry_matches_scenario(
    entry: RegistryEntry,
    scenario_name: str | None,
) -> bool:
    """Return whether a retained helper should be exposed for this scenario."""
    return registry_entry_visibility_reason(entry, scenario_name)[0]


def with_registry_tools(
    scenario: Scenario,
    store: RegistryStore,
    *,
    on_reuse: Callable[[str], None] | None = None,
    scenario_name: str | None = None,
) -> Scenario:
    """Return a scenario copy whose starting context includes registry tools."""
    scenario_copy = copy.deepcopy(scenario)
    entries = [
        entry
        for entry in store.load_entries().values()
        if registry_entry_matches_scenario(entry, scenario_name)
    ]
    inject_registry_tools_into_context(
        scenario_copy.starting_context,
        entries,
        on_reuse=on_reuse,
    )
    return scenario_copy
