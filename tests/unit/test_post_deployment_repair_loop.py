"""Focused tests for prospective, post-deployment generated-tool repair."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

import pytest

import sage_ts.orchestration.online_birth as online_birth
from sage_ts.adequacy.inadequacy_classifier import CapabilityObservation
from sage_ts.generation.tool_generator import ToolGenerationRequest
from sage_ts.generation.tool_spec import (
    GeneratedTool,
    StructuredInadequacyEvidence,
    ToolFamily,
    ToolInput,
    ToolSpec,
)
from sage_ts.orchestration.online_birth import OnlineBirthController
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.registry.store import RegistryStore
from sage_ts.validation.sandbox_validator import ToolExample, ValidationResult

TOOL_NAME = "prepare_safe_action_or_abstain"
HIDDEN_TASK_ID = "benchmark_case_DO_NOT_REPLAY_7391"
HIDDEN_EXPECTED_VALUE = "private_capability_DO_NOT_DISCLOSE_4217"
HIDDEN_NEGATIVE_VALUE = "private_negative_DO_NOT_DISCLOSE_8842"


def _spec() -> ToolSpec:
    return ToolSpec(
        tool_name=TOOL_NAME,
        family=ToolFamily.VALIDATION_ABSTENTION_HELPER,
        description=(
            "Decide from public runtime inputs whether an action can continue or "
            "must safely abstain."
        ),
        inputs=(
            ToolInput("user_request", "str", "Visible user request."),
            ToolInput("requested_action", "str", "Requested action category."),
            ToolInput("target_identifier", "str", "Visible stable target identifier."),
            ToolInput("required_original_tools", "list", "Required capabilities."),
            ToolInput("available_original_tools", "list", "Available capabilities."),
            ToolInput("visible_records_count", "int", "Number of visible matches."),
        ),
        output_annotation="dict",
        output_schema={
            "type": "object",
            "properties": {
                "should_abstain": {"type": "boolean"},
                "missing_information": {"type": "array"},
                "required_original_tools": {"type": "array"},
                "safe_next_action": {"type": "string"},
                "final_answer_recommendation": {"type": "string"},
                "abstain_reason": {"type": "string"},
            },
        },
        positive_triggers=("missing capability", "missing target"),
        negative_triggers=("complete safe request",),
        preserves_side_effect_tools=("search_contacts", "modify_contact"),
        required_original_tool_calls=("search_contacts", "modify_contact"),
        abstain_behavior="Abstain when information or a required capability is missing.",
        generalization_rationale=(
            "The same capability and target checks apply across multiple action families."
        ),
        estimated_step_compression=3,
        cross_task_applicability_count=2,
        applicable_task_families=("contact_lookup_tasks", "contact_update_tasks"),
        reason_tool_is_decisive=(
            "It prevents an unsafe action before any original side-effect tool executes."
        ),
        shortfall_cluster_evidence=("deterministic_public_contract_failure",),
        known_failure_mechanisms_addressed=("unsafe_continue_with_missing_input",),
        inadequacy_evidence=StructuredInadequacyEvidence(
            summary=(
                "Repeated public runtime failures show that missing inputs are not "
                "being converted into a safe abstention."
            ),
            signals=("missing_runtime_capability", "missing_target_identifier"),
        ),
    )


def _faulty_tool() -> GeneratedTool:
    return GeneratedTool(
        spec=_spec(),
        code=(
            "def prepare_safe_action_or_abstain(user_request: str, requested_action: str, "
            "target_identifier: str, required_original_tools: list, "
            "available_original_tools: list, visible_records_count: int) -> dict:\n"
            "    return {'should_abstain': True, "
            "'missing_information': ['search_contacts'], "
            "'required_original_tools': ['search_contacts'], "
            "'safe_next_action': 'ask_user_or_abstain', "
            "'final_answer_recommendation': 'Cannot continue without search_contacts.', "
            "'abstain_reason': 'missing_required_original_tool'}\n"
        ),
    )


def _repaired_tool() -> GeneratedTool:
    return GeneratedTool(
        spec=_spec(),
        code=(
            "def prepare_safe_action_or_abstain(user_request: str, requested_action: str, "
            "target_identifier: str, required_original_tools: list, "
            "available_original_tools: list, visible_records_count: int) -> dict:\n"
            "    required = [required_original_tools] if isinstance(required_original_tools, str) else list(required_original_tools)\n"
            "    available = [available_original_tools] if isinstance(available_original_tools, str) else list(available_original_tools)\n"
            "    missing = [item for item in required if item not in available]\n"
            "    if missing:\n"
            "        return {'should_abstain': True, 'missing_information': missing, "
            "'required_original_tools': required, 'safe_next_action': 'ask_user_or_abstain', "
            "'final_answer_recommendation': 'Cannot continue without ' + ', '.join(missing) + '.', "
            "'abstain_reason': 'missing_required_original_tool'}\n"
            "    action = str(requested_action or '').lower()\n"
            "    if any(word in action for word in ('update', 'modify', 'remove', 'send')) and not str(target_identifier or '').strip():\n"
            "        return {'should_abstain': True, 'missing_information': ['target_identifier'], "
            "'required_original_tools': required, 'safe_next_action': 'ask_user_or_abstain', "
            "'final_answer_recommendation': 'Cannot continue without a target identifier.', "
            "'abstain_reason': 'missing_target_identifier'}\n"
            "    return {'should_abstain': False, 'missing_information': [], "
            "'required_original_tools': required, 'safe_next_action': 'continue_with_original_tool', "
            "'final_answer_recommendation': '', 'abstain_reason': ''}\n"
        ),
    )


def _observation() -> CapabilityObservation:
    return CapabilityObservation(
        scenario_name=HIDDEN_TASK_ID,
        task_context_label="visible_task_context(family=record_safety)",
        task_family_key="record_safety",
        canonical_key="validation:prepare_safe_action_or_abstain",
        observation=(
            "A general runtime safety decision needs capability and target checks "
            "using only information visible to the actor."
        ),
        allowed_families=(str(ToolFamily.VALIDATION_ABSTENTION_HELPER),),
        validation_examples=(
            ToolExample(
                inputs={
                    "user_request": "Inspect a record",
                    "requested_action": "lookup_record",
                    "target_identifier": "",
                    "required_original_tools": ["search_contacts"],
                    "available_original_tools": [],
                    "visible_records_count": 0,
                },
                expected={
                    "should_abstain": True,
                    "missing_information": ["search_contacts"],
                    "required_original_tools": ["search_contacts"],
                    "safe_next_action": "ask_user_or_abstain",
                    "final_answer_recommendation": (
                        "Cannot continue without search_contacts."
                    ),
                    "abstain_reason": "missing_required_original_tool",
                },
            ),
            ToolExample(
                inputs={
                    "user_request": HIDDEN_TASK_ID,
                    "requested_action": "lookup_record",
                    "target_identifier": "",
                    "required_original_tools": [HIDDEN_EXPECTED_VALUE],
                    "available_original_tools": [HIDDEN_EXPECTED_VALUE],
                    "visible_records_count": 0,
                },
                expected={
                    "should_abstain": False,
                    "missing_information": [],
                    "required_original_tools": [HIDDEN_EXPECTED_VALUE],
                    "safe_next_action": "continue_with_original_tool",
                    "final_answer_recommendation": "",
                    "abstain_reason": "",
                },
                held_out=True,
            ),
            ToolExample(
                inputs={
                    "user_request": "Update a record",
                    "requested_action": "update_record",
                    "target_identifier": "",
                    "required_original_tools": ["modify_contact"],
                    "available_original_tools": ["modify_contact"],
                    "visible_records_count": 0,
                },
                expected={
                    "should_abstain": True,
                    "missing_information": ["target_identifier"],
                    "required_original_tools": ["modify_contact"],
                    "safe_next_action": "ask_user_or_abstain",
                    "final_answer_recommendation": (
                        "Cannot continue without a target identifier."
                    ),
                    "abstain_reason": "missing_target_identifier",
                },
                negative_applicability=True,
            ),
            ToolExample(
                inputs={
                    "user_request": "A hidden negative contract case",
                    "requested_action": "lookup_record",
                    "target_identifier": "",
                    "required_original_tools": [HIDDEN_NEGATIVE_VALUE],
                    "available_original_tools": [],
                    "visible_records_count": 0,
                },
                expected={
                    "should_abstain": True,
                    "missing_information": [HIDDEN_NEGATIVE_VALUE],
                    "required_original_tools": [HIDDEN_NEGATIVE_VALUE],
                    "safe_next_action": "ask_user_or_abstain",
                    "final_answer_recommendation": (
                        f"Cannot continue without {HIDDEN_NEGATIVE_VALUE}."
                    ),
                    "abstain_reason": "missing_required_original_tool",
                },
                held_out=True,
                negative_applicability=True,
            ),
        ),
        generation_allowed=True,
        reason="public_contract_shortfall",
        inadequacy_signals=("missing_runtime_capability",),
        failed_tool_calls=("search_contacts", "modify_contact"),
        evidence_source="visible_task_context",
    )


def _accepted_historical_entry(tool: GeneratedTool) -> RegistryEntry:
    # A historical proof can predate stronger semantic validation. The lifecycle
    # audit must re-check the raw deployed implementation against today's contract.
    return RegistryEntry.accepted(
        tool,
        ValidationResult(
            True,
            (),
            source_example_count=1,
            held_out_check_count=1,
            negative_applicability_count=1,
            runtime_smoke_passed=True,
        ),
        birth_scenario="historical_public_contract",
    )


def _repair_request(**extra: Any) -> dict[str, Any]:
    return {
        "request_id": "repair-request-1",
        "request_key": f"{TOOL_NAME}:v1:record_safety",
        "repair_kind": "implementation",
        "tool_name": TOOL_NAME,
        "source_tool_version": 1,
        "target_task_family": "record_safety",
        "trigger_reason_codes": ["deterministic_public_contract_failure"],
        "trigger_completed_count": 8,
        "eligible_from_completed_count": 9,
        "future_tasks_only": True,
        "triggering_task_replay_allowed": False,
        "public_evidence": {
            "called_count": 8,
            "candidate_outcome_mean": 0.25,
            "contract_failure_count": 2,
        },
        **extra,
    }


@dataclass
class DeterministicRepairGenerator:
    store: RegistryStore
    candidate: GeneratedTool
    repair_calls: int = 0
    requests: list[ToolGenerationRequest] = field(default_factory=list)
    error_inputs: list[tuple[str, ...]] = field(default_factory=list)
    retired_during_calls: list[bool] = field(default_factory=list)

    def generate(self, request: ToolGenerationRequest) -> GeneratedTool:
        raise AssertionError("post-deployment repair must use the repair interface")

    def repair_candidates(
        self,
        request: ToolGenerationRequest,
        rejected_tool: GeneratedTool,
        errors: tuple[str, ...],
    ) -> tuple[GeneratedTool, ...]:
        self.repair_calls += 1
        self.requests.append(request)
        self.error_inputs.append(errors)
        current = self.store.get(TOOL_NAME)
        self.retired_during_calls.append(bool(current and current.retired))
        return (self.candidate,)


def _controller(
    tmp_path: Path,
    generator: DeterministicRepairGenerator,
    *,
    events: list[tuple[str, dict[str, Any]]] | None = None,
) -> OnlineBirthController:
    return OnlineBirthController(
        store=generator.store,
        generator=generator,
        output_dir=tmp_path / "outputs",
        failure_memory_path=None,
        event_hook=(
            (lambda event, payload: events.append((event, dict(payload))))
            if events is not None
            else None
        ),
    )


def test_queued_repair_waits_for_future_processing_then_stores_v2_and_acknowledges(
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    events: list[tuple[str, dict[str, Any]]] = []
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator, events=events)
    controller.observations_by_tool_name[TOOL_NAME] = _observation()

    assert controller.queue_post_deployment_repair_requests([_repair_request()]) == (
        "repair-request-1",
    )
    unchanged = store.get(TOOL_NAME)
    assert unchanged is not None
    assert unchanged.version == 1
    assert unchanged.retired is False
    assert generator.repair_calls == 0

    acknowledgements: list[tuple[str, int, str, str]] = []
    repaired = controller.process_pending_repairs(
        completed_count=8, acknowledge=lambda *args: acknowledgements.append(args) or {}
    )

    assert repaired == (TOOL_NAME,)
    assert generator.repair_calls == 1
    assert generator.retired_during_calls == [True]
    replacement = store.get(TOOL_NAME)
    assert replacement is not None
    assert replacement.version == 2
    assert replacement.retired is False
    assert replacement.tool.code == _repaired_tool().code
    assert acknowledgements == [(TOOL_NAME, 2, "repair-request-1", "canary_pending")]
    accepted_event = next(
        payload
        for event, payload in events
        if event == "post_deployment_tool_repair_accepted"
    )
    assert accepted_event["triggering_task_replayed"] is False
    assert accepted_event["canary_eligible_from_next_task"] is True


def test_run_end_sparse_failure_reason_survives_repair_queue_sanitization(
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator)

    queued = controller.queue_post_deployment_repair_requests(
        [
            _repair_request(
                trigger_reason_codes=["unresolved_generated_tool_execution_failure"]
            )
        ],
        visible_task_family="record_safety",
    )

    assert queued == ("repair-request-1",)
    assert controller.pending_repair_requests[0]["trigger_reason_codes"] == [
        "unresolved_generated_tool_execution_failure"
    ]


def test_failed_bounded_repair_leaves_known_bad_tool_retired(tmp_path: Path) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    generator = DeterministicRepairGenerator(store=store, candidate=_faulty_tool())
    controller = _controller(tmp_path, generator)
    controller.observations_by_tool_name[TOOL_NAME] = _observation()
    controller.queue_post_deployment_repair_requests([_repair_request()])
    acknowledgements: list[tuple[str, int, str, str]] = []

    assert (
        controller.process_pending_repairs(
            completed_count=8,
            acknowledge=lambda *args: acknowledgements.append(args) or {},
        )
        == ()
    )

    retired = store.get(TOOL_NAME)
    assert retired is not None
    assert retired.version == 1
    assert retired.retired is True
    assert generator.repair_calls > 1
    assert all(generator.retired_during_calls)
    assert acknowledgements == [(TOOL_NAME, 1, "repair-request-1", "rejected")]
    assert controller.pending_repair_requests == []
    assert "repair-request-1" in controller.handled_repair_request_ids


def test_missing_or_superseded_repair_request_gets_terminal_acknowledgement(
    tmp_path: Path,
) -> None:
    missing_store = RegistryStore(tmp_path / "missing_registry")
    missing_generator = DeterministicRepairGenerator(
        store=missing_store, candidate=_repaired_tool()
    )
    missing_controller = _controller(tmp_path / "missing", missing_generator)
    missing_controller.queue_post_deployment_repair_requests([_repair_request()])
    missing_acknowledgements: list[tuple[str, int, str, str]] = []

    assert (
        missing_controller.process_pending_repairs(
            completed_count=8,
            acknowledge=lambda *args: missing_acknowledgements.append(args) or {},
        )
        == ()
    )
    assert missing_acknowledgements == [(TOOL_NAME, 1, "repair-request-1", "rejected")]

    stale_store = RegistryStore(tmp_path / "stale_registry")
    stale_store.put(_accepted_historical_entry(_faulty_tool()))
    stale_generator = DeterministicRepairGenerator(
        store=stale_store, candidate=_repaired_tool()
    )
    stale_controller = _controller(tmp_path / "stale", stale_generator)
    stale_controller.observations_by_tool_name[TOOL_NAME] = _observation()
    stale_controller.queue_post_deployment_repair_requests([_repair_request()])
    stale_store.put(_accepted_historical_entry(_repaired_tool()))
    stale_acknowledgements: list[tuple[str, int, str, str]] = []

    assert (
        stale_controller.process_pending_repairs(
            completed_count=8,
            acknowledge=lambda *args: stale_acknowledgements.append(args) or {},
        )
        == ()
    )
    assert stale_acknowledgements == [(TOOL_NAME, 1, "repair-request-1", "rejected")]
    assert stale_store.get(TOOL_NAME).version == 2  # type: ignore[union-attr]
    assert stale_store.get(TOOL_NAME).retired is False  # type: ignore[union-attr]


def test_generation_and_repair_requests_omit_held_out_and_trigger_task_values(
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator)
    observation = _observation()
    controller.observations_by_tool_name[TOOL_NAME] = observation

    initial_request = controller._generation_request(  # noqa: SLF001
        observation,
        suggested_name=TOOL_NAME,
    )
    initial_text = json.dumps(asdict(initial_request), default=str, sort_keys=True)
    assert HIDDEN_TASK_ID not in initial_text
    assert HIDDEN_EXPECTED_VALUE not in initial_text
    assert HIDDEN_NEGATIVE_VALUE not in initial_text
    assert len(initial_request.validation_examples) == 2

    controller.queue_post_deployment_repair_requests(
        [
            _repair_request(
                target_task_family=f"raw-task-id/{HIDDEN_TASK_ID}",
                scenario_name=HIDDEN_TASK_ID,
                task_id=HIDDEN_TASK_ID,
                expected_answer=HIDDEN_EXPECTED_VALUE,
                evaluator_trace={"expected": HIDDEN_EXPECTED_VALUE},
            )
        ]
    )
    assert controller.process_pending_repairs(completed_count=8) == (TOOL_NAME,)

    repair_text = json.dumps(asdict(generator.requests[0]), default=str, sort_keys=True)
    repair_errors = json.dumps(generator.error_inputs[0], default=str, sort_keys=True)
    assert HIDDEN_TASK_ID not in repair_text
    assert HIDDEN_EXPECTED_VALUE not in repair_text
    assert HIDDEN_NEGATIVE_VALUE not in repair_text
    assert HIDDEN_TASK_ID not in repair_errors
    assert HIDDEN_EXPECTED_VALUE not in repair_errors
    assert HIDDEN_NEGATIVE_VALUE not in repair_errors
    assert "candidate_outcome" not in repair_text
    assert "success_flip" not in repair_text
    assert len(generator.requests[0].validation_examples) == 2
    assert all(
        example.get("held_out") is False
        for example in generator.requests[0].validation_examples
    )
    assert controller.canary_state_by_tool[TOOL_NAME]["target_task_family"] == (
        "unclassified"
    )
    controller.record_canary_result(
        called_tools=[TOOL_NAME],
        called_tool_versions={TOOL_NAME: 2},
        attributable_tools=[TOOL_NAME],
        visible_tools=[TOOL_NAME],
        failed_tools=[],
        candidate_outcome=1.0,
        audited_outcome_delta=1.0,
        fresh_control_success_flip=True,
        contract_failures=[],
        exception_type=None,
        task_family_key="record_safety",
    )
    assert (
        controller.canary_state_by_tool[TOOL_NAME]["attributable_observation_count"]
        == 0
    )


def test_pending_request_and_canary_state_survive_controller_restart(
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    first_generator = DeterministicRepairGenerator(
        store=store, candidate=_repaired_tool()
    )
    first = _controller(tmp_path, first_generator)
    first.observations_by_tool_name[TOOL_NAME] = _observation()
    first.queue_post_deployment_repair_requests([_repair_request()])

    second_generator = DeterministicRepairGenerator(
        store=store, candidate=_repaired_tool()
    )
    second = _controller(tmp_path, second_generator)
    assert [request["request_id"] for request in second.pending_repair_requests] == [
        "repair-request-1"
    ]
    second.observations_by_tool_name[TOOL_NAME] = _observation()
    assert second.process_pending_repairs(completed_count=8) == (TOOL_NAME,)

    third_generator = DeterministicRepairGenerator(
        store=store, candidate=_repaired_tool()
    )
    third = _controller(tmp_path, third_generator)
    assert third.pending_repair_requests == []
    assert third.canary_state_by_tool[TOOL_NAME]["tool_version"] == 2
    assert third.canary_state_by_tool[TOOL_NAME]["request_id"] == "repair-request-1"


def test_contract_audit_flags_faulty_abstention_helper_without_hidden_values(
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    events: list[tuple[str, dict[str, Any]]] = []
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator, events=events)
    controller.observations_by_tool_name[TOOL_NAME] = _observation()

    assert controller.contract_failures_for_tools([TOOL_NAME]) == (TOOL_NAME,)
    failure_event = next(
        payload
        for event, payload in events
        if event == "post_deployment_public_contract_failure"
    )
    event_text = json.dumps(failure_event, sort_keys=True)
    assert HIDDEN_TASK_ID not in event_text
    assert HIDDEN_EXPECTED_VALUE not in event_text
    assert HIDDEN_NEGATIVE_VALUE not in event_text
    assert failure_event["raw_hidden_case_values_logged"] is False


def test_repaired_canary_promotes_only_from_attributable_audited_evidence(
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator)
    controller.observations_by_tool_name[TOOL_NAME] = _observation()
    controller.queue_post_deployment_repair_requests([_repair_request()])
    controller.process_pending_repairs(completed_count=8)
    acknowledgements: list[tuple[str, int, str, str]] = []

    assert (
        controller.record_canary_result(
            called_tools=[TOOL_NAME],
            called_tool_versions={TOOL_NAME: 2},
            attributable_tools=[TOOL_NAME],
            visible_tools=[TOOL_NAME],
            failed_tools=[],
            candidate_outcome=0.0,
            audited_outcome_delta=-1.0,
            fresh_control_success_flip=False,
            contract_failures=[],
            exception_type=None,
            task_family_key="unrelated_family",
            acknowledge=lambda *args: acknowledgements.append(args) or {},
        )
        == ()
    )
    for outcome, delta, success_flip in (
        (1.0, 1.0, True),
        (1.0, 0.0, False),
    ):
        assert (
            controller.record_canary_result(
                called_tools=[TOOL_NAME],
                called_tool_versions={TOOL_NAME: 2},
                attributable_tools=[TOOL_NAME],
                visible_tools=[TOOL_NAME],
                failed_tools=[],
                candidate_outcome=outcome,
                audited_outcome_delta=delta,
                fresh_control_success_flip=success_flip,
                contract_failures=[],
                exception_type=None,
                task_family_key="record_safety",
                acknowledge=lambda *args: acknowledgements.append(args) or {},
            )
            == ()
        )
    decisions = controller.record_canary_result(
        called_tools=[TOOL_NAME],
        called_tool_versions={TOOL_NAME: 2},
        attributable_tools=[TOOL_NAME],
        visible_tools=[TOOL_NAME],
        failed_tools=[],
        candidate_outcome=0.0,
        audited_outcome_delta=0.0,
        fresh_control_success_flip=False,
        contract_failures=[],
        exception_type=None,
        task_family_key="record_safety",
        acknowledge=lambda *args: acknowledgements.append(args) or {},
    )

    assert len(decisions) == 1
    assert decisions[0]["status"] == "promoted"
    assert decisions[0]["outcome_success_rate"] == 2 / 3
    assert decisions[0]["attributable_observation_count"] == 3
    assert decisions[0]["audited_regression_count"] == 0
    assert decisions[0]["fresh_control_success_flip_count"] == 1
    assert store.get(TOOL_NAME).retired is False  # type: ignore[union-attr]
    assert acknowledgements == [(TOOL_NAME, 2, "repair-request-1", "promoted")]


def test_repaired_canary_rolls_back_on_first_attributable_audited_regression(
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator)
    controller.observations_by_tool_name[TOOL_NAME] = _observation()
    controller.queue_post_deployment_repair_requests([_repair_request()])
    controller.process_pending_repairs(completed_count=8)

    decisions = controller.record_canary_result(
        called_tools=[TOOL_NAME],
        called_tool_versions={TOOL_NAME: 2},
        attributable_tools=[TOOL_NAME],
        visible_tools=[TOOL_NAME],
        failed_tools=[],
        candidate_outcome=0.0,
        audited_outcome_delta=-1.0,
        fresh_control_success_flip=False,
        contract_failures=[],
        exception_type=None,
        task_family_key="record_safety",
    )

    assert len(decisions) == 1
    assert decisions[0]["status"] == "rolled_back"
    assert decisions[0]["reason"] == "attributable_audited_outcome_regression"
    assert decisions[0]["audited_regression_count"] == 1
    assert decisions[0]["attributable_observation_count"] == 1
    assert store.get(TOOL_NAME).retired is True  # type: ignore[union-attr]


def test_repaired_canary_ignores_confounded_and_wrong_version_soft_evidence(
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator)
    controller.observations_by_tool_name[TOOL_NAME] = _observation()
    controller.queue_post_deployment_repair_requests([_repair_request()])
    controller.process_pending_repairs(completed_count=8)

    assert (
        controller.record_canary_result(
            called_tools=[TOOL_NAME, "another_generated_tool"],
            called_tool_versions={TOOL_NAME: 2, "another_generated_tool": 1},
            attributable_tools=[],
            visible_tools=[TOOL_NAME, "another_generated_tool"],
            failed_tools=[],
            candidate_outcome=1.0,
            audited_outcome_delta=1.0,
            fresh_control_success_flip=True,
            contract_failures=[],
            exception_type=None,
            task_family_key="record_safety",
        )
        == ()
    )
    assert (
        controller.record_canary_result(
            called_tools=[TOOL_NAME],
            called_tool_versions={TOOL_NAME: 1},
            attributable_tools=[TOOL_NAME],
            visible_tools=[TOOL_NAME],
            failed_tools=[],
            candidate_outcome=1.0,
            audited_outcome_delta=1.0,
            fresh_control_success_flip=True,
            contract_failures=[],
            exception_type=None,
            task_family_key="record_safety",
        )
        == ()
    )

    state = controller.canary_state_by_tool[TOOL_NAME]
    assert state["called_count"] == 1
    assert state["attributable_observation_count"] == 0
    assert state["fresh_control_success_flip_count"] == 0
    assert state["version_mismatch_call_count"] == 1
    assert store.get(TOOL_NAME).retired is False  # type: ignore[union-attr]


def test_repaired_canary_requires_a_fresh_control_success_flip(
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator)
    controller.observations_by_tool_name[TOOL_NAME] = _observation()
    controller.queue_post_deployment_repair_requests([_repair_request()])
    controller.process_pending_repairs(completed_count=8)

    decisions: tuple[dict[str, Any], ...] = ()
    for _ in range(3):
        decisions = controller.record_canary_result(
            called_tools=[TOOL_NAME],
            called_tool_versions={TOOL_NAME: 2},
            attributable_tools=[TOOL_NAME],
            visible_tools=[TOOL_NAME],
            failed_tools=[],
            candidate_outcome=1.0,
            audited_outcome_delta=0.0,
            fresh_control_success_flip=False,
            contract_failures=[],
            exception_type=None,
            task_family_key="record_safety",
        )

    assert len(decisions) == 1
    assert decisions[0]["status"] == "rolled_back"
    assert decisions[0]["reason"] == "attributable_canary_gate_not_met"
    assert decisions[0]["outcome_success_count"] == 3
    assert decisions[0]["fresh_control_success_flip_count"] == 0
    assert store.get(TOOL_NAME).retired is True  # type: ignore[union-attr]


def test_scenario_exception_after_valid_tool_call_is_not_tool_failure(
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator)
    controller.observations_by_tool_name[TOOL_NAME] = _observation()
    controller.queue_post_deployment_repair_requests([_repair_request()])
    controller.process_pending_repairs(completed_count=8)

    assert (
        controller.record_canary_result(
            called_tools=[TOOL_NAME],
            called_tool_versions={TOOL_NAME: 2},
            attributable_tools=[TOOL_NAME],
            visible_tools=[TOOL_NAME],
            failed_tools=[],
            # The scenario runner emits a zero audited outcome for a generic
            # exception.  Even a negative paired delta is not tool-attributable.
            candidate_outcome=0.0,
            audited_outcome_delta=-1.0,
            fresh_control_success_flip=False,
            contract_failures=[],
            exception_type="ActorRuntimeError",
            task_family_key="record_safety",
        )
        == ()
    )

    state = controller.canary_state_by_tool[TOOL_NAME]
    assert state["runtime_failure_count"] == 0
    assert state["attributable_observation_count"] == 0
    assert state["audited_regression_count"] == 0
    assert store.get(TOOL_NAME).retired is False  # type: ignore[union-attr]


def test_repaired_canary_contract_failure_is_retired_immediately(
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator)
    controller.observations_by_tool_name[TOOL_NAME] = _observation()
    controller.queue_post_deployment_repair_requests([_repair_request()])
    controller.process_pending_repairs(completed_count=8)

    decisions = controller.record_canary_result(
        called_tools=[TOOL_NAME],
        called_tool_versions={TOOL_NAME: 2},
        attributable_tools=[TOOL_NAME],
        visible_tools=[TOOL_NAME],
        failed_tools=[],
        candidate_outcome=1.0,
        audited_outcome_delta=1.0,
        fresh_control_success_flip=True,
        contract_failures=[TOOL_NAME],
        exception_type=None,
        task_family_key="record_safety",
    )

    assert len(decisions) == 1
    assert decisions[0]["status"] == "rolled_back"
    assert decisions[0]["contract_failure_count"] == 1
    assert store.get(TOOL_NAME).retired is True  # type: ignore[union-attr]


def test_repaired_canary_failed_tool_message_retires_without_run_exception(
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator)
    controller.observations_by_tool_name[TOOL_NAME] = _observation()
    controller.queue_post_deployment_repair_requests([_repair_request()])
    controller.process_pending_repairs(completed_count=8)

    decisions = controller.record_canary_result(
        called_tools=[TOOL_NAME],
        called_tool_versions={TOOL_NAME: 2},
        attributable_tools=[TOOL_NAME],
        visible_tools=[TOOL_NAME],
        failed_tools=[TOOL_NAME],
        candidate_outcome=0.0,
        audited_outcome_delta=0.0,
        fresh_control_success_flip=False,
        contract_failures=[],
        exception_type=None,
        task_family_key="record_safety",
    )

    assert len(decisions) == 1
    assert decisions[0]["status"] == "rolled_back"
    assert decisions[0]["runtime_failure_count"] == 1
    assert store.get(TOOL_NAME).retired is True  # type: ignore[union-attr]


def test_repaired_canary_retires_after_eight_family_tasks_without_adoption(
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator)
    controller.observations_by_tool_name[TOOL_NAME] = _observation()
    controller.queue_post_deployment_repair_requests([_repair_request()])
    controller.process_pending_repairs(completed_count=8)

    for _ in range(7):
        assert (
            controller.record_canary_result(
                called_tools=[],
                called_tool_versions={},
                attributable_tools=[],
                visible_tools=[],
                failed_tools=[],
                candidate_outcome=None,
                audited_outcome_delta=None,
                fresh_control_success_flip=False,
                contract_failures=[],
                exception_type=None,
                task_family_key="record_safety",
            )
            == ()
        )
    decisions = controller.record_canary_result(
        called_tools=[],
        called_tool_versions={},
        attributable_tools=[],
        visible_tools=[],
        failed_tools=[],
        candidate_outcome=None,
        audited_outcome_delta=None,
        fresh_control_success_flip=False,
        contract_failures=[],
        exception_type=None,
        task_family_key="record_safety",
    )

    assert len(decisions) == 1
    assert decisions[0]["status"] == "rolled_back"
    assert decisions[0]["canary_deadline_reached"] is True
    assert decisions[0]["called_count"] == 0
    assert store.get(TOOL_NAME).retired is True  # type: ignore[union-attr]


def test_routed_visible_family_is_preserved_across_repair_and_canary(
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator)
    observation = replace(_observation(), task_family_key="safe_abstain")
    controller.observations_by_tool_name[TOOL_NAME] = observation

    assert controller.queue_post_deployment_repair_requests(
        [_repair_request(target_task_family="contact")],
        visible_task_family="contact",
    ) == ("repair-request-1",)
    assert controller.pending_repair_requests[0]["target_task_family"] == "contact"
    assert controller.process_pending_repairs(completed_count=8) == (TOOL_NAME,)
    assert controller.canary_state_by_tool[TOOL_NAME]["target_task_family"] == "contact"

    controller.record_canary_result(
        called_tools=[TOOL_NAME],
        called_tool_versions={TOOL_NAME: 2},
        attributable_tools=[TOOL_NAME],
        visible_tools=[TOOL_NAME],
        failed_tools=[],
        candidate_outcome=1.0,
        audited_outcome_delta=0.0,
        fresh_control_success_flip=False,
        contract_failures=[],
        exception_type=None,
        task_family_key="safe_abstain",
    )
    assert controller.canary_state_by_tool[TOOL_NAME]["called_count"] == 0
    controller.record_canary_result(
        called_tools=[TOOL_NAME],
        called_tool_versions={TOOL_NAME: 2},
        attributable_tools=[TOOL_NAME],
        visible_tools=[TOOL_NAME],
        failed_tools=[],
        candidate_outcome=1.0,
        audited_outcome_delta=1.0,
        fresh_control_success_flip=True,
        contract_failures=[],
        exception_type=None,
        task_family_key="contact",
    )
    assert controller.canary_state_by_tool[TOOL_NAME]["called_count"] == 1


def test_run_finalization_retires_and_acknowledges_unprocessed_request(
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator)
    controller.observations_by_tool_name[TOOL_NAME] = _observation()
    controller.queue_post_deployment_repair_requests([_repair_request()])
    acknowledgements: list[tuple[str, int, str, str]] = []

    decisions = controller.finalize_run(
        acknowledge=lambda *args: acknowledgements.append(args) or {}
    )

    assert generator.repair_calls == 0
    assert decisions == (
        {
            "event": "post_deployment_tool_repair_retired",
            "request_id": "repair-request-1",
            "tool_name": TOOL_NAME,
            "source_tool_version": 1,
            "current_tool_version": 1,
            "status": "rejected",
            "reason": "run_ended_before_future_repair_task",
            "entry_retired": True,
            "run_finalization": True,
            "future_tasks_only": True,
            "triggering_task_replayed": False,
        },
    )
    assert acknowledgements == [(TOOL_NAME, 1, "repair-request-1", "rejected")]
    assert store.get(TOOL_NAME).retired is True  # type: ignore[union-attr]
    state = json.loads(controller.repair_state_path.read_text(encoding="utf-8"))
    assert state["pending_repair_requests"] == []
    assert state["canary_state_by_tool"] == {}
    events = [
        json.loads(line)
        for line in (
            controller.output_dir / "post_deployment_lifecycle_finalization.jsonl"
        )
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert events == list(decisions)


def test_run_finalization_rolls_back_incomplete_repaired_canary(
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator)
    controller.observations_by_tool_name[TOOL_NAME] = _observation()
    controller.queue_post_deployment_repair_requests([_repair_request()])
    controller.process_pending_repairs(completed_count=8)
    controller.record_canary_result(
        called_tools=[TOOL_NAME],
        called_tool_versions={TOOL_NAME: 2},
        attributable_tools=[TOOL_NAME],
        visible_tools=[TOOL_NAME],
        failed_tools=[],
        candidate_outcome=1.0,
        audited_outcome_delta=1.0,
        fresh_control_success_flip=True,
        contract_failures=[],
        exception_type=None,
        task_family_key="record_safety",
    )
    acknowledgements: list[tuple[str, int, str, str]] = []

    decisions = controller.finalize_run(
        acknowledge=lambda *args: acknowledgements.append(args) or {}
    )

    assert len(decisions) == 1
    assert decisions[0]["status"] == "rolled_back"
    assert decisions[0]["reason"] == "run_ended_before_canary_completed"
    assert decisions[0]["outcome_observation_count"] == 1
    assert decisions[0]["attributable_observation_count"] == 1
    assert decisions[0]["audited_outcome_delta_observation_count"] == 1
    assert decisions[0]["audited_regression_count"] == 0
    assert decisions[0]["fresh_control_success_flip_count"] == 1
    assert decisions[0]["attribution_policy"] == (
        "sole_generated_tool_called_current_version_same_family"
    )
    assert decisions[0]["triggering_task_replayed"] is False
    assert acknowledgements == [(TOOL_NAME, 2, "repair-request-1", "rolled_back")]
    assert store.get(TOOL_NAME).retired is True  # type: ignore[union-attr]
    assert controller.pending_repair_requests == []
    assert controller.canary_state_by_tool == {}


def test_out_of_family_hard_failure_retires_canary_but_ignores_soft_outcome(
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator)
    controller.observations_by_tool_name[TOOL_NAME] = _observation()
    controller.queue_post_deployment_repair_requests([_repair_request()])
    controller.process_pending_repairs(completed_count=8)
    acknowledgements: list[tuple[str, int, str, str]] = []

    decisions = controller.record_canary_result(
        called_tools=[TOOL_NAME],
        called_tool_versions={TOOL_NAME: 2},
        attributable_tools=[TOOL_NAME],
        visible_tools=[TOOL_NAME],
        failed_tools=[TOOL_NAME],
        candidate_outcome=1.0,
        audited_outcome_delta=1.0,
        fresh_control_success_flip=True,
        contract_failures=[],
        exception_type=None,
        task_family_key="unrelated_family",
        acknowledge=lambda *args: acknowledgements.append(args) or {},
    )

    assert len(decisions) == 1
    assert decisions[0]["status"] == "rolled_back"
    assert decisions[0]["runtime_failure_count"] == 1
    assert decisions[0]["called_count"] == 0
    assert decisions[0]["outcome_observation_count"] == 0
    assert decisions[0]["eligible_family_task_count"] == 0
    assert acknowledgements == [(TOOL_NAME, 2, "repair-request-1", "rolled_back")]
    assert store.get(TOOL_NAME).retired is True  # type: ignore[union-attr]


def test_resumed_triggering_task_cannot_activate_future_only_repair(
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    first_generator = DeterministicRepairGenerator(
        store=store, candidate=_repaired_tool()
    )
    first = _controller(tmp_path, first_generator)
    first.queue_post_deployment_repair_requests([_repair_request()])

    resumed_generator = DeterministicRepairGenerator(
        store=store, candidate=_repaired_tool()
    )
    resumed = _controller(tmp_path, resumed_generator)
    resumed.observations_by_tool_name[TOOL_NAME] = _observation()

    # Only seven tasks are durably complete, so the prospective task has ordinal
    # eight: it is the triggering task being replayed, not eligible future task 9.
    assert resumed.process_pending_repairs(completed_count=7) == ()
    assert resumed_generator.repair_calls == 0
    assert resumed.pending_repair_requests[0]["request_id"] == "repair-request-1"
    assert store.get(TOOL_NAME).version == 1  # type: ignore[union-attr]
    assert store.get(TOOL_NAME).retired is False  # type: ignore[union-attr]

    assert resumed.process_pending_repairs(completed_count=8) == (TOOL_NAME,)
    assert resumed_generator.repair_calls == 1
    assert store.get(TOOL_NAME).version == 2  # type: ignore[union-attr]


def test_crash_after_repair_activation_recovers_exact_version_into_canary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator)
    controller.observations_by_tool_name[TOOL_NAME] = _observation()
    controller.queue_post_deployment_repair_requests([_repair_request()])
    real_write = controller._write_repair_state  # noqa: SLF001
    write_count = 0

    def crash_on_post_activation_commit() -> None:
        nonlocal write_count
        write_count += 1
        if write_count == 3:
            raise OSError("simulated crash after registry activation")
        real_write()

    monkeypatch.setattr(
        controller,
        "_write_repair_state",
        crash_on_post_activation_commit,
    )
    with pytest.raises(OSError, match="simulated crash"):
        controller.process_pending_repairs(completed_count=8)

    active = store.get(TOOL_NAME)
    assert active is not None and active.version == 2 and not active.retired
    restarted = _controller(
        tmp_path,
        DeterministicRepairGenerator(store=store, candidate=_repaired_tool()),
    )
    assert restarted.pending_repair_requests == []
    assert restarted.repair_transactions_by_tool == {}
    recovered = restarted.canary_state_by_tool[TOOL_NAME]
    assert recovered["request_id"] == "repair-request-1"
    assert recovered["tool_version"] == 2
    assert recovered["evidence_schema_version"] == 2
    assert recovered["outcomes"] == []
    assert recovered["attributable_observation_count"] == 0


def test_crash_before_repair_activation_recovers_by_retiring_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator)
    controller.observations_by_tool_name[TOOL_NAME] = _observation()
    request = _repair_request()
    request_path = (
        controller.output_dir / online_birth.POST_DEPLOYMENT_REPAIR_REQUEST_FILENAME
    )
    request_path.write_text(json.dumps(request) + "\n", encoding="utf-8")
    controller.queue_post_deployment_repair_requests([request])

    def crash_during_activation(_entry: RegistryEntry) -> None:
        raise SystemExit("simulated process death before registry activation")

    monkeypatch.setattr(store, "put", crash_during_activation)
    with pytest.raises(SystemExit, match="simulated process death"):
        controller.process_pending_repairs(completed_count=8)

    restarted = _controller(
        tmp_path,
        DeterministicRepairGenerator(store=store, candidate=_repaired_tool()),
    )
    source = store.get(TOOL_NAME)
    assert source is not None and source.version == 1 and source.retired
    assert restarted.pending_repair_requests == []
    assert restarted.canary_state_by_tool == {}
    assert restarted.repair_transactions_by_tool == {}
    acknowledgements = restarted._jsonl_rows(  # noqa: SLF001
        restarted.output_dir
        / online_birth.POST_DEPLOYMENT_REPAIR_ACKNOWLEDGEMENT_FILENAME
    )
    assert acknowledgements[-1]["request_id"] == "repair-request-1"
    assert acknowledgements[-1]["status"] == "rejected"


@pytest.mark.parametrize(
    "failure_stage",
    ["request_construction", "prior_validation", "candidate_normalization"],
)
def test_repair_stage_exception_retires_and_terminally_rejects(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure_stage: str,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator)
    controller.observations_by_tool_name[TOOL_NAME] = _observation()
    controller.queue_post_deployment_repair_requests([_repair_request()])

    def fail(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError(f"simulated {failure_stage} failure")

    if failure_stage == "request_construction":
        monkeypatch.setattr(controller, "_generation_request", fail)
    elif failure_stage == "prior_validation":
        monkeypatch.setattr(online_birth, "validate_generated_tool", fail)
    else:
        monkeypatch.setattr(
            online_birth,
            "_normalize_live_birth_routing_metadata",
            fail,
        )
    acknowledgements: list[tuple[str, int, str, str]] = []

    assert (
        controller.process_pending_repairs(
            completed_count=8,
            acknowledge=lambda *args: acknowledgements.append(args) or {},
        )
        == ()
    )
    entry = store.get(TOOL_NAME)
    assert entry is not None and entry.version == 1 and entry.retired
    assert controller.pending_repair_requests == []
    assert controller.canary_state_by_tool == {}
    assert controller.repair_transactions_by_tool == {}
    assert acknowledgements == [(TOOL_NAME, 1, "repair-request-1", "rejected")]


def test_restart_pops_terminal_pending_canary_and_transaction_state(
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator)
    request = _repair_request()
    controller.pending_repair_requests = [request]
    controller.canary_state_by_tool[TOOL_NAME] = {
        "request_id": "repair-request-1",
        "tool_version": 1,
    }
    controller.repair_transactions_by_tool[TOOL_NAME] = {
        "request_id": "repair-request-1",
        "target_tool_version": 2,
    }
    controller._write_repair_state()  # noqa: SLF001
    acknowledgement_path = (
        controller.output_dir
        / online_birth.POST_DEPLOYMENT_REPAIR_ACKNOWLEDGEMENT_FILENAME
    )
    acknowledgement_path.write_text(
        json.dumps(
            {
                "request_id": "repair-request-1",
                "tool_name": TOOL_NAME,
                "new_version": 1,
                "status": "rejected",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    restarted = _controller(
        tmp_path,
        DeterministicRepairGenerator(store=store, candidate=_repaired_tool()),
    )

    assert restarted.pending_repair_requests == []
    assert restarted.canary_state_by_tool == {}
    assert restarted.repair_transactions_by_tool == {}
    assert "repair-request-1" in restarted.handled_repair_request_ids
    assert store.get(TOOL_NAME).retired is True  # type: ignore[union-attr]


def test_restart_resets_legacy_canary_soft_evidence_fail_closed(
    tmp_path: Path,
) -> None:
    store = RegistryStore(tmp_path / "registry")
    store.put(_accepted_historical_entry(_faulty_tool()))
    generator = DeterministicRepairGenerator(store=store, candidate=_repaired_tool())
    controller = _controller(tmp_path, generator)
    controller.observations_by_tool_name[TOOL_NAME] = _observation()
    controller.queue_post_deployment_repair_requests([_repair_request()])
    assert controller.process_pending_repairs(completed_count=8) == (TOOL_NAME,)
    legacy = controller.canary_state_by_tool[TOOL_NAME]
    legacy.pop("evidence_schema_version")
    legacy["outcomes"] = [1.0, 1.0, 1.0]
    legacy["called_count"] = 3
    legacy["attributable_observation_count"] = 3
    legacy["runtime_failure_count"] = 1
    controller._write_repair_state()  # noqa: SLF001

    restarted = _controller(
        tmp_path,
        DeterministicRepairGenerator(store=store, candidate=_repaired_tool()),
    )
    recovered = restarted.canary_state_by_tool[TOOL_NAME]

    assert recovered["evidence_schema_version"] == 2
    assert recovered["outcomes"] == []
    assert recovered["called_count"] == 0
    assert recovered["attributable_observation_count"] == 0
    assert recovered["runtime_failure_count"] == 1
