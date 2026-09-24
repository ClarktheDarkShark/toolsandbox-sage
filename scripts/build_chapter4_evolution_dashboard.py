#!/usr/bin/env python3
"""Build the reordered Chapter 4 self-evolution evidence dashboard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.research.chapter4_evidence import EVIDENCE_HTML_NAME
from scripts.research.chapter4_evolution_evidence import (
    write_evolution_evidence_dashboard,
)


def _corroboration_entry(args: argparse.Namespace) -> dict[str, Any] | None:
    if args.corroboration_verification is None:
        return None
    if args.corroboration_registry_dir is None:
        raise ValueError(
            "--corroboration-registry-dir is required with "
            "--corroboration-verification."
        )
    verification = json.loads(
        args.corroboration_verification.resolve().read_text(encoding="utf-8")
    )
    if not isinstance(verification, dict) or verification.get("status") != "pass":
        raise ValueError("The corroboration verification receipt is not passing.")
    run_root = verification.get("run_root")
    if not isinstance(run_root, str) or not run_root:
        raise ValueError("The corroboration verification receipt has no run_root.")
    return {
        "replication": 0,
        "label": args.corroboration_label,
        "run_root": run_root,
        "registry_dir": str(args.corroboration_registry_dir.resolve()),
        "verification_receipt": str(args.corroboration_verification.resolve()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--bootstrap-iterations", type=int, default=10_000)
    parser.add_argument("--randomization-iterations", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--corroboration-verification", type=Path)
    parser.add_argument("--corroboration-registry-dir", type=Path)
    parser.add_argument(
        "--corroboration-label",
        default="Randomized task order",
    )
    args = parser.parse_args()
    if args.bootstrap_iterations < 100:
        parser.error("--bootstrap-iterations must be at least 100")
    if args.randomization_iterations < 100:
        parser.error("--randomization-iterations must be at least 100")

    data = write_evolution_evidence_dashboard(
        repo_root=args.repo_root.resolve(),
        campaign_manifest_path=args.campaign_manifest.resolve(),
        output_dir=args.output_dir.resolve(),
        bootstrap_iterations=args.bootstrap_iterations,
        randomization_iterations=args.randomization_iterations,
        seed=args.seed,
        corroboration_entry=_corroboration_entry(args),
    )
    print(
        "chapter4_evolution_evidence "
        f"online={data['campaign']['completed_online_runs']} "
        f"h1={data['hypotheses'][0]['value_label']} "
        f"h2={data['hypotheses'][1]['value_label']} "
        f"h3={data['hypotheses'][2]['value_label']} "
        f"dashboard={args.output_dir.resolve() / EVIDENCE_HTML_NAME}",
        flush=True,
    )


if __name__ == "__main__":
    main()
