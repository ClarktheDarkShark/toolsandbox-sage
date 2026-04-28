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


@dataclass
class _RecencyGenerator:
    calls: int = 0

    def generate(self, _request: ToolGenerationRequest) -> GeneratedTool:
        self.calls += 1
        spec = ToolSpec(
            tool_name="canonicalize_recency_label",
            family=ToolFamily("canonicalizer"),
            description="Normalize recency labels.",
            inputs=(ToolInput("label", "str", "Recency label."),),
            output_annotation="str",
            generalization_rationale="Recency labels recur across scenarios.",
            inadequacy_evidence="No existing tool normalizes recency words.",
        )
        code = (
            "def canonicalize_recency_label(label: str) -> str:\n"
            "    s = label.strip().lower()\n"
            "    if s in ('newest', 'latest', 'recent'): return 'latest'\n"
            "    if s in ('oldest', 'earliest'): return 'oldest'\n"
            "    if 'upcoming' in s: return 'upcoming'\n"
            "    if 'yesterday' in s: return 'yesterday'\n"
            "    return s\n"
        )
        return GeneratedTool(spec=spec, code=code)


def _make_entry(tmp_path: Path) -> tuple[RegistryStore, RegistryEntry]:
    generator = _RecencyGenerator()
    tool = generator.generate(None)  # type: ignore[arg-type]
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample({"label": "Newest"}, "latest"),
            ToolExample({"label": "oldest"}, "oldest"),
        ),
    )
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
    scenario = Scenario(categories=[ScenarioCategories.CANONICALIZATION])  # type: ignore[list-item]
    for i in range(2):
        obs = classify_scenario_observations(
            f"search_reminder_with_recency_latest_s{i}",
            scenario,
            {"similarity": 0},
        )
        assert len(obs) == 1
        controller.observe(obs[0])

    assert generator.calls == 1
    entry = store.get("canonicalize_recency_label")
    assert entry is not None, "tool should be in registry after birth"
    assert entry.validation.accepted

    # Compile and invoke the tool — reuse event must fire
    reuse_log: list[str] = []
    fn = _compile_toolsandbox_tool(entry, on_reuse=reuse_log.append)
    assert fn("Newest") == "latest"
    assert reuse_log == ["canonicalize_recency_label"]

    # Verify birth events jsonl
    birth_line = json.loads((tmp_path / "tool_birth_events.jsonl").read_text())
    assert birth_line["accepted"] is True
    assert birth_line["tool_name"] == "canonicalize_recency_label"


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
    ) -> Path:
        outdir = tmp_path / "run"
        outdir.mkdir(exist_ok=True)
        scenario = Scenario(
            starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
        )
        enhanced = scenario_transform("later_scenario", scenario, outdir)
        tools = enhanced.starting_context.get_available_tools(scrambling_allowed=False)
        assert "canonicalize_recency_label" in tools, "tool must be injected"
        result = tools["canonicalize_recency_label"]("Newest")
        assert result == "latest"
        invoked_tools.append("canonicalize_recency_label")
        if result_hook is not None:
            result_hook("later_scenario", enhanced, {"similarity": 1}, outdir)
        return outdir

    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.run_scenario_sequence",
        fake_sequence,
    )

    outdir = run_sage_with_registry(
        SageRunConfig(
            agent="Unhelpful",
            user="GPT_4_o_2024_05_13",
            scenario_names=("later_scenario",),
            output_dir=tmp_path / "outputs",
            registry_dir=store.root,
        )
    )

    assert invoked_tools == ["canonicalize_recency_label"]
    entry = store.get("canonicalize_recency_label")
    assert entry is not None
    assert entry.reuse_count == 1

    reuse_event = json.loads((outdir / "reuse_events.jsonl").read_text())
    assert reuse_event["tool_name"] == "canonicalize_recency_label"
    assert reuse_event["scenario"] == "later_scenario"
