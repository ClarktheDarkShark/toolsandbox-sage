#!/usr/bin/env python3
"""Verify a strict development-only lifecycle-repair cohort.

This verifier deliberately does not confer publication eligibility. It checks
fresh paired execution, lifecycle integrity, and predeclared outcome guards for
the exposed dev10/dev30 cohorts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from sage_ts.dashboard.server import DASHBOARD_SERVER_PROTOCOL
from sage_ts.evaluation.outcome_score import outcome_evaluator_manifest

try:
    from scripts import verify_publication_run as _strict_run_verifier
except ModuleNotFoundError:  # pragma: no cover - direct execution from scripts/
    import verify_publication_run as _strict_run_verifier

LIFECYCLE_USE_CASE_TOOL = "prepare_safe_action_or_abstain"
LIFECYCLE_FAULT_FIXTURE_SHA256 = (
    "285604ee15dcb3b066816267ef1730bb40dffab7a9880160ddd885b2894a5630"
)
DEV10_ORDER = (
    "remove_contact_by_phone_no_search_contacts_insufficient_information",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_3_distraction_tools",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_3_distraction_tools_arg_description_scrambled",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_3_distraction_tools_tool_description_scrambled",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_3_distraction_tools_arg_type_scrambled",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_3_distraction_tools_tool_name_scrambled",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_all_tools",
    "add_reminder_content_and_week_delta_and_time",
    "add_reminder_content_and_weekday_delta_and_time",
    "search_phone_number_with_name",
)
DEV30_ORDER = (
    "remove_contact_by_phone_no_search_contacts_insufficient_information_10_distraction_tools",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_alt",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_alt_10_distraction_tools",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_alt_3_distraction_tools",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_alt_3_distraction_tools_arg_description_scrambled",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_alt_3_distraction_tools_arg_type_scrambled",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_alt_3_distraction_tools_tool_description_scrambled",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_alt_3_distraction_tools_tool_name_scrambled",
    "remove_contact_by_phone_no_search_contacts_insufficient_information_alt_all_tools",
    "find_days_till_holiday_insufficient_information_10_distraction_tools",
    "find_days_till_holiday_insufficient_information_3_distraction_tools_tool_name_scrambled",
    "find_days_till_holiday_insufficient_information",
    "find_days_till_holiday_insufficient_information_3_distraction_tools",
    "remove_contact_by_phone_no_remove_contact_insufficient_information_10_distraction_tools",
    "remove_contact_by_phone_no_remove_contact_insufficient_information",
    "remove_contact_by_phone_no_remove_contact_insufficient_information_3_distraction_tools",
    "remove_contact_by_phone_no_remove_contact_insufficient_information_3_distraction_tools_arg_description_scrambled",
    "remove_contact_by_phone_no_remove_contact_insufficient_information_3_distraction_tools_arg_type_scrambled",
    "remove_contact_by_phone_no_remove_contact_insufficient_information_3_distraction_tools_tool_description_scrambled",
    "remove_contact_by_phone_no_remove_contact_insufficient_information_3_distraction_tools_tool_name_scrambled",
    "remove_contact_by_phone_no_remove_contact_insufficient_information_all_tools",
    "modify_contact_with_message_recency_insufficient_information_10_distraction_tools",
    "modify_contact_with_message_recency_insufficient_information_3_distraction_tools_tool_description_scrambled",
    "search_reminder_with_creation_recency_yesterday_insufficient_information_10_distraction_tools",
    "search_reminder_with_creation_recency_yesterday_insufficient_information_3_distraction_tools_arg_description_scrambled",
    "search_reminder_with_creation_recency_yesterday_insufficient_information_implicit",
    "add_reminder_content_and_week_delta_and_time_3_distraction_tools_arg_description_scrambled",
    "add_reminder_content_and_weekday_delta_and_time_alt_3_distraction_tools",
    "search_phone_number_with_name_10_distraction_tools",
    "search_phone_number_with_name_3_distraction_tools_tool_description_scrambled",
)


def _order_sha256(names: tuple[str, ...] | list[str]) -> str:
    return hashlib.sha256(("\n".join(names) + "\n").encode("utf-8")).hexdigest()


COHORT_SPECS: dict[str, dict[str, Any]] = {
    "development_diagnostic_lifecycle_repair_dev10": {
        "order": DEV10_ORDER,
        "order_sha256": "b59acee1559e254551ffe783acdaf351b45c4b6977b4a4bb990229afe733cf0e",
        "roles": {
            "repair_target": DEV10_ORDER[:7],
            "preservation": DEV10_ORDER[7:],
        },
        "safe_role": "repair_target",
        "contact_role": "repair_target",
        "safe_visible_called_minimum": 7,
        "safe_exact_minimum": 6,
        "contact_exact_no_remove_minimum": 6,
        "preservation_exact_hidden_minimum": 3,
        "overall_exact_minimum": 9,
        "future_v2_exact_minimum": 6,
        "future_v2_success_flip_minimum": 1,
        "predeclared_gates": {
            "safe_abstain_visible_and_called": {
                "role": "repair_target",
                "minimum": 7,
                "total": 7,
            },
            "safe_abstain_exact_without_forbidden_remove": {
                "role": "repair_target",
                "minimum": 6,
                "total": 7,
            },
            "preservation_exact_and_safe_helper_hidden": {
                "role": "preservation",
                "minimum": 3,
                "total": 3,
            },
            "overall_exact_outcomes": {"minimum": 9, "total": 10},
            "before_after": {
                "trigger_version": 1,
                "trigger_outcome_less_than": 1.0,
                "future_version": 2,
                "minimum_future_exact_successes": 6,
                "minimum_future_success_flips": 1,
            },
        },
    },
    "development_diagnostic_lifecycle_repair_dev30": {
        "order": DEV30_ORDER,
        "order_sha256": "4ab88c1b5c110b0681eb64763f8ca7870fba8b23271a980edf02d40a8424c39f",
        "roles": {
            "safe_abstain_confirmation": DEV30_ORDER[:26],
            "cross_family_safe_abstain": DEV30_ORDER[9:13],
            "contact_repair_confirmation": DEV30_ORDER[:9],
            "preservation": DEV30_ORDER[26:],
        },
        "safe_role": "safe_abstain_confirmation",
        "contact_role": "contact_repair_confirmation",
        "cross_family_role": "cross_family_safe_abstain",
        "safe_visible_called_minimum": 26,
        "safe_exact_minimum": 21,
        "contact_exact_no_remove_minimum": 8,
        "preservation_exact_hidden_minimum": 4,
        "overall_exact_minimum": 25,
        "future_v2_exact_minimum": 21,
        "future_v2_success_flip_minimum": 1,
        "predeclared_gates": {
            "safe_abstain_visible_and_called": {
                "role": "safe_abstain_confirmation",
                "minimum": 26,
                "total": 26,
            },
            "contact_exact_without_forbidden_remove": {
                "role": "contact_repair_confirmation",
                "minimum": 8,
                "total": 9,
            },
            "insufficiency_exact": {
                "role": "safe_abstain_confirmation",
                "minimum": 21,
                "total": 26,
            },
            "preservation_exact_and_safe_helper_hidden": {
                "role": "preservation",
                "minimum": 4,
                "total": 4,
            },
            "overall_exact_outcomes": {"minimum": 25, "total": 30},
            "before_after": {
                "trigger_version": 1,
                "trigger_outcome_less_than": 1.0,
                "future_version": 2,
                "minimum_future_exact_successes": 21,
                "minimum_future_success_flips": 1,
            },
        },
    },
}


def _latest_run_root(search_root: Path) -> Path:
    manifests = sorted(
        search_root.rglob("protocol_manifest.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not manifests:
        raise ValueError(f"No protocol_manifest.json found under {search_root}")
    return manifests[-1].parent


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _result_rows(run_dir: Path) -> list[dict[str, Any]]:
    for filename in ("result_summary.json", "live_result_summary.json"):
        path = run_dir / filename
        if not path.exists():
            continue
        payload = _load_json(path)
        if isinstance(payload, list):
            return [dict(row) for row in payload if isinstance(row, dict)]
        rows = payload.get("per_scenario_results")
        if isinstance(rows, list):
            return [dict(row) for row in rows if isinstance(row, dict)]
    raise ValueError(f"No result rows found in {run_dir}")


def _outcome(row: dict[str, Any]) -> float | None:
    value = row.get("outcome_similarity")
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0.0 <= float(value) <= 1.0
    ):
        return float(value)
    return None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _manifest_task_names(manifest: dict[str, Any]) -> tuple[str, ...]:
    splits = manifest.get("splits")
    rows = splits.get("full_benchmark") if isinstance(splits, dict) else None
    if not isinstance(rows, list):
        return ()
    names: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("name"), str):
            return ()
        name = str(row["name"])
        if not name:
            return ()
        names.append(name)
    return tuple(names)


def _role_names(manifest: dict[str, Any], role: str) -> tuple[str, ...]:
    roles = manifest.get("validation_roles")
    values = roles.get(role) if isinstance(roles, dict) else None
    if not isinstance(values, list) or any(
        not isinstance(item, str) or not item for item in values
    ):
        return ()
    return tuple(values)


def _selection_has_tool(row: dict[str, Any], field: str, tool_name: str) -> bool:
    values = row.get(field)
    return isinstance(values, list) and tool_name in values


def _exact_outcome(row: dict[str, Any]) -> bool:
    return _outcome(row) == 1.0


def _exact_targeted_abstention(row: dict[str, Any]) -> bool:
    if not _exact_outcome(row):
        return False
    checks = row.get("outcome_checks")
    if not isinstance(checks, list):
        return False
    return any(
        isinstance(check, dict)
        and check.get("kind") == "insufficient_information_contract"
        and check.get("included") is True
        and check.get("score") == 1.0
        and check.get("outcome_basis") == "targeted_abstention_or_clarification"
        for check in checks
    )


def _forbidden_remove_contact(row: dict[str, Any]) -> bool:
    checks = row.get("outcome_checks")
    diagnostics: list[dict[str, Any]] = []
    if isinstance(checks, list):
        for check in checks:
            if not isinstance(check, dict):
                continue
            raw = check.get("forbidden_action_diagnostics")
            if isinstance(raw, list):
                diagnostics.extend(item for item in raw if isinstance(item, dict))
    if any(item.get("tool_name") == "remove_contact" for item in diagnostics):
        return True
    return bool(row.get("outcome_forbidden_action_detected")) and not diagnostics


def _rows_by_scenario(
    rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], tuple[str, ...]]:
    order = tuple(str(row.get("scenario") or "") for row in rows)
    return {str(row.get("scenario") or ""): row for row in rows}, order


def _verify_execution_artifacts(
    run_root: Path,
    protocol: dict[str, Any],
    *,
    expected_tasks: int,
    expected_evaluator: dict[str, Any],
) -> tuple[Path, Path, dict[str, Any]]:
    """Apply the publication verifier's execution-integrity schema to dev runs."""

    parallel_execution = _strict_run_verifier._verify_parallel_arm_execution(
        run_root, protocol
    )
    control_dir = _strict_run_verifier._resolve_declared_path(
        run_root,
        protocol.get("control_dir"),
        "control_dir",
        required_parent=run_root / "control",
    )
    candidate_dir = _strict_run_verifier._resolve_declared_path(
        run_root,
        protocol.get("candidate_dir"),
        "candidate_dir",
        required_parent=run_root / "candidate",
    )

    receipt_path = _strict_run_verifier._resolve_declared_path(
        run_root,
        protocol.get("dashboard_open_receipt_path"),
        "dashboard_open_receipt_path",
        required_parent=run_root,
    )
    receipt = _load_json(receipt_path)
    expected_dashboard = (run_root / "dashboard" / "task_compare.html").resolve()
    opened_monotonic_ns = receipt.get("opened_monotonic_ns")
    first_process_start = min(
        int(parallel_execution["arms"][arm]["started_monotonic_ns"])
        for arm in ("control", "candidate")
    )
    if (
        receipt.get("dashboard") != "task_compare"
        or receipt.get("comparison") != "fresh_control_vs_policy_sage"
        or Path(str(receipt.get("path") or "")).resolve() != expected_dashboard
        or not expected_dashboard.is_file()
        or receipt.get("url") != protocol.get("dashboard_task_compare_url")
        or receipt.get("external_browser_opened") is not True
        or receipt.get("http_verified_before_open") is not True
        or receipt.get("dashboard_server_protocol") != DASHBOARD_SERVER_PROTOCOL
        or Path(str(receipt.get("dashboard_server_root") or "")).resolve()
        != run_root.resolve()
        or receipt.get("opened_before_model_processes") is not True
        or isinstance(opened_monotonic_ns, bool)
        or not isinstance(opened_monotonic_ns, int)
        or opened_monotonic_ns <= 0
        or opened_monotonic_ns >= first_process_start
    ):
        raise ValueError(
            "Development dashboard receipt does not prove that the exact run "
            "dashboard opened externally before either model process."
        )

    control_rows, _control_order, control_totals = _strict_run_verifier._uncached_rows(
        control_dir,
        expected_tasks=expected_tasks,
        arm="control",
        expected_outcome_evaluator=expected_evaluator,
    )
    candidate_rows, _candidate_order, candidate_totals = (
        _strict_run_verifier._uncached_rows(
            candidate_dir,
            expected_tasks=expected_tasks,
            arm="candidate",
            expected_outcome_evaluator=expected_evaluator,
        )
    )
    _strict_run_verifier._verify_llm_usage_artifacts(
        control_dir,
        rows=control_rows,
        row_totals=control_totals,
        arm="control",
        expected_event_arm="online_build_full_control",
        allow_generation_source=False,
    )
    _strict_run_verifier._verify_llm_usage_artifacts(
        candidate_dir,
        rows=candidate_rows,
        row_totals=candidate_totals,
        arm="candidate",
        expected_event_arm="online_build_full_candidate",
        allow_generation_source=True,
    )
    return control_dir, candidate_dir, parallel_execution


def _lifecycle_integrity(
    candidate_dir: Path,
    registry_dir: Path,
) -> dict[str, Any]:
    requests = _read_jsonl(candidate_dir / "self_evolution_tool_repair_requests.jsonl")
    acknowledgements = _read_jsonl(
        candidate_dir / "self_evolution_tool_repair_acknowledgements.jsonl"
    )
    state_path = candidate_dir / "post_deployment_repair_state.json"
    state = _load_json(state_path) if state_path.is_file() else None
    pending = state.get("pending_repair_requests") if isinstance(state, dict) else None
    canaries = state.get("canary_state_by_tool") if isinstance(state, dict) else None
    transactions = (
        state.get("repair_transactions_by_tool") if isinstance(state, dict) else None
    )
    handled = (
        state.get("handled_repair_request_ids") if isinstance(state, dict) else None
    )

    final_ack_by_request: dict[str, dict[str, Any]] = {}
    for row in acknowledgements:
        request_id = str(row.get("request_id") or "")
        if request_id:
            final_ack_by_request[request_id] = row
    request_ids = {
        str(row.get("request_id") or "")
        for row in requests
        if str(row.get("request_id") or "")
    }
    request_by_id = {
        str(row.get("request_id") or ""): row
        for row in requests
        if str(row.get("request_id") or "")
    }
    duplicate_request_ids = sorted(
        request_id
        for request_id in request_ids
        if sum(str(row.get("request_id") or "") == request_id for row in requests) != 1
    )
    unacknowledged = sorted(request_ids - set(final_ack_by_request))
    orphaned_acknowledgements = sorted(set(final_ack_by_request) - request_ids)
    terminal_statuses = {"promoted", "rejected", "rolled_back"}
    nonterminal = sorted(
        request_id
        for request_id in final_ack_by_request
        if str(final_ack_by_request[request_id].get("status") or "")
        not in terminal_statuses
    )
    mismatched_acknowledgement_tools = sorted(
        request_id
        for request_id in request_ids & set(final_ack_by_request)
        if str(final_ack_by_request[request_id].get("tool_name") or "")
        != str(request_by_id[request_id].get("tool_name") or "")
    )

    handled_state_valid = bool(
        isinstance(handled, list)
        and all(isinstance(item, str) and item for item in handled)
        and len(handled) == len(set(handled))
    )
    handled_ids = set(handled) if handled_state_valid else set()
    unhandled = sorted(request_ids - handled_ids)
    orphaned_handled = sorted(handled_ids - request_ids)

    registry = _load_json(registry_dir / "registry_manifest.json")
    registry_tools = registry.get("tools") if isinstance(registry, dict) else None
    active_unresolved: list[str] = []
    active_repairs_without_promotion: list[str] = []
    promoted_versions = {
        (
            str(acknowledgement.get("tool_name") or ""),
            acknowledgement.get("new_version"),
        )
        for acknowledgement in final_ack_by_request.values()
        if acknowledgement.get("status") == "promoted"
        and str(acknowledgement.get("tool_name") or "")
        and isinstance(acknowledgement.get("new_version"), int)
        and not isinstance(acknowledgement.get("new_version"), bool)
    }
    if isinstance(registry_tools, dict):
        for request_id in sorted(final_ack_by_request):
            acknowledgement = final_ack_by_request[request_id]
            if acknowledgement.get("status") == "promoted":
                continue
            tool_name = str(acknowledgement.get("tool_name") or "")
            version = acknowledgement.get("new_version")
            entry = registry_tools.get(tool_name)
            if (
                isinstance(entry, dict)
                and entry.get("version") == version
                and entry.get("retired") is not True
            ):
                active_unresolved.append(f"{tool_name}:v{version}:{request_id}")
        active_repairs_without_promotion = sorted(
            f"{tool_name}:v{entry.get('version')}"
            for tool_name, entry in registry_tools.items()
            if isinstance(tool_name, str)
            and isinstance(entry, dict)
            and entry.get("retired") is not True
            and str(entry.get("birth_scenario") or "").startswith(
                "post_deployment_repair:"
            )
            and (tool_name, entry.get("version")) not in promoted_versions
        )
    return {
        "repair_requests": requests,
        "acknowledgements": acknowledgements,
        "state_present": isinstance(state, dict),
        "state_schema_valid": (
            isinstance(state, dict) and state.get("schema_version") == 1
        ),
        "pending_repair_request_count": len(pending)
        if isinstance(pending, list)
        else None,
        "open_canary_count": len(canaries) if isinstance(canaries, dict) else None,
        "open_repair_transaction_count": (
            len(transactions) if isinstance(transactions, dict) else None
        ),
        "handled_state_valid": handled_state_valid,
        "unacknowledged_repair_request_ids": unacknowledged,
        "duplicate_repair_request_ids": duplicate_request_ids,
        "orphaned_repair_acknowledgement_ids": orphaned_acknowledgements,
        "mismatched_repair_acknowledgement_tool_ids": (
            mismatched_acknowledgement_tools
        ),
        "nonterminal_repair_request_ids": nonterminal,
        "unhandled_repair_request_ids": unhandled,
        "orphaned_handled_repair_request_ids": orphaned_handled,
        "active_unresolved_tools": active_unresolved,
        "active_repairs_without_promotion": active_repairs_without_promotion,
    }


def verify(search_root: Path, expected_tasks: int) -> dict[str, Any]:
    run_root = _latest_run_root(search_root)
    protocol = _load_json(run_root / "protocol_manifest.json")
    comparison = _load_json(run_root / "paired_comparison.json")
    cache_report = _load_json(run_root / "control_cache_report.json")
    reasons: list[str] = []

    benchmark_manifest_path = _strict_run_verifier._resolve_declared_path(
        run_root,
        protocol.get("benchmark_manifest_path"),
        "benchmark_manifest_path",
    )
    if not benchmark_manifest_path.is_file():
        raise ValueError(
            f"Recorded benchmark manifest is missing: {benchmark_manifest_path}"
        )
    benchmark_manifest = _load_json(benchmark_manifest_path)
    manifest_type = str(benchmark_manifest.get("manifest_type") or "")
    spec = COHORT_SPECS.get(manifest_type)
    if spec is None:
        raise ValueError(f"Unknown lifecycle development cohort: {manifest_type!r}")
    expected_order = tuple(spec["order"])
    if expected_tasks != len(expected_order):
        reasons.append("verifier_expected_task_count_mismatch")

    benchmark_sha256 = hashlib.sha256(benchmark_manifest_path.read_bytes()).hexdigest()
    if protocol.get("benchmark_manifest_sha256") != benchmark_sha256:
        reasons.append("benchmark_manifest_bytes_do_not_match_protocol")
    if protocol.get("manifest_type") != manifest_type:
        reasons.append("protocol_manifest_type_mismatch")
    manifest_order = _manifest_task_names(benchmark_manifest)
    if manifest_order != expected_order:
        reasons.append("benchmark_scenario_order_mismatch")
    if len(set(manifest_order)) != len(manifest_order):
        reasons.append("benchmark_contains_duplicate_tasks")
    expected_order_sha256 = str(spec["order_sha256"])
    if _order_sha256(expected_order) != expected_order_sha256:
        raise AssertionError("Internal lifecycle cohort order pin is invalid.")
    if benchmark_manifest.get("scenario_order_sha256") != expected_order_sha256:
        reasons.append("benchmark_scenario_order_pin_mismatch")
    if protocol.get("scenario_order_sha256") != expected_order_sha256:
        reasons.append("protocol_scenario_order_pin_mismatch")
    if (
        benchmark_manifest.get("lifecycle_evidence_mode")
        != "seeded_historical_v1_postdeployment_repair"
    ):
        reasons.append("lifecycle_evidence_mode_mismatch")
    if benchmark_manifest.get("predeclared_gates") != spec["predeclared_gates"]:
        reasons.append("predeclared_gate_contract_mismatch")
    observed_roles = benchmark_manifest.get("validation_roles")
    expected_roles = spec["roles"]
    if not isinstance(observed_roles, dict) or set(observed_roles) != set(
        expected_roles
    ):
        reasons.append("development_validation_role_set_mismatch")
    for role, expected_names in expected_roles.items():
        if _role_names(benchmark_manifest, role) != tuple(expected_names):
            reasons.append(f"{role}_role_membership_mismatch")

    if protocol.get("publication_gate_purpose") != "development-diagnostic":
        reasons.append("not_labeled_development_diagnostic")
    if protocol.get("scenario_count") != expected_tasks:
        reasons.append("protocol_task_count_mismatch")
    if protocol.get("fresh_control_required") is not True:
        reasons.append("fresh_control_not_required")
    if protocol.get("parallel_arms") is not True:
        reasons.append("arms_not_parallel")
    if comparison.get("runtime_exception_count") != 0:
        reasons.append("runtime_exceptions_present")
    if comparison.get("candidate_stopped_early") is not False:
        reasons.append("candidate_stopped_early")

    required_cache_protocol = {
        "control_cache_mode": "off",
        "control_source": "fresh",
        "cached_control_tasks": 0,
        "fresh_control_tasks": expected_tasks,
        "openai_response_cache_enabled": False,
        "openai_response_cache_mode": "off",
        "sage_task_cache_enabled": False,
        "cross_run_failure_memory_enabled": False,
    }
    if any(
        protocol.get(field) != expected
        for field, expected in required_cache_protocol.items()
    ):
        reasons.append("protocol_no_cache_provenance_mismatch")

    required_cache_report = {
        "mode": "off",
        "control_source": "fresh",
        "cached_control_tasks": 0,
        "fresh_control_tasks": expected_tasks,
        "cache_accessed": False,
        "fresh_control_enforced": True,
    }
    if any(
        cache_report.get(field) != expected
        for field, expected in required_cache_report.items()
    ):
        reasons.append("control_cache_report_not_fully_fresh")

    cache = comparison.get("control_cache")
    if not isinstance(cache, dict) or any(
        (
            cache.get("mode") != "off",
            cache.get("cache_accessed") is not False,
            cache.get("cached_control_tasks") != 0,
            cache.get("fresh_control_tasks") != expected_tasks,
        )
    ):
        reasons.append("control_was_not_fully_fresh")

    expected_evaluator = outcome_evaluator_manifest()
    control_dir, candidate_dir, parallel_execution = _verify_execution_artifacts(
        run_root,
        protocol,
        expected_tasks=expected_tasks,
        expected_evaluator=expected_evaluator,
    )
    control_rows = _result_rows(control_dir)
    candidate_rows = _result_rows(candidate_dir)
    if len(control_rows) != expected_tasks or len(candidate_rows) != expected_tasks:
        reasons.append("arm_task_count_mismatch")
    control_order = tuple(str(row.get("name") or "") for row in control_rows)
    candidate_order = tuple(str(row.get("name") or "") for row in candidate_rows)
    if control_order != expected_order:
        reasons.append("control_result_task_order_mismatch")
    if candidate_order != expected_order:
        reasons.append("candidate_result_task_order_mismatch")
    control_by_name = {str(row.get("name") or ""): row for row in control_rows}
    candidate_by_name = {str(row.get("name") or ""): row for row in candidate_rows}
    if len(control_by_name) != len(control_rows):
        reasons.append("control_result_contains_duplicate_tasks")
    if len(candidate_by_name) != len(candidate_rows):
        reasons.append("candidate_result_contains_duplicate_tasks")
    if set(control_by_name) != set(candidate_by_name):
        reasons.append("paired_task_names_mismatch")

    if protocol.get("reporting_outcome_evaluator") != expected_evaluator:
        reasons.append("protocol_outcome_evaluator_identity_mismatch")
    evaluator_fields = {
        "outcome_evaluator_version": "version",
        "outcome_evaluator_contract_sha256": "contract_sha256",
        "outcome_evaluator_source_sha256": "source_sha256",
    }
    for arm, rows in (("control", control_rows), ("candidate", candidate_rows)):
        if sum(_outcome(row) is not None for row in rows) != expected_tasks:
            reasons.append(f"{arm}_audited_outcome_count_mismatch")
        if any(
            any(
                row.get(result_field) != expected_evaluator.get(manifest_field)
                for result_field, manifest_field in evaluator_fields.items()
            )
            for row in rows
        ):
            reasons.append(f"{arm}_outcome_evaluator_identity_mismatch")

    candidate_outcomes = [
        value for row in candidate_rows if (value := _outcome(row)) is not None
    ]
    control_outcomes = [
        value for row in control_rows if (value := _outcome(row)) is not None
    ]
    candidate_mean = _mean(candidate_outcomes)
    control_mean = _mean(control_outcomes)
    overall_exact_successes = sum(_exact_outcome(row) for row in candidate_rows)
    if overall_exact_successes < int(spec["overall_exact_minimum"]):
        reasons.append("overall_exact_outcome_gate_failed")

    selection_rows = _read_jsonl(candidate_dir / "scenario_tool_selection.jsonl")
    selection_by_name, selection_order = _rows_by_scenario(selection_rows)
    if selection_order != expected_order or len(selection_by_name) != len(
        selection_rows
    ):
        reasons.append("scenario_tool_selection_order_or_coverage_mismatch")
    feedback_rows = _read_jsonl(candidate_dir / "self_evolution_task_feedback.jsonl")
    feedback_by_name, feedback_order = _rows_by_scenario(feedback_rows)
    if feedback_order != expected_order or len(feedback_by_name) != len(feedback_rows):
        reasons.append("lifecycle_feedback_order_or_coverage_mismatch")

    safe_names = tuple(expected_roles[str(spec["safe_role"])])
    contact_names = tuple(expected_roles[str(spec["contact_role"])])
    preservation_names = tuple(expected_roles["preservation"])
    safe_visible_called_names = [
        name
        for name in safe_names
        if name in selection_by_name
        and name in feedback_by_name
        and _selection_has_tool(
            selection_by_name[name], "generated_tools_visible", LIFECYCLE_USE_CASE_TOOL
        )
        and _selection_has_tool(
            selection_by_name[name], "generated_tools_called", LIFECYCLE_USE_CASE_TOOL
        )
        and _selection_has_tool(
            feedback_by_name[name], "generated_tools_visible", LIFECYCLE_USE_CASE_TOOL
        )
        and _selection_has_tool(
            feedback_by_name[name], "generated_tools_called", LIFECYCLE_USE_CASE_TOOL
        )
    ]
    if len(safe_visible_called_names) < int(spec["safe_visible_called_minimum"]):
        reasons.append("safe_abstain_not_visible_and_called_on_all_required_tasks")
    cross_family_names = tuple(
        expected_roles.get(str(spec.get("cross_family_role") or ""), ())
    )
    cross_family_visible_called_count = sum(
        name in safe_visible_called_names for name in cross_family_names
    )

    safe_exact_names = [
        name
        for name in safe_names
        if name in candidate_by_name
        and _exact_targeted_abstention(candidate_by_name[name])
    ]
    if len(safe_exact_names) < int(spec["safe_exact_minimum"]):
        reasons.append("insufficiency_exact_outcome_gate_failed")
    contact_exact_no_remove_names = [
        name
        for name in contact_names
        if name in candidate_by_name
        and _exact_targeted_abstention(candidate_by_name[name])
        and not _forbidden_remove_contact(candidate_by_name[name])
    ]
    if len(contact_exact_no_remove_names) < int(
        spec["contact_exact_no_remove_minimum"]
    ):
        reasons.append("contact_exact_without_forbidden_remove_gate_failed")
    preservation_exact_hidden_names = [
        name
        for name in preservation_names
        if name in candidate_by_name
        and _exact_outcome(candidate_by_name[name])
        and name in selection_by_name
        and not _selection_has_tool(
            selection_by_name[name], "generated_tools_visible", LIFECYCLE_USE_CASE_TOOL
        )
        and not _selection_has_tool(
            selection_by_name[name], "generated_tools_called", LIFECYCLE_USE_CASE_TOOL
        )
        and name in feedback_by_name
        and not _selection_has_tool(
            feedback_by_name[name], "generated_tools_visible", LIFECYCLE_USE_CASE_TOOL
        )
        and not _selection_has_tool(
            feedback_by_name[name], "generated_tools_called", LIFECYCLE_USE_CASE_TOOL
        )
    ]
    if len(preservation_exact_hidden_names) < int(
        spec["preservation_exact_hidden_minimum"]
    ):
        reasons.append("preservation_exact_and_safe_helper_hidden_gate_failed")

    registry_dir = _strict_run_verifier._resolve_declared_path(
        run_root,
        protocol.get("registry_dir"),
        "registry_dir",
    )
    lifecycle = _lifecycle_integrity(candidate_dir, registry_dir)
    repair_requests = lifecycle["repair_requests"]
    acknowledgements = lifecycle["acknowledgements"]
    initial_registry = protocol.get("registry_gate_snapshot")
    if not isinstance(initial_registry, dict) or any(
        (
            initial_registry.get("manifest_existed_before_run") is not True,
            initial_registry.get("manifest_digest_before_run")
            != LIFECYCLE_FAULT_FIXTURE_SHA256,
        )
    ):
        reasons.append("pinned_historical_fault_fixture_not_used")
    else:
        initial_snapshot_path = _strict_run_verifier._resolve_declared_path(
            run_root,
            initial_registry.get("snapshot_path"),
            "registry_gate_snapshot.snapshot_path",
            required_parent=run_root / "registry_gate",
        )
        if (
            not initial_snapshot_path.is_file()
            or hashlib.sha256(initial_snapshot_path.read_bytes()).hexdigest()
            != LIFECYCLE_FAULT_FIXTURE_SHA256
        ):
            reasons.append("pinned_historical_fault_snapshot_bytes_mismatch")
    prohibited_payload_keys = {
        "scenario_name",
        "task_id",
        "expected_answer",
        "target_state",
        "evaluator_trace",
    }
    for request in repair_requests:
        public_evidence = request.get("public_evidence")
        if not isinstance(public_evidence, dict):
            reasons.append("repair_public_evidence_missing")
            continue
        if prohibited_payload_keys & set(public_evidence):
            reasons.append("repair_request_contains_prohibited_evidence")
        if request.get("future_tasks_only") is not True:
            reasons.append("repair_not_future_only")
        if request.get("triggering_task_replay_allowed") is not False:
            reasons.append("repair_allows_triggering_task_replay")

    if not lifecycle["state_present"]:
        reasons.append("lifecycle_repair_state_missing")
    if not lifecycle["state_schema_valid"]:
        reasons.append("lifecycle_repair_state_schema_invalid")
    if lifecycle["pending_repair_request_count"] != 0:
        reasons.append("pending_lifecycle_repair_requests_at_run_end")
    if lifecycle["open_canary_count"] != 0:
        reasons.append("open_repaired_tool_canaries_at_run_end")
    if lifecycle["open_repair_transaction_count"] != 0:
        reasons.append("open_lifecycle_repair_transactions_at_run_end")
    if not lifecycle["handled_state_valid"]:
        reasons.append("invalid_handled_lifecycle_repair_state")
    if lifecycle["unacknowledged_repair_request_ids"]:
        reasons.append("unacknowledged_lifecycle_repair_requests")
    if lifecycle["duplicate_repair_request_ids"]:
        reasons.append("duplicate_lifecycle_repair_requests")
    if lifecycle["orphaned_repair_acknowledgement_ids"]:
        reasons.append("orphaned_lifecycle_repair_acknowledgements")
    if lifecycle["mismatched_repair_acknowledgement_tool_ids"]:
        reasons.append("lifecycle_repair_acknowledgement_tool_mismatch")
    if lifecycle["nonterminal_repair_request_ids"]:
        reasons.append("nonterminal_lifecycle_repair_acknowledgements")
    if lifecycle["unhandled_repair_request_ids"]:
        reasons.append("terminal_lifecycle_requests_missing_from_handled_state")
    if lifecycle["orphaned_handled_repair_request_ids"]:
        reasons.append("handled_lifecycle_requests_missing_from_journal")
    if lifecycle["active_unresolved_tools"]:
        reasons.append("active_unresolved_repaired_tools")
    if lifecycle["active_repairs_without_promotion"]:
        reasons.append("active_repair_without_exact_promoted_acknowledgement")

    use_case_requests = [
        row
        for row in repair_requests
        if row.get("tool_name") == LIFECYCLE_USE_CASE_TOOL
        and row.get("source_tool_version") == 1
        and row.get("repair_kind") == "implementation"
    ]
    if len(use_case_requests) != 1:
        reasons.append("historical_v1_repair_request_count_mismatch")
    use_case_request = use_case_requests[0] if len(use_case_requests) == 1 else {}
    use_case_request_id = str(use_case_request.get("request_id") or "")
    if "deterministic_public_contract_failure" not in (
        use_case_request.get("trigger_reason_codes") or []
    ):
        reasons.append("historical_v1_repair_reason_not_deterministic_contract_failure")
    use_case_acks = [
        row
        for row in acknowledgements
        if str(row.get("request_id") or "") == use_case_request_id
    ]
    use_case_ack_statuses = [str(row.get("status") or "") for row in use_case_acks]
    if "canary_pending" not in use_case_ack_statuses:
        reasons.append("historical_v1_replacement_not_accepted_for_canary")
    if not use_case_ack_statuses or use_case_ack_statuses[-1] != "promoted":
        reasons.append("historical_v1_replacement_not_promoted")

    triggering_completed_count = int(
        use_case_request.get("trigger_completed_count") or 0
    )
    trigger_rows = [
        row
        for row in feedback_rows
        if int(row.get("completed_count") or 0) == triggering_completed_count
        and str(row.get("scenario") or "") in safe_names
        and use_case_request_id in (row.get("post_deployment_repair_request_ids") or [])
    ]
    trigger_row = trigger_rows[0] if len(trigger_rows) == 1 else {}
    trigger_scenario = str(trigger_row.get("scenario") or "")
    trigger_versions = trigger_row.get("generated_tool_versions")
    trigger_outcome = (
        _outcome(candidate_by_name[trigger_scenario])
        if trigger_scenario in candidate_by_name
        else None
    )
    trigger_proves_v1_failure = bool(
        len(trigger_rows) == 1
        and trigger_scenario == safe_names[0]
        and isinstance(trigger_versions, dict)
        and trigger_versions.get(LIFECYCLE_USE_CASE_TOOL) == 1
        and LIFECYCLE_USE_CASE_TOOL in (trigger_row.get("generated_tools_called") or [])
        and LIFECYCLE_USE_CASE_TOOL
        in (trigger_row.get("generated_tool_contract_failures") or [])
        and trigger_outcome is not None
        and trigger_outcome < 1.0
    )
    if not trigger_proves_v1_failure:
        reasons.append("historical_v1_trigger_did_not_prove_observed_failure")

    future_v2_rows: list[dict[str, Any]] = []
    for row in feedback_rows:
        versions = row.get("generated_tool_versions")
        if (
            int(row.get("completed_count") or 0) > triggering_completed_count
            and str(row.get("scenario") or "") in safe_names
            and isinstance(versions, dict)
            and versions.get(LIFECYCLE_USE_CASE_TOOL) == 2
            and LIFECYCLE_USE_CASE_TOOL in (row.get("generated_tools_called") or [])
        ):
            future_v2_rows.append(row)
    expected_future_v2_call_count = len(safe_names) - 1
    if len(future_v2_rows) != expected_future_v2_call_count:
        reasons.append("future_v2_safe_task_call_coverage_mismatch")
    future_v2_exact_successes = sum(
        str(row.get("scenario") or "") in candidate_by_name
        and _exact_targeted_abstention(
            candidate_by_name[str(row.get("scenario") or "")]
        )
        for row in future_v2_rows
    )
    if future_v2_exact_successes < int(spec["future_v2_exact_minimum"]):
        reasons.append("future_v2_exact_success_gate_failed")
    future_v2_success_flips = sum(
        str(row.get("scenario") or "") in candidate_by_name
        and str(row.get("scenario") or "") in control_by_name
        and _exact_targeted_abstention(
            candidate_by_name[str(row.get("scenario") or "")]
        )
        and not _exact_outcome(control_by_name[str(row.get("scenario") or "")])
        for row in future_v2_rows
    )
    if future_v2_success_flips < int(spec["future_v2_success_flip_minimum"]):
        reasons.append("future_v2_affirmative_success_flip_missing")

    run_events = _read_jsonl(candidate_dir / "sage_run_events.jsonl")
    repair_acceptance_events = [
        row
        for row in run_events
        if row.get("event") == "post_deployment_tool_repair_accepted"
        and row.get("request_id") == use_case_request_id
        and row.get("tool_name") == LIFECYCLE_USE_CASE_TOOL
        and row.get("source_tool_version") == 1
        and row.get("new_tool_version") == 2
        and row.get("triggering_task_replayed") is False
    ]
    if len(repair_acceptance_events) != 1:
        reasons.append("postdeployment_v2_acceptance_event_missing")

    registry_path = registry_dir / "registry_manifest.json"
    registry = _load_json(registry_path)
    recorded_registry_digest = protocol.get("registry_manifest_digest_after_run")
    observed_registry_digest = hashlib.sha256(registry_path.read_bytes()).hexdigest()
    if recorded_registry_digest != observed_registry_digest:
        reasons.append("final_registry_digest_mismatch")
    final_entry = (
        registry.get("tools", {}).get(LIFECYCLE_USE_CASE_TOOL)
        if isinstance(registry, dict) and isinstance(registry.get("tools"), dict)
        else None
    )
    if not isinstance(final_entry, dict) or any(
        (final_entry.get("version") != 2, final_entry.get("retired") is not False)
    ):
        reasons.append("promoted_repaired_version_not_active_in_final_registry")

    report = {
        "status": "pass" if not reasons else "fail",
        "run_root": str(run_root),
        "development_only": True,
        "publication_eligible": False,
        "manifest_type": manifest_type,
        "lifecycle_evidence_mode": ("seeded_historical_v1_postdeployment_repair"),
        "expected_tasks": expected_tasks,
        "scenario_order_sha256": expected_order_sha256,
        "parallel_arm_execution": parallel_execution,
        "candidate_audited_outcome_count": len(candidate_outcomes),
        "control_audited_outcome_count": len(control_outcomes),
        "outcome_evaluator": expected_evaluator,
        "candidate_outcome_mean": candidate_mean,
        "control_outcome_mean": control_mean,
        "outcome_lift": (
            candidate_mean - control_mean
            if candidate_mean is not None and control_mean is not None
            else None
        ),
        "overall_exact_success_count": overall_exact_successes,
        "safe_abstain_task_count": len(safe_names),
        "safe_abstain_visible_and_called_count": len(safe_visible_called_names),
        "safe_abstain_exact_outcome_count": len(safe_exact_names),
        "cross_family_safe_abstain_task_count": len(cross_family_names),
        "cross_family_safe_abstain_visible_and_called_count": (
            cross_family_visible_called_count
        ),
        "contact_repair_task_count": len(contact_names),
        "contact_exact_without_forbidden_remove_count": len(
            contact_exact_no_remove_names
        ),
        "preservation_task_count": len(preservation_names),
        "preservation_exact_and_safe_helper_hidden_count": len(
            preservation_exact_hidden_names
        ),
        "historical_fault_fixture_sha256": LIFECYCLE_FAULT_FIXTURE_SHA256,
        "use_case_tool": LIFECYCLE_USE_CASE_TOOL,
        "use_case_request_id": use_case_request_id or None,
        "use_case_repair_reason_codes": list(
            use_case_request.get("trigger_reason_codes") or []
        ),
        "use_case_acknowledgement_statuses": use_case_ack_statuses,
        "historical_v1_trigger_scenario": trigger_scenario or None,
        "historical_v1_trigger_outcome": trigger_outcome,
        "historical_v1_observed_failure_proved": trigger_proves_v1_failure,
        "repaired_version_future_call_count": len(future_v2_rows),
        "repaired_version_future_exact_success_count": future_v2_exact_successes,
        "repaired_version_future_success_flip_count": future_v2_success_flips,
        "repair_acceptance_event_count": len(repair_acceptance_events),
        "repair_request_count": len(repair_requests),
        "repair_acknowledgement_count": len(acknowledgements),
        "unacknowledged_repair_request_ids": lifecycle[
            "unacknowledged_repair_request_ids"
        ],
        "duplicate_repair_request_ids": lifecycle["duplicate_repair_request_ids"],
        "orphaned_repair_acknowledgement_ids": lifecycle[
            "orphaned_repair_acknowledgement_ids"
        ],
        "mismatched_repair_acknowledgement_tool_ids": lifecycle[
            "mismatched_repair_acknowledgement_tool_ids"
        ],
        "nonterminal_repair_request_ids": lifecycle["nonterminal_repair_request_ids"],
        "pending_repair_request_count": lifecycle["pending_repair_request_count"],
        "open_canary_count": lifecycle["open_canary_count"],
        "open_repair_transaction_count": lifecycle["open_repair_transaction_count"],
        "unhandled_repair_request_ids": lifecycle["unhandled_repair_request_ids"],
        "orphaned_handled_repair_request_ids": lifecycle[
            "orphaned_handled_repair_request_ids"
        ],
        "active_unresolved_tools": lifecycle["active_unresolved_tools"],
        "active_repairs_without_promotion": lifecycle[
            "active_repairs_without_promotion"
        ],
        "reasons": sorted(set(reasons)),
    }
    report_path = run_root / "lifecycle_repair_validation_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-root", type=Path, required=True)
    parser.add_argument("--expected-tasks", type=int, required=True)
    args = parser.parse_args()
    report = verify(args.search_root, args.expected_tasks)
    print(json.dumps(report, indent=2))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
