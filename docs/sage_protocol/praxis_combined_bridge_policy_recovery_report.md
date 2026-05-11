# Praxis Combined Bridge-Policy Recovery Report

Status: experimental repair/recovery result, not protected final evidence.

## Treatment

This campaign tested the frozen Praxis BridgePack registry with an explicit feature-flagged bridge policy:

- Registry: `artifacts/praxis_safety_repair/registries/praxis_bridgepack_combined_bridge_policy_v1/registry_manifest.json`
- Registry SHA-256: `7867cde8c8709f31efb02006e8c0743bbf890f2ede1519de99155e4631614349`
- Runtime flag: `SAGE_PRAXIS_BRIDGE_POLICY=combined`
- Routing evidence: disabled
- Generation: off
- Candidate task cache: off
- OpenAI response cache: disabled
- Control cache: `use-if-eligible`
- Diagnostic force calls: absent

This should be described as a registry plus actor/checker bridge-policy treatment, not a registry-only result.

Plain-English interpretation: the retained tools were present before, but the
actor needed general SAGE operating rules to know when helper output should be
used, when the original ToolSandbox side-effect tool still had to be called,
and how to retain a final answer after helper-assisted work. Restoring that
policy is methodologically valid if it is part of the declared treatment and is
validated under matched conditions. It is not a force-call path and does not
use labels, expected answers, benchmark facts, or task selection.

## Results

| Run | N | Control canonical | SAGE canonical | Canonical delta | Relative canonical lift | Control outcome | SAGE outcome | Outcome delta | Relative outcome lift | Natural tool-call scenarios | Runtime / helper failures |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Formal order broad60 v2 policy-repair | 60 | 0.695 | 0.751 | +0.056 | +8.0% | 0.606 | 0.783 | +0.177 | +29.2% | 24 | 0 / 0 |
| Formal order 61-100 holdout40 v2 policy-repair | 40 | 0.592 | 0.681 | +0.089 | +15.1% | 0.599 | 0.656 | +0.057 | +9.4% | 15 | 0 / 0 |
| Disjoint first100 v2 same-code aggregate | 100 | 0.654 | 0.723 | +0.069 | +10.6% | 0.604 | 0.737 | +0.133 | +22.0% | 39 | 0 / 0 |

The repaired broad60 slice gives the strongest outcome signal so far. The repaired holdout40 gives strong canonical/reference lift but weaker outcome lift; it failed the local protocol gate only because outcome delta was below `0.08` and the outcome gain/regression ratio was below `1.4`. Across the first 100 formal-order tasks, the same-code aggregate is back above the prior 10% canonical-lift band while preserving a large outcome/task-completion lift.

Machine-readable aggregate: `artifacts/praxis_combined_bridge_policy/summary/praxis_combined_bridge_policy_first100_v2_same_code_summary.json`, SHA-256 `fd279d109437c4bc361595efb8b52efdfe4b2c83829dbe1ec5017e54260d6ae3`.

## Safety Note

An earlier pre-repair broad60 run emitted one side-effect preservation row for `plan_device_state_action_sequence_v3` on `cellular_off`. Autopsy showed the original setter had already succeeded and returned `None`; the agent misread `None` as failure and retried. The trace checker also missed the conversation-visible retry error. That pre-repair run is no longer the primary evidence row above.

Repairs made:

- Actor policy now states that `None` from original state setters means success and should not trigger a retry or planning helper.
- Side-effect preservation checker now falls back to conversation-visible assistant tool calls when low-level trace rows omit failed original tool attempts.

Post-repair diagnostic:

- `cellular_off_safety1`, N=1
- SAGE canonical: 0.937
- SAGE outcome: 1.000
- Natural generated-tool calls: 0
- Runtime exceptions: 0
- Side-effect preservation rows: 0

The v2 broad60 and v2 holdout40 same-code runs after this repair had zero side-effect preservation rows.

## Dashboard

Task Compare is now the default dashboard for future runs. It is dark mode and includes run progress, total task count, paired completion count, baseline completed count, SAGE completed count, run-level baseline score, SAGE score, score lift, baseline outcome, SAGE outcome, outcome lift, and a clickable generated-tool contribution panel.

- Latest holdout Task Compare: `http://127.0.0.1:62518/outputs/praxis_combined_bridge_policy/formal500_order_061_100_broad40_v2_policy_repair/mechanism_40_20260511_115212/dashboard/task_compare.html`
- Broad60 Task Compare: `http://127.0.0.1:62517/outputs/praxis_combined_bridge_policy/formal500_order_broad60_v2_policy_repair/mechanism_60_20260511_113538/dashboard/task_compare.html`

## Interpretation

The best integrity-preserving way back toward the earlier high lift is not force-calling tools. It is to label Praxis honestly as a combined treatment and make the actor policy better at naturally adopting high-value helpers while preserving original ToolSandbox side effects.

The strongest current signal remains outcome lift. Canonical lift is now also back in the earlier high-lift range on the first100 aggregate, but still varies by slice. Peer-review language should state that canonical/reference matching remains secondary and that some outcome-preserving cases score lower canonically because the route or final phrasing differs from the benchmark reference.

## Next Validation Step

Run a clean same-code formal500 only after this patch set is committed:

- same frozen registry hash
- `SAGE_PRAXIS_BRIDGE_POLICY=combined`
- generation off
- candidate cache off
- OpenAI response cache disabled
- control cache `use-if-eligible`
- routing evidence disabled
- no diagnostic force env vars
- Task Compare default dashboard

Protected-claim promotion still requires a clean matched formal500 with zero side-effect rows.

## Validation Checks

- Registry hashes:
  - best3 reference copy: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
  - V2.6 reference copy: `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`
  - Praxis combined BridgePack: `7867cde8c8709f31efb02006e8c0743bbf890f2ede1519de99155e4631614349`
- Registry validation: `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only ...` -> `PASS`, 22 active entries pass.
- Focused tests: `conda run -n lifelong bash -lc 'export PYTHONPATH=src:.; python -m pytest tests/unit/test_openai_toolsandbox_roles.py tests/unit/test_openai_selector_actor_policy.py tests/unit/test_role_factory.py tests/unit/test_dashboard_exporters.py tests/unit/test_run_metrics.py'` -> `35 passed, 2 warnings`.
- Syntax checks: `python -m py_compile` on the modified run script, role policy, and dashboard modules -> `PASS`.
- Dashboard browser check: Task Compare opened at the latest holdout URL with `Run Progress 40/40`, dark mode, and zero console errors.
- `git diff --check` -> `PASS`.

## Methodology Artifacts

- Chapter 3 update: `docs/sage_protocol/chapter3_methodology_prep.md`
- Dedicated bridge-policy note:
  `docs/sage_protocol/praxis_bridge_policy_methodology.md`
- Versioned heuristic entry:
  `docs/sage_protocol/protocol_heuristics_v1.json`
