# CyberGym Reference Reassessment - 2026-05-22

This is an experimental reassessment note for standalone SAGE on CyberGym. It is not protected final-claim evidence.

## Question

The concern was that current CyberGym runs appeared to be moving away from the early result where the baseline solved about 1/20 tasks and SAGE solved about 4-5/20 tasks. The reassessment checks whether that was a real SAGE regression or a run-design artifact.

## Reference Runs

| Run | Baseline | SAGE | Tools born | Tools accepted | Tool reuse | Integrity issues |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `balanced_visible_budget_probe20_v2_20260522` | 1/20 | 5/20 | 7 | 7 | 114 | 0 |
| `persistent_feedback_probe20_v1_20260522` | 1/20 | 5/20 | 13 | 13 | 178 | 0 |
| `semantic_candidate_probe20_v3_20260522` | 1/20 | 5/20 | 13 | 13 | 178 | 0 |
| `general_gap_v2_20_rerun_20260521_151632` | 1/20 | 5/20 | 4 | 4 | 86 | 0 |
| `pulse_replay_balanced12_20_20260522` | 1/20 | 5/20 | 28 | 13 | 172 | 0 |

The replay run confirms the early success is still reproducible on the same first-20 window.

## What Looked Like Regression

The recent flat runs were mostly not comparable to the reference runs. They focused on an offset window where the prior first-20 run also had sparse lift. In the first-20 reference, SAGE's wins were concentrated at tasks 1, 6, 9, 17, and 20. Checking only a middle offset can therefore show little or no lift even when the same mechanism is still working.

The second issue was policy drift. The newer context-aware candidate ranking was too eager to make candidate strings look semantically related to the task description. CyberGym success often comes from odd visible artifacts such as dictionary entries, configure flags, source literals, public documentation URLs, and malformed format fragments. These are not cheating when they are visible task artifacts, but they can look noisy and get demoted by an over-semantic ranker.

## Current Interpretation

SAGE is not getting further away from the early CyberGym success. The recovered `pulse_replay_balanced12_20_20260522` run matched the 1/20 baseline and 5/20 SAGE result with zero integrity issues. The main lesson is that the working CyberGym mechanism is broad public-artifact harvesting plus immediate birth/retry and reuse, not narrow semantic candidate selection.

The current default should therefore remain the balanced broad-harvest strategy. Context-aware ranking should be treated as an explicit experiment, not the default CyberGym policy, until it beats the same-window reference.

## Regular Re-Evaluation Policy

For CyberGym adaptation runs, use pulse checks after each 4-task batch:

| Tasks seen | Reference baseline | Reference SAGE | Decision rule |
| ---: | ---: | ---: | --- |
| 4 | 0 | 1 | Continue unless integrity or setup fails. |
| 8 | 0 | 2 | Continue if SAGE is within one win; reassess if lower. |
| 12 | 1 | 3 | Continue if on track; inspect if one win behind. |
| 16 | 1 | 3 | Do not overreact; reference wins are sparse. |
| 20 | 1 | 5 | Treat below 4/20 as a policy or candidate-quality regression. |

The batched CyberGym runner now records `pulse_assessment` metadata in each batch report by default. This does not change tool generation, routing, candidate ordering, or scoring; it only records whether the run is on track against the reference curve.

## Next Technical Focus

The next improvement should not manually expose tools or hard-code CyberGym answers. It should improve the general SAGE lifecycle by preserving broad artifact diversity while making candidate budgets smarter:

- keep public artifact literals in the candidate portfolio even when they look noisy,
- use failed execution feedback to redesign planners,
- archive or repair tools that repeatedly produce no successful candidates,
- compare only same-window runs before deciding a policy regressed,
- validate any stricter ranking against the first-20 reference before scaling.
