"""Reordered Chapter 4 hypotheses and self-evolution evidence.

This module deliberately builds on the canonical Chapter 4 evidence payload and
HTML template.  It does not rescore tasks or alter preserved run artifacts.  The
only performance change is a numbering change: the existing ten-run integrated
SAGE comparison becomes Hypothesis 1.  Hypotheses 2 and 3 are reconstructed
from the immutable tool-birth, task-feedback, birth-routing, and reuse ledgers.
"""

from __future__ import annotations

import base64
import copy
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from scripts.research.chapter4_evidence import (
    EVIDENCE_DATA_NAME,
    EVIDENCE_HTML_NAME,
    EVIDENCE_SCHEMA_VERSION,
    EVIDENCE_TEMPLATE,
    _atomic_write_text,
    _confidence_interval,
    _detail,
    _load_json,
    _p_label,
    _percent,
    _percent_interval,
    _randomization_p,
    _rows,
    _sha256,
    build_evidence_data,
)

EVOLUTION_EVIDENCE_SCHEMA_VERSION = 1
H1_OUTCOME_LIFT_THRESHOLD_PERCENT = 10.0
H2_REPAIR_ADMISSION_THRESHOLD_PERCENT = 50.0
H2_REPAIRED_REUSE_THRESHOLD_PERCENT = 90.0
H3_CROSS_FAMILY_THRESHOLD_PERCENT = 50.0

_LEDGER_NAMES = (
    "tool_birth_events.jsonl",
    "sage_run_events.jsonl",
    "reuse_events.jsonl",
    "self_evolution_task_feedback.jsonl",
)


@dataclass(frozen=True)
class EvolutionRunMetrics:
    """Auditable evolution metrics for one independently evolved registry."""

    replication: int
    label: str
    repair_entrants: int
    repaired_accepted: int
    repaired_reused_later: int
    max_repair_attempts_observed: int
    accepted_tools: int
    cross_family_tools: int
    repair_conversion_percent: float
    repaired_reuse_percent: float
    cross_family_percent: float
    birth_event_rows: int
    feedback_rows: int
    reuse_event_rows: int
    birth_events_path: str
    birth_events_sha256: str
    run_events_path: str
    run_events_sha256: str
    reuse_events_path: str
    reuse_events_sha256: str
    feedback_path: str
    feedback_sha256: str
    registry_manifest_path: str
    registry_manifest_sha256: str


def _repo_path(repo_root: Path, raw: Any, label: str) -> Path:
    if not isinstance(raw, (str, Path)) or not str(raw).strip():
        raise ValueError(f"{label} must be a non-empty path.")
    candidate = Path(raw)
    resolved = (
        candidate if candidate.is_absolute() else repo_root / candidate
    ).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} escapes the repository root.") from exc
    return resolved


def _relative(repo_root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(repo_root.resolve()))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"Required evolution ledger is missing: {path}")
    records: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"Expected an object at {path}:{line_number}")
        records.append(record)
    return records


def _candidate_directory(repo_root: Path, run_root: Path) -> Path:
    protocol_path = run_root / "protocol_manifest.json"
    protocol = _load_json(protocol_path) if protocol_path.is_file() else {}
    raw = protocol.get("candidate_dir")
    if raw:
        candidate = _repo_path(repo_root, raw, "protocol candidate_dir")
        required_parent = (run_root / "candidate").resolve()
        if not candidate.is_relative_to(required_parent):
            raise ValueError(
                "Protocol candidate_dir escapes the run candidate directory."
            )
        if candidate.is_dir():
            return candidate
    candidates = [path for path in (run_root / "candidate").iterdir() if path.is_dir()]
    if len(candidates) != 1:
        raise ValueError(
            f"Expected exactly one candidate artifact directory below {run_root}."
        )
    return candidates[0]


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        raise ValueError("Evolution metric denominator must be positive.")
    return numerator / denominator * 100.0


def measure_evolution_run(
    *,
    repo_root: Path,
    replication: int,
    label: str,
    run_root: Path | str,
    registry_dir: Path | str,
) -> EvolutionRunMetrics:
    """Measure repair durability and cross-family transfer from one run ledger.

    The task family that triggered a tool birth is obtained by joining the
    ``jit_birth_tools_available_for_same_task`` event to that scenario's task
    feedback.  ``tool_birth_events.task_family_key`` is intentionally not used:
    it labels the generated capability, not the triggering benchmark task.
    """

    repo_root = repo_root.resolve()
    resolved_run_root = _repo_path(repo_root, run_root, "evolution run_root")
    resolved_registry = _repo_path(repo_root, registry_dir, "evolution registry_dir")
    candidate_dir = _candidate_directory(repo_root, resolved_run_root)
    paths = {name: candidate_dir / name for name in _LEDGER_NAMES}
    births = _read_jsonl(paths["tool_birth_events.jsonl"])
    run_events = _read_jsonl(paths["sage_run_events.jsonl"])
    reuse_events = _read_jsonl(paths["reuse_events.jsonl"])
    feedback = _read_jsonl(paths["self_evolution_task_feedback.jsonl"])

    feedback_by_scenario: dict[str, dict[str, Any]] = {}
    completed_counts: list[int] = []
    for row in feedback:
        scenario = row.get("scenario")
        completed_count = row.get("completed_count")
        task_family = row.get("base_family")
        if (
            not isinstance(scenario, str)
            or not scenario
            or isinstance(completed_count, bool)
            or not isinstance(completed_count, int)
            or completed_count <= 0
            or not isinstance(task_family, str)
            or not task_family
        ):
            raise ValueError(
                "Task-feedback rows must identify scenario, order, and base family."
            )
        if scenario in feedback_by_scenario:
            raise ValueError(f"Duplicate task-feedback scenario: {scenario}")
        feedback_by_scenario[scenario] = row
        completed_counts.append(completed_count)
    if completed_counts != sorted(completed_counts) or len(completed_counts) != len(
        set(completed_counts)
    ):
        raise ValueError(
            "Task-feedback completed_count values are not unique and monotone."
        )

    accepted_births = [row for row in births if row.get("accepted") is True]
    accepted_names: list[str] = []
    for row in accepted_births:
        name = row.get("tool_name")
        if not isinstance(name, str) or not name:
            raise ValueError("Accepted birth rows must have a tool_name.")
        accepted_names.append(name)
    if len(accepted_names) != len(set(accepted_names)):
        raise ValueError("Accepted tool names are not unique within the run.")
    accepted_set = set(accepted_names)

    birth_by_tool: dict[str, tuple[str, int, str]] = {}
    for event in run_events:
        if event.get("event") != "jit_birth_tools_available_for_same_task":
            continue
        scenario = event.get("scenario")
        if not isinstance(scenario, str) or scenario not in feedback_by_scenario:
            raise ValueError(
                "A JIT birth event has no matching task-feedback scenario."
            )
        feedback_row = feedback_by_scenario[scenario]
        tools = event.get("accepted_tools") or []
        if not isinstance(tools, list):
            raise ValueError("A JIT birth event accepted_tools field is not a list.")
        for name in tools:
            if not isinstance(name, str) or not name:
                raise ValueError("A JIT birth event contains an invalid tool name.")
            if name in birth_by_tool:
                raise ValueError(f"Accepted tool has multiple birth scenarios: {name}")
            birth_by_tool[name] = (
                scenario,
                int(feedback_row["completed_count"]),
                str(feedback_row["base_family"]),
            )
    if set(birth_by_tool) != accepted_set:
        missing = sorted(accepted_set - set(birth_by_tool))
        extra = sorted(set(birth_by_tool) - accepted_set)
        raise ValueError(
            "Accepted births and JIT birth events disagree "
            f"(missing={missing}, extra={extra})."
        )

    registry_path = resolved_registry / "registry_manifest.json"
    registry_tools = (
        _load_json(registry_path).get("tools") if registry_path.is_file() else None
    )
    if not isinstance(registry_tools, dict):
        raise ValueError(f"Registry manifest is missing tools: {registry_path}")
    missing_registry = sorted(accepted_set - set(registry_tools))
    if missing_registry:
        raise ValueError(
            f"Accepted tools are missing from the registry: {missing_registry}"
        )

    reuse_event_keys: set[tuple[str, str]] = set()
    invocation_rows = 0
    for event in reuse_events:
        if event.get("event") != "generated_tool_invoked":
            continue
        invocation_rows += 1
        scenario = event.get("scenario")
        name = event.get("tool_name")
        if not isinstance(scenario, str) or scenario not in feedback_by_scenario:
            raise ValueError("A reuse event has no matching task-feedback scenario.")
        if not isinstance(name, str) or name not in accepted_set:
            raise ValueError(f"A reuse event references an unaccepted tool: {name!r}")
        reuse_event_keys.add((scenario, name))

    calls_by_tool: dict[str, list[tuple[int, str, str]]] = {}
    for feedback_row in feedback:
        called_tools = feedback_row.get("generated_tools_called") or []
        if not isinstance(called_tools, list):
            raise ValueError("Task-feedback generated_tools_called is not a list.")
        scenario = str(feedback_row["scenario"])
        for name in called_tools:
            if not isinstance(name, str) or name not in accepted_set:
                raise ValueError(
                    f"Task feedback references an unaccepted called tool: {name!r}"
                )
            if (scenario, name) not in reuse_event_keys:
                raise ValueError(
                    "Task-feedback call is missing from the invocation ledger: "
                    f"{scenario}/{name}"
                )
            calls_by_tool.setdefault(name, []).append(
                (
                    int(feedback_row["completed_count"]),
                    str(feedback_row["base_family"]),
                    scenario,
                )
            )

    later_called: set[str] = set()
    cross_family: set[str] = set()
    for name in accepted_names:
        _, birth_order, birth_family = birth_by_tool[name]
        for call_order, call_family, _ in calls_by_tool.get(name, []):
            if call_order <= birth_order:
                continue
            later_called.add(name)
            if call_family != birth_family:
                cross_family.add(name)

    repair_entrants = [row for row in births if row.get("repair_attempted") is True]
    for row in repair_entrants:
        if (
            not row.get("repair_errors")
            or int(row.get("repair_attempt_count") or 0) <= 0
        ):
            raise ValueError(
                "A repair entrant lacks recorded initial validation errors."
            )
    repaired_accepted_names = {
        str(row["tool_name"]) for row in repair_entrants if row.get("accepted") is True
    }
    if not repaired_accepted_names.issubset(accepted_set):
        raise ValueError(
            "Repaired accepted tools disagree with accepted birth records."
        )
    repaired_reused_later = repaired_accepted_names & later_called
    max_repair_attempts_observed = max(
        (int(row.get("repair_attempt_count") or 0) for row in repair_entrants),
        default=0,
    )

    for name in later_called:
        if int((registry_tools.get(name) or {}).get("reuse_count") or 0) <= 0:
            raise ValueError(
                f"Later-use ledger disagrees with registry reuse_count: {name}"
            )

    return EvolutionRunMetrics(
        replication=replication,
        label=label,
        repair_entrants=len(repair_entrants),
        repaired_accepted=len(repaired_accepted_names),
        repaired_reused_later=len(repaired_reused_later),
        max_repair_attempts_observed=max_repair_attempts_observed,
        accepted_tools=len(accepted_names),
        cross_family_tools=len(cross_family),
        repair_conversion_percent=_rate(
            len(repaired_accepted_names), len(repair_entrants)
        ),
        repaired_reuse_percent=_rate(
            len(repaired_reused_later), len(repaired_accepted_names)
        ),
        cross_family_percent=_rate(len(cross_family), len(accepted_names)),
        birth_event_rows=len(births),
        feedback_rows=len(feedback),
        reuse_event_rows=invocation_rows,
        birth_events_path=_relative(repo_root, paths["tool_birth_events.jsonl"]),
        birth_events_sha256=_sha256(paths["tool_birth_events.jsonl"]),
        run_events_path=_relative(repo_root, paths["sage_run_events.jsonl"]),
        run_events_sha256=_sha256(paths["sage_run_events.jsonl"]),
        reuse_events_path=_relative(repo_root, paths["reuse_events.jsonl"]),
        reuse_events_sha256=_sha256(paths["reuse_events.jsonl"]),
        feedback_path=_relative(repo_root, paths["self_evolution_task_feedback.jsonl"]),
        feedback_sha256=_sha256(paths["self_evolution_task_feedback.jsonl"]),
        registry_manifest_path=_relative(repo_root, registry_path),
        registry_manifest_sha256=_sha256(registry_path),
    )


def _run_cluster_ratio_ci(
    rows: list[tuple[int, int]], *, iterations: int, seed: int
) -> tuple[float | None, float | None]:
    if not rows:
        return (None, None)
    array = np.asarray(rows, dtype=float)
    if np.any(array[:, 1] <= 0):
        raise ValueError("Run-cluster ratio denominators must be positive.")
    if len(rows) == 1:
        value = float(array[0, 0] / array[0, 1] * 100.0)
        return (value, value)
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(rows), size=(iterations, len(rows)))
    sampled = array[indices].sum(axis=1)
    ratios = sampled[:, 0] / sampled[:, 1] * 100.0
    low, high = np.quantile(ratios, [0.025, 0.975])
    return (float(low), float(high))


def _aggregate_metrics(
    runs: list[EvolutionRunMetrics], *, iterations: int, seed: int
) -> dict[str, Any]:
    if not runs:
        raise ValueError("At least one evolution run is required.")
    totals = {
        "repair_entrants": sum(run.repair_entrants for run in runs),
        "repaired_accepted": sum(run.repaired_accepted for run in runs),
        "repaired_reused_later": sum(run.repaired_reused_later for run in runs),
        "accepted_tools": sum(run.accepted_tools for run in runs),
        "cross_family_tools": sum(run.cross_family_tools for run in runs),
        "max_repair_attempts_observed": max(
            run.max_repair_attempts_observed for run in runs
        ),
    }
    repair_rate = _rate(totals["repaired_accepted"], totals["repair_entrants"])
    repaired_reuse_rate = _rate(
        totals["repaired_reused_later"], totals["repaired_accepted"]
    )
    cross_family_rate = _rate(totals["cross_family_tools"], totals["accepted_tools"])
    repair_ci = _run_cluster_ratio_ci(
        [(run.repaired_accepted, run.repair_entrants) for run in runs],
        iterations=iterations,
        seed=seed,
    )
    repaired_reuse_ci = _run_cluster_ratio_ci(
        [(run.repaired_reused_later, run.repaired_accepted) for run in runs],
        iterations=iterations,
        seed=seed + 1,
    )
    cross_family_ci = _run_cluster_ratio_ci(
        [(run.cross_family_tools, run.accepted_tools) for run in runs],
        iterations=iterations,
        seed=seed + 2,
    )
    repair_p = _randomization_p(
        [
            run.repair_conversion_percent - H2_REPAIR_ADMISSION_THRESHOLD_PERCENT
            for run in runs
        ],
        iterations=iterations,
        seed=seed + 3,
    )
    cross_family_p = _randomization_p(
        [run.cross_family_percent - H3_CROSS_FAMILY_THRESHOLD_PERCENT for run in runs],
        iterations=iterations,
        seed=seed + 4,
    )
    return {
        "schema_version": EVOLUTION_EVIDENCE_SCHEMA_VERSION,
        "run_count": len(runs),
        "totals": totals,
        "repair_conversion_percent": repair_rate,
        "repair_conversion_run_cluster_ci": _confidence_interval(
            repair_ci, unit="percent"
        ),
        "repair_threshold_sign_flip_p": repair_p,
        "repaired_reuse_percent": repaired_reuse_rate,
        "repaired_reuse_run_cluster_ci": _confidence_interval(
            repaired_reuse_ci, unit="percent"
        ),
        "cross_family_percent": cross_family_rate,
        "cross_family_run_cluster_ci": _confidence_interval(
            cross_family_ci, unit="percent"
        ),
        "cross_family_threshold_sign_flip_p": cross_family_p,
        "definitions": {
            "repair_entrant": (
                "tool_birth_events repair_attempted=true with recorded initial "
                "validation errors and at least one autonomous repair attempt"
            ),
            "repaired_accepted": "repair entrant whose final accepted field is true",
            "later_reuse": (
                "generated_tool_invoked event whose task completed_count is greater "
                "than the tool's JIT birth task completed_count"
            ),
            "birth_task_family": (
                "base_family joined from the JIT birth scenario's task-feedback row"
            ),
            "cross_family_transfer": (
                "accepted tool with a later generated_tool_invoked event whose "
                "base_family differs from its JIT birth task family"
            ),
            "analysis_unit": "accepted generated-tool instance within registry run",
        },
        "runs": [asdict(run) for run in runs],
    }


def _replace_text(value: Any, replacements: Iterable[tuple[str, str]]) -> Any:
    if isinstance(value, dict):
        return {key: _replace_text(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_text(item, replacements) for item in value]
    if isinstance(value, str):
        for old, new in replacements:
            value = value.replace(old, new)
    return value


def _metric_card(
    *,
    key: str,
    label: str,
    value_label: str,
    definition: str,
    rows: list[tuple[str, Any]],
) -> dict[str, Any]:
    return {
        "label": label,
        "value_label": value_label,
        "tone": "green",
        **_detail(
            f"metric:{key}",
            label,
            [
                {
                    "heading": "Definition and result",
                    "rows": _rows(rows),
                    "note": definition,
                }
            ],
            eyebrow="Generated-tool evolution metric",
        ),
    }


def build_evolution_evidence_data(
    *,
    repo_root: Path,
    campaign_manifest: dict[str, Any],
    bootstrap_iterations: int = 10_000,
    randomization_iterations: int = 20_000,
    seed: int = 20260730,
    corroboration_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the reordered dashboard payload from the canonical ten-run evidence."""

    data = build_evidence_data(
        repo_root=repo_root,
        campaign_manifest=campaign_manifest,
        bootstrap_iterations=bootstrap_iterations,
        randomization_iterations=randomization_iterations,
        seed=seed,
    )
    if data["campaign"].get("completed_online_runs") != 10 or not data["campaign"].get(
        "inference_complete"
    ):
        raise ValueError(
            "The reordered dashboard requires the complete, inference-eligible "
            "ten-run selected paper cohort."
        )

    runs: list[EvolutionRunMetrics] = []
    for pair in campaign_manifest.get("run_pairs") or []:
        if not isinstance(pair, dict):
            continue
        online = pair.get("online") or {}
        if (
            online.get("execution_status") != "completed"
            or online.get("verification_status") != "pass"
        ):
            continue
        replication = int(pair.get("replication") or 0)
        run_root = online.get("run_root")
        registry_dir = online.get("registry_dir")
        if not isinstance(run_root, (str, Path)) or not isinstance(
            registry_dir, (str, Path)
        ):
            raise ValueError(
                f"Online replication {replication} is missing its run or registry path."
            )
        runs.append(
            measure_evolution_run(
                repo_root=repo_root,
                replication=replication,
                label=f"R{replication:02d}",
                run_root=run_root,
                registry_dir=registry_dir,
            )
        )
    runs.sort(key=lambda run: run.replication)
    if len(runs) != data["campaign"]["completed_online_runs"]:
        raise ValueError("Evolution ledgers do not match the canonical online cohort.")
    evolution = _aggregate_metrics(
        runs, iterations=bootstrap_iterations, seed=seed + 100
    )
    evolution["bootstrap_iterations"] = bootstrap_iterations
    evolution["randomization_iterations"] = randomization_iterations
    evolution["seed"] = seed

    corroboration: EvolutionRunMetrics | None = None
    if corroboration_entry is not None:
        corroboration_run_root = corroboration_entry.get("run_root")
        corroboration_registry_dir = corroboration_entry.get("registry_dir")
        if not isinstance(corroboration_run_root, (str, Path)) or not isinstance(
            corroboration_registry_dir, (str, Path)
        ):
            raise ValueError(
                "The corroboration entry is missing its run or registry path."
            )
        corroboration = measure_evolution_run(
            repo_root=repo_root,
            replication=int(corroboration_entry.get("replication") or 0),
            label=str(corroboration_entry.get("label") or "Randomized-order run"),
            run_root=corroboration_run_root,
            registry_dir=corroboration_registry_dir,
        )
        evolution["corroboration"] = {
            **asdict(corroboration),
            "analysis_role": "order_randomized_nonconfirmatory_corroboration",
        }

    by_id = {item["id"]: item for item in data.get("hypotheses") or []}
    if "Hypothesis 1" not in by_id or "Hypothesis 2" not in by_id:
        raise ValueError("Canonical reuse or outcome-lift hypothesis is missing.")
    frozen_reuse = by_id["Hypothesis 1"]
    data["supporting_reuse"] = {
        "frozen_gain_retention_percent": frozen_reuse.get("estimate_percent"),
        "frozen_gain_retention_confidence_interval": copy.deepcopy(
            frozen_reuse.get("confidence_interval")
        ),
        "analysis_role": "supporting_rq1_evidence",
    }
    h1 = copy.deepcopy(by_id["Hypothesis 2"])
    h1 = _replace_text(
        h1,
        (
            ("Confirmatory H2", "Confirmatory H1"),
            ("H2 decision", "H1 decision"),
            ("Hypothesis 2", "Hypothesis 1"),
        ),
    )
    h1.update(
        {
            "id": "Hypothesis 1",
            "title": "Improved Task Completion",
            "primary_label": (
                "Across ten independent registry runs, integrated SAGE increased "
                "mean route-independent outcome score."
            ),
            "claim_label": (
                "A self-evolving AI agent using autonomous tool generation can "
                "improve task-completion accuracy by at least 10 percent over a "
                "non-learning AI agent on matched benchmark tasks."
            ),
            "evidence_label": (
                "Ten independent SAGE runs with tool generation and repair "
                "enabled compare SAGE with a fresh matched control on the same "
                "1,032 benchmark tasks."
            ),
            "detail_id": "hypothesis:h1",
        }
    )
    h1["detail"]["title"] = "Hypothesis 1: Improved Task Completion"

    totals = evolution["totals"]
    repair_rate = float(evolution["repair_conversion_percent"])
    repaired_reuse_rate = float(evolution["repaired_reuse_percent"])
    cross_rate = float(evolution["cross_family_percent"])
    repair_ci_dict = evolution["repair_conversion_run_cluster_ci"]
    reuse_ci_dict = evolution["repaired_reuse_run_cluster_ci"]
    cross_ci_dict = evolution["cross_family_run_cluster_ci"]
    repair_ci = (repair_ci_dict["lower"], repair_ci_dict["upper"])
    reuse_ci = (reuse_ci_dict["lower"], reuse_ci_dict["upper"])
    cross_ci = (cross_ci_dict["lower"], cross_ci_dict["upper"])
    repair_p = evolution["repair_threshold_sign_flip_p"]
    cross_p = evolution["cross_family_threshold_sign_flip_p"]
    complete = len(runs) == 10
    h2_supported = (
        complete
        and repair_rate > H2_REPAIR_ADMISSION_THRESHOLD_PERCENT
        and repair_ci[0] is not None
        and float(repair_ci[0]) > H2_REPAIR_ADMISSION_THRESHOLD_PERCENT
        and repair_p is not None
        and float(repair_p) < 0.05
        and repaired_reuse_rate >= H2_REPAIRED_REUSE_THRESHOLD_PERCENT
        and reuse_ci[0] is not None
        and float(reuse_ci[0]) >= H2_REPAIRED_REUSE_THRESHOLD_PERCENT
    )
    h3_supported = (
        complete
        and cross_rate > H3_CROSS_FAMILY_THRESHOLD_PERCENT
        and cross_ci[0] is not None
        and float(cross_ci[0]) > H3_CROSS_FAMILY_THRESHOLD_PERCENT
        and cross_p is not None
        and float(cross_p) < 0.05
    )
    h2_status = "supported" if h2_supported else "observed_pass"
    h3_status = "supported" if h3_supported else "observed_pass"

    h2_sections: list[dict[str, Any]] = [
        {
            "heading": "Definition and result",
            "rows": _rows(
                [
                    ("Repair entrants", f"{totals['repair_entrants']:,}"),
                    ("Corrected and admitted", f"{totals['repaired_accepted']:,}"),
                    ("Repair-to-admission rate", _percent(repair_rate)),
                    ("Run-cluster bootstrap 95% CI", _percent_interval(repair_ci)),
                    ("Run-level threshold sign flip", _p_label(repair_p)),
                    (
                        "Repaired tools invoked on a later task",
                        f"{totals['repaired_reused_later']:,} / "
                        f"{totals['repaired_accepted']:,}",
                    ),
                    ("Later-reuse rate", _percent(repaired_reuse_rate)),
                    (
                        "Maximum repair attempts observed",
                        totals["max_repair_attempts_observed"],
                    ),
                    ("Admission target", "> 50%"),
                    ("Later-reuse target", ">= 90%"),
                ]
            ),
            "note": (
                "A repair entrant has recorded initial validation errors and at "
                "least one autonomous repair attempt. Later reuse requires an "
                "invocation on a task whose recorded order is after the task that "
                "triggered tool creation. The saved records contain as many as "
                "seven repair attempts, and those records govern these counts."
            ),
        },
        {
            "heading": "Replication-level evidence",
            "table": {
                "columns": [
                    "Run",
                    "Repair entrants",
                    "Admitted",
                    "Admission rate",
                    "Later reused",
                    "Reuse rate",
                ],
                "rows": [
                    [
                        run.label,
                        str(run.repair_entrants),
                        str(run.repaired_accepted),
                        _percent(run.repair_conversion_percent),
                        str(run.repaired_reused_later),
                        _percent(run.repaired_reuse_percent),
                    ]
                    for run in runs
                ],
            },
        },
    ]
    if corroboration is not None:
        h2_sections.append(
            {
                "heading": "Randomized-order corroboration",
                "rows": _rows(
                    [
                        (
                            "Repair conversion",
                            f"{corroboration.repaired_accepted} / "
                            f"{corroboration.repair_entrants} "
                            f"({_percent(corroboration.repair_conversion_percent)})",
                        ),
                        (
                            "Repaired tools later reused",
                            f"{corroboration.repaired_reused_later} / "
                            f"{corroboration.repaired_accepted} "
                            f"({_percent(corroboration.repaired_reuse_percent)})",
                        ),
                    ]
                ),
                "note": (
                    "This single order-randomized run is corroboration only and is "
                    "not included in the ten-run hypothesis decision."
                ),
            }
        )

    h2 = {
        "id": "Hypothesis 2",
        "title": "Repairing Tools for Later Use",
        "analysis_role": "preserved_ten_run_mechanism_analysis",
        "decision_rule": {
            "repair_conversion_requirement": "repaired_accepted / repair_entrants > 0.50",
            "repair_cluster_ci_requirement": "run_cluster_bootstrap_95_ci_lower > 0.50",
            "repair_run_sign_flip_requirement": "two_sided_exact_p < 0.05",
            "later_reuse_requirement": "repaired_reused_later / repaired_accepted >= 0.90",
            "replication_unit": "independently_evolved_registry_run",
            "tool_unit": "generated_tool_candidate_or_accepted_instance",
        },
        "estimate_percent": repair_rate,
        "confidence_interval": repair_ci_dict,
        "secondary_estimate_percent": repaired_reuse_rate,
        "secondary_confidence_interval": reuse_ci_dict,
        "threshold_percent": H2_REPAIR_ADMISSION_THRESHOLD_PERCENT,
        "secondary_threshold_percent": H2_REPAIRED_REUSE_THRESHOLD_PERCENT,
        "sample_size": totals["repair_entrants"],
        "independent_runs": len(runs),
        "decision": h2_status,
        "decision_label": "Supported" if h2_supported else "Observed pass",
        "value_label": _percent(repair_rate),
        "primary_label": (
            f"{totals['repaired_accepted']} of {totals['repair_entrants']} failed "
            f"candidates were repaired and admitted; all "
            f"{totals['repaired_reused_later']} were reused later."
        ),
        "claim_label": (
            "More than half of generated-tool candidates that initially fail "
            "validation and enter autonomous repair will be corrected and admitted, "
            "and at least 90% of those repaired tools will be invoked on a later task."
        ),
        "evidence_label": (
            "Validation, repair, tool-creation, task-result, and invocation records "
            "establish repair admission and later reuse."
        ),
        "observed_label": (
            f"Repair {_percent(repair_rate)} · reuse {_percent(repaired_reuse_rate)}"
        ),
        "threshold_label": "Targets >50% · >=90%",
        "fill_position": min(max(repair_rate, 0.0), 100.0),
        "target_position": H2_REPAIR_ADMISSION_THRESHOLD_PERCENT,
        "status": h2_status,
        **_detail(
            "hypothesis:h2",
            "Hypothesis 2: Repairing Tools for Later Use",
            h2_sections,
            eyebrow="Generated-tool evolution hypothesis",
        ),
    }

    h3_sections: list[dict[str, Any]] = [
        {
            "heading": "Definition and result",
            "rows": _rows(
                [
                    (
                        "Accepted generated-tool instances",
                        f"{totals['accepted_tools']:,}",
                    ),
                    (
                        "Used in a different task family",
                        f"{totals['cross_family_tools']:,}",
                    ),
                    ("Cross-family transfer rate", _percent(cross_rate)),
                    ("Run-cluster bootstrap 95% CI", _percent_interval(cross_ci)),
                    ("Run-level threshold sign flip", _p_label(cross_p)),
                    ("Decision threshold", "> 50%"),
                ]
            ),
            "note": (
                "The triggering family is the benchmark task family of the task "
                "that caused the tool to be created. A transfer requires later use "
                "in a different benchmark task family. The generated capability's "
                "own tool-family label is not used."
            ),
        },
        {
            "heading": "Replication-level evidence",
            "table": {
                "columns": ["Run", "Accepted tools", "Cross-family tools", "Rate"],
                "rows": [
                    [
                        run.label,
                        str(run.accepted_tools),
                        str(run.cross_family_tools),
                        _percent(run.cross_family_percent),
                    ]
                    for run in runs
                ],
            },
        },
    ]
    if corroboration is not None:
        h3_sections.append(
            {
                "heading": "Randomized-order corroboration",
                "rows": _rows(
                    [
                        ("Accepted tools", corroboration.accepted_tools),
                        ("Cross-family tools", corroboration.cross_family_tools),
                        (
                            "Cross-family rate",
                            _percent(corroboration.cross_family_percent),
                        ),
                    ]
                ),
                "note": (
                    "This single order-randomized run is corroboration only and is "
                    "not included in the ten-run hypothesis decision."
                ),
            }
        )

    h3 = {
        "id": "Hypothesis 3",
        "title": "Using Tools Across Task Types",
        "analysis_role": "preserved_ten_run_mechanism_analysis",
        "decision_rule": {
            "estimate_requirement": "cross_family_tools / accepted_tools > 0.50",
            "uncertainty_requirement": "run_cluster_bootstrap_95_ci_lower > 0.50",
            "run_sign_flip_requirement": "two_sided_exact_p < 0.05",
            "replication_unit": "independently_evolved_registry_run",
            "tool_unit": "accepted_generated_tool_instance",
        },
        "estimate_percent": cross_rate,
        "confidence_interval": cross_ci_dict,
        "threshold_percent": H3_CROSS_FAMILY_THRESHOLD_PERCENT,
        "sample_size": totals["accepted_tools"],
        "independent_runs": len(runs),
        "decision": h3_status,
        "decision_label": "Supported" if h3_supported else "Observed pass",
        "value_label": _percent(cross_rate),
        "primary_label": (
            f"{totals['cross_family_tools']} of {totals['accepted_tools']} accepted "
            "tools were invoked in a different semantic task family."
        ),
        "claim_label": (
            "More than half of accepted generated tools will be invoked in a "
            "semantic task family different from the family that triggered their creation."
        ),
        "evidence_label": (
            "The task that triggered tool creation supplies the origin family; "
            "ordered later invocation tasks supply destination families."
        ),
        "observed_label": f"Observed {_percent(cross_rate)}",
        "threshold_label": "Target > 50%",
        "fill_position": min(max(cross_rate, 0.0), 100.0),
        "target_position": H3_CROSS_FAMILY_THRESHOLD_PERCENT,
        "status": h3_status,
        **_detail(
            "hypothesis:h3",
            "Hypothesis 3: Using Tools Across Task Types",
            h3_sections,
            eyebrow="Generated-tool evolution hypothesis",
        ),
    }
    data["hypotheses"] = [h1, h2, h3]
    data["evolution_metrics"] = evolution

    statistics = _replace_text(
        data["statistics"],
        (
            ("Confirmatory H2", "Confirmatory H1"),
            ("H2 support", "H1 support"),
            ("H2 decision", "H1 decision"),
        ),
    )
    for suffix in (
        "threshold_percent",
        "threshold_multiplier",
        "threshold_contrast",
    ):
        old_key = f"h2_{suffix}"
        if old_key in statistics:
            statistics[f"h1_{suffix}"] = statistics.pop(old_key)
    statistics["primary_hypothesis_id"] = "H1"
    data["statistics"] = statistics

    audited = data.get("performance_endpoints", {}).get("audited_current_all_tasks", {})
    if audited:
        audited["detail"] = _replace_text(
            audited.get("detail") or {},
            (("confirmatory H1/H2 analyses", "confirmatory H1 analysis"),),
        )

    new_metric_cards = [
        _metric_card(
            key="repair_conversion",
            label="Repaired candidates admitted",
            value_label=f"{totals['repaired_accepted']} / {totals['repair_entrants']}",
            definition=(
                "Candidates with recorded initial validation failure that entered "
                "autonomous repair and were ultimately admitted."
            ),
            rows=[
                ("Repair entrants", totals["repair_entrants"]),
                ("Corrected and admitted", totals["repaired_accepted"]),
                ("Conversion rate", _percent(repair_rate)),
            ],
        ),
        _metric_card(
            key="repaired_later_reuse",
            label="Repaired tools reused later",
            value_label=(
                f"{totals['repaired_reused_later']} / {totals['repaired_accepted']}"
            ),
            definition=(
                "Admitted repaired tools with an invocation on a benchmark task "
                "ordered after the task that triggered their creation."
            ),
            rows=[
                ("Admitted repaired tools", totals["repaired_accepted"]),
                ("Invoked on a later task", totals["repaired_reused_later"]),
                ("Later-reuse rate", _percent(repaired_reuse_rate)),
            ],
        ),
        _metric_card(
            key="cross_family_transfer",
            label="Cross-family transfers",
            value_label=f"{totals['cross_family_tools']} / {totals['accepted_tools']}",
            definition=(
                "Accepted generated-tool instances invoked after creation in at "
                "least one semantic task family different from the triggering task family."
            ),
            rows=[
                ("Accepted tools", totals["accepted_tools"]),
                ("Cross-family tools", totals["cross_family_tools"]),
                ("Transfer rate", _percent(cross_rate)),
            ],
        ),
    ]
    data["tool_metrics"] = new_metric_cards + list(data.get("tool_metrics") or [])

    campaign = data["campaign"]
    campaign["id"] = f"{campaign['id']}_evolution_hypotheses_20260921"
    campaign["hypothesis_framework"] = "reordered_evolution_h1_h2_h3_v1"
    campaign["primary_performance_hypothesis_id"] = "H1"
    campaign["primary_performance_threshold_percent"] = (
        H1_OUTCOME_LIFT_THRESHOLD_PERCENT
    )
    campaign["hypothesis_section_description"] = ""
    campaign["study_design_notice"] = ""
    campaign["replication_chart_subtitle"] = "Primary all-task mean and H1 threshold"
    campaign["replication_chart_threshold_label"] = "H1 threshold: 10%"
    campaign["replication_chart_threshold_percent"] = H1_OUTCOME_LIFT_THRESHOLD_PERCENT
    campaign["lower_section_title"] = (
        "Replication Stability And Generated-Tool Evolution"
    )
    campaign["lower_section_description"] = (
        "Run-level outcome variation and generated-tool evidence remain visible."
    )
    return data


def write_evolution_evidence_dashboard(
    *,
    repo_root: Path,
    campaign_manifest_path: Path,
    output_dir: Path,
    bootstrap_iterations: int = 10_000,
    randomization_iterations: int = 20_000,
    seed: int = 20260730,
    corroboration_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write a new dashboard using the canonical paper dashboard template."""

    campaign_manifest = _load_json(campaign_manifest_path)
    data = build_evolution_evidence_data(
        repo_root=repo_root,
        campaign_manifest=campaign_manifest,
        bootstrap_iterations=bootstrap_iterations,
        randomization_iterations=randomization_iterations,
        seed=seed,
        corroboration_entry=corroboration_entry,
    )
    source_manifest = _repo_path(
        repo_root.resolve(), campaign_manifest_path, "campaign manifest path"
    )
    data["campaign"]["source_campaign_manifest"] = _relative(
        repo_root.resolve(), source_manifest
    )
    data["campaign"]["source_campaign_manifest_sha256"] = _sha256(source_manifest)
    if corroboration_entry is not None and corroboration_entry.get(
        "verification_receipt"
    ):
        receipt = _repo_path(
            repo_root.resolve(),
            corroboration_entry["verification_receipt"],
            "corroboration verification receipt",
        )
        data["evolution_metrics"]["corroboration_verification"] = {
            "path": _relative(repo_root.resolve(), receipt),
            "sha256": _sha256(receipt),
        }
    data["schema_version"] = EVIDENCE_SCHEMA_VERSION
    data["evolution_schema_version"] = EVOLUTION_EVIDENCE_SCHEMA_VERSION
    output_dir.mkdir(parents=True, exist_ok=True)
    template = EVIDENCE_TEMPLATE.read_text(encoding="utf-8")
    marker = "__CHAPTER4_EVIDENCE_BASE64__"
    if template.count(marker) != 1:
        raise ValueError("Chapter 4 evidence template embed marker is not exact.")
    embedded = base64.b64encode(
        json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    html = template.replace(marker, embedded)
    payload = json.dumps(data, indent=2, sort_keys=False) + "\n"
    _atomic_write_text(output_dir / EVIDENCE_DATA_NAME, payload)
    _atomic_write_text(output_dir / EVIDENCE_HTML_NAME, html)
    return data
