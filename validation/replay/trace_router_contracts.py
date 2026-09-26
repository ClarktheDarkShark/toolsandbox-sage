"""Focused trace, routing, and normalization contracts for the runtime refactor.

This module is validation-only.  It characterizes the order-sensitive seams
that are easiest to change accidentally when the runtime integration and
normalizer are consolidated.  It is loaded by ``snapshot.py`` only after the
selected checkout has been placed on ``sys.path``.
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from typing import Any, Callable


def _trace_contracts(
    *,
    capture: Callable[[Callable[[], Any]], dict[str, Any]],
    exact: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    import sage_ts.runtime.toolsandbox_integration as integration

    class TraceColumn(list[Any]):
        def to_list(self) -> list[Any]:
            return list(self)

    class FakeSandbox:
        def __init__(
            self,
            rows: list[dict[str, Any]],
            *,
            current_traces: list[Any] | None = None,
        ) -> None:
            self.rows = rows
            self.current_traces = current_traces

        def to_dicts(self) -> list[dict[str, Any]]:
            return self.rows

        def __getitem__(self, key: str) -> list[Any]:
            if key != "tool_trace":
                raise KeyError(key)
            return [self.current_traces]

    class FakeContext:
        def __init__(self, sandbox: FakeSandbox) -> None:
            self.sandbox = sandbox
            self.tool_allow_list = None
            self.name_to_tool: dict[str, Any] = {}

        def get_database(self, *args: Any, **kwargs: Any) -> FakeSandbox:
            return self.sandbox

    def trace(
        tool_name: str,
        result: Any,
        *,
        arguments: Any = None,
        include_arguments: bool = False,
    ) -> str:
        payload: dict[str, Any] = {"tool_name": tool_name, "result": result}
        if include_arguments:
            payload["arguments"] = arguments
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    original_get_current_context = integration.get_current_context

    def with_rows(
        rows: list[dict[str, Any]],
        callback: Callable[[], Any],
        *,
        current_traces: list[Any] | None = None,
    ) -> dict[str, Any]:
        integration.get_current_context = lambda: FakeContext(
            FakeSandbox(rows, current_traces=current_traces)
        )
        try:
            return capture(callback)
        finally:
            integration.get_current_context = original_get_current_context

    old_contact = {"person_id": "old", "name": "Earlier"}
    new_contact = {"person_id": "new", "name": "Later"}
    newest_contact = {"person_id": "newest", "name": "Last in row"}

    def records(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return with_rows(
            rows,
            lambda: integration._latest_original_tool_records(  # noqa: SLF001
                ("search_contacts",)
            ),
        )

    row_order_forward = records(
        [
            {"tool_trace": [trace("search_contacts", [old_contact])]},
            {"tool_trace": [trace("search_contacts", [new_contact])]},
        ]
    )
    row_order_reversed = records(
        [
            {"tool_trace": [trace("search_contacts", [new_contact])]},
            {"tool_trace": [trace("search_contacts", [old_contact])]},
        ]
    )
    within_row_forward = records(
        [
            {
                "tool_trace": TraceColumn(
                    [
                        trace("search_contacts", [new_contact]),
                        trace("search_contacts", [newest_contact]),
                    ]
                )
            }
        ]
    )
    within_row_reversed = records(
        [
            {
                "tool_trace": [
                    trace("search_contacts", [newest_contact]),
                    trace("search_contacts", [new_contact]),
                ]
            }
        ]
    )

    malformed = records(
        [
            {
                "tool_trace": [
                    trace("search_contacts", [old_contact]),
                    "{malformed-json",
                ]
            }
        ]
    )
    scalar_payload = with_rows(
        [{"tool_trace": [trace("get_current_timestamp", 123.5)]}],
        lambda: integration._latest_original_tool_payload(  # noqa: SLF001
            ("get_current_timestamp",)
        ),
    )
    list_payload = with_rows(
        [
            {
                "tool_trace": [
                    trace(
                        "search_contacts",
                        [
                            None,
                            {},
                            {"person_id": "first-nonempty"},
                            {"person_id": "later"},
                        ],
                    )
                ]
            }
        ],
        lambda: integration._latest_original_tool_payload(  # noqa: SLF001
            ("search_contacts",)
        ),
    )
    dict_payload = with_rows(
        [{"tool_trace": [trace("search_contacts", new_contact)]}],
        lambda: integration._latest_original_tool_payload(  # noqa: SLF001
            ("search_contacts",)
        ),
    )
    scalar_as_records = records(
        [{"tool_trace": [trace("search_contacts", "not-records")]}]
    )
    scalar_json_trace = with_rows(
        [{"tool_trace": [json.dumps("valid-json-scalar")]}],
        integration._latest_original_search_records,  # noqa: SLF001
    )

    latest_invalid_scalar = with_rows(
        [
            {
                "tool_trace": [
                    trace("get_current_timestamp", 100.0),
                    trace("get_current_timestamp", "not-a-number"),
                ]
            }
        ],
        lambda: integration._latest_original_tool_scalar(  # noqa: SLF001
            "get_current_timestamp"
        ),
    )
    latest_invalid_payload_falls_back = with_rows(
        [
            {
                "tool_trace": [
                    trace("search_contacts", old_contact),
                    trace("search_contacts", None),
                ]
            }
        ],
        lambda: integration._latest_original_tool_payload(  # noqa: SLF001
            ("search_contacts",)
        ),
    )
    latest_invalid_records_fall_back = records(
        [
            {
                "tool_trace": [
                    trace("search_contacts", [old_contact]),
                    trace("search_contacts", [new_contact, "invalid-record"]),
                ]
            }
        ]
    )

    complete_datetime = {
        "year": 2026,
        "month": 9,
        "day": 26,
        "hour": 12,
        "minute": 34,
        "second": 56,
    }

    def datetime_lookup(
        argument_timestamp: Any,
        requested_timestamp: Any,
        *,
        result: Any = complete_datetime,
        include_arguments: bool = True,
    ) -> dict[str, Any]:
        return with_rows(
            [
                {
                    "tool_trace": [
                        trace(
                            "timestamp_to_datetime_info",
                            result,
                            arguments={"timestamp": argument_timestamp},
                            include_arguments=include_arguments,
                        )
                    ]
                }
            ],
            lambda: integration._latest_datetime_info_for_timestamp(  # noqa: SLF001
                requested_timestamp
            ),
        )

    timestamp_cases = {
        "exact": datetime_lookup(200.0, 200.0),
        "positive_one_second_boundary": datetime_lookup(201.0, 200.0),
        "negative_one_second_boundary": datetime_lookup(199.0, 200.0),
        "outside_tolerance": datetime_lookup(201.000001, 200.0),
        "numeric_string_argument": datetime_lookup("200.5", 200.0),
        "invalid_argument": datetime_lookup("invalid", 200.0),
        "missing_arguments_are_accepted": datetime_lookup(
            None,
            200.0,
            include_arguments=False,
        ),
        "incomplete_result": datetime_lookup(
            200.0,
            200.0,
            result={"year": 2026, "month": 9},
        ),
        "invalid_requested_timestamp": datetime_lookup(200.0, "invalid"),
    }

    def setting_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return with_rows(
            rows,
            integration._visible_setting_state_summary_from_trace,  # noqa: SLF001
        )

    setting_cases = {
        "row_order_last_write_wins": setting_summary(
            [
                {
                    "tool_trace": [
                        trace(
                            "set_wifi_status",
                            None,
                            arguments={"on": True},
                            include_arguments=True,
                        )
                    ]
                },
                {
                    "tool_trace": [
                        trace(
                            "set_wifi_status",
                            None,
                            arguments={"on": False},
                            include_arguments=True,
                        )
                    ]
                },
            ]
        ),
        "within_row_last_write_wins": setting_summary(
            [
                {
                    "tool_trace": [
                        trace(
                            "set_wifi_status",
                            None,
                            arguments={"on": False},
                            include_arguments=True,
                        ),
                        trace(
                            "set_wifi_status",
                            None,
                            arguments={"on": True},
                            include_arguments=True,
                        ),
                    ]
                }
            ]
        ),
        "failed_later_write_is_ignored": setting_summary(
            [
                {
                    "tool_trace": [
                        trace(
                            "set_wifi_status",
                            None,
                            arguments={"on": True},
                            include_arguments=True,
                        ),
                        trace(
                            "set_wifi_status",
                            "failed to update",
                            arguments={"on": False},
                            include_arguments=True,
                        ),
                    ]
                }
            ]
        ),
        "already_state_counts_as_success": setting_summary(
            [
                {
                    "tool_trace": [
                        trace(
                            "set_location_service_status",
                            "Location service is already disabled",
                            arguments={"on": False},
                            include_arguments=True,
                        )
                    ]
                }
            ]
        ),
        "summary_uses_tool_name_order_not_event_order": setting_summary(
            [
                {
                    "tool_trace": [
                        trace(
                            "set_wifi_status",
                            None,
                            arguments={"on": True},
                            include_arguments=True,
                        ),
                        trace(
                            "set_cellular_service_status",
                            None,
                            arguments={"on": False},
                            include_arguments=True,
                        ),
                    ]
                }
            ]
        ),
        "malformed_and_missing_arguments_are_ignored": setting_summary(
            [
                {
                    "tool_trace": [
                        trace("set_wifi_status", None),
                        "{broken",
                    ]
                }
            ]
        ),
    }

    current_trace_count = with_rows(
        [],
        integration._current_tool_trace_count,  # noqa: SLF001
        current_traces=["first", "second", "third"],
    )

    return {
        "traversal_order": exact(
            {
                "row_forward": row_order_forward,
                "row_reversed": row_order_reversed,
                "within_row_forward": within_row_forward,
                "within_row_reversed": within_row_reversed,
            }
        ),
        "malformed_and_shapes": exact(
            {
                "malformed_json_skipped": malformed,
                "scalar_payload_wrapped": scalar_payload,
                "list_payload_first_nonempty_mapping": list_payload,
                "dict_payload_copied": dict_payload,
                "scalar_result_is_not_records": scalar_as_records,
                "valid_json_scalar_trace": scalar_json_trace,
            }
        ),
        "latest_invalid_result": exact(
            {
                "scalar_stops_at_latest_invalid": latest_invalid_scalar,
                "payload_skips_latest_invalid": latest_invalid_payload_falls_back,
                "records_skip_latest_invalid": latest_invalid_records_fall_back,
            }
        ),
        "timestamp_tolerance": exact(timestamp_cases),
        "setting_overwrite_order": exact(setting_cases),
        "current_trace_count": current_trace_count,
    }


def _normalization_contracts(
    *,
    tool_spec: Callable[..., Any],
    exact: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily, ToolInput
    from sage_ts.validation.output_normalization import normalize_generated_tool_output

    string = {"type": "string"}
    boolean = {"type": "boolean"}
    mapping = {"type": "object"}
    array = {"type": "array"}

    def generated(
        name: str,
        family: Any,
        *,
        inputs: tuple[Any, ...] = (),
        output_properties: dict[str, Any] | None = None,
        preserves: tuple[str, ...] = (),
        required: tuple[str, ...] = (),
        native: bool = False,
    ) -> Any:
        return GeneratedTool(
            spec=tool_spec(
                name=name,
                family=family,
                inputs=inputs,
                output_properties=output_properties,
                preserves=preserves,
                required_calls=required,
                native_action_delegation=native,
            ),
            code=f"def {name}(**kwargs):\n    return {{}}\n",
        )

    state = generated(
        "plan_device_state_action_sequence_v3",
        ToolFamily.STATE_PRECONDITION_HELPER,
        inputs=(
            ToolInput("user_request", "str", "Visible request."),
            ToolInput("visible_state_or_error", "str", "Visible state."),
        ),
        output_properties={
            "tool_name": string,
            "arguments": mapping,
            "should_call": boolean,
            "reason": string,
            "action_sequence": array,
            "final_response_recommendation": string,
            "continue_original_task_after_sequence": boolean,
            "abstain_reason": string,
        },
    )
    state_blank = {
        "tool_name": "",
        "arguments": {},
        "should_call": False,
        "reason": "",
        "action_sequence": [],
        "final_response_recommendation": "",
        "continue_original_task_after_sequence": False,
        "abstain_reason": "not_ready",
    }

    reminder = generated(
        "prepare_reminder_creation_args",
        ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        output_properties={
            "add_reminder_kwargs": mapping,
            "should_call_add_reminder": boolean,
            "location_status": string,
            "timestamp_source": string,
            "abstain_reason": string,
        },
    )
    reminder_raw = {
        "add_reminder_kwargs": {
            "content": "Pick up groceries",
            "reminder_timestamp": None,
            "latitude": None,
            "longitude": None,
        },
        "should_call_add_reminder": True,
        "location_status": "",
        "timestamp_source": "",
        "abstain_reason": "",
    }
    datetime_info = {
        "year": 2026,
        "month": 9,
        "day": 26,
        "hour": 12,
        "minute": 34,
        "second": 56,
    }

    def normalize_case(
        tool: Any,
        raw: Any,
        inputs: dict[str, Any] | None,
    ) -> dict[str, Any]:
        before = copy.deepcopy(raw)
        inputs_before = copy.deepcopy(inputs)
        result = normalize_generated_tool_output(tool, raw, inputs=inputs)
        if raw != before or inputs != inputs_before:
            raise RuntimeError("Normalizer mutated caller-owned inputs")
        return exact(
            {
                "result": result,
                "result_is_input_object": result is raw,
                "raw_before": before,
                "raw_after": raw,
                "inputs_before": inputs_before,
                "inputs_after": inputs,
            }
        )

    device_cases = {
        "duplicate_actions_removed_distinct_actions_keep_order": normalize_case(
            state,
            {
                **state_blank,
                "action_sequence": [
                    {
                        "tool_name": "set_wifi_status",
                        "arguments": {"on": True, "optional": None},
                        "reason": "first",
                    },
                    {
                        "tool_name": "set_wifi_status",
                        "arguments": {"on": False},
                        "reason": "second",
                    },
                    {
                        "tool_name": "set_wifi_status",
                        "arguments": {"on": True},
                        "reason": "duplicate-with-different-reason",
                    },
                    "opaque-sequence-marker",
                ],
            },
            {"user_request": "Adjust Wi-Fi"},
        ),
        "three_step_location_recovery": normalize_case(
            state,
            dict(state_blank),
            {
                "user_request": "Find weather near me",
                "visible_state_or_error": "PermissionError: location is disabled",
            },
        ),
        "location_recovery_skips_known_clear_steps": normalize_case(
            state,
            dict(state_blank),
            {
                "user_request": "Find weather near me",
                "visible_state_or_error": (
                    "PermissionError: location is disabled; "
                    "low battery mode is off; wifi is on"
                ),
            },
        ),
        "direct_request_precedes_conflicting_blocker": normalize_case(
            state,
            dict(state_blank),
            {
                "user_request": "Turn Wi-Fi off",
                "visible_state_or_error": "cellular service is disabled",
            },
        ),
        "low_battery_is_deliberately_not_a_direct_setting_marker": normalize_case(
            state,
            dict(state_blank),
            {
                "user_request": "Turn on low battery mode",
                "visible_state_or_error": "low battery mode is disabled",
            },
        ),
        "known_low_battery_off_removes_only_redundant_clear": normalize_case(
            state,
            {
                **state_blank,
                "action_sequence": [
                    {
                        "tool_name": "set_low_battery_mode_status",
                        "arguments": {"on": False},
                        "reason": "already-clear",
                    },
                    {
                        "tool_name": "set_cellular_service_status",
                        "arguments": {"on": True},
                        "reason": "enable-cellular",
                    },
                ],
            },
            {"visible_state_summary": "low battery mode is off"},
        ),
    }

    relative_inputs = {
        "content": "Pick up groceries",
        "current_timestamp": 1_790_422_496.0,
        "day_offset": 1,
        "hour": 9,
        "minute": 30,
        "current_datetime_info": datetime_info,
    }
    reminder_cases = {
        "required_location_missing": normalize_case(
            reminder,
            copy.deepcopy(reminder_raw),
            {**relative_inputs, "location_required": True, "location_available": False},
        ),
        "optional_location_pending": normalize_case(
            reminder,
            copy.deepcopy(reminder_raw),
            {
                **relative_inputs,
                "location_requested": True,
                "location_available": False,
                "location_lookup_failed": False,
            },
        ),
        "optional_location_failed_proceeds_without_coordinates": normalize_case(
            reminder,
            copy.deepcopy(reminder_raw),
            {
                **relative_inputs,
                "location_requested": True,
                "location_available": False,
                "location_lookup_failed": True,
            },
        ),
        "absolute_prepared_timestamp_wins": normalize_case(
            reminder,
            {
                **copy.deepcopy(reminder_raw),
                "add_reminder_kwargs": {
                    "content": "Pick up groceries",
                    "reminder_timestamp": 1_900_000_000.0,
                },
            },
            {
                **relative_inputs,
                "resolved_reminder_timestamp": 1_800_000_000.0,
            },
        ),
        "resolved_timestamp_recovers_missing_prepared_value": normalize_case(
            reminder,
            copy.deepcopy(reminder_raw),
            {
                "content": "Pick up groceries",
                "resolved_reminder_timestamp": 1_800_000_000.0,
            },
        ),
        "relative_timestamp_from_visible_datetime": normalize_case(
            reminder,
            copy.deepcopy(reminder_raw),
            relative_inputs,
        ),
        "relative_fields_without_datetime_abstain": normalize_case(
            reminder,
            copy.deepcopy(reminder_raw),
            {
                "content": "Pick up groceries",
                "current_timestamp": 1_790_422_496.0,
                "day_offset": 1,
                "hour": 9,
                "minute": 30,
                "current_datetime_info": {},
            },
        ),
        "missing_all_time_information_abstains": normalize_case(
            reminder,
            copy.deepcopy(reminder_raw),
            {"content": "Pick up groceries"},
        ),
        "coordinates_strip_location_suffix": normalize_case(
            reminder,
            {
                **copy.deepcopy(reminder_raw),
                "add_reminder_kwargs": {
                    "content": "Pick up groceries near Market Street",
                    "reminder_timestamp": 1_900_000_000.0,
                },
            },
            {
                "content": "Pick up groceries near Market Street",
                "location_requested": True,
                "location_available": True,
                "latitude": 37.0,
                "longitude": -122.0,
                "resolved_reminder_timestamp": 1_900_000_000.0,
            },
        ),
    }

    native = generated(
        "native_identity_passthrough",
        ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        output_properties={
            "downstream_tool_kwargs": mapping,
            "abstain_reason": string,
        },
        preserves=("remove_contact",),
        required=("remove_contact",),
        native=True,
    )
    non_native = generated(
        "non_native_null_cleanup",
        ToolFamily.CANONICALIZER,
        output_properties={"downstream_tool_kwargs": mapping},
    )
    native_raw = {
        "downstream_tool_kwargs": {"person_id": "p1", "optional": None},
        "abstain_reason": "",
    }
    non_native_raw = {
        "downstream_tool_kwargs": {"person_id": "p1", "optional": None},
        "root_null_is_not_a_kwarg": None,
    }
    passthrough_cases = {
        "native_identity_precedes_null_cleanup": normalize_case(
            native,
            native_raw,
            {},
        ),
        "non_native_kwargs_are_cleaned_first": normalize_case(
            non_native,
            non_native_raw,
            {},
        ),
    }

    return {
        "device_state": exact(device_cases),
        "reminder": exact(reminder_cases),
        "native_and_null_order": exact(passthrough_cases),
    }


def _routing_contracts(
    *,
    tool_spec: Callable[..., Any],
    accepted_entry: Callable[[Any], Any],
    exact: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily, ToolInput
    from sage_ts.runtime.toolsandbox_integration import route_registry_entries

    string = {"type": "string"}
    mapping = {"type": "object"}

    def entry(
        name: str,
        *,
        family: Any = ToolFamily.CANONICALIZER,
        inputs: tuple[Any, ...] = (),
        output_properties: dict[str, Any] | None = None,
        positive: tuple[str, ...] = (),
        negative: tuple[str, ...] = (),
        preserves: tuple[str, ...] = (),
        required: tuple[str, ...] = (),
        retired: bool = False,
    ) -> Any:
        normalized_inputs = inputs or (ToolInput("value", "str", "Visible value."),)
        normalized_output = output_properties
        normalized_negative = negative
        normalized_preserves = preserves
        normalized_required = required
        abstain_behavior = ""
        if family == ToolFamily.STATE_PRECONDITION_HELPER:
            normalized_inputs = inputs or (
                ToolInput("next_action", "str", "Visible next setter action."),
            )
            normalized_output = normalized_output or {
                "tool_name": {
                    "type": "string",
                    "enum": ["", "set_wifi_status"],
                },
                "arguments": mapping,
                "should_call": {"type": "boolean"},
                "reason": string,
            }
            normalized_negative = normalized_negative or ("unknown service",)
            normalized_preserves = normalized_preserves or ("set_wifi_status",)
            normalized_required = normalized_required or ("set_wifi_status",)
            abstain_behavior = "Abstain on an unknown service target."
        elif family == ToolFamily.SEARCH_FILTER_RANKING_HELPER:
            normalized_output = normalized_output or {
                "selected_record": mapping,
                "selected_id": string,
                "value": string,
                "tie_candidates": {"type": "array"},
                "abstain_reason": string,
            }
            normalized_negative = normalized_negative or ("ambiguous tie",)
            abstain_behavior = "Abstain on ambiguous ties."
        elif family == ToolFamily.COMPOSITE_WORKFLOW_HELPER:
            normalized_preserves = normalized_preserves or (
                normalized_required or ("search_contacts",)
            )
            normalized_required = normalized_required or normalized_preserves
            normalized_output = normalized_output or {
                "downstream_tool_kwargs": mapping,
                "abstain_reason": string,
            }
            if not any(str(key).endswith("_kwargs") for key in normalized_output):
                normalized_output = {
                    **normalized_output,
                    "downstream_tool_kwargs": mapping,
                }
            normalized_negative = normalized_negative or ("insufficient_information",)
            abstain_behavior = "Abstain on insufficient_information."
        generated = GeneratedTool(
            spec=tool_spec(
                name=name,
                family=family,
                inputs=normalized_inputs,
                output_properties=normalized_output,
                positive_triggers=positive,
                negative_triggers=normalized_negative,
                preserves=normalized_preserves,
                required_calls=normalized_required,
                abstain_behavior=abstain_behavior,
            ),
            code=f"def {name}(**kwargs):\n    return {{}}\n",
        )
        result = accepted_entry(generated)
        return replace(result, retired=True) if retired else result

    def route(
        entries: dict[str, Any],
        *,
        context: str,
        family: str = "edge_family",
        base_tools: set[str] | None = None,
        lifecycle: dict[str, dict[str, Any]] | None = None,
        cap: int = 4,
    ) -> dict[str, Any]:
        selected, decisions = route_registry_entries(
            entries,
            scenario_name=family,
            max_bundle_size=cap,
            available_base_tools=base_tools,
            lifecycle_state=lifecycle,
            task_context_text=context,
            task_family_key=family,
        )
        return exact(
            {
                "input_entry_order": list(entries),
                "selected_order": [item.tool.spec.tool_name for item in selected],
                "decision_order": list(decisions),
                "decisions": {
                    name: decision.to_json() for name, decision in decisions.items()
                },
            }
        )

    equal_entries = {
        name: entry(name, positive=("equal_signal",))
        for name in ("zeta_equal", "alpha_equal", "middle_equal")
    }
    budget_entries = {
        "zeta_low": entry("zeta_low", positive=("one",)),
        "echo_high": entry("echo_high", positive=("one", "two", "three")),
        "delta_mid": entry("delta_mid", positive=("one", "two")),
        "charlie_high": entry("charlie_high", positive=("one", "two", "three")),
        "bravo_low": entry("bravo_low", positive=("one",)),
        "alpha_high": entry("alpha_high", positive=("one", "two", "three")),
    }
    order_cases = {
        "equal_score_uses_lexical_name_order": route(
            equal_entries,
            context="request=test signals=equal_signal",
            base_tools=set(),
        ),
        "four_tool_cap_is_applied_after_score_then_lexical_sort": route(
            budget_entries,
            context="request=test signals=one two three",
            base_tools=set(),
            cap=4,
        ),
    }

    lifecycle_tool_name = "prepare_specific_location_search_args"
    life_entry = entry(
        lifecycle_tool_name,
        family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        inputs=(ToolInput("location_query", "str", "Visible qualified place."),),
        output_properties={"search_kwargs": mapping, "abstain_reason": string},
        positive=("location_phrase", "external_lookup"),
        preserves=("search_location_around_lat_lon",),
        required=("search_location_around_lat_lon",),
    )
    lifecycle_context = (
        "request=Find weather near 1 Market Street "
        "signals=location_phrase external_lookup"
    )
    lifecycle_base_tools = {"search_location_around_lat_lon"}
    lifecycle_cases = {
        "retired_registry_entry_is_always_hidden": route(
            {
                "retired_lifecycle_edge_helper": entry(
                    "retired_lifecycle_edge_helper",
                    positive=("life_signal",),
                    retired=True,
                )
            },
            context="request=test signals=life_signal",
        ),
        "parked_is_hidden": route(
            {lifecycle_tool_name: life_entry},
            context=lifecycle_context,
            base_tools=lifecycle_base_tools,
            lifecycle={lifecycle_tool_name: {"decision": "parked"}},
        ),
        "one_family_harm_is_below_repair_threshold": route(
            {lifecycle_tool_name: life_entry},
            context=lifecycle_context,
            base_tools=lifecycle_base_tools,
            lifecycle={
                lifecycle_tool_name: {
                    "decision": "retain_with_route_repair",
                    "route_repair_families": ["edge_family"],
                    "harmful_called_families": ["edge_family"],
                    "helpful_called_families": [],
                    "failed_count": 1,
                }
            },
        ),
        "two_family_harms_hide_failed_tool": route(
            {lifecycle_tool_name: life_entry},
            context=lifecycle_context,
            base_tools=lifecycle_base_tools,
            lifecycle={
                lifecycle_tool_name: {
                    "decision": "retain_with_route_repair",
                    "route_repair_families": ["edge_family"],
                    "harmful_called_families": ["edge_family", "edge_family"],
                    "helpful_called_families": [],
                    "failed_count": 1,
                }
            },
        ),
        "clean_retained_tool_visible_signal_overrides_coarse_family_harm": route(
            {lifecycle_tool_name: life_entry},
            context=lifecycle_context,
            base_tools=lifecycle_base_tools,
            lifecycle={
                lifecycle_tool_name: {
                    "decision": "retain_with_route_repair",
                    "route_repair_families": ["edge_family"],
                    "harmful_called_families": ["edge_family", "edge_family"],
                    "helpful_called_families": [],
                    "failed_count": 0,
                    "side_effect_incident_count": 0,
                }
            },
        ),
        "exact_harmful_scenario_beats_visible_signal": route(
            {lifecycle_tool_name: life_entry},
            context=lifecycle_context,
            base_tools=lifecycle_base_tools,
            lifecycle={
                lifecycle_tool_name: {
                    "decision": "retain_with_route_repair",
                    "harmful_called_scenarios": ["edge_family"],
                    "failed_count": 0,
                    "side_effect_incident_count": 0,
                }
            },
        ),
        "needs_repair_two_harms_are_hidden": route(
            {lifecycle_tool_name: life_entry},
            context=lifecycle_context,
            base_tools=lifecycle_base_tools,
            lifecycle={
                lifecycle_tool_name: {
                    "decision": "needs_repair",
                    "route_repair_families": ["edge_family"],
                    "harmful_called_families": ["edge_family", "edge_family"],
                }
            },
        ),
    }

    all_required = entry(
        "all_required_helper",
        positive=("downstream_signal",),
        required=("search_contacts", "search_messages"),
    )
    any_enum = entry(
        "any_enum_helper",
        positive=("downstream_signal",),
        required=("missing_static_requirement",),
        output_properties={
            "tool_name": {
                "type": "string",
                "enum": ["search_contacts", "search_messages"],
            },
            "arguments": mapping,
        },
    )
    native_alternatives = entry(
        "native_alternative_helper",
        positive=("downstream_signal",),
        required=("search_contacts", "remove_contact", "modify_contact"),
    )
    producer_only_selector = entry(
        "producer_only_selector",
        family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
        inputs=(
            ToolInput("records", "list", "Visible records."),
            ToolInput("selection_mode", "str", "Visible mode."),
        ),
        output_properties={
            "selected_record": mapping,
            "selected_id": string,
            "value": string,
            "tie_candidates": {"type": "array"},
            "abstain_reason": string,
        },
        positive=("downstream_signal",),
        preserves=("search_contacts", "remove_contact"),
        required=("search_contacts", "remove_contact"),
    )
    state_bypass = entry(
        "state_bypass_helper",
        family=ToolFamily.STATE_PRECONDITION_HELPER,
        positive=("downstream_signal",),
        required=("set_wifi_status",),
    )
    downstream_cases = {
        "all_required_missing_one": route(
            {"all_required_helper": all_required},
            context="request=test signals=downstream_signal",
            base_tools={"search_contacts"},
        ),
        "all_required_present": route(
            {"all_required_helper": all_required},
            context="request=test signals=downstream_signal",
            base_tools={"search_contacts", "search_messages"},
        ),
        "enum_requires_any_one": route(
            {"any_enum_helper": any_enum},
            context="request=test signals=downstream_signal",
            base_tools={"search_messages"},
        ),
        "native_alternative_needs_producer_and_one_action": route(
            {"native_alternative_helper": native_alternatives},
            context="request=test signals=downstream_signal",
            base_tools={"search_contacts", "remove_contact"},
        ),
        "native_alternative_action_without_producer_is_hidden": route(
            {"native_alternative_helper": native_alternatives},
            context="request=test signals=downstream_signal",
            base_tools={"remove_contact"},
        ),
        "native_alternative_producer_without_action_is_hidden": route(
            {"native_alternative_helper": native_alternatives},
            context="request=test signals=downstream_signal",
            base_tools={"search_contacts"},
        ),
        "selector_requires_only_read_producer": route(
            {"producer_only_selector": producer_only_selector},
            context="request=test signals=downstream_signal",
            base_tools={"search_contacts"},
        ),
        "state_helper_bypasses_static_downstream_check": route(
            {"state_bypass_helper": state_bypass},
            context="request=test signals=downstream_signal",
            base_tools=set(),
        ),
    }

    lower = entry(
        "lower_shared_helper",
        family=ToolFamily.CANONICALIZER,
        inputs=(ToolInput("value", "str", "Visible value."),),
        positive=("shared_signal",),
        required=("search_contacts",),
    )
    composite_alpha = entry(
        "alpha_composite_helper",
        family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        inputs=(ToolInput("value", "str", "Visible value."),),
        output_properties={"value": string, "abstain_reason": string},
        positive=("shared_signal",),
        preserves=("search_contacts",),
        required=("search_contacts",),
    )
    composite_zeta = entry(
        "zeta_composite_helper",
        family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
        inputs=(ToolInput("value", "str", "Visible value."),),
        output_properties={"value": string, "abstain_reason": string},
        positive=("shared_signal",),
        preserves=("search_contacts",),
        required=("search_contacts",),
    )
    subsumption_cases = {
        "lexically_first_composite_suppresses_lower_level": route(
            {
                "zeta_composite_helper": composite_zeta,
                "lower_shared_helper": lower,
                "alpha_composite_helper": composite_alpha,
            },
            context="request=test signals=shared_signal",
            base_tools={"search_contacts"},
        )
    }

    return {
        "ordering_and_budget": exact(order_cases),
        "lifecycle_thresholds": exact(lifecycle_cases),
        "downstream_contracts": exact(downstream_cases),
        "subsumption_collisions": exact(subsumption_cases),
    }


def run_probe(
    *,
    tool_spec: Callable[..., Any],
    accepted_entry: Callable[[Any], Any],
    capture: Callable[[Callable[[], Any]], dict[str, Any]],
    exact: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    """Return the complete validation-only edge-contract snapshot."""

    payload = {
        "trace_order": _trace_contracts(capture=capture, exact=exact),
        "normalization_edges": _normalization_contracts(
            tool_spec=tool_spec,
            exact=exact,
        ),
        "routing_edges": _routing_contracts(
            tool_spec=tool_spec,
            accepted_entry=accepted_entry,
            exact=exact,
        ),
    }
    return {
        "contract_schema_version": 1,
        "contract_sections": list(payload),
        "payload": payload,
    }
