#!/usr/bin/env python3
"""Run and verify matched SAGE auto-selection beside a fresh non-learning control."""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import math
import os
import subprocess
import time
import traceback
from datetime import datetime, timezone
from multiprocessing import get_context
from pathlib import Path
from typing import Any, Callable

from sage_ts.dashboard.exporters import open_dashboard, write_protocol_dashboard
from sage_ts.dashboard.server import DASHBOARD_SERVER_PROTOCOL
from sage_ts.evaluation.outcome_score import outcome_evaluator_manifest
from scripts.research.actor_selection_comparison import (
    ActorSelectionVerificationError,
    verify_matched_actor_selection_experiment,
)
from scripts.run_sage_protocol import (
    _parallel_arm_execution_record,
    _run_candidate_arm_worker,
    _run_control_arm_worker,
    _status_run_dir,
    _stop_parallel_process,
    _validate_uncached_result_rows,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLICATION_ENVIRONMENT_LOCK = REPO_ROOT / "requirements-publication-lock.txt"
STAGE_PINS: dict[str, dict[str, object]] = {
    "pilot": {
        "scenario_count": 30,
        "benchmark_sha256": (
            "378b681dbe86e0f27c911c485c6257075c9fe377f7c993f8083cba35a2fdda90"
        ),
        "scenario_order_sha256": (
            "ce19bea3a0ff404487c195dd68a9f07f3e8705a9ed59364a534b13385da09d5e"
        ),
    },
    "full": {
        "scenario_count": 1032,
        "benchmark_sha256": (
            "21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec"
        ),
        "scenario_order_sha256": (
            "fec899dde5b3ce1879157c16eff120e24c1791a2ab1df53712677bcacb250176"
        ),
    },
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read JSON artifact: {path}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected a JSON object: {path}")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _verified_environment() -> dict[str, object]:
    try:
        from scripts.verify_publication_environment import verify_environment
    except ModuleNotFoundError:
        from verify_publication_environment import verify_environment

    try:
        report = verify_environment(PUBLICATION_ENVIRONMENT_LOCK, repo_root=REPO_ROOT)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ActorSelectionVerificationError(
            f"Publication environment verification failed: {exc}"
        ) from exc
    if report.get("status") != "pass":
        raise ActorSelectionVerificationError(
            "Publication environment verifier did not return pass status."
        )
    return report


def _verify_policy_donor(run_root: Path, *, stage: str) -> dict[str, object]:
    try:
        from scripts.verify_publication_run import verify_pinned_run
    except ModuleNotFoundError:
        from verify_publication_run import verify_pinned_run

    try:
        result = verify_pinned_run(
            run_root,
            cohort=stage,
            expect_reflection="same-run-fresh",
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise ActorSelectionVerificationError(
            f"Policy donor failed strict publication verification: {exc}"
        ) from exc
    if Path(str(result.get("run_root") or "")).resolve() != run_root:
        raise ActorSelectionVerificationError(
            "Strict publication verification selected a different policy donor."
        )
    return result


def _required_evidence_hashes(paths: dict[str, Path]) -> dict[str, dict[str, object]]:
    evidence: dict[str, dict[str, object]] = {}
    for label, path in sorted(paths.items()):
        resolved = path.resolve()
        if not resolved.is_file():
            raise ActorSelectionVerificationError(
                f"Required experiment evidence is missing: {label}={resolved}"
            )
        evidence[label] = {
            "path": str(resolved),
            "sha256": _sha256(resolved),
            "size_bytes": resolved.stat().st_size,
        }
    return evidence


def _verify_recorded_evidence(payload: dict[str, Any]) -> None:
    raw_evidence = payload.get("evidence_hashes")
    if not isinstance(raw_evidence, dict) or not raw_evidence:
        raise SystemExit("Pilot evidence has no sealed artifact hashes.")
    for label, raw_record in raw_evidence.items():
        if not isinstance(raw_record, dict):
            raise SystemExit(f"Pilot evidence record is malformed: {label}")
        path = Path(str(raw_record.get("path") or "")).resolve()
        if (
            not path.is_file()
            or raw_record.get("sha256") != _sha256(path)
            or raw_record.get("size_bytes") != path.stat().st_size
        ):
            raise SystemExit(f"Pilot evidence artifact has drifted: {label}")


def _recorded_path(raw: object, *, label: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise SystemExit(f"Policy manifest does not record {label}.")
    path = Path(raw)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def _git_output(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=REPO_ROOT, text=True, stderr=subprocess.STDOUT
        ).strip()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Git identity check failed: {exc.output.strip()}") from exc


def _assert_clean_matching_source(protocol: dict[str, Any]) -> dict[str, str]:
    if _git_output("status", "--porcelain", "--untracked-files=all"):
        raise SystemExit(
            "Auto replay requires a clean tracked worktree matching the policy donor."
        )
    commit = _git_output("rev-parse", "HEAD")
    tree = _git_output("rev-parse", "HEAD^{tree}")
    provenance = protocol.get("publication_provenance")
    if not isinstance(provenance, dict):
        raise SystemExit("Policy donor has no strict publication provenance.")
    if (
        provenance.get("git_clean") is not True
        or provenance.get("git_commit") != commit
        or provenance.get("git_tree") != tree
    ):
        raise SystemExit("Current source identity does not match the policy donor.")
    return {"git_commit": commit, "git_tree": tree}


def _assert_empty_target(path: Path, *, label: str) -> None:
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise SystemExit(f"{label} must be absent or empty: {path}")


def _write_status(
    path: Path,
    *,
    status: str,
    auto_run_dir: Path | None = None,
    error: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "arm": "sage_auto_selection",
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if auto_run_dir is not None:
        payload["run_dir"] = str(auto_run_dir)
    if error is not None:
        payload["error"] = error
    _write_json(path, payload)


def _outcome_only_pair_summary(
    control_rows: dict[str, dict[str, Any]],
    auto_rows: dict[str, dict[str, Any]],
    scenario_names: tuple[str, ...],
) -> dict[str, object]:
    if not scenario_names:
        raise RuntimeError("Parallel auto-selection pair has an empty task cohort.")
    control_values: list[float] = []
    auto_values: list[float] = []
    for name in scenario_names:
        raw_control = control_rows[name].get("outcome_similarity")
        raw_auto = auto_rows[name].get("outcome_similarity")
        if (
            isinstance(raw_control, bool)
            or not isinstance(raw_control, (int, float))
            or not math.isfinite(float(raw_control))
            or isinstance(raw_auto, bool)
            or not isinstance(raw_auto, (int, float))
            or not math.isfinite(float(raw_auto))
            or not 0.0 <= float(raw_control) <= 1.0
            or not 0.0 <= float(raw_auto) <= 1.0
        ):
            raise RuntimeError(
                f"Parallel auto-selection pair has no outcome value for {name!r}."
            )
        control_values.append(float(raw_control))
        auto_values.append(float(raw_auto))
    count = len(scenario_names)
    return {
        "schema_version": 1,
        "publication_performance_endpoint": "outcome_task_completion_similarity",
        "scenario_count": count,
        "outcome_evaluated_count": count,
        "control_exact_outcome_successes": sum(
            value == 1.0 for value in control_values
        ),
        "auto_exact_outcome_successes": sum(value == 1.0 for value in auto_values),
        "control_mean_outcome_similarity": sum(control_values) / count,
        "auto_mean_outcome_similarity": sum(auto_values) / count,
        "mean_outcome_similarity_delta": (
            sum(auto_values) / count - sum(control_values) / count
        ),
        "auto_outcome_gain_count": sum(
            auto > control for control, auto in zip(control_values, auto_values)
        ),
        "auto_outcome_regression_count": sum(
            auto < control for control, auto in zip(control_values, auto_values)
        ),
        "outcome_tie_count": sum(
            auto == control for control, auto in zip(control_values, auto_values)
        ),
    }


def _run_parallel_auto_pair(
    *,
    pair_root: Path,
    pair_artifact_root: Path,
    control_root: Path,
    auto_root: Path,
    auto_registry: Path,
    mode: str,
    agent: str,
    user: str,
    generation_model: str,
    recurrence_threshold: int,
    base_tool_policy: str,
    scenario_names: tuple[str, ...],
    benchmark_manifest: Path,
    authority_root: Path,
    progress_hook: Callable[[Path | None, Path | None, str], None],
) -> tuple[Path, Path, dict[str, Any], dict[str, object]]:
    """Run fresh non-learning control and matched-inventory auto SAGE together."""

    if not pair_root.is_dir():
        raise RuntimeError(
            "Auto-selection pair root must be initialized by its dashboard preflight."
        )
    pair_artifact_root.mkdir(parents=True, exist_ok=False)
    base_params: dict[str, Any] = {
        "mode": mode,
        "run_root": str(pair_root),
        "artifact_root": str(pair_artifact_root),
        "agent": agent,
        "user": user,
        "generation_model": generation_model,
        "recurrence_threshold": recurrence_threshold,
        "base_tool_policy": base_tool_policy,
        "registry_dir": str(auto_registry),
        "scenario_names": list(scenario_names),
        "manifest": str(benchmark_manifest),
        "control_resume_dir": None,
        "candidate_resume_dir": None,
        "resume_completed_limit": None,
        "actor_selection_mode": "auto",
        "candidate_arm_name": "sage_auto_selection",
        "inventory_authority_capture_dir": None,
        "inventory_authority_replay_dir": str(authority_root),
        "require_fresh_control": True,
        # Inventory replay has generation and online reflection disabled. The
        # fresh control is nevertheless required as the concurrent peer for
        # every experimental SAGE execution.
        "reflection_control_channel": None,
    }
    ctx = get_context("spawn")
    control_process = ctx.Process(
        target=_run_control_arm_worker,
        args=({**base_params, "control_root": str(control_root)},),
        name="sage_ts_auto_selection_control_arm",
    )
    auto_process = ctx.Process(
        target=_run_candidate_arm_worker,
        args=(
            {
                **base_params,
                "candidate_root": str(auto_root),
                "generation_enabled": False,
            },
        ),
        name="sage_ts_auto_selection_arm",
    )
    processes = {"control": control_process, "candidate": auto_process}
    started = {arm: False for arm in processes}
    failed_arm: str | None = None
    try:
        control_process.start()
        started["control"] = True
        auto_process.start()
        started["candidate"] = True
        while control_process.is_alive() or auto_process.is_alive():
            for arm, process in processes.items():
                if process.exitcode not in (None, 0):
                    failed_arm = arm
                    break
            if failed_arm is not None:
                break
            progress_hook(
                _status_run_dir(pair_root, "control", control_root),
                _status_run_dir(pair_root, "candidate", auto_root),
                "running",
            )
            time.sleep(5)
        if failed_arm is not None:
            peer = "candidate" if failed_arm == "control" else "control"
            _stop_parallel_process(processes[peer])
            raise RuntimeError(
                f"{failed_arm} arm exited with code {processes[failed_arm].exitcode}."
            )
        control_process.join()
        auto_process.join()
        if control_process.exitcode != 0 or auto_process.exitcode != 0:
            raise RuntimeError(
                "Fresh control or auto-selection SAGE exited unsuccessfully."
            )
        control_dir = _status_run_dir(pair_root, "control", control_root)
        auto_dir = _status_run_dir(pair_root, "candidate", auto_root)
        if control_dir is None or auto_dir is None:
            raise RuntimeError(
                "Parallel auto-selection pair finished without both run directories."
            )
        parallel_execution = _parallel_arm_execution_record(pair_root)
        control_rows = _validate_uncached_result_rows(
            control_dir,
            expected_scenarios=scenario_names,
            arm="auto-selection fresh control",
            require_complete=True,
        )
        auto_rows = _validate_uncached_result_rows(
            auto_dir,
            expected_scenarios=scenario_names,
            arm="sage_auto_selection",
            require_complete=True,
        )
        if tuple(control_rows) != scenario_names or tuple(auto_rows) != scenario_names:
            raise RuntimeError(
                "Parallel auto-selection pair did not preserve exact task order."
            )
        progress_hook(control_dir, auto_dir, "complete")
        return (
            control_dir,
            auto_dir,
            parallel_execution,
            _outcome_only_pair_summary(control_rows, auto_rows, scenario_names),
        )
    except BaseException:
        for arm, process in processes.items():
            if started[arm]:
                _stop_parallel_process(process)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--policy-run-root",
        required=True,
        type=Path,
        help="Completed protocol root containing control + policy donor arms.",
    )
    parser.add_argument(
        "--stage",
        choices=("pilot", "full"),
        required=True,
        help="Experiment stage recorded in the comparison manifest.",
    )
    parser.add_argument(
        "--auto-registry-dir",
        type=Path,
        help="Fresh mutable registry used while replaying donor state.",
    )
    parser.add_argument(
        "--dashboard-port",
        type=int,
        default=5520,
        help="Port for the externally opened live control-versus-auto dashboard.",
    )
    parser.add_argument(
        "--pilot-evidence",
        type=Path,
        default=(
            Path(os.environ["SAGE_AUTO_SELECTION_PILOT_EVIDENCE"])
            if os.environ.get("SAGE_AUTO_SELECTION_PILOT_EVIDENCE")
            else None
        ),
        help=(
            "Completed, sealed pilot experiment manifest. Required before a full "
            "matched comparison."
        ),
    )
    args = parser.parse_args()

    run_root = args.policy_run_root.resolve()
    if not run_root.is_dir():
        raise SystemExit(f"Policy run root is missing: {run_root}")
    current_outcome_evaluator = outcome_evaluator_manifest()
    status_path = run_root / "sage_auto_selection_arm_status.json"
    report_path = run_root / "actor_selection_outcome_comparison.json"
    experiment_manifest_path = run_root / "actor_selection_experiment_manifest.json"
    for path in (status_path, report_path, experiment_manifest_path):
        if path.exists():
            raise SystemExit(
                f"Auto-selection experiment artifact already exists: {path}"
            )
    lifecycle = {"finalized": False}
    _write_status(status_path, status="preflight")
    _write_json(
        experiment_manifest_path,
        {
            "schema_version": 2,
            "experiment": "sage_auto_selection",
            "stage": args.stage,
            "status": "preflight",
            "policy_run_root": str(run_root),
            "outcome_evaluator": current_outcome_evaluator,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    def mark_incomplete_failure() -> None:
        if lifecycle["finalized"]:
            return
        try:
            current = _read_json(experiment_manifest_path)
            current["status"] = "failed"
            current["updated_at"] = datetime.now(timezone.utc).isoformat()
            current["error"] = "Auto-selection replay exited before final verification."
            _write_json(experiment_manifest_path, current)
            _write_status(
                status_path,
                status="failed",
                error="Auto-selection replay exited before final verification.",
            )
        except BaseException:
            return

    atexit.register(mark_incomplete_failure)
    protocol_path = run_root / "protocol_manifest.json"
    protocol = _read_json(protocol_path)
    if protocol.get("outcome_evaluator") != current_outcome_evaluator:
        raise SystemExit(
            "Policy donor does not use the current outcome evaluator identity."
        )
    if (
        protocol.get("candidate_actor_selection_mode") != "policy"
        or protocol.get("inventory_authority_mode") != "capture"
        or protocol.get("control_cache_mode") != "off"
        or protocol.get("openai_response_cache_enabled") is not False
        or protocol.get("sage_task_cache_enabled") is not False
        or int(protocol.get("cached_control_tasks") or 0) != 0
    ):
        raise SystemExit(
            "Policy donor is not a cache-free policy-selection authority capture."
        )
    source_identity = _assert_clean_matching_source(protocol)
    if args.stage == "full":
        if args.pilot_evidence is None:
            raise SystemExit(
                "Full replay requires --pilot-evidence (or "
                "SAGE_AUTO_SELECTION_PILOT_EVIDENCE)."
            )
        pilot_evidence = _read_json(args.pilot_evidence.resolve())
        if (
            pilot_evidence.get("schema_version") != 2
            or pilot_evidence.get("experiment") != "sage_auto_selection"
            or pilot_evidence.get("stage") != "pilot"
            or pilot_evidence.get("status") != "complete"
            or pilot_evidence.get("mechanism_counts_are_performance_gates") is not False
            or pilot_evidence.get("integrity_gate_passed") is not True
            or pilot_evidence.get("integrity_gate_reasons") != []
            or pilot_evidence.get("outcome_evidence_complete") is not True
            or pilot_evidence.get("performance_gate_applied") is not False
            or pilot_evidence.get("performance_gate_reason")
            != "no_predeclared_selector_performance_threshold"
            or pilot_evidence.get("experiment_passed") is not True
            or pilot_evidence.get("stability_gate_passed") is not True
            or pilot_evidence.get("scenario_count")
            != STAGE_PINS["pilot"]["scenario_count"]
            or pilot_evidence.get("benchmark_manifest_sha256")
            != STAGE_PINS["pilot"]["benchmark_sha256"]
            or pilot_evidence.get("scenario_order_sha256")
            != STAGE_PINS["pilot"]["scenario_order_sha256"]
            or pilot_evidence.get("source_identity") != source_identity
            or pilot_evidence.get("outcome_evaluator") != current_outcome_evaluator
            or pilot_evidence.get("auto_parallel_arms") is not True
            or pilot_evidence.get("auto_control_cache_mode") != "off"
            or pilot_evidence.get("auto_control_source") != "fresh"
            or pilot_evidence.get("auto_cached_control_tasks") != 0
            or pilot_evidence.get("auto_fresh_control_tasks")
            != STAGE_PINS["pilot"]["scenario_count"]
            or pilot_evidence.get("auto_control_cache_accessed") is not False
            or pilot_evidence.get("auto_control_delivery") != "not_connected"
            or pilot_evidence.get("auto_control_output_influences_inventory")
            is not False
            or pilot_evidence.get("auto_control_output_influences_execution")
            is not False
        ):
            raise SystemExit(
                "Full replay pilot evidence is not valid or source-matched."
            )
        _verify_recorded_evidence(pilot_evidence)
    protocol_sha256 = _sha256(protocol_path)
    policy_dir = _recorded_path(protocol.get("candidate_dir"), label="candidate_dir")
    authority_path = _recorded_path(
        protocol.get("inventory_authority_manifest_path"),
        label="inventory_authority_manifest_path",
    )
    authority = _read_json(authority_path)
    authority_sha256 = _sha256(authority_path)
    scenario_names_raw = authority.get("scenario_names")
    if not isinstance(scenario_names_raw, list) or not all(
        isinstance(name, str) for name in scenario_names_raw
    ):
        raise SystemExit("Inventory authority has no exact scenario order.")
    scenario_names = tuple(str(name) for name in scenario_names_raw)
    stage_pin = STAGE_PINS[args.stage]
    expected_stage_count = int(stage_pin["scenario_count"])
    scenario_order_sha256 = hashlib.sha256(
        ("\n".join(scenario_names) + "\n").encode("utf-8")
    ).hexdigest()
    if len(scenario_names) != expected_stage_count:
        raise SystemExit(
            f"{args.stage.title()} replay requires the exact sealed "
            f"{expected_stage_count}-task cohort."
        )
    if scenario_order_sha256 != stage_pin["scenario_order_sha256"]:
        raise SystemExit(
            f"{args.stage.title()} replay scenario order does not match its pin."
        )
    if (
        authority.get("complete") is not True
        or authority.get("source_actor_selection_mode") != "policy"
        or authority.get("task_count") != len(scenario_names)
        or protocol.get("scenario_count") != len(scenario_names)
        or protocol.get("inventory_authority_manifest_sha256")
        != _sha256(authority_path)
    ):
        raise SystemExit("Policy inventory authority is incomplete or has drifted.")

    benchmark_manifest = _recorded_path(
        protocol.get("benchmark_manifest_path"), label="benchmark_manifest_path"
    )
    benchmark_manifest_sha256 = _sha256(benchmark_manifest)
    if (
        benchmark_manifest_sha256 != stage_pin["benchmark_sha256"]
        or protocol.get("benchmark_manifest_sha256") != benchmark_manifest_sha256
        or protocol.get("scenario_order_sha256") != scenario_order_sha256
    ):
        raise SystemExit("Benchmark manifest bytes have changed since policy capture.")
    if (
        protocol.get("mode") != "online_build_full"
        or protocol.get("generation_enabled") is not True
        or protocol.get("candidate_generation_enabled") is not True
        or protocol.get("sage_policy") != "self-evolving-praxis"
        or int(protocol.get("scenario_count") or 0) != expected_stage_count
    ):
        raise SystemExit("Policy donor is not a completed online publication arm.")
    if policy_dir.parent.resolve() != (run_root / "candidate").resolve() or not (
        _is_relative_to(policy_dir, run_root)
    ):
        raise SystemExit("Policy candidate directory escapes its protocol run root.")
    source_run_config_path = policy_dir.parent / "sage_ts_run_manifest.json"
    source_run_config = _read_json(source_run_config_path)
    if source_run_config.get(
        "actor_selection_mode"
    ) != "policy" or source_run_config.get("scenario_names") != list(scenario_names):
        raise SystemExit("Policy run configuration does not match its authority.")

    agent = str(source_run_config.get("agent") or "")
    user = str(source_run_config.get("user") or "")
    generation_model = str(protocol.get("generation_model") or "")
    if not agent or not user or not generation_model:
        raise SystemExit("Policy donor does not record all model settings.")
    policy_publication_verification = _verify_policy_donor(
        run_root,
        stage=args.stage,
    )
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise SystemExit("OPENAI_API_KEY is required for the live auto-selection arm.")
    os.environ["SAGE_TS_MODEL"] = agent
    environment_before = _verified_environment()

    auto_root = run_root / "sage_auto_selection"
    auto_registry = (
        args.auto_registry_dir.resolve()
        if args.auto_registry_dir is not None
        else run_root / "sage_auto_selection_registry"
    )
    pair_root = run_root / "sage_auto_selection_parallel_pair"
    pair_artifact_root = pair_root / "artifacts"
    auto_control_root = pair_root / "control"
    _assert_empty_target(auto_root, label="Auto-selection output root")
    _assert_empty_target(auto_registry, label="Auto-selection registry")
    _assert_empty_target(pair_root, label="Auto-selection parallel-pair root")
    pair_root.mkdir(parents=True, exist_ok=False)
    auto_dashboard_root = pair_root
    dashboard_index = write_protocol_dashboard(
        auto_dashboard_root,
        mode="sage_auto_selection",
        status="running",
        phase="parallel_control_and_auto_selection",
        agent=agent,
        user=user,
        model_metadata=protocol.get("model_metadata")
        if isinstance(protocol.get("model_metadata"), dict)
        else None,
        generation_enabled=False,
        base_tool_policy=str(source_run_config.get("base_tool_policy") or ""),
        scenario_count=len(scenario_names),
        registry_dir=auto_registry,
        control_label="Fresh non-learning control",
        candidate_label="SAGE auto selection",
    )
    dashboard_task_compare_path = dashboard_index.with_name("task_compare.html")
    dashboard_url = open_dashboard(
        dashboard_task_compare_path,
        port=args.dashboard_port,
        server_root=run_root,
    )
    dashboard_opened_monotonic_ns = time.monotonic_ns()
    dashboard_open_receipt_path = auto_dashboard_root / "dashboard_open_receipt.json"
    _write_json(
        dashboard_open_receipt_path,
        {
            "dashboard": "task_compare",
            "comparison": "fresh_control_vs_sage_auto_selection",
            "path": str(dashboard_task_compare_path.resolve()),
            "url": dashboard_url,
            "external_browser_opened": True,
            "http_verified_before_open": True,
            "dashboard_server_protocol": DASHBOARD_SERVER_PROTOCOL,
            "dashboard_server_root": str(run_root.resolve()),
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "opened_monotonic_ns": dashboard_opened_monotonic_ns,
            "opened_before_model_processes": True,
        },
    )
    _write_status(status_path, status="running")

    auto_control_dir: Path | None = None
    auto_dir: Path | None = None
    last_dashboard_refresh = 0.0

    def refresh_auto_dashboard(
        control_run_dir: Path | None,
        auto_run_dir: Path | None,
        status: str,
    ) -> None:
        nonlocal last_dashboard_refresh
        now = time.monotonic()
        if status == "running" and now - last_dashboard_refresh < 5.0:
            return
        write_protocol_dashboard(
            auto_dashboard_root,
            mode="sage_auto_selection",
            status=status,
            phase="auto_selection",
            agent=agent,
            user=user,
            model_metadata=protocol.get("model_metadata")
            if isinstance(protocol.get("model_metadata"), dict)
            else None,
            generation_enabled=False,
            base_tool_policy=str(source_run_config.get("base_tool_policy") or ""),
            scenario_count=len(scenario_names),
            control_dir=control_run_dir,
            candidate_dir=auto_run_dir,
            registry_dir=auto_registry,
            control_label="Fresh non-learning control",
            candidate_label="SAGE auto selection",
        )
        last_dashboard_refresh = now

    try:
        (
            auto_control_dir,
            auto_dir,
            auto_parallel_execution,
            auto_control_outcomes,
        ) = _run_parallel_auto_pair(
            pair_root=pair_root,
            pair_artifact_root=pair_artifact_root,
            control_root=auto_control_root,
            auto_root=auto_root,
            auto_registry=auto_registry,
            mode=str(protocol.get("mode") or ""),
            agent=agent,
            user=user,
            generation_model=generation_model,
            recurrence_threshold=int(
                source_run_config.get("recurrence_threshold") or 2
            ),
            base_tool_policy=str(source_run_config.get("base_tool_policy") or ""),
            scenario_names=scenario_names,
            benchmark_manifest=benchmark_manifest,
            authority_root=authority_path.parent,
            progress_hook=refresh_auto_dashboard,
        )
        auto_run_config = _read_json(auto_dir.parent / "sage_ts_run_manifest.json")
        auto_control_run_config = _read_json(
            auto_control_dir.parent / "sage_ts_run_manifest.json"
        )
        matched_run_config_fields = (
            "agent",
            "user",
            "scenario_names",
            "processes",
            "base_tool_policy",
        )
        if (
            auto_run_config.get("actor_selection_mode") != "auto"
            or any(
                auto_run_config.get(field) != source_run_config.get(field)
                for field in matched_run_config_fields
            )
            or auto_run_config.get("resume_from_dir") is not None
            or auto_run_config.get("resume_completed_limit") is not None
        ):
            raise ActorSelectionVerificationError(
                "Auto-selection run configuration drifted from the policy donor."
            )
        if (
            auto_control_run_config.get("actor_selection_mode") != "policy"
            or any(
                auto_control_run_config.get(field) != source_run_config.get(field)
                for field in matched_run_config_fields
            )
            or auto_control_run_config.get("resume_from_dir") is not None
            or auto_control_run_config.get("resume_completed_limit") is not None
        ):
            raise ActorSelectionVerificationError(
                "Concurrent non-learning control configuration drifted from the "
                "auto-selection arm."
            )
        first_model_process_start = min(
            int(auto_parallel_execution["arms"][arm]["started_monotonic_ns"])
            for arm in ("control", "candidate")
        )
        if dashboard_opened_monotonic_ns >= first_model_process_start:
            raise ActorSelectionVerificationError(
                "Auto-selection Task Compare was not opened before both model "
                "processes started."
            )
        final_source_identity = _assert_clean_matching_source(protocol)
        environment_after = _verified_environment()
        if (
            final_source_identity != source_identity
            or environment_after != environment_before
            or _sha256(protocol_path) != protocol_sha256
            or _sha256(authority_path) != authority_sha256
            or _sha256(benchmark_manifest) != benchmark_manifest_sha256
        ):
            raise ActorSelectionVerificationError(
                "Source, environment, or frozen experiment inputs changed during "
                "auto replay."
            )
        auto_control_outcome_comparison_path = (
            pair_root / "auto_control_outcome_comparison.json"
        )
        _write_json(auto_control_outcome_comparison_path, auto_control_outcomes)
        pair_manifest_path = pair_root / "parallel_pair_manifest.json"
        pair_manifest = {
            "schema_version": 1,
            "experiment": "sage_auto_selection_parallel_control_pair",
            "status": "complete",
            "mode": str(protocol.get("mode") or ""),
            "agent": agent,
            "user": user,
            "base_tool_policy": str(source_run_config.get("base_tool_policy") or ""),
            "scenario_count": len(scenario_names),
            "scenario_order_sha256": scenario_order_sha256,
            "control_role": "fresh_non_learning_control",
            "candidate_role": "sage_auto_selection",
            "control_run_dir": str(auto_control_dir),
            "auto_run_dir": str(auto_dir),
            "control_cache_mode": "off",
            "control_source": "fresh",
            "cached_control_tasks": 0,
            "fresh_control_tasks": len(scenario_names),
            "cache_accessed": False,
            "openai_response_cache_enabled": False,
            "sage_task_cache_enabled": False,
            "persistent_response_cache_reuse": False,
            "publication_performance_endpoint": ("outcome_task_completion_similarity"),
            "legacy_score_is_performance_gate": False,
            "parallel_arms": True,
            "parallel_arm_execution": auto_parallel_execution,
            "auto_control_delivery": "not_connected",
            "auto_control_output_influences_inventory": False,
            "auto_control_output_influences_execution": False,
            "auto_inventory_source": "matched_policy_inventory_authority",
            "inventory_authority_path": str(authority_path),
            "inventory_authority_sha256": authority_sha256,
            "outcome_evaluator": current_outcome_evaluator,
            "outcome_comparison_path": str(auto_control_outcome_comparison_path),
            "outcome_comparison_sha256": _sha256(auto_control_outcome_comparison_path),
            "timezone": os.environ.get("TZ"),
            "dashboard_task_compare_path": str(dashboard_task_compare_path.resolve()),
            "dashboard_task_compare_url": dashboard_url,
            "dashboard_open_receipt_path": str(dashboard_open_receipt_path.resolve()),
        }
        _write_json(pair_manifest_path, pair_manifest)
        try:
            from scripts.verify_publication_run import (
                verify_auto_selection_parallel_pair,
            )
        except ModuleNotFoundError:
            from verify_publication_run import verify_auto_selection_parallel_pair

        auto_parallel_verification = verify_auto_selection_parallel_pair(
            pair_manifest_path,
            run_root=run_root,
            expected_tasks=len(scenario_names),
            expected_scenario_order_sha256=scenario_order_sha256,
            expected_auto_dir=auto_dir,
        )
        report = verify_matched_actor_selection_experiment(
            policy_dir=policy_dir,
            auto_dir=auto_dir,
            authority_path=authority_path,
            require_zero_generated_tool_failures=args.stage == "pilot",
        )
        if report.get("outcome_evaluator") != current_outcome_evaluator:
            raise ActorSelectionVerificationError(
                "Actor-selection comparison used an unexpected outcome evaluator."
            )
        experiment_passed = bool(report["experiment_passed"])
        _write_json(report_path, report)
        policy_auto_dashboard_root = run_root / "actor_selection_dashboard"
        policy_auto_dashboard_index = write_protocol_dashboard(
            policy_auto_dashboard_root,
            mode="sage_auto_selection",
            status="complete" if experiment_passed else "failed_gate",
            phase="policy_vs_auto_outcome_comparison",
            agent=agent,
            user=user,
            model_metadata=protocol.get("model_metadata")
            if isinstance(protocol.get("model_metadata"), dict)
            else None,
            generation_enabled=False,
            base_tool_policy=str(source_run_config.get("base_tool_policy") or ""),
            scenario_count=len(scenario_names),
            control_dir=policy_dir,
            candidate_dir=auto_dir,
            registry_dir=auto_registry,
            control_label="SAGE policy selection",
            candidate_label="SAGE auto selection",
        )
        policy_auto_dashboard_path = policy_auto_dashboard_index.with_name(
            "task_compare.html"
        )
        policy_auto_dashboard_url = open_dashboard(
            policy_auto_dashboard_path,
            port=args.dashboard_port,
            server_root=run_root,
        )
        policy_auto_dashboard_receipt_path = (
            policy_auto_dashboard_root / "dashboard_open_receipt.json"
        )
        _write_json(
            policy_auto_dashboard_receipt_path,
            {
                "dashboard": "task_compare",
                "comparison": "policy_vs_sage_auto_selection",
                "path": str(policy_auto_dashboard_path.resolve()),
                "url": policy_auto_dashboard_url,
                "external_browser_opened": True,
                "http_verified_before_open": True,
                "dashboard_server_protocol": DASHBOARD_SERVER_PROTOCOL,
                "dashboard_server_root": str(run_root.resolve()),
                "opened_at": datetime.now(timezone.utc).isoformat(),
                "opened_phase": "post_run_causal_comparison",
            },
        )
        final_dashboard_status = "complete" if experiment_passed else "failed_gate"
        refresh_auto_dashboard(
            auto_control_dir,
            auto_dir,
            final_dashboard_status,
        )
        arm_evidence_filenames = (
            "actor_request_audit.jsonl",
            "actor_request_audit_summary.json",
            "actor_schema_catalog.json",
            "actor_schema_catalog.jsonl",
            "live_result_summary.json",
            "llm_usage_events.jsonl",
            "llm_usage_summary.json",
            "result_summary.json",
            "scenario_tool_selection.jsonl",
            "selection_summary.json",
        )
        evidence_paths: dict[str, Path] = {
            "policy.protocol_manifest": protocol_path,
            "policy.inventory_authority": authority_path,
            "policy.benchmark_manifest": benchmark_manifest,
            "comparison.live_policy_control_dashboard_open_receipt": (
                run_root / "dashboard_open_receipt.json"
            ),
            "comparison.live_policy_control_task_compare_data": (
                run_root / "dashboard" / "task_compare_data.json"
            ),
            "comparison.live_policy_control_task_compare_html": (
                run_root / "dashboard" / "task_compare.html"
            ),
            "comparison.outcome_report": report_path,
            "comparison.live_auto_control_dashboard_open_receipt": (
                dashboard_open_receipt_path
            ),
            "comparison.live_auto_control_task_compare_data": (
                auto_dashboard_root / "dashboard" / "task_compare_data.json"
            ),
            "comparison.live_auto_control_task_compare_html": (
                auto_dashboard_root / "dashboard" / "task_compare.html"
            ),
            "comparison.policy_auto_dashboard_open_receipt": (
                policy_auto_dashboard_receipt_path
            ),
            "comparison.task_compare_data": (
                policy_auto_dashboard_root / "dashboard" / "task_compare_data.json"
            ),
            "comparison.task_compare_html": (
                policy_auto_dashboard_root / "dashboard" / "task_compare.html"
            ),
            "auto_parallel_pair.manifest": pair_manifest_path,
            "auto_parallel_pair.control_status": (
                pair_root / "control_arm_status.json"
            ),
            "auto_parallel_pair.auto_status": pair_root / "candidate_arm_status.json",
            "auto_parallel_pair.outcome_comparison": (
                auto_control_outcome_comparison_path
            ),
            "auto_parallel_pair.control_run_manifest": (
                auto_control_dir.parent / "sage_ts_run_manifest.json"
            ),
            "policy.run_manifest": policy_dir.parent / "sage_ts_run_manifest.json",
            "auto.run_manifest": auto_dir.parent / "sage_ts_run_manifest.json",
        }
        for filename in (
            "actor_request_audit.jsonl",
            "actor_request_audit_summary.json",
            "actor_schema_catalog.json",
            "actor_schema_catalog.jsonl",
            "live_result_summary.json",
            "llm_usage_events.jsonl",
            "llm_usage_summary.json",
            "result_summary.json",
        ):
            evidence_paths[f"auto_parallel_control.{filename}"] = (
                auto_control_dir / filename
            )
        for arm_name, arm_dir in (("policy", policy_dir), ("auto", auto_dir)):
            for filename in arm_evidence_filenames:
                evidence_paths[f"{arm_name}.{filename}"] = arm_dir / filename
        evidence_hashes = _required_evidence_hashes(evidence_paths)
        experiment_manifest = {
            "schema_version": 2,
            "experiment": "sage_auto_selection",
            "stage": args.stage,
            "status": "complete" if experiment_passed else "failed_gate",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "policy_protocol_manifest_path": str(protocol_path),
            "policy_protocol_manifest_sha256": protocol_sha256,
            "policy_run_dir": str(policy_dir),
            "auto_run_dir": str(auto_dir),
            "control_run_dir": protocol.get("control_dir"),
            "auto_control_run_dir": str(auto_control_dir),
            "auto_parallel_pair_manifest_path": str(pair_manifest_path),
            "auto_parallel_pair_manifest_sha256": _sha256(pair_manifest_path),
            "auto_parallel_arms": True,
            "auto_parallel_arm_execution": auto_parallel_execution,
            "auto_parallel_verification": auto_parallel_verification,
            "auto_control_outcome_comparison_path": str(
                auto_control_outcome_comparison_path
            ),
            "auto_control_outcomes": auto_control_outcomes,
            "auto_control_cache_mode": "off",
            "auto_control_source": "fresh",
            "auto_cached_control_tasks": 0,
            "auto_fresh_control_tasks": len(scenario_names),
            "auto_control_cache_accessed": False,
            "auto_control_delivery": "not_connected",
            "auto_control_output_influences_inventory": False,
            "auto_control_output_influences_execution": False,
            "publication_performance_endpoint": ("outcome_task_completion_similarity"),
            "legacy_score_is_performance_gate": False,
            "mechanism_counts_are_performance_gates": False,
            "inventory_authority_path": str(authority_path),
            "inventory_authority_sha256": authority_sha256,
            "inventory_authority_tasks_sha256": authority.get("tasks_sha256"),
            "benchmark_manifest_path": str(benchmark_manifest),
            "benchmark_manifest_sha256": benchmark_manifest_sha256,
            "source_identity": source_identity,
            "policy_publication_verification": policy_publication_verification,
            "publication_environment_before": environment_before,
            "publication_environment_after": environment_after,
            "publication_environment_sha256": _canonical_sha256(environment_before),
            "scenario_count": len(scenario_names),
            "scenario_order_sha256": scenario_order_sha256,
            "policy_generation_enabled": authority.get("source_generation_enabled"),
            "auto_generation_enabled": False,
            "auto_evolution_source": "matched_policy_inventory_authority",
            "actor_selection_treatment": {
                "policy": (
                    "selector prompting, cascade, dynamic schema filtering, wrapper "
                    "hiding, and optional named tool_choice"
                ),
                "auto": (
                    "upstream model inference over the exact routed schemas, with no "
                    "selector prompt or named tool_choice"
                ),
            },
            "estimand": report["estimand"],
            "persistent_response_cache_reuse": False,
            "outcome_evaluator": current_outcome_evaluator,
            "outcome_comparison_path": str(report_path),
            "dashboard_task_compare_path": str(policy_auto_dashboard_path),
            "dashboard_task_compare_url": policy_auto_dashboard_url,
            "dashboard_open_receipt_path": str(policy_auto_dashboard_receipt_path),
            "live_auto_control_task_compare_path": str(dashboard_task_compare_path),
            "live_auto_control_task_compare_url": dashboard_url,
            "live_auto_control_dashboard_open_receipt_path": str(
                dashboard_open_receipt_path
            ),
            "policy_auto_dashboard_open_receipt_path": str(
                policy_auto_dashboard_receipt_path
            ),
            "live_policy_control_task_compare_path": str(
                (run_root / "dashboard" / "task_compare.html").resolve()
            ),
            "live_policy_control_task_compare_url": protocol.get(
                "dashboard_task_compare_url"
            ),
            "live_policy_control_dashboard_open_receipt_path": str(
                (run_root / "dashboard_open_receipt.json").resolve()
            ),
            "evidence_hashes": evidence_hashes,
            "integrity_gate_passed": report["integrity_gate_passed"],
            "integrity_gate_reasons": report["integrity_gate_reasons"],
            "outcome_evidence_complete": report["outcome_evidence_complete"],
            "performance_gate_applied": report["performance_gate_applied"],
            "performance_gate_reason": report["performance_gate_reason"],
            "experiment_passed": experiment_passed,
            "stability_gate_passed": report["stability_gate_passed"],
            "stability_gate_reasons": report["stability_gate_reasons"],
        }
        _write_json(experiment_manifest_path, experiment_manifest)
        _write_status(
            status_path,
            status="complete" if experiment_passed else "failed_gate",
            auto_run_dir=auto_dir,
        )
        lifecycle["finalized"] = True
        outcome = report["outcomes"]
        print(
            json.dumps(
                {
                    "stage": args.stage,
                    "integrity_gate_passed": report["integrity_gate_passed"],
                    "outcome_evidence_complete": report["outcome_evidence_complete"],
                    "performance_gate_applied": report["performance_gate_applied"],
                    "experiment_passed": experiment_passed,
                    "stability_gate_passed": report["stability_gate_passed"],
                    "scenario_count": outcome["scenario_count"],
                    "outcome_evaluated_count": outcome["outcome_evaluated_count"],
                    "policy_exact_outcome_successes": outcome[
                        "policy_exact_outcome_successes"
                    ],
                    "auto_exact_outcome_successes": outcome[
                        "auto_exact_outcome_successes"
                    ],
                    "policy_mean_outcome_similarity": outcome[
                        "policy_mean_outcome_similarity"
                    ],
                    "auto_mean_outcome_similarity": outcome[
                        "auto_mean_outcome_similarity"
                    ],
                    "fresh_control_exact_outcome_successes": auto_control_outcomes[
                        "control_exact_outcome_successes"
                    ],
                    "fresh_control_mean_outcome_similarity": auto_control_outcomes[
                        "control_mean_outcome_similarity"
                    ],
                    "comparison_path": str(report_path),
                },
                indent=2,
            )
        )
        if not experiment_passed:
            raise SystemExit(2)
    except (Exception, ActorSelectionVerificationError) as exc:
        _write_status(
            status_path,
            status="failed",
            auto_run_dir=auto_dir,
            error=traceback.format_exc(),
        )
        try:
            refresh_auto_dashboard(
                auto_control_dir,
                auto_dir,
                "failed",
            )
        except Exception:
            pass
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
