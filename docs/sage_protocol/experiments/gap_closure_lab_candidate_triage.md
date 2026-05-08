# SAGE Gap-Closure Lab Candidate Triage

Experimental evidence only. Generated tools listed here are not part of protected final evidence unless separately validated and promoted through a reviewed claim process.

## Current Status
No candidate tools have been generated on this branch yet. Campaign preflight on 2026-05-08 blocked live SAGE generation because `OPENAI_API_KEY` is not available in the execution environment.

## Triage Table
| Candidate | Source experiment | Registry path | Validation status | Natural call status | Force-call diagnosis | Called-subset outcome | VNC | Safety | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| None yet | GCL-001 | None | Blocked before generation | Blocked before exposure | Blocked before force diagnostics | Not available | Not available | No incidents | Resume candidate generation only after model credentials are available |

## Required Diagnosis Labels
- hidden by routing
- visible but not called
- called with bad arguments
- schema/interface mismatch
- output not useful
- output not final-answer-ready
- unsafe side-effect risk
- overlap/interference with best3
- true negative value

## Promotion Guardrail
Force-call success can justify repair or rerun, but cannot justify promotion. A candidate must demonstrate natural calls, positive called-subset outcome, zero runtime exceptions, zero helper side-effect incidents, and downstream value on unseen tasks.
