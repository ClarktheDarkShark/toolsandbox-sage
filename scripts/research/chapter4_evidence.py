"""Chapter 4 campaign aggregation and hypothesis evidence.

The dashboard produced from this module is an evidence view over preserved run
artifacts. It does not alter or rescore either experimental arm.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import tempfile
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np

EVIDENCE_TEMPLATE = Path(__file__).with_name("chapter4_evidence_template.html")
EVIDENCE_DATA_NAME = "chapter4_evidence_data.json"
EVIDENCE_HTML_NAME = "chapter4_evidence.html"
EVIDENCE_SCHEMA_VERSION = 3

AUDITED_ENDPOINT_NAME = "audited_current_all_tasks"
PAPER_ENDPOINT_NAME = "paper_comparable_historical_subset"
OUTCOME_EVALUATOR_SOURCE = Path("src/sage_ts/evaluation/outcome_score.py")
RESEARCHER_SAMPLE_WAIVER_STATUS = "waived_by_researcher"
RESEARCHER_SAMPLE_WAIVER_AUTHORIZATION = "explicit_prepare_cli"
_DASHBOARD_WRITE_LOCK = threading.Lock()

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
    control_score: float | None
    candidate_score: float | None
    control_outcome: float | None
    candidate_outcome: float | None
    task_rows: tuple[dict[str, Any], ...]
    paper_control_outcome: float | None
    paper_candidate_outcome: float | None
    paper_task_rows: tuple[dict[str, Any], ...]
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


@dataclass(frozen=True)
class DualEndpointSpec:
    """Content-addressed declarations for the two non-interchangeable endpoints."""

    thresholds_path: Path
    thresholds_sha256: str
    audited: dict[str, Any]
    paper: dict[str, Any]
    historical: dict[str, Any]


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


def _atomic_write_text(path: Path, content: str) -> None:
    """Atomically replace one dashboard artifact via a unique same-dir temp file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


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
        "descriptive_only": "Descriptive only",
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


def _ordered_name_sha256(names: Iterable[str]) -> str:
    return hashlib.sha256(("\n".join(names) + "\n").encode("utf-8")).hexdigest()


def _required_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string.")
    return value


def _required_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer.")
    return value


def _required_unit_float(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric.")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"{label} must be finite and within [0, 1].")
    return result


def _resolve_repo_path(repo_root: Path, raw: Any, label: str) -> Path:
    value = _required_string(raw, label)
    candidate = Path(value)
    resolved = (
        candidate if candidate.is_absolute() else repo_root / candidate
    ).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} escapes the repository root.") from exc
    return resolved


def _load_dual_endpoint_spec(
    repo_root: Path,
    campaign_manifest: dict[str, Any],
) -> DualEndpointSpec | None:
    """Load exact endpoint declarations pinned by a sample or explicit waiver."""

    statistical_plan = campaign_manifest.get("statistical_plan") or {}
    plan_endpoints = statistical_plan.get("performance_endpoints")
    if plan_endpoints in (None, {}):
        return None
    if not isinstance(plan_endpoints, dict) or set(plan_endpoints) != {
        AUDITED_ENDPOINT_NAME,
        PAPER_ENDPOINT_NAME,
    }:
        raise ValueError("Campaign performance endpoint declarations are not exact.")

    sample = campaign_manifest.get("sample_validation")
    if not isinstance(sample, dict):
        raise ValueError(
            "Dual-endpoint evidence requires a passing sample report or explicit "
            "researcher waiver."
        )
    if sample.get("status") == "pass":
        sample_path = _resolve_repo_path(
            repo_root,
            sample.get("path"),
            "campaign sample-validation path",
        )
        if not sample_path.is_file():
            raise ValueError(
                f"Campaign sample-validation report is missing: {sample_path}"
            )
        expected_sample_hash = _required_string(
            sample.get("sha256"), "campaign sample-validation SHA-256"
        )
        if _sha256(sample_path) != expected_sample_hash:
            raise ValueError("Campaign sample-validation report bytes changed.")
        endpoint_input = _load_json(sample_path)
        if endpoint_input.get("status") != "pass":
            raise ValueError("Campaign sample-validation report is not passing.")
    elif sample.get("status") == RESEARCHER_SAMPLE_WAIVER_STATUS:
        if sample.get("authorization") != RESEARCHER_SAMPLE_WAIVER_AUTHORIZATION:
            raise ValueError("Campaign sample-validation waiver is not authorized.")
        reason = sample.get("reason")
        if not isinstance(reason, str) or not reason or reason != reason.strip():
            raise ValueError("Campaign sample-validation waiver reason is invalid.")
        if sample.get("required_gate") != "release-sample":
            raise ValueError(
                "Campaign sample-validation waiver does not identify release-sample."
            )
        authorized_at = sample.get("authorized_at")
        if not isinstance(authorized_at, str) or not authorized_at:
            raise ValueError(
                "Campaign sample-validation waiver authorization time is missing."
            )
        endpoint_input = sample
    else:
        raise ValueError(
            "Dual-endpoint evidence requires a passing sample report or explicit "
            "researcher waiver."
        )
    thresholds_path = _resolve_repo_path(
        repo_root,
        endpoint_input.get("thresholds_path"),
        "sample-validation thresholds path",
    )
    expected_thresholds_hash = _required_string(
        endpoint_input.get("thresholds_sha256"),
        "sample-validation thresholds SHA-256",
    )
    if (
        not thresholds_path.is_file()
        or _sha256(thresholds_path) != expected_thresholds_hash
    ):
        raise ValueError("Sample-validation threshold bytes changed.")
    thresholds = _load_json(thresholds_path)
    if (
        thresholds.get("schema_version") != 3
        or thresholds.get("performance_endpoint_policy")
        != "dual_scoped_outcome_endpoints"
        or thresholds.get("canonical_metric_policy")
        != "descriptive_only_never_a_release_gate"
    ):
        raise ValueError("Sample report does not pin the dual-endpoint v3 policy.")
    endpoints = thresholds.get("performance_endpoints")
    historical = thresholds.get("historical_reference")
    benchmark = thresholds.get("benchmark")
    if (
        not isinstance(endpoints, dict)
        or set(endpoints) != {AUDITED_ENDPOINT_NAME, PAPER_ENDPOINT_NAME}
        or not isinstance(historical, dict)
        or not isinstance(benchmark, dict)
    ):
        raise ValueError("Pinned threshold endpoint inputs are incomplete.")
    audited = endpoints[AUDITED_ENDPOINT_NAME]
    paper = endpoints[PAPER_ENDPOINT_NAME]
    if not isinstance(audited, dict) or not isinstance(paper, dict):
        raise ValueError("Pinned endpoint declarations must be objects.")

    expected_tasks = _required_integer(
        campaign_manifest.get("expected_tasks_per_run"),
        "campaign expected tasks per run",
    )
    expected_online_runs = _required_integer(
        campaign_manifest.get("expected_online_runs"),
        "campaign expected online runs",
    )
    if benchmark.get("task_count") != expected_tasks or benchmark.get(
        "manifest_sha256"
    ) != campaign_manifest.get("benchmark_sha256"):
        raise ValueError("Campaign benchmark and pinned endpoint benchmark disagree.")

    for endpoint_name, declaration in (
        (AUDITED_ENDPOINT_NAME, audited),
        (PAPER_ENDPOINT_NAME, paper),
    ):
        planned = plan_endpoints.get(endpoint_name)
        if not isinstance(planned, dict):
            raise ValueError(f"Campaign endpoint {endpoint_name!r} is not an object.")
        if (
            set(planned)
            != {
                "metric_field",
                "evaluator_version",
                "task_count_per_run",
                "expected_matched_pairs",
                "aggregate_statistics",
            }
            or planned.get("aggregate_statistics") is not None
        ):
            raise ValueError(
                f"Campaign endpoint {endpoint_name!r} fields are not exact."
            )
        task_count = _required_integer(
            declaration.get("task_count"), f"{endpoint_name} task count"
        )
        expected_pairs = expected_online_runs * task_count
        expected_plan = {
            "metric_field": declaration.get("metric_field"),
            "evaluator_version": declaration.get("evaluator_version"),
            "task_count_per_run": task_count,
            "expected_matched_pairs": expected_pairs,
        }
        for field, expected in expected_plan.items():
            if planned.get(field) != expected:
                raise ValueError(
                    f"Campaign {endpoint_name}.{field} disagrees with pinned thresholds."
                )

    audited_source = (repo_root / OUTCOME_EVALUATOR_SOURCE).resolve()
    if not audited_source.is_file() or _sha256(audited_source) != audited.get(
        "evaluator_source_sha256"
    ):
        raise ValueError("Audited outcome evaluator source bytes changed.")
    paper_source = _resolve_repo_path(
        repo_root,
        paper.get("evaluator_source_path"),
        "paper-comparable evaluator source path",
    )
    if not paper_source.is_file() or _sha256(paper_source) != paper.get(
        "evaluator_source_sha256"
    ):
        raise ValueError("Paper-comparable evaluator source bytes changed.")
    return DualEndpointSpec(
        thresholds_path=thresholds_path,
        thresholds_sha256=expected_thresholds_hash,
        audited=audited,
        paper=paper,
        historical=historical,
    )


def _task_compare_url(protocol_manifest: dict[str, Any], path: Path) -> str:
    declared = str(protocol_manifest.get("dashboard_task_compare_url") or "")
    if declared.startswith(
        ("http://127.0.0.1:", "http://localhost:", "http://[::1]:")
    ) and declared.endswith("/dashboard/task_compare.html"):
        return declared
    return path.resolve().as_uri() if path.is_file() else ""


def resolve_run_root(repo_root: Path, entry: dict[str, Any]) -> Path | None:
    """Resolve a manifest run entry to its active or completed protocol root."""

    search_root_raw = str(entry.get("search_root") or "").strip()
    search_root = (
        _resolve_repo_path(repo_root, search_root_raw, "campaign search_root")
        if search_root_raw
        else None
    )
    explicit = str(entry.get("run_root") or "").strip()
    if explicit:
        path = _resolve_repo_path(repo_root, explicit, "campaign run_root")
        if search_root is not None and not path.is_relative_to(search_root):
            raise ValueError("Campaign run_root escapes its declared search_root.")
        if path.exists():
            return path

    if search_root is None:
        return None
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


def _declared_arm_directory(
    *,
    repo_root: Path,
    run_root: Path,
    protocol_manifest: dict[str, Any],
    paired: dict[str, Any],
    arm: str,
) -> Path:
    required_parent = (run_root / arm).resolve()
    protocol_dir = _resolve_repo_path(
        repo_root,
        protocol_manifest.get(f"{arm}_dir"),
        f"protocol {arm}_dir",
    )
    paired_arm = paired.get(arm)
    if not isinstance(paired_arm, dict):
        raise ValueError(f"Paired comparison is missing its {arm} arm.")
    paired_dir = _resolve_repo_path(
        repo_root,
        paired_arm.get("run_dir"),
        f"paired comparison {arm}.run_dir",
    )
    if (
        not protocol_dir.is_dir()
        or not protocol_dir.is_relative_to(required_parent)
        or paired_dir != protocol_dir
    ):
        raise ValueError(
            f"{arm} result directory is outside or disagrees with the protocol."
        )
    return protocol_dir


def _result_rows(run_dir: Path, arm: str) -> list[dict[str, Any]]:
    summary_path = run_dir / "result_summary.json"
    if not summary_path.is_file():
        raise ValueError(f"{arm} result summary is missing: {summary_path}")
    raw_rows = _load_json(summary_path).get("per_scenario_results")
    if not isinstance(raw_rows, list):
        raise ValueError(f"{arm} result summary has no scenario result list.")
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(raw_rows):
        if not isinstance(row, dict):
            raise ValueError(f"{arm} scenario result {index} is not an object.")
        rows.append(row)
    return rows


def _identity_values(rows: Iterable[dict[str, Any]], field: str) -> set[Any]:
    return {row.get(field) for row in rows}


def _load_dual_task_rows(
    *,
    repo_root: Path,
    run_root: Path,
    protocol_manifest: dict[str, Any],
    paired: dict[str, Any],
    endpoint_spec: DualEndpointSpec,
) -> tuple[
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
    float,
    float,
    float,
    float,
]:
    """Load and fail-closed validate both raw per-task outcome endpoints."""

    arm_rows: dict[str, list[dict[str, Any]]] = {}
    for arm in ("control", "candidate"):
        run_dir = _declared_arm_directory(
            repo_root=repo_root,
            run_root=run_root,
            protocol_manifest=protocol_manifest,
            paired=paired,
            arm=arm,
        )
        arm_rows[arm] = _result_rows(run_dir, arm)

    audited = endpoint_spec.audited
    paper = endpoint_spec.paper
    audited_count = _required_integer(
        audited.get("task_count"), "audited endpoint task count"
    )
    paper_count = _required_integer(
        paper.get("task_count"), "paper-comparable endpoint task count"
    )
    audited_names: dict[str, list[str]] = {}
    paper_names: dict[str, list[str]] = {}
    audited_values: dict[str, list[float]] = {}
    paper_values: dict[str, list[float]] = {}

    for arm, rows in arm_rows.items():
        if len(rows) != audited_count:
            raise ValueError(
                f"{arm} audited endpoint has {len(rows)} rows; expected {audited_count}."
            )
        names = [
            _required_string(row.get("name"), f"{arm} task {index} name")
            for index, row in enumerate(rows)
        ]
        if len(set(names)) != len(names):
            raise ValueError(f"{arm} audited endpoint task names are not unique.")
        if _ordered_name_sha256(names) != audited.get("ordered_task_name_sha256"):
            raise ValueError(f"{arm} audited endpoint task order changed.")
        if _identity_values(rows, "outcome_evaluator_version") != {
            audited.get("evaluator_version")
        }:
            raise ValueError(f"{arm} audited evaluator version is not exact.")
        if _identity_values(rows, "outcome_evaluator_contract_sha256") != {
            audited.get("evaluator_contract_sha256")
        }:
            raise ValueError(f"{arm} audited evaluator contract hash is not exact.")
        if _identity_values(rows, "outcome_evaluator_source_sha256") != {
            audited.get("evaluator_source_sha256")
        }:
            raise ValueError(f"{arm} audited evaluator source hash is not exact.")
        values = [
            _required_unit_float(
                row.get("outcome_similarity"), f"{arm} audited task {name}"
            )
            for name, row in zip(names, rows, strict=True)
        ]
        selected_paper_rows = [
            row
            for row in rows
            if row.get("online_feedback_outcome_similarity") is not None
        ]
        selected_paper_names = [
            _required_string(row.get("name"), f"{arm} paper-comparable task name")
            for row in selected_paper_rows
        ]
        if len(selected_paper_rows) != paper_count:
            raise ValueError(
                f"{arm} paper-comparable endpoint has {len(selected_paper_rows)} "
                f"rows; expected {paper_count}."
            )
        if len(set(selected_paper_names)) != len(selected_paper_names):
            raise ValueError(f"{arm} paper-comparable task names are not unique.")
        if _ordered_name_sha256(selected_paper_names) != paper.get(
            "ordered_task_name_sha256"
        ):
            raise ValueError(f"{arm} paper-comparable task subset or order changed.")
        if _identity_values(
            selected_paper_rows, "online_feedback_evaluator_version"
        ) != {paper.get("evaluator_version")}:
            raise ValueError(f"{arm} paper-comparable evaluator version is not exact.")
        selected_paper_values = [
            _required_unit_float(
                row.get("online_feedback_outcome_similarity"),
                f"{arm} paper-comparable task {name}",
            )
            for name, row in zip(selected_paper_names, selected_paper_rows, strict=True)
        ]
        audited_names[arm] = names
        paper_names[arm] = selected_paper_names
        audited_values[arm] = values
        paper_values[arm] = selected_paper_values

    if audited_names["control"] != audited_names["candidate"]:
        raise ValueError("Audited endpoint control/candidate task order differs.")
    if paper_names["control"] != paper_names["candidate"]:
        raise ValueError("Paper-comparable control/candidate subset or order differs.")

    paired_deltas = paired.get("deltas")
    if not isinstance(paired_deltas, list) or len(paired_deltas) != audited_count:
        raise ValueError("Paired comparison does not contain the audited task set.")
    normalized_rows: list[dict[str, Any]] = []
    for index, (name, control_row, candidate_row) in enumerate(
        zip(
            audited_names["control"],
            arm_rows["control"],
            arm_rows["candidate"],
            strict=True,
        )
    ):
        delta_row = paired_deltas[index]
        if not isinstance(delta_row, dict) or delta_row.get("scenario") != name:
            raise ValueError(
                "Paired comparison task order differs from result summaries."
            )
        control_outcome = audited_values["control"][index]
        candidate_outcome = audited_values["candidate"][index]
        for field, expected in (
            ("control_outcome_similarity", control_outcome),
            ("candidate_outcome_similarity", candidate_outcome),
            ("outcome_delta", candidate_outcome - control_outcome),
        ):
            observed = _safe_float(delta_row.get(field))
            if observed is None or not math.isclose(
                observed, expected, rel_tol=0.0, abs_tol=1e-12
            ):
                raise ValueError(f"Paired comparison {field} disagrees for {name}.")
        normalized_rows.append(
            {
                "scenario": name,
                "control_score": _safe_float(control_row.get("similarity")),
                "candidate_score": _safe_float(candidate_row.get("similarity")),
                "score_delta": _safe_float(delta_row.get("delta")),
                "control_outcome": control_outcome,
                "candidate_outcome": candidate_outcome,
                "outcome_delta": candidate_outcome - control_outcome,
            }
        )

    normalized_paper_rows = tuple(
        {
            "scenario": name,
            "control_outcome": control,
            "candidate_outcome": candidate,
            "outcome_delta": candidate - control,
        }
        for name, control, candidate in zip(
            paper_names["control"],
            paper_values["control"],
            paper_values["candidate"],
            strict=True,
        )
    )
    return (
        tuple(normalized_rows),
        normalized_paper_rows,
        float(np.mean(audited_values["control"])),
        float(np.mean(audited_values["candidate"])),
        float(np.mean(paper_values["control"])),
        float(np.mean(paper_values["candidate"])),
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
    *,
    endpoint_spec: DualEndpointSpec | None = None,
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

    task_rows: tuple[dict[str, Any], ...]
    paper_task_rows: tuple[dict[str, Any], ...] = ()
    paper_control_outcome: float | None = None
    paper_candidate_outcome: float | None = None
    raw_control_outcome: float | None = None
    raw_candidate_outcome: float | None = None
    if endpoint_spec is not None and paired_path.exists():
        (
            task_rows,
            paper_task_rows,
            raw_control_outcome,
            raw_candidate_outcome,
            paper_control_outcome,
            paper_candidate_outcome,
        ) = _load_dual_task_rows(
            repo_root=repo_root,
            run_root=run_root,
            protocol_manifest=protocol_manifest,
            paired=paired,
            endpoint_spec=endpoint_spec,
        )
    else:
        legacy_rows: list[dict[str, Any]] = []
        for row in paired.get("deltas") or []:
            if not isinstance(row, dict):
                continue
            scenario = str(row.get("scenario") or "")
            legacy_rows.append(
                {
                    "scenario": scenario,
                    "control_score": _safe_float(row.get("control_similarity")),
                    "candidate_score": _safe_float(row.get("candidate_similarity")),
                    "score_delta": _safe_float(row.get("delta")),
                    "control_outcome": _safe_float(
                        row.get("control_outcome_similarity")
                    ),
                    "candidate_outcome": _safe_float(
                        row.get("candidate_outcome_similarity")
                    ),
                    "outcome_delta": _safe_float(row.get("outcome_delta")),
                }
            )
        task_rows = tuple(legacy_rows)

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
    control_score = _safe_float(
        summary.get("balanced_control_mean_similarity")
        if summary
        else paired.get("control_mean_similarity")
    )
    candidate_score = _safe_float(
        summary.get("balanced_candidate_mean_similarity")
        if summary
        else paired.get("candidate_mean_similarity")
    )
    control_outcome = raw_control_outcome
    if control_outcome is None:
        control_outcome = _safe_float(
            summary.get("balanced_control_mean_outcome_similarity")
            if summary
            else paired.get("control_mean_outcome_similarity")
        )
    candidate_outcome = raw_candidate_outcome
    if candidate_outcome is None:
        candidate_outcome = _safe_float(
            summary.get("balanced_candidate_mean_outcome_similarity")
            if summary
            else paired.get("candidate_mean_outcome_similarity")
        )
    dashboard_url = _task_compare_url(
        protocol_manifest,
        run_root / "dashboard" / "task_compare.html",
    )
    return RunEvidence(
        run_root=run_root,
        complete=complete,
        completed_tasks=completed_tasks,
        scenario_count=scenario_count,
        control_score=control_score,
        candidate_score=candidate_score,
        control_outcome=control_outcome,
        candidate_outcome=candidate_outcome,
        task_rows=task_rows,
        paper_control_outcome=paper_control_outcome,
        paper_candidate_outcome=paper_candidate_outcome,
        paper_task_rows=paper_task_rows,
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


def verify_run_endpoint_measurements(
    *,
    repo_root: Path,
    campaign_manifest: dict[str, Any],
    entry: dict[str, Any],
) -> dict[str, Any]:
    """Fail closed unless one completed run has both exact endpoint measurements.

    This is an availability, identity, scope, order, and numeric-validity check.
    It intentionally applies no performance floor and never examines canonical
    similarity as a release criterion.
    """

    endpoint_spec = _load_dual_endpoint_spec(repo_root, campaign_manifest)
    if endpoint_spec is None:
        raise ValueError("Campaign does not declare dual-scoped outcome endpoints.")
    evidence = load_run_evidence(
        repo_root,
        entry,
        endpoint_spec=endpoint_spec,
    )
    if evidence is None or not evidence.complete:
        raise ValueError("Run is incomplete or lacks final paired outcome artifacts.")
    audited_count = _required_integer(
        endpoint_spec.audited.get("task_count"), "audited endpoint task count"
    )
    paper_count = _required_integer(
        endpoint_spec.paper.get("task_count"),
        "paper-comparable endpoint task count",
    )
    if len(evidence.task_rows) != audited_count:
        raise ValueError("Run audited endpoint count changed after validation.")
    if len(evidence.paper_task_rows) != paper_count:
        raise ValueError(
            "Run paper-comparable endpoint count changed after validation."
        )
    return {
        "status": "pass",
        "run_root": str(evidence.run_root),
        "performance_endpoint_policy": "dual_scoped_outcome_endpoints",
        "audited_current_all_tasks": {
            "metric_field": endpoint_spec.audited.get("metric_field"),
            "evaluator_version": endpoint_spec.audited.get("evaluator_version"),
            "evaluator_contract_sha256": endpoint_spec.audited.get(
                "evaluator_contract_sha256"
            ),
            "evaluator_source_sha256": endpoint_spec.audited.get(
                "evaluator_source_sha256"
            ),
            "task_count": audited_count,
            "ordered_task_name_sha256": endpoint_spec.audited.get(
                "ordered_task_name_sha256"
            ),
            "control_mean": evidence.control_outcome,
            "candidate_mean": evidence.candidate_outcome,
        },
        "paper_comparable_historical_subset": {
            "metric_field": endpoint_spec.paper.get("metric_field"),
            "evaluator_version": endpoint_spec.paper.get("evaluator_version"),
            "task_count": paper_count,
            "ordered_task_name_sha256": endpoint_spec.paper.get(
                "ordered_task_name_sha256"
            ),
            "control_mean": evidence.paper_control_outcome,
            "candidate_mean": evidence.paper_candidate_outcome,
        },
        "performance_floors_applied": False,
        "canonical_metric_checked_as_gate": False,
    }


def _entry_is_inference_eligible(
    *,
    repo_root: Path,
    entry: dict[str, Any],
    evidence: RunEvidence | None,
    endpoint_spec: DualEndpointSpec | None,
) -> bool:
    if evidence is None or not evidence.complete:
        return False
    if endpoint_spec is None:
        return True
    if (
        entry.get("execution_status") != "completed"
        or type(entry.get("return_code")) is not int
        or entry.get("return_code") != 0
        or entry.get("verification_status") != "pass"
    ):
        return False
    try:
        declared_root = _resolve_repo_path(
            repo_root,
            entry.get("run_root"),
            "completed campaign entry run_root",
        )
    except ValueError:
        return False
    if declared_root != evidence.run_root.resolve():
        return False

    attestation = entry.get("endpoint_measurements")
    if not isinstance(attestation, dict) or set(attestation) != {
        "status",
        "run_root",
        "performance_endpoint_policy",
        AUDITED_ENDPOINT_NAME,
        PAPER_ENDPOINT_NAME,
        "performance_floors_applied",
        "canonical_metric_checked_as_gate",
    }:
        return False
    if (
        attestation.get("status") != "pass"
        or attestation.get("performance_endpoint_policy")
        != "dual_scoped_outcome_endpoints"
        or attestation.get("performance_floors_applied") is not False
        or attestation.get("canonical_metric_checked_as_gate") is not False
    ):
        return False
    try:
        attested_root = _resolve_repo_path(
            repo_root,
            attestation.get("run_root"),
            "endpoint attestation run_root",
        )
    except ValueError:
        return False
    if attested_root != evidence.run_root.resolve():
        return False

    audited = attestation.get(AUDITED_ENDPOINT_NAME)
    paper = attestation.get(PAPER_ENDPOINT_NAME)
    if not isinstance(audited, dict) or set(audited) != {
        "metric_field",
        "evaluator_version",
        "evaluator_contract_sha256",
        "evaluator_source_sha256",
        "task_count",
        "ordered_task_name_sha256",
        "control_mean",
        "candidate_mean",
    }:
        return False
    if not isinstance(paper, dict) or set(paper) != {
        "metric_field",
        "evaluator_version",
        "task_count",
        "ordered_task_name_sha256",
        "control_mean",
        "candidate_mean",
    }:
        return False
    for observed, declaration, fields in (
        (
            audited,
            endpoint_spec.audited,
            (
                "metric_field",
                "evaluator_version",
                "evaluator_contract_sha256",
                "evaluator_source_sha256",
                "task_count",
                "ordered_task_name_sha256",
            ),
        ),
        (
            paper,
            endpoint_spec.paper,
            (
                "metric_field",
                "evaluator_version",
                "task_count",
                "ordered_task_name_sha256",
            ),
        ),
    ):
        if any(observed.get(field) != declaration.get(field) for field in fields):
            return False
    for observed, expected in (
        (audited.get("control_mean"), evidence.control_outcome),
        (audited.get("candidate_mean"), evidence.candidate_outcome),
        (paper.get("control_mean"), evidence.paper_control_outcome),
        (paper.get("candidate_mean"), evidence.paper_candidate_outcome),
    ):
        try:
            value = _required_unit_float(observed, "endpoint attestation mean")
        except ValueError:
            return False
        if expected is None or not math.isclose(
            value,
            expected,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            return False
    return True


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


def _two_way_paired_outcome_bootstrap(
    control_rows: list[list[float]],
    candidate_rows: list[list[float]],
    *,
    threshold_percent: float,
    iterations: int,
    seed: int,
) -> dict[str, tuple[float | None, float | None]]:
    """Resample independent runs and the common matched-task order.

    The threshold contrast is ``candidate - (1 + threshold) * control``. Its
    zero boundary therefore tests the predeclared relative-lift threshold
    directly, instead of testing only whether the arm difference is positive.
    """

    empty = {
        "absolute_difference": (None, None),
        "relative_lift_percent": (None, None),
        "threshold_contrast": (None, None),
    }
    if not control_rows or not candidate_rows:
        return empty
    if len(control_rows) != len(candidate_rows):
        raise ValueError("Two-way bootstrap arm run counts differ.")
    task_counts = {len(row) for row in [*control_rows, *candidate_rows]}
    if len(task_counts) != 1 or not next(iter(task_counts), 0):
        raise ValueError("Two-way bootstrap requires one common non-empty task order.")
    control = np.asarray(control_rows, dtype=float)
    candidate = np.asarray(candidate_rows, dtype=float)
    if control.shape != candidate.shape or control.ndim != 2:
        raise ValueError("Two-way bootstrap arm matrices differ.")
    if not np.isfinite(control).all() or not np.isfinite(candidate).all():
        raise ValueError("Two-way bootstrap inputs must be finite.")

    rng = np.random.default_rng(seed)
    run_count, task_count = control.shape
    multiplier = 1.0 + threshold_percent / 100.0
    delta_samples: list[np.ndarray] = []
    lift_samples: list[np.ndarray] = []
    contrast_samples: list[np.ndarray] = []
    remaining = iterations
    batch_size = min(128, iterations)
    while remaining:
        size = min(batch_size, remaining)
        run_indices = rng.integers(0, run_count, size=(size, run_count))
        task_indices = rng.integers(0, task_count, size=(size, task_count))
        control_sample = control[
            run_indices[:, :, None],
            task_indices[:, None, :],
        ].mean(axis=(1, 2))
        candidate_sample = candidate[
            run_indices[:, :, None],
            task_indices[:, None, :],
        ].mean(axis=(1, 2))
        delta_samples.append(candidate_sample - control_sample)
        contrast_samples.append(candidate_sample - multiplier * control_sample)
        valid = np.abs(control_sample) > 1e-12
        if np.any(valid):
            lift_samples.append(
                (candidate_sample[valid] - control_sample[valid])
                / control_sample[valid]
                * 100.0
            )
        remaining -= size

    def interval(samples: list[np.ndarray]) -> tuple[float | None, float | None]:
        if not samples:
            return (None, None)
        low, high = np.quantile(np.concatenate(samples), [0.025, 0.975])
        return (float(low), float(high))

    return {
        "absolute_difference": interval(delta_samples),
        "relative_lift_percent": interval(lift_samples),
        "threshold_contrast": interval(contrast_samples),
    }


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


def _h2_confirmatory_status(
    *,
    lift_percent: float | None,
    threshold_percent: float,
    two_way_threshold_contrast_ci: tuple[float | None, float | None],
    run_threshold_contrast_ci: tuple[float | None, float | None],
    run_threshold_sign_flip_p: float | None,
    complete: bool,
    alpha: float,
) -> str:
    """Apply the run/task-cluster-aware H2 decision rule."""

    if lift_percent is None or not complete:
        return "pending"
    if lift_percent < threshold_percent:
        return "not_supported"
    two_way_low, _ = two_way_threshold_contrast_ci
    run_low, _ = run_threshold_contrast_ci
    if (
        two_way_low is not None
        and two_way_low > 0.0
        and run_low is not None
        and run_low > 0.0
        and run_threshold_sign_flip_p is not None
        and run_threshold_sign_flip_p < alpha
    ):
        return "supported"
    return "observed_pass"


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
    policy_directed_calls = 0
    gains = 0
    regressions = 0
    preserved = 0
    runtime_failures = 0

    for replicate, run in online_runs:
        accepted_total += run.accepted_tools
        reuse_events += run.reuse_events
        policy_directed_calls += run.generated_tool_called_scenarios
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
                                ("Policy-directed calls", record["calls"]),
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
        # Keep the historical key for evidence-file compatibility; these calls
        # were selected by the production actor policy, not naturally by the
        # base model.
        "natural_calls": policy_directed_calls,
        "policy_directed_calls": policy_directed_calls,
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
    online_inference_eligible: bool = False,
    frozen_inference_eligible: bool = False,
    historical_paper_candidate_mean: float | None = None,
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
    paper_lift = (
        _relative_lift(
            online.paper_candidate_outcome,
            online.paper_control_outcome,
        )
        if online
        else None
    )
    paper_historical_delta = (
        online.paper_candidate_outcome - historical_paper_candidate_mean
        if online
        and online.paper_candidate_outcome is not None
        and historical_paper_candidate_mean is not None
        else None
    )
    retention = None
    if (
        online_inference_eligible
        and frozen_inference_eligible
        and online
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
        if online_inference_eligible and frozen_inference_eligible
        else "Online complete"
        if online_inference_eligible
        else "Excluded from inference"
        if (online and online.complete) or (frozen and frozen.complete)
        else "Running"
        if online or frozen
        else "Queued"
    )
    sections = [
        {
            "heading": "Audited current endpoint (v9, all 1,032 tasks)",
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
            "heading": "Paper-comparable endpoint (v1, exact 800-task subset)",
            "rows": _rows(
                [
                    (
                        "Fresh baseline outcome",
                        f"{online.paper_control_outcome:.3f}"
                        if online and online.paper_control_outcome is not None
                        else "-",
                    ),
                    (
                        "Online-build SAGE outcome",
                        f"{online.paper_candidate_outcome:.3f}"
                        if online and online.paper_candidate_outcome is not None
                        else "-",
                    ),
                    ("Same-run relative lift", _percent(paper_lift, signed=True)),
                    (
                        "SAGE minus historical SAGE mean",
                        _signed(paper_historical_delta, 4),
                    ),
                ]
            ),
            "note": (
                "This v1 subset is used only for an apples-to-apples descriptive "
                "comparison with the archived paper campaign. It is not mixed "
                "with the v9 all-task hypothesis analysis."
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
        "online_inference_eligible": online_inference_eligible,
        "frozen_inference_eligible": frozen_inference_eligible,
        "dashboard_url": online.dashboard_url if online else "",
        "baseline_outcome": (
            online.control_outcome if online and online_inference_eligible else None
        ),
        "online_sage_outcome": (
            online.candidate_outcome if online and online_inference_eligible else None
        ),
        "frozen_sage_outcome": (
            frozen.candidate_outcome if frozen and frozen_inference_eligible else None
        ),
        "audited_current_outcome_lift_percent": (
            online_lift if online_inference_eligible else None
        ),
        "online_outcome_lift_percent": (
            online_lift if online_inference_eligible else None
        ),
        "paper_comparable_baseline_outcome": (
            online.paper_control_outcome
            if online and online_inference_eligible
            else None
        ),
        "paper_comparable_sage_outcome": (
            online.paper_candidate_outcome
            if online and online_inference_eligible
            else None
        ),
        "paper_comparable_outcome_lift_percent": (
            paper_lift if online_inference_eligible else None
        ),
        "paper_comparable_candidate_minus_historical_mean": (
            paper_historical_delta if online_inference_eligible else None
        ),
        "frozen_gain_retention_percent": (
            retention
            if online_inference_eligible and frozen_inference_eligible
            else None
        ),
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

    endpoint_spec = _load_dual_endpoint_spec(repo_root, campaign_manifest)
    pair_entries = campaign_manifest.get("run_pairs") or []
    expected_online = _safe_int(
        campaign_manifest.get("expected_online_runs") or len(pair_entries)
    )
    declared_expected_frozen = campaign_manifest.get("expected_frozen_runs")
    expected_frozen = _safe_int(
        len(pair_entries)
        if declared_expected_frozen is None
        else declared_expected_frozen
    )
    statistical_plan = campaign_manifest.get("statistical_plan") or {}
    h1_threshold = _safe_float(statistical_plan.get("hypothesis_1_threshold_percent"))
    h2_threshold = _safe_float(statistical_plan.get("hypothesis_2_threshold_percent"))
    h3_threshold = _safe_float(statistical_plan.get("hypothesis_3_threshold_percent"))
    h1_threshold = H1_THRESHOLD_PERCENT if h1_threshold is None else h1_threshold
    h2_threshold = H2_THRESHOLD_PERCENT if h2_threshold is None else h2_threshold
    h3_threshold = H3_THRESHOLD_PERCENT if h3_threshold is None else h3_threshold

    loaded_pairs: list[tuple[int, RunEvidence | None, RunEvidence | None]] = []
    entries_by_replication: dict[int, dict[str, dict[str, Any]]] = {}
    for entry in pair_entries:
        if not isinstance(entry, dict):
            continue
        replicate = _safe_int(entry.get("replication"))
        online_entry = entry.get("online") or {}
        frozen_entry = entry.get("frozen") or {}
        if endpoint_spec is not None and replicate in entries_by_replication:
            raise ValueError("Campaign replication identifiers are not unique.")
        entries_by_replication[replicate] = {
            "online": online_entry if isinstance(online_entry, dict) else {},
            "frozen": frozen_entry if isinstance(frozen_entry, dict) else {},
        }
        online = (
            load_run_evidence(
                repo_root,
                online_entry,
                endpoint_spec=endpoint_spec,
            )
            if isinstance(online_entry, dict)
            else None
        )
        frozen = (
            load_run_evidence(
                repo_root,
                frozen_entry,
                endpoint_spec=endpoint_spec,
            )
            if isinstance(frozen_entry, dict)
            else None
        )
        loaded_pairs.append((replicate, online, frozen))

    online_eligibility = {
        replicate: _entry_is_inference_eligible(
            repo_root=repo_root,
            entry=entries_by_replication[replicate]["online"],
            evidence=run,
            endpoint_spec=endpoint_spec,
        )
        for replicate, run, _ in loaded_pairs
    }
    frozen_eligibility = {
        replicate: _entry_is_inference_eligible(
            repo_root=repo_root,
            entry=entries_by_replication[replicate]["frozen"],
            evidence=run,
            endpoint_spec=endpoint_spec,
        )
        for replicate, _, run in loaded_pairs
    }
    completed_online = [
        (replicate, run)
        for replicate, run, _ in loaded_pairs
        if run is not None and online_eligibility[replicate]
    ]
    completed_frozen = [
        (replicate, run)
        for replicate, _, run in loaded_pairs
        if run is not None and frozen_eligibility[replicate]
    ]
    completed_frozen_by_rep = dict(completed_frozen)
    declared_campaign_complete = campaign_manifest.get("status") == "complete"
    online_complete = len(completed_online) == expected_online
    frozen_complete = len(completed_frozen) == expected_frozen
    if endpoint_spec is not None:
        online_complete = online_complete and declared_campaign_complete
        frozen_complete = frozen_complete and declared_campaign_complete
    else:
        # Legacy artifacts remain readable for diagnosis, but cannot become
        # confirmatory evidence without the exact dual-endpoint attestations.
        online_complete = False
        frozen_complete = False

    online_task_rows = [row for _, run in completed_online for row in run.task_rows]
    paper_online_task_rows = [
        row for _, run in completed_online for row in run.paper_task_rows
    ]
    control_outcomes = [
        row["control_outcome"]
        for row in online_task_rows
        if row["control_outcome"] is not None
    ]
    candidate_outcomes = [
        row["candidate_outcome"]
        for row in online_task_rows
        if row["candidate_outcome"] is not None
    ]
    outcome_deltas = [
        row["outcome_delta"]
        for row in online_task_rows
        if row["outcome_delta"] is not None
    ]
    score_deltas = [
        row["score_delta"] for row in online_task_rows if row["score_delta"] is not None
    ]
    baseline_outcome = _mean(control_outcomes)
    sage_outcome = _mean(candidate_outcomes)
    paper_control_outcomes = [row["control_outcome"] for row in paper_online_task_rows]
    paper_candidate_outcomes = [
        row["candidate_outcome"] for row in paper_online_task_rows
    ]
    paper_outcome_deltas = [row["outcome_delta"] for row in paper_online_task_rows]
    paper_baseline_outcome = _mean(paper_control_outcomes)
    paper_sage_outcome = _mean(paper_candidate_outcomes)
    paper_outcome_delta = (
        paper_sage_outcome - paper_baseline_outcome
        if paper_sage_outcome is not None and paper_baseline_outcome is not None
        else None
    )
    paper_outcome_lift = _relative_lift(
        paper_sage_outcome,
        paper_baseline_outcome,
    )
    frozen_sage_outcome = _mean(run.candidate_outcome for _, run in completed_frozen)
    overall_outcome_delta = (
        sage_outcome - baseline_outcome
        if sage_outcome is not None and baseline_outcome is not None
        else None
    )
    overall_outcome_lift = _relative_lift(sage_outcome, baseline_outcome)
    historical_paper_candidate_mean: float | None = None
    historical_paper_candidate_minimum: float | None = None
    historical_paper_hybrid_control_mean: float | None = None
    historical_paper_original_control_mean: float | None = None
    if endpoint_spec is not None:
        historical_paper_candidate_mean = _required_unit_float(
            endpoint_spec.historical.get("paper_comparable_candidate_outcome_mean"),
            "historical paper-comparable SAGE mean",
        )
        historical_paper_candidate_minimum = _required_unit_float(
            endpoint_spec.historical.get("paper_comparable_candidate_outcome_minimum"),
            "historical paper-comparable SAGE minimum",
        )
        historical_paper_hybrid_control_mean = _required_unit_float(
            endpoint_spec.historical.get(
                "paper_comparable_hybrid_control_outcome_mean"
            ),
            "historical paper-comparable hybrid-control mean",
        )
        historical_paper_original_control_mean = _required_unit_float(
            endpoint_spec.historical.get(
                "paper_comparable_pure_original_v140_control_outcome_mean"
            ),
            "historical paper-comparable original-control mean",
        )
    paper_candidate_minus_historical_mean = (
        paper_sage_outcome - historical_paper_candidate_mean
        if paper_sage_outcome is not None
        and historical_paper_candidate_mean is not None
        else None
    )
    baseline_score = _mean(
        row["control_score"]
        for row in online_task_rows
        if row["control_score"] is not None
    )
    sage_score = _mean(
        row["candidate_score"]
        for row in online_task_rows
        if row["candidate_score"] is not None
    )
    canonical_lift = _relative_lift(sage_score, baseline_score)

    task_iid_ci = _bootstrap_mean_ci(
        outcome_deltas,
        iterations=bootstrap_iterations,
        seed=seed,
    )
    h2_multiplier = 1.0 + h2_threshold / 100.0
    task_threshold_contrasts = [
        float(row["candidate_outcome"]) - h2_multiplier * float(row["control_outcome"])
        for row in online_task_rows
        if row["control_outcome"] is not None and row["candidate_outcome"] is not None
    ]
    task_iid_threshold_contrast_ci = _bootstrap_mean_ci(
        task_threshold_contrasts,
        iterations=bootstrap_iterations,
        seed=seed + 1,
    )
    online_run_mean_deltas: list[float] = []
    online_run_threshold_contrasts: list[float] = []
    online_run_control_rows: list[list[float]] = []
    online_run_candidate_rows: list[list[float]] = []
    for _, run in completed_online:
        run_pairs = [
            (float(row["control_outcome"]), float(row["candidate_outcome"]))
            for row in run.task_rows
            if row["control_outcome"] is not None
            and row["candidate_outcome"] is not None
        ]
        if run_pairs:
            run_control = [pair[0] for pair in run_pairs]
            run_candidate = [pair[1] for pair in run_pairs]
            online_run_control_rows.append(run_control)
            online_run_candidate_rows.append(run_candidate)
            online_run_mean_deltas.append(
                float(np.mean(np.asarray(run_candidate) - np.asarray(run_control)))
            )
            online_run_threshold_contrasts.append(
                float(
                    np.mean(
                        np.asarray(run_candidate)
                        - h2_multiplier * np.asarray(run_control)
                    )
                )
            )
    common_task_counts = {
        len(row) for row in [*online_run_control_rows, *online_run_candidate_rows]
    }
    if len(common_task_counts) == 1:
        two_way_bootstrap = _two_way_paired_outcome_bootstrap(
            online_run_control_rows,
            online_run_candidate_rows,
            threshold_percent=h2_threshold,
            iterations=bootstrap_iterations,
            seed=seed + 2,
        )
    else:
        two_way_bootstrap = {
            "absolute_difference": (None, None),
            "relative_lift_percent": (None, None),
            "threshold_contrast": (None, None),
        }
    two_way_delta_ci = two_way_bootstrap["absolute_difference"]
    h2_lift_ci = two_way_bootstrap["relative_lift_percent"]
    two_way_threshold_contrast_ci = two_way_bootstrap["threshold_contrast"]
    run_delta_ci = _bootstrap_mean_ci(
        online_run_mean_deltas,
        iterations=bootstrap_iterations,
        seed=seed + 3,
    )
    run_threshold_contrast_ci = _bootstrap_mean_ci(
        online_run_threshold_contrasts,
        iterations=bootstrap_iterations,
        seed=seed + 4,
    )
    task_p = _randomization_p(
        outcome_deltas,
        iterations=randomization_iterations,
        seed=seed + 5,
    )
    task_threshold_p = _randomization_p(
        task_threshold_contrasts,
        iterations=randomization_iterations,
        seed=seed + 6,
    )
    run_delta_p = _randomization_p(
        online_run_mean_deltas,
        iterations=randomization_iterations,
        seed=seed + 7,
    )
    run_threshold_p = _randomization_p(
        online_run_threshold_contrasts,
        iterations=randomization_iterations,
        seed=seed + 8,
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
        seed=seed + 9,
    )
    called_lift_samples: list[float] = []
    if called_rows:
        rng = np.random.default_rng(seed + 10)
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
        seed=seed + 11,
    )

    h1_status = _hypothesis_status(
        value=retention,
        threshold=h1_threshold,
        ci=retention_ci,
        complete=online_complete and frozen_complete,
    )
    h2_threshold_contrast = (
        sage_outcome - h2_multiplier * baseline_outcome
        if sage_outcome is not None and baseline_outcome is not None
        else None
    )
    h2_status = _h2_confirmatory_status(
        lift_percent=overall_outcome_lift,
        threshold_percent=h2_threshold,
        two_way_threshold_contrast_ci=two_way_threshold_contrast_ci,
        run_threshold_contrast_ci=run_threshold_contrast_ci,
        run_threshold_sign_flip_p=run_threshold_p,
        complete=online_complete,
        alpha=0.05,
    )
    h3_status = "descriptive_only" if called_lift is not None else "pending"

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
        _run_detail(
            replicate=replicate,
            online=online,
            frozen=frozen,
            online_inference_eligible=(
                endpoint_spec is not None and online_eligibility[replicate]
            ),
            frozen_inference_eligible=(
                endpoint_spec is not None and frozen_eligibility[replicate]
            ),
            historical_paper_candidate_mean=historical_paper_candidate_mean,
        )
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
    excluded_completed_artifact_count = sum(
        1
        for replicate, online, frozen in loaded_pairs
        for run, eligible in (
            (online, online_eligibility[replicate]),
            (frozen, frozen_eligibility[replicate]),
        )
        if run is not None and run.complete and not eligible
    )
    campaign_inference_complete = (
        online_complete
        and frozen_complete
        and len(loaded_pairs) == expected_online
        and active_run_count == 0
        and excluded_completed_artifact_count == 0
    )
    manifest_status = str(campaign_manifest.get("status") or "")
    status_label = (
        "Legacy / non-confirmatory"
        if endpoint_spec is None
        and any(online or frozen for _, online, frozen in loaded_pairs)
        else "Complete"
        if campaign_inference_complete
        else "Incomplete"
        if manifest_status in {"complete", "incomplete"}
        or excluded_completed_artifact_count
        else "Running"
        if manifest_status == "running"
        or any(online or frozen for _, online, frozen in loaded_pairs)
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
            "analysis_role": "confirmatory_run_paired",
            "decision_rule": {
                "estimate_requirement": f"gain_retention_percent >= {h1_threshold:g}",
                "uncertainty_requirement": (
                    f"run_paired_bootstrap_95_ci_lower >= {h1_threshold:g}"
                ),
                "replication_unit": "paired_online_and_frozen_registry_run",
            },
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
                "Uses the audited v9 all-1,032-task endpoint to compare each "
                "online-build run with a paired frozen-registry run where "
                "generation and repair are disabled."
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
            "title": "SAGE improves audited all-task outcome over baseline",
            "analysis_role": "confirmatory_two_way_run_task_clustered",
            "decision_rule": {
                "target_contrast": (
                    f"candidate_mean - {h2_multiplier:.6g} * control_mean"
                ),
                "estimate_requirement": (
                    f"audited_relative_outcome_lift_percent >= {h2_threshold:g}"
                ),
                "two_way_uncertainty_requirement": (
                    "two_way_run_task_bootstrap_95_ci_lower_for_target_contrast > 0"
                ),
                "run_cluster_requirement": (
                    "run_cluster_bootstrap_95_ci_lower_for_target_contrast > 0"
                ),
                "run_sign_flip_requirement": "two_sided_exact_p < 0.05",
                "replication_unit": "independently_evolved_registry_run",
                "task_unit": "fixed_matched_benchmark_task",
                "iid_task_analysis_role": "descriptive_only",
            },
            "estimate_percent": overall_outcome_lift,
            "confidence_interval": _confidence_interval(
                h2_lift_ci,
                unit="percent",
            ),
            "threshold_percent": h2_threshold,
            "sample_size": len(completed_online),
            "matched_task_observations": len(outcome_deltas),
            "baseline_mean": baseline_outcome,
            "sage_mean": sage_outcome,
            "threshold_contrast": h2_threshold_contrast,
            "two_way_threshold_contrast_ci": _confidence_interval(
                two_way_threshold_contrast_ci,
                unit="score",
            ),
            "run_threshold_contrast_ci": _confidence_interval(
                run_threshold_contrast_ci,
                unit="score",
            ),
            "run_threshold_sign_flip_p": run_threshold_p,
            "decision": h2_status,
            "decision_label": _decision_label(h2_status),
            "value_label": _percent(overall_outcome_lift, signed=True),
            "primary_label": "Across matched tasks, SAGE completed more tasks correctly.",
            "claim_label": (
                "Across the full benchmark, SAGE completes more tasks than the "
                "same LLM agent without autonomous tool generation."
            ),
            "evidence_label": (
                "Compares audited v9 baseline and SAGE outcomes for the same "
                "1,032-task order across all complete replications."
            ),
            "observed_label": f"Observed {_percent(overall_outcome_lift, signed=True)}",
            "threshold_label": f"Target >= {h2_threshold:g}%",
            "fill_position": min(max((overall_outcome_lift or 0.0) * 2.0, 0.0), 100.0),
            "target_position": min(max(h2_threshold * 2.0, 0.0), 100.0),
            "status": h2_status,
            **_detail(
                "hypothesis:h2",
                "Hypothesis 2: Audited v9 all-task outcome lift",
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
                                    "Lift 95% two-way run/task bootstrap CI",
                                    _percent_interval(h2_lift_ci),
                                ),
                                (
                                    "10% target contrast",
                                    _signed(h2_threshold_contrast, 4),
                                ),
                                (
                                    "Decision threshold",
                                    f">= {h2_threshold:g}%",
                                ),
                                ("Independent registry runs", len(completed_online)),
                                ("Matched task observations", len(outcome_deltas)),
                            ]
                        ),
                        "note": (
                            "Support requires the point estimate to reach the target, "
                            "both cluster-aware 95% lower bounds for the target "
                            "contrast to exceed zero, and the two-sided run-level "
                            "sign-flip p-value to be below .05."
                        ),
                    },
                    {
                        "heading": "Confirmatory clustered inference",
                        "rows": _rows(
                            [
                                (
                                    "Two-way target-contrast CI",
                                    _interval(two_way_threshold_contrast_ci),
                                ),
                                (
                                    "Run-cluster target-contrast CI",
                                    _interval(run_threshold_contrast_ci),
                                ),
                                (
                                    "Run-level target-contrast sign flip",
                                    _p_label(run_threshold_p),
                                ),
                                (
                                    "Two-way absolute-difference CI",
                                    _interval(two_way_delta_ci),
                                ),
                            ]
                        ),
                    },
                    {
                        "heading": "Descriptive task-IID analysis",
                        "rows": _rows(
                            [
                                ("Task-IID difference CI", _interval(task_iid_ci)),
                                ("Task-IID sign flip", _p_label(task_p)),
                                (
                                    "Task-IID target-contrast CI",
                                    _interval(task_iid_threshold_contrast_ci),
                                ),
                                (
                                    "Task-IID target-contrast sign flip",
                                    _p_label(task_threshold_p),
                                ),
                                (
                                    "Run-level raw-difference CI",
                                    _interval(run_delta_ci),
                                ),
                                (
                                    "Run-level raw-difference sign flip",
                                    _p_label(run_delta_p),
                                ),
                            ]
                        ),
                        "note": (
                            "These rows describe task-level precision and the raw "
                            "positive-difference contrast. They do not determine "
                            "the confirmatory H2 decision."
                        ),
                    },
                ],
                eyebrow="Primary hypothesis metric",
            ),
        },
        {
            "id": "Hypothesis 3",
            "title": "Outcome lift among generated-tool-called tasks",
            "analysis_role": "selection_conditioned_descriptive_only",
            "causal_attribution_allowed": False,
            "decision_rule": {
                "classification": "descriptive_only_no_hypothesis_support_decision",
                "reason": (
                    "generated-tool-called status is selected after treatment and "
                    "there is no randomized tool-use ablation"
                ),
                "threshold_role": "predeclared_descriptive_reference_only",
            },
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
            "primary_label": "Lift is measured on tasks where the SAGE actor policy called generated tools.",
            "claim_label": (
                "This is a selection-conditioned description of tasks where the "
                "SAGE actor policy selected and called a generated tool."
            ),
            "evidence_label": (
                "Uses audited v9 outcomes on generated-tool-called tasks under "
                "the declared production policy; diagnostic overrides, "
                "scenario-name routing, and synthetic bridge completions are disabled. "
                "It does not establish causal attribution."
            ),
            "observed_label": f"Observed {_percent(called_lift, signed=True)}",
            "threshold_label": f"Descriptive reference: {h3_threshold:g}%",
            "fill_position": min(max(called_lift or 0.0, 0.0), 100.0),
            "target_position": h3_threshold,
            "status": h3_status,
            **_detail(
                "hypothesis:h3",
                "Generated-tool-called task association",
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
                                    "Descriptive reference",
                                    f"{h3_threshold:g}% (not a causal gate)",
                                ),
                                ("Called-task observations", len(called_rows)),
                            ]
                        ),
                        "note": (
                            "Generated-tool-called status is observed after the SAGE "
                            "intervention. Without a randomized tool-use ablation, "
                            "this selected subset can show association but cannot "
                            "identify the generated call as the cause of the outcome."
                        ),
                    }
                ],
                eyebrow="Selection-conditioned descriptive analysis",
            ),
        },
    ]

    audited_declaration = endpoint_spec.audited if endpoint_spec is not None else {}
    paper_declaration = endpoint_spec.paper if endpoint_spec is not None else {}
    audited_endpoint = {
        "metric_field": audited_declaration.get("metric_field", "outcome_similarity"),
        "evaluator_version": audited_declaration.get("evaluator_version"),
        "task_scope": audited_declaration.get("task_scope", "matched_tasks"),
        "task_count_per_run": audited_declaration.get("task_count"),
        "matched_task_observations": len(outcome_deltas),
        "baseline": baseline_outcome,
        "sage": sage_outcome,
        "absolute_difference": overall_outcome_delta,
        "relative_lift_percent": overall_outcome_lift,
        "delta_label": _signed(overall_outcome_delta),
        "lift_label": _percent(overall_outcome_lift, signed=True),
        "analysis_role": "current_same_run_hypothesis_endpoint",
        **_detail(
            "endpoint:audited-current-all-tasks",
            "Audited current endpoint: v9 on all 1,032 tasks",
            [
                {
                    "heading": "Exact endpoint identity",
                    "rows": _rows(
                        [
                            ("Metric field", audited_declaration.get("metric_field")),
                            (
                                "Evaluator version",
                                audited_declaration.get("evaluator_version"),
                            ),
                            (
                                "Tasks per replication",
                                audited_declaration.get("task_count"),
                            ),
                            ("Matched observations", len(outcome_deltas)),
                        ]
                    ),
                    "note": (
                        "This complete-benchmark endpoint supplies the current "
                        "same-run lift, confirmatory H1/H2 analyses, and the "
                        "selection-conditioned descriptive called-task analysis."
                    ),
                },
                {
                    "heading": "Observed current results",
                    "rows": _rows(
                        [
                            ("Fresh baseline mean", baseline_outcome),
                            ("SAGE mean", sage_outcome),
                            ("Absolute difference", _signed(overall_outcome_delta, 4)),
                            (
                                "Relative lift",
                                _percent(overall_outcome_lift, signed=True),
                            ),
                        ]
                    ),
                },
            ],
            eyebrow="Audited outcome endpoint",
        ),
    }
    paper_endpoint = {
        "metric_field": paper_declaration.get(
            "metric_field", "online_feedback_outcome_similarity"
        ),
        "evaluator_version": paper_declaration.get("evaluator_version"),
        "task_scope": paper_declaration.get("task_scope"),
        "task_count_per_run": paper_declaration.get("task_count"),
        "matched_task_observations": len(paper_outcome_deltas),
        "baseline": paper_baseline_outcome,
        "sage": paper_sage_outcome,
        "absolute_difference": paper_outcome_delta,
        "relative_lift_percent": paper_outcome_lift,
        "historical_sage_mean": historical_paper_candidate_mean,
        "historical_sage_minimum": historical_paper_candidate_minimum,
        "historical_hybrid_control_mean": historical_paper_hybrid_control_mean,
        "historical_original_control_mean": historical_paper_original_control_mean,
        "candidate_minus_historical_mean": paper_candidate_minus_historical_mean,
        "delta_label": _signed(paper_outcome_delta),
        "lift_label": _percent(paper_outcome_lift, signed=True),
        "historical_delta_label": _signed(
            paper_candidate_minus_historical_mean,
            4,
        ),
        "analysis_role": "apples_to_apples_historical_comparison_only",
        **_detail(
            "endpoint:paper-comparable-historical-subset",
            "Paper-comparable endpoint: v1 on the exact 800-task subset",
            [
                {
                    "heading": "Exact endpoint identity",
                    "rows": _rows(
                        [
                            ("Metric field", paper_declaration.get("metric_field")),
                            (
                                "Evaluator version",
                                paper_declaration.get("evaluator_version"),
                            ),
                            (
                                "Tasks per replication",
                                paper_declaration.get("task_count"),
                            ),
                            ("Matched observations", len(paper_outcome_deltas)),
                        ]
                    ),
                    "note": (
                        "Only the exact non-null v1 subset in frozen benchmark "
                        "order is included. Values are never mixed with v9."
                    ),
                },
                {
                    "heading": "Apples-to-apples historical comparison",
                    "rows": _rows(
                        [
                            ("Current fresh baseline mean", paper_baseline_outcome),
                            ("Current SAGE mean", paper_sage_outcome),
                            (
                                "Archived paper SAGE mean",
                                historical_paper_candidate_mean,
                            ),
                            (
                                "Current minus archived SAGE mean",
                                _signed(paper_candidate_minus_historical_mean, 4),
                            ),
                        ]
                    ),
                    "note": (
                        "The archived campaign remains provenance-invalid for final "
                        "inference. This is a descriptive comparison under the same "
                        "v1 evaluator and exact ordered 800-task subset."
                    ),
                },
            ],
            eyebrow="Historical-comparison endpoint",
        ),
    }
    performance_endpoints = {
        AUDITED_ENDPOINT_NAME: audited_endpoint,
        PAPER_ENDPOINT_NAME: paper_endpoint,
    }

    performance = {
        "baseline": baseline_outcome,
        "sage": sage_outcome,
        "frozen_sage": frozen_sage_outcome,
        "outcome_delta": overall_outcome_delta,
        "outcome_lift_percent": overall_outcome_lift,
        "canonical_baseline": baseline_score,
        "canonical_sage": sage_score,
        "canonical_delta": _mean(score_deltas),
        "canonical_lift_percent": canonical_lift,
        "delta_label": _signed(overall_outcome_delta),
        "outcome_lift_label": _percent(overall_outcome_lift, signed=True),
        "canonical_lift_label": _percent(canonical_lift, signed=True),
        **_detail(
            "panel:performance",
            "Overall matched performance",
            [
                {
                    "heading": "Audited v9 outcome (all 1,032 tasks per run)",
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
                {
                    "heading": "Canonical/reference score",
                    "rows": _rows(
                        [
                            (
                                "Baseline mean",
                                f"{baseline_score:.4f}"
                                if baseline_score is not None
                                else "-",
                            ),
                            (
                                "SAGE mean",
                                f"{sage_score:.4f}" if sage_score is not None else "-",
                            ),
                            ("Mean paired difference", _signed(_mean(score_deltas), 4)),
                            ("Relative lift", _percent(canonical_lift, signed=True)),
                        ]
                    ),
                    "note": (
                        "Canonical score is descriptive route-compatibility output only; "
                        "it is never a performance or release criterion."
                    ),
                },
            ],
        ),
    }

    baseline_successes = sum(value >= 1.0 - 1e-12 for value in control_outcomes)
    sage_successes = sum(value >= 1.0 - 1e-12 for value in candidate_outcomes)
    statistics = {
        "mean_delta": overall_outcome_delta,
        "analysis_role": "confirmatory_two_way_run_task_clustered",
        "decision_rule": {
            "target_contrast": f"candidate_mean - {h2_multiplier:.6g} * control_mean",
            "two_way_bootstrap_lower_must_exceed": 0.0,
            "run_cluster_bootstrap_lower_must_exceed": 0.0,
            "run_sign_flip_p_must_be_below": 0.05,
            "iid_task_analysis_role": "descriptive_only",
        },
        "h2_threshold_percent": h2_threshold,
        "h2_threshold_multiplier": h2_multiplier,
        "h2_threshold_contrast": h2_threshold_contrast,
        "two_way_run_task_bootstrap_delta_ci": _confidence_interval(
            two_way_delta_ci,
            unit="score",
        ),
        "two_way_run_task_bootstrap_lift_ci": _confidence_interval(
            h2_lift_ci,
            unit="percent",
        ),
        "two_way_run_task_bootstrap_threshold_contrast_ci": _confidence_interval(
            two_way_threshold_contrast_ci,
            unit="score",
        ),
        "run_cluster_threshold_contrast_ci": _confidence_interval(
            run_threshold_contrast_ci,
            unit="score",
        ),
        "run_threshold_contrast_sign_flip_p": run_threshold_p,
        "task_iid_bootstrap_ci": _confidence_interval(task_iid_ci, unit="score"),
        "task_iid_sign_flip_p": task_p,
        "task_iid_threshold_contrast_ci": _confidence_interval(
            task_iid_threshold_contrast_ci,
            unit="score",
        ),
        "task_iid_threshold_contrast_sign_flip_p": task_threshold_p,
        "run_raw_difference_bootstrap_ci": _confidence_interval(
            run_delta_ci,
            unit="score",
        ),
        "run_raw_difference_sign_flip_p": run_delta_p,
        "bootstrap_iterations": bootstrap_iterations,
        "randomization_iterations": randomization_iterations,
        "matched_task_observations": len(outcome_deltas),
        "baseline_successes": baseline_successes,
        "sage_successes": sage_successes,
        "independent_online_runs": len(completed_online),
        "significance_alpha": 0.05,
        "mean_delta_label": _signed(overall_outcome_delta),
        "ci_label": _interval(two_way_threshold_contrast_ci),
        "p_label": _p_label(run_threshold_p),
        "successes_label": f"{baseline_successes:,} / {sage_successes:,}",
        **_detail(
            "panel:statistics",
            "Paired audited-v9 statistical evidence",
            [
                {
                    "heading": "Confirmatory H2 clustered analysis",
                    "rows": _rows(
                        [
                            (
                                f"Threshold contrast (SAGE - {h2_multiplier:.3g} x baseline)",
                                _signed(h2_threshold_contrast, 4),
                            ),
                            (
                                "Two-way run/task contrast 95% CI",
                                _interval(two_way_threshold_contrast_ci, 4),
                            ),
                            (
                                "Run-cluster contrast 95% CI",
                                _interval(run_threshold_contrast_ci, 4),
                            ),
                            (
                                "Run-level contrast sign flip",
                                _p_label(run_threshold_p),
                            ),
                            ("Bootstrap iterations", f"{bootstrap_iterations:,}"),
                            (
                                "Randomization iterations",
                                f"{randomization_iterations:,}",
                            ),
                            ("Matched task observations", f"{len(outcome_deltas):,}"),
                        ]
                    ),
                    "note": (
                        "The contrast tests the predeclared relative-lift target "
                        "directly. H2 support requires both cluster-aware lower "
                        "bounds above zero and the two-sided run-level sign-flip "
                        "p-value below .05."
                    ),
                },
                {
                    "heading": "Descriptive analyses (not decision criteria)",
                    "rows": _rows(
                        [
                            ("Independent online-build runs", len(completed_online)),
                            (
                                "Two-way raw-difference 95% CI",
                                _interval(two_way_delta_ci, 4),
                            ),
                            (
                                "Task-IID difference 95% CI",
                                _interval(task_iid_ci, 4),
                            ),
                            ("Task-IID sign-flip test", _p_label(task_p)),
                            (
                                "Task-IID target-contrast 95% CI",
                                _interval(task_iid_threshold_contrast_ci, 4),
                            ),
                            (
                                "Task-IID target-contrast sign flip",
                                _p_label(task_threshold_p),
                            ),
                            (
                                "Run-level raw-difference 95% CI",
                                _interval(run_delta_ci, 4),
                            ),
                            (
                                "Run-level raw-difference sign flip",
                                _p_label(run_delta_p),
                            ),
                        ]
                    ),
                    "note": (
                        "The task-IID rows do not treat repeated benchmark tasks "
                        "across registries as independent confirmatory evidence."
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
        {"label": "Diagnostic tool-call override checks", "value": force_violations},
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
                            "Diagnostic override variables",
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
            "Policy-directed tool calls",
            f"{tool_totals['policy_directed_calls']:,}",
            "",
            "Matched task scenarios containing a generated-tool call selected by the production actor policy, with diagnostic overrides disabled.",
        ),
        (
            "gains",
            "Called-task gains",
            f"{tool_totals['gains']:,}",
            "green",
            "Generated-tool-called scenarios with positive matched outcome difference; descriptive association only.",
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
            "Called-task regressions",
            f"{tool_totals['regressions']:,}",
            "amber",
            "Generated-tool-called scenarios with negative matched outcome difference; descriptive association only.",
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
        "excluded_completed_artifacts": excluded_completed_artifact_count,
        "inference_complete": campaign_inference_complete,
        "manifest_status": manifest_status,
        "progress_percent": (
            min(100.0, recorded_task_progress / expected_task_progress * 100.0)
            if expected_task_progress
            else 0.0
        ),
        "progress_label": (
            "Legacy artifacts loaded for diagnosis only; dual-endpoint "
            "attestations are absent"
            if endpoint_spec is None
            else f"{complete_run_count} of {expected_run_count} verified runs included"
            + (f" · {active_run_count} active" if active_run_count else "")
            + (
                f" · {excluded_completed_artifact_count} completed artifact(s) excluded"
                if excluded_completed_artifact_count
                else ""
            )
        ),
        "recorded_task_progress": recorded_task_progress,
        "expected_task_progress": expected_task_progress,
        "paired_observations": len(online_task_rows),
        "audited_current_matched_observations": len(online_task_rows),
        "paper_comparable_matched_observations": len(paper_online_task_rows),
        "tasks_per_run": expected_tasks_per_run,
        "updated_at": now.isoformat(),
        "updated_at_label": now.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "benchmark_sha256": benchmark_hash,
        "baseline_cache": str(campaign_manifest.get("baseline_cache") or ""),
        "baseline_cache_policy": str(
            campaign_manifest.get("baseline_cache_policy") or ""
        ),
        "claim_safeguards": dict(campaign_manifest.get("claim_safeguards") or {}),
        "endpoint_policy": (
            "dual_scoped_outcome_endpoints"
            if endpoint_spec is not None
            else "legacy_single_endpoint"
        ),
        "inference_exclusion_reason": (
            None
            if endpoint_spec is not None
            else "missing_dual_endpoint_sample_and_run_attestations"
        ),
        "thresholds_path": (
            str(endpoint_spec.thresholds_path) if endpoint_spec is not None else ""
        ),
        "thresholds_sha256": (
            endpoint_spec.thresholds_sha256 if endpoint_spec is not None else ""
        ),
    }
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "campaign": campaign,
        "hypotheses": hypotheses,
        "performance_endpoints": performance_endpoints,
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
    template = EVIDENCE_TEMPLATE.read_text(encoding="utf-8")
    marker = "__CHAPTER4_EVIDENCE_BASE64__"
    if template.count(marker) != 1:
        raise ValueError("Chapter 4 evidence template embed marker is not exact.")
    embedded = base64.b64encode(
        json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    html = template.replace(marker, embedded)
    payload = json.dumps(data, indent=2, sort_keys=False) + "\n"
    with _DASHBOARD_WRITE_LOCK:
        _atomic_write_text(output_dir / EVIDENCE_DATA_NAME, payload)
        _atomic_write_text(output_dir / EVIDENCE_HTML_NAME, html)
    return data
