from pathlib import Path

from sage_agent import SAGEAgent, SAGEConfig
from sage_agent.adapters import (
    CyberGymAdapter,
    ToolSandboxMiniAdapter,
    ToolSandboxScenarioProbeAdapter,
)
from sage_agent.generators import TemplateHelperGenerator
from sage_agent.integrity import (
    IntegrityError,
    ResearchIntegrityPolicy,
    check_task_specs,
)
from sage_agent.interfaces import (
    EnvironmentProfile,
    GapSignal,
    HelperCandidate,
    HelperRecord,
    HelperSpec,
    TaskRunResult,
    TaskSpec,
    ValidationCase,
)


def test_standalone_sage_births_and_reuses_tool_on_toolsandbox_shape(
    tmp_path: Path,
) -> None:
    agent = SAGEAgent(
        adapter=ToolSandboxMiniAdapter(),
        generator=TemplateHelperGenerator(),
        config=SAGEConfig(registry_dir=tmp_path / "registry"),
    )

    first = agent.run(limit=1)
    assert first.environment == "toolsandbox"
    assert first.tools_born == 1
    assert first.tools_accepted == 1
    assert first.birth_task_retry_successes == 1

    second = agent.run(limit=2)
    assert second.tools_reused >= 1
    assert second.tasks_succeeded >= 1
    assert second.lifecycle_decisions[0]["decision"] in {"keep", "scale"}


def test_standalone_sage_cybergym_adapter_births_log_classifier(
    tmp_path: Path,
) -> None:
    repo_root = Path("external/cybergym")
    agent = SAGEAgent(
        adapter=CyberGymAdapter(repo_root=repo_root),
        generator=TemplateHelperGenerator(),
        config=SAGEConfig(registry_dir=tmp_path / "registry"),
    )

    first = agent.run(limit=1)
    assert first.environment == "cybergym"
    assert first.tools_born == 1
    assert first.tools_accepted == 1

    second = agent.run(limit=1)
    assert second.tools_reused == 1
    assert second.tasks_succeeded == 1


def test_standalone_sage_toolsandbox_probe_uses_real_scenario_registry(
    tmp_path: Path,
) -> None:
    agent = SAGEAgent(
        adapter=ToolSandboxScenarioProbeAdapter(
            scenario_names=("search_phone_number_with_name",)
        ),
        generator=TemplateHelperGenerator(),
        config=SAGEConfig(registry_dir=tmp_path / "registry"),
    )

    summary = agent.run(limit=1)
    assert summary.environment == "toolsandbox"
    assert summary.tools_accepted == 1
    assert summary.birth_task_retry_successes == 1


def test_standalone_sage_repairs_rejected_helper(tmp_path: Path) -> None:
    agent = SAGEAgent(
        adapter=ToolSandboxMiniAdapter(),
        generator=BrokenThenRepairGenerator(),
        config=SAGEConfig(registry_dir=tmp_path / "registry", repair_attempts=1),
    )

    summary = agent.run(limit=1)
    assert summary.tools_born == 1
    assert summary.repair_attempts == 1
    assert summary.tools_accepted == 1
    assert summary.tools_rejected == 0


def test_standalone_adapters_do_not_expose_label_or_oracle_metadata() -> None:
    policy = ResearchIntegrityPolicy()
    toolsandbox_tasks = ToolSandboxMiniAdapter().tasks()
    cybergym_tasks = CyberGymAdapter(repo_root=Path("external/cybergym")).tasks(limit=1)

    assert check_task_specs(toolsandbox_tasks, policy).passed
    assert check_task_specs(cybergym_tasks, policy).passed


def test_standalone_sage_blocks_label_peeking_metadata(tmp_path: Path) -> None:
    agent = SAGEAgent(
        adapter=LeakyAdapter(),
        generator=TemplateHelperGenerator(),
        config=SAGEConfig(registry_dir=tmp_path / "registry"),
    )

    try:
        agent.run(limit=1)
    except IntegrityError as exc:
        assert "expected_answer" in str(exc)
    else:  # pragma: no cover - defensive clarity
        raise AssertionError("SAGE accepted leak-prone task metadata")


class BrokenThenRepairGenerator(TemplateHelperGenerator):
    def generate(
        self,
        gap: GapSignal,
        profile: EnvironmentProfile,
        validation_cases: tuple[ValidationCase, ...],
        *,
        model: str,
    ) -> HelperCandidate:
        del gap, profile, validation_cases, model
        return HelperCandidate(
            spec=HelperSpec(
                name="select_visible_record_by_field",
                family="record_selector",
                description="Broken first draft.",
            ),
            code="def select_visible_record_by_field(records: list) -> dict:\n    if True return {}\n",
        )

    def repair(
        self,
        gap: GapSignal,
        profile: EnvironmentProfile,
        rejected: HelperCandidate,
        errors: tuple[str, ...],
        validation_cases: tuple[ValidationCase, ...],
        *,
        model: str,
    ) -> HelperCandidate:
        del rejected, errors
        return TemplateHelperGenerator.generate(
            self, gap, profile, validation_cases, model=model
        )


class LeakyAdapter:
    def profile(self) -> EnvironmentProfile:
        return EnvironmentProfile(name="leaky", description="Leaky test adapter.")

    def prepare(self) -> None:
        return None

    def tasks(self, *, limit: int | None = None) -> tuple[TaskSpec, ...]:
        tasks = (
            TaskSpec(
                task_id="leaky-1",
                name="leaky task",
                prompt="Visible prompt.",
                metadata={"expected_answer": "secret"},
            ),
        )
        return tasks[:limit] if limit is not None else tasks

    def route_helpers(
        self, task: TaskSpec, helpers: dict[str, HelperRecord]
    ) -> tuple[str, ...]:
        del task, helpers
        return ()

    def run_task(
        self, task: TaskSpec, helpers: dict[str, HelperRecord]
    ) -> TaskRunResult:
        del helpers
        return TaskRunResult(task=task, success=False)

    def observe_gap(
        self,
        task: TaskSpec,
        result: TaskRunResult,
        helpers: dict[str, HelperRecord],
    ) -> GapSignal | None:
        del result, helpers
        return GapSignal(
            key="leaky_gap",
            summary="Generate from visible inputs only.",
            source_task_id=task.task_id,
            source_environment="leaky",
        )

    def validation_cases_for_gap(self, gap: GapSignal) -> tuple[ValidationCase, ...]:
        del gap
        return ()
