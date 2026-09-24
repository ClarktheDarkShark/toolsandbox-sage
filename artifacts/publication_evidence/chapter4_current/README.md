# Current Chapter 4 evidence

This compact bundle is the public, aggregate reconstruction of the 20 selected
runs used by the current manuscript. It contains the evidence JSON, a
self-contained dashboard, and the eight manuscript tables. Open
`chapter4_evidence.html` directly in a browser.

The large per-task trajectories and lifecycle ledgers are not duplicated in
Git. Rebuilding this bundle requires the protected selected cohort identified
in [`docs/experiment_contract.md`](../../../docs/experiment_contract.md). Its
selected-manifest and verification hashes are recorded there and in
[`docs/reference_evidence_manifest.json`](../../../docs/reference_evidence_manifest.json).

The public reconstruction differs from the protected reference only in three
non-scientific provenance fields: its generation timestamps are newer and its
threshold file is recorded as a repository-relative path instead of a personal
absolute path. Removing those three fields produces identical JSON. Every
metric, hypothesis decision, run value, tool count, confidence interval, and
table image is unchanged. `reconstruction_receipt.json` records the exact
hashes and normalization.

To rebuild after placing a verified copy of the raw cohort at its documented
path:

```bash
make analyze \
  CAMPAIGN_MANIFEST=artifacts/chapter4_evidence/chapter4_final_policy_online_frozen_20260911_4ce1c6d/technical_replacement/final_selected_cohort/selected_cohort_manifest.json \
  ANALYSIS_OUTPUT=artifacts/publication_evidence/chapter4_current
make render-paper \
  EVIDENCE_DATA=artifacts/publication_evidence/chapter4_current/chapter4_evidence_data.json \
  TABLE_OUTPUT=artifacts/publication_evidence/chapter4_current/tables
```
