"""Fail-closed black-box contract for visible task signal classification.

This validation-only module calls ``_visible_task_signals`` and
``_visible_primary_family`` exactly as external consumers do.  It neither
parses the classifier source nor requires production instrumentation.
"""

from __future__ import annotations

import argparse
import copy
import importlib
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


SignalFunction = Callable[[str, tuple[str, ...]], tuple[str, ...]]
FamilyFunction = Callable[[tuple[str, ...]], str]


def _classifier_contract_helpers() -> Any:
    module_name = "_sage_replay_classifier_contracts"
    module = sys.modules.get(module_name)
    if module is not None:
        return module
    module_path = Path(__file__).with_name("classifier_contracts.py")
    module_spec = importlib.util.spec_from_file_location(module_name, module_path)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"Could not load classifier replay helpers: {module_path}")
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_name] = module
    module_spec.loader.exec_module(module)
    return module


_digest = _classifier_contract_helpers()._digest


@dataclass(frozen=True)
class _Call:
    request: str
    tools: tuple[str, ...] = ()


@dataclass(frozen=True)
class _SiteCase:
    site: int
    case_id: str
    target: str
    positive: _Call
    negative: _Call


def _site(
    site: int,
    case_id: str,
    target: str,
    positive_request: str,
    positive_tools: tuple[str, ...] = (),
    *,
    negative_request: str | None = None,
    negative_tools: tuple[str, ...] | None = None,
) -> _SiteCase:
    return _SiteCase(
        site,
        case_id,
        target,
        _Call(positive_request, positive_tools),
        _Call(
            positive_request if negative_request is None else negative_request,
            positive_tools if negative_tools is None else negative_tools,
        ),
    )


_S = "search_contacts"
_A = "add_contact"
_M = "modify_contact"
_R = "remove_contact"
_SM = "search_messages"
_SEND = "send_message_with_phone_number"
_AR = "add_reminder"
_MR = "modify_reminder"
_RR = "remove_reminder"
_SR = "search_reminder"
_NOW = "get_current_timestamp"
_LOC = "search_location_around_lat_lon"
_LAT = "search_lat_lon"
_HOLIDAY = "search_holiday"


# One minimal positive/negative carrier for every ordered add(...) site.  The
# repeated insufficient-information and safe-abstention sites deliberately use
# different conditions so a refactor cannot collapse their independent paths.
_SITE_CASES: tuple[_SiteCase, ...] = (
    _site(
        1,
        "literal_insufficient_information",
        "insufficient_information",
        "insufficient information",
        negative_request="insufficient-information",
    ),
    _site(
        2,
        "phone_like_value",
        "has_phone_number",
        "call 555-0123",
        negative_request="call 555012",
    ),
    _site(
        3,
        "contact_domain",
        "contact",
        "view contact",
        (_S,),
        negative_request="view record",
    ),
    _site(
        4,
        "add_contact",
        "add_contact",
        "add contact",
        (_A,),
        negative_request="view contact",
    ),
    _site(
        5,
        "requested_remove_contact",
        "requested_remove_contact",
        "remove contact",
        negative_request="view contact",
    ),
    _site(
        6,
        "remove_contact_available",
        "remove_contact",
        "remove contact",
        (_R,),
        negative_tools=(),
    ),
    _site(
        7,
        "modify_contact",
        "modify_contact",
        "update contact",
        (_M,),
        negative_tools=(_S,),
    ),
    _site(
        8,
        "contact_update_by_id",
        "contact_update_by_id",
        "update id abcdef",
        (_M,),
        negative_request="view id abcdef",
    ),
    _site(
        9,
        "contact_lookup",
        "contact_lookup",
        "what is contact phone",
        (_S,),
        negative_request="show contact phone",
    ),
    _site(
        10,
        "relationship_batch_update",
        "relationship_batch_update",
        "update all friends",
        (_M, _S),
        negative_request="update my friend",
    ),
    _site(
        11,
        "direct_contact_action",
        "direct_contact_action",
        "send 555-0123",
        (_SEND,),
        negative_request="send latest message to 555-0123",
    ),
    _site(
        12,
        "remove_without_native_action",
        "safe_abstain_needed",
        "remove 555-0123",
        (_S,),
        negative_tools=(_S, _R),
    ),
    _site(
        13,
        "modify_without_lookup",
        "safe_abstain_needed",
        "update contact",
        (_M,),
        negative_tools=(_M, _S),
    ),
    _site(14, "message_domain", "message", "message", (_SM,), negative_request="note"),
    _site(
        15,
        "send_message",
        "send_message",
        "send hello",
        (_SEND,),
        negative_request="find message",
    ),
    _site(
        16,
        "named_message_recipient",
        "named_message_recipient",
        "send message to Alice",
        (_SEND, _S),
        negative_tools=(_SEND,),
    ),
    _site(
        17,
        "send_without_recipient_lookup",
        "safe_abstain_needed",
        "send message to Alice",
        (_SEND,),
        negative_tools=(_SEND, _S),
    ),
    _site(
        18,
        "message_recency",
        "message_recency",
        "latest message",
        (_SM,),
        negative_request="message",
    ),
    _site(
        19,
        "message_search_followup",
        "message_search_followup_possible",
        "find message",
        (_SM,),
        negative_request="view message",
    ),
    _site(
        20,
        "message_counterparty_lookup",
        "message_counterparty_lookup",
        "who sent this",
        (_SM,),
        negative_request="who mailed this",
    ),
    _site(
        21,
        "message_counterparty_update",
        "message_counterparty_update",
        "update whoever I contacted last",
        (_SM, _M),
        negative_request="whoever I contacted last",
    ),
    _site(
        22,
        "missing_message_search",
        "insufficient_information",
        "update whoever I contacted last",
        (_M,),
        negative_tools=(_M, _SM),
    ),
    _site(
        23, "reminder_domain", "reminder", "reminder", (_SR,), negative_request="note"
    ),
    _site(
        24,
        "reminder_create",
        "reminder_create",
        "create reminder",
        (_AR,),
        negative_request="view reminder",
    ),
    _site(
        25,
        "reminder_modify",
        "reminder_modify",
        "change reminder",
        (_MR,),
        negative_request="view reminder",
    ),
    _site(
        26,
        "reminder_remove",
        "reminder_remove",
        "delete reminder",
        (_RR,),
        negative_request="view reminder",
    ),
    _site(
        27, "relative_time", "relative_time", "tomorrow", negative_request="some day"
    ),
    _site(28, "weekday_time", "weekday_time", "monday", negative_request="weekday"),
    _site(29, "explicit_time", "explicit_time", "9 pm", negative_request="21:00"),
    _site(
        30,
        "missing_reminder_time",
        "missing_reminder_time",
        "create reminder",
        (_AR,),
        negative_request="create reminder tomorrow",
    ),
    _site(
        31,
        "location_phrase",
        "location_phrase",
        "find address",
        (_LAT,),
        negative_request="find place",
    ),
    _site(
        32,
        "recency_search",
        "recency_search",
        "latest message",
        (_SM,),
        negative_request="message",
    ),
    _site(
        33,
        "missing_current_time",
        "missing_current_time_prerequisite",
        "find messages from today",
        (_SM,),
        negative_tools=(_SM, _NOW),
    ),
    _site(
        34,
        "relative_anchor_abstention",
        "safe_abstain_needed",
        "find messages from today",
        (_SM,),
        negative_tools=(_SM, _NOW),
    ),
    _site(
        35,
        "upcoming_reminder_search",
        "upcoming_reminder_search",
        "next reminder",
        (_SR, _NOW),
        negative_request="latest reminder",
    ),
    _site(
        36,
        "message_recency_search",
        "message_recency_search",
        "latest message",
        (_SM,),
        negative_request="latest reminder",
        negative_tools=(_SR,),
    ),
    _site(
        37,
        "past_reminder_recency",
        "past_reminder_recency_search",
        "latest reminder",
        (_SR,),
        negative_request="next reminder",
    ),
    _site(
        38,
        "recency_action",
        "recency_action",
        "modify latest reminder",
        (_SR, _MR),
        negative_tools=(_SR,),
    ),
    _site(
        39,
        "device_status_read",
        "device_status_read",
        "check wifi status",
        ("get_wifi_status",),
        negative_request="use wifi",
    ),
    _site(
        40,
        "direct_device_state_action",
        "direct_device_state_action",
        "turn on wifi",
        ("set_wifi_status",),
        negative_request="repair wifi if needed",
    ),
    _site(
        41,
        "device_state_action",
        "device_state_action",
        "resolve any issue",
        ("set_wifi_status",),
        negative_request="proceed",
    ),
    _site(
        42,
        "state_precondition_possible",
        "state_precondition_possible",
        "send 555-0123 if needed",
        ("set_wifi_status", _SEND),
        negative_tools=(_SEND,),
    ),
    _site(
        43,
        "holiday",
        "holiday",
        "thanksgiving",
        (_HOLIDAY,),
        negative_request="celebration",
    ),
    _site(
        44,
        "calendar_distance",
        "calendar_distance",
        "how many days until thanksgiving",
        (_HOLIDAY, _NOW),
        negative_request="thanksgiving",
    ),
    _site(
        45,
        "calendar_missing_current_time",
        "insufficient_information",
        "how many days until thanksgiving",
        (_HOLIDAY,),
        negative_tools=(_HOLIDAY, _NOW),
    ),
    _site(
        46,
        "currency_lookup",
        "currency_lookup",
        "convert usd",
        ("convert_currency",),
        negative_request="exchange money",
    ),
    _site(
        47,
        "external_lookup",
        "external_lookup",
        "stock price",
        ("search_stock",),
        negative_request="equity price",
    ),
    _site(
        48,
        "stock_lookup",
        "stock_lookup",
        "stock price",
        ("search_stock",),
        negative_request="currency rate",
    ),
    _site(
        49,
        "service_answer_extraction",
        "service_answer_extraction",
        "weather in Paris",
        ("search_weather_around_lat_lon",),
        negative_tools=("search_stock",),
    ),
)


_PRIMARY_PRIORITY = (
    "relationship_batch_update",
    "named_message_recipient",
    "message_counterparty_lookup",
    "message_counterparty_update",
    "recency_action",
    "recency_search",
    "reminder_create",
    "add_contact",
    "direct_contact_action",
    "contact_lookup",
    "device_state_action",
    "device_status_read",
    "stock_lookup",
    "holiday",
    "service_answer_extraction",
    "external_lookup",
    "message",
    "contact",
    "reminder",
)


@dataclass(frozen=True)
class _AliasGroup:
    case_id: str
    target: str
    aliases: tuple[str, ...]
    template: str
    tools: tuple[str, ...]


_ALIAS_GROUPS: tuple[_AliasGroup, ...] = (
    _AliasGroup(
        "contacted_recency_phrases",
        "message_counterparty_update",
        (
            "whoever i contacted",
            "whoever contacted me",
            "contacted last",
            "last contacted",
            "i contacted last",
            "contacted most recently",
            "most recently contacted",
            "who did i talk to",
            "who did i speak to",
            "talk to last",
            "talked to last",
            "speak to last",
            "spoke to last",
            "last talked",
            "last spoke",
            "most recently talked",
            "most recently spoke",
        ),
        "update {}",
        (_SM, _M),
    ),
    _AliasGroup(
        "counterparty_recency_words",
        "message_counterparty_update",
        (
            "latest",
            "oldest",
            "recent",
            "last message",
            "last person",
            "last contact",
            "most recent message",
            "last conversation",
            "last chat",
        ),
        "{} message update",
        (_SM, _M),
    ),
    _AliasGroup(
        "counterparty_communication_words",
        "message_counterparty_update",
        (
            "contacted",
            "message",
            "messages",
            "text",
            "sent",
            "wrote",
            "written",
            "writer",
            "author",
            "asked me",
            "talk",
            "talked",
            "speak",
            "spoke",
            "chat",
            "conversation",
        ),
        "latest {} update",
        (_SM, _M),
    ),
    _AliasGroup(
        "contact_change_words",
        "message_counterparty_update",
        (
            "update",
            "modify",
            "change",
            "mark ",
            "mark as",
            "marked",
            "classify",
            "classified",
            "label ",
            "labeled",
            "set ",
        ),
        "{}latest message",
        (_SM, _M),
    ),
    _AliasGroup(
        "contact_nouns",
        "contact",
        (
            "contact",
            "phone",
            "relationship",
            "person",
            "friend",
            "enemy",
            "enemies",
            "coworker",
            "coworkers",
            "boss",
            "bosses",
        ),
        "{}",
        (_S,),
    ),
    _AliasGroup(
        "add_contact_verbs",
        "add_contact",
        ("add ", "create ", "save "),
        "{}contact",
        (_A,),
    ),
    _AliasGroup(
        "remove_contact_verbs",
        "requested_remove_contact",
        (
            "remove",
            "delete",
            "get rid",
            "get him out",
            "get her out",
            "get them out",
            "get this person out",
            "out of my contact",
            "out of my contacts",
        ),
        "{} contact",
        (),
    ),
    _AliasGroup(
        "contact_lookup_phrases",
        "contact_lookup",
        ("phone number", "relationship", "who is", "what is", "who are"),
        "{} contact",
        (_S,),
    ),
    _AliasGroup(
        "relationship_update_verbs",
        "relationship_batch_update",
        ("update", "modify", "change", "make", "turn", "set "),
        "{} all friends",
        (_S, _M),
    ),
    _AliasGroup(
        "relationship_groups",
        "relationship_batch_update",
        (
            "all ",
            "all of",
            "everyone",
            "them",
            "friends",
            "enemies",
            "coworkers",
            "bosses",
        ),
        "update {} friends",
        (_S, _M),
    ),
    _AliasGroup(
        "relationship_targets",
        "relationship_batch_update",
        (
            "friend",
            "friends",
            "enemy",
            "enemies",
            "coworker",
            "coworkers",
            "boss",
            "bosses",
            "relationship",
        ),
        "update all {}",
        (_S, _M),
    ),
    _AliasGroup(
        "relationship_lookup_verbs",
        "relationship_batch_update",
        ("who are", "which", "list", "show", "find", "search"),
        "{} all friends",
        (_S, _M),
    ),
    _AliasGroup(
        "message_domain_words",
        "message",
        ("message", "messages", "text", "contacted", "send", "sent me", "asked me"),
        "{}",
        (_SM,),
    ),
    _AliasGroup(
        "send_message_words",
        "send_message",
        ("send", "message to", "text to", "tell ", "ask "),
        "{}Alice",
        (_SEND,),
    ),
    _AliasGroup(
        "message_search_verbs",
        "message_search_followup_possible",
        ("find", "look for", "search"),
        "{} message",
        (_SM,),
    ),
    _AliasGroup(
        "message_recency_words",
        "message_recency",
        (
            "latest",
            "oldest",
            "earliest",
            "recent",
            "last message",
            "last text",
            "first message",
            "first text",
            "first ever",
            "most recent",
        ),
        "{} message",
        (_SM,),
    ),
    _AliasGroup(
        "message_counterparty_words",
        "message_counterparty_lookup",
        (
            "which phone number",
            "who asked",
            "who sent",
            "asked me",
            "sent me",
            "wrote to me",
            "written to me",
            "who wrote",
            "author",
            "which contact",
            "whoever i contacted",
            "contacted last",
            "last contacted",
            "who did i talk to",
            "who did i speak to",
            "talk to last",
            "talked to last",
            "spoke to last",
            "last conversation",
            "last chat",
        ),
        "{}",
        (_SM,),
    ),
    _AliasGroup(
        "reminder_words",
        "reminder",
        ("reminder", "remind", "todo", "to-do"),
        "{}",
        (_SR,),
    ),
    _AliasGroup(
        "reminder_create_phrases",
        "reminder_create",
        (
            "remind me to",
            "add a reminder",
            "add reminder",
            "create a reminder",
            "create reminder",
            "set a reminder",
            "set reminder",
            "add a todo",
            "add todo",
            "create a todo",
            "create todo",
            "new reminder",
            "new todo",
        ),
        "{}",
        (_AR,),
    ),
    _AliasGroup(
        "reminder_modify_verbs",
        "reminder_modify",
        (
            "modify",
            "update",
            "change",
            "postpone",
            "reschedule",
            "move",
            "push",
            "shift",
            "delay",
            "defer",
        ),
        "{} reminder",
        (_MR,),
    ),
    _AliasGroup(
        "reminder_remove_verbs",
        "reminder_remove",
        ("remove", "delete", "get rid", "cancel", "clear"),
        "{} reminder",
        (_RR,),
    ),
    _AliasGroup(
        "relative_time_words",
        "relative_time",
        (
            "tomorrow",
            "tonight",
            "next ",
            "in a week",
            "in two",
            "days from",
            "weeks from",
            "today",
            "yesterday",
            "upcoming",
            "later",
        ),
        "{}",
        (),
    ),
    _AliasGroup(
        "weekday_words",
        "weekday_time",
        ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"),
        "{}",
        (),
    ),
    _AliasGroup(
        "recency_search_words",
        "recency_search",
        (
            "latest",
            "oldest",
            "earliest",
            "first ",
            "first ever",
            "recent",
            "yesterday",
            "today",
            "upcoming",
            "next",
            "later",
            "made",
            "created",
            "last ",
            "contacted last",
            "sent last",
            "received last",
            "texted last",
        ),
        "{} message",
        (_SM, _NOW),
    ),
    _AliasGroup(
        "upcoming_reminder_phrases",
        "upcoming_reminder_search",
        (
            "next reminder",
            "upcoming reminder",
            "next todo",
            "next to-do",
            "upcoming todo",
            "upcoming to-do",
        ),
        "{}",
        (_SR, _NOW),
    ),
    _AliasGroup(
        "past_reminder_phrases",
        "past_reminder_recency_search",
        (
            "latest reminder",
            "most recent reminder",
            "oldest reminder",
            "earliest reminder",
            "last reminder",
        ),
        "{}",
        (_SR,),
    ),
    _AliasGroup(
        "device_read_verbs",
        "device_status_read",
        ("is my", "whether", "status", "check"),
        "{} wifi",
        ("get_wifi_status",),
    ),
    _AliasGroup(
        "device_names",
        "device_status_read",
        ("wifi", "cellular", "location", "low battery"),
        "check {} status",
        ("get_wifi_status",),
    ),
    _AliasGroup(
        "device_action_verbs",
        "direct_device_state_action",
        ("turn on", "turn off", "enable", "disable"),
        "{} wifi",
        ("set_wifi_status",),
    ),
    _AliasGroup(
        "dependent_state_phrases",
        "device_state_action",
        (
            "resolve any issue",
            "issue alone",
            "whatever you need",
            "if needed",
            "can't send",
            "cannot send",
            "can't access",
            "cannot access",
            "can't connect",
            "cannot connect",
            "cellphone signal",
            "current location",
            "connected to the internet",
            "access my current location",
            "so you can",
            "in order to",
        ),
        "{}",
        ("set_wifi_status",),
    ),
    _AliasGroup(
        "holiday_words",
        "holiday",
        (
            "holiday",
            "christmas",
            "thanksgiving",
            "easter",
            "halloween",
            "memorial day",
            "labor day",
            "independence day",
            "veterans day",
        ),
        "{}",
        (_HOLIDAY,),
    ),
    _AliasGroup(
        "calendar_distance_phrases",
        "calendar_distance",
        ("how many days", "days until", "days till", "when is"),
        "{} thanksgiving",
        (_HOLIDAY, _NOW),
    ),
    _AliasGroup(
        "currency_words",
        "currency_lookup",
        ("currency", "convert", "usd", "cny", "eur", "gbp", "jpy", "$", "how much is"),
        "{}",
        ("convert_currency",),
    ),
    _AliasGroup(
        "location_phrase_words",
        "location_phrase",
        (
            " near ",
            " nearby",
            "location",
            "address",
            "distance",
            "how far",
            "how many km",
            "how many miles",
            "km to",
            "miles to",
            "phone number of",
        ),
        "{} Paris",
        (_LAT,),
    ),
    _AliasGroup(
        "location_at_around_phrases",
        "location_phrase",
        ("at Paris", "around Paris"),
        "{}",
        (_LAT,),
    ),
    _AliasGroup(
        "weather_location_words",
        "location_phrase",
        ("temperature", "temp", "weather", "forecast"),
        "{} in Paris",
        (_LAT,),
    ),
    _AliasGroup(
        "state_precondition_off_phrases",
        "state_precondition_possible",
        ("cellular off", "wifi off", "location off", "low battery"),
        "{}",
        ("set_wifi_status", _SEND),
    ),
    _AliasGroup(
        "external_phone_lookup_words",
        "external_lookup",
        (
            "find",
            "what is",
            "what's",
            "lookup",
            "look up",
            "business",
            "restaurant",
            "store",
            "venue",
        ),
        "{} phone number of Blue Cafe",
        (_LOC,),
    ),
    _AliasGroup(
        "external_query_words",
        "external_lookup",
        (
            "temperature",
            "temp",
            "weather",
            "celsius",
            "fahrenheit",
            "distance",
            "how far",
            "how many km",
            "how many miles",
            "km to",
            "miles to",
            "currency",
            "convert",
            "stock",
            "address",
            "business",
            "restaurant",
            "store",
            "venue",
        ),
        "{}",
        ("search_stock",),
    ),
    _AliasGroup(
        "stock_words",
        "stock_lookup",
        ("stock", "ticker", "symbol"),
        "{}",
        ("search_stock",),
    ),
    _AliasGroup(
        "service_answer_words",
        "service_answer_extraction",
        (
            "what is",
            "what's",
            "find",
            "how far",
            "how many km",
            "how many miles",
            "km to",
            "miles to",
            "convert",
            "phone number",
            "address",
            "distance",
            "temperature",
            "temp",
            "weather",
            "forecast",
            "celsius",
            "fahrenheit",
        ),
        "business {} result",
        ("search_weather_around_lat_lon",),
    ),
)


@dataclass(frozen=True)
class _SuppressionGroup:
    case_id: str
    suppressed_signal: str
    aliases: tuple[str, ...]
    template: str
    tools: tuple[str, ...]


_SUPPRESSION_GROUPS: tuple[_SuppressionGroup, ...] = (
    _SuppressionGroup(
        "message_lookup_blocks_send",
        "send_message",
        (
            "find",
            "look for",
            "search",
            "what does",
            "what's",
            "which message",
            "which text",
            "oldest",
            "latest",
            "earliest",
            "first message",
            "first text",
            "first ever",
            "last message",
            "last text",
            "most recent",
            "sent me",
            "asked me",
        ),
        "send 555-0123 {}",
        (_SEND,),
    ),
    _SuppressionGroup(
        "indirect_target_blocks_direct_contact_action",
        "direct_contact_action",
        (
            "latest",
            "oldest",
            "recent",
            "last message",
            "last person",
            "last contact",
            "first text",
            "first ever",
            "first message",
            "earliest",
            "most recent",
            "who sent",
            "whoever i contacted",
            "contacted last",
            "last contacted",
            "asked me",
            "sent me",
            "which contact",
            "who did i talk to",
            "who did i speak to",
            "talk to last",
            "talked to last",
            "spoke to last",
            "last conversation",
            "last chat",
        ),
        "send 555-0123 {}",
        (_SEND,),
    ),
)


@dataclass(frozen=True)
class _ToolCase:
    case_id: str
    exact_tool: str
    request: str
    target: str
    exact_contains_target: bool = True
    companion_tools: tuple[str, ...] = ()


_TOOL_CASES: tuple[_ToolCase, ...] = (
    _ToolCase("search_contacts", _S, "what is contact phone", "contact_lookup"),
    _ToolCase("add_contact", _A, "add contact", "add_contact"),
    _ToolCase("modify_contact", _M, "update contact", "modify_contact"),
    _ToolCase("remove_contact", _R, "remove contact", "remove_contact"),
    _ToolCase("send_message", _SEND, "send 555-0123", "send_message"),
    _ToolCase("search_messages", _SM, "latest message", "message_recency"),
    _ToolCase("add_reminder", _AR, "create reminder", "reminder_create"),
    _ToolCase("modify_reminder", _MR, "change reminder", "reminder_modify"),
    _ToolCase("remove_reminder", _RR, "remove reminder", "reminder_remove"),
    _ToolCase("search_reminder", _SR, "latest reminder", "recency_search"),
    _ToolCase(
        "current_timestamp",
        _NOW,
        "find messages today",
        "missing_current_time_prerequisite",
        False,
        (_SM,),
    ),
    _ToolCase("location_around", _LOC, "find address", "location_phrase"),
    _ToolCase("lat_lon", _LAT, "find address", "location_phrase"),
    _ToolCase(
        "wifi_getter", "get_wifi_status", "check wifi status", "device_status_read"
    ),
    _ToolCase(
        "cellular_getter",
        "get_cellular_service_status",
        "check cellular status",
        "device_status_read",
    ),
    _ToolCase(
        "location_getter",
        "get_location_service_status",
        "check location status",
        "device_status_read",
    ),
    _ToolCase(
        "battery_getter",
        "get_low_battery_mode_status",
        "check low battery status",
        "device_status_read",
    ),
    _ToolCase(
        "wifi_setter", "set_wifi_status", "turn on wifi", "direct_device_state_action"
    ),
    _ToolCase(
        "cellular_setter",
        "set_cellular_service_status",
        "turn on cellular",
        "direct_device_state_action",
    ),
    _ToolCase(
        "location_setter",
        "set_location_service_status",
        "turn on location",
        "direct_device_state_action",
    ),
    _ToolCase(
        "battery_setter",
        "set_low_battery_mode_status",
        "turn on low battery",
        "direct_device_state_action",
    ),
    _ToolCase("distance", "calculate_lat_lon_distance", "how far", "external_lookup"),
    _ToolCase("holiday", _HOLIDAY, "thanksgiving", "holiday"),
    _ToolCase("currency", "convert_currency", "convert usd", "currency_lookup"),
    _ToolCase("stock", "search_stock", "stock price", "stock_lookup"),
    _ToolCase(
        "weather",
        "search_weather_around_lat_lon",
        "weather in Paris",
        "external_lookup",
    ),
)


_PHONE_CASES: tuple[tuple[str, _Call, bool], ...] = (
    ("seven_digits", _Call("call 555-0123"), True),
    ("fifteen_digits", _Call("call +123456789012345"), True),
    ("dotted", _Call("call 555.012.3456"), True),
    ("six_digits", _Call("call 555012"), False),
    ("sixteen_digits", _Call("call 1234567890123456"), False),
    ("alphanumeric", _Call("call abc5550123456"), False),
    ("uuid", _Call("id 123e4567-e89b-12d3-a456-426614174000"), False),
    (
        "latitude_longitude",
        _Call("address of latitude 37.7749 longitude -122.4194"),
        False,
    ),
)


_NEAR_MISS_CASES: tuple[tuple[str, str, _Call], ...] = (
    (
        "insufficient_hyphen",
        "insufficient_information",
        _Call("insufficient-information"),
    ),
    ("contact_typo", "contact", _Call("contakt", (_S,))),
    ("remove_typo", "requested_remove_contact", _Call("remuve contact")),
    (
        "counterparty_typo",
        "message_counterparty_lookup",
        _Call("who mailed this", (_SM,)),
    ),
    ("reminder_typo", "reminder", _Call("remnder", (_SR,))),
    ("relative_time_no_space", "relative_time", _Call("next")),
    ("weekday_abbreviation", "weekday_time", _Call("mon")),
    ("explicit_24_hour", "explicit_time", _Call("21:00")),
    ("holiday_typo", "holiday", _Call("thanksgivng", (_HOLIDAY,))),
    ("stock_synonym", "stock_lookup", _Call("equity price", ("search_stock",))),
)


_SUBSTRING_QUIRKS: tuple[tuple[str, _Call], ...] = (
    ("embossed_contains_boss", _Call("embossed", (_S,))),
    ("collateral_contains_later", _Call("collateral")),
    ("sender_contains_send", _Call("sender Alice", (_SEND,))),
    ("livestock_contains_stock", _Call("livestock", ("search_stock",))),
    ("attempt_contains_temp", _Call("attempt", ("search_stock",))),
    ("headphone_contains_phone", _Call("headphone", (_S,))),
    ("pretext_to_contains_text_to", _Call("pretext to Alice", (_SEND,))),
    ("reset_contains_set_space", _Call("reset all friends", (_S, _M))),
    ("nextdoor_matches_recency_next", _Call("nextdoor message", (_SM, _NOW))),
)


# Truth-table carriers for conjunctions, suppressors, and regex paths that are
# not adequately distinguished by one-literal alias templates.  These are
# ordinary black-box inputs; their exact signal tuples and primary families are
# frozen in the replay contract.
_FOCUSED_BRANCH_CALLS: tuple[tuple[str, _Call], ...] = (
    (
        "relationship_everyone",
        _Call("update everyone relationship", (_S, _M)),
    ),
    ("contact_lookup_phone_operand", _Call("what is phone", (_S,))),
    ("message_followup_text_domain", _Call("find text", (_SM,))),
    (
        "message_followup_sent_me_suppression",
        _Call("find message sent me", (_SM,)),
    ),
    (
        "missing_search_delete_action",
        _Call("delete whoever I contacted last", (_M,)),
    ),
    ("recency_sent_last_terminal", _Call("message sent last", (_SM,))),
    (
        "external_phone_find_verb",
        _Call("find Blue Cafe phone number", (_LOC,)),
    ),
    ("absolute_date_iso", _Call("create reminder on 2026-10-03", (_AR,))),
    ("absolute_date_slash", _Call("create reminder on 10/03/2026", (_AR,))),
    ("absolute_date_month", _Call("create reminder on October 3, 2026", (_AR,))),
    ("natural_text_recipient_regex", _Call("text Alice", (_SEND,))),
    (
        "safe_abstain_suppresses_state_precondition",
        _Call("send Alice if needed", ("set_wifi_status", _SEND)),
    ),
    (
        "location_around_is_stateful_downstream",
        _Call("resolve any issue near Paris", ("set_wifi_status", _LOC)),
    ),
    (
        "reverse_geocode_suppresses_location_phrase",
        _Call("what is the address of latitude 37.7749 longitude -122.4194", (_LAT,)),
    ),
    (
        "reverse_geocode_space_address_alias",
        _Call("find address latitude 37.7749 longitude -122.4194", (_LAT,)),
    ),
    (
        "reverse_geocode_address_of_alias",
        _Call("address of latitude 37.7749 longitude -122.4194", (_LAT,)),
    ),
    (
        "reverse_geocode_what_is_address_alias",
        _Call("what is the address: latitude 37.7749 longitude -122.4194", (_LAT,)),
    ),
    (
        "reverse_geocode_where_is_alias",
        _Call("where is location latitude 37.7749 longitude -122.4194", (_LAT,)),
    ),
    (
        "reverse_geocode_location_of_alias",
        _Call("location of latitude 37.7749 longitude -122.4194", (_LAT,)),
    ),
    ("parenthesized_phone", _Call("call (555) 012-3456")),
    ("tell_space_positive", _Call("tell Alice", (_SEND,))),
    ("teller_boundary_negative", _Call("teller Alice", (_SEND,))),
    ("temporal_at_not_location", _Call("meet at 9 pm", (_LOC,))),
    ("weather_stopword_not_location", _Call("weather today", (_LOC,))),
    ("weather_bare_city_location", _Call("weather Paris", (_LOC,))),
    ("weather_stopword_a", _Call("weather a", (_LOC,))),
    ("weather_stopword_an", _Call("weather an", (_LOC,))),
    ("weather_stopword_any", _Call("weather any", (_LOC,))),
    ("weather_stopword_current", _Call("weather current", (_LOC,))),
    ("weather_stopword_fahrenheit", _Call("weather fahrenheit", (_LOC,))),
    ("weather_stopword_forecast", _Call("weather forecast", (_LOC,))),
    ("weather_stopword_local", _Call("weather local", (_LOC,))),
    ("weather_stopword_now", _Call("weather now", (_LOC,))),
    ("weather_stopword_temp", _Call("weather temp", (_LOC,))),
    ("weather_stopword_temperature", _Call("weather temperature", (_LOC,))),
    ("weather_stopword_the", _Call("weather the", (_LOC,))),
    ("weather_stopword_weather", _Call("weather weather", (_LOC,))),
    ("weather_whitespace_normalization", _Call("weather   Paris", (_LOC,))),
    ("weather_degree_suffix_cleanup", _Call("weather today in celsius", (_LOC,))),
    ("weather_stopword_token_join", _Call("weather the weather", (_LOC,))),
    ("weather_connector_stopword_for", _Call("weather in for", (_LOC,))),
    ("weather_connector_stopword_in", _Call("weather for in", (_LOC,))),
    ("weather_connector_stopword_near", _Call("weather in near", (_LOC,))),
    ("numeric_at_not_location", _Call("meet at 123", (_LOC,))),
    ("temporal_at_slash_date", _Call("meet at 10/3/2026 office", (_LOC,))),
    ("temporal_at_iso_date", _Call("meet at 2026-10-03 office", (_LOC,))),
    ("temporal_at_today", _Call("meet at today office", (_LOC,))),
    ("temporal_at_tomorrow", _Call("meet at tomorrow office", (_LOC,))),
    ("temporal_at_tonight", _Call("meet at tonight office", (_LOC,))),
    ("temporal_at_yesterday", _Call("meet at yesterday office", (_LOC,))),
    ("temporal_at_next", _Call("meet at next office", (_LOC,))),
    ("temporal_at_monday", _Call("meet at monday office", (_LOC,))),
    ("temporal_at_tuesday", _Call("meet at tuesday office", (_LOC,))),
    ("temporal_at_wednesday", _Call("meet at wednesday office", (_LOC,))),
    ("temporal_at_thursday", _Call("meet at thursday office", (_LOC,))),
    ("temporal_at_friday", _Call("meet at friday office", (_LOC,))),
    ("temporal_at_saturday", _Call("meet at saturday office", (_LOC,))),
    ("temporal_at_sunday", _Call("meet at sunday office", (_LOC,))),
    (
        "direct_action_suppresses_location_phrase",
        _Call("send 555-0123 and find address", (_SEND, _LAT)),
    ),
    (
        "remove_request_suppresses_location_phrase",
        _Call("remove contact and find address", (_LAT,)),
    ),
    (
        "remove_request_suppresses_external_phone_lookup",
        _Call("remove contact and find Blue Cafe phone number", (_LOC,)),
    ),
    (
        "direct_action_suppresses_external_phone_lookup",
        _Call(
            "send 555-0123 and find Blue Cafe phone number",
            (_SEND, _LOC),
        ),
    ),
    (
        "external_phone_requires_location_tool",
        _Call("find Blue Cafe phone number", ("search_weather_around_lat_lon",)),
    ),
    (
        "external_phone_contact_exclusion",
        _Call("find contact phone number near Blue Cafe", (_LOC, _S)),
    ),
    (
        "relationship_lookup_without_update",
        _Call("list all friends", (_S, _M)),
    ),
    (
        "relationship_lookup_missing_search",
        _Call("list all friends", (_M,)),
    ),
    (
        "relationship_lookup_missing_modify",
        _Call("list all friends", (_S,)),
    ),
    (
        "direct_scalar_blocked_by_recency",
        _Call("send 555-0123 latest", (_SEND,)),
    ),
    (
        "direct_scalar_blocked_by_relationship_batch",
        _Call("update all friends id abcdef", (_M, _S)),
    ),
    (
        "state_precondition_location_arm",
        _Call("find address near Paris", ("set_wifi_status", _LOC)),
    ),
    (
        "state_precondition_send_arm",
        _Call("send 555-0123", ("set_wifi_status", _SEND)),
    ),
    (
        "state_precondition_holiday_forward_absence",
        _Call("thanksgiving", ("set_wifi_status", _HOLIDAY)),
    ),
    (
        "missing_search_remove_action",
        _Call("remove whoever I contacted last", (_R,)),
    ),
    (
        "reminder_modify_requires_reminder_word",
        _Call("postpone item", (_MR,)),
    ),
    (
        "reminder_remove_requires_reminder_word",
        _Call("cancel item", (_RR,)),
    ),
    (
        "recency_action_requires_action_signal",
        _Call("latest reminder", (_SR, _MR)),
    ),
    (
        "upcoming_excludes_past_reminder",
        _Call("next reminder", (_SR,)),
    ),
    (
        "past_reminder_requires_past_alias",
        _Call("recent reminder", (_SR,)),
    ),
    (
        "external_location_excludes_friend_contact",
        _Call("find friend phone number near Blue Cafe", (_LOC, _S)),
    ),
    (
        "external_location_excludes_enemy_contact",
        _Call("find enemy phone number near Blue Cafe", (_LOC, _S)),
    ),
    (
        "external_location_excludes_boss_contact",
        _Call("find boss phone number near Blue Cafe", (_LOC, _S)),
    ),
    (
        "external_location_excludes_coworker_contact",
        _Call("find coworker phone number near Blue Cafe", (_LOC, _S)),
    ),
    (
        "external_location_excludes_person_contact",
        _Call("find person phone number near Blue Cafe", (_LOC, _S)),
    ),
    (
        "external_location_excludes_relationship_contact",
        _Call("find relationship phone number near Blue Cafe", (_LOC, _S)),
    ),
    ("contact_update_id_modify", _Call("modify id abcdef", (_M,))),
    ("contact_update_id_change", _Call("change id abcdef", (_M,))),
    ("contact_lookup_enemy_operand", _Call("what is enemy", (_S,))),
    ("contact_lookup_boss_operand", _Call("what is boss", (_S,))),
    ("contact_lookup_coworker_operand", _Call("what is coworker", (_S,))),
    ("contact_lookup_number_operand", _Call("what is number", (_S,))),
    (
        "relationship_group_them",
        _Call("update them relationship", (_S, _M)),
    ),
    (
        "relationship_group_enemies",
        _Call("update enemies relationship", (_S, _M)),
    ),
    (
        "relationship_group_coworkers",
        _Call("update coworkers relationship", (_S, _M)),
    ),
    (
        "relationship_group_bosses",
        _Call("update bosses relationship", (_S, _M)),
    ),
    ("direct_scalar_text", _Call("text 555-0123", (_SEND,))),
    ("direct_scalar_message", _Call("message 555-0123", (_SEND,))),
    ("direct_id_remove", _Call("remove id abcdef", (_R,))),
    ("direct_id_delete", _Call("delete id abcdef", (_R,))),
    ("direct_id_modify", _Call("modify id abcdef", (_M,))),
    (
        "message_followup_asked_me_suppression",
        _Call("find message asked me", (_SM,)),
    ),
    (
        "message_followup_phone_suppression",
        _Call("find message which phone number", (_SM,)),
    ),
    (
        "missing_search_modify_action",
        _Call("modify whoever I contacted last", (_M,)),
    ),
    (
        "missing_search_change_action",
        _Call("change whoever I contacted last", (_M,)),
    ),
    ("recency_received_last", _Call("message received last", (_SM,))),
    ("recency_texted_last", _Call("message texted last", (_SM,))),
    (
        "external_phone_what_is_verb",
        _Call("what is Blue Cafe phone number", (_LOC,)),
    ),
    (
        "external_phone_whats_verb",
        _Call("what's Blue Cafe phone number", (_LOC,)),
    ),
    (
        "external_phone_lookup_verb",
        _Call("lookup Blue Cafe phone number", (_LOC,)),
    ),
    (
        "external_phone_look_up_verb",
        _Call("look up Blue Cafe phone number", (_LOC,)),
    ),
    (
        "external_phone_no_query_verb",
        _Call("phone number of Blue Cafe", (_LOC,)),
    ),
    (
        "contact_lookup_from_phone_modify_signal",
        _Call("update contact 555-0123", (_M, _S)),
    ),
    (
        "contact_lookup_from_underspecified_removal",
        _Call("remove contact", (_S,)),
    ),
    (
        "direct_add_contact_with_phone",
        _Call("add contact 555-0123", (_A,)),
    ),
    ("direct_remove_by_id", _Call("remove id abcdef", (_R,))),
    (
        "missing_search_with_remove_tool",
        _Call("delete whoever I contacted last", (_R,)),
    ),
    (
        "missing_search_with_contact_search_tool",
        _Call("delete whoever I contacted last", (_S,)),
    ),
    (
        "location_blocked_by_add_contact_workflow",
        _Call("add contact and find address", (_A, _LAT)),
    ),
    (
        "location_blocked_by_remove_contact_workflow",
        _Call("remove contact and find address", (_R, _LAT)),
    ),
    (
        "location_blocked_by_modify_contact_workflow",
        _Call("update contact and find address", (_M, _LAT)),
    ),
    (
        "recency_action_remove_reminder",
        _Call("remove latest reminder", (_SR, _RR)),
    ),
    (
        "stateful_downstream_lat_lon",
        _Call("resolve any issue", ("set_wifi_status", _LAT)),
    ),
    (
        "stateful_downstream_distance",
        _Call("resolve any issue", ("set_wifi_status", "calculate_lat_lon_distance")),
    ),
    (
        "stateful_downstream_holiday",
        _Call("resolve any issue", ("set_wifi_status", _HOLIDAY)),
    ),
    (
        "visible_location_dependency_lat_lon",
        _Call("find address", ("set_wifi_status", _LAT)),
    ),
    (
        "external_phone_blocked_by_add_workflow",
        _Call("find Blue Cafe phone number and add contact", (_LOC, _A)),
    ),
    (
        "external_phone_blocked_by_remove_workflow",
        _Call("find Blue Cafe phone number and remove contact", (_LOC, _R)),
    ),
    (
        "external_phone_blocked_by_modify_workflow",
        _Call("find Blue Cafe phone number and update contact", (_LOC, _M)),
    ),
    (
        "counterparty_requires_recency_operand",
        _Call("update author", (_SM, _M)),
    ),
    (
        "counterparty_requires_communication_operand",
        _Call("update latest parcel", (_SM, _M)),
    ),
    (
        "counterparty_target_requires_search_tool",
        _Call("update latest message what is contact phone", (_S, _M)),
    ),
    (
        "counterparty_target_requires_text",
        _Call("send 555-0123", (_SM, _SEND)),
    ),
    (
        "indirect_target_counterparty_arm",
        _Call("send 555-0123 whoever contacted me", (_SM, _SEND)),
    ),
    (
        "external_phone_requires_location_capability",
        _Call("phone number of Blue Cafe", ("search_stock",)),
    ),
    (
        "external_phone_requires_location_phrase",
        _Call("Blue Cafe phone number", (_LOC,)),
    ),
    ("add_contact_requires_contact_word", _Call("add record", (_A,))),
    (
        "contact_update_by_id_requires_modify_tool",
        _Call("update id abcdef", (_S,)),
    ),
    (
        "phone_lookup_requires_action_signal",
        _Call("contact 555-0123", (_S,)),
    ),
    (
        "phone_lookup_requested_remove_arm",
        _Call("remove 555-0123 id abcdef", (_S,)),
    ),
    (
        "underspecified_remove_requires_no_identifier",
        _Call("remove contact id abcdef", (_S,)),
    ),
    (
        "contact_lookup_blocks_external_location_phone",
        _Call("what is phone number of Blue Cafe", (_S, _LOC)),
    ),
    (
        "contact_lookup_blocks_counterparty_update",
        _Call("update latest message what is contact phone", (_SM, _M, _S)),
    ),
    (
        "contact_lookup_counterparty_change_operand",
        _Call("latest message what is contact phone", (_SM, _S)),
    ),
    (
        "relationship_lookup_requires_lookup_verb",
        _Call("all friends", (_S, _M)),
    ),
    (
        "relationship_update_requires_search_tool",
        _Call("update all friends", (_M,)),
    ),
    (
        "relationship_update_requires_modify_tool",
        _Call("update all friends", (_S,)),
    ),
    (
        "relationship_update_requires_target",
        _Call("update all people", (_S, _M)),
    ),
    (
        "direct_send_requires_send_tool",
        _Call("send 555-0123", (_M,)),
    ),
    ("direct_send_requires_action_word", _Call("555-0123", (_SEND,))),
    (
        "direct_add_requires_add_signal",
        _Call("555-0123", (_A,)),
    ),
    (
        "direct_id_requires_contact_action_tool",
        _Call("remove id abcdef", (_SEND,)),
    ),
    (
        "remove_abstention_requires_missing_lookup",
        _Call("remove 555-0123", (_R,)),
    ),
    (
        "modify_abstention_identifier_suppression",
        _Call("update contact id abcdef", (_M,)),
    ),
    (
        "modify_abstention_person_suppression",
        _Call("update contact person Alice", (_M,)),
    ),
    (
        "named_recipient_rejects_phone",
        _Call("send message to 555-0123", (_SEND, _S)),
    ),
    ("followup_requires_message_domain", _Call("find note", (_SM,))),
    (
        "counterparty_update_requires_modify_tool",
        _Call("update latest message", (_SM,)),
    ),
    (
        "counterparty_update_requires_target",
        _Call("update ordinary note", (_SM, _M)),
    ),
    (
        "missing_search_requires_action_tool",
        _Call("delete whoever I contacted last", (_SEND,)),
    ),
    (
        "missing_search_requires_action_word",
        _Call("whoever I contacted last", (_M,)),
    ),
    ("reminder_time_weekday_operand", _Call("create reminder Monday", (_AR,))),
    ("reminder_time_explicit_operand", _Call("create reminder 9 pm", (_AR,))),
    (
        "external_phone_overrides_contact_workflow_for_location",
        _Call("send 555-0123 and phone number of Blue Cafe", (_SEND, _LOC)),
    ),
    ("recency_requires_domain", _Call("latest report", (_SM,))),
    (
        "absolute_date_suppresses_missing_current_time",
        _Call("find messages today 2026-10-03", (_SM,)),
    ),
    (
        "upcoming_requires_recency_search",
        _Call("next reminder", (_AR,)),
    ),
    (
        "upcoming_requires_reminder_domain",
        _Call("next reminder message", (_SM,)),
    ),
    (
        "past_requires_recency_search",
        _Call("latest reminder", (_MR,)),
    ),
    (
        "past_requires_reminder_domain",
        _Call("latest reminder message", (_SM,)),
    ),
    (
        "past_is_suppressed_by_upcoming",
        _Call("next reminder and latest reminder", (_SR,)),
    ),
    (
        "device_read_requires_device_word",
        _Call("check service", ("get_wifi_status",)),
    ),
    (
        "device_action_requires_device_word",
        _Call("turn on service", ("set_wifi_status",)),
    ),
    (
        "visible_location_dependency_requires_location_signal",
        _Call("proceed", ("set_wifi_status", _LOC)),
    ),
    (
        "visible_location_dependency_excludes_external_phone",
        _Call("phone number of Blue Cafe", ("set_wifi_status", _LOC)),
    ),
    (
        "send_dependency_requires_send_signal",
        _Call("proceed", ("set_wifi_status", _SEND)),
    ),
    (
        "calendar_distance_requires_holiday_signal",
        _Call("how many days until thanksgiving"),
    ),
    (
        "external_phone_fallback_requires_query_verb",
        _Call("Blue Cafe phone number", ("search_weather_around_lat_lon",)),
    ),
    (
        "service_extraction_requires_answer_intent",
        _Call("business report", ("search_weather_around_lat_lon",)),
    ),
)


def _evaluate(
    signal_fn: SignalFunction,
    family_fn: FamilyFunction,
    call: _Call,
) -> dict[str, Any]:
    request_before = call.request
    tools_before = tuple(call.tools)
    signals = signal_fn(call.request, call.tools)
    if type(signals) is not tuple:
        raise ValueError(
            "visible task signals must return an exact tuple, "
            f"got {type(signals).__name__}"
        )
    return {
        "request": call.request,
        "tools": list(call.tools),
        "signals": list(signals),
        "primary_family": family_fn(signals),
        # The production signature accepts only immutable str/tuple inputs.
        # This records value preservation; it does not claim a mutable-input
        # aliasing guarantee that the API cannot express.
        "immutable_inputs_equal_after_call": call.request == request_before
        and call.tools == tools_before,
    }


def _semantic_body(
    signal_fn: SignalFunction,
    family_fn: FamilyFunction,
) -> dict[str, Any]:
    site_cases = []
    for case in _SITE_CASES:
        positive = _evaluate(signal_fn, family_fn, case.positive)
        negative = _evaluate(signal_fn, family_fn, case.negative)
        site_cases.append(
            {
                "site": case.site,
                "case_id": case.case_id,
                "target": case.target,
                "positive": positive,
                "negative": negative,
                "target_in_positive": case.target in positive["signals"],
                "target_in_negative": case.target in negative["signals"],
            }
        )

    aliases = []
    for group in _ALIAS_GROUPS:
        aliases.append(
            {
                "case_id": group.case_id,
                "target": group.target,
                "cases": [
                    {
                        "alias": alias,
                        "result": _evaluate(
                            signal_fn,
                            family_fn,
                            _Call(group.template.format(alias), group.tools),
                        ),
                    }
                    for alias in group.aliases
                ],
            }
        )

    suppression_aliases = []
    for group in _SUPPRESSION_GROUPS:
        suppression_aliases.append(
            {
                "case_id": group.case_id,
                "suppressed_signal": group.suppressed_signal,
                "cases": [
                    {
                        "alias": alias,
                        "result": _evaluate(
                            signal_fn,
                            family_fn,
                            _Call(group.template.format(alias), group.tools),
                        ),
                    }
                    for alias in group.aliases
                ],
            }
        )

    exact_tools = []
    for case in _TOOL_CASES:
        exact = _evaluate(
            signal_fn,
            family_fn,
            _Call(case.request, (*case.companion_tools, case.exact_tool)),
        )
        near = _evaluate(
            signal_fn,
            family_fn,
            _Call(
                case.request, (*case.companion_tools, f"{case.exact_tool}__near_miss")
            ),
        )
        exact_tools.append(
            {
                "case_id": case.case_id,
                "exact_tool": case.exact_tool,
                "target": case.target,
                "exact_contains_target": case.target in exact["signals"],
                "expected_exact_contains_target": case.exact_contains_target,
                "near_miss_contains_target": case.target in near["signals"],
                "exact": exact,
                "near_miss": near,
            }
        )

    broad_call = _Call(
        "update all friends; send 555-0123; find latest message; create reminder "
        "tomorrow at 9 pm; find address; check wifi; thanksgiving; convert usd; "
        "stock price",
        (
            _S,
            _M,
            _SEND,
            _SM,
            _AR,
            _LAT,
            "get_wifi_status",
            _HOLIDAY,
            "convert_currency",
            "search_stock",
            _NOW,
        ),
    )
    base_inventory = _evaluate(signal_fn, family_fn, broad_call)
    reversed_inventory = _evaluate(
        signal_fn,
        family_fn,
        _Call(broad_call.request, tuple(reversed(broad_call.tools))),
    )
    duplicate_inventory = _evaluate(
        signal_fn,
        family_fn,
        _Call(broad_call.request, (*broad_call.tools, *broad_call.tools[:4])),
    )
    unknown_inventory = _evaluate(
        signal_fn,
        family_fn,
        _Call(broad_call.request, (*broad_call.tools, "unknown_native_tool")),
    )

    duplicate_cases = {
        "insufficient_information_three_sites": _evaluate(
            signal_fn,
            family_fn,
            _Call(
                "insufficient information: update whoever I contacted last and "
                "say how many days until thanksgiving",
                (_M, _HOLIDAY),
            ),
        ),
        "safe_abstain_first_then_relative": _evaluate(
            signal_fn,
            family_fn,
            _Call("remove 555-0123 and find messages today", (_S, _SM)),
        ),
        "safe_abstain_modify_then_send": _evaluate(
            signal_fn,
            family_fn,
            _Call("update contact and send Alice", (_M, _SEND)),
        ),
    }

    forward_order = {
        "message_recency_before_counterparty": _evaluate(
            signal_fn,
            family_fn,
            _Call("latest item: who sent this", (_SM,)),
        ),
        "holiday_after_state_precondition": _evaluate(
            signal_fn,
            family_fn,
            _Call(
                "how many days until thanksgiving",
                ("set_wifi_status", _HOLIDAY, _NOW),
            ),
        ),
    }

    primary_families = [
        {
            "case_id": f"single_{signal}",
            "signals": [signal],
            "primary_family": family_fn((signal,)),
        }
        for signal in _PRIMARY_PRIORITY
    ]
    dynamic_primary_signal = "".join(("recency", "_search"))
    canonical_primary_signal = "recency_search"
    if (
        dynamic_primary_signal != canonical_primary_signal
        or dynamic_primary_signal is canonical_primary_signal
    ):
        raise AssertionError("primary-family identity carrier was interned or changed")
    primary_families.append(
        {
            "case_id": "dynamic_equal_nonidentical_recency_search",
            "signals": [dynamic_primary_signal],
            "primary_family": family_fn((dynamic_primary_signal,)),
        }
    )
    primary_families.extend(
        (
            {
                "case_id": "all_priority_signals_forward",
                "signals": list(_PRIMARY_PRIORITY),
                "primary_family": family_fn(_PRIMARY_PRIORITY),
            },
            {
                "case_id": "all_priority_signals_reverse",
                "signals": list(reversed(_PRIMARY_PRIORITY)),
                "primary_family": family_fn(tuple(reversed(_PRIMARY_PRIORITY))),
            },
            {
                "case_id": "no_priority_signal",
                "signals": ["relative_time", "safe_abstain_needed"],
                "primary_family": family_fn(("relative_time", "safe_abstain_needed")),
            },
            {
                "case_id": "empty",
                "signals": [],
                "primary_family": family_fn(()),
            },
        )
    )

    return {
        "site_cases": site_cases,
        "alias_groups": aliases,
        "suppression_alias_groups": suppression_aliases,
        "phone_boundaries": [
            {
                "case_id": case_id,
                "expected_has_phone_number": expected,
                "result": _evaluate(signal_fn, family_fn, call),
            }
            for case_id, call, expected in _PHONE_CASES
        ],
        "near_misses": [
            {
                "case_id": case_id,
                "target": target,
                "result": _evaluate(signal_fn, family_fn, call),
            }
            for case_id, target, call in _NEAR_MISS_CASES
        ],
        "substring_quirks": [
            {
                "case_id": case_id,
                "result": _evaluate(signal_fn, family_fn, call),
            }
            for case_id, call in _SUBSTRING_QUIRKS
        ],
        "focused_branch_truth_tables": [
            {
                "case_id": case_id,
                "result": _evaluate(signal_fn, family_fn, call),
            }
            for case_id, call in _FOCUSED_BRANCH_CALLS
        ],
        "exact_tool_names": exact_tools,
        "tool_inventory_set_semantics": {
            "base": base_inventory,
            "reversed": reversed_inventory,
            "duplicates": duplicate_inventory,
            "unknown_appended": unknown_inventory,
        },
        "duplicate_insertions": duplicate_cases,
        "forward_order_traps": forward_order,
        "primary_family_cases": primary_families,
    }


def _production_functions() -> tuple[SignalFunction, FamilyFunction]:
    classifier = importlib.import_module("sage_ts.adequacy.inadequacy_classifier")
    return classifier._visible_task_signals, classifier._visible_primary_family


def build_visible_signal_trace(
    *,
    signal_fn: SignalFunction | None = None,
    family_fn: FamilyFunction | None = None,
) -> dict[str, Any]:
    if signal_fn is None or family_fn is None:
        production_signal_fn, production_family_fn = _production_functions()
        signal_fn = signal_fn or production_signal_fn
        family_fn = family_fn or production_family_fn
    first = _semantic_body(signal_fn, family_fn)
    second = _semantic_body(signal_fn, family_fn)
    body = {
        "schema_version": 1,
        **first,
        "deterministic_repeated_calls": {
            "first": _digest(first),
            "second": _digest(second),
            "equal": first == second,
        },
    }
    return {**body, "integrity": {"body": _digest(body)}}


_ALL_FINAL_SIGNALS = (
    "add_contact",
    "calendar_distance",
    "contact",
    "contact_lookup",
    "contact_update_by_id",
    "currency_lookup",
    "device_state_action",
    "device_status_read",
    "direct_contact_action",
    "direct_device_state_action",
    "explicit_time",
    "external_lookup",
    "has_phone_number",
    "holiday",
    "insufficient_information",
    "location_phrase",
    "message",
    "message_counterparty_lookup",
    "message_counterparty_update",
    "message_recency",
    "message_recency_search",
    "message_search_followup_possible",
    "missing_current_time_prerequisite",
    "missing_reminder_time",
    "modify_contact",
    "named_message_recipient",
    "past_reminder_recency_search",
    "recency_action",
    "recency_search",
    "relationship_batch_update",
    "relative_time",
    "reminder",
    "reminder_create",
    "reminder_modify",
    "reminder_remove",
    "remove_contact",
    "requested_remove_contact",
    "safe_abstain_needed",
    "send_message",
    "service_answer_extraction",
    "state_precondition_possible",
    "stock_lookup",
    "upcoming_reminder_search",
    "weekday_time",
)


EXPECTED_VISIBLE_SIGNAL_TRACE: dict[str, Any] = {
    "body": {
        "byte_count": 562_729,
        "sha256": "4a05de2f3d47c824ecf83d6a461dbab0358cf2125b00485c71b3db796b7ec434",
    },
    "schema_version": 1,
    "site_case_count": 49,
    "site_numbers": list(range(1, 50)),
    "site_case_ids": [case.case_id for case in _SITE_CASES],
    "unique_final_signal_count": 44,
    "unique_final_signals": list(_ALL_FINAL_SIGNALS),
    "site_results": {
        "byte_count": 75_058,
        "sha256": "b76a71cd725579e3ef4c95c0df94a8716e6314298bdaf3a50d426cb254553075",
    },
    "alias_group_count": 41,
    "alias_case_count": 354,
    "alias_results": {
        "byte_count": 251_457,
        "sha256": "c443a19e9120bfaedd970b4f628bb8772f26a252fd47101abcebe436d0e2b95a",
    },
    "suppression_alias_group_count": 2,
    "suppression_alias_case_count": 43,
    "suppression_alias_results": {
        "byte_count": 29_856,
        "sha256": "97b122a7d421a791224644300facf5235dd79cb7a77062ac2c90749d6e1c32a6",
    },
    "phone_boundaries": {
        "byte_count": 5_150,
        "sha256": "ad1c146f1dc3b53711572ea76313843e5c2df281b76f21b5f3a933190f58f4b2",
    },
    "near_misses": {
        "byte_count": 6_305,
        "sha256": "e1f5be5d954644c3f557a89ce5b0b4c399db23ef912ea6bd335309fcc2ff2956",
    },
    "substring_quirks": {
        "byte_count": 5_935,
        "sha256": "525ff9075d9d023dcb34882eb42f9490149380fd1a8939acd08f9fb8ff4ff902",
    },
    "focused_branch_truth_tables": {
        "byte_count": 126_151,
        "sha256": "a707dd44e67d9014842406575b311d7f92f2926044bda8b7c0004d0ba82053c5",
    },
    "exact_tool_names": {
        "byte_count": 41_564,
        "sha256": "3e41434934b3160072021a678537cca59b50fb1a40841799fe37cca9fc507cf5",
    },
    "tool_inventory_set_semantics": {
        "byte_count": 7_194,
        "sha256": "35846322328df4bc882d29cc22aad2d5815a8aa25c0b1a50e2145be0918e5684",
    },
    "duplicate_insertions": {
        "byte_count": 2_673,
        "sha256": "d141678ee4c75c2cc98690350382d9d7c0a53b5da2517ee98a80db0511cd9be9",
    },
    "forward_order_traps": {
        "byte_count": 1_356,
        "sha256": "e9dfee8f77cce178d31024e9b6a97b38422903493c0d830cf6d0e8f41d0829be",
    },
    "primary_family_cases": {
        "byte_count": 8_718,
        "sha256": "d13e6fcc2c2166a60af4580fcc62994d00c30bb112e21b9895dfff215fcbeca0",
    },
    "deterministic_repeated_calls": {
        "byte_count": 594,
        "sha256": "087895d8bb3c42a80ea63272f766bb598127d2d32800b7a44f7e51c7da06cd7b",
    },
}


def _contract_projection(contract: dict[str, Any]) -> dict[str, Any]:
    cases = contract["site_cases"]
    aliases = contract["alias_groups"]
    all_signals = {
        signal
        for case in cases
        for side in ("positive", "negative")
        for signal in case[side]["signals"]
    }
    return {
        "body": contract["integrity"]["body"],
        "schema_version": contract["schema_version"],
        "site_case_count": len(cases),
        "site_numbers": [case["site"] for case in cases],
        "site_case_ids": [case["case_id"] for case in cases],
        "unique_final_signal_count": len(all_signals),
        "unique_final_signals": sorted(all_signals),
        "site_results": _digest(cases),
        "alias_group_count": len(aliases),
        "alias_case_count": sum(len(group["cases"]) for group in aliases),
        "alias_results": _digest(aliases),
        "suppression_alias_group_count": len(contract["suppression_alias_groups"]),
        "suppression_alias_case_count": sum(
            len(group["cases"]) for group in contract["suppression_alias_groups"]
        ),
        "suppression_alias_results": _digest(contract["suppression_alias_groups"]),
        "phone_boundaries": _digest(contract["phone_boundaries"]),
        "near_misses": _digest(contract["near_misses"]),
        "substring_quirks": _digest(contract["substring_quirks"]),
        "focused_branch_truth_tables": _digest(contract["focused_branch_truth_tables"]),
        "exact_tool_names": _digest(contract["exact_tool_names"]),
        "tool_inventory_set_semantics": _digest(
            contract["tool_inventory_set_semantics"]
        ),
        "duplicate_insertions": _digest(contract["duplicate_insertions"]),
        "forward_order_traps": _digest(contract["forward_order_traps"]),
        "primary_family_cases": _digest(contract["primary_family_cases"]),
        "deterministic_repeated_calls": _digest(
            contract["deterministic_repeated_calls"]
        ),
    }


def _all_results(value: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if {
            "request",
            "tools",
            "signals",
            "primary_family",
            "immutable_inputs_equal_after_call",
        } <= set(value):
            results.append(value)
        for item in value.values():
            results.extend(_all_results(item))
    elif isinstance(value, list):
        for item in value:
            results.extend(_all_results(item))
    return results


def verify_visible_signal_trace(contract: dict[str, Any]) -> None:
    body = {key: value for key, value in contract.items() if key != "integrity"}
    if contract.get("integrity", {}).get("body") != _digest(body):
        raise ValueError("visible-signal trace body digest does not match its contents")
    actual = _contract_projection(contract)
    if not EXPECTED_VISIBLE_SIGNAL_TRACE:
        raise ValueError("visible-signal trace expected contract has not been frozen")
    if actual != EXPECTED_VISIBLE_SIGNAL_TRACE:
        raise ValueError(
            "visible-signal trace differs from its frozen reference contract: "
            f"expected={EXPECTED_VISIBLE_SIGNAL_TRACE!r}, actual={actual!r}"
        )

    cases = contract["site_cases"]
    if [case["site"] for case in cases] != list(range(1, 50)):
        raise ValueError("visible-signal trace does not cover add sites 1 through 49")
    if any(
        not case["target_in_positive"] or case["target_in_negative"] for case in cases
    ):
        raise ValueError("a signal-site positive/negative carrier is not isolated")
    if any(
        not result["immutable_inputs_equal_after_call"]
        for result in _all_results(contract)
    ):
        raise ValueError(
            "visible signal classification changed an immutable input value"
        )
    if not contract["deterministic_repeated_calls"]["equal"]:
        raise ValueError("visible signal classification is not deterministic")

    phone = contract["phone_boundaries"]
    if any(
        ("has_phone_number" in item["result"]["signals"])
        != item["expected_has_phone_number"]
        for item in phone
    ):
        raise ValueError("phone-number boundary behavior changed")
    if any(
        item["target"] in item["result"]["signals"] for item in contract["near_misses"]
    ):
        raise ValueError("a discriminating lexical near miss became a match")
    if any(
        group["target"] not in item["result"]["signals"]
        for group in contract["alias_groups"]
        for item in group["cases"]
    ):
        raise ValueError("a declared literal alias no longer emits its signal")
    if any(
        group["suppressed_signal"] in item["result"]["signals"]
        for group in contract["suppression_alias_groups"]
        for item in group["cases"]
    ):
        raise ValueError("a declared suppressing alias no longer suppresses its signal")

    expected_substring_quirks = {
        "embossed_contains_boss": ("contact",),
        "collateral_contains_later": ("relative_time",),
        "sender_contains_send": ("message", "send_message", "safe_abstain_needed"),
        "livestock_contains_stock": ("external_lookup", "stock_lookup"),
        "attempt_contains_temp": ("external_lookup",),
        "headphone_contains_phone": ("contact",),
        "pretext_to_contains_text_to": (
            "message",
            "send_message",
            "safe_abstain_needed",
        ),
        "reset_contains_set_space": ("contact", "relationship_batch_update"),
        "nextdoor_matches_recency_next": (
            "message",
            "recency_search",
            "message_recency_search",
        ),
    }
    actual_substring_quirks = {
        item["case_id"]: tuple(item["result"]["signals"])
        for item in contract["substring_quirks"]
    }
    if actual_substring_quirks != expected_substring_quirks:
        raise ValueError("known substring-matching behavior changed")

    for item in contract["exact_tool_names"]:
        if (
            item["exact_contains_target"] != item["expected_exact_contains_target"]
            or item["near_miss_contains_target"]
            == item["expected_exact_contains_target"]
        ):
            raise ValueError(f"exact tool-name boundary changed for {item['case_id']}")

    inventory = contract["tool_inventory_set_semantics"]
    base_semantics = (
        inventory["base"]["signals"],
        inventory["base"]["primary_family"],
    )
    for name in ("reversed", "duplicates", "unknown_appended"):
        if (
            inventory[name]["signals"],
            inventory[name]["primary_family"],
        ) != base_semantics:
            raise ValueError("tool inventory no longer has exact set semantics")

    for signal, item in zip(_PRIMARY_PRIORITY, contract["primary_family_cases"]):
        if item["primary_family"] != signal:
            raise ValueError("primary-family single-signal behavior changed")
    if [item["primary_family"] for item in contract["primary_family_cases"][-4:]] != [
        _PRIMARY_PRIORITY[0],
        _PRIMARY_PRIORITY[0],
        "general_visible_task",
        "general_visible_task",
    ]:
        raise ValueError("primary-family priority or fallback behavior changed")

    duplicates = contract["duplicate_insertions"]
    for name, signal in (
        ("insufficient_information_three_sites", "insufficient_information"),
        ("safe_abstain_first_then_relative", "safe_abstain_needed"),
        ("safe_abstain_modify_then_send", "safe_abstain_needed"),
    ):
        if duplicates[name]["signals"].count(signal) != 1:
            raise ValueError(f"duplicate suppression changed for {name}")
    if duplicates["insufficient_information_three_sites"]["signals"][0] != (
        "insufficient_information"
    ):
        raise ValueError("insufficient-information no longer retains first position")
    if (
        duplicates["safe_abstain_first_then_relative"]["signals"].index(
            "safe_abstain_needed"
        )
        != 4
        or duplicates["safe_abstain_modify_then_send"]["signals"].index(
            "safe_abstain_needed"
        )
        != 2
    ):
        raise ValueError(
            "safe-abstention no longer retains its first insertion position"
        )

    forward = contract["forward_order_traps"]
    message_signals = forward["message_recency_before_counterparty"]["signals"]
    if (
        "message_counterparty_lookup" not in message_signals
        or "message_recency" in message_signals
    ):
        raise ValueError("message-recency/counterparty forward-order behavior changed")
    holiday_signals = forward["holiday_after_state_precondition"]["signals"]
    if (
        "holiday" not in holiday_signals
        or "state_precondition_possible" in holiday_signals
    ):
        raise ValueError("holiday/state-precondition forward-order behavior changed")


def probe_visible_signal_trace(_root: Any) -> dict[str, Any]:
    contract = build_visible_signal_trace()
    verify_visible_signal_trace(contract)
    return contract


def _rehash(contract: dict[str, Any]) -> None:
    body = {key: value for key, value in contract.items() if key != "integrity"}
    contract["integrity"]["body"] = _digest(body)


def _tamper_self_test(contract: dict[str, Any]) -> None:
    tampered = copy.deepcopy(contract)
    tampered["site_cases"][0]["positive"]["signals"] = []
    try:
        verify_visible_signal_trace(tampered)
    except ValueError:
        pass
    else:
        raise AssertionError("unhashed visible-signal tamper was not rejected")

    for label, mutate in (
        ("dropped site", lambda value: value["site_cases"].pop(5)),
        ("reordered sites", lambda value: value["site_cases"].reverse()),
        (
            "added signal",
            lambda value: value["site_cases"][0]["positive"]["signals"].append(
                "mutant_signal"
            ),
        ),
    ):
        forged = copy.deepcopy(contract)
        mutate(forged)
        _rehash(forged)
        try:
            verify_visible_signal_trace(forged)
        except ValueError:
            pass
        else:
            raise AssertionError(f"rehashed {label} tamper was not rejected")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-contract", action="store_true")
    parser.add_argument("--tamper-self-test", action="store_true")
    args = parser.parse_args()
    contract = build_visible_signal_trace()
    if args.print_contract:
        print(json.dumps(_contract_projection(contract), indent=2))
        return 0
    verify_visible_signal_trace(contract)
    if args.tamper_self_test:
        _tamper_self_test(contract)
    print(
        json.dumps(
            {
                "status": "verified",
                "contract": _contract_projection(contract),
                "tamper_self_test": args.tamper_self_test,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
