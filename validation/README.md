# SAGE refactor validation

This directory is the external, non-shipping safety harness for the
behavior-preserving minimal-runtime refactor. It is intentionally maintained
on the validation branch rather than packaged with the production
application.

The harness has five responsibilities:

- `contract/` freezes the reference source, benchmark inputs, evidence
  anchors, model and policy configuration, and statistical acceptance gates.
- `replay/` compares deterministic semantic snapshots from the immutable
  reference and candidate checkouts and fails on every unapproved difference.
- `inventory/` reports production, dashboard, native ToolSandbox, generated,
  and behavior-definition line counts without hiding implementation in data.
- `historical/` runs the detached historical pytest oracle against a candidate
  checkout in the approved three-shard compatibility gate.
- `packaging/` verifies that the production `make package` target rejects dirty
  tracked and untracked trees, ignores poisoned build state, reproduces the
  exact application files and bytes stored at `HEAD`, exposes only the four
  approved commands, installs and imports in an isolated target, and emits
  byte-identical wheels from two builds of the same commit.

Reference commit: `2518a2a134c50d603d6250b08f47623b27e7737f`

Reference tag: `sage-refactor-reference-2518a2a`

Captured model responses may be used here only for offline equivalence
testing. Replay or cached responses must never be enabled in live evidence
runs.

## Historical pytest compatibility gate

Run the frozen 1,167-test compatibility partition against a candidate with the
same Python used for publication validation:

```bash
python -m validation.historical.verify_historical_pytest \
  --candidate-root /absolute/path/to/toolsandbox-sage-public-release \
  --test-oracle-root /absolute/path/to/toolsandbox-sage-refactor-test-oracle \
  --python /absolute/path/to/publication-python \
  --output-dir /absolute/path/to/new-gate-output
```

The three concurrent shards must finish with the exact core summaries `398
passed`, `384 passed, 7 deselected`, and `385 passed`. A shard may have no
warnings or exactly the two known pandas dependency warnings for `numexpr` and
`bottleneck`; their count and matched families are recorded separately. The
seven exclusions are the obsolete historical tests approved in
`contract/deletion_waivers_v1.json`. Any other return code, core summary,
warning family/count, or pytest outcome fails the gate. Each shard has a
separate pytest base directory and readable log, and `report.json` records the
commands, durations, full and core summaries, warnings, and exact 1,167-pass
total. If `--output-dir` is omitted, the runner creates a persistent temporary
output directory and prints its path in the report.

Before using a new oracle checkpoint, verify that collection still produces
one unique partition with the frozen SHA-256:

```bash
python -m validation.historical.verify_historical_pytest \
  --candidate-root /absolute/path/to/toolsandbox-sage-public-release \
  --test-oracle-root /absolute/path/to/toolsandbox-sage-refactor-test-oracle \
  --python /absolute/path/to/publication-python \
  --output-dir /absolute/path/to/new-collection-output \
  --verify-partition
```

The partition digest is SHA-256 over sorted unique node IDs joined by newline
and terminated by one trailing newline. That encoding reproduces
`b7d6f521ed1aceed160a960a42f5a362d242b92e8b2953a65b7c19dcd421ae5b`;
the non-terminated encoding does not, and both observed digests are retained in
the collection report.

Run the packaging gate against a clean candidate checkout with the same Python
used for publication validation:

```bash
python -m validation.packaging.verify_clean_wheel \
  /absolute/path/to/toolsandbox-sage-public-release \
  --python /absolute/path/to/publication-python \
  --report /tmp/sage-clean-wheel-report.json
```

The expected application-file count is derived from the candidate's committed
`pyproject.toml` and Git archive. It is intentionally never hard-coded, so a
reviewed source addition or removal changes the contract transparently while a
stale local build file still fails it.
