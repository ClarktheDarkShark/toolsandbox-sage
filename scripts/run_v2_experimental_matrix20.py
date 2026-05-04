#!/usr/bin/env python3
"""Run the SAGE V2 20-scenario experiment matrix and summarize results."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sage_ts.evaluation.task_strata import expected_helper_fit
from sage_ts.experiments.v2_flags import (
    ALL_FEATURES,
    CANDIDATE_REPAIR,
    CONTRACT_SYNTHESIS,
    DEPENDENCY_LOGIC,
    EVIDENCE_ROUTING,
    GRADING_ACCOUNTING,
    LIVE_VALIDATION,
)

MATRIX_NAME = os.environ.get("SAGE_V2_MATRIX_NAME", "v2_experimental_matrix20_clean")
REGISTRY_MODE = os.environ.get("SAGE_V2_MATRIX_REGISTRY_MODE", "clean")
SUMMARY_ROOT = Path(f"artifacts/summaries/{MATRIX_NAME}")
OUTPUT_ROOT = Path(f"outputs/{MATRIX_NAME}")
REGISTRY_ROOT = Path(f"artifacts/registry_candidates/{MATRIX_NAME}")
SEED_REGISTRY = Path("artifacts/registry_candidates/v2_architecture_readiness_20")
SOURCE_MANIFEST = Path(
    "artifacts/summaries/v2_architecture_readiness_20/cohort_manifest.json"
)
SOURCE_DIVERSITY = Path(
    "artifacts/summaries/v2_architecture_readiness_20/cohort_diversity_report.json"
)
MANIFEST = SUMMARY_ROOT / "cohort_manifest.json"
DIVERSITY = SUMMARY_ROOT / "cohort_diversity_report.json"

VARIANTS = [
    {
        "id": "variant0_current_v2_baseline",
        "label": "Variant 0 - Current V2 Baseline",
        "features": "default",
        "purpose": "Current repaired V2 behavior as-is.",
    },
    {
        "id": "variant1_grading_accounting",
        "label": "Variant 1 - Grading-Accounted Helper Substitution",
        "features": GRADING_ACCOUNTING,
        "purpose": "Allow declared canonical-route substitution when final state is preserved.",
    },
    {
        "id": "variant2_dependency_logic",
        "label": "Variant 2 - Dependency/Precondition Bundle Logic",
        "features": DEPENDENCY_LOGIC,
        "purpose": "Enable generic dependency/precondition shortfall detection.",
    },
    {
        "id": "variant3_live_validation",
        "label": "Variant 3 - Lightweight Live Validation",
        "features": LIVE_VALIDATION,
        "purpose": "Run live positive/negative candidate checks after gate checks.",
    },
    {
        "id": "variant4_candidate_repair",
        "label": "Variant 4 - Candidate Repair Pass",
        "features": CANDIDATE_REPAIR,
        "purpose": "Attempt one structured repair before final rejection.",
    },
    {
        "id": "variant5_contract_synthesis",
        "label": "Variant 5 - Trigger/Tie/Ambiguity Contract Synthesis",
        "features": CONTRACT_SYNTHESIS,
        "purpose": "Strengthen generated spec trigger, tie, and ambiguity contracts.",
    },
    {
        "id": "variant6_evidence_routing",
        "label": "Variant 6 - Evidence-Aware Runtime Routing",
        "features": EVIDENCE_ROUTING,
        "purpose": "Use contribution evidence and visible-not-called risk in routing.",
    },
]


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _copy_registry(dst: Path) -> None:
    if dst.exists():
        raise SystemExit(f"Refusing to overwrite existing registry: {dst}")
    if REGISTRY_MODE == "warm_start":
        shutil.copytree(SEED_REGISTRY, dst)
        return
    dst.mkdir(parents=True)
    (dst / "registry_manifest.json").write_text(
        json.dumps({"tools": {}}, indent=2) + "\n", encoding="utf-8"
    )


def _latest_run_root(output_dir: Path) -> Path | None:
    if not output_dir.exists():
        return None
    candidates = [path for path in output_dir.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _scenario_names() -> list[str]:
    manifest = _read_json(MANIFEST, {})
    items = manifest.get("splits", {}).get("mechanism_40", [])
    return [str(item.get("name")) for item in items if isinstance(item, dict)]


def _negative_exposure(candidate_dir: Path | None) -> dict[str, Any]:
    names = set(_scenario_names())
    negative_names = {name for name in names if not expected_helper_fit(name)}
    if candidate_dir is None:
        return {
            "negative_scenario_count": len(negative_names),
            "exposed_count": 0,
            "scenarios": [],
        }
    visibility_path = candidate_dir / "scenario_tool_visibility.jsonl"
    exposed: list[str] = []
    for row in _read_jsonl(visibility_path):
        scenario = str(row.get("scenario", ""))
        if scenario in negative_names and row.get("generated_tools"):
            exposed.append(scenario)
    return {
        "negative_scenario_count": len(negative_names),
        "exposed_count": len(set(exposed)),
        "scenarios": sorted(set(exposed)),
    }


def _helper_totals(helper_summary: dict[str, Any]) -> dict[str, Any]:
    helpers = helper_summary.get("helpers", {})
    totals: Counter[str] = Counter()
    accepted_but_uncalled = list(helper_summary.get("accepted_but_uncalled_tools", []))
    called_subset_outcome: list[float] = []
    called_subset_canonical: list[float] = []
    vnc_subset_outcome: list[float] = []
    vnc_subset_canonical: list[float] = []
    side_effect_incidents = 0
    runtime_incidents = 0
    if isinstance(helpers, dict):
        for payload in helpers.values():
            if not isinstance(payload, dict):
                continue
            for key in (
                "visible_count",
                "called_count",
                "visible_not_called_count",
                "failed_attempt_count",
                "hidden_no_call_count",
            ):
                totals[key] += int(payload.get(key, 0) or 0)
            side_effect_incidents += len(payload.get("side_effect_incidents", []) or [])
            runtime_incidents += len(payload.get("runtime_incidents", []) or [])
            called = payload.get("called_subset", {})
            if isinstance(called, dict):
                if called.get("mean_outcome_delta") is not None:
                    called_subset_outcome.append(float(called["mean_outcome_delta"]))
                if called.get("mean_canonical_delta") is not None:
                    called_subset_canonical.append(
                        float(called["mean_canonical_delta"])
                    )
            vnc = payload.get("visible_not_called_subset", {})
            if isinstance(vnc, dict):
                if vnc.get("mean_outcome_delta") is not None:
                    vnc_subset_outcome.append(float(vnc["mean_outcome_delta"]))
                if vnc.get("mean_canonical_delta") is not None:
                    vnc_subset_canonical.append(float(vnc["mean_canonical_delta"]))
    return {
        **dict(totals),
        "accepted_but_uncalled_tools": accepted_but_uncalled,
        "called_subset_mean_outcome_delta": (
            sum(called_subset_outcome) / len(called_subset_outcome)
            if called_subset_outcome
            else None
        ),
        "called_subset_mean_canonical_delta": (
            sum(called_subset_canonical) / len(called_subset_canonical)
            if called_subset_canonical
            else None
        ),
        "visible_not_called_subset_mean_outcome_delta": (
            sum(vnc_subset_outcome) / len(vnc_subset_outcome)
            if vnc_subset_outcome
            else None
        ),
        "visible_not_called_subset_mean_canonical_delta": (
            sum(vnc_subset_canonical) / len(vnc_subset_canonical)
            if vnc_subset_canonical
            else None
        ),
        "side_effect_incidents": side_effect_incidents,
        "runtime_incidents": runtime_incidents,
    }


def _birth_summary(candidate_dir: Path | None) -> dict[str, Any]:
    if candidate_dir is None:
        return {}
    births = _read_jsonl(candidate_dir / "tool_birth_events.jsonl")
    rejection_reasons: Counter[str] = Counter()
    accepted: list[str] = []
    diagnostic: list[str] = []
    nondiagnostic: list[str] = []
    classifications: Counter[str] = Counter()
    live_findings: Counter[str] = Counter()
    repair_attempts = 0
    for birth in births:
        errors = birth.get("errors", []) or []
        for error in errors:
            rejection_reasons[str(error)] += 1
        if birth.get("accepted"):
            accepted.append(str(birth.get("tool_name")))
            # Diagnostic status is stored in registry; unknown here means diagnostic evidence only.
            if birth.get("source_example_count", 0) and birth.get(
                "held_out_check_count", 0
            ):
                nondiagnostic.append(str(birth.get("tool_name")))
            else:
                diagnostic.append(str(birth.get("tool_name")))
        classification = birth.get("grading_classification")
        if classification:
            classifications[str(classification)] += 1
        live = birth.get("lightweight_live_validation")
        if isinstance(live, dict):
            live_findings["checked"] += 1
            if live.get("accepted"):
                live_findings["accepted"] += 1
            else:
                live_findings["rejected"] += 1
        if birth.get("repair_attempted"):
            repair_attempts += 1
    return {
        "tools_proposed": len(births),
        "tools_accepted": len(accepted),
        "tools_rejected": max(0, len(births) - len(accepted)),
        "accepted_tools": accepted,
        "accepted_diagnostic_only_tools": diagnostic,
        "accepted_non_diagnostic_tools": nondiagnostic,
        "rejection_reasons": dict(rejection_reasons),
        "grading_classifications": dict(classifications),
        "live_validation_findings": dict(live_findings),
        "repair_attempts": repair_attempts,
    }


def _summarize_variant(
    variant: dict[str, str], run_root: Path | None, returncode: int, log_path: Path
) -> dict[str, Any]:
    if run_root is None:
        return {
            "variant": variant,
            "returncode": returncode,
            "log_path": str(log_path),
            "failed": True,
        }
    protocol = _read_json(run_root / "protocol_manifest.json", {})
    comparison = _read_json(run_root / "paired_comparison.json", {})
    helper_summary = _read_json(run_root / "helper_contribution_summary.json", {})
    candidate_dir = (
        Path(str(protocol.get("candidate_dir")))
        if protocol.get("candidate_dir")
        else None
    )
    birth = _birth_summary(candidate_dir)
    helpers = _helper_totals(helper_summary)
    control_cache = _read_json(run_root / "control_cache_report.json", {})
    candidate_cache = _read_json(
        run_root / "cache_artifacts/candidate/cache/cache_stats.json", {}
    )
    negative = _negative_exposure(candidate_dir)
    return {
        "variant": variant,
        "returncode": returncode,
        "failed": returncode != 0,
        "run_root": str(run_root),
        "log_path": str(log_path),
        "dashboard_path": protocol.get("dashboard_path"),
        "task_focus_dashboard": protocol.get("dashboard_task_focus_url"),
        "candidate_dir": str(candidate_dir) if candidate_dir else None,
        "control_cache_status": {
            "source": control_cache.get("control_source"),
            "cached": control_cache.get("cached_control_tasks"),
            "fresh": control_cache.get("fresh_control_tasks"),
            "manifest_hash": control_cache.get("cache_manifest_hash"),
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
        "birth": birth,
        "helpers": helpers,
        "negative_case_exposure": negative,
        "retained_helper_called_tools": helper_summary.get(
            "retained_helper_called_tools", []
        ),
        "newly_generated_helper_called_tools": helper_summary.get(
            "newly_generated_helper_called_tools", []
        ),
        "registry_size": helper_summary.get("registry_size"),
        "runtime_bundle_size": helper_summary.get("runtime_bundle_size"),
        "token_time_cache_usage": {
            "candidate_cache": candidate_cache,
            "control_cache": control_cache.get("estimated_token_time_savings"),
        },
    }


def _run_variant(variant: dict[str, str]) -> dict[str, Any]:
    variant_id = variant["id"]
    registry_dir = REGISTRY_ROOT / variant_id
    output_dir = OUTPUT_ROOT / variant_id
    log_dir = SUMMARY_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{variant_id}.log"
    _copy_registry(registry_dir)
    env = os.environ.copy()
    env["PYTHONPATH"] = "src:."
    env["SAGE_V2_EXPERIMENT_FEATURES"] = variant["features"]
    cmd = [
        sys.executable,
        "scripts/run_sage_protocol.py",
        "--manifest",
        str(MANIFEST),
        "--mode",
        "mechanism_40",
        "--registry-dir",
        str(registry_dir),
        "--output-root",
        str(output_dir),
        "--artifact-root",
        "artifacts",
        "--generation",
        "on",
        "--parallel-arms",
        "--control-cache",
        "use-if-eligible",
        "--no-dashboard-open",
    ]
    with log_path.open("w", encoding="utf-8") as log:
        log.write("COMMAND: " + " ".join(cmd) + "\n")
        log.write("SAGE_V2_EXPERIMENT_FEATURES=" + variant["features"] + "\n\n")
        result = subprocess.run(
            cmd,
            cwd=Path.cwd(),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    run_root = _latest_run_root(output_dir)
    summary = _summarize_variant(variant, run_root, result.returncode, log_path)
    (SUMMARY_ROOT / f"{variant_id}_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def _select_combined_features(summaries: list[dict[str, Any]]) -> str:
    by_id = {item["variant"]["id"]: item for item in summaries}
    baseline = by_id.get("variant0_current_v2_baseline", {})
    baseline_vnc = int(
        baseline.get("helpers", {}).get("visible_not_called_count", 999999) or 999999
    )
    features: set[str] = set()
    for item in summaries:
        variant_id = item["variant"]["id"]
        if variant_id == "variant0_current_v2_baseline" or item.get("failed"):
            continue
        outcome = item.get("outcome_delta")
        accepted = int(item.get("birth", {}).get("tools_accepted", 0) or 0)
        vnc = int(
            item.get("helpers", {}).get("visible_not_called_count", 999999) or 999999
        )
        runtime = int(item.get("runtime_exceptions", 0) or 0)
        side = int(item.get("helpers", {}).get("side_effect_incidents", 0) or 0)
        if runtime or side:
            continue
        useful = (
            (isinstance(outcome, int | float) and outcome > 0)
            or accepted > 0
            or vnc < baseline_vnc
        )
        if not useful:
            continue
        features.update(str(item["variant"]["features"]).split(","))
    features = {item for item in features if item and item in ALL_FEATURES}
    if not features:
        return "default"
    return ",".join(sorted(features))


def main() -> None:
    SUMMARY_ROOT.mkdir(parents=True, exist_ok=False)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=False)
    REGISTRY_ROOT.mkdir(parents=True, exist_ok=False)
    shutil.copy2(SOURCE_MANIFEST, MANIFEST)
    shutil.copy2(SOURCE_DIVERSITY, DIVERSITY)

    summaries: list[dict[str, Any]] = []
    for variant in VARIANTS:
        summaries.append(_run_variant(variant))

    combined_features = _select_combined_features(summaries)
    combined = {
        "id": "variant7_combined_best_stack",
        "label": "Variant 7 - Combined Best Stack",
        "features": combined_features,
        "purpose": "Combined features selected mechanically from Variants 1-6.",
    }
    summaries.append(_run_variant(combined))

    matrix = {
        "written_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(MANIFEST),
        "diversity_report": str(DIVERSITY),
        "registry_mode": REGISTRY_MODE,
        "seed_registry": (
            str(SEED_REGISTRY / "registry_manifest.json")
            if REGISTRY_MODE == "warm_start"
            else "empty registry_manifest.json"
        ),
        "combined_features": combined_features,
        "variants": summaries,
    }
    (SUMMARY_ROOT / "matrix_summary.json").write_text(
        json.dumps(matrix, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(matrix, indent=2))


if __name__ == "__main__":
    main()
