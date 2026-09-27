"""Immutable generated-tool family definitions and shared routing constants."""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping


@dataclass(frozen=True, slots=True)
class GeneratedToolFamilyDefinition:
    """Independent generation and routing metadata for one generated tool."""

    applicable_task_families: tuple[str, ...] | None
    default_original_tool_calls: tuple[str, ...] | None
    visible_context_signals: tuple[str, ...] | None


def _family(
    applicable: tuple[str, ...] | None,
    original_calls: tuple[str, ...] | None,
    visible_signals: tuple[str, ...] | None,
) -> GeneratedToolFamilyDefinition:
    return GeneratedToolFamilyDefinition(applicable, original_calls, visible_signals)


# Each definition keeps the three policies independent.  ``None`` means the tool
# was absent from that historical policy, rather than present with an empty tuple.
# fmt: off
GENERATED_TOOL_FAMILY_DEFINITIONS: Mapping[str, GeneratedToolFamilyDefinition] = MappingProxyType({
    "plan_contact_lookup_query": _family(
        ("contact_lookup", "contact_phone_lookup", "contact_relationship_lookup"),
        ("search_contacts",), ("contact_lookup",)),
    "plan_contact_relationship_batch_update": _family(
        ("relationship_batch_update", "contact_bulk_update", "contact_lookup"),
        ("search_contacts", "modify_contact"), ("relationship_batch_update",)),
    "prepare_reminder_creation_args": _family(
        ("reminder_create", "relative_time", "location_phrase"),
        ("add_reminder",), ("reminder_create",)),
    "relative_day_time_to_timestamp": _family(
        ("relative_time", "reminder_create"),
        ("get_current_timestamp", "timestamp_to_datetime_info", "add_reminder", "modify_reminder"),
        ("relative_time",)),
    "next_weekday_time_to_timestamp": _family(
        ("weekday_time", "reminder_create"),
        ("get_current_timestamp", "timestamp_to_datetime_info", "add_reminder", "modify_reminder"),
        ("weekday_time",)),
    "prepare_location_search_args": _family(
        ("location_phrase", "reminder_create", "external_lookup"),
        ("get_current_location", "search_location_around_lat_lon"),
        ("location_phrase", "external_lookup")),
    "prepare_specific_location_search_args": _family(
        ("location_phrase", "reminder_create", "external_lookup"),
        ("search_location_around_lat_lon",), ("location_phrase", "external_lookup")),
    "prepare_broad_location_search_args": _family(
        ("location_phrase", "reminder_create", "external_lookup"),
        ("get_current_location", "search_location_around_lat_lon"),
        ("location_phrase", "external_lookup")),
    "plan_message_counterparty_search": _family(
        ("message_counterparty_lookup", "message", "contact_lookup"),
        ("search_contacts", "search_messages"),
        ("message_counterparty_lookup", "message_counterparty_update")),
    "select_message_counterparty_for_contact_update": _family(
        ("message_counterparty_update", "message_recency", "modify_contact"),
        ("search_messages", "modify_contact"),
        ("contact_lookup", "message_counterparty_lookup", "message_counterparty_update")),
    "resolve_search_window_or_bounds": _family(
        ("recency_search", "message_recency", "reminder_recency", "recency_action"),
        ("search_reminder", "search_messages"),
        ("recency_search", "message_search_followup_possible")),
    "prepare_upcoming_reminder_search_args": _family(
        ("upcoming_reminder_search", "reminder_due_time_search"),
        ("search_reminder",), None),
    "prepare_message_recency_search_args": _family(
        ("message_recency_search", "message_recency", "message_counterparty_update"),
        ("search_messages",), None),
    "prepare_past_reminder_recency_search_args": _family(
        ("past_reminder_recency_search", "reminder_creation_recency_search"),
        ("search_reminder",), None),
    "select_record_by_timestamp_extreme": _family(
        ("recency_search", "message_recency", "reminder_recency"),
        ("search_reminder", "search_messages"),
        ("recency_search", "message_search_followup_possible")),
    "select_message_content_by_recency": _family(
        ("message_recency", "recency_search"), ("search_messages",),
        ("message_recency", "message_search_followup_possible")),
    "select_action_target_by_recency": _family(
        ("recency_action", "modify_reminder", "remove_reminder"),
        ("search_reminder", "modify_reminder", "remove_reminder"), ("recency_action",)),
    "prepare_holiday_search_args": _family(
        ("holiday_lookup", "holiday_timestamp", "calendar_distance"),
        ("search_holiday",), ("holiday",)),
    "days_between_timestamps": _family(
        ("calendar_distance", "holiday_distance", "timestamp_difference"),
        ("get_current_timestamp", "search_holiday"), ("calendar_distance",)),
    "plan_device_status_lookup": _family(
        ("device_status_read", "wifi_status_read", "cellular_status_read"),
        (
            "get_wifi_status", "get_cellular_service_status",
            "get_location_service_status", "get_low_battery_mode_status",
        ),
        ("device_status_read",)),
    "plan_device_state_action_sequence_v3": _family(
        (
            "device_state_action", "wifi_service_recovery",
            "cellular_service_recovery", "location_service_recovery",
            "low_battery_precondition_recovery", "blocked_downstream_task_continuation",
        ),
        (
            "set_wifi_status", "set_cellular_service_status",
            "set_location_service_status", "set_low_battery_mode_status",
        ),
        ("device_state_action", "direct_device_state_action", "state_precondition_possible")),
    "plan_device_state_action_sequence_location_recovery": _family(
        (
            "device_state_action", "location_service_recovery", "wifi_service_recovery",
            "low_battery_precondition_recovery",
            "blocked_downstream_location_task_continuation",
        ),
        ("set_location_service_status", "set_low_battery_mode_status", "set_wifi_status"),
        ("location_phrase",)),
    "plan_send_message_contact_lookup": _family(
        ("named_message_recipient", "contact_lookup", "send_message"),
        ("search_contacts", "send_message_with_phone_number"), ("named_message_recipient",)),
    "prepare_direct_contact_action_args": _family(
        (
            "direct_contact_action", "add_contact", "modify_contact",
            "remove_contact", "send_message",
        ),
        ("add_contact", "modify_contact", "remove_contact", "send_message_with_phone_number"),
        ("direct_contact_action",)),
    "prepare_safe_action_or_abstain": _family(
        ("safe_abstain", "contact_lookup", "side_effect_guard"),
        (
            "search_contacts", "remove_contact", "modify_contact",
            "send_message_with_phone_number", "search_reminder", "search_messages",
            "get_current_timestamp",
        ),
        ("insufficient_information", "safe_abstain_needed")),
    "extract_service_answer_field": _family(
        (
            "service_answer_extraction", "convert_currency", "find_phone_number",
            "find_distance", "weather_lookup",
        ),
        (
            "search_location_around_lat_lon", "search_lat_lon",
            "search_weather_around_lat_lon", "calculate_lat_lon_distance",
            "convert_currency",
        ),
        ("service_answer_extraction",)),
    "extract_address_result": _family(
        ("service_answer_extraction", "find_address"),
        ("search_lat_lon", "search_location_around_lat_lon"), ("service_answer_extraction",)),
    "extract_converted_amount_result": _family(
        ("service_answer_extraction", "convert_currency"),
        ("convert_currency",), ("service_answer_extraction",)),
    "extract_phone_number_result": _family(
        ("service_answer_extraction", "find_phone_number"),
        ("search_location_around_lat_lon",), ("service_answer_extraction",)),
    "extract_distance_result": _family(
        ("service_answer_extraction", "find_distance"),
        ("calculate_lat_lon_distance",), ("service_answer_extraction",)),
    "extract_temperature_result": _family(
        ("service_answer_extraction", "weather_lookup", "temperature_lookup"),
        ("search_weather_around_lat_lon",), ("service_answer_extraction",)),
    "extract_stock_symbol": _family(None, ("search_stock",), ("stock_lookup",)),
    "next_service_tool_call": _family(None, None, ("state_precondition_possible",)),
    "prepare_add_contact_args": _family(None, None, ("add_contact",)),
})
# fmt: on


_TIMESTAMP_ORIGINAL_CALL_TOOLS = (
    "relative_day_time_to_timestamp",
    "next_weekday_time_to_timestamp",
)

# Runtime signals intentionally use their historical insertion order, which differs
# from generation order. This compact order table contains no policy values.
_VISIBLE_CONTEXT_SIGNAL_ORDER = (
    "prepare_safe_action_or_abstain",
    "plan_device_status_lookup",
    "plan_device_state_action_sequence_v3",
    "plan_device_state_action_sequence_location_recovery",
    "next_service_tool_call",
    "prepare_reminder_creation_args",
    "relative_day_time_to_timestamp",
    "next_weekday_time_to_timestamp",
    "prepare_location_search_args",
    "prepare_specific_location_search_args",
    "prepare_broad_location_search_args",
    "prepare_add_contact_args",
    "prepare_direct_contact_action_args",
    "plan_contact_lookup_query",
    "plan_send_message_contact_lookup",
    "plan_contact_relationship_batch_update",
    "select_message_counterparty_for_contact_update",
    "plan_message_counterparty_search",
    "resolve_search_window_or_bounds",
    "select_record_by_timestamp_extreme",
    "select_message_content_by_recency",
    "select_action_target_by_recency",
    "prepare_holiday_search_args",
    "days_between_timestamps",
    "extract_stock_symbol",
    "extract_service_answer_field",
    "extract_address_result",
    "extract_converted_amount_result",
    "extract_phone_number_result",
    "extract_distance_result",
    "extract_temperature_result",
)

_FamilyField = Literal[
    "applicable_task_families",
    "default_original_tool_calls",
    "visible_context_signals",
]


def _project(field: _FamilyField, order: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    projection: dict[str, tuple[str, ...]] = {}
    for tool_name in order:
        value = getattr(GENERATED_TOOL_FAMILY_DEFINITIONS[tool_name], field)
        if value is not None:
            projection[tool_name] = value
    return projection


def applicable_task_families_by_tool() -> dict[str, tuple[str, ...]]:
    return _project(
        "applicable_task_families", tuple(GENERATED_TOOL_FAMILY_DEFINITIONS)
    )


def default_original_tool_calls_by_tool() -> dict[str, tuple[str, ...]]:
    regular = tuple(
        name
        for name in GENERATED_TOOL_FAMILY_DEFINITIONS
        if name not in _TIMESTAMP_ORIGINAL_CALL_TOOLS
    )
    return _project(
        "default_original_tool_calls", regular + _TIMESTAMP_ORIGINAL_CALL_TOOLS
    )


def visible_context_signals_by_tool() -> dict[str, tuple[str, ...]]:
    return _project("visible_context_signals", _VISIBLE_CONTEXT_SIGNAL_ORDER)


def generated_tool_applicable_task_families(tool_name: str) -> tuple[str, ...]:
    value = GENERATED_TOOL_FAMILY_DEFINITIONS[tool_name].applicable_task_families
    if value is None:
        raise KeyError(f"{tool_name!r} has no applicable task families")
    return value


SETTING_SETTER_TOOL_NAME_ORDER = (
    "set_cellular_service_status",
    "set_location_service_status",
    "set_low_battery_mode_status",
    "set_wifi_status",
)

LOCATION_SEARCH_ARGUMENT_TOOL_NAME_ORDER = (
    "prepare_broad_location_search_args",
    "prepare_specific_location_search_args",
    "prepare_location_search_args",
)

VISIBLE_LAT_LON_REQUEST_RE = re.compile(
    r"\b(?:lat(?:itude)?|lattitude)\b[^a-z0-9+-]+[-+]?\d+(?:\.\d+)?"
    r".{0,80}\b(?:lon(?:gitude)?|lng)\b[^a-z0-9+-]+[-+]?\d+(?:\.\d+)?|"
    r"\b(?:lon(?:gitude)?|lng)\b[^a-z0-9+-]+[-+]?\d+(?:\.\d+)?"
    r".{0,80}\b(?:lat(?:itude)?|lattitude)\b[^a-z0-9+-]+[-+]?\d+(?:\.\d+)?",
    re.IGNORECASE,
)
