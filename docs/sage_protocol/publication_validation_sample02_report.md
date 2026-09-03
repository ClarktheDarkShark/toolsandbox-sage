# Completed Strict-Intent Publication Validation Attempt 02 — 2026-09-01

## Decision

**COMPLETE, OUTCOME GATES PASSED, BUT CONFIGURATION-INELIGIBLE.** Both
1,032-task arms finished and the then-current independent integrity checks
passed. Candidate outcome exceeded the historical lower envelope and its
same-run relative outcome lift exceeded 10%. The original v1 report also used
canonical/reference similarity as a release gate; the researcher has clarified
that outcome/task-completion similarity is the sole performance endpoint, so
that canonical gate is superseded. A post-run audit found two
release-configuration drifts: this tree had inadvertently removed validated
within-run generator memoization, and its launcher omitted the July campaign's
five-retry SDK setting. The sample cannot serve as the release gate after those
historical settings are restored and fully pinned.

## Preserved Identity

- Run: `publication_validation_20260901_strict_sample02`
- Local run path:
  `outputs/publication_validation/publication_validation_20260901_strict_sample02/native_action/online_build_full_20260901_200636`
- Release commit: `1e012f4a60282f62372d6c36ac684ee0fc2393da`
- Release tree: `8225632afe2842b1e6c47653f5ad6d29e3c42cf5`
- Publication report SHA-256:
  `8b5436e058ccf29ec64a3e7662ff8d419178903326a74a3d517fe2ad886cfe43`
- Artifact availability: the full run and raw JSON report are preserved as
  local ignored artifacts at the run path named below. They are not shipped in
  a clean clone; this tracked diagnostic report records their identity and
  limitations but is not a substitute for the pending publishable rerun.
- Runtime: dependency-valid 108-distribution publication lock on CPython
  3.12.7, Darwin/arm64
- Historical environment limitation: the July campaign package state was not
  captured. The later cleanup-host snapshot and the clean release lock are
  distinct provenance records; neither is represented as the missing July
  environment.
- Retry-policy limitation: sample 02 omitted `SAGE_OPENAI_MAX_RETRIES`, so the
  adapters used their default value of 2. The preserved July launcher and run
  manifest record 5. Sample 02 retained the observed 120/600-second timeouts,
  two default 1/3-second wrapper delay lists, and four scenario attempts.

## Gate Results

| Check | Observed | Required | Status |
|---|---:|---:|---|
| Control tasks | 1,032 | 1,032 | Pass |
| Candidate tasks | 1,032 | 1,032 | Pass |
| Outcome-scored tasks per arm | 800 | 800 | Pass |
| Runtime exceptions per arm | 0 | 0 | Pass |
| Cached control tasks | 0 | 0 | Pass |
| Persistent repository whole-response replay hits | 0 | 0 | Pass |
| Candidate canonical/reference | 0.7845485310 | Report only | Descriptive |
| Candidate outcome | 0.7788122917 | at least 0.7760515297 | Pass |
| Same-run outcome lift | 58.0413% | at least 10% | Pass |
| Accepted generated tools | 28 | at least 1 | Pass |
| Reuse events | 1,783 | at least 1 | Pass |
| Tasks calling generated tools | 705 | at least 1 | Pass |

Under the active outcome-only policy, every performance gate passed. The raw
report identified above remains unchanged for auditability and records the
superseded v1 canonical failure decision.

## Cache Accounting

The run made 20,651 repository-recorded GPT-4o Mini calls. Every call was a
live request and none replayed a persistently stored whole response. Provider
prefix-token metadata and ordinary token usage were available for all 20,651
calls. OpenAI usage metadata also
reported 11,886,464 provider-cached prompt-prefix tokens across 6,740 calls,
or 40.753% of 29,167,007 prompt tokens. This is provider-side reuse of prompt
computation, not reuse of a task result or model output:

| Arm | Calls | Calls with cached prefix tokens | Prompt tokens | Provider-cached prefix tokens |
|---|---:|---:|---:|---:|
| Control | 9,282 | 2,911 | 10,597,055 | 4,847,616 |
| Candidate | 11,369 | 3,829 | 18,569,952 | 7,038,848 |

The API usage records do not identify whether a matched prefix originated in
the same arm, the other arm, an earlier run, or unrelated traffic in the same
organization and processing region.

Future manifests use separate names for persistent repository whole-response replay,
persistent generated-output replay, nonpersistent within-run generator
contract-and-repair-analysis memoization, and OpenAI-managed prompt-prefix
computation. GPT-4o Mini supports
the earlier-model implicit prompt-caching behavior described in the official
OpenAI documentation.

## Diagnostic Finding

Two early `plan_contact_lookup_query` uses scored an
outcome delta of `-0.5` against their fresh controls. The existing lifecycle
policy classified the helper as harmful and suppressed it for 86 later tasks.
In the superseded campaign, the hybrid cached control scored zero on those
same two tasks, so the historical controller did not trigger that suppression.

This establishes that correcting the control source changed the online
intervention, which is exactly why the July campaign cannot be repaired by
substituting a baseline column. The result does not justify restoring the
hybrid cache or tuning the deferred lifecycle modules after observing this
sample.

Separately, cleanup had removed an in-memory dictionary that reuses identical
model-authored contract and rejected-code repair analyses during one generator
lifetime. That changed repair call sequences and violated the instruction to
defer generator behavior.
The dictionary is not persisted and cannot carry information between runs. It
has been restored. The replacement launcher also restores the July run's
five-retry SDK setting and fail-closes the complete operational policy: SDK
retries, both wrapper delay lists, scenario attempts, and both request timeouts.
These corrections were made before a replacement sample because they restore
documented configuration and deferred behavior, not to select another
stochastic score.

## Next Gate

The configuration-ineligible sample and its raw v1 report remain preserved. At
the time this attempt closed, no replacement sample had been run and the
campaign had not been prepared or executed. Sample 03 subsequently passed on
the corrected tree; that later result is recorded separately in
`publication_validation_sample03_report.md` and does not change this attempt's
ineligible decision.

## Decision Label

`BLOCKED_BY_CONFIGURATION_INELIGIBILITY`
