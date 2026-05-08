import json
from pathlib import Path

from sage_ts.config.campaign_splits import make_campaign_manifest
from sage_ts.config.splits import load_split_names, write_split_manifest


def test_write_and_load_split_manifest(tmp_path: Path) -> None:
    manifest_path = write_split_manifest(tmp_path / "splits.json", seed=7)

    smoke = load_split_names(manifest_path, "smoke_10")
    online = load_split_names(manifest_path, "online_build_100")

    assert len(smoke) == 10
    assert len(online) == 100
    assert len(set(smoke)) == 10
    assert not set(smoke) & set(online)


def test_load_split_names_resolves_manifest_alias(tmp_path: Path) -> None:
    manifest_path = tmp_path / "aliased_splits.json"
    manifest_path.write_text(
        json.dumps(
            {
                "splits": {
                    "pilot_unseen": [
                        {"scenario_id": "task_a"},
                        {"scenario_id": "task_b"},
                    ]
                },
                "split_aliases": {"pilot_20": "pilot_unseen"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert load_split_names(manifest_path, "pilot_20") == ["task_a", "task_b"]


def test_campaign_manifest_front_loads_recency_birth_scenarios() -> None:
    manifest = make_campaign_manifest()
    mechanism = manifest["splits"]["mechanism_40"]  # type: ignore[index]
    transfer = manifest["splits"]["transfer_40"]  # type: ignore[index]

    assert len(mechanism) == 40
    assert len(transfer) == 40
    assert mechanism[0]["name"].startswith("search_reminder_with_recency_yesterday")
    assert mechanism[1]["name"].startswith("search_reminder_with_recency_upcoming")
    assert manifest["split_sizes"]["transfer_40"] == 40  # type: ignore[index]
    assert {row["name"] for row in mechanism}.isdisjoint(
        {row["name"] for row in transfer}
    )
