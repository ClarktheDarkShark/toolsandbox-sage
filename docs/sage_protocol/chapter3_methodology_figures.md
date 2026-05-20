# Chapter 3 Methodology Figures

Status comment: SAGE Praxis with true self-evolution working is the current main SAGE system going forward for methodology writing and future validation campaigns. This status does not modify protected final-claim evidence; protected claims still require locked matched validation and review.

These figures are prepared for Chapter 3 drafting, methodology review, and paper figures. This package uses architecture-grade system diagrams with explicit runtime boundaries, data stores, control/data flows, safety gates, lifecycle states, and claim boundaries rather than sketch-level boxes. SVG files are preferred for editing and submission workflows; PNG files are included for quick draft insertion and dashboard-style review. The one-page infographic also has an HTML companion built from selectable DOM sections so browser annotation tools can target individual panels, cards, evidence steps, and generated-tool examples.

Regenerate all figures with:

```bash
python3 scripts/render_sage_methodology_diagrams.py
```

Do not manually regenerate or edit only one image artifact for committed figure changes. The renderer is the source of truth and should be run as a full set so SVG, PNG, and HTML companions stay synchronized.

## Figure Set

| Figure | Purpose | Files |
|---|---|---|
| 1. SAGE + ToolSandbox System Architecture | Full execution architecture with protocol trust boundary, manifest/control-cache stores, matched baseline and SAGE arms, ToolSandbox runtime, scoring, contribution export, artifact storage, feedback, and claim-run invariants. | `docs/sage_protocol/figures/sage_toolsandbox_system_overview.svg`, `docs/sage_protocol/figures/sage_toolsandbox_system_overview.png` |
| 2. SAGE Runtime Component Architecture | Internal SAGE subsystem design: event ingress, gap observer, opportunity ranker, generator, candidate builder, validator, registry, router/composer, actor bridge, ToolSandbox adapter, feedback packets, lifecycle ledger, and repair planner. | `docs/sage_protocol/figures/sage_internal_components_zoom.svg`, `docs/sage_protocol/figures/sage_internal_components_zoom.png` |
| 3. Tool Generation, Validation, And Repair State Machine | Tool birth state machine with explicit validation gates, failure classification, self-healing repair paths, promotion evidence boundary, scale gate, and hard stop conditions. | `docs/sage_protocol/figures/sage_tool_generation_validation_repair_loop.svg`, `docs/sage_protocol/figures/sage_tool_generation_validation_repair_loop.png` |
| 4. Paper Figure: Matched Validation And Self-Evolving Tool Lifecycle | Peer-review-ready panel figure covering matched validation, statistical outputs, self-evolving lifecycle, and research integrity guardrails. | `docs/sage_protocol/figures/sage_peer_review_methodology_figure.svg`, `docs/sage_protocol/figures/sage_peer_review_methodology_figure.png` |
| 5. One-Page SAGE Infographic | Forum/shareable visual summary of the self-evolving SAGE flywheel: observe gaps, generate helpers, validate and repair, store safe tools, route bounded helper bundles, measure contribution, and preserve the research claim boundary. | `docs/sage_protocol/figures/sage_one_page_infographic.svg`, `docs/sage_protocol/figures/sage_one_page_infographic.png`, `docs/sage_protocol/figures/sage_one_page_infographic.html` |

## Suggested Captions

**Figure 1. SAGE and ToolSandbox end-to-end system.** SAGE wraps ToolSandbox with an experimental layer for gap observation, tool generation, validation, routing, lifecycle reflection, paired scoring, contribution export, dashboard review, and artifact preservation. Baseline controls may use transparent task-level cache; SAGE/candidate evidence remains fresh.

**Figure 2. Internal SAGE components.** SAGE turns task and trace evidence into gap packets, generated helper candidates, validated registry entries, bounded routed bundles, natural actor usage, and lifecycle decisions. The bridge policy is a documented treatment component that helps preserve final answers and original ToolSandbox side-effect calls.

**Figure 3. Tool generation, validation, and repair loop.** Generated helpers are not promoted from generation alone. They must pass static/schema checks, minefield tests, live smoke validation, natural adoption, contribution review, and safety gates before scale-up. Force-call diagnostics can reveal latent value but are never counted as promotion evidence.

**Figure 4. Matched ToolSandbox validation design.** Baseline and SAGE arms share a sealed manifest and model policy. Controls may use task-level cache with provenance; SAGE/candidate arms are fresh. Outcome/task completion is primary, canonical/reference score is secondary, and paired statistical comparisons are reported with safety, leakage, cache, and reproducibility controls.

**Figure 5. SAGE one-page infographic.** SAGE operates as a self-evolving flywheel: it observes deterministic capability gaps, generates small side-effect-free helpers, validates and repairs them, stores accepted tools in a registry, routes only relevant helpers, and evaluates whether natural reuse improves matched ToolSandbox outcomes under leakage, cache, and safety controls. The HTML version uses selectable sections and clickable generated-tool pills that reveal actual Python helper examples from the self-evolving v71 registry.

## Chapter 3 Placement

Use Figure 1 in the system overview subsection, Figure 2 in the SAGE architecture subsection, Figure 3 in the self-evolving tool lifecycle subsection, Figure 4 in the formal evaluation design subsection, and Figure 5 for presentations, professional forum posts, and high-level Chapter 3 orientation.

## Boundary Statement

These figures describe the current SAGE Praxis methodology and live self-evolving system. They do not by themselves promote any experimental registry or treatment into protected final evidence.
