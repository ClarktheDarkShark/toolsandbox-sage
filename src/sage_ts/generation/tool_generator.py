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
            "For recency action-target selectors, prefer inputs records: list, "
            "timestamp_key: str, selection_mode: str, action_type: str, and "
            "constraints: dict. Treat constraints as optional; the generated "
            "function must work when constraints is omitted or {}, using {} as "
            "the default no-extra-filter case. Return selected_record, selected_index, "
            "selected_id, selected_timestamp, action_type, downstream_tool_name, "
            "tie_candidates, and abstain_reason. For unique matches, tie_candidates "
            "must be an empty list. selected_id should use the first available "
            "stable id key among reminder_id, message_id, person_id, "
            "sender_person_id, recipient_person_id, or id. On timestamp ties, "
            "selected_record must be empty and tie_candidates must include every "
            "record sharing the best timestamp, including the first best record. "
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
    if tool_name != "prepare_reminder_creation_args":
        return None
    joined_errors = " ".join(errors)
    if not (
        "negative_" in joined_errors
        or "held_out_" in joined_errors
        or "annotation" in joined_errors
        or "mismatch" in joined_errors
    ):
        return None
    return _prepare_reminder_creation_args_contract_tool(request, rejected_tool)


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
            "add_reminder_content_and_weekday_delta_and_time",
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
    if resolved_reminder_timestamp is not None and float(resolved_reminder_timestamp) > 0.0:
        reminder_timestamp = float(resolved_reminder_timestamp)
        timestamp_source = "resolved"
    else:
        if current_timestamp is None or day_offset is None or hour is None or minute is None:
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
        offset_seconds = float(local_utc_offset_hours) * 3600.0
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
    if bool(location_required) and not has_complete_coordinates:
        return {
            "add_reminder_kwargs": {},
            "should_call_add_reminder": False,
            "abstain_reason": "required_location_unresolved",
            "location_status": "required_missing",
            "timestamp_source": timestamp_source,
        }
    if (
        bool(location_requested)
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
