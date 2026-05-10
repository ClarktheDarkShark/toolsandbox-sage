# mypy: ignore-errors
"""Build schedule-v2 plus action/CRUD combo variants for gap-closure testing.

Experimental only. These registries keep the current positive schedule/recency
portfolio unchanged, then add narrowly-scoped action helpers one slice at a time
so broad adoption can be tested without mixing every parked helper back in.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

REGISTRY_ROOT = Path(
    "artifacts/registry_experiments/gap_closure_lab/action_precondition_loop"
)
SUMMARY_OUT = (
    Path("artifacts/experiment_manifests/gap_closure_lab/action_precondition_loop")
    / "schedule_state_crud_combo_variants_summary.json"
)

BASE = (
    REGISTRY_ROOT
    / "full_timestamp_no_field_plus_schedule_v2_pack"
    / "registry_manifest.json"
)
STATE = REGISTRY_ROOT / "state_action_sequence_pack" / "registry_manifest.json"
CRUD = REGISTRY_ROOT / "top_tools_plus_crud_bridge_pack" / "registry_manifest.json"

STATE_TOOLS = ("plan_device_state_action_sequence",)
CRUD_TOOLS = ("plan_contact_crud_action", "prepare_reminder_crud_action")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    digest = _sha256(text.encode("utf-8"))
    path.with_suffix(path.suffix + ".sha256").write_text(
        f"{digest}  {path.name}\n", encoding="utf-8"
    )
    return digest


def _load_tools(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8"))["tools"])


def _mark(entry: dict[str, Any], note: str) -> dict[str, Any]:
    updated = copy.deepcopy(entry)
    spec = updated["tool"]["spec"]
    existing = str(spec.get("adoption_experiment_note", "")).strip()
    spec["adoption_experiment_note"] = f"{existing}; {note}" if existing else note
    return updated


def _variant(
    base_tools: dict[str, Any],
    extras: dict[str, Any],
    extra_names: tuple[str, ...],
    note: str,
) -> dict[str, Any]:
    tools = {name: _mark(entry, note) for name, entry in base_tools.items()}
    missing = [name for name in extra_names if name not in extras]
    if missing:
        raise KeyError(f"extra registry missing tools: {missing}")
    for name in extra_names:
        tools[name] = _mark(extras[name], note)
    return tools


def main() -> None:
    base_tools = _load_tools(BASE)
    state_tools = _load_tools(STATE)
    crud_tools = _load_tools(CRUD)
    extra_source = {**state_tools, **crud_tools}

    variants = {
        "full_timestamp_schedule_v2_plus_state_pack": _variant(
            base_tools,
            state_tools,
            STATE_TOOLS,
            "schedule_v2_plus_state: add only the trigger-gated pure device-state action sequence helper",
        ),
        "full_timestamp_schedule_v2_plus_crud_pack": _variant(
            base_tools,
            crud_tools,
            CRUD_TOOLS,
            "schedule_v2_plus_crud: add only trigger-gated contact/reminder CRUD bridge helpers",
        ),
        "full_timestamp_schedule_v2_plus_state_crud_pack": _variant(
            base_tools,
            extra_source,
            STATE_TOOLS + CRUD_TOOLS,
            "schedule_v2_plus_state_crud: combine trigger-gated state and CRUD bridges with retained schedule-v2 portfolio",
        ),
    }

    summary: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "protected_claim_evidence": False,
        "base_registry": str(BASE),
        "base_registry_sha256": _sha256(BASE.read_bytes()),
        "objective": (
            "Recombine retained positive schedule/recency tools with narrow "
            "state and CRUD bridges after broad100 showed remaining losses in "
            "settings/device-state and contact/reminder action buckets."
        ),
        "policy_change": (
            "State, CRUD, and domain-abstention actor nudges are trigger-gated "
            "in openai_toolsandbox_roles.py for these experiments to reduce "
            "broad context pollution."
        ),
        "leakage_controls": {
            "truth_labels_inspected": False,
            "used_cache_availability_for_selection": False,
            "scenario_ids_encoded_into_tools_or_router": False,
            "candidate_arms_fresh_only": True,
            "baseline_cache_policy": "use-if-eligible",
        },
        "variants": {},
    }
    for label, tools in variants.items():
        path = REGISTRY_ROOT / label / "registry_manifest.json"
        digest = _write_json(path, {"tools": tools})
        summary["variants"][label] = {
            "path": str(path),
            "sha256": digest,
            "tools": sorted(tools),
        }

    _write_json(SUMMARY_OUT, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
