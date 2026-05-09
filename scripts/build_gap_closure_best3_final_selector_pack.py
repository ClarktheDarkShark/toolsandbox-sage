"""Build a best3-plus-final-selector recombination pack.

This copies the experimental best3/V2.6 reference registry into an isolated
gap-closure registry and adds the retained final-answer-ready message selector
plus repaired contact-recency selector.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BEST3 = Path(
    "artifacts/registry_experiments/gap_closure_lab/"
    "best3_v26_reference_copy/registry_manifest.json"
)
FINAL_SELECTOR = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "recency_search_contact_selector_safe_bridge_plus_guard_final_selector_pack/"
    "registry_manifest.json"
)
OUT = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "best3_plus_final_selector_positive_pack/registry_manifest.json"
)
SUMMARY = Path(
    "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/"
    "best3_plus_final_selector_positive_build_summary.json"
)

ADD = (
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
    best3 = json.loads(BEST3.read_text(encoding="utf-8"))
    final = json.loads(FINAL_SELECTOR.read_text(encoding="utf-8"))
    tools = copy.deepcopy(best3["tools"])
    now = datetime.now(timezone.utc).isoformat()
    for name in ADD:
        entry = copy.deepcopy(final["tools"][name])
        entry["accepted_at"] = now
        entry["birth_scenario"] = (
            "gap_closure_lab_best3_final_selector_positive_recombination"
        )
        entry["version"] = int(entry.get("version", 1)) + 1
        spec = entry["tool"]["spec"]
        rationale = str(spec.get("generalization_rationale") or "")
        spec["generalization_rationale"] = (
            rationale
            + " This isolated registry tests whether the retained final selector "
            "and contact selector can add low-frequency value to the copied "
            "best3/V2.6 reference helper set without promoting either into a "
            "protected registry."
        ).strip()
        tools[name] = entry

    digest = _write_json(OUT, {"tools": tools})
    summary = {
        "created_at": now,
        "source_best3_reference_copy": str(BEST3),
        "source_final_selector_registry": str(FINAL_SELECTOR),
        "output_registry": str(OUT),
        "output_registry_sha256": digest,
        "tool_names": sorted(tools),
        "added_tools": list(ADD),
        "experimental_only": True,
        "objective": (
            "Combine the best3/V2.6 reference helper copy with the strongest "
            "low-frequency final-answer-ready recency/action selectors."
        ),
        "leakage_statement": (
            "Copies existing experimental registry entries and generic trigger "
            "metadata only. No protected registry is modified and no expected "
            "answers, hidden labels, scenario IDs, or cache availability are "
            "encoded."
        ),
    }
    _write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
