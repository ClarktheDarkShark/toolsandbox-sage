#!/usr/bin/env python3
"""Fail closed unless a completed publication run is entirely fresh and paired."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib
import json
import math
import os
import random
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Iterator, cast

from sage_ts.adapters.role_factory import (
    SAGE_WRAPPED_AGENT_RUNTIME as SAGE_WRAPPED_AGENT_RUNTIME,
)
from sage_ts.adapters.sage_run_adapter import (
    _side_effect_followup_failures,
    _tool_trace_events_from_execution_context,
)
from sage_ts.adapters.toolsandbox_adapter import DEFAULT_TOOL_BACKEND
from sage_ts.dashboard.server import DASHBOARD_SERVER_PROTOCOL
from sage_ts.evaluation.online_feedback_score import (
    ONLINE_FEEDBACK_EVALUATOR_VERSION as ONLINE_FEEDBACK_EVALUATOR_VERSION,
)
from sage_ts.evaluation.online_feedback_score import (
    compute_outcome_score as compute_online_feedback_score,
)
from sage_ts.evaluation.outcome_score import (
    compute_outcome_score as compute_audited_outcome_score,
)
from sage_ts.evaluation.outcome_score import (
    outcome_evaluator_manifest as outcome_evaluator_manifest,
)
from sage_ts.generation.complete_tools import native_action_tool_enabled
from sage_ts.generation.tool_spec import GeneratedTool
from sage_ts.orchestration.online_birth import (
    POST_DEPLOYMENT_REPAIR_STATE_FILENAME,
    REPAIR_STAGNATION_DUPLICATE_CANDIDATE_LABEL,
    _repair_prompt_errors,
    _validation_error_distance,
    _validation_failure_score,
    prohibited_repair_payload_paths,
)
from sage_ts.registry.manifest import RegistryEntry, has_current_validation_proof
from sage_ts.registry.validation_contracts import (
    VALIDATION_CONTRACT_BINDING_SCHEMA_VERSION,
    ValidationContractBindingStore,
)
from sage_ts.validation.sandbox_validator import validate_generated_tool
from tool_sandbox.cli.utils import resolve_scenarios
from tool_sandbox.common.evaluation import Milestone, Minefield
from tool_sandbox.common.execution_context import ExecutionContext
from tool_sandbox.common.message_conversion import serialize_to_conversation
from tool_sandbox.common.scenario import Scenario

PINNED_RAPID_FIXTURE_SHA256 = (
    "eae0a6ab7d2ee5dd272612a0b5ce44d85af34cd1297ff662007260941192322f"
)
PINNED_BENCHMARK_SHA256 = (
    "21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec"
)
PINNED_SCENARIO_ORDER_SHA256 = (
    "fec899dde5b3ce1879157c16eff120e24c1791a2ab1df53712677bcacb250176"
)
PINNED_PUBLICATION_ENVIRONMENT_LOCK_SHA256 = (
    "5c3ea1802331bf45809fd3e3e31fd8352473449e709cd7a443d03d1975477d1f"
)
PUBLICATION_ENVIRONMENT_LOCK = "requirements-publication-lock.txt"
PUBLICATION_FIXED_TOOLSANDBOX_TIMESTAMP = 1784832588
PUBLICATION_MODEL = "gpt-4o-mini"
PUBLICATION_TASK_COUNT = 1032
PUBLICATION_TIMEZONE = "America/New_York"
PUBLICATION_OUTCOME_EVALUATOR_VERSION = "sage_outcome_contracts_v9"
PUBLICATION_OUTCOME_EVALUATOR_CONTRACT_SHA256 = (
    "d6a7598e708b24e40823278c228c895c387ef1a4d116e3b92173885967ad1955"
)
PUBLICATION_OUTCOME_EVALUATOR_SOURCE_SHA256 = (
    "8ed1595b3eb050004ba2cc161836fb78906e58d3c0127b2c421df03400f14c63"
)
PUBLICATION_GATE_PURPOSE_RELEASE_SAMPLE = "release-sample"
PUBLICATION_GATE_PURPOSE_CAMPAIGN_INCLUSION = "campaign-inclusion"
PUBLICATION_GATE_PURPOSES = (
    PUBLICATION_GATE_PURPOSE_RELEASE_SAMPLE,
    PUBLICATION_GATE_PURPOSE_CAMPAIGN_INCLUSION,
)
MATCHED_CONTROL_CONDITION = "matched_policy_wrapper_without_generated_tools"
LIFECYCLE_CONTRACT_FAILURE_THRESHOLD = 1
LIFECYCLE_EXECUTION_FAILURE_THRESHOLD = 3
LIFECYCLE_METADATA_VISIBLE_THRESHOLD = 8
LIFECYCLE_ROUTE_HARMFUL_CALL_THRESHOLD = 2
LIFECYCLE_ROUTE_HARM_DELTA = -0.25
LIFECYCLE_ROUTE_HELP_DELTA = 0.10
LIFECYCLE_GLOBAL_RETIREMENT_REASON = "repeated_attributable_harm_without_helpful_route"
LIFECYCLE_CROSS_FAMILY_EXECUTION_FAILURE = "cross_family_execution_failure"
LIFECYCLE_CANARY_ATTRIBUTABLE_OBSERVATION_MINIMUM = 3
LIFECYCLE_CANARY_EXACT_OUTCOME_MINIMUM = 2
LIFECYCLE_CANARY_FRESH_CONTROL_SUCCESS_FLIP_MINIMUM = 1
PUBLICATION_EXECUTION_ENV = {
    "TZ": PUBLICATION_TIMEZONE,
    "SAGE_OPENAI_MAX_RETRIES": "5",
    "SAGE_OPENAI_TRANSIENT_RETRY_DELAYS_SECONDS": "1,3",
    "SAGE_GENERATION_TRANSIENT_RETRY_DELAYS_SECONDS": "1,3",
    "SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS": "4",
    "SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS": "120",
    "SAGE_GENERATION_OPENAI_REQUEST_TIMEOUT_SECONDS": "600",
}
LLM_USAGE_INTEGER_FIELDS = (
    "llm_call_count",
    "llm_live_call_count",
    "llm_cached_call_count",
    "llm_prompt_tokens",
    "llm_provider_cached_prompt_tokens",
    "llm_provider_cached_prompt_call_count",
    "llm_provider_cached_prompt_tokens_available_count",
    "llm_completion_tokens",
    "llm_total_tokens",
    "llm_usage_available_count",
)
LLM_USAGE_SOURCE_INTEGER_FIELDS = tuple(
    field for field in LLM_USAGE_INTEGER_FIELDS if field != "llm_usage_available_count"
)
_PUBLICATION_LOCK_LINE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)$")
REPO_ROOT = Path(__file__).resolve().parents[1]


def _external_distribution_lock_identity(lock_path: Path) -> tuple[int, str]:
    """Independently derive the lock's canonical external package identity."""

    if not lock_path.is_file():
        raise ValueError(f"Publication environment lock is missing: {lock_path}")
    locked: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        lock_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _PUBLICATION_LOCK_LINE.fullmatch(line)
        if match is None:
            raise ValueError(
                "Publication environment lock must contain exact name==version "
                f"entries; line {line_number} is invalid: {line!r}."
            )
        display_name, version = match.groups()
        canonical_name = re.sub(r"[-_.]+", "-", display_name).lower()
        if canonical_name in locked:
            raise ValueError(
                "Publication environment lock contains duplicate distribution "
                f"{canonical_name!r}."
            )
        locked[canonical_name] = version
    if not locked:
        raise ValueError("Publication environment lock is empty.")
    canonical_entries = sorted(
        f"{name}=={version}\n" for name, version in locked.items()
    )
    canonical_bytes = "".join(canonical_entries).encode("utf-8")
    return len(locked), hashlib.sha256(canonical_bytes).hexdigest()


def _git_output(repo_root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"Cannot inspect current publication source: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(
            "Cannot inspect current publication source: "
            f"git {' '.join(arguments)} failed ({detail or completed.returncode})."
        )
    return completed.stdout.strip()


def _clean_source_identity(repo_root: Path) -> dict[str, Any]:
    """Return current Git identity only for the exact, clean repository root."""

    repo_root = repo_root.resolve()
    git_root = Path(_git_output(repo_root, "rev-parse", "--show-toplevel")).resolve()
    if git_root != repo_root:
        raise ValueError(
            f"Current publication source root is {git_root}; expected {repo_root}."
        )
    status = _git_output(
        repo_root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    if status:
        first_entries = ", ".join(status.splitlines()[:5])
        raise ValueError(
            "Current publication source worktree is not clean"
            + (f": {first_entries}" if first_entries else ".")
        )
    commit = _git_output(repo_root, "rev-parse", "--verify", "HEAD")
    tree = _git_output(repo_root, "rev-parse", "--verify", "HEAD^{tree}")
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit) or not re.fullmatch(
        r"[0-9a-f]{40,64}", tree
    ):
        raise ValueError("Current publication Git commit or tree is malformed.")
    return {"git_commit": commit, "git_tree": tree, "git_clean": True}


def _active_publication_environment(
    lock_path: Path,
    *,
    repo_root: Path,
) -> dict[str, Any]:
    try:
        environment_verifier = importlib.import_module(
            "scripts.verify_publication_environment"
        )
    except ModuleNotFoundError:
        environment_verifier = importlib.import_module("verify_publication_environment")

    try:
        report = environment_verifier.verify_environment(
            lock_path,
            repo_root=repo_root,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f"Active publication environment is invalid: {exc}") from exc
    if not isinstance(report, dict) or report.get("status") != "pass":
        raise ValueError("Active publication environment verifier did not pass.")
    return report


def _verify_publication_provenance(protocol: dict[str, Any]) -> dict[str, Any]:
    provenance = protocol.get("publication_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("Protocol does not record publication provenance.")
    if provenance.get("schema_version") != 2:
        raise ValueError("Publication provenance schema version is not 2.")
    if protocol.get("toolsandbox_clock_policy") != "frozen":
        raise ValueError("Publication protocol did not freeze the ToolSandbox clock.")
    required_timestamp = str(PUBLICATION_FIXED_TOOLSANDBOX_TIMESTAMP)
    if protocol.get("toolsandbox_fixed_now_timestamp") != required_timestamp:
        raise ValueError(
            "Protocol ToolSandbox timestamp is not the exact publication pin."
        )
    if (
        provenance.get("fixed_toolsandbox_timestamp")
        != PUBLICATION_FIXED_TOOLSANDBOX_TIMESTAMP
    ):
        raise ValueError(
            "Publication provenance ToolSandbox timestamp is not the exact pin."
        )

    recorded_commit = provenance.get("git_commit")
    recorded_tree = provenance.get("git_tree")
    if not isinstance(recorded_commit, str) or not re.fullmatch(
        r"[0-9a-f]{40,64}", recorded_commit
    ):
        raise ValueError("Publication provenance Git commit is missing or malformed.")
    if not isinstance(recorded_tree, str) or not re.fullmatch(
        r"[0-9a-f]{40,64}", recorded_tree
    ):
        raise ValueError("Publication provenance Git tree is missing or malformed.")
    if provenance.get("git_clean") is not True:
        raise ValueError("Publication provenance does not attest a clean Git worktree.")
    current_source = _clean_source_identity(REPO_ROOT)
    for field in ("git_commit", "git_tree", "git_clean"):
        if provenance.get(field) != current_source.get(field):
            raise ValueError(
                f"Current clean source identity does not match recorded {field}."
            )

    if provenance.get("environment_lock_path") != PUBLICATION_ENVIRONMENT_LOCK:
        raise ValueError(
            "Publication provenance does not name the canonical environment lock."
        )
    lock_path = (REPO_ROOT / PUBLICATION_ENVIRONMENT_LOCK).resolve()
    observed_lock_sha256 = (
        hashlib.sha256(lock_path.read_bytes()).hexdigest()
        if lock_path.is_file()
        else "missing"
    )
    if observed_lock_sha256 != PINNED_PUBLICATION_ENVIRONMENT_LOCK_SHA256:
        raise ValueError(
            "Current publication environment lock does not match its exact pin."
        )
    if provenance.get("environment_lock_sha256") != observed_lock_sha256:
        raise ValueError(
            "Recorded publication environment lock hash does not match current bytes."
        )
    distribution_count, distribution_sha256 = _external_distribution_lock_identity(
        lock_path
    )
    if provenance.get("external_distribution_count") != distribution_count:
        raise ValueError(
            "Recorded external distribution count does not match the exact lock."
        )
    if provenance.get("external_distribution_sha256") != distribution_sha256:
        raise ValueError(
            "Recorded external distribution identity does not match the exact lock."
        )

    exact_environment: dict[str, Any] = {
        "python_version": "3.12.7",
        "python_implementation": "CPython",
        "isolated_environment": True,
        "platform_system": "Darwin",
        "platform_machine": "arm64",
    }
    for field, expected in exact_environment.items():
        if provenance.get(field) != expected:
            raise ValueError(
                f"Publication provenance field {field!r} is "
                f"{provenance.get(field)!r}; expected {expected!r}."
            )
    for field in ("python_executable", "python_prefix", "python_base_prefix"):
        value = provenance.get(field)
        if not isinstance(value, str) or not value or not Path(value).is_absolute():
            raise ValueError(
                f"Publication provenance field {field!r} is not an absolute path."
            )
    if provenance.get("execution_environment") != PUBLICATION_EXECUTION_ENV:
        raise ValueError(
            "Publication provenance does not pin the complete execution policy."
        )

    active_environment = _active_publication_environment(
        lock_path,
        repo_root=REPO_ROOT,
    )
    required_active: dict[str, Any] = {
        **exact_environment,
        "environment_lock_path": str(lock_path),
        "environment_lock_sha256": observed_lock_sha256,
        "external_distribution_count": distribution_count,
        "external_distribution_sha256": distribution_sha256,
    }
    for field, expected in required_active.items():
        if active_environment.get(field) != expected:
            raise ValueError(
                f"Active publication environment field {field!r} is "
                f"{active_environment.get(field)!r}; expected {expected!r}."
            )
    for field in (
        "python_executable",
        "python_version",
        "python_implementation",
        "python_prefix",
        "python_base_prefix",
        "isolated_environment",
        "platform_system",
        "platform_machine",
    ):
        if active_environment.get(field) != provenance.get(field):
            raise ValueError(
                f"Active publication environment does not match recorded {field}."
            )
    return dict(provenance)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read required JSON artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def _read_jsonl_objects(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Lifecycle JSONL line {line_number} is invalid in {path}: {exc}"
            ) from exc
        if not isinstance(row, dict):
            raise ValueError(
                f"Lifecycle JSONL line {line_number} is not an object in {path}."
            )
        rows.append(row)
    return rows


def _declared_path_is_symlink(run_root: Path, value: Any) -> bool:
    """Reject a symlink before path resolution erases that fact."""

    if not isinstance(value, str) or not value.strip():
        return False
    path = Path(value)
    candidates = (
        (path,)
        if path.is_absolute()
        else (REPO_ROOT / path, Path.cwd() / path, run_root / path)
    )
    return any(candidate.is_symlink() for candidate in candidates)


def _verified_protocol_event_rows(
    *,
    run_root: Path,
    protocol: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load the manifest-pinned, append-complete protocol event journal."""

    journal = protocol.get("protocol_event_journal")
    if not isinstance(journal, dict):
        raise ValueError("Publication run has no sealed protocol event journal.")
    schema_version = journal.get("schema_version")
    if (
        isinstance(schema_version, bool)
        or schema_version != 1
        or journal.get("append_closed_before_protocol_manifest") is not True
    ):
        raise ValueError("Publication protocol event journal seal is malformed.")
    declared_path = journal.get("path")
    if _declared_path_is_symlink(run_root, declared_path):
        raise ValueError("Publication protocol event journal must not be a symlink.")
    artifact_root = _resolve_declared_path(
        run_root,
        journal.get("artifact_root"),
        "protocol_event_journal.artifact_root",
    )
    journal_path = _resolve_declared_path(
        run_root,
        declared_path,
        "protocol_event_journal.path",
        required_parent=artifact_root / "events",
    )
    if journal_path != (artifact_root / "events" / "latest.jsonl").resolve():
        raise ValueError("Publication protocol event journal is not latest.jsonl.")
    if not journal_path.is_file() or journal_path.is_symlink():
        raise ValueError("Publication protocol event journal is missing or unsafe.")
    expected_sha256 = journal.get("sha256")
    observed_sha256 = hashlib.sha256(journal_path.read_bytes()).hexdigest()
    expected_count = journal.get("event_count")
    if (
        not isinstance(expected_sha256, str)
        or _SHA256_HEX_PATTERN.fullmatch(expected_sha256) is None
        or expected_sha256 != observed_sha256
        or isinstance(expected_count, bool)
        or not isinstance(expected_count, int)
        or expected_count < 1
    ):
        raise ValueError("Publication protocol event journal identity is invalid.")
    rows = _read_jsonl_objects(journal_path)
    if len(rows) != expected_count:
        raise ValueError("Publication protocol event journal count is invalid.")
    return rows, {
        "mode": "sealed_protocol_event_journal",
        "path": str(journal_path),
        "sha256": observed_sha256,
        "event_count": len(rows),
        "sealed": True,
    }


def _read_json_list(path: Path, *, label: str) -> list[Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read required {label} {path}: {exc}") from exc
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list for {label}: {path}")
    return payload


@contextlib.contextmanager
def _publication_evaluation_environment() -> Iterator[None]:
    """Recreate the clock, timezone, and random seed used to build scenarios."""

    prior_timestamp = os.environ.get("TOOL_SANDBOX_FIXED_NOW_TIMESTAMP")
    prior_timezone = os.environ.get("TZ")
    prior_random_state = random.getstate()
    os.environ["TOOL_SANDBOX_FIXED_NOW_TIMESTAMP"] = str(
        PUBLICATION_FIXED_TOOLSANDBOX_TIMESTAMP
    )
    os.environ["TZ"] = PUBLICATION_TIMEZONE
    if hasattr(time, "tzset"):
        time.tzset()
    random.seed(42)
    try:
        yield
    finally:
        random.setstate(prior_random_state)
        if prior_timestamp is None:
            os.environ.pop("TOOL_SANDBOX_FIXED_NOW_TIMESTAMP", None)
        else:
            os.environ["TOOL_SANDBOX_FIXED_NOW_TIMESTAMP"] = prior_timestamp
        if prior_timezone is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = prior_timezone
        if hasattr(time, "tzset"):
            time.tzset()


def _load_publication_scenarios(
    scenario_names: list[str],
) -> dict[str, Scenario]:
    """Load only the declared scenarios under the publication runtime pins."""

    with _publication_evaluation_environment():
        return cast(
            dict[str, Scenario],
            resolve_scenarios(
                desired_scenario_names=scenario_names,
                preferred_tool_backend=DEFAULT_TOOL_BACKEND,
            ),
        )


def _independently_recompute_trajectory(
    scenario: Scenario,
    execution_context: ExecutionContext,
    *,
    scenario_name: str,
) -> dict[str, Any]:
    """Re-evaluate one saved trajectory without using any summary artifact."""

    evaluation_result = scenario.evaluation.evaluate(
        execution_context=execution_context,
        max_turn_count=scenario.max_messages,
    )
    canonical_milestone_scores = {
        int(index): float(score)
        for index, (_, score) in evaluation_result.milestone_mapping.items()
    }
    audited_outcome = compute_audited_outcome_score(
        scenario,
        execution_context,
        scenario_name=scenario_name,
    )
    paper_outcome = compute_online_feedback_score(
        scenario,
        execution_context,
        canonical_milestone_scores=canonical_milestone_scores,
        minefield_similarity=evaluation_result.minefield_similarity,
    )
    conversation = serialize_to_conversation(
        execution_context=execution_context,
        evaluation_result=evaluation_result,
        milestones=cast(
            list[Milestone], scenario.evaluation.milestone_matcher.milestones
        ),
        minefields=cast(
            list[Minefield], scenario.evaluation.minefield_matcher.milestones
        ),
    )
    return {
        "audited_outcome": audited_outcome,
        "paper_outcome": paper_outcome,
        "conversation": conversation,
    }


def _json_values_equal(left: Any, right: Any) -> bool:
    """Compare JSON-compatible evaluator data without bool/number coercion."""

    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return (
            math.isfinite(float(left))
            and math.isfinite(float(right))
            and math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-12)
        )
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(
            _json_values_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        # The explicit length check is the strictness guarantee.  Avoid
        # ``zip(strict=True)`` so legacy development fixtures can still be
        # verified under their Python 3.9 test environment. Evaluator
        # contracts may retain tuples in memory, while their persisted JSON
        # representation necessarily contains arrays; those are the same
        # serialized value and must compare element-for-element.
        return len(left) == len(right) and all(
            _json_values_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    return type(left) is type(right) and left == right


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _conversation_execution_projection(conversation: list[Any]) -> list[Any]:
    """Remove only evaluator annotations from a serialized conversation.

    ``tool_details`` and ``assistant_details`` are regenerated scorer reports;
    their internal constraint ordering is not semantic. Every actor-visible and
    tool-execution field remains exact and is independently regenerated from the
    execution context.
    """

    projected: list[Any] = []
    for message in conversation:
        if not isinstance(message, dict):
            projected.append(message)
            continue
        projected.append(
            {
                key: value
                for key, value in message.items()
                if not key.endswith("_details")
            }
        )
    return projected


def _tool_response_is_failure(content: Any) -> bool:
    text = str(content or "")
    return bool(
        "Error:" in text
        or text.startswith(("TypeError", "ValueError", "ValidationError"))
        or "Traceback" in text
    )


def _trajectory_generated_tool_evidence(
    serialized_context: dict[str, Any],
    conversation: list[Any],
    *,
    generated_tool_names: set[str],
    scenario_name: str,
) -> dict[str, tuple[str, ...]]:
    """Derive generated-tool visibility and execution only from a trajectory."""

    allow_list = serialized_context.get("tool_allow_list")
    deny_list = serialized_context.get("tool_deny_list")
    if allow_list is not None and (
        not isinstance(allow_list, list)
        or any(not isinstance(item, str) or not item for item in allow_list)
        or len(allow_list) != len(set(allow_list))
    ):
        raise ValueError(
            f"Trajectory {scenario_name!r} has a malformed tool allow list."
        )
    if deny_list is not None and (
        not isinstance(deny_list, list)
        or any(not isinstance(item, str) or not item for item in deny_list)
        or len(deny_list) != len(set(deny_list))
    ):
        raise ValueError(
            f"Trajectory {scenario_name!r} has a malformed tool deny list."
        )
    denied = set(deny_list or [])
    if allow_list is None and generated_tool_names:
        raise ValueError(
            f"Trajectory {scenario_name!r} cannot prove which generated tools "
            "were visible because its allow list is null."
        )
    visible = [
        tool_name
        for tool_name in (allow_list or [])
        if tool_name in generated_tool_names and tool_name not in denied
    ]

    databases = serialized_context.get("_dbs")
    sandbox_rows = databases.get("SANDBOX") if isinstance(databases, dict) else None
    if not isinstance(sandbox_rows, list) or any(
        not isinstance(row, dict) for row in sandbox_rows
    ):
        raise ValueError(
            f"Trajectory {scenario_name!r} has no valid SANDBOX execution rows."
        )

    attempted: list[str] = []
    responses: list[str] = []
    failed: list[str] = []
    for row in sandbox_rows:
        tool_name = row.get("openai_function_name")
        if not isinstance(tool_name, str) or tool_name not in generated_tool_names:
            continue
        if tool_name not in visible:
            raise ValueError(
                f"Trajectory {scenario_name!r} executed generated tool "
                f"{tool_name!r} without recording it as visible."
            )
        sender = row.get("sender")
        recipient = row.get("recipient")
        if sender == "AGENT" and recipient == "EXECUTION_ENVIRONMENT":
            _append_unique(attempted, tool_name)
        elif sender == "EXECUTION_ENVIRONMENT" and recipient == "AGENT":
            _append_unique(responses, tool_name)
            if row.get("tool_call_exception") not in (
                None,
                "",
            ) or _tool_response_is_failure(row.get("content")):
                _append_unique(failed, tool_name)

    conversation_attempted: list[str] = []
    conversation_responses: list[str] = []
    conversation_failed: list[str] = []
    for message in conversation:
        if not isinstance(message, dict):
            raise ValueError(
                f"Trajectory {scenario_name!r} conversation contains a non-object."
            )
        tool_calls = message.get("tool_calls")
        if tool_calls is not None:
            if not isinstance(tool_calls, list):
                raise ValueError(
                    f"Trajectory {scenario_name!r} has malformed conversation "
                    "tool calls."
                )
            for tool_call in tool_calls:
                function = (
                    tool_call.get("function") if isinstance(tool_call, dict) else None
                )
                tool_name = function.get("name") if isinstance(function, dict) else None
                if isinstance(tool_name, str) and tool_name in generated_tool_names:
                    _append_unique(conversation_attempted, tool_name)
        if message.get("role") != "tool":
            continue
        tool_name = message.get("name")
        if not isinstance(tool_name, str) or tool_name not in generated_tool_names:
            continue
        _append_unique(conversation_attempted, tool_name)
        _append_unique(conversation_responses, tool_name)
        if _tool_response_is_failure(message.get("content")):
            _append_unique(conversation_failed, tool_name)

    if tuple(attempted) != tuple(conversation_attempted):
        raise ValueError(
            f"Trajectory {scenario_name!r} execution rows and conversation disagree "
            "about generated-tool attempts."
        )
    if tuple(responses) != tuple(conversation_responses):
        raise ValueError(
            f"Trajectory {scenario_name!r} execution rows and conversation disagree "
            "about generated-tool responses."
        )
    if tuple(failed) != tuple(conversation_failed):
        raise ValueError(
            f"Trajectory {scenario_name!r} execution rows and conversation disagree "
            "about generated-tool failures."
        )
    called = [tool_name for tool_name in responses if tool_name not in set(failed)]
    return {
        "generated_tools_visible": tuple(visible),
        "generated_tools_attempted": tuple(attempted),
        "generated_tools_failed": tuple(failed),
        "generated_tools_called": tuple(called),
    }


def _verify_trajectory_artifacts(
    run_dir: Path,
    *,
    rows: dict[str, dict[str, Any]],
    order: list[str],
    arm: str,
    generated_tool_names: set[str],
) -> dict[str, dict[str, tuple[str, ...]]]:
    """Require and independently audit one complete trajectory per result row."""

    trajectory_root = run_dir / "trajectories"
    if (
        not trajectory_root.is_dir()
        or trajectory_root.is_symlink()
        or trajectory_root.resolve().parent != run_dir.resolve()
    ):
        raise ValueError(f"{arm} run has no valid trajectory directory.")
    scenarios = _load_publication_scenarios(order)
    if set(scenarios) != set(order):
        raise ValueError(f"{arm} trajectory scenarios are incomplete.")

    evidence: dict[str, dict[str, tuple[str, ...]]] = {}
    with _publication_evaluation_environment():
        for scenario_name in order:
            if Path(scenario_name).name != scenario_name or scenario_name in {
                ".",
                "..",
            }:
                raise ValueError(f"{arm} result has an unsafe scenario name.")
            scenario_dir = trajectory_root / scenario_name
            execution_path = scenario_dir / "execution_context.json"
            conversation_path = scenario_dir / "conversation.json"
            if (
                not scenario_dir.is_dir()
                or scenario_dir.is_symlink()
                or scenario_dir.resolve().parent != trajectory_root.resolve()
                or not execution_path.is_file()
                or execution_path.is_symlink()
                or not conversation_path.is_file()
                or conversation_path.is_symlink()
            ):
                raise ValueError(
                    f"{arm} task {scenario_name!r} is missing complete trajectory "
                    "artifacts."
                )
            serialized_context = _read_json(execution_path)
            conversation = _read_json_list(
                conversation_path,
                label=f"{arm} trajectory conversation",
            )
            try:
                execution_context = ExecutionContext.from_dict(serialized_context)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"{arm} task {scenario_name!r} has an invalid execution context: "
                    f"{exc}"
                ) from exc
            try:
                recomputed = _independently_recompute_trajectory(
                    scenarios[scenario_name],
                    execution_context,
                    scenario_name=scenario_name,
                )
            except Exception as exc:
                raise ValueError(
                    f"{arm} task {scenario_name!r} cannot be independently "
                    f"re-evaluated: {exc}"
                ) from exc
            audited = recomputed.get("audited_outcome")
            paper = recomputed.get("paper_outcome")
            canonical_conversation = recomputed.get("conversation")
            if not isinstance(audited, dict) or not isinstance(paper, dict):
                raise ValueError(
                    f"{arm} task {scenario_name!r} evaluator recomputation is invalid."
                )
            row = rows[scenario_name]
            for field, expected in audited.items():
                if field not in row or not _json_values_equal(row[field], expected):
                    raise ValueError(
                        f"{arm} task {scenario_name!r} summary {field!r} disagrees "
                        "with its independently recomputed audited v9 outcome."
                    )
            if (
                row.get("online_feedback_evaluator_version")
                != ONLINE_FEEDBACK_EVALUATOR_VERSION
                or "online_feedback_outcome_similarity" not in row
                or not _json_values_equal(
                    row["online_feedback_outcome_similarity"],
                    paper.get("outcome_similarity"),
                )
            ):
                raise ValueError(
                    f"{arm} task {scenario_name!r} summary disagrees with its "
                    "independently recomputed paper-era v1 outcome."
                )
            if not isinstance(canonical_conversation, list) or not _json_values_equal(
                _conversation_execution_projection(conversation),
                _conversation_execution_projection(canonical_conversation),
            ):
                raise ValueError(
                    f"{arm} task {scenario_name!r} stored conversation is not the "
                    "canonical serialization of its execution context."
                )
            evidence[scenario_name] = _trajectory_generated_tool_evidence(
                serialized_context,
                conversation,
                generated_tool_names=generated_tool_names,
                scenario_name=scenario_name,
            )
    return evidence


_LIFECYCLE_SELECTION_FIELDS = (
    "generated_tools_visible",
    "generated_tools_called",
    "generated_tools_attempted",
    "generated_tools_failed",
    "generated_tool_contract_failures",
)
_SHA256_HEX_PATTERN = re.compile(r"[0-9a-f]{64}")
_REPAIR_CANDIDATE_ARTIFACT_FILENAME = "post_deployment_repair_candidates.jsonl"
_REPAIR_CANDIDATE_ARTIFACT_SCHEMA_VERSION = 3
_REPAIR_CANDIDATE_ARTIFACT_LEGACY_SCHEMA_VERSION = 1
_REPAIR_CANDIDATE_ARTIFACT_BEST_STATE_SCHEMA_VERSION = 2
_REPAIR_CANDIDATE_ARTIFACT_SCHEMA_VERSIONS = frozenset(
    {
        _REPAIR_CANDIDATE_ARTIFACT_LEGACY_SCHEMA_VERSION,
        _REPAIR_CANDIDATE_ARTIFACT_BEST_STATE_SCHEMA_VERSION,
        _REPAIR_CANDIDATE_ARTIFACT_SCHEMA_VERSION,
    }
)
_REPAIR_CANDIDATE_ORIGINS = frozenset({"ordinary", "clean_room"})
_REPAIR_CANDIDATE_RECORD_KEYS_V1_V2 = {
    "schema_version",
    "event",
    "request_id",
    "tool_name",
    "source_tool_version",
    "repair_kind",
    "generated_after_completed_count",
    "attempt",
    "candidate_index",
    "source_validation_contract_hash",
    "source_tool_code_sha256",
    "source_tool_spec_sha256",
    "generator_candidate",
    "evaluated_candidate",
    "validation",
    "selected_for_attempt",
    "disposition",
    "failure_stage",
    "failure_type",
    "future_tasks_only",
    "triggering_task_replayed",
    "evidence_policy",
    "record_sha256",
}
_REPAIR_CANDIDATE_RECORD_KEYS_BY_VERSION = {
    _REPAIR_CANDIDATE_ARTIFACT_LEGACY_SCHEMA_VERSION: (
        _REPAIR_CANDIDATE_RECORD_KEYS_V1_V2
    ),
    _REPAIR_CANDIDATE_ARTIFACT_BEST_STATE_SCHEMA_VERSION: (
        _REPAIR_CANDIDATE_RECORD_KEYS_V1_V2
    ),
    _REPAIR_CANDIDATE_ARTIFACT_SCHEMA_VERSION: (
        _REPAIR_CANDIDATE_RECORD_KEYS_V1_V2 | {"candidate_origin"}
    ),
}
_REPAIR_CANDIDATE_VALIDATION_KEYS = {
    "available",
    "accepted",
    "failure_score",
    "source_example_count",
    "held_out_check_count",
    "negative_applicability_count",
    "runtime_smoke_passed",
    "sanitized_frontier",
    "sanitized_frontier_count",
    "raw_validation_errors_persisted",
}
_REPAIR_CANDIDATE_REFERENCE_KEYS_V1_V2 = {
    "candidate_index",
    "candidate_code_hash",
    "accepted",
    "validation_score",
    "error_frontier_count",
    "errors",
    "candidate_artifact_path",
    "candidate_artifact_schema_version",
    "candidate_artifact_record_sha256",
}
_REPAIR_CANDIDATE_REFERENCE_KEYS_BY_VERSION = {
    _REPAIR_CANDIDATE_ARTIFACT_LEGACY_SCHEMA_VERSION: (
        _REPAIR_CANDIDATE_REFERENCE_KEYS_V1_V2
    ),
    _REPAIR_CANDIDATE_ARTIFACT_BEST_STATE_SCHEMA_VERSION: (
        _REPAIR_CANDIDATE_REFERENCE_KEYS_V1_V2
    ),
    _REPAIR_CANDIDATE_ARTIFACT_SCHEMA_VERSION: (
        _REPAIR_CANDIDATE_REFERENCE_KEYS_V1_V2
        | {
            "candidate_origin",
            "focused_public_case_failed",
            "public_failed_case_count",
            "public_validation_score",
            "regressed_public_case_count",
        }
    ),
}
_REPAIR_PUBLIC_CASE_LABEL_PATTERN = re.compile(r"^((?:source|negative)_\d+)_")


class _RepairCandidateArtifactVerificationError(ValueError):
    """Carry a stable strict-verifier reason for candidate-evidence failures."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def _repair_candidate_require(condition: Any, reason: str, message: str) -> None:
    if not condition:
        raise _RepairCandidateArtifactVerificationError(reason, message)


def _canonical_json_sha256(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise _RepairCandidateArtifactVerificationError(
            "repair_candidate_artifact_schema_invalid",
            f"Repair candidate evidence is not canonical JSON: {exc}",
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def _strict_json_object(line: str, *, line_number: int, path: Path) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            _repair_candidate_require(
                key not in value,
                "repair_candidate_artifact_schema_invalid",
                f"Duplicate JSON key {key!r} at repair-candidate line {line_number}.",
            )
            value[key] = item
        return value

    def reject_nonfinite(value: str) -> Any:
        raise _RepairCandidateArtifactVerificationError(
            "repair_candidate_artifact_schema_invalid",
            f"Non-finite value {value!r} at repair-candidate line {line_number}.",
        )

    try:
        row = json.loads(
            line,
            object_pairs_hook=unique_object,
            parse_constant=reject_nonfinite,
        )
    except json.JSONDecodeError as exc:
        raise _RepairCandidateArtifactVerificationError(
            "repair_candidate_artifact_schema_invalid",
            f"Invalid JSON at repair-candidate line {line_number}: {path}: {exc}.",
        ) from exc
    _repair_candidate_require(
        isinstance(row, dict),
        "repair_candidate_artifact_schema_invalid",
        f"Repair-candidate line {line_number} is not an object: {path}.",
    )
    return cast(dict[str, Any], row)


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _verify_repair_candidate_tool_evidence(
    evidence: Any,
    *,
    label: str,
) -> dict[str, Any]:
    _repair_candidate_require(
        isinstance(evidence, dict)
        and set(evidence)
        == {"tool", "code_sha256", "spec_sha256", "tool_payload_sha256"},
        "repair_candidate_artifact_schema_invalid",
        f"Repair candidate {label} does not have the exact evidence schema.",
    )
    tool = evidence.get("tool")
    _repair_candidate_require(
        isinstance(tool, dict) and set(tool) == {"spec", "code"},
        "repair_candidate_artifact_schema_invalid",
        f"Repair candidate {label} does not contain an exact tool payload.",
    )
    spec = tool.get("spec")
    code = tool.get("code")
    _repair_candidate_require(
        isinstance(spec, dict) and isinstance(code, str),
        "repair_candidate_artifact_schema_invalid",
        f"Repair candidate {label} has malformed tool spec or code.",
    )
    try:
        canonical_tool = GeneratedTool.from_json(tool).to_json()
    except (KeyError, TypeError, ValueError) as exc:
        raise _RepairCandidateArtifactVerificationError(
            "repair_candidate_artifact_schema_invalid",
            f"Repair candidate {label} cannot be decoded: {exc}.",
        ) from exc
    _repair_candidate_require(
        canonical_tool == tool,
        "repair_candidate_artifact_schema_invalid",
        f"Repair candidate {label} is not the canonical generated-tool schema.",
    )
    expected_hashes = {
        "code_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest(),
        "spec_sha256": _canonical_json_sha256(spec),
        "tool_payload_sha256": _canonical_json_sha256(tool),
    }
    for field, expected in expected_hashes.items():
        _repair_candidate_require(
            evidence.get(field) == expected,
            "repair_candidate_artifact_tampered",
            f"Repair candidate {label} {field} does not match its payload.",
        )
    return cast(dict[str, Any], evidence)


def _repair_candidate_reference_path_matches(
    candidate_dir: Path,
    value: Any,
) -> bool:
    if not isinstance(value, str) or not value:
        return False
    expected = candidate_dir / _REPAIR_CANDIDATE_ARTIFACT_FILENAME
    allowed = {str(expected)}
    for root in (REPO_ROOT, Path.cwd()):
        try:
            allowed.add(str(expected.resolve().relative_to(root.resolve())))
        except ValueError:
            pass
    if value not in allowed:
        return False
    declared = Path(value)
    candidates = (
        (declared,)
        if declared.is_absolute()
        else (REPO_ROOT / declared, Path.cwd() / declared)
    )
    if any(path.is_symlink() for path in candidates):
        return False
    return any(path.resolve() == expected.resolve() for path in candidates)


def _verified_repair_source_bindings(
    candidate_dir: Path,
    rows: list[dict[str, Any]],
) -> None:
    """Bind each source identity to its exact after-N sealed checkpoint."""

    checked: set[tuple[int, str, int, str, str, str]] = set()
    for row in rows:
        identity = (
            row["generated_after_completed_count"],
            row["tool_name"],
            row["source_tool_version"],
            row["source_validation_contract_hash"],
            row["source_tool_code_sha256"],
            row["source_tool_spec_sha256"],
        )
        if identity in checked:
            continue
        checked.add(identity)
        completed, tool_name, version, contract_hash, code_sha256, spec_sha256 = (
            identity
        )
        checkpoint_matches = list(
            (candidate_dir / "registry_checkpoints").glob(f"after_{completed:04d}_*")
        )
        _repair_candidate_require(
            len(checkpoint_matches) == 1
            and checkpoint_matches[0].is_dir()
            and not checkpoint_matches[0].is_symlink(),
            "repair_candidate_artifact_source_lineage_mismatch",
            f"Repair candidate has no unique sealed after-{completed} checkpoint.",
        )
        checkpoint_dir = checkpoint_matches[0]
        index_path = checkpoint_dir / "validation_contract_bindings.json"
        _repair_candidate_require(
            index_path.is_file() and not index_path.is_symlink(),
            "repair_candidate_artifact_source_lineage_mismatch",
            f"Repair candidate source binding index is missing after task {completed}.",
        )
        index = _strict_json_object(
            index_path.read_text(encoding="utf-8"), line_number=1, path=index_path
        )
        bindings = index.get("bindings")
        _repair_candidate_require(
            set(index) == {"schema_version", "bindings"}
            and index.get("schema_version")
            == VALIDATION_CONTRACT_BINDING_SCHEMA_VERSION
            and isinstance(bindings, dict),
            "repair_candidate_artifact_source_lineage_mismatch",
            f"Repair candidate source binding index is malformed after task {completed}.",
        )
        bindings_dict = cast(dict[str, Any], bindings)
        versions = bindings_dict.get(tool_name)
        metadata = versions.get(str(version)) if isinstance(versions, dict) else None
        expected_metadata = {
            "tool_version": version,
            "tool_code_hash": code_sha256,
            "tool_spec_hash": spec_sha256,
            "contract_hash": contract_hash,
        }
        _repair_candidate_require(
            isinstance(metadata, dict)
            and set(metadata)
            == {
                "tool_version",
                "tool_code_hash",
                "tool_spec_hash",
                "canonical_key",
                "contract_hash",
            }
            and all(
                metadata.get(key) == value for key, value in expected_metadata.items()
            )
            and isinstance(metadata.get("canonical_key"), str)
            and bool(metadata["canonical_key"]),
            "repair_candidate_artifact_source_lineage_mismatch",
            f"Repair candidate source binding disagrees for {tool_name}:v{version}.",
        )
        metadata_dict = cast(dict[str, Any], metadata)
        blob_path = checkpoint_dir / "validation_contracts" / f"{contract_hash}.json"
        _repair_candidate_require(
            blob_path.is_file()
            and not blob_path.is_symlink()
            and blob_path.resolve().parent
            == (checkpoint_dir / "validation_contracts").resolve(),
            "repair_candidate_artifact_source_lineage_mismatch",
            f"Repair candidate source contract blob is missing for {tool_name}:v{version}.",
        )
        blob = _strict_json_object(
            blob_path.read_text(encoding="utf-8"), line_number=1, path=blob_path
        )
        _repair_candidate_require(
            set(blob)
            == {
                "schema_version",
                "tool_name",
                "tool_version",
                "tool_code_hash",
                "tool_spec_hash",
                "canonical_key",
                "contract",
            }
            and blob.get("schema_version") == VALIDATION_CONTRACT_BINDING_SCHEMA_VERSION
            and blob.get("tool_name") == tool_name
            and blob.get("tool_version") == version
            and blob.get("tool_code_hash") == code_sha256
            and blob.get("tool_spec_hash") == spec_sha256
            and blob.get("canonical_key") == metadata_dict["canonical_key"]
            and isinstance(blob.get("contract"), dict)
            and _canonical_json_sha256(blob) == contract_hash,
            "repair_candidate_artifact_source_lineage_mismatch",
            f"Repair candidate source contract blob disagrees for {tool_name}:v{version}.",
        )


def _verified_repair_source_state(
    candidate_dir: Path,
    identity: tuple[int, str, int, str, str, str],
) -> tuple[str, tuple[str, ...], int, bool]:
    """Revalidate the exact checkpointed source tool against its bound contract."""

    completed, tool_name, version, contract_hash, code_sha256, spec_sha256 = identity
    checkpoint_matches = list(
        (candidate_dir / "registry_checkpoints").glob(f"after_{completed:04d}_*")
    )
    _repair_candidate_require(
        len(checkpoint_matches) == 1
        and checkpoint_matches[0].is_dir()
        and not checkpoint_matches[0].is_symlink(),
        "repair_candidate_artifact_source_lineage_mismatch",
        f"Repair source state has no unique sealed after-{completed} checkpoint.",
    )
    checkpoint_dir = checkpoint_matches[0]
    manifest_path = checkpoint_dir / "registry_manifest.json"
    _repair_candidate_require(
        manifest_path.is_file() and not manifest_path.is_symlink(),
        "repair_candidate_artifact_source_lineage_mismatch",
        f"Repair source registry is missing after task {completed}.",
    )
    manifest = _strict_json_object(
        manifest_path.read_text(encoding="utf-8"),
        line_number=1,
        path=manifest_path,
    )
    tools = manifest.get("tools")
    entry_payload = tools.get(tool_name) if isinstance(tools, dict) else None
    _repair_candidate_require(
        isinstance(tools, dict) and isinstance(entry_payload, dict),
        "repair_candidate_artifact_source_lineage_mismatch",
        f"Repair source registry has no exact entry for {tool_name!r}.",
    )
    try:
        entry = RegistryEntry.from_json(cast(dict[str, Any], entry_payload))
    except (KeyError, TypeError, ValueError) as exc:
        raise _RepairCandidateArtifactVerificationError(
            "repair_candidate_artifact_source_lineage_mismatch",
            f"Repair source registry entry cannot be decoded for {tool_name!r}: {exc}.",
        ) from exc
    actual_code_sha256 = hashlib.sha256(entry.tool.code.encode("utf-8")).hexdigest()
    actual_spec_sha256 = _canonical_json_sha256(entry.tool.spec.to_json())
    _repair_candidate_require(
        entry.tool.spec.tool_name == tool_name
        and entry.version == version
        and entry.stored_code_hash == code_sha256
        and actual_code_sha256 == code_sha256
        and actual_spec_sha256 == spec_sha256,
        "repair_candidate_artifact_source_lineage_mismatch",
        f"Repair source registry identity disagrees for {tool_name}:v{version}.",
    )
    binding, binding_error = ValidationContractBindingStore(checkpoint_dir).resolve(
        entry
    )
    _repair_candidate_require(
        binding is not None
        and binding_error is None
        and binding.tool_name == tool_name
        and binding.tool_version == version
        and binding.tool_code_hash == code_sha256
        and binding.tool_spec_hash == spec_sha256
        and binding.contract_hash == contract_hash,
        "repair_candidate_artifact_source_lineage_mismatch",
        f"Repair source contract cannot be resolved for {tool_name}:v{version}: "
        f"{binding_error}.",
    )
    assert binding is not None
    source_validation = validate_generated_tool(
        entry.tool,
        examples=binding.observation.validation_examples,
    )
    return (
        actual_code_sha256,
        _repair_prompt_errors(source_validation.errors),
        _validation_failure_score(source_validation),
        source_validation.accepted,
    )


def _repair_candidate_event_references(
    candidate_dir: Path,
    protocol_events: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    artifact_fields = {
        "candidate_artifact_path",
        "candidate_artifact_schema_version",
        "candidate_artifact_record_sha256",
    }
    for event_index, event in enumerate(protocol_events):
        _repair_candidate_require(
            isinstance(event, dict),
            "repair_candidate_artifact_event_reference_mismatch",
            f"Protocol event {event_index} is not an object.",
        )
        event_name = event.get("event")
        if event_name == "post_deployment_tool_repair_attempted":
            items = event.get("candidate_validations")
            _repair_candidate_require(
                isinstance(items, list)
                and _positive_int(event.get("candidate_count"))
                and event["candidate_count"] == len(items)
                and isinstance(event.get("request_id"), str)
                and event["request_id"]
                and isinstance(event.get("tool_name"), str)
                and event["tool_name"]
                and _positive_int(event.get("attempt"))
                and _nonnegative_int(event.get("selected_candidate_index")),
                "repair_candidate_artifact_event_reference_mismatch",
                f"Repair-attempt candidate coverage is malformed at event {event_index}.",
            )
            item_rows = cast(list[Any], items)
            seen: set[int] = set()
            event_schema_versions: set[int] = set()
            for item in item_rows:
                artifact_schema_version = (
                    item.get("candidate_artifact_schema_version")
                    if isinstance(item, dict)
                    else None
                )
                expected_reference_keys = (
                    _REPAIR_CANDIDATE_REFERENCE_KEYS_BY_VERSION.get(
                        artifact_schema_version
                    )
                    if isinstance(artifact_schema_version, int)
                    and not isinstance(artifact_schema_version, bool)
                    else None
                )
                _repair_candidate_require(
                    isinstance(item, dict)
                    and expected_reference_keys is not None
                    and set(item) == expected_reference_keys
                    and _nonnegative_int(item.get("candidate_index"))
                    and item["candidate_index"] not in seen
                    and _repair_candidate_reference_path_matches(
                        candidate_dir, item.get("candidate_artifact_path")
                    )
                    and artifact_schema_version
                    in _REPAIR_CANDIDATE_ARTIFACT_SCHEMA_VERSIONS
                    and (
                        artifact_schema_version
                        != _REPAIR_CANDIDATE_ARTIFACT_SCHEMA_VERSION
                        or (
                            item.get("candidate_origin") in _REPAIR_CANDIDATE_ORIGINS
                            and isinstance(item.get("focused_public_case_failed"), bool)
                            and _nonnegative_int(item.get("public_failed_case_count"))
                            and _nonnegative_int(item.get("public_validation_score"))
                            and _nonnegative_int(
                                item.get("regressed_public_case_count")
                            )
                        )
                    )
                    and all(
                        isinstance(item.get(field), str)
                        and _SHA256_HEX_PATTERN.fullmatch(item[field]) is not None
                        for field in (
                            "candidate_artifact_record_sha256",
                            "candidate_code_hash",
                        )
                    )
                    and isinstance(item.get("accepted"), bool)
                    and _nonnegative_int(item.get("validation_score"))
                    and _nonnegative_int(item.get("error_frontier_count"))
                    and isinstance(item.get("errors"), list)
                    and item["error_frontier_count"] == len(item["errors"]),
                    "repair_candidate_artifact_event_reference_mismatch",
                    f"Candidate reference is malformed at protocol event {event_index}.",
                )
                seen.add(item["candidate_index"])
                event_schema_versions.add(cast(int, artifact_schema_version))
                references.append(
                    {
                        "kind": "validated",
                        "event_index": event_index,
                        "event": event,
                        "item": item,
                        "request_id": event["request_id"],
                        "tool_name": event["tool_name"],
                        "attempt": event["attempt"],
                        "candidate_index": item["candidate_index"],
                        "artifact_schema_version": item[
                            "candidate_artifact_schema_version"
                        ],
                        "candidate_origin": item.get("candidate_origin"),
                        "record_sha256": item["candidate_artifact_record_sha256"],
                    }
                )
            _repair_candidate_require(
                event["selected_candidate_index"] in seen,
                "repair_candidate_artifact_event_reference_mismatch",
                f"Selected candidate has no reference at protocol event {event_index}.",
            )
            _repair_candidate_require(
                len(event_schema_versions) == 1,
                "repair_candidate_artifact_schema_invalid",
                f"Repair attempt mixes candidate artifact schemas at event {event_index}.",
            )
            event_schema_version = next(iter(event_schema_versions))
            if event_schema_version == _REPAIR_CANDIDATE_ARTIFACT_SCHEMA_VERSION:
                _repair_candidate_require(
                    isinstance(event.get("clean_room_fallback_requested"), bool)
                    and _nonnegative_int(event.get("ordinary_candidate_count"))
                    and _nonnegative_int(event.get("clean_room_candidate_count"))
                    and event.get("selected_candidate_origin")
                    in _REPAIR_CANDIDATE_ORIGINS
                    and _nonnegative_int(event.get("public_validation_score"))
                    and _nonnegative_int(event.get("best_public_validation_score"))
                    and isinstance(
                        event.get("best_failed_public_case_labels_before_attempt"),
                        list,
                    )
                    and (
                        event.get("focused_public_case_label") is None
                        or (
                            isinstance(event.get("focused_public_case_label"), str)
                            and re.fullmatch(
                                r"(?:source|negative)_\d+",
                                cast(str, event["focused_public_case_label"]),
                            )
                            is not None
                        )
                    ),
                    "repair_candidate_artifact_event_reference_mismatch",
                    f"Repair portfolio provenance is malformed at event {event_index}.",
                )
        elif (
            event_name == "post_deployment_tool_repair_attempt_failed"
            and event.get("stage") == "candidate_normalization_and_validation"
        ):
            artifact_schema_version = event.get("candidate_artifact_schema_version")
            _repair_candidate_require(
                isinstance(event.get("request_id"), str)
                and event["request_id"]
                and isinstance(event.get("tool_name"), str)
                and event["tool_name"]
                and _positive_int(event.get("attempt"))
                and _nonnegative_int(event.get("candidate_index"))
                and isinstance(event.get("error_type"), str)
                and event["error_type"]
                and _repair_candidate_reference_path_matches(
                    candidate_dir, event.get("candidate_artifact_path")
                )
                and isinstance(artifact_schema_version, int)
                and not isinstance(artifact_schema_version, bool)
                and artifact_schema_version
                in _REPAIR_CANDIDATE_ARTIFACT_SCHEMA_VERSIONS
                and (
                    artifact_schema_version != _REPAIR_CANDIDATE_ARTIFACT_SCHEMA_VERSION
                    or event.get("candidate_origin") in _REPAIR_CANDIDATE_ORIGINS
                )
                and isinstance(event.get("candidate_artifact_record_sha256"), str)
                and _SHA256_HEX_PATTERN.fullmatch(
                    event["candidate_artifact_record_sha256"]
                )
                is not None,
                "repair_candidate_artifact_event_reference_mismatch",
                f"Failed-candidate reference is malformed at event {event_index}.",
            )
            references.append(
                {
                    "kind": "exception",
                    "event_index": event_index,
                    "request_id": event["request_id"],
                    "tool_name": event["tool_name"],
                    "attempt": event["attempt"],
                    "candidate_index": event["candidate_index"],
                    "artifact_schema_version": event[
                        "candidate_artifact_schema_version"
                    ],
                    "candidate_origin": event.get("candidate_origin"),
                    "error_type": event["error_type"],
                    "record_sha256": event["candidate_artifact_record_sha256"],
                }
            )
        else:
            _repair_candidate_require(
                not artifact_fields.intersection(event),
                "repair_candidate_artifact_event_reference_mismatch",
                f"Candidate reference appears on unsupported event {event_index}.",
            )
    return references


_REPAIR_BEST_STATE_EVENT_FIELDS = frozenset(
    {
        "best_candidate_code_hash_before_attempt",
        "best_error_labels_before_attempt",
        "best_validation_score",
        "duplicate_of_best",
        "improved_best",
        "next_seed_source",
        "retained_equal_score",
        "stagnation_feedback_label",
    }
)
_REPAIR_BEST_STATE_ACTIVATION_FIELDS = frozenset(
    {
        "best_candidate_code_hash_before_attempt",
        "best_error_labels_before_attempt",
        "duplicate_of_best",
        "stagnation_feedback_label",
    }
)


def _repair_public_case_labels(errors: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Return ordered unique model-visible public case labels."""

    labels: list[str] = []
    for error in errors:
        match = _REPAIR_PUBLIC_CASE_LABEL_PATTERN.match(error)
        if match and match.group(1) not in labels:
            labels.append(match.group(1))
    return tuple(labels)


def _repair_public_validation_score(errors: list[str] | tuple[str, ...]) -> int:
    """Recompute the controller's public-only validation distance."""

    return sum(
        _validation_error_distance(error)
        for error in errors
        if _REPAIR_PUBLIC_CASE_LABEL_PATTERN.match(error)
    )


def _repair_candidate_source_identity(
    row: dict[str, Any],
) -> tuple[int, str, int, str, str, str]:
    return (
        cast(int, row["generated_after_completed_count"]),
        cast(str, row["tool_name"]),
        cast(int, row["source_tool_version"]),
        cast(str, row["source_validation_contract_hash"]),
        cast(str, row["source_tool_code_sha256"]),
        cast(str, row["source_tool_spec_sha256"]),
    )


def _verified_repair_best_state_chains(
    candidate_dir: Path,
    row_by_hash: dict[str, dict[str, Any]],
    references: list[dict[str, Any]],
) -> None:
    """Authenticate each repair attempt against the preceding best candidate."""

    attempted_by_event: dict[int, tuple[dict[str, Any], list[dict[str, Any]]]] = {}
    all_rows_by_attempt: dict[tuple[str, int], list[dict[str, Any]]] = {}
    seen_candidate_identities: set[tuple[str, int, int]] = set()
    reference_items_by_record_hash: dict[str, dict[str, Any]] = {}
    for reference in references:
        row = row_by_hash[cast(str, reference["record_sha256"])]
        request_id = cast(str, reference["request_id"])
        attempt = cast(int, reference["attempt"])
        candidate_index = cast(int, reference["candidate_index"])
        candidate_identity = (request_id, attempt, candidate_index)
        _repair_candidate_require(
            candidate_identity not in seen_candidate_identities,
            "repair_candidate_artifact_event_reference_mismatch",
            f"Repair candidate identity is duplicated: {candidate_identity!r}.",
        )
        seen_candidate_identities.add(candidate_identity)
        all_rows_by_attempt.setdefault((request_id, attempt), []).append(row)
        if reference["kind"] != "validated":
            continue
        reference_items_by_record_hash[cast(str, reference["record_sha256"])] = cast(
            dict[str, Any], reference["item"]
        )
        event_index = cast(int, reference["event_index"])
        event = cast(dict[str, Any], reference["event"])
        prior = attempted_by_event.get(event_index)
        if prior is None:
            prior = (event, [])
            attempted_by_event[event_index] = prior
        else:
            _repair_candidate_require(
                prior[0] is event,
                "repair_candidate_artifact_event_reference_mismatch",
                f"Repair event {event_index} has inconsistent candidate references.",
            )
        prior[1].append(row_by_hash[cast(str, reference["record_sha256"])])

    attempts_by_request: dict[
        str, list[tuple[int, dict[str, Any], list[dict[str, Any]]]]
    ] = {}
    for event_index, (event, event_rows) in sorted(attempted_by_event.items()):
        attempts_by_request.setdefault(cast(str, event["request_id"]), []).append(
            (event_index, event, event_rows)
        )

    source_state_cache: dict[
        tuple[int, str, int, str, str, str], tuple[str, tuple[str, ...], int, bool]
    ] = {}
    for request_id, attempted_events in attempts_by_request.items():
        referenced_schema_versions = {
            cast(int, row["schema_version"])
            for _, _, event_rows in attempted_events
            for row in event_rows
        }
        _repair_candidate_require(
            len(referenced_schema_versions) == 1,
            "repair_candidate_artifact_schema_invalid",
            f"Repair request {request_id!r} mixes candidate artifact schemas.",
        )
        schema_version = next(iter(referenced_schema_versions))
        chain_enabled = schema_version in {
            _REPAIR_CANDIDATE_ARTIFACT_BEST_STATE_SCHEMA_VERSION,
            _REPAIR_CANDIDATE_ARTIFACT_SCHEMA_VERSION,
        } or any(
            bool(_REPAIR_BEST_STATE_ACTIVATION_FIELDS.intersection(event))
            or any(
                row.get("disposition") == "validator_rejected_duplicate_of_best"
                for row in event_rows
            )
            for _, event, event_rows in attempted_events
        )
        if not chain_enabled:
            # Candidate journals written before best-state evidence was introduced
            # remain verifiable under their original exact schema.
            continue

        request_attempt_rows = [
            row
            for _, event, _ in attempted_events
            for row in all_rows_by_attempt.get(
                (request_id, cast(int, event["attempt"])), []
            )
        ]
        identities = {
            _repair_candidate_source_identity(row) for row in request_attempt_rows
        }
        _repair_candidate_require(
            len(identities) == 1,
            "repair_candidate_artifact_source_lineage_mismatch",
            f"Repair request {request_id!r} crosses source tool identities.",
        )
        identity = next(iter(identities))
        if identity not in source_state_cache:
            source_state_cache[identity] = _verified_repair_source_state(
                candidate_dir, identity
            )
        best_code_hash, best_frontier, best_score, best_accepted = source_state_cache[
            identity
        ]
        prior_attempt = 0

        for event_index, event, event_rows in attempted_events:
            attempt = cast(int, event["attempt"])
            _repair_candidate_require(
                attempt > prior_attempt
                and set(_REPAIR_BEST_STATE_EVENT_FIELDS).issubset(event),
                "repair_candidate_artifact_event_reference_mismatch",
                f"Repair request {request_id!r} has malformed attempt ordering or "
                f"best-state evidence at event {event_index}.",
            )
            prior_attempt = attempt
            before_frontier = event.get("best_error_labels_before_attempt")
            _repair_candidate_require(
                event.get("best_candidate_code_hash_before_attempt") == best_code_hash
                and before_frontier == list(best_frontier),
                "repair_candidate_artifact_event_reference_mismatch",
                f"Repair request {request_id!r} does not carry the authenticated "
                f"best candidate into attempt {attempt}.",
            )
            if schema_version == _REPAIR_CANDIDATE_ARTIFACT_SCHEMA_VERSION:
                attempt_rows = all_rows_by_attempt.get((request_id, attempt), [])
                ordinary_rows = [
                    row
                    for row in attempt_rows
                    if row.get("candidate_origin") == "ordinary"
                ]
                clean_room_rows = [
                    row
                    for row in attempt_rows
                    if row.get("candidate_origin") == "clean_room"
                ]
                ordinary_count = event.get("ordinary_candidate_count")
                clean_room_count = event.get("clean_room_candidate_count")
                fallback_requested = event.get("clean_room_fallback_requested")
                _repair_candidate_require(
                    _nonnegative_int(ordinary_count)
                    and _nonnegative_int(clean_room_count)
                    and ordinary_count == len(ordinary_rows)
                    and clean_room_count == len(clean_room_rows)
                    and len(attempt_rows) == ordinary_count + clean_room_count
                    and sorted(
                        cast(int, row["candidate_index"]) for row in ordinary_rows
                    )
                    == list(range(cast(int, ordinary_count)))
                    and sorted(
                        cast(int, row["candidate_index"]) for row in clean_room_rows
                    )
                    == list(
                        range(
                            cast(int, ordinary_count),
                            cast(int, ordinary_count) + cast(int, clean_room_count),
                        )
                    )
                    and [cast(int, row["candidate_index"]) for row in event_rows]
                    == sorted(cast(int, row["candidate_index"]) for row in event_rows)
                    and (
                        fallback_requested is True
                        or (fallback_requested is False and clean_room_count == 0)
                    )
                    and (clean_room_count == 0 or fallback_requested is True),
                    "repair_candidate_artifact_event_reference_mismatch",
                    f"Repair request {request_id!r} has invalid candidate-origin "
                    f"coverage at attempt {attempt}.",
                )
                if fallback_requested is True:
                    _repair_candidate_require(
                        bool(ordinary_rows)
                        and all(
                            cast(dict[str, Any], row["validation"]).get("accepted")
                            is not True
                            for row in ordinary_rows
                        ),
                        "repair_candidate_artifact_event_reference_mismatch",
                        f"Repair request {request_id!r} used clean-room fallback "
                        f"before all ordinary candidates were rejected at attempt "
                        f"{attempt}.",
                    )
                best_public_labels = _repair_public_case_labels(best_frontier)
                expected_focus = best_public_labels[0] if best_public_labels else None
                _repair_candidate_require(
                    event.get("focused_public_case_label") == expected_focus,
                    "repair_candidate_portfolio_selection_mismatch",
                    f"Repair request {request_id!r} has invalid public focus at "
                    f"attempt {attempt}.",
                )
                best_public_label_set = set(best_public_labels)
                ranked_candidates: list[
                    tuple[tuple[bool, int, bool, int, int, int, bool, int], int]
                ] = []
                for row in event_rows:
                    validation = cast(dict[str, Any], row["validation"])
                    candidate_errors = cast(list[str], validation["sanitized_frontier"])
                    candidate_public_labels = _repair_public_case_labels(
                        candidate_errors
                    )
                    regressed_public_case_count = len(
                        set(candidate_public_labels) - best_public_label_set
                    )
                    focused_public_case_failed = bool(
                        expected_focus and expected_focus in candidate_public_labels
                    )
                    public_failed_case_count = len(candidate_public_labels)
                    public_validation_score = _repair_public_validation_score(
                        candidate_errors
                    )
                    candidate_index = cast(int, row["candidate_index"])
                    evaluated = cast(dict[str, Any], row["evaluated_candidate"])
                    accepted = cast(bool, validation["accepted"])
                    validation_score = cast(int, validation["failure_score"])
                    if accepted:
                        public_validation_score = 0
                    duplicate = bool(
                        not accepted
                        and evaluated.get("code_sha256") == best_code_hash
                        and tuple(candidate_errors) == best_frontier
                    )
                    reference_item = reference_items_by_record_hash[
                        cast(str, row["record_sha256"])
                    ]
                    _repair_candidate_require(
                        reference_item.get("regressed_public_case_count")
                        == regressed_public_case_count
                        and reference_item.get("focused_public_case_failed")
                        is focused_public_case_failed
                        and reference_item.get("public_failed_case_count")
                        == public_failed_case_count
                        and reference_item.get("public_validation_score")
                        == public_validation_score,
                        "repair_candidate_portfolio_selection_mismatch",
                        f"Repair request {request_id!r} has invalid public ranking "
                        f"evidence for candidate {candidate_index} at attempt "
                        f"{attempt}.",
                    )
                    ranked_candidates.append(
                        (
                            (
                                not accepted,
                                regressed_public_case_count,
                                focused_public_case_failed,
                                public_failed_case_count,
                                public_validation_score,
                                validation_score,
                                duplicate,
                                candidate_index,
                            ),
                            candidate_index,
                        )
                    )
                expected_selected_index = min(ranked_candidates)[1]
                _repair_candidate_require(
                    event.get("selected_candidate_index") == expected_selected_index,
                    "repair_candidate_portfolio_selection_mismatch",
                    f"Repair request {request_id!r} selected a non-minimal "
                    f"candidate at attempt {attempt}.",
                )
            selected_index = cast(int, event["selected_candidate_index"])
            selected_rows = [
                row for row in event_rows if row["candidate_index"] == selected_index
            ]
            _repair_candidate_require(
                len(selected_rows) == 1,
                "repair_candidate_artifact_event_reference_mismatch",
                f"Repair request {request_id!r} has no unique selected row at "
                f"attempt {attempt}.",
            )
            selected = selected_rows[0]
            selected_validation = cast(dict[str, Any], selected["validation"])
            selected_evidence = cast(dict[str, Any], selected["evaluated_candidate"])
            selected_code_hash = cast(str, selected_evidence["code_sha256"])
            selected_frontier = tuple(
                cast(list[str], selected_validation["sanitized_frontier"])
            )
            selected_score = cast(int, selected_validation["failure_score"])
            selected_accepted = cast(bool, selected_validation["accepted"])
            duplicate_expected = bool(
                not selected_accepted
                and selected_code_hash == best_code_hash
                and selected_frontier == best_frontier
            )
            if schema_version == _REPAIR_CANDIDATE_ARTIFACT_SCHEMA_VERSION:
                selected_public_labels = _repair_public_case_labels(selected_frontier)
                selected_public_score = (
                    0
                    if selected_accepted
                    else _repair_public_validation_score(selected_frontier)
                )
                selected_regressed_public_count = len(
                    set(selected_public_labels) - set(best_public_labels)
                )
                selected_focused_public_failed = bool(
                    expected_focus and expected_focus in selected_public_labels
                )
                selected_progress_rank = (
                    not selected_accepted,
                    selected_regressed_public_count,
                    selected_focused_public_failed,
                    len(set(selected_public_labels)),
                    selected_public_score,
                    selected_score,
                )
                best_public_score = _repair_public_validation_score(best_frontier)
                best_progress_rank = (
                    not best_accepted,
                    0,
                    bool(expected_focus),
                    len(set(best_public_labels)),
                    best_public_score,
                    best_score,
                )
                improved_expected = bool(
                    selected_accepted or selected_progress_rank < best_progress_rank
                )
                retained_expected = bool(
                    not selected_accepted
                    and selected_progress_rank == best_progress_rank
                    and not duplicate_expected
                )
                _repair_candidate_require(
                    event.get("selected_candidate_origin")
                    == selected.get("candidate_origin")
                    and event.get("public_validation_score") == selected_public_score
                    and event.get("best_failed_public_case_labels_before_attempt")
                    == list(best_public_labels),
                    "repair_candidate_portfolio_selection_mismatch",
                    f"Repair request {request_id!r} has invalid selected public "
                    f"evidence at attempt {attempt}.",
                )
            else:
                improved_expected = bool(
                    selected_accepted or selected_score < best_score
                )
                retained_expected = bool(
                    not selected_accepted
                    and selected_score == best_score
                    and not duplicate_expected
                )
            advances_best = improved_expected or retained_expected
            expected_next_seed = (
                "selected_candidate" if advances_best else "best_previous_candidate"
            )
            _repair_candidate_require(
                event.get("duplicate_of_best") is duplicate_expected
                and event.get("stagnation_feedback_label")
                == (
                    REPAIR_STAGNATION_DUPLICATE_CANDIDATE_LABEL
                    if duplicate_expected
                    else None
                )
                and event.get("improved_best") is improved_expected
                and event.get("retained_equal_score") is retained_expected
                and event.get("next_seed_source") == expected_next_seed,
                "repair_candidate_artifact_event_reference_mismatch",
                f"Repair request {request_id!r} has an invalid best-candidate "
                f"decision at attempt {attempt}.",
            )
            if advances_best:
                best_code_hash = selected_code_hash
                best_frontier = selected_frontier
                best_score = selected_score
                best_accepted = selected_accepted
            _repair_candidate_require(
                event.get("best_validation_score") == best_score
                and (
                    schema_version != _REPAIR_CANDIDATE_ARTIFACT_SCHEMA_VERSION
                    or event.get("best_public_validation_score")
                    == _repair_public_validation_score(best_frontier)
                ),
                "repair_candidate_artifact_event_reference_mismatch",
                f"Repair request {request_id!r} has an invalid post-attempt best "
                f"score at attempt {attempt}.",
            )


def _verified_repair_candidate_artifacts(
    candidate_dir: Path,
    protocol_events: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Verify exact repair candidates and their sealed 1:1 event references."""

    artifact_path = candidate_dir / _REPAIR_CANDIDATE_ARTIFACT_FILENAME
    _repair_candidate_require(
        candidate_dir.is_dir()
        and not candidate_dir.is_symlink()
        and artifact_path.resolve().parent == candidate_dir.resolve()
        and not artifact_path.is_symlink()
        and (not artifact_path.exists() or artifact_path.is_file()),
        "repair_candidate_artifact_path_invalid",
        f"Repair candidate artifact path is not fixed and safe: {artifact_path}.",
    )
    references = _repair_candidate_event_references(candidate_dir, protocol_events)
    _repair_candidate_require(
        not references or artifact_path.is_file(),
        "repair_candidate_artifact_missing",
        f"Protocol events reference missing repair candidate artifact {artifact_path}.",
    )

    rows: list[dict[str, Any]] = []
    artifact_bytes = b""
    if artifact_path.is_file():
        try:
            artifact_bytes = artifact_path.read_bytes()
            text = artifact_bytes.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise _RepairCandidateArtifactVerificationError(
                "repair_candidate_artifact_schema_invalid",
                f"Cannot read repair candidate artifact {artifact_path}: {exc}.",
            ) from exc
        _repair_candidate_require(
            not artifact_bytes or artifact_bytes.endswith(b"\n"),
            "repair_candidate_artifact_schema_invalid",
            f"Repair candidate artifact is not append-complete: {artifact_path}.",
        )
        for line_number, line in enumerate(text.splitlines(), start=1):
            _repair_candidate_require(
                bool(line.strip()),
                "repair_candidate_artifact_schema_invalid",
                f"Blank repair-candidate row at line {line_number}: {artifact_path}.",
            )
            rows.append(
                _strict_json_object(line, line_number=line_number, path=artifact_path)
            )

    row_by_hash: dict[str, dict[str, Any]] = {}
    for row_index, row in enumerate(rows):
        schema_version = row.get("schema_version")
        expected_record_keys = (
            _REPAIR_CANDIDATE_RECORD_KEYS_BY_VERSION.get(schema_version)
            if isinstance(schema_version, int) and not isinstance(schema_version, bool)
            else None
        )
        _repair_candidate_require(
            expected_record_keys is not None and set(row) == expected_record_keys,
            "repair_candidate_artifact_schema_invalid",
            f"Repair candidate row {row_index} does not have the exact schema.",
        )
        record_sha256 = row.get("record_sha256")
        _repair_candidate_require(
            schema_version in _REPAIR_CANDIDATE_ARTIFACT_SCHEMA_VERSIONS
            and row.get("event") == "post_deployment_tool_repair_candidate_recorded"
            and isinstance(row.get("request_id"), str)
            and bool(row["request_id"])
            and isinstance(row.get("tool_name"), str)
            and bool(row["tool_name"])
            and _positive_int(row.get("source_tool_version"))
            and row.get("repair_kind") in {"implementation", "metadata"}
            and _nonnegative_int(row.get("generated_after_completed_count"))
            and _positive_int(row.get("attempt"))
            and _nonnegative_int(row.get("candidate_index"))
            and all(
                isinstance(row.get(field), str)
                and _SHA256_HEX_PATTERN.fullmatch(row[field]) is not None
                for field in (
                    "source_validation_contract_hash",
                    "source_tool_code_sha256",
                    "source_tool_spec_sha256",
                )
            )
            and isinstance(row.get("selected_for_attempt"), bool)
            and row.get("future_tasks_only") is True
            and row.get("triggering_task_replayed") is False
            and (
                schema_version != _REPAIR_CANDIDATE_ARTIFACT_SCHEMA_VERSION
                or row.get("candidate_origin") in _REPAIR_CANDIDATE_ORIGINS
            )
            and row.get("evidence_policy")
            == {
                "frontier": "generator_visible_sanitized_labels_only",
                "raw_validation_values_logged": False,
                "private_benchmark_fields_logged": False,
            }
            and isinstance(record_sha256, str)
            and _SHA256_HEX_PATTERN.fullmatch(record_sha256) is not None,
            "repair_candidate_artifact_schema_invalid",
            f"Repair candidate row {row_index} has malformed identity fields.",
        )
        _verify_repair_candidate_tool_evidence(
            row.get("generator_candidate"), label=f"row {row_index} generator"
        )
        evaluated_raw = row.get("evaluated_candidate")
        evaluated_evidence = (
            _verify_repair_candidate_tool_evidence(
                evaluated_raw, label=f"row {row_index} evaluated"
            )
            if evaluated_raw is not None
            else None
        )
        validation = row.get("validation")
        _repair_candidate_require(
            isinstance(validation, dict)
            and set(validation) == _REPAIR_CANDIDATE_VALIDATION_KEYS,
            "repair_candidate_artifact_schema_invalid",
            f"Repair candidate row {row_index} has malformed validation evidence.",
        )
        validation_dict = cast(dict[str, Any], validation)
        frontier = validation_dict.get("sanitized_frontier")
        available = validation_dict.get("available")
        accepted = validation_dict.get("accepted")
        _repair_candidate_require(
            isinstance(available, bool)
            and isinstance(accepted, bool)
            and isinstance(frontier, list)
            and all(isinstance(item, str) and item for item in frontier)
            and len(frontier) == len(set(frontier))
            and _nonnegative_int(validation_dict.get("sanitized_frontier_count"))
            and validation_dict["sanitized_frontier_count"] == len(frontier)
            and validation_dict.get("raw_validation_errors_persisted") is False
            and not any(
                (item.startswith(("held_out_", "blind_property_")) and ":" in item)
                or "expected=" in item
                for item in frontier
            ),
            "repair_candidate_artifact_schema_invalid",
            f"Repair candidate row {row_index} has an unsanitized frontier.",
        )
        disposition = row.get("disposition")
        if available:
            score = validation_dict.get("failure_score")
            selected_dispositions = {
                "validator_accepted_selected",
                "validator_rejected_selected_for_next_seed",
            }
            _repair_candidate_require(
                evaluated_evidence is not None
                and _nonnegative_int(score)
                and all(
                    _nonnegative_int(validation_dict.get(field))
                    for field in (
                        "source_example_count",
                        "held_out_check_count",
                        "negative_applicability_count",
                    )
                )
                and isinstance(validation_dict.get("runtime_smoke_passed"), bool)
                and accepted == (score == 0)
                and row.get("failure_stage") is None
                and row.get("failure_type") is None
                and disposition
                in {
                    "validator_accepted_selected",
                    "validator_accepted_not_selected",
                    "validator_rejected_selected_for_next_seed",
                    "validator_rejected_duplicate_of_best",
                    "validator_rejected",
                }
                and accepted == disposition.startswith("validator_accepted")
                and (
                    disposition == "validator_rejected_duplicate_of_best"
                    or row["selected_for_attempt"]
                    == (disposition in selected_dispositions)
                ),
                "repair_candidate_artifact_schema_invalid",
                f"Repair candidate row {row_index} has inconsistent validation state.",
            )
        else:
            expected_frontier = [
                f"{row.get('failure_stage')}:{row.get('failure_type')}"
            ]
            _repair_candidate_require(
                not accepted
                and validation_dict.get("failure_score") is None
                and all(
                    validation_dict.get(field) is None
                    for field in (
                        "source_example_count",
                        "held_out_check_count",
                        "negative_applicability_count",
                        "runtime_smoke_passed",
                    )
                )
                and row.get("selected_for_attempt") is False
                and disposition == "normalization_or_validation_exception"
                and row.get("failure_stage") == "candidate_normalization_and_validation"
                and isinstance(row.get("failure_type"), str)
                and row["failure_type"]
                and frontier == expected_frontier,
                "repair_candidate_artifact_schema_invalid",
                f"Repair candidate row {row_index} has inconsistent failure state.",
            )
        _repair_candidate_require(
            row.get("repair_kind") != "metadata"
            or evaluated_evidence is None
            or evaluated_evidence["code_sha256"] == row["source_tool_code_sha256"],
            "repair_candidate_artifact_tampered",
            f"Metadata repair candidate row {row_index} changed executable code.",
        )
        prohibited_paths = prohibited_repair_payload_paths(row)
        _repair_candidate_require(
            not prohibited_paths,
            "repair_candidate_artifact_prohibited_payload",
            f"Repair candidate row has private paths: {list(prohibited_paths)!r}.",
        )
        payload = {key: value for key, value in row.items() if key != "record_sha256"}
        _repair_candidate_require(
            _canonical_json_sha256(payload) == record_sha256,
            "repair_candidate_artifact_tampered",
            f"Repair candidate row {row_index} record hash is invalid.",
        )
        _repair_candidate_require(
            record_sha256 not in row_by_hash,
            "repair_candidate_artifact_extra_rows",
            f"Repair candidate artifact duplicates record {record_sha256}.",
        )
        row_by_hash[cast(str, record_sha256)] = row
    _verified_repair_source_bindings(candidate_dir, rows)
    reference_hashes = [str(item["record_sha256"]) for item in references]
    _repair_candidate_require(
        len(reference_hashes) == len(set(reference_hashes)),
        "repair_candidate_artifact_event_reference_mismatch",
        "Protocol events reference a repair candidate record more than once.",
    )
    missing_hashes = [item for item in reference_hashes if item not in row_by_hash]
    _repair_candidate_require(
        not missing_hashes,
        "repair_candidate_artifact_event_reference_mismatch",
        f"Protocol events reference missing candidate rows: {missing_hashes!r}.",
    )
    extra_hashes = [item for item in row_by_hash if item not in set(reference_hashes)]
    _repair_candidate_require(
        not extra_hashes,
        "repair_candidate_artifact_extra_rows",
        f"Repair candidate rows lack protocol-event references: {extra_hashes!r}.",
    )

    for reference in references:
        row = row_by_hash[reference["record_sha256"]]
        _repair_candidate_require(
            row.get("schema_version") == reference["artifact_schema_version"]
            and all(
                row.get(field) == reference.get(field)
                for field in ("request_id", "tool_name", "attempt", "candidate_index")
            )
            and (
                row.get("schema_version") != _REPAIR_CANDIDATE_ARTIFACT_SCHEMA_VERSION
                or row.get("candidate_origin") == reference.get("candidate_origin")
            ),
            "repair_candidate_artifact_event_reference_mismatch",
            f"Candidate identity disagrees at event {reference['event_index']}.",
        )
        if reference["kind"] == "exception":
            _repair_candidate_require(
                row.get("disposition") == "normalization_or_validation_exception"
                and row.get("failure_stage") == "candidate_normalization_and_validation"
                and row.get("failure_type") == reference["error_type"],
                "repair_candidate_artifact_event_reference_mismatch",
                f"Candidate failure disagrees at event {reference['event_index']}.",
            )
            continue
        event = reference["event"]
        item = reference["item"]
        validation = row["validation"]
        evaluated = row["evaluated_candidate"]
        selected = row["candidate_index"] == event["selected_candidate_index"]
        duplicate_disposition = (
            row.get("disposition") == "validator_rejected_duplicate_of_best"
        )
        duplicate_evidence_present = any(
            field in event
            for field in (
                "best_candidate_code_hash_before_attempt",
                "best_error_labels_before_attempt",
                "duplicate_of_best",
                "stagnation_feedback_label",
            )
        )
        if duplicate_disposition or duplicate_evidence_present:
            best_code_hash = event.get("best_candidate_code_hash_before_attempt")
            best_frontier = event.get("best_error_labels_before_attempt")
            duplicate_expected = bool(
                not validation["accepted"]
                and isinstance(evaluated, dict)
                and evaluated.get("code_sha256") == best_code_hash
                and validation["sanitized_frontier"] == best_frontier
            )
            _repair_candidate_require(
                isinstance(best_code_hash, str)
                and _SHA256_HEX_PATTERN.fullmatch(best_code_hash) is not None
                and isinstance(best_frontier, list)
                and all(isinstance(label, str) and label for label in best_frontier)
                and len(best_frontier) == len(set(best_frontier))
                and not any(
                    (
                        label.startswith(("held_out_", "blind_property_"))
                        and ":" in label
                    )
                    or "expected=" in label
                    for label in best_frontier
                )
                and duplicate_disposition == duplicate_expected,
                "repair_candidate_artifact_event_reference_mismatch",
                f"Candidate duplicate evidence disagrees at event {reference['event_index']}.",
            )
            if selected:
                _repair_candidate_require(
                    event.get("duplicate_of_best") is duplicate_expected
                    and event.get("stagnation_feedback_label")
                    == (
                        REPAIR_STAGNATION_DUPLICATE_CANDIDATE_LABEL
                        if duplicate_expected
                        else None
                    )
                    and (
                        not duplicate_expected
                        or (
                            event.get("next_seed_source") == "best_previous_candidate"
                            and event.get("retained_equal_score") is False
                        )
                    ),
                    "repair_candidate_artifact_event_reference_mismatch",
                    f"Selected duplicate disposition disagrees at event {reference['event_index']}.",
                )
        _repair_candidate_require(
            isinstance(evaluated, dict)
            and item["candidate_code_hash"] == evaluated["code_sha256"]
            and item["accepted"] == validation["accepted"]
            and item["validation_score"] == validation["failure_score"]
            and item["error_frontier_count"] == validation["sanitized_frontier_count"]
            and item["errors"] == validation["sanitized_frontier"]
            and row["selected_for_attempt"] == selected
            and (
                not selected
                or (
                    event.get("selected_candidate_code_hash")
                    == evaluated["code_sha256"]
                    and event.get("accepted") == validation["accepted"]
                    and event.get("validation_score") == validation["failure_score"]
                    and event.get("error_labels") == validation["sanitized_frontier"]
                )
            ),
            "repair_candidate_artifact_event_reference_mismatch",
            f"Candidate validation disagrees at event {reference['event_index']}.",
        )

    _verified_repair_best_state_chains(candidate_dir, row_by_hash, references)

    schema_versions = sorted({cast(int, row["schema_version"]) for row in rows})
    current_schema_only = bool(rows) and schema_versions == [
        _REPAIR_CANDIDATE_ARTIFACT_SCHEMA_VERSION
    ]
    return {
        "status": "pass",
        "path": str(artifact_path),
        "artifact_present": artifact_path.is_file(),
        "record_count": len(rows),
        "referenced_record_count": len(references),
        "artifact_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
        "canonical_records_sha256": _canonical_json_sha256(rows),
        "schema_versions": schema_versions,
        "candidate_origin_authenticated": current_schema_only,
        "portfolio_selection_authenticated": current_schema_only,
    }


def _verify_metadata_implementation_proof(
    *,
    request: dict[str, Any],
    acknowledgement: dict[str, Any],
) -> None:
    """Require code-hash equality for every metadata-repair disposition."""

    request_id = str(request.get("request_id") or "")
    source_hash = request.get("source_code_hash")
    proof = acknowledgement.get("implementation_proof")
    if (
        not isinstance(source_hash, str)
        or _SHA256_HEX_PATTERN.fullmatch(source_hash) is None
        or not isinstance(proof, dict)
    ):
        raise ValueError(
            f"Metadata repair {request_id!r} has no valid source-hash proof."
        )
    proof_source_hash = proof.get("source_code_hash")
    replacement_hash = proof.get("replacement_code_hash")
    replacement_activated = proof.get("replacement_activated")
    implementation_preserved = proof.get("implementation_preserved")
    code_change_discarded = proof.get("model_authored_code_change_discarded")
    status = str(acknowledgement.get("status") or "")
    valid = bool(
        proof.get("proof_schema_version") == 1
        and proof.get("repair_kind") == "metadata"
        and proof_source_hash == source_hash
        and isinstance(replacement_activated, bool)
        and implementation_preserved is True
        and isinstance(code_change_discarded, bool)
        and (
            (
                replacement_activated
                and isinstance(replacement_hash, str)
                and _SHA256_HEX_PATTERN.fullmatch(replacement_hash) is not None
                and replacement_hash == source_hash
            )
            or (not replacement_activated and replacement_hash is None)
        )
        and (status not in {"canary_pending", "promoted"} or replacement_activated)
    )
    if not valid:
        raise ValueError(
            f"Metadata repair {request_id!r} did not preserve its source "
            "implementation hash."
        )


def _lifecycle_tool_names(
    row: dict[str, Any],
    *,
    field: str,
    artifact: str,
) -> tuple[str, ...]:
    value = row.get(field)
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        raise ValueError(f"Lifecycle {artifact} has malformed {field!r}.")
    return tuple(value)


def _lifecycle_tool_versions(
    row: dict[str, Any],
    *,
    artifact: str,
) -> dict[str, int]:
    value = row.get("generated_tool_versions")
    if not isinstance(value, dict):
        raise ValueError(
            f"Lifecycle {artifact} has malformed 'generated_tool_versions'."
        )
    versions: dict[str, int] = {}
    for tool_name, version in value.items():
        if (
            not isinstance(tool_name, str)
            or not tool_name
            or isinstance(version, bool)
            or not isinstance(version, int)
            or version < 1
        ):
            raise ValueError(
                f"Lifecycle {artifact} has malformed generated-tool version data."
            )
        versions[tool_name] = version
    return versions


def _public_lifecycle_family(row: dict[str, Any]) -> str:
    """Mirror the lifecycle's fail-closed public family-label boundary."""

    if row.get("source_task_id_redacted") is not True:
        return "unclassified"
    family = str(row.get("task_family_key") or "").strip().lower()
    if (
        not family
        or len(family) > 128
        or re.fullmatch(r"[a-z0-9_.:-]+", family) is None
    ):
        return "unclassified"
    return family


def _paired_lifecycle_evidence_rows(
    candidate_dir: Path,
    *,
    trajectory_evidence: dict[str, dict[str, tuple[str, ...]]] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Bind selection facts to the matching independently written feedback row."""

    selection_rows = _read_jsonl_objects(
        candidate_dir / "scenario_tool_selection.jsonl"
    )
    feedback_rows = [
        row
        for row in _read_jsonl_objects(
            candidate_dir / "self_evolution_task_feedback.jsonl"
        )
        if row.get("event") == "self_evolution_task_assessed"
    ]
    if not selection_rows or len(selection_rows) != len(feedback_rows):
        raise ValueError(
            "Lifecycle selection and reflection evidence are missing or incomplete."
        )
    if trajectory_evidence is not None and len(trajectory_evidence) != len(
        selection_rows
    ):
        raise ValueError(
            "Lifecycle evidence is not backed by one trajectory for every task."
        )

    paired: list[dict[str, Any]] = []
    # Cardinality was checked above, so ordinary zip remains fail-closed while
    # retaining compatibility with the legacy Python 3.9 lifecycle fixtures.
    for selection, feedback in zip(selection_rows, feedback_rows):
        scenario = str(selection.get("scenario") or "")
        if not scenario or str(feedback.get("scenario") or "") != scenario:
            raise ValueError(
                "Reflection task order disagrees with lifecycle selection evidence."
            )
        selection_values = {
            field: _lifecycle_tool_names(
                selection,
                field=field,
                artifact=f"selection row for {scenario!r}",
            )
            for field in _LIFECYCLE_SELECTION_FIELDS
        }
        if trajectory_evidence is not None:
            raw = trajectory_evidence.get(scenario)
            if not isinstance(raw, dict):
                raise ValueError(
                    f"Lifecycle evidence for {scenario!r} has no raw trajectory."
                )
            for field in (
                "generated_tools_visible",
                "generated_tools_called",
                "generated_tools_attempted",
                "generated_tools_failed",
            ):
                raw_values = raw.get(field)
                if not isinstance(raw_values, tuple) or set(
                    selection_values[field]
                ) != set(raw_values):
                    raise ValueError(
                        "Lifecycle selection evidence disagrees with raw trajectory "
                        f"{field!r} for {scenario!r}."
                    )
        feedback_values = {
            field: _lifecycle_tool_names(
                feedback,
                field=field,
                artifact=f"feedback row for {scenario!r}",
            )
            for field in _LIFECYCLE_SELECTION_FIELDS
        }
        if selection_values != feedback_values:
            raise ValueError(
                "Lifecycle selection and reflection generated-tool evidence disagree "
                f"for {scenario!r}."
            )
        selection_versions = _lifecycle_tool_versions(
            selection,
            artifact=f"selection row for {scenario!r}",
        )
        feedback_versions = _lifecycle_tool_versions(
            feedback,
            artifact=f"feedback row for {scenario!r}",
        )
        if selection_versions != feedback_versions:
            raise ValueError(
                "Lifecycle selection and reflection generated-tool versions disagree "
                f"for {scenario!r}."
            )
        if selection.get("exception_type") != feedback.get("exception_type"):
            raise ValueError(
                "Lifecycle selection and reflection exception evidence disagree "
                f"for {scenario!r}."
            )
        observed_tools = set().union(*map(set, selection_values.values()))
        if set(selection_versions) != observed_tools:
            raise ValueError(
                "Lifecycle evidence cannot bind every observed generated tool to its "
                f"version for {scenario!r}."
            )
        called = set(selection_values["generated_tools_called"])
        attempted = set(selection_values["generated_tools_attempted"])
        failed = set(selection_values["generated_tools_failed"])
        contract_failed = set(selection_values["generated_tool_contract_failures"])
        if not failed.issubset(attempted) or not contract_failed.issubset(called):
            raise ValueError(
                "Lifecycle evidence contains a failure not attributable to an actual "
                f"generated-tool attempt/call for {scenario!r}."
            )
        paired.append(
            {
                "scenario": scenario,
                "selection": selection,
                "feedback": feedback,
                "selection_values": selection_values,
                "versions": selection_versions,
                "observed_tools": observed_tools,
            }
        )
    return tuple(paired)


def _safe_checkpoint_name(scenario_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", scenario_name).strip("_")
    return slug[:120] or "scenario"


def _verified_checkpoint_tool_identity(
    *,
    entry: Any,
    scenario: str,
    tool_name: str,
    expected_version: int,
) -> dict[str, Any]:
    """Return a registry-backed call-time identity or fail closed."""

    if not isinstance(entry, dict):
        raise ValueError(
            f"Registry checkpoint for {scenario!r} has no entry for observed "
            f"generated tool {tool_name!r}."
        )
    version = entry.get("version")
    tool = entry.get("tool")
    spec = tool.get("spec") if isinstance(tool, dict) else None
    declared_name = spec.get("tool_name") if isinstance(spec, dict) else None
    code = tool.get("code") if isinstance(tool, dict) else None
    stored_code_hash = entry.get("code_hash")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version < 1
        or version != expected_version
    ):
        raise ValueError(
            f"Registry checkpoint version disagrees with lifecycle evidence for "
            f"{scenario!r} tool {tool_name!r}."
        )
    if declared_name != tool_name:
        raise ValueError(
            f"Registry checkpoint key and declared generated-tool name disagree "
            f"for {scenario!r} tool {tool_name!r}."
        )
    if (
        not isinstance(code, str)
        or not isinstance(stored_code_hash, str)
        or _SHA256_HEX_PATTERN.fullmatch(stored_code_hash) is None
        or hashlib.sha256(code.encode("utf-8")).hexdigest() != stored_code_hash
    ):
        raise ValueError(
            f"Registry checkpoint code hash is invalid for {scenario!r} tool "
            f"{tool_name!r}."
        )
    return {
        "scenario": scenario,
        "tool_name": tool_name,
        "tool_version": version,
        "code_hash": stored_code_hash,
    }


def _validated_checkpoint_contract_identity(
    *,
    checkpoint_dir: Path,
    copied_files: set[str],
    raw_entry: Any,
    scenario: str,
    tool_name: str,
    expected_version: int,
    require_active_proof: bool,
) -> dict[str, Any]:
    """Resolve and replay one contract using only one sealed checkpoint.

    Held-out values remain inside the validator-side contract blob.  Neither
    this function's result nor its errors serialize those values.
    """

    identity = _verified_checkpoint_tool_identity(
        entry=raw_entry,
        scenario=scenario,
        tool_name=tool_name,
        expected_version=expected_version,
    )
    try:
        entry = RegistryEntry.from_json(raw_entry)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"Registry checkpoint entry is malformed for {scenario!r} tool "
            f"{tool_name!r}."
        ) from exc
    if (
        entry.tool.spec.tool_name != tool_name
        or entry.version != expected_version
        or entry.stored_code_hash != identity["code_hash"]
        or not entry.code_hash_verified
    ):
        raise ValueError(
            f"Registry checkpoint entry identity changed while parsing "
            f"{scenario!r} tool {tool_name!r}."
        )

    binding_store = ValidationContractBindingStore(checkpoint_dir)
    binding, binding_error = binding_store.resolve(entry)
    if binding is None:
        raise ValueError(
            f"Registry checkpoint validation-contract binding is invalid for "
            f"{scenario!r} tool {tool_name!r}: "
            f"{binding_error or 'unknown_binding_error'}."
        )
    index_relative = binding_store.index_path.relative_to(checkpoint_dir).as_posix()
    blob_relative = (
        (binding_store.blob_directory / f"{binding.contract_hash}.json")
        .relative_to(checkpoint_dir)
        .as_posix()
    )
    if index_relative not in copied_files or blob_relative not in copied_files:
        raise ValueError(
            f"Registry checkpoint metadata omits the exact validation contract "
            f"for {scenario!r} tool {tool_name!r}."
        )
    spec_sha256 = hashlib.sha256(
        json.dumps(
            entry.tool.spec.to_json(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    if (
        binding.tool_name != tool_name
        or binding.tool_version != expected_version
        or binding.tool_code_hash != identity["code_hash"]
        or binding.tool_spec_hash != spec_sha256
    ):
        raise ValueError(
            f"Registry checkpoint validation contract has the wrong identity for "
            f"{scenario!r} tool {tool_name!r}."
        )

    replayed = validate_generated_tool(
        entry.tool,
        binding.observation.validation_examples,
    )
    if not replayed.accepted or not entry.validation.accepted:
        raise ValueError(
            f"Registry checkpoint validation contract is not accepted for "
            f"{scenario!r} tool {tool_name!r}."
        )
    if replayed != entry.validation:
        raise ValueError(
            f"Registry checkpoint validation replay disagrees with the stored "
            f"admission result for {scenario!r} tool {tool_name!r}."
        )
    if require_active_proof and not has_current_validation_proof(entry):
        raise ValueError(
            f"Final active registry tool lacks current validation proof: {tool_name!r}."
        )

    return {
        **identity,
        "contract_hash": binding.contract_hash,
        "canonical_key_sha256": hashlib.sha256(
            binding.canonical_key.encode("utf-8")
        ).hexdigest(),
        "tool_spec_sha256": binding.tool_spec_hash,
        "validation_replayed": True,
        "validation_accepted": True,
    }


def _checkpoint_metadata(
    *,
    checkpoint_dir: Path,
    expected_registry_dir: Path,
    scenario: str,
    completed_count: int,
) -> tuple[dict[str, Any], set[str]]:
    metadata_path = checkpoint_dir / "checkpoint.json"
    if (
        not checkpoint_dir.is_dir()
        or checkpoint_dir.is_symlink()
        or not metadata_path.is_file()
        or metadata_path.is_symlink()
    ):
        raise ValueError(
            f"Registry checkpoint is missing for publication task {scenario!r}."
        )
    metadata = _read_json(metadata_path)
    copied_files = metadata.get("copied_files")
    snapshot_errors = metadata.get("validation_contract_snapshot_errors")
    if (
        metadata.get("scenario") != scenario
        or metadata.get("completed_count") != completed_count
        or not isinstance(metadata.get("registry_dir"), str)
        or Path(metadata["registry_dir"]).resolve() != expected_registry_dir
        or not isinstance(copied_files, list)
        or any(not isinstance(item, str) or not item for item in copied_files)
        or len(copied_files) != len(set(copied_files))
        or not isinstance(snapshot_errors, list)
        or snapshot_errors
    ):
        raise ValueError(
            f"Registry checkpoint metadata or validation-contract snapshot is "
            f"invalid for publication task {scenario!r}."
        )
    copied_set = set(copied_files)
    if any(
        Path(item).is_absolute()
        or ".." in Path(item).parts
        or Path(item).as_posix() != item
        for item in copied_set
    ):
        raise ValueError(
            f"Registry checkpoint copied-file paths are invalid for publication "
            f"task {scenario!r}."
        )
    return metadata, copied_set


def _selection_only_checkpoint_rows(
    candidate_dir: Path,
    *,
    trajectory_evidence: dict[str, dict[str, tuple[str, ...]]],
) -> tuple[dict[str, Any], ...]:
    """Build checkpoint rows for immutable generation-off registry reuse."""

    selection_rows = _read_jsonl_objects(
        candidate_dir / "scenario_tool_selection.jsonl"
    )
    if not selection_rows or len(selection_rows) != len(trajectory_evidence):
        raise ValueError("Frozen registry selection evidence is missing or incomplete.")
    rows: list[dict[str, Any]] = []
    for selection in selection_rows:
        scenario = str(selection.get("scenario") or "")
        raw = trajectory_evidence.get(scenario)
        if not scenario or not isinstance(raw, dict):
            raise ValueError(
                "Frozen registry selection evidence has no matching raw trajectory."
            )
        selection_values = {
            field: _lifecycle_tool_names(
                selection,
                field=field,
                artifact=f"selection row for {scenario!r}",
            )
            for field in _LIFECYCLE_SELECTION_FIELDS
        }
        for field in (
            "generated_tools_visible",
            "generated_tools_called",
            "generated_tools_attempted",
            "generated_tools_failed",
        ):
            raw_values = raw.get(field)
            if not isinstance(raw_values, tuple) or set(selection_values[field]) != set(
                raw_values
            ):
                raise ValueError(
                    "Frozen registry selection evidence disagrees with raw "
                    f"trajectory {field!r} for {scenario!r}."
                )
        versions = _lifecycle_tool_versions(
            selection,
            artifact=f"selection row for {scenario!r}",
        )
        observed_tools = set().union(*map(set, selection_values.values()))
        if set(versions) != observed_tools:
            raise ValueError(
                "Frozen registry evidence cannot bind every observed generated "
                f"tool to its version for {scenario!r}."
            )
        rows.append(
            {
                "scenario": scenario,
                "selection": selection,
                "selection_values": selection_values,
                "versions": versions,
                "observed_tools": observed_tools,
            }
        )
    return tuple(rows)


def _verify_registry_checkpoint_bindings(
    candidate_dir: Path,
    registry_dir: Path,
    *,
    scenario_order: list[str] | tuple[str, ...],
    trajectory_evidence: dict[str, dict[str, tuple[str, ...]]],
    require_lifecycle_feedback: bool = True,
) -> dict[str, Any]:
    """Bind each task's generated-tool evidence to its after-task registry.

    Selection and feedback files are both adapter-authored summaries.  A forged
    version in both previously passed.  These checks instead require the exact
    ordered checkpoint emitted after every task and hash the implementation
    bytes stored there.  Empty-start tasks before the first tool birth may have
    no registry manifest; that is valid only when no generated tool was visible
    or executed on that task.
    """

    paired_rows = (
        _paired_lifecycle_evidence_rows(
            candidate_dir,
            trajectory_evidence=trajectory_evidence,
        )
        if require_lifecycle_feedback
        else _selection_only_checkpoint_rows(
            candidate_dir,
            trajectory_evidence=trajectory_evidence,
        )
    )
    paired_order = tuple(str(row["scenario"]) for row in paired_rows)
    expected_order = tuple(scenario_order)
    if paired_order != expected_order:
        raise ValueError(
            "Registry checkpoint verification cannot bind lifecycle evidence to "
            "the exact publication task order."
        )

    checkpoint_root = candidate_dir / "registry_checkpoints"
    if not checkpoint_root.is_dir() or checkpoint_root.is_symlink():
        raise ValueError(
            "Completed online SAGE run is missing its registry checkpoint directory."
        )

    expected_registry_dir = registry_dir.resolve()
    identities: list[dict[str, Any]] = []
    checkpoint_count = 0
    checkpoint_by_count: dict[int, Path] = {}
    for completed_count, paired in enumerate(paired_rows, start=1):
        scenario = str(paired["scenario"])
        checkpoint_dir = checkpoint_root / (
            f"after_{completed_count:04d}_{_safe_checkpoint_name(scenario)}"
        )
        manifest_path = checkpoint_dir / "registry_manifest.json"
        _metadata, copied_files = _checkpoint_metadata(
            checkpoint_dir=checkpoint_dir,
            expected_registry_dir=expected_registry_dir,
            scenario=scenario,
            completed_count=completed_count,
        )
        checkpoint_by_count[completed_count] = checkpoint_dir

        observed_tools = set(paired["observed_tools"])
        if not manifest_path.is_file() or manifest_path.is_symlink():
            if "registry_manifest.json" in copied_files or observed_tools:
                raise ValueError(
                    f"Registry checkpoint for {scenario!r} cannot bind observed "
                    "generated tools to a manifest."
                )
            checkpoint_count += 1
            continue
        if "registry_manifest.json" not in copied_files:
            raise ValueError(
                f"Registry checkpoint metadata omits its manifest for publication "
                f"task {scenario!r}."
            )
        manifest = _read_json(manifest_path)
        tools = manifest.get("tools")
        if not isinstance(tools, dict):
            raise ValueError(
                f"Registry checkpoint manifest is invalid for publication task "
                f"{scenario!r}."
            )
        versions = paired["versions"]
        if set(versions) != observed_tools:
            raise ValueError(
                f"Registry checkpoint version coverage is incomplete for publication "
                f"task {scenario!r}."
            )
        for tool_name in sorted(observed_tools):
            identities.append(
                _validated_checkpoint_contract_identity(
                    checkpoint_dir=checkpoint_dir,
                    copied_files=copied_files,
                    raw_entry=tools.get(tool_name),
                    scenario=scenario,
                    tool_name=tool_name,
                    expected_version=versions[tool_name],
                    require_active_proof=False,
                )
            )
        checkpoint_count += 1

    finalization_dir = checkpoint_root / (
        f"after_{len(paired_rows):04d}_{_safe_checkpoint_name('run_finalization')}"
    )
    if finalization_dir.exists() or finalization_dir.is_symlink():
        final_checkpoint_dir = finalization_dir
        final_scenario = "run_finalization"
        _metadata, final_copied_files = _checkpoint_metadata(
            checkpoint_dir=final_checkpoint_dir,
            expected_registry_dir=expected_registry_dir,
            scenario=final_scenario,
            completed_count=len(paired_rows),
        )
    else:
        final_checkpoint_dir = checkpoint_by_count[len(paired_rows)]
        final_scenario = str(paired_rows[-1]["scenario"])
        _metadata, final_copied_files = _checkpoint_metadata(
            checkpoint_dir=final_checkpoint_dir,
            expected_registry_dir=expected_registry_dir,
            scenario=final_scenario,
            completed_count=len(paired_rows),
        )
    final_checkpoint_manifest = final_checkpoint_dir / "registry_manifest.json"
    final_registry_manifest = registry_dir / "registry_manifest.json"
    if (
        "registry_manifest.json" not in final_copied_files
        or not final_checkpoint_manifest.is_file()
        or final_checkpoint_manifest.is_symlink()
        or not final_registry_manifest.is_file()
        or final_registry_manifest.is_symlink()
        or final_checkpoint_manifest.read_bytes()
        != final_registry_manifest.read_bytes()
    ):
        raise ValueError(
            "Final checkpoint registry manifest does not exactly match the sealed "
            "final registry manifest."
        )
    final_manifest = _read_json(final_checkpoint_manifest)
    final_tools = final_manifest.get("tools")
    if not isinstance(final_tools, dict):
        raise ValueError("Final checkpoint registry manifest has no tool mapping.")
    final_active_identities: list[dict[str, Any]] = []
    for tool_name, raw_entry in sorted(final_tools.items()):
        if not isinstance(tool_name, str) or not tool_name:
            raise ValueError("Final checkpoint registry has an invalid tool key.")
        if not isinstance(raw_entry, dict):
            raise ValueError(
                f"Final checkpoint registry entry is malformed for {tool_name!r}."
            )
        # Match runtime's fail-closed interpretation: only literal true retires.
        if raw_entry.get("retired") is True:
            continue
        version = raw_entry.get("version")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError(
                f"Final active registry tool has an invalid version: {tool_name!r}."
            )
        final_active_identities.append(
            _validated_checkpoint_contract_identity(
                checkpoint_dir=final_checkpoint_dir,
                copied_files=final_copied_files,
                raw_entry=raw_entry,
                scenario=final_scenario,
                tool_name=tool_name,
                expected_version=version,
                require_active_proof=True,
            )
        )

    canonical_identity_bytes = json.dumps(
        identities,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    canonical_contract_bytes = json.dumps(
        {
            "observed": identities,
            "final_active": final_active_identities,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "registry_checkpoint_count": checkpoint_count,
        "registry_checkpoint_binding_count": len(identities),
        "registry_checkpoint_binding_sha256": hashlib.sha256(
            canonical_identity_bytes
        ).hexdigest(),
        "public_contract_binding_verification": {
            "status": "pass",
            "source": "checkpoint_local_content_addressed_contracts",
            "observed_contract_replay_count": len(identities),
            "final_active_contract_replay_count": len(final_active_identities),
            "validation_values_reported": False,
            "contract_replay_identity_sha256": hashlib.sha256(
                canonical_contract_bytes
            ).hexdigest(),
        },
    }


def _checkpoint_lifecycle_rows(path: Path) -> dict[str, Any] | None:
    if not path.is_file() or path.is_symlink():
        return None
    payload = _read_json(path)
    rows = payload.get("tool_lifecycle")
    return rows if isinstance(rows, dict) else None


def _public_actor_followthrough_family(feedback: dict[str, Any]) -> str | None:
    family = feedback.get("task_family_key")
    label = feedback.get("task_context_label")
    if (
        feedback.get("source_task_id_redacted") is not True
        or not isinstance(family, str)
        or re.fullmatch(r"[a-z0-9_.:-]{1,128}", family) is None
        or not isinstance(label, str)
        or not label.startswith(f"visible_task_context(family={family}")
    ):
        return None
    return family


def _actor_followthrough_family_suppressed(
    lifecycle_row: Any,
    *,
    family: str,
    tool_version: int,
) -> bool:
    if not isinstance(lifecycle_row, dict):
        return False
    reason_codes = lifecycle_row.get("route_repair_reason_codes")
    failure_count = lifecycle_row.get("actor_followthrough_failure_count")
    return bool(
        lifecycle_row.get("tool_version") == tool_version
        and isinstance(failure_count, int)
        and not isinstance(failure_count, bool)
        and failure_count >= 1
        and family in (lifecycle_row.get("actor_followthrough_failure_families") or [])
        and family in (lifecycle_row.get("route_repair_families") or [])
        and isinstance(reason_codes, dict)
        and "generated_helper_followup_failure" in (reason_codes.get(family) or [])
        and lifecycle_row.get("repair_kind") == "routing"
        and lifecycle_row.get("routing_disposition") == "family_suppression_active"
        and lifecycle_row.get("decision")
        in {"needs_route_repair", "retain_with_route_repair"}
    )


def _final_registry_checkpoint_directory(
    candidate_dir: Path,
    *,
    scenario_order: list[str] | tuple[str, ...],
) -> Path:
    checkpoint_root = candidate_dir / "registry_checkpoints"
    finalization = checkpoint_root / (
        f"after_{len(scenario_order):04d}_{_safe_checkpoint_name('run_finalization')}"
    )
    if finalization.exists() or finalization.is_symlink():
        return finalization
    return checkpoint_root / (
        f"after_{len(scenario_order):04d}_"
        f"{_safe_checkpoint_name(str(scenario_order[-1]))}"
    )


def _terminal_actor_followthrough_supersession(
    *,
    candidate_dir: Path,
    final_checkpoint_dir: Path,
    protocol_events: list[dict[str, Any]],
    tool_name: str,
    source_tool_version: int,
    final_entry_payload: Any,
) -> dict[str, Any] | None:
    """Prove that a validated implementation repair superseded a failed version."""

    try:
        if not isinstance(final_entry_payload, dict):
            raise ValueError("final_entry_missing")
        final_entry = RegistryEntry.from_json(final_entry_payload)
        final_version = final_entry.version
        if (
            final_entry.tool.spec.tool_name != tool_name
            or final_version <= source_tool_version
        ):
            raise ValueError("not_a_later_exact_tool_version")

        # Resolve only from the immutable final checkpoint.  The mutable final
        # registry is deliberately not a fallback source for this proof.
        binding, binding_error = ValidationContractBindingStore(
            final_checkpoint_dir
        ).resolve(final_entry)
        if binding is None:
            raise ValueError(binding_error or "binding_invalid")
        replay = validate_generated_tool(
            final_entry.tool,
            binding.observation.validation_examples,
        )
        if not replay.accepted or replay != final_entry.validation:
            raise ValueError("validation_replay_mismatch")

        repair_requests = _read_jsonl_objects(
            candidate_dir / "self_evolution_tool_repair_requests.jsonl"
        )
        request_candidates = [
            row
            for row in repair_requests
            if row.get("tool_name") == tool_name
            and row.get("source_tool_version") == source_tool_version
            and not isinstance(row.get("source_tool_version"), bool)
        ]
        if len(request_candidates) != 1:
            raise ValueError("repair_request_not_unique")
        request = request_candidates[0]
        request_id = request.get("request_id")
        if (
            not isinstance(request_id, str)
            or not request_id
            or request.get("repair_kind") != "implementation"
            or request.get("future_tasks_only") is not True
            or request.get("triggering_task_replay_allowed") is not False
        ):
            raise ValueError("repair_request_not_terminal_implementation")

        acknowledgements = _read_jsonl_objects(
            candidate_dir / "self_evolution_tool_repair_acknowledgements.jsonl"
        )
        request_acknowledgements = [
            row for row in acknowledgements if row.get("request_id") == request_id
        ]
        promoted_acknowledgements = [
            row
            for row in request_acknowledgements
            if row.get("status") == "promoted"
            and row.get("tool_name") == tool_name
            and row.get("new_version") == final_version
            and not isinstance(row.get("new_version"), bool)
        ]
        if (
            len(promoted_acknowledgements) != 1
            or not request_acknowledgements
            or request_acknowledgements[-1] != promoted_acknowledgements[0]
        ):
            raise ValueError("terminal_promoted_acknowledgement_missing")

        acceptance_candidates = [
            row
            for row in protocol_events
            if row.get("event") == "post_deployment_tool_repair_accepted"
            and (
                row.get("request_id") == request_id
                or (
                    row.get("tool_name") == tool_name
                    and row.get("source_tool_version") == source_tool_version
                    and not isinstance(row.get("source_tool_version"), bool)
                )
            )
        ]
        accepted_events = [
            row
            for row in acceptance_candidates
            if row.get("request_id") == request_id
            and row.get("tool_name") == tool_name
            and row.get("source_tool_version") == source_tool_version
            and not isinstance(row.get("source_tool_version"), bool)
            and row.get("new_tool_version") == final_version
            and not isinstance(row.get("new_tool_version"), bool)
            and row.get("repair_kind") == "implementation"
            and row.get("validation_contract_hash") == binding.contract_hash
            and row.get("triggering_task_replayed") is False
        ]
        if len(acceptance_candidates) != 1 or len(accepted_events) != 1:
            raise ValueError("sealed_acceptance_event_missing_or_ambiguous")
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None

    return {
        "request_id": request_id,
        "source_tool_version": source_tool_version,
        "new_tool_version": final_version,
        "new_tool_retired": final_entry.retired,
        "new_tool_code_hash": binding.tool_code_hash,
        "new_tool_spec_hash": binding.tool_spec_hash,
        "validation_contract_hash": binding.contract_hash,
        "terminal_acknowledgement": "promoted",
        "sealed_acceptance_event_count": 1,
    }


def _verify_actor_followthrough_closed(
    candidate_dir: Path,
    registry_dir: Path,
    *,
    scenario_order: list[str] | tuple[str, ...],
    trajectory_evidence: dict[str, dict[str, tuple[str, ...]]],
    protocol_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Derive actor follow-through failures from raw traces and prove closure."""

    paired_rows = _paired_lifecycle_evidence_rows(
        candidate_dir,
        trajectory_evidence=trajectory_evidence,
    )
    expected_registry_dir = registry_dir.resolve()
    action_journal = _read_jsonl_objects(
        candidate_dir / "self_evolution_tool_lifecycle.jsonl"
    )
    protocol_events = protocol_events or []
    consumed_action_indices: set[int] = set()
    last_consumed_action_index = -1
    obligations: list[dict[str, Any]] = []
    for completed_count, paired in enumerate(paired_rows, start=1):
        scenario = str(paired["scenario"])
        checkpoint_dir = (
            candidate_dir
            / "registry_checkpoints"
            / (f"after_{completed_count:04d}_{_safe_checkpoint_name(scenario)}")
        )
        _metadata, copied_files = _checkpoint_metadata(
            checkpoint_dir=checkpoint_dir,
            expected_registry_dir=expected_registry_dir,
            scenario=scenario,
            completed_count=completed_count,
        )
        manifest = _read_json(checkpoint_dir / "registry_manifest.json")
        checkpoint_tools = manifest.get("tools")
        conversation = _read_json_list(
            candidate_dir / "trajectories" / scenario / "conversation.json",
            label=f"candidate trajectory {scenario!r} conversation",
        )
        if not isinstance(checkpoint_tools, dict):
            raise ValueError(
                f"Actor follow-through checkpoint is malformed for {scenario!r}."
            )
        trace_events = _tool_trace_events_from_execution_context(
            candidate_dir / "trajectories" / scenario / "execution_context.json"
        )
        derived_failures: list[tuple[str, int]] = []
        called_tools = trajectory_evidence[scenario]["generated_tools_called"]
        for tool_name in called_tools:
            raw_entry = checkpoint_tools.get(tool_name)
            try:
                if not isinstance(raw_entry, dict):
                    raise ValueError("checkpoint_entry_missing")
                entry = RegistryEntry.from_json(raw_entry)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"Actor follow-through checkpoint entry is invalid for "
                    f"{scenario!r} tool {tool_name!r}."
                ) from exc
            if entry.version != paired["versions"].get(tool_name):
                raise ValueError(
                    f"Actor follow-through tool version is unbound for "
                    f"{scenario!r} tool {tool_name!r}."
                )
            if native_action_tool_enabled(entry.tool):
                continue
            if _side_effect_followup_failures(
                conversation,
                helper_name=tool_name,
                required_original_tool_calls=tuple(
                    entry.tool.spec.required_original_tool_calls
                ),
                actual_tool_trace_events=trace_events,
            ):
                derived_failures.append((tool_name, entry.version))

        feedback = paired["feedback"]
        raw_recorded = feedback.get("actor_followthrough_failures")
        if (
            not isinstance(raw_recorded, list)
            or any(not isinstance(item, str) or not item for item in raw_recorded)
            or len(raw_recorded) != len(set(raw_recorded))
            or set(raw_recorded) != {name for name, _version in derived_failures}
        ):
            raise ValueError(
                f"Actor follow-through sidecar disagrees with raw trajectory "
                f"evidence for {scenario!r}."
            )
        family = _public_actor_followthrough_family(feedback)
        immediate_actions = feedback.get("immediate_actions")
        if not isinstance(immediate_actions, list) or any(
            not isinstance(item, dict) for item in immediate_actions
        ):
            raise ValueError(
                f"Actor follow-through immediate actions are malformed for "
                f"{scenario!r}."
            )
        lifecycle_rows = _checkpoint_lifecycle_rows(
            checkpoint_dir / "tool_lifecycle.json"
        )
        lifecycle_context = str(feedback.get("task_context_label") or "")
        for tool_name, tool_version in derived_failures:
            raw_entry = checkpoint_tools[tool_name]
            if family is None:
                expected_action = {
                    "tool_name": tool_name,
                    "decision": "parked",
                    "reason": "actor_followthrough_failure_without_public_family",
                    "scenario": lifecycle_context,
                    "source_tool_version": tool_version,
                }
                checkpoint_closed = raw_entry.get("retired") is True
                disposition = "global_retirement"
            else:
                expected_action = {
                    "tool_name": tool_name,
                    "decision": "needs_route_repair",
                    "repair_kind": "routing",
                    "reason": "generated_helper_followup_failure",
                    "scenario": lifecycle_context,
                    "routing_disposition": "family_suppression_active",
                    "target_task_family": family,
                    "source_tool_version": tool_version,
                }
                checkpoint_closed = raw_entry.get("retired") is True or (
                    "tool_lifecycle.json" in copied_files
                    and isinstance(lifecycle_rows, dict)
                    and _actor_followthrough_family_suppressed(
                        lifecycle_rows.get(tool_name),
                        family=family,
                        tool_version=tool_version,
                    )
                )
                disposition = (
                    "global_retirement"
                    if raw_entry.get("retired") is True
                    else "family_suppression"
                )
            matching_immediate = [
                action
                for action in immediate_actions
                if all(
                    action.get(key) == value for key, value in expected_action.items()
                )
            ]
            matching_journal_indices = [
                index
                for index, action in enumerate(action_journal)
                if index > last_consumed_action_index
                and index not in consumed_action_indices
                and all(
                    action.get(key) == value for key, value in expected_action.items()
                )
            ]
            matched_action_index = (
                matching_journal_indices[0] if matching_journal_indices else None
            )
            if matched_action_index is not None:
                consumed_action_indices.add(matched_action_index)
                last_consumed_action_index = matched_action_index
            if (
                len(matching_immediate) != 1
                or matched_action_index is None
                or not checkpoint_closed
            ):
                raise ValueError(
                    f"Actor follow-through failure was not closed immediately for "
                    f"{scenario!r} tool {tool_name!r} v{tool_version}."
                )
            obligations.append(
                {
                    "scenario_sha256": hashlib.sha256(
                        scenario.encode("utf-8")
                    ).hexdigest(),
                    "tool_name": tool_name,
                    "tool_version": tool_version,
                    "family_sha256": (
                        hashlib.sha256(family.encode("utf-8")).hexdigest()
                        if family is not None
                        else None
                    ),
                    "terminal_disposition": disposition,
                    "lifecycle_action_journal_index": matched_action_index,
                }
            )

    actor_action_indices = {
        index
        for index, action in enumerate(action_journal)
        if action.get("reason")
        in {
            "generated_helper_followup_failure",
            "actor_followthrough_failure_without_public_family",
        }
    }
    if actor_action_indices != consumed_action_indices:
        raise ValueError(
            "Actor follow-through lifecycle journal has extra, missing, or "
            "reordered actions."
        )

    final_checkpoint_dir = _final_registry_checkpoint_directory(
        candidate_dir,
        scenario_order=scenario_order,
    )
    final_manifest = _read_json(final_checkpoint_dir / "registry_manifest.json")
    final_tools = final_manifest.get("tools")
    final_lifecycle = _checkpoint_lifecycle_rows(
        final_checkpoint_dir / "tool_lifecycle.json"
    )
    if not isinstance(final_tools, dict):
        raise ValueError("Final actor follow-through registry checkpoint is malformed.")
    for obligation in obligations:
        tool_name = str(obligation["tool_name"])
        tool_version = int(obligation["tool_version"])
        final_entry = final_tools.get(tool_name)
        final_retired = bool(
            isinstance(final_entry, dict)
            and final_entry.get("version") == tool_version
            and final_entry.get("retired") is True
        )
        final_suppressed = False
        if obligation["terminal_disposition"] == "family_suppression":
            for paired in paired_rows:
                scenario_hash = hashlib.sha256(
                    str(paired["scenario"]).encode("utf-8")
                ).hexdigest()
                if scenario_hash != obligation["scenario_sha256"]:
                    continue
                family = _public_actor_followthrough_family(paired["feedback"])
                final_suppressed = bool(
                    isinstance(family, str)
                    and isinstance(final_entry, dict)
                    and final_entry.get("version") == tool_version
                    and final_entry.get("retired") is False
                    and isinstance(final_lifecycle, dict)
                    and _actor_followthrough_family_suppressed(
                        final_lifecycle.get(tool_name),
                        family=family,
                        tool_version=tool_version,
                    )
                )
                break
        terminal_supersession = None
        if not final_retired and not final_suppressed:
            terminal_supersession = _terminal_actor_followthrough_supersession(
                candidate_dir=candidate_dir,
                final_checkpoint_dir=final_checkpoint_dir,
                protocol_events=protocol_events,
                tool_name=tool_name,
                source_tool_version=tool_version,
                final_entry_payload=final_entry,
            )
        if not final_retired and not final_suppressed and not terminal_supersession:
            raise ValueError(
                f"Actor follow-through closure became stale by run end for "
                f"tool {tool_name!r} v{tool_version}."
            )
        obligation["terminal_disposition"] = (
            "global_retirement"
            if final_retired
            else "family_suppression"
            if final_suppressed
            else "validated_implementation_supersession"
        )
        obligation["terminal_supersession"] = terminal_supersession

    obligation_bytes = json.dumps(
        obligations,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "status": "pass",
        "derived_obligation_count": len(obligations),
        "closed_after_task_count": len(obligations),
        "closed_at_run_end_count": len(obligations),
        "validated_implementation_supersession_count": sum(
            obligation["terminal_disposition"]
            == "validated_implementation_supersession"
            for obligation in obligations
        ),
        "lifecycle_action_journal_indices": sorted(consumed_action_indices),
        "sidecar_reconciled_task_count": len(paired_rows),
        "raw_validation_values_reported": False,
        "obligation_identity_sha256": hashlib.sha256(obligation_bytes).hexdigest(),
    }


def _derive_lifecycle_repair_obligations(
    candidate_dir: Path,
    *,
    trajectory_evidence: dict[str, dict[str, tuple[str, ...]]] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Derive repair duties independently from paired lifecycle evidence."""

    paired_rows = _paired_lifecycle_evidence_rows(
        candidate_dir,
        trajectory_evidence=trajectory_evidence,
    )

    stats: dict[tuple[str, int], dict[str, dict[str, int]]] = {}
    for paired in paired_rows:
        feedback = paired["feedback"]
        selection = paired["selection"]
        selection_values = paired["selection_values"]
        selection_versions = paired["versions"]
        observed_tools = paired["observed_tools"]
        called = set(selection_values["generated_tools_called"])
        failed = set(selection_values["generated_tools_failed"])
        contract_failed = set(selection_values["generated_tool_contract_failures"])
        visible = set(selection_values["generated_tools_visible"])
        family = _public_lifecycle_family(feedback)
        for tool_name in observed_tools:
            version_stats = stats.setdefault(
                (tool_name, selection_versions[tool_name]), {}
            )
            family_stats = version_stats.setdefault(
                family,
                {
                    "visible": 0,
                    "called": 0,
                    "failed": 0,
                    "contract_failed": 0,
                    "sole_harmful": 0,
                    "sole_helpful": 0,
                },
            )
            family_stats["visible"] += int(tool_name in visible)
            family_stats["called"] += int(tool_name in called)
            family_stats["failed"] += int(tool_name in failed)
            family_stats["contract_failed"] += int(tool_name in contract_failed)
            attributable_route_delta = _strict_attributable_route_delta(
                paired,
                tool_name=tool_name,
            )
            if attributable_route_delta is not None:
                family_stats["sole_harmful"] += int(
                    attributable_route_delta <= LIFECYCLE_ROUTE_HARM_DELTA
                )
                family_stats["sole_helpful"] += int(
                    attributable_route_delta >= LIFECYCLE_ROUTE_HELP_DELTA
                )

    obligations: list[dict[str, Any]] = []
    for (tool_name, version), family_stats_by_name in sorted(stats.items()):
        # Runtime metadata repair replaces one registry version globally. Mirror
        # that boundary here: a version adopted anywhere must not be replaced or
        # retired merely because it was not selected in another visible family.
        globally_called = any(
            family_stats["called"] > 0 for family_stats in family_stats_by_name.values()
        )
        implementation_targets: dict[str, set[str]] = {}
        for family, family_stats in sorted(family_stats_by_name.items()):
            reasons: set[str] = set()
            if family_stats["contract_failed"] >= LIFECYCLE_CONTRACT_FAILURE_THRESHOLD:
                reasons.add("deterministic_public_contract_failure")
            if family_stats["failed"] >= LIFECYCLE_EXECUTION_FAILURE_THRESHOLD:
                reasons.add("repeated_generated_tool_execution_failure")
            if reasons:
                implementation_targets[family] = reasons
        if not implementation_targets:
            failed_families = sorted(
                family
                for family, family_stats in family_stats_by_name.items()
                if family_stats["failed"] > 0
            )
            if failed_families:
                target_family = (
                    failed_families[0]
                    if len(failed_families) == 1
                    else LIFECYCLE_CROSS_FAMILY_EXECUTION_FAILURE
                )
                implementation_targets[target_family] = {
                    "unresolved_generated_tool_execution_failure"
                }
        for family, reasons in sorted(implementation_targets.items()):
            obligations.append(
                {
                    "tool_name": tool_name,
                    "source_tool_version": version,
                    "repair_kind": "implementation",
                    "target_task_family": family,
                    "required_reason_codes": sorted(reasons),
                }
            )
        for family, family_stats in sorted(family_stats_by_name.items()):
            if (
                not globally_called
                and family_stats["visible"] >= LIFECYCLE_METADATA_VISIBLE_THRESHOLD
                and family_stats["called"] == 0
            ):
                obligations.append(
                    {
                        "tool_name": tool_name,
                        "source_tool_version": version,
                        "repair_kind": "metadata",
                        "target_task_family": family,
                        "required_reason_codes": [
                            "visible_repeatedly_without_adoption"
                        ],
                    }
                )
            if (
                family_stats["sole_harmful"] >= LIFECYCLE_ROUTE_HARMFUL_CALL_THRESHOLD
                and family_stats["sole_harmful"] > family_stats["sole_helpful"]
            ):
                obligations.append(
                    {
                        "tool_name": tool_name,
                        "source_tool_version": version,
                        "repair_kind": "routing",
                        "target_task_family": family,
                        "required_reason_codes": [
                            "repeated_sole_tool_family_regression"
                        ],
                    }
                )
    return tuple(obligations)


def _strict_attributable_route_delta(
    paired: dict[str, Any],
    *,
    tool_name: str,
) -> float | None:
    """Return a route delta only at the runtime's strict attribution boundary."""

    feedback = paired["feedback"]
    selection = paired["selection"]
    selection_values = paired["selection_values"]
    called = set(selection_values["generated_tools_called"])
    attempted = set(selection_values["generated_tools_attempted"])
    failed = set(selection_values["generated_tools_failed"])
    all_attempted = called | attempted | failed
    control_outcome = feedback.get("control_outcome")
    candidate_outcome = feedback.get("candidate_outcome")
    outcome_delta = feedback.get("outcome_delta")
    if not (
        tool_name in called
        and all_attempted == {tool_name}
        and feedback.get("source_task_id_redacted") is True
        and feedback.get("control_source") == "same_run_fresh"
        and feedback.get("control_outcome_source") == "audited_outcome"
        and feedback.get("candidate_outcome_source") == "audited_outcome"
        and "exception_type" in selection
        and selection["exception_type"] is None
        and isinstance(control_outcome, (int, float))
        and not isinstance(control_outcome, bool)
        and isinstance(candidate_outcome, (int, float))
        and not isinstance(candidate_outcome, bool)
        and isinstance(outcome_delta, (int, float))
        and not isinstance(outcome_delta, bool)
        and math.isfinite(float(control_outcome))
        and math.isfinite(float(candidate_outcome))
        and math.isfinite(float(outcome_delta))
        and float(outcome_delta) == float(candidate_outcome) - float(control_outcome)
    ):
        return None
    return float(outcome_delta)


def _derived_attributable_harm_retirements(
    paired_rows: tuple[dict[str, Any], ...],
) -> dict[tuple[str, int], dict[str, Any]]:
    """Derive the exact point where strictly attributable harm requires retirement."""

    family_stats_by_tool: dict[tuple[str, int], dict[str, dict[str, int]]] = {}
    expected: dict[tuple[str, int], dict[str, Any]] = {}
    for row_number, paired in enumerate(paired_rows, start=1):
        feedback = paired["feedback"]
        completed_count = feedback.get("completed_count")
        family = _public_lifecycle_family(feedback)
        observed_keys = {
            (tool_name, paired["versions"][tool_name])
            for tool_name in paired["observed_tools"]
        }
        for key in sorted(observed_keys):
            existing = expected.get(key)
            if existing is not None and row_number > existing["trigger_row_number"]:
                existing["observed_after_trigger"].append(paired["scenario"])
            tool_name, _version = key
            family_stats = family_stats_by_tool.setdefault(key, {}).setdefault(
                family,
                {
                    "attributable_harmful_call_count": 0,
                    "attributable_helpful_call_count": 0,
                },
            )
            delta = _strict_attributable_route_delta(
                paired,
                tool_name=tool_name,
            )
            if delta is None:
                continue
            family_stats["attributable_harmful_call_count"] += int(
                delta <= LIFECYCLE_ROUTE_HARM_DELTA
            )
            family_stats["attributable_helpful_call_count"] += int(
                delta >= LIFECYCLE_ROUTE_HELP_DELTA
            )

        for key in sorted(observed_keys):
            if key in expected:
                continue
            tool_family_stats = family_stats_by_tool[key]
            qualifying_families = sorted(
                family_name
                for family_name, counts in tool_family_stats.items()
                if counts["attributable_harmful_call_count"]
                >= LIFECYCLE_ROUTE_HARMFUL_CALL_THRESHOLD
                and counts["attributable_harmful_call_count"]
                > counts["attributable_helpful_call_count"]
            )
            total_helpful = sum(
                counts["attributable_helpful_call_count"]
                for counts in tool_family_stats.values()
            )
            if not qualifying_families or total_helpful:
                continue
            task_context_label = feedback.get("task_context_label")
            if (
                isinstance(completed_count, bool)
                or not isinstance(completed_count, int)
                or completed_count != row_number
                or not isinstance(task_context_label, str)
                or not task_context_label.strip()
            ):
                # This cannot be a runtime-produced public retirement boundary.
                # Leave it to the ordinary route-suppression obligation; any
                # forged retirement event will then be rejected as unexpected.
                continue
            tool_name, version = key
            action = {
                "tool_name": tool_name,
                "decision": "parked",
                "reason": LIFECYCLE_GLOBAL_RETIREMENT_REASON,
                "scenario": task_context_label.strip(),
                "source_tool_version": version,
            }
            expected[key] = {
                "action": action,
                "trigger_completed_count": completed_count,
                "trigger_row_number": row_number,
                "qualifying_families": qualifying_families,
                "family_evidence": {
                    family_name: dict(counts)
                    for family_name, counts in sorted(tool_family_stats.items())
                },
                "observed_after_trigger": [],
            }
    return expected


def _verify_attributable_harm_retirements(
    candidate_dir: Path,
    registry_dir: Path,
    *,
    paired_rows: tuple[dict[str, Any], ...],
) -> tuple[set[tuple[str, int]], dict[str, int]]:
    """Verify repeated-harm retirement from raw evidence through terminal state."""

    expected = _derived_attributable_harm_retirements(paired_rows)
    ordered_expected = sorted(
        expected.items(),
        key=lambda item: (
            item[1]["trigger_completed_count"],
            item[0][0],
            item[0][1],
        ),
    )
    expected_actions = [details["action"] for _key, details in ordered_expected]
    action_journal = _read_jsonl_objects(
        candidate_dir / "self_evolution_tool_lifecycle.jsonl"
    )
    recorded_actions = [
        action
        for action in action_journal
        if action.get("reason") == LIFECYCLE_GLOBAL_RETIREMENT_REASON
    ]
    if recorded_actions != expected_actions:
        raise ValueError(
            "Repeated-harm global-retirement journal disagrees with independently "
            "derived strictly attributable evidence."
        )

    expected_sidecar_actions = [
        (details["trigger_row_number"], details["action"])
        for _key, details in ordered_expected
    ]
    recorded_sidecar_actions: list[tuple[int, dict[str, Any]]] = []
    for row_number, paired in enumerate(paired_rows, start=1):
        immediate_actions = paired["feedback"].get("immediate_actions", [])
        if not isinstance(immediate_actions, list) or any(
            not isinstance(action, dict) for action in immediate_actions
        ):
            raise ValueError(
                "Lifecycle feedback has malformed immediate-action evidence."
            )
        recorded_sidecar_actions.extend(
            (row_number, action)
            for action in immediate_actions
            if action.get("reason") == LIFECYCLE_GLOBAL_RETIREMENT_REASON
        )
    if recorded_sidecar_actions != expected_sidecar_actions:
        raise ValueError(
            "Repeated-harm global retirement is not bound to its exact triggering "
            "task feedback row."
        )

    registry = _read_json(registry_dir / "registry_manifest.json")
    registry_tools = registry.get("tools")
    if not isinstance(registry_tools, dict):
        raise ValueError("Final registry manifest has no tool mapping.")
    lifecycle_path = registry_dir / "tool_lifecycle.json"
    lifecycle_rows: dict[str, Any] = {}
    if expected:
        if not lifecycle_path.is_file():
            raise ValueError(
                "Repeated-harm global retirement has no durable lifecycle state."
            )
        lifecycle_payload = _read_json(lifecycle_path)
        raw_rows = lifecycle_payload.get("tool_lifecycle")
        if not isinstance(raw_rows, dict):
            raise ValueError(
                "Repeated-harm global retirement has malformed durable lifecycle state."
            )
        lifecycle_rows = raw_rows

    verified: set[tuple[str, int]] = set()
    for key, details in ordered_expected:
        tool_name, version = key
        if details["observed_after_trigger"]:
            raise ValueError(
                "A globally retired generated tool remained visible or callable "
                f"after retirement: {tool_name}:v{version}."
            )
        entry = registry_tools.get(tool_name)
        exact_retired_source = bool(
            isinstance(entry, dict)
            and entry.get("version") == version
            and entry.get("retired") is True
        )
        if not exact_retired_source:
            # A newer, independently repaired version may validly supersede the
            # retired source.  It must close the obligation through the ordinary
            # acknowledged-repair path below, never through this retirement path.
            if (
                not isinstance(entry, dict)
                or isinstance(entry.get("version"), bool)
                or not isinstance(entry.get("version"), int)
                or entry["version"] <= version
            ):
                raise ValueError(
                    "Repeated-harm global-retirement action disagrees with the "
                    f"terminal registry state: {tool_name}:v{version}."
                )
            continue

        lifecycle_row = lifecycle_rows.get(tool_name)
        if not (
            isinstance(lifecycle_row, dict)
            and lifecycle_row.get("tool_version") == version
            and lifecycle_row.get("decision") == "parked"
            and lifecycle_row.get("decision_reason") == "retired_this_run"
            and lifecycle_row.get("repair_kind") is None
            and lifecycle_row.get("routing_disposition") == "quarantined"
        ):
            raise ValueError(
                "Repeated-harm global retirement has no exact terminal lifecycle "
                f"state: {tool_name}:v{version}."
            )
        family_evidence = lifecycle_row.get("family_evidence")
        expected_family_evidence = details["family_evidence"]
        if not isinstance(family_evidence, dict) or set(family_evidence) != set(
            expected_family_evidence
        ):
            raise ValueError(
                "Repeated-harm retirement family evidence disagrees with raw "
                f"paired rows: {tool_name}:v{version}."
            )
        for family, expected_counts in expected_family_evidence.items():
            recorded_counts = family_evidence.get(family)
            if not isinstance(recorded_counts, dict) or any(
                recorded_counts.get(field) != expected_count
                for field, expected_count in expected_counts.items()
            ):
                raise ValueError(
                    "Repeated-harm retirement counts disagree with raw paired "
                    f"rows: {tool_name}:v{version}:{family}."
                )
        route_families = {
            str(item)
            for item in (lifecycle_row.get("route_repair_families") or [])
            if isinstance(item, str)
        }
        reason_codes = lifecycle_row.get("route_repair_reason_codes")
        if any(
            family not in route_families
            or not isinstance(reason_codes, dict)
            or "repeated_sole_tool_family_regression"
            not in (reason_codes.get(family) or [])
            for family in details["qualifying_families"]
        ):
            raise ValueError(
                "Repeated-harm global retirement lacks its exact durable routing "
                f"evidence: {tool_name}:v{version}."
            )
        verified.add(key)

    return verified, {
        "derived_global_retirement_count": len(expected),
        "verified_global_retirement_count": len(verified),
    }


def _optional_lifecycle_metric(value: Any, *, label: str) -> float | None:
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise ValueError(f"Promoted canary has malformed {label} evidence.")
    return float(value)


def _positive_lifecycle_count(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Promoted canary has malformed {label} boundary.")
    return cast(int, value)


def _verify_promoted_canary_evidence(
    paired_rows: tuple[dict[str, Any], ...],
    *,
    request: dict[str, Any],
    canary_pending: dict[str, Any],
    promoted: dict[str, Any],
) -> dict[str, int]:
    """Recompute the prospective promotion gate from per-task evidence."""

    request_id = str(request.get("request_id") or "")
    tool_name = str(request.get("tool_name") or "")
    version = promoted.get("new_version")
    target_family = str(request.get("target_task_family") or "").strip().lower()
    if (
        not target_family
        or len(target_family) > 128
        or re.fullmatch(r"[a-z0-9_.:-]+", target_family) is None
    ):
        raise ValueError(
            f"Promoted canary {request_id!r} has no valid public target family."
        )
    if (
        canary_pending.get("new_version") != version
        or canary_pending.get("tool_name") != tool_name
        or promoted.get("tool_name") != tool_name
        or isinstance(request.get("source_tool_version"), bool)
        or not isinstance(request.get("source_tool_version"), int)
        or version != request["source_tool_version"] + 1
    ):
        raise ValueError(
            f"Promoted canary {request_id!r} changes tool or version during canary."
        )
    pending_after = _positive_lifecycle_count(
        canary_pending.get("acknowledged_after_completed_count"),
        label="canary-pending acknowledgement",
    )
    eligible_from = _positive_lifecycle_count(
        canary_pending.get("eligible_from_completed_count"),
        label="prospective eligibility",
    )
    promoted_after = _positive_lifecycle_count(
        promoted.get("acknowledged_after_completed_count"),
        label="promotion acknowledgement",
    )
    if (
        eligible_from != pending_after + 1
        or promoted_after < eligible_from
        or pending_after > len(paired_rows)
        or promoted_after > len(paired_rows)
    ):
        raise ValueError(
            f"Promoted canary {request_id!r} has an invalid prospective window."
        )

    eligible_call_count = 0
    attributable_observation_count = 0
    exact_outcome_count = 0
    regression_count = 0
    fresh_control_success_flip_count = 0
    previous_completed_count = 0
    for paired in paired_rows:
        feedback = paired["feedback"]
        selection = paired["selection"]
        scenario = paired["scenario"]
        completed_count = feedback.get("completed_count")
        if (
            isinstance(completed_count, bool)
            or not isinstance(completed_count, int)
            or completed_count != previous_completed_count + 1
        ):
            raise ValueError(
                "Promoted canary evidence has malformed reflection task ordering."
            )
        previous_completed_count = completed_count
        if not eligible_from <= completed_count <= promoted_after:
            continue

        selection_values = paired["selection_values"]
        versions = paired["versions"]
        failed = set(selection_values["generated_tools_failed"])
        contract_failed = set(selection_values["generated_tool_contract_failures"])
        if versions.get(tool_name) == version and (
            tool_name in failed or tool_name in contract_failed
        ):
            raise ValueError(
                f"Promoted canary {request_id!r} has a generated-tool hard failure."
            )

        all_called = set(selection_values["generated_tools_called"]) | failed
        if (
            _public_lifecycle_family(feedback) != target_family
            or all_called != {tool_name}
            or versions.get(tool_name) != version
        ):
            continue
        eligible_call_count += 1

        if "exception_type" not in selection or not (
            selection["exception_type"] is None
            or isinstance(selection["exception_type"], str)
        ):
            raise ValueError(
                f"Promoted canary evidence for {scenario!r} has no valid exception "
                "provenance."
            )
        if selection["exception_type"] is not None:
            continue
        if (
            feedback.get("control_source") != "same_run_fresh"
            or feedback.get("control_outcome_source") != "audited_outcome"
            or feedback.get("candidate_outcome_source") != "audited_outcome"
        ):
            continue
        control_outcome = _optional_lifecycle_metric(
            feedback.get("control_outcome"),
            label=f"control outcome for {scenario!r}",
        )
        candidate_outcome = _optional_lifecycle_metric(
            feedback.get("candidate_outcome"),
            label=f"candidate outcome for {scenario!r}",
        )
        outcome_delta = _optional_lifecycle_metric(
            feedback.get("outcome_delta"),
            label=f"outcome delta for {scenario!r}",
        )
        selection_outcome = _optional_lifecycle_metric(
            selection.get("outcome_similarity"),
            label=f"selection outcome for {scenario!r}",
        )
        if (
            control_outcome is None
            or candidate_outcome is None
            or outcome_delta is None
            or selection_outcome != candidate_outcome
            or outcome_delta != candidate_outcome - control_outcome
        ):
            continue
        attributable_observation_count += 1
        exact_success = candidate_outcome == 1.0
        success_flip = bool(
            exact_success and control_outcome < 1.0 and outcome_delta > 0.0
        )
        if not isinstance(feedback.get("candidate_success_flip"), bool) or (
            feedback["candidate_success_flip"] is not success_flip
        ):
            raise ValueError(
                f"Promoted canary success-flip evidence disagrees for {scenario!r}."
            )
        exact_outcome_count += int(exact_success)
        regression_count += int(outcome_delta < 0.0)
        fresh_control_success_flip_count += int(success_flip)

    counts = {
        "eligible_call_count": eligible_call_count,
        "attributable_observation_count": attributable_observation_count,
        "exact_outcome_count": exact_outcome_count,
        "regression_count": regression_count,
        "fresh_control_success_flip_count": fresh_control_success_flip_count,
    }
    if (
        eligible_call_count < LIFECYCLE_CANARY_ATTRIBUTABLE_OBSERVATION_MINIMUM
        or attributable_observation_count
        < LIFECYCLE_CANARY_ATTRIBUTABLE_OBSERVATION_MINIMUM
        or exact_outcome_count < LIFECYCLE_CANARY_EXACT_OUTCOME_MINIMUM
        or regression_count != 0
        or fresh_control_success_flip_count
        < LIFECYCLE_CANARY_FRESH_CONTROL_SUCCESS_FLIP_MINIMUM
    ):
        raise ValueError(
            f"Promoted canary {request_id!r} lacks independently verified evidence: "
            f"{counts!r}."
        )
    return counts


def _verify_lifecycle_closed(
    candidate_dir: Path,
    registry_dir: Path,
    *,
    trajectory_evidence: dict[str, dict[str, tuple[str, ...]]] | None = None,
    protocol_events: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    """Require every repair request to have a safe terminal run disposition."""

    repair_candidate_artifacts = _verified_repair_candidate_artifacts(
        candidate_dir,
        protocol_events,
    )
    paired_rows = _paired_lifecycle_evidence_rows(
        candidate_dir,
        trajectory_evidence=trajectory_evidence,
    )
    obligations = _derive_lifecycle_repair_obligations(
        candidate_dir,
        trajectory_evidence=trajectory_evidence,
    )
    (
        verified_global_retirements,
        global_retirement_report,
    ) = _verify_attributable_harm_retirements(
        candidate_dir,
        registry_dir,
        paired_rows=paired_rows,
    )
    requests = _read_jsonl_objects(
        candidate_dir / "self_evolution_tool_repair_requests.jsonl"
    )
    acknowledgements = _read_jsonl_objects(
        candidate_dir / "self_evolution_tool_repair_acknowledgements.jsonl"
    )
    state_path = candidate_dir / "post_deployment_repair_state.json"
    if not state_path.is_file():
        raise ValueError("Completed SAGE run is missing lifecycle repair state.")
    state = _read_json(state_path)
    if state.get("schema_version") != 1:
        raise ValueError("Completed SAGE run has an invalid lifecycle state schema.")
    pending = state.get("pending_repair_requests")
    canaries = state.get("canary_state_by_tool")
    transactions = state.get("repair_transactions_by_tool", {})
    handled = state.get("handled_repair_request_ids")
    if not isinstance(pending, list) or pending:
        raise ValueError("Completed SAGE run has pending lifecycle repair requests.")
    if not isinstance(canaries, dict) or canaries:
        raise ValueError("Completed SAGE run has open repaired-tool canaries.")
    if not isinstance(transactions, dict) or transactions:
        raise ValueError("Completed SAGE run has open lifecycle repair transactions.")
    if not isinstance(handled, list) or any(
        not isinstance(request_id, str) or not request_id for request_id in handled
    ):
        raise ValueError("Completed SAGE run has invalid handled lifecycle state.")

    request_by_id: dict[str, dict[str, Any]] = {}
    for row in requests:
        request_id = str(row.get("request_id") or "")
        tool_name = str(row.get("tool_name") or "")
        source_version = row.get("source_tool_version")
        prohibited_paths = prohibited_repair_payload_paths(row)
        if prohibited_paths:
            raise ValueError(
                "Completed SAGE run has evaluator-private evidence in lifecycle "
                f"request {request_id!r}: {list(prohibited_paths)!r}."
            )
        if (
            not request_id
            or request_id in request_by_id
            or not tool_name
            or row.get("schema_version") != 1
            or isinstance(source_version, bool)
            or not isinstance(source_version, int)
            or source_version < 1
            or row.get("future_tasks_only") is not True
            or row.get("triggering_task_replay_allowed") is not False
        ):
            raise ValueError("Completed SAGE run has a malformed lifecycle request.")
        if row.get("repair_kind") == "metadata" and (
            not isinstance(row.get("source_code_hash"), str)
            or _SHA256_HEX_PATTERN.fullmatch(row["source_code_hash"]) is None
        ):
            raise ValueError(
                "Completed SAGE run has a metadata repair without a valid source "
                "implementation hash."
            )
        request_by_id[request_id] = row
    acknowledgements_by_request: dict[str, list[dict[str, Any]]] = {}
    final_ack_by_request: dict[str, dict[str, Any]] = {}
    allowed_acknowledgement_statuses = {
        "validation_failed",
        "canary_pending",
        "promoted",
        "rejected",
        "rolled_back",
    }
    for row in acknowledgements:
        request_id = str(row.get("request_id") or "")
        tool_name = str(row.get("tool_name") or "")
        version = row.get("new_version")
        if (
            not request_id
            or not tool_name
            or row.get("schema_version") != 1
            or isinstance(version, bool)
            or not isinstance(version, int)
            or version < 1
            or row.get("status") not in allowed_acknowledgement_statuses
            or row.get("future_tasks_only") is not True
            or row.get("triggering_task_replay_allowed") is not False
        ):
            raise ValueError(
                "Completed SAGE run has a malformed lifecycle acknowledgement."
            )
        request = request_by_id.get(request_id)
        if isinstance(request, dict) and request.get("repair_kind") == "metadata":
            _verify_metadata_implementation_proof(
                request=request,
                acknowledgement=row,
            )
        acknowledgements_by_request.setdefault(request_id, []).append(row)
        final_ack_by_request[request_id] = row
    request_ids = set(request_by_id)
    unacknowledged = sorted(request_ids - set(final_ack_by_request))
    if unacknowledged:
        raise ValueError(
            "Completed SAGE run has unacknowledged lifecycle repair requests: "
            f"{unacknowledged!r}."
        )
    terminal_statuses = {"promoted", "rejected", "rolled_back"}
    orphaned_acknowledgements = sorted(set(final_ack_by_request) - request_ids)
    if orphaned_acknowledgements:
        raise ValueError(
            "Completed SAGE run has lifecycle acknowledgements without requests: "
            f"{orphaned_acknowledgements!r}."
        )
    mismatched_tools = sorted(
        request_id
        for request_id, request_acknowledgements in acknowledgements_by_request.items()
        if request_id in request_by_id
        and any(
            acknowledgement.get("tool_name")
            != request_by_id[request_id].get("tool_name")
            for acknowledgement in request_acknowledgements
        )
    )
    if mismatched_tools:
        raise ValueError(
            "Completed SAGE run has lifecycle acknowledgements for the wrong tool: "
            f"{mismatched_tools!r}."
        )
    nonterminal = sorted(
        request_id
        for request_id in final_ack_by_request
        if str(final_ack_by_request[request_id].get("status") or "")
        not in terminal_statuses
    )
    if nonterminal:
        raise ValueError(
            "Completed SAGE run has nonterminal lifecycle acknowledgements: "
            f"{nonterminal!r}."
        )

    verified_promoted_canaries: dict[str, dict[str, int]] = {}
    for request_id, request_acknowledgements in acknowledgements_by_request.items():
        acknowledgement_statuses = [
            str(row.get("status") or "") for row in request_acknowledgements
        ]
        if "promoted" not in acknowledgement_statuses:
            continue
        if acknowledgement_statuses != ["canary_pending", "promoted"]:
            raise ValueError(
                "Completed SAGE run has a promoted lifecycle repair without the "
                "ordered canary_pending -> promoted transition: "
                f"{request_id!r}:{acknowledgement_statuses!r}."
            )
        verified_promoted_canaries[request_id] = _verify_promoted_canary_evidence(
            paired_rows,
            request=request_by_id[request_id],
            canary_pending=request_acknowledgements[0],
            promoted=request_acknowledgements[1],
        )
    unhandled = sorted(request_ids - set(handled))
    if unhandled:
        raise ValueError(
            "Completed SAGE run has terminal lifecycle requests missing from state: "
            f"{unhandled!r}."
        )

    missing_obligations: list[str] = []
    lifecycle_routing_path = registry_dir / "tool_lifecycle.json"
    lifecycle_routing_rows: dict[str, Any] = {}
    if any(item["repair_kind"] == "routing" for item in obligations):
        if not lifecycle_routing_path.is_file():
            raise ValueError(
                "Completed SAGE run has routing-repair obligations but no durable "
                "lifecycle routing state."
            )
        lifecycle_routing_payload = _read_json(lifecycle_routing_path)
        raw_lifecycle_rows = lifecycle_routing_payload.get("tool_lifecycle")
        if not isinstance(raw_lifecycle_rows, dict):
            raise ValueError(
                "Completed SAGE run has malformed durable lifecycle routing state."
            )
        lifecycle_routing_rows = raw_lifecycle_rows
    verified_route_repair_count = 0
    for obligation in obligations:
        if obligation["repair_kind"] == "routing":
            lifecycle_row = lifecycle_routing_rows.get(obligation["tool_name"])
            route_applied = bool(
                isinstance(lifecycle_row, dict)
                and lifecycle_row.get("tool_version")
                == obligation["source_tool_version"]
                and lifecycle_row.get("repair_kind") == "routing"
                and lifecycle_row.get("routing_disposition")
                == "family_suppression_active"
                and lifecycle_row.get("decision")
                in {"needs_route_repair", "retain_with_route_repair"}
                and obligation["target_task_family"]
                in {
                    str(item)
                    for item in (lifecycle_row.get("route_repair_families") or [])
                    if isinstance(item, str)
                }
            )
            superseded_by_terminal_repair = any(
                request.get("tool_name") == obligation["tool_name"]
                and request.get("source_tool_version")
                == obligation["source_tool_version"]
                and request.get("repair_kind") == "implementation"
                and str(request.get("request_id") or "") in final_ack_by_request
                and str(
                    final_ack_by_request[str(request.get("request_id") or "")].get(
                        "status"
                    )
                    or ""
                )
                in terminal_statuses
                for request in requests
            )
            globally_retired = (
                obligation["tool_name"],
                obligation["source_tool_version"],
            ) in verified_global_retirements
            if route_applied or superseded_by_terminal_repair or globally_retired:
                verified_route_repair_count += 1
                continue
            missing_obligations.append(
                f"routing:{obligation['tool_name']}:"
                f"v{obligation['source_tool_version']}:"
                f"{obligation['target_task_family']}"
            )
            continue
        required_reasons = set(obligation["required_reason_codes"])
        matching_requests = [
            row
            for row in requests
            if row.get("tool_name") == obligation["tool_name"]
            and row.get("source_tool_version") == obligation["source_tool_version"]
            and row.get("repair_kind") == obligation["repair_kind"]
            and row.get("target_task_family") == obligation["target_task_family"]
            and required_reasons.issubset(
                {
                    str(reason)
                    for reason in (row.get("trigger_reason_codes") or [])
                    if isinstance(reason, str)
                }
            )
        ]
        if not matching_requests or not any(
            str(row.get("request_id") or "") in final_ack_by_request
            and str(
                final_ack_by_request[str(row.get("request_id") or "")].get("status")
                or ""
            )
            in terminal_statuses
            for row in matching_requests
        ):
            missing_obligations.append(
                f"{obligation['repair_kind']}:{obligation['tool_name']}:"
                f"v{obligation['source_tool_version']}:"
                f"{obligation['target_task_family']}"
            )
    if missing_obligations:
        raise ValueError(
            "Completed SAGE run did not terminally repair or retire all derived "
            f"lifecycle obligations: {sorted(missing_obligations)!r}."
        )

    registry = _read_json(registry_dir / "registry_manifest.json")
    registry_tools = registry.get("tools")
    if not isinstance(registry_tools, dict):
        raise ValueError("Final registry manifest has no tool mapping.")
    active_unresolved: list[str] = []
    promoted_versions: set[tuple[str, int]] = set()
    for request_id in sorted(final_ack_by_request):
        acknowledgement = final_ack_by_request[request_id]
        status = str(acknowledgement.get("status") or "")
        tool_name = str(acknowledgement.get("tool_name") or "")
        version = acknowledgement.get("new_version")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError(
                "Completed SAGE run has a malformed lifecycle acknowledgement version."
            )
        entry = registry_tools.get(tool_name)
        request = request_by_id[request_id]
        proof = acknowledgement.get("implementation_proof")
        if (
            request.get("repair_kind") == "metadata"
            and isinstance(proof, dict)
            and proof.get("replacement_activated") is True
            and isinstance(entry, dict)
            and entry.get("version") == version
            and entry.get("code_hash") != proof.get("replacement_code_hash")
        ):
            raise ValueError(
                "Completed SAGE run registry code hash disagrees with metadata "
                f"repair proof: {tool_name}:v{version}:{request_id}."
            )
        if status == "promoted" and (
            not isinstance(entry, dict)
            or isinstance(entry.get("version"), bool)
            or not isinstance(entry.get("version"), int)
            or entry["version"] < version
        ):
            raise ValueError(
                "Completed SAGE run has no registry version for promoted tool: "
                f"{tool_name}:v{version}:{request_id}."
            )
        if (
            status == "promoted"
            and isinstance(entry, dict)
            and entry.get("version") == version
            and entry.get("retired") is not False
        ):
            raise ValueError(
                "Completed SAGE run marks a current promoted tool as retired: "
                f"{tool_name}:v{version}:{request_id}."
            )
        if status == "promoted":
            promoted_versions.add((tool_name, version))
            continue
        if (
            isinstance(entry, dict)
            and entry.get("version") == version
            and entry.get("retired") is not True
        ):
            active_unresolved.append(f"{tool_name}:v{version}:{request_id}")
    if active_unresolved:
        raise ValueError(
            "Completed SAGE run leaves unresolved affected tools active: "
            f"{active_unresolved!r}."
        )
    active_repairs_without_promotion = sorted(
        f"{tool_name}:v{entry.get('version')}"
        for tool_name, entry in registry_tools.items()
        if isinstance(tool_name, str)
        and isinstance(entry, dict)
        # Registry loading treats every value other than literal ``true`` as
        # active.  Verification must use the same fail-closed interpretation;
        # otherwise a malformed repair entry with no ``retired`` field could
        # remain callable without a matching promotion acknowledgement.
        and entry.get("retired") is not True
        and str(entry.get("birth_scenario") or "").startswith("post_deployment_repair:")
        and (tool_name, entry.get("version")) not in promoted_versions
    )
    if active_repairs_without_promotion:
        raise ValueError(
            "Completed SAGE run has active post-deployment repair versions without "
            "matching promoted acknowledgements: "
            f"{active_repairs_without_promotion!r}."
        )
    return {
        "repair_request_count": len(requests),
        "repair_acknowledgement_count": len(acknowledgements),
        "derived_repair_obligation_count": len(obligations),
        "verified_promoted_canary_count": len(verified_promoted_canaries),
        "verified_route_repair_count": verified_route_repair_count,
        **global_retirement_report,
        "pending_repair_request_count": 0,
        "open_canary_count": 0,
        "open_repair_transaction_count": 0,
        "active_unresolved_tool_count": 0,
        "repair_candidate_artifacts": repair_candidate_artifacts,
    }


def _verify_empty_online_registry_start(
    run_root: Path,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    """Require an online publication arm to start without registry sidecars."""

    snapshot = protocol.get("registry_gate_snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("Online publication run has no pre-run registry snapshot.")
    snapshot_path = run_root / "registry_gate" / "registry_gate_snapshot.json"
    if _read_json(snapshot_path) != snapshot:
        raise ValueError(
            "Online publication pre-run registry snapshot differs from its artifact."
        )
    required: dict[str, object] = {
        "manifest_existed_before_run": False,
        "snapshot_path": None,
        "manifest_digest_before_run": None,
        "registry_directory_existed_before_run": False,
        "registry_inventory_before_run": [],
        "registry_inventory_count_before_run": 0,
        "registry_inventory_sha256": hashlib.sha256(b"[]").hexdigest(),
    }
    for field, expected in required.items():
        if snapshot.get(field) != expected:
            raise ValueError(
                "Online publication registry did not start exactly empty: "
                f"{field}={snapshot.get(field)!r}, expected {expected!r}."
            )
    return snapshot


def _registry_inventory_for_verification(registry_dir: Path) -> list[dict[str, Any]]:
    """Independently hash every object in an immutable frozen registry."""

    if not registry_dir.is_dir() or registry_dir.is_symlink():
        raise ValueError("Frozen publication registry is not a regular directory.")
    inventory: list[dict[str, Any]] = []
    for path in sorted(registry_dir.rglob("*")):
        relative_path = path.relative_to(registry_dir).as_posix()
        if path.is_symlink():
            inventory.append(
                {
                    "path": relative_path,
                    "kind": "symlink",
                    "target": os.readlink(path),
                }
            )
        elif path.is_dir():
            inventory.append({"path": relative_path, "kind": "directory"})
        elif path.is_file():
            inventory.append(
                {
                    "path": relative_path,
                    "kind": "file",
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
        else:
            inventory.append({"path": relative_path, "kind": "other"})
    return inventory


def _verify_frozen_registry_immutable(
    run_root: Path,
    protocol: dict[str, Any],
    registry_dir: Path,
) -> dict[str, Any]:
    """Prove generation-off reuse did not alter its installed registry."""

    snapshot = protocol.get("registry_gate_snapshot")
    snapshot_path = run_root / "registry_gate" / "registry_gate_snapshot.json"
    if not isinstance(snapshot, dict) or _read_json(snapshot_path) != snapshot:
        raise ValueError("Frozen publication registry snapshot is missing or changed.")
    before = snapshot.get("registry_inventory_before_run")
    before_count = snapshot.get("registry_inventory_count_before_run")
    before_sha256 = snapshot.get("registry_inventory_sha256")
    if (
        not isinstance(before, list)
        or isinstance(before_count, bool)
        or not isinstance(before_count, int)
        or before_count != len(before)
        or not isinstance(before_sha256, str)
        or _SHA256_HEX_PATTERN.fullmatch(before_sha256) is None
    ):
        raise ValueError("Frozen publication registry snapshot inventory is invalid.")
    canonical_before = json.dumps(
        before,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if hashlib.sha256(canonical_before).hexdigest() != before_sha256:
        raise ValueError(
            "Frozen publication pre-run registry inventory hash is invalid."
        )
    after = _registry_inventory_for_verification(registry_dir)
    if before != after:
        raise ValueError("Frozen publication registry changed during execution.")
    if protocol.get("registry_gate_restore") is not None:
        raise ValueError("Frozen publication run unexpectedly restored its registry.")
    return {
        "status": "pass",
        "inventory_count": len(after),
        "inventory_sha256": before_sha256,
    }


def _verify_no_scenario_transform_failures(candidate_dir: Path) -> None:
    """Reject a strict run that ever fell back after transformation failed."""

    failure_path = candidate_dir / "scenario_transform_failures.jsonl"
    if _read_jsonl_objects(failure_path):
        raise ValueError(
            "Candidate run contains scenario transformation failures; strict runs "
            "must abort instead of falling back to the base scenario."
        )


def _verify_matched_policy_runtimes(
    control_dir: Path,
    candidate_dir: Path,
) -> dict[str, Any]:
    """Bind both arms to the same policy actor implementation.

    The control is intentionally not ToolSandbox's upstream actor. It is the
    same SAGE policy wrapper used by the candidate, with generated tools absent.
    That matched actor runtime isolates the generated-tool lifecycle treatment.
    """

    manifests: dict[str, dict[str, Any]] = {}
    for arm, run_dir in (("control", control_dir), ("candidate", candidate_dir)):
        manifest = _read_json(run_dir / "sage_ts_run_manifest.json")
        if manifest.get("agent_runtime") != SAGE_WRAPPED_AGENT_RUNTIME:
            raise ValueError(
                f"Publication {arm} arm did not use the matched SAGE policy wrapper."
            )
        if manifest.get("actor_selection_mode") != "policy":
            raise ValueError(
                f"Publication {arm} arm did not record policy actor selection."
            )
        manifests[arm] = manifest
    return {
        "control_condition": MATCHED_CONTROL_CONDITION,
        "control_agent_runtime": manifests["control"]["agent_runtime"],
        "candidate_agent_runtime": manifests["candidate"]["agent_runtime"],
        "actor_selection_mode": "policy",
    }


def _verify_parallel_arm_execution(
    run_root: Path,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    record = protocol.get("parallel_arm_execution")
    if not isinstance(record, dict):
        raise ValueError("Protocol has no parallel child-process execution evidence.")
    if (
        record.get("unit") != "isolated_child_process"
        or record.get("positive_overlap_asserted") is not True
    ):
        raise ValueError("Parallel execution evidence has invalid process metadata.")
    recorded_arms = record.get("arms")
    if not isinstance(recorded_arms, dict):
        raise ValueError("Parallel execution evidence has no arm records.")
    intervals: dict[str, tuple[int, int]] = {}
    pids: set[int] = set()
    fields = (
        "status",
        "process_pid",
        "started_at",
        "completed_at",
        "started_monotonic_ns",
        "completed_monotonic_ns",
    )
    for arm in ("control", "candidate"):
        arm_record = recorded_arms.get(arm)
        if not isinstance(arm_record, dict):
            raise ValueError(f"Parallel execution evidence is missing {arm!r}.")
        status = _read_json(run_root / f"{arm}_arm_status.json")
        if any(arm_record.get(field) != status.get(field) for field in fields):
            raise ValueError(
                f"Parallel {arm} execution evidence differs from its arm status."
            )
        pid = arm_record.get("process_pid")
        started = arm_record.get("started_monotonic_ns")
        completed = arm_record.get("completed_monotonic_ns")
        if (
            arm_record.get("status") != "complete"
            or isinstance(pid, bool)
            or not isinstance(pid, int)
            or pid <= 0
            or pid in pids
            or isinstance(started, bool)
            or not isinstance(started, int)
            or isinstance(completed, bool)
            or not isinstance(completed, int)
            or completed <= started
        ):
            raise ValueError(f"Parallel {arm} process timing/PID evidence is invalid.")
        pids.add(pid)
        intervals[arm] = (started, completed)
    overlap_ns = min(interval[1] for interval in intervals.values()) - max(
        interval[0] for interval in intervals.values()
    )
    if (
        overlap_ns <= 0
        or record.get("overlap_monotonic_ns") != overlap_ns
        or record.get("overlap_seconds") != overlap_ns / 1_000_000_000
    ):
        raise ValueError("Control and SAGE process intervals do not prove overlap.")
    return record


def _resolve_declared_path(
    run_root: Path,
    value: Any,
    label: str,
    *,
    required_parent: Path | None = None,
) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Protocol manifest does not declare {label}.")
    path = Path(value)
    if path.is_absolute():
        resolved = path.resolve()
    else:
        candidates = [REPO_ROOT / path, Path.cwd() / path, run_root / path]
        existing: list[Path] = []
        for candidate in candidates:
            candidate_resolved = candidate.resolve()
            if candidate_resolved.exists() and candidate_resolved not in existing:
                existing.append(candidate_resolved)
        if len(existing) == 1:
            resolved = existing[0]
        elif len(existing) > 1:
            raise ValueError(f"Protocol {label} path is ambiguous: {value!r}.")
        else:
            resolved = (REPO_ROOT / path).resolve()
    if required_parent is not None and not resolved.is_relative_to(
        required_parent.resolve()
    ):
        raise ValueError(
            f"Protocol {label} escapes its same-run directory: {resolved}."
        )
    return resolved


def _completed_run_roots(search_root: Path) -> list[Path]:
    return sorted(
        {
            path.parent
            for path in search_root.rglob("protocol_manifest.json")
            if (path.parent / "paired_comparison.json").is_file()
            and (path.parent / "control_cache_report.json").is_file()
        },
        key=lambda path: path.stat().st_mtime,
    )


def _uncached_rows(
    run_dir: Path,
    *,
    expected_tasks: int,
    arm: str,
    expected_outcome_evaluator: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[str], dict[str, int]]:
    summary_path = run_dir / "result_summary.json"
    payload = _read_json(summary_path)
    rows = payload.get("per_scenario_results")
    if not isinstance(rows, list):
        raise ValueError(f"{arm} result summary has no per-scenario rows.")
    by_name: dict[str, dict[str, Any]] = {}
    totals = {field: 0 for field in LLM_USAGE_INTEGER_FIELDS}
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError(f"{arm} result summary contains a non-object row.")
        name = str(item.get("name") or "")
        if not name:
            raise ValueError(f"{arm} result summary contains an unnamed task.")
        if name in by_name:
            raise ValueError(f"{arm} result summary duplicates task {name!r}.")
        exception_type = item.get("exception_type")
        traceback_text = item.get("traceback")
        if exception_type not in (None, "") or traceback_text not in (None, ""):
            raise ValueError(
                f"{arm} task {name!r} contains a runtime exception "
                f"({exception_type or 'traceback recorded'})."
            )
        outcome_similarity = item.get("outcome_similarity")
        if (
            isinstance(outcome_similarity, bool)
            or not isinstance(outcome_similarity, (int, float))
            or not math.isfinite(float(outcome_similarity))
            or not 0.0 <= float(outcome_similarity) <= 1.0
        ):
            raise ValueError(
                f"{arm} task {name!r} is missing a finite audited outcome similarity."
            )
        evaluator_fields = {
            "outcome_evaluator_version": "version",
            "outcome_evaluator_contract_sha256": "contract_sha256",
            "outcome_evaluator_source_sha256": "source_sha256",
        }
        for result_field, manifest_field in evaluator_fields.items():
            if result_field not in item or item[
                result_field
            ] != expected_outcome_evaluator.get(manifest_field):
                raise ValueError(
                    f"{arm} task {name!r} outcome evaluator field "
                    f"{result_field!r} does not match the exact publication "
                    "evaluator identity."
                )
        cache_source = str(item.get("control_cache_source") or "").lower()
        cache_detail = item.get("control_cache")
        if cache_source and cache_source != "fresh":
            raise ValueError(f"{arm} task {name!r} is cache sourced.")
        if isinstance(cache_detail, dict) and (
            str(cache_detail.get("source") or "").lower() == "cached"
            or cache_detail.get("record_ids")
        ):
            raise ValueError(f"{arm} task {name!r} contains cached baseline data.")
        if "llm_cached_call_count" not in item:
            raise ValueError(
                f"{arm} task {name!r} does not report repository whole-response "
                "replay provenance."
            )
        repository_response_replays = item["llm_cached_call_count"]
        if isinstance(repository_response_replays, bool) or not isinstance(
            repository_response_replays, int
        ):
            raise ValueError(
                f"{arm} task {name!r} has invalid repository whole-response "
                "replay provenance."
            )
        if repository_response_replays:
            raise ValueError(
                f"{arm} task {name!r} contains repository whole-response replay calls."
            )
        usage_counts: dict[str, int] = {}
        for field in LLM_USAGE_INTEGER_FIELDS:
            value = item.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{arm} task {name!r} has invalid or missing {field}.")
            usage_counts[field] = value
        if item.get("llm_usage_recorded") is not bool(usage_counts["llm_call_count"]):
            raise ValueError(
                f"{arm} task {name!r} has inconsistent llm_usage_recorded status."
            )
        if (
            usage_counts["llm_live_call_count"] + usage_counts["llm_cached_call_count"]
            != usage_counts["llm_call_count"]
        ):
            raise ValueError(
                f"{arm} task {name!r} has inconsistent live/replayed LLM call counts."
            )
        if (
            usage_counts["llm_provider_cached_prompt_tokens_available_count"]
            != usage_counts["llm_call_count"]
        ):
            raise ValueError(
                f"{arm} task {name!r} is missing provider-prefix cache metadata "
                "for one or more LLM calls."
            )
        if usage_counts["llm_usage_available_count"] != usage_counts["llm_call_count"]:
            raise ValueError(
                f"{arm} task {name!r} is missing token usage for one or more LLM calls."
            )
        if (
            usage_counts["llm_provider_cached_prompt_call_count"]
            > usage_counts["llm_provider_cached_prompt_tokens_available_count"]
        ):
            raise ValueError(
                f"{arm} task {name!r} reports more provider-prefix cache calls "
                "than LLM calls."
            )
        if (
            usage_counts["llm_provider_cached_prompt_tokens"]
            > usage_counts["llm_prompt_tokens"]
        ):
            raise ValueError(
                f"{arm} task {name!r} reports more provider-prefix cached tokens "
                "than prompt tokens."
            )
        if bool(usage_counts["llm_provider_cached_prompt_tokens"]) != bool(
            usage_counts["llm_provider_cached_prompt_call_count"]
        ):
            raise ValueError(
                f"{arm} task {name!r} has inconsistent provider-prefix cache "
                "token and call counts."
            )
        if usage_counts["llm_total_tokens"] != (
            usage_counts["llm_prompt_tokens"] + usage_counts["llm_completion_tokens"]
        ):
            raise ValueError(
                f"{arm} task {name!r} has inconsistent total token accounting."
            )
        for field, value in usage_counts.items():
            totals[field] += value
        by_name[name] = item
    if len(by_name) != expected_tasks:
        raise ValueError(
            f"{arm} has {len(by_name)} unique task rows; expected {expected_tasks}."
        )
    for forbidden in (
        run_dir / "openai_response_cache_metrics.json",
        run_dir / "prompt_cache_metrics.json",
    ):
        if forbidden.exists():
            raise ValueError(f"{arm} emitted forbidden cache artifact {forbidden}.")
    return by_name, list(by_name), totals


def _required_usage_integer(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer.")
    return int(value)


def _verify_llm_usage_artifacts(
    run_dir: Path,
    *,
    rows: dict[str, dict[str, Any]],
    row_totals: dict[str, int],
    arm: str,
    expected_event_arm: str,
    allow_generation_source: bool,
) -> None:
    """Reconcile row, arm-summary, and raw-event LLM usage evidence."""

    summary_path = run_dir / "llm_usage_summary.json"
    summary = _read_json(summary_path)
    if summary.get("schema_version") != 2:
        raise ValueError(f"{arm} LLM usage summary schema version is not 2.")
    if summary.get("token_source") != "openai_chat_completion_usage":
        raise ValueError(f"{arm} LLM usage summary has an invalid token source.")
    if summary.get("llm_usage_recorded") is not bool(row_totals["llm_call_count"]):
        raise ValueError(f"{arm} LLM usage summary has inconsistent recorded status.")
    for field in LLM_USAGE_INTEGER_FIELDS:
        observed = _required_usage_integer(
            summary.get(field),
            label=f"{arm} LLM usage summary field {field!r}",
        )
        if observed != row_totals[field]:
            raise ValueError(
                f"{arm} LLM usage summary field {field!r} does not match "
                "the result rows."
            )
    expected_scenario_count = sum(
        1 for row in rows.values() if row["llm_call_count"] > 0
    )
    if summary.get("scenario_count_with_usage") != expected_scenario_count:
        raise ValueError(
            f"{arm} LLM usage summary scenario count does not match result rows."
        )

    events_path = run_dir / "llm_usage_events.jsonl"
    if not events_path.is_file():
        raise ValueError(f"Missing {arm} LLM usage event artifact: {events_path}")
    event_totals = {field: 0 for field in LLM_USAGE_INTEGER_FIELDS}
    scenario_totals = {
        name: {field: 0 for field in LLM_USAGE_INTEGER_FIELDS} for name in rows
    }
    source_totals: dict[str, dict[str, int]] = {}
    event_count = 0
    allowed_sources = {"toolsandbox_agent", "toolsandbox_user"}
    if allow_generation_source:
        allowed_sources.add("sage_generation")
    try:
        event_lines = events_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(
            f"Cannot read required LLM usage artifact {events_path}: {exc}"
        ) from exc
    for line_number, line in enumerate(event_lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{arm} LLM usage event line {line_number} is invalid JSON: {exc}"
            ) from exc
        if not isinstance(event, dict):
            raise ValueError(
                f"{arm} LLM usage event line {line_number} is not an object."
            )
        scenario = event.get("scenario")
        if not isinstance(scenario, str) or scenario not in rows:
            raise ValueError(
                f"{arm} LLM usage event line {line_number} has an unknown scenario."
            )
        if event.get("model") != PUBLICATION_MODEL:
            raise ValueError(
                f"{arm} LLM usage event line {line_number} does not use "
                f"{PUBLICATION_MODEL}."
            )
        if event.get("source") not in allowed_sources:
            raise ValueError(
                f"{arm} LLM usage event line {line_number} has an invalid source."
            )
        if event.get("arm") != expected_event_arm:
            raise ValueError(
                f"{arm} LLM usage event line {line_number} has an invalid arm."
            )
        if event.get("response_cache_status") != "live":
            raise ValueError(
                f"{arm} LLM usage event line {line_number} is not a live response."
            )
        if event.get("usage_available") is not True:
            raise ValueError(
                f"{arm} LLM usage event line {line_number} has no token usage."
            )
        prompt_tokens = _required_usage_integer(
            event.get("prompt_tokens"),
            label=f"{arm} LLM usage event line {line_number} prompt_tokens",
        )
        cached_prompt_tokens = _required_usage_integer(
            event.get("provider_cached_prompt_tokens"),
            label=(
                f"{arm} LLM usage event line {line_number} "
                "provider_cached_prompt_tokens"
            ),
        )
        completion_tokens = _required_usage_integer(
            event.get("completion_tokens"),
            label=f"{arm} LLM usage event line {line_number} completion_tokens",
        )
        total_tokens = _required_usage_integer(
            event.get("total_tokens"),
            label=f"{arm} LLM usage event line {line_number} total_tokens",
        )
        if cached_prompt_tokens > prompt_tokens:
            raise ValueError(
                f"{arm} LLM usage event line {line_number} reports more "
                "provider-prefix cached tokens than prompt tokens."
            )
        if total_tokens != prompt_tokens + completion_tokens:
            raise ValueError(
                f"{arm} LLM usage event line {line_number} has inconsistent "
                "total token accounting."
            )
        raw_usage = event.get("raw_usage")
        if not isinstance(raw_usage, dict):
            raise ValueError(
                f"{arm} LLM usage event line {line_number} has no raw API usage."
            )
        raw_prompt_tokens = _required_usage_integer(
            raw_usage.get("prompt_tokens"),
            label=f"{arm} LLM usage event line {line_number} raw prompt_tokens",
        )
        raw_completion_tokens = _required_usage_integer(
            raw_usage.get("completion_tokens"),
            label=f"{arm} LLM usage event line {line_number} raw completion_tokens",
        )
        raw_total_tokens = _required_usage_integer(
            raw_usage.get("total_tokens"),
            label=f"{arm} LLM usage event line {line_number} raw total_tokens",
        )
        raw_prompt_details = raw_usage.get("prompt_tokens_details")
        if not isinstance(raw_prompt_details, dict):
            raise ValueError(
                f"{arm} LLM usage event line {line_number} has no raw "
                "prompt-token details."
            )
        raw_cached_prompt_tokens = _required_usage_integer(
            raw_prompt_details.get("cached_tokens"),
            label=(f"{arm} LLM usage event line {line_number} raw cached_tokens"),
        )
        if (
            raw_prompt_tokens != prompt_tokens
            or raw_completion_tokens != completion_tokens
            or raw_total_tokens != total_tokens
            or raw_cached_prompt_tokens != cached_prompt_tokens
        ):
            raise ValueError(
                f"{arm} LLM usage event line {line_number} disagrees with "
                "its raw API usage."
            )
        increments = {
            "llm_call_count": 1,
            "llm_live_call_count": 1,
            "llm_cached_call_count": 0,
            "llm_prompt_tokens": prompt_tokens,
            "llm_provider_cached_prompt_tokens": cached_prompt_tokens,
            "llm_provider_cached_prompt_call_count": int(cached_prompt_tokens > 0),
            "llm_provider_cached_prompt_tokens_available_count": 1,
            "llm_completion_tokens": completion_tokens,
            "llm_total_tokens": total_tokens,
            "llm_usage_available_count": 1,
        }
        for field, value in increments.items():
            event_totals[field] += value
            scenario_totals[scenario][field] += value
        source = str(event["source"])
        if source not in source_totals:
            source_totals[source] = {
                field: 0 for field in LLM_USAGE_SOURCE_INTEGER_FIELDS
            }
        for field in LLM_USAGE_SOURCE_INTEGER_FIELDS:
            source_totals[source][field] += increments[field]
        event_count += 1

    if event_count != row_totals["llm_call_count"]:
        raise ValueError(f"{arm} LLM usage event count does not match result rows.")
    for field in LLM_USAGE_INTEGER_FIELDS:
        if event_totals[field] != row_totals[field]:
            raise ValueError(
                f"{arm} raw LLM usage events field {field!r} does not match "
                "the result rows."
            )
    for scenario, expected in scenario_totals.items():
        row = rows[scenario]
        for field in LLM_USAGE_INTEGER_FIELDS:
            if expected[field] != row[field]:
                raise ValueError(
                    f"{arm} raw LLM usage events for task {scenario!r} field "
                    f"{field!r} do not match the result row."
                )
    if summary.get("llm_usage_by_source") != dict(sorted(source_totals.items())):
        raise ValueError(f"{arm} LLM usage source summary does not match raw events.")


def _optional_feedback_metric(value: Any, *, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric or null.")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{label} must be finite.")
    return numeric


def _feedback_outcome_with_source(
    row: dict[str, Any],
    *,
    label: str,
) -> tuple[float | None, str]:
    audited_outcome = _optional_feedback_metric(
        row.get("outcome_similarity"),
        label=f"{label} audited outcome",
    )
    if audited_outcome is not None:
        return audited_outcome, "audited_outcome"
    return None, "unavailable"


def _require_reflection_field(
    row: dict[str, Any],
    *,
    field: str,
    expected: Any,
    label: str,
) -> None:
    if field not in row or row[field] != expected:
        raise ValueError(f"Reflection {label} mismatch for {row.get('scenario')!r}.")


def _verify_reflection(
    candidate_dir: Path,
    *,
    control_rows: dict[str, dict[str, Any]],
    candidate_rows: dict[str, dict[str, Any]],
) -> None:
    feedback_path = candidate_dir / "self_evolution_task_feedback.jsonl"
    if not feedback_path.is_file():
        raise ValueError(f"Missing same-run reflection feedback: {feedback_path}")
    feedback: dict[str, dict[str, Any]] = {}
    feedback_order: list[str] = []
    for line in feedback_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("event") != "self_evolution_task_assessed":
            continue
        name = str(row.get("scenario") or "")
        if not name or name in feedback:
            raise ValueError(f"Duplicate or unnamed reflection task {name!r}.")
        completed_count = row.get("completed_count")
        expected_completed_count = len(feedback_order) + 1
        if (
            isinstance(completed_count, bool)
            or not isinstance(completed_count, int)
            or completed_count != expected_completed_count
        ):
            raise ValueError(
                f"Reflection completed_count mismatch for {name!r}; expected "
                f"{expected_completed_count}."
            )
        if row.get("control_source") != "same_run_fresh":
            raise ValueError(f"Reflection task {name!r} is not same-run fresh.")
        control = control_rows.get(name)
        if control is None:
            raise ValueError(f"Reflection task {name!r} has no matched live control.")
        candidate = candidate_rows.get(name)
        if candidate is None:
            raise ValueError(f"Reflection task {name!r} has no matched candidate.")
        control_score = _optional_feedback_metric(
            control.get("similarity"), label=f"control task {name!r} score"
        )
        candidate_score = _optional_feedback_metric(
            candidate.get("similarity"), label=f"candidate task {name!r} score"
        )
        control_outcome, control_outcome_source = _feedback_outcome_with_source(
            control, label=f"control task {name!r}"
        )
        candidate_outcome, candidate_outcome_source = _feedback_outcome_with_source(
            candidate, label=f"candidate task {name!r}"
        )
        score_delta = (
            candidate_score - control_score
            if control_score is not None and candidate_score is not None
            else None
        )
        outcome_delta = (
            candidate_outcome - control_outcome
            if control_outcome is not None and candidate_outcome is not None
            else None
        )
        for field, expected, label in (
            ("control_score", control_score, "control score"),
            ("candidate_score", candidate_score, "candidate score"),
            ("score_delta", score_delta, "score delta"),
            ("control_outcome", control_outcome, "control outcome"),
            (
                "control_outcome_source",
                control_outcome_source,
                "control outcome source",
            ),
            ("candidate_outcome", candidate_outcome, "candidate outcome"),
            (
                "candidate_outcome_source",
                candidate_outcome_source,
                "candidate outcome source",
            ),
            ("outcome_delta", outcome_delta, "outcome delta"),
        ):
            _require_reflection_field(
                row,
                field=field,
                expected=expected,
                label=label,
            )
        feedback[name] = row
        feedback_order.append(name)
    if set(feedback) != set(control_rows):
        raise ValueError(
            "Reflection/control task sets differ "
            f"(missing={sorted(set(control_rows) - set(feedback))!r}, "
            f"extra={sorted(set(feedback) - set(control_rows))!r})."
        )
    if set(feedback) != set(candidate_rows):
        raise ValueError(
            "Reflection/candidate task sets differ "
            f"(missing={sorted(set(candidate_rows) - set(feedback))!r}, "
            f"extra={sorted(set(feedback) - set(candidate_rows))!r})."
        )
    if feedback_order != list(control_rows) or feedback_order != list(candidate_rows):
        raise ValueError(
            "Reflection task order does not exactly match control and candidate order."
        )


def _verify_actor_visible_only_feedback(candidate_dir: Path) -> dict[str, Any]:
    """Prove that a score-free online build emitted no reflection artifacts."""

    forbidden = (
        "self_evolution_task_feedback.jsonl",
        "self_evolution_tool_repair_requests.jsonl",
        "self_evolution_tool_repair_acknowledgements.jsonl",
        "self_evolution_tool_lifecycle.jsonl",
    )
    nonempty = [
        name
        for name in forbidden
        if (candidate_dir / name).is_file()
        and (candidate_dir / name).read_text(encoding="utf-8").strip()
    ]
    if nonempty:
        raise ValueError(
            "Actor-visible-only run contains evaluator/reflection artifacts: "
            f"{nonempty}."
        )
    repair_state_path = candidate_dir / POST_DEPLOYMENT_REPAIR_STATE_FILENAME
    repair_state_status = "absent"
    if repair_state_path.exists():
        repair_state = _read_json(repair_state_path)
        expected_repair_state = {
            "schema_version": 1,
            "pending_repair_requests": [],
            "handled_repair_request_ids": [],
            "canary_state_by_tool": {},
            "repair_transactions_by_tool": {},
            "last_completed_count": 0,
        }
        if repair_state != expected_repair_state:
            raise ValueError(
                "Actor-visible-only run contains nonempty post-deployment repair state."
            )
        repair_state_status = "present_empty_disabled_receipt"
    summary = _read_json(candidate_dir / "result_summary.json")
    result_rows = summary.get("per_scenario_results")
    if not isinstance(result_rows, list):
        raise ValueError("Actor-visible-only result summary has no scenario rows.")
    expected_order = [
        str(row.get("name") or "") for row in result_rows if isinstance(row, dict)
    ]
    receipt_path = candidate_dir / "online_birth_feedback_receipts.jsonl"
    if not receipt_path.is_file():
        raise ValueError("Actor-visible-only feedback receipt journal is missing.")
    receipts = [
        json.loads(line)
        for line in receipt_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not all(isinstance(row, dict) for row in receipts):
        raise ValueError("Actor-visible-only feedback receipt journal is malformed.")
    receipt_order = [str(row.get("scenario") or "") for row in receipts]
    if receipt_order != expected_order:
        raise ValueError(
            "Actor-visible-only feedback receipts do not match the task order."
        )
    for row in receipts:
        if (
            row.get("online_feedback_mode") != "actor-visible-only"
            or row.get("online_birth_outcome_source") != "withheld_actor_visible_only"
            or row.get("score_fields_with_values") != []
            or row.get("evaluator_private_fields_present") != []
            or isinstance(row.get("visible_message_count"), bool)
            or not isinstance(row.get("visible_message_count"), int)
            or int(row["visible_message_count"]) < 0
        ):
            raise ValueError(
                "Actor-visible-only feedback receipt contains evaluator evidence."
            )
    return {
        "status": "pass",
        "online_feedback_mode": "actor-visible-only",
        "nonempty_forbidden_artifacts": [],
        "repair_state_status": repair_state_status,
        "score_free_feedback_receipt_count": len(receipts),
        "score_free_feedback_receipt_sha256": hashlib.sha256(
            receipt_path.read_bytes()
        ).hexdigest(),
    }


def _verify_paired_outcome_aggregates(
    comparison: dict[str, Any],
    *,
    control_rows: dict[str, dict[str, Any]],
    candidate_rows: dict[str, dict[str, Any]],
) -> None:
    paired_outcomes: list[tuple[float, float, float]] = []
    for name in control_rows:
        control_outcome = _optional_feedback_metric(
            control_rows[name].get("outcome_similarity"),
            label=f"control task {name!r} audited outcome",
        )
        candidate_outcome = _optional_feedback_metric(
            candidate_rows[name].get("outcome_similarity"),
            label=f"candidate task {name!r} audited outcome",
        )
        if control_outcome is None or candidate_outcome is None:
            continue
        paired_outcomes.append(
            (control_outcome, candidate_outcome, candidate_outcome - control_outcome)
        )

    count = len(paired_outcomes)
    deltas = [values[2] for values in paired_outcomes]
    expected: dict[str, int | float | None] = {
        "scenario_count": len(control_rows),
        "outcome_scenario_count": count,
        "control_mean_outcome_similarity": (
            sum(values[0] for values in paired_outcomes) / count if count else None
        ),
        "candidate_mean_outcome_similarity": (
            sum(values[1] for values in paired_outcomes) / count if count else None
        ),
        "mean_outcome_similarity_delta": (sum(deltas) / count if count else None),
        "outcome_gain_count": sum(delta > 0 for delta in deltas),
        "outcome_regression_count": sum(delta < 0 for delta in deltas),
        "outcome_preserved_count": sum(delta == 0 for delta in deltas),
    }
    integer_fields = {
        "scenario_count",
        "outcome_scenario_count",
        "outcome_gain_count",
        "outcome_regression_count",
        "outcome_preserved_count",
    }
    for field, expected_value in expected.items():
        if field not in comparison:
            raise ValueError(f"Paired comparison is missing outcome field {field!r}.")
        observed = comparison[field]
        if field in integer_fields:
            matches = (
                not isinstance(observed, bool)
                and isinstance(observed, int)
                and observed == expected_value
            )
        elif expected_value is None:
            matches = observed is None
        else:
            matches = (
                not isinstance(observed, bool)
                and isinstance(observed, (int, float))
                and math.isfinite(float(observed))
                and float(observed) == expected_value
            )
        if not matches:
            raise ValueError(
                f"Paired comparison outcome field {field!r} does not match "
                "the scored result rows."
            )


def verify_run(
    search_root: Path,
    *,
    expected_tasks: int,
    expect_reflection: str,
    expected_fixture_sha256: str = PINNED_RAPID_FIXTURE_SHA256,
    expected_benchmark_sha256: str = PINNED_BENCHMARK_SHA256,
    expected_scenario_order_sha256: str = PINNED_SCENARIO_ORDER_SHA256,
    gate_purpose: str = PUBLICATION_GATE_PURPOSE_RELEASE_SAMPLE,
) -> dict[str, Any]:
    if gate_purpose not in PUBLICATION_GATE_PURPOSES:
        raise ValueError(f"Unknown publication gate purpose: {gate_purpose!r}.")
    if (
        expected_benchmark_sha256 == PINNED_BENCHMARK_SHA256
        and expected_tasks != PUBLICATION_TASK_COUNT
    ):
        raise ValueError(
            "The pinned publication benchmark requires exactly "
            f"{PUBLICATION_TASK_COUNT} tasks per arm."
        )
    runs = _completed_run_roots(search_root)
    if not runs:
        raise ValueError(f"No completed paired run found under {search_root}.")
    run_root = runs[-1]
    protocol = _read_json(run_root / "protocol_manifest.json")
    protocol_events, protocol_event_journal = _verified_protocol_event_rows(
        run_root=run_root,
        protocol=protocol,
    )
    cache_report = _read_json(run_root / "control_cache_report.json")
    comparison = _read_json(run_root / "paired_comparison.json")
    current_outcome_evaluator = outcome_evaluator_manifest()
    pinned_outcome_evaluator_identity = {
        "version": PUBLICATION_OUTCOME_EVALUATOR_VERSION,
        "contract_sha256": PUBLICATION_OUTCOME_EVALUATOR_CONTRACT_SHA256,
        "source_sha256": PUBLICATION_OUTCOME_EVALUATOR_SOURCE_SHA256,
    }
    if any(
        current_outcome_evaluator.get(field) != expected
        for field, expected in pinned_outcome_evaluator_identity.items()
    ):
        raise ValueError(
            "The installed reporting outcome evaluator is not the exact "
            "pinned publication evaluator identity."
        )
    publication_provenance = _verify_publication_provenance(protocol)
    for model_field in ("agent", "user", "generation_model"):
        if protocol.get(model_field) != PUBLICATION_MODEL:
            raise ValueError(
                f"Protocol field {model_field!r} is not {PUBLICATION_MODEL}."
            )
    online_generation = expect_reflection in {
        "same-run-fresh",
        "actor-visible-only",
    }
    expected_mode = "online_build_full" if online_generation else "full_benchmark"
    if protocol.get("mode") != expected_mode:
        raise ValueError(f"Protocol mode is not {expected_mode!r}.")
    expected_generation = online_generation
    if protocol.get("generation_enabled") is not expected_generation:
        raise ValueError(
            "Protocol generation_enabled does not match the publication arm."
        )
    expected_sage_policy = "self-evolving-praxis" if expected_generation else "none"
    if protocol.get("sage_policy") != expected_sage_policy:
        raise ValueError(f"Protocol sage_policy is not {expected_sage_policy!r}.")
    if int(protocol.get("scenario_count") or 0) != expected_tasks:
        raise ValueError(
            "Protocol scenario count does not match the publication cohort."
        )
    if protocol.get("benchmark_manifest_sha256") != expected_benchmark_sha256:
        raise ValueError(
            "Protocol benchmark manifest does not match the publication pin."
        )
    benchmark_path = _resolve_declared_path(
        run_root,
        protocol.get("benchmark_manifest_path"),
        "benchmark_manifest_path",
    )
    if not benchmark_path.is_file():
        raise ValueError(f"Recorded benchmark manifest is missing: {benchmark_path}")
    if (
        hashlib.sha256(benchmark_path.read_bytes()).hexdigest()
        != expected_benchmark_sha256
    ):
        raise ValueError("Recorded benchmark manifest bytes no longer match the pin.")
    if protocol.get("scenario_order_sha256") != expected_scenario_order_sha256:
        raise ValueError(
            "Protocol ordered scenario names do not match the publication pin."
        )
    required_protocol = {
        "publication_gate_purpose": gate_purpose,
        "protocol_gate_passed": True,
        "protocol_gate_reasons": [],
        "fresh_control_required": True,
        "scenario_transform_failure_policy": "abort",
        "publication_performance_endpoint": "outcome_task_completion_similarity",
        "actor_selection_mode": "policy",
        "control_condition": MATCHED_CONTROL_CONDITION,
        "control_agent_runtime": SAGE_WRAPPED_AGENT_RUNTIME,
        "control_actor_selection_mode": "policy",
        "control_generated_tools_enabled": False,
        "candidate_agent_runtime": SAGE_WRAPPED_AGENT_RUNTIME,
        "candidate_actor_selection_mode": "policy",
        "candidate_generated_tools_enabled": expected_generation,
        "reporting_outcome_evaluator": current_outcome_evaluator,
        "online_feedback_evaluator_version": ONLINE_FEEDBACK_EVALUATOR_VERSION,
        "timezone": PUBLICATION_TIMEZONE,
        "control_cache_mode": "off",
        "control_source": "fresh",
        "cached_control_tasks": 0,
        "fresh_control_tasks": expected_tasks,
        "openai_response_cache_enabled": False,
        "openai_response_cache_mode": "off",
        "openai_response_cache_scope": "persistent_repository_whole_response_replay",
        "prompt_cache_enabled": False,
        "prompt_cache_scope": "persistent_generation_output_replay",
        "generator_contract_and_repair_analysis_memoization": "within_run_only",
        "openai_provider_prompt_prefix_cache_policy": "automatic_implicit",
        "openai_provider_prompt_prefix_cache_reuses_responses": False,
        "sage_task_cache_enabled": False,
        "cross_run_failure_memory_enabled": False,
        "cross_run_failure_memory_path": None,
        "diagnostic_force_allowed": False,
        "active_diagnostic_force_env": [],
        "parallel_arms": True,
        "reflection_control_delivery": (
            "task_synchronous_stream"
            if expect_reflection == "same-run-fresh"
            else "withheld_actor_visible_only"
            if expect_reflection == "actor-visible-only"
            else "not_applicable_generation_disabled"
        ),
        "dashboard_open_required": True,
    }
    for field, expected in required_protocol.items():
        if protocol.get(field) != expected:
            raise ValueError(
                f"Protocol field {field!r} is {protocol.get(field)!r}; "
                f"expected {expected!r}."
            )
    recorded_feedback_mode = protocol.get("online_feedback_mode")
    if expect_reflection == "actor-visible-only":
        if recorded_feedback_mode != "actor-visible-only":
            raise ValueError(
                "Actor-visible-only run did not record its online feedback mode."
            )
        pilot_manifest_value = protocol.get("hypothesis_pilot_manifest")
        if not isinstance(pilot_manifest_value, str) or not pilot_manifest_value:
            raise ValueError(
                "Actor-visible-only campaign did not bind a hypothesis-pilot manifest."
            )
        pilot_manifest_path = Path(pilot_manifest_value).resolve()
        if not pilot_manifest_path.is_file():
            raise ValueError("Bound hypothesis-pilot manifest is missing.")
    elif recorded_feedback_mode not in {None, "audited"}:
        raise ValueError(
            "Publication run records an unexpected online feedback mode: "
            f"{recorded_feedback_mode!r}."
        )
    if comparison.get("protocol_gate_passed") is not True:
        raise ValueError("Paired comparison protocol gate did not pass.")
    if comparison.get("protocol_gate_reasons") != []:
        raise ValueError("Paired comparison contains protocol gate failure reasons.")
    if comparison.get("publication_gate_purpose") != gate_purpose:
        raise ValueError(
            "Paired comparison publication gate purpose does not match verification."
        )
    performance_gate_passed = protocol.get("performance_gate_passed")
    performance_gate_reasons = protocol.get("performance_gate_reasons")
    if not isinstance(performance_gate_passed, bool):
        raise ValueError("Protocol performance gate result is not boolean.")
    if not isinstance(performance_gate_reasons, list) or any(
        not isinstance(reason, str) or not reason for reason in performance_gate_reasons
    ):
        raise ValueError("Protocol performance gate reasons are malformed.")
    if performance_gate_passed != (not performance_gate_reasons):
        raise ValueError(
            "Protocol performance gate result and reasons are inconsistent."
        )
    if comparison.get("performance_gate_passed") is not performance_gate_passed:
        raise ValueError("Paired comparison performance gate result disagrees.")
    if comparison.get("performance_gate_reasons") != performance_gate_reasons:
        raise ValueError("Paired comparison performance gate reasons disagree.")
    if gate_purpose == PUBLICATION_GATE_PURPOSE_RELEASE_SAMPLE and (
        performance_gate_passed is not True or performance_gate_reasons != []
    ):
        raise ValueError("Release-sample performance gate did not pass.")
    runtime_exception_count = comparison.get("runtime_exception_count")
    if (
        isinstance(runtime_exception_count, bool)
        or not isinstance(runtime_exception_count, int)
        or runtime_exception_count != 0
    ):
        raise ValueError("Paired comparison contains runtime exceptions.")
    for arm_name in ("control", "candidate"):
        arm_summary = comparison.get(arm_name)
        if not isinstance(arm_summary, dict):
            raise ValueError(f"Paired comparison is missing {arm_name} summary.")
        required_arm_summary = {
            "run_status": "complete",
            "scenario_count": expected_tasks,
            "planned_scenario_count": expected_tasks,
            "exception_count": 0,
        }
        for field, expected in required_arm_summary.items():
            if arm_summary.get(field) != expected:
                raise ValueError(
                    f"Paired comparison {arm_name} field {field!r} is "
                    f"{arm_summary.get(field)!r}; expected {expected!r}."
                )
    parallel_execution = _verify_parallel_arm_execution(run_root, protocol)
    dashboard_receipt_path = _resolve_declared_path(
        run_root,
        protocol.get("dashboard_open_receipt_path"),
        "dashboard_open_receipt_path",
        required_parent=run_root,
    )
    dashboard_receipt = _read_json(dashboard_receipt_path)
    expected_task_dashboard = (run_root / "dashboard" / "task_compare.html").resolve()
    opened_monotonic_ns = dashboard_receipt.get("opened_monotonic_ns")
    first_model_process_start = min(
        int(parallel_execution["arms"][arm]["started_monotonic_ns"])
        for arm in ("control", "candidate")
    )
    if (
        dashboard_receipt.get("dashboard") != "task_compare"
        or dashboard_receipt.get("comparison") != "fresh_control_vs_policy_sage"
        or Path(str(dashboard_receipt.get("path") or "")).resolve()
        != expected_task_dashboard
        or dashboard_receipt.get("url") != protocol.get("dashboard_task_compare_url")
        or dashboard_receipt.get("external_browser_opened") is not True
        or dashboard_receipt.get("http_verified_before_open") is not True
        or dashboard_receipt.get("dashboard_server_protocol")
        != DASHBOARD_SERVER_PROTOCOL
        or Path(str(dashboard_receipt.get("dashboard_server_root") or "")).resolve()
        != run_root.resolve()
        or dashboard_receipt.get("opened_before_model_processes") is not True
        or isinstance(opened_monotonic_ns, bool)
        or not isinstance(opened_monotonic_ns, int)
        or opened_monotonic_ns <= 0
        or opened_monotonic_ns >= first_model_process_start
    ):
        raise ValueError(
            "Task Compare dashboard receipt does not prove the exact run dashboard "
            "opened externally before either model process."
        )
    run_env = protocol.get("run_affecting_sage_env")
    if not isinstance(run_env, dict):
        raise ValueError("Publication run did not record its execution environment.")
    for env_name, expected in PUBLICATION_EXECUTION_ENV.items():
        if run_env.get(env_name) != expected:
            raise ValueError(f"Publication run did not record {env_name}={expected!r}.")
    fixture = protocol.get("external_fixture")
    if not isinstance(fixture, dict):
        raise ValueError("Protocol does not record a validated external fixture.")
    if fixture.get("policy") != "validated_read_only_fixture":
        raise ValueError("External fixture policy is not validated read-only.")
    if fixture.get("mode") != "read_only":
        raise ValueError("External fixture was not used read-only.")
    if fixture.get("sha256") != expected_fixture_sha256:
        raise ValueError("External fixture does not match the pinned SHA-256.")
    fixture_path = _resolve_declared_path(
        run_root,
        fixture.get("path"),
        "external_fixture.path",
    )
    if not fixture_path.is_file():
        raise ValueError(f"Recorded external fixture is missing: {fixture_path}")
    observed_fixture_sha256 = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    if observed_fixture_sha256 != expected_fixture_sha256:
        raise ValueError("Recorded external fixture bytes no longer match the pin.")
    if expect_reflection == "same-run-fresh":
        if protocol.get("reflection_control_source") != "same_run_fresh":
            raise ValueError(
                "Online reflection did not declare same-run fresh control."
            )
    elif expect_reflection == "actor-visible-only":
        if protocol.get("reflection_control_source") != "withheld_actor_visible_only":
            raise ValueError(
                "Actor-visible-only run did not declare evaluator feedback withheld."
            )
    elif protocol.get("reflection_control_source") != "not_applicable":
        raise ValueError(
            "Frozen run unexpectedly declared a reflection control source."
        )
    for field in (
        "resume_run_root",
        "resume_completed_limit",
        "control_resume_dir",
        "candidate_resume_dir",
    ):
        if protocol.get(field) is not None:
            raise ValueError(
                f"Publication run used forbidden partial-row resume field {field!r}."
            )
    required_report = {
        "mode": "off",
        "control_source": "fresh",
        "cached_control_tasks": 0,
        "fresh_control_tasks": expected_tasks,
        "cache_accessed": False,
        "fresh_control_enforced": True,
    }
    for field, expected in required_report.items():
        if cache_report.get(field) != expected:
            raise ValueError(
                f"Control report field {field!r} is {cache_report.get(field)!r}; "
                f"expected {expected!r}."
            )
    control_dir = _resolve_declared_path(
        run_root,
        protocol.get("control_dir"),
        "control_dir",
        required_parent=run_root / "control",
    )
    candidate_dir = _resolve_declared_path(
        run_root,
        protocol.get("candidate_dir"),
        "candidate_dir",
        required_parent=run_root / "candidate",
    )
    matched_policy_runtimes = _verify_matched_policy_runtimes(
        control_dir,
        candidate_dir,
    )
    _verify_no_scenario_transform_failures(candidate_dir)
    lifecycle_integrity: dict[str, Any] | None = None
    registry_dir = _resolve_declared_path(
        run_root,
        protocol.get("registry_dir"),
        "registry_dir",
    )
    registry_manifest = registry_dir / "registry_manifest.json"
    if not registry_manifest.is_file() or registry_manifest.is_symlink():
        raise ValueError(
            "Completed SAGE run is missing its final registry manifest or it is "
            "not a regular file: "
            f"{registry_manifest}"
        )
    recorded_registry_digest = protocol.get("registry_manifest_digest_after_run")
    if not isinstance(recorded_registry_digest, str) or not re.fullmatch(
        r"[0-9a-f]{64}", recorded_registry_digest
    ):
        raise ValueError(
            "Protocol does not record a valid final registry manifest digest."
        )
    observed_registry_digest = hashlib.sha256(
        registry_manifest.read_bytes()
    ).hexdigest()
    if observed_registry_digest != recorded_registry_digest:
        raise ValueError("Final registry manifest does not match the protocol digest.")
    registry_payload = _read_json(registry_manifest)
    registry_tools = registry_payload.get("tools")
    if not isinstance(registry_tools, dict) or any(
        not isinstance(tool_name, str) or not tool_name for tool_name in registry_tools
    ):
        raise ValueError("Final registry manifest has an invalid tool mapping.")
    generated_tool_names = set(registry_tools)
    if expected_generation:
        _verify_empty_online_registry_start(run_root, protocol)
    control_rows, control_order, control_llm_usage = _uncached_rows(
        control_dir,
        expected_tasks=expected_tasks,
        arm="control",
        expected_outcome_evaluator=current_outcome_evaluator,
    )
    candidate_rows, candidate_order, candidate_llm_usage = _uncached_rows(
        candidate_dir,
        expected_tasks=expected_tasks,
        arm="candidate",
        expected_outcome_evaluator=current_outcome_evaluator,
    )
    _verify_llm_usage_artifacts(
        control_dir,
        rows=control_rows,
        row_totals=control_llm_usage,
        arm="control",
        expected_event_arm=f"{expected_mode}_control",
        allow_generation_source=False,
    )
    _verify_llm_usage_artifacts(
        candidate_dir,
        rows=candidate_rows,
        row_totals=candidate_llm_usage,
        arm="candidate",
        expected_event_arm=f"{expected_mode}_candidate",
        allow_generation_source=expected_generation,
    )
    if control_order != candidate_order:
        raise ValueError("Control and candidate task order is not identical.")
    observed_order_sha256 = hashlib.sha256(
        ("\n".join(control_order) + "\n").encode("utf-8")
    ).hexdigest()
    if observed_order_sha256 != expected_scenario_order_sha256:
        raise ValueError(
            "Result rows do not preserve the pinned publication task order."
        )
    control_trajectory_evidence = _verify_trajectory_artifacts(
        control_dir,
        rows=control_rows,
        order=control_order,
        arm="control",
        generated_tool_names=generated_tool_names,
    )
    if any(
        any(values for values in task_evidence.values())
        for task_evidence in control_trajectory_evidence.values()
    ):
        raise ValueError(
            "Control trajectories expose or execute a generated registry tool."
        )
    candidate_trajectory_evidence = _verify_trajectory_artifacts(
        candidate_dir,
        rows=candidate_rows,
        order=candidate_order,
        arm="candidate",
        generated_tool_names=generated_tool_names,
    )
    checkpoint_integrity = _verify_registry_checkpoint_bindings(
        candidate_dir,
        registry_dir,
        scenario_order=candidate_order,
        trajectory_evidence=candidate_trajectory_evidence,
        require_lifecycle_feedback=expect_reflection == "same-run-fresh",
    )
    if expect_reflection == "same-run-fresh":
        lifecycle_integrity = _verify_lifecycle_closed(
            candidate_dir,
            registry_dir,
            trajectory_evidence=candidate_trajectory_evidence,
            protocol_events=protocol_events,
        )
        lifecycle_integrity.update(checkpoint_integrity)
        lifecycle_integrity["actor_followthrough_closure"] = (
            _verify_actor_followthrough_closed(
                candidate_dir,
                registry_dir,
                scenario_order=candidate_order,
                trajectory_evidence=candidate_trajectory_evidence,
                protocol_events=protocol_events,
            )
        )
    elif expect_reflection == "actor-visible-only":
        lifecycle_integrity = {
            "lifecycle_mutation_expected": False,
            "online_registry_birth_expected": True,
            "evaluator_feedback_withheld": _verify_actor_visible_only_feedback(
                candidate_dir
            ),
            **checkpoint_integrity,
        }
    else:
        lifecycle_integrity = {
            "lifecycle_mutation_expected": False,
            "frozen_registry_integrity": _verify_frozen_registry_immutable(
                run_root,
                protocol,
                registry_dir,
            ),
            **checkpoint_integrity,
        }
    _verify_paired_outcome_aggregates(
        comparison,
        control_rows=control_rows,
        candidate_rows=candidate_rows,
    )
    if expect_reflection == "same-run-fresh":
        _verify_reflection(
            candidate_dir,
            control_rows=control_rows,
            candidate_rows=candidate_rows,
        )
    return {
        "status": "pass",
        "run_root": str(run_root),
        "publication_gate_purpose": gate_purpose,
        "performance_gate_passed": performance_gate_passed,
        "performance_gate_reasons": performance_gate_reasons,
        "scenario_count": expected_tasks,
        "matched_policy_runtimes": matched_policy_runtimes,
        "audited_outcome_count": {
            "control": len(control_rows),
            "candidate": len(candidate_rows),
        },
        "trajectory_audit_count": {
            "control": len(control_trajectory_evidence),
            "candidate": len(candidate_trajectory_evidence),
        },
        "cached_control_tasks": 0,
        # Backward-compatible name: this counts repository response replays,
        # not provider prompt-prefix cached input tokens.
        "cached_llm_calls": 0,
        "repository_whole_response_replay_hits": 0,
        "openai_provider_prompt_prefix_cache_policy": protocol[
            "openai_provider_prompt_prefix_cache_policy"
        ],
        "publication_model": PUBLICATION_MODEL,
        "openai_provider_cached_prompt_tokens": {
            "control": control_llm_usage["llm_provider_cached_prompt_tokens"],
            "candidate": candidate_llm_usage["llm_provider_cached_prompt_tokens"],
        },
        "openai_provider_cached_prompt_call_count": {
            "control": control_llm_usage["llm_provider_cached_prompt_call_count"],
            "candidate": candidate_llm_usage["llm_provider_cached_prompt_call_count"],
        },
        "openai_provider_cached_prompt_tokens_available_count": {
            "control": control_llm_usage[
                "llm_provider_cached_prompt_tokens_available_count"
            ],
            "candidate": candidate_llm_usage[
                "llm_provider_cached_prompt_tokens_available_count"
            ],
        },
        "reflection_control_source": protocol.get("reflection_control_source"),
        "reflection_control_delivery": protocol.get("reflection_control_delivery"),
        "parallel_arm_execution": parallel_execution,
        "reporting_outcome_evaluator": current_outcome_evaluator,
        "online_feedback_evaluator_version": ONLINE_FEEDBACK_EVALUATOR_VERSION,
        "lifecycle_integrity": lifecycle_integrity,
        "protocol_event_journal": protocol_event_journal,
        "external_fixture_sha256": observed_fixture_sha256,
        "git_commit": publication_provenance["git_commit"],
        "git_tree": publication_provenance["git_tree"],
        "python_version": publication_provenance["python_version"],
        "python_implementation": publication_provenance["python_implementation"],
        "platform_system": publication_provenance["platform_system"],
        "platform_machine": publication_provenance["platform_machine"],
        "environment_lock_sha256": publication_provenance["environment_lock_sha256"],
        "external_distribution_count": publication_provenance[
            "external_distribution_count"
        ],
        "external_distribution_sha256": publication_provenance[
            "external_distribution_sha256"
        ],
        "fixed_toolsandbox_timestamp": publication_provenance[
            "fixed_toolsandbox_timestamp"
        ],
        "publication_provenance": publication_provenance,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-root", type=Path, required=True)
    parser.add_argument("--expected-tasks", type=int, default=PUBLICATION_TASK_COUNT)
    parser.add_argument(
        "--expect-reflection",
        choices=("same-run-fresh", "actor-visible-only", "not-applicable"),
        required=True,
    )
    parser.add_argument(
        "--gate-purpose",
        choices=PUBLICATION_GATE_PURPOSES,
        default=PUBLICATION_GATE_PURPOSE_RELEASE_SAMPLE,
    )
    args = parser.parse_args()
    try:
        result = verify_run(
            args.search_root,
            expected_tasks=args.expected_tasks,
            expect_reflection=args.expect_reflection,
            gate_purpose=args.gate_purpose,
        )
    except ValueError as exc:
        raise SystemExit(f"publication_run_verification=failed\n{exc}") from exc
    print("publication_run_verification=pass")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
