"""Register the claim-safe resolve_search_window_or_bounds helper.

Usage:
    python scripts/register_resolve_search_window_or_bounds.py
    python scripts/register_resolve_search_window_or_bounds.py --registry-dir outputs/tmp_registry
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
def resolve_search_window_or_bounds(
    current_timestamp: float,
    phrase: str,
    target_domain: str,
    timestamp_intent: str,
    direction: str,
    content_keyword: str = "",
    lookback_days: int = 0,
    timezone_offset: float = 0.0,
) -> dict:
    min_timestamp = 315529200.0
    now = float(current_timestamp)
    if now <= 0:
        return {
            "target_tool_name": "",
            "search_kwargs": {},
            "should_call_search": False,
            "abstain_reason": "missing_current_timestamp",
            "interpretation": "",
            "bounds_source": "abstain",
        }
    domain = str(target_domain or "").strip().lower()
    if domain == "message":
        tool_name = "search_messages"
    elif domain == "reminder":
        tool_name = "search_reminder"
    else:
        return {
            "target_tool_name": "",
            "search_kwargs": {},
            "should_call_search": False,
            "abstain_reason": "unsupported_target_domain",
            "interpretation": "",
            "bounds_source": "abstain",
        }
    intent = str(timestamp_intent or "").strip().lower()
    if domain == "message":
        lower_key = "creation_timestamp_lowerbound"
        upper_key = "creation_timestamp_upperbound"
    elif intent == "creation":
        lower_key = "creation_timestamp_lowerbound"
        upper_key = "creation_timestamp_upperbound"
    elif intent == "reminder":
        lower_key = "reminder_timestamp_lowerbound"
        upper_key = "reminder_timestamp_upperbound"
    else:
        return {
            "target_tool_name": "",
            "search_kwargs": {},
            "should_call_search": False,
            "abstain_reason": "unsupported_timestamp_intent",
            "interpretation": "",
            "bounds_source": "abstain",
        }
    normalized_direction = str(direction or "").strip().lower()
    normalized_phrase = str(phrase or "").strip().lower()
    if not normalized_direction:
        if normalized_phrase in ("yesterday", "today", "later today", "later_today", "upcoming", "recent", "latest", "oldest"):
            normalized_direction = normalized_phrase.replace(" ", "_")
        else:
            return {
                "target_tool_name": "",
                "search_kwargs": {},
                "should_call_search": False,
                "abstain_reason": "ambiguous_phrase",
                "interpretation": "",
                "bounds_source": "abstain",
            }
    offset_seconds = float(timezone_offset) * 3600.0
    local_now = now + offset_seconds
    local_day_start = float(int(local_now // 86400.0) * 86400.0)
    day_start = local_day_start - offset_seconds
    next_day_start = day_start + 86400.0
    kwargs = {}
    interpretation = normalized_direction
    bounds_source = "resolved_direction"
    if normalized_direction == "yesterday":
        kwargs[lower_key] = max(min_timestamp, day_start - 86400.0)
        kwargs[upper_key] = max(min_timestamp, day_start - 1.0)
    elif normalized_direction == "today":
        kwargs[lower_key] = max(min_timestamp, day_start)
        kwargs[upper_key] = max(min_timestamp, next_day_start - 1.0)
    elif normalized_direction == "later_today":
        kwargs[lower_key] = max(min_timestamp, now)
        kwargs[upper_key] = max(min_timestamp, next_day_start - 1.0)
    elif normalized_direction == "upcoming":
        kwargs[lower_key] = max(min_timestamp, now)
    elif normalized_direction == "recent":
        days = int(lookback_days)
        if days <= 0:
            days = 7
        kwargs[lower_key] = max(min_timestamp, now - days * 86400.0)
        kwargs[upper_key] = max(min_timestamp, now)
    elif normalized_direction in ("latest", "oldest"):
        if domain == "message":
            kwargs[upper_key] = max(min_timestamp, now)
        else:
            days = int(lookback_days)
            if days <= 0:
                days = 3650
            kwargs[lower_key] = max(min_timestamp, now - days * 86400.0)
            kwargs[upper_key] = max(min_timestamp, now)
    elif normalized_direction == "custom":
        days = int(lookback_days)
        if days <= 0:
            return {
                "target_tool_name": "",
                "search_kwargs": {},
                "should_call_search": False,
                "abstain_reason": "custom_window_requires_positive_lookback_days",
                "interpretation": "",
                "bounds_source": "abstain",
            }
        kwargs[lower_key] = max(min_timestamp, now - days * 86400.0)
        kwargs[upper_key] = max(min_timestamp, now)
        interpretation = "custom_lookback"
    else:
        return {
            "target_tool_name": "",
            "search_kwargs": {},
            "should_call_search": False,
            "abstain_reason": "unsupported_direction",
            "interpretation": "",
            "bounds_source": "abstain",
        }
    if str(content_keyword or "").strip():
        kwargs["content"] = str(content_keyword)
    if not kwargs:
        return {
            "target_tool_name": "",
            "search_kwargs": {},
            "should_call_search": False,
            "abstain_reason": "no_search_criteria_prepared",
            "interpretation": "",
            "bounds_source": "abstain",
        }
    return {
        "target_tool_name": tool_name,
        "search_kwargs": kwargs,
        "should_call_search": True,
        "abstain_reason": "",
        "interpretation": interpretation,
        "bounds_source": bounds_source,
    }
"""

SPEC = ToolSpec(
    tool_name="resolve_search_window_or_bounds",
    family=ToolFamily.DERIVED_VALUE_CALCULATOR,
    description=(
        "When a search task needs bounded time criteria such as yesterday, today, "
        "later today, upcoming, recent, latest, or oldest, you MUST call this "
        "helper after obtaining get_current_timestamp and BEFORE calling the "
        "original search tool. Call path: (1) get_current_timestamp. "
        "(2) In the NEXT turn call resolve_search_window_or_bounds with "
        "current_timestamp, target_domain, timestamp_intent, and direction. "
        "(3) If should_call_search=True, call the original tool named in "
        "target_tool_name with **search_kwargs. This helper never calls search "
        "itself and never creates, modifies, or sends anything. Use "
        "target_domain='reminder' with timestamp_intent='creation' for reminder "
        "creation-time recency, timestamp_intent='reminder' for reminder due-time "
        "recency, and target_domain='message' with timestamp_intent='message_creation' "
        "for message search. Do NOT call search_messages({}) or search_reminder({}) "
        "with no criteria. Do NOT manually construct timestamp bounds across turns "
        "when this helper is visible. For latest or oldest message search, use "
        "the helper output to produce trace-compatible search_messages kwargs "
        "before any later record-selection helper. If this helper is visible at "
        "the same time as a record-selection helper, call this helper FIRST, then "
        "call the original search tool, and only then call the selector with the "
        "returned records in a later turn. If the phrase is ambiguous or "
        "current_timestamp is missing, the helper abstains and you should ask for "
        "clarification rather than guessing."
    ),
    inputs=(
        ToolInput(
            "current_timestamp",
            "float",
            "Current Unix timestamp from get_current_timestamp.",
        ),
        ToolInput(
            "phrase",
            "str",
            "Original user-facing time phrase, such as 'yesterday' or 'later today'.",
        ),
        ToolInput("target_domain", "str", "Either 'reminder' or 'message'."),
        ToolInput(
            "timestamp_intent",
            "str",
            "For reminders use 'creation' or 'reminder'. For messages use 'message_creation'.",
        ),
        ToolInput(
            "direction",
            "str",
            "Normalized time-window intent: yesterday, today, later_today, upcoming, recent, latest, oldest, or custom.",
        ),
        ToolInput(
            "content_keyword",
            "str",
            "Optional content filter to pass through to the original search tool.",
        ),
        ToolInput(
            "lookback_days",
            "int",
            "Optional explicit lookback window in days for recent/custom searches.",
        ),
        ToolInput(
            "timezone_offset",
            "float",
            "Optional local UTC offset in hours when local-day boundaries matter.",
        ),
    ),
    output_annotation="dict",
    output_schema={
        "type": "object",
        "properties": {
            "target_tool_name": {"type": "string"},
            "search_kwargs": {"type": "object"},
            "should_call_search": {"type": "boolean"},
            "abstain_reason": {"type": "string"},
            "interpretation": {"type": "string"},
            "bounds_source": {"type": "string"},
        },
        "required": [
            "target_tool_name",
            "search_kwargs",
            "should_call_search",
            "abstain_reason",
            "interpretation",
            "bounds_source",
        ],
    },
    positive_triggers=(
        "search_reminder_with_creation_recency_yesterday",
        "search_reminder_with_recency_yesterday",
        "search_reminder_with_recency_upcoming",
        "search_message_with_recency_latest",
        "search_message_with_recency_oldest",
        "bounded_recency_search_requires_time_window",
    ),
    negative_triggers=(
        "add_reminder",
        "modify_contact",
        "pure_service_enablement",
        "insufficient_information",
        "search_without_time_phrase",
    ),
    preserves_side_effect_tools=(),
    required_original_tool_calls=(),
    abstain_behavior=(
        "Return should_call_search=False with abstain_reason when current_timestamp "
        "is missing, the target domain or timestamp intent is unsupported, or the "
        "phrase/direction is ambiguous. When should_call_search=True, call only the "
        "original search tool in target_tool_name with **search_kwargs."
    ),
    generalization_rationale=(
        "Reminder and message search tasks repeatedly require converting a natural "
        "time phrase into benchmark-compatible lower/upper bounds before a search "
        "tool can be called safely. This helper compresses multi-step time-window "
        "construction without replacing the original search tool."
    ),
    inadequacy_evidence=StructuredInadequacyEvidence(
        summary=(
            "Reminder and message search tasks fail when the agent needs bounded "
            "timestamp criteria but only has natural recency language such as "
            "yesterday, today, upcoming, latest, or oldest."
        ),
        signals=(
            "repeated_failed_tool_call",
            "visible_raw_data_lacking_deterministic_transform",
            "unnecessary_clarification",
        ),
        failed_tool_calls=("search_reminder", "search_messages"),
        repeated_failed_tool_calls=("search_reminder", "search_messages"),
        visible_data_gaps=("missing benchmark-compatible search window kwargs",),
        planner_failures=("no_criteria_search_call",),
        final_answer_route_mismatch=False,
    ),
)

EXAMPLES = (
    ToolExample(
        {
            "current_timestamp": 1777380998.0,
            "phrase": "yesterday",
            "target_domain": "reminder",
            "timestamp_intent": "creation",
            "direction": "yesterday",
            "content_keyword": "",
            "lookback_days": 0,
            "timezone_offset": 0.0,
        },
        {
            "target_tool_name": "search_reminder",
            "search_kwargs": {
                "creation_timestamp_lowerbound": 1777248000.0,
                "creation_timestamp_upperbound": 1777334399.0,
            },
            "should_call_search": True,
            "abstain_reason": "",
            "interpretation": "yesterday",
            "bounds_source": "resolved_direction",
        },
    ),
    ToolExample(
        {
            "current_timestamp": 1777380998.0,
            "phrase": "today",
            "target_domain": "reminder",
            "timestamp_intent": "reminder",
            "direction": "today",
            "content_keyword": "",
            "lookback_days": 0,
            "timezone_offset": 0.0,
        },
        {
            "target_tool_name": "search_reminder",
            "search_kwargs": {
                "reminder_timestamp_lowerbound": 1777334400.0,
                "reminder_timestamp_upperbound": 1777420799.0,
            },
            "should_call_search": True,
            "abstain_reason": "",
            "interpretation": "today",
            "bounds_source": "resolved_direction",
        },
        held_out=True,
    ),
    ToolExample(
        {
            "current_timestamp": 1777380998.0,
            "phrase": "most recent message",
            "target_domain": "message",
            "timestamp_intent": "message_creation",
            "direction": "latest",
            "content_keyword": "project",
            "lookback_days": 0,
            "timezone_offset": 0.0,
        },
        {
            "target_tool_name": "search_messages",
            "search_kwargs": {
                "creation_timestamp_upperbound": 1777380998.0,
                "content": "project",
            },
            "should_call_search": True,
            "abstain_reason": "",
            "interpretation": "latest",
            "bounds_source": "resolved_direction",
        },
    ),
    ToolExample(
        {
            "current_timestamp": 0.0,
            "phrase": "yesterday",
            "target_domain": "reminder",
            "timestamp_intent": "creation",
            "direction": "yesterday",
            "content_keyword": "",
            "lookback_days": 0,
            "timezone_offset": 0.0,
        },
        {
            "target_tool_name": "",
            "search_kwargs": {},
            "should_call_search": False,
            "abstain_reason": "missing_current_timestamp",
            "interpretation": "",
            "bounds_source": "abstain",
        },
        negative_applicability=True,
    ),
    ToolExample(
        {
            "current_timestamp": 1777380998.0,
            "phrase": "sometime soon",
            "target_domain": "message",
            "timestamp_intent": "message_creation",
            "direction": "",
            "content_keyword": "",
            "lookback_days": 0,
            "timezone_offset": 0.0,
        },
        {
            "target_tool_name": "",
            "search_kwargs": {},
            "should_call_search": False,
            "abstain_reason": "ambiguous_phrase",
            "interpretation": "",
            "bounds_source": "abstain",
        },
        negative_applicability=True,
    ),
)

TOOL = GeneratedTool(spec=SPEC, code=TOOL_CODE)


def register(*, registry_dir: Path) -> RegistryEntry:
    validation = validate_generated_tool(TOOL, EXAMPLES)
    if not validation.accepted:
        raise SystemExit(
            "resolve_search_window_or_bounds validation failed: "
            + "; ".join(validation.errors)
        )
    store = RegistryStore(registry_dir)
    entry = RegistryEntry.accepted(
        TOOL,
        validation,
        birth_scenario="search_reminder_with_creation_recency_yesterday",
    )
    store.put(entry)
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry-dir",
        type=Path,
        default=Path("outputs/resolve_search_window_or_bounds_registry"),
    )
    args = parser.parse_args()
    entry = register(registry_dir=args.registry_dir)
    print(
        {
            "accepted": entry.validation.accepted,
            "tool_name": entry.tool.spec.tool_name,
            "registry_dir": str(args.registry_dir),
            "source_example_count": entry.validation.source_example_count,
            "held_out_check_count": entry.validation.held_out_check_count,
            "negative_applicability_count": entry.validation.negative_applicability_count,
            "runtime_smoke_passed": entry.validation.runtime_smoke_passed,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
