"""Environment-backed feature flags for V2 matrix diagnostics."""

from __future__ import annotations

import os

GRADING_ACCOUNTING = "grading_accounting"
DEPENDENCY_LOGIC = "dependency_logic"
LIVE_VALIDATION = "live_validation"
CANDIDATE_REPAIR = "candidate_repair"
CONTRACT_SYNTHESIS = "contract_synthesis"
EVIDENCE_ROUTING = "evidence_routing"
MEDIUM_GRAIN_SKILLS = "medium_grain_skills"

# Evidence-backed current stack from the fair-chance confirmation run plus the
# self-evolving repair loop: contract synthesis improves tool specs, while
# candidate repair lets online birth fix schema/example mismatches before
# parking a generated helper.
CURRENT_REPAIRED_DEFAULTS = frozenset({CONTRACT_SYNTHESIS, CANDIDATE_REPAIR})
ALL_FEATURES = frozenset(
    {
        GRADING_ACCOUNTING,
        DEPENDENCY_LOGIC,
        LIVE_VALIDATION,
        CANDIDATE_REPAIR,
        CONTRACT_SYNTHESIS,
        EVIDENCE_ROUTING,
        MEDIUM_GRAIN_SKILLS,
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
