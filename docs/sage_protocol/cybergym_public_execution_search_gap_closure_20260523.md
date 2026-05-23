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
69 passed
```

Compile validation passed:

```text
python -m py_compile src/sage_agent/adapters/cybergym_live.py scripts/run_cybergym_live_batched_sage.py
```

The new tests cover direct public seed extraction, public seed guardrails, nested AFL crash artifact recognition, AFL command safety/environment setup, vulnerable-search candidate import, and rejection of incomplete materialized task caches.

## Interpretation

The successful approach is bigger than earlier static candidate planners but still aligned with research constraints. SAGE now knows that some environments require an execution-search helper class: detect weak static candidate quality, generate a planner that asks for bounded public search, validate that the helper is side-effect-free, and let the adapter perform benchmark-legal discovery and normal scoring.

This improves CyberGym first-window performance from the prior `5/20` to `7/20`, and the larger validation reaches `10/40` against a `1/40` cached baseline. SAGE is still not fully CyberGym benchmark-ready. The next general improvement should focus on:

- source-family clustering across failed tasks
- longer but budgeted search for hard clusters
- learned candidate-budget allocation based on public execution feedback
- helper lifecycle promotion only after fixed-side verified wins
- richer source summarization that remains label-free

## Decision

`PUBLIC_EXECUTION_SEARCH_IMPROVES_CYBERGYM_FIRST20_WITH_GENERAL_FRAMEWORK_REPAIR`
