# Documentation index

This release keeps the documentation needed to run, audit, and interpret the
experiment reported in the paper. Historical development logs, abandoned
benchmark integrations, superseded phase reports, and textual wrappers for
stale static dashboard exports are available in Git history rather than in the
release tree. Remaining legacy PNG/PDF snapshots are archival only: they are
not inputs to the runtime, analysis, dashboards, or manuscript build.

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
  identifies the restored policy-directed implementation and its claim boundary.
- [`sage_protocol/policy_production_final_evidence_20260916.md`](sage_protocol/policy_production_final_evidence_20260916.md)
  identifies the final 10 online and 10 frozen runs.
- [`sage_protocol/h3_reporting_interpretation_amendment_20260917.md`](sage_protocol/h3_reporting_interpretation_amendment_20260917.md)
  records the superseded H3 interpretation used before the manuscript adopted
  its current cross-family-use hypothesis. It is retained only as provenance.
- [`sage_protocol/publication_cleanup_audit_20260901.md`](sage_protocol/publication_cleanup_audit_20260901.md)
  documents the provenance problems corrected before the clean campaign.
- [`sage_protocol/chapter4_evidence_correction_and_rerun_readiness_20260901.md`](sage_protocol/chapter4_evidence_correction_and_rerun_readiness_20260901.md)
  records the clean-rerun boundary.
- [`sage_protocol/native_action_method_validation_20260719.md`](sage_protocol/native_action_method_validation_20260719.md)
  and the [generated-tool appendix](sage_protocol/appendix_native_action_generated_tools.md)
  document the native-action method and representative generated tools.

The repository does not track the large raw 20-run cohort. Its immutable local
location and hashes are recorded in the experiment contract and reference
manifest. The source release therefore verifies the compact frozen inputs but
cannot reconstruct the Chapter 4 aggregate without obtaining that cohort.
Dashboard HTML and images are regenerated from the cohort by the maintained
analysis commands in the main README.
