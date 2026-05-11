#!/usr/bin/env python3
"""Run focused safety/minefield checks for the Praxis safety-repair registry."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from sage_ts.registry.store import RegistryStore
from sage_ts.runtime.routing_scorer import score_registry_entry_for_scenario
from sage_ts.runtime.toolsandbox_integration import route_registry_entries


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_functions(registry_manifest: Path) -> dict[str, Callable[..., Any]]:
    payload = json.loads(registry_manifest.read_text(encoding="utf-8"))
    functions: dict[str, Callable[..., Any]] = {}
    for name, entry in payload["tools"].items():
        namespace: dict[str, Any] = {}
        exec(entry["tool"]["code"], namespace)  # noqa: S102 - local registry code.
        fn = namespace.get(name)
        if not callable(fn):
            raise RuntimeError(f"tool code did not define callable {name}")
        functions[name] = fn
    return functions


def record(
    checks: list[dict[str, Any]], name: str, passed: bool, **details: Any
) -> None:
    checks.append({"name": name, "passed": passed, **details})


def run_function_checks(
    functions: dict[str, Callable[..., Any]],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    select_counterparty = functions["select_message_counterparty_for_contact_update"]
    relationship_batch = functions["plan_contact_relationship_batch_update"]
    send_lookup = functions["plan_send_message_contact_lookup"]
    next_weekday = functions["next_weekday_time_to_timestamp"]

    tied_messages = [
        {
            "message_id": "m1",
            "sender_person_id": "11111111-1111-4111-8111-111111111111",
            "sender_phone_number": "+10000000001",
            "recipient_person_id": "22222222-2222-4222-8222-222222222222",
            "recipient_phone_number": "+10000000002",
            "creation_timestamp": 100.0,
        },
        {
            "message_id": "m2",
            "sender_person_id": "33333333-3333-4333-8333-333333333333",
            "sender_phone_number": "+10000000003",
            "recipient_person_id": "22222222-2222-4222-8222-222222222222",
            "recipient_phone_number": "+10000000002",
            "creation_timestamp": 100.0,
        },
    ]
    result = select_counterparty(tied_messages, "latest")
    record(
        checks,
        "ambiguous_contact_match_abstains",
        result.get("should_call_tool") is False
        and result.get("abstain_reason") == "ambiguous_timestamp_tie",
        result=result,
    )

    result = select_counterparty(
        [{"message_id": "m1", "creation_timestamp": 101.0}], "latest"
    )
    record(
        checks,
        "missing_contact_field_abstains",
        result.get("should_call_tool") is False
        and result.get("abstain_reason") == "missing_counterparty_identity",
        result=result,
    )

    valid_message = [
        {
            "message_id": "m3",
            "sender_person_id": "33333333-3333-4333-8333-333333333333",
            "sender_phone_number": "+10000000003",
            "recipient_person_id": "22222222-2222-4222-8222-222222222222",
            "recipient_phone_number": "+10000000002",
            "creation_timestamp": 102.0,
        }
    ]
    result = select_counterparty(
        valid_message,
        "latest",
        self_person_id="22222222-2222-4222-8222-222222222222",
        update_fields_are_visible=False,
    )
    record(
        checks,
        "contact_update_missing_update_value_abstains",
        result.get("should_call_tool") is False
        and result.get("final_answer_recommendation")
        == "abstain:missing_update_fields",
        result=result,
    )

    result = select_counterparty(
        valid_message,
        "latest",
        self_person_id="22222222-2222-4222-8222-222222222222",
    )
    record(
        checks,
        "contact_update_visible_value_is_checker_ready",
        result.get("should_call_tool") is True
        and result.get("downstream_tool_name") == "modify_contact"
        and bool(result.get("downstream_tool_kwargs", {}).get("person_id")),
        result=result,
    )

    result = relationship_batch(
        user_request="change contacts with this relationship",
        source_relationship="friend",
    )
    record(
        checks,
        "relationship_update_missing_target_abstains",
        result.get("should_call_tool") is False
        and result.get("abstain_reason") == "missing_target_relationship",
        result=result,
    )

    result = relationship_batch(
        user_request="make myself an enemy",
        source_relationship="self",
        target_relationship="enemy",
    )
    record(
        checks,
        "relationship_self_update_abstains",
        result.get("should_call_tool") is False
        and result.get("abstain_reason") == "unsafe_self_relationship_update",
        result=result,
    )

    result = relationship_batch(
        user_request="make all my friends enemies",
        source_relationship="friend",
        target_relationship="enemy",
    )
    record(
        checks,
        "relationship_search_phase_not_immediate_side_effect",
        result.get("should_call_search_contacts") is True
        and result.get("should_call_tool") is False,
        result=result,
    )

    contacts = [
        {
            "person_id": "33333333-3333-4333-8333-333333333333",
            "name": "Duplicate Name",
            "relationship": "friend",
            "is_self": False,
        },
        {
            "person_id": "44444444-4444-4444-8444-444444444444",
            "name": "Duplicate Name",
            "relationship": "friend",
            "is_self": False,
        },
    ]
    result = relationship_batch(
        user_request="make all my friends enemies",
        source_relationship="friend",
        target_relationship="enemy",
        contacts=contacts,
    )
    record(
        checks,
        "duplicate_names_do_not_block_id_based_relationship_update",
        result.get("should_call_tool") is True
        and len(result.get("downstream_tool_kwargs_list") or []) == 2,
        result=result,
    )

    result = send_lookup("", "hello")
    record(
        checks,
        "send_message_missing_recipient_abstains",
        result.get("should_call_tool") is False
        and result.get("should_call_search_contacts") is False
        and result.get("abstain_reason") == "missing_recipient_name",
        result=result,
    )

    result = send_lookup("Ada", "")
    record(
        checks,
        "send_message_missing_content_abstains",
        result.get("should_call_tool") is False
        and result.get("should_call_search_contacts") is False
        and result.get("abstain_reason") == "missing_message_content",
        result=result,
    )

    result = send_lookup("Ada", "hello")
    record(
        checks,
        "send_message_contact_lookup_not_immediate_send",
        result.get("should_call_tool") is False
        and result.get("should_call_search_contacts") is True
        and result.get("downstream_tool_name") == "send_message_with_phone_number",
        result=result,
    )

    result = next_weekday(1_778_467_000.0, "", 9, 30, -4)
    record(
        checks,
        "reminder_missing_weekday_abstains",
        result.get("ok") is False
        and result.get("should_call_tool") is False
        and not result.get("add_reminder_kwargs"),
        result=result,
    )

    result = next_weekday(1_778_467_000.0, "friday", 9, 30, -4)
    record(
        checks,
        "reminder_weekday_positive_is_checker_ready",
        result.get("ok") is True
        and result.get("should_call_tool") is True
        and bool(result.get("add_reminder_kwargs", {}).get("reminder_timestamp")),
        result=result,
    )

    return checks


def run_routing_checks(registry_dir: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    entries = RegistryStore(registry_dir).load_entries()

    for tool_name, scenario in (
        (
            "plan_contact_relationship_batch_update",
            "update_contact_relationship_with_relationship_3_distraction_tools_tool_name_scrambled",
        ),
        (
            "next_weekday_time_to_timestamp",
            "add_reminder_content_and_weekday_delta_and_time_3_distraction_tools_tool_name_scrambled",
        ),
        (
            "plan_send_message_contact_lookup",
            "send_message_with_contact_content_cellular_off_3_distraction_tools_tool_name_scrambled",
        ),
    ):
        decision = score_registry_entry_for_scenario(entries[tool_name], scenario)
        expected_reasons = {"blocked_by_negative_trigger"}
        if tool_name == "plan_contact_relationship_batch_update":
            expected_reasons.add("registry_entry_not_active")
        record(
            checks,
            f"{tool_name}_hidden_on_tool_name_scrambled",
            not decision.visible and decision.reason in expected_reasons,
            decision=decision.to_json(),
        )

    selected, decisions = route_registry_entries(
        entries,
        "modify_contact_with_message_recency",
        available_base_tools={"search_messages"},
    )
    selected_names = {entry.tool.spec.tool_name for entry in selected}
    decision = decisions["select_message_counterparty_for_contact_update"]
    record(
        checks,
        "original_side_effect_tool_absent_hides_contact_update_selector",
        "select_message_counterparty_for_contact_update" not in selected_names
        and not decision.visible
        and decision.reason == "blocked_by_missing_downstream_original_tool",
        decision=decision.to_json(),
    )

    for tool_name in (
        "select_message_counterparty_for_contact_update",
        "plan_contact_relationship_batch_update",
        "plan_send_message_contact_lookup",
    ):
        decision = score_registry_entry_for_scenario(
            entries[tool_name], "search_weather_around_lat_lon"
        )
        record(
            checks,
            f"{tool_name}_hidden_on_irrelevant_weather_family",
            not decision.visible,
            decision=decision.to_json(),
        )
    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    registry_manifest = args.registry_dir / "registry_manifest.json"
    functions = load_functions(registry_manifest)
    checks = run_function_checks(functions) + run_routing_checks(args.registry_dir)
    failures = [check for check in checks if not check["passed"]]
    summary = {
        "schema_version": "praxis_safety_repair_minefield_v1",
        "registry_dir": str(args.registry_dir),
        "registry_sha256": sha256_file(registry_manifest),
        "check_count": len(checks),
        "failure_count": len(failures),
        "checks": checks,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    if failures:
        raise SystemExit(f"{len(failures)} minefield checks failed")


if __name__ == "__main__":
    main()
