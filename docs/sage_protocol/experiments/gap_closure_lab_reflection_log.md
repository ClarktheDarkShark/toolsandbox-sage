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

## 2026-05-09 - Reflection 05 - External Holdout Stress Test

**Observation.** A stricter residual scan found 118 fresh uninspected scenarios, but all were external-service families. I built an experimental confirm100 holdout from them to execute the recommended next action anyway. The run was outcome-negative (-0.0447), canonical-slightly-positive (+0.0085), exact-success-positive (+5), and safe, but all retained recency/day helpers were hidden because the cohort had 0/100 expected helper fit.

**Interpretation.** This does not invalidate the day-distance helper; it tests a different gap family. It also does not unblock formal validation because the holdout is external-service contaminated and failed primary outcome.

**Next action.** Record the result as a negative experimental stress test, do not scale, and keep the clean-data blocker. A future campaign needs a new non-external split with day-distance/recency opportunities, not another external-service rerun.

**Micro/macro adjustment.** The right macro move is to stop local confirmation attempts on mismatched residual data. Further progress requires new data or a separate external-service tool family, not more recombination of the retained recency/day portfolio on no-fit tasks.

## 2026-05-09 - Reflection 06 - High-Fit Scale Breakthrough

**Observation.** After the campaign directive to pursue 250/500 scale rather than stop at data exhaustion, I built a high-fit experimental split and recombined the retained recency/day/contact positives into a compact portfolio. It passed scale250 with outcome +0.3723 and scale500 with outcome +0.2488, canonical +0.1281, exact success +83, zero runtime exceptions, and zero helper side-effect incidents.

**Interpretation.** The earlier broad-mixed failures were largely cohort-fit and adoption problems, not proof that the retained tools lacked value. Concentrating the portfolio around the lanes where the helpers have real affordance produced natural calls at scale. The remaining caveat is evaluation status: this is high-fit revalidation with prior local output coverage and quality warnings, not protected final evidence.

**Next action.** Freeze the high-fit portfolio for a clean same-manifest formal validation campaign against protected best3/V2.6. Watch `extract_contact_field_from_search_result` because it was safe but called-subset-negative in the scale500; keep the narrowed contact planners but require contribution analysis before formal promotion.

**Micro/macro adjustment.** The correct macro step was to stop iterating only on tiny mixed pilots and build a portfolio-level scale test around the actual positive lanes. The next microstep should not be more prompt tweaking; it should be formal validation design and strict matched-arm execution.

## 2026-05-09 - Reflection 07 - Broad500 Top-Tool Stress And Next Gap

**Observation.** The run named `Broad500 Top Tool Combo: Full Timestamp No-Field Pack` passed at 500 broad tasks with outcome +0.1406, canonical +0.0596, exact success +42, zero runtime exceptions, and zero helper side-effect incidents. It is positive, but its run-vs-control lift is below the documented current-code best3 500 lift of +0.1617. The strongest called subsets remained recency/date/contact lanes, while the largest no-effective-tool buckets were safe insufficient-information, settings/device-state, contact CRUD, reminder CRUD/scheduling, and send-message preconditions.

**Interpretation.** The retained positive tools are real and should not be discarded for low frequency. They are not enough by themselves to close the broad gap because many broad tasks need side-effect-free feasibility, missing-info, precondition, and final action-spec normalization rather than another recency selector.

**Next action.** Generate and test a small routed `prepare_safe_action_or_abstain` family: a feasibility classifier, an action-spec normalizer, and a chain variant that can use existing timestamp/recency helpers. Start with targeted20 natural adoption, use force diagnostics only on safe seed/dev cases, then move to expanded60 only if natural calls and outcome are positive.

**Micro/macro adjustment.** Stop over-investing in minor recency metadata tweaks. The next macro bet should group several unsupported buckets under one side-effect-free action/precondition tool type, while preserving the current retained positives as a smaller routed portfolio.

## 2026-05-10 - Reflection 08 - Bucket Closure And Broad BridgePack Breakthrough

**Observation.** The action/precondition loop closed reminder CRUD/scheduling at narrow100 with outcome `+0.2100`, contact CRUD at narrow100 with outcome `+0.3303`, and settings/device-state at confirm100 with outcome `+0.0946`. Recombining those retained positives with best3-style timestamp/window/record selectors and the contact/reminder/ack-retention actor bridge produced `BridgePack Broad500: Ack-Retention Contact+Reminder+State Pack`: control `0.5949`, SAGE `0.8213`, delta `+0.2264`, relative lift `+38.1%`, exact success delta `+155`, runtime exceptions `0`, and no observed helper side-effect incidents.

**Interpretation.** The biggest blocker was not a single missing deterministic helper. It was the shallow interaction between routing/adoption and final-response policy: useful low-frequency tools needed a compact portfolio plus actor bridge support so they were actually used when their specific gap appeared. The broad500 result beats the documented best3 500 run-vs-control lift experimentally, but it depends on branch-only bridge code and therefore is not protected claim evidence.

**Next action.** Freeze BridgePack as an experimental candidate, stop making code or registry changes for the matched comparison, and run clean formal-style validation against protected best3 and V2.6 on the same formal manifest with per-task control cache, fresh candidate arms, Task Focus dashboards, contribution export, and explicit bridge-policy reporting.

**Micro/macro adjustment.** The campaign should now move from tool discovery to validation discipline. Further micro-tweaks risk overfitting the inspected broad500 diagnosis; the next useful work is a locked matched formal run and, separately, a small repair lane for the remaining insufficient-information and settings regressions.

## 2026-05-10 - Reflection 09 - Clean Broad500 Rerun After Bridge Repairs

**Observation.** The first broad500 bridge result was strong, but follow-up diagnostics exposed two infrastructure risks: bridge calls could fail under tool-name scrambling because the synthetic calls used execution names, and a search-required contact planner could be misread as a missing side-effect. I repaired both and reran the full broad500 with cached controls and fresh candidate execution. The clean rerun produced control `0.5949`, SAGE `0.8134`, delta `+0.2185`, relative lift `+36.7%`, exact success delta `+163`, runtime exceptions `0`, and helper side-effect incidents `0`.

**Interpretation.** The result is slightly lower than the earlier peak bridge run, but it is the better campaign reference because it validates the repaired bridge machinery under full broad stress. The lift still clears the documented current-code best3 500 run-vs-control lift by roughly `0.0568` outcome points. The positive signal is therefore not only a narrow bucket artifact; it survives a broad same-split rerun once the infrastructure risks are removed.

**Next action.** Stop local code/registry changes for this candidate and prepare a locked matched formal validation against protected best3 and V2.6. The report must separate registry value from bridge-policy value, because this branch has not proven a registry-only replacement.

**Micro/macro adjustment.** The campaign has reached validation discipline. Additional tweaks on this inspected branch are now more likely to overfit than to improve claim quality; the right next step is freezing the candidate and comparing it cleanly.
