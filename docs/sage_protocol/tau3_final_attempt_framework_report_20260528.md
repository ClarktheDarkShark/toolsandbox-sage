# tau3 Final-Attempt Framework Report - 2026-05-28

This note records the final tau3 portability attempt for the standalone SAGE
agent. It is experimental engineering evidence, not protected claim evidence.

## Objective

Replicate the ToolSandbox SAGE behavior on tau3: identify deterministic gaps,
generate real Python helper tools, validate and repair them, store them in the
registry, route them into later tasks, execute them through the host tool loop,
track generated-tool gains/regressions, and avoid counting stochastic LLM
variance as SAGE lift.

## Framework Changes Tested

- Added confirmation-aware action bridging: a later "yes/proceed" can authorize
  a generated helper action when recent user turns establish the action class.
- Allowed direct execution of safe read-only helper actions such as record
  lookups when their purpose is to resolve missing visible state before a risky
  write.
- Hardened generated helper input mining so helper outputs do not become future
  record IDs. Record IDs are now mined from user-visible user/tool state, not
  SAGE helper/action-review text.
- Tightened import-mode routing so transfer/escalation helpers require explicit
  transfer or unsupported-action evidence.
- Tightened policy-guard routing so policy helpers require actual
  cancellation/refund or side-effect policy context.
- Added a positive route floor so SAGE may expose no helper when the current
  context does not strongly match any retained helper.

These are intended as general SAGE framework repairs, not tau3-specific task
solutions.

## Runs

| Run | Sample Reached | Baseline | SAGE | Net | Generated Tool Use | Direct Helper Actions | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `tau3_sageagent_replay_helpers20_v12_state_replay_policy_lookup_20260528_01` | 4 | 3 | 1 | -2 | 84 reused | 0 | stopped: early regressions |
| `tau3_sageagent_replay_helpers20_v13_recent_confirm_direct_20260528_01` | 4 | 3 | 4 | +1 | 5 calls | 0 | stopped: unsafe helper-output ID mining |
| `tau3_sageagent_replay_helpers20_v14_readonly_direct_guard_20260528_01` | 5 | 4 | 5 | +1 | 8 calls | 2 | stopped: unsafe helper-output ID mining persisted |
| `tau3_sageagent_replay_helpers20_v15_safe_direct_lookup_20260528_01` | 7 | 6 | 5 | -1 | 30 calls | 2 | stopped: policy helper parsed helper-result text as state |
| `tau3_sageagent_manual_prototype20_v1_20260528_01` | 4 | 3 | 3 | 0 | 10 calls | 0 | stopped: manual helpers introduced a regression |
| `tau3_sageagent_replay_helpers20_v16_routing_safe_direct_20260528_01` | 4 | 3 | 2 | -1 | 18 calls | 0 | stopped: over-routed baggage helper regression |
| `tau3_sageagent_replay_helpers20_v17_positive_route_floor_20260528_01` | 3 | 2 | 1 | -1 | 14 calls | 0 | stopped: route floor did not recover stable lift |

The best complete recent tau3 run remains
`tau3_sageagent_replay_helpers20_v4_bounded_20260528_01`: 20 tasks, baseline
8/20, SAGE 9/20, three SAGE gains, two regressions. That was not stable enough
to scale to 40/100.

## Finding

The final attempt did not produce a scale-ready tau3 result. The blocker is no
longer "SAGE cannot create or expose tools." It can create, accept, route, call,
and in v14 directly execute host actions from generated helper outputs. The
blocker is that tau3's long host-owned dialogue loop is highly sensitive to
helper exposure. Weakly matched helpers perturb the actor before producing
enough deterministic wins.

The most important framework bug found and repaired was stale helper-output
leakage: generated helper outputs were entering later helper inputs as `tool:`
messages and could be re-mined as visible records. The fix is general and should
remain. The second important repair was route abstention: the router should be
allowed to expose no helper when all candidates are poor contextual matches.

## Recommendation

Do not run tau3 40/100/500 yet. The next tau3 attempt should not add more broad
policy/action helpers. It should implement a host-action integration boundary
that is closer to the successful ToolSandbox bridge:

1. Shadow newly accepted helpers until they either drive a same-task retry win
   or pass replay validation on the exact failure turn.
2. Treat helper execution as a gated action-review layer, not as extra prompt
   noise for every turn.
3. Promote only causally useful helpers: baseline failed, SAGE succeeded, helper
   was called or bridged, and the helper output directly constrained the
   successful host action or final response.
4. Quarantine any helper after a helper-attributed regression until repaired on
   a replay case.
5. Add replay validation around host-owned dialogues: execute the helper on the
   transcript slice before the failed action and verify the exact next action,
   abstain decision, or read-only lookup.

This is the general missing piece for tau3-like benchmarks. ToolSandbox works
because the bridge is tight enough that generated tools become deterministic
control points. tau3 import/parity mode is closer, but still lets helpers
influence the dialogue too broadly before they are proven useful.

## Validation Performed

- `PYTHONPATH=src python -m py_compile src/sage_agent/import_agent.py src/sage_agent/generators.py scripts/run_tau3_sageagent_parity.py`
- `PYTHONPATH=src:. pytest tests/unit/test_sage_agent_standalone.py -q`
  - `80 passed`

No 40/100 tau3 run was launched because no 20-task probe met the gate of
positive generated-helper-attributed lift with zero helper-attributed
regressions.

Decision label:
`TAU3_NOT_SCALE_READY: FRAMEWORK_REPAIRS_IDENTIFIED_AND_PARTIALLY_IMPLEMENTED`
