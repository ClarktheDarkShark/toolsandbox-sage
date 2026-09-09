# Chapter 3 Methodology Figures

This figure set documents the current SAGE evidence boundary used for Chapter 3:
autonomous tool generation, validation/repair, registry retention, visible-context
routing, policy-directed generated-tool use, lifecycle feedback, contribution
accounting, and matched baseline comparison. It does not describe retired
synthetic completion paths or the later natural-selection experiments.

Current source-of-truth methodology document:

```text
docs/sage_protocol/chapter3_sage_methodology_system_architecture_v061.md
```

Current primary figure assets:

| Figure | Purpose | Files |
|---|---|---|
| SAGE self-evolution flow | High-level SAGE loop: observe task evidence, generate candidate tools, validate and repair, store accepted tools, route relevant tools, execute normal task turns, and learn from feedback. | `docs/sage_protocol/figures/sage_self_evolution_flow_v061.svg`, `docs/sage_protocol/figures/sage_self_evolution_flow_v061.png` |
| SAGE self-evolution publication loop | Publication-oriented visual of the same tool-generation lifecycle. | `docs/sage_protocol/figures/sage_self_evolution_loop_publication.svg`, `docs/sage_protocol/figures/sage_self_evolution_loop_publication.png`, `docs/sage_protocol/figures/sage_self_evolution_loop_publication.html` |
| SAGE design loop | Editable design companion for the high-level loop. | `docs/sage_protocol/figures/sage_self_evolution_loop_design.html`, `docs/sage_protocol/figures/sage_self_evolution_loop_design.png`, `docs/sage_protocol/figures/sage_self_evolution_loop_design.pdf` |

The old figure generators were removed from the production branch because they
encoded superseded natural-selection claims. The checked-in assets are
historical references; publication figures must be re-authored from the current
policy-directed methodology before reuse.

Release note: older methodology figures that mention retired synthetic
completion paths, force-call promotion, or generated-helper terminology are
obsolete and should not be used in Chapter 3 or production release material.
