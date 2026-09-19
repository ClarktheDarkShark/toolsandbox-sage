#!/usr/bin/env python3
"""Lock the H3 registry-availability assignment from completed H2 controls."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from scripts.research.h3_registry_ablation import (
    DEFAULT_ASSIGNMENT_SEED,
    build_registry_assignment,
)


def _control_rows(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read H2 control rows from {path}.") from exc
    rows: Any
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict) and isinstance(
        payload.get("per_scenario_results"), list
    ):
        rows = payload["per_scenario_results"]
    else:
        raise ValueError(
            "H2 control input must be a ToolSandbox result summary or a JSON row list."
        )
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("H2 control input contains a non-object row.")
    return [dict(row) for row in rows]


def build_assignment_file(
    *, control_summary: Path, output: Path, seed: int = DEFAULT_ASSIGNMENT_SEED
) -> dict[str, Any]:
    """Build, validate, and atomically persist one immutable H3 assignment."""

    if seed != DEFAULT_ASSIGNMENT_SEED:
        raise ValueError(
            f"H3 pilot assignment seed is locked to {DEFAULT_ASSIGNMENT_SEED}."
        )
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to overwrite H3 assignment: {output}")
    manifest = build_registry_assignment(_control_rows(control_summary), seed=seed)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, output)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--h2-control", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_ASSIGNMENT_SEED)
    args = parser.parse_args()
    manifest = build_assignment_file(
        control_summary=args.h2_control,
        output=args.output,
        seed=args.seed,
    )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "assignment_sha256": manifest["assignment_sha256"],
                "design_sha256": manifest["design_sha256"],
                "counts": manifest["counts"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
