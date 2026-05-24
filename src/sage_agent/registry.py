"""Filesystem registry for standalone SAGE helpers."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sage_agent.interfaces import (
    HelperCandidate,
    HelperRecord,
    HelperSpec,
    HelperValidationReport,
    ValidationCase,
)

REGISTRY_VERSION = 1


class LocalSAGERegistry:
    """Small JSON registry for environment-neutral generated helpers."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.root / "sage_registry.json"

    def load(self) -> dict[str, HelperRecord]:
        if not self.manifest_path.exists():
            return {}
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        tools = payload.get("tools", {})
        if not isinstance(tools, dict):
            return {}
        return {
            str(name): _record_from_json(record)
            for name, record in tools.items()
            if isinstance(record, dict)
        }

    def save(self, records: dict[str, HelperRecord]) -> None:
        payload = {
            "schema_version": REGISTRY_VERSION,
            "tools": {
                name: _record_to_json(record) for name, record in records.items()
            },
        }
        tmp = self.manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, self.manifest_path)

    def add(
        self,
        candidate: HelperCandidate,
        validation: HelperValidationReport,
        *,
        birth_gap_key: str,
        birth_environment: str,
    ) -> HelperRecord:
        records = self.load()
        record = HelperRecord(
            candidate=candidate,
            validation=validation,
            birth_gap_key=birth_gap_key,
            birth_environment=birth_environment,
            created_at=datetime.now(timezone.utc).isoformat(),
            code_hash=hashlib.sha256(candidate.code.encode("utf-8")).hexdigest(),
        )
        records[candidate.spec.name] = record
        self.save(records)
        return record

    def record_use(self, tool_name: str, *, success: bool) -> None:
        records = self.load()
        record = records.get(tool_name)
        if record is None:
            return
        records[tool_name] = replace(
            record,
            uses=record.uses + 1,
            successes=record.successes + int(success),
        )
        self.save(records)

    def retire(self, tool_name: str) -> bool:
        """Park a helper so routers no longer expose it naturally."""

        records = self.load()
        record = records.get(tool_name)
        if record is None or record.retired:
            return False
        records[tool_name] = replace(record, retired=True)
        self.save(records)
        return True


def _spec_to_json(spec: HelperSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "family": spec.family,
        "description": spec.description,
        "helper_type": spec.helper_type,
        "input_schema": dict(spec.input_schema),
        "output_schema": dict(spec.output_schema),
        "positive_triggers": list(spec.positive_triggers),
        "negative_triggers": list(spec.negative_triggers),
        "safety_notes": list(spec.safety_notes),
    }


def _spec_from_json(payload: dict[str, Any]) -> HelperSpec:
    return HelperSpec(
        name=str(payload["name"]),
        family=str(payload.get("family", "deterministic_helper")),
        description=str(payload.get("description", "")),
        helper_type=str(payload.get("helper_type", "deterministic_callable")),
        input_schema=_str_map(payload.get("input_schema", {})),
        output_schema=_str_map(payload.get("output_schema", {})),
        positive_triggers=tuple(
            str(item) for item in payload.get("positive_triggers", ())
        ),
        negative_triggers=tuple(
            str(item) for item in payload.get("negative_triggers", ())
        ),
        safety_notes=tuple(str(item) for item in payload.get("safety_notes", ())),
    )


def _case_to_json(case: ValidationCase) -> dict[str, Any]:
    return {
        "name": case.name,
        "inputs": dict(case.inputs),
        "expected": dict(case.expected),
        "should_abstain": case.should_abstain,
        "description": case.description,
    }


def _case_from_json(payload: dict[str, Any]) -> ValidationCase:
    return ValidationCase(
        name=str(payload["name"]),
        inputs=dict(payload.get("inputs", {})),
        expected=dict(payload.get("expected", {})),
        should_abstain=bool(payload.get("should_abstain", False)),
        description=str(payload.get("description", "")),
    )


def _candidate_to_json(candidate: HelperCandidate) -> dict[str, Any]:
    return {
        "spec": _spec_to_json(candidate.spec),
        "code": candidate.code,
        "validation_cases": [
            _case_to_json(case) for case in candidate.validation_cases
        ],
        "metadata": dict(candidate.metadata),
    }


def _candidate_from_json(payload: dict[str, Any]) -> HelperCandidate:
    return HelperCandidate(
        spec=_spec_from_json(payload["spec"]),
        code=str(payload.get("code", "")),
        validation_cases=tuple(
            _case_from_json(case)
            for case in payload.get("validation_cases", ())
            if isinstance(case, dict)
        ),
        metadata=dict(payload.get("metadata", {})),
    )


def _validation_to_json(report: HelperValidationReport) -> dict[str, Any]:
    return {
        "accepted": report.accepted,
        "errors": list(report.errors),
        "cases_run": report.cases_run,
        "cases_passed": report.cases_passed,
        "runtime_smoke_passed": report.runtime_smoke_passed,
        "side_effect_free": report.side_effect_free,
    }


def _validation_from_json(payload: dict[str, Any]) -> HelperValidationReport:
    return HelperValidationReport(
        accepted=bool(payload.get("accepted", False)),
        errors=tuple(str(item) for item in payload.get("errors", ())),
        cases_run=int(payload.get("cases_run", 0)),
        cases_passed=int(payload.get("cases_passed", 0)),
        runtime_smoke_passed=bool(payload.get("runtime_smoke_passed", False)),
        side_effect_free=bool(payload.get("side_effect_free", False)),
    )


def _record_to_json(record: HelperRecord) -> dict[str, Any]:
    return {
        "candidate": _candidate_to_json(record.candidate),
        "validation": _validation_to_json(record.validation),
        "birth_gap_key": record.birth_gap_key,
        "birth_environment": record.birth_environment,
        "created_at": record.created_at,
        "code_hash": record.code_hash,
        "uses": record.uses,
        "successes": record.successes,
        "retired": record.retired,
    }


def _record_from_json(payload: dict[str, Any]) -> HelperRecord:
    return HelperRecord(
        candidate=_candidate_from_json(payload["candidate"]),
        validation=_validation_from_json(payload["validation"]),
        birth_gap_key=str(payload.get("birth_gap_key", "")),
        birth_environment=str(payload.get("birth_environment", "")),
        created_at=str(payload.get("created_at", "")),
        code_hash=str(payload.get("code_hash", "")),
        uses=int(payload.get("uses", 0)),
        successes=int(payload.get("successes", 0)),
        retired=bool(payload.get("retired", False)),
    )


def _str_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}
