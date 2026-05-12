import json
from pathlib import Path

import pytest

from sage_ts.orchestration.self_evolving_campaign import (
    MINI_MODEL,
    SelfEvolvingCampaignConfig,
    enforce_mini_model_policy,
    prepare_self_evolving_campaign,
)


def _write_gap_packet(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "ranked_gap_buckets": [
                    {
                        "bucket": "contact_lookup_update_search_crud",
                        "scenario_count": 3,
                        "outcome_regression_count": 2,
                        "score_regression_count": 2,
                        "negative_outcome_mass": 1.5,
                        "negative_score_mass": 0.5,
                        "no_visible_helper_count": 2,
                        "no_called_helper_count": 3,
                        "top_outcome_regressions": [
                            {"scenario": "search_phone_number_with_name"},
                            {"scenario": ("update_contact_with_id_and_phone_number")},
                        ],
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_manifest(path: Path) -> Path:
    records = [
        {"name": "search_phone_number_with_name", "categories": []},
        {"name": "update_contact_with_id_and_phone_number", "categories": []},
        {"name": "search_name_with_relationship", "categories": []},
    ]
    path.write_text(
        json.dumps({"splits": {"full_benchmark": records}}) + "\n",
        encoding="utf-8",
    )
    return path


def test_self_evolving_policy_rejects_large_or_non_mini_runs() -> None:
    with pytest.raises(ValueError, match="self_evolving_sample_cap_exceeded"):
        enforce_mini_model_policy(
            max_samples=61,
            agent_model=MINI_MODEL,
            user_model=MINI_MODEL,
            generation_model=MINI_MODEL,
        )

    with pytest.raises(ValueError, match="non_mini_model_requested"):
        enforce_mini_model_policy(
            max_samples=60,
            agent_model="gpt-5",
            user_model=MINI_MODEL,
            generation_model=MINI_MODEL,
        )


def test_prepare_self_evolving_campaign_starts_empty_then_generates_tool(
    tmp_path: Path,
) -> None:
    prepared = prepare_self_evolving_campaign(
        SelfEvolvingCampaignConfig(
            source_gap_packet=_write_gap_packet(tmp_path / "gap_packet.json"),
            source_manifest=_write_manifest(tmp_path / "formal_manifest.json"),
            output_root=tmp_path / "campaign",
            max_samples=2,
        )
    )

    summary = json.loads(prepared.summary_path.read_text(encoding="utf-8"))
    manifest = json.loads(prepared.manifest_path.read_text(encoding="utf-8"))

    assert summary["starting_registry_tool_count"] == 0
    assert summary["model_policy"]["all_models_forced_to"] == MINI_MODEL
    assert summary["integrity_controls"]["labels_or_expected_answers_used"] is False
    assert summary["generated_tool_names"] == [
        "prepare_contact_lookup_or_update_action_v2"
    ]
    assert prepared.selected_scenario_count == 2
    assert len(manifest["splits"]["transfer_60"]) == 2
    assert Path(str(prepared.registry_dir / "registry_manifest.json")).exists()
