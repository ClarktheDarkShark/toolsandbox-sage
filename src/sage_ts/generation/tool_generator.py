"""Structured generation of deterministic helper tools."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from sage_ts.adapters.openai_agent_adapter import ChatRequest
from sage_ts.generation.prompt_cache import PromptCache, cache_key
from sage_ts.generation.tool_spec import GeneratedTool, ToolFamily, ToolInput, ToolSpec


class ChatCompleter(Protocol):
    model: str

    def complete(self, request: ChatRequest) -> str: ...


@dataclass(frozen=True)
class ToolGenerationRequest:
    scenario_name: str
    observation: str
    allowed_families: tuple[str, ...]
    validation_examples: tuple[dict[str, object], ...] = ()
    suggested_tool_name: str | None = None

    def prompt(self) -> str:
        families = ", ".join(self.allowed_families)
        examples = (
            f" Validation examples: {json.dumps(list(self.validation_examples))}."
            if self.validation_examples
            else ""
        )
        tool_name_hint = (
            f' The tool_name must be exactly "{self.suggested_tool_name}".'
            if self.suggested_tool_name
            else ""
        )
        return (
            "Propose one deterministic Python helper tool as JSON with two top-level "
            'keys: "spec" and "code". '
            '"spec" must have: tool_name (str), family (str from allowed list), '
            "description (str), "
            'inputs (list of objects each with exactly keys "name", "annotation", '
            '"description"), '
            "output_annotation (str), generalization_rationale (str), "
            "inadequacy_evidence (str). "
            "Annotations must be exactly one of: str, int, float, bool, dict. "
            'If the output is a dictionary, output_annotation must be exactly "dict". '
            '"code" is a self-contained Python function string with exactly one '
            "function whose name matches spec.tool_name. The function signature must "
            "include type annotations matching spec.inputs and spec.output_annotation. "
            "Do not include imports, try/except, classes, lambdas, filesystem access, "
            "network access, subprocess calls, side effects, hidden global state, or "
            "wrapper functions. "
            "The function must pass every validation example exactly. "
            f"{tool_name_hint} "
            f"Allowed families: {families}. "
            f"Scenario: {self.scenario_name}. Observation: {self.observation}.{examples}"
        )


class ToolGenerator:
    def __init__(self, completer: ChatCompleter, cache: PromptCache) -> None:
        self.completer = completer
        self.cache = cache

    def generate(self, request: ToolGenerationRequest) -> GeneratedTool:
        prompt = request.prompt()
        key = cache_key(self.completer.model, {"kind": "tool_generation_v3"}, prompt)
        response = self.cache.get(key)
        if response is None:
            response = self.completer.complete(
                ChatRequest(
                    system="You generate safe deterministic Python helper tools.",
                    user=prompt,
                    model=self.completer.model,
                )
            )
            self.cache.put(key, response)
        return parse_generated_tool_json(response)


def _to_snake_case(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _coerce_input(item: Any) -> ToolInput:
    if isinstance(item, dict):
        return ToolInput(
            name=str(item.get("name", item.get("param", "arg"))),
            annotation=str(item.get("annotation", item.get("type", "str"))),
            description=str(item.get("description", "")),
        )
    if isinstance(item, str):
        parts = item.split(":", 2)
        name = parts[0].strip()
        annotation = parts[1].strip() if len(parts) > 1 else "str"
        description = parts[2].strip() if len(parts) > 2 else ""
        return ToolInput(name=name, annotation=annotation, description=description)
    raise ValueError(f"Cannot coerce ToolInput from {type(item)}: {item!r}")


def parse_generated_tool_json(response: str) -> GeneratedTool:
    response = response.strip()
    if response.startswith("```"):
        response = response.removeprefix("```json").removeprefix("```").strip()
        response = response.removesuffix("```").strip()
    payload = json.loads(response)
    spec_payload = payload["spec"]
    spec = ToolSpec(
        tool_name=_to_snake_case(str(spec_payload["tool_name"])),
        family=ToolFamily(str(spec_payload["family"])),
        description=str(spec_payload["description"]),
        inputs=tuple(_coerce_input(item) for item in spec_payload["inputs"]),
        output_annotation=str(spec_payload["output_annotation"]),
        generalization_rationale=str(spec_payload["generalization_rationale"]),
        inadequacy_evidence=str(spec_payload["inadequacy_evidence"]),
    )
    return GeneratedTool(spec=spec, code=str(payload["code"]))
