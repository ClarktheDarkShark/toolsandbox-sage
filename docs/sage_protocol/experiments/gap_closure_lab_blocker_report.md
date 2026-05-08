# SAGE Gap-Closure Lab Blocker Report

## Decision
`RESOLVED: missing_openai_api_key blocker cleared; campaign executed`

## Scope
Experimental branch `exp/sage-gap-closure-lab`. This report is not protected final claim evidence.

## Root Cause
This was an early setup blocker: the execution environment initially did not expose `OPENAI_API_KEY`.

This blocks fair campaign execution because the required workflow depends on live OpenAI-backed calls for:

- ToolSandbox control-arm agent/user turns.
- SAGE candidate-arm agent/user turns.
- SAGE tool generation and repair through `OpenAIChatAdapter`.
- Live candidate validation, natural adoption, force-call diagnostics, and matched outcome comparisons.

Without credentials, any substitute such as static-only inspection, hardwired tool calls, or a deterministic non-model agent would not have satisfied the requested fair-chance standard and could not have been reported as SAGE campaign evidence.

The blocker was later resolved by sourcing the local untracked environment file. The campaign preflight now reports `status: ready`, and the live campaign results are recorded in:

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
The local environment was repaired and the campaign was executed through fair-chance diagnostics, expanded pilots, repair loops, and reporting. This blocker report remains for audit history only.

## Protected Asset Statement
No protected best3 registry, locked formal evidence, locked best3 evidence, V2.6 locked evidence, or final-package claim artifact was modified.
