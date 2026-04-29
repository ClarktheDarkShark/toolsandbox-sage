"""ToolSandbox runner with accepted SAGE registry tools injected."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sage_ts.adapters.toolsandbox_adapter import (
    EventHook,
    ProgressHook,
    ToolSandboxRunConfig,
    run_scenario_sequence,
)
from sage_ts.adequacy.inadequacy_classifier import classify_scenario_observations
from sage_ts.orchestration.checkpoints import append_jsonl
from sage_ts.orchestration.online_birth import (
    GeneratedToolFactory,
    OnlineBirthController,
)
from sage_ts.registry.store import RegistryStore
from sage_ts.runtime.base_toolset import UPSTREAM_POLICY
from sage_ts.runtime.toolsandbox_integration import (
    registry_entry_matches_scenario,
    with_registry_tools,
)
from tool_sandbox.common.scenario import Scenario


def _reuse_log_tools(output_directory: Path, scenario_name: str) -> list[str]:
    path = output_directory / "reuse_events.jsonl"
    if not path.exists():
        return []
    tools: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("scenario") != scenario_name:
            continue
        tool_name = event.get("tool_name")
        if isinstance(tool_name, str) and tool_name not in tools:
            tools.append(tool_name)
    return tools


@dataclass(frozen=True)
class SageRunConfig:
    agent: str
    user: str
    scenario_names: tuple[str, ...]
    output_dir: Path
    registry_dir: Path
    run_type: str = "sage_online"
    recurrence_threshold: int = 2
    base_tool_policy: str = UPSTREAM_POLICY


def run_sage_with_registry(
    config: SageRunConfig,
    *,
    generator: GeneratedToolFactory | None = None,
    progress_hook: ProgressHook | None = None,
    event_hook: EventHook | None = None,
) -> Path:
    """Run ToolSandbox scenarios with accepted generated tools available."""
    store = RegistryStore(config.registry_dir)
    registry_tools = sorted(store.load_entries())
    visible_generated_by_scenario: dict[str, list[str]] = {}
    called_generated_by_scenario: dict[str, list[str]] = {}
    selection_context_by_scenario: dict[str, dict[str, object]] = {}

    birth_controller: OnlineBirthController | None = None
    registry_load_logged = False

    def transform(name: str, scenario: Scenario, output_directory: Path) -> Scenario:
        nonlocal birth_controller, registry_load_logged
        if generator is not None and birth_controller is None:

            def birth_event_hook(event: str, payload: dict[str, object]) -> None:
                if event_hook is not None:
                    event_hook(event, output_directory, payload)

            birth_controller = OnlineBirthController(
                store=store,
                generator=generator,
                output_dir=output_directory,
                recurrence_threshold=config.recurrence_threshold,
                event_hook=birth_event_hook,
            )
        if not registry_load_logged:
            append_jsonl(
                output_directory / "sage_run_events.jsonl",
                {
                    "event": "registry_load",
                    "registry_dir": str(config.registry_dir),
                    "registry_tools": registry_tools,
                    "registry_size": len(registry_tools),
                    "base_tool_policy": config.base_tool_policy,
                    "generation_enabled": generator is not None,
                },
            )
            if event_hook is not None:
                event_hook(
                    "registry_loaded",
                    output_directory,
                    {
                        "registry_dir": str(config.registry_dir),
                        "registry_tools": registry_tools,
                        "registry_size": len(registry_tools),
                        "base_tool_policy": config.base_tool_policy,
                        "generation_enabled": generator is not None,
                    },
                )
            registry_load_logged = True

        def record_reuse(tool_name: str) -> None:
            store.record_reuse(tool_name)
            called = called_generated_by_scenario.setdefault(name, [])
            if tool_name not in called:
                called.append(tool_name)
            append_jsonl(
                output_directory / "reuse_events.jsonl",
                {
                    "scenario": name,
                    "tool_name": tool_name,
                    "event": "generated_tool_invoked",
                },
            )
            if event_hook is not None:
                event_hook(
                    "tool_reused",
                    output_directory,
                    {
                        "scenario": name,
                        "tool_name": tool_name,
                        "registry_dir": str(config.registry_dir),
                    },
                )

        loaded_entries = store.load_entries()
        retained_tools_loaded = sorted(loaded_entries)
        shortlisted_generated_tools = [
            tool_name
            for tool_name, entry in sorted(loaded_entries.items())
            if registry_entry_matches_scenario(entry, name)
        ]
        filtered_out_generated_tools = [
            tool_name
            for tool_name in retained_tools_loaded
            if tool_name not in set(shortlisted_generated_tools)
        ]
        filtered_out_reasons = {
            tool_name: "scenario_relevance_filter"
            for tool_name in filtered_out_generated_tools
        }
        original_tool_order = list(scenario.starting_context.name_to_tool)
        enhanced = with_registry_tools(
            scenario,
            store,
            on_reuse=record_reuse,
            scenario_name=name,
        )
        enhanced_tool_order = list(enhanced.starting_context.name_to_tool)
        available_tools = set(
            enhanced.starting_context.get_available_tools(scrambling_allowed=False)
        )
        generated_tools = [
            tool_name
            for tool_name in sorted(store.load_entries())
            if tool_name in available_tools
        ]
        visible_generated_by_scenario[name] = generated_tools
        priority_injection_changed_tool_order = bool(
            generated_tools
            and enhanced_tool_order[: len(generated_tools)] == generated_tools
            and enhanced_tool_order != original_tool_order
        )
        selection_context_by_scenario[name] = {
            "retained_tools_loaded": retained_tools_loaded,
            "filtered_out_generated_tools": filtered_out_generated_tools,
            "filtered_out_reasons": filtered_out_reasons,
            "shortlisted_generated_tools": shortlisted_generated_tools,
            "priority_injection_changed_tool_order": (
                priority_injection_changed_tool_order
            ),
            "relevance_gating_hid_retained_tool": bool(filtered_out_generated_tools),
        }
        append_jsonl(
            output_directory / "scenario_tool_visibility.jsonl",
            {
                "scenario": name,
                "base_tool_policy": config.base_tool_policy,
                "retained_tools_loaded": retained_tools_loaded,
                "filtered_out_generated_tools": filtered_out_generated_tools,
                "filtered_out_reasons": filtered_out_reasons,
                "shortlisted_generated_tools": shortlisted_generated_tools,
                "priority_injection_changed_tool_order": (
                    priority_injection_changed_tool_order
                ),
                "relevance_gating_hid_retained_tool": bool(
                    filtered_out_generated_tools
                ),
                "tool_allow_list": list(
                    enhanced.starting_context.tool_allow_list or []
                ),
                "available_tools": sorted(
                    enhanced.starting_context.get_available_tools(
                        scrambling_allowed=False
                    )
                ),
                "generated_tools": generated_tools,
            },
        )
        return enhanced

    def after_result(
        name: str,
        scenario: Scenario,
        result: dict[str, object],
        output_directory: Path,
    ) -> dict[str, object]:
        generated_visible = visible_generated_by_scenario.get(name, [])
        generated_called = list(called_generated_by_scenario.get(name, []))
        for tool_name in _reuse_log_tools(output_directory, name):
            if tool_name not in generated_called:
                generated_called.append(tool_name)
        generated_not_called = [
            tool for tool in generated_visible if tool not in set(generated_called)
        ]
        raw_similarity = result.get("similarity", 0.0)
        try:
            similarity = (
                float(raw_similarity)
                if isinstance(raw_similarity, (int, float, str))
                else 0.0
            )
        except ValueError:
            similarity = 0.0
        selection_status = (
            "generated_tool_called"
            if generated_called
            else "generated_tool_visible_not_called"
            if generated_visible
            else "no_visible_generated_tools"
        )
        if generated_called:
            selection_reason = "retained_tool_invoked"
        elif generated_visible:
            selection_reason = "retained_tool_visible_but_model_did_not_call_it"
        else:
            selection_reason = "no_retained_tool_visible_after_relevance_filter"
        context = selection_context_by_scenario.get(name, {})
        selection_record = {
            "scenario": name,
            "base_tool_policy": config.base_tool_policy,
            "retained_tools_loaded": context.get("retained_tools_loaded", []),
            "filtered_out_generated_tools": context.get(
                "filtered_out_generated_tools", []
            ),
            "filtered_out_reasons": context.get("filtered_out_reasons", {}),
            "shortlisted_generated_tools": context.get(
                "shortlisted_generated_tools", generated_visible
            ),
            "chosen_retained_tool": generated_called[0] if generated_called else None,
            "priority_injection_changed_tool_order": context.get(
                "priority_injection_changed_tool_order", False
            ),
            "relevance_gating_hid_retained_tool": context.get(
                "relevance_gating_hid_retained_tool", False
            ),
            "generated_tools_visible": generated_visible,
            "generated_tools_called": generated_called,
            "generated_tools_not_called": generated_not_called,
            "visible_generated_tool_count": len(generated_visible),
            "called_generated_tool_count": len(generated_called),
            "selection_status": selection_status,
            "selection_reason": selection_reason,
            "not_called_reason": None
            if generated_called or not generated_visible
            else "model_did_not_call_retained_tool",
            "similarity": similarity,
            "exception_type": result.get("exception_type"),
            "failure_after_selection": similarity < 1.0
            or bool(result.get("exception_type")),
        }
        append_jsonl(
            output_directory / "scenario_tool_selection.jsonl",
            selection_record,
        )
        append_jsonl(output_directory / "selection_trace.jsonl", selection_record)
        if birth_controller is None:
            return result
        observations = classify_scenario_observations(name, scenario, result)
        for observation in observations:
            if event_hook is not None:
                event_hook(
                    "inadequacy_detected",
                    output_directory,
                    observation.to_json(),
                )
            birth_controller.observe(observation)
        result["sage_observations"] = [item.to_json() for item in observations]
        return result

    output_directory = run_scenario_sequence(
        ToolSandboxRunConfig(
            agent=config.agent,
            user=config.user,
            scenario_names=config.scenario_names,
            output_dir=config.output_dir,
            processes=1,
            run_type=config.run_type,
            base_tool_policy=config.base_tool_policy,
        ),
        scenario_transform=transform,
        result_hook=after_result,
        progress_hook=progress_hook,
        event_hook=event_hook,
    )
    final_registry_tools = sorted(store.load_entries())
    append_jsonl(
        output_directory / "sage_run_events.jsonl",
        {
            "event": "run_finished",
            "registry_dir": str(config.registry_dir),
            "registry_tools": registry_tools,
            "final_registry_tools": final_registry_tools,
            "final_registry_size": len(final_registry_tools),
        },
    )
    selection_summary = {
        "scenario_count": len(config.scenario_names),
        "registry_dir": str(config.registry_dir),
        "registry_tools": registry_tools,
        "final_registry_tools": final_registry_tools,
        "generated_tool_visible_scenarios": sum(
            1 for tools in visible_generated_by_scenario.values() if tools
        ),
        "generated_tool_called_scenarios": sum(
            1 for tools in called_generated_by_scenario.values() if tools
        ),
        "relevance_gate_hidden_scenarios": sum(
            1
            for context in selection_context_by_scenario.values()
            if context.get("relevance_gating_hid_retained_tool")
        ),
    }
    (output_directory / "selection_summary.json").write_text(
        json.dumps(selection_summary, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_directory
