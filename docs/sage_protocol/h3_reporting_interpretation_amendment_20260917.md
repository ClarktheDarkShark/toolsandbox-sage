# H3 Reporting Interpretation Amendment

## Purpose

This amendment records the interpretation used for reporting Hypothesis 3 in
the final paper and its derived Chapter 4 dashboard. It does not alter the
preserved campaign manifest, run selection, outcomes, confidence intervals, or
execution artifacts.

## Provenance

- The paper stated H3 as a 30 percent outcome-lift hypothesis on tasks where a
  generated tool was selected and called before the final campaign began. That
  statement is present in paper commit
  `7ab3da61597ff50d9c73cf7939f8a81f81bad635` from 2026-09-07.
- The final campaign plan later classified the called-task analysis as
  selection-conditioned and descriptive, with no support decision. That rule
  is present in code commit `984a14ca4fe608513842add906eb4c6bbc820661`
  from 2026-09-10 and remains unchanged in the preserved selected-cohort
  manifest.
- On 2026-09-17, the researcher directed that H3 be reported against the
  paper-stated association threshold.

## Reporting decision

H3 is reported as **Supported for the paper-stated selection-conditioned
association** because the observed relative lift was 47.17 percent and the
paired-bootstrap 95 percent confidence interval was 44.28 to 50.19 percent,
fully above the paper's 30 percent threshold.

This label is not a causal reclassification. Generated-tool-called status is
observed after treatment and was not randomized. Accordingly, the dashboard,
tables, and paper must retain the limitation that this result does not by
itself establish that a generated-tool call caused the improvement. H1 and H2
remain the campaign's confirmatory analyses; H3 is a supported noncausal
association hypothesis.

## Decision

**READY_FOR_PAPER_UPDATE**
