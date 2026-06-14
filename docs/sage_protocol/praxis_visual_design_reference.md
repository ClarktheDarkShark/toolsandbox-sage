# SAGE Praxis Visual Design Reference

Last updated: 2026-06-14

Purpose: durable design guidance for the charts, graphics, diagrams, tables, and LaTeX fragments used in the SAGE praxis paper. Use this file before creating or revising assets under `docs/sage_protocol/figures/` or adding table/figure blocks to the LaTeX draft.

## Operating Standard

SAGE paper visuals should read like peer-reviewed CS/AI methodology and evaluation figures: compact, evidence-focused, self-contained, reproducible, and defensible under close review.

Default output choices:

| Need | Preferred artifact | Rationale |
|---|---|---|
| Exact numeric comparison, run metadata, controls, gates | Native LaTeX table | Precise values, good typography, easy citation and revision. |
| Architecture, lifecycle, evidence boundary, workflow | Vector source plus exported PNG | Diagrams need crisp text and arrows at paper scale. Keep SVG/PDF as source of truth. |
| Main quantitative result | Reproducible chart exported as PDF/SVG plus PNG preview | Reviewers need rapid visual comparison and exact values in captions/tables. |
| Screenshots or dashboard excerpts | Raster image only when the real UI matters | Avoid screenshot figures unless the paper claim depends on the rendered interface. |
| Pseudocode or protocol logic | LaTeX algorithm, listing, or compact monospaced block | Do not use screenshots for code or algorithms. |

Current repo context:

- Chapter 3 LaTeX draft: `docs/sage_protocol/chapter3_sage_methodology_latex_draft.tex`
- Current figure inventory: `docs/sage_protocol/chapter3_methodology_figures.md`
- Current figure assets: `docs/sage_protocol/figures/`
- Current regeneration command in README: `python scripts/render_chapter3_sage_figures.py`
- Additional methodology diagram renderer noted in the figure inventory: `python3 scripts/render_sage_methodology_diagrams.py`

## Source Base Surveyed

The conventions below synthesize visualization research, journal/venue author guidance, and recent AI-agent benchmark papers.

Foundational visualization and perception:

- Cleveland and McGill, "Graphical Perception: Theory, Experimentation, and Application to the Development of Graphical Methods" (JASA, 1984): position and length encodings are read more accurately than angle, area, volume, and color intensity. Source: https://faculty.washington.edu/aragon/classes/hcde511/s12/readings/cleveland84.pdf
- Heer and Bostock, "Crowdsourcing Graphical Perception" (CHI, 2010): graphical-perception experiments can be replicated at scale and reinforce the importance of empirically grounded chart choices. Source: https://vis.stanford.edu/files/2010-MTurk-CHI.pdf
- Mackinlay, "Automating the Design of Graphical Presentations of Relational Information" (ACM TOG, 1986): chart design should consider expressiveness and effectiveness, matching data type and task to visual encoding. Source: https://dl.acm.org/doi/10.1145/22949.22950
- Munzner, "A Nested Model for Visualization Design and Validation" (IEEE TVCG, 2009): start from domain problem and task abstraction before choosing encodings or implementation. Source: https://www.cs.ubc.ca/labs/imager/tr/2009/NestedModel/NestedModel.pdf

Scientific figure practice:

- Rougier, Droettboom, and Bourne, "Ten Simple Rules for Better Figures" (PLOS Computational Biology, 2014): identify the audience and message, adapt to the support medium, and do not trust software defaults. Source: https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1003833
- Weissgerber et al., "Beyond Bar and Line Graphs" (PLOS Biology, 2015): avoid hiding distributions behind mean-only bar/line graphs; show raw data or distributional structure when possible. Source: https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.1002128
- Correll and Gleicher, "Error Bars Considered Harmful" (IEEE TVCG, 2014): standard mean-plus-error encodings can change viewer decisions and are often misunderstood; uncertainty should be chosen deliberately. Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC6214189/
- Wickham, Cook, and Hofmann, "Visualizing Statistical Models: Removing the Blindfold" (Statistical Analysis and Data Mining, 2015): show models in data space and expose collections/processes, not only final summaries. Source: https://vita.had.co.nz/papers/model-vis.html
- Crameri, Shephard, and Heron, "The misuse of colour in science communication" (Nature Communications, 2020): avoid rainbow and red-green schemes; use perceptually uniform, color-vision-deficiency-aware palettes. Source: https://www.nature.com/articles/s41467-020-19160-7

Table and LaTeX guidance:

- Fear, "Publication quality tables in LaTeX" / `booktabs`: professional tables use sparse horizontal rules, no vertical rules, and careful spacing. Source: https://tug.ctan.org/macros/latex/contrib/booktabs/booktabs.pdf
- ACM LaTeX best practices: figures and tables use standard environments; ACM has template-specific placement/caption conventions. Source: https://www.acm.org/publications/taps/latex-best-practices
- ACM/SIGACCESS figure descriptions: captions and accessibility descriptions are different; figures should have equivalent textual descriptions when target venues support them. Source: https://www.acm.org/publications/taps/describing-figures/
- IEEE graphics guidance: prefer vector or high-resolution graphics; avoid enlarging small graphics; line art needs stronger resolution than ordinary raster images. Source: https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/create-graphics-for-your-article/resolution-and-size/
- Nature/Springer figure conventions: panel labels, labels, units, contrast, and line widths must remain readable after reduction. Source: https://www.nature.com/srep/author-instructions/submission-guidelines

Relevant AI-agent and benchmark paper exemplars:

- ToolSandbox uses an early trajectory/system figure, benchmark-comparison tables, ablation tables, category-statistic tables, and detailed captions that explain what each figure/table is evidence for. Source: https://arxiv.org/html/2408.04682v1
- SWE-agent uses a first-page conceptual interface figure, interface screenshots/schematics, compact result tables, ablation tables, and pass@k plots; the exact tables carry benchmark claims while figures explain mechanism and variance. Source: https://arxiv.org/pdf/2405.15793
- AgentBench and WebArena use benchmark overview diagrams, model comparison tables, category breakdowns, and failure-analysis summaries. Sources: https://proceedings.iclr.cc/paper_files/paper/2024/file/e9df36b21ff4ee211a8b71ee8b7e9f57-Paper-Conference.pdf and https://arxiv.org/abs/2307.13854

## What Research Papers Typically Do

Common strong pattern in CS/AI methodology and benchmark papers:

1. Figure 1 establishes the system, task setting, or conceptual contract.
2. A methods diagram explains components, data flow, lifecycle states, or evaluation setup.
3. Tables carry exact benchmark comparisons, ablations, dataset statistics, and configuration details.
4. Charts visualize the main contrast, variance, distribution, or trend that is hard to parse from numbers alone.
5. Captions are written as mini-interpretations, not just labels.
6. Figure panels are ordered to match the narrative, usually from setup to mechanism to evidence.
7. Appendix figures/tables carry exhaustive details; main-text figures/tables carry claims and reader orientation.

Implication for SAGE: the main paper should not overload diagrams with every implementation detail. Main-text visuals should answer one of these questions:

- What is SAGE?
- What changes relative to the baseline?
- What is the evaluation contract?
- What evidence supports the claim?
- Where are the safety, leakage, and reproducibility boundaries?
- Which generated tools or tool families caused the measured effect?

## SAGE Figure And Table Taxonomy

| SAGE need | Best form | Main design constraints |
|---|---|---|
| High-level SAGE mechanism | One-panel lifecycle diagram or 3-panel schematic | Show the actor, generated tools, registry, routing, reuse, and evidence logging without implementation clutter. |
| ToolSandbox evaluation design | Matched-arm architecture diagram | Make baseline and SAGE arms visually symmetric; make treatment differences explicit. |
| Generated-tool lifecycle | State machine or gated flow | Use gates for validation, repair, promotion, natural use, and exclusion from claims. |
| Evidence boundary and claim ladder | Layered diagram or step ladder | Separate diagnostics, discovery evidence, validation evidence, and protected claims. |
| Main control-vs-SAGE result | Paired dot plot, slope chart, or compact forest plot | Emphasize paired task-level delta and uncertainty; include n and denominators. |
| Final-task success rates | Dot-and-interval plot or table plus small chart | Avoid mean-only bars if per-task variation matters. |
| Score by task family/stratum | Small multiples, heatmap, or grouped dot plot | Keep categories in protocol order or ordered by effect size; show n. |
| Tool contribution | Funnel, flow, or table | Distinguish accepted, visible, naturally called, outcome-relevant, and safety-clean tools. |
| Ablations | LaTeX table | Put control, variant, primary metric, delta, and interpretation in adjacent columns. |
| Failure or regression analysis | Matrix table plus optional stacked bar | Use taxonomy labels that map to audit artifacts; include counts and examples. |
| Safety/leakage controls | Checklist table | Include rule, enforcement point, evidence artifact, and claim implication. |
| Reproducibility package | Table | Include manifest, code hash, registry hash, cache policy, model roles, output root, dashboard. |
| Algorithmic protocol | LaTeX algorithm/listing | Keep exact control flow in text, not in an image. |

## Chart Rules

Use charts only when spatial comparison helps the reader more than a table.

Quantitative encoding:

- Prefer position on a common scale for primary comparisons.
- Use length for simple totals and counts.
- Use color for grouping or semantics, not for precise magnitude.
- Avoid pies, donuts, 3D charts, exploded bars, and decorative perspective.
- Avoid stacked bars unless the task is part-to-whole comparison and each segment matters.
- Avoid dual y-axes unless there is a strong reason and the caption explains the mapping.

Paired SAGE results:

- Show paired deltas when the same task appears under control and SAGE.
- Prefer a paired slope/dot chart for small numbers of families or a forest plot for many families.
- Show the primary endpoint first: outcome/task completion before canonical/reference similarity.
- Include the denominator: `control=.../n`, `SAGE=.../n`, or `n paired tasks`.
- If a chart uses cached controls and fresh SAGE arms, state that in the caption or footnote.

Distribution and uncertainty:

- For small n, show individual points plus summary.
- For larger n, use box/violin/ridge only when the distributional shape matters.
- Show confidence intervals, bootstrap intervals, or paired uncertainty bands when claims depend on uncertainty.
- Label whether intervals are 95% CI, standard error, standard deviation, bootstrap CI, or credible interval.
- Never imply statistical certainty from decorative error bars.

Axes and labels:

- Axes must start at zero for bar-length comparisons unless there is a stated statistical reason.
- Dot plots and forest plots may use nonzero ranges, but the scale must be obvious.
- Units belong in axis labels or table headers, not repeated in every cell.
- Use direct labels where feasible; legends are acceptable but should not force back-and-forth reading.
- Use light grid lines only when they help read values.

Ordering:

- Use protocol order when sequence matters.
- Use effect-size order when comparison matters.
- Use grouped semantic order for safety gates and lifecycle states.
- Avoid alphabetical ordering unless the table is a lookup reference.

## Diagram Rules

Diagrams should explain mechanism, boundary, or evaluation design, not decorate the paper.

Composition:

- One primary message per figure.
- 4 to 7 major objects per panel.
- Left-to-right for execution flow; top-to-bottom for layered trust/evidence hierarchy.
- Keep labels inside objects short; put interpretation in the caption.
- Use panel labels when a figure has multiple claims.
- Use consistent node widths and alignment; visual raggedness reads as conceptual uncertainty.

Recommended SAGE visual grammar:

| Element | Meaning |
|---|---|
| Rounded rectangle | Component, process, actor, tool, or validation step. |
| Cylinder or database icon | Registry, cache, manifest, artifact store. |
| Diamond | Decision or validation gate. |
| Solid arrow | Runtime data/control flow counted inside the claim boundary. |
| Dashed arrow | Diagnostic, repair, optional, or excluded-from-claim path. |
| Thick boundary box | Evaluation/protocol/claim boundary. |
| Red outline or red text | Blocked, rejected, prohibited, leakage, or safety exclusion. |
| Amber outline | Diagnostic, caution, not-yet-promoted, or review-needed state. |
| Green outline | Accepted, safety-clean, promoted, or SAGE treatment path. |
| Slate outline | Baseline, neutral infrastructure, or unchanged environment. |

Boundary handling:

- If a generated tool does not mutate environment state, show that boundary visually.
- If diagnostic force-calls are excluded from evidence, use a dashed path and label it as diagnostic.
- If baseline caching is allowed but SAGE task evidence must be fresh, show cache provenance explicitly.
- If a figure is about protected final claims, include leakage/cache/safety controls in the visual or caption.

Text density:

- Diagrams for the main text should remain readable at one-column or 0.90 `\textwidth`.
- Avoid full sentences inside boxes.
- Avoid tiny tables inside figures unless the figure is a table-like result graphic.
- Use callouts sparingly; each callout should correspond to a reviewer concern or methodological boundary.

## Table Rules

Tables are the default for exact evidence.

Use a table when:

- Values must be read exactly.
- The result has many conditions, models, tool families, or runs.
- The table is a reproducibility record or evidence index.
- The claim depends on conditions, controls, or caveats.

Use a chart instead when:

- The reader must compare shape, trend, distribution, or paired deltas.
- Exact values can go in the caption or companion table.

LaTeX table house style:

- Use `booktabs`: `\toprule`, `\midrule`, `\bottomrule`.
- Avoid vertical rules and boxed cells.
- Use `tabularx` for text-heavy tables.
- Use `siunitx` for aligned decimals and percentages.
- Use `threeparttable` or table notes for cache policy, denominators, model settings, and statistical notes.
- Use `longtable` only for appendix-scale evidence lists.
- Keep table width to `\textwidth`; use `p{}` columns or `X` columns instead of tiny fonts whenever possible.
- Use `\footnotesize` or `\small`; avoid going below readable size in main text.
- Use bold only for the primary winner or central claim cell, not for every local maximum.
- Keep precision consistent: if outcome is reported to one decimal point, do not mix with three-decimal claims unless the statistic requires it.
- Put units in headers: `Outcome (\%)`, `Tokens`, `Delta (pp)`, `Cost (USD)`.
- Include denominators for rates: `23/40 (57.5\%)`.

Recommended SAGE result-table columns:

| Column | Purpose |
|---|---|
| Run / Condition / Tool family | Identifies the unit being compared. |
| n | Prevents percentage-only ambiguity. |
| Control | Baseline score or success count. |
| SAGE | Treatment score or success count. |
| Delta | Absolute change, preferably percentage points for rates. |
| Relative lift | Optional; use only after absolute delta is clear. |
| Generated-tool evidence | Visible, called, accepted, or contribution summary. |
| Safety/cache note | Makes the evidence boundary auditable. |

## Captions And Descriptions

Every figure/table should be independently interpretable.

Caption template for figures:

```text
Figure X. Short noun phrase naming the visual. One sentence explains the setup and what is encoded. One sentence states the key takeaway or boundary. Include n, endpoint, cache/fresh status, and exclusion rule when relevant.
```

Caption template for tables:

```text
Table X. Short noun phrase naming the evidence. One sentence explains rows, columns, primary endpoint, and denominator. Footnote cache/model/protocol caveats rather than burying them in the title.
```

Accessibility description:

- If the target LaTeX class supports `\Description{...}` or equivalent, add it for every figure.
- A description is not the caption. It should say what the visual structure is and what information a nonvisual reader needs.
- For charts, include the main trend and any major exception.
- For diagrams, include the flow order and boundary meaning.
- For tables, real LaTeX tables are preferable to image tables because screen readers and downstream conversion tools can parse them.

## Color And Typography

Use the existing SAGE palette unless a target venue requires grayscale:

| Role | Color |
|---|---|
| Ink | `#172033` |
| Muted text | `#596579` |
| Standard line | `#9aa7b7` |
| Light line | `#d8e0ea` |
| Baseline / protocol blue | `#2563eb` |
| SAGE / accepted green | `#059669` |
| Diagnostic / caution amber | `#d97706` |
| Blocked / rejected red | `#dc2626` |
| Generation / analysis violet | `#7c3aed` |
| Neutral slate | `#64748b` |

Color rules:

- Do not rely on red/green alone; pair color with labels, symbols, line styles, or position.
- Avoid rainbow color maps.
- Use sequential perceptually uniform maps for magnitude.
- Use diverging maps only when there is a meaningful zero or neutral midpoint.
- Use no more than 5 semantic colors in one figure.
- Ensure grayscale print still preserves the hierarchy.

Typography:

- Use sans-serif inside generated image figures, matching the current SVG style (`Arial, Helvetica, sans-serif`).
- Use LaTeX typography for tables and algorithms.
- Final scaled figure text should remain at least about 7 to 8 pt.
- Lines should remain at least about 1 pt after scaling.
- Use normal letter spacing.
- Use title case only for figure titles or panel headers; ordinary labels should be sentence case where feasible.

## LaTeX Patterns

Generic figure:

```latex
\begin{figure}[tbp]
    \centering
    \includegraphics[width=0.92\textwidth]{figures/sage_result_delta.pdf}
    \caption{Paired control-vs-SAGE outcome deltas by task family. Points show paired family-level outcome differences; intervals show 95\% bootstrap confidence intervals across paired tasks.}
    \label{fig:sage_result_delta}
\end{figure}
```

ACM-style figure with description, if using `acmart`:

```latex
\begin{figure}[tbp]
    \centering
    \includegraphics[width=\linewidth]{figures/sage_tool_lifecycle.pdf}
    \caption{Generated-tool lifecycle from gap observation through validation, registry acceptance, routing, natural reuse, and contribution logging.}
    \Description{A left-to-right flow diagram shows task evidence entering a gap detector, tool generator, validation and repair gates, an accepted registry, routed tool bundles, actor reuse, and evidence logging. Dashed paths indicate repair or diagnostic-only flows excluded from promotion evidence.}
    \label{fig:sage_tool_lifecycle}
\end{figure}
```

Result table:

```latex
\begin{table}[tbp]
\centering
\small
\caption{Matched SAGE outcome summary by evaluation condition.}
\label{tab:sage_matched_summary}
\begin{threeparttable}
\begin{tabularx}{\textwidth}{l r r r r X}
\toprule
\textbf{Condition} & \textbf{n} & \textbf{Control} & \textbf{SAGE} & \textbf{Delta} & \textbf{Evidence note} \\
\midrule
Online build & 250 & 112/250 & 151/250 & +15.6 pp & Fresh SAGE arm; generated-tool visibility and calls logged. \\
Frozen registry & 250 & 112/250 & 146/250 & +13.6 pp & Generation disabled; accepted registry reused. \\
\bottomrule
\end{tabularx}
\begin{tablenotes}
\footnotesize
\item Percentages should be added when final values are locked. Delta is absolute percentage-point change.
\end{tablenotes}
\end{threeparttable}
\end{table}
```

Text-heavy method table:

```latex
\begin{table}[tbp]
\centering
\footnotesize
\caption{SAGE evidence controls and claim implications.}
\label{tab:sage_evidence_controls}
\begin{tabularx}{\textwidth}{p{3.0cm} X X}
\toprule
\textbf{Control} & \textbf{Rule} & \textbf{Claim implication} \\
\midrule
No answer leakage & Generated tools must not encode hidden labels, expected answers, scenario IDs, or prior SAGE traces. & Required for protected generated-tool contribution claims. \\
\addlinespace
No force-call evidence & Diagnostic force-calls may reveal latent utility but are excluded from promotion evidence. & Natural actor adoption must be reported separately. \\
\bottomrule
\end{tabularx}
\end{table}
```

Packages commonly needed:

```latex
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{array}
\usepackage{siunitx}
\usepackage{threeparttable}
\usepackage{subcaption}
```

Only include packages that the target class permits.

## Asset Workflow

For each figure:

1. Define the figure claim in one sentence.
2. Identify whether the evidence is conceptual, exact numeric, distributional, paired, or procedural.
3. Choose table, chart, diagram, or algorithm form from the taxonomy above.
4. Create or update a reproducible source script when data or drawing logic is nontrivial.
5. Export vector source (`.svg` or `.pdf`) and PNG preview when useful.
6. Save assets under `docs/sage_protocol/figures/`.
7. Add or update the LaTeX block only after the asset is readable at final size.
8. Check color, grayscale, text size, line width, caption, label, and source-data traceability.

For generated charts from run data:

- Store or reference the exact data source: manifest, JSON summary, CSV export, dashboard export, or run artifact.
- Make chart scripts deterministic.
- Avoid manual spreadsheet transformations unless the transformed table is saved as an artifact with provenance.
- Keep chart labels in code, not hand-edited post-export.
- If data are preliminary, label the figure or caption as draft/preliminary.

For diagrams:

- Keep the renderer or source SVG editable.
- Do not edit only the PNG.
- If a renderer produces SVG, PNG, and HTML companions, regenerate the full set together.
- Keep diagram text separate from evidence claims when the evidence is still pending.

## Review Checklist

Before considering a visual ready for the paper:

- Does it answer one explicit paper question?
- Is the key message visible within 5 seconds?
- Is every axis, unit, denominator, and endpoint defined?
- Is `n` shown for every rate or aggregate?
- Are control and SAGE arms visually and methodologically comparable?
- Are cache/fresh policies disclosed where they affect interpretation?
- Are generated-tool visibility, natural call, and diagnostic force-call evidence separated?
- Are safety/leakage boundaries shown or captioned where relevant?
- Would the figure remain readable if printed in grayscale?
- Would the figure remain readable at one-column or dissertation-page scale?
- Are text labels at final size large enough?
- Is the caption self-contained?
- Is the LaTeX `\label{}` placed after `\caption{}`?
- Is the source file or script reproducible?
- Is the asset free of hidden-answer leakage, scenario-specific answer strings, or unreviewed claim language?

## Common Pitfalls To Avoid

- Mean-only bars for paired task outcomes.
- Percentages without denominators.
- "Lift" without first showing absolute delta.
- Overloaded architecture diagrams with every class/module in the codebase.
- Screenshots of tables or code.
- Default rainbow palettes.
- Red/green-only distinctions.
- Tiny legends and axis labels.
- Axis truncation that exaggerates differences.
- Captions that only repeat the title.
- Tables with vertical lines, boxed cells, or inconsistent decimal precision.
- Diagrams where dashed, solid, red, and green arrows are not semantically defined.
- Mixing protected final evidence with exploratory diagnostics in the same visual without boundary labels.

## Candidate Visual Package For The SAGE Praxis Paper

Main text:

| Slot | Visual | Current status |
|---|---|---|
| Figure 1 | High-level SAGE lifecycle | Existing asset likely usable after paper-scale review. |
| Figure 2 | Paired ToolSandbox/SAGE evaluation architecture | Existing asset likely usable after boundary/caption tightening. |
| Figure 3 | Generated-tool validation and repair lifecycle | Existing asset likely usable after gate labels are checked. |
| Figure 4 | Evidence boundary and claim ladder | Existing asset likely usable if final claim labels match locked evidence. |
| Figure 5 | Main matched outcome delta | Needed once final result values are locked. |
| Figure 6 | Generated-tool contribution flow/counts | Existing contribution-flow asset or new chart depending final data. |
| Table 1 | Research questions and hypotheses | Existing draft table, should be reviewed for precision and final labels. |
| Table 2 | Evaluation conditions | Existing draft table, likely keep as LaTeX. |
| Table 3 | Main result summary | Needed from locked run artifacts. |
| Table 4 | Safety/leakage/reproducibility controls | Existing draft table, should align with final evidence boundary. |
| Table 5 | Tool portfolio/contribution summary | Needed from final registry/contribution artifacts. |

Appendix:

| Slot | Visual/table |
|---|---|
| Run ledger table | Manifest, run root, model roles, cache policy, code/registry hashes, dashboard path. |
| Task-family breakdown | Heatmap or table with n, control, SAGE, delta, called-tool subset. |
| Ablation table | Online build vs frozen registry vs disabled components, where available. |
| Failure taxonomy | Counts, examples, causal class, mitigation status. |
| Registry table | Accepted tools, function class, validation evidence, promotion status, safety notes. |
| Figure-source inventory | Asset path, generation command, source data, caption, paper placement. |

## SAGE-Specific Interpretation Rules

- Outcome/task completion is primary. Canonical/reference similarity is secondary unless a specific section is about route fidelity.
- A SAGE gain should be shown as paired task-level lift, not just aggregate model performance.
- Generated-tool contribution must separate accepted, visible, naturally called, and outcome-relevant tools.
- Diagnostic force-call results may be useful in appendix or methods discussion, but use dashed visual treatment and state that they are excluded from promotion evidence.
- Side-effect boundaries are central to SAGE. If a figure mentions generated tools, it should clarify whether original ToolSandbox tools remain responsible for state mutation.
- Cache policy is part of the evidence, not a footnote afterthought. Include it in tables or captions for final-claim visuals.
- Do not allow figure text to claim broader self-improvement than the methodology supports. SAGE evolves the system-level tool portfolio, not model weights.
