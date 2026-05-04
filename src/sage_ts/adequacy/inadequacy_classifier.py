"""Artifact-backed capability observations for online tool birth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sage_ts.generation.tool_spec import StructuredInadequacyEvidence, ToolFamily
from sage_ts.validation.sandbox_validator import ToolExample
from tool_sandbox.common.execution_context import ScenarioCategories
from tool_sandbox.common.scenario import Scenario


def _similarity(result: dict[str, Any]) -> float:
    value = result.get("similarity", 0.0)
    try:
        return float(value) if isinstance(value, (int, float, str)) else 0.0
    except ValueError:
        return 0.0


def _is_latest_record_scenario(scenario_name: str) -> bool:
    return scenario_name.startswith(("modify_contact_with_message_recency",))


def _is_message_search_window_scenario(scenario_name: str) -> bool:
    return scenario_name.startswith("modify_contact_with_message_recency")


def _is_message_recency_extreme_scenario(scenario_name: str) -> bool:
    return scenario_name.startswith(
        (
            "search_message_with_recency_latest",
            "search_message_with_recency_oldest",
        )
    )


def _is_contact_constraint_scenario(scenario_name: str) -> bool:
    return "ambiguous" not in scenario_name and scenario_name.startswith(
        (
            "search_phone_number_with_name",
            "search_relationship_with_phone_number",
            "search_name_with_relationship",
            "update_contact_relationship_with_relationship",
        )
    )


def _is_direct_service_precondition_scenario(scenario_name: str) -> bool:
    return "insufficient_information" not in scenario_name and scenario_name.startswith(
        (
            "turn_on_wifi_low_battery_mode",
            "turn_on_cellular_low_battery_mode",
            "turn_on_location_low_battery_mode",
            "wifi_off",
            "cellular_off",
            "send_message_with_contact_content_cellular_off",
        )
    )


def _is_reminder_optional_location_argument_scenario(scenario_name: str) -> bool:
    return (
        "insufficient_information" not in scenario_name
        and scenario_name.startswith("add_reminder_content_and_")
        and "_time" in scenario_name
    )


def _reminder_optional_location_argument_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="composite:prepare_reminder_creation_args",
        observation=(
            "Reminder creation tasks with relative date/time and optional location "
            "repeatedly fail after the agent has enough visible information to call "
            "the original add_reminder ToolSandbox side-effect tool. The missing "
            "capability is not another side effect; it is deterministic argument "
            "preparation. Generate a small trace-compatible helper named "
            "prepare_reminder_creation_args and use it immediately before "
            "add_reminder as the normal final step once reminder content and time "
            "are known. Inputs: content, "
            "resolved_reminder_timestamp, current_timestamp, day_offset, hour, "
            "minute, local_utc_offset_hours, location_requested, location_required, "
            "location_available, latitude, longitude, and location_lookup_failed. "
            "Return a dict with add_reminder_kwargs, should_call_add_reminder, "
            "abstain_reason, location_status, and timestamp_source. "
            "add_reminder_kwargs must be directly splattable into the original "
            "ToolSandbox add_reminder(content, reminder_timestamp, latitude, "
            "longitude) side-effect tool. If resolved_reminder_timestamp is "
            "present, use it directly. Otherwise use local-day timestamp "
            "arithmetic, not current_timestamp plus raw hours. Formula: "
            "offset_seconds = local_utc_offset_hours * 3600; local_seconds = "
            "current_timestamp + offset_seconds; local_midnight = floor("
            "local_seconds / 86400) * 86400; reminder_timestamp = local_midnight "
            "+ day_offset * 86400 - offset_seconds + hour * 3600 + minute * 60. "
            "Prefer resolved_reminder_timestamp whenever current benchmark "
            "timestamp context already makes the reminder time clear. In "
            "ToolSandbox reminder creation, plain relative times like 'tomorrow "
            "at 5 PM' mean local device time by default, so do not ask the user "
            "for timezone or UTC offset again unless the request is truly "
            "ambiguous. "
            "Set location_requested to true when the user mentioned a location "
            "that you would like to attach if resolution succeeds. Set "
            "location_required to true only when the user explicitly requires "
            "the created reminder to include a location. "
            "If optional location is unavailable or a lookup already failed, do "
            "not invent coordinates: include latitude None and longitude None in "
            "add_reminder_kwargs, set location_status to omitted_optional, and "
            "still allow the original add_reminder call. If an optional location "
            "is still being chosen or refined and lookup has not failed yet, "
            "abstain with location_status lookup_pending and do not call "
            "add_reminder yet instead of creating the reminder prematurely. "
            "After that optional location is resolved or explicitly skipped, "
            "call this helper again before add_reminder. If location is "
            "explicitly required but "
            "unresolved, abstain instead of retrying blindly. This "
            "helper must preserve the original ToolSandbox add_reminder call by "
            "preparing arguments only; it must not create or modify reminders "
            "itself."
        ),
        allowed_families=(str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "content": "Buy tickets",
                    "resolved_reminder_timestamp": None,
                    "current_timestamp": 0.0,
                    "day_offset": 1,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": 0.0,
                    "location_requested": False,
                    "location_required": False,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": True,
                },
                {
                    "add_reminder_kwargs": {
                        "content": "Buy tickets",
                        "reminder_timestamp": 147600.0,
                        "latitude": None,
                        "longitude": None,
                    },
                    "should_call_add_reminder": True,
                    "abstain_reason": "",
                    "location_status": "omitted_optional",
                    "timestamp_source": "relative_fields",
                },
            ),
            ToolExample(
                {
                    "content": "Team meeting",
                    "resolved_reminder_timestamp": 1777500000.0,
                    "current_timestamp": 1777428906.0,
                    "day_offset": 0,
                    "hour": 0,
                    "minute": 0,
                    "local_utc_offset_hours": 0.0,
                    "location_requested": False,
                    "location_required": False,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": False,
                },
                {
                    "add_reminder_kwargs": {
                        "content": "Team meeting",
                        "reminder_timestamp": 1777500000.0,
                        "latitude": None,
                        "longitude": None,
                    },
                    "should_call_add_reminder": True,
                    "abstain_reason": "",
                    "location_status": "omitted_optional",
                    "timestamp_source": "resolved",
                },
                held_out=True,
            ),
            ToolExample(
                {
                    "content": "Meet at park",
                    "resolved_reminder_timestamp": None,
                    "current_timestamp": 0.0,
                    "day_offset": 1,
                    "hour": 14,
                    "minute": 0,
                    "local_utc_offset_hours": 0.0,
                    "location_requested": True,
                    "location_required": True,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": True,
                },
                {
                    "add_reminder_kwargs": {},
                    "should_call_add_reminder": False,
                    "abstain_reason": "required_location_unresolved",
                    "location_status": "required_missing",
                    "timestamp_source": "relative_fields",
                },
                negative_applicability=True,
            ),
            ToolExample(
                {
                    "content": "Buy chocolate milk at Whole Foods",
                    "resolved_reminder_timestamp": 1777776000.0,
                    "current_timestamp": 1777687768.0,
                    "day_offset": 1,
                    "hour": 17,
                    "minute": 0,
                    "local_utc_offset_hours": 0.0,
                    "location_requested": True,
                    "location_required": False,
                    "location_available": False,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "location_lookup_failed": False,
                },
                {
                    "add_reminder_kwargs": {},
                    "should_call_add_reminder": False,
                    "abstain_reason": (
                        "optional_location_lookup_pending_do_not_call_add_reminder"
                    ),
                    "location_status": "lookup_pending",
                    "timestamp_source": "resolved",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="reminder_creation_argument_preparation_failure",
        inadequacy_signals=(
            "optional_info_treated_as_required",
            "visible_raw_data_lacking_deterministic_transform",
        ),
        visible_data_gaps=(
            "relative day/time and optional location must be converted into add_reminder kwargs",
        ),
    )


def _message_search_window_observation(scenario_name: str) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="derived_value:message_search_time_window",
        observation=(
            "Contact/message recency tasks fail before ranking because the base "
            "search_messages tool requires at least one concrete search criterion. "
            "When the user asks for the latest or oldest contact they messaged but "
            "does not know the contact id or phone number, the agent needs a "
            "deterministic way to create broad timestamp bounds so it can call the "
            "original search_messages benchmark tool and retrieve visible candidate "
            "records. Generate a small trace-compatible helper named "
            "message_search_time_window. Inputs: anchor_timestamp as a float Unix "
            "timestamp and lookback_days as an integer number of days. Return a dict "
            "with creation_timestamp_lowerbound and creation_timestamp_upperbound. "
            "The lower bound is anchor_timestamp - lookback_days * 86400 and the "
            "upper bound is anchor_timestamp. Clamp negative lookback_days to zero. "
            "This helper must not inspect messages, contacts, hidden state, or "
            "replace search_messages; it only produces benchmark-compatible "
            "arguments for the original search tool."
        ),
        allowed_families=(str(ToolFamily.DERIVED_VALUE_CALCULATOR),),
        validation_examples=(
            ToolExample(
                {
                    "anchor_timestamp": 864000.0,
                    "lookback_days": 2,
                },
                {
                    "creation_timestamp_lowerbound": 691200.0,
                    "creation_timestamp_upperbound": 864000.0,
                },
            ),
            ToolExample(
                {
                    "anchor_timestamp": 1000.0,
                    "lookback_days": 0,
                },
                {
                    "creation_timestamp_lowerbound": 1000.0,
                    "creation_timestamp_upperbound": 1000.0,
                },
            ),
            ToolExample(
                {
                    "anchor_timestamp": 1000.0,
                    "lookback_days": -5,
                },
                {
                    "creation_timestamp_lowerbound": 1000.0,
                    "creation_timestamp_upperbound": 1000.0,
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="contact_message_search_requires_trace_compatible_time_bounds",
        inadequacy_signals=(
            "repeated_failed_tool_call",
            "visible_raw_data_lacking_deterministic_transform",
        ),
        failed_tool_calls=("search_messages",),
        visible_data_gaps=("missing benchmark-compatible timestamp window",),
    )


def _latest_record_selection_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="search_filter:select_record_by_timestamp_extreme",
        observation=(
            "Repeated latest-result scenarios require choosing the timestamp "
            "extreme from a visible list returned by search tools. Agents can "
            "compute valid search bounds but still select or report the wrong "
            "candidate. Generate the shared deterministic search/filter/ranking "
            "helper named select_record_by_timestamp_extreme rather than a "
            "latest-only variant. Inputs: records as a list of record "
            "dictionaries copied directly from the visible search-tool result, "
            "timestamp_key as the timestamp field to compare, and selection_mode as either 'latest' "
            "or 'oldest'. Ignore records missing a numeric timestamp. Return the "
            "full selected record, or an empty dict if no valid timestamp exists."
        ),
        allowed_families=(str(ToolFamily.SEARCH_FILTER_RANKING_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "records": [
                        {"content": "older", "creation_timestamp": 10.0},
                        {"content": "newer", "creation_timestamp": 20.0},
                    ],
                    "timestamp_key": "creation_timestamp",
                    "selection_mode": "latest",
                },
                {"content": "newer", "creation_timestamp": 20.0},
            ),
            ToolExample(
                {
                    "records": [
                        {"content": "missing"},
                        {"content": "old", "reminder_timestamp": 5.0},
                        {"content": "new", "reminder_timestamp": 15.0},
                    ],
                    "timestamp_key": "reminder_timestamp",
                    "selection_mode": "latest",
                },
                {"content": "new", "reminder_timestamp": 15.0},
            ),
            ToolExample(
                {
                    "records": [{"content": "none"}],
                    "timestamp_key": "creation_timestamp",
                    "selection_mode": "latest",
                },
                {},
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="repeated_latest_record_selection_failure",
        inadequacy_signals=("wrong_selected_record",),
        visible_data_gaps=(
            "visible candidate list requires deterministic extreme selection",
        ),
    )


def _days_between_timestamps_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="derived_value:days_between_timestamps",
        observation=(
            "Holiday/calendar tasks repeatedly require computing the same "
            "deterministic timestamp difference that the reduced base toolset no "
            "longer exposes through timestamp_diff. The agent can still call "
            "get_current_timestamp and search_holiday, but it needs a small "
            "value-producing helper named days_between_timestamps that accepts "
            "timestamp_0 and timestamp_1 floats and returns a dict with integer "
            "days and seconds matching Python datetime timedelta semantics for "
            "timestamp_1 - timestamp_0. This is reusable for future calendar and "
            "deadline-distance tasks and does not require hidden answers."
        ),
        allowed_families=(str(ToolFamily.DERIVED_VALUE_CALCULATOR),),
        validation_examples=(
            ToolExample(
                {"timestamp_0": 0.0, "timestamp_1": 86400.0},
                {"days": 1, "seconds": 0},
            ),
            ToolExample(
                {"timestamp_0": 0.0, "timestamp_1": 90061.0},
                {"days": 1, "seconds": 3661},
            ),
            ToolExample(
                {"timestamp_0": 1000.0, "timestamp_1": 1000.0},
                {"days": 0, "seconds": 0},
            ),
        ),
        generation_allowed=True,
        reason="reduced_base_missing_timestamp_diff_for_calendar_distance",
        inadequacy_signals=("visible_raw_data_lacking_deterministic_transform",),
        visible_data_gaps=(
            "holiday timestamp and current timestamp need day-distance computation",
        ),
    )


def _contact_constraint_observation(scenario_name: str) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="search_filter:select_contact_field_by_constraint",
        observation=(
            "Repeated contact lookup scenarios require selecting one visible contact "
            "candidate and extracting the exact field needed for the downstream "
            "answer or original ToolSandbox action. Generate a small deterministic "
            "search/filter helper named select_contact_field_by_constraint. "
            "Inputs: records as a list of contact "
            "dictionaries copied directly from the visible search_contacts result, "
            "match_field as the contact field to match, expected_value as the "
            "target value, and output_field as the field to return. "
            "For phone_number matching, normalize both sides to digits. For "
            "string fields, compare case-insensitively after trimming. Return "
            "a dict containing selected_record and value, or an empty dict if "
            "there is not exactly one match or the output field is missing. "
            "The spec.output_schema must be a JSON Schema object with properties "
            "selected_record and value. Include negative_triggers for no candidates, "
            "ambiguous matches or ties, missing output field, and insufficient "
            "constraints. The spec.required_original_tool_calls must include "
            "search_contacts. The spec.preserves_side_effect_tools must include "
            "search_contacts and should include modify_contact when the selected "
            "contact will feed a downstream update. This helper only selects from "
            "visible records and prepares evidence; it must not replace the original "
            "ToolSandbox search_contacts or modify_contact calls."
        ),
        allowed_families=(str(ToolFamily.SEARCH_FILTER_RANKING_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "records": [
                        {
                            "name": "Ada Lovelace",
                            "person_id": "a",
                            "phone_number": "+1 (555) 0100",
                            "relationship": "friend",
                        },
                        {
                            "name": "Grace Hopper",
                            "person_id": "b",
                            "phone_number": "+1 (555) 0200",
                            "relationship": "coworker",
                        },
                    ],
                    "match_field": "phone_number",
                    "expected_value": "15550200",
                    "output_field": "person_id",
                },
                {
                    "selected_record": {
                        "name": "Grace Hopper",
                        "person_id": "b",
                        "phone_number": "+1 (555) 0200",
                        "relationship": "coworker",
                    },
                    "value": "b",
                },
            ),
            ToolExample(
                {
                    "records": [
                        {
                            "name": "Ada Lovelace",
                            "person_id": "a",
                            "phone_number": "+1 (555) 0100",
                        }
                    ],
                    "match_field": "name",
                    "expected_value": " ada lovelace ",
                    "output_field": "phone_number",
                },
                {
                    "selected_record": {
                        "name": "Ada Lovelace",
                        "person_id": "a",
                        "phone_number": "+1 (555) 0100",
                    },
                    "value": "+1 (555) 0100",
                },
            ),
            ToolExample(
                {
                    "records": [
                        {"person_id": "a", "relationship": "friend"},
                        {"person_id": "b", "relationship": "friend"},
                    ],
                    "match_field": "relationship",
                    "expected_value": "friend",
                    "output_field": "person_id",
                },
                {},
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="repeated_contact_candidate_selection_failure",
        inadequacy_signals=("wrong_selected_record",),
        visible_data_gaps=(
            "visible contact candidates need deterministic field-constrained selection",
        ),
    )


def _stock_symbol_extraction_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="derived_value:extract_stock_symbol",
        observation=(
            "Stock lookup scenarios repeatedly require extracting the benchmark "
            "answer field from a visible search_stock result. The base tool can "
            "return a dictionary with symbol values such as 'NASDAQ:AAPL' or "
            "'AAPL', but agents sometimes fail to normalize and report the symbol "
            "only. Generate a small deterministic helper named extract_stock_symbol. "
            "Input: stock_payload dict returned by search_stock. Return the symbol "
            "string with any exchange prefix removed, or an empty string if the "
            "payload does not contain a usable string symbol."
        ),
        allowed_families=(str(ToolFamily.DERIVED_VALUE_CALCULATOR),),
        validation_examples=(
            ToolExample({"stock_payload": {"symbol": "NASDAQ:AAPL"}}, "AAPL"),
            ToolExample({"stock_payload": {"symbol": "AAPL"}}, "AAPL"),
            ToolExample({"stock_payload": {"name": "Apple"}}, ""),
        ),
        generation_allowed=True,
        reason="stock_symbol_field_extraction_failure",
        inadequacy_signals=("visible_raw_data_lacking_deterministic_transform",),
        visible_data_gaps=(
            "visible stock payload requires deterministic symbol extraction",
        ),
    )


def _next_service_tool_call_observation(
    scenario_name: str,
) -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=scenario_name,
        canonical_key="state_precondition:next_service_tool_call",
        observation=(
            "Direct service-precondition tasks repeatedly require deciding the "
            "single next original ToolSandbox tool call needed to enable wifi, "
            "cellular, or location service. Existing advisory state helpers are "
            "trace-misaligned because they return informal action strings instead "
            "of benchmark tool names and arguments. Generate a deterministic "
            "state-precondition helper named next_service_tool_call. Inputs: "
            "target_service string ('wifi', 'cellular', or 'location'), "
            "wifi_enabled bool, cellular_enabled bool, location_service_enabled "
            "bool, and low_battery_mode bool. The spec.output_schema must be a "
            "JSON Schema object with properties tool_name, arguments, should_call, "
            "and reason. tool_name must have exactly this enum: '', "
            "'set_wifi_status', 'set_cellular_service_status', "
            "'set_location_service_status', and 'set_low_battery_mode_status'. "
            "Do not omit should_call. Return a dict with ready bool, tool_name "
            "string, arguments dict, should_call bool, and reason string. If the "
            "target service is already enabled, return ready True, empty "
            "tool_name, empty arguments, should_call False, and a reason. If "
            "low_battery_mode is true and the "
            "target is not enabled, return tool_name 'set_low_battery_mode_status' "
            "with arguments {'on': False} and should_call True. Otherwise return the exact original "
            "ToolSandbox setter: wifi -> set_wifi_status, cellular -> "
            "set_cellular_service_status, location -> set_location_service_status, "
            "always with arguments {'on': True} and should_call True. This helper is for one chosen "
            "target service at a time; it must not encourage calling parallel or "
            "alternative service flows for unrelated targets. After the caller "
            "uses the returned ToolSandbox tool call, it should report only the "
            "final state of that chosen target service unless the user explicitly "
            "asks to broaden scope. For unknown target services, return ready "
            "False, empty tool_name, empty arguments, should_call False, and a "
            "brief reason. negative_triggers must include already_ready, "
            "unknown_target_service, and insufficient_state. "
            "spec.required_original_tool_calls and spec.preserves_side_effect_tools "
            "must include the relevant original setter tools."
        ),
        allowed_families=(str(ToolFamily.STATE_PRECONDITION_HELPER),),
        validation_examples=(
            ToolExample(
                {
                    "target_service": "wifi",
                    "wifi_enabled": False,
                    "cellular_enabled": True,
                    "location_service_enabled": True,
                    "low_battery_mode": True,
                },
                {
                    "ready": False,
                    "tool_name": "set_low_battery_mode_status",
                    "arguments": {"on": False},
                    "should_call": True,
                    "reason": "wifi cannot be enabled while low battery mode is on",
                },
            ),
            ToolExample(
                {
                    "target_service": "cellular",
                    "wifi_enabled": True,
                    "cellular_enabled": False,
                    "location_service_enabled": True,
                    "low_battery_mode": False,
                },
                {
                    "ready": False,
                    "tool_name": "set_cellular_service_status",
                    "arguments": {"on": True},
                    "should_call": True,
                    "reason": "cellular is disabled and must be enabled first",
                },
            ),
            ToolExample(
                {
                    "target_service": "location",
                    "wifi_enabled": True,
                    "cellular_enabled": True,
                    "location_service_enabled": True,
                    "low_battery_mode": False,
                },
                {
                    "ready": True,
                    "tool_name": "",
                    "arguments": {},
                    "should_call": False,
                    "reason": "location is already enabled",
                },
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="trace_compatible_service_precondition_next_tool_call",
        inadequacy_signals=("failed_base_tool_with_deterministic_fallback",),
        failed_tool_calls=(
            "set_wifi_status",
            "set_cellular_service_status",
            "set_location_service_status",
        ),
    )


@dataclass(frozen=True)
class CapabilityObservation:
    scenario_name: str
    canonical_key: str
    observation: str
    allowed_families: tuple[str, ...]
    validation_examples: tuple[ToolExample, ...]
    generation_allowed: bool
    reason: str
    inadequacy_signals: tuple[str, ...] = ()
    failed_tool_calls: tuple[str, ...] = ()
    repeated_failed_tool_calls: tuple[str, ...] = ()
    visible_data_gaps: tuple[str, ...] = ()
    planner_failures: tuple[str, ...] = ()
    final_answer_route_mismatch: bool = False
    # "heuristic" = scenario-name prefix only; "transcript_verified" = signal confirmed in transcript
    evidence_source: str = "heuristic"

    def to_inadequacy_evidence(self) -> StructuredInadequacyEvidence:
        return StructuredInadequacyEvidence(
            summary=self.observation,
            signals=self.inadequacy_signals,
            failed_tool_calls=self.failed_tool_calls,
            repeated_failed_tool_calls=self.repeated_failed_tool_calls,
            visible_data_gaps=self.visible_data_gaps,
            planner_failures=self.planner_failures,
            final_answer_route_mismatch=self.final_answer_route_mismatch,
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "canonical_key": self.canonical_key,
            "observation": self.observation,
            "allowed_families": list(self.allowed_families),
            "validation_examples": [
                {
                    "inputs": item.inputs,
                    "expected": item.expected,
                    "held_out": item.held_out,
                    "negative_applicability": item.negative_applicability,
                }
                for item in self.validation_examples
            ],
            "generation_allowed": self.generation_allowed,
            "reason": self.reason,
            "evidence_source": self.evidence_source,
            "inadequacy_evidence": self.to_inadequacy_evidence().to_json(),
        }


def classify_scenario_observations(
    scenario_name: str,
    scenario: Scenario,
    result: dict[str, Any],
) -> tuple[CapabilityObservation, ...]:
    """Classify only narrow, repeated ToolSandbox hard-mode observations."""
    categories = {str(category) for category in scenario.categories}
    similarity = _similarity(result)
    raw_outcome_similarity = result.get("outcome_similarity")
    try:
        outcome_similarity = (
            float(raw_outcome_similarity)
            if isinstance(raw_outcome_similarity, (int, float, str))
            else None
        )
    except ValueError:
        outcome_similarity = None
    route_mismatch = bool(
        outcome_similarity is not None and outcome_similarity > similarity
    )
    if ScenarioCategories.INSUFFICIENT_INFORMATION in scenario.categories:
        return (
            CapabilityObservation(
                scenario_name=scenario_name,
                canonical_key="insufficient_information",
                observation=(
                    "Scenario is marked insufficient-information; this should be "
                    "stored as abstention/guard evidence, not immediate tool birth."
                ),
                allowed_families=(str(ToolFamily.VALIDATION_ABSTENTION_HELPER),),
                validation_examples=(),
                generation_allowed=False,
                reason="insufficient_information_observation_only",
                inadequacy_signals=("missing_user_information",),
                planner_failures=("abstain_or_clarify_instead_of_birth",),
            ),
        )

    if similarity < 1.0 and (
        "recency" in scenario_name
        and ScenarioCategories.CANONICALIZATION in scenario.categories
    ):
        # Validation constants: day 10 boundary (all values are exact float arithmetic)
        _ts = float(10 * 86400)  # 864000.0
        _yesterday_start = float(9 * 86400)  # 777600.0
        _today_ts = float(10 * 86400 + 3600)  # 867600.0
        _today_start = float(10 * 86400)  # 864000.0
        observations = [
            CapabilityObservation(
                scenario_name=scenario_name,
                canonical_key="derived_value:recency_timestamp_bounds",
                observation=(
                    "ToolSandbox scenarios repeatedly require converting user-facing "
                    "bounded recency words (yesterday, today, upcoming) into "
                    "Unix timestamp lower/upper bounds to pass to search tools "
                    "(search_reminder, search_messages). The base toolset provides "
                    "get_current_timestamp, timestamp_to_datetime_info, and "
                    "datetime_info_to_timestamp as building blocks but not a single "
                    "recency-to-bounds helper. Agents must make 3+ extra calls and "
                    "are error-prone on day boundary arithmetic."
                ),
                allowed_families=(str(ToolFamily.DERIVED_VALUE_CALCULATOR),),
                validation_examples=(
                    ToolExample(
                        {"recency_label": "yesterday", "current_timestamp": _ts},
                        {"lower_bound": _yesterday_start, "upper_bound": _ts},
                    ),
                    ToolExample(
                        {"recency_label": "today", "current_timestamp": _today_ts},
                        {"lower_bound": _today_start, "upper_bound": _today_ts},
                    ),
                ),
                generation_allowed=True,
                reason=f"categories:{','.join(sorted(categories))}",
                inadequacy_signals=(
                    "visible_raw_data_lacking_deterministic_transform",
                ),
                visible_data_gaps=(
                    "bounded recency label must become timestamp lower/upper bounds",
                ),
                final_answer_route_mismatch=route_mismatch,
            )
        ]
        if scenario_name.startswith("modify_reminder_with_recency_latest"):
            observations.append(
                CapabilityObservation(
                    scenario_name=scenario_name,
                    canonical_key="canonicalizer:relative_day_time_timestamp",
                    observation=(
                        "Repeated modify_reminder recency scenarios require turning "
                        "a user-facing relative date/time such as 'tomorrow 5PM' "
                        "into the exact local Unix timestamp passed to "
                        "modify_reminder. In the reduced base toolset the date/time "
                        "decomposition helpers are absent, so agents find the right "
                        "reminder but often write the wrong timestamp. Generate a "
                        "small deterministic canonicalizer named "
                        "relative_day_time_to_timestamp that accepts current_timestamp, "
                        "day_offset, hour, minute, and local_utc_offset_hours. Use "
                        "local_utc_offset_hours=-4 for the current ToolSandbox local "
                        "environment unless another offset is explicitly known."
                    ),
                    allowed_families=(str(ToolFamily.CANONICALIZER),),
                    validation_examples=(
                        ToolExample(
                            {
                                "current_timestamp": 1777428906.194959,
                                "day_offset": 1,
                                "hour": 17,
                                "minute": 0,
                                "local_utc_offset_hours": -4,
                            },
                            1777496400.0,
                        ),
                        ToolExample(
                            {
                                "current_timestamp": 1777428906.194959,
                                "day_offset": 2,
                                "hour": 8,
                                "minute": 30,
                                "local_utc_offset_hours": -4,
                            },
                            1777552200.0,
                        ),
                    ),
                    generation_allowed=True,
                    reason="repeated_modify_reminder_relative_datetime_failure",
                    inadequacy_signals=(
                        "visible_raw_data_lacking_deterministic_transform",
                    ),
                    visible_data_gaps=(
                        "relative day/time must become exact benchmark timestamp",
                    ),
                    final_answer_route_mismatch=route_mismatch,
                )
            )
        if _is_latest_record_scenario(
            scenario_name
        ) or _is_message_recency_extreme_scenario(scenario_name):
            observations.append(_latest_record_selection_observation(scenario_name))
        if _is_message_search_window_scenario(
            scenario_name
        ) or _is_message_recency_extreme_scenario(scenario_name):
            observations.append(_message_search_window_observation(scenario_name))
        return tuple(observations)

    if similarity < 1.0 and _is_reminder_optional_location_argument_scenario(
        scenario_name
    ):
        return (_reminder_optional_location_argument_observation(scenario_name),)

    if similarity < 1.0 and (
        _is_latest_record_scenario(scenario_name)
        or _is_message_search_window_scenario(scenario_name)
        or _is_message_recency_extreme_scenario(scenario_name)
    ):
        observations = []
        if _is_latest_record_scenario(
            scenario_name
        ) or _is_message_recency_extreme_scenario(scenario_name):
            observations.append(_latest_record_selection_observation(scenario_name))
        if _is_message_search_window_scenario(
            scenario_name
        ) or _is_message_recency_extreme_scenario(scenario_name):
            observations.append(_message_search_window_observation(scenario_name))
        return tuple(observations)

    if similarity < 1.0 and _is_contact_constraint_scenario(scenario_name):
        return (_contact_constraint_observation(scenario_name),)

    if similarity < 1.0 and scenario_name.startswith("find_days_till_holiday"):
        return (_days_between_timestamps_observation(scenario_name),)

    if similarity < 1.0 and scenario_name.startswith(
        "find_stock_symbol_with_company_name"
    ):
        return (_stock_symbol_extraction_observation(scenario_name),)

    if similarity < 1.0 and _is_direct_service_precondition_scenario(scenario_name):
        return (_next_service_tool_call_observation(scenario_name),)

    if result.get("similarity") == 0:
        return (
            CapabilityObservation(
                scenario_name=scenario_name,
                canonical_key="failed:unclassified",
                observation=(
                    "Scenario failed, but no narrow repeated SAGE helper class is "
                    "eligible yet."
                ),
                allowed_families=(),
                validation_examples=(),
                generation_allowed=False,
                reason="no_repeated_supported_pattern",
                inadequacy_signals=("no_valid_deterministic_helper_opportunity",),
            ),
        )
    return ()
