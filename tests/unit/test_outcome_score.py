# mypy: ignore-errors
import datetime as dt
import inspect
import json
from copy import deepcopy
from pathlib import Path

import polars as pl
import pytest

from sage_ts.evaluation.outcome_score import (
    _CONTRACT_PERTURBATION_SUFFIXES,
    _INFORMATION_ANSWER_BASE_CONTRACTS,
    OUTCOME_EVALUATOR_VERSION,
    _build_state_outcome_matcher,
    _content_similarity,
    _match_state_outcomes,
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


def _add_tool_result(
    execution_context: ExecutionContext,
    tool_name: str,
    result,
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
                            "arguments": {},
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
                "content": "There are 239 days until Christmas Day.",
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
                "content": "There are 239 days until Christmas Day.",
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


@pytest.mark.parametrize(
    "closure",
    [
        "Of course! Happy to help.",
        "Anytime!",
        "My pleasure!",
        "No worries!",
        "You're very welcome!",
        "Thank you! Let me know if you need anything else.",
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


def test_insufficient_information_requires_every_missing_fact() -> None:
    scenario_name = "find_min_temperature_weekday_insufficient_information"
    assert (
        _score(
            scenario_name,
            _rollout_context("I need your current location."),
        )["outcome_similarity"]
        == 0.0
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
        "There are 239 days until Christmas Day.",
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
        "celsius": {"value": 12.3, "absolute_tolerance": 0.01},
        "fahrenheit": {"value": 54.14, "absolute_tolerance": 0.05},
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
