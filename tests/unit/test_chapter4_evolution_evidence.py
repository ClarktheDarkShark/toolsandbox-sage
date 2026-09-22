from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.research.chapter4_evolution_evidence import measure_evolution_run


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo_root = tmp_path
    run_root = repo_root / "outputs" / "run01"
    candidate = run_root / "candidate" / "candidate_run"
    registry = repo_root / "artifacts" / "registry01"
    _write_json(
        run_root / "protocol_manifest.json",
        {"candidate_dir": str(candidate.relative_to(repo_root))},
    )
    _write_jsonl(
        candidate / "tool_birth_events.jsonl",
        [
            {
                "tool_name": "tool_a",
                "accepted": True,
                "repair_attempted": True,
                "repair_attempt_count": 2,
                "repair_errors": ["initial validation failure"],
                # This is the capability family, not the triggering task family.
                "task_family_key": "beta",
            },
            {
                "tool_name": "tool_b",
                "accepted": True,
                "repair_attempted": False,
                "repair_attempt_count": 0,
                "repair_errors": [],
                "task_family_key": "alpha",
            },
            {
                "tool_name": "tool_failed",
                "accepted": False,
                "repair_attempted": True,
                "repair_attempt_count": 1,
                "repair_errors": ["still invalid"],
                "task_family_key": "gamma",
            },
        ],
    )
    _write_jsonl(
        candidate / "sage_run_events.jsonl",
        [
            {
                "event": "jit_birth_tools_available_for_same_task",
                "scenario": "birth_a",
                "accepted_tools": ["tool_a"],
            },
            {
                "event": "jit_birth_tools_available_for_same_task",
                "scenario": "birth_b",
                "accepted_tools": ["tool_b"],
            },
        ],
    )
    _write_jsonl(
        candidate / "self_evolution_task_feedback.jsonl",
        [
            {
                "scenario": "birth_a",
                "completed_count": 1,
                "base_family": "alpha",
                "task_family_key": "alpha",
                "generated_tools_called": ["tool_a"],
            },
            {
                "scenario": "birth_b",
                "completed_count": 2,
                "base_family": "alpha",
                "task_family_key": "alpha",
                "generated_tools_called": ["tool_b"],
            },
            {
                "scenario": "later_beta",
                "completed_count": 3,
                "base_family": "beta",
                "task_family_key": "beta",
                "generated_tools_called": ["tool_a"],
            },
            {
                "scenario": "later_alpha",
                "completed_count": 4,
                "base_family": "alpha",
                "task_family_key": "alpha",
                "generated_tools_called": ["tool_b"],
            },
        ],
    )
    _write_jsonl(
        candidate / "reuse_events.jsonl",
        [
            {
                "event": "generated_tool_invoked",
                "scenario": scenario,
                "tool_name": name,
            }
            for scenario, name in (
                ("birth_a", "tool_a"),
                ("birth_b", "tool_b"),
                ("later_beta", "tool_a"),
                ("later_alpha", "tool_b"),
            )
        ],
    )
    _write_json(
        registry / "registry_manifest.json",
        {
            "tools": {
                "tool_a": {"reuse_count": 2},
                "tool_b": {"reuse_count": 2},
            }
        },
    )
    return repo_root, run_root, registry


def test_measure_evolution_run_uses_actual_birth_task_family(tmp_path: Path) -> None:
    repo_root, run_root, registry = _fixture(tmp_path)

    result = measure_evolution_run(
        repo_root=repo_root,
        replication=1,
        label="R01",
        run_root=run_root,
        registry_dir=registry,
    )

    assert result.repair_entrants == 2
    assert result.repaired_accepted == 1
    assert result.repaired_reused_later == 1
    assert result.max_repair_attempts_observed == 2
    assert result.repair_conversion_percent == pytest.approx(50.0)
    assert result.repaired_reuse_percent == pytest.approx(100.0)
    assert result.accepted_tools == 2
    assert result.cross_family_tools == 1
    assert result.cross_family_percent == pytest.approx(50.0)


def test_measure_evolution_run_fails_when_accepted_tool_lacks_registry_entry(
    tmp_path: Path,
) -> None:
    repo_root, run_root, registry = _fixture(tmp_path)
    _write_json(registry / "registry_manifest.json", {"tools": {"tool_a": {}}})

    with pytest.raises(ValueError, match="missing from the registry"):
        measure_evolution_run(
            repo_root=repo_root,
            replication=1,
            label="R01",
            run_root=run_root,
            registry_dir=registry,
        )
