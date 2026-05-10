# mypy: ignore-errors
"""Build a narrow send-message recipient lookup pack for gap-closure testing.

Experimental only. Broad500 diagnostics showed a small but high-leverage send
bucket where the actor sometimes asked for a phone number even though a named
recipient and search_contacts were visible. This helper is pure: it prepares the
safe contact search and preserves the original send side effect.
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
BASE = (
    REGISTRY_ROOT
    / "full_timestamp_no_field_plus_schedule_v2_pack"
    / "registry_manifest.json"
)
COMBINED_OUT = (
    REGISTRY_ROOT
    / "full_timestamp_schedule_v2_plus_send_lookup_pack"
    / "registry_manifest.json"
)
SEND_ONLY_OUT = (
    REGISTRY_ROOT / "send_message_lookup_only_pack" / "registry_manifest.json"
)
BROAD_SPLITS = Path(
    "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/top_tool_combo_broad_splits.json"
)
SEND_SPLITS = MANIFEST_ROOT / "send_message_precondition_splits.json"
SUMMARY_OUT = MANIFEST_ROOT / "send_message_lookup_pack_summary.json"

SEND_LOOKUP_CODE = '''
def plan_send_message_contact_lookup(recipient_name: str, message_content: str) -> dict:
    """Prepare a safe contact lookup before sending a message to a named contact."""
    name = " ".join(str(recipient_name or "").strip().split())
    content = str(message_content or "").strip()
    if not name:
        return {
            "should_call_search_contacts": False,
            "search_contacts_kwargs": {},
            "downstream_tool_name": "",
            "message_content": content,
            "abstain_reason": "missing_recipient_name",
            "next_step": "ask_for_recipient_or_phone_number",
            "final_answer_recommendation": "I need the recipient name or phone number before I can send that message.",
        }
    if not content:
        return {
            "should_call_search_contacts": False,
            "search_contacts_kwargs": {},
            "downstream_tool_name": "",
            "message_content": "",
            "abstain_reason": "missing_message_content",
            "next_step": "ask_for_message_content",
            "final_answer_recommendation": "I need the message content before I can send that message.",
        }
    return {
        "should_call_search_contacts": True,
        "search_contacts_kwargs": {"name": name},
        "downstream_tool_name": "send_message_with_phone_number",
        "message_content": content,
        "abstain_reason": "",
        "next_step": "call search_contacts, then send_message_with_phone_number using the returned phone_number and this message_content",
        "final_answer_recommendation": "search_contacts first; if cellular is disabled during send, enable cellular and retry once",
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


def _send_lookup_entry() -> dict[str, Any]:
    spec = ToolSpec(
        tool_name="plan_send_message_contact_lookup",
        family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        description=(
            "Pure send-message recipient lookup planner. Use when the user asks "
            "to send, ask, or tell a named contact something and search_contacts "
            "is visible but the phone number is not already known. It returns "
            "search_contacts_kwargs and the message_content to carry forward to "
            "send_message_with_phone_number after the original search returns a "
            "phone number. It does not send messages or mutate device state."
        ),
        inputs=(
            ToolInput(
                "recipient_name",
                "str",
                "Visible recipient/contact name from the user request.",
            ),
            ToolInput(
                "message_content",
                "str",
                "Visible message text to send after contact lookup.",
            ),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "should_call_search_contacts": {"type": "boolean"},
                "search_contacts_kwargs": {"type": "object"},
                "downstream_tool_name": {
                    "type": "string",
                    "enum": ["send_message_with_phone_number", ""],
                },
                "message_content": {"type": "string"},
                "abstain_reason": {"type": "string"},
                "next_step": {"type": "string"},
                "final_answer_recommendation": {"type": "string"},
            },
        },
        positive_triggers=(
            "send_message",
            "send message",
            "ask named contact",
            "tell named contact",
            "named recipient lookup before sending",
        ),
        negative_triggers=(
            "insufficient_information",
            "phone_number_and_content",
            "no recipient name",
            "missing message content",
            "search_contacts unavailable",
            "reminder",
            "weather",
            "stock",
            "currency",
        ),
        preserves_side_effect_tools=(
            "search_contacts",
            "send_message_with_phone_number",
        ),
        required_original_tool_calls=(
            "search_contacts",
            "send_message_with_phone_number",
        ),
        abstain_behavior=(
            "If recipient_name or message_content is missing, return "
            "should_call_search_contacts=False and a final-answer-ready clarification."
        ),
        generalization_rationale=(
            "Named-recipient send requests recur across plain, distracted, and "
            "tool-scrambled send-message variants. The helper only prepares a "
            "search and carries message text, so it is safe to test narrowly."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=("send_message", "send message to named contact"),
        reason_tool_is_decisive=(
            "It prevents premature phone-number clarification when a safe contact "
            "search can resolve the recipient before the original send tool."
        ),
        shortfall_cluster_evidence=("send_message_precondition_no_visible_helper",),
        known_failure_mechanisms_addressed=(
            "named_recipient_phone_clarification_instead_of_search",
            "message_content_lost_before_send_retry",
            "cellular_disabled_retry_needs_same_send_arguments",
        ),
        canonical_route_substitution_risk="low",
        expected_milestone_calls_replaced=(),
        final_state_preservation_plan=(
            "The helper has no side effects. The original search_contacts and "
            "send_message_with_phone_number calls must still happen in the trace."
        ),
        grading_accounting_note=(
            "Outcome/task completion is primary; canonical route is preserved "
            "because original search/send calls remain required."
        ),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary=(
                "Broad500 send-message diagnostics showed no visible dedicated "
                "helper and repeated premature phone-number clarification on named "
                "recipient tasks despite search_contacts being available."
            ),
            signals=(
                "no_current_helper_fit",
                "visible_named_recipient",
                "send_precondition",
            ),
            visible_data_gaps=(
                "search_contacts kwargs and message content carry-forward",
            ),
            planner_failures=("asked_user_for_phone_before_safe_contact_search",),
            final_answer_route_mismatch=False,
        ),
    )
    tool = GeneratedTool(spec=spec, code=SEND_LOOKUP_CODE)
    examples = (
        ToolExample(
            {
                "recipient_name": "Fredrik Thordendal",
                "message_content": "How's the new album coming along.",
            },
            {
                "should_call_search_contacts": True,
                "search_contacts_kwargs": {"name": "Fredrik Thordendal"},
                "downstream_tool_name": "send_message_with_phone_number",
                "message_content": "How's the new album coming along.",
                "abstain_reason": "",
                "next_step": "call search_contacts, then send_message_with_phone_number using the returned phone_number and this message_content",
                "final_answer_recommendation": "search_contacts first; if cellular is disabled during send, enable cellular and retry once",
            },
        ),
        ToolExample(
            {"recipient_name": "  Ada   Lovelace ", "message_content": "Call me back"},
            {
                "should_call_search_contacts": True,
                "search_contacts_kwargs": {"name": "Ada Lovelace"},
                "downstream_tool_name": "send_message_with_phone_number",
                "message_content": "Call me back",
                "abstain_reason": "",
                "next_step": "call search_contacts, then send_message_with_phone_number using the returned phone_number and this message_content",
                "final_answer_recommendation": "search_contacts first; if cellular is disabled during send, enable cellular and retry once",
            },
            held_out=True,
        ),
        ToolExample(
            {"recipient_name": "", "message_content": "Hello"},
            {
                "should_call_search_contacts": False,
                "search_contacts_kwargs": {},
                "downstream_tool_name": "",
                "message_content": "Hello",
                "abstain_reason": "missing_recipient_name",
                "next_step": "ask_for_recipient_or_phone_number",
                "final_answer_recommendation": "I need the recipient name or phone number before I can send that message.",
            },
            negative_applicability=True,
        ),
    )
    validation = validate_generated_tool(tool, examples)
    if not validation.accepted:
        raise RuntimeError(f"send lookup validation failed: {validation.errors}")
    return RegistryEntry.accepted(
        tool=tool,
        validation=validation,
        birth_scenario="send_message_named_recipient_lookup_seed",
    ).to_json()


def _send_rows_from_broad_manifest() -> list[dict[str, Any]]:
    broad = json.loads(BROAD_SPLITS.read_text(encoding="utf-8"))
    rows = broad["splits"]["top_tool_broad500"]
    direct_send = [
        copy.deepcopy(row)
        for row in rows
        if str(row.get("scenario_id", "")).startswith("send_message")
    ]
    for row in direct_send:
        row["truth_labels_inspected"] = False
        row["used_for_generation"] = False
        row["used_for_repair"] = False
        row["used_for_routing"] = False
        row["used_for_validation"] = True
        row["final_evaluation"] = False
    return direct_send


def _family_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        family = str(row.get("family_label") or row.get("scenario_id", "unknown"))
        counts[family] = counts.get(family, 0) + 1
    return dict(sorted(counts.items()))


def _write_send_manifest(rows: list[dict[str, Any]]) -> str:
    splits = {
        "send_message_precondition_20": [
            {**copy.deepcopy(row), "split": "send_message_precondition_20"}
            for row in rows[:20]
        ],
        "send_message_precondition_all": [
            {**copy.deepcopy(row), "split": "send_message_precondition_all"}
            for row in rows
        ],
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "sage_gap_closure_lab_send_message_precondition_splits",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "protected_claim_evidence": False,
        "truth_labels_inspected": False,
        "selection_policy": {
            "selection_note": (
                "Direct send-message scenarios copied in existing broad500 order. "
                "No labels or cache availability were used."
            ),
            "used_truth_labels": False,
            "used_expected_answers": False,
            "used_cache_availability": False,
        },
        "cache_policy": {
            "baseline_control_cache": "use-if-eligible",
            "sage_candidate_cache": "fresh_only",
            "openai_response_cache_for_candidate": "disabled",
        },
        "split_aliases": {
            "pilot_20": "send_message_precondition_20",
            "expanded_60": "send_message_precondition_all",
            "confirm_100": "send_message_precondition_all",
        },
        "split_sizes": {name: len(split_rows) for name, split_rows in splits.items()},
        "split_diversity": {
            name: {
                "distinct_family_count": len(_family_counts(split_rows)),
                "family_counts": _family_counts(split_rows),
                "near_duplicate_assessment": (
                    "Narrow send-message precondition split; variants include no "
                    "distraction, distraction, all-tools, alt phrasing, and tool "
                    "metadata scrambling. It is intentionally bucket-specific."
                ),
            }
            for name, split_rows in splits.items()
        },
        "splits": splits,
    }
    return _write_json(SEND_SPLITS, manifest)


def main() -> None:
    base_tools = _load_tools(BASE)
    send_entry = _send_lookup_entry()
    send_only = {"plan_send_message_contact_lookup": send_entry}
    combined = {**copy.deepcopy(base_tools), **send_only}
    send_only_sha = _write_json(SEND_ONLY_OUT, {"tools": send_only})
    combined_sha = _write_json(COMBINED_OUT, {"tools": combined})
    rows = _send_rows_from_broad_manifest()
    split_sha = _write_send_manifest(rows)
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "protected_claim_evidence": False,
        "objective": (
            "Add a narrow pure helper for send-message named-recipient lookup and "
            "test whether it repairs premature phone-number clarification."
        ),
        "base_registry": str(BASE),
        "base_registry_sha256": _sha256(BASE.read_bytes()),
        "registries": {
            "send_only": {
                "path": str(SEND_ONLY_OUT),
                "sha256": send_only_sha,
                "tools": sorted(send_only),
            },
            "combined": {
                "path": str(COMBINED_OUT),
                "sha256": combined_sha,
                "tools": sorted(combined),
            },
        },
        "manifest": {
            "path": str(SEND_SPLITS),
            "sha256": split_sha,
            "direct_send_scenario_count": len(rows),
        },
        "leakage_controls": {
            "truth_labels_inspected": False,
            "used_cache_availability_for_selection": False,
            "scenario_ids_encoded_into_tool": False,
            "candidate_arms_fresh_only": True,
            "baseline_cache_policy": "use-if-eligible",
        },
    }
    _write_json(SUMMARY_OUT, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
