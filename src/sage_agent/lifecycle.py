"""Generic helper lifecycle assessment for standalone SAGE."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from sage_agent.interfaces import HelperRecord


@dataclass(frozen=True)
class HelperLifecycleAssessment:
    """Keep/refine/park/scale decision for one generated helper."""

    tool_name: str
    decision: str
    uses: int
    successes: int
    success_rate: float
    reason: str

    def to_json(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "decision": self.decision,
            "uses": self.uses,
            "successes": self.successes,
            "success_rate": self.success_rate,
            "reason": self.reason,
        }


def assess_helper_lifecycle(
    records: Mapping[str, HelperRecord],
    *,
    min_scale_uses: int = 5,
    min_keep_success_rate: float = 0.5,
) -> tuple[HelperLifecycleAssessment, ...]:
    """Assess retained helpers from environment-neutral reuse evidence."""

    assessments: list[HelperLifecycleAssessment] = []
    for name, record in records.items():
        if record.retired:
            assessments.append(
                HelperLifecycleAssessment(
                    tool_name=name,
                    decision="park",
                    uses=record.uses,
                    successes=record.successes,
                    success_rate=_success_rate(record),
                    reason="helper is already retired",
                )
            )
            continue
        if record.uses == 0:
            decision = "watch"
            reason = "accepted but not naturally reused yet"
        elif (
            record.uses >= min_scale_uses
            and _success_rate(record) >= min_keep_success_rate
        ):
            decision = "scale"
            reason = "naturally reused with enough positive evidence"
        elif _success_rate(record) >= min_keep_success_rate:
            decision = "keep"
            reason = "naturally reused with positive early evidence"
        else:
            decision = "refine"
            reason = "natural reuse evidence is weak or mixed"
        assessments.append(
            HelperLifecycleAssessment(
                tool_name=name,
                decision=decision,
                uses=record.uses,
                successes=record.successes,
                success_rate=_success_rate(record),
                reason=reason,
            )
        )
    return tuple(sorted(assessments, key=lambda item: item.tool_name))


def _success_rate(record: HelperRecord) -> float:
    if record.uses <= 0:
        return 0.0
    return record.successes / record.uses
