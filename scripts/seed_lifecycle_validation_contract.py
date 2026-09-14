#!/usr/bin/env python3
"""Bind the development-only historical fault fixture to its frozen contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from sage_ts.adequacy.inadequacy_classifier import (
    _relative_day_time_timestamp_observation,
    _reminder_creation_finalizer_observation,
    _safe_action_or_abstain_observation,
)
from sage_ts.registry.store import RegistryStore
from sage_ts.registry.validation_contracts import (
    VALIDATION_CONTRACT_BINDING_SCHEMA_VERSION,
    ValidationContractBindingStore,
)

TOOL_NAME = "prepare_safe_action_or_abstain"
CONTRACT_FACTORIES = {
    TOOL_NAME: _safe_action_or_abstain_observation,
    "relative_day_time_to_timestamp": _relative_day_time_timestamp_observation,
    "prepare_reminder_creation_args": _reminder_creation_finalizer_observation,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seed_binding(
    *,
    registry_dir: Path,
    fixture_path: Path,
    receipt_path: Path,
) -> dict[str, object]:
    """Install only the predeclared synthetic validator contract for fixture v1."""

    registry_manifest = registry_dir / "registry_manifest.json"
    if not fixture_path.is_file() or not registry_manifest.is_file():
        raise ValueError("fixture and installed registry manifest must both exist")
    fixture_sha256 = _sha256(fixture_path)
    if _sha256(registry_manifest) != fixture_sha256:
        raise ValueError("installed historical fixture bytes do not match source")
    store = RegistryStore(registry_dir)
    entries = store.load_entries()
    if set(entries) != set(CONTRACT_FACTORIES):
        raise ValueError(
            "historical fixture tools do not match the predeclared contract set"
        )
    binding_store = ValidationContractBindingStore(registry_dir)
    bindings: dict[str, dict[str, object]] = {}
    for tool_name, entry in sorted(entries.items()):
        if entry.version != 1 or entry.retired or not entry.code_hash_verified:
            raise ValueError(
                f"historical fixture tool {tool_name!r} is not exact active version 1"
            )
        observation = CONTRACT_FACTORIES[tool_name](
            "development_synthetic_validation_contract"
        )
        binding = binding_store.persist(
            entry,
            observation,
            validation_examples=observation.validation_examples,
        )
        blob_path = binding_store.blob_directory / f"{binding.contract_hash}.json"
        bindings[tool_name] = {
            "tool_name": binding.tool_name,
            "tool_version": binding.tool_version,
            "tool_code_hash": binding.tool_code_hash,
            "tool_spec_hash": binding.tool_spec_hash,
            "canonical_key": binding.canonical_key,
            "contract_hash": binding.contract_hash,
            "binding_blob_path": str(blob_path.resolve()),
            "binding_blob_sha256": _sha256(blob_path),
        }
    index_path = binding_store.index_path
    receipt: dict[str, object] = {
        "receipt_type": "development_only_historical_validation_contract_bindings",
        "fixture_sha256": fixture_sha256,
        "binding_count": len(bindings),
        "bindings": bindings,
        "contract_schema_version": VALIDATION_CONTRACT_BINDING_SCHEMA_VERSION,
        "contract_provenance": "predeclared_synthetic_validator_contract",
        "held_out_usage": "validator_and_model_selection_only",
        "benchmark_identifiers_persisted": False,
        "binding_index_path": str(index_path.resolve()),
        "binding_index_sha256": _sha256(index_path),
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-dir", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    receipt = seed_binding(
        registry_dir=args.registry_dir,
        fixture_path=args.fixture,
        receipt_path=args.receipt,
    )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
