import json
from pathlib import Path
from typing import Optional

import pytest
from sage_ts.adapters.sage_run_adapter import SageRunConfig, run_sage_with_registry
from sage_ts.adapters.toolsandbox_adapter import (
    ResultHook,
    ScenarioTransform,
    ToolSandboxRunConfig,
)
from sage_ts.orchestration.toy_mechanism import canonicalizer_tool
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.registry.store import RegistryStore
from sage_ts.validation.sandbox_validator import ToolExample, validate_generated_tool

from tool_sandbox.common.execution_context import ExecutionContext
from tool_sandbox.common.scenario import Scenario


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


def test_sage_runner_records_registry_reuse(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = _registry_with_canonicalizer(tmp_path / "registry")

    def fake_sequence(
        config: ToolSandboxRunConfig,
        *,
        scenario_transform: ScenarioTransform,
        result_hook: Optional[ResultHook] = None,
    ) -> Path:
        output_dir = tmp_path / "run"
        output_dir.mkdir()
        scenario = Scenario(
            starting_context=ExecutionContext(tool_allow_list=["end_conversation"])
        )
        enhanced = scenario_transform("later_scenario", scenario, output_dir)
        tool = enhanced.starting_context.get_available_tools(scrambling_allowed=False)[
            "canonicalize_connectivity_label"
        ]
        assert tool("Wi-Fi") == "wifi"
        if result_hook is not None:
            result_hook("later_scenario", enhanced, {"similarity": 1}, output_dir)
        return output_dir

    monkeypatch.setattr(
        "sage_ts.adapters.sage_run_adapter.run_scenario_sequence",
        fake_sequence,
    )

    output_dir = run_sage_with_registry(
        SageRunConfig(
            agent="Unhelpful",
            user="GPT_4_o_2024_05_13",
            scenario_names=("later_scenario",),
            output_dir=tmp_path / "outputs",
            registry_dir=store.root,
        )
    )

    entry = store.get("canonicalize_connectivity_label")
    assert entry is not None
    assert entry.reuse_count == 1

    reuse_event = json.loads((output_dir / "reuse_events.jsonl").read_text())
    assert reuse_event["scenario"] == "later_scenario"
    assert reuse_event["tool_name"] == "canonicalize_connectivity_label"

    run_event = json.loads((output_dir / "sage_run_events.jsonl").read_text())
    assert run_event["registry_tools"] == ["canonicalize_connectivity_label"]
