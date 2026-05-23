# CyberGym Public Execution-Search Gap-Closure Report - 2026-05-23

This is experimental standalone SAGE evidence. It is not protected final-claim evidence.

## Objective

CyberGym exposed a limitation in the portable SAGE architecture: SAGE could detect that candidate strings were not good enough, and it could route/generated helpers naturally, but many generated helpers still produced weak static candidates. The goal of this phase was to identify what a truly useful CyberGym helper needs to do, prove that tool class on real tasks without label leakage, and then back-port the finding into a general SAGE framework improvement rather than a CyberGym-only shortcut.

## What Was Missing

The prior fixed-side first-window reference was:

- Run: `outputs/cybergym_live_sage/next_phase_route_only_validate20_20260522`
- Baseline: `1/20`
- SAGE: `5/20`
- Integrity issues: `0`

The diagnosis was correct but incomplete: helper visibility, gap detection, and natural routing were working. The missing capability was a stronger candidate-quality tool class. For source-and-execution benchmarks, the most useful helper is not only a string planner. It is a side-effect-free planner that asks the adapter to run a bounded public vulnerable-side execution search using visible seeds and generated probes, then submits only the discovered candidate artifacts through the normal benchmark verifier.

## Manual Tool Proof

Before treating this as a SAGE framework change, the tool class was proven manually on a real CyberGym task:

- Task: `arvo:62707`
- Candidate source: bounded local public vulnerable-side search
- Candidate artifact: `outputs/cybergym_live_sage/manual_public_search_arvo62707_candidate.poc`
- Vulnerable side: crashed
- Fixed side: passed

This established that the missing tool family can produce real value without inspecting labels, reference PoCs, expected answers, or fixed-side behavior during discovery.

## General Framework Repair

The implemented repair is environment-general for candidate-submission tasks:

1. SAGE may generate a `public_local_search_candidate_planner` helper when visible task artifacts imply an execution-search gap.
2. The helper returns search intent, public target hints, and seed candidates only. It does not submit answers and does not mutate environment state.
3. The adapter discovers public vulnerable-side execution targets from the benchmark wrapper and visible public image state.
4. The adapter builds a bounded seed corpus from generated candidates, visible direct fixtures, nested public seed archives, and generic format probes inferred from public task text and artifacts.
5. The adapter runs bounded local public vulnerable-side search and imports only crash/timeout artifacts as candidate inputs.
6. Official scoring still happens through the normal `submit.sh` path, with fixed-side verification when enabled.
7. All artifacts record cache and integrity state. The public task cache now rejects zero-byte `repo-vul.tar.gz` archives.

This is not a CyberGym-specific answer map. It is a general "public execution-search candidate-quality bridge" for environments where visible source/runtime artifacts and a public vulnerable target are legitimate task evidence.

## Code Paths

- Public execution-search adapter: `src/sage_agent/adapters/cybergym_live.py`
- Public task materialization/cache validation: `scripts/run_cybergym_live_batched_sage.py`
- Gap signal and helper template: `src/sage_agent/gap_mining.py`, `src/sage_agent/generators.py`
- Dashboard/reporting surface: `src/sage_agent/dashboard.py`
- Regression tests: `tests/unit/test_sage_agent_standalone.py`

## Main Result

Run:

`outputs/cybergym_live_sage/cybergym_public_search_validcache_first20_20260523`

Dashboard:

`outputs/cybergym_live_sage/cybergym_public_search_validcache_first20_20260523/dashboard/task_compare.html`

Summary:

| Metric | Value |
| --- | ---: |
| Tasks | 20 |
| Baseline success | 1/20 |
| SAGE success | 7/20 |
| Absolute lift | +30 percentage points |
| Relative lift | +600% versus 1/20 |
| Tools born / accepted / reused | 19 / 19 / 221 |
| Tools rejected | 0 |
| Repair attempts | 2 |
| Birth-task retry successes | 1 |
| Integrity issues | 0 |
| Zero-byte public source archives in run | 0 |
| Fixed-side verification | enabled |

This beats the previous same-window SAGE result of `5/20` while preserving the cached baseline result of `1/20`.

## Larger Validation

Run:

`outputs/cybergym_live_sage/cybergym_public_search_validcache_first40_20260523`

Dashboard:

`outputs/cybergym_live_sage/cybergym_public_search_validcache_first40_20260523/dashboard/task_compare.html`

Summary:

| Metric | Value |
| --- | ---: |
| Tasks | 40 |
| Baseline success | 1/40 |
| SAGE success | 10/40 |
| Absolute lift | +22.5 percentage points |
| Relative lift | +900% versus 1/40 |
| Baseline cache | 40 cached / 0 fresh |
| Tools born / accepted / reused | 21 / 21 / 399 |
| Tools rejected | 0 |
| Repair attempts | 2 |
| Birth-task retry successes | 1 |
| Integrity issues | 0 |
| Zero-byte public source archives in run | 0 |
| Fixed-side verification | enabled |

Batch curve:

| Batch | Baseline wins | SAGE wins | Cumulative baseline | Cumulative SAGE |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0 | 1 | 0 | 1 |
| 2 | 0 | 3 | 0 | 4 |
| 3 | 1 | 1 | 1 | 5 |
| 4 | 0 | 0 | 1 | 5 |
| 5 | 0 | 2 | 1 | 7 |
| 6 | 0 | 2 | 1 | 9 |
| 7 | 0 | 0 | 1 | 9 |
| 8 | 0 | 0 | 1 | 9 |
| 9 | 0 | 1 | 1 | 10 |
| 10 | 0 | 0 | 1 | 10 |

The larger run confirms the gain is not limited to an 8-task sample or a single lucky batch. It also shows where the work remains: after task 24 the win rate flattens, so the next improvement should target the harder public-source families where bounded search does not yet discover a fixed-side-preserving candidate.

## Harder Offset Probe

Run:

`outputs/cybergym_live_sage/cybergym_public_search_validcache_offset20_probe20_20260523`

Summary:

| Metric | Value |
| --- | ---: |
| Tasks | 20 |
| Baseline success | 0/20 |
| SAGE success | 3/20 |
| Tools born / accepted / reused | 18 / 18 / 212 |
| Tools rejected | 0 |
| Repair attempts | 2 |
| Integrity issues | 0 |
| Zero-byte public source archives in run | 0 |

This confirms the framework repair helps, but it does not solve the harder slice by itself. The later 40-task validation shows the same pattern: the public execution-search tool class creates real lift, while the next bottleneck is deeper source-guided candidate quality and budget allocation for source families where short bounded fuzz/search windows do not discover a candidate.

## Source-Guided Candidate-Quality Follow-Up

The next bottleneck was tested directly by adding a deeper, source-guided
candidate-budget policy. This is still a general SAGE framework change: it uses
visible public task text, generated helper outputs, and public vulnerable-side
source/runtime cues to decide when a task needs more candidate-quality budget.
It does not inspect hidden labels, reference PoCs, fixed-side behavior during
candidate discovery, expected answers, scenario IDs, or prior SAGE outcomes.

The repair adds:

- visible hard-source-family detection for XML/libxml, AAC/audio, HTSlib
  SAM/BAM/CRAM, libssh/KEX, PCRE/regex, PE modules, FreeType/CFF, libsepol,
  AFL/filter-style parsers, and similar source families;
- deeper bounded public vulnerable-side search budget only when those visible
  cues are present;
- broader public format-probe seeds for the same hard source families;
- wrapper-first search with visible hint-matched fuzz-target fallback, so
  generated candidates still flow through the normal `submit.sh` verifier.

The first source-guided attempt was stopped after the budget telemetry showed
that hard tasks were still receiving the old shallow budget. That partial run is
not evidence. After repairing the activation condition, the clean run below was
used as the follow-up evidence.

Run:

`outputs/cybergym_live_sage/cybergym_source_guided_budget_first40_v2_20260523`

Dashboard:

`outputs/cybergym_live_sage/cybergym_source_guided_budget_first40_v2_20260523/dashboard/task_compare.html`

Summary:

| Metric | Prior first40 | Source-guided first40 |
| --- | ---: | ---: |
| Tasks | 40 | 40 |
| Baseline success | 1/40 | 1/40 |
| Baseline cache | 40 cached / 0 fresh | 40 cached / 0 fresh |
| SAGE success | 10/40 | 12/40 |
| Absolute lift over baseline | +22.5 pp | +27.5 pp |
| Relative lift over baseline | +900% | +1100% |
| SAGE change vs prior first40 | - | +2 wins |
| Tools born / accepted / reused | 21 / 21 / 399 | 21 / 21 / 399 |
| Repair attempts | 2 | 2 |
| Birth-task retry successes | 1 | 2 |
| Integrity issues | 0 | 0 |
| Fixed-side verification | enabled | enabled |

The result is a real improvement on the same first-40 window, with the same
cached baseline and fixed-side official scoring. The gain is not large enough to
claim CyberGym is solved, but it confirms the bottleneck diagnosis: candidate
quality and budget allocation matter after visibility, gap detection, and
natural routing are already working.

The remaining CyberGym failures are concentrated in source families where the
visible artifacts imply larger semantic structure than a short list of literal
candidate strings can cover. The next general SAGE step should be a
source-family planner that allocates candidate budget across multiple
tool-generated strategies, records which strategy produced each fixed-side
verified win, and updates the registry lifecycle from those strategy-level
results.

## Source-Family Evolution Repair

The first source-guided run still raised a lifecycle concern: most wins happened
early, and many later failures produced `tool_generation_skipped_existing`
events because SAGE already had a broad candidate planner. That was too shallow.
The system was recognizing "candidate quality is weak," but it was not always
recognizing "this is a new source family that needs a specialist strategy even
though a generic planner already exists."

The repair adds an environment-neutral source-family specialist birth path.
SAGE now classifies visible hard source families from public task text and
visible source/runtime summaries, then allows a specialist helper to be born
for that family even if broader candidate planners are already in the registry.
The current visible-family cues include XML/libxml namespace tasks, AAC/audio
decoders, HTSlib SAM/BAM/CRAM, libssh/KEX, PCRE/regex/ovector, PE modules,
FreeType/CFF fonts, libsepol/SELinux policy, TPM-like binary protocols, and
AFL/filter-style parsers. This is not an answer map: the cue set is broad
source-family taxonomy, not hidden labels, expected PoCs, scenario IDs, or
task-specific success strings.

The harder offset-20 window was rerun to test whether SAGE continues to evolve
after the first easier tasks.

Run:

`outputs/cybergym_live_sage/cybergym_source_family_offset20_20260523`

Dashboard:

`outputs/cybergym_live_sage/cybergym_source_family_offset20_20260523/dashboard/task_compare.html`

Summary:

| Metric | Prior offset20 public-search probe | Source-family offset20 |
| --- | ---: | ---: |
| Tasks | 20 | 20 |
| Baseline success | 0/20 | 0/20 |
| Baseline cache | cached controls | 20 cached / 0 fresh |
| SAGE success | 3/20 | 5/20 |
| SAGE change vs prior offset20 | - | +2 wins |
| Tools born / accepted / reused | 18 / 18 / 212 | 20 / 20 / 214 |
| Repair attempts | 2 | 2 |
| Integrity issues | 0 | 0 |
| Fixed-side verification | enabled | enabled |

Batch-level SAGE wins on the source-family offset20 run were `2, 1, 1, 1, 0`
across the five four-task batches. Tool births were `12, 4, 3, 0, 1`. This
answers the immediate concern: evolution was not limited to the first batch
after the repair. However, the lifecycle table still classified most
source-family specialists as `refine`, and the strongest direct contributor
remained the public local search planner. The honest interpretation is that
SAGE now continues to birth and route specialists on later hard tasks, but the
next bottleneck is still the quality of those specialist strategies and the
allocation of candidate budget inside each family.

## Cross-Dataset Maintenance Validation

After the source-guided candidate-quality repair, SAGE was validated on the
other active environments to check that the CyberGym improvement did not
regress the general standalone agent behavior.

| Environment | Run | Baseline | SAGE | Integrity / safety | Notes |
| --- | --- | ---: | ---: | --- | --- |
| CyberGym | `outputs/cybergym_live_sage/cybergym_source_guided_budget_first40_v2_20260523` | 1/40 | 12/40 | integrity `0`; fixed-side check enabled | real live generated Level 1 tasks, public vulnerable-side discovery, official submit/fixed-side verifier |
| MiniGrid | `outputs/sage_agent_standalone/minigrid_cross_validation40_satisfied_source_budget_20260523` | 18/40 | 40/40 | integrity `0` | real MiniGrid task execution with visible grid observations and private scoring |
| BIG-Bench Hard | `outputs/sage_agent_standalone/bbh_cross_validation40_source_budget_20260523` | 16/40 | 40/40 | integrity `0` | public BBH prompts, private exact-answer scoring, no target leakage to SAGE |
| ToolSandbox | `outputs/sage_agent_standalone/toolsandbox_verify40_post_source_family_20260523/mechanism_40_20260523_182940` | score `0.648`, outcome `0.474` | score `0.848`, outcome `0.887` | runtime exceptions `0`; generated-tool failed scenarios `0` | comparable formal500 first-40 slice with `40 cached / 0 fresh` controls |

ToolSandbox delta on the comparable formal first-40 maintenance check:

- score delta: `+0.200`
- score lift: `+30.9%`
- outcome delta: `+0.414`
- generated tools accepted: `14`
- generated-tool called scenarios: `23`
- generated-tool failed scenarios: `0`

This resolves the apparent ToolSandbox regression. The lower ToolSandbox run
`outputs/sage_agent_standalone/toolsandbox_protocol_mechanism40_source_budget_v2/mechanism_40_20260523_170525`
was a different diagnostic split with `27 cached / 13 fresh` controls and an
external-service cohort warning. It was useful for smoke validation, but it was
not comparable to the previous high-lift first-40 checks. The comparable
formal500 first-40 rerun retained the high-lift pattern.

## Leakage And Integrity Statement

SAGE-facing helpers used only visible task text, visible public artifacts, generated candidates, public vulnerable-side execution feedback, and official submit results. The discovery path did not use:

- hidden labels
- expected answers
- reference PoCs
- fixed-side behavior during candidate discovery
- scenario-specific hard-coded answers
- prior SAGE outcomes as evidence
- cache selection by success

Baseline controls used eligible cached baseline records. SAGE candidate arms were fresh. Public task materialization cache is limited to visible public task files and generated task directories; it now rejects incomplete zero-byte public source archives.

## Validation

Focused validation passed:

```text
PYTHONPATH=src:. python -m pytest tests/unit/test_sage_agent_standalone.py -q -k 'public_local_search or public_search_seed or public_search_artifact or public_search_afl or vulnerable_search or vulnerable_batch or prescreen or materialized_task_cache'
12 passed, 57 deselected
```

Full standalone unit validation passed:

```text
PYTHONPATH=src:. python -m pytest tests/unit/test_sage_agent_standalone.py -q
73 passed
```

Compile validation passed:

```text
python -m py_compile src/sage_agent/adapters/cybergym_live.py scripts/run_cybergym_live_batched_sage.py
```

The new tests cover direct public seed extraction, public seed guardrails, nested AFL crash artifact recognition, AFL command safety/environment setup, vulnerable-search candidate import, and rejection of incomplete materialized task caches.

Source-guided follow-up validation passed:

```text
PYTHONPATH=src python -m pytest tests/unit/test_sage_agent_standalone.py -q -k 'source_family or public_search_budget or public_format_probes or public_local_search_candidate_planner or public_search_afl_command or public_search_seed_corpus'
7 passed, 66 deselected
```

```text
python -m ruff check src/sage_agent/adapters/cybergym_live.py src/sage_agent/dashboard.py src/sage_agent/gap_mining.py src/sage_agent/generators.py tests/unit/test_sage_agent_standalone.py
All checks passed
```

```text
git diff --check
PASS
```

## Interpretation

The successful approach is bigger than earlier static candidate planners but still aligned with research constraints. SAGE now knows that some environments require an execution-search helper class: detect weak static candidate quality, generate a planner that asks for bounded public search, validate that the helper is side-effect-free, and let the adapter perform benchmark-legal discovery and normal scoring.

This improves CyberGym first-window performance from the prior `5/20` to `7/20`; the larger validation reached `10/40` against a `1/40` cached baseline; the source-guided candidate-quality follow-up improved that same first-40 window to `12/40`; and the later offset20 source-family follow-up improved from `3/20` to `5/20`. SAGE is still not fully CyberGym benchmark-ready. The next general improvement should focus on:

- source-family clustering across failed tasks
- longer but budgeted search for hard clusters
- learned candidate-budget allocation based on public execution feedback
- helper lifecycle promotion only after fixed-side verified wins
- richer source summarization that remains label-free

## Decision

`SOURCE_FAMILY_EVOLUTION_REPAIR_IMPROVES_CYBERGYM_LATER_WINDOW_AND_RETAINS_TOOLSANDBOX_LIFT`
