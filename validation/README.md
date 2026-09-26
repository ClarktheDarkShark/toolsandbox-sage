# SAGE refactor validation

This directory is the external, non-shipping safety harness for the
behavior-preserving minimal-runtime refactor. It is intentionally maintained
on the validation branch rather than packaged with the production
application.

The harness has three responsibilities:

- `contract/` freezes the reference source, benchmark inputs, evidence
  anchors, model and policy configuration, and statistical acceptance gates.
- `replay/` compares deterministic semantic snapshots from the immutable
  reference and candidate checkouts and fails on every unapproved difference.
- `inventory/` reports production, dashboard, native ToolSandbox, generated,
  and behavior-definition line counts without hiding implementation in data.

Reference commit: `2518a2a134c50d603d6250b08f47623b27e7737f`

Reference tag: `sage-refactor-reference-2518a2a`

Captured model responses may be used here only for offline equivalence
testing. Replay or cached responses must never be enabled in live evidence
runs.
