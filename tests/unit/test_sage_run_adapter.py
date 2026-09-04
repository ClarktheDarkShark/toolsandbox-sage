import copy
import inspect
import json
import ssl
from multiprocessing import get_context
from pathlib import Path
from typing import Optional

import pytest

from sage_ts.adapters.sage_run_adapter import (
    InventoryAuthorityError,
    SageRunConfig,
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
from scripts.run_sage_protocol import _candidate_protocol_event_hook
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
        positive_triggers=("general_visible_task",),
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


def test_side_effect_safety_flags_native_action_after_complete_tool_abstains() -> None:
    messages = [
        {
            "role": "tool",
            "name": "complete_contact_action",
            "content": {
                "status": "abstain",
                "confirmation": "",
                "abstain_reason": "The target contact is ambiguous.",
                "native_action": "",
                "native_result": None,
            },
        },
        {
            "role": "assistant",
            "tool_calls": [{"function": {"name": "remove_contact"}}],
        },
    ]

    assert _side_effect_followup_failures(
        messages,
        helper_name="complete_contact_action",
        required_original_tool_calls=("remove_contact",),
    )


def test_side_effect_trace_flags_native_action_after_complete_tool_abstains() -> None:
    events = [
        {
            "tool_name": "complete_contact_action",
            "result": {
                "status": "abstain",
                "confirmation": "",
                "abstain_reason": "The target contact is ambiguous.",
                "native_action": "",
                "native_result": None,
            },
        },
        {"tool_name": "remove_contact", "result": None},
    ]

    assert _side_effect_followup_failures_from_trace_events(
        events,
        helper_name="complete_contact_action",
        required_side_effect_calls=("remove_contact",),
    )


def test_side_effect_safety_allows_generated_route_without_native_followup() -> None:
    messages = [
        {"role": "tool", "name": "prepare", "content": {"should_call": True}},
        {
            "role": "assistant",
            "tool_calls": [{"function": {"name": "search_location_around_lat_lon"}}],
        },
    ]

    assert not _side_effect_followup_failures(
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


def test_side_effect_preservation_accepts_scrambled_native_action_result() -> None:
    messages = [
        {
            "role": "tool",
            "name": "generated_tools_0",
            "content": {
                "status": "success",
                "native_action": "add_reminder",
                "native_result": "reminder-1",
            },
        }
    ]
    traces = [
        {
            "tool_name": "add_reminder",
            "arguments": {"content": "Buy milk"},
            "result": "reminder-1",
        }
    ]

    assert not _side_effect_followup_failures(
        messages,
        helper_name="prepare_reminder_creation_args",
        required_original_tool_calls=("add_reminder",),
        actual_tool_trace_events=traces,
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


def test_side_effect_safety_leaves_missing_native_followup_to_outcome() -> None:
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

    assert not _side_effect_followup_failures(
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


def test_side_effect_safety_allows_target_selection_without_native_side_effect() -> (
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

    assert not _side_effect_followup_failures(
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


@pytest.fixture
def matched_authority_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOOL_SANDBOX_FIXED_NOW_TIMESTAMP", "1784832588")
    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.git_sha",
        lambda: "a" * 40,
    )
    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter._tracked_source_state",
        lambda _root: {
            "tracked_changes_present": False,
            "tracked_diff_sha256": "b" * 64,
        },
    )


def test_inventory_authority_capture_and_replay_restore_exact_pre_task_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    matched_authority_context: None,
) -> None:
    del matched_authority_context
    benchmark_manifest = tmp_path / "benchmark_manifest.json"
    benchmark_manifest.write_text('{"sealed": true}\n', encoding="utf-8")
    rapidapi_fixture = tmp_path / "rapidapi_fixture.json"
    rapidapi_fixture.write_text('{"fixture": "sealed"}\n', encoding="utf-8")
    monkeypatch.setenv("TOOLSANDBOX_RAPID_CACHE_MODE", "strict")
    monkeypatch.setenv("TOOLSANDBOX_RAPID_CACHE_PATH", str(rapidapi_fixture))
    monkeypatch.setenv("SAGE_OPENAI_MAX_RETRIES", "5")
    donor_store = _registry_with_canonicalizer(tmp_path / "donor_registry")
    donor_lifecycle = {
        "artifact_type": "self_evolution_tool_lifecycle",
        "tool_lifecycle": {},
    }
    (donor_store.root / "tool_lifecycle.json").write_text(
        json.dumps(donor_lifecycle) + "\n",
        encoding="utf-8",
    )
    authority_root = tmp_path / "inventory_authority"
    scenario_names = ("toy_birth", "toy_birth_2")

    def capture_sequence(
        config: ToolSandboxRunConfig,
        *,
        scenario_transform: ScenarioTransform,
        result_hook: Optional[ResultHook] = None,
        **_kwargs: object,
    ) -> Path:
        assert config.actor_selection_mode == "policy"
        output_dir = tmp_path / "capture_run"
        output_dir.mkdir()
        for index, name in enumerate(scenario_names):
            monkeypatch.setenv("SAGE_TS_SCENARIO_ORDER_INDEX", str(index))
            scenario = Scenario(
                starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
            )
            enhanced = scenario_transform(name, scenario, output_dir)
            if index == 0:
                partial = json.loads(
                    (authority_root / "inventory_authority.partial.json").read_text(
                        encoding="utf-8"
                    )
                )
                assert partial["complete"] is False
                assert partial["expected_task_count"] == 2
                assert partial["task_count"] == 1
                assert partial["last_task"]["scenario"] == scenario_names[0]
                assert "tasks" not in partial
                assert "tasks_sha256" not in partial
            assert (
                "canonicalize_connectivity_label"
                in enhanced.starting_context.get_available_tools(
                    scrambling_allowed=False
                )
            )
            if result_hook is not None:
                result_hook(name, enhanced, {"similarity": 1.0}, output_dir)
        return output_dir

    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.run_scenario_sequence",
        capture_sequence,
    )
    run_sage_with_registry(
        SageRunConfig(
            agent="gpt-4o-mini",
            user="gpt-4o-mini",
            scenario_names=scenario_names,
            output_dir=tmp_path / "capture_output",
            registry_dir=donor_store.root,
            generation_model="gpt-4o-mini-generation",
            recurrence_threshold=3,
            actor_selection_mode="policy",
            manifest_path=benchmark_manifest,
            inventory_authority_capture_dir=authority_root,
        )
    )

    authority = json.loads(
        (authority_root / "inventory_authority.json").read_text(encoding="utf-8")
    )
    assert not (authority_root / "inventory_authority.partial.json").exists()
    assert authority["complete"] is True
    assert authority["source_actor_selection_mode"] == "policy"
    assert authority["source_generation_enabled"] is False
    assert authority["expected_task_count"] == 2
    assert len(authority["tasks"]) == 2
    shared_context = authority["shared_context"]
    assert shared_context["agent"] == "gpt-4o-mini"
    assert shared_context["user"] == "gpt-4o-mini"
    assert shared_context["generation_model"] == "gpt-4o-mini-generation"
    assert shared_context["benchmark_manifest_present"] is True
    assert shared_context["benchmark_manifest_sha256"]
    assert shared_context["base_tool_policy"] == "upstream"
    assert shared_context["recurrence_threshold"] == 3
    assert shared_context["fixed_toolsandbox_timestamp"] == "1784832588"
    assert shared_context["source_git_commit"] == "a" * 40
    assert shared_context["tracked_source_state"] == {
        "tracked_changes_present": False,
        "tracked_diff_sha256": "b" * 64,
    }
    assert shared_context["behavior_environment"]["SAGE_OPENAI_MAX_RETRIES"] == "5"
    assert shared_context["rapidapi_fixture"]["configured"] is True
    assert shared_context["rapidapi_fixture"]["present"] is True
    assert shared_context["rapidapi_fixture"]["sha256"]
    assert authority["shared_context_sha256"]
    assert authority["scenario_names"] == list(scenario_names)
    assert authority["task_count"] == 2
    assert [task["routed_generated_tool_names"] for task in authority["tasks"]] == [
        ["canonicalize_connectivity_label"],
        ["canonicalize_connectivity_label"],
    ]
    assert all(task["routed_inventory_sha256"] for task in authority["tasks"])

    replay_store = RegistryStore(tmp_path / "replay_registry")

    def replay_sequence(
        config: ToolSandboxRunConfig,
        *,
        scenario_transform: ScenarioTransform,
        result_hook: Optional[ResultHook] = None,
        **_kwargs: object,
    ) -> Path:
        assert config.actor_selection_mode == "auto"
        output_dir = tmp_path / "replay_run"
        output_dir.mkdir()
        for index, name in enumerate(scenario_names):
            monkeypatch.setenv("SAGE_TS_SCENARIO_ORDER_INDEX", str(index))
            scenario = Scenario(
                starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
            )
            enhanced = scenario_transform(name, scenario, output_dir)
            assert (
                "canonicalize_connectivity_label"
                in enhanced.starting_context.get_available_tools(
                    scrambling_allowed=False
                )
            )
            restored = replay_store.get("canonicalize_connectivity_label")
            assert restored is not None and not restored.retired
            tool = enhanced.starting_context.get_available_tools(
                scrambling_allowed=False
            )["canonicalize_connectivity_label"]
            assert tool("Wi-Fi") == "wifi"
            if result_hook is not None:
                result_hook(name, enhanced, {"similarity": 1.0}, output_dir)
            if index == 0:
                # Simulate an arm-specific lifecycle decision after task 1. Task 2
                # must still receive the donor's unretired entry and lifecycle.
                replay_store.retire("canonicalize_connectivity_label")
                (replay_store.root / "tool_lifecycle.json").write_text(
                    json.dumps(
                        {
                            "tool_lifecycle": {
                                "canonicalize_connectivity_label": {
                                    "decision": "parked"
                                }
                            }
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
        return output_dir

    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.run_scenario_sequence",
        replay_sequence,
    )
    replay_output = run_sage_with_registry(
        SageRunConfig(
            agent="gpt-4o-mini",
            user="gpt-4o-mini",
            scenario_names=scenario_names,
            output_dir=tmp_path / "replay_output",
            registry_dir=replay_store.root,
            generation_model="gpt-4o-mini-generation",
            recurrence_threshold=3,
            actor_selection_mode="auto",
            manifest_path=benchmark_manifest,
            inventory_authority_replay_dir=authority_root,
        )
    )

    replay_summary = json.loads(
        (replay_output / "selection_summary.json").read_text(encoding="utf-8")
    )
    assert replay_summary["inventory_authority_mode"] == "replay"
    assert replay_summary["inventory_authority_task_count"] == 2
    assert replay_summary["inventory_authority_controls_later_exposure"] is True
    assert replay_summary["generation_enabled"] is False
    assert replay_summary["inventory_authority_source_generation_enabled"] is False
    assert (
        replay_summary["inventory_authority_shared_context_sha256"]
        == authority["shared_context_sha256"]
    )
    assert (
        replay_summary["inventory_authority_tasks_sha256"] == authority["tasks_sha256"]
    )
    replay_reuse_events = [
        json.loads(line)
        for line in (replay_output / "reuse_events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert [event["scenario"] for event in replay_reuse_events] == list(scenario_names)
    assert all(
        event["tool_name"] == "canonicalize_connectivity_label"
        for event in replay_reuse_events
    )
    restored_entry = replay_store.get("canonicalize_connectivity_label")
    assert restored_entry is not None and restored_entry.reuse_count == 0
    assert (
        json.loads(
            (replay_store.root / "tool_lifecycle.json").read_text(encoding="utf-8")
        )
        == donor_lifecycle
    )


def test_inventory_authority_captures_same_task_birth_and_replay_skips_repriming(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    matched_authority_context: None,
) -> None:
    del matched_authority_context
    authority_root = tmp_path / "inventory_authority"
    donor_store = RegistryStore(tmp_path / "donor_registry")
    scenario_names = ("toy_birth",)

    class FakeBirthController:
        prime_allowed = True
        initialization_count = 0
        prime_count = 0

        def __init__(self, *, store: RegistryStore, **_kwargs: object) -> None:
            type(self).initialization_count += 1
            self.store = store

        def prime_before_scenario(
            self, _scenario_name: str, _scenario: Scenario
        ) -> list[str]:
            type(self).prime_count += 1
            if not self.prime_allowed:
                raise AssertionError("replay must not independently re-prime births")
            born = _registry_with_canonicalizer(self.store.root)
            assert born.get("canonicalize_connectivity_label") is not None
            return ["canonicalize_connectivity_label"]

    class FakeReflectionController:
        @classmethod
        def from_env(cls, **_kwargs: object) -> "FakeReflectionController":
            return cls()

        def assert_fresh_control_complete(
            self, _scenario_names: tuple[str, ...]
        ) -> None:
            return None

    def one_scenario_sequence(
        _config: ToolSandboxRunConfig,
        *,
        scenario_transform: ScenarioTransform,
        **_kwargs: object,
    ) -> Path:
        output_dir = tmp_path / (
            "capture_run" if FakeBirthController.prime_allowed else "replay_run"
        )
        output_dir.mkdir()
        monkeypatch.setenv("SAGE_TS_SCENARIO_ORDER_INDEX", "0")
        scenario = Scenario(
            starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
        )
        enhanced = scenario_transform("toy_birth", scenario, output_dir)
        assert (
            "canonicalize_connectivity_label"
            in enhanced.starting_context.get_available_tools(scrambling_allowed=False)
        )
        return output_dir

    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.OnlineBirthController",
        FakeBirthController,
    )
    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.SelfEvolutionReflectionController",
        FakeReflectionController,
    )
    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.run_scenario_sequence",
        one_scenario_sequence,
    )
    run_sage_with_registry(
        SageRunConfig(
            agent="gpt-4o-mini",
            user="gpt-4o-mini",
            scenario_names=scenario_names,
            output_dir=tmp_path / "capture_output",
            registry_dir=donor_store.root,
            inventory_authority_capture_dir=authority_root,
        ),
        generator=object(),  # type: ignore[arg-type]
    )
    authority = json.loads(
        (authority_root / "inventory_authority.json").read_text(encoding="utf-8")
    )
    assert authority["source_generation_enabled"] is True
    assert authority["tasks"][0]["registry_manifest_present"] is True
    assert authority["tasks"][0]["routed_generated_tool_names"] == [
        "canonicalize_connectivity_label"
    ]
    assert FakeBirthController.initialization_count == 1
    assert FakeBirthController.prime_count == 1

    FakeBirthController.prime_allowed = False
    replay_store = RegistryStore(tmp_path / "replay_registry")
    run_sage_with_registry(
        SageRunConfig(
            agent="gpt-4o-mini",
            user="gpt-4o-mini",
            scenario_names=scenario_names,
            output_dir=tmp_path / "replay_output",
            registry_dir=replay_store.root,
            actor_selection_mode="auto",
            inventory_authority_replay_dir=authority_root,
        )
    )
    assert FakeBirthController.initialization_count == 1
    assert FakeBirthController.prime_count == 1


def test_inventory_authority_replay_rejects_independent_generator(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="requires generator=None"):
        run_sage_with_registry(
            SageRunConfig(
                agent="gpt-4o-mini",
                user="gpt-4o-mini",
                scenario_names=("toy_birth",),
                output_dir=tmp_path / "replay_output",
                registry_dir=tmp_path / "replay_registry",
                actor_selection_mode="auto",
                inventory_authority_replay_dir=tmp_path / "inventory_authority",
            ),
            generator=object(),  # type: ignore[arg-type]
        )


def test_inventory_authority_replay_rejects_nonempty_registry(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "replay_registry"
    registry.mkdir()
    (registry / "tool_lifecycle.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="requires an empty registry directory"):
        run_sage_with_registry(
            SageRunConfig(
                agent="gpt-4o-mini",
                user="gpt-4o-mini",
                scenario_names=("toy_birth",),
                output_dir=tmp_path / "replay_output",
                registry_dir=registry,
                actor_selection_mode="auto",
                inventory_authority_replay_dir=tmp_path / "inventory_authority",
            )
        )


@pytest.mark.parametrize(
    ("capture", "actor_selection_mode", "message"),
    (
        (True, "auto", "capture requires actor_selection_mode='policy'"),
        (False, "policy", "replay requires actor_selection_mode='auto'"),
    ),
)
def test_inventory_authority_core_enforces_treatment_modes(
    tmp_path: Path,
    *,
    capture: bool,
    actor_selection_mode: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        run_sage_with_registry(
            SageRunConfig(
                agent="gpt-4o-mini",
                user="gpt-4o-mini",
                scenario_names=("toy_birth",),
                output_dir=tmp_path / "output",
                registry_dir=tmp_path / "registry",
                actor_selection_mode=actor_selection_mode,
                inventory_authority_capture_dir=(
                    tmp_path / "authority" if capture else None
                ),
                inventory_authority_replay_dir=(
                    None if capture else tmp_path / "authority"
                ),
            )
        )


def test_inventory_authority_requires_frozen_toolsandbox_clock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("TOOL_SANDBOX_FIXED_NOW_TIMESTAMP", raising=False)
    with pytest.raises(ValueError, match="requires a fixed ToolSandbox timestamp"):
        run_sage_with_registry(
            SageRunConfig(
                agent="gpt-4o-mini",
                user="gpt-4o-mini",
                scenario_names=("toy_birth",),
                output_dir=tmp_path / "output",
                registry_dir=tmp_path / "registry",
                actor_selection_mode="policy",
                inventory_authority_capture_dir=tmp_path / "authority",
            )
        )


def test_inventory_authority_replay_rejects_shared_context_drift_before_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    matched_authority_context: None,
) -> None:
    del matched_authority_context
    donor_store = _registry_with_canonicalizer(tmp_path / "donor_registry")
    authority_root = tmp_path / "inventory_authority"

    def capture_sequence(
        _config: ToolSandboxRunConfig,
        *,
        scenario_transform: ScenarioTransform,
        **_kwargs: object,
    ) -> Path:
        output_dir = tmp_path / "capture_run"
        output_dir.mkdir()
        monkeypatch.setenv("SAGE_TS_SCENARIO_ORDER_INDEX", "0")
        scenario_transform(
            "toy_birth",
            Scenario(
                starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
            ),
            output_dir,
        )
        return output_dir

    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.run_scenario_sequence",
        capture_sequence,
    )
    base_config = {
        "agent": "gpt-4o-mini",
        "user": "gpt-4o-mini",
        "scenario_names": ("toy_birth",),
        "generation_model": "gpt-4o-mini-generation",
    }
    run_sage_with_registry(
        SageRunConfig(
            **base_config,
            output_dir=tmp_path / "capture_output",
            registry_dir=donor_store.root,
            actor_selection_mode="policy",
            inventory_authority_capture_dir=authority_root,
        )
    )

    run_started = False

    def must_not_run(*_args: object, **_kwargs: object) -> Path:
        nonlocal run_started
        run_started = True
        raise AssertionError("shared-context drift reached the scenario runner")

    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.run_scenario_sequence",
        must_not_run,
    )
    with pytest.raises(ValueError, match="generation_model"):
        run_sage_with_registry(
            SageRunConfig(
                **{**base_config, "generation_model": "different-generation-model"},
                output_dir=tmp_path / "model_drift_output",
                registry_dir=tmp_path / "model_drift_registry",
                actor_selection_mode="auto",
                inventory_authority_replay_dir=authority_root,
            )
        )
    assert run_started is False

    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter._tracked_source_state",
        lambda _root: {
            "tracked_changes_present": True,
            "tracked_diff_sha256": "c" * 64,
        },
    )
    with pytest.raises(ValueError, match="tracked_source_state"):
        run_sage_with_registry(
            SageRunConfig(
                **base_config,
                output_dir=tmp_path / "source_drift_output",
                registry_dir=tmp_path / "source_drift_registry",
                actor_selection_mode="auto",
                inventory_authority_replay_dir=authority_root,
            )
        )
    assert run_started is False


def test_inventory_authority_replay_preflight_rejects_corrupt_state_before_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    matched_authority_context: None,
) -> None:
    del matched_authority_context
    donor_store = _registry_with_canonicalizer(tmp_path / "donor_registry")
    authority_root = tmp_path / "inventory_authority"

    def capture_sequence(
        _config: ToolSandboxRunConfig,
        *,
        scenario_transform: ScenarioTransform,
        **_kwargs: object,
    ) -> Path:
        output_dir = tmp_path / "capture_run"
        output_dir.mkdir()
        monkeypatch.setenv("SAGE_TS_SCENARIO_ORDER_INDEX", "0")
        scenario_transform(
            "toy_birth",
            Scenario(
                starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
            ),
            output_dir,
        )
        return output_dir

    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.run_scenario_sequence",
        capture_sequence,
    )
    run_sage_with_registry(
        SageRunConfig(
            agent="gpt-4o-mini",
            user="gpt-4o-mini",
            scenario_names=("toy_birth",),
            output_dir=tmp_path / "capture_output",
            registry_dir=donor_store.root,
            inventory_authority_capture_dir=authority_root,
        )
    )
    authority_path = authority_root / "inventory_authority.json"
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    run_started = False

    def must_not_run(*_args: object, **_kwargs: object) -> Path:
        nonlocal run_started
        run_started = True
        raise AssertionError("corrupt replay reached the scenario runner")

    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.run_scenario_sequence",
        must_not_run,
    )
    authority["source_actor_selection_mode"] = "auto"
    authority_path.write_text(json.dumps(authority) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="policy-selection source arm"):
        run_sage_with_registry(
            SageRunConfig(
                agent="gpt-4o-mini",
                user="gpt-4o-mini",
                scenario_names=("toy_birth",),
                output_dir=tmp_path / "source_mode_replay_output",
                registry_dir=tmp_path / "source_mode_replay_registry",
                actor_selection_mode="auto",
                inventory_authority_replay_dir=authority_root,
            )
        )
    assert run_started is False

    authority["source_actor_selection_mode"] = "policy"
    authority["source_generation_enabled"] = "unknown"
    authority_path.write_text(json.dumps(authority) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source_generation_enabled"):
        run_sage_with_registry(
            SageRunConfig(
                agent="gpt-4o-mini",
                user="gpt-4o-mini",
                scenario_names=("toy_birth",),
                output_dir=tmp_path / "provenance_replay_output",
                registry_dir=tmp_path / "provenance_replay_registry",
                actor_selection_mode="auto",
                inventory_authority_replay_dir=authority_root,
            )
        )
    assert run_started is False

    authority["source_generation_enabled"] = False
    authority_path.write_text(json.dumps(authority) + "\n", encoding="utf-8")
    task_state = authority_root / authority["tasks"][0]["state_dir"]
    (task_state / "registry_manifest.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        run_sage_with_registry(
            SageRunConfig(
                agent="gpt-4o-mini",
                user="gpt-4o-mini",
                scenario_names=("toy_birth",),
                output_dir=tmp_path / "replay_output",
                registry_dir=tmp_path / "replay_registry",
                actor_selection_mode="auto",
                inventory_authority_replay_dir=authority_root,
            )
        )
    assert run_started is False


def test_inventory_authority_mismatch_uses_fail_closed_abort(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    matched_authority_context: None,
) -> None:
    del matched_authority_context
    donor_store = _registry_with_canonicalizer(tmp_path / "donor_registry")
    authority_root = tmp_path / "inventory_authority"

    def one_scenario_sequence(
        _config: ToolSandboxRunConfig,
        *,
        scenario_transform: ScenarioTransform,
        **_kwargs: object,
    ) -> Path:
        output_dir = tmp_path / "run"
        output_dir.mkdir(exist_ok=True)
        monkeypatch.setenv("SAGE_TS_SCENARIO_ORDER_INDEX", "0")
        scenario_transform(
            "toy_birth",
            Scenario(
                starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
            ),
            output_dir,
        )
        return output_dir

    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.run_scenario_sequence",
        one_scenario_sequence,
    )
    run_sage_with_registry(
        SageRunConfig(
            agent="gpt-4o-mini",
            user="gpt-4o-mini",
            scenario_names=("toy_birth",),
            output_dir=tmp_path / "capture_output",
            registry_dir=donor_store.root,
            inventory_authority_capture_dir=authority_root,
        )
    )

    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.route_registry_entries",
        lambda *_args, **_kwargs: ([], {}),
    )
    assert issubclass(InventoryAuthorityError, RuntimeError)
    assert InventoryAuthorityError.fail_closed_scenario_transform is True
    with pytest.raises(
        InventoryAuthorityError, match="diverged before actor inference"
    ):
        run_sage_with_registry(
            SageRunConfig(
                agent="gpt-4o-mini",
                user="gpt-4o-mini",
                scenario_names=("toy_birth",),
                output_dir=tmp_path / "replay_output",
                registry_dir=tmp_path / "replay_registry",
                actor_selection_mode="auto",
                inventory_authority_replay_dir=authority_root,
            )
        )


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
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}\n", encoding="utf-8")

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
            result_hook(
                "toy_birth",
                enhanced,
                {"similarity": 1, "outcome_similarity": 1},
                output_dir,
            )
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
            manifest_path=manifest_path,
            reflection_control_rows={
                "toy_birth": {
                    "name": "toy_birth",
                    "similarity": 1,
                    "outcome_similarity": 1,
                }
            },
            require_fresh_reflection_control=True,
        ),
        generator=UnpicklableGenerator(),  # type: ignore[arg-type]
    )


def test_spawn_queue_is_absent_from_generated_tool_callback_chain(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Candidate worker/config queues must not enter dill-copied tool closures."""

    store = _registry_with_canonicalizer(tmp_path / "registry")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}\n", encoding="utf-8")
    spawn_context = get_context("spawn")
    reflection_channel = spawn_context.Queue()
    worker_params = {
        "mode": "online_build_full",
        "run_root": str(tmp_path / "protocol_run"),
        "artifact_root": str(tmp_path / "artifacts"),
        "reflection_control_channel": reflection_channel,
    }
    event_hook = _candidate_protocol_event_hook(worker_params)

    class UnpicklableGenerator:
        def __init__(self) -> None:
            self.ssl_context = ssl.create_default_context()

    class StopAfterDeepcopy(Exception):
        pass

    def fake_sequence(
        config: ToolSandboxRunConfig,
        *,
        scenario_transform: ScenarioTransform,
        **_kwargs: object,
    ) -> Path:
        output_dir = tmp_path / "run"
        output_dir.mkdir()
        for scenario_name in config.scenario_names:
            enhanced = scenario_transform(
                scenario_name,
                Scenario(
                    starting_context=ExecutionContext(
                        tool_allow_list=["end_conversation"]
                    )
                ),
                output_dir,
            )
            wrapper = enhanced.starting_context.name_to_tool[
                "canonicalize_connectivity_label"
            ]
            reuse_callback = inspect.getclosurevars(wrapper).nonlocals["on_reuse"]
            reuse_freevars = inspect.getclosurevars(reuse_callback).nonlocals
            assert "config" not in reuse_freevars
            assert (
                "params"
                not in inspect.getclosurevars(reuse_freevars["event_hook"]).nonlocals
            )
            copy.deepcopy(enhanced.starting_context)
        raise StopAfterDeepcopy

    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.run_scenario_sequence",
        fake_sequence,
    )

    try:
        with pytest.raises(StopAfterDeepcopy):
            run_sage_with_registry(
                SageRunConfig(
                    agent="Unhelpful",
                    user="GPT_4_o_2024_05_13",
                    scenario_names=("scenario_one", "scenario_two"),
                    output_dir=tmp_path / "outputs",
                    registry_dir=store.root,
                    manifest_path=manifest_path,
                    reflection_control_channel=reflection_channel,
                    require_fresh_reflection_control=True,
                ),
                generator=UnpicklableGenerator(),  # type: ignore[arg-type]
                event_hook=event_hook,
            )
    finally:
        reflection_channel.cancel_join_thread()
        reflection_channel.close()


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


def test_sage_runner_propagates_fresh_control_channel_to_reflection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    class FakeBirthController:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def prime_before_scenario(
            self,
            _scenario_name: str,
            _scenario: Scenario,
        ) -> list[str]:
            return []

    class FakeReflectionController:
        @classmethod
        def from_env(cls, **kwargs: object) -> "FakeReflectionController":
            captured.update(kwargs)
            return cls()

        def assert_fresh_control_complete(
            self,
            scenario_names: tuple[str, ...],
        ) -> None:
            captured["asserted_scenario_names"] = scenario_names

    def fake_sequence(
        _config: ToolSandboxRunConfig,
        *,
        scenario_transform: ScenarioTransform,
        **_kwargs: object,
    ) -> Path:
        output_dir = tmp_path / "run"
        output_dir.mkdir()
        scenario_transform(
            "toy_birth",
            Scenario(starting_context=ExecutionContext()),
            output_dir,
        )
        return output_dir

    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.OnlineBirthController",
        FakeBirthController,
    )
    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.SelfEvolutionReflectionController",
        FakeReflectionController,
    )
    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.run_scenario_sequence",
        fake_sequence,
    )
    channel = object()

    run_sage_with_registry(
        SageRunConfig(
            agent="Unhelpful",
            user="GPT_4_o_2024_05_13",
            scenario_names=("toy_birth",),
            output_dir=tmp_path / "outputs",
            registry_dir=tmp_path / "registry",
            reflection_control_channel=channel,
            require_fresh_reflection_control=True,
        ),
        generator=object(),  # type: ignore[arg-type]
    )

    assert captured["fresh_control_rows"] is None
    assert captured["require_fresh_control"] is True
    assert captured["fresh_control_channel"] is channel
    assert captured["asserted_scenario_names"] == ("toy_birth",)
