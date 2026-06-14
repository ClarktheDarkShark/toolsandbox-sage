"""Online conversion from repeated observations to accepted helper tools."""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Protocol

from sage_ts.adequacy.candidate_gate import evaluate_candidate_gate
from sage_ts.adequacy.failure_memory import generation_failure_memory_context
from sage_ts.adequacy.inadequacy_classifier import (
    CapabilityObservation,
    classify_planned_scenario_observations,
    classify_visible_task_observations,
)
from sage_ts.evaluation.task_strata import base_task_family, expected_helper_fit
from sage_ts.experiments.v2_flags import (
    CANDIDATE_REPAIR,
    DEPENDENCY_LOGIC,
    LIVE_VALIDATION,
    MEDIUM_GRAIN_SKILLS,
    feature_enabled,
)
from sage_ts.generation.tool_generator import ToolGenerationRequest
from sage_ts.generation.tool_spec import GeneratedTool
from sage_ts.orchestration.checkpoints import append_jsonl
from sage_ts.registry.manifest import RegistryEntry, has_current_validation_proof
from sage_ts.registry.store import RegistryStore
from sage_ts.validation.live_candidate_check import run_lightweight_live_candidate_check
from sage_ts.validation.sandbox_validator import (
    ToolExample,
    ValidationResult,
    validate_generated_tool,
)


class GeneratedToolFactory(Protocol):
    def generate(self, request: ToolGenerationRequest) -> GeneratedTool: ...


class GeneratedToolRepairFactory(GeneratedToolFactory, Protocol):
    def repair(
        self,
        request: ToolGenerationRequest,
        rejected_tool: GeneratedTool,
        errors: tuple[str, ...],
    ) -> GeneratedTool: ...


CampaignEventHook = Callable[[str, dict[str, Any]], None]


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
    if suffix in {"device_state_action_sequence", "plan_device_state_action_sequence"}:
        return "plan_device_state_action_sequence_v3"
    if suffix in {"service_next_action", "next_service_tool_call"}:
        return "next_service_tool_call"
    if (
        feature_enabled(DEPENDENCY_LOGIC)
        and suffix == "dependency_precondition_tool_call"
    ):
        return "next_dependency_precondition_call"
    if (
        feature_enabled(MEDIUM_GRAIN_SKILLS)
        and suffix == "constraint_to_action_planner"
    ):
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
DEFAULT_CANDIDATE_REPAIR_ATTEMPTS = 2
PROACTIVE_BIRTH_ENV = "SAGE_SELF_EVOLVING_PROACTIVE_BIRTH"
PROACTIVE_BIRTH_SCOPE_ENV = "SAGE_SELF_EVOLVING_PROACTIVE_SCOPE"
SCENARIO_METADATA_POLICY_ENV = "SAGE_SCENARIO_METADATA_POLICY"
DISABLE_SCENARIO_NAME_BIRTH_ENV = "SAGE_DISABLE_SCENARIO_NAME_BIRTH"
DISABLE_SCENARIO_NAME_ROUTING_ENV = "SAGE_DISABLE_SCENARIO_NAME_ROUTING"
PROACTIVE_SCOPE_MANIFEST = "manifest"
PROACTIVE_SCOPE_JUST_IN_TIME = "just_in_time"
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
        "composite:prepare_reminder_creation_args",
        "composite:select_message_counterparty_for_contact_update",
        "derived_value:days_between_timestamps",
        "derived_value:extract_service_answer_field",
        "derived_value:extract_stock_symbol",
        "derived_value:plan_device_status_lookup",
        "derived_value:resolve_search_window_or_bounds",
        "search_filter:select_action_target_by_recency",
        "search_filter:select_message_content_by_recency",
        "search_filter:select_record_by_timestamp_extreme",
        "state_precondition:plan_device_state_action_sequence",
        "validation:prepare_safe_action_or_abstain",
    }
)
CHAIN_ROUTING_FAMILIES_BY_KEY = {
    "composite:plan_contact_lookup_query": (
        "update_contact_relationship_with_relationship_twice",
        "update_contact_relationship_with_relationship",
        "remove_contact_by_phone",
    ),
    "composite:plan_contact_update_from_id": (
        "update_contact_with_id_and_phone_number",
        "contact_id_update_argument_planning",
    ),
    "composite:prepare_direct_contact_action_args": (
        "remove_contact_with_id",
        "send_message_with_phone_number_and_content",
        "add_contact_with_name_and_phone_number",
        "update_contact_with_id_and_phone_number",
    ),
    "composite:plan_send_message_contact_lookup": (
        "send_message_with_contact_content",
        "send_message_with_contact_content_cellular_off",
    ),
    "state_precondition:plan_device_state_action_sequence": (
        "cellular_off",
        "wifi_off",
        "turn_on_wifi_low_battery_mode",
        "turn_on_cellular_low_battery_mode",
        "turn_on_location_low_battery_mode",
        "send_message_with_contact_content_cellular_off",
        "find_days_till_holiday_wifi_off",
        "add_reminder_content_and_week_delta_and_time_and_location_low_battery_mode",
    ),
    "composite:select_message_counterparty_for_contact_update": (
        "modify_contact_with_message_recency",
        "modify_contact_with_message_recency_alt",
    ),
    "derived_value:resolve_search_window_or_bounds": (
        "search_reminder_with_creation_recency_yesterday",
        "search_reminder_with_recency_yesterday",
        "search_reminder_with_recency_upcoming",
        "search_message_with_recency_latest",
        "search_message_with_recency_oldest",
        "modify_reminder_with_recency_latest",
        "remove_reminder_with_recency_latest",
    ),
}

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
        "modify_contact",
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
    "derived_value:plan_device_status_lookup": (
        "device_status_read",
        "wifi_status",
        "cellular_status",
        "location_status",
        "battery_status",
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


def visible_context_metadata_enabled() -> bool:
    raw = os.environ.get(SCENARIO_METADATA_POLICY_ENV, "").strip().lower()
    disable_birth = os.environ.get(DISABLE_SCENARIO_NAME_BIRTH_ENV, "").strip().lower()
    disable_routing = (
        os.environ.get(DISABLE_SCENARIO_NAME_ROUTING_ENV, "").strip().lower()
    )
    if disable_birth in {"1", "true", "yes", "on", "enabled"}:
        return True
    if disable_routing in {"1", "true", "yes", "on", "enabled"}:
        return True
    return raw in {
        "visible_context",
        "visible-context",
        "visible",
        "no_scenario_names",
        "no-scenario-names",
    }


def _observation_family_key(observation: CapabilityObservation) -> str:
    value = str(observation.task_family_key or "").strip()
    if value:
        return value
    return base_task_family(observation.scenario_name)


SCENARIO_LIKE_LABEL_PREFIXES = (
    "add_reminder_",
    "remove_reminder_",
    "modify_reminder_",
    "search_reminder_",
    "add_contact_",
    "remove_contact_",
    "modify_contact_",
    "update_contact_",
    "search_message_",
    "search_sender_",
    "send_message_",
    "search_phone_",
    "search_name_",
    "search_relationship_",
    "find_days_",
    "find_distance_",
    "find_holiday_",
    "find_thanksgiving_",
    "find_phone_",
    "find_temperature",
    "convert_currency",
    "get_wifi",
    "get_cellular",
    "wifi_off",
    "cellular_off",
    "turn_on_",
)


def _scenario_like_label(item: str) -> bool:
    value = str(item or "").strip().lower()
    return value.startswith(SCENARIO_LIKE_LABEL_PREFIXES)


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

    Generation models sometimes emit full robustness-variant scenario names as
    ``applicable_task_families``. Those names are valid evidence lineage, but
    they are too narrow for natural reuse and can hide an otherwise useful
    helper on later tasks from the same base family. Normalize them into base
    family labels derived only from visible scenario names, and add the same
    labels as trigger tokens so routing does not depend on exact variants.
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
    if not visible_context_observation:
        family_candidates.extend(_expanded_family_labels(observation.scenario_name))
        for item in CHAIN_ROUTING_FAMILIES_BY_KEY.get(observation.canonical_key, ()):
            family_candidates.extend(_expanded_family_labels(item))
    else:
        for item in VISIBLE_ROUTING_FAMILIES_BY_KEY.get(observation.canonical_key, ()):
            family_candidates.extend(_expanded_family_labels(item))
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
                "phrase": "todo item I made yesterday",
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
    )


def _prepare_location_validation_examples() -> tuple[ToolExample, ...]:
    """Validation examples for generated location-search argument preparation."""

    return (
        ToolExample(
            {
                "user_request": "Add a reminder to buy milk at Whole Foods on Stevens Creek tomorrow.",
                "location_phrase": "",
                "latitude": 0.0,
                "longitude": 0.0,
            },
            {
                "search_location_kwargs": {
                    "location": "Whole Foods on Stevens Creek",
                },
                "should_call_downstream_tool": True,
                "downstream_tool_name": "search_location_around_lat_lon",
                "downstream_tool_kwargs": {
                    "location": "Whole Foods on Stevens Creek",
                },
                "location_query": "Whole Foods on Stevens Creek",
                "abstain_reason": "",
            },
        ),
        ToolExample(
            {
                "user_request": "Add a reminder to buy milk at Whole Foods.",
                "location_phrase": "Whole Foods",
                "latitude": 0.0,
                "longitude": 0.0,
            },
            {
                "search_location_kwargs": {},
                "should_call_downstream_tool": False,
                "downstream_tool_name": "",
                "downstream_tool_kwargs": {},
                "location_query": "Whole Foods",
                "abstain_reason": "missing_reminder_time_before_location_lookup",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "user_request": "Whole Foods on Stevens Creek",
                "location_phrase": "Whole Foods",
                "latitude": 0.0,
                "longitude": 0.0,
            },
            {
                "search_location_kwargs": {
                    "location": "Whole Foods on Stevens Creek",
                },
                "should_call_downstream_tool": True,
                "downstream_tool_name": "search_location_around_lat_lon",
                "downstream_tool_kwargs": {
                    "location": "Whole Foods on Stevens Creek",
                },
                "location_query": "Whole Foods on Stevens Creek",
                "abstain_reason": "",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "user_request": "Find a Whole Foods near me.",
                "location_phrase": "Whole Foods",
                "latitude": 0.0,
                "longitude": 0.0,
            },
            {
                "search_location_kwargs": {},
                "should_call_downstream_tool": True,
                "downstream_tool_name": "get_current_location",
                "downstream_tool_kwargs": {},
                "location_query": "Whole Foods",
                "abstain_reason": "need_current_coordinates_for_broad_location_query",
            },
        ),
        ToolExample(
            {
                "user_request": "Find a Whole Foods near me.",
                "location_phrase": "Whole Foods",
                "latitude": 37.323,
                "longitude": -122.032,
            },
            {
                "search_location_kwargs": {
                    "location": "Whole Foods",
                    "latitude": 37.323,
                    "longitude": -122.032,
                },
                "should_call_downstream_tool": True,
                "downstream_tool_name": "search_location_around_lat_lon",
                "downstream_tool_kwargs": {
                    "location": "Whole Foods",
                    "latitude": 37.323,
                    "longitude": -122.032,
                },
                "location_query": "Whole Foods",
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
        observation.canonical_key == "derived_value:recency_timestamp_bounds"
        and tool.spec.tool_name == "resolve_search_window_or_bounds"
    ):
        return _resolve_window_validation_examples()
    if (
        observation.canonical_key == "composite:prepare_location_search_args"
        and tool.spec.tool_name == "prepare_location_search_args"
    ):
        return _prepare_location_validation_examples()
    return observation.validation_examples


def _proactive_birth_enabled() -> bool:
    return os.environ.get(PROACTIVE_BIRTH_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _proactive_birth_scope() -> str:
    scope = os.environ.get(PROACTIVE_BIRTH_SCOPE_ENV, PROACTIVE_SCOPE_MANIFEST)
    normalized = scope.strip().lower().replace("-", "_")
    if normalized in {"jit", "justintime", "just_in_time", "per_task"}:
        return PROACTIVE_SCOPE_JUST_IN_TIME
    return PROACTIVE_SCOPE_MANIFEST


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
    max_rejections_per_key: int = 2
    failure_memory_path: Path | None = Path("artifacts/summaries/failure_memory.json")
    proactive_manifest_primed: bool = False

    def _event(self, event: str, payload: dict[str, Any]) -> None:
        if self.event_hook is not None:
            self.event_hook(event, payload)

    def prime_from_scenario_names(self, scenario_names: tuple[str, ...]) -> None:
        """Birth early tools from unlabeled manifest task-family text when enabled."""
        if visible_context_metadata_enabled():
            self.proactive_manifest_primed = True
            self._event(
                "proactive_manifest_reflection_skipped",
                {
                    "scenario_count": len(scenario_names),
                    "metadata_policy": "visible_context",
                    "reason": "scenario_names_not_allowed_for_tool_birth",
                },
            )
            return
        if (
            not _proactive_birth_enabled()
            or _proactive_birth_scope() != PROACTIVE_SCOPE_MANIFEST
            or self.proactive_manifest_primed
        ):
            return
        self.proactive_manifest_primed = True
        observation_count = 0
        keys_before = set(self.generated_keys)
        for scenario_name in scenario_names:
            for observation in classify_planned_scenario_observations(scenario_name):
                if not observation.generation_allowed:
                    continue
                observation_count += 1
                self._event(
                    "proactive_inadequacy_detected",
                    {
                        "scenario_name": scenario_name,
                        "canonical_key": observation.canonical_key,
                        "evidence_source": observation.evidence_source,
                        "reason": observation.reason,
                    },
                )
                self.observe(observation)
        born_keys = sorted(set(self.generated_keys) - keys_before)
        self._event(
            "proactive_manifest_reflection_completed",
            {
                "scenario_count": len(scenario_names),
                "observation_count": observation_count,
                "born_or_suppressed_keys": born_keys,
                "registry_dir": str(self.store.root),
            },
        )

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

        if (
            not _proactive_birth_enabled()
            or _proactive_birth_scope() != PROACTIVE_SCOPE_JUST_IN_TIME
        ):
            return []
        accepted: list[str] = []
        observation_count = 0
        keys_before = set(self.generated_keys)
        if visible_context_metadata_enabled():
            if scenario is None:
                return []
            observations = classify_visible_task_observations(scenario_name, scenario)
        else:
            observations = classify_planned_scenario_observations(scenario_name)
        for observation in observations:
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
            if feature_enabled(MEDIUM_GRAIN_SKILLS)
            and observation.canonical_key == "composite:constraint_to_action_planner"
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
            "current_helper_fit": (
                ()
                if observation.task_context_label
                else expected_helper_fit(observation.scenario_name)
            ),
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

        suggested_name = suggested_tool_name(observation.canonical_key)
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

        request = ToolGenerationRequest(
            scenario_name=observation.task_context_label or observation.scenario_name,
            observation=observation.observation,
            allowed_families=observation.allowed_families,
            validation_examples=tuple(
                {
                    "inputs": item.inputs,
                    "expected": item.expected,
                    "held_out": item.held_out,
                    "negative_applicability": item.negative_applicability,
                }
                for item in observation.validation_examples
            ),
            suggested_tool_name=suggested_name,
            inadequacy_evidence=observation.to_inadequacy_evidence().to_json(),
            failure_memory_context=generation_failure_memory_context(
                self.failure_memory_path,
                canonical_key=observation.canonical_key,
                suggested_tool_name=suggested_name,
            ),
            shortfall_cluster_context=self._cluster_context(observation),
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
            tool = self.generator.generate(request)
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
                },
            )
            memory_gate, live_check, validation = self._gate_and_validate(
                tool,
                observation,
            )
            repair_attempted = False
            repair_attempt_count = 0
            repair_errors: tuple[str, ...] = ()
            repair_history: list[dict[str, Any]] = []
            repair_method = getattr(self.generator, "repair", None)
            if (
                not validation.accepted
                and feature_enabled(CANDIDATE_REPAIR)
                and callable(repair_method)
            ):
                repair_errors = tuple(validation.errors)
                for attempt in range(1, DEFAULT_CANDIDATE_REPAIR_ATTEMPTS + 1):
                    if validation.accepted:
                        break
                    repair_attempted = True
                    repair_attempt_count = attempt
                    current_errors = tuple(validation.errors)
                    repaired_tool = repair_method(request, tool, current_errors)
                    repaired_tool = _normalize_live_birth_routing_metadata(
                        repaired_tool,
                        observation,
                        tuple(self._cluster_context(observation)["base_task_families"]),
                    )
                    repaired_gate, repaired_live_check, repaired_validation = (
                        self._gate_and_validate(repaired_tool, observation)
                    )
                    repair_record = {
                        "attempt": attempt,
                        "input_errors": list(current_errors),
                        "repaired_errors": list(repaired_validation.errors),
                        "accepted": repaired_validation.accepted,
                        "repaired_tool_name": repaired_tool.spec.tool_name,
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
                    tool = repaired_tool
                    memory_gate = repaired_gate
                    live_check = repaired_live_check
                    validation = repaired_validation
        except Exception as exc:
            append_jsonl(
                self.output_dir / "tool_birth_events.jsonl",
                {
                    "canonical_key": observation.canonical_key,
                    "accepted": False,
                    "errors": [f"generation_error:{type(exc).__name__}:{exc}"],
                },
            )
            self.rejected_counts[observation.canonical_key] += 1
            self._event(
                "tool_birth_rejected",
                {
                    "canonical_key": observation.canonical_key,
                    **_observation_public_context(observation),
                    "error": f"{type(exc).__name__}:{exc}",
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
                "errors": list(validation.errors),
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
                "repair_final_errors": list(validation.errors)
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
                "errors": list(validation.errors),
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
            },
        )
        if validation.accepted:
            self.generated_keys.add(observation.canonical_key)
            entry = RegistryEntry.accepted(
                tool,
                validation,
                birth_scenario=birth_context,
            )
            self.store.put(entry)
            saved_entry = self.store.get(tool.spec.tool_name) or entry
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
                },
            )
            self._event(
                "registry_saved",
                {
                    "registry_dir": str(self.store.root),
                    "tool_name": tool.spec.tool_name,
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
                    "errors": list(validation.errors),
                    "rejection_count": self.rejected_counts[observation.canonical_key],
                },
            )
        return None

    def _gate_and_validate(
        self,
        tool: GeneratedTool,
        observation: CapabilityObservation,
    ) -> tuple[Any, Any, ValidationResult]:
        examples = _validation_examples_for_tool(tool, observation)
        memory_gate = evaluate_candidate_gate(
            tool.spec,
            failure_memory_path=self.failure_memory_path,
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
        if feature_enabled(LIVE_VALIDATION):
            live_check = run_lightweight_live_candidate_check(
                tool,
                examples,
            )
            if not live_check.accepted:
                return (
                    memory_gate,
                    live_check,
                    ValidationResult(False, live_check.errors),
                )
        else:
            live_check = None
        return (
            memory_gate,
            live_check,
            validate_generated_tool(
                tool,
                examples=examples,
            ),
        )
