"""Build a standalone dashboard for the H1/H2/H3/H4 pilot.

The input is a JSON manifest that may be updated while a run is in progress.
The writer deliberately uses the status label ``Observed`` rather than
``Supported`` for a completed pilot: one registry realization cannot establish
replication-level hypothesis support.
"""

from __future__ import annotations

import hashlib
import html
import json
import math
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from sage_ts.dashboard.hypothesis_pilot_template import HYPOTHESIS_PILOT_HTML

HYPOTHESIS_PILOT_SCHEMA_VERSION = 2
HYPOTHESIS_PILOT_HTML_NAME = "hypothesis_pilot.html"
HYPOTHESIS_PILOT_DATA_NAME = "hypothesis_pilot_data.json"
LATEST_HYPOTHESIS_PILOT_NAME = "latest_sage_ts_hypothesis_pilot.html"

_RUN_STATUSES = {"pending", "running", "complete", "completed", "failed"}
_HYPOTHESIS_STATUSES = {
    "pending",
    "running",
    "complete",
    "completed",
    "observed",
    "failed",
    "failed_integrity",
}
_INTEGRITY_STATUSES = {"pending", "pass", "fail"}


def _load_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Pilot manifest is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Pilot manifest must contain a JSON object: {path}")
    return payload


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _optional_unit_float(value: Any, label: str) -> float | None:
    if value is None:
        return None
    number = _finite_float(value)
    if number is None or not 0.0 <= number <= 1.0:
        raise ValueError(f"{label} must be a finite number within [0, 1]")
    return number


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _rate(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _difference(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


def _relative_lift(treatment: float | None, baseline: float | None) -> float | None:
    if treatment is None or baseline is None or baseline == 0.0:
        return None
    return (treatment - baseline) / baseline


def _ci_pair(value: Any) -> list[float | None]:
    if isinstance(value, Mapping):
        value = [value.get("lower"), value.get("upper")]
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return [None, None]
    return [_finite_float(value[0]), _finite_float(value[1])]


def _validated_status(value: Any, allowed: set[str], label: str) -> str:
    status = str(value or "pending").lower()
    if status not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"{label} must be one of: {choices}")
    return status


def _normalise_integrity(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, Mapping) else {}
    status = _validated_status(
        raw.get("status"), _INTEGRITY_STATUSES, "integrity.status"
    )
    checks: list[dict[str, str]] = []
    raw_checks = raw.get("checks")
    if isinstance(raw_checks, list):
        for index, item in enumerate(raw_checks):
            if not isinstance(item, Mapping):
                continue
            label = str(item.get("label") or item.get("name") or f"Check {index + 1}")
            check_status_raw = item.get("status")
            if check_status_raw is None and isinstance(item.get("passed"), bool):
                check_status_raw = "pass" if item["passed"] else "fail"
            check_status = _validated_status(
                check_status_raw,
                _INTEGRITY_STATUSES,
                f"integrity.checks[{index}].status",
            )
            checks.append(
                {
                    "label": label,
                    "status": check_status,
                    "detail": str(item.get("detail") or ""),
                }
            )
    return {"status": status, "checks": checks}


def _normalise_pilot_gate(
    raw: Mapping[str, Any], *, hypothesis: str
) -> tuple[str, str]:
    nested = raw.get("pilot_gate")
    gate = nested if isinstance(nested, Mapping) else {}
    outcome_raw = raw.get("pilot_gate_outcome", gate.get("outcome"))
    if outcome_raw is None:
        outcome_raw = raw.get("pilot_gate_passed", gate.get("passed"))
    if isinstance(outcome_raw, bool):
        outcome = "cleared" if outcome_raw else "not_cleared"
    else:
        outcome = str(outcome_raw or "pending")

    label = str(raw.get("pilot_gate_label") or gate.get("label") or "")
    if not label:
        label = {
            "cleared": "PILOT_THRESHOLD_CLEARED",
            "not_cleared": "PILOT_THRESHOLD_NOT_CLEARED",
            "integrity_failure": "INTEGRITY_FAILURE",
            "pending": "PENDING",
            "running": "RUNNING",
        }.get(outcome.lower(), outcome.upper())
    decision_text = f"{outcome} {label}".upper()
    if "SUPPORTED" in decision_text or "REJECTED" in decision_text:
        raise ValueError(
            f"{hypothesis} pilot gate may not use confirmatory "
            "Supported/Rejected labels"
        )
    return outcome, label


def _normalise_descriptive_canonical_similarity(
    value: Any,
    *,
    treatment_key: str,
    baseline_key: str,
    count_keys: tuple[str, ...],
) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("descriptive_canonical_similarity must be a JSON object")
    role = str(value.get("role") or "")
    if role != "descriptive_not_primary":
        raise ValueError("Canonical similarity must be labeled descriptive_not_primary")
    treatment = _optional_unit_float(
        value.get(treatment_key),
        f"descriptive_canonical_similarity.{treatment_key}",
    )
    baseline = _optional_unit_float(
        value.get(baseline_key),
        f"descriptive_canonical_similarity.{baseline_key}",
    )
    raw_difference = value.get("mean_difference")
    difference = _finite_float(raw_difference)
    if raw_difference is not None and difference is None:
        raise ValueError(
            "descriptive_canonical_similarity.mean_difference must be finite"
        )
    if difference is None:
        difference = _difference(treatment, baseline)
    elif (
        treatment is not None
        and baseline is not None
        and not math.isclose(difference, treatment - baseline, abs_tol=1e-12)
    ):
        raise ValueError(
            "descriptive_canonical_similarity.mean_difference disagrees with means"
        )
    normalized: dict[str, Any] = {
        "role": role,
        treatment_key: treatment,
        baseline_key: baseline,
        "mean_difference": difference,
    }
    for key in count_keys:
        normalized[key] = _nonnegative_int(value.get(key))
    return normalized


def _normalise_h1(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, Mapping) else {}
    passed = _nonnegative_int(raw.get("blind_cases_passed"))
    total = _nonnegative_int(raw.get("blind_cases_total"))
    accepted = _nonnegative_int(raw.get("accepted_tools"))
    evaluated = _nonnegative_int(raw.get("evaluated_tools"))
    case_rate = _finite_float(raw.get("case_weighted_pass_rate"))
    coverage = _finite_float(raw.get("tool_coverage_rate"))
    pilot_gate_outcome, pilot_gate_label = _normalise_pilot_gate(raw, hypothesis="H1")
    return {
        "status": _validated_status(
            raw.get("status"), _HYPOTHESIS_STATUSES, "h1.status"
        ),
        "blind_cases_passed": passed,
        "blind_cases_total": total,
        "case_weighted_pass_rate": case_rate
        if case_rate is not None
        else _rate(passed, total),
        "accepted_tools": accepted,
        "evaluated_tools": evaluated,
        "tool_coverage_rate": coverage
        if coverage is not None
        else _rate(evaluated, accepted),
        "tool_weighted_pass_rate": _finite_float(raw.get("tool_weighted_pass_rate")),
        "clopper_pearson_lower_bound": _optional_unit_float(
            raw.get("clopper_pearson_lower_bound"),
            "h1.clopper_pearson_lower_bound",
        ),
        "pilot_gate_outcome": pilot_gate_outcome,
        "pilot_gate_label": pilot_gate_label,
        "method_note": str(raw.get("method_note") or ""),
        "integrity": _normalise_integrity(raw.get("integrity")),
    }


def _normalise_h2(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, Mapping) else {}
    control = _finite_float(raw.get("control_mean"))
    sage = _finite_float(raw.get("integrated_sage_mean"))
    difference = _finite_float(raw.get("mean_difference"))
    lift = _finite_float(raw.get("relative_lift"))
    pilot_gate_outcome, pilot_gate_label = _normalise_pilot_gate(raw, hypothesis="H2")
    return {
        "status": _validated_status(
            raw.get("status"), _HYPOTHESIS_STATUSES, "h2.status"
        ),
        "control_mean": control,
        "integrated_sage_mean": sage,
        "mean_difference": difference
        if difference is not None
        else _difference(sage, control),
        "relative_lift": lift if lift is not None else _relative_lift(sage, control),
        "cluster_ci_95": _ci_pair(raw.get("cluster_ci_95")),
        "stem_clusters": _nonnegative_int(raw.get("stem_clusters")),
        "independent_registry_runs": _nonnegative_int(
            raw.get("independent_registry_runs")
        ),
        "tasks": _nonnegative_int(raw.get("tasks")),
        "evidence_role": str(raw.get("evidence_role") or "pilot_observation"),
        "paper_decision": str(raw.get("paper_decision") or ""),
        "pilot_gate_outcome": pilot_gate_outcome,
        "pilot_gate_label": pilot_gate_label,
        "descriptive_canonical_similarity": (
            _normalise_descriptive_canonical_similarity(
                raw.get("descriptive_canonical_similarity"),
                treatment_key="integrated_sage_mean",
                baseline_key="control_mean",
                count_keys=("tasks",),
            )
        ),
        "method_note": str(raw.get("method_note") or ""),
        "integrity": _normalise_integrity(raw.get("integrity")),
    }


def _normalise_h3(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, Mapping) else {}
    available = _finite_float(raw.get("registry_available_mean"))
    masked = _finite_float(raw.get("registry_masked_mean"))
    difference = _finite_float(raw.get("itt_mean_difference"))
    allocation_raw = raw.get("allocation")
    allocation = allocation_raw if isinstance(allocation_raw, Mapping) else {}
    pilot_gate_outcome, pilot_gate_label = _normalise_pilot_gate(raw, hypothesis="H3")
    return {
        "status": _validated_status(
            raw.get("status"), _HYPOTHESIS_STATUSES, "h3.status"
        ),
        "registry_available_mean": available,
        "registry_masked_mean": masked,
        "itt_mean_difference": difference
        if difference is not None
        else _difference(available, masked),
        "cluster_ci_95": _ci_pair(raw.get("cluster_ci_95")),
        "p_value": _finite_float(raw.get("p_value")),
        "p_value_note": str(raw.get("p_value_note") or "restricted randomization test"),
        "available_tasks": _nonnegative_int(raw.get("available_tasks")),
        "masked_tasks": _nonnegative_int(raw.get("masked_tasks")),
        "stem_clusters": _nonnegative_int(raw.get("stem_clusters")),
        "pilot_gate_outcome": pilot_gate_outcome,
        "pilot_gate_label": pilot_gate_label,
        "descriptive_canonical_similarity": (
            _normalise_descriptive_canonical_similarity(
                raw.get("descriptive_canonical_similarity"),
                treatment_key="registry_available_mean",
                baseline_key="registry_masked_mean",
                count_keys=("available_tasks", "masked_tasks"),
            )
        ),
        "allocation": {
            "seed": allocation.get("seed"),
            "sha256": str(allocation.get("sha256") or ""),
            "stratification": str(allocation.get("stratification") or ""),
        },
        "method_note": str(raw.get("method_note") or ""),
        "integrity": _normalise_integrity(raw.get("integrity")),
    }


def _normalise_h4(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, Mapping) else {}
    available = _finite_float(raw.get("frozen_available_mean"))
    masked = _finite_float(raw.get("registry_masked_mean"))
    difference = _finite_float(raw.get("mean_difference"))
    lift = _finite_float(raw.get("relative_lift"))
    split_raw = raw.get("split")
    split = split_raw if isinstance(split_raw, Mapping) else {}
    pilot_gate_outcome, pilot_gate_label = _normalise_pilot_gate(raw, hypothesis="H4")
    return {
        "status": _validated_status(
            raw.get("status"), _HYPOTHESIS_STATUSES, "h4.status"
        ),
        "exploratory_alternate": True,
        "discovery_tasks": _nonnegative_int(raw.get("discovery_tasks")),
        "discovery_stems": _nonnegative_int(raw.get("discovery_stems")),
        "heldout_tasks": _nonnegative_int(raw.get("heldout_tasks")),
        "heldout_stems": _nonnegative_int(raw.get("heldout_stems")),
        "frozen_available_mean": available,
        "registry_masked_mean": masked,
        "mean_difference": difference
        if difference is not None
        else _difference(available, masked),
        "relative_lift": lift
        if lift is not None
        else _relative_lift(available, masked),
        "cluster_ci_95": _ci_pair(raw.get("cluster_ci_95")),
        "split_seed": raw.get("split_seed", split.get("seed")),
        "split_sha256": str(raw.get("split_sha256") or split.get("sha256") or ""),
        "pilot_gate_outcome": pilot_gate_outcome,
        "pilot_gate_label": pilot_gate_label,
        "descriptive_canonical_similarity": (
            _normalise_descriptive_canonical_similarity(
                raw.get("descriptive_canonical_similarity"),
                treatment_key="registry_available_mean",
                baseline_key="registry_masked_mean",
                count_keys=("available_tasks", "masked_tasks"),
            )
        ),
        "method_note": str(raw.get("method_note") or ""),
        "integrity": _normalise_integrity(raw.get("integrity")),
    }


def _artifact_href(
    raw_path: str, *, manifest_dir: Path, output_dir: Path
) -> tuple[str, bool]:
    parsed = urlparse(raw_path)
    if parsed.scheme in {"http", "https"}:
        return raw_path, True
    artifact_path = Path(raw_path)
    if not artifact_path.is_absolute():
        artifact_path = manifest_dir / artifact_path
    resolved = artifact_path.resolve()
    return os.path.relpath(resolved, output_dir.resolve()), resolved.exists()


def _normalise_artifacts(
    value: Any, *, manifest_dir: Path, output_dir: Path
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    artifacts: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            continue
        raw_path = item.get("path") or item.get("href")
        if not isinstance(raw_path, str) or not raw_path:
            continue
        href, exists = _artifact_href(
            raw_path,
            manifest_dir=manifest_dir,
            output_dir=output_dir,
        )
        artifacts.append(
            {
                "label": str(item.get("label") or f"Artifact {index + 1}"),
                "kind": str(item.get("kind") or "artifact"),
                "path": raw_path,
                "href": href,
                "exists": exists,
            }
        )
    return artifacts


def build_hypothesis_pilot_payload(
    manifest: Mapping[str, Any],
    *,
    manifest_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Validate and normalize the mutable pilot manifest for display."""

    status = _validated_status(manifest.get("status"), _RUN_STATUSES, "status")
    h1 = _normalise_h1(manifest.get("h1"))
    h2 = _normalise_h2(manifest.get("h2"))
    h3 = _normalise_h3(manifest.get("h3"))
    h4 = _normalise_h4(manifest.get("h4"))
    failed_integrity = any(
        hypothesis["integrity"]["status"] == "fail" for hypothesis in (h1, h2, h3, h4)
    )
    progress_stage = _nonnegative_int(manifest.get("progress_stage"))
    return {
        "schema_version": HYPOTHESIS_PILOT_SCHEMA_VERSION,
        "pilot_id": str(manifest.get("pilot_id") or manifest_path.parent.name),
        "study_label": str(manifest.get("study_label") or "one complete run"),
        "status": status,
        "integrity_status": "fail" if failed_integrity else "pass",
        "progress_stage": min(progress_stage or 0, 5),
        "generated_at": datetime.now(UTC).isoformat(),
        "source_manifest": str(manifest_path.resolve()),
        "source_manifest_sha256": _sha256(manifest_path),
        "h1": h1,
        "h2": h2,
        "h3": h3,
        "h4": h4,
        "artifacts": _normalise_artifacts(
            manifest.get("artifacts"),
            manifest_dir=manifest_path.parent,
            output_dir=output_dir,
        ),
    }


def _embedded_json(payload: Mapping[str, Any]) -> str:
    # Escaping angle brackets prevents a manifest string from closing the script tag.
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def write_latest_hypothesis_pilot_pointer(
    dashboard_path: Path,
    *,
    latest_path: Path,
) -> Path:
    """Atomically write a small relative redirect to the newest pilot dashboard."""

    dashboard = dashboard_path.resolve()
    target = os.path.relpath(dashboard, latest_path.parent.resolve())
    escaped_target = html.escape(target, quote=True)
    redirect = f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\">
<meta http-equiv=\"refresh\" content=\"0; url={escaped_target}\">
<title>Latest SAGE hypothesis pilot</title></head>
<body><p>Opening <a href=\"{escaped_target}\">latest SAGE hypothesis pilot</a>…</p></body></html>
"""
    _atomic_write_text(latest_path, redirect)
    return latest_path


def write_hypothesis_pilot_dashboard(
    *,
    manifest_path: Path,
    output_dir: Path,
    latest_path: Path | None = None,
) -> dict[str, Any]:
    """Write the JSON evidence view and self-contained HTML dashboard."""

    manifest_path = manifest_path.resolve()
    output_dir = output_dir.resolve()
    manifest = _load_object(manifest_path)
    payload = build_hypothesis_pilot_payload(
        manifest,
        manifest_path=manifest_path,
        output_dir=output_dir,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    data_path = output_dir / HYPOTHESIS_PILOT_DATA_NAME
    dashboard_path = output_dir / HYPOTHESIS_PILOT_HTML_NAME
    _atomic_write_text(
        data_path,
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )
    dashboard_html = HYPOTHESIS_PILOT_HTML.replace(
        "__PILOT_DATA__", _embedded_json(payload)
    )
    _atomic_write_text(dashboard_path, dashboard_html)
    if latest_path is not None:
        write_latest_hypothesis_pilot_pointer(
            dashboard_path,
            latest_path=latest_path.resolve(),
        )
    return payload


__all__ = [
    "HYPOTHESIS_PILOT_DATA_NAME",
    "HYPOTHESIS_PILOT_HTML_NAME",
    "LATEST_HYPOTHESIS_PILOT_NAME",
    "build_hypothesis_pilot_payload",
    "write_hypothesis_pilot_dashboard",
    "write_latest_hypothesis_pilot_pointer",
]
