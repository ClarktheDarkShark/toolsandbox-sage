# Generated-tool repair and retirement protocol

Status: prospective development protocol; not a reconstruction of the July
paper runs.

## Purpose

SAGE must do more than report that a generated tool failed. A directly
attributable implementation, execution, safety, routing, or adoption failure
must cause a bounded action: repair the tool and validate a new version, narrow
its route, or retire it. The action applies only to later tasks. SAGE never
replays or rescores the task that produced the evidence.

Within that attribution boundary, a confirmed failing implementation cannot
remain active with only a `needs_repair` label. The repair queue must resolve to
either a fully validated prospective candidate or a durable terminal retirement
of the affected tool name and canonical contract. A failure confined to one
public semantic route is resolved at the route boundary when the same tool has
independent helpful evidence elsewhere. That is a routing repair, not an
assertion that the implementation is globally defective.

For outcome-based harm attribution, “strictly attributable” means that both
arms have fresh audited outcomes for the same task, the task has a public
semantic-family context, no runtime exception occurred, and the candidate
attempted or called exactly one generated tool. Two harmful observations under
that boundary can suppress the affected family route. They cause global
retirement only when the tool has no strictly attributable helpful observation
in any family. A task with co-called generated tools cannot satisfy this test,
so its loss remains diagnostic rather than being assigned to an arbitrary tool.

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
failures enter the same terminal queue so the affected version is resolved by
validated repair or retirement rather than silently surviving because no third
observation occurred.

## Mechanical decisions

| Observed evidence | Required action |
| --- | --- |
| A deployed implementation fails its public, task-independent contract | Quarantine that version; attempt bounded regeneration and full validation; retire it if no candidate passes. |
| A generated tool repeatedly fails during execution | Treat it as an implementation failure and use the same repair-or-retire path. |
| A generated helper returns a valid action plan, but the actor does not execute the required downstream native action | Suppress that exact public-family route immediately. Do not regenerate the helper from this actor-follow-through signal. Park globally only when no trustworthy public family is available. |
| Strictly attributable calls are repeatedly harmful in one semantic task family, but the tool is independently helpful elsewhere | Suppress that family route while retaining the independently helpful routes. |
| Strictly attributable calls are repeatedly harmful and the tool has no attributable helpful use | Retire the tool globally rather than leaving a harmful implementation active. |
| A low-outcome task contains multiple generated calls or otherwise lacks strict attribution | Record a diagnostic alarm. Do not rewrite or retire a particular implementation from that task-level result alone. |
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

Generation prompts use synthetic contract examples. Across the validation
helper contracts, applicable public branches include missing capability,
named-recipient dependency, missing target, ambiguous target, read-only target
exemption, and safe continuation; a narrow successor receives only the branches
declared by its own domain contract. These are task-independent
developer-authored cases, not benchmark answers. The separate cases labeled
held-out are internal validation and model-selection data, not an unseen test
set. Their values and expected outputs are removed before prompt construction,
and the exact prompt is audited immediately before model inference. Repair
queues are reduced to public operational counts and task-independent reason
codes; recursive guards reject scenario/task identifiers, expected or reference
answers, target state, evaluator traces, outcome values, and success-flip values
at persistence, request-construction, and prompt boundaries.

For structured validation helpers, bounded repair uses compact public
counterexample-guided synthesis. Each ordinary attempt first traces the current
best implementation against labeled, model-visible synthetic cases and returns
a schema-checked decision plan; a second model call writes one complete
replacement. The first unresolved public case remains the explicit final gate
until it passes; the prompt also lists already-passing public cases as regression
guards. Only then does focus advance to the next public failure. Both stages receive the
same minimal executable specification, current code, public input/output
contract, public cases, and public validation frontier. Held-out and blind
checks appear only as value-free invariant labels. When those operations are
present in the selected public contract, the plan must order normalization,
inferred public prerequisites, missing-capability checks, read-only versus
mutating classification, target checks, and ambiguity checks before code is
authored. Later attempts use the best validation frontier observed so far. When
all ordinary candidates in an attempt are rejected, that
same bounded lifecycle attempt immediately adds one independently model-authored
clean-room candidate: it omits the rejected code and synthesizes from the public
contract in one call. The controller evaluates the complete portfolio and keeps
the strongest result. This avoids depending on a later iteration for a diverse
candidate and does not relax or change the full acceptance validator.

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

Candidate-journal schema v3 also binds each candidate's origin as `ordinary` or
`clean_room`. Its sealed attempt reference records the first unresolved public
case and the public-only rank components used to choose the portfolio winner.
The strict verifier independently recomputes those components, candidate-origin
counts, and the complete winner ordering from the hash-bound candidate rows.
Candidates are ordered by acceptance, newly regressed public cases, failure of
the focused public case, total failed public cases, public validation distance,
full validation distance, exact duplication of the current best, and finally
candidate index. Clean-room provenance is valid only after every ordinary
candidate in that attempt was rejected; a false fallback flag requires a zero
clean-room count.
Schemas v1 and v2 remain readable for historical reports under their original
exact fields, but only v3 establishes authenticated origin and portfolio-choice
evidence.

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

## Contact-removal use case

`prepare_safe_action_or_abstain` is the historical motivating failure. Its
broad public contract covered several unrelated action families and required it
to distinguish a missing capability from a missing target. The historical
implementation instead returned a largely fixed missing-search answer. A
runtime semantic normalizer then rewrote some incorrect decisions before the
actor observed them, concealing the generated implementation's behavior and
attributing framework-authored corrections to the tool. Validation-helper
output is now preserved exactly. The independent validator, rather than runtime
rewriting, decides whether generated semantics are acceptable.

The ordered 10-task development diagnostic exercises this prospective causal
sequence:

1. Load the historical broad helper as active version 1 and expose a later
   public contact-removal failure that its synthetic contract deterministically
   reproduces. This public-contract violation is direct implementation evidence;
   it does not rely on the benchmark answer or a whole-task score.
2. Quarantine version 1 and make exactly seven bounded repair attempts. Ordinary
   and, when eligible, clean-room candidates receive only the public executable
   contract, model-visible synthetic examples, and sanitized public failure
   frontier. No task identifier, benchmark answer, target state, evaluator
   trace, outcome value, or hidden expected value enters a repair prompt.
3. If no candidate passes the unchanged full validator, record the terminal
   repair acknowledgement as rejected and retire the broad source. Persist a
   tombstone for both its name and canonical contract before updating the
   registry. The tombstone prevents the same failed product from being
   reactivated or reborn after a restart.
4. On a later contact-removal observation, generate the independently specified
   narrower successor `assess_contact_removal_readiness`. This is a new
   canonical tool, not version 2 of the retired broad helper and not a rewrite
   from the triggering benchmark task. Its public contract applies only to
   contact removals. It consumes the visible request, action, target, visible
   match count, and two host-grounded Boolean facts indicating whether contact
   lookup and contact removal are present in the routed native inventory.
5. Validate the successor before registry activation. Public examples cover
   missing lookup, missing removal, missing target, ambiguous matches, stable
   identifiers, and safe continuation. Held-out cases and blind metamorphic
   checks remain outside the generation prompt. The blind checks independently
   withhold each declared capability, combine capability loss with a blank
   target to verify decision precedence, and vary visible-match count to verify
   ambiguity handling. The generated helper must return the raw six-field
   decision contract and must never search, select, remove, or invent a record.
6. Activate only a fully validated successor and assess it prospectively on the
   six later contact-removal tasks in the 10-task diagnostic. The predeclared
   gate requires it to be visible and called on all six, achieve at least five
   exact outcomes, produce at least one success flip against the fresh matched
   control, and never run beside the retired broad source.

The two availability Booleans are reconciled by the host from the routed native
schemas immediately before execution. The actor may supply the request evidence
needed by the helper, but it cannot claim that an absent native capability is
available or hide one that is present. This reconciliation uses only the public
tool inventory; it adds no task label or evaluator information.

The exact registry produced by a passing 10-task diagnostic is then frozen and
transferred into a disjoint 30-task development cohort. Generation and lifecycle
mutation are disabled for that transfer. The verifier requires the same active
successor and retired-source tombstone, a byte-identical registry inventory,
successful successor use on at least eight disjoint contact-removal
cases, preserved execution of two pinned working reminder-tool paths, and exact
non-regression on two unrelated native-only tasks. This is scoped transfer and
no-harm evidence for the predeclared paths, not proof that no task or tool can
ever regress.

During disclosed development, the synthetic public contract and repair guidance
were made internally consistent with the validator, including the explicit
`target_identifier` fact, removal-before-lookup requirement order, and
capability-before-target decision order. These are developer-authored,
task-independent safety rules. The use case tests whether SAGE can actuate a
public-evidence repair-or-retire lifecycle and validate a narrower successor; it
is not evidence that SAGE autonomously discovered those semantic rules.

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
   Require the exact validated successor to generalize and the registry to remain
   byte-identical. The preservation check is deliberately narrow and follows
   the tool paths observed in the pinned successful paper run: the day-offset
   reminder calls `relative_day_time_to_timestamp` and
   `prepare_reminder_creation_args`; the weekday reminder calls the validated
   `next_weekday_time_to_timestamp` successor and
   `prepare_reminder_creation_args`. Both preserved entries must be exercised
   across the cohort and remain failure-free. The installed registry inventory
   must be byte-identical to the source snapshot before the run and remain
   byte-identical through final verification. Two unrelated native-only tasks
   must remain exact with no negative outcome delta. This demonstrates those
   working paths plus the disjoint cohort; it is not a universal no-harm claim.
   An independently seeded 30-task repair run is a separate repair-process
   replication and cannot substitute for this transfer check.

Steps 1–3 are disclosed development diagnostics. They establish mechanism,
prompt secrecy, scoped transfer, and scoped non-regression, but they are not
publication outcome samples. The publication boundary begins only after the
accepted code and inputs are frozen for step 4.

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
