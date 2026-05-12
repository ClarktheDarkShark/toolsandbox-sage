# Praxis Combined Treatment Classification

Decision label: `PROMISING_COMBINED_TREATMENT_FORMAL500_POSITIVE_NOT_PROTECTED_CLAIM_READY`

This document classifies the high-lift Praxis recovery result separately from
the registry-only Praxis repair v2 result.

## Classification

| Question | Answer |
| --- | --- |
| Registry-only improvement? | No for this high-lift result. The bridge policy was enabled. |
| Actor/router bridge-policy improvement? | Partly. The policy improved natural helper adoption, chaining, final-answer retention, and side-effect preservation recognition. |
| Registry + bridge-policy combined treatment? | Yes. This is the correct classification for the completed formal500 v2 run. |
| Harness/scoring/cache artifact? | No evidence found. Scoring was unchanged; controls used task-level cache with provenance; candidate/SAGE arm was fresh. |
| Treatment to review | Frozen Praxis registry SHA `7867cde8c8709f31efb02006e8c0743bbf890f2ede1519de99155e4631614349` plus `SAGE_PRAXIS_BRIDGE_POLICY=combined`. |

## Evidence Basis

Formal500 run:
`outputs/praxis_combined_bridge_policy/formal500_full_v2_bridge_repair_rapid_cache_polars1/full_benchmark_20260511_190013`

Task Compare dashboard:
`http://127.0.0.1:62543/outputs/praxis_combined_bridge_policy/formal500_full_v2_bridge_repair_rapid_cache_polars1/full_benchmark_20260511_190013/dashboard/task_compare.html`

| Metric | Baseline | Praxis combined | Delta |
| --- | ---: | ---: | ---: |
| Canonical/reference | 0.670025 | 0.757369 | +0.087344 |
| Outcome/task completion | 0.594872 | 0.839943 | +0.245071 |

Relative canonical lift: `+13.04%`.
Relative outcome lift: `+41.20%`.

Runtime exceptions: `0`.
Helper failures / side-effect incidents: `0 / 0`.

## Integrity Controls

- Generation off.
- Candidate/SAGE task cache off.
- OpenAI response cache disabled.
- Control cache `use-if-eligible`, with `500 cached / 0 fresh`.
- Routing evidence disabled.
- Diagnostic force-call environment variables absent.
- RapidAPI cache read-only as an external-service fixture, not as task evidence.
- No scenario selection by cache availability.
- No label, expected-answer, scenario-ID, task-string, or prior-SAGE-trace leakage found.

## Claim Boundary

This result can support a future combined-treatment claim if a dedicated
matched ablation confirms the effect under the same committed runtime. It
should not be represented as registry-only Praxis value.

The registry-only Praxis repair v2 result remains separately documented in
`docs/sage_protocol/praxis_treatment_classification_final.md`.

## Required Next Review

Before any protected final-claim update, run a matched ablation transaction:

- best3 reference
- V2.6 reference
- Praxis registry-only repair v2
- Praxis combined bridge-policy v2

All arms should use the formal500 manifest, same runtime/scorer, cached controls
where eligible, fresh candidate arms, generation off, OpenAI response cache
disabled, routing evidence disabled or pinned, and no diagnostic force-call
environment variables.
