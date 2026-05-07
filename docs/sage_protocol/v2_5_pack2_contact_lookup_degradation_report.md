# V2.5 Pack 2 Contact Lookup Degradation Analysis

## Objective
Explain why `plan_contact_lookup_query` and `extract_contact_field_from_search_result` looked stronger in 60/100 runs than in the broad 250, and distinguish tool-value failure from cohort dilution or routing interference.

## Artifact
- Machine-readable analysis: `artifacts/summaries/v2_5_pack2_contact_degradation_analysis_250/analysis.json`
- Summary artifact: `artifacts/summaries/v2_5_candidate_pack2_contact_lookup_summary/summary.json`

## Run Comparison
| Run | Pack outcome | Delta vs control | Planner V/C/VNC | Planner called outcome | Extractor V/C/VNC | Extractor called outcome |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Additive60 pre-retention | `0.4260` | `+0.0891` | `24/19/5` | `+0.0338` | `24/11/13` | `+0.0038` |
| Confirmation60 after retention | `0.7811` | `+0.4168` | `24/19/5` | `+0.5975` | `24/11/13` | `+0.6401` |
| Frozen100 | `0.6490` | `+0.2295` | `28/18/10` | `+0.6848` | `24/8/16` | `+0.6155` |
| Broad250 | `0.5637` | `+0.1636` | `26/11/15` | `+0.6563` | `15/7/8` | `+0.6762` |

## Findings
- The contact tools did not lose called-subset value at 250. Planner called-subset outcome stayed high at `+0.6563`; extractor called-subset outcome stayed high at `+0.6762`.
- Aggregate lift fell because the 250 had fewer target-lane opportunities relative to total size: `15 / 250`, versus `24 / 100` and a focused 60.
- Adoption density fell in the broad 250. Planner calls were `11` at 250 versus `18` at 100 and `19` at 60. Extractor calls were `7` at 250 versus `8` at 100 and `11` at 60.
- Cross-lane regressions diluted the contact gain: best3-lane scenarios averaged `-0.0127`; negative/no-helper lanes averaged `-0.0213`.
- False exposure remains a routing issue. Planner appeared on several non-contact `all_tools` scenarios and was visible-not-called, adding context pressure without corresponding tool value.
- This is not primarily a generated-tool value failure. It is a combination of target-lane sparsity, broader variant mix, and insufficiently strict routing outside the target lane.

## Recommended Repair
- Keep Candidate Pack 2 as a confirmed contact-lookup candidate lane.
- Before final expanded-portfolio scaling, tighten routing so `plan_contact_lookup_query` is hidden unless the task has a contact lookup intent plus one scalar constraint and a requested answer field.
- Add a second non-overlapping candidate lane before another final 250 attempt, because 15 contact cases cannot close the original `44.4% -> <=40.0%` gap alone.
- Preserve route-mismatch accounting for extractor calls where outcome is positive but canonical is negative.

## Decision Label
`continue gap-closure loop`

## Post-Analysis Routing Repair
- Root cause confirmed: after generic routing returned `defer`, explicit-contract helpers could still be exposed by broad provisional birth-family visibility.
- Repair: explicit positive triggers or applicable families are now authoritative. If none match, the helper is hidden with `explicit_contract_requires_trigger_or_family_match`.
- Static route probe: `artifacts/summaries/v2_5_contact_routing_contract_repair/route_probe.json` showed contact helpers visible on `search_name_with_relationship` and `search_phone_number_with_name`, hidden on `add_reminder...all_tools`, `search_reminder...all_tools`, and insufficient-information contact scenarios.
- Live diagnostic20: `outputs/v2_5_contact_routing_repair20_pack_20260506_220717/mechanism_40_20260506_220721` showed planner visible/called/VNC/hidden `6 / 5 / 1 / 14`, extractor `6 / 3 / 3 / 14`, runtime/side-effect `0 / 0`.
- This validates the hypothesis that 250 aggregate dilution was partly routing/context pollution rather than tool-value failure.
