from types import SimpleNamespace

import pytest

import sage_ts.adequacy.inadequacy_classifier as classifier
from tool_sandbox.common.execution_context import ExecutionContext
from tool_sandbox.common.scenario import Scenario


@pytest.fixture
def visible_context(monkeypatch: pytest.MonkeyPatch) -> Scenario:
    monkeypatch.setattr(
        classifier,
        "visible_task_context_from_scenario",
        lambda _scenario: SimpleNamespace(signals=(), available_tools=()),
    )
    return Scenario(starting_context=ExecutionContext())


def test_visible_trace_classifier_ignores_canonical_failure_when_outcome_succeeds(
    visible_context: Scenario,
) -> None:
    observations = classifier.classify_visible_trace_observations(
        "reminder_task",
        visible_context,
        {
            "similarity": 0.0,
            "outcome_similarity": 1.0,
            "agent_actions": "Tomorrow at 3 pm, call add_reminder.",
        },
    )

    assert observations == ()


def test_visible_trace_classifier_uses_outcome_failure_despite_canonical_success(
    visible_context: Scenario,
) -> None:
    observations = classifier.classify_visible_trace_observations(
        "reminder_task",
        visible_context,
        {
            "similarity": 1.0,
            "outcome_similarity": 0.5,
            "agent_actions": "Tomorrow at 3 pm, call add_reminder.",
        },
    )

    assert [item.canonical_key for item in observations] == [
        "canonicalizer:relative_day_time_timestamp"
    ]


def test_visible_trace_classifier_requires_outcome_value(
    visible_context: Scenario,
) -> None:
    with pytest.raises(ValueError, match="requires a non-null outcome_similarity"):
        classifier.classify_visible_trace_observations(
            "reminder_task",
            visible_context,
            {
                "similarity": 0.0,
                "agent_actions": "Tomorrow at 3 pm, call add_reminder.",
            },
        )
