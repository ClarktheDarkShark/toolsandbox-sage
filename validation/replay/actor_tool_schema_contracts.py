"""Black-box contracts for the actor's routed-tool schema boundary.

This module deliberately calls the accepted private compatibility functions
rather than mirroring their implementation.  It is validation-only: live SAGE
never imports it.  The contract freezes results, exception behavior, schema
order, alias handling, and the set-derived ordering used by generated-tool
selection while remaining independent of any proposed ``ToolSchemaFacts``
implementation.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from collections.abc import Iterator, Mapping
from typing import Any, Callable


def _mixed_case_value(value: str) -> str:
    upper_next = True
    result: list[str] = []
    for character in value:
        if character.isalpha():
            result.append(character.upper() if upper_next else character.lower())
            upper_next = not upper_next
        else:
            result.append(character)
    return "".join(result)


def _case_variant(value: str, casing: str) -> str:
    if casing == "lowercase":
        return value
    if casing == "uppercase":
        return value.upper()
    if casing == "mixed_case":
        return _mixed_case_value(value)
    raise ValueError(f"unknown field-matrix casing: {casing}")


CONTRACT_SCHEMA_VERSION = 1

COLLECTION_OPERATIONS = (
    "_tool_names",
    "_tool_names_execution_facing",
    "_generated_tool_names_execution_facing",
    "_selector_tool_names",
    "_derived_value_tool_names",
    "_lookup_query_planner_tool_names",
    "_search_window_tool_names",
    "_relative_time_tool_names",
    "_scheduling_timestamp_tool_names",
    "_state_action_planner_tool_names",
    "_validation_abstention_tool_names",
    "_action_argument_helper_tool_names",
    "_post_selection_action_helper_tool_names",
)

CATEGORY_OPERATIONS = COLLECTION_OPERATIONS[3:]

TARGET_OPERATIONS = (
    "_tool_input_names_execution_facing",
    "_tool_output_names_execution_facing",
    "_tool_description_execution_facing",
    "_tool_name_for_call",
    "_declared_service_answer_producers",
)

INDIVIDUAL_SCHEMA_OPERATIONS = (
    "_tool_schema_execution_name",
    "_tool_schema_text",
)

CATEGORY_BRANCH_CASE_IDS = (
    "category_branches_selector",
    "category_branches_derived_value",
    "category_branches_lookup_query_planner",
    "category_branches_search_window",
    "category_branches_relative_time",
    "category_branches_scheduling_timestamp",
    "category_branches_state_action_planner",
    "category_branches_validation_abstention",
    "category_branches_action_argument_helper",
    "category_branches_post_selection_action_helper",
)

FIELD_NORMALIZATION_CASE_IDS = tuple(
    case_id.replace("category_branches_", "field_normalization_", 1)
    for case_id in CATEGORY_BRANCH_CASE_IDS
)

EXPECTED_CASE_IDS = (
    "normal_catalog",
    "aliases_and_duplicates",
    "output_schema_boundaries",
    "mapping_and_malformed_members",
    "not_given",
    "empty",
    *CATEGORY_BRANCH_CASE_IDS,
    *FIELD_NORMALIZATION_CASE_IDS,
    "producer_schema_locations",
)

# Filled from the immutable reference with ordering-sensitive fields normalized
# only where CPython set iteration legitimately depends on PYTHONHASHSEED.
EXPECTED_CANONICAL_SHA256 = (
    "dd8dafed28379b32f189637409442c4c8d3b2817a3dd4dc99507d9cedb8cab4a"
)
EXPECTED_HASHSEED_ZERO_BODY_SHA256 = (
    "b3e3377fb1f84b92d14b8f89e477f82aa7c8dc9730b247c07b3983fcfa65c737"
)
EXPECTED_HASHSEED_ZERO_ORDER_SHA256 = (
    "5d6d0df27cce6e9245eda9eaf4f83ae748f715b14331caebb7ada711d604bc52"
)

FIXTURE_SIDE_EFFECT_TOOL_NAMES = (
    "add_contact",
    "modify_contact",
    "remove_contact",
    "set_cellular_service_status",
    "set_location_service_status",
    "set_low_battery_mode_status",
    "set_wifi_status",
    "send_message_with_phone_number",
    "add_reminder",
    "modify_reminder",
    "remove_reminder",
)
FIXTURE_READ_ONLY_NATIVE_TOOL_NAMES = (
    "search_contacts",
    "search_messages",
    "get_wifi_status",
    "search_weather_around_lat_lon",
    "convert_currency",
    "get_current_timestamp",
)
FIXTURE_SERVICE_PRODUCER_NAMES = (
    "search_location_around_lat_lon",
    "search_lat_lon",
    "search_weather_around_lat_lon",
    "calculate_lat_lon_distance",
    "convert_currency",
    "unit_conversion",
)

EXPECTED_ORIGINAL_SIDE_EFFECT_TOOL_NAMES = tuple(sorted(FIXTURE_SIDE_EFFECT_TOOL_NAMES))
EXPECTED_SERVICE_ANSWER_PRODUCER_TOOLS = tuple(sorted(FIXTURE_SERVICE_PRODUCER_NAMES))
EXPECTED_ORIGINAL_TOOLSANDBOX_TOOL_NAMES = tuple(
    sorted(
        (
            "add_contact",
            "add_reminder",
            "calculate_lat_lon_distance",
            "convert_currency",
            "datetime_info_to_timestamp",
            "end_conversation",
            "get_cellular_service_status",
            "get_current_location",
            "get_current_timestamp",
            "get_location_service_status",
            "get_low_battery_mode_status",
            "get_wifi_status",
            "modify_contact",
            "modify_reminder",
            "remove_contact",
            "remove_reminder",
            "search_contacts",
            "search_holiday",
            "search_lat_lon",
            "search_location_around_lat_lon",
            "search_messages",
            "search_reminder",
            "search_stock",
            "search_weather_around_lat_lon",
            "seconds_to_hours_minutes_seconds",
            "send_message_with_phone_number",
            "set_cellular_service_status",
            "set_location_service_status",
            "set_low_battery_mode_status",
            "set_wifi_status",
            "shift_timestamp",
            "timestamp_diff",
            "timestamp_to_datetime_info",
            "unit_conversion",
        )
    )
)

EXACT_NAMES_BY_CATEGORY_CASE: dict[str, tuple[str, ...]] = {
    "category_branches_selector": (),
    "category_branches_derived_value": (),
    "category_branches_lookup_query_planner": (),
    "category_branches_search_window": (
        "prepare_message_recency_search_args",
        "prepare_past_reminder_recency_search_args",
        "resolve_search_window_or_bounds",
        "prepare_upcoming_reminder_search_args",
    ),
    "category_branches_relative_time": ("relative_day_time_to_timestamp",),
    "category_branches_scheduling_timestamp": (
        "next_weekday_time_to_timestamp",
        "relative_weeks_time_to_timestamp",
        "weeks_from_now_time_to_timestamp",
        "week_delta_time_to_timestamp",
        "weekday_delta_time_to_timestamp",
    ),
    "category_branches_state_action_planner": ("next_service_tool_call",),
    "category_branches_validation_abstention": ("prepare_safe_action_or_abstain",),
    "category_branches_action_argument_helper": (),
    "category_branches_post_selection_action_helper": (),
}

SUBSET_REQUIRED_FIELDS_BY_CATEGORY_CASE: dict[
    str,
    tuple[tuple[str, tuple[str, ...]], ...],
] = {
    "category_branches_selector": (),
    "category_branches_derived_value": (),
    "category_branches_lookup_query_planner": (),
    "category_branches_search_window": (
        (
            "subset_extra_complete_search_window",
            (
                "current_timestamp",
                "phrase",
                "target_domain",
                "timestamp_intent",
                "direction",
            ),
        ),
    ),
    "category_branches_relative_time": (
        (
            "subset_extra_relative_time",
            ("current_timestamp", "day_offset", "hour", "minute"),
        ),
    ),
    "category_branches_scheduling_timestamp": (
        (
            "subset_extra_scheduling_timestamp",
            (
                "current_timestamp",
                "hour",
                "minute",
                "local_utc_offset_hours",
            ),
        ),
    ),
    "category_branches_state_action_planner": (
        (
            "subset_extra_classic_state_action",
            ("user_request", "visible_state_or_error"),
        ),
        (
            "subset_extra_structured_state_action",
            ("target_service", "desired_on"),
        ),
    ),
    "category_branches_validation_abstention": (
        (
            "subset_extra_validation_abstention",
            (
                "user_request",
                "requested_action",
                "required_original_tools",
                "available_original_tools",
            ),
        ),
    ),
    "category_branches_action_argument_helper": (),
    "category_branches_post_selection_action_helper": (),
}

NON_SUBSET_INPUT_FIELDS_BY_CATEGORY_CASE: dict[
    str,
    tuple[tuple[str, tuple[str, ...]], ...],
] = {
    "category_branches_selector": (
        ("membership_extra_selector_records", ("records",)),
    ),
    "category_branches_derived_value": (),
    "category_branches_lookup_query_planner": (
        ("membership_extra_lookup_inputs", ("query",)),
    ),
    "category_branches_search_window": (
        ("membership_extra_current_timestamp", ("current_timestamp",)),
    ),
    "category_branches_relative_time": (),
    "category_branches_scheduling_timestamp": (),
    "category_branches_state_action_planner": (
        ("membership_multi_next_service_inputs", ("target_service",)),
    ),
    "category_branches_validation_abstention": (),
    "category_branches_action_argument_helper": (
        ("membership_extra_action_inputs", ("user_request",)),
    ),
    "category_branches_post_selection_action_helper": (
        ("membership_multi_post_selection_inputs", ("selected_record",)),
    ),
}

FIELD_MATRIX_FIELDS = (
    "raw_name",
    "execution_name",
    "description",
    "input_property",
    "direct_output_property",
    "nested_output_property",
    "schema_json",
)
FIELD_MATRIX_CASINGS = ("lowercase", "uppercase", "mixed_case")

FIELD_NORMALIZATION_PLANS: dict[str, dict[str, Any]] = {
    "category_branches_selector": {
        "operation": "_selector_tool_names",
        "lexical_token": "selected_record",
        "lexical_read_fields": ("description",),
        "structural_token": "records",
        "structural_read_fields": ("input_property",),
    },
    "category_branches_derived_value": {
        "operation": "_derived_value_tool_names",
        "lexical_token": "d_extract_custom",
        "lexical_read_fields": ("raw_name", "description"),
        "structural_token": "payload",
        "structural_read_fields": ("input_property",),
    },
    "category_branches_lookup_query_planner": {
        "operation": "_lookup_query_planner_tool_names",
        "lexical_token": "query planner",
        "lexical_read_fields": ("raw_name", "description"),
        "structural_token": "search_records_kwargs",
        "structural_read_fields": ("direct_output_property",),
    },
    "category_branches_search_window": {
        "operation": "_search_window_tool_names",
        "lexical_token": "bounded search",
        "lexical_read_fields": ("description",),
        "structural_token": "current_timestamp",
        "structural_read_fields": ("input_property",),
    },
    "category_branches_relative_time": {
        "operation": "_relative_time_tool_names",
        "lexical_token": "tomorrow",
        "lexical_read_fields": ("raw_name", "description"),
        "structural_token": "current_timestamp",
        "structural_read_fields": ("input_property",),
    },
    "category_branches_scheduling_timestamp": {
        "operation": "_scheduling_timestamp_tool_names",
        "lexical_token": "scheduling",
        "lexical_read_fields": ("description",),
        "structural_token": "current_timestamp",
        "structural_read_fields": ("input_property",),
    },
    "category_branches_state_action_planner": {
        "operation": "_state_action_planner_tool_names",
        "lexical_token": "state action sequence",
        "lexical_read_fields": ("description",),
        "structural_token": "visible_state_or_error",
        "structural_read_fields": ("input_property",),
    },
    "category_branches_validation_abstention": {
        "operation": "_validation_abstention_tool_names",
        "lexical_token": "safe action",
        "lexical_read_fields": ("description",),
        "structural_token": "available_original_tools",
        "structural_read_fields": ("input_property",),
    },
    "category_branches_action_argument_helper": {
        "operation": "_action_argument_helper_tool_names",
        "lexical_token": "prepare final",
        "lexical_read_fields": ("raw_name", "description"),
        "structural_token": "user_request",
        "structural_read_fields": ("input_property",),
    },
    "category_branches_post_selection_action_helper": {
        "operation": "_post_selection_action_helper_tool_names",
        "lexical_token": "side-effect",
        "lexical_read_fields": ("raw_name", "description"),
        "structural_token": "selected_record",
        "structural_read_fields": ("input_property",),
    },
}

STRUCTURAL_CASE_INSENSITIVE_FIELDS_BY_CATEGORY_CASE = {
    case_id: (
        ("input_property",)
        if case_id
        in {
            "category_branches_derived_value",
            "category_branches_action_argument_helper",
        }
        else ()
    )
    for case_id in CATEGORY_BRANCH_CASE_IDS
}

ADDITIONAL_FIELD_TOKEN_PLANS_BY_CATEGORY_CASE: dict[
    str,
    tuple[tuple[str, str, tuple[str, ...]], ...],
] = {
    case_id: (
        (
            (
                "raw_selector_select",
                "select",
                ("raw_name",),
            ),
        )
        if case_id == "category_branches_selector"
        else (
            (
                "raw_state_plan_prefix",
                "plan_device_state_action_sequence_custom",
                ("raw_name",),
            ),
            (
                "raw_state_apply_prefix",
                "apply_single_device_state_action_custom",
                ("raw_name",),
            ),
        )
        if case_id == "category_branches_state_action_planner"
        else ()
    )
    for case_id in CATEGORY_BRANCH_CASE_IDS
}


def _field_token_plans(
    category_case_id: str,
) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    plan = FIELD_NORMALIZATION_PLANS[category_case_id]
    return (
        (
            "lexical",
            str(plan["lexical_token"]),
            tuple(plan["lexical_read_fields"]),
        ),
        (
            "structural",
            str(plan["structural_token"]),
            tuple(plan["structural_read_fields"]),
        ),
        *ADDITIONAL_FIELD_TOKEN_PLANS_BY_CATEGORY_CASE[category_case_id],
    )


EXACT_EXECUTION_ALIAS_RAW_BY_NAME: dict[str, str] = {}
_exact_alias_index = 1
for _case_id in CATEGORY_BRANCH_CASE_IDS:
    for _exact_name in EXACT_NAMES_BY_CATEGORY_CASE[_case_id]:
        EXACT_EXECUTION_ALIAS_RAW_BY_NAME[_exact_name] = (
            "relative_alias_custom"
            if _exact_name == "relative_day_time_to_timestamp"
            else f"category_exact_alias_{_exact_alias_index:02d}"
        )
        _exact_alias_index += 1


def _field_execution_alias_raw(
    category_case_id: str,
    token_kind: str,
    casing: str,
) -> str:
    case_index = CATEGORY_BRANCH_CASE_IDS.index(category_case_id) + 1
    token_index = next(
        index
        for index, (candidate_kind, _token, _fields) in enumerate(
            _field_token_plans(category_case_id),
            start=1,
        )
        if candidate_kind == token_kind
    )
    casing_index = FIELD_MATRIX_CASINGS.index(casing) + 1
    return f"fm_alias_{case_index:02d}_{token_index:02d}_{casing_index:02d}"


FIELD_EXECUTION_ALIASES = {
    _field_execution_alias_raw(category_case_id, token_kind, casing): _case_variant(
        token,
        casing,
    )
    for category_case_id in FIELD_NORMALIZATION_PLANS
    for token_kind, token, _read_fields in _field_token_plans(category_case_id)
    for casing in FIELD_MATRIX_CASINGS
}

ACTION_ARGUMENT_PREPARATION_MARKERS = (
    "prepare the arguments",
    "prepares the arguments",
    "prepare arguments",
    "prepares arguments",
    "prepare the call",
    "prepares the call",
    "prepare final",
    "prepares final",
    "prepare exact kwargs",
    "prepares exact kwargs",
    "safe downstream kwargs",
    "downstream_tool_kwargs",
    "side-effect",
    "action argument",
)
ACTION_ARGUMENT_RETURN_MARKERS = (
    "should_call_tool",
    "should_call_add_reminder",
    "downstream tool",
    "downstream_tool_name",
    "downstream_tool_kwargs",
    "original toolsandbox",
    *EXPECTED_ORIGINAL_SIDE_EFFECT_TOOL_NAMES,
)
POST_SELECTION_ACTION_MARKERS = (
    "downstream_tool_kwargs",
    "side-effect",
    "prepare arguments",
    "prepare the arguments",
    "prepares the arguments",
    "prepare the call",
    "prepares the call",
    "safe downstream kwargs",
    "selected record",
    *EXPECTED_ORIGINAL_SIDE_EFFECT_TOOL_NAMES,
)

# Frozen from every category predicate in the accepted actor that searches the
# joined raw-name/description string. Categories absent from this tuple inspect
# those fields separately (or do not inspect one of them).
JOINED_NAME_DESCRIPTION_MARKERS_BY_CATEGORY_CASE = {
    "category_branches_derived_value": (
        "extract",
        "normalize",
        "canonicalize",
        "deterministic extraction",
    ),
    "category_branches_lookup_query_planner": (
        "search_contacts_kwargs",
        "lookup query",
        "query planner",
        "prepare search",
        "search kwargs",
    ),
    "category_branches_relative_time": (
        "relative local day",
        "relative day",
        "tomorrow",
        "timestamp",
    ),
    "category_branches_action_argument_helper": (
        *ACTION_ARGUMENT_PREPARATION_MARKERS,
        *ACTION_ARGUMENT_RETURN_MARKERS,
    ),
    "category_branches_post_selection_action_helper": (*POST_SELECTION_ACTION_MARKERS,),
}
JOINED_NAME_DESCRIPTION_CATEGORY_CASES = tuple(
    case_id
    for case_id in CATEGORY_BRANCH_CASE_IDS
    if case_id in JOINED_NAME_DESCRIPTION_MARKERS_BY_CATEGORY_CASE
)
CROSS_FIELD_COMPOSITION_MARKERS_BY_CATEGORY_CASE = {
    case_id: tuple(
        marker
        for marker in JOINED_NAME_DESCRIPTION_MARKERS_BY_CATEGORY_CASE.get(case_id, ())
        if " " in marker
    )
    for case_id in CATEGORY_BRANCH_CASE_IDS
}
CROSS_FIELD_COMPOSITION_VARIANTS = (
    "forward_lowercase",
    "forward_uppercase_description",
    "uppercase_raw_name",
    "reverse_field_order",
    "raw_name_leading_space",
    "raw_name_trailing_space",
    "description_leading_space",
    "description_trailing_space",
    "execution_alias_raw_name",
)
JOINED_FIELD_WHITESPACE_EDGE_VARIANTS = (
    "raw_name_leading_space",
    "raw_name_trailing_space",
    "description_leading_space",
    "description_trailing_space",
)
JOINED_FIELD_WHITESPACE_INTERNAL_PLACEMENTS = (
    "raw_name_internal_double_space",
    "description_internal_double_space",
)


def _cross_field_marker_splits(marker: str) -> tuple[tuple[str, str], ...]:
    words = marker.split()
    return tuple(
        (" ".join(words[:boundary]), " ".join(words[boundary:]))
        for boundary in range(1, len(words))
    )


def _cross_field_alias_raw_name(
    category_case_id: str,
    marker_index: int,
    split_index: int,
) -> str:
    case_index = CATEGORY_BRANCH_CASE_IDS.index(category_case_id) + 1
    return f"cross_field_alias_{case_index:02d}_{marker_index:02d}_{split_index:02d}"


CROSS_FIELD_EXECUTION_ALIASES = {
    _cross_field_alias_raw_name(category_case_id, marker_index, split_index): (
        f"cross_field_execution_{CATEGORY_BRANCH_CASE_IDS.index(category_case_id) + 1:02d}_"
        f"{left}"
    )
    for category_case_id in CATEGORY_BRANCH_CASE_IDS
    for marker_index, marker in enumerate(
        CROSS_FIELD_COMPOSITION_MARKERS_BY_CATEGORY_CASE[category_case_id],
        start=1,
    )
    for split_index, (left, _right) in enumerate(
        _cross_field_marker_splits(marker),
        start=1,
    )
}

# The accepted derived predicate's only space-bearing phrase is not observably
# dependent on joining: ``extraction`` already contains its separate ``extract``
# marker. The composition fixture records this masking instead of pretending a
# joined-only counterexample exists.
CROSS_FIELD_MASK_REASONS = {
    (
        "category_branches_derived_value",
        "deterministic extraction",
    ): "description 'extraction' independently matches marker 'extract'",
}

DERIVED_SCHEMA_TYPE_VALUES = (
    "object",
    "array",
    "string",
    "number",
    "integer",
    "boolean",
)
DERIVED_SCHEMA_TYPE_CASINGS = FIELD_MATRIX_CASINGS


class MappingOnly(Mapping[str, Any]):
    """Stable non-dict Mapping used to freeze dict-vs-Mapping behavior."""

    def __init__(self, values: Mapping[str, Any]) -> None:
        self._values = dict(values)

    def __getitem__(self, key: str) -> Any:
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        return f"MappingOnly({self._values!r})"

    def __deepcopy__(self, memo: dict[int, Any]) -> MappingOnly:
        return type(self)(copy.deepcopy(self._values, memo))


class ExplodingMapping(MappingOnly):
    """Mapping whose ``get`` preserves the current propagation boundary."""

    def get(self, key: str, default: Any = None) -> Any:
        raise RuntimeError(f"schema_get_exploded:{key}")


class NameMappingContext:
    """Deterministic raw/agent/execution tool-name mapping fixture."""

    execution_aliases = {
        "agent_native_search": "functions.search_contacts",
        "agent_generated_primary": "functions.generated_exec",
        "agent_generated_secondary": "generated_exec",
        "agent_mapping_function": "mapping_function_exec",
        "agent_mapping_parameters": "mapping_parameters_exec",
        **{
            f"producer_alias_{index:02d}_first": f"producer_alias_{index:02d}_exec"
            for index, _producer in enumerate(
                FIXTURE_SERVICE_PRODUCER_NAMES,
                start=1,
            )
        },
        **{
            f"producer_alias_{index:02d}_second": f"producer_alias_{index:02d}_exec"
            for index, _producer in enumerate(
                FIXTURE_SERVICE_PRODUCER_NAMES,
                start=1,
            )
        },
        **{
            raw_alias: exact_name
            for exact_name, raw_alias in EXACT_EXECUTION_ALIAS_RAW_BY_NAME.items()
        },
        **FIELD_EXECUTION_ALIASES,
        **CROSS_FIELD_EXECUTION_ALIASES,
    }
    agent_aliases = {
        "missing_generated": "agent_missing_generated",
        "generated_exec": "agent_generated_fallback",
    }

    def get_execution_facing_tool_name(self, name: str) -> str:
        if name == "execution_mapping_error":
            raise RuntimeError("execution_name_mapping_failed")
        return self.execution_aliases.get(name, name)

    def get_agent_facing_tool_name(self, name: str) -> str:
        if name == "agent_mapping_error":
            raise RuntimeError("agent_name_mapping_failed")
        return self.agent_aliases.get(name, name)


def _schema(
    name: Any,
    *,
    description: Any = "",
    properties: Any = None,
    output_properties: Any = None,
    nested_output_properties: Any = None,
    function_factory: Callable[[Mapping[str, Any]], Any] = dict,
    parameters_factory: Callable[[Mapping[str, Any]], Any] = dict,
    outer_factory: Callable[[Mapping[str, Any]], Any] = dict,
) -> Any:
    parameters_values: dict[str, Any] = {
        "type": "object",
        "properties": {} if properties is None else properties,
    }
    if nested_output_properties is not None:
        parameters_values["output_schema"] = {
            "type": "object",
            "properties": nested_output_properties,
        }
    function_values: dict[str, Any] = {
        "name": name,
        "description": description,
        "parameters": parameters_factory(parameters_values),
    }
    if output_properties is not None:
        function_values["output_schema"] = {
            "type": "object",
            "properties": output_properties,
        }
    return outer_factory(
        {"type": "function", "function": function_factory(function_values)}
    )


def _normal_catalog() -> list[Any]:
    string = {"type": "string"}
    number = {"type": "number"}
    integer = {"type": "integer"}
    mapping = {"type": "object"}
    records = {"type": "array", "items": {"type": "object"}}
    return [
        _schema("search_contacts", properties={"name": string}),
        _schema(
            "generated_visible_selector",
            description="Deterministic visible-record constraint selection.",
            properties={"records": records, "selection_mode": string},
        ),
        _schema(
            "generated_payload_extractor",
            description="Deterministic extraction and normalization helper.",
            properties={"service_payload": mapping, "requested_unit": string},
        ),
        _schema(
            "generated_lookup_planner",
            description="Lookup query planner returning search_contacts_kwargs.",
            properties={"contact_name": string},
            output_properties={"search_contacts_kwargs": mapping},
        ),
        _schema(
            "resolve_search_window_or_bounds",
            description="Prepare bounded search kwargs from a recency phrase.",
            properties={
                "current_timestamp": number,
                "phrase": string,
                "target_domain": string,
                "timestamp_intent": string,
                "direction": string,
            },
        ),
        _schema(
            "relative_day_time_to_timestamp",
            description="Convert a relative local day to a timestamp.",
            properties={
                "current_timestamp": number,
                "day_offset": integer,
                "hour": integer,
                "minute": integer,
            },
        ),
        _schema(
            "next_weekday_time_to_timestamp",
            description="Produce a reminder_timestamp for weekday scheduling.",
            properties={
                "current_timestamp": number,
                "hour": integer,
                "minute": integer,
                "local_utc_offset_hours": number,
            },
        ),
        _schema(
            "plan_device_state_action_sequence",
            description="Plan a device-state setter sequence.",
            properties={"user_request": string, "visible_state_or_error": mapping},
        ),
        _schema(
            "prepare_safe_action_or_abstain",
            description="Prepare a safe action or abstain for insufficient information.",
            properties={
                "user_request": string,
                "requested_action": string,
                "required_original_tools": records,
                "available_original_tools": records,
            },
        ),
        _schema(
            "prepare_contact_action_args",
            description=(
                "Prepare the arguments and downstream_tool_kwargs for an original "
                "modify_contact side-effect call."
            ),
            properties={"user_request": string},
        ),
        _schema(
            "prepare_selected_contact_action",
            description="Prepare arguments for a selected record side-effect.",
            properties={"selected_record": mapping, "requested_action": string},
        ),
        _schema(
            "extract_service_answer_field",
            description=(
                "Deterministic extraction helper. First call one declared original "
                "producer: search_weather_around_lat_lon or calculate_lat_lon_distance."
            ),
            properties={"service_payload": mapping, "requested_field": string},
        ),
        _schema("add_reminder", properties={"content": string}),
    ]


def _alias_and_duplicate_schemas() -> list[Any]:
    string = {"type": "string"}
    return [
        _schema("agent_native_search", properties={"first_native": string}),
        _schema(
            "agent_generated_primary",
            description="Deterministic extraction helper.",
            properties={"first_input": string},
            output_properties={"first_output": string},
        ),
        _schema(
            "agent_generated_secondary",
            description="Visible-record constraint selection.",
            properties={"records": {"type": "array"}, "second_input": string},
            output_properties={"second_output": string},
        ),
        _schema(
            "agent_generated_primary",
            description="Duplicate raw name should not replace the first schema.",
            properties={"duplicate_raw_input": string},
            output_properties={"duplicate_raw_output": string},
        ),
    ]


def _output_schema_boundaries() -> list[Any]:
    string = {"type": "string"}
    direct_and_nested = _schema(
        "direct_and_nested",
        properties={"input_a": string},
        output_properties={"direct_output": string},
        nested_output_properties={"nested_output": string},
    )
    nested_only = _schema(
        "nested_only",
        properties={"input_b": string},
        nested_output_properties={"nested_only_output": string},
    )
    empty_direct = _schema(
        "empty_direct",
        properties={"input_c": string},
        output_properties={},
        nested_output_properties={"fallback_nested_output": string},
    )
    empty_direct["function"]["output_schema"] = {}
    malformed_direct = _schema(
        "malformed_direct",
        properties={"input_d": string},
        nested_output_properties={"ignored_nested_output": string},
    )
    malformed_direct["function"]["output_schema"] = "truthy-not-a-mapping"
    direct_planner = _schema(
        "direct_output_planner",
        properties={"query": string},
        output_properties={"search_contacts_kwargs": {"type": "object"}},
    )
    nested_planner = _schema(
        "nested_output_only_planner",
        properties={"query": string},
        nested_output_properties={"search_contacts_kwargs": {"type": "object"}},
    )
    return [
        direct_and_nested,
        nested_only,
        empty_direct,
        malformed_direct,
        direct_planner,
        nested_planner,
    ]


def _mapping_and_malformed_members() -> list[Any]:
    string = {"type": "string"}
    mapping_function = _schema(
        "agent_mapping_function",
        description="Deterministic extraction helper.",
        properties={"mapping_function_input": string},
        function_factory=MappingOnly,
    )
    mapping_parameters = _schema(
        "agent_mapping_parameters",
        description="Deterministic extraction helper.",
        properties={"mapping_parameter_input": string},
        parameters_factory=MappingOnly,
    )
    mapping_outer = _schema(
        "mapping_outer",
        description="Deterministic extraction helper.",
        properties={"outer_input": string},
        outer_factory=MappingOnly,
    )
    return [
        mapping_function,
        mapping_parameters,
        mapping_outer,
        {"type": "function", "function": None},
        {"type": "function", "function": []},
        {"type": "function", "function": {"name": 17, "parameters": {}}},
        {
            "type": "function",
            "function": {
                "name": "properties_as_list",
                "description": "deterministic extraction",
                "parameters": {"properties": ["not", "a", "mapping"]},
            },
        },
    ]


def _branch_case(
    case_id: str,
    operation: str,
    positives: list[tuple[str, Any]],
    near_misses: list[tuple[str, Any]],
) -> dict[str, Any]:
    exact_names = EXACT_NAMES_BY_CATEGORY_CASE[case_id]
    for exact_name in exact_names:
        near_misses.extend(
            (
                (
                    f"exact_name_suffix_near_miss_{exact_name}",
                    _schema(f"{exact_name}_v2"),
                ),
                (
                    f"exact_name_prefix_near_miss_{exact_name}",
                    _schema(f"v2_{exact_name}"),
                ),
                (
                    f"exact_name_uppercase_near_miss_{exact_name}",
                    _schema(exact_name.upper()),
                ),
                (
                    f"exact_name_mixed_case_near_miss_{exact_name}",
                    _schema(_mixed_case_value(exact_name)),
                ),
                (
                    f"exact_name_execution_alias_near_miss_{exact_name}",
                    _schema(EXACT_EXECUTION_ALIAS_RAW_BY_NAME[exact_name]),
                ),
                (
                    f"exact_name_leading_space_near_miss_{exact_name}",
                    _schema(f" {exact_name}"),
                ),
                (
                    f"exact_name_trailing_space_near_miss_{exact_name}",
                    _schema(f"{exact_name} "),
                ),
            )
        )

    def rows(values: list[tuple[str, Any]]) -> list[dict[str, str]]:
        return [
            {
                "alternative_id": alternative_id,
                "tool_name": str(schema["function"]["name"]),
            }
            for alternative_id, schema in values
        ]

    return {
        "case_id": case_id,
        "tools": [schema for _alternative_id, schema in (*positives, *near_misses)],
        "targets": (),
        "category_branch_contract": {
            "operation": operation,
            "positives": rows(positives),
            "near_misses": rows(near_misses),
            "exact_name_contract": [
                {
                    "exact_name": exact_name,
                    "suffix_near_miss": f"{exact_name}_v2",
                    "prefix_near_miss": f"v2_{exact_name}",
                    "uppercase_near_miss": exact_name.upper(),
                    "mixed_case_near_miss": _mixed_case_value(exact_name),
                    "execution_alias_near_miss": (
                        EXACT_EXECUTION_ALIAS_RAW_BY_NAME[exact_name]
                    ),
                    "leading_space_near_miss": f" {exact_name}",
                    "trailing_space_near_miss": f"{exact_name} ",
                }
                for exact_name in exact_names
            ],
            "subset_extra_contract": [
                {
                    "alternative_id": alternative_id,
                    "required_inputs": list(required_inputs),
                    "positive_tool_name": next(
                        str(schema["function"]["name"])
                        for candidate_id, schema in positives
                        if candidate_id == alternative_id
                    ),
                }
                for alternative_id, required_inputs in (
                    SUBSET_REQUIRED_FIELDS_BY_CATEGORY_CASE[case_id]
                )
            ],
            "non_subset_input_contract": [
                {
                    "alternative_id": alternative_id,
                    "minimal_inputs": list(minimal_inputs),
                    "positive_tool_name": next(
                        str(schema["function"]["name"])
                        for candidate_id, schema in positives
                        if candidate_id == alternative_id
                    ),
                }
                for alternative_id, minimal_inputs in (
                    NON_SUBSET_INPUT_FIELDS_BY_CATEGORY_CASE[case_id]
                )
            ],
        },
    }


def _selector_branch_case() -> dict[str, Any]:
    records = {"records": {"type": "array"}}
    positives = [
        (
            "description_visible_record_constraint_selection",
            _schema(
                "s_p01",
                description="visible-record constraint selection",
                properties=records,
            ),
        ),
        (
            "description_selection_action_usage",
            _schema("s_p02", description="selection/action usage", properties=records),
        ),
        (
            "description_medium_grain_workflow_usage",
            _schema(
                "s_p03", description="medium-grain workflow usage", properties=records
            ),
        ),
        (
            "description_constraint_to_action",
            _schema("s_p04", description="constraint-to-action", properties=records),
        ),
        (
            "description_selected_record",
            _schema("s_p05", description="selected_record", properties=records),
        ),
        (
            "name_select_and_description_record",
            _schema("s_select_p06", description="record routing", properties=records),
        ),
        (
            "membership_extra_selector_records",
            _schema(
                "s_p07",
                description="selected_record",
                properties={**records, "locale": {"type": "string"}},
            ),
        ),
    ]
    near_misses = [
        (
            "marker_without_records_input",
            _schema(
                "s_n01",
                description="visible-record constraint selection",
                properties={"candidates": {"type": "array"}},
            ),
        ),
        (
            "records_without_marker",
            _schema("s_n02", description="constraint choice", properties=records),
        ),
        (
            "record_description_without_select_name",
            _schema("s_choose_n03", description="record routing", properties=records),
        ),
        (
            "select_name_without_record_description",
            _schema(
                "s_select_n04", description="candidate routing", properties=records
            ),
        ),
    ]
    return _branch_case(
        "category_branches_selector",
        "_selector_tool_names",
        positives,
        near_misses,
    )


def _derived_value_branch_case() -> dict[str, Any]:
    scalar = {"value": {"type": "string"}}
    positives = [
        (
            "marker_extract_description",
            _schema("d_p01", description="extract", properties=scalar),
        ),
        (
            "marker_normalize_description",
            _schema("d_p02", description="normalize", properties=scalar),
        ),
        (
            "marker_canonicalize_description",
            _schema("d_p03", description="canonicalize", properties=scalar),
        ),
        (
            "marker_deterministic_extraction_description",
            _schema("d_p04", description="deterministic extraction", properties=scalar),
        ),
        (
            "marker_extract_in_name",
            _schema("d_extract_p05", description="transform", properties=scalar),
        ),
        (
            "multi_input_object_payload",
            _schema(
                "d_p06",
                description="extract",
                properties={
                    "payload": {"type": "object"},
                    "label": {"type": "string"},
                },
            ),
        ),
        (
            "multi_input_array_payload",
            _schema(
                "d_p07",
                description="extract",
                properties={
                    "payload": {"type": "array"},
                    "enabled": {"type": "boolean"},
                },
            ),
        ),
        (
            "marker_normalize_in_name",
            _schema("d_normalize_p08", description="transform", properties=scalar),
        ),
        (
            "marker_canonicalize_in_name",
            _schema("d_canonicalize_p09", description="transform", properties=scalar),
        ),
        (
            "marker_deterministic_extraction_in_name",
            _schema(
                "d deterministic extraction p10",
                description="transform",
                properties=scalar,
            ),
        ),
        (
            "multi_input_object_payload_number_extra",
            _schema(
                "d_p11",
                description="extract",
                properties={
                    "payload": {"type": "object"},
                    "threshold": {"type": "number"},
                },
            ),
        ),
        (
            "multi_input_array_payload_integer_extra",
            _schema(
                "d_p12",
                description="extract",
                properties={
                    "payload": {"type": "array"},
                    "limit": {"type": "integer"},
                },
            ),
        ),
        (
            "multi_input_object_payload_three_plus_inputs",
            _schema(
                "d_p13",
                description="extract",
                properties={
                    "payload": {"type": "object"},
                    "label": {"type": "string"},
                    "limit": {"type": "integer"},
                    "enabled": {"type": "boolean"},
                },
            ),
        ),
    ]
    near_misses = [
        (
            "single_input_without_marker",
            _schema("d_n01", description="transform", properties=scalar),
        ),
        (
            "multiple_scalars_without_payload",
            _schema(
                "d_n02",
                description="extract",
                properties={"left": {"type": "string"}, "right": {"type": "integer"}},
            ),
        ),
        (
            "payload_with_unsupported_extra_type",
            _schema(
                "d_n03",
                description="extract",
                properties={
                    "payload": {"type": "object"},
                    "opaque": {"type": "custom"},
                },
            ),
        ),
        (
            "marker_without_inputs",
            _schema("d_n04", description="extract", properties={}),
        ),
    ]
    return _branch_case(
        "category_branches_derived_value",
        "_derived_value_tool_names",
        positives,
        near_misses,
    )


def _lookup_query_planner_branch_case() -> dict[str, Any]:
    query = {"query": {"type": "string"}}
    positives: list[tuple[str, Any]] = []
    for index, prefix in enumerate(("search", "find", "get"), start=1):
        positives.append(
            (
                f"direct_output_{prefix}_kwargs",
                _schema(
                    f"l_p0{index}",
                    properties=query,
                    output_properties={f"{prefix}_records_kwargs": {"type": "object"}},
                ),
            )
        )
    for index, marker in enumerate(
        (
            "search_contacts_kwargs",
            "lookup query",
            "query planner",
            "prepare search",
            "search kwargs",
        ),
        start=4,
    ):
        positives.append(
            (
                f"text_marker_{marker.replace(' ', '_')}",
                _schema(f"l_p0{index}", description=marker, properties=query),
            )
        )
    for index, raw_name in enumerate(
        (
            "search_contacts_kwargs_builder",
            "lookup query builder",
            "query planner builder",
            "prepare search builder",
            "search kwargs builder",
        ),
        start=9,
    ):
        positives.append(
            (
                f"name_marker_{raw_name.replace(' ', '_')}",
                _schema(raw_name, description="neutral", properties=query),
            )
        )
    positives.append(
        (
            "membership_extra_lookup_inputs",
            _schema(
                "l_p14",
                description="query planner",
                properties={**query, "locale": {"type": "string"}},
            ),
        )
    )
    near_misses = [
        (
            "nested_output_kwargs_is_not_direct",
            _schema(
                "l_n01",
                properties=query,
                nested_output_properties={"search_records_kwargs": {"type": "object"}},
            ),
        ),
        (
            "output_prefix_without_kwargs_suffix",
            _schema(
                "l_n02",
                properties=query,
                output_properties={"search_records_arguments": {"type": "object"}},
            ),
        ),
        (
            "output_kwargs_suffix_without_allowed_prefix",
            _schema(
                "l_n08",
                properties=query,
                output_properties={"records_kwargs": {"type": "object"}},
            ),
        ),
        (
            "direct_output_match_without_inputs",
            _schema(
                "l_n09",
                properties={},
                output_properties={"search_records_kwargs": {"type": "object"}},
            ),
        ),
        (
            "marker_without_inputs",
            _schema("l_n03", description="query planner", properties={}),
        ),
    ]
    for index, prohibited in enumerate(
        ("records", "candidates", "selected_record", "contact_record"),
        start=4,
    ):
        near_misses.append(
            (
                f"prior_record_input_{prohibited}",
                _schema(
                    f"l_n0{index}",
                    description="query planner",
                    properties={
                        "query": {"type": "string"},
                        prohibited: {"type": "object"},
                    },
                ),
            )
        )
    return _branch_case(
        "category_branches_lookup_query_planner",
        "_lookup_query_planner_tool_names",
        positives,
        near_misses,
    )


def _search_window_branch_case() -> dict[str, Any]:
    positives = [
        (f"exact_name_{name}", _schema(name))
        for name in (
            "prepare_message_recency_search_args",
            "prepare_past_reminder_recency_search_args",
            "resolve_search_window_or_bounds",
            "prepare_upcoming_reminder_search_args",
        )
    ]
    positives.append(
        (
            "current_timestamp_reminder_search_kwargs",
            _schema(
                "w_p05",
                description="reminder search kwargs",
                properties={"current_timestamp": {"type": "number"}},
            ),
        )
    )
    complete_inputs = {
        "current_timestamp": {"type": "number"},
        "phrase": {"type": "string"},
        "target_domain": {"type": "string"},
        "timestamp_intent": {"type": "string"},
        "direction": {"type": "string"},
    }
    for index, marker in enumerate(
        ("time-window", "recency phrase", "search kwargs", "bounded search"),
        start=6,
    ):
        positives.append(
            (
                f"complete_inputs_marker_{marker.replace(' ', '_')}",
                _schema(
                    f"w_p{index:02d}", description=marker, properties=complete_inputs
                ),
            )
        )
    positives.append(
        (
            "subset_extra_complete_search_window",
            _schema(
                "w_p10",
                description="bounded search",
                properties={**complete_inputs, "locale": {"type": "string"}},
            ),
        )
    )
    positives.append(
        (
            "membership_extra_current_timestamp",
            _schema(
                "w_p11",
                description="reminder search kwargs",
                properties={
                    "current_timestamp": {"type": "number"},
                    "locale": {"type": "string"},
                },
            ),
        )
    )
    near_misses = [
        (
            "five_inputs_nonmarker_time_window",
            _schema("w_n02", description="time window", properties=complete_inputs),
        ),
        (
            "timestamp_search_kwargs_without_reminder",
            _schema(
                "w_n04",
                description="search kwargs",
                properties={"current_timestamp": {"type": "number"}},
            ),
        ),
        (
            "reminder_search_kwargs_without_current_timestamp",
            _schema(
                "w_n05",
                description="reminder search kwargs",
                properties={"phrase": {"type": "string"}},
            ),
        ),
        (
            "timestamp_reminder_without_search_kwargs",
            _schema(
                "w_n06",
                description="reminder lookup arguments",
                properties={"current_timestamp": {"type": "number"}},
            ),
        ),
    ]
    for index, missing_input in enumerate(complete_inputs, start=10):
        incomplete = dict(complete_inputs)
        incomplete.pop(missing_input)
        near_misses.append(
            (
                f"bounded_search_missing_{missing_input}",
                _schema(
                    f"w_n{index:02d}",
                    description="bounded search",
                    properties=incomplete,
                ),
            )
        )
    return _branch_case(
        "category_branches_search_window",
        "_search_window_tool_names",
        positives,
        near_misses,
    )


def _relative_time_branch_case() -> dict[str, Any]:
    required = {
        "current_timestamp": {"type": "number"},
        "day_offset": {"type": "integer"},
        "hour": {"type": "integer"},
        "minute": {"type": "integer"},
    }
    positives = [("exact_name", _schema("relative_day_time_to_timestamp"))]
    for index, marker in enumerate(
        ("relative local day", "relative day", "tomorrow", "timestamp"),
        start=2,
    ):
        positives.append(
            (
                f"required_inputs_marker_{marker.replace(' ', '_')}",
                _schema(f"r_p0{index}", description=marker, properties=required),
            )
        )
    for index, raw_name in enumerate(
        (
            "relative local day converter",
            "relative day converter",
            "tomorrow_converter",
            "timestamp_converter",
        ),
        start=6,
    ):
        positives.append(
            (
                f"required_inputs_name_marker_{raw_name.replace(' ', '_')}",
                _schema(raw_name, description="neutral", properties=required),
            )
        )
    positives.append(
        (
            "subset_extra_relative_time",
            _schema(
                "r_p10",
                description="tomorrow",
                properties={**required, "timezone": {"type": "string"}},
            ),
        )
    )
    near_misses = [
        ("required_inputs_without_marker", _schema("r_n03", properties=required)),
    ]
    for index, missing_input in enumerate(required, start=10):
        incomplete = dict(required)
        incomplete.pop(missing_input)
        near_misses.append(
            (
                f"tomorrow_marker_missing_{missing_input}",
                _schema(
                    f"r_n{index:02d}",
                    description="tomorrow",
                    properties=incomplete,
                ),
            )
        )
    return _branch_case(
        "category_branches_relative_time",
        "_relative_time_tool_names",
        positives,
        near_misses,
    )


def _scheduling_timestamp_branch_case() -> dict[str, Any]:
    positives = [
        (f"exact_name_{name}", _schema(name))
        for name in (
            "next_weekday_time_to_timestamp",
            "relative_weeks_time_to_timestamp",
            "weeks_from_now_time_to_timestamp",
            "week_delta_time_to_timestamp",
            "weekday_delta_time_to_timestamp",
        )
    ]
    required = {
        "current_timestamp": {"type": "number"},
        "hour": {"type": "integer"},
        "minute": {"type": "integer"},
        "local_utc_offset_hours": {"type": "number"},
    }
    for index, marker in enumerate(("week", "weekday", "scheduling"), start=6):
        positives.append(
            (
                f"required_inputs_marker_{marker}",
                _schema(
                    f"t_p0{index}",
                    description=f"reminder_timestamp {marker}",
                    properties=required,
                ),
            )
        )
    positives.append(
        (
            "subset_extra_scheduling_timestamp",
            _schema(
                "t_p09",
                description="reminder_timestamp scheduling",
                properties={**required, "label": {"type": "string"}},
            ),
        )
    )
    near_misses = [
        (
            "reminder_timestamp_without_week_marker",
            _schema(
                "t_n02", description="reminder_timestamp daily", properties=required
            ),
        ),
        (
            "week_marker_without_reminder_timestamp",
            _schema("t_n03", description="week planner", properties=required),
        ),
    ]
    for index, missing_input in enumerate(required, start=10):
        incomplete = dict(required)
        incomplete.pop(missing_input)
        near_misses.append(
            (
                f"scheduling_marker_missing_{missing_input}",
                _schema(
                    f"t_n{index:02d}",
                    description="reminder_timestamp scheduling",
                    properties=incomplete,
                ),
            )
        )
    return _branch_case(
        "category_branches_scheduling_timestamp",
        "_scheduling_timestamp_tool_names",
        positives,
        near_misses,
    )


def _state_action_planner_branch_case() -> dict[str, Any]:
    classic = {
        "user_request": {"type": "string"},
        "visible_state_or_error": {"type": "object"},
    }
    structured = {
        "target_service": {"type": "string"},
        "desired_on": {"type": "boolean"},
    }
    positives = [
        ("exact_name_next_service_tool_call", _schema("next_service_tool_call")),
        (
            "next_service_input_target_service",
            _schema(
                "a_p02",
                description="device-state",
                properties={"target_service": {"type": "string"}},
            ),
        ),
        (
            "next_service_input_tool_name",
            _schema(
                "a_p03",
                description="device-state",
                properties={"tool_name": {"type": "string"}},
            ),
        ),
        (
            "next_service_input_should_call",
            _schema(
                "a_p04",
                description="device-state",
                properties={"should_call": {"type": "boolean"}},
            ),
        ),
        (
            "next_service_device_state_space",
            _schema(
                "a_p05",
                description="device state",
                properties={"tool_name": {"type": "string"}},
            ),
        ),
        (
            "membership_multi_next_service_inputs",
            _schema(
                "a_p06",
                description="device-state",
                properties={
                    "target_service": {"type": "string"},
                    "tool_name": {"type": "string"},
                },
            ),
        ),
        (
            "classic_inputs_named_prefix",
            _schema("plan_device_state_action_sequence_v2", properties=classic),
        ),
        (
            "classic_inputs_state_action_sequence",
            _schema("a_p07", description="state action sequence", properties=classic),
        ),
        (
            "classic_inputs_device_state_hyphen_setter",
            _schema(
                "a_p08",
                description="device-state setter sequence",
                properties=classic,
            ),
        ),
        (
            "classic_inputs_device_state_space_setter",
            _schema(
                "a_p09",
                description="device state setter sequence",
                properties=classic,
            ),
        ),
        (
            "structured_inputs_plan_prefix",
            _schema(
                "plan_device_state_action_sequence_structured", properties=structured
            ),
        ),
        (
            "structured_inputs_apply_prefix",
            _schema("apply_single_device_state_action_v2", properties=structured),
        ),
        (
            "subset_extra_classic_state_action",
            _schema(
                "plan_device_state_action_sequence_with_reason",
                properties={**classic, "reason": {"type": "string"}},
            ),
        ),
        (
            "subset_extra_structured_state_action",
            _schema(
                "apply_single_device_state_action_with_metadata",
                properties={**structured, "metadata": {"type": "object"}},
            ),
        ),
    ]
    near_misses = [
        (
            "device_text_without_gate_input",
            _schema(
                "a_n01",
                description="device-state setter sequence",
                properties={"desired_on": {"type": "boolean"}},
            ),
        ),
        (
            "classic_prefix_missing_visible_state",
            _schema(
                "plan_device_state_action_sequence_incomplete",
                properties={"user_request": {"type": "string"}},
            ),
        ),
        (
            "classic_prefix_missing_user_request",
            _schema(
                "plan_device_state_action_sequence_visible_only",
                properties={"visible_state_or_error": {"type": "object"}},
            ),
        ),
        (
            "classic_inputs_without_name_or_description_marker",
            _schema("a_n04", properties=classic),
        ),
        (
            "classic_device_text_missing_setter_sequence",
            _schema("a_n05", description="device-state", properties=classic),
        ),
        (
            "classic_setter_sequence_missing_device_text",
            _schema("a_n06", description="setter sequence", properties=classic),
        ),
        (
            "structured_prefix_missing_desired_on",
            _schema(
                "apply_single_device_state_action_incomplete",
                properties={"target_service": {"type": "string"}},
            ),
        ),
        (
            "structured_prefix_missing_target_service",
            _schema(
                "apply_single_device_state_action_desired_only",
                properties={"desired_on": {"type": "boolean"}},
            ),
        ),
        (
            "structured_inputs_without_name_or_description_marker",
            _schema("a_n09", properties=structured),
        ),
        (
            "next_service_input_without_device_description",
            _schema(
                "a_n10",
                description="service planner",
                properties={"tool_name": {"type": "string"}},
            ),
        ),
    ]
    return _branch_case(
        "category_branches_state_action_planner",
        "_state_action_planner_tool_names",
        positives,
        near_misses,
    )


def _validation_abstention_branch_case() -> dict[str, Any]:
    required = {
        "user_request": {"type": "string"},
        "requested_action": {"type": "string"},
        "required_original_tools": {"type": "array"},
        "available_original_tools": {"type": "array"},
    }
    positives = [("exact_name", _schema("prepare_safe_action_or_abstain"))]
    for index, marker in enumerate(
        ("abstain", "insufficient information", "safe action"),
        start=2,
    ):
        positives.append(
            (
                f"required_inputs_marker_{marker.replace(' ', '_')}",
                _schema(f"v_p0{index}", description=marker, properties=required),
            )
        )
    positives.append(
        (
            "subset_extra_validation_abstention",
            _schema(
                "v_p05",
                description="safe action",
                properties={**required, "audit_tag": {"type": "string"}},
            ),
        )
    )
    near_misses = [
        ("required_inputs_without_marker", _schema("v_n03", properties=required)),
    ]
    for index, missing_input in enumerate(required, start=10):
        incomplete = dict(required)
        incomplete.pop(missing_input)
        near_misses.append(
            (
                f"safe_action_missing_{missing_input}",
                _schema(
                    f"v_n{index:02d}",
                    description="safe action",
                    properties=incomplete,
                ),
            )
        )
    return _branch_case(
        "category_branches_validation_abstention",
        "_validation_abstention_tool_names",
        positives,
        near_misses,
    )


def _action_argument_helper_branch_case() -> dict[str, Any]:
    inputs = {"user_request": {"type": "string"}}
    preparation_markers = (
        "prepare the arguments",
        "prepares the arguments",
        "prepare arguments",
        "prepares arguments",
        "prepare the call",
        "prepares the call",
        "prepare final",
        "prepares final",
        "prepare exact kwargs",
        "prepares exact kwargs",
        "safe downstream kwargs",
        "downstream_tool_kwargs",
        "side-effect",
        "action argument",
    )
    return_markers = (
        "should_call_tool",
        "should_call_add_reminder",
        "downstream tool",
        "downstream_tool_name",
        "downstream_tool_kwargs",
        "original toolsandbox",
    )
    positives = [
        (
            f"preparation_marker_{index:02d}_{marker.replace(' ', '_')}",
            _schema(
                f"g_p{index:02d}",
                description=f"{marker}; original toolsandbox",
                properties=inputs,
            ),
        )
        for index, marker in enumerate(preparation_markers, start=1)
    ]
    offset = len(positives)
    positives.extend(
        (
            f"return_marker_{index:02d}_{marker.replace(' ', '_')}",
            _schema(
                f"g_p{offset + index:02d}",
                description=f"prepare final; {marker}",
                properties=inputs,
            ),
        )
        for index, marker in enumerate(return_markers, start=1)
    )
    offset = len(positives)
    positives.extend(
        (
            f"native_return_marker_{native_name}",
            _schema(
                f"g_p{offset + index:02d}",
                description=f"prepare final; {native_name}",
                properties=inputs,
            ),
        )
        for index, native_name in enumerate(FIXTURE_SIDE_EFFECT_TOOL_NAMES, start=1)
    )
    positives.append(
        (
            "membership_extra_action_inputs",
            _schema(
                "g_membership_extra",
                description="prepare final; original toolsandbox",
                properties={**inputs, "locale": {"type": "string"}},
            ),
        )
    )
    offset = len(positives)
    positives.extend(
        (
            f"name_preparation_marker_{index:02d}_{marker.replace(' ', '_')}",
            _schema(
                (
                    "downstream_tool_kwargs_builder"
                    if marker == "downstream_tool_kwargs"
                    else f"{marker} builder {index:02d}"
                ),
                description="original toolsandbox",
                properties=inputs,
            ),
        )
        for index, marker in enumerate(preparation_markers, start=1)
    )
    offset = len(positives)
    positives.extend(
        (
            f"name_return_marker_{index:02d}_{marker.replace(' ', '_')}",
            _schema(
                f"{marker} return builder {offset + index:02d}",
                description="prepare final",
                properties=inputs,
            ),
        )
        for index, marker in enumerate(return_markers, start=1)
    )
    offset = len(positives)
    positives.extend(
        (
            f"name_native_return_marker_{native_name}",
            _schema(
                f"{native_name}_builder_{offset + index:02d}",
                description="prepare final",
                properties=inputs,
            ),
        )
        for index, native_name in enumerate(FIXTURE_SIDE_EFFECT_TOOL_NAMES, start=1)
    )
    valid_description = "prepare final; original toolsandbox"
    near_misses = [
        (
            f"prohibited_prior_input_{index:02d}_{prohibited}",
            _schema(
                f"g_n{index:02d}",
                description=valid_description,
                properties={
                    "user_request": {"type": "string"},
                    prohibited: {"type": "object"},
                },
            ),
        )
        for index, prohibited in enumerate(
            ("records", "candidates", "selected_record", "contact_record"),
            start=1,
        )
    ]
    near_misses.extend(
        (
            (
                "preparation_without_return",
                _schema("g_n05", description="prepare final", properties=inputs),
            ),
            (
                "return_without_preparation",
                _schema("g_n06", description="original toolsandbox", properties=inputs),
            ),
            (
                "markers_without_inputs",
                _schema("g_n07", description=valid_description, properties={}),
            ),
        )
    )
    offset = len(near_misses)
    near_misses.extend(
        (
            f"read_only_native_in_description_{native_name}",
            _schema(
                f"g_n{offset + index:02d}",
                description=f"prepare final; {native_name}",
                properties=inputs,
            ),
        )
        for index, native_name in enumerate(FIXTURE_READ_ONLY_NATIVE_TOOL_NAMES, 1)
    )
    offset = len(near_misses)
    near_misses.extend(
        (
            f"read_only_native_in_name_{native_name}",
            _schema(
                f"{native_name}_builder_{offset + index:02d}",
                description="prepare final",
                properties=inputs,
            ),
        )
        for index, native_name in enumerate(FIXTURE_READ_ONLY_NATIVE_TOOL_NAMES, 1)
    )
    return _branch_case(
        "category_branches_action_argument_helper",
        "_action_argument_helper_tool_names",
        positives,
        near_misses,
    )


def _post_selection_action_helper_branch_case() -> dict[str, Any]:
    record_inputs = (
        "selected_record",
        "contact_record",
        "record",
        "records",
        "candidates",
    )
    preparation_markers = (
        "downstream_tool_kwargs",
        "side-effect",
        "prepare arguments",
        "prepare the arguments",
        "prepares the arguments",
        "prepare the call",
        "prepares the call",
        "safe downstream kwargs",
        "selected record",
    )
    positives = [
        (
            f"record_input_{record_input}",
            _schema(
                f"p_p{index:02d}",
                description="side-effect",
                properties={record_input: {"type": "object"}},
            ),
        )
        for index, record_input in enumerate(record_inputs, start=1)
    ]
    offset = len(positives)
    positives.extend(
        (
            f"preparation_marker_{index:02d}_{marker.replace(' ', '_')}",
            _schema(
                f"p_p{offset + index:02d}",
                description=marker,
                properties={"selected_record": {"type": "object"}},
            ),
        )
        for index, marker in enumerate(preparation_markers, start=1)
    )
    offset = len(positives)
    positives.extend(
        (
            f"native_marker_{native_name}",
            _schema(
                f"p_p{offset + index:02d}",
                description=native_name,
                properties={"selected_record": {"type": "object"}},
            ),
        )
        for index, native_name in enumerate(FIXTURE_SIDE_EFFECT_TOOL_NAMES, start=1)
    )
    offset = len(positives)
    positives.extend(
        (
            f"name_preparation_marker_{index:02d}_{marker.replace(' ', '_')}",
            _schema(
                (
                    "downstream_tool_kwargs_builder"
                    if marker == "downstream_tool_kwargs"
                    else f"{marker} selected builder {index:02d}"
                ),
                description="neutral",
                properties={"selected_record": {"type": "object"}},
            ),
        )
        for index, marker in enumerate(preparation_markers, start=1)
    )
    offset = len(positives)
    positives.extend(
        (
            f"name_native_marker_{native_name}",
            _schema(
                f"{native_name}_builder_post_{offset + index:02d}",
                description="neutral",
                properties={"selected_record": {"type": "object"}},
            ),
        )
        for index, native_name in enumerate(FIXTURE_SIDE_EFFECT_TOOL_NAMES, start=1)
    )
    positives.append(
        (
            "membership_multi_post_selection_inputs",
            _schema(
                "p_membership_multi",
                description="side-effect",
                properties={
                    "selected_record": {"type": "object"},
                    "record": {"type": "object"},
                },
            ),
        )
    )
    near_misses = [
        (
            "marker_without_record_input",
            _schema(
                "p_n01",
                description="side-effect",
                properties={"selection": {"type": "object"}},
            ),
        ),
        (
            "record_input_without_marker",
            _schema("p_n02", properties={"selected_record": {"type": "object"}}),
        ),
    ]
    offset = len(near_misses)
    near_misses.extend(
        (
            f"read_only_native_in_description_{native_name}",
            _schema(
                f"p_n{offset + index:02d}",
                description=native_name,
                properties={"selected_record": {"type": "object"}},
            ),
        )
        for index, native_name in enumerate(FIXTURE_READ_ONLY_NATIVE_TOOL_NAMES, 1)
    )
    offset = len(near_misses)
    near_misses.extend(
        (
            f"read_only_native_in_name_{native_name}",
            _schema(
                f"{native_name}_builder_post_{offset + index:02d}",
                description="neutral",
                properties={"selected_record": {"type": "object"}},
            ),
        )
        for index, native_name in enumerate(FIXTURE_READ_ONLY_NATIVE_TOOL_NAMES, 1)
    )
    return _branch_case(
        "category_branches_post_selection_action_helper",
        "_post_selection_action_helper_tool_names",
        positives,
        near_misses,
    )


def _category_branch_specs() -> tuple[dict[str, Any], ...]:
    return (
        _selector_branch_case(),
        _derived_value_branch_case(),
        _lookup_query_planner_branch_case(),
        _search_window_branch_case(),
        _relative_time_branch_case(),
        _scheduling_timestamp_branch_case(),
        _state_action_planner_branch_case(),
        _validation_abstention_branch_case(),
        _action_argument_helper_branch_case(),
        _post_selection_action_helper_branch_case(),
    )


def _field_matrix_base(
    category_case_id: str,
    token_kind: str,
) -> tuple[str, dict[str, dict[str, Any]], dict[str, Any]]:
    string = {"type": "string"}
    number = {"type": "number"}
    integer = {"type": "integer"}
    mapping = {"type": "object"}
    array = {"type": "array"}
    if token_kind == "raw_selector_select":
        return "record routing", {"records": array}, string
    if token_kind in {"raw_state_plan_prefix", "raw_state_apply_prefix"}:
        return (
            "",
            {"target_service": string, "desired_on": {"type": "boolean"}},
            string,
        )
    if token_kind == "lexical":
        values = {
            "category_branches_selector": ("", {"records": array}, string),
            "category_branches_derived_value": ("", {"value": string}, string),
            "category_branches_lookup_query_planner": (
                "",
                {"query": string},
                string,
            ),
            "category_branches_search_window": (
                "",
                {
                    "current_timestamp": number,
                    "phrase": string,
                    "target_domain": string,
                    "timestamp_intent": string,
                    "direction": string,
                },
                string,
            ),
            "category_branches_relative_time": (
                "",
                {
                    "current_timestamp": number,
                    "day_offset": integer,
                    "hour": integer,
                    "minute": integer,
                },
                string,
            ),
            "category_branches_scheduling_timestamp": (
                "reminder_timestamp",
                {
                    "current_timestamp": number,
                    "hour": integer,
                    "minute": integer,
                    "local_utc_offset_hours": number,
                },
                string,
            ),
            "category_branches_state_action_planner": (
                "",
                {"user_request": string, "visible_state_or_error": mapping},
                string,
            ),
            "category_branches_validation_abstention": (
                "",
                {
                    "user_request": string,
                    "requested_action": string,
                    "required_original_tools": array,
                    "available_original_tools": array,
                },
                string,
            ),
            "category_branches_action_argument_helper": (
                "original toolsandbox",
                {"user_request": string},
                string,
            ),
            "category_branches_post_selection_action_helper": (
                "",
                {"selected_record": mapping},
                string,
            ),
        }
    else:
        values = {
            "category_branches_selector": ("selected_record", {}, array),
            "category_branches_derived_value": ("extract", {}, mapping),
            "category_branches_lookup_query_planner": (
                "",
                {"query": string},
                mapping,
            ),
            "category_branches_search_window": (
                "reminder search kwargs",
                {},
                number,
            ),
            "category_branches_relative_time": (
                "tomorrow",
                {"day_offset": integer, "hour": integer, "minute": integer},
                number,
            ),
            "category_branches_scheduling_timestamp": (
                "reminder_timestamp scheduling",
                {
                    "hour": integer,
                    "minute": integer,
                    "local_utc_offset_hours": number,
                },
                number,
            ),
            "category_branches_state_action_planner": (
                "state action sequence",
                {"user_request": string},
                mapping,
            ),
            "category_branches_validation_abstention": (
                "safe action",
                {
                    "user_request": string,
                    "requested_action": string,
                    "required_original_tools": array,
                },
                array,
            ),
            "category_branches_action_argument_helper": (
                "prepare final; original toolsandbox",
                {},
                string,
            ),
            "category_branches_post_selection_action_helper": (
                "side-effect",
                {},
                mapping,
            ),
        }
    description, properties, property_schema = values[category_case_id]
    return description, copy.deepcopy(properties), copy.deepcopy(property_schema)


def _field_matrix_schema(
    category_case_id: str,
    token_kind: str,
    field: str,
    casing: str,
    index: int,
) -> dict[str, Any]:
    token = _case_variant(
        next(
            token
            for candidate_kind, token, _read_fields in _field_token_plans(
                category_case_id
            )
            if candidate_kind == token_kind
        ),
        casing,
    )
    description, properties, property_schema = _field_matrix_base(
        category_case_id,
        token_kind,
    )
    raw_name = f"field_probe_{index:03d}"
    direct_output: dict[str, Any] | None = None
    nested_output: dict[str, Any] | None = None
    if field == "raw_name":
        raw_name = token
    elif field == "execution_name":
        raw_name = _field_execution_alias_raw(category_case_id, token_kind, casing)
    elif field == "description":
        description = f"{description} {token}".strip()
    elif field == "input_property":
        properties[token] = property_schema
    elif field == "direct_output_property":
        direct_output = {token: property_schema}
    elif field == "nested_output_property":
        nested_output = {token: property_schema}
    elif field != "schema_json":
        raise ValueError(f"unknown field-matrix field: {field}")
    schema = _schema(
        raw_name,
        description=description,
        properties=properties,
        output_properties=direct_output,
        nested_output_properties=nested_output,
    )
    if field == "schema_json":
        schema["function"]["x-field-boundary-token"] = token
    return schema


def _joined_marker_carrier(
    category_case_id: str,
    marker: str,
) -> tuple[dict[str, Any], str]:
    if category_case_id == "category_branches_derived_value":
        return {"value": {"type": "string"}}, ""
    if category_case_id == "category_branches_lookup_query_planner":
        return {"query": {"type": "string"}}, ""
    if category_case_id == "category_branches_relative_time":
        return (
            {
                "current_timestamp": {"type": "number"},
                "day_offset": {"type": "integer"},
                "hour": {"type": "integer"},
                "minute": {"type": "integer"},
            },
            "",
        )
    if category_case_id == "category_branches_action_argument_helper":
        return (
            {"user_request": {"type": "string"}},
            (
                " original toolsandbox"
                if marker in ACTION_ARGUMENT_PREPARATION_MARKERS
                else " prepare final"
            ),
        )
    if category_case_id == "category_branches_post_selection_action_helper":
        return {"selected_record": {"type": "object"}}, ""
    raise AssertionError(f"missing joined-marker carrier for: {category_case_id}")


def _cross_field_composition_schemas(
    category_case_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    schemas: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    case_index = CATEGORY_BRANCH_CASE_IDS.index(category_case_id) + 1
    for marker_index, marker in enumerate(
        CROSS_FIELD_COMPOSITION_MARKERS_BY_CATEGORY_CASE[category_case_id],
        start=1,
    ):
        properties, carrier_suffix = _joined_marker_carrier(
            category_case_id,
            marker,
        )
        mask_reason = CROSS_FIELD_MASK_REASONS.get((category_case_id, marker))
        for split_index, (left, right) in enumerate(
            _cross_field_marker_splits(marker),
            start=1,
        ):
            alias_name = _cross_field_alias_raw_name(
                category_case_id,
                marker_index,
                split_index,
            )
            for variant_index, variant in enumerate(
                CROSS_FIELD_COMPOSITION_VARIANTS,
                start=1,
            ):
                prefix = (
                    f"cross_field_{case_index:02d}_{marker_index:02d}_"
                    f"{split_index:02d}_{variant_index:02d}_"
                )
                raw_name = f"{prefix}{left}"
                description = f"{right}{carrier_suffix}"
                expected_member = bool(mask_reason) or variant in {
                    "forward_lowercase",
                    "forward_uppercase_description",
                    "raw_name_leading_space",
                    "description_trailing_space",
                }
                if variant == "forward_uppercase_description":
                    description = description.upper()
                elif variant == "uppercase_raw_name":
                    raw_name = f"{prefix}{left.upper()}"
                elif variant == "reverse_field_order":
                    raw_name = f"{prefix}{right}"
                    description = f"{left}{carrier_suffix}"
                elif variant == "raw_name_leading_space":
                    raw_name = f" {raw_name}"
                elif variant == "raw_name_trailing_space":
                    raw_name = f"{prefix}{left} "
                elif variant == "description_leading_space":
                    description = f" {description}"
                elif variant == "description_trailing_space":
                    description = f"{description} "
                elif variant == "execution_alias_raw_name":
                    raw_name = alias_name
                schema = _schema(
                    raw_name,
                    description=description,
                    properties=copy.deepcopy(properties),
                )
                schemas.append(schema)
                rows.append(
                    {
                        "probe_id": (
                            f"{marker.replace(' ', '_')}_split_{split_index}_{variant}"
                        ),
                        "marker": marker,
                        "split_index": split_index,
                        "left": left,
                        "right": right,
                        "variant": variant,
                        "carrier_suffix": carrier_suffix,
                        "tool_name": raw_name,
                        "description": description,
                        "expected_member": expected_member,
                        "cross_boundary_required": (
                            expected_member and mask_reason is None
                        ),
                        "mask_reason": mask_reason,
                    }
                )
    return schemas, rows


def _joined_field_whitespace_schemas(
    category_case_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    schemas: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    case_index = CATEGORY_BRANCH_CASE_IDS.index(category_case_id) + 1
    for marker_index, marker in enumerate(
        CROSS_FIELD_COMPOSITION_MARKERS_BY_CATEGORY_CASE[category_case_id],
        start=1,
    ):
        properties, carrier_suffix = _joined_marker_carrier(
            category_case_id,
            marker,
        )
        carrier_description = carrier_suffix.strip()
        mask_reason = CROSS_FIELD_MASK_REASONS.get((category_case_id, marker))
        marker_slug = marker.replace(" ", "_")
        for variant_index, variant in enumerate(
            JOINED_FIELD_WHITESPACE_EDGE_VARIANTS,
            start=1,
        ):
            prefix = (
                f"joined_ws_{case_index:02d}_{marker_index:02d}_"
                f"edge_{variant_index:02d}_"
            )
            if variant == "raw_name_leading_space":
                raw_name = f" {prefix}{marker}"
                description = carrier_description
            elif variant == "raw_name_trailing_space":
                raw_name = f"{prefix}{marker} "
                description = carrier_description
            elif variant == "description_leading_space":
                raw_name = f"{prefix}neutral"
                description = f" {marker}{carrier_suffix}"
            elif variant == "description_trailing_space":
                raw_name = f"{prefix}neutral"
                description = f"{marker}{carrier_suffix} "
            else:
                raise AssertionError(f"unknown whitespace edge variant: {variant}")
            schema = _schema(
                raw_name,
                description=description,
                properties=copy.deepcopy(properties),
            )
            schemas.append(schema)
            rows.append(
                {
                    "probe_id": f"{marker_slug}_{variant}",
                    "marker": marker,
                    "variant": variant,
                    "boundary_index": None,
                    "tool_name": raw_name,
                    "description": description,
                    "expected_member": True,
                    "mask_reason": mask_reason,
                }
            )
        words = marker.split()
        for boundary_index in range(1, len(words)):
            doubled = (
                f"{' '.join(words[:boundary_index])}  "
                f"{' '.join(words[boundary_index:])}"
            )
            for placement_index, placement in enumerate(
                JOINED_FIELD_WHITESPACE_INTERNAL_PLACEMENTS,
                start=1,
            ):
                prefix = (
                    f"joined_ws_{case_index:02d}_{marker_index:02d}_"
                    f"internal_{boundary_index:02d}_{placement_index:02d}_"
                )
                if placement == "raw_name_internal_double_space":
                    raw_name = f"{prefix}{doubled}"
                    description = carrier_description
                elif placement == "description_internal_double_space":
                    raw_name = f"{prefix}neutral"
                    description = f"{doubled}{carrier_suffix}"
                else:
                    raise AssertionError(
                        f"unknown whitespace internal placement: {placement}"
                    )
                schema = _schema(
                    raw_name,
                    description=description,
                    properties=copy.deepcopy(properties),
                )
                schemas.append(schema)
                rows.append(
                    {
                        "probe_id": (
                            f"{marker_slug}_boundary_{boundary_index}_{placement}"
                        ),
                        "marker": marker,
                        "variant": placement,
                        "boundary_index": boundary_index,
                        "tool_name": raw_name,
                        "description": description,
                        "expected_member": bool(mask_reason),
                        "mask_reason": mask_reason,
                    }
                )
    return schemas, rows


def _derived_schema_type_schemas() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    schemas: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for type_index, json_type in enumerate(DERIVED_SCHEMA_TYPE_VALUES, start=1):
        for casing_index, casing in enumerate(DERIVED_SCHEMA_TYPE_CASINGS, start=1):
            type_value = _case_variant(json_type, casing)
            if json_type in {"object", "array"}:
                properties = {
                    "payload": {"type": type_value},
                    "label": {"type": "string"},
                }
            else:
                properties = {
                    "payload": {"type": "object"},
                    "extra": {"type": type_value},
                }
            raw_name = f"schema_type_probe_{type_index:02d}_{casing_index:02d}"
            schema = _schema(
                raw_name,
                description="extract",
                properties=properties,
            )
            schemas.append(schema)
            rows.append(
                {
                    "probe_id": f"{json_type}_{casing}",
                    "json_type": json_type,
                    "casing": casing,
                    "type_value": type_value,
                    "tool_name": raw_name,
                    "expected_member": casing == "lowercase",
                }
            )
    return schemas, rows


def _field_normalization_specs() -> tuple[dict[str, Any], ...]:
    specs: list[dict[str, Any]] = []
    for category_case_id in CATEGORY_BRANCH_CASE_IDS:
        plan = FIELD_NORMALIZATION_PLANS[category_case_id]
        rows: list[dict[str, Any]] = []
        tools: list[dict[str, Any]] = []
        index = 1
        token_plans = _field_token_plans(category_case_id)
        for token_kind, _token, configured_read_fields in token_plans:
            expected_fields = set(configured_read_fields)
            for field in FIELD_MATRIX_FIELDS:
                for casing in FIELD_MATRIX_CASINGS:
                    schema = _field_matrix_schema(
                        category_case_id,
                        token_kind,
                        field,
                        casing,
                        index,
                    )
                    expected = field in expected_fields and (
                        token_kind == "lexical"
                        and field == "description"
                        or token_kind == "structural"
                        and field
                        in STRUCTURAL_CASE_INSENSITIVE_FIELDS_BY_CATEGORY_CASE[
                            category_case_id
                        ]
                        or casing == "lowercase"
                    )
                    rows.append(
                        {
                            "probe_id": (f"{token_kind}_{field}_{casing}"),
                            "token_kind": token_kind,
                            "field": field,
                            "casing": casing,
                            "tool_name": str(schema["function"]["name"]),
                            "expected_member": expected,
                        }
                    )
                    tools.append(schema)
                    index += 1
        composition_schemas, composition_rows = _cross_field_composition_schemas(
            category_case_id
        )
        tools.extend(composition_schemas)
        whitespace_schemas, whitespace_rows = _joined_field_whitespace_schemas(
            category_case_id
        )
        tools.extend(whitespace_schemas)
        schema_type_schemas: list[dict[str, Any]] = []
        schema_type_rows: list[dict[str, Any]] = []
        if category_case_id == "category_branches_derived_value":
            schema_type_schemas, schema_type_rows = _derived_schema_type_schemas()
            tools.extend(schema_type_schemas)
        specs.append(
            {
                "case_id": category_case_id.replace(
                    "category_branches_",
                    "field_normalization_",
                    1,
                ),
                "tools": tools,
                "targets": (),
                "field_normalization_contract": {
                    "category_case_id": category_case_id,
                    "operation": plan["operation"],
                    "lexical_token": plan["lexical_token"],
                    "lexical_read_fields": list(plan["lexical_read_fields"]),
                    "structural_token": plan["structural_token"],
                    "structural_read_fields": list(plan["structural_read_fields"]),
                    "structural_case_insensitive_fields": list(
                        STRUCTURAL_CASE_INSENSITIVE_FIELDS_BY_CATEGORY_CASE[
                            category_case_id
                        ]
                    ),
                    "token_plans": [
                        {
                            "token_kind": token_kind,
                            "token": token,
                            "read_fields": list(read_fields),
                        }
                        for token_kind, token, read_fields in token_plans
                    ],
                    "rows": rows,
                    "joined_scan_markers": list(
                        JOINED_NAME_DESCRIPTION_MARKERS_BY_CATEGORY_CASE.get(
                            category_case_id,
                            (),
                        )
                    ),
                    "cross_field_markers": list(
                        CROSS_FIELD_COMPOSITION_MARKERS_BY_CATEGORY_CASE[
                            category_case_id
                        ]
                    ),
                    "cross_field_variants": list(CROSS_FIELD_COMPOSITION_VARIANTS),
                    "composition_rows": composition_rows,
                    "whitespace_edge_variants": list(
                        JOINED_FIELD_WHITESPACE_EDGE_VARIANTS
                    ),
                    "whitespace_internal_placements": list(
                        JOINED_FIELD_WHITESPACE_INTERNAL_PLACEMENTS
                    ),
                    "whitespace_rows": whitespace_rows,
                    "schema_type_values": (
                        list(DERIVED_SCHEMA_TYPE_VALUES)
                        if category_case_id == "category_branches_derived_value"
                        else []
                    ),
                    "schema_type_casings": (
                        list(DERIVED_SCHEMA_TYPE_CASINGS)
                        if category_case_id == "category_branches_derived_value"
                        else []
                    ),
                    "schema_type_rows": schema_type_rows,
                },
            }
        )
    return tuple(specs)


def _producer_schema_location_case() -> dict[str, Any]:
    string = {"type": "string"}
    schemas: list[dict[str, Any]] = []
    expected: dict[str, tuple[str, ...]] = {}
    placements: dict[str, dict[str, str]] = {}
    aliases: list[str] = []
    for index, producer in enumerate(FIXTURE_SERVICE_PRODUCER_NAMES, start=1):
        raw_target = f"producer_raw_{index:02d}_{producer}_bridge"
        description_target = f"producer_description_{index:02d}"
        input_target = f"producer_input_{index:02d}"
        nested_target = f"producer_nested_{index:02d}"
        direct_target = f"producer_direct_{index:02d}"
        near_target = f"producer_near_{index:02d}"
        alias_first = f"producer_alias_{index:02d}_first"
        alias_second = f"producer_alias_{index:02d}_second"
        alias_target = f"producer_alias_{index:02d}_exec"
        near_spelling = producer.replace("_", "-")
        schemas.extend(
            (
                _schema(raw_target),
                _schema(description_target, description=producer),
                _schema(input_target, properties={producer: string}),
                _schema(
                    nested_target,
                    nested_output_properties={producer: string},
                ),
                _schema(direct_target, output_properties={producer: string}),
                _schema(near_target, description=near_spelling),
                _schema(alias_first, description=producer),
                _schema(alias_second, description="convert_currency unit_conversion"),
            )
        )
        expected.update(
            {
                raw_target: (producer,),
                description_target: (producer,),
                input_target: (producer,),
                nested_target: (producer,),
                direct_target: (),
                near_target: (),
                alias_target: (producer,),
            }
        )
        placements[producer] = {
            "raw_name": raw_target,
            "description": description_target,
            "input_property": input_target,
            "nested_output_property": nested_target,
            "direct_output_near_miss": direct_target,
            "lexical_near_miss": near_target,
            "alias_first_schema": alias_target,
        }
        aliases.append(alias_target)
    nonmember_target = "producer_nonmember_search_stock"
    schemas.append(_schema(nonmember_target, description="search_stock"))
    expected[nonmember_target] = ()
    return {
        "case_id": "producer_schema_locations",
        "tools": schemas,
        "targets": tuple(expected),
        "set_order_derived_targets": tuple(aliases),
        "producer_location_contract": {
            "expected_by_target": {
                target: list(producers) for target, producers in expected.items()
            },
            "placements_by_producer": placements,
            "nonmember_constant_near_misses": {"search_stock": nonmember_target},
            "direct_output_is_currently_not_scanned": True,
        },
    }


def _case_specs(actor: Any) -> tuple[dict[str, Any], ...]:
    return (
        {
            "case_id": "normal_catalog",
            "tools": _normal_catalog(),
            "targets": (
                "search_contacts",
                "generated_visible_selector",
                "generated_lookup_planner",
                "extract_service_answer_field",
                "missing_generated",
            ),
        },
        {
            "case_id": "aliases_and_duplicates",
            "tools": _alias_and_duplicate_schemas(),
            "targets": (
                "search_contacts",
                "generated_exec",
                "agent_generated_primary",
                "missing_generated",
            ),
            "set_order_derived_targets": ("generated_exec",),
        },
        {
            "case_id": "output_schema_boundaries",
            "tools": _output_schema_boundaries(),
            "targets": (
                "direct_and_nested",
                "nested_only",
                "empty_direct",
                "malformed_direct",
                "direct_output_planner",
                "nested_output_only_planner",
            ),
        },
        {
            "case_id": "mapping_and_malformed_members",
            "tools": _mapping_and_malformed_members(),
            "targets": (
                "mapping_function_exec",
                "mapping_parameters_exec",
                "mapping_outer",
                "properties_as_list",
            ),
        },
        {
            "case_id": "not_given",
            "tools": actor.NOT_GIVEN,
            "targets": ("search_contacts", "missing_generated"),
        },
        {
            "case_id": "empty",
            "tools": [],
            "targets": ("search_contacts", "missing_generated"),
        },
        *_category_branch_specs(),
        *_field_normalization_specs(),
        _producer_schema_location_case(),
    )


def _typed(value: Any) -> dict[str, Any]:
    if value is None:
        return {"python_type": "NoneType", "value": None}
    if isinstance(value, bool):
        return {"python_type": "bool", "value": value}
    if isinstance(value, int):
        return {"python_type": "int", "value": value}
    if isinstance(value, float):
        return {"python_type": "float", "value": value}
    if isinstance(value, str):
        return {"python_type": "str", "value": value}
    if isinstance(value, set):
        iteration = [_typed(item) for item in value]
        return {
            "python_type": "set",
            "iteration": iteration,
            "sorted": sorted(iteration, key=_stable_json),
        }
    if isinstance(value, (list, tuple)):
        return {
            "python_type": type(value).__name__,
            "items": [_typed(item) for item in value],
        }
    if isinstance(value, Mapping):
        return {
            "python_type": type(value).__name__,
            "items": [
                {"key": _typed(key), "value": _typed(item)}
                for key, item in value.items()
            ],
        }
    return {"python_type": type(value).__name__, "value": str(value)}


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _capture(call: Callable[[], Any]) -> dict[str, Any]:
    try:
        return {"status": "returned", "result": _typed(call())}
    except Exception as error:  # noqa: BLE001 - exception behavior is contractual.
        return {
            "status": "raised",
            "exception_type": type(error).__name__,
        }


def _returned_items(result: dict[str, Any]) -> list[str]:
    if result.get("status") != "returned":
        return []
    typed = result.get("result", {})
    values = typed.get("iteration", typed.get("items", []))
    return [str(item.get("value")) for item in values]


def _schema_order(tools: object, actor: Any) -> list[dict[str, Any]]:
    if tools is actor.NOT_GIVEN:
        return []
    rows: list[dict[str, Any]] = []
    for index, tool in enumerate(tools):
        try:
            function = tool.get("function", {})
            raw_name = function.get("name") if isinstance(function, Mapping) else None
        except Exception as error:  # noqa: BLE001 - malformed input is part of corpus.
            raw_name = f"<{type(error).__name__}:{error}>"
        rows.append({"index": index, "raw_name": _typed(raw_name)})
    return rows


def _run_collection_operations(actor: Any, tools: object) -> dict[str, Any]:
    return {
        name: _capture(lambda name=name: getattr(actor, name)(tools))
        for name in COLLECTION_OPERATIONS
    }


def _run_target_operations(
    actor: Any,
    tools: object,
    targets: tuple[str, ...],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for target in targets:
        rows.append(
            {
                "target": target,
                "operations": {
                    name: _capture(
                        lambda name=name, target=target: getattr(actor, name)(
                            tools, target
                        )
                    )
                    for name in TARGET_OPERATIONS
                },
            }
        )
    return rows


def _run_individual_schema_operations(
    actor: Any, tools: object
) -> list[dict[str, Any]]:
    if tools is actor.NOT_GIVEN:
        return []
    rows: list[dict[str, Any]] = []
    for index, tool in enumerate(tools):
        rows.append(
            {
                "index": index,
                "operations": {
                    name: _capture(
                        lambda name=name, tool=tool: getattr(actor, name)(tool)
                    )
                    for name in INDIVIDUAL_SCHEMA_OPERATIONS
                },
            }
        )
    return rows


def _freshness_contract(actor: Any, tools: object) -> dict[str, Any]:
    if tools is actor.NOT_GIVEN:
        return {"applicable": False}
    rows: dict[str, Any] = {}
    for name in COLLECTION_OPERATIONS:
        function = getattr(actor, name)
        first = function(tools)
        second = function(tools)
        same_identity = first is second
        mutation_supported = isinstance(first, (list, set))
        if isinstance(first, list):
            first.append("__validation_mutation__")
        elif isinstance(first, set):
            first.add("__validation_mutation__")
        third = function(tools)
        rows[name] = {
            "same_identity": same_identity,
            "mutation_supported": mutation_supported,
            "mutation_leaked": "__validation_mutation__" in third,
            "second_matches_fresh_third": _typed(second) == _typed(third),
        }
    return {"applicable": True, "operations": rows}


def _name_mapping_contract(actor: Any) -> dict[str, Any]:
    names = (
        "",
        "search_contacts",
        "functions.search_contacts",
        "agent_native_search",
        "agent_generated_primary",
        "generated_exec",
        "execution_mapping_error",
        "agent_mapping_error",
        "missing_generated",
    )
    return {
        name: {
            "agent_facing": _capture(
                lambda name=name: actor._agent_facing_tool_name(name)
            ),
            "execution_facing": _capture(
                lambda name=name: actor._execution_facing_tool_name(name)
            ),
        }
        for name in names
    }


def _generated_order_contract(
    actor: Any,
    tools: object,
    collection_results: dict[str, Any],
) -> dict[str, Any]:
    if tools is actor.NOT_GIVEN:
        return {"applicable": False}
    raw_iteration = _returned_items(collection_results["_tool_names"])
    execution_by_raw = {
        name: actor._execution_facing_tool_name(name) for name in raw_iteration
    }
    expected = [
        execution_by_raw[name]
        for name in raw_iteration
        if execution_by_raw[name] not in actor.ORIGINAL_TOOLSANDBOX_TOOL_NAMES
    ]
    actual = _returned_items(
        collection_results["_generated_tool_names_execution_facing"]
    )
    return {
        "applicable": True,
        "raw_name_set_iteration": raw_iteration,
        "execution_by_raw": execution_by_raw,
        "original_execution_names": sorted(actor.ORIGINAL_TOOLSANDBOX_TOOL_NAMES),
        "expected_generated_order": expected,
        "actual_generated_order": actual,
        "matches": actual == expected,
    }


def _selection_order_contract(
    actor: Any,
    tools: object,
    derived_targets: tuple[str, ...],
    target_results: list[dict[str, Any]],
    collection_results: dict[str, Any],
) -> list[dict[str, Any]]:
    if tools is actor.NOT_GIVEN or not derived_targets:
        return []
    raw_set_order = _returned_items(collection_results["_tool_names"])
    target_rows = {row["target"]: row for row in target_results}
    schemas = list(tools)
    rows: list[dict[str, Any]] = []
    for target in derived_targets:
        schema_first = None
        for schema in schemas:
            function = schema.get("function", {})
            raw_name = function.get("name") if isinstance(function, Mapping) else None
            if (
                isinstance(raw_name, str)
                and actor._execution_facing_tool_name(raw_name) == target
            ):
                schema_first = raw_name
                break
        set_first = next(
            (
                raw_name
                for raw_name in raw_set_order
                if actor._execution_facing_tool_name(raw_name) == target
            ),
            None,
        )
        result = target_rows[target]["operations"]["_tool_name_for_call"]
        actual = (
            result.get("result", {}).get("value")
            if result.get("status") == "returned"
            else None
        )
        rows.append(
            {
                "target": target,
                "schema_first_raw_name": schema_first,
                "set_first_raw_name": set_first,
                "actual_raw_name": actual,
                "actual_matches_set_first": actual == set_first,
            }
        )
    return rows


def _container_equivalence(actor: Any, tools: object) -> dict[str, Any]:
    if tools is actor.NOT_GIVEN:
        return {"applicable": False}
    source = list(tools)
    rows: dict[str, Any] = {}
    for name in COLLECTION_OPERATIONS:
        function = getattr(actor, name)
        variants = {
            "list": _capture(lambda function=function: function(copy.deepcopy(source))),
            "tuple": _capture(
                lambda function=function: function(tuple(copy.deepcopy(source)))
            ),
            "one_shot_iterator": _capture(
                lambda function=function: function(iter(copy.deepcopy(source)))
            ),
        }
        rows[name] = {
            "variants": variants,
            "list_equals_tuple": variants["list"] == variants["tuple"],
            "list_equals_iterator": variants["list"] == variants["one_shot_iterator"],
        }
    return {"applicable": True, "operations": rows}


def _boundary_exception_contract(actor: Any) -> dict[str, Any]:
    collection_boundaries: dict[str, Any] = {}
    for label, factory in (
        ("none", lambda: None),
        ("scalar_member", lambda: [42]),
        ("exploding_mapping", lambda: [ExplodingMapping({"function": {}})]),
    ):
        collection_boundaries[label] = {
            name: _capture(
                lambda name=name, factory=factory: getattr(actor, name)(factory())
            )
            for name in COLLECTION_OPERATIONS
        }
    individual_boundaries = {
        label: {
            name: _capture(lambda name=name, value=value: getattr(actor, name)(value))
            for name in INDIVIDUAL_SCHEMA_OPERATIONS
        }
        for label, value in (
            ("none", None),
            ("integer", 42),
            ("exploding_mapping", ExplodingMapping({"function": {}})),
        )
    }
    return {
        "collection_boundaries": collection_boundaries,
        "individual_boundaries": individual_boundaries,
    }


def _behavior_constant_inventories(actor: Any) -> dict[str, list[str]]:
    return {
        "ORIGINAL_TOOLSANDBOX_TOOL_NAMES": sorted(
            actor.ORIGINAL_TOOLSANDBOX_TOOL_NAMES
        ),
        "ORIGINAL_SIDE_EFFECT_TOOL_NAMES": sorted(
            actor.ORIGINAL_SIDE_EFFECT_TOOL_NAMES
        ),
        "SERVICE_ANSWER_PRODUCER_TOOLS": sorted(actor.SERVICE_ANSWER_PRODUCER_TOOLS),
    }


def _run_case(actor: Any, spec: dict[str, Any]) -> dict[str, Any]:
    tools = spec["tools"]
    before = None if tools is actor.NOT_GIVEN else _typed(copy.deepcopy(tools))
    collection_results = _run_collection_operations(actor, tools)
    target_results = _run_target_operations(actor, tools, spec["targets"])
    derived_targets = tuple(spec.get("set_order_derived_targets", ()))
    row = {
        "case_id": spec["case_id"],
        "schema_order": _schema_order(tools, actor),
        "input_before": before,
        "collection_operations": collection_results,
        "target_operations": target_results,
        "individual_schema_operations": _run_individual_schema_operations(actor, tools),
        "freshness": _freshness_contract(actor, tools),
        "container_equivalence": _container_equivalence(actor, tools),
        "generated_order_contract": _generated_order_contract(
            actor, tools, collection_results
        ),
        "set_order_derived_targets": list(derived_targets),
        "selection_order_contract": _selection_order_contract(
            actor,
            tools,
            derived_targets,
            target_results,
            collection_results,
        ),
    }
    if "category_branch_contract" in spec:
        row["category_branch_contract"] = copy.deepcopy(
            spec["category_branch_contract"]
        )
    if "field_normalization_contract" in spec:
        row["field_normalization_contract"] = copy.deepcopy(
            spec["field_normalization_contract"]
        )
    if "producer_location_contract" in spec:
        row["producer_location_contract"] = copy.deepcopy(
            spec["producer_location_contract"]
        )
    after = None if tools is actor.NOT_GIVEN else _typed(tools)
    row["input_after"] = after
    row["input_unchanged"] = before == after
    return row


def _canonicalize_for_manifest(body: dict[str, Any]) -> dict[str, Any]:
    canonical = copy.deepcopy(body)

    def normalize_typed(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("python_type") == "set":
                value["iteration"] = copy.deepcopy(value.get("sorted", []))
            for item in value.values():
                normalize_typed(item)
        elif isinstance(value, list):
            for item in value:
                normalize_typed(item)

    normalize_typed(canonical)

    def normalize_generated_lists(value: Any, *, generated_scope: bool = False) -> None:
        if isinstance(value, dict):
            if generated_scope and value.get("python_type") == "list":
                value["items"] = sorted(value.get("items", []), key=_stable_json)
            for key, item in value.items():
                normalize_generated_lists(
                    item,
                    generated_scope=(
                        generated_scope
                        or key == "_generated_tool_names_execution_facing"
                    ),
                )
        elif isinstance(value, list):
            for item in value:
                normalize_generated_lists(item, generated_scope=generated_scope)

    normalize_generated_lists(canonical)
    for case in canonical["cases"]:
        for target in case["target_operations"]:
            if target["target"] in case["set_order_derived_targets"]:
                result = target["operations"]["_tool_name_for_call"]
                if result.get("status") == "returned":
                    result["result"] = {
                        "python_type": "str",
                        "value": "<set-order-derived>",
                    }
        for selection in case["selection_order_contract"]:
            selection["set_first_raw_name"] = "<set-order-derived>"
            selection["actual_raw_name"] = "<set-order-derived>"
        order = case["generated_order_contract"]
        if order.get("applicable"):
            for key in (
                "raw_name_set_iteration",
                "expected_generated_order",
                "actual_generated_order",
            ):
                order[key] = sorted(order[key])
    return canonical


def _manifest_projection(body: dict[str, Any]) -> dict[str, Any]:
    return _canonicalize_for_manifest(body)


def _verify_generated_order(case: dict[str, Any]) -> None:
    order = case["generated_order_contract"]
    if not order.get("applicable"):
        return
    expected = [
        order["execution_by_raw"][name]
        for name in order["raw_name_set_iteration"]
        if order["execution_by_raw"][name] not in set(order["original_execution_names"])
    ]
    if order["expected_generated_order"] != expected:
        raise ValueError("stored generated-tool order derivation is inconsistent")
    if order["actual_generated_order"] != expected or not order["matches"]:
        raise ValueError("set-derived generated-tool ordering changed")


def _verify_set_order_tool_choice(case: dict[str, Any]) -> None:
    derived_targets = set(case["set_order_derived_targets"])
    if not derived_targets:
        return
    order = case["generated_order_contract"]
    raw_order = order["raw_name_set_iteration"]
    execution_by_raw = order["execution_by_raw"]
    target_rows = {row["target"]: row for row in case["target_operations"]}
    selection_rows = {row["target"]: row for row in case["selection_order_contract"]}
    if set(selection_rows) != derived_targets:
        raise ValueError("set-derived selection-order inventory changed")
    for target in derived_targets:
        execution_target = execution_by_raw.get(target, target)
        expected = next(
            (raw for raw in raw_order if execution_by_raw[raw] == execution_target),
            None,
        )
        result = target_rows[target]["operations"]["_tool_name_for_call"]
        actual = (
            result.get("result", {}).get("value")
            if result.get("status") == "returned"
            else None
        )
        if actual != expected:
            raise ValueError("set-derived tool-name selection ordering changed")
        selection = selection_rows[target]
        if (
            selection["set_first_raw_name"] != expected
            or selection["actual_raw_name"] != actual
            or not selection["actual_matches_set_first"]
        ):
            raise ValueError("schema-first versus set-first selection behavior changed")


def _verify_category_branch_contract(case: dict[str, Any]) -> None:
    branch = case.get("category_branch_contract")
    if not branch:
        return
    operation = branch["operation"]
    result = case["collection_operations"][operation]
    if result.get("status") != "returned":
        raise ValueError(f"category branch operation raised: {operation}")
    typed = result["result"]
    if typed.get("python_type") != "set":
        raise ValueError(f"category branch operation changed return type: {operation}")
    actual = {item["value"] for item in typed.get("iteration", [])}
    positives = branch["positives"]
    near_misses = branch["near_misses"]
    positive_names = {item["tool_name"] for item in positives}
    near_miss_names = {item["tool_name"] for item in near_misses}
    if len(positive_names) != len(positives) or len(near_miss_names) != len(
        near_misses
    ):
        raise ValueError(f"category branch fixture names are not unique: {operation}")
    if positive_names & near_miss_names:
        raise ValueError(f"category branch fixtures overlap: {operation}")
    case_id = case["case_id"]
    expected_exact_names = EXACT_NAMES_BY_CATEGORY_CASE[case_id]
    exact_rows = branch["exact_name_contract"]
    if tuple(row["exact_name"] for row in exact_rows) != expected_exact_names:
        raise ValueError(f"exact-name inventory changed: {operation}")
    exact_positive_names = tuple(
        row["tool_name"]
        for row in positives
        if row["alternative_id"] == "exact_name"
        or row["alternative_id"].startswith("exact_name_")
    )
    if exact_positive_names != expected_exact_names:
        raise ValueError(f"exact-name positives are not paired: {operation}")
    for row in exact_rows:
        if {
            row["suffix_near_miss"],
            row["prefix_near_miss"],
            row["uppercase_near_miss"],
            row["mixed_case_near_miss"],
            row["execution_alias_near_miss"],
            row["leading_space_near_miss"],
            row["trailing_space_near_miss"],
        } - near_miss_names:
            raise ValueError(f"exact-name near-miss pair changed: {operation}")

    expected_subsets = SUBSET_REQUIRED_FIELDS_BY_CATEGORY_CASE[case_id]
    subset_rows = branch["subset_extra_contract"]
    actual_subsets = tuple(
        (row["alternative_id"], tuple(row["required_inputs"])) for row in subset_rows
    )
    if actual_subsets != expected_subsets:
        raise ValueError(f"subset extra-field inventory changed: {operation}")
    positives_by_id = {row["alternative_id"]: row["tool_name"] for row in positives}
    for row in subset_rows:
        if positives_by_id.get(row["alternative_id"]) != row["positive_tool_name"]:
            raise ValueError(f"subset extra-field positive changed: {operation}")
    expected_non_subset = NON_SUBSET_INPUT_FIELDS_BY_CATEGORY_CASE[case_id]
    non_subset_rows = branch["non_subset_input_contract"]
    actual_non_subset = tuple(
        (row["alternative_id"], tuple(row["minimal_inputs"])) for row in non_subset_rows
    )
    if actual_non_subset != expected_non_subset:
        raise ValueError(f"non-subset input inventory changed: {operation}")
    for row in non_subset_rows:
        if positives_by_id.get(row["alternative_id"]) != row["positive_tool_name"]:
            raise ValueError(f"non-subset extra-field positive changed: {operation}")
    if actual != positive_names:
        raise ValueError(f"category branch alternatives changed: {operation}")


def _verify_field_normalization_contract(case: dict[str, Any]) -> None:
    contract = case.get("field_normalization_contract")
    if not contract:
        return
    category_case_id = contract["category_case_id"]
    expected_case_id = category_case_id.replace(
        "category_branches_",
        "field_normalization_",
        1,
    )
    if case["case_id"] != expected_case_id:
        raise ValueError("field-normalization case mapping changed")
    plan = FIELD_NORMALIZATION_PLANS[category_case_id]
    for key in (
        "operation",
        "lexical_token",
        "structural_token",
    ):
        if contract[key] != plan[key]:
            raise ValueError(f"field-normalization plan changed: {category_case_id}")
    for key in ("lexical_read_fields", "structural_read_fields"):
        if tuple(contract[key]) != tuple(plan[key]):
            raise ValueError(f"field-normalization field inventory changed: {key}")
    if tuple(contract["structural_case_insensitive_fields"]) != tuple(
        STRUCTURAL_CASE_INSENSITIVE_FIELDS_BY_CATEGORY_CASE[category_case_id]
    ):
        raise ValueError("field-normalization case inventory changed")
    expected_token_plans = _field_token_plans(category_case_id)
    actual_token_plans = tuple(
        (
            row["token_kind"],
            row["token"],
            tuple(row["read_fields"]),
        )
        for row in contract["token_plans"]
    )
    if actual_token_plans != expected_token_plans:
        raise ValueError("field-normalization token inventory changed")
    expected_probe_ids = tuple(
        f"{token_kind}_{field}_{casing}"
        for token_kind, _token, _read_fields in expected_token_plans
        for field in FIELD_MATRIX_FIELDS
        for casing in FIELD_MATRIX_CASINGS
    )
    rows = contract["rows"]
    if tuple(row["probe_id"] for row in rows) != expected_probe_ids:
        raise ValueError("field-normalization probe inventory changed")
    expected_joined_markers = JOINED_NAME_DESCRIPTION_MARKERS_BY_CATEGORY_CASE.get(
        category_case_id,
        (),
    )
    if tuple(contract["joined_scan_markers"]) != expected_joined_markers:
        raise ValueError("joined name/description marker inventory changed")
    expected_markers = CROSS_FIELD_COMPOSITION_MARKERS_BY_CATEGORY_CASE[
        category_case_id
    ]
    if tuple(contract["cross_field_markers"]) != expected_markers:
        raise ValueError("cross-field marker inventory changed")
    if tuple(contract["cross_field_variants"]) != CROSS_FIELD_COMPOSITION_VARIANTS:
        raise ValueError("cross-field variant inventory changed")
    _composition_schemas, expected_composition_rows = _cross_field_composition_schemas(
        category_case_id
    )
    composition_rows = contract["composition_rows"]
    if composition_rows != expected_composition_rows:
        raise ValueError("cross-field composition probes changed")
    if tuple(contract["whitespace_edge_variants"]) != (
        JOINED_FIELD_WHITESPACE_EDGE_VARIANTS
    ):
        raise ValueError("joined-field whitespace edge inventory changed")
    if tuple(contract["whitespace_internal_placements"]) != (
        JOINED_FIELD_WHITESPACE_INTERNAL_PLACEMENTS
    ):
        raise ValueError("joined-field whitespace placement inventory changed")
    _whitespace_schemas, expected_whitespace_rows = _joined_field_whitespace_schemas(
        category_case_id
    )
    whitespace_rows = contract["whitespace_rows"]
    if whitespace_rows != expected_whitespace_rows:
        raise ValueError("joined-field whitespace probes changed")
    expected_schema_type_values = (
        DERIVED_SCHEMA_TYPE_VALUES
        if category_case_id == "category_branches_derived_value"
        else ()
    )
    expected_schema_type_casings = (
        DERIVED_SCHEMA_TYPE_CASINGS
        if category_case_id == "category_branches_derived_value"
        else ()
    )
    if tuple(contract["schema_type_values"]) != expected_schema_type_values:
        raise ValueError("JSON-schema type inventory changed")
    if tuple(contract["schema_type_casings"]) != expected_schema_type_casings:
        raise ValueError("JSON-schema type casing inventory changed")
    expected_schema_type_rows: list[dict[str, Any]] = []
    if expected_schema_type_values:
        _schema_type_schemas, expected_schema_type_rows = _derived_schema_type_schemas()
    schema_type_rows = contract["schema_type_rows"]
    if schema_type_rows != expected_schema_type_rows:
        raise ValueError("JSON-schema type probes changed")
    boundary_rows = [
        *rows,
        *composition_rows,
        *whitespace_rows,
        *schema_type_rows,
    ]
    tool_names = [row["tool_name"] for row in boundary_rows]
    if len(set(tool_names)) != len(tool_names):
        raise ValueError("field-normalization tool names are not unique")
    operation = contract["operation"]
    result = case["collection_operations"][operation]
    if result.get("status") != "returned":
        raise ValueError(f"field-normalization operation raised: {operation}")
    typed = result["result"]
    if typed.get("python_type") != "set":
        raise ValueError(f"field-normalization return type changed: {operation}")
    actual = {item["value"] for item in typed.get("iteration", [])}
    expected = {row["tool_name"] for row in boundary_rows if row["expected_member"]}
    if actual != expected:
        raise ValueError(f"field-normalization behavior changed: {operation}")


def _verify_producer_location_contract(case: dict[str, Any]) -> None:
    producer = case.get("producer_location_contract")
    if not producer:
        return
    target_rows = {row["target"]: row for row in case["target_operations"]}
    expected_by_target = producer["expected_by_target"]
    if set(target_rows) != set(expected_by_target):
        raise ValueError("producer location target inventory changed")
    for target, expected in expected_by_target.items():
        result = target_rows[target]["operations"]["_declared_service_answer_producers"]
        if result.get("status") != "returned":
            raise ValueError(f"producer location accessor raised: {target}")
        actual = [item["value"] for item in result["result"].get("items", [])]
        if actual != expected:
            raise ValueError(f"producer schema location behavior changed: {target}")


def verify_actor_tool_schema_contract(contract: dict[str, Any]) -> None:
    body = {key: value for key, value in contract.items() if key != "integrity"}
    actual_body_digest = _digest(body)
    if contract.get("integrity", {}).get("body_sha256") != actual_body_digest:
        raise ValueError("actor tool-schema body digest does not match contents")
    if body.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise ValueError("actor tool-schema contract schema version changed")
    if tuple(case["case_id"] for case in body.get("cases", [])) != EXPECTED_CASE_IDS:
        raise ValueError("actor tool-schema case inventory changed")
    if tuple(body.get("collection_operations", ())) != COLLECTION_OPERATIONS:
        raise ValueError("actor tool-schema collection operation inventory changed")
    if tuple(body.get("target_operations", ())) != TARGET_OPERATIONS:
        raise ValueError("actor tool-schema target operation inventory changed")
    if tuple(body.get("individual_schema_operations", ())) != (
        INDIVIDUAL_SCHEMA_OPERATIONS
    ):
        raise ValueError("actor individual-schema operation inventory changed")
    expected_constants = {
        "ORIGINAL_TOOLSANDBOX_TOOL_NAMES": list(
            EXPECTED_ORIGINAL_TOOLSANDBOX_TOOL_NAMES
        ),
        "ORIGINAL_SIDE_EFFECT_TOOL_NAMES": list(
            EXPECTED_ORIGINAL_SIDE_EFFECT_TOOL_NAMES
        ),
        "SERVICE_ANSWER_PRODUCER_TOOLS": list(EXPECTED_SERVICE_ANSWER_PRODUCER_TOOLS),
    }
    if body.get("behavior_constant_inventories") != expected_constants:
        raise ValueError("actor behavior-defining constant inventory changed")
    for case in body["cases"]:
        if not case["input_unchanged"]:
            raise ValueError(f"actor schema input mutated: {case['case_id']}")
        freshness = case["freshness"]
        if freshness.get("applicable"):
            for name, result in freshness["operations"].items():
                if (
                    result["same_identity"]
                    or result["mutation_leaked"]
                    or not result["second_matches_fresh_third"]
                ):
                    raise ValueError(f"actor schema result was not fresh: {name}")
        _verify_generated_order(case)
        _verify_set_order_tool_choice(case)
        _verify_category_branch_contract(case)
        _verify_field_normalization_contract(case)
        _verify_producer_location_contract(case)
    actual_manifest = _digest(_manifest_projection(body))
    if EXPECTED_CANONICAL_SHA256 and actual_manifest != EXPECTED_CANONICAL_SHA256:
        raise ValueError(
            "actor tool-schema semantics differ from frozen reference contract"
        )
    if (
        os.environ.get("PYTHONHASHSEED") == "0"
        and not sys.flags.isolated
        and _digest(_seed_zero_exact_projection(contract))
        != EXPECTED_HASHSEED_ZERO_BODY_SHA256
    ):
        raise ValueError(
            "actor tool-schema hash-seed-zero semantics differ from frozen reference"
        )


def build_actor_tool_schema_contract() -> dict[str, Any]:
    from sage_ts.adapters import openai_toolsandbox_roles as actor

    original_context = actor.get_current_context
    actor.get_current_context = lambda: NameMappingContext()
    try:
        cases = [_run_case(actor, spec) for spec in _case_specs(actor)]
        body = {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "collection_operations": list(COLLECTION_OPERATIONS),
            "category_operations": list(CATEGORY_OPERATIONS),
            "target_operations": list(TARGET_OPERATIONS),
            "individual_schema_operations": list(INDIVIDUAL_SCHEMA_OPERATIONS),
            "behavior_constant_inventories": _behavior_constant_inventories(actor),
            "name_mapping": _name_mapping_contract(actor),
            "boundary_exceptions": _boundary_exception_contract(actor),
            "cases": cases,
        }
    finally:
        actor.get_current_context = original_context
    contract = dict(body)
    contract["integrity"] = {
        "body_sha256": _digest(body),
        "canonical_manifest_sha256": _digest(_manifest_projection(body)),
    }
    return contract


def _ordering_receipt(contract: dict[str, Any]) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for case in contract["cases"]:
        collection = case["collection_operations"]
        cases.append(
            {
                "case_id": case["case_id"],
                "generated_name_order": _returned_items(
                    collection["_generated_tool_names_execution_facing"]
                ),
                "selection_order_contract": case["selection_order_contract"],
            }
        )
    return {"cases": cases}


def _seed_zero_exact_projection(contract: dict[str, Any]) -> dict[str, Any]:
    """Keep exact order only where set order reaches actor-visible behavior."""

    body = {key: value for key, value in contract.items() if key != "integrity"}
    return {
        "canonical_body": _manifest_projection(body),
        "order_receipt": _ordering_receipt(contract),
    }


def _seeded_child_payload(root: Path, seed: int) -> dict[str, Any]:
    if os.environ.get("PYTHONHASHSEED") != str(seed) or sys.flags.isolated:
        raise RuntimeError(
            "seeded child must be non-isolated with the requested PYTHONHASHSEED"
        )
    resolved = root.expanduser().resolve()
    required = (resolved / "pyproject.toml", resolved / "src" / "sage_ts")
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise ValueError(f"Not a SAGE checkout; missing: {missing}")
    sys.path[:] = [str(resolved / "src"), str(resolved), *sys.path]
    os.chdir(resolved)
    contract = build_actor_tool_schema_contract()
    verify_actor_tool_schema_contract(contract)
    semantic_body_digest = _digest(_seed_zero_exact_projection(contract))
    ordering = _ordering_receipt(contract)
    order_digest = _digest(ordering)
    if seed == 0 and semantic_body_digest != EXPECTED_HASHSEED_ZERO_BODY_SHA256:
        raise ValueError(
            "actor tool-schema seed-zero semantic body differs from reference"
        )
    if seed == 0 and order_digest != EXPECTED_HASHSEED_ZERO_ORDER_SHA256:
        raise ValueError("actor tool-schema seed-zero ordering differs from reference")
    aliases = next(
        case
        for case in contract["cases"]
        if case["case_id"] == "aliases_and_duplicates"
    )
    return {
        "hash_seed": seed,
        "body_sha256": semantic_body_digest,
        "ordering_sha256": order_digest,
        "selection_order_contract": aliases["selection_order_contract"],
    }


def _run_seeded_child(root: Path, seed: int) -> dict[str, Any]:
    environment = dict(os.environ)
    for name in list(environment):
        if name.startswith("SAGE_") or name in {
            "PYTHONHOME",
            "PYTHONPATH",
            "PYTHONSAFEPATH",
        }:
            environment.pop(name, None)
    environment.update(
        {
            "PYTHONHASHSEED": str(seed),
            "PYTHONDONTWRITEBYTECODE": "1",
            "LANG": "C",
            "LC_ALL": "C",
            "TZ": "UTC",
        }
    )
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--seeded-child-root",
        str(root),
        "--seeded-child-seed",
        str(seed),
    ]
    completed = subprocess.run(
        command,
        cwd=root,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Actor tool-schema seed-{seed} child failed "
            f"(exit {completed.returncode})\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return json.loads(completed.stdout)


def _run_seed_zero_child(root: Path) -> dict[str, Any]:
    return _run_seeded_child(root, 0)


def run_probe(root: Any) -> dict[str, Any]:
    contract = build_actor_tool_schema_contract()
    verify_actor_tool_schema_contract(contract)
    body = {key: value for key, value in contract.items() if key != "integrity"}
    return {
        "contract": _manifest_projection(body),
        "seed_zero_exact": _run_seed_zero_child(Path(root)),
        "integrity": {
            "canonical_manifest_sha256": contract["integrity"][
                "canonical_manifest_sha256"
            ],
            "process_local_generated_order_verified": True,
            "process_local_tool_name_selection_verified": True,
        },
    }


def _rehash(contract: dict[str, Any]) -> None:
    body = {key: value for key, value in contract.items() if key != "integrity"}
    contract["integrity"] = {
        "body_sha256": _digest(body),
        "canonical_manifest_sha256": _digest(_manifest_projection(body)),
    }


def _tamper_self_test(contract: dict[str, Any]) -> None:
    unhashed = copy.deepcopy(contract)
    unhashed["cases"][0]["schema_order"][0]["raw_name"]["value"] = "tampered"
    try:
        verify_actor_tool_schema_contract(unhashed)
    except ValueError:
        pass
    else:
        raise AssertionError("unhashed actor tool-schema tamper was not rejected")

    reordered = copy.deepcopy(contract)
    order = reordered["cases"][0]["generated_order_contract"]
    order["actual_generated_order"].reverse()
    _rehash(reordered)
    try:
        verify_actor_tool_schema_contract(reordered)
    except ValueError:
        pass
    else:
        raise AssertionError("generated-order actor schema tamper was not rejected")

    semantic = copy.deepcopy(contract)
    selector = semantic["cases"][0]["collection_operations"]["_selector_tool_names"][
        "result"
    ]
    selector["iteration"].append(_typed("tampered_selector"))
    selector["sorted"] = sorted(selector["iteration"], key=_stable_json)
    _rehash(semantic)
    try:
        verify_actor_tool_schema_contract(semantic)
    except ValueError:
        pass
    else:
        raise AssertionError("rehashed actor schema semantic tamper was not rejected")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tamper-self-test", action="store_true")
    parser.add_argument("--print-canonical-sha", action="store_true")
    parser.add_argument("--seeded-child-root", type=Path)
    parser.add_argument("--seeded-child-seed", type=int)
    args = parser.parse_args()
    if args.seeded_child_root is not None:
        if args.seeded_child_seed is None:
            parser.error("--seeded-child-root requires --seeded-child-seed")
        print(
            json.dumps(
                _seeded_child_payload(
                    args.seeded_child_root,
                    args.seeded_child_seed,
                ),
                sort_keys=True,
            )
        )
        return 0
    contract = build_actor_tool_schema_contract()
    if args.print_canonical_sha:
        print(contract["integrity"]["canonical_manifest_sha256"])
        return 0
    verify_actor_tool_schema_contract(contract)
    if args.tamper_self_test:
        _tamper_self_test(contract)
    print(
        json.dumps(
            {
                "case_count": len(contract["cases"]),
                "collection_operation_count": len(COLLECTION_OPERATIONS),
                "category_operation_count": len(CATEGORY_OPERATIONS),
                "target_operation_count": len(TARGET_OPERATIONS),
                "tamper_self_test": args.tamper_self_test,
                "canonical_manifest_sha256": contract["integrity"][
                    "canonical_manifest_sha256"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
