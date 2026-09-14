"""Online conversion from repeated observations to accepted helper tools."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import time
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Protocol

from sage_ts.adequacy.candidate_gate import evaluate_candidate_gate
from sage_ts.adequacy.failure_memory import generation_failure_memory_context
from sage_ts.adequacy.inadequacy_classifier import (
    CapabilityObservation,
    classify_visible_task_observations,
)
from sage_ts.evaluation.task_strata import base_task_family
from sage_ts.generation.complete_tools import COMPLETE_TOOLS_NATIVE_NAMES
from sage_ts.generation.tool_generator import (
    ToolGenerationRequest,
    public_input_contract_from_example_inputs,
    public_output_contract_from_example_outputs,
)
from sage_ts.generation.tool_spec import (
    GeneratedTool,
    ToolFamily,
)
from sage_ts.orchestration.checkpoints import append_jsonl
from sage_ts.registry.manifest import (
    RegistryEntry,
    code_hash,
    has_current_validation_proof,
)
from sage_ts.registry.store import RegistryStore
from sage_ts.registry.validation_contracts import (
    ResolvedValidationContract,
    ValidationContractBindingStore,
)
from sage_ts.validation.sandbox_validator import (
    ToolExample,
    ValidationResult,
    validate_generated_tool,
)


class GeneratedToolFactory(Protocol):
    def generate(self, request: ToolGenerationRequest) -> GeneratedTool: ...


CampaignEventHook = Callable[[str, dict[str, Any]], None]
RepairAcknowledgementHook = Callable[..., dict[str, Any]]


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
REPAIR_STAGNATION_DUPLICATE_CANDIDATE_LABEL = "repair_stagnation_duplicate_candidate"
MAX_REJECTIONS_PER_TOOL_KEY = 2
POST_DEPLOYMENT_CANARY_REQUIRED_ATTRIBUTABLE_OBSERVATIONS = 3
POST_DEPLOYMENT_CANARY_REQUIRED_EXACT_SUCCESSES = 2
POST_DEPLOYMENT_CANARY_REQUIRED_FRESH_CONTROL_SUCCESS_FLIPS = 1
POST_DEPLOYMENT_CANARY_MAX_FAMILY_TASKS = 8
POST_DEPLOYMENT_REPAIR_STATE_FILENAME = "post_deployment_repair_state.json"
POST_DEPLOYMENT_REPAIR_REQUEST_FILENAME = "self_evolution_tool_repair_requests.jsonl"
POST_DEPLOYMENT_REPAIR_ACKNOWLEDGEMENT_FILENAME = (
    "self_evolution_tool_repair_acknowledgements.jsonl"
)
POST_DEPLOYMENT_REPAIR_CANDIDATE_FILENAME = "post_deployment_repair_candidates.jsonl"
POST_DEPLOYMENT_REPAIR_CANDIDATE_SCHEMA_VERSION = 2
POST_DEPLOYMENT_REPAIR_PUBLIC_EVIDENCE_FIELDS = frozenset(
    {
        "called_count",
        "visible_count",
        "public_visible_context_count",
        "contract_failure_count",
        "failed_count",
    }
)
_PROHIBITED_REPAIR_PAYLOAD_EXACT_KEYS = frozenset(
    {
        "scenario_name",
        "scenario_names",
        "scenario_id",
        "scenario_ids",
        "task_id",
        "task_ids",
        "expected_answer",
        "expected_answers",
        "gold_answer",
        "gold_answers",
        "reference_answer",
        "reference_answers",
        "target_state",
        "expected_target_state",
        "evaluator_trace",
        "evaluator_traces",
        "evaluator_result",
        "evaluator_results",
    }
)
_PROHIBITED_REPAIR_PROMPT_TOKENS = (
    "candidate_outcome",
    "control_outcome",
    "outcome_similarity",
    "success_flip",
    "task_id",
    "scenario_id",
    "expected_answer",
    "target_state",
    "evaluator_trace",
)
_GENERIC_REPAIR_CONTEXT_PATTERN = re.compile(
    r"post_deployment_repair\(kind=(?:implementation|metadata);"
    r"family=[a-z0-9_.:-]+\)"
)
_SHA256_HEX_PATTERN = re.compile(r"[0-9a-f]{64}")


def _canonical_json_hash(payload: Any) -> str:
    """Hash one JSON payload independently of presentation formatting."""

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _generated_tool_evidence(tool: GeneratedTool) -> dict[str, Any]:
    """Return an exact tool payload plus independently checkable identities."""

    tool_payload = tool.to_json()
    spec_payload = tool.spec.to_json()
    return {
        "tool": tool_payload,
        "code_sha256": code_hash(tool.code),
        "spec_sha256": _canonical_json_hash(spec_payload),
        "tool_payload_sha256": _canonical_json_hash(tool_payload),
    }


def _append_evidence_jsonl(path: Path, payload: dict[str, Any]) -> None:
    """Append and sync one integrity-critical evidence record."""

    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, sort_keys=True, allow_nan=False) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def _metadata_implementation_proof(
    *,
    source_code_hash: str,
    replacement_code_hash: str | None,
    replacement_activated: bool,
    model_authored_code_change_discarded: bool,
) -> dict[str, Any]:
    """Describe whether a metadata-only repair preserved executable behavior."""

    source_hash = str(source_code_hash or "").strip().lower()
    replacement_hash = (
        str(replacement_code_hash or "").strip().lower()
        if replacement_code_hash is not None
        else None
    )
    source_valid = _SHA256_HEX_PATTERN.fullmatch(source_hash) is not None
    replacement_valid = bool(
        replacement_hash and _SHA256_HEX_PATTERN.fullmatch(replacement_hash) is not None
    )
    implementation_preserved = bool(
        source_valid
        and (
            (not replacement_activated and replacement_hash is None)
            or (
                replacement_activated
                and replacement_valid
                and replacement_hash == source_hash
            )
        )
    )
    return {
        "proof_schema_version": 1,
        "repair_kind": "metadata",
        "source_code_hash": source_hash,
        "replacement_code_hash": replacement_hash,
        "replacement_activated": replacement_activated,
        "implementation_preserved": implementation_preserved,
        "model_authored_code_change_discarded": (model_authored_code_change_discarded),
    }


def prohibited_repair_payload_paths(
    payload: Any,
    *,
    allow_generic_root_scenario_name: bool = False,
) -> tuple[str, ...]:
    """Recursively locate evaluator-private fields in a repair payload.

    Aggregate execution/adoption counts and prospective task ordinals are public
    operational evidence. Scenario/task identifiers, evaluator artifacts, and
    scalar reward values are not generator inputs. ``scenario_name`` is allowed
    only for the required, synthetic ``ToolGenerationRequest`` context label.
    """

    violations: list[str] = []

    def visit(value: Any, path: tuple[str, ...]) -> None:
        if isinstance(value, dict):
            for raw_key, child in value.items():
                key = re.sub(r"[^a-z0-9]+", "_", str(raw_key).strip().lower()).strip(
                    "_"
                )
                compact_key = key.replace("_", "")
                child_path = (*path, str(raw_key))
                generic_root_label = bool(
                    allow_generic_root_scenario_name
                    and not path
                    and key == "scenario_name"
                    and isinstance(child, str)
                    and _GENERIC_REPAIR_CONTEXT_PATTERN.fullmatch(child)
                )
                prohibited = bool(
                    key in _PROHIBITED_REPAIR_PAYLOAD_EXACT_KEYS
                    or compact_key in {"scenarioname", "scenarionames"}
                    or key.endswith(
                        (
                            "_scenario_id",
                            "_scenario_ids",
                            "_task_id",
                            "_task_ids",
                        )
                    )
                    or compact_key.endswith(
                        ("scenarioid", "scenarioids", "taskid", "taskids")
                    )
                    or "expectedanswer" in compact_key
                    or "targetstate" in compact_key
                    or "evaluatortrace" in compact_key
                    or "outcome" in compact_key
                    or "successflip" in compact_key
                )
                if prohibited and not generic_root_label:
                    violations.append("$." + ".".join(child_path))
                visit(child, child_path)
        elif isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                visit(child, (*path, f"[{index}]"))

    visit(payload, ())
    return tuple(dict.fromkeys(violations))


def _assert_repair_payload_safe(
    payload: Any,
    *,
    label: str,
    allow_generic_root_scenario_name: bool = False,
) -> None:
    violations = prohibited_repair_payload_paths(
        payload,
        allow_generic_root_scenario_name=allow_generic_root_scenario_name,
    )
    if violations:
        raise ValueError(
            f"{label} contains prohibited evaluator-private fields: "
            + ", ".join(violations)
        )


def _assert_repair_generation_request_safe(request: ToolGenerationRequest) -> None:
    """Audit both the structured request and the exact generator-facing prompt."""

    _assert_repair_payload_safe(
        asdict(request),
        label="post-deployment repair generation request",
        allow_generic_root_scenario_name=True,
    )
    prompt = request.prompt().lower()
    prompt_violations = [
        token for token in _PROHIBITED_REPAIR_PROMPT_TOKENS if token in prompt
    ]
    if prompt_violations:
        raise ValueError(
            "post-deployment repair generator prompt contains prohibited "
            "evaluator-private field tokens: " + ", ".join(prompt_violations)
        )


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


def _model_visible_generation_examples(
    examples: tuple[ToolExample, ...],
) -> tuple[ToolExample, ...]:
    """Keep claim-grade validation cases out of model generation prompts.

    Explicitly marked held-out cases are never shown to the generator.  Older
    contracts without markers reserve their final non-negative case, matching
    the validator's legacy partition.  Negative-applicability examples remain
    part of the public generation contract.
    """

    marked_held_out = {
        index for index, example in enumerate(examples) if example.held_out
    }
    if marked_held_out:
        return tuple(
            example
            for index, example in enumerate(examples)
            if index not in marked_held_out
        )
    non_negative_indexes = [
        index
        for index, example in enumerate(examples)
        if not example.negative_applicability
    ]
    if len(non_negative_indexes) < 2:
        return examples
    reserved_index = non_negative_indexes[-1]
    return tuple(
        example for index, example in enumerate(examples) if index != reserved_index
    )


def _repair_prompt_errors(errors: tuple[str, ...]) -> tuple[str, ...]:
    """Remove held-out values while retaining actionable invariant labels."""

    sanitized: list[str] = []
    for raw_error in errors:
        error = str(raw_error)
        if error.startswith(("held_out_", "blind_property_")):
            error = error.split(":", 1)[0]
        elif "expected=" in error:
            error = error.split(":expected=", 1)[0]
        if error and error not in sanitized:
            sanitized.append(error)
    return tuple(sanitized)


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
            "undefined_name:",
            "generated_tool_name_mismatch:",
            "input_signature_mismatch:",
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
    # Non-visible trace observations use their public capability identifier.
    # A private benchmark scenario name must never become generation/routing
    # metadata merely because a caller omitted a visible family label.
    return _normalize_family_label(observation.canonical_key.replace(":", "_"))


SCENARIO_VARIANT_MARKERS = (
    "distraction_tools",
    "arg_description_scrambled",
    "arg_type_scrambled",
    "tool_description_scrambled",
    "tool_name_scrambled",
    "insufficient_information",
    "multiple_user_turn",
    "all_tools",
)


def _scenario_like_label(item: str) -> bool:
    """Identify dataset/robustness labels by shape, not benchmark prefixes."""

    value = str(item or "").strip().lower()
    if not value:
        return False
    normalized = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    segments = tuple(part for part in normalized.split("_") if part)
    return bool(
        any(marker in normalized for marker in SCENARIO_VARIANT_MARKERS)
        or re.search(r"(?:^|_)\d+_distraction(?:_|$)", normalized)
        or len(segments) >= 9
        or len(normalized) > 80
    )


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

    Generation models sometimes emit full robustness-variant scenario labels as
    ``applicable_task_families``. Those names are valid evidence lineage, but
    they are too narrow for natural reuse and can hide an otherwise useful
    helper on later tasks from the same semantic family. Normalize them into
    labels derived from visible task context or public capability identifiers,
    and add the same labels as trigger tokens so routing never depends on a
    private benchmark name.
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
    if visible_context_observation:
        for item in VISIBLE_ROUTING_FAMILIES_BY_KEY.get(observation.canonical_key, ()):
            family_candidates.extend(_expanded_family_labels(item))
    elif not family_candidates:
        family_candidates.extend(_expanded_family_labels(observation.canonical_key))
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
                "phrase": "sample reminder created yesterday",
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
                "user_request": (
                    "Add a reminder to collect supplies at Example Market on "
                    "Fiction Avenue tomorrow."
                ),
                "location_phrase": "",
                "latitude": 0.0,
                "longitude": 0.0,
            },
            {
                "search_location_kwargs": {
                    "location": "Example Market on Fiction Avenue",
                },
                "should_call_downstream_tool": True,
                "downstream_tool_name": "search_location_around_lat_lon",
                "downstream_tool_kwargs": {
                    "location": "Example Market on Fiction Avenue",
                },
                "location_query": "Example Market on Fiction Avenue",
                "abstain_reason": "",
            },
        ),
        ToolExample(
            {
                "user_request": "Add a reminder to collect notes at Sample Library.",
                "location_phrase": "Sample Library",
                "latitude": 0.0,
                "longitude": 0.0,
            },
            {
                "search_location_kwargs": {},
                "should_call_downstream_tool": False,
                "downstream_tool_name": "",
                "downstream_tool_kwargs": {},
                "location_query": "Sample Library",
                "abstain_reason": "missing_reminder_time_before_location_lookup",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "user_request": "Sample Library on Fiction Boulevard",
                "location_phrase": "Sample Library",
                "latitude": 0.0,
                "longitude": 0.0,
            },
            {
                "search_location_kwargs": {
                    "location": "Sample Library on Fiction Boulevard",
                },
                "should_call_downstream_tool": True,
                "downstream_tool_name": "search_location_around_lat_lon",
                "downstream_tool_kwargs": {
                    "location": "Sample Library on Fiction Boulevard",
                },
                "location_query": "Sample Library on Fiction Boulevard",
                "abstain_reason": "",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "user_request": "Find an Example Market near me.",
                "location_phrase": "Example Market",
                "latitude": 0.0,
                "longitude": 0.0,
            },
            {
                "search_location_kwargs": {},
                "should_call_downstream_tool": True,
                "downstream_tool_name": "get_current_location",
                "downstream_tool_kwargs": {},
                "location_query": "Example Market",
                "abstain_reason": "need_current_coordinates_for_broad_location_query",
            },
        ),
        ToolExample(
            {
                "user_request": "Find a Sample Library near me.",
                "location_phrase": "Sample Library",
                "latitude": 35.123,
                "longitude": -80.456,
            },
            {
                "search_location_kwargs": {
                    "location": "Sample Library",
                    "latitude": 35.123,
                    "longitude": -80.456,
                },
                "should_call_downstream_tool": True,
                "downstream_tool_name": "search_location_around_lat_lon",
                "downstream_tool_kwargs": {
                    "location": "Sample Library",
                    "latitude": 35.123,
                    "longitude": -80.456,
                },
                "location_query": "Sample Library",
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
    failure_memory_path: Path | None = None
    pre_scenario_visible_observations: set[str] = field(default_factory=set)
    observations_by_tool_name: dict[str, CapabilityObservation] = field(
        default_factory=dict
    )
    pending_repair_requests: list[dict[str, Any]] = field(default_factory=list)
    handled_repair_request_ids: set[str] = field(default_factory=set)
    canary_state_by_tool: dict[str, dict[str, Any]] = field(default_factory=dict)
    repair_transactions_by_tool: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_completed_count: int = 0
    _validation_contract_store: ValidationContractBindingStore = field(
        init=False, repr=False
    )
    _validation_contract_restore_failures: dict[str, str] = field(
        init=False, default_factory=dict, repr=False
    )

    def __post_init__(self) -> None:
        self._validation_contract_store = ValidationContractBindingStore(
            self.store.root
        )
        restored, self._validation_contract_restore_failures = (
            self._validation_contract_store.restore(self.store.load_entries())
        )
        for tool_name, binding in restored.items():
            self._install_restored_contract(tool_name, binding)
        # An active implementation without its exact admission contract must
        # never remain routable after process restart. Development fixtures bind
        # explicitly before controller construction; there is no runtime backfill.
        for tool_name, reason in self._validation_contract_restore_failures.items():
            entry = self.store.get(tool_name)
            if entry is None or entry.retired:
                continue
            self.store.retire(tool_name)
            self._event(
                "validation_contract_restore_failed_entry_retired",
                {
                    "tool_name": tool_name,
                    "tool_version": entry.version,
                    "tool_code_hash": entry.stored_code_hash,
                    "binding_error": reason,
                    "entry_retired": True,
                    "repair_model_called": False,
                    "raw_hidden_case_values_logged": False,
                },
            )
        self._load_repair_state()

    def _install_restored_contract(
        self,
        tool_name: str,
        binding: ResolvedValidationContract,
    ) -> None:
        """Restore only synthetic public contract context, never task identity."""

        observation = binding.observation
        self.observations_by_tool_name[tool_name] = observation
        self.scenarios_by_key.setdefault(observation.canonical_key, set()).add(
            f"validation_contract:v{binding.tool_version}"
        )
        self.base_families_by_key.setdefault(observation.canonical_key, set()).add(
            _observation_family_key(observation)
        )

    def _resolve_validation_contract(
        self,
        entry: RegistryEntry,
    ) -> tuple[ResolvedValidationContract | None, str | None]:
        """Reverify the durable binding at each lifecycle decision boundary."""

        binding, error = self._validation_contract_store.resolve(entry)
        tool_name = entry.tool.spec.tool_name
        if binding is None:
            self.observations_by_tool_name.pop(tool_name, None)
            self._validation_contract_restore_failures[tool_name] = (
                error or "binding_invalid"
            )
            return None, error or "binding_invalid"
        self._validation_contract_restore_failures.pop(tool_name, None)
        self._install_restored_contract(tool_name, binding)
        return binding, None

    def _persist_validation_contract(
        self,
        entry: RegistryEntry,
        observation: CapabilityObservation,
        *,
        validation_examples: tuple[ToolExample, ...],
    ) -> ResolvedValidationContract:
        binding = self._validation_contract_store.persist(
            entry,
            observation,
            validation_examples=validation_examples,
        )
        self._install_restored_contract(entry.tool.spec.tool_name, binding)
        return binding

    @property
    def repair_state_path(self) -> Path:
        return self.output_dir / POST_DEPLOYMENT_REPAIR_STATE_FILENAME

    @property
    def repair_candidate_artifact_path(self) -> Path:
        return self.output_dir / POST_DEPLOYMENT_REPAIR_CANDIDATE_FILENAME

    def _persist_repair_candidate_artifact(
        self,
        *,
        request_id: str,
        tool_name: str,
        source_tool_version: int,
        repair_kind: str,
        completed_count: int,
        attempt: int,
        candidate_index: int,
        validation_contract_hash: str,
        source_tool_code_sha256: str,
        source_tool_spec_sha256: str,
        generator_candidate: GeneratedTool,
        evaluated_candidate: GeneratedTool | None,
        validation: ValidationResult | None,
        validation_score: int | None,
        selected_for_attempt: bool,
        disposition: str,
        failure_stage: str | None = None,
        failure_type: str | None = None,
    ) -> dict[str, Any]:
        """Append exact candidate evidence without validator-private values.

        The generator candidate is preserved separately from the tool actually
        evaluated because routing normalization can change metadata and a
        metadata-only repair deliberately restores the deployed source code.
        Validator errors are never serialized directly: the artifact contains
        only the same redacted frontier that is eligible to guide another repair.
        """

        if any(
            _SHA256_HEX_PATTERN.fullmatch(value) is None
            for value in (
                validation_contract_hash,
                source_tool_code_sha256,
                source_tool_spec_sha256,
            )
        ):
            raise ValueError(
                "Repair candidate evidence requires exact source-contract hashes."
            )

        if validation is None:
            sanitized_frontier = tuple(
                item
                for item in (
                    f"{failure_stage}:{failure_type}"
                    if failure_stage and failure_type
                    else failure_stage
                    or failure_type
                    or "candidate_validation_unavailable",
                )
                if item
            )
        else:
            sanitized_frontier = _repair_prompt_errors(validation.errors)
        if any(
            (item.startswith(("held_out_", "blind_property_")) and ":" in item)
            or "expected=" in item
            for item in sanitized_frontier
        ):
            raise ValueError(
                "Repair candidate evidence contains an unsanitized validation frontier."
            )

        validation_evidence = {
            "available": validation is not None,
            "accepted": bool(validation is not None and validation.accepted),
            "failure_score": validation_score,
            "source_example_count": (
                validation.source_example_count if validation is not None else None
            ),
            "held_out_check_count": (
                validation.held_out_check_count if validation is not None else None
            ),
            "negative_applicability_count": (
                validation.negative_applicability_count
                if validation is not None
                else None
            ),
            "runtime_smoke_passed": (
                validation.runtime_smoke_passed if validation is not None else None
            ),
            "sanitized_frontier": list(sanitized_frontier),
            "sanitized_frontier_count": len(sanitized_frontier),
            "raw_validation_errors_persisted": False,
        }
        record_payload: dict[str, Any] = {
            "schema_version": POST_DEPLOYMENT_REPAIR_CANDIDATE_SCHEMA_VERSION,
            "event": "post_deployment_tool_repair_candidate_recorded",
            "request_id": request_id,
            "tool_name": tool_name,
            "source_tool_version": source_tool_version,
            "repair_kind": repair_kind,
            "generated_after_completed_count": completed_count,
            "attempt": attempt,
            "candidate_index": candidate_index,
            "source_validation_contract_hash": validation_contract_hash,
            "source_tool_code_sha256": source_tool_code_sha256,
            "source_tool_spec_sha256": source_tool_spec_sha256,
            "generator_candidate": _generated_tool_evidence(generator_candidate),
            "evaluated_candidate": (
                _generated_tool_evidence(evaluated_candidate)
                if evaluated_candidate is not None
                else None
            ),
            "validation": validation_evidence,
            "selected_for_attempt": selected_for_attempt,
            "disposition": disposition,
            "failure_stage": failure_stage,
            "failure_type": failure_type,
            "future_tasks_only": True,
            "triggering_task_replayed": False,
            "evidence_policy": {
                "frontier": "generator_visible_sanitized_labels_only",
                "raw_validation_values_logged": False,
                "private_benchmark_fields_logged": False,
            },
        }
        _assert_repair_payload_safe(
            record_payload,
            label="post-deployment repair candidate artifact",
        )
        record_sha256 = _canonical_json_hash(record_payload)
        record = {**record_payload, "record_sha256": record_sha256}
        path = self.repair_candidate_artifact_path
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError(
                "Repair candidate evidence path must be a regular non-symlink file."
            )
        # Do not catch persistence errors. A repair must never be accepted or
        # retired without its exact candidate evidence having been durably added.
        _append_evidence_jsonl(path, record)
        return {
            "artifact_path": str(path),
            "artifact_schema_version": (
                POST_DEPLOYMENT_REPAIR_CANDIDATE_SCHEMA_VERSION
            ),
            "record_sha256": record_sha256,
        }

    @staticmethod
    def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows

    @staticmethod
    def _prepared_canary_state(
        *,
        request_id: str,
        tool_version: int,
        source_tool_version: int,
        target_task_family: str,
        eligible_from_completed_count: int,
    ) -> dict[str, Any]:
        """Create an empty, claim-grade prospective canary state."""

        return {
            "evidence_schema_version": 2,
            "request_id": request_id,
            "tool_version": tool_version,
            "source_tool_version": source_tool_version,
            "target_task_family": target_task_family,
            "eligible_from_completed_count": eligible_from_completed_count,
            "called_count": 0,
            "visible_count": 0,
            "eligible_family_task_count": 0,
            "outcomes": [],
            "outcome_deltas": [],
            "attributable_call_count": 0,
            "attributable_observation_count": 0,
            "exact_success_count": 0,
            "audited_regression_count": 0,
            "fresh_control_success_flip_count": 0,
            "version_mismatch_call_count": 0,
            "contract_failure_count": 0,
            "runtime_failure_count": 0,
        }

    @staticmethod
    def _nonnegative_int(value: Any, *, default: int = 0) -> int:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        return default

    def _normalize_loaded_canary_state(
        self,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """Preserve v2 evidence; reset untyped legacy soft evidence fail-closed."""

        request_id = str(state.get("request_id") or "")
        raw_version = state.get("tool_version")
        tool_version = (
            raw_version
            if isinstance(raw_version, int) and not isinstance(raw_version, bool)
            else 0
        )
        raw_source_version = state.get("source_tool_version")
        source_tool_version = (
            raw_source_version
            if isinstance(raw_source_version, int)
            and not isinstance(raw_source_version, bool)
            and raw_source_version > 0
            else max(tool_version - 1, 1)
        )
        raw_eligible = state.get("eligible_from_completed_count")
        eligible = (
            raw_eligible
            if isinstance(raw_eligible, int)
            and not isinstance(raw_eligible, bool)
            and raw_eligible > 0
            else self.last_completed_count + 1
        )
        if state.get("evidence_schema_version") != 2:
            reset = self._prepared_canary_state(
                request_id=request_id,
                tool_version=tool_version,
                source_tool_version=source_tool_version,
                target_task_family=self._normalized_task_family(
                    state.get("target_task_family")
                ),
                eligible_from_completed_count=eligible,
            )
            # Deterministic contract/runtime failures remain valid hard evidence;
            # old outcome/call counters lacked sufficient attribution metadata.
            reset["contract_failure_count"] = self._nonnegative_int(
                state.get("contract_failure_count")
            )
            reset["runtime_failure_count"] = self._nonnegative_int(
                state.get("runtime_failure_count")
            )
            return reset
        normalized = dict(state)
        defaults = self._prepared_canary_state(
            request_id=request_id,
            tool_version=tool_version,
            source_tool_version=source_tool_version,
            target_task_family=self._normalized_task_family(
                state.get("target_task_family")
            ),
            eligible_from_completed_count=eligible,
        )
        for key, value in defaults.items():
            normalized.setdefault(key, value)
        return normalized

    def _append_recovery_acknowledgement(
        self,
        *,
        request_id: str,
        tool_name: str,
        version: int,
        status: str,
        implementation_proof: dict[str, Any] | None = None,
    ) -> None:
        """Durably close a transaction recovered before hooks are constructed."""

        if not request_id or not tool_name or version < 1:
            return
        event: dict[str, Any] = {
            "event": "post_deployment_tool_repair_acknowledged",
            "schema_version": 1,
            "request_id": request_id,
            "tool_name": tool_name,
            "new_version": version,
            "status": status,
            "acknowledged_after_completed_count": self.last_completed_count,
            "eligible_from_completed_count": self.last_completed_count + 1,
            "future_tasks_only": True,
            "triggering_task_replay_allowed": False,
            "recovered_transaction": True,
        }
        if implementation_proof is not None:
            event["implementation_proof"] = implementation_proof
        append_jsonl(
            self.output_dir / POST_DEPLOYMENT_REPAIR_ACKNOWLEDGEMENT_FILENAME,
            event,
        )

    def _load_repair_state(self) -> None:
        if self.repair_state_path.exists():
            try:
                payload = json.loads(self.repair_state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}
            if isinstance(payload, dict):
                pending = payload.get("pending_repair_requests")
                if isinstance(pending, list):
                    self.pending_repair_requests = [
                        sanitized
                        for item in pending
                        if isinstance(item, dict)
                        and (
                            sanitized := self._sanitize_post_deployment_repair_request(
                                item
                            )
                        )
                        is not None
                    ]
                handled = payload.get("handled_repair_request_ids")
                if isinstance(handled, list):
                    self.handled_repair_request_ids = {
                        str(item) for item in handled if str(item)
                    }
                canaries = payload.get("canary_state_by_tool")
                if isinstance(canaries, dict):
                    self.canary_state_by_tool = {
                        str(name): dict(state)
                        for name, state in canaries.items()
                        if isinstance(name, str) and isinstance(state, dict)
                    }
                transactions = payload.get("repair_transactions_by_tool")
                if isinstance(transactions, dict):
                    self.repair_transactions_by_tool = {
                        str(name): dict(state)
                        for name, state in transactions.items()
                        if isinstance(name, str) and isinstance(state, dict)
                    }
                completed_count = payload.get("last_completed_count")
                if (
                    isinstance(completed_count, int)
                    and not isinstance(completed_count, bool)
                    and completed_count >= 0
                ):
                    self.last_completed_count = completed_count

        request_rows = self._jsonl_rows(
            self.output_dir / POST_DEPLOYMENT_REPAIR_REQUEST_FILENAME
        )
        request_by_id = {
            str(row.get("request_id")): row
            for row in request_rows
            if str(row.get("request_id") or "")
        }

        acknowledgement_rows = self._jsonl_rows(
            self.output_dir / POST_DEPLOYMENT_REPAIR_ACKNOWLEDGEMENT_FILENAME
        )
        final_status_by_request: dict[str, dict[str, Any]] = {}
        for row in acknowledgement_rows:
            request_id = str(row.get("request_id") or "")
            if request_id:
                final_status_by_request[request_id] = row
        terminal_statuses = {"promoted", "rejected", "rolled_back"}
        terminal_request_ids = {
            request_id
            for request_id, row in final_status_by_request.items()
            if str(row.get("status") or "") in terminal_statuses
        }
        for request_id in terminal_request_ids:
            acknowledgement = final_status_by_request[request_id]
            if str(acknowledgement.get("status") or "") == "promoted":
                continue
            tool_name = str(acknowledgement.get("tool_name") or "")
            version = acknowledgement.get("new_version")
            entry = self.store.get(tool_name) if tool_name else None
            if (
                entry is not None
                and isinstance(version, int)
                and not isinstance(version, bool)
                and entry.version == version
                and not entry.retired
            ):
                self.store.retire(tool_name)
        self.pending_repair_requests = [
            request
            for request in self.pending_repair_requests
            if str(request.get("request_id") or "") not in terminal_request_ids
        ]
        self.canary_state_by_tool = {
            tool_name: state
            for tool_name, state in self.canary_state_by_tool.items()
            if str(state.get("request_id") or "") not in terminal_request_ids
        }
        self.repair_transactions_by_tool = {
            tool_name: state
            for tool_name, state in self.repair_transactions_by_tool.items()
            if str(state.get("request_id") or "") not in terminal_request_ids
        }
        self.handled_repair_request_ids.update(terminal_request_ids)

        # A crash after the preactivation state write can leave either an exact
        # active vN+1 (recover it into its empty canary) or no trustworthy target
        # version (retire the affected entry and close the request).
        for tool_name, transaction in list(self.repair_transactions_by_tool.items()):
            request_id = str(transaction.get("request_id") or "")
            target_version = transaction.get("target_tool_version")
            source_version = transaction.get("source_tool_version")
            expected_code_hash = str(transaction.get("replacement_code_hash") or "")
            entry = self.store.get(tool_name)
            entry_binding, _binding_error = (
                self._validation_contract_store.resolve(entry)
                if entry is not None
                else (None, "registry_entry_missing")
            )
            matches_target = bool(
                isinstance(target_version, int)
                and not isinstance(target_version, bool)
                and entry is not None
                and entry.version == target_version
                and not entry.retired
                and entry_binding is not None
                and entry.birth_scenario.startswith("post_deployment_repair:")
                and (
                    not expected_code_hash
                    or entry.stored_code_hash == expected_code_hash
                )
            )
            if matches_target:
                raw_canary = transaction.get("canary_state")
                canary = dict(raw_canary) if isinstance(raw_canary, dict) else {}
                canary.setdefault("request_id", request_id)
                canary.setdefault("tool_version", target_version)
                canary.setdefault("source_tool_version", source_version)
                self.canary_state_by_tool[tool_name] = (
                    self._normalize_loaded_canary_state(canary)
                )
                self.handled_repair_request_ids.add(request_id)
                self.pending_repair_requests = [
                    request
                    for request in self.pending_repair_requests
                    if str(request.get("request_id") or "") != request_id
                ]
                self._event(
                    "post_deployment_tool_repair_transaction_recovered",
                    {
                        "request_id": request_id,
                        "tool_name": tool_name,
                        "tool_version": target_version,
                        "recovery_disposition": "canary",
                    },
                )
            else:
                if entry is not None and not entry.retired:
                    self.store.retire(tool_name)
                self.pending_repair_requests = [
                    request
                    for request in self.pending_repair_requests
                    if str(request.get("request_id") or "") != request_id
                ]
                self.handled_repair_request_ids.add(request_id)
                if request_id in request_by_id:
                    acknowledgement_version = (
                        source_version
                        if isinstance(source_version, int)
                        and not isinstance(source_version, bool)
                        and source_version > 0
                        else 1
                    )
                    self._append_recovery_acknowledgement(
                        request_id=request_id,
                        tool_name=tool_name,
                        version=acknowledgement_version,
                        status="rejected",
                        implementation_proof=(
                            _metadata_implementation_proof(
                                source_code_hash=str(
                                    transaction.get("source_code_hash") or ""
                                ),
                                replacement_code_hash=(
                                    entry.stored_code_hash
                                    if entry is not None
                                    and entry.version == target_version
                                    else None
                                ),
                                replacement_activated=bool(
                                    entry is not None
                                    and entry.version == target_version
                                ),
                                model_authored_code_change_discarded=bool(
                                    (
                                        transaction.get("metadata_implementation_proof")
                                        or {}
                                    ).get("model_authored_code_change_discarded", False)
                                ),
                            )
                            if transaction.get("repair_kind") == "metadata"
                            else None
                        ),
                    )
                self._event(
                    "post_deployment_tool_repair_transaction_recovered",
                    {
                        "request_id": request_id,
                        "tool_name": tool_name,
                        "source_tool_version": source_version,
                        "target_tool_version": target_version,
                        "recovery_disposition": "retired",
                    },
                )
            self.repair_transactions_by_tool.pop(tool_name, None)

        self.canary_state_by_tool = {
            tool_name: self._normalize_loaded_canary_state(state)
            for tool_name, state in self.canary_state_by_tool.items()
        }
        verified_canaries: dict[str, dict[str, Any]] = {}
        for tool_name, state in self.canary_state_by_tool.items():
            entry = self.store.get(tool_name)
            binding, binding_error = (
                self._validation_contract_store.resolve(entry)
                if entry is not None
                else (None, "registry_entry_missing")
            )
            raw_version = state.get("tool_version")
            if (
                entry is not None
                and not entry.retired
                and isinstance(raw_version, int)
                and not isinstance(raw_version, bool)
                and entry.version == raw_version
                and binding is not None
            ):
                verified_canaries[tool_name] = state
                continue
            if entry is not None and not entry.retired:
                self.store.retire(tool_name)
            self._event(
                "post_deployment_tool_canary_recovery_rejected",
                {
                    "tool_name": tool_name,
                    "tool_version": raw_version,
                    "binding_error": binding_error,
                    "entry_retired": bool(entry is not None and not entry.retired),
                    "repair_model_called": False,
                },
            )
        self.canary_state_by_tool = verified_canaries
        for request_id, row in final_status_by_request.items():
            status = str(row.get("status") or "")
            if status in terminal_statuses:
                continue
            if status != "canary_pending":
                continue
            tool_name = str(row.get("tool_name") or "")
            version = row.get("new_version")
            if (
                tool_name
                and isinstance(version, int)
                and not isinstance(version, bool)
                and version > 0
                and tool_name not in self.canary_state_by_tool
            ):
                request = request_by_id.get(request_id, {})
                entry = self.store.get(tool_name)
                entry_binding, _binding_error = (
                    self._validation_contract_store.resolve(entry)
                    if entry is not None
                    else (None, "registry_entry_missing")
                )
                if (
                    entry is not None
                    and entry.version == version
                    and not entry.retired
                    and entry_binding is not None
                    and entry.birth_scenario.startswith("post_deployment_repair:")
                ):
                    recovered_canary = self._prepared_canary_state(
                        request_id=request_id,
                        tool_version=version,
                        source_tool_version=max(version - 1, 1),
                        target_task_family=self._normalized_task_family(
                            request.get("target_task_family")
                        ),
                        eligible_from_completed_count=self._nonnegative_int(
                            request.get("eligible_from_completed_count"),
                            default=self.last_completed_count + 1,
                        ),
                    )
                    if request.get("repair_kind") == "metadata":
                        recovered_canary["metadata_implementation_proof"] = (
                            _metadata_implementation_proof(
                                source_code_hash=str(
                                    request.get("source_code_hash") or ""
                                ),
                                replacement_code_hash=entry.stored_code_hash,
                                replacement_activated=True,
                                model_authored_code_change_discarded=bool(
                                    row.get("implementation_proof", {}).get(
                                        "model_authored_code_change_discarded", False
                                    )
                                    if isinstance(row.get("implementation_proof"), dict)
                                    else False
                                ),
                            )
                        )
                    self.canary_state_by_tool[tool_name] = recovered_canary
                else:
                    if (
                        entry is not None
                        and entry.version == version
                        and not entry.retired
                    ):
                        self.store.retire(tool_name)
                    if request_id in request_by_id:
                        self._append_recovery_acknowledgement(
                            request_id=request_id,
                            tool_name=tool_name,
                            version=version,
                            status="rolled_back",
                            implementation_proof=(
                                _metadata_implementation_proof(
                                    source_code_hash=str(
                                        request.get("source_code_hash") or ""
                                    ),
                                    replacement_code_hash=None,
                                    replacement_activated=False,
                                    model_authored_code_change_discarded=False,
                                )
                                if request.get("repair_kind") == "metadata"
                                else None
                            ),
                        )
                self.handled_repair_request_ids.add(request_id)

        acknowledged_ids = set(final_status_by_request)
        pending_ids = {
            str(item.get("request_id") or "") for item in self.pending_repair_requests
        }
        for row in request_rows:
            request_id = str(row.get("request_id") or "")
            sanitized = self._sanitize_post_deployment_repair_request(row)
            if (
                request_id
                and sanitized is not None
                and request_id not in acknowledged_ids
                and request_id not in self.handled_repair_request_ids
                and request_id not in pending_ids
            ):
                self.pending_repair_requests.append(sanitized)
                pending_ids.add(request_id)
        self._write_repair_state()

    def _write_repair_state(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "pending_repair_requests": self.pending_repair_requests,
            "handled_repair_request_ids": sorted(self.handled_repair_request_ids),
            "canary_state_by_tool": self.canary_state_by_tool,
            "repair_transactions_by_tool": self.repair_transactions_by_tool,
            "last_completed_count": self.last_completed_count,
        }
        temporary_path = self.repair_state_path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_path, self.repair_state_path)

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

    @staticmethod
    def _normalized_task_family(value: Any) -> str:
        normalized = str(value or "").strip().lower()
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_.:-")
        if (
            not normalized
            or len(normalized) > 128
            or any(character not in allowed for character in normalized)
        ):
            return "unclassified"
        return normalized

    def _trusted_target_task_family(
        self,
        tool_name: str,
        value: Any,
        *,
        visible_task_family: str | None = None,
    ) -> str:
        """Keep repair and canary families in the routed-task namespace.

        Reflection receives the same public ``VisibleTaskContext`` family that
        routing uses. Capability observations use a different namespace (for
        example ``safe_abstain`` rather than ``contact``), so they are only a
        compatibility fallback for direct controller callers.
        """

        normalized = self._normalized_task_family(value)
        if normalized == "unclassified":
            return normalized
        expected_family = self._normalized_task_family(visible_task_family)
        if expected_family == "unclassified":
            observation = self.observations_by_tool_name.get(tool_name)
            expected_family = self._normalized_task_family(
                observation.task_family_key if observation is not None else None
            )
        if expected_family != "unclassified" and normalized != expected_family:
            return "unclassified"
        return normalized

    def queue_post_deployment_repair_requests(
        self,
        requests: tuple[dict[str, Any], ...] | list[dict[str, Any]],
        *,
        visible_task_family: str | None = None,
    ) -> tuple[str, ...]:
        """Accept only future-only, sanitized lifecycle repair handoffs."""

        queued: list[str] = []
        already_pending = {
            str(item.get("request_id") or "") for item in self.pending_repair_requests
        }
        for raw_request in requests:
            sanitized = self._sanitize_post_deployment_repair_request(
                raw_request,
                visible_task_family=visible_task_family,
            )
            if sanitized is None:
                continue
            request_id = str(sanitized["request_id"])
            tool_name = str(sanitized["tool_name"])
            repair_kind = str(sanitized["repair_kind"])
            if (
                request_id in self.handled_repair_request_ids
                or request_id in already_pending
            ):
                continue
            self.pending_repair_requests.append(sanitized)
            already_pending.add(request_id)
            queued.append(request_id)
            self._event(
                "post_deployment_tool_repair_queued",
                {
                    "request_id": request_id,
                    "tool_name": tool_name,
                    "repair_kind": repair_kind,
                    "source_tool_version": sanitized["source_tool_version"],
                    "target_task_family": sanitized["target_task_family"],
                    "eligible_from_completed_count": sanitized[
                        "eligible_from_completed_count"
                    ],
                    "future_tasks_only": True,
                },
            )
        if queued:
            self._write_repair_state()
        return tuple(queued)

    def _sanitize_post_deployment_repair_request(
        self,
        raw_request: dict[str, Any],
        *,
        visible_task_family: str | None = None,
    ) -> dict[str, Any] | None:
        """Build the only repair-request shape allowed to reach generation."""

        request_id = str(raw_request.get("request_id") or "").strip()
        tool_name = str(raw_request.get("tool_name") or "").strip()
        repair_kind = str(raw_request.get("repair_kind") or "").strip()
        source_code_hash = (
            str(raw_request.get("source_code_hash") or "").strip().lower()
        )
        if (
            not request_id
            or not tool_name
            or repair_kind not in {"implementation", "metadata"}
            or (
                repair_kind == "metadata"
                and _SHA256_HEX_PATTERN.fullmatch(source_code_hash) is None
            )
            or not bool(raw_request.get("future_tasks_only"))
            or bool(raw_request.get("triggering_task_replay_allowed"))
        ):
            return None

        raw_evidence = raw_request.get("public_evidence")
        public_evidence = (
            {
                str(key): value
                for key, value in raw_evidence.items()
                if str(key) in POST_DEPLOYMENT_REPAIR_PUBLIC_EVIDENCE_FIELDS
                and isinstance(value, int)
                and not isinstance(value, bool)
                and value >= 0
            }
            if isinstance(raw_evidence, dict)
            else {}
        )
        trusted_target_family = self._trusted_target_task_family(
            tool_name,
            raw_request.get("target_task_family"),
            visible_task_family=visible_task_family,
        )
        raw_trigger_count = raw_request.get("trigger_completed_count")
        raw_eligible_count = raw_request.get("eligible_from_completed_count")
        trigger_count_valid = bool(
            isinstance(raw_trigger_count, int)
            and not isinstance(raw_trigger_count, bool)
            and raw_trigger_count >= 0
        )
        eligible_count_valid = bool(
            isinstance(raw_eligible_count, int)
            and not isinstance(raw_eligible_count, bool)
            and raw_eligible_count > 0
            and trigger_count_valid
            and raw_eligible_count > raw_trigger_count
        )
        sanitized = {
            "request_id": request_id,
            "repair_kind": repair_kind,
            "tool_name": tool_name,
            "source_code_hash": (
                source_code_hash if repair_kind == "metadata" else None
            ),
            "source_tool_version": (
                raw_request.get("source_tool_version")
                if isinstance(raw_request.get("source_tool_version"), int)
                and not isinstance(raw_request.get("source_tool_version"), bool)
                else None
            ),
            "target_task_family": trusted_target_family,
            "trigger_reason_codes": [
                str(item)
                for item in raw_request.get("trigger_reason_codes", [])
                if str(item)
                in {
                    "deterministic_public_contract_failure",
                    "repeated_generated_tool_execution_failure",
                    "unresolved_generated_tool_execution_failure",
                    "repeated_visible_not_called",
                    "visible_repeatedly_without_adoption",
                }
            ],
            "trigger_completed_count": (
                raw_trigger_count if trigger_count_valid else None
            ),
            "eligible_from_completed_count": (
                raw_eligible_count if eligible_count_valid else None
            ),
            "repair_request_validation_error": (
                None
                if trigger_count_valid and eligible_count_valid
                else "invalid_future_task_completed_count"
            ),
            "future_tasks_only": True,
            "triggering_task_replay_allowed": False,
            "public_evidence": public_evidence,
        }
        _assert_repair_payload_safe(
            sanitized,
            label="sanitized post-deployment repair request",
        )
        return sanitized

    def contract_failures_for_tools(
        self, tool_names: list[str] | tuple[str, ...]
    ) -> tuple[str, ...]:
        """Recheck called deployed tools against their public frozen contracts."""

        failed: list[str] = []
        for tool_name in dict.fromkeys(str(item) for item in tool_names if item):
            entry = self.store.get(tool_name)
            if entry is None:
                continue
            binding, binding_error = self._resolve_validation_contract(entry)
            if binding is None:
                was_active = not entry.retired
                if was_active:
                    self.store.retire(tool_name)
                failed.append(tool_name)
                self._event(
                    "post_deployment_public_contract_binding_invalid",
                    {
                        "tool_name": tool_name,
                        "tool_version": entry.version,
                        "tool_code_hash": entry.stored_code_hash,
                        "binding_error": binding_error,
                        "error_labels": ["invalid_public_contract_binding"],
                        "entry_retired": was_active,
                        "repair_model_called": False,
                        "raw_hidden_case_values_logged": False,
                    },
                )
                continue
            observation = binding.observation
            validation = validate_generated_tool(
                entry.tool,
                # The content-addressed binding freezes the exact synthetic
                # source/held-out contract that admitted this version.
                examples=observation.validation_examples,
            )
            original_contract_errors = _original_tool_contract_errors(
                entry.tool, observation
            )
            if validation.accepted and not original_contract_errors:
                continue
            failed.append(tool_name)
            self._event(
                "post_deployment_public_contract_failure",
                {
                    "tool_name": tool_name,
                    "tool_version": entry.version,
                    "canonical_key": observation.canonical_key,
                    "error_labels": list(
                        _repair_prompt_errors(
                            (*original_contract_errors, *validation.errors)
                        )
                    ),
                    "raw_hidden_case_values_logged": False,
                },
            )
        return tuple(failed)

    def record_canary_result(
        self,
        *,
        called_tools: list[str] | tuple[str, ...],
        called_tool_versions: dict[str, int],
        attributable_tools: list[str] | tuple[str, ...],
        candidate_outcome: float | None,
        audited_outcome_delta: float | None,
        fresh_control_success_flip: bool,
        contract_failures: list[str] | tuple[str, ...],
        exception_type: Any,
        task_family_key: str,
        visible_tools: list[str] | tuple[str, ...] = (),
        failed_tools: list[str] | tuple[str, ...] = (),
        acknowledge: RepairAcknowledgementHook | None = None,
    ) -> tuple[dict[str, Any], ...]:
        """Promote only from attributable, current-version, prospective evidence."""

        decisions: list[dict[str, Any]] = []
        called_set = {str(item) for item in called_tools if item}
        visible_set = {str(item) for item in visible_tools if item}
        failed_set = {str(item) for item in failed_tools if item}
        all_called_set = called_set | failed_set
        attributable_set = {str(item) for item in attributable_tools if item}
        version_by_tool = {
            str(tool_name): version
            for tool_name, version in called_tool_versions.items()
            if isinstance(tool_name, str)
            and isinstance(version, int)
            and not isinstance(version, bool)
            and version > 0
        }
        contract_failure_set = set(contract_failures)
        for tool_name, state in list(self.canary_state_by_tool.items()):
            entry = self.store.get(tool_name)
            if entry is None or entry.retired or entry.version != state["tool_version"]:
                request_id = str(state.get("request_id") or "")
                version = state.get("tool_version")
                acknowledgement_version = (
                    version if isinstance(version, int) and version > 0 else 1
                )
                decision = {
                    "event": "post_deployment_tool_canary_retired",
                    "request_id": request_id,
                    "tool_name": tool_name,
                    "tool_version": acknowledgement_version,
                    "status": "rolled_back",
                    "reason": "canary_registry_version_missing_or_superseded",
                    "run_finalization": False,
                    "decision_uses_score": False,
                }
                self._event(decision["event"], decision)
                acknowledged = self._acknowledge_repair_without_escaping(
                    acknowledge,
                    tool_name=tool_name,
                    version=acknowledgement_version,
                    request_id=request_id,
                    status="rolled_back",
                    implementation_proof=(
                        state.get("metadata_implementation_proof")
                        if isinstance(state.get("metadata_implementation_proof"), dict)
                        else None
                    ),
                )
                if not acknowledged:
                    continue
                if request_id:
                    self.handled_repair_request_ids.add(request_id)
                self.canary_state_by_tool.pop(tool_name, None)
                decisions.append(decision)
                continue
            state.setdefault("evidence_schema_version", 2)
            state.setdefault("called_count", 0)
            state.setdefault("visible_count", 0)
            state.setdefault("eligible_family_task_count", 0)
            state.setdefault("outcomes", [])
            state.setdefault("outcome_deltas", [])
            state.setdefault("attributable_call_count", 0)
            state.setdefault("attributable_observation_count", 0)
            state.setdefault("exact_success_count", 0)
            state.setdefault("audited_regression_count", 0)
            state.setdefault("fresh_control_success_flip_count", 0)
            state.setdefault("version_mismatch_call_count", 0)
            state.setdefault("contract_failure_count", 0)
            state.setdefault("runtime_failure_count", 0)
            target_family = str(state.get("target_task_family") or "unclassified")
            reported_called = tool_name in all_called_set
            current_version_called = bool(
                reported_called
                and version_by_tool.get(tool_name) == entry.version
                and entry.version == state["tool_version"]
            )
            if reported_called and not current_version_called:
                state["version_mismatch_call_count"] += 1
            # ``unclassified`` is a real fail-closed bucket, not a wildcard.
            # Otherwise a malformed or mismatched repair family could collect
            # favorable evidence from arbitrary later tasks and be promoted.
            in_target_family = task_family_key == target_family
            attributable_call = bool(
                current_version_called
                and len(all_called_set) == 1
                and tool_name in attributable_set
            )
            if current_version_called and tool_name in contract_failure_set:
                state["contract_failure_count"] += 1
            # A scenario-level exception can happen in the actor, user simulator,
            # evaluator, or framework after a valid helper call. Only the tool's
            # own failed result is attributable runtime evidence.
            if current_version_called and tool_name in failed_set:
                state["runtime_failure_count"] += 1
            if not in_target_family:
                if reported_called:
                    self._event(
                        "post_deployment_tool_canary_out_of_family_call_ignored",
                        {
                            "request_id": state["request_id"],
                            "tool_name": tool_name,
                            "tool_version": entry.version,
                            "target_task_family": target_family,
                            "observed_task_family": task_family_key,
                            "soft_evidence_ignored": True,
                            "called_version": version_by_tool.get(tool_name),
                            "current_version_call": current_version_called,
                            "hard_failure_applied": bool(
                                state["contract_failure_count"]
                                or state["runtime_failure_count"]
                            ),
                        },
                    )
                if not (
                    state["contract_failure_count"] or state["runtime_failure_count"]
                ):
                    continue
            else:
                state["eligible_family_task_count"] = (
                    int(state.get("eligible_family_task_count") or 0) + 1
                )
                if tool_name in visible_set:
                    state["visible_count"] = int(state.get("visible_count") or 0) + 1
            if current_version_called and in_target_family:
                state["called_count"] += 1
            # A scenario-level exception is not attributable to the generated
            # tool.  In particular, the audited runner records a zero outcome
            # for framework/actor/user failures, so consuming that delta here
            # would silently turn the same generic exception back into a tool
            # regression.  Explicit failed_tools/contract_failures above remain
            # immediate hard evidence for this exact current version.
            attributable_outcome_observation = bool(
                attributable_call and in_target_family and not exception_type
            )
            if attributable_call and in_target_family:
                state["attributable_call_count"] += 1
                if (
                    attributable_outcome_observation
                    and candidate_outcome is not None
                    and audited_outcome_delta is not None
                ):
                    outcome = float(candidate_outcome)
                    outcome_delta = float(audited_outcome_delta)
                    state["outcomes"].append(outcome)
                    state["outcome_deltas"].append(outcome_delta)
                    state["attributable_observation_count"] += 1
                    if outcome == 1.0:
                        state["exact_success_count"] += 1
                    if outcome_delta < 0.0:
                        state["audited_regression_count"] += 1
                    if (
                        fresh_control_success_flip
                        and outcome == 1.0
                        and outcome_delta > 0.0
                    ):
                        state["fresh_control_success_flip_count"] += 1

            hard_failure = bool(
                state["contract_failure_count"]
                or state["runtime_failure_count"]
                or state["audited_regression_count"]
            )
            enough_attributable_observations = (
                state["attributable_observation_count"]
                >= POST_DEPLOYMENT_CANARY_REQUIRED_ATTRIBUTABLE_OBSERVATIONS
            )
            deadline_reached = (
                state["eligible_family_task_count"]
                >= POST_DEPLOYMENT_CANARY_MAX_FAMILY_TASKS
            )
            if (
                not hard_failure
                and not enough_attributable_observations
                and not deadline_reached
            ):
                self._event(
                    "post_deployment_tool_canary_observed",
                    {
                        "request_id": state["request_id"],
                        "tool_name": tool_name,
                        "tool_version": entry.version,
                        "called_count": state["called_count"],
                        "visible_count": state.get("visible_count", 0),
                        "eligible_family_task_count": state[
                            "eligible_family_task_count"
                        ],
                        "attributable_call_count": state["attributable_call_count"],
                        "attributable_observation_count": state[
                            "attributable_observation_count"
                        ],
                        "required_attributable_observations": (
                            POST_DEPLOYMENT_CANARY_REQUIRED_ATTRIBUTABLE_OBSERVATIONS
                        ),
                        "exact_success_count": state["exact_success_count"],
                        "audited_regression_count": state["audited_regression_count"],
                        "fresh_control_success_flip_count": state[
                            "fresh_control_success_flip_count"
                        ],
                        "version_mismatch_call_count": state[
                            "version_mismatch_call_count"
                        ],
                        "attribution_policy": (
                            "sole_generated_tool_called_current_version_same_family"
                        ),
                        "nonattributable_task_exception_observed": bool(exception_type),
                    },
                )
                continue

            outcomes = list(state["outcomes"])
            outcome_deltas = list(state["outcome_deltas"])
            success_count = int(state["exact_success_count"])
            success_rate = success_count / len(outcomes) if outcomes else 0.0
            promoted = (
                not hard_failure
                and enough_attributable_observations
                and success_count >= POST_DEPLOYMENT_CANARY_REQUIRED_EXACT_SUCCESSES
                and state["fresh_control_success_flip_count"]
                >= POST_DEPLOYMENT_CANARY_REQUIRED_FRESH_CONTROL_SUCCESS_FLIPS
            )
            status = "promoted" if promoted else "rolled_back"
            event_name = (
                "post_deployment_tool_canary_promoted"
                if promoted
                else "post_deployment_tool_canary_retired"
            )
            if promoted:
                decision_reason = "attributable_audited_canary_gate_passed"
            elif state["contract_failure_count"]:
                decision_reason = "public_contract_failure"
            elif state["runtime_failure_count"]:
                decision_reason = "generated_tool_runtime_failure"
            elif state["audited_regression_count"]:
                decision_reason = "attributable_audited_outcome_regression"
            elif deadline_reached:
                decision_reason = "canary_deadline_without_sufficient_evidence"
            else:
                decision_reason = "attributable_canary_gate_not_met"
            if not promoted:
                self.store.retire(tool_name)
            decision = {
                "event": event_name,
                "request_id": state["request_id"],
                "tool_name": tool_name,
                "tool_version": entry.version,
                "status": status,
                "reason": decision_reason,
                "called_count": state["called_count"],
                "visible_count": state.get("visible_count", 0),
                "eligible_family_task_count": state["eligible_family_task_count"],
                "attributable_call_count": state["attributable_call_count"],
                "attributable_observation_count": state[
                    "attributable_observation_count"
                ],
                "outcome_observation_count": len(outcomes),
                "outcome_success_count": success_count,
                "outcome_success_rate": success_rate,
                "audited_outcome_delta_observation_count": len(outcome_deltas),
                "audited_outcome_delta_mean": (
                    sum(outcome_deltas) / len(outcome_deltas)
                    if outcome_deltas
                    else None
                ),
                "audited_regression_count": state["audited_regression_count"],
                "fresh_control_success_flip_count": state[
                    "fresh_control_success_flip_count"
                ],
                "version_mismatch_call_count": state["version_mismatch_call_count"],
                "contract_failure_count": state["contract_failure_count"],
                "runtime_failure_count": state["runtime_failure_count"],
                "canary_deadline_reached": deadline_reached,
                "attribution_policy": (
                    "sole_generated_tool_called_current_version_same_family"
                ),
                "nonattributable_task_exception_observed": bool(exception_type),
                "decision_uses_score": False,
            }
            self._event(event_name, decision)
            acknowledged = self._acknowledge_repair_without_escaping(
                acknowledge,
                tool_name=tool_name,
                version=entry.version,
                request_id=str(state["request_id"]),
                status=status,
                implementation_proof=(
                    state.get("metadata_implementation_proof")
                    if isinstance(state.get("metadata_implementation_proof"), dict)
                    else None
                ),
            )
            if not acknowledged:
                continue
            self.canary_state_by_tool.pop(tool_name, None)
            decisions.append(decision)
        self._write_repair_state()
        return tuple(decisions)

    def _generation_request(
        self,
        observation: CapabilityObservation,
        *,
        suggested_name: str | None,
        lifecycle_request: dict[str, Any] | None = None,
    ) -> ToolGenerationRequest:
        generation_examples = observation.validation_examples
        if (
            suggested_name == "resolve_search_window_or_bounds"
            and observation.canonical_key
            in {
                "derived_value:recency_timestamp_bounds",
                "derived_value:resolve_search_window_or_bounds",
            }
        ):
            generation_examples = _resolve_window_validation_examples()
        model_visible_examples = _model_visible_generation_examples(generation_examples)
        cluster_context = self._cluster_context(observation)
        scenario_label = observation.task_context_label or observation.scenario_name
        inadequacy_evidence = observation.to_inadequacy_evidence().to_json()
        if lifecycle_request is not None:
            _assert_repair_payload_safe(
                lifecycle_request,
                label="queued post-deployment repair request",
            )
            repair_kind = str(lifecycle_request.get("repair_kind") or "implementation")
            target_family = str(
                lifecycle_request.get("target_task_family") or "unclassified"
            )
            raw_public_evidence = lifecycle_request.get("public_evidence")
            # Outcome values and success flips are lifecycle reward.  They may
            # determine whether a version is repaired/retired, but must never
            # become generator prompt content.  The repair model receives only
            # public operational evidence describing adoption and explicit
            # tool-level failures.
            prompt_safe_public_evidence = (
                {
                    key: value
                    for key, value in raw_public_evidence.items()
                    if key in POST_DEPLOYMENT_REPAIR_PUBLIC_EVIDENCE_FIELDS
                }
                if isinstance(raw_public_evidence, dict)
                else {}
            )
            scenario_label = (
                f"post_deployment_repair(kind={repair_kind};family={target_family})"
            )
            inadequacy_evidence = {
                **inadequacy_evidence,
                "post_deployment_repair": {
                    "repair_kind": repair_kind,
                    "reason_codes": list(
                        lifecycle_request.get("trigger_reason_codes") or []
                    ),
                    "public_aggregate_evidence": prompt_safe_public_evidence,
                    "future_tasks_only": True,
                },
            }
            cluster_context = {
                key: value
                for key, value in cluster_context.items()
                if key not in {"scenarios", "source_task_ids_available"}
            }
            cluster_context = {
                **cluster_context,
                "repair_kind": repair_kind,
                "target_task_family": target_family,
            }
        request = ToolGenerationRequest(
            scenario_name=scenario_label,
            observation=observation.observation,
            allowed_families=observation.allowed_families,
            validation_examples=tuple(
                {
                    "inputs": item.inputs,
                    "expected": item.expected,
                    "held_out": False,
                    "negative_applicability": item.negative_applicability,
                }
                for item in model_visible_examples
            ),
            public_input_contract=public_input_contract_from_example_inputs(
                tuple(item.inputs for item in generation_examples)
            ),
            public_output_contract=public_output_contract_from_example_outputs(
                tuple(item.expected for item in generation_examples)
            ),
            suggested_tool_name=suggested_name,
            inadequacy_evidence=inadequacy_evidence,
            failure_memory_context=(
                None
                if lifecycle_request is not None
                else generation_failure_memory_context(
                    self.failure_memory_path,
                    canonical_key=observation.canonical_key,
                    suggested_tool_name=suggested_name,
                )
            ),
            shortfall_cluster_context=cluster_context,
        )
        if lifecycle_request is not None:
            _assert_repair_generation_request_safe(request)
        return request

    def _remove_pending_repair_request(self, request_id: str) -> None:
        self.pending_repair_requests = [
            request
            for request in self.pending_repair_requests
            if str(request.get("request_id") or "") != request_id
        ]

    def _acknowledge_repair_without_escaping(
        self,
        acknowledge: RepairAcknowledgementHook | None,
        *,
        tool_name: str,
        version: int,
        request_id: str,
        status: str,
        implementation_proof: dict[str, Any] | None = None,
    ) -> bool:
        if acknowledge is None or not request_id or not tool_name:
            return True
        try:
            if implementation_proof is None:
                acknowledge(tool_name, max(version, 1), request_id, status)
            else:
                acknowledge(
                    tool_name,
                    max(version, 1),
                    request_id,
                    status,
                    implementation_proof,
                )
        except Exception as exc:
            self._event(
                "post_deployment_tool_repair_acknowledgement_failed",
                {
                    "request_id": request_id,
                    "tool_name": tool_name,
                    "tool_version": version,
                    "status": status,
                    "error": f"{type(exc).__name__}:{exc}",
                },
            )
            return False
        return True

    def _reject_pending_repair(
        self,
        lifecycle_request: dict[str, Any],
        *,
        reason: str,
        acknowledge: RepairAcknowledgementHook | None,
        event_name: str = "post_deployment_tool_repair_retired",
        error: BaseException | None = None,
        retire_current: bool = True,
        implementation_proof: dict[str, Any] | None = None,
    ) -> None:
        request_id = str(lifecycle_request.get("request_id") or "")
        tool_name = str(lifecycle_request.get("tool_name") or "")
        source_version = self._nonnegative_int(
            lifecycle_request.get("source_tool_version"), default=1
        )
        entry = self.store.get(tool_name) if tool_name else None
        retired = False
        if retire_current and entry is not None and not entry.retired:
            self.store.retire(tool_name)
            retired = True
        payload: dict[str, Any] = {
            "request_id": request_id,
            "tool_name": tool_name,
            "source_tool_version": source_version,
            "current_tool_version": entry.version if entry is not None else None,
            "reason": reason,
            "entry_retired": retired,
            "status": "rejected",
            "future_tasks_only": True,
            "triggering_task_replayed": False,
        }
        if error is not None:
            payload["error"] = f"{type(error).__name__}:{error}"
        self._event(event_name, payload)
        acknowledged = self._acknowledge_repair_without_escaping(
            acknowledge,
            tool_name=tool_name,
            version=source_version,
            request_id=request_id,
            status="rejected",
            implementation_proof=(
                implementation_proof
                or _metadata_implementation_proof(
                    source_code_hash=str(
                        lifecycle_request.get("source_code_hash") or ""
                    ),
                    replacement_code_hash=None,
                    replacement_activated=False,
                    model_authored_code_change_discarded=bool(
                        lifecycle_request.get(
                            "model_authored_code_change_discarded", False
                        )
                    ),
                )
                if lifecycle_request.get("repair_kind") == "metadata"
                else None
            ),
        )
        if acknowledged:
            self._remove_pending_repair_request(request_id)
            self.repair_transactions_by_tool.pop(tool_name, None)
            if request_id:
                self.handled_repair_request_ids.add(request_id)
        self._write_repair_state()

    def process_pending_repairs(
        self,
        *,
        completed_count: int,
        acknowledge: RepairAcknowledgementHook | None = None,
    ) -> tuple[str, ...]:
        """Repair or retire requests only before their eligible future task."""

        if (
            not isinstance(completed_count, int)
            or isinstance(completed_count, bool)
            or completed_count < 0
        ):
            self._event(
                "post_deployment_tool_repair_deferred",
                {"reason": "invalid_durable_completed_count"},
            )
            return ()
        self.last_completed_count = completed_count
        self._write_repair_state()

        accepted_tools: list[str] = []
        for raw_lifecycle_request in list(self.pending_repair_requests):
            lifecycle_request = dict(raw_lifecycle_request)
            request_id = str(lifecycle_request.get("request_id") or "")
            tool_name = str(lifecycle_request.get("tool_name") or "")
            repair_kind = str(lifecycle_request.get("repair_kind") or "")
            trigger_count = lifecycle_request.get("trigger_completed_count")
            eligible_count = lifecycle_request.get("eligible_from_completed_count")
            valid_ordinals = bool(
                isinstance(trigger_count, int)
                and not isinstance(trigger_count, bool)
                and trigger_count >= 0
                and isinstance(eligible_count, int)
                and not isinstance(eligible_count, bool)
                and eligible_count > trigger_count
            )
            if (
                not request_id
                or not tool_name
                or lifecycle_request.get("repair_request_validation_error")
                or not valid_ordinals
            ):
                self._reject_pending_repair(
                    lifecycle_request,
                    reason="malformed_future_task_repair_request",
                    acknowledge=acknowledge,
                )
                continue
            prospective_completed_count = completed_count + 1
            if prospective_completed_count < eligible_count:
                self._event(
                    "post_deployment_tool_repair_deferred",
                    {
                        "request_id": request_id,
                        "tool_name": tool_name,
                        "reason": "future_task_eligibility_not_reached",
                        "completed_count": completed_count,
                        "prospective_completed_count": prospective_completed_count,
                        "trigger_completed_count": trigger_count,
                        "eligible_from_completed_count": eligible_count,
                        "triggering_task_replayed": False,
                    },
                )
                continue

            entry = self.store.get(tool_name)
            if entry is None:
                self._reject_pending_repair(
                    lifecycle_request,
                    reason="registry_entry_missing",
                    acknowledge=acknowledge,
                    retire_current=False,
                )
                continue
            source_version = lifecycle_request.get("source_tool_version")
            if (
                not isinstance(source_version, int)
                or isinstance(source_version, bool)
                or source_version < 1
            ):
                self._reject_pending_repair(
                    lifecycle_request,
                    reason="invalid_source_tool_version",
                    acknowledge=acknowledge,
                )
                continue
            if entry.version != source_version:
                self._reject_pending_repair(
                    lifecycle_request,
                    reason="source_tool_version_superseded",
                    acknowledge=acknowledge,
                    event_name="post_deployment_tool_repair_stale",
                    retire_current=False,
                )
                continue
            source_code_hash = (
                str(lifecycle_request.get("source_code_hash") or "").strip().lower()
            )
            if repair_kind == "metadata" and (
                not entry.code_hash_verified
                or entry.stored_code_hash != source_code_hash
                or code_hash(entry.tool.code) != source_code_hash
            ):
                self._reject_pending_repair(
                    lifecycle_request,
                    reason="metadata_source_implementation_hash_mismatch",
                    acknowledge=acknowledge,
                )
                continue
            binding, binding_error = self._resolve_validation_contract(entry)
            if binding is None:
                self._event(
                    "post_deployment_public_contract_binding_invalid",
                    {
                        "request_id": request_id,
                        "tool_name": tool_name,
                        "tool_version": entry.version,
                        "tool_code_hash": entry.stored_code_hash,
                        "binding_error": binding_error,
                        "error_labels": ["invalid_public_contract_binding"],
                        "entry_retired": not entry.retired,
                        "repair_model_called": False,
                        "raw_hidden_case_values_logged": False,
                    },
                )
                self._reject_pending_repair(
                    lifecycle_request,
                    reason=(
                        f"public_contract_binding_invalid:{binding_error or 'unknown'}"
                    ),
                    acknowledge=acknowledge,
                )
                continue
            observation = binding.observation
            lifecycle_request["target_task_family"] = self._normalized_task_family(
                lifecycle_request.get("target_task_family")
            )

            # The known-bad source is unavailable while bounded repair runs.
            self.store.retire(tool_name)
            self._event(
                "post_deployment_tool_repair_started",
                {
                    "request_id": request_id,
                    "tool_name": tool_name,
                    "source_tool_version": entry.version,
                    "repair_kind": repair_kind,
                    "source_code_hash": (
                        source_code_hash if repair_kind == "metadata" else None
                    ),
                    "completed_count": completed_count,
                    "eligible_from_completed_count": eligible_count,
                    "future_tasks_only": True,
                    "triggering_task_replayed": False,
                },
            )
            try:
                request = self._generation_request(
                    observation,
                    suggested_name=tool_name,
                    lifecycle_request=lifecycle_request,
                )
                validation_examples = observation.validation_examples
                prior_validation = validate_generated_tool(
                    entry.tool,
                    examples=validation_examples,
                )
                base_task_families = tuple(
                    self._cluster_context(observation)["base_task_families"]
                )
            except Exception as exc:
                self._reject_pending_repair(
                    lifecycle_request,
                    reason="repair_setup_failed",
                    acknowledge=acknowledge,
                    error=exc,
                )
                continue

            immutable_repair_errors = [
                f"post_deployment_{reason}"
                for reason in lifecycle_request.get("trigger_reason_codes", [])
            ]
            if not immutable_repair_errors:
                immutable_repair_errors.append(
                    "post_deployment_public_contract_or_adoption_shortfall"
                )
            immutable_repair_errors = list(dict.fromkeys(immutable_repair_errors))

            best_tool: GeneratedTool | None = None
            best_validation: ValidationResult | None = None
            model_authored_code_change_discarded = False
            best_partial_tool = entry.tool
            best_partial_validation = prior_validation
            best_partial_score = _validation_failure_score(prior_validation)
            seed_tool = entry.tool
            seed_errors = tuple(
                dict.fromkeys(
                    (
                        *immutable_repair_errors,
                        *_repair_prompt_errors(prior_validation.errors),
                    )
                )
            )
            for attempt in range(1, CANDIDATE_REPAIR_ATTEMPTS + 1):
                best_candidate_code_hash_before_attempt = code_hash(
                    best_partial_tool.code
                )
                best_error_labels_before_attempt = _repair_prompt_errors(
                    best_partial_validation.errors
                )
                try:
                    candidates_method = getattr(
                        self.generator, "repair_candidates", None
                    )
                    repair_method = getattr(self.generator, "repair", None)
                    attempt_errors = (*seed_errors, f"repair_strategy:{attempt}")
                    if callable(candidates_method):
                        candidates = tuple(
                            candidates_method(request, seed_tool, attempt_errors)
                        )
                    elif callable(repair_method):
                        candidates = (
                            repair_method(request, seed_tool, attempt_errors),
                        )
                    else:
                        candidates = (self.generator.generate(request),)
                except Exception as exc:
                    self._event(
                        "post_deployment_tool_repair_attempt_failed",
                        {
                            "request_id": request_id,
                            "tool_name": tool_name,
                            "attempt": attempt,
                            "stage": "candidate_generation",
                            "error": f"{type(exc).__name__}:{exc}",
                        },
                    )
                    continue
                candidate_results: list[
                    tuple[
                        int,
                        GeneratedTool,
                        GeneratedTool,
                        ValidationResult,
                        int,
                        bool,
                    ]
                ] = []
                for candidate_index, raw_candidate in enumerate(candidates):
                    generator_candidate = raw_candidate
                    candidate: GeneratedTool | None = None
                    try:
                        if repair_kind == "metadata" and (
                            raw_candidate.code != entry.tool.code
                            or code_hash(raw_candidate.code) != source_code_hash
                        ):
                            model_authored_code_change_discarded = True
                            lifecycle_request[
                                "model_authored_code_change_discarded"
                            ] = True
                            self._event(
                                "post_deployment_metadata_code_change_discarded",
                                {
                                    "request_id": request_id,
                                    "tool_name": tool_name,
                                    "attempt": attempt,
                                    "candidate_index": candidate_index,
                                    "source_code_hash": source_code_hash,
                                    "model_candidate_code_hash": code_hash(
                                        raw_candidate.code
                                    ),
                                    "executable_candidate_code_hash": source_code_hash,
                                    "model_authored_code_executed": False,
                                },
                            )
                            raw_candidate = replace(
                                raw_candidate,
                                code=entry.tool.code,
                            )
                        candidate = _normalize_live_birth_routing_metadata(
                            raw_candidate,
                            observation,
                            base_task_families,
                        )
                        if repair_kind == "metadata" and (
                            candidate.code != entry.tool.code
                            or code_hash(candidate.code) != source_code_hash
                        ):
                            validation = ValidationResult(
                                False,
                                ("metadata_repair_changed_executable_implementation",),
                            )
                        elif candidate.spec.tool_name != tool_name:
                            validation = ValidationResult(
                                False,
                                ("post_deployment_repair_changed_tool_name",),
                            )
                        else:
                            _gate, _live_check, validation = self._gate_and_validate(
                                candidate,
                                observation,
                                expected_tool_name=tool_name,
                            )
                    except Exception as exc:
                        candidate_artifact = self._persist_repair_candidate_artifact(
                            request_id=request_id,
                            tool_name=tool_name,
                            source_tool_version=entry.version,
                            repair_kind=repair_kind,
                            completed_count=completed_count,
                            attempt=attempt,
                            candidate_index=candidate_index,
                            validation_contract_hash=binding.contract_hash,
                            source_tool_code_sha256=binding.tool_code_hash,
                            source_tool_spec_sha256=binding.tool_spec_hash,
                            generator_candidate=generator_candidate,
                            evaluated_candidate=candidate,
                            validation=None,
                            validation_score=None,
                            selected_for_attempt=False,
                            disposition="normalization_or_validation_exception",
                            failure_stage=("candidate_normalization_and_validation"),
                            failure_type=type(exc).__name__,
                        )
                        self._event(
                            "post_deployment_tool_repair_attempt_failed",
                            {
                                "request_id": request_id,
                                "tool_name": tool_name,
                                "attempt": attempt,
                                "candidate_index": candidate_index,
                                "stage": "candidate_normalization_and_validation",
                                "error_type": type(exc).__name__,
                                "candidate_artifact_path": candidate_artifact[
                                    "artifact_path"
                                ],
                                "candidate_artifact_schema_version": (
                                    candidate_artifact["artifact_schema_version"]
                                ),
                                "candidate_artifact_record_sha256": (
                                    candidate_artifact["record_sha256"]
                                ),
                            },
                        )
                        continue
                    candidate_frontier = _repair_prompt_errors(validation.errors)
                    candidate_duplicates_best = bool(
                        not validation.accepted
                        and code_hash(candidate.code)
                        == best_candidate_code_hash_before_attempt
                        and candidate_frontier == best_error_labels_before_attempt
                    )
                    candidate_results.append(
                        (
                            candidate_index,
                            generator_candidate,
                            candidate,
                            validation,
                            _validation_failure_score(validation),
                            candidate_duplicates_best,
                        )
                    )
                if not candidate_results:
                    continue
                selected_result_index = min(
                    range(len(candidate_results)),
                    key=lambda index: (
                        not candidate_results[index][3].accepted,
                        candidate_results[index][4],
                        candidate_results[index][5],
                        index,
                    ),
                )
                (
                    selected_candidate_index,
                    _selected_generator_candidate,
                    candidate,
                    validation,
                    validation_score,
                    duplicate_of_best,
                ) = candidate_results[selected_result_index]
                improved_best = validation.accepted or (
                    validation_score < best_partial_score
                )
                retained_equal_score = (
                    not validation.accepted
                    and validation_score == best_partial_score
                    and not duplicate_of_best
                )
                if improved_best or retained_equal_score:
                    best_partial_tool = candidate
                    best_partial_validation = validation
                    best_partial_score = validation_score
                candidate_validation_rows: list[dict[str, Any]] = []
                for (
                    result_candidate_index,
                    generator_candidate,
                    candidate_tool,
                    candidate_validation,
                    candidate_score,
                    candidate_duplicates_best,
                ) in candidate_results:
                    selected_for_attempt = (
                        result_candidate_index == selected_candidate_index
                    )
                    if candidate_validation.accepted:
                        disposition = (
                            "validator_accepted_selected"
                            if selected_for_attempt
                            else "validator_accepted_not_selected"
                        )
                    elif candidate_duplicates_best:
                        disposition = "validator_rejected_duplicate_of_best"
                    else:
                        disposition = (
                            "validator_rejected_selected_for_next_seed"
                            if selected_for_attempt
                            else "validator_rejected"
                        )
                    candidate_artifact = self._persist_repair_candidate_artifact(
                        request_id=request_id,
                        tool_name=tool_name,
                        source_tool_version=entry.version,
                        repair_kind=repair_kind,
                        completed_count=completed_count,
                        attempt=attempt,
                        candidate_index=result_candidate_index,
                        validation_contract_hash=binding.contract_hash,
                        source_tool_code_sha256=binding.tool_code_hash,
                        source_tool_spec_sha256=binding.tool_spec_hash,
                        generator_candidate=generator_candidate,
                        evaluated_candidate=candidate_tool,
                        validation=candidate_validation,
                        validation_score=candidate_score,
                        selected_for_attempt=selected_for_attempt,
                        disposition=disposition,
                    )
                    sanitized_errors = _repair_prompt_errors(
                        candidate_validation.errors
                    )
                    candidate_validation_rows.append(
                        {
                            "candidate_index": result_candidate_index,
                            "candidate_code_hash": code_hash(candidate_tool.code),
                            "accepted": candidate_validation.accepted,
                            "validation_score": candidate_score,
                            "error_frontier_count": len(sanitized_errors),
                            "errors": list(sanitized_errors),
                            "candidate_artifact_path": candidate_artifact[
                                "artifact_path"
                            ],
                            "candidate_artifact_schema_version": (
                                candidate_artifact["artifact_schema_version"]
                            ),
                            "candidate_artifact_record_sha256": (
                                candidate_artifact["record_sha256"]
                            ),
                        }
                    )
                self._event(
                    "post_deployment_tool_repair_attempted",
                    {
                        "request_id": request_id,
                        "tool_name": tool_name,
                        "attempt": attempt,
                        "candidate_count": len(candidate_results),
                        "selected_candidate_index": selected_candidate_index,
                        "selected_candidate_code_hash": code_hash(candidate.code),
                        "accepted": validation.accepted,
                        "validation_score": validation_score,
                        "best_validation_score": best_partial_score,
                        "improved_best": improved_best,
                        "retained_equal_score": retained_equal_score,
                        "best_candidate_code_hash_before_attempt": (
                            best_candidate_code_hash_before_attempt
                        ),
                        "best_error_labels_before_attempt": list(
                            best_error_labels_before_attempt
                        ),
                        "duplicate_of_best": duplicate_of_best,
                        "stagnation_feedback_label": (
                            REPAIR_STAGNATION_DUPLICATE_CANDIDATE_LABEL
                            if duplicate_of_best
                            else None
                        ),
                        "next_seed_source": (
                            "selected_candidate"
                            if improved_best or retained_equal_score
                            else "best_previous_candidate"
                        ),
                        "candidate_validations": candidate_validation_rows,
                        "implementation_code_preserved": (
                            code_hash(candidate.code) == source_code_hash
                            if repair_kind == "metadata"
                            else None
                        ),
                        "model_authored_code_change_discarded": (
                            model_authored_code_change_discarded
                            if repair_kind == "metadata"
                            else None
                        ),
                        "error_labels": list(_repair_prompt_errors(validation.errors)),
                    },
                )
                # Never let a worse repair displace the best validated partial repair.
                # Feedback always describes the exact candidate supplied to the next
                # model call. Lifecycle trigger reasons remain immutable.
                seed_tool = best_partial_tool
                seed_errors = tuple(
                    dict.fromkeys(
                        (
                            *immutable_repair_errors,
                            *_repair_prompt_errors(best_partial_validation.errors),
                            *(
                                (REPAIR_STAGNATION_DUPLICATE_CANDIDATE_LABEL,)
                                if duplicate_of_best
                                else ()
                            ),
                        )
                    )
                )
                if validation.accepted:
                    best_tool = candidate
                    best_validation = validation
                    break

            if best_tool is None or best_validation is None:
                self._reject_pending_repair(
                    lifecycle_request,
                    reason="bounded_repair_failed_validation",
                    acknowledge=acknowledge,
                )
                continue
            if repair_kind == "metadata" and (
                best_tool.code != entry.tool.code
                or code_hash(best_tool.code) != source_code_hash
            ):
                self._reject_pending_repair(
                    lifecycle_request,
                    reason="metadata_repair_changed_executable_implementation",
                    acknowledge=acknowledge,
                )
                continue

            birth_scenario = (
                "post_deployment_repair:"
                f"{lifecycle_request.get('target_task_family', 'unclassified')}"
            )
            replacement = RegistryEntry.accepted(
                best_tool,
                best_validation,
                birth_scenario=birth_scenario,
            )
            if repair_kind == "metadata" and (
                replacement.stored_code_hash != source_code_hash
                or not replacement.code_hash_verified
            ):
                self._reject_pending_repair(
                    lifecycle_request,
                    reason="metadata_replacement_implementation_hash_mismatch",
                    acknowledge=acknowledge,
                )
                continue
            target_version = entry.version + 1
            canary_state = self._prepared_canary_state(
                request_id=request_id,
                tool_version=target_version,
                source_tool_version=entry.version,
                target_task_family=str(lifecycle_request["target_task_family"]),
                eligible_from_completed_count=eligible_count,
            )
            metadata_proof = (
                _metadata_implementation_proof(
                    source_code_hash=source_code_hash,
                    replacement_code_hash=replacement.stored_code_hash,
                    replacement_activated=True,
                    model_authored_code_change_discarded=(
                        model_authored_code_change_discarded
                    ),
                )
                if repair_kind == "metadata"
                else None
            )
            if metadata_proof is not None:
                canary_state["metadata_implementation_proof"] = metadata_proof
            self.repair_transactions_by_tool[tool_name] = {
                "phase": "canary_prepared",
                "request_id": request_id,
                "tool_name": tool_name,
                "source_tool_version": entry.version,
                "target_tool_version": target_version,
                "target_task_family": lifecycle_request["target_task_family"],
                "eligible_from_completed_count": eligible_count,
                "prepared_after_completed_count": completed_count,
                "repair_kind": repair_kind,
                "source_code_hash": (
                    source_code_hash if repair_kind == "metadata" else None
                ),
                "replacement_code_hash": replacement.stored_code_hash,
                "metadata_implementation_proof": metadata_proof,
                "canary_state": canary_state,
            }
            # This write is the transaction boundary: an active vN+1 must never
            # exist without enough durable lineage to recover its empty canary.
            self._write_repair_state()
            try:
                self.store.put(replacement)
                saved_entry = self.store.get(tool_name)
                if (
                    saved_entry is None
                    or saved_entry.version != target_version
                    or saved_entry.retired
                    or saved_entry.birth_scenario != birth_scenario
                    or saved_entry.stored_code_hash != replacement.stored_code_hash
                    or (
                        repair_kind == "metadata"
                        and (
                            saved_entry.tool.code != entry.tool.code
                            or saved_entry.stored_code_hash != source_code_hash
                            or not saved_entry.code_hash_verified
                        )
                    )
                ):
                    raise RuntimeError("activated repair version did not match lineage")
                contract_binding = self._persist_validation_contract(
                    saved_entry,
                    observation,
                    validation_examples=observation.validation_examples,
                )
                snapshot_dir = self.output_dir / "generated_tool_snapshots"
                snapshot_dir.mkdir(parents=True, exist_ok=True)
                snapshot_path = snapshot_dir / f"{tool_name}_v{saved_entry.version}.py"
                snapshot_path.write_text(best_tool.code + "\n", encoding="utf-8")
            except Exception as exc:
                current_after_failure = self.store.get(tool_name)
                replacement_activated = bool(
                    current_after_failure is not None
                    and current_after_failure.version == target_version
                )
                activation_failure_proof = (
                    _metadata_implementation_proof(
                        source_code_hash=source_code_hash,
                        replacement_code_hash=(
                            current_after_failure.stored_code_hash
                            if replacement_activated
                            else None
                        ),
                        replacement_activated=replacement_activated,
                        model_authored_code_change_discarded=(
                            model_authored_code_change_discarded
                        ),
                    )
                    if repair_kind == "metadata"
                    else None
                )
                self._reject_pending_repair(
                    lifecycle_request,
                    reason="repair_activation_failed",
                    acknowledge=acknowledge,
                    error=exc,
                    implementation_proof=activation_failure_proof,
                )
                continue

            self.canary_state_by_tool[tool_name] = canary_state
            self.repair_transactions_by_tool.pop(tool_name, None)
            self._remove_pending_repair_request(request_id)
            self.handled_repair_request_ids.add(request_id)
            accepted_tools.append(tool_name)
            self._write_repair_state()
            self._event(
                "post_deployment_tool_repair_accepted",
                {
                    "request_id": request_id,
                    "tool_name": tool_name,
                    "source_tool_version": entry.version,
                    "new_tool_version": saved_entry.version,
                    "repair_kind": lifecycle_request.get("repair_kind"),
                    "source_code_hash": (
                        source_code_hash if repair_kind == "metadata" else None
                    ),
                    "replacement_code_hash": (
                        saved_entry.stored_code_hash
                        if repair_kind == "metadata"
                        else None
                    ),
                    "implementation_preserved": (
                        metadata_proof["implementation_preserved"]
                        if metadata_proof is not None
                        else None
                    ),
                    "model_authored_code_change_discarded": (
                        model_authored_code_change_discarded
                        if repair_kind == "metadata"
                        else None
                    ),
                    "snapshot_path": str(snapshot_path),
                    "validation_contract_hash": contract_binding.contract_hash,
                    "canary_eligible_from_next_task": True,
                    "eligible_from_completed_count": eligible_count,
                    "activated_after_completed_count": completed_count,
                    "triggering_task_replayed": False,
                },
            )
            self._acknowledge_repair_without_escaping(
                acknowledge,
                tool_name=tool_name,
                version=saved_entry.version,
                request_id=request_id,
                status="canary_pending",
                implementation_proof=metadata_proof,
            )
        self._write_repair_state()
        return tuple(accepted_tools)

    def finalize_run(
        self,
        *,
        acknowledge: RepairAcknowledgementHook | None = None,
    ) -> tuple[dict[str, Any], ...]:
        """Conservatively close lifecycle work when no future task remains.

        A request emitted by the final task cannot be applied without violating
        future-only semantics. Likewise, an incomplete canary has insufficient
        prospective evidence. Both dispositions retire only the affected current
        version and record a terminal acknowledgement.
        """

        decisions: list[dict[str, Any]] = []
        for request in list(self.pending_repair_requests):
            request_id = str(request.get("request_id") or "")
            tool_name = str(request.get("tool_name") or "")
            source_version = request.get("source_tool_version")
            entry = self.store.get(tool_name) if tool_name else None
            version = (
                source_version
                if isinstance(source_version, int) and source_version > 0
                else entry.version
                if entry is not None
                else 1
            )
            retired = False
            if entry is not None and (
                not isinstance(source_version, int) or entry.version == source_version
            ):
                self.store.retire(tool_name)
                retired = True
            decision = {
                "event": "post_deployment_tool_repair_retired",
                "request_id": request_id,
                "tool_name": tool_name,
                "source_tool_version": source_version,
                "current_tool_version": entry.version if entry is not None else None,
                "status": "rejected",
                "reason": "run_ended_before_future_repair_task",
                "entry_retired": retired,
                "run_finalization": True,
                "future_tasks_only": True,
                "triggering_task_replayed": False,
            }
            self._event(decision["event"], decision)
            append_jsonl(
                self.output_dir / "post_deployment_lifecycle_finalization.jsonl",
                decision,
            )
            acknowledged = self._acknowledge_repair_without_escaping(
                acknowledge,
                tool_name=tool_name,
                version=version,
                request_id=request_id,
                status="rejected",
                implementation_proof=(
                    _metadata_implementation_proof(
                        source_code_hash=str(request.get("source_code_hash") or ""),
                        replacement_code_hash=None,
                        replacement_activated=False,
                        model_authored_code_change_discarded=False,
                    )
                    if request.get("repair_kind") == "metadata"
                    else None
                ),
            )
            if acknowledged and request_id:
                self.handled_repair_request_ids.add(request_id)
            decisions.append(decision)
            if acknowledged:
                self._remove_pending_repair_request(request_id)

        for tool_name, state in list(self.canary_state_by_tool.items()):
            request_id = str(state.get("request_id") or "")
            raw_version = state.get("tool_version")
            version = (
                raw_version if isinstance(raw_version, int) and raw_version > 0 else 1
            )
            entry = self.store.get(tool_name)
            retired = False
            if entry is not None and entry.version == version:
                self.store.retire(tool_name)
                retired = True
            outcomes = [
                float(value)
                for value in state.get("outcomes", [])
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            ]
            outcome_deltas = [
                float(value)
                for value in state.get("outcome_deltas", [])
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            ]
            success_count = int(
                state.get("exact_success_count")
                if isinstance(state.get("exact_success_count"), int)
                and not isinstance(state.get("exact_success_count"), bool)
                else sum(value == 1.0 for value in outcomes)
            )
            decision = {
                "event": "post_deployment_tool_canary_retired",
                "request_id": request_id,
                "tool_name": tool_name,
                "tool_version": version,
                "status": "rolled_back",
                "reason": "run_ended_before_canary_completed",
                "entry_retired": retired,
                "called_count": int(state.get("called_count") or 0),
                "visible_count": int(state.get("visible_count") or 0),
                "eligible_family_task_count": int(
                    state.get("eligible_family_task_count") or 0
                ),
                "attributable_call_count": int(
                    state.get("attributable_call_count") or 0
                ),
                "attributable_observation_count": int(
                    state.get("attributable_observation_count") or 0
                ),
                "outcome_observation_count": len(outcomes),
                "outcome_success_count": success_count,
                "outcome_success_rate": (
                    success_count / len(outcomes) if outcomes else 0.0
                ),
                "audited_outcome_delta_observation_count": len(outcome_deltas),
                "audited_outcome_delta_mean": (
                    sum(outcome_deltas) / len(outcome_deltas)
                    if outcome_deltas
                    else None
                ),
                "audited_regression_count": int(
                    state.get("audited_regression_count") or 0
                ),
                "fresh_control_success_flip_count": int(
                    state.get("fresh_control_success_flip_count") or 0
                ),
                "version_mismatch_call_count": int(
                    state.get("version_mismatch_call_count") or 0
                ),
                "contract_failure_count": int(state.get("contract_failure_count") or 0),
                "runtime_failure_count": int(state.get("runtime_failure_count") or 0),
                "canary_deadline_reached": False,
                "run_finalization": True,
                "attribution_policy": (
                    "sole_generated_tool_called_current_version_same_family"
                ),
                "decision_uses_score": False,
                "future_tasks_only": True,
                "triggering_task_replayed": False,
            }
            self._event(decision["event"], decision)
            append_jsonl(
                self.output_dir / "post_deployment_lifecycle_finalization.jsonl",
                decision,
            )
            acknowledged = self._acknowledge_repair_without_escaping(
                acknowledge,
                tool_name=tool_name,
                version=version,
                request_id=request_id,
                status="rolled_back",
                implementation_proof=(
                    state.get("metadata_implementation_proof")
                    if isinstance(state.get("metadata_implementation_proof"), dict)
                    else None
                ),
            )
            if acknowledged and request_id:
                self.handled_repair_request_ids.add(request_id)
            if acknowledged:
                self.canary_state_by_tool.pop(tool_name, None)
            decisions.append(decision)

        self._write_repair_state()
        return tuple(decisions)

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
            # Do not consult evaluation-side benchmark prefix maps. Current fit
            # is established by public capability metadata and validation only.
            "current_helper_fit": (),
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
        suggested_name = suggested_tool_name(observation.canonical_key)
        if suggested_name is not None:
            self.observations_by_tool_name[suggested_name] = observation
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

        request = self._generation_request(
            observation,
            suggested_name=suggested_name,
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
                expected_tool_name=suggested_name,
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
            if not validation.accepted and callable(repair_method):
                repair_errors = _repair_prompt_errors(validation.errors)
                for attempt in range(1, CANDIDATE_REPAIR_ATTEMPTS + 1):
                    if validation.accepted:
                        break
                    repair_attempted = True
                    repair_attempt_count = attempt
                    # Candidate-specific feedback must describe the exact best partial
                    # implementation supplied to this round. Errors from superseded
                    # candidates are stale and can reintroduce branches already fixed.
                    current_errors = _repair_prompt_errors(
                        repair_seed_validation.errors
                    )
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
                            self._gate_and_validate(
                                normalized_candidate,
                                observation,
                                expected_tool_name=suggested_name,
                            )
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
                    advanced_case_frontier = _advances_repair_case_frontier(
                        tuple(repair_seed_validation.errors),
                        tuple(repaired_validation.errors),
                    )
                    improved = repaired_validation.accepted or (
                        repaired_score < best_validation_score
                    )
                    retained_equal_score = (
                        not repaired_validation.accepted
                        and repaired_score == best_validation_score
                    )
                    repair_record = {
                        "attempt": attempt,
                        "input_errors": list(current_errors),
                        "repaired_errors": list(
                            _repair_prompt_errors(repaired_validation.errors)
                        ),
                        "accepted": repaired_validation.accepted,
                        "repaired_tool_name": repaired_tool.spec.tool_name,
                        "elapsed_seconds": round(repair_elapsed, 3),
                        "code_chars": len(repaired_tool.code),
                        "code": repaired_tool.code,
                        "validation_score": repaired_score,
                        "improved_best": improved,
                        "retained_equal_score": retained_equal_score,
                        "advanced_case_frontier": advanced_case_frontier,
                        "repair_candidate_count": len(candidate_results),
                        "selected_candidate_index": selected_candidate_index,
                        "repair_candidate_validations": [
                            {
                                "candidate_index": index,
                                "accepted": candidate_validation.accepted,
                                "validation_score": candidate_score,
                                "errors": list(
                                    _repair_prompt_errors(candidate_validation.errors)
                                ),
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
                    if improved or retained_equal_score:
                        best_tool = repaired_tool
                        best_memory_gate = repaired_gate
                        best_live_check = repaired_live_check
                        best_validation = repaired_validation
                        best_validation_score = repaired_score
                    # Equal-score candidates may advance implementation structure, but
                    # a strictly worse candidate never becomes the next repair seed.
                    repair_seed_tool = best_tool
                    repair_seed_validation = best_validation
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
                "errors": list(_repair_prompt_errors(validation.errors)),
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
                "repair_final_errors": list(_repair_prompt_errors(validation.errors))
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
                "errors": list(_repair_prompt_errors(validation.errors)),
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
            entry = RegistryEntry.accepted(
                tool,
                validation,
                birth_scenario=birth_context,
            )
            try:
                self.store.put(entry)
                saved_entry = self.store.get(tool.spec.tool_name)
                if (
                    saved_entry is None
                    or saved_entry.retired
                    or saved_entry.stored_code_hash != entry.stored_code_hash
                    or not saved_entry.code_hash_verified
                ):
                    raise RuntimeError(
                        "accepted registry version did not match generated tool"
                    )
                contract_binding = self._persist_validation_contract(
                    saved_entry,
                    observation,
                    validation_examples=_validation_examples_for_tool(
                        tool, observation
                    ),
                )
            except Exception as exc:
                current_entry = self.store.get(tool.spec.tool_name)
                if (
                    current_entry is not None
                    and not current_entry.retired
                    and current_entry.stored_code_hash == entry.stored_code_hash
                ):
                    self.store.retire(tool.spec.tool_name)
                self.generated_keys.discard(observation.canonical_key)
                self.rejected_counts[observation.canonical_key] += 1
                self._event(
                    "tool_birth_validation_contract_binding_failed",
                    {
                        "canonical_key": observation.canonical_key,
                        "tool_name": tool.spec.tool_name,
                        "tool_version": (
                            current_entry.version if current_entry is not None else None
                        ),
                        "tool_code_hash": entry.stored_code_hash,
                        "error": f"{type(exc).__name__}:{exc}",
                        "entry_retired": bool(
                            current_entry is not None and not current_entry.retired
                        ),
                        "raw_hidden_case_values_logged": False,
                    },
                )
                return None
            self.generated_keys.add(observation.canonical_key)
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
                    "validation_contract_hash": contract_binding.contract_hash,
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
                    "validation_contract_hash": contract_binding.contract_hash,
                    "code": tool.code,
                },
            )
            self._event(
                "registry_saved",
                {
                    "registry_dir": str(self.store.root),
                    "tool_name": tool.spec.tool_name,
                    "tool_version": saved_entry.version,
                    "validation_contract_hash": contract_binding.contract_hash,
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
                    "errors": list(_repair_prompt_errors(validation.errors)),
                    "code": tool.code,
                    "rejection_count": self.rejected_counts[observation.canonical_key],
                },
            )
        return None

    def _gate_and_validate(
        self,
        tool: GeneratedTool,
        observation: CapabilityObservation,
        *,
        expected_tool_name: str | None = None,
    ) -> tuple[Any, Any, ValidationResult]:
        examples = _validation_examples_for_tool(tool, observation)
        memory_gate = evaluate_candidate_gate(
            tool.spec,
            failure_memory_path=self.failure_memory_path,
        )
        if expected_tool_name and tool.spec.tool_name != expected_tool_name:
            return (
                memory_gate,
                None,
                ValidationResult(
                    False,
                    (
                        "generated_tool_name_mismatch:"
                        f"{tool.spec.tool_name}!={expected_tool_name}",
                    ),
                ),
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
