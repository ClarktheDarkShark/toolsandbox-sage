"""Structured generation of deterministic helper tools."""

from __future__ import annotations

import ast
import inspect
import json
import re
from dataclasses import dataclass, replace
from typing import Any, Protocol

from sage_ts.adapters.openai_agent_adapter import ChatRequest
from sage_ts.generation.complete_tools import (
    COMPLETE_TOOLS_NATIVE_NAMES,
    COMPLETE_TOOLS_PROMPT_CONSTRAINT,
    native_side_effect_tools,
)
from sage_ts.generation.tool_spec import (
    GeneratedTool,
    StructuredInadequacyEvidence,
    ToolFamily,
    ToolInput,
    ToolSpec,
)


class ChatCompleter(Protocol):
    model: str

    def complete(self, request: ChatRequest) -> str: ...


@dataclass(frozen=True)
class ToolGenerationRequest:
    scenario_name: str
    observation: str
    allowed_families: tuple[str, ...]
    validation_examples: tuple[dict[str, object], ...] = ()
    suggested_tool_name: str | None = None
    inadequacy_evidence: dict[str, object] | None = None
    failure_memory_context: dict[str, object] | None = None
    shortfall_cluster_context: dict[str, object] | None = None

    def prompt(self) -> str:
        families = ", ".join(self.allowed_families)
        examples = (
            f" Validation examples: {json.dumps(list(self.validation_examples))}."
            if self.validation_examples
            else ""
        )
        tool_name_hint = (
            f' The tool_name must be exactly "{self.suggested_tool_name}".'
            if self.suggested_tool_name
            else ""
        )
        evidence = (
            f" Structured inadequacy evidence: {json.dumps(self.inadequacy_evidence)}."
            if self.inadequacy_evidence
            else ""
        )
        failure_memory = (
            f" Relevant unresolved failure memory: {json.dumps(self.failure_memory_context)}. "
            "If this repeats a prior mechanism, set diagnostic_only=true unless the "
            "design explicitly names the mechanism in known_failure_mechanisms_addressed "
            "and explains the material repair in reason_tool_is_decisive."
            if self.failure_memory_context
            else ""
        )
        cluster_context = (
            f" Shortfall cluster context: {json.dumps(self.shortfall_cluster_context)}. "
            "If non_diagnostic_birth_allowed is false, set diagnostic_only=true. "
            "If it is true, cite cluster_id or failure_mechanism in "
            "shortfall_cluster_evidence."
            if self.shortfall_cluster_context
            else ""
        )
        dependency_contract = (
            "tool_name must have an enum containing '' plus the original ToolSandbox "
            "set_* or enable/disable precondition tools that may be returned. Include "
            "negative_triggers for already ready state, unknown target dependency, "
            "and insufficient state. State/precondition helpers must not require an "
            "opaque dict input such as dependency_state; expose concrete top-level "
            "scalar inputs for every required visible state value instead, for "
            "example target_action, blocked_reason, service_ready, blocker_active, "
            "and blocker_kind. "
        )
        synthesis_guidance = (
            "For selection/planning helpers, synthesize explicit positive triggers, "
            "negative triggers, no-match behavior, multiple-match behavior, tie or "
            "ambiguity abstention behavior, and side-effect-risk behavior in the "
            "description and abstain_behavior. Do not rely on implicit selection "
            "rules. "
        )
        medium_grain_guidance = (
            "Medium-grain skill experiment guidance: when the observation asks for "
            "a constraint-to-action, visible-record workflow, prefer a single "
            "composite_workflow_helper that accepts records: list, match_field: str, "
            "match_value: str, action_type: str, update_fields: dict, and "
            "return_field: str. Do not split this into a thin selector plus a "
            "separate side-effect preparer. The helper must normalize constraints "
            "internally, including stripping non-digits from both sides for phone "
            "or number fields, select exactly one visible record, abstain on ties "
            "or missing data, and return downstream_tool_name plus "
            "downstream_tool_kwargs for the preserved original ToolSandbox action. "
            "It must also support answer_field by returning value with "
            "should_call_tool=false and empty downstream kwargs. The spec must "
            "name every returned original side-effect tool in both "
            "preserves_side_effect_tools and required_original_tool_calls; for "
            "contact actions this includes modify_contact, remove_contact, and "
            "send_message when those action types are supported. "
        )
        return (
            "Propose one deterministic Python helper tool as valid JSON. Return "
            'exactly one JSON object with top-level keys "spec" and either '
            '"code_lines" or "code". Prefer "code_lines": a list of Python source '
            'lines, one line per string. Use "code": a single Python source string '
            "only if every backslash and quote is valid JSON escaping. "
            '"spec" must have: tool_name (str), family (str from allowed list), '
            "description (str), "
            'inputs (list of objects each with exactly keys "name", "annotation", '
            '"description"), '
            "output_annotation (str), output_schema (object|null), "
            "positive_triggers (list[str]), negative_triggers (list[str]), "
            "preserves_side_effect_tools (list[str]), "
            "required_original_tool_calls (list[str]), abstain_behavior (str), "
            "generalization_rationale (str), estimated_step_compression (int), "
            "cross_task_applicability_count (int), "
            "applicable_task_families (list[str]), reason_tool_is_decisive (str), "
            "diagnostic_only (bool), shortfall_cluster_evidence (list[str]), "
            "known_failure_mechanisms_addressed (list[str]), "
            "inadequacy_evidence (object). "
            "inadequacy_evidence must include: summary (str), signals (list[str]), "
            "failed_tool_calls (list[str]), repeated_failed_tool_calls (list[str]), "
            "visible_data_gaps (list[str]), planner_failures (list[str]), "
            "final_answer_route_mismatch (bool). "
            "Reject thin helpers: only propose a tool when it compresses at least 3 "
            "reasoning/tool-use steps, applies across at least 2 task families, "
            "preserves required downstream ToolSandbox tools, and does more than "
            "replace a single existing base tool. "
            f"{synthesis_guidance}"
            f"{medium_grain_guidance}"
            "Use concrete scenario-family labels in applicable_task_families, "
            "not helper-family labels such as canonicalizer, state_precondition_helper, "
            "search_filter_ranking_helper, or timestamp_conversion. "
            "Set diagnostic_only true only when the evidence is from a single task "
            "or no recurring shortfall cluster is available. Claim-grade candidates "
            "must set diagnostic_only false and include shortfall_cluster_evidence "
            "naming at least one recurring mechanism plus "
            "known_failure_mechanisms_addressed naming the concrete failure modes "
            "the helper is intended to repair. "
            "If family is search_filter_ranking_helper, output_schema must be a "
            "JSON Schema object with type 'object' and properties including "
            "selected_record. Include value or selected_id when the helper returns "
            "a field/id. Include negative_triggers for no candidates, ambiguous "
            "matches, missing fields, and insufficient constraints. The helper must "
            "use only visible records/candidates passed as inputs and must abstain "
            "with an empty dict when no unique safe selection exists. "
            "For visible-record constraint selectors, prefer simple inputs "
            "records: list, field_name: str, expected_value: str, and "
            "return_field: str. Avoid opaque constraints dict inputs when one "
            "field/value pair is enough; flat scalar inputs are more callable by "
            "the acting model. Return "
            "selected_record, selected_index, selected_id, value, "
            "matched_constraints, tie_candidates, and abstain_reason. "
            "Generated code must compare the record value at record[field_name] "
            "against expected_value. Normalize BOTH sides before comparing: "
            "for phone/number fields keep only digits from both the visible record "
            "value and expected_value; otherwise strip and lowercase both strings. "
            "Do not compare raw formatted phone strings to digit-only expected "
            "values. If return_field is present in the selected record, value must "
            "be selected_record[return_field]; otherwise value should be selected_id. "
            "selected_id should use the first available stable id among person_id, "
            "message_id, reminder_id, sender_person_id, recipient_person_id, or id. "
            "On ambiguous ties, selected_record must be empty and tie_candidates "
            "must include every tied visible record, including the first matching "
            "record, and matched_constraints must still include field_name. "
            "The exact ambiguity output contract is selected_index=-1, "
            "selected_id='', value='', selected_record={}, and tie_candidates "
            "containing ALL matching records; never leave the first match in "
            "selected_id/value when abstaining for ambiguity. "
            "For next-weekday reminder timestamp canonicalizers, use tool_name "
            "next_weekday_time_to_timestamp with inputs current_timestamp: float, "
            "target_isoweekday: int where Monday=1 and Sunday=7, hour: int, "
            "minute: int, and local_utc_offset_hours: float. Return a float Unix "
            "timestamp for the next matching local weekday/time strictly after the "
            "current local timestamp; if the target weekday is today and the target "
            "time is still in the future, use today, otherwise use seven days "
            "later. Do not call add_reminder from this helper. "
            "For recency action-target selectors, prefer inputs records: list, "
            "timestamp_key: str, selection_mode: str, action_type: str, and "
            "constraints: dict plus updates: dict for modify actions. Treat "
            "constraints and updates as optional; the generated function must work "
            "when either is omitted or {}, using {} as the default case. Return "
            "selected_record, selected_index, selected_id, selected_timestamp, "
            "action_type, downstream_tool_name, downstream_tool_kwargs, "
            "should_call_tool, tie_candidates, abstain_reason, and safety_notes. "
            "For unique matches, tie_candidates must be an empty list. For "
            "reminder actions, selected_id and downstream_tool_kwargs must use "
            "reminder_id. For contact actions, selected_id and "
            "downstream_tool_kwargs must use person_id; do not use message_id as "
            "a contact id. If only one of sender_person_id or recipient_person_id "
            "is present, that can be used as person_id, but if both are present "
            "and differ, abstain unless the record already has person_id. Remove "
            "actions may set should_call_tool true with only the id. Modify "
            "actions must merge explicit updates and abstain when updates is {}. "
            "On timestamp ties, selected_record must be empty and tie_candidates "
            "must include every record sharing the best timestamp, including the "
            "first best record. "
            "If family is state_precondition_helper, output_schema must be a JSON "
            "Schema object with type 'object' and properties exactly covering the "
            "runtime contract: tool_name, arguments, should_call, and reason. "
            f"{dependency_contract}"
            "If family is validation_abstention_helper, output_schema must be a "
            "JSON Schema object with type 'object' and properties exactly covering "
            "the safe-abstention contract: should_abstain, missing_information, "
            "required_original_tools, safe_next_action, final_answer_recommendation, "
            "and abstain_reason. It must never execute or prepare a side-effect "
            "tool call; it only returns whether the actor should abstain or safely "
            "continue with original ToolSandbox tools. It still must declare the "
            "original ToolSandbox tools it guards in required_original_tool_calls "
            "or preserves_side_effect_tools so the safety gate can verify that "
            "side-effect preservation remains explicit. "
            "If family is composite_workflow_helper, output_schema must be a JSON "
            "Schema object with type 'object' and properties including a key ending "
            "in _kwargs, should_call_tool, and abstain_reason. For post-selection "
            "side-effect preparation, prefer low-friction call patterns: either "
            "records: list plus explicit selection/action inputs when the helper is "
            "expected to run immediately after an original search result, or "
            "selected_record: dict when a prior selector/search produced one clear "
            "record. If selected_record is used, positive_triggers and description "
            "must say to call only after a unique visible record exists; the runtime "
            "may safely autofill selected_record from the latest original search_* "
            "result only when that result contains exactly one record. Use inputs "
            "action_type: str, updates: dict, and user_intent: str as needed. Return "
            "downstream_tool_name, downstream_tool_kwargs, should_call_tool, and "
            "abstain_reason. The function should safely handle omitted optional "
            "chaining inputs by using empty-dict defaults for selected_record and "
            "updates, and empty-string defaults for optional scalar update fields "
            "such as name, relationship, phone_number, email, target_field, "
            "new_value, and message_text. It should abstain when selected_record "
            "is unavailable. Remove/delete "
            "actions may use empty updates. Normalize common action aliases before "
            "branching: remove/delete -> remove_contact when selected_record has "
            "person_id, modify/update/change -> modify_contact when selected_record "
            "has person_id, remove/delete -> remove_reminder when selected_record "
            "has reminder_id, and modify/update/change -> modify_reminder when "
            "selected_record has reminder_id. Modify/update actions must abstain "
            "unless updates contains at least one concrete field to change. The "
            "helper must prepare arguments only and preserve the original "
            "ToolSandbox side-effect call. "
            "For any direct contact/message side-effect helper that prepares "
            "phone_number kwargs, phone normalization must preserve ToolSandbox "
            "phone validity: strip spaces/dashes/parentheses/dots, keep an existing "
            "leading '+', and if the visible user input starts with '+' then the "
            "returned phone_number must also start with '+'. Do not return "
            "digit-only phone numbers when validation examples expect an "
            "E.164-style leading plus. Exact E.164 normalization rule: after "
            "stripping non-digits, if there are 11 digits and the first digit is "
            "'1', return '+' plus those 11 digits; if there are 10 digits, return "
            "'+1' plus those 10 digits; otherwise preserve an existing leading '+' "
            "with the stripped digits. Never prepend '+1' to an 11-digit US number "
            "that already starts with country code 1. For name and relationship "
            "search kwargs, preserve the original case and spacing except for "
            "leading/trailing whitespace; do not lowercase display names. On "
            "abstention, returned tool-name and kwargs fields must be empty when "
            "the output contract says should_call/should_call_search is false. "
            "If family is derived_value_calculator and output_annotation is dict, "
            "output_schema must be a JSON Schema object with type 'object' and "
            "properties for every returned key. It must preserve a downstream "
            "original ToolSandbox call such as search_*, modify_*, send_*, set_*, "
            "or add_* in required_original_tool_calls or preserves_side_effect_tools. "
            "Annotations must be exactly one of: str, int, float, bool, dict, list. "
            'If the output is a dictionary, output_annotation must be exactly "dict". '
            '"code_lines" or "code" must define a self-contained Python function '
            "with exactly one function whose name matches spec.tool_name. The "
            "function signature must "
            "include type annotations matching spec.inputs and spec.output_annotation. "
            "Do not include imports, try/except, classes, lambdas, raise statements, "
            "filesystem access, network access, subprocess calls, side effects, hidden "
            "global state, or wrapper functions. Return safe fallback values instead "
            "of raising exceptions. "
            "The function must pass every validation example exactly. Treat the "
            "validation examples as the executable public contract for the tool: "
            "preserve field names, booleans, empty strings, empty dictionaries, "
            "None/null values, and wording in expected output values exactly. "
            "When expected outputs contain actor-facing text such as "
            "final_answer_recommendation, answer_value, safe_next_action, "
            "abstain_reason, or safety_notes, infer the reusable text template "
            "from the examples and fill it from visible input/record fields; do "
            "not invent alternate phrasing. "
            f"{tool_name_hint} "
            f"Allowed families: {families}. "
            f"Scenario: {self.scenario_name}. Observation: {self.observation}."
            f"{evidence}{failure_memory}{cluster_context}{examples}"
        )


class ToolGenerator:
    def __init__(self, completer: ChatCompleter) -> None:
        self.completer = completer

    def generate(self, request: ToolGenerationRequest) -> GeneratedTool:
        prompt = _model_authored_generation_prompt(request)
        prompt += self._contract_analysis_suffix(request)
        response = self.completer.complete(
            ChatRequest(
                system=(
                    "You generate safe deterministic Python helper tools. "
                    "Return valid JSON only."
                ),
                user=prompt,
                model=self.completer.model,
                response_format_json=True,
            )
        )
        tools = parse_generated_tool_candidates_json(
            response, default_tool_name=request.suggested_tool_name
        )
        return _select_model_authored_candidate(request, tools)

    def repair(
        self,
        request: ToolGenerationRequest,
        rejected_tool: GeneratedTool,
        errors: tuple[str, ...],
    ) -> GeneratedTool:
        tools = self.repair_candidates(request, rejected_tool, errors)
        if not tools:
            raise ValueError("tool repair returned no candidates")
        return _select_model_authored_candidate(request, list(tools))

    def repair_candidates(
        self,
        request: ToolGenerationRequest,
        rejected_tool: GeneratedTool,
        errors: tuple[str, ...],
    ) -> tuple[GeneratedTool, ...]:
        """Return every independently authored repair for contract validation."""

        prompt = _model_authored_repair_prompt(request, rejected_tool, errors)
        prompt += self._contract_analysis_suffix(request)
        prompt += self._repair_analysis_suffix(request, rejected_tool, errors)
        prompt += _model_authored_final_repair_directive(request, errors)
        response = self.completer.complete(
            ChatRequest(
                system=(
                    "You repair rejected deterministic Python helper tools. "
                    "Return valid JSON only."
                ),
                user=prompt,
                model=self.completer.model,
                response_format_json=True,
            )
        )
        tools = parse_generated_tool_candidates_json(
            response, default_tool_name=request.suggested_tool_name
        )
        return tuple(_normalize_model_authored_tool(request, tool) for tool in tools)

    def _contract_analysis_suffix(self, request: ToolGenerationRequest) -> str:
        if not _request_complete_tools_enabled(request):
            return ""
        analysis_prompt = _model_authored_contract_analysis_prompt(request)
        analysis = self.completer.complete(
            ChatRequest(
                system=(
                    "You analyze public generated-tool validation contracts. "
                    "Return valid JSON only and do not write code."
                ),
                user=analysis_prompt,
                model=self.completer.model,
                response_format_json=True,
            )
        )
        return (
            " A separate model-authored contract analysis follows. Use it as a "
            "reasoning aid, but the public validation examples remain authoritative. "
            "Do not copy example constants or descriptive paths into code. Analysis: "
            + analysis
        )

    def _repair_analysis_suffix(
        self,
        request: ToolGenerationRequest,
        rejected_tool: GeneratedTool,
        errors: tuple[str, ...],
    ) -> str:
        if not _request_complete_tools_enabled(request):
            return ""
        analysis_prompt = _model_authored_repair_analysis_prompt(
            request, rejected_tool, errors
        )
        analysis = self.completer.complete(
            ChatRequest(
                system=(
                    "You trace rejected generated Python tools against public "
                    "validation cases. Return valid JSON only and do not write "
                    "replacement code."
                ),
                user=analysis_prompt,
                model=self.completer.model,
                response_format_json=True,
            )
        )
        return (
            " A separate model-authored trace of the current rejected code follows. "
            "Use its concrete blocking-condition analysis when repairing, but keep "
            "the public validation examples authoritative. Repair trace: " + analysis
        )


def _model_authored_candidate_count() -> int:
    return 3


def _model_authored_repair_candidate_count() -> int:
    return 3


MODEL_AUTHORED_DEFAULT_FAMILIES_BY_TOOL: dict[str, tuple[str, ...]] = {
    "plan_contact_lookup_query": (
        "contact_lookup",
        "contact_phone_lookup",
        "contact_relationship_lookup",
    ),
    "plan_contact_relationship_batch_update": (
        "relationship_batch_update",
        "contact_bulk_update",
        "contact_lookup",
    ),
    "prepare_reminder_creation_args": (
        "reminder_create",
        "relative_time",
        "location_phrase",
    ),
    "relative_day_time_to_timestamp": (
        "relative_time",
        "reminder_create",
    ),
    "next_weekday_time_to_timestamp": (
        "weekday_time",
        "reminder_create",
    ),
    "prepare_location_search_args": (
        "location_phrase",
        "reminder_create",
        "external_lookup",
    ),
    "prepare_specific_location_search_args": (
        "location_phrase",
        "reminder_create",
        "external_lookup",
    ),
    "prepare_broad_location_search_args": (
        "location_phrase",
        "reminder_create",
        "external_lookup",
    ),
    "plan_message_counterparty_search": (
        "message_counterparty_lookup",
        "message",
        "contact_lookup",
    ),
    "select_message_counterparty_for_contact_update": (
        "message_counterparty_update",
        "message_recency",
        "modify_contact",
    ),
    "resolve_search_window_or_bounds": (
        "recency_search",
        "message_recency",
        "reminder_recency",
        "recency_action",
    ),
    "prepare_upcoming_reminder_search_args": (
        "upcoming_reminder_search",
        "reminder_due_time_search",
    ),
    "prepare_message_recency_search_args": (
        "message_recency_search",
        "message_recency",
        "message_counterparty_update",
    ),
    "prepare_past_reminder_recency_search_args": (
        "past_reminder_recency_search",
        "reminder_creation_recency_search",
    ),
    "select_record_by_timestamp_extreme": (
        "recency_search",
        "message_recency",
        "reminder_recency",
    ),
    "select_message_content_by_recency": (
        "message_recency",
        "recency_search",
    ),
    "select_action_target_by_recency": (
        "recency_action",
        "modify_reminder",
        "remove_reminder",
    ),
    "prepare_holiday_search_args": (
        "holiday_lookup",
        "holiday_timestamp",
        "calendar_distance",
    ),
    "days_between_timestamps": (
        "calendar_distance",
        "holiday_distance",
        "timestamp_difference",
    ),
    "plan_device_status_lookup": (
        "device_status_read",
        "wifi_status_read",
        "cellular_status_read",
    ),
    "plan_device_state_action_sequence_v3": (
        "device_state_action",
        "wifi_service_recovery",
        "cellular_service_recovery",
        "location_service_recovery",
        "low_battery_precondition_recovery",
        "blocked_downstream_task_continuation",
    ),
    "plan_device_state_action_sequence_location_recovery": (
        "device_state_action",
        "location_service_recovery",
        "wifi_service_recovery",
        "low_battery_precondition_recovery",
        "blocked_downstream_location_task_continuation",
    ),
    "plan_send_message_contact_lookup": (
        "named_message_recipient",
        "contact_lookup",
        "send_message",
    ),
    "prepare_direct_contact_action_args": (
        "direct_contact_action",
        "add_contact",
        "modify_contact",
        "remove_contact",
        "send_message",
    ),
    "prepare_safe_action_or_abstain": (
        "safe_abstain",
        "contact_lookup",
        "side_effect_guard",
    ),
    "extract_service_answer_field": (
        "service_answer_extraction",
        "convert_currency",
        "find_phone_number",
        "find_distance",
        "weather_lookup",
    ),
    "extract_address_result": ("service_answer_extraction", "find_address"),
    "extract_converted_amount_result": (
        "service_answer_extraction",
        "convert_currency",
    ),
    "extract_phone_number_result": (
        "service_answer_extraction",
        "find_phone_number",
    ),
    "extract_distance_result": ("service_answer_extraction", "find_distance"),
    "extract_temperature_result": (
        "service_answer_extraction",
        "weather_lookup",
        "temperature_lookup",
    ),
}


MODEL_AUTHORED_DEFAULT_ORIGINAL_CALLS_BY_TOOL: dict[str, tuple[str, ...]] = {
    "plan_contact_lookup_query": ("search_contacts",),
    "plan_contact_relationship_batch_update": (
        "search_contacts",
        "modify_contact",
    ),
    "prepare_reminder_creation_args": ("add_reminder",),
    "prepare_location_search_args": (
        "get_current_location",
        "search_location_around_lat_lon",
    ),
    "prepare_specific_location_search_args": ("search_location_around_lat_lon",),
    "prepare_broad_location_search_args": (
        "get_current_location",
        "search_location_around_lat_lon",
    ),
    "plan_message_counterparty_search": ("search_contacts", "search_messages"),
    "select_message_counterparty_for_contact_update": (
        "search_messages",
        "modify_contact",
    ),
    "resolve_search_window_or_bounds": ("search_reminder", "search_messages"),
    "prepare_upcoming_reminder_search_args": ("search_reminder",),
    "prepare_message_recency_search_args": ("search_messages",),
    "prepare_past_reminder_recency_search_args": ("search_reminder",),
    "select_record_by_timestamp_extreme": ("search_reminder", "search_messages"),
    "select_message_content_by_recency": ("search_messages",),
    "select_action_target_by_recency": (
        "search_reminder",
        "modify_reminder",
        "remove_reminder",
    ),
    "prepare_holiday_search_args": ("search_holiday",),
    "days_between_timestamps": ("get_current_timestamp", "search_holiday"),
    "plan_device_status_lookup": (
        "get_wifi_status",
        "get_cellular_service_status",
        "get_location_service_status",
        "get_low_battery_mode_status",
    ),
    "plan_device_state_action_sequence_v3": (
        "set_wifi_status",
        "set_cellular_service_status",
        "set_location_service_status",
        "set_low_battery_mode_status",
    ),
    "plan_device_state_action_sequence_location_recovery": (
        "set_location_service_status",
        "set_low_battery_mode_status",
        "set_wifi_status",
    ),
    "plan_send_message_contact_lookup": (
        "search_contacts",
        "send_message_with_phone_number",
    ),
    "prepare_direct_contact_action_args": (
        "add_contact",
        "modify_contact",
        "remove_contact",
        "send_message_with_phone_number",
    ),
    "prepare_safe_action_or_abstain": (
        "search_contacts",
        "remove_contact",
        "modify_contact",
        "send_message_with_phone_number",
    ),
    "extract_service_answer_field": (
        "search_location_around_lat_lon",
        "search_lat_lon",
        "search_weather_around_lat_lon",
        "calculate_lat_lon_distance",
        "convert_currency",
    ),
    "extract_address_result": ("search_lat_lon", "search_location_around_lat_lon"),
    "extract_converted_amount_result": ("convert_currency",),
    "extract_phone_number_result": ("search_location_around_lat_lon",),
    "extract_distance_result": ("calculate_lat_lon_distance",),
    "extract_temperature_result": ("search_weather_around_lat_lon",),
    "extract_stock_symbol": ("search_stock",),
    "relative_day_time_to_timestamp": (
        "get_current_timestamp",
        "timestamp_to_datetime_info",
        "add_reminder",
        "modify_reminder",
    ),
    "next_weekday_time_to_timestamp": (
        "get_current_timestamp",
        "timestamp_to_datetime_info",
        "add_reminder",
        "modify_reminder",
    ),
}


def _request_native_action_names(request: ToolGenerationRequest) -> tuple[str, ...]:
    """Infer approved native actions from public generation evidence."""

    allowed = set(COMPLETE_TOOLS_NATIVE_NAMES)
    validation_actions: list[str] = []
    names: list[str] = list(
        MODEL_AUTHORED_DEFAULT_ORIGINAL_CALLS_BY_TOOL.get(
            request.suggested_tool_name or "", ()
        )
    )
    evidence = request.inadequacy_evidence or {}
    for key in ("failed_tool_calls", "repeated_failed_tool_calls"):
        value = evidence.get(key, ())
        if isinstance(value, str):
            names.append(value)
        elif isinstance(value, (list, tuple, set)):
            names.extend(str(item) for item in value)
    for item in request.validation_examples:
        expected = item.get("expected") if isinstance(item, dict) else None
        if not isinstance(expected, dict):
            continue
        for key in ("downstream_tool_name", "tool_name"):
            name = str(expected.get(key) or "")
            if name:
                names.append(name)
                if name in allowed:
                    validation_actions.append(name)
        for name in allowed:
            if isinstance(expected.get(f"{name}_kwargs"), dict):
                names.append(name)
                validation_actions.append(name)
    approved = validation_actions or names
    return tuple(dict.fromkeys(name for name in approved if name in allowed))


def _request_complete_tools_enabled(request: ToolGenerationRequest) -> bool:
    """Use native execution only for compact, well-covered action contracts.

    The decision uses the public validation contract rather than a task, family,
    or benchmark identifier.  Complex transformations remain ordinary generated
    tools that prepare inputs for the actor's native call.
    """

    eligible_families = {
        str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),
        str(ToolFamily.SEARCH_FILTER_RANKING_HELPER),
    }
    if not eligible_families.intersection(request.allowed_families):
        return False
    positive_count = 0
    held_out_positive_count = 0
    negative_count = 0
    input_names: set[str] = set()
    native_actions: set[str] = set()
    max_action_argument_count = 0
    for item in request.validation_examples:
        if not isinstance(item, dict):
            continue
        inputs = item.get("inputs")
        if isinstance(inputs, dict):
            input_names.update(str(name) for name in inputs)
        expected = item.get("expected")
        if not isinstance(expected, dict):
            continue
        sequence = expected.get("action_sequence")
        if isinstance(sequence, list) and len(sequence) > 1:
            return False
        if any(
            isinstance(value, list) and value
            for key, value in expected.items()
            if str(key).endswith(("_kwargs_list", "_actions"))
        ):
            return False
        should_values = [
            bool(value)
            for key, value in expected.items()
            if str(key) == "should_call" or str(key).startswith("should_call_")
        ]
        if item.get("negative_applicability") or (
            should_values and not any(should_values)
        ):
            negative_count += 1
            continue
        action_name = str(expected.get("downstream_tool_name") or "")
        action_arguments = expected.get("downstream_tool_kwargs")
        if action_name not in COMPLETE_TOOLS_NATIVE_NAMES:
            action_name = str(expected.get("tool_name") or "")
            action_arguments = next(
                (
                    expected.get(key)
                    for key in ("tool_kwargs", "arguments", "kwargs")
                    if isinstance(expected.get(key), dict)
                ),
                None,
            )
        if action_name not in COMPLETE_TOOLS_NATIVE_NAMES:
            for candidate in COMPLETE_TOOLS_NATIVE_NAMES:
                candidate_arguments = expected.get(f"{candidate}_kwargs")
                if isinstance(candidate_arguments, dict):
                    action_name = candidate
                    action_arguments = candidate_arguments
                    break
        if action_name not in COMPLETE_TOOLS_NATIVE_NAMES:
            continue
        # Direct execution is eligible only when the public contract already
        # supplies concrete action arguments. A contract that still requires
        # an upstream lookup remains an ordinary generated planning tool.
        if not isinstance(action_arguments, dict) or not action_arguments:
            return False
        positive_count += 1
        held_out_positive_count += int(bool(item.get("held_out")))
        native_actions.add(action_name)
        if isinstance(action_arguments, dict):
            max_action_argument_count = max(
                max_action_argument_count, len(action_arguments)
            )

    compact_contract = len(input_names) <= 6
    densely_validated_single_action = bool(
        len(native_actions) == 1
        and len(input_names) <= 16
        and positive_count >= 4
        and held_out_positive_count >= 2
        and negative_count >= 2
    )

    # These are contract-complexity bounds, not dataset rules. Broad contracts
    # are eligible only when one native action is covered by a dense public test
    # matrix; multi-action contracts must remain compact.
    return bool(
        positive_count
        and positive_count <= 8
        and held_out_positive_count
        and negative_count
        and (compact_contract or densely_validated_single_action)
        and len(native_actions) <= 4
        and max_action_argument_count <= 4
        and set(_request_native_action_names(request)) == native_actions
    )


def _native_action_behavior_summary(request: ToolGenerationRequest) -> str:
    """Keep detected behavior while removing obsolete planner-only constraints."""

    kept: list[str] = []
    for raw_sentence in re.split(r"(?<=[.!?])\s+", request.observation.strip()):
        sentence = raw_sentence.strip()
        lowered = sentence.lower()
        if not sentence:
            continue
        if lowered.startswith("return") and any(
            marker in lowered
            for marker in (
                "should_call",
                "_kwargs",
                "downstream_tool",
                "action_sequence",
            )
        ):
            continue
        if any(
            marker in lowered
            for marker in (
                "prepare arguments only",
                "preparing arguments only",
                "only prepares",
                "only selects the target",
                "must preserve the original",
            )
        ):
            continue
        if "required_original_tool_calls" in lowered or (
            "preserves_side_effect_tools" in lowered
        ):
            continue
        if "must never call" in lowered or "only prepares" in lowered:
            continue
        if lowered.startswith("when ") and "downstream_tool_" in lowered:
            continue
        sentence = re.sub(
            r"side-effect-free helper",
            "native-action tool",
            sentence,
            flags=re.IGNORECASE,
        )
        sentence = re.split(
            r",?\s+and return a final-action-ready\b",
            sentence,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].rstrip(" ,")
        if sentence and sentence[-1] not in ".!?":
            sentence += "."
        kept.append(sentence)
    return " ".join(kept)


def _native_action_api_guidance(native_names: tuple[str, ...]) -> str:
    """Describe the final native call without retaining planner-only semantics."""

    if not native_names:
        return ""
    guidance = (
        "The expected_native_action object is the sole positive-case execution "
        "contract. Ignore any legacy planning implication in the generated function "
        "name: this native-action variant must execute the declared native function, "
        "not return should_call flags or prepared kwargs. "
    )
    if native_names == ("add_reminder",):
        guidance += (
            "For every positive case, literally call add_reminder once with the "
            "keyword arguments content, reminder_timestamp, latitude, and longitude "
            "shown by expected_native_action. Derive those values from the declared "
            "inputs and argument_value_locations; never invent content, coordinates, "
            "or a timestamp. Missing content or time and unresolved required location "
            "must abstain before the call. For optional location, distinguish pending "
            "from failed lookup: requested=true, available=false, and lookup_failed=false "
            "must abstain, while lookup_failed=true with location_required=false may "
            "call add_reminder with latitude=None and longitude=None. Apply this "
            "decision table before the native call: no location requested calls with "
            "None coordinates; available location calls with the visible coordinates; "
            "optional requested location with lookup_failed=true calls with None "
            "coordinates; optional requested location with lookup_failed=false "
            "abstains because lookup is pending; required unavailable location always "
            "abstains. Do not merge the pending and failed branches. "
        )
    if set(native_names) == {"modify_reminder", "remove_reminder"}:
        guidance += (
            "The visible selection_mode controls the ranked target: latest selects "
            "the unique maximum numeric timestamp and oldest selects the unique "
            "minimum numeric timestamp. Do not default both modes to max. Collect all "
            "records tied at the selected extreme and abstain unless exactly one "
            "winner remains before executing the native action. "
        )
    device_setters = tuple(
        name
        for name in native_names
        if name.startswith("set_") and name.endswith("_status")
    )
    if device_setters and len(device_setters) == len(native_names):
        setter_mapping = ", ".join(
            (
                name.removeprefix("set_")
                .removesuffix("_status")
                .removesuffix("_service")
                + " to "
                + name
            )
            for name in device_setters
        )
        guidance += (
            "This contract performs one explicit device-state action only. Map "
            f"the schema-derived targets as follows: {setter_mapping}. "
            "Pass desired_on unchanged as the native "
            "on argument and call exactly one setter. Unknown or blank targets must "
            "abstain without calling any setter; do not add prerequisite or recovery "
            "actions. "
        )
    return guidance


def _native_action_validation_examples(
    request: ToolGenerationRequest,
) -> list[dict[str, object]]:
    """Project preparatory contracts into the native action calls they require."""

    allowed = set(COMPLETE_TOOLS_NATIVE_NAMES)
    projected: list[dict[str, object]] = []
    source_index = 0
    held_out_index = 0
    negative_index = 0
    for item in request.validation_examples:
        if not isinstance(item, dict):
            continue
        expected = item.get("expected")
        if not isinstance(expected, dict):
            continue
        should_values = [
            bool(value)
            for key, value in expected.items()
            if str(key) == "should_call" or str(key).startswith("should_call_")
        ]
        negative = bool(item.get("negative_applicability")) or (
            bool(should_values) and not any(should_values)
        )
        if negative:
            case_label = f"negative_{negative_index}"
            negative_index += 1
        elif item.get("held_out"):
            case_label = f"held_out_{held_out_index}"
            held_out_index += 1
        else:
            case_label = f"source_{source_index}"
            source_index += 1
        native_name = ""
        native_arguments: dict[str, object] = {}
        if not negative:
            downstream_name = str(expected.get("downstream_tool_name") or "")
            if downstream_name in allowed and isinstance(
                expected.get("downstream_tool_kwargs"), dict
            ):
                native_name = downstream_name
                native_arguments = dict(expected["downstream_tool_kwargs"])
            direct_name = str(expected.get("tool_name") or "")
            if not native_name and direct_name in allowed:
                for key in ("tool_kwargs", "arguments", "kwargs"):
                    if isinstance(expected.get(key), dict):
                        native_name = direct_name
                        native_arguments = dict(expected[key])
                        break
            if not native_name:
                for candidate in COMPLETE_TOOLS_NATIVE_NAMES:
                    kwargs = expected.get(f"{candidate}_kwargs")
                    if isinstance(kwargs, dict):
                        native_name = candidate
                        native_arguments = dict(kwargs)
                        break
            sequence = expected.get("action_sequence")
            if not native_name and isinstance(sequence, list) and len(sequence) == 1:
                action = sequence[0]
                if isinstance(action, dict):
                    candidate = str(action.get("tool_name") or action.get("name") or "")
                    arguments = action.get("arguments") or action.get("kwargs")
                    if candidate in allowed and isinstance(arguments, dict):
                        native_name = candidate
                        native_arguments = dict(arguments)
        projected.append(
            {
                "case_label": case_label,
                "inputs": item.get("inputs"),
                "expected_native_action": (
                    {
                        "name": native_name,
                        "arguments": native_arguments,
                        "argument_value_locations": {
                            key: _visible_value_locations(item.get("inputs"), value)
                            for key, value in native_arguments.items()
                        },
                    }
                    if native_name
                    else None
                ),
                "negative_applicability": negative,
                "held_out": bool(item.get("held_out", False)),
            }
        )
    alias_index = 0
    seen_aliases: set[str] = set()
    aliases_by_mode = {
        "latest": ("last", "latest_by_time", "most_recent"),
        "oldest": ("first", "oldest_by_time", "earliest"),
    }
    for item in list(projected):
        if not item.get("expected_native_action"):
            continue
        inputs = item.get("inputs")
        if not isinstance(inputs, dict):
            continue
        mode = str(inputs.get("selection_mode") or "").strip().lower()
        for alias in aliases_by_mode.get(mode, ()):
            if alias in seen_aliases:
                continue
            seen_aliases.add(alias)
            alias_inputs = dict(inputs)
            alias_inputs["selection_mode"] = alias
            projected.append(
                {
                    **item,
                    "case_label": f"held_out_alias_{alias_index}",
                    "inputs": alias_inputs,
                    "held_out": True,
                }
            )
            alias_index += 1

    action_alias_index = 0
    seen_action_aliases: set[tuple[str, str]] = set()
    for item in list(projected):
        expected_action = item.get("expected_native_action")
        inputs = item.get("inputs")
        if not isinstance(expected_action, dict) or not isinstance(inputs, dict):
            continue
        canonical_action = str(expected_action.get("name") or "").strip()
        visible_action = str(inputs.get("action_type") or "").strip()
        verb = canonical_action.split("_", 1)[0]
        if (
            visible_action != canonical_action
            or verb not in {"add", "modify", "remove", "send"}
            or (canonical_action, verb) in seen_action_aliases
        ):
            continue
        seen_action_aliases.add((canonical_action, verb))
        alias_inputs = dict(inputs)
        alias_inputs["action_type"] = verb
        projected.append(
            {
                **item,
                "case_label": f"held_out_action_alias_{action_alias_index}",
                "inputs": alias_inputs,
                "held_out": True,
            }
        )
        action_alias_index += 1

    target_override_index = 0
    for item in list(projected):
        expected_action = item.get("expected_native_action")
        inputs = item.get("inputs")
        if not isinstance(expected_action, dict) or not isinstance(inputs, dict):
            continue
        arguments = expected_action.get("arguments")
        updates = inputs.get("updates")
        records = inputs.get("records")
        if not (
            isinstance(arguments, dict)
            and isinstance(updates, dict)
            and bool(updates)
            and isinstance(records, list)
        ):
            continue
        for identifier_key, selected_identifier in arguments.items():
            if not str(identifier_key).endswith("_id"):
                continue
            conflicting_identifier = next(
                (
                    record.get(identifier_key)
                    for record in records
                    if isinstance(record, dict)
                    and record.get(identifier_key) not in {None, selected_identifier}
                ),
                None,
            )
            if conflicting_identifier is None:
                continue
            override_inputs = dict(inputs)
            override_inputs["updates"] = {
                **updates,
                identifier_key: conflicting_identifier,
            }
            projected.append(
                {
                    **item,
                    "case_label": f"held_out_target_override_{target_override_index}",
                    "inputs": override_inputs,
                    "held_out": True,
                }
            )
            target_override_index += 1
            break

    structural_negative_inputs: list[tuple[str, dict[str, object]]] = []
    for item in projected:
        if not item.get("expected_native_action"):
            continue
        inputs = item.get("inputs")
        if not isinstance(inputs, dict):
            continue
        records = inputs.get("records")
        if (
            not isinstance(records, list)
            or not records
            or not all(isinstance(record, dict) for record in records)
        ):
            continue
        timestamp_key = str(inputs.get("timestamp_key") or "").strip()
        if not timestamp_key:
            common_keys = set(records[0])
            for record in records[1:]:
                common_keys.intersection_update(record)
            timestamp_key = next(
                (
                    key
                    for key in sorted(common_keys)
                    if key.endswith("_timestamp")
                    and all(
                        isinstance(record.get(key), (int, float)) for record in records
                    )
                ),
                "",
            )
        if not timestamp_key or not any(timestamp_key in record for record in records):
            continue

        malformed_records = [dict(record) for record in records]
        malformed_records[0].pop(timestamp_key, None)
        malformed_inputs = dict(inputs)
        malformed_inputs["records"] = malformed_records
        structural_negative_inputs.append(("missing_rank_field", malformed_inputs))

        numeric_records = [
            record
            for record in records
            if isinstance(record.get(timestamp_key), (int, float))
        ]
        if numeric_records:
            mode = str(inputs.get("selection_mode") or "latest").lower()
            selected = (
                min(numeric_records, key=lambda record: record[timestamp_key])
                if mode in {"oldest", "first", "oldest_by_time", "earliest"}
                else max(numeric_records, key=lambda record: record[timestamp_key])
            )
            tied_inputs = dict(inputs)
            tied_inputs["records"] = [
                *[dict(record) for record in records],
                dict(selected),
            ]
            structural_negative_inputs.append(("tied_rank", tied_inputs))
        break

    for index, (reason, inputs) in enumerate(structural_negative_inputs):
        projected.append(
            {
                "case_label": f"negative_structural_{index}_{reason}",
                "inputs": inputs,
                "expected_native_action": None,
                "negative_applicability": True,
                "held_out": False,
            }
        )
    return projected


def _native_action_validator_labeled_examples(
    request: ToolGenerationRequest,
) -> list[dict[str, object]]:
    """Attach the case labels emitted by the executable validator."""

    indexes = {"source": 0, "held_out": 0, "negative": 0}
    labeled: list[dict[str, object]] = []
    for item in _native_action_validation_examples(request):
        if item.get("negative_applicability"):
            category = "negative"
        elif item.get("held_out"):
            category = "held_out"
        else:
            category = "source"
        validator_label = f"{category}_{indexes[category]}"
        indexes[category] += 1
        labeled.append({**item, "validator_case_label": validator_label})
    return labeled


def _visible_value_locations(
    inputs: object,
    expected_value: object,
) -> list[str]:
    """Locate expected scalar action values in public validation inputs."""

    if isinstance(expected_value, (dict, list, tuple, set)):
        return []
    locations: list[str] = []

    def visit(value: object, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, f"{path}.{key}" if path else str(key))
            return
        if isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")
            return
        if value == expected_value:
            locations.append(path)

    visit(inputs, "inputs")
    return locations[:8]


def _native_action_coverage_guidance(
    examples: list[dict[str, object]],
) -> str:
    positive = [item for item in examples if item.get("expected_native_action")]
    held_out = [item for item in positive if item.get("held_out")]
    negative = [item for item in examples if item.get("negative_applicability")]
    labels = [str(item.get("case_label") or "") for item in positive]
    action_names = {
        str(expected.get("name") or "")
        for item in positive
        for expected in [item.get("expected_native_action")]
        if isinstance(expected, dict)
    }
    role_mapping_guidance = (
        "When the selected record has multiple role identifiers with a shared "
        "semantic suffix, such as paired participant or person identifiers, and "
        "a visible self identifier is supplied, collect the selected record's "
        "candidate identifiers, remove blank values and the self value, and require "
        "one unique remaining action target. Do not bind the target to one fixed "
        "role field. Never abstain merely because one sender, recipient, participant, "
        "or other role identifier equals the self identifier when another role "
        "identifier is visible. Any guard that tests one role equals self before "
        "collecting all role candidates is invalid. Filter all candidates first; "
        "abstain only if the filtered set does not contain exactly one identifier. "
        "Do not call next() directly on a tuple or list of role values. Build the "
        "filtered candidate list explicitly, deduplicate it, require length one, "
        "and only then index candidates[0]. "
        if action_names & {"modify_contact", "remove_contact"}
        else ""
    )
    return (
        "Contract coverage is mandatory: implement all "
        f"{len(positive)} positive cases ({', '.join(labels)}), including "
        f"{len(held_out)} held-out cases, while making zero native calls for "
        f"all {len(negative)} negative cases. Do not optimize only for source_0. "
        "Compare the positive inputs and expected action arguments, then implement "
        "the reusable branches needed to cover every variation. Each positive "
        "action includes argument_value_locations showing where its expected scalar "
        "arguments occur in that case's visible inputs. Use those locations to infer "
        "a reusable value-mapping rule; never hard-code the example values themselves. "
        "The locations are descriptive paths rooted at the function inputs, not Python "
        "expressions: never reference a variable named inputs unless it is a declared "
        "function parameter. Translate each path to the declared parameter and ordinary "
        "dictionary/list access. "
        + role_mapping_guidance
        + "When native action arguments come from an input mapping, copy "
        "every non-None mapping entry into the native call rather than using "
        "mutually exclusive branches for individual update keys. Treat a mapping "
        "with any non-None entry as actionable; do not require one particular key "
        "before accepting it. Build one action-argument dictionary from the stable "
        "target identifier plus all non-None writable mapping entries, then make "
        "exactly one "
        "native call with that dictionary. Build the success confirmation from the "
        "same visible update mapping: every nonempty changed value must appear in "
        "the confirmation. A generic confirmation such as 'updated successfully' "
        "is invalid because the actor must be able to report what changed without "
        "reconstructing hidden state. Describe a selected target with visible "
        "selection context such as latest or oldest, and never expose an opaque "
        "record identifier in actor-facing confirmation text. Normalize any "
        "selection aliases demonstrated by the public held-out examples before "
        "choosing the record. A target identifier is not an update field. Ignore "
        "mapping keys whose names end in _id when constructing updates, and bind "
        "the native target identifier only from the uniquely selected record or "
        "the explicit identity input demonstrated by the public contract. Never "
        "allow an updates mapping to replace that selected identity. "
        "Every positive case is valid by contract. Trace each positive input through "
        "every guard and return before writing code. Do not add an early abstention "
        "condition that fires for a positive example merely because one visible role "
        "or identifier denotes the agent or self; use the other visible roles and "
        "argument_value_locations to infer the expected reusable mapping. Derive "
        "abstention conditions from negative examples, not from assumptions that "
        "contradict a positive example. "
        "Preserve a branch once it satisfies a positive case when adding another branch. "
    )


def _model_authored_contract_analysis_prompt(
    request: ToolGenerationRequest,
) -> str:
    examples = _native_action_validation_examples(request)
    native_actions = _request_native_action_names(request)
    role_analysis = (
        "paired roles where one visible identifier denotes the agent or self, "
        if set(native_actions) & {"modify_contact", "remove_contact"}
        else ""
    )
    return (
        "Analyze this public native-action tool contract before code is written. "
        "Compare every source, held-out, and negative example. Infer a reusable "
        "algorithm that maps declared inputs to exactly one approved native action "
        "for every positive case and no action for every negative case. Pay special "
        "attention to action arguments whose value location changes across cases, "
        + role_analysis
        + "mapping "
        "inputs whose concrete keys vary across cases, and ordering or selection modes. "
        "Return a JSON object with keys algorithm_steps, positive_case_coverage, "
        "argument_binding_rules, abstain_conditions, and invariants. Paths in "
        "argument_value_locations are descriptive evidence only. Do not output Python, "
        "do not hard-code example values, and do not refer to hidden labels, scenario "
        "IDs, or benchmark answers. Required tool name: "
        + str(request.suggested_tool_name or "infer_from_contract")
        + ". Approved native actions: "
        + json.dumps(list(native_actions), sort_keys=True)
        + ". Validation examples: "
        + json.dumps(examples, sort_keys=True)
    )


def _model_authored_repair_analysis_prompt(
    request: ToolGenerationRequest,
    rejected_tool: GeneratedTool,
    errors: tuple[str, ...],
) -> str:
    """Ask the generator to trace current code through only the failing public cases."""

    failed_case_labels = {
        match.group(1)
        for error in errors
        if (match := re.match(r"^((?:source|held_out|negative)_\d+)_", error))
    }
    all_cases = _native_action_validation_examples(request)
    failing_cases = [
        item
        for item in all_cases
        if str(item.get("case_label") or "") in failed_case_labels
    ]
    return (
        "Trace this rejected model-authored native-action tool against each failing "
        "public validation case. Substitute the complete input values into the "
        "current Python control flow in execution order. Identify the first guard, "
        "condition, return, or argument binding that causes each validator error. "
        "For boolean expressions, report the evaluated truth value and the input "
        "values responsible for it. Compare the failing case with the nearest passing "
        "positive and negative cases so the next repair fixes the failure without "
        "reintroducing a previously cleared branch. Return JSON with keys "
        "failing_case_traces, first_blocking_condition, minimal_semantic_change, "
        "and regression_guards. Do not output Python or a replacement function. "
        "Do not use hidden labels, scenario identifiers, or benchmark answers. "
        "Approved native actions: "
        + json.dumps(list(_request_native_action_names(request)), sort_keys=True)
        + ". Validator errors: "
        + json.dumps(list(errors), sort_keys=True)
        + ". Failing public cases: "
        + json.dumps(failing_cases, sort_keys=True)
        + ". All public case classifications for regression comparison: "
        + json.dumps(all_cases, sort_keys=True)
        + ". Current generated code: "
        + rejected_tool.code
    )


def _model_authored_final_repair_directive(
    request: ToolGenerationRequest,
    errors: tuple[str, ...],
) -> str:
    """Restate structural invariants after verbose model-authored analysis."""

    if not _request_complete_tools_enabled(request):
        return ""
    cases = _native_action_validator_labeled_examples(request)
    ranked_record_contract = any(
        isinstance(item.get("inputs"), dict)
        and "records" in item["inputs"]
        and "selection_mode" in item["inputs"]
        for item in cases
    )
    ranked_failure = any(
        marker in error
        for error in errors
        for marker in (
            "native_action_execution_error",
            "unexpected_native_action",
            "native_action_abstain",
            "native_action_count",
            "native_action_arguments",
        )
    )
    if not ranked_record_contract or not ranked_failure:
        return ""

    paired_role_contract = any(
        isinstance(inputs := item.get("inputs"), dict)
        and bool(inputs.get("self_person_id"))
        and isinstance(records := inputs.get("records"), list)
        and any(
            isinstance(record, dict)
            and len([key for key in record if str(key).endswith("_person_id")]) >= 2
            for record in records
        )
        for item in cases
    )
    paired_role_step = (
        "6. If the visible self_person_id is blank, abstain before role processing. "
        "Otherwise, from only the selected record, collect every nonblank role "
        "identifier whose field ends in _person_id and build a new filtered list of "
        "values unequal to self_person_id. Never mutate the list with remove(), because "
        "the value may be absent; use a non-mutating filter, deduplicate the result, "
        "and abstain unless exactly one target remains. Never assume a fixed sender or "
        "recipient direction. "
        if paired_role_contract
        else ""
    )
    return (
        " FINAL BINDING REPAIR CHECKLIST. This checklist is authoritative after the "
        "analysis above. Implement every step literally in each returned candidate: "
        "1. Normalize every selection-mode alias demonstrated by a positive or held-out "
        "case into the contract's latest or oldest meaning. "
        "2. Inspect the original records collection without filtering or dropping any "
        "item. Before ranking, abstain if it is empty, any item is not a mapping, any "
        "item lacks the demonstrated ranking field, or any ranking value is not of the "
        "demonstrated comparable type. "
        "3. Compute the requested minimum or maximum ranking value from the unchanged "
        "collection. Build winners from every original record equal to that extreme. "
        "4. Abstain unless len(winners) is exactly one; duplicate or distinct tied "
        "records are both ambiguous. Never resolve a tie by input order or sorting. "
        "5. Only after those checks, bind selected_record = winners[0]. "
        + paired_role_step
        + "7. Copy every concrete writable value from any demonstrated update mapping, "
        "excluding target-identifier keys; abstain if no concrete update remains. "
        "8. Call the approved native action exactly once only after all prerequisites "
        "pass, then return the complete success object. Every failed prerequisite must "
        "return the complete abstain object and make zero native calls. "
        "9. Mentally execute every public positive, held-out, alias, malformed-record, "
        "and tied-rank case before emitting code. Do not return an explanation; return "
        "only the requested complete JSON repair candidate or candidate array. Every "
        "public positive and held-out case must reach exactly one native call; do not "
        "add an abstention condition that rejects a demonstrated valid case."
    )


MODEL_AUTHORED_OUTPUT_TOOL_NAME_ENUM_BY_TOOL: dict[str, tuple[str, ...]] = {
    "plan_device_state_action_sequence_v3": (
        "",
        "set_wifi_status",
        "set_cellular_service_status",
        "set_location_service_status",
        "set_low_battery_mode_status",
    ),
    "plan_device_state_action_sequence_location_recovery": (
        "",
        "set_location_service_status",
        "set_low_battery_mode_status",
        "set_wifi_status",
    ),
    "plan_device_status_lookup": (
        "",
        "get_wifi_status",
        "get_cellular_service_status",
        "get_location_service_status",
        "get_low_battery_mode_status",
    ),
}


def _model_authored_generation_prompt(
    request: ToolGenerationRequest,
    *,
    candidate_count_override: int | None = None,
) -> str:
    expected_tool_name = request.suggested_tool_name or "infer_from_contract"
    _complete_tools = _request_complete_tools_enabled(request)
    # In complete-tools mode the helper "prepare kwargs / should_call" contracts
    # and helper-shaped validation examples would override the complete-tools
    # instruction, so neutralize them and let the state-change validator judge.
    contract_rules = () if _complete_tools else _model_authored_contract_rules(request)
    candidate_count = (
        max(1, int(candidate_count_override))
        if candidate_count_override is not None
        else _model_authored_candidate_count()
    )
    examples = (
        _native_action_validation_examples(request)
        if _complete_tools
        else [
            {
                "inputs": item.get("inputs"),
                "expected": item.get("expected"),
                "negative_applicability": item.get("negative_applicability", False),
            }
            for item in request.validation_examples
            if isinstance(item, dict)
        ]
    )
    inadequacy_payload: dict[str, object]
    prompt_observation = request.observation
    if _complete_tools:
        native_names = _request_native_action_names(request)
        prompt_observation = (
            _native_action_behavior_summary(request)
            + " The generated tool must map its visible inputs to exactly one "
            "validated native action or safely abstain. The native implementation "
            "remains responsible for the state change and trace. Approved actions "
            "for this contract: " + ", ".join(native_names) + "."
        )
        raw_evidence = request.inadequacy_evidence or {}
        inadequacy_payload = {
            "summary": _compact_text(prompt_observation, 1800),
            "signals": raw_evidence.get("signals", ()),
            "failed_tool_calls": native_names,
        }
    elif contract_rules:
        raw_evidence = request.inadequacy_evidence or {}
        inadequacy_payload = {
            "summary": _compact_text(
                str(raw_evidence.get("summary") or request.observation), 800
            ),
            "signals": raw_evidence.get("signals", ()),
        }
    else:
        inadequacy_payload = request.inadequacy_evidence or {}
    payload = {
        "required_tool_name": expected_tool_name,
        "candidate_count": candidate_count,
        "task_context": _compact_text(request.scenario_name, 500)
        if contract_rules
        else request.scenario_name,
        "observation": _compact_text(prompt_observation, 800)
        if contract_rules
        else prompt_observation,
        "allowed_families": list(request.allowed_families),
        "contract_rules": contract_rules,
        "inadequacy_evidence": inadequacy_payload,
        "failure_memory_context": request.failure_memory_context or {},
        "shortfall_cluster_context": request.shortfall_cluster_context or {},
        "validation_contract": (
            "native_action_delegation" if _complete_tools else "exact_return_value"
        ),
        "validation_examples": examples,
    }
    coverage_guidance = (
        _native_action_coverage_guidance(examples) if _complete_tools else ""
    )
    native_action_algorithm_guidance = (
        "Before any native action call, implement the negative public examples "
        "as explicit abstention branches. When records are ranked by a field, infer "
        "that field from the positive public examples and validate every candidate "
        "before sorting or calling min/max. If a candidate is not a mapping, lacks "
        "the ranking field, or has a nonnumeric ranking value when the examples use "
        "numeric ranking, call no native action and abstain. Only after that guard, "
        "compute the winning value and collect every record at that value. If more "
        "than one record shares the winning value, call no native action and abstain. "
        "Call native functions with keyword arguments whose names exactly match "
        "the binding expected_native_action arguments; never bind update values "
        "positionally or substitute one update field for another. "
        if _complete_tools
        else ""
    )
    native_action_api_guidance = (
        _native_action_api_guidance(_request_native_action_names(request))
        if _complete_tools
        else ""
    )
    validation_guidance = (
        "For native_action_delegation validation, each positive example contains "
        "expected_native_action with the exact approved native function name and "
        "arguments. Call that native function exactly once, then return status "
        "success, the native action name, the native result, an empty abstain_reason, "
        "and a concise nonempty confirmation. If the declared inputs include an "
        "updates mapping, every visible nonempty update value must appear in that "
        "confirmation; generic success text is not sufficient. Confirmation text "
        "must not expose native identifier arguments whose keys end in _id. If "
        "selection_mode is a declared input, preserve its visible value in the "
        "confirmation. When "
        "expected_native_action is null, "
        "call no native function and return status abstain, an empty native action "
        "and confirmation, and a nonempty abstain_reason. Never return an empty "
        "object. Classify examples by expected_native_action, not by whether an "
        "input name sounds adverse: a positive example remains positive even when "
        "an input includes words such as failed, missing, unavailable, or ambiguous. "
        "Do not create a single-input abstention guard when that same input value "
        "appears in a positive example; use the complete demonstrated combination. "
        "Do not reproduce "
        "the former should_call/kwargs planning object; the native call itself is the "
        "contract. " + coverage_guidance
        if _complete_tools
        else "The function must return the expected object exactly for every "
        "validation example, including every field, boolean, empty string, empty "
        "dict/list, None/null, and actor-facing text. If expected text follows a "
        "pattern, infer the reusable template and fill it from input or record fields. "
    )
    return (
        "Synthesize one reusable deterministic Python tool from this public "
        "tool contract. Return valid JSON only. If candidate_count is 1, return "
        "top-level keys spec and code_lines. If candidate_count is greater than "
        "1, return a top-level candidates array with exactly candidate_count "
        "independent objects, each containing spec and code_lines. The code must "
        "be authored now as a list of Python source "
        "lines, not copied from a template. The function name must equal "
        "required_tool_name unless that value is infer_from_contract; if it is "
        "infer_from_contract, choose a valid snake_case Python function name. "
        "Use the validation examples as executable contract tests. Generalize "
        "from the examples and task evidence; do not hard-code by entire input "
        "object, hidden task id, benchmark scenario id, or answer string. The "
        "candidates must use meaningfully different branch structure when "
        "possible so deterministic validation can select the safest one. "
        + validation_guidance
        + "The contract_rules list in the payload is binding and has priority over "
        "generic helper design. "
        "Every code_lines item must be one complete Python source line. Do not "
        "split a string literal across lines. Prefer double-quoted Python strings "
        "when the text may contain apostrophes. Define exactly one top-level "
        "function and no other top-level def; use inline loops and branches "
        "rather than helper functions when the contract is simple. "
        "The spec object should be minimal: tool_name, family, description, "
        "inputs, output_annotation, and output_schema. Do not spend tokens on "
        "registry metadata; SAGE will fill lifecycle metadata from the same "
        "public birth evidence after validation. The tool_name must equal "
        "required_tool_name unless required_tool_name is infer_from_contract. "
        "The family must be one of allowed_families. Each input must be an object "
        "with name, annotation, and description. output_annotation must be one of "
        "str, int, float, bool, dict, or list. "
        + (
            COMPLETE_TOOLS_PROMPT_CONSTRAINT + " "
            if _complete_tools
            else "The function must be pure and side-effect free: no imports, try/except, "
            "raise statements, classes, lambdas, while loops, file/network/subprocess access, "
            "global state, mutation of inputs, or calls to ToolSandbox side-effect "
            "tools. Return safe fallback values instead of raising. "
        )
        + "Treat optional "
        "dict or list inputs as empty dict/list when they are None or the wrong "
        "type before calling .get, indexing, or iterating. "
        + native_action_algorithm_guidance
        + native_action_api_guidance
        + ("" if _complete_tools else _model_authored_tool_specific_guidance(request))
        + "Required JSON payload: "
        + json.dumps(payload, sort_keys=True)
    )


def _compact_text(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _model_authored_contract_rules(request: ToolGenerationRequest) -> tuple[str, ...]:
    if request.suggested_tool_name == "prepare_add_contact_args":
        return (
            "Use the typed name, phone_number, and relationship inputs; user_request is intent context only. Do not parse missing scalar values out of free-form prose and do not call or define auxiliary parsing or validation functions.",
            "Normalize phone_number inline by trimming outer whitespace and removing spaces, parentheses, periods, and dashes while preserving a leading plus sign.",
            "Check missing name or phone_number only after trimming the typed scalars. If either is blank, return the required abstention object and call no native action.",
            "For a positive case, build keyword arguments with name and normalized phone_number, include relationship only when nonblank, literally call add_contact once with those keyword arguments, assign its return value to native_result, and then return the required success object.",
            "Write confirmation as a clear subject-first completed-state sentence that names the visible contact and says the contact has been added; include the visible normalized phone number. Do not use an imperative, a vague generic success message, or an opaque identifier.",
            "Never return prepared arguments as native_result and never report success without executing add_contact.",
        )
    if request.suggested_tool_name == "plan_contact_update_from_id":
        return (
            "Use only the typed person_id, phone_number, name, and relationship inputs. Do not call or define auxiliary parsing or validation functions.",
            "Normalize a nonblank phone_number inline by trimming it and removing spaces, parentheses, periods, and dashes while preserving a leading plus sign.",
            "Build keyword arguments starting with person_id, then add only nonblank update fields. Never pass blank optional values to modify_contact.",
            "If person_id is blank or every update field is blank, return the required abstention object and call no native action.",
            "For a positive case, literally call modify_contact once with the filtered keyword arguments, assign its return value to native_result, and then return the required success object.",
        )
    if request.suggested_tool_name == "plan_contact_lookup_query":
        return (
            "Build search_contacts_kwargs from contact_name, phone_number, and relationship before branching on selected_record; return those kwargs in both pre-search and selected-record outputs.",
            "If selected_record is a non-empty dict and requested_field is present, should_call_search_contacts is false, abstain_reason is empty, selected_record is copied exactly, answer_field equals requested_field, and answer_value is selected_record[requested_field].",
            "Use an early return for selected_record cases so should_call_search_contacts cannot remain true from pre-search kwargs.",
            "For selected_record relationship answers with a nonblank phone_number lookup, final_answer_recommendation equals phone_number + ' is your ' + answer_value.",
            "This relationship-answer rule applies even when contact_name is blank: if requested_field == 'relationship', phone_number is nonblank, and selected_record has relationship, final_answer_recommendation must be the phone number plus ' is your ' plus selected_record['relationship'].",
            'For selected_record phone_number answers with a nonblank contact_name lookup, final_answer_recommendation equals contact_name + "\'s phone number is " + answer_value.',
            "For selected_record name answers with a nonblank relationship lookup, final_answer_recommendation equals 'Your ' + relationship + ' is ' + answer_value.",
            "For selected_record person_id answers, answer_value is the person_id and final_answer_recommendation is empty.",
            "In every output where requested_field is nonblank, answer_field must equal requested_field; do not leave answer_field empty during pre-search planning.",
            "If selected_record is empty and at least one lookup kwarg exists, should_call_search_contacts is true, selected_record is {}, answer_field equals requested_field, answer_value and final_answer_recommendation are empty, copy_exactly is false, and abstain_reason is empty.",
            "If selected_record is empty and no lookup kwarg exists, should_call_search_contacts is false and abstain_reason is missing_lookup_constraint.",
        )
    if request.suggested_tool_name == "prepare_safe_action_or_abstain":
        return (
            "Return exactly these output keys on every branch: should_abstain, missing_information, required_original_tools, safe_next_action, final_answer_recommendation, and abstain_reason.",
            "Normalize required_original_tools and available_original_tools from concrete ToolSandbox names to semantic capabilities: search_contacts becomes contact_lookup and send_message_with_phone_number becomes message_send.",
            "For requested_action message_send, send_message, or any send/text/message action, a target_identifier that is not a phone number is a named recipient and requires contact_lookup before message_send.",
            "If a named-recipient message send lacks contact_lookup in available_original_tools, return should_abstain true, include contact_lookup in missing_information, set safe_next_action ask_user_or_abstain, and recommend that the message cannot be sent safely because the recipient cannot be resolved to a phone number.",
            "Never treat message_send alone as sufficient for a named recipient. message_send alone is sufficient only when target_identifier already looks like a concrete phone number.",
            "If required_original_tools or available_original_tools is a string, treat it as one capability value, not as an iterable of characters.",
            "If required_original_tools is omitted, malformed, or incomplete, infer required semantic capabilities from requested_action, user_request, and target_identifier before computing missing_information.",
            "The function must never return should_abstain false when the action would require guessing a phone number, person_id, reminder_id, current location, or missing search result.",
            "For contact or reminder update/remove actions, a blank target_identifier must return should_abstain true with missing_information target_identifier and abstain_reason missing_target_identifier.",
            "When visible_records_count is greater than one, never choose or guess a record: return should_abstain true, include unique_target_identifier in missing_information, and use abstain_reason ambiguous_target.",
            "Implement every validation branch in the generated function itself. Runtime output normalization is not part of validation proof and must not be relied on to add missing requirements or reverse should_abstain.",
        )
    if request.suggested_tool_name == "prepare_upcoming_reminder_search_args":
        return (
            "Return exactly target_tool_name, search_kwargs, should_call_search, and abstain_reason on every branch.",
            "For a positive current_timestamp, target_tool_name is search_reminder, search_kwargs contains only reminder_timestamp_lowerbound equal to current_timestamp, should_call_search is true, and abstain_reason is empty.",
            "For a missing, nonnumeric, or nonpositive current_timestamp, target_tool_name is empty, search_kwargs is empty, should_call_search is false, and abstain_reason is missing_current_timestamp.",
            "Never call search_reminder or any state-changing function inside this generated argument-preparation tool.",
        )
    if request.suggested_tool_name == "prepare_message_recency_search_args":
        return (
            "Return exactly target_tool_name, search_kwargs, should_call_search, and abstain_reason on every branch.",
            "For a positive current_timestamp, target_tool_name is search_messages, search_kwargs contains creation_timestamp_upperbound equal to current_timestamp, should_call_search is true, and abstain_reason is empty.",
            "If content_keyword is nonblank, copy it into search_kwargs as content; if it is blank, omit content.",
            "For a missing, nonnumeric, or nonpositive current_timestamp, target_tool_name is empty, search_kwargs is empty, should_call_search is false, and abstain_reason is missing_current_timestamp.",
            "Never call search_messages or any state-changing function inside this generated argument-preparation tool.",
        )
    if request.suggested_tool_name == "prepare_past_reminder_recency_search_args":
        return (
            "Return exactly target_tool_name, search_kwargs, should_call_search, and abstain_reason on every branch.",
            "For a positive current_timestamp, target_tool_name is search_reminder, search_kwargs contains only creation_timestamp_upperbound equal to current_timestamp, should_call_search is true, and abstain_reason is empty.",
            "For a missing, nonnumeric, or nonpositive current_timestamp, target_tool_name is empty, search_kwargs is empty, should_call_search is false, and abstain_reason is missing_current_timestamp.",
            "Never call search_reminder or any state-changing function inside this generated argument-preparation tool.",
        )
    if request.suggested_tool_name == "resolve_search_window_or_bounds":
        return (
            "Return exactly these output keys on every branch: target_tool_name, search_kwargs, should_call_search, abstain_reason, interpretation, and bounds_source.",
            "Normalize phrase and direction to lowercase strings before branching.",
            "Infer a phrase_direction from phrase before using direction: yesterday or prior day -> yesterday; later today -> later_today; today -> today; upcoming, future, next reminder, next todo, due later, or later -> upcoming; oldest, earliest, or first -> oldest; latest, most recent, or newest -> latest.",
            "If phrase_direction is nonblank, it overrides generic or conflicting direction values such as latest, recent, most_recent, newest, old, or empty.",
            "Do not abstain when phrase contains a supported bounded recency word even if direction is generic.",
            "Use target_tool_name search_reminder for target_domain reminder and search_messages for target_domain message.",
            "For reminder target_domain with timestamp_intent creation, reminder_creation, created, creation_time, or created_time, use creation_timestamp_lowerbound and creation_timestamp_upperbound.",
            "For reminder target_domain with timestamp_intent reminder, upcoming, due, due_time, reminder_time, or empty, use reminder_timestamp_lowerbound and reminder_timestamp_upperbound.",
            "For message target_domain, use creation_timestamp_lowerbound and creation_timestamp_upperbound.",
            "For yesterday, compute center=current_timestamp-86400, lower=center-120, and upper=center+120.",
            "For today, compute the UTC day bounds from current_timestamp unless timezone_offset is provided: lower=current day's midnight and upper=lower+86399.",
            "For upcoming, return only the lowerbound key set to current_timestamp.",
            "For latest or oldest with lookback_days equal to zero, return only the appropriate creation_timestamp_upperbound set to current_timestamp; zero means no explicit lookback limit and must not cause abstention.",
            "If current_timestamp is missing or <= 0, return should_call_search false, empty target_tool_name/search_kwargs, abstain_reason missing_current_timestamp, empty interpretation, and bounds_source abstain.",
        )
    if request.suggested_tool_name == "plan_message_counterparty_search":
        return (
            "Return exactly these output keys on every branch: phase, message_direction, selection_mode, should_call_search_contacts, search_contacts_kwargs, should_call_search_messages, search_messages_kwargs, should_call_tool, abstain_reason, next_step, selected_message, counterparty_phone_number, answer_value, exact_final_answer, final_answer_recommendation, copy_exactly.",
            "Normalize message_direction aliases: sent, outgoing, from_me, sender, i_sent, and me_to_them become sent; received, incoming, to_me, recipient, they_sent, and them_to_me become received; either stays either and must abstain as ambiguous_message_direction.",
            "Normalize selection_mode aliases: latest, last, newest, most_recent, and recent become latest; oldest, first, and earliest become oldest.",
            "Use this branch order: validate direction and mode; if messages is a non-empty list, select the latest or oldest visible message by numeric creation_timestamp and return answer_ready; else if self_person_id is blank, return self_lookup_required; else return message_search_required.",
            "For self_lookup_required, set should_call_search_contacts true, search_contacts_kwargs {'is_self': True}, should_call_search_messages false, search_messages_kwargs {}, should_call_tool true, next_step exactly 'call search_contacts, then call this helper again with self_person_id', and all answer fields empty with copy_exactly false.",
            "For message_search_required with sent, search_messages_kwargs must include {'sender_person_id': self_person_id}; for received it must include {'recipient_person_id': self_person_id}. If content_keyword is nonblank, also include {'content': content_keyword}.",
            "For message_search_required, set should_call_search_contacts false, should_call_search_messages true, should_call_tool true, next_step exactly 'call search_messages with search_messages_kwargs', selected_message {}, answer fields empty, and copy_exactly false.",
            "For answer_ready, set should_call_search_contacts false, should_call_search_messages false, search kwargs empty, should_call_tool false, next_step exactly 'answer with final_answer_recommendation', selected_message to the selected visible record exactly, counterparty_phone_number and answer_value to the selected counterparty phone, and copy_exactly true.",
            "For answer_ready with self_person_id present, counterparty is the side whose person_id is not self_person_id; otherwise use sender_phone_number for received messages and recipient_phone_number for sent messages.",
            "For a received answer with content containing 'you want' and a nonblank content_keyword, exact_final_answer and final_answer_recommendation must be phone + ' asked you if you want some ' + content_keyword.",
            "For the outgoing/sent visible-message answer branch in the public examples, exact_final_answer and final_answer_recommendation are exactly the counterparty phone number.",
            "For abstain, include all output keys, set should_call_tool false, empty kwargs and selected_message {}, answer fields empty, copy_exactly false, and next_step to the expected ask/repair action.",
        )
    if request.suggested_tool_name == "prepare_direct_contact_action_args":
        return (
            "Return exactly these output keys on every branch: downstream_tool_name, downstream_tool_kwargs, should_call_tool, and abstain_reason.",
            "The spec must list the preserved original side-effect tools in both required_original_tool_calls and preserves_side_effect_tools: add_contact, modify_contact, remove_contact, and send_message_with_phone_number.",
            "This generated tool never mutates contacts or sends messages. It only prepares the original ToolSandbox tool name and kwargs from visible scalar inputs.",
            "Normalize action_type aliases: add/create/save become add_contact; update/modify/change become modify_contact; remove/delete become remove_contact; send/message/text become send_message.",
            "Normalize phone numbers by removing spaces, parentheses, periods, and dashes while preserving a leading plus sign when present.",
            "For add_contact, require contact_name and phone_number, then return downstream_tool_name add_contact with kwargs containing name and phone_number. Include relationship only when it is nonblank.",
            "For modify_contact, require record_id and at least one concrete update field. Return downstream_tool_name modify_contact with person_id equal to record_id plus phone_number, name, or relationship when those updates are visible. If target_field/new_value are used, map phone/phone_number/number to phone_number, name/contact_name to name, and relationship to relationship.",
            "For remove_contact, require record_id and return downstream_tool_name remove_contact with kwargs {'person_id': record_id}.",
            "For send_message, require phone_number and message_text and return downstream_tool_name send_message_with_phone_number with kwargs {'phone_number': normalized_phone, 'content': message_text}.",
            "For search, recency, relationship-batch, reminder, ambiguous, or insufficient-information requests, return downstream_tool_name '', downstream_tool_kwargs {}, should_call_tool false, and abstain_reason not_direct_scalar_contact_action.",
            "For missing fields, abstain with the specific reason missing_required_fields, missing_person_id, or no_update_fields.",
            "Never invent a person_id, phone number, name, relationship, or message content that is not visible in the inputs.",
        )
    if request.suggested_tool_name == "select_message_counterparty_for_contact_update":
        return (
            "Return exactly these output keys on every branch: selected_record, selected_message, selected_message_id, selected_person_id, selected_phone_number, selected_timestamp, downstream_tool_name, downstream_tool_kwargs, should_call_tool, tie_candidates, abstain_reason, safety_notes, final_answer_recommendation.",
            "Normalize selection_mode so latest selects the maximum numeric creation_timestamp and oldest selects the minimum numeric creation_timestamp.",
            "Use a direct extreme-value algorithm rather than sorting and choosing opposite list ends: normalize the mode, compute winning_timestamp = max(valid_timestamps) for latest or min(valid_timestamps) for oldest, then collect records whose creation_timestamp equals winning_timestamp. Require exactly one winner before continuing.",
            "If updates is missing, empty, or only contains blank/None values, abstain with missing_updates before selecting records.",
            "Build candidates only from dict records with numeric creation_timestamp. A bool is not a numeric timestamp.",
            "If more than one distinct visible record has the selected timestamp, abstain with ambiguous_timestamp_tie and include those records in tie_candidates.",
            "Require self_person_id to be copied from a visible search_contacts(is_self=True) result; never infer or invent it.",
            "For the selected message, compare sender_person_id and recipient_person_id with self_person_id. Use the single nonblank participant id unequal to self_person_id as the counterparty. Support both sent and received messages, and abstain with unresolved_counterparty unless exactly one non-self participant is available.",
            "On success, selected_record and selected_message must copy the selected visible record exactly; selected_message_id is message_id as a string or empty string; selected_timestamp is the selected creation_timestamp float.",
            "On success, downstream_tool_name must be modify_contact, downstream_tool_kwargs must contain person_id plus every concrete update field, should_call_tool true, tie_candidates [], abstain_reason empty, safety_notes exactly 'call modify_contact with downstream_tool_kwargs', and final_answer_recommendation exactly 'call modify_contact with downstream_tool_kwargs'.",
            "For any abstain branch, downstream_tool_name must be empty, downstream_tool_kwargs {}, should_call_tool false, safety_notes exactly 'abstain; no safe contact update target', and final_answer_recommendation must be 'abstain:' plus abstain_reason.",
        )
    if request.suggested_tool_name == "select_message_content_by_recency":
        return (
            "Return exactly these output keys: selected_record, selected_message, selected_message_id, selected_content, selected_timestamp, should_answer, abstain_reason, tie_candidates, selection_reason, exact_final_answer, final_answer_recommendation, copy_exactly.",
            "Normalize selection_mode so latest, newest, most recent, and recent select the maximum creation_timestamp; oldest, earliest, and first select the minimum creation_timestamp.",
            "Build candidates only from dict records with numeric creation_timestamp. A bool is not a numeric timestamp.",
            "Before tie detection, de-duplicate duplicate visible message records. Prefer a stable key of message_id, creation_timestamp, and content; if message_id is missing, include creation_timestamp, content, sender_person_id, recipient_person_id, sender_phone_number, and recipient_phone_number.",
            "The stable key must include message_id when message_id is present. Two records with different message_id values are distinct messages even when timestamp and content match.",
            "If duplicate copies share the full stable key, keep the first visible copy and its original input index. Do not overwrite it with a later duplicate, and do not use the duplicate's later index in selection_reason.",
            "Treat same-timestamp records as ambiguous only when two distinct deduplicated visible messages remain at the selected timestamp; different message_id values at the same timestamp are distinct and must produce ambiguous_timestamp_tie.",
            "Recommended algorithm: create two parallel lists named deduped_records and deduped_indices. Iterate enumerate(records). Build key = (message_id, creation_timestamp, content) when message_id is nonblank; otherwise key = (creation_timestamp, content, sender_person_id, recipient_person_id, sender_phone_number, recipient_phone_number). If key was already seen, skip it. Otherwise append the record to deduped_records and append the original index to deduped_indices.",
            "Do not store deduped records as tuple pairs, and do not iterate 'for index, record in deduped_records'. Records are dictionaries, so unpacking a record as two values is invalid.",
            "After dedupe, compute selected_timestamp as max or min over deduped_records. Build tied_positions as integer positions i where deduped_records[i]['creation_timestamp'] equals selected_timestamp. If len(tied_positions) > 1, return ambiguous_timestamp_tie with tie_candidates copied from deduped_records at those positions in original order.",
            "For a successful selection, selected_pos must be tied_positions[0], selected_original_index must be deduped_indices[selected_pos], and selected_record must be deduped_records[selected_pos]. selection_reason must be exactly 'selected_latest_message_by_creation_timestamp_at_index_' + selected_original_index for latest mode, or 'selected_oldest_message_by_creation_timestamp_at_index_' + selected_original_index for oldest mode.",
            "For success, selected_record and selected_message must copy the first visible selected record exactly, selected_message_id must be the selected record message_id as a string or empty string, selected_content must be stripped content, should_answer true, abstain_reason empty, tie_candidates empty, copy_exactly true.",
            "For a latest success, exact_final_answer and final_answer_recommendation must equal \"Your most recent message says '<content>'.\" using the selected_content exactly inside single quotes.",
            "For an oldest success, exact_final_answer and final_answer_recommendation must equal \"Your oldest message says '<content>'.\" using the selected_content exactly inside single quotes.",
            "For no records, invalid mode, no numeric timestamps, missing selected content, or distinct timestamp ties, should_answer must be false, exact_final_answer empty, copy_exactly false, and final_answer_recommendation must be 'abstain:' plus the abstain_reason.",
        )
    if request.suggested_tool_name == "prepare_holiday_search_args":
        return (
            "Return exactly these output keys on every branch: should_call_search_holiday, search_holiday_kwargs, holiday_name, year_policy, final_answer_recommendation, and abstain_reason.",
            "Extract a visible holiday name from user_request without using benchmark task ids or hidden answers. Preserve common holiday capitalization such as Thanksgiving and Christmas Day.",
            "Do not hard-code a finite if/elif list of holiday names from the examples. Write a small text-extraction algorithm that can handle an unseen holiday label in the same wording pattern.",
            "Do not import any module. The validator rejects imports; use only plain Python string operations, loops, and conditionals inside the single generated function.",
            "The extraction should remove task framing such as 'how many days until', 'what is the timestamp for', 'holiday', 'date', 'this year', and question punctuation, then keep the remaining visible holiday phrase.",
            "Algorithm requirement: first find and remove a standalone four-digit year and surrounding words like 'in 2027' from the candidate holiday phrase; then strip leading phrases such as 'how many days is it till', 'how many days until', 'what is the timestamp for', 'what is the date for', and 'when is'.",
            "After stripping framing, title-case the remaining phrase unless it already contains apostrophes or mixed capitalization. The returned holiday_name must not include a year or words such as timestamp, date, holiday, how many days, until, or till.",
            "If user_request contains any four digit year from 1900 through 2200 anywhere in the visible text, convert it to int, include that year in search_holiday_kwargs, and set year_policy exactly to explicit_year.",
            "If no explicit year is visible, search_holiday_kwargs must contain only holiday_name and year_policy must be environment_resolves_year.",
            "If no concrete holiday name is visible, should_call_search_holiday is false, search_holiday_kwargs is {}, holiday_name is '', year_policy is missing_holiday_name, final_answer_recommendation is exactly 'I need the holiday name before I can look up its timestamp.', and abstain_reason is missing_holiday_name.",
            "In the missing holiday-name branch, year_policy must be missing_holiday_name even when no explicit year is present.",
            "Do not compute a holiday date or timestamp inside this generated tool. It only prepares the preserved original search_holiday call.",
        )
    if request.suggested_tool_name == "extract_service_answer_field":
        return (
            "Return exactly these output keys on every branch: answer_value, answer_kind, answer_unit, should_call_downstream_tool, downstream_tool_name, downstream_tool_kwargs, exact_final_answer, final_answer_recommendation, copy_exactly, and abstain_reason.",
            "The spec must list the preserved original producer tools in both required_original_tool_calls and preserves_side_effect_tools: search_location_around_lat_lon, search_lat_lon, search_weather_around_lat_lon, calculate_lat_lon_distance, and convert_currency.",
            "This generated tool never calls a service. It only reads the visible payload returned by an original ToolSandbox lookup, distance, weather, or conversion tool.",
            "Normalize service_payload before extracting: if it is a list, inspect dict items in order; if it is a dict with a result key, inspect result and the wrapper; if it is a scalar wrapped as {'result': value}, extract from result.",
            "Supported answer fields include phone_number, address, distance, distance_km, converted_amount, amount, current_temperature, temperature, high_temperature, low_temperature, and result.",
            "If service_payload is {'result': numeric} and requested_unit or answer_subject is visible, treat it as a distance result for distance-style requests and return answer_kind distance with the numeric result preserved as answer_value.",
            "If service_payload is {'result': numeric} and requested_unit is a visible currency code such as USD, EUR, CNY, or GBP, treat it as a converted_amount result and include requested_unit as answer_unit.",
            "Currency unit preservation is mandatory: if the payload has currency_code, currency, target_currency, to_currency, or requested_unit is a visible three-letter currency code, answer_unit must be that code and must not be blank.",
            "For converted_amount results with a nonblank answer_unit, exact_final_answer and final_answer_recommendation must be exactly answer_value + ' ' + answer_unit with no trailing blank when answer_unit is empty and no duplicated unit.",
            "If service_payload is {'result': string} and the string looks like a street/postal address or answer_subject is address, treat it as an address result and preserve the string exactly.",
            "For missing or blank requested fields, return answer_value '', copy_exactly false, and a nonempty abstain_reason such as no_supported_answer_field or missing_requested_field.",
            "If a downstream lookup is needed and the payload visibly contains latitude and longitude plus a downstream place or destination, return should_call_downstream_tool true with the original downstream_tool_name and kwargs only; otherwise should_call_downstream_tool false.",
            "When answer_value is found, answer_kind must name the supported field class, answer_unit must use requested_unit when visible or the payload unit when present, exact_final_answer and final_answer_recommendation must contain the scalar answer, copy_exactly true, and abstain_reason ''.",
            "For phone numbers, preserve the visible phone string exactly. For addresses, preserve the visible address string. For distances and temperatures, preserve the numeric text and unit without adding unsupported conversions.",
        )
    if request.suggested_tool_name == "extract_address_result":
        return (
            "Return exactly these output keys on every branch: answer_value, answer_kind, answer_unit, should_call_downstream_tool, downstream_tool_name, downstream_tool_kwargs, exact_final_answer, final_answer_recommendation, copy_exactly, and abstain_reason.",
            "This generated tool never calls a service. It only reads the visible payload returned by an original ToolSandbox lookup, distance, or conversion tool.",
            "Normalize service_payload before extracting: if it is a list, inspect dict items in order; if it is a dict with a result key, inspect result and the wrapper; if it is a scalar wrapped as {'result': value}, extract from result.",
            "When answer_value is found, copy_exactly must be true, abstain_reason must be '', should_call_downstream_tool must be false, downstream_tool_name must be '', and downstream_tool_kwargs must be {}.",
            "When no supported answer field is present, answer_value, answer_kind, answer_unit, exact_final_answer, and final_answer_recommendation must be '', copy_exactly false, and abstain_reason must be no_supported_answer_field.",
        )
    if request.suggested_tool_name == "extract_phone_number_result":
        return (
            "Return exactly these output keys on every branch: answer_value, answer_kind, answer_unit, should_call_downstream_tool, downstream_tool_name, downstream_tool_kwargs, exact_final_answer, final_answer_recommendation, copy_exactly, and abstain_reason.",
            "This generated tool never calls a service. It only reads the visible payload returned by an original ToolSandbox lookup.",
            "The tool should accept service_payload and optional answer_subject. If answer_subject is omitted, default it to ''.",
            "Normalize service_payload before extracting: if it is a list, inspect dict items in order; if it is a dict with a result key, inspect result and the wrapper; otherwise inspect the dict itself.",
            "Extract the visible phone_number field exactly; do not insert spaces, dashes, parentheses, or country-code formatting.",
            "When answer_subject is nonblank, exact_final_answer and final_answer_recommendation must be exactly 'The phone number for ' + answer_subject + ' is ' + answer_value.",
            "When answer_subject is blank and the payload record has a nonblank name, use that record name as answer_subject.",
            "When no subject is available, exact_final_answer and final_answer_recommendation must be exactly answer_value.",
            "When answer_value is found, copy_exactly must be true, abstain_reason must be '', should_call_downstream_tool must be false, downstream_tool_name must be '', and downstream_tool_kwargs must be {}.",
            "When no supported answer field is present, answer_value, answer_kind, answer_unit, exact_final_answer, and final_answer_recommendation must be '', copy_exactly false, and abstain_reason must be no_supported_answer_field.",
        )
    if request.suggested_tool_name == "extract_distance_result":
        return (
            "Return exactly these output keys on every branch: answer_value, answer_kind, answer_unit, should_call_downstream_tool, downstream_tool_name, downstream_tool_kwargs, exact_final_answer, final_answer_recommendation, copy_exactly, and abstain_reason.",
            "This generated tool never calls a service. It only reads a visible distance payload from calculate_lat_lon_distance.",
            "If service_payload is a dict with result, distance_km, distance, or value, extract that numeric value directly. If service_payload['result'] is a float or int, do not call .get on it; use it as the distance.",
            "Set answer_kind exactly to distance for every successful branch. Set answer_unit to km when requested_unit is kilometers, kilometer, km, or blank and no other distance unit is visible.",
            "For success with answer_subject, exact_final_answer and final_answer_recommendation must be exactly 'You are approximately <rounded> kilometers away from <answer_subject>.' where <rounded> is the numeric value rounded to two decimal places with trailing zeros removed.",
            "When answer_subject is blank, exact_final_answer and final_answer_recommendation must be '<answer_value> <answer_unit>' with no duplicated unit.",
            "When no numeric distance is present, return empty answer fields, copy_exactly false, and abstain_reason no_supported_answer_field.",
        )
    if request.suggested_tool_name == "extract_temperature_result":
        return (
            "Return exactly these output keys on every branch: answer_value, answer_kind, answer_unit, should_call_downstream_tool, downstream_tool_name, downstream_tool_kwargs, exact_final_answer, final_answer_recommendation, copy_exactly, and abstain_reason.",
            "This generated tool never calls a weather service itself. It reads a visible search_weather_around_lat_lon payload and completes any local deterministic unit conversion inside the generated function.",
            "Normalize service_payload before extracting: if it is a list, inspect dict items in order; if it is a dict with a result key, inspect both result and the wrapper without discarding richer named fields. Metric-specific named fields take precedence over a generic result scalar. Use a scalar result directly only when no requested metric-specific field is available.",
            "Use requested_metric to select the visible temperature field. Treat selector tokens used by the public validation examples as the canonical interface values, and normalize visible aliases such as now/current, mean/average, highest/maximum/high/max, and lowest/minimum/low/min to those declared values. Current selects current_temperature then temperature; average selects average_temperature; maximum semantics select max_temperature then high_temperature; minimum semantics select min_temperature then low_temperature. Never silently use current_temperature when an explicit maximum, minimum, or average metric was requested.",
            "When requested_unit is Fahrenheit and the selected visible unit is Celsius, calculate Fahrenheit as Celsius * 9 / 5 + 32 inside this pure generated tool. When requested_unit is Celsius and the selected visible unit is Fahrenheit, calculate Celsius as (Fahrenheit - 32) * 5 / 9. Do not return a downstream handoff to unit_conversion for deterministic arithmetic on already-visible values.",
            "Complete field selection and unit conversion before constructing answer_value or either final-answer string. Round a converted numeric value to at most two decimal places so binary floating-point artifacts are not exposed, while preserving a visible unconverted numeric value as text.",
            "Every successful branch must be answer-ready in one generated-tool call: should_call_downstream_tool false, downstream_tool_name '', downstream_tool_kwargs {}, nonempty exact_final_answer and final_answer_recommendation, copy_exactly true, and abstain_reason ''.",
            "For a successful answer with answer_subject, exact_final_answer and final_answer_recommendation must identify the canonical requested metric, subject, numeric answer, and answer unit. Use the same canonical selector label required by the corresponding public validation example.",
            "When no supported temperature field or scalar conversion result is present, return empty answer fields, copy_exactly false, and abstain_reason no_supported_answer_field.",
        )
    if request.suggested_tool_name == "extract_converted_amount_result":
        return (
            "Return exactly these output keys on every branch: answer_value, answer_kind, answer_unit, should_call_downstream_tool, downstream_tool_name, downstream_tool_kwargs, exact_final_answer, final_answer_recommendation, copy_exactly, and abstain_reason.",
            "This generated tool never calls a service. It only reads a visible convert_currency payload.",
            "If service_payload is a dict with converted_amount, amount, value, or result, extract that numeric value directly. If service_payload['result'] is a float or int, do not call .get on it; use it as the converted amount.",
            "Set answer_kind exactly to converted_amount for every successful branch.",
            "Set answer_unit from requested_unit first when nonblank; otherwise use currency_code, currency, target_currency, to_currency, or unit from the payload. If a unit is visible, answer_unit must not be blank.",
            "For success, exact_final_answer and final_answer_recommendation must be answer_value + ' ' + answer_unit when answer_unit is nonblank; otherwise they must be answer_value with no trailing space.",
            "When no numeric converted amount is present, return empty answer fields, copy_exactly false, and abstain_reason no_supported_answer_field.",
        )
    if request.suggested_tool_name == "days_between_timestamps":
        return (
            "Return exactly these output keys: days and seconds.",
            "Compute diff = int(timestamp_1) - int(timestamp_0). days is diff // 86400 and seconds is diff % 86400.",
            "If timestamp_1 is earlier than timestamp_0, preserve Python floor-division semantics for days and seconds so the two fields still reconstruct the signed difference.",
            "Do not call time, datetime, search_holiday, or any ToolSandbox tool. Use only the two visible timestamp inputs.",
        )
    if request.suggested_tool_name == "plan_device_status_lookup":
        return (
            "Return exactly these output keys on every branch: tool_name, arguments, should_call, target_service, status_value, status_label, final_answer_recommendation, and abstain_reason.",
            "This is read-only. Never return a setter tool and never change state.",
            "First classify whether user_request is a read-only question or an action request. Requests containing action verbs such as turn on, turn off, enable, disable, switch on, switch off, set, activate, or deactivate are not read-only status lookups; for those return should_call false, tool_name '', arguments {}, target_service '', status_value false, status_label '', final_answer_recommendation '', and abstain_reason not_read_only_status_lookup.",
            "Map wifi requests to get_wifi_status, cellular/mobile service requests to get_cellular_service_status, location service requests to get_location_service_status, and low battery mode requests to get_low_battery_mode_status.",
            "Before a visible getter result exists, return the selected getter tool_name, arguments {}, should_call true, the normalized target_service, the readable status_label such as Wifi or Cellular service, empty final_answer_recommendation, status_value false, and abstain_reason ''.",
            "After visible_state_result contains a visible true/on/enabled result, return should_call false, status_value true, status_label as the readable service label, and a final_answer_recommendation that answers the requested service as on.",
            "After visible_state_result contains a visible false/off/disabled result, return should_call false, status_value false, status_label as the readable service label, and a final_answer_recommendation that answers the requested service as off.",
            "If no supported read-only status target is visible, return should_call false, tool_name '', arguments {}, target_service '', status_label '', final_answer_recommendation '', and abstain_reason no_status_target.",
        )
    if request.suggested_tool_name == "plan_device_state_action_sequence_v3":
        return (
            "Return exactly these output keys on every branch: tool_name, arguments, should_call, reason, action_sequence, final_response_recommendation, continue_original_task_after_sequence, and abstain_reason.",
            "This tool only plans original native setter calls and must never execute them.",
            "The function inputs are target_service, desired_on, low_battery_blocks_enable, resume_original_task, and additional_services_to_enable. Do not parse natural-language requests, scenario names, task identifiers, hidden answers, or dataset labels.",
            "Map the normalized services wifi, cellular, location, and low_battery to set_wifi_status, set_cellular_service_status, set_location_service_status, and set_low_battery_mode_status. Every setter receives arguments {'on': <bool>}.",
            "Build a complete minimal action_sequence. When desired_on and low_battery_blocks_enable are true for wifi, cellular, or location, prepend one set_low_battery_mode_status action with on false and reason clear_low_battery_before_enabling_service. Then append the target setter. Append each supported additional_services_to_enable setter in input order, skipping duplicates and the target service.",
            "Use reason set_<service>_on or set_<service>_off for ordinary target and additional-service actions. Treat the public validation examples as binding for exact output shapes, action order, and final response strings.",
            "When resume_original_task is true, final_response_recommendation is exactly continue_original_task and continue_original_task_after_sequence is true. Otherwise return the service-specific completed-state sentence shown by the public examples and continue_original_task_after_sequence false.",
            "On success, should_call is true, abstain_reason is empty, and top-level tool_name, arguments, and reason exactly copy the first action. Never duplicate actions.",
            "When no supported target is visible, use the exact no_device_state_target abstention object from the negative example.",
        )
    if (
        request.suggested_tool_name
        == "plan_device_state_action_sequence_location_recovery"
    ):
        return (
            "Return exactly these output keys on every branch: tool_name, arguments, should_call, reason, action_sequence, final_response_recommendation, continue_original_task_after_sequence, and abstain_reason.",
            "This tool only plans original ToolSandbox setter calls. It must never execute those calls.",
            "This narrowed tool applies only to downstream location-dependent tasks after visible_state_or_error exposes a location-service PermissionError, disabled location service, location service not enabled, low battery blocking location enablement, or wifi disabled during a location search.",
            "For an applicable downstream location-service blocker, return exactly this action_sequence: first {'tool_name': 'set_low_battery_mode_status', 'arguments': {'on': False}, 'reason': 'clear_low_battery_before_enabling_service'}, second {'tool_name': 'set_location_service_status', 'arguments': {'on': True}, 'reason': 'set_location_on'}, third {'tool_name': 'set_wifi_status', 'arguments': {'on': True}, 'reason': 'enable_wifi_for_downstream_location_search'}.",
            "Treat these visible_state_or_error variants as the same applicable location-service blocker: PermissionError: Location service is not enabled; Location service is not enabled; Location service cannot be turned on in low battery mode; location service disabled; location unavailable.",
            "For an applicable downstream location-search wifi blocker such as ConnectionError: Wifi is not enabled, return exactly one action: {'tool_name': 'set_wifi_status', 'arguments': {'on': True}, 'reason': 'enable_wifi_for_downstream_location_search'}.",
            "On the applicable branch, top-level tool_name, arguments, and reason must copy the first action exactly; should_call must be true; final_response_recommendation must be exactly continue_original_task; continue_original_task_after_sequence must be true; abstain_reason must be ''.",
            "The applicable branch includes visible user requests for reminders, todos, weather, distance, location lookup, address lookup, phone lookup for a place, find/search/look up near a place, or any visible text that needs a location service result after the location-service error.",
            "Do not use this tool for cellular-disabled, contact-only, message-only, direct device-setting, or unrelated device-state errors. Do not use it for a wifi-disabled error unless the visible request is a downstream location-dependent search/reminder/weather/distance task. For non-applicable branches return should_call false, tool_name '', arguments {}, action_sequence [], final_response_recommendation '', continue_original_task_after_sequence false, reason exactly no_device_state_target, and abstain_reason exactly no_device_state_target.",
            "Never return a successful branch with an empty action_sequence. Never duplicate actions in action_sequence.",
            "Never return generic text such as Device state has been updated or Completed action. The only successful final_response_recommendation for this tool is exactly continue_original_task.",
        )
    if request.suggested_tool_name == "plan_send_message_contact_lookup":
        return (
            "Return exactly the keys shown in the validation examples on every branch.",
            "Before a contact record is visible, prepare search_contacts kwargs from recipient_name and keep the exact visible message_content for the later original send_message_with_phone_number call.",
            "After a unique selected contact is visible, prepare the preserved original send_message_with_phone_number kwargs with that contact's phone_number and the exact visible message_content.",
            "Do not call search_contacts or send_message_with_phone_number inside this generated tool.",
            "If recipient_name or message_content is missing, abstain with the exact expected missing-field reason and do not prepare downstream kwargs.",
        )
    if request.suggested_tool_name == "relative_day_time_to_timestamp":
        return (
            "Declare current_datetime_info as a required parameter with no default immediately after current_timestamp, before every optional parameter, so the callable schema requires visible local datetime context from timestamp_to_datetime_info. Declare day_offset, hour, and minute with None defaults after current_datetime_info because negative contract cases intentionally omit those scalar fields and must return 0.0 instead of raising TypeError. local_utc_offset_hours remains optional after them.",
            "The first executable validation branch must return 0.0 when current_datetime_info is not a dict, is empty, omits any of hour/minute/second, or contains None for any of those fields. A check for current_datetime_info is None is insufficient. Do not use dict.get with a zero default for required datetime fields because an empty producer record is invalid, not midnight.",
            "Return 0.0 instead of raising an exception whenever hour, minute, day_offset, current_timestamp, or current_datetime_info is missing, None, or malformed.",
            "Reject invalid hour/minute by returning 0.0.",
            "When current_datetime_info is present, require hour, minute, and second fields in that dict.",
            "For current_datetime_info arithmetic, compute local_midnight_timestamp = int(current_timestamp) - (current_hour*3600 + current_minute*60 + current_second).",
            "Return float(local_midnight_timestamp + int(day_offset)*86400 + target_hour*3600 + target_minute*60).",
            "Do not preserve current seconds or fractional current_timestamp in the returned timestamp.",
            "Do not apply local_utc_offset_hours after current_datetime_info arithmetic.",
        )
    if request.suggested_tool_name == "next_weekday_time_to_timestamp":
        return (
            "Reject invalid target_isoweekday outside 1..7 by returning 0.0 before computing any timestamp.",
            "Reject invalid hour/minute by returning 0.0.",
            "Require current_datetime_info to be a non-empty dict with hour, minute, second, and isoweekday fields; return 0.0 when it is missing or empty.",
            "Compute local_midnight_timestamp = int(current_timestamp) - (current_hour*3600 + current_minute*60 + current_second).",
            "Compute days_ahead = (target_isoweekday - current_isoweekday) % 7.",
            "If days_ahead is 0 and target hour/minute is not strictly after the current local time, set days_ahead to 7.",
            "Return float(local_midnight_timestamp + days_ahead*86400 + target_hour*3600 + target_minute*60).",
            "Do not preserve current seconds or fractional current_timestamp in the returned timestamp.",
            "Do not apply local_utc_offset_hours after current_datetime_info arithmetic.",
        )
    if request.suggested_tool_name == "prepare_reminder_creation_args":
        return (
            "Use this execution order: normalize inputs; determine whether concrete coordinates exist; apply location abstention gates; choose timestamp; clean content only if coordinates will be included; return add_reminder kwargs.",
            "Apply location abstention gates before constructing add_reminder_kwargs.",
            "For location abstention gates, set timestamp_source to current_datetime_info when current_datetime_info is a non-empty dict and relative fields are present; otherwise use resolved when only a resolved timestamp is available; otherwise use none.",
            "If location_required is true and concrete coordinates are unavailable, return should_call_add_reminder false, add_reminder_kwargs {}, abstain_reason required_location_unresolved, location_status required_missing.",
            "If location_requested is true, location_required is false, location_available is false, and location_lookup_failed is false, return should_call_add_reminder false, add_reminder_kwargs {}, abstain_reason optional_location_lookup_pending_do_not_call_add_reminder, location_status lookup_pending.",
            "After location gates, if resolved_reminder_timestamp is positive, use it directly, set timestamp_source resolved, and do not require current_timestamp, current_datetime_info, day_offset, hour, or minute.",
            "If no resolved timestamp exists and current_timestamp, day_offset, hour, and minute are all missing or None, return should_call_add_reminder false with abstain_reason missing_time_info; if concrete coordinates are available, location_status is provided.",
            "If no resolved timestamp is available and current_timestamp/day_offset/hour/minute are present but current_datetime_info is missing or empty, return abstain_reason missing_current_datetime_info_call_timestamp_to_datetime_info and timestamp_source none; location_status is provided only when concrete coordinates are available, otherwise omitted_optional.",
            "When using current_datetime_info for a relative timestamp, compute local_midnight_timestamp = int(current_timestamp) - (current_hour*3600 + current_minute*60 + current_second), then add int(day_offset)*86400 + target_hour*3600 + target_minute*60.",
            "If location_available is true and latitude/longitude are concrete nonzero values, include latitude and longitude in add_reminder_kwargs and set location_status provided.",
            "If location coordinates are unavailable and creation is allowed, do not invent coordinates; include latitude None and longitude None only when the expected object includes them, and set location_status omitted_optional.",
            "When coordinates are included, implement content cleaning with this exact general algorithm: cleaned_content = str(content or '').strip(); lower_content = cleaned_content.lower(); for marker in (' at ', ' near ', ' in ', ' by '): index = lower_content.rfind(marker); if index > 0: cleaned_content = cleaned_content[:index].strip(); break. Do not use lstrip, replace, strip(chars), or remove leading letters. For 'buy chocolate milk at Whole Foods', the stripped content is exactly 'buy chocolate milk'. When coordinates are not included, preserve content.",
        )
    if request.suggested_tool_name in {
        "prepare_location_search_args",
        "prepare_specific_location_search_args",
        "prepare_broad_location_search_args",
    }:
        if request.suggested_tool_name == "prepare_broad_location_search_args":
            return (
                "Return exactly these output keys: search_location_kwargs, should_call_downstream_tool, downstream_tool_name, downstream_tool_kwargs, location_query, abstain_reason.",
                "This tool only handles broad unqualified place or category names such as Whole Foods, pharmacy, coffee shop, Safeway, or Trader Joe's. It does not handle qualified street/neighborhood phrases.",
                "Inputs must include user_request: str, location_phrase: str, latitude: float = 0.0, and longitude: float = 0.0.",
                "Clean location_query from location_phrase when nonblank, otherwise from the visible broad place phrase in user_request. If no broad place exists, return should_call_downstream_tool false, downstream_tool_name '', empty kwargs, location_query '', and abstain_reason missing_location_phrase.",
                "If location_query contains ' on ' or street, road, avenue, boulevard, bridge, airport, creek, market, center, mall, plaza, downtown, north, south, east, or west, return should_call_downstream_tool false, downstream_tool_name '', empty kwargs, location_query, and abstain_reason not_broad_location_phrase.",
                "If latitude or longitude is missing, None, or 0.0, return should_call_downstream_tool true, downstream_tool_name get_current_location, search_location_kwargs {}, downstream_tool_kwargs {}, location_query, and abstain_reason need_current_coordinates_for_broad_location_query.",
                "If nonzero latitude and longitude are present, return should_call_downstream_tool true, downstream_tool_name search_location_around_lat_lon, search_location_kwargs and downstream_tool_kwargs both exactly {'location': location_query, 'latitude': float(latitude), 'longitude': float(longitude)}, location_query, and abstain_reason ''.",
                "Never call original tools inside this generated function. Only return the next original tool name and kwargs.",
            )
        return (
            "Return exactly these output keys: search_location_kwargs, should_call_downstream_tool, downstream_tool_name, downstream_tool_kwargs, location_query, abstain_reason.",
            "This tool is scoped to specific visible place phrases. It prepares search_location_around_lat_lon kwargs for a venue, street, neighborhood, or qualified place phrase that is visible in user_request or location_phrase.",
            "For every successful specific-place result, search_location_kwargs and downstream_tool_kwargs must both be exactly {'location': location_query}, should_call_downstream_tool must be true, downstream_tool_name must be search_location_around_lat_lon, and abstain_reason must be ''.",
            "Never return should_call_downstream_tool true with blank downstream_tool_name. Never return a nonblank location_query for a valid specific-place search while leaving search_location_kwargs empty.",
            "If location_phrase is nonblank, treat it as the already-isolated visible place phrase. The normal successful query is cleaned location_phrase exactly; do not replace it with text from user_request when user_request is a reminder, todo, message, call, weather, distance, or other task sentence.",
            "Use user_request extraction only when location_phrase is blank or when user_request itself is a standalone place phrase with no task/reminder wording.",
            "When user_request is a standalone place phrase, such as 'Whole Foods on Stevens Creek' or 'Central Market on North Lamar', and it does not contain reminder/task wording, use the entire stripped user_request as location_query even when location_phrase is blank.",
            "When user_request is only a standalone place phrase that extends a short location_phrase, such as user_request 'Whole Foods on Stevens Creek' with location_phrase 'Whole Foods', use the full user_request as location_query. Do not apply this extension rule to full reminder/task sentences.",
            "When user_request is a reminder with explicit time/date and a location preposition, extract only the place phrase after the last location preposition (' at ', ' near ', ' in ', or ' by ') and strip trailing punctuation such as periods/commas plus temporal words.",
            "Never include reminder command text such as 'remind me', 'please create a reminder', 'add a reminder', or 'set a reminder' in location_query.",
            "Never use pronouns or command words such as 'me', 'my', 'please', 'remind', 'reminder', 'create', 'add', 'set', 'buy', or 'pick up' as a location_query.",
            "After extraction, location_query must never start with a location preposition. Remove leading 'at ', 'near ', 'around ', 'in ', or 'by ' before returning.",
            "Never include temporal words in location_query. Strip today, tomorrow, tonight, yesterday, weekday names, month names, next, this, AM/PM, clock times, and phrases such as 'at 5 PM' from the extracted place.",
            "If ' at ' is followed by a clock time such as '5 PM' and a later place preposition such as 'near', 'in', 'by', or another 'at' appears, do not include the clock time in location_query; use only the place phrase after the later place preposition.",
            "For 'Remind me to buy chocolate milk tomorrow 5PM at Whole Foods on Stevens Creek.', location_query is exactly 'Whole Foods on Stevens Creek'.",
            'For "Please create a reminder to pick up pasta tomorrow at 5 PM near Trader Joe\'s on Market Street.", location_query is exactly "Trader Joe\'s on Market Street".',
            "For 'Remind me to buy milk tomorrow at 5 PM.', there is no location phrase; return missing_location_phrase with empty kwargs.",
            "Do not return missing_reminder_time_before_location_lookup from this narrowed location tool. This tool only prepares read-only location lookup arguments or abstains when no visible place exists.",
            "For 'How far am I from the Golden Gate Bridge', is_reminder_request is false and the tool must call search_location_around_lat_lon for Golden Gate Bridge, even though the text has no reminder date/time.",
            "For standalone 'Whole Foods on Stevens Creek' with location_phrase 'Whole Foods', location_query is exactly 'Whole Foods on Stevens Creek' and the downstream tool is search_location_around_lat_lon with only {'location': 'Whole Foods on Stevens Creek'} because the street qualifier makes it specific.",
            "When neither location_phrase nor an extractable place exists in user_request, set should_call_downstream_tool false, location_query '', empty kwargs, downstream_tool_name '', and abstain_reason missing_location_phrase.",
        )
    return ()


def _model_authored_repair_prompt(
    request: ToolGenerationRequest,
    rejected_tool: GeneratedTool,
    errors: tuple[str, ...],
) -> str:
    repair_candidate_count = _model_authored_repair_candidate_count()
    strategy_number = next(
        (
            int(match.group(1))
            for error in errors
            if (match := re.fullmatch(r"repair_strategy:(\d+)", error))
        ),
        1,
    )
    errors = tuple(
        error for error in errors if not error.startswith("repair_strategy:")
    )
    strategy_guidance = {
        1: (
            "Trace each failing case through the current control flow and remove the "
            "first incorrect guard or return."
        ),
        2: (
            "Build a compact case table from the public examples, derive one shared "
            "predicate for positive versus negative cases, then implement it."
        ),
        3: (
            "Derive every native argument from argument_value_locations before writing "
            "guards; then add only abstention conditions proven by negative cases."
        ),
        4: (
            "Discard the prior branch structure and write the smallest clean algorithm "
            "that covers every public case without literal example-value checks."
        ),
        5: (
            "Adversarially audit every return path: prove each positive reaches exactly "
            "one native call and each negative reaches none, then rewrite any path that "
            "fails that proof."
        ),
    }.get(strategy_number, "Rewrite from the binding public contract.")
    syntax_repair = any(
        "syntax_error" in error or "missing_generated_code" in error for error in errors
    )
    force_rewrite = request.suggested_tool_name in {
        "prepare_location_search_args",
        "prepare_specific_location_search_args",
        "prepare_broad_location_search_args",
        "plan_device_state_action_sequence_v3",
        "plan_contact_relationship_batch_update",
        "prepare_direct_contact_action_args",
    }
    native_action_failures = tuple(
        error
        for error in errors
        if any(
            marker in error
            for marker in (
                "native_action_count",
                "native_action_arguments",
                "unexpected_native_action",
                "native_action_abstain",
                "native_action_success_status",
                "native_action_confirmation",
                "native_action_result_name",
            )
        )
    )
    native_action_failure_cases = {
        match.group(1)
        for error in native_action_failures
        if (match := re.match(r"^((?:source|held_out|negative)_\d+)_", error))
    }
    positive_native_action_failure_cases = {
        label
        for label in native_action_failure_cases
        if label.startswith(("source_", "held_out_"))
    }
    native_action_rewrite = (
        _request_complete_tools_enabled(request)
        and len(native_action_failure_cases) > 1
        and bool(positive_native_action_failure_cases)
        and (_validation_error_distance(errors) > 300 or strategy_number >= 4)
    )
    confirmation_contract_has_updates = any(
        isinstance(item.get("inputs"), dict) and "updates" in item["inputs"]
        for item in _native_action_validation_examples(request)
    )
    confirmation_repair_guidance = (
        " CRITICAL confirmation repair rule: the current candidate was rejected "
        "because its actor-facing confirmation violated the public contract. In the "
        "generated function, construct confirmation from the updates mapping after "
        "filtering out None and blank values. Include str(value) for every retained "
        "entry so each changed value appears verbatim. If selection_mode is visible, "
        "include it and describe the selected record by its semantic role. Never put "
        "a person_id, reminder_id, message_id, or other opaque identifier value in "
        "the confirmation. Do not return a fixed generic message such as 'updated "
        "successfully', and do not hard-code any example value. This repair is invalid "
        "unless that dynamic construction is present. "
        if confirmation_contract_has_updates
        and any("native_action_confirmation_" in error for error in errors)
        else ""
    )
    subject_first_confirmation_guidance = (
        " CRITICAL subject-first confirmation rule: each "
        "native_action_confirmation_not_subject_first validator error names a "
        "visible semantic subject value after the final colon. For each failing "
        "public case, identify the declared input parameter carrying that value. "
        "Construct the success confirmation so it begins with str(that parameter), "
        "followed by a concise action description. The first character of the "
        "confirmation must be the first character of the visible subject; do not "
        "prefix it with words such as Added, Created, Updated, Prepared, or Contact. "
        "Derive the subject parameter across all public cases and never hard-code "
        "the example values from validator errors. "
        if any(
            "native_action_confirmation_not_subject_first:" in error for error in errors
        )
        else ""
    )
    confirmation_contract_rewrite = (
        _request_complete_tools_enabled(request)
        and strategy_number >= 2
        and bool(confirmation_repair_guidance)
    )
    subject_first_confirmation_rewrite = (
        _request_complete_tools_enabled(request)
        and strategy_number >= 2
        and bool(subject_first_confirmation_guidance)
    )
    failed_case_labels = {
        match.group(1)
        for error in errors
        if (match := re.match(r"^((?:source|held_out|negative)_\d+)_", error))
    }
    native_action_cases = _native_action_validator_labeled_examples(request)
    failed_case_context = [
        item
        for item in native_action_cases
        if str(item.get("validator_case_label")) in failed_case_labels
    ]
    positive_count_failure = any(
        error.startswith(("source_", "held_out_"))
        and "_native_action_count:0!=1" in error
        for error in errors
    )
    focused_positive_case_guidance = (
        " CRITICAL FIRST STEP: repair the failing positive cases before considering "
        "any other cleanup. Each case below has a non-null expected_native_action, "
        "so its complete input combination must reach that exact native call once. "
        "A field name or value that sounds adverse does not make a positive case an "
        "abstention case. Substitute the complete failing inputs through every guard "
        "and remove or narrow the first guard that returns before the native call. "
        "Do not add a one-field abstention rule when that field value occurs in any "
        "positive case; distinguish it using the other demonstrated inputs. Failing "
        "positive cases: " + json.dumps(failed_case_context, sort_keys=True) + ". "
        if positive_count_failure
        else ""
    )
    previous_candidate = rejected_tool.to_json()
    if (
        syntax_repair
        or force_rewrite
        or native_action_rewrite
        or confirmation_contract_rewrite
        or subject_first_confirmation_rewrite
        or strategy_number >= 4
    ):
        previous_candidate = {"spec": previous_candidate["spec"], "code": ""}
    if _request_complete_tools_enabled(request):
        all_contract_cases = native_action_cases
        ranked_records_contract = any(
            isinstance(item.get("inputs"), dict)
            and "records" in item["inputs"]
            and "selection_mode" in item["inputs"]
            for item in all_contract_cases
        )
        ranked_record_repair_guidance = (
            " CRITICAL BLOCKING REPAIR: the validator has proven that the current "
            "ranked-record implementation acts or raises on malformed or tied "
            "evidence. Before any sorted, min, max, indexing, or native call, derive "
            "the ranking-field name from the positive examples and verify that records "
            "is nonempty, every item is a mapping, every item contains that field, and "
            "every ranking value has the demonstrated comparable type. If any check "
            "fails, return the complete abstain object immediately. Normalize the "
            "selection mode first. Compute winning_value = max(valid_values) for "
            "latest and winning_value = min(valid_values) for oldest; do not sort "
            "and then choose a different list end. Collect all records whose value "
            "equals winning_value, and require "
            "len(winners) == 1. Otherwise return the complete abstain object. Only "
            "index winners[0] after this uniqueness check. A repair that still uses "
            "max(records, ...), min(records, ...), or sorted(records, ...) before these "
            "guards is invalid. "
            if ranked_records_contract
            and any(
                marker in error
                for error in errors
                for marker in (
                    "native_action_execution_error",
                    "unexpected_native_action",
                    "native_action_abstain",
                )
            )
            else ""
        )
        paired_role_contract = any(
            isinstance(inputs := item.get("inputs"), dict)
            and bool(inputs.get("self_person_id"))
            and isinstance(records := inputs.get("records"), list)
            and any(
                isinstance(record, dict)
                and len([key for key in record if str(key).endswith("_person_id")]) >= 2
                for record in records
            )
            for item in all_contract_cases
        )
        counterparty_repair_guidance = (
            " CRITICAL counterparty binding rule: self_person_id is a required "
            "visible input copied from search_contacts(is_self=True). Compare it "
            "with both sender_person_id and recipient_person_id on the selected "
            "message. Bind person_id to the single nonblank participant unequal to "
            "self_person_id, regardless of whether self sent or received the "
            "message. Build and deduplicate a filtered list, require its length to "
            "be exactly one, then index candidates[0]. Never call next() directly "
            "on a tuple or list of role values. If that does not yield exactly one "
            "target, abstain before the native call, and never pass self_person_id "
            "to modify_contact. "
            if paired_role_contract
            else ""
        )
        focused_ranked_record_repair = (
            ranked_records_contract
            and bool(failed_case_labels)
            and any(
                marker in error
                for error in errors
                for marker in (
                    "unexpected_native_action",
                    "native_action_abstain",
                    "native_action_execution_error",
                    "native_action_count",
                    "native_action_arguments",
                    "native_action_result_",
                )
            )
        )
        if focused_ranked_record_repair:
            focused_strategy = {
                1: "Patch only the first unsafe selection or prerequisite branch.",
                2: "Re-derive the extreme ranking value and its exact winner set.",
                3: "Trace every remaining negative case to the first native-call path.",
                4: "Rewrite only the ranked-selection block, preserving action logic.",
                5: "Audit each prerequisite and prove that ambiguity reaches abstention.",
            }.get(strategy_number, "Patch only the remaining failed branches.")
            focused_output_contract = (
                "Return one JSON object with top-level spec and code_lines; do not "
                "return a candidates array. "
                if repair_candidate_count == 1
                else "Return a top-level candidates array with exactly "
                + str(repair_candidate_count)
                + " independent objects, each containing spec and code_lines. "
                "Candidate 1 must implement an explicit extreme-value winner set, "
                "candidate 2 must implement a grouped rank-value uniqueness check, "
                "and candidate 3 must use a distinct control flow that proves one "
                "unambiguous winner before the native call. Additional candidates, "
                "when requested, must use meaningfully different ranked-selection "
                "logic. Every candidate must be a complete standalone repair. "
            )
            return (
                "FOCUSED RANKED-RECORD REPAIR. Focused attempt "
                + str(strategy_number)
                + ": "
                + focused_strategy
                + " "
                + strategy_guidance
                + (
                    " Rewrite the implementation from the public contract because "
                    "earlier focused patches did not converge. "
                    if strategy_number >= 4
                    else " Make one minimal edit to the current model-authored "
                    "candidate; do not rewrite branches that already pass. "
                )
                + focused_output_contract
                + "Each code_lines value must define exactly one complete top-level "
                "function beginning with def and preserving the supplied function name "
                "and signature; never return only a function body. Keep the supplied "
                "spec, native action, and successful output behavior unchanged. "
                + focused_positive_case_guidance
                + counterparty_repair_guidance
                + "For each failing positive case, derive every action argument from "
                "the listed argument_value_locations and translate those descriptive "
                "paths to the declared function parameters. "
                + "The remaining failed public cases prove "
                "that the candidate acts or raises when ranked evidence is malformed "
                "or ambiguous. Before sorted, min, max, indexing, or the native call: "
                "require a nonempty records list; require every record to be a mapping "
                "containing the ranking field demonstrated by the positive contract; "
                "and require comparable ranking values. Do not build valid_records by "
                "filtering malformed entries out of the original collection. Use an "
                "all-record guard that immediately abstains if any original record "
                "fails one of these checks, then rank the unchanged collection. Derive "
                "the winning scalar "
                "value for the requested mode, collect every record whose ranking "
                "value equals it, and require len(winners) == 1. If any prerequisite "
                "fails or the winner is not unique, return the complete abstain object. "
                "The winners collection must contain only records equal to the "
                "mode-dependent minimum or maximum ranking value; setting winners to "
                "all structurally valid records is incorrect. "
                "without a native call. Only then select winners[0] and continue through "
                "the existing passing counterparty/action logic. Do not select directly "
                "with max(records), min(records), sorted(records), records[0], or "
                "records[-1]. Before record selection, filter optional action-update "
                "mappings to entries whose values are neither None nor blank strings; "
                "if no concrete update remains, abstain without a native call. Do not "
                "drop valid update fields: pass only keys that are present with "
                "non-None values. Forward all such entries together to the native "
                "action after target selection. "
                "drop required visible context guards while making this edit. If a "
                "negative case has a blank required context identifier, such as a "
                "self identifier needed to distinguish paired roles, abstain before "
                "selection and before the native call. Do not "
                "hard-code any example value. Every return path must contain all five "
                "keys: status, confirmation, abstain_reason, native_action, "
                "and native_result. Abstention uses status='abstain', confirmation='', "
                "a nonempty abstain_reason, native_action='', and native_result=None. "
                "The validator will rerun all positive, held-out, and negative cases, "
                "so preserve every behavior not implicated by the remaining failure. "
                "Approved native actions: "
                + json.dumps(
                    list(_request_native_action_names(request)), sort_keys=True
                )
                + ". Remaining validation errors: "
                + json.dumps(list(errors), sort_keys=True)
                + ". Remaining failed public cases: "
                + json.dumps(failed_case_context, sort_keys=True)
                + ". Supplied spec and current best candidate JSON: "
                + json.dumps(previous_candidate, sort_keys=True)
            )
        return (
            "Repair exactly one rejected native-action Python tool from its public "
            "contract. Return valid JSON only. "
            + (
                "Return one JSON object with top-level spec and code_lines; do not "
                "return a candidates array. "
                if repair_candidate_count == 1
                else "Return a top-level candidates array with exactly "
                + str(repair_candidate_count)
                + " independent objects, each containing spec and code_lines. "
                "Candidate 1 should make the smallest failing-case patch, candidate "
                "2 should implement an explicit public-case decision table, and "
                "candidate 3 should derive positive eligibility before applying "
                "negative guards. Additional candidates, when requested, must use "
                "meaningfully different control flow. The validator will execute all "
                "candidates and retain only the strongest contract match. "
            )
            + "Keep the supplied spec and function "
            "signature unchanged. Repair strategy "
            + str(strategy_number)
            + ": "
            + strategy_guidance
            + focused_positive_case_guidance
            + counterparty_repair_guidance
            + ranked_record_repair_guidance
            + confirmation_repair_guidance
            + subject_first_confirmation_guidance
            + _native_action_api_guidance(_request_native_action_names(request))
            + " Validation examples are binding for the exact native "
            "tool name and arguments. Positive examples must call exactly one approved "
            "native action; held-out examples must generalize; negative or "
            "insufficient-information examples must call none. The generated function "
            + (
                "The prior branch structure caused a native-action count or argument "
                "failure. Rewrite the implementation from the public contract rather "
                "than reconstructing or patching the previous code. "
                if native_action_rewrite
                else ""
            )
            + (
                "The prior implementation repeated a confirmation-contract failure. "
                "Rewrite the function from the public contract and do not reconstruct "
                "the prior confirmation expression. Build the confirmation only from "
                "semantic visible context such as selection_mode and from concrete "
                "nonblank update values; never interpolate an opaque native identifier. "
                if confirmation_contract_rewrite
                else ""
            )
            + "must return a JSON object after success or abstention. Never return the "
            "native function call directly because an approved native action may return "
            "None; assign its result to a local variable, then return a success JSON "
            "object. Every return path must contain all five keys: status, "
            "confirmation, abstain_reason, native_action, and native_result. A "
            "successful return uses status='success', a nonempty confirmation, an "
            "empty abstain_reason, the called native_action name, and native_result. "
            "An abstention return uses exactly status='abstain', confirmation='', a "
            "nonempty abstain_reason, native_action='', and native_result=None. Never "
            "omit an empty required field. A None native return is normal completion, not failure or "
            "abstention, so never branch on native_result is None. If "
            "a validation error says native_action_count is zero, revise the relevant "
            "positive branch so it literally calls the expected approved native "
            "function once with keyword arguments, assigns that call result to "
            "native_result, and then returns success. Do not substitute an arguments "
            "dict for the function call. Reference declared function parameters "
            "directly; never reference a variable named inputs unless inputs is itself "
            "a declared parameter. Paths such as inputs.content in the public contract "
            "mean the declared content parameter, not an inputs dictionary. Keep all "
            "parsing and normalization inside "
            "the required generated function and remove every reference to undefined "
            "utility or auxiliary functions. Trace the failing positive inputs through the candidate, "
            "identify the first guard or early return that prevents the native call, "
            "and remove or narrow that guard; a positive case cannot be rejected as "
            "insufficient or unsafe. Do not remove a working positive branch while repairing a "
            "held-out branch. When a selected record exposes paired role identifiers "
            "and the contract supplies an explicit self identifier, bind the action "
            "identity to the non-self value by comparing all visible role identifiers. "
            "Do not return early merely because one role equals self; a positive case "
            "may intentionally place self on either side of the selected record. Choose "
            "the single nonblank identifier unequal to self, and abstain only when the "
            "contract's negative cases require it. Do not assume one fixed role field "
            "is always the target. Apply this rule only when the validation examples "
            "demonstrate the paired-role invariant. "
            "When an input mapping supplies optional native-action updates, pass only "
            "keys that are present with non-None values. Forward all such entries "
            "together; do not make individual update fields mutually exclusive "
            "unless the public contract requires that. Do not add absent optional "
            "arguments with None unless the expected action explicitly contains them. "
            "When the function accepts an updates mapping, construct the success "
            "confirmation from that same filtered mapping and include every nonempty "
            "changed value verbatim. A fixed generic confirmation is never valid for "
            "an update action. Never include opaque native identifier values such as "
            "person_id, reminder_id, or message_id in confirmation text. If a visible "
            "selection_mode input determines the target, include that mode in the "
            "confirmation and describe the target by its semantic role rather than "
            "its internal identifier. "
            "Before any native action call, implement every binding negative case "
            "as an explicit abstention branch. For ranked record selection, validate "
            "the complete candidate collection before sorting: each candidate must be "
            "a mapping, must contain the ranking field demonstrated by the positive "
            "examples, and must carry the demonstrated value type. A KeyError or "
            "TypeError on a negative case means this guard must occur earlier; never "
            "sort, index, or call min/max before it. After the guard, compute the best "
            "value and collect every record that shares it. If more than one record "
            "shares that value, abstain before any native call. Do not treat the first "
            "best record as uniquely selected until this tie check passes. Always call "
            "native functions with keyword arguments using the "
            "exact names in expected_native_action; never pass update values "
            "positionally or map a value to a different field name. "
            "The function must not call the "
            "native action inside a loop, and must not ask the actor to repeat a native "
            "action that already succeeded. Keep all non-native side effects, imports, "
            "filesystem, network, subprocess, hidden state, try/except, raise, classes, "
            "lambdas, and while loops prohibited. Approved native actions: "
            + json.dumps(list(_request_native_action_names(request)), sort_keys=True)
            + ". Binding public contract cases: "
            + json.dumps(all_contract_cases, sort_keys=True)
            + ". Validation errors: "
            + json.dumps(list(errors), sort_keys=True)
            + ". Failing public contract cases (binding): "
            + json.dumps(failed_case_context, sort_keys=True)
            + ". For each failing positive case, trace the selected input record, "
            "derive every action argument from the listed argument_value_locations, "
            "and confirm that no guard returns before the declared action. "
            + "Supplied spec and previous candidate JSON: "
            + json.dumps(previous_candidate, sort_keys=True)
        )
    syntax_guidance = (
        "Because this is a syntax/code-shape failure, rewrite the function body "
        "from scratch instead of patching or copying the prior code. Every "
        "code_lines item must be one complete Python source line. Do not split "
        "a string literal across lines. Prefer double-quoted Python strings when "
        "the text may contain apostrophes, or build the text with string "
        "concatenation. Define exactly one top-level function and no other "
        "top-level def. "
        if syntax_repair
        else ""
    )
    semantic_rewrite_guidance = (
        "Because repeated repairs have not satisfied the public contract, rewrite "
        "the implementation "
        "from scratch. Do not copy the prior branch structure. Base the new code "
        "only on the public contract_rules, validation examples, and validation "
        "errors. "
        if (force_rewrite or strategy_number >= 4) and not syntax_repair
        else ""
    )
    state_sequence_guidance = (
        "For plan_device_state_action_sequence repairs, rewrite the failing branch "
        "to match the EXPECTED object in each public validation error exactly. "
        "Preserve the expected action count and order; do not add a setter absent "
        "from EXPECTED. Direct requests use the expected completed-state sentence "
        "and continue_original_task_after_sequence false. Downstream repairs use "
        "continue_original_task exactly when EXPECTED does. The top-level action "
        "fields must copy the first action. Use Python True and False, never JSON "
        "true or false. For the negative case, return the exact "
        "no_device_state_target object. Infer behavior only from the function "
        "inputs and public examples, never from scenario names or task labels. "
        if (request.suggested_tool_name or "").startswith(
            "plan_device_state_action_sequence"
        )
        else ""
    )
    status_lookup_guidance = (
        "For plan_device_status_lookup repairs, negative validation examples "
        "are binding. A request like 'Turn on wifi' is an action request, not a "
        "status question; it must return should_call false, empty tool_name, "
        "empty target_service/status_label/final_answer_recommendation, "
        "status_value false, and abstain_reason not_read_only_status_lookup. "
        "Check action verbs before checking device target words. If "
        "visible_state_result is a non-empty string such as True, False, on, "
        "or off, parse it and return should_call false with a final answer; do "
        "not return the getter again after a visible result is present. "
        if request.suggested_tool_name == "plan_device_status_lookup"
        else ""
    )
    relationship_batch_guidance = (
        "For plan_contact_relationship_batch_update repairs, every returned dict "
        "must include source_relationship and target_relationship. Use one local "
        "result-building branch or repeat all contract keys in every return; "
        "validation rejects branches missing those keys. Do not spend logic on "
        "natural-language status prose for this planner; "
        "final_answer_recommendation must be empty because the actor answers "
        "after original modify_contact calls complete. For __all_contacts__ with visible contacts, select every "
        "non-self contact not already at the target relationship instead of "
        "filtering by source relationship or looking for a relationship literally "
        "named __all_contacts__. If contacts are visible for __all_contacts__, "
        "do not abstain with no matching contacts while any non-self contact still "
        "needs the target relationship. If visible contact records have person_id "
        "but omit relationship, keep them eligible as actor-selected contacts "
        "instead of returning no matching contacts. "
        if request.suggested_tool_name == "plan_contact_relationship_batch_update"
        else ""
    )
    direct_contact_guidance = (
        "For prepare_direct_contact_action_args repairs, rewrite the direct "
        "action planner from the contract examples. The modify_contact branch "
        "must not require target_field/new_value when phone_number, contact_name, "
        "or relationship is already visible as a concrete update input. Build "
        "kwargs with person_id from record_id, then add normalized phone_number "
        "when phone_number is nonblank, name when contact_name is nonblank, and "
        "relationship when relationship is nonblank. Also support target_field "
        "and new_value as an alternate way to express one update field. If the "
        "expected object after != contains phone_number, the repaired code must "
        "include that phone_number in downstream_tool_kwargs for the matching "
        "modify_contact branch. Short action_type values are binding aliases: "
        "remove must behave as remove_contact, send must behave as send_message, "
        "modify/update must behave as modify_contact, and add/create must behave "
        "as add_contact. Do not return not_direct_scalar_contact_action for a "
        "visible direct scalar action merely because action_type is an alias. "
        if request.suggested_tool_name == "prepare_direct_contact_action_args"
        else ""
    )
    location_arg_guidance = (
        "For prepare_specific_location_search_args repairs, do not use missing "
        "reminder time as an abstention gate. This generated tool only prepares "
        "read-only search_location_around_lat_lon arguments from visible place text. "
        "If a specific qualified place phrase is visible, return a downstream location search "
        "plan even for reminder requests that lack a date/time; the actor handles "
        "missing reminder time before any later mutating add_reminder action. "
        "The Python function signature should only require user_request and "
        "location_phrase. Do not add latitude or longitude to this specific-place "
        "tool. For any successful visible specific place, return "
        "search_location_around_lat_lon with exactly {'location': location_query}. "
        "Only return missing_location_phrase when no visible place can be extracted. "
        if request.suggested_tool_name == "prepare_specific_location_search_args"
        else ""
    )
    broad_location_arg_guidance = (
        "For prepare_broad_location_search_args repairs, keep the tool small. "
        "The Python signature must include user_request: str, location_phrase: "
        "str, latitude: float = 0.0, and longitude: float = 0.0. If the cleaned "
        "query contains ' on ' or street, road, avenue, bridge, airport, creek, "
        "market, center, mall, plaza, downtown, north, south, east, or west, "
        "return not_broad_location_phrase with should_call_downstream_tool false. "
        "If the query is broad and coordinates are missing or zero, return "
        "downstream_tool_name get_current_location with search_location_kwargs "
        "{} and downstream_tool_kwargs {}. If broad coordinates are nonzero, "
        "return search_location_around_lat_lon with location, latitude, and "
        "longitude in both kwargs dicts. Avoid regex strings with embedded "
        "quotes; simple lowercase string checks are enough. "
        if request.suggested_tool_name == "prepare_broad_location_search_args"
        else ""
    )
    service_extraction_guidance = (
        "For extract_service_answer_field repairs, the spec must preserve the "
        "original producer tools in required_original_tool_calls and "
        "preserves_side_effect_tools. The helper must not call services; it only "
        "extracts visible fields from service_payload. If the error is "
        "missing_downstream_tool_preservation, repair the spec metadata and keep "
        "the code pure. When answer_value is unavailable, return a nonempty "
        "abstain_reason instead of an empty successful answer. "
        if request.suggested_tool_name == "extract_service_answer_field"
        else ""
    )
    action_selector_guidance = (
        "For select_action_target_by_recency repairs, if the EXPECTED object has "
        "selected_id from sender_person_id, recipient_person_id, or person_id, "
        "copy that same nonblank id into selected_id and "
        "downstream_tool_kwargs['person_id']. For modify actions, merge every "
        "nonblank update field with the selected id; never return person_id ''. "
        if request.suggested_tool_name == "select_action_target_by_recency"
        else ""
    )
    message_content_guidance = (
        "For select_message_content_by_recency repairs, avoid tuple-pair "
        "dedupe structures. Keep deduped_records and deduped_indices as parallel "
        "lists, build tied_positions as integer indexes into deduped_records, and "
        "never iterate 'for index, record in deduped_records' because each record "
        "is a dictionary. A ValueError about too many values to unpack means the "
        "repair must replace pair unpacking with index-based access. Every return "
        "branch must include copy_exactly. Successful latest and oldest branches "
        "must set copy_exactly true; abstain branches must set copy_exactly false. "
        "Do not substitute the word latest in final-answer text: for latest mode "
        "the exact phrase is \"Your most recent message says '<content>'.\" and "
        "for oldest mode the exact phrase is \"Your oldest message says '<content>'.\" "
        "If validation shows only copy_exactly or final-answer wording mismatches, "
        "patch those fields without changing the selection algorithm. "
        if request.suggested_tool_name == "select_message_content_by_recency"
        else ""
    )
    timestamp_bounds_guidance = (
        "CRITICAL resolve_search_window_or_bounds repair rule: do not choose one "
        "timestamp prefix for the whole function and do not derive the prefix from "
        "target_domain. Branch on timestamp_intent for each call: "
        "creation and message_creation require creation_timestamp_* keys; "
        "reminder requires reminder_timestamp_* keys. The validation examples may "
        "include both intents, so passing one example by hard-setting the other "
        "prefix will fail the next example. If the phrase says upcoming, later, "
        "due later, next reminder, or next todo, treat the request as upcoming "
        "even when direction was supplied as latest or most recent; upcoming uses "
        "reminder_timestamp_lowerbound=current_timestamp. "
        if request.suggested_tool_name == "resolve_search_window_or_bounds"
        else ""
    )
    return (
        timestamp_bounds_guidance
        + _model_authored_generation_prompt(
            request, candidate_count_override=repair_candidate_count
        )
        + " Repair strategy "
        + str(strategy_number)
        + ": "
        + strategy_guidance
        + " "
        + " The previous model-authored candidate failed deterministic validation. "
        "Repair the same tool without changing the intended capability, suggested "
        "tool name, or safety limits. If the failure is semantic rather than "
        "syntax/code-shape, preserve branches and fields that already match the "
        "expected objects and patch only the mismatching branch conditions or "
        "return fields. If the failure is syntax/code-shape, rewrite the function "
        "implementation from the public contract, contract_rules, and validation "
        "errors. "
        "The validation error format is ACTUAL!=EXPECTED; "
        "the object after != is the exact expected output. Revise the spec and "
        "code_lines so every failing case returns the EXPECTED object exactly, "
        "including booleans, empty strings, empty dictionaries/lists, None/null, "
        "and answer text. If a mismatch is in actor-facing text, infer the "
        "reusable template from the EXPECTED object and fill it from input or "
        "record fields; do not invent alternate wording. If the same mismatch "
        "appears in consecutive repair attempts, change the relevant branch so "
        "the actual value moves to the expected value shown after != while "
        "keeping previously correct cases correct. Do not add side effects, "
        "imports, try/except, hidden "
        "state, filesystem access, network access, subprocess calls, classes, "
        "lambdas, while loops, or raise statements. Treat optional dict or list inputs as "
        "empty dict/list when they are None or the wrong type before calling .get, "
        "indexing, or iterating. Return valid JSON only, preferably using "
        "code_lines instead of a raw code string. "
        + syntax_guidance
        + semantic_rewrite_guidance
        + state_sequence_guidance
        + status_lookup_guidance
        + relationship_batch_guidance
        + direct_contact_guidance
        + location_arg_guidance
        + broad_location_arg_guidance
        + service_extraction_guidance
        + action_selector_guidance
        + message_content_guidance
        + "Validation errors: "
        + json.dumps(list(errors), sort_keys=True)
        + ". Previous candidate JSON: "
        + json.dumps(previous_candidate, sort_keys=True)
    )


def _with_native_action_update_contract(
    request: ToolGenerationRequest,
    inputs: tuple[ToolInput, ...],
) -> tuple[ToolInput, ...]:
    """Describe update keys from the public native-action function signature."""

    if not any(item.name == "updates" for item in inputs):
        return inputs
    action_names = _request_native_action_names(request)
    writable: set[str] = set()
    for action_name in action_names:
        native_function = native_side_effect_tools().get(action_name)
        if native_function is None:
            continue
        writable.update(
            name
            for name, parameter in inspect.signature(native_function).parameters.items()
            if not name.endswith("_id")
            and parameter.kind
            not in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}
        )
    if not writable:
        return inputs
    allowed = ", ".join(sorted(writable))
    suffix = (
        f" Keys must exactly match writable approved native-action parameters: "
        f"{allowed}. Never include a key ending in _id; target identity comes only "
        "from the uniquely selected visible record. Do not use role-prefixed record "
        "fields as update keys."
    )
    return tuple(
        replace(item, description=item.description.rstrip() + suffix)
        if item.name == "updates" and suffix.strip() not in item.description
        else item
        for item in inputs
    )


def _model_authored_tool_specific_guidance(request: ToolGenerationRequest) -> str:
    """Add public-contract guidance for known tool contracts without emitting code."""

    if _request_complete_tools_enabled(request):
        # Helper-contract guidance (should_call/prepare/preserve) would override
        # the complete-tools instruction; suppress it so the tool performs the
        # state change itself.
        return ""

    if request.suggested_tool_name == "plan_contact_lookup_query":
        return (
            "For plan_contact_lookup_query, treat this as a two-phase contact "
            "lookup/answer contract. Before a contact record is visible, return "
            "should_call_search_contacts true and search_contacts_kwargs built "
            "from the visible lookup key. If selected_record is a non-empty dict, "
            "the original search has already happened, so should_call_search_contacts "
            "must be false for every selected-record case. After selected_record "
            "is visible, preserve search_contacts_kwargs, copy selected_record "
            "exactly, set answer_value to selected_record[answer_field], and set "
            "copy_exactly true when final_answer_recommendation is non-empty. "
            "For relationship answers after a phone-number lookup, the final "
            "answer template is phone_number + ' is your ' + answer_value, not "
            "the record name. For phone-number answers after a name lookup, the "
            'final answer template is contact_name + "\'s phone number is " + '
            "answer_value; keep the apostrophe after the visible contact name "
            "exactly. For name answers after a relationship lookup, use 'Your ' "
            "+ relationship + ' is ' + answer_value. For person_id target "
            "lookups, leave final_answer_recommendation empty because the actor "
            "will use the id in a preserved side-effect tool. If no "
            "selected_record is visible and the tool is still preparing a search, "
            "final_answer_recommendation must be empty and copy_exactly false. "
            "Avoid single-quoted f-strings for final_answer_recommendation. Use "
            "double-quoted string literals or string concatenation when the text "
            "contains a possessive apostrophe. "
        )
    if request.suggested_tool_name == "prepare_safe_action_or_abstain":
        return (
            "For prepare_safe_action_or_abstain, compute semantic requirements from "
            "the visible request instead of trusting malformed required_original_tools. "
            "A send/text/message request to a named recipient needs both contact_lookup "
            "and message_send unless target_identifier already looks like a concrete "
            "phone number. If contact_lookup is unavailable, should_abstain must be "
            "true and final_answer_recommendation should say the recipient cannot be "
            "resolved to a phone number with the available information/tools. Do not "
            "return continue_with_original_tool for a named-recipient send merely "
            "because message_send is available. Treat string required_original_tools "
            "and available_original_tools values as single capabilities, not "
            "character lists. A blank contact/reminder action target must abstain with "
            "missing_target_identifier. More than one visible matching record must "
            "abstain with unique_target_identifier and ambiguous_target. The generated "
            "function itself must satisfy these branches without relying on output "
            "normalization to repair its result. "
        )
    if request.suggested_tool_name == "prepare_reminder_creation_args":
        return (
            "For prepare_reminder_creation_args, keep reminder content, time, and "
            "location state separate. Use resolved_reminder_timestamp directly "
            "when present and set timestamp_source to resolved. For relative "
            "local time, use current_timestamp plus the difference from the "
            "current local day/time to day_offset/hour/minute; do not add timezone "
            "offset twice. When current_datetime_info is visible, compute local "
            "midnight as int(current_timestamp) minus current hour*3600, current "
            "minute*60, and current second, then add day_offset*86400 plus target "
            "hour*3600 plus target minute*60. This intentionally removes current "
            "seconds and fractional seconds so a request for 5:00 PM returns an "
            "exact top-of-minute timestamp, not 5:00 plus the current seconds. "
            "If relative fields are present but current_datetime_info is missing "
            "and no explicit resolved timestamp is available, abstain with "
            "missing_current_datetime_info_call_timestamp_to_datetime_info. "
            "Apply location gates before creating kwargs: a required unresolved "
            "location returns required_location_unresolved; an optional requested "
            "location with no available coordinates and no failed lookup returns "
            "optional_location_lookup_pending_do_not_call_add_reminder, even when "
            "a timestamp is already resolved. Omit latitude and longitude unless "
            "location_available is true and concrete non-placeholder coordinates "
            "are visible. If an "
            "optional location is requested but lookup is still pending, return "
            "should_call_add_reminder false, add_reminder_kwargs {}, "
            "location_status lookup_pending, and the exact abstain reason from "
            "the expected object. If optional location lookup failed, allow the "
            "reminder without coordinates. If required location is missing, "
            "abstain. When coordinates are included, remove a trailing place "
            "phrase from the reminder content so the content does not duplicate "
            "the searched location; common trailing forms include ' at PLACE', "
            "' near PLACE', ' in PLACE', and ' by PLACE'. If coordinates are not "
            "included, keep the content unchanged unless the expected object "
            "shows otherwise. "
        )
    if request.suggested_tool_name == "relative_day_time_to_timestamp":
        return (
            "For relative_day_time_to_timestamp, compute a Unix timestamp for a "
            "local target day and clock time from current_timestamp, current local "
            "datetime fields, day_offset, hour, minute, and local UTC offset. The "
            "tool must never raise for incomplete actor arguments; return 0.0 "
            "when current_timestamp, day_offset, hour, minute, or "
            "current_datetime_info is missing, None, or malformed. The "
            "first executable validation branch must explicitly reject a "
            "current_datetime_info value that is not a dict, is empty, omits "
            "hour/minute/second, or contains None for any required field. Do not "
            "replace missing producer fields with zero through dict.get defaults. The "
            "result is current_timestamp plus the local elapsed seconds between "
            "the current local date/time and the target local date/time. When "
            "current_datetime_info is present, compute local midnight as "
            "int(current_timestamp) minus current hour*3600, current minute*60, "
            "and current second, then add day_offset*86400 plus target hour*3600 "
            "plus target minute*60. Do not preserve current seconds or fractional "
            "seconds in the result. Do not shift the result by the UTC offset "
            "after computing that delta. "
        )
    if request.suggested_tool_name == "next_weekday_time_to_timestamp":
        return (
            "For next_weekday_time_to_timestamp, current_timestamp is already the "
            "absolute Unix timestamp for the visible current local datetime fields. "
            "Never return current_timestamp + target_hour_seconds. First compute "
            "local_midnight_timestamp = int(current_timestamp) - "
            "(current_hour*3600 + current_minute*60 + current_second) using "
            "current_datetime_info. Then choose days_ahead from the current "
            "isoweekday to target_isoweekday. If days_ahead is 0 and the target "
            "hour/minute is not strictly after the current hour/minute/second, "
            "set days_ahead to 7. Return float(local_midnight_timestamp + "
            "days_ahead*86400 + hour*3600 + minute*60). Do not add timezone "
            "offset after this calculation and do not preserve the current "
            "seconds or fractional current_timestamp. "
        )
    if request.suggested_tool_name == "prepare_specific_location_search_args":
        return (
            "For prepare_specific_location_search_args, handle specific visible "
            "place phrases only. Return search_location_kwargs, "
            "should_call_downstream_tool, downstream_tool_name, "
            "downstream_tool_kwargs, location_query, and abstain_reason. Treat "
            "location_phrase as the already isolated visible place phrase. When "
            "location_phrase is nonblank, clean and use it as the query exactly; "
            "do not replace it with text from a full reminder/task user_request. "
            "Use user_request extraction only when location_phrase is blank or "
            "when user_request itself is only a standalone place phrase. Clean "
            "location_phrase by trimming whitespace and a leading location "
            "preposition such as at, near, around, in, or by. Preserve venue, "
            "street, neighborhood, and qualifier text exactly. Do not return "
            "missing_reminder_time_before_location_lookup; missing reminder time "
            "belongs to the actor's later side-effect decision, not this read-only "
            "location argument tool. "
            "If there is no visible place, return missing_location_phrase. On "
            "specific-place success, downstream_tool_name is "
            "search_location_around_lat_lon and both kwargs dicts are exactly "
            "{'location': location_query}. Do not include latitude or longitude "
            "in this specific-place tool; broad unqualified location names are "
            "handled by prepare_broad_location_search_args."
        )
    if request.suggested_tool_name == "prepare_broad_location_search_args":
        return (
            "For prepare_broad_location_search_args, write a small branch-only "
            "argument planner. Signature: user_request: str, location_phrase: str, "
            "latitude: float = 0.0, longitude: float = 0.0. Clean query from "
            "location_phrase first. This tool applies only to broad unqualified "
            "place names. If query contains ' on ' or street/road/avenue/bridge/"
            "airport/creek/market/center/mall/plaza/downtown/directional "
            "qualifier words, return not_broad_location_phrase with no downstream "
            "call. For broad query with missing or zero coordinates, return "
            "get_current_location and empty kwargs. For broad query with nonzero "
            "coordinates, return search_location_around_lat_lon and include "
            "location, latitude, and longitude in both kwargs dicts. Do not use "
            "regular expressions; simple lowercase checks are enough."
        )
    if request.suggested_tool_name == "plan_message_counterparty_search":
        return (
            "For plan_message_counterparty_search, every return object must "
            "include exactly the public contract keys, including should_call_tool. "
            "Use this branch order. First normalize direction aliases: sent, "
            "outgoing, and from_me become sent; received, incoming, and to_me "
            "become received. Normalize selection_mode to latest or oldest. If "
            "messages is a non-empty list, select latest or oldest by numeric "
            "creation_timestamp, then identify the counterparty phone. If "
            "self_person_id is visible, the counterparty is the message side "
            "whose person_id is not self_person_id. Otherwise for received "
            "messages use sender_phone_number; for sent messages use "
            "recipient_phone_number. Return phase answer_ready, "
            "should_call_tool false, should_call_search_contacts false, "
            "should_call_search_messages false, exact_final_answer and "
            "final_answer_recommendation from the expected text pattern. If no "
            "messages are visible and self_person_id is blank, return phase "
            "self_lookup_required with should_call_search_contacts true and "
            "search_contacts_kwargs {'is_self': True}. If no messages are visible "
            "and self_person_id is present, return phase message_search_required "
            "with should_call_search_messages true. Use sender_person_id for sent "
            "and recipient_person_id for received. Add content to "
            "search_messages_kwargs only when content_keyword is nonblank. "
            "Preserve expected message_direction labels exactly; for outgoing "
            "the expected normalized label is sent. Do not abstain merely because "
            "messages is empty when self_person_id is present; that is the search "
            "planning branch, not a no_messages branch. "
        )
    if request.suggested_tool_name == "plan_contact_relationship_batch_update":
        return (
            "For plan_contact_relationship_batch_update, preserve the original "
            "ToolSandbox side-effect path. The spec must list search_contacts "
            "and modify_contact in both required_original_tool_calls and "
            "preserves_side_effect_tools, with a nonempty final_state_preservation_plan. "
            "The function must accept user_request: str, source_relationship: str, "
            "target_relationship: str, and contacts: list. Every return object "
            "must include exactly these public contract keys: phase, "
            "source_relationship, target_relationship, should_call_search_contacts, "
            "search_contacts_kwargs, selected_contacts, downstream_tool_name, "
            "downstream_tool_kwargs_list, should_call_tools, abstain_reason, and "
            "final_answer_recommendation. Echo the normalized source_relationship "
            "and target_relationship in every branch, including abstain branches. "
            "A returned dict missing source_relationship or target_relationship is invalid. "
            "Prefer a single local output/result helper that always writes all public "
            "contract keys exactly once, then call it from every branch. "
            "Before contacts are visible, return phase 'search_required', "
            "should_call_search_contacts true, downstream_tool_name '', "
            "downstream_tool_kwargs_list [], should_call_tools false, "
            "abstain_reason '', and final_answer_recommendation ''. For ordinary "
            "source relationships, search_contacts_kwargs must be exactly "
            "{'relationship': source_relationship}. Treat __all_contacts__, all, "
            "everyone, and contacts as all-contacts sources and use "
            "search_contacts_kwargs exactly {'is_self': False}; do not use empty "
            "search kwargs for this branch. After contacts are visible, select "
            "each non-self contact whose current relationship matches the source "
            "relationship unless the source is all-contacts. If a visible contact "
            "record has person_id but omits relationship, treat it as an "
            "actor-selected contact from the current request and keep it eligible "
            "instead of abstaining. Normalize visible relationship values by "
            "stripping whitespace, lowercasing, and treating a simple trailing "
            "plural s as equivalent; friend and friends match, enemy and enemies "
            "match. Skip contacts "
            "already at the target relationship. For all-contacts, a visible "
            "non-self contact needing change is a positive match even if its "
            "relationship does not match source_relationship; do not abstain with "
            "no matching contacts while any non-self visible contact still needs "
            "the target relationship. Return phase "
            "'modify_required', downstream_tool_name 'modify_contact', "
            "downstream_tool_kwargs_list with one dict per selected contact "
            "containing person_id and relationship, and should_call_tools true. "
            "Never call search_contacts or modify_contact inside the generated "
            "function. Abstain on missing target_relationship, missing "
            "source_relationship, source equal to target, no contacts, no "
            "matching contacts, no contacts needing change, or records missing "
            "person_id; do not treat a missing relationship field as a missing "
            "person_id. On every branch, set final_answer_recommendation to an "
            "empty string. The generated tool is only a side-effect planner; "
            "after original modify_contact calls complete, the actor can answer "
            "the user in its own words. Use only visible inputs and returned "
            "contact records. Write simple Python loops and branch returns only; "
            "avoid nested comprehensions and avoid long one-line list/dict literals "
            "so code_lines remain syntactically complete. "
        )
    if request.suggested_tool_name == "resolve_search_window_or_bounds":
        return (
            "For resolve_search_window_or_bounds, return the original search tool "
            "name and exact search kwargs from public examples. For direction "
            "yesterday, compute center = current_timestamp - 86400, lower = "
            "center - 120, upper = center + 120. Use creation_timestamp_* keys "
            "whenever timestamp_intent is exactly creation, even when target_domain "
            "is reminder; use reminder_timestamp_* keys only when timestamp_intent "
            "is exactly reminder. Use creation_timestamp_* keys for message_creation. "
            "When phrase contains a clear bounded recency word such as yesterday, "
            "today, later today, or upcoming, that phrase-derived direction must "
            "override generic direction values such as latest, recent, or empty. "
            "Do not abstain merely because direction is generic when phrase gives "
            "a supported bounded window. "
            "For direction today with reminder intent, compute "
            "local day bounds from current_timestamp: lower is the current day's "
            "midnight timestamp and upper is lower + 86399. For upcoming, use "
            "reminder_timestamp_lowerbound = current_timestamp. If phrase says "
            "upcoming, later, due later, next reminder, or next todo, upcoming "
            "wins over latest/most recent because it is a due-time lower-bound "
            "request. For latest or "
            "most recent, set an upper bound at current_timestamp; if lookback_days "
            "is positive, also set lowerbound = current_timestamp - "
            "lookback_days*86400. target_domain message uses search_messages and "
            "creation_timestamp_* keys; target_domain reminder uses "
            "search_reminder. Copy content_keyword into search kwargs as content "
            "only when it is nonblank. Return missing_current_timestamp when "
            "current_timestamp is 0 or missing. "
        )
    if request.suggested_tool_name == "select_action_target_by_recency":
        return (
            "For select_action_target_by_recency, return exactly these public "
            "contract keys on every branch: selected_record, selected_index, "
            "selected_id, selected_timestamp, action_type, downstream_tool_name, "
            "downstream_tool_kwargs, should_call_tool, tie_candidates, "
            "abstain_reason, and safety_notes. Treat records that are not lists "
            "as empty lists, constraints that are not dicts as {}, and updates "
            "that are not dicts as {}. Select by numeric timestamp_key using "
            "latest/highest or oldest/lowest. Apply constraints before ranking; "
            "a record satisfies a nonempty constraint only when str(record[key]) "
            "equals str(value). If multiple records share the selected timestamp, "
            "abstain with selected_index -1, selected_record {}, selected_id '', "
            "selected_timestamp set to the tied timestamp, should_call_tool "
            "false, and tie_candidates containing every tied record. For "
            "remove_reminder and modify_reminder, selected_id and downstream "
            "kwargs use reminder_id. Remove actions can call the "
            "downstream tool with only the id. Modify actions must merge the "
            "selected id with updates and abstain if updates is empty. Never call "
            "the original search, modify, remove, send, or add tool inside this "
            "generated function; only return the preserved downstream call plan. "
            "On every successful branch, safety_notes is exactly 'call ' + "
            "downstream_tool_name + ' with downstream_tool_kwargs'. On ambiguity, "
            "safety_notes is exactly 'do not guess before side-effect action'. "
        )
    if request.suggested_tool_name != "prepare_location_search_args":
        return ""
    return (
        "For the location-search argument tool, treat this as a specific visible "
        "place-phrase extraction and downstream-argument preparation contract. "
        "Use only visible user_request and location_phrase; latitude and "
        "longitude are outside this narrowed generated-tool contract. The "
        "location phrase is place text only; date/time/reminder scheduling words "
        "are not part of the location query. Strip trailing or embedded temporal "
        "fragments such as today, tomorrow, tonight, yesterday, next week, this "
        "week, weekday names, at/by/around/before/after followed by a clock time, "
        "AM/PM clock expressions, and trailing punctuation such as periods or "
        "commas. Preserve venue, street, road, avenue, city, neighborhood, and "
        "qualifier text that belongs to the place. If user_request is a "
        "standalone place phrase with no reminder/task wording, the full stripped "
        "request is the location query even when location_phrase is blank. Missing "
        "reminder date/time is handled before the later mutating reminder action, "
        "not by this read-only location-argument tool. If there is no place text, return "
        "missing_location_phrase. Do not treat a standalone date/time expression "
        "as a place. Use this ordered algorithm in the generated code: first "
        "clean strings by trimming whitespace and trailing punctuation while "
        "preserving original case; second detect whether user_request is a "
        "reminder/task request and whether it contains time evidence such as "
        "today, tomorrow, tonight, next, a weekday/month name, AM/PM, a colon "
        "time, or a numeric clock expression; third extract request_place from "
        "the text after the last real location preposition among ' at ', "
        "' near ', ' around ', ' in ', and ' by '; ignore an ' at ' occurrence "
        "that introduces a clock time such as 'at 5 PM' when a later location "
        "preposition exists, then remove trailing punctuation and time "
        "fragments; fourth start with cleaned location_phrase, but replace "
        "it with request_place when request_place is longer or contains the "
        "phrase tokens, and if no phrase exists and the request is a standalone "
        "place query rather than a reminder/task, use the full cleaned request; "
        "fifth, if the resulting query is blank or time-only, return "
        "missing_location_phrase; sixth, for "
        "qualified/specific place queries return search_location_around_lat_lon "
        "with the location only. For that final branch, search_location_kwargs "
        "and downstream_tool_kwargs are the same dict {'location': query}, "
        "downstream_tool_name is search_location_around_lat_lon, "
        "should_call_downstream_tool is true, and abstain_reason is empty. "
        "Do not return get_current_location from this narrowed contract and do "
        "not include latitude or longitude in the kwargs. "
    )


def _normalize_model_authored_tool(
    request: ToolGenerationRequest, tool: GeneratedTool
) -> GeneratedTool:
    """Fill underspecified metadata from public birth evidence, not tool code."""

    spec = tool.spec
    normalized_code = tool.code
    evidence = spec.inadequacy_evidence
    replacement_evidence = _request_evidence(
        request,
        summary=request.observation or "Visible task context showed a reusable gap.",
        signals=("visible_context_gap",),
    )
    updates: dict[str, Any] = {}
    complete_tools = _request_complete_tools_enabled(request)
    if complete_tools:
        updates["native_action_delegation"] = True
        cleaned_summary = _native_action_behavior_summary(request).strip()
        updates["inadequacy_evidence"] = StructuredInadequacyEvidence(
            summary=(
                cleaned_summary
                or "Visible task evidence requires one validated native action."
            ),
            signals=evidence.signals or replacement_evidence.signals,
            failed_tool_calls=tuple(
                dict.fromkeys(
                    (
                        *evidence.failed_tool_calls,
                        *_request_native_action_names(request),
                    )
                )
            ),
            repeated_failed_tool_calls=evidence.repeated_failed_tool_calls,
            visible_data_gaps=evidence.visible_data_gaps,
            planner_failures=evidence.planner_failures,
            final_answer_route_mismatch=evidence.final_answer_route_mismatch,
        )
        updates["reason_tool_is_decisive"] = (
            "The generated tool maps visible inputs to one validated native action "
            "or a validation-proven abstention."
        )
        updates["final_state_preservation_plan"] = (
            "Delegate exactly one approved action to the preserved native "
            "ToolSandbox implementation; negative cases call no native action."
        )
    if len(spec.description.strip()) < 10:
        updates["description"] = request.observation or (
            "Deterministic generated tool for a visible recurring task gap."
        )
    inferred_inputs = _infer_inputs_from_examples(request)
    if inferred_inputs:
        authored_inputs = {item.name: item for item in spec.inputs}
        inferred_inputs = tuple(
            replace(
                item,
                description=_merged_visible_input_description(
                    authored_inputs.get(item.name), item.description
                ),
            )
            for item in inferred_inputs
        )
        if tuple((item.name, item.annotation) for item in spec.inputs) != tuple(
            (item.name, item.annotation) for item in inferred_inputs
        ):
            updates["inputs"] = inferred_inputs
        normalized_code = _align_model_authored_function_signature(
            normalized_code,
            spec.tool_name,
            inferred_inputs,
        )
    if complete_tools:
        effective_inputs = tuple(updates.get("inputs", spec.inputs))
        enriched_inputs = _with_native_action_update_contract(request, effective_inputs)
        if enriched_inputs != effective_inputs:
            updates["inputs"] = enriched_inputs
    if not complete_tools and (
        len(evidence.summary.strip()) < 20 or not evidence.signals
    ):
        updates["inadequacy_evidence"] = replacement_evidence
    if len(spec.generalization_rationale.strip()) < 20:
        updates["generalization_rationale"] = (
            "Generated from recurring public validation examples and visible "
            "task evidence so the same deterministic transformation can be reused."
        )
    if not complete_tools and len(spec.reason_tool_is_decisive.strip()) < 20:
        updates["reason_tool_is_decisive"] = (
            "The tool turns visible task constraints into deterministic arguments "
            "or abstention signals before the actor chooses the preserved action."
        )
    if spec.estimated_step_compression is None:
        updates["estimated_step_compression"] = 3
    elif spec.estimated_step_compression < 3:
        updates["estimated_step_compression"] = 3
    if spec.cross_task_applicability_count is None:
        updates["cross_task_applicability_count"] = 2
    elif spec.cross_task_applicability_count < 2:
        updates["cross_task_applicability_count"] = 2
    default_families = MODEL_AUTHORED_DEFAULT_FAMILIES_BY_TOOL.get(
        spec.tool_name
    ) or MODEL_AUTHORED_DEFAULT_FAMILIES_BY_TOOL.get(request.suggested_tool_name or "")
    if "prepare_broad_location_search_args" in {
        spec.tool_name,
        request.suggested_tool_name or "",
    }:
        default_families = MODEL_AUTHORED_DEFAULT_FAMILIES_BY_TOOL[
            "prepare_broad_location_search_args"
        ]
    generic_families = {
        "canonicalizer",
        "derived_value_calculator",
        "state_precondition_helper",
        "search_filter_ranking_helper",
        "composite_workflow_helper",
        "validation_abstention_helper",
        "helper",
        "search_filter",
        "state_precondition",
        "timestamp_conversion",
    }
    if default_families and (
        len(spec.applicable_task_families) < 2
        or any(
            family.strip().lower() in generic_families
            for family in spec.applicable_task_families
        )
    ):
        updates["applicable_task_families"] = default_families
    default_original_calls = MODEL_AUTHORED_DEFAULT_ORIGINAL_CALLS_BY_TOOL.get(
        spec.tool_name
    ) or MODEL_AUTHORED_DEFAULT_ORIGINAL_CALLS_BY_TOOL.get(
        request.suggested_tool_name or ""
    )
    if "prepare_broad_location_search_args" in {
        spec.tool_name,
        request.suggested_tool_name or "",
    }:
        default_original_calls = MODEL_AUTHORED_DEFAULT_ORIGINAL_CALLS_BY_TOOL[
            "prepare_broad_location_search_args"
        ]
    if _request_complete_tools_enabled(request):
        default_original_calls = tuple(
            dict.fromkeys(
                (*default_original_calls, *_request_native_action_names(request))
                if default_original_calls
                else _request_native_action_names(request)
            )
        )
    if default_original_calls:
        if not spec.required_original_tool_calls:
            updates["required_original_tool_calls"] = default_original_calls
        if not spec.preserves_side_effect_tools:
            updates["preserves_side_effect_tools"] = default_original_calls
    if not spec.positive_triggers:
        updates["positive_triggers"] = tuple(replacement_evidence.signals) or (
            "visible_reusable_gap",
        )
    if not spec.negative_triggers:
        updates["negative_triggers"] = (
            "insufficient_visible_information",
            "ambiguous_visible_match",
            "missing_required_input",
        )
    if not spec.shortfall_cluster_evidence:
        cluster = request.shortfall_cluster_context or {}
        cluster_label = str(
            cluster.get("cluster_id")
            or cluster.get("failure_mechanism")
            or request.suggested_tool_name
            or "visible_context_shortfall"
        )
        updates["shortfall_cluster_evidence"] = (cluster_label,)
    if not spec.known_failure_mechanisms_addressed:
        updates["known_failure_mechanisms_addressed"] = (
            request.suggested_tool_name or "visible_context_gap",
        )
    inferred_schema = (
        {}
        if _request_complete_tools_enabled(request)
        else _infer_output_schema_from_examples(request)
    )
    if _request_complete_tools_enabled(request):
        updates["output_schema"] = {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["success", "abstain"]},
                "confirmation": {"type": "string"},
                "abstain_reason": {"type": "string"},
                "native_action": {"type": "string"},
                "native_result": {},
            },
            "required": [
                "status",
                "confirmation",
                "abstain_reason",
                "native_action",
            ],
            "additionalProperties": True,
        }
    if inferred_schema:
        current_schema = (
            spec.output_schema if isinstance(spec.output_schema, dict) else {}
        )
        current_props = current_schema.get("properties", {})
        current_props = current_props if isinstance(current_props, dict) else {}
        needs_schema = not current_props
        if spec.family == ToolFamily.COMPOSITE_WORKFLOW_HELPER and not any(
            str(key).endswith("_kwargs") for key in current_props
        ):
            needs_schema = True
        if needs_schema:
            updates["output_schema"] = _merge_output_schemas(
                current_schema, inferred_schema
            )
    tool_name_enum = MODEL_AUTHORED_OUTPUT_TOOL_NAME_ENUM_BY_TOOL.get(
        spec.tool_name
    ) or MODEL_AUTHORED_OUTPUT_TOOL_NAME_ENUM_BY_TOOL.get(
        request.suggested_tool_name or ""
    )
    if tool_name_enum:
        emitted_original_tools = tuple(item for item in tool_name_enum if item)
        if emitted_original_tools:
            required_calls = tuple(
                dict.fromkeys(
                    (*spec.required_original_tool_calls, *emitted_original_tools)
                )
            )
            preserved_calls = tuple(
                dict.fromkeys(
                    (*spec.preserves_side_effect_tools, *emitted_original_tools)
                )
            )
            updates["required_original_tool_calls"] = required_calls
            updates["preserves_side_effect_tools"] = preserved_calls
        if spec.family == ToolFamily.STATE_PRECONDITION_HELPER:
            description = spec.description.strip()
            state_contract_text = (
                " Returns the original ToolSandbox setter tool_name and arguments "
                "for the single next action or abstains when no visible state "
                "precondition action is safe."
            )
            if (
                "setter" not in description.lower()
                or "tool_name" not in description.lower()
            ):
                updates["description"] = (description + state_contract_text).strip()
        schema_source = updates.get("output_schema", spec.output_schema)
        schema = dict(schema_source) if isinstance(schema_source, dict) else {}
        props_source = schema.get("properties", {})
        props = dict(props_source) if isinstance(props_source, dict) else {}
        props["tool_name"] = {"type": "string", "enum": list(tool_name_enum)}
        schema["type"] = schema.get("type") or "object"
        schema["properties"] = props
        updates["output_schema"] = schema
    if updates:
        spec = replace(spec, **updates)
    if normalized_code == tool.code and spec == tool.spec:
        return tool
    return replace(tool, spec=spec, code=normalized_code)


def _align_model_authored_function_signature(
    code: str,
    tool_name: str,
    inputs: tuple[ToolInput, ...],
) -> str:
    """Align model-authored function shape with the public validation contract."""

    if not inputs:
        return code
    try:
        module = ast.parse(code)
    except SyntaxError:
        return code
    functions = [node for node in module.body if isinstance(node, ast.FunctionDef)]
    if len(functions) != 1:
        return code
    fn = functions[0]
    if fn.args.vararg is not None or fn.args.kwarg is not None:
        return code
    defaults_by_name: dict[str, ast.expr | None] = {}
    positional = fn.args.args
    defaults = list(fn.args.defaults)
    first_default = len(positional) - len(defaults)
    for index, arg in enumerate(positional):
        default_index = index - first_default
        defaults_by_name[arg.arg] = (
            defaults[default_index] if default_index >= 0 else None
        )
    new_args: list[ast.arg] = []
    new_defaults: list[ast.expr] = []
    any_default = False
    for item in inputs:
        annotation = ast.Name(id=item.annotation, ctx=ast.Load())
        new_args.append(
            ast.arg(arg=item.name, annotation=annotation, type_comment=None)
        )
        default = defaults_by_name.get(item.name)
        if default is None:
            default = _model_authored_optional_input_default(tool_name, item)
        if default is None and any_default:
            default = ast.Constant(value=None)
        if default is not None:
            any_default = True
            new_defaults.append(default)
    if any_default and len(new_defaults) < len(new_args):
        missing = len(new_args) - len(new_defaults)
        new_defaults = [ast.Constant(value=None) for _ in range(missing)] + new_defaults
    fn.name = tool_name
    fn.args.args = new_args
    fn.args.defaults = new_defaults
    ast.fix_missing_locations(module)
    try:
        return ast.unparse(module) + "\n"
    except Exception:
        return code


def _model_authored_optional_input_default(
    tool_name: str, item: ToolInput
) -> ast.expr | None:
    """Return a safe default for optional generated-tool inputs.

    The generation model often writes useful logic but omits defaults for
    optional contract fields. Adding defaults here preserves the model-authored
    body while keeping the public callable contract usable when examples or actor
    calls provide only the required visible inputs.
    """

    optional_by_tool: dict[str, dict[str, Any]] = {
        "extract_service_answer_field": {
            "requested_unit": "",
            "answer_subject": "",
        },
        "extract_converted_amount_result": {
            "requested_unit": "",
        },
        "extract_phone_number_result": {
            "answer_subject": "",
        },
        "extract_distance_result": {
            "requested_unit": "",
            "answer_subject": "",
        },
        "extract_temperature_result": {
            "requested_unit": "",
            "answer_subject": "",
        },
        "select_action_target_by_recency": {
            "timestamp_key": "",
            "selection_mode": "latest",
            "action_type": "",
            "constraints": {},
            "updates": {},
            "self_person_id": "",
            "reference_timestamp": 0.0,
        },
        "plan_device_state_action_sequence_v3": {
            "visible_state_or_error": "",
            "visible_state_summary": "",
            "available_tools": [],
        },
        "plan_device_state_action_sequence_location_recovery": {
            "visible_state_or_error": "",
            "visible_state_summary": "",
            "available_tools": [],
        },
        "plan_contact_relationship_batch_update": {
            "contacts": [],
        },
        "prepare_holiday_search_args": {
            "visible_current_year": 0,
        },
        "prepare_direct_contact_action_args": {
            "action_type": "",
            "contact_name": "",
            "phone_number": "",
            "relationship": "",
            "record_id": "",
            "target_field": "",
            "new_value": "",
            "message_text": "",
            "user_request": "",
        },
        "prepare_safe_action_or_abstain": {
            "target_identifier": "",
            "required_original_tools": [],
            "available_original_tools": [],
            "visible_records_count": 0,
        },
    }
    defaults = optional_by_tool.get(tool_name, {})
    if item.name not in defaults:
        return None
    return (
        ast.Constant(value=defaults[item.name])
        if not isinstance(defaults[item.name], (dict, list))
        else ast.parse(repr(defaults[item.name])).body[0].value
    )


def _merge_output_schemas(
    current_schema: dict[str, Any], inferred_schema: dict[str, Any]
) -> dict[str, Any]:
    if not current_schema:
        return inferred_schema
    merged = dict(current_schema)
    current_props = merged.get("properties", {})
    inferred_props = inferred_schema.get("properties", {})
    props = dict(current_props) if isinstance(current_props, dict) else {}
    if isinstance(inferred_props, dict):
        props.update(
            {key: value for key, value in inferred_props.items() if key not in props}
        )
    merged["type"] = merged.get("type") or "object"
    merged["properties"] = props
    return merged


def _infer_inputs_from_examples(
    request: ToolGenerationRequest,
) -> tuple[ToolInput, ...]:
    values_by_name: dict[str, list[Any]] = {}
    for item in request.validation_examples:
        if not isinstance(item, dict):
            continue
        inputs = item.get("inputs")
        if not isinstance(inputs, dict):
            continue
        for key, value in inputs.items():
            name = str(key)
            values_by_name.setdefault(name, []).append(value)
    return tuple(
        ToolInput(
            name=name,
            annotation=_python_annotation_for_values(values),
            description=_visible_input_description(name, values),
        )
        for name, values in values_by_name.items()
    )


def _visible_input_description(name: str, values: list[Any]) -> str:
    """Describe actor inputs from public example structure, not task answers."""

    record_keys = {
        str(key)
        for value in values
        if isinstance(value, list)
        for record in value
        if isinstance(record, dict)
        for key in record
    }
    if record_keys:
        description = (
            "Complete visible records from the original tool result; preserve "
            "every record, field, and value exactly as returned."
        )
        if "is_self" in record_keys:
            description += (
                " Preserve each visible is_self value when present; do not add or "
                "fabricate a self record."
            )
        return description
    if name == "selection_mode":
        return "Visible semantic selection mode requested by the user."
    if name == "updates":
        return "Only the concrete field changes explicitly requested by the user."
    if name == "self_person_id":
        return (
            "Current user's person id copied exactly from a visible "
            "search_contacts result whose is_self field is true; never infer it."
        )
    return f"Visible input {name}."


def _merged_visible_input_description(
    authored: ToolInput | None,
    inferred_description: str,
) -> str:
    if authored is None or not authored.description.strip():
        return inferred_description
    authored_description = authored.description.strip()
    if inferred_description.startswith("Complete visible records") and (
        "preserve" not in authored_description.lower()
        or ("is_self" in inferred_description and "is_self" not in authored_description)
    ):
        return f"{authored_description.rstrip('.')}. {inferred_description}"
    return authored_description


def _python_annotation_for_value(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, list):
        return "list"
    return "str"


def _python_annotation_for_values(values: list[Any]) -> str:
    """Infer one callable type from all public validation-example values."""

    concrete = [value for value in values if value is not None]
    if not concrete:
        return "str"
    if all(isinstance(value, bool) for value in concrete):
        return "bool"
    if all(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in concrete
    ):
        return "float" if any(isinstance(value, float) for value in concrete) else "int"
    annotations = {_python_annotation_for_value(value) for value in concrete}
    if len(annotations) == 1:
        return annotations.pop()
    return _python_annotation_for_value(concrete[0])


def _infer_output_schema_from_examples(
    request: ToolGenerationRequest,
) -> dict[str, Any] | None:
    properties: dict[str, dict[str, str]] = {}
    for item in request.validation_examples:
        if not isinstance(item, dict):
            continue
        expected = item.get("expected")
        if not isinstance(expected, dict):
            continue
        for key, value in expected.items():
            properties.setdefault(str(key), {"type": _json_schema_type(value)})
    if not properties:
        return None
    return {"type": "object", "properties": properties}


def _json_schema_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if value is None:
        return "null"
    return "string"


def _request_evidence(
    request: ToolGenerationRequest,
    *,
    summary: str,
    signals: tuple[str, ...],
    failed_tool_calls: tuple[str, ...] = (),
) -> StructuredInadequacyEvidence:
    if isinstance(request.inadequacy_evidence, dict):
        evidence = StructuredInadequacyEvidence.from_json(request.inadequacy_evidence)
        if evidence.summary and evidence.signals:
            return evidence
    return StructuredInadequacyEvidence(
        summary=summary,
        signals=signals,
        failed_tool_calls=failed_tool_calls,
        repeated_failed_tool_calls=failed_tool_calls,
    )


def _coerce_input(item: Any) -> ToolInput:
    if isinstance(item, dict):
        return ToolInput(
            name=str(item.get("name", item.get("param", "arg"))),
            annotation=str(item.get("annotation", item.get("type", "str"))),
            description=str(item.get("description", "")),
        )
    if isinstance(item, str):
        parts = item.split(":", 2)
        name = parts[0].strip()
        annotation = parts[1].strip() if len(parts) > 1 else "str"
        description = parts[2].strip() if len(parts) > 2 else ""
        return ToolInput(name=name, annotation=annotation, description=description)
    raise ValueError(f"Cannot coerce ToolInput from {type(item)}: {item!r}")


def _coerce_str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    if isinstance(value, dict):
        return tuple(str(item) for item in value.values() if str(item).strip())
    try:
        return tuple(str(item) for item in value if str(item).strip())
    except TypeError:
        text = str(value)
        return (text,) if text.strip() else ()


def _coerce_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    match = re.search(r"-?\d+", str(value))
    return int(match.group(0)) if match else None


def _tool_examples_from_request(
    request: ToolGenerationRequest,
) -> tuple[Any, ...]:
    try:
        from sage_ts.validation.sandbox_validator import ToolExample
    except Exception:
        return ()
    examples: list[Any] = []
    raw_examples: object = request.validation_examples
    if _request_complete_tools_enabled(request):
        raw_examples = _native_action_validation_examples(request)
    for item in raw_examples:
        if not isinstance(item, dict):
            continue
        inputs = item.get("inputs", {})
        if not isinstance(inputs, dict):
            continue
        expected = item.get("expected")
        if _request_complete_tools_enabled(request):
            action = item.get("expected_native_action")
            expected = {}
            if isinstance(action, dict) and action.get("name"):
                expected = {
                    "tool_name": action.get("name"),
                    "arguments": action.get("arguments", {}),
                }
        examples.append(
            ToolExample(
                inputs=dict(inputs),
                expected=expected,
                held_out=bool(item.get("held_out", False)),
                negative_applicability=bool(item.get("negative_applicability", False)),
            )
        )
    return tuple(examples)


def _select_model_authored_candidate(
    request: ToolGenerationRequest,
    tools: list[GeneratedTool],
) -> GeneratedTool:
    if not tools:
        raise ValueError("missing_generated_tool_candidates")
    normalized = [_normalize_model_authored_tool(request, tool) for tool in tools]
    examples = _tool_examples_from_request(request)
    if len(normalized) == 1 or not examples:
        return normalized[0]
    try:
        from sage_ts.validation.sandbox_validator import validate_generated_tool
    except Exception:
        return normalized[0]

    best_tool = normalized[0]
    best_score: int | None = None
    for tool in normalized:
        try:
            result = validate_generated_tool(tool, examples)
        except Exception:
            continue
        if result.accepted:
            return tool
        score = _validation_error_distance(result.errors)
        if best_score is None or score < best_score:
            best_tool = tool
            best_score = score
    return best_tool


def _validation_error_distance(errors: tuple[str, ...]) -> int:
    """Rank rejected candidates by how far actual outputs are from expectations."""

    if not errors:
        return 0
    score = 0
    for error in errors:
        score += _single_validation_error_distance(error)
    return score


def _single_validation_error_distance(error: str) -> int:
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
        actual = ast.literal_eval(actual_text.replace("NOT_GIVEN", "'__NOT_GIVEN__'"))
        expected = ast.literal_eval(
            expected_text.replace("NOT_GIVEN", "'__NOT_GIVEN__'")
        )
    except Exception:
        return 10
    return _value_distance(actual, expected)


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


def _load_generated_tool_payload(response: str) -> dict[str, Any]:
    response = response.strip()
    if response.startswith("```"):
        response = response.removeprefix("```json").removeprefix("```").strip()
        response = response.removesuffix("```").strip()
    payload = json.loads(response)
    if not isinstance(payload, dict):
        raise ValueError("generated_tool_json_must_be_object")
    return payload


def parse_generated_tool_candidates_json(
    response: str,
    *,
    default_tool_name: str | None = None,
) -> list[GeneratedTool]:
    payload = _load_generated_tool_payload(response)
    candidates = payload.get("candidates")
    if isinstance(candidates, list) and candidates:
        tools: list[GeneratedTool] = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            try:
                tools.append(
                    _parse_generated_tool_payload(
                        candidate, default_tool_name=default_tool_name
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        if tools:
            return tools
        raise ValueError("missing_valid_generated_tool_candidates")
    return [_parse_generated_tool_payload(payload, default_tool_name=default_tool_name)]


def _parse_generated_tool_payload(
    payload: dict[str, Any],
    *,
    default_tool_name: str | None = None,
) -> GeneratedTool:
    spec_payload = payload["spec"]
    tool_name = str(spec_payload.get("tool_name") or default_tool_name or "")
    if not tool_name:
        raise ValueError("missing_generated_tool_name")
    if tool_name != tool_name.strip():
        raise ValueError("tool_name_has_surrounding_whitespace")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tool_name):
        raise ValueError(f"invalid_python_function_name:{tool_name}")
    spec = ToolSpec(
        tool_name=tool_name,
        family=ToolFamily(str(spec_payload["family"])),
        description=str(spec_payload.get("description", "")),
        inputs=tuple(_coerce_input(item) for item in spec_payload.get("inputs", ())),
        output_annotation=str(spec_payload.get("output_annotation", "dict")),
        output_schema=spec_payload.get("output_schema"),
        positive_triggers=_coerce_str_tuple(spec_payload.get("positive_triggers", ())),
        negative_triggers=_coerce_str_tuple(spec_payload.get("negative_triggers", ())),
        preserves_side_effect_tools=_coerce_str_tuple(
            spec_payload.get("preserves_side_effect_tools", ())
        ),
        required_original_tool_calls=_coerce_str_tuple(
            spec_payload.get("required_original_tool_calls", ())
        ),
        abstain_behavior=str(spec_payload.get("abstain_behavior", "")),
        generalization_rationale=str(spec_payload.get("generalization_rationale", "")),
        estimated_step_compression=_coerce_optional_int(
            spec_payload.get("estimated_step_compression")
        ),
        cross_task_applicability_count=_coerce_optional_int(
            spec_payload.get("cross_task_applicability_count")
        ),
        applicable_task_families=_coerce_str_tuple(
            spec_payload.get("applicable_task_families", ())
        ),
        reason_tool_is_decisive=str(spec_payload.get("reason_tool_is_decisive", "")),
        diagnostic_only=bool(spec_payload.get("diagnostic_only", False)),
        shortfall_cluster_evidence=_coerce_str_tuple(
            spec_payload.get("shortfall_cluster_evidence", ())
        ),
        known_failure_mechanisms_addressed=_coerce_str_tuple(
            spec_payload.get("known_failure_mechanisms_addressed", ())
        ),
        canonical_route_substitution_risk=str(
            spec_payload.get("canonical_route_substitution_risk", "none")
        ),
        expected_milestone_calls_replaced=_coerce_str_tuple(
            spec_payload.get("expected_milestone_calls_replaced", ())
        ),
        final_state_preservation_plan=str(
            spec_payload.get("final_state_preservation_plan", "")
        ),
        grading_accounting_note=str(spec_payload.get("grading_accounting_note", "")),
        inadequacy_evidence=StructuredInadequacyEvidence.from_json(
            dict(spec_payload.get("inadequacy_evidence", {}))
        )
        if isinstance(spec_payload.get("inadequacy_evidence"), dict)
        else StructuredInadequacyEvidence(
            summary=str(spec_payload.get("inadequacy_evidence", "")),
            signals=(),
        ),
    )
    return GeneratedTool(spec=spec, code=_coerce_generated_code(payload))


def _coerce_generated_code(payload: dict[str, Any]) -> str:
    if "code_lines" in payload:
        raw_lines = payload["code_lines"]
        if isinstance(raw_lines, str):
            raw_lines = raw_lines.splitlines()
        if not isinstance(raw_lines, list):
            raise ValueError("code_lines_must_be_list")
        lines = [str(line).rstrip("\n") for line in raw_lines]
        return "\n".join(lines).strip() + "\n"
    if "code" in payload:
        return str(payload["code"])
    raise ValueError("missing_generated_code")
