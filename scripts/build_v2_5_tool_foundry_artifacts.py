#!/usr/bin/env python3
# mypy: ignore-errors
"""Build V2.5 blocker-aware gap atlas, feasibility screen, and candidate batch."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sage_ts.adapters.openai_agent_adapter import OpenAIChatAdapter
from sage_ts.config.splits import ScenarioRecord, scenario_records
from sage_ts.evaluation.task_strata import (
    base_task_family,
    cohort_policy_report,
    expected_birth_opportunities,
    expected_helper_fit,
)
from sage_ts.generation.prompt_cache import PromptCache
from sage_ts.generation.tool_generator import ToolGenerationRequest, ToolGenerator
from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily
from sage_ts.registry.manifest import RegistryEntry
from sage_ts.registry.store import RegistryStore
from sage_ts.validation.live_candidate_check import run_lightweight_live_candidate_check
from sage_ts.validation.sandbox_validator import ToolExample, validate_generated_tool

BEST3_REGISTRY = Path("artifacts/registry_frozen_best3_claim/registry_manifest.json")
BEST3_TOOLS = {
    "relative_day_time_to_timestamp",
    "resolve_search_window_or_bounds",
    "select_record_by_timestamp_extreme",
}

SOURCES: dict[str, Path] = {
    "formal100_best3": Path(
        "outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/"
        "validate_100_20260504_050428/paired_comparison.json"
    ),
    "formal250_best3": Path(
        "outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/"
        "validate_250_20260504_052222/paired_comparison.json"
    ),
    "formal500_best3": Path(
        "outputs/v2_1_formal500_best3_parallel_20260504_232126/"
        "full_benchmark_20260504_232130/paired_comparison.json"
    ),
    "formal1032_best3": Path(
        "outputs/v2_1_formal1000_best3_full_20260505_004901/"
        "full_benchmark_20260505_004905/paired_comparison.json"
    ),
    "robustness60_best3": Path(
        "outputs/v2_best3_robustness60_clean_20260504_070424/"
        "mechanism_40_20260504_070441/paired_comparison.json"
    ),
    "best4_ablation_best3": Path(
        "outputs/v2_2_best4_ablation60_best3_20260506_075831/"
        "mechanism_60_20260506_075938/paired_comparison.json"
    ),
    "best4_frozen100": Path(
        "outputs/v2_2_best4_frozen100_20260506_075831/"
        "validate_100_20260506_084140/paired_comparison.json"
    ),
}

PARKED_MECHANISMS: dict[str, dict[str, str]] = {
    "dependency_precondition": {
        "blocker": "adoption/value/safety failure",
        "evidence": "V2.0 natural calls 0; force-call called-subset negative with side-effect risk.",
    },
    "visible_record_selector": {
        "blocker": "adoption failure",
        "evidence": "V2.2 selector exposed after routing repair but natural calls stayed 0/16.",
    },
    "selected_record_side_effect_prep": {
        "blocker": "callability/value/safety failure",
        "evidence": "V2.1 force-call mixed/negative; selected-record-only prep brittle.",
    },
    "recency_action_selector": {
        "blocker": "value failure",
        "evidence": "V2.1 confirmation called-subset outcome negative despite callability repair.",
    },
    "stock_symbol_extraction": {
        "blocker": "value failure",
        "evidence": "V2.2 fair-chance natural calls 4/4 but called-subset outcome negative.",
    },
    "broad_constraint_action_planner": {
        "blocker": "safety/value failure",
        "evidence": "V2.3 force-call harmful with side-effect incidents.",
    },
    "broad_external_service_answer_extraction": {
        "blocker": "value failure",
        "evidence": "V2.4 extract_service_answer_field called 5 times but called-subset outcome -0.1804.",
    },
    "temperature_unit_answer_resolution": {
        "blocker": "value failure after callability repair",
        "evidence": "V2.5 scalar resolve_temperature_answer_unit was naturally called 5/8 visible positives, but called-subset outcome was -0.1428.",
    },
    "location_field_answer_resolution": {
        "blocker": "canonical-only/value failure after fair callability test",
        "evidence": "V2.5 resolve_location_lookup_field was valid and force-called 4/4 after lookup, but called-subset outcome delta was 0.0 while canonical improved; address backend output differed from target and phone answer was reformatted by the actor.",
    },
    "days_between_calendar_distance": {
        "blocker": "non-additive over best3",
        "evidence": "V2.2 Best4 frozen100 underperformed best3.",
    },
}

DEFERRED_MICRO_POSITIVE_MECHANISMS: dict[str, dict[str, str]] = {
    "distance_answer_resolution": {
        "status": "micro-positive narrow candidate",
        "evidence": "V2.5 format_calculated_distance_km was called 4/4 on relevant positives, VNC 0, called-subset outcome +0.5556, and best3+distance beat best3 by +0.0447 on the same micro manifest. Coverage is too narrow to close the gap alone.",
    }
}

FAILED_CANDIDATE_DESIGNS: dict[str, dict[str, str]] = {
    "direct_contact_action_kwargs_preparer": {
        "blocker": "callability/value/safety failure for dict-payload interface",
        "evidence": "V2.5 force-call diagnostic called prepare_direct_contact_action_kwargs 8/8, but the actor supplied {}, producing missing_required_helper_inputs; called-subset outcome was -0.1155 and one side-effect preservation incident was reported.",
        "next_material_repair": "Try a materially different flat-scalar interface rather than action_payload: dict.",
    }
}

_SCENARIOS: list[ScenarioRecord] | None = None


@dataclass(frozen=True)
class CandidateDesign:
    design_id: str
    cluster_id: str
    tool_name: str
    design_type: str
    allowed_family: str
    deterministic_value: int
    input_simplicity: int
    natural_adoption_likelihood: int
    side_effect_safety: int
    negative_case_safety: int
    expected_additive_value: int
    canonical_only_risk: int
    best3_duplication_risk: int
    visible_not_called_pollution_risk: int
    expected_direct_route_advantage: str
    likely_direct_base_tool_route: str
    observation: str
    validation_examples: tuple[ToolExample, ...]
    scenario_prefixes: tuple[str, ...]
    negative_prefixes: tuple[str, ...]

    @property
    def feasibility_score(self) -> int:
        return (
            self.deterministic_value * 4
            + self.input_simplicity * 3
            + self.natural_adoption_likelihood * 3
            + self.side_effect_safety * 3
            + self.negative_case_safety * 2
            + self.expected_additive_value * 4
            - self.canonical_only_risk * 3
            - self.best3_duplication_risk * 4
            - self.visible_not_called_pollution_risk * 3
        )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _records() -> list[ScenarioRecord]:
    global _SCENARIOS
    if _SCENARIOS is None:
        _SCENARIOS = list(scenario_records())
    return _SCENARIOS


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _cluster_id(scenario: str) -> str:
    name = scenario.lower()
    if set(expected_helper_fit(scenario)) & BEST3_TOOLS:
        return "best3_covered"
    if name.startswith(("find_days_till_holiday", "find_thanksgiving_timestamp")):
        return "days_between_calendar_distance"
    if name.startswith("find_stock_symbol_with_company_name"):
        return "stock_symbol_extraction"
    if any(token in name for token in ("low_battery", "wifi_off", "cellular_off")):
        return "dependency_precondition"
    if name.startswith(
        (
            "modify_contact_with_message_recency",
            "modify_reminder_with_recency_latest",
            "remove_reminder_with_recency_latest",
        )
    ):
        return "recency_action_selector"
    if name.startswith(
        (
            "remove_contact_by_phone",
            "search_phone_number_with_name",
            "search_relationship_with_phone_number",
            "search_sender_phone_number_with_content",
            "search_name_with_relationship",
            "update_contact_relationship_with_relationship",
        )
    ):
        return "visible_record_selector"
    if "insufficient_information" in name:
        return "insufficient_information_or_clarification"
    if name.startswith(("find_temperature_f_with_location", "find_temperature")):
        return "temperature_unit_answer_resolution"
    if name.startswith("find_distance_with_location_name"):
        return "distance_answer_resolution"
    if name.startswith(("convert_currency", "convert_currency_canonicalize")):
        return "currency_answer_normalization"
    if name.startswith(
        ("find_address_with_lat_lon", "find_phone_number_with_location_name")
    ):
        return "location_field_answer_resolution"
    if name.startswith(
        (
            "add_contact",
            "send_message",
            "remove_contact_with_id",
            "update_contact_with_id",
        )
    ):
        return "direct_side_effect_no_helper"
    return "other_no_current_helper_fit"


def _read_comparison_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source, path in SOURCES.items():
        if not path.exists():
            continue
        for row in _load_json(path).get("deltas", []):
            scenario = str(row.get("scenario"))
            candidate_outcome = row.get("candidate_outcome_similarity")
            outcome_delta = row.get("outcome_delta")
            rows.append(
                {
                    "source": source,
                    "scenario": scenario,
                    "base_family": base_task_family(scenario),
                    "cluster_id": _cluster_id(scenario),
                    "canonical_delta": row.get("delta"),
                    "outcome_delta": outcome_delta,
                    "candidate_outcome_similarity": candidate_outcome,
                    "control_outcome_similarity": row.get("control_outcome_similarity"),
                    "candidate_failed": isinstance(candidate_outcome, (int, float))
                    and float(candidate_outcome) < 0.75,
                    "outcome_regression": isinstance(outcome_delta, (int, float))
                    and float(outcome_delta) < -1e-9,
                    "expected_helper_fit": expected_helper_fit(scenario),
                    "expected_birth_opportunities": expected_birth_opportunities(
                        scenario
                    ),
                }
            )
    return rows


def _designs() -> list[CandidateDesign]:
    temp_examples = (
        ToolExample(
            {
                "temperature_value": 21.5,
                "source_unit": "Celsius",
                "target_unit": "Fahrenheit",
                "precision": 1,
            },
            {
                "answer_value": "70.7",
                "answer_unit": "Fahrenheit",
                "source_value": 21.5,
                "source_unit": "Celsius",
                "abstain_reason": "",
            },
        ),
        ToolExample(
            {
                "temperature_value": 68.0,
                "source_unit": "Fahrenheit",
                "target_unit": "Fahrenheit",
                "precision": 1,
            },
            {
                "answer_value": "68.0",
                "answer_unit": "Fahrenheit",
                "source_value": 68.0,
                "source_unit": "Fahrenheit",
                "abstain_reason": "",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "temperature_value": 21.5,
                "source_unit": "Celsius",
                "target_unit": "Kelvin",
                "precision": 1,
            },
            {
                "answer_value": "",
                "answer_unit": "",
                "source_value": 21.5,
                "source_unit": "Celsius",
                "abstain_reason": "invalid_target_unit",
            },
            negative_applicability=True,
        ),
    )
    temp_args_examples = (
        ToolExample(
            {
                "weather_payload": {
                    "current_temperature": 21.5,
                    "temperature_unit": "Celsius",
                },
                "target_unit": "Fahrenheit",
            },
            {
                "downstream_tool_name": "unit_conversion",
                "downstream_tool_kwargs": {
                    "amount": 21.5,
                    "from_unit": "Celsius",
                    "to_unit": "Fahrenheit",
                },
                "should_call_tool": True,
                "abstain_reason": "",
            },
        ),
        ToolExample(
            {
                "weather_payload": {"temperature": 4.0, "temperature_unit": "Celsius"},
                "target_unit": "Fahrenheit",
            },
            {
                "downstream_tool_name": "unit_conversion",
                "downstream_tool_kwargs": {
                    "amount": 4.0,
                    "from_unit": "Celsius",
                    "to_unit": "Fahrenheit",
                },
                "should_call_tool": True,
                "abstain_reason": "",
            },
            held_out=True,
        ),
        ToolExample(
            {"weather_payload": {"humidity": 40}, "target_unit": "Fahrenheit"},
            {
                "downstream_tool_name": "",
                "downstream_tool_kwargs": {},
                "should_call_tool": False,
                "abstain_reason": "missing_temperature",
            },
            negative_applicability=True,
        ),
    )
    distance_examples = (
        ToolExample(
            {"distance_km": 67.856, "target_unit": "", "precision": 2},
            {
                "answer_value": "67.86",
                "answer_unit": "kilometers",
                "source_unit": "kilometers",
                "abstain_reason": "",
            },
        ),
        ToolExample(
            {"distance_km": 1.609344, "target_unit": "miles", "precision": 2},
            {
                "answer_value": "1.00",
                "answer_unit": "miles",
                "source_unit": "kilometers",
                "abstain_reason": "",
            },
            held_out=True,
        ),
        ToolExample(
            {"distance_km": None, "target_unit": "kilometers", "precision": 2},
            {
                "answer_value": "",
                "answer_unit": "",
                "source_unit": "kilometers",
                "abstain_reason": "missing_distance_km",
            },
            negative_applicability=True,
        ),
    )
    currency_examples = (
        ToolExample(
            {"converted_amount": 123.456, "currency_code": "EUR", "precision": 2},
            {"answer_value": "123.46", "answer_unit": "EUR", "abstain_reason": ""},
        ),
        ToolExample(
            {"converted_amount": 50.0, "currency_code": "JPY", "precision": 0},
            {"answer_value": "50", "answer_unit": "JPY", "abstain_reason": ""},
            held_out=True,
        ),
        ToolExample(
            {"converted_amount": 0.0, "currency_code": "", "precision": 2},
            {
                "answer_value": "",
                "answer_unit": "",
                "abstain_reason": "missing_amount_or_currency",
            },
            negative_applicability=True,
        ),
    )
    location_field_examples = (
        ToolExample(
            {
                "location_payload": {
                    "result": "Apple Park 1 Apple Park Way Cupertino, CA 95014 United States",
                },
                "requested_field": "address",
            },
            {
                "answer_value": "Apple Park 1 Apple Park Way Cupertino, CA 95014 United States",
                "answer_field": "address",
                "abstain_reason": "",
            },
        ),
        ToolExample(
            {
                "location_payload": {
                    "phone_number": "+14089961010",
                    "name": "Apple Park",
                },
                "requested_field": "phone_number",
            },
            {
                "answer_value": "+14089961010",
                "answer_field": "phone_number",
                "abstain_reason": "",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "location_payload": {"name": "Apple Park"},
                "requested_field": "phone_number",
            },
            {
                "answer_value": "",
                "answer_field": "phone_number",
                "abstain_reason": "missing_requested_field",
            },
            negative_applicability=True,
        ),
    )
    direct_side_effect_examples = (
        ToolExample(
            {
                "action_payload": {
                    "action_type": "add_contact",
                    "name": "Stephen Sondheim",
                    "phone_number": "+19876543210",
                }
            },
            {
                "downstream_tool_name": "add_contact",
                "downstream_tool_kwargs": {
                    "name": "Stephen Sondheim",
                    "phone_number": "+19876543210",
                },
                "should_call_tool": True,
                "abstain_reason": "",
            },
        ),
        ToolExample(
            {
                "action_payload": {
                    "action_type": "update_contact",
                    "person_id": "550e8400-e29b-41d4-a716-446655440000",
                    "phone_number": "+19876543210",
                }
            },
            {
                "downstream_tool_name": "modify_contact",
                "downstream_tool_kwargs": {
                    "person_id": "550e8400-e29b-41d4-a716-446655440000",
                    "phone_number": "+19876543210",
                },
                "should_call_tool": True,
                "abstain_reason": "",
            },
            held_out=True,
        ),
        ToolExample(
            {
                "action_payload": {
                    "action_type": "send_message",
                    "phone_number": "+12453344098",
                    "content": "How's the new album coming along",
                }
            },
            {
                "downstream_tool_name": "send_message_with_phone_number",
                "downstream_tool_kwargs": {
                    "phone_number": "+12453344098",
                    "content": "How's the new album coming along",
                },
                "should_call_tool": True,
                "abstain_reason": "",
            },
            held_out=True,
        ),
        ToolExample(
            {"action_payload": {"action_type": "add_contact", "name": "No Phone"}},
            {
                "downstream_tool_name": "",
                "downstream_tool_kwargs": {},
                "should_call_tool": False,
                "abstain_reason": "missing_required_fields",
            },
            negative_applicability=True,
        ),
    )
    return [
        CandidateDesign(
            design_id="temperature_unit_answer_resolver",
            cluster_id="temperature_unit_answer_resolution",
            tool_name="resolve_temperature_answer_unit",
            design_type="answer-only scalar calculator",
            allowed_family=str(ToolFamily.DERIVED_VALUE_CALCULATOR),
            deterministic_value=5,
            input_simplicity=4,
            natural_adoption_likelihood=3,
            side_effect_safety=5,
            negative_case_safety=4,
            expected_additive_value=4,
            canonical_only_risk=2,
            best3_duplication_risk=0,
            visible_not_called_pollution_risk=2,
            expected_direct_route_advantage="Avoids manual Celsius/Fahrenheit conversion and answer formatting after visible weather payloads.",
            likely_direct_base_tool_route="search_location_around_lat_lon -> search_weather_around_lat_lon -> unit_conversion -> answer",
            observation=(
                "Design a deterministic answer-only helper named resolve_temperature_answer_unit. It must be easy for the acting model to call after search_weather_around_lat_lon returns a visible weather dictionary. Use scalar inputs, not an opaque required payload: temperature_value: float, source_unit: str, target_unit: str, and precision: int. The acting model should read the appropriate visible weather scalar first, such as current_temperature, min_temperature, max_temperature, average_temperature, or perceived_temperature, then call this helper with that scalar and the visible temperature_unit. The helper converts Celsius<->Fahrenheit itself when target_unit requests the other unit and returns exactly answer_value, answer_unit, source_value, source_unit, abstain_reason. Use the requested precision for converted Fahrenheit/Celsius values and preserve no final side effects. This materially repairs V2.4 broad extraction failure by doing the missing unit resolution, not merely copying a raw Celsius field."
                " The spec must list search_weather_around_lat_lon in required_original_tool_calls because the weather scalar must still come from that original ToolSandbox search. It may intentionally replace the intermediate unit_conversion milestone; set canonical_route_substitution_risk='medium', expected_milestone_calls_replaced=['unit_conversion'], and explain that final-state safety is unaffected because this is answer-only with no side effects."
            ),
            validation_examples=temp_examples,
            scenario_prefixes=("find_temperature_f_with_location", "find_temperature"),
            negative_prefixes=(
                "find_temperature_f_with_location_insufficient_information",
                "find_current_city_insufficient_information",
                "add_contact_with_name_and_phone_number",
            ),
        ),
        CandidateDesign(
            design_id="temperature_conversion_args_preparer",
            cluster_id="temperature_unit_answer_resolution",
            tool_name="prepare_temperature_conversion_args",
            design_type="argument preparer for canonical unit conversion",
            allowed_family=str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),
            deterministic_value=4,
            input_simplicity=4,
            natural_adoption_likelihood=3,
            side_effect_safety=5,
            negative_case_safety=4,
            expected_additive_value=3,
            canonical_only_risk=0,
            best3_duplication_risk=0,
            visible_not_called_pollution_risk=2,
            expected_direct_route_advantage="Prepares correct unit_conversion kwargs from visible weather payloads while preserving the original unit_conversion call.",
            likely_direct_base_tool_route="search_weather_around_lat_lon -> manually construct unit_conversion args",
            observation=(
                "Design a deterministic preparation helper named prepare_temperature_conversion_args. It accepts weather_payload: dict and target_unit: str. It must extract current_temperature or temperature and source unit from a visible weather payload, return downstream_tool_name='unit_conversion', downstream_tool_kwargs with amount/from_unit/to_unit, should_call_tool, and abstain_reason. It must preserve unit_conversion and search_weather_around_lat_lon as original ToolSandbox calls and never answer directly."
            ),
            validation_examples=temp_args_examples,
            scenario_prefixes=("find_temperature_f_with_location",),
            negative_prefixes=(
                "find_temperature_f_with_location_insufficient_information",
                "find_current_city_insufficient_information",
                "add_contact_with_name_and_phone_number",
            ),
        ),
        CandidateDesign(
            design_id="distance_answer_km_formatter",
            cluster_id="distance_answer_resolution",
            tool_name="format_calculated_distance_km",
            design_type="unit-safe scalar answer formatter",
            allowed_family=str(ToolFamily.DERIVED_VALUE_CALCULATOR),
            deterministic_value=3,
            input_simplicity=5,
            natural_adoption_likelihood=3,
            side_effect_safety=5,
            negative_case_safety=4,
            expected_additive_value=2,
            canonical_only_risk=2,
            best3_duplication_risk=0,
            visible_not_called_pollution_risk=2,
            expected_direct_route_advantage="Formats calculate_lat_lon_distance output as kilometers by default and only converts units when explicitly requested, preventing freeform-unit mistakes.",
            likely_direct_base_tool_route="search_lat_lon/search_location_around_lat_lon -> calculate_lat_lon_distance -> answer",
            observation=(
                "Design a deterministic unit-safe answer formatter named format_calculated_distance_km. It accepts distance_km: float, target_unit: str, and precision: int. The distance_km input is the visible scalar returned by the original ToolSandbox calculate_lat_lon_distance tool, whose output unit is kilometers. Do not accept a freeform source unit. Default or normalize target_unit to kilometers when target_unit is blank/None or when the user did not explicitly request miles; convert to miles only when target_unit is miles/mi. Return exactly answer_value, answer_unit, source_unit, and abstain_reason. answer_value must be a fixed-decimal string using the requested precision, including trailing zeros when precision requires them; do not use str(round(...)) for the final string. If distance_km is None or cannot be parsed, return answer_value='', answer_unit='', source_unit='kilometers', abstain_reason='missing_distance_km'. If target_unit is unsupported after blank/None has been normalized to kilometers, abstain_reason='unsupported_target_unit'. The helper must not call location services, must not compute distance itself, and must never answer insufficient-information tasks where current location or target location is unavailable. Include positive_triggers for calculate_lat_lon_distance result visible and find_distance_with_location_name tasks. Include negative_triggers for insufficient_information, current_location_unavailable, missing_distance_km, and distance request without calculated distance. The spec must list calculate_lat_lon_distance in required_original_tool_calls because the distance scalar must still come from that original ToolSandbox calculation. Set canonical_route_substitution_risk='none' and expected_milestone_calls_replaced=[] because the helper preserves the canonical distance calculation and only formats/converts the final answer."
            ),
            validation_examples=distance_examples,
            scenario_prefixes=("find_distance_with_location_name",),
            negative_prefixes=(
                "find_distance_with_location_name_insufficient_information",
                "get_wifi",
                "add_contact_with_name_and_phone_number",
            ),
        ),
        CandidateDesign(
            design_id="currency_answer_normalizer",
            cluster_id="currency_answer_normalization",
            tool_name="normalize_currency_answer",
            design_type="scalar answer formatter",
            allowed_family=str(ToolFamily.DERIVED_VALUE_CALCULATOR),
            deterministic_value=3,
            input_simplicity=5,
            natural_adoption_likelihood=3,
            side_effect_safety=5,
            negative_case_safety=4,
            expected_additive_value=1,
            canonical_only_risk=2,
            best3_duplication_risk=0,
            visible_not_called_pollution_risk=2,
            expected_direct_route_advantage="Formats visible convert_currency output with correct currency code and precision.",
            likely_direct_base_tool_route="convert_currency -> answer",
            observation=(
                "Design a deterministic answer formatter named normalize_currency_answer. It accepts converted_amount: float, currency_code: str, and precision: int. It returns answer_value, answer_unit, and abstain_reason. It must only format visible conversion output and must not call currency services or execute side effects."
            ),
            validation_examples=currency_examples,
            scenario_prefixes=("convert_currency", "convert_currency_canonicalize"),
            negative_prefixes=(
                "get_wifi",
                "add_contact_with_name_and_phone_number",
                "find_current_city_insufficient_information",
            ),
        ),
        CandidateDesign(
            design_id="location_field_answer_resolver",
            cluster_id="location_field_answer_resolution",
            tool_name="resolve_location_lookup_field",
            design_type="narrow visible payload field resolver",
            allowed_family=str(ToolFamily.DERIVED_VALUE_CALCULATOR),
            deterministic_value=4,
            input_simplicity=4,
            natural_adoption_likelihood=4,
            side_effect_safety=5,
            negative_case_safety=4,
            expected_additive_value=4,
            canonical_only_risk=1,
            best3_duplication_risk=0,
            visible_not_called_pollution_risk=2,
            expected_direct_route_advantage=(
                "Extracts only address or phone-number fields from visible location "
                "lookup payloads, avoiding broad service-answer extraction errors."
            ),
            likely_direct_base_tool_route=(
                "search_lat_lon/search_location_around_lat_lon -> manually identify "
                "address or phone field -> answer"
            ),
            observation=(
                "Design a deterministic answer-only helper named resolve_location_lookup_field. "
                "It accepts location_payload: dict and requested_field: str. The runtime may "
                "autofill location_payload from the latest original lookup trace; search_lat_lon "
                "returns a string and is bridged as {'result': address_text}, while "
                "search_location_around_lat_lon returns a list of dictionaries and is bridged to "
                "the first visible result dictionary. It must support only requested_field values "
                "address and phone_number. The acting model should call it after the original "
                "ToolSandbox search_lat_lon or search_location_around_lat_lon tool returns a "
                "visible result and pass requested_field='address' or 'phone_number'. It returns "
                "exactly answer_value, answer_field, abstain_reason. For address it must check "
                "address, formatted_address, full_address, and result string fields. For "
                "phone_number it must check phone_number, phone, formatted_phone_number, "
                "formatted_phone, and international_phone_number fields. Do not test only "
                "`requested_field in location_payload`; map requested fields through the alias "
                "lists first. It must abstain on missing payload, unsupported "
                "field, missing requested field, multiple conflicting values, or "
                "insufficient-information tasks. It must not call location services itself, "
                "must not fabricate fields, and must not execute side effects. Include positive "
                "triggers for find_address_with_lat_lon and find_phone_number_with_location_name "
                "after a visible location lookup result. Include negative triggers for "
                "insufficient_information, missing_location_payload, unsupported_requested_field, "
                "non-location-answer tasks, and ambiguous/conflicting field values. The spec "
                "must list search_lat_lon and search_location_around_lat_lon in "
                "required_original_tool_calls because the payload must still come from original "
                "ToolSandbox lookup calls. This materially repairs the parked broad "
                "extract_service_answer_field design by limiting scope to two concrete fields "
                "and refusing all other service-answer extraction."
            ),
            validation_examples=location_field_examples,
            scenario_prefixes=(
                "find_address_with_lat_lon",
                "find_phone_number_with_location_name",
            ),
            negative_prefixes=(
                "find_current_city_insufficient_information",
                "find_distance_with_location_name_insufficient_information",
                "get_wifi",
            ),
        ),
        CandidateDesign(
            design_id="direct_contact_action_kwargs_preparer",
            cluster_id="direct_side_effect_no_helper",
            tool_name="prepare_direct_contact_action_kwargs",
            design_type="scalar side-effect kwargs preparer",
            allowed_family=str(ToolFamily.COMPOSITE_WORKFLOW_HELPER),
            deterministic_value=4,
            input_simplicity=3,
            natural_adoption_likelihood=3,
            side_effect_safety=4,
            negative_case_safety=4,
            expected_additive_value=3,
            canonical_only_risk=1,
            best3_duplication_risk=1,
            visible_not_called_pollution_risk=2,
            expected_direct_route_advantage=(
                "Compiles explicit user-provided scalar action fields into the exact "
                "original ToolSandbox side-effect kwargs while preserving the final "
                "side-effect call."
            ),
            likely_direct_base_tool_route=(
                "parse user scalars -> choose add/modify/remove/send side-effect tool "
                "-> construct kwargs -> call original side-effect tool"
            ),
            observation=(
                "Design a deterministic preparation helper named "
                "prepare_direct_contact_action_kwargs. It accepts one flat dictionary "
                "input action_payload: dict containing user-visible scalar fields. It "
                "must support only these action_type values and aliases: add/add_contact, "
                "remove/remove_contact/delete by person_id, update/update_contact/"
                "modify_phone by person_id plus phone_number, and send/send_message by "
                "phone_number plus content. It returns exactly downstream_tool_name, "
                "downstream_tool_kwargs, should_call_tool, and abstain_reason. It must "
                "never call or execute add_contact, remove_contact, modify_contact, or "
                "send_message_with_phone_number. It only prepares kwargs and requires the "
                "acting model to call the returned original ToolSandbox tool next when "
                "should_call_tool is true. It must normalize phone numbers by preserving "
                "a leading plus sign and stripping spaces/dashes/parentheses. It must "
                "abstain on missing action_type, unsupported action, missing required "
                "fields, ambiguous payload, or insufficient-information tasks. It must "
                "not infer missing ids, names, phone numbers, or message content. This "
                "is materially different from the parked selected-record side-effect "
                "prep lane because it only handles direct scalar tasks where the user "
                "already supplied the target id/phone/name/content. Include positive "
                "triggers for add_contact_with_name_and_phone_number, "
                "remove_contact_with_id, update_contact_with_id_and_phone_number, and "
                "send_message_with_phone_number_and_content. Include negative triggers "
                "for selected-record-only workflows, missing scalar fields, "
                "insufficient_information, and relationship/recency selection tasks. "
                "The spec must list add_contact, remove_contact, modify_contact, and "
                "send_message_with_phone_number in both required_original_tool_calls and "
                "preserves_side_effect_tools."
            ),
            validation_examples=direct_side_effect_examples,
            scenario_prefixes=(
                "add_contact_with_name_and_phone_number",
                "remove_contact_with_id",
                "update_contact_with_id_and_phone_number",
                "send_message_with_phone_number_and_content",
            ),
            negative_prefixes=(
                "remove_contact_by_phone_no_search_contacts_insufficient_information",
                "send_message_with_recipient_name_no_search_tools_insufficient_information",
                "search_message_with_recency_latest",
                "find_current_city_insufficient_information",
            ),
        ),
    ]


def build_gap_atlas() -> dict[str, Any]:
    rows = _read_comparison_rows()
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        clusters[row["cluster_id"]].append(row)
    ranked = []
    design_by_cluster: dict[str, list[CandidateDesign]] = defaultdict(list)
    for design in _designs():
        design_by_cluster[design.cluster_id].append(design)
    for cluster, items in clusters.items():
        families = Counter(item["base_family"] for item in items)
        failures = [item for item in items if item["candidate_failed"]]
        regressions = [item for item in items if item["outcome_regression"]]
        no_fit = [item for item in items if not item["expected_helper_fit"]]
        prior = PARKED_MECHANISMS.get(cluster)
        deferred = DEFERRED_MICRO_POSITIVE_MECHANISMS.get(cluster)
        if prior is None and cluster == "best3_covered":
            prior = {
                "blocker": "best3-covered",
                "evidence": "Excluded from additive candidate search.",
            }
        candidate_designs = sorted(
            design_by_cluster.get(cluster, []),
            key=lambda d: d.feasibility_score,
            reverse=True,
        )
        status = (
            "candidate_ranked"
            if candidate_designs and prior is None and deferred is None
            else "deferred_micro_positive"
            if deferred is not None
            else "excluded_or_parked"
            if prior
            else "support_or_negative_not_primary"
        )
        score = (
            len(failures) * 3
            + len(regressions) * 4
            + len(no_fit) * 2
            + len(families) * 2
        )
        if candidate_designs:
            score += max(d.feasibility_score for d in candidate_designs)
        if status != "candidate_ranked":
            score -= 100
        ranked.append(
            {
                "cluster_id": cluster,
                "status": status,
                "scenario_count": len(items),
                "base_family_count": len(families),
                "base_families": dict(families.most_common()),
                "best3_failures": len(failures),
                "best3_regressions": len(regressions),
                "no_current_helper_fit_count": len(no_fit),
                "prior_blocker": prior,
                "deferred_candidate": deferred,
                "deterministic_intermediate_step": _intermediate_step(cluster),
                "likely_direct_base_tool_route": candidate_designs[
                    0
                ].likely_direct_base_tool_route
                if candidate_designs
                else "direct ToolSandbox route or no helper route",
                "why_helper_might_beat_direct_route": candidate_designs[
                    0
                ].expected_direct_route_advantage
                if candidate_designs
                else "No clear deterministic helper shape survived prior evidence.",
                "negative_and_ambiguity_cases": _negative_case_note(cluster),
                "candidate_design_options": [
                    asdict_with_score(design) for design in candidate_designs
                ],
                "additive_score": score,
                "worst_examples": sorted(
                    (
                        {
                            "source": item["source"],
                            "scenario": item["scenario"],
                            "outcome_delta": item["outcome_delta"],
                            "candidate_outcome_similarity": item[
                                "candidate_outcome_similarity"
                            ],
                        }
                        for item in items
                    ),
                    key=lambda item: float(item["candidate_outcome_similarity"] or 0),
                )[:10],
            }
        )
    ranked.sort(key=lambda item: float(item["additive_score"]), reverse=True)
    candidate_clusters = [
        item for item in ranked if item["status"] == "candidate_ranked"
    ]
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "sources": {key: str(path) for key, path in SOURCES.items()},
        "protected_best3_registry": str(BEST3_REGISTRY),
        "protected_best3_sha256": _sha256(BEST3_REGISTRY)
        if BEST3_REGISTRY.exists()
        else None,
        "parked_mechanisms": PARKED_MECHANISMS,
        "ranked_clusters": ranked,
        "candidate_clusters": candidate_clusters,
        "decision_label": "tool-foundry ready"
        if candidate_clusters
        else "no tool-suitable gap found",
        "shortfall_record_count": len(rows),
    }


def asdict_with_score(design: CandidateDesign) -> dict[str, Any]:
    payload = asdict(design)
    payload["feasibility_score"] = design.feasibility_score
    payload["validation_examples"] = [
        {
            "inputs": ex.inputs,
            "expected": ex.expected,
            "held_out": ex.held_out,
            "negative_applicability": ex.negative_applicability,
        }
        for ex in design.validation_examples
    ]
    return payload


def _intermediate_step(cluster: str) -> str:
    return {
        "temperature_unit_answer_resolution": "extract visible weather temperature, resolve requested unit, and format the answer",
        "distance_answer_resolution": "format visible distance scalar with safe precision and unit",
        "currency_answer_normalization": "format visible converted amount with target currency code",
        "location_field_answer_resolution": "extract an address or phone-number field from a visible location lookup payload",
        "direct_side_effect_no_helper": "compile explicit user-provided scalar action fields into original side-effect tool kwargs",
    }.get(cluster, "no simple deterministic intermediate isolated")


def _negative_case_note(cluster: str) -> str:
    return {
        "temperature_unit_answer_resolution": "insufficient location/weather payload, missing temperature field, non-temperature tasks",
        "distance_answer_resolution": "insufficient location, missing distance scalar, non-distance tasks",
        "currency_answer_normalization": "missing converted amount/currency code, non-currency tasks",
        "location_field_answer_resolution": "insufficient location payload, unsupported field, missing address/phone, non-location tasks",
        "direct_side_effect_no_helper": "missing action type, missing required scalar fields, selected-record-only workflows, insufficient-information side-effect tasks",
    }.get(cluster, "insufficient-information and unrelated no-helper cases")


def feasibility_payload(atlas: dict[str, Any]) -> dict[str, Any]:
    designs = sorted(_designs(), key=lambda d: d.feasibility_score, reverse=True)
    rows = []
    for design in designs:
        status = (
            "reject_exhausted_or_parked_cluster"
            if design.cluster_id in PARKED_MECHANISMS
            or design.cluster_id in DEFERRED_MICRO_POSITIVE_MECHANISMS
            or design.design_id in FAILED_CANDIDATE_DESIGNS
            else "advance_to_generation"
            if design.feasibility_score >= 35 and design.expected_additive_value >= 2
            else "reject_before_generation"
        )
        rows.append(
            {
                **asdict_with_score(design),
                "feasibility_decision": status,
                "failed_design": FAILED_CANDIDATE_DESIGNS.get(design.design_id),
            }
        )
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "atlas_decision": atlas["decision_label"],
        "candidate_designs": rows,
        "advanced_designs": [
            row
            for row in rows
            if row["feasibility_decision"] == "advance_to_generation"
        ],
        "decision_label": "candidate designs ready"
        if any(row["feasibility_decision"] == "advance_to_generation" for row in rows)
        else "needs new gap atlas",
    }


def _request_for_design(design: CandidateDesign) -> ToolGenerationRequest:
    examples = [
        {
            "inputs": example.inputs,
            "expected": example.expected,
            "held_out": example.held_out,
            "negative_applicability": example.negative_applicability,
        }
        for example in design.validation_examples
    ]
    return ToolGenerationRequest(
        scenario_name=design.scenario_prefixes[0],
        observation=design.observation,
        allowed_families=(design.allowed_family,),
        validation_examples=tuple(examples),
        suggested_tool_name=design.tool_name,
        inadequacy_evidence={
            "summary": design.observation,
            "signals": [
                "visible_raw_data_lacking_deterministic_transform",
                "v2_5_foundry_candidate_design",
            ],
            "failed_tool_calls": [],
            "repeated_failed_tool_calls": [],
            "visible_data_gaps": [design.expected_direct_route_advantage],
            "planner_failures": [
                "direct route requires brittle manual intermediate reasoning"
            ],
            "final_answer_route_mismatch": design.canonical_only_risk > 0,
        },
        shortfall_cluster_context={
            "cluster_id": design.cluster_id,
            "candidate_design_type": design.design_type,
            "non_diagnostic_birth_allowed": True,
            "distinct_base_task_families": 2,
            "base_task_families": list(design.scenario_prefixes),
            "prior_failed_designs": [
                PARKED_MECHANISMS["broad_external_service_answer_extraction"][
                    "evidence"
                ]
            ],
            "material_repair": design.expected_direct_route_advantage,
        },
    )


def generate_candidate_batch(
    feasibility: dict[str, Any], out_dir: Path, model: str
) -> dict[str, Any]:
    cache = PromptCache(Path("artifacts/prompt_cache") / "v2_5_tool_foundry")
    generator = ToolGenerator(OpenAIChatAdapter(model=model), cache)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    generated_payloads: list[dict[str, Any]] = []
    registry_dir = out_dir / "candidate_batch_registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BEST3_REGISTRY, registry_dir / "registry_manifest.json")
    store = RegistryStore(registry_dir)
    advanced = feasibility["advanced_designs"][:3]
    for row in advanced:
        design = next(item for item in _designs() if item.design_id == row["design_id"])
        request = _request_for_design(design)
        try:
            tool = generator.generate(request)
        except Exception as exc:
            rejected.append(
                {
                    "design_id": design.design_id,
                    "tool_name": design.tool_name,
                    "stage": "generation",
                    "errors": [f"{type(exc).__name__}:{exc}"],
                }
            )
            continue
        generated_payloads.append(
            {
                "design_id": design.design_id,
                "attempt": "initial",
                "tool": tool.to_json(),
            }
        )
        validation = validate_generated_tool(tool, design.validation_examples)
        live = run_lightweight_live_candidate_check(tool, design.validation_examples)
        repair_errors = tuple(
            list(validation.errors) + list(live.errors) + _strict_registry_errors(tool)
        )
        repaired = False
        if repair_errors:
            try:
                repaired_tool = generator.repair(request, tool, repair_errors)
                generated_payloads.append(
                    {
                        "design_id": design.design_id,
                        "attempt": "repair_1",
                        "tool": repaired_tool.to_json(),
                        "repair_errors": list(repair_errors),
                    }
                )
                repaired_validation = validate_generated_tool(
                    repaired_tool, design.validation_examples
                )
                repaired_live = run_lightweight_live_candidate_check(
                    repaired_tool, design.validation_examples
                )
                if repaired_validation.accepted and repaired_live.accepted:
                    repaired_errors = _strict_registry_errors(repaired_tool)
                    if repaired_errors:
                        rejected.append(
                            {
                                "design_id": design.design_id,
                                "tool_name": repaired_tool.spec.tool_name,
                                "stage": "repair",
                                "errors": repaired_errors,
                                "initial_errors": list(repair_errors),
                            }
                        )
                        continue
                    tool = repaired_tool
                    validation = repaired_validation
                    live = repaired_live
                    repaired = True
            except Exception as exc:
                rejected.append(
                    {
                        "design_id": design.design_id,
                        "tool_name": design.tool_name,
                        "stage": "repair",
                        "errors": [f"{type(exc).__name__}:{exc}"],
                        "initial_errors": list(repair_errors),
                    }
                )
                continue
        strict_errors = _strict_registry_errors(tool)
        if validation.accepted and live.accepted and not strict_errors:
            entry = RegistryEntry.accepted(
                tool, validation, birth_scenario=design.scenario_prefixes[0]
            )
            store.put(entry)
            accepted.append(
                {
                    "design_id": design.design_id,
                    "tool_name": tool.spec.tool_name,
                    "family": tool.spec.family.value,
                    "validation": validation.__dict__,
                    "live_check": live.to_json(),
                    "feasibility_score": design.feasibility_score,
                    "repair_attempted": bool(repair_errors),
                    "repair_succeeded": repaired,
                }
            )
        else:
            rejected.append(
                {
                    "design_id": design.design_id,
                    "tool_name": tool.spec.tool_name,
                    "stage": "validation",
                    "validation": validation.__dict__,
                    "live_check": live.to_json(),
                    "errors": list(validation.errors)
                    + list(live.errors)
                    + strict_errors,
                    "repair_attempted": bool(repair_errors),
                }
            )
    write_json(out_dir / "generated_candidates.json", generated_payloads)
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "model": model,
        "registry_dir": str(registry_dir),
        "registry_manifest": str(registry_dir / "registry_manifest.json"),
        "registry_sha256": _sha256(registry_dir / "registry_manifest.json"),
        "prompt_cache": cache.metrics(),
        "tools_proposed": len(advanced),
        "tools_accepted": len(accepted),
        "tools_rejected": len(rejected),
        "accepted": accepted,
        "rejected": rejected,
        "decision_label": "candidate batch generated"
        if accepted
        else "generation contract repair needed",
    }


def _strict_registry_errors(tool: GeneratedTool) -> list[str]:
    """Mirror claim-safety checks that must pass without experiment flags."""
    spec = tool.spec
    errors: list[str] = []
    if not (spec.preserves_side_effect_tools or spec.required_original_tool_calls):
        errors.append("missing_downstream_tool_preservation")
    if spec.family == ToolFamily.DERIVED_VALUE_CALCULATOR:
        calls = {
            *(item.strip() for item in spec.preserves_side_effect_tools),
            *(item.strip() for item in spec.required_original_tool_calls),
        }
        if not any(
            call.startswith(("search_", "calculate_", "convert_", "unit_conversion"))
            for call in calls
        ):
            errors.append("missing_downstream_original_tool_call")
    return errors


def _select_records(
    prefixes: tuple[str, ...],
    count: int,
    already: set[str],
    family_counts: Counter[str],
    include_insufficient: bool = False,
) -> list[ScenarioRecord]:
    candidates = [
        record
        for record in _records()
        if record.name.startswith(prefixes)
        and record.name not in already
        and (
            include_insufficient or "INSUFFICIENT_INFORMATION" not in record.categories
        )
    ]
    candidates.sort(key=lambda r: (base_task_family(r.name), r.name))
    selected: list[ScenarioRecord] = []
    for record in candidates:
        if len(selected) >= count:
            break
        family = base_task_family(record.name)
        if family_counts[family] >= 2:
            continue
        selected.append(record)
        already.add(record.name)
        family_counts[family] += 1
    if len(selected) != count:
        raise RuntimeError(
            f"Could only select {len(selected)} of {count} for {prefixes}"
        )
    return selected


def build_micro_manifest(design: CandidateDesign, summary_dir: Path) -> dict[str, Any]:
    already: set[str] = set()
    family_counts: Counter[str] = Counter()
    selected: list[ScenarioRecord] = []
    role_by_name: dict[str, str] = {}
    positive_count = (
        4
        if design.cluster_id
        in {"distance_answer_resolution", "location_field_answer_resolution"}
        else 8
    )
    for record in _select_records(
        design.scenario_prefixes, positive_count, already, family_counts
    ):
        selected.append(record)
        role_by_name[record.name] = "candidate_positive"
    support_prefixes = (
        "add_reminder_content_and_date_and_time",
        "search_reminder_with_recency_yesterday",
        "search_message_with_recency_latest",
        "add_contact_with_name_and_phone_number",
    )
    for record in _select_records(support_prefixes, 8, already, family_counts):
        selected.append(record)
        role_by_name[record.name] = "best3_or_known_helper_control"
    negative_prefixes = (
        *design.negative_prefixes,
        "find_current_city_insufficient_information",
        "find_temperature_f_with_location_insufficient_information",
    )
    negative_count = 20 - len(selected)
    for record in _select_records(
        negative_prefixes,
        negative_count,
        already,
        family_counts,
        include_insufficient=True,
    ):
        selected.append(record)
        role_by_name[record.name] = "negative_or_no_helper"
    categories_by_name = {record.name: record.categories for record in selected}
    diversity = cohort_policy_report(
        [record.name for record in selected],
        categories_by_name=categories_by_name,
        generation_enabled=False,
        registry_tool_count=4,
    )
    if diversity["quality_gate_status"] != "pass":
        raise RuntimeError(
            f"micro cohort quality failed: {diversity['quality_gate_failures']}"
        )
    manifest = {
        "manifest_type": "sage_v2_5_micro_value_test",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_design": design.design_id,
        "candidate_tool_name": design.tool_name,
        "splits": {"mechanism_40": [record.to_json() for record in selected]},
        "split_sizes": {"mechanism_40": len(selected)},
        "role_by_scenario": role_by_name,
        "cohort_diversity_report": diversity,
    }
    write_json(summary_dir / f"{design.tool_name}_micro_manifest.json", manifest)
    write_json(
        summary_dir / f"{design.tool_name}_micro_diversity_report.json", diversity
    )
    return manifest


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def write_reports(
    atlas: dict[str, Any],
    feasibility: dict[str, Any],
    batch: dict[str, Any],
    summary_dir: Path,
) -> None:
    rows = []
    for cluster in atlas["ranked_clusters"][:12]:
        rows.append(
            f"| `{cluster['cluster_id']}` | {cluster['status']} | {cluster['scenario_count']} | {cluster['base_family_count']} | {cluster['best3_failures']} | {cluster['best3_regressions']} | {cluster['no_current_helper_fit_count']} | {cluster['additive_score']} | {cluster.get('prior_blocker', {}).get('blocker', '') if cluster.get('prior_blocker') else ''} |"
        )
    Path("docs/sage_protocol/v2_5_blocker_gap_atlas_report.md").write_text(
        "# V2.5 Blocker-Aware Gap Atlas Report\n\n"
        "## Objective\n\nBuild a blocker-aware gap atlas from best3 and V2.x evidence, separating adoption, callability, value, and safety failures before spending on new runs.\n\n"
        "## Ranked Clusters\n\n"
        "| Cluster | Status | Scenarios | Families | Best3 failures | Best3 regressions | No-fit | Additive score | Prior blocker |\n"
        "|---|---|---:|---:|---:|---:|---:|---:|---|\n"
        + "\n".join(rows)
        + "\n\n## Candidate Design Options\n\n"
        + "\n".join(
            f"- `{d['tool_name']}` / `{d['design_type']}` in `{d['cluster_id']}`: score `{d['feasibility_score']}`, advantage: {d['expected_direct_route_advantage']}"
            for cluster in atlas["ranked_clusters"]
            for d in cluster.get("candidate_design_options", [])
        )
        + f"\n\n## Artifact\n\n- `{summary_dir / 'latest_gap_atlas.json'}`\n\n## Decision Label\n\n`{atlas['decision_label']}`\n",
        encoding="utf-8",
    )
    Path("docs/sage_protocol/v2_5_tool_feasibility_report.md").write_text(
        "# V2.5 Tool Feasibility Report\n\n"
        "## Objective\n\nScore candidate designs before generation to avoid repeating known adoption, callability, value, and safety failures.\n\n"
        "| Design | Cluster | Type | Score | Decision | Main advantage |\n|---|---|---|---:|---|---|\n"
        + "\n".join(
            f"| `{d['tool_name']}` | `{d['cluster_id']}` | `{d['design_type']}` | {d['feasibility_score']} | `{d['feasibility_decision']}` | {d['expected_direct_route_advantage']} |"
            for d in feasibility["candidate_designs"]
        )
        + f"\n\n## Decision Label\n\n`{feasibility['decision_label']}`\n",
        encoding="utf-8",
    )
    Path("docs/sage_protocol/v2_5_candidate_batch_generation_report.md").write_text(
        "# V2.5 Candidate Batch Generation Report\n\n"
        "## Objective\n\nGenerate and validate a small batch of candidate tools from the best feasibility-screened designs.\n\n"
        f"- Registry: `{batch.get('registry_manifest')}`\n"
        f"- Registry SHA-256: `{batch.get('registry_sha256')}`\n"
        f"- Tools proposed / accepted / rejected: `{batch['tools_proposed']} / {batch['tools_accepted']} / {batch['tools_rejected']}`\n"
        f"- Prompt cache: `{batch.get('prompt_cache')}`\n\n"
        "## Accepted\n\n"
        + (
            "\n".join(
                f"- `{item['tool_name']}` from `{item['design_id']}`"
                for item in batch["accepted"]
            )
            or "None"
        )
        + "\n\n## Rejected\n\n"
        + (
            "\n".join(
                f"- `{item.get('tool_name')}` from `{item['design_id']}`: `{item.get('errors')}`"
                for item in batch["rejected"]
            )
            or "None"
        )
        + f"\n\n## Decision Label\n\n`{batch['decision_label']}`\n",
        encoding="utf-8",
    )
    callability_decision = (
        "`candidate ready for micro-run`" if batch["accepted"] else "`candidate parked`"
    )
    callability_body = (
        "# V2.5 Callability Validation Report\n\n"
        "## Objective\n\nRun offline schema/static validation and lightweight live validation before any micro-run.\n\n"
        "## Accepted Candidates\n\n"
        + (
            "\n".join(
                f"- `{item['tool_name']}`: repair_attempted `{item.get('repair_attempted')}`, "
                f"repair_succeeded `{item.get('repair_succeeded')}`, validation `{item['validation']}`, live `{item['live_check']}`"
                for item in batch["accepted"]
            )
            or "None"
        )
        + "\n\n## Parked Or Rejected Candidates\n\n"
        + (
            "\n".join(
                f"- `{item.get('tool_name')}`: repair_attempted `{item.get('repair_attempted')}`, `{item.get('errors')}`"
                for item in batch["rejected"]
            )
            or "None"
        )
        + f"\n\n## Decision Label\n\n{callability_decision}\n"
    )
    Path("docs/sage_protocol/v2_5_callability_validation_report.md").write_text(
        callability_body,
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    parser.add_argument("--generate", action="store_true")
    parser.add_argument(
        "--model", default=os.environ.get("SAGE_TS_GENERATION_MODEL", "gpt-4o-mini")
    )
    args = parser.parse_args()
    summary_dir = Path("artifacts/summaries/v2_5_gap_atlas")
    run_dir = Path("artifacts/summaries") / f"v2_5_tool_foundry_{args.timestamp}"
    atlas = build_gap_atlas()
    feasibility = feasibility_payload(atlas)
    write_json(summary_dir / "latest_gap_atlas.json", atlas)
    write_json(run_dir / "feasibility.json", feasibility)
    batch = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "registry_manifest": None,
        "registry_sha256": None,
        "tools_proposed": len(feasibility["advanced_designs"][:3]),
        "tools_accepted": 0,
        "tools_rejected": 0,
        "accepted": [],
        "rejected": [],
        "decision_label": "candidate batch generated"
        if not args.generate
        else "generation contract repair needed",
    }
    if args.generate and feasibility["advanced_designs"]:
        batch = generate_candidate_batch(feasibility, run_dir, args.model)
        for item in batch["accepted"]:
            design = next(d for d in _designs() if d.design_id == item["design_id"])
            manifest = build_micro_manifest(design, run_dir)
            item["micro_manifest"] = str(
                run_dir / f"{design.tool_name}_micro_manifest.json"
            )
            item["micro_diversity_report"] = str(
                run_dir / f"{design.tool_name}_micro_diversity_report.json"
            )
            item["micro_quality_gate"] = manifest["cohort_diversity_report"][
                "quality_gate_status"
            ]
    write_json(run_dir / "candidate_batch_summary.json", batch)
    write_reports(atlas, feasibility, batch, run_dir)
    print(
        json.dumps(
            {
                "summary_dir": str(run_dir),
                "atlas_decision": atlas["decision_label"],
                "feasibility_decision": feasibility["decision_label"],
                "batch_decision": batch["decision_label"],
                "accepted": [item["tool_name"] for item in batch["accepted"]],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
