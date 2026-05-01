"""Create immutable registry subsets for retained-tool ablation runs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tools", nargs="*", default=())
    parser.add_argument("--exclude", nargs="*", default=())
    parser.add_argument("--label", default="registry_subset")
    args = parser.parse_args()

    source_manifest = args.source / "registry_manifest.json"
    payload = json.loads(source_manifest.read_text(encoding="utf-8"))
    tools = dict(payload.get("tools", {}))
    requested = set(args.tools)
    excluded = set(args.exclude)
    if requested:
        missing = sorted(requested - set(tools))
        if missing:
            raise SystemExit(f"unknown requested tools: {missing}")
        kept = {name: tools[name] for name in sorted(requested)}
    else:
        kept = {name: entry for name, entry in sorted(tools.items())}
    if excluded:
        missing = sorted(excluded - set(tools))
        if missing:
            raise SystemExit(f"unknown excluded tools: {missing}")
        kept = {name: entry for name, entry in kept.items() if name not in excluded}

    args.out.mkdir(parents=True, exist_ok=True)
    manifest = {"tools": kept}
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    (args.out / "registry_manifest.json").write_bytes(manifest_bytes)
    lock = {
        "label": args.label,
        "source_registry": str(args.source),
        "source_manifest_sha256": _digest(source_manifest.read_bytes()),
        "registry_manifest_sha256": _digest(manifest_bytes),
        "included_tools": sorted(kept),
        "excluded_tools": sorted(set(tools) - set(kept)),
    }
    (args.out / "registry_lock.json").write_text(
        json.dumps(lock, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(lock, indent=2))


if __name__ == "__main__":
    main()
