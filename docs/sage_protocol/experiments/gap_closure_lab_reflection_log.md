# SAGE Gap-Closure Lab Reflection Log

This log is experimental process evidence only. It is not protected final claim evidence.

## 2026-05-08 - Reflection 01 - Hidden/No-Call Confirmation Regression

**Observation.** The selector-only confirmation100 run failed broadly, but the main outcome loss was concentrated in hidden/no-call scenarios rather than in natural helper calls. Selector-only expanded60 showed a strong low-frequency called subset, while confirmation100 showed only two natural calls and one side-effect preservation incident on a remove-reminder case.

**Interpretation.** More tool generation would be premature until the paired-run scaffold/noise floor is measured. A retained helper can be useful even when rare, but hidden/no-call regressions make it unclear whether the candidate arm is suffering from run variance, global actor policy effects, or an unrelated harness asymmetry.

**Next action.** Run a null-scaffold experimental registry with no retained helpers on the same expanded60 protocol. If the null arm moves materially, treat broad deltas from low-exposure packs as noisy and shift to adoption/routing subsets, repeated measurements, or harness parity repair before scaling. If null is stable, resume recency/action portfolio recombination with stricter routing and side-effect-safe affordances.

**Micro/macro adjustment.** Pause micro-iterations on individual helper descriptions; first verify the experimental pipeline itself can distinguish rare helper value from broad paired-run variance.

## 2026-05-09 - Reflection 02 - Task 77 Outcome Versus Canonical

**Observation.** Task 77 was reported as SAGE missing points, but the final answer was correct. The outcome scorer gave 1.000 while canonical/reference scoring was 0.978 because the answer and tool trace only partially matched the canonical reference form.

**Interpretation.** The dashboard was overemphasizing canonical score as if it were final task correctness. This matters more once generated helpers substitute for reference intermediate tools, such as `days_between_timestamps` replacing `timestamp_diff`.

**Next action.** Repair the Task Focus exporter/template to display outcome correctness and canonical score separately. Treat canonical/reference as secondary unless outcome regresses or final state/side effects are wrong.

**Micro/macro adjustment.** Do not discard tools merely because canonical score drops when the outcome is correct. Instead, classify whether the loss is a route-substitution artifact, answer-shape issue, or true task failure.

## 2026-05-09 - Reflection 03 - Day-Distance Gap And Answer Shape

**Observation.** The quality expanded60 run exposed a missing day-distance helper. Adding `days_between_timestamps` produced the best broad-quality outcome backtest in the continuation: outcome +0.0735, exact success +3, zero incidents, and natural calls 11/11 visible. A final-answer-ready variant helped a narrow holiday residual diagnostic but regressed on the quality split.

**Interpretation.** The deterministic arithmetic helper is valuable, but adding final phrasing into the helper over-shaped the actor behavior in mixed cohorts. The simpler scalar helper is more robust even though canonical/reference scoring penalizes the substituted intermediate route.

**Next action.** Retain `days_between_timestamps` as the best current experimental candidate. Park `format_days_until_event_answer` for broad routing. Future final-answer-ready versions need stronger negative triggers and probably chain-level validation before exposure.

**Micro/macro adjustment.** Small targeted helpers can carry real gap value. The next campaign should scale a clean version of the simple helper before adding more expressive answer formatting.

## 2026-05-09 - Reflection 04 - Pruning And Scale Discipline

**Observation.** Pruning to a five-tool recency/time/day portfolio reduced context and improved exact successes (+7), but outcome was +0.0542, below the unpruned days pack (+0.0735). The 100/250 confirmation/scale splits that remain clean enough in concept are already inspected/backtest-only here, and the cache planner showed 0/100 and 0/250 eligible cached controls under the three-run rule.

**Interpretation.** More local backtests are now mostly measuring run variance and inspected-split fit, not clean generalization. A scale250 run would consume fresh control and candidate calls but still could not be formal evidence because the split has been inspected and used for repair decisions.

**Next action.** Stop this branch as experimental with a data-exhaustion blocker for formal validation. Recommend a new clean frozen confirmation100/scale250 campaign carrying the retained `days_between_timestamps` and minimal recency/time/day pack.

**Micro/macro adjustment.** Avoid taking too many late microsteps on the same inspected split. The system found the best local direction; the bottleneck is now clean evaluation capacity, not another prompt tweak.
