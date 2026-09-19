from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

import scripts.manage_hypothesis_pilot as pilot_manager
from scripts.manage_hypothesis_pilot import (
    add_artifact,
    bind_frozen_registry,
    bind_h4_frozen_registry,
    create_manifest,
    main,
    record_result,
    register_dashboard,
    seal_phase_inputs,
    update_phase,
)


@pytest.fixture(autouse=True)
def _git_identity_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pilot_manager,
        "_verified_git_identity",
        lambda: {
            "git_commit": "1" * 40,
            "git_tree": "2" * 40,
            "git_status": "clean",
        },
    )


def _file(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_manifest_lifecycle_refreshes_all_registered_dashboards(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "artifacts" / "pilot.json"
    first_dashboard = tmp_path / "outputs" / "dashboard"
    second_dashboard = tmp_path / "outputs" / "run" / "dashboard"
    benchmark = _file(tmp_path / "benchmark.json", "{}\n")
    protocol = _file(tmp_path / "protocol.md", "# Locked\n")
    latest = tmp_path / "outputs" / "latest.html"

    manifest = create_manifest(
        manifest_path=manifest_path,
        pilot_id="h1234_test",
        dashboard_dir=first_dashboard,
        latest_pointer=latest,
        git_commit="1" * 40,
        git_tree="2" * 40,
        benchmark_path=benchmark,
        protocol_path=protocol,
        output_root=tmp_path / "outputs",
        artifact_root=tmp_path / "artifacts",
    )

    assert manifest["h4"]["status"] == "pending"
    assert manifest["locked_design"]["h3_randomization_draws"] == 100000
    assert manifest["locked_design"]["h4_random_generator"].endswith("(PCG64)")
    assert manifest["locked_design"]["h4_bootstrap_seed"] == 20260920
    assert manifest["locked_design"]["transient_scenario_attempt_limit"] == 4
    assert (first_dashboard / "hypothesis_pilot.html").is_file()
    assert latest.is_file()

    register_dashboard(manifest_path=manifest_path, dashboard_dir=second_dashboard)
    update_phase(
        manifest_path=manifest_path,
        phase="h2_online",
        progress_stage=1,
        hypothesis="h2",
        hypothesis_status="running",
    )
    evidence = _file(tmp_path / "evidence.json", "{}\n")
    add_artifact(
        manifest_path=manifest_path,
        path=evidence,
        label="Evidence",
        kind="analysis",
    )

    stored = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert stored["h2"]["status"] == "running"
    assert stored["progress_stage"] == 1
    assert len(stored["dashboard_directories"]) == 2
    assert stored["artifacts"][-1]["path"] == str(evidence.resolve())
    for directory in (first_dashboard, second_dashboard):
        payload = json.loads(
            (directory / "hypothesis_pilot_data.json").read_text(encoding="utf-8")
        )
        assert payload["h2"]["status"] == "running"


def test_manifest_refuses_overwrite_and_invalid_stage(tmp_path: Path) -> None:
    manifest_path = tmp_path / "pilot.json"
    benchmark = _file(tmp_path / "benchmark.json", "{}\n")
    protocol = _file(tmp_path / "protocol.md", "# Locked\n")
    kwargs: dict[str, Any] = {
        "manifest_path": manifest_path,
        "pilot_id": "test",
        "dashboard_dir": tmp_path / "dashboard",
        "latest_pointer": tmp_path / "latest.html",
        "git_commit": "1" * 40,
        "git_tree": "2" * 40,
        "benchmark_path": benchmark,
        "protocol_path": protocol,
        "output_root": tmp_path / "output",
        "artifact_root": tmp_path / "artifact",
    }
    create_manifest(**kwargs)
    with pytest.raises(FileExistsError):
        create_manifest(**kwargs)
    with pytest.raises(ValueError, match="between 0 and 5"):
        update_phase(
            manifest_path=manifest_path,
            phase="bad",
            progress_stage=6,
        )


def _new_manifest(tmp_path: Path) -> Path:
    manifest_path = tmp_path / "artifacts" / "pilot.json"
    create_manifest(
        manifest_path=manifest_path,
        pilot_id="projection_test",
        dashboard_dir=tmp_path / "dashboard",
        latest_pointer=tmp_path / "latest.html",
        git_commit="1" * 40,
        git_tree="2" * 40,
        benchmark_path=_file(tmp_path / "benchmark.json", "{}\n"),
        protocol_path=_file(tmp_path / "protocol.md", "# Locked\n"),
        output_root=tmp_path / "outputs",
        artifact_root=tmp_path / "artifacts",
    )
    return manifest_path


def _write_report(path: Path, payload: Mapping[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _execution_identity() -> dict[str, object]:
    return {
        "git_commit": "1" * 40,
        "git_tree": "2" * 40,
        "git_clean": True,
    }


def test_record_result_projects_all_four_locked_report_schemas(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest_path = _new_manifest(tmp_path)
    registry_dir = tmp_path / "h2_run" / "candidate" / "registry"
    registry_manifest = _file(registry_dir / "registry_manifest.json", "{}\n")
    _file(registry_dir / "generated_tools" / "tool.py", "def invoke():\n    return 1\n")
    h2_run_root = tmp_path / "h2_run"
    _write_report(
        h2_run_root / "protocol_manifest.json",
        {
            "registry_dir": str(registry_dir.resolve()),
            "registry_manifest_digest_after_run": _sha256(registry_manifest),
        },
    )
    h2_control = _write_report(tmp_path / "h2_control.json", {"arm": "control"})

    update_phase(
        manifest_path=manifest_path,
        phase="h2_online",
        progress_stage=1,
        hypothesis="h2",
        hypothesis_status="running",
    )
    h2_report = {
        "report_type": "h2_integrated_sage_pilot_analysis",
        "status": "observed",
        "pilot_gate_label": "PILOT_THRESHOLD_CLEARED",
        "integrity": {
            "status": "pass",
            "checks": [{"name": "complete roster", "passed": True}],
            "strict_verification_receipt": {
                "status": "pass",
                "run_root": str(h2_run_root.resolve()),
                "hypothesis_pilot_manifest": {
                    "path": str(manifest_path.resolve()),
                    "sha256_at_verification": _sha256(manifest_path),
                },
                "verification": _execution_identity(),
            },
        },
        "inputs": {
            "control": {
                "path": str(h2_control.resolve()),
                "sha256": _sha256(h2_control),
            }
        },
        "control_mean": 0.4,
        "integrated_sage_mean": 0.5,
        "mean_difference": 0.1,
        "relative_lift": 0.25,
        "cluster_ci_95": [0.02, 0.18],
        "stem_clusters": 129,
        "tasks": 1032,
        "descriptive_canonical_similarity": {
            "role": "descriptive_not_primary",
            "control_mean": 0.30,
            "integrated_sage_mean": 0.36,
            "mean_difference": 0.06,
            "tasks": 1032,
        },
        "method_note": "Locked paired stem bootstrap.",
    }
    h2_path = _write_report(tmp_path / "h2.json", h2_report)
    record_result(
        manifest_path=manifest_path,
        hypothesis="h2",
        report_path=h2_path,
    )
    bound = bind_frozen_registry(
        manifest_path=manifest_path,
        registry_dir=registry_dir,
        h2_run_root=h2_run_root,
    )["frozen_h123_registry"]

    update_phase(
        manifest_path=manifest_path,
        phase="h1_blind_audit",
        progress_stage=2,
        hypothesis="h1",
        hypothesis_status="running",
    )
    case_bank = _write_report(tmp_path / "h1_case_bank.json", {"cases": []})
    seal_phase_inputs(
        manifest_path=manifest_path,
        phase="h1_blind_audit",
        files={"case_bank": case_bank},
        declarations={"blinding": "procedural_spec_only"},
    )
    tool_rows = {
        f"tool_{index}": {
            "passed": True,
            "case_count": 2,
            "passing_case_count": 2,
            "static_safety_errors": [],
            "case_results": [
                {"errors": [], "passed": True},
                {"errors": [], "passed": True},
            ],
        }
        for index in range(20)
    }
    h1_report = {
        "report_type": "blind_functional_validity_audit",
        "status": "complete",
        "case_bank": {
            "hash_verified": True,
            "expected_sha256": _sha256(case_bank),
        },
        "registry_immutability": {
            "immutable": True,
            "before_tree_sha256": bound["content_sha256"],
        },
        "integrity": {
            "valid": True,
            "admission_input_overlap_count": 0,
        },
        "endpoint_result": {
            "estimable": True,
            "active_tool_count": 20,
            "passing_tool_count": 20,
            "tool_weighted_validity_rate": 1.0,
            "case_count": 40,
            "passing_case_count": 40,
            "clopper_pearson": {"lower_bound": 0.831566529},
        },
        "tools": tool_rows,
    }
    record_result(
        manifest_path=manifest_path,
        hypothesis="h1",
        report_path=_write_report(tmp_path / "h1.json", h1_report),
    )

    update_phase(
        manifest_path=manifest_path,
        phase="h3_randomized_availability",
        progress_stage=3,
        hypothesis="h3",
        hypothesis_status="running",
    )
    h3_assignment = _write_report(tmp_path / "h3_assignment.json", {"seed": 20260918})
    seal_phase_inputs(
        manifest_path=manifest_path,
        phase="h3_randomized_availability",
        files={"assignment": h3_assignment, "h2_control": h2_control},
        declarations={"registry_mode": "available_vs_masked"},
    )

    h3_integrity: dict[str, object] = {
        "status": "pass",
        "passed": True,
        "online_evaluator_feedback_consumed": False,
        **{
            key: True
            for key in (
                "complete_itt_roster",
                "one_result_per_randomized_scenario",
                "assignment_id_recorded_per_scenario",
                "identical_wrapper_and_native_inventory",
                "registry_source_unchanged",
                "registry_copy_unchanged",
                "generator_disabled",
                "reflection_repair_lifecycle_disabled",
            )
        },
        "condition_exposure_validation": {
            "masked_generated_exposure_count": 0,
            "masked_generated_call_count": 0,
            "forbidden_lifecycle_event_count": 0,
            "prohibited_lifecycle_artifact_count": 0,
        },
    }
    h3_report = {
        "status": "complete",
        "pilot_gate_label": "PILOT_THRESHOLD_CLEARED",
        "phase_inputs_sealed_before_model_execution": True,
        "inputs": {
            "pilot_manifest_path": str(manifest_path.resolve()),
            "registry_source": str(registry_dir.resolve()),
        },
        "publication_environment": _execution_identity(),
        "provenance": {
            "registry_source_before": {"content_sha256": bound["content_sha256"]},
            "assignment_file_sha256": _sha256(h3_assignment),
            "h2_control_file_sha256": _sha256(h2_control),
        },
        "integrity": h3_integrity,
        "registry_available_mean": 0.55,
        "registry_masked_mean": 0.45,
        "itt_mean_difference": 0.1,
        "cluster_ci_95": [0.01, 0.19],
        "p_value": 0.01,
        "available_tasks": 520,
        "masked_tasks": 512,
        "stem_clusters": 129,
        "allocation": {
            "seed": 20260918,
            "sha256": "a" * 64,
            "stratification": "63 pairs plus one triplet",
        },
        "descriptive_canonical_similarity": {
            "role": "descriptive_not_primary",
            "registry_available_mean": 0.42,
            "registry_masked_mean": 0.39,
            "available_tasks": 520,
            "masked_tasks": 512,
        },
    }
    record_result(
        manifest_path=manifest_path,
        hypothesis="h3",
        report_path=_write_report(tmp_path / "h3.json", h3_report),
    )

    update_phase(
        manifest_path=manifest_path,
        phase="h4_split",
        progress_stage=4,
        hypothesis="h4",
        hypothesis_status="running",
    )
    h4_design = _write_report(tmp_path / "h4_design.json", {"seed": 20260919})
    seal_phase_inputs(
        manifest_path=manifest_path,
        phase="h4_split",
        files={"design": h4_design},
        declarations={
            "discovery_stems": 64,
            "held_out_stems": 65,
            "design_sha256": "b" * 64,
        },
    )
    h4_registry = tmp_path / "h4_registry"
    _file(h4_registry / "registry_manifest.json", '{"tools": {}}\n')
    h4_discovery_run = tmp_path / "h4_discovery_run"
    h4_discovery_run.mkdir()
    h4_binding = bind_h4_frozen_registry(
        manifest_path=manifest_path,
        registry_dir=h4_registry,
        design_sha256="b" * 64,
        discovery_run_dir=h4_discovery_run,
    )["h4_frozen_registry"]
    h4_integrity = {
        "passed": True,
        **{
            key: True
            for key in (
                "complete_rosters",
                "source_disjoint_stems",
                "design_hash_verified",
                "execution_order_hashes_verified",
                "immutable_equal_registry_copies",
                "identical_runtime_and_native_inventory",
                "masked_zero_generated_exposure",
                "masked_zero_generated_calls",
                "available_generated_exposure_positive",
                "held_out_arms_concurrent",
                "zero_runtime_exceptions",
                "frozen_phase_generation_repair_reflection_lifecycle_disabled",
            )
        },
    }
    h4_report = {
        "status": "complete",
        "status_label": "PILOT_THRESHOLD_CLEARED",
        "phase_inputs_sealed_before_model_execution": True,
        "inputs": {"pilot_manifest_path": str(manifest_path.resolve())},
        "publication_environment": _execution_identity(),
        "provenance": {
            "design_file_sha256": _sha256(h4_design),
            "frozen_registry_content_sha256": h4_binding["content_sha256"],
        },
        "h4_frozen_registry_binding": {
            key: h4_binding[key]
            for key in ("path", "content_sha256", "manifest_sha256", "design_sha256")
        },
        "analysis": {
            "status_label": "PILOT_THRESHOLD_CLEARED",
            "counts": {
                "discovery_stems": 64,
                "discovery_scenarios": 512,
                "held_out_stems": 65,
                "scenarios_per_arm": 520,
            },
            "outcomes": {
                "registry_available_mean": 0.6,
                "registry_masked_mean": 0.5,
                "absolute_difference": 0.1,
                "relative_lift": 0.2,
            },
            "uncertainty": {"mean_difference_ci": [0.02, 0.18]},
            "pilot_gate": {"decision": "PILOT_THRESHOLD_CLEARED"},
            "integrity": h4_integrity,
            "design_sha256": "b" * 64,
        },
        "integrity": h4_integrity,
        "design_sha256": "b" * 64,
        "descriptive_canonical_similarity": {
            "role": "descriptive_not_primary",
            "registry_available_mean": 0.44,
            "registry_masked_mean": 0.41,
        },
    }
    record_result(
        manifest_path=manifest_path,
        hypothesis="h4",
        report_path=_write_report(tmp_path / "h4.json", h4_report),
    )

    stored = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert stored["h1"]["tool_weighted_pass_rate"] == 1.0
    assert stored["h1"]["pilot_gate_label"] == "PILOT_THRESHOLD_CLEARED"
    assert stored["h2"]["relative_lift"] == 0.25
    assert stored["h2"]["descriptive_canonical_similarity"] == {
        "role": "descriptive_not_primary",
        "control_mean": 0.30,
        "integrated_sage_mean": 0.36,
        "mean_difference": pytest.approx(0.06),
        "tasks": 1032,
    }
    assert stored["h3"]["available_tasks"] == 520
    assert stored["h3"]["integrity"]["status"] == "pass"
    assert stored["h3"]["descriptive_canonical_similarity"][
        "mean_difference"
    ] == pytest.approx(0.03)
    assert stored["h4"]["exploratory_alternate"] is True
    assert stored["h4"]["heldout_tasks"] == 520
    assert stored["h4"]["descriptive_canonical_similarity"][
        "mean_difference"
    ] == pytest.approx(0.03)
    assert (
        len([item for item in stored["artifacts"] if item["kind"] == "analysis"]) == 4
    )

    dashboard = json.loads(
        (tmp_path / "dashboard" / "hypothesis_pilot_data.json").read_text(
            encoding="utf-8"
        )
    )
    assert dashboard["h1"]["pilot_gate_label"] == "PILOT_THRESHOLD_CLEARED"
    assert dashboard["h2"]["integrated_sage_mean"] == 0.5
    assert dashboard["h3"]["p_value"] == 0.01
    assert dashboard["h4"]["split_sha256"] == "b" * 64
    assert dashboard["h2"]["descriptive_canonical_similarity"][
        "integrated_sage_mean"
    ] == pytest.approx(0.36)
    assert dashboard["h3"]["descriptive_canonical_similarity"][
        "registry_masked_mean"
    ] == pytest.approx(0.39)
    assert dashboard["h4"]["descriptive_canonical_similarity"][
        "registry_available_mean"
    ] == pytest.approx(0.44)

    monkeypatch.setattr(
        "sys.argv",
        [
            "manage_hypothesis_pilot.py",
            "record-result",
            "--manifest",
            str(manifest_path),
            "--hypothesis",
            "h2",
            "--report",
            str(h2_path),
        ],
    )
    events_before = len(json.loads(manifest_path.read_text())["events"])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["phase"] == "h4_split"
    assert len(json.loads(manifest_path.read_text())["events"]) == events_before

    changed_h2 = dict(h2_report)
    changed_h2["integrated_sage_mean"] = 0.51
    changed_h2["mean_difference"] = 0.11
    changed_h2["relative_lift"] = 0.275
    with pytest.raises(ValueError, match="already has a different locked result"):
        record_result(
            manifest_path=manifest_path,
            hypothesis="h2",
            report_path=_write_report(tmp_path / "changed_h2.json", changed_h2),
        )


def test_record_result_fails_closed_without_mutating_manifest(
    tmp_path: Path,
) -> None:
    manifest_path = _new_manifest(tmp_path)
    before = manifest_path.read_bytes()
    report = {
        "report_type": "h2_integrated_sage_pilot_analysis",
        "status": "observed",
        "pilot_gate_label": "SUPPORTED",
        "integrity": {"status": "pass", "checks": []},
        "control_mean": 0.4,
        "integrated_sage_mean": 0.5,
        "mean_difference": 0.1,
        "relative_lift": 0.25,
        "cluster_ci_95": [0.02, 0.18],
        "stem_clusters": 129,
        "tasks": 1032,
    }
    with pytest.raises(ValueError, match="Supported/Rejected"):
        record_result(
            manifest_path=manifest_path,
            hypothesis="h2",
            report_path=_write_report(tmp_path / "bad_h2.json", report),
        )
    assert manifest_path.read_bytes() == before


def test_h2_projection_rejects_canonical_similarity_as_primary() -> None:
    report = {
        "report_type": "h2_integrated_sage_pilot_analysis",
        "status": "observed",
        "pilot_gate_label": "PILOT_THRESHOLD_CLEARED",
        "integrity": {
            "status": "pass",
            "checks": [{"name": "complete roster", "passed": True}],
        },
        "control_mean": 0.4,
        "integrated_sage_mean": 0.5,
        "mean_difference": 0.1,
        "relative_lift": 0.25,
        "cluster_ci_95": [0.02, 0.18],
        "stem_clusters": 129,
        "tasks": 1032,
        "descriptive_canonical_similarity": {
            "role": "primary_endpoint",
            "control_mean": 0.3,
            "integrated_sage_mean": 0.4,
        },
    }

    with pytest.raises(ValueError, match="descriptive_not_primary"):
        pilot_manager._project_h2(report)


def test_record_result_rejects_passing_h3_without_exposure_integrity(
    tmp_path: Path,
) -> None:
    manifest_path = _new_manifest(tmp_path)
    report = {
        "status": "complete",
        "pilot_gate_label": "PILOT_THRESHOLD_CLEARED",
        "integrity": {"status": "pass", "passed": True},
        "registry_available_mean": 0.6,
        "registry_masked_mean": 0.5,
        "itt_mean_difference": 0.1,
        "cluster_ci_95": [0.01, 0.2],
        "p_value": 0.01,
        "available_tasks": 520,
        "masked_tasks": 512,
        "stem_clusters": 129,
        "allocation": {"sha256": "a" * 64},
    }
    with pytest.raises(ValueError, match="missing required integrity checks"):
        record_result(
            manifest_path=manifest_path,
            hypothesis="h3",
            report_path=_write_report(tmp_path / "bad_h3.json", report),
        )
