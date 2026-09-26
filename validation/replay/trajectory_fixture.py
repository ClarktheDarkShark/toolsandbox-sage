#!/usr/bin/env python3
"""Build and verify the compact, historical full-trajectory replay corpus.

The builder reads only the frozen Chapter 4 paper cohort.  It deliberately
allowlists trajectory, outcome, routing, and lifecycle fields rather than
copying whole run directories, mutable registries, model credentials, hidden
user-simulator prompts, or interactive consoles.

The checked-in fixture is sufficient for offline outcome/state replay.  When
the original artifacts are available, ``--source-root`` additionally verifies
every source file against the content hashes in the fixture manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


HERE = Path(__file__).resolve().parent
DEFAULT_FIXTURE = HERE / "fixtures" / "full_trajectory_v1.json"
DEFAULT_MANIFEST = HERE / "fixtures" / "full_trajectory_v1.manifest.json"

COHORT_ID = "chapter4_final_policy_online_frozen_20260911_4ce1c6d"
COHORT_MANIFEST = (
    "artifacts/chapter4_evidence/"
    f"{COHORT_ID}/technical_replacement/final_selected_cohort/"
    "selected_cohort_manifest.json"
)
ONLINE_REP01_RUN = (
    "outputs/chapter4_evidence/"
    f"{COHORT_ID}/online/rep01/native_action/"
    "online_build_full_20260911_150719"
)
ONLINE_REP01 = (
    f"{ONLINE_REP01_RUN}/candidate/"
    "online_build_full_candidate_agent_gpt-4o-mini_user_gpt-4o-mini_"
    "09_11_2026_15_07_31"
)
FIXED_TIMESTAMP = 1784832588
FIXED_TIMEZONE = "America/New_York"

SELECTED_CASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "add_contact_with_name_and_phone_number",
        (
            "early_task",
            "birth",
            "repair",
            "reuse",
            "generated_execution",
            "native_execution",
            "state_change",
            "contact",
        ),
    ),
    (
        "add_reminder_content_and_week_delta_and_time",
        (
            "relative_time",
            "generated_execution",
            "native_execution",
            "state_change",
            "reminder",
        ),
    ),
    (
        "find_days_till_holiday_insufficient_information",
        (
            "insufficient_information",
            "generated_execution",
            "abstention",
        ),
    ),
    (
        "find_distance_with_location_name",
        (
            "external_fixture",
            "generated_execution",
            "native_execution",
            "answer_only",
            "location",
        ),
    ),
    (
        "search_name_with_relationship_3_distraction_tools",
        (
            "post_700",
            "generated_execution",
            "native_execution",
            "reuse",
            "contact_read",
        ),
    ),
    (
        "send_message_with_phone_number_and_content",
        (
            "post_700",
            "generated_execution",
            "native_execution",
            "state_change",
            "messaging",
        ),
    ),
    (
        "update_contact_relationship_with_relationship",
        (
            "post_700",
            "generated_execution",
            "native_execution",
            "state_change",
            "multi_step",
            "contact",
        ),
    ),
    (
        "wifi_off",
        (
            "post_700",
            "generated_execution",
            "native_execution",
            "state_change",
            "device_state",
        ),
    ),
)

REQUIRED_COVERAGE = frozenset(
    {
        "birth",
        "repair",
        "reuse",
        "generated_execution",
        "native_execution",
        "state_change",
        "insufficient_information",
        "external_fixture",
        "post_700",
    }
)
STATE_NAMESPACES = ("SETTING", "CONTACT", "MESSAGING", "REMINDER")
_CALL_ID_RE = re.compile(r"\bcall_[A-Za-z0-9]+\b")


def canonical_bytes(value: Any) -> bytes:
    """Return the canonical bytes used for all record and corpus hashes."""

    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _read_json(path: Path) -> Any:
    raw = path.read_bytes()
    if not raw:
        raise ValueError(f"Source artifact is empty or not hydrated: {path}")
    return json.loads(raw)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    if not raw:
        raise ValueError(f"Source artifact is empty or not hydrated: {path}")
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def _compact_row(row: dict[str, Any]) -> dict[str, Any]:
    """Drop schema-fill nulls while preserving null-only snapshot markers."""

    compact = {key: value for key, value in row.items() if value is not None}
    if "sandbox_message_index" not in compact:
        compact["sandbox_message_index"] = row["sandbox_message_index"]
    return compact


def _replace_call_ids(value: Any, mapping: dict[str, str]) -> Any:
    """Replace provider request IDs with stable fixture-local IDs."""

    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            raw = match.group(0)
            if raw not in mapping:
                mapping[raw] = f"fixture_call_{len(mapping) + 1:03d}"
            return mapping[raw]

        return _CALL_ID_RE.sub(replace, value)
    if isinstance(value, list):
        return [_replace_call_ids(item, mapping) for item in value]
    if isinstance(value, dict):
        return {
            key: _replace_call_ids(item, mapping) for key, item in value.items()
        }
    return value


def _record_hash(record: Any) -> str:
    return sha256_bytes(canonical_bytes(record))


def _indexed(rows: Iterable[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows}


def _source_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"Source path escapes source root: {relative}") from exc
    return path


def _birth_summary(row: dict[str, Any]) -> dict[str, Any]:
    repair_history = row.get("repair_history") or []
    return {
        "accepted": bool(row.get("accepted")),
        "canonical_key": row.get("canonical_key"),
        "family": row.get("family"),
        "repair_attempted": bool(row.get("repair_attempted")),
        "repair_attempt_count": int(row.get("repair_attempt_count") or 0),
        "repair_final_errors": list(row.get("repair_final_errors") or []),
        "source_example_count": int(row.get("source_example_count") or 0),
        "held_out_check_count": int(row.get("held_out_check_count") or 0),
        "runtime_smoke_passed": bool(row.get("runtime_smoke_passed")),
        "repair_history_sha256": _record_hash(repair_history),
        "repair_code_sha256": [
            sha256_bytes(str(item.get("code") or "").encode("utf-8"))
            for item in repair_history
        ],
    }


def _selection_summary(row: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "base_tool_policy",
        "generated_tools_visible",
        "shortlisted_generated_tools",
        "generated_tools_attempted",
        "generated_tools_called",
        "generated_tools_failed",
        "selection_status",
        "selection_reason",
        "priority_injection_changed_tool_order",
        "relevance_gating_hid_retained_tool",
    )
    return {key: row.get(key) for key in keys}


def _visibility_summary(row: dict[str, Any]) -> dict[str, Any]:
    generated = list(row.get("generated_tools") or [])
    decisions = row.get("routing_decisions") or {}
    return {
        "available_tools": list(row.get("available_tools") or []),
        "generated_tools": generated,
        "shortlisted_generated_tools": list(
            row.get("shortlisted_generated_tools") or []
        ),
        "tool_allow_list": list(row.get("tool_allow_list") or []),
        "generated_routing_decisions": {
            name: decisions.get(name) for name in generated if name in decisions
        },
        "filtered_out_reasons_sha256": _record_hash(
            row.get("filtered_out_reasons") or {}
        ),
    }


def _feedback_summary(row: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "candidate_outcome",
        "candidate_outcome_source",
        "control_outcome",
        "control_outcome_source",
        "outcome_delta",
        "task_family_key",
        "generated_tools_visible",
        "generated_tools_attempted",
        "generated_tools_called",
        "generated_tools_failed",
        "immediate_actions",
        "side_effect_failures",
    )
    return {key: row.get(key) for key in keys}


def build_fixture(source_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Extract the allowlisted replay fixture and its content-hash manifest."""

    source_root = source_root.expanduser().resolve()
    run_root = _source_path(source_root, ONLINE_REP01)
    source_relatives = [
        COHORT_MANIFEST,
        f"{ONLINE_REP01_RUN}/protocol_manifest.json",
        f"{ONLINE_REP01}/result_summary.json",
        f"{ONLINE_REP01}/scenario_tool_selection.jsonl",
        f"{ONLINE_REP01}/scenario_tool_visibility.jsonl",
        f"{ONLINE_REP01}/tool_birth_events.jsonl",
        f"{ONLINE_REP01}/reuse_events.jsonl",
        f"{ONLINE_REP01}/self_evolution_task_feedback.jsonl",
        f"{ONLINE_REP01}/self_evolution_tool_lifecycle.jsonl",
    ]
    source_files: dict[str, dict[str, Any]] = {}
    for relative in source_relatives:
        path = _source_path(source_root, relative)
        source_files[relative] = {
            "byte_count": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    protocol_manifest = _read_json(
        _source_path(source_root, f"{ONLINE_REP01_RUN}/protocol_manifest.json")
    )
    if protocol_manifest.get("timezone") != FIXED_TIMEZONE:
        raise ValueError(
            "Historical protocol timezone drifted: "
            f"{protocol_manifest.get('timezone')!r} != {FIXED_TIMEZONE!r}"
        )
    if str(protocol_manifest.get("toolsandbox_fixed_now_timestamp")) != str(
        FIXED_TIMESTAMP
    ):
        raise ValueError("Historical protocol fixed timestamp drifted")

    result_summary = _read_json(run_root / "result_summary.json")
    result_rows = list(result_summary["per_scenario_results"])
    result_by_name = _indexed(result_rows, "name")
    task_index = {str(row["name"]): index for index, row in enumerate(result_rows)}
    selections = _indexed(
        _read_jsonl(run_root / "scenario_tool_selection.jsonl"), "scenario"
    )
    visibility = _indexed(
        _read_jsonl(run_root / "scenario_tool_visibility.jsonl"), "scenario"
    )
    feedback = _indexed(
        _read_jsonl(run_root / "self_evolution_task_feedback.jsonl"), "scenario"
    )
    births = _read_jsonl(run_root / "tool_birth_events.jsonl")
    reuse = _read_jsonl(run_root / "reuse_events.jsonl")
    births_by_tool: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in births:
        births_by_tool[str(row.get("tool_name") or "")].append(row)
    reuse_by_tool = Counter(str(row.get("tool_name") or "") for row in reuse)
    reuse_scenarios: dict[str, list[str]] = defaultdict(list)
    for row in reuse:
        reuse_scenarios[str(row.get("tool_name") or "")].append(
            str(row.get("scenario") or "")
        )

    first_name = SELECTED_CASES[0][0]
    first_context_relative = f"{ONLINE_REP01}/trajectories/{first_name}/execution_context.json"
    first_context_path = _source_path(source_root, first_context_relative)
    first_context = _read_json(first_context_path)
    source_files[first_context_relative] = {
        "byte_count": first_context_path.stat().st_size,
        "sha256": sha256_file(first_context_path),
    }
    sandbox_rows = first_context["_dbs"]["SANDBOX"]
    start_index = max(
        int(row["sandbox_message_index"])
        for row in sandbox_rows
        if row.get("sender") == "USER" and row.get("recipient") == "AGENT"
    )
    shared_prefix = [
        _compact_row(row)
        for row in sandbox_rows
        if int(row["sandbox_message_index"]) < start_index
        and row.get("sender") != "SYSTEM"
    ]
    shared_initial_state = {
        namespace: [
            _compact_row(row)
            for row in first_context["_dbs"][namespace]
            if int(row["sandbox_message_index"]) <= start_index
        ]
        for namespace in STATE_NAMESPACES
    }
    shared = {
        "sandbox_prefix": shared_prefix,
        "initial_state": shared_initial_state,
    }

    cases: list[dict[str, Any]] = []
    all_birth_facts: dict[str, dict[str, Any]] = {}
    for scenario_name, coverage in SELECTED_CASES:
        if scenario_name not in result_by_name:
            raise ValueError(f"Selected scenario missing from result summary: {scenario_name}")
        conversation_relative = (
            f"{ONLINE_REP01}/trajectories/{scenario_name}/conversation.json"
        )
        context_relative = (
            f"{ONLINE_REP01}/trajectories/{scenario_name}/execution_context.json"
        )
        conversation_path = _source_path(source_root, conversation_relative)
        context_path = _source_path(source_root, context_relative)
        conversation = _read_json(conversation_path)
        context = _read_json(context_path)
        for relative, path in (
            (conversation_relative, conversation_path),
            (context_relative, context_path),
        ):
            source_files[relative] = {
                "byte_count": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        request = next(
            str(message.get("content") or "")
            for message in conversation
            if message.get("role") == "user"
        )
        current_start = max(
            int(row["sandbox_message_index"])
            for row in context["_dbs"]["SANDBOX"]
            if row.get("sender") == "USER"
            and row.get("recipient") == "AGENT"
            and str(row.get("content") or "") == request
        )
        if current_start != start_index:
            raise ValueError(
                f"Unexpected trajectory start for {scenario_name}: {current_start}"
            )
        candidate_prefix = [
            _compact_row(row)
            for row in context["_dbs"]["SANDBOX"]
            if int(row["sandbox_message_index"]) < current_start
            and row.get("sender") != "SYSTEM"
        ]
        candidate_initial = {
            namespace: [
                _compact_row(row)
                for row in context["_dbs"][namespace]
                if int(row["sandbox_message_index"]) <= current_start
            ]
            for namespace in STATE_NAMESPACES
        }
        if candidate_prefix != shared_prefix or candidate_initial != shared_initial_state:
            raise ValueError(
                f"Selected scenario does not share frozen initial state: {scenario_name}"
            )

        call_id_mapping: dict[str, str] = {}
        current_rows = [
            _compact_row(row)
            for row in context["_dbs"]["SANDBOX"]
            if int(row["sandbox_message_index"]) >= current_start
            and row.get("sender") != "SYSTEM"
        ]
        current_rows = _replace_call_ids(current_rows, call_id_mapping)
        state_rows = {
            namespace: [
                _compact_row(row)
                for row in context["_dbs"][namespace]
                if int(row["sandbox_message_index"]) > current_start
            ]
            for namespace in STATE_NAMESPACES
        }
        selection_row = selections[scenario_name]
        visibility_row = visibility[scenario_name]
        feedback_row = feedback[scenario_name]
        result_row = result_by_name[scenario_name]
        generated_called = list(selection_row.get("generated_tools_called") or [])
        for tool_name in generated_called:
            if tool_name in all_birth_facts:
                continue
            matching_births = births_by_tool.get(tool_name, [])
            if matching_births:
                accepted = [row for row in matching_births if row.get("accepted")]
                selected_birth = (accepted or matching_births)[-1]
                all_birth_facts[tool_name] = {
                    **_birth_summary(selected_birth),
                    "reuse_event_count": int(reuse_by_tool[tool_name]),
                    "first_reuse_scenario": (
                        reuse_scenarios[tool_name][0]
                        if reuse_scenarios[tool_name]
                        else None
                    ),
                    "last_reuse_scenario": (
                        reuse_scenarios[tool_name][-1]
                        if reuse_scenarios[tool_name]
                        else None
                    ),
                }

        case = {
            "id": f"online_rep01_{task_index[scenario_name]:04d}_{scenario_name}",
            "scenario": scenario_name,
            "task_index_zero_based": task_index[scenario_name],
            "coverage": list(coverage),
            "sandbox_rows": current_rows,
            "state_rows": state_rows,
            "historical": {
                "categories": list(result_row.get("categories") or []),
                "exception_type": result_row.get("exception_type"),
                "turn_count": int(result_row.get("turn_count") or 0),
                "outcome_similarity": result_row.get("outcome_similarity"),
                "outcome_check_count": int(result_row.get("outcome_check_count") or 0),
                "outcome_state_history_safe": result_row.get(
                    "outcome_state_history_safe"
                ),
                "outcome_evaluator_version": result_row.get(
                    "outcome_evaluator_version"
                ),
                "selection": _selection_summary(selection_row),
                "visibility": _visibility_summary(visibility_row),
                "feedback": _feedback_summary(feedback_row),
            },
            "source_record_sha256": {
                "result": _record_hash(result_row),
                "selection": _record_hash(selection_row),
                "visibility": _record_hash(visibility_row),
                "feedback": _record_hash(feedback_row),
            },
        }
        cases.append(case)

    fixture = {
        "schema_version": 1,
        "cohort_id": COHORT_ID,
        "source_arm": "online_rep01_candidate",
        "fixed_toolsandbox_timestamp": FIXED_TIMESTAMP,
        "timezone": FIXED_TIMEZONE,
        "normalizations": [
            "provider tool-call request IDs replaced with ordered fixture_call_NNN IDs",
            "SYSTEM rows excluded, including hidden user-simulator prompts and imports",
            "schema-fill null fields omitted; null-only snapshot markers retained",
        ],
        "shared": shared,
        "birth_facts": dict(sorted(all_birth_facts.items())),
        "cases": cases,
    }
    fixture_bytes = json.dumps(
        fixture, ensure_ascii=False, indent=2, sort_keys=True
    ).encode("utf-8") + b"\n"
    case_hashes = {case["id"]: _record_hash(case) for case in cases}
    coverage = sorted({tag for case in cases for tag in case["coverage"]})
    missing_coverage = sorted(REQUIRED_COVERAGE - set(coverage))
    if missing_coverage:
        raise ValueError(f"Fixture misses required coverage: {missing_coverage}")
    manifest = {
        "schema_version": 1,
        "cohort_id": COHORT_ID,
        "fixture_file": "full_trajectory_v1.json",
        "fixture_byte_count": len(fixture_bytes),
        "fixture_sha256": sha256_bytes(fixture_bytes),
        "canonical_case_hash": (
            "sha256(json.dumps(case, ensure_ascii=False, separators=(',', ':'), "
            "sort_keys=True).encode('utf-8'))"
        ),
        "case_sha256": case_hashes,
        "case_count": len(cases),
        "coverage": coverage,
        "required_coverage": sorted(REQUIRED_COVERAGE),
        "source_files": dict(sorted(source_files.items())),
        "privacy": {
            "credentials_copied": False,
            "mutable_registry_copied": False,
            "hidden_user_simulator_prompts_copied": False,
            "absolute_paths_copied": False,
            "benchmark_records_are_synthetic": True,
        },
        "known_boundary_gap": (
            "The frozen run preserved routed tool names and lifecycle decisions, "
            "but not the exact per-request OpenAI schema payload/prompt presented "
            "to the model. Exact actor schema/prompt equivalence is therefore "
            "covered by the separate deterministic actor probe, not reconstructed "
            "from these historical artifacts."
        ),
    }
    return fixture, manifest


def _validate_relative_sources(manifest: dict[str, Any]) -> None:
    for raw in manifest.get("source_files", {}):
        path = Path(str(raw))
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Manifest contains unsafe source path: {raw}")


def load_verified_fixture(
    fixture_path: Path = DEFAULT_FIXTURE,
    manifest_path: Path = DEFAULT_MANIFEST,
    *,
    source_root: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the checked corpus and fail closed on any content-hash mismatch."""

    fixture_bytes = fixture_path.read_bytes()
    manifest = _read_json(manifest_path)
    expected_sha = str(manifest["fixture_sha256"])
    observed_sha = sha256_bytes(fixture_bytes)
    if observed_sha != expected_sha:
        raise ValueError(
            f"Trajectory fixture hash mismatch: {observed_sha} != {expected_sha}"
        )
    if len(fixture_bytes) != int(manifest["fixture_byte_count"]):
        raise ValueError("Trajectory fixture byte count mismatch")
    fixture = json.loads(fixture_bytes)
    if fixture.get("schema_version") != 1 or manifest.get("schema_version") != 1:
        raise ValueError("Unsupported trajectory fixture schema")
    cases = fixture.get("cases")
    if not isinstance(cases, list) or len(cases) != int(manifest["case_count"]):
        raise ValueError("Trajectory fixture case count mismatch")
    expected_cases = manifest.get("case_sha256") or {}
    observed_cases = {str(case["id"]): _record_hash(case) for case in cases}
    if observed_cases != expected_cases:
        raise ValueError("Trajectory fixture case content hash mismatch")
    coverage = {str(tag) for case in cases for tag in case.get("coverage", [])}
    missing = set(manifest.get("required_coverage") or []) - coverage
    if missing:
        raise ValueError(f"Trajectory fixture coverage missing: {sorted(missing)}")
    _validate_relative_sources(manifest)
    serialized = fixture_bytes.decode("utf-8")
    if "/Users/" in serialized or "OPENAI_API_KEY" in serialized:
        raise ValueError("Trajectory fixture contains an absolute path or credential key")
    if source_root is not None:
        source_root = source_root.expanduser().resolve()
        for relative, expected in manifest["source_files"].items():
            path = _source_path(source_root, relative)
            observed = {
                "byte_count": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            if observed != expected:
                raise ValueError(
                    f"Historical source drifted for {relative}: "
                    f"{observed!r} != {expected!r}"
                )
    return fixture, manifest


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--build",
        action="store_true",
        help="Rebuild the compact fixture from the frozen historical artifacts.",
    )
    args = parser.parse_args()
    if args.build:
        if args.source_root is None:
            parser.error("--build requires --source-root")
        fixture, manifest = build_fixture(args.source_root)
        _write_json(args.fixture, fixture)
        _write_json(args.manifest, manifest)
    fixture, manifest = load_verified_fixture(
        args.fixture,
        args.manifest,
        source_root=args.source_root,
    )
    print(
        json.dumps(
            {
                "status": "verified",
                "fixture_sha256": manifest["fixture_sha256"],
                "case_count": len(fixture["cases"]),
                "coverage": manifest["coverage"],
                "source_files_verified": (
                    len(manifest["source_files"])
                    if args.source_root is not None
                    else 0
                ),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
