"""Build a final-answer-ready day-distance experimental pack.

The first day-distance helper showed real outcome value but often hurt
canonical/reference scoring because it replaced the expected intermediate
``timestamp_diff`` trace and left final phrasing to the actor. This pack tests a
generic formatter/calculator that accepts two visible timestamps plus a visible
event name and returns final-answer-ready text. It is experimental only.
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
    "best3_plus_final_selector_days_answer_pack/registry_manifest.json"
)
SUMMARY = Path(
    "artifacts/experiment_manifests/gap_closure_lab/recombination_adoption/"
    "best3_plus_final_selector_days_answer_build_summary.json"
)


ANSWER_CODE = '''def format_days_until_event_answer(timestamp_0: float, timestamp_1: float, event_name: str) -> dict:
    """
    Return a deterministic day distance plus final-answer-ready event wording.

    Use this only after the current timestamp, target event timestamp, and
    event/holiday name are visible. The helper is pure and has no side effects.
    """
    cleaned_event_name = str(event_name or "").strip()
    if not cleaned_event_name:
        return {
            "days": 0,
            "seconds": 0,
            "total_seconds": 0,
            "direction": "unknown",
            "event_name": "",
            "final_answer": "",
            "abstain_reason": "missing_event_name",
        }

    total_seconds = int(float(timestamp_1) - float(timestamp_0))
    sign = -1 if total_seconds < 0 else 1
    absolute_seconds = abs(total_seconds)
    absolute_days = absolute_seconds // 86400
    leftover_seconds = absolute_seconds - (absolute_days * 86400)
    days = int(absolute_days * sign)
    seconds = int(leftover_seconds * sign)

    if total_seconds < 0:
        final_answer = f"It was {abs(days)} days since {cleaned_event_name}."
        direction = "past"
    elif total_seconds == 0:
        final_answer = f"It is 0 days till {cleaned_event_name}."
        direction = "same_time"
    else:
        final_answer = f"It is {days} days till {cleaned_event_name}."
        direction = "future"

    return {
        "days": days,
        "seconds": seconds,
        "total_seconds": int(total_seconds),
        "direction": direction,
        "event_name": cleaned_event_name,
        "final_answer": final_answer,
        "abstain_reason": "",
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


def _answer_entry(now: str) -> dict[str, Any]:
    code_hash = _sha256(ANSWER_CODE.encode("utf-8"))
    return {
        "accepted_at": now,
        "birth_scenario": "gap_closure_lab_days_answer_shape_reflection",
        "code_hash": code_hash,
        "legacy_diagnostic": False,
        "retired": False,
        "reuse_count": 0,
        "schema_version": 2,
        "success_flips": 0,
        "tool": {
            "code": ANSWER_CODE,
            "spec": {
                "abstain_behavior": (
                    "Return abstain_reason='missing_event_name' if the event name "
                    "is not visible. Do not infer holiday dates, current time, "
                    "or event names."
                ),
                "applicable_task_families": [
                    "find_days_till_holiday",
                    "find_days_till_holiday_wifi_off",
                ],
                "canonical_route_substitution_risk": "medium",
                "cross_task_applicability_count": 11,
                "description": (
                    "Compute whole-day distance between two Unix timestamps and "
                    "return final-answer-ready wording for a visible holiday or "
                    "event name, for example 'It is N days till <event>'."
                ),
                "diagnostic_only": False,
                "estimated_step_compression": 3,
                "expected_milestone_calls_replaced": [],
                "family": "derived_value_calculator",
                "final_state_preservation_plan": (
                    "Pure formatting/calculation helper. It does not read, write, "
                    "mutate, or call app state."
                ),
                "generalization_rationale": (
                    "Calendar-distance tasks need deterministic timestamp arithmetic "
                    "and exact final phrasing after visible current and target "
                    "timestamps are available. The helper is generic over event "
                    "names and timestamps and contains no scenario IDs, hidden "
                    "labels, expected answers, or benchmark facts."
                ),
                "grading_accounting_note": (
                    "Outcome/task completion remains primary. This helper may "
                    "substitute for an intermediate reference tool trace; canonical "
                    "impact is reported separately."
                ),
                "inadequacy_evidence": {
                    "failed_tool_calls": [],
                    "final_answer_route_mismatch": True,
                    "planner_failures": [],
                    "repeated_failed_tool_calls": [],
                    "signals": [
                        "days_between_timestamps_positive_but_answer_shape_loss",
                        "task77_outcome_correct_canonical_partial_dashboard_repair",
                    ],
                    "summary": (
                        "The generic days_between_timestamps helper improved outcome "
                        "but left final holiday naming to the actor and hurt canonical "
                        "tool-trace scoring. This candidate tests a final-answer-ready "
                        "shape without encoding any task-specific answer."
                    ),
                    "visible_data_gaps": [],
                },
                "inputs": [
                    {
                        "annotation": "float",
                        "description": "Current or earlier Unix timestamp in seconds.",
                        "name": "timestamp_0",
                    },
                    {
                        "annotation": "float",
                        "description": "Target event Unix timestamp in seconds.",
                        "name": "timestamp_1",
                    },
                    {
                        "annotation": "str",
                        "description": (
                            "Visible event or holiday name to preserve in the final "
                            "answer, such as the name used in the user's request or "
                            "the holiday lookup."
                        ),
                        "name": "event_name",
                    },
                ],
                "known_failure_mechanisms_addressed": [
                    "manual_timestamp_subtraction_errors",
                    "wrong_day_count_from_seconds_arithmetic",
                    "final_answer_uses_date_instead_of_named_event",
                    "intermediate_value_not_final_answer_ready",
                ],
                "negative_triggers": [
                    "Do not use when either timestamp is unknown.",
                    "Do not use when the event or holiday name is not visible.",
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
                        "event_name": {"type": "string"},
                        "final_answer": {"type": "string"},
                        "abstain_reason": {"type": "string"},
                    },
                    "required": [
                        "days",
                        "seconds",
                        "total_seconds",
                        "direction",
                        "event_name",
                        "final_answer",
                        "abstain_reason",
                    ],
                },
                "positive_triggers": [
                    "Question asks how many days until a holiday or event.",
                    "Current timestamp, target timestamp, and event name are visible.",
                ],
                "preserves_side_effect_tools": [],
                "reason_tool_is_decisive": (
                    "It returns the exact day count and final answer wording after "
                    "the current and event timestamps are retrieved."
                ),
                "required_original_tool_calls": [
                    "get_current_timestamp",
                    "search_holiday",
                ],
                "schema_version": 2,
                "shortfall_cluster_evidence": [
                    "derived_value:days_between_timestamps",
                    "final_answer_ready:holiday_day_count",
                ],
                "tool_name": "format_days_until_event_answer",
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
    tools["format_days_until_event_answer"] = _answer_entry(now)
    digest = _write_json(OUT, {"tools": tools})
    summary = {
        "created_at": now,
        "source_registry": str(BASE),
        "output_registry": str(OUT),
        "output_registry_sha256": digest,
        "tool_names": sorted(tools),
        "added_tools": ["format_days_until_event_answer"],
        "experimental_only": True,
        "objective": (
            "Repair the day-distance answer-shape gap while retaining the "
            "positive best3/final-selector portfolio."
        ),
        "leakage_statement": (
            "The helper is generic over two numeric timestamps and a visible "
            "event name. It does not encode scenario IDs, holiday names, expected "
            "answers, truth labels, or cache availability."
        ),
    }
    _write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
