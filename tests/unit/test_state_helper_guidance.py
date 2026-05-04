from sage_ts.adequacy.inadequacy_classifier import _next_service_tool_call_observation
from sage_ts.generation.tool_spec import (
    GeneratedTool,
    StructuredInadequacyEvidence,
    ToolFamily,
    ToolInput,
    ToolSpec,
)
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.runtime.toolsandbox_integration import _google_docstring
from sage_ts.validation.sandbox_validator import ValidationResult


def _state_helper_entry() -> RegistryEntry:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="next_service_tool_call",
            family=ToolFamily.STATE_PRECONDITION_HELPER,
            description="Return the exact next ToolSandbox tool call.",
            inputs=(
                ToolInput("target_service", "str", "Requested service."),
                ToolInput("wifi_enabled", "bool", "Whether wifi is already enabled."),
                ToolInput(
                    "cellular_enabled",
                    "bool",
                    "Whether cellular is already enabled.",
                ),
                ToolInput(
                    "location_service_enabled",
                    "bool",
                    "Whether location service is already enabled.",
                ),
                ToolInput(
                    "low_battery_mode",
                    "bool",
                    "Whether low battery mode is enabled.",
                ),
            ),
            output_annotation="dict",
            generalization_rationale="State precondition handling recurs.",
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Base tools do not expose a deterministic next step.",
                signals=("state_precondition",),
            ),
        ),
        code="def next_service_tool_call(*args, **kwargs):\n    return {}\n",
    )
    validation = ValidationResult(
        accepted=True,
        errors=(),
        source_example_count=2,
        held_out_check_count=1,
        runtime_smoke_passed=True,
    )
    return RegistryEntry.accepted(tool, validation, birth_scenario="toy_birth")


def test_next_service_tool_call_observation_scopes_to_single_target() -> None:
    observation = _next_service_tool_call_observation(
        "turn_on_wifi_low_battery_mode"
    ).observation

    assert "one chosen target service at a time" in observation
    assert "must not encourage calling parallel or alternative service flows" in (
        observation
    )
    assert "report only the final state of that chosen target service" in observation


def test_next_service_tool_call_docstring_includes_usage_constraints() -> None:
    docstring = _google_docstring(_state_helper_entry())

    assert "Usage:" in docstring
    assert "Use only for the single service you are actively trying to change." in (
        docstring
    )
    assert "Do not call this helper for multiple alternative services in parallel." in (
        docstring
    )
    assert "answer only about that final target state" in docstring


def test_generic_downstream_helper_docstring_uses_actual_output_schema() -> None:
    tool = GeneratedTool(
        spec=ToolSpec(
            tool_name="message_search_time_window",
            family=ToolFamily.DERIVED_VALUE_CALCULATOR,
            description="Compute timestamp bounds for message search.",
            inputs=(
                ToolInput("anchor_timestamp", "float", "Reference timestamp."),
                ToolInput("lookback_days", "int", "Days to look back."),
            ),
            output_annotation="dict",
            output_schema={
                "type": "object",
                "properties": {
                    "creation_timestamp_lowerbound": {"type": "number"},
                    "creation_timestamp_upperbound": {"type": "number"},
                },
            },
            positive_triggers=("latest message", "oldest message"),
            negative_triggers=("missing current timestamp",),
            required_original_tool_calls=("search_messages",),
            generalization_rationale="Message recency search recurs.",
            inadequacy_evidence=StructuredInadequacyEvidence(
                summary="Manual timestamp bounds are error-prone.",
                signals=("derived_value",),
            ),
        ),
        code="def message_search_time_window(anchor_timestamp: float, lookback_days: int) -> dict:\n    return {}\n",
    )
    entry = RegistryEntry.accepted(
        tool,
        ValidationResult(
            accepted=True,
            errors=(),
            source_example_count=1,
            held_out_check_count=1,
            runtime_smoke_passed=True,
        ),
        birth_scenario="search_message_with_recency_oldest",
    )

    docstring = _google_docstring(entry)

    assert "Use when:" in docstring
    assert "latest message" in docstring
    assert "Do not use when:" in docstring
    assert "creation_timestamp_lowerbound" in docstring
    assert "Then pass the relevant returned fields into search_messages." in docstring
    assert "should_call_add_reminder" not in docstring
    assert "search_messages_kwargs" not in docstring
