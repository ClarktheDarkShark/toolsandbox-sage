#!/usr/bin/env python3
"""Run the SAGE online lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sage_ts.adapters.openai_agent_adapter import OpenAIChatAdapter
from sage_ts.adapters.sage_run_adapter import SageRunConfig, run_sage_with_registry
from sage_ts.cache.openai_response_cache import (
    configure_response_cache_context,
    install_openai_response_cache,
    write_cache_artifacts,
)
from sage_ts.cache.openai_response_cache import (
    reset_metrics as reset_openai_response_cache_metrics,
)
from sage_ts.cache.openai_response_cache import (
    write_metrics as write_openai_response_cache_metrics,
)
from sage_ts.config.models import DEFAULT_MODEL
from sage_ts.config.splits import load_split_names
from sage_ts.generation.prompt_cache import PromptCache
from sage_ts.generation.tool_generator import ToolGenerator
from sage_ts.orchestration.toy_mechanism import run_toy_birth_reuse
from sage_ts.runtime.base_toolset import KNOWN_POLICIES, UPSTREAM_POLICY


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--split")
    parser.add_argument("--agent", default="Unhelpful")
    parser.add_argument("--user", default="GPT_4_o_2024_05_13")
    parser.add_argument(
        "--base-tool-policy",
        choices=KNOWN_POLICIES,
        default=UPSTREAM_POLICY,
    )
    parser.add_argument("--generation-model", default=DEFAULT_MODEL)
    parser.add_argument("--recurrence-threshold", type=int, default=2)
    parser.add_argument(
        "--prompt-cache-dir", type=Path, default=Path("outputs/prompt_cache")
    )
    parser.add_argument(
        "--enable-generation",
        action="store_true",
        help="Enable repeated-observation to generated-tool birth.",
    )
    parser.add_argument(
        "--registry-dir", type=Path, default=Path("outputs/sage_registry")
    )
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=Path("outputs/sage_online")
    )
    parser.add_argument(
        "--openai-response-cache-dir",
        type=Path,
        default=Path("outputs/openai_response_cache"),
    )
    parser.add_argument(
        "--cache-mode",
        choices=("off", "read_write", "read_only", "write_only"),
        default="read_write",
    )
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts"))
    parser.add_argument("--disable-openai-response-cache", action="store_true")
    parser.add_argument(
        "--toy-mechanism",
        action="store_true",
        help="Run a controlled generated-tool birth/reuse smoke.",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.toy_mechanism:
        result = run_toy_birth_reuse(args.output_dir)
        print(json.dumps(result, indent=2))
        return

    if args.manifest is None or args.split is None:
        raise SystemExit(
            "--manifest and --split are required unless --toy-mechanism is used"
        )

    scenario_names = tuple(load_split_names(args.manifest, args.split))
    response_cache_enabled = (
        not args.disable_openai_response_cache and args.cache_mode != "off"
    )
    if response_cache_enabled:
        install_openai_response_cache(
            args.openai_response_cache_dir,
            mode=args.cache_mode,
        )
    configure_response_cache_context(
        mode=f"sage_online:{args.split}",
        arm="candidate",
        agent=args.agent,
        user=args.user,
        base_tool_policy=args.base_tool_policy,
        scenario_names=scenario_names,
        registry_dir=args.registry_dir,
        generation_enabled=args.enable_generation,
        generation_model=args.generation_model,
        recurrence_threshold=args.recurrence_threshold,
    )
    reset_openai_response_cache_metrics()
    prompt_cache = PromptCache(args.prompt_cache_dir)
    generator = (
        ToolGenerator(
            completer=OpenAIChatAdapter(model=args.generation_model),
            cache=prompt_cache,
        )
        if args.enable_generation
        else None
    )
    output_directory = run_sage_with_registry(
        SageRunConfig(
            agent=args.agent,
            user=args.user,
            scenario_names=scenario_names,
            output_dir=args.output_dir,
            registry_dir=args.registry_dir,
            recurrence_threshold=args.recurrence_threshold,
            base_tool_policy=args.base_tool_policy,
        ),
        generator=generator,
    )
    (output_directory / "prompt_cache_metrics.json").write_text(
        json.dumps(prompt_cache.metrics(), indent=2) + "\n",
        encoding="utf-8",
    )
    if response_cache_enabled:
        write_openai_response_cache_metrics(
            output_directory / "openai_response_cache_metrics.json"
        )
        write_cache_artifacts(args.artifact_root)
    print(json.dumps({"output_directory": str(output_directory)}, indent=2))


if __name__ == "__main__":
    main()
