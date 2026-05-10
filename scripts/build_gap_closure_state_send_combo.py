# mypy: ignore-errors
"""Build an experimental schedule-v2 + state-v3 + send-lookup combo registry.

Experimental only. This combines two narrow positive action/precondition repairs:
device-state setter success/adoption and named-recipient send lookup.
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
STATE_SOURCE = (
    REGISTRY_ROOT
    / "full_timestamp_schedule_v2_plus_state_v3_pack"
    / "registry_manifest.json"
)
SEND_SOURCE = REGISTRY_ROOT / "send_message_lookup_only_pack" / "registry_manifest.json"
OUT = (
    REGISTRY_ROOT
    / "full_timestamp_schedule_v2_plus_state_v3_send_lookup_pack"
    / "registry_manifest.json"
)
SUMMARY_OUT = MANIFEST_ROOT / "state_v3_send_lookup_combo_summary.json"


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
    state_tools = _load_tools(STATE_SOURCE)
    send_tools = _load_tools(SEND_SOURCE)
    merged = dict(state_tools)
    for name, entry in send_tools.items():
        if name in merged:
            raise RuntimeError(f"duplicate tool: {name}")
        merged[name] = entry

    registry_hash = _write_json(OUT, {"tools": merged})
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "protected_assets_modified": False,
        "sources": {
            "state_source": str(STATE_SOURCE),
            "send_source": str(SEND_SOURCE),
        },
        "output_registry": str(OUT),
        "registry_sha256": registry_hash,
        "tool_count": len(merged),
        "tools": sorted(merged),
        "purpose": (
            "Combine the repaired device-state action lane with the retained "
            "send-message lookup/precondition helper for narrow settings/send "
            "diagnostics before any broad use."
        ),
    }
    _write_json(SUMMARY_OUT, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
