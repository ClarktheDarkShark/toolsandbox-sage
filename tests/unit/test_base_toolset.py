import pytest

from sage_ts.runtime.base_toolset import apply_base_tool_policy
from tool_sandbox.common.execution_context import ExecutionContext
from tool_sandbox.common.scenario import Scenario


def test_removed_recency_policy_is_rejected() -> None:
    scenario = Scenario(
        starting_context=ExecutionContext(
            tool_allow_list=[
                "search_reminder",
                "get_current_timestamp",
                "shift_timestamp",
                "timestamp_to_datetime_info",
                "end_conversation",
            ]
        )
    )

    with pytest.raises(ValueError, match="only 'upstream'"):
        apply_base_tool_policy(scenario, "recency_reduced")


def test_upstream_policy_keeps_allowed_tools() -> None:
    scenario = Scenario(
        starting_context=ExecutionContext(
            tool_allow_list=["search_reminder", "shift_timestamp"]
        )
    )

    copied = apply_base_tool_policy(scenario, "upstream")

    assert copied.starting_context.tool_allow_list == [
        "search_reminder",
        "shift_timestamp",
    ]
