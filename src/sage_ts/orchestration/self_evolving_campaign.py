"""Self-evolving SAGE mini-campaign preparation.

This module wires together the first autonomous loop from
``praxis_next_gap_and_self_evolving_sage_plan.md``:

1. observe ranked gaps,
2. select a high-opportunity bucket,
3. synthesize a safe deterministic helper,
4. validate it with source, held-out, and negative examples,
5. write a capped <=60 task manifest for a natural-adoption run.

It intentionally keeps the initial implementation narrow and auditable.  The
generated helper template is derived from the bucket specification, not hidden
labels or scenario-specific expected answers.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sage_ts.evaluation.gap_observer import GapBucket, load_gap_buckets
from sage_ts.generation.tool_spec import (
    GeneratedTool,
    StructuredInadequacyEvidence,
    ToolFamily,
    ToolInput,
    ToolSpec,
)
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.registry.store import RegistryStore
from sage_ts.validation.sandbox_validator import ToolExample, validate_generated_tool

MINI_MODEL = "gpt-4o-mini"
MAX_SELF_EVOLVING_SAMPLES = 60


@dataclass(frozen=True)
class SelfEvolvingCampaignConfig:
    source_gap_packet: Path
    source_manifest: Path
    output_root: Path
    max_samples: int = MAX_SELF_EVOLVING_SAMPLES
    agent_model: str = MINI_MODEL
    user_model: str = MINI_MODEL
    generation_model: str = MINI_MODEL
    split_name: str = "transfer_60"
    bucket_hint: str = "contact_lookup_update_search_crud"
    tool_strategy: str = "contact_action_v2"
    recipe_registry: Path | None = None


@dataclass(frozen=True)
class PreparedSelfEvolvingCampaign:
    registry_dir: Path
    manifest_path: Path
    summary_path: Path
    registry_hash: str
    manifest_hash: str
    generated_tool_names: tuple[str, ...]
    selected_bucket: str
    selected_scenario_count: int

    def to_json(self) -> dict[str, Any]:
        return {
            "registry_dir": str(self.registry_dir),
            "manifest_path": str(self.manifest_path),
            "summary_path": str(self.summary_path),
            "registry_hash": self.registry_hash,
            "manifest_hash": self.manifest_hash,
            "generated_tool_names": list(self.generated_tool_names),
            "selected_bucket": self.selected_bucket,
            "selected_scenario_count": self.selected_scenario_count,
        }


def enforce_mini_model_policy(
    *,
    max_samples: int,
    agent_model: str,
    user_model: str,
    generation_model: str,
) -> None:
    if max_samples > MAX_SELF_EVOLVING_SAMPLES:
        raise ValueError(
            f"self_evolving_sample_cap_exceeded:{max_samples}>"
            f"{MAX_SELF_EVOLVING_SAMPLES}"
        )
    models = {
        "agent_model": agent_model,
        "user_model": user_model,
        "generation_model": generation_model,
    }
    non_mini = {key: value for key, value in models.items() if value != MINI_MODEL}
    if non_mini:
        raise ValueError(f"non_mini_model_requested:{non_mini}")


def prepare_self_evolving_campaign(
    config: SelfEvolvingCampaignConfig,
) -> PreparedSelfEvolvingCampaign:
    enforce_mini_model_policy(
        max_samples=config.max_samples,
        agent_model=config.agent_model,
        user_model=config.user_model,
        generation_model=config.generation_model,
    )
    config.output_root.mkdir(parents=True, exist_ok=True)
    selected_bucket = _select_bucket(
        load_gap_buckets(config.source_gap_packet), config.bucket_hint
    )
    registry_dir = config.output_root / "registry"
    manifest_path = config.output_root / "self_evolving_mini60_manifest.json"
    summary_path = config.output_root / "self_evolving_mini60_preparation.json"

    _write_empty_registry(registry_dir)
    starting_registry_hash = _sha256(registry_dir / "registry_manifest.json")

    generated_entries = _build_generated_entries(config, selected_bucket)
    store = RegistryStore(registry_dir)
    for entry in generated_entries:
        store.put(entry)
    selected_scenarios = _write_capped_manifest(
        source_manifest=config.source_manifest,
        output_path=manifest_path,
        split_name=config.split_name,
        bucket=selected_bucket,
        max_samples=config.max_samples,
    )
    registry_hash = _sha256(registry_dir / "registry_manifest.json")
    manifest_hash = _sha256(manifest_path)
    summary = {
        "artifact_type": "self_evolving_sage_mini60_preparation",
        "labels_inspected": False,
        "final_claim_evidence": False,
        "source_gap_packet": str(config.source_gap_packet),
        "source_manifest": str(config.source_manifest),
        "selected_bucket": selected_bucket.to_json(),
        "starting_registry_tool_count": 0,
        "starting_registry_hash": starting_registry_hash,
        "tool_strategy": config.tool_strategy,
        "recipe_registry": str(config.recipe_registry)
        if config.recipe_registry
        else None,
        "generated_tool_count": len(generated_entries),
        "generated_tool_names": [
            entry.tool.spec.tool_name for entry in generated_entries
        ],
        "generated_tool_specs": [
            entry.tool.spec.to_json() for entry in generated_entries
        ],
        "validation": [
            {
                "tool_name": entry.tool.spec.tool_name,
                "accepted": entry.validation.accepted,
                "errors": list(entry.validation.errors),
                "source_example_count": entry.validation.source_example_count,
                "held_out_check_count": entry.validation.held_out_check_count,
                "negative_applicability_count": (
                    entry.validation.negative_applicability_count
                ),
                "runtime_smoke_passed": entry.validation.runtime_smoke_passed,
            }
            for entry in generated_entries
        ],
        "registry_dir": str(registry_dir),
        "registry_hash": registry_hash,
        "manifest_path": str(manifest_path),
        "manifest_hash": manifest_hash,
        "split_name": config.split_name,
        "selected_scenario_count": len(selected_scenarios),
        "sample_cap": MAX_SELF_EVOLVING_SAMPLES,
        "model_policy": {
            "agent_model": config.agent_model,
            "user_model": config.user_model,
            "generation_model": config.generation_model,
            "all_models_forced_to": MINI_MODEL,
        },
        "cache_policy_for_run": {
            "control_cache": "use-if-eligible",
            "candidate_task_cache": "off",
            "openai_response_cache": "disabled",
            "routing_evidence_mode": "disabled",
        },
        "integrity_controls": {
            "scenario_ids_encoded_in_tool": False,
            "labels_or_expected_answers_used": False,
            "force_call_allowed": False,
            "generated_helper_side_effects": False,
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    _write_sha256_sidecar(summary_path)
    _write_sha256_sidecar(manifest_path)
    _write_sha256_sidecar(registry_dir / "registry_manifest.json")
    return PreparedSelfEvolvingCampaign(
        registry_dir=registry_dir,
        manifest_path=manifest_path,
        summary_path=summary_path,
        registry_hash=registry_hash,
        manifest_hash=manifest_hash,
        generated_tool_names=tuple(
            entry.tool.spec.tool_name for entry in generated_entries
        ),
        selected_bucket=selected_bucket.bucket,
        selected_scenario_count=len(selected_scenarios),
    )


def _build_generated_entries(
    config: SelfEvolvingCampaignConfig,
    selected_bucket: GapBucket,
) -> tuple[RegistryEntry, ...]:
    if config.tool_strategy == "contact_action_v2":
        tool = build_contact_lookup_or_update_action_tool(selected_bucket)
        validation = validate_generated_tool(
            tool, _contact_action_validation_examples()
        )
        if not validation.accepted:
            raise ValueError(
                "generated_tool_validation_failed:" + ",".join(validation.errors)
            )
        return (
            RegistryEntry.accepted(
                tool,
                validation,
                birth_scenario=f"self_evolving_gap_bucket:{selected_bucket.bucket}",
            ),
        )
    if config.tool_strategy == "praxis_contact_bridgepack":
        return _materialize_recipe_entries(
            config.recipe_registry,
            CONTACT_BRIDGEPACK_RECIPE_TOOLS,
            selected_bucket=selected_bucket,
        )
    if config.tool_strategy == "praxis_current_pack":
        return _materialize_recipe_entries(
            config.recipe_registry,
            PRAXIS_CURRENT_RECIPE_TOOLS,
            selected_bucket=selected_bucket,
        )
    raise ValueError(f"unknown_tool_strategy:{config.tool_strategy}")


CONTACT_BRIDGEPACK_RECIPE_TOOLS = (
    "plan_contact_lookup_query",
    "plan_contact_search_from_scalar_constraint",
    "plan_contact_relationship_batch_update",
    "plan_send_message_contact_lookup",
    "select_message_content_by_recency",
    "select_message_counterparty_for_contact_update",
)

PRAXIS_CURRENT_RECIPE_TOOLS = (
    "days_between_timestamps",
    "next_weekday_time_to_timestamp",
    "plan_contact_lookup_query",
    "plan_contact_relationship_batch_update",
    "plan_contact_search_from_scalar_constraint",
    "plan_device_state_action_sequence_v3",
    "plan_send_message_contact_lookup",
    "relative_day_time_to_timestamp",
    "relative_weeks_time_to_timestamp",
    "resolve_search_window_or_bounds",
    "select_message_content_by_recency",
    "select_message_counterparty_for_contact_update",
    "select_record_by_timestamp_extreme",
)


def _materialize_recipe_entries(
    recipe_registry: Path | None,
    tool_names: tuple[str, ...],
    *,
    selected_bucket: GapBucket,
) -> tuple[RegistryEntry, ...]:
    if recipe_registry is None:
        raise ValueError("recipe_registry_required_for_recipe_pack_strategy")
    entries = RegistryStore(recipe_registry).load_entries()
    missing = [name for name in tool_names if name not in entries]
    if missing:
        raise ValueError("recipe_tools_missing:" + ",".join(missing))
    materialized: list[RegistryEntry] = []
    accepted_at = datetime.now(timezone.utc).isoformat()
    for name in tool_names:
        entry = entries[name]
        if not entry.validation.accepted or entry.retired:
            raise ValueError(f"recipe_tool_not_active:{name}")
        materialized.append(
            replace(
                entry,
                birth_scenario=f"self_evolving_recipe:{selected_bucket.bucket}",
                accepted_at=accepted_at,
                reuse_count=0,
                success_flips=0,
                retired=False,
                version=1,
            )
        )
    return tuple(materialized)


def _select_bucket(buckets: tuple[GapBucket, ...], bucket_hint: str) -> GapBucket:
    for bucket in buckets:
        if bucket.bucket == bucket_hint:
            return bucket
    if not buckets:
        raise ValueError("no_gap_buckets_found")
    return buckets[0]


def _write_empty_registry(registry_dir: Path) -> None:
    registry_dir.mkdir(parents=True, exist_ok=True)
    (registry_dir / "registry_manifest.json").write_text(
        json.dumps({"tools": {}}, indent=2) + "\n", encoding="utf-8"
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_sha256_sidecar(path: Path) -> Path:
    sidecar = path.with_suffix(path.suffix + ".sha256")
    sidecar.write_text(f"{_sha256(path)}  {path}\n", encoding="utf-8")
    return sidecar


def _write_capped_manifest(
    *,
    source_manifest: Path,
    output_path: Path,
    split_name: str,
    bucket: GapBucket,
    max_samples: int,
) -> tuple[str, ...]:
    source = json.loads(source_manifest.read_text(encoding="utf-8"))
    source_records = source.get("splits", {}).get("full_benchmark", [])
    records_by_name = {
        str(record["name"]): record for record in source_records if "name" in record
    }
    priority_names = [scenario.scenario for scenario in bucket.top_scenarios]
    contact_tokens = (
        "search_phone_number_with_name",
        "search_name_with_relationship",
        "search_relationship_with_phone_number",
        "search_sender_phone_number_with_content",
        "update_contact_with_id_and_phone_number",
        "update_contact_relationship_with_relationship",
        "modify_contact_with_message_recency",
        "remove_contact_by_phone",
        "send_message_with_contact_content",
    )
    selected: list[str] = []
    for name in priority_names:
        if name in records_by_name and name not in selected:
            selected.append(name)
    for name in records_by_name:
        lowered = name.lower()
        if any(token in lowered for token in contact_tokens) and name not in selected:
            selected.append(name)
        if len(selected) >= max_samples:
            break
    selected = selected[:max_samples]
    output = {
        "manifest_type": "self_evolving_sage_contact_gap_mini60_experimental",
        "final_claim_evidence": False,
        "labels_inspected": False,
        "cache_selection_used": False,
        "selection_rule": (
            "Autonomous gap observer selected the highest outcome-regression "
            "bucket, then built a <=60 contact lookup/update/search mini split "
            "from the formal manifest without using labels or expected answers."
        ),
        "source_manifest": str(source_manifest),
        "selected_bucket": bucket.bucket,
        "sample_cap": MAX_SELF_EVOLVING_SAMPLES,
        "splits": {split_name: [records_by_name[name] for name in selected]},
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    return tuple(selected)


def build_contact_lookup_or_update_action_tool(bucket: GapBucket) -> GeneratedTool:
    return GeneratedTool(
        spec=_contact_lookup_or_update_action_spec(bucket),
        code=CONTACT_LOOKUP_OR_UPDATE_ACTION_CODE,
    )


def _contact_lookup_or_update_action_spec(bucket: GapBucket) -> ToolSpec:
    return ToolSpec(
        tool_name="prepare_contact_lookup_or_update_action_v2",
        family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        description=(
            "Prepare a final-answer-ready contact lookup, contact update, removal, "
            "or relationship-batch action from scalar constraints and optional "
            "visible contact records. Use for contact name/phone/relationship "
            "lookup tasks and contact CRUD tasks. It never mutates state; it only "
            "returns the original ToolSandbox search_contacts, modify_contact, "
            "remove_contact, or send_message_with_phone_number call that must be "
            "made next, or a final answer when a unique visible record is enough."
        ),
        inputs=(
            ToolInput(
                "operation",
                "str",
                "lookup, update_phone, update_relationship, remove, relationship_batch_update, or send_message.",
            ),
            ToolInput(
                "lookup_field",
                "str",
                "Scalar lookup field: name, phone_number, relationship, or person_id.",
            ),
            ToolInput(
                "lookup_value",
                "str",
                "Scalar lookup value supplied by the user or prior visible state.",
            ),
            ToolInput(
                "requested_field",
                "str",
                "For lookup tasks, the contact field to answer with.",
            ),
            ToolInput("target_name", "str", "Optional contact display name."),
            ToolInput("target_phone_number", "str", "Optional target phone number."),
            ToolInput("relationship", "str", "Optional current/source relationship."),
            ToolInput(
                "new_phone_number", "str", "Optional new phone number for update_phone."
            ),
            ToolInput(
                "new_relationship",
                "str",
                "Optional target relationship for update_relationship or batch update.",
            ),
            ToolInput(
                "person_id",
                "str",
                "Optional stable contact person_id when already visible.",
            ),
            ToolInput(
                "message_content",
                "str",
                "Optional message content for send-message preparation.",
            ),
            ToolInput("contacts", "list", "Optional visible search_contacts records."),
            ToolInput(
                "allow_ambiguous",
                "bool",
                "Whether to allow more than one matched contact. Normally false.",
            ),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "phase": {"type": "string"},
                "operation": {"type": "string"},
                "should_call_search_contacts": {"type": "boolean"},
                "search_contacts_kwargs": {"type": "object"},
                "selected_contact_id": {"type": "string"},
                "selected_display_name": {"type": "string"},
                "selected_phone_number": {"type": "string"},
                "selected_relationship": {"type": "string"},
                "selected_value": {},
                "requested_field": {"type": "string"},
                "downstream_tool_name": {"type": "string"},
                "downstream_tool_kwargs": {"type": "object"},
                "downstream_tool_kwargs_list": {"type": "array"},
                "should_call_tool": {"type": "boolean"},
                "should_call_tools": {"type": "boolean"},
                "required_original_tool": {"type": "string"},
                "required_original_arguments": {"type": "object"},
                "final_answer": {"type": "string"},
                "final_answer_recommendation": {"type": "string"},
                "abstain_reason": {"type": "string"},
                "safety_notes": {"type": "string"},
                "tie_candidates": {"type": "array"},
            },
        },
        positive_triggers=(
            "search_phone_number_with_name",
            "search_name_with_relationship",
            "search_relationship_with_phone_number",
            "search_sender_phone_number_with_content",
            "update_contact_with_id_and_phone_number",
            "update_contact_relationship_with_relationship",
            "modify_contact_with_message_recency",
            "remove_contact_by_phone",
            "send_message_with_contact_content",
            "contact lookup",
            "contact update",
            "relationship batch update",
        ),
        negative_triggers=(
            "reminder",
            "holiday",
            "weather",
            "stock",
            "distance",
            "wifi",
            "location_service",
            "no contact constraint",
            "ambiguous contacts",
            "missing update value",
        ),
        preserves_side_effect_tools=(
            "search_contacts",
            "modify_contact",
            "remove_contact",
            "send_message_with_phone_number",
        ),
        required_original_tool_calls=(
            "search_contacts",
            "modify_contact",
            "remove_contact",
            "send_message_with_phone_number",
        ),
        abstain_behavior=(
            "Abstain with a concrete reason when the lookup constraint, requested "
            "field, update value, message content, or unique target contact is "
            "missing; abstain on duplicate matches unless allow_ambiguous is true."
        ),
        generalization_rationale=(
            "Contact lookup, contact update, relationship batch update, and "
            "send-message precondition tasks repeatedly require the same safe "
            "bridge from scalar user constraints to original contact search/action "
            "calls. The helper is generic over visible contact records and scalar "
            "fields and contains no scenario IDs or expected answers."
        ),
        estimated_step_compression=4,
        cross_task_applicability_count=max(bucket.scenario_count, 2),
        applicable_task_families=(
            "search_phone_number_with_name",
            "search_name_with_relationship",
            "update_contact_with_id_and_phone_number",
            "update_contact_relationship_with_relationship",
            "remove_contact_by_phone",
            "send_message_with_contact_content",
        ),
        reason_tool_is_decisive=(
            "It produces either the final answer from a unique visible contact or "
            "the exact original ToolSandbox action arguments that must be called "
            "next, which repairs intermediate-only contact helpers."
        ),
        diagnostic_only=False,
        shortfall_cluster_evidence=(bucket.bucket,),
        known_failure_mechanisms_addressed=(
            "contact_lookup_visible_not_called",
            "contact_helper_intermediate_only_output",
            "relationship_update_requires_batch_action_spec",
            "missing_final_answer_ready_contact_value",
        ),
        canonical_route_substitution_risk="low",
        expected_milestone_calls_replaced=(),
        final_state_preservation_plan=(
            "The helper is side-effect-free and explicitly returns the original "
            "ToolSandbox call and arguments. The actor must still call "
            "search_contacts, modify_contact, remove_contact, or "
            "send_message_with_phone_number when should_call_* is true."
        ),
        grading_accounting_note=(
            "Outcome/task completion remains primary. Canonical/reference route "
            "effects are secondary and reported separately."
        ),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary=(
                "Formal500 gap observation ranked contact lookup/update/search CRUD "
                "as the largest residual outcome-regression bucket with many no "
                "visible/no called helper cases."
            ),
            signals=(
                "largest_residual_contact_bucket",
                "no_visible_helper",
                "visible_not_called",
                "intermediate_only_contact_output",
            ),
            failed_tool_calls=(),
            repeated_failed_tool_calls=(),
            visible_data_gaps=("missing_final_answer_ready_contact_action_spec",),
            planner_failures=("contact_lookup_or_update_action_not_normalized",),
            final_answer_route_mismatch=True,
        ),
    )


CONTACT_LOOKUP_OR_UPDATE_ACTION_CODE = """def prepare_contact_lookup_or_update_action_v2(operation: str, lookup_field: str = "", lookup_value: str = "", requested_field: str = "", target_name: str = "", target_phone_number: str = "", relationship: str = "", new_phone_number: str = "", new_relationship: str = "", person_id: str = "", message_content: str = "", contacts: list = None, allow_ambiguous: bool = False) -> dict:
    contacts = contacts if isinstance(contacts, list) else []

    def clean(value):
        return " ".join(str(value or "").strip().split())

    def lower(value):
        return clean(value).lower().replace("-", "_").replace(" ", "_")

    def normalize_phone(value):
        raw = clean(value)
        if not raw:
            return ""
        keep_plus = raw.startswith("+")
        digits = "".join(ch for ch in raw if ch.isdigit())
        if not digits:
            return ""
        if keep_plus:
            return "+" + digits
        if len(digits) == 10:
            return "+1" + digits
        if len(digits) == 11 and digits.startswith("1"):
            return "+" + digits
        return "+" + digits

    def normalize_relationship(value):
        raw = lower(value)
        aliases = {
            "friends": "friend",
            "friend": "friend",
            "enemies": "enemy",
            "enemy": "enemy",
            "coworkers": "coworker",
            "coworker": "coworker",
            "colleagues": "coworker",
            "colleague": "coworker",
            "family": "family",
            "relatives": "family",
            "relative": "family",
            "self": "self",
        }
        return aliases.get(raw, raw)

    def empty(reason):
        return {
            "status": "abstain",
            "phase": "abstain",
            "operation": lower(operation),
            "should_call_search_contacts": False,
            "search_contacts_kwargs": {},
            "selected_contact_id": "",
            "selected_display_name": "",
            "selected_phone_number": "",
            "selected_relationship": "",
            "selected_value": "",
            "requested_field": clean(requested_field),
            "downstream_tool_name": "",
            "downstream_tool_kwargs": {},
            "downstream_tool_kwargs_list": [],
            "should_call_tool": False,
            "should_call_tools": False,
            "required_original_tool": "",
            "required_original_arguments": {},
            "final_answer": "",
            "final_answer_recommendation": "abstain:" + str(reason or "insufficient_information"),
            "abstain_reason": str(reason or "insufficient_information"),
            "safety_notes": "no state change prepared",
            "tie_candidates": [],
        }

    op = lower(operation) or "lookup"
    field = lower(lookup_field)
    value = clean(lookup_value)
    req = lower(requested_field)
    name = clean(target_name)
    phone = normalize_phone(target_phone_number)
    source_rel = normalize_relationship(relationship)
    target_rel = normalize_relationship(new_relationship)
    new_phone = normalize_phone(new_phone_number)
    pid = clean(person_id)
    content = clean(message_content)

    if not field:
        if name:
            field = "name"
            value = name
        elif phone:
            field = "phone_number"
            value = phone
        elif source_rel:
            field = "relationship"
            value = source_rel
        elif pid:
            field = "person_id"
            value = pid

    if field == "phone":
        field = "phone_number"
    if field == "id":
        field = "person_id"
    if field == "relationship":
        value = normalize_relationship(value)
    if field == "phone_number":
        value = normalize_phone(value)
    if field == "name":
        value = clean(value)

    supported_fields = ("name", "phone_number", "relationship", "person_id")
    if field and field not in supported_fields:
        return empty("unsupported_lookup_field")

    search_kwargs = {}
    if field in ("name", "phone_number", "relationship") and value:
        search_kwargs[field] = value

    def contact_value(contact, key):
        if not isinstance(contact, dict):
            return ""
        raw = contact.get(key)
        if key == "relationship":
            return normalize_relationship(raw)
        if key == "phone_number":
            return normalize_phone(raw)
        return clean(raw)

    matches = []
    if contacts:
        for contact in contacts:
            if not isinstance(contact, dict):
                continue
            if field and value:
                current = contact_value(contact, field)
                expected = normalize_phone(value) if field == "phone_number" else (normalize_relationship(value) if field == "relationship" else clean(value))
                if field == "name":
                    if current.lower() != expected.lower():
                        continue
                elif current != expected:
                    continue
            matches.append(contact)

    def selected_payload(contact):
        selected_id = contact_value(contact, "person_id") or contact_value(contact, "id")
        selected_name = contact_value(contact, "name")
        selected_phone = contact_value(contact, "phone_number")
        selected_rel = contact_value(contact, "relationship")
        selected_value = ""
        if req:
            selected_value = contact_value(contact, req)
        return selected_id, selected_name, selected_phone, selected_rel, selected_value

    if op in ("relationship_batch_update", "update_relationship_batch", "batch_relationship_update"):
        if not source_rel:
            return empty("missing_source_relationship")
        if not target_rel:
            return empty("missing_target_relationship")
        if source_rel == target_rel:
            return empty("source_relationship_already_target")
        if not contacts:
            return {
                "status": "search_required",
                "phase": "search_required",
                "operation": "relationship_batch_update",
                "should_call_search_contacts": True,
                "search_contacts_kwargs": {"relationship": source_rel},
                "selected_contact_id": "",
                "selected_display_name": "",
                "selected_phone_number": "",
                "selected_relationship": source_rel,
                "selected_value": "",
                "requested_field": "",
                "downstream_tool_name": "",
                "downstream_tool_kwargs": {},
                "downstream_tool_kwargs_list": [],
                "should_call_tool": False,
                "should_call_tools": False,
                "required_original_tool": "search_contacts",
                "required_original_arguments": {"relationship": source_rel},
                "final_answer": "",
                "final_answer_recommendation": "call:search_contacts",
                "abstain_reason": "",
                "safety_notes": "search contacts before relationship batch update",
                "tie_candidates": [],
            }
        batch = []
        selected_contacts = []
        for contact in contacts:
            if not isinstance(contact, dict) or bool(contact.get("is_self")):
                continue
            if contact_value(contact, "relationship") != source_rel:
                continue
            selected_id = contact_value(contact, "person_id")
            if selected_id:
                batch.append({"person_id": selected_id, "relationship": target_rel})
                selected_contacts.append(contact)
        if not batch:
            return empty("no_matching_contacts_for_relationship_update")
        return {
            "status": "action_ready",
            "phase": "action_batch_ready",
            "operation": "relationship_batch_update",
            "should_call_search_contacts": False,
            "search_contacts_kwargs": {"relationship": source_rel},
            "selected_contact_id": "",
            "selected_display_name": "",
            "selected_phone_number": "",
            "selected_relationship": source_rel,
            "selected_value": "",
            "requested_field": "",
            "downstream_tool_name": "modify_contact",
            "downstream_tool_kwargs": {},
            "downstream_tool_kwargs_list": batch,
            "should_call_tool": False,
            "should_call_tools": True,
            "required_original_tool": "modify_contact",
            "required_original_arguments": {},
            "final_answer": "",
            "final_answer_recommendation": "call:modify_contact_for_each_downstream_tool_kwargs_list_item",
            "abstain_reason": "",
            "safety_notes": "call original modify_contact once per prepared batch item",
            "tie_candidates": selected_contacts,
        }

    if op in ("send", "send_message", "message"):
        if not content:
            return empty("missing_message_content")
        if not contacts and search_kwargs:
            return {
                "status": "search_required",
                "phase": "search_required",
                "operation": "send_message",
                "should_call_search_contacts": True,
                "search_contacts_kwargs": search_kwargs,
                "selected_contact_id": "",
                "selected_display_name": "",
                "selected_phone_number": "",
                "selected_relationship": "",
                "selected_value": "",
                "requested_field": "phone_number",
                "downstream_tool_name": "",
                "downstream_tool_kwargs": {},
                "downstream_tool_kwargs_list": [],
                "should_call_tool": False,
                "should_call_tools": False,
                "required_original_tool": "search_contacts",
                "required_original_arguments": search_kwargs,
                "final_answer": "",
                "final_answer_recommendation": "call:search_contacts_then_send_message_with_phone_number",
                "abstain_reason": "",
                "safety_notes": "search contact before sending",
                "tie_candidates": [],
            }
        req = "phone_number"

    if not contacts:
        if op in ("lookup", "search", "answer", "find"):
            if not req:
                return empty("missing_requested_field")
            if not search_kwargs:
                return empty("missing_lookup_constraint")
            return {
                "status": "search_required",
                "phase": "search_required",
                "operation": "lookup",
                "should_call_search_contacts": True,
                "search_contacts_kwargs": search_kwargs,
                "selected_contact_id": "",
                "selected_display_name": "",
                "selected_phone_number": "",
                "selected_relationship": "",
                "selected_value": "",
                "requested_field": req,
                "downstream_tool_name": "",
                "downstream_tool_kwargs": {},
                "downstream_tool_kwargs_list": [],
                "should_call_tool": False,
                "should_call_tools": False,
                "required_original_tool": "search_contacts",
                "required_original_arguments": search_kwargs,
                "final_answer": "",
                "final_answer_recommendation": "call:search_contacts_then_answer_" + req,
                "abstain_reason": "",
                "safety_notes": "preserve original search_contacts call",
                "tie_candidates": [],
            }
        if op in ("update_phone", "modify_phone"):
            if not pid:
                return empty("missing_person_id")
            if not new_phone:
                return empty("missing_new_phone_number")
            kwargs = {"person_id": pid, "phone_number": new_phone}
            return {
                "status": "action_ready",
                "phase": "action_ready",
                "operation": "update_phone",
                "should_call_search_contacts": False,
                "search_contacts_kwargs": {},
                "selected_contact_id": pid,
                "selected_display_name": "",
                "selected_phone_number": new_phone,
                "selected_relationship": "",
                "selected_value": new_phone,
                "requested_field": "phone_number",
                "downstream_tool_name": "modify_contact",
                "downstream_tool_kwargs": kwargs,
                "downstream_tool_kwargs_list": [kwargs],
                "should_call_tool": True,
                "should_call_tools": True,
                "required_original_tool": "modify_contact",
                "required_original_arguments": kwargs,
                "final_answer": "",
                "final_answer_recommendation": "call:modify_contact",
                "abstain_reason": "",
                "safety_notes": "call original modify_contact with prepared kwargs",
                "tie_candidates": [],
            }
        if search_kwargs:
            return {
                "status": "search_required",
                "phase": "search_required",
                "operation": op,
                "should_call_search_contacts": True,
                "search_contacts_kwargs": search_kwargs,
                "selected_contact_id": "",
                "selected_display_name": "",
                "selected_phone_number": "",
                "selected_relationship": "",
                "selected_value": "",
                "requested_field": req,
                "downstream_tool_name": "",
                "downstream_tool_kwargs": {},
                "downstream_tool_kwargs_list": [],
                "should_call_tool": False,
                "should_call_tools": False,
                "required_original_tool": "search_contacts",
                "required_original_arguments": search_kwargs,
                "final_answer": "",
                "final_answer_recommendation": "call:search_contacts_then_prepare_action",
                "abstain_reason": "",
                "safety_notes": "search before contact action",
                "tie_candidates": [],
            }
        return empty("missing_contact_constraint")

    if not matches:
        return empty("no_matching_contact")
    if len(matches) != 1 and not bool(allow_ambiguous):
        result = empty("ambiguous_contacts")
        result["tie_candidates"] = matches
        return result
    contact = matches[0]
    selected_id, selected_name, selected_phone, selected_rel, selected_value = selected_payload(contact)

    if op in ("lookup", "search", "answer", "find"):
        if not req:
            return empty("missing_requested_field")
        if not selected_value:
            return empty("missing_requested_field_value")
        return {
            "status": "answer_ready",
            "phase": "answer_ready",
            "operation": "lookup",
            "should_call_search_contacts": False,
            "search_contacts_kwargs": search_kwargs,
            "selected_contact_id": selected_id,
            "selected_display_name": selected_name,
            "selected_phone_number": selected_phone,
            "selected_relationship": selected_rel,
            "selected_value": selected_value,
            "requested_field": req,
            "downstream_tool_name": "",
            "downstream_tool_kwargs": {},
            "downstream_tool_kwargs_list": [],
            "should_call_tool": False,
            "should_call_tools": False,
            "required_original_tool": "",
            "required_original_arguments": {},
            "final_answer": str(selected_value),
            "final_answer_recommendation": str(selected_value),
            "abstain_reason": "",
            "safety_notes": "answer from one visible contact record",
            "tie_candidates": [],
        }

    if op in ("update_phone", "modify_phone"):
        if not selected_id:
            return empty("missing_person_id")
        if not new_phone:
            return empty("missing_new_phone_number")
        kwargs = {"person_id": selected_id, "phone_number": new_phone}
        return {
            "status": "action_ready",
            "phase": "action_ready",
            "operation": "update_phone",
            "should_call_search_contacts": False,
            "search_contacts_kwargs": search_kwargs,
            "selected_contact_id": selected_id,
            "selected_display_name": selected_name,
            "selected_phone_number": selected_phone,
            "selected_relationship": selected_rel,
            "selected_value": new_phone,
            "requested_field": "phone_number",
            "downstream_tool_name": "modify_contact",
            "downstream_tool_kwargs": kwargs,
            "downstream_tool_kwargs_list": [kwargs],
            "should_call_tool": True,
            "should_call_tools": True,
            "required_original_tool": "modify_contact",
            "required_original_arguments": kwargs,
            "final_answer": "",
            "final_answer_recommendation": "call:modify_contact",
            "abstain_reason": "",
            "safety_notes": "call original modify_contact with prepared kwargs",
            "tie_candidates": [],
        }

    if op in ("remove", "remove_contact", "delete"):
        if not selected_id:
            return empty("missing_person_id")
        kwargs = {"person_id": selected_id}
        return {
            "status": "action_ready",
            "phase": "action_ready",
            "operation": "remove_contact",
            "should_call_search_contacts": False,
            "search_contacts_kwargs": search_kwargs,
            "selected_contact_id": selected_id,
            "selected_display_name": selected_name,
            "selected_phone_number": selected_phone,
            "selected_relationship": selected_rel,
            "selected_value": selected_id,
            "requested_field": "person_id",
            "downstream_tool_name": "remove_contact",
            "downstream_tool_kwargs": kwargs,
            "downstream_tool_kwargs_list": [kwargs],
            "should_call_tool": True,
            "should_call_tools": True,
            "required_original_tool": "remove_contact",
            "required_original_arguments": kwargs,
            "final_answer": "",
            "final_answer_recommendation": "call:remove_contact",
            "abstain_reason": "",
            "safety_notes": "call original remove_contact with prepared kwargs",
            "tie_candidates": [],
        }

    if op in ("send", "send_message", "message"):
        if not selected_phone:
            return empty("missing_selected_phone_number")
        if not content:
            return empty("missing_message_content")
        kwargs = {"phone_number": selected_phone, "content": content}
        return {
            "status": "action_ready",
            "phase": "action_ready",
            "operation": "send_message",
            "should_call_search_contacts": False,
            "search_contacts_kwargs": search_kwargs,
            "selected_contact_id": selected_id,
            "selected_display_name": selected_name,
            "selected_phone_number": selected_phone,
            "selected_relationship": selected_rel,
            "selected_value": selected_phone,
            "requested_field": "phone_number",
            "downstream_tool_name": "send_message_with_phone_number",
            "downstream_tool_kwargs": kwargs,
            "downstream_tool_kwargs_list": [kwargs],
            "should_call_tool": True,
            "should_call_tools": True,
            "required_original_tool": "send_message_with_phone_number",
            "required_original_arguments": kwargs,
            "final_answer": "",
            "final_answer_recommendation": "call:send_message_with_phone_number",
            "abstain_reason": "",
            "safety_notes": "call original send_message_with_phone_number with prepared kwargs",
            "tie_candidates": [],
        }

    return empty("unsupported_operation")
"""


def _contact_action_validation_examples() -> tuple[ToolExample, ...]:
    return (
        ToolExample(
            inputs={
                "operation": "lookup",
                "lookup_field": "name",
                "lookup_value": "Alice Smith",
                "requested_field": "phone_number",
                "contacts": [],
            },
            expected={
                "status": "search_required",
                "phase": "search_required",
                "operation": "lookup",
                "should_call_search_contacts": True,
                "search_contacts_kwargs": {"name": "Alice Smith"},
                "selected_contact_id": "",
                "selected_display_name": "",
                "selected_phone_number": "",
                "selected_relationship": "",
                "selected_value": "",
                "requested_field": "phone_number",
                "downstream_tool_name": "",
                "downstream_tool_kwargs": {},
                "downstream_tool_kwargs_list": [],
                "should_call_tool": False,
                "should_call_tools": False,
                "required_original_tool": "search_contacts",
                "required_original_arguments": {"name": "Alice Smith"},
                "final_answer": "",
                "final_answer_recommendation": "call:search_contacts_then_answer_phone_number",
                "abstain_reason": "",
                "safety_notes": "preserve original search_contacts call",
                "tie_candidates": [],
            },
        ),
        ToolExample(
            inputs={
                "operation": "lookup",
                "lookup_field": "name",
                "lookup_value": "Alice Smith",
                "requested_field": "phone_number",
                "contacts": [
                    {
                        "person_id": "person-1",
                        "name": "Alice Smith",
                        "phone_number": "(555) 010-0200",
                        "relationship": "friend",
                    }
                ],
            },
            expected={
                "status": "answer_ready",
                "phase": "answer_ready",
                "operation": "lookup",
                "should_call_search_contacts": False,
                "search_contacts_kwargs": {"name": "Alice Smith"},
                "selected_contact_id": "person-1",
                "selected_display_name": "Alice Smith",
                "selected_phone_number": "+15550100200",
                "selected_relationship": "friend",
                "selected_value": "+15550100200",
                "requested_field": "phone_number",
                "downstream_tool_name": "",
                "downstream_tool_kwargs": {},
                "downstream_tool_kwargs_list": [],
                "should_call_tool": False,
                "should_call_tools": False,
                "required_original_tool": "",
                "required_original_arguments": {},
                "final_answer": "+15550100200",
                "final_answer_recommendation": "+15550100200",
                "abstain_reason": "",
                "safety_notes": "answer from one visible contact record",
                "tie_candidates": [],
            },
            held_out=True,
        ),
        ToolExample(
            inputs={
                "operation": "lookup",
                "lookup_field": "name",
                "lookup_value": "Alice Smith",
                "requested_field": "phone_number",
                "contacts": [
                    {
                        "person_id": "person-1",
                        "name": "Alice Smith",
                        "phone_number": "+15550100200",
                    },
                    {
                        "person_id": "person-2",
                        "name": "Alice Smith",
                        "phone_number": "+15550100300",
                    },
                ],
            },
            expected={
                "status": "abstain",
                "phase": "abstain",
                "operation": "lookup",
                "should_call_search_contacts": False,
                "search_contacts_kwargs": {},
                "selected_contact_id": "",
                "selected_display_name": "",
                "selected_phone_number": "",
                "selected_relationship": "",
                "selected_value": "",
                "requested_field": "phone_number",
                "downstream_tool_name": "",
                "downstream_tool_kwargs": {},
                "downstream_tool_kwargs_list": [],
                "should_call_tool": False,
                "should_call_tools": False,
                "required_original_tool": "",
                "required_original_arguments": {},
                "final_answer": "",
                "final_answer_recommendation": "abstain:ambiguous_contacts",
                "abstain_reason": "ambiguous_contacts",
                "safety_notes": "no state change prepared",
                "tie_candidates": [
                    {
                        "person_id": "person-1",
                        "name": "Alice Smith",
                        "phone_number": "+15550100200",
                    },
                    {
                        "person_id": "person-2",
                        "name": "Alice Smith",
                        "phone_number": "+15550100300",
                    },
                ],
            },
            negative_applicability=True,
        ),
    )
