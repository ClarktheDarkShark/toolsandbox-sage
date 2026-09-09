# mypy: ignore-errors
import datetime as dt
import json
from copy import deepcopy
from functools import lru_cache

import polars as pl

from sage_ts.evaluation.outcome_score import compute_outcome_score
from tool_sandbox.cli.utils import resolve_scenarios
from tool_sandbox.common.execution_context import DatabaseNamespace, RoleType
from tool_sandbox.common.tool_discovery import ToolBackend


@lru_cache(maxsize=None)
def _scenario(name: str):
    return resolve_scenarios(
        desired_scenario_names=[name],
        preferred_tool_backend=ToolBackend.DEFAULT,
    )[name]


def _starting_context(name: str):
    return deepcopy(_scenario(name).starting_context)


def _add_agent_message(execution_context, content: str, *, recipient=RoleType.USER):
    execution_context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [{"sender": RoleType.AGENT, "recipient": recipient, "content": content}],
    )


def _add_user_message(execution_context, content: str) -> None:
    execution_context.add_to_database(
        DatabaseNamespace.SANDBOX,
        [{"sender": RoleType.USER, "recipient": RoleType.AGENT, "content": content}],
    )


def _add_tool_result(execution_context, tool_name: str, result) -> None:
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


def _commit_state(execution_context, namespace, dataframe, label: str) -> None:
    _add_agent_message(
        execution_context,
        label,
        recipient=RoleType.EXECUTION_ENVIRONMENT,
    )
    execution_context.update_database(namespace, dataframe)


def _score(scenario_name: str, execution_context):
    return compute_outcome_score(
        _scenario(scenario_name),
        execution_context,
        scenario_name=scenario_name,
    )


def _assert_restored_collateral_rejected(outcome) -> None:
    assert outcome["outcome_similarity"] == 0.0
    assert outcome["outcome_unexpected_state_mutation_detected"] is True
    state_completion = outcome["outcome_checks"][0]["state_completion"]
    assert state_completion["verified"] is False
    history = state_completion["state_transition_history"]
    assert history["reason"] == "unexpected_intermediate_target_namespace_state"
    assert history["offending_sandbox_message_index"] is not None


def test_exact_action_state_can_terminate_without_final_user_message() -> None:
    scenario_name = "remove_contact_by_phone_no_remove_contact_insufficient_information"
    execution_context = _starting_context(scenario_name)
    contacts = execution_context.get_database(DatabaseNamespace.CONTACT)
    _commit_state(
        execution_context,
        DatabaseNamespace.CONTACT,
        contacts.filter(pl.col("phone_number") != "+12453344098"),
        "generated_remove_target_contact()",
    )

    outcome = _score(scenario_name, execution_context)

    assert outcome["outcome_similarity"] == 1.0
    state_completion = outcome["outcome_checks"][0]["state_completion"]
    assert state_completion["verified"] is True
    assert state_completion["state_transition_history"]["reason"] == (
        "exact_irreversible_target_transition"
    )


def test_scalar_answer_rejects_unrelated_state_mutation() -> None:
    scenario_name = "convert_currency"
    execution_context = _starting_context(scenario_name)
    contacts = execution_context.get_database(DatabaseNamespace.CONTACT)
    collateral_id = contacts.filter(~pl.col("is_self")).to_dicts()[0]["person_id"]
    _commit_state(
        execution_context,
        DatabaseNamespace.CONTACT,
        contacts.filter(pl.col("person_id") != collateral_id),
        "generated_remove_unrelated_contact()",
    )
    _add_agent_message(execution_context, "2048 USD is 13988.4544 CNY.")

    outcome = _score(scenario_name, execution_context)

    assert outcome["outcome_milestone_similarity"] == 1.0
    assert outcome["outcome_similarity"] == 0.0
    assert outcome["outcome_state_history_safe"] is False
    contact_diagnostics = next(
        item
        for item in outcome["outcome_state_history_diagnostics"][
            "namespace_diagnostics"
        ]
        if item["namespace"] == str(DatabaseNamespace.CONTACT)
    )
    assert contact_diagnostics["reason"] == "unmodeled_namespace_mutation"


def test_remove_contact_rejects_restored_collateral_contact_mutation() -> None:
    scenario_name = "remove_contact_by_phone_no_remove_contact_insufficient_information"
    execution_context = _starting_context(scenario_name)
    contacts = execution_context.get_database(DatabaseNamespace.CONTACT)
    collateral = contacts.filter(
        (pl.col("phone_number") != "+12453344098") & ~pl.col("is_self")
    ).to_dicts()[0]

    _commit_state(
        execution_context,
        DatabaseNamespace.CONTACT,
        contacts.filter(pl.col("person_id") != collateral["person_id"]),
        "generated_remove_wrong_contact()",
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.CONTACT,
        contacts,
        "generated_restore_wrong_contact()",
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.CONTACT,
        contacts.filter(pl.col("phone_number") != "+12453344098"),
        "generated_remove_target_contact()",
    )
    _add_agent_message(execution_context, "Done.")

    _assert_restored_collateral_rejected(_score(scenario_name, execution_context))


def test_modify_contact_rejects_restored_collateral_contact_mutation() -> None:
    scenario_name = "modify_contact_with_message_recency_insufficient_information"
    execution_context = _starting_context(scenario_name)
    contacts = execution_context.get_database(DatabaseNamespace.CONTACT)
    collateral = contacts.with_columns(
        pl.when(pl.col("name") == "Fredrik Thordendal")
        .then(pl.lit("collateral-change"))
        .otherwise(pl.col("relationship"))
        .alias("relationship")
    )
    expected = contacts.with_columns(
        pl.when(pl.col("name") == "Homer S")
        .then(pl.lit("+10293847563"))
        .otherwise(pl.col("phone_number"))
        .alias("phone_number")
    )

    _commit_state(
        execution_context,
        DatabaseNamespace.CONTACT,
        collateral,
        "generated_modify_wrong_contact()",
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.CONTACT,
        contacts,
        "generated_restore_wrong_contact()",
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.CONTACT,
        expected,
        "generated_modify_target_contact()",
    )
    _add_agent_message(execution_context, "Done.")

    _assert_restored_collateral_rejected(_score(scenario_name, execution_context))


def test_send_message_rejects_restored_collateral_message_mutation() -> None:
    scenario_name = (
        "send_message_with_contact_content_cellular_off_insufficient_information"
    )
    execution_context = _starting_context(scenario_name)
    contacts = execution_context.get_database(DatabaseNamespace.CONTACT).to_dicts()
    messages = execution_context.get_database(DatabaseNamespace.MESSAGING)
    self_row = next(row for row in contacts if row["is_self"])
    fredrik = next(row for row in contacts if row["name"] == "Fredrik Thordendal")
    latest_timestamp = max(
        float(row["creation_timestamp"]) for row in messages.to_dicts()
    )

    def message_row(message_id: str, content: str, timestamp_offset: int):
        return {
            "message_id": message_id,
            "sender_person_id": self_row["person_id"],
            "sender_phone_number": self_row["phone_number"],
            "recipient_person_id": fredrik["person_id"],
            "recipient_phone_number": fredrik["phone_number"],
            "content": content,
            "creation_timestamp": latest_timestamp + timestamp_offset,
        }

    wrong = pl.DataFrame(
        [message_row("collateral-message", "Wrong message", 30)],
        schema=messages.schema,
    )
    expected = pl.DataFrame(
        [
            message_row(
                "target-message",
                "How's the new album coming along.",
                60,
            )
        ],
        schema=messages.schema,
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.MESSAGING,
        pl.concat([messages, wrong], how="vertical"),
        "generated_send_wrong_message()",
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.MESSAGING,
        messages,
        "generated_restore_message_history()",
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.MESSAGING,
        pl.concat([messages, expected], how="vertical"),
        "generated_send_target_message()",
    )
    _add_agent_message(execution_context, "Done.")

    _assert_restored_collateral_rejected(_score(scenario_name, execution_context))


def test_remove_reminder_rejects_restored_collateral_reminder_mutation() -> None:
    scenario_name = "remove_reminder_with_recency_latest_insufficient_information"
    execution_context = _starting_context(scenario_name)
    reminders = execution_context.get_database(DatabaseNamespace.REMINDER)
    target_timestamp = reminders.select(pl.col("reminder_timestamp").max()).item()
    target = reminders.filter(
        pl.col("reminder_timestamp") == target_timestamp
    ).to_dicts()[0]
    collateral = reminders.filter(
        pl.col("reminder_id") != target["reminder_id"]
    ).to_dicts()[0]

    _commit_state(
        execution_context,
        DatabaseNamespace.REMINDER,
        reminders.filter(pl.col("reminder_id") != collateral["reminder_id"]),
        "generated_remove_wrong_reminder()",
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.REMINDER,
        reminders,
        "generated_restore_wrong_reminder()",
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.REMINDER,
        reminders.filter(pl.col("reminder_id") != target["reminder_id"]),
        "generated_remove_target_reminder()",
    )
    _add_agent_message(execution_context, "Done.")

    _assert_restored_collateral_rejected(_score(scenario_name, execution_context))


def test_modify_reminder_rejects_restored_collateral_reminder_mutation() -> None:
    scenario_name = "modify_reminder_with_recency_latest_insufficient_information"
    execution_context = _starting_context(scenario_name)
    reminders = execution_context.get_database(DatabaseNamespace.REMINDER)
    target_timestamp = reminders.select(pl.col("reminder_timestamp").max()).item()
    target = reminders.filter(
        pl.col("reminder_timestamp") == target_timestamp
    ).to_dicts()[0]
    collateral_id = reminders.filter(
        pl.col("reminder_id") != target["reminder_id"]
    ).to_dicts()[0]["reminder_id"]
    collateral = reminders.with_columns(
        pl.when(pl.col("reminder_id") == collateral_id)
        .then(pl.lit("collateral-change"))
        .otherwise(pl.col("content"))
        .alias("content")
    )
    inferred_now = (
        float(reminders.select(pl.col("creation_timestamp").max()).item())
        + float(target_timestamp)
    ) / 2
    tomorrow = dt.datetime.fromtimestamp(inferred_now) + dt.timedelta(days=1)
    expected_timestamp = tomorrow.replace(
        hour=17,
        minute=0,
        second=0,
        microsecond=0,
    ).timestamp()
    expected = reminders.with_columns(
        pl.when(pl.col("reminder_id") == target["reminder_id"])
        .then(pl.lit(expected_timestamp))
        .otherwise(pl.col("reminder_timestamp"))
        .alias("reminder_timestamp"),
        pl.when(pl.col("reminder_id") == target["reminder_id"])
        .then(pl.col("creation_timestamp") + 1)
        .otherwise(pl.col("creation_timestamp"))
        .alias("creation_timestamp"),
    )

    _commit_state(
        execution_context,
        DatabaseNamespace.REMINDER,
        collateral,
        "generated_modify_wrong_reminder()",
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.REMINDER,
        reminders,
        "generated_restore_wrong_reminder()",
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.REMINDER,
        expected,
        "generated_modify_target_reminder()",
    )
    _add_agent_message(execution_context, "Done.")

    _assert_restored_collateral_rejected(_score(scenario_name, execution_context))


def test_valid_action_rejects_restored_non_prerequisite_setting_mutation() -> None:
    scenario_name = (
        "send_message_with_contact_content_cellular_off_insufficient_information"
    )
    execution_context = _starting_context(scenario_name)
    contacts = execution_context.get_database(DatabaseNamespace.CONTACT).to_dicts()
    messages = execution_context.get_database(DatabaseNamespace.MESSAGING)
    settings = execution_context.get_database(DatabaseNamespace.SETTING)
    self_row = next(row for row in contacts if row["is_self"])
    fredrik = next(row for row in contacts if row["name"] == "Fredrik Thordendal")

    _commit_state(
        execution_context,
        DatabaseNamespace.SETTING,
        settings.with_columns(pl.lit(42.0).alias("latitude")),
        "generated_change_unrelated_setting()",
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.SETTING,
        settings,
        "generated_restore_unrelated_setting()",
    )
    message = pl.DataFrame(
        [
            {
                "message_id": "target-message",
                "sender_person_id": self_row["person_id"],
                "sender_phone_number": self_row["phone_number"],
                "recipient_person_id": fredrik["person_id"],
                "recipient_phone_number": fredrik["phone_number"],
                "content": "How's the new album coming along.",
                "creation_timestamp": max(
                    float(row["creation_timestamp"]) for row in messages.to_dicts()
                )
                + 60,
            }
        ],
        schema=messages.schema,
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.MESSAGING,
        pl.concat([messages, message], how="vertical"),
        "generated_send_target_message()",
    )
    _add_agent_message(execution_context, "Done.")

    outcome = _score(scenario_name, execution_context)

    assert outcome["outcome_similarity"] == 0.0
    assert outcome["outcome_checks"][0]["state_completion"]["verified"] is True
    assert outcome["outcome_checks"][0]["invalid_setting_transition"] is True


def test_repeated_target_transition_with_restore_is_rejected() -> None:
    scenario_name = "remove_contact_by_phone_no_remove_contact_insufficient_information"
    execution_context = _starting_context(scenario_name)
    contacts = execution_context.get_database(DatabaseNamespace.CONTACT)
    expected = contacts.filter(pl.col("phone_number") != "+12453344098")

    _commit_state(
        execution_context,
        DatabaseNamespace.CONTACT,
        expected,
        "generated_remove_target_contact_once()",
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.CONTACT,
        contacts,
        "generated_restore_target_contact()",
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.CONTACT,
        expected,
        "generated_remove_target_contact_twice()",
    )
    _add_agent_message(execution_context, "Done.")

    outcome = _score(scenario_name, execution_context)

    assert outcome["outcome_similarity"] == 0.0
    history = outcome["outcome_checks"][0]["state_completion"][
        "state_transition_history"
    ]
    assert history["reason"] == "target_transition_reversed"
    assert history["offending_sandbox_message_index"] is not None


def test_reminder_modify_accepts_native_creation_timestamp_update() -> None:
    scenario_name = "modify_reminder_with_recency_latest_insufficient_information"
    execution_context = _starting_context(scenario_name)
    reminders = execution_context.get_database(DatabaseNamespace.REMINDER)
    target_timestamp = reminders.select(pl.col("reminder_timestamp").max()).item()
    target = reminders.filter(
        pl.col("reminder_timestamp") == target_timestamp
    ).to_dicts()[0]
    inferred_now = (
        float(reminders.select(pl.col("creation_timestamp").max()).item())
        + float(target_timestamp)
    ) / 2
    tomorrow = dt.datetime.fromtimestamp(inferred_now) + dt.timedelta(days=1)
    expected_timestamp = tomorrow.replace(
        hour=17,
        minute=0,
        second=0,
        microsecond=0,
    ).timestamp()
    expected = reminders.with_columns(
        pl.when(pl.col("reminder_id") == target["reminder_id"])
        .then(pl.lit(expected_timestamp))
        .otherwise(pl.col("reminder_timestamp"))
        .alias("reminder_timestamp"),
        pl.when(pl.col("reminder_id") == target["reminder_id"])
        .then(pl.col("creation_timestamp") + 1)
        .otherwise(pl.col("creation_timestamp"))
        .alias("creation_timestamp"),
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.REMINDER,
        expected,
        "generated_modify_target_and_creation_timestamp()",
    )
    _add_agent_message(execution_context, "Done.")

    outcome = _score(scenario_name, execution_context)

    assert outcome["outcome_similarity"] == 1.0
    state_completion = outcome["outcome_checks"][0]["state_completion"]
    assert state_completion["verified"] is True
    assert state_completion["reason"] == "exact_upcoming_reminder_modified"


def _generic_namespace_diagnostic(outcome, namespace: DatabaseNamespace):
    return next(
        item
        for item in outcome["outcome_state_history_diagnostics"][
            "namespace_diagnostics"
        ]
        if item["namespace"] == str(namespace)
    )


def test_generic_remove_contact_rejects_wrong_restore_then_target_history() -> None:
    scenario_name = "remove_contact_by_phone"
    execution_context = _starting_context(scenario_name)
    contacts = execution_context.get_database(DatabaseNamespace.CONTACT)
    _commit_state(
        execution_context,
        DatabaseNamespace.CONTACT,
        contacts.filter(pl.col("phone_number") != "+10000000000"),
        "generated_remove_wrong_contact()",
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.CONTACT,
        contacts,
        "generated_restore_wrong_contact()",
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.CONTACT,
        contacts.filter(pl.col("phone_number") != "+12453344098"),
        "generated_remove_target_contact()",
    )
    _add_agent_message(
        execution_context,
        "Phone number +12453344098 has been removed from your contact",
    )

    outcome = _score(scenario_name, execution_context)

    assert outcome["outcome_milestone_similarity"] == 1.0
    assert outcome["outcome_similarity"] == 0.0
    assert outcome["outcome_state_history_safe"] is False
    diagnostic = _generic_namespace_diagnostic(outcome, DatabaseNamespace.CONTACT)
    assert diagnostic["reason"] == "unmodeled_snapshot_or_rollback"


def test_generic_pure_answer_rejects_restored_collateral_state() -> None:
    scenario_name = "find_days_till_holiday_3_distraction_tools"
    execution_context = _starting_context(scenario_name)
    contacts = execution_context.get_database(DatabaseNamespace.CONTACT)
    _commit_state(
        execution_context,
        DatabaseNamespace.CONTACT,
        contacts.filter(pl.col("phone_number") != "+10000000000"),
        "generated_remove_unrelated_contact()",
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.CONTACT,
        contacts,
        "generated_restore_unrelated_contact()",
    )
    _add_tool_result(execution_context, "get_current_timestamp", 1777597539.872639)
    _add_agent_message(
        execution_context,
        "There are 107 days until Christmas Day.",
    )

    outcome = _score(scenario_name, execution_context)

    assert outcome["outcome_milestone_similarity"] == 1.0
    assert outcome["outcome_similarity"] == 0.0
    assert outcome["outcome_state_history_safe"] is False
    diagnostic = _generic_namespace_diagnostic(outcome, DatabaseNamespace.CONTACT)
    assert diagnostic["represented_by_verified_state_milestone"] is False
    assert diagnostic["reason"] == "unmodeled_namespace_mutation"


def test_generic_two_state_contact_progression_remains_valid() -> None:
    scenario_name = (
        "update_contact_relationship_with_relationship_twice_multiple_user_turn"
    )
    execution_context = _starting_context(scenario_name)
    contacts = execution_context.get_database(DatabaseNamespace.CONTACT)
    target_names = ["Fredrik Thordendal", "John Petrucci"]
    enemies = contacts.with_columns(
        pl.when(pl.col("name").is_in(target_names))
        .then(pl.lit("enemy"))
        .otherwise(pl.col("relationship"))
        .alias("relationship")
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.CONTACT,
        enemies,
        "generated_set_relationship_enemy()",
    )
    _add_agent_message(
        execution_context,
        "Fredrik Thordendal and John Petrucci are now your enemies",
    )
    _add_user_message(execution_context, "Now change them back to friends.")
    friends = enemies.with_columns(
        pl.when(pl.col("name").is_in(target_names))
        .then(pl.lit("friend"))
        .otherwise(pl.col("relationship"))
        .alias("relationship")
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.CONTACT,
        friends,
        "generated_set_relationship_friend()",
    )
    _add_agent_message(
        execution_context,
        "Fredrik Thordendal and John Petrucci are now your friends again.",
    )

    outcome = _score(scenario_name, execution_context)

    assert outcome["outcome_similarity"] == 1.0
    assert outcome["outcome_state_history_safe"] is True
    diagnostic = _generic_namespace_diagnostic(outcome, DatabaseNamespace.CONTACT)
    assert diagnostic["reason"] == "matched_state_progression"
    assert len(diagnostic["observed_progression"]) == 3


def test_generic_two_state_setting_progression_remains_valid() -> None:
    scenario_name = "turn_on_cellular_low_battery_mode"
    execution_context = _starting_context(scenario_name)
    settings = execution_context.get_database(DatabaseNamespace.SETTING)
    low_battery_disabled = settings.with_columns(
        pl.lit(False).alias("low_battery_mode")
    )
    _commit_state(
        execution_context,
        DatabaseNamespace.SETTING,
        low_battery_disabled,
        "set_low_battery_mode_status(on=False)",
    )
    cellular_enabled = low_battery_disabled.with_columns(pl.lit(True).alias("cellular"))
    _commit_state(
        execution_context,
        DatabaseNamespace.SETTING,
        cellular_enabled,
        "set_cellular_service_status(on=True)",
    )
    _add_agent_message(execution_context, "Cellular service has been turned on.")

    outcome = _score(scenario_name, execution_context)

    assert outcome["outcome_similarity"] == 1.0
    assert outcome["outcome_state_history_safe"] is True
    diagnostic = _generic_namespace_diagnostic(outcome, DatabaseNamespace.SETTING)
    assert diagnostic["reason"] == "matched_state_progression"
    assert len(diagnostic["observed_progression"]) == 3
