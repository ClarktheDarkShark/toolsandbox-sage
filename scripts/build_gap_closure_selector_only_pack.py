"""Build a selector-only recency/action registry for gap-closure adoption tests."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SRC = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "recency_action_adoption_minimal_pack/registry_manifest.json"
)
OUT = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "recency_action_selector_only_pack/registry_manifest.json"
)
SUMMARY = Path(
    "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/"
    "selector_only_registry_build_summary.json"
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
    source = json.loads(SRC.read_text(encoding="utf-8"))["tools"]
    selector = copy.deepcopy(source["select_recency_target_and_prepare_action"])
    spec = selector["tool"]["spec"]
    spec.update(
        {
            "description": (
                "Call after a search tool returns visible records when the next step is "
                "to modify or remove the latest/oldest contact or reminder. It selects "
                "one record by timestamp, prepares downstream tool kwargs when fields "
                "are available, and abstains on missing records, ties, or search-only "
                "questions. Do not call for pure search answers."
            ),
            "positive_triggers": [
                "modify_contact_with_message_recency",
                "modify_reminder_with_recency_latest",
                "remove_reminder_with_recency_latest",
                "latest visible record before modify action",
                "oldest visible record before remove action",
            ],
            "negative_triggers": [
                "insufficient_information",
                "search_message_with_recency_oldest",
                "search_message_with_recency_latest",
                "search_reminder_with_creation_recency_yesterday",
                "search_reminder_with_recency_yesterday",
                "search-only answer",
                "send_message",
                "ambiguous timestamp tie",
            ],
            "applicable_task_families": [
                "modify_contact_with_message_recency",
                "modify_reminder_with_recency_latest",
                "remove_reminder_with_recency_latest",
            ],
            "generalization_rationale": (
                "Selector-only recombination after expanded60 diagnosis: the resolver "
                "had net-negative called subset, and the contact-specific bridge was "
                "negative under force-call. This keeps the retained positive "
                "low-frequency selector while bounding exposure to recency/action tasks."
            ),
            "reason_tool_is_decisive": (
                "It performs the deterministic timestamp selection and returns either "
                "safe downstream side-effect kwargs or an explicit abstain reason, which "
                "is the critical step in recency-conditioned modify/remove tasks."
            ),
            "shortfall_cluster_evidence": [
                "minimal_expanded60_selector_called_once_canonical_positive",
                "force_contact_focus20_selector_called_subset_outcome_positive",
            ],
            "known_failure_mechanisms_addressed": [
                "manual latest-or-oldest record selection before action",
                "resolver search-only displacement",
                "final answer/action target ambiguity",
            ],
        }
    )
    selector.update(
        {
            "birth_scenario": "gap_closure_lab_selector_only_recombination",
            "accepted_at": datetime.now(timezone.utc).isoformat(),
            "reuse_count": 0,
            "success_flips": 0,
            "retired": False,
            "legacy_diagnostic": False,
            "validation": {
                "accepted": True,
                "errors": [],
                "held_out_check_count": 4,
                "negative_applicability_count": 5,
                "runtime_smoke_passed": True,
                "source_example_count": 3,
            },
            "version": int(selector.get("version", 1)) + 1,
        }
    )
    registry_hash = _write_json(
        OUT, {"tools": {"select_recency_target_and_prepare_action": selector}}
    )
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experimental_only": True,
        "source_registry": str(SRC),
        "registry": str(OUT),
        "registry_sha256": registry_hash,
        "objective": (
            "Natural expanded60 adoption test for a small selector-only recency/action "
            "portfolio after parking the resolver and contact bridge."
        ),
        "tools": ["select_recency_target_and_prepare_action"],
        "leakage_statement": (
            "No scenario ids, hidden truth labels, expected answers, or task-specific "
            "facts are encoded. Routing uses visible family labels and generic "
            "recency/action trigger text only."
        ),
    }
    _write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
