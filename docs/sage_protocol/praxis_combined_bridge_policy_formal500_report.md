# Praxis Combined Bridge-Policy Formal500 Report

Status: experimental combined-treatment review evidence, not a protected final-claim update.

## Treatment

Praxis is classified here as the frozen Praxis registry plus a feature-flagged actor/checker bridge policy (`SAGE_PRAXIS_BRIDGE_POLICY=combined`). This is not a registry-only claim.

The bridge policy is a general SAGE operating policy: it improves natural helper adoption, helper chaining, final-answer retention, scrambled tool-name compatibility, and checker-visible preservation of required original ToolSandbox side-effect calls. It does not force helper calls, use labels, encode expected answers, or change scoring.

## Formal500 Result

| Metric | Value |
|---|---:|
| Tasks | 500 |
| Baseline canonical | 0.670025 |
| SAGE canonical | 0.757369 |
| Canonical delta | +0.087344 |
| Relative canonical lift | +13.04% |
| Baseline outcome | 0.594872 |
| SAGE outcome | 0.839943 |
| Outcome delta | +0.245071 |
| Relative outcome lift | +41.20% |
| Runtime exceptions | 0 |
| Helper side-effect incidents | 0 |

This recovers and exceeds the previously cited high-lift run: prior dashboard `0.670 -> 0.751` (`+0.081`, `+12.1%`) and outcome `0.595 -> 0.813` (`+0.219`); this run produced `0.670 -> 0.757` (`+0.087`, `+13.0%`) and outcome `0.595 -> 0.840` (`+0.245`).

## Paired Statistics Versus Control

| Comparison | Mean delta | 95% bootstrap CI | sign-flip p | Gains | Regressions | Preserved |
|---|---:|---|---:|---:|---:|---:|
| Canonical/reference | +0.087344 | [+0.059364, +0.114717] | 0.0001 | 315 | 114 | 71 |
| Outcome/task completion | +0.245071 | [+0.209620, +0.281405] | 0.0001 | 252 | 41 | 91 |

## Reference Context

These reference rows use same-manifest formal500 artifacts, but they are not a fresh same-transaction ablation after the combined bridge-policy code was introduced. They should be used as orientation until a dedicated matched ablation is run.

| Arm | Canonical | Outcome | Run-vs-control outcome delta | Exact successes | Runtime exceptions |
|---|---:|---:|---:|---:|---:|
| best3 reference | 0.704683 | 0.659956 | +0.065084 | 90 | 0 |
| V2.6 reference | 0.728769 | 0.668039 | +0.073167 | 97 | 0 |
| Praxis registry-only repair v2 | 0.724125 | 0.706948 | +0.112076 | 109 | 0 |
| Praxis combined bridge-policy v2 | 0.757369 | 0.839943 | +0.245071 | 179 | 0 |

## Cache And Leakage

- Controls used task-level cache: `500 cached / 0 fresh`, manifest hash `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`.
- Candidate/SAGE arm was fresh: candidate task cache off, OpenAI response cache disabled, generation off.
- Routing evidence disabled; diagnostic force-call env vars absent.
- RapidAPI cache was read-only external-service fixture only, SHA-256 `3ed7732443c44d7d26e0f46ac32fa2e09fc773278368c6f13131021afafdbf25`.
- No labels, expected answers, scenario IDs, benchmark facts, or prior SAGE traces were used as outcome evidence.

## Artifacts

- Run root: `outputs/praxis_combined_bridge_policy/formal500_full_v2_bridge_repair_rapid_cache_polars1/full_benchmark_20260511_190013`
- Task Compare dashboard: `http://127.0.0.1:62543/outputs/praxis_combined_bridge_policy/formal500_full_v2_bridge_repair_rapid_cache_polars1/full_benchmark_20260511_190013/dashboard/task_compare.html`
- Paired comparison SHA-256: `d853009f7d6e490dec80a0468a2fbc3c9ed5582afcb8e1d7c2e653be4204f261`
- Machine-readable summary: `artifacts/praxis_combined_bridge_policy/summary/praxis_combined_bridge_policy_formal500_v2_statistics.json`, SHA-256 `e064e9f3cec303d2a657063132549e8cfda2fdb1a946e0405649449ca21ddf6f`
- Gap packet: `artifacts/praxis_combined_bridge_policy/summary/praxis_combined_bridge_policy_formal500_v2_gap_packets.json`.

## Decision

Decision label: `PROMISING_COMBINED_TREATMENT_FORMAL500_POSITIVE_NOT_PROTECTED_CLAIM_READY`.

Recommended next action: do not promote as registry-only. If this is pursued for protected claims, run a dedicated matched ablation transaction that includes best3, V2.6, Praxis registry-only, and Praxis combined bridge-policy under the same committed runtime, then lock statistics and safety review.
