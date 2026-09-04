"""Outcome-only Chapter 4 campaign aggregation and hypothesis evidence.

The dashboard produced from this module is an evidence view over preserved run
artifacts. It does not alter or reevaluate either experimental arm. Canonical
similarity remains available in the source run artifacts but is intentionally
excluded from the paper-facing evidence payload.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np

EVIDENCE_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "dashboard"
    / "chapter4_evidence_template.html"
)
EVIDENCE_DATA_NAME = "chapter4_evidence_data.json"
EVIDENCE_HTML_NAME = "chapter4_evidence.html"
EVIDENCE_SCHEMA_VERSION = 3

H1_THRESHOLD_PERCENT = 80.0
H2_THRESHOLD_PERCENT = 10.0
H3_THRESHOLD_PERCENT = 30.0


@dataclass(frozen=True)
class RunEvidence:
    """Normalized evidence extracted from one completed or active run."""

    run_root: Path
    complete: bool
    completed_tasks: int
    scenario_count: int
    control_outcome: float | None
    candidate_outcome: float | None
    task_rows: tuple[dict[str, Any], ...]
    called_scenarios: frozenset[str]
    accepted_tools: int
    reuse_events: int
    generated_tool_called_scenarios: int
    generated_tool_failed_scenarios: int
    runtime_exceptions: int
    helper_side_effect_incidents: int
    helpers: dict[str, dict[str, Any]]
    registry_tools: dict[str, dict[str, Any]]
    protocol_manifest: dict[str, Any]
    dashboard_url: str


def _load_json(path: Path) -> dict[str, Any]:
    last_error: OSError | json.JSONDecodeError | None = None
    for attempt in range(5):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < 4:
                time.sleep(0.05 * (attempt + 1))
                continue
            raise
        if not isinstance(payload, dict):
            raise ValueError(f"Expected a JSON object in {path}")
        return payload
    raise RuntimeError(f"Unable to read JSON from {path}: {last_error!r}")


def _safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _mean(values: Iterable[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    if not valid:
        return None
    return float(np.mean(np.asarray(valid, dtype=float)))


def _relative_lift(candidate: float | None, control: float | None) -> float | None:
    if candidate is None or control in (None, 0.0):
        return None
    return (candidate - control) / control * 100.0


def _has_paired_outcome(row: dict[str, Any]) -> bool:
    """Return whether a row has a complete matched outcome comparison."""

    return bool(
        row.get("control_outcome") is not None
        and row.get("candidate_outcome") is not None
        and row.get("outcome_delta") is not None
    )


def _signed(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "-"
    return f"{value:+.{digits}f}"


def _percent(value: float | None, *, signed: bool = False) -> str:
    if value is None:
        return "-"
    prefix = "+" if signed and value > 0 else ""
    return f"{prefix}{value:.1f}%"


def _interval(values: tuple[float | None, float | None], digits: int = 3) -> str:
    low, high = values
    if low is None or high is None:
        return "-"
    return f"[{low:+.{digits}f}, {high:+.{digits}f}]"


def _percent_interval(
    values: tuple[float | None, float | None],
) -> str:
    low, high = values
    if low is None or high is None:
        return "-"
    return f"[{low:+.1f}%, {high:+.1f}%]"


def _confidence_interval(
    values: tuple[float | None, float | None],
    *,
    unit: str,
) -> dict[str, float | str | None]:
    return {
        "level": 0.95,
        "lower": values[0],
        "upper": values[1],
        "unit": unit,
    }


def _decision_label(status: str) -> str:
    return {
        "supported": "Supported",
        "observed_pass": "Observed pass",
        "not_supported": "Not supported",
        "pending": "Pending",
    }.get(status, status.replace("_", " ").title())


def _p_label(value: float | None) -> str:
    if value is None:
        return "-"
    if value < 0.001:
        return "p < .001"
    return f"p = {value:.3f}".replace("0.", ".")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_relative_url(repo_root: Path, path: Path) -> str:
    try:
        relative = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return ""
    return "/" + relative.as_posix()


def resolve_run_root(repo_root: Path, entry: dict[str, Any]) -> Path | None:
    """Resolve a manifest run entry to its active or completed protocol root."""

    explicit = str(entry.get("run_root") or "").strip()
    if explicit:
        path = (
            (repo_root / explicit).resolve()
            if not Path(explicit).is_absolute()
            else Path(explicit)
        )
        if path.exists():
            return path

    search_root_raw = str(entry.get("search_root") or "").strip()
    if not search_root_raw:
        return None
    search_root = (
        (repo_root / search_root_raw).resolve()
        if not Path(search_root_raw).is_absolute()
        else Path(search_root_raw)
    )
    if not search_root.exists():
        return None
    candidates = {
        path.parent.parent
        for path in search_root.rglob("dashboard/task_compare_data.json")
    }
    candidates.update(
        path.parent for path in search_root.rglob("paired_comparison.json")
    )
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda path: max(
            (
                child.stat().st_mtime
                for child in (
                    path / "paired_comparison.json",
                    path / "dashboard" / "task_compare_data.json",
                )
                if child.exists()
            ),
            default=0.0,
        ),
    )


def _load_registry_tools(
    repo_root: Path,
    entry: dict[str, Any],
    protocol_manifest: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    registry_raw = str(
        entry.get("registry_dir") or protocol_manifest.get("registry_dir") or ""
    ).strip()
    if not registry_raw:
        return {}
    registry_dir = (
        (repo_root / registry_raw).resolve()
        if not Path(registry_raw).is_absolute()
        else Path(registry_raw)
    )
    manifest_path = registry_dir / "registry_manifest.json"
    if not manifest_path.exists():
        return {}
    tools = _load_json(manifest_path).get("tools") or {}
    return tools if isinstance(tools, dict) else {}


def _side_effect_incident_count(helpers: dict[str, dict[str, Any]]) -> int:
    total = 0
    for payload in helpers.values():
        incidents = payload.get("side_effect_incidents")
        if isinstance(incidents, list):
            total += len(incidents)
        else:
            total += _safe_int(payload.get("side_effect_incident_count"))
    return total


def load_run_evidence(
    repo_root: Path,
    entry: dict[str, Any],
) -> RunEvidence | None:
    """Load one run without requiring it to be complete."""

    run_root = resolve_run_root(repo_root, entry)
    if run_root is None:
        return None
    dashboard_path = run_root / "dashboard" / "task_compare_data.json"
    paired_path = run_root / "paired_comparison.json"
    if not dashboard_path.exists() and not paired_path.exists():
        return None

    dashboard = _load_json(dashboard_path) if dashboard_path.exists() else {}
    summary = dashboard.get("summary") or {}
    paired = _load_json(paired_path) if paired_path.exists() else {}
    protocol_path = run_root / "protocol_manifest.json"
    protocol_manifest = _load_json(protocol_path) if protocol_path.exists() else {}
    helper_path = run_root / "helper_contribution_summary.json"
    helper_payload = _load_json(helper_path) if helper_path.exists() else {}
    helpers = helper_payload.get("helpers") or {}
    if not isinstance(helpers, dict):
        helpers = {}

    scenario_count = _safe_int(
        protocol_manifest.get("scenario_count")
        or paired.get("scenario_count")
        or summary.get("scenario_count")
    )
    completed_tasks = _safe_int(
        summary.get("balanced_completed") or paired.get("scenario_count")
    )
    complete = (
        paired_path.exists()
        and scenario_count > 0
        and completed_tasks >= scenario_count
    )

    task_rows: list[dict[str, Any]] = []
    for row in paired.get("deltas") or []:
        if not isinstance(row, dict):
            continue
        scenario = str(row.get("scenario") or "")
        task_rows.append(
            {
                "scenario": scenario,
                "control_outcome": _safe_float(row.get("control_outcome_similarity")),
                "candidate_outcome": _safe_float(
                    row.get("candidate_outcome_similarity")
                ),
                "outcome_delta": _safe_float(row.get("outcome_delta")),
            }
        )

    called_scenarios: set[str] = set()
    for pair in dashboard.get("pairs") or []:
        if not isinstance(pair, dict):
            continue
        candidate = pair.get("candidate") or {}
        generated = candidate.get("generated_tools") or []
        events = candidate.get("generated_tool_events") or []
        called = bool(generated) or any(
            isinstance(event, dict) and event.get("kind") == "called"
            for event in events
        )
        if called:
            called_scenarios.add(str(pair.get("scenario") or ""))

    registry_tools = _load_registry_tools(
        repo_root,
        entry,
        protocol_manifest,
    )
    control_outcome = _safe_float(
        summary.get("balanced_control_mean_outcome_similarity")
        if summary
        else paired.get("control_mean_outcome_similarity")
    )
    candidate_outcome = _safe_float(
        summary.get("balanced_candidate_mean_outcome_similarity")
        if summary
        else paired.get("candidate_mean_outcome_similarity")
    )
    dashboard_url = _repo_relative_url(
        repo_root,
        run_root / "dashboard" / "task_compare.html",
    )
    return RunEvidence(
        run_root=run_root,
        complete=complete,
        completed_tasks=completed_tasks,
        scenario_count=scenario_count,
        control_outcome=control_outcome,
        candidate_outcome=candidate_outcome,
        task_rows=tuple(task_rows),
        called_scenarios=frozenset(called_scenarios),
        accepted_tools=_safe_int(summary.get("accepted_tools") or len(registry_tools)),
        reuse_events=_safe_int(summary.get("reuse_count")),
        generated_tool_called_scenarios=_safe_int(
            summary.get("generated_tool_called_scenarios") or len(called_scenarios)
        ),
        generated_tool_failed_scenarios=_safe_int(
            summary.get("generated_tool_failed_scenarios")
        ),
        runtime_exceptions=_safe_int(
            summary.get("current_exceptions") or paired.get("runtime_exception_count")
        ),
        helper_side_effect_incidents=_side_effect_incident_count(helpers),
        helpers=helpers,
        registry_tools=registry_tools,
        protocol_manifest=protocol_manifest,
        dashboard_url=dashboard_url,
    )


def _bootstrap_mean_ci(
    values: list[float],
    *,
    iterations: int,
    seed: int,
) -> tuple[float | None, float | None]:
    if not values:
        return (None, None)
    array = np.asarray(values, dtype=float)
    if len(array) == 1:
        value = float(array[0])
        return (value, value)
    rng = np.random.default_rng(seed)
    batch_size = min(1000, iterations)
    means: list[np.ndarray] = []
    remaining = iterations
    while remaining:
        size = min(batch_size, remaining)
        indices = rng.integers(0, len(array), size=(size, len(array)))
        means.append(array[indices].mean(axis=1))
        remaining -= size
    samples = np.concatenate(means)
    low, high = np.quantile(samples, [0.025, 0.975])
    return (float(low), float(high))


def _bootstrap_retention_ci(
    rows: list[tuple[float, float, float]],
    *,
    iterations: int,
    seed: int,
) -> tuple[float | None, float | None]:
    """Bootstrap run-paired (baseline, online, frozen) retention ratios."""

    if not rows:
        return (None, None)
    array = np.asarray(rows, dtype=float)
    if len(array) == 1:
        denominator = array[0, 1] - array[0, 0]
        if denominator == 0:
            return (None, None)
        value = (array[0, 2] - array[0, 0]) / denominator * 100.0
        return (float(value), float(value))
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(array), size=(iterations, len(array)))
    sampled = array[indices].mean(axis=1)
    denominator = sampled[:, 1] - sampled[:, 0]
    valid = np.abs(denominator) > 1e-12
    ratios = (sampled[valid, 2] - sampled[valid, 0]) / denominator[valid] * 100.0
    if not len(ratios):
        return (None, None)
    low, high = np.quantile(ratios, [0.025, 0.975])
    return (float(low), float(high))


def _randomization_p(
    values: list[float],
    *,
    iterations: int,
    seed: int,
) -> float | None:
    """Two-sided paired sign-flip randomization test on mean differences."""

    if not values:
        return None
    array = np.asarray(values, dtype=float)
    observed = abs(float(array.mean()))
    if observed == 0:
        return 1.0
    if len(array) <= 20:
        masks = np.arange(1 << len(array), dtype=np.uint64)[:, None]
        bits = np.arange(len(array), dtype=np.uint64)[None, :]
        signs = ((masks >> bits) & 1).astype(np.int8) * 2 - 1
        permuted = np.abs((signs * array).mean(axis=1))
        return float(np.mean(permuted >= observed - 1e-15))

    rng = np.random.default_rng(seed)
    extreme = 0
    processed = 0
    batch_size = min(512, iterations)
    while processed < iterations:
        size = min(batch_size, iterations - processed)
        signs = rng.integers(0, 2, size=(size, len(array)), dtype=np.int8)
        signs = signs * 2 - 1
        permuted = np.abs((signs * array).mean(axis=1))
        extreme += int(np.count_nonzero(permuted >= observed - 1e-15))
        processed += size
    return (extreme + 1) / (iterations + 1)


def _hypothesis_status(
    *,
    value: float | None,
    threshold: float,
    ci: tuple[float | None, float | None],
    complete: bool,
) -> str:
    if value is None or not complete:
        return "pending"
    low, _ = ci
    if low is not None and low >= threshold:
        return "supported"
    if value >= threshold:
        return "observed_pass"
    return "not_supported"


def _detail(
    detail_id: str,
    title: str,
    sections: list[dict[str, Any]],
    *,
    eyebrow: str = "Evidence detail",
) -> dict[str, Any]:
    return {
        "detail_id": detail_id,
        "detail": {
            "eyebrow": eyebrow,
            "title": title,
            "sections": sections,
        },
    }


def _rows(items: Iterable[tuple[str, Any]]) -> list[dict[str, str]]:
    return [
        {"label": label, "value": "-" if value is None else str(value)}
        for label, value in items
    ]


def _paper_claim_safeguards(raw: Any) -> dict[str, Any]:
    """Keep operational safeguards while excluding non-outcome metric policy."""

    if not isinstance(raw, dict):
        return {}
    return {
        str(key): value
        for key, value in raw.items()
        if not str(key).startswith("canonical")
    }


def _tool_records(
    online_runs: list[tuple[int, RunEvidence]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    aggregate: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "accepted_runs": set(),
            "calls": 0,
            "later_calls": 0,
            "gains": 0,
            "regressions": 0,
            "preserved": 0,
            "weighted_delta": 0.0,
            "delta_weight": 0,
            "failures": 0,
            "side_effect_incidents": 0,
            "code_hashes": set(),
            "validation_passes": 0,
        }
    )
    accepted_total = 0
    reused_tool_total = 0
    reuse_events = 0
    natural_calls = 0
    gains = 0
    regressions = 0
    preserved = 0
    runtime_failures = 0

    for replicate, run in online_runs:
        accepted_total += run.accepted_tools
        reuse_events += run.reuse_events
        natural_calls += run.generated_tool_called_scenarios
        runtime_failures += run.generated_tool_failed_scenarios
        for name, registry_entry in run.registry_tools.items():
            if not isinstance(registry_entry, dict) or registry_entry.get("retired"):
                continue
            record = aggregate[name]
            record["accepted_runs"].add(replicate)
            reuse_count = _safe_int(registry_entry.get("reuse_count"))
            record["later_calls"] += reuse_count
            if reuse_count > 0:
                reused_tool_total += 1
            code_hash = str(registry_entry.get("code_hash") or "")
            if code_hash:
                record["code_hashes"].add(code_hash)
            validation = registry_entry.get("validation") or {}
            if validation.get("accepted"):
                record["validation_passes"] += 1

        for name, helper in run.helpers.items():
            if not isinstance(helper, dict):
                continue
            record = aggregate[name]
            called_count = _safe_int(helper.get("called_count"))
            subset = helper.get("called_subset") or {}
            tool_gains = _safe_int(subset.get("outcome_gains"))
            tool_regressions = _safe_int(subset.get("outcome_regressions"))
            tool_preserved = _safe_int(subset.get("outcome_preserved"))
            mean_delta = _safe_float(subset.get("mean_outcome_delta"))
            record["calls"] += called_count
            record["gains"] += tool_gains
            record["regressions"] += tool_regressions
            record["preserved"] += tool_preserved
            record["failures"] += _safe_int(helper.get("failed_attempt_count"))
            incidents = helper.get("side_effect_incidents")
            record["side_effect_incidents"] += (
                len(incidents)
                if isinstance(incidents, list)
                else _safe_int(helper.get("side_effect_incident_count"))
            )
            if mean_delta is not None and called_count:
                record["weighted_delta"] += mean_delta * called_count
                record["delta_weight"] += called_count
            gains += tool_gains
            regressions += tool_regressions
            preserved += tool_preserved

    tools: list[dict[str, Any]] = []
    for name, record in aggregate.items():
        if not record["accepted_runs"] and not record["calls"]:
            continue
        mean_delta = (
            record["weighted_delta"] / record["delta_weight"]
            if record["delta_weight"]
            else 0.0
        )
        detail_id = f"tool:{name}"
        tool = {
            "name": name,
            "calls": record["calls"],
            "later_calls": record["later_calls"],
            "gains": record["gains"],
            "regressions": record["regressions"],
            "preserved": record["preserved"],
            "failures": record["failures"],
            "mean_outcome_delta": mean_delta,
            "mean_outcome_delta_label": _signed(mean_delta),
            **_detail(
                detail_id,
                name,
                [
                    {
                        "heading": "Contribution",
                        "rows": _rows(
                            [
                                ("Natural calls", record["calls"]),
                                ("Later-task reuse events", record["later_calls"]),
                                ("Outcome gains", record["gains"]),
                                ("Outcome regressions", record["regressions"]),
                                ("Outcomes preserved", record["preserved"]),
                                ("Mean called-task outcome delta", _signed(mean_delta)),
                            ]
                        ),
                    },
                    {
                        "heading": "Generation and validation provenance",
                        "rows": _rows(
                            [
                                (
                                    "Accepted in replications",
                                    ", ".join(
                                        f"R{value:02d}"
                                        for value in sorted(record["accepted_runs"])
                                    )
                                    or "-",
                                ),
                                ("Validation passes", record["validation_passes"]),
                                ("Distinct code hashes", len(record["code_hashes"])),
                                (
                                    "Code hash prefixes",
                                    ", ".join(
                                        value[:12]
                                        for value in sorted(record["code_hashes"])
                                    )
                                    or "-",
                                ),
                                ("Runtime failures", record["failures"]),
                                (
                                    "Side-effect incidents",
                                    record["side_effect_incidents"],
                                ),
                            ]
                        ),
                        "note": (
                            "Distinct hashes preserve evidence that model-authored "
                            "tool code can vary across independent online-build runs."
                        ),
                    },
                ],
                eyebrow="Generated tool",
            ),
        }
        tools.append(tool)
    tools.sort(
        key=lambda item: (
            item["mean_outcome_delta"] * max(item["calls"], 1),
            item["calls"],
        ),
        reverse=True,
    )
    totals = {
        "accepted": accepted_total,
        "reused_tools": reused_tool_total,
        "reuse_events": reuse_events,
        "natural_calls": natural_calls,
        "gains": gains,
        "regressions": regressions,
        "preserved": preserved,
        "runtime_failures": runtime_failures,
    }
    return tools, totals


def _run_detail(
    *,
    replicate: int,
    online: RunEvidence | None,
    frozen: RunEvidence | None,
) -> dict[str, Any]:
    protocol = online.protocol_manifest if online else {}
    env = protocol.get("run_affecting_sage_env") or {}
    native_action_enabled = protocol.get("native_action_tools_enabled") is True
    scenario_name_birth_enabled = protocol.get("scenario_name_birth_enabled")
    scenario_name_routing_enabled = protocol.get("scenario_name_routing_enabled")
    if scenario_name_birth_enabled is None:
        scenario_name_birth_enabled = env.get("SAGE_DISABLE_SCENARIO_NAME_BIRTH") != "1"
    if scenario_name_routing_enabled is None:
        scenario_name_routing_enabled = (
            env.get("SAGE_DISABLE_SCENARIO_NAME_ROUTING") != "1"
        )
    online_lift = (
        _relative_lift(online.candidate_outcome, online.control_outcome)
        if online
        else None
    )
    retention = None
    if (
        online
        and frozen
        and online.control_outcome is not None
        and online.candidate_outcome is not None
        and frozen.candidate_outcome is not None
        and online.candidate_outcome != online.control_outcome
    ):
        retention = (
            (frozen.candidate_outcome - online.control_outcome)
            / (online.candidate_outcome - online.control_outcome)
            * 100.0
        )
    status_label = (
        "Online + frozen complete"
        if online and online.complete and frozen and frozen.complete
        else "Online complete"
        if online and online.complete
        else "Running"
        if online or frozen
        else "Queued"
    )
    sections = [
        {
            "heading": "Replication metrics",
            "rows": _rows(
                [
                    (
                        "Online-build task completion",
                        f"{online.completed_tasks}/{online.scenario_count}"
                        if online
                        else "not started",
                    ),
                    (
                        "Baseline outcome",
                        f"{online.control_outcome:.3f}"
                        if online and online.control_outcome is not None
                        else "-",
                    ),
                    (
                        "Online-build SAGE outcome",
                        f"{online.candidate_outcome:.3f}"
                        if online and online.candidate_outcome is not None
                        else "-",
                    ),
                    ("Online-build outcome lift", _percent(online_lift, signed=True)),
                    (
                        "Frozen-registry SAGE outcome",
                        f"{frozen.candidate_outcome:.3f}"
                        if frozen and frozen.candidate_outcome is not None
                        else "-",
                    ),
                    ("Frozen gain retention", _percent(retention)),
                ]
            ),
        },
        {
            "heading": "Tool lifecycle",
            "rows": _rows(
                [
                    ("Accepted tools", online.accepted_tools if online else "-"),
                    ("Reuse events", online.reuse_events if online else "-"),
                    (
                        "Generated-tool-called tasks",
                        online.generated_tool_called_scenarios if online else "-",
                    ),
                    (
                        "Generated-tool failure scenarios",
                        online.generated_tool_failed_scenarios if online else "-",
                    ),
                    (
                        "Runtime exceptions",
                        online.runtime_exceptions if online else "-",
                    ),
                ]
            ),
        },
        {
            "heading": "Run configuration",
            "rows": _rows(
                [
                    ("Actor model", protocol.get("agent") or "-"),
                    ("User model", protocol.get("user") or "-"),
                    (
                        "Generation model",
                        protocol.get("generation_model") or "-",
                    ),
                    (
                        "Generation enabled",
                        (
                            "enabled"
                            if protocol.get("generation_enabled")
                            else "disabled"
                        )
                        if protocol
                        else "-",
                    ),
                    (
                        "Complete/native-action tools",
                        "enabled" if native_action_enabled else "disabled",
                    ),
                    (
                        "Synthetic bridge completions",
                        (
                            "enabled"
                            if protocol.get(
                                "synthetic_bridge_completions_enabled", False
                            )
                            else "disabled"
                        ),
                    ),
                    (
                        "Scenario-name birth/routing",
                        (
                            "disabled / disabled"
                            if not scenario_name_birth_enabled
                            and not scenario_name_routing_enabled
                            else "review required"
                        ),
                    ),
                    (
                        "Control cache",
                        (
                            f"{protocol.get('control_cache_mode')}: "
                            f"{protocol.get('cached_control_tasks')} cached / "
                            f"{protocol.get('fresh_control_tasks')} fresh"
                        )
                        if protocol
                        else "-",
                    ),
                ]
            ),
        },
    ]
    links: list[dict[str, str]] = []
    if online and online.dashboard_url:
        links.append(
            {"label": "Open online-build Task Compare", "href": online.dashboard_url}
        )
    if frozen and frozen.dashboard_url:
        links.append(
            {
                "label": "Open frozen-registry Task Compare",
                "href": frozen.dashboard_url,
            }
        )
    if links:
        sections.append({"heading": "Run dashboards", "links": links})
    return {
        "replication": replicate,
        "label": f"Replication {replicate:02d}",
        "short_label": f"R{replicate}",
        "status_label": status_label,
        "dashboard_url": online.dashboard_url if online else "",
        "baseline_outcome": online.control_outcome if online else None,
        "online_sage_outcome": online.candidate_outcome if online else None,
        "frozen_sage_outcome": frozen.candidate_outcome if frozen else None,
        "online_outcome_lift_percent": online_lift,
        "frozen_gain_retention_percent": retention,
        **_detail(
            f"run:{replicate}",
            f"Replication {replicate:02d}",
            sections,
            eyebrow="Full-dataset replication",
        ),
    }


def build_evidence_data(
    *,
    repo_root: Path,
    campaign_manifest: dict[str, Any],
    bootstrap_iterations: int = 10_000,
    randomization_iterations: int = 20_000,
    seed: int = 20260730,
) -> dict[str, Any]:
    """Build the complete JSON payload consumed by the evidence dashboard."""

    pair_entries = campaign_manifest.get("run_pairs") or []
    expected_online_raw = campaign_manifest.get("expected_online_runs")
    expected_frozen_raw = campaign_manifest.get("expected_frozen_runs")
    expected_online = _safe_int(
        len(pair_entries) if expected_online_raw is None else expected_online_raw
    )
    expected_frozen = _safe_int(
        len(pair_entries) if expected_frozen_raw is None else expected_frozen_raw
    )
    statistical_plan = campaign_manifest.get("statistical_plan") or {}
    h1_threshold = _safe_float(statistical_plan.get("hypothesis_1_threshold_percent"))
    h2_threshold = _safe_float(statistical_plan.get("hypothesis_2_threshold_percent"))
    h3_threshold = _safe_float(statistical_plan.get("hypothesis_3_threshold_percent"))
    h1_threshold = H1_THRESHOLD_PERCENT if h1_threshold is None else h1_threshold
    h2_threshold = H2_THRESHOLD_PERCENT if h2_threshold is None else h2_threshold
    h3_threshold = H3_THRESHOLD_PERCENT if h3_threshold is None else h3_threshold

    loaded_pairs: list[tuple[int, RunEvidence | None, RunEvidence | None]] = []
    for entry in pair_entries:
        if not isinstance(entry, dict):
            continue
        replicate = _safe_int(entry.get("replication"))
        online_entry = entry.get("online") or {}
        frozen_entry = entry.get("frozen") or {}
        online = (
            load_run_evidence(repo_root, online_entry)
            if isinstance(online_entry, dict)
            else None
        )
        frozen = (
            load_run_evidence(repo_root, frozen_entry)
            if isinstance(frozen_entry, dict)
            else None
        )
        loaded_pairs.append((replicate, online, frozen))

    completed_online = [
        (replicate, run)
        for replicate, run, _ in loaded_pairs
        if run is not None and run.complete
    ]
    completed_frozen = [
        (replicate, run)
        for replicate, _, run in loaded_pairs
        if run is not None and run.complete
    ]
    completed_frozen_by_rep = dict(completed_frozen)
    online_complete = len(completed_online) >= expected_online
    frozen_complete = len(completed_frozen) >= expected_frozen

    online_task_rows = [row for _, run in completed_online for row in run.task_rows]
    frozen_task_rows = [row for _, run in completed_frozen for row in run.task_rows]
    online_outcome_rows = [row for row in online_task_rows if _has_paired_outcome(row)]
    frozen_outcome_rows = [row for row in frozen_task_rows if _has_paired_outcome(row)]
    control_outcomes = [row["control_outcome"] for row in online_outcome_rows]
    candidate_outcomes = [row["candidate_outcome"] for row in online_outcome_rows]
    outcome_deltas = [row["outcome_delta"] for row in online_outcome_rows]
    baseline_outcome = _mean(control_outcomes)
    sage_outcome = _mean(candidate_outcomes)
    frozen_sage_outcome = _mean(run.candidate_outcome for _, run in completed_frozen)
    overall_outcome_delta = (
        sage_outcome - baseline_outcome
        if sage_outcome is not None and baseline_outcome is not None
        else None
    )
    overall_outcome_lift = _relative_lift(sage_outcome, baseline_outcome)

    expected_outcomes_per_run = _safe_int(
        statistical_plan.get("outcome_scored_tasks_per_run")
    )
    expected_online_outcomes = _safe_int(
        statistical_plan.get("expected_outcome_scored_pairs")
    )
    if expected_online_outcomes <= 0:
        expected_online_outcomes = (
            expected_online * expected_outcomes_per_run
            if expected_outcomes_per_run > 0
            else sum(run.scenario_count for _, run in completed_online)
        )
    expected_frozen_outcomes = (
        expected_frozen * expected_outcomes_per_run
        if expected_outcomes_per_run > 0
        else sum(run.scenario_count for _, run in completed_frozen)
    )
    observed_online_outcomes = len(online_outcome_rows)
    observed_frozen_outcomes = len(frozen_outcome_rows)
    online_outcomes_complete = (
        online_complete and observed_online_outcomes == expected_online_outcomes
    )
    frozen_outcomes_complete = (
        frozen_complete and observed_frozen_outcomes == expected_frozen_outcomes
    )

    task_ci = _bootstrap_mean_ci(
        outcome_deltas,
        iterations=bootstrap_iterations,
        seed=seed,
    )
    online_run_mean_deltas: list[float] = []
    for _, run in completed_online:
        run_deltas = [
            row["outcome_delta"] for row in run.task_rows if _has_paired_outcome(row)
        ]
        if run_deltas:
            online_run_mean_deltas.append(float(np.mean(run_deltas)))
    run_cluster_ci = _bootstrap_mean_ci(
        online_run_mean_deltas,
        iterations=bootstrap_iterations,
        seed=seed + 1,
    )
    task_p = _randomization_p(
        outcome_deltas,
        iterations=randomization_iterations,
        seed=seed + 2,
    )
    run_p = _randomization_p(
        online_run_mean_deltas,
        iterations=randomization_iterations,
        seed=seed + 3,
    )

    called_rows: list[dict[str, Any]] = []
    for _, run in completed_online:
        called_rows.extend(
            row
            for row in run.task_rows
            if row["scenario"] in run.called_scenarios
            and row["control_outcome"] is not None
            and row["candidate_outcome"] is not None
            and row["outcome_delta"] is not None
        )
    called_control = _mean(
        row["control_outcome"]
        for row in called_rows
        if row["control_outcome"] is not None
    )
    called_sage = _mean(
        row["candidate_outcome"]
        for row in called_rows
        if row["candidate_outcome"] is not None
    )
    called_lift = _relative_lift(called_sage, called_control)
    called_deltas = [
        row["outcome_delta"] for row in called_rows if row["outcome_delta"] is not None
    ]
    called_unique_gains = sum(delta > 1e-12 for delta in called_deltas)
    called_unique_regressions = sum(delta < -1e-12 for delta in called_deltas)
    called_unique_preserved = (
        len(called_deltas) - called_unique_gains - called_unique_regressions
    )
    called_delta_ci = _bootstrap_mean_ci(
        called_deltas,
        iterations=bootstrap_iterations,
        seed=seed + 4,
    )
    called_lift_samples: list[float] = []
    if called_rows:
        rng = np.random.default_rng(seed + 5)
        control_array = np.asarray(
            [float(row["control_outcome"]) for row in called_rows],
            dtype=float,
        )
        candidate_array = np.asarray(
            [float(row["candidate_outcome"]) for row in called_rows],
            dtype=float,
        )
        for _ in range(bootstrap_iterations):
            indices = rng.integers(0, len(called_rows), size=len(called_rows))
            control_mean = float(control_array[indices].mean())
            if control_mean == 0:
                continue
            candidate_mean = float(candidate_array[indices].mean())
            called_lift_samples.append(
                (candidate_mean - control_mean) / control_mean * 100.0
            )
    called_lift_ci = (
        tuple(
            float(value) for value in np.quantile(called_lift_samples, [0.025, 0.975])
        )
        if called_lift_samples
        else (None, None)
    )

    retention_rows: list[tuple[float, float, float]] = []
    per_rep_retention: list[tuple[int, float]] = []
    for replicate, online in completed_online:
        frozen = completed_frozen_by_rep.get(replicate)
        if (
            frozen is None
            or online.control_outcome is None
            or online.candidate_outcome is None
            or frozen.candidate_outcome is None
        ):
            continue
        retention_rows.append(
            (
                online.control_outcome,
                online.candidate_outcome,
                frozen.candidate_outcome,
            )
        )
        denominator = online.candidate_outcome - online.control_outcome
        if denominator:
            per_rep_retention.append(
                (
                    replicate,
                    (frozen.candidate_outcome - online.control_outcome)
                    / denominator
                    * 100.0,
                )
            )
    retention = None
    if retention_rows:
        retention_array = np.asarray(retention_rows, dtype=float).mean(axis=0)
        denominator = retention_array[1] - retention_array[0]
        if denominator:
            retention = (retention_array[2] - retention_array[0]) / denominator * 100.0
    retention_ci = _bootstrap_retention_ci(
        retention_rows,
        iterations=bootstrap_iterations,
        seed=seed + 6,
    )

    h1_status = _hypothesis_status(
        value=retention,
        threshold=h1_threshold,
        ci=retention_ci,
        complete=online_outcomes_complete and frozen_outcomes_complete,
    )
    h2_lift_ci = (
        (task_ci[0] / baseline_outcome * 100.0)
        if task_ci[0] is not None and baseline_outcome not in (None, 0.0)
        else None,
        (task_ci[1] / baseline_outcome * 100.0)
        if task_ci[1] is not None and baseline_outcome not in (None, 0.0)
        else None,
    )
    h2_status = _hypothesis_status(
        value=overall_outcome_lift,
        threshold=h2_threshold,
        ci=h2_lift_ci,
        complete=online_outcomes_complete,
    )
    h3_status = _hypothesis_status(
        value=called_lift,
        threshold=h3_threshold,
        ci=called_lift_ci,
        complete=online_outcomes_complete,
    )

    tools, tool_totals = _tool_records(completed_online)
    tool_totals["gains"] = called_unique_gains
    tool_totals["regressions"] = called_unique_regressions
    tool_totals["preserved"] = called_unique_preserved
    reuse_rate = (
        tool_totals["reused_tools"] / tool_totals["accepted"] * 100.0
        if tool_totals["accepted"]
        else None
    )

    config_violation_rows: list[list[str]] = []
    bridge_violations = 0
    metadata_violations = 0
    force_violations = 0
    configuration_digest_violations = 0
    runtime_exceptions = 0
    side_effect_incidents = 0
    expected_identity = campaign_manifest.get("configuration_identity") or {}
    for replicate, run in completed_online:
        protocol = run.protocol_manifest
        env = protocol.get("run_affecting_sage_env") or {}
        bridge_policy = protocol.get("synthetic_bridge_completions_enabled")
        if bridge_policy is None:
            bridge_policy = env.get("SAGE_PRAXIS_BRIDGE_POLICY") != "disabled"
        bridge_ok = bridge_policy is False
        scenario_birth = protocol.get("scenario_name_birth_enabled")
        scenario_routing = protocol.get("scenario_name_routing_enabled")
        if scenario_birth is None:
            scenario_birth = env.get("SAGE_DISABLE_SCENARIO_NAME_BIRTH") != "1"
        if scenario_routing is None:
            scenario_routing = env.get("SAGE_DISABLE_SCENARIO_NAME_ROUTING") != "1"
        metadata_ok = not scenario_birth and not scenario_routing
        active_force = [
            key
            for key in (
                "SAGE_DIAGNOSTIC_EXPOSE_TOOL_NAME",
                "SAGE_DIAGNOSTIC_FORCE_TOOL_NAME",
                "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_ERROR",
                "SAGE_DIAGNOSTIC_FORCE_TOOL_AFTER_BASE_TOOL",
            )
            if str(env.get(key) or "").strip()
        ]
        identity_ok = all(
            not expected or env.get(env_key) == expected
            for expected_key, env_key in (
                ("runtime_digest", "SAGE_TS_RUNTIME_DIGEST"),
                (
                    "generation_settings_digest",
                    "SAGE_TS_GENERATION_SETTINGS_DIGEST",
                ),
                ("prompt_policy_digest", "SAGE_TS_PROMPT_POLICY_DIGEST"),
            )
            for expected in (expected_identity.get(expected_key),)
        )
        bridge_violations += 0 if bridge_ok else 1
        metadata_violations += 0 if metadata_ok else 1
        force_violations += 1 if active_force else 0
        configuration_digest_violations += 0 if identity_ok else 1
        runtime_exceptions += run.runtime_exceptions
        side_effect_incidents += run.helper_side_effect_incidents
        config_violation_rows.append(
            [
                f"R{replicate:02d}",
                "pass" if metadata_ok else "violation",
                "pass" if bridge_ok else "violation",
                "none" if not active_force else ", ".join(active_force),
                "match" if identity_ok else "mismatch",
                str(run.runtime_exceptions),
                str(run.helper_side_effect_incidents),
            ]
        )

    run_cards = [
        _run_detail(replicate=replicate, online=online, frozen=frozen)
        for replicate, online, frozen in loaded_pairs
    ]
    complete_run_count = len(completed_online) + len(completed_frozen)
    expected_run_count = expected_online + expected_frozen
    expected_tasks_per_run = _safe_int(
        campaign_manifest.get("expected_tasks_per_run") or 1032
    )
    recorded_task_progress = sum(
        min(
            run.completed_tasks,
            run.scenario_count or expected_tasks_per_run,
        )
        for _, online, frozen in loaded_pairs
        for run in (online, frozen)
        if run is not None
    )
    expected_task_progress = expected_run_count * expected_tasks_per_run
    active_run_count = sum(
        1
        for _, online, frozen in loaded_pairs
        for run in (online, frozen)
        if run is not None and not run.complete
    )
    outcome_coverage_complete = online_outcomes_complete and (
        expected_frozen == 0 or frozen_outcomes_complete
    )
    status_label = (
        "Complete"
        if complete_run_count >= expected_run_count and outcome_coverage_complete
        else "Outcome coverage incomplete"
        if complete_run_count >= expected_run_count
        else "Running"
        if any(online or frozen for _, online, frozen in loaded_pairs)
        else "Ready"
    )
    now = datetime.now(UTC)

    h1_detail_rows = [
        [
            f"R{replicate:02d}",
            _percent(value),
        ]
        for replicate, value in per_rep_retention
    ]
    hypotheses = [
        {
            "id": "Hypothesis 1",
            "title": "Reusable generated tools preserve online-build gains",
            "estimate_percent": retention,
            "confidence_interval": _confidence_interval(
                retention_ci,
                unit="percent",
            ),
            "threshold_percent": h1_threshold,
            "sample_size": len(retention_rows),
            "decision": h1_status,
            "decision_label": _decision_label(h1_status),
            "value_label": _percent(retention),
            "primary_label": "Tools built during learning still work when reused later.",
            "claim_label": (
                "SAGE is not just solving tasks while it generates tools. The "
                "tools it creates remain useful when reused later from a frozen "
                "registry."
            ),
            "evidence_label": (
                "Compares each online-build run with a paired frozen-registry "
                "run where generation and repair are disabled."
            ),
            "observed_label": f"Observed {_percent(retention)}",
            "threshold_label": f"Target >= {h1_threshold:g}%",
            "fill_position": min(max(retention or 0.0, 0.0), 100.0),
            "target_position": h1_threshold,
            "status": h1_status,
            **_detail(
                "hypothesis:h1",
                "Hypothesis 1: Frozen-registry gain retention",
                [
                    {
                        "heading": "Definition and result",
                        "rows": _rows(
                            [
                                (
                                    "Formula",
                                    "(frozen SAGE - baseline) / (online SAGE - baseline)",
                                ),
                                ("Observed retention", _percent(retention)),
                                (
                                    "95% run-paired bootstrap CI",
                                    _percent_interval(retention_ci),
                                ),
                                (
                                    "Decision threshold",
                                    f">= {h1_threshold:g}%",
                                ),
                                ("Complete online/frozen pairs", len(retention_rows)),
                            ]
                        ),
                        "note": (
                            "Each frozen run receives a copy of the registry born "
                            "in its paired online-build run. Tool generation and "
                            "candidate repair are disabled."
                        ),
                    },
                    {
                        "heading": "Replication-level retention",
                        "table": {
                            "columns": ["Replication", "Gain retained"],
                            "rows": h1_detail_rows,
                        },
                    },
                ],
                eyebrow="Primary hypothesis metric",
            ),
        },
        {
            "id": "Hypothesis 2",
            "title": "SAGE improves task-completion accuracy over baseline",
            "estimate_percent": overall_outcome_lift,
            "confidence_interval": _confidence_interval(
                h2_lift_ci,
                unit="percent",
            ),
            "threshold_percent": h2_threshold,
            "sample_size": len(outcome_deltas),
            "baseline_mean": baseline_outcome,
            "sage_mean": sage_outcome,
            "decision": h2_status,
            "decision_label": _decision_label(h2_status),
            "value_label": _percent(overall_outcome_lift, signed=True),
            "primary_label": "Across matched tasks, SAGE completed more tasks correctly.",
            "claim_label": (
                "Across the full benchmark, SAGE completes more tasks than the "
                "same LLM agent without autonomous tool generation."
            ),
            "evidence_label": (
                "Compares matched baseline and SAGE outcomes for the same task "
                "order across all complete replications."
            ),
            "observed_label": f"Observed {_percent(overall_outcome_lift, signed=True)}",
            "threshold_label": f"Target >= {h2_threshold:g}%",
            "fill_position": min(max((overall_outcome_lift or 0.0) * 2.0, 0.0), 100.0),
            "target_position": min(max(h2_threshold * 2.0, 0.0), 100.0),
            "status": h2_status,
            **_detail(
                "hypothesis:h2",
                "Hypothesis 2: Overall task-completion lift",
                [
                    {
                        "heading": "Definition and result",
                        "rows": _rows(
                            [
                                (
                                    "Formula",
                                    "(SAGE outcome - baseline outcome) / baseline outcome",
                                ),
                                (
                                    "Baseline outcome",
                                    f"{baseline_outcome:.4f}"
                                    if baseline_outcome is not None
                                    else "-",
                                ),
                                (
                                    "SAGE outcome",
                                    f"{sage_outcome:.4f}"
                                    if sage_outcome is not None
                                    else "-",
                                ),
                                (
                                    "Relative lift",
                                    _percent(overall_outcome_lift, signed=True),
                                ),
                                (
                                    "Lift 95% paired bootstrap CI",
                                    _percent_interval(h2_lift_ci),
                                ),
                                (
                                    "Decision threshold",
                                    f">= {h2_threshold:g}%",
                                ),
                                ("Matched task observations", len(outcome_deltas)),
                            ]
                        ),
                    },
                    {
                        "heading": "Inference sensitivity",
                        "rows": _rows(
                            [
                                ("Task-paired difference CI", _interval(task_ci)),
                                (
                                    "Run-cluster mean difference CI",
                                    _interval(run_cluster_ci),
                                ),
                                ("Task-paired randomization", _p_label(task_p)),
                                ("Run-level randomization", _p_label(run_p)),
                            ]
                        ),
                    },
                ],
                eyebrow="Primary hypothesis metric",
            ),
        },
        {
            "id": "Hypothesis 3",
            "title": "Generated tools account for the accuracy gain",
            "estimate_percent": called_lift,
            "confidence_interval": _confidence_interval(
                called_lift_ci,
                unit="percent",
            ),
            "threshold_percent": h3_threshold,
            "sample_size": len(called_rows),
            "baseline_mean": called_control,
            "sage_mean": called_sage,
            "decision": h3_status,
            "decision_label": _decision_label(h3_status),
            "value_label": _percent(called_lift, signed=True),
            "primary_label": "Lift is measured only where SAGE naturally called generated tools.",
            "claim_label": (
                "The strongest gains occur on tasks where SAGE naturally selects "
                "and calls a tool it generated."
            ),
            "evidence_label": (
                "Uses only generated-tool-called tasks, with force-call "
                "diagnostics, scenario-name routing, and synthetic bridge "
                "completions disabled."
            ),
            "observed_label": f"Observed {_percent(called_lift, signed=True)}",
            "threshold_label": f"Target >= {h3_threshold:g}%",
            "fill_position": min(max(called_lift or 0.0, 0.0), 100.0),
            "target_position": h3_threshold,
            "status": h3_status,
            **_detail(
                "hypothesis:h3",
                "Hypothesis 3: Naturally called generated-tool lift",
                [
                    {
                        "heading": "Definition and result",
                        "rows": _rows(
                            [
                                (
                                    "Subset",
                                    "matched tasks with at least one recorded generated-tool call",
                                ),
                                (
                                    "Baseline outcome on subset",
                                    f"{called_control:.4f}"
                                    if called_control is not None
                                    else "-",
                                ),
                                (
                                    "SAGE outcome on subset",
                                    f"{called_sage:.4f}"
                                    if called_sage is not None
                                    else "-",
                                ),
                                (
                                    "Relative outcome lift",
                                    _percent(called_lift, signed=True),
                                ),
                                (
                                    "Lift 95% paired bootstrap CI",
                                    _percent_interval(called_lift_ci),
                                ),
                                (
                                    "Mean absolute-difference CI",
                                    _interval(called_delta_ci),
                                ),
                                (
                                    "Decision threshold",
                                    f">= {h3_threshold:g}%",
                                ),
                                ("Called-task observations", len(called_rows)),
                            ]
                        ),
                        "note": (
                            "Diagnostic force-call variables must be absent for "
                            "these calls to count as natural selection evidence."
                        ),
                    }
                ],
                eyebrow="Primary hypothesis metric",
            ),
        },
    ]

    performance = {
        "baseline": baseline_outcome,
        "sage": sage_outcome,
        "frozen_sage": frozen_sage_outcome,
        "outcome_delta": overall_outcome_delta,
        "outcome_lift_percent": overall_outcome_lift,
        "delta_label": _signed(overall_outcome_delta),
        "outcome_lift_label": _percent(overall_outcome_lift, signed=True),
        **_detail(
            "panel:performance",
            "Overall matched performance",
            [
                {
                    "heading": "Outcome / task completion",
                    "rows": _rows(
                        [
                            (
                                "Baseline mean",
                                f"{baseline_outcome:.4f}"
                                if baseline_outcome is not None
                                else "-",
                            ),
                            (
                                "SAGE mean",
                                f"{sage_outcome:.4f}"
                                if sage_outcome is not None
                                else "-",
                            ),
                            ("Absolute difference", _signed(overall_outcome_delta, 4)),
                            (
                                "Relative lift",
                                _percent(overall_outcome_lift, signed=True),
                            ),
                        ]
                    ),
                },
            ],
        ),
    }

    baseline_successes = sum(value >= 1.0 - 1e-12 for value in control_outcomes)
    sage_successes = sum(value >= 1.0 - 1e-12 for value in candidate_outcomes)
    statistics = {
        "mean_delta": overall_outcome_delta,
        "paired_bootstrap_ci": _confidence_interval(
            task_ci,
            unit="outcome_difference",
        ),
        "paired_randomization_p": task_p,
        "bootstrap_iterations": bootstrap_iterations,
        "randomization_iterations": randomization_iterations,
        "matched_task_observations": len(outcome_deltas),
        "baseline_successes": baseline_successes,
        "sage_successes": sage_successes,
        "independent_online_runs": len(completed_online),
        "run_cluster_bootstrap_ci": _confidence_interval(
            run_cluster_ci,
            unit="outcome_difference",
        ),
        "run_sign_flip_p": run_p,
        "significance_alpha": 0.05,
        "mean_delta_label": _signed(overall_outcome_delta),
        "ci_label": _interval(task_ci),
        "p_label": _p_label(task_p),
        "successes_label": f"{baseline_successes:,} / {sage_successes:,}",
        **_detail(
            "panel:statistics",
            "Paired statistical evidence",
            [
                {
                    "heading": "Primary paired analysis",
                    "rows": _rows(
                        [
                            (
                                "Mean paired outcome difference",
                                _signed(overall_outcome_delta, 4),
                            ),
                            ("Paired bootstrap 95% CI", _interval(task_ci, 4)),
                            ("Paired randomization test", _p_label(task_p)),
                            ("Bootstrap iterations", f"{bootstrap_iterations:,}"),
                            (
                                "Randomization iterations",
                                f"{randomization_iterations:,}",
                            ),
                            ("Matched task observations", f"{len(outcome_deltas):,}"),
                        ]
                    ),
                },
                {
                    "heading": "Replication sensitivity",
                    "rows": _rows(
                        [
                            ("Independent online-build runs", len(completed_online)),
                            (
                                "Run-cluster bootstrap 95% CI",
                                _interval(run_cluster_ci, 4),
                            ),
                            ("Run-level sign-flip test", _p_label(run_p)),
                        ]
                    ),
                    "note": (
                        "The run-cluster sensitivity treats each independently "
                        "generated registry as the unit of replication."
                    ),
                },
            ],
        ),
    }

    integrity_items = [
        {
            "label": "Same SAGE settings across runs",
            "value": configuration_digest_violations,
        },
        {"label": "Benchmark-metadata shortcut checks", "value": metadata_violations},
        {"label": "Code-based answer shortcut checks", "value": bridge_violations},
        {"label": "Forced generated-tool call checks", "value": force_violations},
        {"label": "Tool side-effect audit flags", "value": side_effect_incidents},
    ]
    integrity = {
        "counts": {
            "configuration_mismatches": configuration_digest_violations,
            "metadata_shortcut_violations": metadata_violations,
            "bridge_shortcut_violations": bridge_violations,
            "forced_call_violations": force_violations,
            "shortcut_violations": (
                metadata_violations + bridge_violations + force_violations
            ),
            "runtime_exceptions": runtime_exceptions,
            "side_effect_flags": side_effect_incidents,
        },
        "items": integrity_items,
        **_detail(
            "panel:integrity",
            "Evidence validity checks",
            [
                {
                    "heading": "Configuration and incident audit",
                    "table": {
                        "columns": [
                            "Run",
                            "Visible-context routing",
                            "Bridge disabled",
                            "Force-call variables",
                            "SAGE digests",
                            "Runtime exceptions",
                            "Side effects",
                        ],
                        "rows": config_violation_rows,
                    },
                    "note": (
                        "A configuration violation is counted when a completed "
                        "online-build run does not preserve the claim-grade safeguards."
                    ),
                }
            ],
        ),
    }

    metric_specs = [
        (
            "accepted",
            "Accepted tools",
            f"{tool_totals['accepted']:,}",
            "",
            "Tools accepted after source, held-out, negative, schema, and runtime validation.",
        ),
        (
            "reused",
            "Reused on later tasks",
            f"{tool_totals['reused_tools']:,}",
            "green",
            "Accepted tool instances with at least one registry reuse event after birth.",
        ),
        (
            "reuse_rate",
            "Tool reuse rate",
            _percent(reuse_rate),
            "green",
            "Accepted tool instances reused at least once divided by accepted tool instances.",
        ),
        (
            "calls",
            "Natural tool calls",
            f"{tool_totals['natural_calls']:,}",
            "",
            "Matched task scenarios containing a recorded generated-tool call with force-call diagnostics disabled.",
        ),
        (
            "gains",
            "Attributed gains",
            f"{tool_totals['gains']:,}",
            "green",
            "Called generated-tool scenarios with positive matched outcome difference.",
        ),
        (
            "preserved",
            "Preserved outcomes",
            f"{tool_totals['preserved']:,}",
            "",
            "Called generated-tool scenarios with zero matched outcome difference.",
        ),
        (
            "regressions",
            "Attributed regressions",
            f"{tool_totals['regressions']:,}",
            "amber",
            "Called generated-tool scenarios with negative matched outcome difference.",
        ),
        (
            "failures",
            "Tool-call failure scenarios",
            f"{tool_totals['runtime_failures']:,}",
            "green" if tool_totals["runtime_failures"] == 0 else "amber",
            "Matched scenarios containing at least one recorded failed generated-tool call across completed online-build runs.",
        ),
    ]
    tool_metrics = []
    for key, label, value_label, tone, definition in metric_specs:
        tool_metrics.append(
            {
                "label": label,
                "value_label": value_label,
                "tone": tone,
                **_detail(
                    f"metric:{key}",
                    label,
                    [
                        {
                            "heading": "Definition",
                            "rows": _rows(
                                [
                                    ("Observed value", value_label),
                                    (
                                        "Completed online-build runs",
                                        len(completed_online),
                                    ),
                                ]
                            ),
                            "note": definition,
                        }
                    ],
                    eyebrow="Generated-tool metric",
                ),
            }
        )

    tool_failure_summary = {
        "completed_online_runs": len(completed_online),
        "failed_scenarios": tool_totals["runtime_failures"],
        "tools": [
            {
                "name": tool["name"],
                "failed_scenarios": tool["failures"],
            }
            for tool in sorted(
                tools,
                key=lambda item: (item["failures"], item["name"]),
                reverse=True,
            )
            if tool["failures"] > 0
        ],
    }

    benchmark_path = repo_root / str(campaign_manifest.get("benchmark_manifest") or "")
    benchmark_hash = (
        _sha256(benchmark_path)
        if benchmark_path.is_file()
        else str(campaign_manifest.get("benchmark_sha256") or "")
    )
    campaign = {
        "id": str(campaign_manifest.get("campaign_id") or "chapter4_evidence"),
        "model": str(campaign_manifest.get("model") or "gpt-4o-mini"),
        "benchmark_label": str(
            campaign_manifest.get("benchmark_label") or "ToolSandbox full benchmark"
        ),
        "status_label": status_label,
        "completed_runs": complete_run_count,
        "expected_runs": expected_run_count,
        "completed_online_runs": len(completed_online),
        "completed_frozen_runs": len(completed_frozen),
        "progress_percent": (
            min(100.0, recorded_task_progress / expected_task_progress * 100.0)
            if expected_task_progress
            else 0.0
        ),
        "progress_label": (
            f"{complete_run_count} of {expected_run_count} full runs complete"
            + (
                f" · {observed_online_outcomes:,} of "
                f"{expected_online_outcomes:,} paired online outcomes"
                if complete_run_count >= expected_run_count
                and not outcome_coverage_complete
                else ""
            )
            + (f" · {active_run_count} active" if active_run_count else "")
        ),
        "recorded_task_progress": recorded_task_progress,
        "expected_task_progress": expected_task_progress,
        "paired_observations": observed_online_outcomes,
        "expected_paired_observations": expected_online_outcomes,
        "frozen_paired_observations": observed_frozen_outcomes,
        "expected_frozen_paired_observations": expected_frozen_outcomes,
        "outcome_coverage_complete": outcome_coverage_complete,
        "outcome_coverage_label": (
            f"{observed_online_outcomes:,} / {expected_online_outcomes:,} online; "
            f"{observed_frozen_outcomes:,} / {expected_frozen_outcomes:,} frozen"
        ),
        "tasks_per_run": expected_tasks_per_run,
        "updated_at": now.isoformat(),
        "updated_at_label": now.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "benchmark_sha256": benchmark_hash,
        "baseline_cache": str(campaign_manifest.get("baseline_cache") or ""),
        "baseline_cache_policy": str(
            campaign_manifest.get("baseline_cache_policy") or ""
        ),
        "claim_safeguards": _paper_claim_safeguards(
            campaign_manifest.get("claim_safeguards")
        ),
    }
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "campaign": campaign,
        "hypotheses": hypotheses,
        "performance": performance,
        "statistics": statistics,
        "integrity": integrity,
        "tool_metrics": tool_metrics,
        "tool_failure_summary": tool_failure_summary,
        "runs": run_cards,
        "tools": tools,
    }


def write_evidence_dashboard(
    *,
    repo_root: Path,
    campaign_manifest_path: Path,
    output_dir: Path,
    bootstrap_iterations: int = 10_000,
    randomization_iterations: int = 20_000,
    seed: int = 20260730,
) -> dict[str, Any]:
    """Write the dashboard HTML and its measured evidence payload."""

    campaign_manifest = _load_json(campaign_manifest_path)
    data = build_evidence_data(
        repo_root=repo_root,
        campaign_manifest=campaign_manifest,
        bootstrap_iterations=bootstrap_iterations,
        randomization_iterations=randomization_iterations,
        seed=seed,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(EVIDENCE_TEMPLATE, output_dir / EVIDENCE_HTML_NAME)
    (output_dir / EVIDENCE_DATA_NAME).write_text(
        json.dumps(data, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return data
