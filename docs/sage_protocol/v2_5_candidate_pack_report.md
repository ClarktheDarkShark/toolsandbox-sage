# V2.5 Candidate Pack Report

## Candidate Pack 1
- Registry: `artifacts/registry_candidates/v2_5_candidate_pack1_distance/registry_manifest.json`
- Registry SHA-256: `d599a8e56f024f978bcb572ca0df12abb4a4d2196639becf64ef826cbf5f73f4`
- Tools: `relative_day_time_to_timestamp`, `resolve_search_window_or_bounds`, `select_record_by_timestamp_extreme`, `format_calculated_distance_km`
- Flat-scalar direct-action candidate: parked after force-call value failure; see micro report.
- Cohort manifest: `artifacts/summaries/v2_5_candidate_pack1_distance_additive60/cohort_manifest.json`
- Cohort quality: `pass`; largest family share `0.13333333333333333`; best3 no-current-helper-fit proxy `0.600`.

## Decision Label
`candidate pack ready for additive60`

## Candidate Pack 2: Contact Lookup Planner + Field Extractor
- Registry: `artifacts/registry_candidates/v2_5_additive_toolset/registry_manifest.json`
- Registry SHA-256: `835b1ab6524b27ad33591a57b9154dc1d89edbc6b1655f3431b1173fd74a0c48`
- Protected best3 registry unchanged: `artifacts/registry_frozen_best3_claim/registry_manifest.json`, SHA-256 `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
- Tools: best3 plus `plan_contact_lookup_query`, `extract_contact_field_from_search_result`.
- Candidate design: two-stage contact lookup route that preserves the original `search_contacts` call. `plan_contact_lookup_query` turns scalar constraints such as relationship/name/phone/requested field into `search_contacts` kwargs. `extract_contact_field_from_search_result` extracts the requested field from visible search results and reports route-mismatch when canonical credit drops despite outcome success.
- Key framework repairs needed to fairly test value:
  - Fixed generated-helper Python signature ordering so optional scalar defaults do not prevent tool injection.
  - Added actor policy so the model calls the pre-search planner before guessing/manual lookup.
  - Added answer-retention handling so brief user acknowledgement turns do not erase the tool-backed answer from the final scored response.
  - Added registry-aware helper-fit accounting for the contact lookup lane.
- Candidate batch registry source: `artifacts/summaries/v2_5_tool_foundry_v2_5_loop17_contact_lookup_planner_generate/candidate_batch_registry/registry_manifest.json`
- Summary artifact: `artifacts/summaries/v2_5_candidate_pack2_contact_lookup_summary/summary.json`

## Candidate Pack 2 Decision
Candidate Pack 2 is validated as a real contact-lookup gap-lane improvement, but not yet a broad final portfolio replacement. It improves the target contact-lookup subset strongly at 100 and 250, reduces registry-aware no-current-helper-fit on the 250 manifest by `11.54%` relative (`52.0% -> 46.0%`), and is runtime/side-effect clean. Broad 250 aggregate outcome is only `+0.0011` over best3, so the next loop should reduce cross-lane routing/context interference or add another non-overlapping candidate before final expanded-portfolio claim.

## Updated Decision Label
`continue gap-closure loop`
