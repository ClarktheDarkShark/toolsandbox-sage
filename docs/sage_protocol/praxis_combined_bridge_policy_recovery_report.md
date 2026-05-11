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

## Results

| Run | N | Control canonical | SAGE canonical | Canonical delta | Relative canonical lift | Control outcome | SAGE outcome | Outcome delta | Relative outcome lift | Natural tool-call scenarios | Runtime / helper failures |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Formal order broad60 | 60 | 0.695 | 0.782 | +0.087 | +12.5% | 0.606 | 0.751 | +0.145 | +24.0% | 26 | 0 / 0 helper runtime; 1 old checker row |
| Formal order 61-100 holdout40 | 40 | 0.592 | 0.618 | +0.026 | +4.4% | 0.599 | 0.763 | +0.164 | +27.3% | 15 | 0 / 0 |
| Disjoint first100 aggregate | 100 | 0.654 | 0.716 | +0.063 | +9.6% | 0.603 | 0.756 | +0.153 | +25.3% | 41 | 0 / see safety note |

The broad60 slice recovered the earlier high canonical-lift band. The disjoint holdout40 confirmed strong outcome lift but only modest canonical/reference lift. Across the first 100 formal-order tasks, the treatment remains close to the previous high canonical range and substantially stronger on outcome/task completion.

## Safety Note

The broad60 run was started before the setter-`None` actor-policy repair and trace-checker fallback. It emitted one side-effect preservation row for `plan_device_state_action_sequence_v3` on `cellular_off`. Autopsy showed the original setter had already succeeded and returned `None`; the agent misread `None` as failure and retried. The trace checker also missed the conversation-visible retry error.

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

The holdout40 run after this repair had zero side-effect preservation rows.

## Dashboard

Task Compare is now the default dashboard for future runs. It includes run-level baseline score, SAGE score, score lift, baseline outcome, SAGE outcome, outcome lift, and a clickable generated-tool contribution panel.

- Latest holdout Task Compare: `http://127.0.0.1:62514/outputs/praxis_combined_bridge_policy/formal500_order_061_100_broad40/mechanism_40_20260511_102941/dashboard/task_compare.html`
- Broad60 Task Compare: `http://127.0.0.1:62512/outputs/praxis_combined_bridge_policy/formal500_order_broad60/mechanism_60_20260511_101421/dashboard/task_compare.html`

## Interpretation

The best integrity-preserving way back toward the earlier high lift is not force-calling tools. It is to label Praxis honestly as a combined treatment and make the actor policy better at naturally adopting high-value helpers while preserving original ToolSandbox side effects.

The strongest current signal is outcome lift. Canonical lift is mixed: positive and near the previous high-lift level in the first 100 aggregate, but variable by slice. Peer-review language should state that canonical/reference matching remains secondary and that some outcome-preserving cases score lower canonically because the route or final phrasing differs from the benchmark reference.

## Next Validation Step

Run a clean same-code formal100 or formal500 only after this patch set is committed:

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
