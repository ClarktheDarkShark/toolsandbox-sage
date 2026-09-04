# Final Limitations And Future Work

> **SUPERSEDED — ARCHIVAL ONLY.** This document describes an earlier evidence
> package and is not current publication guidance. See
> [current_state.md](current_state.md).

## Limitations

- The frozen best3 portfolio is the broad locked claim portfolio; V2.6 expanded contact-scalar helpers are a safe, current-code-positive candidate portfolio with targeted gap-closure evidence.
- The V2.6 matched gap-enriched frozen250 run proves a `17.39%` relative helper-fit gap reduction on a targeted manifest, not the original formal250 absolute `44.4% -> <=40.0%` threshold.
- Current-code original250 matched evidence is outcome-positive for expanded V2.6 (`+0.0100`) and dynamically reduces no-current-helper-fit by `11.54%`, but canonical/reference falls by `0.0283` and exact successes fall by 8.
- Current-code non-external500 matched evidence is positive for outcome (`+0.0101`), canonical/reference (`+0.0225`), and exact successes (`+1`), but broad helper-fit reduction is `7.10%`, below the 10% relative gap-reduction target.
- The 500 sample shows that contact-scalar tools do not cover enough of the remaining helper-fit gap. Many remaining no-fit cases are reminder/action, service/precondition, insufficient-information, or other non-contact lanes.
- `plan_contact_search_from_scalar_constraint` was naturally called at 500 and showed positive direct expanded-vs-best3 called-subset outcome, but `plan_contact_lookup_query` and `extract_contact_field_from_search_result` were mixed versus current-code best3 despite positive contribution versus control.
- The locked matched gap250 evidence remains valid, but a current-code matched gap250 rerun was deferred because the higher-value missing evidence was original250 and non-external500 matched validation.
- A 1032 expanded current-code validation was deferred because 500 provides broad non-external scale evidence and 1032 includes sparse/external lanes not specifically targeted by contact-scalar tools.
- Outcome/task-completion remains primary. Canonical/reference score is secondary and can diverge when helper substitution, route mismatch, or stochastic trajectory differences occur.
- Final frozen runs must explicitly disable or pin routing contribution evidence. Earlier diagnostic/discovery behavior allowed routing to consult latest helper-contribution summaries by mtime, which is not acceptable for future final claims.
- Task-level cached controls are score-complete for metric arithmetic, but cached-only synthetic control rows can be trace-incomplete. Feedback packets now label this as `score_complete_trace_incomplete`; trace-level control interpretation should not be overclaimed for those rows.
- Methodology-critical helper-fit, task-strata, and routing thresholds remain protocol-defined heuristics. They are version-documented in `docs/sage_protocol/protocol_heuristics_v1.json`, but not fully externalized into executable config.

## Future Work

- Target the next gap-closure campaign at non-contact no-fit lanes, especially safe insufficient-information handling, reminder/action workflows, and service/precondition cases.
- Split the contact-scalar portfolio analysis by helper before any broad promotion: scalar contact search appears stronger at 500 than the earlier two-step contact lookup/extraction pair.
- Continue improving evidence-aware routing to reduce visible-not-called exposure without suppressing high-value helpers on matching tasks.
- Extend feedback packets to distinguish static no-current-helper-fit, dynamic helper-hidden no-fit, and helper-visible-but-not-called adoption gaps.
- Run expanded 1032 only if the research narrative requires broad full-benchmark validation beyond non-external500 evidence.
- If pursuing publication-grade expanded-portfolio claims, preregister whether success means targeted gap closure, broad helper-fit reduction, broad outcome lift, or all three; the current evidence supports the first two only in limited forms.
- Before any future large final run, run `scripts/preflight_final_run.py` with generation OFF, control cache `use-if-eligible`, and routing evidence `disabled` or `pinned`.
