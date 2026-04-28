"""Small attribution helpers for matched baseline/SAGE comparisons."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OutcomePair:
    scenario: str
    baseline_success: bool
    sage_success: bool
    generated_tool_used: bool


def attributable_success_flips(pairs: list[OutcomePair]) -> list[str]:
    return [
        pair.scenario
        for pair in pairs
        if pair.generated_tool_used and not pair.baseline_success and pair.sage_success
    ]
