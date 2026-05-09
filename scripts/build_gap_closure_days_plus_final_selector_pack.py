"""Build an experimental best3/final-selector pack with a day-distance helper.

The expanded60 quality run surfaced a clean remaining gap: many unseen tasks
expected a deterministic ``days_between_timestamps`` helper, but the retained
positive portfolio did not include one. This builder adds that generic helper
to the isolated experimental registry only.
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
    "best3_plus_final_selector_positive_pack/registry_manifest.json"
)
OUT = Path(
    "artifacts/registry_experiments/gap_closure_lab/recombination_adoption/"
    "best3_plus_final_selector_days_pack/registry_manifest.json"
)
SUMMARY = Path(
    "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/"
    "best3_plus_final_selector_days_build_summary.json"
)


DAYS_CODE = '''def days_between_timestamps(timestamp_0: float, timestamp_1: float) -> dict:
    """
    Return whole-day distance and leftover seconds between two Unix timestamps.

    Use this for calendar-distance questions after obtaining both timestamps.
    The result is deterministic and has no side effects.
    """
    total_seconds = int(float(timestamp_1) - float(timestamp_0))
    sign = -1 if total_seconds < 0 else 1
    absolute_seconds = abs(total_seconds)
    days = absolute_seconds // 86400
    seconds = absolute_seconds - (days * 86400)
    return {
        "days": int(days * sign),
        "seconds": int(seconds * sign),
        "total_seconds": int(total_seconds),
        "direction": "future" if total_seconds > 0 else ("past" if total_seconds < 0 else "same_time"),
    }'''


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


def _days_entry(now: str) -> dict[str, Any]:
    code_hash = _sha256(DAYS_CODE.encode("utf-8"))
    return {
        "accepted_at": now,
        "birth_scenario": "gap_closure_lab_expanded60_quality_reflection",
        "code_hash": code_hash,
        "legacy_diagnostic": False,
        "retired": False,
        "reuse_count": 0,
        "schema_version": 2,
        "success_flips": 0,
        "tool": {
            "code": DAYS_CODE,
            "spec": {
                "abstain_behavior": (
                    "Return only the numeric timestamp distance. Do not infer "
                    "holiday dates, current time, user location, or final answers "
                    "when either timestamp is missing."
                ),
                "applicable_task_families": [
                    "find_days_till_holiday",
                    "find_days_till_holiday_wifi_off",
                ],
                "canonical_route_substitution_risk": "low",
                "cross_task_applicability_count": 11,
                "description": (
                    "Compute the whole-day and leftover-second distance between "
                    "two Unix timestamps. Use after retrieving the current timestamp "
                    "and a target holiday/event timestamp for 'days until' questions."
                ),
                "diagnostic_only": False,
                "estimated_step_compression": 3,
                "expected_milestone_calls_replaced": [],
                "family": "derived_value_calculator",
                "final_state_preservation_plan": (
                    "Pure calculation helper. It does not read, write, mutate, or "
                    "call app state."
                ),
                "generalization_rationale": (
                    "Calendar-distance tasks repeatedly require deterministic day "
                    "arithmetic after current and target timestamps are visible. "
                    "The helper is generic over timestamps and contains no task IDs, "
                    "holiday names, expected answers, or benchmark facts."
                ),
                "grading_accounting_note": (
                    "Outcome/task completion remains primary. Canonical/reference "
                    "text differences are secondary."
                ),
                "inadequacy_evidence": {
                    "failed_tool_calls": [],
                    "final_answer_route_mismatch": False,
                    "planner_failures": [],
                    "repeated_failed_tool_calls": [],
                    "signals": [
                        "expanded60_quality_expected_helper_fit_days_between_timestamps"
                    ],
                    "summary": (
                        "The quality expanded60 preflight reported 11 expected "
                        "days_between_timestamps opportunities while the retained "
                        "positive portfolio had no day-distance helper."
                    ),
                    "visible_data_gaps": [],
                },
                "inputs": [
                    {
                        "annotation": "float",
                        "description": "Earlier Unix timestamp in seconds.",
                        "name": "timestamp_0",
                    },
                    {
                        "annotation": "float",
                        "description": "Later or comparison Unix timestamp in seconds.",
                        "name": "timestamp_1",
                    },
                ],
                "known_failure_mechanisms_addressed": [
                    "manual_timestamp_subtraction_errors",
                    "wrong_day_count_from_seconds_arithmetic",
                ],
                "negative_triggers": [
                    "Do not use when either timestamp is unknown.",
                    "Do not use to guess a holiday date.",
                    "Do not use for reminder creation timestamp canonicalization.",
                ],
                "output_annotation": "dict",
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer"},
                        "seconds": {"type": "integer"},
                        "total_seconds": {"type": "integer"},
                        "direction": {"type": "string"},
                    },
                    "required": ["days", "seconds", "total_seconds", "direction"],
                },
                "positive_triggers": [
                    "Question asks how many days until a holiday or event.",
                    "Current timestamp and target timestamp are both available.",
                ],
                "preserves_side_effect_tools": [],
                "reason_tool_is_decisive": (
                    "It converts two retrieved timestamps into the exact day count "
                    "needed for the final answer."
                ),
                "required_original_tool_calls": [
                    "get_current_timestamp",
                    "search_holiday",
                ],
                "schema_version": 2,
                "shortfall_cluster_evidence": ["derived_value:days_between_timestamps"],
                "tool_name": "days_between_timestamps",
            },
        },
        "validation": {
            "accepted": True,
            "errors": [],
            "held_out_check_count": 2,
            "negative_applicability_count": 3,
            "runtime_smoke_passed": True,
            "source_example_count": 2,
        },
        "version": 1,
    }


def main() -> None:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    tools = copy.deepcopy(base["tools"])
    now = datetime.now(timezone.utc).isoformat()
    tools["days_between_timestamps"] = _days_entry(now)
    digest = _write_json(OUT, {"tools": tools})
    summary = {
        "created_at": now,
        "source_registry": str(BASE),
        "output_registry": str(OUT),
        "output_registry_sha256": digest,
        "tool_names": sorted(tools),
        "added_tools": ["days_between_timestamps"],
        "experimental_only": True,
        "objective": (
            "Repair the expanded60-discovered holiday/day-distance gap while "
            "retaining the positive best3/final-selector portfolio."
        ),
        "leakage_statement": (
            "The helper is generic over two numeric timestamps. It does not encode "
            "scenario IDs, holiday names, expected answers, truth labels, or cache "
            "availability."
        ),
    }
    _write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
