# mypy: ignore-errors
"""Focused tests for resolve_search_window_or_bounds registration and semantics."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))


def _load_module():
    return importlib.import_module("scripts.register_resolve_search_window_or_bounds")


def _call_helper(**kwargs):
    namespace: dict[str, object] = {}
    module = _load_module()
    exec(module.TOOL_CODE, namespace)
    return namespace["resolve_search_window_or_bounds"](**kwargs)


def test_description_mentions_get_current_timestamp_and_original_search() -> None:
    module = _load_module()
    desc = module.SPEC.description.lower()
    assert "get_current_timestamp" in desc
    assert (
        "search_messages({})" in module.SPEC.description
        or "search_reminder({})" in module.SPEC.description
    )
    assert "target_tool_name" in desc


def test_validation_and_candidate_gate_pass() -> None:
    from sage_ts.adequacy.candidate_gate import evaluate_candidate_gate
    from sage_ts.validation.sandbox_validator import validate_generated_tool

    module = _load_module()
    decision = evaluate_candidate_gate(module.SPEC)
    assert decision.allowed, decision.reason
    result = validate_generated_tool(module.TOOL, module.EXAMPLES)
    assert result.accepted, result.errors
    assert result.held_out_check_count >= 1
    assert result.negative_applicability_count >= 2
    assert result.runtime_smoke_passed


def test_yesterday_creation_window_is_bounded() -> None:
    result = _call_helper(
        current_timestamp=1777380998.0,
        phrase="yesterday",
        target_domain="reminder",
        timestamp_intent="creation",
        direction="yesterday",
        content_keyword="",
        lookback_days=0,
        timezone_offset=0.0,
    )
    assert result["should_call_search"] is True
    assert result["target_tool_name"] == "search_reminder"
    assert result["search_kwargs"]["creation_timestamp_lowerbound"] == 1777248000.0
    assert result["search_kwargs"]["creation_timestamp_upperbound"] == 1777334399.0


def test_later_today_due_window_uses_now_to_end_of_day() -> None:
    result = _call_helper(
        current_timestamp=1777380998.0,
        phrase="later today",
        target_domain="reminder",
        timestamp_intent="reminder",
        direction="later_today",
        content_keyword="",
        lookback_days=0,
        timezone_offset=0.0,
    )
    assert result["should_call_search"] is True
    assert result["search_kwargs"]["reminder_timestamp_lowerbound"] == 1777380998.0
    assert result["search_kwargs"]["reminder_timestamp_upperbound"] == 1777420799.0


def test_latest_message_path_avoids_no_criteria_search() -> None:
    result = _call_helper(
        current_timestamp=1777380998.0,
        phrase="latest message",
        target_domain="message",
        timestamp_intent="message_creation",
        direction="latest",
        content_keyword="project",
        lookback_days=0,
        timezone_offset=0.0,
    )
    assert result["should_call_search"] is True
    assert result["target_tool_name"] == "search_messages"
    assert result["search_kwargs"] == {
        "creation_timestamp_upperbound": 1777380998.0,
        "content": "project",
    }


def test_message_phrase_overrides_bad_direction_annotation() -> None:
    result = _call_helper(
        current_timestamp=1777380998.0,
        phrase="oldest message",
        target_domain="message",
        timestamp_intent="past",
        direction="backward",
        content_keyword="",
        lookback_days=0,
        timezone_offset=0.0,
    )
    assert result["should_call_search"] is True
    assert result["target_tool_name"] == "search_messages"
    assert result["interpretation"] == "oldest"
    assert result["search_kwargs"] == {
        "creation_timestamp_upperbound": 1777380998.0,
    }


def test_first_message_phrase_maps_to_oldest_even_with_noisy_direction() -> None:
    result = _call_helper(
        current_timestamp=1777380998.0,
        phrase="first ever text",
        target_domain="message",
        timestamp_intent="message_creation",
        direction="older",
        content_keyword="",
        lookback_days=0,
        timezone_offset=0.0,
    )
    assert result["should_call_search"] is True
    assert result["target_tool_name"] == "search_messages"
    assert result["interpretation"] == "oldest"
    assert result["search_kwargs"] == {
        "creation_timestamp_upperbound": 1777380998.0,
    }


def test_missing_current_timestamp_abstains() -> None:
    result = _call_helper(
        current_timestamp=0.0,
        phrase="today",
        target_domain="reminder",
        timestamp_intent="creation",
        direction="today",
        content_keyword="",
        lookback_days=0,
        timezone_offset=0.0,
    )
    assert result["should_call_search"] is False
    assert result["abstain_reason"] == "missing_current_timestamp"


def test_ambiguous_phrase_abstains() -> None:
    result = _call_helper(
        current_timestamp=1777380998.0,
        phrase="sometime soon",
        target_domain="message",
        timestamp_intent="message_creation",
        direction="",
        content_keyword="",
        lookback_days=0,
        timezone_offset=0.0,
    )
    assert result["should_call_search"] is False
    assert result["abstain_reason"] == "ambiguous_phrase"
