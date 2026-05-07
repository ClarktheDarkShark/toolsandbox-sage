# Final Evidence Index

## Protected Best3 Broad Claim

- Frozen best3 registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Registry SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Formal100 run: `outputs/v2_formal100_clean_20260504_025812_frozen_best3_relative_20260504_050423/validate_100_20260504_050428`
- Formal250 run: `outputs/v2_formal250_clean_20260504_034104_frozen_best3_relative_20260504_052217/validate_250_20260504_052222`
- Formal500 run: `outputs/v2_1_formal500_best3_parallel_20260504_232126/full_benchmark_20260504_232130`
- Formal1032 run: `outputs/v2_1_formal1000_best3_full_20260505_004901/full_benchmark_20260505_004905`
- Formal250 evidence lock: `docs/sage_protocol/v2_formal250_evidence_lock_report.md`
- Formal250 metric audit: `docs/sage_protocol/v2_formal250_metric_audit_report.md`
- Best3 contribution audit: `docs/sage_protocol/v2_best3_helper_contribution_audit.md`

## V2.6 Matched Gap-Closure Evidence

- Report: `docs/sage_protocol/v2_6_matched_gap_evidence_lock_report.md`
- Matched manifest: `artifacts/summaries/v2_6_gap_closure_250/cohort_manifest.json`
- Matched manifest SHA-256: `5019602d637362a03317ac4349b9b89a2a790ff69bd5a72203d8dad9516f60e6`
- Best3 matched run: `outputs/v2_6_gap_closure_250_best3/validate_250_20260507_023114`
- Expanded matched run: `outputs/v2_6_gap_closure_250_expanded_rerun/validate_250_20260507_033336`
- Expanded paired comparison SHA-256: `e8dacf3c36c542ee156b2625ba3d91ca10e92fa66c0f964e3c478b9f61be140f`
- Expanded helper contribution SHA-256: `2310ec2158dc288b4e83b45ab9c45bdba699e8306208c48c5fa6e2d43dcab4ba`

## V2.6 Routing Audit

- Report: `docs/sage_protocol/v2_6_contact_scalar_routing_audit.md`
- Code path repaired before current-code matched campaign: `src/sage_ts/runtime/routing_scorer.py`
- Test path: `tests/unit/test_runtime_routing_scorer.py`
- Decision: `routing repaired for original250`

## V2.6 Current-Code Matched Original250 Evidence

- Report: `docs/sage_protocol/v2_6_current_code_original250_matched_report.md`
- Original formal250 manifest: `artifacts/summaries/v2_formal250_clean_20260504_034104/cohort_manifest.json`
- Manifest SHA-256: `c7ec4010f8fc3ea3ca1f914b8d5a980f70e51494c75cc3d9f9148b0b3604a47e`
- Current-code best3 run: `outputs/v2_6_current_code_original250_best3/validate_250_20260507_131235`
- Current-code best3 paired comparison SHA-256: `bf94553bcf4b74eebb4d65dd14c192801a6fa96703a9ce4f79eabc1e8c650c8c`
- Current-code best3 helper contribution SHA-256: `21ce0effb15f382961666f721d5daba71a91ac16f80317969ad609030a504545`
- Current-code expanded run: `outputs/v2_6_current_code_original250_expanded/validate_250_20260507_141441`
- Current-code expanded paired comparison SHA-256: `1793ca3700fa75de42300b16021fd80b07f1b640d836940625119396cc5f74f3`
- Current-code expanded helper contribution SHA-256: `4d65b558092d499e36c1ef7bcb085418713d0d18259eb9ac9ae59ee11929f533`
- Feedback summaries: `artifacts/summaries/v2_6_feedback_packets/v2_6_current_code_original250_best3/feedback_summary.json`, `artifacts/summaries/v2_6_feedback_packets/v2_6_current_code_original250_expanded/feedback_summary.json`

## V2.6 Current-Code Matched Non-External500 Evidence

- Report: `docs/sage_protocol/v2_6_current_code_500_matched_report.md`
- Manifest: `docs/sage_protocol/manifests/v2_1_formal_500.json`
- Manifest SHA-256: `093547e7a89e704e67d4cea85fd96511063becd0b5542ba3abf21c242453bbbf`
- Current-code best3 run: `outputs/v2_6_current_code_500_best3/full_benchmark_20260507_145553`
- Current-code best3 paired comparison SHA-256: `fbfc2f86839d2221925f6eab05a957120c9b7e754659376d5f0d63ea68c2237d`
- Current-code best3 helper contribution SHA-256: `e3a3a0cb0ac41c7d8da534ec65484762f21e3d69d572bc2fff73b3494d6f2da3`
- Current-code expanded run: `outputs/v2_6_current_code_500_expanded/full_benchmark_20260507_165427`
- Current-code expanded paired comparison SHA-256: `3ac838638cb1a02188c8b981c2c53ecd4b74d79f241b79593a93582dc023e65e`
- Current-code expanded helper contribution SHA-256: `e16a0720b94a91ab6017c078b82d745ed5b2cd3d0a39a3b66c19901e51c10351`
- Feedback summaries: `artifacts/summaries/v2_6_feedback_packets/v2_6_current_code_500_best3/feedback_summary.json`, `artifacts/summaries/v2_6_feedback_packets/v2_6_current_code_500_expanded/feedback_summary.json`

## Current-Code Synthesis

- Synthesis report: `docs/sage_protocol/v2_6_current_code_evidence_synthesis.md`
- Decision: `expanded portfolio non-harmful but variance-limited`
- Gap250 current-code rerun: deferred; locked matched-gap evidence already exists.
- Expanded 1032 current-code validation: deferred; current-code 500 gives broad non-external evidence and 1032 contains sparse/external lanes outside contact-scalar scope.

## Final Package

- Package directory: `artifacts/final_sage_praxis_package/`
- Primary summary: `artifacts/final_sage_praxis_package/final_claim_summary.md`
- Evidence index: `artifacts/final_sage_praxis_package/final_evidence_index.md`
- Limitations: `artifacts/final_sage_praxis_package/final_limitations_and_future_work.md`
- V2.6 current-code reports copied into final package for reference.
