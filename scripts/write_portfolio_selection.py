#!/usr/bin/env python3
# mypy: ignore-errors
"""Select the next claim portfolio from missed-opportunity and audit evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_INITIAL_PORTFOLIO = (
    "relative_day_time_to_timestamp",
    "days_between_timestamps",
    "select_record_by_timestamp_extreme",
    "prepare_reminder_creation_args",
    "select_contact_or_message_by_constraints",
)


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _registry_tools(registry_manifest: Path) -> dict[str, dict[str, Any]]:
    payload = _read_json(registry_manifest, {"tools": {}})
    tools = payload.get("tools", {}) if isinstance(payload, dict) else {}
    return tools if isinstance(tools, dict) else {}


def _quarantine_lookup(quarantine_report: Path) -> dict[str, dict[str, Any]]:
    payload = _read_json(quarantine_report, {})
    rows = []
    if isinstance(payload, dict):
        rows.extend(payload.get("claim_safe_tools") or [])
        rows.extend(payload.get("quarantined_tools") or [])
    return {
        str(row.get("tool_name")): row
        for row in rows
        if isinstance(row, dict) and row.get("tool_name")
    }


def _audit_lookup(audit_paths: list[Path]) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for path in audit_paths:
        payload = _read_json(path, {})
        if not isinstance(payload, dict):
            continue
        tools = payload.get("tools", {})
        if not isinstance(tools, dict):
            continue
        for tool_name, row in tools.items():
            if not isinstance(row, dict):
                continue
            target = merged.setdefault(
                tool_name,
                {
                    "visible_scenarios": 0,
                    "called_scenarios": 0,
                    "gains_when_called": 0,
                    "regressions_when_called": 0,
                    "exact_success_flips_when_called": 0,
                    "exact_regressions_when_called": 0,
                    "canonical_deltas": [],
                    "outcome_deltas": [],
                    "runs": set(),
                },
            )
            target["visible_scenarios"] += int(row.get("visible_scenarios") or 0)
            target["called_scenarios"] += int(row.get("called_scenarios") or 0)
            target["gains_when_called"] += int(row.get("gains_when_called") or 0)
            target["regressions_when_called"] += int(
                row.get("regressions_when_called") or 0
            )
            target["exact_success_flips_when_called"] += int(
                row.get("exact_success_flips_when_called") or 0
            )
            target["exact_regressions_when_called"] += int(
                row.get("exact_regressions_when_called") or 0
            )
            if row.get("mean_canonical_delta_when_called") is not None:
                target["canonical_deltas"].append(
                    float(row["mean_canonical_delta_when_called"])
                )
            if row.get("mean_outcome_delta_when_called") is not None:
                target["outcome_deltas"].append(
                    float(row["mean_outcome_delta_when_called"])
                )
            for run in row.get("runs") or []:
                target["runs"].add(str(run))

    for row in merged.values():
        canonical = row.pop("canonical_deltas")
        outcome = row.pop("outcome_deltas")
        row["mean_canonical_delta_when_called"] = (
            sum(canonical) / len(canonical) if canonical else None
        )
        row["mean_outcome_delta_when_called"] = (
            sum(outcome) / len(outcome) if outcome else None
        )
        row["runs"] = sorted(row["runs"])
    return merged


def _missed_lookup(missed_candidates: Path) -> dict[str, dict[str, Any]]:
    rows = _read_json(missed_candidates, [])
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("candidate_tool")): row
        for row in rows
        if isinstance(row, dict) and row.get("candidate_tool")
    }


def _status_for(
    tool_name: str,
    *,
    registry_tools: dict[str, dict[str, Any]],
    quarantine: dict[str, dict[str, Any]],
    audit: dict[str, dict[str, Any]],
    missed: dict[str, dict[str, Any]],
) -> str:
    if tool_name in registry_tools and not quarantine.get(tool_name, {}).get(
        "quarantine_reasons"
    ):
        row = audit.get(tool_name, {})
        called = int(row.get("called_scenarios") or 0)
        regressions = int(row.get("regressions_when_called") or 0)
        gains = int(row.get("gains_when_called") or 0)
        mean_delta = row.get("mean_canonical_delta_when_called")
        if (
            called > 0
            and gains >= regressions
            and isinstance(mean_delta, (int, float))
            and float(mean_delta) > 0
        ):
            return "portfolio_ready"
        return "validated_but_needs_adoption_evidence"
    if tool_name in registry_tools:
        return "quarantined_or_legacy_diagnostic"
    if tool_name in missed:
        return "candidate_requires_birth_or_update"
    return "candidate_requires_evidence"


def _decision_for(tool_name: str, status: str, audit: dict[str, Any]) -> str:
    if status == "portfolio_ready":
        regressions = int(audit.get("regressions_when_called") or 0)
        called = int(audit.get("called_scenarios") or 0)
        if regressions > 0:
            return "keep_with_tight_routing"
        if called >= 5:
            return "keep_for_portfolio"
        return "keep_but_confirm_on_focused_cohort"
    if status == "validated_but_needs_adoption_evidence":
        return "update_routing_or_schema_before_claim"
    if status == "quarantined_or_legacy_diagnostic":
        return "quarantine_until_current_validation_proof"
    return "run_interaction_replay_then_birth_or_update"


def build_portfolio_selection(
    *,
    registry_manifest: Path,
    quarantine_report: Path,
    missed_candidates_path: Path,
    audit_paths: list[Path],
) -> dict[str, Any]:
    registry_tools = _registry_tools(registry_manifest)
    quarantine = _quarantine_lookup(quarantine_report)
    audit = _audit_lookup(audit_paths)
    missed = _missed_lookup(missed_candidates_path)

    candidate_names = list(DEFAULT_INITIAL_PORTFOLIO)
    for name in (
        "next_service_tool_call",
        "recency_to_timestamp_bounds",
        "message_search_time_window",
        "normalize_stock_query_or_extract_symbol",
    ):
        if name in registry_tools or name in missed or name in audit:
            candidate_names.append(name)

    rows: list[dict[str, Any]] = []
    for tool_name in dict.fromkeys(candidate_names):
        status = _status_for(
            tool_name,
            registry_tools=registry_tools,
            quarantine=quarantine,
            audit=audit,
            missed=missed,
        )
        row = {
            "tool_name": tool_name,
            "status": status,
            "decision": _decision_for(tool_name, status, audit.get(tool_name, {})),
            "in_current_registry": tool_name in registry_tools,
            "claim_safe_validation": status
            in {"portfolio_ready", "validated_but_needs_adoption_evidence"},
            "missed_opportunity_evidence": missed.get(tool_name),
            "prior_run_audit": audit.get(tool_name),
            "validation_row": quarantine.get(tool_name),
        }
        if tool_name == "recency_to_timestamp_bounds":
            row["decision"] = "keep_only_with_tight_temporal_bound_routing"
        if tool_name == "next_service_tool_call":
            row["decision"] = "only_count_after_trace_compatible_runtime_evidence"
        if tool_name == "normalize_stock_query_or_extract_symbol":
            row["decision"] = "diagnostic_only_until_external_contamination_controlled"
        rows.append(row)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_policy": "Non-test missed-opportunity examples plus completed diagnostic run audits; no hidden gold answers used.",
        "registry_manifest": str(registry_manifest),
        "quarantine_report": str(quarantine_report),
        "missed_candidates": str(missed_candidates_path),
        "audit_paths": [str(path) for path in audit_paths],
        "portfolio_size_target": "3-5 tools",
        "canonical_score_primary": True,
        "outcome_score_secondary_route_mismatch_check": True,
        "selected_initial_portfolio": [
            row for row in rows if row["tool_name"] in DEFAULT_INITIAL_PORTFOLIO
        ],
        "watchlist": [
            row for row in rows if row["tool_name"] not in DEFAULT_INITIAL_PORTFOLIO
        ],
        "next_evidence_loop": {
            "run_a": "4-8 interaction replay examples for candidate birth/adoption",
            "run_b": "12-20 focused value cohort with positive and negative applicability",
            "run_c": "frozen reuse with generation disabled and actual helper calls",
        },
    }


def write_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Tool Portfolio Candidates",
        "",
        "Canonical ToolSandbox score remains primary. Outcome score is a secondary route-mismatch sanity check.",
        "",
        "## Initial Portfolio",
    ]
    for row in payload["selected_initial_portfolio"]:
        audit = row.get("prior_run_audit") or {}
        lines.append(
            "- {tool}: {decision}; status={status}; called={called}; gains/regressions={gains}/{regs}; mean canonical delta when called={delta}; mean outcome delta when called={outcome}".format(
                tool=row["tool_name"],
                decision=row["decision"],
                status=row["status"],
                called=audit.get("called_scenarios"),
                gains=audit.get("gains_when_called"),
                regs=audit.get("regressions_when_called"),
                delta=audit.get("mean_canonical_delta_when_called"),
                outcome=audit.get("mean_outcome_delta_when_called"),
            )
        )
    lines.extend(["", "## Watchlist"])
    for row in payload["watchlist"]:
        lines.append(
            "- {tool}: {decision}; status={status}".format(
                tool=row["tool_name"],
                decision=row["decision"],
                status=row["status"],
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry-manifest",
        type=Path,
        default=Path("outputs/claim_portfolio_registry/registry_manifest.json"),
    )
    parser.add_argument(
        "--quarantine-report",
        type=Path,
        default=Path("artifacts/summaries/registry_quarantine_report.json"),
    )
    parser.add_argument(
        "--missed-candidates",
        type=Path,
        default=Path("artifacts/summaries/top_candidate_tools_from_examples.json"),
    )
    parser.add_argument("--audit", action="append", type=Path, default=[])
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/summaries/claim_portfolio_selection_20260501"),
    )
    parser.add_argument(
        "--summary-root",
        type=Path,
        default=Path("artifacts/summaries"),
    )
    args = parser.parse_args()

    audit_paths = args.audit or [
        Path(
            "artifacts/summaries/claim_portfolio_combined_20260501/top_tool_audit.json"
        ),
        Path(
            "artifacts/summaries/claim_portfolio_mixed60_frozen_20260501/top_tool_audit.json"
        ),
    ]
    payload = build_portfolio_selection(
        registry_manifest=args.registry_manifest,
        quarantine_report=args.quarantine_report,
        missed_candidates_path=args.missed_candidates,
        audit_paths=audit_paths,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.output_dir / "tool_portfolio_candidates.json", payload)
    (args.output_dir / "tool_portfolio_candidates.md").write_text(
        write_markdown(payload)
    )
    args.summary_root.mkdir(parents=True, exist_ok=True)
    (args.summary_root / "tool_portfolio_candidates.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    (args.summary_root / "tool_portfolio_candidates.md").write_text(
        write_markdown(payload)
    )
    print(
        json.dumps(
            {
                "output": str(args.output_dir / "tool_portfolio_candidates.json"),
                "initial_portfolio_count": len(payload["selected_initial_portfolio"]),
                "watchlist_count": len(payload["watchlist"]),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
