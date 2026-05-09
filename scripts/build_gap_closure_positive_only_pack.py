"""Build a positive-only recency/action recombination pack.

This removes the post-scale negative abstention guard while retaining the
low-frequency tools with positive called-subset outcome in the sealed scale run.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SOURCE = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "recency_search_contact_selector_safe_bridge_plus_guard_final_selector_pack/"
    "registry_manifest.json"
)
OUT = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "recency_search_contact_selector_positive_only_pack/registry_manifest.json"
)
SUMMARY = Path(
    "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/"
    "recency_search_contact_selector_positive_only_build_summary.json"
)

KEEP = (
    "resolve_search_window_or_bounds",
    "select_message_content_by_recency",
    "select_message_counterparty_for_contact_update",
)


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
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    tools = {name: copy.deepcopy(source["tools"][name]) for name in KEEP}
    now = datetime.now(timezone.utc).isoformat()
    for name, entry in tools.items():
        entry["accepted_at"] = now
        entry["birth_scenario"] = (
            "gap_closure_lab_postscale_positive_only_recombination"
        )
        entry["version"] = int(entry.get("version", 1)) + 1
        spec = entry["tool"]["spec"]
        rationale = str(spec.get("generalization_rationale") or "")
        spec["generalization_rationale"] = (
            rationale
            + " Post-scale validate250 showed this helper family had positive "
            "called-subset value while the insufficient-record guard was "
            "slightly outcome-negative, so this registry tests the smaller "
            "positive-only bundle without the guard."
        ).strip()

    digest = _write_json(OUT, {"tools": tools})
    summary = {
        "created_at": now,
        "source_registry": str(SOURCE),
        "output_registry": str(OUT),
        "output_registry_sha256": digest,
        "tool_names": sorted(tools),
        "removed_tools": ["detect_insufficient_visible_records"],
        "experimental_only": True,
        "objective": (
            "Test whether retaining only positive called-subset recency/action "
            "helpers improves natural adoption and reduces context pollution."
        ),
        "leakage_statement": (
            "Uses sealed scale diagnostics at aggregate/tool level as development "
            "feedback, then evaluates on remaining fresh split. No hidden labels, "
            "expected answers, scenario IDs, or task-specific facts are encoded."
        ),
    }
    _write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
