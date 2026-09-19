from __future__ import annotations

import json
from pathlib import Path

import pytest

from sage_ts.evaluation.blind_functional_validity import file_sha256
from scripts.audit_blind_functional_validity import _validate_assessor_receipt


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _binding(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": file_sha256(path)}


def test_assessor_receipt_binds_spec_only_packet_and_completed_bank(
    tmp_path: Path,
) -> None:
    pilot = tmp_path / "pilot.json"
    pilot.write_text(json.dumps({"pilot_id": "pilot-1"}), encoding="utf-8")
    scaffold = _write(tmp_path / "scaffold.json", "{}\n")
    case_bank = _write(tmp_path / "case_bank.json", '{"tools": []}\n')
    prompt = _write(tmp_path / "prompt.txt", "Author cases from the scaffold only.\n")
    completion = _write(tmp_path / "completion.txt", "Case bank completed.\n")
    receipt = {
        "schema_version": 1,
        "receipt_type": "h1_procedural_spec_only_assessor",
        "pilot_id": "pilot-1",
        "registry_content_sha256": "registry-tree",
        "assessor": {
            "identity": "separate-assessor-task",
            "model": "gpt-5.6-sol",
            "separate_context": True,
        },
        "completed_at": "2026-09-18T12:00:00Z",
        "declarations": {
            "spec_only_inputs": True,
            "source_code_not_provided": True,
            "admission_cases_not_provided": True,
            "execution_results_not_provided": True,
            "procedural_not_cryptographic_isolation": True,
        },
        "inputs": {"scaffold": _binding(scaffold)},
        "outputs": {"case_bank": _binding(case_bank)},
        "records": {
            "prompt": _binding(prompt),
            "completion": _binding(completion),
        },
    }
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    files = _validate_assessor_receipt(
        receipt_path=receipt_path,
        pilot_manifest=pilot,
        registry_identity={"content_sha256": "registry-tree"},
        case_bank_path=case_bank,
        case_bank_sha256=file_sha256(case_bank),
    )

    assert files == {
        "scaffold": scaffold,
        "assessor_prompt": prompt,
        "assessor_completion": completion,
    }


def test_assessor_receipt_fails_closed_without_blinding_declarations(
    tmp_path: Path,
) -> None:
    pilot = tmp_path / "pilot.json"
    pilot.write_text(json.dumps({"pilot_id": "pilot-1"}), encoding="utf-8")
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "receipt_type": "h1_procedural_spec_only_assessor",
                "pilot_id": "pilot-1",
                "registry_content_sha256": "registry-tree",
                "assessor": {
                    "identity": "assessor",
                    "model": "model",
                    "separate_context": True,
                },
                "completed_at": "2026-09-18T12:00:00Z",
                "declarations": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="blinding declarations"):
        _validate_assessor_receipt(
            receipt_path=receipt_path,
            pilot_manifest=pilot,
            registry_identity={"content_sha256": "registry-tree"},
            case_bank_path=tmp_path / "missing-bank.json",
            case_bank_sha256="missing",
        )
