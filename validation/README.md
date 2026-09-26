# SAGE refactor validation

This directory is the external, non-shipping safety harness for the
behavior-preserving minimal-runtime refactor. It is intentionally maintained
on the validation branch rather than packaged with the production
application.

The harness has four responsibilities:

- `contract/` freezes the reference source, benchmark inputs, evidence
  anchors, model and policy configuration, and statistical acceptance gates.
- `replay/` compares deterministic semantic snapshots from the immutable
  reference and candidate checkouts and fails on every unapproved difference.
- `inventory/` reports production, dashboard, native ToolSandbox, generated,
  and behavior-definition line counts without hiding implementation in data.
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
