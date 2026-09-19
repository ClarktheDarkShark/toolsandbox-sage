from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_h3_registry_assignment import build_assignment_file
from scripts.research.h3_registry_ablation import ROBUSTNESS_SUFFIXES


def _summary(path: Path) -> Path:
    rows = [
        {
            "name": f"task_{stem:03d}{suffix}",
            "outcome_similarity": 0.1 + stem / 1000,
        }
        for stem in range(129)
        for suffix in ("", *ROBUSTNESS_SUFFIXES)
    ]
    path.write_text(json.dumps({"per_scenario_results": rows}) + "\n", encoding="utf-8")
    return path


def test_build_assignment_file_is_balanced_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    control = _summary(tmp_path / "control.json")
    output = tmp_path / "assignment.json"

    manifest = build_assignment_file(
        control_summary=control, output=output, seed=20260918
    )

    assert json.loads(output.read_text(encoding="utf-8")) == manifest
    assert manifest["counts"]["registry_available_scenarios"] == 520
    assert manifest["counts"]["registry_masked_scenarios"] == 512
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        build_assignment_file(control_summary=control, output=output)
