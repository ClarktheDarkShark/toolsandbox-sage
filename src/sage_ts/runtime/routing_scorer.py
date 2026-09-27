"""Runtime routing types shared by the visible-context router."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sage_ts.evaluation.task_strata import base_task_family
from sage_ts.generation.complete_tools import COMPLETE_TOOLS_NATIVE_NAMES
from sage_ts.generation.tool_spec import ToolFamily

DEFAULT_MAX_RUNTIME_BUNDLE_SIZE = 5


def _string_items(row: dict[str, Any], key: str) -> tuple[str, ...]:
    return tuple(str(item) for item in row.get(key, []) if item)


def _int_or(value: Any, default: Any) -> Any:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True, slots=True)
class RoutingTextFacts:
    """The two exact text views consumed by runtime routing rules."""

    has_visible_context: bool
    routing_lower: str
    match_context: str

    @classmethod
    def from_context(
        cls,
        task_context_text: str | None,
        task_family_key: str | None,
    ) -> RoutingTextFacts:
        routing_lower = (task_context_text or "").lower()
        if not task_context_text:
            return cls(False, routing_lower, "")
        match_context = f"{task_context_text} family={task_family_key or ''}".lower()
        if " tools=" in match_context and " signals=" in match_context:
            request_part = match_context.split(" tools=", 1)[0]
            signal_part = match_context.split(" signals=", 1)[1]
            match_context = f"{request_part} signals={signal_part}"
        return cls(True, routing_lower, match_context)


@dataclass(frozen=True, slots=True)
class DownstreamRequirement:
    """Original ToolSandbox calls required by one routed generated tool."""

    tool_names: frozenset[str]
    requires_any: bool = False

    @classmethod
    def from_spec(cls, spec: Any) -> DownstreamRequirement:
        tool_names = set(spec.required_original_tool_calls)
        requires_any = False
        output_schema = spec.output_schema or {}
        output_props = (
            output_schema.get("properties", {})
            if isinstance(output_schema, dict)
            else {}
        )
        if isinstance(output_props, dict):
            tool_name_schema = output_props.get("tool_name", {})
            if isinstance(tool_name_schema, dict):
                emitted = {
                    str(item) for item in tool_name_schema.get("enum", ()) if str(item)
                }
                if emitted:
                    tool_names = emitted
                    requires_any = True
            if "downstream_tool_name" in output_props and spec.family in {
                ToolFamily.COMPOSITE_WORKFLOW_HELPER,
                ToolFamily.SEARCH_FILTER_RANKING_HELPER,
            }:
                tool_names = set(spec.preserves_side_effect_tools)
                requires_any = True
        if spec.family == ToolFamily.DERIVED_VALUE_CALCULATOR and len(tool_names) > 1:
            requires_any = True
        if not tool_names:
            tool_names = set(spec.preserves_side_effect_tools)
        return cls(frozenset(tool_names), requires_any)

    def narrowed_to_search_producers(
        self,
        preserved_tools: tuple[str, ...],
    ) -> DownstreamRequirement:
        producer_tools = frozenset(
            tool_name
            for tool_name in self.tool_names | set(preserved_tools)
            if tool_name.startswith(("search_", "get_", "find_"))
        )
        return type(self)(producer_tools, True) if producer_tools else self

    def missing_from(
        self,
        available_tools: set[str],
    ) -> set[str]:
        alternative_actions = self.tool_names & set(COMPLETE_TOOLS_NATIVE_NAMES)
        if len(alternative_actions) > 1:
            missing = set(self.tool_names - alternative_actions - available_tools)
            if not alternative_actions & available_tools:
                missing.update(alternative_actions)
            return missing
        if self.requires_any:
            return set() if self.tool_names & available_tools else set(self.tool_names)
        return set(self.tool_names - available_tools)


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


@dataclass(frozen=True, slots=True)
class LifecycleRoutingFacts:
    """One registry entry's frozen lifecycle evidence for the routed family."""

    override: tuple[bool, str] | None
    retained_row: dict[str, Any] | None = None

    @classmethod
    def from_state(
        cls,
        *,
        tool_name: str,
        task_family_key: str | None,
        lifecycle_state: dict[str, dict[str, Any]] | None,
    ) -> LifecycleRoutingFacts | None:
        if not task_family_key or not lifecycle_state:
            return None
        row = lifecycle_state.get(tool_name)
        if not row:
            return None
        decision = str(row.get("decision") or "")
        if decision in {"park", "parked"}:
            return cls((False, "lifecycle_suppressed_parked_tool"))

        scenario_family = base_task_family(task_family_key)
        route_repair_families = frozenset(_string_items(row, "route_repair_families"))
        harmful_scenarios = _string_items(row, "harmful_called_scenarios")
        harmful_count = _int_or(row.get("harmful_called_count"), len(harmful_scenarios))
        helpful_families = _string_items(row, "helpful_called_families")
        harmful_family_rows = _string_items(row, "harmful_called_families")
        harmful_family_rows = harmful_family_rows or harmful_scenarios
        helpful_families = helpful_families or _string_items(
            row, "helpful_called_scenarios"
        )

        def same_family(value: str) -> bool:
            family = str(value or "")
            return (
                family == scenario_family or base_task_family(family) == scenario_family
            )

        harmful_family_count = sum(map(same_family, harmful_family_rows))
        helpful_family_count = sum(map(same_family, helpful_families))
        is_abstention = tool_name == "prepare_safe_action_or_abstain"
        if is_abstention:
            side_effect_count = _int_or(row.get("side_effect_incident_count") or 0, 0)
            failed_count = _int_or(row.get("failed_count") or 0, 0)
            operationally_clean = side_effect_count == 0 and failed_count == 0
        else:
            operationally_clean = False
        override = None
        if not (is_abstention and operationally_clean):
            if decision == "retain_with_route_repair":
                if task_family_key in harmful_scenarios:
                    override = (
                        False,
                        "lifecycle_suppressed_exact_harmful_called_scenario",
                    )
                elif (
                    harmful_family_count >= 2
                    and harmful_family_count > helpful_family_count
                    and scenario_family in route_repair_families
                ):
                    override = (False, "lifecycle_suppressed_harmful_called_family")
            elif scenario_family in route_repair_families:
                below_threshold = harmful_family_count < 2 and not is_abstention
                harm_is_offset = (
                    harmful_family_count
                    and harmful_family_count <= helpful_family_count
                )
                if not below_threshold and not harm_is_offset:
                    override = (False, "lifecycle_suppressed_harmful_called_family")
            elif decision in {"needs_route_repair", "needs_repair"}:
                harmful_families = {
                    base_task_family(str(item)) for item in harmful_family_rows
                }
                below_threshold = (
                    harmful_family_count < 2 and harmful_count < 2 and not is_abstention
                )
                if scenario_family in harmful_families and not below_threshold:
                    override = (False, "lifecycle_suppressed_harmful_called_family")
        retained_row = row if decision == "retain_with_route_repair" else None
        return cls(override, retained_row)

    def can_override_family_suppression(
        self,
        generic_decision: RuntimeRoutingDecision,
    ) -> bool:
        if (
            not generic_decision.visible
            or generic_decision.reason != "visible_context_signal_match"
            or not self.retained_row
        ):
            return False
        for key in ("failed_count", "side_effect_incident_count"):
            try:
                if int(self.retained_row.get(key) or 0) > 0:
                    return False
            except (TypeError, ValueError):
                return False
        return True


def _is_insufficient_information_guard(spec: Any) -> bool:
    """Identify tools whose validated contract safely abstains on missing data."""
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
