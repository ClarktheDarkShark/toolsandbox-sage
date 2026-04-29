import json
from pathlib import Path

from sage_ts.campaign.artifacts import append_event


def test_duplicate_birth_skip_is_valid_campaign_event(tmp_path: Path) -> None:
    row = append_event(
        "tool_birth_skipped_existing",
        {"tool_name": "recency_to_timestamp_bounds"},
        root=tmp_path,
    )

    assert row["event"] == "tool_birth_skipped_existing"
    latest = tmp_path / "events" / "latest.jsonl"
    assert json.loads(latest.read_text(encoding="utf-8"))["tool_name"] == (
        "recency_to_timestamp_bounds"
    )
