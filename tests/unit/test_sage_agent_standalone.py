from collections.abc import Mapping
from pathlib import Path

from sage_agent import SAGEAgent, SAGEConfig
from sage_agent.adapters import (
    CyberGymAdapter,
    ToolSandboxMiniAdapter,
    ToolSandboxScenarioProbeAdapter,
)
from sage_agent.dashboard import write_standalone_dashboard
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
    HelperValidationReport,
    TaskRunResult,
    TaskSpec,
    ToolUseRecord,
    ValidationCase,
)
from sage_agent.registry import LocalSAGERegistry


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


def test_standalone_sage_refines_underperforming_retained_helper(
    tmp_path: Path,
) -> None:
    registry = LocalSAGERegistry(tmp_path / "registry")
    registry.add(
        RetainedRefinementGenerator.bad_candidate(),
        HelperValidationReport(
            accepted=True,
            cases_run=1,
            cases_passed=1,
            runtime_smoke_passed=True,
            side_effect_free=True,
        ),
        birth_gap_key="constant_gap",
        birth_environment="refinement-test",
    )
    agent = SAGEAgent(
        adapter=RefinementAdapter(),
        generator=RetainedRefinementGenerator(),
        config=SAGEConfig(
            registry_dir=tmp_path / "registry",
            max_new_tools=0,
            max_refinements=1,
        ),
    )

    summary = agent.run(limit=1)

    assert summary.tools_born == 0
    assert summary.tools_refined == 1
    assert summary.birth_task_retry_successes == 1
    assert summary.tasks_succeeded == 1


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


def test_standalone_dashboard_exports_env_neutral_run(tmp_path: Path) -> None:
    agent = SAGEAgent(
        adapter=CyberGymAdapter(repo_root=Path("external/cybergym")),
        generator=TemplateHelperGenerator(),
        config=SAGEConfig(registry_dir=tmp_path / "registry"),
    )

    summary = agent.run(limit=2)
    dashboard_path = write_standalone_dashboard(
        summary,
        tmp_path / "run",
        registry_path=tmp_path / "registry" / "sage_registry.json",
        baseline={
            "policy": "no_generated_helpers",
            "tasks_seen": 2,
            "tasks_succeeded": 0,
            "success_rate": 0.0,
            "results": [],
        },
        run_metadata={
            "execution_mode": "cybergym_synthetic_probe",
            "benchmark_ready": False,
            "available_tasks": 2,
            "requested_limit": 2,
            "real_task_generator_used": False,
            "real_submission_server_used": False,
            "real_poc_verifier_used": False,
            "interpretation": "Probe only.",
            "setup_notes": ("No real verifier used.",),
        },
    )

    html = dashboard_path.read_text(encoding="utf-8")
    assert "SAGE Standalone Dashboard" in html
    assert "cybergym" in html
    assert "Baseline success" in html
    assert "Relative lift" in html
    assert "Run Mode" in html
    assert "cybergym_synthetic_probe" in html
    assert (tmp_path / "run" / "summary.json").exists()
    assert (tmp_path / "run" / "dashboard_data.json").exists()


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


class RetainedRefinementGenerator(TemplateHelperGenerator):
    @staticmethod
    def bad_candidate() -> HelperCandidate:
        return HelperCandidate(
            spec=HelperSpec(
                name="constant_helper",
                family="constant",
                description="Return the retained value.",
            ),
            code=(
                "def constant_helper() -> dict:\n"
                "    return {'value': 'bad', 'abstain': False}\n"
            ),
            validation_cases=(
                ValidationCase(
                    name="bad_case",
                    inputs={},
                    expected={"value": "bad", "abstain": False},
                ),
            ),
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
        del gap, profile, rejected, errors, validation_cases, model
        return HelperCandidate(
            spec=HelperSpec(
                name="constant_helper",
                family="constant",
                description="Return the repaired retained value.",
            ),
            code=(
                "def constant_helper() -> dict:\n"
                "    return {'value': 'good', 'abstain': False}\n"
            ),
            validation_cases=(
                ValidationCase(
                    name="good_case",
                    inputs={},
                    expected={"value": "good", "abstain": False},
                ),
            ),
        )


class RefinementAdapter:
    def profile(self) -> EnvironmentProfile:
        return EnvironmentProfile(
            name="refinement-test",
            description="Synthetic environment for retained helper refinement.",
            helper_families=("constant",),
        )

    def prepare(self) -> None:
        return None

    def tasks(self, *, limit: int | None = None) -> tuple[TaskSpec, ...]:
        tasks = (
            TaskSpec(
                task_id="refine-1",
                name="refine retained helper",
                prompt="Return good.",
            ),
        )
        return tasks[:limit] if limit is not None else tasks

    def route_helpers(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> tuple[str, ...]:
        del task
        return tuple(helpers)

    def run_task(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> TaskRunResult:
        if not helpers:
            return TaskRunResult(task=task, success=False)
        name, record = next(iter(helpers.items()))
        success = "'good'" in record.candidate.code
        return TaskRunResult(
            task=task,
            success=success,
            score=1.0 if success else 0.0,
            tool_uses=(
                ToolUseRecord(
                    tool_name=name,
                    success=True,
                    generated_helper=True,
                ),
            ),
        )

    def observe_gap(
        self,
        task: TaskSpec,
        result: TaskRunResult,
        helpers: Mapping[str, HelperRecord],
    ) -> GapSignal | None:
        del helpers
        if result.success:
            return None
        return GapSignal(
            key="constant_gap",
            summary="Repair the retained helper when natural use underperforms.",
            source_task_id=task.task_id,
            source_environment="refinement-test",
            suggested_tool_name="constant_helper",
            suggested_helper_family="constant",
            required_inputs={},
            expected_outputs={"value": "str", "abstain": "bool"},
        )

    def validation_cases_for_gap(self, gap: GapSignal) -> tuple[ValidationCase, ...]:
        del gap
        return (
            ValidationCase(
                name="good_case",
                inputs={},
                expected={"value": "good", "abstain": False},
            ),
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
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> tuple[str, ...]:
        del task, helpers
        return ()

    def run_task(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> TaskRunResult:
        del helpers
        return TaskRunResult(task=task, success=False)

    def observe_gap(
        self,
        task: TaskSpec,
        result: TaskRunResult,
        helpers: Mapping[str, HelperRecord],
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
