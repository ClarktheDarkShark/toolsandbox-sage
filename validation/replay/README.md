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
- `actor`: feeds fixed model-boundary messages and routed schemas through the
  policy composer and every named-choice selector in production precedence
  order. It snapshots exact prompt text, original schema order, selected named
  `tool_choice`, filtered schema content, and final schema order.
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

The behavior vectors are validation-only characterization fixtures. Outcome and
classifier cases are drawn from the committed benchmark and the historical
characterization tests at the validated test-oracle checkpoint. Actor vectors
use the same message/schema shapes as those oracle tests. Routing and lifecycle
vectors are deliberately minimal typed contracts and ordered feedback events,
so they exercise policy without copying a mutable registry or invoking an LLM.
No probe calls the network, current clock, model service, or an unseeded random
source.

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
`actor` probe above. A future evidence run should archive those payloads if a
historical byte-for-byte model-boundary replay is required.

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
