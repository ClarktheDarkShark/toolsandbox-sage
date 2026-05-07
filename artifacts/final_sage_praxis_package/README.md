# Final SAGE Praxis Package

Created: 2026-05-04T06:06:50.697792
Updated: 2026-05-07 for V2.6 expanded contact-scalar evidence.

## Broad Locked Claim

Decision: frozen best3 passed the primary relative outcome/task-completion target at 100, 250, 500, and 1,032 scenarios.

Frozen best3 registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
Registry SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`

Best3 tools:
- `relative_day_time_to_timestamp`
- `resolve_search_window_or_bounds`
- `select_record_by_timestamp_extreme`

Formal 100: `outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428`
Formal 250: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222`
Formal 500: `outputs/v2_1_formal500_best3_parallel_20260504_232126/full_benchmark_20260504_232130`
Formal 1032: `outputs/v2_1_formal1000_best3_full_20260505_004901/full_benchmark_20260505_004905`

Primary formal250 result: outcome lift `+20.52%`.

## V2.6 Expanded Candidate Evidence

Expanded contact-scalar registry: `artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json`
Expanded registry SHA-256: `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`

Expanded tools are best3 plus:
- `plan_contact_lookup_query`
- `extract_contact_field_from_search_result`
- `plan_contact_search_from_scalar_constraint`

Matched gap-enriched frozen250:
- Outcome `0.6040 -> 0.6235`
- No-current-helper-fit `55.2% -> 45.6%`
- Relative gap reduction `17.39%`
- Runtime/helper side-effect incidents `0 / 0`

Original formal250 expanded validation:
- Expanded outcome `0.5986`
- Expanded vs preserved best3 outcome `+0.1249`
- Feedback no-current-helper-fit `52.0% -> 46.0%`
- Runtime/helper side-effect incidents `0 / 0`

Expanded 500 validation:
- Expanded outcome `0.6822`
- Expanded vs preserved best3 500 outcome `+0.1299`
- Feedback no-current-helper-fit `67.6% -> 62.8%`
- Runtime/helper side-effect incidents `0 / 0`
- Protocol gate PASS

## Key Package Files

- `final_claim_summary.md`
- `final_evidence_index.md`
- `limitations_and_non_claims.md`
- `v2_6_matched_gap_evidence_lock_report.md`
- `v2_6_contact_scalar_routing_audit.md`
- `v2_6_original_formal250_expanded_report.md`
- `v2_6_expanded_500_report.md`
