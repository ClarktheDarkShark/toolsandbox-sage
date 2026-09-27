#!/usr/bin/env python3
"""Verify the frozen SAGE refactor contract without making model calls.

The invocation validates the immutable reference identity, inputs,
configuration source hashes, external selected-cohort manifest, and paper
anchors.  The external manifest location must be supplied through
``--historical-cohort-manifest`` or ``SAGE_HISTORICAL_COHORT_MANIFEST``;
its logical identity and digest remain frozen in the contract.  Passing
``--results`` additionally applies the predeclared noninferiority rules to a
machine-readable final validation summary.

This verifier is intentionally outside the production packages.  It is not a
response cache and its output is not publication evidence.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_CONTRACT = Path(__file__).with_name("sage_frozen_behavior_contract_v1.json")
DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_COHORT_ENV = "SAGE_HISTORICAL_COHORT_MANIFEST"
LOCK_LINE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)$")
ACTOR_POLICY_ROLE = "actor_policy"
REPLAY_COMPARE_SOURCE = Path(__file__).resolve().parents[1] / "replay" / "compare.py"


@dataclass
class VerificationReport:
    """Accumulate named checks so all contract defects are reported together."""

    checks: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def pass_check(self, name: str, observed: Any) -> None:
        self.checks.append({"name": name, "status": "pass", "observed": observed})

    def fail(self, name: str, observed: Any, expected: Any) -> None:
        self.checks.append(
            {
                "name": name,
                "status": "fail",
                "observed": observed,
                "expected": expected,
            }
        )
        self.errors.append(f"{name}: expected {expected!r}, observed {observed!r}")

    def waive(
        self,
        name: str,
        observed: Any,
        expected: Any,
        *,
        evidence: str,
    ) -> None:
        """Record an explicit, evidence-backed exception to one named check."""

        self.checks.append(
            {
                "name": name,
                "status": "waived",
                "observed": observed,
                "expected": expected,
                "evidence": evidence,
            }
        )

    def equal(self, name: str, observed: Any, expected: Any) -> None:
        if observed == expected:
            self.pass_check(name, observed)
        else:
            self.fail(name, observed, expected)

    def close(
        self,
        name: str,
        observed: float,
        expected: float,
        *,
        tolerance: float = 1e-12,
    ) -> None:
        if math.isclose(observed, expected, rel_tol=0.0, abs_tol=tolerance):
            self.pass_check(name, observed)
        else:
            self.fail(name, observed, expected)

    def condition(self, name: str, passed: bool, observed: Any, expected: str) -> None:
        if passed:
            self.pass_check(name, observed)
        else:
            self.fail(name, observed, expected)

    def payload(self, contract_id: str) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "contract_id": contract_id,
            "status": "pass" if not self.errors else "fail",
            "check_count": len(self.checks),
            "failure_count": len(self.errors),
            "errors": self.errors,
            "checks": self.checks,
        }


def _load_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read JSON object {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_file(repo_root: Path, relative_path: str) -> Path:
    candidate = (repo_root / relative_path).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(f"Contract path escapes repository: {relative_path}") from exc
    return candidate


def _git(repo_root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"Git command could not run: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(f"git {' '.join(arguments)} failed: {detail}")
    return completed.stdout.strip()


def _module_literal(path: Path, variable: str) -> Any:
    """Read a top-level literal assignment without importing production code."""

    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for statement in module.body:
        value_node: ast.expr | None = None
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == variable
            for target in statement.targets
        ):
            value_node = statement.value
        elif (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == variable
        ):
            value_node = statement.value
        if value_node is not None:
            try:
                return ast.literal_eval(value_node)
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"{variable} in {path} is not a literal assignment"
                ) from exc
    raise ValueError(f"Could not find top-level assignment {variable} in {path}")


def _expected_replay_probes() -> list[str]:
    """Read the complete current replay suite without importing the harness."""

    probes = _module_literal(REPLAY_COMPARE_SOURCE, "DEFAULT_PROBES")
    if (
        not isinstance(probes, tuple)
        or not probes
        or any(not isinstance(item, str) or not item for item in probes)
        or len(set(probes)) != len(probes)
    ):
        raise ValueError("DEFAULT_PROBES must be a non-empty tuple of unique names")
    return list(probes)


def _verify_actor_source_equivalence_report(
    report_path: Path,
    contract: dict[str, Any],
    repo_root: Path,
    actor_source: dict[str, Any],
    report: VerificationReport,
) -> bool:
    """Validate exact replay evidence for the sole actor-source hash waiver."""

    error_count = len(report.errors)
    check_prefix = "actor_source_equivalence_report"
    try:
        evidence_path = report_path.expanduser().resolve()
        payload = _load_object(evidence_path)
        expected_probes = _expected_replay_probes()
    except (OSError, ValueError) as exc:
        report.fail(f"{check_prefix}.read", str(exc), "valid exact replay report")
        return False

    report.equal(f"{check_prefix}.schema_version", payload.get("schema_version"), 1)
    report.equal(f"{check_prefix}.status", payload.get("status"), "equivalent")
    difference_count = payload.get("difference_count")
    report.condition(
        f"{check_prefix}.difference_count",
        type(difference_count) is int and difference_count == 0,
        difference_count,
        "integer 0",
    )
    report.equal(f"{check_prefix}.differences", payload.get("differences"), [])
    report.equal(f"{check_prefix}.error", payload.get("error"), None)
    report.equal(f"{check_prefix}.probes", payload.get("probes"), expected_probes)

    normalizations = payload.get("approved_normalizations")
    normalizations_valid = (
        isinstance(normalizations, dict)
        and isinstance(normalizations.get("reference"), list)
        and isinstance(normalizations.get("candidate"), list)
    )
    report.condition(
        f"{check_prefix}.approved_normalizations",
        normalizations_valid,
        normalizations,
        "object containing reference and candidate lists",
    )

    actor_identity = payload.get("actor_source")
    actor_identity_valid = isinstance(actor_identity, dict)
    report.condition(
        f"{check_prefix}.actor_source.structure",
        actor_identity_valid,
        actor_identity,
        "object containing path and reference/candidate SHA-256 values",
    )
    reported_reference_actor_sha: Any = None
    reported_candidate_actor_sha: Any = None
    if actor_identity_valid:
        report.equal(
            f"{check_prefix}.actor_source.path",
            actor_identity.get("path"),
            actor_source["path"],
        )
        reported_reference_actor_sha = actor_identity.get("reference_sha256")
        reported_candidate_actor_sha = actor_identity.get("candidate_sha256")
        report.equal(
            f"{check_prefix}.actor_source.reference_sha256",
            reported_reference_actor_sha,
            actor_source["sha256"],
        )

    candidate_root_value = payload.get("candidate_root")
    reference_root_value = payload.get("reference_root")
    candidate_root: Path | None = None
    reference_root: Path | None = None
    if isinstance(candidate_root_value, str) and candidate_root_value:
        candidate_root = Path(candidate_root_value).expanduser().resolve()
        report.equal(
            f"{check_prefix}.candidate_root.canonical",
            candidate_root_value,
            str(candidate_root),
        )
        report.equal(
            f"{check_prefix}.candidate_root",
            str(candidate_root),
            str(repo_root.resolve()),
        )
    else:
        report.fail(
            f"{check_prefix}.candidate_root",
            candidate_root_value,
            "absolute candidate checkout path",
        )
    if isinstance(reference_root_value, str) and reference_root_value:
        reference_root = Path(reference_root_value).expanduser().resolve()
        report.equal(
            f"{check_prefix}.reference_root.canonical",
            reference_root_value,
            str(reference_root),
        )
        report.condition(
            f"{check_prefix}.reference_root.directory",
            reference_root.is_dir(),
            str(reference_root),
            "existing reference checkout directory",
        )
        report.condition(
            f"{check_prefix}.roots_are_distinct",
            candidate_root is None or reference_root != candidate_root,
            {
                "reference_root": str(reference_root),
                "candidate_root": str(candidate_root) if candidate_root else None,
            },
            "distinct reference and candidate roots",
        )
    else:
        report.fail(
            f"{check_prefix}.reference_root",
            reference_root_value,
            "absolute immutable-reference checkout path",
        )

    frozen_commit = str(contract["reference_source"]["git_commit"])
    reference_head: str | None = None
    candidate_head: str | None = None
    if reference_root is not None and reference_root.is_dir():
        try:
            reference_head = _git(reference_root, "rev-parse", "HEAD")
            reference_status = _git(
                reference_root, "status", "--porcelain", "--untracked-files=all"
            )
        except ValueError as exc:
            report.fail(
                f"{check_prefix}.reference_root.git_identity",
                str(exc),
                f"clean checkout at {frozen_commit}",
            )
        else:
            report.equal(
                f"{check_prefix}.reference_root.git_commit",
                reference_head,
                frozen_commit,
            )
            report.equal(
                f"{check_prefix}.reference_root.worktree_status",
                reference_status,
                "",
            )
        try:
            reference_actor_path = _repo_file(reference_root, str(actor_source["path"]))
            reference_actor_sha = _sha256(reference_actor_path)
        except (KeyError, OSError, ValueError) as exc:
            report.fail(
                f"{check_prefix}.reference_actor_source_sha256",
                str(exc),
                actor_source.get("sha256"),
            )
        else:
            report.equal(
                f"{check_prefix}.reference_actor_source_sha256",
                reference_actor_sha,
                actor_source["sha256"],
            )
            report.equal(
                f"{check_prefix}.actor_source.reference_report_binding",
                reported_reference_actor_sha,
                reference_actor_sha,
            )

    try:
        candidate_head = _git(repo_root, "rev-parse", "HEAD")
    except ValueError as exc:
        report.fail(
            f"{check_prefix}.candidate_root.git_identity",
            str(exc),
            "resolvable candidate HEAD",
        )

    if "reference_commit" in payload:
        report.equal(
            f"{check_prefix}.reference_commit",
            payload.get("reference_commit"),
            reference_head or frozen_commit,
        )
    if "candidate_commit" in payload:
        report.equal(
            f"{check_prefix}.candidate_commit",
            payload.get("candidate_commit"),
            candidate_head,
        )

    try:
        candidate_actor_path = _repo_file(repo_root, str(actor_source["path"]))
        candidate_actor_sha = _sha256(candidate_actor_path)
        evidence_mtime = evidence_path.stat().st_mtime_ns
        candidate_actor_mtime = candidate_actor_path.stat().st_mtime_ns
    except (KeyError, OSError, ValueError) as exc:
        report.fail(
            f"{check_prefix}.freshness",
            str(exc),
            "report created after current candidate actor source",
        )
    else:
        report.equal(
            f"{check_prefix}.actor_source.candidate_report_binding",
            reported_candidate_actor_sha,
            candidate_actor_sha,
        )
        report.condition(
            f"{check_prefix}.freshness",
            evidence_mtime >= candidate_actor_mtime,
            {
                "report_mtime_ns": evidence_mtime,
                "candidate_actor_mtime_ns": candidate_actor_mtime,
            },
            "report mtime >= candidate actor source mtime",
        )

    return len(report.errors) == error_count


def _verify_reference_identity(
    contract: dict[str, Any], repo_root: Path, report: VerificationReport
) -> None:
    source = contract["reference_source"]
    commit = source["git_commit"]
    try:
        resolved_commit = _git(repo_root, "rev-parse", f"{commit}^{{commit}}")
        resolved_tree = _git(repo_root, "rev-parse", f"{commit}^{{tree}}")
        sage_tree = _git(repo_root, "rev-parse", f"{commit}:src/sage_ts")
        toolsandbox_tree = _git(repo_root, "rev-parse", f"{commit}:tool_sandbox")
        scripts_tree = _git(repo_root, "rev-parse", f"{commit}:scripts")
        validated_sage_tree = _git(
            repo_root,
            "rev-parse",
            f"{source['validated_full_run_runtime_commit']}:src/sage_ts",
        )
    except ValueError as exc:
        report.fail("reference_source.git_objects", str(exc), "all objects resolvable")
        return
    report.equal("reference_source.git_commit", resolved_commit, commit)
    report.equal("reference_source.git_tree", resolved_tree, source["git_tree"])
    report.equal(
        "reference_source.sage_runtime_tree", sage_tree, source["sage_runtime_tree"]
    )
    report.equal(
        "reference_source.toolsandbox_runtime_tree",
        toolsandbox_tree,
        source["toolsandbox_runtime_tree"],
    )
    report.equal("reference_source.scripts_tree", scripts_tree, source["scripts_tree"])
    report.equal(
        "reference_source.validated_full_run_sage_runtime_tree",
        validated_sage_tree,
        source["validated_full_run_sage_runtime_tree"],
    )


def _verify_hash(
    name: str,
    repo_root: Path,
    record: dict[str, Any],
    report: VerificationReport,
) -> Path | None:
    try:
        path = _repo_file(repo_root, str(record["path"]))
        observed = _sha256(path)
    except (KeyError, OSError, ValueError) as exc:
        report.fail(name, str(exc), record.get("sha256"))
        return None
    report.equal(name, observed, record["sha256"])
    return path


def _verify_policy_source_hash(
    repo_root: Path,
    source: dict[str, Any],
    report: VerificationReport,
    *,
    actor_source_equivalence_valid: bool,
) -> Path | None:
    """Verify a policy source, waiving only changed actor bytes after replay."""

    role = str(source.get("role", ""))
    name = f"policy_configuration.{role}.source_sha256"
    try:
        path = _repo_file(repo_root, str(source["path"]))
        observed = _sha256(path)
        expected = source["sha256"]
    except (KeyError, OSError, ValueError) as exc:
        report.fail(name, str(exc), source.get("sha256"))
        return None
    if (
        role == ACTOR_POLICY_ROLE
        and observed != expected
        and actor_source_equivalence_valid
    ):
        report.waive(
            name,
            observed,
            expected,
            evidence="actor_source_equivalence_report",
        )
    else:
        report.equal(name, observed, expected)
    return path


def _read_lock_entries(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = LOCK_LINE.fullmatch(line)
        if match is None:
            raise ValueError(
                f"invalid exact lock entry on line {line_number}: {line!r}"
            )
        display_name, version = match.groups()
        canonical_name = re.sub(r"[-_.]+", "-", display_name).lower()
        if canonical_name in entries:
            raise ValueError(f"duplicate lock distribution: {canonical_name}")
        entries[canonical_name] = version
    return entries


def _verify_frozen_inputs(
    contract: dict[str, Any], repo_root: Path, report: VerificationReport
) -> dict[str, Any] | None:
    frozen = contract["frozen_inputs"]
    benchmark_record = frozen["benchmark"]
    benchmark_path = _verify_hash(
        "frozen_inputs.benchmark.sha256", repo_root, benchmark_record, report
    )
    evidence_path = _verify_hash(
        "frozen_inputs.paper_evidence.sha256",
        repo_root,
        frozen["paper_evidence"],
        report,
    )
    _verify_hash(
        "frozen_inputs.external_fixture.sha256",
        repo_root,
        frozen["external_fixture"],
        report,
    )
    lock_path = _verify_hash(
        "frozen_inputs.environment_lock.sha256",
        repo_root,
        frozen["environment_lock"],
        report,
    )

    if benchmark_path is not None:
        try:
            benchmark = _load_object(benchmark_path)
            records = benchmark["splits"][benchmark_record["split"]]
            names = [str(record["name"]) for record in records]
            order_hash = hashlib.sha256(
                ("\n".join(names) + "\n").encode("utf-8")
            ).hexdigest()
            report.equal(
                "frozen_inputs.benchmark.manifest_type",
                benchmark.get("manifest_type"),
                benchmark_record["manifest_type"],
            )
            report.equal(
                "frozen_inputs.benchmark.scenario_count",
                len(names),
                benchmark_record["scenario_count"],
            )
            report.equal(
                "frozen_inputs.benchmark.unique_scenario_count",
                len(set(names)),
                benchmark_record["unique_scenario_count"],
            )
            report.equal(
                "frozen_inputs.benchmark.scenario_order_sha256",
                order_hash,
                benchmark_record["scenario_order_sha256"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            report.fail(
                "frozen_inputs.benchmark.structure",
                str(exc),
                "valid ordered full_benchmark split",
            )

    if lock_path is not None:
        try:
            entries = _read_lock_entries(lock_path)
            report.equal(
                "frozen_inputs.environment_lock.exact_distribution_count",
                len(entries),
                frozen["environment_lock"]["exact_distribution_count"],
            )
        except (OSError, ValueError) as exc:
            report.fail(
                "frozen_inputs.environment_lock.format",
                str(exc),
                "unique exact name==version entries",
            )

    if evidence_path is None:
        return None
    try:
        return _load_object(evidence_path)
    except ValueError as exc:
        report.fail("frozen_inputs.paper_evidence.structure", str(exc), "JSON object")
        return None


def _verify_historical_anchor(
    contract: dict[str, Any], override: Path | None, report: VerificationReport
) -> None:
    record = contract["frozen_inputs"]["historical_selected_cohort"]
    locator = record.get("path_locator", {})
    logical_path = str(record.get("logical_path", ""))
    logical = Path(logical_path)
    report.condition(
        "historical_selected_cohort.logical_path",
        bool(logical_path)
        and not logical.is_absolute()
        and ".." not in logical.parts
        and logical.name == "selected_cohort_manifest.json",
        logical_path,
        "portable relative logical path ending in selected_cohort_manifest.json",
    )
    report.equal(
        "historical_selected_cohort.path_locator.required",
        locator.get("required"),
        True,
    )
    report.equal(
        "historical_selected_cohort.path_locator.cli_option",
        locator.get("cli_option"),
        "--historical-cohort-manifest",
    )
    report.equal(
        "historical_selected_cohort.path_locator.environment_variable",
        locator.get("environment_variable"),
        HISTORICAL_COHORT_ENV,
    )

    environment_override = os.environ.get(HISTORICAL_COHORT_ENV)
    supplied_path = override
    locator_source = "command_line"
    if supplied_path is None and environment_override:
        supplied_path = Path(environment_override)
        locator_source = f"environment:{HISTORICAL_COHORT_ENV}"
    if supplied_path is None:
        report.fail(
            "historical_selected_cohort.location",
            "not supplied",
            (
                "an explicit --historical-cohort-manifest path or "
                f"{HISTORICAL_COHORT_ENV} value"
            ),
        )
        return

    path = supplied_path.expanduser().resolve()
    report.pass_check("historical_selected_cohort.location_source", locator_source)
    try:
        observed_hash = _sha256(path)
        payload = _load_object(path)
    except (OSError, ValueError) as exc:
        report.fail("historical_selected_cohort.read", str(exc), record["sha256"])
        return
    report.equal("historical_selected_cohort.sha256", observed_hash, record["sha256"])
    for field_name in (
        "schema_version",
        "campaign_id",
        "status",
        "expected_online_runs",
        "expected_frozen_runs",
        "expected_tasks_per_run",
    ):
        report.equal(
            f"historical_selected_cohort.{field_name}",
            payload.get(field_name),
            record[field_name],
        )
    benchmark = contract["frozen_inputs"]["benchmark"]
    fixture = contract["frozen_inputs"]["external_fixture"]
    environment = contract["frozen_inputs"]["environment_lock"]
    clock = contract["frozen_inputs"]["clock"]
    primary_evaluator = contract["evaluator_configuration"]["primary"]
    comparable_evaluator = contract["evaluator_configuration"]["paper_comparable"]
    report.equal(
        "historical_selected_cohort.benchmark_sha256",
        payload.get("benchmark_sha256"),
        benchmark["sha256"],
    )
    report.equal(
        "historical_selected_cohort.external_fixture.sha256",
        payload.get("external_fixture", {}).get("sha256"),
        fixture["sha256"],
    )
    report.equal(
        "historical_selected_cohort.external_fixture.mode",
        payload.get("external_fixture", {}).get("mode"),
        fixture["mode"],
    )
    report.equal(
        "historical_selected_cohort.fixed_toolsandbox_timestamp",
        payload.get("fixed_toolsandbox_timestamp"),
        clock["toolsandbox_fixed_now_timestamp"],
    )
    configuration = payload.get("configuration_identity", {})
    report.equal(
        "historical_selected_cohort.environment_lock_sha256",
        configuration.get("environment_lock_sha256"),
        environment["sha256"],
    )
    for contract_field in (
        "python_version",
        "python_implementation",
        "platform_system",
        "platform_machine",
    ):
        report.equal(
            f"historical_selected_cohort.{contract_field}",
            configuration.get(contract_field),
            environment[contract_field],
        )
    report.equal(
        "historical_selected_cohort.external_distribution_count",
        configuration.get("external_distribution_count"),
        environment["exact_distribution_count"],
    )
    report.equal(
        "historical_selected_cohort.timezone",
        configuration.get("execution_environment", {}).get("TZ"),
        clock["timezone"],
    )
    report.equal(
        "historical_selected_cohort.model",
        payload.get("model"),
        contract["model_configuration"]["agent"],
    )
    endpoints = payload.get("statistical_plan", {}).get("performance_endpoints", {})
    for endpoint_name, evaluator in (
        ("audited_current_all_tasks", primary_evaluator),
        ("paper_comparable_historical_subset", comparable_evaluator),
    ):
        endpoint = endpoints.get(endpoint_name, {})
        report.equal(
            f"historical_selected_cohort.{endpoint_name}.metric_field",
            endpoint.get("metric_field"),
            evaluator["metric_field"],
        )
        report.equal(
            f"historical_selected_cohort.{endpoint_name}.evaluator_version",
            endpoint.get("evaluator_version"),
            evaluator["version"],
        )
    run_pairs = payload.get("run_pairs", [])
    report.equal(
        "historical_selected_cohort.run_pair_count",
        len(run_pairs) if isinstance(run_pairs, list) else None,
        record["expected_online_runs"],
    )
    if isinstance(run_pairs, list):
        for pair_index, pair in enumerate(run_pairs, start=1):
            if not isinstance(pair, dict):
                report.fail(
                    f"historical_selected_cohort.run_pair_{pair_index}.structure",
                    type(pair).__name__,
                    "object",
                )
                continue
            for arm_name in ("online", "frozen"):
                measurements = (
                    pair.get(arm_name, {}).get("endpoint_measurements", {})
                    if isinstance(pair.get(arm_name), dict)
                    else {}
                )
                primary = measurements.get("audited_current_all_tasks", {})
                comparable = measurements.get("paper_comparable_historical_subset", {})
                prefix = f"historical_selected_cohort.run_pair_{pair_index}.{arm_name}"
                report.equal(
                    f"{prefix}.primary_evaluator_version",
                    primary.get("evaluator_version"),
                    primary_evaluator["version"],
                )
                report.equal(
                    f"{prefix}.primary_evaluator_contract_sha256",
                    primary.get("evaluator_contract_sha256"),
                    primary_evaluator["contract_sha256"],
                )
                report.equal(
                    f"{prefix}.primary_task_count",
                    primary.get("task_count"),
                    benchmark["scenario_count"],
                )
                report.equal(
                    f"{prefix}.paper_comparable_evaluator_version",
                    comparable.get("evaluator_version"),
                    comparable_evaluator["version"],
                )
                report.equal(
                    f"{prefix}.paper_comparable_task_count",
                    comparable.get("task_count"),
                    comparable_evaluator["task_count_per_run"],
                )


def _verify_configuration_sources(
    contract: dict[str, Any],
    repo_root: Path,
    report: VerificationReport,
    *,
    actor_source_equivalence_report: Path | None = None,
) -> None:
    model = contract["model_configuration"]
    model_path = _verify_hash(
        "model_configuration.source_sha256",
        repo_root,
        model["model_config_source"],
        report,
    )
    policy_sources = contract["policy_configuration"]["source_hashes"]
    actor_source_equivalence_valid = False
    if actor_source_equivalence_report is not None:
        actor_sources = [
            source
            for source in policy_sources
            if source.get("role") == ACTOR_POLICY_ROLE
        ]
        if len(actor_sources) != 1:
            report.fail(
                "actor_source_equivalence_report.actor_source_record",
                len(actor_sources),
                "exactly one actor_policy source record",
            )
        else:
            actor_source_equivalence_valid = _verify_actor_source_equivalence_report(
                actor_source_equivalence_report,
                contract,
                repo_root,
                actor_sources[0],
                report,
            )
    for source in policy_sources:
        _verify_policy_source_hash(
            repo_root,
            source,
            report,
            actor_source_equivalence_valid=actor_source_equivalence_valid,
        )
    primary = contract["evaluator_configuration"]["primary"]
    primary_path = _verify_hash(
        "evaluator_configuration.primary.source_sha256",
        repo_root,
        primary["source"],
        report,
    )
    comparable = contract["evaluator_configuration"]["paper_comparable"]
    comparable_path = _verify_hash(
        "evaluator_configuration.paper_comparable.source_sha256",
        repo_root,
        comparable["source"],
        report,
    )

    protocol_path = _repo_file(repo_root, "scripts/run_sage_protocol.py")
    try:
        report.equal(
            "model_configuration.DEFAULT_MODEL",
            _module_literal(model_path, "DEFAULT_MODEL") if model_path else None,
            model["agent"],
        )
        report.equal(
            "policy_configuration.ACTOR_SELECTION_MODE",
            _module_literal(protocol_path, "ACTOR_SELECTION_MODE"),
            contract["policy_configuration"]["actor_selection_mode"],
        )
        report.equal(
            "policy_configuration.online_sage_policy",
            _module_literal(protocol_path, "SAGE_POLICY_SELF_EVOLVING_PRAXIS"),
            contract["policy_configuration"]["online_sage_policy"],
        )
        report.equal(
            "policy_configuration.frozen_sage_policy",
            _module_literal(protocol_path, "SAGE_POLICY_NONE"),
            contract["policy_configuration"]["frozen_sage_policy"],
        )
        report.equal(
            "frozen_inputs.clock.toolsandbox_fixed_now_timestamp",
            _module_literal(protocol_path, "PUBLICATION_FIXED_TOOLSANDBOX_TIMESTAMP"),
            contract["frozen_inputs"]["clock"]["toolsandbox_fixed_now_timestamp"],
        )
        execution_env = _module_literal(protocol_path, "PUBLICATION_EXECUTION_ENV")
        report.equal(
            "frozen_inputs.clock.timezone",
            execution_env.get("TZ"),
            contract["frozen_inputs"]["clock"]["timezone"],
        )
        report.equal(
            "evaluator_configuration.primary.version",
            _module_literal(primary_path, "OUTCOME_EVALUATOR_VERSION")
            if primary_path
            else None,
            primary["version"],
        )
        report.equal(
            "evaluator_configuration.paper_comparable.version",
            _module_literal(comparable_path, "ONLINE_FEEDBACK_EVALUATOR_VERSION")
            if comparable_path
            else None,
            comparable["version"],
        )
    except (AttributeError, OSError, SyntaxError, ValueError) as exc:
        report.fail("configuration.literal_identity", str(exc), "frozen literals")


def _hypothesis(evidence: dict[str, Any], hypothesis_id: str) -> dict[str, Any]:
    for record in evidence.get("hypotheses", []):
        if isinstance(record, dict) and record.get("id") == hypothesis_id:
            return record
    raise ValueError(f"Missing {hypothesis_id} in paper evidence")


def _verify_paper_anchors(
    contract: dict[str, Any],
    evidence: dict[str, Any] | None,
    report: VerificationReport,
) -> None:
    if evidence is None:
        return
    anchors = contract["paper_anchors"]
    try:
        campaign = evidence["campaign"]
        report.equal(
            "paper_anchors.campaign.completed_online_runs",
            campaign["completed_online_runs"],
            anchors["campaign"]["completed_online_runs"],
        )
        report.equal(
            "paper_anchors.campaign.completed_frozen_runs",
            campaign["completed_frozen_runs"],
            anchors["campaign"]["completed_frozen_runs"],
        )
        report.equal(
            "paper_anchors.campaign.tasks_per_run",
            campaign["tasks_per_run"],
            anchors["campaign"]["tasks_per_run"],
        )
        report.equal(
            "paper_anchors.campaign.matched_online_observations",
            campaign["audited_current_matched_observations"],
            anchors["campaign"]["matched_online_observations"],
        )
        report.equal(
            "paper_anchors.campaign.paper_comparable_observations",
            campaign["paper_comparable_matched_observations"],
            anchors["campaign"]["paper_comparable_observations"],
        )
        report.equal(
            "historical_selected_cohort.evidence_sha256",
            campaign["source_campaign_manifest_sha256"],
            contract["frozen_inputs"]["historical_selected_cohort"]["sha256"],
        )

        current = evidence["performance_endpoints"]["audited_current_all_tasks"]
        h1_anchor = anchors["h1_task_completion"]
        for evidence_key, contract_key in (
            ("baseline", "baseline_mean"),
            ("sage", "sage_mean"),
            ("absolute_difference", "absolute_difference"),
            ("relative_lift_percent", "relative_lift_percent"),
        ):
            report.close(
                f"paper_anchors.h1.{contract_key}",
                float(current[evidence_key]),
                float(h1_anchor[contract_key]),
            )
        h1 = _hypothesis(evidence, "Hypothesis 1")
        report.equal("paper_anchors.h1.decision", h1["decision"], h1_anchor["decision"])
        statistics = evidence["statistics"]
        report.close(
            "paper_anchors.h1.run_threshold_sign_flip_p",
            float(statistics["run_threshold_contrast_sign_flip_p"]),
            float(h1_anchor["run_threshold_sign_flip_p"]),
        )
        report.equal(
            "paper_anchors.h1.baseline_successes",
            statistics["baseline_successes"],
            h1_anchor["baseline_successes"],
        )
        report.equal(
            "paper_anchors.h1.sage_successes",
            statistics["sage_successes"],
            h1_anchor["sage_successes"],
        )
        for source_key, anchor_key in (
            ("two_way_run_task_bootstrap_delta_ci", "two_way_run_task_delta_ci_95"),
            (
                "two_way_run_task_bootstrap_threshold_contrast_ci",
                "two_way_threshold_contrast_ci_95",
            ),
            (
                "run_cluster_threshold_contrast_ci",
                "run_cluster_threshold_contrast_ci_95",
            ),
        ):
            observed_ci = statistics[source_key]
            expected_ci = h1_anchor[anchor_key]
            report.close(
                f"paper_anchors.h1.{anchor_key}.lower",
                float(observed_ci["lower"]),
                float(expected_ci[0]),
            )
            report.close(
                f"paper_anchors.h1.{anchor_key}.upper",
                float(observed_ci["upper"]),
                float(expected_ci[1]),
            )

        comparable = evidence["performance_endpoints"][
            "paper_comparable_historical_subset"
        ]
        comparable_anchor = anchors["paper_comparable_800_task_endpoint"]
        for evidence_key, contract_key in (
            ("baseline", "baseline_mean"),
            ("sage", "sage_mean"),
            ("absolute_difference", "absolute_difference"),
            ("relative_lift_percent", "relative_lift_percent"),
        ):
            report.close(
                f"paper_anchors.paper_comparable.{contract_key}",
                float(comparable[evidence_key]),
                float(comparable_anchor[contract_key]),
            )

        frozen_anchor = anchors["frozen_registry"]
        report.close(
            "paper_anchors.frozen.sage_mean",
            float(evidence["performance"]["frozen_sage"]),
            float(frozen_anchor["sage_mean"]),
        )
        supporting = evidence["supporting_reuse"]
        report.close(
            "paper_anchors.frozen.gain_retention_percent",
            float(supporting["frozen_gain_retention_percent"]),
            float(frozen_anchor["gain_retention_percent"]),
        )
        observed_frozen_ci = supporting["frozen_gain_retention_confidence_interval"]
        report.close(
            "paper_anchors.frozen.gain_retention_ci_95.lower",
            float(observed_frozen_ci["lower"]),
            float(frozen_anchor["gain_retention_ci_95"][0]),
        )
        report.close(
            "paper_anchors.frozen.gain_retention_ci_95.upper",
            float(observed_frozen_ci["upper"]),
            float(frozen_anchor["gain_retention_ci_95"][1]),
        )

        evolution = evidence["evolution_metrics"]
        totals = evolution["totals"]
        h2_anchor = anchors["h2_repair_and_later_reuse"]
        h2 = _hypothesis(evidence, "Hypothesis 2")
        report.equal("paper_anchors.h2.decision", h2["decision"], h2_anchor["decision"])
        for field_name in (
            "repair_entrants",
            "repaired_accepted",
            "repaired_reused_later",
        ):
            report.equal(
                f"paper_anchors.h2.{field_name}",
                totals[field_name],
                h2_anchor[field_name],
            )
        report.close(
            "paper_anchors.h2.repair_conversion_rate",
            float(evolution["repair_conversion_percent"]) / 100.0,
            float(h2_anchor["repair_conversion_rate"]),
        )
        observed_h2_ci = evolution["repair_conversion_run_cluster_ci"]
        report.close(
            "paper_anchors.h2.repair_conversion_run_cluster_ci_95.lower",
            float(observed_h2_ci["lower"]) / 100.0,
            float(h2_anchor["repair_conversion_run_cluster_ci_95"][0]),
        )
        report.close(
            "paper_anchors.h2.repair_conversion_run_cluster_ci_95.upper",
            float(observed_h2_ci["upper"]) / 100.0,
            float(h2_anchor["repair_conversion_run_cluster_ci_95"][1]),
        )
        report.close(
            "paper_anchors.h2.repair_threshold_sign_flip_p",
            float(evolution["repair_threshold_sign_flip_p"]),
            float(h2_anchor["repair_threshold_sign_flip_p"]),
        )
        report.close(
            "paper_anchors.h2.repaired_reuse_rate",
            float(evolution["repaired_reuse_percent"]) / 100.0,
            float(h2_anchor["repaired_reuse_rate"]),
        )

        h3_anchor = anchors["h3_cross_family_use"]
        h3 = _hypothesis(evidence, "Hypothesis 3")
        report.equal("paper_anchors.h3.decision", h3["decision"], h3_anchor["decision"])
        for field_name in ("accepted_tools", "cross_family_tools"):
            report.equal(
                f"paper_anchors.h3.{field_name}",
                totals[field_name],
                h3_anchor[field_name],
            )
        report.close(
            "paper_anchors.h3.cross_family_rate",
            float(evolution["cross_family_percent"]) / 100.0,
            float(h3_anchor["cross_family_rate"]),
        )
        observed_h3_ci = evolution["cross_family_run_cluster_ci"]
        report.close(
            "paper_anchors.h3.cross_family_run_cluster_ci_95.lower",
            float(observed_h3_ci["lower"]) / 100.0,
            float(h3_anchor["cross_family_run_cluster_ci_95"][0]),
        )
        report.close(
            "paper_anchors.h3.cross_family_run_cluster_ci_95.upper",
            float(observed_h3_ci["upper"]) / 100.0,
            float(h3_anchor["cross_family_run_cluster_ci_95"][1]),
        )
        report.close(
            "paper_anchors.h3.cross_family_threshold_sign_flip_p",
            float(evolution["cross_family_threshold_sign_flip_p"]),
            float(h3_anchor["cross_family_threshold_sign_flip_p"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        report.fail("paper_anchors.structure", str(exc), "all frozen evidence fields")


def _verify_gate_formulas(contract: dict[str, Any], report: VerificationReport) -> None:
    anchors = contract["paper_anchors"]
    gates = contract["predeclared_acceptance_gates"]
    primary = gates["primary_outcome_noninferiority"]
    report.close(
        "gates.primary.reference_mean",
        float(primary["reference_mean"]),
        float(anchors["h1_task_completion"]["sage_mean"]),
    )
    report.close(
        "gates.primary.minimum_new_mean_formula",
        float(primary["minimum_new_mean"]),
        float(primary["reference_mean"]) - float(primary["absolute_margin"]),
    )
    paired = gates["paired_improvement"]
    report.close(
        "gates.paired.minimum_difference_formula",
        float(paired["minimum_difference"]),
        float(paired["reference_difference"]) - float(paired["absolute_margin"]),
    )
    comparable = gates["paper_comparable_endpoint"]
    report.close(
        "gates.paper_comparable.minimum_new_mean_formula",
        float(comparable["minimum_new_mean"]),
        float(comparable["reference_mean"]) - float(comparable["absolute_margin"]),
    )
    frozen = gates["frozen_registry"]
    report.close(
        "gates.frozen.minimum_new_mean_formula",
        float(frozen["minimum_new_mean"]),
        float(frozen["reference_mean"]) - float(frozen["absolute_margin"]),
    )
    for gate_name, reference_field, margin_field, minimum_field in (
        (
            "h2_repair_and_later_reuse",
            "reference_repair_conversion_rate",
            "noninferiority_margin",
            "minimum_repair_conversion_rate",
        ),
        (
            "h3_cross_family_use",
            "reference_cross_family_rate",
            "noninferiority_margin",
            "minimum_cross_family_rate",
        ),
    ):
        gate = gates[gate_name]
        report.close(
            f"gates.{gate_name}.minimum_formula",
            float(gate[minimum_field]),
            float(gate[reference_field]) - float(gate[margin_field]),
        )
    h2_anchor = anchors["h2_repair_and_later_reuse"]
    report.close(
        "paper_anchors.h2.count_rate_consistency",
        float(h2_anchor["repair_conversion_rate"]),
        h2_anchor["repaired_accepted"] / h2_anchor["repair_entrants"],
    )
    h3_anchor = anchors["h3_cross_family_use"]
    report.close(
        "paper_anchors.h3.count_rate_consistency",
        float(h3_anchor["cross_family_rate"]),
        h3_anchor["cross_family_tools"] / h3_anchor["accepted_tools"],
    )


def _number(results: dict[str, Any], name: str) -> float:
    value = results.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Result field {name!r} must be numeric")
    return float(value)


def _apply_results_gates(
    contract: dict[str, Any], results: dict[str, Any], report: VerificationReport
) -> None:
    """Apply the predeclared gates to a compact final validation summary."""

    gates = contract["predeclared_acceptance_gates"]
    accounting = gates["replication_accounting"]
    try:
        for field_name, expected_key in (
            ("online_runs", "required_online_runs"),
            ("frozen_runs", "required_frozen_runs"),
            ("tasks_per_run", "required_tasks_per_run"),
            ("runtime_exception_count", "required_runtime_exception_count"),
            ("integrity_violation_count", "required_integrity_violation_count"),
        ):
            report.equal(
                f"results.{field_name}",
                results.get(field_name),
                accounting[expected_key],
            )
        report.equal(
            "results.performance_based_exclusion_count",
            results.get("performance_based_exclusion_count"),
            0,
        )

        primary = gates["primary_outcome_noninferiority"]
        value = _number(results, "new_sage_mean_outcome")
        report.condition(
            "results.new_sage_mean_outcome",
            value >= float(primary["minimum_new_mean"]),
            value,
            f">= {primary['minimum_new_mean']}",
        )
        value = _number(results, "new_minus_reference_ci_lower")
        report.condition(
            "results.new_minus_reference_ci_lower",
            value > float(primary["ci_lower_threshold"]),
            value,
            f"> {primary['ci_lower_threshold']}",
        )

        paired = gates["paired_improvement"]
        value = _number(results, "new_sage_minus_control_mean")
        report.condition(
            "results.new_sage_minus_control_mean",
            value >= float(paired["minimum_difference"]),
            value,
            f">= {paired['minimum_difference']}",
        )

        h1 = gates["h1_original_decision_rule"]
        for field_name, threshold_key, strict in (
            ("h1_relative_lift_percent", "minimum_relative_lift_percent", False),
            (
                "h1_two_way_threshold_contrast_ci_lower",
                "two_way_threshold_contrast_ci_lower_threshold",
                True,
            ),
            (
                "h1_run_cluster_threshold_contrast_ci_lower",
                "run_cluster_threshold_contrast_ci_lower_threshold",
                True,
            ),
        ):
            value = _number(results, field_name)
            threshold = float(h1[threshold_key])
            passed = value > threshold if strict else value >= threshold
            report.condition(
                f"results.{field_name}",
                passed,
                value,
                f"{'> ' if strict else '>= '}{threshold}",
            )
        value = _number(results, "h1_run_threshold_sign_flip_p")
        report.condition(
            "results.h1_run_threshold_sign_flip_p",
            value < float(h1["run_threshold_sign_flip_p_threshold"]),
            value,
            f"< {h1['run_threshold_sign_flip_p_threshold']}",
        )

        comparable = gates["paper_comparable_endpoint"]
        value = _number(results, "paper_comparable_sage_mean")
        report.condition(
            "results.paper_comparable_sage_mean",
            value >= float(comparable["minimum_new_mean"]),
            value,
            f">= {comparable['minimum_new_mean']}",
        )
        report.equal(
            "results.paper_comparable_tasks_per_run",
            results.get("paper_comparable_tasks_per_run"),
            comparable["required_tasks_per_run"],
        )

        frozen = gates["frozen_registry"]
        value = _number(results, "frozen_sage_mean")
        report.condition(
            "results.frozen_sage_mean",
            value >= float(frozen["minimum_new_mean"]),
            value,
            f">= {frozen['minimum_new_mean']}",
        )
        value = _number(results, "frozen_gain_retention_percent")
        report.condition(
            "results.frozen_gain_retention_percent",
            value >= float(frozen["minimum_gain_retention_percent"]),
            value,
            f">= {frozen['minimum_gain_retention_percent']}",
        )

        for prefix, gate_name, estimate_field, minimum_field in (
            (
                "h2",
                "h2_repair_and_later_reuse",
                "h2_repair_conversion_rate",
                "minimum_repair_conversion_rate",
            ),
            (
                "h3",
                "h3_cross_family_use",
                "h3_cross_family_rate",
                "minimum_cross_family_rate",
            ),
        ):
            gate = gates[gate_name]
            estimate = _number(results, estimate_field)
            report.condition(
                f"results.{estimate_field}",
                estimate >= float(gate[minimum_field])
                and estimate > float(gate["support_threshold_rate"]),
                estimate,
                f">= {gate[minimum_field]} and > {gate['support_threshold_rate']}",
            )
            ci_field = f"{prefix}_run_cluster_ci_lower"
            ci_lower = _number(results, ci_field)
            report.condition(
                f"results.{ci_field}",
                ci_lower > float(gate["run_cluster_ci_lower_threshold"]),
                ci_lower,
                f"> {gate['run_cluster_ci_lower_threshold']}",
            )
            p_field = f"{prefix}_sign_flip_p"
            p_value = _number(results, p_field)
            report.condition(
                f"results.{p_field}",
                p_value < float(gate["sign_flip_p_threshold"]),
                p_value,
                f"< {gate['sign_flip_p_threshold']}",
            )
        h2 = gates["h2_repair_and_later_reuse"]
        value = _number(results, "h2_repaired_reuse_rate")
        report.condition(
            "results.h2_repaired_reuse_rate",
            value >= float(h2["minimum_repaired_reuse_rate"]),
            value,
            f">= {h2['minimum_repaired_reuse_rate']}",
        )

        strata_gate = gates["predeclared_strata"]
        strata = results.get("predeclared_strata")
        if not isinstance(strata, list):
            raise ValueError("Result field 'predeclared_strata' must be a list")
        for index, stratum in enumerate(strata):
            if not isinstance(stratum, dict):
                raise ValueError(f"predeclared_strata[{index}] must be an object")
            observations = int(stratum.get("observations", -1))
            decline = float(stratum.get("absolute_outcome_decline", math.inf))
            name = str(stratum.get("name", index))
            if observations < int(strata_gate["minimum_observations_for_gate"]):
                report.pass_check(
                    f"results.strata.{name}.not_gated",
                    {"observations": observations, "absolute_outcome_decline": decline},
                )
                continue
            report.condition(
                f"results.strata.{name}.maximum_decline",
                decline <= float(strata_gate["maximum_absolute_outcome_decline"]),
                decline,
                f"<= {strata_gate['maximum_absolute_outcome_decline']}",
            )
    except (KeyError, TypeError, ValueError) as exc:
        report.fail("results.structure", str(exc), "complete final validation summary")


def verify(
    contract_path: Path,
    repo_root: Path,
    *,
    historical_anchor: Path | None = None,
    results_path: Path | None = None,
    actor_source_equivalence_report: Path | None = None,
) -> tuple[dict[str, Any], VerificationReport]:
    contract = _load_object(contract_path)
    report = VerificationReport()
    report.equal("contract.schema_version", contract.get("schema_version"), 1)
    report.equal(
        "contract.scope.canonical_score_is_a_gate",
        contract.get("scope", {}).get("canonical_score_is_a_gate"),
        False,
    )
    report.equal(
        "contract.scope.performance_based_run_exclusion_allowed",
        contract.get("scope", {}).get("performance_based_run_exclusion_allowed"),
        False,
    )
    _verify_reference_identity(contract, repo_root, report)
    evidence = _verify_frozen_inputs(contract, repo_root, report)
    _verify_historical_anchor(contract, historical_anchor, report)
    _verify_configuration_sources(
        contract,
        repo_root,
        report,
        actor_source_equivalence_report=actor_source_equivalence_report,
    )
    _verify_paper_anchors(contract, evidence, report)
    _verify_gate_formulas(contract, report)
    if results_path is not None:
        try:
            results = _load_object(results_path)
        except ValueError as exc:
            report.fail("results.read", str(exc), "JSON object")
        else:
            _apply_results_gates(contract, results, report)
    return contract, report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument(
        "--historical-cohort-manifest",
        "--historical-anchor",
        dest="historical_cohort_manifest",
        type=Path,
        help=(
            "Required external selected-cohort manifest path. The deprecated "
            "--historical-anchor spelling remains accepted. If omitted, read "
            f"{HISTORICAL_COHORT_ENV}."
        ),
    )
    parser.add_argument(
        "--results",
        type=Path,
        help="Optional final validation summary to evaluate against the frozen gates.",
    )
    parser.add_argument(
        "--actor-source-equivalence-report",
        type=Path,
        help=(
            "Optional exact replay report permitting only the actor_policy source "
            "SHA check to be marked waived. The report must prove a complete, "
            "zero-difference replay against the immutable reference checkout."
        ),
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit the full JSON report."
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        contract, report = verify(
            args.contract.resolve(),
            args.repo_root.resolve(),
            historical_anchor=args.historical_cohort_manifest,
            results_path=args.results,
            actor_source_equivalence_report=args.actor_source_equivalence_report,
        )
    except (KeyError, OSError, TypeError, ValueError) as exc:
        print(f"frozen_contract_verification=failed\n{exc}", file=sys.stderr)
        return 1
    payload = report.payload(str(contract.get("contract_id", "")))
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"frozen_contract_verification={payload['status']}")
        print(f"contract_id={payload['contract_id']}")
        print(f"checks={payload['check_count']}")
        print(f"failures={payload['failure_count']}")
        for error in report.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    return 0 if not report.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
