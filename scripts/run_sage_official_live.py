# mypy: ignore-errors
"""Run SAGE against official benchmark harnesses.

This runner is intentionally separate from the repository-probe smoke runner.
It uses each benchmark's own scorer when a scorer is available locally:

* tau2/tau3: official tau2 simulation evaluator.
* Terminal-Bench: official Docker harness and task parser.
* ScienceAgentBench: blocked unless the non-redistributable benchmark artifacts
  are present under ``external/ScienceAgentBench/benchmark``.

The SAGE arm is a lightweight live adaptation layer: failed official outcomes
produce bounded prompt helpers with gpt-4o-mini, and later tasks run with those
helpers injected into the benchmark agent. The dashboard is generated from the
official scorer outputs, not from repository metadata probes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sage_agent import SAGERunSummary  # noqa: E402
from sage_agent.dashboard import (  # noqa: E402
    open_standalone_dashboard,
    write_standalone_dashboard,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run harness-backed SAGE live evaluations."
    )
    parser.add_argument(
        "--dataset",
        choices=("tau2-bench", "tau3-bench", "terminal-bench", "scienceagentbench"),
        required=True,
    )
    parser.add_argument("--samples", type=int, default=40)
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument(
        "--output-root", type=Path, default=Path("outputs/sage_official_live")
    )
    parser.add_argument("--run-id", default="")
    parser.add_argument("--dashboard-port", type=int, default=62660)
    parser.add_argument("--no-dashboard-open", action="store_true")
    parser.add_argument("--max-helpers", type=int, default=3)
    parser.add_argument(
        "--active-helpers",
        type=int,
        default=2,
        help="Most recent accepted helpers injected into an active task.",
    )
    parser.add_argument("--seed", type=int, default=300)
    parser.add_argument("--tau2-repo", type=Path, default=Path("external/tau2-bench"))
    parser.add_argument("--tau2-domain", default="airline")
    parser.add_argument("--tau2-max-steps", type=int, default=200)
    parser.add_argument("--tau2-timeout-sec", type=float, default=180.0)
    parser.add_argument(
        "--tau2-task-id",
        action="append",
        default=[],
        help="Specific tau2 task ID to run. Repeat to provide many.",
    )
    parser.add_argument(
        "--terminal-bench-repo",
        type=Path,
        default=Path("external/terminal-bench"),
    )
    parser.add_argument("--terminal-agent-timeout-sec", type=float, default=240.0)
    parser.add_argument("--terminal-test-timeout-sec", type=float, default=240.0)
    parser.add_argument(
        "--terminal-task-id",
        action="append",
        default=[],
        help="Specific Terminal-Bench task ID to run. Repeat to provide many.",
    )
    parser.add_argument(
        "--scienceagentbench-repo",
        type=Path,
        default=Path("external/ScienceAgentBench"),
    )
    args = parser.parse_args()

    if args.model != "gpt-4o-mini":
        raise SystemExit("Live development runs are capped to gpt-4o-mini.")
    _install_interrupt_handler()

    if args.dataset in {"tau2-bench", "tau3-bench"}:
        _reexec_if_missing("tau2", ROOT / "artifacts/live_envs/tau2/bin/python")
        _run_tau2(args)
    elif args.dataset == "terminal-bench":
        _reexec_if_missing(
            "terminal_bench", ROOT / "artifacts/live_envs/terminal_bench/bin/python"
        )
        _run_terminal_bench(args)
    else:
        _run_scienceagentbench(args)


def _reexec_if_missing(module_name: str, python_path: Path) -> None:
    try:
        __import__(module_name)
        return
    except Exception:
        pass
    if os.environ.get("SAGE_OFFICIAL_LIVE_REEXEC") == "1":
        raise SystemExit(f"Required module is not importable: {module_name}")
    if not python_path.exists():
        raise SystemExit(
            f"Missing benchmark virtualenv for {module_name}: {python_path}. "
            "Create it with the setup commands in README.md."
        )
    env = dict(os.environ)
    env["SAGE_OFFICIAL_LIVE_REEXEC"] = "1"
    env["PYTHONPATH"] = (
        f"{SRC}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else str(SRC)
    )
    os.execvpe(str(python_path), [str(python_path), __file__, *sys.argv[1:]], env)


def _run_tau2(args: argparse.Namespace) -> None:
    from tau2.agent.llm_agent import LLMAgent
    from tau2.registry import registry
    from tau2.runner import get_tasks, run_single_task

    _quiet_loguru()

    class SAGEGuidedTauAgent(LLMAgent):
        def __init__(self, *agent_args, sage_guidance: str = "", **kwargs) -> None:
            super().__init__(*agent_args, **kwargs)
            self._sage_guidance = sage_guidance.strip()

        @property
        def system_prompt(self) -> str:
            base = super().system_prompt
            if not self._sage_guidance:
                return base
            return (
                f"{base}\n\n"
                "<sage_generated_helpers>\n"
                f"{self._sage_guidance}\n"
                "</sage_generated_helpers>\n"
                "Use SAGE helpers only as general guidance from prior official "
                "outcomes. Follow the domain policy and available tools exactly."
            )

    def create_sage_guided_tau_agent(tools, domain_policy, **kwargs):
        llm_args = dict(kwargs.get("llm_args") or {})
        guidance = str(llm_args.pop("sage_guidance", ""))
        return SAGEGuidedTauAgent(
            tools=tools,
            domain_policy=domain_policy,
            llm=kwargs.get("llm"),
            llm_args=llm_args,
            sage_guidance=guidance,
        )

    try:
        registry.register_agent_factory(
            create_sage_guided_tau_agent, "sage_guided_tau_agent"
        )
    except ValueError:
        pass

    run_dir = _run_dir(args)
    helper_path = run_dir / "sage_prompt_helpers.md"
    helper_path.write_text("", encoding="utf-8")
    _write_prompt_registry(run_dir, [])
    tasks = get_tasks(
        args.tau2_domain,
        task_ids=list(args.tau2_task_id) if args.tau2_task_id else None,
        num_tasks=None if args.tau2_task_id else args.samples,
    )[: args.samples]
    selected = [_tau2_task_id(args.tau2_domain, task.id) for task in tasks]
    _write_manifest(
        run_dir,
        args,
        {
            "dataset": args.dataset,
            "official_harness": "tau2",
            "domain": args.tau2_domain,
            "selected_task_ids": selected,
        },
    )

    baseline_results: list[dict[str, Any]] = []
    sage_events: list[dict[str, Any]] = []
    helper_guidance: list[str] = []
    dashboard_path = _write_live_dashboard(
        args=args,
        run_dir=run_dir,
        environment=f"{args.dataset}:{args.tau2_domain}",
        baseline_results=baseline_results,
        sage_events=sage_events,
        run_metadata={
            "status": "running",
            "official_harness": "tau2",
            "comparison_valid": True,
            "selected_task_ids": selected,
        },
    )
    _open_dashboard(args, dashboard_path)

    try:
        for index, task in enumerate(tasks, start=1):
            task_spec = _task_spec(
                task_id=_tau2_task_id(args.tau2_domain, task.id),
                name=f"tau2 {args.tau2_domain} {task.id}",
                prompt=f"Official tau2 {args.tau2_domain} task {task.id}",
                metadata={"domain": args.tau2_domain, "source_task_id": task.id},
            )
            print(
                f"tau2 {args.tau2_domain}: task {index}/{len(tasks)} baseline {task.id}",
                flush=True,
            )
            baseline_result = _run_one_tau2_task(
                args=args,
                run_single_task=run_single_task,
                task=task,
                task_spec=task_spec,
                agent="llm_agent",
                sage_guidance="",
                seed=args.seed + index,
                save_dir=run_dir / "tau2_artifacts" / "baseline",
                policy=f"official_tau2_llm_agent:{args.model}",
            )
            baseline_results.append(baseline_result)

            print(
                f"tau2 {args.tau2_domain}: task {index}/{len(tasks)} sage {task.id}",
                flush=True,
            )
            guidance_items, helper_names = _active_helpers(helper_guidance, args)
            sage_result = _run_one_tau2_task(
                args=args,
                run_single_task=run_single_task,
                task=task,
                task_spec=task_spec,
                agent="sage_guided_tau_agent",
                sage_guidance="\n\n".join(guidance_items),
                seed=args.seed + 10_000 + index,
                save_dir=run_dir / "tau2_artifacts" / "sage",
                policy=f"official_tau2_sage_guided_agent:{args.model}",
                visible_helpers=helper_names,
            )
            sage_events.append(_task_event_from_result(sage_result))

            if not sage_result["success"] and len(helper_guidance) < args.max_helpers:
                baseline_note = (
                    "The baseline agent succeeded on the same task."
                    if baseline_result.get("success")
                    else "The baseline agent also failed on the same task."
                )
                helper = _generate_prompt_helper(
                    args=args,
                    dataset="tau2",
                    task_id=task_spec["task_id"],
                    transcript=sage_result.get("transcript", []),
                    failure_summary=(
                        "Official tau2 reward was below 1.0. " + baseline_note
                    ),
                )
                if helper:
                    helper_guidance.append(
                        f"### sage_prompt_helper_{len(helper_guidance) + 1}\n{helper}"
                    )
                    helper_path.write_text(
                        "\n\n".join(helper_guidance), encoding="utf-8"
                    )
                    _write_prompt_registry(run_dir, helper_guidance)
                    sage_events.append(
                        {
                            "event": "tool_birth",
                            "tool_name": f"sage_prompt_helper_{len(helper_guidance)}",
                            "accepted": True,
                            "errors": [],
                            "cases": 1,
                            "task_id": task_spec["task_id"],
                        }
                    )

            _write_live_dashboard(
                args=args,
                run_dir=run_dir,
                environment=f"{args.dataset}:{args.tau2_domain}",
                baseline_results=baseline_results,
                sage_events=sage_events,
                run_metadata={
                    "status": "running",
                    "official_harness": "tau2",
                    "comparison_valid": True,
                    "completed": index,
                    "requested_samples": args.samples,
                    "selected_task_ids": selected,
                    "max_helpers": args.max_helpers,
                    "active_helpers": args.active_helpers,
                },
            )
    except KeyboardInterrupt:
        interrupted_dashboard = _write_live_dashboard(
            args=args,
            run_dir=run_dir,
            environment=f"{args.dataset}:{args.tau2_domain}",
            baseline_results=baseline_results,
            sage_events=sage_events,
            run_metadata={
                "status": "stopped_interrupted",
                "official_harness": "tau2",
                "comparison_valid": True,
                "completed": len(
                    [
                        event
                        for event in sage_events
                        if event.get("event") == "task_result"
                    ]
                ),
                "requested_samples": args.samples,
                "selected_task_ids": selected,
                "helper_path": str(helper_path),
                "stopped_at": datetime.now(timezone.utc).isoformat(),
                "max_helpers": args.max_helpers,
                "active_helpers": args.active_helpers,
            },
        )
        _write_run_result(run_dir, baseline_results, sage_events, interrupted_dashboard)
        print(
            json.dumps(
                {
                    "run_dir": str(run_dir),
                    "dashboard_path": str(interrupted_dashboard),
                    "status": "stopped_interrupted",
                },
                indent=2,
            )
        )
        return

    final_dashboard = _write_live_dashboard(
        args=args,
        run_dir=run_dir,
        environment=f"{args.dataset}:{args.tau2_domain}",
        baseline_results=baseline_results,
        sage_events=sage_events,
        run_metadata={
            "status": "completed",
            "official_harness": "tau2",
            "comparison_valid": True,
            "completed": len(tasks),
            "requested_samples": args.samples,
            "selected_task_ids": selected,
            "helper_path": str(helper_path),
            "max_helpers": args.max_helpers,
            "active_helpers": args.active_helpers,
        },
    )
    _write_run_result(run_dir, baseline_results, sage_events, final_dashboard)
    print(
        json.dumps(
            {"run_dir": str(run_dir), "dashboard_path": str(final_dashboard)}, indent=2
        )
    )


def _tau2_config(args: argparse.Namespace, *, agent: str, sage_guidance: str) -> Any:
    from tau2.data_model.simulation import TextRunConfig

    llm_args_agent: dict[str, Any] = {"temperature": 0}
    if sage_guidance:
        llm_args_agent["sage_guidance"] = sage_guidance
    return TextRunConfig(
        domain=args.tau2_domain,
        agent=agent,
        user="user_simulator",
        llm_agent=args.model,
        llm_user=args.model,
        llm_args_agent=llm_args_agent,
        llm_args_user={"temperature": 0},
        max_steps=args.tau2_max_steps,
        timeout=args.tau2_timeout_sec,
        max_errors=10,
        max_retries=1,
        retry_delay=1.0,
        log_level="ERROR",
        hallucination_retries=0,
    )


def _run_one_tau2_task(
    *,
    args: argparse.Namespace,
    run_single_task: Any,
    task: Any,
    task_spec: dict[str, Any],
    agent: str,
    sage_guidance: str,
    seed: int,
    save_dir: Path,
    policy: str,
    visible_helpers: tuple[str, ...] = (),
) -> dict[str, Any]:
    try:
        simulation = run_single_task(
            _tau2_config(args, agent=agent, sage_guidance=sage_guidance),
            task,
            seed=seed,
            save_dir=save_dir,
            verbose_logs=False,
        )
    except Exception as exc:
        return {
            **task_spec,
            "policy": policy,
            "success": False,
            "score": 0.0,
            "outcome_score": 0.0,
            "transcript": [f"tau2 official runner error: {type(exc).__name__}: {exc}"],
            "visible_helpers": list(visible_helpers),
            "artifacts": {"exception_type": type(exc).__name__},
            "error": f"tau2_runner_error:{type(exc).__name__}",
        }
    return _tau2_result_json(
        task_spec=task_spec,
        simulation=simulation,
        policy=policy,
        visible_helpers=visible_helpers,
    )


def _run_terminal_bench(args: argparse.Namespace) -> None:
    from terminal_bench.dataset import Dataset

    run_dir = _run_dir(args)
    helper_path = run_dir / "sage_prompt_helpers.md"
    helper_path.write_text("", encoding="utf-8")
    _write_prompt_registry(run_dir, [])
    dataset_path = args.terminal_bench_repo / "original-tasks"
    dataset = Dataset(path=dataset_path)
    task_ids = (
        list(args.terminal_task_id)
        if args.terminal_task_id
        else sorted(dataset.task_ids)[: args.samples]
    )
    task_ids = task_ids[: args.samples]
    _write_manifest(
        run_dir,
        args,
        {
            "dataset": args.dataset,
            "official_harness": "terminal-bench",
            "dataset_path": str(dataset_path),
            "selected_task_ids": task_ids,
        },
    )

    baseline_results: list[dict[str, Any]] = []
    sage_events: list[dict[str, Any]] = []
    helper_guidance: list[str] = []
    dashboard_path = _write_live_dashboard(
        args=args,
        run_dir=run_dir,
        environment="terminal-bench",
        baseline_results=baseline_results,
        sage_events=sage_events,
        run_metadata={
            "status": "running",
            "official_harness": "terminal-bench",
            "comparison_valid": True,
            "selected_task_ids": task_ids,
        },
    )
    _open_dashboard(args, dashboard_path)

    try:
        for index, task_id in enumerate(task_ids, start=1):
            baseline_run_id = f"baseline_{_slug(task_id)}"
            sage_run_id = f"sage_{_slug(task_id)}"
            baseline_record = _run_one_terminal_task(
                args=args,
                run_dir=run_dir,
                task_id=task_id,
                run_id=baseline_run_id,
                agent_args=("--agent", "terminus"),
                policy=f"official_terminal_bench_terminus:{args.model}",
            )
            baseline_results.append(baseline_record)

            guidance_items, helper_names = _active_helpers(helper_guidance, args)
            helper_path.write_text("\n\n".join(guidance_items), encoding="utf-8")
            sage_record = _run_one_terminal_task(
                args=args,
                run_dir=run_dir,
                task_id=task_id,
                run_id=sage_run_id,
                agent_args=(
                    "--agent-import-path",
                    "sage_agent.terminal_bench_agent:SAGEGuidedTerminus",
                    "--agent-kwarg",
                    f"helper_path={helper_path}",
                ),
                policy=f"official_terminal_bench_sage_guided_terminus:{args.model}",
                visible_helpers=helper_names,
            )
            sage_events.append(_task_event_from_result(sage_record))

            if not sage_record["success"] and len(helper_guidance) < args.max_helpers:
                baseline_note = (
                    "The baseline agent succeeded on the same task."
                    if baseline_record.get("success")
                    else "The baseline agent also failed on the same task."
                )
                helper = _generate_prompt_helper(
                    args=args,
                    dataset="terminal-bench",
                    task_id=sage_record["task_id"],
                    transcript=sage_record.get("transcript", []),
                    failure_summary=(
                        str(sage_record.get("error", "Official harness unresolved."))
                        + " "
                        + baseline_note
                    ),
                )
                if helper:
                    helper_guidance.append(
                        f"### sage_prompt_helper_{len(helper_guidance) + 1}\n{helper}"
                    )
                    helper_path.write_text(
                        "\n\n".join(helper_guidance), encoding="utf-8"
                    )
                    _write_prompt_registry(run_dir, helper_guidance)
                    sage_events.append(
                        {
                            "event": "tool_birth",
                            "tool_name": f"sage_prompt_helper_{len(helper_guidance)}",
                            "accepted": True,
                            "errors": [],
                            "cases": 1,
                            "task_id": sage_record["task_id"],
                        }
                    )

            _write_live_dashboard(
                args=args,
                run_dir=run_dir,
                environment="terminal-bench",
                baseline_results=baseline_results,
                sage_events=sage_events,
                run_metadata={
                    "status": "running",
                    "official_harness": "terminal-bench",
                    "comparison_valid": True,
                    "completed": index,
                    "requested_samples": args.samples,
                    "selected_task_ids": task_ids,
                    "max_helpers": args.max_helpers,
                    "active_helpers": args.active_helpers,
                },
            )
    except KeyboardInterrupt:
        interrupted_dashboard = _write_live_dashboard(
            args=args,
            run_dir=run_dir,
            environment="terminal-bench",
            baseline_results=baseline_results,
            sage_events=sage_events,
            run_metadata={
                "status": "stopped_interrupted",
                "official_harness": "terminal-bench",
                "comparison_valid": True,
                "completed": len(
                    [
                        event
                        for event in sage_events
                        if event.get("event") == "task_result"
                    ]
                ),
                "requested_samples": args.samples,
                "selected_task_ids": task_ids,
                "helper_path": str(helper_path),
                "stopped_at": datetime.now(timezone.utc).isoformat(),
                "max_helpers": args.max_helpers,
                "active_helpers": args.active_helpers,
            },
        )
        _write_run_result(run_dir, baseline_results, sage_events, interrupted_dashboard)
        print(
            json.dumps(
                {
                    "run_dir": str(run_dir),
                    "dashboard_path": str(interrupted_dashboard),
                    "status": "stopped_interrupted",
                },
                indent=2,
            )
        )
        return

    final_dashboard = _write_live_dashboard(
        args=args,
        run_dir=run_dir,
        environment="terminal-bench",
        baseline_results=baseline_results,
        sage_events=sage_events,
        run_metadata={
            "status": "completed",
            "official_harness": "terminal-bench",
            "comparison_valid": True,
            "completed": len(task_ids),
            "requested_samples": args.samples,
            "selected_task_ids": task_ids,
            "helper_path": str(helper_path),
            "max_helpers": args.max_helpers,
            "active_helpers": args.active_helpers,
        },
    )
    _write_run_result(run_dir, baseline_results, sage_events, final_dashboard)
    print(
        json.dumps(
            {"run_dir": str(run_dir), "dashboard_path": str(final_dashboard)}, indent=2
        )
    )


def _run_one_terminal_task(
    *,
    args: argparse.Namespace,
    run_dir: Path,
    task_id: str,
    run_id: str,
    agent_args: tuple[str, ...],
    policy: str,
    visible_helpers: tuple[str, ...] = (),
) -> dict[str, Any]:
    output_path = run_dir / "terminal_bench_runs"
    dataset_path = args.terminal_bench_repo / "original-tasks"
    cmd = [
        sys.executable,
        "-m",
        "terminal_bench.cli.tb.main",
        "run",
        "--dataset-path",
        str(dataset_path),
        "--task-id",
        task_id,
        "--output-path",
        str(output_path),
        "--run-id",
        run_id,
        "--model",
        args.model,
        "--n-concurrent",
        "1",
        "--n-attempts",
        "1",
        "--global-agent-timeout-sec",
        str(args.terminal_agent_timeout_sec),
        "--global-test-timeout-sec",
        str(args.terminal_test_timeout_sec),
        *agent_args,
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = (
        f"{SRC}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else str(SRC)
    )
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=int(
                args.terminal_agent_timeout_sec + args.terminal_test_timeout_sec + 180
            ),
        )
    except subprocess.TimeoutExpired as exc:
        _stop_terminal_containers(run_id)
        timeout_log = (
            f"COMMAND: {' '.join(cmd)}\n\n"
            f"TIMEOUT: {exc.timeout}s\n\n"
            f"STDOUT:\n{(exc.stdout or '')[-4000:]}\n\n"
            f"STDERR:\n{(exc.stderr or '')[-4000:]}"
        )
        log_path = output_path / run_id / "subprocess_timeout.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(timeout_log, encoding="utf-8")
        task_spec = _task_spec(
            task_id=f"terminal-bench:{task_id}",
            name=f"Terminal-Bench {task_id}",
            prompt=f"Official Terminal-Bench task {task_id}",
            metadata={"source_task_id": task_id},
        )
        return {
            **task_spec,
            "policy": policy,
            "success": False,
            "score": 0.0,
            "outcome_score": 0.0,
            "transcript": [timeout_log[-4000:]],
            "visible_helpers": list(visible_helpers),
            "artifacts": {
                "subprocess_timeout_sec": exc.timeout,
                "log_path": str(log_path),
            },
            "error": f"terminal_bench_subprocess_timeout:{exc.timeout}s",
        }
    task_spec = _task_spec(
        task_id=f"terminal-bench:{task_id}",
        name=f"Terminal-Bench {task_id}",
        prompt=f"Official Terminal-Bench task {task_id}",
        metadata={"source_task_id": task_id},
    )
    result_path = output_path / run_id / "results.json"
    if not result_path.exists():
        log_path = output_path / run_id / "subprocess.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            f"COMMAND: {' '.join(cmd)}\n\nSTDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}",
            encoding="utf-8",
        )
        return {
            **task_spec,
            "policy": policy,
            "success": False,
            "score": 0.0,
            "outcome_score": 0.0,
            "transcript": [proc.stdout[-4000:], proc.stderr[-4000:]],
            "visible_helpers": list(visible_helpers),
            "artifacts": {
                "result_path": str(result_path),
                "subprocess_returncode": proc.returncode,
            },
            "error": f"terminal_bench_results_missing:returncode_{proc.returncode}",
        }
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    results = payload.get("results", [])
    trial = results[0] if results else {}
    success = bool(trial.get("is_resolved"))
    transcript = _terminal_transcript(output_path / run_id / task_id)
    return {
        **task_spec,
        "policy": policy,
        "success": success,
        "score": 1.0 if success else 0.0,
        "outcome_score": 1.0 if success else 0.0,
        "transcript": transcript or [f"Terminal-Bench resolved={success}"],
        "visible_helpers": list(visible_helpers),
        "artifacts": {
            "result_path": str(result_path),
            "failure_mode": str(trial.get("failure_mode", "")),
            "parser_results": trial.get("parser_results"),
            "total_input_tokens": trial.get("total_input_tokens"),
            "total_output_tokens": trial.get("total_output_tokens"),
        },
        "error": "" if success else str(trial.get("failure_mode", "unresolved")),
    }


def _stop_terminal_containers(run_id: str) -> None:
    try:
        output = subprocess.check_output(
            ["docker", "ps", "--format", "{{.Names}}"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return
    for name in output.splitlines():
        if run_id in name:
            subprocess.run(
                ["docker", "stop", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


def _active_helpers(
    helper_guidance: list[str], args: argparse.Namespace
) -> tuple[list[str], tuple[str, ...]]:
    active_count = max(0, int(args.active_helpers))
    if active_count == 0:
        return [], ()
    start = max(0, len(helper_guidance) - active_count)
    return (
        helper_guidance[start:],
        tuple(
            f"sage_prompt_helper_{index + 1}"
            for index in range(start, len(helper_guidance))
        ),
    )


def _run_scienceagentbench(args: argparse.Namespace) -> None:
    run_dir = _run_dir(args)
    benchmark = args.scienceagentbench_repo / "benchmark"
    required = ("datasets", "eval_programs", "gold_programs", "scoring_rubrics")
    missing = [name for name in required if not (benchmark / name).exists()]
    metadata = {
        "status": "blocked",
        "official_harness": "ScienceAgentBench",
        "comparison_valid": False,
        "blocked_reason": (
            "ScienceAgentBench GitHub clone contains only a benchmark placeholder. "
            "Official scoring requires the password-protected benchmark artifacts."
        ),
        "missing_artifacts": missing,
        "required_path": str(benchmark),
    }
    _write_manifest(run_dir, args, metadata)
    dashboard_path = _write_live_dashboard(
        args=args,
        run_dir=run_dir,
        environment="scienceagentbench",
        baseline_results=[],
        sage_events=[],
        run_metadata=metadata,
    )
    _open_dashboard(args, dashboard_path)
    print(
        json.dumps(
            {
                "run_dir": str(run_dir),
                "dashboard_path": str(dashboard_path),
                **metadata,
            },
            indent=2,
        )
    )


def _normalize_prompt_helper(guidance: str) -> str:
    lines = [line.strip() for line in guidance.splitlines() if line.strip()]
    normalized: list[str] = []
    for line in lines:
        line = re.sub(r"^\s*[-*]\s*", "- ", line)
        line = re.sub(r"^\s*\d+[.)]\s*", "- ", line)
        if not line.startswith("- "):
            line = f"- {line}"
        normalized.append(line[:220])
    return "\n".join(normalized[:4])


def _is_actionable_helper(guidance: str) -> bool:
    text = guidance.lower()
    if len(text.split()) < 12:
        return False
    actionable_terms = (
        "tool",
        "policy",
        "verify",
        "calculate",
        "total",
        "payment",
        "reservation",
        "refund",
        "cancel",
        "transfer",
        "test",
        "command",
        "file",
        "assert",
        "validate",
        "stop",
    )
    if not any(term in text for term in actionable_terms):
        return False
    generic_terms = (
        "friendly",
        "polite",
        "acknowledge",
        "empathy",
        "satisfaction",
        "helpful tone",
        "provide clear options",
        "maintain a",
    )
    if sum(term in text for term in generic_terms) >= 2:
        return False
    return True


def _generate_prompt_helper(
    *,
    args: argparse.Namespace,
    dataset: str,
    task_id: str,
    transcript: list[str],
    failure_summary: str,
) -> str:
    try:
        from openai import OpenAI
    except Exception:
        return ""
    client = OpenAI()
    prompt = {
        "dataset": dataset,
        "task_id": task_id,
        "failure_summary": failure_summary,
        "visible_transcript_excerpt": "\n".join(transcript)[-8000:],
        "requirements": (
            "Return one concise, reusable prompt helper for future tasks in this "
            "benchmark. Do not infer hidden labels, exact expected actions, or test "
            "answers. Focus only on concrete policy/tool preconditions, calculation "
            "checks, validation steps, and stop conditions visible in the transcript. "
            "Avoid tone, empathy, style, and generic customer-service advice. Use "
            "2-4 bullet lines and no more than 90 words."
        ),
    }
    try:
        response = client.chat.completions.create(
            model=args.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate safe SAGE prompt helpers from official "
                        "benchmark feedback. Respond as JSON with key 'guidance'. "
                        "The guidance must be specific enough to change tool use."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, indent=2)},
            ],
        )
        payload = json.loads(response.choices[0].message.content or "{}")
    except Exception:
        return ""
    guidance_value = payload.get("guidance", "")
    if isinstance(guidance_value, list):
        raw_guidance = "\n".join(str(item) for item in guidance_value)
    else:
        raw_guidance = str(guidance_value)
    guidance = _normalize_prompt_helper(raw_guidance.strip())
    if not _is_actionable_helper(guidance):
        return ""
    return guidance[:900]


def _write_live_dashboard(
    *,
    args: argparse.Namespace,
    run_dir: Path,
    environment: str,
    baseline_results: list[dict[str, Any]],
    sage_events: list[dict[str, Any]],
    run_metadata: dict[str, Any],
) -> Path:
    summary = _summary(
        environment=environment,
        model=args.model,
        run_dir=run_dir,
        events=sage_events,
    )
    baseline_successes = sum(1 for item in baseline_results if item.get("success"))
    baseline = {
        "policy": run_metadata.get("baseline_policy", f"official_control:{args.model}"),
        "comparison_valid": bool(run_metadata.get("comparison_valid", True)),
        "comparison_note": "Official benchmark harness/scorer output.",
        "tasks_seen": len(baseline_results),
        "tasks_succeeded": baseline_successes,
        "success_rate": baseline_successes / len(baseline_results)
        if baseline_results
        else 0.0,
        "results": baseline_results,
    }
    return write_standalone_dashboard(
        summary,
        run_dir,
        registry_path=run_dir / "sage_prompt_registry.json",
        baseline=baseline,
        run_metadata=run_metadata,
    )


def _summary(
    *, environment: str, model: str, run_dir: Path, events: list[dict[str, Any]]
) -> SAGERunSummary:
    task_events = [event for event in events if event.get("event") == "task_result"]
    tool_births = [event for event in events if event.get("event") == "tool_birth"]
    successes = sum(1 for event in task_events if event.get("success"))
    return SAGERunSummary(
        environment=environment,
        tasks_seen=len(task_events),
        tasks_succeeded=successes,
        gaps_observed=len(tool_births),
        tools_born=len(tool_births),
        tools_accepted=sum(1 for event in tool_births if event.get("accepted")),
        tools_rejected=sum(1 for event in tool_births if not event.get("accepted")),
        tools_reused=sum(
            len(event.get("visible_helpers", [])) for event in task_events
        ),
        repair_attempts=0,
        tools_refined=0,
        birth_task_retries=0,
        birth_task_retry_successes=0,
        model=model,
        registry_path=str(run_dir / "sage_prompt_registry.json"),
        integrity_passed=True,
        integrity_issues=0,
        lifecycle_decisions=(),
        events=tuple(events),
    )


def _task_event_from_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "event": "task_result",
        "task_id": result["task_id"],
        "task": {
            "task_id": result["task_id"],
            "name": result["name"],
            "prompt": result["prompt"],
            "artifacts": result.get("artifacts", {}),
            "metadata": result.get("metadata", {}),
        },
        "success": result["success"],
        "score": result["score"],
        "outcome_score": result["outcome_score"],
        "transcript": result.get("transcript", []),
        "tool_uses": [],
        "visible_helpers": result.get("visible_helpers", []),
        "artifacts": result.get("artifacts", {}),
        "error": result.get("error", ""),
    }


def _tau2_result_json(
    *,
    task_spec: dict[str, Any],
    simulation: Any,
    policy: str,
    visible_helpers: tuple[str, ...] = (),
) -> dict[str, Any]:
    reward = float(simulation.reward_info.reward if simulation.reward_info else 0.0)
    success = reward >= 1.0
    return {
        **task_spec,
        "policy": policy,
        "success": success,
        "score": reward,
        "outcome_score": reward,
        "transcript": _tau2_transcript(simulation),
        "visible_helpers": list(visible_helpers),
        "artifacts": {
            "simulation_id": simulation.id,
            "termination_reason": str(simulation.termination_reason),
            "duration": simulation.duration,
            "agent_cost": simulation.agent_cost,
            "user_cost": simulation.user_cost,
        },
        "error": "" if success else "tau2_reward_below_1",
    }


def _tau2_transcript(simulation: Any) -> list[str]:
    lines: list[str] = []
    for message in simulation.get_messages():
        role = str(getattr(message, "role", type(message).__name__))
        content = getattr(message, "content", None)
        if not content and getattr(message, "tool_calls", None):
            content = json.dumps(
                [call.model_dump(mode="json") for call in message.tool_calls],
                ensure_ascii=True,
            )
        if content:
            lines.append(f"{role}: {str(content)[:1200]}")
    return lines[-20:]


def _terminal_transcript(task_run_path: Path) -> list[str]:
    excerpts: list[str] = []
    if not task_run_path.exists():
        return excerpts
    for path in sorted(task_run_path.rglob("post_agent_pane.txt"))[:1]:
        excerpts.append(
            f"post_agent_pane:\n{path.read_text(encoding='utf-8', errors='replace')[-3000:]}"
        )
    for path in sorted(task_run_path.rglob("post_test_pane.txt"))[:1]:
        excerpts.append(
            f"post_test_pane:\n{path.read_text(encoding='utf-8', errors='replace')[-3000:]}"
        )
    return excerpts


def _task_spec(
    *, task_id: str, name: str, prompt: str, metadata: dict[str, Any]
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "name": name,
        "prompt": prompt,
        "artifacts": {},
        "metadata": metadata,
    }


def _run_dir(args: argparse.Namespace) -> Path:
    run_id = args.run_id or _default_run_id(args.dataset)
    run_dir = args.output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _default_run_id(dataset: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{_slug(dataset)}_official_live_{stamp}"


def _open_dashboard(args: argparse.Namespace, dashboard_path: Path) -> None:
    if args.no_dashboard_open:
        return
    url = open_standalone_dashboard(dashboard_path, port=args.dashboard_port)
    print(f"Dashboard opened: {url}", flush=True)


def _write_manifest(
    run_dir: Path, args: argparse.Namespace, metadata: dict[str, Any]
) -> None:
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "command": sys.argv,
        "model": args.model,
        "samples": args.samples,
        **metadata,
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def _write_run_result(
    run_dir: Path,
    baseline_results: list[dict[str, Any]],
    sage_events: list[dict[str, Any]],
    dashboard_path: Path,
) -> None:
    payload = {
        "baseline_results": baseline_results,
        "sage_events": sage_events,
        "dashboard_path": str(dashboard_path),
    }
    (run_dir / "official_live_results.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def _quiet_loguru() -> None:
    try:
        from loguru import logger

        logger.remove()
        logger.add(sys.stderr, level="WARNING")
    except Exception:
        return


def _install_interrupt_handler() -> None:
    def _raise_keyboard_interrupt(_signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt

    try:
        signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)
    except Exception:
        return


def _write_prompt_registry(run_dir: Path, helper_guidance: list[str]) -> None:
    tools: dict[str, Any] = {}
    for index, guidance in enumerate(helper_guidance, start=1):
        name = f"sage_prompt_helper_{index}"
        tools[name] = {
            "candidate": {
                "spec": {
                    "name": name,
                    "family": "official_harness_prompt_guidance",
                    "description": guidance,
                    "input_schema": {"official_feedback": "str"},
                    "output_schema": {"guidance": "str"},
                    "positive_triggers": ["official harness failure feedback"],
                    "negative_triggers": ["hidden labels", "hidden expected answers"],
                    "safety_notes": [
                        "generalize from visible feedback only",
                        "do not infer hidden benchmark labels",
                    ],
                },
                "metadata": {"source": "official_live_runner"},
            },
            "validation": {
                "accepted": True,
                "errors": [],
                "cases_run": 1,
                "cases_passed": 1,
                "runtime_smoke_passed": True,
                "side_effect_free": True,
            },
            "uses": 0,
            "successes": 0,
            "retired": False,
        }
    payload = {"schema_version": 1, "tools": tools}
    (run_dir / "sage_prompt_registry.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def _tau2_task_id(domain: str, task_id: str) -> str:
    return f"tau2:{domain}:{task_id}"


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")[:80]


if __name__ == "__main__":
    main()
