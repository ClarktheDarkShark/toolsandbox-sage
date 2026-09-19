# H1/H3/H4 Evaluation With Paper-Exact H2 (2026-09-19)

## Decision status

This protocol replaces the failed `h123_pilot_20260918_01` execution. That
pilot remains preserved and is not resumed or repaired. The new execution ID
is `h134_paper_h2_10x_20260919_01`.

The protocol follows `docs/sage_protocol/00_global_working_agreement.md` and
the researcher's 2026-09-19 direction to restore H2 to the paper design and
test the new H1, H3, and exploratory H4. Phases execute in the order H2, H1,
H3, H4. A failed integrity gate stops the sequence; no failed or partial phase
is silently retried under this ID.

## Locked hypotheses

- **H1:** Blind functional validity of accepted tools.
- **H2:** Ten independently evolved SAGE registries outperform control.
- **H3:** Randomized availability of the frozen generated registry improves
  outcome over registry-masked SAGE.
- **H4 (exploratory backup):** A frozen registry built only on a randomized,
  disjoint discovery half improves outcome over registry-masked SAGE on the
  held-out half.

The primary task endpoint is the route-independent SAGE v9 outcome score.
ToolSandbox canonical similarity is retained as a descriptive measure.

## Common controls

- Model: `gpt-4o-mini` for actor, user simulator, and generator.
- Benchmark: the committed ordered 1,032-task full benchmark, grouped into 129
  original-scenario stems with eight robustness variants per stem.
- Native-tool policy, hybrid SAGE policy, fixed ToolSandbox clock, sanitized
  read-only external fixture, retry policy, and evaluator version are fixed.
- Diagnostic force-call overrides, task-result caches, partial-row resume, and
  repository response replay are prohibited.
- Every phase records a clean Git commit/tree and hashes all inputs before its
  first model request. Later implementation commits may add the already locked
  H1/H3/H4 orchestration, but may not change the hypotheses, assignments,
  endpoints, thresholds, or analyses below in response to observed results.

## H2: restored paper execution

H2 uses the existing Chapter 4 online-only campaign path, not the one-registry
hypothesis-pilot launcher. Ten replications start from ten independent empty
registries. Each replication concurrently executes a fresh matched control and
an integrated online SAGE arm over all 1,032 tasks.

SAGE operates exactly at the paper's feedback boundary:

- `SAGE_ONLINE_FEEDBACK_MODE=audited`;
- strict verification expectation `same-run-fresh`;
- post-task v9 candidate and matched-control outcomes may inform subsequent
  lifecycle repair, retention, and routing;
- no hidden target or score is available to the actor during the current task.

The primary dataset contains 10,320 matched task pairs. The paper's 10-percent
target contrast is retained. H2 clears only if the observed relative lift is at
least 10 percent, both the two-way run/task and run-cluster 95-percent interval
lower bounds for `SAGE - 1.10 * control` exceed zero, and the exact two-sided
run-level sign-flip p-value is below .05. All ten runs must pass strict
integrity verification. The campaign dashboard's legacy H1/H3 panels are not
evidence for the new H1 or H3.

## H1: blind validity across the ten frozen registries

After H2, all active, non-retired current tool instances in all ten final
registries form the H1 population. Each registry is frozen and hashed. For each
replication, a separate-context assessor receives only the public spec scaffold
and content bindings—not generated code, admission cases, transcripts, or
execution results—and produces a case bank that is hashed before execution.

A tool instance passes only if every assigned blind case passes against its
exact frozen code hash. Unknown, uncovered, or contaminated instances fail
closed. Coverage must be 100 percent, registry bytes must remain unchanged,
and no critical unauthorized native action may occur. The pooled tool-instance
pass rate is primary; per-registry rates and a registry-cluster interval are
reported as sensitivity evidence. H1 clears at a pooled pass rate of at least
90 percent with at least 20 active tool instances in total.

## H3: randomized availability across the ten frozen registries

Each H2 registry receives one fresh 1,032-task randomized-availability run.
Generation, repair, evaluator feedback, and lifecycle mutation are disabled.
Within each replication, all eight variants of a stem share one assignment.
Stems are blocked using that replication's prospectively available H2-control
stem mean, then assigned 65 stems available and 64 stems masked. Replication
`r` uses assignment seed `2026091900 + r`; assignments and registry hashes are
sealed before model execution.

Masked tasks retain the same policy-wrapped actor and native tools but expose,
attempt, and call zero generated tools. Available tasks use the frozen
registry's normal router and hybrid selector. The primary estimand is the
equally weighted mean of the ten run-level, stem-weighted intention-to-treat
effects. Analysis reports a two-way registry/stem bootstrap interval, an exact
one-sided sign-flip test over the ten run effects, and within-run restricted
randomization checks. H3 clears only when the aggregate effect is positive,
the 95-percent two-way interval lower bound exceeds zero, the one-sided exact
sign-flip p-value is below .05, and all exposure and immutability gates pass.

## H4: separate split-registry transfer experiment

H4 starts from a separate empty registry and consumes none of the H2
registries. Seed `20260919` with PCG64 locks a stem-level shuffle before any
model request. The first 64 stems (512 tasks) are discovery and the remaining
65 stems (520 tasks) are held out.

Discovery uses `actor-visible-only` adaptation and may generate and admit
tools. It receives no ToolSandbox score, v9 outcome, hidden target state, or
matched-control feedback. The registry is then hashed and frozen. Two fresh,
concurrent held-out arms use identical frozen copies: registry available versus
registry masked. Generation, repair, reflection, and mutation are disabled;
the masked arm must expose, attempt, and call zero generated tools.

The H4 intention-to-treat estimate is the paired mean v9 difference over all
520 held-out tasks. H4 clears its exploratory threshold only with complete and
disjoint stem rosters, zero final task exceptions, immutable registries, zero
masked exposure, relative lift of at least 10 percent, and a paired 65-stem
bootstrap 95-percent interval lower bound above zero.

Decision label before execution: `READY_FOR_H2_LIVE_CAMPAIGN`
