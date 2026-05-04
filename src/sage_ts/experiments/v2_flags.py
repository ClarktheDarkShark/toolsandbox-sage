"""Environment-backed feature flags for V2 matrix diagnostics."""

from __future__ import annotations

import os

GRADING_ACCOUNTING = "grading_accounting"
DEPENDENCY_LOGIC = "dependency_logic"
LIVE_VALIDATION = "live_validation"
CANDIDATE_REPAIR = "candidate_repair"
CONTRACT_SYNTHESIS = "contract_synthesis"
EVIDENCE_ROUTING = "evidence_routing"

CURRENT_REPAIRED_DEFAULTS = frozenset(
    {
        GRADING_ACCOUNTING,
        DEPENDENCY_LOGIC,
        LIVE_VALIDATION,
        EVIDENCE_ROUTING,
    }
)
ALL_FEATURES = frozenset(
    {
        GRADING_ACCOUNTING,
        DEPENDENCY_LOGIC,
        LIVE_VALIDATION,
        CANDIDATE_REPAIR,
        CONTRACT_SYNTHESIS,
        EVIDENCE_ROUTING,
    }
)


def enabled_features() -> frozenset[str]:
    raw = os.environ.get("SAGE_V2_EXPERIMENT_FEATURES")
    if raw is None or raw.strip().lower() in {"", "default", "current"}:
        return CURRENT_REPAIRED_DEFAULTS
    value = raw.strip().lower()
    if value in {"none", "off"}:
        return frozenset()
    if value == "all":
        return ALL_FEATURES
    return (
        frozenset(item.strip().lower() for item in raw.split(",") if item.strip())
        & ALL_FEATURES
    )


def feature_enabled(name: str) -> bool:
    return name in enabled_features()
