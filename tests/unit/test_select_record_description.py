# mypy: ignore-errors
"""Tests for select_record_by_timestamp_extreme description affordance requirements.

These tests verify that the registered description includes the complete call path
(get_current_timestamp → search_messages with creation_timestamp_upperbound → helper)
and the symmetric imperative for both latest and oldest modes.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))


def _load_spec():
    spec_module = importlib.import_module(
        "scripts.register_select_record_by_timestamp_extreme"
    )
    return spec_module.SPEC


def test_description_includes_get_current_timestamp_call_path() -> None:
    spec = _load_spec()
    desc = spec.description.lower()
    assert "get_current_timestamp" in desc, (
        "Description must mention get_current_timestamp so the agent knows to call it first"
    )


def test_description_includes_creation_timestamp_upperbound() -> None:
    spec = _load_spec()
    desc = spec.description.lower()
    assert "creation_timestamp_upperbound" in desc, (
        "Description must include creation_timestamp_upperbound pattern for message retrieval"
    )


def test_description_has_symmetric_oldest_imperative() -> None:
    spec = _load_spec()
    desc = spec.description.lower()
    assert "oldest" in desc, "Description must include oldest mode guidance"
    assert "earliest" in desc or "first" in desc or "oldest" in desc, (
        "Description must cover oldest/earliest/first synonyms"
    )


def test_description_has_symmetric_latest_imperative() -> None:
    spec = _load_spec()
    desc = spec.description.lower()
    assert "latest" in desc or "most recent" in desc or "newest" in desc, (
        "Description must cover latest/most recent/newest synonyms"
    )


def test_description_prohibits_manual_timestamp_comparison() -> None:
    spec = _load_spec()
    desc = spec.description.lower()
    assert (
        "do not attempt manual timestamp" in desc
        or "do not manually compare" in desc
        or ("do not" in desc and "timestamp" in desc)
    ), "Description must prohibit manual timestamp comparison"


def test_description_prohibits_empty_search_call() -> None:
    spec = _load_spec()
    desc = spec.description
    assert (
        "search_messages({})" in desc
        or "empty" in desc.lower()
        or "no results" in desc.lower()
    ), (
        "Description should warn against empty search_messages call which returns no results"
    )


def test_description_has_must_call_imperative() -> None:
    spec = _load_spec()
    desc = spec.description
    assert "MUST" in desc or "you must" in desc.lower(), (
        "Description must include an explicit imperative (MUST) for calling this helper"
    )


def test_description_preserves_tie_behavior() -> None:
    spec = _load_spec()
    desc = spec.description.lower()
    assert "tie" in desc, (
        "Description must include tie-breaking behavior (required by candidate gate)"
    )


def test_description_includes_negative_guards() -> None:
    spec = _load_spec()
    desc = spec.description.lower()
    assert (
        "no records" in desc
        or "not retrieved" in desc
        or "pure reminder creation" in desc
    ), "Description must include negative applicability guards"


def test_candidate_gate_passes() -> None:
    from sage_ts.adequacy.candidate_gate import evaluate_candidate_gate

    spec = _load_spec()
    decision = evaluate_candidate_gate(spec)
    assert decision.allowed, f"Candidate gate blocked: {decision.reason}"


def test_validation_accepts_all_examples() -> None:
    spec_module = importlib.import_module(
        "scripts.register_select_record_by_timestamp_extreme"
    )
    from sage_ts.validation.sandbox_validator import validate_generated_tool

    result = validate_generated_tool(spec_module.TOOL, spec_module.EXAMPLES)
    assert result.accepted, f"Validation failed: {result.errors}"
    assert result.held_out_check_count >= 1
    assert result.negative_applicability_count >= 2
    assert result.runtime_smoke_passed
