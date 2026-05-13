"""Gap observation helpers for self-evolving SAGE campaigns.

The observer deliberately works from run artifacts and task/scenario metadata only.
It does not read labels, expected answers, or hidden benchmark facts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GapScenario:
    scenario: str
    score_delta: float | None = None
    outcome_delta: float | None = None
    visible_tools: tuple[str, ...] = ()
    called_tools: tuple[str, ...] = ()

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "GapScenario":
        return cls(
            scenario=str(payload.get("scenario", "")),
            score_delta=_optional_float(payload.get("score_delta")),
            outcome_delta=_optional_float(payload.get("outcome_delta")),
            visible_tools=tuple(str(item) for item in payload.get("visible_tools", ())),
            called_tools=tuple(str(item) for item in payload.get("called_tools", ())),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "score_delta": self.score_delta,
            "outcome_delta": self.outcome_delta,
            "visible_tools": list(self.visible_tools),
            "called_tools": list(self.called_tools),
        }


@dataclass(frozen=True)
class GapBucket:
    bucket: str
    scenario_count: int
    outcome_regression_count: int
    score_regression_count: int
    negative_outcome_mass: float
    negative_score_mass: float
    no_visible_helper_count: int
    no_called_helper_count: int
    top_scenarios: tuple[GapScenario, ...]
    reported_opportunity_score: float | None = None

    @property
    def opportunity_score(self) -> float:
        """Outcome-first score used to rank next tool-generation opportunities."""

        if self.reported_opportunity_score is not None:
            return self.reported_opportunity_score
        return (
            self.negative_outcome_mass * 10.0
            + self.negative_score_mass
            + self.no_visible_helper_count * 0.05
            + self.no_called_helper_count * 0.025
        )

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "GapBucket":
        scenario_rows: list[dict[str, Any]] = []
        for key in (
            "examples",
            "top_scenarios",
            "top_outcome_regressions",
            "top_unhelped_regressions",
            "top_score_regressions",
        ):
            rows = payload.get(key, [])
            if isinstance(rows, list):
                scenario_rows.extend(
                    row for row in rows if isinstance(row, dict) and row.get("scenario")
                )
        deduped: dict[str, GapScenario] = {}
        for row in scenario_rows:
            scenario = GapScenario.from_json(row)
            deduped.setdefault(scenario.scenario, scenario)
        return cls(
            bucket=str(payload.get("bucket", "")),
            scenario_count=int(payload.get("scenario_count", 0) or 0),
            outcome_regression_count=int(
                _first_present(
                    payload, "outcome_regression_count", "outcome_regressions"
                )
                or 0
            ),
            score_regression_count=int(
                _first_present(payload, "score_regression_count", "score_regressions")
                or 0
            ),
            negative_outcome_mass=float(
                _first_present(
                    payload, "negative_outcome_mass", "outcome_negative_mass"
                )
                or 0
            ),
            negative_score_mass=float(
                _first_present(payload, "negative_score_mass", "score_negative_mass")
                or 0
            ),
            no_visible_helper_count=int(payload.get("no_visible_helper_count", 0) or 0),
            no_called_helper_count=int(payload.get("no_called_helper_count", 0) or 0),
            top_scenarios=tuple(deduped.values()),
            reported_opportunity_score=_optional_float(
                payload.get("opportunity_score")
            ),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "bucket": self.bucket,
            "scenario_count": self.scenario_count,
            "outcome_regression_count": self.outcome_regression_count,
            "score_regression_count": self.score_regression_count,
            "negative_outcome_mass": self.negative_outcome_mass,
            "negative_score_mass": self.negative_score_mass,
            "no_visible_helper_count": self.no_visible_helper_count,
            "no_called_helper_count": self.no_called_helper_count,
            "opportunity_score": self.opportunity_score,
            "reported_opportunity_score": self.reported_opportunity_score,
            "top_scenarios": [scenario.to_json() for scenario in self.top_scenarios],
        }


def _first_present(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_gap_buckets(path: Path) -> tuple[GapBucket, ...]:
    """Load ranked gap buckets from a machine-readable SAGE gap packet."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    buckets = payload.get("ranked_gap_buckets", payload.get("top_buckets", []))
    if not isinstance(buckets, list):
        return ()
    parsed = [GapBucket.from_json(item) for item in buckets if isinstance(item, dict)]
    return tuple(
        sorted(parsed, key=lambda bucket: bucket.opportunity_score, reverse=True)
    )


def write_gap_observation(path: Path, buckets: tuple[GapBucket, ...]) -> Path:
    """Write a stable, compact gap-observation artifact."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "artifact_type": "self_evolving_sage_gap_observation",
        "labels_inspected": False,
        "bucket_count": len(buckets),
        "ranked_gap_buckets": [bucket.to_json() for bucket in buckets],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
