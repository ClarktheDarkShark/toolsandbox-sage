# Phase D — rapid portfolio ablation

> **SUPERSEDED — ARCHIVAL EXECUTION PROMPT.** Do not execute these instructions;
> use the current publication protocol in `../current_state.md`.

Use mixed 30-scenario cohort:
- reminder creation / optional-location lane
- reminder search-window lane
- message recency selection lane
- non-applicable contact / holiday / stock / modify negatives

Arms:
1. control (implicit in every paired run)
2. prepare only
3. select only
4. resolve only
5. full portfolio
6. without prepare
7. without select
8. without resolve

Registry source:
- `artifacts/registry_phaseC_C3_candidate_v2/registry_manifest.json`

Mode:
- `transfer_40`
- generation OFF
- gpt-4o-mini / gpt-4o-mini / gpt-4o-mini
