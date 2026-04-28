from pathlib import Path

from sage_ts.adapters.toolsandbox_adapter import (
    ToolSandboxRunConfig,
    write_run_manifest,
)


def test_write_run_manifest(tmp_path: Path) -> None:
    config = ToolSandboxRunConfig(
        agent="Unhelpful",
        user="GPT_4_o_2024_05_13",
        scenario_names=("wifi_off",),
        output_dir=tmp_path,
    )

    path = write_run_manifest(config)
    text = path.read_text(encoding="utf-8")

    assert "wifi_off" in text
    assert "baseline" in text
