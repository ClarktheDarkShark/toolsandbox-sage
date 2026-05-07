# V2.6 Current-Code Non-External 500 Matched Report

## Purpose

Compare the current-code frozen best3 portfolio against the current-code expanded V2.6 contact-scalar portfolio on the same non-external 500 manifest, with generation OFF and no code edits between matched arms.

This run set was required because earlier V2.6 expanded 500 evidence was compared primarily against preserved best3 evidence. The current-code matched result gives the more defensible same-code, same-manifest comparison.

## Preflight

- Commit: `f7aaffa5c02cff26a355dfcb4a540e33b91fde7d`
- Branch: `sage/init-toolsandbox`
- Registry check: PASS
- Targeted tests: `125 passed, 2 warnings`
- `git diff --check`: PASS
- Generation: OFF
- Control cache mode: `use-if-eligible`
- Contribution export: active
- Feedback packet export: active after each arm

## Registries

- Best3 registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Best3 registry SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Expanded V2.6 registry: `artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json`
- Expanded V2.6 registry SHA-256: `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`

## Manifest

- Manifest: `docs/sage_protocol/manifests/v2_1_formal_500.json`
- Manifest SHA-256: `093547e7a89e704e67d4cea85fd96511063becd0b5542ba3abf21c242453bbbf`
- Mode: `full_benchmark`
- Cohort quality: PASS
- Scenario count: 500
- Distinct base families: 54
- Largest family share: 2.4%

Composition notes:

| Category Token | Count |
|---|---:|
| Contact | 123 |
| Message | 78 |
| Phone | 82 |
| Relationship | 35 |
| Search | 163 |
| Reminder | 190 |
| Insufficient information | 119 |
| Wifi | 44 |
| Location | 36 |
| Battery | 56 |
| Holiday | 35 |
| External | 0 |

Static expected helper-fit counts from the manifest include `no_current_helper_fit: 200`, `resolve_search_window_or_bounds: 106`, `relative_day_time_to_timestamp: 67`, `select_record_by_timestamp_extreme: 47`, and several unpromoted/parked lanes such as side-effect prep, service/precondition, visible-record selector, days-between, and recency-action selector. This broader distribution dilutes the contact-scalar opportunity density relative to the matched gap250.

## Commands

Best3 arm:

```bash
OPENAI_API_KEY="$(conda run -n lifelong python -c 'import os; print(os.environ["OPENAI_API_KEY"])')" PYTHONPATH=src:. python scripts/run_sage_protocol.py --mode full_benchmark --manifest docs/sage_protocol/manifests/v2_1_formal_500.json --registry-dir artifacts/registry_frozen_best3_claim --generation off --control-cache use-if-eligible --output-root outputs/v2_6_current_code_500_best3 --dashboard-port 5686
```

Expanded arm:

```bash
OPENAI_API_KEY="$(conda run -n lifelong python -c 'import os; print(os.environ["OPENAI_API_KEY"])')" PYTHONPATH=src:. python scripts/run_sage_protocol.py --mode full_benchmark --manifest docs/sage_protocol/manifests/v2_1_formal_500.json --registry-dir artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack --generation off --control-cache use-if-eligible --output-root outputs/v2_6_current_code_500_expanded --dashboard-port 5687
```

Feedback export commands:

```bash
PYTHONPATH=src:. python scripts/export_v2_6_feedback_packets.py --run-root outputs/v2_6_current_code_500_best3/full_benchmark_20260507_145553 --run-id v2_6_current_code_500_best3 --output-root artifacts/summaries/v2_6_feedback_packets
PYTHONPATH=src:. python scripts/export_v2_6_feedback_packets.py --run-root outputs/v2_6_current_code_500_expanded/full_benchmark_20260507_165427 --run-id v2_6_current_code_500_expanded --output-root artifacts/summaries/v2_6_feedback_packets
```

## Artifact Lock

Best3 arm:

- Run root: `outputs/v2_6_current_code_500_best3/full_benchmark_20260507_145553`
- Paired comparison SHA-256: `fbfc2f86839d2221925f6eab05a957120c9b7e754659376d5f0d63ea68c2237d`
- Helper contribution SHA-256: `e3a3a0cb0ac41c7d8da534ec65484762f21e3d69d572bc2fff73b3494d6f2da3`
- Control cache report SHA-256: `f7f9fb43859830bffd2e9e77bc0596a0837ce36ececebc5bb553cff76e91a0c1`
- Feedback summary SHA-256: `4c77b4f6cf6ddb643768106d3cd39d1f8c0a8dc37c9bba345df796549c88bdbd`
- Feedback packets SHA-256: `128fa2bbc6e26f7b6b12900271c8d3390cfce8c7875661f3a8ec80bfc143985f`
- Dashboard: `http://127.0.0.1:5686/outputs/v2_6_current_code_500_best3/full_benchmark_20260507_145553/dashboard/index.html`
- Task Focus dashboard: `http://127.0.0.1:5686/outputs/v2_6_current_code_500_best3/full_benchmark_20260507_145553/dashboard/task_focus.html`

Expanded arm:

- Run root: `outputs/v2_6_current_code_500_expanded/full_benchmark_20260507_165427`
- Paired comparison SHA-256: `3ac838638cb1a02188c8b981c2c53ecd4b74d79f241b79593a93582dc023e65e`
- Helper contribution SHA-256: `e16a0720b94a91ab6017c078b82d745ed5b2cd3d0a39a3b66c19901e51c10351`
- Control cache report SHA-256: `7d56d5000ca9aed0e9a509be4930200ac353ca4dc4d3557d4cb2d16cc54475e6`
- Feedback summary SHA-256: `fcbafe5515a8810936642dd154c718d8d20a295321c8b88994c6dcdb05fe0ef8`
- Feedback packets SHA-256: `8f5f4f25236a1727ac755c087c8251562bd7d9d6d4e518ca19fd7c8f45d443f1`
- Dashboard: `http://127.0.0.1:5687/outputs/v2_6_current_code_500_expanded/full_benchmark_20260507_165427/dashboard/index.html`
- Task Focus dashboard: `http://127.0.0.1:5687/outputs/v2_6_current_code_500_expanded/full_benchmark_20260507_165427/dashboard/task_focus.html`

Both dashboards were HTTP-checked and opened in the browser.

## Control Cache

| Arm | Source | Cached | Fresh | Misses | Manifest Hash |
|---|---:|---:|---:|---:|---|
| Best3 | mixed | 435 | 65 | 65 | `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2` |
| Expanded | mixed | 467 | 33 | 33 | `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2` |

The baseline cache was applied task-by-task. Fresh controls were run only for tasks with fewer than 3 compatible completed control records.

## Matched Result

| Metric | Current-Code Best3 | Current-Code Expanded V2.6 | Expanded - Best3 |
|---|---:|---:|---:|
| Candidate outcome | 0.6590 | 0.6692 | +0.0101 |
| Candidate canonical/reference | 0.7137 | 0.7362 | +0.0225 |
| Exact successes | 92 | 93 | +1 |
| Runtime exceptions | 0 | 0 | 0 |
| Helper side-effect incidents | 0 | 0 | 0 |
| Protocol gate | PASS | PASS | same |
| Route-mismatch qualified | false | false | same |

Run-vs-control metrics:

| Arm | Control Outcome | Candidate Outcome | Delta | Control Canonical | Candidate Canonical | Delta | Exact |
|---|---:|---:|---:|---:|---:|---:|---:|
| Best3 | 0.4973 | 0.6590 | +0.1617 | 0.6553 | 0.7137 | +0.0583 | 30 -> 92 |
| Expanded | 0.4887 | 0.6692 | +0.1804 | 0.6509 | 0.7362 | +0.0853 | 29 -> 93 |

The direct same-code, same-manifest 500 comparison is positive for expanded V2.6 on outcome, canonical/reference, and exact successes.

## Helper-Fit Gap

| Metric | Best3 | Expanded | Relative Change |
|---|---:|---:|---:|
| Feedback no-current-helper-fit share | 67.6% | 62.8% | 7.10% reduction |
| Feedback no-current-helper-fit count | 338 | 314 | -24 |

This is positive gap movement, but it does not meet the 10% relative helper-fit gap-reduction target on the broader 500 sample. The expanded portfolio therefore should not be claimed as having closed the broad 500 helper-fit gap.

## Helper Contribution Summary

Best3 helper contribution:

| Helper | Visible | Called | VNC | Called Outcome Delta | Called Canonical Delta | Side Effect | Runtime |
|---|---:|---:|---:|---:|---:|---:|---:|
| `relative_day_time_to_timestamp` | 51 | 45 | 6 | +0.4058 | +0.2039 | 0 | 0 |
| `resolve_search_window_or_bounds` | 94 | 42 | 52 | +0.2307 | +0.1775 | 0 | 0 |
| `select_record_by_timestamp_extreme` | 58 | 45 | 13 | +0.3346 | +0.3417 | 0 | 0 |

Expanded helper contribution:

| Helper | Visible | Called | VNC | Called Outcome Delta | Called Canonical Delta | Side Effect | Runtime |
|---|---:|---:|---:|---:|---:|---:|---:|
| `plan_contact_lookup_query` | 24 | 13 | 11 | +0.5667 | +0.1070 | 0 | 0 |
| `extract_contact_field_from_search_result` | 24 | 6 | 18 | +0.4139 | +0.0055 | 0 | 0 |
| `plan_contact_search_from_scalar_constraint` | 40 | 14 | 26 | +0.3633 | +0.0124 | 0 | 0 |
| `relative_day_time_to_timestamp` | 51 | 46 | 5 | +0.2966 | +0.1596 | 0 | 0 |
| `resolve_search_window_or_bounds` | 94 | 44 | 50 | +0.2560 | +0.1546 | 0 | 0 |
| `select_record_by_timestamp_extreme` | 58 | 42 | 16 | +0.3942 | +0.3608 | 0 | 0 |

The new contact-scalar helpers were genuinely called and had positive called-subset contribution versus control. `plan_contact_search_from_scalar_constraint` was now naturally called at scale, unlike earlier original250 current-code evidence.

## Expanded-Vs-Best3 Subset Analysis

| Subset | N | Mean Outcome Delta | Mean Canonical Delta |
|---|---:|---:|---:|
| All matched scenarios | 500 | +0.0078 | +0.0225 |
| Contact surface | 163 | +0.0266 | +0.0791 |
| Message surface | 24 | +0.0466 | -0.0040 |
| Reminder surface | 190 | -0.0194 | -0.0004 |
| New tool called | 27 | +0.0262 | +0.0616 |
| New tool visible-not-called only | 21 | +0.1060 | +0.1130 |
| Expanded no-current-helper-fit | 314 | +0.0120 | +0.0332 |

Per-new-helper direct expanded-vs-best3 called subsets:

| Helper Called | N | Mean Outcome Delta | Mean Canonical Delta |
|---|---:|---:|---:|
| `plan_contact_lookup_query` | 13 | -0.2308 | +0.0723 |
| `extract_contact_field_from_search_result` | 6 | -0.3333 | -0.0004 |
| `plan_contact_search_from_scalar_constraint` | 14 | +0.2649 | +0.0517 |

This explains why the broad result is positive but not a clean contact-pack victory. The scalar-contact planner is additive in this 500 run; the two earlier contact helpers remain positive versus control but are mixed when compared directly against current-code best3 on the same 500 tasks.

## Why The 10% Helper-Fit Lift Did Not Hold At 500

The broad 500 sample differs materially from the matched gap250 sample:

| Manifest | Scenarios | Contact Tokens | Message Tokens | Reminder Tokens | Insufficient-Info Tokens | Static No-Current-Fit |
|---|---:|---:|---:|---:|---:|---:|
| Original250 | 250 | 56 | 32 | 112 | 48 | 119 |
| Matched gap250 | 250 | 80 | 48 | 112 | 48 | 114 |
| Non-external500 | 500 | 123 | 78 | 190 | 119 | 200 |

Key conclusions:

- The matched gap250 intentionally concentrated contact/message positives and best3 preservation lanes; it was designed to test helper-fit closure.
- The non-external500 is broader, with 54 base families and a much larger insufficient-information/service/side-effect footprint.
- The contact-scalar pack reduces no-current-helper-fit by 24 tasks on the 500 run, but many remaining no-fit tasks are outside contact-scalar scope.
- The broader 500 still shows positive outcome and exact-success movement, but helper-fit closure reaches only 7.10% relative rather than the 10% target.
- The next gap-closing work should target non-contact no-fit lanes, especially safe insufficient-information handling and reminder/action lanes, not keep over-tuning contact helpers.

## Decision

`expanded portfolio non-harmful but variance-limited`

The expanded V2.6 portfolio is current-code positive on non-external500, with zero runtime exceptions and zero helper side-effect incidents. It does not meet the 10% broad helper-fit gap-reduction target on this 500 sample, so the final claim should state that V2.6 is current-code positive and gap-improving but not a broad 500 gap-closure replacement for best3.
