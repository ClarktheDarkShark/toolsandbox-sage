# Native-Action Generated Tool Validation Protocol

## Purpose

This study tests whether SAGE can improve task completion when an autonomously
generated tool performs a compact deterministic transformation and then invokes
one preserved native environment action. It does not replace the native action
implementation. The native action remains responsible for the state change and
its execution trace remains visible to ToolSandbox.

The comparison is against the same SAGE system using the established generated
tools that prepare values or action arguments for the actor. Outcome/task
completion is the primary metric. Canonical score is retained as a secondary
diagnostic because a direct generated tool can validly complete the final state
without reproducing every benchmark milestone.

## Claim Boundary

Native-action eligibility is determined only from the public generated-tool
contract. The decision does not use scenario names, task identifiers, hidden
answers, or expected benchmark labels. A contract is eligible only when:

1. Every positive validation branch describes exactly one approved native
   action call. A tool may dispatch among a bounded action set only when the
   action choice is an explicit visible input covered by positive and negative
   examples.
2. It has at least one source positive, one held-out positive, and one negative
   applicability example.
3. It contains no multi-action sequence or list of action argument sets.
4. It has no more than six distinct input fields, four positive action cases,
   and four arguments in any action call.
5. The native action is either invariant across positive examples or selected
   from a finite approved set by an explicit visible input covered by the
   positive and negative examples.

Contracts outside these bounds remain ordinary generated tools. This is a
hybrid lifecycle decision, not a rejection of the detected capability gap.

Each accepted direct-action tool carries an explicit
`native_action_delegation` marker in its immutable tool specification. The
runtime and validator require that marker. A process-level experiment switch
cannot grant native execution to an ordinary generated tool.

## Generation And Validation

- Actor, user simulator, and tool generator: `gpt-4o-mini`.
- Tool code generation: model-authored; deterministic code emitters disabled.
- Tool-generation prompt cache: disabled.
- Starting generated registries: empty for every SAGE arm.
- Generation and repair code: authored by `gpt-4o-mini`; deterministic code
  emitters and deterministic code-repair fallbacks are disabled.
- Native action contract: exactly one approved native call for each positive
  example and zero native calls for negative examples.
- Validation: source examples, held-out examples, negative applicability,
  schema and source checks, runtime smoke checks, native action count, exact
  native action name, and exact action arguments.
- Natural use only: diagnostic exposure and force-call settings are unset.
- Bridge policy: disabled.
- Scenario-name birth and routing: disabled.
- SAGE task cache and OpenAI response cache: disabled.

Native-action tool interfaces must not require the actor to infer an opaque
record identifier when that identifier can be derived deterministically from
visible records. For example, a message-counterparty tool receives the visible
message records, semantic update values, and the user's person identifier from
the visible `search_contacts(is_self=True)` result. The generated tool compares
the message sender and recipient identifiers with that visible self identifier
and binds the non-self party internally. This is a general tool-interface rule:
the generated tool owns deterministic record binding; the actor supplies
visible evidence and semantic update values.

Success confirmations are also validated. They must contain every nonempty
changed value supplied in the public `updates` mapping. Avoiding opaque native
identifiers remains generation guidance, but it is not a hard acceptance gate:
identifier wording does not alter state correctness, action safety, or task
completion. Allowed update keys are derived from the public signature of the
preserved native action, so the actor sees valid writable fields without any
task answer or benchmark label.

## Matched Evaluation Ladder

### Focused 20-task diagnostic

The corrected native-action mechanism generated
`select_message_counterparty_for_contact_update`, validated source, two
held-out, and one negative case, called the preserved `modify_contact` native
implementation, and produced the correct final state with no runtime or
side-effect incident. The generated-tool-called subset had baseline outcome
`0.040293` and SAGE outcome `0.733766`. This was a focused mechanism diagnostic,
not a general performance estimate.

### Contact birth-and-reuse gate

The opaque-identifier interface correction was tested with an empty registry
on two contact-update tasks: one tool-birth task and one later multi-turn reuse
task. `gpt-4o-mini` generated
`select_message_counterparty_for_contact_update`, failed its first public
validation attempt, repaired the oldest-selection and confirmation defects,
and passed source, held-out, and negative validation.

- Cached-control mean outcome: `0.141026`.
- Fresh SAGE mean outcome: `0.934211`.
- Absolute paired outcome gain: `+0.793185`.
- Outcome gains/regressions: `2 / 0`.
- SAGE outcomes: `1.000000` on tool birth and `0.868421` on reuse.
- Native runtime or side-effect incidents: `0`.
- Run:
  `outputs/native_action_diagnostics/contact_reuse2_visible_identity_v3/mechanism_40_20260720_060610`.

This gate establishes mechanism viability, not population-level performance.

A second empty-registry contact gate tested the actor-facing schema correction.
The accepted tool schema preserved model-authored descriptions and required
complete visible records, including the contact marked `is_self=true`.

- Cached-control mean outcome: `0.141026`.
- Fresh SAGE mean outcome: `0.791444`.
- Absolute paired outcome gain: `+0.650418`.
- Outcome gains/regressions: `2 / 0`.
- Run:
  `outputs/native_action_diagnostics/contact_reuse2_preserved_schema_v4/mechanism_40_20260720_063356`.

### Reminder native-action gate

An independent empty-registry matched gate tested one generated tool that used
the explicit visible `action_type` input to dispatch between two approved
reminder actions. The generated tool passed source, held-out, and negative
validation and executed the preserved native implementations in both tasks.

- Standard SAGE outcome: `1.000000`.
- Native-action SAGE outcome: `1.000000`.
- Native actions executed: `modify_reminder`, `remove_reminder`.
- Runtime or side-effect incidents: `0`.
- Accepted tools: standard `5`, native-action `4`.
- Run: `outputs/native_action_4omini_ab/reminder2_20260720_062109`.

### Representative 60-task comparison

Both arms use the same deterministic representative manifest, task order,
fixed clock, strict cached controls, models, generation settings, and empty
registries. The only treatment difference is whether eligible generated tools
may carry the per-tool native-action delegation marker.

- Manifest:
  `artifacts/chapter3_token_reduction/representative_samples/toolsandbox_representative_60.json`
- Manifest SHA-256:
  `9430d91fa3a79d3ce7e3dc99ae4b0d1ff9cef098e6c0f3f0fb2278c477b6dea2`
- Controls: 60 cached, 0 fresh.
- Primary comparison: paired per-task outcome difference.
- Supporting analysis: native wins, standard wins, ties, paired bootstrap 95%
  confidence interval, paired randomization test, and exact sign test.

The first 60-task diagnostic exposed a process-wide permission defect and is
not claim evidence. The corrected run uses an explicit per-tool permission and
is recorded under:

`outputs/native_action_4omini_ab/representative60_20260719_180112`

The current action-first matched validation uses the same representative
60-task set reordered so action-eligible tasks occur early. Reordering changes
the online learning trajectory, so it is a mechanism and stress-test cohort;
the standard-order representative 250 remains the promotion cohort. Both
60-task arms begin with empty registries and generate their tools within the
measured run:

`outputs/native_action_4omini_ab/action_first60_20260720_060959`

The completed action-first 60-task run is:

`outputs/native_action_4omini_ab/action_first60_20260720_111546`

- Standard SAGE outcome: `0.672286`.
- Native-action SAGE outcome: `0.645933`.
- Paired native-minus-standard outcome: `-0.026354` over 47 scored tasks.
- Native/standard/tied outcomes: `6 / 13 / 28`.
- Paired bootstrap 95% interval: `[-0.120545, 0.069072]`.
- Paired randomization p-value: `0.598988`.
- Runtime exceptions: `0 / 0`.

This run did not establish broad superiority. It exposed two contract defects:
the contact tool required the actor to project contact records while preserving
an `is_self` marker, and the recency-tool repair loop repeatedly supplied stale
errors that later candidates had already fixed. The public contact contract was
replaced by the visible scalar `self_person_id`, and repairs now receive only
the remaining errors of the best current candidate.

### Corrected 20-task action cohort

The corrected implementation was evaluated with empty registries on a 20-task
cohort covering contact selection, reminder recency, insufficient-information
cases, direct contact actions, messaging, and device state:

`outputs/native_action_4omini_ab/action20_20260720_122526`

- Standard SAGE outcome: `0.759804`.
- Native-action SAGE outcome: `0.826936`.
- Paired native-minus-standard outcome: `+0.067132` over 17 scored tasks.
- Native/standard/tied outcomes: `6 / 3 / 8`.
- Paired bootstrap 95% interval: `[-0.056628, 0.216180]`.
- Paired randomization p-value: `0.438611`.
- Native-action executions: one `modify_contact`, one `modify_reminder`, and
  one `remove_reminder`.
- Failed native-action calls, runtime exceptions, side-effect flags, and tool
  runtime incidents: `0 / 0 / 0 / 0`.

The contact tool reached task outcome `1.0`. The recency tool reached task
outcome `1.0` on its modify birth task and again on its later remove reuse task.
The positive aggregate difference is not statistically conclusive at this
sample size, but it confirms that the corrected contracts can be generated,
called naturally, and reused without an extra actor turn.

### Strict 8-task contract confirmation

Inspection of the 20-task recency candidate found that its held-out validation
did not require `oldest` selection and that its tie negative could be passed by
rejecting an otherwise unsupported update. The admission contract was therefore
strengthened to require latest remove, latest modify, oldest remove, and a tie
case using an otherwise valid modify update. No generated tool body was added to
the framework.

The final empty-registry matched confirmation is:

`outputs/native_action_4omini_ab/action8_20260720_124835`

- Standard SAGE outcome: `0.873149`.
- Native-action SAGE outcome: `0.827342`.
- Paired native-minus-standard outcome: `-0.045806` over seven scored tasks.
- Native/standard/tied outcomes: `1 / 4 / 2`.
- Native-action executions: one `modify_contact`, one `modify_reminder`, and
  one `remove_reminder`.
- Failed native-action calls, runtime exceptions, side-effect flags, and tool
  runtime incidents: `0 / 0 / 0 / 0`.

`gpt-4o-mini` repaired the recency candidate on the fifth permitted repair and
reached validation score `0` across all four cases. Both reminder executions
then reached task outcome `1.0`. The contact execution also reached task outcome
`1.0` and exceeded standard SAGE by `+0.692308` on that row. The four aggregate
losses occurred on rows where no native-action tool executed. They are arm-level
actor/generation variation and must not be described as direct native-action
failures.

### Representative 250-task comparison

Promotion to 250 requires the corrected 60-task native arm to preserve standard
SAGE outcome, produce at least one naturally called and validated native-action
tool, and show no runtime or native side-effect incident. The 250-task study
uses:

- Manifest:
  `artifacts/chapter3_token_reduction/representative_samples/toolsandbox_representative_250.json`
- Manifest SHA-256:
  `a28e77a46c39dd86ca7ef15402caf837f0825640aff6117a965ec6c3fda07012`
- Controls: strict cached controls only.
- SAGE: fresh empty registries and generation enabled in both arms.

### Full-dataset native-action evaluation

The final standard-order evaluation resumed the same frozen-clock SAGE lineage
from its task-794 registry checkpoint and completed all 1,032 tasks. The resume
preserved the original task order, fixed timestamp, task results, registry, and
tool provenance. It did not rerun or replace completed SAGE rows.

- Run:
  `outputs/native_action_4omini_ab/full_20260721_091909/native_action/online_build_full_20260721_091916`
- Task Compare dashboard:
  `outputs/native_action_4omini_ab/full_20260721_091909/native_action/online_build_full_20260721_091916/dashboard/task_compare.html`
- Models: `gpt-4o-mini` for actor, user simulator, generation, and repair.
- Controls: `1,032` strict cached / `0` fresh.
- SAGE task cache and OpenAI response cache: off.
- Bridge, diagnostic force calls, scenario-name birth, and scenario-name
  routing: disabled.
- Extra actor-turn and generated-tool contract retries: disabled. No transient
  scenario retry was exercised.
- Score: `0.733488 -> 0.806969`, delta `+0.073480`, lift `+10.02%`.
- Composite outcome: `0.457342 -> 0.786036`, delta `+0.328694`, lift
  `+71.87%`.
- Exact successes: `200 -> 370`, delta `+170`.
- Score gain/regression/preserved: `458 / 212 / 362`.
- Outcome gain/regression/preserved: `456 / 103 / 241` across `800`
  outcome-scored tasks.
- Generated-tool visibility/attempt/call: `804 / 689 / 734` scenarios.
- Generated-tool reuse events: `1,864`.
- Runtime exceptions: `0`.

The called-generated-tool subset provides the most direct mechanism evidence.
Across `734` tasks where a generated tool was called, outcome increased from
`0.370593` to `0.804165`, an absolute gain of `+0.433572` and relative lift of
`+116.99%`. These rows contained `421` outcome gains, `60` regressions, and
`134` preserved outcomes. In contrast, the `124` attribution rows where a
generated tool was visible but not called were net negative (`-0.097846`
outcome). The aggregate gain is therefore concentrated in actual generated-tool
execution rather than mere SAGE-arm membership.

The resumed segment evaluated `11` new tool candidates. `gpt-4o-mini` accepted
three after validation and repair: `plan_send_message_contact_lookup`,
`plan_contact_relationship_batch_update`, and
`plan_contact_update_from_id`. Eight candidates were rejected: four attempts
at `resolve_search_window_or_bounds` and four at
`plan_device_state_action_sequence_v3`. The registry contained `24` validated
tools at the checkpoint and `27` at completion. Every accepted tool was called.

#### State completion and answer-credit boundary

The benchmark composite outcome combines state checks with final-answer checks.
The completed SAGE run averaged `0.925000` across `720` included state checks,
with `666` exact state checks, but `0.680738` across `632` answer checks. At the
task level, the corresponding means were `0.925000` over `520` state-scored
tasks and `0.685568` over `624` answer-scored tasks. Thus SAGE exceeded the
requested `0.8` threshold for environment-state completion, while the reported
composite outcome remained `0.786036`.

One representative contact-relationship trace completed both required native
`modify_contact` actions and received state score `1.0`, but the fixed task turn
budget ended after the second action. With no extra SAGE-only turn permitted,
the trace lacked a final confirmation sentence and received answer score
`0.470588`, producing composite outcome `0.735294`. This is evidence of an
evaluation-credit boundary, not permission to add an unfair completion turn.

The remaining device-state loss also has a concrete framework cause. The
validated one-action tool supported Wi-Fi, cellular, and location setters but
did not include the equally visible low-battery-mode setter. On a Wi-Fi task,
the actor correctly discovered that low-battery mode blocked Wi-Fi activation,
but the generated tool abstained when asked to disable that precondition. A
future contract may derive the complete finite set of one-action Boolean
setters from visible native schemas. It must not encode ToolSandbox task names
or hard-code a task sequence.

#### Safety-audit qualification

The resumed portion, tasks `554-1032`, produced no new side-effect-preservation
flags. The merged lineage still contains `21` flags from tasks `151-519`, all
created before the audit recognized validated native-action delegation. They
name three validated tools and are inherited evidence, not newly observed
runtime exceptions. They must be re-adjudicated before describing the whole
lineage as having zero side-effect incidents. The protocol gate passed and the
run recorded zero runtime exceptions.

## Promotion Rule

Native-action generation becomes part of the primary SAGE configuration only
if the wider matched evidence shows no outcome regression, naturally called
direct-action tools account for successful final states, validation remains
clean, and no native side-effect incident occurs. A numerical aggregate gain
without direct-action attribution is not sufficient.

## Final Decision

`FULL_DATASET_CANDIDATE_VALIDATED_PENDING_SAFETY_READJUDICATION`

Native-action generation is viable at full-dataset scale and the completed
candidate is the strongest current clean-method full-run outcome (`0.786036`).
It also achieved `0.925000` mean state-check completion. The direct mechanism
attribution is strong: tasks that called generated tools reached `0.804165`
outcome versus `0.370593` for their matched controls.

This run does not, by itself, prove that native-action tools broadly outperform
standard SAGE because the full comparison arm was the non-learning baseline,
not a simultaneous standard-SAGE arm. The inherited 21 pre-fix safety-audit
flags also require adjudication. Standard SAGE remains the publication default
until that audit is complete or a matched full standard-SAGE comparison is
performed. The native-action configuration is nevertheless the leading
full-dataset candidate for outcome-focused follow-up.
