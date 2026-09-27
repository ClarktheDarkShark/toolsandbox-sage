"""Validation-only source-mutation audit for the visible signal guard.

The live replay probe remains source-independent.  This module is used only by
tests to prove that the black-box carrier corpus observes each current
behavior-distinct literal, tool-role, and boolean operand.  Source mutations
are compiled into an isolated function namespace and never replace production
code or run in benchmark evidence collection.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from validation.replay import visible_signal_contracts as contracts


MutationKind = Literal[
    "literal",
    "tool",
    "boolean_operand",
    "string_constant",
    "helper_string",
    "temporal_prefix",
    "text_role",
    "text_membership",
    "tool_role",
    "signal_role",
    "regex_literal",
    "text_normalization",
    "tool_normalization",
    "return_shape",
    "family_semantics",
    "role_crosswire",
    "helper_call",
    "shared_definition",
    "shared_use",
    "shared_crosswire",
    "evaluation_order",
    "local_helper",
]


REFERENCE_PROFILE = "reference_v1"
CANDIDATE_PROFILE = "candidate_shared_facts_v1"


PROFILE_IDENTITIES = {
    REFERENCE_PROFILE: {
        "source_byte_count": 26_953,
        "source_sha256": "6cbf4de1714f61145125f0fb87381e6fc7857d8b3ef18bec0bb766c3622819f5",
        "ast_byte_count": 50_982,
        "ast_sha256": "a73bb39f8aa5307732ed1d7b1a6b0a4081edfbbed638b2203ef06562b34250c6",
    },
    CANDIDATE_PROFILE: {
        "source_byte_count": 22_114,
        "source_sha256": "1eaecc42c463013b2e09fa38eeb0eafdfc2a50ae1872b5013b80c8a23c7f28a2",
        "ast_byte_count": 47_807,
        "ast_sha256": "6450bc2e151b6b7f1cef684e3e5ad1ad5f7f779765a500c35e51548442c19ad8",
        "dependency_source_byte_count": 4_416,
        "dependency_source_sha256": (
            "71f5f246594d1158f29462c58b542e68b83f3fa6d3378bf4f330f35958b84339"
        ),
        "dependency_ast_byte_count": 11_763,
        "dependency_ast_sha256": (
            "6e7e58b934fb1d757d3bb37661130e419590690048ab7970c71ad5d5daa2e27e"
        ),
    },
}


PROFILE_KIND_COUNTS = {
    REFERENCE_PROFILE: {
        "boolean_operand": 223,
        "helper_string": 51,
        "literal": 419,
        "string_constant": 122,
        "temporal_prefix": 15,
        "tool": 101,
    },
    CANDIDATE_PROFILE: {
        "boolean_operand": 258,
        "evaluation_order": 8,
        "family_semantics": 1,
        "helper_call": 154,
        "helper_string": 51,
        "local_helper": 38,
        "regex_literal": 6,
        "return_shape": 1,
        "role_crosswire": 7_256,
        "shared_definition": 86,
        "shared_crosswire": 256,
        "shared_use": 46,
        "signal_role": 117,
        "temporal_prefix": 15,
        "text_membership": 12,
        "text_normalization": 1,
        "text_role": 336,
        "tool_normalization": 5,
        "tool_role": 89,
    },
}


_HELPER_FUNCTIONS = (
    "_visible_reverse_geocode_request",
    "_has_phone_like_value",
    "_visible_location_phrase_requested",
    "_visible_weather_location_phrase_requested",
)


_TEMPORAL_PREFIX_SEGMENTS = (
    ("clock", r"\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b|"),
    ("slash_date", r"\d{1,2}/\d{1,2}/\d{2,4}\b|"),
    ("iso_date", r"\d{4}-\d{1,2}-\d{1,2}\b|"),
    ("today", r"today\b|"),
    ("tomorrow", r"tomorrow\b|"),
    ("tonight", r"tonight\b|"),
    ("yesterday", r"yesterday\b|"),
    ("next", r"next\b|"),
    ("monday", r"monday\b|"),
    ("tuesday", r"tuesday\b|"),
    ("wednesday", r"wednesday\b|"),
    ("thursday", r"thursday\b|"),
    ("friday", r"friday\b|"),
    ("saturday", r"saturday\b|"),
    ("sunday", r"sunday\b"),
)


_TOOL_NAMES = frozenset(
    {
        "add_contact",
        "add_reminder",
        "calculate_lat_lon_distance",
        "convert_currency",
        "get_cellular_service_status",
        "get_current_timestamp",
        "get_location_service_status",
        "get_low_battery_mode_status",
        "get_wifi_status",
        "modify_contact",
        "modify_reminder",
        "remove_contact",
        "remove_reminder",
        "search_contacts",
        "search_holiday",
        "search_lat_lon",
        "search_location_around_lat_lon",
        "search_messages",
        "search_reminder",
        "search_stock",
        "search_weather_around_lat_lon",
        "send_message_with_phone_number",
        "set_cellular_service_status",
        "set_location_service_status",
        "set_low_battery_mode_status",
        "set_wifi_status",
    }
)


# These mutations are externally indistinguishable by construction, not merely
# unobserved by the corpus.  Each reason identifies the dominating predicate or
# downstream implication.  Any newly invisible mutation is a hard failure.
EXPECTED_EQUIVALENT_MUTANTS: dict[str, str] = {
    "literal:11:3:last contacted": "the broad branch matches 'last contact' and 'contacted'",
    "literal:11:4:i contacted last": "the same tuple also matches 'contacted last'",
    "literal:11:5:contacted most recently": "the broad branch matches 'recent' and 'contacted'",
    "literal:11:6:most recently contacted": "the broad branch matches 'recent' and 'contacted'",
    "literal:11:15:most recently talked": "the broad branch matches 'recent' and 'talk'",
    "literal:11:16:most recently spoke": "the broad branch matches 'recent' and 'spoke'",
    "literal:35:6:most recent message": "'recent' is a substring in the same tuple",
    "literal:49:2:messages": "'message' is a substring in the same tuple",
    "literal:49:11:talked": "'talk' is a substring in the same tuple",
    "literal:74:4:mark as": "'mark ' is a substring in the same tuple",
    "literal:90:10:most recent": "'recent' is a substring in the same tuple",
    "literal:90:14:last contacted": "'last contact' is a substring in the same tuple",
    "literal:154:8:coworkers": "'coworker' is a substring in the same tuple",
    "literal:154:10:bosses": "'boss' is a substring in the same tuple",
    "literal:178:8:out of my contacts": "'out of my contact' is a substring in the same tuple",
    "literal:243:1:all of": "'all ' is a substring in the same tuple",
    "literal:256:1:friends": "'friend' is a substring in the same tuple",
    "literal:256:5:coworkers": "'coworker' is a substring in the same tuple",
    "literal:256:7:bosses": "'boss' is a substring in the same tuple",
    "literal:343:1:messages": "'message' is a substring in the same tuple",
    "literal:403:1:messages": "'message' is a substring in the same tuple",
    "literal:417:9:most recent": "'recent' is a substring in the same tuple",
    "literal:478:0:reminder": "'remind' is a substring in the same tuple",
    "literal:625:4:first ever": "'first ' is a substring in the same tuple",
    "literal:744:13:access my current location": "'current location' is a substring in the same tuple",
    "literal:853:0:temperature": "'temp' is a substring in the same tuple",
    "literal:881:5:business": "the earlier external-query predicate already matches 'business'",
    "literal:881:6:restaurant": "the earlier external-query predicate already matches 'restaurant'",
    "literal:881:7:store": "the earlier external-query predicate already matches 'store'",
    "literal:881:8:venue": "the earlier external-query predicate already matches 'venue'",
    "literal:931:12:temperature": "'temp' is a substring in the same tuple",
    "tool:593:12:remove_contact": "requested_remove_contact is always present before remove_contact",
    "tool:787:37:search_holiday": "holiday is emitted after this forward-only dependency check",
    "tool:843:12:add_contact": "the base contact signal already marks every add-contact workflow",
    "tool:845:12:remove_contact": "requested_remove_contact already marks every removal workflow",
    "tool:846:12:modify_contact": "the base contact signal already marks every modify workflow",
    "boolean_operand:214:1:And": "outer contact lookup independently requires search_contacts",
    "boolean_operand:271:0:And": "outer relationship batch independently requires search_contacts",
    "boolean_operand:271:1:And": "outer relationship batch independently requires modify_contact",
    "boolean_operand:271:2:And": "A or (not A and B) is equivalent to A or B",
    "boolean_operand:271:3:And": "outer relationship batch independently requires a group",
    "boolean_operand:271:4:And": "outer relationship batch independently requires a target",
    "boolean_operand:290:2:And": "each direct-action alternative independently requires an allowed tool",
    "boolean_operand:308:0:And": "add_contact signal existence implies the add_contact tool",
    "boolean_operand:332:0:Or": "modify_contact signal existence implies the modify_contact tool",
    "boolean_operand:465:1:And": "message_counterparty_target implies search_messages",
    "boolean_operand:713:1:And": "reminder action signals imply the reminder domain signal",
    "boolean_operand:713:2:And": "reminder action signals imply an action tool",
    "boolean_operand:781:2:Or": "holiday is emitted after this forward-only dependency check",
    "boolean_operand:782:2:And": "location_phrase existence implies a location-search tool",
    "boolean_operand:786:1:And": "send_message existence implies its native send tool",
    "boolean_operand:787:1:And": "holiday is emitted after this forward-only dependency check",
    "string_constant:412:16:message_counterparty_lookup": (
        "message-counterparty lookup is emitted later, after this forward-only check"
    ),
    "string_constant:413:16:message_counterparty_update": (
        "message-counterparty update is emitted later, after this forward-only check"
    ),
    "string_constant:595:12:contact_update_by_id": (
        "ID-based updates also emit direct_contact_action before location suppression"
    ),
    "string_constant:611:12:message_recency": (
        "message_recency always emits the broader message signal"
    ),
    "string_constant:615:12:reminder_create": (
        "reminder creation always emits the broader reminder signal"
    ),
    "string_constant:616:12:reminder_modify": (
        "reminder modification always emits the broader reminder signal"
    ),
    "string_constant:617:12:reminder_remove": (
        "reminder removal always emits the broader reminder signal"
    ),
    "string_constant:688:16:message_recency": (
        "message_recency always emits the broader message signal"
    ),
    "string_constant:787:12:holiday": (
        "holiday is emitted after this forward-only dependency check"
    ),
    "string_constant:848:12:relationship_batch_update": (
        "relationship batches always emit the broader contact signal"
    ),
    "helper_string:_has_phone_like_value:2:33: ": (
        "UUID scrubbing consumes a boundary-delimited token, so an empty or space "
        "replacement cannot create a phone match"
    ),
    "helper_string:_has_phone_like_value:3:47: ": (
        "latitude/longitude scrubbing consumes a boundary-delimited span, so an "
        "empty or space replacement cannot create a phone match"
    ),
    "helper_string:_visible_weather_location_phrase_requested:4:9:temperature": (
        "the same substring predicate also contains the shorter 'temp' alias"
    ),
    "helper_string:_visible_weather_location_phrase_requested:4:55:celsius": (
        "celsius alone passes the domain precheck but no location-capture pattern"
    ),
    "helper_string:_visible_weather_location_phrase_requested:4:66:fahrenheit": (
        "fahrenheit alone passes the domain precheck but no location-capture pattern"
    ),
    "helper_string:_visible_weather_location_phrase_requested:40:39: .?!:;,'\"": (
        "punctuation stripping cannot change the later alphanumeric token-set test"
    ),
    "temporal_prefix:1:slash_date": (
        "the earlier clock alternative already matches the leading one or two date digits"
    ),
}


EXPECTED_MUTATION_AUDIT = {
    "inventory": {
        "byte_count": 51_382,
        "sha256": "0db6a83b154443a4b357adcbb69124aa2c29fa643acb15994c015eafbf5fa5d1",
    },
    "equivalence_groups": {
        "byte_count": 11_463,
        "sha256": "3dfd37487b994872178269fcae6be25e71e97630a038c87c8e6c1886cd056c78",
    },
    "carrier_pairings": {
        "byte_count": 1_322_851,
        "sha256": "e0b9c1666c1ec954207f9faf46ffb1f4164e9b9c9322db76e56a20313b492a59",
    },
    "mutation_count": 931,
    "caught_count": 862,
    "equivalent_count": 69,
}


# Frozen only after every candidate mutant is either distinguished by the
# external carrier corpus or proven externally equivalent.  The immutable
# reference maps above remain byte-for-byte unchanged.
CANDIDATE_EQUIVALENT_MUTANTS: dict[str, str] = {
    "boolean_operand:183:1:And": (
        "the outer contact-lookup rule independently requires search_contacts"
    ),
    "boolean_operand:213:0:And": (
        "the outer relationship-batch rule independently requires search_contacts"
    ),
    "boolean_operand:213:1:And": (
        "the outer relationship-batch rule independently requires modify_contact"
    ),
    "boolean_operand:213:2:And": (
        "A or (not A and B) is equivalent to A or B in the outer rule"
    ),
    "boolean_operand:213:3:And": (
        "the outer relationship-batch rule independently requires a group"
    ),
    "boolean_operand:213:4:And": (
        "the outer relationship-batch rule independently requires a target"
    ),
    "boolean_operand:232:2:And": (
        "each direct-action alternative independently requires an allowed tool"
    ),
    "boolean_operand:247:0:And": (
        "the add_contact signal already implies the add_contact tool"
    ),
    "boolean_operand:271:0:Or": (
        "the modify_contact signal already implies the modify_contact tool"
    ),
    "boolean_operand:351:1:And": (
        "message_counterparty_target already implies search_messages"
    ),
    "boolean_operand:550:1:And": (
        "the reminder action signals already imply the reminder domain signal"
    ),
    "boolean_operand:550:2:And": (
        "the reminder action signals already imply an action tool"
    ),
    "boolean_operand:605:2:Or": (
        "holiday is emitted after this forward-only dependency snapshot"
    ),
    "boolean_operand:606:2:And": (
        "location_phrase already implies a location-search tool"
    ),
    "boolean_operand:610:1:And": ("send_message already implies its native send tool"),
    "boolean_operand:611:1:And": (
        "holiday is emitted after this forward-only dependency snapshot"
    ),
    "helper_string:_has_phone_like_value:2:33: ": (
        "UUID scrubbing consumes a boundary-delimited token, so empty and space "
        "replacements are externally equivalent"
    ),
    "helper_string:_has_phone_like_value:3:47: ": (
        "coordinate scrubbing consumes a boundary-delimited span, so empty and "
        "space replacements are externally equivalent"
    ),
    "helper_string:_visible_weather_location_phrase_requested:4:9:temperature": (
        "the shorter temp alias dominates the same substring predicate"
    ),
    "helper_string:_visible_weather_location_phrase_requested:4:55:celsius": (
        "celsius alone reaches no weather-location capture pattern"
    ),
    "helper_string:_visible_weather_location_phrase_requested:4:66:fahrenheit": (
        "fahrenheit alone reaches no weather-location capture pattern"
    ),
    "helper_string:_visible_weather_location_phrase_requested:40:39: .?!:;,'\"": (
        "punctuation stripping cannot change the later alphanumeric token-set test"
    ),
    "signal_role:has_signal:328:1:message_counterparty_lookup": (
        "lookup is emitted later, after this forward-only recency snapshot"
    ),
    "signal_role:has_signal:328:2:message_counterparty_update": (
        "update is emitted later, after this forward-only recency snapshot"
    ),
    "signal_role:has_signal:447:2:remove_contact": (
        "requested_remove_contact is always present before remove_contact"
    ),
    "signal_role:has_signal:463:1:message_recency": (
        "message_recency always co-emits the broader message signal"
    ),
    "signal_role:has_signal:463:5:reminder_create": (
        "reminder creation always co-emits the broader reminder signal"
    ),
    "signal_role:has_signal:463:6:reminder_modify": (
        "reminder modification always co-emits the broader reminder signal"
    ),
    "signal_role:has_signal:463:7:reminder_remove": (
        "reminder removal always co-emits the broader reminder signal"
    ),
    "signal_role:has_signal:528:1:message_recency": (
        "message_recency always co-emits the broader message signal"
    ),
    "signal_role:direct_signals:611:12:holiday": (
        "holiday is emitted after this forward-only dependency snapshot"
    ),
    "signal_role:has_signal:657:1:add_contact": (
        "add-contact workflows already co-emit the broader contact signal"
    ),
    "signal_role:has_signal:657:3:remove_contact": (
        "requested_remove_contact is always present before remove_contact"
    ),
    "signal_role:has_signal:657:4:modify_contact": (
        "modify-contact workflows already co-emit the broader contact signal"
    ),
    "signal_role:has_signal:657:6:relationship_batch_update": (
        "relationship batches already co-emit the broader contact signal"
    ),
    "temporal_prefix:1:slash_date": (
        "the earlier clock alternative already matches the leading date digits"
    ),
    "text_role:has_text:52:1:i contacted last": (
        "contacted last is another alias in the shared recency core"
    ),
    "text_role:has_text:52:2:contacted most recently": (
        "recent/contacted broad predicates already match this phrase"
    ),
    "text_role:has_text:52:3:most recently contacted": (
        "recent/contacted broad predicates already match this phrase"
    ),
    "text_role:has_text:52:7:most recently talked": (
        "recent/talk broad predicates already match this phrase"
    ),
    "text_role:has_text:52:8:most recently spoke": (
        "recent/spoke broad predicates already match this phrase"
    ),
    "text_role:has_text:65:6:most recent message": (
        "recent is a shorter alias in the same predicate"
    ),
    "text_role:has_text:76:2:messages": (
        "message is a shorter alias in the same predicate"
    ),
    "text_role:has_text:76:11:talked": (
        "talk is a shorter alias in the same predicate"
    ),
    "text_role:has_text:98:1:mark as": (
        "mark-space is a shorter alias in the same predicate"
    ),
    "text_role:has_text:138:5:coworkers": (
        "coworker is a shorter alias in the same predicate"
    ),
    "text_role:has_text:138:6:bosses": (
        "boss is a shorter alias in the same predicate"
    ),
    "text_role:has_text:155:5:out of my contacts": (
        "out of my contact is a shorter alias in the same predicate"
    ),
    "text_role:has_text:206:1:all of": (
        "all-space is a shorter alias in the same predicate"
    ),
    "text_role:has_text:282:1:messages": (
        "message is a shorter alias in the same predicate"
    ),
    "text_role:has_text:322:1:messages": (
        "message is a shorter alias in the same predicate"
    ),
    "text_role:has_text:364:0:reminder": (
        "remind is a shorter alias in the same predicate"
    ),
    "text_role:has_text:477:4:first ever": (
        "first-space is a shorter alias in the same predicate"
    ),
    "text_role:has_text:577:13:access my current location": (
        "current location is a shorter alias in the same predicate"
    ),
    "text_role:has_text:666:0:temperature": (
        "temp is a shorter alias in the same predicate"
    ),
    "text_role:has_text:688:5:business": (
        "the earlier external-location phone predicate already matches business"
    ),
    "text_role:has_text:688:6:restaurant": (
        "the earlier external-location phone predicate already matches restaurant"
    ),
    "text_role:has_text:688:7:store": (
        "the earlier external-location phone predicate already matches store"
    ),
    "text_role:has_text:688:8:venue": (
        "the earlier external-location phone predicate already matches venue"
    ),
    "tool_role:direct_tools:611:37:search_holiday": (
        "holiday is emitted after this forward-only dependency snapshot"
    ),
    "helper_call:has_tool:234:1:true": (
        "forcing the direct-action tool-group check true is absorbed by the "
        "more specific tool-and-signal checks in every downstream action arm"
    ),
    "helper_call:has_tool:552:1:true": (
        "reminder_modify or reminder_remove already implies that one of the "
        "same reminder action tools is available"
    ),
    "helper_call:has_tool:608:1:true": (
        "location_phrase in this branch is only emitted when one of the same "
        "location-search tools is available"
    ),
    "shared_crosswire:use:contact_recency_core:27:32:message_counterparty_core": (
        "the replacement expands to contact_recency_core OR the exact aliases "
        "already present on the right side of this same assignment"
    ),
    "shared_crosswire:use:singular_contact_role:119:28:external_contact_role": (
        "the replacement expands to singular_contact_role OR the exact aliases "
        "already present on the right side of this same assignment"
    ),
    "shared_crosswire:use:singular_contact_role:137:15:external_contact_role": (
        "the broader external-contact aliases are already tested by the later "
        "has_text operand in this contact condition"
    ),
}


# Exhaustive local has_signal cross-wiring leaves only these proven semantic
# equivalence groups.  The replacement lists are explicit rather than inferred
# from source order so a candidate edit cannot silently broaden the exemption.
_SIGNAL_CROSSWIRE_EQUIVALENCE_GROUPS = (
    (
        328,
        1,
        "message_counterparty_lookup",
        (
            "calendar_distance",
            "currency_lookup",
            "device_state_action",
            "device_status_read",
            "direct_contact_action",
            "direct_device_state_action",
            "explicit_time",
            "external_lookup",
            "holiday",
            "location_phrase",
            "message",
            "message_counterparty_update",
            "message_recency",
            "message_recency_search",
            "message_search_followup_possible",
            "missing_current_time_prerequisite",
            "missing_reminder_time",
            "past_reminder_recency_search",
            "recency_action",
            "recency_search",
            "relative_time",
            "reminder",
            "reminder_create",
            "reminder_modify",
            "reminder_remove",
            "service_answer_extraction",
            "state_precondition_possible",
            "stock_lookup",
            "upcoming_reminder_search",
            "weekday_time",
        ),
        "replacement is forward-dead, already retained as message, or cannot "
        "coexist with the required chronology before this snapshot",
    ),
    (
        328,
        2,
        "message_counterparty_update",
        (
            "calendar_distance",
            "currency_lookup",
            "device_state_action",
            "device_status_read",
            "direct_contact_action",
            "direct_device_state_action",
            "explicit_time",
            "external_lookup",
            "holiday",
            "location_phrase",
            "message",
            "message_counterparty_lookup",
            "message_recency",
            "message_recency_search",
            "message_search_followup_possible",
            "missing_current_time_prerequisite",
            "missing_reminder_time",
            "past_reminder_recency_search",
            "recency_action",
            "recency_search",
            "relative_time",
            "reminder",
            "reminder_create",
            "reminder_modify",
            "reminder_remove",
            "service_answer_extraction",
            "state_precondition_possible",
            "stock_lookup",
            "upcoming_reminder_search",
            "weekday_time",
        ),
        "replacement is forward-dead, already retained as message, or cannot "
        "coexist with the required chronology before this snapshot",
    ),
    (
        447,
        2,
        "remove_contact",
        (
            "add_contact",
            "calendar_distance",
            "contact_lookup",
            "contact_update_by_id",
            "currency_lookup",
            "device_state_action",
            "device_status_read",
            "direct_contact_action",
            "direct_device_state_action",
            "external_lookup",
            "holiday",
            "location_phrase",
            "message_recency_search",
            "missing_current_time_prerequisite",
            "modify_contact",
            "past_reminder_recency_search",
            "recency_action",
            "recency_search",
            "relationship_batch_update",
            "requested_remove_contact",
            "service_answer_extraction",
            "state_precondition_possible",
            "stock_lookup",
            "upcoming_reminder_search",
        ),
        "remove_contact is absorbed by requested_remove_contact; replacements "
        "are retained workflow arms or forward-dead at this snapshot",
    ),
    (
        463,
        1,
        "message_recency",
        (
            "calendar_distance",
            "currency_lookup",
            "device_state_action",
            "device_status_read",
            "direct_device_state_action",
            "external_lookup",
            "holiday",
            "message",
            "message_counterparty_lookup",
            "message_counterparty_update",
            "message_recency_search",
            "message_search_followup_possible",
            "missing_current_time_prerequisite",
            "missing_reminder_time",
            "past_reminder_recency_search",
            "recency_action",
            "recency_search",
            "reminder",
            "reminder_create",
            "reminder_modify",
            "reminder_remove",
            "service_answer_extraction",
            "state_precondition_possible",
            "stock_lookup",
            "upcoming_reminder_search",
        ),
        "message_recency is absorbed by message; replacements are another "
        "retained domain arm, imply it, or are forward-dead",
    ),
    (
        463,
        5,
        "reminder_create",
        (
            "calendar_distance",
            "currency_lookup",
            "device_state_action",
            "device_status_read",
            "direct_device_state_action",
            "external_lookup",
            "holiday",
            "message",
            "message_counterparty_lookup",
            "message_counterparty_update",
            "message_recency",
            "message_recency_search",
            "message_search_followup_possible",
            "missing_current_time_prerequisite",
            "missing_reminder_time",
            "past_reminder_recency_search",
            "recency_action",
            "recency_search",
            "reminder",
            "reminder_modify",
            "reminder_remove",
            "service_answer_extraction",
            "state_precondition_possible",
            "stock_lookup",
            "upcoming_reminder_search",
        ),
        "reminder_create is absorbed by reminder; replacements are another "
        "retained domain arm, imply it, or are forward-dead",
    ),
    (
        463,
        6,
        "reminder_modify",
        (
            "calendar_distance",
            "currency_lookup",
            "device_state_action",
            "device_status_read",
            "direct_device_state_action",
            "external_lookup",
            "holiday",
            "message",
            "message_counterparty_lookup",
            "message_counterparty_update",
            "message_recency",
            "message_recency_search",
            "message_search_followup_possible",
            "missing_current_time_prerequisite",
            "missing_reminder_time",
            "past_reminder_recency_search",
            "recency_action",
            "recency_search",
            "reminder",
            "reminder_create",
            "reminder_remove",
            "service_answer_extraction",
            "state_precondition_possible",
            "stock_lookup",
            "upcoming_reminder_search",
        ),
        "reminder_modify is absorbed by reminder; replacements are another "
        "retained domain arm, imply it, or are forward-dead",
    ),
    (
        463,
        7,
        "reminder_remove",
        (
            "calendar_distance",
            "currency_lookup",
            "device_state_action",
            "device_status_read",
            "direct_device_state_action",
            "external_lookup",
            "holiday",
            "message",
            "message_counterparty_lookup",
            "message_counterparty_update",
            "message_recency",
            "message_recency_search",
            "message_search_followup_possible",
            "missing_current_time_prerequisite",
            "missing_reminder_time",
            "past_reminder_recency_search",
            "recency_action",
            "recency_search",
            "reminder",
            "reminder_create",
            "reminder_modify",
            "service_answer_extraction",
            "state_precondition_possible",
            "stock_lookup",
            "upcoming_reminder_search",
        ),
        "reminder_remove is absorbed by reminder; replacements are another "
        "retained domain arm, imply it, or are forward-dead",
    ),
    (
        528,
        1,
        "message_recency",
        (
            "calendar_distance",
            "currency_lookup",
            "device_state_action",
            "device_status_read",
            "direct_device_state_action",
            "external_lookup",
            "holiday",
            "message",
            "message_counterparty_lookup",
            "message_counterparty_update",
            "message_recency_search",
            "message_search_followup_possible",
            "past_reminder_recency_search",
            "recency_action",
            "service_answer_extraction",
            "state_precondition_possible",
            "stock_lookup",
        ),
        "message_recency is absorbed by message; replacements imply message, "
        "cannot coexist with reminder recency, or are forward-dead",
    ),
    (
        657,
        1,
        "add_contact",
        (
            "contact",
            "contact_lookup",
            "contact_update_by_id",
            "currency_lookup",
            "direct_contact_action",
            "external_lookup",
            "message_counterparty_update",
            "modify_contact",
            "named_message_recipient",
            "relationship_batch_update",
            "remove_contact",
            "requested_remove_contact",
            "service_answer_extraction",
            "stock_lookup",
        ),
        "add_contact is absorbed by contact; replacements are retained contact "
        "arms, forward-dead, or independently force the external-query branch",
    ),
    (
        657,
        3,
        "remove_contact",
        (
            "add_contact",
            "contact",
            "contact_lookup",
            "contact_update_by_id",
            "currency_lookup",
            "direct_contact_action",
            "external_lookup",
            "message_counterparty_update",
            "modify_contact",
            "named_message_recipient",
            "relationship_batch_update",
            "requested_remove_contact",
            "service_answer_extraction",
            "stock_lookup",
        ),
        "remove_contact is absorbed by requested_remove_contact; replacements "
        "are retained contact arms, forward-dead, or independently force the "
        "external-query branch",
    ),
    (
        657,
        4,
        "modify_contact",
        (
            "add_contact",
            "contact",
            "contact_lookup",
            "contact_update_by_id",
            "currency_lookup",
            "direct_contact_action",
            "external_lookup",
            "message_counterparty_update",
            "named_message_recipient",
            "relationship_batch_update",
            "remove_contact",
            "requested_remove_contact",
            "service_answer_extraction",
            "stock_lookup",
        ),
        "modify_contact is absorbed by contact; replacements are retained "
        "contact arms, forward-dead, or independently force the external-query "
        "branch",
    ),
    (
        657,
        6,
        "relationship_batch_update",
        (
            "add_contact",
            "contact",
            "contact_lookup",
            "contact_update_by_id",
            "currency_lookup",
            "direct_contact_action",
            "external_lookup",
            "message_counterparty_update",
            "modify_contact",
            "named_message_recipient",
            "remove_contact",
            "requested_remove_contact",
            "service_answer_extraction",
            "stock_lookup",
        ),
        "relationship_batch_update is absorbed by contact; replacements are "
        "retained contact arms, forward-dead, or independently force the "
        "external-query branch",
    ),
)

for (
    _line,
    _index,
    _original,
    _replacements,
    _reason,
) in _SIGNAL_CROSSWIRE_EQUIVALENCE_GROUPS:
    for _replacement in _replacements:
        _key = (
            "role_crosswire:signal_role:has_signal:"
            f"{_original}:{_line}:{_index}:{_replacement}"
        )
        if _key in CANDIDATE_EQUIVALENT_MUTANTS:
            raise AssertionError(f"duplicate candidate equivalence {_key}")
        CANDIDATE_EQUIVALENT_MUTANTS[_key] = _reason

if sum(len(group[3]) for group in _SIGNAL_CROSSWIRE_EQUIVALENCE_GROUPS) != 257:
    raise AssertionError("candidate signal-crosswire equivalence manifest changed")

_DIRECT_ROLE_CROSSWIRE_EQUIVALENCES = {
    "role_crosswire:signal_role:direct_signals:reminder:551:12:recency_search": (
        "the preceding recency_search requirement is unchanged and reminder action "
        "signals already imply the reminder domain"
    ),
    **{
        (f"role_crosswire:signal_role:direct_signals:holiday:611:12:{replacement}"): (
            "the replacement is forward-dead, contradicts the enclosing safe guard, "
            "or is absorbed by the preceding send dependency arm"
        )
        for replacement in (
            "calendar_distance",
            "currency_lookup",
            "external_lookup",
            "missing_current_time_prerequisite",
            "named_message_recipient",
            "safe_abstain_needed",
            "send_message",
            "service_answer_extraction",
            "state_precondition_possible",
            "stock_lookup",
        )
    },
    "role_crosswire:tool_role:direct_tools:search_contacts:213:8:modify_contact": (
        "the outer relationship-batch condition independently requires both tools"
    ),
    "role_crosswire:tool_role:direct_tools:modify_contact:214:12:search_contacts": (
        "the outer relationship-batch condition independently requires both tools"
    ),
    "role_crosswire:tool_role:direct_tools:search_messages:352:12:modify_contact": (
        "message_counterparty_target already implies search_messages and the outer "
        "update rule independently requires modify_contact"
    ),
    **{
        (
            f"role_crosswire:tool_role:direct_tools:search_holiday:611:37:{replacement}"
        ): "holiday is emitted after this forward-only dependency snapshot"
        for replacement in sorted(_TOOL_NAMES - {"search_holiday"})
    },
}

if len(_DIRECT_ROLE_CROSSWIRE_EQUIVALENCES) != 39:
    raise AssertionError("candidate direct-role equivalence manifest changed")
for _key, _reason in _DIRECT_ROLE_CROSSWIRE_EQUIVALENCES.items():
    if _key in CANDIDATE_EQUIVALENT_MUTANTS:
        raise AssertionError(f"duplicate candidate equivalence {_key}")
    CANDIDATE_EQUIVALENT_MUTANTS[_key] = _reason

CANDIDATE_EXPECTED_MUTATION_AUDIT: dict[str, Any] = {
    "inventory": {
        "byte_count": 866_301,
        "sha256": "e0ba9cca68dc47e99763ec1babe77ea5c6c0b25b2269eef5c49ea6b33b4eabfe",
    },
    "equivalence_groups": {
        "byte_count": 95_322,
        "sha256": "111ba5fb1e8e0b42815dde21ba58e7d9dbf6d63c5692555575cf05cb6421dfbd",
    },
    "carrier_pairings": {
        "byte_count": 21_139_427,
        "sha256": "a07d08729171dfe3a94962d6b58bed3369e8ca793b74b25763092edb68afec92",
    },
    "mutation_count": 8_736,
    "caught_count": 8_374,
    "equivalent_count": 362,
}


@dataclass(frozen=True, order=True)
class Mutation:
    kind: MutationKind
    line: int
    index: int
    value: str
    scope: str = "_visible_task_signals"

    @property
    def key(self) -> str:
        if self.kind == "helper_string":
            return f"{self.kind}:{self.scope}:{self.line}:{self.index}:{self.value}"
        if self.kind == "temporal_prefix":
            return f"{self.kind}:{self.index}:{self.value}"
        if self.kind in {
            "text_role",
            "text_membership",
            "tool_role",
            "signal_role",
            "regex_literal",
            "text_normalization",
            "tool_normalization",
            "return_shape",
            "family_semantics",
            "role_crosswire",
            "helper_call",
            "shared_definition",
            "shared_use",
            "shared_crosswire",
            "evaluation_order",
            "local_helper",
        }:
            return f"{self.kind}:{self.scope}:{self.line}:{self.index}:{self.value}"
        return f"{self.kind}:{self.line}:{self.index}:{self.value}"


def _production_context() -> tuple[Any, str, ast.Module]:
    classifier = inspect.getmodule(contracts._production_functions()[0])
    if classifier is None:
        raise RuntimeError("could not resolve visible-signal classifier module")
    source = inspect.getsource(classifier._visible_task_signals)
    return classifier, source, ast.parse(source)


def current_profile_identity() -> dict[str, Any]:
    """Return stable exact-source and formatting-independent AST identities."""

    classifier, source, tree = _production_context()
    ast_body = ast.dump(tree, annotate_fields=True, include_attributes=False)
    identity = {
        "source_byte_count": len(source.encode("utf-8")),
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "ast_byte_count": len(ast_body.encode("utf-8")),
        "ast_sha256": hashlib.sha256(ast_body.encode("utf-8")).hexdigest(),
    }
    candidate_base = {
        key: PROFILE_IDENTITIES[CANDIDATE_PROFILE][key]
        for key in (
            "source_byte_count",
            "source_sha256",
            "ast_byte_count",
            "ast_sha256",
        )
    }
    if identity != candidate_base:
        return identity

    dependency_names = ("_has_any", *_HELPER_FUNCTIONS, "_visible_primary_family")
    dependency_sources = tuple(
        (name, inspect.getsource(getattr(classifier, name)))
        for name in dependency_names
    )
    temporal = classifier._TEMPORAL_LOCATION_PREFIX_RE
    dependency_source_body = repr(
        (
            dependency_sources,
            temporal.pattern,
            temporal.flags,
        )
    )
    dependency_ast_body = repr(
        (
            tuple(
                (
                    name,
                    ast.dump(
                        ast.parse(helper_source),
                        annotate_fields=True,
                        include_attributes=False,
                    ),
                )
                for name, helper_source in dependency_sources
            ),
            temporal.pattern,
            temporal.flags,
        )
    )
    identity.update(
        {
            "dependency_source_byte_count": len(dependency_source_body.encode("utf-8")),
            "dependency_source_sha256": hashlib.sha256(
                dependency_source_body.encode("utf-8")
            ).hexdigest(),
            "dependency_ast_byte_count": len(dependency_ast_body.encode("utf-8")),
            "dependency_ast_sha256": hashlib.sha256(
                dependency_ast_body.encode("utf-8")
            ).hexdigest(),
        }
    )
    return identity


def current_profile() -> str:
    """Fail closed unless the imported implementation has a frozen shape."""

    identity = current_profile_identity()
    matches = [
        name for name, expected in PROFILE_IDENTITIES.items() if identity == expected
    ]
    if len(matches) != 1:
        raise ValueError(
            "visible-signal source does not match a frozen mutation profile: "
            f"{identity!r}"
        )
    return matches[0]


def _enumerate_reference_mutations() -> tuple[Mutation, ...]:
    """Enumerate current source mutation sites without affecting live replay."""

    _classifier, _source, tree = _production_context()
    mutations: list[Mutation] = []
    has_any_literal_locations: set[tuple[int, int]] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_has_any"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Tuple)
        ):
            for index, element in enumerate(node.args[1].elts):
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    has_any_literal_locations.add((element.lineno, element.col_offset))
                    mutations.append(
                        Mutation("literal", node.lineno, index, element.value)
                    )
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value in _TOOL_NAMES
        ):
            mutations.append(Mutation("tool", node.lineno, node.col_offset, node.value))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value not in _TOOL_NAMES
            and (node.lineno, node.col_offset) not in has_any_literal_locations
        ):
            mutations.append(
                Mutation(
                    "string_constant",
                    node.lineno,
                    node.col_offset,
                    node.value,
                )
            )
    for node in ast.walk(tree):
        if isinstance(node, ast.BoolOp):
            for index in range(len(node.values)):
                mutations.append(
                    Mutation(
                        "boolean_operand",
                        node.lineno,
                        index,
                        type(node.op).__name__,
                    )
                )
    for helper_name in _HELPER_FUNCTIONS:
        helper = getattr(_classifier, helper_name)
        helper_tree = ast.parse(inspect.getsource(helper))
        for node in ast.walk(helper_tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value
            ):
                mutations.append(
                    Mutation(
                        "helper_string",
                        node.lineno,
                        node.col_offset,
                        node.value,
                        scope=helper_name,
                    )
                )
    mutations.extend(
        Mutation(
            "temporal_prefix",
            0,
            index,
            name,
            scope="_TEMPORAL_LOCATION_PREFIX_RE",
        )
        for index, (name, _segment) in enumerate(_TEMPORAL_PREFIX_SEGMENTS)
    )
    return tuple(sorted(mutations))


_CANDIDATE_ROLE_CALLS: dict[str, MutationKind] = {
    "has_text": "text_role",
    "has_tool": "tool_role",
    "has_signal": "signal_role",
}


_CANDIDATE_SHARED_FACTS = (
    "contact_recency_core",
    "message_counterparty_core",
    "message_chronology_core",
    "basic_change_intent",
    "basic_removal_intent",
    "singular_contact_role",
    "plural_contact_role",
    "external_contact_role",
    "service_value_term",
)


_CANDIDATE_SHARED_USE_COUNTS = {
    "contact_recency_core": 2,
    "message_counterparty_core": 2,
    "message_chronology_core": 3,
    "basic_change_intent": 5,
    "basic_removal_intent": 2,
    "singular_contact_role": 4,
    "plural_contact_role": 2,
    "external_contact_role": 1,
    "service_value_term": 2,
}


def _append_shared_helper_mutations(mutations: list[Mutation], classifier: Any) -> None:
    for helper_name in _HELPER_FUNCTIONS:
        helper = getattr(classifier, helper_name)
        helper_tree = ast.parse(inspect.getsource(helper))
        for node in ast.walk(helper_tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value
            ):
                mutations.append(
                    Mutation(
                        "helper_string",
                        node.lineno,
                        node.col_offset,
                        node.value,
                        scope=helper_name,
                    )
                )
    mutations.extend(
        Mutation(
            "temporal_prefix",
            0,
            index,
            name,
            scope="_TEMPORAL_LOCATION_PREFIX_RE",
        )
        for index, (name, _segment) in enumerate(_TEMPORAL_PREFIX_SEGMENTS)
    )


def _enumerate_candidate_mutations() -> tuple[Mutation, ...]:
    """Enumerate every candidate rule, shared fact, and local helper seam."""

    classifier, _source, tree = _production_context()
    function = tree.body[0]
    if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise AssertionError("visible-signal source did not parse as one function")

    mutations: list[Mutation] = []
    role_locations: set[tuple[int, int]] = set()
    direct_role_locations: set[tuple[int, int]] = set()
    parents: dict[ast.AST, ast.AST] = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }

    initial_assignments = {
        statement.targets[0].id: statement
        for statement in function.body
        if isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
        and statement.targets[0].id in {"text", "tools"}
    }
    if set(initial_assignments) != {"text", "tools"}:
        raise AssertionError("candidate input-normalization assignments changed")
    mutations.extend(
        (
            Mutation(
                "text_normalization",
                initial_assignments["text"].lineno,
                initial_assignments["text"].col_offset,
                "casefold",
                scope="text",
            ),
            *(
                Mutation(
                    "tool_normalization",
                    initial_assignments["tools"].lineno,
                    index,
                    variant,
                    scope="tools",
                )
                for index, variant in enumerate(
                    (
                        "lower_each",
                        "strip_each",
                        "hyphen_to_underscore",
                        "space_to_underscore",
                        "remove_underscores",
                    )
                )
            ),
        )
    )
    return_nodes = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Return)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "tuple"
        and len(node.value.args) == 1
        and isinstance(node.value.args[0], ast.Name)
        and node.value.args[0].id == "signals"
    ]
    if len(return_nodes) != 1:
        raise AssertionError(
            f"candidate has {len(return_nodes)} tuple-signal returns instead of one"
        )
    return_node = return_nodes[0]
    mutations.append(
        Mutation(
            "return_shape",
            return_node.lineno,
            return_node.col_offset,
            "list",
            scope="signals",
        )
    )
    family_tree = ast.parse(inspect.getsource(classifier._visible_primary_family))
    family_memberships = [
        node
        for node in ast.walk(family_tree)
        if isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.In)
        and isinstance(node.left, ast.Name)
        and node.left.id == "signal"
        and len(node.comparators) == 1
        and isinstance(node.comparators[0], ast.Name)
        and node.comparators[0].id == "signals"
    ]
    if len(family_memberships) != 1:
        raise AssertionError("candidate primary-family membership expression changed")
    family_membership = family_memberships[0]
    mutations.append(
        Mutation(
            "family_semantics",
            family_membership.lineno,
            family_membership.col_offset,
            "identity_membership",
            scope="_visible_primary_family",
        )
    )

    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _CANDIDATE_ROLE_CALLS
        ):
            continue
        kind = _CANDIDATE_ROLE_CALLS[node.func.id]
        for index, replacement in enumerate(("false", "true")):
            mutations.append(
                Mutation(
                    "helper_call",
                    node.lineno,
                    index,
                    replacement,
                    scope=node.func.id,
                )
            )
        for index, argument in enumerate(node.args):
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                role_locations.add((argument.lineno, argument.col_offset))
                mutations.append(
                    Mutation(
                        kind,
                        node.lineno,
                        index,
                        argument.value,
                        scope=node.func.id,
                    )
                )

    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        location = (node.lineno, node.col_offset)
        if location in role_locations:
            continue
        parent = parents.get(node)
        kind: MutationKind | None = None
        scope = "direct"
        if (
            isinstance(parent, ast.Call)
            and isinstance(parent.func, ast.Name)
            and parent.func.id == "add"
            and parent.args
            and parent.args[0] is node
        ):
            kind = "signal_role"
            scope = "add"
        elif isinstance(parent, ast.Compare):
            names = {
                candidate.id
                for candidate in (parent.left, *parent.comparators)
                if isinstance(candidate, ast.Name)
            }
            if "tools" in names:
                kind = "tool_role"
                scope = "direct_tools"
            elif "signals" in names:
                kind = "signal_role"
                scope = "direct_signals"
            elif "text" in names:
                kind = "text_membership"
                scope = "direct_text"
        if (
            kind is None
            and isinstance(parent, ast.Call)
            and isinstance(parent.func, ast.Attribute)
            and isinstance(parent.func.value, ast.Name)
            and parent.func.value.id == "re"
            and parent.func.attr in {"search", "match", "fullmatch"}
            and parent.args
            and parent.args[0] is node
        ):
            kind = "regex_literal"
            scope = f"re.{parent.func.attr}"
        if kind is not None:
            direct_role_locations.add(location)
            mutations.append(
                Mutation(kind, node.lineno, node.col_offset, node.value, scope=scope)
            )

    remaining_strings = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and (node.lineno, node.col_offset) not in role_locations
        and (node.lineno, node.col_offset) not in direct_role_locations
    ]
    if remaining_strings:
        raise AssertionError(
            "candidate contains unclassified behavior-defining strings: "
            + ", ".join(
                f"{node.lineno}:{node.col_offset}:{node.value!r}"
                for node in remaining_strings
            )
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.BoolOp):
            for index in range(len(node.values)):
                mutations.append(
                    Mutation(
                        "boolean_operand",
                        node.lineno,
                        index,
                        type(node.op).__name__,
                        scope="candidate",
                    )
                )

    excluded_assignments = {"text", "tools", "signals"}
    shared_assignments: dict[str, ast.Assign] = {}
    for statement in function.body:
        if not (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
        ):
            continue
        name = statement.targets[0].id
        if name in excluded_assignments:
            continue
        shared_assignments[name] = statement
        for index, replacement in enumerate(("false", "true")):
            mutations.append(
                Mutation(
                    "shared_definition",
                    statement.lineno,
                    index,
                    replacement,
                    scope=name,
                )
            )

    missing_shared_facts = set(_CANDIDATE_SHARED_FACTS) - shared_assignments.keys()
    if missing_shared_facts:
        raise AssertionError(
            f"candidate shared facts are missing: {sorted(missing_shared_facts)!r}"
        )
    for target_name in _CANDIDATE_SHARED_FACTS:
        statement = shared_assignments[target_name]
        for replacement_name in _CANDIDATE_SHARED_FACTS:
            if replacement_name == target_name:
                continue
            mutations.append(
                Mutation(
                    "shared_crosswire",
                    statement.lineno,
                    statement.col_offset,
                    replacement_name,
                    scope=f"definition:{target_name}",
                )
            )

    shared_uses: dict[str, list[ast.Name]] = {
        name: [] for name in _CANDIDATE_SHARED_FACTS
    }
    for node in ast.walk(function):
        if (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in shared_uses
        ):
            shared_uses[node.id].append(node)
    actual_use_counts = {name: len(nodes) for name, nodes in shared_uses.items()}
    if actual_use_counts != _CANDIDATE_SHARED_USE_COUNTS:
        raise AssertionError(
            "candidate shared-fact consumer manifest changed: "
            f"expected={_CANDIDATE_SHARED_USE_COUNTS!r}, "
            f"actual={actual_use_counts!r}"
        )
    for source_name, nodes in shared_uses.items():
        for node in nodes:
            for index, replacement in enumerate(("false", "true")):
                mutations.append(
                    Mutation(
                        "shared_use",
                        node.lineno,
                        node.col_offset,
                        replacement,
                        scope=source_name,
                    )
                )
            for replacement_name in _CANDIDATE_SHARED_FACTS:
                if replacement_name == source_name:
                    continue
                mutations.append(
                    Mutation(
                        "shared_crosswire",
                        node.lineno,
                        node.col_offset,
                        replacement_name,
                        scope=f"use:{source_name}",
                    )
                )

    for statement in function.body:
        if not isinstance(statement, ast.FunctionDef):
            continue
        if statement.name in _CANDIDATE_ROLE_CALLS:
            variants = ["false", "true", "all"]
            if statement.name == "has_text":
                variants.extend(
                    ("first_requested", "negated", "raw_request", "casefold_text")
                )
            elif statement.name == "has_tool":
                variants.extend(
                    (
                        "first_requested",
                        "first_available",
                        "remove_not",
                        "read_signals",
                        "lower_available",
                        "strip_available",
                        "available_substring",
                        "available_prefix",
                        "available_suffix",
                        "requested_substring",
                        "requested_prefix",
                        "requested_suffix",
                        "hyphen_to_underscore",
                        "space_to_underscore",
                        "remove_underscores",
                        "identity_membership",
                    )
                )
            elif statement.name == "has_signal":
                variants.extend(
                    (
                        "eager_snapshot",
                        "first_requested",
                        "first_emitted",
                        "not_in",
                        "read_tools",
                    )
                )
        elif statement.name == "add":
            variants = ["omit", "ignore_condition", "allow_duplicates", "prepend"]
        else:
            continue
        for index, variant in enumerate(variants):
            mutations.append(
                Mutation(
                    "local_helper",
                    statement.lineno,
                    index,
                    variant,
                    scope=statement.name,
                )
            )

    has_signal_calls = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "has_signal"
    ]
    if len(has_signal_calls) != 6:
        raise AssertionError(
            f"candidate has {len(has_signal_calls)} has_signal calls instead of six"
        )
    mutations.extend(
        Mutation(
            "evaluation_order",
            node.lineno,
            node.col_offset,
            "snapshot",
            scope="has_signal_call",
        )
        for node in has_signal_calls
    )
    add_calls = {
        node.args[0].value: node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "add"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    for label, scope in (
        ("message_counterparty_lookup", "counterparty_before_recency"),
        ("holiday", "holiday_before_state_dependency"),
    ):
        call = add_calls.get(label)
        if call is None:
            raise AssertionError(f"candidate add call {label!r} is missing")
        mutations.append(
            Mutation(
                "evaluation_order",
                call.lineno,
                call.col_offset,
                "move_earlier",
                scope=scope,
            )
        )

    _append_shared_helper_mutations(mutations, classifier)
    # Exhaustively cross-wire every finite tool/signal role: helper arguments,
    # direct memberships, and emitted add labels.  Text aliases remain covered
    # by exhaustive deletion because their free-form replacement universe is
    # intentionally not claimed to be finite.
    finite_roles = [
        mutation
        for mutation in mutations
        if mutation.kind in {"signal_role", "tool_role"}
    ]
    signal_roles = [
        mutation for mutation in finite_roles if mutation.kind == "signal_role"
    ]
    tool_roles = [mutation for mutation in finite_roles if mutation.kind == "tool_role"]
    if len(signal_roles) != 117 or len(tool_roles) != 89:
        raise AssertionError(
            "candidate finite-role manifest changed: "
            f"signals={len(signal_roles)}, tools={len(tool_roles)}"
        )
    replacement_domains = {
        "signal_role": tuple(contracts._ALL_FINAL_SIGNALS),
        "tool_role": tuple(sorted(_TOOL_NAMES)),
    }
    for role in finite_roles:
        for replacement in replacement_domains[role.kind]:
            if replacement == role.value:
                continue
            mutations.append(
                Mutation(
                    "role_crosswire",
                    role.line,
                    role.index,
                    replacement,
                    scope=f"{role.kind}:{role.scope}:{role.value}",
                )
            )
    return tuple(sorted(mutations))


def enumerate_mutations(profile: str | None = None) -> tuple[Mutation, ...]:
    selected = profile or current_profile()
    if selected == REFERENCE_PROFILE:
        return _enumerate_reference_mutations()
    if selected == CANDIDATE_PROFILE:
        return _enumerate_candidate_mutations()
    raise ValueError(f"unknown visible-signal mutation profile: {selected!r}")


def _candidate_shared_expressions(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, ast.expr]:
    assignments = {
        statement.targets[0].id: statement.value
        for statement in function.body
        if isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
        and statement.targets[0].id in _CANDIDATE_SHARED_FACTS
    }
    if set(assignments) != set(_CANDIDATE_SHARED_FACTS):
        raise AssertionError("candidate shared-expression manifest changed")

    expanded: dict[str, ast.expr] = {}

    def expand(name: str, stack: tuple[str, ...] = ()) -> ast.expr:
        if name in expanded:
            return copy.deepcopy(expanded[name])
        if name in stack:
            raise AssertionError(
                f"candidate shared facts contain a cycle: {stack + (name,)!r}"
            )

        class _DependencyExpander(ast.NodeTransformer):
            def visit_Name(self, node: ast.Name) -> Any:  # noqa: N802 - ast API
                if (
                    isinstance(node.ctx, ast.Load)
                    and node.id in _CANDIDATE_SHARED_FACTS
                ):
                    return ast.copy_location(expand(node.id, stack + (name,)), node)
                return node

        expression = _DependencyExpander().visit(copy.deepcopy(assignments[name]))
        ast.fix_missing_locations(expression)
        expanded[name] = expression
        return copy.deepcopy(expression)

    return {name: expand(name) for name in _CANDIDATE_SHARED_FACTS}


class _Mutator(ast.NodeTransformer):
    def __init__(
        self,
        mutation: Mutation,
        shared_expressions: dict[str, ast.expr] | None = None,
    ) -> None:
        self.mutation = mutation
        self.shared_expressions = shared_expressions or {}
        self.applied = 0
        self.snapshot_call: ast.Call | None = None

    def visit_Call(self, node: ast.Call) -> Any:  # noqa: N802 - ast API
        self.generic_visit(node)
        mutation = self.mutation
        if mutation.kind == "role_crosswire":
            original_kind, original_scope, original_value = mutation.scope.split(":", 2)
            expected_kind = _CANDIDATE_ROLE_CALLS.get(original_scope)
            if (
                expected_kind == original_kind
                and node.lineno == mutation.line
                and isinstance(node.func, ast.Name)
                and node.func.id == original_scope
                and 0 <= mutation.index < len(node.args)
            ):
                argument = node.args[mutation.index]
                if (
                    isinstance(argument, ast.Constant)
                    and argument.value == original_value
                ):
                    node.args[mutation.index] = ast.copy_location(
                        ast.Constant(value=mutation.value), argument
                    )
                    self.applied += 1
            return node
        if (
            mutation.kind == "helper_call"
            and node.lineno == mutation.line
            and isinstance(node.func, ast.Name)
            and node.func.id == mutation.scope
            and mutation.value in {"false", "true"}
        ):
            self.applied += 1
            return ast.copy_location(
                ast.Constant(value=mutation.value == "true"),
                node,
            )
        if (
            mutation.kind == "evaluation_order"
            and mutation.scope == "has_signal_call"
            and node.lineno == mutation.line
            and node.col_offset == mutation.index
            and isinstance(node.func, ast.Name)
            and node.func.id == "has_signal"
        ):
            self.snapshot_call = copy.deepcopy(node)
            self.applied += 1
            return ast.copy_location(
                ast.Name(id="_early_has_signal_snapshot", ctx=ast.Load()),
                node,
            )
        if (
            mutation.kind in {"text_role", "tool_role", "signal_role"}
            and mutation.scope in _CANDIDATE_ROLE_CALLS
            and node.lineno == mutation.line
            and isinstance(node.func, ast.Name)
            and node.func.id == mutation.scope
        ):
            if not 0 <= mutation.index < len(node.args):
                return node
            argument = node.args[mutation.index]
            if not (
                isinstance(argument, ast.Constant) and argument.value == mutation.value
            ):
                return node
            node.args = [
                value
                for index, value in enumerate(node.args)
                if index != mutation.index
            ]
            self.applied += 1
            return node
        if (
            mutation.kind == "literal"
            and node.lineno == mutation.line
            and isinstance(node.func, ast.Name)
            and node.func.id == "_has_any"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Tuple)
        ):
            elements = node.args[1].elts
            if not 0 <= mutation.index < len(elements):
                return node
            element = elements[mutation.index]
            if not (
                isinstance(element, ast.Constant) and element.value == mutation.value
            ):
                return node
            node.args[1] = ast.copy_location(
                ast.Tuple(
                    elts=[
                        item
                        for index, item in enumerate(elements)
                        if index != mutation.index
                    ],
                    ctx=ast.Load(),
                ),
                node.args[1],
            )
            self.applied += 1
        return node

    def visit_Name(self, node: ast.Name) -> Any:  # noqa: N802 - ast API
        mutation = self.mutation
        if (
            mutation.kind == "shared_use"
            and node.lineno == mutation.line
            and node.col_offset == mutation.index
            and isinstance(node.ctx, ast.Load)
            and node.id == mutation.scope
            and mutation.value in {"false", "true"}
        ):
            self.applied += 1
            return ast.copy_location(
                ast.Constant(value=mutation.value == "true"),
                node,
            )
        if mutation.kind == "shared_crosswire" and mutation.scope.startswith("use:"):
            source_name = mutation.scope.removeprefix("use:")
            if (
                node.lineno == mutation.line
                and node.col_offset == mutation.index
                and isinstance(node.ctx, ast.Load)
                and node.id == source_name
            ):
                replacement = self.shared_expressions.get(mutation.value)
                if replacement is None:
                    raise AssertionError(
                        f"unknown candidate shared fact {mutation.value!r}"
                    )
                self.applied += 1
                return ast.copy_location(copy.deepcopy(replacement), node)
        return node

    def _visit_string_sequence(self, node: ast.Tuple | ast.Set) -> Any:
        mutation = self.mutation
        if (
            mutation.kind
            in {
                "string_constant",
                "helper_string",
                "tool_role",
                "signal_role",
            }
            and mutation.scope not in _CANDIDATE_ROLE_CALLS
        ):
            retained: list[ast.expr] = []
            for element in node.elts:
                if (
                    isinstance(element, ast.Constant)
                    and element.lineno == mutation.line
                    and element.col_offset == mutation.index
                    and element.value == mutation.value
                ):
                    self.applied += 1
                else:
                    retained.append(element)
            node.elts = retained
        self.generic_visit(node)
        return node

    def visit_Tuple(self, node: ast.Tuple) -> Any:  # noqa: N802 - ast API
        return self._visit_string_sequence(node)

    def visit_Set(self, node: ast.Set) -> Any:  # noqa: N802 - ast API
        return self._visit_string_sequence(node)

    def visit_Constant(self, node: ast.Constant) -> Any:  # noqa: N802 - ast API
        mutation = self.mutation
        if mutation.kind == "role_crosswire":
            original_kind, original_scope, original_value = mutation.scope.split(":", 2)
            if (
                original_kind in {"signal_role", "tool_role"}
                and original_scope not in _CANDIDATE_ROLE_CALLS
                and node.lineno == mutation.line
                and node.col_offset == mutation.index
                and node.value == original_value
            ):
                self.applied += 1
                return ast.copy_location(ast.Constant(value=mutation.value), node)
        if (
            mutation.kind in {"text_membership", "regex_literal"}
            and node.lineno == mutation.line
            and node.col_offset == mutation.index
            and node.value == mutation.value
        ):
            self.applied += 1
            replacement = (
                "__deleted_text_literal__"
                if mutation.kind == "text_membership"
                else r"(?!)"
            )
            return ast.copy_location(ast.Constant(value=replacement), node)
        if (
            mutation.kind == "tool"
            and node.lineno == mutation.line
            and node.col_offset == mutation.index
            and node.value == mutation.value
        ):
            self.applied += 1
            return ast.copy_location(
                ast.Constant(value=f"__deleted_tool_role__{mutation.value}"),
                node,
            )
        if (
            (
                mutation.kind in {"string_constant", "helper_string"}
                or (
                    mutation.kind in {"tool_role", "signal_role"}
                    and mutation.scope not in _CANDIDATE_ROLE_CALLS
                )
            )
            and node.lineno == mutation.line
            and node.col_offset == mutation.index
            and node.value == mutation.value
        ):
            self.applied += 1
            return ast.copy_location(
                ast.Constant(value=""),
                node,
            )
        return node

    def visit_Assign(self, node: ast.Assign) -> Any:  # noqa: N802 - ast API
        mutation = self.mutation
        if (
            mutation.kind == "text_normalization"
            and node.lineno == mutation.line
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "text"
            and mutation.value == "casefold"
        ):
            node.value = ast.parse("user_request.casefold()", mode="eval").body
            self.applied += 1
            return node
        if (
            mutation.kind == "tool_normalization"
            and node.lineno == mutation.line
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "tools"
            and mutation.value
            in {
                "lower_each",
                "strip_each",
                "hyphen_to_underscore",
                "space_to_underscore",
                "remove_underscores",
            }
        ):
            source = {
                "lower_each": "set(tool.lower() for tool in available_tools)",
                "strip_each": "set(tool.strip() for tool in available_tools)",
                "hyphen_to_underscore": (
                    'set(tool.replace("-", "_") for tool in available_tools)'
                ),
                "space_to_underscore": (
                    'set(tool.replace(" ", "_") for tool in available_tools)'
                ),
                "remove_underscores": (
                    'set(tool.replace("_", "") for tool in available_tools)'
                ),
            }[mutation.value]
            node.value = ast.parse(source, mode="eval").body
            self.applied += 1
            return node
        if (
            mutation.kind == "shared_crosswire"
            and mutation.scope.startswith("definition:")
            and node.lineno == mutation.line
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == mutation.scope.removeprefix("definition:")
        ):
            replacement = self.shared_expressions.get(mutation.value)
            if replacement is None:
                raise AssertionError(
                    f"unknown candidate shared fact {mutation.value!r}"
                )
            node.value = ast.copy_location(copy.deepcopy(replacement), node.value)
            self.applied += 1
            return node
        if (
            mutation.kind == "shared_definition"
            and node.lineno == mutation.line
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == mutation.scope
            and mutation.value in {"false", "true"}
        ):
            node.value = ast.copy_location(
                ast.Constant(value=mutation.value == "true"), node.value
            )
            self.applied += 1
            return node
        self.generic_visit(node)
        return node

    def visit_Return(self, node: ast.Return) -> Any:  # noqa: N802 - ast API
        mutation = self.mutation
        if (
            mutation.kind == "return_shape"
            and node.lineno == mutation.line
            and node.col_offset == mutation.index
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "tuple"
            and mutation.value == "list"
        ):
            node.value.func.id = "list"
            self.applied += 1
            return node
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:  # noqa: N802 - ast API
        mutation = self.mutation
        if mutation.kind == "evaluation_order" and node.name == "_visible_task_signals":
            if mutation.scope == "has_signal_call":
                self.generic_visit(node)
                if self.snapshot_call is None:
                    raise AssertionError(
                        f"candidate has_signal snapshot target is missing: {mutation.key}"
                    )
                insert_at = next(
                    index + 1
                    for index, statement in enumerate(node.body)
                    if isinstance(statement, ast.FunctionDef)
                    and statement.name == "has_signal"
                )
                snapshot = ast.Assign(
                    targets=[
                        ast.Name(id="_early_has_signal_snapshot", ctx=ast.Store())
                    ],
                    value=self.snapshot_call,
                )
                node.body.insert(
                    insert_at,
                    ast.copy_location(snapshot, node.body[insert_at]),
                )
                return node

            def add_label(statement: ast.stmt) -> str | None:
                if not (
                    isinstance(statement, ast.Expr)
                    and isinstance(statement.value, ast.Call)
                    and isinstance(statement.value.func, ast.Name)
                    and statement.value.func.id == "add"
                    and statement.value.args
                    and isinstance(statement.value.args[0], ast.Constant)
                    and isinstance(statement.value.args[0].value, str)
                ):
                    return None
                return statement.value.args[0].value

            if mutation.scope == "counterparty_before_recency":
                source_index = next(
                    index
                    for index, statement in enumerate(node.body)
                    if add_label(statement) == "message_counterparty_lookup"
                )
                target_index = next(
                    index
                    for index, statement in enumerate(node.body)
                    if add_label(statement) == "message_recency"
                )
            elif mutation.scope == "holiday_before_state_dependency":
                source_index = next(
                    index
                    for index, statement in enumerate(node.body)
                    if add_label(statement) == "holiday"
                )
                target_index = next(
                    index
                    for index, statement in enumerate(node.body)
                    if isinstance(statement, ast.Assign)
                    and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name)
                    and statement.targets[0].id == "visible_stateful_dependency"
                )
            else:
                raise AssertionError(
                    f"unknown evaluation-order mutation: {mutation.key}"
                )
            statement = node.body.pop(source_index)
            if source_index < target_index:
                target_index -= 1
            node.body.insert(target_index, statement)
            self.applied += 1
            return node
        if (
            mutation.kind == "local_helper"
            and mutation.scope == "has_signal"
            and mutation.value == "eager_snapshot"
            and node.name == "_visible_task_signals"
        ):
            self.generic_visit(node)
            insert_at = next(
                index + 1
                for index, statement in enumerate(node.body)
                if (
                    isinstance(statement, ast.AnnAssign)
                    and isinstance(statement.target, ast.Name)
                    and statement.target.id == "signals"
                )
                or (
                    isinstance(statement, ast.Assign)
                    and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name)
                    and statement.targets[0].id == "signals"
                )
            )
            snapshot = ast.Assign(
                targets=[ast.Name(id="_eager_signal_snapshot", ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id="tuple", ctx=ast.Load()),
                    args=[ast.Name(id="signals", ctx=ast.Load())],
                    keywords=[],
                ),
            )
            node.body.insert(
                insert_at, ast.copy_location(snapshot, node.body[insert_at])
            )
            return node
        if (
            mutation.kind == "local_helper"
            and node.lineno == mutation.line
            and node.name == mutation.scope
        ):
            if node.name == "add":
                replacements = {
                    "omit": "return None",
                    "ignore_condition": (
                        "if signal not in signals:\n    signals.append(signal)"
                    ),
                    "allow_duplicates": ("if condition:\n    signals.append(signal)"),
                    "prepend": (
                        "if condition and signal not in signals:\n"
                        "    signals.insert(0, signal)"
                    ),
                }
                if mutation.value not in replacements:
                    raise AssertionError(f"unknown add-helper mutation: {mutation.key}")
                node.body = ast.parse(replacements[mutation.value]).body
                self.applied += 1
                return node
            direct_expressions = {
                ("has_text", "negated"): "not _has_any(text, phrases)",
                ("has_text", "raw_request"): "_has_any(user_request, phrases)",
                ("has_text", "casefold_text"): "_has_any(text.casefold(), phrases)",
                ("has_tool", "remove_not"): "tools.isdisjoint(names)",
                ("has_tool", "read_signals"): ("not set(signals).isdisjoint(names)"),
                ("has_tool", "lower_available"): (
                    "not {tool.lower() for tool in tools}.isdisjoint(names)"
                ),
                ("has_tool", "strip_available"): (
                    "not {tool.strip() for tool in tools}.isdisjoint(names)"
                ),
                ("has_tool", "available_substring"): (
                    "any(tool in name for tool in tools for name in names)"
                ),
                ("has_tool", "available_prefix"): (
                    "any(name.startswith(tool) for tool in tools for name in names)"
                ),
                ("has_tool", "available_suffix"): (
                    "any(name.endswith(tool) for tool in tools for name in names)"
                ),
                ("has_tool", "requested_substring"): (
                    "any(name in tool for tool in tools for name in names)"
                ),
                ("has_tool", "requested_prefix"): (
                    "any(tool.startswith(name) for tool in tools for name in names)"
                ),
                ("has_tool", "requested_suffix"): (
                    "any(tool.endswith(name) for tool in tools for name in names)"
                ),
                ("has_tool", "hyphen_to_underscore"): (
                    'not {tool.replace("-", "_") for tool in tools}.isdisjoint(names)'
                ),
                ("has_tool", "space_to_underscore"): (
                    'not {tool.replace(" ", "_") for tool in tools}.isdisjoint(names)'
                ),
                ("has_tool", "remove_underscores"): (
                    'not {tool.replace("_", "") for tool in tools}.isdisjoint('
                    'name.replace("_", "") for name in names)'
                ),
                ("has_tool", "identity_membership"): (
                    "any(tool is name for tool in tools for name in names)"
                ),
                ("has_signal", "not_in"): (
                    "any(name not in signals for name in names)"
                ),
                ("has_signal", "read_tools"): ("any(name in tools for name in names)"),
            }
            direct_source = direct_expressions.get((node.name, mutation.value))
            if direct_source is not None:
                expression = ast.parse(direct_source, mode="eval").body
                node.body = [ast.Return(value=expression)]
                self.applied += 1
                return node
            if mutation.value in {
                "first_requested",
                "first_available",
                "first_emitted",
            }:
                expressions = {
                    ("has_text", "first_requested"): (
                        "bool(phrases) and phrases[0] in text"
                    ),
                    ("has_tool", "first_requested"): (
                        "bool(names) and names[0] in tools"
                    ),
                    ("has_tool", "first_available"): (
                        "bool(tools) and sorted(tools)[0] in names"
                    ),
                    ("has_signal", "first_requested"): (
                        "bool(names) and names[0] in signals"
                    ),
                    ("has_signal", "first_emitted"): (
                        "bool(signals) and signals[0] in names"
                    ),
                }
                source = expressions.get((node.name, mutation.value))
                if source is None:
                    raise AssertionError(
                        f"invalid first-only helper mutation: {mutation.key}"
                    )
                expression = ast.parse(source, mode="eval").body
                node.body = [ast.Return(value=expression)]
                self.applied += 1
                return node
            if mutation.value == "false":
                expression: ast.expr = ast.Constant(value=False)
            elif mutation.value == "true":
                expression = ast.Constant(value=True)
            elif mutation.value in {"all", "eager_snapshot"}:
                item_name, collection_name = {
                    "has_text": ("phrase", "phrases"),
                    "has_tool": ("name", "names"),
                    "has_signal": ("name", "names"),
                }[node.name]
                container_name = {
                    "has_text": "text",
                    "has_tool": "tools",
                    "has_signal": "signals",
                }[node.name]
                aggregate_name = "all"
                if mutation.value == "eager_snapshot":
                    if node.name != "has_signal":
                        raise AssertionError(
                            f"snapshot mutation is invalid for {node.name}"
                        )
                    container_name = "_eager_signal_snapshot"
                    aggregate_name = "any"
                expression = ast.Call(
                    func=ast.Name(id=aggregate_name, ctx=ast.Load()),
                    args=[
                        ast.GeneratorExp(
                            elt=ast.Compare(
                                left=ast.Name(id=item_name, ctx=ast.Load()),
                                ops=[ast.In()],
                                comparators=[
                                    ast.Name(id=container_name, ctx=ast.Load())
                                ],
                            ),
                            generators=[
                                ast.comprehension(
                                    target=ast.Name(id=item_name, ctx=ast.Store()),
                                    iter=ast.Name(id=collection_name, ctx=ast.Load()),
                                    ifs=[],
                                    is_async=0,
                                )
                            ],
                        )
                    ],
                    keywords=[],
                )
            else:
                raise AssertionError(f"unknown local-helper mutation: {mutation.key}")
            node.body = [ast.Return(value=ast.copy_location(expression, node))]
            self.applied += 1
            return node
        self.generic_visit(node)
        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:  # noqa: N802 - ast API
        self.generic_visit(node)
        mutation = self.mutation
        if (
            mutation.kind != "boolean_operand"
            or node.lineno != mutation.line
            or type(node.op).__name__ != mutation.value
            or not 0 <= mutation.index < len(node.values)
        ):
            return node
        values = [
            value for index, value in enumerate(node.values) if index != mutation.index
        ]
        self.applied += 1
        if len(values) == 1:
            return ast.copy_location(values[0], node)
        return ast.copy_location(ast.BoolOp(op=node.op, values=values), node)


def compile_family_mutant(mutation: Mutation) -> contracts.FamilyFunction:
    if (
        mutation.kind != "family_semantics"
        or mutation.scope != "_visible_primary_family"
        or mutation.value != "identity_membership"
    ):
        raise ValueError(f"unknown primary-family mutation: {mutation.key}")
    classifier, _source, _tree = _production_context()
    family_tree = ast.parse(inspect.getsource(classifier._visible_primary_family))

    class _FamilyMutator(ast.NodeTransformer):
        def __init__(self) -> None:
            self.applied = 0

        def visit_Compare(self, node: ast.Compare) -> Any:  # noqa: N802 - ast API
            self.generic_visit(node)
            if (
                node.lineno == mutation.line
                and node.col_offset == mutation.index
                and len(node.ops) == 1
                and isinstance(node.ops[0], ast.In)
                and isinstance(node.left, ast.Name)
                and node.left.id == "signal"
                and len(node.comparators) == 1
                and isinstance(node.comparators[0], ast.Name)
                and node.comparators[0].id == "signals"
            ):
                self.applied += 1
                return ast.copy_location(
                    ast.parse(
                        "any(item is signal for item in signals)",
                        mode="eval",
                    ).body,
                    node,
                )
            return node

    mutator = _FamilyMutator()
    family_tree = mutator.visit(family_tree)
    ast.fix_missing_locations(family_tree)
    if mutator.applied != 1:
        raise AssertionError(
            f"mutation {mutation.key} applied {mutator.applied} times instead of once"
        )
    namespace = dict(vars(classifier))
    exec(compile(family_tree, "<visible-family-mutant>", "exec"), namespace)
    return namespace["_visible_primary_family"]


def compile_mutant(mutation: Mutation) -> contracts.SignalFunction:
    classifier, _source, tree = _production_context()
    if mutation.kind in {"helper_string", "temporal_prefix"}:
        namespace = dict(vars(classifier))
        applied = 0
        if mutation.kind == "temporal_prefix":
            name, segment = _TEMPORAL_PREFIX_SEGMENTS[mutation.index]
            if name != mutation.value:
                raise AssertionError(f"temporal mutation changed: {mutation.key}")
            pattern = classifier._TEMPORAL_LOCATION_PREFIX_RE.pattern
            if pattern.count(segment) != 1:
                raise AssertionError(
                    f"temporal segment {name!r} occurs {pattern.count(segment)} times"
                )
            namespace["_TEMPORAL_LOCATION_PREFIX_RE"] = re.compile(
                pattern.replace(segment, ""),
                classifier._TEMPORAL_LOCATION_PREFIX_RE.flags,
            )
            applied = 1
        for helper_name in _HELPER_FUNCTIONS:
            helper_tree = ast.parse(inspect.getsource(getattr(classifier, helper_name)))
            if mutation.kind == "helper_string" and helper_name == mutation.scope:
                mutator = _Mutator(mutation)
                helper_tree = mutator.visit(helper_tree)
                applied += mutator.applied
            ast.fix_missing_locations(helper_tree)
            exec(
                compile(helper_tree, "<visible-signal-helper-string-mutant>", "exec"),
                namespace,
            )
        if applied != 1:
            raise AssertionError(
                f"mutation {mutation.key} applied {applied} times instead of once"
            )
        exec(compile(tree, "<visible-signal-mutant>", "exec"), namespace)
        return namespace["_visible_task_signals"]
    function = tree.body[0]
    shared_expressions = (
        _candidate_shared_expressions(function)
        if current_profile() == CANDIDATE_PROFILE
        and isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef))
        else {}
    )
    mutator = _Mutator(mutation, shared_expressions)
    mutated_tree = mutator.visit(copy.deepcopy(tree))
    ast.fix_missing_locations(mutated_tree)
    if mutator.applied != 1:
        raise AssertionError(
            f"mutation {mutation.key} applied {mutator.applied} times instead of once"
        )
    namespace = dict(vars(classifier))
    exec(compile(mutated_tree, "<visible-signal-mutant>", "exec"), namespace)
    return namespace["_visible_task_signals"]


class _NamedMutator(ast.NodeTransformer):
    def __init__(self, name: str) -> None:
        self.name = name
        self.applied = 0

    def visit_Assign(self, node: ast.Assign) -> Any:  # noqa: N802 - ast API
        self.generic_visit(node)
        target_names = {
            target.id for target in node.targets if isinstance(target, ast.Name)
        }
        if self.name == "absolute_date_false" and target_names == {
            "has_absolute_date_signal"
        }:
            node.value = ast.copy_location(ast.Constant(value=False), node.value)
            self.applied += 1
        elif self.name == "drop_natural_text_regex" and target_names == {
            "explicit_send_message_intent"
        }:
            value = node.value
            if not (
                isinstance(value, ast.BoolOp)
                and isinstance(value.op, ast.And)
                and isinstance(value.values[-1], ast.BoolOp)
                and isinstance(value.values[-1].op, ast.Or)
            ):
                raise AssertionError("send-message expression shape changed")
            value.values[-1] = value.values[-1].values[0]
            self.applied += 1
        return node

    def visit_Compare(self, node: ast.Compare) -> Any:  # noqa: N802 - ast API
        self.generic_visit(node)
        if (
            self.name == "ignore_safe_abstain_precondition"
            and isinstance(node.left, ast.Constant)
            and node.left.value == "safe_abstain_needed"
            and len(node.ops) == 1
            and isinstance(node.ops[0], ast.NotIn)
            and len(node.comparators) == 1
            and isinstance(node.comparators[0], ast.Name)
            and node.comparators[0].id == "signals"
        ):
            self.applied += 1
            return ast.copy_location(ast.Constant(value=True), node)
        return node

    def visit_Constant(self, node: ast.Constant) -> Any:  # noqa: N802 - ast API
        if self.name == "broaden_tell_boundary" and node.value == "tell ":
            self.applied += 1
            return ast.copy_location(ast.Constant(value="tell"), node)
        return node


def compile_named_mutant(name: str) -> contracts.SignalFunction:
    classifier, _source, tree = _production_context()
    mutator = _NamedMutator(name)
    mutated_tree = mutator.visit(copy.deepcopy(tree))
    ast.fix_missing_locations(mutated_tree)
    if mutator.applied != 1:
        raise AssertionError(
            f"named mutation {name} applied {mutator.applied} times instead of once"
        )
    namespace = dict(vars(classifier))
    exec(compile(mutated_tree, "<visible-signal-named-mutant>", "exec"), namespace)
    return namespace["_visible_task_signals"]


def compile_helper_override(name: str) -> contracts.SignalFunction:
    classifier, _source, tree = _production_context()
    namespace = dict(vars(classifier))
    exec(compile(tree, "<visible-signal-helper-mutant>", "exec"), namespace)
    if name == "reverse_geocode_location_leak":
        original = namespace["_visible_location_phrase_requested"]

        def mutated_location(text: str) -> bool:
            if "latitude" in text and "longitude" in text:
                return True
            return original(text)

        namespace["_visible_location_phrase_requested"] = mutated_location
    elif name == "reject_parenthesized_phone":
        original_phone = namespace["_has_phone_like_value"]

        def mutated_phone(text: str) -> bool:
            if "(" in text or ")" in text:
                return False
            return original_phone(text)

        namespace["_has_phone_like_value"] = mutated_phone
    elif name == "reject_dotted_phone":
        original_phone = namespace["_has_phone_like_value"]

        def mutated_phone(text: str) -> bool:
            if "." in text:
                return False
            return original_phone(text)

        namespace["_has_phone_like_value"] = mutated_phone
    elif name == "allow_alphanumeric_phone":
        original_phone = namespace["_has_phone_like_value"]

        def mutated_phone(text: str) -> bool:
            if re.search(r"[a-z]+\d{7,15}(?!\d)", text, flags=re.IGNORECASE):
                return True
            return original_phone(text)

        namespace["_has_phone_like_value"] = mutated_phone
    elif name == "allow_temporal_at_location":
        original_location = namespace["_visible_location_phrase_requested"]

        def mutated_location(text: str) -> bool:
            if "at 9 pm" in text:
                return True
            return original_location(text)

        namespace["_visible_location_phrase_requested"] = mutated_location
    elif name == "allow_weather_stopword_location":
        original_location = namespace["_visible_location_phrase_requested"]

        def mutated_location(text: str) -> bool:
            if text.strip().lower() == "weather today":
                return True
            return original_location(text)

        namespace["_visible_location_phrase_requested"] = mutated_location
    elif name == "reject_bare_city_weather":
        original_location = namespace["_visible_location_phrase_requested"]

        def mutated_location(text: str) -> bool:
            if text.strip().lower() == "weather paris":
                return False
            return original_location(text)

        namespace["_visible_location_phrase_requested"] = mutated_location
    else:
        raise ValueError(f"unknown helper override: {name}")
    return namespace["_visible_task_signals"]


def _flatten_results(value: Any, path: str = "") -> dict[str, tuple[Any, ...]]:
    results: dict[str, tuple[Any, ...]] = {}
    if isinstance(value, dict):
        if "signals" in value and "primary_family" in value:
            results[path or "/"] = (
                tuple(value["signals"]),
                value["primary_family"],
            )
            return results
        for key, item in value.items():
            if key in {
                "target_in_positive",
                "target_in_negative",
                "immutable_inputs_equal_after_call",
            }:
                continue
            results.update(_flatten_results(item, f"{path}/{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            label = item.get("case_id", index) if isinstance(item, dict) else index
            results.update(_flatten_results(item, f"{path}/{label}"))
    return results


_CANDIDATE_REFACTOR_CALLS = (
    (
        "id_update_recency_suppresses_location",
        contracts._Call(
            "update id abcdef latest near Paris",
            ("modify_contact", "search_lat_lon"),
        ),
    ),
    (
        "counterparty_core_not_contact_recency_core",
        contracts._Call(
            "update who sent",
            ("search_messages", "modify_contact"),
        ),
    ),
    (
        "external_contact_role_not_singular_role",
        contracts._Call(
            "update all contact",
            ("search_contacts", "modify_contact"),
        ),
    ),
    (
        "tool_lookup_is_not_first_only",
        contracts._Call(
            "find address",
            ("unknown_native_tool", "search_lat_lon"),
        ),
    ),
    (
        "signal_lookup_is_not_first_only",
        contracts._Call("555-0123 latest message", ("search_messages",)),
    ),
    (
        "uppercase_tool_name_is_not_native",
        contracts._Call("add contact Alice", ("ADD_CONTACT",)),
    ),
    (
        "leading_space_tool_name_is_not_native",
        contracts._Call("latest message", (" search_messages",)),
    ),
    (
        "trailing_space_tool_name_is_not_native",
        contracts._Call("latest message", ("search_messages ",)),
    ),
    (
        "truncated_tool_name_is_not_native",
        contracts._Call("latest message", ("search_message",)),
    ),
    (
        "leading_truncated_tool_name_is_not_native",
        contracts._Call("latest message", ("earch_messages",)),
    ),
    (
        "interior_tool_name_is_not_native",
        contracts._Call("latest message", ("arch_messag",)),
    ),
    (
        "leading_overlong_tool_name_is_not_native",
        contracts._Call("latest message", ("prefix_search_messages",)),
    ),
    (
        "hyphenated_tool_name_is_not_native",
        contracts._Call("latest message", ("search-messages",)),
    ),
    (
        "spaced_tool_name_is_not_native",
        contracts._Call("latest message", ("search messages",)),
    ),
    (
        "underscore_deleted_tool_name_is_not_native",
        contracts._Call("latest message", ("searchmessages",)),
    ),
    (
        "unicode_long_s_is_not_ascii_send",
        contracts._Call("ſend 555-0123", ("send_message_with_phone_number",)),
    ),
    (
        "contact_workflow_does_not_treat_safe_abstain_as_remove",
        contracts._Call(
            "send Alice near Paris",
            ("send_message_with_phone_number", "search_lat_lon"),
        ),
    ),
    (
        "contact_workflow_does_not_treat_relative_time_as_relationship_batch",
        contracts._Call("tomorrow near Paris", ("search_lat_lon",)),
    ),
    (
        "external_lookup_does_not_treat_contact_lookup_as_contact_workflow",
        contracts._Call(
            "what is phone number",
            ("add_contact", "search_lat_lon"),
        ),
    ),
    (
        "external_lookup_does_not_treat_safe_abstain_as_remove",
        contracts._Call(
            "send Alice what is phone number",
            ("send_message_with_phone_number", "search_lat_lon"),
        ),
    ),
    (
        "recency_action_modify_tool_is_not_search_tool",
        contracts._Call(
            "change latest reminder",
            ("modify_reminder", "search_messages"),
        ),
    ),
    (
        "recency_action_remove_tool_is_not_search_tool",
        contracts._Call(
            "remove latest reminder",
            ("remove_reminder", "search_messages"),
        ),
    ),
    (
        "location_state_dependency_does_not_treat_location_search_as_state_action",
        contracts._Call(
            "find address",
            (
                "search_location_around_lat_lon",
                "set_cellular_service_status",
            ),
        ),
    ),
    (
        "lat_lon_state_dependency_does_not_treat_location_search_as_state_action",
        contracts._Call(
            "find address",
            ("search_lat_lon", "set_cellular_service_status"),
        ),
    ),
    (
        "send_state_dependency_does_not_treat_send_tool_as_state_action",
        contracts._Call(
            "send Alice hello",
            (
                "send_message_with_phone_number",
                "search_contacts",
                "set_cellular_service_status",
            ),
        ),
    ),
    (
        "upcoming_suppression_does_not_treat_missing_time_as_upcoming",
        contracts._Call("latest reminder today", ("search_reminder",)),
    ),
    (
        "upcoming_suppression_does_not_treat_relative_time_as_upcoming",
        contracts._Call(
            "latest reminder today",
            ("search_reminder", "get_current_timestamp"),
        ),
    ),
    (
        "recency_action_requires_current_search_and_reminder_domain",
        contracts._Call(
            "change next reminder",
            ("search_reminder", "modify_reminder", "get_current_timestamp"),
        ),
    ),
    (
        "send_dependency_does_not_treat_contact_action_as_send",
        contracts._Call(
            "add contact 555-0123",
            ("add_contact", "send_message_with_phone_number", "set_wifi_status"),
        ),
    ),
    (
        "send_dependency_does_not_treat_phone_presence_as_send",
        contracts._Call(
            "call 555-0123",
            ("send_message_with_phone_number", "set_wifi_status"),
        ),
    ),
    (
        "send_dependency_does_not_treat_message_domain_as_send",
        contracts._Call(
            "find message",
            (
                "search_messages",
                "send_message_with_phone_number",
                "set_wifi_status",
            ),
        ),
    ),
    (
        "stock_exclusion_does_not_treat_message_update_as_stock",
        contracts._Call(
            "update latest message weather",
            (
                "modify_contact",
                "search_messages",
                "search_weather_around_lat_lon",
            ),
        ),
    ),
    (
        "stock_exclusion_does_not_treat_relationship_batch_as_stock",
        contracts._Call(
            "update all friends weather",
            (
                "modify_contact",
                "search_contacts",
                "search_weather_around_lat_lon",
            ),
        ),
    ),
    (
        "phone_contact_lookup_does_not_treat_remove_request_as_phone",
        contracts._Call("who is +15550123456", ("search_contacts",)),
    ),
    (
        "recency_domain_does_not_treat_direct_contact_action_as_domain",
        contracts._Call(
            "meet at next office and remove id abcdef",
            ("search_location_around_lat_lon", "remove_contact", "search_messages"),
        ),
    ),
    (
        "message_recency_does_not_treat_direct_contact_action_as_message",
        contracts._Call(
            "add contact 555-0123 and next reminder",
            ("add_contact", "search_reminder"),
        ),
    ),
    (
        "recency_domain_does_not_treat_named_send_as_message_domain",
        contracts._Call(
            "tell Alice today",
            (
                "send_message_with_phone_number",
                "search_contacts",
                "search_messages",
            ),
        ),
    ),
    (
        "message_recency_does_not_treat_named_send_as_message_domain",
        contracts._Call(
            "tell Alice next reminder",
            (
                "send_message_with_phone_number",
                "search_contacts",
                "search_reminder",
            ),
        ),
    ),
    (
        "message_recency_does_not_treat_named_send_as_prior_message",
        contracts._Call(
            "tell Alice recent reminder",
            (
                "search_reminder",
                "send_message_with_phone_number",
                "search_contacts",
                "search_messages",
            ),
        ),
    ),
    (
        "external_phone_fallback_does_not_treat_location_as_contact_workflow",
        contracts._Call(
            "For audit zephyr, what is the contact phone number near Paris?",
            ("calculate_lat_lon_distance", "search_location_around_lat_lon"),
        ),
    ),
)


# A compact black-box truth table for the refactor's local signal-dependency
# helpers.  Each seed preserves one upstream signal while activating one of the
# downstream has_signal consumers.  Together they distinguish every live
# all-pair dependency substitution; forward-dead and logically absorbed pairs
# are documented separately as external equivalences.
_CANDIDATE_SIGNAL_CROSSWIRE_SEEDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "find messages from today find Blue Cafe phone number",
        ("search_messages", "search_location_around_lat_lon"),
    ),
    ("update contact latest", ("modify_contact", "search_messages")),
    (
        "modify latest reminder find Blue Cafe phone number",
        (
            "search_reminder",
            "modify_reminder",
            "search_location_around_lat_lon",
        ),
    ),
    ("remove contact latest", ("remove_contact", "search_messages")),
    (
        "send 555-0123 and find Blue Cafe phone number latest",
        (
            "send_message_with_phone_number",
            "search_location_around_lat_lon",
            "search_messages",
        ),
    ),
    (
        "how many days until thanksgiving find Blue Cafe phone number",
        (
            "search_holiday",
            "get_current_timestamp",
            "search_location_around_lat_lon",
        ),
    ),
    (
        "turn on wifi find Blue Cafe phone number",
        ("set_wifi_status", "search_location_around_lat_lon"),
    ),
    (
        "create reminder find Blue Cafe phone number",
        ("add_reminder", "search_location_around_lat_lon"),
    ),
    ("add contact latest", ("add_contact", "search_messages")),
    ("what is contact phone latest", ("search_contacts", "search_messages")),
    ("update id abcdef latest", ("modify_contact", "search_messages")),
    ("call 555-0123 latest", ("search_messages",)),
    ("insufficient information latest", ("search_messages",)),
    (
        "update all friends latest",
        ("modify_contact", "search_contacts", "search_messages"),
    ),
    ("view contact near Paris", ("search_contacts", "search_lat_lon")),
    (
        "update all friends near Paris",
        ("modify_contact", "search_contacts", "search_lat_lon"),
    ),
    ("9 pm latest", ("search_messages",)),
    ("find address latest", ("search_lat_lon", "search_messages")),
    ("tomorrow latest", ("search_messages",)),
    ("monday latest", ("search_messages",)),
    (
        "check wifi status find Blue Cafe phone number",
        ("get_wifi_status", "search_location_around_lat_lon"),
    ),
    ("9 pm find Blue Cafe phone number", ("search_location_around_lat_lon",)),
    (
        "insufficient information find Blue Cafe phone number",
        ("search_location_around_lat_lon",),
    ),
    (
        "near Paris find message which phone number",
        ("search_messages", "search_lat_lon"),
    ),
    (
        "delete reminder find Blue Cafe phone number",
        ("remove_reminder", "search_location_around_lat_lon"),
    ),
    (
        "repair wifi if needed find Blue Cafe phone number",
        ("set_wifi_status", "search_location_around_lat_lon"),
    ),
    (
        "next reminder find Blue Cafe phone number",
        (
            "search_reminder",
            "get_current_timestamp",
            "search_location_around_lat_lon",
        ),
    ),
    ("monday find Blue Cafe phone number", ("search_location_around_lat_lon",)),
    (
        "send 555-0123 and find address latest",
        ("send_message_with_phone_number", "search_lat_lon", "search_messages"),
    ),
    ("create reminder near Paris", ("add_reminder", "search_lat_lon")),
    (
        "remove contact latest reminder",
        ("remove_contact", "search_reminder"),
    ),
    (
        "update who did i talk to near Paris",
        ("search_messages", "modify_contact", "search_lat_lon"),
    ),
    ("create reminder 9 pm latest", ("add_reminder", "search_messages")),
    ("9 pm near Paris", ("search_lat_lon",)),
    ("insufficient information near Paris", ("search_lat_lon",)),
    ("find message near Paris", ("search_messages", "search_lat_lon")),
    (
        "send message to Alice near Paris",
        ("send_message_with_phone_number", "search_contacts", "search_lat_lon"),
    ),
    ("change reminder near Paris", ("modify_reminder", "search_lat_lon")),
    ("delete reminder near Paris", ("remove_reminder", "search_lat_lon")),
    ("monday near Paris", ("search_lat_lon",)),
    ("add contact latest reminder", ("add_contact", "search_reminder")),
    (
        "what is contact phone latest reminder",
        ("search_contacts", "search_reminder"),
    ),
    (
        "update id abcdef latest reminder",
        ("modify_contact", "search_reminder"),
    ),
    (
        "create reminder on 2026-10-03 latest",
        ("add_reminder", "search_messages"),
    ),
    ("insufficient information latest reminder", ("search_reminder",)),
    (
        "next reminder near Paris",
        ("search_reminder", "get_current_timestamp", "search_lat_lon"),
    ),
    ("create reminder latest", ("add_reminder", "search_messages")),
    (
        "update contact latest reminder",
        ("modify_contact", "search_reminder"),
    ),
    (
        "update all friends latest reminder",
        ("modify_contact", "search_contacts", "search_reminder"),
    ),
    ("create reminder Monday latest", ("add_reminder", "search_messages")),
)


# Isolated witnesses for every live replacement of the forward-dead holiday
# read in the state-precondition dependency.  The location case deliberately
# uses the external-phone path so the preceding location arm stays false.
_CANDIDATE_HOLIDAY_CROSSWIRE_SEEDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("add contact", ("add_contact", "search_holiday", "set_wifi_status")),
    ("view contact", ("search_contacts", "search_holiday", "set_wifi_status")),
    (
        "what is contact phone",
        ("search_contacts", "search_holiday", "set_wifi_status"),
    ),
    (
        "update id abcdef",
        ("modify_contact", "search_holiday", "set_wifi_status"),
    ),
    ("turn on wifi", ("set_wifi_status", "search_holiday")),
    (
        "check wifi status",
        ("get_wifi_status", "search_holiday", "set_wifi_status"),
    ),
    ("9 pm", ("search_holiday", "set_wifi_status")),
    ("call 555-0123", ("search_holiday", "set_wifi_status")),
    ("insufficient information", ("search_holiday", "set_wifi_status")),
    (
        "phone number of Blue Cafe",
        (
            "search_location_around_lat_lon",
            "search_holiday",
            "set_wifi_status",
        ),
    ),
    (
        "send latest message to 555-0123",
        (
            "send_message_with_phone_number",
            "search_holiday",
            "set_wifi_status",
        ),
    ),
    ("who sent this", ("search_messages", "search_holiday", "set_wifi_status")),
    (
        "update latest message what is contact phone",
        (
            "search_messages",
            "modify_contact",
            "search_contacts",
            "search_holiday",
            "set_wifi_status",
        ),
    ),
    ("latest message", ("search_messages", "search_holiday", "set_wifi_status")),
    ("find message", ("search_messages", "search_holiday", "set_wifi_status")),
    ("create reminder", ("add_reminder", "search_holiday", "set_wifi_status")),
    (
        "update contact",
        (
            "modify_contact",
            "search_contacts",
            "search_holiday",
            "set_wifi_status",
        ),
    ),
    (
        "latest reminder",
        (
            "search_reminder",
            "get_current_timestamp",
            "search_holiday",
            "set_wifi_status",
        ),
    ),
    (
        "modify latest reminder",
        (
            "search_reminder",
            "modify_reminder",
            "search_holiday",
            "set_wifi_status",
        ),
    ),
    (
        "update all friends",
        (
            "modify_contact",
            "search_contacts",
            "search_holiday",
            "set_wifi_status",
        ),
    ),
    ("tomorrow", ("search_holiday", "set_wifi_status")),
    ("reminder", ("search_reminder", "search_holiday", "set_wifi_status")),
    (
        "change reminder",
        ("modify_reminder", "search_holiday", "set_wifi_status"),
    ),
    (
        "delete reminder",
        ("remove_reminder", "search_holiday", "set_wifi_status"),
    ),
    ("remove contact", ("remove_contact", "search_holiday", "set_wifi_status")),
    (
        "next reminder",
        (
            "search_reminder",
            "get_current_timestamp",
            "search_holiday",
            "set_wifi_status",
        ),
    ),
    ("monday", ("search_holiday", "set_wifi_status")),
)


def _semantic_body_for_profile(
    signal_fn: contracts.SignalFunction,
    family_fn: contracts.FamilyFunction,
    profile: str | None = None,
) -> dict[str, Any]:
    selected = profile or current_profile()
    body = contracts._semantic_body(signal_fn, family_fn)
    if selected == CANDIDATE_PROFILE:
        dynamic_tool = "".join(("search", "_messages"))
        canonical_tool = "search_messages"
        if dynamic_tool != canonical_tool or dynamic_tool is canonical_tool:
            raise AssertionError(
                "candidate exact-tool identity carrier was interned or changed"
            )
        body["candidate_refactor_cases"] = [
            {
                "case_id": case_id,
                "result": contracts._evaluate(signal_fn, family_fn, call),
            }
            for case_id, call in _CANDIDATE_REFACTOR_CALLS
        ]
        body["candidate_signal_crosswire_cases"] = [
            {
                "case_id": f"signal_crosswire_{index:02d}",
                "result": contracts._evaluate(
                    signal_fn,
                    family_fn,
                    contracts._Call(request, tools),
                ),
            }
            for index, (request, tools) in enumerate(
                _CANDIDATE_SIGNAL_CROSSWIRE_SEEDS, start=1
            )
        ]
        body["candidate_holiday_crosswire_cases"] = [
            {
                "case_id": f"holiday_crosswire_{index:02d}",
                "result": contracts._evaluate(
                    signal_fn,
                    family_fn,
                    contracts._Call(request, tools),
                ),
            }
            for index, (request, tools) in enumerate(
                _CANDIDATE_HOLIDAY_CROSSWIRE_SEEDS, start=1
            )
        ]
        body["candidate_dynamic_identity_case"] = contracts._evaluate(
            signal_fn,
            family_fn,
            contracts._Call("latest message", (dynamic_tool,)),
        )
    return body


def audit_mutation(
    mutation: Mutation,
    *,
    baseline_results: dict[str, tuple[Any, ...]] | None = None,
) -> dict[str, Any]:
    _signal_fn, family_fn = contracts._production_functions()
    profile = current_profile()
    if baseline_results is None:
        baseline_results = _flatten_results(
            _semantic_body_for_profile(_signal_fn, family_fn, profile)
        )
    if mutation.kind == "family_semantics":
        mutant_signal_fn = _signal_fn
        mutant_family_fn = compile_family_mutant(mutation)
    else:
        mutant_signal_fn = compile_mutant(mutation)
        mutant_family_fn = family_fn
    try:
        mutant_results = _flatten_results(
            _semantic_body_for_profile(mutant_signal_fn, mutant_family_fn, profile)
        )
    except Exception as exc:  # a crashing semantic mutant is also rejected
        marker = ("exception", type(exc).__name__, str(exc))
        return {
            "mutation": mutation.key,
            "caught": True,
            "changed_paths": ["/__mutation_exception__"],
            "changes": [
                {
                    "carrier_path": "/__mutation_exception__",
                    "baseline": None,
                    "mutant": marker,
                }
            ],
        }
    changed_paths = sorted(
        path
        for path in baseline_results.keys() | mutant_results.keys()
        if baseline_results.get(path) != mutant_results.get(path)
    )
    changes = [
        {
            "carrier_path": path,
            "baseline": baseline_results.get(path),
            "mutant": mutant_results.get(path),
        }
        for path in changed_paths
    ]
    return {
        "mutation": mutation.key,
        "caught": bool(changed_paths),
        "changed_paths": changed_paths,
        "changes": changes,
    }


def run_mutation_audit(kinds: frozenset[MutationKind] | None = None) -> dict[str, Any]:
    profile = current_profile()
    equivalences = (
        EXPECTED_EQUIVALENT_MUTANTS
        if profile == REFERENCE_PROFILE
        else CANDIDATE_EQUIVALENT_MUTANTS
    )
    signal_fn, family_fn = contracts._production_functions()
    baseline_results = _flatten_results(
        _semantic_body_for_profile(signal_fn, family_fn, profile)
    )
    selected = [
        mutation
        for mutation in enumerate_mutations()
        if kinds is None or mutation.kind in kinds
    ]
    rows = [
        audit_mutation(mutation, baseline_results=baseline_results)
        for mutation in selected
    ]
    return {
        "mutation_count": len(rows),
        "caught_count": sum(row["caught"] for row in rows),
        "invisible_count": sum(not row["caught"] for row in rows),
        "expected_equivalent_count": sum(
            row["mutation"] in equivalences for row in rows
        ),
        "unexpected_invisible": [
            row["mutation"]
            for row in rows
            if not row["caught"] and row["mutation"] not in equivalences
        ],
        "unexpected_caught_equivalence": [
            row["mutation"]
            for row in rows
            if row["caught"] and row["mutation"] in equivalences
        ],
        "profile": profile,
        "profile_identity": current_profile_identity(),
        "rows": rows,
    }


def mutation_audit_projection(report: dict[str, Any]) -> dict[str, Any]:
    profile = report.get("profile", current_profile())
    equivalences = (
        EXPECTED_EQUIVALENT_MUTANTS
        if profile == REFERENCE_PROFILE
        else CANDIDATE_EQUIVALENT_MUTANTS
    )
    mutations = enumerate_mutations()
    pairings = tuple(
        (
            row["mutation"],
            row["caught"],
            tuple(row["changed_paths"]),
        )
        for row in report["rows"]
    )
    return {
        "inventory": contracts._digest(tuple(mutation.key for mutation in mutations)),
        "equivalence_groups": contracts._digest(tuple(sorted(equivalences.items()))),
        "carrier_pairings": contracts._digest(pairings),
        "mutation_count": report["mutation_count"],
        "caught_count": report["caught_count"],
        "equivalent_count": report["invisible_count"],
    }


def verify_mutation_audit(report: dict[str, Any]) -> None:
    profile = current_profile()
    if report.get("profile") != profile:
        raise ValueError("visible-signal mutation report profile does not match source")
    if report.get("profile_identity") != PROFILE_IDENTITIES[profile]:
        raise ValueError("visible-signal mutation report source identity changed")
    expected = (
        EXPECTED_MUTATION_AUDIT
        if profile == REFERENCE_PROFILE
        else CANDIDATE_EXPECTED_MUTATION_AUDIT
    )
    projection = mutation_audit_projection(report)
    if not expected:
        raise ValueError(f"visible-signal mutation profile {profile!r} is not frozen")
    if projection != expected:
        raise ValueError(
            "visible-signal mutation audit differs from its frozen inventory: "
            f"expected={expected!r}, actual={projection!r}"
        )
    if report["unexpected_invisible"] or report["unexpected_caught_equivalence"]:
        raise ValueError("visible-signal mutation equivalence classification changed")
    kind_counts = Counter(item.kind for item in enumerate_mutations())
    if dict(kind_counts) != PROFILE_KIND_COUNTS[profile]:
        raise ValueError(
            "visible-signal mutation category inventory changed: "
            f"expected={PROFILE_KIND_COUNTS[profile]!r}, actual={dict(kind_counts)!r}"
        )
    if profile == CANDIDATE_PROFILE:
        shared_rows = [
            row
            for row in report["rows"]
            if row["mutation"].startswith("shared_definition:")
        ]
        helper_rows = [
            row for row in report["rows"] if row["mutation"].startswith("local_helper:")
        ]
        if len(shared_rows) != 86 or not all(row["caught"] for row in shared_rows):
            raise ValueError(
                "a candidate shared fact can be omitted or forced silently"
            )
        shared_use_rows = [
            row for row in report["rows"] if row["mutation"].startswith("shared_use:")
        ]
        if len(shared_use_rows) != 46 or not all(
            row["caught"] for row in shared_use_rows
        ):
            raise ValueError("a candidate shared-fact consumer can change silently")
        if len(helper_rows) != 38 or not all(row["caught"] for row in helper_rows):
            raise ValueError("a candidate local fact helper can change silently")
        crosswire_rows = [
            row
            for row in report["rows"]
            if row["mutation"].startswith("shared_crosswire:")
        ]
        if len(crosswire_rows) != 256 or not all(
            row["caught"]
            for row in crosswire_rows
            if row["mutation"] not in CANDIDATE_EQUIVALENT_MUTANTS
        ):
            raise ValueError("candidate shared facts can be cross-wired silently")
        evaluation_rows = [
            row
            for row in report["rows"]
            if row["mutation"].startswith("evaluation_order:")
        ]
        if len(evaluation_rows) != 8 or not all(
            row["caught"] for row in evaluation_rows
        ):
            raise ValueError("candidate signal evaluation order can change silently")
        boundary_rows = [
            row
            for row in report["rows"]
            if row["mutation"].startswith(
                ("return_shape:", "text_normalization:", "tool_normalization:")
            )
        ]
        if len(boundary_rows) != 7 or not all(row["caught"] for row in boundary_rows):
            raise ValueError(
                "candidate input/output boundary semantics can change silently"
            )
        family_rows = [
            row
            for row in report["rows"]
            if row["mutation"].startswith("family_semantics:")
        ]
        if len(family_rows) != 1 or not family_rows[0]["caught"]:
            raise ValueError(
                "candidate primary-family value semantics changed silently"
            )
        role_crosswire_rows = [
            row
            for row in report["rows"]
            if row["mutation"].startswith("role_crosswire:")
        ]
        if len(role_crosswire_rows) != 7_256 or not all(
            row["caught"]
            for row in role_crosswire_rows
            if row["mutation"] not in CANDIDATE_EQUIVALENT_MUTANTS
        ):
            raise ValueError(
                "candidate local tool/signal dependency roles can be cross-wired silently"
            )
        if not any("eager_snapshot" in row["mutation"] for row in helper_rows):
            raise ValueError("candidate has_signal eager-snapshot mutant is missing")
