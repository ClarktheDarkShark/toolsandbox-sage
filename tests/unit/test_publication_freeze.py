from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_publication_freeze import (
    FreezeError,
    canonical_json_bytes,
    directory_inventory,
    immutable_write,
    original_v140_snapshot_bytes,
    sanitized_rapid_fixture_bytes,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _cache_key(request: dict) -> str:
    encoded = json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def test_directory_inventory_is_creation_order_independent(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "b.txt").write_text("beta\n", encoding="utf-8")
    (first / "a.txt").write_text("alpha\n", encoding="utf-8")
    (second / "a.txt").write_text("alpha\n", encoding="utf-8")
    (second / "b.txt").write_text("beta\n", encoding="utf-8")

    first_inventory = directory_inventory(tmp_path, first)
    second_inventory = directory_inventory(tmp_path, second)

    assert first_inventory["files"] == second_inventory["files"]
    assert first_inventory["directory_sha256"] == second_inventory["directory_sha256"]


def test_immutable_write_never_overwrites_different_bytes(tmp_path: Path) -> None:
    path = tmp_path / "artifact.json"
    immutable_write(path, b"one\n")
    immutable_write(path, b"one\n")

    with pytest.raises(FreezeError, match="different bytes"):
        immutable_write(path, b"two\n")

    assert path.read_bytes() == b"one\n"


def test_original_v140_snapshot_excludes_later_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.build_publication_freeze as freeze

    monkeypatch.setattr(freeze, "EXPECTED_TASK_COUNT", 2)
    benchmark = tmp_path / "benchmark.json"
    _write_json(
        benchmark,
        {"splits": {"full_benchmark": [{"name": "task_b"}, {"name": "task_a"}]}},
    )
    cache = tmp_path / "cache"
    source_dir = "outputs/original/control"
    _write_json(
        cache / "v140_source_report.json",
        {
            "source_control_dir": source_dir,
            "source_run_root": "outputs/original",
        },
    )
    rows = [
        {
            "scenario_key": "task_a",
            "run_dir": source_dir,
            "valid_for_cache": True,
            "complete_run": True,
            "canonical_score": 0.5,
            "outcome_score": 0.25,
        },
        {
            "scenario_key": "task_b",
            "run_dir": source_dir,
            "valid_for_cache": True,
            "complete_run": True,
            "canonical_score": 1.0,
            "outcome_score": None,
        },
        {
            "scenario_key": "task_a",
            "run_dir": "outputs/later/control",
            "valid_for_cache": True,
            "complete_run": True,
            "canonical_score": 0.0,
            "outcome_score": 0.0,
        },
    ]
    (cache / "compact_records.jsonl").write_bytes(
        b"".join(canonical_json_bytes(row) for row in rows)
    )

    snapshot, metadata = original_v140_snapshot_bytes(
        legacy_cache_root=cache,
        benchmark=benchmark,
    )
    selected = [json.loads(line) for line in snapshot.splitlines()]

    assert [row["scenario_key"] for row in selected] == ["task_b", "task_a"]
    assert all(row["run_dir"] == source_dir for row in selected)
    assert metadata["record_count"] == 2
    assert metadata["legacy_cache_total_records_at_freeze"] == 3
    assert metadata["eligible_for_new_experiment_runs"] is False


def test_rapid_fixture_is_allowlisted_and_cache_keys_are_revalidated(
    tmp_path: Path,
) -> None:
    request = {
        "url": "https://example.p.rapidapi.com/search",
        "host": "example.p.rapidapi.com",
        "params": {"query": "paper"},
    }
    key = _cache_key(request)
    source = tmp_path / "rapid.json"
    _write_json(
        source,
        {"entries": {key: {"request": request, "response": {"value": 42}}}},
    )

    payload, metadata = sanitized_rapid_fixture_bytes(source)

    assert json.loads(payload) == json.loads(source.read_bytes())
    assert metadata["entry_count"] == 1
    assert metadata["contains_api_credentials"] is False


def test_rapid_fixture_rejects_request_secrets(tmp_path: Path) -> None:
    request = {
        "url": "https://example.p.rapidapi.com/search",
        "host": "example.p.rapidapi.com",
        "params": {"api_key": "do-not-publish"},
    }
    source = tmp_path / "rapid.json"
    _write_json(
        source,
        {
            "entries": {
                _cache_key(request): {
                    "request": request,
                    "response": {"value": 42},
                }
            }
        },
    )

    with pytest.raises(FreezeError, match="sensitive key"):
        sanitized_rapid_fixture_bytes(source)
