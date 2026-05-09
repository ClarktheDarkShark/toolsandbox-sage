"""Build the smallest retained-positive recency/time/day portfolio.

Recent recombination runs showed that value came from time/day and recency
selection helpers, while contact scalar planners were either uncalled or weakly
negative in the mixed expanded60 split. This pack keeps only the retained
positive recency/action tools plus the generic day-distance helper.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "best3_plus_final_selector_days_pack/registry_manifest.json"
)
OUT = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "recency_time_days_minimal_pack/registry_manifest.json"
)
SUMMARY = Path(
    "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/"
    "recency_time_days_minimal_build_summary.json"
)

KEEP_TOOLS = {
    "days_between_timestamps",
    "relative_day_time_to_timestamp",
    "resolve_search_window_or_bounds",
    "select_message_content_by_recency",
    "select_message_counterparty_for_contact_update",
}


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
    base = json.loads(BASE.read_text(encoding="utf-8"))
    source_tools = base["tools"]
    missing = sorted(KEEP_TOOLS - set(source_tools))
    if missing:
        raise SystemExit(f"Missing expected source tools: {missing}")
    tools = {name: copy.deepcopy(source_tools[name]) for name in sorted(KEEP_TOOLS)}
    now = datetime.now(timezone.utc).isoformat()
    digest = _write_json(OUT, {"tools": tools})
    summary = {
        "created_at": now,
        "source_registry": str(BASE),
        "output_registry": str(OUT),
        "output_registry_sha256": digest,
        "tool_names": sorted(tools),
        "experimental_only": True,
        "objective": (
            "Retain the positive recency/time/day helpers while pruning contact "
            "scalar planners and broad timestamp selectors that showed weak or "
            "negative mixed-cohort value."
        ),
        "keep_reason": {
            "days_between_timestamps": (
                "Quality expanded60 backtest called 11/11 visible with positive "
                "called-subset outcome; residual diagnostic outcome +0.116."
            ),
            "relative_day_time_to_timestamp": (
                "Quality expanded60 backtests repeatedly showed strong called-subset "
                "outcome on reminder relative-time tasks."
            ),
            "resolve_search_window_or_bounds": (
                "Retained from prior scale run with strong called-subset outcome in "
                "recency/search-window tasks."
            ),
            "select_message_content_by_recency": (
                "Retained positive low-frequency message-recency selector."
            ),
            "select_message_counterparty_for_contact_update": (
                "Retained as a narrow recency/action pocket; no broad promotion "
                "claim is made."
            ),
        },
        "pruned_reason": {
            "format_days_until_event_answer": (
                "Helped narrow diagnostic but called-subset outcome was negative "
                "in the quality expanded60 backtest."
            ),
            "plan_contact_search_from_scalar_constraint": (
                "Weak/negative mixed-cohort called-subset signal in recent runs."
            ),
            "plan_contact_lookup_query": (
                "No natural value in the current recency/time/day campaign."
            ),
            "extract_contact_field_from_search_result": (
                "Visible-not-called in current mixed runs; not part of the retained "
                "recency/action portfolio."
            ),
            "select_record_by_timestamp_extreme": (
                "Earlier targeted positives did not survive broad mixed cohorts."
            ),
        },
        "leakage_statement": (
            "This pack filters previously generated generic helpers by observed "
            "tool-level behavior. It does not encode scenario IDs, hidden labels, "
            "expected answers, or benchmark-specific facts."
        ),
    }
    _write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
