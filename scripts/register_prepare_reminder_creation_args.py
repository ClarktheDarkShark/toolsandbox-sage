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
    location_refinement_in_progress: bool,
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
                "abstain_reason": "missing_time_info",
                "location_status": "omitted",
                "timestamp_source": timestamp_source,
            }
        if int(hour) < 0 or int(hour) > 23 or int(minute) < 0 or int(minute) > 59:
            return {
                "add_reminder_kwargs": {},
                "should_call_add_reminder": False,
                "abstain_reason": "malformed_time_info",
                "location_status": "omitted",
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
    if bool(location_refinement_in_progress):
        return {
            "add_reminder_kwargs": {},
            "should_call_add_reminder": False,
            "should_retry_location_lookup": False,
            "location_status": "refining",
            "abstain_reason": "location_still_being_refined",
            "timestamp_source": timestamp_source,
        }
    lat_zero = float(latitude) == 0.0
    lon_zero = float(longitude) == 0.0
    partial_coords = bool(location_available) and (lat_zero != lon_zero)
    if partial_coords:
        return {
            "add_reminder_kwargs": {},
            "should_call_add_reminder": False,
            "should_retry_location_lookup": False,
            "location_status": "partial",
            "abstain_reason": "partial_location_coordinates",
            "timestamp_source": timestamp_source,
        }
    coords_valid = bool(location_available) and not (lat_zero and lon_zero)
    if coords_valid:
        lat_out = float(latitude)
        lon_out = float(longitude)
        location_status = "provided"
        should_retry = False
    elif bool(location_required) and not bool(location_available):
        return {
            "add_reminder_kwargs": {},
            "should_call_add_reminder": False,
            "should_retry_location_lookup": False,
            "location_status": "required_but_missing",
            "abstain_reason": "required_location_unresolved",
            "timestamp_source": timestamp_source,
        }
    else:
        lat_out = None
        lon_out = None
        location_status = "omitted"
        should_retry = False
    return {
        "add_reminder_kwargs": {
            "content": content,
            "reminder_timestamp": reminder_timestamp,
            "latitude": lat_out,
            "longitude": lon_out,
        },
        "should_call_add_reminder": True,
        "should_retry_location_lookup": should_retry,
        "abstain_reason": "",
        "location_status": location_status,
        "timestamp_source": timestamp_source,
    }
"""

SPEC = ToolSpec(
    tool_name="prepare_reminder_creation_args",
    family=ToolFamily.COMPOSITE_WORKFLOW_HELPER,
    description=(
        "Two valid call paths. "
        "Path A (preferred — use for absolute dates and for relative times when UTC offset is unknown): "
        "(1) Call datetime_info_to_timestamp first (or timestamp_to_datetime_info then "
        "datetime_info_to_timestamp for relative offsets like 'tomorrow'). "
        "(2) Wait for the result in a separate turn. "
        "(3) Then call this helper with resolved_reminder_timestamp set to that returned timestamp. "
        "Path B (only when local UTC offset is explicitly known from context): "
        "(1) Do NOT call datetime_info_to_timestamp. "
        "(2) Call this helper directly with time_fields_complete=True "
        "and day_offset, hour, minute, local_utc_offset_hours all provided with correct values. "
        "If local_utc_offset_hours is not explicitly known, use Path A instead — "
        "do not assume UTC offset is 0. "
        "NEVER call datetime_info_to_timestamp and this helper in the same turn. "
        "Do not call any base tool and a generated prep helper in the same "
        "parallel batch when the helper requires the base tool's result. "
        "Call path: prepare_reminder_creation_args(...) → "
        "add_reminder(**result['add_reminder_kwargs']) when should_call_add_reminder=True. "
        "Set location_required=True only when the user explicitly requires a "
        "location on the reminder. Optional or mentioned locations that have not "
        "resolved use location_available=False; the helper proceeds without "
        "coordinates rather than blocking the reminder unless location "
        "refinement is still in progress. If the user is still choosing or "
        "refining the location, set location_refinement_in_progress=True so "
        "the helper abstains instead of creating the reminder too early."
    ),
    inputs=(
        ToolInput(
            "content",
            "str",
            "Exact reminder content to pass through to add_reminder.",
        ),
        ToolInput(
            "resolved_reminder_timestamp",
            "float",
            "Preferred whenever available. Pass the exact Unix reminder "
            "timestamp when it is already known from prior reasoning or tool "
            "results. In ToolSandbox reminder creation, unspecified relative "
            "times such as 'tomorrow at 5 PM' are local device time by default. "
            "If current benchmark timestamp context already makes the relative "
            "reminder time resolvable, prefer passing the resolved timestamp "
            "instead of asking the user for timezone or UTC offset again. Pass "
            "0 only when the helper must compute from relative time fields "
            "instead.",
        ),
        ToolInput(
            "current_timestamp",
            "float",
            "Current Unix timestamp used only when computing from relative time "
            "fields.",
        ),
        ToolInput("day_offset", "int", "Local-day offset for the reminder date."),
        ToolInput("hour", "int", "Target local reminder hour."),
        ToolInput("minute", "int", "Target local reminder minute."),
        ToolInput(
            "local_utc_offset_hours",
            "float",
            "Local UTC offset used for relative-time conversion. Use the "
            "existing ToolSandbox local timestamp context when it is already "
            "sufficient. For plain relative reminders with no explicit timezone, "
            "treat the request as local device time and do not ask the user for "
            "timezone again unless the request is truly ambiguous.",
        ),
        ToolInput(
            "time_fields_complete",
            "bool",
            "True only when day_offset, hour, minute, and local_utc_offset_hours "
            "are fully known and safe to use for add_reminder.",
        ),
        ToolInput(
            "location_required",
            "bool",
            "True only when the user explicitly requires the reminder to include "
            "a location. False when location is optional or not mentioned.",
        ),
        ToolInput(
            "location_available",
            "bool",
            "True only when both latitude and longitude are already resolved and "
            "available. False when coordinates have not yet been obtained.",
        ),
        ToolInput("latitude", "float", "Latitude when coordinates are available."),
        ToolInput(
            "longitude",
            "float",
            "Longitude when coordinates are available.",
        ),
        ToolInput(
            "location_lookup_failed",
            "bool",
            "True when a location lookup was attempted and definitively failed. "
            "Combined with location_required=True this causes the helper to "
            "abstain. When location is not required, a failed lookup means the "
            "helper proceeds without coordinates.",
        ),
        ToolInput(
            "location_refinement_in_progress",
            "bool",
            "True when the user is still choosing or refining the location and "
            "the reminder should not yet be created. False when location was "
            "omitted, skipped, definitively failed, or is already resolved.",
        ),
    ),
    output_annotation="dict",
    output_schema={
        "type": "object",
        "properties": {
            "add_reminder_kwargs": {
                "type": "object",
                "description": "Keyword arguments to pass unchanged into the "
                "very next original add_reminder call.",
            },
            "should_call_add_reminder": {
                "type": "boolean",
                "description": "True when the agent should call add_reminder now "
                "as the next step.",
            },
            "should_retry_location_lookup": {
                "type": "boolean",
                "description": "True when the caller should retry location lookup "
                "before calling add_reminder. The caller may still proceed with "
                "add_reminder without coordinates if desired.",
            },
            "abstain_reason": {
                "type": "string",
                "description": "Reason the helper says not to call add_reminder "
                "yet. Empty when add_reminder should be called immediately.",
            },
            "location_status": {
                "type": "string",
                "enum": [
                    "provided",
                    "omitted",
                    "required_but_missing",
                    "refining",
                    "partial",
                ],
            },
            "timestamp_source": {
                "type": "string",
                "enum": ["resolved", "relative_fields", "none"],
            },
        },
        "required": [
            "add_reminder_kwargs",
            "should_call_add_reminder",
            "abstain_reason",
            "location_status",
            "timestamp_source",
        ],
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
        "Use this as the standard last step right before add_reminder. Return "
        "should_call_add_reminder=False only when time information is missing or "
        "malformed, when the user explicitly requires a location that is still "
        "unresolved, when location refinement is still in progress, or when only "
        "partial coordinates are available. When should_call_add_reminder is "
        "False, do not call add_reminder. Prefer resolved_reminder_timestamp "
        "whenever it is already available from prior tool results or existing "
        "timestamp context. For plain relative reminders like 'tomorrow at 5 PM', "
        "treat that time as local device time and do not ask the user for "
        "timezone or UTC offset again when the current ToolSandbox timestamp "
        "context is already sufficient. If optional location lookup fails or "
        "location is not required, proceed without coordinates. If "
        "should_call_add_reminder=True, call add_reminder with "
        "add_reminder_kwargs unchanged."
    ),
    generalization_rationale=(
        "Reminder creation tasks need a deterministic final preparation step "
        "before add_reminder so the agent can stop re-asking for optional "
        "location details, stop retrying failed location lookup, and still call "
        "the original ToolSandbox side-effect tool."
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
    # Case 1: Relative time, no location — location_status="omitted"
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
            "location_lookup_failed": False,
            "location_refinement_in_progress": False,
        },
        {
            "add_reminder_kwargs": {
                "content": "Buy tickets",
                "reminder_timestamp": 147600.0,
                "latitude": None,
                "longitude": None,
            },
            "should_call_add_reminder": True,
            "should_retry_location_lookup": False,
            "location_status": "omitted",
            "abstain_reason": "",
            "timestamp_source": "relative_fields",
        },
    ),
    # Case 2: Resolved timestamp, no location — location_status="omitted"
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
            "location_refinement_in_progress": False,
        },
        {
            "add_reminder_kwargs": {
                "content": "Team meeting",
                "reminder_timestamp": 1777500000.0,
                "latitude": None,
                "longitude": None,
            },
            "should_call_add_reminder": True,
            "should_retry_location_lookup": False,
            "location_status": "omitted",
            "abstain_reason": "",
            "timestamp_source": "resolved",
        },
        held_out=True,
    ),
    # Case 3: Optional location available — location_status="provided"
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
            "location_refinement_in_progress": False,
        },
        {
            "add_reminder_kwargs": {
                "content": "Arrive early",
                "reminder_timestamp": 1777496400.0,
                "latitude": 37.3237926356735,
                "longitude": -122.03961770355414,
            },
            "should_call_add_reminder": True,
            "should_retry_location_lookup": False,
            "location_status": "provided",
            "abstain_reason": "",
            "timestamp_source": "relative_fields",
        },
    ),
    # Case 4: Optional location lookup failed — proceed without coords (low-battery
    # scenario). NOT an abstain case — location is not required.
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
            "location_refinement_in_progress": False,
        },
        {
            "add_reminder_kwargs": {
                "content": "Whole Foods while low battery",
                "reminder_timestamp": 898200.0,
                "latitude": None,
                "longitude": None,
            },
            "should_call_add_reminder": True,
            "should_retry_location_lookup": False,
            "location_status": "omitted",
            "abstain_reason": "",
            "timestamp_source": "relative_fields",
        },
    ),
    # Case 5: Required location definitively failed — abstain
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
            "location_refinement_in_progress": False,
        },
        {
            "add_reminder_kwargs": {},
            "should_call_add_reminder": False,
            "should_retry_location_lookup": False,
            "location_status": "required_but_missing",
            "abstain_reason": "required_location_unresolved",
            "timestamp_source": "relative_fields",
        },
        negative_applicability=True,
    ),
    # Case 6: Missing time — abstain
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
            "location_refinement_in_progress": False,
        },
        {
            "add_reminder_kwargs": {},
            "should_call_add_reminder": False,
            "location_status": "omitted",
            "abstain_reason": "missing_time_info",
            "timestamp_source": "none",
        },
        negative_applicability=True,
    ),
    # Case 7: Both coords zero with location_available=True -> treat as not
    # available -> omit and proceed for optional location.
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
            "longitude": 0.0,
            "location_lookup_failed": False,
            "location_refinement_in_progress": False,
        },
        {
            "add_reminder_kwargs": {
                "content": "Pick up package",
                "reminder_timestamp": 43200.0,
                "latitude": None,
                "longitude": None,
            },
            "should_call_add_reminder": True,
            "should_retry_location_lookup": False,
            "location_status": "omitted",
            "abstain_reason": "",
            "timestamp_source": "relative_fields",
        },
    ),
    # Case 8: Optional location still being refined -> abstain
    ToolExample(
        {
            "content": "Stop by the store",
            "resolved_reminder_timestamp": 0.0,
            "current_timestamp": 864000.0,
            "day_offset": 0,
            "hour": 10,
            "minute": 15,
            "local_utc_offset_hours": 0.0,
            "time_fields_complete": True,
            "location_required": False,
            "location_available": False,
            "latitude": 0.0,
            "longitude": 0.0,
            "location_lookup_failed": False,
            "location_refinement_in_progress": True,
        },
        {
            "add_reminder_kwargs": {},
            "should_call_add_reminder": False,
            "should_retry_location_lookup": False,
            "location_status": "refining",
            "abstain_reason": "location_still_being_refined",
            "timestamp_source": "relative_fields",
        },
    ),
    # Case 9: Required location unresolved even before definitive failure -> abstain
    ToolExample(
        {
            "content": "Meet at the venue",
            "resolved_reminder_timestamp": 0.0,
            "current_timestamp": 0.0,
            "day_offset": 1,
            "hour": 18,
            "minute": 0,
            "local_utc_offset_hours": 0.0,
            "time_fields_complete": True,
            "location_required": True,
            "location_available": False,
            "latitude": 0.0,
            "longitude": 0.0,
            "location_lookup_failed": False,
            "location_refinement_in_progress": False,
        },
        {
            "add_reminder_kwargs": {},
            "should_call_add_reminder": False,
            "should_retry_location_lookup": False,
            "location_status": "required_but_missing",
            "abstain_reason": "required_location_unresolved",
            "timestamp_source": "relative_fields",
        },
    ),
    # Case 10: Partial coordinates -> abstain
    ToolExample(
        {
            "content": "Drop off return",
            "resolved_reminder_timestamp": 0.0,
            "current_timestamp": 0.0,
            "day_offset": 0,
            "hour": 13,
            "minute": 45,
            "local_utc_offset_hours": 0.0,
            "time_fields_complete": True,
            "location_required": False,
            "location_available": True,
            "latitude": 37.0,
            "longitude": 0.0,
            "location_lookup_failed": False,
            "location_refinement_in_progress": False,
        },
        {
            "add_reminder_kwargs": {},
            "should_call_add_reminder": False,
            "should_retry_location_lookup": False,
            "location_status": "partial",
            "abstain_reason": "partial_location_coordinates",
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
            birth_scenario="add_reminder_content_and_week_delta_and_time",
        )
    )
    print(args.registry_dir / "registry_manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
