import json
import tarfile
import zipfile
from collections.abc import Callable, Mapping, Sequence
from io import BytesIO
from pathlib import Path
from typing import Any, cast

from pytest import MonkeyPatch

from sage_agent import SAGEAgent, SAGEConfig
from sage_agent.adapters import (
    BBHAdapter,
    CyberGymAdapter,
    ScienceAgentBenchProbeAdapter,
    TauBenchProbeAdapter,
    TerminalBenchProbeAdapter,
    ToolSandboxMiniAdapter,
    ToolSandboxScenarioProbeAdapter,
)
from sage_agent.dashboard import write_standalone_dashboard
from sage_agent.gap_mining import mine_gap_signals
from sage_agent.generators import OpenAIHelperGenerator, TemplateHelperGenerator
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


def test_repository_probe_adapters_are_runnable_dataset_choices(
    tmp_path: Path,
) -> None:
    tau_root = tmp_path / "tau2-bench"
    tau_domain = tau_root / "data/tau2/domains/airline"
    tau_domain.mkdir(parents=True)
    (tau_domain / "tasks.json").write_text(
        json.dumps(
            [
                {
                    "id": "0",
                    "description": {"purpose": "Refuse unsupported cancellation."},
                    "user_scenario": {
                        "instructions": {"reason_for_call": "Cancel a trip."}
                    },
                },
                {
                    "id": "1",
                    "description": {"purpose": "Update a reservation."},
                    "user_scenario": {
                        "instructions": {"reason_for_call": "Change a seat."}
                    },
                },
            ]
        ),
        encoding="utf-8",
    )

    terminal_root = tmp_path / "terminal-bench"
    terminal_task = terminal_root / "original-tasks/jsonl-aggregator"
    terminal_task.mkdir(parents=True)
    (terminal_task / "task.yaml").write_text(
        "instruction: Aggregate JSONL files.\n"
        "category: file-operations\n"
        "difficulty: easy\n",
        encoding="utf-8",
    )

    science_root = tmp_path / "ScienceAgentBench"
    science_root.mkdir()

    adapters = (
        TauBenchProbeAdapter(repo_root=tau_root),
        TerminalBenchProbeAdapter(repo_root=terminal_root),
        ScienceAgentBenchProbeAdapter(repo_root=science_root),
    )
    policy = ResearchIntegrityPolicy()
    for index, adapter in enumerate(adapters):
        tasks = adapter.tasks(limit=2)
        assert tasks
        assert check_task_specs(tasks, policy).passed
        agent = SAGEAgent(
            adapter=adapter,
            generator=TemplateHelperGenerator(),
            config=SAGEConfig(registry_dir=tmp_path / f"registry-{index}"),
        )
        summary = agent.run(limit=2)
        assert summary.tools_accepted == 1
        assert summary.tasks_succeeded >= 1


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


def test_validation_rejects_syntax_warnings() -> None:
    candidate = HelperCandidate(
        spec=HelperSpec(
            name="bad_escape_helper",
            family="candidate_planner",
            description="Uses an invalid Python escape.",
        ),
        code=(
            "def bad_escape_helper() -> dict:\n"
            "    return {'candidates': ['\\A'], 'candidate_count': 1, "
            "'first_candidate': '\\A', 'abstain': False}\n"
        ),
        validation_cases=(
            ValidationCase(
                name="call",
                inputs={},
                expected={"candidate_count": 1, "abstain": False},
            ),
        ),
    )

    report = validate_helper_candidate(candidate)

    assert not report.accepted
    assert any("syntax_warning" in error for error in report.errors)


def test_openai_generator_uses_scaffold_for_known_template(
    monkeypatch: MonkeyPatch,
) -> None:
    def fail_if_called(*args: object, **kwargs: object) -> object:
        raise AssertionError("OpenAI client should not be called for scaffolded gaps")

    monkeypatch.setattr(OpenAIHelperGenerator, "_complete_json", fail_if_called)
    generator = OpenAIHelperGenerator.__new__(OpenAIHelperGenerator)
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
    candidate = generator.generate(
        gap,
        GenericCandidateAdapter().profile(),
        GenericCandidateAdapter().validation_cases_for_gap(gap),
        model="gpt-4o-mini",
    )

    assert candidate.spec.name == "plan_source_boundary_input_candidates"
    assert validate_helper_candidate(candidate).accepted


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
            min_uses_before_lifecycle_action=0,
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
            min_uses_before_lifecycle_action=0,
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


def test_generic_gap_mining_synthesizes_adaptive_candidate_portfolio() -> None:
    profile = EnvironmentProfile(
        name="portable-candidate-env",
        description="Generic candidate submission environment.",
        base_tools=("submit_candidate",),
        action_tools=("submit_candidate",),
        observation_fields=("description", "artifact_summary", "attempts"),
    )
    task = TaskSpec(
        task_id="portable-2",
        name="source candidate task",
        prompt="Submit an input for a visible parser.",
        artifacts={
            "description": "Parser reads structured input.",
            "artifact_summary": (
                "literal: MAGIC_HEADER\nsource_line: if (size == 4294967295) crash();"
            ),
        },
    )
    result = TaskRunResult(
        task=task,
        success=False,
        transcript=(
            "candidate 0: exit_code=0 len=4",
            "candidate 1: exit_code=0 len=8",
        ),
        artifacts={
            "attempts": [
                {"exit_code": 0, "poc_length": 4},
                {"exit_code": 0, "poc_length": 8},
                {"exit_code": 0, "poc_length": 16},
                {"exit_code": 0, "poc_length": 32},
            ]
        },
    )
    helpers = {
        "a": _helper_record_for_family("source_boundary_candidate_planner"),
        "b": _helper_record_for_family("artifact_literal_candidate_planner"),
    }

    gaps = mine_gap_signals(profile=profile, task=task, result=result, helpers=helpers)

    assert "adaptive_candidate_portfolio_planning" in {gap.key for gap in gaps}


def test_generic_gap_mining_escalates_to_visible_evidence_portfolio() -> None:
    profile = EnvironmentProfile(
        name="portable-candidate-env",
        description="Generic candidate submission environment.",
        base_tools=("submit_candidate",),
        action_tools=("submit_candidate",),
        observation_fields=("description", "artifact_summary", "attempts"),
    )
    task = TaskSpec(
        task_id="portable-portfolio",
        name="candidate task with weak planners",
        prompt="Submit an input for the visible parser.",
        artifacts={
            "description": "Parser reads XML and regex-like input.",
            "artifact_summary": (
                "literal: MAGIC_HEADER\nsource_line: if (size == 4294967295) crash();"
            ),
        },
    )
    result = TaskRunResult(
        task=task,
        success=False,
        transcript=(
            "candidate 0: exit_code=0 len=4",
            "candidate 1: exit_code=0 len=8",
        ),
        artifacts={
            "attempts": [
                {"exit_code": 0, "poc_length": 4},
                {"exit_code": 0, "poc_length": 8},
                {"exit_code": 0, "poc_length": 16},
                {"exit_code": 0, "poc_length": 32},
            ]
        },
    )
    helpers = {
        "source": _helper_record_for_family("source_boundary_candidate_planner"),
        "literal": _helper_record_for_family("artifact_literal_candidate_planner"),
        "adaptive": _helper_record_for_family("adaptive_candidate_portfolio_planner"),
    }

    gaps = mine_gap_signals(profile=profile, task=task, result=result, helpers=helpers)

    assert "visible_evidence_budgeted_portfolio_planning" in {gap.key for gap in gaps}


def test_generic_gap_mining_detects_public_harness_envelope_gap() -> None:
    profile = EnvironmentProfile(
        name="portable-candidate-env",
        description="Generic candidate submission environment.",
        base_tools=("submit_candidate",),
        action_tools=("submit_candidate",),
        observation_fields=("description", "artifact_summary", "attempts"),
    )
    task = TaskSpec(
        task_id="portable-harness",
        name="candidate task with visible fuzzer harness",
        prompt="Submit an input for the visible public fuzzer.",
        artifacts={
            "description": "The decoder target exposes LLVMFuzzerTestOneInput.",
            "artifact_summary": (
                "source_line: size_t preamble = 2 + 2 + 1 + sizeof(NeAACDecConfiguration);\n"
                "source_line: size_t len1 = data[0] | (data[1] << 8);\n"
                "source_line: size_t len2 = data[0] | (data[1] << 8);"
            ),
        },
    )
    result = TaskRunResult(
        task=task,
        success=False,
        transcript=("candidate 0: exit_code=0 len=4",),
        artifacts={"attempts": [{"exit_code": 0, "poc_length": 4}]},
    )

    gaps = mine_gap_signals(profile=profile, task=task, result=result, helpers={})

    assert "public_harness_envelope_candidate_planning" in {gap.key for gap in gaps}


def test_generic_gap_mining_detects_public_crash_pattern_gap() -> None:
    profile = EnvironmentProfile(
        name="portable-candidate-env",
        description="Generic candidate submission environment.",
        base_tools=("submit_candidate",),
        action_tools=("submit_candidate",),
        observation_fields=("description", "artifact_summary", "attempts"),
    )
    task = TaskSpec(
        task_id="portable-public-pattern",
        name="candidate task with visible public parser cues",
        prompt="Submit an input for the visible public parser.",
        artifacts={
            "description": "PCRE2 fuzzsupport has an overwriting bug when input text is very short.",
            "artifact_summary": (
                "source_line: #include <magic.h>\n"
                "source_line: magic_buffer(env->magic, data, size);\n"
                "--with-html             HTML parser (on)"
            ),
        },
    )
    result = TaskRunResult(
        task=task,
        success=False,
        transcript=("candidate 0: exit_code=0 len=4",),
        artifacts={"attempts": [{"exit_code": 0, "poc_length": 4}]},
    )

    gaps = mine_gap_signals(profile=profile, task=task, result=result, helpers={})

    assert "public_crash_pattern_candidate_planning" in {gap.key for gap in gaps}


def test_standalone_sage_can_birth_sibling_helpers_from_generic_gap_mining(
    tmp_path: Path,
) -> None:
    agent = SAGEAgent(
        adapter=GenericCandidateAdapter(),
        generator=TemplateHelperGenerator(),
        config=SAGEConfig(
            registry_dir=tmp_path / "registry",
            max_new_tools=4,
            max_new_tools_per_task=3,
        ),
    )

    summary = agent.run(limit=1)

    assert summary.tools_born == 3
    assert summary.tools_accepted == 3
    assert summary.birth_task_retry_successes >= 1
    assert summary.tasks_succeeded == 1
    assert not any(
        event.get("tool_name") == "mutate_candidates_from_execution_feedback"
        for event in summary.events
    )


def test_standalone_sage_can_continue_same_task_gap_mining_when_configured(
    tmp_path: Path,
) -> None:
    agent = SAGEAgent(
        adapter=GenericCandidateAdapter(),
        generator=TemplateHelperGenerator(),
        config=SAGEConfig(
            registry_dir=tmp_path / "registry",
            max_new_tools=4,
            max_new_tools_per_task=4,
            stop_task_gap_processing_after_successful_retry=False,
        ),
    )

    summary = agent.run(limit=1)

    assert summary.tools_born >= 4
    assert summary.tools_accepted >= 4


def test_standalone_sage_can_defer_birth_retries_for_expensive_environments(
    tmp_path: Path,
) -> None:
    agent = SAGEAgent(
        adapter=GenericCandidateAdapter(),
        generator=TemplateHelperGenerator(),
        config=SAGEConfig(
            registry_dir=tmp_path / "registry",
            max_new_tools=4,
            max_new_tools_per_task=3,
            defer_birth_task_retries=True,
        ),
    )

    summary = agent.run(limit=1)

    assert summary.tools_born == 3
    assert summary.tools_accepted == 3
    assert summary.birth_task_retries == 1
    assert summary.birth_task_retry_successes == 1
    assert summary.tasks_succeeded == 1
    assert any(
        event["event"] == "birth_task_retry_deferred" for event in summary.events
    )
    assert any(
        event["event"] == "deferred_birth_task_retry" for event in summary.events
    )


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


def test_adaptive_candidate_portfolio_planner_validates_without_repair() -> None:
    gap = GapSignal(
        key="adaptive_candidate_portfolio_planning",
        summary="Synthesize candidate planners into an adaptive portfolio.",
        source_task_id="portable-2",
        source_environment="portable-candidate-env",
        suggested_tool_name="plan_adaptive_candidate_portfolio",
        suggested_helper_family="adaptive_candidate_portfolio_planner",
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
        generation_directives={"template": "adaptive_candidate_portfolio_planner"},
    )
    candidate = TemplateHelperGenerator().generate(
        gap,
        GenericCandidateAdapter().profile(),
        (
            ValidationCase(
                name="adaptive_visible_artifacts",
                inputs={
                    "description": "Input parser reads XML and size fields.",
                    "readme": "",
                    "feedback": "candidate 0: exit_code=0 len=4",
                    "artifact_summary": (
                        "literal: MAGIC_HEADER\n"
                        "source_line: if (size == 4294967295) crash();"
                    ),
                    "max_candidates": 4,
                },
                expected={
                    "candidate_count": 4,
                    "first_candidate": "MAGIC_HEADER",
                    "abstain": False,
                },
            ),
        ),
        model="gpt-4o-mini",
    )
    report = validate_helper_candidate(candidate)

    assert report.accepted, report.errors


def test_visible_evidence_portfolio_planner_validates_without_repair() -> None:
    gap = GapSignal(
        key="visible_evidence_budgeted_portfolio_planning",
        summary="Budget candidate generation across visible evidence families.",
        source_task_id="portable-portfolio",
        source_environment="portable-candidate-env",
        suggested_tool_name="plan_visible_evidence_candidate_portfolio",
        suggested_helper_family="visible_evidence_portfolio_candidate_planner",
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
        generation_directives={
            "template": "visible_evidence_portfolio_candidate_planner"
        },
    )
    candidate = TemplateHelperGenerator().generate(
        gap,
        GenericCandidateAdapter().profile(),
        (
            ValidationCase(
                name="visible-evidence-budget",
                inputs={
                    "description": "Regex, XML, htslib BAM/CRAM, and numeric edges.",
                    "readme": "Submit candidate input strings only.",
                    "feedback": "candidate 0: exit_code=0 len=4",
                    "artifact_summary": (
                        "sample_escape: MZ\\x90\\x00PE\\x00\\x00A\n"
                        "literal: MAGIC_HEADER\n"
                        "dict: \\\\A\n"
                        "--with-html             HTML parser (on)\n"
                        "source_line: #include <magic.h>\n"
                        "source_line: if (size == 4294967295) crash();"
                    ),
                    "max_candidates": 10,
                },
                expected={
                    "abstain": False,
                    "candidates_min_unique": 8,
                    "candidates_contains_any_fragment": (
                        "MAGIC_HEADER",
                        "#include <magic.h>",
                        "4294967295",
                        "\\A",
                        "BAM",
                        "CRAM",
                        "--with-html",
                    ),
                    "candidates_max_count": 10,
                },
            ),
        ),
        model="gpt-4o-mini",
    )
    report = validate_helper_candidate(candidate)

    assert report.accepted, report.errors


def test_harness_envelope_candidate_planner_validates_and_builds_wrappers() -> None:
    gap = GapSignal(
        key="public_harness_envelope_candidate_planning",
        summary="Build public harness-envelope candidate inputs.",
        source_task_id="portable-harness",
        source_environment="portable-candidate-env",
        suggested_tool_name="plan_public_harness_envelope_candidates",
        suggested_helper_family="harness_envelope_candidate_planner",
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
        generation_directives={"template": "harness_envelope_candidate_planner"},
    )
    candidate = TemplateHelperGenerator().generate(
        gap,
        GenericCandidateAdapter().profile(),
        (
            ValidationCase(
                name="public_harness_envelopes",
                inputs={
                    "description": "Visible LLVMFuzzerTestOneInput AAC decoder harness.",
                    "readme": "Submit candidate input strings only.",
                    "feedback": "candidate 0: exit_code=0 len=4",
                    "artifact_summary": (
                        "source_line: size_t preamble = 2 + 2 + 1 + sizeof(NeAACDecConfiguration);\n"
                        "source_line: size_t len1 = data[0] | (data[1] << 8);\n"
                        "source_line: xmlFuzzReadEntities();"
                    ),
                    "max_candidates": 8,
                },
                expected={
                    "abstain": False,
                    "candidates_min_unique": 4,
                    "candidates_contains_any_fragment": ("\xff\xf1", "main.xml"),
                    "candidates_max_count": 8,
                },
            ),
        ),
        model="gpt-4o-mini",
    )
    report = validate_helper_candidate(candidate)

    assert report.accepted, report.errors


def test_public_crash_pattern_candidate_planner_validates_reviewed_patterns() -> None:
    gap = GapSignal(
        key="public_crash_pattern_candidate_planning",
        summary="Build manually reviewed public-pattern candidate inputs.",
        source_task_id="portable-public-pattern",
        source_environment="portable-candidate-env",
        suggested_tool_name="plan_public_crash_pattern_candidates",
        suggested_helper_family="public_crash_pattern_candidate_planner",
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
        generation_directives={"template": "public_crash_pattern_candidate_planner"},
    )
    candidate = TemplateHelperGenerator().generate(
        gap,
        GenericCandidateAdapter().profile(),
        (
            ValidationCase(
                name="manual_public_patterns",
                inputs={
                    "description": (
                        "PCRE2 fuzzsupport with very short input and libxml2 "
                        "xmlSearchNsSafe public parser cues."
                    ),
                    "readme": "",
                    "feedback": "candidate 0: exit_code=0 len=4",
                    "artifact_summary": (
                        "source_line: #include <magic.h>\n"
                        "source_line: magic_buffer(env->magic, data, size);\n"
                        "source_line: jpeg_write_raw_data MCU padding\n"
                        "--with-html             HTML parser (on)"
                    ),
                    "max_candidates": 12,
                },
                expected={
                    "abstain": False,
                    "candidates_contains_any_fragment": (
                        "#include <magic.h>",
                        "0E-100000",
                        "MZ",
                        "--with-html",
                    ),
                    "candidates_max_count": 12,
                },
            ),
        ),
        model="gpt-4o-mini",
    )
    report = validate_helper_candidate(candidate)

    assert report.accepted, report.errors


def test_public_local_search_candidate_planner_validates_search_request() -> None:
    gap = GapSignal(
        key="public_local_search_candidate_planning",
        summary="Request bounded public vulnerable-side search from visible cues.",
        source_task_id="public-search",
        source_environment="portable-candidate-env",
        suggested_tool_name="plan_public_local_fuzz_search_candidates",
        suggested_helper_family="public_local_search_candidate_planner",
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
        generation_directives={"template": "public_local_search_candidate_planner"},
    )
    candidate = TemplateHelperGenerator().generate(
        gap,
        GenericCandidateAdapter().profile(),
        (
            ValidationCase(
                name="public_runtime_search",
                inputs={
                    "description": "Visible fuzzer with public seed corpus.",
                    "readme": "Submit one candidate input.",
                    "feedback": "candidate 0: exit_code=0 len=4",
                    "artifact_summary": (
                        "runtime_binary: xaac_dec_fuzzer\n"
                        "source_line: LLVMFuzzerTestOneInput(data, size)\n"
                        "corpus_sample: \\xff\\xf1\\x50\\x80"
                    ),
                    "max_candidates": 8,
                },
                expected={
                    "abstain": False,
                    "candidates_contains": ("search_strategy: public_local_fuzz",),
                    "candidates_contains_any_fragment": (
                        "runtime_binary",
                        "corpus_sample",
                    ),
                    "candidates_max_count": 8,
                },
            ),
        ),
        model="gpt-4o-mini",
    )
    report = validate_helper_candidate(candidate)

    assert report.accepted, report.errors


def test_candidate_validation_allows_visible_fragments_inside_candidates() -> None:
    gap = GapSignal(
        key="adaptive_candidate_portfolio_planning",
        summary="Synthesize candidate planners into an adaptive portfolio.",
        source_task_id="portable-fragment",
        source_environment="portable-candidate-env",
        suggested_tool_name="plan_adaptive_candidate_portfolio",
        suggested_helper_family="adaptive_candidate_portfolio_planner",
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
        generation_directives={"template": "adaptive_candidate_portfolio_planner"},
    )
    candidate = TemplateHelperGenerator().generate(
        gap,
        GenericCandidateAdapter().profile(),
        (
            ValidationCase(
                name="visible_fragment_preserved",
                inputs={
                    "description": "Parser reads visible source constants.",
                    "readme": "",
                    "feedback": "",
                    "artifact_summary": (
                        "literal: MAGIC_HEADER\n"
                        "source_line: if (size == 4294967295) crash();"
                    ),
                    "max_candidates": 4,
                },
                expected={
                    "first_candidate": "MAGIC_HEADER",
                    "abstain": False,
                    "candidates_contains_any_fragment": ("4294967295",),
                },
            ),
        ),
        model="gpt-4o-mini",
    )
    report = validate_helper_candidate(candidate)

    assert report.accepted, report.errors


def test_adaptive_candidate_portfolio_extracts_prose_examples() -> None:
    gap = GapSignal(
        key="adaptive_candidate_portfolio_planning",
        summary="Synthesize candidate planners into an adaptive portfolio.",
        source_task_id="portable-3",
        source_environment="portable-candidate-env",
        suggested_tool_name="plan_adaptive_candidate_portfolio",
        suggested_helper_family="adaptive_candidate_portfolio_planner",
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
        generation_directives={"template": "adaptive_candidate_portfolio_planner"},
    )
    candidate = TemplateHelperGenerator().generate(
        gap,
        GenericCandidateAdapter().profile(),
        (),
        model="gpt-4o-mini",
    )
    namespace: dict[str, object] = {}
    exec(  # noqa: S102
        candidate.code,
        {
            "__builtins__": {
                "all": all,
                "any": any,
                "bool": bool,
                "dict": dict,
                "int": int,
                "isinstance": isinstance,
                "len": len,
                "list": list,
                "max": max,
                "min": min,
                "range": range,
                "set": set,
                "str": str,
            }
        },
        namespace,
    )
    planner = cast(
        Callable[..., Mapping[str, Any]],
        namespace["plan_adaptive_candidate_portfolio"],
    )
    result = planner(
        description=("A parser stringifies certain numbers such as -10E-1000010001."),
        readme="Submit parser inputs only.",
        feedback="candidate 0: exit_code=0 len=4",
        artifact_summary="source_line: jv res = parse(input);",
        max_candidates=8,
    )

    candidates = result["candidates"]
    assert isinstance(candidates, list)
    assert "-10E-1000010001" in candidates
    assert "[-10E-1000010001]" in candidates


def test_format_edge_candidate_planner_validates_and_prioritizes_regex() -> None:
    gap = GapSignal(
        key="regex_format_edge_candidate_planning",
        summary="Generate regex edge candidates.",
        source_task_id="portable-4",
        source_environment="portable-candidate-env",
        suggested_tool_name="plan_regex_edge_input_candidates",
        suggested_helper_family="format_edge_candidate_planner",
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
        generation_directives={
            "template": "format_edge_candidate_planner",
            "format_kind": "regex",
        },
    )
    candidate = TemplateHelperGenerator().generate(
        gap,
        GenericCandidateAdapter().profile(),
        (
            ValidationCase(
                name="regex_edges",
                inputs={
                    "description": "The parser accepts regex input.",
                    "readme": "",
                    "feedback": "",
                    "artifact_summary": "dict: \\\\A",
                    "max_candidates": 6,
                },
                expected={"candidate_count": 6, "abstain": False},
            ),
        ),
        model="gpt-4o-mini",
    )
    report = validate_helper_candidate(candidate)

    assert report.accepted, report.errors
    namespace: dict[str, object] = {}
    exec(  # noqa: S102
        candidate.code,
        {
            "__builtins__": {
                "all": all,
                "any": any,
                "bool": bool,
                "dict": dict,
                "int": int,
                "len": len,
                "list": list,
                "max": max,
                "min": min,
                "range": range,
                "set": set,
                "str": str,
            }
        },
        namespace,
    )
    planner = cast(
        Callable[..., Mapping[str, Any]],
        namespace["plan_regex_edge_input_candidates"],
    )
    result = planner(
        description="The parser accepts PCRE regex input.",
        artifact_summary="dict: \\\\A",
        max_candidates=20,
    )
    candidates = result["candidates"]
    assert isinstance(candidates, list)
    assert any(item.endswith("A") and "\\" in item for item in candidates)
    assert "(a)\\1" in candidates


def test_semantic_description_candidate_planner_validates_and_uses_visible_cues() -> (
    None
):
    gap = GapSignal(
        key="semantic_description_candidate_planning",
        summary="Generate semantic candidate inputs from visible task text.",
        source_task_id="portable-5",
        source_environment="portable-candidate-env",
        suggested_tool_name="plan_semantic_description_input_candidates",
        suggested_helper_family="semantic_description_candidate_planner",
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
        generation_directives={"template": "semantic_description_candidate_planner"},
    )
    candidate = TemplateHelperGenerator().generate(
        gap,
        GenericCandidateAdapter().profile(),
        GenericCandidateAdapter().validation_cases_for_gap(gap),
        model="gpt-4o-mini",
    )
    report = validate_helper_candidate(candidate)

    assert report.accepted, report.errors
    namespace: dict[str, object] = {}
    exec(  # noqa: S102
        candidate.code,
        {
            "__builtins__": {
                "any": any,
                "all": all,
                "bool": bool,
                "dict": dict,
                "int": int,
                "len": len,
                "list": list,
                "set": set,
                "sorted": sorted,
                "str": str,
            }
        },
        namespace,
    )
    planner = cast(
        Callable[..., Mapping[str, Any]],
        namespace["plan_semantic_description_input_candidates"],
    )
    xml_result = planner(
        description=(
            "A type confusion vulnerability exists in XML namespace declarations "
            "and attribute ID handling."
        ),
        artifact_summary="source_line: xmlValidateOneNamespace(ctx, node)",
        max_candidates=12,
    )
    pe_result = planner(
        description="A heap overflow exists in the Portable Executable PE module.",
        artifact_summary="source_line: pe_parse_header(input)",
        max_candidates=12,
    )
    sam_result = planner(
        description="The BAM/CRAM auxiliary tag parser reads B aux tags.",
        artifact_summary="source_line: cram_encode_aux(tag)",
        max_candidates=12,
    )

    assert any("xmlns" in item for item in xml_result["candidates"])
    assert "MZ" in pe_result["candidates"]
    assert any("XX:B" in item for item in sam_result["candidates"])


def test_execution_feedback_mutation_planner_reuses_visible_failed_candidates() -> None:
    gap = GapSignal(
        key="execution_feedback_candidate_mutation",
        summary="Generate follow-up candidates from visible failed attempts.",
        source_task_id="portable-6",
        source_environment="portable-candidate-env",
        suggested_tool_name="mutate_candidates_from_execution_feedback",
        suggested_helper_family="execution_feedback_candidate_mutation_planner",
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
        generation_directives={
            "template": "execution_feedback_candidate_mutation_planner"
        },
    )
    candidate = TemplateHelperGenerator().generate(
        gap,
        GenericCandidateAdapter().profile(),
        GenericCandidateAdapter().validation_cases_for_gap(gap),
        model="gpt-4o-mini",
    )
    report = validate_helper_candidate(candidate)

    assert report.accepted, report.errors
    namespace: dict[str, object] = {}
    exec(  # noqa: S102
        candidate.code,
        {
            "__builtins__": {
                "all": all,
                "any": any,
                "bool": bool,
                "dict": dict,
                "int": int,
                "len": len,
                "list": list,
                "max": max,
                "min": min,
                "set": set,
                "str": str,
            }
        },
        namespace,
    )
    planner = cast(
        Callable[..., Mapping[str, Any]],
        namespace["mutate_candidates_from_execution_feedback"],
    )
    result = planner(
        description="The parser accepts numeric JSON input.",
        feedback="candidate 3: exit_code=0 len=14\ncandidate_text: -10E-1000010001",
        max_candidates=8,
    )

    assert "-10E-1000010001" in result["candidates"]
    assert "[-10E-1000010001]" in result["candidates"]


def test_generic_gap_mining_synthesizes_semantic_candidate_planner() -> None:
    adapter = GenericCandidateAdapter()
    task = TaskSpec(
        task_id="portable-semantic",
        name="namespace parser",
        prompt="Submit candidate input strings only.",
        artifacts={
            "description": "The visible parser handles XML namespace attributes.",
            "artifact_summary": "source_line: xmlValidateOneNamespace(ctx, node)",
        },
    )
    result = TaskRunResult(
        task=task,
        success=False,
        transcript=("candidate 0: exit_code=0 len=4",),
        artifacts={"attempts": [{"exit_code": 0, "poc_length": 4}]},
    )

    gaps = mine_gap_signals(
        profile=adapter.profile(),
        task=task,
        result=result,
        helpers={},
    )

    assert any(
        gap.suggested_helper_family == "semantic_description_candidate_planner"
        for gap in gaps
    )


def test_cybergym_artifact_priority_keeps_dictionaries_first() -> None:
    from sage_agent.adapters.cybergym_live import _artifact_member_priority

    dict_member = type("Member", (), {"name": "src/project/fuzz.dict"})()
    fuzz_member = type("Member", (), {"name": "src/project/fuzzer.cc"})()
    readme_member = type("Member", (), {"name": "README.md"})()

    assert _artifact_member_priority(dict_member) < _artifact_member_priority(
        fuzz_member
    )
    assert _artifact_member_priority(fuzz_member) < _artifact_member_priority(
        readme_member
    )


def test_candidate_batch_composer_reserves_space_for_specialized_helpers() -> None:
    from sage_agent.adapters.cybergym_live import _compose_candidate_batches

    primary = [[f"portfolio-{index}" for index in range(16)]]
    secondary = [["source-specific-1", "source-specific-2"]]

    candidates = _compose_candidate_batches(primary, secondary, limit=8)

    assert "source-specific-1" in candidates
    assert "source-specific-2" in candidates
    assert len(candidates) == 8


def test_candidate_batch_composer_anchors_multiple_primary_planners() -> None:
    from sage_agent.adapters.cybergym_live import _compose_candidate_batches

    primary = [
        ["#include <magic.h>", "magic-second"],
        ["0E-100000", "numeric-second"],
        ["--with-html             HTML parser (on)", "xml-second"],
    ]
    secondary = [["secondary-1", "secondary-2"]]

    candidates = _compose_candidate_batches(primary, secondary, limit=6)

    assert candidates[:3] == [
        "#include <magic.h>",
        "0E-100000",
        "--with-html             HTML parser (on)",
    ]


def test_candidate_submission_plan_keeps_initial_budget_and_adds_reserve() -> None:
    from sage_agent.adapters.cybergym_live import (
        _compose_candidate_batches,
        _compose_candidate_submission_plan,
    )

    primary = [
        ["#include <magic.h>", "magic-second", "magic-third"],
        ["0E-100000", "numeric-second", "numeric-third"],
    ]
    secondary = [["secondary-1", "secondary-2", "secondary-3", "secondary-4"]]

    initial = _compose_candidate_batches(primary, secondary, limit=4)
    planned = _compose_candidate_submission_plan(
        primary,
        secondary,
        limit=4,
        reserve=3,
    )

    assert planned[:4] == initial
    assert len(planned) == 7
    assert set(planned[4:]) - set(initial)


def test_cybergym_candidate_route_key_uses_natural_success_evidence() -> None:
    from sage_agent.adapters.cybergym_live import _candidate_helper_route_key

    def record(name: str, family: str, *, uses: int, successes: int) -> HelperRecord:
        return HelperRecord(
            candidate=HelperCandidate(
                spec=HelperSpec(
                    name=name,
                    family=family,
                    description="candidate planner",
                ),
                code="def helper(**kwargs):\n    return {'candidates': ['A']}\n",
            ),
            validation=HelperValidationReport(accepted=True),
            birth_gap_key="candidate_gap",
            birth_environment="cybergym-live",
            created_at="2026-05-22T00:00:00Z",
            code_hash=name,
            uses=uses,
            successes=successes,
        )

    unproven = (
        "plan_adaptive_candidate_portfolio",
        record(
            "plan_adaptive_candidate_portfolio",
            "adaptive_candidate_portfolio_planner",
            uses=10,
            successes=0,
        ),
    )
    proven = (
        "plan_source_boundary_input_candidates",
        record(
            "plan_source_boundary_input_candidates",
            "source_boundary_candidate_planner",
            uses=10,
            successes=3,
        ),
    )

    assert _candidate_helper_route_key(proven) < _candidate_helper_route_key(unproven)


def test_cybergym_candidate_route_prefers_relevant_format_edge() -> None:
    from sage_agent.adapters.cybergym_live import _candidate_helper_route_key

    def record(name: str, family: str) -> HelperRecord:
        return HelperRecord(
            candidate=HelperCandidate(
                spec=HelperSpec(
                    name=name,
                    family=family,
                    description="candidate planner",
                ),
                code=f"def {name}():\n    return {{}}\n",
            ),
            validation=HelperValidationReport(accepted=True),
            birth_gap_key="candidate_gap",
            birth_environment="cybergym-live",
            created_at="2026-05-22T00:00:00Z",
            code_hash=name,
        )

    task_text = "description: visible XML namespace parser vulnerability"
    xml = (
        "plan_xml_edge_input_candidates",
        record("plan_xml_edge_input_candidates", "format_edge_candidate_planner"),
    )
    regex = (
        "plan_regex_edge_input_candidates",
        record("plan_regex_edge_input_candidates", "format_edge_candidate_planner"),
    )
    semantic = (
        "plan_semantic_description_input_candidates",
        record(
            "plan_semantic_description_input_candidates",
            "semantic_description_candidate_planner",
        ),
    )

    assert _candidate_helper_route_key(xml, task_text) < _candidate_helper_route_key(
        semantic, task_text
    )
    assert _candidate_helper_route_key(xml, task_text) < _candidate_helper_route_key(
        regex, task_text
    )


def test_context_aware_candidate_promotion_uses_public_task_relevance() -> None:
    from sage_agent.adapters.cybergym_live import _promote_candidates_for_strategy

    candidates = [
        "MZ",
        "%PDF-1.7",
        "CRAM",
        "@HD\tVN:1.6",
        "999999999999999999999999999999999999",
    ]
    task_text = "description: htslib cram bam sam auxiliary tag parser"

    promoted = _promote_candidates_for_strategy(candidates, task_text, "context_aware")

    assert promoted.index("CRAM") < promoted.index("MZ")
    assert promoted.index("@HD\tVN:1.6") < promoted.index("%PDF-1.7")


def test_format_focus_candidate_promotion_is_task_aware_and_diverse() -> None:
    from sage_agent.adapters.cybergym_live import _promote_candidates_for_strategy

    candidates = [
        "MZ",
        "%PDF-1.7",
        "999999999999999999999999999999999999",
        "<a/>",
        "\\x00\\x00\\x00\\x00",
        "A\\x00A",
    ]
    task_text = (
        "description: uart transport binary_message packet parser fuzzer "
        "with framed input"
    )

    promoted = _promote_candidates_for_strategy(candidates, task_text, "format_focus")

    assert promoted.index("\x00\x00\x00\x00") < promoted.index("MZ")
    assert any(
        candidate.startswith("MSG") or candidate.startswith("LEN=")
        for candidate in promoted[:8]
    )


def test_format_focus_candidate_promotion_adds_public_media_shape_seeds() -> None:
    from sage_agent.adapters.cybergym_live import _promote_candidates_for_strategy

    promoted = _promote_candidates_for_strategy(
        ["MZ", "%PDF-1.7", "999999999999999999999999999999999999"],
        "description: xaac audio codec decoder fuzzer reads media frames",
        "format_focus",
    )

    assert any(
        candidate.startswith(("\xff\xf1", "\xff\xf9", "ADIF", "ID3", "RIFF"))
        for candidate in promoted[:8]
    )
    assert promoted.index("MZ") > 0


def test_generic_gap_mining_detects_binary_protocol_format() -> None:
    profile = EnvironmentProfile(
        name="portable-candidate-env",
        description="Generic candidate submission environment.",
        base_tools=("submit_candidate",),
        action_tools=("submit_candidate",),
        observation_fields=("description", "artifact_summary", "attempts"),
    )
    task = TaskSpec(
        task_id="portable-ssh",
        name="ssh protocol parser",
        prompt="Submit input for a libssh key-exchange parser.",
        artifacts={
            "description": "The parser handles SSH KEX protocol packets.",
            "artifact_summary": "source_line: kex_method = read_packet(input);",
        },
    )
    result = TaskRunResult(
        task=task,
        success=False,
        transcript=("candidate 0: exit_code=0 len=4",),
        artifacts={"attempts": [{"exit_code": 0, "poc_length": 4}]},
    )
    helpers = {
        "source": _helper_record_for_family("source_boundary_candidate_planner"),
        "literal": _helper_record_for_family("artifact_literal_candidate_planner"),
    }

    gaps = mine_gap_signals(profile=profile, task=task, result=result, helpers=helpers)

    assert gaps[0].suggested_tool_name == "plan_binary_protocol_edge_input_candidates"
    assert any(
        gap.suggested_tool_name == "plan_binary_protocol_edge_input_candidates"
        for gap in gaps
    )


def test_visible_candidate_signal_promotion_keeps_source_literals_in_budget() -> None:
    from sage_agent.adapters.cybergym_live import (
        _compose_candidate_batches,
        _promote_visible_candidate_signals,
    )

    source_candidates = [
        "License",
        "AS IS",
        "0",
        "1",
        "error loading magic file: %s\\n",
        "/magic",
        "AAAA",
        "(",
        "()",
        "<a/>",
        "#include <magic.h>",
    ]
    visible_candidates = ["A", "AAAA", "0", "1", "-1", "0\\n"]

    promoted_source = _promote_visible_candidate_signals(source_candidates)
    candidates = _compose_candidate_batches(
        [],
        [visible_candidates, promoted_source],
        limit=8,
    )

    assert "#include <magic.h>" in candidates
    assert "License" not in candidates or candidates.index(
        "#include <magic.h>"
    ) < candidates.index("License")


def test_visible_candidate_signal_promotion_uses_clean_payloads() -> None:
    from sage_agent.adapters.cybergym_live import _promote_visible_candidate_signals

    candidates = [
        "\\\\A",
        "0",
        "\\\\b",
        "\\\\B",
        "0\\n",
        "\\\\d",
        "\\\\D",
        "\\\\h",
        "dict: \\\\A",
    ]

    promoted = _promote_visible_candidate_signals(candidates)

    assert promoted.index("\\\\A") < 8
    assert "dict: \\\\A" not in promoted


def test_visible_candidate_signal_promotion_keeps_cli_options_before_xml_noise() -> (
    None
):
    from sage_agent.adapters.cybergym_live import _promote_visible_candidate_signals

    candidates = [f"dict: <tag{index}></tag{index}>" for index in range(40)]
    candidates.append("--with-html             HTML parser (on)")

    promoted = _promote_visible_candidate_signals(candidates)

    assert promoted.index("--with-html             HTML parser (on)") < 8


def test_visible_candidate_signal_promotion_prioritizes_visible_numeric_edges() -> None:
    from sage_agent.adapters.cybergym_live import _promote_visible_candidate_signals

    candidates = [
        "999999999999999999999999999999999999",
        "[![Fuzzing Status](https://oss-fuzz-build-logs.storage.googleapis.com/badges/demo.svg)](https://oss-fuzz-build-logs.storage.googleapis.com/index.html#demo)",
        "source_line: ./configure --with-parser=yes",
        'source_line: add_definitions("-DUSE_POSIX_API")',
        "-10E-1000010001",
        "-10E-1000010001\n",
        "<a/>",
    ]

    promoted = _promote_visible_candidate_signals(candidates)

    assert promoted.index("-10E-1000010001") < promoted.index(
        "./configure --with-parser=yes"
    )
    assert promoted.index("-10E-1000010001") < promoted.index(
        "[![Fuzzing Status](https://oss-fuzz-build-logs.storage.googleapis.com/badges/demo.svg)](https://oss-fuzz-build-logs.storage.googleapis.com/index.html#demo)"
    )


def test_visible_candidate_signal_promotion_keeps_category_diversity() -> None:
    from sage_agent.adapters.cybergym_live import _promote_visible_candidate_signals

    candidates = [
        "--help",
        "--binary-files=word",
        "https://example.test/docs",
        "https://example.test/archive",
        "https://example.test/more",
        "dict: \\\\A",
        "dict: \\\\b",
        "dict: \\\\B",
        "dict: \\\\d",
        "--with-html             HTML parser (on)",
    ]

    promoted = _promote_visible_candidate_signals(candidates)

    assert promoted.index("--with-html             HTML parser (on)") < 8
    assert promoted.index("\\\\A") < 8
    assert "dict: \\\\A" not in promoted


def test_visible_candidate_signal_promotion_does_not_overweight_generic_includes() -> (
    None
):
    from sage_agent.adapters.cybergym_live import _promote_visible_candidate_signals

    candidates = [
        "#include <cassert>",
        "#include <stdio.h>",
        "dict: \\\\A",
        "dict: \\\\b",
        "#include <magic.h>",
    ]

    promoted = _promote_visible_candidate_signals(candidates)

    assert promoted.index("#include <magic.h>") < promoted.index("\\\\A")
    assert "dict: \\\\A" not in promoted
    assert promoted.index("\\\\A") < promoted.index("#include <cassert>")


def test_visible_candidate_signal_promotion_adds_clean_payload_variants() -> None:
    from sage_agent.adapters.cybergym_live import _promote_visible_candidate_signals

    promoted = _promote_visible_candidate_signals(
        ["dict: <a></a>", "source_line: #include <magic.h>"]
    )

    assert "<a></a>" in promoted
    assert "dict: <a></a>" not in promoted
    assert "#include <magic.h>" in promoted
    assert "source_line: #include <magic.h>" not in promoted


def test_candidate_payload_expansion_strips_provenance_before_submission() -> None:
    from sage_agent.adapters.cybergym_live import _expand_candidate_payload_variants

    expanded = _expand_candidate_payload_variants(
        ["dict: <a></a>", "source_line: #include <magic.h>"]
    )

    assert expanded[:2] == [
        "<a></a>",
        "#include <magic.h>",
    ]


def test_cybergym_visible_artifact_summary_balances_noisy_archives(
    tmp_path: Path,
) -> None:
    from sage_agent.adapters.cybergym_live import _visible_artifact_summary

    task_dir = tmp_path / "task"
    task_dir.mkdir()
    with tarfile.open(task_dir / "repo-vul.tar.gz", "w:gz") as tar:
        _add_tar_text(
            tar,
            "src/proj/fuzz/noisy.dict",
            "\n".join(f'"<tag{index}></tag{index}>"' for index in range(120)),
        )
        _add_tar_text(
            tar,
            "src/proj/README.md",
            "\n".join(
                (
                    "--with-c14n             Canonical XML support (on)",
                    "--with-html             HTML parser (on)",
                    "--with-regexps          regular expressions support (on)",
                )
            ),
        )
        _add_tar_text(
            tar,
            "src/proj/fuzzer.c",
            "#include <magic.h>\nif (size == 4294967295) abort();\n",
        )

    summary = _visible_artifact_summary(task_dir)

    assert "--with-html             HTML parser (on)" in summary
    assert "source_line: #include <magic.h>" in summary
    assert summary.index("dict: <tag10></tag10>") < summary.index("file: ")


def test_cybergym_visible_artifact_summary_extracts_visible_samples(
    tmp_path: Path,
) -> None:
    from sage_agent.adapters.cybergym_live import (
        _expand_candidate_payload_variants,
        _promote_visible_candidate_signals,
        _visible_artifact_summary,
    )

    task_dir = tmp_path / "task"
    task_dir.mkdir()
    with tarfile.open(task_dir / "repo-vul.tar.gz", "w:gz") as tar:
        _add_tar_bytes(tar, "src/proj/tests/data/tiny", b"MZ\x90\x00PE\x00\x00A")
        _add_tar_text(tar, "src/proj/examples/example.xml", "<root><a/></root>\n")
        _add_tar_text(tar, "src/proj/tests/crash-abc", "do not expose\n")
        _add_tar_text(tar, "src/proj/tests/poc-secret", "do not expose\n")

    summary = _visible_artifact_summary(task_dir)
    expanded = _expand_candidate_payload_variants(summary.splitlines())
    promoted = _promote_visible_candidate_signals(
        [
            "9223372036854775807",
            "source_line: if (size == 4294967295) abort();",
            *summary.splitlines(),
        ]
    )

    assert "sample_escape: MZ\\x90\\x00PE\\x00\\x00A" in summary
    assert "sample_text: <root><a/></root>" in summary
    assert "do not expose" not in summary
    assert "MZ\x90\x00PE\x00\x00A" in expanded
    assert "<root><a/></root>" in expanded
    assert promoted.index("MZ\x90\x00PE\x00\x00A") < promoted.index(
        "9223372036854775807"
    )


def test_cybergym_visible_artifact_summary_extracts_public_nested_seed_archives(
    tmp_path: Path,
) -> None:
    from sage_agent.adapters.cybergym_live import (
        _expand_candidate_payload_variants,
        _visible_artifact_summary,
    )

    task_dir = tmp_path / "task"
    task_dir.mkdir()
    seed_zip = BytesIO()
    with zipfile.ZipFile(seed_zip, "w") as archive:
        archive.writestr("seed1", b"\xff\xf1\x50\x80\x00\x1f\xfc")
        archive.writestr("nested/sample.bin", b"RIFF$\x00\x00\x00WAVEfmt ")
        archive.writestr("hidden/poc-secret", b"do not expose")
    with tarfile.open(task_dir / "repo-vul.tar.gz", "w:gz") as tar:
        _add_tar_bytes(
            tar,
            "src-vul/public_seed_corpus.zip",
            seed_zip.getvalue(),
        )

    summary = _visible_artifact_summary(task_dir)
    expanded = _expand_candidate_payload_variants(summary.splitlines())

    assert "sample_escape: \\xff\\xf1P\\x80\\x00\\x1f\\xfc" in summary
    assert "sample_escape: RIFF$\\x00\\x00\\x00WAVEfmt " in summary
    assert "do not expose" not in summary
    assert "\xff\xf1P\x80\x00\x1f\xfc" in expanded
    assert "RIFF$\x00\x00\x00WAVEfmt" in expanded


def test_cybergym_visible_artifact_summary_adds_public_sample_mutations(
    tmp_path: Path,
) -> None:
    from sage_agent.adapters.cybergym_live import (
        _expand_candidate_payload_variants,
        _visible_artifact_summary,
    )

    task_dir = tmp_path / "task"
    task_dir.mkdir()
    seed_zip = BytesIO()
    with zipfile.ZipFile(seed_zip, "w") as archive:
        archive.writestr("seed.aac", b"\xff\xf1P\x80\x00\x1f\xfc")
    with tarfile.open(task_dir / "repo-vul.tar.gz", "w:gz") as tar:
        _add_tar_bytes(tar, "src-vul/public_seed_corpus.zip", seed_zip.getvalue())

    summary = _visible_artifact_summary(task_dir)
    expanded = _expand_candidate_payload_variants(summary.splitlines())

    assert "corpus_sample:" in summary
    assert b"\xff\xf1P\x80\x00\x1f\xfc\x00" in [
        item.encode("latin1", errors="ignore") for item in expanded
    ]
    assert b"\x00\xff\xf1P\x80\x00\x1f\xfc" in [
        item.encode("latin1", errors="ignore") for item in expanded
    ]


def test_visible_sample_helper_generates_bounded_public_sample_mutations() -> None:
    gap = GapSignal(
        key="visible_sample_candidate_planning",
        summary="Generate candidates from visible public samples.",
        source_task_id="task",
        source_environment="generic-fuzz-env",
        severity=0.8,
        suggested_tool_name="plan_visible_sample_input_candidates",
        suggested_helper_family="visible_sample_candidate_planner",
        evidence=("visible public sample",),
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
        generation_directives={"template": "visible_sample_candidate_planner"},
    )
    candidate = TemplateHelperGenerator().generate(
        gap,
        EnvironmentProfile(
            name="generic-fuzz-env",
            description="Generic candidate-submission environment.",
            base_tools=("submit",),
            action_tools=("submit",),
            observation_fields=("artifact_summary",),
            helper_families=("visible_sample_candidate_planner",),
            safety_rules=("helpers must not submit candidates",),
        ),
        (
            ValidationCase(
                name="visible_sample_mutation",
                inputs={
                    "description": "Parser uses public corpus inputs.",
                    "readme": "",
                    "feedback": "candidate 0: exit_code=0 len=4",
                    "artifact_summary": "sample_escape: ABC\\x00DEF\\x01GHI\n",
                    "max_candidates": 40,
                },
                expected={
                    "abstain": False,
                    "candidates_contains": (
                        "sample_escape: ABC\\x00DEF\\x01GHI",
                        "ABC\x00DEF\x01GHI",
                        "\x00BC\x00DEF\x01GHI",
                    ),
                    "candidates_max_count": 40,
                },
            ),
        ),
        model="gpt-4o-mini",
    )

    report = validate_helper_candidate(candidate)

    assert report.accepted, report.errors


def test_cybergym_public_search_seed_corpus_uses_direct_visible_fixtures(
    tmp_path: Path,
) -> None:
    from sage_agent.adapters.cybergym_live import _write_public_seed_corpus

    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "description.txt").write_text("Public parser task.", encoding="utf-8")
    (task_dir / "README.md").write_text("Use public fixtures.", encoding="utf-8")
    with tarfile.open(task_dir / "repo-vul.tar.gz", "w:gz") as tar:
        _add_tar_bytes(tar, "project/tests/data/sample.bin", b"PUBLIC-SEED")
        _add_tar_text(tar, "project/tests/data/crash-hidden", "do not expose")
        _add_tar_text(tar, "project/src/parser.c", "int main(void) { return 0; }")
        _add_tar_text(tar, "project/reference/poc.txt", "do not expose")
    seeds_dir = tmp_path / "seeds"
    seeds_dir.mkdir()

    written = _write_public_seed_corpus(task_dir, seeds_dir)

    assert written == 1
    assert [path.read_bytes() for path in seeds_dir.iterdir()] == [b"PUBLIC-SEED"]


def test_cybergym_public_search_seed_member_guardrails() -> None:
    from sage_agent.adapters.cybergym_live import _looks_public_search_seed_member

    def member(name: str, size: int = 8) -> tarfile.TarInfo:
        info = tarfile.TarInfo(name)
        info.size = size
        return info

    assert _looks_public_search_seed_member(member("pkg/tests/data/input.xml"))
    assert _looks_public_search_seed_member(member("pkg/corpus/seed0"))
    assert not _looks_public_search_seed_member(member("pkg/src/parser.c"))
    assert not _looks_public_search_seed_member(member("pkg/tests/crash-123"))
    assert not _looks_public_search_seed_member(member("pkg/reference/poc.txt"))
    assert not _looks_public_search_seed_member(member("pkg/tests/data/empty", 0))


def test_cybergym_public_search_artifact_recognizes_nested_crashes(
    tmp_path: Path,
) -> None:
    from sage_agent.adapters.cybergym_live import _looks_public_search_artifact

    out_dir = tmp_path / "out"
    crash = out_dir / "default/crashes/id:000000,sig:06"
    queue = out_dir / "default/queue/id:000000"
    log = out_dir / "fuzz.log"
    for path in (crash, queue, log):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")

    assert _looks_public_search_artifact(crash, out_dir)
    assert not _looks_public_search_artifact(queue, out_dir)
    assert not _looks_public_search_artifact(log, out_dir)


def test_cybergym_public_search_afl_command_uses_public_wrapper_safe_env() -> None:
    from sage_agent.adapters.cybergym_live import _public_search_command

    command = _public_search_command(
        "/out/fuzz_binary_message",
        engine="afl",
        search_seconds=9,
        max_artifacts=2,
    )

    assert "/out/afl-fuzz" in command
    assert "@@" in command
    assert " -V " not in command
    assert "eval \"$(grep '^export ' /bin/arvo" in command
    assert "ASAN_OPTIONS" in command
    assert "MSAN_OPTIONS" in command
    assert "UBSAN_OPTIONS" in command


def test_cybergym_batched_runner_parallel_image_pull_reports_task_failures(
    monkeypatch: MonkeyPatch,
) -> None:
    from scripts import run_cybergym_live_batched_sage as runner

    calls: list[tuple[str, bool]] = []

    def fake_pull(image: str, *, skip_existing: bool) -> None:
        calls.append((image, skip_existing))
        if image == "bad:image":
            raise RuntimeError("pull failed")

    monkeypatch.setattr(runner, "_pull_image", fake_pull)

    failures = runner._pull_images_for_tasks(
        [("ok:1", ["ok:vul", "ok:fix"]), ("bad:2", ["bad:image"])],
        workers=2,
        skip_existing=True,
    )

    assert ("ok:vul", True) in calls
    assert ("ok:fix", True) in calls
    assert failures == ["bad:2: DockerImagePullError: pull failed"]


def test_cybergym_materialized_task_cache_reuses_public_task_dir(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    from scripts import run_cybergym_live_batched_sage as runner

    task = {
        "task_id": "arvo:1",
        "task_difficulty": {
            "level1": [
                "data/arvo/1/repo-vul.tar.gz",
                "data/arvo/1/description.txt",
            ]
        },
    }
    calls = {"download": 0, "generate": 0}

    def fake_download(_task: dict[str, Any], _difficulty: str, data_root: Path) -> None:
        calls["download"] += 1
        visible = data_root / "data/arvo/1"
        visible.mkdir(parents=True, exist_ok=True)
        (visible / "repo-vul.tar.gz").write_text("public repo", encoding="utf-8")
        (visible / "description.txt").write_text("public description", encoding="utf-8")

    def fake_generate(
        _task_id: str,
        out_dir: Path,
        _data_root: Path,
        server: str,
        _difficulty: str,
    ) -> None:
        calls["generate"] += 1
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "README.md").write_text("readme", encoding="utf-8")
        (out_dir / "description.txt").write_text("description", encoding="utf-8")
        (out_dir / "repo-vul.tar.gz").write_text("public repo", encoding="utf-8")
        (out_dir / "submit.sh").write_text(
            f"curl -X POST {server}/submit-vul\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(runner, "_download_visible_assets", fake_download)
    monkeypatch.setattr(runner, "_generate_task_dir", fake_generate)
    cache_root = tmp_path / "cache"

    runner._ensure_materialized_task_dir(
        task,
        "level1",
        tmp_path / "run1/task",
        tmp_path / "run1/data",
        "http://127.0.0.1:8666",
        cache_root,
    )
    runner._ensure_materialized_task_dir(
        task,
        "level1",
        tmp_path / "run2/task",
        tmp_path / "run2/data",
        "http://127.0.0.1:9999",
        cache_root,
    )

    assert calls == {"download": 1, "generate": 1}
    assert (tmp_path / "run2/data/data/arvo/1/repo-vul.tar.gz").read_text(
        encoding="utf-8"
    ) == "public repo"
    assert "127.0.0.1:9999" in (tmp_path / "run2/task/submit.sh").read_text(
        encoding="utf-8"
    )
    manifests = list(cache_root.rglob("materialized_task_manifest.json"))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert manifest["research_integrity"]["labels_cached"] is False
    assert manifest["research_integrity"]["sage_outcomes_cached"] is False


def test_cybergym_materialized_task_cache_rejects_empty_public_source(
    tmp_path: Path,
) -> None:
    from scripts import run_cybergym_live_batched_sage as runner

    cache_dir = tmp_path / "cache"
    task_dir = cache_dir / "task"
    data_dir = cache_dir / "data"
    task_dir.mkdir(parents=True)
    data_dir.mkdir()
    for name in ("README.md", "description.txt", "submit.sh"):
        (task_dir / name).write_text("public", encoding="utf-8")
    (task_dir / "repo-vul.tar.gz").write_bytes(b"")
    manifest_path = cache_dir / "materialized_task_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "task_id": "arvo:empty",
                "research_integrity": {
                    "labels_cached": False,
                    "reference_pocs_cached": False,
                    "hidden_answers_cached": False,
                    "sage_outcomes_cached": False,
                    "candidate_outputs_cached": False,
                },
            }
        ),
        encoding="utf-8",
    )

    assert not runner._valid_materialized_task_cache(
        cache_dir, manifest_path, task_id="arvo:empty"
    )


def test_cybergym_materialized_task_cache_harvests_existing_public_task_dir(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    from scripts import run_cybergym_live_batched_sage as runner

    task = {
        "task_id": "arvo:2",
        "task_difficulty": {
            "level1": [
                "data/arvo/2/repo-vul.tar.gz",
                "data/arvo/2/description.txt",
            ]
        },
    }
    old_task = tmp_path / "outputs/cybergym_live_sage/old_run/tasks/01_arvo_2"
    old_task.mkdir(parents=True)
    (old_task / "README.md").write_text("readme", encoding="utf-8")
    (old_task / "description.txt").write_text("description", encoding="utf-8")
    (old_task / "repo-vul.tar.gz").write_text("repo", encoding="utf-8")
    (old_task / "submit.sh").write_text(
        "curl -X POST http://127.0.0.1:8666/submit-vul\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(runner, "ROOT", tmp_path)

    runner._ensure_materialized_task_dir(
        task,
        "level1",
        tmp_path / "run/task",
        tmp_path / "run/data",
        "http://127.0.0.1:9999",
        tmp_path / "cache",
    )

    assert (tmp_path / "run/task/repo-vul.tar.gz").read_text(encoding="utf-8") == "repo"
    assert "127.0.0.1:9999" in (tmp_path / "run/task/submit.sh").read_text(
        encoding="utf-8"
    )
    assert (tmp_path / "run/data/data/arvo/2/repo-vul.tar.gz").exists()
    manifest = json.loads(
        next((tmp_path / "cache").rglob("materialized_task_manifest.json")).read_text(
            encoding="utf-8"
        )
    )
    assert manifest["source"] == "harvested_existing_public_task_dir"
    assert manifest["research_integrity"]["hidden_answers_cached"] is False


def test_cybergym_vulnerable_prescreen_skips_unpromising_official_submits(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    from sage_agent.adapters import cybergym_live
    from sage_agent.adapters.cybergym_live import (
        CyberGymLiveSubmitAdapter,
        CyberGymLiveTask,
    )

    task_dir = tmp_path / "task"
    task_dir.mkdir()
    submitted: list[str] = []

    def fake_prescreen(
        task_id: str,
        task_dir: Path,
        index: int,
        candidate: str,
        *,
        timeout_seconds: float,
        cmd_timeout_seconds: int,
    ) -> dict[str, Any]:
        del task_id, task_dir, timeout_seconds, cmd_timeout_seconds
        exit_code = 1 if candidate == "hit" else 0
        return {
            "ok": True,
            "candidate_index": index,
            "prescreen_mode": "vulnerable-local",
            "prescreen_exit_code": exit_code,
            "prescreen_crashed": exit_code != 0,
        }

    def fake_submit(
        task_dir: Path,
        index: int,
        candidate: str,
        *,
        timeout_seconds: float,
        fixed_side_check: bool,
        fixed_side_api_key: str,
    ) -> dict[str, Any]:
        del task_dir, timeout_seconds, fixed_side_check, fixed_side_api_key
        submitted.append(candidate)
        return {
            "ok": True,
            "candidate_index": index,
            "exit_code": 1 if candidate == "hit" else 0,
            "poc_length": len(candidate),
            "official_success": candidate == "hit",
            "fixed_side_checked": False,
        }

    monkeypatch.setattr(
        cybergym_live, "_local_vulnerable_prescreen_candidate", fake_prescreen
    )
    monkeypatch.setattr(cybergym_live, "_submit_candidate", fake_submit)
    adapter = CyberGymLiveSubmitAdapter(
        tasks_root=tmp_path,
        tasks_to_run=(
            CyberGymLiveTask(
                task_key="arvo:demo",
                task_dir=task_dir,
                display_name="CyberGym demo",
            ),
        ),
        max_candidates=2,
        candidate_prescreen="vulnerable-local",
        prescreen_submit_floor=0,
    )
    task = TaskSpec(task_id="arvo:demo", name="demo", prompt="visible")

    result = adapter.run_candidate_strings(
        task,
        ["skip", "hit"],
        transcript_prefix="prescreen test",
    )

    assert result.success
    assert submitted == ["hit"]
    assert result.artifacts["candidate_budget"]["official_skipped"] == 1
    assert result.artifacts["candidate_budget"]["official_submitted"] == 1


def test_cybergym_vulnerable_prescreen_uses_arvo_run_entrypoint() -> None:
    from sage_agent.adapters.cybergym_live import _cybergym_image_and_command

    image, command = _cybergym_image_and_command("arvo:59185", "vul")

    assert image == "n132/arvo:59185-vul"
    assert command == ["/bin/arvo", "run"]


def test_cybergym_vulnerable_batch_prescreen_only_submits_crashes(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    from sage_agent.adapters import cybergym_live
    from sage_agent.adapters.cybergym_live import (
        CyberGymLiveSubmitAdapter,
        CyberGymLiveTask,
    )

    task_dir = tmp_path / "task"
    task_dir.mkdir()
    submitted: list[str] = []

    def fake_batch_prescreen(
        task_id: str,
        task_dir: Path,
        candidates: Sequence[str],
        *,
        timeout_seconds: float,
        cmd_timeout_seconds: int,
    ) -> dict[int, dict[str, Any]]:
        del task_id, task_dir, timeout_seconds, cmd_timeout_seconds
        return {
            index: {
                "ok": True,
                "candidate_index": index,
                "prescreen_mode": "vulnerable-batch",
                "prescreen_exit_code": 1 if candidate == "hit" else 0,
                "prescreen_crashed": candidate == "hit",
            }
            for index, candidate in enumerate(candidates)
        }

    def fake_submit(
        task_dir: Path,
        index: int,
        candidate: str,
        *,
        timeout_seconds: float,
        fixed_side_check: bool,
        fixed_side_api_key: str,
    ) -> dict[str, Any]:
        del task_dir, timeout_seconds, fixed_side_check, fixed_side_api_key
        submitted.append(candidate)
        return {
            "ok": True,
            "candidate_index": index,
            "exit_code": 1 if candidate == "hit" else 0,
            "poc_length": len(candidate),
            "official_success": candidate == "hit",
            "fixed_side_checked": False,
        }

    monkeypatch.setattr(
        cybergym_live,
        "_local_vulnerable_batch_prescreen_candidates",
        fake_batch_prescreen,
    )
    monkeypatch.setattr(cybergym_live, "_submit_candidate", fake_submit)
    adapter = CyberGymLiveSubmitAdapter(
        tasks_root=tmp_path,
        tasks_to_run=(
            CyberGymLiveTask(
                task_key="arvo:demo",
                task_dir=task_dir,
                display_name="CyberGym demo",
            ),
        ),
        max_candidates=3,
        candidate_prescreen="vulnerable-batch",
        prescreen_submit_floor=0,
    )
    task = TaskSpec(task_id="arvo:demo", name="demo", prompt="visible")

    result = adapter.run_candidate_strings(
        task,
        ["skip", "also-skip", "hit"],
        transcript_prefix="batch prescreen test",
    )

    assert result.success
    assert submitted == ["hit"]
    assert result.artifacts["candidate_budget"]["official_skipped"] == 2
    assert result.artifacts["candidate_budget"]["official_submitted"] == 1


def test_cybergym_vulnerable_search_appends_public_search_artifact(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    from sage_agent.adapters import cybergym_live
    from sage_agent.adapters.cybergym_live import (
        CyberGymLiveSubmitAdapter,
        CyberGymLiveTask,
    )

    task_dir = tmp_path / "task"
    task_dir.mkdir()
    submitted: list[str] = []

    def fake_batch_prescreen(
        task_id: str,
        task_dir: Path,
        candidates: Sequence[str],
        *,
        timeout_seconds: float,
        cmd_timeout_seconds: int,
    ) -> dict[int, dict[str, Any]]:
        del task_id, task_dir, timeout_seconds, cmd_timeout_seconds
        return {
            index: {
                "ok": True,
                "candidate_index": index,
                "prescreen_mode": "vulnerable-search",
                "prescreen_exit_code": 0,
                "prescreen_crashed": False,
            }
            for index, _candidate in enumerate(candidates)
        }

    def fake_public_search(
        task_id: str,
        task_dir: Path,
        *,
        seed_candidates: Sequence[str],
        timeout_seconds: float,
        search_seconds: int,
        max_artifacts: int,
    ) -> list[dict[str, Any]]:
        del task_id, task_dir, seed_candidates, timeout_seconds, search_seconds
        assert max_artifacts >= 1
        return [
            {
                "candidate": "searched-hit",
                "target": "demo_fuzzer",
                "size": 12,
                "vulnerable_exit_code": 1,
                "log_excerpt": "public vulnerable-side crash",
            }
        ]

    def fake_submit(
        task_dir: Path,
        index: int,
        candidate: str,
        *,
        timeout_seconds: float,
        fixed_side_check: bool,
        fixed_side_api_key: str,
    ) -> dict[str, Any]:
        del task_dir, timeout_seconds, fixed_side_check, fixed_side_api_key
        submitted.append(candidate)
        return {
            "ok": True,
            "candidate_index": index,
            "exit_code": 1 if candidate == "searched-hit" else 0,
            "poc_length": len(candidate),
            "official_success": candidate == "searched-hit",
            "fixed_side_checked": False,
        }

    monkeypatch.setattr(
        cybergym_live,
        "_local_vulnerable_batch_prescreen_candidates",
        fake_batch_prescreen,
    )
    monkeypatch.setattr(
        cybergym_live,
        "_local_vulnerable_public_search_candidates",
        fake_public_search,
    )
    monkeypatch.setattr(cybergym_live, "_submit_candidate", fake_submit)
    adapter = CyberGymLiveSubmitAdapter(
        tasks_root=tmp_path,
        tasks_to_run=(
            CyberGymLiveTask(
                task_key="arvo:demo",
                task_dir=task_dir,
                display_name="CyberGym demo",
            ),
        ),
        max_candidates=3,
        candidate_prescreen="vulnerable-search",
        prescreen_submit_floor=0,
    )
    task = TaskSpec(task_id="arvo:demo", name="demo", prompt="visible")
    tool_use = ToolUseRecord(
        "plan_public_local_fuzz_search_candidates",
        result={"candidates": ["search_strategy: public_local_fuzz"]},
        generated_helper=True,
    )

    result = adapter.run_candidate_strings(
        task,
        ["search_strategy: public_local_fuzz", "skip"],
        transcript_prefix="public search test",
        tool_uses=(tool_use,),
        candidate_sources={"skip": ("plan_public_local_fuzz_search_candidates",)},
    )

    assert result.success
    assert submitted == ["searched-hit"]
    assert result.artifacts["candidate_budget"]["public_search_artifacts"] == 1
    assert result.artifacts["candidate_budget"]["official_skipped"] == 1
    assert result.tool_uses[0].success


def test_cybergym_baseline_cache_falls_back_to_task_record() -> None:
    from scripts import run_cybergym_live_batched_sage as runner

    task = TaskSpec(
        task_id="arvo:demo",
        name="demo",
        prompt="new visible summary",
        artifacts={"artifact_summary": "source_line: changed order"},
    )
    records = {
        "old-visible-hash": {
            "task_id": "arvo:demo",
            "success": False,
            "error": "",
            "transcript": ["LLM baseline planned 1 candidate inputs."],
            "artifacts": {"attempts": []},
        },
        "bad-current-hash": {
            "task_id": "arvo:demo",
            "success": False,
            "error": "Missing credentials.",
            "transcript": ["LLM baseline failed: Missing credentials."],
            "artifacts": {},
        },
    }

    assert (
        runner._eligible_baseline_cache_key(
            records,
            task=task,
            cache_key="bad-current-hash",
            legacy_cache_key="missing-legacy",
            fixed_side_check=True,
        )
        == "old-visible-hash"
    )


def _helper_record_for_family(family: str) -> HelperRecord:
    candidate = HelperCandidate(
        spec=HelperSpec(
            name=f"helper_{family}",
            family=family,
            description="test helper",
        ),
        code="def helper():\n    return {}\n",
    )
    return HelperRecord(
        candidate=candidate,
        validation=HelperValidationReport(accepted=True),
        birth_gap_key=family,
        birth_environment="portable-candidate-env",
        created_at="2026-05-21T00:00:00Z",
        code_hash=family,
    )


def _add_tar_text(tar: tarfile.TarFile, name: str, text: str) -> None:
    payload = text.encode("utf-8")
    _add_tar_bytes(tar, name, payload)


def _add_tar_bytes(tar: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    tar.addfile(info, BytesIO(payload))


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
                "semantic_description_candidate_planner",
                "execution_feedback_candidate_mutation_planner",
                "structured_input_candidate_planner",
                "adaptive_candidate_portfolio_planner",
                "visible_evidence_portfolio_candidate_planner",
                "format_edge_candidate_planner",
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
        if template == "semantic_description_candidate_planner":
            return (
                ValidationCase(
                    name="semantic-description",
                    inputs={
                        "description": "XML namespace parser accepts visible text.",
                        "readme": "",
                        "feedback": "",
                        "artifact_summary": "",
                        "max_candidates": 4,
                    },
                    expected={
                        "candidate_count": 4,
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
