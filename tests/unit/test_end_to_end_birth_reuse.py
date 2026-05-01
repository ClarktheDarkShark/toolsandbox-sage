"""End-to-end test: birth → registry → injection → invocation → reuse_event."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest

from sage_ts.adapters.sage_run_adapter import SageRunConfig, run_sage_with_registry
from sage_ts.adapters.toolsandbox_adapter import (
    ResultHook,
    ScenarioTransform,
    ToolSandboxRunConfig,
)
from sage_ts.adequacy.inadequacy_classifier import classify_scenario_observations
from sage_ts.generation.tool_generator import ToolGenerationRequest
from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily, ToolInput, ToolSpec
from sage_ts.orchestration.online_birth import OnlineBirthController
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.registry.store import RegistryStore
from sage_ts.runtime.toolsandbox_integration import _compile_toolsandbox_tool
from sage_ts.validation.sandbox_validator import ToolExample, validate_generated_tool
from tool_sandbox.common.execution_context import ExecutionContext, ScenarioCategories
from tool_sandbox.common.scenario import Scenario

_TOOL_NAME = "recency_to_timestamp_bounds"
_TOOL_CODE = (
    "def recency_to_timestamp_bounds(recency_label: str, current_timestamp: float) -> dict:\n"
    "    SECONDS_PER_DAY = 86400\n"
    "    label = recency_label.strip().lower()\n"
    "    day_start = float(int(current_timestamp) // SECONDS_PER_DAY * SECONDS_PER_DAY)\n"
    "    if label == 'yesterday':\n"
    "        return {'lower_bound': day_start - SECONDS_PER_DAY, 'upper_bound': day_start}\n"
    "    if label in ('today', 'earlier today'):\n"
    "        return {'lower_bound': day_start, 'upper_bound': current_timestamp}\n"
    "    if 'upcoming' in label or label == 'future':\n"
    "        return {'lower_bound': current_timestamp, 'upper_bound': current_timestamp + 365 * SECONDS_PER_DAY}\n"
    "    return {'lower_bound': 0.0, 'upper_bound': current_timestamp}\n"
)
_VALIDATION_EXAMPLES = (
    ToolExample(
        {"recency_label": "yesterday", "current_timestamp": float(10 * 86400)},
        {"lower_bound": float(9 * 86400), "upper_bound": float(10 * 86400)},
    ),
    ToolExample(
        {"recency_label": "today", "current_timestamp": float(10 * 86400 + 3600)},
        {"lower_bound": float(10 * 86400), "upper_bound": float(10 * 86400 + 3600)},
    ),
)


@dataclass
class _RecencyGenerator:
    calls: int = 0

    def generate(self, _request: ToolGenerationRequest) -> GeneratedTool:
        self.calls += 1
        spec = ToolSpec(
            tool_name=_TOOL_NAME,
            family=ToolFamily("derived_value_calculator"),
            description="Convert a recency label to Unix timestamp lower/upper bounds.",
            inputs=(
                ToolInput("recency_label", "str", "Recency word, e.g. yesterday."),
                ToolInput("current_timestamp", "float", "Current Unix timestamp."),
            ),
            output_annotation="dict",
            generalization_rationale="Recency-to-bounds needed across reminder/message search.",
            inadequacy_evidence="Base toolset lacks a single recency→bounds helper.",
        )
        return GeneratedTool(spec=spec, code=_TOOL_CODE)


def _make_entry(tmp_path: Path) -> tuple[RegistryStore, RegistryEntry]:
    generator = _RecencyGenerator()
    tool = generator.generate(None)  # type: ignore[arg-type]
    validation = validate_generated_tool(tool, examples=_VALIDATION_EXAMPLES)
    assert validation.accepted
    store = RegistryStore(tmp_path / "registry")
    entry = RegistryEntry.accepted(tool, validation, birth_scenario="scenario_birth")
    store.put(entry)
    return store, entry


def test_birth_then_reuse_in_later_scenario(tmp_path: Path) -> None:
    """Birth a tool via recurrence, then verify it is callable and reuse fires."""
    store = RegistryStore(tmp_path / "registry")
    generator = _RecencyGenerator()
    controller = OnlineBirthController(
        store=store,
        generator=generator,
        output_dir=tmp_path,
        recurrence_threshold=2,
    )

    # Two observations → tool born
    scenario = Scenario(
        categories=[ScenarioCategories(str(ScenarioCategories.CANONICALIZATION))]
    )
    for i in range(2):
        obs = classify_scenario_observations(
            f"search_reminder_with_recency_latest_s{i}",
            scenario,
            {"similarity": 0},
        )
        assert len(obs) == 1
        controller.observe(obs[0])

    assert generator.calls == 1
    entry = store.get(_TOOL_NAME)
    assert entry is not None, "tool should be in registry after birth"
    assert entry.validation.accepted

    # Compile and invoke the tool — reuse event must fire
    reuse_log: list[str] = []
    fn = _compile_toolsandbox_tool(entry, on_reuse=reuse_log.append)
    result = fn("yesterday", float(10 * 86400))
    assert result == {"lower_bound": float(9 * 86400), "upper_bound": float(10 * 86400)}
    assert reuse_log == [_TOOL_NAME]

    # Verify birth events jsonl
    birth_line = json.loads((tmp_path / "tool_birth_events.jsonl").read_text())
    assert birth_line["accepted"] is True
    assert birth_line["tool_name"] == _TOOL_NAME


def test_sage_run_adapter_full_loop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Run the full SageRunConfig loop: simulate agent calling injected tool."""
    store, _ = _make_entry(tmp_path)
    invoked_tools: list[str] = []

    def fake_sequence(
        _config: ToolSandboxRunConfig,
        *,
        scenario_transform: ScenarioTransform,
        result_hook: Optional[ResultHook] = None,
        **_kwargs: object,
    ) -> Path:
        outdir = tmp_path / "run"
        outdir.mkdir(exist_ok=True)
        scenario = Scenario(
            starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
        )
        scenario_name = "search_reminder_with_creation_recency_yesterday"
        enhanced = scenario_transform(scenario_name, scenario, outdir)
        tools = enhanced.starting_context.get_available_tools(scrambling_allowed=False)
        assert _TOOL_NAME in tools, "tool must be injected"
        result = tools[_TOOL_NAME]("yesterday", float(10 * 86400))
        assert result == {
            "lower_bound": float(9 * 86400),
            "upper_bound": float(10 * 86400),
        }
        invoked_tools.append(_TOOL_NAME)
        if result_hook is not None:
            result_hook(scenario_name, enhanced, {"similarity": 1}, outdir)
        return outdir

    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.run_scenario_sequence",
        fake_sequence,
    )

    outdir = run_sage_with_registry(
        SageRunConfig(
            agent="Unhelpful",
            user="GPT_4_o_2024_05_13",
            scenario_names=("search_reminder_with_creation_recency_yesterday",),
            output_dir=tmp_path / "outputs",
            registry_dir=store.root,
        )
    )

    assert invoked_tools == [_TOOL_NAME]
    entry = store.get(_TOOL_NAME)
    assert entry is not None
    assert entry.reuse_count == 0

    reuse_event = json.loads((outdir / "reuse_events.jsonl").read_text())
    assert reuse_event["tool_name"] == _TOOL_NAME
    assert reuse_event["scenario"] == "search_reminder_with_creation_recency_yesterday"
