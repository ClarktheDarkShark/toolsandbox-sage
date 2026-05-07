# V2.6 Gap Closure 250 Report

## Objective
Determine whether the expanded contact-scalar portfolio closes the no-current-helper-fit gap by at least 10% relative to matched frozen best3 while preserving or improving task-completion outcome.

## Protected Assets
- Frozen best3 registry was not modified.
- Frozen best3 registry SHA-256 before/after: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Locked formal evidence and final best3 package artifacts were not modified during the run.

## Expanded Registry
- Path: `artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json`
- SHA-256 before/after: `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`
- Tools: frozen best3 plus `plan_contact_lookup_query`, `extract_contact_field_from_search_result`, `plan_contact_search_from_scalar_constraint`
- Registry check-only: PASS

## Manifest
- Path: `artifacts/summaries/v2_6_gap_closure_250/cohort_manifest.json`
- SHA-256: `5019602d637362a03317ac4349b9b89a2a790ff69bd5a72203d8dad9516f60e6`
- Scenario count: 250
- Base families: 33
- Largest family share: 3.2%
- Cohort quality: PASS
- Role counts: contact/message positive 80, best3 preservation 112, no-helper negative 10, negative/abstention 48

## Commands Run
```bash
OPENAI_API_KEY="$(conda run -n lifelong python -c 'import os; print(os.environ["OPENAI_API_KEY"])')" PYTHONPATH=src:. python scripts/run_sage_protocol.py --mode validate_250 --manifest artifacts/summaries/v2_6_gap_closure_250/cohort_manifest.json --registry-dir artifacts/registry_frozen_best3_claim --generation off --control-cache use-if-eligible --output-root outputs/v2_6_gap_closure_250_best3 --dashboard-port 5679
```

```bash
OPENAI_API_KEY="$(conda run -n lifelong python -c 'import os; print(os.environ["OPENAI_API_KEY"])')" PYTHONPATH=src:. python scripts/run_sage_protocol.py --mode validate_250 --manifest artifacts/summaries/v2_6_gap_closure_250/cohort_manifest.json --registry-dir artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack --generation off --control-cache use-if-eligible --output-root outputs/v2_6_gap_closure_250_expanded_rerun --dashboard-port 5680
```

## Runs
- Best3 run: `outputs/v2_6_gap_closure_250_best3/validate_250_20260507_023114`
- Expanded run: `outputs/v2_6_gap_closure_250_expanded_rerun/validate_250_20260507_033336`
- Interrupted partial expanded run not used: `outputs/v2_6_gap_closure_250_expanded/validate_250_20260507_032818`
- Reason for restart: initial expanded launch planned only 87 cached controls / 163 fresh controls; a fresh cache plan after best3 evidence had settled showed 222 cached / 28 fresh. Restart preserved the task-by-task cache policy and avoided unnecessary baseline recomputation.
- Generation: OFF for both completed runs
- Dashboards opened and HTTP-checked:
  - `http://127.0.0.1:5679/outputs/v2_6_gap_closure_250_best3/validate_250_20260507_023114/dashboard/index.html`
  - `http://127.0.0.1:5679/outputs/v2_6_gap_closure_250_best3/validate_250_20260507_023114/dashboard/task_focus.html`
  - `http://127.0.0.1:5680/outputs/v2_6_gap_closure_250_expanded_rerun/validate_250_20260507_033336/dashboard/index.html`
  - `http://127.0.0.1:5680/outputs/v2_6_gap_closure_250_expanded_rerun/validate_250_20260507_033336/dashboard/task_focus.html`

## Control Cache Status
- Best3: mixed, 190 cached / 60 fresh
- Expanded: mixed, 222 cached / 28 fresh
- Cache manifest hash: `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- Cache was used task-by-task for eligible baseline tasks only. SAGE/candidate arms were never cached.

## Matched Metrics
- Best3 outcome: `0.6039972795`
- Expanded outcome: `0.6235364061`
- Expanded vs best3 outcome delta: `+0.0195391266`
- Best3 canonical/reference: `0.7838171644`
- Expanded canonical/reference: `0.8060497313`
- Expanded vs best3 canonical delta: `+0.0222325669`
- Exact successes: `59 -> 59`
- Runtime exceptions: `0 -> 0`
- Protocol gate: PASS for both
- Route-mismatch qualified: false for both

## Gap Metric
- Best3 no-current-helper-fit share on matched 250: `55.2%`
- Expanded no-current-helper-fit share on matched 250: `45.6%`
- Relative matched reduction: `17.39%`
- Matched-manifest target: `<=49.68%`; result meets target.
- Original formal250 absolute reference target was `44.4% -> <=40.0%`. This gap-enriched frozen250 is not directly comparable to the original formal cohort, so the direct absolute `<=40.0%` threshold is not claimed here.

## Helper Contribution
- `plan_contact_lookup_query`: visible/called/VNC `24 / 15 / 9`, called outcome `+0.6527`, called canonical `+0.1501`, side-effect/runtime `0 / 0`
- `extract_contact_field_from_search_result`: visible/called/VNC `24 / 7 / 17`, called outcome `+0.6904`, called canonical `+0.0045`, side-effect/runtime `0 / 0`
- `plan_contact_search_from_scalar_constraint`: visible/called/VNC `74 / 12 / 62`, called outcome `+0.4279`, called canonical `-0.0148`, side-effect/runtime `0 / 0`
- Best3 helpers remained positive on called subsets and had side-effect/runtime `0 / 0`.

## Safety
- Runtime exceptions: `0`
- Helper side-effect incidents: `0`
- Accepted-but-uncalled tools: none
- Negative/insufficient-information cases remained part of the cohort; no helper side-effect incidents were observed.

## Why Smaller Runs Looked Stronger Than 250
- Micro and 60 runs were denser in post-birth/contact opportunities, so called-subset gains had higher aggregate weight.
- Broad 250 includes many preservation and negative lanes where new helpers should be hidden or abstain; this dilutes aggregate lift.
- VNC remains high for `plan_contact_search_from_scalar_constraint` (`62 / 74`), so some context exposure remains unused even though called cases are positive.
- Prior failed tools often had positive narrow called subsets but lost value at 100/250 because of sparse applicability, non-contact lane variance, or cross-lane context cost.
- The current expanded pack overcame that enough to improve matched 250 outcome and matched gap share, but not enough to claim direct reduction below the original formal `40.0%` absolute threshold.

## Pipeline Blocker Diagnosis
- Gap closure advanced.
- Remaining blocker: scalar contact-search routing is too broad; VNC is acceptable for this run because outcome and safety passed, but it should be tightened before any larger 500/1032 validation.
- Feedback packets were sufficient; no instrumentation blocker remained.

## Decision Label
`gap closure target met`

## Exact Next Action
Lock this matched frozen250 expanded-pack evidence, update final package artifacts with the matched-gap caveat, and optionally run an original-formal-manifest 250 or 500/1032 validation only if a claim beyond the matched gap-enriched cohort is needed.
