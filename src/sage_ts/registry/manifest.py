"""Persistent registry manifest types."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sage_ts.generation.tool_spec import GeneratedTool
from sage_ts.validation.sandbox_validator import ValidationResult


def code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def has_current_validation_proof(entry: "RegistryEntry") -> bool:
    """Return whether an accepted entry has claim-grade validation metadata."""
    return (
        entry.validation.accepted
        and entry.validation.held_out_check_count > 0
        and entry.validation.runtime_smoke_passed
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
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "tool": self.tool.to_json(),
            "validation": {
                "accepted": self.validation.accepted,
                "errors": list(self.validation.errors),
                "source_example_count": self.validation.source_example_count,
                "held_out_check_count": self.validation.held_out_check_count,
                "runtime_smoke_passed": self.validation.runtime_smoke_passed,
            },
            "birth_scenario": self.birth_scenario,
            "accepted_at": self.accepted_at,
            "version": self.version,
            "reuse_count": self.reuse_count,
            "success_flips": self.success_flips,
            "retired": self.retired,
            "code_hash": code_hash(self.tool.code),
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "RegistryEntry":
        return cls(
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
                runtime_smoke_passed=bool(
                    payload["validation"].get("runtime_smoke_passed", False)
                ),
            ),
            birth_scenario=str(payload["birth_scenario"]),
            accepted_at=str(payload["accepted_at"]),
            version=int(payload["version"]),
            reuse_count=int(payload["reuse_count"]),
            success_flips=int(payload["success_flips"]),
            retired=bool(payload["retired"]),
        )
