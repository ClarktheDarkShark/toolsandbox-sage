# Generated-tool repair and retirement protocol

Status: prospective development protocol; not a reconstruction of the July
paper runs.

## Purpose

SAGE must do more than report that a generated tool failed. A directly
attributable implementation, execution, safety, routing, or adoption failure
must cause a bounded action: repair the tool and validate a new version, narrow
its route, or retire it. The action applies only to later tasks. SAGE never
replays or rescores the task that produced the evidence.

Whole-task outcome is an alarm, not by itself proof that every generated tool
called on that task is defective. Rewriting a tool from that signal alone would
misattribute failures caused by the actor, another tool, or the final answer.
Implementation regeneration therefore requires tool-attributable evidence such
as failure of the tool's public contract or repeated execution failure.
Three explicit execution failures trigger repair even when they occur across
different public task families. At run end, one or two remaining explicit tool
failures enter the same terminal queue so the affected version is retired
rather than silently surviving because no third observation occurred.

## Mechanical decisions

| Observed evidence | Required action |
| --- | --- |
| A deployed implementation fails its public, task-independent contract | Quarantine that version; attempt bounded regeneration and full validation; retire it if no candidate passes. |
| A generated tool repeatedly fails during execution | Treat it as an implementation failure and use the same repair-or-retire path. |
| Calls are repeatedly harmful only in a semantic task family | Suppress that family route while retaining independently helpful routes. |
| A tool is routed repeatedly but never selected | Repair its public schema/description, revalidate it, and canary the new version; retire it if adoption does not occur. |
| The generated-tool executor explicitly reports a tool failure, or a generated call causes a confirmed safety failure | Count only that tool-attributable evidence; retire immediately when required by safety policy. A generic actor, user, evaluator, or framework exception is a run-integrity failure, not proof that a called tool failed. |
| A repaired version is deployed | Limit it to a prospective canary. Promotion requires at least three audited, same-family observations where the current version was the sole generated tool called, at least two exact outcomes, no audited regression, and at least one success flip against the fresh matched control. Retire on a contract/tool-runtime failure or after eight eligible family tasks without adequate evidence. |
| The run ends with repair or canary work unresolved | Retire the unresolved version and record a terminal acknowledgement; do not carry an unvalidated active tool into the final registry. |

Lifecycle implementation decisions use public tool contracts, generated-tool
execution status, public semantic-family labels, adoption counts, and the
audited v9 post-task scalar outcome. The paper-era v1 value remains a separately
reported comparability diagnostic and is not mixed into prospective decisions.
Lifecycle components do not receive scenario identifiers, expected answers,
target state, or evaluator traces. The fresh control result can support paired
analysis and family routing, but it is not included in an implementation-repair
prompt. The triggering task is never made available to the replacement as a
repair example.

## Contact-dependency use case

`prepare_safe_action_or_abstain` is the historical motivating failure. Its
public contract already required the tool to distinguish a missing search
capability from a missing target identifier. The historical implementation
returned a fixed missing-search answer, and an old validator could normalize
that wrong raw output before checking it.

The current validation gate checks raw semantic behavior before normalization,
including held-out and negative-applicability cases. That historical candidate
is now rejected before deployment. A deterministic prospective lifecycle test
also loads the historical accepted version, detects its public-contract
failure, quarantines version 1, validates version 2, and evaluates version 2
only on later matching-family observations. Hidden expected values and the
triggering task identifier are asserted absent from generation prompts, repair
feedback, and logs.

This distinction matters: closing the validator defect is a pre-deployment
repair. The seeded historical-version test demonstrates the post-deployment
actuator without pretending that a newly generated invalid tool passed the
strengthened validator.

## Validation ladder and claim boundary

1. Run deterministic lifecycle and semantic-validator tests, including a
   failing replacement, a successful replacement, non-adoption retirement,
   restart persistence, and held-out-value secrecy.
2. Run the exposed 10-task development cohort to check targeted generation and
   execution mechanics.
3. Run the disjoint exposed 30-task development cohort to check broader
   behavior and working-tool non-regression.
4. Freeze the code, then run a fresh-control, no-cache 1,032-task validation.
5. If SAGE outcome exceeds `0.80` with zero exceptions and all integrity checks
   pass, count that run as replication 1 and run nine additional isolated
   replications.

The 10-task and 30-task cohorts are development diagnostics, not publication
evidence or unseen test sets. Prior investigation has exposed the full
ToolSandbox benchmark as well; the final ten runs estimate stochastic
performance on that disclosed benchmark. A lifecycle-off ablation is required
to attribute a performance change specifically to the new repair lifecycle.

The strict full-run launcher forbids partial-row resume. Exact recovery of an
in-progress canary after copying only part of a run into a new output directory
is therefore outside the publication protocol.
