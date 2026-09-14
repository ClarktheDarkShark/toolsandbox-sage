import inspect
import json

import sage_ts.adapters.openai_toolsandbox_roles as actor_roles
import sage_ts.adequacy.inadequacy_classifier as inadequacy_classifier
import sage_ts.validation.output_normalization as output_normalization
from sage_ts.adequacy.inadequacy_classifier import (
    _contact_lookup_query_planner_observation,
    _contact_update_by_id_observation,
    _currency_answer_extraction_observation,
    _device_status_lookup_observation,
    _visible_broad_location_phrase_requested,
    _visible_holiday_request,
    _visible_state_recovery_intent,
    _visible_task_signals,
)


def test_held_out_examples_use_only_synthetic_values() -> None:
    observations = (
        _device_status_lookup_observation("synthetic"),
        _contact_lookup_query_planner_observation("synthetic"),
        _currency_answer_extraction_observation("synthetic"),
    )
    held_out_payload = json.dumps(
        [
            {"inputs": example.inputs, "expected": example.expected}
            for observation in observations
            for example in observation.validation_examples
            if example.held_out
        ],
        sort_keys=True,
    )

    assert "Report whether cellular connectivity is active." in held_out_payload
    assert "+12025550149" in held_out_payload
    assert "246.8 CNY" in held_out_payload
    assert "Cellular service is on." not in held_out_payload
    assert "Location service has been turned on." not in held_out_payload
    assert "keep me posted" not in held_out_payload


def test_observation_audit_json_redacts_held_out_values() -> None:
    observation = _contact_lookup_query_planner_observation("synthetic")
    held_out_examples = [
        example for example in observation.validation_examples if example.held_out
    ]
    assert held_out_examples
    secret_input = next(
        value
        for example in held_out_examples
        for value in example.inputs.values()
        if isinstance(value, str) and value
    )
    serialized = json.dumps(observation.to_json(), sort_keys=True)

    assert secret_input not in serialized
    logged_held_out = [
        example
        for example in observation.to_json()["validation_examples"]
        if example["held_out"]
    ]
    assert logged_held_out
    assert all(example["values_redacted"] is True for example in logged_held_out)
    assert all("inputs" not in example for example in logged_held_out)
    assert all("expected" not in example for example in logged_held_out)
    assert all(example["input_contract"] for example in logged_held_out)
    assert all(example["output_contract"] for example in logged_held_out)


def test_model_visible_observation_has_no_benchmark_scenario_identifier() -> None:
    observation = _contact_update_by_id_observation("private_task_identifier")

    assert "update_contact_with_id_and_phone_number" not in observation.observation
    assert "private_task_identifier" not in observation.observation


def test_state_recovery_intent_generalizes_by_semantic_structure() -> None:
    requests = (
        "Please repair the blocked network autonomously.",
        "Messaging is unavailable; restore the required service.",
        "Take any steps necessary to recover location access.",
        "I am unable to connect to the network.",
    )

    assert all(_visible_state_recovery_intent(request) for request in requests)
    signals = _visible_task_signals(
        requests[0],
        (
            "set_wifi_status",
            "get_wifi_status",
            "search_location_around_lat_lon",
        ),
    )
    assert "device_state_action" in signals
    assert "state_precondition_possible" in signals


def test_holiday_detection_uses_general_calendar_event_structure() -> None:
    calendar_requests = (
        "What is the timestamp for Founders Observance?",
        "How many days remain until River Festival?",
        "When is the Spring Celebration?",
        "Founders Day when?",
    )

    assert all(_visible_holiday_request(request) for request in calendar_requests)
    for request in calendar_requests:
        assert "holiday" in _visible_task_signals(request, ("search_holiday",))
    assert not _visible_holiday_request("How far am I from the Example Harbor Bridge?")


def test_creek_is_not_an_intrinsic_specific_location_qualifier() -> None:
    assert _visible_broad_location_phrase_requested("Find a cafe near Willow Creek")
    assert not _visible_broad_location_phrase_requested(
        "Find a cafe near Example Market on Fiction Creek"
    )


def test_message_counterparty_signals_compose_interaction_and_participant_cues() -> (
    None
):
    requests = (
        "Identify the recipient in my most recent text exchange.",
        "Whom did I converse with most recently?",
        "Find the sender from the earliest message.",
    )

    for request in requests:
        signals = _visible_task_signals(
            request,
            ("search_messages", "search_contacts"),
        )
        assert "message_counterparty_lookup" in signals
        assert "message_recency_search" in signals

    update_signals = _visible_task_signals(
        "Change the mobile number for the recipient in my latest text exchange.",
        ("search_messages", "search_contacts", "modify_contact"),
    )
    assert "message_counterparty_update" in update_signals


def test_production_intent_matching_does_not_embed_benchmark_sentence_aliases() -> None:
    sources = {
        "actor": inspect.getsource(actor_roles).lower(),
        "classifier": inspect.getsource(inadequacy_classifier).lower(),
        "normalization": inspect.getsource(output_normalization).lower(),
    }
    forbidden = {
        "actor": (
            "what" + "_city_am_i_in",
            "what is the " + "name of my",
        ),
        "classifier": (
            "who did i " + "talk to",
            "who did i " + "speak to",
        ),
        "normalization": (
            "what" + "_city_am_i_in",
            "turn on " + "wifi",
            "turn wifi " + "off",
        ),
    }

    for module_name, phrases in forbidden.items():
        assert [phrase for phrase in phrases if phrase in sources[module_name]] == []
