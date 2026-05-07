# V2.6 Contact Pack Rerun Report

## Objective
Revalidate the contact pack after routing repair before adding it to any V2.6 expanded portfolio.

## Registry Paths And Hashes
- Protected best3 registry: `artifacts/registry_frozen_best3_claim/registry_manifest.json`
- Protected best3 SHA-256: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Candidate pack registry: `artifacts/registry_candidates/v2_5_additive_toolset/registry_manifest.json`
- Candidate pack SHA-256: `835b1ab6524b27ad33591a57b9154dc1d89edbc6b1655f3431b1173fd74a0c48`
- Candidate tools: `plan_contact_lookup_query`, `extract_contact_field_from_search_result`

## Commands
```bash
OPENAI_API_KEY="$KEY" PYTHONPATH=src:. python scripts/run_sage_protocol.py \
  --mode validate_100 \
  --manifest artifacts/summaries/v2_5_gap_closure_100_pack2_contact/cohort_manifest.json \
  --registry-dir artifacts/registry_frozen_best3_claim \
  --generation off \
  --control-cache use-if-eligible \
  --output-root outputs/v2_6_contact_pack_rerun_best3 \
  --dashboard-port 5672

OPENAI_API_KEY="$KEY" PYTHONPATH=src:. python scripts/run_sage_protocol.py \
  --mode validate_100 \
  --manifest artifacts/summaries/v2_5_gap_closure_100_pack2_contact/cohort_manifest.json \
  --registry-dir artifacts/registry_candidates/v2_5_additive_toolset \
  --generation off \
  --control-cache use-if-eligible \
  --output-root outputs/v2_6_contact_pack_rerun_pack \
  --dashboard-port 5673
```

## Runs And Dashboards
- Best3 run: `outputs/v2_6_contact_pack_rerun_best3/validate_100_20260507_000133`
- Best3 dashboards: `http://127.0.0.1:5672/outputs/v2_6_contact_pack_rerun_best3/validate_100_20260507_000133/dashboard/index.html`, `http://127.0.0.1:5672/outputs/v2_6_contact_pack_rerun_best3/validate_100_20260507_000133/dashboard/task_focus.html`
- Pack run: `outputs/v2_6_contact_pack_rerun_pack/validate_100_20260507_002045`
- Pack dashboards: `http://127.0.0.1:5673/outputs/v2_6_contact_pack_rerun_pack/validate_100_20260507_002045/dashboard/index.html`, `http://127.0.0.1:5673/outputs/v2_6_contact_pack_rerun_pack/validate_100_20260507_002045/dashboard/task_focus.html`
- Cohort quality: `PASS` for both runs.

## Control Cache Status
- Best3 run: `cached`, `100 cached / 0 fresh`.
- Pack run: `mixed`, `44 cached / 56 fresh`.
- Cache explanation: reuse is task-by-task but compatibility includes scenario and initial-state checksum. The pack run resolved different compatible initial states for 56 tasks, so it legitimately collected fresh controls. After collection, future matching contexts can use those records.
- Cache manifest hash: `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`.

## Direct Best3-vs-Pack Metrics
Matched candidate-arm comparison over `88` numeric-outcome scenarios:

| Metric | Best3 | Best3 + contact pack | Delta |
| --- | ---: | ---: | ---: |
| Outcome | `0.7249` | `0.7071` | `-0.0178` |
| Canonical/reference | `0.8477` | `0.8884` | `+0.0408` |
| Exact successes | `30` | `29` | `-1` |

Contact subset, `24` scenarios:

| Metric | Best3 | Best3 + contact pack | Delta |
| --- | ---: | ---: | ---: |
| Outcome | `0.8187` | `0.8750` | `+0.0563` |
| Canonical/reference | `0.7262` | `0.8722` | `+0.1461` |
| Exact successes | `0` | `0` | `0` |

Approximate best3-lane subset, `47` scenarios:

| Metric | Best3 | Best3 + contact pack | Delta |
| --- | ---: | ---: | ---: |
| Outcome | `0.6441` | `0.6183` | `-0.0258` |
| Canonical/reference | `0.8868` | `0.9020` | `+0.0151` |
| Exact successes | `30` | `29` | `-1` |

## Helper Contribution
| Helper | Visible | Called | VNC | Failed | Called outcome delta | Called canonical delta | Runtime | Side-effect |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `plan_contact_lookup_query` | 24 | 15 | 9 | 0 | `+0.5755` | `+0.0545` | 0 | 0 |
| `extract_contact_field_from_search_result` | 24 | 9 | 15 | 0 | `+0.6851` | `+0.0108` | 0 | 0 |

Accepted-but-uncalled tools: none.

## Gap Metric
Feedback packet no-current-helper-fit share:
- Best3 rerun100: `48.0%`.
- Pack rerun100: `24.0%`.
- Relative reduction: `50.0%` on this contact-heavy manifest.

## Why Smaller Runs Look Better Than 250
- The contact tools retain high called-subset value in every run; the issue is not that contact calls stopped working.
- Broad 250 had only a small number of target contact opportunities relative to total tasks, so contact gains were diluted.
- The V2.6 rerun shows the same pattern: contact subset improved, but unrelated best3/reminder/message lanes drifted negative.
- Prior false exposure was repaired, but aggregate outcome still depends on target-lane density and cross-lane model variance.
- Therefore the contact pack is a valid candidate lane but cannot close the full `44.4% -> <= 40.0%` formal250 target alone.

## Decision Label
`contact pack retained`

## Exact Next Action
Retain the contact pack as candidate evidence, but combine it only with another non-overlapping, outcome-positive abstraction before another frozen250 proof attempt.
