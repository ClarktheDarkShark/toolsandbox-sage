"""Exact trajectory/runtime contracts for a future facts-layer refactor.

This validation-only probe characterizes the artifact readers and the
conversation/ToolSandbox-trace rules used after a generated helper runs.  It
uses only synthetic public trajectory fields and never replays provider output.
"""

from __future__ import annotations

import copy
import importlib
import json
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any


def _wire(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _wire(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_wire(item) for item in value]
    if isinstance(value, set):
        return sorted((_wire(item) for item in value), key=repr)
    return str(value)


def _capture(call: Callable[[], Any], *, fixture_root: Path) -> dict[str, Any]:
    try:
        value = call()
    except Exception as error:  # noqa: BLE001 - exception behavior is the contract.
        return {
            "status": "raised",
            "exception_type": type(error).__name__,
            "message": str(error).replace(str(fixture_root), "<fixture>"),
        }
    return {
        "status": "returned",
        "python_type": type(value).__name__,
        "value": _wire(value),
    }


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _read_jsonl(path: Path) -> list[Any]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _tool_call(name: Any, *, arguments: Any = "{}", call_id: Any = None) -> dict[str, Any]:
    function: dict[str, Any] = {"name": name, "arguments": arguments}
    payload: dict[str, Any] = {"function": function}
    if call_id is not None:
        payload["id"] = call_id
    return payload


def _assistant_call(*names: str) -> dict[str, Any]:
    return {
        "role": "assistant",
        "tool_calls": [
            _tool_call(name, call_id=f"call-{index}")
            for index, name in enumerate(names)
        ],
    }


def _content_parsing_contract(adapter: Any, fixture_root: Path) -> dict[str, Any]:
    values: dict[str, Any] = {
        "none": None,
        "bool": False,
        "integer": 7,
        "float": 3.5,
        "mapping": {"z": 1, "a": [2]},
        "list": [1, {"b": 2}],
        "unsupported_tuple_object": ("already", "tuple"),
        "empty": "",
        "whitespace": "  \n\t ",
        "json_mapping": ' {"z":1,"a":2} ',
        "json_list": '[1,{"a":2}]',
        "json_boolean_precedes_literal": "true",
        "json_null_precedes_literal": "null",
        "json_string": '"text"',
        "python_mapping_fallback": "{'single': 1, 'truth': True}",
        "python_tuple_fallback": "('a', 2)",
        "python_set_fallback": "{'b', 'a'}",
        "malformed_returns_trimmed_text": "  not json or literal  ",
    }
    return {
        case_id: _capture(
            lambda value=value: adapter._parse_tool_message_content(value),
            fixture_root=fixture_root,
        )
        for case_id, value in values.items()
    }


def _loader_contract(adapter: Any, root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    missing = root / "missing"
    missing.mkdir()

    tolerant = root / "tolerant"
    _write(
        tolerant / "reuse_events.jsonl",
        "\n".join(
            (
                '{"scenario":"alpha","tool_name":"helper_b"}',
                "not-json",
                '{"scenario":"other","tool_name":"ignored"}',
                '{"scenario":"alpha","tool_name":"helper_a"}',
                '{"scenario":"alpha","tool_name":"helper_b"}',
                '{"scenario":"alpha","tool_name":7}',
                '{"scenario":"alpha"}',
            )
        )
        + "\n",
    )
    _write(
        tolerant / "scenario_tool_selection.jsonl",
        '{"scenario":"alpha","chosen":"helper_b"}\n'
        "bad-json\n"
        '["ignored"]\n'
        '{"scenario":"beta","chosen":null}\n',
    )

    non_object = root / "non_object"
    _write(non_object / "reuse_events.jsonl", '["not","an","event"]\n')
    directory_file = root / "directory_file"
    (directory_file / "reuse_events.jsonl").mkdir(parents=True)
    (directory_file / "scenario_tool_selection.jsonl").mkdir()

    loaders = {
        "reuse_missing": lambda: adapter._reuse_log_tools(missing, "alpha"),
        "selection_missing": lambda: adapter._selection_log_rows(missing),
        "reuse_tolerant_dedupe_order": lambda: adapter._reuse_log_tools(
            tolerant, "alpha"
        ),
        "reuse_other_scenario": lambda: adapter._reuse_log_tools(tolerant, "other"),
        "selection_tolerant_dict_only": lambda: adapter._selection_log_rows(tolerant),
        "reuse_valid_non_object": lambda: adapter._reuse_log_tools(
            non_object, "alpha"
        ),
        "reuse_read_failure": lambda: adapter._reuse_log_tools(
            directory_file, "alpha"
        ),
        "selection_read_failure": lambda: adapter._selection_log_rows(directory_file),
    }
    return {
        case_id: _capture(call, fixture_root=root)
        for case_id, call in loaders.items()
    }


def _conversation_contract(adapter: Any, root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    scenario = "fixture_case"
    empty_generated = root / "empty_generated"
    (empty_generated / "trajectories" / scenario / "conversation.json").mkdir(
        parents=True
    )

    malformed = root / "malformed"
    _write(
        malformed / "trajectories" / scenario / "conversation.json",
        '{"broken":',
    )
    scalar = root / "scalar"
    _write(
        scalar / "trajectories" / scenario / "conversation.json",
        '{"role":"assistant"}',
    )
    directory_file = root / "directory_file"
    (directory_file / "trajectories" / scenario / "conversation.json").mkdir(
        parents=True
    )

    rich = root / "rich"
    messages: list[Any] = [
        "non-mapping",
        {
            "role": "user",
            "content": "Use the helper",
            "scorer_secret": "drop",
            "tool_calls": [_tool_call("helper_a", call_id="user-call")],
        },
        {
            "role": "assistant",
            "content": None,
            "name": 9,
            "tool_calls": [
                None,
                {"function": []},
                _tool_call("helper_b", arguments='{"z":1}', call_id="b-1"),
                _tool_call("helper_a", arguments=7, call_id=5),
                _tool_call("helper_b", arguments="{}", call_id="b-2"),
                {"type": 7, "function": {"name": "helper_a"}},
                {"function": {"arguments": "{}"}},
            ],
        },
        {"role": "tool", "name": "helper_b", "content": "{'value': 1}"},
        {"role": "tool", "name": "helper_a", "content": "Error: failed once"},
        {"role": "tool", "name": "helper_b", "content": "[2, 3]"},
        {"role": "tool", "name": "helper_a", "content": "Traceback at end"},
        {
            "role": "tool",
            "name": "helper_result_only",
            "content": "ValueError result-only failure",
        },
        {"role": "tool", "name": "native_only", "content": "TypeError bad"},
        {"role": "assistant", "content": {"structured": "dropped"}, "name": "kept"},
        {"ignored": {"nested": "metadata"}},
    ]
    _write(
        rich / "trajectories" / scenario / "conversation.json",
        json.dumps(messages),
    )

    generated = ["helper_a", "helper_b", "helper_result_only", "unused"]
    seeded = ["seeded", "helper_a"]
    reconciled = adapter._reconcile_generated_tool_calls_from_conversation(
        rich,
        scenario,
        generated,
        seeded,
    )
    no_generated_called = ["original"]
    no_generated_result = adapter._reconcile_generated_tool_calls_from_conversation(
        directory_file,
        scenario,
        [],
        no_generated_called,
    )
    calls: dict[str, Callable[[], Any]] = {
        "attempts_missing": lambda: adapter._conversation_generated_tool_attempts(
            root / "missing", scenario, generated
        ),
        "attempts_empty_generated_fast_path": lambda: (
            adapter._conversation_generated_tool_attempts(
                empty_generated, scenario, []
            )
        ),
        "attempts_malformed_json": lambda: (
            adapter._conversation_generated_tool_attempts(malformed, scenario, generated)
        ),
        "attempts_non_list": lambda: adapter._conversation_generated_tool_attempts(
            scalar, scenario, generated
        ),
        "attempts_rich_order_and_failure": lambda: (
            adapter._conversation_generated_tool_attempts(rich, scenario, generated)
        ),
        "attempts_read_failure": lambda: adapter._conversation_generated_tool_attempts(
            directory_file, scenario, generated
        ),
        "visible_missing": lambda: adapter._visible_conversation_messages_for_observation(
            root / "missing", scenario
        ),
        "visible_malformed_json": lambda: (
            adapter._visible_conversation_messages_for_observation(
                malformed, scenario
            )
        ),
        "visible_non_list": lambda: (
            adapter._visible_conversation_messages_for_observation(scalar, scenario)
        ),
        "visible_rich_sanitized": lambda: (
            adapter._visible_conversation_messages_for_observation(rich, scenario)
        ),
        "visible_read_failure": lambda: (
            adapter._visible_conversation_messages_for_observation(
                directory_file, scenario
            )
        ),
        "results_empty_generated_fast_path": lambda: (
            adapter._conversation_generated_tool_results(
                empty_generated, scenario, []
            )
        ),
        "results_malformed_json": lambda: (
            adapter._conversation_generated_tool_results(malformed, scenario, generated)
        ),
        "results_non_list": lambda: adapter._conversation_generated_tool_results(
            scalar, scenario, generated
        ),
        "results_rich_parse_order": lambda: (
            adapter._conversation_generated_tool_results(rich, scenario, generated)
        ),
        "results_read_failure": lambda: (
            adapter._conversation_generated_tool_results(
                directory_file, scenario, generated
            )
        ),
    }
    return {
        "calls": {
            case_id: _capture(call, fixture_root=root)
            for case_id, call in calls.items()
        },
        "reconcile": {
            "seeded_before": seeded,
            "seeded_after": seeded,
            "result": reconciled,
            "result_is_seeded_object": reconciled is seeded,
            "empty_generated_result": no_generated_result,
            "empty_generated_preserves_identity": (
                no_generated_result is no_generated_called
            ),
        },
        "rich_messages_unchanged": messages
        == json.loads(
            (rich / "trajectories" / scenario / "conversation.json").read_text(
                encoding="utf-8"
            )
        ),
    }


def _trace_reconstruction_contract(adapter: Any, root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    paths["missing"] = root / "missing.json"
    paths["directory_read_failure"] = root / "directory"
    paths["directory_read_failure"].mkdir()
    fixtures: dict[str, Any] = {
        "malformed": "not-json",
        "non_mapping": [1, 2],
        "missing_dbs": {"other": {}},
        "dbs_non_mapping": {"_dbs": []},
        "rows_non_list": {"_dbs": {"SANDBOX": {}}},
        "rich": {
            "_dbs": {
                "SANDBOX": [
                    "non-row",
                    {
                        "sandbox_message_index": 9,
                        "openai_function_name": "scrambled_alpha",
                        "tool_trace": [
                            '{"tool_name":"helper","arguments":{"x":1},"result":{"ok":true}}',
                            '{"tool_name":"helper","arguments":{"x":2},"result":{"ok":true}}',
                            "{'tool_name': 'send_message', 'result': 'done'}",
                            "not-a-mapping",
                            '{"tool_name":7}',
                            '{"tool_name":""}',
                        ],
                    },
                    {
                        "sandbox_message_index": 2,
                        "openai_function_name": "scrambled_beta",
                        "tool_trace": {
                            "tool_name": "set_wifi_status",
                            "result": False,
                            "_sandbox_message_index": "overwritten",
                        },
                    },
                    {
                        "sandbox_message_index": 3,
                        "openai_function_name": "scrambled_gamma",
                        "tool_trace": [],
                        "content": "_response = add_reminder(content='ignored')",
                    },
                    {
                        "sandbox_message_index": 4,
                        "openai_function_name": "scrambled_delta",
                        "tool_trace": "malformed trace",
                        "content": "_response = remove_contact(person_id='ignored')",
                    },
                    {
                        "sandbox_message_index": 5,
                        "openai_function_name": "scrambled_epsilon",
                        "tool_trace": None,
                        "content": "prefix _response = modify_contact(person_id='p')",
                        "tool_call_exception": "ValueError: fixture",
                    },
                    {
                        "sandbox_message_index": 6,
                        "openai_function_name": "scrambled_zeta",
                        "content": "_response = search_contacts(query='not side effect')",
                    },
                    {
                        "sandbox_message_index": 7,
                        "openai_function_name": "scrambled_eta",
                        "content": 7,
                    },
                ]
            }
        },
    }
    for case_id, payload in fixtures.items():
        path = root / f"{case_id}.json"
        paths[case_id] = path
        _write(path, payload if isinstance(payload, str) else json.dumps(payload))
    return {
        case_id: _capture(
            lambda path=path: adapter._tool_trace_events_from_execution_context(path),
            fixture_root=root,
        )
        for case_id, path in paths.items()
    }


def _next_tool_contract(adapter: Any, fixture_root: Path) -> dict[str, Any]:
    assistant_messages: list[Any] = [
        "malformed",
        {"role": "system", "content": "skip"},
        {"role": "assistant", "tool_calls": []},
        {"role": "tool", "name": "helper", "content": "{}"},
        {"role": "assistant", "tool_calls": [None, {"function": []}]},
        _assistant_call("native_a", "native_a", ""),
        {"role": "user", "content": "barrier"},
        _assistant_call("native_b"),
    ]
    trace_events = [
        {"tool_name": "helper"},
        {"tool_name": None},
        {"other": "skip"},
        {"tool_name": "native_a"},
        {"tool_name": "native_b"},
        {"tool_name": "native_a"},
        {"tool_name": ""},
    ]
    calls: dict[str, Callable[[], Any]] = {
        "assistant_names_missing": lambda: adapter._assistant_tool_names({}),
        "assistant_names_tuple_rejected": lambda: adapter._assistant_tool_names(
            {"tool_calls": tuple([_tool_call("native_a")])}
        ),
        "assistant_names_malformed_and_duplicates": lambda: (
            adapter._assistant_tool_names(assistant_messages[4])
        ),
        "assistant_names_order_and_empty_string": lambda: (
            adapter._assistant_tool_names(assistant_messages[5])
        ),
        "next_assistant_stops_at_first_truthy_malformed_calls": lambda: (
            adapter._next_assistant_tool_names(assistant_messages, start_index=1)
        ),
        "next_assistant_after_malformed_finds_ordered_calls": lambda: (
            adapter._next_assistant_tool_names(assistant_messages, start_index=4)
        ),
        "next_assistant_user_barrier": lambda: adapter._next_assistant_tool_names(
            assistant_messages, start_index=5
        ),
        "next_assistant_after_barrier": lambda: adapter._next_assistant_tool_names(
            assistant_messages, start_index=6
        ),
        "next_trace_skips_non_string": lambda: adapter._next_trace_tool_names(
            trace_events, start_index=0
        ),
        "next_trace_returns_first_only": lambda: adapter._next_trace_tool_names(
            trace_events, start_index=2
        ),
        "next_trace_accepts_empty_string": lambda: adapter._next_trace_tool_names(
            trace_events, start_index=5
        ),
        "later_trace_deduplicates_all_strings": lambda: (
            adapter._later_trace_tool_names(trace_events, start_index=0)
        ),
        "later_trace_out_of_range": lambda: adapter._later_trace_tool_names(
            trace_events, start_index=20
        ),
    }
    return {
        case_id: _capture(call, fixture_root=fixture_root)
        for case_id, call in calls.items()
    }


def _conversation_for_followup(
    helper_name: str,
    output: Any,
    followers: tuple[str, ...],
    *,
    helper_present: bool = True,
) -> list[Any]:
    messages: list[Any] = []
    if helper_present:
        content = json.dumps(output) if isinstance(output, (dict, list)) else output
        messages.append({"role": "tool", "name": helper_name, "content": content})
    for index, name in enumerate(followers):
        messages.append(_assistant_call(name))
        messages.append(
            {
                "role": "tool",
                "name": name,
                "content": json.dumps({"step": index}),
            }
        )
    return messages


def _trace_for_followup(
    helper_name: str,
    output: Any,
    followers: tuple[str, ...],
    *,
    helper_present: bool = True,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if helper_present:
        events.append({"tool_name": helper_name, "result": copy.deepcopy(output)})
    events.extend(
        {"tool_name": name, "result": {"step": index}}
        for index, name in enumerate(followers)
    )
    return events


def _side_effect_contract(adapter: Any, fixture_root: Path) -> dict[str, Any]:
    helper = "non_native_helper"
    required = ("add_reminder", "send_message", "search_contacts")
    cases: dict[str, dict[str, Any]] = {
        "no_required_side_effect_names": {
            "required": ("search_contacts",),
            "output": {"should_call": True},
            "followers": (),
        },
        "helper_result_absent": {
            "output": {"should_call": True},
            "followers": (),
            "helper_present": False,
        },
        "scalar_output_has_no_contract": {"output": 123.5, "followers": ()},
        "mapping_without_declaration": {"output": {"value": 3}, "followers": ()},
        "preparatory_search_flag": {
            "output": {"should_call_tools": True, "should_call_search_contacts": True},
            "followers": (),
        },
        "preparatory_search_next_step": {
            "output": {"downstream_tool_kwargs": {}, "next_step": "SEARCH_MESSAGES first"},
            "followers": (),
        },
        "negative_search_without_action": {
            "output": {"should_call_search_contacts": True, "should_call_tools": False},
            "followers": ("search_contacts",),
        },
        "negative_search_but_immediate_action": {
            "output": {"should_call_search_contacts": True, "should_call_tools": False},
            "followers": ("send_message",),
        },
        "negative_search_explicit_without_action": {
            "output": {
                "should_call_search_contacts": True,
                "should_call_tools": False,
                "downstream_tool_name": "send_message",
            },
            "followers": ("search_contacts",),
        },
        "negative_search_explicit_but_immediate_action": {
            "output": {
                "should_call_search_contacts": True,
                "should_call_tools": False,
                "downstream_tool_name": "send_message",
            },
            "followers": ("send_message",),
        },
        "generic_negative_without_action": {
            "output": {"should_call": False},
            "followers": (),
        },
        "generic_negative_but_immediate_action": {
            "output": {"should_call_tool": False},
            "followers": ("add_reminder",),
        },
        "generic_negative_action_only_later": {
            "output": {"should_call_tools": False},
            "followers": ("search_contacts", "send_message"),
        },
        "contradictory_true_and_false_prefers_false": {
            "output": {"should_call": True, "should_call_tool": False},
            "followers": ("send_message",),
        },
        "truthy_non_boolean_is_neutral_declaration": {
            "output": {"should_call": 1},
            "followers": (),
        },
        "selection_bridge_with_late_action": {
            "output": {
                "should_call": False,
                "selected_record": {"id": "record-1"},
                "downstream_tool_name": "send_message",
                "final_answer_recommendation": "use_selected_record:record-1",
            },
            "followers": ("search_contacts", "send_message"),
        },
        "selection_bridge_missing_action": {
            "output": {
                "should_call": False,
                "selected_record": {"id": "record-1"},
                "downstream_tool_name": "send_message",
                "final_answer_recommendation": "use_selected_record:record-1",
            },
            "followers": ("search_contacts",),
        },
        "affirmative_immediate_action": {
            "output": {"should_call": True},
            "followers": ("send_message",),
        },
        "affirmative_late_action": {
            "output": {"should_call_tool": True},
            "followers": ("search_contacts", "send_message"),
        },
        "affirmative_missing_action": {
            "output": {"should_call_tools": True},
            "followers": ("search_contacts",),
        },
        "neutral_declaration_with_late_action": {
            "output": {"downstream_tool_kwargs": {"content": "hello"}},
            "followers": ("search_contacts", "send_message"),
        },
        "neutral_declaration_missing_action": {
            "output": {"downstream_tool_kwargs": {"content": "hello"}},
            "followers": (),
        },
        "explicit_name_narrows_to_send_but_add_follows": {
            "output": {"should_call": True, "downstream_tool_name": "send_message"},
            "followers": ("add_reminder",),
        },
        "explicit_name_narrows_to_send_and_send_follows": {
            "output": {"should_call": True, "tool_name": " send_message "},
            "followers": ("send_message",),
        },
        "action_sequence_narrows_required": {
            "output": {
                "should_call_tools": True,
                "action_sequence": [
                    "malformed",
                    {"tool_name": "add_reminder"},
                    {"tool_name": "not_required"},
                ],
            },
            "followers": ("add_reminder",),
        },
        "add_reminder_kwargs_imply_call": {
            "output": {"add_reminder_kwargs": {}},
            "followers": ("add_reminder",),
        },
        "explicit_non_side_effect_does_not_narrow": {
            "output": {"should_call": True, "downstream_tool_name": "search_contacts"},
            "followers": ("send_message",),
        },
    }

    cases_before = copy.deepcopy(cases)
    results: dict[str, Any] = {}
    for case_id, case in cases.items():
        case_required = tuple(case.get("required", required))
        output = case["output"]
        followers = tuple(case["followers"])
        helper_present = bool(case.get("helper_present", True))
        messages = _conversation_for_followup(
            helper, output, followers, helper_present=helper_present
        )
        events = _trace_for_followup(
            helper, output, followers, helper_present=helper_present
        )
        results[case_id] = {
            "required": list(case_required),
            "output": _wire(output),
            "followers": list(followers),
            "explicit_required": sorted(
                adapter._explicit_side_effect_calls_from_output(
                    output if isinstance(output, dict) else {},
                    required_side_effect_calls=case_required,
                )
            ),
            "preparatory": (
                adapter._output_is_preparatory_search_followup(output)
                if isinstance(output, dict)
                else None
            ),
            "conversation_failure": adapter._side_effect_followup_failures(
                messages,
                helper_name=helper,
                required_original_tool_calls=case_required,
            ),
            "trace_failure": (
                adapter._side_effect_followup_failures_from_trace_events(
                    events,
                    helper_name=helper,
                    required_side_effect_calls=tuple(
                        name
                        for name in case_required
                        if name.startswith(
                            ("add_", "modify_", "remove_", "send_", "set_")
                        )
                    ),
                )
                if any(
                    name.startswith(
                        ("add_", "modify_", "remove_", "send_", "set_")
                    )
                    for name in case_required
                )
                else None
            ),
            "combined_failure": adapter._side_effect_followup_failures(
                messages,
                helper_name=helper,
                required_original_tool_calls=case_required,
                actual_tool_trace_events=events,
            ),
        }

    native_success_message = {
        "role": "tool",
        "name": "different_helper",
        "content": json.dumps(
            {
                "status": "success",
                "native_action": "send_message",
                "native_result": {},
            }
        ),
    }
    native_trace = [{"tool_name": "send_message", "result": {}}]
    integration = {
        "other_helper_native_action_success_short_circuit": (
            adapter._side_effect_followup_failures(
                [native_success_message],
                helper_name=helper,
                required_original_tool_calls=("send_message",),
                actual_tool_trace_events=native_trace,
            )
        ),
        "false_native_result_still_short_circuits": (
            adapter._side_effect_followup_failures(
                [
                    {
                        **native_success_message,
                        "content": json.dumps(
                            {
                                "status": "success",
                                "native_action": "send_message",
                                "native_result": False,
                            }
                        ),
                    }
                ],
                helper_name=helper,
                required_original_tool_calls=("send_message",),
                actual_tool_trace_events=native_trace,
            )
        ),
        "cross_user_later_action_is_credited": adapter._side_effect_followup_failures(
            [
                {
                    "role": "tool",
                    "name": helper,
                    "content": json.dumps({"should_call": True}),
                },
                {"role": "user", "content": "new turn"},
                _assistant_call("send_message"),
            ],
            helper_name=helper,
            required_original_tool_calls=("send_message",),
        ),
        "native_action_missing_trace_falls_back": adapter._side_effect_followup_failures(
            [native_success_message],
            helper_name=helper,
            required_original_tool_calls=("send_message",),
            actual_tool_trace_events=[{"tool_name": "search_contacts", "result": {}}],
        ),
        "trace_failure_conversation_success_fallback": (
            adapter._side_effect_followup_failures(
                _conversation_for_followup(
                    helper, {"should_call": True}, ("send_message",)
                ),
                helper_name=helper,
                required_original_tool_calls=("send_message",),
                actual_tool_trace_events=_trace_for_followup(
                    helper, {"should_call": True}, ()
                ),
            )
        ),
        "trace_success_wins_before_conversation_failure": (
            adapter._side_effect_followup_failures(
                _conversation_for_followup(helper, {"should_call": True}, ()),
                helper_name=helper,
                required_original_tool_calls=("send_message",),
                actual_tool_trace_events=_trace_for_followup(
                    helper, {"should_call": True}, ("send_message",)
                ),
            )
        ),
    }
    side_effect_names = {
        str(value): adapter._side_effect_tool_name(value, {"send_message"})
        for value in (None, 7, "", " send_message ", "search_contacts", "SEND_MESSAGE")
    }
    return {
        "cases": results,
        "trace_conversation_integration": integration,
        "side_effect_name_normalization": side_effect_names,
        "inputs_are_not_mutated": cases == cases_before,
        "capture_contract": _capture(lambda: True, fixture_root=fixture_root),
    }


def _end_to_end_helper_contract(adapter: Any, online_birth: Any, root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    scenario = "helper_lifecycle_case"
    trajectory = root / "trajectories" / scenario
    helper_output = {
        "should_call": True,
        "downstream_tool_name": "send_message",
        "downstream_tool_kwargs": {"phone_number": "+15550100", "content": "Hi"},
    }
    messages = [
        {"role": "user", "content": "Use helper non native then send a message."},
        _assistant_call("helper_non_native"),
        {
            "role": "tool",
            "name": "helper_non_native",
            "content": json.dumps(helper_output),
        },
        _assistant_call("search_contacts"),
        {"role": "tool", "name": "search_contacts", "content": "[]"},
        _assistant_call("send_message"),
        {"role": "tool", "name": "send_message", "content": "success"},
        _assistant_call("failed_helper"),
        {"role": "tool", "name": "failed_helper", "content": "Error: fixture"},
    ]
    _write(trajectory / "conversation.json", json.dumps(messages))
    _write(
        trajectory / "execution_context.json",
        json.dumps(
            {
                "_dbs": {
                    "SANDBOX": [
                        {
                            "sandbox_message_index": 1,
                            "openai_function_name": "helper_non_native",
                            "tool_trace": {
                                "tool_name": "helper_non_native",
                                "result": helper_output,
                            },
                        },
                        {
                            "sandbox_message_index": 2,
                            "openai_function_name": "search_contacts",
                            "tool_trace": {"tool_name": "search_contacts", "result": []},
                        },
                        {
                            "sandbox_message_index": 3,
                            "openai_function_name": "send_message",
                            "tool_trace": {"tool_name": "send_message", "result": "success"},
                        },
                    ]
                }
            }
        ),
    )
    _write(
        root / "reuse_events.jsonl",
        '{"scenario":"helper_lifecycle_case","tool_name":"helper_non_native"}\n'
        '{"scenario":"helper_lifecycle_case","tool_name":"helper_non_native"}\n'
        '{"scenario":"helper_lifecycle_case","tool_name":"failed_helper"}\n',
    )
    generated = ["helper_non_native", "failed_helper", "unused_helper"]
    reuse = adapter._reuse_log_tools(root, scenario)
    attempted, failed = adapter._conversation_generated_tool_attempts(
        root, scenario, generated
    )
    results = adapter._conversation_generated_tool_results(root, scenario, generated)
    reconciled = adapter._reconcile_generated_tool_calls_from_conversation(
        root, scenario, generated, reuse
    )
    trace_events = adapter._tool_trace_events_from_execution_context(
        trajectory / "execution_context.json"
    )
    visible = adapter._visible_conversation_messages_for_observation(root, scenario)

    class _UnusedStore:
        root = Path("fixture-registry")

    class _UnusedGenerator:
        pass

    controller = online_birth.OnlineBirthController(
        store=_UnusedStore(),
        generator=_UnusedGenerator(),
        output_dir=root,
        recurrence_threshold=2,
        failure_memory_path=None,
    )
    classifier = importlib.import_module("sage_ts.adequacy.inadequacy_classifier")
    observation = classifier.CapabilityObservation(
        scenario_name=scenario,
        canonical_key="replay:non_native_helper_followup",
        observation="Synthetic visible helper follow-up shortfall.",
        allowed_families=(),
        validation_examples=(),
        generation_allowed=False,
        reason="trajectory_runtime_replay",
        inadequacy_signals=("helper_non_native",),
        failed_tool_calls=("failed_helper",),
        evidence_source="heuristic",
    )
    observe_result = controller.observe(observation)
    malformed_scenario = "malformed_lifecycle"
    _write(
        root / "trajectories" / malformed_scenario / "conversation.json",
        "not-json",
    )
    malformed_observation = classifier.CapabilityObservation(
        scenario_name=malformed_scenario,
        canonical_key="replay:malformed_trajectory",
        observation="Malformed synthetic trace.",
        allowed_families=(),
        validation_examples=(),
        generation_allowed=False,
        reason="trajectory_runtime_replay",
        inadequacy_signals=("missing",),
        evidence_source="heuristic",
    )
    malformed_verified = controller._check_heuristic_signal(malformed_observation)
    nested_only_scenario = "nested_tool_call_only"
    _write(
        root / "trajectories" / nested_only_scenario / "conversation.json",
        json.dumps([_assistant_call("nested_signal_only")]),
    )
    nested_only_observation = classifier.CapabilityObservation(
        scenario_name=nested_only_scenario,
        canonical_key="replay:nested_tool_call_only",
        observation="Nested tool call is not transcript text.",
        allowed_families=(),
        validation_examples=(),
        generation_allowed=False,
        reason="trajectory_runtime_replay",
        inadequacy_signals=("nested_signal_only",),
        evidence_source="heuristic",
    )
    empty_signal_observation = classifier.CapabilityObservation(
        scenario_name=scenario,
        canonical_key="replay:empty_signal",
        observation="Empty signal behavior.",
        allowed_families=(),
        validation_examples=(),
        generation_allowed=False,
        reason="trajectory_runtime_replay",
        inadequacy_signals=("",),
        evidence_source="heuristic",
    )
    return {
        "reuse_order_and_dedup": reuse,
        "attempted": attempted,
        "failed": failed,
        "parsed_results": results,
        "reconciled": reconciled,
        "successful_called_after_failed_removed": [
            name for name in reconciled if name not in set(failed)
        ],
        "visible_messages": visible,
        "trace_events": trace_events,
        "side_effect_followup_failure": adapter._side_effect_followup_failures(
            messages,
            helper_name="helper_non_native",
            required_original_tool_calls=("send_message",),
            actual_tool_trace_events=trace_events,
        ),
        "heuristic_signal_verified": controller._check_heuristic_signal(observation),
        "malformed_heuristic_signal_verified": malformed_verified,
        "nested_tool_call_signal_is_not_visible_text": (
            controller._check_heuristic_signal(nested_only_observation)
        ),
        "empty_signal_matches_nonempty_transcript": (
            controller._check_heuristic_signal(empty_signal_observation)
        ),
        "observe_generation_disabled_result": observe_result,
        "case_insensitive_first_spelling_dedup": online_birth._dedupe_nonempty(
            (" Alpha ", "", "alpha", None, "Beta", " BETA ")
        ),
        "online_birth_feedback_precedence": {
            "paper_zero_over_audited": adapter._online_birth_feedback_result(
                {
                    "online_feedback_outcome_similarity": 0.0,
                    "outcome_similarity": 1.0,
                }
            ),
            "audited_fallback": adapter._online_birth_feedback_result(
                {"outcome_similarity": 0.5}
            ),
            "unavailable": adapter._online_birth_feedback_result({}),
        },
        "observation_counts": dict(controller.counts),
        "observation_scenarios": {
            key: sorted(value) for key, value in controller.scenarios_by_key.items()
        },
        "observation_rows": _read_jsonl(root / "capability_observations.jsonl"),
        "run_event_rows": _read_jsonl(root / "sage_run_events.jsonl"),
    }


def run_probe(
    root: Path,
    *,
    exact: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    """Return the deterministic trajectory/runtime characterization."""

    del root
    adapter = importlib.import_module("sage_ts.adapters.sage_run_adapter")
    online_birth = importlib.import_module("sage_ts.orchestration.online_birth")
    with tempfile.TemporaryDirectory(prefix="sage-trajectory-runtime-") as temporary:
        fixture_root = Path(temporary)
        payload = {
            "tool_content_parsing": _content_parsing_contract(
                adapter, fixture_root
            ),
            "jsonl_loaders": _loader_contract(adapter, fixture_root / "loaders"),
            "conversation_loaders": _conversation_contract(
                adapter, fixture_root / "conversation"
            ),
            "execution_trace_reconstruction": _trace_reconstruction_contract(
                adapter, fixture_root / "trace"
            ),
            "next_tool_semantics": _next_tool_contract(adapter, fixture_root),
            "side_effect_followup_semantics": _side_effect_contract(
                adapter, fixture_root
            ),
            "non_native_helper_lifecycle_path": _end_to_end_helper_contract(
                adapter, online_birth, fixture_root / "lifecycle"
            ),
        }
    return {
        "contract_schema_version": 1,
        "contract_sections": list(payload),
        "payload": exact(payload),
    }
