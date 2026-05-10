"""Build a narrow contact selector-only pack for gap-closure experiments.

Experimental only. Contact CRUD broad testing showed the contact counterparty
selector has strong called-subset value, while broader packs introduce
cross-lane regressions on simple relationship/update tasks. This pack keeps
only the high-precision message-recency contact update selector so routing can
hide helpers for plain CRUD cases.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

ROOT = Path("artifacts/registry_experiments/gap_closure_lab/action_precondition_loop")
MANIFEST_ROOT = Path(
    "artifacts/experiment_manifests/gap_closure_lab/action_precondition_loop"
)
SOURCE = (
    ROOT
    / "full_timestamp_schedule_v2_plus_state_v3_send_lookup_pack"
    / "registry_manifest.json"
)
OUT = ROOT / "contact_counterparty_selector_only_pack" / "registry_manifest.json"
SUMMARY = MANIFEST_ROOT / "contact_counterparty_selector_only_summary.json"
TOOL_NAME = "select_message_counterparty_for_contact_update"


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


def main() -> None:
    source = cast(dict[str, Any], json.loads(SOURCE.read_text(encoding="utf-8")))
    tool_entry = source["tools"][TOOL_NAME]
    manifest = {"tools": {TOOL_NAME: tool_entry}}
    registry_sha = _write_json(OUT, manifest)
    summary_sha = _write_json(
        SUMMARY,
        {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "experimental_only": True,
            "source_registry": str(SOURCE),
            "output_registry": str(OUT),
            "registry_sha256": registry_sha,
            "tool_names": [TOOL_NAME],
            "rationale": (
                "Retain the proven message-recency contact update selector while "
                "removing broad timestamp/contact planners that can pollute plain "
                "Contact CRUD tasks."
            ),
            "leakage_control": (
                "No scenario ids, expected answers, truth labels, or hidden facts "
                "are encoded in the tool. The pack is a registry recombination of "
                "an already validated pure helper."
            ),
        },
    )
    print(
        json.dumps(
            {
                "registry": str(OUT),
                "registry_sha256": registry_sha,
                "summary_sha256": summary_sha,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
