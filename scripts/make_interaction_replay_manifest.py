#!/usr/bin/env python3
"""Build a small replay manifest from collected missed-opportunity examples."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from sage_ts.config.splits import ScenarioRecord, scenario_records
from sage_ts.evaluation.task_strata import base_task_family, classify_task_strata


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _record_lookup() -> dict[str, ScenarioRecord]:
    return {record.name: record for record in scenario_records()}


def _example_matches(row: dict[str, Any], candidate_tool: str) -> bool:
    suspected = str(row.get("suspected_missed_tool_opportunity") or "")
    return suspected == candidate_tool


def build_manifest(
    *,
    examples_path: Path,
    candidate_tool: str,
    count: int,
    split_name: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    examples = [
        row
        for row in _load_jsonl(examples_path)
        if _example_matches(row, candidate_tool)
    ][:count]
    if len(examples) < count:
        raise ValueError(
            f"Only found {len(examples)} examples for {candidate_tool}; requested {count}"
        )
    records = _record_lookup()
    selected: list[ScenarioRecord] = []
    missing: list[str] = []
    for example in examples:
        name = str(example.get("scenario_name"))
        record = records.get(name)
        if record is None:
            missing.append(name)
            continue
        selected.append(record)
    if missing:
        raise ValueError(
            f"Examples not found in ToolSandbox scenario records: {missing}"
        )

    family_counts = Counter(base_task_family(record.name) for record in selected)
    strata_counts: Counter[str] = Counter()
    for record in selected:
        strata_counts.update(classify_task_strata(record.name, record.categories))
    manifest = {
        "manifest_type": "interaction_replay_discovery",
        "candidate_tool": candidate_tool,
        "strategy": (
            "Small non-test replay cohort built from collected prior-run examples. "
            "Use for adequacy/birth/adoption diagnostics only, not broad claims."
        ),
        "source_examples": str(examples_path),
        "splits": {split_name: [record.to_json() for record in selected]},
        "split_sizes": {split_name: len(selected)},
    }
    report = {
        "label": "interaction replay",
        "candidate_tool": candidate_tool,
        "scenario_count": len(selected),
        "source_examples": [
            {
                "example_id": example.get("example_id"),
                "scenario_name": example.get("scenario_name"),
                "source_run": example.get("source_run"),
                "suspected_missed_tool_opportunity": example.get(
                    "suspected_missed_tool_opportunity"
                ),
                "categories": example.get("categories", []),
            }
            for example in examples
        ],
        "family_counts": dict(family_counts.most_common()),
        "strata_counts": dict(strata_counts.most_common()),
        "decision_use": "diagnostic_replay_only",
        "warnings": [
            "small_replay_not_claim_grade",
            "prior_run_examples_not_hidden_gold",
        ],
    }
    return manifest, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--examples",
        type=Path,
        default=Path("artifacts/summaries/interaction_examples.jsonl"),
    )
    parser.add_argument("--candidate-tool", required=True)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--split-name", default="transfer_40")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report-output", required=True, type=Path)
    args = parser.parse_args()

    manifest, report = build_manifest(
        examples_path=args.examples,
        candidate_tool=args.candidate_tool,
        count=args.count,
        split_name=args.split_name,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n")
    args.report_output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "manifest": str(args.output),
                "cohort_diversity_report": str(args.report_output),
                "candidate_tool": args.candidate_tool,
                "scenario_count": report["scenario_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
