from pathlib import Path

from sage_ts.config.splits import load_split_names


def test_loads_sealed_full_benchmark_manifest() -> None:
    manifest_path = (
        Path(__file__).resolve().parents[2]
        / "docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json"
    )

    scenarios = load_split_names(manifest_path, "full_benchmark")

    assert len(scenarios) == 1032
    assert len(set(scenarios)) == 1032
