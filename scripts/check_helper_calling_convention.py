# mypy: ignore-errors
"""Trace-check: verify prep-helper calling-convention invariants across a run.

Checks four invariants for any generated prep helper (currently
prepare_reminder_creation_args) in candidate trajectory conversation.json files:

  1. The helper and its required base tool (datetime_info_to_timestamp) are
     never issued in the same parallel assistant batch.
  2. When datetime_info_to_timestamp is called, its result message appears
     before the next prepare_reminder_creation_args call.
  3. When prepare_reminder_creation_args succeeds (should_call_add_reminder=True),
     add_reminder is called in a subsequent turn.
  4. When prepare_reminder_creation_args abstains (should_call_add_reminder=False),
     add_reminder is NOT called directly after without another helper call.

Usage:
    python scripts/check_helper_calling_convention.py <run_output_dir> [<run_output_dir> ...]
    python scripts/check_helper_calling_convention.py outputs/phase_B_v2_corrected_description
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_HELPER = "prepare_reminder_creation_args"
_TIMESTAMP_BASE = "datetime_info_to_timestamp"
_SIDE_EFFECT = "add_reminder"


def _tool_names(message: dict) -> list[str]:
    return [
        tc.get("function", {}).get("name", "")
        for tc in message.get("tool_calls") or []
        if isinstance(tc, dict)
    ]


def _parse_result(content: object) -> object:
    if isinstance(content, str):
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return content
    return content


def check_conversation(path: Path) -> list[str]:
    violations: list[str] = []
    messages: list[dict] = json.loads(path.read_text(encoding="utf-8"))

    pending_datetime_call = False
    datetime_result_seen = False

    for idx, msg in enumerate(messages):
        role = msg.get("role", "")

        if role == "assistant" and msg.get("tool_calls"):
            names = _tool_names(msg)
            has_helper = _HELPER in names
            has_ts_base = _TIMESTAMP_BASE in names

            # Invariant 1: never in same batch
            if has_helper and has_ts_base:
                violations.append(
                    f"  [msg {idx}] {_HELPER} and {_TIMESTAMP_BASE} in same parallel batch"
                )

            # Track whether datetime call is pending
            if has_ts_base:
                pending_datetime_call = True
                datetime_result_seen = False

            # Invariant 2: datetime result must arrive before helper call
            if has_helper and pending_datetime_call and not datetime_result_seen:
                violations.append(
                    f"  [msg {idx}] {_HELPER} called before {_TIMESTAMP_BASE} result received"
                )

        elif role == "tool":
            name = msg.get("name", "")

            if name == _TIMESTAMP_BASE and pending_datetime_call:
                datetime_result_seen = True
                pending_datetime_call = False

            if name == _HELPER:
                # Reset datetime tracking after helper is called
                pending_datetime_call = False
                datetime_result_seen = False

                result = _parse_result(msg.get("content"))
                if not isinstance(result, dict):
                    continue
                should_call = result.get("should_call_add_reminder")

                # Look ahead to next assistant batch
                next_assistant_names: list[str] = []
                for lookahead in messages[idx + 1 :]:
                    if lookahead.get("role") == "assistant" and lookahead.get(
                        "tool_calls"
                    ):
                        next_assistant_names = _tool_names(lookahead)
                        break
                    if lookahead.get("role") == "user":
                        break

                # Invariant 3: success → add_reminder must follow
                if should_call is True and _SIDE_EFFECT not in next_assistant_names:
                    violations.append(
                        f"  [tool msg after {idx}] helper succeeded but {_SIDE_EFFECT} not called next"
                    )

                # Invariant 4: abstain → add_reminder must NOT follow directly
                if should_call is False and _SIDE_EFFECT in next_assistant_names:
                    violations.append(
                        f"  [tool msg after {idx}] helper abstained but {_SIDE_EFFECT} called directly after"
                    )

    return violations


def check_run_dir(run_dir: Path) -> dict[str, list[str]]:
    results: dict[str, list[str]] = {}
    for convo in sorted(run_dir.rglob("conversation.json")):
        if "candidate" not in convo.parts:
            continue
        scenario = convo.parent.name
        violations = check_conversation(convo)
        if violations:
            results[scenario] = violations
    return results


def main(argv: list[str]) -> int:
    if not argv:
        print(
            "Usage: check_helper_calling_convention.py <run_dir> [...]", file=sys.stderr
        )
        return 1

    total_scenarios = 0
    total_violations: dict[str, list[str]] = {}

    for arg in argv:
        run_dir = Path(arg)
        if not run_dir.exists():
            print(f"ERROR: {run_dir} does not exist", file=sys.stderr)
            return 1
        found = check_run_dir(run_dir)
        total_violations.update(found)
        # count candidate conversations
        total_scenarios += sum(
            1 for p in run_dir.rglob("conversation.json") if "candidate" in p.parts
        )

    print(
        f"Scanned {total_scenarios} candidate conversation(s) across {len(argv)} run dir(s)."
    )
    if not total_violations:
        print("OK: no calling-convention violations found.")
        return 0

    print(f"VIOLATIONS in {len(total_violations)} scenario(s):")
    for scenario, viols in sorted(total_violations.items()):
        print(f"\n  Scenario: {scenario}")
        for v in viols:
            print(v)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
