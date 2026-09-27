"""Fail-closed source contracts for actor tool-schema implementations.

The behavioral oracle supports two intentionally different implementations:
the immutable, loop-based reference and the typed ``ToolSchemaFacts`` candidate.
This module identifies either profile from its declarations, freezes the relevant
AST and dependency graph, and applies additional architectural assertions to the
typed profile.  It is validation-only and is never imported by live SAGE.
"""

from __future__ import annotations

import ast
import builtins
from collections.abc import Iterator
import dataclasses
from dataclasses import FrozenInstanceError
import dis
import hashlib
import inspect
import json
import sys
import textwrap
from types import CodeType, FunctionType, ModuleType
import typing
from typing import Any, Iterable, Mapping

try:
    from validation.replay import actor_tool_schema_contracts as behavior
except ModuleNotFoundError:
    behavior = sys.modules.get("_sage_replay_actor_tool_schema_contracts")
    if behavior is None:
        import actor_tool_schema_contracts as behavior


class ActorSchemaSourceContractError(ValueError):
    """The actor schema implementation no longer matches an accepted profile."""


LEGACY_UNITS = (
    "_agent_facing_tool_name",
    "_execution_facing_tool_name",
    "_tool_schema_text",
    "_tool_names",
    "_tool_names_execution_facing",
    "_tool_input_names_execution_facing",
    "_tool_output_names_execution_facing",
    "_tool_description_execution_facing",
    "_tool_name_for_call",
    "_generated_tool_names_execution_facing",
    "_tool_schema_execution_name",
    "_declared_service_answer_producers",
    "_selector_tool_names",
    "_derived_value_tool_names",
    "_lookup_query_planner_tool_names",
    "_search_window_tool_names",
    "_relative_time_tool_names",
    "_scheduling_timestamp_tool_names",
    "_state_action_planner_tool_names",
    "_validation_abstention_tool_names",
    "_action_argument_helper_tool_names",
    "_post_selection_action_helper_tool_names",
)

TYPED_CONSTANTS = (
    "_DERIVED_INPUT_TYPES",
    "_SCHEDULING_INPUTS",
    "_PRIOR_RECORD_INPUTS",
    "_WINDOW_MARKERS",
    "_DERIVED_MARKERS",
    "_LOOKUP_QUERY_MARKERS",
    "_RELATIVE_TIME_MARKERS",
    "_SHARED_ACTION_ARGUMENT_MARKERS",
    "_ACTION_ARGUMENT_MARKERS",
    "_DOWNSTREAM_CALL_MARKERS",
    "_POST_SELECTION_MARKERS",
)

TYPED_UNITS = (
    "_ToolSchemaFacts",
    "_ToolSchemaInventory",
    "_schema_property_names",
    *LEGACY_UNITS[:12],
    "_category_names",
    *LEGACY_UNITS[12:],
)

EXPECTED_AST_SHA256 = {
    "legacy": "7e42ed83cec863309d0e30823f2cb308fd30c26164deeee17987dbd2bd0f7240",
    "typed_v1": "eab7f00c6f289b61dc39c30f9f1e4f6b4115496bfb5b15cc3312a7ed5a85276b",
}
EXPECTED_SOURCE_SHA256 = {
    "legacy": "563c5f39b0372294090c16baf74a97e68b51bffdfd27d9270520e4babed79b82",
    "typed_v1": "209753ed71336830c415efcbaffcfb0782254b256817b5f19d377eba8959f80c",
}

# Filled from the exact call graph of the accepted typed candidate.  This is
# intentionally separate from the aggregate AST digest so dependency drift has
# a direct, comprehensible failure mode.
EXPECTED_TYPED_DEPENDENCY_SHA256 = (
    "d45b713a80abd1cab73591bb497482a40e88a4aadfeffb607da7a152e68ddab8"
)
EXPECTED_LIVE_CODE_SHA256 = {
    "legacy": "cfdb35344260c545d2759ca6af22299b3f02a580184739913eda8bb3a2f70470",
    "typed_v1": "5281fced230de1b3664fd73cea498e965ad10883a395cf1bbbaa5f0b3842a425",
}

TYPED_WRAPPER_METHODS = {
    "_selector_tool_names": "is_selector",
    "_derived_value_tool_names": "is_derived_value",
    "_lookup_query_planner_tool_names": "is_lookup_query_planner",
    "_search_window_tool_names": "is_search_window",
    "_relative_time_tool_names": "is_relative_time",
    "_scheduling_timestamp_tool_names": "is_scheduling_timestamp",
    "_state_action_planner_tool_names": "is_state_action_planner",
    "_validation_abstention_tool_names": "is_validation_abstention",
    "_action_argument_helper_tool_names": "is_action_argument_helper",
    "_post_selection_action_helper_tool_names": ("is_post_selection_action_helper"),
}

TYPED_JOINED_MARKER_CONSTANTS = {
    "category_branches_derived_value": ("_DERIVED_MARKERS",),
    "category_branches_lookup_query_planner": ("_LOOKUP_QUERY_MARKERS",),
    "category_branches_relative_time": ("_RELATIVE_TIME_MARKERS",),
    "category_branches_action_argument_helper": (
        "_ACTION_ARGUMENT_MARKERS",
        "_DOWNSTREAM_CALL_MARKERS",
        "ORIGINAL_SIDE_EFFECT_TOOL_NAMES",
    ),
    "category_branches_post_selection_action_helper": (
        "_POST_SELECTION_MARKERS",
        "ORIGINAL_SIDE_EFFECT_TOOL_NAMES",
    ),
}

TYPED_EXTERNAL_GLOBALS = {
    "Any",
    "Exception",
    "Iterable",
    "Mapping",
    "NOT_GIVEN",
    "TypeError",
    "any",
    "bool",
    "cast",
    "dict",
    "get_current_context",
    "isinstance",
    "json",
    "len",
    "set",
    "sorted",
    "str",
    "tuple",
}
TYPED_INTERNAL_GLOBALS = {
    "ORIGINAL_SIDE_EFFECT_TOOL_NAMES",
    "ORIGINAL_TOOLSANDBOX_TOOL_NAMES",
    "SERVICE_ANSWER_PRODUCER_TOOLS",
    *(set(TYPED_CONSTANTS) - {"_SHARED_ACTION_ARGUMENT_MARKERS"}),
    "_ToolSchemaFacts",
    "_ToolSchemaInventory",
    "_agent_facing_tool_name",
    "_category_names",
    "_execution_facing_tool_name",
    "_schema_property_names",
    "_tool_names",
    "_tool_schema_text",
}
EXPECTED_TYPED_GLOBAL_LOADS = TYPED_EXTERNAL_GLOBALS | TYPED_INTERNAL_GLOBALS

LEGACY_INTERNAL_GLOBALS = {
    "ORIGINAL_SIDE_EFFECT_TOOL_NAMES",
    "ORIGINAL_TOOLSANDBOX_TOOL_NAMES",
    "SERVICE_ANSWER_PRODUCER_TOOLS",
    "_agent_facing_tool_name",
    "_execution_facing_tool_name",
    "_tool_names",
    "_tool_schema_text",
}
EXPECTED_LEGACY_GLOBAL_LOADS = TYPED_EXTERNAL_GLOBALS | LEGACY_INTERNAL_GLOBALS

_DATACLASS_SURFACE = {
    "__module__": "builtins.str",
    "__annotations__": "builtins.dict",
    "__doc__": "builtins.str",
    "__dataclass_params__": "dataclasses._DataclassParams",
    "__dataclass_fields__": "builtins.dict",
    "__init__": "builtins.function",
    "__repr__": "builtins.function",
    "__eq__": "builtins.function",
    "__setattr__": "builtins.function",
    "__delattr__": "builtins.function",
    "__hash__": "builtins.function",
    "__match_args__": "builtins.tuple",
    "__slots__": "builtins.tuple",
    "__getstate__": "builtins.function",
    "__setstate__": "builtins.function",
}
EXPECTED_TYPED_CLASS_SURFACES = {
    "_ToolSchemaFacts": {
        **_DATACLASS_SURFACE,
        "from_tool": "builtins.classmethod",
        "marker_text": "builtins.property",
        "description_has": "builtins.function",
        "marker_has": "builtins.function",
        "has_inputs": "builtins.function",
        "has_any_input": "builtins.function",
        "is_selector": "builtins.function",
        "is_derived_value": "builtins.function",
        "is_lookup_query_planner": "builtins.function",
        "is_search_window": "builtins.function",
        "is_scheduling_timestamp": "builtins.function",
        "is_state_action_planner": "builtins.function",
        "is_validation_abstention": "builtins.function",
        "is_relative_time": "builtins.function",
        "is_action_argument_helper": "builtins.function",
        "is_post_selection_action_helper": "builtins.function",
        "description": "builtins.member_descriptor",
        "function": "builtins.member_descriptor",
        "input_names": "builtins.member_descriptor",
        "name": "builtins.member_descriptor",
        "properties": "builtins.member_descriptor",
    },
    "_ToolSchemaInventory": {
        **_DATACLASS_SURFACE,
        "tools": "builtins.function",
        "raw_names": "builtins.function",
        "find": "builtins.function",
        "source": "builtins.member_descriptor",
    },
}


def _fail(message: str) -> None:
    raise ActorSchemaSourceContractError(message)


def _require(condition: bool, message: str) -> None:
    if not condition:
        _fail(message)


def _named_nodes(tree: ast.Module) -> dict[str, ast.AST]:
    nodes: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            nodes[node.name] = node
            continue
        if isinstance(node, ast.Assign):
            targets: Iterable[ast.expr] = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = (node.target,)
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                nodes[target.id] = node
    return nodes


def _digest_nodes(nodes: Mapping[str, ast.AST], names: Iterable[str]) -> str:
    try:
        bodies = [ast.dump(nodes[name], include_attributes=False) for name in names]
    except KeyError as error:
        _fail(f"missing source-contract declaration: {error.args[0]}")
    return hashlib.sha256("\n".join(bodies).encode()).hexdigest()


def _digest_source(
    source: str, nodes: Mapping[str, ast.AST], names: Iterable[str]
) -> str:
    try:
        segments = [ast.get_source_segment(source, nodes[name]) for name in names]
    except KeyError as error:
        _fail(f"missing source-contract declaration: {error.args[0]}")
    _require(all(segment is not None for segment in segments), "missing source segment")
    return hashlib.sha256("\n".join(segments).encode()).hexdigest()  # type: ignore[arg-type]


def _call_name(call: ast.Call) -> str:
    function = call.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        parts = [function.attr]
        value = function.value
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name):
            parts.append(value.id)
        return ".".join(reversed(parts))
    return type(function).__name__


def _dependency_projection(
    nodes: Mapping[str, ast.AST], names: Iterable[str]
) -> dict[str, tuple[str, ...]]:
    return {
        name: tuple(
            sorted(
                {
                    _call_name(call)
                    for call in ast.walk(nodes[name])
                    if isinstance(call, ast.Call)
                }
            )
        )
        for name in names
    }


def _dependency_digest(projection: Mapping[str, tuple[str, ...]]) -> str:
    body = "\n".join(f"{name}:{','.join(calls)}" for name, calls in projection.items())
    return hashlib.sha256(body.encode()).hexdigest()


def _is_name_description_join(node: ast.AST) -> bool:
    if not isinstance(node, ast.JoinedStr) or len(node.values) != 3:
        return False
    first, separator, second = node.values
    return (
        isinstance(first, ast.FormattedValue)
        and isinstance(first.value, ast.Name)
        and first.value.id == "name"
        and isinstance(separator, ast.Constant)
        and separator.value == " "
        and isinstance(second, ast.FormattedValue)
        and isinstance(second.value, ast.Name)
        and second.value.id == "description"
    )


def _legacy_joined_markers(node: ast.AST) -> tuple[str, ...]:
    join_variables = {
        target.id
        for assignment in ast.walk(node)
        if isinstance(assignment, ast.Assign)
        and _is_name_description_join(assignment.value)
        for target in assignment.targets
        if isinstance(target, ast.Name)
    }
    generators = sorted(
        (item for item in ast.walk(node) if isinstance(item, ast.GeneratorExp)),
        key=lambda item: (item.lineno, item.col_offset),
    )
    markers: list[str] = []
    for generator in generators:
        comparison = generator.elt
        if not isinstance(comparison, ast.Compare) or len(comparison.comparators) != 1:
            continue
        compared_text = comparison.comparators[0]
        reads_join = _is_name_description_join(compared_text) or (
            isinstance(compared_text, ast.Name) and compared_text.id in join_variables
        )
        if not reads_join or len(generator.generators) != 1:
            continue
        iterable = generator.generators[0].iter
        if isinstance(iterable, (ast.Tuple, ast.List, ast.Set)):
            markers.extend(
                element.value
                for element in iterable.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            )
        elif (
            isinstance(iterable, ast.Name)
            and iterable.id == "ORIGINAL_SIDE_EFFECT_TOOL_NAMES"
        ):
            markers.extend(behavior.EXPECTED_ORIGINAL_SIDE_EFFECT_TOOL_NAMES)
    return tuple(markers)


def _legacy_marker_inventory(
    nodes: Mapping[str, ast.AST],
) -> dict[str, tuple[str, ...]]:
    inventory: dict[str, tuple[str, ...]] = {}
    for case_id in behavior.CATEGORY_BRANCH_CASE_IDS:
        operation = behavior.FIELD_NORMALIZATION_PLANS[case_id]["operation"]
        markers = _legacy_joined_markers(nodes[operation])
        if markers:
            inventory[case_id] = markers
    return inventory


def _typed_marker_inventory(actor: ModuleType) -> dict[str, frozenset[str]]:
    inventory: dict[str, frozenset[str]] = {}
    for case_id, constant_names in TYPED_JOINED_MARKER_CONSTANTS.items():
        markers: list[str] = []
        for constant_name in constant_names:
            value = getattr(actor, constant_name, None)
            _require(
                isinstance(value, (tuple, frozenset, set)),
                f"typed joined marker constant changed shape: {constant_name}",
            )
            markers.extend(value)
        inventory[case_id] = frozenset(markers)
    return inventory


def _function(nodes: Mapping[str, ast.AST], name: str) -> ast.FunctionDef:
    node = nodes.get(name)
    _require(isinstance(node, ast.FunctionDef), f"missing function: {name}")
    return node


def _class_method(class_node: ast.ClassDef, name: str) -> ast.FunctionDef:
    method = next(
        (
            node
            for node in class_node.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        ),
        None,
    )
    _require(isinstance(method, ast.FunctionDef), f"missing typed method: {name}")
    return method


def _assert_typed_wrappers(nodes: Mapping[str, ast.AST]) -> None:
    for wrapper_name, method_name in TYPED_WRAPPER_METHODS.items():
        wrapper = _function(nodes, wrapper_name)
        _require(
            len(wrapper.body) == 1 and isinstance(wrapper.body[0], ast.Return),
            f"typed compatibility wrapper grew behavior: {wrapper_name}",
        )
        call = wrapper.body[0].value
        valid_call = (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "_category_names"
            and len(call.args) == 2
            and isinstance(call.args[0], ast.Name)
            and call.args[0].id == "openai_tools"
            and isinstance(call.args[1], ast.Attribute)
            and isinstance(call.args[1].value, ast.Name)
            and call.args[1].value.id == "_ToolSchemaFacts"
            and call.args[1].attr == method_name
            and not call.keywords
        )
        _require(valid_call, f"typed compatibility delegation changed: {wrapper_name}")


def _assert_no_typed_rebindings(tree: ast.Module) -> None:
    protected_classes = {"_ToolSchemaFacts", "_ToolSchemaInventory"}
    protected_imports = TYPED_EXTERNAL_GLOBALS | {"list"}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and (
            node.name in protected_imports
        ):
            _fail(f"typed dependency rebound after import: {node.name}")
        targets: Iterable[ast.expr]
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = (node.target,)
        else:
            targets = ()
        for target in targets:
            if isinstance(target, ast.Attribute) and target.attr == "__code__":
                _fail("typed protected code object reassigned")
            if isinstance(target, ast.Name) and target.id in protected_imports:
                _fail(f"typed dependency rebound after import: {target.id}")
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id in protected_classes
            ):
                _fail(
                    "typed schema method rebound after declaration: "
                    f"{target.value.id}.{target.attr}"
                )
        for call in (item for item in ast.walk(node) if isinstance(item, ast.Call)):
            direct_mutator = (
                isinstance(call.func, ast.Name)
                and call.func.id in {"setattr", "delattr"}
            ) or (
                isinstance(call.func, ast.Attribute)
                and call.func.attr in {"__setattr__", "__delattr__"}
            )
            if (
                direct_mutator
                and call.args
                and isinstance(call.args[0], ast.Name)
                and call.args[0].id in protected_classes
            ):
                _fail(f"typed schema class mutated by call: {call.args[0].id}")
        if isinstance(
            node, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)
        ):
            continue
        for call in (item for item in ast.walk(node) if isinstance(item, ast.Call)):
            if any(
                isinstance(item, ast.Name) and item.id in protected_classes
                for argument in call.args
                for item in ast.walk(argument)
            ):
                _fail("top-level call received a protected typed schema class")


def _code_constant_projection(value: object) -> object:
    if isinstance(value, CodeType):
        return {"code": _code_projection(value)}
    if isinstance(value, tuple):
        return {"tuple": [_code_constant_projection(item) for item in value]}
    if isinstance(value, frozenset):
        items = [_code_constant_projection(item) for item in value]
        return {"frozenset": sorted(items, key=lambda item: repr(item))}
    if isinstance(value, bytes):
        return {"bytes": value.hex()}
    if value is None or isinstance(value, (bool, int, float, str)):
        return {type(value).__name__: value}
    return {"repr": f"{type(value).__module__}.{type(value).__qualname__}:{value!r}"}


def _code_projection(code: CodeType) -> dict[str, object]:
    return {
        "argcount": code.co_argcount,
        "posonlyargcount": code.co_posonlyargcount,
        "kwonlyargcount": code.co_kwonlyargcount,
        "nlocals": code.co_nlocals,
        "stacksize": code.co_stacksize,
        "flags": code.co_flags,
        "code": code.co_code.hex(),
        "consts": [_code_constant_projection(value) for value in code.co_consts],
        "names": list(code.co_names),
        "varnames": list(code.co_varnames),
        "freevars": list(code.co_freevars),
        "cellvars": list(code.co_cellvars),
        "name": code.co_name,
        "qualname": code.co_qualname,
        "exceptiontable": code.co_exceptiontable.hex(),
    }


def _live_code_digest(
    actor: ModuleType,
    nodes: Mapping[str, ast.AST],
    units: Iterable[str],
    *,
    include_typed_methods: bool,
) -> str:
    functions: dict[str, object] = {
        name: getattr(actor, name)
        for name in units
        if isinstance(nodes[name], ast.FunctionDef)
    }
    if include_typed_methods:
        for class_name in ("_ToolSchemaFacts", "_ToolSchemaInventory"):
            live_class = getattr(actor, class_name)
            for method_name, descriptor in vars(live_class).items():
                if isinstance(descriptor, (classmethod, staticmethod)):
                    function = descriptor.__func__
                elif isinstance(descriptor, property):
                    function = descriptor.fget
                elif inspect.isfunction(descriptor):
                    function = descriptor
                else:
                    continue
                functions[f"{class_name}.{method_name}"] = function
    projection = {
        name: _function_runtime_projection(actor, function)
        for name, function in functions.items()
    }
    return hashlib.sha256(
        json.dumps(projection, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _globals_owner(actor: ModuleType, globals_dict: object) -> str:
    if globals_dict is actor.__dict__:
        return "actor"
    if globals_dict is dataclasses.__dict__:
        return "dataclasses"
    return "other"


def _closure_value_projection(actor: ModuleType, value: object) -> object:
    if inspect.isfunction(value):
        return {"function": _function_runtime_projection(actor, value)}
    if isinstance(value, type):
        identity = (
            "facts"
            if value is getattr(actor, "_ToolSchemaFacts", None)
            else "inventory"
            if value is getattr(actor, "_ToolSchemaInventory", None)
            else "builtins.object"
            if value is builtins.object
            else "dataclasses.FrozenInstanceError"
            if value is FrozenInstanceError
            else "noncanonical"
        )
        return {
            "type": f"{value.__module__}.{value.__qualname__}",
            "identity": identity,
        }
    if isinstance(value, set):
        return {
            "set": sorted(
                (_code_constant_projection(item) for item in value),
                key=repr,
            )
        }
    return _code_constant_projection(value)


def _function_runtime_projection(
    actor: ModuleType,
    function: object,
) -> dict[str, object]:
    closure = function.__closure__ or ()
    return {
        "code": _code_projection(function.__code__),
        "defaults": _code_constant_projection(function.__defaults__),
        "kwdefaults": _code_constant_projection(function.__kwdefaults__),
        "globals_owner": _globals_owner(actor, function.__globals__),
        "builtins_owner": (
            "builtins" if function.__builtins__ is builtins.__dict__ else "other"
        ),
        "closure": {
            name: _closure_value_projection(actor, cell.cell_contents)
            for name, cell in zip(function.__code__.co_freevars, closure, strict=True)
        },
    }


def _assert_live_function(
    actor: ModuleType,
    expected_node: ast.FunctionDef,
    function: object,
    expected_qualname: str,
) -> None:
    _require(
        inspect.isfunction(function),
        f"live actor binding is not a function: {expected_qualname}",
    )
    _require(
        function.__module__ == actor.__name__
        and function.__qualname__ == expected_qualname,
        f"live actor function identity changed: {expected_qualname}",
    )
    _require(
        function.__globals__ is actor.__dict__,
        f"live actor function globals changed: {expected_qualname}",
    )
    _require(
        function.__builtins__ is builtins.__dict__,
        f"live actor function builtins changed: {expected_qualname}",
    )
    expected_first_line = min(
        (item.lineno for item in (*expected_node.decorator_list, expected_node)),
    )
    _require(
        function.__code__.co_firstlineno == expected_first_line
        and inspect.getsourcefile(function) == actor.__file__,
        f"live actor code location changed: {expected_qualname}",
    )
    live_tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    _require(
        len(live_tree.body) == 1
        and ast.dump(live_tree.body[0], include_attributes=False)
        == ast.dump(expected_node, include_attributes=False),
        f"live actor code differs from declared source: {expected_qualname}",
    )


def _assert_live_bindings(
    actor: ModuleType,
    nodes: Mapping[str, ast.AST],
    units: Iterable[str],
    *,
    include_typed_classes: bool,
) -> None:
    for name in units:
        node = nodes[name]
        if isinstance(node, ast.FunctionDef):
            _assert_live_function(actor, node, getattr(actor, name, None), name)
    if not include_typed_classes:
        return
    for class_name in ("_ToolSchemaFacts", "_ToolSchemaInventory"):
        class_node = nodes[class_name]
        _require(isinstance(class_node, ast.ClassDef), f"missing class: {class_name}")
        live_class = getattr(actor, class_name, None)
        _require(
            inspect.isclass(live_class), f"live class binding changed: {class_name}"
        )
        for method_node in (
            item for item in class_node.body if isinstance(item, ast.FunctionDef)
        ):
            descriptor = vars(live_class).get(method_node.name)
            if isinstance(descriptor, (classmethod, staticmethod)):
                function = descriptor.__func__
            elif isinstance(descriptor, property):
                function = descriptor.fget
            else:
                function = descriptor
            _assert_live_function(
                actor,
                method_node,
                function,
                f"{class_name}.{method_node.name}",
            )


def _live_declared_functions(
    actor: ModuleType,
    nodes: Mapping[str, ast.AST],
    units: Iterable[str],
    *,
    include_typed_classes: bool,
) -> tuple[object, ...]:
    functions: list[object] = []
    for name in units:
        node = nodes[name]
        if isinstance(node, ast.FunctionDef):
            functions.append(getattr(actor, name))
    if not include_typed_classes:
        return tuple(functions)
    for class_name in ("_ToolSchemaFacts", "_ToolSchemaInventory"):
        class_node = nodes[class_name]
        live_class = getattr(actor, class_name)
        for method_node in (
            item for item in class_node.body if isinstance(item, ast.FunctionDef)
        ):
            descriptor = vars(live_class)[method_node.name]
            if isinstance(descriptor, (classmethod, staticmethod)):
                functions.append(descriptor.__func__)
            elif isinstance(descriptor, property):
                functions.append(descriptor.fget)
            else:
                functions.append(descriptor)
    return tuple(functions)


def _assert_live_global_dependencies(
    actor: ModuleType,
    nodes: Mapping[str, ast.AST],
    units: Iterable[str],
    expected_global_loads: set[str],
    *,
    include_typed_classes: bool,
    profile: str,
) -> None:
    global_loads = {
        instruction.argval
        for function in _live_declared_functions(
            actor,
            nodes,
            units,
            include_typed_classes=include_typed_classes,
        )
        for instruction in dis.get_instructions(function)
        if instruction.opname == "LOAD_GLOBAL"
    }
    _require(
        global_loads == expected_global_loads,
        f"{profile} live global dependency inventory changed: "
        f"missing={sorted(expected_global_loads - global_loads)}, "
        f"added={sorted(global_loads - expected_global_loads)}",
    )


def _assert_live_class_surfaces(actor: ModuleType) -> None:
    for class_name, expected in EXPECTED_TYPED_CLASS_SURFACES.items():
        live_class = getattr(actor, class_name)
        actual = {
            name: f"{type(value).__module__}.{type(value).__qualname__}"
            for name, value in vars(live_class).items()
        }
        _require(
            actual == expected,
            f"typed live class surface changed for {class_name}: "
            f"missing={sorted(set(expected) - set(actual))}, "
            f"added={sorted(set(actual) - set(expected))}, "
            f"type_changes={sorted(name for name in expected.keys() & actual.keys() if expected[name] != actual[name])}",
        )
        live_class = getattr(actor, class_name)
        init_closure = dict(
            zip(
                live_class.__init__.__code__.co_freevars,
                live_class.__init__.__closure__ or (),
                strict=True,
            )
        )
        _require(
            init_closure["__dataclass_builtins_object__"].cell_contents
            is builtins.object,
            f"typed dataclass __init__ object closure changed: {class_name}",
        )
        frozen_class_cells: list[object] = []
        for method_name in ("__setattr__", "__delattr__"):
            method = vars(live_class)[method_name]
            closure = dict(
                zip(
                    method.__code__.co_freevars,
                    method.__closure__ or (),
                    strict=True,
                )
            )
            _require(
                closure["FrozenInstanceError"].cell_contents is FrozenInstanceError,
                f"typed dataclass frozen closure changed: {class_name}.{method_name}",
            )
            frozen_class_cells.append(closure["cls"].cell_contents)
        slot_origin = frozen_class_cells[0]
        _require(
            frozen_class_cells[1] is slot_origin
            and isinstance(slot_origin, type)
            and slot_origin is not live_class
            and slot_origin.__module__ == live_class.__module__
            and slot_origin.__qualname__ == live_class.__qualname__,
            f"typed slotted dataclass origin closure changed: {class_name}",
        )
        repr_method = vars(live_class)["__repr__"]
        repr_closure = dict(
            zip(
                repr_method.__code__.co_freevars,
                repr_method.__closure__ or (),
                strict=True,
            )
        )
        _require(
            type(repr_closure["repr_running"].cell_contents) is set
            and not repr_closure["repr_running"].cell_contents
            and repr_closure["user_function"].cell_contents.__globals__
            is actor.__dict__,
            f"typed dataclass repr closure changed: {class_name}",
        )


def _assert_no_normalization_or_cache(nodes: Mapping[str, ast.AST]) -> None:
    facts = nodes["_ToolSchemaFacts"]
    inventory = nodes["_ToolSchemaInventory"]
    forbidden_normalizers = {
        call.func.attr
        for call in ast.walk(facts)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
        if call.func.attr in {"strip", "casefold", "lstrip", "rstrip"}
    }
    _require(
        not forbidden_normalizers,
        f"typed raw-field normalization broadened: {sorted(forbidden_normalizers)}",
    )
    forbidden_cache_names = {
        name
        for node in ast.walk(inventory)
        if isinstance(node, ast.Name)
        and (name := node.id) in {"cache", "cached_property", "lru_cache"}
    }
    _require(
        not forbidden_cache_names,
        f"typed inventory introduced caching: {sorted(forbidden_cache_names)}",
    )


def _assert_typed_boundaries(nodes: Mapping[str, ast.AST]) -> None:
    facts = nodes["_ToolSchemaFacts"]
    inventory = nodes["_ToolSchemaInventory"]
    _require(isinstance(facts, ast.ClassDef), "_ToolSchemaFacts is not a class")
    _require(isinstance(inventory, ast.ClassDef), "_ToolSchemaInventory is not a class")
    expected_decorator = "@dataclass(frozen=True, slots=True)"
    _require(
        ast.unparse(facts).startswith(expected_decorator)
        and ast.unparse(inventory).startswith(expected_decorator),
        "typed schema containers lost frozen slotted dataclass identity",
    )
    fact_fields = tuple(
        node.target.id
        for node in facts.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    )
    inventory_fields = tuple(
        node.target.id
        for node in inventory.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    )
    _require(
        fact_fields == ("function", "name", "description", "properties", "input_names"),
        f"typed fact field inventory changed: {fact_fields}",
    )
    _require(
        inventory_fields == ("source",),
        f"typed inventory field set changed: {inventory_fields}",
    )
    fact_methods = tuple(
        node.name for node in facts.body if isinstance(node, ast.FunctionDef)
    )
    inventory_methods = tuple(
        node.name for node in inventory.body if isinstance(node, ast.FunctionDef)
    )
    _require(
        fact_methods
        == (
            "from_tool",
            "marker_text",
            "description_has",
            "marker_has",
            "has_inputs",
            "has_any_input",
            "is_selector",
            "is_derived_value",
            "is_lookup_query_planner",
            "is_search_window",
            "is_scheduling_timestamp",
            "is_state_action_planner",
            "is_validation_abstention",
            "is_relative_time",
            "is_action_argument_helper",
            "is_post_selection_action_helper",
        ),
        f"typed fact method inventory changed: {fact_methods}",
    )
    _require(
        inventory_methods == ("tools", "raw_names", "find"),
        f"typed inventory method set changed: {inventory_methods}",
    )

    from_tool = _class_method(facts, "from_tool")
    normalized = ast.unparse(from_tool)
    _require(
        "description = str(function.get('description', '')).lower()" in normalized,
        "typed description normalization changed",
    )
    _require(
        "if not isinstance(function, dict):" in normalized
        and "if isinstance(parameters, dict)" in normalized
        and "if isinstance(properties, dict)" in normalized,
        "typed exact-dict parsing boundary changed",
    )

    marker_text = _class_method(facts, "marker_text")
    _require(
        "return f'{self.name} {self.description}'" in ast.unparse(marker_text),
        "typed joined raw-name/description bytes changed",
    )

    tools = _class_method(inventory, "tools")
    tools_text = ast.unparse(tools)
    _require(
        "self.source is NOT_GIVEN" in tools_text
        and any(isinstance(node, ast.YieldFrom) for node in ast.walk(tools)),
        "typed inventory sentinel or lazy iteration changed",
    )
    eager_calls = {
        _call_name(node)
        for node in ast.walk(tools)
        if isinstance(node, ast.Call)
        and _call_name(node) in {"list", "tuple", "sorted"}
    }
    _require(not eager_calls, f"typed inventory eagerly materializes: {eager_calls}")

    find = _class_method(inventory, "find")
    find_text = ast.unparse(find)
    _require(
        "self.source is NOT_GIVEN" in find_text
        and "isinstance(function, Mapping)" in find_text
        and "return (tool, function)" in find_text,
        "typed lookup Mapping/sentinel/original-schema boundary changed",
    )

    raw_names = _class_method(inventory, "raw_names")
    _require(
        "isinstance((function := tool.get('function', {})), dict)"
        in ast.unparse(raw_names),
        "typed raw-name exact-dict boundary changed",
    )

    category_names = _function(nodes, "_category_names")
    category_calls = {
        _call_name(node)
        for node in ast.walk(category_names)
        if isinstance(node, ast.Call)
    }
    _require(
        not ({"list", "tuple", "sorted"} & category_calls),
        "typed category scan eagerly materializes or reorders schemas",
    )

    output_names = ast.unparse(_function(nodes, "_tool_output_names_execution_facing"))
    _require(
        "output_schema: object = function.get('output_schema', {})" in output_names
        and "if not output_schema and isinstance(parameters, Mapping):" in output_names
        and "output_schema = parameters.get('output_schema', {})" in output_names,
        "typed direct/nested output-schema precedence changed",
    )

    tool_name_for_call = ast.unparse(_function(nodes, "_tool_name_for_call"))
    generated_names = ast.unparse(
        _function(nodes, "_generated_tool_names_execution_facing")
    )
    _require(
        "for name in _tool_names(openai_tools):" in tool_name_for_call
        and "for tool_name in _tool_names(openai_tools)" in generated_names,
        "typed set-derived name ordering changed",
    )

    producers = ast.unparse(_function(nodes, "_declared_service_answer_producers"))
    _require(
        "_tool_schema_text(found[0])" in producers
        and "sorted(SERVICE_ANSWER_PRODUCER_TOOLS)" in producers,
        "typed producer original-schema reread or mutable inventory changed",
    )

    facts_text = ast.unparse(facts)
    _require(
        facts_text.count("ORIGINAL_SIDE_EFFECT_TOOL_NAMES") == 2,
        "typed side-effect inventory is no longer read at call time",
    )
    _require(
        "ORIGINAL_TOOLSANDBOX_TOOL_NAMES" in generated_names,
        "typed native/generated inventory is no longer read at call time",
    )
    _assert_no_normalization_or_cache(nodes)


def inspect_actor_schema_source(actor: ModuleType) -> dict[str, Any]:
    """Return and verify the accepted source profile for an imported actor."""

    source = inspect.getsource(actor)
    tree = ast.parse(source)
    nodes = _named_nodes(tree)
    has_facts = "_ToolSchemaFacts" in nodes
    has_inventory = "_ToolSchemaInventory" in nodes
    _require(has_facts == has_inventory, "partial typed actor-schema architecture")

    if not has_facts:
        profile = "legacy"
        units = LEGACY_UNITS
        _assert_live_bindings(
            actor,
            nodes,
            units,
            include_typed_classes=False,
        )
        _assert_live_global_dependencies(
            actor,
            nodes,
            units,
            EXPECTED_LEGACY_GLOBAL_LOADS,
            include_typed_classes=False,
            profile=profile,
        )
        _assert_canonical_runtime_dependencies(actor, profile)
        marker_inventory = _legacy_marker_inventory(nodes)
        _require(
            marker_inventory
            == behavior.JOINED_NAME_DESCRIPTION_MARKERS_BY_CATEGORY_CASE,
            "legacy joined-marker source inventory changed",
        )
    else:
        profile = "typed_v1"
        units = (*TYPED_CONSTANTS, *TYPED_UNITS)
        _assert_no_typed_rebindings(tree)
        _assert_typed_wrappers(nodes)
        _assert_typed_boundaries(nodes)
        _assert_live_bindings(
            actor,
            nodes,
            TYPED_UNITS,
            include_typed_classes=True,
        )
        _assert_live_global_dependencies(
            actor,
            nodes,
            TYPED_UNITS,
            EXPECTED_TYPED_GLOBAL_LOADS,
            include_typed_classes=True,
            profile=profile,
        )
        _assert_canonical_runtime_dependencies(actor, profile)
        _assert_live_class_surfaces(actor)
        marker_inventory = _typed_marker_inventory(actor)
        expected_markers = {
            case_id: frozenset(markers)
            for case_id, markers in (
                behavior.JOINED_NAME_DESCRIPTION_MARKERS_BY_CATEGORY_CASE.items()
            )
        }
        _require(
            marker_inventory == expected_markers,
            "typed joined-marker source inventory changed",
        )

    ast_digest = _digest_nodes(nodes, units)
    _require(
        ast_digest == EXPECTED_AST_SHA256[profile],
        f"{profile} actor-schema AST digest changed: {ast_digest}",
    )
    source_digest = _digest_source(source, nodes, units)
    _require(
        source_digest == EXPECTED_SOURCE_SHA256[profile],
        f"{profile} actor-schema source digest changed: {source_digest}",
    )
    dependencies = _dependency_projection(nodes, units)
    dependency_digest = _dependency_digest(dependencies)
    if profile == "typed_v1":
        _require(
            dependency_digest == EXPECTED_TYPED_DEPENDENCY_SHA256,
            f"typed actor-schema dependency digest changed: {dependency_digest}",
        )
    live_code_digest = _live_code_digest(
        actor,
        nodes,
        units,
        include_typed_methods=profile == "typed_v1",
    )
    _require(
        live_code_digest == EXPECTED_LIVE_CODE_SHA256[profile],
        f"{profile} actor-schema live code digest changed: {live_code_digest}",
    )
    return {
        "profile": profile,
        "ast_sha256": ast_digest,
        "source_sha256": source_digest,
        "dependency_sha256": dependency_digest,
        "live_code_sha256": live_code_digest,
        "joined_marker_categories": tuple(marker_inventory),
    }


def _replace_once(source: str, old: str, new: str) -> str:
    _require(source.count(old) == 1, f"typed mutant carrier count changed: {old!r}")
    return source.replace(old, new, 1)


def _typed_mutants(source: str) -> dict[str, str]:
    """Plausible typed refactor mistakes that the source profile must reject."""

    frozen_side_effects = _replace_once(
        source,
        "@dataclass(frozen=True, slots=True)\nclass _ToolSchemaFacts:",
        "_FROZEN_SIDE_EFFECT_NAMES = tuple(ORIGINAL_SIDE_EFFECT_TOOL_NAMES)\n\n\n"
        "@dataclass(frozen=True, slots=True)\nclass _ToolSchemaFacts:",
    )
    frozen_side_effects = _replace_once(
        frozen_side_effects,
        "returns_call = self.marker_has(*_DOWNSTREAM_CALL_MARKERS) or any(\n"
        "            name in self.marker_text for name in ORIGINAL_SIDE_EFFECT_TOOL_NAMES",
        "returns_call = self.marker_has(*_DOWNSTREAM_CALL_MARKERS) or any(\n"
        "            name in self.marker_text for name in _FROZEN_SIDE_EFFECT_NAMES",
    )
    post_definition_rebind = (
        source + "\n\ndef _widen_derived_value(self):\n"
        "    return 'derive' in self.marker_text\n\n"
        "_ToolSchemaFacts.is_derived_value = _widen_derived_value\n"
    )
    code_object_rebind = (
        source + "\n\ndef _replace_derived_code(self):\n"
        "    return 'derive' in self.marker_text\n\n"
        "_ToolSchemaFacts.is_derived_value.__code__ = "
        "_replace_derived_code.__code__\n"
    )
    extra_magic_method = (
        source + "\n\ndef _schema_getattribute(self, name):\n"
        "    return object.__getattribute__(self, name)\n\n"
        "_ToolSchemaFacts.__getattribute__ = _schema_getattribute\n"
    )
    return {
        "dropped_wrapper_delegation": _replace_once(
            source,
            "return _category_names(openai_tools, _ToolSchemaFacts.is_selector)",
            "return _category_names(openai_tools, _ToolSchemaFacts.is_derived_value)",
        ),
        "raw_description_strip": _replace_once(
            source,
            'description = str(function.get("description", "")).lower()',
            'description = str(function.get("description", "")).strip().lower()',
        ),
        "broadened_function_mapping": _replace_once(
            source,
            "if not isinstance(function, dict):\n            return None",
            "if not isinstance(function, Mapping):\n            return None",
        ),
        "eager_inventory_materialization": _replace_once(
            source,
            "yield from cast(Iterable[Mapping[str, Any]], self.source)",
            "yield from list(cast(Iterable[Mapping[str, Any]], self.source))",
        ),
        "sentinel_equality": _replace_once(
            source,
            "if self.source is NOT_GIVEN:\n            return\n"
            "        yield from cast(Iterable[Mapping[str, Any]], self.source)",
            "if self.source == NOT_GIVEN:\n            return\n"
            "        yield from cast(Iterable[Mapping[str, Any]], self.source)",
        ),
        "nested_output_overrides_direct": _replace_once(
            source,
            "if not output_schema and isinstance(parameters, Mapping):",
            "if isinstance(parameters, Mapping):",
        ),
        "schema_order_generated_names": _replace_once(
            source,
            "for tool_name in _tool_names(openai_tools)\n        if",
            "for tool_name in sorted(_tool_names(openai_tools))\n        if",
        ),
        "producer_reads_parsed_function": _replace_once(
            source,
            "_tool_schema_text(found[0])",
            "_tool_schema_text(found[1])",
        ),
        "cached_inventory": _replace_once(
            source,
            "    def raw_names(self) -> set[str]:",
            "    @cached_property\n    def raw_names(self) -> set[str]:",
        ),
        "frozen_side_effect_inventory": frozen_side_effects,
        "post_definition_predicate_rebind": post_definition_rebind,
        "post_definition_code_object_rebind": code_object_rebind,
        "extra_live_magic_method": extra_magic_method,
        "canonical_sentinel_rebind": source + "\nNOT_GIVEN = object()\n",
        "eager_cast_rebind": (
            source + "\n\ndef cast(_type, value):\n    return list(value)\n"
        ),
    }


def assert_typed_mutants_rejected(actor: ModuleType) -> tuple[str, ...]:
    """Prove representative typed architectural regressions fail closed."""

    source = inspect.getsource(actor)
    rejected: list[str] = []
    for name, mutant in _typed_mutants(source).items():
        tree = ast.parse(mutant)
        nodes = _named_nodes(tree)
        try:
            _assert_no_typed_rebindings(tree)
            _assert_typed_wrappers(nodes)
            _assert_typed_boundaries(nodes)
            digest = _digest_nodes(nodes, (*TYPED_CONSTANTS, *TYPED_UNITS))
            _require(
                digest == EXPECTED_AST_SHA256["typed_v1"],
                f"typed actor-schema AST digest changed: {digest}",
            )
        except ActorSchemaSourceContractError:
            rejected.append(name)
            continue
        _fail(f"typed actor-schema mutant escaped: {name}")
    return tuple(rejected)


def _assert_canonical_runtime_dependencies(actor: ModuleType, profile: str) -> None:
    """Require imported dependencies to retain their canonical identities."""

    from openai import NOT_GIVEN as canonical_not_given
    from tool_sandbox.common.execution_context import (
        get_current_context as canonical_get_current_context,
    )

    _require(
        actor.NOT_GIVEN is canonical_not_given,
        f"{profile} actor NOT_GIVEN is not the canonical OpenAI sentinel",
    )
    expected_module_dependencies = {
        "Any": typing.Any,
        "cast": typing.cast,
        "Mapping": typing.Mapping,
        "Iterable": typing.Iterable,
        "json": json,
        "get_current_context": canonical_get_current_context,
    }
    for name, expected in expected_module_dependencies.items():
        _require(
            getattr(actor, name, None) is expected,
            f"{profile} runtime dependency rebound: {name}",
        )
    for name in (
        "Exception",
        "TypeError",
        "any",
        "bool",
        "dict",
        "isinstance",
        "len",
        "list",
        "set",
        "sorted",
        "str",
        "tuple",
    ):
        expected = getattr(builtins, name)
        _require(
            actor.__dict__.get(name, expected) is expected,
            f"{profile} builtin dependency shadowed: {name}",
        )
    expected_inventories = {
        "ORIGINAL_TOOLSANDBOX_TOOL_NAMES": (
            behavior.EXPECTED_ORIGINAL_TOOLSANDBOX_TOOL_NAMES
        ),
        "ORIGINAL_SIDE_EFFECT_TOOL_NAMES": (
            behavior.EXPECTED_ORIGINAL_SIDE_EFFECT_TOOL_NAMES
        ),
        "SERVICE_ANSWER_PRODUCER_TOOLS": (
            behavior.EXPECTED_SERVICE_ANSWER_PRODUCER_TOOLS
        ),
    }
    for name, expected in expected_inventories.items():
        actual = getattr(actor, name, None)
        _require(
            type(actual) is set and tuple(sorted(actual)) == expected,
            f"{profile} mutable tool inventory changed: {name}",
        )


def assert_typed_runtime_boundaries(actor: ModuleType) -> dict[str, bool]:
    """Exercise boundaries that source shape alone cannot prove at runtime."""

    _assert_canonical_runtime_dependencies(actor, "typed_v1")
    expected_structural_constants = {
        "_DERIVED_INPUT_TYPES": {
            "object",
            "array",
            "string",
            "number",
            "integer",
            "boolean",
        },
        "_SCHEDULING_INPUTS": {
            "current_timestamp",
            "hour",
            "minute",
            "local_utc_offset_hours",
        },
        "_PRIOR_RECORD_INPUTS": {
            "records",
            "candidates",
            "selected_record",
            "contact_record",
        },
        "_WINDOW_MARKERS": (
            "time-window",
            "recency phrase",
            "search kwargs",
            "bounded search",
        ),
    }
    for name, expected in expected_structural_constants.items():
        _require(
            getattr(actor, name, None) == expected
            and type(getattr(actor, name, None)) is type(expected),
            f"typed structural constant rebound: {name}",
        )
    for name in (
        "_DERIVED_MARKERS",
        "_LOOKUP_QUERY_MARKERS",
        "_RELATIVE_TIME_MARKERS",
        "_SHARED_ACTION_ARGUMENT_MARKERS",
        "_ACTION_ARGUMENT_MARKERS",
        "_DOWNSTREAM_CALL_MARKERS",
        "_POST_SELECTION_MARKERS",
    ):
        _require(
            type(getattr(actor, name, None)) is tuple,
            f"typed marker constant changed container type: {name}",
        )

    facts_type = actor._ToolSchemaFacts
    inventory_type = actor._ToolSchemaInventory
    _require(
        inspect.isgeneratorfunction(inventory_type.tools),
        "typed inventory tools() is no longer lazy",
    )
    _require(
        facts_type.__slots__
        == ("function", "name", "description", "properties", "input_names")
        and inventory_type.__slots__ == ("source",),
        "typed runtime slots changed",
    )

    def schema(
        name: str,
        *,
        description: str = "",
        properties: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": dict(properties or {}),
                },
            },
        }

    frozen = inventory_type([])
    try:
        frozen.source = ()
    except FrozenInstanceError:
        pass
    else:
        _fail("typed inventory is no longer frozen")

    yielded = 0

    def tracked_iterator() -> Iterable[Mapping[str, Any]]:
        nonlocal yielded
        for index in range(3):
            yielded += 1
            yield schema(f"lazy_probe_{index}")

    lazy_iterator = inventory_type(iter(tracked_iterator())).tools()
    _require(
        yielded == 0,
        "typed inventory iterated during generator construction",
    )
    next(lazy_iterator)
    _require(
        yielded == 1,
        "typed inventory consumed past its first streamed schema",
    )
    list(lazy_iterator)
    _require(yielded == 3, "typed inventory dropped streamed schemas")

    mutable_source = [schema("first_visible")]
    mutable_inventory = inventory_type(mutable_source)
    _require(
        mutable_inventory.raw_names() == {"first_visible"},
        "typed inventory initial mutable-source scan changed",
    )
    mutable_source.append(schema("second_visible"))
    _require(
        mutable_inventory.raw_names() == {"first_visible", "second_visible"},
        "typed inventory cached mutable source state",
    )

    one_shot = inventory_type(iter((schema("one_shot"),)))
    _require(
        one_shot.raw_names() == {"one_shot"} and one_shot.raw_names() == set(),
        "typed inventory materialized or replayed a one-shot source",
    )

    class FalseySchemas(list[Mapping[str, Any]]):
        def __bool__(self) -> bool:
            return False

    _require(
        inventory_type(FalseySchemas((schema("falsey_probe"),))).raw_names()
        == {"falsey_probe"},
        "typed inventory treated a falsey iterable as missing",
    )

    class SentinelEqualityDecoy:
        def __eq__(self, _other: object) -> bool:
            return True

        def __iter__(self) -> Iterable[Mapping[str, Any]]:
            yield schema("identity_probe")

    _require(
        inventory_type(SentinelEqualityDecoy()).raw_names() == {"identity_probe"},
        "typed inventory used equality instead of NOT_GIVEN identity",
    )
    missing_inventory = inventory_type(actor.NOT_GIVEN)
    _require(
        list(missing_inventory.tools()) == []
        and missing_inventory.find("missing") is None,
        "typed NOT_GIVEN boundary changed",
    )

    producer_name = "convert_currency"
    target_name = "second_read_probe"

    class SecondReadSchema(dict[str, Any]):
        reads = 0

        def get(self, key: str, default: Any = None) -> Any:
            if key != "function":
                return super().get(key, default)
            self.reads += 1
            function: dict[str, Any] = {
                "name": target_name,
                "parameters": {"type": "object", "properties": {}},
            }
            if self.reads >= 2:
                function["description"] = f"Consumes {producer_name} output."
            return function

    second_read = SecondReadSchema(type="function")
    _require(
        actor._declared_service_answer_producers([second_read], target_name)
        == (producer_name,)
        and second_read.reads == 2,
        "typed producer scan did not reread the original schema exactly once",
    )

    side_effect_probe = "actor_guard_live_side_effect_probe"
    service_probe = "actor_guard_live_service_probe"
    native_probe = "actor_guard_live_native_probe"
    side_effects = actor.ORIGINAL_SIDE_EFFECT_TOOL_NAMES
    service_producers = actor.SERVICE_ANSWER_PRODUCER_TOOLS
    native_names = actor.ORIGINAL_TOOLSANDBOX_TOOL_NAMES
    _require(
        all(
            type(value) is set
            for value in (side_effects, service_producers, native_names)
        ),
        "typed mutable tool-name inventories changed type",
    )
    action_schema = schema(
        "live_action_helper",
        description=f"Prepare arguments, then use {side_effect_probe}.",
        properties={"user_request": {"type": "string"}},
    )
    post_schema = schema(
        "live_post_helper",
        description=f"Use {side_effect_probe}.",
        properties={"selected_record": {"type": "object"}},
    )
    producer_schema = schema(
        "live_producer_consumer",
        description=f"Consumes {service_probe} output.",
    )
    native_schema = schema(native_probe)
    _require(
        actor._action_argument_helper_tool_names([action_schema]) == set()
        and actor._post_selection_action_helper_tool_names([post_schema]) == set()
        and actor._declared_service_answer_producers(
            [producer_schema], "live_producer_consumer"
        )
        == ()
        and actor._generated_tool_names_execution_facing([native_schema])
        == [native_probe],
        "typed late-binding probes collided with existing inventories",
    )
    try:
        actor.ORIGINAL_SIDE_EFFECT_TOOL_NAMES = {*side_effects, side_effect_probe}
        actor.SERVICE_ANSWER_PRODUCER_TOOLS = {*service_producers, service_probe}
        actor.ORIGINAL_TOOLSANDBOX_TOOL_NAMES = {*native_names, native_probe}
        _require(
            actor._action_argument_helper_tool_names([action_schema])
            == {"live_action_helper"}
            and actor._post_selection_action_helper_tool_names([post_schema])
            == {"live_post_helper"}
            and actor._declared_service_answer_producers(
                [producer_schema], "live_producer_consumer"
            )
            == (service_probe,)
            and actor._generated_tool_names_execution_facing([native_schema]) == [],
            "typed predicates captured a mutable tool-name inventory early",
        )
    finally:
        actor.ORIGINAL_SIDE_EFFECT_TOOL_NAMES = side_effects
        actor.SERVICE_ANSWER_PRODUCER_TOOLS = service_producers
        actor.ORIGINAL_TOOLSANDBOX_TOOL_NAMES = native_names

    return {
        "frozen_slots": True,
        "lazy_one_shot_fresh": True,
        "sentinel_identity": True,
        "producer_second_read": True,
        "mutable_constants_live": True,
    }


def assert_runtime_dependency_mutants_rejected(
    actor: ModuleType,
) -> tuple[str, ...]:
    """Prove every externally loaded dependency is identity-checked."""

    rejected: list[str] = []
    for name in sorted(TYPED_EXTERNAL_GLOBALS):
        existed = name in actor.__dict__
        original = actor.__dict__.get(name)
        setattr(actor, name, object())
        try:
            inspect_actor_schema_source(actor)
        except ActorSchemaSourceContractError:
            rejected.append(f"live_{name}_rebind")
        else:
            _fail(f"live {name} dependency rebinding escaped source validation")
        finally:
            if existed:
                setattr(actor, name, original)
            else:
                delattr(actor, name)
    return tuple(rejected)


def assert_mutable_inventory_mutants_rejected(
    actor: ModuleType,
) -> tuple[str, ...]:
    """Prove set-subclass semantics and inventory-content drift fail closed."""

    class GhostSet(set[str]):
        def __contains__(self, value: object) -> bool:
            return value == "ghost_native" or super().__contains__(value)

    rejected: list[str] = []
    for name in (
        "ORIGINAL_SIDE_EFFECT_TOOL_NAMES",
        "ORIGINAL_TOOLSANDBOX_TOOL_NAMES",
        "SERVICE_ANSWER_PRODUCER_TOOLS",
    ):
        original = getattr(actor, name)
        for suffix, replacement in (
            ("subclass", GhostSet(original)),
            ("content", {*original, "ghost_native"}),
        ):
            setattr(actor, name, replacement)
            try:
                inspect_actor_schema_source(actor)
            except ActorSchemaSourceContractError:
                rejected.append(f"live_{name}_{suffix}")
            else:
                _fail(f"live {name} {suffix} mutant escaped source validation")
            finally:
                setattr(actor, name, original)
    return tuple(rejected)


def assert_live_rebinding_mutants_rejected(actor: ModuleType) -> tuple[str, ...]:
    """Prove post-import mutation cannot bypass the frozen source profile."""

    rejected: list[str] = []
    original_predicate = actor._ToolSchemaFacts.is_derived_value

    def widened_predicate(self: Any) -> bool:
        return "derive" in self.marker_text

    actor._ToolSchemaFacts.is_derived_value = widened_predicate
    try:
        inspect_actor_schema_source(actor)
    except ActorSchemaSourceContractError:
        rejected.append("live_predicate_rebind")
    else:
        _fail("live predicate rebinding escaped source validation")
    finally:
        actor._ToolSchemaFacts.is_derived_value = original_predicate

    original_sentinel = actor.NOT_GIVEN
    actor.NOT_GIVEN = object()
    try:
        assert_typed_runtime_boundaries(actor)
    except ActorSchemaSourceContractError:
        rejected.append("live_sentinel_rebind")
    else:
        _fail("live NOT_GIVEN rebinding escaped runtime validation")
    finally:
        actor.NOT_GIVEN = original_sentinel

    original_cast = actor.cast

    def eager_iterator_cast(_type: Any, value: Any) -> Any:
        return list(value) if isinstance(value, Iterator) else value

    actor.cast = eager_iterator_cast
    try:
        assert_typed_runtime_boundaries(actor)
    except ActorSchemaSourceContractError:
        rejected.append("live_eager_cast_rebind")
    else:
        _fail("live eager-cast rebinding escaped runtime validation")
    finally:
        actor.cast = original_cast

    original_context = actor.get_current_context
    actor.get_current_context = lambda: None
    try:
        assert_typed_runtime_boundaries(actor)
    except ActorSchemaSourceContractError:
        rejected.append("live_context_rebind")
    else:
        _fail("live execution-context rebinding escaped runtime validation")
    finally:
        actor.get_current_context = original_context

    for name, replacement in (("Exception", RuntimeError), ("dict", Mapping)):
        existed = name in actor.__dict__
        original = actor.__dict__.get(name)
        setattr(actor, name, replacement)
        try:
            assert_typed_runtime_boundaries(actor)
        except ActorSchemaSourceContractError:
            rejected.append(f"live_{name}_rebind")
        else:
            _fail(f"live {name} rebinding escaped runtime validation")
        finally:
            if existed:
                setattr(actor, name, original)
            else:
                delattr(actor, name)

    original_code = original_predicate.__code__

    def widened_code(self: Any) -> bool:
        return "derive" in self.marker_text

    original_predicate.__code__ = widened_code.__code__.replace(
        co_filename=original_code.co_filename,
        co_firstlineno=original_code.co_firstlineno,
        co_name=original_code.co_name,
        co_qualname=original_code.co_qualname,
    )
    try:
        inspect_actor_schema_source(actor)
    except ActorSchemaSourceContractError:
        rejected.append("live_code_object_rebind")
    else:
        _fail("live code-object rebinding escaped source validation")
    finally:
        original_predicate.__code__ = original_code

    def schema_getattribute(self: Any, name: str) -> Any:
        value = object.__getattribute__(self, name)
        if name == "marker_text" and "reusable value" in str(value):
            return f"{value} extract"
        return value

    actor._ToolSchemaFacts.__getattribute__ = schema_getattribute
    try:
        inspect_actor_schema_source(actor)
    except ActorSchemaSourceContractError:
        rejected.append("live_extra_magic_method")
    else:
        _fail("live extra magic method escaped source validation")
    finally:
        del actor._ToolSchemaFacts.__getattribute__

    alternate_globals = dict(actor.__dict__)
    alternate_globals["_DERIVED_MARKERS"] = (
        *actor._DERIVED_MARKERS,
        "derive",
    )
    cloned_predicate = FunctionType(
        original_predicate.__code__,
        alternate_globals,
        original_predicate.__name__,
        original_predicate.__defaults__,
        original_predicate.__closure__,
    )
    cloned_predicate.__kwdefaults__ = original_predicate.__kwdefaults__
    cloned_predicate.__annotations__ = original_predicate.__annotations__
    cloned_predicate.__module__ = original_predicate.__module__
    cloned_predicate.__qualname__ = original_predicate.__qualname__
    actor._ToolSchemaFacts.is_derived_value = cloned_predicate
    try:
        inspect_actor_schema_source(actor)
    except ActorSchemaSourceContractError:
        rejected.append("live_alternate_globals_clone")
    else:
        _fail("live alternate-globals clone escaped source validation")
    finally:
        actor._ToolSchemaFacts.is_derived_value = original_predicate

    original_marker_has = actor._ToolSchemaFacts.marker_has
    original_builtins_binding = actor.__dict__.get("__builtins__")
    evil_builtins = dict(builtins.__dict__)
    evil_builtins["any"] = lambda _values: True
    actor.__dict__["__builtins__"] = evil_builtins
    captured_builtins_clone = FunctionType(
        original_marker_has.__code__,
        actor.__dict__,
        original_marker_has.__name__,
        original_marker_has.__defaults__,
        original_marker_has.__closure__,
    )
    actor.__dict__["__builtins__"] = original_builtins_binding
    captured_builtins_clone.__kwdefaults__ = original_marker_has.__kwdefaults__
    captured_builtins_clone.__annotations__ = original_marker_has.__annotations__
    captured_builtins_clone.__module__ = original_marker_has.__module__
    captured_builtins_clone.__qualname__ = original_marker_has.__qualname__
    actor._ToolSchemaFacts.marker_has = captured_builtins_clone
    try:
        inspect_actor_schema_source(actor)
    except ActorSchemaSourceContractError:
        rejected.append("live_captured_builtins_clone")
    else:
        _fail("live captured-builtins clone escaped source validation")
    finally:
        actor._ToolSchemaFacts.marker_has = original_marker_has

    original_init = vars(actor._ToolSchemaFacts)["__init__"]

    class SpoofedObject:
        pass

    SpoofedObject.__module__ = "builtins"
    SpoofedObject.__qualname__ = "object"

    def closure_cell(value: object) -> object:
        return (lambda: value).__closure__[0]

    cloned_init = FunctionType(
        original_init.__code__,
        original_init.__globals__,
        original_init.__name__,
        original_init.__defaults__,
        (closure_cell(SpoofedObject),),
    )
    cloned_init.__kwdefaults__ = original_init.__kwdefaults__
    cloned_init.__annotations__ = original_init.__annotations__
    cloned_init.__module__ = original_init.__module__
    cloned_init.__qualname__ = original_init.__qualname__
    actor._ToolSchemaFacts.__init__ = cloned_init
    try:
        inspect_actor_schema_source(actor)
    except ActorSchemaSourceContractError:
        rejected.append("live_spoofed_init_closure")
    else:
        _fail("live spoofed dataclass closure escaped source validation")
    finally:
        actor._ToolSchemaFacts.__init__ = original_init

    return tuple(rejected)
