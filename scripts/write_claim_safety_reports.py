#!/usr/bin/env python3
# mypy: ignore-errors
"""Write claim-safety reports for a SAGE registry and prior run artifacts.

This script is intentionally read-only with respect to benchmark outputs. It
turns the current registry/validation safeguards into durable JSON artifacts
that can be inspected before claim-grade portfolio runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

EVENT_KEYWORDS = (
    "adequacy",
    "inadequacy",
    "tool_birth",
    "birth",
    "validation",
    "registry",
    "gate_",
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _registry_manifest_path(registry_dir: Path) -> Path:
    if registry_dir.name == "registry_manifest.json":
        return registry_dir
    return registry_dir / "registry_manifest.json"


def _tool_name(entry_name: str, entry: dict[str, Any]) -> str:
    return (
        entry.get("tool", {})
        .get("spec", {})
        .get("tool_name", entry.get("tool_name", entry_name))
    )


def _validation_reasons(entry: dict[str, Any]) -> list[str]:
    validation = entry.get("validation", {})
    reasons: list[str] = []
    if entry.get("retired") is True:
        reasons.append("retired")
    if validation.get("accepted") is not True:
        reasons.append("validation_not_accepted")
    if int(validation.get("held_out_check_count") or 0) <= 0:
        reasons.append("missing_semantic_held_out_checks")
    if validation.get("runtime_smoke_passed") is not True:
        reasons.append("missing_runtime_smoke_pass")
    return reasons


def build_registry_quarantine_report(registry_manifest: Path) -> dict[str, Any]:
    payload = _read_json(registry_manifest)
    tools = payload.get("tools", {})
    if not isinstance(tools, dict):
        raise ValueError(f"{registry_manifest} has non-dict 'tools' payload")

    accepted: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()

    for entry_name, entry in sorted(tools.items()):
        if not isinstance(entry, dict):
            continue
        validation = entry.get("validation", {})
        spec = entry.get("tool", {}).get("spec", {})
        reasons = _validation_reasons(entry)
        row = {
            "tool_name": _tool_name(entry_name, entry),
            "registry_key": entry_name,
            "family": spec.get("family"),
            "birth_scenario": entry.get("birth_scenario"),
            "accepted_at": entry.get("accepted_at"),
            "version": entry.get("version"),
            "retired": bool(entry.get("retired", False)),
            "code_hash": entry.get("code_hash"),
            "validation": {
                "accepted": validation.get("accepted"),
                "source_example_count": int(
                    validation.get("source_example_count") or 0
                ),
                "held_out_check_count": int(
                    validation.get("held_out_check_count") or 0
                ),
                "runtime_smoke_passed": bool(
                    validation.get("runtime_smoke_passed", False)
                ),
                "errors": list(validation.get("errors") or []),
            },
            "quarantine_reasons": reasons,
        }
        family_counts[str(row["family"])] += 1
        if reasons:
            quarantined.append(row)
            reason_counts.update(reasons)
        else:
            accepted.append(row)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "registry_manifest": str(registry_manifest),
        "registry_manifest_sha256": _sha256_file(registry_manifest),
        "summary": {
            "tool_count": len(tools),
            "claim_safe_tool_count": len(accepted),
            "quarantined_tool_count": len(quarantined),
            "quarantine_reason_counts": dict(sorted(reason_counts.items())),
            "family_counts": dict(sorted(family_counts.items())),
        },
        "policy": {
            "inject_only_claim_safe_tools": True,
            "claim_safe_definition": {
                "validation.accepted": True,
                "validation.held_out_check_count": "> 0",
                "validation.runtime_smoke_passed": True,
                "retired": False,
            },
            "quarantined_tools_are_not_injected": True,
        },
        "claim_safe_tools": accepted,
        "quarantined_tools": quarantined,
    }


def build_validation_policy_report(repo_root: Path) -> dict[str, Any]:
    files = {
        "registry_manifest": repo_root / "src/sage_ts/registry/manifest.py",
        "toolsandbox_integration": repo_root
        / "src/sage_ts/runtime/toolsandbox_integration.py",
        "tool_invoker": repo_root / "src/sage_ts/runtime/tool_invoker.py",
        "sandbox_validator": repo_root / "src/sage_ts/validation/sandbox_validator.py",
        "schema_check": repo_root / "src/sage_ts/validation/schema_check.py",
        "protocol_runner": repo_root / "scripts/run_sage_protocol.py",
        "makefile": repo_root / "Makefile",
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": {
            "registry_injection_requires_current_validation_proof": True,
            "current_validation_proof_requires": {
                "validation.accepted": True,
                "validation.held_out_check_count": "> 0",
                "validation.runtime_smoke_passed": True,
            },
            "semantic_held_out_validation_required": True,
            "single_example_acceptance_allowed": False,
            "deterministic_replay_required": True,
            "json_serializable_output_required": True,
            "toolsandbox_runtime_smoke_required": True,
            "generated_function_name_must_match_spec": True,
            "fallback_to_first_function_allowed": False,
            "frozen_transfer_generation_forced_off": True,
            "cohort_preflight_required_for_protocol_runs": True,
            "external_contamination_blocked_by_default": True,
            "outcome_score_secondary_only": True,
        },
        "source_files": {
            name: {
                "path": str(path),
                "exists": path.exists(),
                "sha256": _sha256_file(path) if path.exists() else None,
            }
            for name, path in files.items()
        },
    }


def _iter_event_files(run_roots: Iterable[Path]) -> Iterable[Path]:
    names = {
        "sage_run_events.jsonl",
        "tool_birth_events.jsonl",
        "selection_trace.jsonl",
        "adequacy_gate_events.jsonl",
    }
    for root in run_roots:
        if not root.exists():
            continue
        if root.is_file() and root.name.endswith(".jsonl"):
            yield root
            continue
        for path in root.rglob("*.jsonl"):
            if path.name in names or "event" in path.name:
                yield path


def _event_matches(payload: dict[str, Any]) -> bool:
    event_type = str(
        payload.get("event")
        or payload.get("event_type")
        or payload.get("type")
        or payload.get("name")
        or ""
    ).lower()
    if any(keyword in event_type for keyword in EVENT_KEYWORDS):
        return True
    text = json.dumps(payload, sort_keys=True).lower()
    return any(keyword in text for keyword in EVENT_KEYWORDS)


def write_adequacy_events(run_roots: list[Path], output_path: Path) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    event_count = 0
    file_count = 0
    event_type_counts: Counter[str] = Counter()
    sources: list[str] = []

    with output_path.open("w") as out:
        for event_file in sorted(set(_iter_event_files(run_roots))):
            file_count += 1
            sources.append(str(event_file))
            for line_number, line in enumerate(event_file.read_text().splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict) or not _event_matches(payload):
                    continue
                event_type = str(
                    payload.get("event")
                    or payload.get("event_type")
                    or payload.get("type")
                    or payload.get("name")
                    or "unknown"
                )
                event_type_counts[event_type] += 1
                event_count += 1
                payload = dict(payload)
                payload.setdefault("_source_file", str(event_file))
                payload.setdefault("_source_line", line_number)
                out.write(json.dumps(payload, sort_keys=True) + "\n")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output": str(output_path),
        "run_roots": [str(path) for path in run_roots],
        "scanned_event_files": sources,
        "scanned_event_file_count": file_count,
        "matched_event_count": event_count,
        "event_type_counts": dict(sorted(event_type_counts.items())),
    }


def _copy_to_summary_root(path: Path, summary_root: Path) -> None:
    summary_root.mkdir(parents=True, exist_ok=True)
    (summary_root / path.name).write_text(path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry-dir",
        required=True,
        type=Path,
        help="Registry directory or registry_manifest.json path to audit.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory for claim-safety reports.",
    )
    parser.add_argument(
        "--run-root",
        action="append",
        default=[],
        type=Path,
        help="Prior run root to scan for adequacy/birth/validation events.",
    )
    parser.add_argument(
        "--summary-root",
        type=Path,
        default=Path("artifacts/summaries"),
        help="Directory to receive convenience copies with canonical filenames.",
    )
    args = parser.parse_args()

    repo_root = Path.cwd()
    registry_manifest = _registry_manifest_path(args.registry_dir)
    if not registry_manifest.exists():
        raise FileNotFoundError(registry_manifest)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    quarantine_report = build_registry_quarantine_report(registry_manifest)
    validation_policy = build_validation_policy_report(repo_root)
    adequacy_summary = write_adequacy_events(
        args.run_root,
        args.output_dir / "adequacy_gate_events.jsonl",
    )

    reports = {
        "registry_quarantine_report.json": quarantine_report,
        "validation_policy_report.json": validation_policy,
        "adequacy_gate_event_summary.json": adequacy_summary,
    }
    for filename, payload in reports.items():
        _write_json(args.output_dir / filename, payload)

    claim_safety_index = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "registry_manifest": str(registry_manifest),
        "reports": {filename: str(args.output_dir / filename) for filename in reports}
        | {
            "adequacy_gate_events.jsonl": str(
                args.output_dir / "adequacy_gate_events.jsonl"
            )
        },
        "claim_safe_tool_count": quarantine_report["summary"]["claim_safe_tool_count"],
        "quarantined_tool_count": quarantine_report["summary"][
            "quarantined_tool_count"
        ],
        "matched_adequacy_event_count": adequacy_summary["matched_event_count"],
    }
    _write_json(args.output_dir / "claim_safety_index.json", claim_safety_index)

    for path in (
        args.output_dir / "registry_quarantine_report.json",
        args.output_dir / "validation_policy_report.json",
        args.output_dir / "adequacy_gate_events.jsonl",
    ):
        _copy_to_summary_root(path, args.summary_root)

    print(json.dumps(claim_safety_index, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
