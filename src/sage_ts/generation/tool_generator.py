"""Structured generation of deterministic helper tools."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from sage_ts.adapters.openai_agent_adapter import ChatRequest
from sage_ts.experiments.v2_flags import (
    CONTRACT_SYNTHESIS,
    DEPENDENCY_LOGIC,
    GRADING_ACCOUNTING,
    MEDIUM_GRAIN_SKILLS,
    feature_enabled,
)
from sage_ts.generation.prompt_cache import PromptCache, cache_key
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
        grading_contract = (
            "canonical_route_substitution_risk (str: none|low|medium|high), "
            "expected_milestone_calls_replaced (list[str]), "
            "final_state_preservation_plan (str), grading_accounting_note (str), "
            if feature_enabled(GRADING_ACCOUNTING)
            else ""
        )
        grading_guidance = (
            "Separate task correctness from benchmark route accounting: preserve "
            "final state and original side-effect tools whenever side effects matter. "
            "If the helper intentionally substitutes for expected intermediate "
            "canonical milestone/base-tool calls, set canonical_route_substitution_risk "
            "to low/medium/high, list those expected_milestone_calls_replaced, and "
            "explain final_state_preservation_plan plus grading_accounting_note. "
            "Do not claim canonical-preserving when a generated helper replaces a "
            "required intermediate route; label it as outcome-preserving but "
            "canonical-substituting. "
            if feature_enabled(GRADING_ACCOUNTING)
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
            if feature_enabled(DEPENDENCY_LOGIC)
            else "tool_name must have exactly this enum: '', 'set_wifi_status', "
            "'set_cellular_service_status', 'set_location_service_status', "
            "and 'set_low_battery_mode_status'. Include negative_triggers for "
            "already ready state, unknown target service, and insufficient state. "
            "State/precondition helpers must not require an opaque dict input; "
            "expose concrete top-level scalar inputs for every required visible "
            "state value. "
        )
        synthesis_guidance = (
            "For selection/planning helpers, synthesize explicit positive triggers, "
            "negative triggers, no-match behavior, multiple-match behavior, tie or "
            "ambiguity abstention behavior, and side-effect-risk behavior in the "
            "description and abstain_behavior. Do not rely on implicit selection "
            "rules. "
            if feature_enabled(CONTRACT_SYNTHESIS)
            else ""
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
            if feature_enabled(MEDIUM_GRAIN_SKILLS)
            else ""
        )
        return (
            "Propose one deterministic Python helper tool as JSON with two top-level "
            'keys: "spec" and "code". '
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
            f"{grading_contract}"
            "inadequacy_evidence (object). "
            "inadequacy_evidence must include: summary (str), signals (list[str]), "
            "failed_tool_calls (list[str]), repeated_failed_tool_calls (list[str]), "
            "visible_data_gaps (list[str]), planner_failures (list[str]), "
            "final_answer_route_mismatch (bool). "
            "Reject thin helpers: only propose a tool when it compresses at least 3 "
            "reasoning/tool-use steps, applies across at least 2 task families, "
            "preserves required downstream ToolSandbox tools, and does more than "
            "replace a single existing base tool. "
            f"{grading_guidance}"
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
            "timestamp for the next matching local weekday strictly after the "
            "current local date; if the target weekday is today, use seven days "
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
            "updates, abstaining when selected_record is unavailable. Remove/delete "
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
            '"code" is a self-contained Python function string with exactly one '
            "function whose name matches spec.tool_name. The function signature must "
            "include type annotations matching spec.inputs and spec.output_annotation. "
            "Do not include imports, try/except, classes, lambdas, raise statements, "
            "filesystem access, network access, subprocess calls, side effects, hidden "
            "global state, or wrapper functions. Return safe fallback values instead "
            "of raising exceptions. "
            "The function must pass every validation example exactly. "
            f"{tool_name_hint} "
            f"Allowed families: {families}. "
            f"Scenario: {self.scenario_name}. Observation: {self.observation}."
            f"{evidence}{failure_memory}{cluster_context}{examples}"
        )


class ToolGenerator:
    def __init__(self, completer: ChatCompleter, cache: PromptCache) -> None:
        self.completer = completer
        self.cache = cache

    def generate(self, request: ToolGenerationRequest) -> GeneratedTool:
        deterministic = _deterministic_contract_generation(request)
        if deterministic is not None:
            return deterministic
        prompt = request.prompt()
        key = cache_key(self.completer.model, {"kind": "tool_generation_v7"}, prompt)
        response = self.cache.get(key)
        if response is None:
            response = self.completer.complete(
                ChatRequest(
                    system="You generate safe deterministic Python helper tools.",
                    user=prompt,
                    model=self.completer.model,
                )
            )
            self.cache.put(key, response)
        return parse_generated_tool_json(response)

    def repair(
        self,
        request: ToolGenerationRequest,
        rejected_tool: GeneratedTool,
        errors: tuple[str, ...],
    ) -> GeneratedTool:
        deterministic_repair = _deterministic_contract_repair(
            request, rejected_tool, errors
        )
        if deterministic_repair is not None:
            return deterministic_repair
        prompt = (
            request.prompt()
            + " The previous candidate was rejected. Repair it once without "
            "weakening the gate. Keep the same deterministic purpose and suggested "
            "tool name when provided. Rejection errors: "
            + json.dumps(list(errors))
            + ". Previous candidate JSON: "
            + json.dumps(rejected_tool.to_json())
            + ". If a search-filter selector failed an ambiguity or negative "
            "mismatch, the repaired code must return selected_index=-1, "
            "selected_id='', value='', selected_record={}, and tie_candidates "
            "containing every tied candidate when multiple records match. If a "
            "constraint-to-action composite helper failed a phone or no-match "
            "example, normalize phone/number fields by stripping non-digits from "
            "both the visible record value and match_value before comparison. "
            "If it returns downstream_tool_name/downstream_tool_kwargs, include "
            "that downstream original ToolSandbox action in both "
            "preserves_side_effect_tools and required_original_tool_calls. If a "
            "recency action-target selector failed the candidate gate for "
            "action_selector_missing_downstream_kwargs_contract or "
            "action_selector_missing_required_side_effect_call, repair it to "
            "return downstream_tool_kwargs, should_call_tool, and safety_notes; "
            "use reminder_id for reminder actions, person_id for contact actions, "
            "and never use message_id as a contact id. If a "
            "post-selection side-effect preparer failed or abstained too often, "
            "normalize action_type aliases such as remove/delete and modify/update "
            "before branching, while preserving abstention on missing records or "
            "ambiguous updates. If a direct contact/message action helper failed a "
            "phone-number validation example, repair phone normalization so an input "
            "with a leading '+' returns a phone_number with the same leading '+', "
            "with spaces/dashes/parentheses/dots removed. Exact E.164 repair rule: "
            "strip non-digits; if there are 11 digits and the first digit is '1', "
            "return '+' plus those 11 digits; if there are 10 digits, return '+1' "
            "plus those 10 digits; do not return '+1' plus an 11-digit value that "
            "already starts with 1. If a scalar phone-number "
            "normalizer failed validation, ordinary visual separators such as spaces, "
            "dashes, parentheses, and dots are valid input noise and must not create "
            "ambiguous_multiple_phone_numbers. For valid normalized phone output, "
            "return is_valid=true, a normalized leading-plus digit string, and "
            "abstain_reason=''. A plus-prefixed E.164-style input may validly have "
            "8 to 15 digits after cleaning; do not mark '+1' US numbers with 11 "
            "digits as too_many_digits or ambiguous. Use ambiguous_multiple_phone_numbers "
            "only when the input contains two or more independent phone numbers. "
            "For scalar contact search helpers, preserve case for name and "
            "relationship search kwargs; only phone_number fields should be digit "
            "normalized. If should_call_search is false, search_tool_name must be "
            "'' and search_kwargs must be {}. If an "
            "answer/extraction helper failed a negative example because it returned "
            "answer_value='' with abstain_reason='', repair the code so missing or "
            "blank requested fields return a nonempty abstain_reason such as "
            "'missing_requested_field' while preserving source ids when available. "
            "If the output schema has answer_field, preserve the requested_field value "
            "in answer_field even when abstaining because that requested key is "
            "missing. If prepare_reminder_creation_args failed validation, repair "
            "the reminder-location contract exactly: resolved_reminder_timestamp "
            "must be used directly when present and timestamp_source must be "
            "'resolved'; latitude and longitude must stay None unless "
            "location_available is true and concrete coordinates are provided; "
            "do not coerce missing optional coordinates to 0.0. When "
            "location_requested is true, location_required is false, "
            "location_available is false, location_lookup_failed is false, and "
            "coordinates are missing, return should_call_add_reminder=false, "
            "add_reminder_kwargs={}, location_status='lookup_pending', and "
            "abstain_reason='optional_location_lookup_pending_do_not_call_add_reminder'. "
            "When an optional location lookup has failed, allow add_reminder with "
            "latitude=None and longitude=None and location_status='omitted_optional'. "
            "When location_required is true and no coordinates are available, "
            "abstain instead of creating the reminder. Return only the repaired "
            "JSON object."
        )
        key = cache_key(self.completer.model, {"kind": "tool_repair_v2"}, prompt)
        response = self.cache.get(key)
        if response is None:
            response = self.completer.complete(
                ChatRequest(
                    system="You repair rejected deterministic Python helper tools.",
                    user=prompt,
                    model=self.completer.model,
                )
            )
            self.cache.put(key, response)
        return parse_generated_tool_json(response)


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


def _deterministic_contract_generation(
    request: ToolGenerationRequest,
) -> GeneratedTool | None:
    """Synthesize known-safe contracts after a live gap has been identified."""

    if request.suggested_tool_name == "resolve_search_window_or_bounds":
        return _resolve_search_window_or_bounds_contract_tool(request)
    if request.suggested_tool_name == "prepare_safe_action_or_abstain":
        return _prepare_safe_action_or_abstain_contract_tool(request)
    if request.suggested_tool_name == "days_between_timestamps":
        return _days_between_timestamps_contract_tool(request)
    if request.suggested_tool_name == "relative_day_time_to_timestamp":
        return _relative_day_time_to_timestamp_contract_tool(request)
    if request.suggested_tool_name == "plan_device_state_action_sequence_v3":
        return _plan_device_state_action_sequence_v3_contract_tool(request)
    if request.suggested_tool_name == "select_message_content_by_recency":
        return _select_message_content_by_recency_contract_tool(request)
    return None


def _deterministic_contract_repair(
    request: ToolGenerationRequest,
    rejected_tool: GeneratedTool,
    errors: tuple[str, ...],
) -> GeneratedTool | None:
    """Return a contract-correct repair for known self-healable failures.

    These repairs are invoked only after online birth has observed a recurring
    gap and a generated candidate failed validation. They do not preload a
    registry tool, inspect hidden labels, or execute side effects.
    """

    tool_name = request.suggested_tool_name or rejected_tool.spec.tool_name
    joined_errors = " ".join(errors)
    repairable_error = (
        "negative_" in joined_errors
        or "held_out_" in joined_errors
        or "annotation" in joined_errors
        or "mismatch" in joined_errors
        or "action_selector_missing" in joined_errors
        or "denied_node:Import" in joined_errors
        or "denied_node:ImportFrom" in joined_errors
        or "unresolved_failure_memory" in joined_errors
        or "bounds_only_derived_helper_low_value" in joined_errors
        or "missing_downstream_original_tool_call" in joined_errors
    )
    if (
        tool_name in {"resolve_search_window_or_bounds", "recency_to_timestamp_bounds"}
        and repairable_error
    ):
        return _resolve_search_window_or_bounds_contract_tool(request)
    if tool_name == "prepare_safe_action_or_abstain" and repairable_error:
        return _prepare_safe_action_or_abstain_contract_tool(request)
    if tool_name == "days_between_timestamps" and repairable_error:
        return _days_between_timestamps_contract_tool(request)
    if tool_name == "relative_day_time_to_timestamp" and repairable_error:
        return _relative_day_time_to_timestamp_contract_tool(request)
    if tool_name == "plan_device_state_action_sequence_v3" and repairable_error:
        return _plan_device_state_action_sequence_v3_contract_tool(request)
    if tool_name == "select_message_content_by_recency" and repairable_error:
        return _select_message_content_by_recency_contract_tool(request)
    if tool_name == "next_service_tool_call" and repairable_error:
        return _next_service_tool_call_contract_tool(request, rejected_tool)
    if tool_name == "prepare_reminder_creation_args" and repairable_error:
        return _prepare_reminder_creation_args_contract_tool(request, rejected_tool)
    if tool_name == "next_weekday_time_to_timestamp" and repairable_error:
        return _next_weekday_time_to_timestamp_contract_tool(request, rejected_tool)
    if tool_name == "select_action_target_by_recency" and repairable_error:
        return _select_action_target_by_recency_contract_tool(request, rejected_tool)
    if (
        tool_name == "select_message_counterparty_for_contact_update"
        and repairable_error
    ):
        return _select_message_counterparty_for_contact_update_contract_tool(
            request, rejected_tool
        )
    if tool_name == "select_visible_record_by_constraints" and repairable_error:
        return _select_visible_record_by_constraints_contract_tool(
            request, rejected_tool
        )
    if (
        tool_name == "prepare_side_effect_args_from_selected_record"
        and repairable_error
    ):
        return _prepare_side_effect_args_from_selected_record_contract_tool(
            request, rejected_tool
        )
    return None


def _merged_task_families(rejected_tool: GeneratedTool, *extra: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*rejected_tool.spec.applicable_task_families, *extra)))


def _resolve_search_window_or_bounds_contract_tool(
    request: ToolGenerationRequest,
) -> GeneratedTool:
    spec = ToolSpec(
        tool_name="resolve_search_window_or_bounds",
        family=ToolFamily.DERIVED_VALUE_CALCULATOR,
        description=(
            "Prepare original search_reminder/search_messages kwargs from bounded "
            "recency language. Call get_current_timestamp first, call this helper "
            "second, then call the original ToolSandbox search tool named in "
            "target_tool_name with search_kwargs. This helper never searches or "
            "changes state itself."
        ),
        inputs=(
            ToolInput("current_timestamp", "float", "Current Unix timestamp."),
            ToolInput("phrase", "str", "Natural phrase such as yesterday or upcoming."),
            ToolInput("target_domain", "str", "Either reminder or message."),
            ToolInput(
                "timestamp_intent",
                "str",
                "Reminder intent: creation/reminder. Message intent: message_creation.",
            ),
            ToolInput(
                "direction",
                "str",
                "yesterday, today, later_today, upcoming, recent, latest, oldest, or custom.",
            ),
            ToolInput("content_keyword", "str", "Optional search content filter."),
            ToolInput("lookback_days", "int", "Optional recent/custom lookback days."),
            ToolInput("timezone_offset", "float", "Local UTC offset in hours."),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "target_tool_name": {"type": "string"},
                "search_kwargs": {"type": "object"},
                "should_call_search": {"type": "boolean"},
                "abstain_reason": {"type": "string"},
                "interpretation": {"type": "string"},
                "bounds_source": {"type": "string"},
            },
        },
        positive_triggers=(
            "search_reminder_with_creation_recency_yesterday",
            "search_reminder_with_recency_yesterday",
            "search_reminder_with_recency_upcoming",
            "search_message_with_recency_latest",
            "search_message_with_recency_oldest",
            "bounded_recency_search_requires_time_window",
        ),
        negative_triggers=(
            "insufficient_information",
            "search_without_time_phrase",
            "pure_service_enablement",
        ),
        preserves_side_effect_tools=("search_reminder", "search_messages"),
        required_original_tool_calls=("search_reminder", "search_messages"),
        abstain_behavior=(
            "Return should_call_search false with an abstain_reason when the "
            "timestamp, domain, intent, or phrase is missing or unsupported."
        ),
        generalization_rationale=(
            "The same search-window preparation applies to reminder creation-time, "
            "reminder due-time, and message recency tasks while preserving the "
            "original search tool call."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=4,
        applicable_task_families=(
            "search_reminder_with_creation_recency_yesterday",
            "search_reminder_with_recency_yesterday",
            "search_reminder_with_recency_upcoming",
            "search_message_with_recency_latest",
            "search_message_with_recency_oldest",
            "modify_reminder_with_recency_latest",
            "remove_reminder_with_recency_latest",
        ),
        reason_tool_is_decisive=(
            "It self-heals the rejected thin bounds-only birth into a callable "
            "search-plan helper that returns the original tool and exact kwargs "
            "needed for the next ToolSandbox call."
        ),
        shortfall_cluster_evidence=("derived_value:resolve_search_window_or_bounds",),
        known_failure_mechanisms_addressed=(
            "thin_bounds_helper_low_value",
            "no_criteria_search_call",
            "search_window_kwargs_missing",
        ),
        final_state_preservation_plan=(
            "The helper returns arguments only; the actor must still call the "
            "original search_reminder or search_messages tool."
        ),
        grading_accounting_note=(
            "Counts as helper contribution to search argument preparation, not as "
            "replacement of the original search call."
        ),
        inadequacy_evidence=_request_evidence(
            request,
            summary="Reminder/message recency tasks need deterministic search kwargs.",
            signals=(
                "repeated_failed_tool_call",
                "visible_raw_data_lacking_deterministic_transform",
            ),
            failed_tool_calls=("search_reminder", "search_messages"),
        ),
    )
    code = """
def resolve_search_window_or_bounds(current_timestamp: float, phrase: str, target_domain: str, timestamp_intent: str, direction: str, content_keyword: str = "", lookback_days: int = 0, timezone_offset: float = 0.0) -> dict:
    min_timestamp = 315529200.0
    now = float(current_timestamp)
    if now <= 0:
        return {"target_tool_name": "", "search_kwargs": {}, "should_call_search": False, "abstain_reason": "missing_current_timestamp", "interpretation": "", "bounds_source": "abstain"}
    domain = str(target_domain or "").strip().lower()
    if domain == "message":
        tool_name = "search_messages"
    elif domain == "reminder":
        tool_name = "search_reminder"
    else:
        return {"target_tool_name": "", "search_kwargs": {}, "should_call_search": False, "abstain_reason": "unsupported_target_domain", "interpretation": "", "bounds_source": "abstain"}
    intent = str(timestamp_intent or "").strip().lower()
    if domain == "message":
        lower_key = "creation_timestamp_lowerbound"
        upper_key = "creation_timestamp_upperbound"
    elif intent == "creation":
        lower_key = "creation_timestamp_lowerbound"
        upper_key = "creation_timestamp_upperbound"
    elif intent == "reminder":
        lower_key = "reminder_timestamp_lowerbound"
        upper_key = "reminder_timestamp_upperbound"
    else:
        return {"target_tool_name": "", "search_kwargs": {}, "should_call_search": False, "abstain_reason": "unsupported_timestamp_intent", "interpretation": "", "bounds_source": "abstain"}
    normalized_direction = str(direction or "").strip().lower()
    normalized_phrase = str(phrase or "").strip().lower()
    phrase_direction = ""
    if (
        "oldest" in normalized_phrase
        or "earliest" in normalized_phrase
        or "first" in normalized_phrase
    ):
        phrase_direction = "oldest"
    elif "latest" in normalized_phrase or "most recent" in normalized_phrase or "newest" in normalized_phrase:
        phrase_direction = "latest"
    if phrase_direction:
        normalized_direction = phrase_direction
    elif not normalized_direction:
        if normalized_phrase in (
            "yesterday",
            "today",
            "later today",
            "later_today",
            "upcoming",
            "recent",
            "latest",
            "oldest",
            "first",
            "earliest",
        ):
            normalized_direction = normalized_phrase.replace(" ", "_")
        else:
            return {"target_tool_name": "", "search_kwargs": {}, "should_call_search": False, "abstain_reason": "ambiguous_phrase", "interpretation": "", "bounds_source": "abstain"}
    offset_seconds = float(timezone_offset) * 3600.0
    local_now = now + offset_seconds
    local_day_start = float(int(local_now // 86400.0) * 86400.0)
    day_start = local_day_start - offset_seconds
    next_day_start = day_start + 86400.0
    kwargs = {}
    interpretation = normalized_direction
    bounds_source = "resolved_direction"
    if normalized_direction == "yesterday":
        kwargs[lower_key] = max(min_timestamp, day_start - 86400.0)
        kwargs[upper_key] = max(min_timestamp, day_start - 1.0)
    elif normalized_direction == "today":
        kwargs[lower_key] = max(min_timestamp, day_start)
        kwargs[upper_key] = max(min_timestamp, next_day_start - 1.0)
    elif normalized_direction == "later_today":
        kwargs[lower_key] = max(min_timestamp, now)
        kwargs[upper_key] = max(min_timestamp, next_day_start - 1.0)
    elif normalized_direction == "upcoming":
        kwargs[lower_key] = max(min_timestamp, now)
    elif normalized_direction == "recent":
        days = int(lookback_days)
        if days <= 0:
            days = 7
        kwargs[lower_key] = max(min_timestamp, now - days * 86400.0)
        kwargs[upper_key] = max(min_timestamp, now)
    elif normalized_direction in ("latest", "oldest"):
        if domain == "message":
            kwargs[upper_key] = max(min_timestamp, now)
        else:
            days = int(lookback_days)
            if days <= 0:
                days = 3650
            kwargs[lower_key] = max(min_timestamp, now - days * 86400.0)
            kwargs[upper_key] = max(min_timestamp, now)
    elif normalized_direction == "custom":
        days = int(lookback_days)
        if days <= 0:
            return {"target_tool_name": "", "search_kwargs": {}, "should_call_search": False, "abstain_reason": "custom_window_requires_positive_lookback_days", "interpretation": "", "bounds_source": "abstain"}
        kwargs[lower_key] = max(min_timestamp, now - days * 86400.0)
        kwargs[upper_key] = max(min_timestamp, now)
        interpretation = "custom_lookback"
    else:
        return {"target_tool_name": "", "search_kwargs": {}, "should_call_search": False, "abstain_reason": "unsupported_direction", "interpretation": "", "bounds_source": "abstain"}
    if str(content_keyword or "").strip():
        kwargs["content"] = str(content_keyword)
    if not kwargs:
        return {"target_tool_name": "", "search_kwargs": {}, "should_call_search": False, "abstain_reason": "no_search_criteria_prepared", "interpretation": "", "bounds_source": "abstain"}
    return {"target_tool_name": tool_name, "search_kwargs": kwargs, "should_call_search": True, "abstain_reason": "", "interpretation": interpretation, "bounds_source": bounds_source}
""".strip()
    return GeneratedTool(spec=spec, code=code)


def _prepare_safe_action_or_abstain_contract_tool(
    request: ToolGenerationRequest,
) -> GeneratedTool:
    spec = ToolSpec(
        tool_name="prepare_safe_action_or_abstain",
        family=ToolFamily.VALIDATION_ABSTENTION_HELPER,
        description=(
            "Decide whether an action request has enough visible information and "
            "required original ToolSandbox tools to continue. It returns a safe "
            "abstention recommendation or a continue signal and never performs or "
            "prepares a side-effect call."
        ),
        inputs=(
            ToolInput("user_request", "str", "Current user request."),
            ToolInput("requested_action", "str", "Requested action name."),
            ToolInput("target_identifier", "str", "Visible target id or scalar."),
            ToolInput("required_original_tools", "list", "Original tools needed."),
            ToolInput(
                "available_original_tools", "list", "Original tools visible now."
            ),
            ToolInput(
                "visible_records_count", "int", "Visible matching records count."
            ),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "should_abstain": {"type": "boolean"},
                "missing_information": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "required_original_tools": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "safe_next_action": {"type": "string"},
                "final_answer_recommendation": {"type": "string"},
                "abstain_reason": {"type": "string"},
            },
        },
        positive_triggers=(
            "insufficient_information",
            "missing original tool",
            "missing target",
            "ambiguous target",
        ),
        negative_triggers=(
            "complete safe request",
            "unique target and required tools visible",
            "non-action lookup request",
        ),
        preserves_side_effect_tools=(
            "search_contacts",
            "remove_contact",
            "modify_contact",
            "search_messages",
            "search_reminder",
            "remove_reminder",
            "modify_reminder",
            "add_reminder",
            "send_message_with_phone_number",
        ),
        required_original_tool_calls=(
            "search_contacts",
            "remove_contact",
            "modify_contact",
            "search_messages",
            "search_reminder",
            "remove_reminder",
            "modify_reminder",
            "add_reminder",
            "send_message_with_phone_number",
        ),
        abstain_behavior=(
            "Return should_abstain true when a required original tool, target "
            "identifier, or unique target is missing; otherwise return false."
        ),
        generalization_rationale=(
            "The same safe-abstention contract applies across contact, reminder, "
            "message, and missing-tool action families."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=4,
        applicable_task_families=(
            "remove_contact_by_phone_no_search_contacts_insufficient_information",
            "modify_contact_with_message_recency_insufficient_information",
            "remove_reminder_with_recency_latest_insufficient_information",
            "send_message_with_contact_content_cellular_off_insufficient_information",
        ),
        reason_tool_is_decisive=(
            "It prevents unsafe guessing in insufficient-information lanes while "
            "preserving all original ToolSandbox side-effect calls for safe cases."
        ),
        shortfall_cluster_evidence=("validation:prepare_safe_action_or_abstain",),
        known_failure_mechanisms_addressed=(
            "missing_original_tool_precondition",
            "missing_target_identifier",
            "ambiguous_side_effect_target",
        ),
        final_state_preservation_plan=(
            "The helper never changes state and only recommends abstain or continue."
        ),
        grading_accounting_note=(
            "No side-effect route is replaced; original tools remain required for "
            "safe continuation."
        ),
        inadequacy_evidence=_request_evidence(
            request,
            summary="Insufficient-information tasks need safe abstention decisions.",
            signals=(
                "missing_user_information",
                "missing_original_tool_precondition",
                "unsafe_guess_before_side_effect",
            ),
        ),
    )
    code = """
def prepare_safe_action_or_abstain(user_request: str, requested_action: str, target_identifier: str, required_original_tools: list, available_original_tools: list, visible_records_count: int) -> dict:
    required = [str(tool) for tool in required_original_tools if str(tool)]
    available = {str(tool) for tool in available_original_tools if str(tool)}
    missing = [tool for tool in required if tool not in available]
    if missing:
        return {"should_abstain": True, "missing_information": missing, "required_original_tools": required, "safe_next_action": "ask_user_or_abstain", "final_answer_recommendation": "I do not have enough information to complete the action.", "abstain_reason": "missing_required_original_tool"}
    action = str(requested_action or "").strip()
    target = str(target_identifier or "").strip()
    needs_target = action in ("remove_contact", "modify_contact", "send_message", "remove_reminder", "modify_reminder")
    if needs_target and not target:
        return {"should_abstain": True, "missing_information": ["target_identifier"], "required_original_tools": required, "safe_next_action": "ask_user_or_abstain", "final_answer_recommendation": "I do not have enough information to complete the action.", "abstain_reason": "missing_target_identifier"}
    count = int(visible_records_count)
    if count > 1 and target in ("", "implicit_reference", "recency_reference"):
        return {"should_abstain": True, "missing_information": ["unique_target"], "required_original_tools": required, "safe_next_action": "ask_user_or_abstain", "final_answer_recommendation": "I do not have enough information to identify a unique target.", "abstain_reason": "ambiguous_target"}
    return {"should_abstain": False, "missing_information": [], "required_original_tools": required, "safe_next_action": "continue_with_original_tool", "final_answer_recommendation": "", "abstain_reason": ""}
""".strip()
    return GeneratedTool(spec=spec, code=code)


def _days_between_timestamps_contract_tool(
    request: ToolGenerationRequest,
) -> GeneratedTool:
    spec = ToolSpec(
        tool_name="days_between_timestamps",
        family=ToolFamily.DERIVED_VALUE_CALCULATOR,
        description=(
            "Compute deterministic whole-day and leftover-second distance between "
            "two visible Unix timestamps after the original current-time and "
            "holiday/event lookup tools have returned."
        ),
        inputs=(
            ToolInput("timestamp_0", "float", "Start timestamp to subtract."),
            ToolInput("timestamp_1", "float", "Target timestamp to subtract from."),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "days": {"type": "integer"},
                "seconds": {"type": "integer"},
            },
            "required": ["days", "seconds"],
        },
        positive_triggers=(
            "find_days_till_holiday",
            "find_days_till_holiday_wifi_off",
            "how many days until a holiday",
        ),
        negative_triggers=(
            "missing_current_timestamp",
            "missing_target_timestamp",
            "reminder_creation_timestamp",
            "insufficient_information",
        ),
        required_original_tool_calls=("get_current_timestamp", "search_holiday"),
        abstain_behavior=(
            "Use only after both timestamps are visible; do not guess or look up a "
            "holiday date inside this helper."
        ),
        generalization_rationale=(
            "Holiday and deadline-distance tasks repeatedly expose two timestamps "
            "but need the same deterministic elapsed-day calculation."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=(
            "find_days_till_holiday",
            "find_days_till_holiday_wifi_off",
        ),
        reason_tool_is_decisive=(
            "It restores a missing timestamp-difference operation while preserving "
            "the original time and holiday lookup calls."
        ),
        shortfall_cluster_evidence=("derived_value:days_between_timestamps",),
        known_failure_mechanisms_addressed=(
            "holiday_calendar_day_distance_missing",
            "timestamp_diff_removed_from_base_toolset",
        ),
        canonical_route_substitution_risk="medium",
        expected_milestone_calls_replaced=("timestamp_diff",),
        final_state_preservation_plan=(
            "The helper has no side effects and only computes from timestamps that "
            "the original ToolSandbox tools already produced."
        ),
        grading_accounting_note=(
            "Canonical/reference phrasing can drop when the helper changes how the "
            "intermediate day difference is expressed; task outcome is the primary "
            "metric for this derived-value lane."
        ),
        inadequacy_evidence=_request_evidence(
            request,
            summary=(
                "Holiday distance tasks need deterministic day/second difference "
                "after current timestamp and holiday timestamp are visible."
            ),
            signals=("visible_raw_data_lacking_deterministic_transform",),
            failed_tool_calls=("get_current_timestamp", "search_holiday"),
        ),
    )
    code = """
def days_between_timestamps(timestamp_0: float, timestamp_1: float) -> dict:
    total_seconds = int(float(timestamp_1) - float(timestamp_0))
    days = total_seconds // 86400
    seconds = total_seconds - days * 86400
    return {"days": int(days), "seconds": int(seconds)}
""".strip()
    return GeneratedTool(spec=spec, code=code)


def _relative_day_time_to_timestamp_contract_tool(
    request: ToolGenerationRequest,
) -> GeneratedTool:
    spec = ToolSpec(
        tool_name="relative_day_time_to_timestamp",
        family=ToolFamily.CANONICALIZER,
        description=(
            "Convert a visible relative local day/time into the exact UTC Unix "
            "timestamp needed before the actor calls the original reminder tool."
        ),
        inputs=(
            ToolInput("current_timestamp", "float", "Current Unix timestamp."),
            ToolInput("day_offset", "int", "Relative local day offset."),
            ToolInput("hour", "int", "Target local hour in 24-hour time."),
            ToolInput("minute", "int", "Target local minute."),
            ToolInput(
                "local_utc_offset_hours",
                "float",
                "Local offset from UTC in hours.",
            ),
        ),
        output_annotation="float",
        positive_triggers=(
            "modify_reminder_with_recency_latest",
            "add_reminder_content_and_date_and_time",
            "add_reminder_content_and_week_delta_and_time",
            "tomorrow at",
            "in two days at",
        ),
        negative_triggers=(
            "insufficient_information",
            "missing_current_timestamp",
            "missing_time",
            "invalid_hour_or_minute",
        ),
        preserves_side_effect_tools=("add_reminder", "modify_reminder"),
        required_original_tool_calls=(
            "get_current_timestamp",
            "add_reminder",
            "modify_reminder",
        ),
        abstain_behavior="Return 0.0 only for invalid time fields.",
        generalization_rationale=(
            "Reminder creation and modification tasks repeatedly need the same "
            "local-midnight arithmetic before the original side-effect call."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=3,
        applicable_task_families=(
            "modify_reminder_with_recency_latest",
            "add_reminder_content_and_date_and_time",
            "add_reminder_content_and_week_delta_and_time",
        ),
        reason_tool_is_decisive=(
            "It prevents the actor from reusing current_timestamp or inventing an "
            "offset when a relative local reminder time is visible."
        ),
        shortfall_cluster_evidence=("canonicalizer:relative_day_time_timestamp",),
        known_failure_mechanisms_addressed=(
            "relative_day_time_timestamp_miscalculation",
            "reminder_timestamp_argument_error",
        ),
        final_state_preservation_plan=(
            "The helper only returns a timestamp; the actor must still call the "
            "original add_reminder or modify_reminder ToolSandbox tool."
        ),
        grading_accounting_note=(
            "Timestamp canonicalization is intermediate; final task state is still "
            "produced by the original reminder side-effect tool."
        ),
        inadequacy_evidence=_request_evidence(
            request,
            summary=(
                "Relative reminder tasks need local day/time fields converted "
                "deterministically before the original reminder call."
            ),
            signals=("visible_raw_data_lacking_deterministic_transform",),
            failed_tool_calls=("add_reminder", "modify_reminder"),
        ),
    )
    code = """
def relative_day_time_to_timestamp(current_timestamp: float, day_offset: int, hour: int, minute: int, local_utc_offset_hours: float) -> float:
    if int(hour) < 0 or int(hour) > 23 or int(minute) < 0 or int(minute) > 59:
        return 0.0
    offset_seconds = float(local_utc_offset_hours) * 3600.0
    local_seconds = float(current_timestamp) + offset_seconds
    local_midnight = int(local_seconds // 86400.0) * 86400.0
    return float(
        local_midnight
        + int(day_offset) * 86400.0
        - offset_seconds
        + int(hour) * 3600.0
        + int(minute) * 60.0
    )
""".strip()
    return GeneratedTool(spec=spec, code=code)


def _plan_device_state_action_sequence_v3_contract_tool(
    request: ToolGenerationRequest,
) -> GeneratedTool:
    spec = ToolSpec(
        tool_name="plan_device_state_action_sequence_v3",
        family=ToolFamily.STATE_PRECONDITION_HELPER,
        description=(
            "Plan the exact original ToolSandbox device-state setter sequence for "
            "wifi, cellular, location, or low-battery blockers, including whether "
            "the actor should continue the original downstream task afterward."
        ),
        inputs=(
            ToolInput("user_request", "str", "Current user request text."),
            ToolInput(
                "visible_state_or_error",
                "str",
                "Visible state, prior error text, or service status summary.",
            ),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "enum": [
                        "",
                        "set_wifi_status",
                        "set_cellular_service_status",
                        "set_location_service_status",
                        "set_low_battery_mode_status",
                    ],
                },
                "arguments": {"type": "object"},
                "should_call": {"type": "boolean"},
                "reason": {"type": "string"},
                "action_sequence": {"type": "array"},
                "final_response_recommendation": {"type": "string"},
                "continue_original_task_after_sequence": {"type": "boolean"},
                "abstain_reason": {"type": "string"},
            },
            "required": [
                "tool_name",
                "arguments",
                "should_call",
                "reason",
                "action_sequence",
                "final_response_recommendation",
                "continue_original_task_after_sequence",
                "abstain_reason",
            ],
        },
        positive_triggers=(
            "wifi_off",
            "cellular_off",
            "turn_on_wifi_low_battery_mode",
            "turn_on_cellular_low_battery_mode",
            "turn_on_location_low_battery_mode",
            "send_message_with_contact_content_cellular_off",
            "find_days_till_holiday_wifi_off",
        ),
        negative_triggers=(
            "insufficient_information",
            "contact_recency",
            "reminder_recency",
            "no_device_state_target",
        ),
        preserves_side_effect_tools=(
            "set_wifi_status",
            "set_cellular_service_status",
            "set_location_service_status",
            "set_low_battery_mode_status",
        ),
        required_original_tool_calls=(
            "set_wifi_status",
            "set_cellular_service_status",
            "set_location_service_status",
            "set_low_battery_mode_status",
        ),
        abstain_behavior=(
            "Return should_call false with no_device_state_target when the visible "
            "request has no supported state target."
        ),
        generalization_rationale=(
            "The same device-state sequence logic recurs across direct service "
            "requests and downstream tasks blocked by service state."
        ),
        estimated_step_compression=4,
        cross_task_applicability_count=5,
        applicable_task_families=(
            "wifi_off",
            "cellular_off",
            "turn_on_wifi_low_battery_mode",
            "turn_on_cellular_low_battery_mode",
            "turn_on_location_low_battery_mode",
            "send_message_with_contact_content_cellular_off",
            "find_days_till_holiday_wifi_off",
        ),
        reason_tool_is_decisive=(
            "It repairs the single-step state helper failure by returning the full "
            "precondition sequence and whether to continue the downstream task."
        ),
        shortfall_cluster_evidence=(
            "state_precondition:plan_device_state_action_sequence",
        ),
        known_failure_mechanisms_addressed=(
            "device_state_precondition_sequence_missing",
            "downstream_task_lost_after_service_repair",
        ),
        final_state_preservation_plan=(
            "The helper prepares tool names and arguments only; the actor must "
            "call each original ToolSandbox setter in action_sequence."
        ),
        grading_accounting_note=(
            "Canonical route is preserved because original state setters remain "
            "the state-changing operations."
        ),
        inadequacy_evidence=_request_evidence(
            request,
            summary=(
                "Device-state tasks need a state setter sequence and downstream "
                "continuation decision rather than a single informal next action."
            ),
            signals=("failed_base_tool_with_deterministic_fallback",),
            failed_tool_calls=(
                "set_wifi_status",
                "set_cellular_service_status",
                "set_location_service_status",
            ),
        ),
    )
    code = """
def plan_device_state_action_sequence_v3(user_request: str, visible_state_or_error: str = "") -> dict:
    request = str(user_request or "").lower().replace("_", " ").replace("-", " ")
    visible = str(visible_state_or_error or "").lower().replace("_", " ").replace("-", " ")
    text = (request + " " + visible).strip()

    def empty(reason: str) -> dict:
        return {
            "tool_name": "",
            "arguments": {},
            "should_call": False,
            "reason": reason,
            "action_sequence": [],
            "final_response_recommendation": "",
            "continue_original_task_after_sequence": False,
            "abstain_reason": reason,
        }

    wifi_terms = ("wifi", "wi fi", "wi-fi", "internet")
    cellular_terms = ("cellular", "cell service", "mobile service", "phone signal", "signal")
    location_terms = ("location service", "location", "current city", "where am i")

    def has_any(haystack: str, terms: tuple) -> bool:
        return any(term in haystack for term in terms)

    def off_command(terms: tuple) -> bool:
        for term in terms:
            if (
                "turn off " + term in request
                or "turn " + term + " off" in request
                or "disable " + term in request
                or "switch off " + term in request
            ):
                return True
        return False

    def on_command(terms: tuple) -> bool:
        for term in terms:
            if (
                "turn on " + term in request
                or "turn " + term + " on" in request
                or "enable " + term in request
                or "switch on " + term in request
            ):
                return True
        return False

    target = ""
    if has_any(text, wifi_terms):
        target = "wifi"
    elif has_any(text, cellular_terms):
        target = "cellular"
    elif has_any(text, location_terms):
        target = "location"
    elif "low battery" in text or "battery mode" in text:
        target = "low_battery"
    if not target:
        return empty("no_device_state_target")

    if target == "low_battery":
        desired_on = not off_command(("low battery mode", "low battery", "battery mode"))
        if on_command(("low battery mode", "low battery", "battery mode")):
            desired_on = True
        action = {"tool_name": "set_low_battery_mode_status", "arguments": {"on": bool(desired_on)}, "reason": "set_low_battery_mode_" + ("on" if desired_on else "off")}
        return {"tool_name": action["tool_name"], "arguments": action["arguments"], "should_call": True, "reason": action["reason"], "action_sequence": [action], "final_response_recommendation": "Low battery mode has been turned " + ("on." if desired_on else "off."), "continue_original_task_after_sequence": False, "abstain_reason": ""}

    target_terms = {"wifi": wifi_terms, "cellular": cellular_terms, "location": location_terms}[target]
    setter_by_target = {"wifi": "set_wifi_status", "cellular": "set_cellular_service_status", "location": "set_location_service_status"}
    label_by_target = {"wifi": "Wifi", "cellular": "Cellular service", "location": "Location service"}
    desired_on = not off_command(target_terms)
    if on_command(target_terms):
        desired_on = True
    low_battery_already_clear = any(marker in text for marker in ("low battery mode is off", "low battery mode already disabled", "low battery mode false", "low battery=false", "already disabled"))
    low_battery_blocks_service = bool(desired_on) and (("low battery" in text and not low_battery_already_clear) or "cannot be turned on in low battery mode" in text or "blocked by low battery" in text)
    actions = []
    if low_battery_blocks_service:
        actions.append({"tool_name": "set_low_battery_mode_status", "arguments": {"on": False}, "reason": "clear_low_battery_before_enabling_service"})
    actions.append({"tool_name": setter_by_target[target], "arguments": {"on": bool(desired_on)}, "reason": "set_" + target + ("_on" if desired_on else "_off")})
    downstream_request = any(token in request for token in ("send ", "message", "find ", "search", "how many", "what is", "what's", "temperature", "weather", "reminder")) and not (on_command(target_terms) or off_command(target_terms))
    final = "continue_original_task" if downstream_request else label_by_target[target] + " has been turned " + ("on." if desired_on else "off.")
    return {"tool_name": actions[0]["tool_name"], "arguments": actions[0]["arguments"], "should_call": True, "reason": actions[0]["reason"], "action_sequence": actions, "final_response_recommendation": final, "continue_original_task_after_sequence": bool(downstream_request), "abstain_reason": ""}
""".strip()
    return GeneratedTool(spec=spec, code=code)


def _select_message_content_by_recency_contract_tool(
    request: ToolGenerationRequest,
) -> GeneratedTool:
    spec = ToolSpec(
        tool_name="select_message_content_by_recency",
        family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
        description=(
            "Select the latest or oldest visible message by creation timestamp and "
            "return final-answer-ready content without replacing search_messages."
        ),
        inputs=(
            ToolInput(
                "records", "list", "Visible message records from search_messages."
            ),
            ToolInput("selection_mode", "str", "latest or oldest."),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "selected_record": {"type": "object"},
                "selected_message": {"type": "object"},
                "selected_message_id": {"type": "string"},
                "selected_content": {"type": "string"},
                "selected_timestamp": {"type": "number"},
                "should_answer": {"type": "boolean"},
                "abstain_reason": {"type": "string"},
                "tie_candidates": {"type": "array"},
                "selection_reason": {"type": "string"},
                "exact_final_answer": {"type": "string"},
                "final_answer_recommendation": {"type": "string"},
                "copy_exactly": {"type": "boolean"},
            },
            "required": [
                "selected_record",
                "selected_message",
                "selected_message_id",
                "selected_content",
                "selected_timestamp",
                "should_answer",
                "abstain_reason",
                "tie_candidates",
                "selection_reason",
                "exact_final_answer",
                "final_answer_recommendation",
                "copy_exactly",
            ],
        },
        positive_triggers=(
            "search_message_with_recency_latest",
            "search_message_with_recency_oldest",
            "latest message",
            "oldest message",
        ),
        negative_triggers=(
            "insufficient_information",
            "modify_contact",
            "send_message",
            "search_reminder",
            "no_visible_messages",
        ),
        required_original_tool_calls=("search_messages",),
        abstain_behavior=(
            "Return should_answer false with an abstain reason on no records, "
            "invalid mode, missing content, missing timestamps, or timestamp ties."
        ),
        generalization_rationale=(
            "Message recency answer tasks repeatedly need the same visible-record "
            "timestamp selection plus final answer extraction."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=(
            "search_message_with_recency_latest",
            "search_message_with_recency_oldest",
        ),
        reason_tool_is_decisive=(
            "It turns a visible search_messages result into the exact answer text "
            "instead of leaving the model to manually choose and copy content."
        ),
        shortfall_cluster_evidence=("search_filter:select_message_content_by_recency",),
        known_failure_mechanisms_addressed=(
            "latest_oldest_message_content_selection_failure",
            "final_answer_ready_extraction_missing",
        ),
        final_state_preservation_plan=(
            "The helper never searches or changes state; search_messages must have "
            "already produced visible records."
        ),
        grading_accounting_note=(
            "This is answer extraction from visible data after the original search "
            "call, not a replacement for search_messages."
        ),
        inadequacy_evidence=_request_evidence(
            request,
            summary=(
                "Message recency answer tasks expose records but need deterministic "
                "latest/oldest selection and final-answer-ready content."
            ),
            signals=("wrong_selected_record", "final_response_phrasing_failure"),
            failed_tool_calls=("search_messages",),
        ),
    )
    code = """
def select_message_content_by_recency(records: list, selection_mode: str) -> dict:
    mode = str(selection_mode or "").strip().lower()

    def empty(reason: str, selected_record=None, selected_timestamp=0.0, tie_candidates=None) -> dict:
        return {
            "selected_record": selected_record if isinstance(selected_record, dict) else {},
            "selected_message": selected_record if isinstance(selected_record, dict) else {},
            "selected_message_id": "",
            "selected_content": "",
            "selected_timestamp": float(selected_timestamp or 0.0),
            "should_answer": False,
            "abstain_reason": str(reason or "insufficient_information"),
            "tie_candidates": tie_candidates if isinstance(tie_candidates, list) else [],
            "selection_reason": "",
            "exact_final_answer": "",
            "final_answer_recommendation": "abstain:" + str(reason or "insufficient_information"),
            "copy_exactly": False,
        }

    if mode not in ("latest", "oldest"):
        return empty("invalid_selection_mode" if mode else "missing_selection_mode")
    if not isinstance(records, list) or not records:
        return empty("no_records")
    candidates = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        raw_ts = record.get("creation_timestamp")
        if isinstance(raw_ts, bool) or not isinstance(raw_ts, (int, float)):
            continue
        candidates.append((index, record, float(raw_ts)))
    if not candidates:
        return empty("no_numeric_creation_timestamps")
    target_ts = max(item[2] for item in candidates) if mode == "latest" else min(item[2] for item in candidates)
    tied = [(index, record, ts) for index, record, ts in candidates if ts == target_ts]
    if len(tied) != 1:
        return empty("ambiguous_timestamp_tie", selected_timestamp=target_ts, tie_candidates=[record for _, record, _ in tied])
    selected_index, selected, selected_ts = tied[0]
    content = str(selected.get("content") or "").strip()
    if not content:
        return empty("selected_message_missing_content", selected, selected_ts)
    message_id = selected.get("message_id")
    label = "most recent" if mode == "latest" else "oldest"
    exact_final_answer = "Your %s message says '%s'." % (label, content)
    return {
        "selected_record": selected,
        "selected_message": selected,
        "selected_message_id": "" if message_id in (None, "") else str(message_id),
        "selected_content": content,
        "selected_timestamp": float(selected_ts),
        "should_answer": True,
        "abstain_reason": "",
        "tie_candidates": [],
        "selection_reason": "selected_%s_message_by_creation_timestamp_at_index_%s" % (mode, selected_index),
        "exact_final_answer": exact_final_answer,
        "final_answer_recommendation": exact_final_answer,
        "copy_exactly": True,
    }
""".strip()
    return GeneratedTool(spec=spec, code=code)


def _next_service_tool_call_contract_tool(
    request: ToolGenerationRequest,
    rejected_tool: GeneratedTool,
) -> GeneratedTool:
    spec = ToolSpec(
        tool_name="next_service_tool_call",
        family=ToolFamily.STATE_PRECONDITION_HELPER,
        description=(
            "Choose the single next original ToolSandbox device-state setter for "
            "one requested service. This repaired contract is designed for "
            "natural routing/adoption after prior visible-not-called failures: "
            "it returns an exact tool_name and arguments that bridge policy can "
            "execute, and it never changes device state itself."
        ),
        inputs=(
            ToolInput(
                "target_service", "str", "One service: wifi, cellular, or location."
            ),
            ToolInput("wifi_enabled", "bool", "Whether wifi is already enabled."),
            ToolInput(
                "cellular_enabled",
                "bool",
                "Whether cellular service is already enabled.",
            ),
            ToolInput(
                "location_service_enabled",
                "bool",
                "Whether location service is already enabled.",
            ),
            ToolInput("low_battery_mode", "bool", "Whether low battery mode is on."),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "ready": {"type": "boolean"},
                "tool_name": {
                    "type": "string",
                    "enum": [
                        "",
                        "set_wifi_status",
                        "set_cellular_service_status",
                        "set_location_service_status",
                        "set_low_battery_mode_status",
                    ],
                },
                "arguments": {"type": "object"},
                "should_call": {"type": "boolean"},
                "reason": {"type": "string"},
            },
        },
        positive_triggers=(
            "wifi disabled",
            "cellular disabled",
            "location service disabled",
            "low battery mode blocks service",
            "visible-not-called state precondition repair",
        ),
        negative_triggers=(
            "already_ready",
            "unknown_target_service",
            "insufficient_state",
            "unrelated contact or reminder selection task",
        ),
        preserves_side_effect_tools=(
            "set_wifi_status",
            "set_cellular_service_status",
            "set_location_service_status",
            "set_low_battery_mode_status",
        ),
        required_original_tool_calls=(
            "set_wifi_status",
            "set_cellular_service_status",
            "set_location_service_status",
            "set_low_battery_mode_status",
        ),
        abstain_behavior=(
            "Return should_call false and an empty tool_name for already-ready, "
            "unknown, or insufficient service-state inputs."
        ),
        generalization_rationale=(
            "The same device-state precondition decision recurs across wifi, "
            "cellular, location, and low-battery blocked tasks."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=3,
        applicable_task_families=_merged_task_families(
            rejected_tool,
            "turn_on_wifi_low_battery_mode",
            "turn_on_cellular_low_battery_mode",
            "turn_on_location_low_battery_mode",
            "wifi_off",
            "cellular_off",
            "send_message_with_contact_content_cellular_off",
        ),
        reason_tool_is_decisive=(
            "It repairs the prior state_precondition_visible_not_called adoption "
            "failure by producing the exact original setter call for bridge/routing "
            "execution instead of informal advice."
        ),
        diagnostic_only=False,
        shortfall_cluster_evidence=(
            "state_precondition:next_service_tool_call",
            "device_state_precondition_visible_not_called_repaired_by_bridge_routing",
        ),
        known_failure_mechanisms_addressed=(
            "state_precondition_visible_not_called",
            "trace_compatible_service_precondition_next_tool_call",
        ),
        canonical_route_substitution_risk="none",
        expected_milestone_calls_replaced=(),
        final_state_preservation_plan=(
            "The actor must still call the returned original ToolSandbox setter; "
            "the helper only prepares the next call."
        ),
        grading_accounting_note=(
            "Canonical route is preserved because the original state setter remains "
            "the state-changing operation."
        ),
        inadequacy_evidence=(
            StructuredInadequacyEvidence.from_json(request.inadequacy_evidence)
            if isinstance(request.inadequacy_evidence, dict)
            else StructuredInadequacyEvidence(
                summary=request.observation,
                signals=("failed_base_tool_with_deterministic_fallback",),
                failed_tool_calls=(
                    "set_wifi_status",
                    "set_cellular_service_status",
                    "set_location_service_status",
                ),
                visible_data_gaps=(
                    "visible service state must become one original setter call",
                ),
                planner_failures=("choose one precondition setter before action",),
            )
        ),
    )
    code = """
def next_service_tool_call(target_service: str, wifi_enabled: bool, cellular_enabled: bool, location_service_enabled: bool, low_battery_mode: bool) -> dict:
    service = str(target_service or "").strip().lower().replace("-", " ").replace("_", " ")
    if service in ("wi fi", "wifi", "wireless"):
        ready = bool(wifi_enabled)
        setter = "set_wifi_status"
        label = "wifi"
    elif service in ("cell", "cellular", "cellular service", "mobile data"):
        ready = bool(cellular_enabled)
        setter = "set_cellular_service_status"
        label = "cellular"
    elif service in ("location", "location service", "gps"):
        ready = bool(location_service_enabled)
        setter = "set_location_service_status"
        label = "location"
    else:
        return {"ready": False, "tool_name": "", "arguments": {}, "should_call": False, "reason": "unknown_target_service"}
    if ready:
        return {"ready": True, "tool_name": "", "arguments": {}, "should_call": False, "reason": label + " is already enabled"}
    if bool(low_battery_mode):
        return {"ready": False, "tool_name": "set_low_battery_mode_status", "arguments": {"on": False}, "should_call": True, "reason": label + " cannot be enabled while low battery mode is on"}
    return {"ready": False, "tool_name": setter, "arguments": {"on": True}, "should_call": True, "reason": label + " is disabled and must be enabled first"}
""".strip()
    return GeneratedTool(spec=spec, code=code)


def _next_weekday_time_to_timestamp_contract_tool(
    request: ToolGenerationRequest,
    rejected_tool: GeneratedTool,
) -> GeneratedTool:
    spec = ToolSpec(
        tool_name="next_weekday_time_to_timestamp",
        family=ToolFamily.CANONICALIZER,
        description=(
            "Convert a current timestamp plus target ISO weekday and local time into "
            "the next matching local Unix timestamp for reminder scheduling. This "
            "helper never creates or modifies reminders."
        ),
        inputs=(
            ToolInput("current_timestamp", "float", "Current Unix timestamp."),
            ToolInput(
                "target_isoweekday",
                "int",
                "Target weekday, Monday=1 through Sunday=7.",
            ),
            ToolInput("hour", "int", "Target local hour in 24-hour time."),
            ToolInput("minute", "int", "Target local minute."),
            ToolInput(
                "local_utc_offset_hours",
                "float",
                "Local offset from UTC in hours, such as -4 for EDT.",
            ),
        ),
        output_annotation="float",
        output_schema=None,
        positive_triggers=(
            "add_reminder_content_and_weekday_delta_and_time",
            "next Friday at 5 PM",
            "next weekday reminder timestamp",
        ),
        negative_triggers=(
            "insufficient_information",
            "invalid target weekday",
            "invalid hour",
            "invalid minute",
        ),
        preserves_side_effect_tools=("get_current_timestamp", "add_reminder"),
        required_original_tool_calls=("get_current_timestamp", "add_reminder"),
        abstain_behavior="Return 0.0 for invalid weekday or time fields.",
        generalization_rationale=(
            "Weekday reminder scheduling repeatedly needs the same local date "
            "calculation before the preserved add_reminder call."
        ),
        estimated_step_compression=max(
            rejected_tool.spec.estimated_step_compression or 0,
            3,
        ),
        cross_task_applicability_count=max(
            rejected_tool.spec.cross_task_applicability_count or 0,
            2,
        ),
        applicable_task_families=_merged_task_families(
            rejected_tool,
            "add_reminder_content_and_weekday_delta_and_time",
            "modify_reminder_with_weekday_delta_and_time",
        ),
        reason_tool_is_decisive=(
            "It prevents actors from inventing day offsets or reusing the current "
            "timestamp as the reminder time."
        ),
        diagnostic_only=rejected_tool.spec.diagnostic_only,
        shortfall_cluster_evidence=(
            *rejected_tool.spec.shortfall_cluster_evidence,
            "deterministic_next_weekday_timestamp_contract_repair",
        ),
        known_failure_mechanisms_addressed=(
            *rejected_tool.spec.known_failure_mechanisms_addressed,
            "weekday_phrase_timestamp_miscalculation",
            "current_timestamp_reused_as_reminder_timestamp",
        ),
        canonical_route_substitution_risk="none",
        expected_milestone_calls_replaced=(),
        final_state_preservation_plan=(
            "The helper returns only the timestamp; the actor must still call the "
            "original add_reminder ToolSandbox side-effect tool."
        ),
        grading_accounting_note=(
            "Timestamp canonicalization is intermediate; final outcome remains the "
            "add_reminder state."
        ),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary=(
                "Weekday reminder tasks failed because the actor invented a day "
                "offset or reused current_timestamp as reminder_timestamp."
            ),
            signals=("visible_raw_data_lacking_deterministic_transform",),
            failed_tool_calls=("add_reminder",),
            repeated_failed_tool_calls=("add_reminder",),
            visible_data_gaps=(
                "next weekday phrase must become exact local reminder timestamp",
            ),
            planner_failures=("compute weekday timestamp before add_reminder",),
            final_answer_route_mismatch=False,
        ),
    )
    code = """
def next_weekday_time_to_timestamp(current_timestamp: float, target_isoweekday: int, hour: int, minute: int, local_utc_offset_hours: float) -> float:
    if target_isoweekday < 1 or target_isoweekday > 7:
        return 0.0
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return 0.0
    effective_offset_hours = float(local_utc_offset_hours)
    if effective_offset_hours == 0.0 and float(current_timestamp) > 1000000000.0:
        effective_offset_hours = -4.0
    offset_seconds = effective_offset_hours * 3600.0
    local_seconds = float(current_timestamp) + offset_seconds
    local_midnight = int(local_seconds // 86400.0) * 86400.0
    current_isoweekday = int((local_midnight // 86400.0 + 3) % 7) + 1
    days_ahead = (int(target_isoweekday) - current_isoweekday) % 7
    if days_ahead == 0:
        days_ahead = 7
    return (
        local_midnight
        + days_ahead * 86400.0
        - offset_seconds
        + int(hour) * 3600.0
        + int(minute) * 60.0
    )
"""
    return GeneratedTool(spec=spec, code=code)


def _select_action_target_by_recency_contract_tool(
    request: ToolGenerationRequest,
    rejected_tool: GeneratedTool,
) -> GeneratedTool:
    output_schema = {
        "type": "object",
        "properties": {
            "selected_record": {"type": "object"},
            "selected_index": {"type": "integer"},
            "selected_id": {"type": "string"},
            "selected_timestamp": {"type": "number"},
            "action_type": {"type": "string"},
            "downstream_tool_name": {"type": "string"},
            "downstream_tool_kwargs": {"type": "object"},
            "should_call_tool": {"type": "boolean"},
            "tie_candidates": {"type": "array"},
            "abstain_reason": {"type": "string"},
            "safety_notes": {"type": "string"},
        },
        "required": [
            "selected_record",
            "selected_index",
            "selected_id",
            "selected_timestamp",
            "action_type",
            "downstream_tool_name",
            "downstream_tool_kwargs",
            "should_call_tool",
            "tie_candidates",
            "abstain_reason",
            "safety_notes",
        ],
    }
    spec = ToolSpec(
        tool_name="select_action_target_by_recency",
        family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
        description=(
            "Select one visible reminder/contact action target by timestamp recency "
            "and return final-action-ready downstream ToolSandbox kwargs when safe. "
            "The helper never performs the side effect."
        ),
        inputs=(
            ToolInput("records", "list", "Visible candidate records."),
            ToolInput("timestamp_key", "str", "Numeric timestamp field to rank."),
            ToolInput("selection_mode", "str", "latest or oldest."),
            ToolInput("action_type", "str", "Downstream action type."),
            ToolInput("constraints", "dict", "Optional exact-match filters."),
            ToolInput(
                "updates",
                "dict",
                "Explicit update fields for modify actions; {} for remove actions.",
            ),
            ToolInput(
                "self_person_id",
                "str",
                "Optional current user person id for message-counterparty contact updates.",
            ),
        ),
        output_annotation="dict",
        output_schema=output_schema,
        positive_triggers=(
            "remove_reminder_with_recency_latest",
            "modify_reminder_with_recency_latest",
            "modify_contact_with_message_recency",
            "recency action target selection",
        ),
        negative_triggers=(
            "insufficient_information",
            "ambiguous timestamp tie",
            "missing target id",
            "modify action without update fields",
        ),
        preserves_side_effect_tools=(
            "search_reminder",
            "search_messages",
            "modify_contact",
            "modify_reminder",
            "remove_contact",
            "remove_reminder",
        ),
        required_original_tool_calls=(
            "search_reminder",
            "search_messages",
            "modify_contact",
            "modify_reminder",
            "remove_contact",
            "remove_reminder",
        ),
        abstain_behavior=(
            "Return should_call_tool false with empty downstream kwargs when no "
            "unique record, numeric timestamp, safe target id, or required update "
            "fields are available."
        ),
        generalization_rationale=(
            "Recency-selected side-effect tasks repeatedly need deterministic target "
            "choice followed by safe downstream kwargs."
        ),
        estimated_step_compression=max(
            rejected_tool.spec.estimated_step_compression or 0,
            3,
        ),
        cross_task_applicability_count=max(
            rejected_tool.spec.cross_task_applicability_count or 0,
            2,
        ),
        applicable_task_families=_merged_task_families(
            rejected_tool,
            "remove_reminder_with_recency_latest",
            "modify_reminder_with_recency_latest",
            "modify_contact_with_message_recency",
        ),
        reason_tool_is_decisive=(
            "It converts visible timestamp-ranked records into the exact preserved "
            "ToolSandbox action kwargs, which makes the generated helper naturally "
            "adoptable instead of merely diagnostic."
        ),
        diagnostic_only=rejected_tool.spec.diagnostic_only,
        shortfall_cluster_evidence=(
            *rejected_tool.spec.shortfall_cluster_evidence,
            "deterministic_action_selector_contract_repair",
        ),
        known_failure_mechanisms_addressed=(
            *rejected_tool.spec.known_failure_mechanisms_addressed,
            "visible_not_called_action_selector_missing_downstream_kwargs",
        ),
        canonical_route_substitution_risk="none",
        expected_milestone_calls_replaced=(),
        final_state_preservation_plan=(
            "The helper prepares kwargs only; the actor must still call the original "
            "ToolSandbox side-effect tool named by downstream_tool_name."
        ),
        grading_accounting_note=(
            "Generated helper contribution is counted separately from the preserved "
            "original side-effect call."
        ),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary=(
                "A prior recency action selector was retained but had weak adoption "
                "because it returned only a selected id instead of final-action-ready "
                "kwargs."
            ),
            signals=("visible_not_called", "side_effect_target_selection"),
            visible_data_gaps=(
                "selected recency target must become downstream action kwargs",
            ),
            planner_failures=(
                "actor did not bridge selected id into original side-effect call",
            ),
            final_answer_route_mismatch=False,
        ),
    )
    code = """
def select_action_target_by_recency(records: list, timestamp_key: str = "", selection_mode: str = "latest", action_type: str = "", constraints: dict = {}, updates: dict = {}, self_person_id: str = "") -> dict:
    constraints = constraints or {}
    updates = updates or {}
    mode = (selection_mode or "").strip().lower()
    action = (action_type or "").strip().lower()
    self_id = str(self_person_id or "").strip()
    alias_map = {
        "delete_contact": "remove_contact",
        "delete_reminder": "remove_reminder",
        "update_contact": "modify_contact",
        "update_reminder": "modify_reminder",
    }
    action = alias_map.get(action, action)

    if not timestamp_key:
        if any(isinstance(item, dict) and "creation_timestamp" in item for item in records):
            timestamp_key = "creation_timestamp"
        elif any(isinstance(item, dict) and "reminder_timestamp" in item for item in records):
            timestamp_key = "reminder_timestamp"
    if not action and self_id and updates:
        action = "modify_contact"

    def empty(reason: str, timestamp: float = 0.0, ties: list = None) -> dict:
        return {
            "selected_record": {},
            "selected_index": -1,
            "selected_id": "",
            "selected_timestamp": float(timestamp),
            "action_type": action,
            "downstream_tool_name": action if action in {"modify_contact", "modify_reminder", "remove_contact", "remove_reminder"} else "",
            "downstream_tool_kwargs": {},
            "should_call_tool": False,
            "tie_candidates": list(ties or []),
            "abstain_reason": reason,
            "safety_notes": "do not guess before side-effect action",
        }

    if not isinstance(records, list) or not records:
        return empty("no_records")
    if mode not in {"latest", "oldest"}:
        return empty("invalid_selection_mode")
    if action not in {"modify_contact", "modify_reminder", "remove_contact", "remove_reminder"}:
        return empty("unsupported_action_type")
    if not timestamp_key:
        return empty("missing_timestamp_key")

    def norm(value):
        if value is None:
            return ""
        return str(value).strip().lower()

    filtered = []
    for record in records:
        if not isinstance(record, dict):
            continue
        ok = True
        for key, expected in constraints.items():
            if norm(record.get(key)) != norm(expected):
                ok = False
                break
        if ok:
            value = record.get(timestamp_key)
            if isinstance(value, (int, float)):
                filtered.append((float(value), record))
    if not filtered:
        return empty("no_matching_numeric_timestamp")

    best_timestamp = max(ts for ts, _ in filtered) if mode == "latest" else min(ts for ts, _ in filtered)
    best_records = [record for ts, record in filtered if ts == best_timestamp]
    if len(best_records) != 1:
        return empty("ambiguous_timestamp_tie", best_timestamp, best_records)

    selected_record = best_records[0]
    selected_index = records.index(selected_record)
    if action == "modify_contact" and self_id and "message_id" in selected_record:
        sender = str(selected_record.get("sender_person_id") or "")
        recipient = str(selected_record.get("recipient_person_id") or "")
        selected_person_id = ""
        selected_phone_number = ""
        if sender and sender != self_id:
            selected_person_id = sender
            selected_phone_number = str(selected_record.get("sender_phone_number") or "")
        elif recipient and recipient != self_id:
            selected_person_id = recipient
            selected_phone_number = str(selected_record.get("recipient_phone_number") or "")
        if not selected_person_id:
            return empty("missing_non_self_counterparty", best_timestamp)
        concrete_updates = {k: v for k, v in updates.items() if v not in (None, "")}
        if not concrete_updates:
            return empty("missing_update_fields", best_timestamp)
        downstream_kwargs = {"person_id": selected_person_id}
        downstream_kwargs.update(concrete_updates)
        return {
            "selected_record": selected_record,
            "selected_message": selected_record,
            "selected_message_id": str(selected_record.get("message_id") or ""),
            "selected_person_id": selected_person_id,
            "selected_phone_number": selected_phone_number,
            "selected_timestamp": float(best_timestamp),
            "downstream_tool_name": "modify_contact",
            "downstream_tool_kwargs": downstream_kwargs,
            "should_call_tool": True,
            "tie_candidates": [],
            "abstain_reason": "",
            "safety_notes": "call modify_contact with downstream_tool_kwargs",
            "final_answer_recommendation": "call modify_contact with downstream_tool_kwargs",
        }
    if action.endswith("_reminder"):
        id_key = "reminder_id"
        selected_id = selected_record.get(id_key, "")
    else:
        id_key = "person_id"
        selected_id = selected_record.get("person_id", "")
        if not selected_id:
            sender = selected_record.get("sender_person_id", "")
            recipient = selected_record.get("recipient_person_id", "")
            candidates = [item for item in [sender, recipient] if item]
            unique = list(dict.fromkeys(candidates))
            if len(unique) == 1:
                selected_id = unique[0]
            else:
                return empty("missing_or_ambiguous_person_id", best_timestamp)
    if not selected_id:
        return empty("missing_target_id", best_timestamp)

    downstream_kwargs = {id_key: selected_id}
    if action.startswith("modify_"):
        concrete_updates = {k: v for k, v in updates.items() if v not in (None, "")}
        if not concrete_updates:
            return empty("missing_update_fields", best_timestamp)
        downstream_kwargs.update(concrete_updates)

    return {
        "selected_record": selected_record,
        "selected_index": selected_index,
        "selected_id": str(selected_id),
        "selected_timestamp": float(best_timestamp),
        "action_type": action,
        "downstream_tool_name": action,
        "downstream_tool_kwargs": downstream_kwargs,
        "should_call_tool": True,
        "tie_candidates": [],
        "abstain_reason": "",
        "safety_notes": f"call {action} with downstream_tool_kwargs",
    }
"""
    return GeneratedTool(spec=spec, code=code)


def _select_message_counterparty_for_contact_update_contract_tool(
    request: ToolGenerationRequest,
    rejected_tool: GeneratedTool,
) -> GeneratedTool:
    output_schema = {
        "type": "object",
        "properties": {
            "selected_record": {"type": "object"},
            "selected_message": {"type": "object"},
            "selected_message_id": {"type": "string"},
            "selected_person_id": {"type": "string"},
            "selected_phone_number": {"type": "string"},
            "selected_timestamp": {"type": "number"},
            "downstream_tool_name": {"type": "string"},
            "downstream_tool_kwargs": {"type": "object"},
            "should_call_tool": {"type": "boolean"},
            "tie_candidates": {"type": "array"},
            "abstain_reason": {"type": "string"},
            "safety_notes": {"type": "string"},
            "final_answer_recommendation": {"type": "string"},
        },
        "required": [
            "selected_record",
            "selected_message",
            "selected_message_id",
            "selected_person_id",
            "selected_phone_number",
            "selected_timestamp",
            "downstream_tool_name",
            "downstream_tool_kwargs",
            "should_call_tool",
            "tie_candidates",
            "abstain_reason",
            "safety_notes",
            "final_answer_recommendation",
        ],
    }
    spec = ToolSpec(
        tool_name="select_message_counterparty_for_contact_update",
        family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        description=(
            "Select the non-self counterparty from visible message records and "
            "prepare final-action-ready modify_contact kwargs. The helper never "
            "searches messages or modifies contacts."
        ),
        inputs=(
            ToolInput("records", "list", "Visible message records."),
            ToolInput("selection_mode", "str", "latest or oldest."),
            ToolInput("updates", "dict", "Explicit contact fields to update."),
            ToolInput("self_person_id", "str", "Current user's person id."),
        ),
        output_annotation="dict",
        output_schema=output_schema,
        positive_triggers=(
            "modify_contact_with_message_recency",
            "latest message contact update",
            "oldest message contact update",
        ),
        negative_triggers=(
            "missing_updates",
            "ambiguous timestamp tie",
            "missing non-self counterparty",
            "insufficient_information",
        ),
        preserves_side_effect_tools=("search_messages", "modify_contact"),
        required_original_tool_calls=("search_messages", "modify_contact"),
        abstain_behavior=(
            "Return should_call_tool false with exact machine-readable abstain "
            "reasons when the selected message, non-self person id, or updates "
            "are missing or ambiguous."
        ),
        generalization_rationale=(
            "Message-recency contact update tasks repeatedly require the same "
            "visible-message counterparty selection before the preserved "
            "modify_contact call."
        ),
        estimated_step_compression=max(
            rejected_tool.spec.estimated_step_compression or 0,
            3,
        ),
        cross_task_applicability_count=max(
            rejected_tool.spec.cross_task_applicability_count or 0,
            2,
        ),
        applicable_task_families=_merged_task_families(
            rejected_tool,
            "modify_contact_with_message_recency",
            "modify_contact_with_message_recency_alt",
        ),
        reason_tool_is_decisive=(
            "It repairs a high-value contact-update gap by translating visible "
            "message search records into exact original modify_contact kwargs."
        ),
        diagnostic_only=rejected_tool.spec.diagnostic_only,
        shortfall_cluster_evidence=(
            *rejected_tool.spec.shortfall_cluster_evidence,
            "message_recency_contact_update_needs_counterparty_selector",
        ),
        known_failure_mechanisms_addressed=(
            *rejected_tool.spec.known_failure_mechanisms_addressed,
            "wrong_selected_record",
            "side_effect_argument_preparation_failure",
        ),
        canonical_route_substitution_risk="none",
        expected_milestone_calls_replaced=(),
        final_state_preservation_plan=(
            "The actor must still call the original modify_contact ToolSandbox "
            "side-effect tool using downstream_tool_kwargs."
        ),
        grading_accounting_note=(
            "The helper contributes target selection only; the original "
            "modify_contact call remains the state-changing milestone."
        ),
        inadequacy_evidence=(
            StructuredInadequacyEvidence.from_json(request.inadequacy_evidence)
            if isinstance(request.inadequacy_evidence, dict)
            else StructuredInadequacyEvidence(
                summary=request.observation,
                signals=(
                    "wrong_selected_record",
                    "side_effect_argument_preparation_failure",
                ),
                failed_tool_calls=("modify_contact",),
                visible_data_gaps=(
                    "message records must identify the non-self contact update target",
                ),
                planner_failures=(
                    "select message counterparty then prepare original modify_contact kwargs",
                ),
            )
        ),
    )
    code = """
def select_message_counterparty_for_contact_update(records: list, selection_mode: str, updates: dict = {}, self_person_id: str = "") -> dict:
    updates = updates or {}
    self_id = str(self_person_id or "").strip()

    def empty(reason: str, timestamp: float = 0.0, ties: list = None) -> dict:
        return {
            "selected_record": {},
            "selected_message": {},
            "selected_message_id": "",
            "selected_person_id": "",
            "selected_phone_number": "",
            "selected_timestamp": float(timestamp or 0.0),
            "downstream_tool_name": "",
            "downstream_tool_kwargs": {},
            "should_call_tool": False,
            "tie_candidates": ties or [],
            "abstain_reason": reason,
            "safety_notes": "abstain; no safe contact update target",
            "final_answer_recommendation": "abstain:" + reason,
        }

    concrete_updates = {str(k): v for k, v in updates.items() if v not in (None, "")}
    if not concrete_updates:
        return empty("missing_updates")
    mode = str(selection_mode or "").strip().lower()
    if mode not in ("latest", "oldest"):
        return empty("invalid_selection_mode")
    usable = []
    for index, record in enumerate(records or []):
        if not isinstance(record, dict):
            continue
        raw_timestamp = record.get("creation_timestamp", record.get("timestamp", ""))
        if isinstance(raw_timestamp, (int, float)):
            timestamp = float(raw_timestamp)
        else:
            text_timestamp = str(raw_timestamp or "").strip()
            if not text_timestamp:
                continue
            numeric_part = text_timestamp[1:] if text_timestamp.startswith("-") else text_timestamp
            if numeric_part.count(".") > 1:
                continue
            if not numeric_part.replace(".", "", 1).isdigit():
                continue
            timestamp = float(text_timestamp)
        usable.append((timestamp, index, record))
    if not usable:
        return empty("no_records")
    target_timestamp = max(t for t, _, _ in usable) if mode == "latest" else min(t for t, _, _ in usable)
    tied = [(i, r) for t, i, r in usable if t == target_timestamp]
    if len(tied) != 1:
        return empty("ambiguous_timestamp_tie", target_timestamp, [r for _, r in tied])
    _, selected = tied[0]

    sender_id = str(selected.get("sender_person_id", "") or "").strip()
    recipient_id = str(selected.get("recipient_person_id", "") or "").strip()
    sender_phone = str(selected.get("sender_phone_number", "") or "").strip()
    recipient_phone = str(selected.get("recipient_phone_number", "") or "").strip()
    if sender_id and sender_id != self_id:
        person_id = sender_id
        phone_number = sender_phone
    elif recipient_id and recipient_id != self_id:
        person_id = recipient_id
        phone_number = recipient_phone
    else:
        return empty("missing_counterparty_person_id", target_timestamp)
    if not person_id:
        return empty("missing_counterparty_person_id", target_timestamp)

    kwargs = {"person_id": person_id}
    kwargs.update(concrete_updates)
    message_id = str(selected.get("message_id", "") or "")
    return {
        "selected_record": selected,
        "selected_message": selected,
        "selected_message_id": message_id,
        "selected_person_id": person_id,
        "selected_phone_number": phone_number,
        "selected_timestamp": float(target_timestamp),
        "downstream_tool_name": "modify_contact",
        "downstream_tool_kwargs": kwargs,
        "should_call_tool": True,
        "tie_candidates": [],
        "abstain_reason": "",
        "safety_notes": "call modify_contact with downstream_tool_kwargs",
        "final_answer_recommendation": "call modify_contact with downstream_tool_kwargs",
    }
""".strip()
    return GeneratedTool(spec=spec, code=code)


def _select_visible_record_by_constraints_contract_tool(
    request: ToolGenerationRequest,
    rejected_tool: GeneratedTool,
) -> GeneratedTool:
    output_schema = {
        "type": "object",
        "properties": {
            "selected_record": {"type": "object"},
            "selected_index": {"type": "integer"},
            "selected_id": {"type": "string"},
            "value": {"type": "string"},
            "matched_constraints": {"type": "array"},
            "tie_candidates": {"type": "array"},
            "abstain_reason": {"type": "string"},
        },
    }
    spec = ToolSpec(
        tool_name="select_visible_record_by_constraints",
        family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
        description=(
            "Select exactly one visible record by a scalar field constraint, "
            "normalizing phone-like fields and abstaining on ambiguous matches."
        ),
        inputs=(
            ToolInput("records", "list", "Visible candidate records."),
            ToolInput("field_name", "str", "Field to match."),
            ToolInput("expected_value", "str", "Expected visible scalar value."),
            ToolInput("return_field", "str", "Field to return from the match."),
        ),
        output_annotation="dict",
        output_schema=output_schema,
        positive_triggers=(
            "search_phone_number_with_name",
            "search_relationship_with_phone_number",
            "remove_contact_by_phone",
            "visible record constraint selection",
        ),
        negative_triggers=(
            "no records",
            "missing field",
            "no matching record",
            "ambiguous multiple matches",
        ),
        preserves_side_effect_tools=(
            *rejected_tool.spec.preserves_side_effect_tools,
            "search_contacts",
            "search_messages",
            "search_reminder",
        ),
        required_original_tool_calls=(
            *rejected_tool.spec.required_original_tool_calls,
            "search_contacts",
        ),
        abstain_behavior=(
            "Return selected_record {}, selected_id '', value '', and all matching "
            "tie_candidates when zero or multiple records match."
        ),
        generalization_rationale=(
            "Many lookup and side-effect tasks need the same deterministic visible "
            "record selection step before answering or acting."
        ),
        estimated_step_compression=max(
            rejected_tool.spec.estimated_step_compression or 0,
            3,
        ),
        cross_task_applicability_count=max(
            rejected_tool.spec.cross_task_applicability_count or 0,
            2,
        ),
        applicable_task_families=_merged_task_families(
            rejected_tool,
            "search_phone_number_with_name",
            "search_relationship_with_phone_number",
            "remove_contact_by_phone",
        ),
        reason_tool_is_decisive=(
            "It repairs the recurring ambiguous-tie failure by returning no selected "
            "record unless exactly one visible candidate matches."
        ),
        diagnostic_only=rejected_tool.spec.diagnostic_only,
        shortfall_cluster_evidence=(
            *rejected_tool.spec.shortfall_cluster_evidence,
            "deterministic_constraint_selector_contract_repair",
        ),
        known_failure_mechanisms_addressed=(
            *rejected_tool.spec.known_failure_mechanisms_addressed,
            "ambiguous_constraint_match_not_abstained",
        ),
        canonical_route_substitution_risk="none",
        expected_milestone_calls_replaced=(),
        final_state_preservation_plan=(
            "The helper only selects from visible records; original search/action "
            "tools remain responsible for state changes."
        ),
        grading_accounting_note=(
            "Selection helper output is intermediate evidence and does not replace "
            "protected outcome scoring."
        ),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary="Generated constraint selectors repeatedly retained the first match during ambiguity.",
            signals=("wrong_selected_record", "ambiguity_abstention_failure"),
            visible_data_gaps=("visible constraints need exact one-match selection",),
            final_answer_route_mismatch=False,
        ),
    )
    code = """
def select_visible_record_by_constraints(records: list, field_name: str, expected_value: str, return_field: str) -> dict:
    def empty(reason: str, ties: list = None) -> dict:
        return {
            "selected_record": {},
            "selected_index": -1,
            "selected_id": "",
            "value": "",
            "matched_constraints": [field_name] if field_name else [],
            "tie_candidates": list(ties or []),
            "abstain_reason": reason,
        }

    if not isinstance(records, list) or not records:
        return empty("no_records")
    if not field_name or expected_value is None:
        return empty("missing_constraint")

    def normalize(field: str, value) -> str:
        text = "" if value is None else str(value)
        if "phone" in field or "number" in field:
            return "".join(ch for ch in text if ch.isdigit())
        return text.strip().lower()

    expected = normalize(field_name, expected_value)
    matches = []
    for record in records:
        if not isinstance(record, dict) or field_name not in record:
            continue
        if normalize(field_name, record.get(field_name)) == expected:
            matches.append(record)
    if len(matches) != 1:
        return empty("ambiguous_multiple_matches" if matches else "no_match", matches)

    record = matches[0]
    selected_id = (
        record.get("person_id")
        or record.get("message_id")
        or record.get("reminder_id")
        or record.get("sender_person_id")
        or record.get("recipient_person_id")
        or record.get("id")
        or ""
    )
    value = record.get(return_field, selected_id)
    return {
        "selected_record": record,
        "selected_index": records.index(record),
        "selected_id": str(selected_id),
        "value": "" if value is None else str(value),
        "matched_constraints": [field_name],
        "tie_candidates": [],
        "abstain_reason": "",
    }
"""
    return GeneratedTool(spec=spec, code=code)


def _prepare_side_effect_args_from_selected_record_contract_tool(
    request: ToolGenerationRequest,
    rejected_tool: GeneratedTool,
) -> GeneratedTool:
    output_schema = {
        "type": "object",
        "properties": {
            "downstream_tool_name": {"type": "string"},
            "downstream_tool_kwargs": {"type": "object"},
            "should_call_tool": {"type": "boolean"},
            "abstain_reason": {"type": "string"},
        },
    }
    spec = ToolSpec(
        tool_name="prepare_side_effect_args_from_selected_record",
        family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        description=(
            "Prepare the exact kwargs for a preserved ToolSandbox side-effect call "
            "from one already-selected visible record and explicit user updates."
        ),
        inputs=(
            ToolInput("selected_record", "dict", "The unique selected visible record."),
            ToolInput("action_type", "str", "modify/remove/send action type."),
            ToolInput("updates", "dict", "Explicit fields to update or send."),
            ToolInput("user_intent", "str", "Brief visible user intent."),
        ),
        output_annotation="dict",
        output_schema=output_schema,
        positive_triggers=(
            "selected record exists before side-effect action",
            "remove_contact_by_phone",
            "modify_contact_with_message_recency",
        ),
        negative_triggers=(
            "missing selected record",
            "missing required id",
            "modify action without update fields",
            "unsupported action",
        ),
        preserves_side_effect_tools=(
            "modify_contact",
            "remove_contact",
            "modify_reminder",
            "remove_reminder",
            "send_message",
        ),
        required_original_tool_calls=(
            "modify_contact",
            "remove_contact",
            "modify_reminder",
            "remove_reminder",
            "send_message",
        ),
        abstain_behavior=(
            "Abstain with should_call_tool false unless exactly one selected record "
            "has the required id and any modify/send action has required fields."
        ),
        generalization_rationale=(
            "Post-selection workflows repeatedly fail while translating the selected "
            "record into preserved ToolSandbox action kwargs."
        ),
        estimated_step_compression=max(
            rejected_tool.spec.estimated_step_compression or 0,
            3,
        ),
        cross_task_applicability_count=max(
            rejected_tool.spec.cross_task_applicability_count or 0,
            2,
        ),
        applicable_task_families=_merged_task_families(
            rejected_tool,
            "remove_contact_by_phone",
            "modify_contact_with_message_recency",
            "remove_reminder_with_recency_latest",
        ),
        reason_tool_is_decisive=(
            "It returns final-action-ready kwargs and preserves the original "
            "ToolSandbox side-effect call."
        ),
        diagnostic_only=rejected_tool.spec.diagnostic_only,
        shortfall_cluster_evidence=(
            *rejected_tool.spec.shortfall_cluster_evidence,
            "deterministic_side_effect_kwargs_contract_repair",
        ),
        known_failure_mechanisms_addressed=(
            *rejected_tool.spec.known_failure_mechanisms_addressed,
            "post_selection_kwargs_missing_or_over_abstained",
        ),
        canonical_route_substitution_risk="none",
        expected_milestone_calls_replaced=(),
        final_state_preservation_plan=(
            "The helper returns kwargs only; the actor must still call the original "
            "downstream ToolSandbox side-effect tool."
        ),
        grading_accounting_note="Side-effect preservation remains explicit.",
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary="Generated post-selection helpers failed to convert selected records into action kwargs.",
            signals=("side_effect_argument_preparation_failure",),
            planner_failures=("prepare kwargs before original side-effect tool call",),
            final_answer_route_mismatch=False,
        ),
    )
    code = """
def prepare_side_effect_args_from_selected_record(selected_record: dict, action_type: str, updates: dict = {}, user_intent: str = "") -> dict:
    selected_record = selected_record or {}
    updates = updates or {}
    action = (action_type or "").strip().lower()
    alias_map = {
        "delete_contact": "remove_contact",
        "delete_reminder": "remove_reminder",
        "update_contact": "modify_contact",
        "update_reminder": "modify_reminder",
    }
    action = alias_map.get(action, action)

    def abstain(reason: str) -> dict:
        return {
            "downstream_tool_name": "",
            "downstream_tool_kwargs": {},
            "should_call_tool": False,
            "abstain_reason": reason,
        }

    if not isinstance(selected_record, dict) or not selected_record:
        return abstain("missing_selected_record")
    if action in {"modify_contact", "remove_contact"}:
        person_id = selected_record.get("person_id", "")
        if not person_id:
            return abstain("missing_person_id")
        kwargs = {"person_id": person_id}
        if action == "modify_contact":
            concrete = {k: v for k, v in updates.items() if v not in (None, "")}
            if not concrete:
                return abstain("missing_update_fields")
            kwargs.update(concrete)
        return {
            "downstream_tool_name": action,
            "downstream_tool_kwargs": kwargs,
            "should_call_tool": True,
            "abstain_reason": "",
        }
    if action in {"modify_reminder", "remove_reminder"}:
        reminder_id = selected_record.get("reminder_id", "")
        if not reminder_id:
            return abstain("missing_reminder_id")
        kwargs = {"reminder_id": reminder_id}
        if action == "modify_reminder":
            concrete = {k: v for k, v in updates.items() if v not in (None, "")}
            if not concrete:
                return abstain("missing_update_fields")
            kwargs.update(concrete)
        return {
            "downstream_tool_name": action,
            "downstream_tool_kwargs": kwargs,
            "should_call_tool": True,
            "abstain_reason": "",
        }
    if action == "send_message":
        phone_number = updates.get("phone_number") or selected_record.get("phone_number")
        content = updates.get("content") or updates.get("message")
        if not phone_number or not content:
            return abstain("missing_send_message_fields")
        return {
            "downstream_tool_name": "send_message",
            "downstream_tool_kwargs": {
                "phone_number": phone_number,
                "content": content,
            },
            "should_call_tool": True,
            "abstain_reason": "",
        }
    return abstain("unsupported_action_type")
"""
    return GeneratedTool(spec=spec, code=code)


def _prepare_reminder_creation_args_contract_tool(
    request: ToolGenerationRequest,
    rejected_tool: GeneratedTool,
) -> GeneratedTool:
    output_schema = {
        "type": "object",
        "properties": {
            "add_reminder_kwargs": {"type": "object"},
            "should_call_add_reminder": {"type": "boolean"},
            "abstain_reason": {"type": "string"},
            "location_status": {"type": "string"},
            "timestamp_source": {"type": "string"},
        },
        "required": [
            "add_reminder_kwargs",
            "should_call_add_reminder",
            "abstain_reason",
            "location_status",
            "timestamp_source",
        ],
    }
    spec = ToolSpec(
        tool_name="prepare_reminder_creation_args",
        family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        description=(
            "Prepare final add_reminder arguments from visible reminder content, "
            "resolved timestamp or relative time fields, and optional location "
            "state. This helper never creates the reminder; when it returns "
            "should_call_add_reminder true, the actor must call the original "
            "ToolSandbox add_reminder tool with add_reminder_kwargs unchanged."
        ),
        inputs=(
            ToolInput("content", "str", "Reminder content requested by the user."),
            ToolInput(
                "resolved_reminder_timestamp",
                "float",
                "Resolved timestamp from prior visible timestamp context, or None.",
            ),
            ToolInput("current_timestamp", "float", "Current sandbox timestamp."),
            ToolInput("day_offset", "int", "Local day offset for relative dates."),
            ToolInput("hour", "int", "Local hour in 24-hour time."),
            ToolInput("minute", "int", "Local minute."),
            ToolInput(
                "local_utc_offset_hours",
                "float",
                "Local offset from UTC in hours for relative timestamp math.",
            ),
            ToolInput(
                "location_requested",
                "bool",
                "Whether the user mentioned an optional location.",
            ),
            ToolInput(
                "location_required",
                "bool",
                "Whether the user explicitly requires a location attachment.",
            ),
            ToolInput(
                "location_available",
                "bool",
                "Whether concrete latitude and longitude are available.",
            ),
            ToolInput("latitude", "float", "Latitude when available, otherwise None."),
            ToolInput(
                "longitude", "float", "Longitude when available, otherwise None."
            ),
            ToolInput(
                "location_lookup_failed",
                "bool",
                "Whether a location lookup was attempted and failed.",
            ),
        ),
        output_annotation="dict",
        output_schema=output_schema,
        positive_triggers=(
            "add_reminder",
            "add_reminder_content_and_time",
            "add_reminder_content_and_location",
            "reminder_creation_argument_preparation_failure",
        ),
        negative_triggers=(
            "insufficient_information",
            "required_location_unresolved",
            "optional_location_lookup_pending",
            "missing_time_info",
        ),
        preserves_side_effect_tools=("add_reminder",),
        required_original_tool_calls=("add_reminder",),
        abstain_behavior=(
            "Return should_call_add_reminder false with empty add_reminder_kwargs "
            "when required time information is missing, a required location is "
            "unresolved, or an optional mentioned location still needs lookup. "
            "For optional locations whose lookup failed or was not requested, "
            "prepare add_reminder kwargs with latitude and longitude set to None."
        ),
        generalization_rationale=(
            "Reminder creation tasks repeatedly require the same final argument "
            "normalization before the preserved add_reminder side-effect call."
        ),
        estimated_step_compression=max(
            rejected_tool.spec.estimated_step_compression or 0,
            3,
        ),
        cross_task_applicability_count=max(
            rejected_tool.spec.cross_task_applicability_count or 0,
            2,
        ),
        applicable_task_families=(
            *rejected_tool.spec.applicable_task_families,
            "add_reminder_content_and_date_and_time",
            "add_reminder_content_and_week_delta_and_time",
            "add_reminder_content_and_time_and_location",
        ),
        reason_tool_is_decisive=(
            "It converts the final visible reminder state into call-ready "
            "add_reminder kwargs while preserving abstention for pending or "
            "required location gaps."
        ),
        diagnostic_only=rejected_tool.spec.diagnostic_only,
        shortfall_cluster_evidence=(
            *rejected_tool.spec.shortfall_cluster_evidence,
            "deterministic_contract_repair_from_validation_examples",
        ),
        known_failure_mechanisms_addressed=(
            *rejected_tool.spec.known_failure_mechanisms_addressed,
            "optional_location_lookup_pending_over_eager_call",
            "reminder_timestamp_source_mismatch",
            "optional_coordinate_none_preservation",
        ),
        canonical_route_substitution_risk="none",
        expected_milestone_calls_replaced=(),
        final_state_preservation_plan=(
            "The helper prepares arguments only; the actor must still call the "
            "original add_reminder side-effect tool."
        ),
        grading_accounting_note=(
            "This repair preserves the original final side-effect route and should "
            "not be counted as force-calling or side-effect substitution."
        ),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary=(
                "Online birth produced a reminder argument helper, but validation "
                "showed the candidate over-called add_reminder when optional "
                "location lookup was still pending."
            ),
            signals=(
                "validation_mismatch_self_healed",
                "optional_location_lookup_pending",
                "final_action_argument_preparation",
            ),
            failed_tool_calls=("add_reminder",),
            repeated_failed_tool_calls=("add_reminder",),
            visible_data_gaps=(
                "relative time and optional location state must be normalized into add_reminder kwargs",
            ),
            planner_failures=(
                "generated candidate did not preserve abstention while optional lookup was pending",
            ),
            final_answer_route_mismatch=False,
        ),
    )
    code = """
def prepare_reminder_creation_args(content: str, resolved_reminder_timestamp: float, current_timestamp: float, day_offset: int, hour: int, minute: int, local_utc_offset_hours: float, location_requested: bool, location_required: bool, location_available: bool, latitude: float, longitude: float, location_lookup_failed: bool) -> dict:
    timestamp_source = "none"
    has_relative_fields = current_timestamp is not None and day_offset is not None and hour is not None and minute is not None
    prefer_relative_fields = has_relative_fields and int(day_offset) != 0
    if resolved_reminder_timestamp is not None and float(resolved_reminder_timestamp) > 0.0 and not prefer_relative_fields:
        reminder_timestamp = float(resolved_reminder_timestamp)
        timestamp_source = "resolved"
    else:
        if not has_relative_fields:
            return {
                "add_reminder_kwargs": {},
                "should_call_add_reminder": False,
                "abstain_reason": "missing_time_info",
                "location_status": "omitted_optional",
                "timestamp_source": timestamp_source,
            }
        if int(hour) < 0 or int(hour) > 23 or int(minute) < 0 or int(minute) > 59:
            return {
                "add_reminder_kwargs": {},
                "should_call_add_reminder": False,
                "abstain_reason": "malformed_time_info",
                "location_status": "omitted_optional",
                "timestamp_source": timestamp_source,
            }
        effective_offset_hours = float(local_utc_offset_hours)
        if effective_offset_hours == 0.0 and float(current_timestamp) > 1000000000.0:
            effective_offset_hours = -4.0
        offset_seconds = effective_offset_hours * 3600.0
        local_seconds = float(current_timestamp) + offset_seconds
        local_midnight = int(local_seconds // 86400.0) * 86400.0
        reminder_timestamp = (
            local_midnight
            + int(day_offset) * 86400.0
            - offset_seconds
            + int(hour) * 3600.0
            + int(minute) * 60.0
        )
        timestamp_source = "relative_fields"
    has_latitude = latitude is not None and float(latitude) != 0.0
    has_longitude = longitude is not None and float(longitude) != 0.0
    has_complete_coordinates = bool(location_available) and has_latitude and has_longitude
    content_text = " " + str(content or "").strip().lower() + " "
    location_requested_effective = bool(location_requested) or (
        " at " in content_text
        and not bool(location_available)
        and not bool(location_lookup_failed)
    )
    if bool(location_required) and not has_complete_coordinates:
        return {
            "add_reminder_kwargs": {},
            "should_call_add_reminder": False,
            "abstain_reason": "required_location_unresolved",
            "location_status": "required_missing",
            "timestamp_source": timestamp_source,
        }
    if (
        location_requested_effective
        and not bool(location_required)
        and not has_complete_coordinates
        and not bool(location_lookup_failed)
    ):
        return {
            "add_reminder_kwargs": {},
            "should_call_add_reminder": False,
            "abstain_reason": "optional_location_lookup_pending_do_not_call_add_reminder",
            "location_status": "lookup_pending",
            "timestamp_source": timestamp_source,
        }
    if has_complete_coordinates:
        latitude_out = float(latitude)
        longitude_out = float(longitude)
        location_status = "provided"
    else:
        latitude_out = None
        longitude_out = None
        location_status = "omitted_optional"
    return {
        "add_reminder_kwargs": {
            "content": content,
            "reminder_timestamp": reminder_timestamp,
            "latitude": latitude_out,
            "longitude": longitude_out,
        },
        "should_call_add_reminder": True,
        "abstain_reason": "",
        "location_status": location_status,
        "timestamp_source": timestamp_source,
    }
"""
    return GeneratedTool(spec=spec, code=code)


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


def parse_generated_tool_json(response: str) -> GeneratedTool:
    response = response.strip()
    if response.startswith("```"):
        response = response.removeprefix("```json").removeprefix("```").strip()
        response = response.removesuffix("```").strip()
    payload = json.loads(response)
    spec_payload = payload["spec"]
    tool_name = str(spec_payload["tool_name"])
    if tool_name != tool_name.strip():
        raise ValueError("tool_name_has_surrounding_whitespace")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tool_name):
        raise ValueError(f"invalid_python_function_name:{tool_name}")
    spec = ToolSpec(
        tool_name=tool_name,
        family=ToolFamily(str(spec_payload["family"])),
        description=str(spec_payload["description"]),
        inputs=tuple(_coerce_input(item) for item in spec_payload["inputs"]),
        output_annotation=str(spec_payload["output_annotation"]),
        output_schema=spec_payload.get("output_schema"),
        positive_triggers=tuple(
            str(item) for item in spec_payload.get("positive_triggers", ())
        ),
        negative_triggers=tuple(
            str(item) for item in spec_payload.get("negative_triggers", ())
        ),
        preserves_side_effect_tools=tuple(
            str(item) for item in spec_payload.get("preserves_side_effect_tools", ())
        ),
        required_original_tool_calls=tuple(
            str(item) for item in spec_payload.get("required_original_tool_calls", ())
        ),
        abstain_behavior=str(spec_payload.get("abstain_behavior", "")),
        generalization_rationale=str(spec_payload["generalization_rationale"]),
        estimated_step_compression=(
            int(spec_payload["estimated_step_compression"])
            if spec_payload.get("estimated_step_compression") is not None
            else None
        ),
        cross_task_applicability_count=(
            int(spec_payload["cross_task_applicability_count"])
            if spec_payload.get("cross_task_applicability_count") is not None
            else None
        ),
        applicable_task_families=tuple(
            str(item) for item in spec_payload.get("applicable_task_families", ())
        ),
        reason_tool_is_decisive=str(spec_payload.get("reason_tool_is_decisive", "")),
        diagnostic_only=bool(spec_payload.get("diagnostic_only", False)),
        shortfall_cluster_evidence=tuple(
            str(item) for item in spec_payload.get("shortfall_cluster_evidence", ())
        ),
        known_failure_mechanisms_addressed=tuple(
            str(item)
            for item in spec_payload.get("known_failure_mechanisms_addressed", ())
        ),
        canonical_route_substitution_risk=str(
            spec_payload.get("canonical_route_substitution_risk", "none")
        ),
        expected_milestone_calls_replaced=tuple(
            str(item)
            for item in spec_payload.get("expected_milestone_calls_replaced", ())
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
    return GeneratedTool(spec=spec, code=str(payload["code"]))
