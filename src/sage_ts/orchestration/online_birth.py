"""Online conversion from repeated observations to accepted helper tools."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from sage_ts.adequacy.inadequacy_classifier import CapabilityObservation
from sage_ts.generation.tool_generator import ToolGenerationRequest
from sage_ts.generation.tool_spec import GeneratedTool
from sage_ts.orchestration.checkpoints import append_jsonl
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.registry.store import RegistryStore
from sage_ts.validation.sandbox_validator import validate_generated_tool


class GeneratedToolFactory(Protocol):
    def generate(self, request: ToolGenerationRequest) -> GeneratedTool: ...


@dataclass
class OnlineBirthController:
    store: RegistryStore
    generator: GeneratedToolFactory
    output_dir: Path
    recurrence_threshold: int = 2
    counts: Counter[str] = field(default_factory=Counter)
    generated_keys: set[str] = field(default_factory=set)

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
        )
        self.generated_keys.add(observation.canonical_key)
        try:
            tool = self.generator.generate(request)
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
