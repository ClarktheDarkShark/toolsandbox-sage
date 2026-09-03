# SAGE Regression Restore Report - 2026-06-23

## Issue

The post-cleanup full validation run did not preserve the prior best SAGE outcome level. The best retained full run remains:

- Run: `outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410`
- Score: `0.733214 -> 0.801186`, delta `+0.067971`
- Outcome: `0.454251 -> 0.757267`, delta `+0.303016`
- Exact successes: `201 -> 406`
- Runtime exceptions: `0`

The failed post-cleanup full validation was:

- Run: `outputs/production_full_validation/v062_post_cleanup_full_20260622_194951/online_build_full_20260622_194956`
- Score: `0.692499 -> 0.792812`, delta `+0.100313`
- Outcome: `0.494012 -> 0.753378`, delta `+0.259366`
- Exact successes: `98 -> 376`
- Runtime exceptions: `0`

The post-cleanup run retained positive lift, but it lost outcome quality relative to v061 and introduced more side-effect preservation incidents.

## Root Cause

The regression was caused by the production cleanup replacing the validated `sage_ts` runtime path with a trimmed `sage_research` runtime path. The trimmed path removed substantial generated-tool actor guidance and call-path handoff behavior while leaving the run flags superficially similar.

The removed behavior included generated-tool usage guidance, generated-tool continuation choice, action-argument handoff guidance, lookup/selection tool handoff, contact/reminder/location policy support, and other actor-facing scaffolding that helped the model use generated tools correctly without synthetic bridge completions.

This matches the observed failure pattern: generated tools were still born and called, but SAGE lost outcome quality and produced more side-effect preservation incidents.

## Restoration

The tracked production files were restored from the committed validated product:

- `scripts/run_sage_protocol.py`
- `src/sage_ts/**`
- `tests/**`
- `pyproject.toml`

The trimmed replacement package was removed:

- `src/sage_research/`
- `src/sage_ts/generation/chat.py`

After restoration, `src/sage_ts`, `scripts`, `tests`, and `pyproject.toml` have no diff against the committed production product, aside from unrelated untracked figure-rendering scripts.

## Validation Completed

Local validation passed:

- `git diff --check -- scripts/run_sage_protocol.py src/sage_ts`
- `python -m py_compile scripts/run_sage_protocol.py src/sage_ts/adapters/openai_toolsandbox_roles.py src/sage_ts/runtime/toolsandbox_integration.py src/sage_ts/adapters/sage_run_adapter.py`
- `PYTHONPATH=src:. pytest tests/unit/test_rapid_api_cache.py -q`
- `PYTHONPATH=src:. pytest tests/unit/test_openai_toolsandbox_roles.py tests/unit/test_sage_run_adapter.py tests/unit/test_tool_generator.py tests/unit/test_generated_tool_lifecycle.py tests/unit/test_self_evolution_reflection.py -q`
- `PYTHONPATH=src:. pytest tests/integration/test_toolsandbox_generated_tool_injection.py tests/unit/test_toolsandbox_adapter.py tests/unit/test_protocol_generation_policy.py tests/unit/test_online_birth.py tests/unit/test_candidate_gate.py -q`

Results:

- Rapid API cache tests: `2 passed`
- SAGE lifecycle/adapter/generator/reflection tests: `234 passed`
- Generated-tool injection and policy tests: `150 passed`

## Fresh Run Blocker

A targeted 30-task validation run was attempted after restoration, but every candidate row failed with `APIConnectionError` before any meaningful actor execution. The local shell can load `OPENAI_API_KEY` from `../Hey_Alfredv2/.env`, but DNS lookup for `api.openai.com` currently fails with `socket.gaierror`.

That targeted run is therefore invalid as a SAGE performance measurement. It measured API/network unavailability, not restored SAGE behavior.

## Current State

The production SAGE implementation has been restored to the validated `sage_ts` path. A new API-backed 20/60/full validation should be run once the OpenAI network path is available.
