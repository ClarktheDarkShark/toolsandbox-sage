# SAGE Gap-Closure Lab Ledger

Experimental evidence only. Nothing in this ledger modifies protected best3, formal, V2.6, or final-package evidence.

| ID | Date | Experiment | Sample | Tools/registry | Model use | Baseline cache | SAGE cache | Result | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GCL-000 | 2026-05-07 | Branch and manifest setup | No benchmark run | No candidate tools | No model calls | Not used | Not used | Created clean experimental worktree, split manifest builder, reports, and validation test | Ready for seed/dev analysis |
| GCL-001 | 2026-05-08 | Harness compatibility repair and campaign preflight | Runner splits: 20/60/100/250; no benchmark run | No candidate tools | Requested live OpenAI-backed ToolSandbox/SAGE execution; resolved model calls blocked because `OPENAI_API_KEY` is absent | Control cache not used; cache manifest hash not used for scenario selection | SAGE cache not used; candidate arms not run | Added runner aliases, `pilot_20`/`expanded_60` modes, manifest preflight, and machine-readable blocker artifact. Preflight passed manifest/hash/split checks and failed only on missing OpenAI credentials. | BLOCKED: live campaign cannot run fairly without model credentials |

## Required Family Status

All required families remain untested rather than parked. The blocker is shared by every family because each fair-chance evaluation requires fresh ToolSandbox/SAGE model calls.

| Family | Status | Fair-chance state | Root cause |
| --- | --- | --- | --- |
| 1. Many small deterministic tools | Blocked | Not started | Missing `OPENAI_API_KEY` prevents SAGE generation, live validation, natural adoption, and outcome comparison |
| 2. Tool chaining | Blocked | Not started | Same live model credential blocker |
| 3. Regular refinement loop | Blocked | Not started | Same live model credential blocker |
| 4. Robust generation/validation/repair loop | Blocked | Not started | Same live model credential blocker |
| 5. Diverse-task pain-point synthesis | Blocked | Seed split available, no label analysis run | Same live model credential blocker for downstream generation and validation |
| 6. Larger generation model / smaller execution model | Blocked | Not started | Same live model credential blocker |
| 7. Actor-policy and affordance | Blocked | Harness supports policy experiments, no run | Same live model credential blocker |
| 8. Router/composer | Blocked | Runner aliases repaired, no run | Same live model credential blocker |
| 9. Safe insufficient-information detector | Blocked | Not started | Same live model credential blocker |
| 10. Final-answer-ready transformation tools | Blocked | Not started | Same live model credential blocker |
| 11. Contrastive generation from feedback packets | Blocked | Not started | Same live model credential blocker |
| 12. Leave-family-out validation | Blocked | Manifest supports disjoint seed/unseen families | Same live model credential blocker |
| 13. Portfolio ablation and interaction testing | Blocked | Expanded/confirm/scale splits available | Same live model credential blocker |
| 14. Adaptive repair from failed calls | Blocked | Not started | Same live model credential blocker |
| 15. Synthetic validation lab | Blocked for SAGE evidence | Static harness possible, no SAGE candidate to validate | Missing credentials block candidate generation and live callability checks |
| 16. Bandit routing | Blocked | Not started | Same live model credential blocker |
| 17. Description compression vs richness | Blocked | Not started | Same live model credential blocker |
| 18. Oracle-free pain-point classifier | Blocked | Not started | Same live model credential blocker |

## Decision Rules
- Keep: unseen outcome improves or matches best3, called-subset outcome is positive, natural calls are real, and safety incidents are zero.
- Refine: latent force-call value exists but routing, actor affordance, schema, or final-answer-readiness blocks natural use.
- Park: no safe latent value, unsafe side-effect risk, label leakage risk, or severe interference with best3.
- Scale: only after confirmation-positive evidence with no code changes between matched arms.

## Required Fields For Future Rows
Every experiment row must include sample size, split manifest/hash, tools tested, requested/resolved model, generation settings, baseline cache eligibility/fresh/cached counts, SAGE cache status, natural calls, VNC, called-subset outcome, runtime exceptions, helper side-effect incidents, result, and decision.
