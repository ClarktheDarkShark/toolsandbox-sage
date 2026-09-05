# mypy: ignore-errors
import datetime as dt
import hashlib
import inspect
import json
from copy import deepcopy
from pathlib import Path

import polars as pl
import pytest

from sage_ts.evaluation.outcome_score import (
    _CONTRACT_PERTURBATION_SUFFIXES,
    _DYNAMIC_NUMERIC_SCENARIO_FAMILIES,
    _INFORMATION_ANSWER_BASE_CONTRACTS,
    _PINNED_RAPID_API_FIXTURE_SHA256,
    OUTCOME_EVALUATOR_VERSION,
    _build_state_outcome_matcher,
    _content_similarity,
    _match_state_outcomes,
    _numbers_in_text,
    compute_outcome_score,
    outcome_evaluator_manifest,
)
from tool_sandbox.cli.utils import resolve_scenarios
from tool_sandbox.common.evaluation import (
    Milestone,
    MilestoneMatcher,
    SnapshotConstraint,
    column_exact_match_similarity,
    guardrail_similarity,
    update_similarity,
)
from tool_sandbox.common.execution_context import (
    DatabaseNamespace,
    ExecutionContext,
    RoleType,
)
from tool_sandbox.common.tool_discovery import ToolBackend


def _scenario(name: str):
    return resolve_scenarios(
        desired_scenario_names=[name],
        preferred_tool_backend=ToolBackend.DEFAULT,
    )[name]


def _rollout_context(
    *agent_messages: str,
    prelude_agent_messages: tuple[str, ...] = (),
) -> ExecutionContext:
    execution_context = ExecutionContext()
    for content in prelude_agent_messages:
        execution_context.add_to_database(
            DatabaseNamespace.SANDBOX,
            [
                {
                    "sender": RoleType.AGENT,
                    "recipient": RoleType.USER,
                    "content": content,
                    "visible_to": [RoleType.USER],
                }
            ],
        )
    execution_context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.USER,
                "recipient": RoleType.AGENT,
                "content": "Publication benchmark request",
            }
        ],
    )
    for content in agent_messages:
        execution_context.add_to_database(
            DatabaseNamespace.SANDBOX,
            [
                {
                    "sender": RoleType.AGENT,
                    "recipient": RoleType.USER,
                    "content": content,
                }
            ],
        )
    return execution_context


def _score(
    scenario_name: str,
    execution_context: ExecutionContext,
):
    scenario = _scenario(scenario_name)
    return compute_outcome_score(
        scenario,
        execution_context,
        scenario_name=scenario_name,
    )


def _starting_context(scenario_name: str) -> ExecutionContext:
    return _scenario(scenario_name).starting_context


def _add_agent_message(
    execution_context: ExecutionContext,
    content: str,
    *,
    recipient: RoleType = RoleType.USER,
) -> None:
    execution_context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.AGENT,
                "recipient": recipient,
                "content": content,
            }
        ],
    )


def _add_user_message(
    execution_context: ExecutionContext,
    content: str,
) -> None:
    execution_context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.USER,
                "recipient": RoleType.AGENT,
                "content": content,
            }
        ],
    )


def _add_tool_result(
    execution_context: ExecutionContext,
    tool_name: str,
    result,
    *,
    arguments=None,
) -> None:
    execution_context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.EXECUTION_ENVIRONMENT,
                "recipient": RoleType.AGENT,
                "content": json.dumps(result),
                "tool_trace": [
                    json.dumps(
                        {
                            "tool_name": tool_name,
                            "arguments": arguments or {},
                            "result": result,
                        }
                    )
                ],
            }
        ],
    )


def test_content_similarity_credits_correct_numeric_answer_with_equivalent_wording() -> (
    None
):
    assert (
        _content_similarity(
            "It is 238 days till Christmas Day",
            "Therefore, there are exactly 238 days until Christmas Day.",
        )
        == 1.0
    )


def test_content_similarity_credits_answer_value_inside_verbose_response() -> None:
    assert (
        _content_similarity(
            "AAPL",
            "The stock symbol for Apple is typically known to be **AAPL**.",
        )
        == 1.0
    )


def test_content_similarity_rejects_wrong_numeric_answer() -> None:
    assert _content_similarity(
        "It is 238 days till Christmas Day",
        "It is 12 days till Christmas Day.",
    ) == pytest.approx(0.0)


def test_content_similarity_does_not_apply_numeric_tolerance_to_phone_numbers() -> None:
    assert (
        _content_similarity(
            "The phone number is +10000000000",
            "The phone number is +10000000001",
        )
        == 0.0
    )


def test_outcome_score_uses_target_facts_for_route_independent_final_answer() -> None:
    scenario_name = "find_days_till_holiday_3_distraction_tools"
    scenario = _scenario(scenario_name)
    current_timestamp = 1777597539.872639
    execution_context = _rollout_context()
    execution_context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.EXECUTION_ENVIRONMENT,
                "recipient": RoleType.AGENT,
                "content": str(current_timestamp),
                "tool_trace": [
                    json.dumps(
                        {
                            "tool_name": "get_current_timestamp",
                            "arguments": {},
                            "result": current_timestamp,
                        }
                    )
                ],
            },
            {
                "sender": RoleType.AGENT,
                "recipient": RoleType.USER,
                "content": "There are 238 days until Christmas Day.",
            },
        ],
    )

    outcome = compute_outcome_score(
        scenario,
        execution_context,
        scenario_name=scenario_name,
    )

    assert outcome["outcome_similarity"] == 1.0
    assert [check["kind"] for check in outcome["outcome_checks"]] == [
        "route",
        "route",
        "route",
        "answer",
    ]


def _weather_result(
    *,
    current_temperature=15.1,
    min_temperature=8.2,
    latitude=36.054,
    longitude=-112.139,
):
    return {
        "current_temperature": current_temperature,
        "min_temperature": min_temperature,
        "temperature_unit": "Celsius",
        "lat": latitude,
        "lon": longitude,
    }


def _baseline_christmas_days(execution_context: ExecutionContext) -> tuple[int, int]:
    reminders = execution_context.get_database(DatabaseNamespace.REMINDER).to_dicts()
    current_timestamp = (
        max(float(row["creation_timestamp"]) for row in reminders)
        + max(float(row["reminder_timestamp"]) for row in reminders)
    ) / 2
    current = dt.datetime.fromtimestamp(current_timestamp)
    christmas = dt.datetime(current.year, 12, 25)
    if christmas <= current:
        christmas = dt.datetime(current.year + 1, 12, 25)
    return (christmas - current).days, christmas.year


def test_dynamic_numeric_fixture_contract_is_derived_from_pinned_bytes() -> None:
    fixture_path = (
        Path(__file__).resolve().parents[2]
        / "artifacts/publication_cleanup_20260901/fixtures/rapid_api_cache.sanitized.json"
    )
    fixture_bytes = fixture_path.read_bytes()
    assert hashlib.sha256(fixture_bytes).hexdigest() == (
        _PINNED_RAPID_API_FIXTURE_SHA256
    )
    entries = json.loads(fixture_bytes)["entries"]
    for contract in _DYNAMIC_NUMERIC_SCENARIO_FAMILIES.values():
        if contract["kind"] != "temperature":
            continue
        reference_latitude, reference_longitude = contract["reference_coordinates"]
        forecast_day = int(contract["forecast_day"])
        expected_request_days = forecast_day + 1
        for observation in contract["fixture_observations"]:
            entry = entries[observation["request_sha256"]]
            request = entry["request"]
            assert request["host"] == "weatherapi-com.p.rapidapi.com"
            assert int(request["params"]["days"]) == expected_request_days
            request_latitude, request_longitude = (
                float(part.strip()) for part in request["params"]["q"].split(",")
            )
            tolerance = float(contract["coordinate_tolerance_degrees"])
            assert abs(request_latitude - reference_latitude) <= tolerance
            assert abs(request_longitude - reference_longitude) <= tolerance
            response = entry["response"]
            assert (
                response["location"]["localtime"].split()[0]
                == observation["capture_date"]
            )
            if contract["source_field"] == "current_temperature":
                source_value = response["current"]["temp_c"]
            else:
                source_value = response["forecast"]["forecastday"][forecast_day]["day"][
                    "mintemp_c"
                ]
            assert float(source_value) == float(observation["source_value"])
            if observation.get("context_source_value") is not None:
                assert forecast_day == 1
                context_source_value = response["forecast"]["forecastday"][0]["day"][
                    "mintemp_c"
                ]
                assert float(context_source_value) == float(
                    observation["context_source_value"]
                )


def test_generated_only_fixture_temperature_is_valid_without_native_route() -> None:
    execution_context = _rollout_context()
    _add_tool_result(
        execution_context,
        "extract_temperature_result",
        {
            "answer_value": "59.18",
            "answer_unit": "Fahrenheit",
            "exact_final_answer": (
                "The current temperature in Grand Canyon is 59.18 Fahrenheit."
            ),
        },
        arguments={
            "service_payload": {"current_temperature": 999},
            "requested_unit": "Fahrenheit",
        },
    )
    _add_agent_message(
        execution_context,
        "The current temperature in Grand Canyon is 59.18 Fahrenheit.",
    )

    assert (
        _score("find_temperature_f_with_location", execution_context)[
            "outcome_similarity"
        ]
        == 1.0
    )


@pytest.mark.parametrize(
    "answer",
    [
        "The current temperature in Grand Canyon is 167 Fahrenheit.",
        "The current temperature in Grand Canyon is 60.98 Fahrenheit.",
        "The current temperature in Grand Canyon is 59.181 Fahrenheit.",
    ],
)
def test_generated_only_arbitrary_or_overprecise_temperature_fails(answer: str) -> None:
    execution_context = _rollout_context()
    _add_tool_result(
        execution_context,
        "extract_temperature_result",
        {"answer_value": answer.split()[-2], "answer_unit": "Fahrenheit"},
        arguments={
            "service_payload": {"current_temperature": answer.split()[-2]},
            "requested_unit": "Fahrenheit",
        },
    )
    _add_agent_message(execution_context, answer)

    assert (
        _score("find_temperature_f_with_location", execution_context)[
            "outcome_similarity"
        ]
        == 0.0
    )


def test_arbitrary_result_dictionary_cannot_bind_temperature_placeholder() -> None:
    execution_context = _rollout_context()
    _add_tool_result(
        execution_context,
        "unrelated_generated_metadata",
        {"temperature": 167, "min_temperature": 167, "days": -941},
    )
    _add_agent_message(
        execution_context,
        "The current temperature in Grand Canyon is 167 Fahrenheit.",
    )

    assert (
        _score("find_temperature_f_with_location", execution_context)[
            "outcome_similarity"
        ]
        == 0.0
    )


@pytest.mark.parametrize(
    "value",
    ["59", "59.2", "59.18", "59.1800", "46.75999999999991"],
)
def test_fixture_temperature_accepts_numeric_equivalent_precision_forms(
    value: str,
) -> None:
    scenario_name = (
        "find_temperature_f_with_location"
        if value.startswith("59")
        else "find_temperature_f_with_location_and_time_diff_multiple_user_turn"
    )
    assert (
        _score(
            scenario_name,
            _rollout_context(f"{value} Fahrenheit"),
        )["outcome_similarity"]
        == 1.0
    )


@pytest.mark.parametrize(
    "answer",
    [
        "The current temperature in Grand Canyon is 59.18 Celsius.",
        "The current temperature in Grand Canyon is not 59.18 Fahrenheit.",
        "59.18 Fahrenheit is not the current temperature in Grand Canyon.",
    ],
)
def test_fixture_temperature_rejects_wrong_unit_and_negative_polarity(
    answer: str,
) -> None:
    assert (
        _score("find_temperature_f_with_location", _rollout_context(answer))[
            "outcome_similarity"
        ]
        == 0.0
    )


def test_fixture_temperature_accepts_consistent_dual_unit_explanation() -> None:
    outcome = _score(
        "find_temperature_f_with_location",
        _rollout_context("The fixture reports 15.1°C, which is approximately 59.2°F."),
    )

    assert outcome["outcome_similarity"] == 1.0


def test_fixture_temperature_rejects_conflicting_target_values() -> None:
    outcome = _score(
        "find_temperature_f_with_location",
        _rollout_context(
            "The temperature is 59.18 Fahrenheit, but it may instead be 54.14 Fahrenheit."
        ),
    )

    assert outcome["outcome_similarity"] == 0.0


def test_multiple_native_routes_do_not_veto_valid_frozen_fixture_answer() -> None:
    execution_context = _rollout_context()
    _add_tool_result(
        execution_context,
        "search_weather_around_lat_lon",
        _weather_result(current_temperature=12.3),
        arguments={"days": 0, "latitude": 36.2678855, "longitude": -112.3535253},
    )
    _add_tool_result(
        execution_context,
        "search_weather_around_lat_lon",
        _weather_result(current_temperature=15.1),
        arguments={"days": 0, "latitude": 36.1069, "longitude": -112.1129},
    )
    _add_agent_message(execution_context, "59.18 Fahrenheit")

    assert (
        _score("find_temperature_f_with_location", execution_context)[
            "outcome_similarity"
        ]
        == 1.0
    )


@pytest.mark.parametrize(
    ("scenario_name", "answer", "expected"),
    [
        (
            "find_temperature",
            "The current temperature is 16.1 Celsius.",
            1.0,
        ),
        (
            "find_temperature",
            "The current temperature is 16.1 Fahrenheit.",
            0.0,
        ),
        (
            "find_temperature_f_with_location_and_time_diff_multiple_user_turn",
            "The lowest temperature in Grand Canyon tomorrow is 46.58 Fahrenheit.",
            1.0,
        ),
        (
            "find_temperature_f_with_location_and_time_diff_multiple_user_turn",
            "The lowest temperature in Grand Canyon tomorrow is 46.76 Fahrenheit.",
            1.0,
        ),
        (
            "find_temperature_f_with_location_and_time_diff_multiple_user_turn",
            "The lowest temperature in Grand Canyon tomorrow is 48.56 Fahrenheit.",
            1.0,
        ),
        (
            "find_temperature_f_with_location_and_time_diff_multiple_user_turn",
            "The lowest temperature in Grand Canyon tomorrow is 8.2 Celsius.",
            0.0,
        ),
    ],
)
def test_temperature_family_day_location_and_unit_contracts(
    scenario_name: str,
    answer: str,
    expected: float,
) -> None:
    assert _score(scenario_name, _rollout_context(answer))["outcome_similarity"] == (
        expected
    )


@pytest.mark.parametrize(
    ("scenario_name", "arguments", "result", "answer"),
    [
        (
            "find_temperature_f_with_location",
            {"days": 0, "latitude": 37.334606, "longitude": -122.009102},
            _weather_result(
                current_temperature=16.1,
                latitude=37.315,
                longitude=-122.002,
            ),
            "The temperature in Grand Canyon is 60.98 Fahrenheit.",
        ),
        (
            "find_temperature_f_with_location_and_time_diff_multiple_user_turn",
            {"days": 0, "latitude": 36.1069, "longitude": -112.1129},
            _weather_result(min_temperature=8.9),
            "The lowest temperature in Grand Canyon tomorrow is 48.02 Fahrenheit.",
        ),
    ],
)
def test_wrong_location_or_forecast_day_trace_cannot_supply_answer_truth(
    scenario_name: str,
    arguments: dict,
    result: dict,
    answer: str,
) -> None:
    execution_context = _rollout_context()
    _add_tool_result(
        execution_context,
        "search_weather_around_lat_lon",
        result,
        arguments=arguments,
    )
    _add_agent_message(execution_context, answer)

    assert _score(scenario_name, execution_context)["outcome_similarity"] == 0.0


def test_later_weather_trace_cannot_retroactively_bind_wrong_answer() -> None:
    execution_context = _rollout_context(
        "The temperature in Grand Canyon is 60.98 Fahrenheit."
    )
    _add_tool_result(
        execution_context,
        "search_weather_around_lat_lon",
        _weather_result(current_temperature=16.1),
        arguments={"days": 0, "latitude": 36.1069, "longitude": -112.1129},
    )

    assert (
        _score("find_temperature_f_with_location", execution_context)[
            "outcome_similarity"
        ]
        == 0.0
    )


def test_generated_only_days_uses_immutable_baseline_clock() -> None:
    scenario_name = "find_days_till_holiday"
    execution_context = _starting_context(scenario_name)
    expected_days, holiday_year = _baseline_christmas_days(execution_context)
    _add_tool_result(
        execution_context,
        "days_between_timestamps",
        {"days": expected_days, "seconds": 0},
        arguments={"timestamp_0": -1, "timestamp_1": -1},
    )
    _add_agent_message(
        execution_context,
        f"There are {expected_days} days until Christmas Day in {holiday_year}.",
    )

    outcome = _score(scenario_name, execution_context)

    assert outcome["outcome_similarity"] == 1.0
    answer_check = next(
        check for check in outcome["outcome_checks"] if check["kind"] == "answer"
    )
    assert answer_check["selected_dynamic_numeric_evidence"]["truth_basis"] == (
        "immutable_pre_task_reminder_fixture_midpoint_plus_scenario_holiday_target"
    )


@pytest.mark.parametrize("wrong_days", [-941, 153, 155])
def test_generated_or_nearby_wrong_days_fail(wrong_days: int) -> None:
    scenario_name = "find_days_till_holiday"
    execution_context = _starting_context(scenario_name)
    _add_tool_result(
        execution_context,
        "days_between_timestamps",
        {"days": wrong_days},
        arguments={"timestamp_0": 1000, "timestamp_1": 2000},
    )
    _add_agent_message(
        execution_context,
        f"There are {wrong_days} days until Christmas Day.",
    )

    expected_days, _ = _baseline_christmas_days(execution_context)
    if wrong_days == expected_days:
        pytest.skip("wall-clock-derived synthetic context happens to match test value")
    assert _score(scenario_name, execution_context)["outcome_similarity"] == 0.0


def test_generated_days_result_without_baseline_or_native_clock_is_not_truth() -> None:
    execution_context = _rollout_context()
    _add_tool_result(
        execution_context,
        "days_between_timestamps",
        {"days": 238},
        arguments={"timestamp_0": 1777597539.872639, "timestamp_1": 1798174800.0},
    )
    _add_agent_message(execution_context, "There are 238 days until Christmas Day.")

    assert (
        _score("find_days_till_holiday", execution_context)["outcome_similarity"] == 0.0
    )


def test_native_clock_after_answer_cannot_retroactively_ground_days() -> None:
    execution_context = _rollout_context("There are 238 days until Christmas Day.")
    _add_tool_result(
        execution_context,
        "get_current_timestamp",
        1777597539.872639,
    )

    assert (
        _score("find_days_till_holiday", execution_context)["outcome_similarity"] == 0.0
    )


@pytest.mark.parametrize(
    "answer",
    [
        "There are 238 hours until Christmas Day.",
        "There are not 238 days until Christmas Day.",
        "There are 238.5 days until Christmas Day.",
    ],
)
def test_days_contract_enforces_unit_polarity_and_integer_precision(
    answer: str,
) -> None:
    current_timestamp = 1777597539.872639
    execution_context = _rollout_context()
    _add_tool_result(execution_context, "get_current_timestamp", current_timestamp)
    _add_agent_message(execution_context, answer)

    assert (
        _score("find_days_till_holiday", execution_context)["outcome_similarity"] == 0.0
    )


def test_days_contract_accepts_equivalent_decimal_formatting() -> None:
    current_timestamp = 1777597539.872639
    execution_context = _rollout_context()
    _add_tool_result(execution_context, "get_current_timestamp", current_timestamp)
    _add_agent_message(
        execution_context,
        "There are 238.0 days until Christmas Day.",
    )

    assert (
        _score("find_days_till_holiday", execution_context)["outcome_similarity"] == 1.0
    )


@pytest.mark.parametrize(
    "answer_template",
    [
        "We are {days} days and about 9 hours away from Christmas Day.",
        "We are {days} days, 9 hours, and 5 minutes away from Christmas Day.",
        "There are {days} days left until December 25, {year}.",
        "There are {days} days left until Christmas Day on December 25, {year}.",
        (
            "There are {days} days until Christmas Day. "
            "If you have any other questions, feel free to ask!"
        ),
    ],
)
def test_days_semantic_slots_accept_saved_valid_responses(
    answer_template: str,
) -> None:
    scenario_name = "find_days_till_holiday"
    execution_context = _starting_context(scenario_name)
    expected_days, holiday_year = _baseline_christmas_days(execution_context)
    _add_agent_message(
        execution_context,
        answer_template.format(days=expected_days, year=holiday_year),
    )

    assert _score(scenario_name, execution_context)["outcome_similarity"] == 1.0


@pytest.mark.parametrize(
    "answer_template",
    [
        "There are {days} days until Christmas Day; correction: {wrong} days.",
        "There are {wrong} days until Christmas Day.",
        "There are {days} hours until Christmas Day.",
        "There are {days} weeks until Christmas Day.",
        "There are {days} days until Christmas Day on December 24, {year}.",
    ],
)
def test_days_semantic_slots_reject_wrong_target_slot(
    answer_template: str,
) -> None:
    scenario_name = "find_days_till_holiday"
    execution_context = _starting_context(scenario_name)
    expected_days, holiday_year = _baseline_christmas_days(execution_context)
    _add_agent_message(
        execution_context,
        answer_template.format(
            days=expected_days,
            wrong=expected_days - 1,
            year=holiday_year,
        ),
    )

    assert _score(scenario_name, execution_context)["outcome_similarity"] == 0.0


@pytest.mark.parametrize(
    ("scenario_name", "answer"),
    [
        (
            "find_temperature",
            (
                "The current temperature is 16.1°C. "
                "If you have any other questions or need assistance, "
                "feel free to let me know!"
            ),
        ),
        (
            "find_temperature",
            "The current temperature is 16.1°C (61°F).",
        ),
        (
            "find_temperature",
            (
                "In CA 95014, USA, the current temperature is 16.1°C "
                "with 72% humidity and 8 mph wind."
            ),
        ),
        (
            "find_temperature_f_with_location_and_time_diff_multiple_user_turn",
            "The lowest temperature of 8.2°C is approximately 46.8°F.",
        ),
        (
            "find_temperature_f_with_location_and_time_diff_multiple_user_turn",
            (
                "Today: 15.1 Celsius is 59.18 Fahrenheit. "
                "Tomorrow: 8.2 Celsius is 46.76 Fahrenheit."
            ),
        ),
        (
            "find_temperature_f_with_location_and_time_diff_multiple_user_turn",
            (
                "The temperatures in Fahrenheit are as follows:\n\n"
                "- Today: Lowest temperature is 48.0°F.\n"
                "- Tomorrow: Lowest temperature is 46.8°F."
            ),
        ),
        (
            "find_temperature_f_with_location_and_time_diff_multiple_user_turn",
            (
                "Today (4.9 Celsius) is 40.82 Fahrenheit; "
                "tomorrow (9.2 Celsius) is 48.56 Fahrenheit."
            ),
        ),
        (
            "find_temperature_f_with_location_and_time_diff_multiple_user_turn",
            (
                "Today was reported as an unrelated 999 Celsius; "
                "tomorrow's lowest temperature is 46.8 Fahrenheit."
            ),
        ),
        (
            "find_temperature_f_with_location_and_time_diff_multiple_user_turn",
            "Tomorrow is 45°F; correction: 46.8°F.",
        ),
        (
            "find_temperature_f_with_location",
            "The current temperature is 59.18°F, not 60°F.",
        ),
    ],
)
def test_temperature_semantic_slots_accept_saved_valid_responses(
    scenario_name: str,
    answer: str,
) -> None:
    assert _score(scenario_name, _rollout_context(answer))["outcome_similarity"] == (
        1.0
    )


@pytest.mark.parametrize(
    "answer",
    [
        "Tomorrow is 46.8°F; correction: it is 45°F.",
        "Tomorrow's lowest temperature is 46.8°C.",
        "The lowest temperature is 8.1°C, which equals 46.8°F.",
        "Tomorrow's lowest temperature is 46.8°F. Actually, that temperature is wrong.",
        "Tomorrow's lowest temperature is 46.8°F or 45°F.",
    ],
)
def test_temperature_semantic_slots_reject_wrong_or_retracted_target(
    answer: str,
) -> None:
    scenario_name = "find_temperature_f_with_location_and_time_diff_multiple_user_turn"
    assert _score(scenario_name, _rollout_context(answer))["outcome_similarity"] == (
        0.0
    )


def test_temperature_target_retraction_without_competing_number_fails() -> None:
    assert (
        _score(
            "find_temperature_f_with_location",
            _rollout_context(
                "The current temperature is 59.18°F, not the actual temperature."
            ),
        )["outcome_similarity"]
        == 0.0
    )


def test_answer_templates_are_parallel_alternatives_not_conjunctive_targets() -> None:
    scenario_name = "find_current_city_low_battery_mode"
    scenario = _scenario(scenario_name)
    execution_context = _rollout_context("Cupertino")

    outcome = compute_outcome_score(
        scenario,
        execution_context,
        scenario_name=scenario_name,
    )

    assert outcome["outcome_similarity"] == 1.0
    answer_check = next(
        check for check in outcome["outcome_checks"] if check["kind"] == "answer"
    )
    assert answer_check["targets"] == ["You are currently in Cupertino", "Cupertino"]
    assert answer_check["score"] == 1.0


def test_outcome_score_uses_last_task_response_not_earlier_answer() -> None:
    scenario_name = "find_days_till_holiday_3_distraction_tools"
    scenario = _scenario(scenario_name)
    execution_context = _rollout_context()
    execution_context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.EXECUTION_ENVIRONMENT,
                "recipient": RoleType.AGENT,
                "content": str(1700000000.0),
                "tool_trace": [
                    json.dumps(
                        {
                            "tool_name": "get_current_timestamp",
                            "arguments": {},
                            "result": 1700000000.0,
                        }
                    )
                ],
            },
            {
                "sender": RoleType.AGENT,
                "recipient": RoleType.USER,
                "content": "There are 238 days until Christmas Day.",
            },
            {
                "sender": RoleType.AGENT,
                "recipient": RoleType.USER,
                "content": "No clue.",
            },
        ],
    )

    outcome = compute_outcome_score(
        scenario,
        execution_context,
        scenario_name=scenario_name,
    )

    assert outcome["outcome_similarity"] == 0.0


def test_answer_scoring_ignores_extended_social_closure() -> None:
    scenario_name = "find_days_till_holiday_3_distraction_tools"
    scenario = _scenario(scenario_name)
    current_timestamp = 1777597539.872639
    execution_context = _rollout_context()
    execution_context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.EXECUTION_ENVIRONMENT,
                "recipient": RoleType.AGENT,
                "content": str(current_timestamp),
                "tool_trace": [
                    json.dumps(
                        {
                            "tool_name": "get_current_timestamp",
                            "arguments": {},
                            "result": current_timestamp,
                        }
                    )
                ],
            },
            {
                "sender": RoleType.AGENT,
                "recipient": RoleType.USER,
                "content": "There are 238 days until Christmas Day.",
            },
            {
                "sender": RoleType.AGENT,
                "recipient": RoleType.USER,
                "content": "You're welcome—let me know if you need anything else!",
            },
        ],
    )

    outcome = compute_outcome_score(
        scenario,
        execution_context,
        scenario_name=scenario_name,
    )

    assert outcome["outcome_similarity"] == 1.0


def test_answer_scoring_rejects_expected_message_text_quoted_inside_denial() -> None:
    outcome = _score(
        "search_message_with_recency_latest_alt_3_distraction_tools_tool_description_scrambled",
        _rollout_context(
            (
                "There are no records of a message with the content "
                '"Good, keep me posted." in your text history.'
            ),
            "Understood. If you need anything else, feel free to ask!",
        ),
    )

    assert outcome["outcome_similarity"] == 0.0
    answer_check = next(
        check for check in outcome["outcome_checks"] if check["kind"] == "answer"
    )
    assert answer_check["selected_explicit_target_contradiction"] is True


def test_answer_scoring_accepts_target_after_explicit_correction() -> None:
    outcome = _score(
        "search_message_with_recency_latest_alt_3_distraction_tools_tool_description_scrambled",
        _rollout_context(
            (
                'There are no records saying "Good, keep me posted"—correction: '
                'the latest message does say "Good, keep me posted".'
            )
        ),
    )

    assert outcome["outcome_similarity"] == 1.0
    answer_check = next(
        check for check in outcome["outcome_checks"] if check["kind"] == "answer"
    )
    assert answer_check["selected_explicit_target_contradiction"] is False


def test_unresolved_numeric_template_rejects_non_answer() -> None:
    outcome = _score(
        "find_temperature_f_with_location_all_tools",
        _rollout_context(
            "I couldn't retrieve the current temperature for the Grand Canyon. "
            "You may want to check a weather app or website for that information."
        ),
    )

    assert outcome["outcome_similarity"] == 0.0


def test_unresolved_numeric_template_preserves_concrete_answer() -> None:
    outcome = _score(
        "find_temperature_f_with_location_all_tools",
        _rollout_context(
            "The temperature in the Grand Canyon is approximately 54.14°F."
        ),
    )

    assert outcome["outcome_similarity"] == 1.0


def test_answer_scoring_rejects_target_followed_by_recency_contradiction() -> None:
    outcome = _score(
        "search_reminder_with_recency_yesterday_implicit_3_distraction_tools",
        _rollout_context(
            'I found a related reminder: "Look for Company SF tickets," created '
            "earlier, but there are no reminders specifically recorded for that "
            "yesterday. The latest reminder regarding it is for an earlier date."
        ),
    )

    assert outcome["outcome_similarity"] == 0.0
    answer_check = next(
        check for check in outcome["outcome_checks"] if check["kind"] == "answer"
    )
    assert answer_check["selected_explicit_target_contradiction"] is True


@pytest.mark.parametrize(
    "answer",
    [
        'The latest message says "Are you coming to dinner?".',
        (
            'The latest message says "Are you coming to dinner?". '
            "I should now be able to help with anything else."
        ),
    ],
)
def test_answer_scoring_preserves_quoted_question_and_benign_tail(answer: str) -> None:
    assert _content_similarity("Are you coming to dinner?", answer) == 1.0


@pytest.mark.parametrize(
    "closure",
    [
        "Of course! Happy to help.",
        "Anytime!",
        "My pleasure!",
        "No worries!",
        "You're very welcome!",
        "Thank you! Let me know if you need anything else.",
        "Understood. If you need anything else, feel free to ask!",
        "That's perfectly fine. If you need any further assistance later, just let me know!",
        "If there's anything else I can assist you with, please let me know!",
        "Understood. If you need assistance later, feel free to ask.",
        "I'm glad I could help!",
        "I don't have anything else to add.",
        "I can't provide anything else.",
    ],
)
def test_answer_scoring_ignores_common_social_only_closures(closure: str) -> None:
    scenario_name = "convert_currency"
    outcome = _score(
        scenario_name,
        _rollout_context("The result is 13988.4544 CNY.", closure),
    )

    assert outcome["outcome_similarity"] == 1.0


def test_polite_prefix_with_substantive_correction_is_not_discarded() -> None:
    outcome = _score(
        "find_current_city_insufficient_information",
        _rollout_context(
            "Your current city is Boston.",
            "No problem. I still can't determine your city without your current location.",
        ),
    )

    assert outcome["outcome_similarity"] == 1.0
    check = outcome["outcome_checks"][0]
    assert check["selected_classification"] == ("correct_abstention_or_clarification")
    assert check["earlier_unsupported_completion_message_indices"]


def test_insufficient_information_later_correction_passes_and_is_diagnostic() -> None:
    outcome = _score(
        "find_current_city_insufficient_information_3_distraction_tools",
        _rollout_context(
            "Your current city is San Francisco.",
            "I can't determine your current city without your current location or coordinates.",
            "You're welcome—let me know if you need anything else.",
            prelude_agent_messages=("Your current city is Seattle.",),
        ),
    )

    assert outcome["outcome_similarity"] == 1.0
    check = outcome["outcome_checks"][0]
    assert check["selected_classification"] == "correct_abstention_or_clarification"
    assert len(check["earlier_unsupported_completion_message_indices"]) == 1
    assert check["earlier_unsupported_completion_message_indices"][0] > 0


def test_insufficient_information_later_substantive_contradiction_still_fails() -> None:
    outcome = _score(
        "find_current_city_insufficient_information",
        _rollout_context(
            "I can't determine your city without your current location.",
            "Actually, your current city is Boston.",
        ),
    )

    assert outcome["outcome_similarity"] == 0.0
    assert outcome["outcome_checks"][0]["selected_classification"] == (
        "unsupported_completion"
    )


def test_insufficient_information_generic_refusal_does_not_receive_credit() -> None:
    outcome = _score(
        "find_current_city_insufficient_information",
        _rollout_context("I can't help with that."),
    )

    assert outcome["outcome_similarity"] == 0.0
    assert (
        outcome["outcome_checks"][0]["selected_classification"]
        == "incorrect_or_nonspecific_response"
    )


def test_insufficient_information_targeted_clarification_receives_credit() -> None:
    outcome = _score(
        "find_current_location_insufficient_information_all_tools",
        _rollout_context("Please share your current location or coordinates."),
    )

    assert outcome["outcome_similarity"] == 1.0


@pytest.mark.parametrize(
    ("scenario_name", "answer"),
    [
        ("find_current_city_insufficient_information", "Where are you?"),
        (
            "find_min_temperature_weekday_insufficient_information",
            "Which Friday, and where are you?",
        ),
        (
            "modify_contact_with_message_recency_insufficient_information_alt",
            "Who did you contact last?",
        ),
        (
            "remove_contact_by_phone_no_remove_contact_insufficient_information",
            "I can't delete it with the available tools.",
        ),
    ],
)
def test_insufficient_information_accepts_natural_targeted_clarifications(
    scenario_name: str,
    answer: str,
) -> None:
    outcome = _score(scenario_name, _rollout_context(answer))

    assert outcome["outcome_similarity"] == 1.0
    assert outcome["outcome_checks"][0]["selected_classification"] == (
        "correct_abstention_or_clarification"
    )


@pytest.mark.parametrize(
    ("scenario_name", "answer"),
    [
        (
            "find_current_city_insufficient_information",
            "I can't access your location, but you're currently in Boston.",
        ),
        (
            "modify_contact_with_message_recency_insufficient_information",
            "I can't access your message history, but I've set it to +10293847563.",
        ),
        (
            "remove_contact_by_phone_no_remove_contact_insufficient_information",
            "I lack a removal tool. Done.",
        ),
    ],
)
def test_insufficient_information_rejects_limitation_completion_contradictions(
    scenario_name: str,
    answer: str,
) -> None:
    outcome = _score(scenario_name, _rollout_context(answer))

    assert outcome["outcome_similarity"] == 0.0
    assert outcome["outcome_checks"][0]["selected_classification"] == (
        "unsupported_completion"
    )


def test_insufficient_information_accepts_any_independently_sufficient_blocker() -> (
    None
):
    scenario_name = "find_min_temperature_weekday_insufficient_information"
    assert (
        _score(
            scenario_name,
            _rollout_context("I need your current location."),
        )["outcome_similarity"]
        == 1.0
    )
    assert (
        _score(
            scenario_name,
            _rollout_context("I need the current date before I can answer."),
        )["outcome_similarity"]
        == 1.0
    )
    assert (
        _score(
            scenario_name,
            _rollout_context(
                "I need your current location and the current date before I can answer."
            ),
        )["outcome_similarity"]
        == 1.0
    )
    assert (
        _score(
            scenario_name,
            _rollout_context("I need more information before I can answer."),
        )["outcome_similarity"]
        == 0.0
    )


def test_insufficient_information_affirmative_completion_overrides_abstention() -> None:
    outcome = _score(
        "send_message_with_contact_content_cellular_off_insufficient_information",
        _rollout_context(
            "I don't have Fredrik's phone number, but I sent the message anyway."
        ),
    )

    assert outcome["outcome_similarity"] == 0.0
    assert outcome["outcome_checks"][0]["selected_classification"] == (
        "unsupported_completion"
    )


def test_minefield_is_recomputed_from_scenario_and_trajectory() -> None:
    outcome = _score(
        "find_current_city_insufficient_information",
        _rollout_context("I can't determine the city without your current location."),
    )

    assert outcome["outcome_milestone_similarity"] == 1.0
    assert outcome["outcome_similarity"] == 1.0
    assert outcome["outcome_checks"][0]["minefield_violation"] is False


def test_insufficient_information_forbidden_action_is_permanent_failure() -> None:
    execution_context = _rollout_context()
    execution_context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.EXECUTION_ENVIRONMENT,
                "recipient": RoleType.AGENT,
                "content": "tool result",
                "tool_trace": [
                    json.dumps(
                        {
                            "tool_name": "send_message_with_phone_number",
                            "arguments": {},
                            "result": None,
                        }
                    )
                ],
            },
            {
                "sender": RoleType.AGENT,
                "recipient": RoleType.USER,
                "content": "I need Fredrik's phone number before I can send it.",
            },
        ],
    )

    outcome = _score(
        "send_message_with_contact_content_cellular_off_insufficient_information",
        execution_context,
    )

    assert outcome["outcome_milestone_similarity"] == 1.0
    assert outcome["outcome_similarity"] == 0.0
    assert outcome["outcome_forbidden_action_detected"] is True


def test_insufficient_information_state_mutation_is_permanent_failure() -> None:
    execution_context = _rollout_context()
    execution_context.add_to_database(
        DatabaseNamespace.CONTACT,
        [
            {
                "person_id": "publication-test-person",
                "name": "Publication Test",
                "phone_number": "+10000000000",
                "relationship": "test",
                "is_self": False,
            }
        ],
    )
    execution_context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.AGENT,
                "recipient": RoleType.USER,
                "content": "I can't determine your city without your current location.",
            }
        ],
    )

    outcome = _score(
        "find_current_city_insufficient_information",
        execution_context,
    )

    assert outcome["outcome_milestone_similarity"] == 1.0
    assert outcome["outcome_similarity"] == 0.0
    assert outcome["outcome_state_mutation_detected"] is True


def test_insufficient_information_allows_setting_prerequisite_changes() -> None:
    scenario_name = (
        "send_message_with_contact_content_cellular_off_insufficient_information"
    )
    execution_context = _starting_context(scenario_name)
    settings = execution_context.get_database(DatabaseNamespace.SETTING).with_columns(
        pl.lit(True).alias("cellular")
    )
    execution_context.update_database(DatabaseNamespace.SETTING, settings)
    _add_agent_message(
        execution_context,
        "I still need Fredrik's phone number before I can send the message.",
    )

    outcome = _score(scenario_name, execution_context)

    assert outcome["outcome_similarity"] == 1.0
    assert outcome["outcome_state_mutation_detected"] is True
    assert outcome["outcome_unexpected_state_mutation_detected"] is False
    assert outcome["outcome_checks"][0]["permitted_state_mutation_diagnostics"]


def test_setting_location_mutation_is_not_a_permitted_prerequisite_change() -> None:
    scenario_name = "find_current_city_insufficient_information"
    execution_context = _starting_context(scenario_name)
    settings = execution_context.get_database(DatabaseNamespace.SETTING).with_columns(
        pl.lit(42.0).alias("latitude")
    )
    execution_context.update_database(DatabaseNamespace.SETTING, settings)
    _add_agent_message(
        execution_context,
        "I can't determine your city without your current location.",
    )

    outcome = _score(scenario_name, execution_context)

    assert outcome["outcome_similarity"] == 0.0
    assert outcome["outcome_unexpected_state_mutation_detected"] is True
    assert (
        outcome["outcome_checks"][0]["setting_prerequisite_mutation_permitted"] is False
    )


@pytest.mark.parametrize(
    "scenario_name",
    [
        "remove_contact_by_phone_no_remove_contact_insufficient_information",
        "remove_contact_by_phone_no_search_contacts_insufficient_information",
    ],
)
def test_verified_direct_contact_deletion_overrides_native_route_minefield(
    scenario_name: str,
) -> None:
    execution_context = _starting_context(scenario_name)
    contacts = execution_context.get_database(DatabaseNamespace.CONTACT)
    target = contacts.filter(pl.col("phone_number") == "+12453344098").to_dicts()[0]
    _add_agent_message(
        execution_context,
        f"remove_contact(person_id={target['person_id']!r})",
        recipient=RoleType.EXECUTION_ENVIRONMENT,
    )
    execution_context.update_database(
        DatabaseNamespace.CONTACT,
        contacts.filter(pl.col("phone_number") != "+12453344098"),
    )
    _add_agent_message(execution_context, "Done.")

    outcome = _score(
        scenario_name,
        execution_context,
    )

    assert outcome["outcome_similarity"] == 1.0
    assert outcome["outcome_forbidden_action_detected"] is True
    assert outcome["outcome_route_capability_safety_overridden"] is True
    check = outcome["outcome_checks"][0]
    assert check["outcome_basis"] == "verified_state_completion"
    assert check["state_completion"]["reason"] == "exact_target_removed"
    assert check["unexpected_state_mutation_diagnostics"] == []


@pytest.mark.parametrize(
    "phones_to_remove",
    [
        {"+10000000000"},
        {"+12453344098", "+10000000000"},
    ],
)
def test_wrong_or_collateral_contact_deletion_is_not_an_outcome_success(
    phones_to_remove: set[str],
) -> None:
    scenario_name = (
        "remove_contact_by_phone_no_search_contacts_insufficient_information"
    )
    execution_context = _starting_context(scenario_name)
    contacts = execution_context.get_database(DatabaseNamespace.CONTACT)
    _add_agent_message(
        execution_context,
        "remove_contact(person_id='generated-resolution')",
        recipient=RoleType.EXECUTION_ENVIRONMENT,
    )
    execution_context.update_database(
        DatabaseNamespace.CONTACT,
        contacts.filter(~pl.col("phone_number").is_in(phones_to_remove)),
    )
    _add_agent_message(execution_context, "Done.")

    outcome = _score(
        scenario_name,
        execution_context,
    )

    assert outcome["outcome_similarity"] == 0.0
    assert outcome["outcome_route_capability_safety_overridden"] is False
    assert outcome["outcome_checks"][0]["state_completion"]["verified"] is False


def test_verified_contact_modification_is_route_independent() -> None:
    scenario_name = "modify_contact_with_message_recency_insufficient_information"
    execution_context = _starting_context(scenario_name)
    contacts = execution_context.get_database(DatabaseNamespace.CONTACT)
    _add_agent_message(
        execution_context,
        "modify_contact(person_id='last-outbound-recipient')",
        recipient=RoleType.EXECUTION_ENVIRONMENT,
    )
    execution_context.update_database(
        DatabaseNamespace.CONTACT,
        contacts.with_columns(
            pl.when(pl.col("name") == "Homer S")
            .then(pl.lit("+10293847563"))
            .otherwise(pl.col("phone_number"))
            .alias("phone_number")
        ),
    )
    _add_agent_message(execution_context, "Done.")

    outcome = _score(
        scenario_name,
        execution_context,
    )

    assert outcome["outcome_similarity"] == 1.0
    assert outcome["outcome_checks"][0]["state_completion"]["reason"] == (
        "exact_contact_updated"
    )


def test_verified_message_send_allows_cellular_prerequisite_change() -> None:
    scenario_name = (
        "send_message_with_contact_content_cellular_off_insufficient_information"
    )
    execution_context = _starting_context(scenario_name)
    contacts = execution_context.get_database(DatabaseNamespace.CONTACT).to_dicts()
    self_row = next(row for row in contacts if row["is_self"])
    fredrik = next(row for row in contacts if row["name"] == "Fredrik Thordendal")
    messages = execution_context.get_database(DatabaseNamespace.MESSAGING).to_dicts()
    _add_agent_message(
        execution_context,
        "send_message_with_phone_number(phone_number='+12453344098')",
        recipient=RoleType.EXECUTION_ENVIRONMENT,
    )
    settings = execution_context.get_database(DatabaseNamespace.SETTING).with_columns(
        pl.lit(True).alias("cellular")
    )
    execution_context.update_database(DatabaseNamespace.SETTING, settings)
    execution_context.add_to_database(
        DatabaseNamespace.MESSAGING,
        [
            {
                "message_id": "publication-direct-send",
                "sender_person_id": self_row["person_id"],
                "sender_phone_number": self_row["phone_number"],
                "recipient_person_id": fredrik["person_id"],
                "recipient_phone_number": fredrik["phone_number"],
                "content": "How's the new album coming along.",
                "creation_timestamp": max(
                    float(row["creation_timestamp"]) for row in messages
                )
                + 60,
            }
        ],
    )
    _add_agent_message(execution_context, "Done.")

    outcome = _score(
        scenario_name,
        execution_context,
    )

    assert outcome["outcome_similarity"] == 1.0
    check = outcome["outcome_checks"][0]
    assert check["state_completion"]["reason"] == "exact_message_appended"
    assert {
        row["namespace"] for row in check["permitted_state_mutation_diagnostics"]
    } == {
        str(DatabaseNamespace.MESSAGING),
        str(DatabaseNamespace.SETTING),
    }


@pytest.mark.parametrize("operation", ["remove", "modify"])
def test_verified_upcoming_reminder_actions_are_route_independent(
    operation: str,
) -> None:
    scenario_name = (
        "remove_reminder_with_recency_latest_insufficient_information"
        if operation == "remove"
        else "modify_reminder_with_recency_latest_insufficient_information"
    )
    execution_context = _starting_context(scenario_name)
    reminders = execution_context.get_database(DatabaseNamespace.REMINDER)
    target_timestamp = reminders.select(pl.col("reminder_timestamp").max()).item()
    target = reminders.filter(
        pl.col("reminder_timestamp") == target_timestamp
    ).to_dicts()[0]
    native_tool = "remove_reminder" if operation == "remove" else "modify_reminder"
    _add_agent_message(
        execution_context,
        f"{native_tool}(reminder_id={target['reminder_id']!r})",
        recipient=RoleType.EXECUTION_ENVIRONMENT,
    )
    if operation == "remove":
        final_reminders = reminders.filter(
            pl.col("reminder_id") != target["reminder_id"]
        )
    else:
        inferred_now = (
            float(reminders.select(pl.col("creation_timestamp").max()).item())
            + float(reminders.select(pl.col("reminder_timestamp").max()).item())
        ) / 2
        tomorrow = dt.datetime.fromtimestamp(inferred_now) + dt.timedelta(days=1)
        expected_timestamp = tomorrow.replace(
            hour=17,
            minute=0,
            second=0,
            microsecond=0,
        ).timestamp()
        final_reminders = reminders.with_columns(
            pl.when(pl.col("reminder_id") == target["reminder_id"])
            .then(pl.lit(expected_timestamp))
            .otherwise(pl.col("reminder_timestamp"))
            .alias("reminder_timestamp")
        )
    execution_context.update_database(DatabaseNamespace.REMINDER, final_reminders)
    _add_agent_message(execution_context, "Done.")

    outcome = _score(
        scenario_name,
        execution_context,
    )

    assert outcome["outcome_similarity"] == 1.0
    assert outcome["outcome_checks"][0]["outcome_basis"] == (
        "verified_state_completion"
    )


@pytest.mark.parametrize(
    ("scenario_name", "answer"),
    [
        ("convert_currency", "The result is 13,988.46 CNY."),
        (
            "convert_currency_canonicalize_3_distraction_tools_tool_name_scrambled",
            "2048 USD converts to 13988.4544 Chinese yuan.",
        ),
        (
            "convert_currency",
            "2048 USD converts to 13988.4544 CNY; confirmed: 13988.4544 CNY.",
        ),
        (
            "find_thanksgiving_timestamp_all_tools",
            "The Thanksgiving timestamp is 1795669201.",
        ),
    ],
)
def test_scalar_contract_accepts_value_tolerance_and_context_without_native_tool(
    scenario_name: str,
    answer: str,
) -> None:
    outcome = _score(scenario_name, _rollout_context(answer))

    assert outcome["outcome_similarity"] == 1.0
    assert outcome["outcome_checks"][0]["kind"] == "scalar_outcome_contract"


@pytest.mark.parametrize(
    ("scenario_name", "answer"),
    [
        ("convert_currency", "The result is 13988.4544."),
        ("convert_currency", "The result is 13988.47 CNY."),
        ("find_thanksgiving_timestamp", "The timestamp is 1795669200."),
        ("find_thanksgiving_timestamp", "Thanksgiving is 1795669200."),
        (
            "find_thanksgiving_timestamp",
            "The Thanksgiving timestamp is 1795669202.",
        ),
    ],
)
def test_scalar_contract_rejects_missing_context_or_out_of_tolerance_value(
    scenario_name: str,
    answer: str,
) -> None:
    assert _score(scenario_name, _rollout_context(answer))["outcome_similarity"] == 0.0


def test_scalar_contract_uses_last_task_response_and_ignores_extended_closure() -> None:
    outcome = _score(
        "convert_currency_10_distraction_tools",
        _rollout_context(
            "The result is 12000 CNY.",
            "Correction: the result is 13988.4544 CNY.",
            "You're welcome—let me know if you need anything else.",
            prelude_agent_messages=("The result is 13988.4544 CNY.",),
        ),
    )

    assert outcome["outcome_similarity"] == 1.0
    assert len(outcome["outcome_checks"][0]["earlier_conflicting_message_indices"]) == 1


def test_scalar_contract_later_wrong_correction_fails() -> None:
    outcome = _score(
        "convert_currency",
        _rollout_context(
            "The result is 13988.4544 CNY.",
            "Actually, correction: the result is 12000 CNY.",
        ),
    )

    assert outcome["outcome_similarity"] == 0.0


def test_scalar_contract_ignores_later_generic_non_outcome_followup() -> None:
    outcome = _score(
        "find_thanksgiving_timestamp",
        _rollout_context(
            "The Thanksgiving timestamp is 1795669200.",
            (
                "Thanksgiving is celebrated on the fourth Thursday of November. "
                "If you would like a specific year's timestamp, please let me know."
            ),
        ),
    )

    assert outcome["outcome_similarity"] == 1.0
    check = outcome["outcome_checks"][0]
    assert check["ignored_later_non_outcome_message_indices"]


def test_scalar_contract_ignores_later_consistent_date_elaboration() -> None:
    outcome = _score(
        "find_thanksgiving_timestamp",
        _rollout_context(
            "The timestamp for Thanksgiving is 1795669200.",
            "The timestamp corresponds to Thanksgiving on November 26, 2026.",
        ),
    )

    assert outcome["outcome_similarity"] == 1.0
    assert outcome["outcome_checks"][0]["ignored_later_non_outcome_message_indices"]


def test_scalar_contract_affirmative_no_further_information_prelude_passes() -> None:
    outcome = _score(
        "find_thanksgiving_timestamp",
        _rollout_context(
            (
                "If you have no further information, the timestamp for this year's "
                "Thanksgiving remains as provided: 1795669200."
            )
        ),
    )

    assert outcome["outcome_similarity"] == 1.0


def test_scalar_contract_wrong_human_readable_year_still_fails() -> None:
    for wrong_date in ("November 26, 2024", "November 11, 2026"):
        outcome = _score(
            "find_thanksgiving_timestamp",
            _rollout_context(
                f"The Thanksgiving timestamp is 1795669200, {wrong_date}."
            ),
        )

        assert outcome["outcome_similarity"] == 0.0


@pytest.mark.parametrize(
    "scenario_name", ["convert_currency", "convert_currency_canonicalize"]
)
def test_scalar_currency_accepts_canonical_input_shorthand(scenario_name: str) -> None:
    outcome = _score(
        scenario_name,
        _rollout_context("$2.048k converts to 13,988.45 CNY."),
    )

    assert outcome["outcome_similarity"] == 1.0


@pytest.mark.parametrize(
    "answer",
    [
        "2.048 USD converts to 13,988.45 CNY.",
        "2.048 CNY and the result is 13,988.45 CNY.",
    ],
)
def test_scalar_currency_rejects_bare_shorthand_magnitude(answer: str) -> None:
    assert (
        _score("convert_currency", _rollout_context(answer))["outcome_similarity"]
        == 0.0
    )


def test_scalar_number_regex_only_consumes_valid_thousands_separators() -> None:
    assert _numbers_in_text("12,500 and December 25, 2026") == [12500.0, 25.0, 2026.0]


def test_scalar_contract_does_not_ignore_later_substantive_retraction() -> None:
    outcome = _score(
        "find_thanksgiving_timestamp",
        _rollout_context(
            "The Thanksgiving timestamp is 1795669200.",
            "That Thanksgiving timestamp is wrong.",
        ),
    )

    assert outcome["outcome_similarity"] == 0.0
    check = outcome["outcome_checks"][0]
    assert check["selected_message_index"] > 1
    assert check["ignored_later_non_outcome_message_indices"] == []


def test_scalar_contract_does_not_ignore_later_wrong_bare_numeric_claim() -> None:
    outcome = _score(
        "convert_currency",
        _rollout_context(
            "The result is 13988.4544 CNY.",
            "It is 12000.",
        ),
    )

    assert outcome["outcome_similarity"] == 0.0
    assert (
        outcome["outcome_checks"][0]["ignored_later_non_outcome_message_indices"] == []
    )


def test_frozen_distance_fixture_replaces_only_the_stale_answer_target() -> None:
    correct = _score(
        "find_distance_with_location_name",
        _rollout_context(
            "You are approximately 67.98 kilometers away from Golden Gate Bridge."
        ),
    )
    stale = _score(
        "find_distance_with_location_name",
        _rollout_context(
            "You are approximately 67.86 kilometers away from Golden Gate Bridge."
        ),
    )

    assert correct["outcome_similarity"] == 1.0
    assert stale["outcome_similarity"] == 0.0
    answer_check = next(
        check for check in correct["outcome_checks"] if check["kind"] == "answer"
    )
    assert answer_check["targets"] == [
        "You are approximately 67.98 kilometers away from Golden Gate Bridge"
    ]


@pytest.mark.parametrize(
    "answer",
    [
        (
            "My current location is One Apple Park Way, Cupertino, CA 95014, USA. "
            "You are approximately 67.98 kilometers away from Golden Gate Bridge."
        ),
        (
            "My coordinates are latitude 37.334606 and longitude -122.009102. "
            "The Golden Gate Bridge is approximately 67.98 km away."
        ),
        "The precise distance to Golden Gate Bridge is 67.977 kilometers.",
        (
            "Latitude 37.334606, longitude -122.009102: the distance to the "
            "Golden Gate Bridge is 67.977 km."
        ),
        ("My equipment serial is 42 km. The Golden Gate Bridge is 67.98 km away."),
        (
            "To get to the Golden Gate Bridge from your current location, head "
            "towards San Francisco. The distance is approximately 67.98 kilometers."
        ),
        (
            "1. Your Current Location: 37.334606, -122.009102\n"
            "2. Golden Gate Bridge Location: 37.819911, -122.478560\n"
            "3. Distance: Approximately 67.98 km"
        ),
        (
            "I can't access your location services directly. However, I was able "
            "to determine that you are approximately 67.98 kilometers away from "
            "the Golden Gate Bridge. If you can provide your current location, "
            "I can help you with the distance again."
        ),
    ],
)
def test_frozen_distance_ignores_only_ancillary_coordinates_and_zip(
    answer: str,
) -> None:
    assert (
        _score(
            "find_distance_with_location_name",
            _rollout_context(answer),
        )["outcome_similarity"]
        == 1.0
    )


@pytest.mark.parametrize(
    "answer",
    [
        "The distance to Golden Gate Bridge is 67.971 km.",
        "The distance to Golden Gate Bridge is 67.86 km.",
        "The Golden Gate Bridge distance is unknown. My serial is 67.98 km.",
        (
            "The Golden Gate Bridge distance is unknown. My serial is stored "
            "elsewhere. The distance is 67.98 km."
        ),
        (
            "The Golden Gate Bridge is in San Francisco. Distance to Los Angeles "
            "is 67.98 km."
        ),
        ("The distance to Golden Gate Bridge is 67.98 km; correction: it is 60 km."),
        (
            "The distance to Golden Gate Bridge is 67.98 km; correction: "
            "I cannot determine the distance."
        ),
    ],
)
def test_frozen_distance_rejects_non_derived_or_retracted_values(answer: str) -> None:
    assert (
        _score(
            "find_distance_with_location_name",
            _rollout_context(answer),
        )["outcome_similarity"]
        == 0.0
    )


def test_generic_terminal_selector_keeps_correct_answer_across_new_task() -> None:
    context = _rollout_context("The phone number for Apple Park is +14089961010")
    _add_user_message(context, "I need you to search for that phone number.")
    _add_agent_message(
        context,
        "I'm unable to perform a reverse search for that phone number.",
    )

    outcome = _score(
        "find_phone_number_with_location_name_3_distraction_tools_arg_description_scrambled",
        context,
    )

    assert outcome["outcome_similarity"] == 1.0
    answer_check = next(
        check for check in outcome["outcome_checks"] if check["kind"] == "answer"
    )
    assert answer_check["ignored_later_non_outcome_message_indices"]


def test_generic_terminal_selector_applies_same_slot_distance_retraction() -> None:
    context = _rollout_context(
        "You are approximately 67.98 kilometers away from Golden Gate Bridge."
    )
    _add_user_message(context, "I cannot confirm that without my current location.")
    _add_agent_message(
        context,
        "Without your current location, I cannot determine the distance to the "
        "Golden Gate Bridge.",
    )

    assert (
        _score("find_distance_with_location_name", context)["outcome_similarity"] == 0.0
    )


@pytest.mark.parametrize(
    "followup",
    [
        "I cannot access your location services or map settings.",
        "What is your current starting location?",
    ],
)
def test_generic_terminal_selector_ignores_distance_route_or_prerequisite_only(
    followup: str,
) -> None:
    context = _rollout_context(
        "You are approximately 67.98 kilometers away from Golden Gate Bridge."
    )
    _add_user_message(context, "Can you double-check how you got that?")
    _add_agent_message(context, followup)

    assert (
        _score("find_distance_with_location_name", context)["outcome_similarity"] == 1.0
    )


def test_generic_terminal_selector_applies_same_slot_message_conflict() -> None:
    context = _rollout_context("Your most recent message says 'Good, keep me posted'.")
    _add_user_message(context, "That is not right. Check the latest message again.")
    _add_agent_message(
        context,
        "Your most recent message says 'Things are proceeding as expected'.",
    )

    outcome = _score("search_message_with_recency_latest", context)
    assert outcome["outcome_similarity"] < 1.0
    answer_check = next(
        check for check in outcome["outcome_checks"] if check["kind"] == "answer"
    )
    assert answer_check["selected_message_index"] == context.max_sandbox_message_index


def test_generic_terminal_selector_keeps_oldest_after_explicit_new_recency() -> None:
    context = _rollout_context(
        "Your oldest message says 'Hey kid, you want some GPU?'."
    )
    _add_user_message(context, "Can you find another recent message instead?")
    _add_agent_message(
        context,
        "Your most recent message says 'Good, keep me posted'.",
    )

    assert (
        _score("search_message_with_recency_oldest", context)["outcome_similarity"]
        == 1.0
    )


def test_generic_terminal_selector_ignores_opposite_recency_after_confirmation() -> (
    None
):
    context = _rollout_context(
        "Your oldest message says 'Hey kid, you want some GPU?'."
    )
    _add_user_message(context, "Yes, that's the message.")
    _add_agent_message(
        context,
        "Your most recent message says 'Good, keep me posted'.",
    )

    assert (
        _score("search_message_with_recency_oldest", context)["outcome_similarity"]
        == 1.0
    )


def test_generic_terminal_selector_applies_opposite_recency_to_recheck() -> None:
    context = _rollout_context("Your most recent message says 'Good, keep me posted'.")
    _add_user_message(context, "That is not the message I want. Please check again.")
    _add_agent_message(
        context,
        "Your oldest message says 'Hey kid, you want some GPU?'.",
    )

    assert (
        _score("search_message_with_recency_latest", context)["outcome_similarity"]
        == 0.0
    )


def test_generic_terminal_selector_does_not_credit_opposite_recency_wrapper() -> None:
    outcome = _score(
        "search_message_with_recency_oldest",
        _rollout_context(
            "Your most recent message says 'Hey kid, you want some GPU?'."
        ),
    )

    assert outcome["outcome_similarity"] == 0.0


def test_generic_terminal_selector_uses_boolean_semantic_affirmation() -> None:
    outcome = _score(
        "get_cellular_10_distraction_tools",
        _rollout_context("Your cellular service is already enabled."),
    )

    assert outcome["outcome_similarity"] == 1.0


@pytest.mark.parametrize(
    "later_echo",
    [
        "If cellular service is on, messaging should work.",
        '{"status": "cellular service is on"}',
    ],
)
def test_generic_terminal_selector_ignores_conditional_or_raw_echo_after_answer(
    later_echo: str,
) -> None:
    context = _rollout_context("Your cellular service is already enabled.")
    _add_agent_message(context, later_echo)

    assert (
        _score("get_cellular_10_distraction_tools", context)["outcome_similarity"]
        == 1.0
    )


def test_generic_terminal_selector_applies_direct_message_nondisclosure() -> None:
    context = _rollout_context("Your most recent message says 'Good, keep me posted'.")
    _add_user_message(context, "Please confirm the content of my latest message.")
    _add_agent_message(
        context,
        "I am unable to disclose the content of your most recent message.",
    )

    assert (
        _score("search_message_with_recency_latest", context)["outcome_similarity"]
        == 0.0
    )


@pytest.mark.parametrize(
    "followup",
    [
        "I cannot share your message content again.",
        "I can't provide further details about the oldest message right now.",
        "Yes, your message was successfully found and confirmed.",
    ],
)
def test_generic_terminal_selector_ignores_privacy_or_compatible_message_tail(
    followup: str,
) -> None:
    context = _rollout_context(
        "Your oldest message says 'Hey kid, you want some GPU?'."
    )
    _add_user_message(context, "Keep that to yourself; I don't want it leaked.")
    _add_agent_message(context, followup)

    assert (
        _score("search_message_with_recency_oldest", context)["outcome_similarity"]
        == 1.0
    )


def test_generic_terminal_selector_applies_disclosure_failure_to_retrieval_goal() -> (
    None
):
    context = _rollout_context("Your most recent message says 'Good, keep me posted'.")
    _add_user_message(
        context,
        "I wanted it private, but please find the content of my most recent message again.",
    )
    _add_agent_message(
        context,
        "I'm unable to disclose the content of your most recent message.",
    )

    assert (
        _score("search_message_with_recency_latest", context)["outcome_similarity"]
        == 0.0
    )


def test_generic_terminal_selector_ignores_disclosure_failure_after_content_disclaimer() -> (
    None
):
    context = _rollout_context("Your most recent message says 'Good, keep me posted'.")
    _add_user_message(
        context,
        "I don't want to know what it says. Just find it without sharing.",
    )
    _add_agent_message(
        context,
        "I cannot provide the content of the message without sharing it.",
    )
    _add_user_message(context, "I don't need the content; just locate it.")
    _add_agent_message(context, "Your most recent message has been located.")

    assert (
        _score("search_message_with_recency_latest", context)["outcome_similarity"]
        == 1.0
    )


def test_generic_terminal_selector_ignores_distinct_keyword_search_absence() -> None:
    context = _rollout_context(
        "Your oldest message says 'Hey kid, you want some GPU?'."
    )
    _add_user_message(context, "I understand. Let's move on.")
    _add_agent_message(
        context,
        'There are no messages containing the keyword "latest."',
    )

    assert (
        _score("search_message_with_recency_oldest", context)["outcome_similarity"]
        == 1.0
    )


def test_generic_terminal_selector_keeps_sender_identity_across_contact_absence() -> (
    None
):
    context = _rollout_context(
        "The phone number +18307976530 asked you if you want some GPUs, "
        "but it is not saved in your contacts."
    )
    _add_user_message(context, "Can you check whether that number is in my contacts?")
    _add_agent_message(
        context,
        "I couldn't find any contacts associated with the phone number +18307976530.",
    )

    assert (
        _score("search_sender_phone_number_with_content_all_tools", context)[
            "outcome_similarity"
        ]
        == 1.0
    )


@pytest.mark.parametrize(
    ("scenario_name", "answer"),
    [
        (
            "search_reminder_with_recency_yesterday_implicit_3_distraction_tools_arg_type_scrambled",
            (
                'I found "Look for Company SF tickets," but it was created earlier '
                "and not specifically tied to yesterday."
            ),
        ),
        (
            "search_reminder_with_recency_yesterday_3_distraction_tools_arg_description_scrambled",
            'Your reminder for "Look for Company SF tickets" was not found.',
        ),
        (
            "search_reminder_with_recency_yesterday_10_distraction_tools",
            'I could not locate the reminder "Look for Company SF tickets."',
        ),
        (
            "get_cellular_10_distraction_tools",
            "If cellular service is on, you should be able to send messages.",
        ),
        (
            "find_stock_symbol_with_company_name_low_battery_mode_alt_3_distraction_tools_tool_description_scrambled",
            '{"query":"AAPL"}',
        ),
    ],
)
def test_generic_answer_does_not_credit_denied_conditional_or_raw_target(
    scenario_name: str,
    answer: str,
) -> None:
    outcome = _score(scenario_name, _rollout_context(answer))
    answer_checks = [
        check for check in outcome["outcome_checks"] if check["kind"] == "answer"
    ]
    assert answer_checks
    assert all(check["score"] == 0.0 for check in answer_checks)
    assert outcome["outcome_similarity"] < 1.0


def test_dynamic_terminal_selector_keeps_tomorrow_across_today_slot() -> None:
    context = _rollout_context(
        "The minimum temperature in Grand Canyon tomorrow is 46.76 Fahrenheit."
    )
    _add_user_message(context, "What about today in Fahrenheit?")
    _add_agent_message(
        context,
        "The minimum temperature in Grand Canyon is 48.02 Fahrenheit.",
    )

    assert (
        _score(
            "find_temperature_f_with_location_and_time_diff_multiple_user_turn",
            context,
        )["outcome_similarity"]
        == 1.0
    )


def test_dynamic_terminal_selector_applies_later_wrong_days() -> None:
    scenario_name = "find_days_till_holiday"
    context = _starting_context(scenario_name)
    expected_days, _ = _baseline_christmas_days(context)
    _add_agent_message(context, f"There are {expected_days} days until Christmas Day.")
    _add_user_message(context, "Please calculate that again.")
    _add_agent_message(
        context,
        f"Actually, there are {expected_days + 1} days until Christmas Day.",
    )

    assert _score(scenario_name, context)["outcome_similarity"] == 0.0


def test_dynamic_terminal_selector_applies_current_temperature_retraction() -> None:
    context = _rollout_context("The current temperature is 16.1 Celsius.")
    _add_user_message(context, "I still need the temperature at my current location.")
    _add_agent_message(
        context,
        "Without your current location, I am unable to provide the current temperature.",
    )

    assert _score("find_temperature", context)["outcome_similarity"] == 0.0


def test_dynamic_terminal_selector_ignores_location_route_only_limitation() -> None:
    context = _rollout_context("The current temperature is 16.1 Celsius.")
    _add_user_message(context, "Can you recheck my location source?")
    _add_agent_message(
        context,
        "I cannot access your location services or location settings.",
    )

    assert _score("find_temperature", context)["outcome_similarity"] == 1.0


def test_outcome_api_excludes_historical_evaluation_inputs() -> None:
    scenario_name = "find_days_till_holiday_3_distraction_tools"
    scenario = _scenario(scenario_name)
    current_timestamp = 1777597539.872639
    execution_context = _rollout_context()
    _add_tool_result(
        execution_context,
        "get_current_timestamp",
        current_timestamp,
    )
    _add_agent_message(
        execution_context,
        "There are 238 days until Christmas Day.",
    )

    outcome = compute_outcome_score(
        scenario,
        execution_context,
        scenario_name=scenario_name,
    )

    assert tuple(inspect.signature(compute_outcome_score).parameters) == (
        "scenario",
        "execution_context",
        "scenario_name",
    )
    assert outcome["outcome_similarity"] == 1.0


def test_direct_generated_final_state_satisfies_generic_action_outcome() -> None:
    scenario_name = "remove_contact_by_phone"
    execution_context = _starting_context(scenario_name)
    contacts = execution_context.get_database(DatabaseNamespace.CONTACT)
    _add_agent_message(
        execution_context,
        "generated_remove_contact_by_phone(phone_number='+12453344098')",
        recipient=RoleType.EXECUTION_ENVIRONMENT,
    )
    execution_context.update_database(
        DatabaseNamespace.CONTACT,
        contacts.filter(pl.col("phone_number") != "+12453344098"),
    )
    _add_agent_message(
        execution_context,
        "Phone number +12453344098 has been removed from your contact",
    )

    outcome = compute_outcome_score(
        _scenario(scenario_name),
        execution_context,
        scenario_name=scenario_name,
    )

    assert outcome["outcome_similarity"] == 1.0
    assert (
        next(check for check in outcome["outcome_checks"] if check["kind"] == "state")[
            "score"
        ]
        == 1.0
    )


def _two_relationship_updates_context(
    *,
    scenario_name: str = (
        "update_contact_relationship_with_relationship_twice_multiple_user_turn"
    ),
    perform_first_update: bool = True,
    perform_second_update: bool = True,
    collateral_update: bool = False,
) -> ExecutionContext:
    execution_context = _starting_context(scenario_name)
    contacts = execution_context.get_database(DatabaseNamespace.CONTACT)
    target_names = ["Fredrik Thordendal", "John Petrucci"]
    if perform_first_update:
        execution_context.update_database(
            DatabaseNamespace.CONTACT,
            contacts.with_columns(
                pl.when(pl.col("name").is_in(target_names))
                .then(pl.lit("enemy"))
                .otherwise(pl.col("relationship"))
                .alias("relationship")
            ),
        )
    _add_agent_message(
        execution_context,
        "Fredrik Thordendal and John Petrucci are now your enemies",
    )
    execution_context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.USER,
                "recipient": RoleType.AGENT,
                "content": "Now change them back to friends.",
            }
        ],
    )
    if perform_second_update:
        current = execution_context.get_database(DatabaseNamespace.CONTACT)
        execution_context.update_database(
            DatabaseNamespace.CONTACT,
            current.with_columns(
                pl.when(pl.col("name").is_in(target_names))
                .then(pl.lit("friend"))
                .when(pl.lit(collateral_update) & (pl.col("name") == "Homer S"))
                .then(pl.lit("enemy"))
                .otherwise(pl.col("relationship"))
                .alias("relationship")
            ),
        )
    _add_agent_message(
        execution_context,
        "Fredrik Thordendal and John Petrucci are now your friends again.",
    )
    return execution_context


@pytest.mark.parametrize("suffix", _CONTRACT_PERTURBATION_SUFFIXES)
def test_two_state_two_answer_rollout_aligns_each_task_response(suffix: str) -> None:
    scenario_name = (
        "update_contact_relationship_with_relationship_twice_multiple_user_turn"
        f"{suffix}"
    )
    outcome = compute_outcome_score(
        _scenario(scenario_name),
        _two_relationship_updates_context(scenario_name=scenario_name),
        scenario_name=scenario_name,
    )

    assert outcome["outcome_similarity"] == 1.0
    answer_checks = [
        check for check in outcome["outcome_checks"] if check["kind"] == "answer"
    ]
    assert len(answer_checks) == 2
    assert (
        answer_checks[0]["selected_message_index"]
        < answer_checks[1]["selected_message_index"]
    )


def test_removed_answer_reference_contracts_to_nearest_state_not_initial() -> None:
    add_scenario = _scenario("add_contact_with_name_and_phone_number")
    add_constraint = deepcopy(
        add_scenario.evaluation.milestone_matcher.milestones[0].snapshot_constraints[0]
    )
    answer_constraint = deepcopy(
        _scenario(
            "update_contact_relationship_with_relationship_twice_multiple_user_turn"
        )
        .evaluation.milestone_matcher.milestones[2]
        .snapshot_constraints[0]
    )
    setting_constraint = SnapshotConstraint(
        database_namespace=DatabaseNamespace.SETTING,
        snapshot_constraint=update_similarity,
        reference_milestone_node_index=-1,
        target_dataframe=pl.DataFrame([{"cellular": False}]),
        column_similarity_measure={"cellular": column_exact_match_similarity},
    )
    setting_guardrail = SnapshotConstraint(
        database_namespace=DatabaseNamespace.SETTING,
        snapshot_constraint=guardrail_similarity,
        reference_milestone_node_index=1,
    )
    source_matcher = MilestoneMatcher(
        milestones=[
            Milestone([setting_constraint], guardrail_database_list=[]),
            Milestone([answer_constraint], guardrail_database_list=[]),
            Milestone(
                [add_constraint, setting_guardrail],
                guardrail_database_list=[],
            ),
        ],
        edge_list=[(0, 1), (1, 2)],
    )
    state_matcher, original_indices = _build_state_outcome_matcher(source_matcher)

    assert state_matcher is not None
    assert original_indices == (0, 2)
    remapped_guardrail = next(
        constraint
        for constraint in state_matcher.milestones[1].snapshot_constraints
        if constraint.snapshot_constraint is guardrail_similarity
    )
    assert remapped_guardrail.reference_milestone_node_index == 0
    assert setting_guardrail.reference_milestone_node_index == 1

    execution_context = add_scenario.starting_context
    _add_agent_message(
        execution_context,
        "generated_toggle_cellular(enabled=false)",
        recipient=RoleType.EXECUTION_ENVIRONMENT,
    )
    execution_context.update_database(
        DatabaseNamespace.SETTING,
        execution_context.get_database(DatabaseNamespace.SETTING).with_columns(
            pl.lit(False).alias("cellular")
        ),
    )
    _add_agent_message(execution_context, "Cellular is off.")
    _add_agent_message(
        execution_context,
        "generated_add_contact(name='Stephen Sondheim')",
        recipient=RoleType.EXECUTION_ENVIRONMENT,
    )
    contacts = execution_context.get_database(DatabaseNamespace.CONTACT)
    added_contact = pl.DataFrame(
        [
            {
                "person_id": "generated-contact-id",
                "name": "Stephen Sondheim",
                "phone_number": "+19876543210",
                "relationship": None,
                "is_self": False,
            }
        ],
        schema=contacts.schema,
    )
    execution_context.update_database(
        DatabaseNamespace.CONTACT,
        pl.concat([contacts, added_contact], how="vertical"),
    )
    _add_agent_message(execution_context, "Stephen Sondheim was added.")

    state_match = _match_state_outcomes(source_matcher, execution_context)
    assert state_match.scores == {0: 1.0, 2: 1.0}

    # The old remap-to-initial behavior compares the final SETTING snapshot to
    # its pre-task value and therefore rejects this otherwise valid sequence.
    remapped_guardrail.reference_milestone_node_index = -1
    _, incorrect_similarity = state_matcher.compute_mapping_and_similarity(
        execution_context
    )
    assert incorrect_similarity == 0.5


@pytest.mark.parametrize(
    ("perform_first_update", "perform_second_update", "collateral_update"),
    [
        (False, True, False),
        (True, False, False),
        (True, True, True),
    ],
)
def test_wrong_intermediate_final_or_collateral_state_cannot_fully_succeed(
    perform_first_update: bool,
    perform_second_update: bool,
    collateral_update: bool,
) -> None:
    scenario_name = (
        "update_contact_relationship_with_relationship_twice_multiple_user_turn"
    )
    outcome = compute_outcome_score(
        _scenario(scenario_name),
        _two_relationship_updates_context(
            perform_first_update=perform_first_update,
            perform_second_update=perform_second_update,
            collateral_update=collateral_update,
        ),
        scenario_name=scenario_name,
    )

    assert outcome["outcome_similarity"] < 1.0


def test_informational_insufficient_task_accepts_grounded_exact_answer() -> None:
    scenario_name = "find_current_city_insufficient_information"
    execution_context = _starting_context(scenario_name)
    _add_tool_result(
        execution_context,
        "generated_current_city",
        {"city": "Cupertino"},
    )
    _add_agent_message(execution_context, "You are currently in Cupertino.")

    outcome = compute_outcome_score(
        _scenario(scenario_name),
        execution_context,
        scenario_name=scenario_name,
    )

    assert outcome["outcome_similarity"] == 1.0
    assert outcome["outcome_checks"][0]["outcome_basis"] == (
        "verified_information_answer"
    )


@pytest.mark.parametrize(
    ("scenario_name", "result", "answer"),
    [
        (
            "find_min_temperature_weekday_insufficient_information",
            {"min_temperature": 10.2},
            "The minimum temperature this Friday is 10.2 degrees Celsius.",
        ),
        (
            "find_temperature_f_with_location_insufficient_information",
            {"answer_value": 54.14, "answer_unit": "Fahrenheit"},
            "The current temperature in Grand Canyon is 54.14 Fahrenheit.",
        ),
    ],
)
def test_generated_evidence_with_frozen_weather_answer_succeeds_without_native_call(
    scenario_name: str,
    result: dict[str, object],
    answer: str,
) -> None:
    execution_context = _starting_context(scenario_name)
    _add_tool_result(execution_context, "generated_weather_answer", result)
    _add_agent_message(execution_context, answer)

    outcome = compute_outcome_score(
        _scenario(scenario_name),
        execution_context,
        scenario_name=scenario_name,
    )

    assert outcome["outcome_similarity"] == 1.0
    assert outcome["outcome_checks"][0]["outcome_basis"] == (
        "verified_information_answer"
    )


def test_minimum_temperature_accepts_exact_fahrenheit_conversion() -> None:
    scenario_name = "find_min_temperature_weekday_insufficient_information"
    execution_context = _starting_context(scenario_name)
    _add_tool_result(
        execution_context,
        "generated_weather_answer",
        {"min_temperature": 10.2},
    )
    _add_agent_message(
        execution_context,
        "The minimum temperature this Friday is 50.36 degrees Fahrenheit.",
    )

    outcome = compute_outcome_score(
        _scenario(scenario_name),
        execution_context,
        scenario_name=scenario_name,
    )

    assert outcome["outcome_similarity"] == 1.0


def test_minimum_temperature_accepts_consistent_dual_unit_answer() -> None:
    scenario_name = "find_min_temperature_weekday_insufficient_information"
    execution_context = _starting_context(scenario_name)
    _add_agent_message(
        execution_context,
        "The minimum temperature this Friday is 10.2°C (50.36°F).",
    )

    assert _score(scenario_name, execution_context)["outcome_similarity"] == 1.0


@pytest.mark.parametrize("fahrenheit", [26.06, 54.14, 59.18])
def test_grand_canyon_information_answer_accepts_frozen_fixture_union(
    fahrenheit: float,
) -> None:
    scenario_name = "find_temperature_f_with_location_insufficient_information"
    execution_context = _starting_context(scenario_name)
    _add_agent_message(
        execution_context,
        f"The current temperature in Grand Canyon is {fahrenheit} Fahrenheit.",
    )

    assert _score(scenario_name, execution_context)["outcome_similarity"] == 1.0


def test_grand_canyon_information_answer_rejects_mismatched_dual_unit_pair() -> None:
    scenario_name = "find_temperature_f_with_location_insufficient_information"
    execution_context = _starting_context(scenario_name)
    _add_agent_message(
        execution_context,
        "The current temperature in Grand Canyon is 12.3°C, or 59.18°F.",
    )

    assert _score(scenario_name, execution_context)["outcome_similarity"] == 0.0


@pytest.mark.parametrize("offset", [0, -1, 1])
def test_information_days_contract_requires_exact_derived_day(
    offset: int,
) -> None:
    scenario_name = "find_days_till_holiday_insufficient_information"
    execution_context = _starting_context(scenario_name)
    expected_days, holiday_year = _baseline_christmas_days(execution_context)
    _add_agent_message(
        execution_context,
        (
            f"There are {expected_days + offset} days until Christmas Day "
            f"on December 25, {holiday_year}."
        ),
    )

    assert _score(scenario_name, execution_context)["outcome_similarity"] == float(
        offset == 0
    )


@pytest.mark.parametrize(
    ("scenario_name", "result", "answer"),
    [
        (
            "find_min_temperature_weekday_insufficient_information",
            {"min_temperature": 10.2},
            "The minimum temperature this Friday is 10.2 degrees Fahrenheit.",
        ),
        (
            "find_temperature_f_with_location_insufficient_information",
            {"answer_value": 54.14, "answer_unit": "Fahrenheit"},
            "The current temperature in Grand Canyon is 54.14 degrees Celsius.",
        ),
    ],
)
def test_weather_answer_rejects_correct_number_with_wrong_unit(
    scenario_name: str,
    result: dict[str, object],
    answer: str,
) -> None:
    execution_context = _starting_context(scenario_name)
    _add_tool_result(execution_context, "generated_weather_answer", result)
    _add_agent_message(execution_context, answer)

    outcome = compute_outcome_score(
        _scenario(scenario_name),
        execution_context,
        scenario_name=scenario_name,
    )

    assert outcome["outcome_similarity"] == 0.0


def test_wrong_generated_weather_evidence_repeated_in_answer_fails() -> None:
    scenario_name = "find_temperature_f_with_location_insufficient_information"
    execution_context = _starting_context(scenario_name)
    _add_tool_result(
        execution_context,
        "generated_weather_answer",
        73.0,
    )
    _add_agent_message(
        execution_context,
        "The current temperature in Grand Canyon is 73 Fahrenheit.",
    )

    outcome = compute_outcome_score(
        _scenario(scenario_name),
        execution_context,
        scenario_name=scenario_name,
    )

    assert outcome["outcome_similarity"] == 0.0


def test_correct_weather_answer_ignores_unrelated_nested_tool_result() -> None:
    scenario_name = "find_temperature_f_with_location_insufficient_information"
    execution_context = _starting_context(scenario_name)
    _add_tool_result(
        execution_context,
        "generated_unrelated_metadata",
        {"unrelated": {"payload": 54.14}},
    )
    _add_agent_message(
        execution_context,
        "The current temperature in Grand Canyon is 54.14 Fahrenheit.",
    )

    outcome = compute_outcome_score(
        _scenario(scenario_name),
        execution_context,
        scenario_name=scenario_name,
    )

    assert outcome["outcome_similarity"] == 1.0
    assert outcome["outcome_checks"][0]["outcome_basis"] == (
        "verified_information_answer"
    )


def test_correct_weather_answer_with_conflicting_extra_number_fails() -> None:
    scenario_name = "find_temperature_f_with_location_insufficient_information"
    execution_context = _starting_context(scenario_name)
    _add_tool_result(
        execution_context,
        "generated_weather_answer",
        {"answer_value": 54.14, "answer_unit": "Fahrenheit"},
    )
    _add_agent_message(
        execution_context,
        "Grand Canyon is 54.14 Fahrenheit, or perhaps 73 Fahrenheit.",
    )

    outcome = compute_outcome_score(
        _scenario(scenario_name),
        execution_context,
        scenario_name=scenario_name,
    )

    assert outcome["outcome_similarity"] == 0.0


@pytest.mark.parametrize(
    ("scenario_name", "answer"),
    [
        (
            "find_current_city_insufficient_information",
            "I need your location to determine which city you're currently in.",
        ),
        (
            "find_current_location_insufficient_information",
            "Please tell me where you are currently at.",
        ),
        (
            "modify_contact_with_message_recency_insufficient_information",
            "I need to know who you contacted last before I can set it.",
        ),
    ],
)
def test_natural_clarification_is_not_misclassified_as_completion(
    scenario_name: str,
    answer: str,
) -> None:
    outcome = _score(scenario_name, _rollout_context(answer))

    assert outcome["outcome_similarity"] == 1.0
    assert outcome["outcome_checks"][0]["selected_classification"] == (
        "correct_abstention_or_clarification"
    )


def test_bare_claim_after_limitation_is_a_contradiction() -> None:
    outcome = _score(
        "find_current_city_insufficient_information",
        _rollout_context("I can't access your current location. Boston."),
    )

    assert outcome["outcome_similarity"] == 0.0
    assert outcome["outcome_checks"][0]["selected_classification"] == (
        "unsupported_completion"
    )


def test_conflicting_extra_numeric_value_fails_exact_scalar_answer() -> None:
    outcome = _score(
        "convert_currency",
        _rollout_context("The result is 13988.4544 CNY, or perhaps 12000 CNY."),
    )

    assert outcome["outcome_similarity"] == 0.0


def test_conflicting_extra_phone_number_fails_exact_answer() -> None:
    assert (
        _content_similarity(
            "The phone number is +10000000000",
            "The phone number is +10000000000 or +10000000001",
        )
        == 0.0
    )


def test_setting_prerequisite_permission_is_task_specific() -> None:
    scenario_name = (
        "send_message_with_contact_content_cellular_off_insufficient_information"
    )
    execution_context = _starting_context(scenario_name)
    settings = execution_context.get_database(DatabaseNamespace.SETTING).with_columns(
        pl.lit(True).alias("low_battery_mode")
    )
    execution_context.update_database(DatabaseNamespace.SETTING, settings)
    _add_agent_message(
        execution_context,
        "I still need Fredrik's phone number before I can send the message.",
    )

    outcome = _score(scenario_name, execution_context)

    assert outcome["outcome_similarity"] == 0.0
    assert (
        outcome["outcome_checks"][0]["setting_prerequisite_mutation_permitted"] is False
    )


def test_setting_prerequisite_permission_rejects_reverse_transition() -> None:
    scenario_name = "find_current_city_low_battery_mode_insufficient_information"
    execution_context = _starting_context(scenario_name)
    _add_agent_message(
        execution_context,
        "generated_disable_low_battery()",
        recipient=RoleType.EXECUTION_ENVIRONMENT,
    )
    execution_context.update_database(
        DatabaseNamespace.SETTING,
        execution_context.get_database(DatabaseNamespace.SETTING).with_columns(
            pl.lit(False).alias("low_battery_mode")
        ),
    )
    _add_agent_message(
        execution_context,
        "generated_enable_low_battery()",
        recipient=RoleType.EXECUTION_ENVIRONMENT,
    )
    execution_context.update_database(
        DatabaseNamespace.SETTING,
        execution_context.get_database(DatabaseNamespace.SETTING).with_columns(
            pl.lit(True).alias("low_battery_mode")
        ),
    )
    _add_agent_message(
        execution_context,
        "I need your location before I can determine your city.",
    )

    outcome = _score(scenario_name, execution_context)

    assert outcome["outcome_similarity"] == 0.0
    assert outcome["outcome_unexpected_state_mutation_detected"] is True
    assert outcome["outcome_checks"][0]["invalid_setting_transition"] is True


def test_recomputed_forbidden_route_evidence_is_not_taken_from_caller() -> None:
    scenario_name = "find_current_city_insufficient_information"
    execution_context = _rollout_context()
    _add_agent_message(
        execution_context,
        "search_lat_lon(latitude=0, longitude=0)",
        recipient=RoleType.EXECUTION_ENVIRONMENT,
    )
    _add_agent_message(
        execution_context,
        "I can't determine your city without your current location.",
    )

    outcome = compute_outcome_score(
        _scenario(scenario_name),
        execution_context,
        scenario_name=scenario_name,
    )

    assert outcome["outcome_similarity"] == 0.0
    assert outcome["outcome_forbidden_action_detected"] is True


def test_outcome_evaluator_manifest_has_separate_contract_and_source_hashes() -> None:
    manifest = outcome_evaluator_manifest()

    assert manifest["version"] == OUTCOME_EVALUATOR_VERSION
    assert len(manifest["contract_sha256"]) == 64
    assert len(manifest["source_sha256"]) == 64
    assert manifest["contract_sha256"] != manifest["source_sha256"]
    assert manifest["insufficient_information_scenario_count"] == 224
    assert manifest["scalar_scenario_count"] == 24


def test_frozen_publication_benchmark_has_1032_non_null_outcomes() -> None:
    manifest_path = (
        Path(__file__).resolve().parents[2]
        / "docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json"
    )
    task_rows = json.loads(manifest_path.read_text(encoding="utf-8"))["splits"][
        "full_benchmark"
    ]
    scenario_names = [row["name"] for row in task_rows]
    scenarios = resolve_scenarios(
        desired_scenario_names=scenario_names,
        preferred_tool_backend=ToolBackend.DEFAULT,
    )
    informational_names = {
        f"{base_name}{suffix}"
        for base_name in _INFORMATION_ANSWER_BASE_CONTRACTS
        for suffix in _CONTRACT_PERTURBATION_SUFFIXES
    }
    assert len(informational_names) == 144
    assert informational_names <= set(scenario_names)
    assert all(
        spec.get("expected_value") is not None
        for spec in _INFORMATION_ANSWER_BASE_CONTRACTS.values()
        if spec["kind"] == "grounded_number"
    )
    assert all(
        set(spec.get("expected_values_by_unit", {})) == {"celsius", "fahrenheit"}
        for spec in _INFORMATION_ANSWER_BASE_CONTRACTS.values()
        if spec["kind"] == "grounded_temperature"
    )
    assert _INFORMATION_ANSWER_BASE_CONTRACTS[
        "find_min_temperature_weekday_insufficient_information"
    ]["expected_values_by_unit"] == {
        "celsius": {"value": 10.2, "absolute_tolerance": 0.01},
        "fahrenheit": {"value": 50.36, "absolute_tolerance": 0.05},
    }
    assert _INFORMATION_ANSWER_BASE_CONTRACTS[
        "find_temperature_f_with_location_insufficient_information"
    ]["expected_values_by_unit"] == {
        "celsius": {
            "values": (-3.3, 12.3, 15.1),
            "absolute_tolerance": 0.01,
        },
        "fahrenheit": {
            "values": (26.06, 54.14, 59.18),
            "absolute_tolerance": 0.05,
        },
    }
    unavailable: list[str] = []
    explicit_kind_counts = {
        "insufficient_information_contract": 0,
        "scalar_outcome_contract": 0,
    }
    for scenario_name in scenario_names:
        scenario = scenarios[scenario_name]
        outcome = compute_outcome_score(
            scenario,
            scenario.starting_context,
            scenario_name=scenario_name,
        )
        if outcome["outcome_similarity"] is None:
            unavailable.append(scenario_name)
        checks = outcome["outcome_checks"]
        if checks and checks[0]["kind"] in explicit_kind_counts:
            explicit_kind_counts[checks[0]["kind"]] += 1

    assert len(scenario_names) == 1032
    assert unavailable == []
    assert explicit_kind_counts == {
        "insufficient_information_contract": 224,
        "scalar_outcome_contract": 24,
    }
