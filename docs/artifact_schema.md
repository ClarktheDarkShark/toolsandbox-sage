# Artifact Schema

Artifacts are JSON or JSONL first.

Required run-level artifacts:

- `run_manifest.json`: git SHA, branch, model, config, scenario manifest, registry path, start/end timestamps.
- `scenario_outcomes.jsonl`: one row per scenario with score, milestones, minefields, turns, tool calls, and generated-tool use.
- `tool_birth_events.jsonl`: proposed tools, inadequacy evidence, validation status, and rejection reasons.
- `registry_manifest.json`: accepted tool versions, code hashes, lineage, reuse counts, and retirement status.
- `reuse_events.jsonl`: later-scenario generated-tool invocations and outcome attribution.
- `transfer_report.json`: matched baseline vs frozen-registry SAGE comparison.
