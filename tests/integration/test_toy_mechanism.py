import json
from pathlib import Path

from sage_ts.orchestration.toy_mechanism import run_toy_birth_reuse


def test_toy_mechanism_writes_lineage_artifacts(tmp_path: Path) -> None:
    result = run_toy_birth_reuse(tmp_path)

    assert result == {"accepted": True, "reused": True, "improved": True}
    assert (tmp_path / "registry" / "registry_manifest.json").exists()
    assert (tmp_path / "tool_birth_events.jsonl").exists()
    assert (tmp_path / "reuse_events.jsonl").exists()

    registry = json.loads(
        (tmp_path / "registry" / "registry_manifest.json").read_text()
    )
    entry = registry["tools"]["canonicalize_connectivity_label"]
    assert entry["reuse_count"] == 1
    assert entry["success_flips"] == 1
