#!/usr/bin/env python3
"""Append and verify a matched SAGE auto-selection arm to a policy protocol run."""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import os
import subprocess
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sage_ts.adapters.sage_run_adapter import SageRunConfig, run_sage_with_registry
from sage_ts.evaluation.actor_selection_comparison import (
    ActorSelectionVerificationError,
    verify_matched_actor_selection_experiment,
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
            "schema_version": 1,
            "experiment": "sage_auto_selection",
            "stage": args.stage,
            "status": "preflight",
            "policy_run_root": str(run_root),
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
            pilot_evidence.get("experiment") != "sage_auto_selection"
            or pilot_evidence.get("stage") != "pilot"
            or pilot_evidence.get("status") != "complete"
            or pilot_evidence.get("stability_gate_passed") is not True
            or pilot_evidence.get("scenario_count")
            != STAGE_PINS["pilot"]["scenario_count"]
            or pilot_evidence.get("benchmark_manifest_sha256")
            != STAGE_PINS["pilot"]["benchmark_sha256"]
            or pilot_evidence.get("scenario_order_sha256")
            != STAGE_PINS["pilot"]["scenario_order_sha256"]
            or pilot_evidence.get("source_identity") != source_identity
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
    _assert_empty_target(auto_root, label="Auto-selection output root")
    _assert_empty_target(auto_registry, label="Auto-selection registry")
    _write_status(status_path, status="running")

    auto_dir: Path | None = None
    try:
        auto_dir = run_sage_with_registry(
            SageRunConfig(
                agent=agent,
                user=user,
                scenario_names=scenario_names,
                output_dir=auto_root,
                registry_dir=auto_registry,
                run_type=f"{protocol.get('mode')}_sage_auto_selection",
                recurrence_threshold=int(
                    source_run_config.get("recurrence_threshold") or 2
                ),
                base_tool_policy=str(source_run_config.get("base_tool_policy") or ""),
                actor_selection_mode="auto",
                inventory_authority_replay_dir=authority_path.parent,
                manifest_path=benchmark_manifest,
                failure_memory_path=None,
                generation_model=generation_model,
            ),
            generator=None,
        )
        auto_run_config = _read_json(auto_dir.parent / "sage_ts_run_manifest.json")
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
        report = verify_matched_actor_selection_experiment(
            policy_dir=policy_dir,
            auto_dir=auto_dir,
            authority_path=authority_path,
            require_zero_generated_tool_failures=args.stage == "pilot",
        )
        _write_json(report_path, report)
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
            "comparison.outcome_report": report_path,
            "policy.run_manifest": policy_dir.parent / "sage_ts_run_manifest.json",
            "auto.run_manifest": auto_dir.parent / "sage_ts_run_manifest.json",
        }
        for arm_name, arm_dir in (("policy", policy_dir), ("auto", auto_dir)):
            for filename in arm_evidence_filenames:
                evidence_paths[f"{arm_name}.{filename}"] = arm_dir / filename
        evidence_hashes = _required_evidence_hashes(evidence_paths)
        experiment_manifest = {
            "schema_version": 1,
            "experiment": "sage_auto_selection",
            "stage": args.stage,
            "status": "complete" if report["stability_gate_passed"] else "failed_gate",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "policy_protocol_manifest_path": str(protocol_path),
            "policy_protocol_manifest_sha256": protocol_sha256,
            "policy_run_dir": str(policy_dir),
            "auto_run_dir": str(auto_dir),
            "control_run_dir": protocol.get("control_dir"),
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
            "outcome_comparison_path": str(report_path),
            "evidence_hashes": evidence_hashes,
            "stability_gate_passed": report["stability_gate_passed"],
            "stability_gate_reasons": report["stability_gate_reasons"],
        }
        _write_json(experiment_manifest_path, experiment_manifest)
        _write_status(
            status_path,
            status="complete" if report["stability_gate_passed"] else "failed_gate",
            auto_run_dir=auto_dir,
        )
        lifecycle["finalized"] = True
        outcome = report["outcomes"]
        print(
            json.dumps(
                {
                    "stage": args.stage,
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
                    "comparison_path": str(report_path),
                },
                indent=2,
            )
        )
        if not report["stability_gate_passed"]:
            raise SystemExit(2)
    except (Exception, ActorSelectionVerificationError) as exc:
        _write_status(
            status_path,
            status="failed",
            auto_run_dir=auto_dir,
            error=traceback.format_exc(),
        )
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
