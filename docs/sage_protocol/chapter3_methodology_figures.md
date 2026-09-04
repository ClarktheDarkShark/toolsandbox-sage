# Chapter 3 Methodology Figures

> **SUPERSEDED — ARCHIVAL V061 FIGURE SET.** These figures are retained to audit
> the earlier methodology boundary and are not current paper assets. See
> [current_state.md](current_state.md).

This figure set documents the current SAGE evidence boundary used for Chapter 3:
autonomous tool generation, validation/repair, registry retention, visible-context
routing, natural generated-tool use, lifecycle feedback, contribution accounting,
and matched baseline comparison. It does not describe retired synthetic
completion paths.

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

Regeneration scripts:

```bash
python3 scripts/render_sage_self_evolution_loop_publication.py
python3 scripts/export_sage_self_evolution_loop_design.py
```

Release note: older methodology figures that mention retired synthetic
completion paths, force-call promotion, or generated-helper terminology are
obsolete and should not be used in Chapter 3 or production release material.
