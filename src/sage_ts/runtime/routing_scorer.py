"""Generic runtime routing scores for retained/generated helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from sage_ts.evaluation.task_strata import HELPER_TRIGGERS, classify_task_strata
from sage_ts.experiments.v2_flags import EVIDENCE_ROUTING, feature_enabled
from sage_ts.registry.manifest import RegistryEntry, has_current_validation_proof

DEFAULT_MAX_RUNTIME_BUNDLE_SIZE = 5
ROUTING_EVIDENCE_ROOT = Path("artifacts/summaries")


@dataclass(frozen=True)
class RuntimeRoutingDecision:
    tool_name: str
    visible: bool
    status: str
    reason: str
    score: int
    matched_positive_triggers: tuple[str, ...] = ()
    matched_negative_triggers: tuple[str, ...] = ()
    matched_task_families: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "visible": self.visible,
            "status": self.status,
            "reason": self.reason,
            "score": self.score,
            "matched_positive_triggers": list(self.matched_positive_triggers),
            "matched_negative_triggers": list(self.matched_negative_triggers),
            "matched_task_families": list(self.matched_task_families),
        }


def _token_match(token: str, scenario_name: str) -> bool:
    token = token.strip().lower()
    if not token:
        return False
    normalized = scenario_name.lower()
    return token in normalized or token.replace("_", " ") in normalized.replace(
        "_", " "
    )


def _family_match(label: str, scenario_strata: set[str], scenario_name: str) -> bool:
    label = label.strip().lower()
    if not label:
        return False
    if _token_match(label, scenario_name):
        return True
    label_parts = {part for part in label.replace("-", "_").split("_") if part}
    for stratum in scenario_strata:
        stratum_parts = {part for part in stratum.split("_") if part}
        if label_parts and len(label_parts & stratum_parts) >= min(2, len(label_parts)):
            return True
    return False


@lru_cache(maxsize=1)
def _latest_helper_contribution_summary() -> dict[str, Any]:
    candidates = sorted(
        ROUTING_EVIDENCE_ROOT.glob("**/helper_contribution_summary.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _helper_evidence(tool_name: str) -> dict[str, Any]:
    helpers = _latest_helper_contribution_summary().get("helpers", {})
    if isinstance(helpers, dict):
        data = helpers.get(tool_name, {})
        return data if isinstance(data, dict) else {}
    return {}


def _blocked_by_adoption_risk(
    tool_name: str,
    *,
    score: int,
    matched_positive: tuple[str, ...],
    matched_families: tuple[str, ...],
) -> tuple[bool, str]:
    if not feature_enabled(EVIDENCE_ROUTING):
        return False, ""
    evidence = _helper_evidence(tool_name)
    if not evidence:
        return False, ""
    visible = int(evidence.get("visible_count", 0) or 0)
    called = int(evidence.get("called_count", 0) or 0)
    visible_not_called = int(evidence.get("visible_not_called_count", 0) or 0)
    if visible < 3:
        return False, ""
    vnc_rate = visible_not_called / max(visible, 1)
    if vnc_rate <= 0.5:
        return False, ""
    called_subset = evidence.get("called_subset", {})
    called_outcome = (
        called_subset.get("mean_outcome_delta")
        if isinstance(called_subset, dict)
        else None
    )
    has_positive_called_contribution = called > 0 and (
        called_outcome is None or float(called_outcome) >= 0
    )
    strong_current_match = (
        bool(matched_positive) and bool(matched_families) and score >= 7
    )
    if strong_current_match and has_positive_called_contribution:
        return False, ""
    return True, "blocked_by_visible_not_called_adoption_risk"


def score_registry_entry_for_scenario(
    entry: RegistryEntry,
    scenario_name: str | None,
) -> RuntimeRoutingDecision:
    spec = entry.tool.spec
    tool_name = spec.tool_name
    if entry.retired or not entry.validation.accepted:
        return RuntimeRoutingDecision(
            tool_name, False, "hidden", "registry_entry_not_active", -100
        )
    if not has_current_validation_proof(entry):
        return RuntimeRoutingDecision(
            tool_name, False, "hidden", "legacy_validation_missing_current_proof", -100
        )
    if not scenario_name:
        return RuntimeRoutingDecision(
            tool_name, False, "hidden", "missing_scenario_name_suppressed", -10
        )
    scenario_lower = scenario_name.lower()
    matched_negative = tuple(
        token for token in spec.negative_triggers if _token_match(token, scenario_lower)
    )
    if matched_negative:
        return RuntimeRoutingDecision(
            tool_name,
            False,
            "hidden",
            "blocked_by_negative_trigger",
            -50,
            matched_negative_triggers=matched_negative,
        )
    score = 0
    matched_positive = tuple(
        token for token in spec.positive_triggers if _token_match(token, scenario_lower)
    )
    if matched_positive:
        score += 4
    scenario_strata = set(classify_task_strata(scenario_name))
    matched_families = tuple(
        family
        for family in spec.applicable_task_families
        if _family_match(family, scenario_strata, scenario_lower)
    )
    matched_spec_families = matched_families
    if matched_families:
        score += 3
    trigger_strata = set(HELPER_TRIGGERS.get(tool_name, ()))
    if (
        trigger_strata
        and scenario_strata & trigger_strata
        and (matched_positive or matched_spec_families)
    ):
        score += 2
        matched_families = tuple(
            sorted(set(matched_families) | (scenario_strata & trigger_strata))
        )
    if spec.required_original_tool_calls or spec.preserves_side_effect_tools:
        score += 1
    if spec.abstain_behavior:
        score += 1
    blocked, block_reason = _blocked_by_adoption_risk(
        tool_name,
        score=score,
        matched_positive=matched_positive,
        matched_families=matched_families,
    )
    if blocked:
        return RuntimeRoutingDecision(
            tool_name,
            False,
            "hidden",
            block_reason,
            score,
            matched_positive_triggers=matched_positive,
            matched_task_families=matched_families,
        )
    if score >= 3:
        return RuntimeRoutingDecision(
            tool_name,
            True,
            "shown",
            "generic_relevance_score_passed",
            score,
            matched_positive_triggers=matched_positive,
            matched_task_families=matched_families,
        )
    return RuntimeRoutingDecision(
        tool_name,
        False,
        "defer",
        "generic_relevance_score_insufficient",
        score,
        matched_positive_triggers=matched_positive,
        matched_task_families=matched_families,
    )
