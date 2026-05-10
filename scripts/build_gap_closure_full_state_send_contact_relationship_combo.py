# mypy: ignore-errors
"""Build the broad retained action pack plus contact relationship repair.

Experimental only. This keeps the current broad timestamp/state/send/contact
portfolio and adds the narrow relationship-batch contact helper that showed
positive called-subset value on Contact CRUD diagnostics.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

REGISTRY_ROOT = Path(
    "artifacts/registry_experiments/gap_closure_lab/action_precondition_loop"
)
MANIFEST_ROOT = Path(
    "artifacts/experiment_manifests/gap_closure_lab/action_precondition_loop"
)
BROAD_SOURCE = (
    REGISTRY_ROOT
    / "full_timestamp_schedule_v2_plus_state_v3_send_lookup_pack"
    / "registry_manifest.json"
)
CONTACT_SOURCE = (
    REGISTRY_ROOT
    / "contact_selector_relationship_update_pack"
    / "registry_manifest.json"
)
OUT = (
    REGISTRY_ROOT
    / "full_state_send_contact_relationship_pack"
    / "registry_manifest.json"
)
SUMMARY_OUT = MANIFEST_ROOT / "full_state_send_contact_relationship_combo_summary.json"


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
    broad_tools = _load_tools(BROAD_SOURCE)
    contact_tools = _load_tools(CONTACT_SOURCE)
    merged = dict(broad_tools)
    for name, entry in contact_tools.items():
        if name in merged:
            continue
        merged[name] = entry

    registry_hash = _write_json(OUT, {"tools": merged})
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "protected_assets_modified": False,
        "sources": {
            "broad_source": str(BROAD_SOURCE),
            "contact_source": str(CONTACT_SOURCE),
        },
        "output_registry": str(OUT),
        "registry_sha256": registry_hash,
        "tool_count": len(merged),
        "tools": sorted(merged),
        "purpose": (
            "Test whether the broad positive search/timestamp/state/send pack plus "
            "the narrow contact relationship repair can improve Contact CRUD and "
            "later broad validation without adding the older negative CRUD bridge."
        ),
        "leakage_control": (
            "This is a registry recombination only. It encodes no scenario ids, "
            "truth labels, expected answers, or hidden benchmark facts."
        ),
    }
    _write_json(SUMMARY_OUT, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
