"""Online conversion from repeated observations to accepted helper tools."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from sage_ts.adequacy.inadequacy_classifier import CapabilityObservation
from sage_ts.generation.tool_generator import ToolGenerationRequest
from sage_ts.generation.tool_spec import GeneratedTool
from sage_ts.orchestration.checkpoints import append_jsonl
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.registry.store import RegistryStore
from sage_ts.validation.sandbox_validator import validate_generated_tool


class GeneratedToolFactory(Protocol):
    def generate(self, request: ToolGenerationRequest) -> GeneratedTool: ...


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
    return suffix


@dataclass
class OnlineBirthController:
    store: RegistryStore
    generator: GeneratedToolFactory
    output_dir: Path
    recurrence_threshold: int = 2
    event_hook: CampaignEventHook | None = None
    counts: Counter[str] = field(default_factory=Counter)
    generated_keys: set[str] = field(default_factory=set)

    def _event(self, event: str, payload: dict[str, Any]) -> None:
        if self.event_hook is not None:
            self.event_hook(event, payload)

    def observe(self, observation: CapabilityObservation) -> None:
        append_jsonl(
            self.output_dir / "capability_observations.jsonl",
            observation.to_json(),
        )
        self.counts[observation.canonical_key] += 1
        if not observation.generation_allowed:
            return
        if observation.canonical_key in self.generated_keys:
            return
        if self.counts[observation.canonical_key] < self.recurrence_threshold:
            return

        request = ToolGenerationRequest(
            scenario_name=observation.scenario_name,
            observation=observation.observation,
            allowed_families=observation.allowed_families,
            validation_examples=tuple(
                {"inputs": item.inputs, "expected": item.expected}
                for item in observation.validation_examples
            ),
            suggested_tool_name=suggested_tool_name(observation.canonical_key),
        )
        self.generated_keys.add(observation.canonical_key)
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
            self._event(
                "validation_started",
                {
                    "canonical_key": observation.canonical_key,
                    "tool_name": tool.spec.tool_name,
                    "scenario": observation.scenario_name,
                },
            )
            validation = validate_generated_tool(
                tool,
                examples=observation.validation_examples,
            )
        except Exception as exc:
            append_jsonl(
                self.output_dir / "tool_birth_events.jsonl",
                {
                    "canonical_key": observation.canonical_key,
                    "accepted": False,
                    "errors": [f"generation_error:{type(exc).__name__}:{exc}"],
                },
            )
            self._event(
                "tool_birth_rejected",
                {
                    "canonical_key": observation.canonical_key,
                    "scenario": observation.scenario_name,
                    "error": f"{type(exc).__name__}:{exc}",
                },
            )
            return

        append_jsonl(
            self.output_dir / "tool_birth_events.jsonl",
            {
                "canonical_key": observation.canonical_key,
                "tool_name": tool.spec.tool_name,
                "family": tool.spec.family.value,
                "accepted": validation.accepted,
                "errors": list(validation.errors),
            },
        )
        self._event(
            "validation_passed" if validation.accepted else "validation_failed",
            {
                "canonical_key": observation.canonical_key,
                "tool_name": tool.spec.tool_name,
                "scenario": observation.scenario_name,
                "errors": list(validation.errors),
            },
        )
        if validation.accepted:
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
            self._event(
                "tool_birth_rejected",
                {
                    "canonical_key": observation.canonical_key,
                    "tool_name": tool.spec.tool_name,
                    "scenario": observation.scenario_name,
                    "errors": list(validation.errors),
                },
            )
