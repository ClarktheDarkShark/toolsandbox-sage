# Chapter 3 Methodology Figures

Status comment: SAGE Praxis with true self-evolution working is the current main SAGE system going forward for methodology writing and future validation campaigns. This status does not modify protected final-claim evidence; protected claims still require locked matched validation and review.

These figures are prepared for Chapter 3 drafting, methodology review, and paper figures. SVG files are preferred for editing and submission workflows; PNG files are included for quick draft insertion and dashboard-style review.

Regenerate all figures with:

```bash
python3 scripts/render_sage_methodology_diagrams.py
```

## Figure Set

| Figure | Purpose | Files |
|---|---|---|
| 1. SAGE + ToolSandbox End-to-End System | Overview of the full experimental system: sealed task cohorts, cached controls, fresh SAGE arms, ToolSandbox, scoring, contribution exports, dashboards, and guardrails. | `docs/sage_protocol/figures/sage_toolsandbox_system_overview.svg`, `docs/sage_protocol/figures/sage_toolsandbox_system_overview.png` |
| 2. SAGE Internal Components | Zoom-in on SAGE: gap observer, generator, validation gates, registry, router/composer, actor bridge policy, lifecycle reflection, and evidence export. | `docs/sage_protocol/figures/sage_internal_components_zoom.svg`, `docs/sage_protocol/figures/sage_internal_components_zoom.png` |
| 3. Tool Generation, Validation, And Repair Loop | Tool birth and repair loop: gap packet, candidate design, static/schema gates, minefields, live smoke, natural adoption, retention/repair/park decisions, and scale gate. | `docs/sage_protocol/figures/sage_tool_generation_validation_repair_loop.svg`, `docs/sage_protocol/figures/sage_tool_generation_validation_repair_loop.png` |
| 4. SAGE Methodology For Matched ToolSandbox Validation | Paper-ready matched-validation diagram: sealed manifest, baseline and SAGE arms, ToolSandbox, SAGE runtime, paired analysis, safety, leakage, and reproducibility controls. | `docs/sage_protocol/figures/sage_peer_review_methodology_figure.svg`, `docs/sage_protocol/figures/sage_peer_review_methodology_figure.png` |

## Suggested Captions

**Figure 1. SAGE and ToolSandbox end-to-end system.** SAGE wraps ToolSandbox with an experimental layer for gap observation, tool generation, validation, routing, lifecycle reflection, paired scoring, contribution export, dashboard review, and artifact preservation. Baseline controls may use transparent task-level cache; SAGE/candidate evidence remains fresh.

**Figure 2. Internal SAGE components.** SAGE turns task and trace evidence into gap packets, generated helper candidates, validated registry entries, bounded routed bundles, natural actor usage, and lifecycle decisions. The bridge policy is a documented treatment component that helps preserve final answers and original ToolSandbox side-effect calls.

**Figure 3. Tool generation, validation, and repair loop.** Generated helpers are not promoted from generation alone. They must pass static/schema checks, minefield tests, live smoke validation, natural adoption, contribution review, and safety gates before scale-up. Force-call diagnostics can reveal latent value but are never counted as promotion evidence.

**Figure 4. Matched ToolSandbox validation design.** Baseline and SAGE arms share a sealed manifest and model policy. Controls may use task-level cache with provenance; SAGE/candidate arms are fresh. Outcome/task completion is primary, canonical/reference score is secondary, and paired statistical comparisons are reported with safety, leakage, cache, and reproducibility controls.

## Chapter 3 Placement

Use Figure 1 in the system overview subsection, Figure 2 in the SAGE architecture subsection, Figure 3 in the self-evolving tool lifecycle subsection, and Figure 4 in the formal evaluation design subsection.

## Boundary Statement

These figures describe the current SAGE Praxis methodology and live self-evolving system. They do not by themselves promote any experimental registry or treatment into protected final evidence.
