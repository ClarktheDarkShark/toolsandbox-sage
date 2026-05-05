"""Mechanical promotion gate for candidate-to-active/frozen registry movement."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from sage_ts.registry.manifest import RegistryEntry, has_current_validation_proof
from sage_ts.registry.store import RegistryStore

UNRESOLVED_FAILURE_STATUSES = {"active_failure", "repaired_pending_test"}
MAX_VISIBLE_NOT_CALLED_RATE = 0.5
SIDE_EFFECT_TOOL_PREFIXES = ("add_", "modify_", "remove_", "send_", "set_")


@dataclass(frozen=True)
class PromotionDecision:
    tool_name: str
    allowed: bool
    decision: str
    reasons: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "allowed": self.allowed,
            "decision": self.decision,
            "reasons": list(self.reasons),
        }


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _failure_memory_entries(path: Path | None) -> list[dict[str, Any]]:
    payload = _read_json(path)
    entries = payload.get("entries", [])
    return entries if isinstance(entries, list) else []


def _failure_memory_blocks(
    entry: RegistryEntry,
    contribution: dict[str, Any],
    failure_memory_path: Path | None,
) -> list[str]:
    tool_name = entry.tool.spec.tool_name
    mechanisms = set(entry.tool.spec.known_failure_mechanisms_addressed)
    blocks: list[str] = []
    called_count = int(contribution.get("called_count", 0) or 0)
    called_outcome = contribution.get("called_subset", {}).get("mean_outcome_delta")
    safe_called_evidence = called_count > 0 and (
        called_outcome is None or float(called_outcome) >= 0
    )
    for item in _failure_memory_entries(failure_memory_path):
        status = str(item.get("status", ""))
        candidate_name = str(item.get("candidate_name", ""))
        mechanism_id = str(item.get("mechanism_id", ""))
        applies = candidate_name == tool_name or mechanism_id in mechanisms
        if not applies or status not in UNRESOLVED_FAILURE_STATUSES:
            continue
        if status == "repaired_pending_test" and safe_called_evidence:
            continue
        blocks.append(f"unresolved_failure_memory:{mechanism_id or candidate_name}")
    return blocks


def evaluate_promotion_entry(
    entry: RegistryEntry,
    helper_contribution_summary: dict[str, Any],
    *,
    failure_memory_path: Path | None = None,
    target_lifecycle: str = "active",
) -> PromotionDecision:
    tool_name = entry.tool.spec.tool_name
    spec = entry.tool.spec
    helper_data = helper_contribution_summary.get("helpers", {}).get(tool_name, {})
    reasons: list[str] = []
    if target_lifecycle not in {"candidate", "active", "frozen"}:
        reasons.append("unsupported_target_lifecycle")
    if not has_current_validation_proof(entry):
        reasons.append("validation_proof_missing")
    if spec.diagnostic_only:
        reasons.append("diagnostic_only_without_later_non_diagnostic_evidence")
    if not spec.shortfall_cluster_evidence:
        reasons.append("missing_shortfall_cluster_evidence")
    if not spec.positive_triggers:
        reasons.append("missing_positive_triggers")
    if not spec.negative_triggers:
        reasons.append("missing_negative_triggers")
    if not spec.abstain_behavior.strip():
        reasons.append("missing_safe_abstain_behavior")
    required_side_effects = {
        tool_name
        for tool_name in spec.required_original_tool_calls
        if tool_name.startswith(SIDE_EFFECT_TOOL_PREFIXES)
    }
    if required_side_effects and not required_side_effects.issubset(
        set(spec.preserves_side_effect_tools)
    ):
        reasons.append("missing_downstream_side_effect_preservation")
    called_count = int(helper_data.get("called_count", 0) or 0)
    visible_count = int(helper_data.get("visible_count", 0) or 0)
    visible_not_called_count = int(helper_data.get("visible_not_called_count", 0) or 0)
    if called_count <= 0:
        reasons.append("no_later_task_calls")
    called_outcome = helper_data.get("called_subset", {}).get("mean_outcome_delta")
    if called_outcome is not None and float(called_outcome) < 0:
        reasons.append("negative_called_subset_outcome_delta")
    if visible_count > 0:
        visible_not_called_rate = visible_not_called_count / visible_count
        if visible_not_called_rate > MAX_VISIBLE_NOT_CALLED_RATE:
            reasons.append("visible_not_called_rate_too_high")
    if helper_data.get("side_effect_incidents"):
        reasons.append("side_effect_incidents_present")
    if helper_data.get("runtime_incidents"):
        reasons.append("runtime_incidents_present")
    reasons.extend(_failure_memory_blocks(entry, helper_data, failure_memory_path))
    return PromotionDecision(
        tool_name=tool_name,
        allowed=not reasons,
        decision="promote" if not reasons else "park",
        reasons=tuple(reasons),
    )


def evaluate_registry_promotion(
    registry_manifest_or_dir: Path,
    helper_contribution_summary_path: Path,
    *,
    failure_memory_path: Path | None = None,
    target_lifecycle: str = "active",
) -> dict[str, Any]:
    registry_dir = (
        registry_manifest_or_dir.parent
        if registry_manifest_or_dir.name == "registry_manifest.json"
        else registry_manifest_or_dir
    )
    entries = RegistryStore(registry_dir).load_entries()
    contribution = _read_json(helper_contribution_summary_path)
    decisions = [
        evaluate_promotion_entry(
            entry,
            contribution,
            failure_memory_path=failure_memory_path,
            target_lifecycle=target_lifecycle,
        )
        for entry in entries.values()
    ]
    return {
        "registry": str(registry_manifest_or_dir),
        "helper_contribution_summary": str(helper_contribution_summary_path),
        "failure_memory": str(failure_memory_path) if failure_memory_path else None,
        "target_lifecycle": target_lifecycle,
        "allowed": all(decision.allowed for decision in decisions),
        "decisions": [decision.to_json() for decision in decisions],
    }
