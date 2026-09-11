from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import scripts.run_chapter4_evidence_campaign as campaign
from scripts.research.chapter4_evidence import EVIDENCE_DATA_NAME, EVIDENCE_HTML_NAME


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid_campaign(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    scope: str = campaign.DEFAULT_CAMPAIGN_SCOPE,
) -> tuple[dict[str, Any], Path, list[dict[str, Any]]]:
    benchmark = tmp_path / "benchmark.json"
    fixture = tmp_path / "fixture.json"
    benchmark.write_text('{"benchmark": true}\n', encoding="utf-8")
    fixture.write_text('{"fixture": true}\n', encoding="utf-8")
    monkeypatch.setattr(
        campaign,
        "PINNED_BENCHMARK_SHA256",
        _sha256(benchmark),
    )
    monkeypatch.setattr(
        campaign,
        "PINNED_EXTERNAL_FIXTURE_SHA256",
        _sha256(fixture),
    )

    identity = {
        "git_commit": "commit",
        "git_tree": "tree",
        "fixed_toolsandbox_timestamp": campaign.DEFAULT_FIXED_NOW,
        "python_version": "3.12.7",
        "python_implementation": "CPython",
        "platform_system": "Darwin",
        "platform_machine": "arm64",
        "isolated_environment": True,
        "environment_lock_sha256": "lock-sha",
        "external_distribution_count": 108,
        "external_distribution_sha256": "distribution-sha",
        "execution_environment": dict(campaign.PUBLICATION_EXECUTION_ENV),
        "runtime_digest": "runtime",
        "generation_settings_digest": "generation",
    }
    monkeypatch.setattr(campaign, "_require_clean_git", lambda repo_root: identity)

    sample_run_root = tmp_path / "sample_run"
    sample_run_root.mkdir()
    sample_payload = {
        "schema_version": 1,
        "status": "pass",
        "publication_gate_purpose": (campaign.PUBLICATION_GATE_PURPOSE_RELEASE_SAMPLE),
        "run_root": str(sample_run_root),
        "integrity_verification": {
            "status": "pass",
            "run_root": str(sample_run_root),
            "publication_provenance": {
                field: identity[field]
                for field in campaign.SAMPLE_RELEASE_IDENTITY_FIELDS
            },
        },
    }
    sample_report = tmp_path / "sample_report.json"
    _write_json(sample_report, sample_payload)
    sample_calls: list[dict[str, Any]] = []

    def verify_sample(
        search_root: Path,
        *,
        output_path: Path | None = None,
        write_report: bool = True,
    ) -> dict[str, Any]:
        sample_calls.append(
            {
                "search_root": search_root,
                "output_path": output_path,
                "write_report": write_report,
            }
        )
        return copy.deepcopy(sample_payload)

    monkeypatch.setattr(campaign, "verify_sample", verify_sample)

    campaign_id = "publication_campaign"
    artifact_root, output_root, _ = campaign._campaign_paths(
        tmp_path,
        campaign_id,
    )
    run_pairs: list[dict[str, Any]] = []
    for replication in range(1, campaign.EXPECTED_REPLICATIONS + 1):
        rep_label = f"rep{replication:02d}"
        online_registry = campaign._relative(
            tmp_path,
            artifact_root / "online" / rep_label / "native_action_registry",
        )
        pair = {
            "replication": replication,
            "online": {
                "source": "campaign_online_build_fresh_control",
                "publication_gate_purpose": (
                    campaign.PUBLICATION_GATE_PURPOSE_CAMPAIGN_INCLUSION
                ),
                "run_root": "",
                "search_root": campaign._relative(
                    tmp_path,
                    output_root / "online" / rep_label / "native_action",
                ),
                "registry_dir": online_registry,
                "execution_status": "queued",
            },
        }
        if scope == "online-and-frozen":
            pair["frozen"] = {
                "source": "paired_frozen_registry_reuse",
                "publication_gate_purpose": (
                    campaign.PUBLICATION_GATE_PURPOSE_CAMPAIGN_INCLUSION
                ),
                "run_root": "",
                "search_root": campaign._relative(
                    tmp_path,
                    output_root / "frozen" / rep_label / "frozen_registry",
                ),
                "registry_dir": campaign._relative(
                    tmp_path,
                    artifact_root / "frozen" / rep_label / "frozen_registry_registry",
                ),
                "source_registry_dir": online_registry,
                "execution_status": "queued",
            }
        run_pairs.append(pair)

    manifest = {
        "schema_version": 2,
        "campaign_id": campaign_id,
        "status": "prepared",
        "campaign_scope": scope,
        "model": campaign.PUBLICATION_MODEL,
        "benchmark_manifest": benchmark.relative_to(tmp_path).as_posix(),
        "benchmark_sha256": _sha256(benchmark),
        "external_fixture": {
            "policy": "validated_read_only_fixture",
            "path": fixture.relative_to(tmp_path).as_posix(),
            "sha256": _sha256(fixture),
            "mode": "read_only",
        },
        "baseline_cache": "",
        "baseline_cache_policy": campaign.BASELINE_CACHE_POLICY,
        "failure_recovery_policy": campaign.CAMPAIGN_FAILURE_RECOVERY_POLICY,
        "control_execution": campaign._expected_control_execution(),
        "fixed_toolsandbox_timestamp": campaign.DEFAULT_FIXED_NOW,
        "expected_online_runs": campaign.EXPECTED_REPLICATIONS,
        "expected_frozen_runs": (
            campaign.EXPECTED_REPLICATIONS if scope == "online-and-frozen" else 0
        ),
        "expected_tasks_per_run": campaign.EXPECTED_TASKS_PER_RUN,
        "sample_validation": {
            "path": sample_report.relative_to(tmp_path).as_posix(),
            "sha256": _sha256(sample_report),
            "run_root": sample_run_root.relative_to(tmp_path).as_posix(),
            "status": "pass",
            "publication_gate_purpose": (
                campaign.PUBLICATION_GATE_PURPOSE_RELEASE_SAMPLE
            ),
            "release_identity": {
                field: identity[field]
                for field in campaign.SAMPLE_RELEASE_IDENTITY_FIELDS
            },
        },
        "maximum_parallel_runs": campaign.MAX_CONCURRENCY,
        "execution_waves": campaign._expected_execution_waves(
            campaign.MAX_CONCURRENCY,
            scope,
        ),
        "statistical_plan": campaign._expected_statistical_plan(),
        "claim_safeguards": campaign._expected_claim_safeguards(),
        "configuration_identity": {
            **identity,
            "prompt_policy_digest": "sage_ts_protocol_v1",
        },
        "paths": {
            "artifact_root": campaign._relative(tmp_path, artifact_root),
            "output_root": campaign._relative(tmp_path, output_root),
            "dashboard_dir": campaign._relative(
                tmp_path,
                output_root / "dashboard",
            ),
        },
        "run_pairs": run_pairs,
        "parallel_wave_execution": {},
        "execution_events": [
            {
                "at": "2026-09-01T00:00:00Z",
                "event": "campaign_prepared",
                "detail": "test",
            }
        ],
    }
    return manifest, sample_report, sample_calls


def _set_nested(
    payload: dict[str, Any],
    path: tuple[str | int, ...],
    value: Any,
) -> None:
    target: Any = payload
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value


def _record_parallel_wave(
    manifest: dict[str, Any],
    *,
    wave: int = 1,
    overlapping: bool = True,
) -> dict[str, Any]:
    arm = "online" if wave == 1 else "frozen"
    results: list[dict[str, Any]] = []
    for replication, pair in enumerate(manifest["run_pairs"], start=1):
        started = 100 + replication
        completed = 1_000 + replication if overlapping else started + 1
        result = {
            "replication": replication,
            "arm": arm,
            "port": 64200 + replication - 1,
            "return_code": 0,
            "process_pid": 10_000 + replication,
            "process_started_monotonic_ns": started,
            "process_completed_monotonic_ns": completed,
        }
        results.append(result)
        pair[arm].update(
            {
                "dashboard_port": result["port"],
                "process_pid": result["process_pid"],
                "process_started_monotonic_ns": started,
                "process_completed_monotonic_ns": completed,
                "process_return_code": 0,
            }
        )
    record = campaign._parallel_wave_execution_record(
        wave=wave,
        jobs=[(replication, arm) for replication in range(1, 11)],
        results=results,
    )
    manifest["parallel_wave_execution"][str(wave)] = record
    return record


def test_campaign_prerequisites_accept_default_online_only_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, sample_report, sample_calls = _valid_campaign(tmp_path, monkeypatch)
    before = sample_report.read_bytes()

    assert campaign._campaign_prerequisite_errors(tmp_path, manifest) == []
    assert manifest["campaign_scope"] == "online-only"
    assert manifest["expected_frozen_runs"] == 0
    assert all("frozen" not in pair for pair in manifest["run_pairs"])
    assert sample_report.read_bytes() == before
    assert sample_calls == [
        {
            "search_root": tmp_path / "sample_run",
            "output_path": sample_report,
            "write_report": False,
        }
    ]


def test_sample_validation_declaration_requires_exactly_one_gate_disposition(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="Declare exactly one"):
        campaign._sample_validation_declaration(
            tmp_path,
            {},
            report_path=None,
            waiver_requested=False,
            waiver_reason=None,
        )
    with pytest.raises(ValueError, match="Declare exactly one"):
        campaign._sample_validation_declaration(
            tmp_path,
            {},
            report_path=Path("sample.json"),
            waiver_requested=True,
            waiver_reason="explicit direction",
        )


def test_sample_validation_waiver_requires_a_nonempty_reason(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires a nonempty"):
        campaign._sample_validation_declaration(
            tmp_path,
            {},
            report_path=None,
            waiver_requested=True,
            waiver_reason="   ",
        )


def test_sample_validation_waiver_is_explicit_hashed_and_never_a_fake_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    thresholds = tmp_path / "thresholds.json"
    _write_json(thresholds, {"schema_version": 3})
    monkeypatch.setattr(
        campaign._sample_verifier,
        "DEFAULT_THRESHOLDS",
        thresholds.relative_to(tmp_path),
    )

    declaration = campaign._sample_validation_declaration(
        tmp_path,
        manifest["configuration_identity"],
        report_path=None,
        waiver_requested=True,
        waiver_reason="  Researcher directed immediate confirmatory campaign.  ",
    )

    assert declaration["status"] == campaign.RESEARCHER_SAMPLE_WAIVER_STATUS
    assert declaration["status"] != "pass"
    assert declaration["authorization"] == (
        campaign.RESEARCHER_SAMPLE_WAIVER_AUTHORIZATION
    )
    assert declaration["reason"] == (
        "Researcher directed immediate confirmatory campaign."
    )
    assert declaration["thresholds_path"] == "thresholds.json"
    assert declaration["thresholds_sha256"] == _sha256(thresholds)
    assert "path" not in declaration
    assert "sha256" not in declaration
    assert "run_root" not in declaration
    assert "publication_gate_purpose" not in declaration


def test_campaign_prerequisites_accept_explicit_sample_waiver_without_relaxing_jobs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, sample_calls = _valid_campaign(tmp_path, monkeypatch)
    thresholds = tmp_path / "thresholds.json"
    _write_json(thresholds, {"schema_version": 3})
    release_identity = manifest["sample_validation"]["release_identity"]
    manifest["sample_validation"] = {
        "status": campaign.RESEARCHER_SAMPLE_WAIVER_STATUS,
        "authorization": campaign.RESEARCHER_SAMPLE_WAIVER_AUTHORIZATION,
        "required_gate": campaign.PUBLICATION_GATE_PURPOSE_RELEASE_SAMPLE,
        "reason": "Researcher directed immediate confirmatory campaign.",
        "authorized_at": "2026-09-11T00:00:00+00:00",
        "thresholds_path": thresholds.relative_to(tmp_path).as_posix(),
        "thresholds_sha256": _sha256(thresholds),
        "release_identity": release_identity,
    }

    assert campaign._campaign_prerequisite_errors(tmp_path, manifest) == []
    assert sample_calls == []
    assert all(
        pair["online"]["publication_gate_purpose"]
        == campaign.PUBLICATION_GATE_PURPOSE_CAMPAIGN_INCLUSION
        for pair in manifest["run_pairs"]
    )


def test_campaign_prerequisites_accept_explicit_online_and_frozen_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(
        tmp_path,
        monkeypatch,
        scope="online-and-frozen",
    )

    assert campaign._campaign_prerequisite_errors(tmp_path, manifest) == []


@pytest.mark.parametrize("field", campaign._expected_statistical_plan())
def test_campaign_rejects_every_statistical_plan_mutation(
    field: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    manifest["statistical_plan"][field] = None

    errors = campaign._campaign_prerequisite_errors(tmp_path, manifest)

    assert f"statistical plan mismatch: {field}" in errors


@pytest.mark.parametrize("field", campaign._expected_control_execution())
def test_campaign_rejects_every_control_execution_mutation(
    field: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    manifest["control_execution"][field] = None

    errors = campaign._campaign_prerequisite_errors(tmp_path, manifest)

    assert f"control execution mismatch: {field}" in errors


@pytest.mark.parametrize("field", campaign._expected_claim_safeguards())
def test_campaign_rejects_every_claim_safeguard_mutation(
    field: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    manifest["claim_safeguards"][field] = None

    errors = campaign._campaign_prerequisite_errors(tmp_path, manifest)

    assert f"claim safeguards mismatch: {field}" in errors


def test_campaign_rejects_undeclared_claim_safeguard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    manifest["claim_safeguards"]["experimental_override"] = True

    errors = campaign._campaign_prerequisite_errors(tmp_path, manifest)

    assert "claim safeguards has undeclared fields: experimental_override" in errors


@pytest.mark.parametrize(
    ("path", "replacement", "expected_error"),
    [
        (("model",), "gpt-4o", "model must be exactly"),
        (
            ("fixed_toolsandbox_timestamp",),
            0,
            "fixed_toolsandbox_timestamp must be exactly",
        ),
        (("baseline_cache",), "old/cache.json", "baseline_cache must be empty"),
        (
            ("baseline_cache_policy",),
            "optional",
            "baseline_cache_policy must prohibit",
        ),
        (
            ("failure_recovery_policy",),
            "reuse_partial",
            "failure_recovery_policy must prohibit",
        ),
        (
            ("paths", "output_root"),
            "outputs/redirected",
            "campaign paths mismatch: output_root",
        ),
        (
            ("run_pairs", 0, "online", "search_root"),
            "outputs/redirected",
            "replication 1 online search_root",
        ),
        (
            ("run_pairs", 0, "online", "registry_dir"),
            "artifacts/redirected",
            "replication 1 online registry_dir",
        ),
        (
            ("run_pairs", 0, "frozen", "search_root"),
            "outputs/redirected",
            "replication 1 frozen search_root",
        ),
        (
            ("run_pairs", 0, "frozen", "registry_dir"),
            "artifacts/redirected",
            "replication 1 frozen registry_dir",
        ),
        (
            ("run_pairs", 0, "frozen", "source_registry_dir"),
            "artifacts/historical_registry",
            "replication 1 frozen source_registry_dir",
        ),
    ],
)
def test_campaign_rejects_model_clock_cache_and_path_mutations(
    path: tuple[str | int, ...],
    replacement: Any,
    expected_error: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = "online-and-frozen" if "frozen" in path else campaign.DEFAULT_CAMPAIGN_SCOPE
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch, scope=scope)
    _set_nested(manifest, path, replacement)

    errors = campaign._campaign_prerequisite_errors(tmp_path, manifest)

    assert any(expected_error in error for error in errors)


def test_campaign_rejects_execution_wave_parallelism_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(
        tmp_path,
        monkeypatch,
        scope="online-and-frozen",
    )
    manifest["execution_waves"][1]["maximum_parallel"] = 1

    errors = campaign._campaign_prerequisite_errors(tmp_path, manifest)

    assert (
        "execution_waves must exactly match the declared campaign parallelism" in errors
    )


def test_online_only_campaign_requires_all_ten_jobs_concurrently(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    manifest["maximum_parallel_runs"] = 9
    manifest["execution_waves"] = campaign._expected_execution_waves(9)

    errors = campaign._campaign_prerequisite_errors(tmp_path, manifest)

    assert (
        "maximum_parallel_runs must be exactly 10 for the online-only publication "
        "campaign" in errors
    )


def test_campaign_rejects_sample_report_run_root_rebinding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, sample_calls = _valid_campaign(tmp_path, monkeypatch)
    manifest["sample_validation"]["run_root"] = "different_sample_run"

    errors = campaign._campaign_prerequisite_errors(tmp_path, manifest)

    assert any("run root does not match" in error for error in errors)
    assert sample_calls == []


def test_campaign_rejects_sample_from_different_release_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    manifest["sample_validation"]["release_identity"]["git_tree"] = "other-tree"

    errors = campaign._campaign_prerequisite_errors(tmp_path, manifest)

    assert "publication sample release identity changed" in errors
    assert "publication sample/current release mismatch: git_tree" in errors


def test_prepared_campaign_rejects_any_started_entry_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    manifest["run_pairs"][0]["online"]["started_at"] = "2026-09-01T00:00:00Z"

    errors = campaign._campaign_prerequisite_errors(tmp_path, manifest)

    assert any("prepared-state execution field started_at" in error for error in errors)


def test_prepared_campaign_blocks_injected_complete_artifacts_before_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    injected_root = tmp_path / manifest["run_pairs"][0]["online"]["search_root"]
    _write_json(
        injected_root / "protocol_manifest.json",
        {"scenario_count": campaign.EXPECTED_TASKS_PER_RUN},
    )
    _write_json(
        injected_root / "paired_comparison.json",
        {"scenario_count": campaign.EXPECTED_TASKS_PER_RUN, "deltas": []},
    )
    wave_called = False

    def run_wave(**kwargs: Any) -> None:
        nonlocal wave_called
        wave_called = True

    monkeypatch.setattr(campaign, "_run_wave", run_wave)
    args = argparse.Namespace(
        resume_incomplete=False,
        max_parallel=None,
        wave="all",
        base_port=63000,
    )

    with pytest.raises(SystemExit, match="prepared search_root already exists"):
        campaign._run_claimed_campaign(
            args,
            tmp_path,
            tmp_path / "campaign_manifest.json",
            manifest,
        )

    assert not wave_called


def test_incomplete_campaign_rejects_run_root_outside_exact_search_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    manifest["status"] = "incomplete"
    prior_run = tmp_path / "historical" / "online_run"
    prior_run.mkdir(parents=True)
    manifest["run_pairs"][0]["online"]["run_root"] = str(prior_run)

    errors = campaign._campaign_prerequisite_errors(tmp_path, manifest)

    assert any(
        "run_root escapes its exact campaign search_root" in error for error in errors
    )


def test_entry_validity_never_reads_an_out_of_campaign_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    search_root = tmp_path / "campaign" / "online" / "rep01"
    search_root.mkdir(parents=True)
    prior_run = tmp_path / "historical" / "run"
    prior_run.mkdir(parents=True)
    entry = {
        "search_root": str(search_root),
        "run_root": str(prior_run),
    }
    evidence_called = False
    verifier_called = False

    def load_evidence(repo_root: Path, observed: dict[str, Any]) -> Any:
        nonlocal evidence_called
        evidence_called = True
        return SimpleNamespace(complete=True)

    def verify_run(search: Path, **kwargs: Any) -> dict[str, Any]:
        nonlocal verifier_called
        verifier_called = True
        return {"status": "pass", "run_root": str(prior_run)}

    monkeypatch.setattr(campaign, "load_run_evidence", load_evidence)
    monkeypatch.setattr(campaign, "verify_run", verify_run)

    assert not campaign._entry_is_valid(
        tmp_path,
        {"expected_tasks_per_run": campaign.EXPECTED_TASKS_PER_RUN},
        entry,
        "online",
    )
    assert not evidence_called
    assert not verifier_called


def test_incomplete_entry_without_bound_run_root_is_rerun_not_discovered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    search_root = tmp_path / "campaign" / "online" / "rep01"
    search_root.mkdir(parents=True)
    evidence_called = False

    def load_evidence(repo_root: Path, observed: dict[str, Any]) -> Any:
        nonlocal evidence_called
        evidence_called = True
        return SimpleNamespace(complete=True)

    monkeypatch.setattr(campaign, "load_run_evidence", load_evidence)

    assert not campaign._entry_is_valid(
        tmp_path,
        {
            "status": "incomplete",
            "expected_tasks_per_run": campaign.EXPECTED_TASKS_PER_RUN,
        },
        {"search_root": str(search_root), "run_root": ""},
        "online",
    )
    assert not evidence_called


def test_campaign_entry_requires_exact_dual_endpoint_measurements(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    search_root = tmp_path / "campaign" / "online" / "rep01"
    run_root = search_root / "run"
    run_root.mkdir(parents=True)
    entry = {
        "search_root": str(search_root),
        "run_root": str(run_root),
    }
    manifest = {"expected_tasks_per_run": campaign.EXPECTED_TASKS_PER_RUN}
    endpoint_calls: list[dict[str, Any]] = []
    verifier_calls: list[dict[str, Any]] = []

    def verify_publication_run(*args: Any, **kwargs: Any) -> dict[str, Any]:
        verifier_calls.append(kwargs)
        return {
            "status": "pass",
            "run_root": str(run_root),
        }

    monkeypatch.setattr(
        campaign,
        "verify_run",
        verify_publication_run,
    )

    def verify_endpoints(**kwargs: Any) -> dict[str, Any]:
        endpoint_calls.append(kwargs)
        raise ValueError(
            "paper-comparable endpoint has 799 rows; expected exact v1 800"
        )

    monkeypatch.setattr(
        campaign,
        "verify_run_endpoint_measurements",
        verify_endpoints,
    )

    with pytest.raises(ValueError, match="expected exact v1 800"):
        campaign._verify_publication_entry(
            tmp_path,
            manifest,
            entry,
            "online",
        )

    assert endpoint_calls == [
        {
            "repo_root": tmp_path,
            "campaign_manifest": manifest,
            "entry": {**entry, "run_root": str(run_root.resolve())},
        }
    ]
    assert verifier_calls[0]["gate_purpose"] == "campaign-inclusion"


def test_force_replacement_rejects_stale_arm_and_registry_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(
        tmp_path,
        monkeypatch,
        scope="online-and-frozen",
    )
    artifact_root, output_root, _ = campaign._campaign_paths(
        tmp_path,
        str(manifest["campaign_id"]),
    )
    manifest["status"] = "prepared"

    assert (
        campaign._force_replacement_errors(
            manifest,
            artifact_root,
            output_root,
        )
        == []
    )

    stale_registry = artifact_root / "online" / "rep01" / "native_action_registry"
    stale_registry.mkdir(parents=True)
    (stale_registry / "registry.json").write_text("{}\n", encoding="utf-8")
    stale_output = output_root / "frozen" / "rep01" / "frozen_registry"
    stale_output.mkdir(parents=True)
    (stale_output / "protocol_manifest.json").write_text(
        "{}\n",
        encoding="utf-8",
    )

    errors = campaign._force_replacement_errors(
        manifest,
        artifact_root,
        output_root,
    )

    assert any("stale campaign arm root" in error for error in errors)
    assert any(str(artifact_root / "online") in error for error in errors)
    assert any(str(output_root / "frozen") in error for error in errors)


def test_force_replacement_rejects_started_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    artifact_root, output_root, _ = campaign._campaign_paths(
        tmp_path,
        str(manifest["campaign_id"]),
    )
    manifest["status"] = "prepared"
    manifest["run_pairs"][0]["online"]["started_at"] = "2026-09-01T00:00:00Z"

    errors = campaign._force_replacement_errors(
        manifest,
        artifact_root,
        output_root,
    )

    assert any("execution field started_at" in error for error in errors)


def test_stale_campaign_roots_are_detected_without_a_manifest(tmp_path: Path) -> None:
    artifact_root, output_root, _ = campaign._campaign_paths(
        tmp_path,
        "orphaned_campaign",
    )
    stale_output = output_root / "online" / "rep01" / "native_action"
    stale_output.mkdir(parents=True)

    errors = campaign._stale_campaign_arm_root_errors(
        artifact_root,
        output_root,
    )

    assert errors == [f"stale campaign arm root exists: {output_root / 'online'}"]


def test_prepare_rejects_stale_arm_artifacts_when_manifest_was_deleted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    fixture = tmp_path / "fixture.json"
    _write_json(
        benchmark,
        {
            "splits": {
                "full_benchmark": [
                    {"name": f"task_{index}"}
                    for index in range(campaign.EXPECTED_TASKS_PER_RUN)
                ]
            }
        },
    )
    fixture.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(campaign, "PINNED_BENCHMARK_SHA256", _sha256(benchmark))
    monkeypatch.setattr(
        campaign,
        "PINNED_EXTERNAL_FIXTURE_SHA256",
        _sha256(fixture),
    )
    monkeypatch.setattr(
        campaign,
        "_require_clean_git",
        lambda repo_root: {
            "git_commit": "commit",
            "git_tree": "tree",
            "fixed_toolsandbox_timestamp": campaign.DEFAULT_FIXED_NOW,
            "python_version": "3.12.7",
            "python_implementation": "CPython",
            "platform_system": "Darwin",
            "platform_machine": "arm64",
            "isolated_environment": True,
            "environment_lock_sha256": "lock-sha",
            "external_distribution_count": 108,
            "external_distribution_sha256": "distribution-sha",
            "execution_environment": dict(campaign.PUBLICATION_EXECUTION_ENV),
            "runtime_digest": "runtime",
            "generation_settings_digest": "generation",
        },
    )
    monkeypatch.setattr(
        campaign,
        "_validated_sample_report",
        lambda repo_root, report_path, expected_identity: {
            "path": "sample.json",
            "sha256": "sample-sha",
            "run_root": "sample_run",
            "status": "pass",
            "release_identity": {
                field: expected_identity[field]
                for field in campaign.SAMPLE_RELEASE_IDENTITY_FIELDS
            },
        },
    )
    campaign_id = "orphaned_prepare"
    _, output_root, manifest_path = campaign._campaign_paths(tmp_path, campaign_id)
    stale_output = output_root / "online" / "rep01" / "native_action"
    stale_output.mkdir(parents=True)
    assert not manifest_path.exists()
    args = argparse.Namespace(
        repo_root=tmp_path,
        sample_validation_report=Path("sample.json"),
        benchmark_manifest=benchmark.relative_to(tmp_path),
        external_fixture=fixture.relative_to(tmp_path),
        campaign_id=campaign_id,
        force=False,
        expected_online_runs=campaign.EXPECTED_REPLICATIONS,
        fixed_now=campaign.DEFAULT_FIXED_NOW,
        max_parallel=campaign.MAX_CONCURRENCY,
        bootstrap_iterations=campaign.DEFAULT_BOOTSTRAP_ITERATIONS,
        randomization_iterations=campaign.DEFAULT_RANDOMIZATION_ITERATIONS,
        seed=campaign.DEFAULT_ANALYSIS_SEED,
    )

    with pytest.raises(SystemExit, match="stale arm artifacts"):
        campaign.prepare_campaign(args)


@pytest.mark.parametrize(
    ("status", "resume_incomplete", "expected_error"),
    [
        ("running", False, "Refusing automatic recovery"),
        ("running", True, "Refusing automatic recovery"),
        ("incomplete", False, "requires --resume-incomplete"),
    ],
)
def test_campaign_execution_rejects_running_or_unreviewed_incomplete_manifest(
    status: str,
    resume_incomplete: bool,
    expected_error: str,
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "campaign_manifest.json"
    campaign_id = "locked_campaign"
    artifact_root, _, _ = campaign._campaign_paths(tmp_path, campaign_id)
    artifact_root.mkdir(parents=True)
    _write_json(
        manifest_path,
        {"status": status, "campaign_id": campaign_id},
    )
    args = type(
        "Args",
        (),
        {
            "repo_root": tmp_path,
            "campaign_manifest": manifest_path,
            "approve_execution": True,
            "resume_incomplete": resume_incomplete,
        },
    )()

    with pytest.raises(SystemExit, match=expected_error):
        campaign.run_campaign(args)
    assert not (artifact_root / campaign.CAMPAIGN_EXECUTION_LOCK_NAME).exists()


def test_campaign_execution_refuses_preexisting_atomic_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign_id = "claimed_campaign"
    artifact_root, _, _ = campaign._campaign_paths(tmp_path, campaign_id)
    artifact_root.mkdir(parents=True)
    lock_path = artifact_root / campaign.CAMPAIGN_EXECUTION_LOCK_NAME
    lock_path.write_text('{"pid": 123}\n', encoding="utf-8")
    manifest_path = artifact_root / "campaign_manifest.json"
    _write_json(
        manifest_path,
        {"status": "prepared", "campaign_id": campaign_id},
    )
    prerequisite_called = False

    def prerequisites(repo_root: Path, manifest: dict[str, Any]) -> list[str]:
        nonlocal prerequisite_called
        prerequisite_called = True
        return []

    monkeypatch.setattr(
        campaign,
        "_campaign_prerequisite_errors",
        prerequisites,
    )
    args = type(
        "Args",
        (),
        {
            "repo_root": tmp_path,
            "campaign_manifest": manifest_path,
            "approve_execution": True,
        },
    )()

    with pytest.raises(SystemExit, match="execution lock already exists"):
        campaign.run_campaign(args)

    assert not prerequisite_called
    assert lock_path.read_text(encoding="utf-8") == '{"pid": 123}\n'


def test_campaign_execution_approval_gate_precedes_atomic_claim(
    tmp_path: Path,
) -> None:
    campaign_id = "approval_gated_campaign"
    artifact_root, _, _ = campaign._campaign_paths(tmp_path, campaign_id)
    artifact_root.mkdir(parents=True)
    manifest_path = artifact_root / "campaign_manifest.json"
    _write_json(
        manifest_path,
        {"status": "prepared", "campaign_id": campaign_id},
    )
    before = manifest_path.read_bytes()
    args = argparse.Namespace(
        repo_root=tmp_path,
        campaign_manifest=manifest_path,
        approve_execution=False,
    )

    with pytest.raises(SystemExit, match="execution is gated"):
        campaign.run_campaign(args)

    assert manifest_path.read_bytes() == before
    assert not (artifact_root / campaign.CAMPAIGN_EXECUTION_LOCK_NAME).exists()


def test_runtime_parallelism_cannot_override_prepared_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        campaign,
        "_campaign_prerequisite_errors",
        lambda repo_root, manifest: [],
    )
    manifest = {
        "status": "prepared",
        "maximum_parallel_runs": campaign.MAX_CONCURRENCY,
    }
    args = argparse.Namespace(
        max_parallel=campaign.MAX_CONCURRENCY - 1,
        resume_incomplete=False,
    )

    with pytest.raises(SystemExit, match="cannot override the prepared campaign plan"):
        campaign._run_claimed_campaign(
            args,
            tmp_path,
            tmp_path / "campaign_manifest.json",
            manifest,
        )


def test_sample_report_validation_is_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    report = tmp_path / "publication_validation_report.json"
    payload: dict[str, Any] = {
        "status": "pass",
        "publication_gate_purpose": (campaign.PUBLICATION_GATE_PURPOSE_RELEASE_SAMPLE),
        "run_root": "run",
        "thresholds_path": "thresholds.json",
        "integrity_verification": {
            "status": "pass",
            "run_root": "run",
            "publication_provenance": {
                "git_commit": "commit",
                "git_tree": "tree",
                "fixed_toolsandbox_timestamp": campaign.DEFAULT_FIXED_NOW,
                "python_version": "3.12.7",
                "python_implementation": "CPython",
                "platform_system": "Darwin",
                "platform_machine": "arm64",
                "isolated_environment": True,
                "environment_lock_sha256": "lock-sha",
                "external_distribution_count": 108,
                "external_distribution_sha256": "distribution-sha",
                "execution_environment": dict(campaign.PUBLICATION_EXECUTION_ENV),
            },
        },
    }
    _write_json(report, payload)
    before = report.read_bytes()
    calls: list[dict[str, Any]] = []

    def verify_sample(
        search_root: Path,
        *,
        output_path: Path | None = None,
        write_report: bool = True,
    ) -> dict[str, Any]:
        calls.append(
            {
                "search_root": search_root,
                "output_path": output_path,
                "write_report": write_report,
            }
        )
        return {
            "status": "pass",
            "publication_gate_purpose": (
                campaign.PUBLICATION_GATE_PURPOSE_RELEASE_SAMPLE
            ),
            "run_root": str(run_root),
            "thresholds_path": str(tmp_path / "thresholds.json"),
            "integrity_verification": {
                "status": "pass",
                "run_root": str(run_root),
                "publication_provenance": payload["integrity_verification"][
                    "publication_provenance"
                ],
            },
        }

    monkeypatch.setattr(campaign, "verify_sample", verify_sample)

    expected_identity = {
        **payload["integrity_verification"]["publication_provenance"],
        "runtime_digest": "runtime",
        "generation_settings_digest": "generation",
    }
    validated = campaign._validated_sample_report(
        tmp_path,
        report,
        expected_identity,
    )

    assert report.read_bytes() == before
    assert validated["sha256"] == hashlib.sha256(before).hexdigest()
    assert validated["run_root"] == "run"
    assert validated["release_identity"]["git_tree"] == "tree"
    assert calls == [
        {
            "search_root": run_root,
            "output_path": report,
            "write_report": False,
        }
    ]


def test_sample_report_validation_rejects_different_current_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    provenance = {
        "git_commit": "commit",
        "git_tree": "sample-tree",
        "fixed_toolsandbox_timestamp": campaign.DEFAULT_FIXED_NOW,
        "python_version": "3.12.7",
        "python_implementation": "CPython",
        "platform_system": "Darwin",
        "platform_machine": "arm64",
        "isolated_environment": True,
        "environment_lock_sha256": "lock-sha",
        "external_distribution_count": 108,
        "external_distribution_sha256": "distribution-sha",
        "execution_environment": dict(campaign.PUBLICATION_EXECUTION_ENV),
    }
    payload = {
        "status": "pass",
        "publication_gate_purpose": (campaign.PUBLICATION_GATE_PURPOSE_RELEASE_SAMPLE),
        "run_root": str(run_root),
        "integrity_verification": {
            "status": "pass",
            "run_root": str(run_root),
            "publication_provenance": provenance,
        },
    }
    report = tmp_path / "publication_validation_report.json"
    _write_json(report, payload)
    monkeypatch.setattr(
        campaign,
        "verify_sample",
        lambda *args, **kwargs: copy.deepcopy(payload),
    )
    expected_identity = {**provenance, "git_tree": "current-tree"}

    with pytest.raises(ValueError, match="current release identity: git_tree"):
        campaign._validated_sample_report(
            tmp_path,
            report,
            expected_identity,
        )


def test_default_campaign_scope_is_one_online_wave_with_dual_v3_endpoints() -> None:
    assert campaign.DEFAULT_CAMPAIGN_SCOPE == "online-only"
    assert campaign._planned_arms(campaign.DEFAULT_CAMPAIGN_SCOPE) == ("online",)
    assert campaign._expected_execution_waves(campaign.MAX_CONCURRENCY) == [
        {
            "wave": 1,
            "description": (
                "Ten new online-build replications, each with a same-run fresh control."
            ),
            "maximum_parallel": campaign.MAX_CONCURRENCY,
        }
    ]
    plan = campaign._expected_statistical_plan()
    audited = plan["performance_endpoints"]["audited_current_all_tasks"]
    paper = plan["performance_endpoints"]["paper_comparable_historical_subset"]
    assert plan["hypothesis_2_confirmatory_rule"] == {
        "analysis_role": "confirmatory_two_way_run_task_clustered",
        "target_contrast": "candidate_mean - 1.10 * control_mean",
        "estimate_requirement": "audited_relative_outcome_lift_percent >= 10",
        "two_way_uncertainty_requirement": (
            "two_way_run_task_bootstrap_95_ci_lower_for_target_contrast > 0"
        ),
        "run_cluster_requirement": (
            "run_cluster_bootstrap_95_ci_lower_for_target_contrast > 0"
        ),
        "run_sign_flip_requirement": "two_sided_exact_p < 0.05",
        "replication_unit": "independently_evolved_registry_run",
        "task_unit": "fixed_matched_benchmark_task",
        "iid_task_analysis_role": "descriptive_only",
    }
    assert plan["hypothesis_3_analysis_rule"] == {
        "analysis_role": "selection_conditioned_descriptive_only",
        "subset": "matched_tasks_with_at_least_one_generated_tool_call",
        "causal_attribution_allowed": False,
        "classification": "descriptive_only_no_hypothesis_support_decision",
        "threshold_role": "predeclared_descriptive_reference_only",
    }
    assert audited == {
        "metric_field": "outcome_similarity",
        "evaluator_version": "sage_outcome_contracts_v9",
        "task_count_per_run": 1032,
        "expected_matched_pairs": 10_320,
        "aggregate_statistics": None,
    }
    assert paper == {
        "metric_field": "online_feedback_outcome_similarity",
        "evaluator_version": "sage_paper_outcome_contracts_v1",
        "task_count_per_run": 800,
        "expected_matched_pairs": 8_000,
        "aggregate_statistics": None,
    }
    assert campaign._expected_claim_safeguards()["parallel_arms"] is True
    assert (
        campaign._expected_claim_safeguards()["replication_inclusion_policy"]
        == "integrity_provenance_completeness_only"
    )
    assert (
        campaign._expected_claim_safeguards()[
            "observed_performance_controls_replication_inclusion"
        ]
        is False
    )


def test_optional_frozen_scope_requires_an_explicit_second_wave() -> None:
    waves = campaign._expected_execution_waves(
        campaign.MAX_CONCURRENCY,
        "online-and-frozen",
    )

    assert campaign._planned_arms("online-and-frozen") == ("online", "frozen")
    assert [wave["wave"] for wave in waves] == [1, 2]


def test_job_command_exports_provenance_and_exact_interpreter_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    publication_python = tmp_path / ".venv-publication" / "bin" / "python"
    publication_python.parent.mkdir(parents=True)
    publication_python.write_text("#!/bin/sh\n", encoding="utf-8")
    publication_python.chmod(0o755)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("SAGE_BATCH_NO_DASHBOARD_OPEN", "1")

    command, env, _ = campaign._job_command(
        repo_root=tmp_path,
        manifest=manifest,
        pair=manifest["run_pairs"][0],
        arm="online",
        port=64200,
    )

    assert command[-3:] == ["64200", "native-only", "campaign-inclusion"]
    assert env["PATH"].split(os.pathsep)[0] == str(publication_python.parent.resolve())
    assert env["SAGE_TS_RUNTIME_DIGEST"] == "runtime"
    assert env["SAGE_TS_GENERATION_SETTINGS_DIGEST"] == "generation"
    assert env["SAGE_TS_PROMPT_POLICY_DIGEST"] == "sage_ts_protocol_v1"
    assert "SAGE_BATCH_NO_DASHBOARD_OPEN" not in env


def test_port_reservation_rejects_collision_and_releases_all_ports() -> None:
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupied.bind(("127.0.0.1", 0))
    occupied.listen(1)
    port = int(occupied.getsockname()[1])
    try:
        with pytest.raises(ValueError, match=f"port {port} is unavailable"):
            with campaign._reserve_dashboard_ports([port]):
                pytest.fail("occupied port was reserved")
    finally:
        occupied.close()

    with campaign._reserve_dashboard_ports([port]):
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with pytest.raises(OSError):
                probe.bind(("127.0.0.1", port))
        finally:
            probe.close()

    rebound = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        rebound.bind(("127.0.0.1", port))
    finally:
        rebound.close()


@pytest.mark.parametrize("ports", [[64000, 64000], [0], [65536]])
def test_port_reservation_rejects_nonunique_or_invalid_blocks(
    ports: list[int],
) -> None:
    with pytest.raises(ValueError):
        with campaign._reserve_dashboard_ports(ports):
            pytest.fail("invalid port block was reserved")


def test_parallel_wave_attestation_recomputes_overlap_and_bindings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)

    record = _record_parallel_wave(manifest)

    assert record["verified"] is True
    assert record["global_overlap_ns"] > 0
    assert campaign._parallel_wave_record_errors(manifest, 1) == []

    record["jobs"][1]["process_pid"] = record["jobs"][0]["process_pid"]
    manifest["run_pairs"][1]["online"]["process_pid"] = record["jobs"][0]["process_pid"]
    duplicate_pid_errors = campaign._parallel_wave_record_errors(manifest, 1)

    assert "wave 1 did not use 10 distinct child processes" in duplicate_pid_errors

    record = _record_parallel_wave(manifest)
    record["jobs"][1]["port"] = record["jobs"][0]["port"]
    manifest["run_pairs"][1]["online"]["dashboard_port"] = record["jobs"][0]["port"]
    duplicate_port_errors = campaign._parallel_wave_record_errors(manifest, 1)

    assert "wave 1 did not use 10 distinct dashboard ports" in duplicate_port_errors

    nonoverlapping = _record_parallel_wave(manifest, overlapping=False)
    errors = campaign._parallel_wave_record_errors(manifest, 1)

    assert nonoverlapping["verified"] is False
    assert nonoverlapping["global_overlap_ns"] <= 0
    assert "wave 1 lacks positive across-job process overlap" in errors
    assert "wave 1 parallel execution is not verified" in errors


def test_dashboard_refresh_shutdown_fails_closed_if_preview_writer_remains_alive() -> (
    None
):
    stop_refresh = threading.Event()
    joins: list[int | None] = []

    class StuckRefreshThread:
        def join(self, timeout: int | None = None) -> None:
            joins.append(timeout)

        def is_alive(self) -> bool:
            return True

    error = campaign._stop_dashboard_refresh(
        stop_refresh,
        StuckRefreshThread(),  # type: ignore[arg-type]
    )

    assert stop_refresh.is_set()
    assert joins == [30]
    assert error is not None
    assert "stale preview could publish afterward" in error


def test_run_wave_consumes_and_records_every_future_before_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    manifest_path = tmp_path / "campaign_manifest.json"
    _write_json(manifest_path, manifest)
    execution_calls: list[int] = []

    def execute_job(**kwargs: Any) -> dict[str, Any]:
        replicate = int(kwargs["pair"]["replication"])
        execution_calls.append(replicate)
        if replicate == 1:
            raise RuntimeError("synthetic worker failure")
        return {
            "replication": replicate,
            "arm": "online",
            "port": kwargs["port"],
            "return_code": 0,
            "completed_at": "2026-09-10T00:01:00Z",
            "log_path": str(
                Path(manifest["paths"]["artifact_root"])
                / "launcher_logs"
                / f"rep{replicate:02d}_online.log"
            ),
            "verification_error": None,
            "verification_status": "pass",
            "run_root": str(Path(kwargs["pair"]["online"]["search_root"]) / "run"),
            "process_pid": 1000 + replicate,
            "process_started_monotonic_ns": 100,
            "process_completed_monotonic_ns": 200,
            "endpoint_measurements": {
                "status": "pass",
                "audited_current_all_tasks": {"task_count": 1032},
                "paper_comparable_historical_subset": {"task_count": 800},
            },
        }

    monkeypatch.setattr(campaign, "_execute_job", execute_job)
    monkeypatch.setattr(campaign, "_refresh_dashboard", lambda **kwargs: None)
    monkeypatch.setattr(
        campaign,
        "_reserve_dashboard_ports",
        lambda ports: nullcontext(),
    )

    with pytest.raises(RuntimeError, match="all job results were recorded"):
        campaign._run_wave(
            repo_root=tmp_path,
            manifest_path=manifest_path,
            manifest=manifest,
            jobs=[(1, "online"), (2, "online")],
            max_parallel=2,
            base_port=64200,
            wave=1,
        )

    saved = campaign._load_manifest(manifest_path)
    assert sorted(execution_calls) == [1, 2]
    assert saved["status"] == "incomplete"
    assert saved["run_pairs"][0]["online"]["execution_status"] == "failed"
    assert saved["run_pairs"][0]["online"]["return_code"] == 98
    assert saved["run_pairs"][0]["online"]["dashboard_port"] == 64200
    assert (
        "synthetic worker failure"
        in saved["run_pairs"][0]["online"]["verification_error"]
    )
    assert (
        saved["run_pairs"][0]["online"]["recovery_disposition"]
        == "preserve_artifacts_and_start_new_campaign"
    )
    assert saved["run_pairs"][1]["online"]["execution_status"] == "completed"
    assert saved["run_pairs"][1]["online"]["return_code"] == 0
    assert saved["run_pairs"][1]["online"]["verification_status"] == "pass"
    assert saved["run_pairs"][1]["online"]["dashboard_port"] == 64201
    assert saved["run_pairs"][1]["online"]["run_root"].endswith(
        "/online/rep02/native_action/run"
    )
    assert (
        saved["run_pairs"][1]["online"]["endpoint_measurements"][
            "paper_comparable_historical_subset"
        ]["task_count"]
        == 800
    )
    assert any(
        event.get("event") == "wave_1_dashboard_ports_reserved"
        and event.get("ports") == [64200, 64201]
        for event in saved["execution_events"]
    )


def test_run_wave_rejects_ten_successes_without_global_process_overlap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    manifest_path = tmp_path / "campaign_manifest.json"
    _write_json(manifest_path, manifest)

    def execute_job(**kwargs: Any) -> dict[str, Any]:
        replication = int(kwargs["pair"]["replication"])
        started = 100 + replication
        return {
            "replication": replication,
            "arm": "online",
            "port": kwargs["port"],
            "return_code": 0,
            "completed_at": "2026-09-10T00:01:00Z",
            "log_path": str(
                Path(manifest["paths"]["artifact_root"])
                / "launcher_logs"
                / f"rep{replication:02d}_online.log"
            ),
            "verification_error": None,
            "verification_status": "pass",
            "run_root": str(Path(kwargs["pair"]["online"]["search_root"]) / "run"),
            "endpoint_measurements": {
                "status": "pass",
                "audited_current_all_tasks": {"task_count": 1032},
                "paper_comparable_historical_subset": {"task_count": 800},
            },
            "process_pid": 2000 + replication,
            "process_started_monotonic_ns": started,
            "process_completed_monotonic_ns": started + 1,
        }

    monkeypatch.setattr(campaign, "_execute_job", execute_job)
    monkeypatch.setattr(campaign, "_refresh_dashboard", lambda **kwargs: None)
    monkeypatch.setattr(
        campaign,
        "_reserve_dashboard_ports",
        lambda ports: nullcontext(),
    )

    with pytest.raises(RuntimeError, match="10 failed job"):
        campaign._run_wave(
            repo_root=tmp_path,
            manifest_path=manifest_path,
            manifest=manifest,
            jobs=[(replication, "online") for replication in range(1, 11)],
            max_parallel=10,
            base_port=64200,
            wave=1,
        )

    saved = campaign._load_manifest(manifest_path)
    assert saved["status"] == "incomplete"
    assert saved["parallel_wave_execution"]["1"]["verified"] is False
    assert saved["parallel_wave_execution"]["1"]["global_overlap_ns"] <= 0
    assert all(
        pair["online"]["execution_status"] == "failed"
        and pair["online"]["return_code"] == 96
        and pair["online"]["process_return_code"] == 0
        and pair["online"]["verification_status"] == "fail"
        for pair in saved["run_pairs"]
    )


def test_worker_result_binding_mismatch_fails_the_expected_job(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    manifest_path = tmp_path / "campaign_manifest.json"
    _write_json(manifest_path, manifest)
    expected_log = (
        Path(manifest["paths"]["artifact_root"]) / "launcher_logs" / "rep01_online.log"
    )

    monkeypatch.setattr(
        campaign,
        "_execute_job",
        lambda **kwargs: {
            "replication": 2,
            "arm": "online",
            "port": 65000,
            "return_code": 0,
            "completed_at": "2026-09-10T00:01:00Z",
            "log_path": str(expected_log),
            "verification_error": None,
            "verification_status": "pass",
            "run_root": str(
                Path(manifest["run_pairs"][0]["online"]["search_root"]) / "run"
            ),
            "process_pid": 1001,
            "process_started_monotonic_ns": 100,
            "process_completed_monotonic_ns": 200,
            "endpoint_measurements": {
                "status": "pass",
                "audited_current_all_tasks": {"task_count": 1032},
                "paper_comparable_historical_subset": {"task_count": 800},
            },
        },
    )
    monkeypatch.setattr(campaign, "_refresh_dashboard", lambda **kwargs: None)
    monkeypatch.setattr(
        campaign,
        "_reserve_dashboard_ports",
        lambda ports: nullcontext(),
    )

    with pytest.raises(RuntimeError, match="may not be retried"):
        campaign._run_wave(
            repo_root=tmp_path,
            manifest_path=manifest_path,
            manifest=manifest,
            jobs=[(1, "online")],
            max_parallel=1,
            base_port=64200,
            wave=1,
        )

    saved = campaign._load_manifest(manifest_path)
    entry = saved["run_pairs"][0]["online"]
    assert saved["status"] == "incomplete"
    assert entry["execution_status"] == "failed"
    assert entry["return_code"] == 98
    assert "replication, port" in entry["verification_error"]
    assert entry["dashboard_port"] == 64200


def test_incomplete_failed_job_is_preserved_and_never_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    manifest["status"] = "incomplete"
    failed_entry = manifest["run_pairs"][0]["online"]
    failed_entry.update(
        {
            "execution_status": "failed",
            "return_code": 1,
            "started_at": "2026-09-10T00:00:00Z",
            "completed_at": "2026-09-10T00:01:00Z",
            "dashboard_port": 64200,
            "log_path": str(
                Path(manifest["paths"]["artifact_root"])
                / "launcher_logs"
                / "rep01_online.log"
            ),
            "verification_error": "launcher failed",
            "recovery_disposition": "preserve_artifacts_and_start_new_campaign",
        }
    )
    partial_output = tmp_path / failed_entry["search_root"] / "partial.json"
    partial_registry = tmp_path / failed_entry["registry_dir"] / "partial.json"
    _write_json(partial_output, {"partial": True})
    _write_json(partial_registry, {"partial": True})
    manifest_path = tmp_path / "campaign_manifest.json"
    _write_json(manifest_path, manifest)
    run_wave_called = False
    dashboard_called = False

    monkeypatch.setattr(
        campaign,
        "_reconcile_completed_entries",
        lambda repo_root, observed: None,
    )

    def run_wave(**kwargs: Any) -> None:
        nonlocal run_wave_called
        run_wave_called = True

    def open_dashboard(**kwargs: Any) -> str:
        nonlocal dashboard_called
        dashboard_called = True
        return "file:///should-not-open.html"

    monkeypatch.setattr(campaign, "_run_wave", run_wave)
    monkeypatch.setattr(campaign, "_open_aggregate_dashboard", open_dashboard)
    args = argparse.Namespace(
        resume_incomplete=True,
        max_parallel=None,
        wave="all",
        base_port=64200,
    )

    with pytest.raises(SystemExit, match="Prepare a new campaign ID"):
        campaign._run_claimed_campaign(
            args,
            tmp_path,
            manifest_path,
            manifest,
        )

    assert not run_wave_called
    assert not dashboard_called
    assert partial_output.read_text(encoding="utf-8") == '{"partial": true}\n'
    assert partial_registry.read_text(encoding="utf-8") == '{"partial": true}\n'


def test_run_wave_checks_entire_port_block_before_starting_jobs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    manifest_path = tmp_path / "campaign_manifest.json"
    before = copy.deepcopy(manifest)
    executed = False
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupied.bind(("127.0.0.1", 0))
    occupied.listen(1)
    port = int(occupied.getsockname()[1])

    def execute_job(**kwargs: Any) -> dict[str, Any]:
        nonlocal executed
        executed = True
        raise AssertionError("job launched before port preflight")

    monkeypatch.setattr(campaign, "_execute_job", execute_job)
    try:
        with pytest.raises(ValueError, match=f"port {port} is unavailable"):
            campaign._run_wave(
                repo_root=tmp_path,
                manifest_path=manifest_path,
                manifest=manifest,
                jobs=[(1, "online")],
                max_parallel=1,
                base_port=port,
                wave=1,
            )
    finally:
        occupied.close()

    assert not executed
    assert manifest == before
    assert not manifest_path.exists()


def test_aggregate_dashboard_opens_with_external_macos_handler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dashboard_dir = tmp_path / "dashboard"
    dashboard_dir.mkdir()
    dashboard = dashboard_dir / "chapter4_evidence.html"
    dashboard.write_text("<html></html>\n", encoding="utf-8")
    calls: list[list[str]] = []
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: calls.append(command),
    )

    url = campaign._open_aggregate_dashboard(
        repo_root=tmp_path,
        manifest={"paths": {"dashboard_dir": "dashboard"}},
    )

    assert url == dashboard.resolve().as_uri()
    assert calls == [["open", url]]


def test_online_only_campaign_completes_after_one_ten_job_wave(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    manifest_path = tmp_path / "campaign_manifest.json"
    _write_json(manifest_path, manifest)
    waves: list[tuple[int, list[tuple[int, str]]]] = []
    launched = False

    monkeypatch.setattr(
        campaign,
        "_campaign_prerequisite_errors",
        lambda repo_root, observed: [],
    )
    monkeypatch.setattr(campaign, "_refresh_dashboard", lambda **kwargs: None)
    monkeypatch.setattr(
        campaign,
        "_open_aggregate_dashboard",
        lambda **kwargs: "file:///aggregate-dashboard.html",
    )
    monkeypatch.setattr(
        campaign,
        "_entry_is_valid",
        lambda *args, **kwargs: launched,
    )
    monkeypatch.setattr(campaign, "_reconcile_completed_entries", lambda *args: None)
    monkeypatch.setattr(campaign, "_parallel_wave_execution_errors", lambda _: [])

    def run_wave(**kwargs: Any) -> None:
        nonlocal launched
        waves.append((kwargs["wave"], kwargs["jobs"]))
        launched = True

    monkeypatch.setattr(
        campaign,
        "_run_wave",
        run_wave,
    )
    args = argparse.Namespace(
        resume_incomplete=False,
        max_parallel=None,
        wave="all",
        base_port=64200,
    )

    campaign._run_claimed_campaign(
        args,
        tmp_path,
        manifest_path,
        manifest,
    )

    saved = campaign._load_manifest(manifest_path)
    assert waves == [
        (
            1,
            [(replication, "online") for replication in range(1, 11)],
        )
    ]
    assert saved["status"] == "complete"
    assert any(
        event.get("event") == "aggregate_dashboard_opened"
        and event.get("external_browser") is True
        for event in saved["execution_events"]
    )


def test_terminal_dashboard_failure_cannot_leave_campaign_complete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    manifest_path = tmp_path / "campaign_manifest.json"
    _write_json(manifest_path, manifest)
    dashboard_dir = tmp_path / manifest["paths"]["dashboard_dir"]
    dashboard_dir.mkdir(parents=True)
    dashboard_html = dashboard_dir / EVIDENCE_HTML_NAME
    dashboard_json = dashboard_dir / EVIDENCE_DATA_NAME
    dashboard_html.write_text("stale complete html", encoding="utf-8")
    dashboard_json.write_text("stale complete json", encoding="utf-8")
    launched = False

    monkeypatch.setattr(
        campaign,
        "_campaign_prerequisite_errors",
        lambda repo_root, observed: [],
    )

    def refresh_dashboard(**kwargs: Any) -> None:
        if kwargs["final"]:
            raise RuntimeError("synthetic terminal dashboard failure")

    monkeypatch.setattr(campaign, "_refresh_dashboard", refresh_dashboard)
    monkeypatch.setattr(
        campaign,
        "_open_aggregate_dashboard",
        lambda **kwargs: "file:///aggregate-dashboard.html",
    )
    monkeypatch.setattr(
        campaign,
        "_entry_is_valid",
        lambda *args, **kwargs: launched,
    )
    monkeypatch.setattr(campaign, "_reconcile_completed_entries", lambda *args: None)
    monkeypatch.setattr(campaign, "_parallel_wave_execution_errors", lambda _: [])

    def run_wave(**kwargs: Any) -> None:
        nonlocal launched
        launched = True

    monkeypatch.setattr(campaign, "_run_wave", run_wave)
    args = argparse.Namespace(
        resume_incomplete=False,
        max_parallel=None,
        wave="all",
        base_port=64200,
    )

    with pytest.raises(RuntimeError, match="synthetic terminal dashboard failure"):
        campaign._run_claimed_campaign(
            args,
            tmp_path,
            manifest_path,
            manifest,
        )

    saved = campaign._load_manifest(manifest_path)
    assert saved["status"] == "incomplete"
    assert not dashboard_html.exists()
    assert not dashboard_json.exists()
    archived_html = list(
        dashboard_dir.glob("chapter4_evidence.failed-verification-*.html")
    )
    archived_json = list(
        dashboard_dir.glob("chapter4_evidence_data.failed-verification-*.json")
    )
    assert len(archived_html) == len(archived_json) == 1
    assert archived_html[0].read_text(encoding="utf-8") == "stale complete html"
    assert archived_json[0].read_text(encoding="utf-8") == "stale complete json"
    assert saved["execution_events"][-2]["event"] == "campaign_execution_finished"
    assert saved["execution_events"][-2]["complete"] is False
    assert (
        saved["execution_events"][-2]["terminal_dashboard_error"]
        == "RuntimeError: synthetic terminal dashboard failure"
    )
    assert saved["execution_events"][-1] == {
        "at": saved["execution_events"][-1]["at"],
        "event": "terminal_dashboard_render_failed",
        "error": "RuntimeError: synthetic terminal dashboard failure",
        "recovery_disposition": (
            "preserve_verified_runs_and_retry_finalization_after_review"
        ),
        "archived_dashboard_artifacts": saved["execution_events"][-1][
            "archived_dashboard_artifacts"
        ],
        "dashboard_archive_errors": [],
    }


def test_verify_complete_campaign_preserves_final_analysis_iterations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    manifest["status"] = "complete"
    manifest_path = tmp_path / "campaign_manifest.json"
    _write_json(manifest_path, manifest)
    refresh_calls: list[dict[str, Any]] = []

    monkeypatch.setattr(
        campaign,
        "_campaign_prerequisite_errors",
        lambda repo_root, observed: [],
    )
    monkeypatch.setattr(campaign, "_entry_complete", lambda *args: True)
    monkeypatch.setattr(
        campaign,
        "_verify_publication_entry",
        lambda *args, **kwargs: {"run_root": "run"},
    )
    monkeypatch.setattr(
        campaign,
        "_refresh_dashboard",
        lambda **kwargs: refresh_calls.append(kwargs),
    )

    campaign.verify_campaign(
        argparse.Namespace(
            repo_root=tmp_path,
            campaign_manifest=manifest_path,
        )
    )

    assert len(refresh_calls) == 1
    assert refresh_calls[0]["final"] is True


def test_verify_terminal_dashboard_failure_downgrades_complete_campaign(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    manifest["status"] = "complete"
    manifest_path = tmp_path / "campaign_manifest.json"
    _write_json(manifest_path, manifest)
    dashboard_dir = tmp_path / manifest["paths"]["dashboard_dir"]
    dashboard_dir.mkdir(parents=True)
    dashboard_html = dashboard_dir / EVIDENCE_HTML_NAME
    dashboard_json = dashboard_dir / EVIDENCE_DATA_NAME
    dashboard_html.write_text("stale complete html", encoding="utf-8")
    dashboard_json.write_text("stale complete json", encoding="utf-8")

    monkeypatch.setattr(
        campaign,
        "_campaign_prerequisite_errors",
        lambda repo_root, observed: [],
    )
    monkeypatch.setattr(campaign, "_entry_complete", lambda *args: True)
    monkeypatch.setattr(
        campaign,
        "_verify_publication_entry",
        lambda *args, **kwargs: {"run_root": "run"},
    )
    monkeypatch.setattr(
        campaign,
        "_refresh_dashboard",
        lambda **kwargs: (_ for _ in ()).throw(
            RuntimeError("synthetic verification dashboard failure")
        ),
    )

    with pytest.raises(RuntimeError, match="synthetic verification dashboard failure"):
        campaign.verify_campaign(
            argparse.Namespace(
                repo_root=tmp_path,
                campaign_manifest=manifest_path,
            )
        )

    saved = campaign._load_manifest(manifest_path)
    assert saved["status"] == "incomplete"
    assert not dashboard_html.exists()
    assert not dashboard_json.exists()
    archived_html = list(
        dashboard_dir.glob("chapter4_evidence.failed-verification-*.html")
    )
    archived_json = list(
        dashboard_dir.glob("chapter4_evidence_data.failed-verification-*.json")
    )
    assert len(archived_html) == len(archived_json) == 1
    assert archived_html[0].read_text(encoding="utf-8") == "stale complete html"
    assert archived_json[0].read_text(encoding="utf-8") == "stale complete json"
    assert saved["execution_events"][-1] == {
        "at": saved["execution_events"][-1]["at"],
        "event": "terminal_dashboard_render_failed",
        "error": "RuntimeError: synthetic verification dashboard failure",
        "recovery_disposition": (
            "preserve_verified_runs_and_retry_finalization_after_review"
        ),
        "archived_dashboard_artifacts": saved["execution_events"][-1][
            "archived_dashboard_artifacts"
        ],
        "dashboard_archive_errors": [],
    }


def test_online_only_campaign_rejects_wave_two_before_dashboard_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    manifest_path = tmp_path / "campaign_manifest.json"
    _write_json(manifest_path, manifest)
    dashboard_touched = False

    monkeypatch.setattr(
        campaign,
        "_campaign_prerequisite_errors",
        lambda repo_root, observed: [],
    )

    def refresh_dashboard(**kwargs: Any) -> None:
        nonlocal dashboard_touched
        dashboard_touched = True

    monkeypatch.setattr(campaign, "_refresh_dashboard", refresh_dashboard)
    args = argparse.Namespace(
        resume_incomplete=False,
        max_parallel=None,
        wave="2",
        base_port=64200,
    )

    with pytest.raises(SystemExit, match="not part of campaign scope 'online-only'"):
        campaign._run_claimed_campaign(
            args,
            tmp_path,
            manifest_path,
            manifest,
        )

    assert not dashboard_touched
