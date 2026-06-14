"""Generic runtime routing scores for retained/generated helpers."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from sage_ts.evaluation.task_strata import HELPER_TRIGGERS, classify_task_strata
from sage_ts.experiments.v2_flags import EVIDENCE_ROUTING, feature_enabled
from sage_ts.generation.tool_spec import ToolFamily
from sage_ts.registry.manifest import RegistryEntry, has_current_validation_proof

DEFAULT_MAX_RUNTIME_BUNDLE_SIZE = 5
ROUTING_EVIDENCE_ROOT = Path("artifacts/summaries")
ROUTING_EVIDENCE_MODE_ENV = "SAGE_ROUTING_EVIDENCE_MODE"
ROUTING_EVIDENCE_PATH_ENV = "SAGE_ROUTING_EVIDENCE_PATH"
FAIR_CHANCE_MAX_VISIBLE_WITHOUT_CALLS = 10
FAMILY_MATCH_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "at",
        "by",
        "for",
        "from",
        "in",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
    }
)


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
    fair_chance_candidate: bool = False
    fair_chance_reason: str = ""

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
            "fair_chance_candidate": self.fair_chance_candidate,
            "fair_chance_reason": self.fair_chance_reason,
        }


def _token_match(token: str, scenario_name: str) -> bool:
    token = token.strip().lower()
    if not token:
        return False
    normalized = scenario_name.lower()
    return token in normalized or token.replace("_", " ") in normalized.replace(
        "_", " "
    )


def _family_parts(value: str) -> set[str]:
    return {
        part
        for part in value.replace("-", "_").split("_")
        if part and part not in FAMILY_MATCH_STOPWORDS
    }


def _family_match(label: str, scenario_strata: set[str], scenario_name: str) -> bool:
    label = label.strip().lower()
    if not label:
        return False
    label_variants = {label}
    for suffix in (
        "_once",
        "_twice",
        "_twice_multiple_user_turn",
        "_multiple_user_turn",
    ):
        if label.endswith(suffix):
            label_variants.add(label[: -len(suffix)])
    if any(_token_match(variant, scenario_name) for variant in label_variants):
        return True
    label_parts = set().union(*(_family_parts(variant) for variant in label_variants))
    for stratum in scenario_strata:
        stratum_parts = _family_parts(stratum)
        shared_part_threshold = 2 if len(label_parts) <= 2 else 3
        if label_parts and len(label_parts & stratum_parts) >= shared_part_threshold:
            return True
    return False


def _normalized_trigger_text(value: str) -> str:
    return " ".join(value.strip().lower().replace("-", "_").replace("_", " ").split())


def _specific_family_overrides_negative_trigger(
    negative_trigger: str,
    matched_families: tuple[str, ...],
    scenario_name: str,
) -> bool:
    """Keep broad negative verbs from hiding a more specific matching family."""
    negative = _normalized_trigger_text(negative_trigger)
    if not negative:
        return False
    # These minefield-style triggers should remain hard blockers even if a broad
    # family label also matches.
    if any(
        token in negative
        for token in (
            "insufficient",
            "missing",
            "ambiguous",
            "no records",
            "no candidates",
            "empty",
            "already ready",
        )
    ):
        return False
    scenario = _normalized_trigger_text(scenario_name)
    for family in matched_families:
        normalized_family = _normalized_trigger_text(family)
        if (
            negative in normalized_family
            and normalized_family != negative
            and normalized_family in scenario
        ):
            return True
    return False


def _summary_has_runtime_exceptions(payload: dict[str, Any]) -> bool:
    """Return whether a contribution summary points to an invalid runtime run."""
    candidate_dir = payload.get("candidate_dir")
    if not isinstance(candidate_dir, str) or not candidate_dir:
        return False
    candidate_path = Path(candidate_dir)
    run_root = candidate_path.parent.parent
    comparison_path = run_root / "paired_comparison.json"
    if not comparison_path.exists():
        return False
    try:
        comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return int(comparison.get("runtime_exception_count", 0) or 0) > 0


def _routing_evidence_mode() -> str:
    raw = os.environ.get(ROUTING_EVIDENCE_MODE_ENV, "auto").strip().lower()
    if raw in {"", "auto", "latest"}:
        return "auto"
    if raw in {"disabled", "off", "none"}:
        return "disabled"
    if raw in {"pinned", "path"}:
        return "pinned"
    return "auto"


def _read_helper_contribution_summary(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    if _summary_has_runtime_exceptions(payload):
        return {}
    return payload


@lru_cache(maxsize=1)
def _latest_helper_contribution_summary() -> dict[str, Any]:
    mode = _routing_evidence_mode()
    if mode == "disabled":
        return {}
    if mode == "pinned":
        raw_path = os.environ.get(ROUTING_EVIDENCE_PATH_ENV, "").strip()
        if not raw_path:
            return {}
        return _read_helper_contribution_summary(Path(raw_path).expanduser())

    candidates = sorted(
        ROUTING_EVIDENCE_ROOT.glob("**/helper_contribution_summary.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        payload = _read_helper_contribution_summary(path)
        if payload:
            return payload
    return {}


def _helper_evidence(tool_name: str) -> dict[str, Any]:
    helpers = _latest_helper_contribution_summary().get("helpers", {})
    if isinstance(helpers, dict):
        data = helpers.get(tool_name, {})
        return data if isinstance(data, dict) else {}
    return {}


def _input_names(spec: Any) -> set[str]:
    return {item.name for item in spec.inputs}


def _is_fair_chance_candidate(entry: RegistryEntry, evidence: dict[str, Any]) -> bool:
    """Return whether a new cluster-born helper deserves bounded first exposure."""
    if not feature_enabled(EVIDENCE_ROUTING):
        return False
    spec = entry.tool.spec
    if spec.diagnostic_only or not spec.shortfall_cluster_evidence:
        return False
    if entry.reuse_count > 0:
        return False
    if not evidence:
        return True
    visible = int(evidence.get("visible_count", 0) or 0)
    called = int(evidence.get("called_count", 0) or 0)
    return called == 0 and visible < FAIR_CHANCE_MAX_VISIBLE_WITHOUT_CALLS


def _cluster_fit_reason(
    entry: RegistryEntry,
    *,
    scenario_strata: set[str],
    matched_positive: tuple[str, ...],
    matched_families: tuple[str, ...],
) -> str:
    """Mechanism-level cluster fit that does not depend on specific tool names."""
    spec = entry.tool.spec
    if matched_positive or matched_families:
        return "trigger_or_family_fit"
    if spec.family == ToolFamily.STATE_PRECONDITION_HELPER and (
        "direct_state_precondition_service_enablement" in scenario_strata
    ):
        evidence_text = " ".join(
            (
                spec.description,
                spec.generalization_rationale,
                " ".join(spec.shortfall_cluster_evidence),
                " ".join(spec.known_failure_mechanisms_addressed),
                " ".join(spec.positive_triggers),
                " ".join(spec.applicable_task_families),
            )
        ).lower()
        if any(
            token in evidence_text
            for token in ("dependency", "precondition", "service", "state")
        ):
            return "state_precondition_cluster_fit"
    return ""


def _blocked_by_adoption_risk(
    tool_name: str,
    *,
    score: int,
    matched_positive: tuple[str, ...],
    matched_families: tuple[str, ...],
    fair_chance_candidate: bool = False,
    cluster_fit: bool = False,
    allow_strong_selector_fair_chance: bool = False,
) -> tuple[bool, str]:
    if not feature_enabled(EVIDENCE_ROUTING):
        return False, ""
    if score < 3:
        return False, ""
    if fair_chance_candidate and cluster_fit:
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
    has_negative_called_contribution = (
        called > 0 and called_outcome is not None and (float(called_outcome) < 0)
    )
    strong_current_match = (
        bool(matched_positive) and bool(matched_families) and score >= 7
    )
    if strong_current_match and has_positive_called_contribution:
        return False, ""
    if allow_strong_selector_fair_chance and not has_negative_called_contribution:
        return False, ""
    return True, "blocked_by_visible_not_called_adoption_risk"


def _is_recency_action_selector(spec_text: str, input_names: set[str]) -> bool:
    return (
        "timestamp_key" in input_names
        and "selection_mode" in input_names
        and "action_type" in input_names
        and any(token in spec_text for token in ("recency", "latest", "oldest"))
    )


def _is_insufficient_information_guard(spec: Any) -> bool:
    """Identify abstention helpers whose purpose is to stop unsafe minefield calls."""
    output_props = {}
    if isinstance(spec.output_schema, dict):
        raw_props = spec.output_schema.get("properties", {})
        if isinstance(raw_props, dict):
            output_props = raw_props
    evidence_text = " ".join(
        (
            spec.description,
            spec.abstain_behavior,
            spec.generalization_rationale,
            " ".join(spec.positive_triggers),
            " ".join(spec.applicable_task_families),
            " ".join(spec.shortfall_cluster_evidence),
            " ".join(spec.known_failure_mechanisms_addressed),
            " ".join(output_props),
        )
    ).lower()
    has_abstention_contract = (
        "should_abstain" in output_props
        and (
            "clarification_prompt" in output_props
            or "final_answer_recommendation" in output_props
        )
        and (
            "safe_next_action" in output_props or "clarification_prompt" in output_props
        )
        and (
            "missing_information" in output_props
            or "forbidden_downstream_tools" in output_props
        )
    )
    return has_abstention_contract and any(
        token in evidence_text
        for token in (
            "insufficient_information",
            "missing information",
            "missing_information",
            "clarification",
            "minefield",
        )
    )


def _is_lookup_answer_planner(spec: Any, input_names: set[str]) -> bool:
    """Identify two-stage lookup helpers that answer from a selected record."""
    if spec.family != ToolFamily.COMPOSITE_WORKFLOW_HELPER:
        return False
    if "selected_record" not in input_names:
        return False
    output_props = {}
    if isinstance(spec.output_schema, dict):
        raw_props = spec.output_schema.get("properties", {})
        if isinstance(raw_props, dict):
            output_props = raw_props
    if not {
        "answer_field",
        "answer_value",
        "final_answer_recommendation",
    }.issubset(output_props):
        return False
    has_search_kwargs = any(
        str(key).startswith("search_") and str(key).endswith("_kwargs")
        for key in output_props
    )
    if not has_search_kwargs:
        return False
    evidence_text = " ".join(
        (
            spec.tool_name,
            spec.description,
            spec.reason_tool_is_decisive,
            spec.generalization_rationale,
            " ".join(spec.positive_triggers),
            " ".join(spec.applicable_task_families),
        )
    ).lower()
    return "answer" in evidence_text and "lookup" in evidence_text


def _scenario_has_recency_action_signal(scenario_name: str) -> bool:
    return any(
        token in scenario_name
        for token in (
            "recency",
            "latest",
            "oldest",
            "recent",
            "upcoming",
            "most_recent",
            "last_",
            "next_",
        )
    )


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
    input_names = _input_names(spec)
    spec_text = " ".join(
        [
            spec.tool_name,
            spec.description,
            *spec.positive_triggers,
            *spec.applicable_task_families,
        ]
    ).lower()
    scenario_strata = set(classify_task_strata(scenario_name))
    matched_positive = tuple(
        token for token in spec.positive_triggers if _token_match(token, scenario_lower)
    )
    matched_families = tuple(
        family
        for family in spec.applicable_task_families
        if _family_match(family, scenario_strata, scenario_lower)
    )
    matched_negative = tuple(
        token
        for token in spec.negative_triggers
        if _token_match(token, scenario_lower)
        and not _specific_family_overrides_negative_trigger(
            token, matched_families, scenario_lower
        )
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
    if matched_positive:
        score += 4
    if _is_recency_action_selector(
        spec_text, input_names
    ) and not _scenario_has_recency_action_signal(scenario_lower):
        return RuntimeRoutingDecision(
            tool_name,
            False,
            "hidden",
            "recency_action_selector_requires_recency_action_task",
            -25,
        )
    if (
        spec.family
        in {
            ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        }
        and "insufficient_information" in scenario_lower
        and (spec.preserves_side_effect_tools or spec.required_original_tool_calls)
    ):
        reason = (
            "side_effect_selector_suppressed_for_insufficient_information"
            if spec.family == ToolFamily.SEARCH_FILTER_RANKING_HELPER
            else "side_effect_composite_suppressed_for_insufficient_information"
        )
        return RuntimeRoutingDecision(
            tool_name,
            False,
            "hidden",
            reason,
            -30,
        )
    if (
        spec.family == ToolFamily.DERIVED_VALUE_CALCULATOR
        and "insufficient_information" in scenario_lower
        and spec.required_original_tool_calls
        and not _is_insufficient_information_guard(spec)
    ):
        return RuntimeRoutingDecision(
            tool_name,
            False,
            "hidden",
            "derived_calculator_suppressed_for_insufficient_information",
            -30,
        )
    if (
        spec.family == ToolFamily.COMPOSITE_WORKFLOW_HELPER
        and "selected_record" in input_names
        and not _is_lookup_answer_planner(spec, input_names)
        and not any(
            token in scenario_lower
            for token in (
                "remove_",
                "delete_",
                "modify_",
                "update_",
                "send_",
                "reply_",
            )
        )
    ):
        return RuntimeRoutingDecision(
            tool_name,
            False,
            "hidden",
            "post_selection_composite_requires_downstream_action_task",
            -20,
        )
    matched_spec_families = matched_families
    if matched_families:
        score += 3
    evidence = _helper_evidence(tool_name)
    fair_chance = _is_fair_chance_candidate(entry, evidence)
    cluster_fit_reason = _cluster_fit_reason(
        entry,
        scenario_strata=scenario_strata,
        matched_positive=matched_positive,
        matched_families=matched_families,
    )
    if cluster_fit_reason:
        score += 3 if fair_chance else 1
        matched_families = tuple(sorted(set(matched_families) | {cluster_fit_reason}))
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
        fair_chance_candidate=fair_chance,
        cluster_fit=bool(cluster_fit_reason),
        allow_strong_selector_fair_chance=(
            spec.family == ToolFamily.SEARCH_FILTER_RANKING_HELPER
            and "records" in input_names
            and any(
                tool_name.startswith(("search_", "find_", "get_"))
                for tool_name in (
                    tuple(spec.required_original_tool_calls)
                    + tuple(spec.preserves_side_effect_tools)
                )
            )
            and "trigger_or_family_fit" in matched_families
            and score >= 7
        ),
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
            fair_chance_candidate=fair_chance,
            fair_chance_reason=cluster_fit_reason if fair_chance else "",
        )
    if fair_chance and cluster_fit_reason and score >= 3:
        return RuntimeRoutingDecision(
            tool_name,
            True,
            "shown",
            "fair_chance_cluster_fit",
            score,
            matched_positive_triggers=matched_positive,
            matched_task_families=matched_families,
            fair_chance_candidate=True,
            fair_chance_reason=cluster_fit_reason,
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
            fair_chance_candidate=fair_chance,
            fair_chance_reason=cluster_fit_reason if fair_chance else "",
        )
    return RuntimeRoutingDecision(
        tool_name,
        False,
        "defer",
        "generic_relevance_score_insufficient",
        score,
        matched_positive_triggers=matched_positive,
        matched_task_families=matched_families,
        fair_chance_candidate=fair_chance,
        fair_chance_reason=cluster_fit_reason if fair_chance else "",
    )
