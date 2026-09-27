#!/usr/bin/env python3
"""Run one frozen visible-signal mutation profile in an isolated checkout."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--profile",
        choices=("reference_v1", "candidate_shared_facts_v1"),
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tamper-self-test", action="store_true")
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    validation_root = Path(__file__).resolve().parents[2]
    sys.path[:0] = [str(root / "src"), str(root), str(validation_root)]

    from validation.replay import visible_signal_mutation_audit as audit

    detected = audit.current_profile()
    if detected != args.profile:
        raise ValueError(
            f"requested mutation profile {args.profile!r}, detected {detected!r}"
        )
    report = audit.run_mutation_audit()
    audit.verify_mutation_audit(report)
    if args.tamper_self_test:
        forged = copy.deepcopy(report)
        forged["profile_identity"]["source_sha256"] = "0" * 64
        try:
            audit.verify_mutation_audit(forged)
        except ValueError:
            pass
        else:
            raise AssertionError("forged mutation-profile identity was accepted")

        if "dependency_source_sha256" in report["profile_identity"]:
            forged = copy.deepcopy(report)
            forged["profile_identity"]["dependency_source_sha256"] = "0" * 64
            try:
                audit.verify_mutation_audit(forged)
            except ValueError:
                pass
            else:
                raise AssertionError(
                    "forged candidate dependency identity was accepted"
                )

        forged = copy.deepcopy(report)
        forged["rows"][0]["changed_paths"].append("/forged")
        try:
            audit.verify_mutation_audit(forged)
        except ValueError:
            pass
        else:
            raise AssertionError("forged mutation carrier pairing was accepted")
    mutations = audit.enumerate_mutations()
    report["kind_counts"] = dict(
        sorted(Counter(item.kind for item in mutations).items())
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"PASS {detected}: {report['caught_count']} caught + "
        f"{report['invisible_count']} proven equivalents = "
        f"{report['mutation_count']} mutations"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
