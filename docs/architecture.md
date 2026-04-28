# ToolSandbox SAGE Architecture

This repository keeps the upstream ToolSandbox benchmark core intact and adds SAGE as a thin outer layer.

SAGE-owned code lives under `src/sage_ts`. It is responsible for experiment orchestration, inadequacy detection, deterministic helper-tool generation, validation, registry persistence, reuse logging, and dashboard exports.

ToolSandbox-owned code remains under `tool_sandbox`. Changes there should be avoided unless there is no adapter path.

The first generated-tool surface is intentionally narrow:

- Canonicalizers.
- Derived-value calculators.
- State-precondition helpers.
- Composite workflow helpers.
- Validation and abstention helpers.

Success requires a generated helper to pass validation, enter the registry, be reused on later distinct scenarios, and improve held-out transfer outcomes over baseline.
