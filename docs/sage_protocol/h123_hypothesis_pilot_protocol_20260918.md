# H1/H2/H3 Core and H4 Split-Registry Pilot Protocol (2026-09-18)

## Decision status

This is one complete engineering replication of the H1--H3 core and one
exploratory randomized split-registry experiment (H4). H1--H3 use one
independently evolved registry; H4 starts a separate empty discovery registry
so its held-out transfer claim cannot borrow tools from the H1--H3 run. It is a
**pilot**, not confirmatory evidence across registry builds. The dashboard and
completion report must use `PILOT_THRESHOLD_CLEARED`,
`PILOT_THRESHOLD_NOT_CLEARED`, or `INTEGRITY_FAILURE`; they must not label any
hypothesis supported or rejected.

This protocol acknowledges and follows
`docs/sage_protocol/00_global_working_agreement.md`. The user's 2026-09-18
instruction to complete this run supplies human approval for the sequential
H2, H1, H3, and H4 phases; phases may not overlap, and each phase receives a
preserved completion record before the next begins. The endpoint rule below is
an explicit study-specific override of the agreement's older canonical-score
default: the custom v9 outcome scorer is the primary endpoint because these
hypotheses concern route-independent task outcome, while ToolSandbox canonical
similarity remains a required descriptive and integrity measure. This override
changes reporting priority only; it does not remove canonical scoring.

## Locked hypotheses

- **H1:** Blind functional validity of accepted tools.
- **H2:** Integrated SAGE improves mean outcome score over control.
- **H3:** Randomized availability of the frozen generated registry improves
  outcome over registry-masked SAGE.
- **H4 (exploratory alternate):** A frozen registry built only on a randomized,
  disjoint discovery half improves mean outcome score over registry-masked SAGE
  on the held-out second half.

The primary endpoint for H2, H3, and H4 is the route-independent SAGE v9
outcome score on `[0, 1]`. ToolSandbox canonical similarity is preserved and
reported for every arm as a descriptive, non-primary measure.

## Common execution controls

- Benchmark: the committed 1,032-scenario full-benchmark manifest.
- Model in every model-using condition: `gpt-4o-mini`.
- Actor: the same SAGE hybrid-policy wrapper in control, available, and masked
  conditions.
- Native-tool policy, benchmark order, fixed ToolSandbox clock, sanitized
  read-only external fixture, four-attempt transient-scenario retry policy, and
  evaluator version are held fixed. Retries remain in their randomized arm and
  are reported; only a final task exception fails integrity.
- Diagnostic force-call environment variables and repository response replay
  are prohibited.
- Every model row is fresh. No task-result cache or partial-row resume is used.
- The aggregate pilot dashboard is generated before H2 and refreshed whenever
  a phase input is sealed or result is recorded. The H2 Task Compare dashboard
  is also served, verified, and opened before H2's first model request, with its
  receipt retained. H3 and H4 do not claim a pre-opened Task Compare receipt.
- Before any model call, the central pilot manifest records the clean Git
  commit/tree,
  benchmark hash, locked randomization seed and algorithm, output paths, H1
  assessor-separation procedure, and phase state. The post-freeze registry and
  completed blind case-bank hashes are appended before either is evaluated.
  Every phase seal records the same pilot ID, central-manifest path, and Git
  identity; a phase cannot run or be ingested from another clean commit.
- All run commands execute from the repository root with `PYTHONPATH=src:.`
  and an isolated environment that exactly matches
  `requirements-publication-lock.txt` placed first on `PATH`.

## Online-feedback boundary

The H2 online candidate uses `actor-visible-only` adaptation. Tool birth may
consume actor-visible task context and sanitized actor-visible transcript
fields. ToolSandbox similarity, SAGE v9 outcomes, hidden target state, and the
matched control row are withheld from generation, repair, retention, and
routing. The matched control is still run concurrently for H2 analysis, but it
is not delivered to the candidate. Post-task evaluator-driven reflection and
repair are disabled. Admission validation remains active.

## H1: post-freeze blind functional validity

The online registry is frozen and content-hashed before H1 evaluation. Because
the active tool roster does not exist until that freeze, the spec-only case-bank
scaffold is exported after the online run. A separate-context assessor receives only
that scaffold (public specifications and content bindings, never generated code,
admission cases, transcripts, or execution results). The completed case bank is
hash-locked before any blind case is executed and is never passed to generation,
admission validation, repair, routing, or the H3 actor.

This is procedural blinding, not cryptographic isolation. A fail-closed assessor
receipt binds the pilot ID, frozen-registry identity, scaffold, completed bank,
assessor prompt, completion record, model/assessor identity, completion time,
and explicit spec-only/no-code/no-admission/no-result declarations. The receipt
supports an auditable separation procedure; it does not prove that filesystem
access was technically impossible.

Population and unit:

- Population: every non-retired current entry in the frozen registry.
- Unit: one current tool implementation/version.
- A tool passes only if every assigned blind case passes against its exact
  frozen code hash.
- Unknown or uncovered active tools remain in the denominator and fail closed;
  they are never silently excluded.
- Any blind case whose canonicalized input and expected output exactly matches
  an admission case is rejected as contaminated.
- Registry bytes are hashed before and after the audit and must be identical.

For pure transformation tools, the bank supplies at least two independently
withheld exact-output cases per tool. For native-action tools, it supplies both
positive call-oracle and negative/abstention cases. The present schema does not
claim a general metamorphic/property-testing layer. Static safety, schema
conversion, determinism, JSON-safe output, input non-mutation, and native-action
contract checks remain hard gates. The H1 estimate is the number of tools
passing every blind case divided by all active frozen tools.

H1 clears its pilot threshold only when all of the following hold:

1. at least 20 active tools are present;
2. case-bank coverage is 100%;
3. at least 90% of active tools pass every blind case;
4. no critical unauthorized or extra native-action event occurs; and
5. all integrity checks, overlap checks, and registry-immutability checks pass.

The exact two-sided 95% Clopper-Pearson lower bound is reported, but it is
descriptive and is not itself a pilot gate.

## H2: integrated SAGE versus matched control

The locked H2 launch is the full 1,032-task `native-only` run with gate purpose
`campaign-inclusion`, `SAGE_ONLINE_FEEDBACK_MODE=actor-visible-only`, and the
exact central pilot manifest supplied. Any other size, execution mode, gate
purpose, feedback mode, pilot-manifest path, or Git identity is rejected before
output creation or a model request.

All 1,032 tasks are analyzed by intention to treat. Let `B` be the mean v9
outcome for the fresh matched control and `S` the mean for online integrated
SAGE. Report `S-B` and relative lift `100(S-B)/B`.

Dependence is handled by stripping only the seven exact ToolSandbox robustness
suffixes, producing exactly 129 original-scenario stems with eight variants
each. The primary uncertainty interval is a 50,000-draw paired bootstrap over
the 129 stems, keeping all eight variants together. A 77 broader-semantic-family
cluster interval is a conservative sensitivity analysis only.

H2 clears its pilot threshold only if:

1. both arms contain all 1,032 unique rows in identical order;
2. all strict integrity gates pass with zero runtime exceptions;
3. relative lift is at least 10%; and
4. the lower endpoint of the 95% 129-stem bootstrap interval for `S-B` is above
   zero.

## H3: randomized frozen-registry availability

After H2 completes, the exact frozen registry is copied read-only for a new
1,032-task run. Generation, repair, evaluator feedback, and lifecycle mutation
are disabled. The actor wrapper and native-tool inventory remain identical.

Randomization unit and blocking:

1. Strip only the seven exact robustness suffixes to recover exactly 129
   original-scenario stems; all eight variants inherit their stem assignment.
2. Compute each stem's mean H2 control outcome. These are pre-treatment H3
   covariates.
3. Sort stems by that control mean and form 63 adjacent pairs plus one final
   triplet using the algorithm version recorded in the manifest.
4. With the locked seed, assign one stem per pair to registry available and one
   to registry masked. Assign two of the triplet's three stems to available.
   This yields 65 available stems (520 tasks) and 64 masked stems (512 tasks).
5. Write and hash the complete assignment before the first H3 model request.
   There is no rerandomization based on H3 outcomes.

Masked tasks return the unmodified policy-wrapped ToolSandbox scenario before
registry routing or injection. Their logs must show zero generated tools
visible, attempted, or called. Available tasks use the frozen registry's normal
router and hybrid-selection policy. Failed executions remain in the assigned
condition with outcome zero; no called-tool or other post-treatment subset is
the primary analysis.

The primary H3 estimand is the equally weighted 129-stem intention-to-treat
difference in mean v9 outcome, available minus masked. Report the raw condition
means, the estimate, a 95% stem-cluster bootstrap interval, and a one-sided
restricted-randomization p-value obtained by replaying the locked assignments
within the same 63 pair/one triplet design. The locked analysis uses 100,000
restricted-randomization draws at seed `20260919` and 20,000 stem-cluster
bootstrap draws at seed `20260920`.

H3 clears its narrow, one-registry pilot threshold only if:

1. all 1,032 rows are present exactly once and retain their assignment;
2. the assignment and frozen registry hashes match their pre-run records;
3. masked exposure/call counts are zero and the registry is byte-identical
   before and after execution;
4. the intention-to-treat estimate is positive;
5. the one-sided restricted-randomization `p < .05`; and
6. the 95% interval lower endpoint is above zero.

An effect of at least `+0.05` is separately reported as a practical-magnitude
flag; it is not substituted for the null test.

## H4: randomized discovery-half to frozen held-out-half transfer

H4 is an exploratory alternate hypothesis and uses a separate registry that
starts empty. Randomization occurs at the same 129 original-scenario-stem unit
used for H2 and H3, not at the individual perturbation row. This prevents any
of a stem's eight near-duplicate robustness variants from appearing in both
discovery and held-out evaluation.

Before any H4 model request, seed `20260919` is used with the recorded PCG64
algorithm to shuffle all 129 stems and to lock a complete ordered assignment.
The first 64 stems (512 task rows) form the discovery half; the remaining 65
stems (520 task rows) form the held-out half. The slight imbalance is required
by the odd number of indivisible stem clusters. Variant order within each half
is also fixed by this pre-execution randomization, and the complete order and
assignment are hashed before execution. There is no result-dependent reshuffle.

During discovery, integrated SAGE uses `actor-visible-only` adaptation and may
generate and admit tools, but receives no ToolSandbox score, v9 outcome, hidden
target state, or matched-control feedback. After the 512th task, the discovery
registry is content-hashed and frozen. Generation, repair, reflection, and
lifecycle mutation are disabled for held-out evaluation. The frozen discovery
registry identity is appended write-once to the central pilot manifest before
either held-out arm may make a model request.

The held-out comparison uses two fresh arms in the identical locked 520-task
order. Both use the same SAGE policy wrapper, native-tool inventory, model,
clock, retry policy, and byte-identical frozen-registry copies. One arm receives
normal frozen-registry availability; the other loads the same registry but
masks it before routing or injection on every assigned task. The masked arm
must expose, attempt, and call zero generated tools. The two arms are launched
as concurrent child processes, and PID/timestamp overlap evidence is retained;
non-overlap is an integrity failure.

If discovery produces zero active accepted tools, H4 ends as a feasibility and
integrity failure. No replacement tool, relaxed recurrence threshold, extra
discovery task, or post-result rerandomization is permitted within this pilot.

The H4 intention-to-treat estimand is the paired mean v9 outcome difference on
all 520 held-out tasks, frozen-registry available minus registry-masked SAGE.
Report both means, the absolute difference, relative lift, and a 50,000-draw
paired percentile bootstrap interval over the 65 held-out stems, keeping all
eight variants together. The bootstrap seed is `20260920`.

H4 clears its exploratory pilot threshold only if:

1. discovery and held-out stems are disjoint and together exhaust all 129
   stems with complete eight-variant rosters;
2. all 512 discovery rows and both 520-row held-out arms are present exactly
   once in their locked order with zero runtime exceptions;
3. both held-out registry copies match the frozen discovery hash before and
   after execution;
4. the masked arm has zero generated-tool exposure, attempts, or calls;
5. relative lift on the held-out half is at least 10%; and
6. the lower endpoint of the paired 65-stem 95% interval is above zero.

## Failure and reporting rules

Any missing row, duplicated scenario, assignment drift, discovery/held-out stem
overlap, case-bank overlap, uncovered active tool, registry mutation, masked
generated-tool exposure, source-identity mismatch, or failed strict run
verification produces `INTEGRITY_FAILURE`. A failed phase is logged and the
pilot stops; no silent retry or result-dependent rerandomization is allowed. A
later replacement run requires a new pilot identifier and an explicit
amendment.

The final aggregate dashboard must show H1--H4 raw denominators, primary point
estimates and intervals, descriptive canonical means, randomization provenance,
integrity checks, and machine-readable artifacts. It links the verified H2 Task
Compare dashboard. H3 and H4 link their raw run directories and result files;
they do not claim arm-level Task Compare dashboards that those direct runners do
not generate. The canonical ten-replication Chapter 4 dashboard is not
overwritten or reinterpreted.

Decision label before execution: `READY_FOR_H123_PILOT_PREPARATION`
