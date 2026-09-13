"""Actor-visible ToolSandbox inventory for lifecycle evidence and routing.

ToolSandbox can replace a native function name with an opaque agent-facing name.
Lifecycle decisions must therefore use the same names and schemas shown to the
actor, not the execution-facing ``function.__name__`` values retained by the
sandbox.  This module is the single boundary for that public inventory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from tool_sandbox.common.execution_context import (
    ExecutionContext,
    RoleType,
    new_context,
)
from tool_sandbox.common.tool_conversion import convert_to_openai_tools


@dataclass(frozen=True)
class ActorVisibleToolInventory:
    """Names/schemas visible to the actor plus schema-derived capability tags."""

    names: tuple[str, ...]
    schema_json: tuple[str, ...]
    # These tags are inferred only from the public schema text and parameter
    # names.  They are used for deterministic compatibility checks and are not
    # included in lifecycle prompts or routing context.
    semantic_capabilities: tuple[str, ...]


def _function_payload(schema: Mapping[str, Any]) -> Mapping[str, Any]:
    function = schema.get("function", {})
    return function if isinstance(function, Mapping) else {}


def _parameter_names(function: Mapping[str, Any]) -> set[str]:
    parameters = function.get("parameters", {})
    if not isinstance(parameters, Mapping):
        return set()
    properties = parameters.get("properties", {})
    if not isinstance(properties, Mapping):
        return set()
    return {str(name) for name in properties}


def _schema_derived_capabilities(
    schemas: tuple[Mapping[str, Any], ...],
) -> tuple[str, ...]:
    """Infer native capability tags without inspecting execution-facing names.

    The rules intentionally use only the same descriptions and argument names
    sent to the actor.  A missed match hides a generated helper conservatively;
    it can never reveal an otherwise hidden native tool.
    """

    capabilities: set[str] = set()
    for schema in schemas:
        function = _function_payload(schema)
        actor_name = str(function.get("name") or "").strip()
        if actor_name:
            # On ordinary scenarios this is already the execution name.  On a
            # name-scrambled scenario it remains the opaque, actor-visible alias.
            capabilities.add(actor_name)

        description = " ".join(str(function.get("description") or "").split()).lower()
        parameters = _parameter_names(function)

        contact_record_schema = "person_id" in parameters and bool(
            parameters & {"name", "phone_number", "relationship", "is_self"}
        )
        contact_record_schema = contact_record_schema or (
            parameters == {"person_id"}
            and any(token in description for token in ("remove", "delete"))
        )
        contact_record_schema = contact_record_schema or (
            {"name", "phone_number"} <= parameters
            and any(token in description for token in ("add", "create"))
        )
        if "contact" in description and contact_record_schema:
            if "search" in description or "find" in description:
                capabilities.add("search_contacts")
            if "add" in description or "create" in description:
                capabilities.add("add_contact")
            if "modify" in description or "update" in description:
                capabilities.add("modify_contact")
            if "remove" in description or "delete" in description:
                capabilities.add("remove_contact")

        if "message" in description:
            if "search" in description or "find" in description:
                capabilities.add("search_messages")
            if {"phone_number", "content"} <= parameters and (
                "send" in description or "recipient" in description
            ):
                capabilities.add("send_message_with_phone_number")

        if "reminder" in description:
            if "search" in description or "find" in description:
                capabilities.add("search_reminder")
            if "add" in description or "create" in description:
                capabilities.add("add_reminder")
            if "modify" in description or "update" in description:
                capabilities.add("modify_reminder")
            if "remove" in description or "delete" in description:
                capabilities.add("remove_reminder")

        if (
            "current posix timestamp" in description
            or "current timestamp" in description
        ):
            capabilities.add("get_current_timestamp")
        if "holiday" in description and (
            "search" in description or "find" in description
        ):
            capabilities.add("search_holiday")
        if "convert" in description and "currency" in description:
            capabilities.add("convert_currency")
        if "stock" in description and (
            "search" in description or "query" in description
        ):
            capabilities.add("search_stock")
        if {"latitude", "longitude"} <= parameters:
            if "weather" in description:
                capabilities.add("search_weather_around_lat_lon")
            elif "location" in parameters or "location around" in description:
                capabilities.add("search_location_around_lat_lon")
            elif "address" in description:
                capabilities.add("search_lat_lon")
        if {"latitude_0", "longitude_0", "latitude_1", "longitude_1"} <= parameters:
            if "distance" in description:
                capabilities.add("calculate_lat_lon_distance")

        if not parameters and "current location" in description:
            capabilities.add("get_current_location")
        if {
            "year",
            "month",
            "day",
            "hour",
            "minute",
            "second",
        } <= parameters and "posix timestamp" in description:
            capabilities.add("datetime_info_to_timestamp")
        if parameters == {"timestamp"} and "date time information" in description:
            capabilities.add("timestamp_to_datetime_info")
        if parameters == {"seconds"} and all(
            token in description for token in ("hours", "minutes", "seconds")
        ):
            capabilities.add("seconds_to_hours_minutes_seconds")
        if "timestamp" in parameters and "provided deltas" in description:
            capabilities.add("shift_timestamp")
        if {"timestamp_0", "timestamp_1"} <= parameters and "difference" in description:
            capabilities.add("timestamp_diff")
        if {"amount", "from_unit", "to_unit"} <= parameters:
            capabilities.add("unit_conversion")

        status_subjects = {
            "wifi": "wifi",
            "cellular service": "cellular_service",
            "location service": "location_service",
            "low battery mode": "low_battery_mode",
        }
        for phrase, suffix in status_subjects.items():
            if phrase not in description:
                continue
            if "status" in description and not parameters:
                capabilities.add(f"get_{suffix}_status")
            if {"on"} <= parameters and any(
                token in description for token in ("enable", "disable", "set")
            ):
                capabilities.add(f"set_{suffix}_status")

        if "conversation" in description and any(
            token in description for token in ("end", "finish", "stop")
        ):
            capabilities.add("end_conversation")

    return tuple(sorted(capabilities))


def actor_visible_tool_inventory(
    context: ExecutionContext,
) -> ActorVisibleToolInventory:
    """Return exactly the tool inventory exposed by the ToolSandbox agent role."""

    # Match BaseRole.get_available_tools for RoleType.AGENT exactly.  The raw
    # execution context also includes tools reserved for the user role (notably
    # end_conversation), which are not part of the actor's observable inventory.
    available = {
        name: tool
        for name, tool in context.get_available_tools(scrambling_allowed=True).items()
        if RoleType.AGENT in getattr(tool, "visible_to", (RoleType.AGENT,))
    }
    # Conversion consults the current context for description/argument
    # augmentations, so bind the scenario context just as the actor role does.
    with new_context(context):
        raw_schemas = tuple(convert_to_openai_tools(available))
    schemas = tuple(schema for schema in raw_schemas if isinstance(schema, Mapping))
    schema_json = tuple(
        json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for schema in schemas
    )
    return ActorVisibleToolInventory(
        names=tuple(sorted(str(name) for name in available)),
        schema_json=schema_json,
        semantic_capabilities=_schema_derived_capabilities(schemas),
    )
