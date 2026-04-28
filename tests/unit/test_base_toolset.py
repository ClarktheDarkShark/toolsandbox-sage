from sage_ts.runtime.base_toolset import apply_base_tool_policy

from tool_sandbox.common.execution_context import ExecutionContext
from tool_sandbox.common.scenario import Scenario


def test_recency_reduced_policy_removes_time_decomposition_tools() -> None:
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

    reduced = apply_base_tool_policy(scenario, "recency_reduced")

    assert reduced.starting_context.tool_allow_list == [
        "search_reminder",
        "get_current_timestamp",
        "end_conversation",
    ]
    assert (
        scenario.starting_context.tool_allow_list
        is not reduced.starting_context.tool_allow_list
    )


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
