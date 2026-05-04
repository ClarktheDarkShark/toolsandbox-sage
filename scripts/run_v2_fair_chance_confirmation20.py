#!/usr/bin/env python3
"""Run frozen fair-chance confirmations for matrix-born tools.

Each variant gets its accepted generated tools from the prior discovery run, then
runs generation OFF on the same quality-gated 20-scenario manifest. This accounts
for late birth by making accepted tools available from turn 1.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

RUN_NAME = os.environ.get("SAGE_V2_CONFIRMATION_NAME", "v2_fair_chance_confirmation20")
SUMMARY_ROOT = Path(f"artifacts/summaries/{RUN_NAME}")
OUTPUT_ROOT = Path(f"outputs/{RUN_NAME}")
REGISTRY_ROOT = Path(f"artifacts/registry_candidates/{RUN_NAME}")
SOURCE_MATRIX_ROOT = Path(
    os.environ.get(
        "SAGE_V2_CONFIRMATION_MATRIX_ROOT",
        "artifacts/summaries/v2_experimental_matrix20_clean",
    )
)
MANIFEST = Path(
    os.environ.get(
        "SAGE_V2_CONFIRMATION_MANIFEST",
        str(SOURCE_MATRIX_ROOT / "cohort_manifest.json"),
    )
)
DIVERSITY = Path(
    os.environ.get(
        "SAGE_V2_CONFIRMATION_DIVERSITY",
        str(SOURCE_MATRIX_ROOT / "cohort_diversity_report.json"),
    )
)

DEFAULT_VARIANTS = [
    {
        "id": "variant0_current_v2_baseline",
        "features": "default",
        "summary": "artifacts/summaries/v2_experimental_matrix20_clean/variant0_current_v2_baseline_summary.json",
    },
    {
        "id": "variant1_grading_accounting",
        "features": "grading_accounting",
        "summary": "artifacts/summaries/v2_experimental_matrix20_clean/variant1_grading_accounting_summary.json",
    },
    {
        "id": "variant2_dependency_logic",
        "features": "dependency_logic",
        "summary": "artifacts/summaries/v2_experimental_matrix20_clean/variant2_dependency_logic_summary.json",
    },
    {
        "id": "variant4_candidate_repair",
        "features": "candidate_repair",
        "summary": "artifacts/summaries/v2_experimental_matrix20_clean_repairfix/variant4_candidate_repair_summary.json",
    },
    {
        "id": "variant5_contract_synthesis",
        "features": "contract_synthesis",
        "summary": "artifacts/summaries/v2_experimental_matrix20_clean/variant5_contract_synthesis_summary.json",
    },
    {
        "id": "variant6_evidence_routing",
        "features": "evidence_routing",
        "summary": "artifacts/summaries/v2_experimental_matrix20_clean/variant6_evidence_routing_summary.json",
    },
    {
        "id": "variant7_combined_best_stack",
        "features": "candidate_repair,contract_synthesis,evidence_routing,grading_accounting",
        "summary": "artifacts/summaries/v2_experimental_matrix20_clean_repairfix/variant7_combined_best_stack_summary.json",
    },
]


def variants_from_source_matrix() -> list[dict[str, str]]:
    matrix_path = SOURCE_MATRIX_ROOT / "matrix_summary.json"
    if not matrix_path.exists():
        return DEFAULT_VARIANTS
    payload = read_json(matrix_path)
    variants: list[dict[str, str]] = []
    for item in payload.get("variants", []):
        variant = item.get("variant", {}) if isinstance(item, dict) else {}
        variant_id = str(variant.get("id", ""))
        features = str(variant.get("features", "default"))
        summary_path = SOURCE_MATRIX_ROOT / f"{variant_id}_summary.json"
        if variant_id and summary_path.exists():
            variants.append(
                {
                    "id": variant_id,
                    "features": features,
                    "summary": str(summary_path),
                }
            )
    return variants or DEFAULT_VARIANTS


def read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def source_registry(summary_path: Path) -> Path:
    summary = read_json(summary_path)
    run_root = Path(summary["run_root"])
    failed_gate = run_root / "registry_gate" / "registry_manifest_failed_gate.json"
    if failed_gate.exists():
        return failed_gate
    protocol = read_json(run_root / "protocol_manifest.json")
    return Path(protocol["registry_dir"]) / "registry_manifest.json"


def latest_run_root(output_dir: Path) -> Path | None:
    if not output_dir.exists():
        return None
    candidates = [p for p in output_dir.iterdir() if p.is_dir()]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def summarize(
    variant: dict[str, str], run_root: Path, log_path: Path, source: Path
) -> dict[str, Any]:
    protocol = read_json(run_root / "protocol_manifest.json")
    comparison = read_json(run_root / "paired_comparison.json")
    helper = read_json(run_root / "helper_contribution_summary.json")
    control_cache = read_json(run_root / "control_cache_report.json")
    helpers = (
        helper.get("helpers", {}) if isinstance(helper.get("helpers"), dict) else {}
    )
    visible = sum(int(v.get("visible_count", 0) or 0) for v in helpers.values())
    called = sum(int(v.get("called_count", 0) or 0) for v in helpers.values())
    vnc = sum(int(v.get("visible_not_called_count", 0) or 0) for v in helpers.values())
    side = sum(len(v.get("side_effect_incidents", []) or []) for v in helpers.values())
    runtime_inc = sum(
        len(v.get("runtime_incidents", []) or []) for v in helpers.values()
    )
    return {
        "variant": variant,
        "source_registry": str(source),
        "run_root": str(run_root),
        "log_path": str(log_path),
        "dashboard_path": protocol.get("dashboard_path"),
        "task_focus_path": str(run_root / "dashboard" / "task_focus.html"),
        "protocol_gate_passed": protocol.get("protocol_gate_passed"),
        "protocol_gate_reasons": protocol.get("protocol_gate_reasons"),
        "route_mismatch_qualified": protocol.get("route_mismatch_qualified"),
        "control_cache": {
            "source": control_cache.get("control_source"),
            "cached": control_cache.get("cached_control_tasks"),
            "fresh": control_cache.get("fresh_control_tasks"),
        },
        "outcome_delta": comparison.get("mean_outcome_similarity_delta"),
        "canonical_delta": comparison.get("mean_similarity_delta"),
        "exact_successes": {
            "control": comparison.get("control_exact_successes"),
            "sage": comparison.get("candidate_exact_successes"),
        },
        "gains_regressions_preserved": {
            "canonical": [
                comparison.get("gain_count"),
                comparison.get("regression_count"),
                comparison.get("preserved_count"),
            ],
            "outcome": [
                comparison.get("outcome_gain_count"),
                comparison.get("outcome_regression_count"),
                comparison.get("outcome_preserved_count"),
            ],
        },
        "runtime_exceptions": comparison.get("runtime_exception_count"),
        "helper_visible_called_vnc": [visible, called, vnc],
        "side_effect_incidents": side,
        "runtime_incidents": runtime_inc,
        "accepted_but_uncalled_tools": helper.get("accepted_but_uncalled_tools"),
        "retained_helper_called_tools": helper.get("retained_helper_called_tools"),
        "newly_generated_helper_called_tools": helper.get(
            "newly_generated_helper_called_tools"
        ),
        "helpers": helpers,
    }


def main() -> None:
    SUMMARY_ROOT.mkdir(parents=True, exist_ok=False)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=False)
    REGISTRY_ROOT.mkdir(parents=True, exist_ok=False)
    shutil.copy2(MANIFEST, SUMMARY_ROOT / "cohort_manifest.json")
    shutil.copy2(DIVERSITY, SUMMARY_ROOT / "cohort_diversity_report.json")
    (SUMMARY_ROOT / "logs").mkdir()
    summaries = []
    for variant in variants_from_source_matrix():
        src = source_registry(Path(variant["summary"]))
        src_payload = read_json(src)
        if not (src_payload.get("tools") or {}):
            summaries.append(
                {
                    "variant": variant,
                    "skipped": True,
                    "reason": "source_registry_empty",
                    "source_registry": str(src),
                }
            )
            continue
        registry_dir = REGISTRY_ROOT / variant["id"]
        registry_dir.mkdir(parents=True)
        shutil.copy2(src, registry_dir / "registry_manifest.json")
        output_dir = OUTPUT_ROOT / variant["id"]
        log_path = SUMMARY_ROOT / "logs" / f"{variant['id']}.log"
        env = os.environ.copy()
        env["PYTHONPATH"] = "src:."
        env["SAGE_V2_EXPERIMENT_FEATURES"] = variant["features"]
        cmd = [
            sys.executable,
            "scripts/run_sage_protocol.py",
            "--manifest",
            str(SUMMARY_ROOT / "cohort_manifest.json"),
            "--mode",
            "mechanism_40",
            "--registry-dir",
            str(registry_dir),
            "--output-root",
            str(output_dir),
            "--artifact-root",
            "artifacts",
            "--generation",
            "off",
            "--parallel-arms",
            "--control-cache",
            "use-if-eligible",
        ]
        with log_path.open("w", encoding="utf-8") as log:
            log.write("COMMAND: " + " ".join(cmd) + "\n")
            log.write("SAGE_V2_EXPERIMENT_FEATURES=" + variant["features"] + "\n")
            result = subprocess.run(
                cmd,
                cwd=Path.cwd(),
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        run_root = latest_run_root(output_dir)
        if run_root is None:
            summaries.append(
                {
                    "variant": variant,
                    "failed": True,
                    "returncode": result.returncode,
                    "log_path": str(log_path),
                    "source_registry": str(src),
                }
            )
        else:
            item = summarize(variant, run_root, log_path, src)
            item["returncode"] = result.returncode
            item["failed"] = result.returncode != 0
            summaries.append(item)
            (SUMMARY_ROOT / f"{variant['id']}_summary.json").write_text(
                json.dumps(item, indent=2) + "\n", encoding="utf-8"
            )
    matrix = {
        "written_at": datetime.now(timezone.utc).isoformat(),
        "run_name": RUN_NAME,
        "manifest": str(SUMMARY_ROOT / "cohort_manifest.json"),
        "diversity_report": str(SUMMARY_ROOT / "cohort_diversity_report.json"),
        "generation": "off",
        "purpose": "Fair-chance frozen confirmation: accepted tools from discovery variants available from turn 1.",
        "variants": summaries,
    }
    (SUMMARY_ROOT / "confirmation_summary.json").write_text(
        json.dumps(matrix, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(matrix, indent=2))


if __name__ == "__main__":
    main()
