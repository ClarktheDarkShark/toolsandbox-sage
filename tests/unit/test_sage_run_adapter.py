import copy
import json
import ssl
from pathlib import Path
from typing import Optional

import pytest

from sage_ts.adapters.sage_run_adapter import (
    SageRunConfig,
    _helper_adoption_retry_candidates,
    _helper_forbids_side_effect_followup,
    _helper_requires_side_effect_followup,
    _should_retry_visible_not_called,
    _side_effect_followup_failures,
    _side_effect_followup_failures_from_trace_events,
    _snapshot_registry_checkpoint,
    run_sage_with_registry,
)
from sage_ts.adapters.toolsandbox_adapter import (
    ResultHook,
    ScenarioTransform,
    ToolSandboxRunConfig,
)
from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily, ToolInput, ToolSpec
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.registry.store import RegistryStore
from sage_ts.validation.sandbox_validator import ToolExample, validate_generated_tool
from tool_sandbox.common.execution_context import ExecutionContext
from tool_sandbox.common.scenario import Scenario


def canonicalizer_tool() -> GeneratedTool:
    spec = ToolSpec(
        tool_name="canonicalize_connectivity_label",
        family=ToolFamily.CANONICALIZER,
        description="Normalize connectivity labels to stable internal labels.",
        inputs=(ToolInput("label", "str", "Raw connectivity label."),),
        output_annotation="str",
        generalization_rationale=(
            "Connectivity labels recur across ToolSandbox scenarios with spacing, "
            "punctuation, and synonym variants."
        ),
        inadequacy_evidence=(
            "ToolSandbox contains connectivity state tools, but no reusable tool for "
            "normalizing noisy user-facing connectivity labels."
        ),
    )
    code = """
def canonicalize_connectivity_label(label: str) -> str:
    cleaned = label.strip().lower().replace("-", " ").replace("_", " ")
    cleaned = " ".join(cleaned.split())
    if cleaned in {"wi fi", "wifi", "wireless"}:
        return "wifi"
    if cleaned in {"cell", "cellular", "mobile data"}:
        return "cellular"
    return cleaned
"""
    return GeneratedTool(spec=spec, code=code)


def test_snapshot_registry_checkpoint_copies_manifest_and_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "run"
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    (registry_dir / "registry_manifest.json").write_text(
        json.dumps({"entries": []}) + "\n",
        encoding="utf-8",
    )
    (registry_dir / "tool_lifecycle.json").write_text(
        json.dumps({"tool_lifecycle": {}}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SAGE_TS_SCENARIO_ORDER_INDEX", "4")

    checkpoint = _snapshot_registry_checkpoint(
        output_directory=output_dir,
        registry_dir=registry_dir,
        scenario_name="find current city?",
    )

    assert checkpoint is not None
    assert checkpoint.name == "after_0005_find_current_city"
    assert (checkpoint / "registry_manifest.json").exists()
    assert (checkpoint / "tool_lifecycle.json").exists()
    metadata = json.loads((checkpoint / "checkpoint.json").read_text())
    assert metadata["completed_count"] == 5
    assert metadata["scenario"] == "find current city?"


def test_side_effect_followup_not_required_for_abstaining_helper() -> None:
    assert not _helper_requires_side_effect_followup(
        [{"should_call_add_reminder": False, "abstain_reason": "missing_time_info"}]
    )


def test_visible_not_called_retry_is_off_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SAGE_SELF_EVOLVING_VISIBLE_NOT_CALLED_RETRY", raising=False)
    assert not _should_retry_visible_not_called(
        generated_visible=["plan_contact_update_from_id"],
        generated_attempted=[],
        generated_failed=[],
        similarity=0.9,
        outcome_similarity=0.0,
    )


def test_visible_not_called_retry_uses_score_for_hinted_tools_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_SELF_EVOLVING_VISIBLE_NOT_CALLED_RETRY", "1")
    assert not _should_retry_visible_not_called(
        generated_visible=["plan_contact_update_from_id"],
        generated_attempted=[],
        generated_failed=[],
        similarity=0.9,
        outcome_similarity=1.0,
    )

    assert _should_retry_visible_not_called(
        generated_visible=["plan_contact_update_from_id"],
        generated_attempted=[],
        generated_failed=[],
        similarity=0.9,
        outcome_similarity=0.0,
    )
    assert _should_retry_visible_not_called(
        generated_visible=[
            "plan_contact_lookup_query",
            "plan_contact_relationship_batch_update",
        ],
        generated_attempted=[],
        generated_failed=[],
        similarity=0.2,
        outcome_similarity=0.05,
    )
    assert not _should_retry_visible_not_called(
        generated_visible=[
            "plan_contact_lookup_query",
            "plan_contact_relationship_batch_update",
        ],
        generated_attempted=[],
        generated_failed=[],
        similarity=0.8,
        outcome_similarity=0.5,
    )

    assert not _should_retry_visible_not_called(
        generated_visible=["unhinted_helper"],
        generated_attempted=[],
        generated_failed=[],
        similarity=0.9,
        outcome_similarity=1.0,
    )
    assert _should_retry_visible_not_called(
        generated_visible=["unhinted_helper"],
        generated_attempted=[],
        generated_failed=[],
        similarity=0.0,
        outcome_similarity=0.0,
    )
    assert _should_retry_visible_not_called(
        generated_visible=["resolve_search_window_or_bounds"],
        generated_attempted=[],
        generated_failed=[],
        similarity=0.0,
        outcome_similarity=0.0,
    )


def test_visible_not_called_retry_targets_unattempted_hinted_tool_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_SELF_EVOLVING_VISIBLE_NOT_CALLED_RETRY", "1")
    visible = [
        "relative_day_time_to_timestamp",
        "prepare_location_search_args",
        "prepare_reminder_creation_args",
    ]

    assert _helper_adoption_retry_candidates(
        generated_visible=visible,
        generated_attempted=[
            "relative_day_time_to_timestamp",
            "prepare_location_search_args",
        ],
        generated_failed=[],
    ) == ["prepare_reminder_creation_args"]
    assert _should_retry_visible_not_called(
        generated_visible=visible,
        generated_attempted=[
            "relative_day_time_to_timestamp",
            "prepare_location_search_args",
        ],
        generated_failed=[],
        similarity=0.8,
        outcome_similarity=0.0,
    )
    assert not _should_retry_visible_not_called(
        generated_visible=visible,
        generated_attempted=[
            "relative_day_time_to_timestamp",
            "prepare_location_search_args",
        ],
        generated_failed=[],
        similarity=0.8,
        outcome_similarity=0.67,
    )


def test_visible_not_called_retry_keeps_recency_workflow_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_SELF_EVOLVING_VISIBLE_NOT_CALLED_RETRY", "1")
    visible = [
        "relative_day_time_to_timestamp",
        "resolve_search_window_or_bounds",
        "select_record_by_timestamp_extreme",
    ]

    assert (
        _helper_adoption_retry_candidates(
            generated_visible=visible,
            generated_attempted=["resolve_search_window_or_bounds"],
            generated_failed=[],
        )
        == visible
    )


def test_visible_not_called_retry_keeps_location_and_versioned_state_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_SELF_EVOLVING_VISIBLE_NOT_CALLED_RETRY", "1")
    visible = [
        "plan_device_state_action_sequence_v3",
        "prepare_location_search_args",
        "prepare_reminder_creation_args",
        "relative_day_time_to_timestamp",
    ]

    assert _helper_adoption_retry_candidates(
        generated_visible=visible,
        generated_attempted=[
            "relative_day_time_to_timestamp",
            "prepare_reminder_creation_args",
        ],
        generated_failed=[],
    ) == [
        "plan_device_state_action_sequence_v3",
        "prepare_location_search_args",
    ]
    assert _should_retry_visible_not_called(
        generated_visible=visible,
        generated_attempted=[
            "relative_day_time_to_timestamp",
            "prepare_reminder_creation_args",
        ],
        generated_failed=[],
        similarity=0.2,
        outcome_similarity=0.0,
    )


def test_visible_not_called_retry_keeps_safe_abstention_after_other_tool_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_SELF_EVOLVING_VISIBLE_NOT_CALLED_RETRY", "1")

    assert _helper_adoption_retry_candidates(
        generated_visible=[
            "prepare_safe_action_or_abstain",
            "select_record_by_timestamp_extreme",
        ],
        generated_attempted=["select_record_by_timestamp_extreme"],
        generated_failed=[],
    ) == ["prepare_safe_action_or_abstain"]


def test_visible_not_called_retry_skips_safe_abstention_after_full_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_SELF_EVOLVING_VISIBLE_NOT_CALLED_RETRY", "1")

    assert not _should_retry_visible_not_called(
        generated_visible=["prepare_safe_action_or_abstain"],
        generated_attempted=[],
        generated_failed=[],
        similarity=1.0,
        outcome_similarity=None,
    )

    assert _should_retry_visible_not_called(
        generated_visible=["prepare_safe_action_or_abstain"],
        generated_attempted=[],
        generated_failed=[],
        similarity=0.0,
        outcome_similarity=None,
    )


def test_visible_not_called_retry_skips_after_generated_tool_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAGE_SELF_EVOLVING_VISIBLE_NOT_CALLED_RETRY", "1")
    assert not _should_retry_visible_not_called(
        generated_visible=[
            "relative_day_time_to_timestamp",
            "prepare_reminder_creation_args",
        ],
        generated_attempted=["relative_day_time_to_timestamp"],
        generated_failed=["relative_day_time_to_timestamp"],
        similarity=0.8,
        outcome_similarity=0.67,
    )


def test_side_effect_followup_required_for_positive_helper_result() -> None:
    assert _helper_requires_side_effect_followup(
        [{"should_call_add_reminder": True, "add_reminder_kwargs": {"content": "x"}}]
    )


def test_side_effect_followup_forbidden_for_abstaining_helper() -> None:
    assert _helper_forbids_side_effect_followup(
        [
            {
                "should_call_add_reminder": False,
                "abstain_reason": (
                    "optional_location_lookup_pending_do_not_call_add_reminder"
                ),
            }
        ]
    )


def test_side_effect_preservation_allows_prerequisite_after_abstain() -> None:
    messages = [
        {"role": "tool", "name": "prepare", "content": {"should_call": False}},
        {
            "role": "assistant",
            "tool_calls": [{"function": {"name": "search_location_around_lat_lon"}}],
        },
        {"role": "tool", "name": "search_location_around_lat_lon", "content": "[]"},
        {
            "role": "assistant",
            "tool_calls": [{"function": {"name": "add_reminder"}}],
        },
    ]

    assert not _side_effect_followup_failures(
        messages,
        helper_name="prepare",
        required_original_tool_calls=("add_reminder",),
    )


def test_side_effect_preservation_flags_direct_side_effect_after_abstain() -> None:
    messages = [
        {"role": "tool", "name": "prepare", "content": {"should_call": False}},
        {
            "role": "assistant",
            "tool_calls": [{"function": {"name": "add_reminder"}}],
        },
    ]

    assert _side_effect_followup_failures(
        messages,
        helper_name="prepare",
        required_original_tool_calls=("add_reminder",),
    )


def test_side_effect_preservation_requires_next_call_after_success() -> None:
    messages = [
        {"role": "tool", "name": "prepare", "content": {"should_call": True}},
        {
            "role": "assistant",
            "tool_calls": [{"function": {"name": "search_location_around_lat_lon"}}],
        },
    ]

    assert _side_effect_followup_failures(
        messages,
        helper_name="prepare",
        required_original_tool_calls=("add_reminder",),
    )


def test_side_effect_preservation_ignores_prerequisite_route_calls() -> None:
    messages = [
        {
            "role": "assistant",
            "tool_calls": [{"function": {"name": "get_current_timestamp"}}],
        },
        {"role": "tool", "name": "get_current_timestamp", "content": "1"},
        {"role": "tool", "name": "days_between_timestamps", "content": {"days": 3}},
    ]

    assert not _side_effect_followup_failures(
        messages,
        helper_name="days_between_timestamps",
        required_original_tool_calls=("get_current_timestamp", "search_holiday"),
    )


def test_side_effect_preservation_ignores_scalar_helper_without_followup_contract() -> (
    None
):
    messages = [
        {
            "role": "tool",
            "name": "normalize_contact_phone_number",
            "content": {
                "normalized_phone_number": "+10000000000",
                "is_valid": True,
                "abstain_reason": "",
            },
        },
        {
            "role": "assistant",
            "tool_calls": [{"function": {"name": "search_contacts"}}],
        },
    ]

    assert not _side_effect_followup_failures(
        messages,
        helper_name="normalize_contact_phone_number",
        required_original_tool_calls=(
            "add_contact",
            "remove_contact",
            "modify_contact",
            "search_contacts",
            "send_message_with_phone_number",
        ),
    )


def test_side_effect_preservation_ignores_non_mapping_scalar_helper_output() -> None:
    messages = [
        {
            "role": "tool",
            "name": "relative_day_time_to_timestamp",
            "content": "1780434000.0",
        },
        {
            "role": "assistant",
            "tool_calls": [{"function": {"name": "search_location_around_lat_lon"}}],
        },
    ]

    assert not _side_effect_followup_failures(
        messages,
        helper_name="relative_day_time_to_timestamp",
        required_original_tool_calls=("add_reminder", "modify_reminder"),
    )


def test_side_effect_trace_ignores_non_mapping_scalar_helper_output() -> None:
    events = [
        {"tool_name": "relative_day_time_to_timestamp", "result": 1780434000.0},
        {"tool_name": "search_location_around_lat_lon", "result": []},
    ]

    assert not _side_effect_followup_failures_from_trace_events(
        events,
        helper_name="relative_day_time_to_timestamp",
        required_side_effect_calls=("add_reminder", "modify_reminder"),
    )


def test_side_effect_preservation_honors_should_call_tool_contract() -> None:
    messages = [
        {
            "role": "tool",
            "name": "prepare_contact",
            "content": {
                "downstream_tool_name": "add_contact",
                "downstream_tool_kwargs": {
                    "name": "Ada",
                    "phone_number": "+10000000000",
                },
                "should_call_tool": True,
                "abstain_reason": "",
            },
        },
        {
            "role": "assistant",
            "tool_calls": [{"function": {"name": "search_contacts"}}],
        },
    ]

    assert _side_effect_followup_failures(
        messages,
        helper_name="prepare_contact",
        required_original_tool_calls=("add_contact",),
    )


def test_side_effect_preservation_allows_target_only_selection_before_side_effect() -> (
    None
):
    messages = [
        {
            "role": "tool",
            "name": "select_action_target_by_recency",
            "content": {
                "selected_record": {"reminder_id": "r1", "creation_timestamp": 2.0},
                "selected_id": "r1",
                "downstream_tool_name": "modify_reminder",
                "downstream_tool_kwargs": {},
                "should_call_tool": False,
                "abstain_reason": "missing_update_fields",
                "final_answer_recommendation": (
                    "use_selected_record:modify_reminder:reminder_id=r1; "
                    "supply required update fields from visible context before "
                    "calling the original tool"
                ),
            },
        },
        {
            "role": "assistant",
            "tool_calls": [{"function": {"name": "modify_reminder"}}],
        },
    ]

    assert not _side_effect_followup_failures(
        messages,
        helper_name="select_action_target_by_recency",
        required_original_tool_calls=("modify_reminder",),
    )


def test_side_effect_preservation_flags_target_only_selection_without_side_effect() -> (
    None
):
    messages = [
        {
            "role": "tool",
            "name": "select_action_target_by_recency",
            "content": {
                "selected_record": {"reminder_id": "r1", "creation_timestamp": 2.0},
                "selected_id": "r1",
                "downstream_tool_name": "modify_reminder",
                "downstream_tool_kwargs": {},
                "should_call_tool": False,
                "abstain_reason": "missing_update_fields",
                "final_answer_recommendation": (
                    "use_selected_record:modify_reminder:reminder_id=r1; "
                    "supply required update fields from visible context before "
                    "calling the original tool"
                ),
            },
        },
        {"role": "assistant", "content": "Done."},
    ]

    assert _side_effect_followup_failures(
        messages,
        helper_name="select_action_target_by_recency",
        required_original_tool_calls=("modify_reminder",),
    )


def _registry_with_canonicalizer(path: Path) -> RegistryStore:
    tool = canonicalizer_tool()
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample({"label": "Wi-Fi"}, "wifi"),
            ToolExample({"label": "mobile data"}, "cellular"),
        ),
    )
    assert validation.accepted
    store = RegistryStore(path)
    store.put(RegistryEntry.accepted(tool, validation, birth_scenario="toy_birth"))
    return store


def test_sage_runner_logs_frozen_registry_reuse_without_mutating_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = _registry_with_canonicalizer(tmp_path / "registry")

    def fake_sequence(
        config: ToolSandboxRunConfig,
        *,
        scenario_transform: ScenarioTransform,
        result_hook: Optional[ResultHook] = None,
        **_kwargs: object,
    ) -> Path:
        output_dir = tmp_path / "run"
        output_dir.mkdir()
        scenario = Scenario(
            starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
        )
        enhanced = scenario_transform("toy_birth", scenario, output_dir)
        tool = enhanced.starting_context.get_available_tools(scrambling_allowed=False)[
            "canonicalize_connectivity_label"
        ]
        assert tool("Wi-Fi") == "wifi"
        if result_hook is not None:
            result_hook("toy_birth", enhanced, {"similarity": 1}, output_dir)
        return output_dir

    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.run_scenario_sequence",
        fake_sequence,
    )

    output_dir = run_sage_with_registry(
        SageRunConfig(
            agent="Unhelpful",
            user="GPT_4_o_2024_05_13",
            scenario_names=("toy_birth",),
            output_dir=tmp_path / "outputs",
            registry_dir=store.root,
        )
    )

    entry = store.get("canonicalize_connectivity_label")
    assert entry is not None
    assert entry.reuse_count == 0

    reuse_event = json.loads((output_dir / "reuse_events.jsonl").read_text())
    assert reuse_event["scenario"] == "toy_birth"
    assert reuse_event["tool_name"] == "canonicalize_connectivity_label"

    run_events = [
        json.loads(line)
        for line in (output_dir / "sage_run_events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert run_events[0]["event"] == "registry_load"
    assert run_events[0]["registry_tools"] == ["canonicalize_connectivity_label"]
    assert run_events[-1]["final_registry_tools"] == ["canonicalize_connectivity_label"]

    visibility = json.loads((output_dir / "scenario_tool_visibility.jsonl").read_text())
    assert "canonicalize_connectivity_label" in visibility["available_tools"]

    selection = json.loads((output_dir / "scenario_tool_selection.jsonl").read_text())
    assert selection["scenario"] == "toy_birth"
    assert selection["selection_status"] == "generated_tool_called"
    assert selection["generated_tools_called"] == ["canonicalize_connectivity_label"]

    summary = json.loads((output_dir / "selection_summary.json").read_text())
    assert summary["generated_tool_called_scenarios"] == 1


def test_generation_enabled_registry_tools_do_not_capture_unpicklable_generator(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Retained tool wrappers must stay pickle-safe when live generation is on."""
    store = _registry_with_canonicalizer(tmp_path / "registry")

    class UnpicklableGenerator:
        def __init__(self) -> None:
            self.ssl_context = ssl.create_default_context()

    def fake_sequence(
        config: ToolSandboxRunConfig,
        *,
        scenario_transform: ScenarioTransform,
        result_hook: Optional[ResultHook] = None,
        **_kwargs: object,
    ) -> Path:
        output_dir = tmp_path / "run"
        output_dir.mkdir()
        scenario = Scenario(
            starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
        )
        enhanced = scenario_transform("toy_birth", scenario, output_dir)
        copy.deepcopy(enhanced.starting_context)
        tool = enhanced.starting_context.get_available_tools(scrambling_allowed=False)[
            "canonicalize_connectivity_label"
        ]
        assert tool("Wi-Fi") == "wifi"
        if result_hook is not None:
            result_hook("toy_birth", enhanced, {"similarity": 1}, output_dir)
        return output_dir

    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.run_scenario_sequence",
        fake_sequence,
    )

    run_sage_with_registry(
        SageRunConfig(
            agent="Unhelpful",
            user="GPT_4_o_2024_05_13",
            scenario_names=("toy_birth",),
            output_dir=tmp_path / "outputs",
            registry_dir=store.root,
        ),
        generator=UnpicklableGenerator(),  # type: ignore[arg-type]
    )


def test_sage_runner_selection_summary_includes_resumed_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = _registry_with_canonicalizer(tmp_path / "registry")

    def fake_sequence(
        config: ToolSandboxRunConfig,
        *,
        scenario_transform: ScenarioTransform,
        result_hook: Optional[ResultHook] = None,
        **_kwargs: object,
    ) -> Path:
        output_dir = tmp_path / "run"
        output_dir.mkdir()
        (output_dir / "scenario_tool_selection.jsonl").write_text(
            json.dumps(
                {
                    "scenario": "previous_scenario",
                    "generated_tools_visible": ["canonicalize_connectivity_label"],
                    "generated_tools_called": ["canonicalize_connectivity_label"],
                    "selection_status": "generated_tool_called",
                    "relevance_gating_hid_retained_tool": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        scenario = Scenario(
            starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
        )
        enhanced = scenario_transform("toy_birth", scenario, output_dir)
        tool = enhanced.starting_context.get_available_tools(scrambling_allowed=False)[
            "canonicalize_connectivity_label"
        ]
        assert tool("mobile data") == "cellular"
        if result_hook is not None:
            result_hook("toy_birth", enhanced, {"similarity": 1}, output_dir)
        return output_dir

    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.run_scenario_sequence",
        fake_sequence,
    )

    output_dir = run_sage_with_registry(
        SageRunConfig(
            agent="Unhelpful",
            user="GPT_4_o_2024_05_13",
            scenario_names=("previous_scenario", "toy_birth"),
            output_dir=tmp_path / "outputs",
            registry_dir=store.root,
        )
    )

    summary = json.loads((output_dir / "selection_summary.json").read_text())
    assert summary["scenario_count"] == 2
    assert summary["generated_tool_visible_scenarios"] == 2
    assert summary["generated_tool_called_scenarios"] == 2


def test_sage_runner_counts_failed_generated_tool_attempts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = _registry_with_canonicalizer(tmp_path / "registry")

    def fake_sequence(
        config: ToolSandboxRunConfig,
        *,
        scenario_transform: ScenarioTransform,
        result_hook: Optional[ResultHook] = None,
        **_kwargs: object,
    ) -> Path:
        output_dir = tmp_path / "run"
        output_dir.mkdir()
        scenario = Scenario(
            starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
        )
        enhanced = scenario_transform("toy_birth", scenario, output_dir)
        assert (
            "canonicalize_connectivity_label"
            in enhanced.starting_context.get_available_tools(scrambling_allowed=False)
        )
        trajectory = output_dir / "trajectories" / "toy_birth"
        trajectory.mkdir(parents=True)
        (trajectory / "conversation.json").write_text(
            json.dumps(
                [
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "type": "function",
                                "function": {
                                    "name": "canonicalize_connectivity_label",
                                    "arguments": "{}",
                                },
                            }
                        ],
                    },
                    {
                        "role": "tool",
                        "name": "canonicalize_connectivity_label",
                        "content": (
                            "TypeError: canonicalize_connectivity_label() "
                            "missing 1 required positional argument: 'label'"
                        ),
                    },
                ]
            ),
            encoding="utf-8",
        )
        if result_hook is not None:
            result_hook("toy_birth", enhanced, {"similarity": 0.2}, output_dir)
        return output_dir

    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.run_scenario_sequence",
        fake_sequence,
    )

    output_dir = run_sage_with_registry(
        SageRunConfig(
            agent="Unhelpful",
            user="GPT_4_o_2024_05_13",
            scenario_names=("toy_birth",),
            output_dir=tmp_path / "outputs",
            registry_dir=store.root,
        )
    )

    selection = json.loads((output_dir / "scenario_tool_selection.jsonl").read_text())
    assert selection["selection_status"] == "generated_tool_attempt_failed"
    assert selection["generated_tools_attempted"] == ["canonicalize_connectivity_label"]
    assert selection["generated_tools_failed"] == ["canonicalize_connectivity_label"]
    assert selection["generated_tools_called"] == []

    summary = json.loads((output_dir / "selection_summary.json").read_text())
    assert summary["generated_tool_attempted_scenarios"] == 1
    assert summary["generated_tool_failed_scenarios"] == 1
    assert summary["generated_tool_called_scenarios"] == 0
