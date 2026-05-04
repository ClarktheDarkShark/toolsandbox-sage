"""Register the claim-safe select_record_by_timestamp_extreme helper.

Usage:
    python scripts/register_select_record_by_timestamp_extreme.py
    python scripts/register_select_record_by_timestamp_extreme.py --registry-dir outputs/tmp_registry
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
def select_record_by_timestamp_extreme(
    records,
    timestamp_field,
    mode,
    tie_break_fields=None,
    required_filters=None,
    allow_missing_timestamp=False,
):
    if mode not in ("latest", "oldest"):
        return {
            "selected_record": None,
            "selected_index": None,
            "selected_timestamp": None,
            "should_use_selected_record": False,
            "abstain_reason": "invalid_mode",
            "selection_reason": "",
        }
    best_idx = None
    best_record = None
    best_ts = None
    for i, record in enumerate(records or []):
        if not isinstance(record, dict):
            continue
        if required_filters:
            filter_match = True
            for _fk, _fv in required_filters.items():
                if record.get(_fk) != _fv:
                    filter_match = False
                    break
            if not filter_match:
                continue
        ts_raw = record.get(timestamp_field)
        if ts_raw is None:
            continue
        if not isinstance(ts_raw, (int, float)):
            continue
        ts_val = float(ts_raw)
        if best_ts is None:
            best_idx = i
            best_record = record
            best_ts = ts_val
        elif mode == "latest" and ts_val > best_ts:
            best_idx = i
            best_record = record
            best_ts = ts_val
        elif mode == "oldest" and ts_val < best_ts:
            best_idx = i
            best_record = record
            best_ts = ts_val
    if best_record is None:
        return {
            "selected_record": None,
            "selected_index": None,
            "selected_timestamp": None,
            "should_use_selected_record": False,
            "abstain_reason": "no_valid_timestamped_records",
            "selection_reason": "",
        }
    return {
        "selected_record": best_record,
        "selected_index": best_idx,
        "selected_timestamp": best_ts,
        "should_use_selected_record": True,
        "abstain_reason": "",
        "selection_reason": "selected_" + mode + "_by_" + str(timestamp_field),
    }
"""

SPEC = ToolSpec(
    tool_name="select_record_by_timestamp_extreme",
    family=ToolFamily.SEARCH_FILTER_RANKING_HELPER,
    description=(
        "When the user asks for the latest, newest, most recent, oldest, earliest, "
        "or first record from a search, you MUST call this helper after retrieving "
        "the records — do NOT manually compare timestamps across turns. "
        "Set mode='latest' for most recent/newest/last. "
        "Set mode='oldest' for oldest/earliest/first. "
        "Complete call path for messages: "
        "(1) Call get_current_timestamp to get the current Unix timestamp. "
        "(2) Call search_messages with creation_timestamp_upperbound=<current_timestamp> "
        "to retrieve all messages. "
        "(3) In the NEXT turn (NOT the same parallel turn), call this helper with "
        "records=<messages list>, timestamp_field='creation_timestamp', "
        "and mode='latest' or mode='oldest'. "
        "(4) If should_use_selected_record=True, use selected_record directly for "
        "the next action (modify, send, remove, update). "
        "Do NOT call search_messages({}) or search_messages with an empty content "
        "filter — this returns no results. Always use creation_timestamp_upperbound. "
        "Do NOT attempt manual timestamp comparison. "
        "Do NOT skip this helper when records are returned and recency selection is needed. "
        "NEVER call a search tool and this helper in the same parallel turn. "
        "This helper does NOT call any side-effect tools and does NOT search for "
        "records itself — it only selects from records already returned. "
        "Use timestamp_field='creation_timestamp' for messages, "
        "'reminder_timestamp' for reminders, or the appropriate field name "
        "visible in the returned records. "
        "Ties in timestamp are broken deterministically by original list order "
        "(the first occurrence in the input list wins). "
        "Do NOT use this helper when no records have been retrieved yet, "
        "when the task is pure reminder creation with no record selection, "
        "when the task is pure service enabling, "
        "or when the task is marked insufficient information."
    ),
    inputs=(
        ToolInput(
            "records",
            "list",
            "The list of record dicts returned by a prior search tool call "
            "(e.g., the 'messages' list from search_messages, or the 'reminders' "
            "list from search_reminder). Pass the list directly.",
        ),
        ToolInput(
            "timestamp_field",
            "str",
            "The field name in each record that contains the Unix timestamp to "
            "compare. Common values: 'creation_timestamp' for messages, "
            "'reminder_timestamp' for reminders.",
        ),
        ToolInput(
            "mode",
            "str",
            "Selection mode: 'latest' to select the record with the highest "
            "timestamp, 'oldest' to select the record with the lowest timestamp.",
        ),
        ToolInput(
            "tie_break_fields",
            "list",
            "Optional list of field names to use as secondary sort key when "
            "timestamps are equal. Pass None to use original list order for ties.",
        ),
        ToolInput(
            "required_filters",
            "dict",
            "Optional dict of field:value pairs. Only records matching ALL filters "
            "are considered. Pass None or empty dict to skip filtering.",
        ),
        ToolInput(
            "allow_missing_timestamp",
            "bool",
            "If False (default), records without the timestamp_field are skipped. "
            "If True, records with missing timestamps are included but sorted last.",
        ),
    ),
    output_annotation="dict",
    output_schema={
        "type": "object",
        "properties": {
            "selected_record": {
                "type": ["object", "null"],
                "description": "The full record dict for the selected record, "
                "or null if no valid record could be selected.",
            },
            "selected_index": {
                "type": ["integer", "null"],
                "description": "Zero-based index of the selected record in the "
                "original records list, or null if abstaining.",
            },
            "selected_timestamp": {
                "type": ["number", "null"],
                "description": "The timestamp value of the selected record, "
                "or null if abstaining.",
            },
            "should_use_selected_record": {
                "type": "boolean",
                "description": "True when the agent should use selected_record "
                "for the next step. False when the helper is abstaining.",
            },
            "abstain_reason": {
                "type": "string",
                "description": "Reason for abstaining. Empty when "
                "should_use_selected_record=True.",
            },
            "selection_reason": {
                "type": "string",
                "description": "Brief description of how the record was selected.",
            },
        },
        "required": [
            "selected_record",
            "selected_index",
            "selected_timestamp",
            "should_use_selected_record",
            "abstain_reason",
            "selection_reason",
        ],
    },
    positive_triggers=(
        "search_message_with_recency_latest",
        "search_message_with_recency_oldest",
        "modify_contact_with_message_recency",
        "remove_reminder_with_recency_latest",
        "modify_reminder_with_recency_latest",
        "select_latest_or_oldest_record_from_search_results",
        "record_returned_needs_latest_oldest_selection",
    ),
    negative_triggers=(
        "add_reminder",
        "insufficient_information",
        "pure_service_enablement",
        "pure_date_arithmetic",
        "no_records_retrieved_yet",
        "search_without_recency_selection",
    ),
    preserves_side_effect_tools=(),
    required_original_tool_calls=(),
    abstain_behavior=(
        "Return should_use_selected_record=False with abstain_reason when: "
        "the records list is empty or None, "
        "no record in the list has the specified timestamp_field, "
        "mode is not 'latest' or 'oldest', "
        "or required_filters eliminate all candidates. "
        "When should_use_selected_record=True, use selected_record directly "
        "for the next action — do not call the search tool again. "
        "This helper does not call side-effect tools. "
        "Do not use this helper before records have been retrieved."
    ),
    generalization_rationale=(
        "Record selection tasks repeatedly require choosing the single latest "
        "or oldest record from a list returned by search tools. The base toolset "
        "provides search tools but no deterministic latest/oldest selector. "
        "Agents frequently pick the wrong record or spend extra turns on manual "
        "comparison. This helper is reusable across message, reminder, and "
        "contact recency tasks."
    ),
    inadequacy_evidence=StructuredInadequacyEvidence(
        summary=(
            "Search results require selecting the latest or oldest record by "
            "timestamp, but agents make wrong selections or waste extra turns "
            "on manual comparison across message, reminder, and contact tasks."
        ),
        signals=(
            "wrong_record_selected_after_search",
            "repeated_failed_base_tool_calls",
            "unnecessary_clarification",
        ),
        failed_tool_calls=("search_messages", "search_reminder"),
        repeated_failed_tool_calls=("search_messages",),
        visible_data_gaps=(
            "records list with timestamps already returned by search tool; "
            "requires deterministic latest/oldest selection before side-effect call",
        ),
        final_answer_route_mismatch=True,
    ),
)

TOOL = GeneratedTool(spec=SPEC, code=TOOL_CODE)

EXAMPLES = (
    # Case 1: Select latest message by creation_timestamp
    ToolExample(
        {
            "records": [
                {"content": "older message", "creation_timestamp": 1000.0},
                {"content": "newer message", "creation_timestamp": 2000.0},
            ],
            "timestamp_field": "creation_timestamp",
            "mode": "latest",
            "tie_break_fields": None,
            "required_filters": None,
            "allow_missing_timestamp": False,
        },
        {
            "selected_record": {
                "content": "newer message",
                "creation_timestamp": 2000.0,
            },
            "selected_index": 1,
            "selected_timestamp": 2000.0,
            "should_use_selected_record": True,
            "abstain_reason": "",
            "selection_reason": "selected_latest_by_creation_timestamp",
        },
    ),
    # Case 2: Select oldest message — held_out
    ToolExample(
        {
            "records": [
                {"content": "middle message", "creation_timestamp": 1500.0},
                {"content": "oldest message", "creation_timestamp": 500.0},
                {"content": "newest message", "creation_timestamp": 3000.0},
            ],
            "timestamp_field": "creation_timestamp",
            "mode": "oldest",
            "tie_break_fields": None,
            "required_filters": None,
            "allow_missing_timestamp": False,
        },
        {
            "selected_record": {
                "content": "oldest message",
                "creation_timestamp": 500.0,
            },
            "selected_index": 1,
            "selected_timestamp": 500.0,
            "should_use_selected_record": True,
            "abstain_reason": "",
            "selection_reason": "selected_oldest_by_creation_timestamp",
        },
        held_out=True,
    ),
    # Case 3: Select latest reminder by reminder_timestamp
    ToolExample(
        {
            "records": [
                {"content": "buy milk", "reminder_timestamp": 86400.0},
                {"content": "call doctor", "reminder_timestamp": 172800.0},
                {"content": "pick up kids", "reminder_timestamp": 43200.0},
            ],
            "timestamp_field": "reminder_timestamp",
            "mode": "latest",
            "tie_break_fields": None,
            "required_filters": None,
            "allow_missing_timestamp": False,
        },
        {
            "selected_record": {
                "content": "call doctor",
                "reminder_timestamp": 172800.0,
            },
            "selected_index": 1,
            "selected_timestamp": 172800.0,
            "should_use_selected_record": True,
            "abstain_reason": "",
            "selection_reason": "selected_latest_by_reminder_timestamp",
        },
    ),
    # Case 4: Tie-breaking by list order (first occurrence wins)
    ToolExample(
        {
            "records": [
                {"content": "first tied", "creation_timestamp": 1000.0},
                {"content": "second tied", "creation_timestamp": 1000.0},
            ],
            "timestamp_field": "creation_timestamp",
            "mode": "latest",
            "tie_break_fields": None,
            "required_filters": None,
            "allow_missing_timestamp": False,
        },
        {
            "selected_record": {"content": "first tied", "creation_timestamp": 1000.0},
            "selected_index": 0,
            "selected_timestamp": 1000.0,
            "should_use_selected_record": True,
            "abstain_reason": "",
            "selection_reason": "selected_latest_by_creation_timestamp",
        },
    ),
    # Case 5: No records — abstain (negative_applicability=True)
    ToolExample(
        {
            "records": [],
            "timestamp_field": "creation_timestamp",
            "mode": "latest",
            "tie_break_fields": None,
            "required_filters": None,
            "allow_missing_timestamp": False,
        },
        {
            "selected_record": None,
            "selected_index": None,
            "selected_timestamp": None,
            "should_use_selected_record": False,
            "abstain_reason": "no_valid_timestamped_records",
            "selection_reason": "",
        },
        negative_applicability=True,
    ),
    # Case 6: All records missing the timestamp field — abstain (negative_applicability=True)
    ToolExample(
        {
            "records": [
                {"content": "no timestamp here"},
                {"content": "also no timestamp"},
            ],
            "timestamp_field": "creation_timestamp",
            "mode": "oldest",
            "tie_break_fields": None,
            "required_filters": None,
            "allow_missing_timestamp": False,
        },
        {
            "selected_record": None,
            "selected_index": None,
            "selected_timestamp": None,
            "should_use_selected_record": False,
            "abstain_reason": "no_valid_timestamped_records",
            "selection_reason": "",
        },
        negative_applicability=True,
    ),
    # Case 7: required_filters narrows candidates before selection
    ToolExample(
        {
            "records": [
                {
                    "sender": "alice",
                    "content": "from alice old",
                    "creation_timestamp": 100.0,
                },
                {
                    "sender": "bob",
                    "content": "from bob recent",
                    "creation_timestamp": 900.0,
                },
                {
                    "sender": "alice",
                    "content": "from alice recent",
                    "creation_timestamp": 500.0,
                },
            ],
            "timestamp_field": "creation_timestamp",
            "mode": "latest",
            "tie_break_fields": None,
            "required_filters": {"sender": "alice"},
            "allow_missing_timestamp": False,
        },
        {
            "selected_record": {
                "sender": "alice",
                "content": "from alice recent",
                "creation_timestamp": 500.0,
            },
            "selected_index": 2,
            "selected_timestamp": 500.0,
            "should_use_selected_record": True,
            "abstain_reason": "",
            "selection_reason": "selected_latest_by_creation_timestamp",
        },
    ),
    # Case 8: Mixed records — some with timestamp, some without; skip missing
    ToolExample(
        {
            "records": [
                {"content": "no timestamp"},
                {"content": "has timestamp", "creation_timestamp": 750.0},
            ],
            "timestamp_field": "creation_timestamp",
            "mode": "oldest",
            "tie_break_fields": None,
            "required_filters": None,
            "allow_missing_timestamp": False,
        },
        {
            "selected_record": {
                "content": "has timestamp",
                "creation_timestamp": 750.0,
            },
            "selected_index": 1,
            "selected_timestamp": 750.0,
            "should_use_selected_record": True,
            "abstain_reason": "",
            "selection_reason": "selected_oldest_by_creation_timestamp",
        },
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--registry-dir",
        type=Path,
        default=Path("outputs/select_record_by_timestamp_extreme_registry"),
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
            birth_scenario="search_message_with_recency_latest",
        )
    )
    print(args.registry_dir / "registry_manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
