"""Online conversion from repeated observations to accepted helper tools."""

from __future__ import annotations

import ast
import json
import re
import time
from collections import Counter
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Protocol

from sage_ts.adequacy.candidate_gate import evaluate_candidate_gate
from sage_ts.adequacy.failure_memory import generation_failure_memory_context
from sage_ts.adequacy.inadequacy_classifier import (
    CapabilityObservation,
    classify_visible_task_observations,
)
from sage_ts.evaluation.task_strata import base_task_family, expected_helper_fit
from sage_ts.generation.complete_tools import COMPLETE_TOOLS_NATIVE_NAMES
from sage_ts.generation.tool_generator import ToolGenerationRequest
from sage_ts.generation.tool_spec import (
    GeneratedTool,
    ToolFamily,
)
from sage_ts.orchestration.checkpoints import append_jsonl
from sage_ts.registry.manifest import RegistryEntry, has_current_validation_proof
from sage_ts.registry.store import RegistryStore
from sage_ts.validation.sandbox_validator import (
    ToolExample,
    ValidationResult,
    validate_generated_tool,
)


class GeneratedToolFactory(Protocol):
    def generate(self, request: ToolGenerationRequest) -> GeneratedTool: ...


CampaignEventHook = Callable[[str, dict[str, Any]], None]


def suggested_tool_name(canonical_key: str) -> str | None:
    """Map recurring capability keys to stable, reusable tool names."""
    suffix = canonical_key.split(":", 1)[-1].strip()
    if not suffix:
        return None
    if suffix == "recency_timestamp_bounds":
        return "recency_to_timestamp_bounds"
    if suffix == "resolve_search_window_or_bounds":
        return "resolve_search_window_or_bounds"
    if suffix == "relative_day_time_timestamp":
        return "relative_day_time_to_timestamp"
    if suffix == "location_service_recovery_sequence":
        return "plan_device_state_action_sequence_location_recovery"
    if suffix in {"device_state_action_sequence", "plan_device_state_action_sequence"}:
        return "plan_device_state_action_sequence_v3"
    if suffix in {"service_next_action", "next_service_tool_call"}:
        return "next_service_tool_call"
    if suffix == "dependency_precondition_tool_call":
        return "next_dependency_precondition_call"
    if suffix == "constraint_to_action_planner":
        return "constraint_to_action_planner"
    if suffix == "prepare_direct_contact_action_args":
        return "prepare_direct_contact_action_args"
    return suffix


BROADER_HELPER_OVERLAPS = {
    "derived_value:recency_timestamp_bounds": ("resolve_search_window_or_bounds",),
    "derived_value:message_search_time_window": ("resolve_search_window_or_bounds",),
    "composite:prepare_side_effect_args_from_selected_record": (
        "constraint_to_action_planner",
    ),
    "state_precondition:next_service_tool_call": (
        "plan_device_state_action_sequence_v3",
    ),
}


PLACEHOLDER_ORIGINAL_TOOL_TOKENS = ("payload", "service", "lookup")
CANDIDATE_REPAIR_ATTEMPTS = 7
MAX_REJECTIONS_PER_TOOL_KEY = 2


def _native_action_observation_priority(
    observation: CapabilityObservation,
) -> int:
    """Put executable action contracts before preparatory contracts when enabled."""

    eligible_families = {
        str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),
        str(ToolFamily.SEARCH_FILTER_RANKING_HELPER),
    }
    if not eligible_families.intersection(observation.allowed_families):
        return 1
    allowed_actions = set(COMPLETE_TOOLS_NATIVE_NAMES)
    for example in observation.validation_examples:
        if example.negative_applicability or not isinstance(example.expected, dict):
            continue
        action_name = str(example.expected.get("downstream_tool_name") or "")
        action_arguments = example.expected.get("downstream_tool_kwargs")
        if action_name in allowed_actions and isinstance(action_arguments, dict):
            return 0
    return 1


def _complements_validated_native_action(
    observation: CapabilityObservation,
) -> bool:
    """Allow non-mutating producers needed before an action tool can run."""

    input_producing_families = {
        str(ToolFamily.CANONICALIZER),
        str(ToolFamily.DERIVED_VALUE_CALCULATOR),
        str(ToolFamily.STATE_PRECONDITION_HELPER),
    }
    if input_producing_families.intersection(observation.allowed_families):
        return True

    if str(ToolFamily.COMPOSITE_WORKFLOW_HELPER) not in observation.allowed_families:
        return False

    downstream_tools = tuple(
        str(example.expected.get("downstream_tool_name") or "")
        for example in observation.validation_examples
        if not example.negative_applicability
        and isinstance(example.expected, dict)
        and example.expected.get("downstream_tool_name")
    )
    if not downstream_tools:
        return False

    read_only_prefixes = ("search_", "get_", "find_")
    native_actions = set(COMPLETE_TOOLS_NATIVE_NAMES)
    return all(
        tool_name.startswith(read_only_prefixes) and tool_name not in native_actions
        for tool_name in downstream_tools
    )


FIRST_OBSERVATION_BIRTH_KEYS = frozenset(
    {
        "canonicalizer:next_weekday_time_to_timestamp",
        "canonicalizer:relative_day_time_timestamp",
        "composite:plan_contact_lookup_query",
        "composite:plan_contact_relationship_batch_update",
        "composite:plan_contact_update_from_id",
        "composite:plan_message_counterparty_search",
        "composite:prepare_direct_contact_action_args",
        "composite:plan_send_message_contact_lookup",
        "composite:prepare_holiday_search_args",
        "composite:prepare_add_contact_args",
        "composite:prepare_location_search_args",
        "composite:prepare_specific_location_search_args",
        "composite:prepare_reminder_creation_args",
        "composite:select_message_counterparty_for_contact_update",
        "derived_value:days_between_timestamps",
        "derived_value:extract_address_result",
        "derived_value:extract_converted_amount_result",
        "derived_value:extract_distance_result",
        "derived_value:extract_phone_number_result",
        "derived_value:extract_service_answer_field",
        "derived_value:extract_stock_symbol",
        "derived_value:extract_temperature_result",
        "derived_value:plan_device_status_lookup",
        "derived_value:prepare_message_recency_search_args",
        "derived_value:prepare_past_reminder_recency_search_args",
        "derived_value:prepare_upcoming_reminder_search_args",
        "derived_value:resolve_search_window_or_bounds",
        "search_filter:select_action_target_by_recency",
        "search_filter:select_message_content_by_recency",
        "search_filter:select_record_by_timestamp_extreme",
        "state_precondition:location_service_recovery_sequence",
        "state_precondition:plan_device_state_action_sequence",
        "validation:prepare_safe_action_or_abstain",
    }
)
CHAIN_ROUTING_FAMILIES_BY_KEY = {
    "composite:plan_contact_lookup_query": (
        "update_contact_relationship_with_relationship_twice",
        "update_contact_relationship_with_relationship",
        "remove_contact_by_phone",
    ),
    "composite:plan_contact_update_from_id": (
        "update_contact_with_id_and_phone_number",
        "contact_id_update_argument_planning",
    ),
    "composite:prepare_direct_contact_action_args": (
        "remove_contact_with_id",
        "send_message_with_phone_number_and_content",
        "add_contact_with_name_and_phone_number",
        "update_contact_with_id_and_phone_number",
    ),
    "composite:plan_send_message_contact_lookup": (
        "send_message_with_contact_content",
        "send_message_with_contact_content_cellular_off",
    ),
    "state_precondition:location_service_recovery_sequence": (
        "turn_on_location_low_battery_mode",
        "add_reminder_content_and_week_delta_and_time_and_location_low_battery_mode",
        "weather_lookup",
        "find_distance",
    ),
    "state_precondition:plan_device_state_action_sequence": (
        "cellular_off",
        "wifi_off",
        "turn_on_wifi_low_battery_mode",
        "turn_on_cellular_low_battery_mode",
        "turn_on_location_low_battery_mode",
        "send_message_with_contact_content_cellular_off",
        "find_days_till_holiday_wifi_off",
        "add_reminder_content_and_week_delta_and_time_and_location_low_battery_mode",
    ),
    "composite:select_message_counterparty_for_contact_update": (
        "modify_contact_with_message_recency",
        "modify_contact_with_message_recency_alt",
    ),
    "derived_value:resolve_search_window_or_bounds": (
        "search_reminder_with_creation_recency_yesterday",
        "search_reminder_with_recency_yesterday",
        "search_reminder_with_recency_upcoming",
        "search_message_with_recency_latest",
        "search_message_with_recency_oldest",
        "modify_reminder_with_recency_latest",
        "remove_reminder_with_recency_latest",
    ),
}

VISIBLE_ROUTING_FAMILIES_BY_KEY = {
    "canonicalizer:next_weekday_time_to_timestamp": (
        "weekday_time",
        "reminder_create",
        "reminder_modify",
    ),
    "canonicalizer:relative_day_time_timestamp": (
        "relative_time",
        "reminder_create",
        "reminder_modify",
    ),
    "composite:prepare_add_contact_args": (
        "add_contact",
        "direct_contact_action",
        "contact_creation",
    ),
    "composite:prepare_direct_contact_action_args": (
        "direct_contact_action",
        "add_contact",
        "remove_contact",
        "modify_contact",
        "send_message",
    ),
    "composite:plan_contact_lookup_query": (
        "contact_lookup",
        "contact_phone_lookup",
        "contact_relationship_lookup",
        "contact_side_effect_target_lookup",
    ),
    "composite:plan_send_message_contact_lookup": (
        "named_message_recipient",
        "send_message",
    ),
    "composite:plan_contact_relationship_batch_update": (
        "relationship_batch_update",
        "contact_bulk_update",
        "contact_lookup",
    ),
    "composite:prepare_location_search_args": (
        "location_phrase",
        "reminder_create",
        "external_lookup",
    ),
    "composite:prepare_specific_location_search_args": (
        "location_phrase",
        "reminder_create",
        "external_lookup",
    ),
    "composite:prepare_broad_location_search_args": (
        "location_phrase",
        "reminder_create",
        "external_lookup",
    ),
    "composite:prepare_reminder_creation_args": (
        "reminder_create",
        "relative_time",
        "weekday_time",
        "location_phrase",
    ),
    "composite:prepare_holiday_search_args": (
        "holiday_lookup",
        "holiday",
        "calendar_distance",
    ),
    "derived_value:extract_stock_symbol": (
        "stock_lookup",
        "external_lookup",
    ),
    "composite:plan_message_counterparty_search": (
        "message_counterparty_lookup",
        "message",
        "contact_lookup",
    ),
    "composite:select_message_counterparty_for_contact_update": (
        "message_counterparty_update",
        "message_recency",
        "modify_contact",
    ),
    "derived_value:resolve_search_window_or_bounds": (
        "recency_search",
        "message_recency",
        "reminder_recency",
        "recency_action",
    ),
    "derived_value:prepare_upcoming_reminder_search_args": (
        "upcoming_reminder_search",
    ),
    "derived_value:prepare_message_recency_search_args": (
        "message_recency_search",
        "message_recency",
        "message_counterparty_update",
    ),
    "derived_value:prepare_past_reminder_recency_search_args": (
        "past_reminder_recency_search",
    ),
    "search_filter:select_record_by_timestamp_extreme": (
        "recency_search",
        "message_recency",
        "reminder_recency",
    ),
    "search_filter:select_message_content_by_recency": (
        "message_recency",
        "recency_search",
        "answer_extraction",
    ),
    "search_filter:select_action_target_by_recency": (
        "recency_action",
        "modify_reminder",
        "remove_reminder",
    ),
    "derived_value:days_between_timestamps": (
        "calendar_distance",
        "holiday",
        "deadline_distance",
    ),
    "derived_value:extract_service_answer_field": (
        "service_answer_extraction",
        "external_lookup",
        "currency_lookup",
        "weather_lookup",
        "temperature_lookup",
    ),
    "derived_value:extract_address_result": (
        "service_answer_extraction",
        "external_lookup",
        "find_address",
    ),
    "derived_value:extract_converted_amount_result": (
        "service_answer_extraction",
        "currency_lookup",
        "convert_currency",
    ),
    "derived_value:extract_phone_number_result": (
        "service_answer_extraction",
        "external_lookup",
        "find_phone_number",
    ),
    "derived_value:extract_distance_result": (
        "service_answer_extraction",
        "external_lookup",
        "find_distance",
    ),
    "derived_value:extract_temperature_result": (
        "service_answer_extraction",
        "external_lookup",
        "weather_lookup",
        "temperature_lookup",
    ),
    "derived_value:plan_device_status_lookup": (
        "device_status_read",
        "wifi_status",
        "cellular_status",
        "location_status",
        "battery_status",
    ),
    "state_precondition:location_service_recovery_sequence": (
        "device_state_action",
        "state_precondition_possible",
        "location_phrase",
        "external_lookup",
        "location_service",
    ),
    "state_precondition:plan_device_state_action_sequence": (
        "device_state_action",
        "state_precondition_possible",
        "wifi",
        "cellular",
        "location_service",
        "low_battery_mode",
    ),
    "validation:prepare_safe_action_or_abstain": (
        "safe_abstain",
        "insufficient_information",
        "safe_abstain_needed",
        "missing_lookup",
    ),
}


def _dedupe_nonempty(items: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    kept: list[str] = []
    for item in items:
        value = str(item or "").strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        kept.append(value)
    return tuple(kept)


_VALIDATION_CASE_LABEL_PATTERN = re.compile(r"^((?:source|held_out|negative)_\d+)_")


def _validation_error_case_labels(errors: tuple[str, ...]) -> set[str]:
    """Return public contract cases implicated by validator errors."""

    return {
        match.group(1)
        for error in errors
        if (match := _VALIDATION_CASE_LABEL_PATTERN.match(error))
    }


def _advances_repair_case_frontier(
    previous_errors: tuple[str, ...],
    repaired_errors: tuple[str, ...],
) -> bool:
    """Detect a repair that fixed every prior case but exposed different cases."""

    previous_cases = _validation_error_case_labels(previous_errors)
    repaired_cases = _validation_error_case_labels(repaired_errors)
    return bool(
        previous_cases and repaired_cases and previous_cases.isdisjoint(repaired_cases)
    )


def _validation_failure_score(validation: ValidationResult) -> int:
    if validation.accepted:
        return 0
    if not validation.errors:
        return 1000
    return sum(_validation_error_distance(error) for error in validation.errors)


def _validation_error_distance(error: str) -> int:
    if error.startswith(
        (
            "syntax_error:",
            "missing_generated_code",
            "expected_exactly_one_function",
            "function_count_mismatch:",
            "compiled_function_count_mismatch:",
            "function_name_mismatch:",
            "missing_expected_function",
            "compile_error:",
            "denied_node:",
            "denied_call:",
            "denied_attribute_call:",
        )
    ):
        return 10_000
    mismatch_tokens = ("_mismatch:", "_native_action_arguments:")
    mismatch_token = next((token for token in mismatch_tokens if token in error), "")
    if not mismatch_token or "!=" not in error:
        if "_native_action_count:" in error:
            return 50
        if "_native_action_execution_error:" in error:
            return 100
        return 20
    try:
        _, rest = error.split(mismatch_token, 1)
        actual_text, expected_text = rest.split("!=", 1)
        actual = ast.literal_eval(_literalize_validation_sentinels(actual_text))
        expected = ast.literal_eval(_literalize_validation_sentinels(expected_text))
    except Exception:
        return 10
    return _value_distance(actual, expected)


def _literalize_validation_sentinels(value: str) -> str:
    return value.replace("NOT_GIVEN", "'__NOT_GIVEN__'")


def _value_distance(actual: Any, expected: Any) -> int:
    if actual == expected:
        return 0
    if isinstance(actual, dict) and isinstance(expected, dict):
        keys = set(actual) | set(expected)
        return sum(_value_distance(actual.get(key), expected.get(key)) for key in keys)
    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        length = max(len(actual), len(expected))
        return sum(
            _value_distance(
                actual[index] if index < len(actual) else None,
                expected[index] if index < len(expected) else None,
            )
            for index in range(length)
        )
    return 1


def _observation_family_key(observation: CapabilityObservation) -> str:
    value = str(observation.task_family_key or "").strip()
    if value:
        return value
    return base_task_family(observation.scenario_name)


SCENARIO_LIKE_LABEL_PREFIXES = (
    "add_reminder_",
    "remove_reminder_",
    "modify_reminder_",
    "search_reminder_",
    "add_contact_",
    "remove_contact_",
    "modify_contact_",
    "update_contact_",
    "search_message_",
    "search_sender_",
    "send_message_",
    "search_phone_",
    "search_name_",
    "search_relationship_",
    "find_days_",
    "find_distance_",
    "find_holiday_",
    "find_thanksgiving_",
    "find_phone_",
    "find_temperature",
    "convert_currency",
    "get_wifi",
    "get_cellular",
    "wifi_off",
    "cellular_off",
    "turn_on_",
)


def _scenario_like_label(item: str) -> bool:
    value = str(item or "").strip().lower()
    return value.startswith(SCENARIO_LIKE_LABEL_PREFIXES)


def _normalize_family_label(label: str) -> str:
    normalized = str(label or "").strip().lower().replace(" ", "_").replace("-", "_")
    if not normalized:
        return ""
    return base_task_family(normalized)


def _expanded_family_labels(label: str) -> tuple[str, ...]:
    normalized = _normalize_family_label(label)
    if not normalized:
        return ()
    expanded = [normalized]
    for suffix in (
        "_twice",
        "_once",
        "_multiple_user_turn",
    ):
        if normalized.endswith(suffix):
            expanded.append(normalized[: -len(suffix)])
    return _dedupe_nonempty(expanded)


def _normalize_live_birth_routing_metadata(
    tool: GeneratedTool,
    observation: CapabilityObservation,
    base_families: tuple[str, ...],
) -> GeneratedTool:
    """Stabilize generated routing metadata before validation and registry save.

    Generation models sometimes emit full robustness-variant scenario names as
    ``applicable_task_families``. Those names are valid evidence lineage, but
    they are too narrow for natural reuse and can hide an otherwise useful
    helper on later tasks from the same base family. Normalize them into base
    family labels derived only from visible scenario names, and add the same
    labels as trigger tokens so routing does not depend on exact variants.
    """

    family_candidates: list[str] = []
    visible_context_observation = bool(observation.task_context_label)
    if not visible_context_observation:
        for item in tool.spec.applicable_task_families:
            family_candidates.extend(_expanded_family_labels(item))
    for item in base_families:
        family_candidates.extend(_expanded_family_labels(item))
    if observation.task_family_key:
        family_candidates.extend(_expanded_family_labels(observation.task_family_key))
    if not visible_context_observation:
        family_candidates.extend(_expanded_family_labels(observation.scenario_name))
        for item in CHAIN_ROUTING_FAMILIES_BY_KEY.get(observation.canonical_key, ()):
            family_candidates.extend(_expanded_family_labels(item))
    else:
        for item in VISIBLE_ROUTING_FAMILIES_BY_KEY.get(observation.canonical_key, ()):
            family_candidates.extend(_expanded_family_labels(item))
    normalized_families = _dedupe_nonempty(family_candidates)
    if not normalized_families:
        return tool
    positive_seed = (
        [item for item in tool.spec.positive_triggers if not _scenario_like_label(item)]
        if visible_context_observation
        else list(tool.spec.positive_triggers)
    )
    positive_triggers = _dedupe_nonempty([*positive_seed, *normalized_families])
    negative_triggers = (
        [item for item in tool.spec.negative_triggers if not _scenario_like_label(item)]
        if visible_context_observation
        else list(tool.spec.negative_triggers)
    )
    if (
        normalized_families == tool.spec.applicable_task_families
        and positive_triggers == tool.spec.positive_triggers
        and tuple(negative_triggers) == tool.spec.negative_triggers
    ):
        return tool
    return replace(
        tool,
        spec=replace(
            tool.spec,
            applicable_task_families=normalized_families,
            positive_triggers=positive_triggers,
            negative_triggers=_dedupe_nonempty(negative_triggers),
        ),
    )


def _observation_public_context(observation: CapabilityObservation) -> dict[str, Any]:
    """Return a non-oracle task label for birth/lifecycle events."""

    context = observation.task_context_label or observation.scenario_name
    payload: dict[str, Any] = {"scenario": context}
    if observation.task_context_label:
        payload["source_task_id_redacted"] = True
        payload["task_context_label"] = observation.task_context_label
    if observation.task_family_key:
        payload["task_family_key"] = observation.task_family_key
    return payload


def existing_broader_helper(
    canonical_key: str,
    store: RegistryStore,
) -> str | None:
    """Return a proved retained helper that already covers this shortfall mechanism."""
    for tool_name in BROADER_HELPER_OVERLAPS.get(canonical_key, ()):
        entry = store.get(tool_name)
        if (
            entry is not None
            and not entry.retired
            and has_current_validation_proof(entry)
        ):
            return tool_name
    return None


def _resolve_window_validation_examples() -> tuple[ToolExample, ...]:
    """Validation examples for the broad recency search-plan helper.

    Narrow ``recency_timestamp_bounds`` observations predate the broader
    ``resolve_search_window_or_bounds`` helper and carry bounds-only examples.
    When repair upgrades the helper to the broader search-plan contract, validate
    against the upgraded contract instead of the obsolete narrow signature.
    """

    return (
        ToolExample(
            {
                "current_timestamp": 1700000000.0,
                "phrase": "todo item I made yesterday",
                "target_domain": "reminder",
                "timestamp_intent": "creation",
                "direction": "yesterday",
                "content_keyword": "",
                "lookback_days": 0,
                "timezone_offset": 0.0,
            },
            {
                "target_tool_name": "search_reminder",
                "search_kwargs": {
                    "creation_timestamp_lowerbound": 1699913480.0,
                    "creation_timestamp_upperbound": 1699913720.0,
                },
                "should_call_search": True,
                "abstain_reason": "",
                "interpretation": "yesterday",
                "bounds_source": "resolved_direction",
            },
        ),
        ToolExample(
            {
                "current_timestamp": 1700000000.0,
                "phrase": "yesterday",
                "target_domain": "reminder",
                "timestamp_intent": "reminder",
                "direction": "yesterday",
                "content_keyword": "",
                "lookback_days": 0,
                "timezone_offset": 0.0,
            },
            {
                "target_tool_name": "search_reminder",
                "search_kwargs": {
                    "reminder_timestamp_lowerbound": 1699913480.0,
                    "reminder_timestamp_upperbound": 1699913720.0,
                },
                "should_call_search": True,
                "abstain_reason": "",
                "interpretation": "yesterday",
                "bounds_source": "resolved_direction",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "current_timestamp": 1700000000.0,
                "phrase": "next reminder",
                "target_domain": "reminder",
                "timestamp_intent": "reminder",
                "direction": "latest",
                "content_keyword": "",
                "lookback_days": 0,
                "timezone_offset": 0.0,
            },
            {
                "target_tool_name": "search_reminder",
                "search_kwargs": {
                    "reminder_timestamp_lowerbound": 1700000000.0,
                },
                "should_call_search": True,
                "abstain_reason": "",
                "interpretation": "upcoming",
                "bounds_source": "resolved_direction",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "current_timestamp": 1700000000.0,
                "phrase": "latest",
                "target_domain": "message",
                "timestamp_intent": "message_creation",
                "direction": "latest",
                "content_keyword": "hello",
                "lookback_days": 0,
                "timezone_offset": 0.0,
            },
            {
                "target_tool_name": "search_messages",
                "search_kwargs": {
                    "creation_timestamp_upperbound": 1700000000.0,
                    "content": "hello",
                },
                "should_call_search": True,
                "abstain_reason": "",
                "interpretation": "latest",
                "bounds_source": "resolved_direction",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "current_timestamp": 1700000000.0,
                "phrase": "most recent",
                "target_domain": "reminder",
                "timestamp_intent": "reminder",
                "direction": "latest",
                "content_keyword": "",
                "lookback_days": 7,
                "timezone_offset": 0.0,
            },
            {
                "target_tool_name": "search_reminder",
                "search_kwargs": {
                    "creation_timestamp_lowerbound": 1699395200.0,
                    "creation_timestamp_upperbound": 1700000000.0,
                },
                "should_call_search": True,
                "abstain_reason": "",
                "interpretation": "latest",
                "bounds_source": "resolved_direction",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "current_timestamp": 1700000000.0,
                "phrase": "latest",
                "target_domain": "reminder",
                "timestamp_intent": "creation",
                "direction": "latest",
                "content_keyword": "",
                "lookback_days": 0,
                "timezone_offset": 0.0,
            },
            {
                "target_tool_name": "search_reminder",
                "search_kwargs": {
                    "creation_timestamp_upperbound": 1700000000.0,
                },
                "should_call_search": True,
                "abstain_reason": "",
                "interpretation": "latest",
                "bounds_source": "resolved_direction",
            },
            held_out=True,
        ),
    )


def _prepare_location_validation_examples() -> tuple[ToolExample, ...]:
    """Validation examples for generated location-search argument preparation."""

    return (
        ToolExample(
            {
                "user_request": "Add a reminder to buy milk at Whole Foods on Stevens Creek tomorrow.",
                "location_phrase": "",
                "latitude": 0.0,
                "longitude": 0.0,
            },
            {
                "search_location_kwargs": {
                    "location": "Whole Foods on Stevens Creek",
                },
                "should_call_downstream_tool": True,
                "downstream_tool_name": "search_location_around_lat_lon",
                "downstream_tool_kwargs": {
                    "location": "Whole Foods on Stevens Creek",
                },
                "location_query": "Whole Foods on Stevens Creek",
                "abstain_reason": "",
            },
        ),
        ToolExample(
            {
                "user_request": "Add a reminder to buy milk at Whole Foods.",
                "location_phrase": "Whole Foods",
                "latitude": 0.0,
                "longitude": 0.0,
            },
            {
                "search_location_kwargs": {},
                "should_call_downstream_tool": False,
                "downstream_tool_name": "",
                "downstream_tool_kwargs": {},
                "location_query": "Whole Foods",
                "abstain_reason": "missing_reminder_time_before_location_lookup",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "user_request": "Whole Foods on Stevens Creek",
                "location_phrase": "Whole Foods",
                "latitude": 0.0,
                "longitude": 0.0,
            },
            {
                "search_location_kwargs": {
                    "location": "Whole Foods on Stevens Creek",
                },
                "should_call_downstream_tool": True,
                "downstream_tool_name": "search_location_around_lat_lon",
                "downstream_tool_kwargs": {
                    "location": "Whole Foods on Stevens Creek",
                },
                "location_query": "Whole Foods on Stevens Creek",
                "abstain_reason": "",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "user_request": "Find a Whole Foods near me.",
                "location_phrase": "Whole Foods",
                "latitude": 0.0,
                "longitude": 0.0,
            },
            {
                "search_location_kwargs": {},
                "should_call_downstream_tool": True,
                "downstream_tool_name": "get_current_location",
                "downstream_tool_kwargs": {},
                "location_query": "Whole Foods",
                "abstain_reason": "need_current_coordinates_for_broad_location_query",
            },
        ),
        ToolExample(
            {
                "user_request": "Find a Whole Foods near me.",
                "location_phrase": "Whole Foods",
                "latitude": 37.323,
                "longitude": -122.032,
            },
            {
                "search_location_kwargs": {
                    "location": "Whole Foods",
                    "latitude": 37.323,
                    "longitude": -122.032,
                },
                "should_call_downstream_tool": True,
                "downstream_tool_name": "search_location_around_lat_lon",
                "downstream_tool_kwargs": {
                    "location": "Whole Foods",
                    "latitude": 37.323,
                    "longitude": -122.032,
                },
                "location_query": "Whole Foods",
                "abstain_reason": "",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "user_request": "Add a reminder tomorrow at 5 PM.",
                "location_phrase": "",
                "latitude": 0.0,
                "longitude": 0.0,
            },
            {
                "search_location_kwargs": {},
                "should_call_downstream_tool": False,
                "downstream_tool_name": "",
                "downstream_tool_kwargs": {},
                "location_query": "",
                "abstain_reason": "missing_location_phrase",
            },
            negative_applicability=True,
        ),
    )


def _validation_examples_for_tool(
    tool: GeneratedTool,
    observation: CapabilityObservation,
) -> tuple[ToolExample, ...]:
    if (
        observation.canonical_key
        in {
            "derived_value:recency_timestamp_bounds",
            "derived_value:resolve_search_window_or_bounds",
        }
        and tool.spec.tool_name == "resolve_search_window_or_bounds"
    ):
        return _resolve_window_validation_examples()
    if (
        observation.canonical_key == "composite:prepare_location_search_args"
        and tool.spec.tool_name == "prepare_location_search_args"
    ):
        return _prepare_location_validation_examples()
    return observation.validation_examples


def _original_tool_contract_errors(
    tool: GeneratedTool,
    observation: CapabilityObservation,
) -> tuple[str, ...]:
    """Reject placeholder or non-observed ToolSandbox producer contracts.

    Candidate specs must preserve concrete original ToolSandbox calls. A broad
    generated helper is allowed to list several possible producer tools, but it
    cannot invent a placeholder such as ``search_service_payload`` that will
    never be present in a scenario allow-list.
    """
    observed = set(observation.failed_tool_calls) | set(
        observation.repeated_failed_tool_calls
    )
    if not observed:
        return ()
    declared = set(tool.spec.required_original_tool_calls) | set(
        tool.spec.preserves_side_effect_tools
    )
    if not declared:
        return ()
    lowered_observed = {item.lower() for item in observed}
    placeholder = sorted(
        item
        for item in declared
        if item.lower() not in lowered_observed
        and any(token in item.lower() for token in PLACEHOLDER_ORIGINAL_TOOL_TOKENS)
    )
    if placeholder:
        return ("placeholder_downstream_original_tool:" + ",".join(placeholder),)
    if not (declared & observed):
        return ("missing_observed_original_tool_preservation",)
    return ()


@dataclass
class OnlineBirthController:
    store: RegistryStore
    generator: GeneratedToolFactory
    output_dir: Path
    recurrence_threshold: int = 2
    event_hook: CampaignEventHook | None = None
    counts: Counter[str] = field(default_factory=Counter)
    scenarios_by_key: dict[str, set[str]] = field(default_factory=dict)
    base_families_by_key: dict[str, set[str]] = field(default_factory=dict)
    generated_keys: set[str] = field(default_factory=set)
    rejected_counts: Counter[str] = field(default_factory=Counter)
    max_rejections_per_key: int = MAX_REJECTIONS_PER_TOOL_KEY
    failure_memory_path: Path | None = Path("artifacts/summaries/failure_memory.json")
    pre_scenario_visible_observations: set[str] = field(default_factory=set)

    def _write_generation_status(self, event: str, payload: dict[str, Any]) -> None:
        status_path = self.output_dir / "tool_generation_status.json"
        try:
            status_path.write_text(
                json.dumps(
                    {
                        "event": event,
                        "timestamp": time.time(),
                        **payload,
                    },
                    indent=2,
                    default=str,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            append_jsonl(
                self.output_dir / "sage_run_events.jsonl",
                {
                    "event": "tool_generation_status_write_failed",
                    "attempted_event": event,
                    "error": f"{type(exc).__name__}:{exc}",
                },
            )

    def _event(self, event: str, payload: dict[str, Any]) -> None:
        self._write_generation_status(event, payload)
        if self.event_hook is not None:
            try:
                self.event_hook(event, payload)
            except Exception as exc:
                append_jsonl(
                    self.output_dir / "sage_run_events.jsonl",
                    {
                        "event": "campaign_event_hook_failed",
                        "attempted_event": event,
                        "error": f"{type(exc).__name__}:{exc}",
                        **payload,
                    },
                )

    def prime_before_scenario(
        self, scenario_name: str, scenario: Any | None = None
    ) -> list[str]:
        """Birth helpers just in time from visible task text before the task runs.

        This path is intentionally oracle-free: it uses the same unlabeled
        task context available to the actor before the candidate trajectory is
        played or scored. It gives a newly born helper a natural same-task
        adoption chance without force-calling it or using result feedback from
        the task.
        """

        if scenario is None:
            return []
        accepted: list[str] = []
        observation_count = 0
        keys_before = set(self.generated_keys)
        observations = classify_visible_task_observations(scenario_name, scenario)
        self.pre_scenario_visible_observations.add(scenario_name)
        observations = tuple(
            sorted(observations, key=_native_action_observation_priority)
        )
        validated_action_tool_name = ""
        for observation_index, observation in enumerate(observations):
            if validated_action_tool_name and not _complements_validated_native_action(
                observation
            ):
                self._event(
                    "jit_proactive_birth_stopped_after_action_tool",
                    {
                        **_observation_public_context(observation),
                        "canonical_key": observation.canonical_key,
                        "tool_name": validated_action_tool_name,
                        "remaining_observation_count": (
                            len(observations) - observation_index
                        ),
                        "reason": "non_dependency_observations_suppressed",
                    },
                )
                break
            if not observation.generation_allowed:
                continue
            observation_count += 1
            self._event(
                "jit_proactive_inadequacy_detected",
                {
                    **_observation_public_context(observation),
                    "canonical_key": observation.canonical_key,
                    "evidence_source": observation.evidence_source,
                    "reason": observation.reason,
                },
            )
            tool_name = self.observe(observation)
            if tool_name:
                accepted.append(tool_name)
            resolved_tool_name = tool_name or suggested_tool_name(
                observation.canonical_key
            )
            entry = (
                self.store.get(resolved_tool_name)
                if resolved_tool_name is not None
                else None
            )
            if (
                entry is not None
                and not bool(getattr(entry, "retired", False))
                and (bool(tool_name) or has_current_validation_proof(entry))
                and entry.tool.spec.native_action_delegation
            ):
                validated_action_tool_name = resolved_tool_name
                self._event(
                    "jit_proactive_action_tool_ready",
                    {
                        **_observation_public_context(observation),
                        "canonical_key": observation.canonical_key,
                        "tool_name": resolved_tool_name,
                        "remaining_observation_count": (
                            len(observations) - observation_index - 1
                        ),
                        "reason": (
                            "validated_action_gap_satisfied"
                            if tool_name
                            else "existing_validated_action_gap_satisfied"
                        ),
                    },
                )
        born_keys = sorted(set(self.generated_keys) - keys_before)
        if observation_count or born_keys:
            task_context = ""
            task_family_key = ""
            source_task_id_redacted = False
            first = next(iter(observations), None)
            if first is not None and first.task_context_label:
                task_context = first.task_context_label
                task_family_key = first.task_family_key
                source_task_id_redacted = True
            context_payload = (
                {
                    "scenario": task_context,
                    "task_context_label": task_context,
                    "task_family_key": task_family_key,
                    "source_task_id_redacted": source_task_id_redacted,
                }
                if task_context
                else {"scenario": scenario_name}
            )
            self._event(
                "jit_proactive_scenario_reflection_completed",
                {
                    **context_payload,
                    "observation_count": observation_count,
                    "born_or_suppressed_keys": born_keys,
                    "accepted_tools": accepted,
                    "registry_dir": str(self.store.root),
                },
            )
        return accepted

    def _required_recurrence_threshold(self, observation: CapabilityObservation) -> int:
        if observation.canonical_key in FIRST_OBSERVATION_BIRTH_KEYS:
            return 1
        return self.recurrence_threshold

    def _check_heuristic_signal(self, observation: CapabilityObservation) -> bool:
        """Attempt lightweight transcript verification for heuristic observations.

        Returns True if at least one claimed signal token is found in the
        conversation transcript, False otherwise.  Verification failure is
        logged but never blocks generation (labeling sprint, not blocking).
        """
        conv_path = (
            self.output_dir
            / "trajectories"
            / observation.scenario_name
            / "conversation.json"
        )
        if not conv_path.exists():
            return False
        try:
            import json as _json

            messages = _json.loads(conv_path.read_text(encoding="utf-8"))
        except Exception:
            return False
        if not isinstance(messages, list):
            return False
        transcript_text = " ".join(
            str(m.get("content", "")) + " " + str(m.get("name", ""))
            for m in messages
            if isinstance(m, dict)
        ).lower()
        for signal in observation.inadequacy_signals:
            if (
                signal.lower().replace("_", " ") in transcript_text
                or signal.lower() in transcript_text
            ):
                return True
        for tool in observation.failed_tool_calls:
            if tool.lower() in transcript_text:
                return True
        return False

    def _cluster_context(self, observation: CapabilityObservation) -> dict[str, Any]:
        scenarios = sorted(self.scenarios_by_key.get(observation.canonical_key, set()))
        families = sorted(
            self.base_families_by_key.get(observation.canonical_key, set())
        )
        required_families = (
            3
            if observation.canonical_key == "composite:constraint_to_action_planner"
            else 2
        )
        non_diagnostic = (
            len(scenarios) >= self.recurrence_threshold
            and len(families) >= required_families
        )
        return {
            "cluster_id": observation.canonical_key,
            "failure_mechanism": observation.canonical_key,
            "scenario_count": len(scenarios),
            "scenarios": scenarios[:20],
            "distinct_base_task_families": len(families),
            "base_task_families": families[:20],
            "required_distinct_base_task_families": required_families,
            "near_duplicate_only": len(families) < required_families,
            "non_diagnostic_birth_allowed": non_diagnostic,
            "repeated_failed_tool_calls": list(observation.repeated_failed_tool_calls),
            "failed_tool_calls": list(observation.failed_tool_calls),
            "inadequacy_signals": list(observation.inadequacy_signals),
            "current_helper_fit": (
                ()
                if observation.task_context_label
                else expected_helper_fit(observation.scenario_name)
            ),
            "positive_applicability_example_count": sum(
                1
                for item in observation.validation_examples
                if not item.negative_applicability
            ),
            "negative_applicability_example_count": sum(
                1
                for item in observation.validation_examples
                if item.negative_applicability
            ),
        }

    def observe(self, observation: CapabilityObservation) -> str | None:
        append_jsonl(
            self.output_dir / "capability_observations.jsonl",
            observation.to_json(),
        )
        self.counts[observation.canonical_key] += 1
        self.scenarios_by_key.setdefault(observation.canonical_key, set()).add(
            observation.task_context_label or observation.scenario_name
        )
        self.base_families_by_key.setdefault(observation.canonical_key, set()).add(
            _observation_family_key(observation)
        )
        # Log heuristic observations that cannot be transcript-verified.
        if observation.evidence_source == "heuristic":
            verified = self._check_heuristic_signal(observation)
            if not verified:
                append_jsonl(
                    self.output_dir / "sage_run_events.jsonl",
                    {
                        "event": "tool_birth_heuristic_unverified",
                        "canonical_key": observation.canonical_key,
                        "scenario": observation.scenario_name,
                        "evidence_source": observation.evidence_source,
                        "note": "scenario-name prefix heuristic could not be confirmed in transcript",
                    },
                )
        if not observation.generation_allowed:
            return None
        if observation.canonical_key in self.generated_keys:
            return None
        if observation.canonical_key == "composite:plan_message_counterparty_search":
            append_jsonl(
                self.output_dir / "sage_run_events.jsonl",
                {
                    "event": "tool_birth_skipped_decomposed_complex_contract",
                    "canonical_key": observation.canonical_key,
                    "scenario": observation.scenario_name,
                    "replacement_strategy": (
                        "birth smaller generated tools for current-user lookup, "
                        "message search/window selection, and contact-update target "
                        "selection instead of one large message-counterparty planner"
                    ),
                },
            )
            self._event(
                "tool_birth_skipped_decomposed_complex_contract",
                {
                    "canonical_key": observation.canonical_key,
                    "scenario": observation.scenario_name,
                },
            )
            return None
        if (
            self.rejected_counts[observation.canonical_key]
            >= self.max_rejections_per_key
        ):
            append_jsonl(
                self.output_dir / "sage_run_events.jsonl",
                {
                    "event": "tool_birth_retry_suppressed",
                    "canonical_key": observation.canonical_key,
                    "rejection_count": self.rejected_counts[observation.canonical_key],
                    "max_rejections_per_key": self.max_rejections_per_key,
                },
            )
            return None
        if self.counts[observation.canonical_key] < self._required_recurrence_threshold(
            observation
        ):
            return None

        suggested_name = suggested_tool_name(observation.canonical_key)
        if suggested_name is not None:
            existing_entry = self.store.get(suggested_name)
            if (
                existing_entry is not None
                and not existing_entry.retired
                and has_current_validation_proof(existing_entry)
            ):
                self.generated_keys.add(observation.canonical_key)
                append_jsonl(
                    self.output_dir / "sage_run_events.jsonl",
                    {
                        "event": "tool_birth_skipped_existing",
                        "canonical_key": observation.canonical_key,
                        "tool_name": suggested_name,
                        "registry_dir": str(self.store.root),
                    },
                )
                self._event(
                    "tool_birth_skipped_existing",
                    {
                        "canonical_key": observation.canonical_key,
                        "tool_name": suggested_name,
                        "registry_dir": str(self.store.root),
                    },
                )
                return None
            if existing_entry is not None and not has_current_validation_proof(
                existing_entry
            ):
                append_jsonl(
                    self.output_dir / "sage_run_events.jsonl",
                    {
                        "event": "tool_birth_existing_requires_revalidation",
                        "canonical_key": observation.canonical_key,
                        "tool_name": suggested_name,
                        "registry_dir": str(self.store.root),
                    },
                )

        broader_tool_name = existing_broader_helper(
            observation.canonical_key,
            self.store,
        )
        if broader_tool_name is not None:
            self.generated_keys.add(observation.canonical_key)
            payload = {
                "event": "tool_birth_skipped_existing_broader_helper",
                "canonical_key": observation.canonical_key,
                "tool_name": broader_tool_name,
                "registry_dir": str(self.store.root),
                "overlap_reason": (
                    "proved retained helper already covers this shortfall mechanism"
                ),
            }
            append_jsonl(self.output_dir / "sage_run_events.jsonl", payload)
            self._event("tool_birth_skipped_existing_broader_helper", payload)
            return None

        generation_examples = observation.validation_examples
        if (
            suggested_name == "resolve_search_window_or_bounds"
            and observation.canonical_key
            in {
                "derived_value:recency_timestamp_bounds",
                "derived_value:resolve_search_window_or_bounds",
            }
        ):
            # Generation and deterministic validation must see the same public
            # broad contract. Otherwise a narrow source observation can produce
            # code that is judged against capabilities never shown to the model.
            generation_examples = _resolve_window_validation_examples()

        request = ToolGenerationRequest(
            scenario_name=observation.task_context_label or observation.scenario_name,
            observation=observation.observation,
            allowed_families=observation.allowed_families,
            validation_examples=tuple(
                {
                    "inputs": item.inputs,
                    "expected": item.expected,
                    "held_out": item.held_out,
                    "negative_applicability": item.negative_applicability,
                }
                for item in generation_examples
            ),
            suggested_tool_name=suggested_name,
            inadequacy_evidence=observation.to_inadequacy_evidence().to_json(),
            failure_memory_context=generation_failure_memory_context(
                self.failure_memory_path,
                canonical_key=observation.canonical_key,
                suggested_tool_name=suggested_name,
            ),
            shortfall_cluster_context=self._cluster_context(observation),
        )
        self._event(
            "tool_birth_started",
            {
                "canonical_key": observation.canonical_key,
                "scenario": observation.scenario_name,
                "allowed_families": observation.allowed_families,
            },
        )
        try:
            generation_started = time.monotonic()
            tool = self.generator.generate(request)
            generation_elapsed = time.monotonic() - generation_started
            self._event(
                "tool_generation_completed",
                {
                    "canonical_key": observation.canonical_key,
                    "scenario": observation.scenario_name,
                    "tool_name": tool.spec.tool_name,
                    "elapsed_seconds": round(generation_elapsed, 3),
                    "code_chars": len(tool.code),
                    "code": tool.code,
                    "estimated_step_compression": (
                        tool.spec.estimated_step_compression
                    ),
                    "cross_task_applicability_count": (
                        tool.spec.cross_task_applicability_count
                    ),
                },
            )
            cluster_context = self._cluster_context(observation)
            tool = _normalize_live_birth_routing_metadata(
                tool,
                observation,
                tuple(cluster_context["base_task_families"]),
            )
            if (
                not cluster_context["non_diagnostic_birth_allowed"]
                and not tool.spec.diagnostic_only
            ):
                tool = replace(
                    tool,
                    spec=replace(
                        tool.spec,
                        diagnostic_only=True,
                        shortfall_cluster_evidence=(
                            *tool.spec.shortfall_cluster_evidence,
                            "diagnostic_only_near_duplicate_or_single_family_cluster",
                        ),
                    ),
                )
            self._event(
                "validation_started",
                {
                    "canonical_key": observation.canonical_key,
                    "tool_name": tool.spec.tool_name,
                    "scenario": observation.scenario_name,
                    "code": tool.code,
                },
            )
            memory_gate, live_check, validation = self._gate_and_validate(
                tool,
                observation,
            )
            repair_attempted = False
            repair_attempt_count = 0
            repair_errors: tuple[str, ...] = ()
            repair_history: list[dict[str, Any]] = []
            repair_method = getattr(self.generator, "repair", None)
            repair_candidates_method = getattr(
                self.generator, "repair_candidates", None
            )
            best_tool = tool
            best_memory_gate = memory_gate
            best_live_check = live_check
            best_validation = validation
            best_validation_score = _validation_failure_score(validation)
            repair_seed_tool = tool
            repair_seed_validation = validation
            repair_error_history = list(validation.errors)
            if not validation.accepted and callable(repair_method):
                repair_errors = tuple(validation.errors)
                for attempt in range(1, CANDIDATE_REPAIR_ATTEMPTS + 1):
                    if validation.accepted:
                        break
                    repair_attempted = True
                    repair_attempt_count = attempt
                    current_errors = tuple(
                        dict.fromkeys(
                            (
                                *repair_error_history,
                                *repair_seed_validation.errors,
                            )
                        )
                    )
                    if repair_seed_tool.spec.native_action_delegation:
                        # Repair the best candidate's remaining failures only. Old
                        # errors describe branches that candidate already fixed and
                        # can make model repair reintroduce those failures.
                        current_errors = tuple(repair_seed_validation.errors)
                    self._event(
                        "tool_repair_started",
                        {
                            "canonical_key": observation.canonical_key,
                            "tool_name": repair_seed_tool.spec.tool_name,
                            "attempt": attempt,
                            "input_errors": list(current_errors),
                            "best_validation_score": best_validation_score,
                        },
                    )
                    repair_started = time.monotonic()
                    # Repeating an identical model prompt tends to reproduce the
                    # same failed implementation. Vary the repair strategy for
                    # every generated-tool family while keeping the public
                    # contract and validation errors unchanged.
                    repair_input_errors = (
                        *current_errors,
                        f"repair_strategy:{attempt}",
                    )
                    if callable(repair_candidates_method):
                        repaired_candidates = tuple(
                            repair_candidates_method(
                                request,
                                repair_seed_tool,
                                repair_input_errors,
                            )
                        )
                    else:
                        repaired_candidates = (
                            repair_method(
                                request,
                                repair_seed_tool,
                                repair_input_errors,
                            ),
                        )
                    if not repaired_candidates:
                        raise ValueError("tool repair returned no candidates")
                    repair_elapsed = time.monotonic() - repair_started
                    candidate_results: list[
                        tuple[GeneratedTool, Any, Any, ValidationResult, int]
                    ] = []
                    for candidate in repaired_candidates:
                        normalized_candidate = _normalize_live_birth_routing_metadata(
                            candidate,
                            observation,
                            tuple(
                                self._cluster_context(observation)["base_task_families"]
                            ),
                        )
                        candidate_gate, candidate_live_check, candidate_validation = (
                            self._gate_and_validate(normalized_candidate, observation)
                        )
                        candidate_results.append(
                            (
                                normalized_candidate,
                                candidate_gate,
                                candidate_live_check,
                                candidate_validation,
                                _validation_failure_score(candidate_validation),
                            )
                        )
                    selected_candidate_index = min(
                        range(len(candidate_results)),
                        key=lambda index: (
                            not candidate_results[index][3].accepted,
                            candidate_results[index][4],
                            index,
                        ),
                    )
                    (
                        repaired_tool,
                        repaired_gate,
                        repaired_live_check,
                        repaired_validation,
                        repaired_score,
                    ) = candidate_results[selected_candidate_index]
                    advanced_case_frontier = (
                        repair_seed_tool.spec.native_action_delegation
                        and _advances_repair_case_frontier(
                            tuple(repair_seed_validation.errors),
                            tuple(repaired_validation.errors),
                        )
                    )
                    repair_error_history.extend(
                        error
                        for error in repaired_validation.errors
                        if error not in repair_error_history
                    )
                    improved = repaired_validation.accepted or (
                        repaired_score < best_validation_score
                    )
                    repair_record = {
                        "attempt": attempt,
                        "input_errors": list(current_errors),
                        "repaired_errors": list(repaired_validation.errors),
                        "accepted": repaired_validation.accepted,
                        "repaired_tool_name": repaired_tool.spec.tool_name,
                        "elapsed_seconds": round(repair_elapsed, 3),
                        "code_chars": len(repaired_tool.code),
                        "code": repaired_tool.code,
                        "validation_score": repaired_score,
                        "improved_best": improved,
                        "advanced_case_frontier": advanced_case_frontier,
                        "repair_candidate_count": len(candidate_results),
                        "selected_candidate_index": selected_candidate_index,
                        "repair_candidate_validations": [
                            {
                                "candidate_index": index,
                                "accepted": candidate_validation.accepted,
                                "validation_score": candidate_score,
                                "errors": list(candidate_validation.errors),
                            }
                            for index, (
                                _candidate,
                                _candidate_gate,
                                _candidate_live_check,
                                candidate_validation,
                                candidate_score,
                            ) in enumerate(candidate_results)
                        ],
                    }
                    repair_history.append(repair_record)
                    self._event(
                        "tool_repair_attempted",
                        {
                            "canonical_key": observation.canonical_key,
                            "tool_name": tool.spec.tool_name,
                            **repair_record,
                        },
                    )
                    if improved:
                        best_tool = repaired_tool
                        best_memory_gate = repaired_gate
                        best_live_check = repaired_live_check
                        best_validation = repaired_validation
                        best_validation_score = repaired_score
                    # A native-action candidate can temporarily score worse while it
                    # fixes every previously failing case and exposes a different
                    # branch. Continue from that complementary candidate so the next
                    # repair can combine both behaviors; otherwise return to the best
                    # proved candidate instead of drifting through arbitrary failures.
                    if (
                        best_tool.spec.native_action_delegation
                        and not improved
                        and not advanced_case_frontier
                    ):
                        repair_seed_tool = best_tool
                        repair_seed_validation = best_validation
                    else:
                        repair_seed_tool = repaired_tool
                        repair_seed_validation = repaired_validation
                    tool = best_tool
                    memory_gate = best_memory_gate
                    live_check = best_live_check
                    validation = best_validation
        except Exception as exc:
            if "generation_started" in locals():
                elapsed_seconds = round(time.monotonic() - generation_started, 3)
            else:
                elapsed_seconds = None
            append_jsonl(
                self.output_dir / "tool_birth_events.jsonl",
                {
                    "canonical_key": observation.canonical_key,
                    "accepted": False,
                    "errors": [f"generation_error:{type(exc).__name__}:{exc}"],
                    "elapsed_seconds": elapsed_seconds,
                },
            )
            self.rejected_counts[observation.canonical_key] += 1
            self._event(
                "tool_birth_rejected",
                {
                    "canonical_key": observation.canonical_key,
                    **_observation_public_context(observation),
                    "error": f"{type(exc).__name__}:{exc}",
                    "elapsed_seconds": elapsed_seconds,
                    "rejection_count": self.rejected_counts[observation.canonical_key],
                },
            )
            return None

        birth_context = observation.task_context_label or observation.scenario_name
        append_jsonl(
            self.output_dir / "tool_birth_events.jsonl",
            {
                "canonical_key": observation.canonical_key,
                **_observation_public_context(observation),
                "birth_scenario": birth_context,
                "evidence_source": observation.evidence_source,
                "observation_reason": observation.reason,
                "tool_name": tool.spec.tool_name,
                "family": tool.spec.family.value,
                "estimated_step_compression": tool.spec.estimated_step_compression,
                "cross_task_applicability_count": tool.spec.cross_task_applicability_count,
                "applicable_task_families": list(tool.spec.applicable_task_families),
                "reason_tool_is_decisive": tool.spec.reason_tool_is_decisive,
                "accepted": validation.accepted,
                "errors": list(validation.errors),
                "source_example_count": validation.source_example_count,
                "held_out_check_count": validation.held_out_check_count,
                "runtime_smoke_passed": validation.runtime_smoke_passed,
                "grading_classification": memory_gate.grading_classification,
                "canonical_route_substitution_risk": (
                    tool.spec.canonical_route_substitution_risk
                ),
                "expected_milestone_calls_replaced": list(
                    tool.spec.expected_milestone_calls_replaced
                ),
                "final_state_preservation_plan": tool.spec.final_state_preservation_plan,
                "grading_accounting_note": tool.spec.grading_accounting_note,
                "lightweight_live_validation": (
                    live_check.to_json() if live_check is not None else None
                ),
                "repair_attempted": repair_attempted,
                "repair_attempt_count": repair_attempt_count,
                "repair_errors": list(repair_errors),
                "repair_final_errors": list(validation.errors)
                if repair_attempted
                else [],
                "repair_history": repair_history,
            },
        )
        self._event(
            "validation_passed" if validation.accepted else "validation_failed",
            {
                "canonical_key": observation.canonical_key,
                "tool_name": tool.spec.tool_name,
                **_observation_public_context(observation),
                "errors": list(validation.errors),
                "source_example_count": validation.source_example_count,
                "held_out_check_count": validation.held_out_check_count,
                "runtime_smoke_passed": validation.runtime_smoke_passed,
                "estimated_step_compression": tool.spec.estimated_step_compression,
                "cross_task_applicability_count": tool.spec.cross_task_applicability_count,
                "applicable_task_families": list(tool.spec.applicable_task_families),
                "grading_classification": memory_gate.grading_classification,
                "canonical_route_substitution_risk": (
                    tool.spec.canonical_route_substitution_risk
                ),
                "lightweight_live_validation": (
                    live_check.to_json() if live_check is not None else None
                ),
                "repair_attempted": repair_attempted,
                "repair_attempt_count": repair_attempt_count,
                "code": tool.code,
            },
        )
        if validation.accepted:
            self.generated_keys.add(observation.canonical_key)
            entry = RegistryEntry.accepted(
                tool,
                validation,
                birth_scenario=birth_context,
            )
            self.store.put(entry)
            saved_entry = self.store.get(tool.spec.tool_name) or entry
            snapshot_dir = self.output_dir / "generated_tool_snapshots"
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            snapshot_path = (
                snapshot_dir / f"{tool.spec.tool_name}_v{saved_entry.version}.py"
            )
            snapshot_path.write_text(tool.code + "\n", encoding="utf-8")
            append_jsonl(
                self.output_dir / "sage_run_events.jsonl",
                {
                    "event": "registry_save",
                    "registry_dir": str(self.store.root),
                    "tool_name": tool.spec.tool_name,
                    "birth_scenario": birth_context,
                    "snapshot_path": str(snapshot_path),
                },
            )
            self._event(
                "tool_birth_succeeded",
                {
                    "canonical_key": observation.canonical_key,
                    "tool_name": tool.spec.tool_name,
                    **_observation_public_context(observation),
                    "family": tool.spec.family.value,
                    "snapshot_path": str(snapshot_path),
                    "code": tool.code,
                },
            )
            self._event(
                "registry_saved",
                {
                    "registry_dir": str(self.store.root),
                    "tool_name": tool.spec.tool_name,
                    **_observation_public_context(observation),
                },
            )
            return tool.spec.tool_name
        else:
            self.rejected_counts[observation.canonical_key] += 1
            self._event(
                "tool_birth_rejected",
                {
                    "canonical_key": observation.canonical_key,
                    "tool_name": tool.spec.tool_name,
                    **_observation_public_context(observation),
                    "errors": list(validation.errors),
                    "code": tool.code,
                    "rejection_count": self.rejected_counts[observation.canonical_key],
                },
            )
        return None

    def _gate_and_validate(
        self,
        tool: GeneratedTool,
        observation: CapabilityObservation,
    ) -> tuple[Any, Any, ValidationResult]:
        examples = _validation_examples_for_tool(tool, observation)
        memory_gate = evaluate_candidate_gate(
            tool.spec,
            failure_memory_path=self.failure_memory_path,
        )
        if not memory_gate.allowed:
            return (
                memory_gate,
                None,
                ValidationResult(False, (memory_gate.reason,)),
            )
        original_contract_errors = _original_tool_contract_errors(tool, observation)
        if original_contract_errors:
            return (
                memory_gate,
                None,
                ValidationResult(False, original_contract_errors),
            )
        live_check = None
        return (
            memory_gate,
            live_check,
            validate_generated_tool(
                tool,
                examples=examples,
            ),
        )
