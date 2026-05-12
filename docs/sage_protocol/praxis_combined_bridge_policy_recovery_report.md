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
- External RapidAPI cache for quota-limited review gates:
  `TOOLSANDBOX_RAPID_CACHE_MODE=read_only`,
  `TOOLSANDBOX_RAPID_CACHE_PATH=.secrets/rapid_api_cache.json`, SHA-256
  `3ed7732443c44d7d26e0f46ac32fa2e09fc773278368c6f13131021afafdbf25`

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
| Gap12 v3 bridge repair + RapidAPI read-only cache | 12 | 0.644 | 0.886 | +0.242 | +37.6% | 0.348 | 0.869 | +0.520 | +149.3% | 11 | 0 / 0 |
| Formal order broad60 v4 bridge repair + RapidAPI read-only cache | 60 | 0.695 | 0.821 | +0.126 | +18.1% | 0.606 | 0.916 | +0.310 | +51.2% | 27 | 0 / 0 |
| Formal order first100 v3 bridge repair + RapidAPI read-only cache | 100 | 0.654 | 0.786 | +0.133 | +20.3% | 0.604 | 0.877 | +0.273 | +45.3% | 47 | 0 / 0 |
| Formal order first250 v2 bridge repair + RapidAPI read-only cache | 250 | 0.679 | 0.759 | +0.080 | +11.8% | 0.624 | 0.837 | +0.213 | +34.2% | 111 | 0 / 0 |
| Formal500 v2 bridge repair + RapidAPI read-only cache + Polars single-thread guard | 500 | 0.670 | 0.757 | +0.087 | +13.0% | 0.595 | 0.840 | +0.245 | +41.2% | 230 | 0 / 0 |

The repaired broad60 slice gives the strongest outcome signal so far. The repaired holdout40 gives strong canonical/reference lift but weaker outcome lift; it failed the local protocol gate only because outcome delta was below `0.08` and the outcome gain/regression ratio was below `1.4`. Across the first 100 formal-order tasks, the same-code aggregate is back above the prior 10% canonical-lift band while preserving a large outcome/task-completion lift.

Machine-readable first100 aggregate: `artifacts/praxis_combined_bridge_policy/summary/praxis_combined_bridge_policy_first100_v2_same_code_summary.json`, SHA-256 `fd279d109437c4bc361595efb8b52efdfe4b2c83829dbe1ec5017e54260d6ae3`.

Machine-readable latest broad60 gate: `artifacts/praxis_combined_bridge_policy/summary/praxis_combined_bridge_policy_broad60_v4_bridge_repair_rapid_cache_summary.json`, SHA-256 `c58b45cd67f5b6ff714f3f7569fc3c5e71752880e763eedebdd54abf9f89ea07`.

Machine-readable formal500 gate: `artifacts/praxis_combined_bridge_policy/summary/praxis_combined_bridge_policy_formal500_v2_bridge_repair_rapid_cache_polars1_summary.json`, SHA-256 `060d3ba14ae1b8b8d15290d8286092a68053347fd207e46ade89c5fba0cc61e6`.

Machine-readable formal500 statistics: `artifacts/praxis_combined_bridge_policy/summary/praxis_combined_bridge_policy_formal500_v2_statistics.json`, SHA-256 `e064e9f3cec303d2a657063132549e8cfda2fdb1a946e0405649449ca21ddf6f`.

Latest validated recovery runs:

- Gap12 v3:
  `outputs/praxis_combined_bridge_policy/bridge_recovery_gap12_v3_bridge_repair_rapid_cache/mechanism_12_20260511_164415`
- Broad60 v4:
  `outputs/praxis_combined_bridge_policy/formal500_order_broad60_v4_bridge_repair_rapid_cache/mechanism_60_20260511_164637`
- Formal500 v2:
  `outputs/praxis_combined_bridge_policy/formal500_full_v2_bridge_repair_rapid_cache_polars1/full_benchmark_20260511_190013`
- Task Compare dashboard:
  `http://127.0.0.1:62543/outputs/praxis_combined_bridge_policy/formal500_full_v2_bridge_repair_rapid_cache_polars1/full_benchmark_20260511_190013/dashboard/task_compare.html`

The v4 broad60 result exceeds the earlier high Praxis formal500 run on the same
60 tasks: prior high same-60 canonical lift was `+9.3%` and outcome lift was
`+46.4%`; v4 produced canonical lift `+18.1%` and outcome lift `+51.2%`.

The v2 formal500 run also exceeds the prior high dashboard cited during review:
prior `0.670 -> 0.751` canonical (`+0.081`, `+12.1%`) and `0.595 -> 0.813`
outcome (`+0.219`); v2 formal500 produced `0.670 -> 0.757` canonical
(`+0.087`, `+13.0%`) and `0.595 -> 0.840` outcome (`+0.245`, `+41.2%`
relative outcome lift).

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

- Latest Formal500 v2 Task Compare: `http://127.0.0.1:62543/outputs/praxis_combined_bridge_policy/formal500_full_v2_bridge_repair_rapid_cache_polars1/full_benchmark_20260511_190013/dashboard/task_compare.html`
- Latest Broad60 v4 Task Compare: `http://127.0.0.1:62538/outputs/praxis_combined_bridge_policy/formal500_order_broad60_v4_bridge_repair_rapid_cache/mechanism_60_20260511_164637/dashboard/task_compare.html`
- Latest holdout Task Compare: `http://127.0.0.1:62518/outputs/praxis_combined_bridge_policy/formal500_order_061_100_broad40_v2_policy_repair/mechanism_40_20260511_115212/dashboard/task_compare.html`

## Interpretation

The best integrity-preserving way back toward the earlier high lift is not force-calling tools. It is to label Praxis honestly as a combined treatment and make the actor policy better at naturally adopting high-value helpers while preserving original ToolSandbox side effects.

The strongest current signal remains outcome lift. Canonical lift is now also
back above the earlier high-lift range on the latest broad60 gate, but still
varies by slice. Peer-review language should state that canonical/reference
matching remains secondary and that some outcome-preserving cases score lower
canonically because the route or final phrasing differs from the benchmark
reference.

## Next Validation Step

The combined treatment has now passed a clean formal500 run-vs-control gate with
zero runtime exceptions, zero helper failures, and zero side-effect incidents.
It is still not a protected final-claim update, because it is not a
registry-only treatment and the best3/V2.6 ablation arms were not rerun in the
same no-code-change transaction after the combined policy was restored.

The next protected-review spend should be a dedicated matched ablation
transaction:

- best3 reference under the current committed runtime
- V2.6 reference under the current committed runtime
- Praxis registry-only repair v2 under the current committed runtime
- Praxis combined bridge-policy v2 under the current committed runtime

All arms should use the same formal500 manifest, cached controls where eligible,
fresh candidate arms, generation off, OpenAI response cache disabled, routing
evidence disabled or pinned, and no diagnostic force env vars.

When ready, run the next clean ablation or confirmation gate with:

- same frozen registry hash
- `SAGE_PRAXIS_BRIDGE_POLICY=combined`
- generation off
- candidate cache off
- OpenAI response cache disabled
- control cache `use-if-eligible`
- routing evidence disabled
- RapidAPI cache read-only when external-service tasks are in scope
- no diagnostic force env vars
- Task Compare default dashboard

Protected-claim promotion still requires a locked matched formal500 ablation
with zero side-effect rows and a clear combined-treatment claim, not a
registry-only claim.

## Validation Checks

- Registry hashes:
  - best3 reference copy: `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf`
  - V2.6 reference copy: `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582`
  - Praxis combined BridgePack: `7867cde8c8709f31efb02006e8c0743bbf890f2ede1519de99155e4631614349`
- Registry validation: `PYTHONPATH=src:. python scripts/migrate_registry.py --check-only ...` -> `PASS`, 13 active entries pass.
- Focused tests: `PYTHONPATH=src:. python -m pytest tests/unit/test_role_factory.py tests/unit/test_openai_toolsandbox_roles.py tests/unit/test_openai_selector_actor_policy.py tests/unit/test_rapid_api_cache.py -q` -> `35 passed, 2 warnings`.
- RapidAPI cache smoke: `env -u RAPID_API_KEY TOOLSANDBOX_RAPID_CACHE_MODE=read_only TOOLSANDBOX_RAPID_CACHE_PATH=.secrets/rapid_api_cache.json PYTHONPATH=src:. python -c ... search_location_around_lat_lon('Whole Foods on Stevens Creek')` -> returned `Whole Foods Market, 20955 Stevens Creek Blvd, Cupertino, CA 95014`.
- Syntax checks: `python -m py_compile` on the modified run script, role policy, and dashboard modules -> `PASS`.
- Dashboard artifact check: the latest broad60 run records `dashboard_url` as `task_compare.html`, `default_dashboard=task_compare`, and `task_compare_data.json` reports `scenario_count=60`.
- Formal500 dashboard browser check: Task Compare opened at the formal500 URL with title `Task Compare - SAGE`, showed `500/500`, `+13.0%` score lift, and `+41.2%` outcome lift, with zero console errors.
- Formal500 side-effect/failure artifact check: no side-effect, failure, or incident artifacts were emitted under the formal500 run root; Task Compare `tool_summary.side_effect_incident_count=0`.
- `git diff --check` -> `PASS`.

## Methodology Artifacts

- Chapter 3 update: `docs/sage_protocol/chapter3_methodology_prep.md`
- Dedicated bridge-policy note:
  `docs/sage_protocol/praxis_bridge_policy_methodology.md`
- Versioned heuristic entry:
  `docs/sage_protocol/protocol_heuristics_v1.json`
