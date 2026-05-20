"""Environment-neutral SAGE interfaces.

These types define what an environment must expose for SAGE to operate as a
standalone self-evolving agent. The core lifecycle is deliberately generic:
task observation, gap detection, helper generation, validation, registry
retention, routing, and reuse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

JsonMap = dict[str, Any]


@dataclass(frozen=True)
class EnvironmentProfile:
    """Capability description supplied by an environment adapter."""

    name: str
    description: str
    base_tools: tuple[str, ...] = ()
    action_tools: tuple[str, ...] = ()
    observation_fields: tuple[str, ...] = ()
    helper_families: tuple[str, ...] = ()
    safety_rules: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskSpec:
    """One executable or inspectable environment task."""

    task_id: str
    name: str
    prompt: str
    artifacts: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolUseRecord:
    """A normalized tool/helper call observed during a task."""

    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    result: Any = None
    success: bool = True
    generated_helper: bool = False


@dataclass(frozen=True)
class TaskRunResult:
    """Environment-normalized task outcome."""

    task: TaskSpec
    success: bool
    score: float = 0.0
    outcome_score: float | None = None
    transcript: tuple[str, ...] = ()
    tool_uses: tuple[ToolUseRecord, ...] = ()
    artifacts: Mapping[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass(frozen=True)
class GapSignal:
    """A reusable capability gap observed by an environment adapter."""

    key: str
    summary: str
    source_task_id: str
    source_environment: str
    severity: float = 1.0
    suggested_tool_name: str | None = None
    suggested_helper_family: str = "deterministic_helper"
    evidence: tuple[str, ...] = ()
    required_inputs: Mapping[str, str] = field(default_factory=dict)
    expected_outputs: Mapping[str, str] = field(default_factory=dict)
    validation_hints: tuple[str, ...] = ()
    generation_directives: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationCase:
    """A helper validation case supplied by the environment adapter."""

    name: str
    inputs: Mapping[str, Any]
    expected: Mapping[str, Any] = field(default_factory=dict)
    should_abstain: bool = False
    description: str = ""


@dataclass(frozen=True)
class HelperSpec:
    """Environment-neutral helper contract."""

    name: str
    family: str
    description: str
    input_schema: Mapping[str, str] = field(default_factory=dict)
    output_schema: Mapping[str, str] = field(default_factory=dict)
    positive_triggers: tuple[str, ...] = ()
    negative_triggers: tuple[str, ...] = ()
    safety_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class HelperCandidate:
    """Generated helper candidate before registry acceptance."""

    spec: HelperSpec
    code: str
    validation_cases: tuple[ValidationCase, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HelperValidationReport:
    """Validation result for a generated helper."""

    accepted: bool
    errors: tuple[str, ...] = ()
    cases_run: int = 0
    cases_passed: int = 0
    runtime_smoke_passed: bool = False
    side_effect_free: bool = False


@dataclass(frozen=True)
class HelperRecord:
    """Accepted helper stored in a standalone SAGE registry."""

    candidate: HelperCandidate
    validation: HelperValidationReport
    birth_gap_key: str
    birth_environment: str
    created_at: str
    code_hash: str
    uses: int = 0
    successes: int = 0
    retired: bool = False


class HelperGenerator(Protocol):
    """Protocol for LLM or deterministic helper generators."""

    def generate(
        self,
        gap: GapSignal,
        profile: EnvironmentProfile,
        validation_cases: tuple[ValidationCase, ...],
        *,
        model: str,
    ) -> HelperCandidate:
        """Generate a helper candidate for a reusable gap."""


class EnvironmentAdapter(Protocol):
    """Contract an environment must implement for standalone SAGE."""

    def profile(self) -> EnvironmentProfile:
        """Return the environment capability and safety profile."""

    def prepare(self) -> None:
        """Prepare local resources needed for a run."""

    def tasks(self, *, limit: int | None = None) -> tuple[TaskSpec, ...]:
        """Return tasks in the sealed order selected by the environment."""

    def route_helpers(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> tuple[str, ...]:
        """Select a bounded helper bundle for a task."""

    def run_task(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> TaskRunResult:
        """Execute or simulate one task with the provided helper bundle."""

    def observe_gap(
        self,
        task: TaskSpec,
        result: TaskRunResult,
        helpers: Mapping[str, HelperRecord],
    ) -> GapSignal | None:
        """Convert task failure or friction into a reusable gap signal."""

    def validation_cases_for_gap(self, gap: GapSignal) -> tuple[ValidationCase, ...]:
        """Provide environment-specific positive and negative validation cases."""
