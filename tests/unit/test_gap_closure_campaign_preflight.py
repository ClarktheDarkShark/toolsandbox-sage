import json
from pathlib import Path

from pytest import MonkeyPatch

from scripts.preflight_gap_closure_campaign import build_preflight


def test_gap_closure_preflight_reports_missing_openai_key(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest = {
        "manifest_type": "sage_gap_closure_lab_splits",
        "split_aliases": {
            "pilot_20": "pilot_unseen",
            "expanded_60": "expanded_pilot_unseen",
            "confirm_100": "confirm_unseen",
            "validate_250": "scale_unseen",
        },
        "splits": {
            "pilot_unseen": [{"scenario_id": f"pilot_{index}"} for index in range(20)],
            "expanded_pilot_unseen": [
                {"scenario_id": f"expanded_{index}"} for index in range(60)
            ],
            "confirm_unseen": [
                {"scenario_id": f"confirm_{index}"} for index in range(100)
            ],
            "scale_unseen": [{"scenario_id": f"scale_{index}"} for index in range(250)],
        },
    }
    from sage_ts.config.gap_closure_lab import payload_sha256

    manifest["manifest_integrity"] = {
        "payload_sha256": payload_sha256(manifest),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    import hashlib

    file_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    manifest_path.with_suffix(".json.sha256").write_text(
        f"{file_hash}  manifest.json\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    preflight = build_preflight(manifest_path)

    assert preflight["status"] == "blocked"
    assert "missing_openai_api_key" in preflight["blockers"]
