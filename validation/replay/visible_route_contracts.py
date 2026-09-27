"""Black-box contract for the visible classifier's ordered route dispatcher.

This validation-only corpus supplies already-classified visible task contexts at
the public ``classify_visible_task_observations`` boundary.  It intentionally
does not inspect a route table or depend on the dispatcher's source layout.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _classifier_contract_helpers() -> Any:
    """Load the sibling typed-digest helpers under isolated replay execution."""

    module_name = "_sage_replay_classifier_contracts"
    module = sys.modules.get(module_name)
    if module is not None:
        return module
    module_path = Path(__file__).with_name("classifier_contracts.py")
    module_spec = importlib.util.spec_from_file_location(module_name, module_path)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"Could not load classifier replay helpers: {module_path}")
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_name] = module
    module_spec.loader.exec_module(module)
    return module


_HELPERS = _classifier_contract_helpers()
_digest = _HELPERS._digest
_mutable_ids = _HELPERS._mutable_ids


@dataclass(frozen=True)
class _RouteCase:
    route_site: int
    case_id: str
    scenario_name: str
    request: str
    signals: tuple[str, ...]
    available_tools: tuple[str, ...]
    primary_family_key: str
    target_emission_index: int
    target_canonical_key: str
    target_task_family_key: str
    target_reason: str


@dataclass(frozen=True)
class _LayeredCase:
    case_id: str
    scenario_name: str
    request: str
    signals: tuple[str, ...]
    available_tools: tuple[str, ...]
    primary_family_key: str


def _case(
    route_site: int,
    case_id: str,
    signals: tuple[str, ...],
    target_emission_index: int,
    target_canonical_key: str,
    target_task_family_key: str,
    target_reason: str,
    *,
    request: str | None = None,
    available_tools: tuple[str, ...] = ("fixture_native_tool",),
    primary_family_key: str | None = None,
    scenario_name: str | None = None,
) -> _RouteCase:
    return _RouteCase(
        route_site=route_site,
        case_id=case_id,
        scenario_name=scenario_name
        or f"visible_route_trace:{route_site:02d}:{case_id}",
        request=request or f"Visible route request for {case_id}.",
        signals=signals,
        available_tools=available_tools,
        primary_family_key=primary_family_key or target_task_family_key,
        target_emission_index=target_emission_index,
        target_canonical_key=target_canonical_key,
        target_task_family_key=target_task_family_key,
        target_reason=f"visible_task_context:{target_reason}",
    )


_ALL_ROUTE_SIGNALS = (
    "insufficient_information",
    "safe_abstain_needed",
    "device_status_read",
    "device_state_action",
    "state_precondition_possible",
    "reminder_create",
    "reminder_modify",
    "relative_time",
    "weekday_time",
    "location_phrase",
    "add_contact",
    "contact_update_by_id",
    "direct_contact_action",
    "contact_lookup",
    "named_message_recipient",
    "relationship_batch_update",
    "message_counterparty_update",
    "message_counterparty_lookup",
    "recency_search",
    "upcoming_reminder_search",
    "message_recency_search",
    "past_reminder_recency_search",
    "message_recency",
    "message_search_followup_possible",
    "recency_action",
    "external_lookup",
    "holiday",
    "calendar_distance",
    "stock_lookup",
    "service_answer_extraction",
    "currency_lookup",
)


_PRIMARY_CASES: tuple[_RouteCase, ...] = (
    _case(
        1,
        "terminal_insufficient_information",
        _ALL_ROUTE_SIGNALS,
        0,
        "validation:prepare_safe_action_or_abstain",
        "safe_abstain",
        "insufficient_information_guard",
        request="Terminal visible insufficient-information request.",
    ),
    _case(
        2,
        "device_status_read",
        ("device_status_read",),
        0,
        "derived_value:plan_device_status_lookup",
        "device_status_read",
        "read_only_device_status",
    ),
    _case(
        3,
        "single_device_state_action",
        ("device_state_action",),
        0,
        "state_precondition:apply_single_device_state_action",
        "device_state_action",
        "visible_single_device_state_action",
    ),
    _case(
        4,
        "device_precondition_plan",
        ("state_precondition_possible",),
        0,
        "state_precondition:plan_device_state_action_sequence",
        "device_state_action",
        "visible_device_or_precondition_action",
    ),
    _case(
        5,
        "reminder_creation_arguments",
        ("reminder_create", "relative_time"),
        0,
        "composite:prepare_reminder_creation_args",
        "reminder_create",
        "visible_reminder_creation",
    ),
    _case(
        6,
        "create_relative_time",
        ("reminder_create", "relative_time"),
        1,
        "canonicalizer:relative_day_time_timestamp",
        "relative_time",
        "visible_relative_time",
    ),
    _case(
        7,
        "create_weekday_time",
        ("reminder_create", "weekday_time"),
        0,
        "canonicalizer:next_weekday_time_to_timestamp",
        "weekday_time",
        "visible_weekday_time",
    ),
    _case(
        8,
        "create_broad_location",
        ("reminder_create", "location_phrase"),
        1,
        "composite:prepare_broad_location_search_args",
        "location_phrase",
        "visible_broad_location_phrase",
        request="Remind me to buy tea near Boston.",
    ),
    _case(
        9,
        "create_specific_location",
        ("reminder_create", "location_phrase"),
        1,
        "composite:prepare_specific_location_search_args",
        "location_phrase",
        "visible_location_phrase",
        request="Remind me to buy tea at 123 Main Street.",
    ),
    _case(
        10,
        "modify_relative_time",
        ("reminder_modify", "relative_time"),
        0,
        "canonicalizer:relative_day_time_timestamp",
        "relative_time",
        "visible_relative_time_for_reminder_update",
    ),
    _case(
        11,
        "modify_weekday_time",
        ("reminder_modify", "weekday_time"),
        0,
        "canonicalizer:next_weekday_time_to_timestamp",
        "weekday_time",
        "visible_weekday_time_for_reminder_update",
    ),
    _case(
        12,
        "add_contact",
        ("add_contact",),
        0,
        "composite:prepare_add_contact_args",
        "add_contact",
        "visible_add_contact_request",
    ),
    _case(
        13,
        "contact_update_by_id",
        ("contact_update_by_id",),
        0,
        "composite:plan_contact_update_from_id",
        "contact_update_by_id",
        "visible_contact_update_by_id",
    ),
    _case(
        14,
        "direct_contact_action",
        ("direct_contact_action",),
        0,
        "composite:prepare_direct_contact_action_args",
        "direct_contact_action",
        "visible_scalar_contact_or_message_action",
    ),
    _case(
        15,
        "contact_lookup",
        ("contact_lookup",),
        0,
        "composite:plan_contact_lookup_query",
        "contact_lookup",
        "visible_contact_lookup_constraint",
    ),
    _case(
        16,
        "named_message_recipient",
        ("named_message_recipient",),
        0,
        "composite:plan_send_message_contact_lookup",
        "named_message_recipient",
        "visible_named_message_recipient",
    ),
    _case(
        17,
        "relationship_batch_update",
        ("relationship_batch_update",),
        0,
        "composite:plan_contact_relationship_batch_update",
        "relationship_batch_update",
        "visible_relationship_batch_update",
    ),
    _case(
        18,
        "counterparty_update_search_plan",
        ("message_counterparty_update",),
        0,
        "composite:plan_message_counterparty_search",
        "message_counterparty_update",
        "visible_message_counterparty_update_search_plan",
    ),
    _case(
        19,
        "counterparty_update_target",
        ("message_counterparty_update",),
        1,
        "composite:select_message_counterparty_for_contact_update",
        "message_counterparty_update",
        "visible_message_counterparty_update",
    ),
    _case(
        20,
        "counterparty_lookup_duplicate_route",
        (
            "has_phone_number",
            "contact",
            "modify_contact",
            "message",
            "message_counterparty_lookup",
            "message_counterparty_update",
            "recency_search",
            "message_recency_search",
        ),
        2,
        "composite:plan_message_counterparty_search",
        "message_counterparty_lookup",
        "visible_message_counterparty_lookup",
        scenario_name="modify_contact_with_message_recency_alt",
        request="Find whoever I contacted last, change his cell to +10293847563.",
        available_tools=(
            "end_conversation",
            "get_current_timestamp",
            "modify_contact",
            "search_contacts",
            "search_messages",
        ),
        primary_family_key="message_counterparty_lookup",
    ),
    _case(
        21,
        "upcoming_reminder_search",
        ("recency_search", "upcoming_reminder_search"),
        0,
        "derived_value:prepare_upcoming_reminder_search_args",
        "upcoming_reminder_search",
        "visible_upcoming_reminder_search",
    ),
    _case(
        22,
        "message_recency_search",
        ("recency_search", "message_recency_search"),
        0,
        "derived_value:prepare_message_recency_search_args",
        "message_recency_search",
        "visible_message_recency_search",
    ),
    _case(
        23,
        "past_reminder_recency_search",
        ("recency_search", "past_reminder_recency_search"),
        0,
        "derived_value:prepare_past_reminder_recency_search_args",
        "past_reminder_recency_search",
        "visible_past_reminder_recency_search",
    ),
    _case(
        24,
        "generic_recency_bounds",
        ("recency_search",),
        0,
        "derived_value:resolve_search_window_or_bounds",
        "recency_search",
        "visible_recency_search",
    ),
    _case(
        25,
        "latest_record_selection",
        ("recency_search",),
        1,
        "search_filter:select_record_by_timestamp_extreme",
        "recency_search",
        "visible_recency_selection",
    ),
    _case(
        26,
        "nested_message_recency_answer",
        ("recency_search", "message_recency_search", "message_recency"),
        2,
        "search_filter:select_message_content_by_recency",
        "message_recency",
        "visible_message_recency_answer",
    ),
    _case(
        27,
        "standalone_message_recency_answer",
        ("message_recency",),
        0,
        "search_filter:select_message_content_by_recency",
        "message_recency",
        "visible_message_recency_answer",
    ),
    _case(
        28,
        "recency_action_target",
        ("recency_action",),
        0,
        "search_filter:select_action_target_by_recency",
        "recency_action",
        "visible_recency_side_effect_target",
    ),
    _case(
        29,
        "external_broad_location",
        ("location_phrase", "external_lookup"),
        0,
        "composite:prepare_broad_location_search_args",
        "location_phrase",
        "visible_external_broad_location_phrase",
        request="Find a pharmacy near Boston.",
    ),
    _case(
        30,
        "external_specific_location",
        ("location_phrase", "external_lookup"),
        0,
        "composite:prepare_specific_location_search_args",
        "location_phrase",
        "visible_external_location_phrase",
        request="Find a pharmacy near 123 Main Street.",
    ),
    _case(
        31,
        "holiday_lookup",
        ("holiday",),
        0,
        "composite:prepare_holiday_search_args",
        "holiday_lookup",
        "visible_holiday_lookup",
    ),
    _case(
        32,
        "calendar_distance",
        ("holiday", "calendar_distance"),
        0,
        "derived_value:days_between_timestamps",
        "calendar_distance",
        "visible_calendar_distance",
    ),
    _case(
        33,
        "stock_lookup",
        ("stock_lookup",),
        0,
        "derived_value:extract_stock_symbol",
        "stock_lookup",
        "visible_stock_lookup",
    ),
    _case(
        34,
        "reverse_geocode_answer",
        ("service_answer_extraction",),
        0,
        "derived_value:extract_address_result",
        "service_answer_extraction",
        "visible_address_service_answer",
        request=("What is the address at latitude 37.7749 longitude -122.4194?"),
    ),
    _case(
        35,
        "currency_answer",
        ("service_answer_extraction", "currency_lookup"),
        0,
        "derived_value:extract_converted_amount_result",
        "service_answer_extraction",
        "visible_currency_service_answer",
        request="Convert 10 USD to EUR.",
    ),
    _case(
        36,
        "phone_answer",
        ("service_answer_extraction",),
        0,
        "derived_value:extract_phone_number_result",
        "service_answer_extraction",
        "visible_phone_service_answer",
        request="What is the phone number of Acme?",
    ),
    _case(
        37,
        "distance_answer",
        ("service_answer_extraction",),
        0,
        "derived_value:extract_distance_result",
        "service_answer_extraction",
        "visible_distance_service_answer",
        request="How far is Acme from Boston?",
    ),
    _case(
        38,
        "temperature_answer",
        ("service_answer_extraction",),
        0,
        "derived_value:extract_temperature_result",
        "service_answer_extraction",
        "visible_temperature_service_answer",
        request="What is the temperature in Boston?",
    ),
    _case(
        39,
        "generic_service_answer",
        ("service_answer_extraction",),
        0,
        "derived_value:extract_service_answer_field",
        "service_answer_extraction",
        "visible_service_answer",
        request="Return the requested service result.",
    ),
)


_NONTERMINAL_COLLISION = _case(
    0,
    "nonterminal_safe_abstain_global_order",
    (
        "safe_abstain_needed",
        "device_status_read",
        "state_precondition_possible",
        "reminder_create",
        "relative_time",
        "location_phrase",
        "contact_lookup",
        "recency_search",
        "message_recency_search",
        "message_recency",
        "recency_action",
        "external_lookup",
        "holiday",
        "stock_lookup",
        "service_answer_extraction",
    ),
    0,
    "validation:prepare_safe_action_or_abstain",
    "safe_abstain",
    "insufficient_information_guard",
    request="Find the temperature near Boston tomorrow.",
    primary_family_key="recency_action",
)


_LAYERED_AVAILABLE_TOOLS = (
    "end_conversation",
    "get_current_timestamp",
    "get_wifi_status",
    "set_wifi_status",
    "add_reminder",
    "modify_reminder",
    "add_contact",
    "modify_contact",
    "search_contacts",
    "search_messages",
    "search_location_around_lat_lon",
    "search_lat_lon",
    "search_holiday",
    "search_stock",
    "convert_currency",
    "calculate_lat_lon_distance",
    "search_weather_around_lat_lon",
)

_LAYERED_BACKBONE = (
    "safe_abstain_needed",
    "device_status_read",
    "device_state_action",
    "state_precondition_possible",
    "reminder_create",
    "reminder_modify",
    "add_contact",
    "contact_update_by_id",
    "direct_contact_action",
    "contact_lookup",
    "named_message_recipient",
    "relationship_batch_update",
    "message_counterparty_update",
    "message_counterparty_lookup",
    "recency_action",
    "external_lookup",
    "holiday",
    "stock_lookup",
    "service_answer_extraction",
)


def _layered_case(
    case_id: str,
    signals: tuple[str, ...],
    request: str,
) -> _LayeredCase:
    return _LayeredCase(
        case_id=case_id,
        scenario_name=f"visible_route_layered:{case_id}",
        request=request,
        signals=signals,
        available_tools=_LAYERED_AVAILABLE_TOOLS,
        primary_family_key="relationship_batch_update",
    )


_LAYERED_CASES: tuple[_LayeredCase, ...] = (
    _layered_case(
        "A_address_weekday_upcoming",
        (
            *_LAYERED_BACKBONE,
            "relative_time",
            "weekday_time",
            "location_phrase",
            "recency_search",
            "upcoming_reminder_search",
            "message_recency_search",
            "past_reminder_recency_search",
            "calendar_distance",
            "currency_lookup",
        ),
        "What is the address at latitude 37.7749 longitude -122.4194 next "
        "Monday? Also convert currency, find the phone number and distance, "
        "and report the weather at 123 Main Street.",
    ),
    _layered_case(
        "B_currency_relative_message",
        (
            *_LAYERED_BACKBONE,
            "relative_time",
            "location_phrase",
            "recency_search",
            "message_recency_search",
            "past_reminder_recency_search",
            "currency_lookup",
        ),
        "Tomorrow near Boston, convert currency and report the phone number, "
        "distance, and temperature.",
    ),
    _layered_case(
        "C_phone_weekday_past",
        (
            *_LAYERED_BACKBONE,
            "weekday_time",
            "location_phrase",
            "recency_search",
            "past_reminder_recency_search",
            "calendar_distance",
        ),
        "On Monday, find the phone number, distance, and temperature at "
        "123 Main Street.",
    ),
    _layered_case(
        "D_distance_relative_generic_recency",
        (
            *_LAYERED_BACKBONE,
            "relative_time",
            "location_phrase",
            "recency_search",
        ),
        "Tomorrow near Boston, how far away is the venue and what is its temperature?",
    ),
    _layered_case(
        "E_temperature_standalone_message",
        (
            *_LAYERED_BACKBONE,
            "location_phrase",
            "message_search_followup_possible",
        ),
        "Find the temperature at 123 Main Street.",
    ),
    _layered_case(
        "F_generic_device_only_reminder_gap",
        (
            "safe_abstain_needed",
            "device_status_read",
            "device_state_action",
            "reminder_create",
            "reminder_modify",
            "add_contact",
            "contact_update_by_id",
            "direct_contact_action",
            "contact_lookup",
            "named_message_recipient",
            "relationship_batch_update",
            "message_counterparty_update",
            "message_counterparty_lookup",
            "recency_action",
            "external_lookup",
            "holiday",
            "stock_lookup",
            "service_answer_extraction",
        ),
        "Return the requested service result and complete the visible actions.",
    ),
    _layered_case(
        "G_no_route_base_signals",
        (
            "contact",
            "message",
            "reminder",
            "external_lookup",
            "reminder_create",
            "reminder_modify",
        ),
        "A base-only visible task with no routed argument gap.",
    ),
)

_EXPECTED_LAYERED_START = (
    "validation:prepare_safe_action_or_abstain",
    "derived_value:plan_device_status_lookup",
    "state_precondition:apply_single_device_state_action",
    "state_precondition:plan_device_state_action_sequence",
    "composite:prepare_reminder_creation_args",
)
_EXPECTED_LAYERED_CONTACTS = (
    "composite:prepare_add_contact_args",
    "composite:plan_contact_update_from_id",
    "composite:prepare_direct_contact_action_args",
    "composite:plan_contact_lookup_query",
    "composite:plan_send_message_contact_lookup",
    "composite:plan_contact_relationship_batch_update",
    "composite:plan_message_counterparty_search",
    "composite:select_message_counterparty_for_contact_update",
    "composite:plan_message_counterparty_search",
)
_EXPECTED_LAYERED_KEY_SEQUENCES: dict[str, tuple[str, ...]] = {
    "A_address_weekday_upcoming": (
        *_EXPECTED_LAYERED_START,
        "canonicalizer:next_weekday_time_to_timestamp",
        "composite:prepare_specific_location_search_args",
        "canonicalizer:next_weekday_time_to_timestamp",
        *_EXPECTED_LAYERED_CONTACTS,
        "derived_value:prepare_upcoming_reminder_search_args",
        "search_filter:select_record_by_timestamp_extreme",
        "search_filter:select_action_target_by_recency",
        "composite:prepare_specific_location_search_args",
        "derived_value:days_between_timestamps",
        "derived_value:extract_stock_symbol",
        "derived_value:extract_address_result",
    ),
    "B_currency_relative_message": (
        *_EXPECTED_LAYERED_START,
        "canonicalizer:relative_day_time_timestamp",
        "composite:prepare_broad_location_search_args",
        "canonicalizer:relative_day_time_timestamp",
        *_EXPECTED_LAYERED_CONTACTS,
        "derived_value:prepare_message_recency_search_args",
        "search_filter:select_record_by_timestamp_extreme",
        "search_filter:select_action_target_by_recency",
        "composite:prepare_broad_location_search_args",
        "composite:prepare_holiday_search_args",
        "derived_value:extract_stock_symbol",
        "derived_value:extract_converted_amount_result",
    ),
    "C_phone_weekday_past": (
        *_EXPECTED_LAYERED_START,
        "canonicalizer:next_weekday_time_to_timestamp",
        "composite:prepare_specific_location_search_args",
        "canonicalizer:next_weekday_time_to_timestamp",
        *_EXPECTED_LAYERED_CONTACTS,
        "derived_value:prepare_past_reminder_recency_search_args",
        "search_filter:select_record_by_timestamp_extreme",
        "search_filter:select_action_target_by_recency",
        "composite:prepare_specific_location_search_args",
        "derived_value:days_between_timestamps",
        "derived_value:extract_stock_symbol",
        "derived_value:extract_phone_number_result",
    ),
    "D_distance_relative_generic_recency": (
        *_EXPECTED_LAYERED_START,
        "canonicalizer:relative_day_time_timestamp",
        "composite:prepare_broad_location_search_args",
        "canonicalizer:relative_day_time_timestamp",
        *_EXPECTED_LAYERED_CONTACTS,
        "derived_value:resolve_search_window_or_bounds",
        "search_filter:select_record_by_timestamp_extreme",
        "search_filter:select_action_target_by_recency",
        "composite:prepare_broad_location_search_args",
        "composite:prepare_holiday_search_args",
        "derived_value:extract_stock_symbol",
        "derived_value:extract_distance_result",
    ),
    "E_temperature_standalone_message": (
        *_EXPECTED_LAYERED_START,
        "composite:prepare_specific_location_search_args",
        *_EXPECTED_LAYERED_CONTACTS,
        "search_filter:select_message_content_by_recency",
        "search_filter:select_action_target_by_recency",
        "composite:prepare_specific_location_search_args",
        "composite:prepare_holiday_search_args",
        "derived_value:extract_stock_symbol",
        "derived_value:extract_temperature_result",
    ),
    "F_generic_device_only_reminder_gap": (
        *_EXPECTED_LAYERED_START,
        *_EXPECTED_LAYERED_CONTACTS,
        "search_filter:select_action_target_by_recency",
        "composite:prepare_holiday_search_args",
        "derived_value:extract_stock_symbol",
        "derived_value:extract_service_answer_field",
    ),
    "G_no_route_base_signals": (),
}


def _invoke_case(
    classifier: Any,
    case: _RouteCase | _LayeredCase,
) -> tuple[Any, ...]:
    context = classifier.VisibleTaskContext(
        user_request=case.request,
        available_tools=case.available_tools,
        signals=case.signals,
        primary_family_key=case.primary_family_key,
    )
    scenario = object()
    original = classifier.visible_task_context_from_scenario

    def replacement(_received: Any) -> Any:
        return context

    classifier.visible_task_context_from_scenario = replacement
    try:
        observations = classifier.classify_visible_task_observations(
            case.scenario_name,
            scenario,
        )
    finally:
        classifier.visible_task_context_from_scenario = original
    return observations


def _emitted_product(index: int, observation: Any) -> dict[str, Any]:
    return {
        "emission_index": index,
        "canonical_key": observation.canonical_key,
        "reason": observation.reason,
        "task_family_key": observation.task_family_key,
        "raw_observation_scenario_label": observation.scenario_name,
        "task_context_label": observation.task_context_label,
        "evidence_source": observation.evidence_source,
        "full_typed_dataclass_digest": _digest(observation),
    }


def _materialize_case(
    classifier: Any, case: _RouteCase
) -> tuple[dict[str, Any], tuple[Any, ...]]:
    observations = _invoke_case(classifier, case)
    products = [
        _emitted_product(index, observation)
        for index, observation in enumerate(observations)
    ]
    if not 0 <= case.target_emission_index < len(products):
        raise AssertionError(f"route target missing for {case.case_id}")
    target = products[case.target_emission_index]
    expected = {
        "canonical_key": case.target_canonical_key,
        "task_family_key": case.target_task_family_key,
        "reason": case.target_reason,
    }
    actual = {key: target[key] for key in expected}
    if actual != expected:
        raise AssertionError(
            f"route target changed for site {case.route_site} {case.case_id}: "
            f"expected={expected!r}, actual={actual!r}"
        )
    occurrence_index = sum(
        item["canonical_key"] == case.target_canonical_key
        for item in products[: case.target_emission_index]
    )
    return (
        {
            "route_site": case.route_site,
            "case_id": case.case_id,
            "scenario_name": case.scenario_name,
            "supplied_context": {
                "request": case.request,
                "signals": list(case.signals),
                "available_tools": list(case.available_tools),
                "primary_family_key": case.primary_family_key,
            },
            "target_emission_index": case.target_emission_index,
            "target_canonical_occurrence_index": occurrence_index,
            "target_signature": expected,
            "emitted_products": products,
        },
        observations,
    )


def _materialize_layered_case(
    classifier: Any,
    case: _LayeredCase,
) -> dict[str, Any]:
    observations = _invoke_case(classifier, case)
    return {
        "case_id": case.case_id,
        "scenario_name": case.scenario_name,
        "supplied_context": {
            "request": case.request,
            "signals": list(case.signals),
            "available_tools": list(case.available_tools),
            "primary_family_key": case.primary_family_key,
        },
        "emitted_products": [
            _emitted_product(index, observation)
            for index, observation in enumerate(observations)
        ],
    }


def _double_run_isolation(classifier: Any) -> dict[str, Any]:
    first = [_invoke_case(classifier, case) for case in _PRIMARY_CASES]
    second = [_invoke_case(classifier, case) for case in _PRIMARY_CASES]
    first_before = _digest(tuple(first))
    second_before = _digest(tuple(second))
    first_ids = set().union(*(_mutable_ids(item) for item in first))
    second_ids = set().union(*(_mutable_ids(item) for item in second))

    mutation_target = first[0][0].validation_examples[0]
    mutation_target.inputs["__visible_route_mutation_probe__"] = ["first-only"]
    if isinstance(mutation_target.expected, dict):
        mutation_target.expected["__visible_route_mutation_probe__"] = {"first": True}
    first_after = _digest(tuple(first))
    second_after = _digest(tuple(second))
    third = [_invoke_case(classifier, case) for case in _PRIMARY_CASES]
    third_after = _digest(tuple(third))
    third_ids = set().union(*(_mutable_ids(item) for item in third))
    return {
        "case_count_per_run": len(_PRIMARY_CASES),
        "first_before": first_before,
        "first_after": first_after,
        "second_before": second_before,
        "second_after": second_after,
        "third_after": third_after,
        "first_mutation_changed_first": first_before != first_after,
        "first_mutation_left_second_unchanged": second_before == second_after,
        "fresh_third_matches_unmutated_second": second_before == third_after,
        "first_second_shared_mutable_count": len(first_ids & second_ids),
        "second_third_shared_mutable_count": len(second_ids & third_ids),
    }


def build_visible_route_trace() -> dict[str, Any]:
    """Materialize all 39 ordered dispatch sites and focused edge contracts."""

    from sage_ts.adequacy import inadequacy_classifier as classifier

    materialized = [_materialize_case(classifier, case)[0] for case in _PRIMARY_CASES]
    collision, _ = _materialize_case(classifier, _NONTERMINAL_COLLISION)
    layered = [_materialize_layered_case(classifier, case) for case in _LAYERED_CASES]
    terminal = materialized[0]
    duplicate = materialized[19]
    body = {
        "schema_version": 1,
        "primary_cases": materialized,
        "focused_extras": {
            "terminal_insufficient_information": {
                "case_id": terminal["case_id"],
                "canonical_keys": [
                    item["canonical_key"] for item in terminal["emitted_products"]
                ],
            },
            "nonterminal_safe_abstain_global_order": collision,
            "layered_nonterminal_collisions": layered,
            "duplicate_modify_contact_route": {
                "case_id": duplicate["case_id"],
                "scenario_name": duplicate["scenario_name"],
                "canonical_keys": [
                    item["canonical_key"] for item in duplicate["emitted_products"]
                ],
                "target_emission_index": duplicate["target_emission_index"],
                "target_canonical_occurrence_index": duplicate[
                    "target_canonical_occurrence_index"
                ],
            },
        },
        "double_run_mutation_isolation": _double_run_isolation(classifier),
    }
    return {**body, "integrity": {"body": _digest(body)}}


EXPECTED_VISIBLE_ROUTE_TRACE: dict[str, Any] = {
    "body": {
        "byte_count": 385_520,
        "sha256": "646a0a18da4530dfbb21a502b4b90357455cd82088d71c18bfd400783799f4ea",
    },
    "schema_version": 1,
    "primary_case_count": 39,
    "route_sites": list(range(1, 40)),
    "case_ids": [case.case_id for case in _PRIMARY_CASES],
    "emitted_product_count": 57,
    "target_signatures": {
        "byte_count": 13_104,
        "sha256": "017dae61fe11b26c15b5c46f27aaa86450e3101bd3f2d9039f1f0f24dc46e2f9",
    },
    "focused_extras": {
        "byte_count": 261_956,
        "sha256": "26f870e0929379454c3943dcb2ae92150bb0cea0168b8af1ebaa26d9992edf75",
    },
    "layered_case_count": 7,
    "layered_emitted_product_count": 135,
    "layered_complete_sequences": {
        "byte_count": 10_085,
        "sha256": "27e4d5df624ec5d42023d7e0a829e62f2bb5b705f6ed8cf2c2930f4dad8e0e20",
    },
    "double_run_mutation_isolation": {
        "byte_count": 1_845,
        "sha256": "61a9adab4b743648ab8cb645335e40ae6b10a2d1ab51d09d02820d140d366047",
    },
}


def _contract_projection(contract: dict[str, Any]) -> dict[str, Any]:
    cases = contract["primary_cases"]
    layered = contract["focused_extras"]["layered_nonterminal_collisions"]
    return {
        "body": contract["integrity"]["body"],
        "schema_version": contract["schema_version"],
        "primary_case_count": len(cases),
        "route_sites": [item["route_site"] for item in cases],
        "case_ids": [item["case_id"] for item in cases],
        "emitted_product_count": sum(len(item["emitted_products"]) for item in cases),
        "target_signatures": _digest([item["target_signature"] for item in cases]),
        "focused_extras": _digest(contract["focused_extras"]),
        "layered_case_count": len(layered),
        "layered_emitted_product_count": sum(
            len(item["emitted_products"]) for item in layered
        ),
        "layered_complete_sequences": _digest(
            [
                (
                    item["case_id"],
                    tuple(
                        product["canonical_key"] for product in item["emitted_products"]
                    ),
                )
                for item in layered
            ]
        ),
        "double_run_mutation_isolation": _digest(
            contract["double_run_mutation_isolation"]
        ),
    }


def verify_visible_route_trace(contract: dict[str, Any]) -> None:
    body = {key: value for key, value in contract.items() if key != "integrity"}
    if contract.get("integrity", {}).get("body") != _digest(body):
        raise ValueError("visible-route trace body digest does not match its contents")
    actual = _contract_projection(contract)
    if not EXPECTED_VISIBLE_ROUTE_TRACE:
        raise ValueError("visible-route trace expected contract has not been frozen")
    if actual != EXPECTED_VISIBLE_ROUTE_TRACE:
        raise ValueError(
            "visible-route trace differs from its frozen reference contract: "
            f"expected={EXPECTED_VISIBLE_ROUTE_TRACE!r}, actual={actual!r}"
        )

    cases = contract["primary_cases"]
    if [item["route_site"] for item in cases] != list(range(1, 40)):
        raise ValueError("visible-route trace does not cover route sites 1 through 39")
    isolation = contract["double_run_mutation_isolation"]
    if not (
        isolation["case_count_per_run"] == 39
        and isolation["first_mutation_changed_first"]
        and isolation["first_mutation_left_second_unchanged"]
        and isolation["fresh_third_matches_unmutated_second"]
        and isolation["first_second_shared_mutable_count"] == 0
        and isolation["second_third_shared_mutable_count"] == 0
    ):
        raise ValueError(
            "visible-route dispatcher reuses mutable products across calls"
        )
    terminal = contract["focused_extras"]["terminal_insufficient_information"]
    if terminal["canonical_keys"] != ["validation:prepare_safe_action_or_abstain"]:
        raise ValueError("terminal insufficient-information route is not safe-only")
    collision = contract["focused_extras"]["nonterminal_safe_abstain_global_order"][
        "emitted_products"
    ]
    if (
        not collision
        or collision[0]["canonical_key"]
        != ("validation:prepare_safe_action_or_abstain")
        or len(collision) == 1
    ):
        raise ValueError("nonterminal safe-abstain route no longer continues in order")
    layered = contract["focused_extras"]["layered_nonterminal_collisions"]
    actual_layered_sequences = {
        item["case_id"]: tuple(
            product["canonical_key"] for product in item["emitted_products"]
        )
        for item in layered
    }
    if actual_layered_sequences != _EXPECTED_LAYERED_KEY_SEQUENCES:
        raise ValueError("layered visible-route order or selector precedence changed")
    duplicate = contract["focused_extras"]["duplicate_modify_contact_route"]
    if duplicate["canonical_keys"] != [
        "composite:plan_message_counterparty_search",
        "composite:select_message_counterparty_for_contact_update",
        "composite:plan_message_counterparty_search",
        "derived_value:prepare_message_recency_search_args",
        "search_filter:select_record_by_timestamp_extreme",
    ] or (
        duplicate["target_emission_index"],
        duplicate["target_canonical_occurrence_index"],
    ) != (2, 1):
        raise ValueError("deliberate duplicate visible route changed")


def probe_visible_route_trace(_root: Any) -> dict[str, Any]:
    contract = build_visible_route_trace()
    verify_visible_route_trace(contract)
    return contract


def _rehash(contract: dict[str, Any]) -> None:
    body = {key: value for key, value in contract.items() if key != "integrity"}
    contract["integrity"]["body"] = _digest(body)


def _tamper_self_test(contract: dict[str, Any]) -> None:
    tampered = copy.deepcopy(contract)
    tampered["primary_cases"][0]["case_id"] = "tampered"
    try:
        verify_visible_route_trace(tampered)
    except ValueError:
        pass
    else:
        raise AssertionError("unhashed visible-route tamper was not rejected")

    for label, mutate in (
        (
            "reordered routes",
            lambda value: value["primary_cases"].__setitem__(
                slice(0, 2), list(reversed(value["primary_cases"][:2]))
            ),
        ),
        ("dropped route", lambda value: value["primary_cases"].pop(4)),
        (
            "device generation label",
            lambda value: value["primary_cases"][2]["emitted_products"][0].__setitem__(
                "raw_observation_scenario_label", "tampered-device-label"
            ),
        ),
        (
            "layered collision order",
            lambda value: value["focused_extras"]["layered_nonterminal_collisions"][0][
                "emitted_products"
            ].reverse(),
        ),
    ):
        forged = copy.deepcopy(contract)
        mutate(forged)
        _rehash(forged)
        try:
            verify_visible_route_trace(forged)
        except ValueError:
            pass
        else:
            raise AssertionError(f"rehashed {label} tamper was not rejected")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-contract", action="store_true")
    parser.add_argument("--tamper-self-test", action="store_true")
    args = parser.parse_args()
    contract = build_visible_route_trace()
    if args.print_contract:
        print(json.dumps(_contract_projection(contract), indent=2))
        return 0
    verify_visible_route_trace(contract)
    if args.tamper_self_test:
        _tamper_self_test(contract)
    print(
        json.dumps(
            {
                "status": "verified",
                "contract": _contract_projection(contract),
                "tamper_self_test": args.tamper_self_test,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
