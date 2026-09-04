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
    ("scenario_name", "answer"),
    [
        (
            "find_current_city_insufficient_information",
            "You are currently in Cupertino.",
        ),
        (
            "find_distance_with_location_name_insufficient_information",
            "The Golden Gate Bridge is 67.86 kilometers away.",
        ),
        (
            "find_min_temperature_weekday_insufficient_information",
            "The minimum temperature this Friday is 10.2 degrees Celsius.",
        ),
        (
            "find_temperature_f_with_location_insufficient_information",
            "The current temperature in Grand Canyon is 54.14 Fahrenheit.",
        ),
    ],
)
def test_information_contract_accepts_exact_answer_without_tool_result(
    scenario_name: str,
    answer: str,
) -> None:
    context = _starting_context(scenario_name)
    _add_agent_message(context, answer)

    outcome = _score(scenario_name, context)

    assert outcome["outcome_similarity"] == 1.0
    check = outcome["outcome_checks"][0]
    assert check["outcome_basis"] == "verified_information_answer"
    assert check["information_answer"]["answer_truth_basis"] == (
        "independently_derived_exact_information_answer"
    )


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
            "The Golden Gate Bridge is not 67.86 kilometers away.",
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
            "The Golden Gate Bridge distance is unknown. My serial is 67.86 km.",
            0.0,
        ),
        (
            "find_distance_with_location_name_insufficient_information",
            "The Golden Gate Bridge is 67.86 km away.",
            1.0,
        ),
        (
            "find_distance_with_location_name_insufficient_information",
            "The bridge is 67.86 km away.",
            0.0,
        ),
        (
            "find_distance_with_location_name_insufficient_information",
            "The Golden Gate is 67.86 km away.",
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


def test_social_prefix_does_not_hide_a_substantive_wrong_answer() -> None:
    scenario_name = "find_current_city_insufficient_information"
    context = _starting_context(scenario_name)
    _add_agent_message(context, "Sounds good. Your current city is Boston.")

    assert _score(scenario_name, context)["outcome_similarity"] == 0.0
