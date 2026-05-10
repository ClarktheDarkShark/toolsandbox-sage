"""Build a narrow contact relationship-update pack for gap-closure tests.

Experimental only. This pack targets two Contact CRUD subcases without exposing
the broader timestamp/state portfolio:
- message-recency contact updates, via the retained counterparty selector
- group relationship updates, via a pure search/modify planner
"""

from __future__ import annotations

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

ROOT = Path("artifacts/registry_experiments/gap_closure_lab/action_precondition_loop")
MANIFEST_ROOT = Path(
    "artifacts/experiment_manifests/gap_closure_lab/action_precondition_loop"
)
SELECTOR_SOURCE = (
    ROOT / "contact_counterparty_selector_only_pack" / "registry_manifest.json"
)
OUT = ROOT / "contact_selector_relationship_update_pack" / "registry_manifest.json"
SUMMARY = MANIFEST_ROOT / "contact_selector_relationship_update_summary.json"
SELECTOR_NAME = "select_message_counterparty_for_contact_update"


RELATIONSHIP_BATCH_CODE = '''
def plan_contact_relationship_batch_update(user_request: str = "", source_relationship: str = "", target_relationship: str = "", contacts: list = None) -> dict:
    """Plan a safe relationship-group contact update without side effects."""
    contacts = contacts if isinstance(contacts, list) else []
    text = str(user_request or "").strip().lower().replace("_", " ").replace("-", " ")

    aliases = {
        "friend": "friend",
        "friends": "friend",
        "enemy": "enemy",
        "enemies": "enemy",
        "coworker": "coworker",
        "coworkers": "coworker",
        "colleague": "coworker",
        "colleagues": "coworker",
        "family": "family",
        "families": "family",
        "relative": "family",
        "relatives": "family",
        "self": "self",
    }

    def norm(value) -> str:
        raw = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
        raw = raw.replace("my ", "").replace("all ", "").strip()
        return aliases.get(raw, raw[:-1] if raw.endswith("s") and len(raw) > 3 else raw)

    def empty(reason: str) -> dict:
        return {
            "phase": "abstain",
            "source_relationship": source,
            "target_relationship": target,
            "search_contacts_kwargs": {},
            "should_call_search_contacts": False,
            "selected_contacts": [],
            "downstream_tool_name": "",
            "downstream_tool_kwargs_list": [],
            "should_call_tools": False,
            "abstain_reason": reason,
            "final_answer_recommendation": "abstain:" + reason,
        }

    source = norm(source_relationship)
    target = norm(target_relationship)

    tokens = text.split()
    relationship_words = set(aliases)
    if not source:
        for index, token in enumerate(tokens):
            if token in relationship_words and index > 0 and tokens[index - 1] in {"my", "all", "the"}:
                source = norm(token)
                break
        if not source:
            for token in tokens:
                if token in relationship_words:
                    source = norm(token)
                    break

    if not target:
        for marker in (" to be my ", " to my ", " into my ", " as my ", " be my ", " my "):
            if marker in " " + text + " ":
                tail = (" " + text + " ").split(marker)[-1].strip()
                if tail:
                    target = norm(tail.split()[0])
        if not target:
            for token in tokens[::-1]:
                candidate = norm(token.strip(".,!?"))
                if candidate in set(aliases.values()) and candidate != source:
                    target = candidate
                    break

    if not source:
        return empty("missing_source_relationship")
    if not target:
        return empty("missing_target_relationship")
    if source == target:
        return empty("source_relationship_already_target")
    if source == "self" or target == "self":
        return empty("unsafe_self_relationship_update")

    if not contacts:
        return {
            "phase": "search_required",
            "source_relationship": source,
            "target_relationship": target,
            "search_contacts_kwargs": {"relationship": source},
            "should_call_search_contacts": True,
            "selected_contacts": [],
            "downstream_tool_name": "",
            "downstream_tool_kwargs_list": [],
            "should_call_tools": False,
            "abstain_reason": "",
            "final_answer_recommendation": "call:search_contacts",
        }

    selected = []
    for contact in contacts:
        if not isinstance(contact, dict):
            continue
        if bool(contact.get("is_self")):
            continue
        if norm(contact.get("relationship")) != source:
            continue
        person_id = str(contact.get("person_id") or "").strip()
        if not person_id:
            continue
        selected.append(contact)

    if not selected:
        return empty("no_non_self_contacts_with_source_relationship")

    kwargs_list = [
        {"person_id": str(contact["person_id"]), "relationship": target}
        for contact in selected
    ]
    return {
        "phase": "action_batch_ready",
        "source_relationship": source,
        "target_relationship": target,
        "search_contacts_kwargs": {"relationship": source},
        "should_call_search_contacts": False,
        "selected_contacts": selected,
        "downstream_tool_name": "modify_contact",
        "downstream_tool_kwargs_list": kwargs_list,
        "should_call_tools": True,
        "abstain_reason": "",
        "final_answer_recommendation": "call:modify_contact_for_each_selected_contact",
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


def _relationship_entry() -> dict[str, Any]:
    spec = ToolSpec(
        tool_name="plan_contact_relationship_batch_update",
        family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        description=(
            "Pure planner for contact relationship group updates. Use only when "
            "the user asks to change all contacts with one visible relationship "
            "label to another relationship label, such as friends to enemies. "
            "First call it with the user request; if it returns search_required, "
            "call search_contacts with search_contacts_kwargs. After the contacts "
            "are visible, call it again with those contacts and then call "
            "modify_contact once per downstream_tool_kwargs_list item. Do not use "
            "for named-contact updates, add/remove contact, message-recency contact "
            "updates, or insufficient-information tasks."
        ),
        inputs=(
            ToolInput("user_request", "str", "Visible user request text."),
            ToolInput(
                "source_relationship",
                "str",
                "Optional visible current relationship label.",
            ),
            ToolInput(
                "target_relationship",
                "str",
                "Optional visible target relationship label.",
            ),
            ToolInput(
                "contacts", "list", "Optional visible search_contacts result list."
            ),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "phase": {"type": "string"},
                "source_relationship": {"type": "string"},
                "target_relationship": {"type": "string"},
                "search_contacts_kwargs": {"type": "object"},
                "should_call_search_contacts": {"type": "boolean"},
                "selected_contacts": {"type": "array"},
                "downstream_tool_name": {"type": "string"},
                "downstream_tool_kwargs_list": {"type": "array"},
                "should_call_tools": {"type": "boolean"},
                "abstain_reason": {"type": "string"},
                "final_answer_recommendation": {"type": "string"},
            },
        },
        positive_triggers=(
            "update_contact_relationship_with_relationship",
            "make all my friends",
            "change all contacts with relationship",
            "all friends to enemies",
            "relationship group update",
        ),
        negative_triggers=(
            "insufficient_information",
            "add_contact",
            "remove_contact",
            "modify_contact_with_message_recency",
            "send_message",
            "reminder",
            "search-only answer",
            "named single contact",
            "self relationship",
        ),
        preserves_side_effect_tools=("search_contacts", "modify_contact"),
        required_original_tool_calls=("search_contacts", "modify_contact"),
        abstain_behavior=(
            "Return abstain with a reason if source/target relationship is missing, "
            "source equals target, self would be modified, or no non-self matching "
            "contacts are visible."
        ),
        generalization_rationale=(
            "Relationship-bulk contact updates recur across plain, distracted, "
            "and tool-scrambled Contact CRUD variants. The helper is pure and only "
            "bridges visible relationship labels to original search/modify calls."
        ),
        estimated_step_compression=4,
        cross_task_applicability_count=2,
        applicable_task_families=(
            "update_contact_relationship_with_relationship",
            "update_contact_relationship_with_relationship_twice_multiple_user_turn",
        ),
        reason_tool_is_decisive=(
            "It prevents unnecessary identifier clarification by using the visible "
            "relationship label as a safe search_contacts constraint, then prepares "
            "one original modify_contact call per matched contact."
        ),
        shortfall_cluster_evidence=("contact_crud_relationship_update_clarification",),
        known_failure_mechanisms_addressed=(
            "asked_for_contact_identifier_instead_of_relationship_search",
            "failed_to_batch_modify_visible_relationship_matches",
        ),
        canonical_route_substitution_risk="low",
        expected_milestone_calls_replaced=(
            "derive_relationship_search_constraint",
            "prepare_repeated_modify_contact_kwargs",
        ),
        final_state_preservation_plan=(
            "The helper performs no side effects. It preserves original search_contacts "
            "and modify_contact calls and excludes self contacts from action kwargs."
        ),
        grading_accounting_note=(
            "Outcome/task completion is primary; route impact is secondary because "
            "the original search and modify tools still perform the state changes."
        ),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary=(
                "Contact CRUD diagnostics showed large regressions on relationship "
                "group update tasks where the actor asked for identifiers instead "
                "of searching contacts by relationship."
            ),
            signals=("contact_crud_relationship_update_regression",),
            visible_data_gaps=(
                "source relationship and target relationship to search/modify kwargs",
            ),
            planner_failures=(
                "asked_for_identifier_despite_visible_relationship_constraint",
            ),
            final_answer_route_mismatch=False,
        ),
    )
    tool = GeneratedTool(spec=spec, code=RELATIONSHIP_BATCH_CODE)
    examples = (
        ToolExample(
            {"user_request": "Make all of my friends my enemy"},
            {
                "phase": "search_required",
                "source_relationship": "friend",
                "target_relationship": "enemy",
                "search_contacts_kwargs": {"relationship": "friend"},
                "should_call_search_contacts": True,
                "selected_contacts": [],
                "downstream_tool_name": "",
                "downstream_tool_kwargs_list": [],
                "should_call_tools": False,
                "abstain_reason": "",
                "final_answer_recommendation": "call:search_contacts",
            },
        ),
        ToolExample(
            {
                "user_request": "Change all friends to enemies",
                "contacts": [
                    {
                        "person_id": "11111111-1111-4111-8111-111111111111",
                        "relationship": "friend",
                        "is_self": False,
                    },
                    {
                        "person_id": "22222222-2222-4222-8222-222222222222",
                        "relationship": "friend",
                        "is_self": False,
                    },
                ],
            },
            {
                "phase": "action_batch_ready",
                "source_relationship": "friend",
                "target_relationship": "enemy",
                "search_contacts_kwargs": {"relationship": "friend"},
                "should_call_search_contacts": False,
                "selected_contacts": [
                    {
                        "person_id": "11111111-1111-4111-8111-111111111111",
                        "relationship": "friend",
                        "is_self": False,
                    },
                    {
                        "person_id": "22222222-2222-4222-8222-222222222222",
                        "relationship": "friend",
                        "is_self": False,
                    },
                ],
                "downstream_tool_name": "modify_contact",
                "downstream_tool_kwargs_list": [
                    {
                        "person_id": "11111111-1111-4111-8111-111111111111",
                        "relationship": "enemy",
                    },
                    {
                        "person_id": "22222222-2222-4222-8222-222222222222",
                        "relationship": "enemy",
                    },
                ],
                "should_call_tools": True,
                "abstain_reason": "",
                "final_answer_recommendation": "call:modify_contact_for_each_selected_contact",
            },
            held_out=True,
        ),
        ToolExample(
            {"user_request": "Make my self my enemy"},
            {
                "phase": "abstain",
                "source_relationship": "self",
                "target_relationship": "enemy",
                "search_contacts_kwargs": {},
                "should_call_search_contacts": False,
                "selected_contacts": [],
                "downstream_tool_name": "",
                "downstream_tool_kwargs_list": [],
                "should_call_tools": False,
                "abstain_reason": "unsafe_self_relationship_update",
                "final_answer_recommendation": "abstain:unsafe_self_relationship_update",
            },
            negative_applicability=True,
        ),
    )
    validation = validate_generated_tool(tool, examples)
    if not validation.accepted:
        raise RuntimeError(
            f"{tool.spec.tool_name} validation failed: {validation.errors}"
        )
    return RegistryEntry.accepted(
        tool=tool,
        validation=validation,
        birth_scenario="gap_closure_lab_contact_relationship_update_repair",
    ).to_json()


def main() -> None:
    selector_manifest = cast(
        dict[str, Any], json.loads(SELECTOR_SOURCE.read_text(encoding="utf-8"))
    )
    tools = {
        SELECTOR_NAME: selector_manifest["tools"][SELECTOR_NAME],
        "plan_contact_relationship_batch_update": _relationship_entry(),
    }
    registry_sha = _write_json(OUT, {"tools": tools})
    summary_sha = _write_json(
        SUMMARY,
        {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "experimental_only": True,
            "source_registry": str(SELECTOR_SOURCE),
            "output_registry": str(OUT),
            "registry_sha256": registry_sha,
            "tool_names": sorted(tools),
            "rationale": (
                "Combine only the retained message-recency selector with a narrow "
                "relationship-bulk planner; avoid exposing unrelated timestamp, "
                "state, send, or broad contact planners on Contact CRUD."
            ),
            "leakage_control": (
                "The new helper uses only visible relationship labels and visible "
                "contact records. It does not encode scenario ids, expected answers, "
                "truth labels, or hidden benchmark facts."
            ),
        },
    )
    print(
        json.dumps(
            {
                "registry": str(OUT),
                "registry_sha256": registry_sha,
                "summary_sha256": summary_sha,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
