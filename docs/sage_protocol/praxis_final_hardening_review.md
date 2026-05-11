# Praxis Final-Hardening Review

Status: registry-only outcome lift reproduced, but blocked for protected-claim
promotion by helper side-effect preservation failures.

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
- Preflight report:
  `artifacts/praxis_final_hardening/preflight/preflight_registry_only_formal500.json`

## Branch Lineage

- Review branch: `review/praxis-final-hardening`
- Protected-base commit:
  `2898c7e502ec75ad5e1fc65c5ffe7a80f5605f4a`
- Experimental source commit:
  `7793c8ca29ab4e121d302c777c4e4ad273226470`
- Setup commit used for matched runs:
  `cfe35647dbbb703b4508a709f75dfee0f1f85036`
- Imported from experiment: frozen Praxis registry copy, locked experimental
  summary, reference registry copies, and control-arm task-level baseline cache
  policy.
- Intentionally not imported: experimental actor/router bridge policy,
  side-effect checker changes, scoring changes, run-script changes, and
  dashboard/export changes.

## Final-Run Controls

- Generation: off.
- Candidate/SAGE task cache: off.
- OpenAI response cache: disabled by command flag.
- Control cache: `use-if-eligible`.
- Control cache match policy:
  `task_name_agent_user_base_tool_policy_min3`.
- Control cache result: 500 cached controls and 0 fresh controls for each arm.
- Control cache manifest hash:
  `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- Routing evidence: disabled.
- Diagnostic force-call env vars: absent and forbidden by preflight.
- Low-quality cohort override: absent and forbidden by preflight.
- No code or registry changes occurred between matched formal arms.

## Matched Formal500 Results

| Arm | Registry | Outcome | Run-vs-control outcome lift | Canonical | Exact successes | Runtime exceptions | Helper side-effect failures |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| best3 reference | `artifacts/praxis_final_hardening/registries/best3_reference` | 0.655285 | 0.060413 | 0.722734 | 94 | 0 | 0 |
| V2.6 reference | `artifacts/praxis_final_hardening/registries/v2_6_reference` | 0.664286 | 0.069414 | 0.713519 | 89 | 0 | 0 |
| Praxis frozen BridgePack | `artifacts/praxis_final_hardening/registries/praxis_bridgepack_frozen_candidate` | 0.696169 | 0.101297 | 0.722681 | 105 | 0 | 13 |

Run roots:

- best3:
  `outputs/praxis_final_hardening/registry_only/best3_reference_formal500/full_benchmark_20260510_223731`
- V2.6:
  `outputs/praxis_final_hardening/registry_only/v2_6_reference_formal500/full_benchmark_20260510_223731`
- Praxis:
  `outputs/praxis_final_hardening/registry_only/praxis_bridgepack_formal500/full_benchmark_20260510_223731`

## Statistical Summary

See `docs/sage_protocol/praxis_matched_formal500_statistical_report.md` and
`artifacts/praxis_final_hardening/praxis_matched_formal500_statistics.json`.

| Comparison | Outcome diff | 95% CI | p-value | Canonical diff | Exact diff |
| --- | ---: | --- | ---: | ---: | ---: |
| V2.6 minus best3 | 0.009002 | [-0.026157, 0.043690] | 0.6029 | -0.009215 | -0.010000 |
| Praxis minus best3 | 0.040884 | [0.004697, 0.078220] | 0.0283 | -0.000054 | 0.022000 |
| Praxis minus V2.6 | 0.031883 | [-0.009376, 0.072576] | 0.1199 | 0.009162 | 0.032000 |

Outcome/task completion remains primary. Praxis reproduces a positive
registry-only mean outcome lift against best3 and V2.6 under the
protected-base runtime. The Praxis-vs-best3 paired outcome interval is positive;
the Praxis-vs-V2.6 interval crosses zero. Canonical/reference behavior is mixed
and does not drive the conclusion.

## Helper Visibility And Calls

| Arm | Helper visible events | Helper called events | Visible-not-called | Called helper names |
| --- | ---: | ---: | ---: | --- |
| best3 | 203 | 123 | 80 | 3 |
| V2.6 | 291 | 163 | 128 | 6 |
| Praxis | 552 | 205 | 347 | 11 |

Praxis increased exposure substantially. That did not create runtime
exceptions, but it did expose side-effect preservation failures in bridge-style
helpers.

## Safety Result

- Runtime exceptions: best3=0, V2.6=0, Praxis=0.
- Helper side-effect preservation failures: best3=0, V2.6=0, Praxis=13.
- Praxis side-effect report:
  `outputs/praxis_final_hardening/registry_only/praxis_bridgepack_formal500/full_benchmark_20260510_223731/candidate/full_benchmark_candidate_agent_gpt-4o-mini_user_GPT_4_o_2024_05_13_05_10_2026_22_38_10/side_effect_preservation_report.jsonl`
- Praxis side-effect report SHA-256:
  `81bf6ee740368bc83f8444f5c608e108d352f5029533d52695d4b430d5fd1aaa`

Per the review protocol, any side-effect incident stops promotion review. Praxis
is therefore not protected-claim ready in registry-only form.

## Dashboard Checks

- Praxis Task Focus dashboard opened in the in-app browser with zero console
  errors:
  `http://127.0.0.1:62333/outputs/praxis_final_hardening/registry_only/praxis_bridgepack_formal500/full_benchmark_20260510_223731/dashboard/task_focus.html`
- Praxis standard dashboard opened in the in-app browser with zero console
  errors:
  `http://127.0.0.1:62333/outputs/praxis_final_hardening/registry_only/praxis_bridgepack_formal500/full_benchmark_20260510_223731/dashboard/index.html`
- Task Compare was not generated by this review branch run.

## Treatment Classification

Initial review treatment:

1. Frozen Praxis registry copy.
2. Protected-base final-hardening runtime.
3. Imported control-arm-only task-level baseline cache policy.
4. Routing evidence disabled.
5. No imported Praxis actor/router bridge policy.

Conclusion: Praxis reproduced as a registry-only outcome-lift treatment under
the protected-base runtime, but failed safety review because helper
side-effect preservation failures appeared. The result is promising but blocked,
not protected-claim ready.

## Decision

Decision label: `BLOCKED: praxis_registry_only_side_effect_preservation_failures`

Recommended next step: do not update the protected final claim. Either redesign
the failing bridge helpers so they pass the protected-base side-effect checker,
or explicitly audit an isolated registry plus bridge-policy/checker treatment
behind a feature flag and rerun matched validation from scratch with zero
side-effect failures.
