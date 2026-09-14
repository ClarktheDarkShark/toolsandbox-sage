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
as failure of the tool's public contract or repeated execution failure. A
successful generated helper call followed by the actor failing to execute the
helper's requested native action is different evidence: it identifies an unsafe
actor-route pairing, not defective generated code. That public family route is
suppressed immediately. If no trustworthy public family is available, SAGE
parks the tool globally because it cannot apply a narrower safe boundary.
Three explicit execution failures trigger repair even when they occur across
different public task families. At run end, one or two remaining explicit tool
failures enter the same terminal queue so the affected version is retired
rather than silently surviving because no third observation occurred.

## Mechanical decisions

| Observed evidence | Required action |
| --- | --- |
| A deployed implementation fails its public, task-independent contract | Quarantine that version; attempt bounded regeneration and full validation; retire it if no candidate passes. |
| A generated tool repeatedly fails during execution | Treat it as an implementation failure and use the same repair-or-retire path. |
| A generated helper returns a valid action plan, but the actor does not execute the required downstream native action | Suppress that exact public-family route immediately. Do not regenerate the helper from this actor-follow-through signal. Park globally only when no trustworthy public family is available. |
| Calls are repeatedly harmful only in a semantic task family | Suppress that family route while retaining independently helpful routes. |
| A tool is routed repeatedly but never selected | Repair its public schema/description, revalidate it, and canary the new version; retire it if adoption does not occur. |
| The generated-tool executor explicitly reports a tool failure, or the generated output itself violates its deterministic safety contract | Count only that tool-attributable evidence and use implementation repair-or-retire; retire immediately when required by safety policy. A downstream actor-follow-through failure, generic actor, user, evaluator, or framework exception is not proof that generated code failed. |
| A repaired version is deployed | Limit it to a prospective canary. Promotion requires at least three audited, same-family observations where the current version was the sole generated tool called, at least two exact outcomes, no audited regression, and at least one success flip against the fresh matched control. Retire on a contract/tool-runtime failure or after eight eligible family tasks without adequate evidence. |
| The run ends with repair or canary work unresolved | Retire the unresolved version and record a terminal acknowledgement; do not carry an unvalidated active tool into the final registry. |

Lifecycle implementation decisions use public tool contracts, generated-tool
execution status, public semantic-family labels, adoption counts, and the
audited v9 post-task scalar outcome. The paper-era v1 value remains a separately
reported comparability diagnostic and is not mixed into prospective decisions.
Lifecycle decisions and repair prompts do not consume scenario identifiers,
expected answers, target state, or evaluator traces. The controller retains the
scenario key only to join each task to its same-run control row and to write the
run's audit trail. The fresh control result can support paired analysis and
family routing, but it is not included in an implementation-repair prompt. The
triggering task is never made available to the replacement as a repair example.

The paired control uses the same `sage_wrapped` policy actor and model as SAGE,
but has no generated tools or generated-tool lifecycle. It is therefore the
matched policy-wrapper-without-generated-tools control, not the untouched
upstream ToolSandbox actor. Protocol and per-arm manifests record this runtime
identity, and strict verification rejects either arm if it drifts.

Generation prompts use synthetic contract examples. The public examples cover
each declared decision branch: missing capability, named-recipient dependency,
missing target, ambiguous target, read-only target exemption, and safe
continuation. They are task-independent developer-authored contract cases, not
benchmark answers. The separate cases labeled held-out are internal validation
and model-selection data, not an unseen test set. Their values and expected
outputs are removed before prompt construction, and the exact prompt is audited
immediately before model inference. Repair queues are reduced to public
operational counts and task-independent reason codes; recursive guards reject
scenario/task identifiers, expected or reference answers, target state,
evaluator traces, outcome values, and success-flip values at persistence,
request-construction, and prompt boundaries.

For structured validation helpers, bounded repair uses compact public
counterexample-guided synthesis. Each ordinary attempt first traces the current
best implementation against labeled, model-visible synthetic cases and returns
a schema-checked decision plan; a second model call writes one complete
replacement. The prompt identifies one unresolved public case to fix first and
lists already-passing public cases as regression guards. Both stages receive the
same minimal executable specification, current code, public input/output
contract, public cases, and public validation frontier. Held-out and blind
checks appear only as value-free invariant labels. The plan must order
normalization, inferred public prerequisites, missing-capability checks,
read-only versus mutating classification, target checks, and ambiguity checks
before code is authored. Later attempts use the best validation frontier
observed so far. If both code and frontier repeat, the next attempt omits the
rejected code and asks the model for a clean-room implementation from the public
contract in one call, avoiding deterministic anchoring on the same failed
predicates. This does not relax or change the full acceptance validator.

Every returned repair candidate is persisted before any lifecycle action in the
append-only `post_deployment_repair_candidates.jsonl` journal. Each record binds
the source contract and implementation, the exact generator-returned candidate,
the normalized candidate actually evaluated, validation counts, a sanitized
error frontier, disposition, and content hashes. The record is self-hashed and
the sealed protocol event journal references it one-to-one. Raw held-out values,
benchmark task identifiers, outcomes, expected answers, target state, and
evaluator traces are prohibited. Rejected candidates therefore remain available
to audit why repair converged or failed, while evaluator-private information
remains outside generation and lifecycle evidence.

If a rejected repair repeats both the current best executable hash and its
sanitized validation frontier, the lifecycle records repair stagnation, keeps
the prior best seed, and requests a substantively different next repair. The
strict verifier replays the frozen source contract and authenticates this best
candidate state across every repair attempt; it does not trust same-event
duplicate claims in isolation.

Tool-name scrambling is also an information boundary. Classification, routing,
and policy selection consume the same actor-visible names, descriptions, and
parameter schemas that ToolSandbox sends to the model. A native capability is
inferred only when that public schema identifies it unambiguously; otherwise it
remains opaque. ToolSandbox's private alias map is used only after selection to
dispatch the chosen visible name, never to choose, filter, or force a tool.

## Contact-dependency use case

`prepare_safe_action_or_abstain` is the historical motivating failure. Its
public contract already required the tool to distinguish a missing search
capability from a missing target identifier. The historical implementation
returned a fixed missing-search answer. A runtime semantic normalizer then
rewrote some incorrect decisions before the actor observed them, concealing the
generated tool's failure and falsely attributing framework-authored behavior to
the tool. Validation-helper output is now preserved exactly; the independent
pre-promotion validator, not runtime rewriting, is responsible for rejecting
bad semantics.

During disclosed development, the public missing-target example was aligned to
name `target_identifier` explicitly, as the existing raw semantic gate already
required. This is a developer-authored consistency repair to the synthetic
contract, not benchmark feedback or a benchmark-specific answer.

The current validation gate checks raw semantic behavior,
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

The contact-lookup and relative-time ordering rules used in this prospective
repair are developer-authored meta-repair guidance derived from the public
contract during disclosed development. This use case tests whether SAGE detects,
repairs or retires, validates, canaries, and promotes correctly; it is not
evidence that SAGE autonomously discovered those two semantic rules.

## Validation ladder and claim boundary

The historically successful working-tool paths are preserved in the tracked,
content-addressed fixture
`docs/sage_protocol/fixtures/paper_rep01_working_path_evidence.json`. It records
the original artifact hashes, exact ordered calls and successful outcomes, and
the three complete registry entries. Original ignored run artifacts are checked
when present; the tracked fixture keeps clean-clone verification hermetic.

1. Run deterministic lifecycle and semantic-validator tests, including a
   failing replacement, a successful replacement, non-adoption retirement,
   restart persistence, and held-out-value secrecy.
2. Run the exposed 10-task development cohort to check targeted generation and
   execution mechanics.
3. Transfer the complete content-addressed registry from the passing 10-task
   run into the disjoint 30-task cohort with generation and repair disabled.
   Require the exact promoted tool to generalize and the registry to remain
   byte-identical. The preservation check is deliberately narrow and follows
   the tool paths observed in the pinned successful paper run: the day-offset
   reminder calls `relative_day_time_to_timestamp` and
   `prepare_reminder_creation_args`; the weekday reminder calls the validated
   `next_weekday_time_to_timestamp` successor and
   `prepare_reminder_creation_args`. Both preserved entries must be exercised
   across the cohort and remain failure-free. Their immutable code, spec,
   validation, and provenance identities must be unchanged at every checkpoint;
   only usage counters may advance. Two unrelated native-only tasks must remain
   exact with no negative outcome delta. This demonstrates those working paths
   plus the disjoint cohort; it is not a universal no-harm claim. An independently
   seeded 30-task repair run is a separate repair-process replication and cannot
   substitute for this transfer check.
4. Freeze the code, then run a fresh-control, no-cache 1,032-task validation.
5. Apply the content-addressed schema-v4 adaptive technical-readiness gate. The
   audited-v9 SAGE mean over all 1,032 tasks must be strictly greater than
   `0.80`—equality fails—with zero exceptions and all integrity checks passing.
   If it passes, count that run as replication 1 and run nine additional
   isolated replications.

Every ladder verifier reads the raw per-task conversation and execution
context, rehydrates the ToolSandbox state, and recomputes the applicable outcome
contracts. It reconstructs generated-tool visibility, attempts, failures, and
successful calls from the trajectory rather than accepting those claims from a
summary sidecar. For the development lifecycle claim, each called version and
code hash is additionally bound to the ordered after-task registry checkpoint.
Post-deployment acceptance evidence is read from the launcher's append-complete
protocol event journal; the manifest pins that journal's path, SHA-256 digest,
and row count, and the verifier requires exactly one acceptance event bound to
the same run, candidate directory, request, tool, and version transition. There
is no unsealed legacy fallback: an older development run without this binding
cannot support the lifecycle claim and must be rerun.

The 10-task and 30-task cohorts are development diagnostics, not publication
evidence or unseen test sets. Prior investigation has exposed the full
ToolSandbox benchmark as well; the final ten runs estimate stochastic
performance on that disclosed benchmark. A lifecycle-off ablation is required
to attribute a performance change specifically to the new repair lifecycle.
Because the first full run is an explicit adaptive gate and a failed gate can
lead to further code changes, the resulting ten-run distribution is technical
validation of the frozen accepted system, not a preregistered or unseen-test
estimate. The gate history and every superseded run must remain preserved.

The strict full-run launcher forbids partial-row resume. Exact recovery of an
in-progress canary after copying only part of a run into a new output directory
is therefore outside the publication protocol.
