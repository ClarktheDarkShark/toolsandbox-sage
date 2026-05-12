"""Online conversion from repeated observations to accepted helper tools."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Protocol

from sage_ts.adequacy.candidate_gate import evaluate_candidate_gate
from sage_ts.adequacy.failure_memory import generation_failure_memory_context
from sage_ts.adequacy.inadequacy_classifier import CapabilityObservation
from sage_ts.evaluation.task_strata import base_task_family, expected_helper_fit
from sage_ts.experiments.v2_flags import (
    CANDIDATE_REPAIR,
    DEPENDENCY_LOGIC,
    LIVE_VALIDATION,
    MEDIUM_GRAIN_SKILLS,
    feature_enabled,
)
from sage_ts.generation.tool_generator import ToolGenerationRequest
from sage_ts.generation.tool_spec import GeneratedTool
from sage_ts.orchestration.checkpoints import append_jsonl
from sage_ts.registry.manifest import RegistryEntry, has_current_validation_proof
from sage_ts.registry.store import RegistryStore
from sage_ts.validation.live_candidate_check import run_lightweight_live_candidate_check
from sage_ts.validation.sandbox_validator import (
    ValidationResult,
    validate_generated_tool,
)


class GeneratedToolFactory(Protocol):
    def generate(self, request: ToolGenerationRequest) -> GeneratedTool: ...


class GeneratedToolRepairFactory(GeneratedToolFactory, Protocol):
    def repair(
        self,
        request: ToolGenerationRequest,
        rejected_tool: GeneratedTool,
        errors: tuple[str, ...],
    ) -> GeneratedTool: ...


CampaignEventHook = Callable[[str, dict[str, Any]], None]


def suggested_tool_name(canonical_key: str) -> str | None:
    """Map recurring capability keys to stable, reusable tool names."""
    suffix = canonical_key.split(":", 1)[-1].strip()
    if not suffix:
        return None
    if suffix == "recency_timestamp_bounds":
        return "recency_to_timestamp_bounds"
    if suffix == "relative_day_time_timestamp":
        return "relative_day_time_to_timestamp"
    if suffix in {"service_next_action", "next_service_tool_call"}:
        return "next_service_tool_call"
    if (
        feature_enabled(DEPENDENCY_LOGIC)
        and suffix == "dependency_precondition_tool_call"
    ):
        return "next_dependency_precondition_call"
    if (
        feature_enabled(MEDIUM_GRAIN_SKILLS)
        and suffix == "constraint_to_action_planner"
    ):
        return "constraint_to_action_planner"
    return suffix


BROADER_HELPER_OVERLAPS = {
    "derived_value:recency_timestamp_bounds": ("resolve_search_window_or_bounds",),
    "derived_value:message_search_time_window": ("resolve_search_window_or_bounds",),
}


PLACEHOLDER_ORIGINAL_TOOL_TOKENS = ("payload", "service", "lookup")
DEFAULT_CANDIDATE_REPAIR_ATTEMPTS = 2
FIRST_OBSERVATION_BIRTH_KEYS = frozenset(
    {
        "composite:plan_contact_lookup_query",
    }
)
CHAIN_ROUTING_FAMILIES_BY_KEY = {
    "composite:plan_contact_lookup_query": (
        "update_contact_relationship_with_relationship_twice",
        "update_contact_relationship_with_relationship",
        "remove_contact_by_phone",
    ),
}


def _dedupe_nonempty(items: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    kept: list[str] = []
    for item in items:
        value = str(item or "").strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        kept.append(value)
    return tuple(kept)


def _normalize_family_label(label: str) -> str:
    normalized = str(label or "").strip().lower().replace(" ", "_").replace("-", "_")
    if not normalized:
        return ""
    return base_task_family(normalized)


def _expanded_family_labels(label: str) -> tuple[str, ...]:
    normalized = _normalize_family_label(label)
    if not normalized:
        return ()
    expanded = [normalized]
    for suffix in (
        "_twice",
        "_once",
        "_multiple_user_turn",
    ):
        if normalized.endswith(suffix):
            expanded.append(normalized[: -len(suffix)])
    return _dedupe_nonempty(expanded)


def _normalize_live_birth_routing_metadata(
    tool: GeneratedTool,
    observation: CapabilityObservation,
    base_families: tuple[str, ...],
) -> GeneratedTool:
    """Stabilize generated routing metadata before validation and registry save.

    Generation models sometimes emit full robustness-variant scenario names as
    ``applicable_task_families``. Those names are valid evidence lineage, but
    they are too narrow for natural reuse and can hide an otherwise useful
    helper on later tasks from the same base family. Normalize them into base
    family labels derived only from visible scenario names, and add the same
    labels as trigger tokens so routing does not depend on exact variants.
    """

    family_candidates: list[str] = []
    for item in tool.spec.applicable_task_families:
        family_candidates.extend(_expanded_family_labels(item))
    for item in base_families:
        family_candidates.extend(_expanded_family_labels(item))
    family_candidates.extend(_expanded_family_labels(observation.scenario_name))
    for item in CHAIN_ROUTING_FAMILIES_BY_KEY.get(observation.canonical_key, ()):
        family_candidates.extend(_expanded_family_labels(item))
    normalized_families = _dedupe_nonempty(family_candidates)
    if not normalized_families:
        return tool
    positive_triggers = _dedupe_nonempty(
        [*tool.spec.positive_triggers, *normalized_families]
    )
    if (
        normalized_families == tool.spec.applicable_task_families
        and positive_triggers == tool.spec.positive_triggers
    ):
        return tool
    return replace(
        tool,
        spec=replace(
            tool.spec,
            applicable_task_families=normalized_families,
            positive_triggers=positive_triggers,
        ),
    )


def existing_broader_helper(
    canonical_key: str,
    store: RegistryStore,
) -> str | None:
    """Return a proved retained helper that already covers this shortfall mechanism."""
    for tool_name in BROADER_HELPER_OVERLAPS.get(canonical_key, ()):
        entry = store.get(tool_name)
        if (
            entry is not None
            and not entry.retired
            and has_current_validation_proof(entry)
        ):
            return tool_name
    return None


def _original_tool_contract_errors(
    tool: GeneratedTool,
    observation: CapabilityObservation,
) -> tuple[str, ...]:
    """Reject placeholder or non-observed ToolSandbox producer contracts.

    Candidate specs must preserve concrete original ToolSandbox calls. A broad
    generated helper is allowed to list several possible producer tools, but it
    cannot invent a placeholder such as ``search_service_payload`` that will
    never be present in a scenario allow-list.
    """
    observed = set(observation.failed_tool_calls) | set(
        observation.repeated_failed_tool_calls
    )
    if not observed:
        return ()
    declared = set(tool.spec.required_original_tool_calls) | set(
        tool.spec.preserves_side_effect_tools
    )
    if not declared:
        return ()
    lowered_observed = {item.lower() for item in observed}
    placeholder = sorted(
        item
        for item in declared
        if item.lower() not in lowered_observed
        and any(token in item.lower() for token in PLACEHOLDER_ORIGINAL_TOOL_TOKENS)
    )
    if placeholder:
        return ("placeholder_downstream_original_tool:" + ",".join(placeholder),)
    if not (declared & observed):
        return ("missing_observed_original_tool_preservation",)
    return ()


@dataclass
class OnlineBirthController:
    store: RegistryStore
    generator: GeneratedToolFactory
    output_dir: Path
    recurrence_threshold: int = 2
    event_hook: CampaignEventHook | None = None
    counts: Counter[str] = field(default_factory=Counter)
    scenarios_by_key: dict[str, set[str]] = field(default_factory=dict)
    base_families_by_key: dict[str, set[str]] = field(default_factory=dict)
    generated_keys: set[str] = field(default_factory=set)
    rejected_counts: Counter[str] = field(default_factory=Counter)
    max_rejections_per_key: int = 2
    failure_memory_path: Path | None = Path("artifacts/summaries/failure_memory.json")

    def _event(self, event: str, payload: dict[str, Any]) -> None:
        if self.event_hook is not None:
            self.event_hook(event, payload)

    def _required_recurrence_threshold(self, observation: CapabilityObservation) -> int:
        if observation.canonical_key in FIRST_OBSERVATION_BIRTH_KEYS:
            return 1
        return self.recurrence_threshold

    def _check_heuristic_signal(self, observation: CapabilityObservation) -> bool:
        """Attempt lightweight transcript verification for heuristic observations.

        Returns True if at least one claimed signal token is found in the
        conversation transcript, False otherwise.  Verification failure is
        logged but never blocks generation (labeling sprint, not blocking).
        """
        conv_path = (
            self.output_dir
            / "trajectories"
            / observation.scenario_name
            / "conversation.json"
        )
        if not conv_path.exists():
            return False
        try:
            import json as _json

            messages = _json.loads(conv_path.read_text(encoding="utf-8"))
        except Exception:
            return False
        if not isinstance(messages, list):
            return False
        transcript_text = " ".join(
            str(m.get("content", "")) + " " + str(m.get("name", ""))
            for m in messages
            if isinstance(m, dict)
        ).lower()
        for signal in observation.inadequacy_signals:
            if (
                signal.lower().replace("_", " ") in transcript_text
                or signal.lower() in transcript_text
            ):
                return True
        for tool in observation.failed_tool_calls:
            if tool.lower() in transcript_text:
                return True
        return False

    def _cluster_context(self, observation: CapabilityObservation) -> dict[str, Any]:
        scenarios = sorted(self.scenarios_by_key.get(observation.canonical_key, set()))
        families = sorted(
            self.base_families_by_key.get(observation.canonical_key, set())
        )
        required_families = (
            3
            if feature_enabled(MEDIUM_GRAIN_SKILLS)
            and observation.canonical_key == "composite:constraint_to_action_planner"
            else 2
        )
        non_diagnostic = (
            len(scenarios) >= self.recurrence_threshold
            and len(families) >= required_families
        )
        return {
            "cluster_id": observation.canonical_key,
            "failure_mechanism": observation.canonical_key,
            "scenario_count": len(scenarios),
            "scenarios": scenarios[:20],
            "distinct_base_task_families": len(families),
            "base_task_families": families[:20],
            "required_distinct_base_task_families": required_families,
            "near_duplicate_only": len(families) < required_families,
            "non_diagnostic_birth_allowed": non_diagnostic,
            "repeated_failed_tool_calls": list(observation.repeated_failed_tool_calls),
            "failed_tool_calls": list(observation.failed_tool_calls),
            "inadequacy_signals": list(observation.inadequacy_signals),
            "current_helper_fit": expected_helper_fit(observation.scenario_name),
            "positive_applicability_example_count": sum(
                1
                for item in observation.validation_examples
                if not item.negative_applicability
            ),
            "negative_applicability_example_count": sum(
                1
                for item in observation.validation_examples
                if item.negative_applicability
            ),
        }

    def observe(self, observation: CapabilityObservation) -> None:
        append_jsonl(
            self.output_dir / "capability_observations.jsonl",
            observation.to_json(),
        )
        self.counts[observation.canonical_key] += 1
        self.scenarios_by_key.setdefault(observation.canonical_key, set()).add(
            observation.scenario_name
        )
        self.base_families_by_key.setdefault(observation.canonical_key, set()).add(
            base_task_family(observation.scenario_name)
        )
        # Log heuristic observations that cannot be transcript-verified.
        if observation.evidence_source == "heuristic":
            verified = self._check_heuristic_signal(observation)
            if not verified:
                append_jsonl(
                    self.output_dir / "sage_run_events.jsonl",
                    {
                        "event": "tool_birth_heuristic_unverified",
                        "canonical_key": observation.canonical_key,
                        "scenario": observation.scenario_name,
                        "evidence_source": observation.evidence_source,
                        "note": "scenario-name prefix heuristic could not be confirmed in transcript",
                    },
                )
        if not observation.generation_allowed:
            return
        if observation.canonical_key in self.generated_keys:
            return
        if (
            self.rejected_counts[observation.canonical_key]
            >= self.max_rejections_per_key
        ):
            append_jsonl(
                self.output_dir / "sage_run_events.jsonl",
                {
                    "event": "tool_birth_retry_suppressed",
                    "canonical_key": observation.canonical_key,
                    "rejection_count": self.rejected_counts[observation.canonical_key],
                    "max_rejections_per_key": self.max_rejections_per_key,
                },
            )
            return
        if self.counts[observation.canonical_key] < self._required_recurrence_threshold(
            observation
        ):
            return

        suggested_name = suggested_tool_name(observation.canonical_key)
        if suggested_name is not None:
            existing_entry = self.store.get(suggested_name)
            if (
                existing_entry is not None
                and not existing_entry.retired
                and has_current_validation_proof(existing_entry)
            ):
                self.generated_keys.add(observation.canonical_key)
                append_jsonl(
                    self.output_dir / "sage_run_events.jsonl",
                    {
                        "event": "tool_birth_skipped_existing",
                        "canonical_key": observation.canonical_key,
                        "tool_name": suggested_name,
                        "registry_dir": str(self.store.root),
                    },
                )
                self._event(
                    "tool_birth_skipped_existing",
                    {
                        "canonical_key": observation.canonical_key,
                        "tool_name": suggested_name,
                        "registry_dir": str(self.store.root),
                    },
                )
                return
            if existing_entry is not None and not has_current_validation_proof(
                existing_entry
            ):
                append_jsonl(
                    self.output_dir / "sage_run_events.jsonl",
                    {
                        "event": "tool_birth_existing_requires_revalidation",
                        "canonical_key": observation.canonical_key,
                        "tool_name": suggested_name,
                        "registry_dir": str(self.store.root),
                    },
                )

        broader_tool_name = existing_broader_helper(
            observation.canonical_key,
            self.store,
        )
        if broader_tool_name is not None:
            self.generated_keys.add(observation.canonical_key)
            payload = {
                "event": "tool_birth_skipped_existing_broader_helper",
                "canonical_key": observation.canonical_key,
                "tool_name": broader_tool_name,
                "registry_dir": str(self.store.root),
                "overlap_reason": (
                    "proved retained helper already covers this shortfall mechanism"
                ),
            }
            append_jsonl(self.output_dir / "sage_run_events.jsonl", payload)
            self._event("tool_birth_skipped_existing_broader_helper", payload)
            return

        request = ToolGenerationRequest(
            scenario_name=observation.scenario_name,
            observation=observation.observation,
            allowed_families=observation.allowed_families,
            validation_examples=tuple(
                {
                    "inputs": item.inputs,
                    "expected": item.expected,
                    "held_out": item.held_out,
                    "negative_applicability": item.negative_applicability,
                }
                for item in observation.validation_examples
            ),
            suggested_tool_name=suggested_name,
            inadequacy_evidence=observation.to_inadequacy_evidence().to_json(),
            failure_memory_context=generation_failure_memory_context(
                self.failure_memory_path,
                canonical_key=observation.canonical_key,
                suggested_tool_name=suggested_name,
            ),
            shortfall_cluster_context=self._cluster_context(observation),
        )
        self._event(
            "tool_birth_started",
            {
                "canonical_key": observation.canonical_key,
                "scenario": observation.scenario_name,
                "allowed_families": observation.allowed_families,
            },
        )
        try:
            tool = self.generator.generate(request)
            cluster_context = self._cluster_context(observation)
            tool = _normalize_live_birth_routing_metadata(
                tool,
                observation,
                tuple(cluster_context["base_task_families"]),
            )
            if (
                not cluster_context["non_diagnostic_birth_allowed"]
                and not tool.spec.diagnostic_only
            ):
                tool = replace(
                    tool,
                    spec=replace(
                        tool.spec,
                        diagnostic_only=True,
                        shortfall_cluster_evidence=(
                            *tool.spec.shortfall_cluster_evidence,
                            "diagnostic_only_near_duplicate_or_single_family_cluster",
                        ),
                    ),
                )
            self._event(
                "validation_started",
                {
                    "canonical_key": observation.canonical_key,
                    "tool_name": tool.spec.tool_name,
                    "scenario": observation.scenario_name,
                },
            )
            memory_gate, live_check, validation = self._gate_and_validate(
                tool,
                observation,
            )
            repair_attempted = False
            repair_attempt_count = 0
            repair_errors: tuple[str, ...] = ()
            repair_history: list[dict[str, Any]] = []
            repair_method = getattr(self.generator, "repair", None)
            if (
                not validation.accepted
                and feature_enabled(CANDIDATE_REPAIR)
                and callable(repair_method)
            ):
                repair_errors = tuple(validation.errors)
                for attempt in range(1, DEFAULT_CANDIDATE_REPAIR_ATTEMPTS + 1):
                    if validation.accepted:
                        break
                    repair_attempted = True
                    repair_attempt_count = attempt
                    current_errors = tuple(validation.errors)
                    repaired_tool = repair_method(request, tool, current_errors)
                    repaired_tool = _normalize_live_birth_routing_metadata(
                        repaired_tool,
                        observation,
                        tuple(self._cluster_context(observation)["base_task_families"]),
                    )
                    repaired_gate, repaired_live_check, repaired_validation = (
                        self._gate_and_validate(repaired_tool, observation)
                    )
                    repair_record = {
                        "attempt": attempt,
                        "input_errors": list(current_errors),
                        "repaired_errors": list(repaired_validation.errors),
                        "accepted": repaired_validation.accepted,
                        "repaired_tool_name": repaired_tool.spec.tool_name,
                    }
                    repair_history.append(repair_record)
                    self._event(
                        "tool_repair_attempted",
                        {
                            "canonical_key": observation.canonical_key,
                            "tool_name": tool.spec.tool_name,
                            **repair_record,
                        },
                    )
                    tool = repaired_tool
                    memory_gate = repaired_gate
                    live_check = repaired_live_check
                    validation = repaired_validation
        except Exception as exc:
            append_jsonl(
                self.output_dir / "tool_birth_events.jsonl",
                {
                    "canonical_key": observation.canonical_key,
                    "accepted": False,
                    "errors": [f"generation_error:{type(exc).__name__}:{exc}"],
                },
            )
            self.rejected_counts[observation.canonical_key] += 1
            self._event(
                "tool_birth_rejected",
                {
                    "canonical_key": observation.canonical_key,
                    "scenario": observation.scenario_name,
                    "error": f"{type(exc).__name__}:{exc}",
                    "rejection_count": self.rejected_counts[observation.canonical_key],
                },
            )
            return

        append_jsonl(
            self.output_dir / "tool_birth_events.jsonl",
            {
                "canonical_key": observation.canonical_key,
                "tool_name": tool.spec.tool_name,
                "family": tool.spec.family.value,
                "estimated_step_compression": tool.spec.estimated_step_compression,
                "cross_task_applicability_count": tool.spec.cross_task_applicability_count,
                "applicable_task_families": list(tool.spec.applicable_task_families),
                "reason_tool_is_decisive": tool.spec.reason_tool_is_decisive,
                "accepted": validation.accepted,
                "errors": list(validation.errors),
                "source_example_count": validation.source_example_count,
                "held_out_check_count": validation.held_out_check_count,
                "runtime_smoke_passed": validation.runtime_smoke_passed,
                "grading_classification": memory_gate.grading_classification,
                "canonical_route_substitution_risk": (
                    tool.spec.canonical_route_substitution_risk
                ),
                "expected_milestone_calls_replaced": list(
                    tool.spec.expected_milestone_calls_replaced
                ),
                "final_state_preservation_plan": tool.spec.final_state_preservation_plan,
                "grading_accounting_note": tool.spec.grading_accounting_note,
                "lightweight_live_validation": (
                    live_check.to_json() if live_check is not None else None
                ),
                "repair_attempted": repair_attempted,
                "repair_attempt_count": repair_attempt_count,
                "repair_errors": list(repair_errors),
                "repair_final_errors": list(validation.errors)
                if repair_attempted
                else [],
                "repair_history": repair_history,
            },
        )
        self._event(
            "validation_passed" if validation.accepted else "validation_failed",
            {
                "canonical_key": observation.canonical_key,
                "tool_name": tool.spec.tool_name,
                "scenario": observation.scenario_name,
                "errors": list(validation.errors),
                "source_example_count": validation.source_example_count,
                "held_out_check_count": validation.held_out_check_count,
                "runtime_smoke_passed": validation.runtime_smoke_passed,
                "estimated_step_compression": tool.spec.estimated_step_compression,
                "cross_task_applicability_count": tool.spec.cross_task_applicability_count,
                "applicable_task_families": list(tool.spec.applicable_task_families),
                "grading_classification": memory_gate.grading_classification,
                "canonical_route_substitution_risk": (
                    tool.spec.canonical_route_substitution_risk
                ),
                "lightweight_live_validation": (
                    live_check.to_json() if live_check is not None else None
                ),
                "repair_attempted": repair_attempted,
                "repair_attempt_count": repair_attempt_count,
            },
        )
        if validation.accepted:
            self.generated_keys.add(observation.canonical_key)
            entry = RegistryEntry.accepted(
                tool,
                validation,
                birth_scenario=observation.scenario_name,
            )
            self.store.put(entry)
            saved_entry = self.store.get(tool.spec.tool_name) or entry
            snapshot_dir = self.output_dir / "generated_tool_snapshots"
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            snapshot_path = (
                snapshot_dir / f"{tool.spec.tool_name}_v{saved_entry.version}.py"
            )
            snapshot_path.write_text(tool.code + "\n", encoding="utf-8")
            append_jsonl(
                self.output_dir / "sage_run_events.jsonl",
                {
                    "event": "registry_save",
                    "registry_dir": str(self.store.root),
                    "tool_name": tool.spec.tool_name,
                    "birth_scenario": observation.scenario_name,
                    "snapshot_path": str(snapshot_path),
                },
            )
            self._event(
                "tool_birth_succeeded",
                {
                    "canonical_key": observation.canonical_key,
                    "tool_name": tool.spec.tool_name,
                    "scenario": observation.scenario_name,
                    "family": tool.spec.family.value,
                    "snapshot_path": str(snapshot_path),
                },
            )
            self._event(
                "registry_saved",
                {
                    "registry_dir": str(self.store.root),
                    "tool_name": tool.spec.tool_name,
                    "scenario": observation.scenario_name,
                },
            )
        else:
            self.rejected_counts[observation.canonical_key] += 1
            self._event(
                "tool_birth_rejected",
                {
                    "canonical_key": observation.canonical_key,
                    "tool_name": tool.spec.tool_name,
                    "scenario": observation.scenario_name,
                    "errors": list(validation.errors),
                    "rejection_count": self.rejected_counts[observation.canonical_key],
                },
            )

    def _gate_and_validate(
        self,
        tool: GeneratedTool,
        observation: CapabilityObservation,
    ) -> tuple[Any, Any, ValidationResult]:
        memory_gate = evaluate_candidate_gate(
            tool.spec,
            failure_memory_path=self.failure_memory_path,
        )
        if not memory_gate.allowed:
            return (
                memory_gate,
                None,
                ValidationResult(False, (memory_gate.reason,)),
            )
        original_contract_errors = _original_tool_contract_errors(tool, observation)
        if original_contract_errors:
            return (
                memory_gate,
                None,
                ValidationResult(False, original_contract_errors),
            )
        if feature_enabled(LIVE_VALIDATION):
            live_check = run_lightweight_live_candidate_check(
                tool,
                observation.validation_examples,
            )
            if not live_check.accepted:
                return (
                    memory_gate,
                    live_check,
                    ValidationResult(False, live_check.errors),
                )
        else:
            live_check = None
        return (
            memory_gate,
            live_check,
            validate_generated_tool(
                tool,
                examples=observation.validation_examples,
            ),
        )
