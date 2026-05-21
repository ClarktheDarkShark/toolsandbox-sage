"""Audit standalone SAGE dashboard exports for live baseline-vs-SAGE runs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dirs", nargs="+", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/sage_agent_standalone/run_audit_latest.json"),
    )
    args = parser.parse_args()

    results = [_audit_run(path) for path in args.run_dirs]
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runs": results,
        "passed": all(item["passed"] for item in results),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if not payload["passed"]:
        raise SystemExit(1)


def _audit_run(run_dir: Path) -> dict[str, Any]:
    data_path = run_dir / "dashboard" / "task_compare_data.json"
    html_paths = [
        run_dir / "dashboard" / "task_compare.html",
        run_dir / "dashboard" / "index.html",
    ]
    issues: list[str] = []
    if not data_path.exists():
        return {
            "run_dir": str(run_dir),
            "passed": False,
            "issues": [f"missing dashboard data: {data_path}"],
        }
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    summary = payload.get("summary") or {}
    baseline = payload.get("baseline") or {}
    metadata = payload.get("run_metadata") or {}
    registry = payload.get("registry") or {}
    events = summary.get("events") or []
    baseline_results = baseline.get("results") or []

    _require_dict("summary", summary, issues)
    _require_dict("baseline", baseline, issues)
    _require_dict("run_metadata", metadata, issues)
    _require_dict("registry", registry, issues)
    for path in html_paths:
        if not path.exists():
            issues.append(f"missing dashboard html: {path}")
        elif "Task Compare" not in path.read_text(encoding="utf-8"):
            issues.append(f"dashboard html lacks Task Compare marker: {path}")

    if not summary.get("environment"):
        issues.append("summary.environment missing")
    if not summary.get("model"):
        issues.append("summary.model missing")
    if baseline.get("comparison_valid") is not True:
        issues.append("baseline.comparison_valid is not true")
    if not str(baseline.get("policy", "")).startswith("llm_visible_artifact_baseline"):
        issues.append("baseline policy is not the live visible-artifact LLM baseline")
    requested = metadata.get("requested_limit")
    baseline_seen = int(baseline.get("tasks_seen") or 0)
    sage_seen = int(summary.get("tasks_seen") or 0)
    if requested is not None and baseline_seen != int(requested):
        issues.append(f"baseline tasks_seen {baseline_seen} != requested {requested}")
    if requested is not None and sage_seen != int(requested):
        issues.append(f"SAGE tasks_seen {sage_seen} != requested {requested}")
    if baseline_seen != len(baseline_results):
        issues.append("baseline tasks_seen does not match exported baseline results")

    baseline_task_ids = {
        str(item.get("task_id"))
        for item in baseline_results
        if item.get("task_id") is not None
    }
    sage_task_ids = {
        str(event.get("task_id"))
        for event in events
        if event.get("event") in {"task", "birth_task_retry", "refined_tool_task_retry"}
        and event.get("task_id") is not None
    }
    if baseline_task_ids != sage_task_ids:
        issues.append(
            f"baseline/SAGE task id mismatch: baseline={len(baseline_task_ids)} "
            f"SAGE={len(sage_task_ids)}"
        )
    for item in baseline_results:
        _require_transaction("baseline", item, issues)
        if item.get("error"):
            issues.append(
                f"baseline task {item.get('task_id')} has error: {item.get('error')}"
            )
    final_sage_by_task = _final_sage_records(events)
    for task_id, item in final_sage_by_task.items():
        _require_transaction(f"SAGE:{task_id}", item, issues)
        if item.get("error"):
            issues.append(f"SAGE task {task_id} has error: {item.get('error')}")

    text = data_path.read_text(encoding="utf-8").lower()
    rate_limit_mentions = text.count("rate limit")
    timeout_mentions = text.count("timeout")
    if rate_limit_mentions:
        issues.append(
            f"rate-limit text appears in dashboard data {rate_limit_mentions} times"
        )

    return {
        "run_dir": str(run_dir),
        "passed": not issues,
        "issues": issues,
        "environment": summary.get("environment"),
        "model": summary.get("model"),
        "requested_limit": requested,
        "baseline_policy": baseline.get("policy"),
        "baseline_tasks_seen": baseline_seen,
        "baseline_tasks_succeeded": baseline.get("tasks_succeeded"),
        "sage_tasks_seen": sage_seen,
        "sage_tasks_succeeded": summary.get("tasks_succeeded"),
        "tools_born": summary.get("tools_born"),
        "tools_reused": summary.get("tools_reused"),
        "integrity_passed": summary.get("integrity_passed"),
        "real_task_generator_used": metadata.get("real_task_generator_used"),
        "real_submission_server_used": metadata.get("real_submission_server_used"),
        "real_poc_verifier_used": metadata.get("real_poc_verifier_used"),
        "official_success_verification": metadata.get("official_success_verification"),
        "rate_limit_mentions": rate_limit_mentions,
        "timeout_mentions": timeout_mentions,
        "baseline_error_count": sum(
            1 for item in baseline_results if item.get("error")
        ),
        "sage_error_count": sum(
            1 for item in final_sage_by_task.values() if item.get("error")
        ),
    }


def _require_dict(name: str, value: Any, issues: list[str]) -> None:
    if not isinstance(value, dict):
        issues.append(f"{name} is not an object")


def _require_transaction(label: str, item: dict[str, Any], issues: list[str]) -> None:
    transcript = item.get("transcript") or []
    artifacts = item.get("artifacts") or {}
    if not transcript:
        issues.append(f"{label} missing transcript")
    if not isinstance(artifacts, dict):
        issues.append(f"{label} artifacts is not an object")
    if "success" not in item or "score" not in item or "outcome_score" not in item:
        issues.append(f"{label} missing score fields")


def _final_sage_records(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("event") not in {
            "task",
            "birth_task_retry",
            "refined_tool_task_retry",
        }:
            continue
        task_id = str(event.get("task_id"))
        if not task_id:
            continue
        if event.get("success") is True:
            records[task_id] = event
        else:
            records.setdefault(task_id, event)
    return records


if __name__ == "__main__":
    main()
