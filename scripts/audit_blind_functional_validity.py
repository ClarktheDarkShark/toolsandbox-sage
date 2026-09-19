#!/usr/bin/env python3
"""Create or execute a hash-pinned post-freeze H1 case bank."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sage_ts.evaluation.blind_functional_validity import (
    audit_blind_functional_validity,
    create_case_bank_scaffold,
    file_sha256,
    write_audit_report,
)
from scripts.manage_hypothesis_pilot import (
    _registry_content_identity,
    seal_phase_inputs,
)


def _validate_bound_registry(
    *, pilot_manifest: Path, registry_dir: Path
) -> dict[str, Any]:
    payload = json.loads(pilot_manifest.read_text(encoding="utf-8"))
    binding = payload.get("frozen_h123_registry")
    if not isinstance(binding, dict):
        raise ValueError("Pilot manifest has no frozen H2 registry binding.")
    identity = _registry_content_identity(registry_dir)
    if Path(str(binding.get("path") or "")).resolve() != registry_dir.resolve():
        raise ValueError("H1 registry path differs from the H2 registry binding.")
    if binding.get("content_sha256") != identity["content_sha256"]:
        raise ValueError("H1 registry bytes differ from the H2 registry binding.")
    return identity


def _object(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a JSON object.")
    return value


def _receipt_file(
    value: object, *, label: str, expected_path: Path | None = None
) -> Path:
    binding = _object(value, label)
    path = Path(str(binding.get("path") or "")).resolve()
    expected_sha256 = str(binding.get("sha256") or "")
    if expected_path is not None and path != expected_path.resolve():
        raise ValueError(f"{label} names the wrong file.")
    if not path.is_file() or file_sha256(path) != expected_sha256:
        raise ValueError(f"{label} is missing or does not match its receipt hash.")
    return path


def _validate_assessor_receipt(
    *,
    receipt_path: Path,
    pilot_manifest: Path,
    registry_identity: Mapping[str, object],
    case_bank_path: Path,
    case_bank_sha256: str,
) -> dict[str, Path]:
    """Validate the procedural, spec-only assessor record and its file bindings."""

    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("H1 assessor receipt is unreadable or malformed.") from exc
    receipt = _object(receipt, "H1 assessor receipt")
    pilot = json.loads(pilot_manifest.read_text(encoding="utf-8"))
    if receipt.get("schema_version") != 1:
        raise ValueError("H1 assessor receipt schema_version must be 1.")
    if receipt.get("receipt_type") != "h1_procedural_spec_only_assessor":
        raise ValueError("H1 assessor receipt_type is invalid.")
    if receipt.get("pilot_id") != pilot.get("pilot_id"):
        raise ValueError("H1 assessor receipt has the wrong pilot ID.")
    if receipt.get("registry_content_sha256") != registry_identity.get(
        "content_sha256"
    ):
        raise ValueError("H1 assessor receipt has the wrong registry identity.")

    assessor = _object(receipt.get("assessor"), "H1 assessor identity")
    if (
        not str(assessor.get("identity") or "").strip()
        or not str(assessor.get("model") or "").strip()
    ):
        raise ValueError("H1 assessor identity and model are required.")
    if assessor.get("separate_context") is not True:
        raise ValueError("H1 assessor must declare a separate task context.")

    declarations = _object(receipt.get("declarations"), "H1 assessor declarations")
    required_true = (
        "spec_only_inputs",
        "source_code_not_provided",
        "admission_cases_not_provided",
        "execution_results_not_provided",
        "procedural_not_cryptographic_isolation",
    )
    if any(declarations.get(key) is not True for key in required_true):
        raise ValueError("H1 assessor receipt lacks required blinding declarations.")
    if not str(receipt.get("completed_at") or "").strip():
        raise ValueError("H1 assessor receipt must record completion time.")

    inputs = _object(receipt.get("inputs"), "H1 assessor inputs")
    outputs = _object(receipt.get("outputs"), "H1 assessor outputs")
    records = _object(receipt.get("records"), "H1 assessor records")
    scaffold = _receipt_file(inputs.get("scaffold"), label="H1 assessor scaffold")
    completed_bank = _receipt_file(
        outputs.get("case_bank"),
        label="H1 assessor case bank",
        expected_path=case_bank_path,
    )
    if file_sha256(completed_bank) != case_bank_sha256:
        raise ValueError("H1 assessor case-bank hash differs from the audit lock.")
    prompt = _receipt_file(records.get("prompt"), label="H1 assessor prompt")
    completion = _receipt_file(
        records.get("completion"), label="H1 assessor completion record"
    )
    return {
        "scaffold": scaffold,
        "assessor_prompt": prompt,
        "assessor_completion": completion,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    scaffold = commands.add_parser(
        "scaffold",
        help="Export a spec-only packet for an independent blind case author.",
    )
    scaffold.add_argument("--registry-dir", type=Path, required=True)
    scaffold.add_argument("--pilot-manifest", type=Path, required=True)
    scaffold.add_argument("--output", type=Path, required=True)
    scaffold.add_argument("--bank-id", required=True)
    scaffold.add_argument("--minimum-oracle-cases-per-tool", type=int, default=2)

    hash_command = commands.add_parser(
        "hash", help="Print the raw-byte SHA-256 used to lock a completed bank."
    )
    hash_command.add_argument("--case-bank", type=Path, required=True)

    audit = commands.add_parser(
        "audit", help="Run the frozen registry against a pinned external bank."
    )
    audit.add_argument("--registry-dir", type=Path, required=True)
    audit.add_argument("--pilot-manifest", type=Path, required=True)
    audit.add_argument("--assessor-receipt", type=Path, required=True)
    audit.add_argument("--case-bank", type=Path, required=True)
    audit.add_argument("--case-bank-sha256", required=True)
    audit.add_argument("--output", type=Path, required=True)
    audit.add_argument("--confidence-level", type=float, default=0.95)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "scaffold":
        _validate_bound_registry(
            pilot_manifest=args.pilot_manifest,
            registry_dir=args.registry_dir,
        )
        payload = create_case_bank_scaffold(
            registry_dir=args.registry_dir,
            output_path=args.output,
            bank_id=args.bank_id,
            minimum_oracle_cases_per_tool=args.minimum_oracle_cases_per_tool,
        )
        print(
            json.dumps(
                {
                    "case_bank": str(args.output.resolve()),
                    "active_tool_count": len(payload["tools"]),
                    "next_step": (
                        "Have a code- and admission-case-blind assessor add the "
                        "required independent oracles, then run the hash command."
                    ),
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "hash":
        print(file_sha256(args.case_bank))
        return 0

    identity = _validate_bound_registry(
        pilot_manifest=args.pilot_manifest,
        registry_dir=args.registry_dir,
    )
    receipt_files = _validate_assessor_receipt(
        receipt_path=args.assessor_receipt,
        pilot_manifest=args.pilot_manifest,
        registry_identity=identity,
        case_bank_path=args.case_bank,
        case_bank_sha256=args.case_bank_sha256,
    )
    seal_phase_inputs(
        manifest_path=args.pilot_manifest,
        phase="h1_blind_audit",
        files={
            "case_bank": args.case_bank,
            "assessor_receipt": args.assessor_receipt,
            **receipt_files,
        },
        declarations={
            "registry_path": str(args.registry_dir.resolve()),
            "registry_content_sha256": identity["content_sha256"],
            "case_bank_sha256": args.case_bank_sha256,
            "blinding": "spec_only_procedural_not_cryptographic_isolation",
        },
    )
    report = audit_blind_functional_validity(
        registry_dir=args.registry_dir,
        case_bank_path=args.case_bank,
        expected_case_bank_sha256=args.case_bank_sha256,
        confidence_level=args.confidence_level,
    )
    write_audit_report(report, args.output)
    print(json.dumps(report, sort_keys=True))
    # A scientifically negative tool result is a completed audit, not a process
    # crash.  Nonzero is reserved for invalid integrity/evidence inputs.
    return 0 if report["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
