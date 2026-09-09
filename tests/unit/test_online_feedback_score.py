# mypy: ignore-errors
import json

import pytest

from sage_ts.evaluation.online_feedback_score import (
    _content_similarity,
    compute_outcome_score,
)
from tool_sandbox.cli.utils import resolve_scenarios
from tool_sandbox.common.execution_context import (
    DatabaseNamespace,
    ExecutionContext,
    RoleType,
)
from tool_sandbox.common.tool_discovery import ToolBackend


def test_content_similarity_credits_correct_numeric_answer_with_equivalent_wording() -> (
    None
):
    assert (
        _content_similarity(
            "It is 238 days till Christmas Day",
            "Therefore, there are approximately 237 days until Christmas Day.",
        )
        == 1.0
    )


def test_content_similarity_credits_answer_value_inside_verbose_response() -> None:
    assert (
        _content_similarity(
            "AAPL",
            "The stock symbol for Apple is typically known to be **AAPL**.",
        )
        == 1.0
    )


def test_content_similarity_rejects_wrong_numeric_answer() -> None:
    assert _content_similarity(
        "It is 238 days till Christmas Day",
        "It is 12 days till Christmas Day.",
    ) == pytest.approx(0.0)


def test_outcome_score_uses_target_facts_for_route_independent_final_answer() -> None:
    scenario_name = "find_days_till_holiday_3_distraction_tools"
    scenario = resolve_scenarios(
        desired_scenario_names=[scenario_name],
        preferred_tool_backend=ToolBackend.DEFAULT,
    )[scenario_name]
    current_timestamp = 1777597539.872639
    execution_context = ExecutionContext()
    execution_context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.EXECUTION_ENVIRONMENT,
                "recipient": RoleType.AGENT,
                "content": str(current_timestamp),
                "tool_trace": [
                    json.dumps(
                        {
                            "tool_name": "get_current_timestamp",
                            "arguments": {},
                            "result": current_timestamp,
                        }
                    )
                ],
            },
            {
                "sender": RoleType.AGENT,
                "recipient": RoleType.USER,
                "content": "There are 239 days until Christmas Day.",
            },
        ],
    )

    outcome = compute_outcome_score(
        scenario,
        execution_context,
        canonical_milestone_scores={0: 1.0, 1: 0.0, 2: 0.0, 3: 0.0},
        minefield_similarity=0.0,
    )

    assert outcome["outcome_similarity"] == 1.0
    assert [check["kind"] for check in outcome["outcome_checks"]] == [
        "route",
        "route",
        "route",
        "answer",
    ]


def test_outcome_score_only_uses_final_agent_to_user_message() -> None:
    scenario_name = "find_days_till_holiday_3_distraction_tools"
    scenario = resolve_scenarios(
        desired_scenario_names=[scenario_name],
        preferred_tool_backend=ToolBackend.DEFAULT,
    )[scenario_name]
    execution_context = ExecutionContext()
    execution_context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.EXECUTION_ENVIRONMENT,
                "recipient": RoleType.AGENT,
                "content": str(1700000000.0),
                "tool_trace": [
                    json.dumps(
                        {
                            "tool_name": "get_current_timestamp",
                            "arguments": {},
                            "result": 1700000000.0,
                        }
                    )
                ],
            },
            {
                "sender": RoleType.AGENT,
                "recipient": RoleType.USER,
                "content": "There are 238 days until Christmas Day.",
            },
            {
                "sender": RoleType.AGENT,
                "recipient": RoleType.USER,
                "content": "No clue.",
            },
        ],
    )

    outcome = compute_outcome_score(
        scenario,
        execution_context,
        canonical_milestone_scores={0: 1.0, 1: 0.0, 2: 0.0, 3: 0.0},
        minefield_similarity=0.0,
    )

    assert outcome["outcome_similarity"] == 0.0
