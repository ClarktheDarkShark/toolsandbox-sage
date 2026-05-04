# mypy: ignore-errors
import json
from pathlib import Path

import pytest

from sage_ts.evaluation.control_baseline_cache import (
    ControlBaselineCache,
    build_control_cache_report,
)
from sage_ts.evaluation.task_strata import cohort_policy_report


def _context(
    name: str = "task", *, model: str = "gpt-4o-mini", scorer: str = "scorer"
) -> dict:
    return {
        "scenario_key": name,
        "scenario_checksum": f"scenario-{name}",
        "initial_state_checksum": f"state-{name}",
        "agent_model": model,
        "user_model": "gpt-4o-mini",
        "model_version": f"agent={model}|user=gpt-4o-mini",
        "model_parameters_hash": "params",
        "prompt_hashes": {"agent_role": "a", "user_role": "u"},
        "runner_version": "runner",
        "scorer_version": scorer,
        "toolsandbox_version": "sandbox",
        "manifest_checksum": "manifest",
        "base_tool_policy": "recency_reduced",
    }


def _row(
    name: str = "task", *, similarity: float = 1.0, outcome: float = 1.0, exception=None
) -> dict:
    return {
        "name": name,
        "categories": [],
        "traceback": None,
        "exception_type": exception,
        "milestone_similarity": similarity,
        "minefield_similarity": 0,
        "similarity": similarity,
        "turn_count": 4,
        "milestone_mapping": {"0": similarity},
        "minefield_mapping": {},
        "outcome_similarity": outcome,
        "outcome_checks": [],
    }


def _add(cache: ControlBaselineCache, ctx: dict, row: dict, tmp_path: Path):
    run = tmp_path / "run"
    (run / "trajectories" / row["name"]).mkdir(parents=True, exist_ok=True)
    (run / "trajectories" / row["name"] / "conversation.json").write_text("[]\n")
    (run / "trajectories" / row["name"] / "execution_context.json").write_text(
        json.dumps({"db": row["name"]}) + "\n"
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}\n")
    return cache.add_record(
        context=ctx, result_row=row, run_dir=run, manifest_path=manifest
    )


def test_record_creation_writes_manifest_index_and_record(tmp_path: Path) -> None:
    cache = ControlBaselineCache(tmp_path / "cache")
    record = _add(cache, _context(), _row(), tmp_path)

    assert cache.manifest_path.exists()
    assert cache.index_path.exists()
    assert (cache.records_dir / f"{record['record_id']}.json").exists()
    assert record["complete_run"] is True
    assert record["valid_for_cache"] is True
    assert record["final_state_hash_source"] == "execution_context.json"


def test_eligibility_requires_three_compatible_completed_runs(tmp_path: Path) -> None:
    cache = ControlBaselineCache(tmp_path / "cache")
    ctx = _context()
    for _ in range(2):
        _add(cache, ctx, _row(), tmp_path)

    assert not cache.lookup(ctx).eligible
    _add(cache, ctx, _row(similarity=0.5, outcome=0.25), tmp_path)
    lookup = cache.lookup(ctx)

    assert lookup.eligible
    assert lookup.row is not None
    assert lookup.row["similarity"] == pytest.approx((1 + 1 + 0.5) / 3)
    assert lookup.stats is not None
    assert lookup.stats["compatible_count"] == 3
    assert lookup.stats["canonical_variance"] > 0


def test_incompatibility_after_model_scorer_or_scenario_change(tmp_path: Path) -> None:
    cache = ControlBaselineCache(tmp_path / "cache")
    ctx = _context()
    for _ in range(3):
        _add(cache, ctx, _row(), tmp_path)

    assert cache.lookup(_context(model="gpt-4o-mini")).eligible
    assert not cache.lookup(_context(model="different-model")).eligible
    assert not cache.lookup(_context(scorer="new-scorer")).eligible
    assert not cache.lookup(_context(name="different-task")).eligible


def test_runtime_exception_records_are_ineligible(tmp_path: Path) -> None:
    cache = ControlBaselineCache(tmp_path / "cache")
    ctx = _context()
    for _ in range(3):
        _add(cache, ctx, _row(exception="OpenAIError"), tmp_path)

    assert not cache.lookup(ctx).eligible


def test_build_control_cache_report_reports_mixed_sources(tmp_path: Path) -> None:
    cache = ControlBaselineCache(tmp_path / "cache")
    ctx = _context("cached")
    for _ in range(3):
        _add(cache, ctx, _row("cached"), tmp_path)
    lookup = cache.lookup(ctx)

    report = build_control_cache_report(
        mode="use-if-eligible",
        cache=cache,
        scenario_names=("cached", "fresh"),
        cached_scenarios=["cached"],
        fresh_scenarios=["fresh"],
        miss_reasons={"fresh": "fewer_than_3_compatible_completed_controls"},
        lookups={"cached": lookup},
    )

    assert report["control_source"] == "mixed"
    assert report["cached_control_tasks"] == 1
    assert report["fresh_control_tasks"] == 1
    assert report["cache_manifest_hash"]
    assert report["confidence_intervals_account_for_cached_control_variance"] is True


def test_cohort_quality_gate_still_blocks_near_duplicate_cached_manifest() -> None:
    scenarios = [
        "add_reminder_content_and_date_and_time",
        "add_reminder_content_and_date_and_time_3_distraction_tools",
        "add_reminder_content_and_date_and_time_10_distraction_tools",
    ] + [f"uncovered_family_{index}" for index in range(17)]

    report = cohort_policy_report(
        scenarios,
        categories_by_name={scenario: [] for scenario in scenarios},
        generation_enabled=False,
        registry_tool_count=2,
    )

    assert report["should_block_quality"] is True
    assert (
        "near_duplicate_family_variants_above_limit" in report["quality_gate_failures"]
    )
