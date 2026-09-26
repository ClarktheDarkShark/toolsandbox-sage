"""Real-boundary actor replay through ``ConfigurableOpenAIAgent``.

Every case invokes the production ``model_inference`` implementation.  The
only substituted component is ``chat.completions.create``: a deterministic fake
records the exact API kwargs and returns a small completion object.  Internal
policy functions are wrapped only to record call order and return values; their
real implementations still execute.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable


_FIXTURE_PATH = Path(__file__).resolve().with_name("actor_fixture.py")
_FIXTURE_SPEC = importlib.util.spec_from_file_location(
    "_sage_actor_replay_fixture", _FIXTURE_PATH
)
if _FIXTURE_SPEC is None or _FIXTURE_SPEC.loader is None:
    raise RuntimeError(f"Cannot load actor replay fixture: {_FIXTURE_PATH}")
_FIXTURE_MODULE = importlib.util.module_from_spec(_FIXTURE_SPEC)
_FIXTURE_SPEC.loader.exec_module(_FIXTURE_MODULE)
actor_cases = _FIXTURE_MODULE.actor_cases
_FIXTURE_MANIFEST_PATH = _FIXTURE_PATH.with_suffix(".manifest.json")


CHOICE_FUNCTIONS = (
    "_helper_answer_completion_tool_choice",
    "_device_status_completion_tool_choice",
    "_shared_task_closure_tool_choice",
    "_generated_downstream_original_tool_choice",
    "_state_action_planner_tool_choice",
    "_reminder_recency_workflow_tool_choice",
    "_relationship_batch_generated_tool_choice",
    "_reminder_location_batch_tool_choice",
    "_generated_tool_continuation_choice",
    "_new_user_turn_generated_tool_choice",
    "_first_attempt_generated_tool_choice",
)
EAGER_CHOICE_PREFIX = CHOICE_FUNCTIONS[:4]


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted((_jsonable(item) for item in value), key=repr)
    if hasattr(value, "__dict__"):
        return {
            str(key): _jsonable(item)
            for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    return str(value)


def _ordered_key_paths(value: Any, path: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        rows.append({"path": path or "/", "keys": [str(key) for key in value]})
        for key, item in value.items():
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            rows.extend(_ordered_key_paths(item, f"{path}/{escaped}"))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            rows.extend(_ordered_key_paths(item, f"{path}/{index}"))
    return rows


def _exact(value: Any) -> dict[str, Any]:
    jsonable = _jsonable(value)
    raw = json.dumps(jsonable, ensure_ascii=False, separators=(",", ":"))
    return {
        "value": jsonable,
        "object_key_order": _ordered_key_paths(value),
        "raw_json": raw,
        "raw_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    }


def _wire_value(value: Any, actor: Any) -> Any:
    if value is actor.NOT_GIVEN:
        return "<OPENAI_NOT_GIVEN>"
    return _jsonable(value)


def verify_actor_fixture_bytes(payload: bytes, manifest: dict[str, Any]) -> None:
    """Reject any fixture byte or declared-size change."""

    expected_size = int(manifest["source_byte_count"])
    expected_sha = str(manifest["source_sha256"])
    actual_sha = hashlib.sha256(payload).hexdigest()
    if len(payload) != expected_size:
        raise ValueError(
            f"Actor fixture byte count changed: expected {expected_size}, got {len(payload)}"
        )
    if actual_sha != expected_sha:
        raise ValueError(
            f"Actor fixture SHA-256 changed: expected {expected_sha}, got {actual_sha}"
        )


def _source_policy_inventory(root: Path) -> dict[str, Any]:
    path = root / "src" / "sage_ts" / "adapters" / "openai_toolsandbox_roles.py"
    source = path.read_text(encoding="utf-8")
    module = ast.parse(source)
    functions = {
        node.name: node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    composer = functions["_with_selector_actor_policy"]
    direct = {
        node.func.id
        for node in ast.walk(composer)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in functions
        and "policy_message" in node.func.id
    }
    reachable: set[str] = set()
    pending = list(direct)
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        for node in ast.walk(functions[name]):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in functions
                and "policy_message" in node.func.id
                and node.func.id not in reachable
            ):
                pending.append(node.func.id)
    nested = reachable - direct
    return {
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "direct_count": len(direct),
        "direct": sorted(direct, key=lambda name: functions[name].lineno),
        "nested_count": len(nested),
        "nested": sorted(nested, key=lambda name: functions[name].lineno),
        "reachable_count": len(reachable),
        "reachable": sorted(reachable, key=lambda name: functions[name].lineno),
    }


class _FixtureContext:
    def __init__(self, runtime_tools: dict[str, dict[str, Any]]) -> None:
        self.name_to_tool = {
            name: SimpleNamespace(
                **{
                    key: tuple(value) if isinstance(value, list) else value
                    for key, value in fields.items()
                }
            )
            for name, fields in runtime_tools.items()
        }

    @staticmethod
    def get_execution_facing_tool_name(name: str) -> str:
        return name.split(".", 1)[1] if name.startswith("functions.") else name

    @staticmethod
    def get_agent_facing_tool_name(name: str) -> str:
        return name


def _completion(*, mode: str) -> Any:
    if mode == "safe_abstention_tool_call":
        function = SimpleNamespace(
            name="prepare_safe_action_or_abstain",
            arguments=json.dumps(
                {
                    "user_request": "Remove the contact with phone number +15550100.",
                    "requested_action": "contact_removal",
                    "target_identifier": "",
                    "required_original_tools": ["contact_lookup", "contact_removal"],
                    "available_original_tools": ["invented_capability"],
                    "visible_records_count": 0,
                },
                separators=(",", ":"),
            ),
        )
        message = SimpleNamespace(
            content=None,
            tool_calls=[
                SimpleNamespace(
                    id="fixture-safe-call",
                    type="function",
                    function=function,
                )
            ],
        )
    else:
        message = SimpleNamespace(content="fixture response", tool_calls=None)
    return SimpleNamespace(
        id="fixture-completion",
        choices=[SimpleNamespace(index=0, message=message)],
        usage=SimpleNamespace(
            prompt_tokens=11,
            completion_tokens=3,
            total_tokens=14,
            prompt_tokens_details=SimpleNamespace(cached_tokens=2),
        ),
    )


class _FakeCreate:
    def __init__(self, *, actor: Any, mode: str) -> None:
        self.actor = actor
        self.mode = mode
        self.calls: list[dict[str, Any]] = []
        self.responses: list[Any] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(
            {
                "kwargs": {
                    key: _wire_value(value, self.actor) for key, value in kwargs.items()
                },
                "kwargs_order": list(kwargs),
                "named": "tool_choice" in kwargs,
            }
        )
        if self.mode == "transient_named_then_natural" and "tool_choice" in kwargs:
            import httpx

            raise self.actor.APIConnectionError(
                request=httpx.Request("POST", "https://fixture.invalid/chat")
            )
        response = _completion(mode=self.mode)
        self.responses.append(response)
        return response


def _call_builder(
    function: Callable[..., Any], messages: list[dict[str, Any]], tools: Any
) -> Any:
    parameters = tuple(inspect.signature(function).parameters)
    if len(parameters) == 1:
        return function(messages)
    return function(messages, tools)


def _sentinel_counts(messages: Any, actor: Any) -> dict[str, int]:
    contents = [
        str(message.get("content", ""))
        for message in messages
        if isinstance(message, dict)
    ]
    sentinels = {
        name: value
        for name, value in vars(actor).items()
        if name.endswith("_SENTINEL") and isinstance(value, str)
    }
    return {
        name: sum(content.count(value) for content in contents)
        for name, value in sorted(sentinels.items())
        if any(value in content for content in contents)
    }


def _selected_choice(calls: list[dict[str, Any]]) -> str | None:
    for call in calls:
        choice = call["kwargs"].get("tool_choice")
        if not isinstance(choice, dict):
            continue
        function = choice.get("function")
        if isinstance(function, dict) and isinstance(function.get("name"), str):
            return function["name"]
    return None


def _run_case(case: dict[str, Any], actor: Any, reachable: set[str]) -> dict[str, Any]:
    messages = copy.deepcopy(case["messages"])
    tools = (
        actor.NOT_GIVEN
        if case["tools"] == "NOT_GIVEN"
        else copy.deepcopy(case["tools"])
    )
    context = _FixtureContext(copy.deepcopy(case["runtime_tools"]))
    originals: dict[str, Any] = {}
    policy_receipts: dict[str, list[dict[str, Any]]] = {"first": [], "second": []}
    choice_receipts: dict[str, list[dict[str, Any]]] = {"first": [], "second": []}
    phase = "first"

    old_context = actor.get_current_context
    old_usage = actor.record_chat_completion_usage
    old_sleep = actor.time.sleep
    old_retry_delay = os.environ.get("SAGE_OPENAI_TRANSIENT_RETRY_DELAYS_SECONDS")
    usage: dict[str, list[dict[str, Any]]] = {"first": [], "second": []}
    actor.get_current_context = lambda: context
    actor.time.sleep = lambda _seconds: None
    os.environ["SAGE_OPENAI_TRANSIENT_RETRY_DELAYS_SECONDS"] = "0"

    direct_results: dict[str, Any] = {}
    try:
        for name in (*case["direct_positive"], *case["direct_absent"]):
            result = _call_builder(getattr(actor, name), messages, tools)
            direct_results[name] = _exact(result)
            if name in case["direct_positive"] and result is None:
                raise AssertionError(f"{case['id']}: {name} did not return a policy")
            if name in case["direct_absent"] and result is not None:
                raise AssertionError(
                    f"{case['id']}: {name} unexpectedly returned a policy"
                )

        for name in reachable:
            original = getattr(actor, name)
            originals[name] = original

            def policy_wrapper(
                *args: Any,
                __name: str = name,
                __original: Callable[..., Any] = original,
                **kwargs: Any,
            ) -> Any:
                result = __original(*args, **kwargs)
                policy_receipts[phase].append(
                    {"name": __name, "returned": _jsonable(result)}
                )
                return result

            setattr(actor, name, policy_wrapper)

        for name in CHOICE_FUNCTIONS:
            original = getattr(actor, name)
            originals[name] = original

            def choice_wrapper(
                *args: Any,
                __name: str = name,
                __original: Callable[..., Any] = original,
                **kwargs: Any,
            ) -> Any:
                result = __original(*args, **kwargs)
                choice_receipts[phase].append(
                    {"name": __name, "returned": _jsonable(result)}
                )
                return result

            setattr(actor, name, choice_wrapper)

        def record_usage(**kwargs: Any) -> None:
            active_create = first_create if phase == "first" else second_create
            usage[phase].append(
                {
                    "source": kwargs.get("source"),
                    "model": kwargs.get("model"),
                    "messages": _wire_value(kwargs.get("messages"), actor),
                    "tools": _wire_value(kwargs.get("tools"), actor),
                    "response_is_fake_success": kwargs.get("response")
                    in active_create.responses,
                }
            )

        actor.record_chat_completion_usage = record_usage
        agent = object.__new__(actor.ConfigurableOpenAIAgent)
        agent.model_name = "gpt-4o-mini"
        first_create = _FakeCreate(actor=actor, mode=case["response_mode"])
        agent.openai_client = SimpleNamespace(
            chat=SimpleNamespace(completions=first_create)
        )
        response = agent.model_inference(messages, tools)
        if not first_create.responses:
            raise AssertionError(f"{case['id']}: fake API never returned a response")
        response_identity_preserved = response is first_create.responses[-1]

        successful_calls = [
            call
            for call in first_create.calls
            if not (
                case["response_mode"] == "transient_named_then_natural"
                and call["named"]
            )
        ]
        first_prompt = successful_calls[-1]["kwargs"]["messages"]
        first_sentinels = _sentinel_counts(first_prompt, actor)

        phase = "second"
        second_create = _FakeCreate(actor=actor, mode="assistant_text")
        agent.openai_client = SimpleNamespace(
            chat=SimpleNamespace(completions=second_create)
        )
        second_response = agent.model_inference(copy.deepcopy(first_prompt), tools)
        second_prompt = second_create.calls[-1]["kwargs"]["messages"]
        second_sentinels = _sentinel_counts(second_prompt, actor)
        idempotent_prompt = first_prompt == second_prompt
        existing_sentinels_stable = all(
            second_sentinels.get(name) == count
            for name, count in first_sentinels.items()
        )
        no_duplicate_sentinels = all(count == 1 for count in second_sentinels.values())

        first_choice_names = [row["name"] for row in choice_receipts["first"]]
        eager_prefix_observed = (
            not first_choice_names
            or tuple(first_choice_names[:4]) == EAGER_CHOICE_PREFIX
        )
        if not eager_prefix_observed:
            raise AssertionError(f"{case['id']}: eager selector prefix changed")
        first_returned_choice = next(
            (
                row["returned"]
                for row in choice_receipts["first"]
                if isinstance(row["returned"], str) and row["returned"]
            ),
            None,
        )
        sent_tools = successful_calls[-1]["kwargs"].get("tools")
        sent_tool_names = (
            actor._tool_names_execution_facing(sent_tools)
            if isinstance(sent_tools, list)
            else set()
        )
        expected_named_choice = (
            first_returned_choice
            if first_returned_choice
            and actor._execution_facing_tool_name(first_returned_choice)
            in sent_tool_names
            else None
        )
        selected_named_choice = _selected_choice(first_create.calls)
        precedence_preserved = selected_named_choice == expected_named_choice
        if not precedence_preserved:
            raise AssertionError(f"{case['id']}: named-choice precedence changed")

        expected_usage_count = (
            1
            if selected_named_choice is not None
            and case["response_mode"] != "transient_named_then_natural"
            else 0
        )
        if len(usage["first"]) != expected_usage_count:
            raise AssertionError(
                f"{case['id']}: expected {expected_usage_count} named-call usage "
                f"records, got {len(usage['first'])}"
            )

        grounding: dict[str, Any] | None = None
        if case["response_mode"] == "safe_abstention_tool_call":
            arguments = json.loads(
                response.choices[0].message.tool_calls[0].function.arguments
            )
            expected = sorted(
                {
                    actor._safe_action_capability(name)
                    for name in (
                        actor._tool_names_execution_facing(tools)
                        & actor.ORIGINAL_TOOLSANDBOX_TOOL_NAMES
                    )
                }
            )
            grounding = {
                "arguments": arguments,
                "expected_available_original_tools": expected,
                "host_inventory_applied": (
                    arguments.get("available_original_tools") == expected
                ),
            }
            if not grounding["host_inventory_applied"]:
                raise AssertionError(f"{case['id']}: response grounding failed")

        transient_fallback: dict[str, Any] | None = None
        if case["response_mode"] == "transient_named_then_natural":
            transient_fallback = {
                "named_attempt_count": sum(
                    call["named"] for call in first_create.calls
                ),
                "final_attempt_is_natural": not first_create.calls[-1]["named"],
                "attempt_count": len(first_create.calls),
            }
            if not (
                transient_fallback["named_attempt_count"] >= 2
                and transient_fallback["final_attempt_is_natural"]
            ):
                raise AssertionError(
                    f"{case['id']}: transient fallback was not exercised"
                )

        return {
            "id": case["id"],
            "provenance": case["provenance"],
            "source_test": case["source_test"],
            "direct_results": direct_results,
            "original_messages": _exact(messages),
            "routed_tools": _exact(_wire_value(tools, actor)),
            "first": {
                "policy_receipts": policy_receipts["first"],
                "choice_receipts": choice_receipts["first"],
                "api_calls": _exact(first_create.calls),
                "selected_named_choice": selected_named_choice,
                "choice_precedence": {
                    "first_returned_choice": first_returned_choice,
                    "expected_named_choice_after_schema_filter": expected_named_choice,
                    "preserved": precedence_preserved,
                },
                "usage_records": _exact(usage["first"]),
                "response": _exact(response),
                "response_object_identity_preserved": response_identity_preserved,
                "sentinel_counts": first_sentinels,
            },
            "second": {
                "policy_receipts": policy_receipts["second"],
                "choice_receipts": choice_receipts["second"],
                "api_calls": _exact(second_create.calls),
                "usage_records": _exact(usage["second"]),
                "response_object_identity_preserved": (
                    second_response is second_create.responses[-1]
                ),
                "sentinel_counts": second_sentinels,
            },
            "sentinel_idempotence_characterization": {
                "exact_prompt_equal": idempotent_prompt,
                "existing_sentinels_stable": existing_sentinels_stable,
                "no_duplicate_sentinels": no_duplicate_sentinels,
                "new_second_pass_sentinels": sorted(
                    set(second_sentinels) - set(first_sentinels)
                ),
            },
            "eager_first_four_observed": eager_prefix_observed,
            "grounding": grounding,
            "transient_fallback": transient_fallback,
        }
    finally:
        for name, original in originals.items():
            setattr(actor, name, original)
        actor.get_current_context = old_context
        actor.record_chat_completion_usage = old_usage
        actor.time.sleep = old_sleep
        if old_retry_delay is None:
            os.environ.pop("SAGE_OPENAI_TRANSIENT_RETRY_DELAYS_SECONDS", None)
        else:
            os.environ["SAGE_OPENAI_TRANSIENT_RETRY_DELAYS_SECONDS"] = old_retry_delay


def probe_actor_model_inference(root: Path) -> dict[str, Any]:
    """Snapshot the real actor request path and assert complete policy coverage."""

    import sage_ts.adapters.openai_toolsandbox_roles as actor

    fixture_source = _FIXTURE_PATH.read_bytes()
    fixture_manifest = json.loads(_FIXTURE_MANIFEST_PATH.read_text(encoding="utf-8"))
    verify_actor_fixture_bytes(fixture_source, fixture_manifest)
    inventory = _source_policy_inventory(root)
    if inventory["direct_count"] != 46 or inventory["nested_count"] != 3:
        raise AssertionError(
            "Actor policy inventory changed: expected 46 direct + 3 nested, got "
            f"{inventory['direct_count']} direct + {inventory['nested_count']} nested"
        )
    reachable = set(inventory["reachable"])
    cases = actor_cases()
    case_ids = [case["id"] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise AssertionError("Actor fixture case IDs must be unique")

    results = [_run_case(case, actor, reachable) for case in cases]
    direct_positive = {
        name for case in cases for name in case.get("direct_positive", ())
    }
    missing_direct_receipts = sorted(reachable - direct_positive)
    if missing_direct_receipts:
        raise AssertionError(
            "Actor fixture lacks positive branch receipts for: "
            + ", ".join(missing_direct_receipts)
        )
    invoked = {
        row["name"]
        for result in results
        for phase in ("first", "second")
        for row in result[phase]["policy_receipts"]
    }
    missing_invocations = sorted(reachable - invoked)
    if missing_invocations:
        raise AssertionError(
            "Actor model_inference never invoked: " + ", ".join(missing_invocations)
        )

    return {
        "fixture": {
            "case_count": len(cases),
            "historical_test_seed_count": sum(
                case["provenance"] == "historical_test_seed" for case in cases
            ),
            "trajectory_derived_case_count": 0,
            "archived_request_identity_claimed": False,
            "source_sha256": hashlib.sha256(fixture_source).hexdigest(),
            "manifest_source_sha256": fixture_manifest["source_sha256"],
            "source_line_count": len(fixture_source.splitlines()),
        },
        "policy_inventory": inventory,
        "coverage": {
            "positive_branch_receipt_count": len(direct_positive),
            "positive_branch_receipts": sorted(direct_positive),
            "model_inference_invocation_count": len(invoked),
            "model_inference_invocations": sorted(invoked),
            "missing_positive_branch_receipts": missing_direct_receipts,
            "missing_model_inference_invocations": missing_invocations,
        },
        "cases": results,
    }
