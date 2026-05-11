# Praxis Final-Hardening Review

Status: setup complete; matched formal500 validation pending.

This document is a review supplement, not protected final evidence. Praxis is
not promoted into the protected final registry by this branch.

## Objective

Determine whether the frozen Praxis BridgePack result is ready for protected
claim review by auditing the experimental source, reproducing it under clean
matched conditions, and statistically comparing it against best3 and V2.6.

## Frozen Inputs

- Formal manifest: `docs/sage_protocol/manifests/v2_1_formal_500.json`
- Formal manifest SHA-256:
  `093547e7a89e704e67d4cea85fd96511063becd0b5542ba3abf21c242453bbbf`
- best3 registry copy SHA-256:
  `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- V2.6 registry copy SHA-256:
  `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`
- Praxis registry SHA-256:
  `7867cde8c8709f31efb02006e8c0743bbf890f2ede1519de99155e4631614349`
- Locked experimental summary SHA-256:
  `41db7fed0e0997cfb691791abca59d47941a2f076951153382b17df3242e2dcc`

## Final-Run Controls

- Generation: off.
- Candidate/SAGE task cache: off.
- OpenAI response cache: disabled.
- Control cache: `use-if-eligible`.
- Control cache match policy:
  `task_name_agent_user_base_tool_policy_min3`.
- Current full500 cache plan: 500 cached controls, 0 fresh controls.
- Routing evidence: disabled.
- Diagnostic force-call env vars: forbidden by preflight.
- Low-quality cohort override: forbidden by preflight.
- No code or registry changes are allowed between matched formal arms.

## Planned Matched Arms

| Arm | Registry | Treatment notes |
| --- | --- | --- |
| best3 reference | `artifacts/praxis_final_hardening/registries/best3_reference` | Protected best3 registry copy under review runtime |
| V2.6 reference | `artifacts/praxis_final_hardening/registries/v2_6_reference` | V2.6 contact-scalar registry copy under review runtime |
| Praxis frozen BridgePack | `artifacts/praxis_final_hardening/registries/praxis_bridgepack_frozen_candidate` | Frozen Praxis registry under review runtime |

The first matched set intentionally does not import Praxis actor/router bridge
policy. If Praxis requires that branch-only policy to reproduce, the result will
be classified as a registry plus bridge-policy treatment rather than
registry-only value.

## Pending Evidence

Formal500 run outputs, dashboard links, statistical analysis, safety results,
and treatment classification will be added after preflight passes and the
matched arms complete.
