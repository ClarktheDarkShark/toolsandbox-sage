"""Opt-in native-action delegation for model-authored SAGE tools.

Eligible generated composite tools may call one approved native ToolSandbox
action. The native tool remains the state-changing implementation and its trace
is preserved. All other generated tools remain side-effect-free.
"""

from __future__ import annotations

from typing import Any, Callable

# Native side-effect tool names exposed (by bare name) to complete tools.
COMPLETE_TOOLS_NATIVE_NAMES: tuple[str, ...] = (
    "add_contact",
    "modify_contact",
    "remove_contact",
    "send_message_with_phone_number",
    "add_reminder",
    "modify_reminder",
    "remove_reminder",
    "set_cellular_service_status",
    "set_location_service_status",
    "set_low_battery_mode_status",
    "set_wifi_status",
)


def visit_ranked_record_structural_negative_inputs(
    inputs: dict[str, Any],
    emit: Callable[[tuple[str, dict[str, Any]]], None],
) -> bool:
    """Build malformed-field and tied-rank inputs for one ranked record set."""

    records = inputs.get("records")
    if (
        not isinstance(records, list)
        or not records
        or not all(isinstance(record, dict) for record in records)
    ):
        return False
    timestamp_key = str(inputs.get("timestamp_key") or "").strip()
    if not timestamp_key:
        common_keys = set(records[0])
        for record in records[1:]:
            common_keys.intersection_update(record)
        timestamp_key = next(
            (
                key
                for key in sorted(common_keys)
                if key.endswith("_timestamp")
                and all(isinstance(record.get(key), (int, float)) for record in records)
            ),
            "",
        )
    if not timestamp_key or not any(timestamp_key in record for record in records):
        return False

    malformed_records = [dict(record) for record in records]
    malformed_records[0].pop(timestamp_key, None)
    malformed_inputs = dict(inputs)
    malformed_inputs["records"] = malformed_records
    emit(("missing_rank_field", malformed_inputs))

    numeric_records = [
        record
        for record in records
        if isinstance(record.get(timestamp_key), (int, float))
    ]
    if numeric_records:
        mode = str(inputs.get("selection_mode") or "latest").lower()
        selected = (
            min(numeric_records, key=lambda record: record[timestamp_key])
            if mode in {"oldest", "first", "oldest_by_time", "earliest"}
            else max(numeric_records, key=lambda record: record[timestamp_key])
        )
        tied_inputs = dict(inputs)
        tied_inputs["records"] = [
            *[dict(record) for record in records],
            dict(selected),
        ]
        emit(("tied_rank", tied_inputs))
    return True


def native_action_names_for_tool(tool: Any) -> tuple[str, ...]:
    """Return the native actions explicitly declared by a generated tool."""

    spec = getattr(tool, "spec", None)
    if spec is None:
        return ()
    declared = (
        *getattr(spec, "required_original_tool_calls", ()),
        *getattr(spec, "preserves_side_effect_tools", ()),
    )
    allowed = set(COMPLETE_TOOLS_NATIVE_NAMES)
    return tuple(dict.fromkeys(str(name) for name in declared if str(name) in allowed))


def native_action_spec_enabled(spec: Any) -> bool:
    """Return whether a generated-tool specification permits native delegation."""

    eligible_families = {
        "composite_workflow_helper",
        "search_filter_ranking_helper",
    }
    if (
        not bool(getattr(spec, "native_action_delegation", False))
        or str(getattr(spec, "family", "")) not in eligible_families
    ):
        return False
    declared = (
        *getattr(spec, "required_original_tool_calls", ()),
        *getattr(spec, "preserves_side_effect_tools", ()),
    )
    return bool(set(map(str, declared)) & set(COMPLETE_TOOLS_NATIVE_NAMES))


def native_action_tool_enabled(tool: Any) -> bool:
    """Return whether this tool may delegate one action to a native tool."""

    spec = getattr(tool, "spec", None)
    return native_action_spec_enabled(spec) and bool(native_action_names_for_tool(tool))


def native_side_effect_tools() -> dict[str, Callable[..., Any]]:
    """Return the native ToolSandbox side-effect tools keyed by function name.

    Imports happen inside the function to avoid import cycles between the
    generation/validation layers and the tool_sandbox package.
    """

    from tool_sandbox.tools.contact import (
        add_contact,
        modify_contact,
        remove_contact,
    )
    from tool_sandbox.tools.messaging import send_message_with_phone_number
    from tool_sandbox.tools.reminder import (
        add_reminder,
        modify_reminder,
        remove_reminder,
    )
    from tool_sandbox.tools.setting import (
        set_cellular_service_status,
        set_location_service_status,
        set_low_battery_mode_status,
        set_wifi_status,
    )

    tools: tuple[Callable[..., Any], ...] = (
        add_contact,
        modify_contact,
        remove_contact,
        send_message_with_phone_number,
        add_reminder,
        modify_reminder,
        remove_reminder,
        set_cellular_service_status,
        set_location_service_status,
        set_low_battery_mode_status,
        set_wifi_status,
    )
    return {fn.__name__: fn for fn in tools}


COMPLETE_TOOLS_PROMPT_CONSTRAINT = (
    "This is an eligible native-action composite. The function MUST complete "
    "one final state-changing action by calling exactly one approved native "
    "ToolSandbox tool BY NAME, without importing it: "
    + ", ".join(COMPLETE_TOOLS_NATIVE_NAMES)
    + ". The validation examples describe the exact native tool and arguments "
    "that must be invoked when enough visible information exists. On negative, "
    "ambiguous, or insufficient-information examples, call no native action and "
    "return a dict explaining the abstention. The generated function delegates "
    "to the native tool; it does not replace its implementation or trace. Return "
    "a dict with status='success', a nonempty confirmation, an empty "
    "abstain_reason, the native_action name, and the native_result after a "
    "successful call. When abstaining, return status='abstain', an empty "
    "confirmation and native_action, a nonempty abstain_reason, and "
    "native_result=None. Every return path must contain all five fields. Do not "
    "return an empty dict. Do not merely prepare kwargs or ask the actor to repeat "
    "the same native action. On each positive branch, the generated Python must "
    "literally invoke the approved function once with keyword arguments, assign "
    "that call's return value to native_result, and only then return success. "
    "Writing native_action='tool_name' or native_result=arguments without the "
    "function call is invalid. Keep all parsing and normalization inside the one "
    "required generated function; do not reference auxiliary functions, globals, "
    "or names that are not function inputs, safe builtins, or approved native "
    "actions. Do not call a native action inside a loop. "
    "The success confirmation must be a concise, subject-first completed-state "
    "sentence that identifies the visible target and operation in ordinary user "
    "language; do not emit a vague success message or expose an internal id. "
    "Obey all safety rules: no imports, no "
    "try/except, no raise statements, no classes, no lambdas, no while loops, "
    "no file/network/subprocess access, no global state, and no mutation of "
    "your input arguments. Only call the native tool names listed above; do "
    "not call any other side-effect tool."
)
