# tau3 SAGEAgent Parity Repair Note - 2026-05-27

This note records the current tau3-bench parity work for the portable SAGE agent.
It is experimental engineering evidence, not final claim evidence.

## Question

Can tau3 run with the same SAGE behavior that produced the ToolSandbox 250/500
successes: deterministic helper generation, validation, repair, storage,
routing, natural helper calls, gain/regression tracking, and safe helper-mediated
official tool use?

## Current Answer

Partially yes. The tau3 parity runner now injects SAGE helpers as actual Python
tools through the tau3 tool loop, not just prompt guidance. The latest fresh
20-task option-repair run shows a valid generated-tool-attributed gain and no
valid paired regressions, but it does not reproduce the ToolSandbox-scale lift.
The remaining blocker is stable helper candidate quality and candidate-budget
allocation on harder tau3 action families, not basic helper visibility.

## Repairs Implemented

- Added explicit unsupported-action evidence gating. A generated helper can no
  longer block official host tools or transfer merely because it belongs to an
  unsupported-policy lane; visible task evidence must show that the requested
  action is actually unsupported.
- Removed broad host-tool suppression for incomplete helper outputs. SAGE no
  longer hides the correct host action just because a helper says the arguments
  are not ready yet.
- Added trusted visible-ID guarding. Lookup helpers may not call profile/account
  tools with IDs invented from names or echoed from prior failed assistant calls.
- Added sensitive-action guardrails. Certificate/refund/credit actions now need
  explicit generated-helper authorization with visible policy evidence; otherwise
  SAGE escalates rather than issuing unsupported compensation.
- Added option-selection routing/preflight for visible search-result choice
  tasks. The selection helper is now favored when host search results and
  cheapest/option-selection cues are visible.
- Added import-helper sandbox support for standard deterministic Python idioms
  such as `enumerate`, after accepted helpers passed compile validation but
  failed at runtime in the stricter import execution sandbox.
- Repaired source-record lookup and host-action helper templates so same-flight,
  related-reservation, booking, cancellation, and direct/one-stop flight-search
  cases can produce concrete next host-tool specifications from visible records
  rather than broad policy notes.
- Repaired option-selection helpers so phrases such as "Option 2" and
  "Flight Option 2" resolve to the selected result block and expose the selected
  flight codes/dates for downstream action helpers.

## Prior Positive Run

Run:
`outputs/sage_official_live/tau3_sageagent_guarded_retained20_20260527_01`

Dashboard:
`outputs/sage_official_live/tau3_sageagent_guarded_retained20_20260527_01/dashboard/task_compare.html`

Dashboard data SHA-256:
`50c218f6c0f74eda3f22669118bcf19f63a355b99a441f8121f6486646967cd7`

Results on valid non-infra tasks:

| Metric | Value |
| --- | ---: |
| Valid tasks | 18 |
| Baseline successes | 7 |
| SAGE successes | 9 |
| Generated-tool-attributed gains | 3 |
| Generated-tool-attributed regressions | 1 |
| Infra artifacts | 2 |
| Tools born | 24 |
| Tools accepted | 4 |
| Tools reused | 304 |
| Tools refined | 1 |
| Birth-task retries | 5 |
| Birth-task retry successes | 2 |

Gains:

- `tau3:airline:1`
- `tau3:airline:9`
- `tau3:airline:13`

Regression:

- `tau3:airline:16`

## Interpretation

This is a meaningful improvement over the earlier import-mode runs because gains
are tied to real generated helper calls, not random prompt-only variance. It also
shows that the full SAGE-style tool loop can be integrated into tau3 without
rewriting tau3 around an EnvironmentAdapter.

The result is still not scale-ready. The remaining regression is an action
selection/option grounding issue: the agent can still present or act on an
incorrect visible flight option when search results are complex. The next repair
should make option-selection helpers produce final-action-ready selected flight
arguments and require reservation-change/booking helpers to consume those
selected identifiers before side-effect calls.

## Recommendation

Do not run tau3 40/60/500 yet. First repair the remaining option-selection bridge,
rerun targeted task `tau3:airline:16`, then rerun a 20-task guarded slice. Scale
only when the 20-task slice has positive helper-attributed gains and zero
helper-attributed regressions.

## Latest Fresh Option-Repair Run

Run:
`outputs/sage_official_live/tau3_sageagent_fresh20_option_repair_v6_20260527_01`

Dashboard:
`outputs/sage_official_live/tau3_sageagent_fresh20_option_repair_v6_20260527_01/dashboard/task_compare.html`

Dashboard data SHA-256:
`07a89205e9b4d27991b4ba57d026f6d5c3dc1eea01f6002ca8679005e71a19e8`

Registry SHA-256:
`5db233a4efb5bdc33fbe78a42d773d171547fce2bb5f615a44975c6557e8cc8d`

Results on valid non-infra tasks:

| Metric | Value |
| --- | ---: |
| Total requested tasks | 20 |
| Valid non-infra tasks | 15 |
| Baseline successes | 6 |
| SAGE successes | 8 |
| Net valid lift | +2 tasks |
| Generated-tool-attributed gains | 1 |
| Generated-tool-attributed regressions | 0 |
| Infra artifacts | 5 |
| Tools born | 28 |
| Tools accepted | 17 |
| Tools rejected | 11 |
| Tools reused | 252 |
| Birth-task retries | 7 |
| Birth-task retry successes | 1 |

Gains:

- `tau3:airline:1`: SAGE gain without generated-helper attribution.
- `tau3:airline:13`: SAGE gain with generated-helper attribution
  (`prepare_visible_baggage_entitlement_action_args`).

Valid regressions:

- None.

Infra artifacts:

- `tau3:airline:6`
- `tau3:airline:9`
- `tau3:airline:16`
- `tau3:airline:17`
- `tau3:airline:18`

## Updated Interpretation

The latest result is a cleaner safety/contribution signal than the prior
retained-registry run because it removed the valid generated-tool-attributed
regression. It also confirms that tau3 integration is using real generated
callable helpers: SAGE birthed helpers, validated and accepted them, exposed
them through the host loop, recorded natural helper calls, and produced at least
one paired gain where a generated helper was used.

It is not yet the tau3 analogue of the ToolSandbox 250/500 result. ToolSandbox
success came from repeated medium-grain deterministic helpers that were
final-action-ready and routed into many later tasks. The tau3 fresh run still
generates too many helpers that are visible and called but do not convert hard
failures. The next general repair should improve candidate quality and
candidate-budget allocation: keep generating concrete option selectors,
record/field resolvers, payment allocators, and action-argument preparers, but
retire or refine broad helpers that see repeated called failures without paired
gains.

Decision label:
`PARTIAL_TAU3_SAGEAGENT_PARITY: REAL_CALLABLE_HELPER_GAIN_BUT_NOT_SCALE_READY`.
