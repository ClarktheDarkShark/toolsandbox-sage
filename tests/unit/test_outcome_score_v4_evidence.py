# mypy: ignore-errors
"""Focused v4 answer polarity and answer-only contract regressions."""

import json

import polars as pl
import pytest

from sage_ts.evaluation.outcome_score import compute_outcome_score
from tool_sandbox.cli.utils import resolve_scenarios
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


def _starting_context(name: str) -> ExecutionContext:
    return _scenario(name).starting_context


def _rollout_context(answer: str) -> ExecutionContext:
    context = ExecutionContext()
    context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.USER,
                "recipient": RoleType.AGENT,
                "content": "Publication benchmark request",
            },
            {
                "sender": RoleType.AGENT,
                "recipient": RoleType.USER,
                "content": answer,
            },
        ],
    )
    return context


def _add_agent_message(
    context: ExecutionContext,
    content: str,
    *,
    recipient: RoleType = RoleType.USER,
) -> None:
    context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [
            {
                "sender": RoleType.AGENT,
                "recipient": recipient,
                "content": content,
            }
        ],
    )


def _add_tool_result(context: ExecutionContext, tool_name: str, result) -> None:
    context.add_to_database(
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


def _score(name: str, context: ExecutionContext) -> dict:
    return compute_outcome_score(
        _scenario(name),
        context,
        scenario_name=name,
    )


@pytest.mark.parametrize(
    ("scenario_name", "answer", "truth_basis"),
    [
        (
            "find_current_city_insufficient_information",
            "You are currently in Cupertino.",
            "independently_derived_exact_information_answer",
        ),
        (
            "find_distance_with_location_name_insufficient_information",
            "The Golden Gate Bridge is 67.98 kilometers away.",
            "pinned_fixture_distance_contract",
        ),
        (
            "find_min_temperature_weekday_insufficient_information",
            "The minimum temperature this Friday is 10.2 degrees Celsius.",
            "static_information_temperature_contract",
        ),
        (
            "find_temperature_f_with_location_insufficient_information",
            "The current temperature in Grand Canyon is 54.14 Fahrenheit.",
            "pinned_fixture_scenario_contract",
        ),
    ],
)
def test_information_contract_accepts_exact_answer_without_tool_result(
    scenario_name: str,
    answer: str,
    truth_basis: str,
) -> None:
    context = _starting_context(scenario_name)
    _add_agent_message(context, answer)

    outcome = _score(scenario_name, context)

    assert outcome["outcome_similarity"] == 1.0
    check = outcome["outcome_checks"][0]
    assert check["outcome_basis"] == "verified_information_answer"
    assert check["information_answer"]["answer_truth_basis"] == truth_basis


def test_information_answer_does_not_depend_on_tool_result_shape() -> None:
    scenario_name = "find_temperature_f_with_location_insufficient_information"
    context = _starting_context(scenario_name)
    _add_tool_result(
        context,
        "irrelevant_generated_metadata",
        {"unrelated": {"deeply_nested": "not evidence"}},
    )
    _add_agent_message(
        context,
        "The current temperature in Grand Canyon is 54.14 Fahrenheit.",
    )

    assert _score(scenario_name, context)["outcome_similarity"] == 1.0


@pytest.mark.parametrize(
    ("scenario_name", "answer"),
    [
        (
            "find_current_city_insufficient_information",
            "You are not currently in Cupertino.",
        ),
        (
            "find_current_city_insufficient_information",
            "Cupertino is not my current city.",
        ),
        (
            "find_distance_with_location_name_insufficient_information",
            "The Golden Gate Bridge is not 67.98 kilometers away.",
        ),
        (
            "find_temperature_f_with_location_insufficient_information",
            "The current temperature in Grand Canyon is not 54.14 Fahrenheit.",
        ),
        (
            "find_temperature_f_with_location_insufficient_information",
            "54.14 Fahrenheit is not the current temperature in Grand Canyon.",
        ),
        ("convert_currency", "The result is not 13988.4544 CNY."),
        ("convert_currency", "13988.4544 CNY is not the result."),
        (
            "find_thanksgiving_timestamp",
            "1795669200 is not the Thanksgiving timestamp.",
        ),
    ],
)
def test_candidate_specific_negation_fails(
    scenario_name: str,
    answer: str,
) -> None:
    context = (
        _starting_context(scenario_name)
        if "insufficient_information" in scenario_name
        else _rollout_context(answer)
    )
    if "insufficient_information" in scenario_name:
        _add_agent_message(context, answer)

    assert _score(scenario_name, context)["outcome_similarity"] == 0.0


@pytest.mark.parametrize(
    "answer",
    [
        "Maybe your current city is Cupertino.",
        "Your current city is perhaps Cupertino.",
        "Your current city is Cupertino, perhaps.",
        "Your current city is Cupertino: I guess.",
        "Your current city is Cupertino, but actually Boston.",
        "Your city is Cupertino, but you are actually in Boston.",
        "Your current city is unknown: Cupertino.",
        "Cupertino is not necessarily your current city.",
        "Cupertino is unlikely to be your current city.",
        "I doubt that Cupertino is your current city.",
        "Cupertino cannot be your current city.",
        "Cupertino should not be your current city.",
        "Cupertino must not be your current city.",
        "Cupertino need not be your current city.",
        "Cupertino is definitely not your current city.",
        "Cupertino is very unlikely to be your current city.",
        "Cupertino seems unlikely to be your current city.",
        "Cupertino isn't your current city.",
        "Cupertino is presumably your current city.",
        "It is possible that Cupertino is your current city.",
        "I did not guess: Cupertino is your current city.",
    ],
)
def test_text_answer_hedges_and_post_candidate_corrections_fail(answer: str) -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, answer)

    assert _score(scenario_name, context)["outcome_similarity"] == 0.0


@pytest.mark.parametrize(
    "answer",
    [
        "The result is maybe 13988.4544 CNY.",
        "The result is 13988.4544 CNY, perhaps.",
        "The result is 13988.4544 CNY: I guess.",
        "The result is 13988.4544 CNY, but actually 12000 CNY.",
        "13988.4544 CNY is not necessarily the result.",
        "13988.4544 CNY might not be the result.",
        "13988.4544 CNY is unlikely to be the result.",
        "I doubt the result is 13988.4544 CNY.",
        "13988.4544 CNY cannot be the result.",
        "13988.4544 CNY should not be the result.",
        "13988.4544 CNY must not be the result.",
        "13988.4544 CNY need not be the result.",
        "13988.4544 CNY is definitely not the result.",
        "13988.4544 CNY is very unlikely to be the result.",
        "13988.4544 CNY seems unlikely to be the result.",
        "13988.4544 CNY isn't the result.",
        "The result is 13988.4544 CNY. I doubt it.",
        "The result is 13988.4544 CNY. It might be something else.",
    ],
)
def test_scalar_answer_hedges_and_corrections_fail(answer: str) -> None:
    assert (
        _score("convert_currency", _rollout_context(answer))["outcome_similarity"]
        == 0.0
    )


@pytest.mark.parametrize(
    "answer",
    [
        "It is not Boston; your current city is Cupertino.",
        "The city is not Boston, it is Cupertino.",
        "The city isn't Boston, it's Cupertino.",
        "The answer is not Boston, rather Cupertino.",
        "Your current city is Cupertino, not Boston.",
        "Your city is Cupertino, actually.",
        "Your city is Cupertino. Actually, that is correct.",
        "Your city is Cupertino. No correction is needed.",
        "Your city is Cupertino. On reflection, that is right.",
        "Your city is Boston. Correction: Cupertino.",
    ],
)
def test_candidate_scoping_preserves_positive_contrast(answer: str) -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, answer)

    assert _score(scenario_name, context)["outcome_similarity"] == 1.0


@pytest.mark.parametrize(
    "answer",
    [
        (
            "I couldn't determine it natively, but a generated tool found the "
            "city is Cupertino."
        ),
        (
            "I cannot determine it natively, but an external source says your "
            "city is Cupertino."
        ),
    ],
)
def test_explicitly_resolved_prior_limitation_allows_exact_answer(answer: str) -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, answer)

    assert _score(scenario_name, context)["outcome_similarity"] == 1.0


@pytest.mark.parametrize("punctuation", [",", ":", ";"])
def test_unresolved_limitation_before_answer_fails_across_punctuation(
    punctuation: str,
) -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(
        context,
        f"I cannot determine it{punctuation} Cupertino.",
    )

    assert _score(scenario_name, context)["outcome_similarity"] == 0.0


def test_unresolved_limitation_cannot_be_hidden_by_a_filler_clause() -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(
        context,
        "I cannot determine it. Sorry about that. Cupertino.",
    )

    assert _score(scenario_name, context)["outcome_similarity"] == 0.0


def test_epistemic_negation_is_not_mistaken_for_positive_contrast() -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, "I do not know, it is Cupertino.")

    assert _score(scenario_name, context)["outcome_similarity"] == 0.0


def test_grounded_text_requires_a_whole_phrase_match() -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, "Cupertinoville is your city.")

    assert _score(scenario_name, context)["outcome_similarity"] == 0.0


@pytest.mark.parametrize(
    "answer",
    [
        "I do not need your current location.",
        "I don't need your current location because I already know it.",
        "I don't lack your current location.",
        "I already know your current location.",
        "I can access your current location.",
    ],
)
def test_abstention_requires_positive_scoped_missing_information(answer: str) -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, answer)

    assert _score(scenario_name, context)["outcome_similarity"] == 0.0


@pytest.mark.parametrize(
    "answer",
    [
        "I do not know your current location.",
        "I have no access to your current location.",
        "I have insufficient information about your current location.",
        "I need your current location before I can determine your city.",
        "Please share your current location or coordinates.",
    ],
)
def test_positive_scoped_missing_information_still_passes(answer: str) -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, answer)

    assert _score(scenario_name, context)["outcome_similarity"] == 1.0


def test_generated_terminal_action_remains_a_positive_control() -> None:
    scenario_name = (
        "remove_contact_by_phone_no_search_contacts_insufficient_information"
    )
    context = _starting_context(scenario_name)
    contacts = context.get_database(DatabaseNamespace.CONTACT)
    _add_agent_message(
        context,
        "generated_remove_target_contact(phone_number='+12453344098')",
        recipient=RoleType.EXECUTION_ENVIRONMENT,
    )
    context.update_database(
        DatabaseNamespace.CONTACT,
        contacts.filter(pl.col("phone_number") != "+12453344098"),
    )
    _add_agent_message(context, "Done.")

    outcome = _score(scenario_name, context)

    assert outcome["outcome_similarity"] == 1.0
    assert outcome["outcome_checks"][0]["outcome_basis"] == (
        "verified_state_completion"
    )


@pytest.mark.parametrize(
    "answer",
    [
        "I need not know your current location.",
        "I require not knowing your current location.",
        "I am not missing your current location.",
        "I'm not missing your current location.",
        "I lack no information about your current location.",
        "I am not unable to access your current location.",
        "I am not without your current location.",
        "It is false that I lack your current location.",
    ],
)
def test_negated_missing_information_does_not_count_as_abstention(answer: str) -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, answer)

    assert _score(scenario_name, context)["outcome_similarity"] == 0.0


@pytest.mark.parametrize(
    "answer",
    [
        "I know that I lack your current location.",
        "I know I am missing your current location.",
        (
            "I'm unable to determine your current city without latitude, longitude, "
            "or an address. Please check back when you can share one."
        ),
        (
            "I'm unable to determine your current city without latitude, longitude, "
            "or a nearby landmark. You can provide one from Settings."
        ),
    ],
)
def test_positive_missing_information_and_guidance_remain_valid(answer: str) -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, answer)

    assert _score(scenario_name, context)["outcome_similarity"] == 1.0


@pytest.mark.parametrize(
    ("scenario_name", "answer"),
    [
        (
            "find_current_city_insufficient_information",
            "I can determine your city without your current location.",
        ),
        (
            "find_distance_with_location_name_insufficient_information",
            "I can calculate the distance without your current location.",
        ),
        (
            "send_message_with_contact_content_cellular_off_insufficient_information",
            "I can send the message without a phone number.",
        ),
        (
            "find_current_city_insufficient_information",
            "Without your location, I can still determine your city.",
        ),
        (
            "find_current_city_insufficient_information",
            "Without your location, I can't whistle.",
        ),
        (
            "find_current_city_insufficient_information",
            "Without your location, I can't send a message.",
        ),
    ],
)
def test_without_does_not_turn_capability_or_unrelated_limits_into_abstention(
    scenario_name: str,
    answer: str,
) -> None:
    context = _starting_context(scenario_name)
    _add_agent_message(context, answer)

    assert _score(scenario_name, context)["outcome_similarity"] == 0.0


@pytest.mark.parametrize(
    ("scenario_name", "answer"),
    [
        (
            "find_current_city_insufficient_information",
            "Without your current location, I can't determine your city.",
        ),
        (
            "find_distance_with_location_name_insufficient_information",
            "Without your current location; I can't calculate the distance.",
        ),
        (
            "send_message_with_contact_content_cellular_off_insufficient_information",
            "Without his phone number, I can't send the message.",
        ),
        (
            "remove_contact_by_phone_no_remove_contact_insufficient_information",
            (
                "Without the ability to remove or update the contact directly, "
                "I can't complete this request."
            ),
        ),
    ],
)
def test_separated_without_reason_requires_matching_task_limitation(
    scenario_name: str,
    answer: str,
) -> None:
    context = _starting_context(scenario_name)
    _add_agent_message(context, answer)

    assert _score(scenario_name, context)["outcome_similarity"] == 1.0


@pytest.mark.parametrize(
    ("scenario_name", "answer"),
    [
        (
            "find_distance_with_location_name_insufficient_information_3_distraction_tools_arg_description_scrambled",
            (
                "I understand. Unfortunately, without a location or coordinates, "
                "I'm unable to calculate the distance to the Golden Gate Bridge. "
                "If you find your location later, feel free to reach out, and I can "
                "assist you then."
            ),
        ),
        (
            "send_message_with_contact_content_cellular_off_insufficient_information_3_distraction_tools_arg_type_scrambled",
            (
                "I'm unable to send the message without a phone number. If you "
                "obtain the number later, feel free to share it with me."
            ),
        ),
        (
            "find_temperature_f_with_location_insufficient_information",
            (
                "I couldn't retrieve the current temperature for the Grand Canyon. "
                "Please check a weather website such as weather.com, or use a "
                "weather app for the most accurate and updated temperature information."
            ),
        ),
        (
            "find_current_city_insufficient_information_10_distraction_tools",
            (
                "Unfortunately, I can't directly check or refresh the settings beyond "
                "enabling location services, which are already active. If the location "
                "data is still not coming through, it may be best to check your device's "
                "settings manually."
            ),
        ),
        (
            "remove_contact_by_phone_no_remove_contact_insufficient_information_alt_3_distraction_tools_tool_name_scrambled",
            (
                "It appears that I am unable to delete the contact with the current "
                "tools available. I recommend manually deleting the contact through "
                "your device if possible."
            ),
        ),
        (
            "send_message_with_contact_content_cellular_off_insufficient_information_alt_3_distraction_tools_tool_name_scrambled",
            (
                "That's correct; without additional information to identify Fredrik "
                "Thordendal's contact details, I can't proceed with the task. If you "
                "have any other requests, I'm here to assist!"
            ),
        ),
        (
            "find_current_location_low_battery_mode_insufficient_information_10_distraction_tools",
            (
                "I'm unable to determine your exact location without coordinates or a "
                "specific address. If you're in a location where you can access settings, "
                "you might manually check your device for GPS or location information. "
                "Is there anything else you would like to know?"
            ),
        ),
        (
            "send_message_with_contact_content_cellular_off_insufficient_information_alt_3_distraction_tools_arg_type_scrambled",
            (
                "I currently don't have access to check contacts or look up phone "
                "numbers. Therefore, I'm unable to send a message to Fredrik "
                "Thordendal without a phone number."
            ),
        ),
    ],
)
def test_preserved_limitation_advice_is_not_a_completion(
    scenario_name: str,
    answer: str,
) -> None:
    context = _starting_context(scenario_name)
    _add_agent_message(context, answer)

    outcome = _score(scenario_name, context)

    assert outcome["outcome_similarity"] == 1.0
    assert outcome["outcome_checks"][0]["selected_classification"] == (
        "correct_abstention_or_clarification"
    )


def test_preserved_wrong_numeric_completion_after_advice_remains_rejected() -> None:
    scenario_name = (
        "find_days_till_holiday_insufficient_information_"
        "3_distraction_tools_arg_type_scrambled"
    )
    context = _starting_context(scenario_name)
    _add_agent_message(
        context,
        (
            "After checking again, there are indeed 1177 days until Christmas Day. "
            "If you'd like me to check specific current date information, please "
            "provide the date you want to reference."
        ),
    )

    outcome = _score(scenario_name, context)

    assert outcome["outcome_similarity"] == 0.0
    assert outcome["outcome_checks"][0]["selected_classification"] == (
        "unsupported_completion"
    )


@pytest.mark.parametrize(
    "answer",
    [
        "I can't determine your city without your location. Boston.",
        "I can't determine your city without your location. Your city is Boston.",
    ],
)
def test_genuine_post_limitation_wrong_city_remains_rejected(answer: str) -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, answer)

    assert _score(scenario_name, context)["outcome_similarity"] == 0.0


@pytest.mark.parametrize(
    "answer",
    [
        "Your current city may be Cupertino.",
        "Your current city might be Cupertino.",
        "Your current city could be Cupertino.",
        "Your current city is probably Cupertino.",
        "Your current city is likely Cupertino.",
        "Your current city is apparently Cupertino.",
        "Is your current city Cupertino?",
        "If your current city were Cupertino, this would be easy.",
        "Cupertino?",
        "Cupertino is one possibility.",
        "Either Cupertino or Boston is possible.",
        "Your current city is Cupertino or Boston.",
        "It is definitely not Cupertino.",
        "It is certainly not Cupertino.",
        "There is no evidence that Cupertino is your current city.",
        "It is doubtful that Cupertino is your current city.",
        "Supposedly Cupertino is your current city.",
        "I might not know your current city. Cupertino.",
        "I'm not sure of your current city. Cupertino.",
        "I should not guess your current city. Cupertino.",
        "I am uncertain about your current city. Cupertino.",
    ],
)
def test_nonassertive_text_candidates_fail(answer: str) -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, answer)

    assert _score(scenario_name, context)["outcome_similarity"] == 0.0


@pytest.mark.parametrize(
    "answer",
    [
        "The Thanksgiving timestamp may be 1795669200.",
        "The Thanksgiving timestamp is probably 1795669200.",
        "Apparently, the Thanksgiving timestamp is 1795669200.",
        "Is the Thanksgiving timestamp 1795669200?",
        "If the Thanksgiving timestamp were 1795669200, that would work.",
        "1795669200 might be the Thanksgiving timestamp.",
        "It is definitely not 1795669200, the Thanksgiving timestamp.",
        "It is certainly not 1795669200, the Thanksgiving timestamp.",
        "There is no evidence that the Thanksgiving timestamp is 1795669200.",
        "It is doubtful that the Thanksgiving timestamp is 1795669200.",
        "Supposedly the Thanksgiving timestamp is 1795669200.",
        "The Thanksgiving timestamp is 1795669200. That may be wrong.",
        "The Thanksgiving timestamp is 1795669200. Probably not.",
    ],
)
def test_nonassertive_scalar_candidates_fail(answer: str) -> None:
    assert (
        _score("find_thanksgiving_timestamp", _rollout_context(answer))[
            "outcome_similarity"
        ]
        == 0.0
    )


@pytest.mark.parametrize(
    "answer",
    [
        "Your current city is Cupertino. Boston actually.",
        "Your current city is Cupertino. The actual city is Boston.",
        "Your current city is Cupertino. Although Boston is also possible.",
        "Your current city is Cupertino. On second thought, Boston.",
        "Your current city is Cupertino. I think Boston.",
        "Your current city is Cupertino. Or maybe Boston.",
        "Your current city is Cupertino. On reflection, Boston.",
        "Your current city is Cupertino. Correction: Boston.",
        "Your current city is Cupertino. Actually, Boston.",
        "Your current city is Cupertino. No, Boston.",
        "Your current city is Cupertino. I retract that; Boston.",
        "Your current city is Cupertino. Maybe Boston.",
        "Your current city is Cupertino. But maybe Boston.",
        "Your current city is Cupertino. Rather Boston.",
        "Your current city is Cupertino. Instead Boston.",
        "Your current city is Cupertino. I was wrong; Boston.",
        "Your current city is Cupertino. Scratch that; Boston.",
        "Your current city is Cupertino. Disregard that; Boston.",
        "Your current city is Cupertino. Maybe not.",
        "Your current city is Cupertino—but I may be wrong.",
        "Your current city is Cupertino. It might be Boston.",
        "Your current city is Cupertino. That may be wrong.",
        "Your current city is Cupertino. Probably Boston.",
        "Your current city is Cupertino. Boston instead.",
        "Your current city is Cupertino. I doubt it.",
    ],
)
def test_later_target_domain_correction_fails(answer: str) -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, answer)

    assert _score(scenario_name, context)["outcome_similarity"] == 0.0


@pytest.mark.parametrize(
    "unrelated_recovery",
    [
        "However, I found my keys.",
        "However, I verified my email.",
        "However, I obtained lunch.",
    ],
)
def test_unrelated_recovery_does_not_clear_prior_limitation(
    unrelated_recovery: str,
) -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(
        context,
        f"I do not know your city. {unrelated_recovery} Cupertino.",
    )

    assert _score(scenario_name, context)["outcome_similarity"] == 0.0


@pytest.mark.parametrize(
    "recovery",
    [
        "I have not found the city.",
        "I never determined the city.",
        "I may have found the city.",
        "If I had found the city.",
        "I found my keys in the city.",
        "The source does not say the city.",
        "The source returned no city.",
    ],
)
def test_nonaffirmative_or_incidental_recovery_does_not_clear_limitation(
    recovery: str,
) -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(
        context,
        f"I cannot determine your city. {recovery} Cupertino.",
    )

    assert _score(scenario_name, context)["outcome_similarity"] == 0.0


def test_targeted_generated_recovery_can_cross_a_sentence_boundary() -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(
        context,
        (
            "I couldn't determine it natively. However, a generated tool found "
            "the city is Cupertino."
        ),
    )

    assert _score(scenario_name, context)["outcome_similarity"] == 1.0


@pytest.mark.parametrize(
    "answer",
    [
        (
            "I couldn't determine it natively. A generated tool found that your "
            "city is Cupertino."
        ),
        (
            "I lacked access initially. I found through another source that your "
            "city is Cupertino."
        ),
        (
            "I could not determine it natively. An external source returned that "
            "your city is Cupertino."
        ),
        (
            "I couldn't determine it. An external source confirms your city is "
            "Cupertino."
        ),
        ("I couldn't determine it. An external source shows your city is Cupertino."),
    ],
)
def test_targeted_cross_sentence_recovery_needs_no_contrast_marker(answer: str) -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, answer)

    assert _score(scenario_name, context)["outcome_similarity"] == 1.0


def test_abstention_may_end_with_an_offer_to_assist() -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(
        context,
        "I don't know your current location. Once you tell me, I can help.",
    )

    assert _score(scenario_name, context)["outcome_similarity"] == 1.0


@pytest.mark.parametrize(
    ("scenario_name", "answer", "expected"),
    [
        (
            "find_thanksgiving_timestamp",
            "The Thanksgiving timestamp is unknown. My lottery number is 1795669200.",
            0.0,
        ),
        (
            "find_thanksgiving_timestamp",
            "The Thanksgiving timestamp is 1795669200.",
            1.0,
        ),
        (
            "find_distance_with_location_name_insufficient_information",
            "The Golden Gate Bridge distance is unknown. My serial is 67.98 km.",
            0.0,
        ),
        (
            "find_distance_with_location_name_insufficient_information",
            "The Golden Gate Bridge is 67.98 km away.",
            1.0,
        ),
        (
            "find_distance_with_location_name_insufficient_information",
            "The bridge is 67.98 km away.",
            0.0,
        ),
        (
            "find_distance_with_location_name_insufficient_information",
            "The Golden Gate is 67.98 km away.",
            0.0,
        ),
    ],
)
def test_numeric_context_is_candidate_local_and_exact(
    scenario_name: str,
    answer: str,
    expected: float,
) -> None:
    context = (
        _starting_context(scenario_name)
        if "insufficient_information" in scenario_name
        else _rollout_context(answer)
    )
    if "insufficient_information" in scenario_name:
        _add_agent_message(context, answer)

    assert _score(scenario_name, context)["outcome_similarity"] == expected


def test_baseline_reminder_answer_requires_a_full_phrase_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TOOL_SANDBOX_FIXED_NOW_TIMESTAMP", "1784832588")
    scenario_name = (
        "search_reminder_with_creation_recency_yesterday_insufficient_information"
    )
    positive = _starting_context(scenario_name)
    _add_agent_message(positive, "Buy tickets for Merrily next week")
    negative = _starting_context(scenario_name)
    _add_agent_message(negative, "Buy tickets for Merrily next weekend")

    assert _score(scenario_name, positive)["outcome_similarity"] == 1.0
    assert _score(scenario_name, negative)["outcome_similarity"] == 0.0


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("Your current location is {lat}, {lon}.", 1.0),
        ("Latitude is {lat}; longitude is {lon}.", 1.0),
        ("My lucky numbers are {lat} and {lon}.", 0.0),
        ("Longitude is {lat}; latitude is {lon}.", 0.0),
        ("Could your current location be {lat}, {lon}?", 0.0),
        ("Your current location may be {lat}, {lon}.", 0.0),
    ],
)
def test_coordinate_answer_context_association_and_polarity(
    template: str,
    expected: float,
) -> None:
    scenario_name = "find_current_location_insufficient_information"
    context = _starting_context(scenario_name)
    settings = context.get_database(DatabaseNamespace.SETTING).to_dicts()[0]
    answer = template.format(
        lat=settings["latitude"],
        lon=settings["longitude"],
    )
    _add_agent_message(context, answer)

    assert _score(scenario_name, context)["outcome_similarity"] == expected


@pytest.mark.parametrize(
    "closure",
    [
        "Have a great day!",
        "Okay, have a great day!",
        "Alright, have a great day!",
        "If you have questions in the future, feel free to ask.",
        "Alright. If you need anything in the future, just let me know!",
        "If you need assistance in the future, don't hesitate to reach out.",
        "If you think of anything else, don't hesitate to ask. Have a great day!",
        "If you need further assistance, please let me know.",
        "If you have any more questions, just reach out.",
        "Sounds good.",
        "Just reach out if you need anything else.",
    ],
)
def test_social_closure_retains_earlier_targeted_clarification(closure: str) -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(
        context,
        "I can't determine your city without your current location.",
    )
    _add_agent_message(context, closure)

    assert _score(scenario_name, context)["outcome_similarity"] == 1.0


@pytest.mark.parametrize(
    "later_non_outcome_response",
    [
        (
            "I understand, and I'm here to assist you if you need anything else "
            "in the future."
        ),
        "Sounds good! If you need help later, feel free to reach out.",
        (
            "I understand. If you find the current date and time later or have "
            "other questions, feel free to ask."
        ),
        "I'll be here if you need anything else.",
        (
            "I'm sorry I couldn't help you find the reminder. If you need anything "
            "else in the future, feel free to ask."
        ),
        (
            "I'm sorry I couldn't help locate your reminders. If you need assistance "
            "with anything else, feel free to ask!"
        ),
        "Thanks for your patience.",
        "Sorry for the inconvenience.",
        "You may want to try again later.",
        "I hope this helps.",
        "Good luck.",
        (
            "I'm unable to access the reminders app. If you provide more context, "
            "I'll do my best to help."
        ),
        "The tool is unavailable.",
        "I appreciate your patience.",
        "Thank you for understanding.",
        "Apologies for the trouble.",
        "You can try again later.",
        "Perhaps try again later.",
        "I wish I could help further.",
    ],
)
def test_insufficient_contract_ignores_later_non_outcome_dialogue(
    later_non_outcome_response: str,
) -> None:
    scenario_name = "search_reminder_with_recency_upcoming_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(
        context,
        "I need the current date and time before I can identify the reminder.",
    )
    _add_agent_message(context, later_non_outcome_response)

    outcome = _score(scenario_name, context)
    check = outcome["outcome_checks"][0]

    assert outcome["outcome_similarity"] == 1.0
    assert check["selected_classification"] == ("correct_abstention_or_clarification")
    assert check["selected_message_index"] < context.max_sandbox_message_index


@pytest.mark.parametrize(
    "wrong_outcome",
    [
        "I found it. Your upcoming reminder is Buy milk.",
        "No reminders were found.",
    ],
)
def test_insufficient_contract_later_wrong_outcome_overrides_correct_abstention(
    wrong_outcome: str,
) -> None:
    scenario_name = "search_reminder_with_recency_upcoming_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(
        context,
        "I need the current date and time before I can identify the reminder.",
    )
    _add_agent_message(context, wrong_outcome)

    outcome = _score(scenario_name, context)
    check = outcome["outcome_checks"][0]

    assert outcome["outcome_similarity"] == 0.0
    assert check["selected_classification"] == "unsupported_completion"
    assert check["ignored_later_non_outcome_message_indices"] == []


@pytest.mark.parametrize(
    "retraction",
    [
        "Actually, I have the current date and time after all.",
        "Never mind, the current date and time are available.",
        "That earlier limitation was wrong.",
        "I no longer need the current date and time.",
        "I do not need the current date and time.",
        "Dentist appointment.",
    ],
)
def test_insufficient_contract_does_not_ignore_later_retraction_or_bare_answer(
    retraction: str,
) -> None:
    scenario_name = "search_reminder_with_recency_upcoming_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(
        context,
        "I need the current date and time before I can identify the reminder.",
    )
    _add_agent_message(context, retraction)

    outcome = _score(scenario_name, context)
    check = outcome["outcome_checks"][0]

    assert outcome["outcome_similarity"] == 0.0
    assert check["selected_classification"] in {
        "explicit_retraction_or_incorrect_outcome",
        "incorrect_or_nonspecific_response",
        "unsupported_completion",
    }
    assert check["ignored_later_non_outcome_message_indices"] == []


@pytest.mark.parametrize(
    ("scenario_name", "correct_limitation"),
    [
        (
            "find_current_city_low_battery_mode_insufficient_information_3_distraction_tools_tool_description_scrambled",
            (
                "Location services are enabled, and I have turned on Wi-Fi as well. "
                "However, I still cannot determine your location without specific "
                "coordinates or an active connection to retrieve your location. "
                "Please check if there are any other location services available on "
                "your device."
            ),
        ),
        (
            "send_message_with_contact_content_cellular_off_insufficient_information_alt_3_distraction_tools_tool_description_scrambled",
            (
                "I can only send the message if I have Fredrik Thordendal's phone "
                "number. Unfortunately, without that information, I'm unable to "
                "assist you. If you find his contact details, please share them!"
            ),
        ),
        (
            "find_distance_with_location_name_insufficient_information_alt_3_distraction_tools",
            (
                "I understand, but I'm unable to use other devices or tools to "
                "determine a location. If there's anything else you need that "
                "doesn't require location data, feel free to ask!"
            ),
        ),
    ],
)
def test_insufficient_contract_does_not_treat_limitation_language_as_retraction(
    scenario_name: str,
    correct_limitation: str,
) -> None:
    context = _starting_context(scenario_name)
    _add_agent_message(context, correct_limitation)

    outcome = _score(scenario_name, context)
    check = outcome["outcome_checks"][0]

    assert outcome["outcome_similarity"] == 1.0
    assert check["selected_classification"] == "correct_abstention_or_clarification"


@pytest.mark.parametrize(
    ("scenario_name", "correct_limitation"),
    [
        (
            "find_current_location_low_battery_mode_insufficient_information_3_distraction_tools_tool_description_scrambled",
            (
                "I have turned on location services and Wi-Fi, but I cannot "
                "retrieve your location. Please check if there are any restrictions "
                "or connectivity issues that could be affecting location access."
            ),
        ),
        (
            "find_current_city_low_battery_mode_insufficient_information_3_distraction_tools_arg_description_scrambled",
            (
                "I have enabled location services and Wi-Fi. However, I currently "
                "cannot determine your location. Please check your device settings "
                "or try again later."
            ),
        ),
        (
            "find_current_city_low_battery_mode_insufficient_information_3_distraction_tools_arg_type_scrambled",
            (
                "I have enabled location services and Wi-Fi, but it appears I still "
                "need your coordinates to determine your city. You can try checking "
                "your device's map app for your current location."
            ),
        ),
        (
            "find_current_city_low_battery_mode_insufficient_information_3_distraction_tools_arg_type_scrambled",
            (
                "I have successfully turned off low battery mode and enabled "
                "location services and Wi-Fi. However, I am unable to determine "
                "your city at this moment, likely due to missing location data. "
                "Please try again later to see if your location can be retrieved."
            ),
        ),
        (
            "find_current_city_low_battery_mode_insufficient_information_3_distraction_tools_tool_description_scrambled",
            (
                "I have turned on the Wi-Fi, and location services are enabled. "
                "However, I still need your current latitude and longitude to "
                "determine your city. Since I cannot get the coordinates "
                "automatically, please provide them if you can find out where you are."
            ),
        ),
        (
            "find_current_location_low_battery_mode_insufficient_information_3_distraction_tools",
            (
                "I have enabled location services and Wi-Fi, but I wasn't able to "
                "determine your location. Please check your device settings or try "
                "again later."
            ),
        ),
    ],
)
def test_setup_completion_does_not_override_later_missing_information(
    scenario_name: str,
    correct_limitation: str,
) -> None:
    context = _starting_context(scenario_name)
    _add_agent_message(context, correct_limitation)

    outcome = _score(scenario_name, context)
    check = outcome["outcome_checks"][0]

    assert outcome["outcome_similarity"] == 1.0
    assert check["selected_classification"] == "correct_abstention_or_clarification"


@pytest.mark.parametrize(
    ("answer", "expected_score", "expected_classification"),
    [
        (
            (
                "I need your current location. However, I now have your current "
                "location."
            ),
            0.0,
            "explicit_retraction_or_incorrect_outcome",
        ),
        (
            "I have tried to determine your current location, but still cannot.",
            1.0,
            "correct_abstention_or_clarification",
        ),
        (
            (
                "I have access to Wi-Fi although I cannot determine your current "
                "location."
            ),
            1.0,
            "correct_abstention_or_clarification",
        ),
        (
            ("I need your current location. Your current location is now available."),
            0.0,
            "unsupported_completion",
        ),
        (
            (
                "That earlier limitation was wrong. However, I still need your "
                "current location."
            ),
            1.0,
            "correct_abstention_or_clarification",
        ),
        (
            "I know that your current location is missing.",
            1.0,
            "correct_abstention_or_clarification",
        ),
        (
            "I know your current location, but I cannot whistle.",
            0.0,
            "explicit_retraction_or_incorrect_outcome",
        ),
    ],
)
def test_insufficient_contract_orders_possession_and_anaphoric_limitations(
    answer: str,
    expected_score: float,
    expected_classification: str,
) -> None:
    scenario_name = "find_current_location_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, answer)

    outcome = _score(scenario_name, context)
    check = outcome["outcome_checks"][0]

    assert outcome["outcome_similarity"] == expected_score
    assert check["selected_classification"] == expected_classification


@pytest.mark.parametrize(
    "valid_limitation",
    [
        "I have not been able to determine your current location.",
        "I won't be able to determine your current location.",
        "I haven't been able to determine your current location.",
        "I have yet to determine your current location.",
        "I have failed to determine your current location.",
        "I have tried unsuccessfully to determine your current location.",
        (
            "We have attempted to determine your current location; however, we "
            "are unable to do so."
        ),
        "I tried to determine your current location, but I couldn't do it.",
        "I tried to determine your current location, but had no luck.",
        "I tried to determine your current location, but that wasn't possible.",
        "Your current location was not retrievable.",
        (
            "I cannot determine your current location, though I have access to "
            "location services."
        ),
        (
            "While I have location services enabled, I still cannot determine "
            "your current location."
        ),
        (
            "Even though I have location services enabled, I still cannot "
            "determine your current location."
        ),
        "I have your current location listed as unavailable.",
        "I have confirmed that your current location is unavailable.",
        "I have tried, unsuccessfully, to determine your current location.",
        ("I tried to determine your current location; however, that wasn't possible."),
        "I need your location. I don't know whether I have your current location.",
        (
            "I cannot determine your current location, though I have your location "
            "permissions."
        ),
        (
            "I cannot determine your current location, though I have your location "
            "settings open."
        ),
        ("I have checked whether your current location is available, but it is not."),
        "I possess location permissions, but not your actual current location.",
        ("I tried to retrieve your current location. I remain unable to do so."),
        (
            "I tried to retrieve your current location. Unfortunately, I remain "
            "unable to do so."
        ),
        (
            "I understand. Unfortunately, without location services enabled or a "
            "way to connect, I can't determine your city right now."
        ),
    ],
)
def test_natural_auxiliary_and_anaphoric_limitations_are_valid(
    valid_limitation: str,
) -> None:
    scenario_name = "find_current_location_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, valid_limitation)

    assert _score(scenario_name, context)["outcome_similarity"] == 1.0


@pytest.mark.parametrize(
    "retraction",
    [
        (
            "I need your current location. However, I have now obtained your "
            "current location."
        ),
        ("I need your current location. However, I've obtained your current location."),
        "I need your current location, but I found it.",
        "I need your current location. It is available now.",
        "I need your current location. Turns out I have it.",
        "I need your current location. That is no longer a problem.",
        "I need your current location; correction: I have it.",
        "I need your current location. That is no longer true.",
        "I need your current location. I was mistaken; I have it now.",
        "I need your current location. I found it now.",
        "I need your current location. I managed to obtain them.",
        "I need your current location. Actually, yes I do.",
        "I don't know your current location anymore—actually, yes I do.",
        "I need your current location, but now I can.",
        "I need your current location. I can access them now.",
        "I need your current location. I have found it.",
    ],
)
def test_natural_retractions_invalidate_an_earlier_limitation(
    retraction: str,
) -> None:
    scenario_name = "find_current_location_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, retraction)

    assert _score(scenario_name, context)["outcome_similarity"] == 0.0


def test_tangential_failure_dialogue_does_not_erase_a_correct_outcome() -> None:
    scenario_name = "search_reminder_with_recency_upcoming_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(
        context,
        "I need the current date and time before I can identify the reminder.",
    )
    _add_agent_message(
        context,
        (
            "I currently don't have access to any notes or messages. My capabilities "
            "are limited to reminders and to-dos."
        ),
    )
    _add_agent_message(
        context,
        (
            "I'm sorry I couldn't help you find the reminder. If you need anything "
            "else in the future, feel free to ask."
        ),
    )

    outcome = _score(scenario_name, context)

    assert outcome["outcome_similarity"] == 1.0
    assert outcome["outcome_checks"][0]["ignored_later_non_outcome_message_indices"]


@pytest.mark.parametrize(
    "later_substantive_response",
    [
        "dentist appointment.",
        "dentist appointment is what you have later.",
        "You have a dentist appointment later.",
        "Actually, I can get that information now.",
        "I found another way to proceed.",
        "That is no longer a problem.",
        "The corrected answer is 1160 days.",
        "Location services have been successfully enabled.",
        "The confirmed phone number is 555-0100.",
        "I don't know the answer.",
        "I can help by accessing the reminders app now.",
        "Please tell me the answer is Boston.",
        "Please provide the corrected answer.",
        "We need to correct the answer.",
        (
            "If the item were Buy milk, I could open it. Actual result: You "
            "have a reminder to Look for Company SF tickets. I can help."
        ),
        (
            "If the item were Buy milk, I could open it. Actual result: Look "
            "for Company SF tickets. I can help."
        ),
        (
            "If the item were Buy milk; Actual result: Look for Company SF "
            "tickets; I can help."
        ),
        (
            "If the item were Buy milk\nActual result: Look for Company SF "
            "tickets\nI can help."
        ),
        (
            "If the item were Buy milk, but Actual result: Look for Company "
            "SF tickets, and I can help."
        ),
        ("If the item were Buy milk; Actual result: would call Mom; I can help."),
        ("If the item were Buy milk; Actual result: Will call Mom; I can help."),
        "42.",
        "I was wrong.",
        "The result is unknown.",
        "I can access the reminders app now.",
        "I checked the reminders app.",
        "The tool returned no data.",
        "That did not work.",
        "Sounds good, but I can access the app now.",
        "Try checking manually; I found no reminders.",
        "I'm here to help by accessing the reminders app now.",
        "I understand, and I'm here to help by accessing the reminders app now.",
        "I'll be happy to help by accessing the reminders app now.",
        "Please check the app because I found Boston.",
    ],
)
def test_insufficient_contract_does_not_hide_later_substantive_response(
    later_substantive_response: str,
) -> None:
    scenario_name = "search_reminder_with_recency_upcoming_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(
        context,
        "I need the current date and time before I can identify the reminder.",
    )
    _add_agent_message(context, later_substantive_response)

    outcome = _score(scenario_name, context)
    check = outcome["outcome_checks"][0]

    assert outcome["outcome_similarity"] == 0.0
    assert check["selected_message_index"] == context.max_sandbox_message_index
    assert check["ignored_later_non_outcome_message_indices"] == []


@pytest.mark.parametrize(
    "later_guidance",
    [
        "Try the reminders app.",
        "Open the reminders app.",
        "Check the reminders app.",
        "Use the reminders app.",
        "Visit the reminders app.",
        "Ask again later.",
        "Enable reminders access.",
        "Consider checking manually.",
        "Please provide more context.",
        "If you find the date and time later, feel free to ask.",
        "I'll be happy to help if you have other questions.",
    ],
)
def test_insufficient_contract_ignores_proven_imperative_guidance(
    later_guidance: str,
) -> None:
    scenario_name = "search_reminder_with_recency_upcoming_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(
        context,
        "I need the current date and time before I can identify the reminder.",
    )
    _add_agent_message(context, later_guidance)

    outcome = _score(scenario_name, context)
    check = outcome["outcome_checks"][0]

    assert outcome["outcome_similarity"] == 1.0
    assert check["selected_classification"] == "correct_abstention_or_clarification"
    assert check["ignored_later_non_outcome_message_indices"]


@pytest.mark.parametrize(
    "guidance_only",
    [
        "Please provide more context.",
        "Try checking the reminders app manually.",
        "If you find the date and time later, feel free to ask.",
    ],
)
def test_insufficient_contract_never_turns_guidance_alone_into_success(
    guidance_only: str,
) -> None:
    scenario_name = "search_reminder_with_recency_upcoming_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, guidance_only)

    outcome = _score(scenario_name, context)

    assert outcome["outcome_similarity"] == 0.0


def test_insufficient_contract_retains_verified_answer_before_later_dialogue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TOOL_SANDBOX_FIXED_NOW_TIMESTAMP", "1784832588")
    scenario_name = (
        "search_reminder_with_creation_recency_yesterday_insufficient_information"
    )
    context = _starting_context(scenario_name)
    _add_agent_message(context, "Buy tickets for Merrily next week")
    _add_agent_message(
        context,
        "I understand, and I'm here if you need anything else in the future.",
    )

    outcome = _score(scenario_name, context)
    check = outcome["outcome_checks"][0]

    assert outcome["outcome_similarity"] == 1.0
    assert check["selected_classification"] == "verified_information_answer"
    assert check["ignored_later_non_outcome_message_indices"]


@pytest.mark.parametrize(
    "later_false_claim",
    [
        "You have no reminders set for next week.",
        "You have no reminders set for next month.",
        "You have no reminders set for today.",
    ],
)
def test_insufficient_contract_does_not_ignore_later_false_reminder_claim(
    monkeypatch: pytest.MonkeyPatch,
    later_false_claim: str,
) -> None:
    monkeypatch.setenv("TOOL_SANDBOX_FIXED_NOW_TIMESTAMP", "1784832588")
    scenario_name = "search_reminder_with_recency_upcoming_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, "Buy tickets for Merrily next week")
    _add_agent_message(context, later_false_claim)

    outcome = _score(scenario_name, context)
    check = outcome["outcome_checks"][0]

    assert outcome["outcome_similarity"] == 0.0
    assert check["selected_message_index"] == context.max_sandbox_message_index
    assert check["ignored_later_non_outcome_message_indices"] == []


def test_insufficient_contract_does_not_ignore_first_person_negative_search_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TOOL_SANDBOX_FIXED_NOW_TIMESTAMP", "1784832588")
    scenario_name = (
        "search_reminder_with_creation_recency_yesterday_insufficient_information"
    )
    context = _starting_context(scenario_name)
    _add_agent_message(
        context,
        "Please provide the specific date and time range so I can search safely.",
    )
    _add_agent_message(
        context,
        "I couldn't find any reminders for yesterday. It appears that there are "
        "no entries recorded for that day.",
    )

    outcome = _score(scenario_name, context)
    check = outcome["outcome_checks"][0]

    assert outcome["outcome_similarity"] == 0.0
    assert check["selected_message_index"] == context.max_sandbox_message_index
    assert check["ignored_later_non_outcome_message_indices"] == []


def test_negative_reminder_search_result_is_scoped_to_reminder_contracts() -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(
        context,
        "I don't have access to your location, so I can't determine your city.",
    )
    _add_agent_message(context, "I couldn't find any reminders for yesterday.")

    outcome = _score(scenario_name, context)
    check = outcome["outcome_checks"][0]

    assert outcome["outcome_similarity"] == 1.0
    assert check["selected_classification"] == ("correct_abstention_or_clarification")
    assert check["ignored_later_non_outcome_message_indices"]


def test_negative_reminder_search_result_overrides_valid_limitation() -> None:
    scenario_name = "search_reminder_with_recency_yesterday_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(
        context,
        "I need the current date and time to identify yesterday, but I couldn't "
        "find any reminders for yesterday.",
    )

    outcome = _score(scenario_name, context)

    assert outcome["outcome_similarity"] == 0.0
    assert outcome["outcome_checks"][0]["selected_classification"] == (
        "unsupported_completion"
    )


@pytest.mark.parametrize(
    "positive_claim",
    [
        "I am not without your current location, so I cannot proceed with this "
        "request.",
        "I do have your current location, so I cannot proceed with this request.",
        "I am not without your current location or coordinates, although I cannot "
        "proceed with this request.",
        "It is false that I am without your current location, so I cannot proceed "
        "with this request.",
        "I am by no means without your current location, so I cannot proceed with "
        "this request.",
        "I am not without the precise and currently available device-derived "
        "geographic information that supplies your current location, so I cannot "
        "proceed with this request.",
    ],
)
def test_not_without_required_datum_is_not_a_missing_information_claim(
    positive_claim: str,
) -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, positive_claim)

    outcome = _score(scenario_name, context)

    assert outcome["outcome_similarity"] == 0.0
    assert outcome["outcome_checks"][0]["selected_classification"] != (
        "correct_abstention_or_clarification"
    )


@pytest.mark.parametrize(
    ("scenario_name", "limitation"),
    [
        (
            "find_current_city_insufficient_information",
            "I am not without a phone number, and I cannot proceed without your "
            "current location.",
        ),
        (
            "find_current_city_insufficient_information",
            "I am not without an outdated location, and I cannot proceed without "
            "your current location.",
        ),
        (
            "send_message_with_contact_content_cellular_off_insufficient_information",
            "I am not without Fredrik's email, and I cannot proceed without his "
            "phone number.",
        ),
        (
            "search_reminder_with_recency_yesterday_insufficient_information",
            "I am not without yesterday's calendar, and I cannot proceed without "
            "the current date and time.",
        ),
    ],
)
def test_unrelated_not_without_does_not_hide_later_real_limitation(
    scenario_name: str,
    limitation: str,
) -> None:
    context = _starting_context(scenario_name)
    _add_agent_message(context, limitation)

    outcome = _score(scenario_name, context)

    assert outcome["outcome_similarity"] == 1.0
    assert outcome["outcome_checks"][0]["selected_classification"] == (
        "correct_abstention_or_clarification"
    )


@pytest.mark.parametrize(
    ("answer", "expected_score"),
    [
        (
            "I'm unable to do so without a valid phone number for Fredrik Thordendal.",
            1.0,
        ),
        ("I can't do so without Fredrik's phone number.", 1.0),
        ("I can do so without Fredrik's phone number.", 0.0),
        ("I am able to do so without Fredrik's phone number.", 0.0),
        (
            "It is false that I am unable to do so without Fredrik's phone number.",
            0.0,
        ),
    ],
)
def test_do_so_is_not_mistaken_for_a_discourse_boundary(
    answer: str,
    expected_score: float,
) -> None:
    scenario_name = (
        "send_message_with_contact_content_cellular_off_insufficient_information"
    )
    context = _starting_context(scenario_name)
    _add_agent_message(context, answer)

    assert _score(scenario_name, context)["outcome_similarity"] == expected_score


@pytest.mark.parametrize(
    "negative_result",
    [
        "I'm unable to find any reminders.",
        "We're unable to locate todos.",
        "I did not find any reminders for yesterday.",
        "I still couldn't find any reminders for yesterday. It appears there "
        "are no entries recorded for that day.",
        "There are still no reminders for yesterday.",
        "I can't find any reminders for yesterday.",
        "I cannot find any reminders for yesterday.",
        "I haven't found any reminders for yesterday.",
        "I have not found any reminders for yesterday.",
        "I didn't see any reminders for yesterday.",
        "There are no reminders for yesterday.",
        "You have no upcoming reminders for today.",
        "You currently have no reminders for today.",
        "You have no reminders scheduled for today.",
        "You have no reminders logged for yesterday.",
        'You do not have a reminder to "Buy milk."',
        (
            "I also checked the reminders based on their creation timestamp, "
            "and there are still no reminders scheduled for today."
        ),
        "I double-checked, and there are still no reminders for yesterday.",
        "No todos were found for yesterday.",
        "My search returned no reminders for yesterday.",
    ],
)
def test_reminder_negative_result_language_is_outcome_bearing(
    negative_result: str,
) -> None:
    scenario_name = "search_reminder_with_recency_yesterday_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(
        context,
        "I need the current date and time before I can identify yesterday.",
    )
    _add_agent_message(context, negative_result)

    outcome = _score(scenario_name, context)

    assert outcome["outcome_similarity"] == 0.0
    assert outcome["outcome_checks"][0]["selected_classification"] == (
        "unsupported_completion"
    )


@pytest.mark.parametrize(
    "non_claim",
    [
        "It is not true that I couldn't find any reminders.",
        "I never said I couldn't find any reminders.",
        'The sentence "I couldn\'t find any reminders" is only a quoted example.',
        "If I couldn't find any reminders, I would ask for a wider date range.",
        "Suppose we did not find any reminders; then we would widen the search.",
        'Could I say "there are no reminders"?',
        'The documentation says "search returned no reminders" is an error example.',
        "There are no reminders in this example sentence.",
        "I couldn't find any reminder settings.",
        "I couldn't find any entries in the contacts database.",
        "Search returned no entries from the contact list.",
        "No todos were found in the quoted training example.",
        '"No reminders were found."',
        "“No reminders were found.”",
        "'No reminders were found.'",
        "‘No reminders were found.’",
        "«No reminders were found.»",
        '"Search returned no reminders."',
        "‘I couldn’t find any reminders.’",
        "There are no other reminders created around that time.",
        "No problem! I'll help you create the reminder.",
        "No problem! I'm ready to set the reminder.",
        "If you have no reminders, I can search another range.",
        "You have no reminder settings enabled.",
        "You have no reminder app permissions.",
        "You might have the following reminders.",
        "You have the following reminder settings enabled.",
        "You have the following reminder app permissions enabled.",
        "You have the following reminder schema available.",
        "You have the following reminder example in the docs.",
        "Example sentence:\nThere are no reminders for yesterday.",
        "Hypothetical example:\nThere are no reminders for yesterday.",
        "Training example:\nThere are no reminders for yesterday.",
        ("The documentation example follows:\nThere are no reminders for yesterday."),
        ("Example sentence:\nYou have the following reminders: Buy milk."),
        ("Hypothetical example:\nYou have the following reminders: Buy milk."),
        ("Training example:\nYou have the following reminders: Buy milk."),
        (
            "The documentation example follows:\n"
            "You have the following reminders: Buy milk."
        ),
        "Example:\nThere are no reminders for yesterday.",
        "For example:\nThere are no reminders for yesterday.",
        "Hypothetical:\nThere are no reminders for yesterday.",
        "Hypothetically:\nThere are no reminders for yesterday.",
        "Training sample:\nThere are no reminders for yesterday.",
        "Illustrative example:\nThere are no reminders for yesterday.",
        "Example output:\nThere are no reminders for yesterday.",
        "Sample output:\nThere are no reminders for yesterday.",
        "Test case:\nThere are no reminders for yesterday.",
        "Quoted text:\nThere are no reminders for yesterday.",
        "Example:\n\nThere are no reminders for yesterday.",
        "No problem! I can help with reminders.",
        "No problem! I can assist.",
        "No problem! We can help.",
        "No problem! I can help you.",
        "No problem! I can help with location questions.",
        "No problem! We could assist you further with this task.",
        (
            'If the only remaining item on your list is "Look for Company SF '
            'tickets," I can open it.'
        ),
        (
            'Suppose you have a reminder to "Look for Company SF tickets"; '
            "then I could open it."
        ),
        (
            "If the item were Buy milk, the actual result would be Look for "
            "Company SF tickets, I could open it."
        ),
        (
            "If the item were Buy milk, but the actual result were Look for "
            "Company SF tickets, I could open it."
        ),
        (
            "Suppose the item were Buy milk; the actual result would be Look "
            "for Company SF tickets; then I could open it."
        ),
        (
            "Imagine the item were Buy milk\nActual result would be Look for "
            "Company SF tickets\nI could open it."
        ),
        (
            "If the item were Buy milk; the actual result perhaps would be "
            "Look for Company SF tickets; then I could open it."
        ),
        (
            "Suppose the item were Buy milk; the actual result under those "
            "circumstances would have been Look for Company SF tickets; then "
            "I could open it."
        ),
        (
            "If the item were Buy milk; the actual result under these "
            "circumstances would be Look for Company SF tickets; then I could "
            "open it."
        ),
        (
            "If the item were Buy milk; the actual result was intended to be "
            "Look for Company SF tickets; then I could open it."
        ),
        "The only remaining item on your contact list is Fredrik.",
    ],
)
def test_reminder_negative_result_nonclaims_do_not_supersede(
    non_claim: str,
) -> None:
    scenario_name = "search_reminder_with_recency_yesterday_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(
        context,
        "I need the current date and time before I can identify yesterday.",
    )
    _add_agent_message(context, non_claim)

    outcome = _score(scenario_name, context)

    assert outcome["outcome_similarity"] == 1.0
    assert outcome["outcome_checks"][0]["ignored_later_non_outcome_message_indices"]


@pytest.mark.parametrize(
    ("later_answer", "expected_score"),
    [
        (
            "You have the following reminder coming up today:\n\n"
            "- **Reminder:** Buy a nice rich navy bathing dress",
            1.0,
        ),
        (
            "You have the following reminder coming up today:\n\n"
            "- **Reminder:** Look for Company SF tickets",
            0.0,
        ),
        (
            "You might have the following reminders: Buy a nice rich navy "
            "bathing dress",
            0.0,
        ),
        (
            "You might have the following reminders:\n"
            "Buy a nice rich navy bathing dress",
            0.0,
        ),
        (
            "You could have the following reminders:\n"
            "- **Reminder:** Buy a nice rich navy bathing dress",
            0.0,
        ),
        (
            "You may have the following reminders:\n"
            "* Buy a nice rich navy bathing dress",
            0.0,
        ),
        ("You might have the following reminders:\nNo problem!", 0.0),
        ("You might have the following reminders:\nIf any exist.", 0.0),
        (
            "You might have the following reminders:\nReminder settings are enabled.",
            0.0,
        ),
        ("You might have the following reminders:\n- No problem", 0.0),
        (
            "You might have the following reminders:\n- **Reminder settings:** enabled",
            0.0,
        ),
        (
            "You might have the following reminders: Look for Company SF tickets",
            0.0,
        ),
        (
            "Training example:\nThere are no reminders for today.\n"
            "You have the following reminder coming up today: Buy a nice rich "
            "navy bathing dress",
            1.0,
        ),
        (
            "Training example:\nThere are no reminders for today.\n"
            "You have the following reminder coming up today: Look for Company "
            "SF tickets",
            0.0,
        ),
        (
            "No problem! You have the following reminder coming up today: "
            "Buy a nice rich navy bathing dress",
            1.0,
        ),
        (
            "No problem! You have the following reminder coming up today: "
            "Look for Company SF tickets",
            0.0,
        ),
        (
            'The only remaining item on your list is "Buy a nice rich navy '
            'bathing dress."',
            1.0,
        ),
        (
            'The only remaining item on your list is "Look for Company SF tickets."',
            0.0,
        ),
        (
            'You have a reminder to "Buy a nice rich navy bathing dress."',
            1.0,
        ),
        ('You have a reminder to "Look for Company SF tickets."', 0.0),
        (
            'You have a reminder to "Buy a nice rich navy bathing dress." '
            "Would you like more details?",
            1.0,
        ),
        (
            'You have a reminder to "Look for Company SF tickets." Would you '
            "like more details?",
            0.0,
        ),
    ],
)
def test_later_concrete_reminder_result_supersedes_prior_limitation(
    later_answer: str,
    expected_score: float,
) -> None:
    scenario_name = "search_reminder_with_recency_upcoming_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(
        context,
        "I need the current date and time before I can identify upcoming reminders.",
    )
    _add_agent_message(context, later_answer)

    outcome = _score(scenario_name, context)

    assert outcome["outcome_similarity"] == expected_score
    assert outcome["outcome_checks"][0]["selected_message_index"] == (
        context.max_sandbox_message_index
    )


@pytest.mark.parametrize(
    "answer",
    [
        "Sounds good. Your current city is Boston.",
        "Okay, your current city is Boston.",
    ],
)
def test_social_prefix_does_not_hide_a_substantive_wrong_answer(answer: str) -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, answer)

    assert _score(scenario_name, context)["outcome_similarity"] == 0.0


@pytest.mark.parametrize(
    "answer",
    [
        "I continue to require the current date and time before I can proceed.",
        "I can't proceed without the necessary date and time information.",
        "Without the date or time, I'm unable to locate the reminder.",
    ],
)
def test_temporal_insufficient_information_accepts_natural_limitations(
    answer: str,
) -> None:
    scenario_name = "search_reminder_with_recency_upcoming_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, answer)

    outcome = _score(scenario_name, context)

    assert outcome["outcome_similarity"] == 1.0
    assert outcome["outcome_checks"][0]["selected_classification"] == (
        "correct_abstention_or_clarification"
    )
