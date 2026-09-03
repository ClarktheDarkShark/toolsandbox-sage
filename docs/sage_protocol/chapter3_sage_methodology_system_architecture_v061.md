# Chapter 3 Working Draft: SAGE Methodology and System Architecture

Status: editable praxis draft for the current v061 evidence line
Prepared: 2026-06-14
Scope: SAGE methodology, SAGE system architecture, and the current v061 measurement package
Excluded: general baseline ToolSandbox background, except where needed to define the SAGE control comparison, inherited tool boundary, or evaluation interface

## 1. Current Evidence Snapshot

The current v061 run is the evidence anchor for this draft:

```text
Current v061    0.733214 -> 0.801186, +9.27%    0.454251 -> 0.757267, +66.71%    825    3    1    17,245,671
```

Interpreted fields:

| Field | Meaning |
|---|---:|
| Canonical/reference score | 0.733214 control -> 0.801186 SAGE |
| Canonical relative lift | +9.27% |
| Final-task/outcome score | 0.454251 control -> 0.757267 SAGE |
| Final-task/outcome relative lift | +66.71% |
| Scenarios where generated tools were called | 825 |
| Scenarios with generated-tool failure events | 3 |
| Side-effect preservation incidents | 1 |
| SAGE candidate LLM tokens | 17,245,671 |

Primary run artifacts:

| Artifact | Path |
|---|---|
| Run root | `outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410` |
| Registry | `artifacts/chapter3_token_reduction/v061_finish_v059_registry` |
| Protocol manifest | `outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410/protocol_manifest.json` |
| Paired comparison | `outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410/paired_comparison.json` |
| Generated-tool contribution summary | `outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410/helper_contribution_summary.json` |
| Dashboard data | `outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410/dashboard/task_compare_data.json` |
| Dashboard | `outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410/dashboard/task_compare.html` |

Token reduction is an active engineering improvement and should be handled in a later chapter subsection or revision. This Chapter 3 draft records the current token cost as an observed cost of v061, not as a final optimized value.

## 2. Chapter Claim Boundary

SAGE is evaluated here as a self-evolving agent system that can autonomously generate deterministic tools, validate them, store them in a reusable registry, expose them during later tasks, and measure whether natural tool use improves task completion. SAGE does not update model weights. Its learning mechanism is tool-level adaptation: accepted Python tools become persistent registry entries that can be routed into future tasks.

The SAGE system is an outer orchestration and augmentation layer. It preserves the inherited task environment and original side-effect tools, then adds the following SAGE-owned capabilities:

- inadequacy detection and observation logging;
- autonomous generated-tool specification and code generation;
- candidate adequacy gating;
- deterministic sandbox validation;
- persistent registry storage and code-hash provenance;
- runtime routing and bounded generated-tool exposure;
- generated-tool injection into the actor's callable tool set;
- generated-tool reuse logging;
- side-effect preservation checks;
- paired evaluation and generated-tool contribution analysis.

The experimental treatment is SAGE itself.

## 3. Research Questions and Hypotheses

The current hypotheses should be phrased around the measured SAGE mechanism. The final-task/outcome score is the sole performance endpoint. The canonical/reference score is retained only as a descriptive compatibility and milestone diagnostic and never determines a hypothesis or release decision.

### RQ1: Frozen Registry Reuse

Can tools generated during online self-evolution be reused later from a frozen registry, with generation disabled, while preserving most of the online-build gain?

Hypothesis 1:

> A self-evolving AI agent using autonomous tool generation can create reusable tools that are naturally selected and called in later tasks, preserving at least 80 percent of online-build task-completion accuracy gains when reused from a frozen registry.

Operational definition:

```text
frozen_retention_ratio = frozen_registry_outcome_delta / online_build_outcome_delta
```

For the current v061 online-build run:

```text
online_build_outcome_delta = 0.7572667814756449 - 0.45425082649352005
                           = 0.3030159549821248

80_percent_retention_threshold = 0.3030159549821248 * 0.80
                               = 0.24241276398569986
```

Therefore, a matching frozen-registry run must achieve an outcome delta of at least 0.242413 to satisfy H1. The v061 online-build canonical delta of 0.06797136278269156 may be reported descriptively, but no canonical retention threshold is used for H1 or release decisions.

Current v061 status for H1: not yet decided by this online-build run alone. H1 requires a generation-off frozen-registry reuse run on the matched task set and configuration.

### RQ2: Online Self-Evolution Versus Non-Learning Control

Does online self-evolving SAGE improve task completion over a matched non-learning control agent?

Hypothesis 2:

> A self-evolving AI agent using autonomous tool generation can improve task-completion accuracy by at least 10 percent over a non-learning AI agent on matched benchmark tasks.

Operational definition:

```text
relative_outcome_lift = (sage_mean_outcome - control_mean_outcome) / control_mean_outcome
```

Current v061 result:

```text
control_mean_outcome = 0.45425082649352005
sage_mean_outcome    = 0.7572667814756449
relative lift        = 66.71%
```

Current v061 status for H2: supported on the final-task/outcome measure. Canonical/reference similarity improved by +9.27% and is retained only as descriptive route evidence; the 10 percent H2 threshold applies exclusively to task-completion outcome.

### RQ3: Tool-Called Subset and Non-Leakage

When SAGE's generated tools are naturally called, does the system produce large gains without using hidden answer labels, benchmark-answer leakage, or synthetic task completions?

Hypothesis 3:

> A self-evolving AI agent using autonomous tool generation can improve task-completion accuracy by at least 30 percent on tasks where generated tools are naturally called, without relying on benchmark-answer leakage or synthetic code-based task completions.

Operational definition:

```text
called_tool_relative_outcome_lift =
    (sage_called_bucket_mean_outcome - control_called_bucket_mean_outcome)
    / control_called_bucket_mean_outcome
```

Current v061 called-generated-tool bucket:

```text
scenario_count              = 825
control_mean_outcome        = 0.423081651382416
sage_mean_outcome           = 0.7729835798928341
mean_outcome_delta          = 0.3499019285104181
relative outcome lift       = 82.70%
```

Current v061 status for H3: supported on the primary outcome measure for the natural generated-tool-called subset, subject to the generated-tool failure, side-effect preservation, and limitation caveats reported later in this chapter.

## 4. Experimental Design

The evaluation uses a paired, task-level comparison between a non-learning control arm and a SAGE candidate arm. Both arms run over the same task manifest and task order. The comparison is paired at the scenario level so that every measured SAGE score has a matching control score.

### 4.1 Control Arm

The control arm represents the non-learning comparison condition. It uses the original task environment and original callable tools, without access to the generated-tool registry and without online generated tool generation. In v061, the control arm is score-complete through the protocol's control-cache mechanism:

```text
control_cache_mode           = use-if-eligible
cached_control_tasks         = 1032
fresh_control_tasks          = 0
cache_match_policy           = experimental_task_name_base_tool_policy_min1_model_user_bypassed
```

The control cache is used only for the control arm. It does not provide cached SAGE outcomes and does not replace fresh SAGE candidate execution. The cache policy records task identity and base-tool policy compatibility so that the comparison remains matched to the selected benchmark tasks.

### 4.2 SAGE Candidate Arm

The SAGE arm uses the same original environment and original side-effect tools as the control arm, then augments the actor with SAGE's generated-tool lifecycle:

1. observe task context and inadequacy signals;
2. generate candidate tools when justified;
3. validate candidate tools before registry admission;
4. route accepted tools into appropriate later tasks;
5. allow the actor to call generated tools naturally;
6. log visibility, calls, failures, reuse, and side-effect preservation;
7. compare the paired result against the control run.

In online-build mode, generation is enabled. In frozen-registry reuse mode, generation must be disabled and the registry is loaded only for routing and invocation. This distinction is central to H1.

### 4.3 Current v061 Protocol Settings

The current v061 evidence line uses:

| Setting | Value |
|---|---|
| Protocol mode | `online_build_full` |
| SAGE policy | `self-evolving-praxis` |
| Generation | enabled |
| Manifest split | `full_benchmark` |
| Manifest type | `v2_1_formal_1000plus_full_benchmark_best3_scale` |
| Paired scenarios | 1032 |
| Outcome-scored scenarios | 800 |
| Agent model | `gpt-4o-mini` |
| User model | `gpt-4o-mini` |
| Tool-generation model | `gpt-4o-mini` |
| Model comparison key | `agent=gpt-4o-mini|generation=gpt-4o-mini|user=gpt-4o-mini` |
| Model context window | 128000 |
| Model maximum output tokens | 16384 |
| Model supports function calling | true |
| Model supports structured outputs | true |
| Base tool policy | `upstream` |
| ToolSandbox clock policy | frozen |
| Fixed timestamp | `1781397250.09937` |
| Repository whole-response replay cache | disabled; provider prompt-prefix computation was not separately measured in this historical run |
| Routing evidence mode | disabled |
| Diagnostic force flags | disabled |
| Praxis bridge policy | disabled |
| Runtime generated-tool bundle cap | 4 |
| Registry manifest digest after run | `88ff481940832fbadbbfd55d858fa46d30f5b7dfbbb3830075af06dc7450979d` |

The run-affecting SAGE environment included:

```text
SAGE_CONTROL_CACHE_MIN_COMPATIBLE_RUNS=1
SAGE_DISABLE_SCENARIO_NAME_BIRTH=1
SAGE_DISABLE_SCENARIO_NAME_ROUTING=1
SAGE_ENABLE_SAFE_ABSTAIN_BIRTH=1
SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY=1
SAGE_GENERATED_TOOL_CONTINUATION_CHOICE=1
SAGE_GENERATED_TOOL_DOCSTRING_MODE=compact
SAGE_GENERATED_TOOL_FIRST_ATTEMPT_CHOICE=1
SAGE_GENERATED_TOOL_GUIDANCE_MODE=minimal
SAGE_MAX_RUNTIME_GENERATED_TOOL_BUNDLE_SIZE=4
SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS=120
SAGE_PRAXIS_BRIDGE_POLICY=disabled
SAGE_ROUTING_EVIDENCE_MODE=disabled
SAGE_SCENARIO_METADATA_POLICY=visible_context
SAGE_SELF_EVOLVING_MIN_PULSE_TASKS=8
SAGE_SELF_EVOLVING_PROACTIVE_BIRTH=1
SAGE_SELF_EVOLVING_PROACTIVE_SCOPE=just_in_time
SAGE_SELF_EVOLVING_PULSE_INTERVAL=4
SAGE_SELF_EVOLVING_REFLECTION=1
SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS=4
SAGE_V2_EXPERIMENT_FEATURES=contract_synthesis,candidate_repair,dependency_logic,medium_grain_skills
```

### 4.4 Unit of Analysis, Task Corpus, and Sample Justification

The unit of analysis is the individual paired task scenario. Each scenario contributes one control observation and one SAGE observation. This pairing is the basis for estimating the treatment effect because it holds the task prompt, task environment, scoring target, and scenario ordering constant across arms.

The study population is the class of tool-mediated assistant tasks represented by the benchmark corpus: tasks requiring retrieval, filtering, record selection, timestamp reasoning, state-precondition reasoning, argument preparation, safe abstention, and side-effect-preserving action. The v061 sample is the full selected benchmark manifest rather than a convenience subset:

```text
paired_scenarios = 1032
outcome_scored_scenarios = 800
```

This sample size is justified methodologically because the research questions concern system-level task-completion lift and generated-tool reuse across a diverse task population. A small hand-selected subset would be inappropriate for the primary claims because it could overrepresent tasks where generated tools are likely to help. The full manifest reduces selection bias and permits separate analysis of called-generated-tool, visible-not-called, and no-visible-generated-tool cases.

### 4.5 Methodology Chapter Alignment

This Chapter 3 draft is organized around standard doctoral methodology expectations: research questions and hypotheses, research design, sample and unit of analysis, instrumentation, treatment procedure, data collection, data analysis, validity and reliability controls, research-integrity controls, limitations, and reproducibility. For SAGE, "participants" maps to paired task scenarios, "instruments" maps to scoring functions and system logs, and "procedure" maps to the controlled comparison between the non-learning control arm and the SAGE treatment arm.

## 5. Methodological Model of the SAGE Treatment

This chapter should present SAGE as the experimental treatment, not as a software execution story. The relevant methodological question is: what condition is being introduced into the candidate arm, how is it operationalized, how is it measured, and what controls prevent alternative explanations?

The SAGE treatment is an online self-evolution condition in which the agent is allowed to construct, validate, persist, route, and naturally use deterministic generated tools while solving a matched task corpus. The control condition is a non-learning condition in which the actor has the original task environment but no generated-tool learning mechanism. The unit of analysis is the paired task scenario.

The SAGE treatment has eleven mechanism components:

```text
visible task context
online birth controller
candidate tool generator
candidate gate
sandbox validator
registry store
runtime router
generated-tool injection
actor execution
reuse and side-effect logs
reflection and registry checkpoint
```

These are not separate experiments. They are the operational chain that converts a visible task context into a possible reusable tool and then tests whether the actor naturally selects that tool during task completion.

For Chapter 3 purposes, each component should be described in terms of:

- input available to the agent;
- decision or transformation performed;
- output produced;
- methodological role in the research design;
- evidence recorded for later analysis;
- validity control enforced by the component.

Editable or renderable figures already exist for this chapter and should be used to communicate this treatment model visually:

| Figure | Path |
|---|---|
| SAGE self-evolution flow | `docs/sage_protocol/figures/sage_self_evolution_flow_v061.svg` and `.png` |
| SAGE self-evolution publication loop | `docs/sage_protocol/figures/sage_self_evolution_loop_publication.svg`, `.png`, and `.html` |
| Tool generation, validation, and repair loop | `docs/sage_protocol/figures/sage_tool_generation_validation_repair_loop.svg` and `.png` |
| Peer-review methodology figure | `docs/sage_protocol/figures/sage_peer_review_methodology_figure.svg` and `.png` |
| SAGE design loop | `docs/sage_protocol/figures/sage_self_evolution_loop_design.html`, `.png`, and `.pdf` |

## 6. SAGE Treatment Components

### 6.1 Visible Task Context

Visible task context is the information available to SAGE before or during a task that a normally situated agent could observe without access to benchmark answers. In v061, visible context includes the user-facing task request, the current task-family signals, visible tool affordances, and conversation/tool-trace-visible state. It excludes hidden scenario names as a birth or routing signal.

The visible-context policy is central to the research design because it defines the boundary between legitimate task interpretation and benchmark leakage. SAGE can use the same kind of contextual evidence that would be available in a real task setting, but it cannot use hidden benchmark identifiers to decide what tool to create or expose.

Current v061 controls:

```text
SAGE_SCENARIO_METADATA_POLICY=visible_context
SAGE_DISABLE_SCENARIO_NAME_BIRTH=1
SAGE_DISABLE_SCENARIO_NAME_ROUTING=1
```

Methodological role:

- defines the observable input space for tool creation and tool routing;
- prevents scenario-name memorization from explaining the measured gains;
- supports H3's claim that generated-tool-called gains are not caused by hidden benchmark-answer leakage.

Evidence recorded:

- generated-tool visibility by scenario;
- generated-tool selection by scenario;
- attribution buckets based on whether generated tools were visible and called.

### 6.2 Online Birth Controller

The online birth controller is the mechanism that decides whether the current evidence justifies proposing a new generated tool. It is the "self-evolving" part of the treatment. It does not directly solve the task. Instead, it identifies a recurring or generalizable task shortfall and converts that shortfall into a candidate tool request.

The controller may act just in time, meaning it can respond to visible task context before the candidate trajectory is complete. This gives a new generated tool an opportunity to be available during the same task, but it does not force the actor to call the generated tool.

Current v061 controls:

```text
SAGE_SELF_EVOLVING_PROACTIVE_BIRTH=1
SAGE_SELF_EVOLVING_PROACTIVE_SCOPE=just_in_time
```

Inputs:

- visible task context;
- observed inadequacy or anticipated shortfall;
- known task-family labels;
- prior registry coverage;
- failure memory and shortfall cluster evidence.

Decision rule:

- generate only when the shortfall appears reusable rather than task-singular;
- avoid creating a generated tool if an accepted registry tool already covers the mechanism;
- avoid birth decisions based on hidden scenario names;
- prefer generated tools that compress repeated reasoning or tool-use patterns.

Outputs:

- a candidate generation request when a reusable shortfall is identified;
- no tool proposal when the need is too narrow, already covered, or not supported by visible evidence.

Methodological role:

- operationalizes online learning as autonomous tool proposal;
- separates SAGE from a static prompt or static tool bundle;
- creates the mechanism to test whether generated tools can later be naturally selected.

Evidence recorded:

- generated-tool birth attempts;
- accepted tool births;
- newly accepted tool names;
- registry growth during online-build mode.

### 6.3 Candidate Tool Generator

The candidate tool generator converts the birth request into a proposed deterministic generated tool. The product is not merely code. It is a structured research instrument consisting of a tool specification, an input/output contract, applicability criteria, safety constraints, validation evidence, and executable generated tool logic.

The generator must propose tools that are reusable across task contexts. This is essential because the study is not testing whether an agent can write one-off code to answer one benchmark item. It is testing whether autonomous tool generation creates reusable procedural knowledge that can be selected later.

Supported generated tool families:

| Family | Methodological purpose |
|---|---|
| `canonicalizer` | Standardize values that otherwise create avoidable reasoning or matching errors |
| `derived_value_calculator` | Compute deterministic intermediate values needed for task completion |
| `state_precondition_tool` | Determine whether a state-changing action has sufficient preconditions |
| `search_filter_ranking_tool` | Select or rank records from visible search results |
| `composite_workflow_tool` | Prepare a multi-step action plan while preserving original side-effect tools |
| `validation_abstention_tool` | Identify cases where safe abstention is preferable to unsafe action |

Required specification fields include:

- tool name;
- generated-tool family;
- input schema;
- output schema;
- positive triggers;
- negative triggers;
- abstention behavior where relevant;
- preserved or required original tool calls;
- generalization rationale;
- expected step compression;
- cross-task applicability;
- applicable task-family labels;
- shortfall evidence;
- failure mechanisms addressed;
- final-state preservation plan.

Generator constraints:

- the generated tool must be deterministic;
- the generated tool must not use hidden answers or scenario labels;
- the generated tool must not access the network or file system;
- the generated tool must not replace a single original tool without adding reusable reasoning value;
- the generated tool must preserve downstream original side-effect calls when state change is required;
- the generated tool should compress at least three reasoning or tool-use steps;
- the generated tool should apply across at least two task families.

Current v061 generation controls:

```text
SAGE_GENERATED_TOOL_GUIDANCE_MODE=minimal
SAGE_GENERATED_TOOL_DOCSTRING_MODE=compact
SAGE_V2_EXPERIMENT_FEATURES=contract_synthesis,candidate_repair,dependency_logic,medium_grain_skills
```

Methodological role:

- operationalizes the adaptive artifact as a reusable deterministic generated tool;
- makes generated procedural knowledge inspectable and auditable;
- prevents the study from depending on opaque model memory alone.

Evidence recorded:

- generated tool specifications;
- accepted tool code snapshots;
- validation results;
- registry manifest entries and code hashes.

### 6.4 Candidate Gate

The candidate gate is the first validity filter. Its purpose is to prevent weak, unsafe, overfitted, or non-general generated tools from entering the reusable registry. In research-method terms, it protects construct validity: a registry entry should represent a reusable generated tool, not a one-off answer, a hidden benchmark shortcut, or a trivial wrapper around an existing tool.

The gate evaluates whether the proposed generated tool satisfies the definition of a SAGE-generated reusable tool.

Accepted candidates must show:

- supported generated-tool family;
- valid input and output contract;
- positive and negative applicability conditions;
- meaningful generalization rationale;
- structured inadequacy evidence;
- step compression;
- cross-task applicability;
- safety and abstention behavior where relevant;
- preservation of required original side-effect tools;
- no scenario-label or answer-label dependence.

Rejected candidates include:

- single-tool replacements with no reusable reasoning;
- generated tools that only encode benchmark-specific constants;
- calculators with no meaningful task-completion value;
- search selectors without ambiguity or tie behavior;
- state generated tools that do not produce actionable scalar arguments;
- composite generated tools that bypass required original side-effect tools.

Methodological role:

- ensures the independent variable is autonomous reusable tool generation, not arbitrary code generation;
- prevents overfitting to source examples;
- prevents benchmark-answer leakage through tool content;
- supports later frozen-registry reuse claims because accepted tools have documented generality requirements.

Evidence recorded:

- accepted or rejected candidate status;
- rejection reasons;
- accepted candidate metadata;
- validation-proof requirements attached to the registry entry.

### 6.5 Sandbox Validator

The sandbox validator is the empirical instrument used to test whether a proposed generated tool behaves deterministically and safely before it can be reused. This is the analog of instrument validation in a research methods chapter: before a generated tool can be treated as part of the experimental intervention, it must demonstrate that it performs the claimed transformation under controlled examples and negative cases.

Validation includes:

- source examples;
- held-out semantic examples;
- negative applicability examples;
- expected-output checks;
- deterministic repeat execution;
- JSON-serializability checks;
- runtime smoke invocation;
- restricted execution checks.

For state, search, and composite generated tool families, validation requires negative applicability evidence. This prevents a generated tool from passing merely because it works on favorable examples while being unsafe on near misses.

Safety restrictions:

- no imports;
- no file access;
- no network access;
- no dynamic evaluation;
- no subprocess or operating-system calls;
- one generated function matching the specification;
- restricted builtins only.

Methodological role:

- improves reliability by checking deterministic repeated behavior;
- improves internal validity by excluding unsafe or overbroad tools before treatment exposure;
- improves reproducibility by storing validation proof with accepted tools;
- separates accepted generated tools from raw model outputs.

Evidence recorded:

- validation accepted/rejected status;
- held-out check count;
- negative applicability count;
- runtime smoke-test status;
- validation errors when present.

### 6.6 Registry Store

The registry store is the persistent memory of the SAGE treatment. It is where accepted generated tools become reusable artifacts. In the study design, the registry is the material substrate for self-evolution: without a persistent registry, SAGE would be an online code-generation system but not a cumulative tool-learning system.

Registry entries store:

- tool specification;
- generated tool code;
- validation result;
- birth context;
- accepted timestamp;
- version;
- reuse count;
- success flips;
- retired status;
- schema version;
- stored code hash;
- diagnostic flag if applicable.

A generated tool can be exposed only if it has current validation proof:

- accepted;
- not retired;
- held-out validation present;
- negative applicability present for state, search, and composite generated tools;
- runtime smoke test passed;
- schema version current;
- stored code hash verified;
- candidate gate still satisfied.

Current v061 registry size:

```text
22 accepted tools
```

Current v061 accepted registry tools:

```text
days_between_timestamps
extract_service_answer_field
extract_stock_symbol
next_weekday_time_to_timestamp
plan_contact_lookup_query
plan_contact_relationship_batch_update
plan_device_state_action_sequence_v3
plan_device_status_lookup
plan_message_counterparty_search
plan_send_message_contact_lookup
prepare_add_contact_args
prepare_direct_contact_action_args
prepare_holiday_search_args
prepare_location_search_args
prepare_reminder_creation_args
prepare_safe_action_or_abstain
relative_day_time_to_timestamp
resolve_search_window_or_bounds
select_action_target_by_recency
select_message_content_by_recency
select_message_counterparty_for_contact_update
select_record_by_timestamp_extreme
```

Newly accepted during v061:

```text
plan_contact_relationship_batch_update
plan_send_message_contact_lookup
```

Methodological role:

- operationalizes learned procedural memory;
- enables frozen-registry reuse tests;
- permits audit of what was learned and when;
- prevents accepted tools from changing silently through code-hash verification.

Evidence recorded:

- registry manifest;
- registry digest;
- accepted tool inventory;
- newly accepted tools;
- reuse counts;
- validation proof for each accepted generated tool.

### 6.7 Runtime Router

The runtime router determines which accepted generated tools are visible on a given task. This is a critical methodological component because the study is not testing a condition in which the actor sees every generated tool at all times. It is testing whether accepted tools can be selected when routed into relevant contexts.

The router uses visible task evidence, positive triggers, negative triggers, applicable family labels, shortfall cluster metadata, and side-effect preservation metadata. It excludes hidden scenario names in v061.

Routing hides tools that are:

- retired;
- not accepted;
- missing current validation proof;
- blocked by negative triggers;
- irrelevant to the visible task context;
- too risky for the current action context.

Current v061 runtime exposure policy:

```text
SAGE_MAX_RUNTIME_GENERATED_TOOL_BUNDLE_SIZE=4
SAGE_ROUTING_EVIDENCE_MODE=disabled
```

Current v061 runtime bundle summary:

| Runtime exposure metric | Value |
|---|---:|
| Scenario count represented in bundle summary | 1028 |
| Mean generated-tool bundle size | 1.5350194552529184 |
| Maximum generated-tool bundle size | 4 |
| Mean available tool count including original tools | 12.441634241245136 |
| Maximum available tool count including original tools | 38 |

Methodological role:

- defines generated-tool exposure;
- prevents registry size alone from creating an unfair all-tools condition;
- supports natural-selection analysis by distinguishing visible tools from called tools;
- creates the visible-not-called and no-visible-generated-tool attribution buckets.

Evidence recorded:

- tools visible per scenario;
- generated-tool bundle size;
- visibility bucket membership;
- visible-not-called cases.

### 6.8 Generated-Tool Injection

Generated-tool injection is the point at which routed registry tools become available to the actor as callable tools. The relevant methodological feature is not how the tool is technically wrapped, but what information is exposed to the actor.

In v061, generated tools are exposed with compact descriptions and callable schemas. The actor receives enough information to understand when the generated tool is relevant, what inputs it expects, what output it returns, and whether it preserves downstream original tool calls. The generated tool does not carry hidden benchmark answers.

Generated-tool injection can also make use of conversation-visible and tool-trace-visible information to reduce argument friction. Examples include visible search records, selected records, current timestamp information, contact records, setting states, and original tool payloads. These are runtime-visible affordances, not hidden labels.

Methodological role:

- standardizes how generated tools are presented to the actor;
- makes generated tools available without forcing use;
- preserves natural actor choice;
- allows the study to distinguish exposure from adoption.

Evidence recorded:

- which generated tools were injected;
- which generated tools were available but not called;
- generated-tool call attempts and results.

### 6.9 Actor Execution

Actor execution is the task-solving phase in which the model interacts with the available tool set. In the SAGE arm, the actor sees the original task environment plus any routed generated tools. The actor may call generated tools, original tools, both, or neither.

This phase is where the natural-selection claim is tested. A generated tool is not counted as contributing merely because it exists in the registry. It must be visible, selected, and called by the actor during task execution to enter the called-generated-tool attribution bucket.

Current v061 call evidence:

```text
generated_tool_called_scenarios = 825
called_generated_tool_bucket_outcome_lift = 82.703167903197%
```

Methodological role:

- tests whether generated tools are usable by the actor;
- tests whether reusable generated tools improve task completion in live task-solving;
- provides the behavioral evidence for H2 and H3.

Evidence recorded:

- task transcript;
- original tool calls;
- generated tool calls;
- generated tool failures;
- final task score;
- canonical/reference score;
- exact success status where available.

### 6.10 Reuse and Side-Effect Logs

Reuse logs record when accepted generated tools are called after registry admission. These logs are essential for distinguishing tool generation from tool reuse. Side-effect logs record whether generated tools that plan or prepare a state-changing action preserve the required original downstream tool calls.

The side-effect preservation rule is a validity control. Generated tools may plan, filter, select, canonicalize, calculate, or prepare arguments. They must not silently replace original side-effect tools when a task requires an actual state change.

Current v061 reuse and side-effect evidence:

```text
reuse_events = 1438
generated_tool_failed_scenarios = 3
side_effect_preservation_incidents = 1
runtime_exceptions = 0
```

The v061 side-effect preservation incident was:

```json
{
  "scenario": "find_temperature_low_battery_mode_3_distraction_tools_tool_name_scrambled",
  "generated_tools_called": ["plan_device_state_action_sequence_v3"],
  "side_effect_preservation_failures": ["plan_device_state_action_sequence_v3"]
}
```

Methodological role:

- measures actual generated-tool adoption;
- separates accepted tools from reused tools;
- protects against synthetic task completion by generated tool alone;
- documents failures and preservation incidents as caveats.

Evidence recorded:

- reuse event count;
- generated-tool call count;
- generated-tool failure count;
- side-effect preservation incident count;
- side-effect incident details.

### 6.11 Reflection and Registry Checkpoint

Reflection and checkpointing are the cumulative-learning controls. Reflection allows SAGE to update its understanding of which task shortfalls remain unresolved and whether existing tools are sufficient. Checkpointing preserves the registry state after accepted changes so that later analysis can distinguish online-build evidence from frozen-registry reuse evidence.

For v061, reflection was enabled and governed by pulse controls:

```text
SAGE_SELF_EVOLVING_REFLECTION=1
SAGE_SELF_EVOLVING_PULSE_INTERVAL=4
SAGE_SELF_EVOLVING_MIN_PULSE_TASKS=8
```

Methodological role:

- supports cumulative adaptation across a task sequence;
- records the registry state associated with the observed results;
- enables later frozen-registry reuse tests with generation disabled;
- preserves the distinction between online self-evolution and static reuse.

Evidence recorded:

- registry checkpoints;
- registry manifest digest;
- accepted tool inventory;
- post-run registry state.

## 7. Data Collection Instruments and Operational Variables

The main instruments in this study are the scoring functions, generated-tool records, registry manifest, selection logs, reuse logs, side-effect preservation logs, and paired comparison outputs. These instruments convert task behavior into measurable variables aligned to the hypotheses.

Primary dependent variable:

- final-task/outcome score, when outcome scoring is available.

Descriptive compatibility diagnostic:

- canonical/reference similarity score (not a hypothesis or release endpoint).

Primary treatment variables:

- generation enabled versus disabled;
- generated tool visible;
- generated tool called;
- generated tool failed;
- registry frozen versus online-build;
- accepted registry size;
- reuse count.

Task-level variables:

- scenario identifier for pairing and artifact lookup;
- control score;
- SAGE score;
- score delta;
- exact success status;
- generated-tool visibility;
- generated-tool call status;
- runtime exception status;
- side-effect preservation status.

Generated-tool-level variables:

- generated-tool family;
- accepted or rejected status;
- validation proof;
- code hash;
- birth context;
- visible count;
- called count;
- failed count;
- contribution deltas on called scenarios.

Cost variables:

- LLM call count;
- prompt tokens;
- completion tokens;
- total tokens;
- wall-clock runtime.

## 8. Data Analysis Plan

The analysis uses paired scenario-level comparison. Each SAGE task result is compared with the matched non-learning control result for the same task.

Mean delta is computed as:

```text
mean_delta = sage_mean - control_mean
```

Relative lift is computed as:

```text
relative_lift = (sage_mean - control_mean) / control_mean
```

Hypothesis-specific analysis:

| Hypothesis | Primary analysis |
|---|---|
| H1 | Frozen-registry outcome delta divided by online-build outcome delta |
| H2 | Overall SAGE outcome lift versus matched non-learning control |
| H3 | Outcome lift on the called-generated-tool attribution bucket |

Generated-tool contribution analysis assigns scenarios to attribution buckets:

| Bucket | Meaning | Claim status |
|---|---|---|
| `called_generated_tool` | A generated registry tool was naturally called | Appropriate for generated-tool-attributed claims |
| `generated_tool_visible_not_called` | At least one generated tool was visible but not called | Context only, not direct generated-tool attribution |
| `no_visible_generated_tool` | No generated tool was visible | Context only |
| `missing_selection_record` | Selection record unavailable | Excluded or separately qualified |

Only the called-generated-tool bucket should be used to claim direct generated-tool contribution. This is a conservative attribution rule: if a generated tool was not called, the chapter should not attribute that scenario's improvement to generated-tool execution.

Additional analysis reports:

- exact successes;
- gains, regressions, and preserved outcomes;
- runtime exceptions;
- generated-tool failures;
- side-effect preservation incidents;
- registry size;
- accepted tool births;
- token cost.

## 9. Validity, Reliability, Trustworthiness, and Research Integrity Controls

Internal validity controls:

- paired task comparison;
- same task order and manifest;
- same model family across agent, user, and generation roles;
- control cache limited to the control arm;
- SAGE candidate arm executed fresh;
- repository whole-response replay disabled; OpenAI-managed prompt-prefix
  computation was a separate, then-unmeasured mechanism;
- frozen clock;
- diagnostic force disabled.

Construct validity controls:

- generated tools must satisfy reusable-generated tool criteria;
- candidate gate rejects trivial, unsafe, overfit, or hidden-label-dependent generated tools;
- validation proof required before registry exposure;
- visible-context policy prevents hidden scenario-name use;
- called-generated-tool attribution required for direct generated tool claims.

Reliability controls:

- deterministic generated tool code;
- repeated validation-example execution;
- held-out semantic examples;
- negative applicability examples;
- schema and code-hash verification;
- registry manifest and digest preservation.

Ecological validity controls:

- generated tools are exposed as normal callable tools;
- actor must naturally choose whether to call them;
- generated tools must preserve original side-effect tools.

Trustworthiness controls:

- artifact preservation in `outputs/` and `artifacts/`;
- transparent registry inventory;
- side-effect incident reporting;
- generated-tool failure reporting;
- explicit limitation that v061 does not by itself establish frozen-registry retention.

Research-integrity and ethical controls:

- no human subjects are recruited or intervened upon in the benchmark runs;
- benchmark-answer leakage is treated as a validity threat and explicitly controlled;
- generated tools are not allowed to hide benchmark labels or answer keys;
- generated tools are not allowed to silently perform side effects outside the original task environment;
- failed generated-tool calls and side-effect incidents are reported rather than suppressed;
- token cost is reported as an observed resource cost and not omitted from the methodology.

## 10. Current v061 Results

### 10.1 Overall Paired Result

| Metric | Control | SAGE | Delta | Relative lift |
|---|---:|---:|---:|---:|
| Canonical/reference score | 0.7332144560228993 | 0.8011858188055907 | 0.06797136278269156 | 9.27% |
| Final-task/outcome score | 0.45425082649352005 | 0.7572667814756449 | 0.3030159549821248 | 66.71% |

Additional paired metrics:

| Metric | Value |
|---|---:|
| Paired scenarios | 1032 |
| Outcome-scored scenarios | 800 |
| Exact successes, control -> SAGE | 201 -> 406 |
| Exact success gain | +205 |
| Canonical gains / regressions / preserved | 455 / 166 / 411 |
| Outcome gains / regressions / preserved | 404 / 88 / 308 |
| Protocol gate passed | true |
| Route mismatch qualified | false |
| Runtime exceptions | 0 |

### 10.2 Generated-Tool Use

| Metric | Value |
|---|---:|
| Control LLM total tokens | 10465294 |
| Registry tool count | 22 |
| Visible generated-tool count | 21 |
| Called generated-tool count | 21 |
| Newly accepted tools during run | 2 |
| Reuse events | 1438 |
| Generated-tool attempted scenarios | 725 |
| Generated-tool called scenarios | 825 |
| Generated-tool failed scenarios | 3 |
| Side-effect preservation incidents | 1 |
| Candidate LLM call count | 11155 |
| Candidate repository whole-response replay call count | 0 |
| Candidate LLM total tokens | 17245671 |
| Candidate wall time seconds | 14153.863965 |
| Candidate wall-time resume offset seconds | 8782.538233 |
| Candidate turns | 15026 |
| Candidate exceptions | 0 |

The dashboard reports `generated_tool_attempted_scenarios=725` and `generated_tool_called_scenarios=825`. Both fields should be preserved as reported. Call accounting reconciles successful generated-tool result messages and reuse callbacks, while attempt accounting is a separate selection field.

The dashboard tool summary also reports per-generated tool contribution totals of 615 outcome gains and 83 outcome regressions. Those are tool-summary contribution totals, not the paired-run scenario-level outcome gain and regression counts reported in Section 10.1.

### 10.3 Generated tool Contribution Buckets

| Bucket | Scenarios | Control canonical | SAGE canonical | Canonical delta | Canonical lift | Control outcome | SAGE outcome | Outcome delta | Outcome lift |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Called generated tool | 825 | 0.7251913197605457 | 0.803058779898015 | 0.07786746013746937 | 10.737505816145287% | 0.423081651382416 | 0.7729835798928341 | 0.3499019285104181 | 82.703167903197% |
| Visible not called | 27 | 0.7681643562895275 | 0.8425590116487961 | 0.07439465535926856 | 9.684731496605474% | 0.3681810800736071 | 0.41208333333333336 | 0.043902253259726215 | 11.924092691278226% |
| No visible generated tool | 180 | 0.7647446788520252 | 0.7863954348721651 | 0.021650756020139997 | 2.831109077168136% | 0.6649560972874016 | 0.6659659092436669 | 0.001009811956265245 | 0.15186144775341354% |

Detailed called-generated-tool bucket counts:

| Called bucket metric | Value |
|---|---:|
| Canonical mean delta | 0.07786746013746937 |
| Outcome mean delta | 0.3499019285104181 |
| Canonical gains / regressions / preserved | 424 / 141 / 260 |
| Outcome gains / regressions / preserved | 386 / 68 / 238 |

Other bucket counts:

| Bucket | Canonical gains / regressions / preserved | Outcome gains / regressions / preserved |
|---|---:|---:|
| Visible not called | 3 / 1 / 23 | 1 / 1 / 2 |
| No visible generated tool | 28 / 24 / 128 | 17 / 19 / 68 |

Outcome gain, regression, and preserved counts are limited to scenarios with available outcome scoring. They therefore do not necessarily sum to the full bucket scenario count.

The called-generated-tool bucket is the correct bucket for H3 because it contains scenarios where generated tools were naturally selected and called by the actor.

### 10.4 Generated-Tool Failure Caveat

The three generated-tool failure events all involved `relative_day_time_to_timestamp` in reminder-removal scenarios:

```text
remove_reminder_with_recency_latest_alt_3_distraction_tools
remove_reminder_with_recency_latest_alt_3_distraction_tools_arg_description_scrambled
remove_reminder_with_recency_latest_alt_all_tools
```

In each of these scenarios, other generated tools were also called and the final score was 1.0 on both canonical and outcome measures. The failures are still counted because they are generated-tool failure events, but they did not cause final task failure in those three cases.

## 11. Leakage, Fairness, and Reproducibility Controls

The current clean methodology includes the following controls:

| Control | v061 status |
|---|---|
| Scenario-name birth disabled | enabled |
| Scenario-name routing disabled | enabled |
| Visible-context metadata policy | enabled |
| Praxis bridge policy | disabled |
| Synthetic bridge completions | absent from clean policy |
| Diagnostic force flags | disabled |
| Repository whole-response replay cache | disabled; provider prompt-prefix computation not separately measured |
| SAGE candidate arm cache | none |
| Control cache | control only |
| Frozen clock | enabled |
| Runtime bundle cap | 4 |
| Registry digest recorded | yes |
| Side-effect audit | enabled |
| Runtime exception count | 0 |

These controls support the claim that v061's primary improvement is produced by SAGE's generated-tool mechanism rather than hidden scenario labels, answer leakage, forced generated-tool calls, synthetic task completions, or cached SAGE outputs.

## 12. Hypothesis Status Under Current v061

| Hypothesis | Current v061 status | Reason |
|---|---|---|
| H1: frozen registry preserves at least 80% of online-build gains | Not yet decided by v061 online-build alone | Requires a matched frozen-registry run with generation disabled. Primary threshold from v061 is outcome delta >= 0.242413. |
| H2: online self-evolving SAGE improves task completion by at least 10% over non-learning control | Supported on primary outcome measure | Outcome lift is +66.71%. Canonical lift is +9.27%, so the hypothesis should remain outcome/task-completion based. |
| H3: generated-tool-called tasks improve by at least 30% without leakage or synthetic completions | Supported on primary called-subset outcome measure | Called-generated-tool bucket has +82.70% outcome lift across 825 scenarios under visible-context, bridge-disabled, no-force-call controls. |

Recommended wording:

> The current evidence supports the online self-evolution and natural generated-tool-use hypotheses on the primary final-task/outcome measure. Frozen-registry retention remains a required follow-up analysis because the current v061 run is an online-build run, not a generation-off frozen reuse run.

## 13. Limitations and Non-Claims

The v061 evidence should be reported with the following limitations:

- SAGE is not model-weight training. Its adaptive substrate is a persistent generated-tool registry.
- v061 is an online-build result. It does not by itself prove frozen-registry retention.
- The current token cost is high: 17,245,671 candidate LLM tokens. Token reduction is underway and should be addressed separately.
- The control arm uses an eligible score cache. This is acceptable for matched scoring, but cache provenance should be disclosed.
- One side-effect preservation incident occurred and should be reported.
- Three generated-tool failure events occurred, although each corresponding scenario still scored 1.0 in final results.
- Current evidence is tied to this task environment, model configuration, manifest, and registry policy.
- Generated tools are deterministic assistants for planning, filtering, ranking, canonicalizing, calculating, and safe abstention. They are not allowed to replace required original side-effect tools silently.
- Contribution claims should be limited to the called-generated-tool bucket unless a separate causal analysis justifies a broader claim.

## 14. Chapter 3 Suggested Structure

The praxis chapter can use the following structure:

1. Restate the purpose of the study and the SAGE claim boundary.
2. Restate the research questions and hypotheses in measurable form.
3. Define the research design as a paired quantitative systems experiment.
4. Define the task corpus, sample, unit of analysis, and sample-size rationale.
5. Define the treatment and comparison conditions.
6. Describe the SAGE treatment mechanism component by component.
7. Define the data sources, instruments, logs, and operational variables.
8. Explain the analysis plan for overall lift, frozen-registry retention, and called-tool attribution.
9. Explain validity, reliability, trustworthiness, leakage, and research-integrity controls.
10. Record the current v061 configuration and evidence boundary.
11. State current hypothesis status without overstating frozen-registry reuse.
12. State limitations, including token cost and pending token-reduction work.

## 15. Reproducibility Checklist

A reader or reviewer should be able to verify v061 from:

```text
outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410/protocol_manifest.json
outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410/paired_comparison.json
outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410/helper_contribution_summary.json
outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410/dashboard/task_compare_data.json
artifacts/chapter3_token_reduction/v061_finish_v059_registry/registry_manifest.json
```

Minimum verification checks:

```text
1. Confirm protocol mode is online_build_full.
2. Confirm SAGE policy is self-evolving-praxis.
3. Confirm generation is enabled for v061.
4. Confirm bridge policy is disabled.
5. Confirm scenario-name birth and routing are disabled.
6. Confirm visible-context metadata policy is enabled.
7. Confirm repository whole-response replay is disabled; do not infer from this
   historical record that OpenAI-managed prompt-prefix computation was absent.
8. Confirm control cache applies only to the control arm.
9. Confirm paired scenario count is 1032 and outcome-scenario count is 800.
10. Confirm canonical score is 0.7332144560228993 -> 0.8011858188055907.
11. Confirm outcome score is 0.45425082649352005 -> 0.7572667814756449.
12. Confirm called-generated-tool bucket has 825 scenarios.
13. Confirm called-generated-tool outcome lift is 82.70%.
14. Confirm runtime exception count is 0.
15. Confirm side-effect preservation incident count is 1.
16. Confirm candidate token count is 17,245,671.
17. Confirm registry contains 22 accepted tools.
18. Confirm newly accepted tools are plan_contact_relationship_batch_update and plan_send_message_contact_lookup.
19. Confirm frozen-registry retention is not claimed from v061 alone.
20. Confirm token reduction is marked as pending.
```

## 16. Revision Notes

The next revision should add the frozen-registry reuse result once it is available. That section should report:

- frozen run root;
- frozen registry digest;
- generation disabled confirmation;
- matched manifest and model confirmation;
- frozen outcome delta;
- frozen canonical delta;
- retention ratio versus v061 online-build delta;
- generated-tool call count under frozen reuse;
- any side-effect incidents or runtime failures;
- whether H1 passes the 80 percent threshold.

The token-reduction revision should report:

- before and after candidate token counts;
- whether outcome and called-bucket gains are preserved;
- whether reduced prompting changes generated-tool adoption;
- whether registry acceptance rate changes;
- whether runtime bundle size or docstring mode changes;
- whether any reduced-token policy weakens safety validation, side-effect preservation, or leakage controls.
