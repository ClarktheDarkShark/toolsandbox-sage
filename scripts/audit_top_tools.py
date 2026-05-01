#!/usr/bin/env python3
# mypy: ignore-errors
"""Audit retained/generated helper contribution across completed protocol runs."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ToolAudit:
    visible_count: int = 0
    shortlisted_count: int = 0
    called_count: int = 0
    attempted_count: int = 0
    visible_not_called_count: int = 0
    canonical_delta_when_called: list[float] = field(default_factory=list)
    outcome_delta_when_called: list[float] = field(default_factory=list)
    canonical_delta_when_visible_not_called: list[float] = field(default_factory=list)
    outcome_delta_when_visible_not_called: list[float] = field(default_factory=list)
    exact_success_flips_when_called: int = 0
    exact_regressions_when_called: int = 0
    gains_when_called: int = 0
    regressions_when_called: int = 0
    preserved_when_called: int = 0
    improper_reuse_cases: list[dict[str, Any]] = field(default_factory=list)
    visible_not_called_cases: list[dict[str, Any]] = field(default_factory=list)
    trace_mismatch_cases: list[dict[str, Any]] = field(default_factory=list)
    runs: set[str] = field(default_factory=set)

    def to_json(self) -> dict[str, Any]:
        return {
            "visible_scenarios": self.visible_count,
            "shortlisted_scenarios": self.shortlisted_count,
            "called_scenarios": self.called_count,
            "attempted_scenarios": self.attempted_count,
            "visible_not_called_scenarios": self.visible_not_called_count,
            "mean_canonical_delta_when_called": _mean(self.canonical_delta_when_called),
            "mean_outcome_delta_when_called": _mean(self.outcome_delta_when_called),
            "mean_canonical_delta_when_visible_not_called": _mean(
                self.canonical_delta_when_visible_not_called
            ),
            "mean_outcome_delta_when_visible_not_called": _mean(
                self.outcome_delta_when_visible_not_called
            ),
            "exact_success_flips_when_called": self.exact_success_flips_when_called,
            "exact_regressions_when_called": self.exact_regressions_when_called,
            "gains_when_called": self.gains_when_called,
            "regressions_when_called": self.regressions_when_called,
            "preserved_when_called": self.preserved_when_called,
            "improper_reuse_cases": self.improper_reuse_cases[:50],
            "visible_not_called_cases": self.visible_not_called_cases[:50],
            "trace_mismatch_cases": self.trace_mismatch_cases[:50],
            "runs": sorted(self.runs),
        }


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _candidate_run_dir(run_root: Path, comparison: dict[str, Any]) -> Path | None:
    candidate = comparison.get("candidate", {})
    raw = candidate.get("run_dir") if isinstance(candidate, dict) else None
    if isinstance(raw, str) and Path(raw).exists():
        return Path(raw)
    matches = sorted((run_root / "candidate").glob("*/result_summary.json"))
    return matches[-1].parent if matches else None


def _selection_rows(candidate_dir: Path | None) -> list[dict[str, Any]]:
    if candidate_dir is None:
        return []
    return _load_jsonl(candidate_dir / "scenario_tool_selection.jsonl")


def _birth_rows(candidate_dir: Path | None) -> list[dict[str, Any]]:
    if candidate_dir is None:
        return []
    return _load_jsonl(candidate_dir / "tool_birth_events.jsonl")


def _delta_by_scenario(comparison: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in comparison.get("deltas", []):
        if isinstance(row, dict) and isinstance(row.get("scenario"), str):
            result[str(row["scenario"])] = row
    return result


def _is_exact(value: Any) -> bool:
    return isinstance(value, (int, float)) and float(value) >= 0.999


def _trace_mismatch(row: dict[str, Any]) -> bool:
    candidate_score = row.get("candidate_similarity")
    outcome_score = row.get("candidate_outcome_similarity")
    if not isinstance(candidate_score, (int, float)) or not isinstance(
        outcome_score, (int, float)
    ):
        return False
    return float(candidate_score) < 0.999 and float(outcome_score) >= 0.999


def _update_tool(
    audit: ToolAudit,
    *,
    run_root: Path,
    scenario: str,
    delta: dict[str, Any],
    visible: bool,
    shortlisted: bool,
    attempted: bool,
    called: bool,
) -> None:
    canonical_delta = float(delta.get("delta", 0.0) or 0.0)
    outcome_delta = float(delta.get("outcome_delta", 0.0) or 0.0)
    audit.runs.add(str(run_root))
    if visible:
        audit.visible_count += 1
    if shortlisted:
        audit.shortlisted_count += 1
    if attempted:
        audit.attempted_count += 1
    if called:
        audit.called_count += 1
        audit.canonical_delta_when_called.append(canonical_delta)
        audit.outcome_delta_when_called.append(outcome_delta)
        if canonical_delta > 0:
            audit.gains_when_called += 1
        elif canonical_delta < 0:
            audit.regressions_when_called += 1
            audit.improper_reuse_cases.append(
                {"run_root": str(run_root), "scenario": scenario, **delta}
            )
        else:
            audit.preserved_when_called += 1
        if _is_exact(delta.get("candidate_similarity")) and not _is_exact(
            delta.get("control_similarity")
        ):
            audit.exact_success_flips_when_called += 1
        if _is_exact(delta.get("control_similarity")) and not _is_exact(
            delta.get("candidate_similarity")
        ):
            audit.exact_regressions_when_called += 1
        if _trace_mismatch(delta):
            audit.trace_mismatch_cases.append(
                {"run_root": str(run_root), "scenario": scenario, **delta}
            )
    elif visible:
        audit.visible_not_called_count += 1
        audit.canonical_delta_when_visible_not_called.append(canonical_delta)
        audit.outcome_delta_when_visible_not_called.append(outcome_delta)
        audit.visible_not_called_cases.append(
            {"run_root": str(run_root), "scenario": scenario, **delta}
        )


def audit_runs(run_roots: list[Path]) -> dict[str, Any]:
    tools: dict[str, ToolAudit] = defaultdict(ToolAudit)
    births: dict[str, list[dict[str, Any]]] = defaultdict(list)
    route_mismatches: list[dict[str, Any]] = []
    run_summaries: list[dict[str, Any]] = []

    for run_root in run_roots:
        comparison_path = run_root / "paired_comparison.json"
        if not comparison_path.exists():
            continue
        comparison = _load_json(comparison_path)
        candidate_dir = _candidate_run_dir(run_root, comparison)
        deltas = _delta_by_scenario(comparison)
        selection_rows = _selection_rows(candidate_dir)
        for row in _birth_rows(candidate_dir):
            tool_name = row.get("tool_name")
            if isinstance(tool_name, str):
                births[tool_name].append({"run_root": str(run_root), **row})

        for row in selection_rows:
            scenario = str(row.get("scenario", ""))
            delta = deltas.get(scenario, {"scenario": scenario})
            if _trace_mismatch(delta):
                route_mismatches.append({"run_root": str(run_root), **delta})
            visible_tools = set(row.get("generated_tools_visible") or [])
            shortlisted_tools = set(row.get("shortlisted_generated_tools") or [])
            attempted_tools = set(row.get("generated_tools_attempted") or [])
            called_tools = set(row.get("generated_tools_called") or [])
            for tool_name in sorted(
                visible_tools | shortlisted_tools | attempted_tools | called_tools
            ):
                _update_tool(
                    tools[tool_name],
                    run_root=run_root,
                    scenario=scenario,
                    delta=delta,
                    visible=tool_name in visible_tools,
                    shortlisted=tool_name in shortlisted_tools,
                    attempted=tool_name in attempted_tools,
                    called=tool_name in called_tools,
                )

        run_summaries.append(
            {
                "run_root": str(run_root),
                "scenario_count": comparison.get("scenario_count"),
                "control_mean_similarity": comparison.get("control_mean_similarity"),
                "candidate_mean_similarity": comparison.get(
                    "candidate_mean_similarity"
                ),
                "mean_similarity_delta": comparison.get("mean_similarity_delta"),
                "mean_outcome_similarity_delta": comparison.get(
                    "mean_outcome_similarity_delta"
                ),
                "exact_success_delta": comparison.get("exact_success_delta"),
                "gain_count": comparison.get("gain_count"),
                "regression_count": comparison.get("regression_count"),
            }
        )

    tool_payload = {name: audit.to_json() for name, audit in sorted(tools.items())}
    candidates = []
    for name, payload in tool_payload.items():
        called = int(payload["called_scenarios"])
        mean_delta = payload["mean_canonical_delta_when_called"]
        mean_outcome = payload["mean_outcome_delta_when_called"]
        regressions = int(payload["regressions_when_called"])
        gains = int(payload["gains_when_called"])
        accepted_births = [
            row
            for row in births.get(name, [])
            if row.get("accepted") is True
            and int(row.get("held_out_check_count") or 0) > 0
            and row.get("runtime_smoke_passed") is True
        ]
        decision = "suppress_or_retest"
        if called > 0 and regressions == 0 and (mean_delta or 0.0) >= 0:
            decision = "promote_candidate"
        elif called > 0 and gains > regressions and (mean_delta or 0.0) > 0:
            decision = "promote_with_routing_review"
        elif called > 0 and (mean_outcome or 0.0) > 0 and (mean_delta or 0.0) <= 0:
            decision = "trace_mismatch_review"
        candidates.append(
            {
                "tool_name": name,
                "decision": decision,
                "called_scenarios": called,
                "visible_scenarios": payload["visible_scenarios"],
                "mean_canonical_delta_when_called": mean_delta,
                "mean_outcome_delta_when_called": mean_outcome,
                "gains_when_called": gains,
                "regressions_when_called": regressions,
                "accepted_birth_evidence_count": len(accepted_births),
            }
        )

    return {
        "generated_at": datetime.now().isoformat(),
        "run_roots": [str(path) for path in run_roots],
        "run_summaries": run_summaries,
        "tools": tool_payload,
        "birth_evidence": dict(births),
        "route_mismatch_cases": route_mismatches,
        "portfolio_candidates": sorted(
            candidates,
            key=lambda row: (
                row["decision"].startswith("promote"),
                row["called_scenarios"],
                row["mean_canonical_delta_when_called"] or -999,
            ),
            reverse=True,
        ),
    }


def write_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# Top Tool Audit",
        "",
        "Canonical ToolSandbox score remains primary. Outcome score is reported as a secondary route-mismatch sanity check.",
        "",
        "## Runs",
    ]
    for run in audit["run_summaries"]:
        lines.append(
            "- {run_root}: delta {delta}, outcome {outcome}, exact {exact}, gains/regressions {gains}/{regs}".format(
                run_root=run["run_root"],
                delta=run.get("mean_similarity_delta"),
                outcome=run.get("mean_outcome_similarity_delta"),
                exact=run.get("exact_success_delta"),
                gains=run.get("gain_count"),
                regs=run.get("regression_count"),
            )
        )
    lines.extend(["", "## Portfolio Candidates"])
    for row in audit["portfolio_candidates"]:
        lines.append(
            "- {tool}: {decision}; called {called}; mean canonical delta {canon}; mean outcome delta {outcome}; gains/regressions {gains}/{regs}; accepted-birth evidence {births}".format(
                tool=row["tool_name"],
                decision=row["decision"],
                called=row["called_scenarios"],
                canon=row["mean_canonical_delta_when_called"],
                outcome=row["mean_outcome_delta_when_called"],
                gains=row["gains_when_called"],
                regs=row["regressions_when_called"],
                births=row["accepted_birth_evidence_count"],
            )
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", action="append", type=Path, default=[])
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/summaries"))
    args = parser.parse_args()
    if not args.run_root:
        args.run_root = sorted(
            path.parent for path in Path("outputs").glob("**/paired_comparison.json")
        )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    audit = audit_runs(args.run_root)
    (args.output_dir / "top_tool_audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_dir / "route_mismatch_report.json").write_text(
        json.dumps(audit["route_mismatch_cases"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "tool_portfolio_candidates.json").write_text(
        json.dumps(audit["portfolio_candidates"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "top_tool_audit.md").write_text(
        write_markdown(audit), encoding="utf-8"
    )
    print(args.output_dir / "top_tool_audit.json")


if __name__ == "__main__":
    main()
