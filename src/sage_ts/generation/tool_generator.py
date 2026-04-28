"""Structured generation of deterministic helper tools."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

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

    def prompt(self) -> str:
        families = ", ".join(self.allowed_families)
        examples = (
            f" Validation examples: {json.dumps(list(self.validation_examples))}."
            if self.validation_examples
            else ""
        )
        return (
            "Propose one deterministic Python helper tool as JSON. "
            "Required keys: spec, code. spec keys: tool_name, family, description, "
            "inputs, output_annotation, generalization_rationale, inadequacy_evidence. "
            "Use only primitive typed inputs and deterministic code with no imports. "
            f"Allowed families: {families}. "
            f"Scenario: {self.scenario_name}. Observation: {self.observation}.{examples}"
        )


class ToolGenerator:
    def __init__(self, completer: ChatCompleter, cache: PromptCache) -> None:
        self.completer = completer
        self.cache = cache

    def generate(self, request: ToolGenerationRequest) -> GeneratedTool:
        prompt = request.prompt()
        key = cache_key(self.completer.model, {"kind": "tool_generation_v1"}, prompt)
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


def parse_generated_tool_json(response: str) -> GeneratedTool:
    response = response.strip()
    if response.startswith("```"):
        response = response.removeprefix("```json").removeprefix("```").strip()
        response = response.removesuffix("```").strip()
    payload = json.loads(response)
    spec_payload = payload["spec"]
    spec = ToolSpec(
        tool_name=str(spec_payload["tool_name"]),
        family=ToolFamily(str(spec_payload["family"])),
        description=str(spec_payload["description"]),
        inputs=tuple(ToolInput(**item) for item in spec_payload["inputs"]),
        output_annotation=str(spec_payload["output_annotation"]),
        generalization_rationale=str(spec_payload["generalization_rationale"]),
        inadequacy_evidence=str(spec_payload["inadequacy_evidence"]),
    )
    return GeneratedTool(spec=spec, code=str(payload["code"]))
