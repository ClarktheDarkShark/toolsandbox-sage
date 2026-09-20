# Standalone H4 Parallel Viability Replacement (2026-09-20)

Execution ID: `h4_parallel_single_viability_20260920_03`.

This is the one permitted prospective replacement for the prematurely
terminated `h4_parallel_single_viability_20260919_02`. The earlier run and all
of its partial artifacts remain terminal, preserved, and ineligible. Nothing
is resumed or copied from it.

This standalone pilot executes only exploratory H4. It uses a separate clean
worktree, manifest, empty registry, output root, and artifact root, and may run
in parallel with H1/H3 because it consumes none of the paper H2 registry,
control outcomes, or core-pilot state. The researcher explicitly authorized
this independent overlap. It remains a single engineering viability run, not
confirmatory evidence.

The scientific design is unchanged from the prospective H4 specification in
`h134_from_paper_h2_single_viability_protocol_20260920.md`:

- `gpt-4o-mini` actor, user simulator, and generator;
- pinned 1,032-task publication benchmark;
- PCG64 stem split seed `20260919`;
- 64 discovery stems / 512 tasks and 65 held-out stems / 520 tasks;
- score-free `actor-visible-only` discovery from an empty registry;
- frozen, content-bound registry after discovery;
- concurrent held-out registry-available and registry-masked arms;
- generation, repair, reflection, evaluator feedback, and mutation disabled in
  both held-out arms;
- zero masked generated-tool exposure, attempts, and calls;
- complete rosters, zero final exceptions, and byte-identical immutable
  registry copies;
- paired 65-stem bootstrap, 50,000 draws, seed `20260920`;
- viability threshold: relative lift at least 10% and 95% interval lower bound
  above zero.

Durable launch and stateful completion monitoring follow the monitoring rules
in the parent September 20 protocol. No retry, repair, partial-row resume, or
reuse of this ID is allowed after any integrity failure.

Decision label before execution: `READY_FOR_STANDALONE_H4_REPLACEMENT_03`.
