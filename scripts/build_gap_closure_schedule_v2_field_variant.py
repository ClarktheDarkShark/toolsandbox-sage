# mypy: ignore-errors
"""Build schedule-v2 plus contact field extractor recombination variant.

Experimental only. The schedule-v2 broad500 portfolio improved the prior
top-tool combo but remained slightly below the documented best3 500 lift. This
variant adds back the retained best3/V2.6 contact field extractor as a narrow
combination test while leaving protected registries untouched.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

ROOT = Path("artifacts/registry_experiments/gap_closure_lab")
ACTION_ROOT = ROOT / "action_precondition_loop"
MANIFEST_ROOT = Path(
    "artifacts/experiment_manifests/gap_closure_lab/action_precondition_loop"
)
SCHEDULE_V2 = (
    ACTION_ROOT
    / "full_timestamp_no_field_plus_schedule_v2_pack"
    / "registry_manifest.json"
)
FIELD_SOURCE = (
    ROOT
    / "recombination_adoption"
    / "top_tools_full_best3_highfit_pack"
    / "registry_manifest.json"
)
OUT = (
    ACTION_ROOT
    / "full_timestamp_schedule_v2_plus_field_pack"
    / "registry_manifest.json"
)
SUMMARY = MANIFEST_ROOT / "schedule_v2_field_variant_summary.json"


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


def main() -> None:
    schedule_tools = copy.deepcopy(_load_tools(SCHEDULE_V2))
    source_tools = _load_tools(FIELD_SOURCE)
    field_name = "extract_contact_field_from_search_result"
    if field_name not in source_tools:
        raise RuntimeError(f"{field_name} missing from {FIELD_SOURCE}")
    schedule_tools[field_name] = copy.deepcopy(source_tools[field_name])
    out_hash = _write_json(OUT, {"tools": schedule_tools})
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "protected_claim_evidence": False,
        "source_registry": str(SCHEDULE_V2),
        "field_source_registry": str(FIELD_SOURCE),
        "output_registry": str(OUT),
        "sha256": out_hash,
        "tools": sorted(schedule_tools),
        "repair_hypothesis": (
            "Schedule-v2 broad500 retained strong recency/scheduling lift but left "
            "contact scalar/field lookup under-adopted. Adding the existing field "
            "extractor may recover low-frequency contact wins without changing the "
            "schedule helpers."
        ),
        "leakage_controls": {
            "truth_labels_inspected": False,
            "used_cache_availability_for_selection": False,
            "scenario_ids_encoded_into_tools_or_router": False,
            "protected_claim_evidence": False,
        },
    }
    summary_hash = _write_json(SUMMARY, summary)
    summary["summary_sha256"] = summary_hash
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
