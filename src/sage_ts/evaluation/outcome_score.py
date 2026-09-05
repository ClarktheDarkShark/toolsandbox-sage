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

OUTCOME_EVALUATOR_VERSION = "sage_outcome_contracts_v5"

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
        # Each group names an independently sufficient fact or capability that
        # blocks safe completion.  An agent need not enumerate every blocker
        # once it has identified one that, by itself, makes the task
        # under-specified or impossible.
        "reason_group_operator": "any",
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
# Canyon/North Rim current values are the route-independent union of the exact
# scenario-valid records in the pinned fixture.  Their independently converted
# Fahrenheit values are 26.06, 54.14, and 59.18.
_FROZEN_GOLDEN_GATE_DISTANCE_KM_RAW = 67.97730305839949
_FROZEN_GOLDEN_GATE_DISTANCE_KM_VALUES = (
    round(_FROZEN_GOLDEN_GATE_DISTANCE_KM_RAW, 2),
    round(_FROZEN_GOLDEN_GATE_DISTANCE_KM_RAW, 3),
    _FROZEN_GOLDEN_GATE_DISTANCE_KM_RAW,
)

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
        "kind": "frozen_golden_gate_distance",
        # The frozen location fixture resolves Golden Gate Bridge to
        # (37.8199109, -122.4785598).  Geodesic distance from the benchmark's
        # current location (37.334606, -122.009102) is 67.97730305839949 km,
        # which is 67.98 km at the response precision used by the benchmark.
        "raw_value": _FROZEN_GOLDEN_GATE_DISTANCE_KM_RAW,
        "accepted_values": _FROZEN_GOLDEN_GATE_DISTANCE_KM_VALUES,
        "context_groups": (
            ("golden gate",),
            ("bridge",),
            ("km", "kilometer", "kilometers"),
        ),
    },
    "find_distance_with_location_name_insufficient_information_alt": {
        "kind": "frozen_golden_gate_distance",
        "raw_value": _FROZEN_GOLDEN_GATE_DISTANCE_KM_RAW,
        "accepted_values": _FROZEN_GOLDEN_GATE_DISTANCE_KM_VALUES,
        "context_groups": (
            ("golden gate",),
            ("bridge",),
            ("km", "kilometer", "kilometers"),
        ),
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
        "dynamic_temperature_family": ("grand_canyon_current_temperature_fahrenheit"),
        "expected_values_by_unit": {
            "celsius": {
                "values": (-3.3, 12.3, 15.1),
                "absolute_tolerance": 0.01,
            },
            "fahrenheit": {
                "values": (26.06, 54.14, 59.18),
                "absolute_tolerance": 0.05,
            },
        },
        "context_groups": (("grand canyon",),),
    },
    "find_temperature_f_with_location_insufficient_information_alt": {
        "kind": "grounded_temperature",
        "required_response_unit": "fahrenheit",
        "dynamic_temperature_family": ("grand_canyon_current_temperature_fahrenheit"),
        "expected_values_by_unit": {
            "celsius": {
                "values": (-3.3, 12.3, 15.1),
                "absolute_tolerance": 0.01,
            },
            "fahrenheit": {
                "values": (26.06, 54.14, 59.18),
                "absolute_tolerance": 0.05,
            },
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

# The upstream ToolSandbox answer milestone was authored against an older
# Golden Gate coordinate/result (67.86 km).  The publication fixture frozen for
# these runs resolves the bridge to (37.8199109, -122.4785598), and the native
# distance implementation returns 67.97730305839949 km from the benchmark
# starting location.  Correct only this exact stale target; numeric matching
# remains exact everywhere else, including currency and timestamp contracts.
_FROZEN_ANSWER_TEMPLATE_OVERRIDES = {
    "You are approximately 67.86 kilometers away from Golden Gate Bridge": (
        "You are approximately 67.98 kilometers away from Golden Gate Bridge"
    ),
}


def _contract_manifest_payload() -> dict[str, Any]:
    return {
        "version": OUTCOME_EVALUATOR_VERSION,
        "rollout_scope": "agent_to_user_at_or_after_first_real_user_message",
        "selection_rule": (
            "chronological_three_way_semantic_slot_reducer:affirm_exact_replaces;"
            "explicit_same_slot_negative_or_conflict_replaces_with_zero;other_"
            "does_not_change_state;no_arbitrary_last_message_fallback"
        ),
        "answer_template_rule": (
            "parallel_targets_are_alternatives; multiple_answer_milestones_are_"
            "aligned_to_distinct_temporal_response_segments"
        ),
        "answer_claim_polarity_rule": (
            "an_exact_rendered_target_under_a_same_clause_search_absence_claim_or_"
            "followed_by_an_explicit_absence_contradiction_does_not_count; the_"
            "last_repeated_target_occurrence_controls"
        ),
        "unresolved_numeric_answer_placeholder_rule": (
            "requires_an_explicit_numeric_value_in_the_observed_answer"
        ),
        "dynamic_numeric_placeholder_rule": (
            "protected_values_never_come_from_generated_or_arbitrary_trace_"
            "payloads; temperature_values_are_numeric_machine_epsilon_matches_"
            "to_values_derived_from_the_enumerated_location_and_forecast_day_"
            "matching_"
            "entries_in_the_hash_pinned_fixture; fixture_capture_dates_are_"
            "parallel_because_the_fixed_toolsandbox_clock_is_independent_of_"
            "external_capture_time; days_are_the_exact_datetime_difference_"
            "from_the_immutable_pre_task_clock_to_the_scenario_holiday; explicit_"
            "units_must_match_the_claimed_semantic_slot; exact_days_may_coexist_"
            "with_separate_hour_minute_or_exact_holiday_date_slots; target_"
            "temperatures_may_coexist_with_the_same_fixture_observation_in_the_"
            "source_unit_or_a_fixture_consistent_separate_today_slot; same_slot_"
            "conflicts_fail; bare_correct_values_are_allowed_only_where_the_"
            "upstream_answer_contract_explicitly_allows_them"
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
            "values; explicit_numeric_units_must_be_compatible_while_bare_"
            "dynamic_answers_remain_valid_when_the_upstream_template_allows_"
            "them; golden_gate_distance_accepts_only_the_exact_two_and_three_"
            "decimal_roundings_or_raw_value_derived_from_the_frozen_fixture; a_"
            "distance_candidate_must_share_a_clause_with_golden_gate_bridge_or_"
            "use_a_definite_distance_or_structured_distance_label_immediately_"
            "after_a_golden_gate_bridge_clause; unrelated_numeric_semantic_slots_"
            "including_coordinates_postal_codes_and_serials_neither_satisfy_nor_"
            "veto_the_distance; exact_frozen_fixture_answer_overrides_replace_"
            "only_enumerated_stale_targets"
        ),
        "insufficient_information_rule": (
            "any_independently_sufficient_targeted_blocker_or_exact_collateral_"
            "free_state_completion_or_independently_derived_exact_information_"
            "answer"
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
        "frozen_answer_template_overrides": _FROZEN_ANSWER_TEMPLATE_OVERRIDES,
        "pinned_rapid_api_fixture_sha256": _PINNED_RAPID_API_FIXTURE_SHA256,
        "dynamic_numeric_scenario_families": _DYNAMIC_NUMERIC_SCENARIO_FAMILIES,
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
                r"(?:i(?:'m| am) )?glad (?:i could help|to help|to hear|"
                r"that|it's correct|it is correct)|happy to help|"
                r"(?:please )?let me know if .+|"
                r"(?:please )?feel free to (?:ask|reach out|let me know).+|"
                r"(?:i )?hope (?:that )?helps|is there anything else|"
                r"would you like anything else|can i help with anything else|"
                r"anything else i can help with|"
                r"if (?:there(?:'s| is)|you (?:need|want|would like|have)) .*"
                r"(?:anything else|further assistance|more questions|other questions).*|"
                r"if you need (?:anything else|(?:further )?assistance)(?: .*)?|"
                r"if you have (?:any )?(?:more|other) questions(?: .*)?|"
                r"i appreciate your understanding|thank you for your understanding|"
                r"understood|alright|great|that's okay|that is okay|"
                r"that's (?:perfectly )?fine|that is (?:perfectly )?fine|"
                r"that sounds (?:like )?(?:a )?(?:good|great) idea|"
                r"that's alright|that is alright|exactly|glad you .+|"
                r"if you (?:change your mind|need anything|think of|recall).*|"
                r"if you have any more questions.*|"
                r"(?:have|wishing you) (?:a )?(?:great|nice|good|wonderful) day|"
                r"(?:please )?just reach out.*|(?:please )?reach out.*|"
                r"i (?:do not|don't|cannot|can't) (?:have|provide|think of) "
                r"anything else(?: to add)?|"
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


def _dialogue_text_between(
    execution_context: ExecutionContext,
    *,
    after_message_index: int,
    before_message_index: int,
    user_only: bool = False,
) -> str:
    """Return visible dialogue text in one answer segment, in rollout order."""
    contents: list[str] = []
    for row in _sandbox_rows(execution_context):
        try:
            message_index = int(row.get("sandbox_message_index"))
        except (TypeError, ValueError):
            continue
        if not (after_message_index < message_index < before_message_index):
            continue
        sender = _role(row.get("sender"))
        recipient = _role(row.get("recipient"))
        if user_only:
            if sender != _role(RoleType.USER) or recipient != _role(RoleType.AGENT):
                continue
        elif not (
            (sender == _role(RoleType.USER) and recipient == _role(RoleType.AGENT))
            or (sender == _role(RoleType.AGENT) and recipient == _role(RoleType.USER))
        ):
            continue
        content = _as_text(row.get("content")).strip()
        if content:
            contents.append(content)
    return "\n".join(contents)


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


_DYNAMIC_NUMERIC_PLACEHOLDERS = frozenset({"days", "temperature", "min_temperature"})
_PINNED_RAPID_API_FIXTURE_SHA256 = (
    "eae0a6ab7d2ee5dd272612a0b5ce44d85af34cd1297ff662007260941192322f"
)

# The fixed ToolSandbox clock (2026-07-23 in the publication protocol) is
# intentionally independent of the external-service fixture capture time.  The
# pinned fixture contains both 2026-05-01 and 2026-05-06 weather observations,
# and preserved publication trajectories legitimately address both capture
# families through different coordinate routes.  Each weather contract below
# therefore freezes the exact set of fixture entries whose request coordinates
# are within the upstream scenario's 0.5-degree location tolerance and whose
# requested forecast day matches the task.  This is a small enumerated answer
# key, not a tolerance over arbitrary model- or tool-authored values.
_DYNAMIC_NUMERIC_SCENARIO_FAMILIES: dict[str, dict[str, Any]] = {
    "local_current_temperature_celsius": {
        "base_scenarios": (
            "find_temperature",
            "find_temperature_low_battery_mode",
            "find_temperature_low_battery_mode_alt",
        ),
        "kind": "temperature",
        "placeholder": "temperature",
        "source_field": "current_temperature",
        "forecast_day": 0,
        "reference_coordinates": (37.334606, -122.009102),
        "coordinate_tolerance_degrees": 0.5,
        "source_unit": "celsius",
        "target_unit": "celsius",
        "fixture_observations": (
            {
                "request_sha256": (
                    "255370a816feb4ebfb3a957551c6a6619f6ddef2695374b935a6e6bcb2dae101"
                ),
                "capture_date": "2026-05-01",
                "source_value": 16.1,
            },
        ),
        "target_terms": ("current temperature", "temperature"),
    },
    "grand_canyon_current_temperature_fahrenheit": {
        "base_scenarios": (
            "find_temperature_f_with_location",
            "find_temperature_f_with_location_alt",
            "find_temperature_f_with_location_wifi_off",
            "find_temperature_f_with_location_wifi_off_alt",
        ),
        "kind": "temperature",
        "placeholder": "temperature",
        "source_field": "current_temperature",
        "forecast_day": 0,
        "reference_coordinates": (36.23686, -112.19147),
        "coordinate_tolerance_degrees": 0.5,
        "source_unit": "celsius",
        "target_unit": "fahrenheit",
        "fixture_observations": (
            {
                "request_sha256": (
                    "156d706d6ee108d2723e302c3aff21fbaf992cf9c9a9b1e22068ef4d91866e4e"
                ),
                "capture_date": "2026-05-01",
                "source_value": 12.3,
            },
            {
                "request_sha256": (
                    "8244c4f0764b2eff112ecdf059ee813f82893db4351a257c314f4eaef1d1713f"
                ),
                "capture_date": "2026-05-01",
                "source_value": 15.1,
            },
            {
                "request_sha256": (
                    "435372201e48a45386709c160efa56381a68350c631c7c07ca41975b410f2242"
                ),
                "capture_date": "2026-05-06",
                "source_value": -3.3,
            },
        ),
        "target_terms": (
            "grand canyon",
            "current temperature",
            "temperature",
        ),
    },
    "grand_canyon_tomorrow_minimum_temperature_fahrenheit": {
        "base_scenarios": (
            "find_temperature_f_with_location_and_time_diff_multiple_user_turn",
            "find_temperature_f_with_location_and_time_diff_wifi_off_multiple_user_turn",
            "find_temperature_f_with_location_and_time_diff_low_battery_mode_multiple_user_turn",
        ),
        "kind": "temperature",
        "placeholder": "min_temperature",
        "source_field": "min_temperature",
        "forecast_day": 1,
        "reference_coordinates": (36.23686, -112.19147),
        "coordinate_tolerance_degrees": 0.5,
        "source_unit": "celsius",
        "target_unit": "fahrenheit",
        "fixture_observations": (
            {
                "request_sha256": (
                    "b8eb7b754c3d5dd379f9b9c33ae52c4cad83f4ee1ed6201326e4d0416b2435d2"
                ),
                "capture_date": "2026-05-01",
                "source_value": 8.1,
                "context_source_value": 6.4,
            },
            {
                "request_sha256": (
                    "78acc83a0272e39a09d1e85156e2f8de49854fbca80e811650da2794cc9adda4"
                ),
                "capture_date": "2026-05-01",
                "source_value": 8.2,
                "context_source_value": 8.9,
            },
            {
                "request_sha256": (
                    "bec484fc797b75193b825520f484522e7a6bcffda548582f29463f0926eeeab5"
                ),
                "capture_date": "2026-05-06",
                "source_value": 9.2,
                "context_source_value": 4.9,
            },
        ),
        "target_terms": (
            "grand canyon",
            "lowest temperature",
            "minimum temperature",
            "tomorrow",
        ),
    },
    "days_until_christmas": {
        "base_scenarios": (
            "find_days_till_holiday",
            "find_days_till_holiday_alt",
            "find_days_till_holiday_wifi_off",
            "find_days_till_holiday_wifi_off_alt",
            "find_days_till_holiday_multiple_user_turn",
            "find_days_till_holiday_wifi_off_multiple_user_turn",
        ),
        "kind": "days",
        "placeholder": "days",
        "holiday_name": "Christmas Day",
        "clock_source": (
            "immutable_pre_task_reminder_fixture_midpoint_or_prior_native_"
            "get_current_timestamp_when_synthetic_context_has_no_baseline"
        ),
        "difference_rule": "datetime.fromtimestamp(end)-datetime.fromtimestamp(start).days",
        "target_terms": ("christmas day", "christmas", "days"),
    },
}


def _convert_temperature_value(
    value: float,
    *,
    source_unit: str,
    target_unit: str,
) -> float | None:
    if source_unit == target_unit:
        return value
    if source_unit == "celsius" and target_unit == "fahrenheit":
        return value * 9.0 / 5.0 + 32.0
    if source_unit == "fahrenheit" and target_unit == "celsius":
        return (value - 32.0) * 5.0 / 9.0
    return None


def _resolve_dynamic_numeric_contract(
    scenario_name: str,
) -> tuple[str, dict[str, Any]] | None:
    for family_name, contract in _DYNAMIC_NUMERIC_SCENARIO_FAMILIES.items():
        for base_name in contract["base_scenarios"]:
            for suffix in _CONTRACT_PERTURBATION_SUFFIXES:
                if scenario_name == f"{base_name}{suffix}":
                    return family_name, contract
    return None


def _prior_native_current_timestamps(
    execution_context: ExecutionContext,
    *,
    upper_message_index: int,
) -> list[float]:
    timestamps: list[float] = []
    for message_index, trace in _iter_tool_traces(execution_context):
        if message_index >= upper_message_index:
            continue
        if trace.get("tool_name") != "get_current_timestamp":
            continue
        try:
            timestamp = float(trace.get("result"))
        except (TypeError, ValueError):
            continue
        if math.isfinite(timestamp) and timestamp not in timestamps:
            timestamps.append(timestamp)
    return timestamps


def _temperature_contract_evidence(
    family_name: str,
    contract: dict[str, Any],
) -> dict[str, Any]:
    source_unit = str(contract["source_unit"])
    target_unit = str(contract["target_unit"])
    pairs: list[dict[str, Any]] = []
    for observation in contract["fixture_observations"]:
        source_value = float(observation["source_value"])
        target_value = _convert_temperature_value(
            source_value,
            source_unit=source_unit,
            target_unit=target_unit,
        )
        if target_value is None or not math.isfinite(target_value):
            continue
        pair = {
            "source_value": source_value,
            "source_forms": tuple(_normalize_value(source_value)),
            "target_value": target_value,
            "target_forms": tuple(_normalize_value(target_value)),
        }
        if source_unit == target_unit:
            alternate_unit = "fahrenheit" if target_unit == "celsius" else "celsius"
            alternate_value = _convert_temperature_value(
                target_value,
                source_unit=target_unit,
                target_unit=alternate_unit,
            )
            if alternate_value is None or not math.isfinite(alternate_value):
                continue
            pair.update(
                {
                    "alternate_unit": alternate_unit,
                    "alternate_value": alternate_value,
                    "alternate_forms": tuple(_normalize_value(alternate_value)),
                }
            )
        context_source_value = observation.get("context_source_value")
        if context_source_value is not None:
            context_source_value = float(context_source_value)
            context_target_value = _convert_temperature_value(
                context_source_value,
                source_unit=source_unit,
                target_unit=target_unit,
            )
            if context_target_value is None or not math.isfinite(context_target_value):
                continue
            pair.update(
                {
                    "context_source_value": context_source_value,
                    "context_source_forms": tuple(
                        _normalize_value(context_source_value)
                    ),
                    "context_target_value": context_target_value,
                    "context_target_forms": tuple(
                        _normalize_value(context_target_value)
                    ),
                }
            )
        if pair not in pairs:
            pairs.append(pair)
    return {
        "family": family_name,
        "kind": "temperature",
        "placeholder": str(contract["placeholder"]),
        "source_unit": source_unit,
        "target_unit": target_unit,
        "pairs": tuple(pairs),
        "target_terms": tuple(contract["target_terms"]),
        "truth_basis": "pinned_fixture_scenario_contract",
    }


def _dynamic_numeric_evidence(
    execution_context: ExecutionContext,
    scenario: Scenario,
    *,
    scenario_name: str,
    upper_message_index: int,
) -> dict[str, Any] | None:
    resolved = _resolve_dynamic_numeric_contract(scenario_name)
    if resolved is None:
        return None
    family_name, contract = resolved
    placeholder = str(contract["placeholder"])
    if contract["kind"] == "temperature":
        return _temperature_contract_evidence(family_name, contract)

    baseline_reminders = _database_rows_at(
        execution_context,
        DatabaseNamespace.REMINDER,
        _first_real_user_message_index(execution_context),
    )
    inferred = _infer_base_now_and_upcoming_reminder(baseline_reminders)
    if inferred is not None:
        current_timestamps = [float(inferred[0])]
        clock_basis = "immutable_pre_task_reminder_fixture_midpoint"
    else:
        current_timestamps = _prior_native_current_timestamps(
            execution_context,
            upper_message_index=upper_message_index,
        )
        clock_basis = "prior_native_get_current_timestamp"
    # Multiple distinct fallback clocks are ambiguous.  Publication contexts
    # always have the immutable baseline clock; this branch exists only for
    # isolated evaluator tests and fails closed on conflicting observations.
    if len(current_timestamps) != 1:
        return {
            "family": family_name,
            "kind": "days",
            "placeholder": placeholder,
            "target_forms": (),
            "holiday_years": (),
            "target_terms": tuple(contract["target_terms"]),
            "truth_basis": f"{clock_basis}_ambiguous_or_missing",
        }
    holiday_timestamps = [
        timestamp
        for timestamp in _expected_holiday_timestamps(scenario, current_timestamps)
        if timestamp > current_timestamps[0]
    ]
    if len(holiday_timestamps) != 1:
        return {
            "family": family_name,
            "kind": "days",
            "placeholder": placeholder,
            "target_forms": (),
            "holiday_years": (),
            "target_terms": tuple(contract["target_terms"]),
            "truth_basis": "scenario_holiday_target_ambiguous_or_missing",
        }
    delta = _dt.datetime.fromtimestamp(
        holiday_timestamps[0]
    ) - _dt.datetime.fromtimestamp(current_timestamps[0])
    if delta.days < 0:
        day_forms: tuple[str, ...] = ()
    else:
        day_forms = (str(delta.days),)
    return {
        "family": family_name,
        "kind": "days",
        "placeholder": placeholder,
        "target_forms": day_forms,
        "holiday_years": (str(_dt.datetime.fromtimestamp(holiday_timestamps[0]).year),),
        "holiday_month": _dt.datetime.fromtimestamp(holiday_timestamps[0]).month,
        "holiday_day": _dt.datetime.fromtimestamp(holiday_timestamps[0]).day,
        "target_terms": tuple(contract["target_terms"]),
        "truth_basis": f"{clock_basis}_plus_scenario_holiday_target",
    }


def _placeholder_values(
    execution_context: ExecutionContext,
) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for _, trace in _iter_tool_traces(execution_context):
        result = trace.get("result")
        if isinstance(result, dict):
            for key, value in result.items():
                if str(key) in _DYNAMIC_NUMERIC_PLACEHOLDERS:
                    continue
                bucket = values.setdefault(str(key), [])
                for normalized in _normalize_value(value):
                    if normalized not in bucket:
                        bucket.append(normalized)
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
    # Dynamic numeric targets are rendered only from independently grounded
    # trace evidence. If grounding is absent, do not let template words or an
    # arbitrary number manufacture the answer key.
    if _PLACEHOLDER_RE.search(expected):
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


_TEMPERATURE_UNIT_AFTER_NUMBER_RE = re.compile(
    r"^\s*(?:°\s*)?(?:(?:degrees?|deg)\s*)?"
    r"(?P<unit>celsius|fahrenheit|c|f)\b",
    re.IGNORECASE,
)
_TEMPERATURE_UNIT_BEFORE_NUMBER_RE = re.compile(
    r"\b(?P<unit>celsius|fahrenheit|c|f)\b\s*"
    r"(?:degrees?\s*)?(?:temperature\s*)?(?:is|=|:)?\s*$",
    re.IGNORECASE,
)
_DURATION_UNIT_AFTER_NUMBER_RE = re.compile(
    r"^\s*(?P<unit>days?|hours?|minutes?|seconds?|weeks?|months?|years?)\b",
    re.IGNORECASE,
)
_DURATION_UNIT_BEFORE_NUMBER_RE = re.compile(
    r"(?P<unit>days?|hours?|minutes?|seconds?|weeks?|months?|years?)\b\s*"
    r"(?:is|=|:)?\s*$",
    re.IGNORECASE,
)
_DISTANCE_UNIT_AFTER_NUMBER_RE = re.compile(
    r"^\s*(?P<unit>kilometers?|kms?|km)\b(?!\s*/\s*h)",
    re.IGNORECASE,
)
_TEMPERATURE_TEMPORAL_LABEL_RE = re.compile(
    r"\b(?P<label>today|tomorrow)(?:['\u2019]s)?\b",
    re.IGNORECASE,
)
_HARD_CLAIM_BOUNDARY_RE = re.compile(r"(?:[!?;\n\r\u2014\u2013]+|(?<!\d)\.+|\.+(?!\d))")
_DECEMBER_DATE_RE = re.compile(
    r"\b(?:december|dec\.?)[\s,]+(?P<day>\d{1,2})(?:st|nd|rd|th)?"
    r"(?:\s*,?\s*(?P<year>\d{4}))?\b",
    re.IGNORECASE,
)
_NUMERIC_HOLIDAY_DATE_RE = re.compile(
    r"(?<!\d)(?P<month>\d{1,2})\s*[/\-]\s*(?P<day>\d{1,2})"
    r"(?:\s*[/\-]\s*(?P<year>\d{4}))?(?!\d)"
)
_OPERATIVE_NUMERIC_CORRECTION_RE = re.compile(
    r"\b(?:correction|actually)\b\s*[:,\u2014\u2013-]?",
    re.IGNORECASE,
)
_EXPLICITLY_REJECTED_NUMBER_PREFIX_RE = re.compile(
    r"\b(?:not|isn't|is not|wasn't|was not|rather than|instead of)\s*$",
    re.IGNORECASE,
)
_EXPLICITLY_REJECTED_NUMERIC_TAIL_RE = re.compile(
    r"\s*[,;]?\s*(?:but\s+)?not\s+"
    r"-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
    r"(?:[eE][+-]?\d+)?\s*(?:°\s*)?"
    r"(?:(?:degrees?|deg)\s*)?(?:celsius|fahrenheit|c|f|days?|hours?)?",
    re.IGNORECASE,
)
_TEMPERATURE_ANCILLARY_NUMBER_RE = re.compile(
    r"(?:\b(?:zip|postal(?: code)?|humidity|wind(?: speed)?|latitude|longitude)"
    r"\b[^.!?;]{0,24}$|^\s*(?:%|mph|kph|km/h)\b)",
    re.IGNORECASE,
)
_US_POSTAL_CONTEXT_RE = re.compile(
    r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\s*(?:,\s*(?:USA|US))?\b"
)


def _number_surface(match: re.Match[str]) -> str | None:
    surface = match.group(0).replace(",", "")
    try:
        value = float(surface)
    except ValueError:
        return None
    return surface if math.isfinite(value) else None


def _surface_matches_exact_numeric_value(surface: str, expected: float) -> bool:
    try:
        observed = float(surface)
    except ValueError:
        return False
    return math.isfinite(observed) and math.isclose(
        observed,
        expected,
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def _temperature_units_adjacent_to_number(
    content: str,
    start: int,
    end: int,
) -> set[str]:
    units: set[str] = set()
    after = _TEMPERATURE_UNIT_AFTER_NUMBER_RE.search(content[end : end + 32])
    before = _TEMPERATURE_UNIT_BEFORE_NUMBER_RE.search(
        content[max(0, start - 40) : start]
    )
    # In "8.2 Celsius is 46.76 Fahrenheit", the remote source unit also
    # matches the permissive unit-before grammar.  The immediately following
    # unit is the syntactic unit of the number and therefore takes precedence.
    match = after if after is not None else before
    if match is not None:
        unit = match.group("unit").casefold()
        units.add("celsius" if unit in {"c", "celsius"} else "fahrenheit")
    return units


def _duration_units_adjacent_to_number(
    content: str,
    start: int,
    end: int,
) -> set[str]:
    units: set[str] = set()
    after = _DURATION_UNIT_AFTER_NUMBER_RE.search(content[end : end + 24])
    before = _DURATION_UNIT_BEFORE_NUMBER_RE.search(content[max(0, start - 24) : start])
    for match in (before, after):
        if match is not None:
            units.add(match.group("unit").casefold().rstrip("s"))
    return units


def _dynamic_target_forms(evidence: dict[str, Any]) -> list[str]:
    if evidence["kind"] == "days":
        return list(evidence["target_forms"])
    forms: list[str] = []
    for pair in evidence["pairs"]:
        for form in pair["target_forms"]:
            if form not in forms:
                forms.append(form)
    return forms


def _has_bare_dynamic_template(
    templates: list[str],
    *,
    placeholder: str,
) -> bool:
    return any(template.strip() == f"{{{placeholder}}}" for template in templates)


def _dynamic_claim_has_positive_polarity(
    content: str,
    start: int,
    end: int,
    *,
    target_terms: tuple[str, ...],
) -> bool:
    """Check the target clause while ignoring a genuinely social-only tail."""
    left = 0
    for boundary in _CLAIM_BOUNDARY_RE.finditer(content, 0, start):
        left = boundary.end()
    right_boundary = _CLAIM_BOUNDARY_RE.search(content, end)
    right = len(content) if right_boundary is None else right_boundary.start()
    local_claim = content[left:right]
    relative_start = start - left
    relative_end = end - left
    # A contrast such as "59.18 F, not 60 F" affirms the target and rejects
    # the competing value.  Remove only that explicit numeric rejection from
    # polarity analysis; "59.18 F, not the actual temperature" remains a
    # retraction and is rejected below.
    local_claim = local_claim[:relative_end] + _EXPLICITLY_REJECTED_NUMERIC_TAIL_RE.sub(
        "",
        local_claim[relative_end:],
    )
    if not _claim_span_has_positive_polarity(
        local_claim,
        relative_start,
        relative_end,
        target_terms=target_terms,
    ):
        return False

    # Same-message corrections remain operative.  The generic polarity helper
    # deliberately treats questions and epistemic clauses conservatively, but
    # those markers must not let a social sign-off ("If you have any other
    # questions...") erase an already complete answer.
    later_clauses = [
        clause.strip(" ,:-\u2014\u2013")
        for clause in re.split(r"[.!?;]+", content[right:])
        if clause.strip(" ,:-\u2014\u2013")
    ]
    for clause in later_clauses:
        if _is_social_closure(clause):
            continue
        if (
            re.match(
                r"^if\s+you\s+(?:need|want|would\s+like|have)\b[^.!?;]*"
                r"\b(?:different|another)\s+(?:location|place|city|area|detail)",
                clause,
                re.IGNORECASE,
            )
            or re.match(
                r"^if\s+you\s+(?:can|could|are\s+able\s+to)\s+"
                r"(?:provide|share)\b[^.!?;]{0,100}\b(?:location|coordinates?|address)\b"
                r"[^.!?;]{0,120}\b(?:help|calculate|check|verify|determine)\b",
                clause,
                re.IGNORECASE,
            )
            or re.match(
                r"^if\s+this\s+(?:does\s+not|doesn't)\s+seem\s+accurate\s+"
                r"(?:for|to)\s+you\b",
                clause,
                re.IGNORECASE,
            )
        ):
            continue
        if _has_later_target_domain_correction(clause, target_terms):
            return False
    return True


def _temperature_temporal_slot(
    content: str,
    *,
    start: int,
    end: int,
    has_today_context: bool,
) -> str:
    """Assign a number to the separately stated today or target slot."""
    if not has_today_context:
        return "target"
    segment_start = 0
    for boundary in _HARD_CLAIM_BOUNDARY_RE.finditer(content, 0, start):
        segment_start = boundary.end()
    segment_end_match = _HARD_CLAIM_BOUNDARY_RE.search(content, end)
    segment_end = (
        len(content) if segment_end_match is None else segment_end_match.start()
    )
    preceding = list(
        _TEMPERATURE_TEMPORAL_LABEL_RE.finditer(content, segment_start, start)
    )
    if preceding:
        return (
            "today" if preceding[-1].group("label").casefold() == "today" else "target"
        )
    following = _TEMPERATURE_TEMPORAL_LABEL_RE.search(content, end, segment_end)
    if following is not None:
        return "today" if following.group("label").casefold() == "today" else "target"
    return "target"


def _temperature_number_matches_slot(
    *,
    surface: str,
    units: set[str],
    source_forms: set[str],
    target_forms: set[str],
    source_value: float,
    target_value: float,
    alternate_forms: set[str],
    alternate_value: float | None,
    alternate_unit: str | None,
    source_unit: str,
    target_unit: str,
    permit_bare_target: bool,
) -> tuple[bool, bool]:
    """Return (valid_for_slot, is_target-unit value)."""
    target_values = {target_value, *(float(value) for value in target_forms)}
    source_values = {source_value, *(float(value) for value in source_forms)}
    if any(
        _surface_matches_exact_numeric_value(surface, value) for value in target_values
    ) and (units == {target_unit} or (not units and permit_bare_target)):
        return True, True
    if (
        source_unit != target_unit
        and any(
            _surface_matches_exact_numeric_value(surface, value)
            for value in source_values
        )
        and units == {source_unit}
    ):
        return True, False
    if (
        alternate_unit is not None
        and alternate_value is not None
        and any(
            _surface_matches_exact_numeric_value(surface, value)
            for value in {
                alternate_value,
                *(float(value) for value in alternate_forms),
            }
        )
        and units == {alternate_unit}
    ):
        return True, False
    return False, False


def _numeric_correction_cutoff(content: str) -> int:
    """Return the last explicit correction that introduces a numeric claim."""
    cutoff = 0
    for correction in _OPERATIVE_NUMERIC_CORRECTION_RE.finditer(content):
        if _SCALAR_NUMBER_RE.search(content, correction.end()) is not None:
            cutoff = correction.end()
    return cutoff


def _number_is_explicitly_rejected(content: str, match: re.Match[str]) -> bool:
    prefix = content[max(0, match.start() - 32) : match.start()]
    return bool(_EXPLICITLY_REJECTED_NUMBER_PREFIX_RE.search(prefix))


def _frozen_golden_gate_distance_answer_score(content: str) -> float:
    """Score the pinned Golden Gate distance without treating coordinates as km."""
    normalized = _normalized_phrase_text(content)
    if not (
        _contains_phrase(normalized, "golden gate")
        and _contains_phrase(normalized, "bridge")
    ):
        return 0.0
    correction_cutoff = _numeric_correction_cutoff(content)
    accepted_spans: list[tuple[int, int]] = []
    for match in _SCALAR_NUMBER_RE.finditer(content, correction_cutoff):
        unit = _DISTANCE_UNIT_AFTER_NUMBER_RE.search(
            content[match.end() : match.end() + 24]
        )
        if unit is None or _number_is_explicitly_rejected(content, match):
            continue
        # Numeric truth is candidate-local: a distance-looking serial or
        # unrelated measurement elsewhere in the response cannot satisfy (or
        # veto) the Golden Gate outcome.  Both entity terms must occur in the
        # same asserted clause as the candidate value.
        prior_boundaries = list(
            _HARD_CLAIM_BOUNDARY_RE.finditer(content, 0, match.start())
        )
        claim_left = prior_boundaries[-1].end() if prior_boundaries else 0
        next_boundary = _HARD_CLAIM_BOUNDARY_RE.search(content, match.end())
        claim_right = len(content) if next_boundary is None else next_boundary.start()
        local_claim = _normalized_phrase_text(content[claim_left:claim_right])
        previous_claim = ""
        if prior_boundaries:
            for boundary_index in range(len(prior_boundaries) - 1, -1, -1):
                previous_left = (
                    prior_boundaries[boundary_index - 1].end()
                    if boundary_index > 0
                    else 0
                )
                candidate = _normalized_phrase_text(
                    content[previous_left : prior_boundaries[boundary_index].start()]
                )
                # A numbered-list marker such as ``3.`` is punctuation, not a
                # semantic intervening clause.  Skip it when resolving the
                # immediately preceding list item.
                if (
                    candidate.strip()
                    and re.fullmatch(r"\d+", candidate.strip()) is None
                ):
                    previous_claim = candidate
                    break
        local_has_entity = _contains_phrase(
            local_claim, "golden gate"
        ) and _contains_phrase(local_claim, "bridge")
        prior_has_entity = _contains_phrase(
            previous_claim, "golden gate"
        ) and _contains_phrase(previous_claim, "bridge")
        has_definite_distance_anaphora = _contains_phrase(local_claim, "the distance")
        if not (
            local_has_entity
            or (
                prior_has_entity
                and (
                    has_definite_distance_anaphora
                    or bool(
                        re.match(
                            r"^distance\s+(?:is\s+|"
                            r"(?:approximately|about|roughly|around)\s+)",
                            local_claim.strip(),
                        )
                    )
                )
            )
        ):
            continue
        surface = _number_surface(match)
        if surface is None:
            return 0.0
        if not any(
            _surface_matches_exact_numeric_value(surface, expected)
            for expected in _FROZEN_GOLDEN_GATE_DISTANCE_KM_VALUES
        ):
            return 0.0
        accepted_spans.append(match.span())
    if not accepted_spans:
        return 0.0
    return float(
        _dynamic_claim_has_positive_polarity(
            content,
            *accepted_spans[-1],
            target_terms=(
                "golden gate bridge",
                "distance",
                "kilometers",
                "km",
            ),
        )
    )


def _temperature_number_is_ancillary(
    content: str,
    match: re.Match[str],
    *,
    units: set[str],
) -> bool:
    if units:
        return False
    prefix = content[max(0, match.start() - 40) : match.start()]
    suffix = content[match.end() : min(len(content), match.end() + 24)]
    if _TEMPERATURE_ANCILLARY_NUMBER_RE.search(prefix + suffix):
        return True
    if re.match(r"\s*(?:%|mph|kph|km/h)\b", suffix, flags=re.IGNORECASE):
        return True
    if re.search(
        r"\b(?:as of|date|year|jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|"
        r"apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|"
        r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
        prefix,
        flags=re.IGNORECASE,
    ):
        return True
    surrounding = content[
        max(0, match.start() - 8) : min(len(content), match.end() + 16)
    ]
    return bool(_US_POSTAL_CONTEXT_RE.search(surrounding))


def _temperature_dynamic_answer_score(
    templates: list[str],
    observed: str,
    evidence: dict[str, Any],
) -> float:
    correction_cutoff = _numeric_correction_cutoff(observed)
    matches = list(_SCALAR_NUMBER_RE.finditer(observed, correction_cutoff))
    if not matches:
        return 0.0
    target_unit = str(evidence["target_unit"])
    source_unit = str(evidence["source_unit"])
    target_terms = tuple(evidence["target_terms"])
    placeholder = str(evidence["placeholder"])
    permits_bare_answer = _has_bare_dynamic_template(
        templates,
        placeholder=placeholder,
    )
    for pair in evidence["pairs"]:
        target_forms = set(pair["target_forms"])
        source_forms = set(pair["source_forms"])
        alternate_forms = set(pair.get("alternate_forms", ()))
        alternate_value = pair.get("alternate_value")
        alternate_unit = pair.get("alternate_unit")
        has_today_context = bool(
            pair.get("context_target_forms") or pair.get("context_source_forms")
        )
        target_spans: list[tuple[int, int]] = []
        valid_pair = True
        for match in matches:
            surface = _number_surface(match)
            if surface is None:
                valid_pair = False
                break
            units = _temperature_units_adjacent_to_number(
                observed,
                match.start(),
                match.end(),
            )
            if _number_is_explicitly_rejected(observed, match):
                continue
            if _temperature_number_is_ancillary(observed, match, units=units):
                continue
            slot = _temperature_temporal_slot(
                observed,
                start=match.start(),
                end=match.end(),
                has_today_context=has_today_context,
            )
            if slot == "today":
                # "Today" is a prior, separately requested informational slot
                # in these multi-turn tasks.  Its value is not the final
                # tomorrow outcome and therefore neither establishes nor
                # vetoes that outcome.
                continue
            else:
                valid, is_target = _temperature_number_matches_slot(
                    surface=surface,
                    units=units,
                    source_forms=source_forms,
                    target_forms=target_forms,
                    source_value=float(pair["source_value"]),
                    target_value=float(pair["target_value"]),
                    alternate_forms=alternate_forms,
                    alternate_value=(
                        None if alternate_value is None else float(alternate_value)
                    ),
                    alternate_unit=(
                        None if alternate_unit is None else str(alternate_unit)
                    ),
                    source_unit=source_unit,
                    target_unit=target_unit,
                    permit_bare_target=permits_bare_answer,
                )
                if valid and is_target:
                    target_spans.append(match.span())
            if not valid:
                valid_pair = False
                break
        if not valid_pair or not target_spans:
            continue
        last_target_span = target_spans[-1]
        if not _dynamic_claim_has_positive_polarity(
            observed,
            *last_target_span,
            target_terms=target_terms,
        ):
            continue
        if not permits_bare_answer:
            local_claim = _claim_clause_text(observed, *last_target_span)
            normalized_claim = _normalized_phrase_text(local_claim)
            units = _temperature_units_adjacent_to_number(
                observed,
                *last_target_span,
            )
            has_target_context = bool(
                units
                or any(
                    _contains_phrase(normalized_claim, term)
                    for term in target_terms
                    if term
                )
            )
            if not has_target_context:
                continue
        return 1.0
    return 0.0


def _days_dynamic_answer_score(
    observed: str,
    evidence: dict[str, Any],
    *,
    permits_bare_answer: bool,
    required_context_groups: tuple[tuple[str, ...], ...] = (),
) -> float:
    target_forms = set(evidence["target_forms"])
    if not target_forms:
        return 0.0
    holiday_years = set(evidence["holiday_years"])
    holiday_month = int(evidence["holiday_month"])
    holiday_day = int(evidence["holiday_day"])
    calendar_spans: set[tuple[int, int]] = set()
    for date_match in _DECEMBER_DATE_RE.finditer(observed):
        year = date_match.group("year")
        if int(date_match.group("day")) != holiday_day or (
            year is not None and year not in holiday_years
        ):
            continue
        calendar_spans.add(date_match.span("day"))
        if year is not None:
            calendar_spans.add(date_match.span("year"))
    for date_match in _NUMERIC_HOLIDAY_DATE_RE.finditer(observed):
        year = date_match.group("year")
        if (
            int(date_match.group("month")) != holiday_month
            or int(date_match.group("day")) != holiday_day
            or (year is not None and year not in holiday_years)
        ):
            continue
        calendar_spans.add(date_match.span("month"))
        calendar_spans.add(date_match.span("day"))
        if year is not None:
            calendar_spans.add(date_match.span("year"))
    target_spans: list[tuple[int, int]] = []
    correction_cutoff = _numeric_correction_cutoff(observed)
    for match in _SCALAR_NUMBER_RE.finditer(observed, correction_cutoff):
        surface = _number_surface(match)
        if surface is None:
            return 0.0
        units = _duration_units_adjacent_to_number(
            observed,
            match.start(),
            match.end(),
        )
        if _number_is_explicitly_rejected(observed, match):
            continue
        if any(
            _surface_matches_exact_numeric_value(surface, float(target))
            for target in target_forms
        ) and (not units or units == {"day"}):
            target_spans.append(match.span())
            continue
        if units in ({"hour"}, {"minute"}, {"second"}):
            continue
        if match.span() in calendar_spans:
            continue
        # The response may identify which Christmas it used, but a year may
        # not itself be labeled as a duration.
        holiday_year_context = bool(
            re.search(
                r"\bchristmas(?:\s+day)?\s*$",
                observed[max(0, match.start() - 40) : match.start()],
                flags=re.IGNORECASE,
            )
        )
        if surface in holiday_years and (not units or holiday_year_context):
            continue
        return 0.0
    if not target_spans:
        return 0.0
    target_span = target_spans[-1]
    if not _dynamic_claim_has_positive_polarity(
        observed,
        *target_span,
        target_terms=tuple(evidence["target_terms"]),
    ):
        return 0.0
    if required_context_groups and not _has_required_answer_context(
        _claim_clause_text(observed, *target_span),
        required_context_groups,
    ):
        return 0.0
    if not permits_bare_answer:
        units = _duration_units_adjacent_to_number(observed, *target_span)
        if units != {"day"}:
            return 0.0
    return 1.0


def _dynamic_numeric_answer_score(
    templates: list[str],
    observed: str,
    evidence: dict[str, Any],
) -> float:
    if evidence["kind"] == "temperature":
        return _temperature_dynamic_answer_score(templates, observed, evidence)
    return _days_dynamic_answer_score(
        observed,
        evidence,
        permits_bare_answer=_has_bare_dynamic_template(
            templates,
            placeholder=str(evidence["placeholder"]),
        ),
    )


_ANSWER_SEARCH_ABSENCE_PREFIX_RE = re.compile(
    r"\b(?:there\s+(?:are|is|were|was)\s+no\s+"
    r"(?:records?|results?|matches?|messages?|reminders?)|"
    r"(?:i|we)\s+(?:still\s+)?(?:could\s+not|couldn't|cannot|can't|did\s+not|didn't|"
    r"was(?:n't|\s+not)?\s+able\s+to|were(?:n't|\s+not)?\s+able\s+to|"
    r"was\s+unable\s+to|were\s+unable\s+to)\s+"
    r"(?:find|locate|retrieve|identify|confirm|verify))\b",
    re.IGNORECASE,
)
_ANSWER_POST_TARGET_ABSENCE_RE = re.compile(
    r"\b(?:but|however|actually|correction)\b[^\n\r]{0,240}?\b"
    r"(?:there\s+(?:are|is|were|was)\s+no\s+"
    r"(?:records?|results?|matches?|messages?|reminders?)|"
    r"(?:the\s+)?(?:answer|result|message|reminder|value)\b[^.!?;]{0,80}"
    r"\b(?:wrong|incorrect|false|not\s+(?:correct|current|latest))\b|"
    r"(?:latest|most\s+recent)\b[^.!?;]{0,80}\bearlier\s+"
    r"(?:date|time|day))\b",
    re.IGNORECASE,
)
_ANSWER_DIRECT_TARGET_DENIAL_RE = re.compile(
    r"(?:^|[.!?;\n\r\u2014\u2013])[^.!?;\n\r]{0,160}?\b"
    r"(?:was|were|is|are|has|have)\s+not\s+"
    r"(?:found|located|retrieved|created|recorded|saved|sent)\b|"
    r"\b(?:created|recorded|saved)\s+earlier\b[^.!?;]{0,120}"
    r"\bnot\s+(?:specifically\s+)?(?:tied\s+to|from|on)\s+yesterday\b|"
    r"\bnot\s+(?:created|recorded|saved)\s+yesterday\b",
    re.IGNORECASE,
)


def _explicitly_contradicts_rendered_answer(
    content: str,
    rendered_targets: list[str],
) -> bool:
    """Reject only an explicit absence/retraction tied to an exact target mention."""

    normalized = " ".join(content.replace("’", "'").split())
    folded = normalized.casefold()
    for target in rendered_targets:
        collapsed_target = " ".join(target.replace("’", "'").split())
        if not collapsed_target or _PLACEHOLDER_RE.search(collapsed_target):
            continue
        start = folded.rfind(collapsed_target.casefold())
        if start < 0:
            continue
        end = start + len(collapsed_target)
        prefix = normalized[max(0, start - 240) : start]
        local_prefix = re.split(
            r"[.!?;\n\r\u2014\u2013]+|\b(?:but|however|correction)\b",
            prefix,
            flags=re.IGNORECASE,
        )[-1]
        if _ANSWER_SEARCH_ABSENCE_PREFIX_RE.search(local_prefix):
            return True
        suffix = normalized[end : min(len(normalized), end + 320)]
        # A returned phone number can correctly be absent from the contacts
        # database.  That different relation does not negate who sent the
        # message containing the requested text.
        denial_suffix = re.sub(
            r"\b(?:is|was)\s+not\s+saved\s+in\s+(?:your\s+)?contacts?\b",
            " ",
            suffix,
            flags=re.IGNORECASE,
        )
        if _ANSWER_POST_TARGET_ABSENCE_RE.search(suffix) or (
            _ANSWER_DIRECT_TARGET_DENIAL_RE.search(denial_suffix)
        ):
            return True
    return False


def _is_raw_structured_answer(content: str) -> bool:
    stripped = content.strip()
    if not stripped or stripped[0] not in "[{":
        return False
    try:
        parsed = json.loads(stripped)
    except (TypeError, json.JSONDecodeError):
        return False
    return isinstance(parsed, (dict, list))


def _target_mention_is_conditional(
    content: str,
    rendered_targets: list[str],
) -> bool:
    """Reject a target echoed only as the consequent/condition of ``if``."""
    normalized = " ".join(content.replace("’", "'").split())
    folded = normalized.casefold()
    last_match: tuple[int, int] | None = None
    for target in rendered_targets:
        collapsed = " ".join(target.replace("’", "'").split())
        if not collapsed or _PLACEHOLDER_RE.search(collapsed):
            continue
        start = folded.rfind(collapsed.casefold())
        if start >= 0 and (last_match is None or start > last_match[0]):
            last_match = (start, start + len(collapsed))
    if last_match is None:
        return False
    prefix = normalized[max(0, last_match[0] - 180) : last_match[0]]
    local_prefix = re.split(r"[.!?;\n\r\u2014\u2013]+", prefix)[-1]
    return bool(re.search(r"\bif\b[^.!?;]{0,160}$", local_prefix, re.IGNORECASE))


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


def _outcome_answer_templates(milestone: Milestone) -> list[str]:
    """Return evaluator targets after exact frozen-fixture corrections."""
    return [
        _FROZEN_ANSWER_TEMPLATE_OVERRIDES.get(template, template)
        for template in _answer_templates(milestone)
    ]


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


_OUTCOME_LIMITATION_MARKER_RE = re.compile(
    r"\b(?:cannot|can't|could not|couldn't|unable|without|need|requires?|"
    r"do not have|don't have|no access|permission(?:s)? issue|limitation)\b",
    re.IGNORECASE,
)
_NEW_LOCATION_BRANCH_RE = re.compile(
    r"\b(?:different|another|other|unspecified)\s+"
    r"(?:location|place|city|area|region|source)\b",
    re.IGNORECASE,
)
_PRIVACY_OR_VISIBILITY_GOAL_RE = re.compile(
    r"\b(?:private|privacy|confidential|do not share|don't share|not share|"
    r"do not leak|don't leak|not leak(?:ed|ing)?|not to leak|"
    r"do not disclose|don't disclose|not disclose|visibility|permissions?|settings?)\b|"
    r"\b(?:keep|remain)\b[^.!?;]{0,60}\b(?:to yourself|between us|private|secret|safe)\b|"
    r"\b(?:do not|don't)\s+want\b[^.!?;]{0,60}\b(?:share|shared|disclose|leak)",
    re.IGNORECASE,
)
_LATEST_MESSAGE_VALUE_CLAIM_RE = re.compile(
    r"\b(?:most\s+recent|latest|last)\s+(?:message|text)"
    r"(?:\s+content)?\s+(?:is|says?|reads?|was)\b",
    re.IGNORECASE,
)
_OLDEST_MESSAGE_VALUE_CLAIM_RE = re.compile(
    r"\b(?:oldest|first(?:\s+ever)?)\s+(?:message|text)"
    r"(?:\s+content)?\s+(?:is|says?|reads?|was)\b",
    re.IGNORECASE,
)
_MESSAGE_CONTENT_PRIVACY_RESPONSE_RE = re.compile(
    r"\b(?:delete|remove|hide|share|disclose|leak|store|private|privacy|secret|safe)\b",
    re.IGNORECASE,
)
_MESSAGE_CONTENT_DIRECT_LIMITATION_RE = re.compile(
    r"\b(?:cannot|can't|could\s+not|couldn't|unable|did\s+not|didn't)\b"
    r"[^.!?;]{0,120}\b(?:find|locate|retrieve|access|provide|disclose|search)\b"
    r"[^.!?;]{0,100}\b(?:content\b[^.!?;]{0,50}\b(?:message|text)|"
    r"(?:most\s+recent|latest|last|oldest|first|recent)\s+(?:message|text)|"
    r"(?:message|text)s?\b[^.!?;]{0,50}\b(?:content|records?|criteria)|criteria)\b|"
    r"\b(?:no|not\s+any)\s+(?:recent|latest|oldest)?\s*"
    r"(?:messages?|texts?|records?)\b",
    re.IGNORECASE,
)


def _scenario_matches_base(scenario_name: str, base_name: str) -> bool:
    return any(
        scenario_name == f"{base_name}{suffix}"
        for suffix in _CONTRACT_PERTURBATION_SUFFIXES
    )


def _is_frozen_distance_scenario(scenario_name: str) -> bool:
    return any(
        _scenario_matches_base(scenario_name, base_name)
        for base_name in (
            "find_distance_with_location_name",
            "find_distance_with_location_name_alt",
        )
    )


def _dynamic_zero_score_is_same_slot(
    content: str,
    evidence: dict[str, Any],
    *,
    user_context: str,
    dialogue_context: str,
) -> bool:
    normalized = _normalized_phrase_text(content)
    family = str(evidence["family"])
    if evidence["kind"] == "days":
        return _contains_phrase(normalized, "christmas") and bool(
            _SCALAR_NUMBER_RE.search(content)
            or _OUTCOME_LIMITATION_MARKER_RE.search(content)
            or re.search(r"\b(?:correction|actually|wrong|days?)\b", content, re.I)
        )

    user_normalized = _normalized_phrase_text(user_context)
    if family == "grand_canyon_tomorrow_minimum_temperature_fahrenheit" and (
        _contains_phrase(user_normalized, "today")
        or (
            _contains_phrase(normalized, "today")
            and not _contains_phrase(normalized, "tomorrow")
        )
    ):
        return False

    if family == "local_current_temperature_celsius" and _NEW_LOCATION_BRANCH_RE.search(
        dialogue_context + "\n" + content
    ):
        return False

    has_temperature_domain = bool(
        re.search(
            r"\b(?:temperature|weather|degrees?|celsius|fahrenheit)\b", content, re.I
        )
    )
    has_numeric_claim = bool(_SCALAR_NUMBER_RE.search(content))
    directly_denies_temperature = bool(
        re.search(
            r"\b(?:cannot|can't|could\s+not|couldn't|unable|without)\b"
            r"[^.!?;]{0,120}\b(?:provide|determine|retrieve|find|check|access)\b"
            r"[^.!?;]{0,80}\b(?:current\s+)?temperature\b|"
            r"\b(?:cannot|can't|could\s+not|couldn't|unable)\b"
            r"[^.!?;]{0,80}\btemperature\s+(?:data|information|reading)\b",
            content,
            re.IGNORECASE,
        )
    )
    return bool(
        has_temperature_domain and (has_numeric_claim or directly_denies_temperature)
    )


def _distance_zero_score_is_same_slot(content: str) -> bool:
    has_unit_bound_number = any(
        _DISTANCE_UNIT_AFTER_NUMBER_RE.search(content[match.end() : match.end() + 24])
        for match in _SCALAR_NUMBER_RE.finditer(content)
    )
    if has_unit_bound_number:
        return True
    return bool(
        re.search(
            r"\b(?:cannot|can't|could\s+not|couldn't|unable|without)\b"
            r"[^.!?;]{0,140}\b(?:calculate|determine|provide|verify)\b"
            r"[^.!?;]{0,60}\bdistance\b|"
            r"\b(?:cannot|can't|could\s+not|couldn't|unable)\b"
            r"[^.!?;]{0,120}\bdistance\b",
            content,
            re.IGNORECASE,
        )
    )


def _message_search_zero_score_is_same_slot(
    content: str,
    *,
    scenario_name: str,
    user_context: str,
) -> bool:
    user_normalized = _normalized_phrase_text(user_context)
    privacy_goal = bool(_PRIVACY_OR_VISIBILITY_GOAL_RE.search(user_context))
    disclaims_content = bool(
        re.search(
            r"\b(?:do not|don't)\s+(?:want|need)\b[^.!?;]{0,80}"
            r"\b(?:content|what\s+(?:it|the\s+message)\s+says?|to\s+know)\b|"
            r"\bwithout\s+(?:sharing|disclosing|revealing)\b",
            user_context,
            re.IGNORECASE,
        )
    )
    repeats_retrieval_goal = bool(
        re.search(
            r"\b(?:find|check|confirm|look(?:ing)?|retrieve|show|provide)\b"
            r"[^.!?;]{0,100}\b(?:content|message|text|recent|latest|oldest)\b",
            user_context,
            re.IGNORECASE,
        )
    )
    if disclaims_content or (privacy_goal and not repeats_retrieval_goal):
        return False
    if re.search(
        r"\b(?:send|delete|remove|retract)\b[^.!?;]{0,60}\bmessage\b",
        user_context,
        re.I,
    ):
        return False
    if re.search(
        r"\banother\s+(?:recent|latest|oldest|message|text)\b", user_context, re.I
    ):
        return False
    asks_latest = any(
        _contains_phrase(user_normalized, term)
        for term in ("most recent", "latest message", "latest text")
    )
    asks_oldest = any(
        _contains_phrase(user_normalized, term)
        for term in ("oldest message", "oldest text", "first message", "first text")
    )
    scenario_is_latest = "search_message_with_recency_latest" in scenario_name
    if (scenario_is_latest and asks_oldest) or (not scenario_is_latest and asks_latest):
        return False

    content_claims_latest = bool(_LATEST_MESSAGE_VALUE_CLAIM_RE.search(content))
    content_claims_oldest = bool(_OLDEST_MESSAGE_VALUE_CLAIM_RE.search(content))
    content_has_opposite_selector = (
        scenario_is_latest and content_claims_oldest and not content_claims_latest
    ) or (
        not scenario_is_latest and content_claims_latest and not content_claims_oldest
    )
    if content_has_opposite_selector:
        # An answer to an explicit same-slot recheck can replace the earlier
        # answer even when it reports the wrong selector.  A spontaneous
        # opposite-recency statement after confirmation/privacy is a distinct
        # proposition and therefore OTHER.
        return bool(
            re.search(
                r"\b(?:not\s+(?:right|correct|the\s+(?:message|one)|what\s+i\s+asked)|"
                r"wrong|try\s+again|look\s+again|check(?:ing)?\s+(?:it\s+)?again|"
                r"check\s+(?:once|one)\s+more|double[- ]check|recheck)\b",
                user_context,
                re.IGNORECASE,
            )
        )

    if re.search(
        r"\b(?:remains? the same|has not changed|not changed)\b", content, re.I
    ):
        return False
    if re.search(
        r"\b(?:message|text)\b[^.!?;]{0,80}"
        r"\b(?:successfully\s+)?(?:found|located|confirmed)\b|"
        r"\b(?:found|located|confirmed)\b[^.!?;]{0,80}\b(?:message|text)\b",
        content,
        re.IGNORECASE,
    ):
        return False
    if re.search(
        r"\bno\s+messages?\b[^.!?;]{0,80}\b(?:containing|matching)\b"
        r"[^.!?;]{0,60}\b(?:keyword|term|phrase)\b",
        content,
        re.IGNORECASE,
    ):
        return False
    if re.search(
        r"\b(?:further|additional|more)\s+(?:details?|information)\b",
        content,
        re.IGNORECASE,
    ):
        return False
    if _MESSAGE_CONTENT_PRIVACY_RESPONSE_RE.search(content) and not (
        _MESSAGE_CONTENT_DIRECT_LIMITATION_RE.search(content)
        and repeats_retrieval_goal
        and not disclaims_content
    ):
        return False
    if (scenario_is_latest and content_claims_latest) or (
        not scenario_is_latest and content_claims_oldest
    ):
        return True
    return bool(_MESSAGE_CONTENT_DIRECT_LIMITATION_RE.search(content))


def _normalized_rendered_target_present(
    content: str,
    rendered_targets: list[str],
) -> bool:
    normalized = _normalized_phrase_text(content)
    return any(
        not _PLACEHOLDER_RE.search(target) and _contains_phrase(normalized, target)
        for target in rendered_targets
    )


def _message_search_affirmative_score(
    content: str,
    *,
    scenario_name: str,
    rendered_targets: list[str],
    similarity_score: float,
) -> float | None:
    normalized = _normalized_phrase_text(content)
    explicitly_latest = any(
        _contains_phrase(normalized, term)
        for term in (
            "most recent message",
            "most recent text",
            "latest message",
            "latest text",
        )
    )
    explicitly_oldest = any(
        _contains_phrase(normalized, term)
        for term in ("oldest message", "oldest text", "first message", "first text")
    )
    scenario_is_latest = "search_message_with_recency_latest" in scenario_name
    if (scenario_is_latest and explicitly_oldest and not explicitly_latest) or (
        not scenario_is_latest and explicitly_latest and not explicitly_oldest
    ):
        return None
    if _normalized_rendered_target_present(content, rendered_targets):
        return 1.0
    if math.isclose(similarity_score, 1.0, rel_tol=0.0, abs_tol=1e-12):
        return 1.0
    return None


def _generic_affirmative_score(
    content: str,
    *,
    scenario_name: str,
    rendered_targets: list[str],
    similarity_score: float,
) -> float | None:
    if "search_message_with_recency_" in scenario_name:
        return _message_search_affirmative_score(
            content,
            scenario_name=scenario_name,
            rendered_targets=rendered_targets,
            similarity_score=similarity_score,
        )
    if "cellular" in scenario_name:
        if re.search(
            r"\bcellular\s+service\b[^.!?;]{0,80}"
            r"\b(?:is|was|remains?|already|confirmed|has\s+been)?\s*"
            r"(?:on|enabled|active|turned\s+on)\b",
            content,
            re.IGNORECASE,
        ):
            return 1.0
    if "wifi" in scenario_name and re.search(
        r"\bwi-?fi(?:\s+service)?\b[^.!?;]{0,80}"
        r"\b(?:on|enabled|active|turned\s+on)\b",
        content,
        re.IGNORECASE,
    ):
        return 1.0
    if _normalized_rendered_target_present(content, rendered_targets):
        return 1.0
    if math.isclose(similarity_score, 1.0, rel_tol=0.0, abs_tol=1e-12):
        return 1.0
    return None


def _generic_zero_score_is_same_slot(
    content: str,
    *,
    scenario_name: str,
    templates: list[str],
    user_context: str,
) -> bool:
    if _is_frozen_distance_scenario(scenario_name):
        return _distance_zero_score_is_same_slot(content)
    if "search_message_with_recency_" in scenario_name:
        return _message_search_zero_score_is_same_slot(
            content,
            scenario_name=scenario_name,
            user_context=user_context,
        )
    if "search_reminder_with_" in scenario_name:
        if _PRIVACY_OR_VISIBILITY_GOAL_RE.search(user_context):
            return False
        return bool(
            re.search(r"\b(?:reminder|todo(?: item)?)\b", content, re.I)
            and (
                _OUTCOME_LIMITATION_MARKER_RE.search(content)
                or re.search(
                    r"\b(?:created|made|due|recorded)\s+yesterday\b", content, re.I
                )
            )
        )

    if "find_phone_number_with_location_name" in scenario_name:
        if re.search(
            r"\b(?:search|look\s+up|reverse(?:-search)?)\b"
            r"[^.!?;]{0,80}\b(?:that|the|this)?\s*phone\s+number\b",
            user_context,
            re.IGNORECASE,
        ):
            return False
        return bool(
            re.search(r"\bphone\s+number\s+for\s+apple\s+park\b", content, re.I)
            and (
                _SCALAR_NUMBER_RE.search(content)
                or _OUTCOME_LIMITATION_MARKER_RE.search(content)
            )
        )

    if "find_stock_symbol_with_company_name" in scenario_name:
        if re.search(
            r"\b(?:stock\s+information|lookup|look\s+up|search)\b",
            user_context,
            re.IGNORECASE,
        ):
            return False
        return bool(
            re.search(
                r"\bstock\s+symbol\s+for\s+apple\b[^.!?;]{0,50}\b(?:is|=)\b",
                content,
                re.IGNORECASE,
            )
        )

    if "cellular" in scenario_name:
        return bool(
            re.search(
                r"\bcellular\s+service\b[^.!?;]{0,80}"
                r"\b(?:off|disabled|inactive|not\s+(?:on|enabled|active))\b",
                content,
                re.IGNORECASE,
            )
            or re.search(
                r"\b(?:cannot|can't|unable)\b[^.!?;]{0,100}"
                r"\b(?:determine|verify|confirm|check)\b[^.!?;]{0,60}"
                r"\bcellular\s+(?:service|status)\b",
                content,
                re.IGNORECASE,
            )
        )

    if "wifi" in scenario_name:
        return bool(
            re.search(
                r"\bwi-?fi(?:\s+service)?\b[^.!?;]{0,80}"
                r"\b(?:off|disabled|inactive|not\s+(?:on|enabled|active))\b",
                content,
                re.IGNORECASE,
            )
        )

    observed_tokens = set(_WORD_RE.findall(content.casefold()))
    anchors = {token for template in templates for token in _anchor_tokens(template)}
    overlap = len(anchors.intersection(observed_tokens))
    if _LATER_RETRACTION_RE.search(content.strip()) and overlap:
        return True
    if any(_NUMBER_RE.search(template) for template in templates):
        return bool(
            _SCALAR_NUMBER_RE.search(content)
            and overlap >= min(2, len(anchors))
            and re.search(r"\b(?:is|equals?|correction|actually)\b", content, re.I)
        )
    return bool(
        overlap >= min(2, len(anchors))
        and re.search(
            r"\b(?:relationship|phone number)\b[^.!?;]{0,80}\b(?:is|was|=)\b",
            content,
            re.IGNORECASE,
        )
    )


def _score_answer_templates(
    templates: list[str],
    messages: list[_RolloutMessage],
    values: dict[str, list[str]],
    *,
    execution_context: ExecutionContext,
    scenario: Scenario,
    scenario_name: str,
) -> tuple[float, dict[str, Any]]:
    if not templates or not messages:
        return 0.0, {
            "selected_message_index": None,
            "earlier_conflicting_message_indices": [],
            "ignored_later_non_outcome_message_indices": [],
        }

    def message_score(
        message: _RolloutMessage,
    ) -> tuple[
        float,
        bool,
        bool,
        dict[str, Any] | None,
        dict[str, Any] | None,
        list[str],
    ]:
        evidence = _dynamic_numeric_evidence(
            execution_context,
            scenario,
            scenario_name=scenario_name,
            upper_message_index=message.sandbox_message_index,
        )
        message_values = dict(values)
        if evidence is not None:
            target_forms = _dynamic_target_forms(evidence)
            if target_forms:
                message_values[str(evidence["placeholder"])] = target_forms
        rendered_targets = [
            expected
            for template in templates
            for expected in _render_templates(template, message_values)
        ]
        # Multiple textual targets in one milestone are parallel acceptable
        # phrasings, not conjunctive requirements.
        if evidence is not None and any(
            f"{{{evidence['placeholder']}}}" in template for template in templates
        ):
            score = _dynamic_numeric_answer_score(
                templates,
                message.content,
                evidence,
            )
        elif _is_frozen_distance_scenario(scenario_name):
            score = _frozen_golden_gate_distance_answer_score(message.content)
        else:
            score = max(
                _content_similarity(expected, message.content)
                for expected in rendered_targets
            )
        contradicted = _explicitly_contradicts_rendered_answer(
            message.content,
            rendered_targets,
        )
        nonaffirmative_echo = _target_mention_is_conditional(
            message.content,
            rendered_targets,
        )
        if _is_raw_structured_answer(message.content):
            nonaffirmative_echo = True
        evidence_diagnostics = (
            None
            if evidence is None
            else {
                "family": evidence["family"],
                "truth_basis": evidence["truth_basis"],
                "accepted_target_forms": _dynamic_target_forms(evidence),
            }
        )
        return (
            0.0 if contradicted or nonaffirmative_echo else score,
            contradicted,
            nonaffirmative_echo,
            evidence_diagnostics,
            evidence,
            rendered_targets,
        )

    scored_messages = [(message, *message_score(message)) for message in messages]
    selected: _RolloutMessage | None = None
    selected_score = 0.0
    selected_contradiction = False
    selected_relation: str | None = None
    selected_numeric_evidence: dict[str, Any] | None = None
    ignored_non_outcome_indices: list[int] = []
    operative_messages: list[tuple[_RolloutMessage, float]] = []
    for (
        message,
        score,
        contradicted,
        nonaffirmative_echo,
        evidence_diagnostics,
        evidence,
        rendered_targets,
    ) in scored_messages:
        after_index = (
            _first_real_user_message_index(execution_context) - 1
            if selected is None
            else selected.sandbox_message_index
        )
        user_context = _dialogue_text_between(
            execution_context,
            after_message_index=after_index,
            before_message_index=message.sandbox_message_index,
            user_only=True,
        )
        dialogue_context = (
            "" if selected is None else selected.content + "\n"
        ) + _dialogue_text_between(
            execution_context,
            after_message_index=after_index,
            before_message_index=message.sandbox_message_index,
        )
        if evidence is not None:
            affirmative_score = (
                score if math.isclose(score, 1.0, rel_tol=0.0, abs_tol=1e-12) else None
            )
        elif _is_frozen_distance_scenario(scenario_name):
            affirmative_score = (
                score if math.isclose(score, 1.0, rel_tol=0.0, abs_tol=1e-12) else None
            )
        else:
            affirmative_score = _generic_affirmative_score(
                message.content,
                scenario_name=scenario_name,
                rendered_targets=rendered_targets,
                similarity_score=score,
            )

        # An exact-looking string in a conditional, raw payload, or explicit
        # denial is not an affirmative answer.  Conditional/raw echoes are
        # OTHER; only a direct contradiction is operative by itself.
        if contradicted or nonaffirmative_echo:
            affirmative_score = None
        same_slot_negative = bool(
            contradicted
            or (
                not nonaffirmative_echo
                and evidence is not None
                and _dynamic_zero_score_is_same_slot(
                    message.content,
                    evidence,
                    user_context=user_context,
                    dialogue_context=dialogue_context,
                )
            )
            or (
                not nonaffirmative_echo
                and evidence is None
                and _generic_zero_score_is_same_slot(
                    message.content,
                    scenario_name=scenario_name,
                    templates=templates,
                    user_context=user_context,
                )
            )
        )

        if affirmative_score is not None:
            selected = message
            selected_score = affirmative_score
            selected_contradiction = False
            selected_relation = "affirm_exact"
            selected_numeric_evidence = evidence_diagnostics
            operative_messages.append((message, affirmative_score))
        elif same_slot_negative:
            selected = message
            selected_score = 0.0
            selected_contradiction = contradicted
            selected_relation = "same_slot_negative_or_conflict"
            selected_numeric_evidence = evidence_diagnostics
            operative_messages.append((message, 0.0))
        elif selected is not None:
            ignored_non_outcome_indices.append(message.sandbox_message_index)

    earlier_conflicts: list[int] = []
    if selected is not None:
        earlier_conflicts = [
            earlier.sandbox_message_index
            for earlier, earlier_score in operative_messages
            if earlier.sandbox_message_index < selected.sandbox_message_index
            and not math.isclose(earlier_score, selected_score, abs_tol=1e-12)
        ]
    return selected_score, {
        "selected_message_index": (
            None if selected is None else selected.sandbox_message_index
        ),
        "earlier_conflicting_message_indices": earlier_conflicts,
        "ignored_later_non_outcome_message_indices": ignored_non_outcome_indices,
        "selected_explicit_target_contradiction": selected_contradiction,
        "selected_answer_relation": selected_relation,
        "selected_dynamic_numeric_evidence": selected_numeric_evidence,
    }


def _score_aligned_answer_milestones(
    scenario: Scenario,
    execution_context: ExecutionContext,
    state_match: _StateOutcomeMatch,
    values: dict[str, list[str]],
    *,
    scenario_name: str,
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
        templates = _outcome_answer_templates(source_matcher.milestones[answer_index])
        score, diagnostics = _score_answer_templates(
            templates,
            segment_messages,
            values,
            execution_context=execution_context,
            scenario=scenario,
            scenario_name=scenario_name,
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
    reason_group_operator = str(contract.get("reason_group_operator", "all"))
    if reason_group_operator == "any":
        has_sufficient_reason = any(reason_matches)
    elif reason_group_operator == "all":
        has_sufficient_reason = bool(reason_matches) and all(reason_matches)
    else:
        raise ValueError(
            f"Unsupported insufficient-information reason operator: "
            f"{reason_group_operator!r}"
        )
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
    if has_sufficient_reason:
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
    r"(?<![A-Za-z0-9_])-?(?:\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.\d+)?(?:[eE][+-]?\d+)?(?![A-Za-z0-9_])"
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

    if kind == "frozen_golden_gate_distance":
        verified = bool(_frozen_golden_gate_distance_answer_score(content))
        diagnostics["matched_value"] = (
            _FROZEN_GOLDEN_GATE_DISTANCE_KM_VALUES if verified else None
        )
        diagnostics["answer_truth_basis"] = "pinned_fixture_distance_contract"
        return float(verified), diagnostics

    context_groups = tuple(
        tuple(str(value) for value in group) for group in spec.get("context_groups", ())
    )
    if kind == "grounded_temperature":
        required_response_unit = spec.get("required_response_unit")
        diagnostics["response_unit"] = _temperature_unit_from_text(content)
        diagnostics["required_response_unit"] = required_response_unit
        if not _has_required_answer_context(content, context_groups):
            return 0.0, diagnostics
        family_name = spec.get("dynamic_temperature_family")
        evidences: list[dict[str, Any]] = []
        if family_name is not None:
            family_contract = _DYNAMIC_NUMERIC_SCENARIO_FAMILIES.get(str(family_name))
            if family_contract is None:
                return 0.0, diagnostics
            evidences.append(
                _temperature_contract_evidence(str(family_name), family_contract)
            )
        else:
            expected_values_by_unit = cast(
                dict[str, dict[str, Any]],
                spec["expected_values_by_unit"],
            )

            def expected_values(unit: str) -> tuple[float, ...]:
                expectation = expected_values_by_unit.get(unit, {})
                raw_values = expectation.get("values")
                if raw_values is None and expectation.get("value") is not None:
                    raw_values = (expectation["value"],)
                return tuple(float(value) for value in (raw_values or ()))

            celsius_values = expected_values("celsius")
            fahrenheit_values = expected_values("fahrenheit")
            if len(celsius_values) != len(fahrenheit_values):
                return 0.0, diagnostics
            requested_units = (
                (str(required_response_unit),)
                if required_response_unit is not None
                else ("celsius", "fahrenheit")
            )
            target_terms = tuple(
                dict.fromkeys(
                    (
                        *_target_terms_from_context_groups(context_groups),
                        "temperature",
                        "minimum temperature",
                    )
                )
            )
            for target_unit in requested_units:
                source_unit = "fahrenheit" if target_unit == "celsius" else "celsius"
                target_values = (
                    celsius_values if target_unit == "celsius" else fahrenheit_values
                )
                source_values = (
                    fahrenheit_values if target_unit == "celsius" else celsius_values
                )
                evidences.append(
                    {
                        "family": f"information_{base_name}_{target_unit}",
                        "kind": "temperature",
                        "placeholder": "temperature",
                        "source_unit": source_unit,
                        "target_unit": target_unit,
                        "pairs": tuple(
                            {
                                "source_value": source_value,
                                "source_forms": tuple(_normalize_value(source_value)),
                                "target_value": target_value,
                                "target_forms": tuple(_normalize_value(target_value)),
                            }
                            for source_value, target_value in zip(
                                source_values,
                                target_values,
                            )
                        ),
                        "target_terms": target_terms,
                        "truth_basis": "static_information_temperature_contract",
                    }
                )
        for evidence in evidences:
            if required_response_unit is not None and str(
                evidence["target_unit"]
            ) != str(required_response_unit):
                continue
            if _temperature_dynamic_answer_score(
                ["The temperature is {temperature} degrees"],
                content,
                evidence,
            ):
                diagnostics["matched_value"] = evidence["family"]
                diagnostics["matched_unit"] = evidence["target_unit"]
                diagnostics["answer_truth_basis"] = evidence["truth_basis"]
                return 1.0, diagnostics
        return 0.0, diagnostics

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
        if christmas <= inferred_now:
            christmas = _dt.datetime(inferred_now.year + 1, 12, 25)
        derived = (christmas - inferred_now).days
        evidence = {
            "kind": "days",
            "placeholder": "days",
            "target_forms": (str(derived),),
            "holiday_years": (str(christmas.year),),
            "holiday_month": christmas.month,
            "holiday_day": christmas.day,
            "target_terms": _target_terms_from_context_groups(context_groups),
        }
        verified = _days_dynamic_answer_score(
            content,
            evidence,
            permits_bare_answer=False,
            required_context_groups=context_groups,
        )
        diagnostics["matched_value"] = float(derived) if verified else None
        return float(verified), diagnostics
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
    expected = float(contract["expected_value"])
    tolerance = float(contract["absolute_tolerance"])
    context_groups = tuple(
        tuple(str(value) for value in group) for group in contract["context_groups"]
    )
    allowed_context_values = tuple(
        float(value) for value in contract.get("allowed_context_values", ())
    )

    def scalar_numeric_content(content: str) -> str:
        # Canonical currency prompts and answers use ``$2.048k`` for the
        # 2048-USD input.  Expand only a number that is actually coupled to the
        # magnitude suffix; a bare ``2.048 USD`` must remain a conflicting
        # number rather than inheriting the shorthand's meaning.
        def expand_thousands(match: re.Match[str]) -> str:
            value = float(match.group("value")) * 1000.0
            return str(int(value)) if value.is_integer() else str(value)

        normalized = re.sub(
            r"(?<![A-Za-z0-9_])(?P<value>\d+(?:\.\d+)?)\s*[kK]\b",
            expand_thousands,
            content,
        )
        if base_name == "find_thanksgiving_timestamp":
            # Date components form one semantic context slot.  Remove only the
            # exact human-readable date denoted by the frozen timestamp; an
            # incorrect month/day/year remains visible and invalidates the
            # otherwise numerically correct timestamp claim.
            normalized = re.sub(
                r"\b(?:november|nov\.?)\s+26(?:th)?\s*,?\s*2026\b|"
                r"(?<!\d)11\s*[/\-]\s*26\s*[/\-]\s*2026(?!\d)",
                " ",
                normalized,
                flags=re.IGNORECASE,
            )
        return normalized

    def message_score(message: _RolloutMessage) -> float:
        content = re.sub(
            r"^\s*if\s+you\s+have\s+no\s+further\s+information\s*,\s*",
            "",
            message.content,
            count=1,
            flags=re.IGNORECASE,
        )
        content = scalar_numeric_content(content)
        verified, _ = _matches_one_exact_number(
            content,
            [expected],
            tolerance=tolerance,
            context_groups=context_groups,
            allowed_context_values=allowed_context_values,
        )
        return float(verified)

    def is_outcome_bearing(message: _RolloutMessage, score: float) -> bool:
        """Keep answers and substantive corrections, but skip generic follow-ups."""
        if score:
            return True
        content = scalar_numeric_content(message.content.replace("’", "'"))
        normalized = _normalized_phrase_text(content)
        target_terms = _target_terms_from_context_groups(context_groups)
        observed_numbers = _numbers_in_text(content)
        has_non_context_number = any(
            not any(
                math.isclose(value, allowed, rel_tol=0.0, abs_tol=0.0)
                for allowed in allowed_context_values
            )
            for value in observed_numbers
        )
        if observed_numbers and (
            has_non_context_number
            or re.fullmatch(
                rf"\s*{_SCALAR_NUMBER_RE.pattern}\s*(?:[.!?])?\s*",
                content,
                flags=re.IGNORECASE,
            )
            or re.search(
                r"\b(?:correction|actually|instead|rather)\b",
                content,
                flags=re.IGNORECASE,
            )
        ):
            return True
        target_pattern = "|".join(re.escape(term) for term in target_terms if term)
        if _LATER_RETRACTION_RE.search(content.strip()):
            return True
        if not target_pattern:
            return False
        return bool(
            re.search(
                rf"\b(?:answer|result|value|{target_pattern})\b[^.!?;]{{0,80}}"
                r"\b(?:wrong|incorrect|false|unknown|unavailable|not correct)\b|"
                r"\b(?:i|we)\s+(?:cannot|can't|do not|don't|could not|couldn't)"
                rf"[^.!?;]{{0,80}}\b(?:answer|provide|determine|{target_pattern})\b|"
                rf"\b(?:i(?:'m| am)|we(?:'re| are))\s+unable[^.!?;]{{0,80}}"
                rf"\b(?:answer|provide|determine|{target_pattern})\b",
                content,
                flags=re.IGNORECASE,
            )
        )

    scored_messages = [(message, message_score(message)) for message in messages]
    outcome_messages = [
        (message, score)
        for message, score in scored_messages
        if is_outcome_bearing(message, score)
    ]
    if outcome_messages:
        selected, selected_score = outcome_messages[-1]
    elif scored_messages:
        selected, selected_score = scored_messages[-1]
    else:
        selected, selected_score = None, 0.0
    ignored_later = (
        []
        if selected is None
        else [
            message.sandbox_message_index
            for message, score in scored_messages
            if message.sandbox_message_index > selected.sandbox_message_index
            and not is_outcome_bearing(message, score)
        ]
    )
    earlier_conflicts = (
        []
        if selected is None
        else [
            message.sandbox_message_index
            for message, score in scored_messages
            if message.sandbox_message_index < selected.sandbox_message_index
            and not math.isclose(score, selected_score, abs_tol=1e-12)
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
        "ignored_later_non_outcome_message_indices": ignored_later,
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
            cast(Any, contract["achievable_state_outcome"]),
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

    values = _placeholder_values(execution_context)
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
        scenario_name=scenario_name,
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
        templates = _outcome_answer_templates(milestone)
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
