# mypy: ignore-errors
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from sage_ts.evaluation.control_baseline_cache import (
    ControlBaselineCache,
    build_control_cache_report,
    initial_state_checksum,
    scenario_checksum,
    write_synthetic_control_run,
)
from sage_ts.evaluation.task_strata import cohort_policy_report


@pytest.fixture(autouse=True)
def _default_cache_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY", raising=False)
    monkeypatch.delenv("SAGE_CONTROL_CACHE_MIN_COMPATIBLE_RUNS", raising=False)


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
        "base_tool_policy": "upstream",
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


def test_synthetic_control_manifest_records_policy_actor_selection(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "synthetic"
    run_dir = write_synthetic_control_run(
        output_root=output_root,
        run_type="test",
        agent="gpt-4o-mini",
        user="gpt-4o-mini",
        scenario_names=("task",),
        cached_rows_by_name={"task": _row()},
        fresh_run_dir=None,
        cache_report={"control_source": "cached", "cache_manifest_hash": "abc"},
    )

    for manifest_path in (
        output_root / "sage_ts_run_manifest.json",
        run_dir / "sage_ts_run_manifest.json",
    ):
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert payload["actor_selection_mode"] == "policy"


def test_record_creation_writes_manifest_index_and_record(tmp_path: Path) -> None:
    cache = ControlBaselineCache(tmp_path / "cache")
    record = _add(cache, _context(), _row(), tmp_path)

    assert cache.manifest_path.exists()
    assert cache.index_path.exists()
    assert (cache.records_dir / f"{record['record_id']}.json").exists()
    assert record["complete_run"] is True
    assert record["valid_for_cache"] is True
    assert record["final_state_hash_source"] == "execution_context.json"
    index_row = json.loads(cache.index_path.read_text(encoding="utf-8").splitlines()[0])
    assert index_row["complete_run"] is True


def test_checksums_ignore_tool_allow_list_order() -> None:
    def scenario(tools: list[str], shift: float = 0.0):
        starting_context = SimpleNamespace(
            tool_allow_list=tools,
            to_dict=lambda: {
                "tool_allow_list": tools,
                "interactive_console": {"locals": {}},
                "_dbs": {
                    "SANDBOX": [
                        {"row": 1, "creation_timestamp": 100.1 + shift},
                        {"row": 2, "creation_timestamp": 110.1 + shift},
                    ]
                },
            },
        )
        return SimpleNamespace(
            categories=["B", "A"],
            max_messages=1,
            starting_context=starting_context,
            evaluation="same",
        )

    first = scenario(["search_messages", "end_conversation", "get_current_timestamp"])
    second = scenario(
        ["get_current_timestamp", "search_messages", "end_conversation"],
        shift=5.25,
    )

    assert scenario_checksum("task", first) == scenario_checksum("task", second)
    assert initial_state_checksum(first) == initial_state_checksum(second)


def test_multiple_compatible_controls_fail_closed_without_averaging(
    tmp_path: Path,
) -> None:
    cache = ControlBaselineCache(tmp_path / "cache")
    ctx = _context()
    for _ in range(2):
        _add(cache, ctx, _row(), tmp_path)

    assert not cache.lookup(ctx).eligible
    _add(cache, ctx, _row(similarity=0.5, outcome=0.25), tmp_path)
    lookup = cache.lookup(ctx)

    assert not lookup.eligible
    assert lookup.row is None
    assert lookup.reason == "ambiguous_multiple_compatible_controls"
    assert len(lookup.compatible_record_ids) == 3


def test_single_compatible_control_is_eligible_without_averaging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = ControlBaselineCache(tmp_path / "cache")
    ctx = _context()
    _add(cache, ctx, _row(similarity=0.75, outcome=0.5), tmp_path)

    lookup = cache.lookup(ctx)

    assert lookup.eligible
    assert lookup.row is not None
    assert lookup.row["similarity"] == pytest.approx(0.75)
    assert lookup.stats is not None
    assert lookup.stats["min_compatible_completed_runs"] == 1
    assert lookup.stats["cache_match_policy"] == (
        "task_name_agent_user_base_tool_policy_min1"
    )

    monkeypatch.setenv("SAGE_CONTROL_CACHE_MIN_COMPATIBLE_RUNS", "3")
    assert not cache.lookup(ctx).eligible


def test_task_level_cache_ignores_state_runner_scorer_and_sandbox_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = ControlBaselineCache(tmp_path / "cache")
    ctx = _context()
    _add(cache, ctx, _row(), tmp_path)
    monkeypatch.setenv("SAGE_CONTROL_CACHE_MIN_COMPATIBLE_RUNS", "1")

    changed = {
        **ctx,
        "scenario_checksum": "different-scenario-checksum",
        "initial_state_checksum": "different-initial-state",
        "runner_version": "different-runner",
        "scorer_version": "different-scorer",
        "toolsandbox_version": "different-sandbox",
        "manifest_checksum": "different-manifest",
        "prompt_hashes": {"agent_role": "changed", "user_role": "changed"},
        "model_version": "different-model-version-string",
        "model_parameters_hash": "different-model-params",
    }

    lookup = cache.lookup(changed)

    assert lookup.eligible
    assert lookup.stats is not None
    assert lookup.stats["cache_match_policy"] == (
        "task_name_agent_user_base_tool_policy_min1"
    )


def test_task_level_cache_still_separates_model_user_policy_and_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = ControlBaselineCache(tmp_path / "cache")
    ctx = _context()
    _add(cache, ctx, _row(), tmp_path)
    monkeypatch.setenv("SAGE_CONTROL_CACHE_MIN_COMPATIBLE_RUNS", "1")

    assert not cache.lookup(_context(model="different-model")).eligible
    assert not cache.lookup({**ctx, "user_model": "different-user"}).eligible
    assert not cache.lookup({**ctx, "base_tool_policy": "different-policy"}).eligible
    assert not cache.lookup(_context(name="different-task")).eligible


def test_experimental_task_only_cache_can_bypass_model_and_user(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = ControlBaselineCache(tmp_path / "cache")
    ctx = _context()
    _add(cache, ctx, _row(), tmp_path)

    monkeypatch.setenv("SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY", "1")
    monkeypatch.setenv("SAGE_CONTROL_CACHE_MIN_COMPATIBLE_RUNS", "1")
    lookup = cache.lookup(
        {
            **ctx,
            "agent_model": "different-agent",
            "user_model": "different-user",
        }
    )

    assert lookup.eligible
    assert lookup.stats is not None
    assert lookup.stats["cache_match_policy"] == (
        "experimental_task_name_base_tool_policy_min1_model_user_bypassed"
    )
    assert lookup.stats["task_level_fields"] == ["scenario_key", "base_tool_policy"]
    assert lookup.stats["experimental_model_user_bypass"] is True
    assert not cache.lookup({**ctx, "base_tool_policy": "different-policy"}).eligible
    assert not cache.lookup(_context(name="different-task")).eligible


def test_manifest_checksum_change_does_not_reset_task_level_eligibility(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = ControlBaselineCache(tmp_path / "cache")
    ctx = _context()
    _add(cache, ctx, _row(), tmp_path)
    monkeypatch.setenv("SAGE_CONTROL_CACHE_MIN_COMPATIBLE_RUNS", "1")

    changed_manifest = {**ctx, "manifest_checksum": "different-manifest"}

    assert cache.lookup(changed_manifest).eligible


def test_runtime_exception_records_are_ineligible(tmp_path: Path) -> None:
    cache = ControlBaselineCache(tmp_path / "cache")
    ctx = _context()
    for _ in range(3):
        _add(cache, ctx, _row(exception="OpenAIError"), tmp_path)

    assert not cache.lookup(ctx).eligible


def test_build_control_cache_report_reports_mixed_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = ControlBaselineCache(tmp_path / "cache")
    ctx = _context("cached")
    _add(cache, ctx, _row("cached"), tmp_path)
    monkeypatch.setenv("SAGE_CONTROL_CACHE_MIN_COMPATIBLE_RUNS", "1")
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


def test_one_record_is_exact_but_three_records_are_ambiguous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = ControlBaselineCache(tmp_path / "cache")
    one_context = _context("one_record_task")
    three_context = _context("three_record_task")
    _add(cache, one_context, _row("one_record_task", similarity=0.25), tmp_path)
    for score in (0.5, 1.0, 1.0):
        _add(
            cache,
            three_context,
            _row("three_record_task", similarity=score),
            tmp_path,
        )
    monkeypatch.setenv("SAGE_CONTROL_CACHE_MIN_COMPATIBLE_RUNS", "1")

    single = cache.lookup(one_context)
    duplicate = cache.lookup(three_context)

    assert single.eligible
    assert single.row is not None
    assert single.row["similarity"] == 0.25
    assert single.stats is not None
    assert single.stats["compatible_count"] == 1
    assert not duplicate.eligible
    assert duplicate.row is None
    assert duplicate.reason == "ambiguous_multiple_compatible_controls"
    assert len(duplicate.compatible_record_ids) == 3


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
