#!/usr/bin/env python3
"""Gate SAGE token-reduction variants before scaling.

The gate compares a candidate SAGE run against a methodology-aligned reference
run over the same task names. It is intentionally conservative: a token-saving
variant should not scale unless it preserves quality and generated-tool use
while producing a material token reduction.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _comparison(run_root: Path) -> dict[str, Any]:
    return _read_json(run_root / "paired_comparison.json")


def _candidate_dir(run_root: Path) -> Path:
    comparison = _comparison(run_root)
    return Path(comparison["candidate"]["run_dir"])


def _comparison_rows_by_name(run_root: Path) -> dict[str, dict[str, Any]]:
    comparison = _comparison(run_root)
    rows = comparison.get("deltas") or []
    return {str(row.get("scenario")): row for row in rows}


def _rows_by_name(run_root: Path) -> dict[str, dict[str, Any]]:
    candidate_dir = _candidate_dir(run_root)
    rows = _read_json(candidate_dir / "result_summary.json")["per_scenario_results"]
    return {str(row.get("name") or row.get("scenario")): row for row in rows}


def _selection_by_name(run_root: Path) -> dict[str, dict[str, Any]]:
    candidate_dir = _candidate_dir(run_root)
    path = candidate_dir / "selection_trace.jsonl"
    if not path.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out[str(row.get("scenario"))] = row
    return out


def _mean(rows: list[dict[str, Any]], key: str) -> float:
    values = [float(row.get(key) or 0.0) for row in rows]
    return sum(values) / len(values) if values else 0.0


def _sum_int(rows: list[dict[str, Any]], key: str) -> int:
    return sum(int(row.get(key) or 0) for row in rows)


def _candidate_tokens(row: dict[str, Any]) -> int:
    return int(
        row.get("candidate_llm_total_tokens") or row.get("llm_total_tokens") or 0
    )


def _called_generated_count(
    selection: dict[str, dict[str, Any]], names: set[str]
) -> int:
    count = 0
    for name in names:
        row = selection.get(name) or {}
        if int(row.get("called_generated_tool_count") or 0) > 0:
            count += 1
    return count


def evaluate(
    *,
    reference_run: Path,
    candidate_run: Path,
    min_token_reduction_pct: float,
    max_score_drop: float,
    max_outcome_drop: float,
    min_called_tool_ratio: float,
    min_scenario_count: int,
) -> dict[str, Any]:
    reference_rows_by_name = _comparison_rows_by_name(reference_run) or _rows_by_name(
        reference_run
    )
    candidate_rows_by_name = _comparison_rows_by_name(candidate_run) or _rows_by_name(
        candidate_run
    )
    common_names = set(reference_rows_by_name) & set(candidate_rows_by_name)
    if min_scenario_count:
        common_names = set(sorted(common_names)[: len(common_names)])

    reference_rows = [reference_rows_by_name[name] for name in sorted(common_names)]
    candidate_rows = [candidate_rows_by_name[name] for name in sorted(common_names)]

    reference_comparison = _comparison(reference_run)
    candidate_comparison = _comparison(candidate_run)
    full_completed_comparison = (
        len(common_names)
        == int(reference_comparison.get("scenario_count") or 0)
        == int(candidate_comparison.get("scenario_count") or 0)
    )

    if full_completed_comparison:
        reference_tokens = int(
            reference_comparison.get("candidate", {}).get("llm_total_tokens") or 0
        )
        candidate_tokens = int(
            candidate_comparison.get("candidate", {}).get("llm_total_tokens") or 0
        )
    else:
        reference_tokens = sum(_candidate_tokens(row) for row in reference_rows)
        candidate_tokens = sum(_candidate_tokens(row) for row in candidate_rows)
    token_reduction_pct = (
        (reference_tokens - candidate_tokens) / reference_tokens * 100.0
        if reference_tokens
        else 0.0
    )

    if full_completed_comparison:
        reference_score = float(
            reference_comparison.get("candidate_mean_similarity") or 0.0
        )
        candidate_score = float(
            candidate_comparison.get("candidate_mean_similarity") or 0.0
        )
        reference_outcome = float(
            reference_comparison.get("candidate_mean_outcome_similarity") or 0.0
        )
        candidate_outcome = float(
            candidate_comparison.get("candidate_mean_outcome_similarity") or 0.0
        )
    else:
        reference_score = _mean(reference_rows, "candidate_similarity")
        candidate_score = _mean(candidate_rows, "candidate_similarity")
        reference_outcome = _mean(reference_rows, "candidate_outcome_similarity")
        candidate_outcome = _mean(candidate_rows, "candidate_outcome_similarity")

    reference_selection = _selection_by_name(reference_run)
    candidate_selection = _selection_by_name(candidate_run)
    reference_called = _called_generated_count(reference_selection, common_names)
    candidate_called = _called_generated_count(candidate_selection, common_names)
    called_ratio = candidate_called / reference_called if reference_called else 1.0

    failures: list[str] = []
    if len(common_names) < min_scenario_count:
        failures.append(
            f"scenario_count_below_minimum:{len(common_names)}<{min_scenario_count}"
        )
    if token_reduction_pct < min_token_reduction_pct:
        failures.append(
            f"token_reduction_below_threshold:{token_reduction_pct:.2f}%"
            f"<{min_token_reduction_pct:.2f}%"
        )
    if candidate_score < reference_score - max_score_drop:
        failures.append(
            f"score_regression:{candidate_score:.6f}<"
            f"{reference_score - max_score_drop:.6f}"
        )
    if candidate_outcome < reference_outcome - max_outcome_drop:
        failures.append(
            f"outcome_regression:{candidate_outcome:.6f}<"
            f"{reference_outcome - max_outcome_drop:.6f}"
        )
    if called_ratio < min_called_tool_ratio:
        failures.append(
            f"generated_tool_call_ratio_below_threshold:{called_ratio:.3f}<"
            f"{min_called_tool_ratio:.3f}"
        )

    return {
        "gate_passed": not failures,
        "failures": failures,
        "scenario_count": len(common_names),
        "reference_run": str(reference_run),
        "candidate_run": str(candidate_run),
        "reference_sage_tokens": reference_tokens,
        "candidate_sage_tokens": candidate_tokens,
        "token_reduction_pct": token_reduction_pct,
        "reference_sage_score": reference_score,
        "candidate_sage_score": candidate_score,
        "score_delta_vs_reference": candidate_score - reference_score,
        "reference_sage_outcome": reference_outcome,
        "candidate_sage_outcome": candidate_outcome,
        "outcome_delta_vs_reference": candidate_outcome - reference_outcome,
        "reference_generated_tool_called_scenarios": reference_called,
        "candidate_generated_tool_called_scenarios": candidate_called,
        "generated_tool_call_ratio": called_ratio,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-run", type=Path, required=True)
    parser.add_argument("--candidate-run", type=Path, required=True)
    parser.add_argument("--min-token-reduction-pct", type=float, default=30.0)
    parser.add_argument("--max-score-drop", type=float, default=0.0)
    parser.add_argument("--max-outcome-drop", type=float, default=0.0)
    parser.add_argument("--min-called-tool-ratio", type=float, default=0.95)
    parser.add_argument("--min-scenario-count", type=int, default=60)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = evaluate(
        reference_run=args.reference_run,
        candidate_run=args.candidate_run,
        min_token_reduction_pct=args.min_token_reduction_pct,
        max_score_drop=args.max_score_drop,
        max_outcome_drop=args.max_outcome_drop,
        min_called_tool_ratio=args.min_called_tool_ratio,
        min_scenario_count=args.min_scenario_count,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        status = "PASS" if result["gate_passed"] else "FAIL"
        print(f"SAGE token-reduction gate: {status}")
        print(
            "Tokens: "
            f"{result['reference_sage_tokens']} -> {result['candidate_sage_tokens']} "
            f"({result['token_reduction_pct']:+.2f}%)"
        )
        print(
            "Score: "
            f"{result['reference_sage_score']:.6f} -> "
            f"{result['candidate_sage_score']:.6f} "
            f"({result['score_delta_vs_reference']:+.6f})"
        )
        print(
            "Outcome: "
            f"{result['reference_sage_outcome']:.6f} -> "
            f"{result['candidate_sage_outcome']:.6f} "
            f"({result['outcome_delta_vs_reference']:+.6f})"
        )
        print(
            "Generated-tool-called scenarios: "
            f"{result['reference_generated_tool_called_scenarios']} -> "
            f"{result['candidate_generated_tool_called_scenarios']} "
            f"(ratio {result['generated_tool_call_ratio']:.3f})"
        )
        if result["failures"]:
            print("Failures:")
            for failure in result["failures"]:
                print(f"- {failure}")
    return 0 if result["gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
