"""Research-integrity guardrails for standalone SAGE.

Environment adapters are allowed to know how to privately score their own
tasks. SAGE itself must not see hidden labels, oracle fields, expected answers,
or prior-result shortcuts when it decides what gap exists or what helper to
generate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from sage_agent.interfaces import (
    EnvironmentProfile,
    GapSignal,
    HelperCandidate,
    TaskSpec,
)


class IntegrityError(RuntimeError):
    """Raised when an adapter exposes leak-prone fields to SAGE."""


@dataclass(frozen=True)
class IntegrityIssue:
    """One blocked integrity finding."""

    location: str
    kind: str
    detail: str
    severity: str = "block"

    def to_json(self) -> dict[str, str]:
        return {
            "location": self.location,
            "kind": self.kind,
            "detail": self.detail,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class IntegrityReport:
    """Integrity scan result."""

    issues: tuple[IntegrityIssue, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.issues

    def to_json(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "issues": [issue.to_json() for issue in self.issues],
        }

    def raise_for_issues(self) -> None:
        if self.passed:
            return
        joined = "; ".join(
            f"{issue.location}:{issue.kind}:{issue.detail}" for issue in self.issues
        )
        raise IntegrityError(f"sage_integrity_blocked:{joined}")


@dataclass(frozen=True)
class ResearchIntegrityPolicy:
    """Configurable no-peeking policy for adapters and candidates."""

    forbidden_metadata_keys: tuple[str, ...] = (
        "answer",
        "answer_key",
        "answers",
        "cached_control",
        "expected",
        "expected_answer",
        "expected_label",
        "expected_output",
        "expected_person_id",
        "gold",
        "gold_answer",
        "ground_truth",
        "hidden_label",
        "label",
        "labels",
        "oracle",
        "prior_sage_trace",
        "prior_trace",
        "reference_answer",
        "score",
        "scorer",
        "solution",
        "solutions",
        "truth",
        "truth_label",
    )
    forbidden_artifact_keys: tuple[str, ...] = (
        "answer_key",
        "expected_answer",
        "gold_answer",
        "ground_truth",
        "oracle",
        "reference_answer",
        "reference_poc",
        "solution",
        "solution_poc",
        "truth_label",
    )
    forbidden_text_fragments: tuple[str, ...] = (
        "answer_key",
        "expected_answer",
        "gold_answer",
        "ground_truth",
        "hidden_label",
        "oracle",
        "prior_sage_trace",
        "reference_answer",
        "solution_poc",
        "truth_label",
    )
    check_candidate_code_for_source_task_id: bool = True


def check_profile(
    profile: EnvironmentProfile,
    policy: ResearchIntegrityPolicy,
) -> IntegrityReport:
    """Check environment-profile metadata exposed to SAGE."""

    issues = _scan_mapping_keys(
        profile.metadata,
        location=f"profile:{profile.name}.metadata",
        forbidden=policy.forbidden_metadata_keys,
        kind="forbidden_profile_metadata_key",
    )
    return IntegrityReport(tuple(issues))


def check_task_specs(
    tasks: tuple[TaskSpec, ...],
    policy: ResearchIntegrityPolicy,
) -> IntegrityReport:
    """Check that SAGE-visible tasks do not carry oracle fields."""

    issues: list[IntegrityIssue] = []
    for task in tasks:
        issues.extend(
            _scan_mapping_keys(
                task.metadata,
                location=f"task:{task.task_id}.metadata",
                forbidden=policy.forbidden_metadata_keys,
                kind="forbidden_task_metadata_key",
            )
        )
        issues.extend(
            _scan_mapping_keys(
                task.artifacts,
                location=f"task:{task.task_id}.artifacts",
                forbidden=policy.forbidden_artifact_keys,
                kind="forbidden_task_artifact_key",
            )
        )
    return IntegrityReport(tuple(issues))


def check_gap_signal(
    gap: GapSignal,
    policy: ResearchIntegrityPolicy,
) -> IntegrityReport:
    """Check gap text/directives before generation sees them."""

    issues: list[IntegrityIssue] = []
    text_parts = [
        gap.key,
        gap.summary,
        gap.suggested_helper_family,
        *(item for item in gap.evidence),
        *(item for item in gap.validation_hints),
    ]
    issues.extend(
        _scan_text_parts(
            text_parts,
            location=f"gap:{gap.key}",
            forbidden=policy.forbidden_text_fragments,
            kind="forbidden_gap_text",
        )
    )
    issues.extend(
        _scan_mapping_keys(
            gap.generation_directives,
            location=f"gap:{gap.key}.generation_directives",
            forbidden=policy.forbidden_metadata_keys,
            kind="forbidden_gap_directive_key",
        )
    )
    return IntegrityReport(tuple(issues))


def check_helper_candidate(
    candidate: HelperCandidate,
    gap: GapSignal,
    policy: ResearchIntegrityPolicy,
) -> IntegrityReport:
    """Check candidate metadata and code before validation/retention."""

    issues: list[IntegrityIssue] = []
    issues.extend(
        _scan_mapping_keys(
            candidate.metadata,
            location=f"candidate:{candidate.spec.name}.metadata",
            forbidden=policy.forbidden_metadata_keys,
            kind="forbidden_candidate_metadata_key",
        )
    )
    issues.extend(
        _scan_text_parts(
            [
                candidate.spec.name,
                candidate.spec.description,
                candidate.code,
                *candidate.spec.positive_triggers,
                *candidate.spec.negative_triggers,
                *candidate.spec.safety_notes,
            ],
            location=f"candidate:{candidate.spec.name}",
            forbidden=policy.forbidden_text_fragments,
            kind="forbidden_candidate_text",
        )
    )
    if policy.check_candidate_code_for_source_task_id:
        source = gap.source_task_id.strip()
        if source and source.lower() in candidate.code.lower():
            issues.append(
                IntegrityIssue(
                    location=f"candidate:{candidate.spec.name}.code",
                    kind="source_task_id_hardcoded",
                    detail=source,
                )
            )
    return IntegrityReport(tuple(issues))


def merge_reports(*reports: IntegrityReport) -> IntegrityReport:
    """Merge reports while preserving issue order."""

    issues: list[IntegrityIssue] = []
    for report in reports:
        issues.extend(report.issues)
    return IntegrityReport(tuple(issues))


def _scan_mapping_keys(
    mapping: Mapping[str, Any],
    *,
    location: str,
    forbidden: tuple[str, ...],
    kind: str,
) -> list[IntegrityIssue]:
    issues: list[IntegrityIssue] = []
    normalized_forbidden = {_normalize_key(item) for item in forbidden}
    for key in mapping:
        normalized = _normalize_key(str(key))
        if normalized not in normalized_forbidden:
            continue
        issues.append(IntegrityIssue(location=location, kind=kind, detail=str(key)))
    return issues


def _scan_text_parts(
    parts: list[str],
    *,
    location: str,
    forbidden: tuple[str, ...],
    kind: str,
) -> list[IntegrityIssue]:
    issues: list[IntegrityIssue] = []
    lowered = "\n".join(parts).lower()
    for fragment in forbidden:
        if fragment.lower() not in lowered:
            continue
        issues.append(IntegrityIssue(location=location, kind=kind, detail=fragment))
    return issues


def _normalize_key(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")
