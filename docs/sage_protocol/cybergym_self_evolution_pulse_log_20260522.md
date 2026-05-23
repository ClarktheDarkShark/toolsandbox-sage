# CyberGym Self-Evolution Pulse Log - 2026-05-22

This is a working pulse log for the standalone SAGE CyberGym adaptation. It is experimental engineering evidence, not protected final-claim evidence.

## Current Reference Target

The immediate reference target is the prior CyberGym first-20 live fixed-side result:

- Baseline: 1/20
- SAGE: 5/20 in several runs, and 4/20 in earlier generic-visible runs
- Fixed-side verification: enabled on the strongest replay runs
- Baseline cache: used for control tasks where eligible
- Generated-tool registry: starts empty for each probe

Representative run roots:

- `outputs/cybergym_live_sage/balanced_visible_budget_probe20_v2_20260522/`
- `outputs/cybergym_live_sage/persistent_feedback_probe20_v1_20260522/`
- `outputs/cybergym_live_sage/semantic_candidate_probe20_v3_20260522/`
- `outputs/cybergym_live_sage/general_gap_v2_20_rerun_20260521_151632/`

## What Worked

The successful first-20 runs did not succeed by producing polished, human-obvious exploit inputs. They succeeded through broad public-artifact harvesting:

- dictionary entries from visible fuzz dictionaries,
- configure flags and option strings,
- source literals and source-line fragments,
- public documentation URLs and text,
- XML and regex edge strings,
- adaptive reuse of prior failed candidate attempts.

The core value was not a single perfect CyberGym-specific tool. It was SAGE birthing reusable candidate-planner helpers, routing a compact bundle, submitting their generated candidates through the environment, and retaining evidence about which helpers contributed.

## What Did Not Work

Recent offset-8 and v7/v8 experiments were drifting away from the reference success in two ways:

- They tested a harder contiguous window where prior methods also tended to flatten, so they were not comparable to the first-20 reference.
- A stricter context-aware ranking policy risked demoting odd but valid public artifacts, such as URLs, configure options, and dictionary tokens. Those artifacts looked noisy to a human but were part of the earlier success path.

## Current Correction

Normal CyberGym runs now preserve the earlier broad-harvest ranking behavior under `balanced`, `literal-reserve`, `sample-first`, and related strategies. The stricter task-aware ranking remains available as the explicit `context-aware` experiment only.

The replay matrix initially compared:

- `pulse_replay_balanced8_20_20260522`
- `pulse_replay_balanced12_20_20260522`
- `pulse_literal_reserve12_20_20260522`
- `pulse_sample_first12_20_20260522`
- `pulse_context_aware12_20_20260522`

After early pulse checks, the matrix was pruned to `pulse_replay_balanced12_20_20260522` because it was the only strategy that reproduced the reference first-batch birth/retry mechanism without demoting odd public artifacts. The completed replay matched the historical first-20 result:

- Baseline: 1/20
- SAGE: 5/20
- Tools born: 28
- Tools accepted: 13
- Tools reused: 172
- Birth-task retry successes: 1
- Integrity issues: 0
- Run root: `outputs/cybergym_live_sage/pulse_replay_balanced12_20_20260522/`

This confirms that the apparent recent regression was not a core SAGE failure. It was caused by evaluating on a harder contiguous offset window and by over-tightening candidate ranking in a way that could suppress useful public artifacts.

## Pulse Rules

For CyberGym adaptation work, re-evaluate after each 4-task batch and before any larger run:

1. Compare against the fixed reference target, not only the latest run.
2. Check whether baseline cached count is complete.
3. Check SAGE task wins, fixed-side wins, tool births, accepted tools, rejected tools, and helper reuse.
4. Inspect winning and failed candidate strings.
5. If a strategy is slower and not producing incremental fixed-side wins by the first or second batch, stop or downscale it.
6. Prefer preserving broad public-artifact harvesting unless a stricter ranking demonstrably improves same-window outcome.
7. Do not use hidden PoCs, expected answers, task labels, or post-hoc truth to generate or rank tools.

The batched CyberGym runner now records a non-interventional `pulse_assessment` in each batch report by default. That assessment compares batch-level progress to the same-window first-20 reference curve. It is metadata only; it does not alter generation, routing, candidate ordering, or scoring.

## Current Hypothesis

SAGE is not fundamentally failing to identify gaps on CyberGym. It is identifying candidate-submission gaps and birthing tools. The key weakness is candidate quality and candidate budget allocation after generation. The next useful improvements should focus on:

- broader but better ordered public-artifact harvesting,
- lifecycle feedback from failed candidates into redesigned planners,
- retaining weird public artifacts that empirically help,
- avoiding overly semantic ranking that discards valid crash triggers,
- comparing on the same task windows before judging progress.
