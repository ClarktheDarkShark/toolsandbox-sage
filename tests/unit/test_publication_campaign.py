from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import scripts.run_chapter4_evidence_campaign as campaign


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid_campaign(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
        run_pairs.append(
            {
                "replication": replication,
                "online": {
                    "source": "campaign_online_build_fresh_control",
                    "run_root": "",
                    "search_root": campaign._relative(
                        tmp_path,
                        output_root / "online" / rep_label / "native_action",
                    ),
                    "registry_dir": online_registry,
                    "execution_status": "queued",
                },
                "frozen": {
                    "source": "paired_frozen_registry_reuse",
                    "run_root": "",
                    "search_root": campaign._relative(
                        tmp_path,
                        output_root / "frozen" / rep_label / "frozen_registry",
                    ),
                    "registry_dir": campaign._relative(
                        tmp_path,
                        artifact_root
                        / "frozen"
                        / rep_label
                        / "frozen_registry_registry",
                    ),
                    "source_registry_dir": online_registry,
                    "execution_status": "queued",
                },
            }
        )

    manifest = {
        "schema_version": 2,
        "campaign_id": campaign_id,
        "status": "prepared",
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
        "control_execution": campaign._expected_control_execution(),
        "fixed_toolsandbox_timestamp": campaign.DEFAULT_FIXED_NOW,
        "expected_online_runs": campaign.EXPECTED_REPLICATIONS,
        "expected_frozen_runs": campaign.EXPECTED_REPLICATIONS,
        "expected_tasks_per_run": campaign.EXPECTED_TASKS_PER_RUN,
        "sample_validation": {
            "path": sample_report.relative_to(tmp_path).as_posix(),
            "sha256": _sha256(sample_report),
            "run_root": sample_run_root.relative_to(tmp_path).as_posix(),
            "status": "pass",
            "release_identity": {
                field: identity[field]
                for field in campaign.SAMPLE_RELEASE_IDENTITY_FIELDS
            },
        },
        "maximum_parallel_runs": campaign.MAX_CONCURRENCY,
        "execution_waves": campaign._expected_execution_waves(campaign.MAX_CONCURRENCY),
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


def test_campaign_prerequisites_accept_only_the_frozen_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, sample_report, sample_calls = _valid_campaign(tmp_path, monkeypatch)
    before = sample_report.read_bytes()

    assert campaign._campaign_prerequisite_errors(tmp_path, manifest) == []
    assert sample_report.read_bytes() == before
    assert sample_calls == [
        {
            "search_root": tmp_path / "sample_run",
            "output_path": sample_report,
            "write_report": False,
        }
    ]


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
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    _set_nested(manifest, path, replacement)

    errors = campaign._campaign_prerequisite_errors(tmp_path, manifest)

    assert any(expected_error in error for error in errors)


def test_campaign_rejects_execution_wave_parallelism_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
    manifest["execution_waves"][1]["maximum_parallel"] = 1

    errors = campaign._campaign_prerequisite_errors(tmp_path, manifest)

    assert (
        "execution_waves must exactly match the declared campaign parallelism" in errors
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


def test_force_replacement_rejects_stale_arm_and_registry_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _ = _valid_campaign(tmp_path, monkeypatch)
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
