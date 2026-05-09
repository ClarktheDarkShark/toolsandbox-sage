# SAGE Gap-Closure Lab Blocker Report

## Decision
`BLOCKED_FOR_FORMAL_VALIDATION: missing_openai_api_key blocker cleared; clean confirmation/scale data exhausted`

## Scope
Experimental branch `exp/sage-gap-closure-lab`. This report is not protected final claim evidence.

## Root Cause
This report now records two blockers:

1. The early setup blocker: the execution environment initially did not expose `OPENAI_API_KEY`.
2. The current formal-validation blocker: the campaign found a promising day-distance portfolio, but clean confirmation100/scale250 data is exhausted in this branch.

This blocks fair campaign execution because the required workflow depends on live OpenAI-backed calls for:

- ToolSandbox control-arm agent/user turns.
- SAGE candidate-arm agent/user turns.
- SAGE tool generation and repair through `OpenAIChatAdapter`.
- Live candidate validation, natural adoption, force-call diagnostics, and matched outcome comparisons.

Without credentials, any substitute such as static-only inspection, hardwired tool calls, or a deterministic non-model agent would not have satisfied the requested fair-chance standard and could not have been reported as SAGE campaign evidence.

The credential blocker was later resolved by sourcing the local untracked environment file. During the postscale continuation, the key was available as a local untracked `OPENAI_KEY` value and mapped to `OPENAI_API_KEY` for live run processes. The secret value was not recorded.

The formal-validation blocker remains. Postscale fresh residual data is low-quality and near-duplicate dominated after the expanded60 runs. The older postrepair confirm100/validate250 splits have been inspected and used for repair/backtest decisions, so additional runs on them are dev backtests, not clean promotion evidence. The control-cache planner also showed that running those larger splits would not be resource-efficient:

- postrepair confirm100: 0 cached / 100 fresh controls under the three-compatible-controls rule.
- postrepair validate250: 0 cached / 250 fresh controls under the same rule.

The campaign preflight reports and live campaign results are recorded in:

- `docs/sage_protocol/experiments/gap_closure_lab_report.md`
- `docs/sage_protocol/experiments/gap_closure_lab_ledger.md`
- `artifacts/experiment_manifests/gap_closure_lab/campaign_run_summary.json`

## Exact Evidence
Machine-readable preflight:

- `artifacts/experiment_manifests/gap_closure_lab/campaign_preflight.json`
- Status: `ready`
- Blockers: none
- Manifest hash check: pass
- Payload hash check: pass
- Runner split aliases: pass
- Runner split counts: `pilot_20=20`, `expanded_60=60`, `confirm_100=100`, `validate_250=250`

Credential check:

- Environment variable `OPENAI_API_KEY`: present after sourcing local untracked secrets
- Direct OpenAI-backed ToolSandbox/SAGE calls completed during the campaign

## Files Involved
- `src/sage_ts/adapters/openai_agent_adapter.py`: creates the SAGE generation client with `OpenAI(base_url="https://api.openai.com/v1")`.
- `tool_sandbox/roles/openai_api_agent.py`: OpenAI-backed ToolSandbox agent role requires an API key.
- `tool_sandbox/roles/openai_api_user.py`: OpenAI-backed ToolSandbox user role requires an API key.
- `scripts/run_sage_protocol.py`: paired control/candidate runner depends on those roles and on `OpenAIChatAdapter` when generation is enabled.
- `scripts/preflight_gap_closure_campaign.py`: added to fail early and record this blocker before expensive or partial runs.

## Repairs Completed Before Blocking
- Added runner-compatible split aliases in the gap-closure manifest.
- Added `pilot_20` and `expanded_60` protocol modes.
- Updated split loading to support alias resolution and `scenario_id` rows.
- Added a campaign preflight script.
- Regenerated the split manifest with an expanded 60-task pilot.

## Resolution
The local environment was repaired and the campaign was executed through fair-chance diagnostics, expanded pilots, repair loops, and reporting.

The clean-data blocker is not resolved in this branch. The smallest next repair is to create a new frozen, uninspected confirmation100 split with adequate family diversity, run the retained `days_between_timestamps`/recency-time portfolio with no code changes between matched arms, and scale to a fresh 250 only if confirmation is positive with natural calls and zero incidents.

## Protected Asset Statement
No protected best3 registry, locked formal evidence, locked best3 evidence, V2.6 locked evidence, or final-package claim artifact was modified.
