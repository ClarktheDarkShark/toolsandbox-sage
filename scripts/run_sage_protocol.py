#!/usr/bin/env python3
# mypy: ignore-errors
"""Run paired ToolSandbox SAGE mechanism/transfer/extended-reuse gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
import traceback
from datetime import datetime
from multiprocessing import get_context
from pathlib import Path
from typing import Any, cast

from sage_ts.adapters.openai_agent_adapter import OpenAIChatAdapter
from sage_ts.adapters.sage_run_adapter import SageRunConfig, run_sage_with_registry
from sage_ts.adapters.toolsandbox_adapter import ToolSandboxRunConfig, run_toolsandbox
from sage_ts.cache.openai_response_cache import (
    configure_response_cache_context,
    install_openai_response_cache,
    write_cache_artifacts,
)
from sage_ts.cache.openai_response_cache import (
    reset_metrics as reset_openai_response_cache_metrics,
)
from sage_ts.cache.openai_response_cache import (
    write_metrics as write_openai_response_cache_metrics,
)
from sage_ts.campaign.artifacts import (
    append_event,
    initialize_campaign,
    record_run,
    snapshot_registry,
    update_task,
)
from sage_ts.config.models import DEFAULT_MODEL, paired_model_metadata
from sage_ts.config.splits import load_split_names, scenario_records
from sage_ts.dashboard.exporters import (
    dashboard_url as make_dashboard_url,
)
from sage_ts.dashboard.exporters import (
    open_dashboard,
    write_protocol_dashboard,
)
from sage_ts.evaluation.control_baseline_cache import (
    ControlBaselineCache,
    build_control_cache_report,
    plan_control_cache,
    write_synthetic_control_run,
)
from sage_ts.evaluation.helper_contribution import write_helper_contribution_summary
from sage_ts.evaluation.run_metrics import compare_runs
from sage_ts.evaluation.task_strata import cohort_policy_report
from sage_ts.generation.prompt_cache import PromptCache
from sage_ts.generation.tool_generator import ToolGenerator
from sage_ts.runtime.base_toolset import KNOWN_POLICIES, UPSTREAM_POLICY

# Run modes are also split names. Keep these explicit so bad campaign labels
# fail early, but support campaign-sized protocol runs directly.
MODES = (
    # Smoke / wiring checks
    "smoke_6",
    "smoke_12",
    # Mechanism / tool-birth checks
    "viability_12",
    "mechanism_12",
    "mechanism_40",
    "mechanism_60",
    "online_build_100",
    "online_build_250",
    "online_build_500",
    # Frozen transfer checks
    "transfer_40",
    "transfer_60",
    "transfer_100",
    # Confirmation / validation
    "extended_reuse_100",
    "confirm_100",
    "validate_100",
    "promotion_250",
    "validate_250",
    "full_benchmark",
)


def _manifest_type(manifest: Path) -> str:
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(payload.get("manifest_type", ""))


def _generation_enabled_by_default(mode: str, manifest_type: str) -> bool:
    """Default live generation for build/discovery lanes, not frozen validation."""

    generation_modes = {
        "smoke_6",
        "smoke_12",
        "viability_12",
        "mechanism_12",
        "mechanism_40",
        "mechanism_60",
        "online_build_100",
        "online_build_250",
        "online_build_500",
        "extended_reuse_100",
    }
    if mode in generation_modes:
        return True
    return "discovery" in manifest_type.lower()


def _is_frozen_transfer_mode(mode: str) -> bool:
    """Modes that should default to generation disabled."""

    frozen_modes = {
        "transfer_40",
        "transfer_60",
        "transfer_100",
        "confirm_100",
        "validate_100",
        "promotion_250",
        "validate_250",
        "full_benchmark",
    }
    return mode in frozen_modes


DIAGNOSTIC_FORCE_ENV_VARS = (
    "SAGE_DIAGNOSTIC_FORCE_TOOL_NAME",
    "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_ERROR",
    "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_BASE_TOOL",
)


def _active_diagnostic_force_env(env: dict[str, str] | None = None) -> dict[str, str]:
    env = env or os.environ
    return {
        name: value
        for name in DIAGNOSTIC_FORCE_ENV_VARS
        if (value := str(env.get(name, "")).strip())
    }


def _redacted_run_affecting_sage_env() -> dict[str, str]:
    blocked_tokens = ("API", "KEY", "TOKEN", "SECRET")
    values: dict[str, str] = {}
    for name, value in sorted(os.environ.items()):
        if not name.startswith("SAGE_"):
            continue
        if any(token in name.upper() for token in blocked_tokens):
            values[name] = "<redacted>"
        else:
            values[name] = value
    return values


def _looks_like_openai_model(model: str) -> bool:
    name = model.strip().lower()
    return name.startswith(("gpt-", "o1", "o3", "o4"))


def _preflight_openai_api_key(
    *,
    agent_model: str,
    user_model: str,
    generation_model: str,
    generation_enabled: bool,
) -> None:
    """Fail before task execution if an OpenAI-backed run has no API key."""

    requires_openai = (
        _looks_like_openai_model(agent_model)
        or _looks_like_openai_model(user_model)
        or (generation_enabled and _looks_like_openai_model(generation_model))
    )
    if not requires_openai:
        return
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key.strip():
        raise SystemExit(
            "OPENAI_API_KEY is required for this OpenAI-backed run but is "
            "missing or blank. Aborting before task execution."
        )


def _resolve_routing_evidence_mode(requested: str, *, frozen_final_run: bool) -> str:
    requested = requested.strip().lower()
    if requested == "default":
        return "disabled" if frozen_final_run else "auto"
    if requested in {"auto", "disabled", "pinned"}:
        return requested
    raise ValueError(f"unsupported_routing_evidence_mode:{requested}")


def _apply_routing_evidence_env(mode: str, path: Path | None) -> None:
    os.environ["SAGE_ROUTING_EVIDENCE_MODE"] = mode
    if path is not None:
        os.environ["SAGE_ROUTING_EVIDENCE_PATH"] = str(path)
    else:
        os.environ.pop("SAGE_ROUTING_EVIDENCE_PATH", None)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _arm_status_path(run_root: Path, arm: str) -> Path:
    return run_root / f"{arm}_arm_status.json"


def _write_arm_status(
    run_root: Path,
    arm: str,
    *,
    status: str,
    run_dir: Path | None = None,
    completed_count: int | None = None,
    scenario_count: int | None = None,
    error: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "arm": arm,
        "status": status,
        "updated_at": datetime.now().isoformat(),
    }
    if run_dir is not None:
        payload["run_dir"] = str(run_dir)
    if completed_count is not None:
        payload["completed_count"] = completed_count
    if scenario_count is not None:
        payload["scenario_count"] = scenario_count
    if error is not None:
        payload["error"] = error
    _arm_status_path(run_root, arm).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def _read_arm_status(run_root: Path, arm: str) -> dict[str, Any]:
    path = _arm_status_path(run_root, arm)
    if not path.exists():
        return {}
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _latest_run_dir(root: Path) -> Path | None:
    if not root.exists():
        return None
    candidates = [path for path in root.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _status_run_dir(run_root: Path, arm: str, root: Path) -> Path | None:
    status = _read_arm_status(run_root, arm)
    raw = status.get("run_dir")
    if isinstance(raw, str) and raw:
        path = Path(raw)
        if path.exists():
            return path
    return _latest_run_dir(root)


def _registry_tool_count(registry_dir: Path) -> int:
    manifest_path = registry_dir / "registry_manifest.json"
    if not manifest_path.exists():
        return 0
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    tools = manifest.get("tools")
    return len(tools) if isinstance(tools, dict) else 0


def _digest_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot_registry_for_gate(run_root: Path, registry_dir: Path) -> dict[str, Any]:
    """Snapshot registry state so failed gated runs cannot contaminate follow-ups."""
    gate_dir = run_root / "registry_gate"
    gate_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = registry_dir / "registry_manifest.json"
    snapshot_path = gate_dir / "registry_manifest_before_run.json"
    existed = manifest_path.exists()
    if existed:
        shutil.copy2(manifest_path, snapshot_path)
    metadata = {
        "registry_dir": str(registry_dir),
        "manifest_existed_before_run": existed,
        "snapshot_path": str(snapshot_path) if existed else None,
        "manifest_digest_before_run": _digest_file(manifest_path) if existed else None,
    }
    (gate_dir / "registry_gate_snapshot.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return metadata


def _restore_registry_after_failed_gate(
    *,
    run_root: Path,
    registry_dir: Path,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Preserve the failed registry, then restore the pre-run registry manifest."""
    gate_dir = run_root / "registry_gate"
    gate_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = registry_dir / "registry_manifest.json"
    failed_snapshot_path = gate_dir / "registry_manifest_failed_gate.json"
    if manifest_path.exists():
        shutil.copy2(manifest_path, failed_snapshot_path)

    prior_snapshot = snapshot.get("snapshot_path")
    prior_exists = bool(snapshot.get("manifest_existed_before_run"))
    if prior_exists and isinstance(prior_snapshot, str):
        registry_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(prior_snapshot), manifest_path)
    elif manifest_path.exists():
        manifest_path.unlink()

    result = {
        "registry_dir": str(registry_dir),
        "restored": True,
        "manifest_existed_before_run": prior_exists,
        "failed_snapshot_path": str(failed_snapshot_path)
        if failed_snapshot_path.exists()
        else None,
        "restored_snapshot_path": prior_snapshot if prior_exists else None,
    }
    (gate_dir / "registry_gate_restore.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def _write_cohort_preflight(
    run_root: Path,
    *,
    scenario_names: tuple[str, ...],
    generation_enabled: bool,
    registry_dir: Path,
) -> dict[str, object]:
    categories_by_name = {
        record.name: record.categories for record in scenario_records()
    }
    report = cohort_policy_report(
        scenario_names,
        categories_by_name=categories_by_name,
        generation_enabled=generation_enabled,
        registry_tool_count=_registry_tool_count(registry_dir),
    )
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "cohort_preflight_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    diversity_report = {
        "scenario_count": report.get("scenario_count"),
        "distinct_base_task_families": report.get("distinct_base_task_families"),
        "required_distinct_base_task_families": report.get(
            "required_distinct_base_task_families"
        ),
        "largest_family_share": report.get("largest_family_share"),
        "family_counts": report.get("family_counts", {}),
        "strata_counts": report.get("strata_counts", {}),
        "warnings": report.get("warnings", []),
        "decision_use": report.get("decision_use"),
    }
    (run_root / "cohort_diversity_report.json").write_text(
        json.dumps(diversity_report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _route_mismatch_qualified(comparison: dict[str, Any]) -> bool:
    """True when outcome improves despite canonical/exact accounting disagreement."""
    canonical_delta = float(comparison.get("mean_similarity_delta", 0.0) or 0.0)
    outcome_delta = _optional_float(comparison.get("mean_outcome_similarity_delta"))
    exact_delta = int(comparison.get("exact_success_delta", 0) or 0)
    gains = int(comparison.get("gain_count", 0) or 0)
    regressions = int(comparison.get("regression_count", 0) or 0)
    outcome_gains = int(comparison.get("outcome_gain_count", 0) or 0)
    outcome_regressions = int(comparison.get("outcome_regression_count", 0) or 0)
    runtime_exceptions = int(comparison.get("runtime_exception_count", 0) or 0)
    candidate = cast(dict[str, Any], comparison.get("candidate", {}))
    called = int(candidate.get("generated_tool_called_scenarios", 0) or 0)
    accepted = int(candidate.get("accepted_tool_count", 0) or 0)
    canonical_or_exact_disagrees = (
        canonical_delta <= 0 or gains <= regressions or exact_delta < 0
    )
    return (
        runtime_exceptions == 0
        and outcome_delta is not None
        and outcome_delta > 0
        and outcome_gains > outcome_regressions
        and (called > 0 or accepted > 0)
        and canonical_or_exact_disagrees
    )


def _protocol_gate_decision(
    comparison: dict[str, Any],
    *,
    scenario_count: int,
) -> tuple[bool, list[str]]:
    """Apply campaign viability gates with outcome primary and canonical reported."""
    reasons: list[str] = []
    delta = float(comparison.get("mean_similarity_delta", 0.0) or 0.0)
    outcome_delta = _optional_float(comparison.get("mean_outcome_similarity_delta"))
    exact_delta = int(comparison.get("exact_success_delta", 0) or 0)
    gains = int(comparison.get("gain_count", 0) or 0)
    regressions = int(comparison.get("regression_count", 0) or 0)
    outcome_gains = int(comparison.get("outcome_gain_count", 0) or 0)
    outcome_regressions = int(comparison.get("outcome_regression_count", 0) or 0)
    runtime_exceptions = int(comparison.get("runtime_exception_count", 0) or 0)
    candidate = cast(dict[str, Any], comparison.get("candidate", {}))
    called = int(candidate.get("generated_tool_called_scenarios", 0) or 0)
    accepted = int(candidate.get("accepted_tool_count", 0) or 0)
    route_mismatch = _route_mismatch_qualified(comparison)
    outcome_qualified = (
        runtime_exceptions == 0
        and outcome_delta is not None
        and outcome_delta > 0
        and outcome_gains > outcome_regressions
        and (called > 0 or accepted > 0)
    )

    if runtime_exceptions:
        reasons.append("runtime_exceptions_present")
    if outcome_delta is not None:
        if outcome_delta <= 0:
            reasons.append("non_positive_outcome_delta")
        if outcome_gains <= outcome_regressions:
            reasons.append("outcome_gains_do_not_exceed_regressions")
    elif delta <= 0:
        reasons.append("outcome_score_unavailable_and_non_positive_canonical_delta")
    if delta <= 0 and not (route_mismatch or outcome_qualified):
        reasons.append("non_positive_canonical_delta")
    if gains <= regressions and not outcome_qualified:
        reasons.append("gains_do_not_exceed_regressions")

    if scenario_count >= 30:
        primary_delta = outcome_delta if outcome_delta is not None else delta
        primary_gains = outcome_gains if outcome_delta is not None else gains
        primary_regressions = (
            outcome_regressions if outcome_delta is not None else regressions
        )
        ratio = primary_gains / max(primary_regressions, 1)
        called_share = called / scenario_count if scenario_count else 0.0
        if primary_delta < 0.08:
            reasons.append("confirmation_outcome_delta_below_0_08")
        if exact_delta <= 0 and not outcome_qualified:
            reasons.append("exact_successes_not_improved")
        if ratio < 1.4:
            reasons.append("gain_regression_ratio_below_1_4")
        if called_share < 0.25:
            reasons.append("helper_call_share_below_25_percent")
    elif scenario_count >= 12:
        if exact_delta < 0 and not outcome_qualified:
            reasons.append("exact_successes_regressed")
        if accepted <= 0 and called < 3:
            reasons.append("no_accepted_helper_and_fewer_than_3_helper_calls")

    return not reasons, reasons


def _resume_arm_dir(resume_run_root: Path | None, arm: str) -> Path | None:
    if resume_run_root is None:
        return None
    return _status_run_dir(resume_run_root, arm, resume_run_root / arm)


def _protocol_event(
    *,
    event: str,
    mode: str,
    run_root: Path,
    run_dir: Path,
    payload: dict[str, object],
    artifact_root: Path,
) -> None:
    append_event(
        event,
        {
            "mode": mode,
            "run_root": str(run_root),
            "run_dir": str(run_dir),
            **payload,
        },
        root=artifact_root,
    )


def _run_control_arm_worker(params: dict[str, Any]) -> None:
    run_root = Path(params["run_root"])
    artifact_root = Path(params["artifact_root"])
    control_root = Path(params["control_root"])
    scenario_names = tuple(params["scenario_names"])
    response_cache_enabled = bool(params["response_cache_enabled"])
    _write_arm_status(
        run_root,
        "control",
        status="starting",
        completed_count=0,
        scenario_count=len(scenario_names),
    )
    try:
        if response_cache_enabled:
            install_openai_response_cache(
                Path(params["openai_response_cache_dir"]),
                mode=str(params["cache_mode"]),
            )
        configure_response_cache_context(
            mode=str(params["mode"]),
            arm="control",
            agent=str(params["agent"]),
            user=str(params["user"]),
            base_tool_policy=str(params["base_tool_policy"]),
            scenario_names=scenario_names,
            registry_dir=None,
            generation_enabled=False,
            generation_model=str(params["generation_model"]),
            recurrence_threshold=int(params["recurrence_threshold"]),
            run_config_extra={"parallel_arms": True},
        )
        reset_openai_response_cache_metrics()

        def progress(
            run_dir: Path,
            rows: list[dict[str, object]],
            status: str,
            scenario_count: int,
        ) -> None:
            _write_arm_status(
                run_root,
                "control",
                status=status,
                run_dir=run_dir,
                completed_count=len(rows),
                scenario_count=scenario_count,
            )

        def event_hook(event: str, run_dir: Path, payload: dict[str, object]) -> None:
            _protocol_event(
                event=event,
                mode=str(params["mode"]),
                run_root=run_root,
                run_dir=run_dir,
                payload=payload,
                artifact_root=artifact_root,
            )

        run_dir = run_toolsandbox(
            ToolSandboxRunConfig(
                agent=str(params["agent"]),
                user=str(params["user"]),
                scenario_names=scenario_names,
                output_dir=control_root,
                processes=1,
                run_type=f"{params['mode']}_control",
                base_tool_policy=str(params["base_tool_policy"]),
                resume_from_dir=Path(params["control_resume_dir"])
                if params.get("control_resume_dir")
                else None,
            ),
            progress_hook=progress,
            event_hook=event_hook,
        )
        if response_cache_enabled:
            write_openai_response_cache_metrics(
                run_dir / "openai_response_cache_metrics.json"
            )
            write_cache_artifacts(run_root / "cache_artifacts" / "control")
        append_event(
            "phase_completed",
            {
                "mode": params["mode"],
                "phase": "control",
                "run_dir": str(run_dir),
                "parallel_arms": True,
            },
            root=artifact_root,
        )
        _write_arm_status(
            run_root,
            "control",
            status="complete",
            run_dir=run_dir,
            completed_count=len(scenario_names),
            scenario_count=len(scenario_names),
        )
    except Exception:
        error = traceback.format_exc()
        _write_arm_status(run_root, "control", status="failed", error=error)
        append_event(
            "blocker_detected",
            {
                "mode": params["mode"],
                "phase": "control",
                "run_root": str(run_root),
                "error": error,
            },
            root=artifact_root,
        )
        raise


def _run_candidate_arm_worker(params: dict[str, Any]) -> None:
    run_root = Path(params["run_root"])
    artifact_root = Path(params["artifact_root"])
    candidate_root = Path(params["candidate_root"])
    registry_dir = Path(params["registry_dir"])
    scenario_names = tuple(params["scenario_names"])
    generation_enabled = bool(params["generation_enabled"])
    response_cache_enabled = bool(params["response_cache_enabled"])
    _write_arm_status(
        run_root,
        "candidate",
        status="starting",
        completed_count=0,
        scenario_count=len(scenario_names),
    )
    try:
        if response_cache_enabled:
            install_openai_response_cache(
                Path(params["openai_response_cache_dir"]),
                mode=str(params["cache_mode"]),
            )
        configure_response_cache_context(
            mode=str(params["mode"]),
            arm="candidate",
            agent=str(params["agent"]),
            user=str(params["user"]),
            base_tool_policy=str(params["base_tool_policy"]),
            scenario_names=scenario_names,
            registry_dir=registry_dir,
            generation_enabled=generation_enabled,
            generation_model=str(params["generation_model"]),
            recurrence_threshold=int(params["recurrence_threshold"]),
            run_config_extra={"parallel_arms": True},
        )
        reset_openai_response_cache_metrics()
        prompt_cache = PromptCache(Path(params["prompt_cache_dir"]))
        generator = (
            ToolGenerator(
                completer=OpenAIChatAdapter(model=str(params["generation_model"])),
                cache=prompt_cache,
            )
            if generation_enabled
            else None
        )

        def progress(
            run_dir: Path,
            rows: list[dict[str, object]],
            status: str,
            scenario_count: int,
        ) -> None:
            _write_arm_status(
                run_root,
                "candidate",
                status=status,
                run_dir=run_dir,
                completed_count=len(rows),
                scenario_count=scenario_count,
            )

        def event_hook(event: str, run_dir: Path, payload: dict[str, object]) -> None:
            _protocol_event(
                event=event,
                mode=str(params["mode"]),
                run_root=run_root,
                run_dir=run_dir,
                payload=payload,
                artifact_root=artifact_root,
            )

        run_dir = run_sage_with_registry(
            SageRunConfig(
                agent=str(params["agent"]),
                user=str(params["user"]),
                scenario_names=scenario_names,
                output_dir=candidate_root,
                registry_dir=registry_dir,
                run_type=f"{params['mode']}_candidate",
                recurrence_threshold=int(params["recurrence_threshold"]),
                base_tool_policy=str(params["base_tool_policy"]),
                resume_from_dir=Path(params["candidate_resume_dir"])
                if params.get("candidate_resume_dir")
                else None,
                manifest_path=Path(params["manifest"]),
            ),
            generator=generator,
            progress_hook=progress,
            event_hook=event_hook,
        )
        (run_dir / "prompt_cache_metrics.json").write_text(
            json.dumps(prompt_cache.metrics(), indent=2) + "\n",
            encoding="utf-8",
        )
        if response_cache_enabled:
            write_openai_response_cache_metrics(
                run_dir / "openai_response_cache_metrics.json"
            )
            write_cache_artifacts(run_root / "cache_artifacts" / "candidate")
        live_summary = _read_metrics(run_dir / "live_result_summary.json")
        completed_count = int(
            live_summary.get("completed_count", len(scenario_names))
            or len(scenario_names)
        )
        final_status = str(live_summary.get("status", "complete") or "complete")
        _write_arm_status(
            run_root,
            "candidate",
            status=final_status,
            run_dir=run_dir,
            completed_count=completed_count,
            scenario_count=len(scenario_names),
        )
    except Exception:
        error = traceback.format_exc()
        _write_arm_status(run_root, "candidate", status="failed", error=error)
        append_event(
            "blocker_detected",
            {
                "mode": params["mode"],
                "phase": "candidate",
                "run_root": str(run_root),
                "error": error,
            },
            root=artifact_root,
        )
        raise


def _read_metrics(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _write_parallel_cache_artifacts(
    *,
    artifact_root: Path,
    run_root: Path,
    cache_mode: str,
    control_cache_dir: Path,
    candidate_cache_dir: Path,
    control_dir: Path | None,
    candidate_dir: Path | None,
) -> None:
    cache_root = artifact_root / "cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    metrics_by_arm = {
        "control": _read_metrics(
            control_dir / "openai_response_cache_metrics.json"
            if control_dir is not None
            else Path("")
        ),
        "candidate": _read_metrics(
            candidate_dir / "openai_response_cache_metrics.json"
            if candidate_dir is not None
            else Path("")
        ),
    }
    totals: dict[str, int] = {}
    for metrics in metrics_by_arm.values():
        for key, value in metrics.items():
            if isinstance(value, int):
                totals[key] = totals.get(key, 0) + value
    manifest = {
        "cache_mode": cache_mode,
        "parallel_arms": True,
        "parallel_cache_policy": "per_arm",
        "arm_cache_roots": {
            "control": str(control_cache_dir),
            "candidate": str(candidate_cache_dir),
        },
        "run_root": str(run_root),
        "combined_sqlite_path": str(cache_root / "openai_response_cache.sqlite"),
        "note": "Parallel paired runs keep per-arm SQLite caches to avoid cross-arm cache state and write-lock contention.",
    }
    stats = {
        "cache_mode": cache_mode,
        "parallel_arms": True,
        "control_evolve_cache_symmetry": cache_mode,
        "arms": metrics_by_arm,
        "totals": totals,
    }
    (cache_root / "cache_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (cache_root / "cache_stats.json").write_text(
        json.dumps(stats, indent=2) + "\n", encoding="utf-8"
    )
    event_parts: list[str] = []
    for arm in ("control", "candidate"):
        events_path = (
            run_root / "cache_artifacts" / arm / "cache" / "cache_events.jsonl"
        )
        if events_path.exists():
            event_parts.append(events_path.read_text(encoding="utf-8"))
    (cache_root / "cache_events.jsonl").write_text(
        "".join(event_parts), encoding="utf-8"
    )
    (cache_root / "openai_response_cache.sqlite").touch()
    for arm, source_root in (
        ("control", control_cache_dir),
        ("candidate", candidate_cache_dir),
    ):
        source = source_root / "openai_response_cache.sqlite"
        if source.exists():
            shutil.copy2(source, cache_root / f"{arm}_openai_response_cache.sqlite")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--agent", default=DEFAULT_MODEL)
    parser.add_argument("--user", default="GPT_4_o_2024_05_13")
    parser.add_argument("--generation-model", default=DEFAULT_MODEL)
    parser.add_argument("--recurrence-threshold", type=int, default=2)
    parser.add_argument(
        "--base-tool-policy",
        choices=KNOWN_POLICIES,
        default=UPSTREAM_POLICY,
    )
    parser.add_argument("--registry-dir", type=Path)
    parser.add_argument(
        "--prompt-cache-dir",
        type=Path,
        default=Path("outputs/prompt_cache"),
    )
    parser.add_argument(
        "-o",
        "--output-root",
        type=Path,
        default=Path("outputs/sage_protocol"),
    )
    parser.add_argument("--dashboard-port", type=int, default=5520)
    parser.add_argument("--no-dashboard-open", action="store_true")
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts"))
    parser.add_argument(
        "--openai-response-cache-dir",
        type=Path,
        default=Path("outputs/openai_response_cache"),
    )
    parser.add_argument(
        "--cache-mode",
        choices=("off", "read_write", "read_only", "write_only"),
        default=os.environ.get("CACHE_MODE", "read_write"),
    )
    parser.add_argument("--disable-openai-response-cache", action="store_true")
    parser.add_argument(
        "--parallel-arms",
        action="store_true",
        help="Run the matched control and SAGE arms concurrently in isolated processes.",
    )
    parser.add_argument(
        "--control-cache",
        choices=("off", "collect", "use-if-eligible", "refresh", "strict"),
        default=os.environ.get("CONTROL_CACHE", "use-if-eligible"),
        help="Control-arm baseline cache mode. Never applies to the SAGE/candidate arm.",
    )
    parser.add_argument(
        "--control-cache-root",
        type=Path,
        default=Path("artifacts/baselines/control_task_baselines"),
        help="Authoritative completed-control baseline cache root.",
    )
    parser.add_argument(
        "--freeze-toolsandbox-clock",
        action="store_true",
        default=os.environ.get("SAGE_TS_FREEZE_TOOLSANDBOX_CLOCK") == "1",
        help=(
            "Freeze ToolSandbox's current timestamp for the whole run. This keeps "
            "scenario setup and timestamp tools on a single benchmark clock during "
            "long runs."
        ),
    )
    parser.add_argument(
        "--generation",
        choices=("auto", "on", "off"),
        default="auto",
        help="Override candidate-side helper generation. Use off for frozen-registry validation.",
    )
    parser.add_argument(
        "--routing-evidence-mode",
        choices=("default", "auto", "disabled", "pinned"),
        default=os.environ.get("SAGE_ROUTING_EVIDENCE_MODE", "default"),
        help=(
            "Helper-contribution evidence mode for runtime routing. Final frozen "
            "runs resolve default to disabled; diagnostics/discovery resolve "
            "default to auto."
        ),
    )
    parser.add_argument(
        "--routing-evidence-path",
        type=Path,
        default=(
            Path(os.environ["SAGE_ROUTING_EVIDENCE_PATH"])
            if os.environ.get("SAGE_ROUTING_EVIDENCE_PATH")
            else None
        ),
        help="Pinned helper_contribution_summary.json used when routing evidence mode is pinned.",
    )
    parser.add_argument(
        "--diagnostic-force-allowed",
        action="store_true",
        help="Allow SAGE_DIAGNOSTIC_FORCE_* env vars for explicit diagnostic runs only.",
    )
    parser.add_argument(
        "--resume-run-root",
        type=Path,
        help="Seed each arm from a prior interrupted paired protocol run root.",
    )
    parser.add_argument(
        "--allow-empty-birth-preflight",
        action="store_true",
        help=(
            "Allow a generation-enabled run to proceed even when the cohort has "
            "no current expected birth path and no retained-helper fit."
        ),
    )
    parser.add_argument(
        "--allow-contaminated-preflight",
        action="store_true",
        help="Allow stock/location/weather/API-contaminated cohorts for explicit diagnostics.",
    )
    parser.add_argument(
        "--allow-low-quality-cohort",
        action="store_true",
        help=(
            "Allow a cohort that fails mechanical diversity/near-duplicate checks. "
            "Use only for explicit diagnostics, not broad claim runs."
        ),
    )
    args = parser.parse_args()

    if args.freeze_toolsandbox_clock and not os.environ.get(
        "TOOL_SANDBOX_FIXED_NOW_TIMESTAMP"
    ):
        os.environ["TOOL_SANDBOX_FIXED_NOW_TIMESTAMP"] = str(time.time())
    toolsandbox_fixed_now = os.environ.get("TOOL_SANDBOX_FIXED_NOW_TIMESTAMP")

    scenario_names = tuple(load_split_names(args.manifest, args.mode))
    manifest_type = _manifest_type(args.manifest)
    model_metadata = paired_model_metadata(
        agent_model=args.agent,
        generation_model=args.generation_model,
        user_model=args.user,
    )
    run_root = args.output_root / f"{args.mode}_{_timestamp()}"
    control_root = run_root / "control"
    candidate_root = run_root / "candidate"
    registry_dir = args.registry_dir or (run_root / "registry")
    registry_gate_snapshot = _snapshot_registry_for_gate(run_root, registry_dir)
    control_dir: Path | None = None
    candidate_dir: Path | None = None
    fresh_control_dir: Path | None = None
    control_resume_dir = _resume_arm_dir(args.resume_run_root, "control")
    candidate_resume_dir = _resume_arm_dir(args.resume_run_root, "candidate")
    generation_enabled = _generation_enabled_by_default(args.mode, manifest_type)
    if args.generation == "on":
        generation_enabled = True
    elif args.generation == "off":
        generation_enabled = False
    elif _is_frozen_transfer_mode(args.mode):
        generation_enabled = False
    frozen_final_run = _is_frozen_transfer_mode(args.mode) and not generation_enabled
    _preflight_openai_api_key(
        agent_model=args.agent,
        user_model=args.user,
        generation_model=args.generation_model,
        generation_enabled=generation_enabled,
    )
    if _is_frozen_transfer_mode(args.mode) and args.generation == "on":
        raise SystemExit(
            "Final/frozen protocol modes must not run with --generation on. "
            "Use a mechanism/discovery mode for tool birth diagnostics."
        )
    active_force_env = _active_diagnostic_force_env()
    if frozen_final_run and active_force_env and not args.diagnostic_force_allowed:
        raise SystemExit(
            "Diagnostic force-call environment is set during a frozen final run: "
            f"{', '.join(sorted(active_force_env))}. Unset these variables or pass "
            "--diagnostic-force-allowed only for explicit diagnostics."
        )
    routing_evidence_mode = _resolve_routing_evidence_mode(
        args.routing_evidence_mode,
        frozen_final_run=frozen_final_run,
    )
    if routing_evidence_mode == "pinned":
        if args.routing_evidence_path is None:
            raise SystemExit(
                "--routing-evidence-mode pinned requires --routing-evidence-path"
            )
        if not args.routing_evidence_path.exists():
            raise SystemExit(
                f"Pinned routing evidence path not found: {args.routing_evidence_path}"
            )
    _apply_routing_evidence_env(routing_evidence_mode, args.routing_evidence_path)
    control_cache = ControlBaselineCache(args.control_cache_root)
    control_cache_plan: dict[str, Any] | None = None
    control_cache_report: dict[str, Any] = {
        "mode": args.control_cache,
        "control_source": "fresh",
        "cached_control_tasks": 0,
        "fresh_control_tasks": len(scenario_names),
        "cached_scenarios": [],
        "fresh_scenarios": list(scenario_names),
        "cache_misses": {},
        "cache_manifest_hash": control_cache.manifest_hash(),
        "baseline_count_and_variance_per_cached_task": {},
        "estimated_token_time_savings": {
            "cached_tasks_skipped": 0,
            "cached_control_turns_avoided": 0,
            "token_savings": None,
            "wall_time_seconds_savings": None,
        },
        "confidence_intervals_account_for_cached_control_variance": False,
        "cohort_selection_influenced_by_cache": False,
    }
    if args.control_cache in {"use-if-eligible", "strict"}:
        control_cache_plan = plan_control_cache(
            cache=control_cache,
            scenario_names=scenario_names,
            agent=args.agent,
            user=args.user,
            base_tool_policy=args.base_tool_policy,
            manifest_path=args.manifest,
        )
        control_cache_report = build_control_cache_report(
            mode=args.control_cache,
            cache=control_cache,
            scenario_names=scenario_names,
            cached_scenarios=list(control_cache_plan["cached_scenarios"]),
            fresh_scenarios=list(control_cache_plan["fresh_scenarios"]),
            miss_reasons=dict(control_cache_plan["miss_reasons"]),
            lookups=dict(control_cache_plan["lookups"]),
        )
        if args.control_cache == "strict" and control_cache_plan["fresh_scenarios"]:
            raise SystemExit(
                "Control cache strict mode blocked this run: ineligible control "
                f"baselines for {len(control_cache_plan['fresh_scenarios'])} tasks."
            )
    effective_parallel_arms = args.parallel_arms and not (
        control_cache_plan is not None and control_cache_plan["cached_scenarios"]
    )
    cohort_preflight = _write_cohort_preflight(
        run_root,
        scenario_names=scenario_names,
        generation_enabled=generation_enabled,
        registry_dir=registry_dir,
    )
    initialize_campaign(root=args.artifact_root, phase=args.mode)
    append_event(
        "phase_started",
        {
            "mode": args.mode,
            "manifest_type": manifest_type,
            "run_root": str(run_root),
            "scenario_count": len(scenario_names),
            "cohort_preflight_report": str(run_root / "cohort_preflight_report.json"),
            "cohort_preflight_warnings": cohort_preflight.get("warnings", []),
            "cohort_quality_gate_status": cohort_preflight.get("quality_gate_status"),
            "control_cache_mode": args.control_cache,
            "control_cache_source": control_cache_report.get("control_source"),
            "control_cache_manifest_hash": control_cache_report.get(
                "cache_manifest_hash"
            ),
            "routing_evidence_mode": routing_evidence_mode,
            "routing_evidence_path": str(args.routing_evidence_path)
            if args.routing_evidence_path
            else None,
            "toolsandbox_clock_policy": "frozen"
            if args.freeze_toolsandbox_clock
            else "wall_clock",
            "toolsandbox_fixed_now_timestamp": toolsandbox_fixed_now,
        },
        root=args.artifact_root,
    )
    if cohort_preflight.get("should_block") and not args.allow_empty_birth_preflight:
        append_event(
            "gate_failed",
            {
                "mode": args.mode,
                "gate": "cohort_preflight",
                "run_root": str(run_root),
                "reason": "generation_enabled_without_birth_path_or_registry_fit",
                "cohort_preflight_report": str(
                    run_root / "cohort_preflight_report.json"
                ),
            },
            root=args.artifact_root,
        )
        raise SystemExit(
            "Cohort preflight blocked this generation-enabled run: no expected "
            "birth path, no retained-helper fit, and empty registry. See "
            f"{run_root / 'cohort_preflight_report.json'}"
        )
    contaminated = cohort_preflight.get("contaminated_external_service_scenarios", [])
    if contaminated and not args.allow_contaminated_preflight:
        append_event(
            "gate_failed",
            {
                "mode": args.mode,
                "gate": "cohort_preflight",
                "run_root": str(run_root),
                "reason": "external_service_contamination",
                "contaminated_external_service_scenarios": contaminated,
                "cohort_preflight_report": str(
                    run_root / "cohort_preflight_report.json"
                ),
            },
            root=args.artifact_root,
        )
        raise SystemExit(
            "Cohort preflight blocked this run because it contains external-service "
            "contamination. Pass --allow-contaminated-preflight only for explicit "
            f"diagnostics. See {run_root / 'cohort_preflight_report.json'}"
        )
    if (
        cohort_preflight.get("should_block_quality")
        and not args.allow_low_quality_cohort
    ):
        append_event(
            "gate_failed",
            {
                "mode": args.mode,
                "gate": "cohort_quality",
                "run_root": str(run_root),
                "reason": "low_quality_cohort",
                "quality_gate_failures": cohort_preflight.get(
                    "quality_gate_failures", []
                ),
                "cohort_preflight_report": str(
                    run_root / "cohort_preflight_report.json"
                ),
            },
            root=args.artifact_root,
        )
        raise SystemExit(
            "Cohort quality gate blocked this run. Use "
            "--allow-low-quality-cohort only for explicit diagnostics, not broad "
            f"claim runs. See {run_root / 'cohort_preflight_report.json'}"
        )
    append_event(
        "gate_passed",
        {
            "mode": args.mode,
            "gate": "cohort_preflight",
            "run_root": str(run_root),
            "warnings": cohort_preflight.get("warnings", []),
        },
        root=args.artifact_root,
    )
    record_run(
        {
            "run_root": str(run_root),
            "mode": args.mode,
            "manifest_type": manifest_type,
            "status": "running",
            "agent": args.agent,
            "model_metadata": model_metadata,
            "generation_enabled": generation_enabled,
            "base_tool_policy": args.base_tool_policy,
            "scenario_count": len(scenario_names),
            "cohort_preflight_report": str(run_root / "cohort_preflight_report.json"),
            "cohort_preflight_warnings": cohort_preflight.get("warnings", []),
            "cohort_quality_gate_status": cohort_preflight.get("quality_gate_status"),
            "routing_evidence_mode": routing_evidence_mode,
        },
        root=args.artifact_root,
    )
    dashboard_index = write_protocol_dashboard(
        run_root,
        mode=args.mode,
        status="running",
        phase="control",
        agent=args.agent,
        user=args.user,
        model_metadata=model_metadata,
        generation_enabled=generation_enabled,
        base_tool_policy=args.base_tool_policy,
        scenario_count=len(scenario_names),
        registry_dir=registry_dir,
        artifact_root=args.artifact_root,
    )
    # Dashboard visibility is part of the experiment surface. Keep it on by
    # default for every run; only the explicit CLI flag should suppress it.
    should_open_dashboard = not args.no_dashboard_open
    dashboard_url = dashboard_standard_url = dashboard_task_focus_url = (
        dashboard_task_compare_url
    ) = None
    if should_open_dashboard:
        dashboard_task_compare_url = open_dashboard(
            dashboard_index.with_name("task_compare.html"),
            port=args.dashboard_port,
        )
        dashboard_standard_url = make_dashboard_url(
            dashboard_index, port=args.dashboard_port
        )
        dashboard_url = dashboard_task_compare_url
        dashboard_task_focus_url = make_dashboard_url(
            dashboard_index.with_name("task_focus.html"),
            port=args.dashboard_port,
        )
        (run_root / "dashboard_urls.json").write_text(
            json.dumps(
                {
                    "dashboard_url": dashboard_task_compare_url,
                    "dashboard_standard_url": dashboard_standard_url,
                    "dashboard_task_focus_url": dashboard_task_focus_url,
                    "dashboard_task_compare_url": dashboard_task_compare_url,
                    "default_dashboard": "task_compare",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    response_cache_enabled = (
        not args.disable_openai_response_cache and args.cache_mode != "off"
    )
    control_cache_dir = args.openai_response_cache_dir
    candidate_cache_dir = args.openai_response_cache_dir
    if effective_parallel_arms:
        control_cache_dir = args.openai_response_cache_dir / "control"
        candidate_cache_dir = args.openai_response_cache_dir / "candidate"
    if response_cache_enabled and not effective_parallel_arms:
        install_openai_response_cache(
            args.openai_response_cache_dir,
            mode=args.cache_mode,
        )

    def refresh_dashboard(phase: str, status: str) -> None:
        write_protocol_dashboard(
            run_root,
            mode=args.mode,
            status=status,
            phase=phase,
            agent=args.agent,
            user=args.user,
            model_metadata=model_metadata,
            generation_enabled=generation_enabled,
            base_tool_policy=args.base_tool_policy,
            scenario_count=len(scenario_names),
            control_dir=control_dir,
            candidate_dir=candidate_dir,
            registry_dir=registry_dir,
            artifact_root=args.artifact_root,
        )

    def campaign_event(
        event: str,
        run_dir: Path,
        payload: dict[str, object],
    ) -> None:
        append_event(
            event,
            {
                "mode": args.mode,
                "run_root": str(run_root),
                "run_dir": str(run_dir),
                **payload,
            },
            root=args.artifact_root,
        )

    if effective_parallel_arms:
        append_event(
            "subtask_started",
            {
                "mode": args.mode,
                "subtask": "parallel_control_and_candidate",
                "run_root": str(run_root),
                "parallel_cache_policy": "per_arm",
            },
            root=args.artifact_root,
        )
        base_params: dict[str, Any] = {
            "mode": args.mode,
            "run_root": str(run_root),
            "artifact_root": str(args.artifact_root),
            "agent": args.agent,
            "user": args.user,
            "generation_model": args.generation_model,
            "recurrence_threshold": args.recurrence_threshold,
            "base_tool_policy": args.base_tool_policy,
            "registry_dir": str(registry_dir),
            "scenario_names": list(scenario_names),
            "manifest": str(args.manifest),
            "cache_mode": args.cache_mode,
            "response_cache_enabled": response_cache_enabled,
            "control_resume_dir": str(control_resume_dir)
            if control_resume_dir
            else None,
            "candidate_resume_dir": str(candidate_resume_dir)
            if candidate_resume_dir
            else None,
        }
        ctx = get_context("spawn")
        control_process = ctx.Process(
            target=_run_control_arm_worker,
            args=(
                {
                    **base_params,
                    "control_root": str(control_root),
                    "openai_response_cache_dir": str(control_cache_dir),
                },
            ),
            name="sage_ts_control_arm",
        )
        candidate_process = ctx.Process(
            target=_run_candidate_arm_worker,
            args=(
                {
                    **base_params,
                    "candidate_root": str(candidate_root),
                    "prompt_cache_dir": str(args.prompt_cache_dir),
                    "openai_response_cache_dir": str(candidate_cache_dir),
                    "generation_enabled": generation_enabled,
                },
            ),
            name="sage_ts_candidate_arm",
        )
        control_process.start()
        candidate_process.start()
        while control_process.is_alive() or candidate_process.is_alive():
            control_dir = _status_run_dir(run_root, "control", control_root)
            candidate_dir = _status_run_dir(run_root, "candidate", candidate_root)
            refresh_dashboard("parallel", "running")
            time.sleep(5)
        control_process.join()
        candidate_process.join()
        control_dir = _status_run_dir(run_root, "control", control_root)
        candidate_dir = _status_run_dir(run_root, "candidate", candidate_root)
        refresh_dashboard("parallel", "running")
        failed = {
            "control": control_process.exitcode,
            "candidate": candidate_process.exitcode,
        }
        if control_process.exitcode != 0 or candidate_process.exitcode != 0:
            append_event(
                "blocker_detected",
                {
                    "mode": args.mode,
                    "run_root": str(run_root),
                    "parallel_arms": True,
                    "exitcodes": failed,
                    "control_status": _read_arm_status(run_root, "control"),
                    "candidate_status": _read_arm_status(run_root, "candidate"),
                },
                root=args.artifact_root,
            )
            raise SystemExit(f"Parallel arm failure: {failed}")
        if control_dir is None or candidate_dir is None:
            raise SystemExit(
                "Parallel arms finished but run directories were not found"
            )
        if response_cache_enabled:
            _write_parallel_cache_artifacts(
                artifact_root=args.artifact_root,
                run_root=run_root,
                cache_mode=args.cache_mode,
                control_cache_dir=control_cache_dir,
                candidate_cache_dir=candidate_cache_dir,
                control_dir=control_dir,
                candidate_dir=candidate_dir,
            )
        append_event(
            "subtask_completed",
            {
                "mode": args.mode,
                "subtask": "parallel_control_and_candidate",
                "run_root": str(run_root),
                "control_dir": str(control_dir),
                "candidate_dir": str(candidate_dir),
                "control_cache_mode": args.control_cache,
                "control_cache_source": control_cache_report.get("control_source"),
            },
            root=args.artifact_root,
        )
        fresh_control_dir = control_dir
        if args.control_cache in {"collect", "use-if-eligible", "refresh"}:
            collected = control_cache.collect_run(
                run_dir=fresh_control_dir,
                config=ToolSandboxRunConfig(
                    agent=args.agent,
                    user=args.user,
                    scenario_names=scenario_names,
                    output_dir=control_root,
                    processes=1,
                    run_type=f"{args.mode}_control",
                    base_tool_policy=args.base_tool_policy,
                ),
                manifest_path=args.manifest,
            )
            control_cache_report["collected_control_records"] = len(collected)
    else:

        def control_progress(
            run_dir: Path,
            _rows: list[dict[str, object]],
            status: str,
            _scenario_count: int,
        ) -> None:
            nonlocal control_dir
            control_dir = run_dir
            refresh_dashboard("control", status)

        cached_rows_by_name: dict[str, dict[str, Any]] = {}
        fresh_control_scenarios = scenario_names
        if control_cache_plan is not None:
            cached_rows_by_name = {
                name: control_cache_plan["lookups"][name].row
                for name in control_cache_plan["cached_scenarios"]
                if control_cache_plan["lookups"][name].row is not None
            }
            fresh_control_scenarios = tuple(control_cache_plan["fresh_scenarios"])
        if fresh_control_scenarios:
            configure_response_cache_context(
                mode=args.mode,
                arm="control",
                agent=args.agent,
                user=args.user,
                base_tool_policy=args.base_tool_policy,
                scenario_names=fresh_control_scenarios,
                registry_dir=None,
                generation_enabled=False,
                generation_model=args.generation_model,
                recurrence_threshold=args.recurrence_threshold,
            )
            reset_openai_response_cache_metrics()
            fresh_control_dir = run_toolsandbox(
                ToolSandboxRunConfig(
                    agent=args.agent,
                    user=args.user,
                    scenario_names=fresh_control_scenarios,
                    output_dir=control_root,
                    processes=1,
                    run_type=f"{args.mode}_control",
                    base_tool_policy=args.base_tool_policy,
                    resume_from_dir=control_resume_dir
                    if fresh_control_scenarios == scenario_names
                    else None,
                ),
                progress_hook=control_progress,
                event_hook=campaign_event,
            )
            control_dir = fresh_control_dir
            if response_cache_enabled:
                write_openai_response_cache_metrics(
                    fresh_control_dir / "openai_response_cache_metrics.json"
                )
                write_cache_artifacts(args.artifact_root)
            if args.control_cache in {"collect", "use-if-eligible", "refresh"}:
                collected = control_cache.collect_run(
                    run_dir=fresh_control_dir,
                    config=ToolSandboxRunConfig(
                        agent=args.agent,
                        user=args.user,
                        scenario_names=fresh_control_scenarios,
                        output_dir=control_root,
                        processes=1,
                        run_type=f"{args.mode}_control",
                        base_tool_policy=args.base_tool_policy,
                    ),
                    manifest_path=args.manifest,
                )
                control_cache_report["collected_control_records"] = len(collected)
        if cached_rows_by_name:
            control_dir = write_synthetic_control_run(
                output_root=control_root,
                run_type=args.mode,
                agent=args.agent,
                user=args.user,
                scenario_names=scenario_names,
                cached_rows_by_name=cached_rows_by_name,
                fresh_run_dir=fresh_control_dir,
                cache_report=control_cache_report,
            )
            control_progress(control_dir, [], "complete", len(scenario_names))
        append_event(
            "phase_completed",
            {
                "mode": args.mode,
                "phase": "control",
                "run_dir": str(control_dir),
                "control_cache_mode": args.control_cache,
                "control_cache_source": control_cache_report.get("control_source"),
                "cached_control_tasks": control_cache_report.get(
                    "cached_control_tasks"
                ),
                "fresh_control_tasks": control_cache_report.get("fresh_control_tasks"),
            },
            root=args.artifact_root,
        )
        refresh_dashboard("candidate", "running")

        prompt_cache = PromptCache(args.prompt_cache_dir)
        generator = (
            ToolGenerator(
                completer=OpenAIChatAdapter(model=args.generation_model),
                cache=prompt_cache,
            )
            if generation_enabled
            else None
        )

        def candidate_progress(
            run_dir: Path,
            _rows: list[dict[str, object]],
            status: str,
            _scenario_count: int,
        ) -> None:
            nonlocal candidate_dir
            candidate_dir = run_dir
            refresh_dashboard("candidate", status)

        configure_response_cache_context(
            mode=args.mode,
            arm="candidate",
            agent=args.agent,
            user=args.user,
            base_tool_policy=args.base_tool_policy,
            scenario_names=scenario_names,
            registry_dir=registry_dir,
            generation_enabled=generation_enabled,
            generation_model=args.generation_model,
            recurrence_threshold=args.recurrence_threshold,
        )
        reset_openai_response_cache_metrics()
        candidate_dir = run_sage_with_registry(
            SageRunConfig(
                agent=args.agent,
                user=args.user,
                scenario_names=scenario_names,
                output_dir=candidate_root,
                registry_dir=registry_dir,
                run_type=f"{args.mode}_candidate",
                recurrence_threshold=args.recurrence_threshold,
                base_tool_policy=args.base_tool_policy,
                resume_from_dir=candidate_resume_dir,
                manifest_path=args.manifest,
            ),
            generator=generator,
            progress_hook=candidate_progress,
            event_hook=campaign_event,
        )
        (candidate_dir / "prompt_cache_metrics.json").write_text(
            json.dumps(prompt_cache.metrics(), indent=2) + "\n",
            encoding="utf-8",
        )
        if response_cache_enabled:
            write_openai_response_cache_metrics(
                candidate_dir / "openai_response_cache_metrics.json"
            )
            write_cache_artifacts(args.artifact_root)
    control_cache_report_path = run_root / "control_cache_report.json"
    control_cache_report_path.write_text(
        json.dumps(control_cache_report, indent=2) + "\n", encoding="utf-8"
    )
    if control_dir is not None:
        (control_dir / "control_cache_report.json").write_text(
            json.dumps(control_cache_report, indent=2) + "\n", encoding="utf-8"
        )
    candidate_live_summary = _read_metrics(candidate_dir / "live_result_summary.json")
    candidate_stopped_early = (
        str(candidate_live_summary.get("status", "")).strip().lower() == "stopped_early"
    )
    comparison = compare_runs(
        control_dir,
        candidate_dir,
        registry_dir=registry_dir,
        require_complete_match=not candidate_stopped_early,
    )
    comparison["candidate_stopped_early"] = candidate_stopped_early
    comparison["control_cache"] = control_cache_report
    comparison["model_metadata"] = model_metadata
    comparison["comparison_model_key"] = model_metadata["comparison_key"]
    comparison["route_mismatch_qualified"] = _route_mismatch_qualified(comparison)
    protocol_gate_passed, protocol_gate_reasons = _protocol_gate_decision(
        comparison,
        scenario_count=len(scenario_names),
    )
    comparison["protocol_gate_passed"] = protocol_gate_passed
    comparison["protocol_gate_reasons"] = protocol_gate_reasons
    comparison_path = run_root / "paired_comparison.json"
    comparison_path.write_text(
        json.dumps(comparison, indent=2) + "\n", encoding="utf-8"
    )
    helper_contribution_path = run_root / "helper_contribution_summary.json"
    helper_contribution = write_helper_contribution_summary(
        control_dir,
        candidate_dir,
        helper_contribution_path,
        registry_dir=registry_dir,
    )
    helper_artifact_dir = args.artifact_root / "summaries" / run_root.name
    helper_artifact_dir.mkdir(parents=True, exist_ok=True)
    helper_contribution_artifact_path = (
        helper_artifact_dir / "helper_contribution_summary.json"
    )
    shutil.copy2(helper_contribution_path, helper_contribution_artifact_path)
    registry_gate_restore: dict[str, Any] | None = None
    if not protocol_gate_passed:
        registry_gate_restore = _restore_registry_after_failed_gate(
            run_root=run_root,
            registry_dir=registry_dir,
            snapshot=registry_gate_snapshot,
        )
    gate_event = "gate_passed" if protocol_gate_passed else "gate_failed"
    append_event(
        gate_event,
        {
            "mode": args.mode,
            "run_root": str(run_root),
            "mean_similarity_delta": comparison.get("mean_similarity_delta"),
            "mean_outcome_similarity_delta": comparison.get(
                "mean_outcome_similarity_delta"
            ),
            "gain_count": comparison.get("gain_count"),
            "regression_count": comparison.get("regression_count"),
            "outcome_gain_count": comparison.get("outcome_gain_count"),
            "outcome_regression_count": comparison.get("outcome_regression_count"),
            "route_mismatch_qualified": comparison.get("route_mismatch_qualified"),
            "protocol_gate_reasons": protocol_gate_reasons,
            "registry_gate_restore": registry_gate_restore,
        },
        root=args.artifact_root,
    )
    append_event(
        "phase_completed",
        {"mode": args.mode, "phase": "comparison", "run_root": str(run_root)},
        root=args.artifact_root,
    )
    snapshot_registry(
        registry_dir, name=f"{args.mode}_{run_root.name}", root=args.artifact_root
    )
    if args.mode in {"viability_12", "mechanism_12", "mechanism_40", "mechanism_60"}:
        update_task(
            "reproduce_clean_recency_birth", "completed", root=args.artifact_root
        )
    elif args.mode in {"transfer_40", "transfer_60", "transfer_100"}:
        update_task("frozen_registry_transfer", "completed", root=args.artifact_root)
    refresh_dashboard("comparison", "complete")
    manifest = {
        "mode": args.mode,
        "manifest_type": manifest_type,
        "agent": args.agent,
        "user": args.user,
        "generation_model": args.generation_model,
        "model_metadata": model_metadata,
        "comparison_model_key": model_metadata["comparison_key"],
        "generation_enabled": generation_enabled,
        "base_tool_policy": args.base_tool_policy,
        "scenario_count": len(scenario_names),
        "control_dir": str(control_dir),
        "candidate_dir": str(candidate_dir),
        "registry_dir": str(registry_dir),
        "registry_gate_snapshot": registry_gate_snapshot,
        "registry_gate_restore": registry_gate_restore,
        "registry_manifest_digest_after_run": _digest_file(
            registry_dir / "registry_manifest.json"
        ),
        "cohort_preflight_report": str(run_root / "cohort_preflight_report.json"),
        "cohort_preflight_warnings": cohort_preflight.get("warnings", []),
        "cohort_quality_gate_status": cohort_preflight.get("quality_gate_status"),
        "cohort_quality_gate_failures": cohort_preflight.get(
            "quality_gate_failures", []
        ),
        "resume_run_root": str(args.resume_run_root) if args.resume_run_root else None,
        "control_resume_dir": str(control_resume_dir) if control_resume_dir else None,
        "candidate_resume_dir": str(candidate_resume_dir)
        if candidate_resume_dir
        else None,
        "comparison_path": str(comparison_path),
        "control_cache_mode": args.control_cache,
        "control_source": control_cache_report.get("control_source"),
        "cached_control_tasks": control_cache_report.get("cached_control_tasks"),
        "fresh_control_tasks": control_cache_report.get("fresh_control_tasks"),
        "control_cache_report_path": str(control_cache_report_path),
        "control_cache_manifest_hash": control_cache_report.get("cache_manifest_hash"),
        "helper_contribution_summary_path": str(helper_contribution_path),
        "helper_contribution_artifact_path": str(helper_contribution_artifact_path),
        "routing_evidence_mode": routing_evidence_mode,
        "routing_evidence_path": str(args.routing_evidence_path)
        if args.routing_evidence_path
        else None,
        "routing_evidence_path_digest": _digest_file(args.routing_evidence_path)
        if args.routing_evidence_path
        else None,
        "diagnostic_force_allowed": args.diagnostic_force_allowed,
        "active_diagnostic_force_env": sorted(active_force_env),
        "toolsandbox_clock_policy": "frozen"
        if args.freeze_toolsandbox_clock
        else "wall_clock",
        "toolsandbox_fixed_now_timestamp": toolsandbox_fixed_now,
        "run_affecting_sage_env": _redacted_run_affecting_sage_env(),
        "accepted_but_uncalled_tools": helper_contribution.get(
            "accepted_but_uncalled_tools", []
        ),
        "dashboard_path": str(dashboard_index),
        "dashboard_url": dashboard_url,
        "dashboard_standard_url": dashboard_standard_url,
        "dashboard_task_focus_url": dashboard_task_focus_url,
        "dashboard_task_compare_url": dashboard_task_compare_url,
        "parallel_arms": args.parallel_arms,
        "parallel_cache_policy": "per_arm" if args.parallel_arms else "shared_process",
        "openai_response_cache_enabled": response_cache_enabled,
        "openai_response_cache_mode": args.cache_mode,
        "openai_response_cache_dir": str(args.openai_response_cache_dir),
        "control_openai_response_cache_dir": str(control_cache_dir),
        "candidate_openai_response_cache_dir": str(candidate_cache_dir),
        "mean_similarity_delta": comparison.get("mean_similarity_delta"),
        "mean_outcome_similarity_delta": comparison.get(
            "mean_outcome_similarity_delta"
        ),
        "route_mismatch_qualified": comparison.get("route_mismatch_qualified"),
        "protocol_gate_passed": protocol_gate_passed,
        "protocol_gate_reasons": protocol_gate_reasons,
    }
    manifest_path = run_root / "protocol_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    record_run(
        {
            "run_root": str(run_root),
            "mode": args.mode,
            "manifest_type": manifest_type,
            "status": "complete",
            "agent": args.agent,
            "model_metadata": model_metadata,
            "comparison_model_key": model_metadata["comparison_key"],
            "generation_enabled": generation_enabled,
            "base_tool_policy": args.base_tool_policy,
            "scenario_count": len(scenario_names),
            "control_dir": str(control_dir),
            "candidate_dir": str(candidate_dir),
            "registry_dir": str(registry_dir),
            "registry_gate_snapshot": registry_gate_snapshot,
            "registry_gate_restore": registry_gate_restore,
            "registry_manifest_digest_after_run": _digest_file(
                registry_dir / "registry_manifest.json"
            ),
            "cohort_preflight_report": str(run_root / "cohort_preflight_report.json"),
            "cohort_preflight_warnings": cohort_preflight.get("warnings", []),
            "cohort_quality_gate_status": cohort_preflight.get("quality_gate_status"),
            "cohort_quality_gate_failures": cohort_preflight.get(
                "quality_gate_failures", []
            ),
            "comparison_path": str(comparison_path),
            "control_cache_mode": args.control_cache,
            "control_source": control_cache_report.get("control_source"),
            "cached_control_tasks": control_cache_report.get("cached_control_tasks"),
            "fresh_control_tasks": control_cache_report.get("fresh_control_tasks"),
            "control_cache_report_path": str(control_cache_report_path),
            "control_cache_manifest_hash": control_cache_report.get(
                "cache_manifest_hash"
            ),
            "helper_contribution_summary_path": str(helper_contribution_path),
            "helper_contribution_artifact_path": str(helper_contribution_artifact_path),
            "routing_evidence_mode": routing_evidence_mode,
            "routing_evidence_path": str(args.routing_evidence_path)
            if args.routing_evidence_path
            else None,
            "accepted_but_uncalled_tools": helper_contribution.get(
                "accepted_but_uncalled_tools", []
            ),
            "dashboard_path": str(dashboard_index),
            "dashboard_url": dashboard_url,
            "dashboard_standard_url": dashboard_standard_url,
            "dashboard_task_focus_url": dashboard_task_focus_url,
            "dashboard_task_compare_url": dashboard_task_compare_url,
            "parallel_arms": args.parallel_arms,
            "mean_similarity_delta": comparison.get("mean_similarity_delta"),
            "mean_outcome_similarity_delta": comparison.get(
                "mean_outcome_similarity_delta"
            ),
            "protocol_gate_passed": protocol_gate_passed,
            "protocol_gate_reasons": protocol_gate_reasons,
        },
        root=args.artifact_root,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
