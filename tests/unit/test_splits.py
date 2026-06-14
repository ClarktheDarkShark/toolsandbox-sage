from pathlib import Path

from sage_ts.config.splits import load_split_names, write_split_manifest


def test_write_and_load_split_manifest(tmp_path: Path) -> None:
    manifest_path = write_split_manifest(tmp_path / "splits.json", seed=7)

    smoke = load_split_names(manifest_path, "smoke_10")
    online = load_split_names(manifest_path, "online_build_100")

    assert len(smoke) == 10
    assert len(online) == 100
    assert len(set(smoke)) == 10
    assert not set(smoke) & set(online)
