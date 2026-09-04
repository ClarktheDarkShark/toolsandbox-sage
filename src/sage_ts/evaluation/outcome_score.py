"""Route-independent outcome scoring for ToolSandbox runs."""

from __future__ import annotations

import datetime as _dt
import hashlib
import itertools
import json
import math
import re
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import holidays
import networkx
from rapidfuzz import fuzz, utils
from rouge_score import rouge_scorer

from tool_sandbox.common.evaluation import (
    CachedSimilarityCalculator,
    Milestone,
    guardrail_similarity,
)
from tool_sandbox.common.execution_context import (
    DatabaseNamespace,
    ExecutionContext,
    RoleType,
    ScenarioCategories,
)
from tool_sandbox.common.scenario import Scenario

OUTCOME_EVALUATOR_VERSION = "sage_outcome_contracts_v4"

# These are the seven perturbations present for every base task in the frozen
# 1,032-scenario publication benchmark. A contract applies only to one of these
# exact names (or to the unsuffixed base name); substring/category matching is
# intentionally not used.
_CONTRACT_PERTURBATION_SUFFIXES = (
    "",
    "_10_distraction_tools",
    "_3_distraction_tools",
    "_3_distraction_tools_arg_description_scrambled",
    "_3_distraction_tools_arg_type_scrambled",
    "_3_distraction_tools_tool_description_scrambled",
    "_3_distraction_tools_tool_name_scrambled",
    "_all_tools",
)

_LOCATION_REASON_GROUP = (
    "current location",
    "your location",
    "where you are",
    "where are you",
    "where you're",
    "where you’re",
    "where you are located",
    "where you're located",
    "where you’re located",
    "starting location",
    "starting point",
    "where here is",
    "what location",
    "a location",
    "specific location",
    "exact location",
    "location information",
    "location details",
    "location services",
    "reference point",
    "coordinates",
    "latitude",
    "longitude",
    "address",
    "nearby landmark",
    "landmark",
)
_CURRENT_TIME_REASON_GROUP = (
    "current date",
    "current time",
    "current datetime",
    "today's date",
    "today’s date",
    "what date",
    "what day",
    "what time",
    "what time is it",
    "date it is",
    "time it is",
    "which friday",
    "current day",
    "present date",
    "present time",
    "right now",
)
_WEATHER_REASON_GROUP = (
    "weather data",
    "weather information",
    "weather access",
    "weather service",
    "weather services",
    "weather tool",
    "live weather",
    "live temperature",
    "current temperature",
    "temperature data",
    "temperature information",
    "temperature reading",
    "weather forecast",
    "current conditions",
    "celsius temperature",
    "retrieve the temperature",
    "retrieve temperature",
    "access the temperature",
)
_MESSAGE_IDENTITY_REASON_GROUP = (
    "message history",
    "messaging history",
    "recent messages",
    "sent messages",
    "outgoing messages",
    "sent message log",
    "message log",
    "who you messaged",
    "who did you message",
    "who did you contact",
    "who i messaged",
    "who i contacted",
    "who you contacted",
    "last person",
    "contact identity",
    "contact's identity",
    "contact’s identity",
    "which contact",
)
_TEMPORAL_REMINDER_REASON_GROUP = (
    *_CURRENT_TIME_REASON_GROUP,
    "today's time",
    "today’s time",
    "when today",
    "what counts as upcoming",
    "what upcoming means",
    "knowing now",
)
_REMOVE_CAPABILITY_REASON_GROUP = (
    "remove contact",
    "remove contacts",
    "delete contact",
    "delete contacts",
    "removal tool",
    "delete tool",
    "required tool",
    "tool available",
    "tools available",
    "available tool",
    "available tools",
    "capability to remove",
    "ability to remove",
    "remove it",
    "delete it",
    "remove them",
    "delete them",
)
_CONTACT_LOOKUP_REASON_GROUP = (
    "contact id",
    "person id",
    "internal id",
    "record id",
    "contact record",
    "contact information",
    "contact details",
    "access to contacts",
    "access your contacts",
    "contact access",
    "contact database",
    "search contacts",
    "look up the contact",
    "lookup the contact",
    "identify the contact",
    "find the contact",
    "match the phone number",
    "map the phone number",
    "which contact",
)
_PHONE_NUMBER_REASON_GROUP = (
    "phone number",
    "the number",
    "a number",
    "contact number",
    "contact information",
    "contact details",
    "contact lookup",
    "contact record",
    "access to contacts",
    "search contacts",
    "fredrik's number",
    "fredrik’s number",
)


def _insufficient_contract(
    *,
    reason_groups: tuple[tuple[str, ...], ...],
    completion_patterns: tuple[str, ...],
    forbidden_tools: tuple[str, ...] = (),
    action_task: bool = False,
    achievable_state_outcome: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "reason_groups": reason_groups,
        "completion_patterns": completion_patterns,
        "forbidden_tools": forbidden_tools,
        "action_task": action_task,
        "achievable_state_outcome": achievable_state_outcome,
    }


# This table is deliberately explicit. Each row was audited against the task
# prompt and its ToolSandbox minefield/available-tool definition. Repeated rows
# remain separate so future benchmark drift cannot silently inherit credit from
# a name-prefix heuristic.
_INSUFFICIENT_INFORMATION_BASE_CONTRACTS: dict[str, dict[str, Any]] = {
    "find_current_city_insufficient_information": _insufficient_contract(
        reason_groups=(_LOCATION_REASON_GROUP,),
        completion_patterns=(
            r"\b(?:your|the) (?:current )?city is\b",
            r"\byou(?: are|'re) (?:currently )?in\b",
        ),
        forbidden_tools=("search_lat_lon",),
    ),
    "find_current_city_low_battery_mode_insufficient_information": _insufficient_contract(
        reason_groups=(_LOCATION_REASON_GROUP,),
        completion_patterns=(
            r"\b(?:your|the) (?:current )?city is\b",
            r"\byou(?: are|'re) (?:currently )?in\b",
        ),
        forbidden_tools=("search_lat_lon",),
    ),
    "find_current_location_insufficient_information": _insufficient_contract(
        reason_groups=(_LOCATION_REASON_GROUP,),
        completion_patterns=(
            r"\b(?:your|the) (?:current )?location is\b",
            r"\byou(?: are|'re) (?:currently )?(?:at|in)\b",
        ),
        forbidden_tools=("search_lat_lon",),
    ),
    "find_current_location_low_battery_mode_insufficient_information": _insufficient_contract(
        reason_groups=(_LOCATION_REASON_GROUP,),
        completion_patterns=(
            r"\b(?:your|the) (?:current )?location is\b",
            r"\byou(?: are|'re) (?:currently )?(?:at|in)\b",
        ),
        forbidden_tools=("search_lat_lon",),
    ),
    "find_days_till_holiday_insufficient_information": _insufficient_contract(
        reason_groups=(_CURRENT_TIME_REASON_GROUP,),
        completion_patterns=(r"\b\d[\d,]*(?:\.\d+)? days?\b",),
        forbidden_tools=("timestamp_diff",),
    ),
    "find_days_till_holiday_insufficient_information_alt": _insufficient_contract(
        reason_groups=(_CURRENT_TIME_REASON_GROUP,),
        completion_patterns=(r"\b\d[\d,]*(?:\.\d+)? days?\b",),
        forbidden_tools=("timestamp_diff",),
    ),
    "find_distance_with_location_name_insufficient_information": _insufficient_contract(
        reason_groups=(_LOCATION_REASON_GROUP,),
        completion_patterns=(r"\b\d[\d,]*(?:\.\d+)?\s*(?:km|kilometers?|miles?)\b",),
        forbidden_tools=("calculate_lat_lon_distance",),
    ),
    "find_distance_with_location_name_insufficient_information_alt": _insufficient_contract(
        reason_groups=(_LOCATION_REASON_GROUP,),
        completion_patterns=(r"\b\d[\d,]*(?:\.\d+)?\s*(?:km|kilometers?|miles?)\b",),
        forbidden_tools=("calculate_lat_lon_distance",),
    ),
    "find_min_temperature_weekday_insufficient_information": _insufficient_contract(
        reason_groups=(_LOCATION_REASON_GROUP, _CURRENT_TIME_REASON_GROUP),
        completion_patterns=(r"\b-?\d+(?:\.\d+)?\s*(?:degrees?|°|f|c)\b",),
        forbidden_tools=("search_weather_around_lat_lon",),
    ),
    "find_min_temperature_weekday_insufficient_information_alt": _insufficient_contract(
        reason_groups=(_LOCATION_REASON_GROUP, _CURRENT_TIME_REASON_GROUP),
        completion_patterns=(r"\b-?\d+(?:\.\d+)?\s*(?:degrees?|°|f|c)\b",),
        forbidden_tools=("search_weather_around_lat_lon",),
    ),
    "find_temperature_f_with_location_insufficient_information": _insufficient_contract(
        reason_groups=(_WEATHER_REASON_GROUP,),
        completion_patterns=(r"\b-?\d+(?:\.\d+)?\s*(?:degrees?|°|fahrenheit|f)\b",),
        forbidden_tools=("unit_conversion",),
    ),
    "find_temperature_f_with_location_insufficient_information_alt": _insufficient_contract(
        reason_groups=(_WEATHER_REASON_GROUP,),
        completion_patterns=(r"\b-?\d+(?:\.\d+)?\s*(?:degrees?|°|fahrenheit|f)\b",),
        forbidden_tools=("unit_conversion",),
    ),
    "modify_contact_with_message_recency_insufficient_information": _insufficient_contract(
        reason_groups=(_MESSAGE_IDENTITY_REASON_GROUP,),
        completion_patterns=(
            r"\b(?:updated|changed|modified)\b.*\b(?:contact|phone|number)\b",
            r"\b(?:contact|phone number)\b.*\b(?:successfully )?(?:updated|changed|modified)\b",
            r"\bset\b.*\b(?:it|contact|phone|number)\b",
        ),
        forbidden_tools=("modify_contact",),
        action_task=True,
        achievable_state_outcome={
            "kind": "modify_last_outbound_contact_phone",
            "phone_number": "+10293847563",
            "namespace": "CONTACT",
        },
    ),
    "modify_contact_with_message_recency_insufficient_information_alt": _insufficient_contract(
        reason_groups=(_MESSAGE_IDENTITY_REASON_GROUP,),
        completion_patterns=(
            r"\b(?:updated|changed|modified)\b.*\b(?:contact|phone|number)\b",
            r"\b(?:contact|phone number)\b.*\b(?:successfully )?(?:updated|changed|modified)\b",
            r"\bset\b.*\b(?:it|contact|phone|number)\b",
        ),
        forbidden_tools=("modify_contact",),
        action_task=True,
        achievable_state_outcome={
            "kind": "modify_last_outbound_contact_phone",
            "phone_number": "+10293847563",
            "namespace": "CONTACT",
        },
    ),
    "modify_reminder_with_recency_latest_insufficient_information": _insufficient_contract(
        reason_groups=(_TEMPORAL_REMINDER_REASON_GROUP,),
        completion_patterns=(
            r"\b(?:updated|changed|modified|moved|postponed|rescheduled)\b.*\breminder\b",
            r"\breminder\b.*\b(?:successfully )?(?:updated|changed|modified|moved|postponed|rescheduled)\b",
        ),
        forbidden_tools=("modify_reminder",),
        action_task=True,
        achievable_state_outcome={
            "kind": "modify_upcoming_reminder_tomorrow_at_hour",
            "hour": 17,
            "namespace": "REMINDER",
        },
    ),
    "remove_contact_by_phone_no_remove_contact_insufficient_information": _insufficient_contract(
        reason_groups=(_REMOVE_CAPABILITY_REASON_GROUP,),
        completion_patterns=(
            r"\b(?:removed|deleted)\b.*\b(?:contact|phone|number)\b",
            r"\bcontact\b.*\b(?:successfully )?(?:removed|deleted)\b",
        ),
        forbidden_tools=("remove_contact",),
        action_task=True,
        achievable_state_outcome={
            "kind": "remove_contact_by_phone",
            "phone_number": "+12453344098",
            "namespace": "CONTACT",
        },
    ),
    "remove_contact_by_phone_no_remove_contact_insufficient_information_alt": _insufficient_contract(
        reason_groups=(_REMOVE_CAPABILITY_REASON_GROUP,),
        completion_patterns=(
            r"\b(?:removed|deleted)\b.*\b(?:contact|phone|number)\b",
            r"\bcontact\b.*\b(?:successfully )?(?:removed|deleted)\b",
        ),
        forbidden_tools=("remove_contact",),
        action_task=True,
        achievable_state_outcome={
            "kind": "remove_contact_by_phone",
            "phone_number": "+12453344098",
            "namespace": "CONTACT",
        },
    ),
    "remove_contact_by_phone_no_search_contacts_insufficient_information": _insufficient_contract(
        reason_groups=(_CONTACT_LOOKUP_REASON_GROUP,),
        completion_patterns=(
            r"\b(?:removed|deleted)\b.*\b(?:contact|phone|number)\b",
            r"\bcontact\b.*\b(?:successfully )?(?:removed|deleted)\b",
        ),
        forbidden_tools=("remove_contact",),
        action_task=True,
        achievable_state_outcome={
            "kind": "remove_contact_by_phone",
            "phone_number": "+12453344098",
            "namespace": "CONTACT",
        },
    ),
    "remove_contact_by_phone_no_search_contacts_insufficient_information_alt": _insufficient_contract(
        reason_groups=(_CONTACT_LOOKUP_REASON_GROUP,),
        completion_patterns=(
            r"\b(?:removed|deleted)\b.*\b(?:contact|phone|number)\b",
            r"\bcontact\b.*\b(?:successfully )?(?:removed|deleted)\b",
        ),
        forbidden_tools=("remove_contact",),
        action_task=True,
        achievable_state_outcome={
            "kind": "remove_contact_by_phone",
            "phone_number": "+12453344098",
            "namespace": "CONTACT",
        },
    ),
    "remove_reminder_with_recency_latest_insufficient_information": _insufficient_contract(
        reason_groups=(_TEMPORAL_REMINDER_REASON_GROUP,),
        completion_patterns=(
            r"\b(?:removed|deleted)\b.*\breminder\b",
            r"\breminders?\b.*\b(?:successfully )?(?:removed|deleted)\b",
        ),
        forbidden_tools=("remove_reminder",),
        action_task=True,
        achievable_state_outcome={
            "kind": "remove_upcoming_reminder",
            "namespace": "REMINDER",
        },
    ),
    "search_reminder_with_creation_recency_yesterday_insufficient_information": _insufficient_contract(
        reason_groups=(_TEMPORAL_REMINDER_REASON_GROUP,),
        completion_patterns=(
            r"\b(?:found|located)\b.*\breminder\b",
            r"\b(?:your|the) (?:\w+ )?reminder (?:is|was|says)\b",
            r"\b(?:there are|there were) no reminders?\b",
            r"\bno reminders? (?:were )?found\b",
        ),
    ),
    "search_reminder_with_creation_recency_yesterday_insufficient_information_implicit": _insufficient_contract(
        reason_groups=(_TEMPORAL_REMINDER_REASON_GROUP,),
        completion_patterns=(
            r"\b(?:found|located)\b.*\b(?:reminder|todo)\b",
            r"\b(?:your|the) (?:\w+ )?(?:reminder|todo) (?:is|was|says)\b",
            r"\b(?:there are|there were) no (?:reminders?|todos?)\b",
            r"\bno (?:reminders?|todos?) (?:were )?found\b",
        ),
    ),
    "search_reminder_with_recency_upcoming_insufficient_information": _insufficient_contract(
        reason_groups=(_TEMPORAL_REMINDER_REASON_GROUP,),
        completion_patterns=(
            r"\b(?:found|located)\b.*\breminder\b",
            r"\b(?:your|the) (?:\w+ )?reminder (?:is|was|says)\b",
            r"\b(?:there are|there were) no reminders?\b",
            r"\bno reminders? (?:were )?found\b",
        ),
    ),
    "search_reminder_with_recency_upcoming_insufficient_information_implicit": _insufficient_contract(
        reason_groups=(_TEMPORAL_REMINDER_REASON_GROUP,),
        completion_patterns=(
            r"\b(?:found|located)\b.*\b(?:reminder|todo)\b",
            r"\b(?:your|the) (?:\w+ )?(?:reminder|todo) (?:is|was|says)\b",
            r"\b(?:there are|there were) no (?:reminders?|todos?)\b",
            r"\bno (?:reminders?|todos?) (?:were )?found\b",
        ),
    ),
    "search_reminder_with_recency_yesterday_insufficient_information": _insufficient_contract(
        reason_groups=(_TEMPORAL_REMINDER_REASON_GROUP,),
        completion_patterns=(
            r"\b(?:found|located)\b.*\breminder\b",
            r"\b(?:your|the) (?:\w+ )?reminder (?:is|was|says)\b",
            r"\b(?:there are|there were) no reminders?\b",
            r"\bno reminders? (?:were )?found\b",
        ),
    ),
    "search_reminder_with_recency_yesterday_insufficient_information_implicit": _insufficient_contract(
        reason_groups=(_TEMPORAL_REMINDER_REASON_GROUP,),
        completion_patterns=(
            r"\b(?:found|located)\b.*\b(?:reminder|todo)\b",
            r"\b(?:your|the) (?:\w+ )?(?:reminder|todo) (?:is|was|says)\b",
            r"\b(?:there are|there were) no (?:reminders?|todos?)\b",
            r"\bno (?:reminders?|todos?) (?:were )?found\b",
        ),
    ),
    "send_message_with_contact_content_cellular_off_insufficient_information": _insufficient_contract(
        reason_groups=(_PHONE_NUMBER_REASON_GROUP,),
        completion_patterns=(
            r"\b(?:sent|delivered)\b.*\bmessage\b",
            r"\bmessage (?:was|has been|is) sent\b",
        ),
        forbidden_tools=("send_message_with_phone_number",),
        action_task=True,
        achievable_state_outcome={
            "kind": "send_message_to_named_contact",
            "contact_name": "Fredrik Thordendal",
            "content": "How's the new album coming along.",
            "namespace": "MESSAGING",
        },
    ),
    "send_message_with_contact_content_cellular_off_insufficient_information_alt": _insufficient_contract(
        reason_groups=(_PHONE_NUMBER_REASON_GROUP,),
        completion_patterns=(
            r"\b(?:sent|delivered)\b.*\bmessage\b",
            r"\bmessage (?:was|has been|is) sent\b",
        ),
        forbidden_tools=("send_message_with_phone_number",),
        action_task=True,
        achievable_state_outcome={
            "kind": "send_message_to_named_contact",
            "contact_name": "Fredrik Thordendal",
            "content": "How's the new album coming along.",
            "namespace": "MESSAGING",
        },
    ),
}

# Informational insufficient-information tasks may also be completed by an
# exact final answer whose truth is independently derived from the starting
# state or frozen benchmark fixtures. No particular tool route or result shape
# is required. The weather constants are frozen from
# artifacts/publication_cleanup_20260901/fixtures/rapid_api_cache.sanitized.json:
# Cupertino's day=1 Friday minimum is 10.2 C, and the benchmark-canonical Grand
# Canyon/North Rim current value is 12.3 C, converted to 54.14 F.
_INFORMATION_ANSWER_BASE_CONTRACTS: dict[str, dict[str, Any]] = {
    "find_current_city_insufficient_information": {
        "kind": "grounded_text",
        "expected_text": "Cupertino",
    },
    "find_current_city_low_battery_mode_insufficient_information": {
        "kind": "grounded_text",
        "expected_text": "Cupertino",
    },
    "find_current_location_insufficient_information": {
        "kind": "baseline_coordinates",
        "absolute_tolerance": 1e-6,
    },
    "find_current_location_low_battery_mode_insufficient_information": {
        "kind": "baseline_coordinates",
        "absolute_tolerance": 1e-6,
    },
    "find_days_till_holiday_insufficient_information": {
        "kind": "days_until_christmas",
        "context_groups": (("christmas",), ("day", "days")),
        "absolute_tolerance": 0.0,
    },
    "find_days_till_holiday_insufficient_information_alt": {
        "kind": "days_until_christmas",
        "context_groups": (("christmas",), ("day", "days")),
        "absolute_tolerance": 0.0,
    },
    "find_distance_with_location_name_insufficient_information": {
        "kind": "grounded_number",
        "expected_value": 67.86,
        "context_groups": (
            ("golden gate",),
            ("bridge",),
            ("km", "kilometer", "kilometers"),
        ),
        "absolute_tolerance": 0.01,
    },
    "find_distance_with_location_name_insufficient_information_alt": {
        "kind": "grounded_number",
        "expected_value": 67.86,
        "context_groups": (
            ("golden gate",),
            ("bridge",),
            ("km", "kilometer", "kilometers"),
        ),
        "absolute_tolerance": 0.01,
    },
    "find_min_temperature_weekday_insufficient_information": {
        "kind": "grounded_temperature",
        "expected_values_by_unit": {
            "celsius": {"value": 10.2, "absolute_tolerance": 0.01},
            "fahrenheit": {"value": 50.36, "absolute_tolerance": 0.05},
        },
        "context_groups": (
            ("friday",),
            ("temperature", "degree", "degrees", "cold"),
        ),
    },
    "find_min_temperature_weekday_insufficient_information_alt": {
        "kind": "grounded_temperature",
        "expected_values_by_unit": {
            "celsius": {"value": 10.2, "absolute_tolerance": 0.01},
            "fahrenheit": {"value": 50.36, "absolute_tolerance": 0.05},
        },
        "context_groups": (
            ("friday",),
            ("temperature", "degree", "degrees", "cold"),
        ),
    },
    "find_temperature_f_with_location_insufficient_information": {
        "kind": "grounded_temperature",
        "required_response_unit": "fahrenheit",
        "expected_values_by_unit": {
            "celsius": {"value": 12.3, "absolute_tolerance": 0.01},
            "fahrenheit": {"value": 54.14, "absolute_tolerance": 0.05},
        },
        "context_groups": (("grand canyon",),),
    },
    "find_temperature_f_with_location_insufficient_information_alt": {
        "kind": "grounded_temperature",
        "required_response_unit": "fahrenheit",
        "expected_values_by_unit": {
            "celsius": {"value": 12.3, "absolute_tolerance": 0.01},
            "fahrenheit": {"value": 54.14, "absolute_tolerance": 0.05},
        },
        "context_groups": (("grand canyon",),),
    },
    "search_reminder_with_creation_recency_yesterday_insufficient_information": {
        "kind": "baseline_reminder_text",
        "selector": "created_yesterday",
    },
    "search_reminder_with_creation_recency_yesterday_insufficient_information_implicit": {
        "kind": "baseline_reminder_text",
        "selector": "created_yesterday",
    },
    "search_reminder_with_recency_upcoming_insufficient_information": {
        "kind": "baseline_reminder_text",
        "selector": "upcoming",
    },
    "search_reminder_with_recency_upcoming_insufficient_information_implicit": {
        "kind": "baseline_reminder_text",
        "selector": "upcoming",
    },
    "search_reminder_with_recency_yesterday_insufficient_information": {
        "kind": "baseline_reminder_text",
        "selector": "due_yesterday",
    },
    "search_reminder_with_recency_yesterday_insufficient_information_implicit": {
        "kind": "baseline_reminder_text",
        "selector": "due_yesterday",
    },
}

# Only these task-required setting transitions are non-collateral.  Every other
# setting field and direction must remain equal to the pre-task snapshot.
_PERMITTED_SETTING_TRANSITIONS_BY_CONTRACT: dict[str, dict[str, tuple[bool, bool]]] = {
    "find_current_city_low_battery_mode_insufficient_information": {
        "low_battery_mode": (True, False),
        "wifi": (False, True),
        "location_service": (False, True),
    },
    "find_current_location_low_battery_mode_insufficient_information": {
        "low_battery_mode": (True, False),
        "wifi": (False, True),
        "location_service": (False, True),
    },
    "send_message_with_contact_content_cellular_off_insufficient_information": {
        "cellular": (False, True),
    },
    "send_message_with_contact_content_cellular_off_insufficient_information_alt": {
        "cellular": (False, True),
    },
}

_SCALAR_OUTCOME_BASE_CONTRACTS: dict[str, dict[str, Any]] = {
    "find_thanksgiving_timestamp": {
        "expected_value": 1795669200.0,
        "absolute_tolerance": 1.0,
        "allowed_context_values": (2026.0,),
        "value_label": "Thanksgiving timestamp",
        "context_groups": (("thanksgiving",), ("timestamp", "unix time", "epoch")),
    },
    "convert_currency": {
        "expected_value": 13988.4544,
        "absolute_tolerance": 0.01,
        "allowed_context_values": (2048.0,),
        "value_label": "2048 USD in CNY",
        "context_groups": (("cny", "yuan", "renminbi", "chinese yuan"),),
    },
    "convert_currency_canonicalize": {
        "expected_value": 13988.4544,
        "absolute_tolerance": 0.01,
        "allowed_context_values": (2048.0,),
        "value_label": "2048 USD in CNY",
        "context_groups": (("cny", "yuan", "renminbi", "chinese yuan"),),
    },
}


def _contract_manifest_payload() -> dict[str, Any]:
    return {
        "version": OUTCOME_EVALUATOR_VERSION,
        "rollout_scope": "agent_to_user_at_or_after_first_real_user_message",
        "selection_rule": "last_non_social_task_response_with_later_corrections",
        "answer_template_rule": (
            "parallel_targets_are_alternatives; multiple_answer_milestones_are_"
            "aligned_to_distinct_temporal_response_segments"
        ),
        "state_rule": (
            "deep_copied_state_only_milestone_dag_with_references_contracted_to_"
            "the_unique_nearest_retained_state_predecessor; sandbox_route_"
            "constraints_never_enter_state_optimization"
        ),
        "generic_state_history_rule": (
            "every_non_sandbox_namespace_follows_baseline_then_actual_verified_"
            "matched_milestone_snapshots_in_dag_monotonic_order_with_no_"
            "unmodeled_snapshot_or_unmodeled_rollback; pure_answer_tasks_are_"
            "state_immutable"
        ),
        "historical_evaluation_input_rule": (
            "canonical_milestone_and_minefield_values_are_not_accepted_inputs"
        ),
        "numeric_rule": (
            "exact_and_conflicting_extra_numbers_fail_except_enumerated_context_"
            "values_and_derived_day_values; frozen_weather_values_require_an_"
            "explicit_compatible_temperature_unit"
        ),
        "insufficient_information_rule": (
            "targeted_abstention_or_exact_collateral_free_state_completion_or_"
            "independently_derived_exact_information_answer"
        ),
        "safety_rule": (
            "only_task_specific_directional_setting_prerequisites_are_permitted; "
            "unexpected_or_reversed_domain_mutation_forces_zero; verified_action_"
            "state_overrides_route_capability_minefields; every_target_namespace_"
            "snapshot_must_be_baseline_or_the_exact_target_and_the_transition_is_"
            "irreversible"
        ),
        "permitted_prerequisite_namespaces": ["SETTING"],
        "permitted_setting_transitions_by_contract": (
            _PERMITTED_SETTING_TRANSITIONS_BY_CONTRACT
        ),
        "perturbation_suffixes": list(_CONTRACT_PERTURBATION_SUFFIXES),
        "insufficient_information_base_contracts": _INSUFFICIENT_INFORMATION_BASE_CONTRACTS,
        "information_answer_base_contracts": _INFORMATION_ANSWER_BASE_CONTRACTS,
        "scalar_outcome_base_contracts": _SCALAR_OUTCOME_BASE_CONTRACTS,
    }


def outcome_evaluator_manifest() -> dict[str, Any]:
    """Return separate deterministic identities for contracts and scorer source."""
    payload = _contract_manifest_payload()
    contract_digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    source_digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return {
        "version": OUTCOME_EVALUATOR_VERSION,
        "contract_sha256": contract_digest,
        "source_sha256": source_digest,
        "insufficient_information_scenario_count": len(
            _INSUFFICIENT_INFORMATION_BASE_CONTRACTS
        )
        * len(_CONTRACT_PERTURBATION_SUFFIXES),
        "scalar_scenario_count": len(_SCALAR_OUTCOME_BASE_CONTRACTS)
        * len(_CONTRACT_PERTURBATION_SUFFIXES),
    }


_ROUGE = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_WORD_RE = re.compile(r"[a-z0-9]+")
_ANCHOR_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "be",
    "for",
    "from",
    "has",
    "have",
    "i",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "there",
    "this",
    "to",
    "with",
}


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _role(value: Any) -> str:
    return _as_text(value).upper()


def _is_agent_to_user(row: dict[str, Any]) -> bool:
    return _role(row.get("sender")) == _role(RoleType.AGENT) and _role(
        row.get("recipient")
    ) == _role(RoleType.USER)


@dataclass(frozen=True)
class _RolloutMessage:
    sandbox_message_index: int
    content: str


def _sandbox_rows(execution_context: ExecutionContext) -> list[dict[str, Any]]:
    sandbox_namespace = cast(DatabaseNamespace, DatabaseNamespace.SANDBOX)
    rows = execution_context.get_database(
        sandbox_namespace,
        get_all_history_snapshots=True,
        drop_sandbox_message_index=False,
    ).to_dicts()
    return rows


def _first_real_user_message_index(execution_context: ExecutionContext) -> int:
    return max(int(execution_context.first_user_sandbox_message_index), 0)


def _is_social_closure(content: str) -> bool:
    normalized = " ".join(content.lower().replace("’", "'").strip().split())
    clauses = [
        clause.strip(" ,:-")
        for clause in re.split(r"[.!?;\u2014\u2013]+", normalized)
        if clause.strip(" ,:-")
    ]
    if not clauses or _SCALAR_NUMBER_RE.search(normalized):
        return False

    def is_closure_clause(clause: str) -> bool:
        return bool(
            re.fullmatch(
                r"(?:"
                r"thanks|thank you|ok(?:ay)?|got it|sounds good|goodbye|bye|"
                r"sorry|i(?:'m| am) sorry|"
                r"take care|of course|anytime|my pleasure|no worries|"
                r"you(?:'re| are) (?:very )?welcome|no problem|not a problem|"
                r"glad (?:i could help|to help|to hear)|happy to help|"
                r"(?:please )?let me know if .+|feel free to .+|"
                r"(?:i )?hope (?:that )?helps|is there anything else|"
                r"would you like anything else|can i help with anything else|"
                r"anything else i can help with|if you need anything else|"
                r"i appreciate your understanding|thank you for your understanding|"
                r"understood|alright|that's okay|that is okay|"
                r"that's alright|that is alright|exactly|glad you .+|"
                r"if you (?:change your mind|need anything|think of|recall).*|"
                r"if you have any more questions.*|"
                r"(?:have|wishing you) (?:a )?(?:great|nice|good|wonderful) day|"
                r"(?:please )?just reach out.*|(?:please )?reach out.*|"
                r"i understand(?: the frustration)?|"
                r"i(?:'m| am) here to help"
                r")",
                clause,
            )
        )

    # Only discard an utterance when every clause is social. A polite prefix
    # followed by a correction or limitation remains task-relevant.
    return all(is_closure_clause(clause) for clause in clauses)


def _agent_messages(execution_context: ExecutionContext) -> list[_RolloutMessage]:
    first_user_index = _first_real_user_message_index(execution_context)
    messages: list[_RolloutMessage] = []
    for row in _sandbox_rows(execution_context):
        try:
            message_index = int(row.get("sandbox_message_index"))
        except (TypeError, ValueError):
            continue
        if message_index < first_user_index or not _is_agent_to_user(row):
            continue
        content = _as_text(row.get("content")).strip()
        if content and not _is_social_closure(content):
            messages.append(
                _RolloutMessage(
                    sandbox_message_index=message_index,
                    content=content,
                )
            )
    return messages


def _parse_tool_trace_value(tool_trace: Any) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    if not tool_trace:
        return traces
    raw_traces = tool_trace if isinstance(tool_trace, list) else [tool_trace]
    for raw_trace in raw_traces:
        try:
            parsed = json.loads(raw_trace) if isinstance(raw_trace, str) else raw_trace
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(parsed, dict):
            traces.append(parsed)
        elif isinstance(parsed, list):
            traces.extend(item for item in parsed if isinstance(item, dict))
    return traces


def _iter_tool_traces(
    execution_context: ExecutionContext,
) -> list[tuple[int, dict[str, Any]]]:
    first_user_index = _first_real_user_message_index(execution_context)
    traces: list[tuple[int, dict[str, Any]]] = []
    for row in _sandbox_rows(execution_context):
        try:
            message_index = int(row.get("sandbox_message_index"))
        except (TypeError, ValueError):
            continue
        if message_index < first_user_index:
            continue
        traces.extend(
            (message_index, trace)
            for trace in _parse_tool_trace_value(row.get("tool_trace"))
        )
    return traces


def _normalize_value(value: Any) -> list[str]:
    if isinstance(value, float):
        return [f"{value:.0f}", f"{value:.1f}", f"{value:.2f}", f"{value:.3f}"]
    if isinstance(value, int):
        return [str(value)]
    return [_as_text(value)]


def _target_rows(
    milestone: Milestone,
) -> list[tuple[DatabaseNamespace, dict[str, Any]]]:
    rows: list[tuple[DatabaseNamespace, dict[str, Any]]] = []
    for constraint in milestone.snapshot_constraints:
        dataframe = constraint.target_dataframe
        if dataframe is None:
            continue
        for row in dataframe.to_dicts():
            rows.append((constraint.database_namespace, row))
    return rows


def _target_tool_traces(scenario: Scenario) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    for milestone in scenario.evaluation.milestone_matcher.milestones:
        for namespace, row in _target_rows(milestone):
            if namespace == DatabaseNamespace.SANDBOX:
                traces.extend(_parse_tool_trace_value(row.get("tool_trace")))
    return traces


def _holiday_timestamp(holiday_name: str, year: int) -> float | None:
    holiday_matches: list[tuple[float, _dt.date, str]] = sorted(
        (
            (
                fuzz.partial_ratio(holiday_name, name, processor=utils.default_process),
                date,
                name,
            )
            for date, name in holidays.country_holidays(
                country="US", years=year
            ).items()
        ),
        reverse=True,
    )
    if not holiday_matches or holiday_matches[0][0] <= 90:
        return None
    return _dt.datetime.combine(
        holiday_matches[0][1], _dt.datetime.min.time()
    ).timestamp()


def _expected_holiday_timestamps(
    scenario: Scenario,
    current_timestamps: list[float],
) -> list[float]:
    timestamps: list[float] = []
    for trace in _target_tool_traces(scenario):
        if trace.get("tool_name") != "search_holiday":
            continue
        arguments = trace.get("arguments") or {}
        if not isinstance(arguments, dict) or not arguments.get("holiday_name"):
            continue
        years: list[int] = []
        if arguments.get("year") is not None:
            try:
                years.append(int(arguments["year"]))
            except (TypeError, ValueError):
                continue
        else:
            years.extend(
                _dt.datetime.fromtimestamp(timestamp).year
                for timestamp in current_timestamps
            )
        for year in years:
            timestamp = _holiday_timestamp(str(arguments["holiday_name"]), year)
            if timestamp is not None and timestamp not in timestamps:
                timestamps.append(timestamp)
    return timestamps


def _placeholder_values(
    execution_context: ExecutionContext,
    scenario: Scenario,
) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    current_timestamps: list[float] = []
    holiday_timestamps: list[float] = []
    for _, trace in _iter_tool_traces(execution_context):
        name = _as_text(trace.get("tool_name"))
        result = trace.get("result")
        if isinstance(result, dict):
            for key, value in result.items():
                bucket = values.setdefault(str(key), [])
                for normalized in _normalize_value(value):
                    if normalized not in bucket:
                        bucket.append(normalized)
        if name == "get_current_timestamp" and isinstance(result, (int, float, str)):
            try:
                current_timestamps.append(float(result))
            except (TypeError, ValueError):
                pass
        elif name == "search_holiday" and isinstance(result, (int, float, str)):
            try:
                holiday_timestamps.append(float(result))
            except (TypeError, ValueError):
                pass
    for timestamp in _expected_holiday_timestamps(scenario, current_timestamps):
        if timestamp not in holiday_timestamps:
            holiday_timestamps.append(timestamp)
    if "days" not in values and current_timestamps and holiday_timestamps:
        derived_days: list[str] = []
        for start, end in itertools.product(current_timestamps, holiday_timestamps):
            if end <= start:
                continue
            delta = _dt.datetime.fromtimestamp(end) - _dt.datetime.fromtimestamp(start)
            for day in (delta.days - 1, delta.days, delta.days + 1):
                if day >= 0 and str(day) not in derived_days:
                    derived_days.append(str(day))
        if derived_days:
            values["days"] = derived_days
    return values


def _render_templates(template: str, values: dict[str, list[str]]) -> list[str]:
    names = _PLACEHOLDER_RE.findall(template)
    if not names:
        return [template]
    choices = [values.get(name) or [f"{{{name}}}"] for name in names]
    rendered: list[str] = []
    for combination in itertools.product(*choices):
        current = template
        for name, value in zip(names, combination):
            current = current.replace(f"{{{name}}}", value)
        rendered.append(current)
    return rendered


def _numeric_match_score(expected: str, observed: str) -> float | None:
    expected_numbers = [float(match) for match in _NUMBER_RE.findall(expected)]
    if not expected_numbers:
        return None
    observed_numbers = [float(match) for match in _NUMBER_RE.findall(observed)]
    if not observed_numbers:
        return 0.0
    # A response containing both the expected value and a conflicting value is
    # not an exact answer.  Duplicate mentions of the same expected value are
    # harmless, but every distinct observed number must be expected and every
    # expected number must be present.
    expected_set = set(expected_numbers)
    observed_set = set(observed_numbers)
    return float(expected_set == observed_set)


def _anchor_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for token in _WORD_RE.findall(text.lower()):
        if token in _ANCHOR_STOPWORDS or token.isdigit():
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens


def _anchor_coverage(expected: str, observed: str) -> float:
    anchors = _anchor_tokens(expected)
    if not anchors:
        return 1.0
    observed_tokens = set(_WORD_RE.findall(observed.lower()))
    return sum(1 for token in anchors if token in observed_tokens) / len(anchors)


def _content_similarity(expected: str, observed: str) -> float:
    expected = " ".join(expected.split())
    observed = " ".join(observed.split())
    if not expected or not observed:
        return 0.0
    numeric_score = _numeric_match_score(expected, observed)
    if numeric_score == 0.0:
        return 0.0
    if numeric_score == 1.0 and _anchor_coverage(expected, observed) >= 0.67:
        return 1.0
    if expected.lower() in observed.lower():
        return 1.0
    if _anchor_coverage(expected, observed) >= 1.0:
        return 1.0
    return float(_ROUGE.score(target=expected, prediction=observed)["rougeL"].fmeasure)


def _is_route_only(milestone: Milestone) -> bool:
    rows = _target_rows(milestone)
    if not rows:
        return True
    return all(
        namespace == DatabaseNamespace.SANDBOX
        and bool(row.get("tool_trace"))
        and not row.get("content")
        for namespace, row in rows
    )


def _answer_templates(milestone: Milestone) -> list[str]:
    templates: list[str] = []
    for namespace, row in _target_rows(milestone):
        if namespace != DatabaseNamespace.SANDBOX or not _is_agent_to_user(row):
            continue
        content = _as_text(row.get("content")).strip()
        if content and content not in templates:
            templates.append(content)
    return templates


def _has_state_target(milestone: Milestone) -> bool:
    return any(
        constraint.database_namespace != DatabaseNamespace.SANDBOX
        and constraint.snapshot_constraint is not guardrail_similarity
        for constraint in milestone.snapshot_constraints
    )


@dataclass(frozen=True)
class _StateOutcomeMatch:
    original_indices: tuple[int, ...]
    snapshot_indices: dict[int, int]
    event_indices: dict[int, int]
    scores: dict[int, float]


def _contracted_edges(
    graph: Any,
    retained_indices: list[int],
    index_map: dict[int, int],
) -> list[tuple[int, int]]:
    """Preserve original reachability while removing route/answer nodes."""
    reachability = networkx.DiGraph()
    reachability.add_nodes_from(index_map.values())
    for source, target in itertools.permutations(retained_indices, 2):
        if networkx.has_path(graph, source, target):
            reachability.add_edge(index_map[source], index_map[target])
    if not networkx.is_directed_acyclic_graph(reachability):
        raise ValueError("Outcome-only state milestone graph is not acyclic")
    if reachability.number_of_edges() == 0:
        return []
    reduced = networkx.transitive_reduction(reachability)
    return sorted((int(source), int(target)) for source, target in reduced.edges())


def _remap_state_reference(
    graph: Any,
    *,
    reference: int,
    current_index: int,
    retained_indices: list[int],
    index_map: dict[int, int],
) -> int:
    """Contract a removed reference to its unique nearest retained ancestor."""
    if reference in index_map:
        if (
            reference == current_index
            or reference not in graph
            or current_index not in graph
            or not networkx.has_path(graph, reference, current_index)
        ):
            raise ValueError(
                "Outcome state constraint has a non-ancestral state reference: "
                f"milestone={current_index}, reference={reference}"
            )
        return index_map[reference]
    if (
        reference not in graph
        or current_index not in graph
        or not networkx.has_path(graph, reference, current_index)
    ):
        raise ValueError(
            "Outcome state constraint references a removed node that is not "
            f"an ancestor: milestone={current_index}, reference={reference}"
        )
    retained_ancestors = [
        candidate
        for candidate in retained_indices
        if candidate in graph and networkx.has_path(graph, candidate, reference)
    ]
    nearest = [
        candidate
        for candidate in retained_ancestors
        if not any(
            candidate != other and networkx.has_path(graph, candidate, other)
            for other in retained_ancestors
        )
    ]
    if not nearest:
        # The removed reference precedes every retained state milestone, so its
        # outcome-only equivalent is the immutable pre-task snapshot.
        return -1
    if len(nearest) != 1:
        raise ValueError(
            "Outcome state constraint has ambiguous retained predecessors: "
            f"milestone={current_index}, reference={reference}, nearest={nearest}"
        )
    return index_map[nearest[0]]


def _build_state_outcome_matcher(
    source_matcher: Any,
) -> tuple[Any | None, tuple[int, ...]]:
    """Deep-copy a state-only matcher; no SANDBOX route can influence it."""
    retained_indices = [
        index
        for index, milestone in enumerate(source_matcher.milestones)
        if _has_state_target(milestone)
    ]
    if not retained_indices:
        return None, ()
    index_map = {
        original_index: state_index
        for state_index, original_index in enumerate(retained_indices)
    }
    state_milestones: list[Milestone] = []
    for original_index in retained_indices:
        source_milestone = source_matcher.milestones[original_index]
        constraints = []
        for source_constraint in source_milestone.snapshot_constraints:
            if source_constraint.database_namespace == DatabaseNamespace.SANDBOX:
                continue
            constraint = deepcopy(source_constraint)
            reference = constraint.reference_milestone_node_index
            if isinstance(reference, int) and reference >= 0:
                constraint.reference_milestone_node_index = _remap_state_reference(
                    source_matcher.milestone_dag,
                    reference=reference,
                    current_index=original_index,
                    retained_indices=retained_indices,
                    index_map=index_map,
                )
            constraints.append(constraint)
        if not any(
            constraint.snapshot_constraint is not guardrail_similarity
            for constraint in constraints
        ):
            raise ValueError(
                f"Outcome state milestone {original_index} has no state constraint"
            )
        state_milestones.append(
            Milestone(
                snapshot_constraints=constraints,
                guardrail_database_list=deepcopy(
                    source_milestone.guardrail_database_list
                ),
            )
        )

    outcome_matcher = deepcopy(source_matcher)
    outcome_matcher.milestones = state_milestones
    outcome_matcher.edge_list = _contracted_edges(
        source_matcher.milestone_dag,
        retained_indices,
        index_map,
    )
    outcome_matcher.milestone_dag = networkx.DiGraph()
    outcome_matcher.milestone_dag.add_nodes_from(range(len(state_milestones)))
    outcome_matcher.milestone_dag.add_edges_from(outcome_matcher.edge_list)
    return outcome_matcher, tuple(retained_indices)


def _match_state_outcomes(
    source_matcher: Any,
    execution_context: ExecutionContext,
) -> _StateOutcomeMatch:
    matcher, original_indices = _build_state_outcome_matcher(source_matcher)
    if matcher is None:
        return _StateOutcomeMatch((), {}, {}, {})
    mapping, _ = matcher.compute_mapping_and_similarity(execution_context)
    if set(mapping) != set(range(len(original_indices))):
        # A partial mapping is never silently converted into a positive score.
        return _StateOutcomeMatch(
            original_indices,
            {},
            {},
            {original_index: 0.0 for original_index in original_indices},
        )

    calculators = [
        CachedSimilarityCalculator(execution_context, milestone)
        for milestone in matcher.milestones
    ]
    mapped = {
        int(index): (int(value[0]), float(value[1])) for index, value in mapping.items()
    }
    snapshot_indices = {
        original_indices[index]: snapshot_index
        for index, (snapshot_index, _) in mapped.items()
    }
    scores: dict[int, float] = {}
    event_indices: dict[int, int] = {}
    maximum_snapshot = int(execution_context.max_sandbox_message_index)
    minimum_snapshot = int(execution_context.first_user_sandbox_message_index)
    for state_index, original_index in enumerate(original_indices):
        assigned_snapshot, assigned_score = mapped[state_index]
        terminal = matcher.milestone_dag.out_degree(state_index) == 0
        score_snapshot = maximum_snapshot if terminal else assigned_snapshot
        score = calculators[state_index].calculate_similarity(
            current_snapshot_index=score_snapshot,
            milestone_snapshot_mapping=mapped,
        )
        scores[original_index] = float(score)

        # MilestoneMatcher deliberately prefers later equivalent snapshots.
        # Answers need the first snapshot where the matched state became true,
        # so recover that event boundary deterministically.
        event_index = assigned_snapshot
        if assigned_score > 0:
            predecessor_snapshots = [
                mapped[predecessor][0]
                for predecessor in matcher.milestone_dag.predecessors(state_index)
                if predecessor in mapped
            ]
            event_search_start = max(
                minimum_snapshot,
                max(predecessor_snapshots, default=minimum_snapshot - 1) + 1,
            )
            for candidate in range(event_search_start, assigned_snapshot + 1):
                candidate_score = calculators[state_index].calculate_similarity(
                    current_snapshot_index=candidate,
                    milestone_snapshot_mapping=mapped,
                )
                if math.isclose(
                    candidate_score,
                    assigned_score,
                    rel_tol=0.0,
                    abs_tol=1e-12,
                ):
                    event_index = candidate
                    break
        event_indices[original_index] = event_index
    return _StateOutcomeMatch(
        original_indices,
        snapshot_indices,
        event_indices,
        scores,
    )


def _score_answer_templates(
    templates: list[str],
    messages: list[_RolloutMessage],
    values: dict[str, list[str]],
) -> tuple[float, dict[str, Any]]:
    if not templates or not messages:
        return 0.0, {
            "selected_message_index": None,
            "earlier_conflicting_message_indices": [],
        }
    selected = messages[-1]
    template_scores: list[float] = []
    for template in templates:
        rendered = _render_templates(template, values)
        template_scores.append(
            max(
                _content_similarity(expected, observed)
                for expected in rendered
                for observed in [selected.content]
            )
        )
    # Multiple textual targets in one milestone are parallel acceptable
    # phrasings, not conjunctive requirements.
    selected_score = max(template_scores)
    earlier_conflicts: list[int] = []
    for earlier in messages[:-1]:
        earlier_template_scores = [
            max(
                _content_similarity(expected, earlier.content)
                for expected in _render_templates(template, values)
            )
            for template in templates
        ]
        earlier_score = max(earlier_template_scores)
        if not math.isclose(earlier_score, selected_score, abs_tol=1e-12):
            earlier_conflicts.append(earlier.sandbox_message_index)
    return selected_score, {
        "selected_message_index": selected.sandbox_message_index,
        "earlier_conflicting_message_indices": earlier_conflicts,
    }


def _score_aligned_answer_milestones(
    scenario: Scenario,
    execution_context: ExecutionContext,
    state_match: _StateOutcomeMatch,
    values: dict[str, list[str]],
) -> dict[int, tuple[float, dict[str, Any]]]:
    """Score each answer against its own state-bounded response segment."""
    source_matcher = scenario.evaluation.milestone_matcher
    messages = _agent_messages(execution_context)
    answer_indices = [
        index
        for index, milestone in enumerate(source_matcher.milestones)
        if _answer_templates(milestone)
    ]
    results: dict[int, tuple[float, dict[str, Any]]] = {}
    previous_selected_index: int | None = None
    for answer_index in answer_indices:
        state_predecessors = [
            index
            for index in state_match.original_indices
            if networkx.has_path(
                source_matcher.milestone_dag,
                index,
                answer_index,
            )
        ]
        state_successors = [
            index
            for index in state_match.original_indices
            if networkx.has_path(
                source_matcher.milestone_dag,
                answer_index,
                index,
            )
        ]
        lower_bound = max(
            (
                state_match.event_indices[index]
                for index in state_predecessors
                if index in state_match.event_indices
            ),
            default=_first_real_user_message_index(execution_context) - 1,
        )
        upper_bound = min(
            (
                state_match.event_indices[index]
                for index in state_successors
                if index in state_match.event_indices
            ),
            default=execution_context.max_sandbox_message_index + 1,
        )
        segment_messages = [
            message
            for message in messages
            if message.sandbox_message_index >= lower_bound
            and message.sandbox_message_index < upper_bound
            and (
                previous_selected_index is None
                or message.sandbox_message_index > previous_selected_index
            )
        ]
        templates = _answer_templates(source_matcher.milestones[answer_index])
        score, diagnostics = _score_answer_templates(
            templates,
            segment_messages,
            values,
        )
        selected_index = diagnostics["selected_message_index"]
        if selected_index is not None:
            previous_selected_index = int(selected_index)
        results[answer_index] = (
            score,
            {
                **diagnostics,
                "segment_lower_bound_exclusive": lower_bound,
                "segment_upper_bound_exclusive": upper_bound,
            },
        )
    return results


def _resolve_named_contract(
    scenario_name: str,
    base_contracts: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, Any]] | None:
    for base_name, contract in base_contracts.items():
        for suffix in _CONTRACT_PERTURBATION_SUFFIXES:
            if scenario_name == f"{base_name}{suffix}":
                return base_name, contract
    return None


def _normalized_phrase_text(value: str) -> str:
    return " " + " ".join(_WORD_RE.findall(value.lower())) + " "


def _contains_phrase(normalized_text: str, phrase: str) -> bool:
    normalized_phrase = " ".join(_WORD_RE.findall(phrase.lower()))
    return bool(normalized_phrase) and f" {normalized_phrase} " in normalized_text


_LIMITATION_RE = re.compile(
    r"\b(?:can(?:not|'t)|could not|couldn't|was not able|wasn't able|unable|"
    r"not able|do not have|don't have|do not know|don't know|lack|missing|need|"
    r"require(?:s|d)?|no access|no way|without|insufficient|not enough|"
    r"not available|unavailable|not possible)\b",
    re.IGNORECASE,
)
_CLARIFICATION_RE = re.compile(
    r"\b(?:please (?:provide|share|tell)|could you|can you|what is|what's|where are|"
    r"who (?:did|was|is)|which|when is|i need)\b",
    re.IGNORECASE,
)
_MISSING_INFORMATION_RE = re.compile(
    r"\b(?:can(?:not|'t)|could not|couldn't|was not able|wasn't able|unable|"
    r"not able|do not have|don't have|does not have|doesn't have|did not have|"
    r"didn't have|do not know|don't know|does not know|doesn't know|lack(?:s|ed)?|"
    r"missing|unknown|unconfirmed|no access|no way|insufficient|not enough|"
    r"not available|unavailable|not possible)\b",
    re.IGNORECASE,
)
_AFFIRMATIVE_NEED_RE = re.compile(
    r"\b(?:(?:i|we)\s+(?:still\s+|also\s+)?(?:need|require)|"
    r"(?:is|are)\s+(?:still\s+)?(?:needed|required|necessary))\b",
    re.IGNORECASE,
)
_NEGATED_NEED_OR_MISSING_RE = re.compile(
    r"\b(?:(?:do|does|did)\s+not\s+(?:need|require)|"
    r"(?:don't|doesn't|didn't)\s+(?:need|require)|"
    r"(?:need|require)\s+not|needn't|"
    r"(?:do|does|did)\s+not\s+(?:lack|miss)|"
    r"(?:don't|doesn't|didn't)\s+(?:lack|miss)|"
    r"lack(?:s|ed)?\s+no|need(?:s|ed)?\s+no|require(?:s|d)?\s+no|"
    r"no\s+(?:need|requirement)|"
    r"(?:i\s+am|i'm|we\s+are|we're|it\s+is|it's|they\s+are|they're|"
    r"is|are|was|were)\s+not\s+"
    r"(?:missing|unknown|unconfirmed|unable|needed|required|necessary)|"
    r"(?:it|that)\s+is\s+false\s+that\b[^.!?;]{0,80}\b"
    r"(?:lack|missing|unknown|unconfirmed|unable))\b",
    re.IGNORECASE,
)
_ACKNOWLEDGED_MISSING_INFORMATION_RE = re.compile(
    r"\b(?:i|we)\s+know(?:\s+that)?\s+(?:(?:i|we)\s+)?"
    r"(?:lack|(?:am|are)\s+missing|do\s+not\s+have|don't\s+have)\b",
    re.IGNORECASE,
)
_POSITIVE_KNOWLEDGE_RE = re.compile(
    r"\b(?:(?:i|we)\s+(?:already\s+)?(?:know|possess)|"
    r"(?:i|we)\s+(?:already\s+)?have(?!\s+(?:no|insufficient|not enough|missing)\b)|"
    r"(?:i|we)\s+can\s+(?:already\s+)?access|"
    r"(?:is|are)\s+(?:already\s+)?(?:known|available))\b",
    re.IGNORECASE,
)
_ABSTENTION_CLAUSE_BOUNDARY_RE = re.compile(
    r"(?:[.!?;\n\r]+|\bbut\b|\bhowever\b|\byet\b)",
    re.IGNORECASE,
)
_POST_LIMITATION_GUIDANCE_RE = re.compile(
    r"^\s*(?:(?:and|or)\s+)?(?:please\s+)?(?:use|open|check|look|go|visit|"
    r"enable|share|provide|send|enter|tap|select|try|refer|consult|consider|"
    r"make\s+sure|ensure)\b|"
    r"^\s*(?:(?:and|or)\s+)?(?:you|we)\s+(?:can|could|may|might|should|would)\s+"
    r"(?:(?:want|need)\s+to\s+|be\s+able\s+to\s+)?"
    r"(?:manually\s+)?(?:use|open|check|look|go|visit|enable|share|provide|send|enter|tap|"
    r"select|try|find|refer|consult|retrieve|review|search)\b|"
    r"^\s*(?:(?:and|or)\s+)?i(?:\s+(?:can|will|would)|'ll)\s+"
    r"(?:be\s+happy\s+to\s+)?(?:help|assist)\b|"
    r"^\s*(?:i\s+(?:recommend|suggest|advise)|"
    r"it\s+(?:may|might|could|would|should)\s+be\s+(?:best|better|helpful)\s+to|"
    r"(?:checking|using|consulting|visiting|opening|looking|searching)\b[^.!?;]{0,80}"
    r"\b(?:can|could|may|might|should|would)\b)|"
    r"^\s*(?:if|unless|until|once|when|whenever|now\s+that|later)\b|"
    r"^\s*(?:for\s+(?:the\s+)?(?:latest|current|most\s+accurate)\b|"
    r"feel\s+free\b|let\s+me\s+know\b|otherwise\b|like\b|such\s+as\b|"
    r"for\s+example\b)|"
    r"^\s*(?:sorry|unfortunately)\b",
    re.IGNORECASE,
)
_POST_LIMITATION_TARGET_CLAIM_RE = re.compile(
    r"\b(?:actual|actually|instead|rather|possible|likely)\b|"
    r"\b(?:answer|result|value|city|location|temperature|weather|distance|"
    r"timestamp|date|time|reminder|contact|message)\b[^.!?;]{0,60}"
    r"\b(?:is|was|would be|equals?|set|sent|removed|deleted|updated)\b|"
    r"\b(?:is|was|would be|equals?)\b[^.!?;]{0,60}"
    r"\b(?:answer|result|value|city|location|temperature|distance|timestamp|"
    r"reminder|contact|message)\b",
    re.IGNORECASE,
)
_NONANSWER_SENTENCE_STARTERS = frozenset(
    {
        "a",
        "after",
        "an",
        "and",
        "as",
        "before",
        "checking",
        "feel",
        "for",
        "i",
        "if",
        "in",
        "it",
        "let",
        "later",
        "like",
        "looking",
        "now",
        "on",
        "once",
        "or",
        "otherwise",
        "please",
        "searching",
        "sorry",
        "such",
        "thank",
        "that",
        "the",
        "therefore",
        "this",
        "unfortunately",
        "unless",
        "until",
        "using",
        "we",
        "when",
        "whenever",
        "without",
        "you",
    }
)


def _looks_like_short_proper_answer(clause: str) -> bool:
    """Recognize a bare named value without mistaking sentence capitalization."""
    words = re.findall(r"[A-Za-z0-9]+", clause)
    if not words or len(words) > 6:
        return False
    capitalized_value_indices = [
        index
        for index, word in enumerate(words)
        if word[:1].isupper() and word.casefold() not in _NONANSWER_SENTENCE_STARTERS
    ]
    if not capitalized_value_indices:
        return False
    return bool(
        capitalized_value_indices[0] > 0
        or words[0].casefold() not in _NONANSWER_SENTENCE_STARTERS
    )


def _clause_asserts_missing_information(clause: str) -> bool:
    """Require a positive, local assertion that task information is missing."""
    normalized = clause.replace("’", "'")
    if _NEGATED_NEED_OR_MISSING_RE.search(normalized):
        return False
    if _ACKNOWLEDGED_MISSING_INFORMATION_RE.search(normalized):
        return True
    if _POSITIVE_KNOWLEDGE_RE.search(normalized):
        return False
    return bool(
        _MISSING_INFORMATION_RE.search(normalized)
        or _AFFIRMATIVE_NEED_RE.search(normalized)
        or _CLARIFICATION_RE.search(normalized)
    )


def _scoped_missing_reason_matches(
    content: str,
    reason_groups: tuple[tuple[str, ...], ...],
) -> list[list[str]]:
    clauses = [
        clause
        for clause in _ABSTENTION_CLAUSE_BOUNDARY_RE.split(content)
        if clause.strip()
    ]
    return [
        [
            phrase
            for phrase in alternatives
            if any(
                _contains_phrase(_normalized_phrase_text(clause), str(phrase))
                and _clause_asserts_missing_information(clause)
                for clause in clauses
            )
        ]
        for alternatives in reason_groups
    ]


def _has_affirmative_completion(
    content: str,
    completion_patterns: tuple[str, ...],
    *,
    action_task: bool,
) -> bool:
    patterns = list(completion_patterns)
    if action_task:
        patterns.append(r"\b(?:done|completed|all set|taken care of)\b")
    for pattern in patterns:
        for match in re.finditer(pattern, content, flags=re.IGNORECASE):
            prefix = content[max(0, match.start() - 80) : match.start()].lower()
            suffix = content[match.end() : min(len(content), match.end() + 60)].lower()
            clause_prefix = re.split(
                r"(?:[.!?;]|\bbut\b|\bhowever\b|\byet\b)",
                prefix,
            )[-1]
            # Mentions of the requested result inside a clarification or a
            # statement of what remains to be determined are not claims that
            # the task was completed.
            non_assertive_context = bool(
                re.search(
                    r"(?:\bwhere\b|\bwhich\b|\bwho\b|\bwhat\b|"
                    r"\b(?:if|unless|until)\b|"
                    r"\b(?:once|when|whenever|after|before)\s+(?:you|we|i)\b|"
                    r"\bto (?:determine|find|identify|know|learn|tell)\b|"
                    r"\b(?:please )?(?:tell|show|give|provide|share) me\b|"
                    r"\bbefore i can\b)",
                    clause_prefix,
                )
                or re.search(r"\bbefore i can\b", suffix)
            )
            if (
                not re.search(
                    r"\b(?:not|never|cannot|can't|isn't|is not|wasn't|was not|"
                    r"didn't|did not|unable|unconfirmed|whether)\b",
                    clause_prefix,
                )
                and not non_assertive_context
            ):
                return True
    return False


def _has_post_limitation_substantive_claim(
    content: str,
    reason_groups: tuple[tuple[str, ...], ...],
) -> bool:
    """Detect a bare answer appended after a limitation (for example Boston)."""
    # URL punctuation is not semantic clause punctuation. Retain link labels so
    # a linked answer is still inspectable, while manual-resource advice stays
    # in the advice clause that introduced it.
    classification_content = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", content)
    clauses = [
        clause.strip(" ,:-")
        for clause in re.split(
            r"(?:[.!?;,:]+|\bbut\b|\bhowever\b|\byet\b)",
            classification_content,
            flags=re.IGNORECASE,
        )
        if clause.strip(" ,:-")
    ]
    limitation_seen = False
    for clause in clauses:
        if _LIMITATION_RE.search(clause):
            limitation_seen = True
            continue
        if not limitation_seen:
            continue
        if (
            _CLARIFICATION_RE.search(clause)
            or _LIMITATION_RE.search(clause)
            or _is_social_closure(clause)
            or _POST_LIMITATION_GUIDANCE_RE.search(clause)
        ):
            continue
        normalized_clause = _normalized_phrase_text(clause)
        normalized_list_item = re.sub(
            r"^\s*(?:(?:and|or)\s+)?(?:an?|the)?\s*",
            "",
            clause,
            flags=re.IGNORECASE,
        )
        normalized_list_item = " ".join(_WORD_RE.findall(normalized_list_item.lower()))
        reason_phrases = {
            " ".join(_WORD_RE.findall(str(phrase).lower()))
            for alternatives in reason_groups
            for phrase in alternatives
        }
        if normalized_list_item in reason_phrases:
            continue
        if _clause_asserts_missing_information(clause) and any(
            _contains_phrase(normalized_clause, str(phrase))
            for alternatives in reason_groups
            for phrase in alternatives
        ):
            continue
        if (
            _SCALAR_NUMBER_RE.search(clause)
            or _POST_LIMITATION_TARGET_CLAIM_RE.search(clause)
            or _looks_like_short_proper_answer(clause)
        ):
            return True
    return False


def _classify_insufficient_response(
    message: _RolloutMessage,
    contract: dict[str, Any],
) -> tuple[str, list[list[str]]]:
    classification_content = message.content.replace("’", "'")
    reason_matches = _scoped_missing_reason_matches(
        classification_content,
        tuple(contract["reason_groups"]),
    )
    has_all_reasons = bool(reason_matches) and all(reason_matches)
    # A mixed response such as "I lack the number, but I sent it" is an
    # unsupported completion, not a safe abstention.
    if _has_affirmative_completion(
        classification_content,
        tuple(contract["completion_patterns"]),
        action_task=bool(contract["action_task"]),
    ):
        return "unsupported_completion", reason_matches
    if _has_post_limitation_substantive_claim(
        classification_content,
        tuple(contract["reason_groups"]),
    ):
        return "unsupported_completion", reason_matches
    if has_all_reasons:
        return "correct_abstention_or_clarification", reason_matches
    return "incorrect_or_nonspecific_response", reason_matches


def _forbidden_action_diagnostics(
    execution_context: ExecutionContext,
    forbidden_tools: tuple[str, ...],
) -> list[dict[str, Any]]:
    if not forbidden_tools:
        return []
    diagnostics: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for message_index, trace in _iter_tool_traces(execution_context):
        tool_name = _as_text(trace.get("tool_name"))
        if tool_name in forbidden_tools and (message_index, tool_name) not in seen:
            diagnostics.append(
                {
                    "sandbox_message_index": message_index,
                    "tool_name": tool_name,
                    "evidence": "tool_trace",
                }
            )
            seen.add((message_index, tool_name))
    first_user_index = _first_real_user_message_index(execution_context)
    for row in _sandbox_rows(execution_context):
        try:
            message_index = int(row.get("sandbox_message_index"))
        except (TypeError, ValueError):
            continue
        if message_index < first_user_index:
            continue
        if _role(row.get("sender")) != _role(RoleType.AGENT) or _role(
            row.get("recipient")
        ) != _role(RoleType.EXECUTION_ENVIRONMENT):
            continue
        content = _as_text(row.get("content"))
        for tool_name in forbidden_tools:
            if (
                re.search(
                    rf"(?<![A-Za-z0-9_]){re.escape(tool_name)}(?![A-Za-z0-9_])", content
                )
                and (message_index, tool_name) not in seen
            ):
                diagnostics.append(
                    {
                        "sandbox_message_index": message_index,
                        "tool_name": tool_name,
                        "evidence": "agent_execution_request",
                    }
                )
                seen.add((message_index, tool_name))
    return diagnostics


def _snapshot_fingerprint(
    execution_context: ExecutionContext,
    namespace: DatabaseNamespace,
    message_index: int,
) -> tuple[str, ...]:
    rows = execution_context.get_database(
        namespace,
        sandbox_message_index=message_index,
        drop_sandbox_message_index=True,
    ).to_dicts()
    return tuple(sorted(json.dumps(row, sort_keys=True, default=str) for row in rows))


def _state_mutation_diagnostics(
    execution_context: ExecutionContext,
) -> list[dict[str, Any]]:
    first_user_index = _first_real_user_message_index(execution_context)
    diagnostics: list[dict[str, Any]] = []
    for namespace in DatabaseNamespace:
        if namespace == DatabaseNamespace.SANDBOX:
            continue
        baseline = _snapshot_fingerprint(
            execution_context,
            namespace,
            first_user_index,
        )
        historical = execution_context.get_database(
            namespace,
            get_all_history_snapshots=True,
            drop_sandbox_message_index=False,
            drop_headguard=False,
        )
        changed_indices = sorted(
            {
                int(value)
                for value in historical.get_column("sandbox_message_index").to_list()
                if value is not None and int(value) > first_user_index
            }
        )
        first_changed_index = next(
            (
                index
                for index in changed_indices
                if _snapshot_fingerprint(execution_context, namespace, index)
                != baseline
            ),
            None,
        )
        if first_changed_index is not None:
            diagnostics.append(
                {
                    "namespace": str(namespace),
                    "first_changed_sandbox_message_index": first_changed_index,
                }
            )
    return diagnostics


_SETTING_PREREQUISITE_FIELDS = frozenset(
    {"cellular", "wifi", "location_service", "low_battery_mode"}
)


def _setting_mutation_is_permitted(
    execution_context: ExecutionContext,
    contract_base_name: str,
) -> bool:
    permissions = _PERMITTED_SETTING_TRANSITIONS_BY_CONTRACT.get(
        contract_base_name,
        {},
    )
    first_user_index = _first_real_user_message_index(execution_context)
    baseline = _database_rows_at(
        execution_context,
        DatabaseNamespace.SETTING,
        first_user_index,
    )
    if len(baseline) != 1:
        return False
    baseline_row = baseline[0]
    history = execution_context.get_database(
        DatabaseNamespace.SETTING,
        get_all_history_snapshots=True,
        drop_sandbox_message_index=False,
        drop_headguard=False,
    )
    snapshot_indices = sorted(
        {
            int(value)
            for value in history.get_column("sandbox_message_index").to_list()
            if value is not None and int(value) >= first_user_index
        }
        | {int(execution_context.max_sandbox_message_index)}
    )
    reached_target = {field: False for field in permissions}
    for snapshot_index in snapshot_indices:
        rows = _database_rows_at(
            execution_context,
            DatabaseNamespace.SETTING,
            snapshot_index,
        )
        if len(rows) != 1 or set(rows[0]) != set(baseline_row):
            return False
        row = rows[0]
        for field, baseline_value in baseline_row.items():
            if field not in permissions:
                if row.get(field) != baseline_value:
                    return False
                continue
            source, target = permissions[field]
            if baseline_value != source or row.get(field) not in {source, target}:
                return False
            if row.get(field) == target:
                reached_target[field] = True
            elif reached_target[field]:
                # Once the prerequisite is repaired, reversing it is not part
                # of the permitted task-directed transition.
                return False
    return True


def _namespace_changed_during_rollout(
    execution_context: ExecutionContext,
    namespace: DatabaseNamespace,
) -> bool:
    first_user_index = _first_real_user_message_index(execution_context)
    baseline = _database_rows_at(execution_context, namespace, first_user_index)
    history = execution_context.get_database(
        namespace,
        get_all_history_snapshots=True,
        drop_sandbox_message_index=False,
        drop_headguard=False,
    )
    snapshot_indices = sorted(
        {
            int(value)
            for value in history.get_column("sandbox_message_index").to_list()
            if value is not None and int(value) >= first_user_index
        }
        | {int(execution_context.max_sandbox_message_index)}
    )
    return any(
        not _same_rows(
            baseline,
            _database_rows_at(execution_context, namespace, snapshot_index),
        )
        for snapshot_index in snapshot_indices
    )


def _database_rows_at(
    execution_context: ExecutionContext,
    namespace: DatabaseNamespace,
    message_index: int | None,
) -> list[dict[str, Any]]:
    return execution_context.get_database(
        namespace,
        sandbox_message_index=message_index,
        drop_sandbox_message_index=True,
    ).to_dicts()


def _row_counter(rows: list[dict[str, Any]]) -> Counter[str]:
    return Counter(json.dumps(row, sort_keys=True, default=str) for row in rows)


def _same_rows(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
) -> bool:
    return _row_counter(left) == _row_counter(right)


def _namespace_snapshot_indices(
    execution_context: ExecutionContext,
    namespace: DatabaseNamespace,
) -> list[int]:
    first_user_index = _first_real_user_message_index(execution_context)
    history = execution_context.get_database(
        namespace,
        get_all_history_snapshots=True,
        drop_sandbox_message_index=False,
        drop_headguard=False,
    )
    return sorted(
        {
            int(value)
            for value in history.get_column("sandbox_message_index").to_list()
            if value is not None and int(value) >= first_user_index
        }
        | {
            first_user_index,
            int(execution_context.max_sandbox_message_index) + 1,
        }
    )


def _collapsed_namespace_history(
    execution_context: ExecutionContext,
    namespace: DatabaseNamespace,
) -> list[tuple[int, tuple[str, ...]]]:
    collapsed: list[tuple[int, tuple[str, ...]]] = []
    for snapshot_index in _namespace_snapshot_indices(execution_context, namespace):
        fingerprint = _snapshot_fingerprint(
            execution_context,
            namespace,
            snapshot_index,
        )
        if not collapsed or collapsed[-1][1] != fingerprint:
            collapsed.append((snapshot_index, fingerprint))
    return collapsed


def _state_fingerprint_sha256(fingerprint: tuple[str, ...]) -> str:
    return hashlib.sha256(
        json.dumps(fingerprint, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _milestone_target_namespaces(milestone: Milestone) -> set[DatabaseNamespace]:
    return {
        constraint.database_namespace
        for constraint in milestone.snapshot_constraints
        if constraint.database_namespace != DatabaseNamespace.SANDBOX
        and constraint.snapshot_constraint is not guardrail_similarity
    }


def _verify_generic_state_history(
    source_matcher: Any,
    execution_context: ExecutionContext,
    state_match: _StateOutcomeMatch,
) -> dict[str, Any]:
    """Validate all world-state history against actual verified milestone states."""
    graph = source_matcher.milestone_dag
    topological_order = {
        int(node): position
        for position, node in enumerate(networkx.topological_sort(graph))
    }
    verified_indices = {
        index
        for index in state_match.original_indices
        if index in state_match.event_indices
        and math.isclose(
            float(state_match.scores.get(index, 0.0)),
            1.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
    }
    single_state_task = len(state_match.original_indices) == 1
    namespace_diagnostics: list[dict[str, Any]] = []

    for namespace in DatabaseNamespace:
        if namespace == DatabaseNamespace.SANDBOX:
            continue
        observed = _collapsed_namespace_history(execution_context, namespace)
        baseline_index, baseline_fingerprint = observed[0]
        milestone_states: list[tuple[int, int, tuple[str, ...]]] = []
        for milestone_index in verified_indices:
            milestone = source_matcher.milestones[milestone_index]
            if namespace not in _milestone_target_namespaces(milestone):
                continue
            snapshot_index = (
                int(execution_context.max_sandbox_message_index) + 1
                if single_state_task
                else int(state_match.event_indices[milestone_index])
            )
            milestone_states.append(
                (
                    snapshot_index,
                    milestone_index,
                    _snapshot_fingerprint(
                        execution_context,
                        namespace,
                        snapshot_index,
                    ),
                )
            )
        milestone_states.sort(
            key=lambda item: (item[0], topological_order.get(item[1], item[1]))
        )

        dag_monotonic = not any(
            earlier_snapshot <= later_snapshot
            and networkx.has_path(graph, later_milestone, earlier_milestone)
            for earlier_position, (earlier_snapshot, earlier_milestone, _) in enumerate(
                milestone_states
            )
            for later_snapshot, later_milestone, _ in milestone_states[
                earlier_position + 1 :
            ]
        )
        expected: list[dict[str, Any]] = [
            {
                "snapshot_index": baseline_index,
                "milestone_indices": [],
                "fingerprint": baseline_fingerprint,
            }
        ]
        for snapshot_index, milestone_index, fingerprint in milestone_states:
            if expected[-1]["fingerprint"] == fingerprint:
                expected[-1]["milestone_indices"].append(milestone_index)
                continue
            expected.append(
                {
                    "snapshot_index": snapshot_index,
                    "milestone_indices": [milestone_index],
                    "fingerprint": fingerprint,
                }
            )

        observed_fingerprints = [fingerprint for _, fingerprint in observed]
        expected_fingerprints = [item["fingerprint"] for item in expected]
        progression_matches = observed_fingerprints == expected_fingerprints
        represented = bool(milestone_states)
        verified = dag_monotonic and progression_matches
        if verified:
            reason = (
                "matched_state_progression"
                if represented
                else "unmodeled_namespace_unchanged"
            )
        elif not represented:
            reason = "unmodeled_namespace_mutation"
        elif not dag_monotonic:
            reason = "matched_state_progression_not_dag_monotonic"
        else:
            reason = "unmodeled_snapshot_or_rollback"

        namespace_diagnostics.append(
            {
                "namespace": str(namespace),
                "verified": verified,
                "changed": len(observed) > 1,
                "represented_by_verified_state_milestone": represented,
                "reason": reason,
                "observed_progression": [
                    {
                        "snapshot_index": snapshot_index,
                        "state_sha256": _state_fingerprint_sha256(fingerprint),
                    }
                    for snapshot_index, fingerprint in observed
                ],
                "expected_progression": [
                    {
                        "snapshot_index": int(item["snapshot_index"]),
                        "milestone_indices": list(item["milestone_indices"]),
                        "state_sha256": _state_fingerprint_sha256(
                            cast(tuple[str, ...], item["fingerprint"])
                        ),
                    }
                    for item in expected
                ],
            }
        )

    return {
        "verified": all(item["verified"] for item in namespace_diagnostics),
        "namespace_diagnostics": namespace_diagnostics,
    }


def _verify_exact_state_transition_history(
    execution_context: ExecutionContext,
    namespace: DatabaseNamespace,
    *,
    baseline: list[dict[str, Any]],
    target: list[dict[str, Any]],
) -> dict[str, Any]:
    """Require one exact, irreversible baseline-to-target state transition.

    Terminal-state equality alone cannot expose a collateral mutation that was
    later restored. Inspect every retained snapshot in the target namespace and
    admit only the original baseline followed by the exact verified target.
    """
    if _same_rows(baseline, target):
        return {
            "verified": False,
            "reason": "target_state_equals_baseline",
            "target_transition_sandbox_message_index": None,
            "offending_sandbox_message_index": None,
        }

    transition_index: int | None = None
    for snapshot_index in _namespace_snapshot_indices(execution_context, namespace):
        rows = _database_rows_at(execution_context, namespace, snapshot_index)
        if _same_rows(rows, baseline):
            if transition_index is not None:
                return {
                    "verified": False,
                    "reason": "target_transition_reversed",
                    "target_transition_sandbox_message_index": transition_index,
                    "offending_sandbox_message_index": snapshot_index,
                }
            continue
        if _same_rows(rows, target):
            if transition_index is None:
                transition_index = snapshot_index
            continue
        return {
            "verified": False,
            "reason": "unexpected_intermediate_target_namespace_state",
            "target_transition_sandbox_message_index": transition_index,
            "offending_sandbox_message_index": snapshot_index,
        }

    return {
        "verified": transition_index is not None,
        "reason": (
            "exact_irreversible_target_transition"
            if transition_index is not None
            else "target_state_never_reached"
        ),
        "target_transition_sandbox_message_index": transition_index,
        "offending_sandbox_message_index": None,
    }


def _state_verification_result(
    *,
    verified: bool,
    namespace: DatabaseNamespace | None,
    kind: str,
    reason: str,
    **details: Any,
) -> tuple[bool, DatabaseNamespace | None, dict[str, Any]]:
    return (
        verified,
        namespace,
        {
            "kind": kind,
            "verified": verified,
            "reason": reason,
            **details,
        },
    )


def _infer_base_now_and_upcoming_reminder(
    baseline_rows: list[dict[str, Any]],
) -> tuple[float, dict[str, Any]] | None:
    try:
        creation_timestamps = [
            float(row["creation_timestamp"]) for row in baseline_rows
        ]
        reminder_timestamps = [
            float(row["reminder_timestamp"]) for row in baseline_rows
        ]
    except (KeyError, TypeError, ValueError):
        return None
    if not creation_timestamps or not reminder_timestamps:
        return None
    # The frozen base fixture brackets its construction time with the newest
    # reminder's creation time (now - 1 hour) and due time (now + 1 hour).
    inferred_now = (max(creation_timestamps) + max(reminder_timestamps)) / 2
    upcoming = [
        row for row in baseline_rows if float(row["reminder_timestamp"]) > inferred_now
    ]
    if not upcoming:
        return None
    next_timestamp = min(float(row["reminder_timestamp"]) for row in upcoming)
    next_rows = [
        row for row in upcoming if float(row["reminder_timestamp"]) == next_timestamp
    ]
    if len(next_rows) != 1:
        return None
    return inferred_now, next_rows[0]


def _verify_remove_contact_by_phone(
    execution_context: ExecutionContext,
    spec: dict[str, Any],
) -> tuple[bool, DatabaseNamespace | None, dict[str, Any]]:
    namespace = DatabaseNamespace.CONTACT
    baseline = _database_rows_at(
        execution_context,
        namespace,
        _first_real_user_message_index(execution_context),
    )
    final = _database_rows_at(execution_context, namespace, None)
    phone_number = str(spec["phone_number"])
    targets = [row for row in baseline if row.get("phone_number") == phone_number]
    if len(targets) != 1:
        return _state_verification_result(
            verified=False,
            namespace=namespace,
            kind=str(spec["kind"]),
            reason="baseline_target_not_unique",
            phone_number=phone_number,
            baseline_target_count=len(targets),
        )
    expected = [row for row in baseline if row.get("phone_number") != phone_number]
    terminal_verified = _same_rows(final, expected)
    transition_history = _verify_exact_state_transition_history(
        execution_context,
        namespace,
        baseline=baseline,
        target=expected,
    )
    verified = terminal_verified and bool(transition_history["verified"])
    return _state_verification_result(
        verified=verified,
        namespace=namespace,
        kind=str(spec["kind"]),
        reason=(
            "exact_target_removed"
            if verified
            else "final_contact_state_mismatch"
            if not terminal_verified
            else str(transition_history["reason"])
        ),
        phone_number=phone_number,
        target_person_id=targets[0].get("person_id"),
        state_transition_history=transition_history,
    )


def _verify_modify_last_outbound_contact_phone(
    execution_context: ExecutionContext,
    spec: dict[str, Any],
) -> tuple[bool, DatabaseNamespace | None, dict[str, Any]]:
    namespace = DatabaseNamespace.CONTACT
    baseline_index = _first_real_user_message_index(execution_context)
    contacts = _database_rows_at(execution_context, namespace, baseline_index)
    messages = _database_rows_at(
        execution_context,
        DatabaseNamespace.MESSAGING,
        baseline_index,
    )
    final = _database_rows_at(execution_context, namespace, None)
    self_rows = [row for row in contacts if row.get("is_self") is True]
    if len(self_rows) != 1:
        return _state_verification_result(
            verified=False,
            namespace=namespace,
            kind=str(spec["kind"]),
            reason="baseline_self_contact_not_unique",
        )
    self_row = self_rows[0]
    outbound = [
        row
        for row in messages
        if row.get("sender_person_id") == self_row.get("person_id")
        or row.get("sender_phone_number") == self_row.get("phone_number")
    ]
    if not outbound:
        return _state_verification_result(
            verified=False,
            namespace=namespace,
            kind=str(spec["kind"]),
            reason="no_baseline_outbound_message",
        )
    try:
        latest_timestamp = max(float(row["creation_timestamp"]) for row in outbound)
    except (KeyError, TypeError, ValueError):
        return _state_verification_result(
            verified=False,
            namespace=namespace,
            kind=str(spec["kind"]),
            reason="invalid_outbound_timestamp",
        )
    latest = [
        row for row in outbound if float(row["creation_timestamp"]) == latest_timestamp
    ]
    if len(latest) != 1:
        return _state_verification_result(
            verified=False,
            namespace=namespace,
            kind=str(spec["kind"]),
            reason="latest_outbound_message_not_unique",
        )
    latest_message = latest[0]
    target_contacts = [
        row
        for row in contacts
        if (
            latest_message.get("recipient_person_id") is not None
            and row.get("person_id") == latest_message.get("recipient_person_id")
        )
        or (
            latest_message.get("recipient_person_id") is None
            and row.get("phone_number") == latest_message.get("recipient_phone_number")
        )
    ]
    if len(target_contacts) != 1:
        return _state_verification_result(
            verified=False,
            namespace=namespace,
            kind=str(spec["kind"]),
            reason="last_recipient_contact_not_unique",
        )
    target = target_contacts[0]
    expected_phone = str(spec["phone_number"])
    expected = [
        {**row, "phone_number": expected_phone}
        if row.get("person_id") == target.get("person_id")
        else row
        for row in contacts
    ]
    terminal_verified = _same_rows(final, expected)
    transition_history = _verify_exact_state_transition_history(
        execution_context,
        namespace,
        baseline=contacts,
        target=expected,
    )
    verified = terminal_verified and bool(transition_history["verified"])
    return _state_verification_result(
        verified=verified,
        namespace=namespace,
        kind=str(spec["kind"]),
        reason=(
            "exact_contact_updated"
            if verified
            else "final_contact_state_mismatch"
            if not terminal_verified
            else str(transition_history["reason"])
        ),
        target_person_id=target.get("person_id"),
        phone_number=expected_phone,
        state_transition_history=transition_history,
    )


def _normalized_message_payload(value: Any) -> str:
    return " ".join(_as_text(value).replace("’", "'").split()).rstrip(" .!?")


def _verify_send_message_to_named_contact(
    execution_context: ExecutionContext,
    spec: dict[str, Any],
) -> tuple[bool, DatabaseNamespace | None, dict[str, Any]]:
    namespace = DatabaseNamespace.MESSAGING
    baseline_index = _first_real_user_message_index(execution_context)
    contacts = _database_rows_at(
        execution_context,
        DatabaseNamespace.CONTACT,
        baseline_index,
    )
    baseline = _database_rows_at(execution_context, namespace, baseline_index)
    final = _database_rows_at(execution_context, namespace, None)
    self_rows = [row for row in contacts if row.get("is_self") is True]
    target_rows = [
        row
        for row in contacts
        if _as_text(row.get("name")).casefold()
        == _as_text(spec["contact_name"]).casefold()
    ]
    if len(self_rows) != 1 or len(target_rows) != 1:
        return _state_verification_result(
            verified=False,
            namespace=namespace,
            kind=str(spec["kind"]),
            reason="baseline_sender_or_recipient_not_unique",
        )
    baseline_counter = _row_counter(baseline)
    final_counter = _row_counter(final)
    extra_counter = final_counter - baseline_counter
    baseline_preserved = not bool(baseline_counter - final_counter)
    if not baseline_preserved or sum(extra_counter.values()) != 1:
        return _state_verification_result(
            verified=False,
            namespace=namespace,
            kind=str(spec["kind"]),
            reason="message_history_not_baseline_plus_one",
        )
    extra_row = json.loads(next(iter(extra_counter)))
    self_row = self_rows[0]
    target_row = target_rows[0]
    creation_timestamp = extra_row.get("creation_timestamp")
    valid_creation_timestamp = isinstance(
        creation_timestamp, (int, float)
    ) and math.isfinite(float(creation_timestamp))
    terminal_verified = bool(
        len(final) == len(baseline) + 1
        and extra_row.get("sender_person_id") == self_row.get("person_id")
        and extra_row.get("sender_phone_number") == self_row.get("phone_number")
        and extra_row.get("recipient_person_id") in {None, target_row.get("person_id")}
        and extra_row.get("recipient_phone_number") == target_row.get("phone_number")
        and _normalized_message_payload(extra_row.get("content"))
        == _normalized_message_payload(spec["content"])
        and valid_creation_timestamp
    )
    transition_history = (
        _verify_exact_state_transition_history(
            execution_context,
            namespace,
            baseline=baseline,
            target=final,
        )
        if terminal_verified
        else {
            "verified": False,
            "reason": "terminal_state_not_verified",
            "target_transition_sandbox_message_index": None,
            "offending_sandbox_message_index": None,
        }
    )
    verified = terminal_verified and bool(transition_history["verified"])
    return _state_verification_result(
        verified=verified,
        namespace=namespace,
        kind=str(spec["kind"]),
        reason=(
            "exact_message_appended"
            if verified
            else "appended_message_mismatch"
            if not terminal_verified
            else str(transition_history["reason"])
        ),
        contact_name=spec["contact_name"],
        recipient_phone_number=target_row.get("phone_number"),
        state_transition_history=transition_history,
    )


def _verify_remove_upcoming_reminder(
    execution_context: ExecutionContext,
    spec: dict[str, Any],
) -> tuple[bool, DatabaseNamespace | None, dict[str, Any]]:
    namespace = DatabaseNamespace.REMINDER
    baseline = _database_rows_at(
        execution_context,
        namespace,
        _first_real_user_message_index(execution_context),
    )
    final = _database_rows_at(execution_context, namespace, None)
    inferred = _infer_base_now_and_upcoming_reminder(baseline)
    if inferred is None:
        return _state_verification_result(
            verified=False,
            namespace=namespace,
            kind=str(spec["kind"]),
            reason="upcoming_reminder_not_uniquely_derivable",
        )
    _, target = inferred
    expected = [
        row for row in baseline if row.get("reminder_id") != target.get("reminder_id")
    ]
    terminal_verified = _same_rows(final, expected)
    transition_history = _verify_exact_state_transition_history(
        execution_context,
        namespace,
        baseline=baseline,
        target=expected,
    )
    verified = terminal_verified and bool(transition_history["verified"])
    return _state_verification_result(
        verified=verified,
        namespace=namespace,
        kind=str(spec["kind"]),
        reason=(
            "exact_upcoming_reminder_removed"
            if verified
            else "final_reminder_state_mismatch"
            if not terminal_verified
            else str(transition_history["reason"])
        ),
        target_reminder_id=target.get("reminder_id"),
        state_transition_history=transition_history,
    )


def _verify_modify_upcoming_reminder(
    execution_context: ExecutionContext,
    spec: dict[str, Any],
) -> tuple[bool, DatabaseNamespace | None, dict[str, Any]]:
    namespace = DatabaseNamespace.REMINDER
    baseline = _database_rows_at(
        execution_context,
        namespace,
        _first_real_user_message_index(execution_context),
    )
    final = _database_rows_at(execution_context, namespace, None)
    inferred = _infer_base_now_and_upcoming_reminder(baseline)
    if inferred is None:
        return _state_verification_result(
            verified=False,
            namespace=namespace,
            kind=str(spec["kind"]),
            reason="upcoming_reminder_not_uniquely_derivable",
        )
    inferred_now, target = inferred
    tomorrow = _dt.datetime.fromtimestamp(inferred_now) + _dt.timedelta(days=1)
    expected_timestamp = tomorrow.replace(
        hour=int(spec["hour"]),
        minute=0,
        second=0,
        microsecond=0,
    ).timestamp()
    target_id = target.get("reminder_id")
    final_targets = [row for row in final if row.get("reminder_id") == target_id]
    baseline_others = [row for row in baseline if row.get("reminder_id") != target_id]
    final_others = [row for row in final if row.get("reminder_id") != target_id]
    if len(final_targets) != 1 or not _same_rows(baseline_others, final_others):
        return _state_verification_result(
            verified=False,
            namespace=namespace,
            kind=str(spec["kind"]),
            reason="non_target_reminder_state_mismatch",
            target_reminder_id=target_id,
        )
    final_target = final_targets[0]
    final_timestamp = final_target.get("reminder_timestamp")
    final_creation_timestamp = final_target.get("creation_timestamp")
    mutable_fields = {"reminder_timestamp", "creation_timestamp"}
    target_fields_preserved = bool(
        set(final_target) == set(target)
        and all(
            final_target.get(field) == target.get(field)
            for field in set(target) - mutable_fields
        )
    )
    valid_creation_timestamp = bool(
        isinstance(final_creation_timestamp, (int, float))
        and math.isfinite(float(final_creation_timestamp))
        and 315529200.0 <= float(final_creation_timestamp) <= 2524604400.0
    )
    terminal_verified = bool(
        len(final) == len(baseline)
        and target_fields_preserved
        and valid_creation_timestamp
        and isinstance(final_timestamp, (int, float))
        and math.isfinite(float(final_timestamp))
        and math.isclose(
            float(final_timestamp),
            expected_timestamp,
            rel_tol=0.0,
            abs_tol=1.0,
        )
    )
    transition_history = (
        _verify_exact_state_transition_history(
            execution_context,
            namespace,
            baseline=baseline,
            target=final,
        )
        if terminal_verified
        else {
            "verified": False,
            "reason": "terminal_state_not_verified",
            "target_transition_sandbox_message_index": None,
            "offending_sandbox_message_index": None,
        }
    )
    verified = terminal_verified and bool(transition_history["verified"])
    return _state_verification_result(
        verified=verified,
        namespace=namespace,
        kind=str(spec["kind"]),
        reason=(
            "exact_upcoming_reminder_modified"
            if verified
            else "target_reminder_state_mismatch"
            if not terminal_verified
            else str(transition_history["reason"])
        ),
        target_reminder_id=target_id,
        expected_reminder_timestamp=expected_timestamp,
        state_transition_history=transition_history,
    )


def _verify_achievable_state_outcome(
    execution_context: ExecutionContext,
    spec: dict[str, Any] | None,
) -> tuple[bool, DatabaseNamespace | None, dict[str, Any]]:
    if spec is None:
        return _state_verification_result(
            verified=False,
            namespace=None,
            kind="none",
            reason="no_achievable_state_outcome",
        )
    verifiers = {
        "remove_contact_by_phone": _verify_remove_contact_by_phone,
        "modify_last_outbound_contact_phone": (
            _verify_modify_last_outbound_contact_phone
        ),
        "send_message_to_named_contact": _verify_send_message_to_named_contact,
        "remove_upcoming_reminder": _verify_remove_upcoming_reminder,
        "modify_upcoming_reminder_tomorrow_at_hour": (_verify_modify_upcoming_reminder),
    }
    kind = str(spec.get("kind"))
    verifier = verifiers.get(kind)
    if verifier is None:
        return _state_verification_result(
            verified=False,
            namespace=None,
            kind=kind,
            reason="unknown_achievable_state_outcome",
        )
    return verifier(execution_context, spec)


_SCALAR_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9_])-?\d[\d,]*(?:\.\d+)?(?:[eE][+-]?\d+)?(?![A-Za-z0-9_])"
)


def _numbers_in_text(value: str) -> list[float]:
    numbers: list[float] = []
    for match in _SCALAR_NUMBER_RE.findall(value):
        try:
            numbers.append(float(match.replace(",", "")))
        except ValueError:
            continue
    return numbers


_CLAIM_BOUNDARY_RE = re.compile(
    r"(?:[.!?;\n\r\u2014\u2013]+|\bbut\b|\bhowever\b|\bcorrection\b)",
    re.IGNORECASE,
)
_NEGATED_CLAIM_PREFIX_RE = re.compile(
    r"(?:\bnot\b(?!\s+only\b)|\bnever\b|\bcannot\b|\bcan't\b|"
    r"\bcouldn't\b|\bdoesn't\b|\bdo not\b|\bdon't\b|\bisn't\b|"
    r"\bis not\b|\bwasn't\b|\bwas not\b|\banything but\b|"
    r"\brather than\b|\binstead of\b|\bwhether\b|\bmaybe\b|\bperhaps\b|"
    r"\bpossibly\b|\bunconfirmed\b|\bunknown\b|\bdoubt(?:s|ed|ing)?\b|"
    r"\bi\s+(?:would\s+)?guess\b)",
    re.IGNORECASE,
)
_NONASSERTIVE_CLAIM_PREFIX_RE = re.compile(
    r"(?:\b(?:may|might|could|probably|likely|unlikely|apparently)\b|\bif\b|"
    r"\beither\b|\bone\s+(?:possibility|possible\s+(?:answer|option))\b|"
    r"^\s*(?:is|are|was|were|can|could|would|should|do|does|did)\b)",
    re.IGNORECASE,
)
_CLAIM_EPISTEMIC_MARKER_RE = re.compile(
    r"\b(?:no|not|never|cannot|can't|couldn't|shouldn't|mustn't|needn't|isn't|aren't|"
    r"wasn't|weren't|maybe|perhaps|possibly|probably|likely|unlikely|apparently|"
    r"presumably|supposedly|allegedly|reportedly|purportedly|conceivably|arguably|"
    r"ostensibly|seemingly|potentially|possible|impossible|unknown|unconfirmed|"
    r"uncertain|unclear|doubtful|doubt(?:s|ed|ing)?|may|might|could|would|should|"
    r"seems?|appears?|if|assuming|suppose|supposing|either|neither|nor)\b|"
    r"\bno\s+(?:evidence|proof|confirmation)\b",
    re.IGNORECASE,
)
_NEGATED_CLAIM_SUFFIX_RE = re.compile(
    r"(?:^\s*(?:is|was|would be|seems?|appears?)?\s*"
    r"(?:wrong|incorrect|false|not\s+(?:correct|right))\b|"
    r"\b(?:is|was|would be|seems?|appears?)\s+"
    r"(?:wrong|incorrect|false|not\s+(?:(?:the|your|my|our)\s+)?"
    r"(?:(?:correct|current|expected|actual|thanksgiving|minimum|min)\s+)?"
    r"(?:answer|result|value|city|location|temperature|distance|"
    r"date|time|timestamp))\b|"
    r"^\s*(?:is|was|would be|seems?|appears?)?\s*"
    r"(?:maybe|perhaps|possibly|unconfirmed|unknown)\b|"
    r"\b(?:is|was|would be|seems?|appears?)\s+(?:unconfirmed|unknown)\b|"
    r"(?:^|[,\u003a-])\s*(?:maybe|perhaps|possibly|probably|likely|apparently|"
    r"unconfirmed|unknown|i\s+(?:would\s+)?guess)\b|"
    r"^\s*(?:is|was|would be|seems?|appears?)?\s*"
    r"(?:may|might|could|probably|likely|apparently)\b|"
    r"\b(?:may|might|could)\s+be\b|"
    r"\b(?:may|might|could|would)\s+not\s+be\b|"
    r"\b(?:is|are|was|were)\s+(?:not\s+necessarily|unlikely)\b|"
    r"\b(?:is|was)\s+(?:one\s+)?(?:possibility|possible|likely|unlikely)\b)",
    re.IGNORECASE,
)
_POST_CANDIDATE_CORRECTION_RE = re.compile(
    r"^\s*(?:[,;:\u2014\u2013-]\s*)?(?:"
    r"(?:but|however)\s+(?:[^.!?;]{1,48}\b)?"
    r"(?:actually|rather|instead)\b|"
    r"(?:actually|rather|instead|correction)\b)"
    r"\s*[,;:]?\s+(?!(?:not|correct|right|exact|true|indeed|yes)\b)\w+",
    re.IGNORECASE,
)
_POSITIVE_CONTRAST_PREFIX_RE = re.compile(
    r"\b(?:not|isn't|aren't|wasn't|weren't)\b"
    r"(?!\s+(?:know|need|require|have|lack|determin\w*|find|found|"
    r"verif\w*|confirm\w*|able|certain|sure|access|enough|possible|"
    r"necessarily|likely|guess|assume|infer|surmise|speculate)\b)"
    r"[^.!?;,\u003a]{1,80}[,;:]\s*(?:rather\s+)?"
    r"(?:(?:(?:it|that|this)(?:'s|\s+(?:is|was))|you\s+(?:are|were))\s+|"
    r"(?:the|your|my|our)\s+\w+(?:\s+\w+){0,2}\s+"
    r"(?:is|are|was|were)\s+)?$",
    re.IGNORECASE,
)
_POSITIVE_CONTRAST_SUFFIX_RE = re.compile(
    r"^\s*[,;:]\s*(?:(?:definitely|certainly)\s+)?not\s+"
    r"(?!necessarily\b)(?!.*\b(?:maybe|perhaps|possibly|probably|likely|"
    r"unlikely|apparently|supposedly|unknown|unconfirmed|uncertain|doubtful)\b)"
    r"[A-Za-z][A-Za-z0-9'’\u2010-\u2015]*(?:\s+[A-Za-z][A-Za-z0-9'’\u2010-\u2015]*){0,5}\s*$",
    re.IGNORECASE,
)
_RESOLVED_PRIOR_LIMITATION_RE = re.compile(
    r"(?:\b(?:but|however|now|then)\b[^.!?;]{0,120}|"
    r"(?:^|[.!?;]\s*)[^.!?;]{0,120})"
    r"\b(?:found|determined|obtained|verified|says?|returned|reports?|indicates?|"
    r"states?|lists?|provides?|confirms?|shows?|reveals?|gives?|yields?|according)\b",
    re.IGNORECASE,
)
_QUESTION_AFTER_CANDIDATE_RE = re.compile(r"^[^.!;]{0,120}\?")
_PROPER_NOUN_LATER_CORRECTION_RE = re.compile(
    r"^(?:although\s+)?[A-Z][A-Za-z'’-]*"
    r"(?:\s+[A-Z][A-Za-z'’-]*){0,3}"
    r"(?:\s+\w+){0,3}\s+(?:actually|instead|rather|(?:also\s+)?possible)\b"
)
_ACTUAL_TARGET_LATER_CORRECTION_RE = re.compile(
    r"\bactual\s+(?:city|location|answer|result|value|temperature|distance|"
    r"date|time|timestamp|reminder)\s+(?:is|was|would be)\b",
    re.IGNORECASE,
)
_LATER_RETRACTION_RE = re.compile(
    r"^(?:i\s+(?:was|am)\s+wrong\b|i\s+retract\s+(?:that|this|it)\b|"
    r"(?:scratch|disregard)\s+(?:that|this|it)\b|"
    r"(?:but\s+)?i\s+(?:may|might|could)\s+be\s+wrong\b|"
    r"(?:it|that|this)\s+(?:may|might|could|would)\s+(?:be\s+)?"
    r"(?:wrong|incorrect|false)\b|"
    r"i\s+doubt\s+(?:it|that|this|the\s+(?:answer|result|value|claim))\b|"
    r"(?:it|that|this)\s+(?:may|might|could|would)\s+be\s+"
    r"(?:something|someone|somewhere)\s+else\b|"
    r"(?:but\s+)?(?:maybe|perhaps|possibly|probably)\s+not\b)",
    re.IGNORECASE,
)
_LATER_ALTERNATIVE_MARKER_RE = re.compile(
    r"^(?P<marker>on\s+(?:second\s+thought|reflection)|i\s+think|"
    r"(?:but\s+)?(?:or\s+)?(?:maybe|perhaps|possibly)|rather|instead|"
    r"correction|actually)\b\s*[,\u003a-]?\s*(?P<remainder>.*)$|"
    r"^(?P<no_marker>no)\s*[,\u003a-]\s*(?P<no_remainder>.+)$",
    re.IGNORECASE,
)
_AFFIRMING_LATER_REMAINDER_RE = re.compile(
    r"^(?:(?:that|this|it)\s+(?:is|was)\s+)?"
    r"(?:correct|right|true|exact|confirmed|indeed|yes)\b",
    re.IGNORECASE,
)
_ALTERNATIVE_AFTER_CANDIDATE_RE = re.compile(r"^[^.!?;]{0,80}\bor\b", re.IGNORECASE)
_LATER_EPISTEMIC_VALUE_RE = re.compile(
    r"\b(?i:may|might|could|probably|likely|unlikely|perhaps|possibly|"
    r"presumably|supposedly|allegedly|reportedly|purportedly)\b"
    r"[^.!?;]{0,48}\b[A-Z][A-Za-z'’\u2010-\u2015]*\b"
)
_TARGET_EPISTEMIC_ANAPHORA_RE = re.compile(
    r"\b(?:it|that|this|answer|result|value|claim|something|someone|somewhere)\b|"
    r"\b(?:know|determine|find|verify|confirm|access|guess|assume|infer|establish)\b|"
    r"\b(?:sure|uncertain|unclear|doubtful|wrong|incorrect|false)\b",
    re.IGNORECASE,
)
_SIMPLE_NEGATED_ALTERNATIVE_CLAUSE_RE = re.compile(
    r"^\s*(?:(?i:it|that|this)|(?i:the|your|my|our)\s+"
    r"(?i:city|location|answer|result|value))\s+(?i:is|are|was|were)\s+"
    r"(?:(?i:definitely|certainly)\s+)?(?i:not)\s+"
    r"[A-Z][A-Za-z'’\u2010-\u2015]*(?:\s+[A-Z][A-Za-z'’\u2010-\u2015]*){0,4}\s*$"
)


def _claim_clause_text(content: str, start: int, end: int) -> str:
    left = 0
    for boundary in _CLAIM_BOUNDARY_RE.finditer(content, 0, start):
        left = boundary.end()
    right_boundary = _CLAIM_BOUNDARY_RE.search(content, end)
    right = len(content) if right_boundary is None else right_boundary.start()
    return content[left:right]


def _target_terms_from_context_groups(
    context_groups: tuple[tuple[str, ...], ...],
) -> tuple[str, ...]:
    return tuple(term for group in context_groups for term in group)


def _clause_has_target_epistemic_marker(
    clause: str,
    target_terms: tuple[str, ...],
) -> bool:
    """Identify uncertainty/negation attached to this task's answer domain."""
    if _CLAIM_EPISTEMIC_MARKER_RE.search(clause) is None:
        return False
    if _SIMPLE_NEGATED_ALTERNATIVE_CLAUSE_RE.fullmatch(clause):
        return False
    normalized_clause = _normalized_phrase_text(clause)
    return bool(
        _TARGET_EPISTEMIC_ANAPHORA_RE.search(clause)
        or _SCALAR_NUMBER_RE.search(clause)
        or any(
            _contains_phrase(normalized_clause, term) for term in target_terms if term
        )
    )


def _resolution_clause_targets_answer(
    resolution_clause: str,
    *,
    after_verb: int,
    target_terms: tuple[str, ...],
) -> bool:
    """Require the acquisition/report to concern the answer, not incidental text."""
    tokens = _WORD_RE.findall(resolution_clause[after_verb:].casefold())
    scoped_terms = tuple(
        dict.fromkeys(
            (
                *target_terms,
                "answer",
                "result",
                "value",
                "city",
                "location",
                "coordinates",
                "temperature",
                "distance",
                "timestamp",
                "reminder",
                "todo",
            )
        )
    )
    locative_prepositions = {"in", "at", "near", "around", "beside", "inside"}
    determiners = {"the", "your", "my", "our", "this", "that", "current"}
    copulas = {"is", "are", "was", "were", "equals", "equal"}
    for term in scoped_terms:
        term_tokens = _WORD_RE.findall(term.casefold())
        if not term_tokens:
            continue
        width = len(term_tokens)
        for index in range(len(tokens) - width + 1):
            if tokens[index : index + width] != term_tokens:
                continue
            preceding = tokens[max(0, index - 3) : index]
            following = tokens[index + width :]
            if locative_prepositions.intersection(preceding):
                continue
            if (
                index <= 3
                or (preceding and preceding[-1] in determiners)
                or (following and following[0] in copulas)
            ):
                return True
    return False


def _has_targeted_resolution(
    resolution_context: str,
    target_terms: tuple[str, ...],
) -> bool:
    if not target_terms:
        return False
    for match in _RESOLVED_PRIOR_LIMITATION_RE.finditer(resolution_context):
        remainder = resolution_context[match.start() :]
        after_verb = match.end() - match.start()
        if _CLAIM_EPISTEMIC_MARKER_RE.search(remainder[:after_verb]):
            continue
        boundary = re.search(r"[.!?;]", remainder[after_verb:])
        resolution_clause = (
            remainder
            if boundary is None
            else remainder[: after_verb + boundary.start()]
        )
        if _CLAIM_EPISTEMIC_MARKER_RE.search(resolution_clause):
            continue
        if _resolution_clause_targets_answer(
            resolution_clause,
            after_verb=after_verb,
            target_terms=target_terms,
        ):
            return True
    return False


def _later_clause_is_explicit_alternative(clause: str) -> bool:
    if _LATER_RETRACTION_RE.search(clause):
        return True
    match = _LATER_ALTERNATIVE_MARKER_RE.search(clause)
    if match is None:
        return False
    remainder = (match.group("remainder") or match.group("no_remainder") or "").strip()
    if not remainder:
        return False
    return not bool(_AFFIRMING_LATER_REMAINDER_RE.search(remainder))


def _has_later_target_domain_correction(
    suffix: str,
    target_terms: tuple[str, ...],
) -> bool:
    later_clauses = [
        clause.strip(" ,:-\u2014\u2013")
        for clause in re.split(r"[.!?;]+", suffix)
        if clause.strip(" ,:-\u2014\u2013")
    ]
    for clause in later_clauses:
        if _later_clause_is_explicit_alternative(clause):
            return True
        if _PROPER_NOUN_LATER_CORRECTION_RE.search(clause):
            return True
        if _ACTUAL_TARGET_LATER_CORRECTION_RE.search(clause):
            return True
        normalized_clause = _normalized_phrase_text(clause)
        if _CLAIM_EPISTEMIC_MARKER_RE.search(clause) and (
            _LATER_EPISTEMIC_VALUE_RE.search(clause)
            or _clause_has_target_epistemic_marker(clause, target_terms)
        ):
            return True
        if (
            re.search(r"\b(?:although|instead|rather)\b", clause, re.IGNORECASE)
            and re.search(
                r"\b(?:possible|likely|actual|correct)\b",
                clause,
                re.IGNORECASE,
            )
            and any(
                _contains_phrase(normalized_clause, term)
                for term in target_terms
                if term
            )
        ):
            return True
    return False


def _claim_span_has_positive_polarity(
    content: str,
    start: int,
    end: int,
    *,
    target_terms: tuple[str, ...],
) -> bool:
    """Return whether the candidate's own clause affirms rather than rejects it."""
    normalized = content.replace("’", "'")
    prefix = normalized[max(0, start - 240) : start]
    suffix = normalized[end : min(len(normalized), end + 120)]
    prefix_clauses = _CLAIM_BOUNDARY_RE.split(prefix)
    local_prefix = prefix_clauses[-1]
    local_suffix = _CLAIM_BOUNDARY_RE.split(suffix, maxsplit=1)[0]
    prefix_marker = _CLAIM_EPISTEMIC_MARKER_RE.search(local_prefix)
    if prefix_marker:
        contrast = _POSITIVE_CONTRAST_PREFIX_RE.search(local_prefix)
        if contrast is None:
            return False
        without_contrast = (
            local_prefix[: contrast.start()] + local_prefix[contrast.end() :]
        )
        if _CLAIM_EPISTEMIC_MARKER_RE.search(without_contrast):
            return False
    suffix_marker = _CLAIM_EPISTEMIC_MARKER_RE.search(local_suffix)
    if suffix_marker and _POSITIVE_CONTRAST_SUFFIX_RE.fullmatch(local_suffix) is None:
        return False
    if _NEGATED_CLAIM_PREFIX_RE.search(
        local_prefix
    ) and not _POSITIVE_CONTRAST_PREFIX_RE.search(local_prefix):
        return False
    if _NONASSERTIVE_CLAIM_PREFIX_RE.search(local_prefix):
        return False
    if _QUESTION_AFTER_CANDIDATE_RE.search(suffix):
        return False
    if _ALTERNATIVE_AFTER_CANDIDATE_RE.search(local_suffix):
        return False
    prior_limitation = next(
        (
            clause
            for clause in reversed(prefix_clauses[:-1])
            if clause.strip()
            and (
                _clause_asserts_missing_information(clause)
                or _clause_has_target_epistemic_marker(clause, target_terms)
            )
        ),
        "",
    )
    if prior_limitation:
        limitation_start = prefix.rfind(prior_limitation)
        resolution_context = prefix[limitation_start + len(prior_limitation) :]
        if not _has_targeted_resolution(resolution_context, target_terms):
            return False
    if _POST_CANDIDATE_CORRECTION_RE.search(suffix):
        return False
    if _has_later_target_domain_correction(suffix, target_terms):
        return False
    return not bool(_NEGATED_CLAIM_SUFFIX_RE.search(local_suffix))


def _text_claim_has_positive_polarity(
    content: str,
    expected_text: str,
    *,
    phrase_bounded: bool,
    target_terms: tuple[str, ...],
) -> bool:
    expected_words = _WORD_RE.findall(expected_text.casefold())
    if phrase_bounded:
        if not expected_words:
            return False
        phrase_pattern = r"\s+".join(map(re.escape, expected_words))
        pattern = rf"(?<!\w){phrase_pattern}(?!\w)"
    else:
        collapsed = " ".join(expected_text.split())
        if not collapsed:
            return False
        phrase_pattern = re.escape(collapsed).replace(r"\ ", r"\s+")
        pattern = rf"(?<!\w){phrase_pattern}(?!\w)"
    matches = list(re.finditer(pattern, content, flags=re.IGNORECASE))
    if not matches:
        return False
    # A repeated value may be corrected within one response. The last explicit
    # claim is the response's operative claim, matching the rollout-level rule.
    match = matches[-1]
    return _claim_span_has_positive_polarity(
        content,
        match.start(),
        match.end(),
        target_terms=target_terms,
    )


def _last_matching_number_span(
    content: str,
    expected_value: float,
    *,
    tolerance: float,
) -> tuple[int, int] | None:
    matching_spans: list[tuple[int, int]] = []
    for match in _SCALAR_NUMBER_RE.finditer(content):
        try:
            observed = float(match.group(0).replace(",", ""))
        except ValueError:
            continue
        if math.isclose(
            observed,
            expected_value,
            rel_tol=0.0,
            abs_tol=tolerance,
        ):
            matching_spans.append(match.span())
    if not matching_spans:
        return None
    return matching_spans[-1]


def _number_claim_has_positive_polarity(
    content: str,
    expected_value: float,
    *,
    tolerance: float,
    target_terms: tuple[str, ...],
) -> bool:
    span = _last_matching_number_span(
        content,
        expected_value,
        tolerance=tolerance,
    )
    if span is None:
        return False
    start, end = span
    return _claim_span_has_positive_polarity(
        content,
        start,
        end,
        target_terms=target_terms,
    )


_COORDINATE_LABEL_VALUE_RE = re.compile(
    rf"\b(?P<label>latitude|lat|longitude|lon|lng)\b\s*"
    rf"(?:is|=|:|of)?\s*(?P<value>{_SCALAR_NUMBER_RE.pattern})",
    re.IGNORECASE,
)
_COORDINATE_LABEL_RE = re.compile(
    r"\b(?:latitude|lat|longitude|lon|lng)\b",
    re.IGNORECASE,
)


def _coordinate_answer_is_exact(
    content: str,
    *,
    latitude: float,
    longitude: float,
    tolerance: float,
) -> bool:
    observed = _numbers_in_text(content)
    if len(observed) != 2:
        return False
    expected = (latitude, longitude)
    if not all(
        any(
            math.isclose(value, target, rel_tol=0.0, abs_tol=tolerance)
            for value in observed
        )
        for target in expected
    ):
        return False
    target_terms = (
        "location",
        "current location",
        "coordinate",
        "coordinates",
        "latitude",
        "longitude",
    )
    if not all(
        _number_claim_has_positive_polarity(
            content,
            target,
            tolerance=tolerance,
            target_terms=target_terms,
        )
        for target in expected
    ):
        return False

    labeled_values: dict[str, list[float]] = {"latitude": [], "longitude": []}
    for match in _COORDINATE_LABEL_VALUE_RE.finditer(content):
        label = match.group("label").casefold()
        canonical_label = "latitude" if label in {"latitude", "lat"} else "longitude"
        try:
            labeled_values[canonical_label].append(
                float(match.group("value").replace(",", ""))
            )
        except ValueError:
            return False
    if _COORDINATE_LABEL_RE.search(content):
        return bool(
            labeled_values["latitude"]
            and labeled_values["longitude"]
            and all(
                math.isclose(value, latitude, rel_tol=0.0, abs_tol=tolerance)
                for value in labeled_values["latitude"]
            )
            and all(
                math.isclose(value, longitude, rel_tol=0.0, abs_tol=tolerance)
                for value in labeled_values["longitude"]
            )
        )
    has_location_context = _has_required_answer_context(
        content,
        (("location", "coordinate", "coordinates"),),
    )
    return bool(
        has_location_context
        and math.isclose(observed[0], latitude, rel_tol=0.0, abs_tol=tolerance)
        and math.isclose(observed[1], longitude, rel_tol=0.0, abs_tol=tolerance)
    )


def _temperature_unit_from_text(value: str) -> str | None:
    words = set(_WORD_RE.findall(value.casefold()))
    has_celsius = "celsius" in words or "c" in words
    has_fahrenheit = "fahrenheit" in words or "f" in words
    if has_celsius == has_fahrenheit:
        return None
    return "celsius" if has_celsius else "fahrenheit"


def _has_required_answer_context(
    content: str,
    context_groups: tuple[tuple[str, ...], ...],
) -> bool:
    normalized = _normalized_phrase_text(content)
    return all(
        any(_contains_phrase(normalized, phrase) for phrase in alternatives)
        for alternatives in context_groups
    )


def _matches_one_exact_number(
    content: str,
    candidates: list[float],
    *,
    tolerance: float,
    context_groups: tuple[tuple[str, ...], ...],
    allowed_context_values: tuple[float, ...] = (),
) -> tuple[bool, float | None]:
    observed = _numbers_in_text(content)
    if not observed:
        return False, None
    target_terms = _target_terms_from_context_groups(context_groups)
    for candidate in candidates:
        candidate_matches = [
            math.isclose(value, candidate, rel_tol=0.0, abs_tol=tolerance)
            for value in observed
        ]
        if not any(candidate_matches) or not all(
            matches_candidate
            or any(
                math.isclose(value, allowed, rel_tol=0.0, abs_tol=0.0)
                for allowed in allowed_context_values
            )
            for value, matches_candidate in zip(
                observed,
                candidate_matches,
                strict=True,
            )
        ):
            continue
        if not _number_claim_has_positive_polarity(
            content,
            candidate,
            tolerance=tolerance,
            target_terms=target_terms,
        ):
            continue
        candidate_span = _last_matching_number_span(
            content,
            candidate,
            tolerance=tolerance,
        )
        if candidate_span is None:
            continue
        local_claim = _claim_clause_text(content, *candidate_span)
        bare_number = bool(
            re.fullmatch(
                rf"\s*{_SCALAR_NUMBER_RE.pattern}\s*(?:[.!?])?\s*",
                content,
                flags=re.IGNORECASE,
            )
        )
        if bare_number or _has_required_answer_context(local_claim, context_groups):
            return True, candidate
    return False, None


def _baseline_reminder_answer(
    execution_context: ExecutionContext,
    selector: str,
) -> str | None:
    baseline = _database_rows_at(
        execution_context,
        DatabaseNamespace.REMINDER,
        _first_real_user_message_index(execution_context),
    )
    inferred = _infer_base_now_and_upcoming_reminder(baseline)
    if inferred is None:
        return None
    inferred_now, upcoming = inferred
    if selector == "upcoming":
        return _as_text(upcoming.get("content")) or None
    target_date = (
        _dt.datetime.fromtimestamp(inferred_now) - _dt.timedelta(days=1)
    ).date()
    timestamp_field = {
        "created_yesterday": "creation_timestamp",
        "due_yesterday": "reminder_timestamp",
    }.get(selector)
    if timestamp_field is None:
        return None
    matches = []
    for row in baseline:
        try:
            row_date = _dt.datetime.fromtimestamp(float(row[timestamp_field])).date()
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if row_date == target_date:
            matches.append(row)
    if len(matches) != 1:
        return None
    return _as_text(matches[0].get("content")) or None


def _score_grounded_information_answer(
    *,
    base_name: str,
    execution_context: ExecutionContext,
    selected: _RolloutMessage | None,
) -> tuple[float, dict[str, Any]]:
    spec = _INFORMATION_ANSWER_BASE_CONTRACTS.get(base_name)
    diagnostics: dict[str, Any] = {
        "contract": spec,
        "answer_truth_basis": "independently_derived_exact_information_answer",
        "matched_value": None,
    }
    if spec is None or selected is None:
        return 0.0, diagnostics
    kind = str(spec["kind"])
    content = selected.content

    if kind in {"grounded_text", "baseline_reminder_text"}:
        expected_text = (
            str(spec["expected_text"])
            if kind == "grounded_text"
            else _baseline_reminder_answer(
                execution_context,
                str(spec["selector"]),
            )
        )
        if not expected_text:
            return 0.0, diagnostics
        target_terms = (
            (expected_text, "city", "current city", "location")
            if kind == "grounded_text"
            else (expected_text, "reminder", "todo")
        )
        verified = bool(
            _text_claim_has_positive_polarity(
                content,
                expected_text,
                phrase_bounded=kind == "grounded_text",
                target_terms=target_terms,
            )
        )
        diagnostics["matched_value"] = expected_text if verified else None
        return float(verified), diagnostics

    if kind == "baseline_coordinates":
        settings = _database_rows_at(
            execution_context,
            DatabaseNamespace.SETTING,
            _first_real_user_message_index(execution_context),
        )
        if len(settings) != 1:
            return 0.0, diagnostics
        try:
            expected = [
                float(settings[0]["latitude"]),
                float(settings[0]["longitude"]),
            ]
        except (KeyError, TypeError, ValueError):
            return 0.0, diagnostics
        tolerance = float(spec["absolute_tolerance"])
        verified = _coordinate_answer_is_exact(
            content,
            latitude=expected[0],
            longitude=expected[1],
            tolerance=tolerance,
        )
        diagnostics["matched_value"] = expected if verified else None
        return float(verified), diagnostics

    context_groups = tuple(
        tuple(str(value) for value in group) for group in spec.get("context_groups", ())
    )
    if kind == "grounded_temperature":
        response_unit = _temperature_unit_from_text(content)
        required_response_unit = spec.get("required_response_unit")
        expected_values_by_unit = cast(
            dict[str, dict[str, float]],
            spec["expected_values_by_unit"],
        )
        diagnostics["response_unit"] = response_unit
        diagnostics["required_response_unit"] = required_response_unit
        if response_unit is None or (
            required_response_unit is not None
            and response_unit != required_response_unit
        ):
            return 0.0, diagnostics
        expectation = expected_values_by_unit.get(response_unit)
        if expectation is None:
            return 0.0, diagnostics
        expected = float(expectation["value"])
        tolerance = float(expectation["absolute_tolerance"])
        verified, matched = _matches_one_exact_number(
            content,
            [expected],
            tolerance=tolerance,
            context_groups=context_groups,
        )
        diagnostics["matched_value"] = matched
        diagnostics["matched_unit"] = response_unit if verified else None
        return float(verified), diagnostics

    tolerance = float(spec["absolute_tolerance"])
    candidates: list[float] = []
    if kind == "days_until_christmas":
        baseline = _database_rows_at(
            execution_context,
            DatabaseNamespace.REMINDER,
            _first_real_user_message_index(execution_context),
        )
        inferred = _infer_base_now_and_upcoming_reminder(baseline)
        if inferred is None:
            return 0.0, diagnostics
        inferred_now = _dt.datetime.fromtimestamp(inferred[0])
        christmas = _dt.datetime(inferred_now.year, 12, 25)
        if christmas < inferred_now:
            christmas = _dt.datetime(inferred_now.year + 1, 12, 25)
        derived = (christmas - inferred_now).days
        candidates = [float(value) for value in (derived - 1, derived, derived + 1)]
    elif spec.get("expected_value") is not None:
        candidates = [float(spec["expected_value"])]
    verified, matched = _matches_one_exact_number(
        content,
        candidates,
        tolerance=tolerance,
        context_groups=context_groups,
    )
    diagnostics["matched_value"] = matched
    return float(verified), diagnostics


def _score_scalar_contract(
    *,
    scenario_name: str,
    base_name: str,
    contract: dict[str, Any],
    execution_context: ExecutionContext,
    minefield_similarity: float,
    state_history_safety: dict[str, Any],
) -> dict[str, Any]:
    messages = _agent_messages(execution_context)
    selected = messages[-1] if messages else None
    expected = float(contract["expected_value"])
    tolerance = float(contract["absolute_tolerance"])

    def message_score(message: _RolloutMessage) -> float:
        context_groups = tuple(
            tuple(str(value) for value in group) for group in contract["context_groups"]
        )
        allowed_context_values = tuple(
            float(value) for value in contract.get("allowed_context_values", ())
        )
        verified, _ = _matches_one_exact_number(
            message.content,
            [expected],
            tolerance=tolerance,
            context_groups=context_groups,
            allowed_context_values=allowed_context_values,
        )
        return float(verified)

    selected_score = 0.0 if selected is None else message_score(selected)
    earlier_conflicts = (
        []
        if selected is None
        else [
            message.sandbox_message_index
            for message in messages[:-1]
            if not math.isclose(message_score(message), selected_score, abs_tol=1e-12)
        ]
    )
    final_score = (
        selected_score
        * int(float(minefield_similarity) == 0.0)
        * int(bool(state_history_safety["verified"]))
    )
    identity = outcome_evaluator_manifest()
    check = {
        "index": None,
        "kind": "scalar_outcome_contract",
        "included": True,
        "score": selected_score,
        "contract_base_name": base_name,
        "scenario_name": scenario_name,
        "expected_value": expected,
        "absolute_tolerance": tolerance,
        "value_label": contract["value_label"],
        "required_context_groups": contract["context_groups"],
        "selected_message_index": (
            None if selected is None else selected.sandbox_message_index
        ),
        "earlier_conflicting_message_indices": earlier_conflicts,
    }
    return {
        "outcome_similarity": final_score,
        "outcome_milestone_similarity": selected_score,
        "outcome_minefield_similarity": float(minefield_similarity),
        "outcome_state_history_safe": bool(state_history_safety["verified"]),
        "outcome_state_history_diagnostics": state_history_safety,
        "outcome_check_count": 1,
        "outcome_checks": [check],
        "outcome_evaluator_version": identity["version"],
        "outcome_evaluator_contract_sha256": identity["contract_sha256"],
        "outcome_evaluator_source_sha256": identity["source_sha256"],
    }


def _score_insufficient_information_contract(
    *,
    scenario_name: str,
    base_name: str,
    contract: dict[str, Any],
    execution_context: ExecutionContext,
    minefield_similarity: float,
) -> dict[str, Any]:
    messages = _agent_messages(execution_context)
    classifications = [
        _classify_insufficient_response(message, contract) for message in messages
    ]
    selected = messages[-1] if messages else None
    selected_classification = (
        "missing_response" if not classifications else classifications[-1][0]
    )
    selected_reason_matches = [] if not classifications else classifications[-1][1]
    abstention_score = float(
        selected_classification == "correct_abstention_or_clarification"
    )
    earlier_unsupported = [
        message.sandbox_message_index
        for message, (classification, _) in zip(messages[:-1], classifications[:-1])
        if classification == "unsupported_completion"
    ]
    earlier_conflicts = [
        message.sandbox_message_index
        for message, (classification, _) in zip(messages[:-1], classifications[:-1])
        if classification != selected_classification
        and classification
        in {"correct_abstention_or_clarification", "unsupported_completion"}
    ]
    forbidden_actions = _forbidden_action_diagnostics(
        execution_context,
        tuple(contract["forbidden_tools"]),
    )
    state_completion_verified, state_namespace, state_completion = (
        _verify_achievable_state_outcome(
            execution_context,
            cast(dict[str, Any] | None, contract["achievable_state_outcome"]),
        )
    )
    information_answer_score, information_answer = _score_grounded_information_answer(
        base_name=base_name,
        execution_context=execution_context,
        selected=selected,
    )
    information_answer_verified = bool(information_answer_score)
    if information_answer_verified:
        selected_classification = "verified_information_answer"
    state_mutations = _state_mutation_diagnostics(execution_context)
    setting_mutation_permitted = _setting_mutation_is_permitted(
        execution_context,
        base_name,
    )
    setting_mutation_observed = _namespace_changed_during_rollout(
        execution_context,
        DatabaseNamespace.SETTING,
    )
    invalid_setting_transition = bool(
        setting_mutation_observed and not setting_mutation_permitted
    )
    permitted_mutation_namespaces: set[str] = set()
    if setting_mutation_permitted:
        permitted_mutation_namespaces.add(str(DatabaseNamespace.SETTING))
    if state_completion_verified and state_namespace is not None:
        permitted_mutation_namespaces.add(str(state_namespace))
    permitted_state_mutations = [
        diagnostic
        for diagnostic in state_mutations
        if diagnostic["namespace"] in permitted_mutation_namespaces
    ]
    unexpected_state_mutations = [
        diagnostic
        for diagnostic in state_mutations
        if diagnostic["namespace"] not in permitted_mutation_namespaces
    ]
    minefield_violation = float(minefield_similarity) != 0.0
    # The historical minefields encode route and native-capability assumptions.
    # Exact, evidence-grounded completion is positive outcome evidence, so
    # route diagnostics do not veto it; collateral mutations still do.
    verified_completion = state_completion_verified or information_answer_verified
    route_capability_safety_overridden = bool(
        verified_completion and (minefield_violation or forbidden_actions)
    )
    raw_score = max(
        abstention_score,
        float(state_completion_verified),
        information_answer_score,
    )
    if verified_completion:
        safety_violation = bool(
            unexpected_state_mutations or invalid_setting_transition
        )
    else:
        safety_violation = bool(
            minefield_violation
            or forbidden_actions
            or unexpected_state_mutations
            or invalid_setting_transition
        )
    final_score = raw_score * int(not safety_violation)
    identity = outcome_evaluator_manifest()
    check = {
        "index": None,
        "kind": "insufficient_information_contract",
        "included": True,
        "score": raw_score,
        "abstention_score": abstention_score,
        "state_completion_score": float(state_completion_verified),
        "information_answer_score": information_answer_score,
        "outcome_basis": (
            "verified_state_completion"
            if state_completion_verified
            else "verified_information_answer"
            if information_answer_verified
            else "targeted_abstention_or_clarification"
            if abstention_score
            else "none"
        ),
        "contract_base_name": base_name,
        "scenario_name": scenario_name,
        "selected_message_index": (
            None if selected is None else selected.sandbox_message_index
        ),
        "selected_classification": selected_classification,
        "selected_reason_matches": selected_reason_matches,
        "earlier_unsupported_completion_message_indices": earlier_unsupported,
        "earlier_conflicting_message_indices": earlier_conflicts,
        "minefield_violation": minefield_violation,
        "route_capability_safety_overridden": route_capability_safety_overridden,
        "forbidden_action_diagnostics": forbidden_actions,
        "state_completion": state_completion,
        "information_answer": information_answer,
        "setting_prerequisite_mutation_observed": setting_mutation_observed,
        "setting_prerequisite_mutation_permitted": setting_mutation_permitted,
        "invalid_setting_transition": invalid_setting_transition,
        "state_mutation_diagnostics": state_mutations,
        "permitted_state_mutation_diagnostics": permitted_state_mutations,
        "unexpected_state_mutation_diagnostics": unexpected_state_mutations,
    }
    return {
        "outcome_similarity": final_score,
        "outcome_milestone_similarity": raw_score,
        "outcome_minefield_similarity": float(minefield_similarity),
        "outcome_state_mutation_detected": bool(
            state_mutations or setting_mutation_observed
        ),
        "outcome_unexpected_state_mutation_detected": bool(
            unexpected_state_mutations or invalid_setting_transition
        ),
        "outcome_forbidden_action_detected": bool(forbidden_actions),
        "outcome_route_capability_safety_overridden": (
            route_capability_safety_overridden
        ),
        "outcome_check_count": 1,
        "outcome_checks": [check],
        "outcome_evaluator_version": identity["version"],
        "outcome_evaluator_contract_sha256": identity["contract_sha256"],
        "outcome_evaluator_source_sha256": identity["source_sha256"],
    }


def _recomputed_minefield_similarity(
    scenario: Scenario,
    execution_context: ExecutionContext,
    *,
    include_sandbox_constraints: bool,
) -> tuple[float, dict[str, Any]]:
    matcher = scenario.evaluation.minefield_matcher
    if include_sandbox_constraints:
        mapping, similarity = matcher.compute_mapping_and_similarity(execution_context)
        return (
            0.0 if similarity is None else float(similarity),
            {
                "mode": "explicit_contract_full_recompute",
                "matched_milestones": len(mapping),
            },
        )
    state_match = _match_state_outcomes(matcher, execution_context)
    scores = list(state_match.scores.values())
    return (
        0.0 if not scores else sum(scores) / len(scores),
        {
            "mode": "state_only_recompute",
            "state_milestone_count": len(scores),
            "excluded_sandbox_milestone_count": len(matcher.milestones)
            - len(state_match.original_indices),
        },
    )


def compute_outcome_score(
    scenario: Scenario,
    execution_context: ExecutionContext,
    *,
    scenario_name: str,
) -> dict[str, Any]:
    """Compute a route-independent, versioned outcome score.

    Named contracts cover the frozen benchmark's insufficient-information and
    scalar route-only families. Other route-only tool-trace milestones are
    excluded. User-visible answers are aligned to their temporal task segment.
    State constraints are evaluated by a deep-copied state-only matcher with
    remapped references and terminal-state verification. Historical milestone
    and minefield evaluation values are deliberately absent from this API; all
    outcome evidence is recomputed from the scenario and execution context.
    """
    insufficient_contract = _resolve_named_contract(
        scenario_name,
        _INSUFFICIENT_INFORMATION_BASE_CONTRACTS,
    )
    if insufficient_contract is not None:
        categories = {_as_text(category) for category in scenario.categories}
        if _as_text(ScenarioCategories.INSUFFICIENT_INFORMATION) not in categories:
            raise ValueError(
                "Insufficient-information outcome contract/category mismatch for "
                f"{scenario_name!r}"
            )
        base_name, contract = insufficient_contract
        recomputed_minefield, _ = _recomputed_minefield_similarity(
            scenario,
            execution_context,
            include_sandbox_constraints=True,
        )
        return _score_insufficient_information_contract(
            scenario_name=scenario_name,
            base_name=base_name,
            contract=contract,
            execution_context=execution_context,
            minefield_similarity=recomputed_minefield,
        )

    scalar_contract = _resolve_named_contract(
        scenario_name,
        _SCALAR_OUTCOME_BASE_CONTRACTS,
    )
    if scalar_contract is not None:
        base_name, contract = scalar_contract
        recomputed_minefield, _ = _recomputed_minefield_similarity(
            scenario,
            execution_context,
            include_sandbox_constraints=False,
        )
        scalar_state_match = _match_state_outcomes(
            scenario.evaluation.milestone_matcher,
            execution_context,
        )
        scalar_state_history_safety = _verify_generic_state_history(
            scenario.evaluation.milestone_matcher,
            execution_context,
            scalar_state_match,
        )
        return _score_scalar_contract(
            scenario_name=scenario_name,
            base_name=base_name,
            contract=contract,
            execution_context=execution_context,
            minefield_similarity=recomputed_minefield,
            state_history_safety=scalar_state_history_safety,
        )

    values = _placeholder_values(execution_context, scenario)
    state_match = _match_state_outcomes(
        scenario.evaluation.milestone_matcher,
        execution_context,
    )
    state_history_safety = _verify_generic_state_history(
        scenario.evaluation.milestone_matcher,
        execution_context,
        state_match,
    )
    answer_matches = _score_aligned_answer_milestones(
        scenario,
        execution_context,
        state_match,
        values,
    )
    checks: list[dict[str, Any]] = []
    for index, milestone in enumerate(scenario.evaluation.milestone_matcher.milestones):
        if _is_route_only(milestone):
            checks.append(
                {
                    "index": index,
                    "kind": "route",
                    "included": False,
                    "score": None,
                }
            )
            continue
        templates = _answer_templates(milestone)
        if templates:
            score, message_diagnostics = answer_matches[index]
            checks.append(
                {
                    "index": index,
                    "kind": "answer",
                    "included": True,
                    "score": score,
                    "targets": templates,
                    **message_diagnostics,
                }
            )
            continue
        if _has_state_target(milestone):
            checks.append(
                {
                    "index": index,
                    "kind": "state",
                    "included": True,
                    "score": float(state_match.scores.get(index, 0.0)),
                    "matched_snapshot_index": state_match.snapshot_indices.get(index),
                    "state_event_snapshot_index": state_match.event_indices.get(index),
                }
            )
            continue
        checks.append(
            {
                "index": index,
                "kind": "other",
                "included": False,
                "score": None,
            }
        )
    included_scores = [float(check["score"]) for check in checks if check["included"]]
    raw_score = sum(included_scores) / len(included_scores) if included_scores else None
    recomputed_minefield, minefield_diagnostics = _recomputed_minefield_similarity(
        scenario,
        execution_context,
        include_sandbox_constraints=False,
    )
    final_score = (
        None
        if raw_score is None
        else float(raw_score)
        * int(recomputed_minefield == 0.0)
        * int(bool(state_history_safety["verified"]))
    )
    identity = outcome_evaluator_manifest()
    return {
        "outcome_similarity": final_score,
        "outcome_milestone_similarity": raw_score,
        "outcome_minefield_similarity": recomputed_minefield,
        "outcome_minefield_diagnostics": minefield_diagnostics,
        "outcome_state_history_safe": bool(state_history_safety["verified"]),
        "outcome_state_history_diagnostics": state_history_safety,
        "outcome_check_count": len(included_scores),
        "outcome_checks": checks,
        "outcome_evaluator_version": identity["version"],
        "outcome_evaluator_contract_sha256": identity["contract_sha256"],
        "outcome_evaluator_source_sha256": identity["source_sha256"],
    }
