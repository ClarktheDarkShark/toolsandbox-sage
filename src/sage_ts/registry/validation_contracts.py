"""Durable, content-addressed validation contracts for generated tools.

The registry manifest proves which implementation is active.  This companion
store proves which synthetic public contract admitted that exact implementation
and version.  Contract values are validator/model-selection data: callers may
use them for deterministic validation, while generation must continue to apply
its held-out filtering before constructing a model prompt.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sage_ts.adequacy.inadequacy_classifier import CapabilityObservation
from sage_ts.registry.manifest import RegistryEntry, code_hash
from sage_ts.validation.sandbox_validator import ToolExample

VALIDATION_CONTRACT_BINDING_SCHEMA_VERSION = 2
VALIDATION_CONTRACT_INDEX_FILENAME = "validation_contract_bindings.json"
VALIDATION_CONTRACT_BLOB_DIRECTORY = "validation_contracts"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ValidationContractBindingError(ValueError):
    """Raised when a binding cannot be written without weakening integrity."""


def _is_positive_int(value: Any) -> bool:
    """Reject JSON booleans, which otherwise compare equal to integers."""

    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


@dataclass(frozen=True)
class ResolvedValidationContract:
    """A verified binding reconstructed without any benchmark identifier."""

    tool_name: str
    tool_version: int
    tool_code_hash: str
    tool_spec_hash: str
    canonical_key: str
    contract_hash: str
    observation: CapabilityObservation


def _canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _content_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _string_tuple(value: Any, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValidationContractBindingError(f"malformed_{field_name}")
    return tuple(value)


def _contract_payload(
    entry: RegistryEntry,
    observation: CapabilityObservation,
    validation_examples: tuple[ToolExample, ...],
) -> dict[str, Any]:
    inadequacy = observation.to_inadequacy_evidence()
    return {
        "schema_version": VALIDATION_CONTRACT_BINDING_SCHEMA_VERSION,
        "tool_name": entry.tool.spec.tool_name,
        "tool_version": entry.version,
        "tool_code_hash": entry.stored_code_hash or code_hash(entry.tool.code),
        "tool_spec_hash": _content_hash(entry.tool.spec.to_json()),
        "canonical_key": observation.canonical_key,
        # Deliberately exclude scenario_name and task_context_label.  They are
        # unnecessary for validation and may contain benchmark identifiers.
        "contract": {
            "observation": observation.observation,
            "allowed_families": list(observation.allowed_families),
            "validation_examples": [
                {
                    "inputs": example.inputs,
                    "expected": example.expected,
                    "held_out": example.held_out,
                    "negative_applicability": example.negative_applicability,
                }
                for example in validation_examples
            ],
            "generation_allowed": observation.generation_allowed,
            "reason": observation.reason,
            "task_family_key": observation.task_family_key,
            "inadequacy_evidence": {
                "signals": list(inadequacy.signals),
                "failed_tool_calls": list(inadequacy.failed_tool_calls),
                "repeated_failed_tool_calls": list(
                    inadequacy.repeated_failed_tool_calls
                ),
                "visible_data_gaps": list(inadequacy.visible_data_gaps),
                "planner_failures": list(inadequacy.planner_failures),
                "final_answer_route_mismatch": inadequacy.final_answer_route_mismatch,
            },
        },
    }


def _observation_from_payload(payload: dict[str, Any]) -> CapabilityObservation:
    expected_payload_keys = {
        "schema_version",
        "tool_name",
        "tool_version",
        "tool_code_hash",
        "tool_spec_hash",
        "canonical_key",
        "contract",
    }
    if set(payload) != expected_payload_keys:
        raise ValidationContractBindingError("malformed_contract_payload_fields")
    contract = payload.get("contract")
    expected_contract_keys = {
        "observation",
        "allowed_families",
        "validation_examples",
        "generation_allowed",
        "reason",
        "task_family_key",
        "inadequacy_evidence",
    }
    if not isinstance(contract, dict) or set(contract) != expected_contract_keys:
        raise ValidationContractBindingError("malformed_contract_fields")
    if not isinstance(contract.get("observation"), str):
        raise ValidationContractBindingError("malformed_contract_observation")
    if not isinstance(contract.get("reason"), str):
        raise ValidationContractBindingError("malformed_contract_reason")
    if not isinstance(contract.get("task_family_key"), str):
        raise ValidationContractBindingError("malformed_contract_task_family_key")
    generation_allowed = contract.get("generation_allowed")
    if not isinstance(generation_allowed, bool):
        raise ValidationContractBindingError("malformed_contract_generation_allowed")

    raw_examples = contract.get("validation_examples")
    if not isinstance(raw_examples, list) or not raw_examples:
        raise ValidationContractBindingError("malformed_validation_examples")
    examples: list[ToolExample] = []
    expected_example_keys = {
        "inputs",
        "expected",
        "held_out",
        "negative_applicability",
    }
    for item in raw_examples:
        if not isinstance(item, dict) or set(item) != expected_example_keys:
            raise ValidationContractBindingError("malformed_validation_example")
        if not isinstance(item.get("inputs"), dict):
            raise ValidationContractBindingError("malformed_validation_example_inputs")
        held_out = item.get("held_out")
        negative = item.get("negative_applicability")
        if not isinstance(held_out, bool) or not isinstance(negative, bool):
            raise ValidationContractBindingError("malformed_validation_example_flags")
        examples.append(
            ToolExample(
                inputs=dict(item["inputs"]),
                expected=item.get("expected"),
                held_out=held_out,
                negative_applicability=negative,
            )
        )

    evidence = contract.get("inadequacy_evidence")
    expected_evidence_keys = {
        "signals",
        "failed_tool_calls",
        "repeated_failed_tool_calls",
        "visible_data_gaps",
        "planner_failures",
        "final_answer_route_mismatch",
    }
    if not isinstance(evidence, dict) or set(evidence) != expected_evidence_keys:
        raise ValidationContractBindingError("malformed_inadequacy_evidence")
    final_answer_route_mismatch = evidence.get("final_answer_route_mismatch")
    if not isinstance(final_answer_route_mismatch, bool):
        raise ValidationContractBindingError("malformed_final_answer_route_mismatch")
    canonical_key = payload.get("canonical_key")
    if not isinstance(canonical_key, str) or not canonical_key.strip():
        raise ValidationContractBindingError("malformed_canonical_key")
    synthetic_label = f"validation_contract:{canonical_key}"
    return CapabilityObservation(
        scenario_name=synthetic_label,
        canonical_key=canonical_key,
        observation=str(contract["observation"]),
        allowed_families=_string_tuple(
            contract.get("allowed_families"), field_name="allowed_families"
        ),
        validation_examples=tuple(examples),
        generation_allowed=generation_allowed,
        reason=str(contract["reason"]),
        inadequacy_signals=_string_tuple(
            evidence.get("signals"), field_name="inadequacy_signals"
        ),
        failed_tool_calls=_string_tuple(
            evidence.get("failed_tool_calls"), field_name="failed_tool_calls"
        ),
        repeated_failed_tool_calls=_string_tuple(
            evidence.get("repeated_failed_tool_calls"),
            field_name="repeated_failed_tool_calls",
        ),
        visible_data_gaps=_string_tuple(
            evidence.get("visible_data_gaps"), field_name="visible_data_gaps"
        ),
        planner_failures=_string_tuple(
            evidence.get("planner_failures"), field_name="planner_failures"
        ),
        final_answer_route_mismatch=final_answer_route_mismatch,
        evidence_source="persisted_validation_contract",
        task_context_label="",
        task_family_key=str(contract["task_family_key"]),
    )


class ValidationContractBindingStore:
    """Persist and verify immutable contract blobs plus a versioned index."""

    def __init__(self, registry_root: Path) -> None:
        self.registry_root = registry_root
        self.index_path = registry_root / VALIDATION_CONTRACT_INDEX_FILENAME
        self.blob_directory = registry_root / VALIDATION_CONTRACT_BLOB_DIRECTORY

    @staticmethod
    def _empty_index() -> dict[str, Any]:
        return {
            "schema_version": VALIDATION_CONTRACT_BINDING_SCHEMA_VERSION,
            "bindings": {},
        }

    def _load_index(self, *, require_existing: bool) -> dict[str, Any]:
        if self.index_path.is_symlink():
            raise ValidationContractBindingError("binding_index_symlink")
        if not self.index_path.exists():
            if require_existing:
                raise ValidationContractBindingError("binding_index_missing")
            return self._empty_index()
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValidationContractBindingError("binding_index_malformed") from exc
        if (
            not isinstance(payload, dict)
            or set(payload) != {"schema_version", "bindings"}
            or not _is_positive_int(payload.get("schema_version"))
            or payload["schema_version"] != VALIDATION_CONTRACT_BINDING_SCHEMA_VERSION
            or not isinstance(payload.get("bindings"), dict)
        ):
            raise ValidationContractBindingError("binding_index_malformed")
        return payload

    def persist(
        self,
        entry: RegistryEntry,
        observation: CapabilityObservation,
        *,
        validation_examples: tuple[ToolExample, ...],
    ) -> ResolvedValidationContract:
        if not entry.code_hash_verified:
            raise ValidationContractBindingError("registry_code_hash_mismatch")
        if not _is_positive_int(entry.version):
            raise ValidationContractBindingError("registry_version_malformed")
        if entry.tool.spec.tool_name != str(entry.tool.spec.tool_name).strip():
            raise ValidationContractBindingError("malformed_tool_name")
        try:
            payload = _contract_payload(entry, observation, validation_examples)
        except (TypeError, ValueError) as exc:
            raise ValidationContractBindingError(
                "registry_tool_spec_malformed"
            ) from exc
        digest = _content_hash(payload)
        index = self._load_index(require_existing=False)
        bindings = dict(index["bindings"])
        raw_versions = bindings.get(entry.tool.spec.tool_name, {})
        if not isinstance(raw_versions, dict):
            raise ValidationContractBindingError("binding_versions_malformed")
        versions = dict(raw_versions)
        version_key = str(entry.version)
        metadata = {
            "tool_version": entry.version,
            "tool_code_hash": entry.stored_code_hash,
            "tool_spec_hash": payload["tool_spec_hash"],
            "canonical_key": observation.canonical_key,
            "contract_hash": digest,
        }
        prior = versions.get(version_key)
        if prior is not None and prior != metadata:
            raise ValidationContractBindingError("binding_version_conflict")

        if self.blob_directory.is_symlink():
            raise ValidationContractBindingError("binding_blob_directory_symlink")
        self.blob_directory.mkdir(parents=True, exist_ok=True)
        blob_path = self.blob_directory / f"{digest}.json"
        if blob_path.is_symlink():
            raise ValidationContractBindingError("binding_blob_symlink")
        if blob_path.exists():
            try:
                existing = json.loads(blob_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValidationContractBindingError("binding_blob_malformed") from exc
            try:
                existing_digest = (
                    _content_hash(existing) if isinstance(existing, dict) else ""
                )
            except (TypeError, ValueError) as exc:
                raise ValidationContractBindingError("binding_blob_malformed") from exc
            if not isinstance(existing, dict) or existing_digest != digest:
                raise ValidationContractBindingError("binding_blob_hash_mismatch")
        else:
            _atomic_write_json(blob_path, payload)
        versions[version_key] = metadata
        bindings[entry.tool.spec.tool_name] = versions
        _atomic_write_json(
            self.index_path,
            {
                "schema_version": VALIDATION_CONTRACT_BINDING_SCHEMA_VERSION,
                "bindings": bindings,
            },
        )
        resolved, error = self.resolve(entry)
        if resolved is None:
            raise ValidationContractBindingError(error or "binding_verification_failed")
        return resolved

    def resolve(
        self, entry: RegistryEntry
    ) -> tuple[ResolvedValidationContract | None, str | None]:
        tool_name = entry.tool.spec.tool_name
        actual_code_hash = code_hash(entry.tool.code)
        if not entry.code_hash_verified or entry.stored_code_hash != actual_code_hash:
            return None, "registry_code_hash_mismatch"
        try:
            try:
                actual_tool_spec_hash = _content_hash(entry.tool.spec.to_json())
            except (TypeError, ValueError) as exc:
                raise ValidationContractBindingError(
                    "registry_tool_spec_malformed"
                ) from exc
            index = self._load_index(require_existing=True)
            raw_versions = index["bindings"].get(tool_name)
            if not isinstance(raw_versions, dict):
                raise ValidationContractBindingError("binding_missing")
            metadata = raw_versions.get(str(entry.version))
            expected_metadata_keys = {
                "tool_version",
                "tool_code_hash",
                "tool_spec_hash",
                "canonical_key",
                "contract_hash",
            }
            if (
                not isinstance(metadata, dict)
                or set(metadata) != expected_metadata_keys
            ):
                raise ValidationContractBindingError("binding_missing_or_malformed")
            digest = metadata.get("contract_hash")
            if not isinstance(digest, str) or not _SHA256_PATTERN.fullmatch(digest):
                raise ValidationContractBindingError("binding_hash_malformed")
            metadata_version = metadata.get("tool_version")
            if (
                not _is_positive_int(metadata_version)
                or metadata_version != entry.version
            ):
                raise ValidationContractBindingError("binding_version_mismatch")
            if metadata.get("tool_code_hash") != actual_code_hash:
                raise ValidationContractBindingError("binding_code_hash_mismatch")
            metadata_spec_hash = metadata.get("tool_spec_hash")
            if (
                not isinstance(metadata_spec_hash, str)
                or not _SHA256_PATTERN.fullmatch(metadata_spec_hash)
                or metadata_spec_hash != actual_tool_spec_hash
            ):
                raise ValidationContractBindingError("binding_tool_spec_hash_mismatch")
            canonical_key = metadata.get("canonical_key")
            if not isinstance(canonical_key, str) or not canonical_key:
                raise ValidationContractBindingError("binding_canonical_key_malformed")
            if self.blob_directory.is_symlink():
                raise ValidationContractBindingError("binding_blob_directory_symlink")
            blob_path = self.blob_directory / f"{digest}.json"
            if not blob_path.exists():
                raise ValidationContractBindingError("binding_blob_missing")
            if blob_path.is_symlink():
                raise ValidationContractBindingError("binding_blob_symlink")
            try:
                payload = json.loads(blob_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValidationContractBindingError("binding_blob_malformed") from exc
            if not isinstance(payload, dict):
                raise ValidationContractBindingError("binding_blob_malformed")
            try:
                observed_digest = _content_hash(payload)
            except (TypeError, ValueError) as exc:
                raise ValidationContractBindingError("binding_blob_malformed") from exc
            if observed_digest != digest:
                raise ValidationContractBindingError("binding_blob_hash_mismatch")
            payload_schema_version = payload.get("schema_version")
            if (
                not _is_positive_int(payload_schema_version)
                or payload_schema_version != VALIDATION_CONTRACT_BINDING_SCHEMA_VERSION
            ):
                raise ValidationContractBindingError("binding_schema_version_mismatch")
            if payload.get("tool_name") != tool_name:
                raise ValidationContractBindingError("binding_tool_name_mismatch")
            payload_tool_version = payload.get("tool_version")
            if (
                not _is_positive_int(payload_tool_version)
                or payload_tool_version != entry.version
            ):
                raise ValidationContractBindingError("binding_version_mismatch")
            if payload.get("tool_code_hash") != actual_code_hash:
                raise ValidationContractBindingError("binding_code_hash_mismatch")
            if payload.get("tool_spec_hash") != actual_tool_spec_hash:
                raise ValidationContractBindingError("binding_tool_spec_hash_mismatch")
            if payload.get("canonical_key") != canonical_key:
                raise ValidationContractBindingError("binding_canonical_key_mismatch")
            observation = _observation_from_payload(payload)
        except ValidationContractBindingError as exc:
            return None, str(exc)
        return (
            ResolvedValidationContract(
                tool_name=tool_name,
                tool_version=entry.version,
                tool_code_hash=actual_code_hash,
                tool_spec_hash=actual_tool_spec_hash,
                canonical_key=str(metadata["canonical_key"]),
                contract_hash=str(metadata["contract_hash"]),
                observation=observation,
            ),
            None,
        )

    def restore(
        self, entries: dict[str, RegistryEntry]
    ) -> tuple[dict[str, ResolvedValidationContract], dict[str, str]]:
        resolved: dict[str, ResolvedValidationContract] = {}
        failures: dict[str, str] = {}
        for tool_name, entry in entries.items():
            if tool_name != entry.tool.spec.tool_name:
                failures[tool_name] = "registry_tool_name_mismatch"
                continue
            binding, error = self.resolve(entry)
            if binding is None:
                failures[tool_name] = error or "binding_invalid"
            else:
                resolved[tool_name] = binding
        return resolved, failures
