"""Route-independent outcome scoring for ToolSandbox runs."""

from __future__ import annotations

import datetime as _dt
import itertools
import json
import math
import re
from typing import Any, cast

import holidays
from rapidfuzz import fuzz, utils
from rouge_score import rouge_scorer

from tool_sandbox.common.evaluation import Milestone
from tool_sandbox.common.execution_context import (
    DatabaseNamespace,
    ExecutionContext,
    RoleType,
)
from tool_sandbox.common.scenario import Scenario

_ROUGE = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_WORD_RE = re.compile(r"[a-z0-9]+")
_ANCHOR_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "be",
    "for",
    "from",
    "has",
    "have",
    "i",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "there",
    "this",
    "to",
    "with",
}


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _role(value: Any) -> str:
    return _as_text(value).upper()


def _is_agent_to_user(row: dict[str, Any]) -> bool:
    return _role(row.get("sender")) == _role(RoleType.AGENT) and _role(
        row.get("recipient")
    ) == _role(RoleType.USER)


def _is_user_to_agent(row: dict[str, Any]) -> bool:
    return _role(row.get("sender")) == _role(RoleType.USER) and _role(
        row.get("recipient")
    ) == _role(RoleType.AGENT)


def _sandbox_rows(execution_context: ExecutionContext) -> list[dict[str, Any]]:
    sandbox_namespace = cast(DatabaseNamespace, DatabaseNamespace.SANDBOX)
    rows = execution_context.get_database(
        sandbox_namespace,
        get_all_history_snapshots=True,
        drop_sandbox_message_index=False,
    ).to_dicts()
    return rows


def _is_brief_user_acknowledgement(content: str) -> bool:
    lower = content.strip().lower()
    if not lower:
        return False
    if "?" in lower or any(
        token in lower
        for token in (
            "can you",
            "could you",
            "what ",
            "why ",
            "how ",
            "search",
            "find",
            "add ",
            "remove ",
            "modify ",
            "send ",
        )
    ):
        return False
    return any(
        token in lower
        for token in (
            "thank",
            "thanks",
            "got it",
            "great",
            "cool",
            "okay",
            "ok",
            "alright",
            "you found it",
        )
    )


def _is_plain_assistant_acknowledgement(content: str) -> bool:
    lower = " ".join(content.strip().lower().split())
    if not lower:
        return False
    if any(
        token in lower
        for token in (
            "recap",
            "says",
            "phone",
            "+",
            " is ",
            " are ",
        )
    ):
        return False
    return lower.startswith(
        (
            "you're welcome",
            "you are welcome",
            "no problem",
            "glad i could help",
            "happy to help",
        )
    )


def _agent_messages(execution_context: ExecutionContext) -> list[str]:
    rows = _sandbox_rows(execution_context)
    messages: list[tuple[int, str]] = []
    for index, row in enumerate(rows):
        if _is_agent_to_user(row):
            content = _as_text(row.get("content")).strip()
            if content:
                messages.append((index, content))
    if not messages:
        return []
    latest_index, latest_content = messages[-1]
    if len(messages) > 1 and _is_plain_assistant_acknowledgement(latest_content):
        latest_user = None
        for row in reversed(rows[:latest_index]):
            if _is_user_to_agent(row):
                latest_user = _as_text(row.get("content"))
                break
            if _is_agent_to_user(row):
                break
        if latest_user is not None and _is_brief_user_acknowledgement(latest_user):
            return [messages[-2][1]]
    return [latest_content]


def _outcome_observed_messages(execution_context: ExecutionContext) -> list[str]:
    """Expose the exact assistant messages used by outcome scoring."""
    return _agent_messages(execution_context)


def _parse_tool_trace_value(tool_trace: Any) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    if not tool_trace:
        return traces
    raw_traces = tool_trace if isinstance(tool_trace, list) else [tool_trace]
    for raw_trace in raw_traces:
        try:
            parsed = json.loads(raw_trace) if isinstance(raw_trace, str) else raw_trace
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(parsed, dict):
            traces.append(parsed)
        elif isinstance(parsed, list):
            traces.extend(item for item in parsed if isinstance(item, dict))
    return traces


def _iter_tool_traces(execution_context: ExecutionContext) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    for row in _sandbox_rows(execution_context):
        traces.extend(_parse_tool_trace_value(row.get("tool_trace")))
    return traces


def _normalize_value(value: Any) -> list[str]:
    if isinstance(value, float):
        return [f"{value:.0f}", f"{value:.1f}", f"{value:.2f}", f"{value:.3f}"]
    if isinstance(value, int):
        return [str(value)]
    return [_as_text(value)]


def _target_rows(
    milestone: Milestone,
) -> list[tuple[DatabaseNamespace, dict[str, Any]]]:
    rows: list[tuple[DatabaseNamespace, dict[str, Any]]] = []
    for constraint in milestone.snapshot_constraints:
        dataframe = constraint.target_dataframe
        if dataframe is None:
            continue
        for row in dataframe.to_dicts():
            rows.append((constraint.database_namespace, row))
    return rows


def _target_tool_traces(scenario: Scenario) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    for milestone in scenario.evaluation.milestone_matcher.milestones:
        for namespace, row in _target_rows(milestone):
            if namespace == DatabaseNamespace.SANDBOX:
                traces.extend(_parse_tool_trace_value(row.get("tool_trace")))
    return traces


def _holiday_timestamp(holiday_name: str, year: int) -> float | None:
    holiday_matches: list[tuple[float, _dt.date, str]] = sorted(
        (
            (
                fuzz.partial_ratio(holiday_name, name, processor=utils.default_process),
                date,
                name,
            )
            for date, name in holidays.country_holidays(
                country="US", years=year
            ).items()
        ),
        reverse=True,
    )
    if not holiday_matches or holiday_matches[0][0] <= 90:
        return None
    return _dt.datetime.combine(
        holiday_matches[0][1], _dt.datetime.min.time()
    ).timestamp()


def _expected_holiday_timestamps(
    scenario: Scenario,
    current_timestamps: list[float],
) -> list[float]:
    timestamps: list[float] = []
    for trace in _target_tool_traces(scenario):
        if trace.get("tool_name") != "search_holiday":
            continue
        arguments = trace.get("arguments") or {}
        if not isinstance(arguments, dict) or not arguments.get("holiday_name"):
            continue
        years: list[int] = []
        if arguments.get("year") is not None:
            try:
                years.append(int(arguments["year"]))
            except (TypeError, ValueError):
                continue
        else:
            years.extend(
                _dt.datetime.fromtimestamp(timestamp).year
                for timestamp in current_timestamps
            )
        for year in years:
            timestamp = _holiday_timestamp(str(arguments["holiday_name"]), year)
            if timestamp is not None and timestamp not in timestamps:
                timestamps.append(timestamp)
    return timestamps


def _placeholder_values(
    execution_context: ExecutionContext,
    scenario: Scenario,
) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    current_timestamps: list[float] = []
    holiday_timestamps: list[float] = []
    for trace in _iter_tool_traces(execution_context):
        name = _as_text(trace.get("tool_name"))
        result = trace.get("result")
        if isinstance(result, dict):
            for key, value in result.items():
                bucket = values.setdefault(str(key), [])
                for normalized in _normalize_value(value):
                    if normalized not in bucket:
                        bucket.append(normalized)
        if name == "get_current_timestamp" and isinstance(result, (int, float, str)):
            try:
                current_timestamps.append(float(result))
            except (TypeError, ValueError):
                pass
        elif name == "search_holiday" and isinstance(result, (int, float, str)):
            try:
                holiday_timestamps.append(float(result))
            except (TypeError, ValueError):
                pass
    for timestamp in _expected_holiday_timestamps(scenario, current_timestamps):
        if timestamp not in holiday_timestamps:
            holiday_timestamps.append(timestamp)
    if "days" not in values and current_timestamps and holiday_timestamps:
        derived_days: list[str] = []
        for start, end in itertools.product(current_timestamps, holiday_timestamps):
            if end <= start:
                continue
            delta = _dt.datetime.fromtimestamp(end) - _dt.datetime.fromtimestamp(start)
            for day in (delta.days - 1, delta.days, delta.days + 1):
                if day >= 0 and str(day) not in derived_days:
                    derived_days.append(str(day))
        if derived_days:
            values["days"] = derived_days
    return values


def _render_templates(template: str, values: dict[str, list[str]]) -> list[str]:
    names = _PLACEHOLDER_RE.findall(template)
    if not names:
        return [template]
    choices = [values.get(name) or [f"{{{name}}}"] for name in names]
    rendered: list[str] = []
    for combination in itertools.product(*choices):
        current = template
        for name, value in zip(names, combination):
            current = current.replace(f"{{{name}}}", value)
        rendered.append(current)
    return rendered


def _numeric_match_score(expected: str, observed: str) -> float | None:
    expected_numbers = [float(match) for match in _NUMBER_RE.findall(expected)]
    if not expected_numbers:
        return None
    observed_numbers = [float(match) for match in _NUMBER_RE.findall(observed)]
    if not observed_numbers:
        return 0.0
    for expected_number in expected_numbers:
        if not any(
            abs(observed_number - expected_number) <= 1
            for observed_number in observed_numbers
        ):
            return 0.0
    return 1.0


def _anchor_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for token in _WORD_RE.findall(text.lower()):
        if token in _ANCHOR_STOPWORDS or token.isdigit():
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens


def _anchor_coverage(expected: str, observed: str) -> float:
    anchors = _anchor_tokens(expected)
    if not anchors:
        return 1.0
    observed_tokens = set(_WORD_RE.findall(observed.lower()))
    return sum(1 for token in anchors if token in observed_tokens) / len(anchors)


def _content_similarity(expected: str, observed: str) -> float:
    expected = " ".join(expected.split())
    observed = " ".join(observed.split())
    if not expected or not observed:
        return 0.0
    numeric_score = _numeric_match_score(expected, observed)
    if numeric_score == 0.0:
        return 0.0
    if numeric_score == 1.0 and _anchor_coverage(expected, observed) >= 0.67:
        return 1.0
    if expected.lower() in observed.lower():
        return 1.0
    if _anchor_coverage(expected, observed) >= 1.0:
        return 1.0
    return float(_ROUGE.score(target=expected, prediction=observed)["rougeL"].fmeasure)


def _is_route_only(milestone: Milestone) -> bool:
    rows = _target_rows(milestone)
    if not rows:
        return True
    return all(
        namespace == DatabaseNamespace.SANDBOX
        and bool(row.get("tool_trace"))
        and not row.get("content")
        for namespace, row in rows
    )


def _answer_templates(milestone: Milestone) -> list[str]:
    templates: list[str] = []
    for namespace, row in _target_rows(milestone):
        if namespace != DatabaseNamespace.SANDBOX or not _is_agent_to_user(row):
            continue
        content = _as_text(row.get("content")).strip()
        if content and content not in templates:
            templates.append(content)
    return templates


def _has_state_target(milestone: Milestone) -> bool:
    return any(
        namespace != DatabaseNamespace.SANDBOX and row
        for namespace, row in _target_rows(milestone)
    )


def _score_answer_templates(
    templates: list[str],
    messages: list[str],
    values: dict[str, list[str]],
) -> float:
    if not templates or not messages:
        return 0.0
    template_scores: list[float] = []
    for template in templates:
        rendered = _render_templates(template, values)
        template_scores.append(
            max(
                _content_similarity(expected, observed)
                for expected, observed in itertools.product(rendered, messages)
            )
        )
    product = math.prod(template_scores)
    return math.pow(product, 1 / len(template_scores))


def compute_outcome_score(
    scenario: Scenario,
    execution_context: ExecutionContext,
    *,
    canonical_milestone_scores: dict[int, float],
    minefield_similarity: float,
) -> dict[str, Any]:
    """Compute a route-independent outcome score alongside canonical ToolSandbox score.

    Route-only tool-trace milestones are excluded. User-visible answer milestones
    are rescored against the actual assistant messages, with placeholder
    resolution from observed tool results and deterministic target facts. State
    milestones keep their canonical score because they already evaluate the
    resulting world state.
    """
    messages = _agent_messages(execution_context)
    values = _placeholder_values(execution_context, scenario)
    checks: list[dict[str, Any]] = []
    for index, milestone in enumerate(scenario.evaluation.milestone_matcher.milestones):
        if _is_route_only(milestone):
            checks.append(
                {
                    "index": index,
                    "kind": "route",
                    "included": False,
                    "score": canonical_milestone_scores.get(index),
                }
            )
            continue
        templates = _answer_templates(milestone)
        if templates:
            score = _score_answer_templates(templates, messages, values)
            checks.append(
                {
                    "index": index,
                    "kind": "answer",
                    "included": True,
                    "score": score,
                    "targets": templates,
                    "observed_messages": messages,
                }
            )
            continue
        if _has_state_target(milestone):
            checks.append(
                {
                    "index": index,
                    "kind": "state",
                    "included": True,
                    "score": float(canonical_milestone_scores.get(index, 0.0)),
                }
            )
            continue
        checks.append(
            {
                "index": index,
                "kind": "other",
                "included": False,
                "score": canonical_milestone_scores.get(index),
            }
        )
    included_scores = [float(check["score"]) for check in checks if check["included"]]
    raw_score = sum(included_scores) / len(included_scores) if included_scores else None
    final_score = (
        None
        if raw_score is None
        else float(raw_score) * int(float(minefield_similarity) == 0)
    )
    return {
        "outcome_similarity": final_score,
        "outcome_milestone_similarity": raw_score,
        "outcome_minefield_similarity": float(minefield_similarity),
        "outcome_check_count": len(included_scores),
        "outcome_checks": checks,
    }
