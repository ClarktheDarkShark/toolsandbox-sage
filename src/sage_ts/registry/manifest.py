"""Persistent registry manifest types."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sage_ts.adequacy.candidate_gate import evaluate_candidate_gate
from sage_ts.generation.tool_spec import TOOL_SPEC_SCHEMA_VERSION, GeneratedTool
from sage_ts.validation.sandbox_validator import ValidationResult

REGISTRY_SCHEMA_VERSION = 2


def code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def has_current_validation_proof(entry: "RegistryEntry") -> bool:
    """Return whether an accepted entry has claim-grade validation metadata."""
    gate = evaluate_candidate_gate(entry.tool.spec)
    family = entry.tool.spec.family.value
    requires_negative = entry.tool.spec.family.value in {
        "state_precondition_helper",
        "search_filter_ranking_helper",
        "composite_workflow_helper",
        "validation_abstention_helper",
    }
    requires_strong_abstention_proof = family == "validation_abstention_helper"
    return (
        entry.validation.accepted
        and entry.validation.held_out_check_count > 0
        and (entry.validation.negative_applicability_count > 0 or not requires_negative)
        and (
            not requires_strong_abstention_proof
            or (
                entry.validation.source_example_count >= 2
                and entry.validation.held_out_check_count >= 2
                and entry.validation.negative_applicability_count >= 2
                and bool(entry.validation.validated_applicability_domains)
            )
        )
        and entry.validation.runtime_smoke_passed
        and not entry.retired
        and entry.schema_version == REGISTRY_SCHEMA_VERSION
        and entry.tool.spec.schema_version == TOOL_SPEC_SCHEMA_VERSION
        and entry.code_hash_verified
        and gate.allowed
    )


@dataclass(frozen=True)
class RegistryEntry:
    tool: GeneratedTool
    validation: ValidationResult
    birth_scenario: str
    accepted_at: str
    version: int = 1
    reuse_count: int = 0
    success_flips: int = 0
    retired: bool = False
    schema_version: int = REGISTRY_SCHEMA_VERSION
    stored_code_hash: str | None = None
    legacy_diagnostic: bool = False

    @classmethod
    def accepted(
        cls,
        tool: GeneratedTool,
        validation: ValidationResult,
        birth_scenario: str,
    ) -> "RegistryEntry":
        return cls(
            tool=tool,
            validation=validation,
            birth_scenario=birth_scenario,
            accepted_at=datetime.now(timezone.utc).isoformat(),
            stored_code_hash=code_hash(tool.code),
        )

    @property
    def code_hash_verified(self) -> bool:
        return self.stored_code_hash == code_hash(self.tool.code)

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tool": self.tool.to_json(),
            "validation": {
                "accepted": self.validation.accepted,
                "errors": list(self.validation.errors),
                "source_example_count": self.validation.source_example_count,
                "held_out_check_count": self.validation.held_out_check_count,
                "negative_applicability_count": self.validation.negative_applicability_count,
                "runtime_smoke_passed": self.validation.runtime_smoke_passed,
                "validated_applicability_domains": list(
                    self.validation.validated_applicability_domains
                ),
            },
            "birth_scenario": self.birth_scenario,
            "accepted_at": self.accepted_at,
            "version": self.version,
            "reuse_count": self.reuse_count,
            "success_flips": self.success_flips,
            "retired": self.retired,
            "code_hash": self.stored_code_hash or code_hash(self.tool.code),
            "legacy_diagnostic": self.legacy_diagnostic,
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "RegistryEntry":
        return cls(
            schema_version=int(payload.get("schema_version", REGISTRY_SCHEMA_VERSION)),
            tool=GeneratedTool.from_json(payload["tool"]),
            validation=ValidationResult(
                accepted=bool(payload["validation"]["accepted"]),
                errors=tuple(payload["validation"]["errors"]),
                source_example_count=int(
                    payload["validation"].get("source_example_count", 0)
                ),
                held_out_check_count=int(
                    payload["validation"].get("held_out_check_count", 0)
                ),
                negative_applicability_count=int(
                    payload["validation"].get("negative_applicability_count", 0)
                ),
                runtime_smoke_passed=bool(
                    payload["validation"].get("runtime_smoke_passed", False)
                ),
                validated_applicability_domains=tuple(
                    str(item)
                    for item in payload["validation"].get(
                        "validated_applicability_domains", []
                    )
                    if str(item)
                ),
            ),
            birth_scenario=str(payload["birth_scenario"]),
            accepted_at=str(payload["accepted_at"]),
            version=int(payload["version"]),
            reuse_count=int(payload["reuse_count"]),
            success_flips=int(payload["success_flips"]),
            retired=bool(payload["retired"]),
            stored_code_hash=payload.get("code_hash"),
            legacy_diagnostic=bool(payload.get("legacy_diagnostic", False)),
        )
