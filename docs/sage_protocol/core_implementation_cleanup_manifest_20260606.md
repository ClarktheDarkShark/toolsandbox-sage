# SAGE Core Implementation Cleanup Manifest

> **SUPERSEDED — ARCHIVAL CLEANUP MANIFEST.** The retained-source list below
> describes an earlier tree and is not the current release inventory. See
> [current_state.md](current_state.md).

Date: 2026-06-14.

## Purpose

This cleanup narrows the active codebase to the native ToolSandbox SAGE Praxis
implementation used for Chapter 3 methodology and full-dataset evidence. The
goal is a smaller, auditable implementation while retaining the evidence
boundary required for the praxis:

- autonomous tool generation;
- validation and repair;
- registry retention;
- routing and reuse;
- same-task availability of accepted generated tools without SAGE-only extra
  retry turns;
- tool-specific actor guidance when generated tools are visible;
- contribution and safety logging;
- Task Compare evidence export.

Synthetic bridge completions and route-around policies remain outside the
primary evidence boundary. Primary runs should use:

```bash
SAGE_PRAXIS_BRIDGE_POLICY=disabled
SAGE_SCENARIO_METADATA_POLICY=visible_context
SAGE_DISABLE_SCENARIO_NAME_BIRTH=1
SAGE_DISABLE_SCENARIO_NAME_ROUTING=1
```

## Retained Runtime Surface

The retained active implementation is:

- `scripts/run_sage_protocol.py`
- whole-dataset preflight launcher (removed from the publication release)
- `scripts/render_chapter3_sage_figures.py`
- `src/sage_ts/adapters/`
- `src/sage_ts/adequacy/`
- `src/sage_ts/cache/`
- `src/sage_ts/config/`
- `src/sage_ts/dashboard/`
- `src/sage_ts/evaluation/`
- `src/sage_ts/generation/`
- `src/sage_ts/registry/`
- `src/sage_ts/runtime/`
- `src/sage_ts/validation/`
- `tool_sandbox/`
- retained `tests/unit/` and `tests/integration/` coverage for the active path.

The package configuration now installs `tool_sandbox*` and `sage_ts*` only.

## Removed Runtime Surface

The cleanup removes active runtime code for experiment paths that are not part
of the current primary Chapter 3 implementation:

- standalone/import-agent SAGE package: `src/sage_agent/`;
- standalone/import-agent smoke and audit scripts;
- CyberGym live-run scripts;
- tau parity/prototype scripts;
- older v2 campaign/matrix/feedback-packet scripts;
- static registration scripts for one-off generated tools;
- old campaign orchestration modules;
- toy mechanism modules and tests;
- tests whose only purpose was to validate removed experiment paths.
- rejected token-reduction scaffolds that altered actor-facing transcripts or
  pruned original ToolSandbox schemas after v061 was selected as canonical.

Historical reports and methodology handoffs under `docs/sage_protocol/` remain
available as future-work context. They are not active runtime code.

## Behavior-Preserving Cleanup Notes

The cleanup intentionally avoids changing the evidence method. The retained
path still runs paired ToolSandbox control/SAGE tasks, generates tools during
SAGE execution, validates accepted tools, records reuse/calls/failures, and
exports Task Compare dashboards.

One narrow accounting fix was kept in `src/sage_ts/adapters/sage_run_adapter.py`:
when a generated tool call fails, that failed tool name is removed from the
successful generated-tool-called set for that scenario. This keeps called and
failed generated-tool counts mutually exclusive in contribution metrics. It does
not add benchmark answers, synthetic completions, or route-around behavior.

## Validation Completed

Post-cleanup structural validation:

```bash
make compile
```

Result: passed.

Focused retained-path validation:

```bash
make test-core
```

Result: `360 passed, 4 warnings`.

Full retained local test sweep:

```bash
make test
```

Result: `514 passed, 4 warnings`.

Stale-reference scan across active docs/config/scripts/tests/package:

```bash
rg -n 'sage_agent|run_sage_agent_smoke|run_cybergym|run_tau3|run_sage_official_live|run_sage_transfer|run_sage_online|self_evolving_campaign|toy_mechanism|feedback_packets|campaign_splits' README.md Makefile pyproject.toml tests scripts src/sage_ts docs/sage_protocol/current_state.md
```

Result: no matches.

## Evidence Status

The cleanup did not rerun the full ToolSandbox sample because that is an
expensive evidence run, not a code-cleanup smoke check. The canonical preserved
full-dataset evidence is v061:

- run:
  `outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410`
- score: `0.733214 -> 0.801186`, lift `+9.27%`;
- outcome: `0.454251 -> 0.757267`, lift `+66.71%`;
- accepted tools: `22`;
- called accepted tools: `21`;
- tool reuse events: `1171`;
- generated-tool-called scenarios: `825`;
- generated-tool failed scenarios: `3`;
- runtime exceptions: `0`.

The v061 configuration is now the SAGE publication boundary. The next
exact-success validation should be a deliberate full ToolSandbox evidence run
using the retained runner and the same bridge-disabled, scenario-name-free
configuration.

## Reproduction Commands

Fast validation:

```bash
make compile
make test-core
make test
```

Full-dataset evidence run:

```bash
make full
```

The preserved v061 protocol manifest remains available at:

```bash
outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410/protocol_manifest.json
```
