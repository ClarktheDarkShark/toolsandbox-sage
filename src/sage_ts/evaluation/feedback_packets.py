"""Structured task feedback packets for V2.6 tool-birth decisions."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from sage_ts.evaluation.run_metrics import _read_json, _read_jsonl, _scenario_rows
from sage_ts.evaluation.task_strata import (
    base_task_family,
    classify_task_strata,
    expected_birth_opportunities,
    expected_helper_fit,
)

MAX_TEXT_CHARS = 1200
SIDE_EFFECT_TOOL_PREFIXES = (
    "add_",
    "modify_",
    "remove_",
    "send_",
    "update_",
    "turn_on_",
    "turn_off_",
)


def _truncate(value: Any, limit: int = MAX_TEXT_CHARS) -> Any:
    if value is None:
        return None
    if not isinstance(value, str):
        value = json.dumps(value, sort_keys=True, default=str)
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def _parse_json_maybe(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _first_existing_run_dir(arm_root: Path) -> Path | None:
    if not arm_root.exists():
        return None
    if (arm_root / "result_summary.json").exists() or (
        arm_root / "live_result_summary.json"
    ).exists():
        return arm_root
    children = [child for child in arm_root.iterdir() if child.is_dir()]
    children.sort(key=lambda path: path.name)
    for child in children:
        if (child / "result_summary.json").exists() or (
            child / "live_result_summary.json"
        ).exists():
            return child
    return children[0] if children else None


def resolve_arm_dirs(run_root: Path) -> tuple[Path | None, Path | None]:
    """Return control and candidate run dirs for a protocol run root."""
    control = _first_existing_run_dir(run_root / "control")
    candidate = _first_existing_run_dir(run_root / "candidate")
    return control, candidate


def _rows_by_name(run_dir: Path | None) -> dict[str, dict[str, Any]]:
    if run_dir is None:
        return {}
    return {str(row.get("name")): row for row in _scenario_rows(run_dir)}


def _jsonl_by_scenario(path: Path) -> dict[str, dict[str, Any]]:
    rows = _read_jsonl(path)
    return {str(row.get("scenario")): row for row in rows if row.get("scenario")}


def _conversation(run_dir: Path | None, scenario: str) -> list[dict[str, Any]]:
    if run_dir is None:
        return []
    path = run_dir / "trajectories" / scenario / "conversation.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _user_request_summary(conversation: list[dict[str, Any]], scenario: str) -> str:
    for message in conversation:
        if message.get("role") == "user" and message.get("content"):
            return str(_truncate(str(message.get("content")), 500))
    return scenario.replace("_", " ")


def _extract_tool_calls(conversation: list[dict[str, Any]]) -> list[dict[str, Any]]:
    outputs_by_id: dict[str, dict[str, Any]] = {}
    for message in conversation:
        if message.get("role") == "tool":
            call_id = str(message.get("tool_call_id") or "")
            outputs_by_id[call_id] = message

    calls: list[dict[str, Any]] = []
    for index, message in enumerate(conversation):
        for call in message.get("tool_calls", []) or []:
            function = call.get("function", {}) or {}
            call_id = str(call.get("id") or "")
            raw_args = function.get("arguments", "{}")
            raw_output = outputs_by_id.get(call_id, {}).get("content")
            calls.append(
                {
                    "index": index,
                    "tool_name": function.get("name"),
                    "arguments": _parse_json_maybe(raw_args),
                    "raw_arguments": _truncate(raw_args, 800),
                    "output": _parse_json_maybe(raw_output),
                    "raw_output": _truncate(raw_output, 1200),
                }
            )
    return calls


def _trace_summary(conversation: list[dict[str, Any]]) -> dict[str, Any]:
    calls = _extract_tool_calls(conversation)
    final_assistant = ""
    for message in reversed(conversation):
        if message.get("role") == "assistant" and message.get("content"):
            final_assistant = str(message.get("content"))
            break
    return {
        "turn_count": len(conversation),
        "tool_calls": [
            {
                "tool_name": call.get("tool_name"),
                "arguments": call.get("arguments"),
                "output_preview": _truncate(call.get("output"), 500),
            }
            for call in calls
        ],
        "tool_call_names": [str(call.get("tool_name")) for call in calls],
        "final_assistant_preview": _truncate(final_assistant, 500),
    }


def _control_trace_completeness(
    *,
    control_cache_source: str | None,
    control_conversation: list[dict[str, Any]],
) -> dict[str, Any]:
    """Describe whether control feedback has usable trace-level evidence."""
    source = (control_cache_source or "").strip().lower()
    has_trace = bool(control_conversation)
    if source == "cached" and not has_trace:
        return {
            "status": "score_complete_trace_incomplete",
            "reason": (
                "Task-level control baseline cache stores aggregate scores for "
                "cached tasks, but this synthetic control row has no historical "
                "conversation trajectory."
            ),
            "control_cache_source": "cached",
            "has_control_conversation": False,
        }
    if has_trace:
        return {
            "status": "trace_complete",
            "reason": "control_conversation_available",
            "control_cache_source": source or None,
            "has_control_conversation": True,
        }
    return {
        "status": "trace_unknown_or_missing",
        "reason": "control_conversation_missing",
        "control_cache_source": source or None,
        "has_control_conversation": False,
    }


def _helper_call_evidence(
    conversation: list[dict[str, Any]], helper_names: set[str]
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for call in _extract_tool_calls(conversation):
        tool_name = str(call.get("tool_name") or "")
        if tool_name not in helper_names:
            continue
        evidence.append(
            {
                "tool_name": tool_name,
                "arguments": call.get("arguments"),
                "output": call.get("output"),
                "raw_output": call.get("raw_output"),
            }
        )
    return evidence


def _abstain_reasons(helper_outputs: list[dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    for output in helper_outputs:
        parsed = output.get("output")
        if isinstance(parsed, dict):
            for key in ("abstain_reason", "reason", "error"):
                value = parsed.get(key)
                if value:
                    reasons.append(str(value))
            status = parsed.get("status")
            if isinstance(status, str) and "abstain" in status.lower():
                reasons.append(status)
        elif isinstance(parsed, str) and "abstain" in parsed.lower():
            reasons.append(_truncate(parsed, 240))
    return sorted(set(reasons))


def _expected_final_from_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    targets: list[Any] = []
    for check in row.get("outcome_checks", []) or []:
        if isinstance(check, dict) and check.get("targets"):
            targets.extend(check.get("targets") or [])
    return {
        "answer_targets": targets[:5],
        "outcome_check_count": row.get("outcome_check_count"),
        "included_outcome_checks": [
            {
                "kind": check.get("kind"),
                "score": check.get("score"),
                "targets": check.get("targets", [])[:3]
                if isinstance(check.get("targets"), list)
                else check.get("targets"),
            }
            for check in row.get("outcome_checks", []) or []
            if isinstance(check, dict) and check.get("included") is True
        ][:8],
    }


def _surface_domain(scenario: str, categories: list[str]) -> str:
    name = scenario.lower()
    if any(token in name for token in ("contact", "phone_number", "relationship")):
        return "contacts"
    if "message" in name or "sender" in name:
        return "messages"
    if "reminder" in name:
        return "reminders"
    if any(token in name for token in ("distance", "location", "lat_lon", "address")):
        return "location_distance"
    if any(token in name for token in ("temperature", "weather")):
        return "weather"
    if "stock" in name or "market" in name:
        return "stock_market"
    if any(token in name for token in ("currency", "exchange_rate")):
        return "currency"
    if any(token in name for token in ("holiday", "business_day", "calendar")):
        return "calendar"
    if any(token in name for token in ("wifi", "cellular", "low_battery", "service")):
        return "device_service"
    if any(category.upper() == "INSUFFICIENT_INFORMATION" for category in categories):
        return "insufficient_information"
    return "general"


def _likely_failure_mechanism(
    scenario: str,
    categories: list[str],
    outcome_delta: float | None,
    no_current_helper_fit: bool,
    selection_row: dict[str, Any],
) -> str:
    name = scenario.lower()
    if "insufficient_information" in name or "INSUFFICIENT_INFORMATION" in {
        c.upper() for c in categories
    }:
        return "safe_insufficient_information_abstention"
    if selection_row.get("selection_status") == "generated_tool_visible_not_called":
        return "helper_visible_not_called_adoption"
    if selection_row.get("generated_tools_failed"):
        return "helper_callability_or_runtime_failure"
    if any(token in name for token in ("contact", "phone_number", "relationship")):
        return "contact_lookup_or_answer_field_resolution"
    if "message" in name:
        return "message_search_selection_or_answer_resolution"
    if any(
        token in name for token in ("distance", "location", "temperature", "weather")
    ):
        return "external_service_answer_or_abstain_resolution"
    if any(token in name for token in ("modify", "remove", "send", "update")):
        return "side_effect_target_or_argument_preparation"
    if no_current_helper_fit:
        return "no_current_helper_fit_unclassified"
    if outcome_delta is not None and outcome_delta < 0:
        return "candidate_regression_with_existing_helper_fit"
    return "preserved_or_low_signal"


def _missing_deterministic_step(mechanism: str) -> str | None:
    mapping = {
        "safe_insufficient_information_abstention": "detect missing required information before calling minefield/base tools",
        "helper_visible_not_called_adoption": "decide to call the visible deterministic helper before manual reasoning",
        "helper_callability_or_runtime_failure": "bridge visible trace data into helper schema and produce usable output",
        "contact_lookup_or_answer_field_resolution": "plan the contact lookup and extract the requested scalar field from visible contact records",
        "message_search_selection_or_answer_resolution": "select or extract the relevant message/record field from search results",
        "external_service_answer_or_abstain_resolution": "format or abstain on external-service scalar answers without unsafe extra calls",
        "side_effect_target_or_argument_preparation": "select the safe action target and prepare downstream ToolSandbox arguments",
        "no_current_helper_fit_unclassified": "identify a repeated deterministic intermediate operation",
        "candidate_regression_with_existing_helper_fit": "prevent cross-lane interference from a visible helper",
    }
    return mapping.get(mechanism)


def _outcome_label(delta: float | None) -> str:
    if delta is None:
        return "unscored"
    if delta > 0:
        return "gain"
    if delta < 0:
        return "regression"
    return "preserved"


def _side_effect_risk(scenario: str, trace: dict[str, Any]) -> bool:
    names = [str(name or "") for name in trace.get("tool_call_names", [])]
    if any(name.startswith(SIDE_EFFECT_TOOL_PREFIXES) for name in names):
        return True
    return any(
        token in scenario.lower()
        for token in ("modify", "remove", "send", "update", "add_")
    )


def _feedback_sufficiency(
    *,
    user_request: str,
    expected_final: dict[str, Any] | None,
    helper_outputs: list[dict[str, Any]],
    categories: list[str],
    scenario: str,
    mechanism: str,
    side_effect_risk: bool,
) -> dict[str, Any]:
    lower = scenario.lower()
    has_negative = "insufficient_information" in lower or any(
        c.upper() == "INSUFFICIENT_INFORMATION" for c in categories
    )
    has_ambiguity = "ambiguous" in lower
    missing: list[str] = []
    if not user_request:
        missing.append("user_request_summary")
    if not expected_final or not (
        expected_final.get("answer_targets")
        or expected_final.get("included_outcome_checks")
    ):
        if not has_negative:
            missing.append("expected_final_answer_or_state")
    if mechanism == "helper_callability_or_runtime_failure" and not helper_outputs:
        missing.append("actual_helper_arguments_outputs")
    if side_effect_risk and not expected_final and not has_negative:
        missing.append("side_effect_final_state_or_guardrail")
    return {
        "sufficient_for_tool_birth": len(missing) == 0,
        "missing_fields": missing,
        "identifies_missing_capability": mechanism != "preserved_or_low_signal",
        "identifies_required_inputs": bool(user_request),
        "identifies_required_outputs": bool(expected_final),
        "identifies_negative_or_abstain_case": has_negative,
        "identifies_ambiguity_case": has_ambiguity,
        "identifies_side_effect_risk": side_effect_risk,
    }


def build_feedback_packets(
    run_root: Path, *, run_id: str | None = None
) -> list[dict[str, Any]]:
    """Build one feedback packet per scenario from a paired protocol run."""
    run_root = run_root.resolve()
    run_id = run_id or run_root.name
    control_dir, candidate_dir = resolve_arm_dirs(run_root)
    if control_dir is None or candidate_dir is None:
        raise ValueError(f"could_not_resolve_control_candidate_dirs:{run_root}")

    paired = _read_json(run_root / "paired_comparison.json")
    control_rows = _rows_by_name(control_dir)
    candidate_rows = _rows_by_name(candidate_dir)
    deltas = {str(row.get("scenario")): row for row in paired.get("deltas", [])}
    selection_by_scenario = _jsonl_by_scenario(
        candidate_dir / "scenario_tool_selection.jsonl"
    )
    visibility_by_scenario = _jsonl_by_scenario(
        candidate_dir / "scenario_tool_visibility.jsonl"
    )
    side_effect_rows = _jsonl_by_scenario(
        candidate_dir / "side_effect_preservation_report.jsonl"
    )
    task_focus = _read_json(run_root / "dashboard" / "task_focus_data.json")
    task_focus_pairs = {
        str(row.get("scenario")): row for row in task_focus.get("pairs", []) or []
    }

    scenario_names = [str(row.get("scenario")) for row in paired.get("deltas", [])]
    scenario_names = [name for name in scenario_names if name and name != "None"]
    if not scenario_names:
        scenario_names = list(candidate_rows) or list(control_rows) or list(deltas)
    packets: list[dict[str, Any]] = []
    for scenario in scenario_names:
        control_row = control_rows.get(scenario, {})
        candidate_row = candidate_rows.get(scenario, {})
        delta_row = deltas.get(scenario, {})
        categories = list(
            candidate_row.get("categories") or control_row.get("categories") or []
        )
        selection_row = selection_by_scenario.get(scenario, {})
        visibility_row = visibility_by_scenario.get(scenario, {})
        routing_decisions = visibility_row.get("routing_decisions", {}) or {}
        visible_tools = list(
            selection_row.get("generated_tools_visible")
            or visibility_row.get("generated_tools")
            or []
        )
        called_tools = list(selection_row.get("generated_tools_called") or [])
        vnc_tools = list(selection_row.get("generated_tools_not_called") or [])
        failed_tools = list(selection_row.get("generated_tools_failed") or [])
        helper_names = set(visible_tools) | set(called_tools) | set(failed_tools)
        task_focus_pair = task_focus_pairs.get(scenario, {})
        control_cache_source = (task_focus_pair.get("control") or {}).get(
            "control_cache_source"
        ) or control_row.get("control_cache_source")
        control_conversation = _conversation(control_dir, scenario)
        candidate_conversation = _conversation(candidate_dir, scenario)
        control_trace = _trace_summary(control_conversation)
        control_trace_completeness = _control_trace_completeness(
            control_cache_source=control_cache_source,
            control_conversation=control_conversation,
        )
        sage_trace = _trace_summary(candidate_conversation)
        helper_outputs = _helper_call_evidence(candidate_conversation, helper_names)
        expected_fit = expected_helper_fit(scenario, categories)
        loaded_helpers = set(visibility_row.get("retained_tools_loaded") or [])
        no_current_helper_fit = (
            not (set(expected_fit) & loaded_helpers)
            if loaded_helpers
            else not expected_fit
        )
        outcome_delta = delta_row.get("outcome_delta")
        if outcome_delta is not None:
            outcome_delta = float(outcome_delta)
        mechanism = _likely_failure_mechanism(
            scenario,
            categories,
            outcome_delta,
            no_current_helper_fit,
            selection_row,
        )
        user_request = _user_request_summary(
            candidate_conversation or control_conversation, scenario
        )
        expected_final = _expected_final_from_row(candidate_row or control_row)
        side_effect_risky = _side_effect_risk(scenario, sage_trace)
        feedback_sufficiency = _feedback_sufficiency(
            user_request=user_request,
            expected_final=expected_final,
            helper_outputs=helper_outputs,
            categories=categories,
            scenario=scenario,
            mechanism=mechanism,
            side_effect_risk=side_effect_risky,
        )
        packet = {
            "schema_version": "v2_6_task_feedback_packet_v1",
            "run_id": run_id,
            "run_root": str(run_root),
            "control_dir": str(control_dir),
            "sage_dir": str(candidate_dir),
            "scenario": scenario,
            "scenario_id": scenario,
            "base_task_family": base_task_family(scenario),
            "task_strata": classify_task_strata(scenario, categories),
            "surface_domain": _surface_domain(scenario, categories),
            "categories": categories,
            "user_request_summary": user_request,
            "expected_final_answer_or_state": expected_final,
            "control_trace_summary": control_trace,
            "control_trace_completeness": control_trace_completeness,
            "sage_trace_summary": sage_trace,
            "scores": {
                "control_outcome_similarity": delta_row.get(
                    "control_outcome_similarity"
                ),
                "sage_outcome_similarity": delta_row.get(
                    "candidate_outcome_similarity"
                ),
                "outcome_delta": delta_row.get("outcome_delta"),
                "control_canonical_similarity": delta_row.get("control_similarity"),
                "sage_canonical_similarity": delta_row.get("candidate_similarity"),
                "canonical_delta": delta_row.get("delta"),
                "sage_exact_success": float(candidate_row.get("similarity", 0.0) or 0.0)
                >= 1.0,
                "control_exact_success": float(
                    control_row.get("similarity", 0.0) or 0.0
                )
                >= 1.0,
                "gain_regression_preserved": _outcome_label(outcome_delta),
            },
            "expected_helper_fit": expected_fit,
            "expected_birth_opportunities": expected_birth_opportunities(
                scenario, categories
            ),
            "no_current_helper_fit": no_current_helper_fit,
            "helper_visible_tools": visible_tools,
            "helper_called_tools": called_tools,
            "visible_not_called_tools": vnc_tools,
            "failed_helper_attempts": failed_tools,
            "actual_helper_calls": helper_outputs,
            "abstain_reasons": _abstain_reasons(helper_outputs),
            "routing_show_hide_reasons": routing_decisions,
            "side_effect_incidents": side_effect_rows.get(scenario, {}).get(
                "side_effect_preservation_failures", []
            ),
            "runtime_exceptions": {
                "control_exception_type": control_row.get("exception_type"),
                "sage_exception_type": candidate_row.get("exception_type"),
            },
            "final_state_mismatch": {
                "outcome_checks": candidate_row.get("outcome_checks", []),
                "minefield_mapping": candidate_row.get("minefield_mapping", {}),
            },
            "missing_deterministic_intermediate_step": _missing_deterministic_step(
                mechanism
            ),
            "likely_failure_mechanism": mechanism,
            "feedback_sufficiency": feedback_sufficiency,
            "task_focus_pair": {
                "control_cache_source": control_cache_source,
                "display_index": task_focus_pair.get("display_index"),
            },
        }
        packets.append(packet)
    return packets


def write_feedback_packets(
    run_root: Path,
    output_root: Path,
    *,
    run_id: str | None = None,
) -> Path:
    """Write task_feedback.jsonl for one protocol run and return the path."""
    packets = build_feedback_packets(run_root, run_id=run_id)
    resolved_run_id = run_id or run_root.resolve().name
    output_dir = output_root / resolved_run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "task_feedback.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for packet in packets:
            handle.write(json.dumps(packet, sort_keys=True) + "\n")
    summary = summarize_feedback_packets(packets)
    (output_dir / "feedback_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    return path


def summarize_feedback_packets(packets: list[dict[str, Any]]) -> dict[str, Any]:
    mechanisms = Counter(
        str(packet.get("likely_failure_mechanism")) for packet in packets
    )
    domains = Counter(str(packet.get("surface_domain")) for packet in packets)
    strata = Counter(
        str(stratum) for packet in packets for stratum in packet.get("task_strata", [])
    )
    no_fit = [packet for packet in packets if packet.get("no_current_helper_fit")]
    insufficient = [
        packet
        for packet in packets
        if not packet.get("feedback_sufficiency", {}).get("sufficient_for_tool_birth")
    ]
    called = [packet for packet in packets if packet.get("helper_called_tools")]
    visible_not_called = [
        packet for packet in packets if packet.get("visible_not_called_tools")
    ]
    trace_incomplete = [
        packet
        for packet in packets
        if packet.get("control_trace_completeness", {}).get("status")
        == "score_complete_trace_incomplete"
    ]
    return {
        "packet_count": len(packets),
        "no_current_helper_fit_count": len(no_fit),
        "no_current_helper_fit_share": len(no_fit) / len(packets) if packets else None,
        "score_complete_trace_incomplete_control_count": len(trace_incomplete),
        "score_complete_trace_incomplete_control_share": (
            len(trace_incomplete) / len(packets) if packets else None
        ),
        "helper_called_packet_count": len(called),
        "visible_not_called_packet_count": len(visible_not_called),
        "feedback_insufficient_count": len(insufficient),
        "feedback_insufficient_share": len(insufficient) / len(packets)
        if packets
        else None,
        "mechanism_counts": dict(mechanisms.most_common()),
        "surface_domain_counts": dict(domains.most_common()),
        "task_strata_counts": dict(strata.most_common()),
        "top_no_fit_mechanisms": dict(
            Counter(
                str(packet.get("likely_failure_mechanism")) for packet in no_fit
            ).most_common()
        ),
    }


def load_feedback_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
