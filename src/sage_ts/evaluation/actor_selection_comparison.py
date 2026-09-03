"""Fail-closed verification for matched policy-versus-auto actor selection runs."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from sage_ts.evaluation.retry_provenance import (
    validate_successful_retry_provenance,
)

INVENTORY_AUTHORITY_ARTIFACT = "sage_matched_inventory_authority"
INVENTORY_AUTHORITY_SCHEMA_VERSION = 2
REPO_ROOT = Path(__file__).resolve().parents[3]
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
PERSISTENT_RESPONSE_CACHE_ARTIFACTS = (
    "openai_response_cache_metrics.json",
    "prompt_cache_metrics.json",
)


class ActorSelectionVerificationError(ValueError):
    """Raised when a selector experiment is not causally interpretable."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ActorSelectionVerificationError(
            f"Cannot read JSON artifact: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise ActorSelectionVerificationError(f"Expected a JSON object: {path}")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ActorSelectionVerificationError(
            f"Cannot read JSONL artifact: {path}"
        ) from exc
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ActorSelectionVerificationError(
                f"Invalid JSONL at {path}:{line_number}"
            ) from exc
        if not isinstance(row, dict):
            raise ActorSelectionVerificationError(
                f"Expected a JSON object at {path}:{line_number}"
            )
        rows.append(row)
    return rows


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _authority_canonical_sha256(payload: object) -> str:
    """Match the inventory-authority writer's canonical JSON encoding."""

    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _scenario_order_sha256(scenario_names: Iterable[str]) -> str:
    return hashlib.sha256(
        ("\n".join(scenario_names) + "\n").encode("utf-8")
    ).hexdigest()


def _validate_authority_state_files(
    authority_root: Path,
    *,
    task: dict[str, Any],
    task_index: int,
) -> None:
    relative_state_dir = task.get("state_dir")
    if not isinstance(relative_state_dir, str) or not relative_state_dir:
        raise ActorSelectionVerificationError(
            f"Inventory authority task {task_index} has no state directory"
        )
    root = authority_root.resolve()
    state_dir = (root / relative_state_dir).resolve()
    try:
        state_dir.relative_to(root)
    except ValueError as exc:
        raise ActorSelectionVerificationError(
            f"Inventory authority task {task_index} state escapes its root"
        ) from exc
    if not state_dir.is_dir():
        raise ActorSelectionVerificationError(
            f"Inventory authority task {task_index} state directory is missing"
        )
    for filename, prefix in (
        ("registry_manifest.json", "registry_manifest"),
        ("tool_lifecycle.json", "tool_lifecycle"),
    ):
        expected_present = task.get(f"{prefix}_present")
        expected_sha256 = task.get(f"{prefix}_sha256")
        path = state_dir / filename
        if not isinstance(expected_present, bool):
            raise ActorSelectionVerificationError(
                f"Inventory authority task {task_index} has invalid {prefix} metadata"
            )
        if path.is_file() != expected_present:
            raise ActorSelectionVerificationError(
                f"Inventory authority task {task_index} {filename} presence drifted"
            )
        observed_sha256 = (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        )
        if observed_sha256 != expected_sha256:
            raise ActorSelectionVerificationError(
                f"Inventory authority task {task_index} {filename} digest drifted"
            )


def _validate_authority(authority_path: Path) -> tuple[dict[str, Any], list[str]]:
    authority = _read_json(authority_path)
    if (
        authority.get("artifact_type") != INVENTORY_AUTHORITY_ARTIFACT
        or authority.get("schema_version") != INVENTORY_AUTHORITY_SCHEMA_VERSION
        or authority.get("complete") is not True
        or authority.get("source_actor_selection_mode") != "policy"
        or not isinstance(authority.get("source_generation_enabled"), bool)
    ):
        raise ActorSelectionVerificationError(
            f"Invalid policy inventory authority: {authority_path}"
        )

    shared_context = authority.get("shared_context")
    if not isinstance(shared_context, dict) or authority.get(
        "shared_context_sha256"
    ) != _authority_canonical_sha256(shared_context):
        raise ActorSelectionVerificationError(
            "Inventory authority shared-context digest is invalid"
        )

    raw_names = authority.get("scenario_names")
    if not isinstance(raw_names, list) or not all(
        isinstance(name, str) for name in raw_names
    ):
        raise ActorSelectionVerificationError(
            f"Invalid policy inventory authority: {authority_path}"
        )
    scenario_names = [str(name) for name in raw_names]
    if len(set(scenario_names)) != len(scenario_names):
        raise ActorSelectionVerificationError(
            "Inventory authority scenario names are not unique"
        )
    tasks = authority.get("tasks")
    if not isinstance(tasks, list) or not all(isinstance(task, dict) for task in tasks):
        raise ActorSelectionVerificationError("Inventory authority tasks are malformed")
    if (
        authority.get("expected_task_count") != len(scenario_names)
        or authority.get("task_count") != len(scenario_names)
        or len(tasks) != len(scenario_names)
        or authority.get("scenario_order_sha256")
        != _scenario_order_sha256(scenario_names)
        or authority.get("tasks_sha256") != _authority_canonical_sha256(tasks)
    ):
        raise ActorSelectionVerificationError(
            "Inventory authority task sequence or digest is invalid"
        )
    for index, (scenario, task) in enumerate(zip(scenario_names, tasks)):
        if task.get("order_index") != index or task.get("scenario") != scenario:
            raise ActorSelectionVerificationError(
                f"Inventory authority task identity is invalid at index {index}"
            )
        _validate_authority_state_files(
            authority_path.parent,
            task=task,
            task_index=index,
        )
    return authority, scenario_names


def _schema_bundle_is_exact(bundle: object) -> bool:
    if not isinstance(bundle, dict):
        return False
    ordered = bundle.get("ordered_schemas")
    native = bundle.get("native_schemas")
    generated = bundle.get("generated_schemas")
    classification = bundle.get("schema_classification")
    if ordered is None:
        return native == [] and generated == [] and classification == []
    if not all(
        isinstance(value, list)
        for value in (ordered, native, generated, classification)
    ):
        return False
    if len(ordered) != len(classification):
        return False
    expected_native: list[object] = []
    expected_generated: list[object] = []
    for index, (schema, item) in enumerate(zip(ordered, classification)):
        if not isinstance(item, dict) or item.get("schema_index") != index:
            return False
        function = schema.get("function") if isinstance(schema, dict) else None
        schema_name = function.get("name") if isinstance(function, dict) else None
        if item.get("agent_facing_name") != str(schema_name or ""):
            return False
        if item.get("kind") == "native":
            expected_native.append(schema)
        elif item.get("kind") == "generated":
            expected_generated.append(schema)
        else:
            return False
    return native == expected_native and generated == expected_generated


def validate_actor_audit(
    run_dir: Path,
    *,
    expected_mode: str,
    expected_scenarios: Iterable[str],
    expected_model: str | None = None,
) -> dict[str, Any]:
    """Validate request coverage and the exact native/generated schema evidence."""

    expected_names = list(expected_scenarios)
    expected_name_set = set(expected_names)
    summary = _read_json(run_dir / "actor_request_audit_summary.json")
    if (
        summary.get("schema_version") != 1
        or summary.get("finalized") is not True
        or summary.get("expected_actor_selection_mode") != expected_mode
    ):
        raise ActorSelectionVerificationError(
            f"Actor audit metadata is invalid for {run_dir}"
        )
    if summary.get("coverage_verified") is not True:
        raise ActorSelectionVerificationError(
            f"Actor audit coverage failed for {run_dir}"
        )
    if summary.get("invariant_failure_request_ids"):
        raise ActorSelectionVerificationError(
            f"Actor audit invariants failed for {run_dir}"
        )

    catalog_payload = _read_json(run_dir / "actor_schema_catalog.json")
    raw_bundles = catalog_payload.get("bundles")
    if not isinstance(raw_bundles, dict) or not raw_bundles:
        raise ActorSelectionVerificationError(
            f"Actor schema catalog is empty for {run_dir}"
        )
    bundles: dict[str, dict[str, Any]] = {}
    for digest, bundle in raw_bundles.items():
        if not isinstance(digest, str) or not isinstance(bundle, dict):
            raise ActorSelectionVerificationError(
                f"Malformed actor schema catalog entry for {run_dir}"
            )
        if _canonical_sha256(bundle) != digest or not _schema_bundle_is_exact(bundle):
            raise ActorSelectionVerificationError(
                f"Actor schema catalog integrity failed for {run_dir}: {digest}"
            )
        bundles[digest] = bundle
    incremental_catalog_rows = _read_jsonl(run_dir / "actor_schema_catalog.jsonl")
    incremental_bundles: dict[str, dict[str, Any]] = {}
    for row in incremental_catalog_rows:
        digest = row.get("schema_catalog_sha256")
        bundle = row.get("bundle")
        if (
            not isinstance(digest, str)
            or not isinstance(bundle, dict)
            or digest in incremental_bundles
        ):
            raise ActorSelectionVerificationError(
                f"Malformed incremental actor schema catalog for {run_dir}"
            )
        incremental_bundles[digest] = bundle
    if incremental_bundles != bundles:
        raise ActorSelectionVerificationError(
            f"Incremental and consolidated actor schema catalogs differ for {run_dir}"
        )

    rows = _read_jsonl(run_dir / "actor_request_audit.jsonl")
    if (
        not rows
        or summary.get("request_count") != len(rows)
        or summary.get("persisted_event_count") != len(rows)
    ):
        raise ActorSelectionVerificationError(
            f"Actor request count is incomplete for {run_dir}"
        )
    usage_rows = _read_jsonl(run_dir / "llm_usage_events.jsonl")
    agent_usage_rows = [
        row for row in usage_rows if row.get("source") == "toolsandbox_agent"
    ]
    if summary.get("agent_call_count") != len(agent_usage_rows):
        raise ActorSelectionVerificationError(
            f"Actor usage count does not match the audit summary for {run_dir}"
        )
    usage_by_request_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for usage_row in agent_usage_rows:
        actor_request_id = usage_row.get("actor_request_id")
        if not isinstance(actor_request_id, str) or not actor_request_id:
            raise ActorSelectionVerificationError(
                f"Unlinked actor usage event in {run_dir}"
            )
        usage_by_request_id[actor_request_id].append(usage_row)

    routed_catalogs: dict[str, set[str]] = defaultdict(set)
    routed_schema_hashes: dict[str, set[str]] = defaultdict(set)
    sent_native_schema_instances = 0
    sent_generated_schema_instances = 0
    failed_request_count = 0
    complete_request_count = 0
    request_ids: set[str] = set()
    for row in rows:
        request_id = row.get("request_id")
        scenario = row.get("scenario")
        if (
            not isinstance(request_id, str)
            or not request_id
            or request_id in request_ids
        ):
            raise ActorSelectionVerificationError(
                f"Duplicate or invalid actor request ID in {run_dir}: {request_id!r}"
            )
        request_ids.add(request_id)
        if row.get("choice_mode") != expected_mode:
            raise ActorSelectionVerificationError(
                f"Unexpected actor mode in {run_dir}: {request_id}"
            )
        if expected_model is not None and row.get("model") != expected_model:
            raise ActorSelectionVerificationError(
                f"Unexpected actor model in {run_dir}: {request_id}"
            )
        if scenario not in expected_name_set:
            raise ActorSelectionVerificationError(
                f"Unexpected actor-audit scenario in {run_dir}: {scenario!r}"
            )
        if row.get("status") not in {"complete", "failed"}:
            raise ActorSelectionVerificationError(
                f"Unfinalized actor request in {run_dir}: {request_id}"
            )
        status = row.get("status")
        linked_usage = usage_by_request_id.get(request_id, [])
        if status == "failed":
            failed_request_count += 1
            if linked_usage:
                raise ActorSelectionVerificationError(
                    f"Failed actor request has a usage link in {run_dir}: {request_id}"
                )
        else:
            complete_request_count += 1
            if len(linked_usage) != 1:
                raise ActorSelectionVerificationError(
                    "Completed actor request must have exactly one usage link in "
                    f"{run_dir}: {request_id}"
                )
        if (
            row.get("messages_unchanged") is not True
            or row.get("sent_schemas_unchanged") is not True
        ):
            raise ActorSelectionVerificationError(
                f"Actor request inputs mutated in {run_dir}: {request_id}"
            )
        if expected_mode == "auto" and (
            row.get("named_tool_choice_absent") is not True
            or row.get("named_tool_choice") is not None
            or row.get("tool_choice") is not None
            or row.get("schemas_exact") is not True
        ):
            raise ActorSelectionVerificationError(
                f"Auto-selection request used policy intervention in {run_dir}: {request_id}"
            )
        for key in ("routed_schema_catalog_sha256", "sent_schema_catalog_sha256"):
            digest = row.get(key)
            if not isinstance(digest, str) or digest not in bundles:
                raise ActorSelectionVerificationError(
                    f"Actor request has no exact schema bundle in {run_dir}: {request_id}"
                )
        routed_digest = str(row["routed_schema_catalog_sha256"])
        sent_digest = str(row["sent_schema_catalog_sha256"])
        routed_schema_hash = row.get("routed_schemas_sha256")
        sent_schema_hash = row.get("sent_schemas_sha256")
        if (
            not isinstance(routed_schema_hash, str)
            or routed_schema_hash
            != _canonical_sha256(bundles[routed_digest]["ordered_schemas"])
            or not isinstance(sent_schema_hash, str)
            or sent_schema_hash
            != _canonical_sha256(bundles[sent_digest]["ordered_schemas"])
        ):
            raise ActorSelectionVerificationError(
                f"Actor request schema hash is invalid in {run_dir}: {request_id}"
            )
        if expected_mode == "auto" and (
            routed_digest != sent_digest or routed_schema_hash != sent_schema_hash
        ):
            raise ActorSelectionVerificationError(
                f"Auto-selection schemas differ from routed schemas in {run_dir}: "
                f"{request_id}"
            )
        routed_catalogs[str(scenario)].add(routed_digest)
        routed_schema_hashes[str(scenario)].add(routed_schema_hash)
        sent_bundle = bundles[sent_digest]
        native_count = len(sent_bundle["native_schemas"])
        generated_count = len(sent_bundle["generated_schemas"])
        if (
            row.get("native_schema_count") != native_count
            or row.get("generated_schema_count") != generated_count
        ):
            raise ActorSelectionVerificationError(
                f"Actor schema counts are invalid in {run_dir}: {request_id}"
            )
        sent_native_schema_instances += native_count
        sent_generated_schema_instances += generated_count

    unexpected_usage_ids = sorted(set(usage_by_request_id) - request_ids)
    if unexpected_usage_ids:
        raise ActorSelectionVerificationError(
            f"Actor usage references unknown requests in {run_dir}: "
            f"{unexpected_usage_ids[:10]}"
        )
    if (
        summary.get("complete_request_count") != complete_request_count
        or summary.get("failed_request_count") != failed_request_count
        or summary.get("linked_agent_call_count") != len(agent_usage_rows)
        or summary.get("unlinked_agent_call_count") != 0
        or summary.get("missing_usage_request_ids")
        or summary.get("unexpected_usage_request_ids")
        or summary.get("duplicate_usage_request_ids")
        or summary.get("mode_mismatch_request_ids")
    ):
        raise ActorSelectionVerificationError(
            f"Actor audit linkage summary is inconsistent for {run_dir}"
        )

    missing_scenarios = [name for name in expected_names if name not in routed_catalogs]
    if missing_scenarios:
        raise ActorSelectionVerificationError(
            f"Actor audit omitted scenarios in {run_dir}: {missing_scenarios[:10]}"
        )
    return {
        "mode": expected_mode,
        "request_count": len(rows),
        "complete_request_count": complete_request_count,
        "failed_request_count": failed_request_count,
        "schema_bundle_count": len(bundles),
        "sent_native_schema_instances": sent_native_schema_instances,
        "sent_generated_schema_instances": sent_generated_schema_instances,
        "routed_catalogs_by_scenario": {
            name: sorted(routed_catalogs[name]) for name in expected_names
        },
        "routed_schema_hashes_by_scenario": {
            name: sorted(routed_schema_hashes[name]) for name in expected_names
        },
        "coverage_verified": True,
        "exact_schema_catalog_verified": True,
    }


def _result_rows(
    run_dir: Path, expected_scenarios: Iterable[str]
) -> list[dict[str, Any]]:
    payload = _read_json(run_dir / "result_summary.json")
    raw_rows = payload.get("per_scenario_results")
    if not isinstance(raw_rows, list) or not all(
        isinstance(row, dict) for row in raw_rows
    ):
        raise ActorSelectionVerificationError(f"Malformed result summary: {run_dir}")
    rows = [dict(row) for row in raw_rows]
    expected_names = list(expected_scenarios)
    observed_names = [str(row.get("name") or "") for row in rows]
    if observed_names != expected_names:
        raise ActorSelectionVerificationError(
            f"Result task order does not match the authority for {run_dir}"
        )
    return rows


def validate_live_uncached_run(
    run_dir: Path,
    *,
    expected_scenarios: Iterable[str],
    allow_generation_source: bool = True,
    expected_models_by_source: dict[str, str] | None = None,
) -> dict[str, Any]:
    expected_names = list(expected_scenarios)
    rows = _result_rows(run_dir, expected_names)
    live_summary = _read_json(run_dir / "live_result_summary.json")
    if (
        live_summary.get("status") != "complete"
        or live_summary.get("completed_count") != len(expected_names)
        or live_summary.get("scenario_count") != len(expected_names)
        or live_summary.get("per_scenario_results") != rows
    ):
        raise ActorSelectionVerificationError(
            f"Live and final result summaries are not identically complete for {run_dir}"
        )
    rows_by_name = {str(row["name"]): row for row in rows}
    exception_rows: list[str] = []
    for row in rows:
        scenario = str(row["name"])
        for exception_field in ("exception_type", "traceback"):
            if exception_field not in row:
                raise ActorSelectionVerificationError(
                    f"actor-selection task {scenario!r} does not report runtime "
                    f"exception field {exception_field!r}"
                )
        if row["exception_type"] is not None or row["traceback"] is not None:
            exception_rows.append(scenario)
            continue
        validate_successful_retry_provenance(
            row,
            run_dir=run_dir,
            repo_root=REPO_ROOT,
            arm="actor-selection",
            scenario=scenario,
            error_type=ActorSelectionVerificationError,
        )
    for artifact_name in PERSISTENT_RESPONSE_CACHE_ARTIFACTS:
        artifact = run_dir / artifact_name
        if artifact.exists():
            raise ActorSelectionVerificationError(
                f"Run emitted forbidden persistent response-cache artifact: {artifact}"
            )

    usage_rows = _read_jsonl(run_dir / "llm_usage_events.jsonl")
    event_totals = {field: 0 for field in LLM_USAGE_INTEGER_FIELDS}
    scenario_totals = {
        name: {field: 0 for field in LLM_USAGE_INTEGER_FIELDS}
        for name in expected_names
    }
    source_totals: dict[str, dict[str, int]] = {}
    scenario_source_totals: dict[str, dict[str, dict[str, int]]] = {
        name: {} for name in expected_names
    }
    allowed_sources = {"toolsandbox_agent", "toolsandbox_user"}
    if allow_generation_source:
        allowed_sources.add("sage_generation")
    for index, event in enumerate(usage_rows, start=1):
        scenario = event.get("scenario")
        if not isinstance(scenario, str) or scenario not in rows_by_name:
            raise ActorSelectionVerificationError(
                f"LLM usage event {index} has an unknown scenario in {run_dir}"
            )
        source = event.get("source")
        if source not in allowed_sources:
            raise ActorSelectionVerificationError(
                f"LLM usage event {index} has an invalid source in {run_dir}"
            )
        if expected_models_by_source is not None and event.get("model") != (
            expected_models_by_source.get(str(source))
        ):
            raise ActorSelectionVerificationError(
                f"LLM usage event {index} has an invalid model in {run_dir}"
            )
        if event.get("response_cache_status") != "live":
            raise ActorSelectionVerificationError(
                f"Persistent response-cache reuse detected in {run_dir}"
            )
        if event.get("usage_available") is not True:
            raise ActorSelectionVerificationError(
                f"LLM usage event {index} has no API token usage in {run_dir}"
            )

        prompt_tokens = _required_nonnegative_int(
            event.get("prompt_tokens"),
            label=f"LLM usage event {index} prompt_tokens",
        )
        provider_cached_tokens = _required_nonnegative_int(
            event.get("provider_cached_prompt_tokens"),
            label=f"LLM usage event {index} provider_cached_prompt_tokens",
        )
        completion_tokens = _required_nonnegative_int(
            event.get("completion_tokens"),
            label=f"LLM usage event {index} completion_tokens",
        )
        total_tokens = _required_nonnegative_int(
            event.get("total_tokens"),
            label=f"LLM usage event {index} total_tokens",
        )
        if provider_cached_tokens > prompt_tokens:
            raise ActorSelectionVerificationError(
                f"LLM usage event {index} has impossible provider-cache tokens"
            )
        if total_tokens != prompt_tokens + completion_tokens:
            raise ActorSelectionVerificationError(
                f"LLM usage event {index} has inconsistent token totals"
            )
        raw_usage = event.get("raw_usage")
        if not isinstance(raw_usage, dict):
            raise ActorSelectionVerificationError(
                f"LLM usage event {index} has no raw API usage in {run_dir}"
            )
        raw_prompt_details = raw_usage.get("prompt_tokens_details")
        if not isinstance(raw_prompt_details, dict):
            raise ActorSelectionVerificationError(
                f"LLM usage event {index} has no raw prompt-token details"
            )
        raw_values = (
            _required_nonnegative_int(
                raw_usage.get("prompt_tokens"),
                label=f"LLM usage event {index} raw prompt_tokens",
            ),
            _required_nonnegative_int(
                raw_prompt_details.get("cached_tokens"),
                label=f"LLM usage event {index} raw cached_tokens",
            ),
            _required_nonnegative_int(
                raw_usage.get("completion_tokens"),
                label=f"LLM usage event {index} raw completion_tokens",
            ),
            _required_nonnegative_int(
                raw_usage.get("total_tokens"),
                label=f"LLM usage event {index} raw total_tokens",
            ),
        )
        if raw_values != (
            prompt_tokens,
            provider_cached_tokens,
            completion_tokens,
            total_tokens,
        ):
            raise ActorSelectionVerificationError(
                f"LLM usage event {index} disagrees with its raw API usage"
            )

        increments = {
            "llm_call_count": 1,
            "llm_live_call_count": 1,
            "llm_cached_call_count": 0,
            "llm_prompt_tokens": prompt_tokens,
            "llm_provider_cached_prompt_tokens": provider_cached_tokens,
            "llm_provider_cached_prompt_call_count": int(provider_cached_tokens > 0),
            "llm_provider_cached_prompt_tokens_available_count": 1,
            "llm_completion_tokens": completion_tokens,
            "llm_total_tokens": total_tokens,
            "llm_usage_available_count": 1,
        }
        for field, value in increments.items():
            event_totals[field] += value
            scenario_totals[scenario][field] += value
        source_key = str(source)
        source_total = source_totals.setdefault(
            source_key,
            {field: 0 for field in LLM_USAGE_SOURCE_INTEGER_FIELDS},
        )
        scenario_source_total = scenario_source_totals[scenario].setdefault(
            source_key,
            {field: 0 for field in LLM_USAGE_SOURCE_INTEGER_FIELDS},
        )
        for field in LLM_USAGE_SOURCE_INTEGER_FIELDS:
            source_total[field] += increments[field]
            scenario_source_total[field] += increments[field]

    for scenario, row in rows_by_name.items():
        expected = scenario_totals[scenario]
        for field in LLM_USAGE_INTEGER_FIELDS:
            observed = _required_nonnegative_int(
                row.get(field),
                label=f"Result row {scenario!r} field {field}",
            )
            if observed != expected[field]:
                raise ActorSelectionVerificationError(
                    f"Raw LLM usage events for {scenario!r} field {field!r} "
                    "do not match the result row"
                )
        if row.get("llm_usage_recorded") is not bool(expected["llm_call_count"]):
            raise ActorSelectionVerificationError(
                f"Result row {scenario!r} has inconsistent llm_usage_recorded"
            )
        if row.get("llm_usage_by_source") != dict(
            sorted(scenario_source_totals[scenario].items())
        ):
            raise ActorSelectionVerificationError(
                f"Raw LLM usage source totals do not match result row {scenario!r}"
            )

    usage_summary = _read_json(run_dir / "llm_usage_summary.json")
    if (
        usage_summary.get("schema_version") != 2
        or usage_summary.get("token_source") != "openai_chat_completion_usage"
        or usage_summary.get("llm_usage_recorded")
        is not bool(event_totals["llm_call_count"])
    ):
        raise ActorSelectionVerificationError(
            f"LLM usage summary metadata is invalid for {run_dir}"
        )
    for field in LLM_USAGE_INTEGER_FIELDS:
        observed = _required_nonnegative_int(
            usage_summary.get(field),
            label=f"LLM usage summary field {field}",
        )
        if observed != event_totals[field]:
            raise ActorSelectionVerificationError(
                f"LLM usage summary field {field!r} does not match raw events"
            )
    scenario_count_with_usage = sum(
        1 for totals in scenario_totals.values() if totals["llm_call_count"] > 0
    )
    if usage_summary.get("scenario_count_with_usage") != scenario_count_with_usage:
        raise ActorSelectionVerificationError(
            f"LLM usage summary scenario count does not match raw events in {run_dir}"
        )
    if usage_summary.get("llm_usage_by_source") != dict(sorted(source_totals.items())):
        raise ActorSelectionVerificationError(
            f"LLM usage source summary does not match raw events in {run_dir}"
        )
    side_effect_failure_scenarios: list[str] = []
    for row in rows:
        failures = row.get("side_effect_preservation_failures", [])
        if not isinstance(failures, list) or not all(
            isinstance(tool_name, str) for tool_name in failures
        ):
            raise ActorSelectionVerificationError(
                "Result row has malformed side-effect preservation failures for "
                f"{row.get('name')!r}"
            )
        if failures:
            side_effect_failure_scenarios.append(str(row["name"]))
    return {
        "scenario_count": len(rows),
        "llm_call_count": len(usage_rows),
        "cached_llm_call_count": 0,
        "runtime_exception_count": len(exception_rows),
        "runtime_exception_scenarios": exception_rows,
        "side_effect_preservation_failure_count": len(side_effect_failure_scenarios),
        "side_effect_preservation_failure_scenarios": side_effect_failure_scenarios,
    }


def _required_nonnegative_int(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ActorSelectionVerificationError(f"{label} must be a non-negative integer")
    return value


def _outcome_value(row: dict[str, Any]) -> float | None:
    raw = row.get("outcome_similarity")
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ActorSelectionVerificationError(
            f"Invalid outcome value for {row.get('name')!r}: {raw!r}"
        ) from exc
    if not 0.0 <= value <= 1.0:
        raise ActorSelectionVerificationError(
            f"Out-of-range outcome value for {row.get('name')!r}: {value}"
        )
    return value


def compare_outcome_values(
    policy_dir: Path,
    auto_dir: Path,
    *,
    expected_scenarios: Iterable[str],
) -> dict[str, Any]:
    """Compare only outcome-evaluator values; canonical similarity is excluded."""

    expected_names = list(expected_scenarios)
    policy_rows = _result_rows(policy_dir, expected_names)
    auto_rows = _result_rows(auto_dir, expected_names)
    paired_rows: list[dict[str, Any]] = []
    policy_values: list[float] = []
    auto_values: list[float] = []
    auto_wins = policy_wins = ties = 0
    for name, policy_row, auto_row in zip(expected_names, policy_rows, auto_rows):
        policy_value = _outcome_value(policy_row)
        auto_value = _outcome_value(auto_row)
        if (policy_value is None) != (auto_value is None):
            raise ActorSelectionVerificationError(
                f"Outcome-evaluator availability changed across arms for {name!r}"
            )
        delta = None
        if policy_value is not None and auto_value is not None:
            policy_values.append(policy_value)
            auto_values.append(auto_value)
            delta = auto_value - policy_value
            if delta > 0:
                auto_wins += 1
            elif delta < 0:
                policy_wins += 1
            else:
                ties += 1
        paired_rows.append(
            {
                "scenario": name,
                "policy_outcome_similarity": policy_value,
                "auto_outcome_similarity": auto_value,
                "auto_minus_policy_outcome_delta": delta,
            }
        )
    evaluated_count = len(policy_values)
    return {
        "endpoint": "outcome_task_completion_similarity",
        "canonical_similarity_included": False,
        "scenario_count": len(expected_names),
        "outcome_evaluated_count": evaluated_count,
        "outcome_not_evaluated_count": len(expected_names) - evaluated_count,
        "policy_exact_outcome_successes": sum(value == 1.0 for value in policy_values),
        "auto_exact_outcome_successes": sum(value == 1.0 for value in auto_values),
        "policy_mean_outcome_similarity": (
            sum(policy_values) / evaluated_count if evaluated_count else None
        ),
        "auto_mean_outcome_similarity": (
            sum(auto_values) / evaluated_count if evaluated_count else None
        ),
        "auto_minus_policy_mean_outcome_delta": (
            sum(auto - policy for policy, auto in zip(policy_values, auto_values))
            / evaluated_count
            if evaluated_count
            else None
        ),
        "auto_outcome_wins": auto_wins,
        "policy_outcome_wins": policy_wins,
        "outcome_ties": ties,
        "per_scenario_outcomes": paired_rows,
    }


def _selection_tool_list(
    row: dict[str, Any],
    field: str,
    *,
    scenario: str,
) -> list[str]:
    value = row.get(field)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ActorSelectionVerificationError(
            f"Selection row {scenario!r} has invalid {field}"
        )
    if len(set(value)) != len(value):
        raise ActorSelectionVerificationError(
            f"Selection row {scenario!r} duplicates tools in {field}"
        )
    return list(value)


def _selection_summary(
    run_dir: Path,
    *,
    expected_scenarios: Iterable[str],
) -> dict[str, Any]:
    expected_names = list(expected_scenarios)
    summary = _read_json(run_dir / "selection_summary.json")
    rows = _read_jsonl(run_dir / "scenario_tool_selection.jsonl")
    observed_names = [str(row.get("scenario") or "") for row in rows]
    if observed_names != expected_names:
        raise ActorSelectionVerificationError(
            f"Selection rows do not match the exact task order for {run_dir}"
        )

    visible_scenarios: list[str] = []
    called_scenarios: list[str] = []
    attempted_scenarios: list[str] = []
    failed_scenarios: list[str] = []
    attempted_without_success_scenarios: list[str] = []
    relevance_hidden_scenarios: list[str] = []
    for row, scenario in zip(rows, expected_names):
        visible = _selection_tool_list(
            row,
            "generated_tools_visible",
            scenario=scenario,
        )
        attempted = _selection_tool_list(
            row,
            "generated_tools_attempted",
            scenario=scenario,
        )
        failed = _selection_tool_list(
            row,
            "generated_tools_failed",
            scenario=scenario,
        )
        called = _selection_tool_list(
            row,
            "generated_tools_called",
            scenario=scenario,
        )
        expected_counts = {
            "visible_generated_tool_count": len(visible),
            "attempted_generated_tool_count": len(attempted),
            "failed_generated_tool_count": len(failed),
            "called_generated_tool_count": len(called),
        }
        for field, expected_count in expected_counts.items():
            if row.get(field) != expected_count:
                raise ActorSelectionVerificationError(
                    f"Selection row {scenario!r} has inconsistent {field}"
                )
        expected_status = (
            "generated_tool_called"
            if called
            else "generated_tool_attempt_failed"
            if failed
            else "generated_tool_attempted_without_success"
            if attempted
            else "generated_tool_visible_not_called"
            if visible
            else "no_visible_generated_tools"
        )
        if row.get("selection_status") != expected_status:
            raise ActorSelectionVerificationError(
                f"Selection row {scenario!r} has inconsistent selection_status"
            )
        relevance_hidden = row.get("relevance_gating_hid_retained_tool")
        if not isinstance(relevance_hidden, bool):
            raise ActorSelectionVerificationError(
                f"Selection row {scenario!r} has invalid relevance-gate status"
            )
        if visible:
            visible_scenarios.append(scenario)
        if called:
            called_scenarios.append(scenario)
        if attempted:
            attempted_scenarios.append(scenario)
        if failed:
            failed_scenarios.append(scenario)
        if attempted and not called and not failed:
            attempted_without_success_scenarios.append(scenario)
        if relevance_hidden:
            relevance_hidden_scenarios.append(scenario)

    derived_counts = {
        "scenario_count": len(rows),
        "generated_tool_visible_scenarios": len(visible_scenarios),
        "generated_tool_called_scenarios": len(called_scenarios),
        "generated_tool_attempted_scenarios": len(attempted_scenarios),
        "generated_tool_failed_scenarios": len(failed_scenarios),
        "relevance_gate_hidden_scenarios": len(relevance_hidden_scenarios),
    }
    for field, expected_count in derived_counts.items():
        if summary.get(field) != expected_count:
            raise ActorSelectionVerificationError(
                f"Selection summary field {field!r} does not match raw rows for "
                f"{run_dir}"
            )
    return {
        "generation_enabled": summary.get("generation_enabled"),
        "actor_selection_mode": summary.get("actor_selection_mode"),
        "inventory_authority_mode": summary.get("inventory_authority_mode"),
        "inventory_authority_task_count": summary.get("inventory_authority_task_count"),
        "inventory_authority_tasks_sha256": summary.get(
            "inventory_authority_tasks_sha256"
        ),
        **derived_counts,
        "generated_tool_visible_scenario_names": visible_scenarios,
        "generated_tool_called_scenario_names": called_scenarios,
        "generated_tool_attempted_scenario_names": attempted_scenarios,
        "generated_tool_failed_scenario_names": failed_scenarios,
        "generated_tool_attempted_without_success_scenarios": len(
            attempted_without_success_scenarios
        ),
        "generated_tool_attempted_without_success_scenario_names": (
            attempted_without_success_scenarios
        ),
        "relevance_gate_hidden_scenario_names": relevance_hidden_scenarios,
        "raw_selection_rows_verified": True,
    }


def verify_matched_actor_selection_experiment(
    *,
    policy_dir: Path,
    auto_dir: Path,
    authority_path: Path,
    require_zero_generated_tool_failures: bool = False,
) -> dict[str, Any]:
    """Return a complete gate report or raise before claiming a matched comparison."""

    authority, scenario_names = _validate_authority(authority_path)
    shared_context = authority["shared_context"]
    expected_agent_model = str(shared_context.get("agent") or "")
    expected_user_model = str(shared_context.get("user") or "")
    expected_generation_model = str(shared_context.get("generation_model") or "")
    if (
        not expected_agent_model
        or not expected_user_model
        or not expected_generation_model
    ):
        raise ActorSelectionVerificationError(
            "Inventory authority does not bind all actor, user, and generation models"
        )

    policy_selection = _selection_summary(
        policy_dir,
        expected_scenarios=scenario_names,
    )
    auto_selection = _selection_summary(
        auto_dir,
        expected_scenarios=scenario_names,
    )
    expected_tasks_sha256 = authority.get("tasks_sha256")
    if (
        policy_selection["actor_selection_mode"] != "policy"
        or policy_selection["inventory_authority_mode"] != "capture"
        or auto_selection["actor_selection_mode"] != "auto"
        or auto_selection["inventory_authority_mode"] != "replay"
        or policy_selection["generation_enabled"]
        is not authority["source_generation_enabled"]
        or auto_selection["generation_enabled"] is not False
        or policy_selection["inventory_authority_tasks_sha256"] != expected_tasks_sha256
        or auto_selection["inventory_authority_tasks_sha256"] != expected_tasks_sha256
        or policy_selection["inventory_authority_task_count"] != len(scenario_names)
        or auto_selection["inventory_authority_task_count"] != len(scenario_names)
    ):
        raise ActorSelectionVerificationError(
            "Policy capture and auto replay do not share one complete authority"
        )

    policy_audit = validate_actor_audit(
        policy_dir,
        expected_mode="policy",
        expected_scenarios=scenario_names,
        expected_model=expected_agent_model,
    )
    auto_audit = validate_actor_audit(
        auto_dir,
        expected_mode="auto",
        expected_scenarios=scenario_names,
        expected_model=expected_agent_model,
    )
    if (
        policy_audit["routed_catalogs_by_scenario"]
        != auto_audit["routed_catalogs_by_scenario"]
        or policy_audit["routed_schema_hashes_by_scenario"]
        != auto_audit["routed_schema_hashes_by_scenario"]
    ):
        raise ActorSelectionVerificationError(
            "Policy and auto actor requests did not receive the same routed schemas"
        )

    policy_execution = validate_live_uncached_run(
        policy_dir,
        expected_scenarios=scenario_names,
        allow_generation_source=bool(authority["source_generation_enabled"]),
        expected_models_by_source={
            "toolsandbox_agent": expected_agent_model,
            "toolsandbox_user": expected_user_model,
            "sage_generation": expected_generation_model,
        },
    )
    auto_execution = validate_live_uncached_run(
        auto_dir,
        expected_scenarios=scenario_names,
        allow_generation_source=False,
        expected_models_by_source={
            "toolsandbox_agent": expected_agent_model,
            "toolsandbox_user": expected_user_model,
        },
    )
    outcomes = compare_outcome_values(
        policy_dir,
        auto_dir,
        expected_scenarios=scenario_names,
    )
    gate_reasons: list[str] = []
    if policy_execution["runtime_exception_count"]:
        gate_reasons.append("policy_runtime_exceptions")
    if auto_execution["runtime_exception_count"]:
        gate_reasons.append("auto_runtime_exceptions")
    if policy_selection["generated_tool_called_scenarios"] < 1:
        gate_reasons.append("policy_generated_tools_not_called")
    if auto_selection["generated_tool_called_scenarios"] < 1:
        gate_reasons.append("auto_generated_tools_not_called")
    if require_zero_generated_tool_failures:
        if policy_selection["generated_tool_failed_scenarios"]:
            gate_reasons.append("policy_generated_tool_execution_failures")
        if auto_selection["generated_tool_failed_scenarios"]:
            gate_reasons.append("auto_generated_tool_execution_failures")
        if policy_selection["generated_tool_attempted_without_success_scenarios"]:
            gate_reasons.append("policy_generated_tool_attempts_without_success")
        if auto_selection["generated_tool_attempted_without_success_scenarios"]:
            gate_reasons.append("auto_generated_tool_attempts_without_success")
        if policy_execution["side_effect_preservation_failure_count"]:
            gate_reasons.append("policy_side_effect_preservation_failures")
        if auto_execution["side_effect_preservation_failure_count"]:
            gate_reasons.append("auto_side_effect_preservation_failures")

    return {
        "schema_version": 1,
        "experiment": "sage_auto_selection",
        "estimand": (
            "Actor-selection regime effect conditional on the policy donor's exact "
            "per-task adaptive registry, lifecycle, routing, and generated-tool schedule."
        ),
        "scenario_count": len(scenario_names),
        "authority_path": str(authority_path),
        "authority_sha256": hashlib.sha256(authority_path.read_bytes()).hexdigest(),
        "authority_tasks_sha256": expected_tasks_sha256,
        "policy_run_dir": str(policy_dir),
        "auto_run_dir": str(auto_dir),
        "policy_selection": policy_selection,
        "auto_selection": auto_selection,
        "policy_actor_audit": policy_audit,
        "auto_actor_audit": auto_audit,
        "policy_execution": policy_execution,
        "auto_execution": auto_execution,
        "routed_schemas_identical_by_scenario": True,
        "persistent_response_cache_reuse": False,
        "zero_generated_tool_failures_required": (require_zero_generated_tool_failures),
        "outcomes": outcomes,
        "stability_gate_passed": not gate_reasons,
        "stability_gate_reasons": gate_reasons,
    }
