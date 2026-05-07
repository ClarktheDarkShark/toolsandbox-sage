# V2.6 Matched-Gap Evidence Lock Report

## Scope

This report locks the V2.6 matched gap-enriched frozen250 evidence for the expanded contact-scalar candidate portfolio. It does not modify or replace the frozen best3 formal evidence.

## Evidence Commit

- Evidence-producing commit: `b63f98695aed7270f15c127c40fd27588d7c342b`
- Expanded V2.6 portfolio:
  - `relative_day_time_to_timestamp`
  - `resolve_search_window_or_bounds`
  - `select_record_by_timestamp_extreme`
  - `plan_contact_lookup_query`
  - `extract_contact_field_from_search_result`
  - `plan_contact_search_from_scalar_constraint`
- Generation mode: `off`

## Registries

- Expanded registry: `artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack/registry_manifest.json`
- Expanded registry SHA-256: `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`
- Best3 registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Best3 registry SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`

## Manifest And Runs

- Matched gap-enriched manifest: `artifacts/summaries/v2_6_gap_closure_250/cohort_manifest.json`
- Manifest SHA-256: `5019602d637362a03317ac4349b9b89a2a790ff69bd5a72203d8dad9516f60e6`
- Best3 run path: `outputs/v2_6_gap_closure_250_best3/validate_250_20260507_023114`
- Expanded run path: `outputs/v2_6_gap_closure_250_expanded_rerun/validate_250_20260507_033336`
- Summary JSON: `artifacts/summaries/v2_6_gap_closure_250/run_summary.json`
- Summary JSON SHA-256: `c0ba914af6f08f0e201013f114d5e286122aea2c0c38d32be5ba4548db6359ba`
- Best3 paired comparison SHA-256: `5b594d52ab6e8fc43e1f647fb23912a9e17812c53b20a6e0b1795f201468ebf1`
- Expanded paired comparison SHA-256: `e8dacf3c36c542ee156b2625ba3d91ca10e92fa66c0f964e3c478b9f61be140f`
- Expanded helper contribution summary: `artifacts/summaries/validate_250_20260507_033336/helper_contribution_summary.json`
- Expanded helper contribution summary SHA-256: `2310ec2158dc288b4e83b45ab9c45bdba699e8306208c48c5fa6e2d43dcab4ba`

## Dashboards

- Best3 dashboard: `outputs/v2_6_gap_closure_250_best3/validate_250_20260507_023114/dashboard/index.html`
- Best3 task focus: `outputs/v2_6_gap_closure_250_best3/validate_250_20260507_023114/dashboard/task_focus.html`
- Expanded dashboard: `outputs/v2_6_gap_closure_250_expanded_rerun/validate_250_20260507_033336/dashboard/index.html`
- Expanded task focus: `outputs/v2_6_gap_closure_250_expanded_rerun/validate_250_20260507_033336/dashboard/task_focus.html`

## Commands

Best3 arm:

```bash
OPENAI_API_KEY="$OPENAI_API_KEY" PYTHONPATH=src:. python scripts/run_sage_protocol.py \
  --mode validate_250 \
  --manifest artifacts/summaries/v2_6_gap_closure_250/cohort_manifest.json \
  --registry-dir artifacts/registry_frozen_best3_claim \
  --generation off \
  --control-cache use-if-eligible \
  --output-root outputs/v2_6_gap_closure_250_best3
```

Expanded arm rerun:

```bash
OPENAI_API_KEY="$OPENAI_API_KEY" PYTHONPATH=src:. python scripts/run_sage_protocol.py \
  --mode validate_250 \
  --manifest artifacts/summaries/v2_6_gap_closure_250/cohort_manifest.json \
  --registry-dir artifacts/registry_candidates/v2_6_expanded_contact_scalar_pack \
  --generation off \
  --control-cache use-if-eligible \
  --output-root outputs/v2_6_gap_closure_250_expanded_rerun
```

## Metrics

- Best3 outcome: `0.6040`
- Expanded outcome: `0.6235`
- Expanded vs best3 outcome delta: `+0.0195`
- Best3 canonical/reference: `0.7838`
- Expanded canonical/reference: `0.8060`
- Canonical/reference delta: `+0.0222`
- Exact successes: `59 -> 59`
- Best3 no-current-helper-fit share: `55.2%`
- Expanded no-current-helper-fit share: `45.6%`
- Relative gap reduction: `17.39%`
- Runtime exceptions: `0` in both arms
- Helper side-effect incidents: `0` in both arms
- Protocol gate: `PASS` for both arms

## Control Cache And Quality

- Best3 control source: mixed, `190` cached and `60` fresh controls
- Expanded control source: mixed, `222` cached and `28` fresh controls
- Cache manifest SHA-256: `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- Cohort quality gate: `PASS`

## Caveat

This evidence proves matched gap-enriched gap closure. It does not directly replace the original formal250 best3 claim and does not by itself prove the original absolute best3 `44.4% -> <=40.0%` helper-fit target on the original formal250 manifest.

## Decision Label

`v2_6 matched gap evidence locked`
