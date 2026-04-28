"""Controlled mechanism smoke for SAGE generated-tool lifecycle."""

from __future__ import annotations

from pathlib import Path

from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily, ToolInput, ToolSpec
from sage_ts.orchestration.checkpoints import append_jsonl, write_json
from sage_ts.orchestration.state import ReuseEvent, ToolBirthEvent
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.registry.store import RegistryStore
from sage_ts.runtime.tool_invoker import invoke_registered_tool
from sage_ts.validation.sandbox_validator import ToolExample, validate_generated_tool


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
            "ToolSandbox contains connectivity state tools, but no reusable helper for "
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


def run_toy_birth_reuse(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    store = RegistryStore(output_dir / "registry")
    tool = canonicalizer_tool()
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample({"label": "Wi-Fi"}, "wifi"),
            ToolExample({"label": "mobile data"}, "cellular"),
        ),
    )
    birth = ToolBirthEvent(
        scenario="toy_birth_connectivity_label",
        tool_name=tool.spec.tool_name,
        family=tool.spec.family.value,
        accepted=validation.accepted,
        errors=validation.errors,
    )
    append_jsonl(output_dir / "tool_birth_events.jsonl", birth.to_json())
    if not validation.accepted:
        return {"accepted": False, "errors": validation.errors}

    store.put(RegistryEntry.accepted(tool, validation, birth_scenario=birth.scenario))
    raw_label: str = "Wi Fi"
    expected_label: str = "wifi"
    baseline_success = raw_label == expected_label
    normalized = invoke_registered_tool(
        store,
        tool.spec.tool_name,
        {"label": raw_label},
        success_flip=not baseline_success,
    )
    sage_success = normalized == expected_label
    reuse = ReuseEvent(
        scenario="toy_reuse_connectivity_label",
        tool_name=tool.spec.tool_name,
        improved=sage_success and not baseline_success,
        baseline_success=baseline_success,
        sage_success=sage_success,
    )
    append_jsonl(output_dir / "reuse_events.jsonl", reuse.to_json())
    append_jsonl(
        output_dir / "scenario_outcomes.jsonl",
        {
            "scenario": reuse.scenario,
            "baseline_success": baseline_success,
            "sage_success": sage_success,
            "generated_tool_used": True,
        },
    )
    write_json(
        output_dir / "run_manifest.json",
        {
            "run_type": "toy_mechanism",
            "accepted_tools": 1,
            "reuse_events": 1,
            "success_flips": 1 if reuse.improved else 0,
        },
    )
    return {"accepted": True, "reused": True, "improved": reuse.improved}
