# SAGE refactor replay gate

This directory contains validation-only tooling. It is not imported by the
SAGE application and is excluded from the installed package.

The gate runs the reference and candidate checkouts in separate `python -I`
subprocesses, records deterministic JSON snapshots, and compares every field.
A difference fails the command unless its exact JSON-pointer path is covered by
a reviewed rule in `approved_nondeterminism.json`. The command line cannot add
or suppress normalization rules.

## Current probes

- `imports`: imports representative application entry points and verifies that
  each module resolves inside the selected checkout.
- `config`: snapshots model configuration, resolution, paired metadata,
  temperature behavior, and default/explicit reasoning-effort behavior.
- `evaluator_manifest`: snapshots the outcome evaluator version and contract
  and source hashes. A source-only evaluator edit therefore remains visible.
- `splits`: snapshots every committed split, manifest hash, and resolved
  ToolSandbox scenario record, including category and allowed-tool order.
- `outcomes`: rebuilds deterministic ToolSandbox rollout contexts and snapshots
  complete evaluator output for targeted insufficient-information, scalar,
  dynamic-time, frozen-distance, weather, recency, contradiction, correction,
  and post-answer-tail cases.
- `trajectory`: rehydrates eight complete, content-hashed trajectories from the
  frozen Chapter 4 paper cohort under its fixed clock. The stratified corpus
  covers generated and native execution, state changes, insufficient
  information, external fixture output, birth/repair/reuse evidence, and four
  post-700 tasks. It reruns each checkout's current visible-context parser and
  outcome evaluator over the captured tool arguments, results, conversation,
  and state history, and fails if the historical outcome no longer reproduces.
- `classifier`: resolves committed benchmark scenarios, then snapshots the
  immutable visible task facts, signal order, family key, generation label, and
  complete tool-birth observations (including validation examples). It gates
  the canonical raw and classified hashes for all 1,032 ordered tasks and also
  exercises independent database/tool-discovery failures, role filtering,
  last-nonempty-request selection, string conversion, sorted tool names, and
  one visible execution-trace precondition failure.
- `classifier_corpus`: freezes the complete ordered classifier boundary for all
  1,032 tasks and 1,874 emitted observations. It records per-task signal order,
  primary family, emission order, route/reason, exact observation hashes, and
  separate prompt, validation-example, and semantic factory-product hashes so
  a difference can be localized without embedding every repeated prompt in
  each case. The corpus also freezes all 21 dictionary expected-result key
  sequences (plus the two scalar expected types), eight intentional duplicate
  emission cases, benchmark and synthetic primary-family collisions, terminal
  insufficient-information versus nonterminal safe-abstention behavior, fresh
  factory materialization and mutation isolation, empty/malformed/temporal/
  precondition trace behavior, and the generic external-service fallback.
  Recursive type tags distinguish tuple/list, bool/int/float, dataclass, set,
  and insertion-ordered dictionary values; hashes are therefore not based on
  lossy sorted JSON.
- `actor`: feeds fixed model-boundary messages and routed schemas through the
  policy composer and every named-choice selector in production precedence
  order. It snapshots exact prompt text, original schema order, selected named
  `tool_choice`, filtered schema content, and final schema order.
- `actor_model_inference`: invokes the real
  `ConfigurableOpenAIAgent.model_inference` method for 43 fixture-first cases
  while a fake `chat.completions.create` records the exact API kwargs. The
  corpus has positive branch receipts for all 46 directly composed policy
  builders and all three nested device-state builders. It preserves exact
  prompt/schema/message order, the eagerly evaluated first four selectors,
  named-choice precedence, `NOT_GIVEN`, named-call usage recording, transient
  named retry followed by natural fallback, post-response safe-abstention
  grounding, response object identity, sentinel re-entry behavior, and focused
  near misses. Thirteen cases are explicitly labeled adaptations of the 72
  historical actor tests; the others are deterministic reference
  characterizations. None is claimed to be an archived evidence-run request.
- `normalization`: snapshots contract repair for state sequencing, ambiguous
  record selection, service-answer extraction, and safe abstention.
- `validation`: snapshots accepted and rejected generated tools across AST
  safety, compilation, runtime smoke, source, held-out, and negative examples.
- `routing`: feeds current-proof generated-tool contracts through a matrix of
  reminder, device, recency, insufficient-information, location, external
  service, and lifecycle states. It snapshots every visibility decision and
  the selected schema order.
- `runtime_contracts`: provides the fail-closed seam for the router and output
  normalization refactor. It characterizes 42 normalization cases across every
  generated-tool family and pass-through, 41 routing cases covering every
  reachable decision reason and precedence layer, and the ToolSandbox runtime
  wrapper's visible-trace traversal, malformed-trace behavior, input-enrichment
  order, abstention/error handling, trace emission, reuse callbacks, and native
  trace preservation. Unlike the ordinary semantic snapshot, this probe also
  records recursive dictionary insertion order, exact compact JSON bytes, and
  SHA-256 hashes. Its vectors incorporate the relevant historical
  normalization and generated-tool-injection oracle cases without adding tests
  to the production package.
- `trace_router_edges`: freezes the order-sensitive refactor boundary that the
  broader runtime matrix can obscure. It records forward/reverse row and
  within-row trace traversal, malformed and scalar JSON behavior, dict/list/
  scalar results, latest-invalid-result handling, timestamp tolerance, and
  setting overwrite order. Trace acquisition is also frozen: each reader's
  exact database keywords, changing-snapshot behavior, datetime enrichment's
  two independent reads, empty-name fast paths, `to_dicts` failure propagation,
  and lazy newest-match short circuit. It also captures exact router score/name
  ordering, the four-tool cap, lifecycle harm/repair thresholds, downstream
  all/any/native-alternative/producer-only rules, composite collisions,
  device-state action order and recovery, every reminder time/location branch,
  and native output identity before null cleanup. Focused collision vectors
  freeze `tools=` false-positive stripping, the no-`signals=` exception, first
  versus repeated and reversed marker behavior, family-only metadata
  augmentation, `None` versus empty context, raw `tools=message_recency`
  post-route activation, overlapping message-content/counterparty rules,
  negative and lifecycle precedence, no-tool guardrails, native-alternative
  versus generic any-of routing, exact evidence retention or loss under each
  suppression shape, and registry-key/spec-name identity mismatches. The R2
  vectors additionally pin lifecycle family/count coercion, downstream-schema
  precedence and producer narrowing, `None` versus empty base inventories,
  default/oversize bundle clamping, composite-before-cap behavior, registry
  alias tie ordering, and the public router signature/import identity.
  Normalization boundaries include same- and cross-service state requests, zero
  versus smallest-positive coordinates and timestamps, 23:59, hour 24, and
  minute 60. They also pin non-mapping identity returns, exact composite-schema
  dispatch, mixed-case ambiguity handling, selected-record fallback with zero
  or one inferred match, false/malformed/zero-longitude coordinate handling,
  datetime key-presence quirks, numeric-string timestamp type preservation, and
  shallow-only null cleanup with survivor order. Recursive key order and exact
  compact bytes are part of every result, including fields appended during
  selection normalization.
- `generation_boundary`: records every exact `ChatRequest` byte stream and hash
  for ordinary generation, native-action generation, cached contract analysis,
  repair analysis, repeated repair, and strategy-specific repair. It also
  freezes candidate parsing, invalid-candidate rejection, normalization, and
  first-accepted candidate selection.
- `validation_distance`: compares the generator and online-birth copies of
  structural, execution, native-action, nested value, and `NOT_GIVEN` error
  weights, including aggregate empty/error results and repair-case frontiers.
- `native_structural_cases`: freezes generator projection and validator
  augmentation for explicit and inferred timestamp keys, malformed records,
  rank ties, aliases, boolean numeric values, duplicate negatives, and the
  first-eligible-contract rule.
- `schema_ast_matrix`: snapshots denied/safe AST constructs, exact sorted error
  order, generated-function compilation, optional annotations, schema mismatch,
  function-count/name precedence, and defensive unreachable errors.
- `validator_matrix`: snapshots source/held-out/negative partitioning, gate →
  AST → schema → execution precedence, deterministic replay, semantic errors,
  and accepted/rejected native-action delegation contracts.
- `online_birth_repair`: drives the live seven-attempt repair controller with
  deterministic fake generators. It freezes batch selection, stable ties,
  cumulative versus native-current errors, strict best-score improvement,
  complementary native case-frontier advancement, seed rollback, event order,
  successful acceptance, and missing-repair behavior.
- `generator_profile_corpus`: executes every one of the 34 named generator
  profiles plus the generic `apply_single_device_state_action`, unknown-name,
  and `None` paths through the live `ToolGenerator`. It freezes exact
  `ChatRequest` field order and prompt hashes, mapping order/types, legacy
  canonical-key mappings, every native-action eligibility boundary, repair
  strategies 1–7, contract/repair-analysis cache order, generated spec/code
  normalization, parsing/coercion failures, and candidate selection. A live-path
  reachability test patches `ToolGenerationRequest.prompt` to raise and proves
  generation, repair, and online birth still succeed, documenting that the
  legacy prompt is not used by evidence runs.
- `validator_error_corpus`: reaches every sandbox-validator return/error branch,
  preserves exact error order, and covers source/held-out/negative precedence,
  gate → AST → schema → execution order, runtime-smoke failures, benign negative
  wording, structured abstention, and every native-action validation failure.
  The fixture declares all required error kinds explicitly so omissions fail
  closed.
- `lifecycle`: replays one ordered same-run control/candidate feedback stream
  and snapshots feedback records, immediate actions, pulses, registry hash,
  reuse/success-flip counters, retirement state, and final retain, repair, park,
  safety-audit, and adoption-repair decisions.
- `reporting`: materializes one content-hashed, five-scenario paired artifact
  set and snapshots exact `summarize_run`, `compare_runs`, helper-contribution,
  helper-writer, and protocol JSON-writer outputs. It records every nested
  object key order plus compact JSON bytes/hashes, and preserves the actual
  indented writer text and terminal newline. Separate cases freeze partial,
  reordered, missing, duplicate, non-object, and invalidly typed result rows;
  strict versus tolerant JSON/JSONL readers; final-summary precedence; live
  fallback; uncached-run rejection reasons; and strict-fresh report checks.
- `runner_provenance`: executes the real ToolSandbox sequence and SAGE runner
  boundaries over two tiny synthetic tasks with model/network calls replaced by
  deterministic fakes. It freezes run-manifest key order, compact semantic
  bytes, writer bytes and terminal newline; manifest-order execution and
  scenario index environment values; initial/per-task/final progress callbacks;
  transform-failure fallback; result-hook timing; usage snapshot-before-clear;
  transient retry archives, terminal failure rows, and role teardown. Separate
  frozen and online fixtures preserve registry checkpoint and event order. The
  adversarial cases freeze the exact `result_hook(...) or result` behavior for
  `None`, an empty mapping, in-place mutation, and fresh mappings with omitted
  or spoofed evaluator identity; evaluator identity reassertion; callback object
  aliasing; row/list mutation timing; and propagated result/progress exceptions.
  Sparse registry cases cover no files, one file, unset/invalid order indices,
  copy failure, metadata-write failure, and checkpoint-event JSONL failure.
  A nonempty selection case preserves visible, attempted, failed, called, and
  not-called generated-tool sets and their summary counts. Environment cases
  distinguish equal and descendant repository paths from sibling and
  shared-prefix paths for editable metadata and import provenance. The
  probe also records exact campaign-status, task-plan, event-ledger, run-index,
  and registry-snapshot bytes; publication-environment pass output, distribution
  digest/order, isolated import provenance, and fail-closed error text. Finally,
  it pins the publication Python launcher to
  `b40856762456913a70e60270f443b91c6c32c56d6ecd7975b8c196edc968b64c`
  and the shell entrypoint to
  `78811efa9f6c682c671c4664a4cf6249937591c94d4e6449df6b9ebd201f1183`.

The runner probe intentionally does not simulate process termination during an
operating-system write or copy, filesystem durability, concurrent writers, or
provider/network failures. Those are infrastructure and fault-injection tests,
not deterministic semantic-equivalence boundaries. A result hook has only a
per-task call site in the selected implementation, so initial/final result-hook
exceptions are structurally unreachable; the progress hook is exercised at all
three stages.

The behavior vectors are validation-only characterization fixtures. Outcome and
classifier cases are drawn from the committed benchmark and the historical
characterization tests at the validated test-oracle checkpoint. Actor vectors
use the same message/schema shapes as those oracle tests, and the expanded
model-inference corpus labels every case's provenance in source. Routing and
lifecycle vectors are deliberately minimal typed contracts and ordered
feedback events, so they exercise policy without copying a mutable registry or
invoking an LLM. No probe calls the network, current clock, model service, or an
unseeded random source.

The R2 router fixtures intentionally preserve several non-obvious current
behaviors rather than endorsing them. Lifecycle matching uses
`task_family_key`, not the positional `scenario_name`, and skips all lifecycle
state (including `park`/`parked`) when that family key is absent. Duplicate
harm/help rows count repeatedly; a malformed harmful-call count falls back to
the harmful-scenario list length. For the abstention helper, malformed
failure/incident counts become zero while negative counts are considered
non-clean; the visible-signal override instead rejects malformed counts but
allows negative ones because it blocks only values greater than zero. In
downstream routing, a `tool_name` enum is evaluated before—and can be replaced
by—`downstream_tool_name`; search helpers narrow the union of required and
preserved tools to read producers; and `available_base_tools=None` disables
the availability check whereas an empty set enforces it. Finally, the public
default bundle size remains five but the runtime clamps both that default and
larger explicit values to four, after composite suppression and before budget
decisions. These quirks are exact compatibility boundaries for the refactor.

The actor corpus is stored as readable Python data in `actor_fixture.py`; its
line count, byte count, and SHA-256 are frozen in
`actor_fixture.manifest.json`. Run the fixture-integrity and semantic tamper
tests with:

```bash
python -m unittest validation.replay.test_actor_contracts -v
```

The classifier corpus is materialized from the frozen benchmark rather than
shipped as a multi-megabyte duplicate fixture. Its independent reference
digests and structural assertions live in `classifier_contracts.py`. Verify
the full corpus and both unhashed and rehashed tamper rejection with:

```bash
python validation/replay/classifier_contracts.py --tamper-self-test
```

The generator/validator corpus is readable Python rather than a generated data
blob. Verify its explicit profile inventory, order, duplicate detection, and
validator-branch tamper rejection with:

```bash
python -m unittest validation.replay.test_generator_validator_corpus -v
```

Verify the trace acquisition, routing-collision, and normalization-boundary
contracts plus deliberate tamper detection with:

```bash
python -m unittest validation.replay.test_trace_router_contracts -v
```

Verify runner callback/checkpoint/provenance invariants and deliberate tamper
detection with:

```bash
python -m unittest validation.replay.test_runner_provenance -v
```

Reporting inputs live in `fixtures/reporting_v1.json` and
`fixtures/reporting_v1.manifest.json`. They are synthetic and deliberately
small: the portable historical trajectory corpus does not contain the complete
paired summary, selection, visibility, birth, reuse, side-effect, and registry
ledger set required to characterize reporting behavior without copying mutable
run directories. The fixture includes the same artifact shapes and metric type
edges, but makes no empirical claim. Verify its byte hash, canonical payload
hash, coverage, and tamper rejection with:

```bash
python validation/replay/reporting_fixture.py --tamper-self-test
```

The trajectory corpus and manifest live in `fixtures/full_trajectory_v1.json`
and `fixtures/full_trajectory_v1.manifest.json`. Provider call IDs are replaced
with stable fixture-local IDs. Hidden user-simulator/system prompts, absolute
paths, credentials, interactive consoles, and mutable registries are excluded.
Every source file, case, and fixture byte stream is hashed. Verify the portable
fixture alone with:

```bash
python validation/replay/trajectory_fixture.py
```

When the original paper artifacts are mounted, verify the entire provenance
chain as well:

```bash
python validation/replay/trajectory_fixture.py \
  --source-root /absolute/path/to/the/original/paper/worktree
```

Run the full initial gate with the Python interpreter from the frozen
publication environment:

```bash
python validation/replay/compare.py \
  --reference-root /absolute/path/to/reference \
  --candidate-root /absolute/path/to/candidate \
  --python /absolute/path/to/publication/python \
  --output /tmp/sage-replay-report.json
```

Exit status is `0` for equivalence, `1` for semantic differences, and `2` when
a probe or the harness fails. Probe failures never count as equivalence.

## Known historical boundary gap

The frozen run recorded routed tool names, tool calls/results, state changes,
and lifecycle decisions, but did not persist the exact per-request OpenAI tool
schema payload and actor prompt sent to the model. That boundary cannot be
truthfully reconstructed from the artifacts. Exact prompt, schema, order,
filtering, and named-choice behavior is therefore gated by the deterministic
`actor` and real-path `actor_model_inference` probes above. A future evidence
run should archive those payloads if a historical byte-for-byte model-boundary
replay is required.

If a source artifact contains a timestamp, PID, temporary path, or duration
that has no behavioral meaning, add the narrowest possible allowlist rule with
a written reason. Do not normalize prompt text, tool names, schema order, task
order, registry state, decisions, outcomes, or evaluator identities.

The reporting probe intentionally characterizes existing behavior rather than
declaring every behavior desirable. In particular, it preserves reordered-row
strict failures, duplicate-row quirks in `compare_runs`, lossy filtering of
non-object protocol rows, and the current differences between strict and
tolerant readers. It does not exercise concurrent writers, filesystem failures,
permission errors, interrupted atomic replacement, resume-checkpoint mtimes, or
the full dashboard HTML rendering path; those remain separate integration
concerns.

The runner fixture does not start multiprocessing workers, open a browser, call
an LLM, or reproduce signal/kill timing. It characterizes each worker's shared
sequence and hook boundary in-process; operating-system scheduling and provider
transport failures are not deterministic replay inputs. The full protocol
manifest remains covered by its frozen launcher source hash plus reporting and
campaign contracts rather than by executing the 1,032-task CLI in this offline
probe.
