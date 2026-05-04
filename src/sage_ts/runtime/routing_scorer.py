"""Generic runtime routing scores for retained/generated helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sage_ts.evaluation.task_strata import HELPER_TRIGGERS, classify_task_strata
from sage_ts.registry.manifest import RegistryEntry, has_current_validation_proof

DEFAULT_MAX_RUNTIME_BUNDLE_SIZE = 5


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
    if matched_families:
        score += 3
    trigger_strata = set(HELPER_TRIGGERS.get(tool_name, ()))
    if trigger_strata and scenario_strata & trigger_strata:
        score += 2
        matched_families = tuple(
            sorted(set(matched_families) | (scenario_strata & trigger_strata))
        )
    if spec.required_original_tool_calls or spec.preserves_side_effect_tools:
        score += 1
    if spec.abstain_behavior:
        score += 1
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
