# Experiment Protocol

All benchmark claims use fixed scenario manifests, fixed order, fixed model settings, and immutable artifacts.

Evaluation layers:

- `smoke_10`: wiring only; no research claim.
- `mechanism_40`: curated missing-capability and reuse debugging.
- `online_build_100`: matched baseline vs SAGE with an empty registry.
- `transfer_100`: matched baseline vs frozen-registry SAGE on unseen scenarios.
- `promotion_250`: broader confirmation before full benchmark.
- `full_benchmark`: final validation only after transfer and promotion gates are positive.

Do not claim tool-evolution success from tool generation alone. The retained-value claim requires accepted generated tools, later reuse, attribution, and held-out transfer improvement.
