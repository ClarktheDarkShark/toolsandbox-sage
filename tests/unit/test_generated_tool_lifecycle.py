from pathlib import Path

from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily, ToolInput, ToolSpec
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.registry.store import RegistryStore
from sage_ts.runtime.tool_invoker import invoke_registered_tool
from sage_ts.validation.sandbox_validator import ToolExample, validate_generated_tool


def _wifi_canonicalizer() -> GeneratedTool:
    spec = ToolSpec(
        tool_name="canonicalize_connectivity_label",
        family=ToolFamily.CANONICALIZER,
        description="Normalize connectivity labels to stable internal labels.",
        inputs=(ToolInput("label", "str", "Raw user-facing connectivity label."),),
        output_annotation="str",
        generalization_rationale=(
            "Connectivity labels recur across scenarios with spacing and punctuation "
            "differences, so a deterministic normalizer can transfer."
        ),
        inadequacy_evidence=(
            "The base tool list exposes state setters and getters, but not a reusable "
            "canonicalization helper for noisy connectivity labels."
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


def test_generated_tool_birth_reuse_and_success_flip(tmp_path: Path) -> None:
    tool = _wifi_canonicalizer()
    validation = validate_generated_tool(
        tool,
        examples=(
            ToolExample({"label": "Wi-Fi"}, "wifi"),
            ToolExample({"label": "mobile data"}, "cellular"),
        ),
    )
    assert validation.accepted

    store = RegistryStore(tmp_path)
    store.put(RegistryEntry.accepted(tool, validation, birth_scenario="toy_birth"))

    raw_label: str = "Wi Fi"
    expected_label: str = "wifi"
    baseline_later_success = raw_label == expected_label
    normalized = invoke_registered_tool(
        store,
        "canonicalize_connectivity_label",
        {"label": raw_label},
        success_flip=not baseline_later_success,
    )

    assert normalized == expected_label
    entry = store.get("canonicalize_connectivity_label")
    assert entry is not None
    assert entry.reuse_count == 1
    assert entry.success_flips == 1
