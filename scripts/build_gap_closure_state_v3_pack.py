# mypy: ignore-errors
"""Build a repaired device-state action helper for gap-closure experiments.

Experimental only. The prior state action helper received natural calls but
regressed on expanded60 because it sometimes treated visible "off" state text
as a user command to turn the service off, and direct-setting final answers were
often over-verbose. This v3 helper keeps the scalar request/error interface but
returns stricter setter ordering and exact final-response recommendations.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

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
SCHEDULE_V2_SOURCE = (
    REGISTRY_ROOT
    / "full_timestamp_no_field_plus_schedule_v2_pack"
    / "registry_manifest.json"
)
STATE_ONLY_OUT = (
    REGISTRY_ROOT / "state_action_sequence_v3_pack" / "registry_manifest.json"
)
COMBINED_OUT = (
    REGISTRY_ROOT
    / "full_timestamp_schedule_v2_plus_state_v3_pack"
    / "registry_manifest.json"
)
SUMMARY_OUT = MANIFEST_ROOT / "state_v3_pack_summary.json"


STATE_SEQUENCE_V3_CODE = '''
def plan_device_state_action_sequence_v3(user_request: str, visible_state_or_error: str = "") -> dict:
    """Plan safe original ToolSandbox state setters and exact final phrasing."""
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
                or "shut off " + term in request
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
        final = "Low battery mode has been turned " + ("on." if desired_on else "off.")
        action = {
            "tool_name": "set_low_battery_mode_status",
            "arguments": {"on": bool(desired_on)},
            "reason": "set_low_battery_mode_" + ("on" if desired_on else "off"),
        }
        return {
            "tool_name": action["tool_name"],
            "arguments": action["arguments"],
            "should_call": True,
            "reason": action["reason"],
            "action_sequence": [action],
            "final_response_recommendation": final,
            "continue_original_task_after_sequence": False,
            "abstain_reason": "",
        }

    target_terms = {
        "wifi": wifi_terms,
        "cellular": cellular_terms,
        "location": location_terms,
    }[target]
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

    # Treat "wifi is off" in visible state as a reason to turn it on, not as a
    # command to turn it off. Only explicit off commands in the user request set
    # the target service to false.
    desired_on = not off_command(target_terms)
    if on_command(target_terms):
        desired_on = True

    low_battery_already_clear = any(
        marker in text
        for marker in (
            "low battery mode is off",
            "low battery mode already disabled",
            "low battery mode false",
            "low battery=false",
            "already disabled",
        )
    )
    low_battery_blocks_service = bool(desired_on) and (
        ("low battery" in text and not low_battery_already_clear)
        or "cannot be turned on in low battery mode" in text
        or "blocked by low battery" in text
    )

    actions = []
    if low_battery_blocks_service:
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
    downstream_request = any(
        token in request
        for token in (
            "send ",
            "message",
            "find ",
            "search",
            "how many",
            "what is",
            "what's",
            "temperature",
            "weather",
            "reminder",
        )
    ) and not (on_command(target_terms) or off_command(target_terms))

    return {
        "tool_name": actions[0]["tool_name"],
        "arguments": actions[0]["arguments"],
        "should_call": True,
        "reason": actions[0]["reason"],
        "action_sequence": actions,
        "final_response_recommendation": "continue_original_task" if downstream_request else final,
        "continue_original_task_after_sequence": bool(downstream_request),
        "abstain_reason": "",
    }
'''


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
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8"))["tools"])


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


def _state_v3_entry() -> dict[str, Any]:
    spec = ToolSpec(
        tool_name="plan_device_state_action_sequence_v3",
        family=ToolFamily.STATE_PRECONDITION_HELPER,
        description=(
            "State action sequence v3 helper. Use for wifi, cellular service, "
            "location service, and low-battery mode tasks. It converts the user "
            "request plus visible state/error text into original ToolSandbox setter "
            "calls in action_sequence, preserving order around low battery mode. "
            "For direct settings tasks, answer exactly with final_response_recommendation. "
            "For downstream tasks, continue_original_task_after_sequence tells the "
            "actor to retry/continue the original request after setters succeed. "
            "Pure helper; it performs no side effects."
        ),
        inputs=(
            ToolInput(
                "user_request", "str", "The current user request or task wording."
            ),
            ToolInput(
                "visible_state_or_error",
                "str",
                "Visible state, prior setter error, or empty string.",
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
            "location_service_off",
            "low_battery_mode",
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
            "contact_recency",
            "reminder_recency",
            "search_only",
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
            "Return should_call false only when no wifi, cellular, location, or "
            "low-battery state target is visible."
        ),
        generalization_rationale=(
            "Settings/device-state and downstream precondition tasks repeatedly "
            "need the same side-effect-free mapping from state text/errors to "
            "legal original setter calls and exact final wording."
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
            "It separates visible off-state text from explicit user commands, "
            "returns low-battery/service setter order, and provides exact final "
            "phrasing for direct settings tasks."
        ),
        shortfall_cluster_evidence=(
            "Settings v2 expanded60 had natural calls but outcome regressed from "
            "misread off-state text and over-verbose final answers.",
            "Broad500 assessment showed settings/device-state as one of the largest unsupported buckets.",
        ),
        known_failure_mechanisms_addressed=(
            "off_state_text_misread_as_turn_off_command",
            "over_verbose_final_setting_answer",
            "downstream_precondition_stops_before_original_task",
        ),
        final_state_preservation_plan=(
            "The helper returns only original setter names and arguments; the actor "
            "must perform any side effects through original ToolSandbox tools."
        ),
        grading_accounting_note=(
            "Direct-setting tasks should preserve exact outcome wording; downstream "
            "tasks should continue to the original requested action after state repair."
        ),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary=(
                "Prior state helper had adoption but insufficient value because "
                "its parser and final-response contract were too loose."
            ),
            signals=(
                "called_subset_negative",
                "final_answer_not_exact",
                "state_ordering_error",
            ),
            failed_tool_calls=(
                "set_wifi_status",
                "set_cellular_service_status",
                "set_location_service_status",
            ),
            planner_failures=("state_visible_off_text_confused_with_user_off_command",),
        ),
    )
    tool = GeneratedTool(spec=spec, code=STATE_SEQUENCE_V3_CODE)
    examples = (
        ToolExample(
            {
                "user_request": "Turn on wifi. Low battery mode is on.",
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
                        "tool_name": "set_wifi_status",
                        "arguments": {"on": True},
                        "reason": "set_wifi_on",
                    },
                ],
                "final_response_recommendation": "Wifi has been turned on.",
                "continue_original_task_after_sequence": False,
                "abstain_reason": "",
            },
        ),
        ToolExample(
            {
                "user_request": "Send a message to Alex saying running late",
                "visible_state_or_error": "PermissionError: Cellular service cannot be turned on in low battery mode",
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
                        "tool_name": "set_cellular_service_status",
                        "arguments": {"on": True},
                        "reason": "set_cellular_on",
                    },
                ],
                "final_response_recommendation": "continue_original_task",
                "continue_original_task_after_sequence": True,
                "abstain_reason": "",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "user_request": "Turn off wifi",
                "visible_state_or_error": "wifi is currently on",
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
                "continue_original_task_after_sequence": False,
                "abstain_reason": "",
            },
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
                "continue_original_task_after_sequence": False,
                "abstain_reason": "no_device_state_target",
            },
            negative_applicability=True,
        ),
    )
    return _entry(tool, examples, "settings_state_v2_expanded60_repair")


def main() -> None:
    state_entry = _state_v3_entry()
    state_hash = _write_json(
        STATE_ONLY_OUT,
        {"tools": {"plan_device_state_action_sequence_v3": state_entry}},
    )
    combined_tools = copy.deepcopy(_load_tools(SCHEDULE_V2_SOURCE))
    combined_tools["plan_device_state_action_sequence_v3"] = state_entry
    combined_hash = _write_json(COMBINED_OUT, {"tools": combined_tools})
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "protected_claim_evidence": False,
        "source_registry": str(SCHEDULE_V2_SOURCE),
        "registries": {
            "state_action_sequence_v3": {
                "path": str(STATE_ONLY_OUT),
                "sha256": state_hash,
                "tools": ["plan_device_state_action_sequence_v3"],
            },
            "full_timestamp_schedule_v2_plus_state_v3": {
                "path": str(COMBINED_OUT),
                "sha256": combined_hash,
                "tools": sorted(combined_tools),
            },
        },
        "repair_hypothesis": (
            "State v2 had natural calls but lost outcome through off-state parsing "
            "and over-verbose final answers. V3 tightens those contracts and keeps "
            "downstream precondition tasks from stopping after setters."
        ),
        "leakage_controls": {
            "truth_labels_inspected": False,
            "used_cache_availability_for_selection": False,
            "scenario_ids_encoded_into_tools_or_router": False,
            "protected_claim_evidence": False,
        },
    }
    digest = _write_json(SUMMARY_OUT, summary)
    summary["summary_sha256"] = digest
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
