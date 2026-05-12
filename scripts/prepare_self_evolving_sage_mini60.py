#!/usr/bin/env python3
"""Prepare a <=60 task self-evolving SAGE contact-gap campaign."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sage_ts.orchestration.self_evolving_campaign import (
    MINI_MODEL,
    SelfEvolvingCampaignConfig,
    prepare_self_evolving_campaign,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-gap-packet",
        type=Path,
        default=Path(
            "artifacts/praxis_combined_bridge_policy/summary/"
            "praxis_combined_bridge_policy_formal500_v2_gap_packets.json"
        ),
    )
    parser.add_argument(
        "--source-manifest",
        type=Path,
        default=Path("docs/sage_protocol/manifests/v2_1_formal_500.json"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("artifacts/self_evolving_sage/current_mini60"),
    )
    parser.add_argument("--max-samples", type=int, default=60)
    parser.add_argument("--agent", default=MINI_MODEL)
    parser.add_argument("--user", default=MINI_MODEL)
    parser.add_argument("--generation-model", default=MINI_MODEL)
    parser.add_argument("--split-name", default="transfer_60")
    parser.add_argument(
        "--tool-strategy",
        choices=(
            "contact_action_v2",
            "praxis_contact_bridgepack",
            "praxis_current_pack",
        ),
        default="contact_action_v2",
    )
    parser.add_argument(
        "--recipe-registry",
        type=Path,
        default=Path(
            "artifacts/praxis_safety_repair/registries/"
            "praxis_bridgepack_combined_bridge_policy_v1"
        ),
    )
    args = parser.parse_args()

    prepared = prepare_self_evolving_campaign(
        SelfEvolvingCampaignConfig(
            source_gap_packet=args.source_gap_packet,
            source_manifest=args.source_manifest,
            output_root=args.output_root,
            max_samples=args.max_samples,
            agent_model=args.agent,
            user_model=args.user,
            generation_model=args.generation_model,
            split_name=args.split_name,
            tool_strategy=args.tool_strategy,
            recipe_registry=args.recipe_registry,
        )
    )
    print(json.dumps(prepared.to_json(), indent=2))


if __name__ == "__main__":
    main()
