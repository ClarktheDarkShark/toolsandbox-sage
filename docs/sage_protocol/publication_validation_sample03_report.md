# Corrected-Tree Publication Validation Sample 03 — 2026-09-02

## Decision

**PASS — ENGINEERING RELEASE GATE SATISFIED.** The corrected-tree strict
fresh-control sample completed both 1,032-task arms. The independent verifier
passed every integrity, lifecycle, and predeclared outcome-only gate.
Outcome/task-completion similarity is the sole performance endpoint for this
decision.

This single sample is not confirmatory evidence and is not used to accept or
reject H1, H2, or H3. The final ten-online/ten-frozen campaign has been
prepared but has not been executed; it still requires explicit researcher
approval.

## Preserved Identity

- Run: `publication_validation_20260902_strict_sample03`
- Local run path:
  `outputs/publication_validation/publication_validation_20260902_strict_sample03/native_action/online_build_full_20260902_071820`
- Validated release commit: `519d6fa3739f4c933487073c5888f7576e2a646a`
- Validated release tree: `718ef02a85f0490d7e4dbbec4192567a1bd10b9d`
- Clean public-history runtime checkpoint:
  `5bf1a1a3377bb913cb11fdcd1228f18003300714` (identical validated tree)
- Publication report SHA-256:
  `f8516686e8a62d0c26c9d76b1122f7d0c811619deeffea86b7ef58d5022d21b6`
- Runtime: CPython 3.12.7 on Darwin/arm64 with the verified 108-distribution
  publication lock
- Model: `gpt-4o-mini`
- Fixed ToolSandbox timestamp: `1784832588`

The full run and machine-readable publication report are preserved as local
ignored artifacts at the path above. This tracked report records their
identity and results without substituting for the raw evidence.

## Outcome Results

| Outcome measure | Control | SAGE | Difference |
|---|---:|---:|---:|
| Mean task-completion similarity | 0.5087366331780064 | 0.7986035515693737 | +0.2898669183913673 |
| Exact outcome successes | 220 | 443 | +223 |

- Relative outcome lift: `56.97779548144769%`.
- Tasks with an explicit outcome evaluator: `800` per arm.
- Paired outcome gains: `413`.
- Paired outcomes preserved: `283`.
- Paired outcome regressions: `104`.

The candidate outcome exceeded the predeclared historical lower envelope of
`0.776051529737963`, and the same-run relative lift exceeded the predeclared
`10%` minimum. Both outcome performance gates passed.

## Integrity and Lifecycle Verification

| Check | Observed | Required | Status |
|---|---:|---:|---|
| Control tasks | 1,032 | 1,032 | Pass |
| SAGE tasks | 1,032 | 1,032 | Pass |
| Outcome-scored tasks per arm | 800 | 800 | Pass |
| Runtime exceptions per arm | 0 | 0 | Pass |
| Cached control tasks | 0 | 0 | Pass |
| Repository whole-response replay hits | 0 | 0 | Pass |
| Reflection source | Same-run fresh control | Same-run fresh control | Pass |
| Accepted generated tools | 30 | At least 1 | Pass |
| Reuse events | 1,909 | At least 1 | Pass |
| Tasks calling generated tools | 801 | At least 1 | Pass |

The verifier also reconciled the complete task order, arm records, model-call
events, and usage metadata. OpenAI-managed prompt-prefix computation was
recorded separately; it did not replay a stored response or task result.

## Campaign Boundary

The verified campaign manifest is:

`artifacts/chapter4_evidence/chapter4_strict_fresh_control_10x_20260902/campaign_manifest.json`

- Campaign ID: `chapter4_strict_fresh_control_10x_20260902`.
- Initial prepared-manifest SHA-256:
  `af5045911ac96e2bfdd67fac5aed3ce5b22cae6389ca94832d340b6d719d4853`.
- Status: **prepared/unstarted**.
- Queue: ten online runs and ten matched frozen-registry runs.

The manifest pins this passing sample report and validated runtime commit
`519d6fa3739f4c933487073c5888f7576e2a646a` / tree
`718ef02a85f0490d7e4dbbec4192567a1bd10b9d`. This documentation-only follow-up
does not change the campaign's runtime identity. Manifest preparation and
verification made no model calls and did not authorize execution.

## Decision Label

`PASS_ENGINEERING_SAMPLE_AWAITING_EXPLICIT_CAMPAIGN_EXECUTION_APPROVAL`
