"""Fail-closed external admission binding for verified legacy paper registries.

The September 11 paper registries predate the durable validation-contract
store.  Their original capability observations and validation-passed events
remain preserved.  This module reconstructs only the admission *input hashes*
needed by later blind-overlap and frozen-registry checks, without changing the
paper registry or exposing admission examples to a blind assessor.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

from sage_ts.generation.complete_tools import native_action_tool_enabled
from sage_ts.registry.manifest import RegistryEntry, code_hash
from sage_ts.registry.store import RegistryStore
from sage_ts.validation.sandbox_validator import (
    ToolExample,
    _with_native_action_structural_negatives,
)

SCHEMA_VERSION = 1
BINDING_TYPE = "legacy_paper_registry_admission_inputs"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PAPER_RUNTIME_COMMIT = "4ce1c6de0ab36dd59e1a319f4e56e298133f4a79"
_HISTORICAL_ONLINE_BIRTH_PATH = "src/sage_ts/orchestration/online_birth.py"
_HISTORICAL_ONLINE_BIRTH_SHA256 = (
    "8e63c8e1ff895ec4f6addc41fd8fef5cd88ec903be91a8cf9af8cd6ce8040602"
)


class LegacyAdmissionBindingError(ValueError):
    """Raised when archival admission provenance is incomplete or ambiguous."""


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise LegacyAdmissionBindingError("noncanonical_json_value") from exc


def _json_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _registry_identity(registry_dir: Path) -> dict[str, Any]:
    root = registry_dir.resolve()
    if not root.is_dir():
        raise LegacyAdmissionBindingError("registry_missing")
    files: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise LegacyAdmissionBindingError("registry_symlink_forbidden")
        if path.is_dir():
            continue
        if not path.is_file():
            raise LegacyAdmissionBindingError("registry_nonregular_file")
        files[path.relative_to(root).as_posix()] = {
            "sha256": file_sha256(path),
            "size_bytes": path.stat().st_size,
        }
    manifest = files.get("registry_manifest.json")
    if manifest is None:
        raise LegacyAdmissionBindingError("registry_manifest_missing")
    return {
        "path": str(root),
        "content_sha256": _json_sha256(files),
        "manifest_sha256": manifest["sha256"],
        "file_count": len(files),
    }


def _active_entries(registry_dir: Path) -> dict[str, RegistryEntry]:
    return {
        name: entry
        for name, entry in sorted(RegistryStore(registry_dir).load_entries().items())
        if not entry.retired
    }


def _read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise LegacyAdmissionBindingError(f"{label}_missing_or_symlink")
    rows: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            value = json.loads(line)
            if not isinstance(value, dict):
                raise LegacyAdmissionBindingError(f"{label}_row_not_object:{number}")
            _canonical_bytes(value)
            rows.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LegacyAdmissionBindingError(f"{label}_malformed") from exc
    return rows


def _spec_sha256(entry: RegistryEntry) -> str:
    return _json_sha256(entry.tool.spec.to_json())


def _historical_resolve_window_examples() -> list[dict[str, Any]]:
    """Read the special validation set from the exact paper runtime commit."""

    repo_root = Path(__file__).resolve().parents[3]
    try:
        source = subprocess.check_output(
            [
                "git",
                "show",
                f"{_PAPER_RUNTIME_COMMIT}:{_HISTORICAL_ONLINE_BIRTH_PATH}",
            ],
            cwd=repo_root,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise LegacyAdmissionBindingError(
            "historical_online_birth_unavailable"
        ) from exc
    if hashlib.sha256(source).hexdigest() != _HISTORICAL_ONLINE_BIRTH_SHA256:
        raise LegacyAdmissionBindingError("historical_online_birth_hash_changed")
    tree = ast.parse(source.decode("utf-8"))
    function = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "_resolve_window_validation_examples"
        ),
        None,
    )
    if function is None:
        raise LegacyAdmissionBindingError("historical_validation_function_missing")
    returned = next(
        (node for node in function.body if isinstance(node, ast.Return)), None
    )
    if returned is None or not isinstance(returned.value, (ast.Tuple, ast.List)):
        raise LegacyAdmissionBindingError("historical_validation_return_malformed")
    examples: list[dict[str, Any]] = []
    for item in returned.value.elts:
        if (
            not isinstance(item, ast.Call)
            or not isinstance(item.func, ast.Name)
            or item.func.id != "ToolExample"
            or len(item.args) < 2
        ):
            raise LegacyAdmissionBindingError("historical_validation_example_malformed")
        inputs = ast.literal_eval(item.args[0])
        expected = ast.literal_eval(item.args[1])
        keywords = {
            keyword.arg: ast.literal_eval(keyword.value) for keyword in item.keywords
        }
        if not isinstance(inputs, dict):
            raise LegacyAdmissionBindingError("historical_validation_inputs_malformed")
        examples.append(
            {
                "inputs": inputs,
                "expected": expected,
                "held_out": bool(keywords.get("held_out", False)),
                "negative_applicability": bool(
                    keywords.get("negative_applicability", False)
                ),
            }
        )
    if len(examples) != 6:
        raise LegacyAdmissionBindingError("historical_validation_example_count_changed")
    return examples


def build_legacy_admission_binding(
    *,
    registry_dir: Path,
    observations_path: Path,
    events_path: Path,
    output_path: Path,
    selected_cohort_manifest_path: Path,
    expected_selected_cohort_sha256: str,
) -> dict[str, Any]:
    """Recover exact admission-input hashes from preserved paper evidence."""

    selected_cohort_manifest_path = selected_cohort_manifest_path.resolve()
    if (
        not _SHA256.fullmatch(expected_selected_cohort_sha256)
        or not selected_cohort_manifest_path.is_file()
        or file_sha256(selected_cohort_manifest_path) != expected_selected_cohort_sha256
    ):
        raise LegacyAdmissionBindingError("selected_cohort_binding_invalid")
    identity = _registry_identity(registry_dir)
    entries = _active_entries(registry_dir)
    if not entries:
        raise LegacyAdmissionBindingError("active_registry_empty")
    observations_path = observations_path.resolve()
    events_path = events_path.resolve()
    observations = _read_jsonl(observations_path, "capability_observations")
    events = _read_jsonl(events_path, "validation_events")

    observation_sets: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in observations:
        key = row.get("canonical_key")
        examples = row.get("validation_examples")
        if not isinstance(key, str) or not key or not isinstance(examples, list):
            continue
        if not examples:
            continue
        for item in examples:
            if not isinstance(item, dict) or set(item) != {
                "inputs",
                "expected",
                "held_out",
                "negative_applicability",
            }:
                raise LegacyAdmissionBindingError(
                    f"malformed_validation_examples:{key}"
                )
            if not isinstance(item.get("inputs"), dict):
                raise LegacyAdmissionBindingError(f"malformed_admission_inputs:{key}")
            if not isinstance(item.get("held_out"), bool) or not isinstance(
                item.get("negative_applicability"), bool
            ):
                raise LegacyAdmissionBindingError(f"malformed_admission_flags:{key}")
        observation_sets.setdefault(key, {})[_json_sha256(examples)] = examples

    tools: dict[str, Any] = {}
    for name, entry in entries.items():
        matching_events = [
            row
            for row in events
            if row.get("event") == "validation_passed"
            and row.get("tool_name") == name
            and isinstance(row.get("code"), str)
            and code_hash(str(row["code"]))
            == (entry.stored_code_hash or code_hash(entry.tool.code))
        ]
        if len(matching_events) != 1:
            raise LegacyAdmissionBindingError(
                f"validation_event_match_count:{name}:{len(matching_events)}"
            )
        event = matching_events[0]
        canonical_key = event.get("canonical_key")
        if not isinstance(canonical_key, str) or not canonical_key:
            raise LegacyAdmissionBindingError(f"canonical_key_missing:{name}")
        unique_sets = observation_sets.get(canonical_key, {})
        if (
            name == "resolve_search_window_or_bounds"
            and canonical_key == "derived_value:resolve_search_window_or_bounds"
        ):
            historical = _historical_resolve_window_examples()
            unique_sets = {_json_sha256(historical): historical}
        if len(unique_sets) != 1:
            raise LegacyAdmissionBindingError(
                f"validation_example_set_count:{name}:{len(unique_sets)}"
            )
        examples_sha256, examples = next(iter(unique_sets.items()))
        if native_action_tool_enabled(entry.tool):
            expanded = _with_native_action_structural_negatives(
                tuple(
                    ToolExample(
                        inputs=dict(item["inputs"]),
                        expected=item.get("expected"),
                        held_out=bool(item["held_out"]),
                        negative_applicability=bool(item["negative_applicability"]),
                    )
                    for item in examples
                )
            )
            examples = [
                {
                    "inputs": item.inputs,
                    "expected": item.expected,
                    "held_out": item.held_out,
                    "negative_applicability": item.negative_applicability,
                }
                for item in expanded
            ]
            examples_sha256 = _json_sha256(examples)
        input_hashes = sorted({_json_sha256(item["inputs"]) for item in examples})
        if len(input_hashes) != len(examples):
            raise LegacyAdmissionBindingError(f"duplicate_admission_inputs:{name}")
        negative_examples = [
            item for item in examples if item["negative_applicability"]
        ]
        non_negative_examples = [
            item for item in examples if not item["negative_applicability"]
        ]
        marked_held_out = [
            item
            for item in examples
            if item["held_out"] and not item["negative_applicability"]
        ]
        if marked_held_out:
            source_count = sum(
                int(not item["held_out"] and not item["negative_applicability"])
                for item in examples
            )
            held_out_count = len(marked_held_out)
        elif len(non_negative_examples) >= 2:
            source_count = len(non_negative_examples) - 1
            held_out_count = 1
        else:
            source_count = len(non_negative_examples)
            held_out_count = 0
        negative_count = len(negative_examples)
        if (
            int(event.get("source_example_count") or -1)
            != entry.validation.source_example_count
            or int(event.get("held_out_check_count") or -1)
            != entry.validation.held_out_check_count
            or source_count != entry.validation.source_example_count
            or held_out_count != entry.validation.held_out_check_count
            or negative_count != entry.validation.negative_applicability_count
        ):
            raise LegacyAdmissionBindingError(f"validation_count_mismatch:{name}")
        tools[name] = {
            "tool_version": entry.version,
            "tool_code_sha256": entry.stored_code_hash or code_hash(entry.tool.code),
            "tool_spec_sha256": _spec_sha256(entry),
            "canonical_key": canonical_key,
            "validation_examples_sha256": examples_sha256,
            "admission_input_sha256": input_hashes,
            "admission_example_count": len(examples),
        }

    payload = {
        "schema_version": SCHEMA_VERSION,
        "binding_type": BINDING_TYPE,
        "construction": "deterministic_exact_recovery_from_preserved_paper_evidence",
        "registry": identity,
        "selected_cohort_manifest": {
            "path": str(selected_cohort_manifest_path),
            "sha256": expected_selected_cohort_sha256,
        },
        "sources": {
            "capability_observations": {
                "path": str(observations_path),
                "sha256": file_sha256(observations_path),
                "row_count": len(observations),
            },
            "validation_events": {
                "path": str(events_path),
                "sha256": file_sha256(events_path),
                "row_count": len(events),
            },
        },
        "historical_source": {
            "git_commit": _PAPER_RUNTIME_COMMIT,
            "path": _HISTORICAL_ONLINE_BIRTH_PATH,
            "sha256": _HISTORICAL_ONLINE_BIRTH_SHA256,
            "use": "resolve_search_window_or_bounds_validation_examples",
        },
        "active_tool_count": len(entries),
        "active_tool_names_sha256": _json_sha256(list(entries)),
        "tools": tools,
    }
    output_path = output_path.resolve()
    if output_path.exists() or output_path.is_symlink():
        raise FileExistsError(f"Legacy admission binding already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output_path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return payload


def verify_legacy_admission_binding(
    *,
    binding_path: Path,
    expected_sha256: str,
    registry_dir: Path,
) -> dict[str, set[str]]:
    """Verify a sealed external binding against an exact frozen registry."""

    binding_path = binding_path.resolve()
    if (
        not _SHA256.fullmatch(expected_sha256)
        or binding_path.is_symlink()
        or not binding_path.is_file()
        or file_sha256(binding_path) != expected_sha256
    ):
        raise LegacyAdmissionBindingError("legacy_binding_hash_invalid")
    try:
        payload = json.loads(binding_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LegacyAdmissionBindingError("legacy_binding_malformed") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise LegacyAdmissionBindingError("legacy_binding_schema_invalid")
    if payload.get("binding_type") != BINDING_TYPE:
        raise LegacyAdmissionBindingError("legacy_binding_type_invalid")
    identity = _registry_identity(registry_dir)
    bound_registry = payload.get("registry")
    if not isinstance(bound_registry, Mapping):
        raise LegacyAdmissionBindingError("legacy_binding_registry_invalid")
    for key in ("content_sha256", "manifest_sha256", "file_count"):
        if bound_registry.get(key) != identity.get(key):
            raise LegacyAdmissionBindingError(f"legacy_binding_registry_{key}_mismatch")
    for source in (
        payload.get("selected_cohort_manifest"),
        *(
            payload.get("sources", {}).values()
            if isinstance(payload.get("sources"), Mapping)
            else ()
        ),
    ):
        if not isinstance(source, Mapping):
            raise LegacyAdmissionBindingError("legacy_binding_source_invalid")
        path = Path(str(source.get("path") or "")).resolve()
        if (
            not path.is_file()
            or path.is_symlink()
            or file_sha256(path) != source.get("sha256")
        ):
            raise LegacyAdmissionBindingError("legacy_binding_source_changed")
    entries = _active_entries(registry_dir)
    historical_source = payload.get("historical_source")
    if not isinstance(historical_source, Mapping) or historical_source != {
        "git_commit": _PAPER_RUNTIME_COMMIT,
        "path": _HISTORICAL_ONLINE_BIRTH_PATH,
        "sha256": _HISTORICAL_ONLINE_BIRTH_SHA256,
        "use": "resolve_search_window_or_bounds_validation_examples",
    }:
        raise LegacyAdmissionBindingError("legacy_binding_historical_source_invalid")
    _historical_resolve_window_examples()
    raw_tools = payload.get("tools")
    if not isinstance(raw_tools, Mapping) or set(raw_tools) != set(entries):
        raise LegacyAdmissionBindingError("legacy_binding_tool_roster_mismatch")
    verified: dict[str, set[str]] = {}
    for name, entry in entries.items():
        row = raw_tools.get(name)
        if not isinstance(row, Mapping):
            raise LegacyAdmissionBindingError(f"legacy_binding_tool_invalid:{name}")
        expected = {
            "tool_version": entry.version,
            "tool_code_sha256": entry.stored_code_hash or code_hash(entry.tool.code),
            "tool_spec_sha256": _spec_sha256(entry),
        }
        if any(row.get(key) != value for key, value in expected.items()):
            raise LegacyAdmissionBindingError(f"legacy_binding_tool_mismatch:{name}")
        hashes = row.get("admission_input_sha256")
        if (
            not isinstance(hashes, list)
            or not hashes
            or any(
                not isinstance(item, str) or not _SHA256.fullmatch(item)
                for item in hashes
            )
            or len(set(hashes)) != len(hashes)
        ):
            raise LegacyAdmissionBindingError(f"legacy_binding_inputs_invalid:{name}")
        verified[name] = set(hashes)
    if payload.get("active_tool_count") != len(entries) or payload.get(
        "active_tool_names_sha256"
    ) != _json_sha256(list(entries)):
        raise LegacyAdmissionBindingError("legacy_binding_active_roster_invalid")
    return verified


__all__ = [
    "LegacyAdmissionBindingError",
    "build_legacy_admission_binding",
    "file_sha256",
    "verify_legacy_admission_binding",
]
