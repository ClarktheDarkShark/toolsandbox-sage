# V2.6 Current-Code Original250 Matched Report

## Purpose

Compare the current-code frozen best3 portfolio against the current-code expanded V2.6 contact-scalar portfolio on the original formal250 manifest, with generation OFF and no code edits between matched arms.

Outcome/task-completion is primary. Canonical/reference similarity is secondary.

## Preflight

- Commit: `f7aaffa5c02cff26a355dfcb4a540e33b91fde7d`
- Branch: `sage/init-toolsandbox`
- Working tree at preflight: clean
- Registry check: PASS
- Targeted tests: `125 passed, 2 warnings`
- `git diff --check`: PASS
- Control cache mode: `use-if-eligible`
- Generation: OFF
- Contribution export: active
- Feedback packet export: active after each arm

Preflight commands:

```bash
PYTHONPATH=src:. python scripts/migrate_registry.py --check-only artifacts/registry_frozen_best3_claim/registry_manifest.json artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json
PYTHONPATH=src:. pytest tests/unit/test_runtime_routing_scorer.py tests/unit/test_helper_contribution.py tests/unit/test_control_baseline_cache.py tests/unit/test_task_strata.py tests/unit/test_candidate_gate.py tests/unit/test_tool_generator.py tests/unit/test_online_birth.py -q
git diff --check
```

## Registries

- Best3 registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Best3 registry SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Expanded V2.6 registry: `artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json`
- Expanded V2.6 registry SHA-256: `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`

Expanded V2.6 tools:

- `relative_day_time_to_timestamp`
- `resolve_search_window_or_bounds`
- `select_record_by_timestamp_extreme`
- `plan_contact_lookup_query`
- `extract_contact_field_from_search_result`
- `plan_contact_search_from_scalar_constraint`

## Manifest

- Manifest: `artifacts/summaries/v2_formal250_clean_20260504_034104/cohort_manifest.json`
- Manifest SHA-256: `c7ec4010f8fc3ea3ca1f914b8d5a980f70e51494c75cc3d9f9148b0b3604a47e`
- Mode: `validate_250`
- Cohort quality: PASS
- Scenario count: 250
- Distinct base families: 32

Composition notes:

- Contact-token scenarios: 56
- Message-token scenarios: 32
- Reminder-token scenarios: 112
- Search-token scenarios: 87
- Insufficient-information-token scenarios: 48
- Static expected `no_current_helper_fit`: 119

## Commands

Best3 arm:

```bash
OPENAI_API_KEY="$(conda run -n lifelong python -c 'import os; print(os.environ["OPENAI_API_KEY"])')" PYTHONPATH=src:. python scripts/run_sage_protocol.py --mode validate_250 --manifest artifacts/summaries/v2_formal250_clean_20260504_034104/cohort_manifest.json --registry-dir artifacts/registry_frozen_best3_claim --generation off --control-cache use-if-eligible --output-root outputs/v2_6_current_code_original250_best3 --dashboard-port 5684
```

Expanded arm:

```bash
OPENAI_API_KEY="$(conda run -n lifelong python -c 'import os; print(os.environ["OPENAI_API_KEY"])')" PYTHONPATH=src:. python scripts/run_sage_protocol.py --mode validate_250 --manifest artifacts/summaries/v2_formal250_clean_20260504_034104/cohort_manifest.json --registry-dir artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack --generation off --control-cache use-if-eligible --output-root outputs/v2_6_current_code_original250_expanded --dashboard-port 5685
```

Feedback export commands:

```bash
PYTHONPATH=src:. python scripts/export_v2_6_feedback_packets.py --run-root outputs/v2_6_current_code_original250_best3/validate_250_20260507_131235 --run-id v2_6_current_code_original250_best3 --output-root artifacts/summaries/v2_6_feedback_packets
PYTHONPATH=src:. python scripts/export_v2_6_feedback_packets.py --run-root outputs/v2_6_current_code_original250_expanded/validate_250_20260507_141441 --run-id v2_6_current_code_original250_expanded --output-root artifacts/summaries/v2_6_feedback_packets
```

## Artifact Lock

Best3 arm:

- Run root: `outputs/v2_6_current_code_original250_best3/validate_250_20260507_131235`
- Paired comparison SHA-256: `bf94553bcf4b74eebb4d65dd14c192801a6fa96703a9ce4f79eabc1e8c650c8c`
- Helper contribution SHA-256: `21ce0effb15f382961666f721d5daba71a91ac16f80317969ad609030a504545`
- Control cache report SHA-256: `46222e9d5969fcde3bb9eed020bc9c21fa63448d25fbe857aad0ad6d0765c7c1`
- Feedback summary SHA-256: `f4d85476b6ef36a248fdb33ed0a2717898553a8e0b493d68cad0376a8a7d7796`
- Feedback packets SHA-256: `2e625264bd06e2c75e1f12d8eb6724b1dce388b671954fd537f8f446d9e3fb7d`
- Dashboard: `http://127.0.0.1:5684/outputs/v2_6_current_code_original250_best3/validate_250_20260507_131235/dashboard/index.html`
- Task Focus dashboard: `http://127.0.0.1:5684/outputs/v2_6_current_code_original250_best3/validate_250_20260507_131235/dashboard/task_focus.html`

Expanded arm:

- Run root: `outputs/v2_6_current_code_original250_expanded/validate_250_20260507_141441`
- Paired comparison SHA-256: `1793ca3700fa75de42300b16021fd80b07f1b640d836940625119396cc5f74f3`
- Helper contribution SHA-256: `4d65b558092d499e36c1ef7bcb085418713d0d18259eb9ac9ae59ee11929f533`
- Control cache report SHA-256: `2d6dca8b5a941a8418d92127c736a8e53515d13a6ff1ed042fb25915596bf972`
- Feedback summary SHA-256: `13bb621a131bcf1392bac2b0d254d024135ce57651cdf0ba33675862fcf94f5f`
- Feedback packets SHA-256: `b17a0531b17500f76ffa908a7c44991b91e8010f2af10ec133c8e7d700ccc4f8`
- Dashboard: `http://127.0.0.1:5685/outputs/v2_6_current_code_original250_expanded/validate_250_20260507_141441/dashboard/index.html`
- Task Focus dashboard: `http://127.0.0.1:5685/outputs/v2_6_current_code_original250_expanded/validate_250_20260507_141441/dashboard/task_focus.html`

Both dashboards were HTTP-checked and opened.

## Control Cache

| Arm | Source | Cached | Fresh | Misses | Manifest Hash |
|---|---:|---:|---:|---:|---|
| Best3 | mixed | 209 | 41 | 41 | `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2` |
| Expanded | cached | 250 | 0 | 0 | `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2` |

The baseline cache was applied task-by-task. The expanded arm reused cached controls for all 250 tasks.

## Matched Result

| Metric | Current-Code Best3 | Current-Code Expanded V2.6 | Expanded - Best3 |
|---|---:|---:|---:|
| Candidate outcome | 0.6078 | 0.6179 | +0.0100 |
| Candidate canonical/reference | 0.7679 | 0.7395 | -0.0283 |
| Exact successes | 48 | 40 | -8 |
| Runtime exceptions | 0 | 0 | 0 |
| Helper side-effect incidents | 0 | 0 | 0 |
| Protocol gate | PASS | PASS | same |
| Route-mismatch qualified | false | false | same |

Run-vs-control metrics:

| Arm | Control Outcome | Candidate Outcome | Delta | Control Canonical | Candidate Canonical | Delta | Exact |
|---|---:|---:|---:|---:|---:|---:|---:|
| Best3 | 0.4007 | 0.6078 | +0.2071 | 0.6753 | 0.7679 | +0.0926 | 14 -> 48 |
| Expanded | 0.4029 | 0.6179 | +0.2150 | 0.6800 | 0.7395 | +0.0595 | 13 -> 40 |

The direct same-manifest current-code comparison is outcome-positive for expanded V2.6 but canonical/reference and exact-success negative versus current-code best3.

## Helper-Fit Gap

| Metric | Best3 | Expanded | Relative Change |
|---|---:|---:|---:|
| Feedback no-current-helper-fit share | 52.0% | 46.0% | 11.54% reduction |
| Feedback no-current-helper-fit count | 130 | 115 | -15 |

On original250 current-code feedback packets, expanded V2.6 meets the 10% relative helper-fit reduction threshold. This is a feedback-derived dynamic no-fit measurement and differs from the older static formal250 reference of 44.4%.

## Helper Contribution Summary

Best3 helper contribution:

| Helper | Visible | Called | VNC | Called Outcome Delta | Called Canonical Delta | Side Effect | Runtime |
|---|---:|---:|---:|---:|---:|---:|---:|
| `relative_day_time_to_timestamp` | 32 | 29 | 3 | +0.3183 | +0.1963 | 0 | 0 |
| `resolve_search_window_or_bounds` | 72 | 41 | 31 | +0.2156 | +0.1639 | 0 | 0 |
| `select_record_by_timestamp_extreme` | 32 | 26 | 6 | +0.2823 | +0.2199 | 0 | 0 |

Expanded helper contribution:

| Helper | Visible | Called | VNC | Called Outcome Delta | Called Canonical Delta | Side Effect | Runtime |
|---|---:|---:|---:|---:|---:|---:|---:|
| `plan_contact_lookup_query` | 15 | 10 | 5 | +0.6010 | +0.0870 | 0 | 0 |
| `extract_contact_field_from_search_result` | 15 | 5 | 10 | +0.8967 | +0.0006 | 0 | 0 |
| `plan_contact_search_from_scalar_constraint` | 15 | 0 | 15 | n/a | n/a | 0 | 0 |
| `relative_day_time_to_timestamp` | 32 | 28 | 4 | +0.1823 | +0.0312 | 0 | 0 |
| `resolve_search_window_or_bounds` | 72 | 43 | 29 | +0.3083 | +0.1853 | 0 | 0 |
| `select_record_by_timestamp_extreme` | 32 | 24 | 8 | +0.3775 | +0.2434 | 0 | 0 |

Contact-scalar helpers were genuinely called and had positive called-subset contribution versus control. `plan_contact_search_from_scalar_constraint` remained visible-but-not-called on original250.

## Subset Analysis

Direct expanded-vs-best3 packet comparison:

| Subset | N | Mean Outcome Delta | Mean Canonical Delta |
|---|---:|---:|---:|
| All matched scenarios | 250 | +0.0081 | -0.0283 |
| Contact surface | 71 | -0.0229 | -0.0133 |
| Message surface | 16 | +0.0291 | -0.0018 |
| Reminder surface | 112 | +0.0168 | -0.0412 |
| New tool called | 10 | +0.0889 | +0.0578 |
| New tool visible-not-called only | 13 | -0.0197 | +0.0715 |
| Expanded no-current-helper-fit | 115 | +0.0098 | -0.0667 |

Interpretation:

- Outcome improved overall and on new-tool-called cases.
- Exact successes fell despite mean outcome improvement, which indicates stochastic and threshold effects around exact success.
- Canonical/reference fell because several non-contact reminder/date lanes varied downward in this matched rerun.
- New helper VNC remained a drag for some contact cases and should stay visible in limitations.

## Decision

`expanded portfolio non-harmful but variance-limited`

The expanded portfolio is current-code original250 outcome-positive and reduces dynamic no-current-helper-fit by more than 10%, but it does not dominate best3 on exact success or canonical/reference. It should be reported as positive but variance-limited current-code evidence, not as a replacement for the protected best3 broad claim.
