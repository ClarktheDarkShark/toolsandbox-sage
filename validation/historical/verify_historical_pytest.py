#!/usr/bin/env python3
"""Run the frozen historical pytest compatibility gate in three shards.

This module is external validation infrastructure.  Tests are collected from
the immutable test-oracle checkout while imports resolve only from the
candidate checkout supplied on the command line.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping, Sequence


EXPECTED_PARTITION_SHA256 = (
    "b7d6f521ed1aceed160a960a42f5a362d242b92e8b2953a65b7c19dcd421ae5b"
)
EXPECTED_TOTAL = 1_167

APPROVED_WARNING_MESSAGES = {
    "pandas_numexpr_version": (
        "UserWarning: Pandas requires version '2.10.2' or newer of 'numexpr' "
        "(version '2.8.7' currently installed)."
    ),
    "pandas_bottleneck_version": (
        "UserWarning: Pandas requires version '1.4.2' or newer of 'bottleneck' "
        "(version '1.3.7' currently installed)."
    ),
}
APPROVED_WARNING_COUNTS = (0, len(APPROVED_WARNING_MESSAGES))

INTENTIONAL_DESELECTIONS = (
    "tests/unit/test_tool_generator.py::test_generation_request_includes_reusable_name_hint",
    "tests/unit/test_tool_generator.py::test_generation_request_preserves_negative_applicability_metadata",
    "tests/unit/test_tool_generator.py::test_generation_request_includes_family_contract_guidance",
    "tests/unit/test_tool_generator.py::test_generation_request_includes_exact_contact_phone_normalization",
    "tests/unit/test_tool_generator.py::test_generation_request_requires_contract_fields",
    "tests/unit/test_tool_generator.py::test_generation_request_includes_medium_grain_guidance",
    "tests/unit/test_tool_generator.py::test_generation_request_includes_failure_memory_and_cluster_context",
)


@dataclass(frozen=True)
class Shard:
    name: str
    selectors: tuple[str, ...]
    expected_passed: int
    expected_summary: str
    deselections: tuple[str, ...] = ()


SHARDS = (
    Shard(
        name="shard1",
        selectors=(
            "tests/unit/test_outcome_score_v4_evidence.py::test_information_answer_does_not_depend_on_tool_result_shape",
            "tests/unit/test_outcome_score_v4_evidence.py::test_epistemic_negation_is_not_mistaken_for_positive_contrast",
            "tests/unit/test_outcome_score_v4_evidence.py::test_abstention_requires_positive_scoped_missing_information",
            "tests/unit/test_outcome_score_v4_evidence.py::test_negated_missing_information_does_not_count_as_abstention",
            "tests/unit/test_outcome_score_v4_evidence.py::test_separated_without_reason_requires_matching_task_limitation",
            "tests/unit/test_outcome_score_v4_evidence.py::test_preserved_wrong_numeric_completion_after_advice_remains_rejected",
            "tests/unit/test_outcome_score_v4_evidence.py::test_genuine_post_limitation_wrong_city_remains_rejected",
            "tests/unit/test_outcome_score_v4_evidence.py::test_unrelated_recovery_does_not_clear_prior_limitation",
            "tests/unit/test_outcome_score_v4_evidence.py::test_targeted_cross_sentence_recovery_needs_no_contrast_marker",
            "tests/unit/test_outcome_score_v4_evidence.py::test_baseline_reminder_answer_requires_a_full_phrase_boundary",
            "tests/unit/test_outcome_score_v4_evidence.py::test_insufficient_contract_does_not_ignore_later_retraction_or_bare_answer",
            "tests/unit/test_outcome_score_v4_evidence.py::test_insufficient_contract_orders_possession_and_anaphoric_limitations",
            "tests/unit/test_outcome_score_v4_evidence.py::test_natural_retractions_invalidate_an_earlier_limitation",
            "tests/unit/test_outcome_score_v4_evidence.py::test_insufficient_contract_ignores_proven_imperative_guidance",
            "tests/unit/test_outcome_score_v4_evidence.py::test_insufficient_contract_does_not_ignore_later_false_reminder_claim",
            "tests/unit/test_outcome_score_v4_evidence.py::test_insufficient_contract_does_not_ignore_first_person_negative_search_result",
            "tests/unit/test_outcome_score_v4_evidence.py::test_reminder_negative_result_language_is_outcome_bearing",
            "tests/unit/test_outcome_score_v4_evidence.py::test_reminder_negative_result_nonclaims_do_not_supersede",
            "tests/unit/test_outcome_score.py",
        ),
        expected_passed=398,
        expected_summary="398 passed",
    ),
    Shard(
        name="shard2",
        selectors=(
            "tests/unit/test_outcome_score_v4_evidence.py::test_candidate_specific_negation_fails",
            "tests/unit/test_outcome_score_v4_evidence.py::test_scalar_answer_hedges_and_corrections_fail",
            "tests/unit/test_outcome_score_v4_evidence.py::test_unresolved_limitation_cannot_be_hidden_by_a_filler_clause",
            "tests/unit/test_outcome_score_v4_evidence.py::test_grounded_text_requires_a_whole_phrase_match",
            "tests/unit/test_outcome_score_v4_evidence.py::test_positive_scoped_missing_information_still_passes",
            "tests/unit/test_outcome_score_v4_evidence.py::test_preserved_limitation_advice_is_not_a_completion",
            "tests/unit/test_outcome_score_v4_evidence.py::test_nonassertive_text_candidates_fail",
            "tests/unit/test_outcome_score_v4_evidence.py::test_targeted_generated_recovery_can_cross_a_sentence_boundary",
            "tests/unit/test_outcome_score_v4_evidence.py::test_numeric_context_is_candidate_local_and_exact",
            "tests/unit/test_outcome_score_v4_evidence.py::test_social_closure_retains_earlier_targeted_clarification",
            "tests/unit/test_outcome_score_v4_evidence.py::test_insufficient_contract_later_wrong_outcome_overrides_correct_abstention",
            "tests/unit/test_outcome_score_v4_evidence.py::test_insufficient_contract_does_not_treat_limitation_language_as_retraction",
            "tests/unit/test_outcome_score_v4_evidence.py::test_setup_completion_does_not_override_later_missing_information",
            "tests/unit/test_outcome_score_v4_evidence.py::test_tangential_failure_dialogue_does_not_erase_a_correct_outcome",
            "tests/unit/test_outcome_score_v4_evidence.py::test_insufficient_contract_does_not_hide_later_substantive_response",
            "tests/unit/test_outcome_score_v4_evidence.py::test_negative_reminder_search_result_is_scoped_to_reminder_contracts",
            "tests/unit/test_outcome_score_v4_evidence.py::test_unrelated_not_without_does_not_hide_later_real_limitation",
            "tests/unit/test_outcome_score_v4_evidence.py::test_do_so_is_not_mistaken_for_a_discourse_boundary",
            "tests/unit/test_outcome_score_v4_evidence.py::test_later_concrete_reminder_result_supersedes_prior_limitation",
            "tests/unit/test_outcome_score_v4_evidence.py::test_temporal_insufficient_information_accepts_natural_limitations",
            "tests/unit/test_base_toolset.py",
            "tests/unit/test_campaign_artifacts.py",
            "tests/unit/test_candidate_gate.py",
            "tests/unit/test_complete_tools.py",
            "tests/unit/test_dashboard_exporters.py",
            "tests/unit/test_failure_memory_integration.py",
            "tests/unit/test_online_birth.py",
            "tests/unit/test_openai_toolsandbox_roles.py",
            "tests/unit/test_tool_generator.py",
        ),
        expected_passed=384,
        expected_summary="384 passed, 7 deselected",
        deselections=INTENTIONAL_DESELECTIONS,
    ),
    Shard(
        name="shard3",
        selectors=(
            "tests/unit/test_outcome_score_v4_evidence.py::test_information_contract_accepts_exact_answer_without_tool_result",
            "tests/unit/test_outcome_score_v4_evidence.py::test_text_answer_hedges_and_post_candidate_corrections_fail",
            "tests/unit/test_outcome_score_v4_evidence.py::test_candidate_scoping_preserves_positive_contrast",
            "tests/unit/test_outcome_score_v4_evidence.py::test_explicitly_resolved_prior_limitation_allows_exact_answer",
            "tests/unit/test_outcome_score_v4_evidence.py::test_unresolved_limitation_before_answer_fails_across_punctuation",
            "tests/unit/test_outcome_score_v4_evidence.py::test_generated_terminal_action_remains_a_positive_control",
            "tests/unit/test_outcome_score_v4_evidence.py::test_positive_missing_information_and_guidance_remain_valid",
            "tests/unit/test_outcome_score_v4_evidence.py::test_without_does_not_turn_capability_or_unrelated_limits_into_abstention",
            "tests/unit/test_outcome_score_v4_evidence.py::test_nonassertive_scalar_candidates_fail",
            "tests/unit/test_outcome_score_v4_evidence.py::test_later_target_domain_correction_fails",
            "tests/unit/test_outcome_score_v4_evidence.py::test_nonaffirmative_or_incidental_recovery_does_not_clear_limitation",
            "tests/unit/test_outcome_score_v4_evidence.py::test_abstention_may_end_with_an_offer_to_assist",
            "tests/unit/test_outcome_score_v4_evidence.py::test_coordinate_answer_context_association_and_polarity",
            "tests/unit/test_outcome_score_v4_evidence.py::test_insufficient_contract_ignores_later_non_outcome_dialogue",
            "tests/unit/test_outcome_score_v4_evidence.py::test_natural_auxiliary_and_anaphoric_limitations_are_valid",
            "tests/unit/test_outcome_score_v4_evidence.py::test_insufficient_contract_never_turns_guidance_alone_into_success",
            "tests/unit/test_outcome_score_v4_evidence.py::test_insufficient_contract_retains_verified_answer_before_later_dialogue",
            "tests/unit/test_outcome_score_v4_evidence.py::test_negative_reminder_search_result_overrides_valid_limitation",
            "tests/unit/test_outcome_score_v4_evidence.py::test_not_without_required_datum_is_not_a_missing_information_claim",
            "tests/unit/test_outcome_score_v4_evidence.py::test_social_prefix_does_not_hide_a_substantive_wrong_answer",
            "tests/integration/test_toolsandbox_generated_tool_injection.py",
            "tests/unit/test_generated_tool_lifecycle.py",
            "tests/unit/test_helper_contribution.py",
            "tests/unit/test_model_config.py",
            "tests/unit/test_online_feedback_score.py",
            "tests/unit/test_openai_agent_adapter.py",
            "tests/unit/test_outcome_score_v4_state_safety.py",
            "tests/unit/test_output_normalization.py",
            "tests/unit/test_protocol_generation_policy.py",
            "tests/unit/test_rapid_api_cache.py",
            "tests/unit/test_role_factory.py",
            "tests/unit/test_run_metrics.py",
            "tests/unit/test_sage_run_adapter.py",
            "tests/unit/test_schema_check.py",
            "tests/unit/test_self_evolution_reflection.py",
            "tests/unit/test_splits.py",
            "tests/unit/test_task_strata.py",
            "tests/unit/test_toolsandbox_adapter.py",
        ),
        expected_passed=385,
        expected_summary="385 passed",
    ),
)

_SUMMARY_RE = re.compile(
    r"^(?:=+ )?(?P<core>\d+ passed(?:, \d+ deselected)?)"
    r"(?:, (?P<warnings>\d+) warnings?)?"
    r" in \d+(?:\.\d+)?s(?: \(\d+:\d{2}:\d{2}\))?(?: =+)?$"
)
_COUNTS_RE = re.compile(
    r"^(?P<passed>\d+) passed(?:, (?P<deselected>\d+) deselected)?$"
)


class GateError(RuntimeError):
    """Raised when the historical gate cannot be run safely."""


def _validate_frozen_contract() -> None:
    if tuple(shard.name for shard in SHARDS) != ("shard1", "shard2", "shard3"):
        raise GateError("historical gate must contain exactly shard1, shard2, shard3")
    if sum(shard.expected_passed for shard in SHARDS) != EXPECTED_TOTAL:
        raise GateError("historical shard pass counts no longer total 1,167")
    if tuple(shard.expected_summary for shard in SHARDS) != (
        "398 passed",
        "384 passed, 7 deselected",
        "385 passed",
    ):
        raise GateError("historical shard summaries changed")
    all_deselections = tuple(
        nodeid for shard in SHARDS for nodeid in shard.deselections
    )
    if (
        SHARDS[0].deselections
        or SHARDS[1].deselections != INTENTIONAL_DESELECTIONS
        or SHARDS[2].deselections
        or all_deselections != INTENTIONAL_DESELECTIONS
    ):
        raise GateError(
            "historical gate must contain exactly seven approved deselections"
        )


def build_command(
    shard: Shard,
    *,
    python: Path,
    basetemp: Path,
    collect_only: bool = False,
) -> list[str]:
    """Build one exact historical shard command."""

    command = [
        str(python),
        "-m",
        "pytest",
        "--import-mode=importlib",
        "-q",
        "-p",
        "no:cacheprovider",
        f"--basetemp={basetemp}",
    ]
    if collect_only:
        command.append("--collect-only")
    command.extend(f"--deselect={nodeid}" for nodeid in shard.deselections)
    command.extend(shard.selectors)
    return command


def parse_test_summary(output: str) -> dict[str, Any] | None:
    """Parse the terminal summary and validate its narrow warning allowance."""

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    match = _SUMMARY_RE.fullmatch(lines[-1]) if lines else None
    if match is None:
        return None
    core_summary = match.group("core")
    counts = _COUNTS_RE.fullmatch(core_summary)
    if counts is None:  # Defensive: _SUMMARY_RE already constrains this.
        return None
    warning_count = int(match.group("warnings") or 0)
    warning_occurrences = {
        family: output.count(message)
        for family, message in APPROVED_WARNING_MESSAGES.items()
    }
    warning_families = sorted(
        family for family, count in warning_occurrences.items() if count
    )
    warnings_approved = (warning_count == 0 and not warning_families) or (
        warning_count == len(APPROVED_WARNING_MESSAGES)
        and all(count == 1 for count in warning_occurrences.values())
    )
    summary = core_summary
    if warning_count:
        label = "warning" if warning_count == 1 else "warnings"
        summary = f"{summary}, {warning_count} {label}"
    return {
        "summary": summary,
        "core_summary": core_summary,
        "passed": int(counts.group("passed")),
        "deselected": int(counts.group("deselected") or 0),
        "warnings": warning_count,
        "warning_families": warning_families,
        "warning_occurrences": warning_occurrences,
        "warnings_approved": warnings_approved,
    }


def parse_collected_nodeids(output: str) -> list[str]:
    """Extract quiet pytest collection node IDs from a shard log."""

    return [
        line.strip()
        for line in output.splitlines()
        if line.strip().startswith("tests/") and "::" in line
    ]


def partition_digest(nodeids: Sequence[str], *, trailing_newline: bool) -> str:
    """Hash sorted unique node IDs using the frozen newline encoding."""

    payload = "\n".join(sorted(set(nodeids)))
    if trailing_newline:
        payload += "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_partition(
    shard_nodeids: Mapping[str, Sequence[str]],
    *,
    expected_counts: Mapping[str, int] | None = None,
    expected_total: int = EXPECTED_TOTAL,
    expected_sha256: str = EXPECTED_PARTITION_SHA256,
) -> dict[str, Any]:
    """Verify exact per-shard counts, uniqueness, union size, and union hash."""

    counts = expected_counts or {shard.name: shard.expected_passed for shard in SHARDS}
    failures: list[str] = []
    seen: set[str] = set()

    for shard_name in (shard.name for shard in SHARDS):
        nodeids = list(shard_nodeids.get(shard_name, ()))
        expected_count = counts.get(shard_name)
        if expected_count is None:
            failures.append(f"{shard_name}: no expected collection count")
        elif len(nodeids) != expected_count:
            failures.append(
                f"{shard_name}: collected {len(nodeids)}, expected {expected_count}"
            )
        local_duplicates = len(nodeids) - len(set(nodeids))
        if local_duplicates:
            failures.append(
                f"{shard_name}: {local_duplicates} duplicate node ID(s) within shard"
            )
        overlap = sorted(seen.intersection(nodeids))
        if overlap:
            failures.append(
                f"{shard_name}: {len(overlap)} node ID(s) duplicate an earlier shard"
            )
        seen.update(nodeids)

    if len(seen) != expected_total:
        failures.append(
            f"unique union has {len(seen)} node IDs, expected {expected_total}"
        )

    digest_without_newline = partition_digest(tuple(seen), trailing_newline=False)
    digest_with_newline = partition_digest(tuple(seen), trailing_newline=True)
    matching_encodings = [
        name
        for name, digest in (
            ("no_trailing_newline", digest_without_newline),
            ("trailing_newline", digest_with_newline),
        )
        if digest == expected_sha256
    ]
    if len(matching_encodings) != 1:
        failures.append(
            "partition digest did not reproduce the frozen SHA-256 under exactly "
            "one newline encoding"
        )

    return {
        "status": "pass" if not failures else "fail",
        "unique_nodeids": len(seen),
        "expected_unique_nodeids": expected_total,
        "sha256": (expected_sha256 if len(matching_encodings) == 1 else None),
        "expected_sha256": expected_sha256,
        "hash_encoding": matching_encodings[0]
        if len(matching_encodings) == 1
        else None,
        "observed_sha256_without_trailing_newline": digest_without_newline,
        "observed_sha256_with_trailing_newline": digest_with_newline,
        "failures": failures,
    }


def _resolve_python(value: str) -> Path:
    candidate = Path(value).expanduser()
    resolved_name = shutil.which(value) if candidate.name == value else None
    resolved = Path(resolved_name).resolve() if resolved_name else candidate.resolve()
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise GateError(f"Python executable is not executable: {resolved}")
    return resolved


def _validate_roots(candidate_root: Path, test_oracle_root: Path) -> None:
    if not (candidate_root / "src/sage_ts").is_dir():
        raise GateError(f"candidate lacks src/sage_ts: {candidate_root}")
    if not (candidate_root / "tool_sandbox").is_dir():
        raise GateError(f"candidate lacks tool_sandbox: {candidate_root}")
    required_test_files = {
        selector.split("::", 1)[0] for shard in SHARDS for selector in shard.selectors
    }
    missing = sorted(
        relative
        for relative in required_test_files
        if not (test_oracle_root / relative).is_file()
    )
    if missing:
        raise GateError(
            f"test oracle lacks {len(missing)} selected test file(s): {missing}"
        )


def _environment(candidate_root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(candidate_root / "src"), str(candidate_root))
    )
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PY_COLORS"] = "0"
    environment["NO_COLOR"] = "1"
    return environment


def _execute_shard(
    shard: Shard,
    *,
    command: Sequence[str],
    cwd: Path,
    environment: Mapping[str, str],
    log_path: Path,
) -> dict[str, Any]:
    started = time.monotonic()
    return_code: int | None = None
    launch_error: str | None = None
    with log_path.open("x", encoding="utf-8") as log:
        log.write(f"$ {shlex.join(command)}\n\n")
        log.flush()
        try:
            completed = subprocess.run(
                list(command),
                cwd=cwd,
                env=dict(environment),
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
                text=True,
            )
            return_code = completed.returncode
        except OSError as error:
            launch_error = f"{type(error).__name__}: {error}"
            log.write(f"\nLAUNCH ERROR: {launch_error}\n")
    duration = time.monotonic() - started
    output = log_path.read_text(encoding="utf-8", errors="replace")
    parsed_summary = parse_test_summary(output)
    return {
        "name": shard.name,
        "command": list(command),
        "return_code": return_code,
        "duration_seconds": round(duration, 3),
        "expected_summary": shard.expected_summary,
        "summary": None if parsed_summary is None else parsed_summary["summary"],
        "core_summary": (
            None if parsed_summary is None else parsed_summary["core_summary"]
        ),
        "passed": None if parsed_summary is None else parsed_summary["passed"],
        "deselected": (
            None if parsed_summary is None else parsed_summary["deselected"]
        ),
        "warnings": None if parsed_summary is None else parsed_summary["warnings"],
        "warning_families": (
            [] if parsed_summary is None else parsed_summary["warning_families"]
        ),
        "warning_occurrences": (
            {} if parsed_summary is None else parsed_summary["warning_occurrences"]
        ),
        "warnings_approved": (
            False if parsed_summary is None else parsed_summary["warnings_approved"]
        ),
        "log": str(log_path),
        "launch_error": launch_error,
        "collected_nodeids": parse_collected_nodeids(output),
    }


def _failed_shard_result(
    shard: Shard,
    command: Sequence[str],
    log_path: Path,
    error: Exception,
) -> dict[str, Any]:
    message = f"runner error: {type(error).__name__}: {error}"
    if not log_path.exists():
        log_path.write_text(message + "\n", encoding="utf-8")
    return {
        "name": shard.name,
        "command": list(command),
        "return_code": None,
        "duration_seconds": None,
        "expected_summary": shard.expected_summary,
        "summary": None,
        "core_summary": None,
        "passed": None,
        "deselected": None,
        "warnings": None,
        "warning_families": [],
        "warning_occurrences": {},
        "warnings_approved": False,
        "log": str(log_path),
        "launch_error": message,
        "collected_nodeids": [],
    }


def run_gate(
    candidate_root: Path,
    test_oracle_root: Path,
    *,
    python: Path,
    output_dir: Path,
    verify_partition_only: bool = False,
) -> dict[str, Any]:
    """Run all shards concurrently and return a fail-closed JSON-ready report."""

    _validate_frozen_contract()
    candidate_root = candidate_root.expanduser().resolve()
    test_oracle_root = test_oracle_root.expanduser().resolve()
    python = python.resolve()
    output_dir = output_dir.resolve()
    _validate_roots(candidate_root, test_oracle_root)
    environment = _environment(candidate_root)

    started_at = datetime.now(timezone.utc).isoformat()
    mode = "verify_partition" if verify_partition_only else "run"
    with tempfile.TemporaryDirectory(prefix="sage-historical-gate-") as temporary:
        temp_parent = Path(temporary)
        jobs: list[tuple[Shard, list[str], Path]] = []
        for shard in SHARDS:
            command = build_command(
                shard,
                python=python,
                basetemp=temp_parent / shard.name,
                collect_only=verify_partition_only,
            )
            jobs.append((shard, command, output_dir / f"{shard.name}.log"))

        results_by_name: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=len(SHARDS)) as executor:
            futures = {
                executor.submit(
                    _execute_shard,
                    shard,
                    command=command,
                    cwd=test_oracle_root,
                    environment=environment,
                    log_path=log_path,
                ): (shard, command, log_path)
                for shard, command, log_path in jobs
            }
            for future in as_completed(futures):
                shard, command, log_path = futures[future]
                try:
                    result = future.result()
                except Exception as error:
                    result = _failed_shard_result(shard, command, log_path, error)
                results_by_name[shard.name] = result

    results = [results_by_name[shard.name] for shard in SHARDS]
    failures = [
        f"{result['name']}: return code {result['return_code']}"
        for result in results
        if result["return_code"] != 0
    ]

    report: dict[str, Any] = {
        "schema_version": 1,
        "mode": mode,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "candidate_root": str(candidate_root),
        "test_oracle_root": str(test_oracle_root),
        "python": str(python),
        "pythonpath": environment["PYTHONPATH"],
        "output_dir": str(output_dir),
        "expected_total_passed": EXPECTED_TOTAL,
        "expected_partition_sha256": EXPECTED_PARTITION_SHA256,
        "approved_warning_counts": list(APPROVED_WARNING_COUNTS),
        "approved_warning_messages": APPROVED_WARNING_MESSAGES,
        "intentional_deselections": list(INTENTIONAL_DESELECTIONS),
        "shards": results,
    }

    if verify_partition_only:
        partition = verify_partition(
            {result["name"]: result.pop("collected_nodeids") for result in results}
        )
        failures.extend(partition["failures"])
        report["partition"] = partition
        report["total_collected"] = partition["unique_nodeids"]
        report["total_passed"] = None
    else:
        for result in results:
            result.pop("collected_nodeids")
            if result["core_summary"] != result["expected_summary"]:
                failures.append(
                    f"{result['name']}: core summary {result['core_summary']!r}, "
                    f"expected {result['expected_summary']!r}"
                )
            if not result["warnings_approved"]:
                failures.append(
                    f"{result['name']}: warnings do not match the approved "
                    f"0-or-{len(APPROVED_WARNING_MESSAGES)} dependency-warning contract"
                )
        passed_counts = [result["passed"] for result in results]
        total_passed = (
            sum(passed_counts)
            if all(value is not None for value in passed_counts)
            else None
        )
        report["total_passed"] = total_passed
        if total_passed != EXPECTED_TOTAL:
            failures.append(f"total passed {total_passed!r}, expected {EXPECTED_TOTAL}")

    report["failures"] = failures
    report["status"] = "pass" if not failures else "fail"
    return report


def _prepare_output_directory(requested: Path | None) -> Path:
    if requested is None:
        return Path(tempfile.mkdtemp(prefix="sage-historical-gate-output-")).resolve()
    output_dir = requested.expanduser().resolve()
    try:
        output_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        if not output_dir.is_dir() or any(output_dir.iterdir()):
            raise GateError(f"output directory is not empty: {output_dir}") from None
    return output_dir


def _write_report(report: Mapping[str, Any], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with report_path.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError:
        raise GateError(f"refusing to overwrite report: {report_path}") from None


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--test-oracle-root", type=Path, required=True)
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable used to invoke pytest (default: current Python)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="new or empty directory for logs (default: a persistent temp directory)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="JSON report path (default: <output-dir>/report.json)",
    )
    parser.add_argument(
        "--verify-partition",
        action="store_true",
        help="collect only; verify the exact unique 1,167-node partition and hash",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parse_args(argv)
    output_dir: Path | None = None
    try:
        output_dir = _prepare_output_directory(arguments.output_dir)
        python = _resolve_python(arguments.python)
        report = run_gate(
            arguments.candidate_root,
            arguments.test_oracle_root,
            python=python,
            output_dir=output_dir,
            verify_partition_only=arguments.verify_partition,
        )
        report_path = (
            arguments.report.expanduser().resolve()
            if arguments.report is not None
            else output_dir / "report.json"
        )
        report["report"] = str(report_path)
        _write_report(report, report_path)
    except GateError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        if output_dir is not None:
            print(f"Logs retained in {output_dir}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
