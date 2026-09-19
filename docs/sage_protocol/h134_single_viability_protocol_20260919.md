# H1/H2/H3 and H4 Single-Run Viability Protocol (2026-09-19)

## Scope and status

Execution ID: `h134_single_viability_20260919_01`.

This is one engineering viability run, not confirmatory evidence. It replaces
the stopped ten-replication campaign `h134_paper_h2_10x_20260919_01`, whose
partial artifacts remain preserved and are ineligible for reuse. The sequence
is H2, H1, H3, then exploratory H4. A phase integrity failure stops the
sequence, and no failed or partial phase is retried under this ID.

## Hypotheses under viability assessment

- **H1:** Blind functional validity of accepted tools.
- **H2:** Ten independently evolved SAGE registries outperform control.
- **H3:** Randomized availability of the frozen generated registry improves
  outcome over registry-masked SAGE.
- **H4 (exploratory backup):** A frozen registry built only on a randomized,
  disjoint discovery half improves outcome over registry-masked SAGE on the
  held-out half.

Because only one registry is evolved here, H2 can clear a single-run viability
threshold but cannot support the paper's ten-registry claim. A later
confirmatory campaign is warranted only if the mechanisms are viable.

The primary task endpoint is the route-independent SAGE v9 outcome score.
ToolSandbox canonical similarity remains descriptive.

## Shared controls

- `gpt-4o-mini` is used for actor, user simulator, and generator.
- The committed ordered 1,032-task benchmark, native-tool policy, hybrid SAGE
  policy, frozen clock, validated read-only external fixture, retry policy, and
  evaluator are fixed.
- Diagnostic force-call overrides, response replay, task-result caching, and
  partial-row resume are prohibited.
- Inputs, assignments, registries, source commit/tree, and outputs are hashed.
- Phases do not overlap. Partial artifacts are preserved but never analyzed as
  completed observations.

## H2: one paper-behavior replication

One empty registry is evolved over all 1,032 tasks alongside a concurrent,
fresh, uncached matched control. SAGE uses the paper's normal operating mode:

- `SAGE_ONLINE_FEEDBACK_MODE=audited`;
- strict reflection expectation `same-run-fresh`;
- post-task candidate and control outcomes may affect later lifecycle repair,
  retention, and routing;
- the actor never receives a hidden target or score for its current task.

The viability analysis uses all 1,032 paired tasks, reports mean outcome,
absolute and relative lift, and a paired bootstrap over the 129 original-task
stems. The H2 viability threshold clears only with complete strict integrity,
at least 10-percent relative lift, and a 95-percent stem-cluster interval for
the absolute difference whose lower endpoint exceeds zero.

## H1: blind functional validity

The completed H2 registry is frozen and content-hashed. A separate-context
assessor receives only the public tool-spec scaffold and content bindings—not
generated code, admission cases, transcripts, or execution results. Its case
bank is hash-locked before execution.

Every active, non-retired tool is included. A tool passes only if every blind
case passes its exact frozen implementation. Unknown, uncovered, contaminated,
or mutated tools fail closed. H1 clears its viability threshold with at least
20 active tools, 100-percent case coverage, at least a 90-percent tool pass
rate, registry immutability, and no critical unauthorized native action.

## H3: randomized frozen-registry availability

The H2 registry is copied and frozen for one fresh 1,032-task run. Generation,
repair, evaluator feedback, and lifecycle mutation are disabled. All eight
variants of each original-task stem share an assignment.

Using the locked H2 control outcomes as pretreatment covariates, seed
`20260918` forms 63 adjacent pairs plus one triplet and assigns 65 stems to
registry available and 64 to registry masked. The complete assignment and
registry hash are sealed before the first H3 model request. Masked tasks retain
the same actor wrapper and native tools but expose, attempt, and call zero
generated tools.

The primary estimand is the 129-stem intention-to-treat difference, available
minus masked. H3 clears its viability threshold only with a positive estimate,
a one-sided restricted-randomization p-value below .05, a stem-cluster
95-percent interval lower endpoint above zero, zero masked exposure, and an
unchanged registry.

## H4: separate split-registry transfer test

H4 starts from a separate empty registry and does not consume the H2 registry.
Seed `20260919` with PCG64 locks 64 discovery stems (512 tasks) and 65 held-out
stems (520 tasks), with no stem split across halves.

Discovery uses score-free `actor-visible-only` adaptation. After discovery,
the registry is frozen. Two fresh concurrent held-out arms compare registry
available with registry masked; generation, repair, feedback, and mutation are
disabled. H4 clears its exploratory viability threshold only with complete
disjoint rosters, zero final exceptions, immutable copies, zero masked
exposure, at least 10-percent relative lift, and a paired 65-stem bootstrap
interval lower endpoint above zero.

Decision label before execution: `READY_FOR_SINGLE_RUN_VIABILITY_TEST`
