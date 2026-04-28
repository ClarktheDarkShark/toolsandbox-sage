"""Persistent prompt cache for model-generated tool specs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def cache_key(model: str, config: dict[str, Any], prompt: str) -> str:
    payload = json.dumps(
        {"model": model, "config": config, "prompt": prompt},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PromptCache:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0
        self.writes = 0

    def get(self, key: str) -> str | None:
        path = self.root / f"{key}.json"
        if not path.exists():
            self.misses += 1
            return None
        self.hits += 1
        payload = json.loads(path.read_text(encoding="utf-8"))
        return str(payload["response"])

    def put(self, key: str, response: str) -> None:
        path = self.root / f"{key}.json"
        path.write_text(json.dumps({"response": response}, indent=2) + "\n")
        self.writes += 1

    def metrics(self) -> dict[str, int | str]:
        return {
            "root": str(self.root),
            "hits": self.hits,
            "misses": self.misses,
            "writes": self.writes,
        }
