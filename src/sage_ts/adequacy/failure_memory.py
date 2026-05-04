"""Mechanism-level failure-memory helpers for generation, gating, and promotion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

UNRESOLVED_STATUSES = {"active_failure", "repaired_pending_test"}


def load_failure_memory(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries", [])
    return entries if isinstance(entries, list) else []


def unresolved_failure_entries(path: Path | None) -> list[dict[str, Any]]:
    return [
        entry
        for entry in load_failure_memory(path)
        if str(entry.get("status", "")) in UNRESOLVED_STATUSES
    ]


def relevant_failure_entries(
    path: Path | None,
    *,
    tool_name: str | None = None,
    mechanisms: tuple[str, ...] = (),
    canonical_key: str | None = None,
) -> list[dict[str, Any]]:
    mechanism_set = {item for item in mechanisms if item}
    canonical = (canonical_key or "").split(":", 1)[-1]
    relevant: list[dict[str, Any]] = []
    for entry in unresolved_failure_entries(path):
        mechanism_id = str(entry.get("mechanism_id", ""))
        candidate_name = str(entry.get("candidate_name", ""))
        symptoms = " ".join(
            str(item) for item in entry.get("failure_symptoms", [])
        ).lower()
        root_cause = str(entry.get("suspected_root_cause", "")).lower()
        if tool_name and candidate_name == tool_name:
            relevant.append(entry)
            continue
        if mechanism_id and mechanism_id in mechanism_set:
            relevant.append(entry)
            continue
        if canonical and canonical in mechanism_id:
            relevant.append(entry)
            continue
        if canonical and (canonical in symptoms or canonical in root_cause):
            relevant.append(entry)
            continue
    return relevant


def generation_failure_memory_context(
    path: Path | None,
    *,
    canonical_key: str,
    suggested_tool_name: str | None,
) -> dict[str, Any]:
    entries = relevant_failure_entries(
        path,
        tool_name=suggested_tool_name,
        canonical_key=canonical_key,
    )
    return {
        "unresolved_relevant_failures": [
            {
                "mechanism_id": item.get("mechanism_id"),
                "candidate_name": item.get("candidate_name"),
                "failure_symptoms": item.get("failure_symptoms", []),
                "suspected_root_cause": item.get("suspected_root_cause"),
                "unblock_conditions": item.get("unblock_conditions", []),
                "status": item.get("status"),
            }
            for item in entries
        ]
    }


def gate_failure_memory_reasons(
    path: Path | None,
    *,
    tool_name: str,
    mechanisms: tuple[str, ...],
    diagnostic_only: bool,
    repair_rationale: str,
) -> list[str]:
    entries = relevant_failure_entries(
        path,
        tool_name=tool_name,
        mechanisms=mechanisms,
    )
    if not entries:
        return []
    repair_text = repair_rationale.lower()

    def _materially_repairs(entry: dict[str, Any]) -> bool:
        mechanism_id = str(entry.get("mechanism_id", "")).lower()
        if "tie" in mechanism_id or "ambigu" in mechanism_id:
            return any(
                token in repair_text
                for token in ("tie", "ambigu", "unique", "abstain", "no match")
            )
        if "visible_not_called" in mechanism_id:
            return any(
                token in repair_text
                for token in (
                    "visible-not-called",
                    "visible not called",
                    "adoption",
                    "called-subset",
                    "called subset",
                    "routing",
                    "suppress",
                )
            )
        if "bounds" in mechanism_id or "narrow_search_window" in mechanism_id:
            return any(
                token in repair_text
                for token in (
                    "not just timestamp bounds",
                    "selection",
                    "selected_record",
                    "downstream action",
                    "search_kwargs",
                )
            )
        return any(
            token in repair_text
            for token in ("repair", "fixed", "addresses", "addressing", "avoids")
        )

    unrepaired = [entry for entry in entries if not _materially_repairs(entry)]
    repaired = len(unrepaired) < len(entries)
    if diagnostic_only and repaired:
        return []
    if not unrepaired and mechanisms:
        return []
    return [
        f"unresolved_failure_memory:{entry.get('mechanism_id') or entry.get('candidate_name')}"
        for entry in unrepaired
    ]
