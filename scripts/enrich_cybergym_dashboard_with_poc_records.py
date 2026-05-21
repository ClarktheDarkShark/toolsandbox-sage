#!/usr/bin/env python3
"""Backfill CyberGym PoC submission evidence into older standalone dashboards."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from sage_agent.dashboard import _dashboard_html


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()

    run_dir = args.run_dir
    data_path = run_dir / "dashboard" / "task_compare_data.json"
    db_path = run_dir / "server" / "poc.db"
    if not data_path.exists():
        raise FileNotFoundError(data_path)
    if not db_path.exists():
        raise FileNotFoundError(db_path)

    data = json.loads(data_path.read_text(encoding="utf-8"))
    records_by_task = _load_records(db_path)
    baseline_poc_ids = _baseline_poc_ids(data.get("baseline", {}))
    updated = 0

    for event in data.get("summary", {}).get("events", []):
        if event.get("event") != "task":
            continue
        if event.get("transcript") or event.get("artifacts", {}).get("attempts"):
            continue
        task_id = str(event.get("task_id", ""))
        rows = [
            row
            for row in records_by_task.get(task_id, [])
            if row["poc_id"] not in baseline_poc_ids.get(task_id, set())
        ]
        if not rows:
            continue
        attempts = [_record_to_attempt(index, row) for index, row in enumerate(rows)]
        event["transcript"] = [_attempt_summary(attempt) for attempt in attempts]
        event["artifacts"] = {"attempts": attempts}
        updated += 1

    data.setdefault("run_metadata", {})["dashboard_poc_record_backfill"] = (
        "SAGE transaction evidence was reconstructed from CyberGym server poc.db records for a historical run that predated normalized SAGE artifact export."
    )

    _write_dashboard(run_dir, data)
    print(f"backfilled_tasks={updated}")
    return 0


def _load_records(db_path: Path) -> dict[str, list[dict[str, Any]]]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        select id, agent_id, task_id, poc_id, poc_hash, poc_length,
               vul_exit_code, fix_exit_code, created_at
        from poc_records
        order by id
        """
    ).fetchall()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        item = dict(row)
        grouped.setdefault(str(item["task_id"]), []).append(item)
    return grouped


def _baseline_poc_ids(baseline: dict[str, Any]) -> dict[str, set[str]]:
    by_task: dict[str, set[str]] = {}
    for result in baseline.get("results", []):
        task_id = str(result.get("task_id", ""))
        ids = by_task.setdefault(task_id, set())
        for attempt in result.get("artifacts", {}).get("attempts", []):
            poc_id = attempt.get("poc_id")
            if poc_id:
                ids.add(str(poc_id))
    return by_task


def _record_to_attempt(index: int, row: dict[str, Any]) -> dict[str, Any]:
    exit_code = row.get("vul_exit_code")
    return {
        "candidate_index": index,
        "exit_code": exit_code,
        "poc_length": row.get("poc_length"),
        "poc_id": row.get("poc_id"),
        "poc_hash": row.get("poc_hash"),
        "server_record_id": row.get("id"),
        "agent_id": row.get("agent_id"),
        "created_at": row.get("created_at"),
        "fix_exit_code": row.get("fix_exit_code"),
        "output_excerpt": (
            "CyberGym server record: "
            f"vul_exit_code={exit_code}; "
            f"fix_exit_code={row.get('fix_exit_code')}; "
            f"poc_id={row.get('poc_id')}"
        ),
    }


def _attempt_summary(attempt: dict[str, Any]) -> str:
    return (
        f"candidate {attempt.get('candidate_index')}: "
        f"exit_code={attempt.get('exit_code')} "
        f"len={attempt.get('poc_length')}"
    )


def _write_dashboard(run_dir: Path, data: dict[str, Any]) -> None:
    rendered = _dashboard_html(data)
    (run_dir / "dashboard_data.json").write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    dashboard_dir = run_dir / "dashboard"
    (dashboard_dir / "task_compare_data.json").write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    (dashboard_dir / "task_compare.html").write_text(rendered, encoding="utf-8")
    (dashboard_dir / "index.html").write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
