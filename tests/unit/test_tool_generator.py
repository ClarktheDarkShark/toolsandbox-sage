import json
from dataclasses import dataclass
from pathlib import Path

from sage_ts.adapters.openai_agent_adapter import ChatRequest
from sage_ts.generation.prompt_cache import PromptCache
from sage_ts.generation.tool_generator import ToolGenerationRequest, ToolGenerator


@dataclass
class FakeCompleter:
    model: str = "fake-model"
    calls: int = 0

    def complete(self, request: ChatRequest) -> str:
        self.calls += 1
        return json.dumps(
            {
                "spec": {
                    "tool_name": "normalize_label",
                    "family": "canonicalizer",
                    "description": "Normalize labels.",
                    "inputs": [
                        {
                            "name": "label",
                            "annotation": "str",
                            "description": "Raw label.",
                        }
                    ],
                    "output_annotation": "str",
                    "generalization_rationale": "Labels recur with superficial variants.",
                    "inadequacy_evidence": "Existing tools do not expose label normalization.",
                },
                "code": "def normalize_label(label: str) -> str:\n    return label.strip().lower()\n",
            }
        )


def test_tool_generator_uses_prompt_cache(tmp_path: Path) -> None:
    completer = FakeCompleter()
    generator = ToolGenerator(completer=completer, cache=PromptCache(tmp_path))
    request = ToolGenerationRequest(
        scenario_name="toy",
        observation="Need deterministic label normalization.",
        allowed_families=("canonicalizer",),
    )

    first = generator.generate(request)
    second = generator.generate(request)

    assert first.spec.tool_name == "normalize_label"
    assert second.spec.tool_name == "normalize_label"
    assert completer.calls == 1


def test_generation_request_includes_reusable_name_hint() -> None:
    request = ToolGenerationRequest(
        scenario_name="find_temperature_f_with_location_alt",
        observation="Repeated Celsius to Fahrenheit conversion is needed.",
        allowed_families=("derived_value_calculator",),
        suggested_tool_name="celsius_to_fahrenheit",
    )

    assert 'tool_name must be exactly "celsius_to_fahrenheit"' in request.prompt()
