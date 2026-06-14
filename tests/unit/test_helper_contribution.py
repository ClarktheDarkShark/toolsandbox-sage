import json
from pathlib import Path

from sage_ts.evaluation.helper_contribution import build_helper_contribution_summary


def _write_summary(path: Path, rows: list[dict[str, object]]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "result_summary.json").write_text(
        json.dumps({"per_scenario_results": rows}) + "\n",
        encoding="utf-8",
    )


def test_helper_contribution_splits_called_visible_and_hidden(tmp_path: Path) -> None:
    control = tmp_path / "control"
    candidate = tmp_path / "candidate"
    registry = tmp_path / "registry"
    _write_summary(
        control,
        [
            {"name": "called", "similarity": 0.0, "outcome_similarity": 0.2},
            {"name": "ignored", "similarity": 1.0, "outcome_similarity": 1.0},
            {"name": "hidden", "similarity": 0.5, "outcome_similarity": 0.5},
        ],
    )
    _write_summary(
        candidate,
        [
            {"name": "called", "similarity": 1.0, "outcome_similarity": 0.9},
            {"name": "ignored", "similarity": 0.5, "outcome_similarity": 0.75},
            {"name": "hidden", "similarity": 0.5, "outcome_similarity": 0.5},
        ],
    )
    (candidate / "scenario_tool_selection.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "scenario": "called",
                        "generated_tools_visible": ["helper"],
                        "generated_tools_called": ["helper"],
                        "generated_tools_attempted": ["helper"],
                        "generated_tools_failed": [],
                    }
                ),
                json.dumps(
                    {
                        "scenario": "ignored",
                        "generated_tools_visible": ["helper"],
                        "generated_tools_called": [],
                        "generated_tools_attempted": [],
                        "generated_tools_failed": [],
                    }
                ),
                json.dumps(
                    {
                        "scenario": "hidden",
                        "generated_tools_visible": [],
                        "generated_tools_called": [],
                        "generated_tools_attempted": [],
                        "generated_tools_failed": [],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (candidate / "tool_birth_events.jsonl").write_text(
        json.dumps({"accepted": True, "tool_name": "new_idle"}) + "\n",
        encoding="utf-8",
    )
    registry.mkdir()
    (registry / "registry_manifest.json").write_text(
        json.dumps({"tools": {"helper": {}}}) + "\n",
        encoding="utf-8",
    )

    summary = build_helper_contribution_summary(
        control, candidate, registry_dir=registry
    )

    helper = summary["helpers"]["helper"]
    assert helper["origin"] == "retained"
    assert helper["called_count"] == 1
    assert helper["visible_not_called_count"] == 1
    assert helper["hidden_no_call_count"] == 1
    assert helper["called_subset"]["mean_outcome_delta"] == 0.7
    assert helper["visible_not_called_subset"]["outcome_regressions"] == 1
    assert summary["accepted_but_uncalled_tools"] == ["new_idle"]
    assert summary["helpers"]["new_idle"]["origin"] == "newly_generated"
    buckets = summary["selection_attribution_buckets"]
    assert buckets["called_generated_tool"]["scenarios"] == ["called"]
    assert buckets["called_generated_tool"]["mean_outcome_delta"] == 0.7
    assert buckets["generated_tool_visible_not_called"]["scenarios"] == ["ignored"]
    assert buckets["generated_tool_visible_not_called"]["outcome_regressions"] == 1
    assert buckets["no_visible_generated_tool"]["scenarios"] == ["hidden"]
    assert (
        summary["selection_attribution_claim_guidance"][
            "generated_helper_attributed_bucket"
        ]
        == "called_generated_tool"
    )


def test_helper_contribution_flags_called_subset_route_mismatch(tmp_path: Path) -> None:
    control = tmp_path / "control"
    candidate = tmp_path / "candidate"
    registry = tmp_path / "registry"
    _write_summary(
        control,
        [
            {"name": "gain", "similarity": 1.0, "outcome_similarity": 0.0},
            {"name": "second_gain", "similarity": 1.0, "outcome_similarity": 0.5},
            {"name": "loss", "similarity": 1.0, "outcome_similarity": 1.0},
        ],
    )
    _write_summary(
        candidate,
        [
            {"name": "gain", "similarity": 0.4, "outcome_similarity": 1.0},
            {"name": "second_gain", "similarity": 0.6, "outcome_similarity": 1.0},
            {"name": "loss", "similarity": 0.7, "outcome_similarity": 0.5},
        ],
    )
    (candidate / "scenario_tool_selection.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "scenario": scenario,
                    "generated_tools_visible": ["helper"],
                    "generated_tools_called": ["helper"],
                    "generated_tools_attempted": ["helper"],
                    "generated_tools_failed": [],
                }
            )
            for scenario in ("gain", "second_gain", "loss")
        )
        + "\n",
        encoding="utf-8",
    )
    registry.mkdir()
    (registry / "registry_manifest.json").write_text(
        json.dumps({"tools": {"helper": {}}}) + "\n",
        encoding="utf-8",
    )

    summary = build_helper_contribution_summary(
        control, candidate, registry_dir=registry
    )

    route = summary["helpers"]["helper"]["called_subset"]["route_mismatch_accounting"]
    assert route["helper_substitution_likely"] is True
    assert (
        route["reason"]
        == "called_subset_outcome_positive_but_canonical_negative_or_regressive"
    )
