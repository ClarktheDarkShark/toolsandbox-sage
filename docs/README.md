# Documentation index

This release keeps the documentation needed to run, audit, and interpret the
experiment reported in the paper. Most historical development logs, abandoned
benchmark integrations, superseded phase reports, and textual wrappers for
stale static dashboard exports are available in Git history rather than in the
release tree. A small number of dated records remain for provenance or because
the legacy freeze helper inventories them; each is labeled archival and is not
current execution guidance. Remaining legacy PNG/PDF snapshots are archival
only: they are not inputs to the runtime, analysis, dashboards, or manuscript
build.

## Reproduce the paper experiment

- [`experiment_contract.md`](experiment_contract.md) defines the immutable
  runtime, arms, task order, cache policy, endpoints, and acceptance rules.
- [`reference_evidence_manifest.json`](reference_evidence_manifest.json)
  records the content hashes for the manuscript, runtime, frozen inputs, and
  selected evidence cohort.
- [`sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`](sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json)
  is the ordered 1,032-task benchmark manifest.
- [`sage_protocol/publication_input_manifest_20260901.json`](sage_protocol/publication_input_manifest_20260901.json),
  [`sage_protocol/publication_checkpoint_amendment_20260902.json`](sage_protocol/publication_checkpoint_amendment_20260902.json),
  and [`sage_protocol/publication_release_manifest_20260910.json`](sage_protocol/publication_release_manifest_20260910.json)
  form the content-addressed publication input chain.
- [`sage_protocol/publication_validation_thresholds_v3.json`](sage_protocol/publication_validation_thresholds_v3.json)
  contains the active integrity and no-regression gates. Earlier threshold
  versions remain only because the release manifest hashes their provenance.

## Audit the method and evidence

- [`sage_protocol/policy_production_release_20260908.md`](sage_protocol/policy_production_release_20260908.md)
  records the dated restoration rationale and policy-directed claim boundary;
  its pre-cleanup file counts are historical.
- [`sage_protocol/policy_production_final_evidence_20260916.md`](sage_protocol/policy_production_final_evidence_20260916.md)
  identifies the final 10 online and 10 frozen runs.
- [`sage_protocol/h3_reporting_interpretation_amendment_20260917.md`](sage_protocol/h3_reporting_interpretation_amendment_20260917.md)
  records an intermediate, superseded H3 reporting decision. It is retained
  only to disclose the reporting-history chain; it is not the current H3.
- [`sage_protocol/publication_cleanup_audit_20260901.md`](sage_protocol/publication_cleanup_audit_20260901.md)
  is a dated diagnostic of the earlier hybrid-cache campaign. Its proposed
  cleanup steps and hypothesis framing are superseded by the contract.
- [`sage_protocol/chapter4_4omini_data_collection_plan.md`](sage_protocol/chapter4_4omini_data_collection_plan.md)
  and [`sage_protocol/chapter4_results_completed.tex`](sage_protocol/chapter4_results_completed.tex)
  are explicitly archival inputs still inventoried by the legacy freeze helper.
  They describe an abandoned protocol and an obsolete manuscript draft; do not
  use them to run or report the present experiment.

The repository does not track the large raw 20-run cohort. Its immutable local
location and hashes are recorded in the experiment contract and reference
manifest. The source release therefore cannot independently recalculate the
Chapter 4 aggregate without obtaining that cohort. It does include a portable,
hash-receipted copy of the resulting [aggregate evidence dashboard, JSON, and
tables](../artifacts/publication_evidence/chapter4_current/). Those files are
regenerated from the raw cohort by the maintained analysis commands in the main
README.
