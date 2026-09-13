# Adaptive sample-as-rep01 campaign mode

The final lifecycle campaign may explicitly count the already completed and
passing 1,032-task release sample as online replication 01. This is an opt-in
accounting mode; the default campaign still treats the sample as a separate gate
and launches ten new online replications.

## Exact semantics

With `--sample-as-rep01`, preparation:

1. re-verifies the passing `release-sample` report against the current clean
   release identity;
2. content-addresses the report, every file in the sample run tree, and every
   file in its generated-tool registry tree;
3. binds that immutable run as completed online `rep01` without inventing a
   launcher process, port, or campaign-inclusion attestation;
4. queues only `rep02` through `rep10` for the online wave;
5. requires all nine new pairs to execute in distinct, overlapping child
   processes with distinct dashboard ports; and
6. aggregates rep01 through rep10 in the final dashboard.

The sample was selected after it passed the strict greater-than-0.80 technical
readiness gate. Therefore this ten-run distribution is **adaptive and
selection-conditioned descriptive evidence, not preregistered confirmatory
inference**. The manifest, JSON evidence payload, dashboard header, hypothesis
cards, and statistics record that limitation. No run may replace or rerun the
bound rep01 inside the campaign.

## Preparation and launch

```bash
make prepare-paper-rerun \
  SAMPLE_REPORT=outputs/<sample>/publication_validation_report.json \
  CAMPAIGN_ARGS='--sample-as-rep01 --campaign-id <final-campaign-id> --scope online-only'

PYTHONPATH=src:. python scripts/run_chapter4_evidence_campaign.py run \
  --repo-root . \
  --campaign-manifest artifacts/chapter4_evidence/<final-campaign-id>/campaign_manifest.json \
  --approve-execution
```

Preparation never starts model calls. The approved `run` command opens the
aggregate dashboard externally before launching rep02-rep10 in parallel. The
default behavior is unchanged when `--sample-as-rep01` is omitted.
