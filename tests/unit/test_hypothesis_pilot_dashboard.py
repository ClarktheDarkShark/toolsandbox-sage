from __future__ import annotations

import json
from pathlib import Path

import pytest

from sage_ts.dashboard.hypothesis_pilot import (
    HYPOTHESIS_PILOT_DATA_NAME,
    HYPOTHESIS_PILOT_HTML_NAME,
    build_hypothesis_pilot_payload,
    write_hypothesis_pilot_dashboard,
)


def _write_manifest(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_pending_dashboard_is_explicitly_nonconfirmatory(tmp_path: Path) -> None:
    manifest = tmp_path / "pilot" / "pilot_manifest.json"
    output = manifest.parent / "dashboard"
    _write_manifest(
        manifest,
        {
            "pilot_id": "h123_pending",
            "status": "pending",
            "progress_stage": 0,
            "h1": {},
            "h2": {},
            "h3": {},
            "h4": {},
        },
    )

    payload = write_hypothesis_pilot_dashboard(
        manifest_path=manifest,
        output_dir=output,
    )

    dashboard = (output / HYPOTHESIS_PILOT_HTML_NAME).read_text(encoding="utf-8")
    assert payload["status"] == "pending"
    assert payload["h1"]["case_weighted_pass_rate"] is None
    assert "PILOT — NOT CONFIRMATORY" in dashboard
    assert "H1 / H2 / H3 / H4 Pilot" in dashboard
    assert "Exploratory alternate" in dashboard
    assert "cannot establish hypothesis support" in dashboard
    assert "Supported" not in dashboard
    assert (output / HYPOTHESIS_PILOT_DATA_NAME).exists()


def test_completed_dashboard_computes_and_preserves_core_estimands(
    tmp_path: Path,
) -> None:
    pilot = tmp_path / "pilot"
    artifact = pilot / "h1" / "blind_audit.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{}\n", encoding="utf-8")
    manifest = pilot / "pilot_manifest.json"
    output = pilot / "dashboard"
    _write_manifest(
        manifest,
        {
            "pilot_id": "h123_complete",
            "study_label": "one-registry protocol pilot",
            "status": "complete",
            "progress_stage": 5,
            "h1": {
                "status": "observed",
                "blind_cases_passed": 17,
                "blind_cases_total": 20,
                "accepted_tools": 5,
                "evaluated_tools": 4,
                "tool_weighted_pass_rate": 0.75,
                "clopper_pearson_lower_bound": 0.2835820638819105,
                "pilot_gate_outcome": "not_cleared",
                "pilot_gate_label": "PILOT_THRESHOLD_NOT_CLEARED",
                "integrity": {
                    "status": "pass",
                    "checks": [
                        {
                            "label": "Audit cases hidden until freeze",
                            "passed": True,
                            "detail": "freeze preceded case release",
                        }
                    ],
                },
            },
            "h2": {
                "status": "observed",
                "control_mean": 0.4,
                "integrated_sage_mean": 0.46,
                "cluster_ci_95": [-0.01, 0.13],
                "stem_clusters": 129,
                "tasks": 1032,
                "pilot_gate": {
                    "outcome": "cleared",
                    "label": "PILOT_THRESHOLD_CLEARED",
                },
                "descriptive_canonical_similarity": {
                    "role": "descriptive_not_primary",
                    "control_mean": 0.31,
                    "integrated_sage_mean": 0.37,
                    "mean_difference": 0.06,
                    "tasks": 1032,
                },
                "integrity": {"status": "pass"},
            },
            "h3": {
                "status": "observed",
                "registry_available_mean": 0.51,
                "registry_masked_mean": 0.47,
                "cluster_ci_95": [0.005, 0.075],
                "p_value": 0.031,
                "p_value_note": "one-sided restricted randomization",
                "available_tasks": 516,
                "masked_tasks": 516,
                "stem_clusters": 129,
                "allocation": {
                    "seed": 20260918,
                    "sha256": "a" * 64,
                    "stratification": "within task stem",
                },
                "pilot_gate_passed": False,
                "pilot_gate_label": "PILOT_THRESHOLD_NOT_CLEARED",
                "descriptive_canonical_similarity": {
                    "role": "descriptive_not_primary",
                    "registry_available_mean": 0.43,
                    "registry_masked_mean": 0.40,
                    "mean_difference": 0.03,
                    "available_tasks": 520,
                    "masked_tasks": 512,
                },
                "integrity": {"status": "pass"},
            },
            "h4": {
                "status": "observed",
                "discovery_tasks": 512,
                "discovery_stems": 64,
                "heldout_tasks": 520,
                "heldout_stems": 65,
                "frozen_available_mean": 0.55,
                "registry_masked_mean": 0.50,
                "cluster_ci_95": [0.012, 0.088],
                "split": {"seed": 20260919, "sha256": "b" * 64},
                "pilot_gate": {
                    "outcome": "cleared",
                    "label": "PILOT_THRESHOLD_CLEARED",
                },
                "method_note": "Disjoint discovery and held-out halves.",
                "descriptive_canonical_similarity": {
                    "role": "descriptive_not_primary",
                    "registry_available_mean": 0.48,
                    "registry_masked_mean": 0.45,
                    "mean_difference": 0.03,
                    "available_tasks": 520,
                    "masked_tasks": 520,
                },
                "integrity": {
                    "status": "pass",
                    "checks": [{"label": "Discovery/held-out overlap", "passed": True}],
                },
            },
            "artifacts": [
                {
                    "label": "Blind audit",
                    "kind": "H1 evidence",
                    "path": "h1/blind_audit.json",
                }
            ],
        },
    )

    payload = write_hypothesis_pilot_dashboard(
        manifest_path=manifest,
        output_dir=output,
    )

    assert payload["h1"]["case_weighted_pass_rate"] == pytest.approx(0.85)
    assert payload["h1"]["tool_coverage_rate"] == pytest.approx(0.8)
    assert payload["h1"]["clopper_pearson_lower_bound"] == pytest.approx(
        0.2835820638819105
    )
    assert payload["h1"]["pilot_gate_outcome"] == "not_cleared"
    assert payload["h1"]["pilot_gate_label"] == "PILOT_THRESHOLD_NOT_CLEARED"
    assert payload["h2"]["mean_difference"] == pytest.approx(0.06)
    assert payload["h2"]["relative_lift"] == pytest.approx(0.15)
    assert payload["h2"]["cluster_ci_95"] == [-0.01, 0.13]
    assert payload["h2"]["stem_clusters"] == 129
    assert payload["h2"]["pilot_gate_outcome"] == "cleared"
    assert payload["h2"]["pilot_gate_label"] == "PILOT_THRESHOLD_CLEARED"
    assert payload["h2"]["descriptive_canonical_similarity"] == {
        "role": "descriptive_not_primary",
        "integrated_sage_mean": pytest.approx(0.37),
        "control_mean": pytest.approx(0.31),
        "mean_difference": pytest.approx(0.06),
        "tasks": 1032,
    }
    assert payload["h3"]["itt_mean_difference"] == pytest.approx(0.04)
    assert payload["h3"]["p_value"] == pytest.approx(0.031)
    assert payload["h3"]["p_value_note"] == "one-sided restricted randomization"
    assert payload["h3"]["allocation"]["seed"] == 20260918
    assert payload["h3"]["pilot_gate_outcome"] == "not_cleared"
    assert payload["h3"]["pilot_gate_label"] == "PILOT_THRESHOLD_NOT_CLEARED"
    assert payload["h3"]["descriptive_canonical_similarity"][
        "mean_difference"
    ] == pytest.approx(0.03)
    assert payload["h4"]["exploratory_alternate"] is True
    assert payload["h4"]["discovery_tasks"] == 512
    assert payload["h4"]["discovery_stems"] == 64
    assert payload["h4"]["heldout_tasks"] == 520
    assert payload["h4"]["heldout_stems"] == 65
    assert payload["h4"]["mean_difference"] == pytest.approx(0.05)
    assert payload["h4"]["relative_lift"] == pytest.approx(0.10)
    assert payload["h4"]["cluster_ci_95"] == [0.012, 0.088]
    assert payload["h4"]["split_seed"] == 20260919
    assert payload["h4"]["split_sha256"] == "b" * 64
    assert payload["h4"]["pilot_gate_outcome"] == "cleared"
    assert payload["h4"]["pilot_gate_label"] == "PILOT_THRESHOLD_CLEARED"
    assert payload["h4"]["descriptive_canonical_similarity"][
        "registry_masked_mean"
    ] == pytest.approx(0.45)
    assert payload["progress_stage"] == 5
    assert payload["artifacts"][0]["exists"] is True
    assert payload["artifacts"][0]["href"] == "../h1/blind_audit.json"

    saved = json.loads(
        (output / HYPOTHESIS_PILOT_DATA_NAME).read_text(encoding="utf-8")
    )
    assert saved["h3"]["allocation"]["sha256"] == "a" * 64
    assert saved["h4"]["exploratory_alternate"] is True
    dashboard_html = (output / HYPOTHESIS_PILOT_HTML_NAME).read_text(encoding="utf-8")
    assert dashboard_html.count("ToolSandbox canonical similarity") == 3
    assert "Descriptive only · not primary" in dashboard_html
    assert "canonical similarity is not used in the pilot gate" in dashboard_html


def test_failed_integrity_overrides_observed_display_status(tmp_path: Path) -> None:
    manifest = tmp_path / "pilot_manifest.json"
    _write_manifest(
        manifest,
        {
            "status": "complete",
            "h1": {
                "status": "observed",
                "integrity": {
                    "status": "fail",
                    "checks": [{"label": "Freeze hash matched", "passed": False}],
                },
            },
            "h2": {},
            "h3": {},
        },
    )

    payload = write_hypothesis_pilot_dashboard(
        manifest_path=manifest,
        output_dir=tmp_path / "dashboard",
    )

    assert payload["integrity_status"] == "fail"
    dashboard = (tmp_path / "dashboard" / HYPOTHESIS_PILOT_HTML_NAME).read_text(
        encoding="utf-8"
    )
    assert "if (integrity === 'fail') return 'Failed integrity'" in dashboard


def test_latest_pointer_uses_relative_dashboard_target(tmp_path: Path) -> None:
    manifest = tmp_path / "artifacts" / "pilot" / "pilot_manifest.json"
    output = tmp_path / "outputs" / "pilot" / "dashboard"
    latest = tmp_path / "outputs" / "dashboard" / "latest_pilot.html"
    _write_manifest(
        manifest,
        {"status": "running", "h1": {}, "h2": {}, "h3": {}, "h4": {}},
    )

    write_hypothesis_pilot_dashboard(
        manifest_path=manifest,
        output_dir=output,
        latest_path=latest,
    )

    pointer = latest.read_text(encoding="utf-8")
    assert "../pilot/dashboard/hypothesis_pilot.html" in pointer
    assert "Latest SAGE hypothesis pilot" in pointer


def test_payload_rejects_unrecognized_status(tmp_path: Path) -> None:
    manifest = tmp_path / "pilot_manifest.json"
    _write_manifest(manifest, {"status": "supported"})

    with pytest.raises(ValueError, match="status must be one of"):
        build_hypothesis_pilot_payload(
            json.loads(manifest.read_text(encoding="utf-8")),
            manifest_path=manifest,
            output_dir=tmp_path / "dashboard",
        )


def test_h1_gate_rejects_confirmatory_decision_language(tmp_path: Path) -> None:
    manifest = tmp_path / "pilot_manifest.json"
    _write_manifest(
        manifest,
        {
            "status": "complete",
            "h1": {
                "status": "observed",
                "pilot_gate_outcome": "supported",
                "pilot_gate_label": "SUPPORTED",
            },
        },
    )

    with pytest.raises(ValueError, match="confirmatory Supported/Rejected"):
        build_hypothesis_pilot_payload(
            json.loads(manifest.read_text(encoding="utf-8")),
            manifest_path=manifest,
            output_dir=tmp_path / "dashboard",
        )


@pytest.mark.parametrize("hypothesis", ["h2", "h3", "h4"])
def test_outcome_hypothesis_gates_reject_confirmatory_decision_language(
    tmp_path: Path, hypothesis: str
) -> None:
    manifest = tmp_path / "pilot_manifest.json"
    _write_manifest(
        manifest,
        {
            "status": "complete",
            hypothesis: {
                "status": "observed",
                "pilot_gate": {"outcome": "rejected", "label": "REJECTED"},
            },
        },
    )

    with pytest.raises(ValueError, match="confirmatory Supported/Rejected"):
        build_hypothesis_pilot_payload(
            json.loads(manifest.read_text(encoding="utf-8")),
            manifest_path=manifest,
            output_dir=tmp_path / "dashboard",
        )
