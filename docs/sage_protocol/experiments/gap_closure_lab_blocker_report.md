# SAGE Gap-Closure Lab Blocker Report

## Decision
`BLOCKED: missing_openai_api_key_prevents_fair_live_campaign_execution`

## Scope
Experimental branch `exp/sage-gap-closure-lab`. This report is not protected final claim evidence.

## Root Cause
The current execution environment does not expose `OPENAI_API_KEY`.

This blocks fair campaign execution because the required workflow depends on live OpenAI-backed calls for:

- ToolSandbox control-arm agent/user turns.
- SAGE candidate-arm agent/user turns.
- SAGE tool generation and repair through `OpenAIChatAdapter`.
- Live candidate validation, natural adoption, force-call diagnostics, and matched outcome comparisons.

Without credentials, any substitute such as static-only inspection, hardwired tool calls, or a deterministic non-model agent would not satisfy the requested fair-chance standard and could not be reported as SAGE campaign evidence.

## Exact Evidence
Machine-readable preflight:

- `artifacts/experiment_manifests/gap_closure_lab/campaign_preflight.json`
- Status: `blocked`
- Blockers: `missing_openai_api_key`
- Manifest hash check: pass
- Payload hash check: pass
- Runner split aliases: pass
- Runner split counts: `pilot_20=20`, `expanded_60=60`, `confirm_100=100`, `validate_250=250`

Credential check:

- Environment variable `OPENAI_API_KEY`: absent
- Direct OpenAI client instantiation fails with: `OpenAIError: The api_key client option must be set either by passing api_key to the client or by setting the OPENAI_API_KEY environment variable`

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

## Smallest Next Repair
Expose a valid `OPENAI_API_KEY` to the shell environment used by Codex, then rerun:

```bash
PYTHONPATH=src:. python scripts/preflight_gap_closure_campaign.py
```

If preflight returns `ready`, start the live campaign with `pilot_20` and generation enabled, keeping all registries and reports under the gap-closure lab experimental paths.

## Protected Asset Statement
No protected best3 registry, locked formal evidence, locked best3 evidence, V2.6 locked evidence, or final-package claim artifact was modified.
