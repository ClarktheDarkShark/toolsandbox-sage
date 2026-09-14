from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path
from types import SimpleNamespace

from sage_ts.orchestration.online_birth import OnlineBirthController
from sage_ts.registry.store import RegistryStore
from sage_ts.registry.validation_contracts import (
    VALIDATION_CONTRACT_BINDING_SCHEMA_VERSION,
    ValidationContractBindingStore,
)
from scripts.seed_lifecycle_validation_contract import seed_binding

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    REPOSITORY_ROOT
    / "docs"
    / "sage_protocol"
    / "fixtures"
    / "historical_faulty_safe_action_registry.json"
)
TOOL_NAME = "prepare_safe_action_or_abstain"
PINNED_CONTRACT_HASH = (
    "74b6ecf95169da106c92ddcf4bc8a843725bcc4741cb49dd96a5386550a6df01"
)


def _seed(tmp_path: Path) -> tuple[RegistryStore, dict[str, object]]:
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    shutil.copy2(FIXTURE, registry_dir / "registry_manifest.json")
    receipt = seed_binding(
        registry_dir=registry_dir,
        fixture_path=FIXTURE,
        receipt_path=tmp_path / "seed_receipt.json",
    )
    return RegistryStore(registry_dir), receipt


def test_development_fixture_seed_is_content_addressed_and_restorable(
    tmp_path: Path,
) -> None:
    store, receipt = _seed(tmp_path)

    binding_receipt = receipt["bindings"][TOOL_NAME]
    assert binding_receipt["contract_hash"] == PINNED_CONTRACT_HASH
    assert binding_receipt["tool_version"] == 1
    assert len(binding_receipt["tool_spec_hash"]) == 64
    assert receipt["binding_count"] == 3
    assert (
        receipt["contract_schema_version"] == VALIDATION_CONTRACT_BINDING_SCHEMA_VERSION
    )
    assert receipt["benchmark_identifiers_persisted"] is False
    blob_path = store.root / "validation_contracts" / f"{PINNED_CONTRACT_HASH}.json"
    blob = json.loads(blob_path.read_text())
    assert "scenario_name" not in blob
    assert "task_context_label" not in blob

    events: list[tuple[str, dict[str, object]]] = []
    controller = OnlineBirthController(
        store=store,
        generator=SimpleNamespace(),
        output_dir=tmp_path / "output",
        event_hook=lambda event, payload: events.append((event, dict(payload))),
    )
    restored = controller.observations_by_tool_name[TOOL_NAME]
    assert restored.scenario_name.startswith("validation_contract:")
    assert any(example.held_out for example in restored.validation_examples)

    # The historical implementation truly fails its restored contract.  The
    # important distinction is that it reaches deterministic validation rather
    # than the invalid-binding quarantine path.
    assert controller.contract_failures_for_tools([TOOL_NAME]) == (TOOL_NAME,)
    assert any(
        event == "post_deployment_public_contract_failure" for event, _ in events
    )
    assert not any(
        event == "post_deployment_public_contract_binding_invalid"
        for event, _ in events
    )


def test_binding_resolve_rejects_registry_code_tamper(tmp_path: Path) -> None:
    store, _receipt = _seed(tmp_path)
    manifest = json.loads(store.manifest_path.read_text())
    manifest["tools"][TOOL_NAME]["tool"]["code"] += "\n# tampered"
    store.manifest_path.write_text(json.dumps(manifest) + "\n")

    entry = store.get(TOOL_NAME)
    assert entry is not None
    binding, error = ValidationContractBindingStore(store.root).resolve(entry)
    assert binding is None
    assert error == "registry_code_hash_mismatch"


def test_binding_resolve_rejects_registry_tool_spec_tamper(tmp_path: Path) -> None:
    store, _receipt = _seed(tmp_path)
    manifest = json.loads(store.manifest_path.read_text())
    manifest["tools"][TOOL_NAME]["tool"]["spec"]["description"] += " tampered"
    store.manifest_path.write_text(json.dumps(manifest) + "\n")

    entry = store.get(TOOL_NAME)
    assert entry is not None
    binding, error = ValidationContractBindingStore(store.root).resolve(entry)
    assert binding is None
    assert error == "binding_tool_spec_hash_mismatch"


def test_binding_resolve_rejects_symlinked_contract_directory(
    tmp_path: Path,
) -> None:
    store, _receipt = _seed(tmp_path)
    contract_directory = store.root / "validation_contracts"
    moved_directory = tmp_path / "moved_contracts"
    contract_directory.rename(moved_directory)
    contract_directory.symlink_to(moved_directory, target_is_directory=True)

    entry = store.get(TOOL_NAME)
    assert entry is not None
    binding, error = ValidationContractBindingStore(store.root).resolve(entry)
    assert binding is None
    assert error == "binding_blob_directory_symlink"


def test_binding_resolve_reports_nonfinite_blob_as_malformed(tmp_path: Path) -> None:
    store, receipt = _seed(tmp_path)
    binding_receipt = receipt["bindings"][TOOL_NAME]
    blob_path = (
        store.root / "validation_contracts" / f"{binding_receipt['contract_hash']}.json"
    )
    blob = json.loads(blob_path.read_text())
    blob["contract"]["validation_examples"][0]["expected"] = math.nan
    blob_path.write_text(json.dumps(blob) + "\n")

    entry = store.get(TOOL_NAME)
    assert entry is not None
    binding, error = ValidationContractBindingStore(store.root).resolve(entry)
    assert binding is None
    assert error == "binding_blob_malformed"


def test_binding_resolve_rejects_boolean_index_schema_version(
    tmp_path: Path,
) -> None:
    store, _receipt = _seed(tmp_path)
    binding_store = ValidationContractBindingStore(store.root)
    index = json.loads(binding_store.index_path.read_text())
    index["schema_version"] = True
    binding_store.index_path.write_text(json.dumps(index) + "\n")

    entry = store.get(TOOL_NAME)
    assert entry is not None
    binding, error = binding_store.resolve(entry)
    assert binding is None
    assert error == "binding_index_malformed"


def test_binding_resolve_rejects_boolean_metadata_tool_version(
    tmp_path: Path,
) -> None:
    store, _receipt = _seed(tmp_path)
    binding_store = ValidationContractBindingStore(store.root)
    index = json.loads(binding_store.index_path.read_text())
    index["bindings"][TOOL_NAME]["1"]["tool_version"] = True
    binding_store.index_path.write_text(json.dumps(index) + "\n")

    entry = store.get(TOOL_NAME)
    assert entry is not None
    binding, error = binding_store.resolve(entry)
    assert binding is None
    assert error == "binding_version_mismatch"


def _coherently_replace_contract_blob(
    store: RegistryStore,
    *,
    field: str,
    value: object,
) -> None:
    binding_store = ValidationContractBindingStore(store.root)
    index = json.loads(binding_store.index_path.read_text())
    metadata = index["bindings"][TOOL_NAME]["1"]
    prior_hash = metadata["contract_hash"]
    prior_path = binding_store.blob_directory / f"{prior_hash}.json"
    blob = json.loads(prior_path.read_text())
    blob[field] = value
    canonical = json.dumps(
        blob,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    replacement_hash = hashlib.sha256(canonical).hexdigest()
    replacement_path = binding_store.blob_directory / f"{replacement_hash}.json"
    replacement_path.write_text(json.dumps(blob, sort_keys=True) + "\n")
    metadata["contract_hash"] = replacement_hash
    binding_store.index_path.write_text(json.dumps(index) + "\n")


def test_binding_resolve_rejects_boolean_blob_schema_version(tmp_path: Path) -> None:
    store, _receipt = _seed(tmp_path)
    _coherently_replace_contract_blob(store, field="schema_version", value=True)

    entry = store.get(TOOL_NAME)
    assert entry is not None
    binding, error = ValidationContractBindingStore(store.root).resolve(entry)
    assert binding is None
    assert error == "binding_schema_version_mismatch"


def test_binding_resolve_rejects_boolean_blob_tool_version(tmp_path: Path) -> None:
    store, _receipt = _seed(tmp_path)
    _coherently_replace_contract_blob(store, field="tool_version", value=True)

    entry = store.get(TOOL_NAME)
    assert entry is not None
    binding, error = ValidationContractBindingStore(store.root).resolve(entry)
    assert binding is None
    assert error == "binding_version_mismatch"
