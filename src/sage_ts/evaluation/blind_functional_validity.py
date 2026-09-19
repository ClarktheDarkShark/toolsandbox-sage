"""Post-freeze blind functional-validity audit for generated-tool registries.

The admission validator answers whether a tool may enter the registry.  This
module intentionally answers a different question: does the frozen tool pass a
separately authored, content-addressed oracle bank that was not used for tool
generation, repair, or admission?

The strict endpoint is tool weighted.  Every non-retired registry entry is in
the denominator and a tool passes only when every integrity, static-safety, and
oracle check passes.  A missing case is therefore a failure, never an implicit
exclusion.  Native actions are replaced with recording stubs; the audit cannot
mutate ToolSandbox state.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from scipy.stats import beta  # type: ignore[import-untyped]

from sage_ts.generation.complete_tools import (
    COMPLETE_TOOLS_NATIVE_NAMES,
    native_action_names_for_tool,
    native_action_spec_enabled,
    native_action_tool_enabled,
    native_side_effect_tools,
)
from sage_ts.generation.tool_spec import GeneratedTool
from sage_ts.registry.manifest import (
    RegistryEntry,
    code_hash,
    has_current_validation_proof,
)
from sage_ts.registry.store import RegistryStore
from sage_ts.registry.validation_contracts import ValidationContractBindingStore
from sage_ts.validation.ast_safety import check_ast_safety
from sage_ts.validation.output_normalization import normalize_generated_tool_output
from sage_ts.validation.schema_check import compile_generated_tool

CASE_BANK_SCHEMA_VERSION = 1
AUDIT_REPORT_SCHEMA_VERSION = 1
ENDPOINT_NAME = "blind_functional_validity_of_accepted_tools"
CONSTRUCTION_METHOD = "external_spec_only_exact_oracle_v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CASE_TYPES = frozenset({"exact_output", "native_action_oracle"})


class BlindFunctionalValidityError(ValueError):
    """Raised for a malformed or unverifiable audit input."""


@dataclass(frozen=True)
class RegistrySnapshot:
    """Content-addressed snapshot of every regular file in a registry root."""

    tree_sha256: str
    manifest_sha256: str | None
    files: dict[str, dict[str, Any]]
    errors: tuple[str, ...]


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BlindFunctionalValidityError("noncanonical_json_value") from exc


def _json_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    """Return a raw-byte SHA-256 digest for a case-bank pin or artifact."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _snapshot_registry(root: Path) -> RegistrySnapshot:
    root = root.resolve()
    errors: list[str] = []
    files: dict[str, dict[str, Any]] = {}
    if not root.is_dir():
        return RegistrySnapshot("", None, {}, ("registry_directory_missing",))

    # os.walk with followlinks=False lets us detect a directory symlink without
    # traversing outside the registry root.
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        for name in tuple(directory_names):
            candidate = directory_path / name
            if candidate.is_symlink():
                relative = candidate.relative_to(root).as_posix()
                errors.append(f"registry_symlink:{relative}")
                directory_names.remove(name)
        for name in sorted(file_names):
            candidate = directory_path / name
            relative = candidate.relative_to(root).as_posix()
            if candidate.is_symlink():
                errors.append(f"registry_symlink:{relative}")
                continue
            if not candidate.is_file():
                errors.append(f"registry_nonregular_file:{relative}")
                continue
            try:
                files[relative] = {
                    "sha256": file_sha256(candidate),
                    "size_bytes": candidate.stat().st_size,
                }
            except OSError:
                errors.append(f"registry_file_unreadable:{relative}")
    tree_hash = _json_sha256(files)
    manifest = files.get("registry_manifest.json")
    return RegistrySnapshot(
        tree_sha256=tree_hash,
        manifest_sha256=str(manifest["sha256"]) if manifest else None,
        files=files,
        errors=tuple(sorted(set(errors))),
    )


def _tool_spec_sha256(entry: RegistryEntry) -> str:
    return _json_sha256(entry.tool.spec.to_json())


def _active_entries(registry_dir: Path) -> dict[str, RegistryEntry]:
    entries = RegistryStore(registry_dir).load_entries()
    return {name: entry for name, entry in sorted(entries.items()) if not entry.retired}


def create_case_bank_scaffold(
    *,
    registry_dir: Path,
    output_path: Path,
    bank_id: str,
    minimum_oracle_cases_per_tool: int = 2,
) -> dict[str, Any]:
    """Export a code- and admission-case-free packet for a blind case author.

    The packet contains only the public tool specification plus immutable
    version/hash bindings.  An independent assessor fills each ``cases`` list,
    locks the resulting file by raw-byte SHA-256, and gives the file and digest
    to :func:`audit_blind_functional_validity`.
    """

    if not str(bank_id).strip():
        raise BlindFunctionalValidityError("bank_id_must_be_nonempty")
    if (
        not isinstance(minimum_oracle_cases_per_tool, int)
        or isinstance(minimum_oracle_cases_per_tool, bool)
        or minimum_oracle_cases_per_tool < 1
    ):
        raise BlindFunctionalValidityError(
            "minimum_oracle_cases_per_tool_must_be_positive"
        )
    entries = _active_entries(registry_dir)
    snapshot = _snapshot_registry(registry_dir)
    if snapshot.errors or snapshot.manifest_sha256 is None:
        raise BlindFunctionalValidityError("registry_snapshot_invalid")
    payload: dict[str, Any] = {
        "schema_version": CASE_BANK_SCHEMA_VERSION,
        "bank_id": str(bank_id).strip(),
        "endpoint": ENDPOINT_NAME,
        "construction_method": CONSTRUCTION_METHOD,
        "blindness_protocol": {
            "authoring_view": "public_tool_specification_only",
            "generated_implementation_excluded": True,
            "admission_examples_excluded": True,
            "execution_results_excluded_until_bank_lock": True,
        },
        "minimum_oracle_cases_per_tool": minimum_oracle_cases_per_tool,
        "case_schema_notes": {
            "exact_output": ("oracle must be {'output': <exact expected output>}"),
            "native_action_oracle": (
                "oracle must be {'native_action': null} for an abstention or "
                "{'native_action': {'name': <approved native name>, "
                "'arguments': <exact kwargs>}} for an action"
            ),
            "provenance": (
                "Record an independent, human-readable source for each oracle; "
                "admission examples are forbidden."
            ),
        },
        "registry_binding": {
            "registry_manifest_sha256": snapshot.manifest_sha256,
            "active_tool_count": len(entries),
            "active_tool_names_sha256": _json_sha256(list(entries)),
        },
        "tools": {
            name: {
                "tool_version": entry.version,
                "tool_code_sha256": entry.stored_code_hash
                or code_hash(entry.tool.code),
                "tool_spec_sha256": _tool_spec_sha256(entry),
                "public_spec": entry.tool.spec.to_json(),
                "cases": [],
            }
            for name, entry in entries.items()
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return payload


def _require_exact_keys(
    payload: dict[str, Any], expected: set[str], *, label: str
) -> None:
    if set(payload) != expected:
        raise BlindFunctionalValidityError(f"{label}_fields_invalid")


def _load_case_bank(path: Path, expected_sha256: str) -> tuple[dict[str, Any], str]:
    if not _SHA256_RE.fullmatch(str(expected_sha256)):
        raise BlindFunctionalValidityError("case_bank_expected_sha256_invalid")
    if path.is_symlink():
        raise BlindFunctionalValidityError("case_bank_symlink_forbidden")
    if not path.is_file():
        raise BlindFunctionalValidityError("case_bank_missing")
    observed_sha256 = file_sha256(path)
    if observed_sha256 != expected_sha256:
        raise BlindFunctionalValidityError("case_bank_sha256_mismatch")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BlindFunctionalValidityError("case_bank_malformed_json") from exc
    if not isinstance(payload, dict):
        raise BlindFunctionalValidityError("case_bank_must_be_object")
    # Re-encoding with allow_nan=False detects NaN/Infinity accepted by Python's
    # permissive JSON parser.
    _canonical_json_bytes(payload)
    return payload, observed_sha256


def _validate_case_bank_shape(payload: dict[str, Any]) -> None:
    _require_exact_keys(
        payload,
        {
            "schema_version",
            "bank_id",
            "endpoint",
            "construction_method",
            "blindness_protocol",
            "minimum_oracle_cases_per_tool",
            "case_schema_notes",
            "registry_binding",
            "tools",
        },
        label="case_bank",
    )
    if payload.get("schema_version") != CASE_BANK_SCHEMA_VERSION:
        raise BlindFunctionalValidityError("case_bank_schema_version_invalid")
    if not isinstance(payload.get("bank_id"), str) or not payload["bank_id"].strip():
        raise BlindFunctionalValidityError("case_bank_id_invalid")
    if payload.get("endpoint") != ENDPOINT_NAME:
        raise BlindFunctionalValidityError("case_bank_endpoint_invalid")
    if payload.get("construction_method") != CONSTRUCTION_METHOD:
        raise BlindFunctionalValidityError("case_bank_construction_method_invalid")
    blindness = payload.get("blindness_protocol")
    if not isinstance(blindness, dict):
        raise BlindFunctionalValidityError("blindness_protocol_invalid")
    _require_exact_keys(
        blindness,
        {
            "authoring_view",
            "generated_implementation_excluded",
            "admission_examples_excluded",
            "execution_results_excluded_until_bank_lock",
        },
        label="blindness_protocol",
    )
    if blindness != {
        "authoring_view": "public_tool_specification_only",
        "generated_implementation_excluded": True,
        "admission_examples_excluded": True,
        "execution_results_excluded_until_bank_lock": True,
    }:
        raise BlindFunctionalValidityError("blindness_protocol_not_strict")
    minimum = payload.get("minimum_oracle_cases_per_tool")
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
        raise BlindFunctionalValidityError("minimum_oracle_cases_invalid")
    if not isinstance(payload.get("case_schema_notes"), dict):
        raise BlindFunctionalValidityError("case_schema_notes_invalid")
    binding = payload.get("registry_binding")
    if not isinstance(binding, dict):
        raise BlindFunctionalValidityError("registry_binding_invalid")
    _require_exact_keys(
        binding,
        {
            "registry_manifest_sha256",
            "active_tool_count",
            "active_tool_names_sha256",
        },
        label="registry_binding",
    )
    if not _SHA256_RE.fullmatch(str(binding.get("registry_manifest_sha256") or "")):
        raise BlindFunctionalValidityError("registry_binding_manifest_hash_invalid")
    active_count = binding.get("active_tool_count")
    if (
        not isinstance(active_count, int)
        or isinstance(active_count, bool)
        or active_count < 0
    ):
        raise BlindFunctionalValidityError("registry_binding_active_count_invalid")
    if not _SHA256_RE.fullmatch(str(binding.get("active_tool_names_sha256") or "")):
        raise BlindFunctionalValidityError("registry_binding_names_hash_invalid")
    if not isinstance(payload.get("tools"), dict):
        raise BlindFunctionalValidityError("case_bank_tools_invalid")


def _validate_tool_bank_shape(tool_name: str, payload: Any) -> None:
    if not isinstance(payload, dict):
        raise BlindFunctionalValidityError(f"tool_bank_invalid:{tool_name}")
    _require_exact_keys(
        payload,
        {
            "tool_version",
            "tool_code_sha256",
            "tool_spec_sha256",
            "public_spec",
            "cases",
        },
        label=f"tool_bank:{tool_name}",
    )
    if not isinstance(payload.get("cases"), list):
        raise BlindFunctionalValidityError(f"tool_cases_invalid:{tool_name}")
    version = payload.get("tool_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise BlindFunctionalValidityError(f"tool_version_invalid:{tool_name}")
    if not isinstance(payload.get("public_spec"), dict):
        raise BlindFunctionalValidityError(f"tool_public_spec_invalid:{tool_name}")
    for digest_field in ("tool_code_sha256", "tool_spec_sha256"):
        if not _SHA256_RE.fullmatch(str(payload.get(digest_field) or "")):
            raise BlindFunctionalValidityError(
                f"tool_binding_hash_invalid:{tool_name}:{digest_field}"
            )


def _validate_case_shape(tool_name: str, case: Any) -> None:
    if not isinstance(case, dict):
        raise BlindFunctionalValidityError(f"case_invalid:{tool_name}")
    _require_exact_keys(
        case,
        {"case_id", "case_type", "inputs", "oracle", "provenance"},
        label=f"case:{tool_name}",
    )
    case_id = case.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        raise BlindFunctionalValidityError(f"case_id_invalid:{tool_name}")
    case_type = case.get("case_type")
    if case_type not in _CASE_TYPES:
        raise BlindFunctionalValidityError(f"case_type_invalid:{tool_name}:{case_id}")
    if not isinstance(case.get("inputs"), dict):
        raise BlindFunctionalValidityError(f"case_inputs_invalid:{tool_name}:{case_id}")
    provenance = case.get("provenance")
    if not isinstance(provenance, str) or len(provenance.strip()) < 8:
        raise BlindFunctionalValidityError(
            f"case_provenance_invalid:{tool_name}:{case_id}"
        )
    oracle = case.get("oracle")
    if not isinstance(oracle, dict):
        raise BlindFunctionalValidityError(f"case_oracle_invalid:{tool_name}:{case_id}")
    if case_type == "exact_output":
        _require_exact_keys(oracle, {"output"}, label=f"oracle:{tool_name}:{case_id}")
    else:
        _require_exact_keys(
            oracle, {"native_action"}, label=f"oracle:{tool_name}:{case_id}"
        )
        action = oracle["native_action"]
        if action is not None:
            if not isinstance(action, dict):
                raise BlindFunctionalValidityError(
                    f"native_action_oracle_invalid:{tool_name}:{case_id}"
                )
            _require_exact_keys(
                action,
                {"name", "arguments"},
                label=f"native_action_oracle:{tool_name}:{case_id}",
            )
            if action.get("name") not in COMPLETE_TOOLS_NATIVE_NAMES or not isinstance(
                action.get("arguments"), dict
            ):
                raise BlindFunctionalValidityError(
                    f"native_action_oracle_invalid:{tool_name}:{case_id}"
                )
    _canonical_json_bytes(case)


def _native_call_names(code: str) -> tuple[str, ...]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ()
    return tuple(
        sorted(
            {
                node.func.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in COMPLETE_TOOLS_NATIVE_NAMES
            }
        )
    )


def _native_calls_inside_loops(code: str) -> tuple[str, ...]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ()
    loop_nodes = (ast.For, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
    names: set[str] = set()
    for loop in (node for node in ast.walk(tree) if isinstance(node, loop_nodes)):
        for node in ast.walk(loop):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in COMPLETE_TOOLS_NATIVE_NAMES
            ):
                names.add(node.func.id)
    return tuple(sorted(names))


def _static_errors(tool: GeneratedTool) -> tuple[str, ...]:
    errors: list[str] = []
    safety = check_ast_safety(tool.code)
    errors.extend(f"ast_safety:{error}" for error in safety.errors)
    native_names = _native_call_names(tool.code)
    if bool(tool.spec.native_action_delegation) and not native_action_spec_enabled(
        tool.spec
    ):
        errors.append("native_action_spec_not_eligible")
    if native_names and not native_action_tool_enabled(tool):
        errors.extend(
            f"native_action_call_not_permitted:{name}" for name in native_names
        )
    if native_action_tool_enabled(tool):
        declared = set(native_action_names_for_tool(tool))
        errors.extend(
            f"native_action_call_not_declared:{name}"
            for name in native_names
            if name not in declared
        )
        errors.extend(
            f"native_action_in_loop:{name}"
            for name in _native_calls_inside_loops(tool.code)
        )
    # Compile with harmless stubs for native-action tools.  This is a static
    # schema/global-name check; no generated function is called here.
    overrides = (
        _recording_native_tools([]) if native_action_tool_enabled(tool) else None
    )
    schema = compile_generated_tool(tool, native_tool_overrides=overrides)
    errors.extend(f"schema:{error}" for error in schema.errors)
    return tuple(sorted(set(errors)))


def _recording_native_tools(
    calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]],
) -> dict[str, Callable[..., Any]]:
    tools: dict[str, Callable[..., Any]] = {}
    for native_name in COMPLETE_TOOLS_NATIVE_NAMES:

        def record(
            *args: Any,
            _native_name: str = native_name,
            **kwargs: Any,
        ) -> Any:
            calls.append((_native_name, args, dict(kwargs)))
            if _native_name in {
                "add_contact",
                "add_reminder",
                "send_message_with_phone_number",
            }:
                return f"blind-audit-{_native_name}-id"
            return None

        record.__name__ = native_name
        tools[native_name] = record
    return tools


def _normalized_native_arguments(
    name: str, args: tuple[Any, ...], kwargs: dict[str, Any]
) -> dict[str, Any]:
    function = native_side_effect_tools()[name]
    bound = inspect.signature(function).bind(*args, **kwargs)
    bound.apply_defaults()
    return dict(bound.arguments)


def _is_strict_json_value(value: Any) -> bool:
    try:
        _canonical_json_bytes(value)
    except BlindFunctionalValidityError:
        return False
    return True


_EXECUTION_UNAVAILABLE = object()


def _run_function_twice(
    function: Callable[..., Any], inputs: dict[str, Any]
) -> tuple[Any, Any, list[str]]:
    errors: list[str] = []
    first_inputs = copy.deepcopy(inputs)
    second_inputs = copy.deepcopy(inputs)
    before_first = copy.deepcopy(first_inputs)
    before_second = copy.deepcopy(second_inputs)
    try:
        first = function(**first_inputs)
    except Exception as exc:
        return (
            _EXECUTION_UNAVAILABLE,
            _EXECUTION_UNAVAILABLE,
            [f"first_execution_error:{type(exc).__name__}:{exc}"],
        )
    if first_inputs != before_first:
        errors.append("first_execution_mutated_inputs")
    try:
        second = function(**second_inputs)
    except Exception as exc:
        return (
            first,
            _EXECUTION_UNAVAILABLE,
            [
                *errors,
                f"second_execution_error:{type(exc).__name__}:{exc}",
            ],
        )
    if second_inputs != before_second:
        errors.append("second_execution_mutated_inputs")
    if first != second:
        errors.append("raw_output_nondeterministic")
    if not _is_strict_json_value(first):
        errors.append("output_not_strict_json")
    return first, second, errors


def _execute_exact_output_case(
    tool: GeneratedTool, case: dict[str, Any]
) -> tuple[str, ...]:
    if native_action_tool_enabled(tool):
        return ("exact_output_case_for_native_action_tool",)
    schema = compile_generated_tool(tool)
    if not schema.valid or schema.function is None:
        return tuple(f"schema:{error}" for error in schema.errors)
    raw, replay, errors = _run_function_twice(schema.function, case["inputs"])
    if errors or replay is _EXECUTION_UNAVAILABLE:
        return tuple(errors)
    try:
        actual = normalize_generated_tool_output(tool, raw, inputs=case["inputs"])
        repeated = normalize_generated_tool_output(tool, replay, inputs=case["inputs"])
        expected = normalize_generated_tool_output(
            tool, case["oracle"]["output"], inputs=case["inputs"]
        )
    except Exception as exc:
        errors.append(f"normalization_error:{type(exc).__name__}:{exc}")
        return tuple(errors)
    if actual != repeated:
        errors.append("normalized_output_nondeterministic")
    if actual != expected:
        errors.append(f"exact_output_mismatch:actual={actual!r}:expected={expected!r}")
    return tuple(errors)


def _native_result_errors(
    result: Any,
    *,
    expected_action: dict[str, Any] | None,
) -> list[str]:
    if not isinstance(result, dict) or not _is_strict_json_value(result):
        return ["native_result_must_be_strict_json_object"]
    status = str(result.get("status") or "").strip().lower()
    confirmation = str(result.get("confirmation") or "").strip()
    abstain_reason = str(result.get("abstain_reason") or "").strip()
    reported_action = str(result.get("native_action") or "").strip()
    errors: list[str] = []
    required_fields = {
        "status",
        "confirmation",
        "abstain_reason",
        "native_action",
        "native_result",
    }
    missing_fields = sorted(required_fields - set(result))
    errors.extend(f"native_result_field_missing:{field}" for field in missing_fields)
    if expected_action is None:
        if status != "abstain":
            errors.append("native_abstention_status_missing")
        if confirmation:
            errors.append("native_abstention_confirmation_present")
        if not abstain_reason:
            errors.append("native_abstention_reason_missing")
        if reported_action:
            errors.append("native_abstention_action_present")
        if result.get("native_result") is not None:
            errors.append("native_abstention_result_present")
    else:
        expected_name = str(expected_action["name"])
        if status != "success":
            errors.append("native_success_status_missing")
        if not confirmation:
            errors.append("native_success_confirmation_missing")
        if abstain_reason:
            errors.append("native_success_abstain_reason_present")
        if reported_action != expected_name:
            errors.append(
                f"native_result_action_mismatch:{reported_action}!={expected_name}"
            )
        if "native_result" not in result:
            errors.append("native_success_result_field_missing")
    return errors


def _execute_native_action_case(
    tool: GeneratedTool, case: dict[str, Any]
) -> tuple[str, ...]:
    if not native_action_tool_enabled(tool):
        return ("native_action_case_for_non_native_tool",)
    calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
    schema = compile_generated_tool(
        tool, native_tool_overrides=_recording_native_tools(calls)
    )
    if not schema.valid or schema.function is None:
        return tuple(f"schema:{error}" for error in schema.errors)
    raw, replay, errors = _run_function_twice(schema.function, case["inputs"])
    expected_action = case["oracle"]["native_action"]
    if replay is not _EXECUTION_UNAVAILABLE:
        errors.extend(_native_result_errors(raw, expected_action=expected_action))
        errors.extend(
            f"replay_{error}"
            for error in _native_result_errors(replay, expected_action=expected_action)
        )
    expected_call_count = 0 if expected_action is None else 2
    if len(calls) != expected_call_count:
        errors.append(f"native_action_call_count:{len(calls)}!={expected_call_count}")
        return tuple(errors)
    if expected_action is None:
        return tuple(errors)
    expected_name = str(expected_action["name"])
    expected_arguments = dict(expected_action["arguments"])
    try:
        normalized_expected = _normalized_native_arguments(
            expected_name, (), expected_arguments
        )
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"native_oracle_arguments_invalid:{type(exc).__name__}:{exc}")
        return tuple(errors)
    normalized_calls: list[tuple[str, dict[str, Any]]] = []
    for actual_name, args, kwargs in calls:
        if actual_name != expected_name:
            errors.append(f"native_action_name:{actual_name}!={expected_name}")
            continue
        try:
            normalized = _normalized_native_arguments(actual_name, args, kwargs)
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"native_action_arguments_invalid:{type(exc).__name__}:{exc}")
            continue
        normalized_calls.append((actual_name, normalized))
        if normalized != normalized_expected:
            errors.append(
                "native_action_arguments_mismatch:"
                f"actual={normalized!r}:expected={normalized_expected!r}"
            )
    if len(normalized_calls) == 2 and normalized_calls[0] != normalized_calls[1]:
        errors.append("native_action_nondeterministic")
    return tuple(errors)


def _clopper_pearson(
    successes: int, trials: int, confidence_level: float
) -> dict[str, Any]:
    if trials < 0 or successes < 0 or successes > trials:
        raise BlindFunctionalValidityError("binomial_counts_invalid")
    if not 0.0 < confidence_level < 1.0:
        raise BlindFunctionalValidityError("confidence_level_invalid")
    if trials == 0:
        return {
            "method": "clopper_pearson_exact_two_sided",
            "confidence_level": confidence_level,
            "lower_bound": None,
            "upper_bound": None,
        }
    alpha = 1.0 - confidence_level
    lower = (
        0.0
        if successes == 0
        else float(beta.ppf(alpha / 2.0, successes, trials - successes + 1))
    )
    upper = (
        1.0
        if successes == trials
        else float(beta.ppf(1.0 - alpha / 2.0, successes + 1, trials - successes))
    )
    return {
        "method": "clopper_pearson_exact_two_sided",
        "confidence_level": confidence_level,
        "lower_bound": lower,
        "upper_bound": upper,
    }


def _fatal_report(
    *,
    fatal_error: str,
    before: RegistrySnapshot,
    after: RegistrySnapshot,
    expected_case_bank_sha256: str,
    observed_case_bank_sha256: str | None,
    confidence_level: float,
    active_tool_names: tuple[str, ...] = (),
) -> dict[str, Any]:
    immutable = before.tree_sha256 == after.tree_sha256 and before.files == after.files
    return {
        "schema_version": AUDIT_REPORT_SCHEMA_VERSION,
        "report_type": "blind_functional_validity_audit",
        "endpoint": ENDPOINT_NAME,
        "status": "invalid",
        "fatal_error": fatal_error,
        "case_bank": {
            "expected_sha256": expected_case_bank_sha256,
            "observed_sha256": observed_case_bank_sha256,
            "hash_verified": observed_case_bank_sha256 == expected_case_bank_sha256,
        },
        "registry_immutability": {
            "before_tree_sha256": before.tree_sha256,
            "after_tree_sha256": after.tree_sha256,
            "before_manifest_sha256": before.manifest_sha256,
            "after_manifest_sha256": after.manifest_sha256,
            "immutable": immutable,
            "snapshot_errors": sorted(set((*before.errors, *after.errors))),
        },
        "endpoint_result": {
            "estimable": False,
            "active_tool_count": len(active_tool_names),
            "passing_tool_count": 0,
            "tool_weighted_validity_rate": None,
            "clopper_pearson": _clopper_pearson(
                0, len(active_tool_names), confidence_level
            ),
        },
        "active_tools_in_denominator": list(active_tool_names),
        "tools": {},
    }


def audit_blind_functional_validity(
    *,
    registry_dir: Path,
    case_bank_path: Path,
    expected_case_bank_sha256: str,
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    """Run the fail-closed post-freeze H1 audit and return its JSON report."""

    if not 0.0 < confidence_level < 1.0 or not math.isfinite(confidence_level):
        raise BlindFunctionalValidityError("confidence_level_invalid")
    before = _snapshot_registry(registry_dir)
    observed_case_bank_sha256: str | None = None
    entries: dict[str, RegistryEntry] = {}
    try:
        if before.errors or before.manifest_sha256 is None:
            raise BlindFunctionalValidityError("registry_snapshot_invalid")
        try:
            entries = _active_entries(registry_dir)
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise BlindFunctionalValidityError("registry_manifest_invalid") from exc
        case_bank, observed_case_bank_sha256 = _load_case_bank(
            case_bank_path, expected_case_bank_sha256
        )
        _validate_case_bank_shape(case_bank)
        tool_banks = case_bank["tools"]
        for name, payload in tool_banks.items():
            if not isinstance(name, str) or not name.strip():
                raise BlindFunctionalValidityError("case_bank_tool_name_invalid")
            _validate_tool_bank_shape(name, payload)
            case_ids: set[str] = set()
            for case in payload["cases"]:
                _validate_case_shape(name, case)
                case_id = str(case["case_id"])
                if case_id in case_ids:
                    raise BlindFunctionalValidityError(
                        f"duplicate_case_id:{name}:{case_id}"
                    )
                case_ids.add(case_id)

        binding = case_bank["registry_binding"]
        global_errors: list[str] = []
        if before.errors:
            global_errors.extend(before.errors)
        if before.manifest_sha256 is None:
            global_errors.append("registry_manifest_missing")
        if binding["registry_manifest_sha256"] != before.manifest_sha256:
            global_errors.append("case_bank_registry_manifest_hash_mismatch")
        if binding["active_tool_count"] != len(entries):
            global_errors.append("case_bank_active_tool_count_mismatch")
        if binding["active_tool_names_sha256"] != _json_sha256(list(entries)):
            global_errors.append("case_bank_active_tool_names_hash_mismatch")
        missing_tools = sorted(set(entries) - set(tool_banks))
        unexpected_tools = sorted(set(tool_banks) - set(entries))
        if missing_tools:
            global_errors.append("case_bank_missing_active_tools")
        if unexpected_tools:
            global_errors.append("case_bank_contains_nonactive_tools")

        resolved, contract_failures = ValidationContractBindingStore(
            registry_dir
        ).restore(entries)
        minimum_cases = int(case_bank["minimum_oracle_cases_per_tool"])
        tool_results: dict[str, dict[str, Any]] = {}
        total_cases = 0
        passing_cases = 0
        admission_overlap_count = 0

        for name, entry in entries.items():
            integrity_errors: list[str] = []
            if name != entry.tool.spec.tool_name:
                integrity_errors.append("registry_tool_name_mismatch")
            if not entry.validation.accepted:
                integrity_errors.append("registry_entry_not_accepted")
            if not entry.code_hash_verified:
                integrity_errors.append("registry_code_hash_mismatch")
            if not has_current_validation_proof(entry):
                integrity_errors.append("current_validation_proof_missing")
            bank = tool_banks.get(name)
            cases: list[dict[str, Any]] = []
            if bank is None:
                integrity_errors.append("active_tool_missing_from_case_bank")
            else:
                if bank["tool_version"] != entry.version:
                    integrity_errors.append("case_bank_tool_version_mismatch")
                if bank["tool_code_sha256"] != code_hash(entry.tool.code):
                    integrity_errors.append("case_bank_tool_code_hash_mismatch")
                if bank["tool_spec_sha256"] != _tool_spec_sha256(entry):
                    integrity_errors.append("case_bank_tool_spec_hash_mismatch")
                if bank["public_spec"] != entry.tool.spec.to_json():
                    integrity_errors.append("case_bank_public_spec_mismatch")
                cases = list(bank["cases"])
                if len(cases) < minimum_cases:
                    integrity_errors.append(
                        f"insufficient_oracle_cases:{len(cases)}<{minimum_cases}"
                    )

            contract = resolved.get(name)
            admission_input_hashes: set[str] = set()
            if contract is None:
                integrity_errors.append(
                    f"admission_contract_unverifiable:"
                    f"{contract_failures.get(name, 'binding_missing')}"
                )
            else:
                admission_input_hashes = {
                    _json_sha256(example.inputs)
                    for example in contract.observation.validation_examples
                }

            seen_case_input_hashes: set[str] = set()
            case_results: list[dict[str, Any]] = []
            positive_native_cases = 0
            negative_native_cases = 0
            for case in cases:
                case_errors: list[str] = []
                input_hash = _json_sha256(case["inputs"])
                if input_hash in seen_case_input_hashes:
                    case_errors.append("duplicate_case_inputs")
                seen_case_input_hashes.add(input_hash)
                if input_hash in admission_input_hashes:
                    case_errors.append("exact_admission_input_overlap")
                    integrity_errors.append(
                        f"exact_admission_input_overlap:{case['case_id']}"
                    )
                    admission_overlap_count += 1
                if case["case_type"] == "exact_output":
                    case_errors.extend(_execute_exact_output_case(entry.tool, case))
                else:
                    action = case["oracle"]["native_action"]
                    if action is None:
                        negative_native_cases += 1
                    else:
                        positive_native_cases += 1
                    case_errors.extend(_execute_native_action_case(entry.tool, case))
                case_passed = not case_errors
                total_cases += 1
                passing_cases += int(case_passed)
                case_results.append(
                    {
                        "case_id": case["case_id"],
                        "case_type": case["case_type"],
                        "provenance": case["provenance"],
                        "input_sha256": input_hash,
                        "passed": case_passed,
                        "errors": sorted(set(case_errors)),
                    }
                )

            static_errors = list(_static_errors(entry.tool))
            if native_action_tool_enabled(entry.tool):
                if positive_native_cases == 0:
                    static_errors.append("native_action_positive_oracle_missing")
                if negative_native_cases == 0:
                    static_errors.append("native_action_abstention_oracle_missing")
            elif any(case["case_type"] == "native_action_oracle" for case in cases):
                static_errors.append("native_action_oracle_for_non_native_tool")
            else:
                if any(case["case_type"] != "exact_output" for case in cases):
                    static_errors.append("exact_output_oracle_missing")

            passed = (
                not global_errors
                and not integrity_errors
                and not static_errors
                and len(cases) >= minimum_cases
                and bool(cases)
                and all(result["passed"] for result in case_results)
            )
            tool_results[name] = {
                "tool_version": entry.version,
                "tool_code_sha256": code_hash(entry.tool.code),
                "family": entry.tool.spec.family.value,
                "passed": passed,
                "case_count": len(cases),
                "passing_case_count": sum(
                    int(result["passed"]) for result in case_results
                ),
                "integrity_errors": sorted(set(integrity_errors)),
                "static_safety_errors": sorted(set(static_errors)),
                "case_results": case_results,
            }
    except BlindFunctionalValidityError as exc:
        after = _snapshot_registry(registry_dir)
        return _fatal_report(
            fatal_error=str(exc),
            before=before,
            after=after,
            expected_case_bank_sha256=expected_case_bank_sha256,
            observed_case_bank_sha256=observed_case_bank_sha256,
            confidence_level=confidence_level,
            active_tool_names=tuple(entries),
        )

    after = _snapshot_registry(registry_dir)
    immutable = before.tree_sha256 == after.tree_sha256 and before.files == after.files
    if not immutable:
        global_errors.append("registry_changed_during_audit")
    if after.errors:
        global_errors.extend(after.errors)
    # Registry immutability is a tool-level gate for the endpoint.  Recompute
    # pass values after the post-execution snapshot so no tool can pass when the
    # supposedly frozen registry changed during evaluation.
    integrity_valid = not global_errors and all(
        not result["integrity_errors"] for result in tool_results.values()
    )
    if not integrity_valid:
        for result in tool_results.values():
            result["passed"] = False

    active_tool_count = len(entries)
    passing_tool_count = sum(int(result["passed"]) for result in tool_results.values())
    estimable = active_tool_count > 0 and integrity_valid
    rate = passing_tool_count / active_tool_count if active_tool_count else None
    report_status = "complete" if estimable else "invalid"
    return {
        "schema_version": AUDIT_REPORT_SCHEMA_VERSION,
        "report_type": "blind_functional_validity_audit",
        "endpoint": ENDPOINT_NAME,
        "endpoint_unit": "active_nonretired_registry_tool",
        "pass_rule": "tool_passes_only_if_all_integrity_static_and_oracle_checks_pass",
        "status": report_status,
        "fatal_error": None,
        "bank_id": case_bank["bank_id"],
        "construction_method": case_bank["construction_method"],
        "case_bank": {
            "expected_sha256": expected_case_bank_sha256,
            "observed_sha256": observed_case_bank_sha256,
            "hash_verified": observed_case_bank_sha256 == expected_case_bank_sha256,
        },
        "registry_immutability": {
            "before_tree_sha256": before.tree_sha256,
            "after_tree_sha256": after.tree_sha256,
            "before_manifest_sha256": before.manifest_sha256,
            "after_manifest_sha256": after.manifest_sha256,
            "immutable": immutable,
            "snapshot_errors": sorted(set((*before.errors, *after.errors))),
        },
        "integrity": {
            "valid": integrity_valid,
            "errors": sorted(set(global_errors)),
            "missing_active_tools": missing_tools,
            "unexpected_nonactive_tools": unexpected_tools,
            "admission_input_overlap_count": admission_overlap_count,
            "active_tools_in_denominator": list(entries),
        },
        "endpoint_result": {
            "estimable": estimable,
            "active_tool_count": active_tool_count,
            "passing_tool_count": passing_tool_count,
            "tool_weighted_validity_rate": rate,
            "case_count": total_cases,
            "passing_case_count": passing_cases,
            "clopper_pearson": _clopper_pearson(
                passing_tool_count, active_tool_count, confidence_level
            ),
        },
        "tools": tool_results,
    }


def write_audit_report(report: dict[str, Any], output_path: Path) -> None:
    """Atomically write one audit report outside the frozen registry."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, output_path)
