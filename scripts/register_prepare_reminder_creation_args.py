"""Register the claim-safe prepare_reminder_creation_args helper.

Usage:
    python scripts/register_prepare_reminder_creation_args.py
    python scripts/register_prepare_reminder_creation_args.py --registry-dir outputs/tmp_registry
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from sage_ts.generation.tool_spec import (  # noqa: E402
    GeneratedTool,
    StructuredInadequacyEvidence,
    ToolFamily,
    ToolInput,
    ToolSpec,
)
from sage_ts.registry.manifest import RegistryEntry  # noqa: E402
from sage_ts.registry.store import RegistryStore  # noqa: E402
from sage_ts.validation.sandbox_validator import (  # noqa: E402
    ToolExample,
    validate_generated_tool,
)

TOOL_CODE = """\
def prepare_reminder_creation_args(
    content: str,
    resolved_reminder_timestamp: float,
    current_timestamp: float,
    day_offset: int,
    hour: int,
    minute: int,
    local_utc_offset_hours: float,
    time_fields_complete: bool,
    location_required: bool,
    location_available: bool,
    latitude: float,
    longitude: float,
    location_lookup_failed: bool,
) -> dict:
    timestamp_source = "none"
    if float(resolved_reminder_timestamp) > 0:
        reminder_timestamp = float(resolved_reminder_timestamp)
        timestamp_source = "resolved"
    else:
        if not time_fields_complete:
            return {
                "add_reminder_kwargs": {},
                "should_call_add_reminder": False,
                "location_status": "omitted_optional",
                "abstain_reason": "missing_time_info",
                "timestamp_source": timestamp_source,
            }
        if int(hour) < 0 or int(hour) > 23 or int(minute) < 0 or int(minute) > 59:
            return {
                "add_reminder_kwargs": {},
                "should_call_add_reminder": False,
                "location_status": "omitted_optional",
                "abstain_reason": "malformed_time_info",
                "timestamp_source": timestamp_source,
            }
        offset_seconds = float(local_utc_offset_hours) * 3600.0
        local_seconds = float(current_timestamp) + offset_seconds
        local_midnight = int(local_seconds // 86400.0) * 86400.0
        reminder_timestamp = (
            local_midnight
            + int(day_offset) * 86400.0
            - offset_seconds
            + int(hour) * 3600.0
            + int(minute) * 60.0
        )
        timestamp_source = "relative_fields"
    coords_available = bool(location_available) and not (
        float(latitude) == 0.0 or float(longitude) == 0.0
    )
    if coords_available:
        latitude_out = float(latitude)
        longitude_out = float(longitude)
        location_status = "provided"
    elif bool(location_required):
        return {
            "add_reminder_kwargs": {},
            "should_call_add_reminder": False,
            "location_status": "required_missing",
            "abstain_reason": "required_location_unresolved",
            "timestamp_source": timestamp_source,
        }
    else:
        latitude_out = None
        longitude_out = None
        location_status = "omitted_optional"
    return {
        "add_reminder_kwargs": {
            "content": content,
            "reminder_timestamp": reminder_timestamp,
            "latitude": latitude_out,
            "longitude": longitude_out,
        },
        "should_call_add_reminder": True,
        "location_status": location_status,
        "abstain_reason": "",
        "timestamp_source": timestamp_source,
    }
"""

SPEC = ToolSpec(
    tool_name="prepare_reminder_creation_args",
    family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
    description=(
        "Prepare add_reminder kwargs for reminder creation while preserving the "
        "original benchmark side-effect call."
    ),
    inputs=(
        ToolInput("content", "str", "Reminder content."),
        ToolInput(
            "resolved_reminder_timestamp",
            "float",
            "Use this timestamp directly when it is greater than zero.",
        ),
        ToolInput("current_timestamp", "float", "Current Unix timestamp."),
        ToolInput("day_offset", "int", "Local-day offset."),
        ToolInput("hour", "int", "Target local hour."),
        ToolInput("minute", "int", "Target local minute."),
        ToolInput("local_utc_offset_hours", "float", "Local UTC offset."),
        ToolInput(
            "time_fields_complete",
            "bool",
            "Whether the relative time fields are present and safe to use.",
        ),
        ToolInput(
            "location_required",
            "bool",
            "Whether the user explicitly requires a location on the reminder.",
        ),
        ToolInput("location_available", "bool", "Whether coordinates are available."),
        ToolInput("latitude", "float", "Latitude when available."),
        ToolInput("longitude", "float", "Longitude when available."),
        ToolInput(
            "location_lookup_failed",
            "bool",
            "Whether a location lookup was already attempted and failed.",
        ),
    ),
    output_annotation="dict",
    output_schema={
        "type": "object",
        "properties": {
            "add_reminder_kwargs": {"type": "object"},
            "should_call_add_reminder": {"type": "boolean"},
            "location_status": {"type": "string"},
            "abstain_reason": {"type": "string"},
            "timestamp_source": {"type": "string"},
        },
    },
    positive_triggers=(
        "add_reminder",
        "optional_info_treated_as_required",
        "relative_time_needs_typed_kwargs",
    ),
    negative_triggers=(
        "modify_reminder",
        "search_reminder",
        "delete_reminder",
        "insufficient_information",
    ),
    preserves_side_effect_tools=("add_reminder",),
    required_original_tool_calls=("add_reminder",),
    abstain_behavior=(
        "Return should_call_add_reminder=False when time information is missing or "
        "malformed, or when location is explicitly required but unresolved."
    ),
    generalization_rationale=(
        "Reminder creation tasks need deterministic argument preparation while "
        "still calling the original add_reminder ToolSandbox side-effect tool for "
        "both no-location and optional-location cases."
    ),
    inadequacy_evidence=StructuredInadequacyEvidence(
        summary=(
            "Reminder creation tasks fail when the agent has enough visible "
            "information to create the reminder but still wastes turns on optional "
            "location handling or timestamp argument preparation."
        ),
        signals=(
            "optional_info_treated_as_required",
            "visible_raw_data_lacking_deterministic_transform",
        ),
        visible_data_gaps=(
            "relative or resolved reminder time and optional location must be "
            "converted into add_reminder kwargs",
        ),
    ),
)

TOOL = GeneratedTool(spec=SPEC, code=TOOL_CODE)

EXAMPLES = (
    ToolExample(
        {
            "content": "Buy tickets",
            "resolved_reminder_timestamp": 0.0,
            "current_timestamp": 0.0,
            "day_offset": 1,
            "hour": 17,
            "minute": 0,
            "local_utc_offset_hours": 0.0,
            "time_fields_complete": True,
            "location_required": False,
            "location_available": False,
            "latitude": 0.0,
            "longitude": 0.0,
            "location_lookup_failed": True,
        },
        {
            "add_reminder_kwargs": {
                "content": "Buy tickets",
                "reminder_timestamp": 147600.0,
                "latitude": None,
                "longitude": None,
            },
            "should_call_add_reminder": True,
            "location_status": "omitted_optional",
            "abstain_reason": "",
            "timestamp_source": "relative_fields",
        },
    ),
    ToolExample(
        {
            "content": "Team meeting",
            "resolved_reminder_timestamp": 1777500000.0,
            "current_timestamp": 1777428906.0,
            "day_offset": 0,
            "hour": 0,
            "minute": 0,
            "local_utc_offset_hours": 0.0,
            "time_fields_complete": False,
            "location_required": False,
            "location_available": False,
            "latitude": 0.0,
            "longitude": 0.0,
            "location_lookup_failed": False,
        },
        {
            "add_reminder_kwargs": {
                "content": "Team meeting",
                "reminder_timestamp": 1777500000.0,
                "latitude": None,
                "longitude": None,
            },
            "should_call_add_reminder": True,
            "location_status": "omitted_optional",
            "abstain_reason": "",
            "timestamp_source": "resolved",
        },
        held_out=True,
    ),
    ToolExample(
        {
            "content": "Arrive early",
            "resolved_reminder_timestamp": 0.0,
            "current_timestamp": 1777428906.194959,
            "day_offset": 1,
            "hour": 17,
            "minute": 0,
            "local_utc_offset_hours": -4.0,
            "time_fields_complete": True,
            "location_required": False,
            "location_available": True,
            "latitude": 37.3237926356735,
            "longitude": -122.03961770355414,
            "location_lookup_failed": False,
        },
        {
            "add_reminder_kwargs": {
                "content": "Arrive early",
                "reminder_timestamp": 1777496400.0,
                "latitude": 37.3237926356735,
                "longitude": -122.03961770355414,
            },
            "should_call_add_reminder": True,
            "location_status": "provided",
            "abstain_reason": "",
            "timestamp_source": "relative_fields",
        },
    ),
    ToolExample(
        {
            "content": "Whole Foods while low battery",
            "resolved_reminder_timestamp": 0.0,
            "current_timestamp": 864000.0,
            "day_offset": 0,
            "hour": 9,
            "minute": 30,
            "local_utc_offset_hours": 0.0,
            "time_fields_complete": True,
            "location_required": False,
            "location_available": False,
            "latitude": 0.0,
            "longitude": 0.0,
            "location_lookup_failed": True,
        },
        {
            "add_reminder_kwargs": {
                "content": "Whole Foods while low battery",
                "reminder_timestamp": 898200.0,
                "latitude": None,
                "longitude": None,
            },
            "should_call_add_reminder": True,
            "location_status": "omitted_optional",
            "abstain_reason": "",
            "timestamp_source": "relative_fields",
        },
    ),
    ToolExample(
        {
            "content": "Meet at park",
            "resolved_reminder_timestamp": 0.0,
            "current_timestamp": 0.0,
            "day_offset": 1,
            "hour": 14,
            "minute": 0,
            "local_utc_offset_hours": 0.0,
            "time_fields_complete": True,
            "location_required": True,
            "location_available": False,
            "latitude": 0.0,
            "longitude": 0.0,
            "location_lookup_failed": True,
        },
        {
            "add_reminder_kwargs": {},
            "should_call_add_reminder": False,
            "location_status": "required_missing",
            "abstain_reason": "required_location_unresolved",
            "timestamp_source": "relative_fields",
        },
        negative_applicability=True,
    ),
    ToolExample(
        {
            "content": "Dentist",
            "resolved_reminder_timestamp": 0.0,
            "current_timestamp": 0.0,
            "day_offset": 0,
            "hour": 0,
            "minute": 0,
            "local_utc_offset_hours": 0.0,
            "time_fields_complete": False,
            "location_required": False,
            "location_available": False,
            "latitude": 0.0,
            "longitude": 0.0,
            "location_lookup_failed": False,
        },
        {
            "add_reminder_kwargs": {},
            "should_call_add_reminder": False,
            "location_status": "omitted_optional",
            "abstain_reason": "missing_time_info",
            "timestamp_source": "none",
        },
        negative_applicability=True,
    ),
    ToolExample(
        {
            "content": "Bad time",
            "resolved_reminder_timestamp": 0.0,
            "current_timestamp": 0.0,
            "day_offset": 0,
            "hour": 25,
            "minute": 61,
            "local_utc_offset_hours": 0.0,
            "time_fields_complete": True,
            "location_required": False,
            "location_available": False,
            "latitude": 0.0,
            "longitude": 0.0,
            "location_lookup_failed": False,
        },
        {
            "add_reminder_kwargs": {},
            "should_call_add_reminder": False,
            "location_status": "omitted_optional",
            "abstain_reason": "malformed_time_info",
            "timestamp_source": "none",
        },
        negative_applicability=True,
    ),
    ToolExample(
        {
            "content": "Pick up package",
            "resolved_reminder_timestamp": 0.0,
            "current_timestamp": 0.0,
            "day_offset": 0,
            "hour": 12,
            "minute": 0,
            "local_utc_offset_hours": 0.0,
            "time_fields_complete": True,
            "location_required": False,
            "location_available": True,
            "latitude": 0.0,
            "longitude": -122.0,
            "location_lookup_failed": False,
        },
        {
            "add_reminder_kwargs": {
                "content": "Pick up package",
                "reminder_timestamp": 43200.0,
                "latitude": None,
                "longitude": None,
            },
            "should_call_add_reminder": True,
            "location_status": "omitted_optional",
            "abstain_reason": "",
            "timestamp_source": "relative_fields",
        },
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--registry-dir",
        type=Path,
        default=Path("outputs/prepare_reminder_creation_args_registry"),
    )
    args = parser.parse_args()

    result = validate_generated_tool(TOOL, EXAMPLES)
    print(f"accepted={result.accepted}")
    print(f"source_example_count={result.source_example_count}")
    print(f"held_out_check_count={result.held_out_check_count}")
    print(f"negative_applicability_count={result.negative_applicability_count}")
    print(f"runtime_smoke_passed={result.runtime_smoke_passed}")
    if result.errors:
        for error in result.errors:
            print(error)
    if not result.accepted:
        return 1

    store = RegistryStore(args.registry_dir)
    store.save_entries({})
    store.put(
        RegistryEntry.accepted(
            tool=TOOL,
            validation=result,
            birth_scenario="add_reminder_content_and_week_delta_and_time_and_location",
        )
    )
    print(args.registry_dir / "registry_manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
