#!/usr/bin/env python3
"""Run one baseline through ToolSandbox's native OpenAI actor implementation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sage_ts.adapters.role_factory import TOOL_SANDBOX_NATIVE_AGENT_RUNTIME
from sage_ts.adapters.toolsandbox_adapter import ToolSandboxRunConfig, run_toolsandbox
from sage_ts.config.models import paired_model_metadata
from sage_ts.config.splits import load_split_names
from sage_ts.dashboard.exporters import open_dashboard, write_protocol_dashboard
from sage_ts.evaluation.run_metrics import compare_runs, summarize_run
from sage_ts.runtime.base_toolset import UPSTREAM_POLICY

EXPECTED_MANIFEST_SHA256 = (
    "21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec"
)
EXPECTED_FIXTURE_SHA256 = (
    "eae0a6ab7d2ee5dd272612a0b5ce44d85af34cd1297ff662007260941192322f"
)
EXPECTED_FIXED_TIMESTAMP = "1784832588"
EXPECTED_SCENARIO_ORDER_SHA256 = (
    "fec899dde5b3ce1879157c16eff120e24c1791a2ab1df53712677bcacb250176"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _git_value(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def _validate_inputs(manifest: Path, fixture: Path) -> tuple[str, str]:
    manifest_sha256 = _sha256(manifest)
    fixture_sha256 = _sha256(fixture)
    if manifest_sha256 != EXPECTED_MANIFEST_SHA256:
        raise ValueError(
            "Benchmark manifest hash mismatch: "
            f"expected {EXPECTED_MANIFEST_SHA256}, observed {manifest_sha256}"
        )
    if fixture_sha256 != EXPECTED_FIXTURE_SHA256:
        raise ValueError(
            "RapidAPI fixture hash mismatch: "
            f"expected {EXPECTED_FIXTURE_SHA256}, observed {fixture_sha256}"
        )
    if os.environ.get("TOOL_SANDBOX_FIXED_NOW_TIMESTAMP") != EXPECTED_FIXED_TIMESTAMP:
        raise ValueError(
            "TOOL_SANDBOX_FIXED_NOW_TIMESTAMP must be "
            f"{EXPECTED_FIXED_TIMESTAMP} for this matched comparison."
        )
    if os.environ.get("TOOLSANDBOX_RAPID_CACHE_MODE") != "read_only":
        raise ValueError("TOOLSANDBOX_RAPID_CACHE_MODE must be read_only.")
    configured_fixture = Path(os.environ.get("TOOLSANDBOX_RAPID_CACHE_PATH", ""))
    if configured_fixture.resolve() != fixture.resolve():
        raise ValueError(
            "TOOLSANDBOX_RAPID_CACHE_PATH must resolve to the validated fixture."
        )
    return manifest_sha256, fixture_sha256


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--comparison-run", type=Path)
    parser.add_argument("--dashboard-port", type=int, default=64540)
    parser.add_argument("--agent", default="gpt-4o-mini")
    parser.add_argument("--user", default="gpt-4o-mini")
    args = parser.parse_args()

    manifest = args.manifest.resolve()
    fixture = args.fixture.resolve()
    output_root = args.output_root.resolve()
    comparison_run = args.comparison_run.resolve() if args.comparison_run else None
    if output_root.exists() and any(output_root.iterdir()):
        raise ValueError(f"Output root must be new and empty: {output_root}")
    if (
        comparison_run is not None
        and not (comparison_run / "result_summary.json").is_file()
    ):
        raise FileNotFoundError(
            f"Comparison run has no result_summary.json: {comparison_run}"
        )

    manifest_sha256, fixture_sha256 = _validate_inputs(manifest, fixture)
    scenario_names = tuple(load_split_names(manifest, "full_benchmark"))
    if len(scenario_names) != 1032 or len(set(scenario_names)) != 1032:
        raise ValueError("Expected exactly 1,032 unique benchmark scenarios.")
    scenario_order_sha256 = hashlib.sha256(
        ("\n".join(scenario_names) + "\n").encode("utf-8")
    ).hexdigest()
    if scenario_order_sha256 != EXPECTED_SCENARIO_ORDER_SHA256:
        raise ValueError(
            "Scenario order hash mismatch: "
            f"expected {EXPECTED_SCENARIO_ORDER_SHA256}, "
            f"observed {scenario_order_sha256}"
        )

    output_root.mkdir(parents=True)
    control_root = output_root / "control"
    model_metadata = paired_model_metadata(
        agent_model=args.agent,
        generation_model=args.agent,
        user_model=args.user,
    )
    definition: dict[str, Any] = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "comparison": "native_toolsandbox_actor_vs_sage_wrapped_actor",
        "execution_scope": (
            "The actor is ToolSandbox OpenAIAPIAgent with only model_name set for "
            "gpt-4o-mini compatibility. The fixed-order harness, user simulator, "
            "fixture, clock, outcome evaluators, and dashboard are held constant."
        ),
        "agent_runtime": TOOL_SANDBOX_NATIVE_AGENT_RUNTIME,
        "actor_selection_mode": "toolsandbox_native",
        "agent_model": args.agent,
        "user_model": args.user,
        "scenario_count": len(scenario_names),
        "scenario_order_sha256": scenario_order_sha256,
        "manifest": str(manifest),
        "manifest_sha256": manifest_sha256,
        "fixture": str(fixture),
        "fixture_sha256": fixture_sha256,
        "fixed_timestamp": int(EXPECTED_FIXED_TIMESTAMP),
        "trajectory_cache": "off",
        "response_replay": "off",
        "comparison_run": str(comparison_run) if comparison_run else None,
        "git_commit": _git_value("rev-parse", "HEAD"),
        "git_tree": _git_value("write-tree"),
        "git_status": _git_value("status", "--porcelain"),
        "native_actor_class": "tool_sandbox.roles.openai_api_agent.OpenAIAPIAgent",
        "sage_actor_wrapper_bypassed": True,
        "original_messages_and_tool_schemas": True,
        "named_tool_choice": False,
        "sage_actor_policy_prompts": False,
        "sage_schema_filtering": False,
        "sage_response_postprocessing": False,
    }
    _write_json(output_root / "comparison_definition.json", definition)

    control_dir: Path | None = None

    def refresh(status: str) -> Path:
        return write_protocol_dashboard(
            output_root,
            mode="pure_toolsandbox_vs_sage_wrapped_control",
            status=status,
            phase="control",
            agent=args.agent,
            user=args.user,
            model_metadata=model_metadata,
            generation_enabled=False,
            base_tool_policy=UPSTREAM_POLICY,
            scenario_count=len(scenario_names),
            control_dir=control_dir,
            candidate_dir=comparison_run,
            artifact_root=output_root / "artifacts",
        )

    dashboard_index = refresh("running")
    dashboard_path = dashboard_index.with_name("task_compare.html")
    dashboard_url = open_dashboard(
        dashboard_path,
        port=args.dashboard_port,
        server_root=output_root,
    )
    _write_json(
        output_root / "dashboard_open_receipt.json",
        {
            "dashboard": "task_compare",
            "comparison": "native_toolsandbox_actor_vs_sage_wrapped_actor",
            "path": str(dashboard_path),
            "url": dashboard_url,
            "external_browser_opened": True,
            "http_verified_before_open": True,
            "opened_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    def progress(
        run_dir: Path,
        rows: list[dict[str, object]],
        status: str,
        scenario_count: int,
    ) -> None:
        nonlocal control_dir
        control_dir = run_dir
        _write_json(
            output_root / "baseline_status.json",
            {
                "status": status,
                "completed_count": len(rows),
                "scenario_count": scenario_count,
                "exception_count": sum(
                    1 for row in rows if row.get("exception_type") is not None
                ),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "run_dir": str(run_dir),
            },
        )
        refresh(status)

    try:
        control_dir = run_toolsandbox(
            ToolSandboxRunConfig(
                agent=args.agent,
                user=args.user,
                scenario_names=scenario_names,
                output_dir=control_root,
                processes=1,
                run_type="pure_toolsandbox_control",
                base_tool_policy=UPSTREAM_POLICY,
                agent_runtime=TOOL_SANDBOX_NATIVE_AGENT_RUNTIME,
            ),
            progress_hook=progress,
        )
        result_payload = json.loads(
            (control_dir / "result_summary.json").read_text(encoding="utf-8")
        )
        rows = result_payload.get("per_scenario_results", [])
        observed_names = [str(row.get("name")) for row in rows]
        observed_order_sha256 = hashlib.sha256(
            ("\n".join(observed_names) + "\n").encode("utf-8")
        ).hexdigest()
        exceptions = [
            {
                "scenario": row.get("name"),
                "exception_type": row.get("exception_type"),
            }
            for row in rows
            if row.get("exception_type") is not None
        ]
        v9_values = [
            float(row["outcome_similarity"])
            for row in rows
            if row.get("outcome_similarity") is not None
        ]
        paper_v1_values = [
            float(row["online_feedback_outcome_similarity"])
            for row in rows
            if row.get("online_feedback_outcome_similarity") is not None
        ]
        cached_llm_calls = sum(
            int(row.get("llm_cached_call_count") or 0) for row in rows
        )
        control_manifest = json.loads(
            (control_root / "sage_ts_run_manifest.json").read_text(encoding="utf-8")
        )
        validation = {
            "status": "pass",
            "scenario_count": len(rows),
            "scenario_order_sha256": observed_order_sha256,
            "exception_count": len(exceptions),
            "exceptions": exceptions,
            "v9_outcome_count": len(v9_values),
            "paper_v1_outcome_count": len(paper_v1_values),
            "cached_llm_call_count": cached_llm_calls,
            "agent_runtime": control_manifest.get("agent_runtime"),
            "actor_selection_mode": control_manifest.get("actor_selection_mode"),
        }
        failures = []
        if observed_names != list(scenario_names):
            failures.append("scenario_order_or_membership_mismatch")
        if observed_order_sha256 != EXPECTED_SCENARIO_ORDER_SHA256:
            failures.append("scenario_order_hash_mismatch")
        if len(exceptions) != 0:
            failures.append("runtime_exceptions_present")
        if len(v9_values) != 1032:
            failures.append("v9_outcome_count_mismatch")
        if len(paper_v1_values) != 800:
            failures.append("paper_v1_outcome_count_mismatch")
        if cached_llm_calls != 0:
            failures.append("cached_llm_calls_present")
        if control_manifest.get("agent_runtime") != TOOL_SANDBOX_NATIVE_AGENT_RUNTIME:
            failures.append("native_agent_runtime_not_recorded")
        if control_manifest.get("actor_selection_mode") != "toolsandbox_native":
            failures.append("native_actor_selection_mode_not_recorded")
        validation["failures"] = failures
        if failures:
            validation["status"] = "failed"
        _write_json(output_root / "strict_validation.json", validation)
        if failures:
            raise ValueError(f"Strict native-baseline validation failed: {failures}")

        pure_summary = summarize_run(control_dir)
        result: dict[str, Any] = {
            "status": "complete",
            "pure_toolsandbox": pure_summary,
            "pure_toolsandbox_v9_outcome": sum(v9_values) / len(v9_values),
            "pure_toolsandbox_paper_v1_outcome": sum(paper_v1_values)
            / len(paper_v1_values),
            "comparison_run": str(comparison_run) if comparison_run else None,
            "strict_validation": validation,
        }
        if comparison_run is not None:
            paired = compare_runs(control_dir, comparison_run)
            comparison_payload = json.loads(
                (comparison_run / "result_summary.json").read_text(encoding="utf-8")
            )
            comparison_rows = comparison_payload.get("per_scenario_results", [])
            comparison_paper_v1_values = [
                float(row["online_feedback_outcome_similarity"])
                for row in comparison_rows
                if row.get("online_feedback_outcome_similarity") is not None
            ]
            if len(comparison_paper_v1_values) != 800:
                raise ValueError(
                    "Comparison run does not contain exactly 800 paper-v1 outcomes."
                )
            comparison_paper_v1 = sum(comparison_paper_v1_values) / len(
                comparison_paper_v1_values
            )
            _write_json(output_root / "paired_comparison.json", paired)
            result["paired_comparison"] = {
                "pure_toolsandbox_outcome": paired["control_mean_outcome_similarity"],
                "sage_wrapped_outcome": paired["candidate_mean_outcome_similarity"],
                "sage_wrapped_minus_pure": paired["mean_outcome_similarity_delta"],
                "pure_toolsandbox_paper_v1_outcome": sum(paper_v1_values)
                / len(paper_v1_values),
                "sage_wrapped_paper_v1_outcome": comparison_paper_v1,
                "sage_wrapped_minus_pure_paper_v1": comparison_paper_v1
                - (sum(paper_v1_values) / len(paper_v1_values)),
            }
        _write_json(output_root / "final_result.json", result)
        refresh("complete")
    except BaseException as exc:
        _write_json(
            output_root / "failure.json",
            {
                "status": "failed",
                "exception_type": type(exc).__name__,
                "message": str(exc),
                "failed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        refresh("failed")
        raise


if __name__ == "__main__":
    main()
