#!/usr/bin/env python3
"""Create and update the auditable H1--H4 pilot manifest and dashboards."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from sage_ts.dashboard.hypothesis_pilot import write_hypothesis_pilot_dashboard

REPO_ROOT = Path(__file__).resolve().parents[1]
_HYPOTHESES = ("h1", "h2", "h3", "h4")
_RUN_STATUSES = frozenset({"pending", "running", "complete", "failed"})
_HYPOTHESIS_STATUSES = frozenset({"pending", "running", "observed", "failed_integrity"})
_PILOT_GATE_LABELS = {
    "cleared": "PILOT_THRESHOLD_CLEARED",
    "not_cleared": "PILOT_THRESHOLD_NOT_CLEARED",
    "integrity_failure": "INTEGRITY_FAILURE",
}
_H3_REQUIRED_TRUE_INTEGRITY = (
    "complete_itt_roster",
    "one_result_per_randomized_scenario",
    "assignment_id_recorded_per_scenario",
    "identical_wrapper_and_native_inventory",
    "registry_source_unchanged",
    "registry_copy_unchanged",
    "generator_disabled",
    "reflection_repair_lifecycle_disabled",
)
_H4_REQUIRED_TRUE_INTEGRITY = (
    "complete_rosters",
    "source_disjoint_stems",
    "design_hash_verified",
    "execution_order_hashes_verified",
    "immutable_equal_registry_copies",
    "identical_runtime_and_native_inventory",
    "masked_zero_generated_exposure",
    "masked_zero_generated_calls",
    "available_generated_exposure_positive",
    "held_out_arms_concurrent",
    "zero_runtime_exceptions",
    "frozen_phase_generation_repair_reflection_lifecycle_disabled",
)
_PHASE_HYPOTHESIS = {
    "h1_blind_audit": "h1",
    "h3_randomized_availability": "h3",
    "h4_split": "h4",
}
_PREDECESSORS = {
    "h1": ("h2",),
    "h2": (),
    "h3": ("h2", "h1"),
    "h4": ("h2", "h1", "h3"),
}
_RUNNING_PROGRESS = {"h2": 1, "h1": 2, "h3": 3, "h4": 4}
SEQUENTIAL_STUDY_MODE = "sequential_h1_h2_h3_h4"
STANDALONE_H4_STUDY_MODE = "standalone_h4_parallel"
_STUDY_MODES = frozenset({SEQUENTIAL_STUDY_MODE, STANDALONE_H4_STUDY_MODE})

# Immutable Chapter 4 evidence adopted by ``bind-paper-h2``. These hashes are
# pinned so a similarly shaped but different campaign cannot be substituted.
_PAPER_H2_SELECTED_MANIFEST_SHA256 = (
    "8cd359bebdc0f3576643d6d4850f0abe09fd3c05dafd50a62fc07d62c6425192"
)
_PAPER_H2_VERIFICATION_SHA256 = (
    "b1f563452b404b21949cae6c4783bc6777cdad5ba0a471b7bd16f250e8dd0b90"
)
_PAPER_H2_DASHBOARD_DATA_SHA256 = (
    "e1512f8ea256a7654c3a8e1ade31d495065ef783b60d1a97599f6f52620d2813"
)
_PAPER_H2_RUNTIME_COMMIT = "4ce1c6de0ab36dd59e1a319f4e56e298133f4a79"
_PAPER_H2_RUNTIME_TREE = "4640019c7a054d4af6a500e7327ebbd0a507bfc5"
_PAPER_H2_REP01_REGISTRY_CONTENT_SHA256 = (
    "7943225668a3dba1a0e5b24e387adf37fe1d9c5de6e22a6e020dc6c59b531011"
)
_PAPER_H2_REP01_REGISTRY_MANIFEST_SHA256 = (
    "58d7d6b2eca6b908bb78da736e69b4553d9f4c9e600fe3ac30d3ae00bd595bfc"
)
_PAPER_H2_REP01_CONTROL_SHA256 = (
    "8e988f0c55892ce884b12872af4e6e89c06f7aeac49ec337bca5d67aa1037af8"
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _registry_content_identity(registry_dir: Path) -> dict[str, Any]:
    registry_dir = registry_dir.resolve()
    if not registry_dir.is_dir():
        raise ValueError(f"Frozen registry directory is missing: {registry_dir}")
    files: dict[str, dict[str, Any]] = {}
    for path in sorted(registry_dir.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise ValueError(f"Frozen registry contains a symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"Frozen registry contains a non-regular file: {path}")
        files[path.relative_to(registry_dir).as_posix()] = {
            "sha256": _file_sha256(path),
            "size_bytes": path.stat().st_size,
        }
    if "registry_manifest.json" not in files:
        raise ValueError("Frozen registry has no registry_manifest.json.")
    content_sha256 = hashlib.sha256(
        json.dumps(
            files,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "path": str(registry_dir),
        "content_sha256": content_sha256,
        "manifest_sha256": files["registry_manifest.json"]["sha256"],
        "file_count": len(files),
        "files": files,
    }


def _verified_git_identity() -> dict[str, str]:
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=REPO_ROOT,
        text=True,
    )
    if status.strip():
        raise ValueError("Pilot initialization requires a clean Git worktree.")
    return {
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        "git_tree": subprocess.check_output(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=REPO_ROOT, text=True
        ).strip(),
        "git_status": "clean",
    }


def _manifest_git_identity(manifest: Mapping[str, Any]) -> dict[str, str]:
    provenance = _mapping(manifest.get("provenance"), "Pilot provenance")
    commit = str(provenance.get("git_commit") or "")
    tree = str(provenance.get("git_tree") or "")
    status = str(provenance.get("git_status") or "")
    if not commit or not tree or status != "clean":
        raise ValueError("Pilot manifest has no valid clean Git identity.")
    return {"git_commit": commit, "git_tree": tree, "git_status": status}


def _require_manifest_git_identity(
    manifest: Mapping[str, Any],
    *,
    observed: Mapping[str, Any] | None = None,
    label: str = "current source",
) -> dict[str, str]:
    """Require one clean commit/tree across every phase of the pilot."""

    expected = _manifest_git_identity(manifest)
    raw_observed = observed if observed is not None else _verified_git_identity()
    nested_provenance = raw_observed.get("publication_provenance")
    nested_clean = (
        nested_provenance.get("git_clean")
        if isinstance(nested_provenance, Mapping)
        else None
    )
    normalized = {
        "git_commit": str(raw_observed.get("git_commit") or ""),
        "git_tree": str(raw_observed.get("git_tree") or ""),
        "git_status": (
            "clean"
            if raw_observed.get("git_clean") is True or nested_clean is True
            else str(raw_observed.get("git_status") or "")
        ),
    }
    if normalized != expected:
        raise ValueError(
            f"{label} Git identity differs from the pilot's locked commit/tree."
        )
    return normalized


def _require_phase_ready(
    manifest: Mapping[str, Any], hypothesis: str, *, require_running: bool
) -> None:
    if manifest.get("status") != "running":
        raise ValueError("Pilot must be running before a hypothesis phase can execute.")
    study_mode = str(manifest.get("study_mode") or SEQUENTIAL_STUDY_MODE)
    if study_mode not in _STUDY_MODES:
        raise ValueError(f"Unknown pilot study mode: {study_mode!r}.")
    if study_mode == STANDALONE_H4_STUDY_MODE and hypothesis != "h4":
        raise ValueError("A standalone H4 pilot may execute only H4.")
    predecessors = (
        ()
        if study_mode == STANDALONE_H4_STUDY_MODE and hypothesis == "h4"
        else _PREDECESSORS[hypothesis]
    )
    for predecessor in predecessors:
        predecessor_state = _mapping(
            manifest.get(predecessor), f"{predecessor.upper()} pilot state"
        )
        if predecessor_state.get("status") != "observed":
            raise ValueError(
                f"{hypothesis.upper()} requires {predecessor.upper()} to be observed."
            )
    current = _mapping(manifest.get(hypothesis), f"{hypothesis.upper()} pilot state")
    expected = "running" if require_running else "pending"
    if current.get("status") != expected:
        raise ValueError(f"{hypothesis.upper()} must be {expected} at this transition.")
    for other in _HYPOTHESES:
        if other == hypothesis:
            continue
        other_state = _mapping(manifest.get(other), f"{other.upper()} pilot state")
        if other_state.get("status") == "running":
            raise ValueError(
                f"{hypothesis.upper()} cannot overlap running {other.upper()}."
            )


def _read_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read JSON object: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
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
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _artifact(path: Path, label: str, kind: str) -> dict[str, Any]:
    resolved = path.resolve()
    return {
        "path": str(resolved),
        "label": label,
        "kind": kind,
        "sha256": _file_sha256(resolved) if resolved.is_file() else None,
    }


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a JSON object.")
    return value


def _finite_float(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite number.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite number.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number.")
    return number


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer.")
    return int(value)


def _ci_pair(value: Any, label: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{label} must contain exactly two bounds.")
    bounds = [
        _finite_float(value[0], f"{label} lower bound"),
        _finite_float(value[1], f"{label} upper bound"),
    ]
    if bounds[0] > bounds[1]:
        raise ValueError(f"{label} bounds are reversed.")
    return bounds


def _integrity_passed(value: Any, label: str) -> tuple[bool, Mapping[str, Any]]:
    raw = _mapping(value, f"{label}.integrity")
    declared_status = raw.get("status")
    declared_passed = raw.get("passed")
    status_passed: bool | None = None
    if declared_status is not None:
        status = str(declared_status).lower()
        if status not in {"pass", "fail"}:
            raise ValueError(f"{label}.integrity.status must be pass or fail.")
        status_passed = status == "pass"
    if declared_passed is not None and not isinstance(declared_passed, bool):
        raise ValueError(f"{label}.integrity.passed must be boolean.")
    if (
        status_passed is not None
        and declared_passed is not None
        and status_passed != declared_passed
    ):
        raise ValueError(f"{label} integrity declarations disagree.")
    if status_passed is None and declared_passed is None:
        raise ValueError(f"{label} result does not declare integrity pass/fail.")
    return (
        status_passed if status_passed is not None else bool(declared_passed),
        raw,
    )


def _integrity_checks(
    raw: Mapping[str, Any], *, expected_false: frozenset[str] = frozenset()
) -> list[dict[str, str]]:
    projected: list[dict[str, str]] = []
    checks = raw.get("checks")
    if isinstance(checks, list):
        for index, item in enumerate(checks):
            if not isinstance(item, Mapping):
                raise ValueError(f"integrity.checks[{index}] must be an object.")
            passed = item.get("passed")
            status = item.get("status")
            if isinstance(passed, bool):
                normalized = "pass" if passed else "fail"
            elif str(status).lower() in {"pass", "fail"}:
                normalized = str(status).lower()
            else:
                raise ValueError(f"integrity.checks[{index}] must declare pass/fail.")
            projected.append(
                {
                    "label": str(
                        item.get("label") or item.get("name") or f"Check {index + 1}"
                    ),
                    "status": normalized,
                    "detail": str(item.get("detail") or ""),
                }
            )
    for key, value in raw.items():
        if key in {"status", "passed", "checks", "valid"}:
            continue
        if isinstance(value, bool):
            check_passed = not value if key in expected_false else value
            projected.append(
                {
                    "label": key.replace("_", " "),
                    "status": "pass" if check_passed else "fail",
                    "detail": "",
                }
            )
    return projected


def _require_integrity_checks_pass(checks: list[dict[str, str]], label: str) -> None:
    if any(check["status"] != "pass" for check in checks):
        raise ValueError(f"{label} declares passing integrity with a failed check.")


def _declared_gate_label(report: Mapping[str, Any]) -> str | None:
    nested_raw = report.get("pilot_gate")
    nested = nested_raw if isinstance(nested_raw, Mapping) else {}
    candidates = (
        report.get("pilot_gate_label"),
        report.get("status_label"),
        nested.get("label"),
        nested.get("decision"),
    )
    for candidate in candidates:
        if candidate is not None:
            return str(candidate).upper()
    return None


def _validated_gate(
    report: Mapping[str, Any], *, integrity_passed: bool, threshold_cleared: bool
) -> tuple[str, str]:
    outcome = (
        "integrity_failure"
        if not integrity_passed
        else "cleared"
        if threshold_cleared
        else "not_cleared"
    )
    label = _PILOT_GATE_LABELS[outcome]
    declared = _declared_gate_label(report)
    if declared is not None:
        if "SUPPORTED" in declared or "REJECTED" in declared:
            raise ValueError(
                "Pilot results may not use confirmatory Supported/Rejected labels."
            )
        if declared not in set(_PILOT_GATE_LABELS.values()):
            raise ValueError(f"Unrecognized pilot decision label: {declared}")
        if declared != label:
            raise ValueError(
                f"Declared pilot decision {declared} disagrees with {label}."
            )
    return outcome, label


def _project_h1(report: Mapping[str, Any]) -> dict[str, Any]:
    if report.get("report_type") != "blind_functional_validity_audit":
        raise ValueError("H1 report type is not a blind functional-validity audit.")
    report_status = report.get("status")
    if report_status not in {"complete", "invalid"}:
        raise ValueError("H1 report status must be complete or invalid.")
    endpoint = _mapping(report.get("endpoint_result"), "H1 endpoint_result")
    integrity_raw = report.get("integrity")
    if integrity_raw is None and report_status == "invalid":
        integrity: Mapping[str, Any] = {}
    else:
        integrity = _mapping(integrity_raw, "H1 integrity")
    case_bank = _mapping(report.get("case_bank"), "H1 case_bank")
    immutability = _mapping(
        report.get("registry_immutability"), "H1 registry_immutability"
    )
    integrity_valid = integrity.get("valid", False)
    if not isinstance(integrity_valid, bool):
        raise ValueError("H1 integrity.valid must be boolean.")
    evidence_valid = bool(
        report_status == "complete"
        and integrity_valid
        and endpoint.get("estimable") is True
        and case_bank.get("hash_verified") is True
        and immutability.get("immutable") is True
    )

    accepted = _nonnegative_int(endpoint.get("active_tool_count"), "H1 active tools")
    passed_tools = _nonnegative_int(
        endpoint.get("passing_tool_count"), "H1 passing tools"
    )
    total_cases = _nonnegative_int(endpoint.get("case_count", 0), "H1 blind cases")
    passed_cases = _nonnegative_int(
        endpoint.get("passing_case_count", 0), "H1 passing blind cases"
    )
    if passed_tools > accepted or passed_cases > total_cases:
        raise ValueError("H1 passing counts exceed their denominators.")
    tool_rate_raw = endpoint.get("tool_weighted_validity_rate")
    tool_rate = (
        _finite_float(tool_rate_raw, "H1 tool-weighted pass rate")
        if tool_rate_raw is not None
        else None
    )
    expected_tool_rate = passed_tools / accepted if accepted else None
    if (
        tool_rate is not None
        and expected_tool_rate is not None
        and not math.isclose(tool_rate, expected_tool_rate, abs_tol=1e-12)
    ):
        raise ValueError("H1 tool-weighted rate disagrees with its counts.")

    tools = _mapping(report.get("tools"), "H1 tools")
    tool_count_consistent = len(tools) == accepted
    reported_tool_passes = 0
    reported_case_count = 0
    reported_passing_cases = 0
    for tool_name, raw_tool in tools.items():
        if not isinstance(raw_tool, Mapping):
            raise ValueError(f"H1 tool result {tool_name!r} must be an object.")
        tool_passed = raw_tool.get("passed")
        if not isinstance(tool_passed, bool):
            raise ValueError(f"H1 tool {tool_name!r} must declare passed as boolean.")
        reported_tool_passes += int(tool_passed)
        reported_case_count += _nonnegative_int(
            raw_tool.get("case_count"), f"H1 tool {tool_name!r} case count"
        )
        reported_passing_cases += _nonnegative_int(
            raw_tool.get("passing_case_count"),
            f"H1 tool {tool_name!r} passing case count",
        )
    tool_count_consistent = bool(
        tool_count_consistent
        and reported_tool_passes == passed_tools
        and reported_case_count == total_cases
        and reported_passing_cases == passed_cases
    )
    evidence_valid = evidence_valid and tool_count_consistent
    evaluated = sum(
        1
        for value in tools.values()
        if isinstance(value, Mapping)
        and isinstance(value.get("case_count"), int)
        and value["case_count"] > 0
    )
    coverage = evaluated / accepted if accepted else None
    admission_overlap = _nonnegative_int(
        integrity.get("admission_input_overlap_count", 0),
        "H1 admission overlap count",
    )
    critical_prefixes = (
        "native_action_call_not_permitted",
        "native_action_call_not_declared",
        "native_action_in_loop",
        "native_action_call_count",
        "native_action_name",
        "native_action_arguments_invalid",
        "native_action_arguments_mismatch",
        "native_action_nondeterministic",
    )
    critical_errors: list[str] = []
    for tool_name, raw_tool in tools.items():
        assert isinstance(raw_tool, Mapping)
        error_groups: list[Any] = [raw_tool.get("static_safety_errors", [])]
        raw_cases = raw_tool.get("case_results", [])
        if not isinstance(raw_cases, list):
            raise ValueError(f"H1 tool {tool_name!r} case_results must be a list.")
        error_groups.extend(
            case.get("errors", []) for case in raw_cases if isinstance(case, Mapping)
        )
        for error_group in error_groups:
            if not isinstance(error_group, list):
                continue
            for error in error_group:
                token = str(error)
                if token.startswith(critical_prefixes):
                    critical_errors.append(f"{tool_name}:{token}")

    cp = _mapping(endpoint.get("clopper_pearson"), "H1 clopper_pearson")
    cp_lower_raw = cp.get("lower_bound")
    cp_lower = (
        _finite_float(cp_lower_raw, "H1 Clopper-Pearson lower bound")
        if cp_lower_raw is not None
        else None
    )
    threshold_cleared = bool(
        evidence_valid
        and accepted >= 20
        and coverage == 1.0
        and tool_rate is not None
        and tool_rate >= 0.90
        and admission_overlap == 0
        and not critical_errors
    )
    outcome, label = _validated_gate(
        report, integrity_passed=evidence_valid, threshold_cleared=threshold_cleared
    )
    checks = [
        ("audit report complete", report_status == "complete"),
        ("endpoint estimable", endpoint.get("estimable") is True),
        ("case-bank hash verified", case_bank.get("hash_verified") is True),
        ("registry immutable", immutability.get("immutable") is True),
        ("audit integrity valid", integrity_valid),
        ("endpoint counts match tool rows", tool_count_consistent),
        ("zero admission overlap", admission_overlap == 0),
    ]
    return {
        "status": "observed" if evidence_valid else "failed_integrity",
        "blind_cases_passed": passed_cases,
        "blind_cases_total": total_cases,
        "case_weighted_pass_rate": (
            passed_cases / total_cases if total_cases else None
        ),
        "accepted_tools": accepted,
        "evaluated_tools": evaluated,
        "tool_coverage_rate": coverage,
        "tool_weighted_pass_rate": tool_rate,
        "clopper_pearson_lower_bound": cp_lower,
        "pilot_gate_outcome": outcome,
        "pilot_gate_label": label,
        "method_note": (
            "Every active frozen tool is in the denominator; a tool passes only "
            "when all independently withheld blind cases and safety checks pass."
        ),
        "critical_native_action_errors": critical_errors,
        "integrity": {
            "status": "pass" if evidence_valid else "fail",
            "checks": [
                {
                    "label": check_label,
                    "status": "pass" if passed else "fail",
                    "detail": "",
                }
                for check_label, passed in checks
            ],
        },
    }


def _project_h2(report: Mapping[str, Any]) -> dict[str, Any]:
    if report.get("report_type") != "h2_integrated_sage_pilot_analysis":
        raise ValueError("H2 report type is not the locked H2 pilot analysis.")
    passed, integrity = _integrity_passed(report.get("integrity"), "H2")
    expected_status = "observed" if passed else "failed_integrity"
    if report.get("status") != expected_status:
        raise ValueError(
            f"H2 status must be {expected_status} for its integrity state."
        )
    control: float | None
    sage: float | None
    difference: float | None
    lift: float | None
    interval: list[float | None]
    clusters: int | None
    tasks: int | None
    if passed:
        control = _finite_float(report.get("control_mean"), "H2 control mean")
        sage = _finite_float(
            report.get("integrated_sage_mean"), "H2 integrated SAGE mean"
        )
        difference = _finite_float(report.get("mean_difference"), "H2 difference")
        lift = _finite_float(report.get("relative_lift"), "H2 relative lift")
        parsed_interval = _ci_pair(report.get("cluster_ci_95"), "H2 cluster CI")
        interval = [parsed_interval[0], parsed_interval[1]]
        clusters = _nonnegative_int(report.get("stem_clusters"), "H2 stem clusters")
        tasks = _nonnegative_int(report.get("tasks"), "H2 tasks")
        if clusters != 129 or tasks != 1032:
            raise ValueError(
                "H2 passing result must contain 129 stems and 1,032 tasks."
            )
        if not math.isclose(difference, sage - control, abs_tol=1e-12):
            raise ValueError("H2 difference disagrees with arm means.")
        if control <= 0 or not math.isclose(lift, difference / control, abs_tol=1e-12):
            raise ValueError("H2 relative lift disagrees with arm means.")
        cleared = lift >= 0.10 and parsed_interval[0] > 0.0
    else:
        control = sage = difference = lift = None
        interval = [None, None]
        clusters = tasks = None
        cleared = False
    checks = _integrity_checks(integrity)
    if passed:
        _require_integrity_checks_pass(checks, "H2")
    outcome, label = _validated_gate(
        report, integrity_passed=passed, threshold_cleared=cleared
    )
    canonical_raw = report.get("descriptive_canonical_similarity")
    canonical: dict[str, Any] | None = None
    if canonical_raw is not None:
        canonical_source = _mapping(
            canonical_raw, "H2 descriptive canonical similarity"
        )
        if canonical_source.get("role") != "descriptive_not_primary":
            raise ValueError(
                "H2 canonical similarity must be labeled descriptive_not_primary."
            )
        canonical_control = _finite_float(
            canonical_source.get("control_mean"),
            "H2 descriptive canonical control mean",
        )
        canonical_sage = _finite_float(
            canonical_source.get(
                "integrated_sage_mean", canonical_source.get("candidate_mean")
            ),
            "H2 descriptive canonical SAGE mean",
        )
        if not 0.0 <= canonical_control <= 1.0 or not 0.0 <= canonical_sage <= 1.0:
            raise ValueError("H2 descriptive canonical means must be within [0, 1].")
        canonical_difference = canonical_sage - canonical_control
        declared_canonical_difference = canonical_source.get("mean_difference")
        if declared_canonical_difference is not None and not math.isclose(
            _finite_float(
                declared_canonical_difference,
                "H2 descriptive canonical difference",
            ),
            canonical_difference,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "H2 descriptive canonical difference disagrees with arm means."
            )
        canonical_tasks = _nonnegative_int(
            canonical_source.get("tasks", tasks),
            "H2 descriptive canonical tasks",
        )
        if tasks is not None and canonical_tasks != tasks:
            raise ValueError("H2 descriptive canonical task count disagrees with H2.")
        canonical = {
            "role": "descriptive_not_primary",
            "control_mean": canonical_control,
            "integrated_sage_mean": canonical_sage,
            "mean_difference": canonical_difference,
            "tasks": canonical_tasks,
        }
    return {
        "status": "observed" if passed else "failed_integrity",
        "control_mean": control,
        "integrated_sage_mean": sage,
        "mean_difference": difference,
        "relative_lift": lift,
        "cluster_ci_95": interval,
        "stem_clusters": clusters,
        "tasks": tasks,
        "pilot_gate_outcome": outcome,
        "pilot_gate_label": label,
        "descriptive_canonical_similarity": canonical,
        "method_note": str(report.get("method_note") or ""),
        "integrity": {
            "status": "pass" if passed else "fail",
            "checks": checks,
        },
    }


def _project_h3(report: Mapping[str, Any]) -> dict[str, Any]:
    passed, integrity = _integrity_passed(report.get("integrity"), "H3")
    expected_status = "complete" if passed else "failed_integrity"
    if report.get("status") != expected_status:
        raise ValueError(
            f"H3 status must be {expected_status} for its integrity state."
        )
    available: float | None
    masked: float | None
    difference: float | None
    p_value: float | None
    interval: list[float | None]
    available_tasks: int | None
    masked_tasks: int | None
    clusters: int | None
    if passed:
        missing_checks = [
            key for key in _H3_REQUIRED_TRUE_INTEGRITY if integrity.get(key) is not True
        ]
        if missing_checks:
            raise ValueError(
                "H3 passing result is missing required integrity checks: "
                + ", ".join(missing_checks)
            )
        if integrity.get("online_evaluator_feedback_consumed") is not False:
            raise ValueError("H3 passing result must show evaluator feedback disabled.")
        exposure = _mapping(
            integrity.get("condition_exposure_validation"),
            "H3 condition exposure validation",
        )
        for key in (
            "masked_generated_exposure_count",
            "masked_generated_call_count",
            "forbidden_lifecycle_event_count",
            "prohibited_lifecycle_artifact_count",
        ):
            if exposure.get(key) != 0:
                raise ValueError(f"H3 integrity field {key} must be zero.")
        available = _finite_float(
            report.get("registry_available_mean"), "H3 available mean"
        )
        masked = _finite_float(report.get("registry_masked_mean"), "H3 masked mean")
        difference = _finite_float(
            report.get("itt_mean_difference"), "H3 ITT difference"
        )
        parsed_interval = _ci_pair(report.get("cluster_ci_95"), "H3 cluster CI")
        interval = [parsed_interval[0], parsed_interval[1]]
        p_value = _finite_float(report.get("p_value"), "H3 p-value")
        available_tasks = _nonnegative_int(
            report.get("available_tasks"), "H3 available tasks"
        )
        masked_tasks = _nonnegative_int(report.get("masked_tasks"), "H3 masked tasks")
        clusters = _nonnegative_int(report.get("stem_clusters"), "H3 stem clusters")
        if (available_tasks, masked_tasks, clusters) != (520, 512, 129):
            raise ValueError(
                "H3 passing result must contain 520/512 tasks and 129 stems."
            )
        if not math.isclose(difference, available - masked, abs_tol=1e-12):
            raise ValueError("H3 ITT difference disagrees with arm means.")
        if not 0.0 <= p_value <= 1.0:
            raise ValueError("H3 p-value must be within [0, 1].")
        allocation = _mapping(report.get("allocation"), "H3 allocation")
        if not str(allocation.get("sha256") or ""):
            raise ValueError("H3 passing result is missing its assignment hash.")
        cleared = difference > 0.0 and p_value < 0.05 and parsed_interval[0] > 0.0
    else:
        available = masked = difference = p_value = None
        interval = [None, None]
        available_tasks = masked_tasks = clusters = None
        allocation = {}
        cleared = False
    checks = _integrity_checks(
        integrity, expected_false=frozenset({"online_evaluator_feedback_consumed"})
    )
    if passed:
        _require_integrity_checks_pass(checks, "H3")
    outcome, label = _validated_gate(
        report, integrity_passed=passed, threshold_cleared=cleared
    )
    canonical_raw = report.get("descriptive_canonical_similarity")
    canonical: dict[str, Any] | None = None
    if canonical_raw is not None:
        canonical_source = _mapping(
            canonical_raw, "H3 descriptive canonical similarity"
        )
        if canonical_source.get("role") != "descriptive_not_primary":
            raise ValueError(
                "H3 canonical similarity must be labeled descriptive_not_primary."
            )
        canonical_available = _finite_float(
            canonical_source.get("registry_available_mean"),
            "H3 descriptive canonical available mean",
        )
        canonical_masked = _finite_float(
            canonical_source.get("registry_masked_mean"),
            "H3 descriptive canonical masked mean",
        )
        if not 0.0 <= canonical_available <= 1.0 or not 0.0 <= canonical_masked <= 1.0:
            raise ValueError("H3 descriptive canonical means must be within [0, 1].")
        canonical_difference = canonical_available - canonical_masked
        declared_canonical_difference = canonical_source.get("mean_difference")
        if declared_canonical_difference is not None and not math.isclose(
            _finite_float(
                declared_canonical_difference,
                "H3 descriptive canonical difference",
            ),
            canonical_difference,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "H3 descriptive canonical difference disagrees with condition means."
            )
        canonical_available_tasks = _nonnegative_int(
            canonical_source.get("available_tasks", available_tasks),
            "H3 descriptive canonical available tasks",
        )
        canonical_masked_tasks = _nonnegative_int(
            canonical_source.get("masked_tasks", masked_tasks),
            "H3 descriptive canonical masked tasks",
        )
        if (
            available_tasks is not None and canonical_available_tasks != available_tasks
        ) or (masked_tasks is not None and canonical_masked_tasks != masked_tasks):
            raise ValueError(
                "H3 descriptive canonical task counts disagree with assignment."
            )
        canonical = {
            "role": "descriptive_not_primary",
            "registry_available_mean": canonical_available,
            "registry_masked_mean": canonical_masked,
            "mean_difference": canonical_difference,
            "available_tasks": canonical_available_tasks,
            "masked_tasks": canonical_masked_tasks,
        }
    return {
        "status": "observed" if passed else "failed_integrity",
        "registry_available_mean": available,
        "registry_masked_mean": masked,
        "itt_mean_difference": difference,
        "cluster_ci_95": interval,
        "p_value": p_value,
        "p_value_note": str(
            report.get("p_value_note") or "one-sided restricted randomization test"
        ),
        "available_tasks": available_tasks,
        "masked_tasks": masked_tasks,
        "stem_clusters": clusters,
        "allocation": {
            "seed": allocation.get("seed"),
            "sha256": str(allocation.get("sha256") or ""),
            "stratification": str(allocation.get("stratification") or ""),
        },
        "pilot_gate_outcome": outcome,
        "pilot_gate_label": label,
        "descriptive_canonical_similarity": canonical,
        "method_note": str(report.get("method_note") or ""),
        "integrity": {
            "status": "pass" if passed else "fail",
            "checks": checks,
        },
    }


def _project_h4(report: Mapping[str, Any]) -> dict[str, Any]:
    # The executor may wrap the locked analysis. Prefer dashboard-ready root
    # fields, while accepting the standalone locked analysis as a report.
    analysis_raw = report.get("analysis")
    analysis = analysis_raw if isinstance(analysis_raw, Mapping) else report
    integrity_value = report.get("integrity", analysis.get("integrity"))
    passed, integrity = _integrity_passed(integrity_value, "H4")
    if isinstance(analysis_raw, Mapping):
        expected_status = "complete" if passed else "failed_integrity"
        if report.get("status") != expected_status:
            raise ValueError(
                f"H4 executor status must be {expected_status} for its integrity state."
            )
    outcomes_raw = analysis.get("outcomes")
    outcomes = outcomes_raw if isinstance(outcomes_raw, Mapping) else {}
    uncertainty_raw = analysis.get("uncertainty")
    uncertainty = uncertainty_raw if isinstance(uncertainty_raw, Mapping) else {}
    available: float | None
    masked: float | None
    difference: float | None
    lift: float | None
    interval: list[float | None]
    if passed:
        missing_checks = [
            key for key in _H4_REQUIRED_TRUE_INTEGRITY if integrity.get(key) is not True
        ]
        if missing_checks:
            raise ValueError(
                "H4 passing result is missing required integrity checks: "
                + ", ".join(missing_checks)
            )
        available = _finite_float(
            report.get(
                "frozen_available_mean", outcomes.get("registry_available_mean")
            ),
            "H4 frozen-registry available mean",
        )
        masked = _finite_float(
            report.get("registry_masked_mean", outcomes.get("registry_masked_mean")),
            "H4 registry-masked mean",
        )
        difference = _finite_float(
            report.get("mean_difference", outcomes.get("absolute_difference")),
            "H4 mean difference",
        )
        lift = _finite_float(
            report.get("relative_lift", outcomes.get("relative_lift")),
            "H4 relative lift",
        )
        parsed_interval = _ci_pair(
            report.get("cluster_ci_95", uncertainty.get("mean_difference_ci")),
            "H4 cluster CI",
        )
        interval = [parsed_interval[0], parsed_interval[1]]
        if not math.isclose(difference, available - masked, abs_tol=1e-12):
            raise ValueError("H4 difference disagrees with arm means.")
        if masked <= 0 or not math.isclose(lift, difference / masked, abs_tol=1e-12):
            raise ValueError("H4 relative lift disagrees with arm means.")
        cleared = lift >= 0.10 and parsed_interval[0] > 0.0
    else:
        available = masked = difference = lift = None
        interval = [None, None]
        cleared = False
    checks = _integrity_checks(integrity)
    if passed:
        _require_integrity_checks_pass(checks, "H4")
    outcome, label = _validated_gate(
        analysis, integrity_passed=passed, threshold_cleared=cleared
    )
    declared_root = _declared_gate_label(report)
    if declared_root is not None and declared_root != label:
        raise ValueError(
            f"Declared H4 executor decision {declared_root} disagrees with {label}."
        )
    counts_raw = analysis.get("counts")
    counts = counts_raw if isinstance(counts_raw, Mapping) else {}
    design_raw = report.get("split")
    design = design_raw if isinstance(design_raw, Mapping) else {}
    discovery_tasks = report.get(
        "discovery_tasks", counts.get("discovery_scenarios", 512)
    )
    discovery_stems = report.get("discovery_stems", counts.get("discovery_stems", 64))
    heldout_tasks = report.get("heldout_tasks", counts.get("scenarios_per_arm", 520))
    heldout_stems = report.get("heldout_stems", counts.get("held_out_stems", 65))
    projected_counts = (
        _nonnegative_int(discovery_tasks, "H4 discovery tasks"),
        _nonnegative_int(discovery_stems, "H4 discovery stems"),
        _nonnegative_int(heldout_tasks, "H4 held-out tasks"),
        _nonnegative_int(heldout_stems, "H4 held-out stems"),
    )
    if passed and projected_counts != (512, 64, 520, 65):
        raise ValueError("H4 passing result must contain the locked 512/520 split.")
    split_seed = report.get("split_seed", design.get("seed", 20260919))
    split_sha = str(
        report.get("split_sha256")
        or design.get("sha256")
        or report.get("design_sha256")
        or analysis.get("design_sha256")
        or ""
    )
    if passed and not split_sha:
        raise ValueError("H4 passing result is missing its split-design hash.")
    canonical_raw = report.get(
        "descriptive_canonical_similarity",
        analysis.get("descriptive_canonical_similarity"),
    )
    canonical: dict[str, Any] | None = None
    if canonical_raw is not None:
        canonical_source = _mapping(
            canonical_raw, "H4 descriptive canonical similarity"
        )
        if canonical_source.get("role") != "descriptive_not_primary":
            raise ValueError(
                "H4 canonical similarity must be labeled descriptive_not_primary."
            )
        canonical_available = _finite_float(
            canonical_source.get("registry_available_mean"),
            "H4 descriptive canonical available mean",
        )
        canonical_masked = _finite_float(
            canonical_source.get("registry_masked_mean"),
            "H4 descriptive canonical masked mean",
        )
        if not 0.0 <= canonical_available <= 1.0 or not 0.0 <= canonical_masked <= 1.0:
            raise ValueError("H4 descriptive canonical means must be within [0, 1].")
        canonical_difference = canonical_available - canonical_masked
        declared_canonical_difference = canonical_source.get("mean_difference")
        if declared_canonical_difference is not None and not math.isclose(
            _finite_float(
                declared_canonical_difference,
                "H4 descriptive canonical difference",
            ),
            canonical_difference,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "H4 descriptive canonical difference disagrees with condition means."
            )
        canonical_available_tasks = _nonnegative_int(
            canonical_source.get("available_tasks", projected_counts[2]),
            "H4 descriptive canonical available tasks",
        )
        canonical_masked_tasks = _nonnegative_int(
            canonical_source.get("masked_tasks", projected_counts[2]),
            "H4 descriptive canonical masked tasks",
        )
        if (
            canonical_available_tasks,
            canonical_masked_tasks,
        ) != (projected_counts[2], projected_counts[2]):
            raise ValueError(
                "H4 descriptive canonical task counts disagree with held-out arms."
            )
        canonical = {
            "role": "descriptive_not_primary",
            "registry_available_mean": canonical_available,
            "registry_masked_mean": canonical_masked,
            "mean_difference": canonical_difference,
            "available_tasks": canonical_available_tasks,
            "masked_tasks": canonical_masked_tasks,
        }
    return {
        "status": "observed" if passed else "failed_integrity",
        "exploratory_alternate": True,
        "discovery_tasks": projected_counts[0],
        "discovery_stems": projected_counts[1],
        "heldout_tasks": projected_counts[2],
        "heldout_stems": projected_counts[3],
        "frozen_available_mean": available,
        "registry_masked_mean": masked,
        "mean_difference": difference,
        "relative_lift": lift,
        "cluster_ci_95": interval,
        "split_seed": split_seed,
        "split_sha256": split_sha,
        "pilot_gate_outcome": outcome,
        "pilot_gate_label": label,
        "descriptive_canonical_similarity": canonical,
        "method_note": str(
            report.get("method_note")
            or "Paired held-out intention-to-treat comparison after a disjoint "
            "randomized discovery half; exploratory and not confirmatory."
        ),
        "integrity": {
            "status": "pass" if passed else "fail",
            "checks": checks,
        },
    }


def _project_result(hypothesis: str, report: Mapping[str, Any]) -> dict[str, Any]:
    projectors = {
        "h1": _project_h1,
        "h2": _project_h2,
        "h3": _project_h3,
        "h4": _project_h4,
    }
    try:
        projector = projectors[hypothesis]
    except KeyError as exc:
        raise ValueError(f"Unknown hypothesis: {hypothesis}") from exc
    return projector(report)


def _refresh(manifest_path: Path, manifest: Mapping[str, Any]) -> None:
    dashboard_dirs = manifest.get("dashboard_directories")
    if not isinstance(dashboard_dirs, list) or not dashboard_dirs:
        raise ValueError("Pilot manifest has no dashboard directories.")
    latest_raw = manifest.get("latest_pointer")
    for index, raw_directory in enumerate(dashboard_dirs):
        if not isinstance(raw_directory, str) or not raw_directory:
            raise ValueError("Pilot dashboard directory is invalid.")
        write_hypothesis_pilot_dashboard(
            manifest_path=manifest_path,
            output_dir=Path(raw_directory),
            latest_path=(Path(str(latest_raw)) if index == 0 and latest_raw else None),
        )


def create_manifest(
    *,
    manifest_path: Path,
    pilot_id: str,
    dashboard_dir: Path,
    latest_pointer: Path,
    git_commit: str,
    git_tree: str,
    benchmark_path: Path,
    protocol_path: Path,
    output_root: Path,
    artifact_root: Path,
    study_mode: str = SEQUENTIAL_STUDY_MODE,
) -> dict[str, Any]:
    """Create the pre-model manifest; existing targets are never overwritten."""

    if manifest_path.exists() or manifest_path.is_symlink():
        raise FileExistsError(f"Pilot manifest already exists: {manifest_path}")
    if not pilot_id.strip():
        raise ValueError("Pilot ID must be nonempty.")
    if study_mode not in _STUDY_MODES:
        raise ValueError(f"Unknown pilot study mode: {study_mode!r}.")
    for path, label in ((benchmark_path, "benchmark"), (protocol_path, "protocol")):
        if not path.is_file():
            raise FileNotFoundError(f"Pilot {label} is missing: {path}")
    verified_git = _verified_git_identity()
    if git_commit != verified_git["git_commit"] or git_tree != verified_git["git_tree"]:
        raise ValueError("Caller-supplied Git commit/tree does not match the worktree.")
    created = _utc_now()
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "pilot_id": pilot_id,
        "study_label": (
            "standalone exploratory H4 split-registry viability run"
            if study_mode == STANDALONE_H4_STUDY_MODE
            else "one complete H1-H3 core run plus exploratory H4 split run"
        ),
        "study_mode": study_mode,
        "execution_topology": (
            "independent_manifest_and_registry_parallel_to_external_h2"
            if study_mode == STANDALONE_H4_STUDY_MODE
            else "single_manifest_sequential_phases"
        ),
        "status": "running",
        "progress_stage": 0,
        "current_phase": "preflight",
        "created_at": created,
        "updated_at": created,
        "decision_scope": "pilot_not_confirmatory",
        "allowed_decision_labels": [
            "PILOT_THRESHOLD_CLEARED",
            "PILOT_THRESHOLD_NOT_CLEARED",
            "INTEGRITY_FAILURE",
        ],
        "h1": {"status": "pending", "integrity": {"status": "pending"}},
        "h2": {"status": "pending", "integrity": {"status": "pending"}},
        "h3": {"status": "pending", "integrity": {"status": "pending"}},
        "h4": {"status": "pending", "integrity": {"status": "pending"}},
        "locked_design": {
            "benchmark_tasks": 1032,
            "original_scenario_stems": 129,
            "variants_per_stem": 8,
            "h2_bootstrap_seed": 20260918,
            "h2_bootstrap_draws": 50000,
            "h3_assignment_seed": 20260918,
            "h3_design": "63_adjacent_pairs_plus_one_triplet",
            "h3_randomization_draws": 100000,
            "h3_randomization_seed": 20260919,
            "h3_bootstrap_draws": 20000,
            "h3_bootstrap_seed": 20260920,
            "h4_split_seed": 20260919,
            "h4_random_generator": "numpy.random.Generator(PCG64)",
            "h4_discovery_stems": 64,
            "h4_heldout_stems": 65,
            "h4_bootstrap_draws": 50000,
            "h4_bootstrap_seed": 20260920,
            "online_feedback_mode": "audited",
            "h2_online_feedback_mode": "audited",
            "h4_discovery_online_feedback_mode": "actor-visible-only",
            "model": "gpt-4o-mini",
            "transient_scenario_attempt_limit": 4,
        },
        "provenance": {
            **verified_git,
            "benchmark_path": str(benchmark_path.resolve()),
            "benchmark_sha256": _file_sha256(benchmark_path),
            "protocol_path": str(protocol_path.resolve()),
            "protocol_sha256": _file_sha256(protocol_path),
            "blind_case_bank_state": "postfreeze_spec_only_assessor_pending",
        },
        "paths": {
            "output_root": str(output_root.resolve()),
            "artifact_root": str(artifact_root.resolve()),
        },
        "dashboard_directories": [str(dashboard_dir.resolve())],
        "latest_pointer": str(latest_pointer.resolve()),
        "artifacts": [
            _artifact(protocol_path, "Locked H1-H4 pilot protocol", "protocol"),
            _artifact(benchmark_path, "Pinned 1,032-task benchmark", "input"),
            _artifact(manifest_path, "Mutable pilot state manifest", "manifest"),
        ],
        "events": [{"at": created, "phase": "preflight", "status": "running"}],
    }
    _atomic_write(manifest_path, manifest)
    _refresh(manifest_path, manifest)
    return manifest


def update_phase(
    *,
    manifest_path: Path,
    phase: str,
    progress_stage: int,
    run_status: str | None = None,
    hypothesis: str | None = None,
    hypothesis_status: str | None = None,
) -> dict[str, Any]:
    manifest = _read_object(manifest_path)
    if run_status is not None and run_status not in _RUN_STATUSES:
        raise ValueError(f"Invalid pilot status: {run_status}")
    if not 0 <= progress_stage <= 5:
        raise ValueError("Pilot progress stage must be between 0 and 5.")
    if hypothesis is not None:
        if hypothesis not in _HYPOTHESES:
            raise ValueError(f"Unknown hypothesis: {hypothesis}")
        if hypothesis_status not in _HYPOTHESIS_STATUSES:
            raise ValueError(f"Invalid hypothesis status: {hypothesis_status}")
        if hypothesis_status == "observed":
            raise ValueError(
                "Observed hypothesis states may only be created by record-result."
            )
        if hypothesis_status == "running":
            if progress_stage != _RUNNING_PROGRESS[hypothesis]:
                raise ValueError(
                    f"{hypothesis.upper()} must start at progress stage "
                    f"{_RUNNING_PROGRESS[hypothesis]}."
                )
            _require_phase_ready(manifest, hypothesis, require_running=False)
        raw_hypothesis = manifest.get(hypothesis)
        current = dict(raw_hypothesis) if isinstance(raw_hypothesis, dict) else {}
        current["status"] = hypothesis_status
        manifest[hypothesis] = current
    manifest["current_phase"] = phase
    manifest["progress_stage"] = progress_stage
    if run_status is not None:
        manifest["status"] = run_status
    manifest["updated_at"] = _utc_now()
    events = manifest.setdefault("events", [])
    if not isinstance(events, list):
        raise ValueError("Pilot event journal is malformed.")
    events.append(
        {
            "at": manifest["updated_at"],
            "phase": phase,
            "status": manifest.get("status"),
            "hypothesis": hypothesis,
            "hypothesis_status": hypothesis_status,
        }
    )
    _atomic_write(manifest_path, manifest)
    _refresh(manifest_path, manifest)
    return manifest


def register_dashboard(*, manifest_path: Path, dashboard_dir: Path) -> dict[str, Any]:
    manifest = _read_object(manifest_path)
    directories = manifest.setdefault("dashboard_directories", [])
    if not isinstance(directories, list):
        raise ValueError("Pilot dashboard directory list is malformed.")
    resolved = str(dashboard_dir.resolve())
    if resolved not in directories:
        directories.append(resolved)
    manifest["updated_at"] = _utc_now()
    _atomic_write(manifest_path, manifest)
    _refresh(manifest_path, manifest)
    return manifest


def bind_frozen_registry(
    *, manifest_path: Path, registry_dir: Path, h2_run_root: Path
) -> dict[str, Any]:
    """Bind the one H2-evolved registry used by both H1 and H3."""

    manifest = _read_object(manifest_path)
    _require_manifest_git_identity(manifest, label="H2 registry binding source")
    h2 = _mapping(manifest.get("h2"), "H2 pilot state")
    if h2.get("status") != "observed":
        raise ValueError(
            "The H2 result must be recorded before registry freeze binding."
        )
    h2_run_root = h2_run_root.resolve()
    h2_report_path = Path(str(h2.get("source_report_path") or "")).resolve()
    if not h2_report_path.is_file() or _file_sha256(h2_report_path) != h2.get(
        "source_report_sha256"
    ):
        raise ValueError("The recorded H2 source report is missing or changed.")
    h2_report = _read_object(h2_report_path)
    h2_integrity = _mapping(h2_report.get("integrity"), "H2 report integrity")
    receipt = _mapping(
        h2_integrity.get("strict_verification_receipt"),
        "H2 strict verification receipt",
    )
    if Path(str(receipt.get("run_root") or "")).resolve() != h2_run_root:
        raise ValueError("H2 registry binding run differs from the recorded H2 run.")
    protocol_path = h2_run_root / "protocol_manifest.json"
    protocol = _read_object(protocol_path)
    declared_registry = Path(str(protocol.get("registry_dir") or "")).resolve()
    registry_dir = registry_dir.resolve()
    if declared_registry != registry_dir:
        raise ValueError(
            "Registry path differs from the strictly verified H2 registry."
        )
    identity = _registry_content_identity(registry_dir)
    if (
        protocol.get("registry_manifest_digest_after_run")
        != identity["manifest_sha256"]
    ):
        raise ValueError("H2 protocol registry-manifest digest no longer matches.")
    binding = {
        **identity,
        "h2_run_root": str(h2_run_root),
        "h2_protocol_manifest_path": str(protocol_path),
        "h2_protocol_manifest_sha256": _file_sha256(protocol_path),
        "bound_at": _utc_now(),
    }
    existing = manifest.get("frozen_h123_registry")
    if isinstance(existing, Mapping):
        comparable_existing = dict(existing)
        comparable_binding = dict(binding)
        comparable_existing.pop("bound_at", None)
        comparable_binding.pop("bound_at", None)
        if comparable_existing == comparable_binding:
            return manifest
        raise ValueError("A different H1/H3 frozen registry is already bound.")
    manifest["frozen_h123_registry"] = binding
    manifest["updated_at"] = binding["bound_at"]
    events = manifest.setdefault("events", [])
    if not isinstance(events, list):
        raise ValueError("Pilot event journal is malformed.")
    events.append(
        {
            "at": binding["bound_at"],
            "phase": "h2_registry_frozen_for_h1_h3",
            "status": manifest.get("status"),
            "registry_content_sha256": binding["content_sha256"],
        }
    )
    _atomic_write(manifest_path, manifest)
    _refresh(manifest_path, manifest)
    return manifest


def bind_paper_h2(
    *,
    manifest_path: Path,
    selected_manifest_path: Path,
    verification_path: Path,
    dashboard_data_path: Path,
    bridge_report_path: Path,
    replication: int = 1,
) -> dict[str, Any]:
    """Adopt the completed paper H2 and bind deterministic rep01 for H1/H3.

    This validates archival evidence only; it executes no model or benchmark.
    """

    if replication != 1:
        raise ValueError("The single-run viability protocol locks paper replication 1.")
    manifest = _read_object(manifest_path)
    _require_manifest_git_identity(manifest, label="paper-H2 evidence binding source")
    if manifest.get("status") != "running":
        raise ValueError("Pilot must be running before paper H2 can be bound.")
    if _mapping(manifest.get("h2"), "H2 pilot state").get("status") != "pending":
        raise ValueError("Paper H2 may only replace a pending H2 state.")
    for hypothesis in ("h1", "h3", "h4"):
        if _mapping(manifest.get(hypothesis), hypothesis).get("status") != "pending":
            raise ValueError("Paper H2 must be bound before H1, H3, or H4 starts.")

    selected_manifest_path = selected_manifest_path.resolve()
    verification_path = verification_path.resolve()
    dashboard_data_path = dashboard_data_path.resolve()
    for path, expected, label in (
        (
            selected_manifest_path,
            _PAPER_H2_SELECTED_MANIFEST_SHA256,
            "selected-cohort manifest",
        ),
        (verification_path, _PAPER_H2_VERIFICATION_SHA256, "verification receipt"),
        (
            dashboard_data_path,
            _PAPER_H2_DASHBOARD_DATA_SHA256,
            "dashboard evidence data",
        ),
    ):
        if not path.is_file() or _file_sha256(path) != expected:
            raise ValueError(f"Canonical paper H2 {label} is missing or changed.")

    selected = _read_object(selected_manifest_path)
    verification = _read_object(verification_path)
    dashboard = _read_object(dashboard_data_path)
    provenance = _mapping(manifest.get("provenance"), "Pilot provenance")
    if (
        selected.get("status") != "complete"
        or selected.get("expected_online_runs") != 10
        or selected.get("expected_frozen_runs") != 10
        or selected.get("benchmark_sha256") != provenance.get("benchmark_sha256")
    ):
        raise ValueError("Canonical paper H2 cohort identity is invalid.")
    run_pairs = selected.get("run_pairs")
    if not isinstance(run_pairs, list) or len(run_pairs) != 10:
        raise ValueError("Canonical paper H2 must contain exactly ten run pairs.")
    replications = [
        pair.get("replication") for pair in run_pairs if isinstance(pair, Mapping)
    ]
    if replications != list(range(1, 11)):
        raise ValueError("Canonical paper H2 replication roster is malformed.")
    for pair in run_pairs:
        pair = _mapping(pair, "Paper H2 run pair")
        for arm_name in ("online", "frozen"):
            arm = _mapping(pair.get(arm_name), f"Paper H2 {arm_name} arm")
            strict = _mapping(
                arm.get("strict_verification"),
                f"Paper H2 {arm_name} strict verification",
            )
            if (
                arm.get("execution_status") != "completed"
                or arm.get("verification_status") != "pass"
                or strict.get("status") != "pass"
                or strict.get("scenario_count") != 1032
                or strict.get("git_commit") != _PAPER_H2_RUNTIME_COMMIT
                or strict.get("git_tree") != _PAPER_H2_RUNTIME_TREE
            ):
                raise ValueError("A canonical paper H2 run is not strictly verified.")

    for key, expected in {
        "status": "pass",
        "runtime_commit": _PAPER_H2_RUNTIME_COMMIT,
        "runtime_tree": _PAPER_H2_RUNTIME_TREE,
        "selected_online_count": 10,
        "selected_frozen_count": 10,
        "all_selected_runs_strictly_verified": True,
        "all_selected_runs_zero_exceptions": True,
        "all_frozen_registries_immutable": True,
        "selected_cohort_manifest_sha256": _PAPER_H2_SELECTED_MANIFEST_SHA256,
    }.items():
        if verification.get(key) != expected:
            raise ValueError(f"Paper H2 verification field {key} is not canonical.")

    hypothesis_rows = dashboard.get("hypotheses")
    if not isinstance(hypothesis_rows, list):
        raise ValueError("Paper H2 dashboard has no hypothesis roster.")
    h2_row = _mapping(
        next(
            (
                row
                for row in hypothesis_rows
                if isinstance(row, Mapping) and row.get("id") == "Hypothesis 2"
            ),
            None,
        ),
        "Paper H2 dashboard result",
    )
    exact_h2: dict[str, Any] = {
        "decision": "supported",
        "sample_size": 10,
        "matched_task_observations": 10320,
        "baseline_mean": 0.5861757105943152,
        "sage_mean": 0.7835432816537468,
        "estimate_percent": 33.670376901035944,
        "run_threshold_sign_flip_p": 0.001953125,
    }
    for key, expected in exact_h2.items():
        value = h2_row.get(key)
        if isinstance(expected, float):
            if not isinstance(value, (int, float)) or not math.isclose(
                float(value), expected, rel_tol=0.0, abs_tol=1e-15
            ):
                raise ValueError(f"Paper H2 dashboard field {key} changed.")
        elif value != expected:
            raise ValueError(f"Paper H2 dashboard field {key} changed.")

    selected_rep = _mapping(run_pairs[replication - 1], "Selected paper replication")
    online = _mapping(selected_rep.get("online"), "Selected online replication")
    frozen = _mapping(selected_rep.get("frozen"), "Selected frozen replication")
    run_root = (REPO_ROOT / str(online.get("run_root") or "")).resolve()
    protocol_path = run_root / "protocol_manifest.json"
    protocol = _read_object(protocol_path)
    control_path = (
        Path(str(protocol.get("control_dir") or "")).resolve() / "result_summary.json"
    )
    if (
        not control_path.is_file()
        or _file_sha256(control_path) != _PAPER_H2_REP01_CONTROL_SHA256
    ):
        raise ValueError("Paper replication 1 control summary is missing or changed.")
    registry_dir = (REPO_ROOT / str(frozen.get("registry_dir") or "")).resolve()
    identity = _registry_content_identity(registry_dir)
    if (
        identity["content_sha256"] != _PAPER_H2_REP01_REGISTRY_CONTENT_SHA256
        or identity["manifest_sha256"] != _PAPER_H2_REP01_REGISTRY_MANIFEST_SHA256
    ):
        raise ValueError("Paper replication 1 frozen registry is missing or changed.")

    statistics = _mapping(dashboard.get("statistics"), "Paper H2 statistics")
    delta_ci = _mapping(
        statistics.get("two_way_run_task_bootstrap_delta_ci"),
        "Paper H2 two-way delta interval",
    )
    target_ci = _mapping(
        statistics.get("two_way_run_task_bootstrap_threshold_contrast_ci"),
        "Paper H2 target-contrast interval",
    )
    bridge_report_path = bridge_report_path.resolve()
    if bridge_report_path.exists() or bridge_report_path.is_symlink():
        raise FileExistsError(
            f"Paper H2 bridge report already exists: {bridge_report_path}"
        )
    bound_at = _utc_now()
    mean_difference = exact_h2["sage_mean"] - exact_h2["baseline_mean"]
    bridge_report: dict[str, Any] = {
        "schema_version": 1,
        "report_type": "canonical_paper_h2_evidence_bridge",
        "status": "complete",
        "created_at": bound_at,
        "evidence_role": "archival_confirmatory_reference",
        "statement": "Ten independently evolved SAGE registries outperform control.",
        "inputs": {
            "selected_cohort_manifest": {
                "path": str(selected_manifest_path),
                "sha256": _PAPER_H2_SELECTED_MANIFEST_SHA256,
            },
            "selected_cohort_verification": {
                "path": str(verification_path),
                "sha256": _PAPER_H2_VERIFICATION_SHA256,
            },
            "dashboard_data": {
                "path": str(dashboard_data_path),
                "sha256": _PAPER_H2_DASHBOARD_DATA_SHA256,
            },
            "control": {
                "path": str(control_path),
                "sha256": _PAPER_H2_REP01_CONTROL_SHA256,
                "selection_rule": "replication_1_first_verified_not_outcome_selected",
            },
            "registry": identity,
        },
        "paper_h2": {
            "decision": "supported",
            "independent_registry_runs": 10,
            "matched_task_observations": 10320,
            "control_mean": exact_h2["baseline_mean"],
            "integrated_sage_mean": exact_h2["sage_mean"],
            "mean_difference": mean_difference,
            "relative_lift": exact_h2["estimate_percent"] / 100.0,
            "two_way_delta_ci_95": [delta_ci.get("lower"), delta_ci.get("upper")],
            "two_way_target_contrast_ci_95": [
                target_ci.get("lower"),
                target_ci.get("upper"),
            ],
            "exact_two_sided_run_sign_flip_p": exact_h2["run_threshold_sign_flip_p"],
        },
        "viability_registry_selection": {
            "replication": replication,
            "rule": "first strictly verified paper replication; outcome-blind",
            "purpose": "single-registry H1/H3 viability only",
        },
        "integrity": {
            "status": "pass",
            "checks": [
                {"name": "canonical hashes pinned", "passed": True},
                {"name": "ten paired runs strictly verified", "passed": True},
                {"name": "zero run exceptions", "passed": True},
                {"name": "frozen registries immutable", "passed": True},
                {
                    "name": "replication 1 selected without outcome screening",
                    "passed": True,
                },
            ],
        },
    }
    _atomic_write(bridge_report_path, bridge_report)
    bridge_sha256 = _file_sha256(bridge_report_path)

    manifest["study_label"] = (
        "single-run H1/H3/H4 viability anchored to completed paper H2"
    )
    manifest["h2"] = {
        "status": "observed",
        "evidence_role": "archival_confirmatory_reference",
        "paper_decision": "supported",
        "control_mean": exact_h2["baseline_mean"],
        "integrated_sage_mean": exact_h2["sage_mean"],
        "mean_difference": mean_difference,
        "relative_lift": exact_h2["estimate_percent"] / 100.0,
        "cluster_ci_95": [delta_ci.get("lower"), delta_ci.get("upper")],
        "independent_registry_runs": 10,
        "tasks": 10320,
        "pilot_gate_outcome": "paper_complete",
        "pilot_gate_label": "CANONICAL_PAPER_EVIDENCE",
        "method_note": (
            "Existing paper H2; no H2 run was executed for this pilot. Ten "
            "independently evolved registries: control 0.5862, SAGE 0.7835, "
            "+33.7%, exact run-level p=.001953125."
        ),
        "integrity": {"status": "pass", "checks": bridge_report["integrity"]["checks"]},
        "source_report_path": str(bridge_report_path),
        "source_report_sha256": bridge_sha256,
    }
    manifest["paper_h2_anchor"] = {
        "selected_cohort_manifest_path": str(selected_manifest_path),
        "selected_cohort_manifest_sha256": _PAPER_H2_SELECTED_MANIFEST_SHA256,
        "verification_path": str(verification_path),
        "verification_sha256": _PAPER_H2_VERIFICATION_SHA256,
        "runtime_commit": _PAPER_H2_RUNTIME_COMMIT,
        "runtime_tree": _PAPER_H2_RUNTIME_TREE,
        "bound_at": bound_at,
    }
    manifest["frozen_h123_registry"] = {
        **identity,
        "paper_replication": replication,
        "selection_rule": "first_strictly_verified_replication",
        "source_selected_cohort_manifest": str(selected_manifest_path),
        "source_selected_cohort_manifest_sha256": _PAPER_H2_SELECTED_MANIFEST_SHA256,
        "h2_run_root": str(run_root),
        "h2_protocol_manifest_path": str(protocol_path),
        "h2_protocol_manifest_sha256": _file_sha256(protocol_path),
        "bound_at": bound_at,
    }
    artifacts = manifest.setdefault("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("Pilot artifact list is malformed.")
    artifacts.extend(
        [
            _artifact(
                bridge_report_path, "Canonical paper H2 evidence bridge", "analysis"
            ),
            _artifact(
                selected_manifest_path, "Canonical paper H2 selected cohort", "evidence"
            ),
            _artifact(
                verification_path,
                "Canonical paper H2 strict verification",
                "verification",
            ),
        ]
    )
    manifest["current_phase"] = "paper_h2_anchored"
    manifest["progress_stage"] = 1
    manifest["updated_at"] = bound_at
    events = manifest.setdefault("events", [])
    if not isinstance(events, list):
        raise ValueError("Pilot event journal is malformed.")
    events.append(
        {
            "at": bound_at,
            "phase": "paper_h2_anchored",
            "status": manifest.get("status"),
            "hypothesis": "h2",
            "hypothesis_status": "observed",
            "evidence_role": "archival_confirmatory_reference",
            "source_report_sha256": bridge_sha256,
            "registry_content_sha256": identity["content_sha256"],
        }
    )
    _atomic_write(manifest_path, manifest)
    _refresh(manifest_path, manifest)
    return manifest


def bind_h4_frozen_registry(
    *,
    manifest_path: Path,
    registry_dir: Path,
    design_sha256: str,
    discovery_run_dir: Path,
) -> dict[str, Any]:
    """Durably bind H4's discovery-built registry before held-out calls."""

    manifest = _read_object(manifest_path)
    _require_manifest_git_identity(manifest, label="H4 registry binding source")
    _require_phase_ready(manifest, "h4", require_running=True)
    seals = _mapping(manifest.get("prospective_phase_seals"), "Prospective seals")
    seal = _mapping(seals.get("h4_split"), "H4 prospective seal")
    declarations = _mapping(seal.get("declarations"), "H4 seal declarations")
    if declarations.get("design_sha256") != design_sha256:
        raise ValueError(
            "H4 registry binding design differs from its prospective seal."
        )
    discovery_run_dir = discovery_run_dir.resolve()
    if not discovery_run_dir.is_dir():
        raise ValueError(f"H4 discovery run is missing: {discovery_run_dir}")
    identity = _registry_content_identity(registry_dir)
    binding = {
        **identity,
        "design_sha256": design_sha256,
        "discovery_run_dir": str(discovery_run_dir),
        "bound_at": _utc_now(),
    }
    existing = manifest.get("h4_frozen_registry")
    if isinstance(existing, Mapping):
        comparable_existing = dict(existing)
        comparable_binding = dict(binding)
        comparable_existing.pop("bound_at", None)
        comparable_binding.pop("bound_at", None)
        if comparable_existing == comparable_binding:
            return manifest
        raise ValueError("A different H4 frozen discovery registry is already bound.")
    manifest["h4_frozen_registry"] = binding
    manifest["updated_at"] = binding["bound_at"]
    events = manifest.setdefault("events", [])
    if not isinstance(events, list):
        raise ValueError("Pilot event journal is malformed.")
    events.append(
        {
            "at": binding["bound_at"],
            "phase": "h4_discovery_registry_frozen",
            "status": manifest.get("status"),
            "registry_content_sha256": binding["content_sha256"],
            "design_sha256": design_sha256,
        }
    )
    _atomic_write(manifest_path, manifest)
    _refresh(manifest_path, manifest)
    return manifest


def seal_phase_inputs(
    *,
    manifest_path: Path,
    phase: str,
    files: Mapping[str, Path],
    declarations: Mapping[str, Any],
) -> dict[str, Any]:
    """Write-once hash seal for inputs fixed before a phase's first model call."""

    if phase not in {"h1_blind_audit", "h3_randomized_availability", "h4_split"}:
        raise ValueError(f"Unsupported prospective seal phase: {phase}")
    manifest = _read_object(manifest_path)
    git_identity = _require_manifest_git_identity(
        manifest, label=f"{phase} pre-call source"
    )
    hypothesis = _PHASE_HYPOTHESIS[phase]
    _require_phase_ready(manifest, hypothesis, require_running=True)
    sealed_files: dict[str, dict[str, Any]] = {}
    for label, path in sorted(files.items()):
        resolved = path.resolve()
        if not resolved.is_file():
            raise ValueError(f"Prospective seal file is missing: {resolved}")
        sealed_files[label] = {
            "path": str(resolved),
            "sha256": _file_sha256(resolved),
            "size_bytes": resolved.stat().st_size,
        }
    payload = {
        "phase": phase,
        "pilot_id": str(manifest.get("pilot_id") or ""),
        "pilot_manifest_path": str(manifest_path.resolve()),
        "git_identity": git_identity,
        "files": sealed_files,
        "declarations": dict(declarations),
    }
    payload["seal_sha256"] = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    seals = manifest.setdefault("prospective_phase_seals", {})
    if not isinstance(seals, dict):
        raise ValueError("Pilot prospective phase seals are malformed.")
    existing = seals.get(phase)
    if isinstance(existing, Mapping):
        comparable = dict(existing)
        comparable.pop("sealed_at", None)
        if comparable == payload:
            return manifest
        raise ValueError(f"A different prospective seal already exists for {phase}.")
    sealed_at = _utc_now()
    seals[phase] = {**payload, "sealed_at": sealed_at}
    manifest["updated_at"] = sealed_at
    events = manifest.setdefault("events", [])
    if not isinstance(events, list):
        raise ValueError("Pilot event journal is malformed.")
    events.append(
        {
            "at": sealed_at,
            "phase": f"{phase}_inputs_sealed",
            "status": manifest.get("status"),
            "seal_sha256": payload["seal_sha256"],
        }
    )
    _atomic_write(manifest_path, manifest)
    _refresh(manifest_path, manifest)
    return manifest


def add_artifact(
    *, manifest_path: Path, path: Path, label: str, kind: str
) -> dict[str, Any]:
    manifest = _read_object(manifest_path)
    artifacts = manifest.setdefault("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("Pilot artifact list is malformed.")
    entry = _artifact(path, label, kind)
    artifacts[:] = [item for item in artifacts if item.get("path") != entry["path"]]
    artifacts.append(entry)
    manifest["updated_at"] = _utc_now()
    _atomic_write(manifest_path, manifest)
    _refresh(manifest_path, manifest)
    return manifest


def _validate_prospective_and_registry_bindings(
    *,
    manifest_path: Path,
    manifest: Mapping[str, Any],
    hypothesis: str,
    report: Mapping[str, Any],
) -> None:
    _require_manifest_git_identity(
        manifest, label=f"{hypothesis.upper()} result-ingestion source"
    )
    expected_manifest_path = manifest_path.resolve()
    if hypothesis == "h2":
        integrity = _mapping(report.get("integrity"), "H2 integrity")
        receipt = _mapping(
            integrity.get("strict_verification_receipt"),
            "H2 strict verification receipt",
        )
        pilot_receipt = _mapping(
            receipt.get("hypothesis_pilot_manifest"),
            "H2 pilot-manifest receipt",
        )
        if (
            Path(str(pilot_receipt.get("path") or "")).resolve()
            != expected_manifest_path
        ):
            raise ValueError("H2 run was bound to a different central pilot manifest.")
        verification = _mapping(receipt.get("verification"), "H2 verification")
        _require_manifest_git_identity(
            manifest,
            observed=verification,
            label="H2 execution",
        )
    elif hypothesis in {"h3", "h4"}:
        if report.get("phase_inputs_sealed_before_model_execution") is not True:
            raise ValueError(
                f"{hypothesis.upper()} result lacks a completed pre-model phase seal."
            )
        inputs = _mapping(report.get("inputs"), f"{hypothesis.upper()} inputs")
        if (
            Path(str(inputs.get("pilot_manifest_path") or "")).resolve()
            != expected_manifest_path
        ):
            raise ValueError(
                f"{hypothesis.upper()} run was bound to a different central pilot manifest."
            )
        publication_environment = _mapping(
            report.get("publication_environment"),
            f"{hypothesis.upper()} publication environment",
        )
        _require_manifest_git_identity(
            manifest,
            observed=publication_environment,
            label=f"{hypothesis.upper()} execution",
        )

    if hypothesis in {"h1", "h3"}:
        binding = _mapping(
            manifest.get("frozen_h123_registry"), "Frozen H1/H3 registry binding"
        )
        expected_tree = str(binding.get("content_sha256") or "")
        if hypothesis == "h1":
            immutability = _mapping(
                report.get("registry_immutability"), "H1 registry immutability"
            )
            observed_tree = str(immutability.get("before_tree_sha256") or "")
        else:
            provenance = _mapping(report.get("provenance"), "H3 provenance")
            source_before = _mapping(
                provenance.get("registry_source_before"),
                "H3 source registry identity",
            )
            observed_tree = str(source_before.get("content_sha256") or "")
            inputs = _mapping(report.get("inputs"), "H3 inputs")
            if (
                Path(str(inputs.get("registry_source") or "")).resolve()
                != Path(str(binding.get("path") or "")).resolve()
            ):
                raise ValueError("H3 registry source path differs from the H2 binding.")
        if not expected_tree or observed_tree != expected_tree:
            raise ValueError(f"{hypothesis.upper()} registry bytes differ from H2.")

    phase_by_hypothesis = {
        "h1": "h1_blind_audit",
        "h3": "h3_randomized_availability",
        "h4": "h4_split",
    }
    phase = phase_by_hypothesis.get(hypothesis)
    if phase is None:
        return
    seals = _mapping(manifest.get("prospective_phase_seals"), "Prospective seals")
    seal = _mapping(seals.get(phase), f"{phase} prospective seal")
    if seal.get("pilot_id") != manifest.get("pilot_id"):
        raise ValueError(f"{phase} seal has the wrong pilot ID.")
    if (
        Path(str(seal.get("pilot_manifest_path") or "")).resolve()
        != expected_manifest_path
    ):
        raise ValueError(f"{phase} seal names a different central manifest.")
    _require_manifest_git_identity(
        manifest,
        observed=_mapping(seal.get("git_identity"), f"{phase} sealed Git identity"),
        label=f"{phase} seal",
    )
    files = _mapping(seal.get("files"), f"{phase} sealed files")
    if hypothesis == "h1":
        bank = _mapping(report.get("case_bank"), "H1 case bank")
        expected = str(bank.get("expected_sha256") or "")
        sealed = _mapping(files.get("case_bank"), "H1 sealed case bank")
        if sealed.get("sha256") != expected:
            raise ValueError("H1 case-bank result differs from its prospective seal.")
    elif hypothesis == "h3":
        provenance = _mapping(report.get("provenance"), "H3 provenance")
        sealed = _mapping(files.get("assignment"), "H3 sealed assignment")
        if sealed.get("sha256") != provenance.get("assignment_file_sha256"):
            raise ValueError("H3 assignment differs from its prospective seal.")
        sealed_control = _mapping(files.get("h2_control"), "H3 sealed H2 control")
        if sealed_control.get("sha256") != provenance.get("h2_control_file_sha256"):
            raise ValueError("H3 H2 control differs from its prospective seal.")
    else:
        provenance = _mapping(report.get("provenance"), "H4 provenance")
        sealed = _mapping(files.get("design"), "H4 sealed design")
        if sealed.get("sha256") != provenance.get("design_file_sha256"):
            raise ValueError("H4 design differs from its prospective seal.")
        binding = _mapping(
            manifest.get("h4_frozen_registry"), "H4 frozen registry binding"
        )
        report_binding = _mapping(
            report.get("h4_frozen_registry_binding"),
            "H4 report frozen registry binding",
        )
        for key in ("path", "content_sha256", "manifest_sha256", "design_sha256"):
            if report_binding.get(key) != binding.get(key):
                raise ValueError(
                    f"H4 report registry binding differs from the central {key}."
                )
        if provenance.get("frozen_registry_content_sha256") != binding.get(
            "content_sha256"
        ):
            raise ValueError("H4 provenance differs from its frozen registry binding.")


def record_result(
    *, manifest_path: Path, hypothesis: str, report_path: Path
) -> dict[str, Any]:
    """Validate and record one locked result in dashboard-facing form.

    Projection finishes before the mutable manifest is written.  A malformed,
    internally inconsistent, or confirmatory-labelled report therefore leaves
    both the manifest and its dashboards unchanged.
    """

    if hypothesis not in _HYPOTHESES:
        raise ValueError(f"Unknown hypothesis: {hypothesis}")
    report_sha256 = _file_sha256(report_path)
    report = _read_object(report_path)
    if _file_sha256(report_path) != report_sha256:
        raise ValueError("Pilot result report changed while it was being recorded.")
    projected = _project_result(hypothesis, report)
    projected["source_report_path"] = str(report_path.resolve())
    projected["source_report_sha256"] = report_sha256

    manifest = _read_object(manifest_path)
    existing = manifest.get(hypothesis)
    if isinstance(existing, Mapping) and existing.get("source_report_sha256"):
        if existing.get("source_report_sha256") == report_sha256:
            return manifest
        raise ValueError(
            f"{hypothesis.upper()} already has a different locked result; "
            "a new pilot ID or prospective amendment is required."
        )
    _require_phase_ready(manifest, hypothesis, require_running=True)
    _validate_prospective_and_registry_bindings(
        manifest_path=manifest_path,
        manifest=manifest,
        hypothesis=hypothesis,
        report=report,
    )
    manifest[hypothesis] = projected
    artifacts = manifest.setdefault("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("Pilot artifact list is malformed.")
    artifact = _artifact(
        report_path,
        f"{hypothesis.upper()} locked pilot result",
        "analysis",
    )
    artifacts[:] = [item for item in artifacts if item.get("path") != artifact["path"]]
    artifacts.append(artifact)
    manifest["updated_at"] = _utc_now()
    events = manifest.setdefault("events", [])
    if not isinstance(events, list):
        raise ValueError("Pilot event journal is malformed.")
    events.append(
        {
            "at": manifest["updated_at"],
            "phase": f"{hypothesis}_result_recorded",
            "status": manifest.get("status"),
            "hypothesis": hypothesis,
            "hypothesis_status": projected["status"],
            "pilot_gate_label": projected["pilot_gate_label"],
            "source_report_sha256": projected["source_report_sha256"],
        }
    )
    _atomic_write(manifest_path, manifest)
    _refresh(manifest_path, manifest)
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    initialize = subparsers.add_parser("init")
    initialize.add_argument("--manifest", type=Path, required=True)
    initialize.add_argument("--pilot-id", required=True)
    initialize.add_argument("--dashboard-dir", type=Path, required=True)
    initialize.add_argument("--latest-pointer", type=Path, required=True)
    initialize.add_argument("--git-commit", required=True)
    initialize.add_argument("--git-tree", required=True)
    initialize.add_argument("--benchmark", type=Path, required=True)
    initialize.add_argument("--protocol", type=Path, required=True)
    initialize.add_argument("--output-root", type=Path, required=True)
    initialize.add_argument("--artifact-root", type=Path, required=True)
    initialize.add_argument(
        "--study-mode",
        choices=sorted(_STUDY_MODES),
        default=SEQUENTIAL_STUDY_MODE,
    )

    phase = subparsers.add_parser("phase")
    phase.add_argument("--manifest", type=Path, required=True)
    phase.add_argument("--phase", required=True)
    phase.add_argument("--progress-stage", type=int, required=True)
    phase.add_argument("--run-status", choices=sorted(_RUN_STATUSES))
    phase.add_argument("--hypothesis", choices=_HYPOTHESES)
    phase.add_argument("--hypothesis-status", choices=sorted(_HYPOTHESIS_STATUSES))

    dashboard = subparsers.add_parser("register-dashboard")
    dashboard.add_argument("--manifest", type=Path, required=True)
    dashboard.add_argument("--dashboard-dir", type=Path, required=True)

    registry = subparsers.add_parser("bind-registry")
    registry.add_argument("--manifest", type=Path, required=True)
    registry.add_argument("--registry-dir", type=Path, required=True)
    registry.add_argument("--h2-run-root", type=Path, required=True)

    paper_h2 = subparsers.add_parser("bind-paper-h2")
    paper_h2.add_argument("--manifest", type=Path, required=True)
    paper_h2.add_argument("--selected-manifest", type=Path, required=True)
    paper_h2.add_argument("--verification", type=Path, required=True)
    paper_h2.add_argument("--dashboard-data", type=Path, required=True)
    paper_h2.add_argument("--bridge-report", type=Path, required=True)
    paper_h2.add_argument("--replication", type=int, default=1)

    artifact = subparsers.add_parser("add-artifact")
    artifact.add_argument("--manifest", type=Path, required=True)
    artifact.add_argument("--path", type=Path, required=True)
    artifact.add_argument("--label", required=True)
    artifact.add_argument("--kind", default="artifact")

    result = subparsers.add_parser("record-result")
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--hypothesis", choices=_HYPOTHESES, required=True)
    result.add_argument("--report", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "init":
        manifest = create_manifest(
            manifest_path=args.manifest,
            pilot_id=args.pilot_id,
            dashboard_dir=args.dashboard_dir,
            latest_pointer=args.latest_pointer,
            git_commit=args.git_commit,
            git_tree=args.git_tree,
            benchmark_path=args.benchmark,
            protocol_path=args.protocol,
            output_root=args.output_root,
            artifact_root=args.artifact_root,
            study_mode=args.study_mode,
        )
    elif args.command == "phase":
        manifest = update_phase(
            manifest_path=args.manifest,
            phase=args.phase,
            progress_stage=args.progress_stage,
            run_status=args.run_status,
            hypothesis=args.hypothesis,
            hypothesis_status=args.hypothesis_status,
        )
    elif args.command == "register-dashboard":
        manifest = register_dashboard(
            manifest_path=args.manifest, dashboard_dir=args.dashboard_dir
        )
    elif args.command == "bind-registry":
        manifest = bind_frozen_registry(
            manifest_path=args.manifest,
            registry_dir=args.registry_dir,
            h2_run_root=args.h2_run_root,
        )
    elif args.command == "bind-paper-h2":
        manifest = bind_paper_h2(
            manifest_path=args.manifest,
            selected_manifest_path=args.selected_manifest,
            verification_path=args.verification,
            dashboard_data_path=args.dashboard_data,
            bridge_report_path=args.bridge_report,
            replication=args.replication,
        )
    elif args.command == "add-artifact":
        manifest = add_artifact(
            manifest_path=args.manifest,
            path=args.path,
            label=args.label,
            kind=args.kind,
        )
    else:
        manifest = record_result(
            manifest_path=args.manifest,
            hypothesis=args.hypothesis,
            report_path=args.report,
        )
    print(
        json.dumps(
            {
                "pilot_id": manifest["pilot_id"],
                "status": manifest["status"],
                "phase": manifest["current_phase"],
                "progress_stage": manifest["progress_stage"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
