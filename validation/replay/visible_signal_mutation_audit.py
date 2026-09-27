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
import inspect
import re
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
]


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
        return f"{self.kind}:{self.line}:{self.index}:{self.value}"


def _production_context() -> tuple[Any, str, ast.Module]:
    classifier = inspect.getmodule(contracts._production_functions()[0])
    if classifier is None:
        raise RuntimeError("could not resolve visible-signal classifier module")
    source = inspect.getsource(classifier._visible_task_signals)
    return classifier, source, ast.parse(source)


def enumerate_mutations() -> tuple[Mutation, ...]:
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


class _Mutator(ast.NodeTransformer):
    def __init__(self, mutation: Mutation) -> None:
        self.mutation = mutation
        self.applied = 0

    def visit_Call(self, node: ast.Call) -> Any:  # noqa: N802 - ast API
        self.generic_visit(node)
        mutation = self.mutation
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

    def _visit_string_sequence(self, node: ast.Tuple | ast.Set) -> Any:
        mutation = self.mutation
        if mutation.kind in {"string_constant", "helper_string"}:
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
            mutation.kind in {"string_constant", "helper_string"}
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
    mutator = _Mutator(mutation)
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


def audit_mutation(
    mutation: Mutation,
    *,
    baseline_results: dict[str, tuple[Any, ...]] | None = None,
) -> dict[str, Any]:
    _signal_fn, family_fn = contracts._production_functions()
    if baseline_results is None:
        baseline_results = _flatten_results(
            contracts._semantic_body(_signal_fn, family_fn)
        )
    mutant = compile_mutant(mutation)
    try:
        mutant_results = _flatten_results(contracts._semantic_body(mutant, family_fn))
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
    signal_fn, family_fn = contracts._production_functions()
    baseline_results = _flatten_results(contracts._semantic_body(signal_fn, family_fn))
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
            row["mutation"] in EXPECTED_EQUIVALENT_MUTANTS for row in rows
        ),
        "unexpected_invisible": [
            row["mutation"]
            for row in rows
            if not row["caught"] and row["mutation"] not in EXPECTED_EQUIVALENT_MUTANTS
        ],
        "unexpected_caught_equivalence": [
            row["mutation"]
            for row in rows
            if row["caught"] and row["mutation"] in EXPECTED_EQUIVALENT_MUTANTS
        ],
        "rows": rows,
    }


def mutation_audit_projection(report: dict[str, Any]) -> dict[str, Any]:
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
        "equivalence_groups": contracts._digest(
            tuple(sorted(EXPECTED_EQUIVALENT_MUTANTS.items()))
        ),
        "carrier_pairings": contracts._digest(pairings),
        "mutation_count": report["mutation_count"],
        "caught_count": report["caught_count"],
        "equivalent_count": report["invisible_count"],
    }


def verify_mutation_audit(report: dict[str, Any]) -> None:
    projection = mutation_audit_projection(report)
    if projection != EXPECTED_MUTATION_AUDIT:
        raise ValueError(
            "visible-signal mutation audit differs from its frozen inventory: "
            f"expected={EXPECTED_MUTATION_AUDIT!r}, actual={projection!r}"
        )
    if report["unexpected_invisible"] or report["unexpected_caught_equivalence"]:
        raise ValueError("visible-signal mutation equivalence classification changed")
