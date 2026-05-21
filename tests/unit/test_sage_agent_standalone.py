import json
from collections.abc import Mapping
from pathlib import Path

from sage_agent import SAGEAgent, SAGEConfig
from sage_agent.adapters import (
    BBHAdapter,
    CyberGymAdapter,
    ToolSandboxMiniAdapter,
    ToolSandboxScenarioProbeAdapter,
)
from sage_agent.dashboard import write_standalone_dashboard
from sage_agent.gap_mining import mine_gap_signals
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
from sage_agent.validation import validate_helper_candidate


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
    assert summary.birth_task_retry_successes >= 1


def test_standalone_sage_bbh_adapter_uses_private_targets_and_reuses_symbolic_helper(
    tmp_path: Path,
) -> None:
    bbh_dir = tmp_path / "bbh_repo" / "bbh"
    bbh_dir.mkdir(parents=True)
    examples = {
        "boolean_expressions": {
            "input": "not ( True ) and ( True ) is",
            "target": "False",
        },
        "multistep_arithmetic_two": {
            "input": "((-1 + 2 + 9 * 5) - (-2 + -4 + -4 * -7)) =",
            "target": "24",
        },
        "dyck_languages": {
            "input": (
                "Complete the rest of the sequence, making sure that the "
                "parentheses are closed properly. Input: < [ ["
            ),
            "target": "] ] >",
        },
        "word_sorting": {
            "input": "Sort the following words alphabetically: List: zebra apple middle",
            "target": "apple middle zebra",
        },
    }
    for family, example in examples.items():
        (bbh_dir / f"{family}.json").write_text(
            json.dumps({"examples": [example]}, indent=2),
            encoding="utf-8",
        )

    adapter = BBHAdapter(repo_root=tmp_path / "bbh_repo")
    tasks = adapter.tasks(limit=4)

    assert {task.metadata["task_family"] for task in tasks} == set(examples)
    assert all("target" not in task.metadata for task in tasks)
    assert all("target" not in task.artifacts for task in tasks)
    assert check_task_specs(tasks, ResearchIntegrityPolicy()).passed

    agent = SAGEAgent(
        adapter=adapter,
        generator=TemplateHelperGenerator(),
        config=SAGEConfig(registry_dir=tmp_path / "registry"),
    )

    summary = agent.run(limit=4)

    assert summary.environment == "bbh"
    assert summary.tools_born == 1
    assert summary.tools_accepted == 1
    assert summary.tasks_succeeded == 4


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
    assert summary.birth_task_retry_successes >= 1
    assert summary.tasks_succeeded == 1


def test_standalone_sage_parks_weak_helper_after_failed_redesign(
    tmp_path: Path,
) -> None:
    registry = LocalSAGERegistry(tmp_path / "registry")
    registry.add(
        NoOpRepairGenerator.weak_candidate(),
        HelperValidationReport(
            accepted=True,
            cases_run=1,
            cases_passed=1,
            runtime_smoke_passed=True,
            side_effect_free=True,
        ),
        birth_gap_key="weak_gap",
        birth_environment="weak-helper-test",
    )
    agent = SAGEAgent(
        adapter=WeakHelperAdapter(),
        generator=NoOpRepairGenerator(),
        config=SAGEConfig(
            registry_dir=tmp_path / "registry",
            max_new_tools=0,
            max_refinements=4,
            min_uses_before_lifecycle_action=1,
            failed_repair_limit_before_parking=2,
        ),
    )

    summary = agent.run(limit=2)
    records = registry.load()

    assert records["weak_helper"].retired is True
    assert any(event["event"] == "tool_parked" for event in summary.events)


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
    assert dashboard_path.name == "task_compare.html"
    assert "Task Compare" in html
    assert "cybergym" in html
    assert "Baseline Score" in html
    assert "Outcome Lift" in html
    assert "Universal SAGE" in html
    assert "cybergym_synthetic_probe" in html
    assert (tmp_path / "run" / "summary.json").exists()
    assert (tmp_path / "run" / "dashboard_data.json").exists()
    assert (tmp_path / "run" / "dashboard" / "task_compare_data.json").exists()
    assert (tmp_path / "run" / "dashboard" / "index.html").exists()


def test_generic_gap_mining_splits_candidate_failures_into_multiple_hypotheses() -> (
    None
):
    profile = EnvironmentProfile(
        name="portable-candidate-env",
        description="Generic candidate submission environment.",
        base_tools=("submit_candidate",),
        action_tools=("submit_candidate",),
        observation_fields=("description", "artifact_summary", "attempts"),
    )
    task = TaskSpec(
        task_id="portable-1",
        name="parse structured input",
        prompt="Submit an input for an XML parser.",
        artifacts={
            "description": "Parser reads XML.",
            "artifact_summary": "literal: MAGIC_HEADER\nsource_line: size=4294967295",
        },
    )
    result = TaskRunResult(
        task=task,
        success=False,
        transcript=("candidate 0: exit_code=0 len=4",),
        artifacts={"attempts": [{"exit_code": 0, "poc_length": 4}]},
    )

    gaps = mine_gap_signals(profile=profile, task=task, result=result, helpers={})
    keys = {gap.key for gap in gaps}

    assert "visible_artifact_literal_candidate_extraction" in keys
    assert "source_boundary_value_candidate_planning" in keys
    assert "execution_feedback_candidate_mutation" in keys
    assert "structured_input_format_candidate_planning" in keys


def test_standalone_sage_can_birth_sibling_helpers_from_generic_gap_mining(
    tmp_path: Path,
) -> None:
    agent = SAGEAgent(
        adapter=GenericCandidateAdapter(),
        generator=TemplateHelperGenerator(),
        config=SAGEConfig(registry_dir=tmp_path / "registry", max_new_tools=4),
    )

    summary = agent.run(limit=1)

    assert summary.tools_born >= 4
    assert summary.tools_accepted >= 4
    assert summary.birth_task_retry_successes >= 1
    assert summary.tasks_succeeded == 1


def test_source_boundary_candidate_planner_validates_without_repair() -> None:
    gap = GapSignal(
        key="source_boundary_value_candidate_planning",
        summary="Generate source-boundary candidates.",
        source_task_id="portable-1",
        source_environment="portable-candidate-env",
        suggested_tool_name="plan_source_boundary_input_candidates",
        suggested_helper_family="source_boundary_candidate_planner",
        required_inputs={
            "description": "str",
            "readme": "str",
            "feedback": "str",
            "artifact_summary": "str",
            "max_candidates": "int",
        },
        expected_outputs={
            "candidates": "list[str]",
            "candidate_count": "int",
            "first_candidate": "str",
            "abstain": "bool",
        },
        generation_directives={"template": "source_boundary_candidate_planner"},
    )
    adapter = GenericCandidateAdapter()
    candidate = TemplateHelperGenerator().generate(
        gap,
        adapter.profile(),
        adapter.validation_cases_for_gap(gap),
        model="gpt-4o-mini",
    )
    report = validate_helper_candidate(candidate)

    assert report.accepted, report.errors


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


class GenericCandidateAdapter:
    def profile(self) -> EnvironmentProfile:
        return EnvironmentProfile(
            name="portable-candidate-env",
            description="Generic candidate submission environment.",
            base_tools=("submit_candidate",),
            action_tools=("submit_candidate",),
            observation_fields=("description", "artifact_summary", "attempts"),
            helper_families=(
                "visible_text_candidate_planner",
                "artifact_literal_candidate_planner",
                "source_boundary_candidate_planner",
                "execution_feedback_candidate_mutation_planner",
                "structured_input_candidate_planner",
            ),
            safety_rules=("helpers prepare candidates but do not submit them",),
        )

    def prepare(self) -> None:
        return None

    def tasks(self, *, limit: int | None = None) -> tuple[TaskSpec, ...]:
        tasks = (
            TaskSpec(
                task_id="portable-1",
                name="parse structured input",
                prompt="Submit an input for an XML parser.",
                artifacts={
                    "description": "Parser reads XML.",
                    "artifact_summary": (
                        "literal: MAGIC_HEADER\nsource_line: size=4294967295"
                    ),
                },
            ),
        )
        return tasks[:limit] if limit is not None else tasks

    def route_helpers(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> tuple[str, ...]:
        del task
        return tuple(name for name, record in helpers.items() if not record.retired)[:4]

    def run_task(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> TaskRunResult:
        success = len(helpers) >= 3
        return TaskRunResult(
            task=task,
            success=success,
            score=1.0 if success else 0.0,
            outcome_score=1.0 if success else 0.0,
            transcript=("candidate 0: exit_code=0 len=4",),
            tool_uses=tuple(
                ToolUseRecord(name, generated_helper=True, success=True)
                for name in helpers
            ),
            artifacts={"attempts": [{"exit_code": 0, "poc_length": 4}]},
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
            key="visible_text_candidate_planning_from_context",
            summary="Create side-effect-free candidate strings from visible context.",
            source_task_id=task.task_id,
            source_environment="portable-candidate-env",
            severity=0.8,
            suggested_tool_name="plan_visible_text_input_candidates",
            suggested_helper_family="visible_text_candidate_planner",
            evidence=("visible description",),
            required_inputs={
                "description": "str",
                "readme": "str",
                "feedback": "str",
                "artifact_summary": "str",
                "max_candidates": "int",
            },
            expected_outputs={
                "candidates": "list[str]",
                "candidate_count": "int",
                "first_candidate": "str",
                "abstain": "bool",
            },
            generation_directives={"template": "visible_text_candidate_planner"},
        )

    def validation_cases_for_gap(self, gap: GapSignal) -> tuple[ValidationCase, ...]:
        template = str(gap.generation_directives.get("template", ""))
        if template == "artifact_literal_candidate_planner":
            return (
                ValidationCase(
                    name="literal",
                    inputs={
                        "description": "",
                        "readme": "",
                        "feedback": "",
                        "artifact_summary": "literal: MAGIC_HEADER",
                        "max_candidates": 2,
                    },
                    expected={
                        "candidate_count": 2,
                        "first_candidate": "MAGIC_HEADER",
                        "abstain": False,
                    },
                ),
            )
        if template == "source_boundary_candidate_planner":
            return (
                ValidationCase(
                    name="source-boundary",
                    inputs={
                        "description": "",
                        "readme": "",
                        "feedback": "",
                        "artifact_summary": (
                            "literal: MAGIC_HEADER\n"
                            "source_line: if (size == 4294967295) crash();"
                        ),
                        "max_candidates": 2,
                    },
                    expected={
                        "candidate_count": 2,
                        "first_candidate": "MAGIC_HEADER",
                        "abstain": False,
                    },
                ),
            )
        if template == "execution_feedback_candidate_mutation_planner":
            return (
                ValidationCase(
                    name="feedback",
                    inputs={
                        "description": "",
                        "readme": "",
                        "feedback": "candidate 0: exit_code=0 len=4",
                        "artifact_summary": "",
                        "max_candidates": 2,
                    },
                    expected={
                        "candidate_count": 2,
                        "first_candidate": "",
                        "abstain": False,
                    },
                ),
            )
        if template == "structured_input_candidate_planner":
            return (
                ValidationCase(
                    name="xml",
                    inputs={
                        "description": "XML parser",
                        "readme": "",
                        "feedback": "",
                        "artifact_summary": "",
                        "max_candidates": 2,
                    },
                    expected={
                        "candidate_count": 2,
                        "first_candidate": "<a/>",
                        "abstain": False,
                    },
                ),
            )
        return (
            ValidationCase(
                name="visible",
                inputs={
                    "description": "Example input: MAGIC_HEADER",
                    "readme": "",
                    "feedback": "",
                    "artifact_summary": "",
                    "max_candidates": 2,
                },
                expected={
                    "candidate_count": 2,
                    "first_candidate": "MAGIC_HEADER",
                    "abstain": False,
                },
            ),
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


class NoOpRepairGenerator(TemplateHelperGenerator):
    @staticmethod
    def weak_candidate() -> HelperCandidate:
        return HelperCandidate(
            spec=HelperSpec(
                name="weak_helper",
                family="weak",
                description="A retained helper that does not solve the task.",
            ),
            code=(
                "def weak_helper() -> dict:\n"
                "    return {'value': 'still_bad', 'abstain': False}\n"
            ),
            validation_cases=(
                ValidationCase(
                    name="weak_case",
                    inputs={},
                    expected={"value": "still_bad", "abstain": False},
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
        del gap, profile, errors, validation_cases, model
        return rejected


class WeakHelperAdapter:
    def profile(self) -> EnvironmentProfile:
        return EnvironmentProfile(
            name="weak-helper-test",
            description="Synthetic environment for parking weak helpers.",
            helper_families=("weak",),
        )

    def prepare(self) -> None:
        return None

    def tasks(self, *, limit: int | None = None) -> tuple[TaskSpec, ...]:
        tasks = (
            TaskSpec(task_id="weak-1", name="weak retained helper 1", prompt="Solve."),
            TaskSpec(task_id="weak-2", name="weak retained helper 2", prompt="Solve."),
        )
        return tasks[:limit] if limit is not None else tasks

    def route_helpers(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> tuple[str, ...]:
        del task
        return tuple(name for name, record in helpers.items() if not record.retired)

    def run_task(
        self, task: TaskSpec, helpers: Mapping[str, HelperRecord]
    ) -> TaskRunResult:
        return TaskRunResult(
            task=task,
            success=False,
            score=0.0,
            tool_uses=tuple(
                ToolUseRecord(
                    tool_name=name,
                    success=True,
                    generated_helper=True,
                )
                for name in helpers
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
            key="weak_gap",
            summary="Redesign a retained helper after weak natural reuse evidence.",
            source_task_id=task.task_id,
            source_environment="weak-helper-test",
            suggested_tool_name="weak_helper",
            suggested_helper_family="weak",
            required_inputs={},
            expected_outputs={"value": "str", "abstain": "bool"},
        )

    def validation_cases_for_gap(self, gap: GapSignal) -> tuple[ValidationCase, ...]:
        del gap
        return (
            ValidationCase(
                name="weak_case",
                inputs={},
                expected={"value": "still_bad", "abstain": False},
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
