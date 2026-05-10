# mypy: ignore-errors
"""Build action/precondition gap-closure experimental registries and manifests.

Experimental only. This loop targets two large unsupported broad buckets from
the Broad500 top-tool gap assessment:

- settings/device-state preconditions
- safe insufficient-information / abstention

The generated registries are not protected final evidence.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from sage_ts.config.splits import ScenarioRecord, scenario_records
from sage_ts.evaluation.task_strata import base_task_family
from sage_ts.generation.tool_spec import (
    GeneratedTool,
    StructuredInadequacyEvidence,
    ToolFamily,
    ToolInput,
    ToolSpec,
)
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.validation.sandbox_validator import ToolExample, validate_generated_tool

REGISTRY_ROOT = Path(
    "artifacts/registry_experiments/gap_closure_lab/action_precondition_loop"
)
MANIFEST_ROOT = Path(
    "artifacts/experiment_manifests/gap_closure_lab/action_precondition_loop"
)
TOP_TOOL_REGISTRY = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "top_tools_full_timestamp_no_field_extractor_pack/registry_manifest.json"
)
FORMAL500 = Path("docs/sage_protocol/manifests/v2_1_formal_500.json")
FORMAL1000 = Path("docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json")

STATE_REGISTRY = (
    REGISTRY_ROOT / "state_precondition_next_action_pack" / "registry_manifest.json"
)
INSUFFICIENT_REGISTRY = (
    REGISTRY_ROOT / "safe_insufficient_abstention_pack" / "registry_manifest.json"
)
COMBINED_REGISTRY = (
    REGISTRY_ROOT / "top_tools_plus_action_precondition_pack" / "registry_manifest.json"
)
STATE_SEQUENCE_REGISTRY = (
    REGISTRY_ROOT / "state_action_sequence_pack" / "registry_manifest.json"
)
INSUFFICIENT_DOMAIN_REGISTRY = (
    REGISTRY_ROOT / "safe_insufficient_domain_response_pack" / "registry_manifest.json"
)
COMBINED_V2_REGISTRY = (
    REGISTRY_ROOT
    / "top_tools_plus_action_precondition_v2_pack"
    / "registry_manifest.json"
)

SETTINGS_MANIFEST = MANIFEST_ROOT / "settings_device_state_splits.json"
INSUFFICIENT_MANIFEST = MANIFEST_ROOT / "safe_insufficient_information_splits.json"
COMBINED_MANIFEST = MANIFEST_ROOT / "settings_insufficient_combined_splits.json"
BROAD_MANIFEST = MANIFEST_ROOT / "action_precondition_broad_splits.json"
CONTACT_MANIFEST = MANIFEST_ROOT / "contact_crud_splits.json"
REMINDER_MANIFEST = MANIFEST_ROOT / "reminder_crud_scheduling_splits.json"
SUMMARY_OUT = MANIFEST_ROOT / "action_precondition_loop_build_summary.json"


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    digest = _sha256(text.encode("utf-8"))
    path.with_suffix(path.suffix + ".sha256").write_text(
        f"{digest}  {path.name}\n", encoding="utf-8"
    )
    return digest


def _load_tools(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return cast(dict[str, Any], payload["tools"])


def _entry(
    tool: GeneratedTool, examples: tuple[ToolExample, ...], birth: str
) -> dict[str, Any]:
    validation = validate_generated_tool(tool, examples)
    if not validation.accepted:
        raise RuntimeError(
            f"{tool.spec.tool_name} validation failed: {validation.errors}"
        )
    return RegistryEntry.accepted(
        tool=tool, validation=validation, birth_scenario=birth
    ).to_json()


STATE_CODE = '''
def plan_device_state_next_action(target_service: str, wifi_enabled: bool, cellular_enabled: bool, location_service_enabled: bool, low_battery_mode: bool) -> dict:
    """Plan one original ToolSandbox setter needed for a device-state precondition."""
    target = str(target_service or "").strip().lower().replace("service", "").replace("_", " ").strip()
    aliases = {
        "wi fi": "wifi",
        "wifi": "wifi",
        "cell": "cellular",
        "cellular": "cellular",
        "cellular service": "cellular",
        "location": "location",
        "location service": "location",
    }
    target = aliases.get(target, target)
    state_by_target = {
        "wifi": bool(wifi_enabled),
        "cellular": bool(cellular_enabled),
        "location": bool(location_service_enabled),
    }
    if target not in state_by_target:
        return {
            "ready": False,
            "tool_name": "",
            "arguments": {},
            "should_call": False,
            "reason": "unknown_target_service",
            "final_response_recommendation": "abstain:unknown_target_service",
            "followup_after_success": "",
        }
    if state_by_target[target]:
        return {
            "ready": True,
            "tool_name": "",
            "arguments": {},
            "should_call": False,
            "reason": target + "_already_enabled",
            "final_response_recommendation": "state_already_ready",
            "followup_after_success": "",
        }
    setter_by_target = {
        "wifi": "set_wifi_status",
        "cellular": "set_cellular_service_status",
        "location": "set_location_service_status",
    }
    if bool(low_battery_mode):
        return {
            "ready": False,
            "tool_name": "set_low_battery_mode_status",
            "arguments": {"on": False},
            "should_call": True,
            "reason": target + "_blocked_by_low_battery_mode",
            "final_response_recommendation": "turn_off_low_battery_mode_then_enable_" + target,
            "followup_after_success": setter_by_target[target],
        }
    return {
        "ready": False,
        "tool_name": setter_by_target[target],
        "arguments": {"on": True},
        "should_call": True,
        "reason": target + "_disabled",
        "final_response_recommendation": "enable_" + target,
        "followup_after_success": "",
    }
'''


INSUFFICIENT_CODE = '''
def recommend_safe_missing_information_response(task_family: str = "", missing_signal: str = "", intended_downstream_tool: str = "") -> dict:
    """Return a final-answer-ready abstention contract for missing-information tasks."""
    family = str(task_family or "").strip().lower()
    missing = str(missing_signal or "").strip()
    downstream = str(intended_downstream_tool or "").strip()
    trigger_text = " ".join([family, missing]).lower()
    should_abstain = bool(missing) or any(
        token in trigger_text
        for token in (
            "insufficient_information",
            "insufficient information",
            "missing",
            "cannot determine",
            "cannot_determine",
            "unknown",
            "ambiguous",
            "not enough",
        )
    )
    if not should_abstain:
        return {
            "should_abstain": False,
            "missing_information": [],
            "clarification_prompt": "",
            "forbidden_downstream_tools": [],
            "reason": "not_applicable",
            "final_answer_recommendation": "continue_normally",
        }
    if missing:
        missing_information = [missing]
    elif family:
        missing_information = [family]
    else:
        missing_information = ["required information is missing"]
    forbidden = [downstream] if downstream else []
    prompt = "I do not have enough information to complete that request."
    return {
        "should_abstain": True,
        "missing_information": missing_information,
        "clarification_prompt": prompt,
        "forbidden_downstream_tools": forbidden,
        "reason": "insufficient_information",
        "final_answer_recommendation": prompt,
    }
'''


STATE_SEQUENCE_CODE = '''
def plan_device_state_action_sequence(user_request: str, visible_state_or_error: str = "") -> dict:
    """Plan original ToolSandbox setting calls directly from a request or precondition error."""
    request = str(user_request or "")
    visible = str(visible_state_or_error or "")
    text = (request + " " + visible).lower().replace("_", " ")

    target = ""
    if "wi fi" in text or "wifi" in text or "internet" in text:
        target = "wifi"
    elif "cellular" in text or "cell service" in text or "mobile service" in text:
        target = "cellular"
    elif "location" in text or "where am i" in text or "current city" in text:
        target = "location"
    elif "low battery" in text or "low-battery" in text:
        target = "low_battery"

    if not target:
        return {
            "tool_name": "",
            "arguments": {},
            "should_call": False,
            "reason": "no_device_state_target",
            "action_sequence": [],
            "final_response_recommendation": "",
            "abstain_reason": "no wifi, cellular, location, or low-battery state target was visible",
        }

    wants_off = any(
        token in text
        for token in (
            "turn off",
            "turned off",
            "disable",
            "disabled",
            "shut off",
            "switch off",
            "off",
        )
    )
    wants_on = any(
        token in text
        for token in (
            "turn on",
            "turned on",
            "enable",
            "enabled",
            "fix",
            "help me",
            "can't access",
            "cannot access",
            "not working",
            "send",
            "search",
        )
    )
    if target == "low_battery":
        desired_on = not wants_off
        action = {
            "tool_name": "set_low_battery_mode_status",
            "arguments": {"on": bool(desired_on)},
            "reason": "set_low_battery_mode",
        }
        return {
            "tool_name": action["tool_name"],
            "arguments": action["arguments"],
            "should_call": True,
            "reason": action["reason"],
            "action_sequence": [action],
            "final_response_recommendation": "Low battery mode has been turned " + ("on." if desired_on else "off."),
            "abstain_reason": "",
        }

    desired_on = True if wants_on and not wants_off else not wants_off
    setter_by_target = {
        "wifi": "set_wifi_status",
        "cellular": "set_cellular_service_status",
        "location": "set_location_service_status",
    }
    label_by_target = {
        "wifi": "Wifi",
        "cellular": "Cellular service",
        "location": "Location service",
    }
    actions = []
    if desired_on and target in {"wifi", "cellular", "location"}:
        actions.append(
            {
                "tool_name": "set_low_battery_mode_status",
                "arguments": {"on": False},
                "reason": "clear_low_battery_before_enabling_service",
            }
        )
    actions.append(
        {
            "tool_name": setter_by_target[target],
            "arguments": {"on": bool(desired_on)},
            "reason": "set_" + target + ("_on" if desired_on else "_off"),
        }
    )
    final = label_by_target[target] + " has been turned " + ("on." if desired_on else "off.")
    return {
        "tool_name": actions[0]["tool_name"],
        "arguments": actions[0]["arguments"],
        "should_call": True,
        "reason": actions[0]["reason"],
        "action_sequence": actions,
        "final_response_recommendation": final,
        "abstain_reason": "",
    }
'''


INSUFFICIENT_DOMAIN_CODE = '''
def recommend_domain_safe_abstention(user_request: str, available_original_tools: str = "", missing_signal: str = "") -> dict:
    """Return a domain-specific final answer when the safe action is to abstain."""
    request = str(user_request or "")
    tools_text = str(available_original_tools or "")
    missing = str(missing_signal or "")
    text = " ".join([request, tools_text, missing]).lower().replace("_", " ")
    available = {item.strip() for item in tools_text.replace(";", ",").split(",") if item.strip()}

    forbidden = []
    missing_items = []
    final = ""
    reason = "insufficient_information"

    asks_remove_contact = any(token in text for token in ("delete", "remove", "get him out")) and "contact" in text
    asks_modify_contact = any(token in text for token in ("update", "change", "modify")) and "contact" in text
    mentions_message_recency = any(token in text for token in ("last person", "last message", "sent a message", "contacted last", "messaged"))
    asks_reminder_recency = "reminder" in text and any(token in text for token in ("upcoming", "yesterday", "today", "latest", "last", "later"))
    asks_calendar_delta = any(token in text for token in ("how many days", "days till", "days until", "holiday"))
    asks_location = any(token in text for token in ("where am i", "current location", "current city", "my location"))

    if asks_remove_contact and "remove_contact" not in available:
        forbidden = ["remove_contact"]
        missing_items = ["remove_contact tool"]
        final = "I cannot remove that contact because the contact-removal tool is not available."
        reason = "required_action_tool_unavailable"
    elif asks_remove_contact and "search_contacts" not in available:
        forbidden = ["remove_contact"]
        missing_items = ["contact lookup result"]
        final = "I cannot safely remove that contact because I cannot identify a concrete contact record first."
        reason = "required_contact_lookup_unavailable"
    elif asks_modify_contact and mentions_message_recency:
        forbidden = ["modify_contact"]
        missing_items = ["message history identifying the non-self counterparty"]
        final = "I cannot update that contact because I cannot determine which non-self contact the request refers to."
        reason = "missing_message_counterparty"
    elif asks_reminder_recency and "get_current_timestamp" not in available:
        forbidden = ["search_reminder", "modify_reminder", "remove_reminder"]
        missing_items = ["current datetime"]
        final = "I cannot determine the requested reminder without the current date and time."
        reason = "missing_current_datetime"
    elif asks_calendar_delta and "get_current_timestamp" not in available:
        forbidden = ["timestamp_diff"]
        missing_items = ["current date"]
        final = "I cannot determine the number of days without the current date."
        reason = "missing_current_date"
    elif asks_location:
        forbidden = ["search_lat_lon", "get_current_location"]
        missing_items = ["current location"]
        final = "I cannot determine your current location from the available information."
        reason = "missing_location"
    elif missing:
        missing_items = [missing]
        final = "I do not have enough information to complete that request."
    else:
        return {
            "should_abstain": False,
            "missing_information": [],
            "forbidden_downstream_tools": [],
            "reason": "not_applicable",
            "final_answer_recommendation": "continue_normally",
        }

    return {
        "should_abstain": True,
        "missing_information": missing_items,
        "forbidden_downstream_tools": forbidden,
        "reason": reason,
        "final_answer_recommendation": final,
    }
'''


def _state_tool() -> dict[str, Any]:
    spec = ToolSpec(
        tool_name="plan_device_state_next_action",
        family=ToolFamily.STATE_PRECONDITION_HELPER,
        description=(
            "Plan exactly one next original ToolSandbox setter for wifi, cellular, "
            "or location service precondition tasks. Use after checking visible "
            "device state with the original getter tools. If low battery mode is "
            "on and the target service is disabled, call the returned "
            "set_low_battery_mode_status first, then call the followup setter "
            "shown in followup_after_success. The helper is pure and performs no "
            "side effects itself."
        ),
        inputs=(
            ToolInput(
                "target_service", "str", "Target service: wifi, cellular, or location."
            ),
            ToolInput("wifi_enabled", "bool", "Visible result from get_wifi_status."),
            ToolInput(
                "cellular_enabled",
                "bool",
                "Visible result from get_cellular_service_status.",
            ),
            ToolInput(
                "location_service_enabled",
                "bool",
                "Visible result from get_location_service_status.",
            ),
            ToolInput(
                "low_battery_mode",
                "bool",
                "Visible result from get_low_battery_mode_status.",
            ),
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
                "final_response_recommendation": {"type": "string"},
                "followup_after_success": {"type": "string"},
            },
            "required": ["tool_name", "arguments", "should_call", "reason"],
        },
        positive_triggers=(
            "low_battery_mode",
            "wifi_off",
            "cellular_off",
            "turn_on_wifi",
            "turn_on_cellular",
            "turn_on_location",
            "send_message_with_contact_content_cellular_off",
            "find_days_till_holiday_wifi_off",
            "find_temperature_f_with_location_wifi_off",
        ),
        negative_triggers=(
            "insufficient_information",
            "unknown_target_service",
            "already_ready",
            "get_wifi",
            "get_cellular",
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
            "Return should_call false with an empty tool_name for unknown target "
            "services or when the target service is already enabled."
        ),
        generalization_rationale=(
            "The same precondition pattern recurs across wifi, cellular, location, "
            "message-send, weather, calendar, and reminder workflows where a "
            "disabled service or low battery mode blocks the requested task."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=6,
        applicable_task_families=(
            "turn_on_wifi_low_battery_mode",
            "turn_on_cellular_low_battery_mode",
            "turn_on_location_low_battery_mode",
            "send_message_with_contact_content_cellular_off",
            "find_days_till_holiday_wifi_off",
            "find_temperature_f_with_location_wifi_off",
        ),
        reason_tool_is_decisive=(
            "It chooses the exact benchmark setter and arguments for the next "
            "precondition side effect instead of leaving the actor to infer the "
            "legal ordering around low battery mode."
        ),
        shortfall_cluster_evidence=(
            "Broad500 settings/device-state bucket had 124 tasks and 80 no-visible-helper cases.",
            "Prior generic state helper was too weak; this version has scalar inputs and exact setter names.",
        ),
        known_failure_mechanisms_addressed=(
            "state_helper_opaque_dict_input_contract",
            "output_not_trace_compatible",
            "low_battery_precondition_ordering",
        ),
        final_state_preservation_plan=(
            "The helper returns only original ToolSandbox setter names and "
            "arguments. The actor must execute those setters; the helper itself "
            "does not mutate state."
        ),
        grading_accounting_note=(
            "Canonical route is preserved because the returned original setter "
            "must still be called and traced."
        ),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary=(
                "Broad500 exposed a large settings/device-state bucket where no "
                "effective helper was available for many service precondition tasks."
            ),
            signals=("no_current_helper_fit", "side_effect_precondition_ordering"),
            failed_tool_calls=(
                "set_wifi_status",
                "set_cellular_service_status",
                "set_location_service_status",
            ),
            planner_failures=("low_battery_mode_requires_ordered_setter_sequence",),
        ),
    )
    tool = GeneratedTool(spec=spec, code=STATE_CODE)
    examples = (
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
                "reason": "wifi_blocked_by_low_battery_mode",
                "final_response_recommendation": "turn_off_low_battery_mode_then_enable_wifi",
                "followup_after_success": "set_wifi_status",
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
                "reason": "cellular_disabled",
                "final_response_recommendation": "enable_cellular",
                "followup_after_success": "",
            },
            held_out=True,
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
                "reason": "location_already_enabled",
                "final_response_recommendation": "state_already_ready",
                "followup_after_success": "",
            },
            negative_applicability=True,
        ),
    )
    return _entry(tool, examples, "turn_on_wifi_low_battery_mode")


def _insufficient_tool() -> dict[str, Any]:
    spec = ToolSpec(
        tool_name="recommend_safe_missing_information_response",
        family=ToolFamily.VALIDATION_ABSTENTION_HELPER,
        description=(
            "Final-answer-ready missing-information guard. Use on tasks where "
            "the user request cannot be completed from visible state, visible "
            "records, or available tools. It returns should_abstain, a concise "
            "missing-information list, a clarification/final-response sentence, "
            "and downstream tools that should not be called."
        ),
        inputs=(
            ToolInput(
                "task_family",
                "str",
                "Short task family or visible reason, such as insufficient_information.",
            ),
            ToolInput(
                "missing_signal",
                "str",
                "Specific missing fact or precondition if known.",
            ),
            ToolInput(
                "intended_downstream_tool",
                "str",
                "Original tool to avoid when information is missing.",
            ),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "should_abstain": {"type": "boolean"},
                "missing_information": {"type": "array", "items": {"type": "string"}},
                "clarification_prompt": {"type": "string"},
                "forbidden_downstream_tools": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "reason": {"type": "string"},
                "final_answer_recommendation": {"type": "string"},
            },
            "required": [
                "should_abstain",
                "missing_information",
                "clarification_prompt",
                "forbidden_downstream_tools",
                "reason",
                "final_answer_recommendation",
            ],
        },
        positive_triggers=(
            "insufficient_information",
            "cannot_determine",
            "missing_information",
            "no_search_contacts_insufficient_information",
            "no_remove_contact_insufficient_information",
        ),
        negative_triggers=(
            "turn_on_wifi_low_battery_mode",
            "turn_on_cellular_low_battery_mode",
            "turn_on_location_low_battery_mode",
        ),
        abstain_behavior=(
            "Return should_abstain true with a final-answer-ready sentence when "
            "the task is missing required information. Return should_abstain "
            "false only when no missing-information signal is supplied."
        ),
        generalization_rationale=(
            "Missing-information tasks recur across location, calendar, contact, "
            "reminder, message, and external-service families; the safe behavior "
            "is to avoid fabricated answers or unsafe side effects."
        ),
        canonical_route_substitution_risk="low",
        final_state_preservation_plan=(
            "The helper has no side effects and forbids downstream calls only "
            "when information is missing; final state is preserved by abstention."
        ),
        grading_accounting_note=(
            "The helper may replace a failed search/action path with a correct "
            "abstention response; outcome is primary and canonical substitution "
            "is reported separately."
        ),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary=(
                "Broad500 safe insufficient-information bucket had 119 tasks and "
                "111 no-visible-helper cases, while earlier broad guards were too "
                "record-specific and not final-answer-ready."
            ),
            signals=("no_current_helper_fit", "missing_information_minefield"),
            visible_data_gaps=("required user or service information absent",),
            final_answer_route_mismatch=True,
        ),
    )
    tool = GeneratedTool(spec=spec, code=INSUFFICIENT_CODE)
    examples = (
        ToolExample(
            {
                "task_family": "insufficient_information",
                "missing_signal": "current location is unavailable",
                "intended_downstream_tool": "search_lat_lon",
            },
            {
                "should_abstain": True,
                "missing_information": ["current location is unavailable"],
                "clarification_prompt": "I do not have enough information to complete that request.",
                "forbidden_downstream_tools": ["search_lat_lon"],
                "reason": "insufficient_information",
                "final_answer_recommendation": "I do not have enough information to complete that request.",
            },
        ),
        ToolExample(
            {
                "task_family": "remove_contact_by_phone_no_search_contacts_insufficient_information",
                "missing_signal": "",
                "intended_downstream_tool": "remove_contact",
            },
            {
                "should_abstain": True,
                "missing_information": [
                    "remove_contact_by_phone_no_search_contacts_insufficient_information"
                ],
                "clarification_prompt": "I do not have enough information to complete that request.",
                "forbidden_downstream_tools": ["remove_contact"],
                "reason": "insufficient_information",
                "final_answer_recommendation": "I do not have enough information to complete that request.",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "task_family": "normal_search",
                "missing_signal": "",
                "intended_downstream_tool": "",
            },
            {
                "should_abstain": False,
                "missing_information": [],
                "clarification_prompt": "",
                "forbidden_downstream_tools": [],
                "reason": "not_applicable",
                "final_answer_recommendation": "continue_normally",
            },
            negative_applicability=True,
        ),
    )
    return _entry(tool, examples, "find_days_till_holiday_insufficient_information")


def _state_sequence_tool() -> dict[str, Any]:
    spec = ToolSpec(
        tool_name="plan_device_state_action_sequence",
        family=ToolFamily.STATE_PRECONDITION_HELPER,
        description=(
            "State action sequence planner for wifi, cellular, location service, "
            "and low battery mode. Use from the user request or from a visible "
            "precondition/error message. It returns the first original setter in "
            "tool_name/arguments plus an action_sequence of original ToolSandbox "
            "setters to call in order. For enabling wifi/cellular/location it "
            "clears low battery mode first, then enables the requested service. "
            "The helper is pure and performs no side effects itself."
        ),
        inputs=(
            ToolInput(
                "user_request", "str", "The current user request or task wording."
            ),
            ToolInput(
                "visible_state_or_error",
                "str",
                "Visible state/error text from prior original tool calls, or empty string.",
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
                "action_sequence": {"type": "array", "items": {"type": "object"}},
                "final_response_recommendation": {"type": "string"},
                "abstain_reason": {"type": "string"},
            },
            "required": ["tool_name", "arguments", "should_call", "reason"],
        },
        positive_triggers=(
            "low_battery_mode",
            "wifi_off",
            "cellular_off",
            "location_service_off",
            "turn_on_wifi",
            "turn_on_cellular",
            "turn_on_location",
            "turn_off_wifi",
            "turn_off_cellular",
            "send_message_with_contact_content_cellular_off",
            "find_days_till_holiday_wifi_off",
            "find_temperature_f_with_location_wifi_off",
        ),
        negative_triggers=(
            "insufficient_information",
            "get_wifi",
            "get_cellular",
            "get_location",
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
            "Return should_call false with abstain_reason when no device-state "
            "target is visible in the request or prior error."
        ),
        generalization_rationale=(
            "The same pure request-to-setter planning step recurs across direct "
            "settings toggles and downstream tasks blocked by wifi, cellular, "
            "location service, or low battery mode."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=8,
        applicable_task_families=(
            "wifi_off",
            "cellular_off",
            "turn_on_wifi_low_battery_mode",
            "turn_on_cellular_low_battery_mode",
            "turn_on_location_low_battery_mode",
            "send_message_with_contact_content_cellular_off",
            "find_days_till_holiday_wifi_off",
            "find_temperature_f_with_location_wifi_off",
        ),
        reason_tool_is_decisive=(
            "It returns original setter calls and ordered low-battery/service "
            "sequences from task text, avoiding the previous full-state-vector "
            "interface that was visible but naturally uncalled."
        ),
        shortfall_cluster_evidence=(
            "The first action-precondition pilot made plan_device_state_next_action "
            "visible on 14/20 settings tasks but called on 0/20.",
            "Broad500 settings/device-state bucket had 124 tasks and 80 no-visible-helper cases.",
        ),
        known_failure_mechanisms_addressed=(
            "visible_not_called_due_to_full_state_vector_contract",
            "low_battery_precondition_ordering",
            "output_not_final_action_ready",
        ),
        final_state_preservation_plan=(
            "The helper does not mutate state. It returns only original setter "
            "names and arguments for the actor to execute when appropriate."
        ),
        grading_accounting_note=(
            "Generated helper contribution is credited only when natural calls "
            "lead to original ToolSandbox setter calls and better task outcome."
        ),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary=(
                "Settings/device-state tasks need a narrow, final-action-ready "
                "planner that is callable before the actor has manually assembled "
                "all state booleans."
            ),
            signals=("visible_not_called", "side_effect_precondition_ordering"),
            failed_tool_calls=(
                "set_wifi_status",
                "set_cellular_service_status",
                "set_location_service_status",
            ),
            planner_failures=("state_vector_schema_too_deep_for_natural_adoption",),
        ),
    )
    tool = GeneratedTool(spec=spec, code=STATE_SEQUENCE_CODE)
    examples = (
        ToolExample(
            {
                "user_request": "Turn on location service",
                "visible_state_or_error": "",
            },
            {
                "tool_name": "set_low_battery_mode_status",
                "arguments": {"on": False},
                "should_call": True,
                "reason": "clear_low_battery_before_enabling_service",
                "action_sequence": [
                    {
                        "tool_name": "set_low_battery_mode_status",
                        "arguments": {"on": False},
                        "reason": "clear_low_battery_before_enabling_service",
                    },
                    {
                        "tool_name": "set_location_service_status",
                        "arguments": {"on": True},
                        "reason": "set_location_on",
                    },
                ],
                "final_response_recommendation": "Location service has been turned on.",
                "abstain_reason": "",
            },
        ),
        ToolExample(
            {
                "user_request": "Turn off wifi",
                "visible_state_or_error": "",
            },
            {
                "tool_name": "set_wifi_status",
                "arguments": {"on": False},
                "should_call": True,
                "reason": "set_wifi_off",
                "action_sequence": [
                    {
                        "tool_name": "set_wifi_status",
                        "arguments": {"on": False},
                        "reason": "set_wifi_off",
                    }
                ],
                "final_response_recommendation": "Wifi has been turned off.",
                "abstain_reason": "",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "user_request": "What is my next reminder?",
                "visible_state_or_error": "",
            },
            {
                "tool_name": "",
                "arguments": {},
                "should_call": False,
                "reason": "no_device_state_target",
                "action_sequence": [],
                "final_response_recommendation": "",
                "abstain_reason": "no wifi, cellular, location, or low-battery state target was visible",
            },
            negative_applicability=True,
        ),
    )
    return _entry(tool, examples, "settings_state_pilot20_repair")


def _insufficient_domain_tool() -> dict[str, Any]:
    spec = ToolSpec(
        tool_name="recommend_domain_safe_abstention",
        family=ToolFamily.VALIDATION_ABSTENTION_HELPER,
        description=(
            "Domain-specific insufficient-information responder. Use when the "
            "request is unsafe or impossible because a required tool, concrete "
            "record id, current time/date, current location, or message-derived "
            "counterparty is unavailable. Pass the user request and the visible "
            "comma-separated original ToolSandbox tool names. If should_abstain "
            "is true, answer with final_answer_recommendation and do not call "
            "forbidden_downstream_tools."
        ),
        inputs=(
            ToolInput(
                "user_request",
                "str",
                "The current user request or concise task wording.",
            ),
            ToolInput(
                "available_original_tools",
                "str",
                "Comma-separated original ToolSandbox tool names visible for this task.",
            ),
            ToolInput(
                "missing_signal",
                "str",
                "Visible missing fact or tool, or empty string.",
            ),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "should_abstain": {"type": "boolean"},
                "missing_information": {"type": "array", "items": {"type": "string"}},
                "forbidden_downstream_tools": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "reason": {"type": "string"},
                "final_answer_recommendation": {"type": "string"},
            },
            "required": [
                "should_abstain",
                "missing_information",
                "forbidden_downstream_tools",
                "reason",
                "final_answer_recommendation",
            ],
        },
        positive_triggers=(
            "insufficient_information",
            "cannot_determine",
            "missing_information",
            "no_search_contacts_insufficient_information",
            "no_remove_contact_insufficient_information",
            "missing_current_datetime",
            "missing_message_counterparty",
        ),
        negative_triggers=(
            "turn_on_wifi_low_battery_mode",
            "turn_on_cellular_low_battery_mode",
            "turn_on_location_low_battery_mode",
            "wifi_off",
            "cellular_off",
        ),
        abstain_behavior=(
            "Return should_abstain true with a specific final answer and forbidden "
            "downstream tools for missing-tool, missing-current-time, missing-location, "
            "or ambiguous-message-counterparty cases. Return should_abstain false "
            "only when none of those signals applies."
        ),
        generalization_rationale=(
            "The same abstention categories recur across contact CRUD, reminder "
            "recency, holiday-date, location, and message-counterparty tasks."
        ),
        canonical_route_substitution_risk="medium",
        final_state_preservation_plan=(
            "The helper is pure. It explicitly lists forbidden downstream tools "
            "so the actor can avoid unsafe contact/reminder/message side effects."
        ),
        grading_accounting_note=(
            "Outcome and minefield avoidance are primary; canonical reference "
            "changes are secondary because correct abstention may replace failed "
            "or unsafe action paths."
        ),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary=(
                "The first safe-insufficient pilot naturally called a generic guard "
                "10/20 times but the called subset regressed, indicating output "
                "specificity rather than visibility was the blocker."
            ),
            signals=("called_subset_negative", "final_answer_not_domain_specific"),
            visible_data_gaps=(
                "current datetime",
                "contact record id",
                "message counterparty",
            ),
            final_answer_route_mismatch=True,
        ),
    )
    tool = GeneratedTool(spec=spec, code=INSUFFICIENT_DOMAIN_CODE)
    examples = (
        ToolExample(
            {
                "user_request": "Remove phone number +12453344098 from my contact",
                "available_original_tools": "search_contacts",
                "missing_signal": "",
            },
            {
                "should_abstain": True,
                "missing_information": ["remove_contact tool"],
                "forbidden_downstream_tools": ["remove_contact"],
                "reason": "required_action_tool_unavailable",
                "final_answer_recommendation": "I cannot remove that contact because the contact-removal tool is not available.",
            },
        ),
        ToolExample(
            {
                "user_request": "What's my upcoming reminder",
                "available_original_tools": "search_reminder, shift_timestamp, timestamp_to_datetime_info",
                "missing_signal": "",
            },
            {
                "should_abstain": True,
                "missing_information": ["current datetime"],
                "forbidden_downstream_tools": [
                    "search_reminder",
                    "modify_reminder",
                    "remove_reminder",
                ],
                "reason": "missing_current_datetime",
                "final_answer_recommendation": "I cannot determine the requested reminder without the current date and time.",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "user_request": "Search contacts for Alice",
                "available_original_tools": "search_contacts",
                "missing_signal": "",
            },
            {
                "should_abstain": False,
                "missing_information": [],
                "forbidden_downstream_tools": [],
                "reason": "not_applicable",
                "final_answer_recommendation": "continue_normally",
            },
            negative_applicability=True,
        ),
    )
    return _entry(tool, examples, "safe_insufficient_pilot20_repair")


def _build_registries() -> dict[str, Any]:
    top_tools = _load_tools(TOP_TOOL_REGISTRY)
    state_entry = _state_tool()
    insufficient_entry = _insufficient_tool()
    state_sequence_entry = _state_sequence_tool()
    insufficient_domain_entry = _insufficient_domain_tool()
    state_hash = _write_json(
        STATE_REGISTRY, {"tools": {"plan_device_state_next_action": state_entry}}
    )
    insufficient_hash = _write_json(
        INSUFFICIENT_REGISTRY,
        {"tools": {"recommend_safe_missing_information_response": insufficient_entry}},
    )
    combined_tools = copy.deepcopy(top_tools)
    combined_tools["plan_device_state_next_action"] = state_entry
    combined_tools["recommend_safe_missing_information_response"] = insufficient_entry
    combined_hash = _write_json(COMBINED_REGISTRY, {"tools": combined_tools})
    state_sequence_hash = _write_json(
        STATE_SEQUENCE_REGISTRY,
        {"tools": {"plan_device_state_action_sequence": state_sequence_entry}},
    )
    insufficient_domain_hash = _write_json(
        INSUFFICIENT_DOMAIN_REGISTRY,
        {"tools": {"recommend_domain_safe_abstention": insufficient_domain_entry}},
    )
    combined_v2_tools = copy.deepcopy(top_tools)
    combined_v2_tools["plan_device_state_action_sequence"] = state_sequence_entry
    combined_v2_tools["recommend_domain_safe_abstention"] = insufficient_domain_entry
    combined_v2_hash = _write_json(COMBINED_V2_REGISTRY, {"tools": combined_v2_tools})
    return {
        "state_precondition_next_action": {
            "path": str(STATE_REGISTRY),
            "sha256": state_hash,
            "tools": ["plan_device_state_next_action"],
        },
        "safe_insufficient_abstention": {
            "path": str(INSUFFICIENT_REGISTRY),
            "sha256": insufficient_hash,
            "tools": ["recommend_safe_missing_information_response"],
        },
        "top_tools_plus_action_precondition": {
            "path": str(COMBINED_REGISTRY),
            "sha256": combined_hash,
            "tools": sorted(combined_tools),
        },
        "state_action_sequence": {
            "path": str(STATE_SEQUENCE_REGISTRY),
            "sha256": state_sequence_hash,
            "tools": ["plan_device_state_action_sequence"],
        },
        "safe_insufficient_domain_response": {
            "path": str(INSUFFICIENT_DOMAIN_REGISTRY),
            "sha256": insufficient_domain_hash,
            "tools": ["recommend_domain_safe_abstention"],
        },
        "top_tools_plus_action_precondition_v2": {
            "path": str(COMBINED_V2_REGISTRY),
            "sha256": combined_v2_hash,
            "tools": sorted(combined_v2_tools),
        },
    }


def _records_by_name() -> dict[str, ScenarioRecord]:
    return {record.name: record for record in scenario_records()}


def _formal_records() -> list[ScenarioRecord]:
    return _manifest_records(FORMAL500, "full_benchmark")


def _formal1000_records() -> list[ScenarioRecord]:
    return _manifest_records(FORMAL1000, "full_benchmark")


def _manifest_records(path: Path, split_name: str) -> list[ScenarioRecord]:
    records = _records_by_name()
    payload = json.loads(path.read_text(encoding="utf-8"))
    names = [str(row["name"]) for row in payload["splits"][split_name]]
    return [records[name] for name in names]


def _bucket(record: ScenarioRecord) -> str:
    name = record.name.lower()
    categories = {category.upper() for category in record.categories}
    if "insufficient_information" in name or "INSUFFICIENT_INFORMATION" in categories:
        return "safe_insufficient_information"
    family = base_task_family(record.name).lower()
    if any(
        token in name
        for token in (
            "wifi",
            "cellular",
            "location",
            "low_battery",
            "device_state",
            "setting",
            "settings",
            "toggle",
            "permission",
        )
    ):
        return "settings_device_state"
    if any(
        token in family
        for token in (
            "add_contact",
            "modify_contact",
            "remove_contact",
            "update_contact",
        )
    ):
        return "contact_crud"
    if any(
        token in family
        for token in (
            "add_reminder",
            "modify_reminder",
            "remove_reminder",
        )
    ):
        return "reminder_crud_scheduling"
    if "send_message" in family:
        return "send_message_preconditions"
    return "other"


def _round_robin(records: list[ScenarioRecord], limit: int) -> list[ScenarioRecord]:
    buckets: dict[str, deque[ScenarioRecord]] = defaultdict(deque)
    for record in sorted(records, key=lambda item: item.name):
        buckets[base_task_family(record.name)].append(record)
    selected: list[ScenarioRecord] = []
    families = sorted(buckets)
    while any(buckets.values()) and len(selected) < limit:
        for family in families:
            if len(selected) >= limit:
                break
            if buckets[family]:
                selected.append(buckets[family].popleft())
    if len(selected) != limit:
        raise RuntimeError(f"needed {limit} records, selected {len(selected)}")
    return selected


def _row(
    record: ScenarioRecord, split: str, bucket: str, *, final_evaluation: bool
) -> dict[str, Any]:
    return {
        "scenario_id": record.name,
        "family_label": base_task_family(record.name),
        "task_labels": list(record.categories),
        "bucket": bucket,
        "allowed_tools": list(record.allowed_tools),
        "truth_labels_inspected": False,
        "used_for_generation": False,
        "used_for_repair": False,
        "used_for_routing": False,
        "used_for_validation": True,
        "final_evaluation": final_evaluation,
        "split": split,
    }


def _diversity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    families = Counter(str(row["family_label"]) for row in rows)
    buckets = Counter(str(row["bucket"]) for row in rows)
    return {
        "scenario_count": len(rows),
        "distinct_family_count": len(families),
        "family_counts": dict(sorted(families.items())),
        "bucket_counts": dict(sorted(buckets.items())),
        "largest_family_count": max(families.values()) if families else 0,
        "largest_family_share": max(families.values()) / len(rows) if rows else 0.0,
        "near_duplicate_dominated": bool(
            rows and max(families.values()) / len(rows) > 0.35
        ),
    }


def _manifest(
    manifest_type: str, splits: dict[str, list[dict[str, Any]]], note: str
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_type": manifest_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "protected_claim_evidence": False,
        "truth_labels_inspected": False,
        "selection_policy": {
            "used_truth_labels": False,
            "used_expected_answers": False,
            "used_cache_availability": False,
            "uses_prior_experimental_gap_assessment": True,
            "selection_note": note,
        },
        "split_aliases": {
            "pilot_20": next(name for name in splits if name.endswith("20")),
            "expanded_60": next(name for name in splits if name.endswith("60")),
            "confirm_100": next(name for name in splits if name.endswith("100")),
            "validate_100": next(name for name in splits if name.endswith("100")),
        },
        "splits": splits,
        "split_sizes": {name: len(rows) for name, rows in splits.items()},
        "split_diversity": {name: _diversity(rows) for name, rows in splits.items()},
        "cache_policy": {
            "baseline_control_cache": "use-if-eligible",
            "sage_candidate_cache": "fresh_only",
            "openai_response_cache_for_candidate": "disabled",
        },
    }


def _build_bucket_manifest(
    *,
    records: list[ScenarioRecord],
    bucket_name: str,
    split_prefix: str,
    path: Path,
    note: str,
) -> dict[str, Any]:
    selected = _round_robin(records, 100)
    splits = {
        f"{split_prefix}20": [
            _row(record, f"{split_prefix}20", bucket_name, final_evaluation=False)
            for record in selected[:20]
        ],
        f"{split_prefix}60": [
            _row(record, f"{split_prefix}60", bucket_name, final_evaluation=False)
            for record in selected[:60]
        ],
        f"{split_prefix}100": [
            _row(record, f"{split_prefix}100", bucket_name, final_evaluation=True)
            for record in selected
        ],
    }
    payload = _manifest(
        f"sage_gap_closure_lab_{split_prefix.rstrip('_')}_splits",
        splits,
        note,
    )
    digest = _write_json(path, payload)
    return {
        "path": str(path),
        "sha256": digest,
        "split_sizes": payload["split_sizes"],
        "split_diversity": payload["split_diversity"],
    }


def _build_manifests() -> dict[str, Any]:
    formal = _formal_records()
    formal1000 = _formal1000_records()
    settings = [
        record for record in formal if _bucket(record) == "settings_device_state"
    ]
    insufficient = [
        record
        for record in formal
        if _bucket(record) == "safe_insufficient_information"
    ]
    contact = [record for record in formal1000 if _bucket(record) == "contact_crud"]
    reminder = [
        record for record in formal1000 if _bucket(record) == "reminder_crud_scheduling"
    ]
    if len(settings) < 100 or len(insufficient) < 100:
        raise RuntimeError(
            f"not enough bucket records: settings={len(settings)}, insufficient={len(insufficient)}"
        )
    if len(contact) < 100 or len(reminder) < 100:
        raise RuntimeError(
            f"not enough CRUD bucket records: contact={len(contact)}, reminder={len(reminder)}"
        )
    settings_summary = _build_bucket_manifest(
        records=settings,
        bucket_name="settings_device_state",
        split_prefix="settings_device_state_",
        path=SETTINGS_MANIFEST,
        note=(
            "Formal500 scenario names filtered by settings/device-state tokens and "
            "round-robin by base family. No labels or cache availability used."
        ),
    )
    insufficient_summary = _build_bucket_manifest(
        records=insufficient,
        bucket_name="safe_insufficient_information",
        split_prefix="safe_insufficient_information_",
        path=INSUFFICIENT_MANIFEST,
        note=(
            "Formal500 scenario names filtered by insufficient-information category "
            "or token and round-robin by base family. No labels or cache availability used."
        ),
    )
    contact_summary = _build_bucket_manifest(
        records=contact,
        bucket_name="contact_crud",
        split_prefix="contact_crud_",
        path=CONTACT_MANIFEST,
        note=(
            "Formal1000 scenario names filtered to contact CRUD base families and "
            "round-robin by base family. No labels or cache availability used."
        ),
    )
    reminder_summary = _build_bucket_manifest(
        records=reminder,
        bucket_name="reminder_crud_scheduling",
        split_prefix="reminder_crud_scheduling_",
        path=REMINDER_MANIFEST,
        note=(
            "Formal1000 scenario names filtered to reminder CRUD/scheduling base "
            "families and round-robin by base family. No labels or cache availability used."
        ),
    )
    combined_candidates = _round_robin(settings, 50) + _round_robin(insufficient, 50)
    combined = _round_robin(combined_candidates, 100)
    combined_splits = {
        "action_precondition_combined20": [
            _row(
                record,
                "action_precondition_combined20",
                _bucket(record),
                final_evaluation=False,
            )
            for record in combined[:20]
        ],
        "action_precondition_combined60": [
            _row(
                record,
                "action_precondition_combined60",
                _bucket(record),
                final_evaluation=False,
            )
            for record in combined[:60]
        ],
        "action_precondition_combined100": [
            _row(
                record,
                "action_precondition_combined100",
                _bucket(record),
                final_evaluation=True,
            )
            for record in combined
        ],
    }
    combined_payload = _manifest(
        "sage_gap_closure_lab_action_precondition_combined_splits",
        combined_splits,
        "Balanced 50/50 settings-device-state and safe-insufficient-information split selected by family round-robin only.",
    )
    combined_hash = _write_json(COMBINED_MANIFEST, combined_payload)

    broad_selected = _round_robin(formal, 100)
    broad_splits = {
        "action_precondition_broad20": [
            _row(
                record,
                "action_precondition_broad20",
                _bucket(record),
                final_evaluation=False,
            )
            for record in broad_selected[:20]
        ],
        "action_precondition_broad60": [
            _row(
                record,
                "action_precondition_broad60",
                _bucket(record),
                final_evaluation=False,
            )
            for record in broad_selected[:60]
        ],
        "action_precondition_broad100": [
            _row(
                record,
                "action_precondition_broad100",
                _bucket(record),
                final_evaluation=True,
            )
            for record in broad_selected
        ],
    }
    broad_payload = _manifest(
        "sage_gap_closure_lab_action_precondition_broad_splits",
        broad_splits,
        "Formal500 scenario names round-robin by base family for broad add-on smoke after narrow bucket evidence.",
    )
    broad_hash = _write_json(BROAD_MANIFEST, broad_payload)
    return {
        "settings_device_state": settings_summary,
        "safe_insufficient_information": insufficient_summary,
        "settings_insufficient_combined": {
            "path": str(COMBINED_MANIFEST),
            "sha256": combined_hash,
            "split_sizes": combined_payload["split_sizes"],
            "split_diversity": combined_payload["split_diversity"],
        },
        "contact_crud": contact_summary,
        "reminder_crud_scheduling": reminder_summary,
        "broad": {
            "path": str(BROAD_MANIFEST),
            "sha256": broad_hash,
            "split_sizes": broad_payload["split_sizes"],
            "split_diversity": broad_payload["split_diversity"],
        },
    }


def main() -> None:
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "protected_claim_evidence": False,
        "objective": (
            "Find narrow high-lift solutions for settings/device-state and "
            "safe insufficient-information buckets, then combine with the current top-tool set."
        ),
        "registries": _build_registries(),
        "manifests": _build_manifests(),
        "leakage_controls": {
            "truth_labels_inspected": False,
            "used_cache_availability_for_selection": False,
            "scenario_ids_encoded_into_tools_or_router": False,
            "uses_prior_broad500_bucket_assessment_for_category_targeting": True,
            "protected_claim_evidence": False,
        },
    }
    _write_json(SUMMARY_OUT, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
