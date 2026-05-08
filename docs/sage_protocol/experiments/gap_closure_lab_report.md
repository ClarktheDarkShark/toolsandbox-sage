# SAGE Gap-Closure Lab Report

## Status
Blocked preflight report for `exp/sage-gap-closure-lab`. No SAGE gap-closure benchmark runs have been executed yet because the environment lacks live OpenAI credentials.

This report is experimental branch documentation only and is not part of the protected final claim package.

## Setup Completed
- Created an isolated experimental branch from clean commit `28fa525`.
- Added a deterministic split-manifest builder for seed/dev, pilot-unseen, confirm-unseen, and scale-unseen cohorts.
- Added split metadata for label access, allowed uses, disallowed uses, final-evaluation eligibility, expected helper fit, birth opportunities, and diversity summaries.
- Added placeholder ledger and candidate triage reports.
- Added runner-compatible aliases for `pilot_20`, `expanded_60`, `confirm_100`, and `validate_250`.
- Added campaign preflight script and artifact.

## Protected Asset Statement
No protected final evidence, locked registry, locked best3 evidence, locked formal evidence, or final-package claim artifact was modified by this setup.

## Data Leakage Statement
The setup manifest marks truth-label access as allowed only for `seed_dev_labeled`. All unseen splits are marked as truth-label-uninspected. Seed/dev base task families are excluded from unseen splits. Scenario IDs are recorded for auditability and are forbidden in tool, router, prompt, repair, or expected-answer logic.

## Cache Statement
No benchmark cache was used during setup. Future baseline/control arms may use eligible control baseline cache with hash reporting. Future SAGE/candidate arms must be fresh experimental runs unless an arm/tool/registry-specific response-cache key is proved and recorded.

Campaign preflight artifact:

- `artifacts/experiment_manifests/gap_closure_lab/campaign_preflight.json`
- Status: `blocked`
- Blocker: `missing_openai_api_key`
- Manifest file SHA-256: `7843305bfee2e0d021ecd0ab429ea12f88cb381676615079538836c91e9f84c9`
- Payload SHA-256: `41a9565960005007bdcc8a0e901b81a300e2e5c1c52c0b38e15e17fe83f983d4`
- Runner split counts: `pilot_20=20`, `expanded_60=60`, `confirm_100=100`, `validate_250=250`

## Experiment Families
The plan covers the six required families plus the additional actor-policy, router/composer, insufficient-information, final-answer-ready, contrastive generation, leave-family-out, ablation, adaptive repair, synthetic validation, bandit routing, metadata compression, and oracle-free classifier families.

## Current Blockers
Hard blocker: `OPENAI_API_KEY` is not set in this execution environment. ToolSandbox agent/user runs, SAGE tool generation, live validation, natural adoption tests, force-call diagnostics, and fresh candidate arms all require live model calls. Running synthetic or hardwired substitutes would not satisfy the requested fair-chance standard and would risk mislabeling non-SAGE work as SAGE evidence.

## Recommended Next Campaign
1. Provide live model credentials to the environment, preferably by sourcing a local untracked file such as `.secrets/env.sh` or `.env.local` with `OPENAI_API_KEY`.
2. Rerun `PYTHONPATH=src:. python scripts/preflight_gap_closure_campaign.py`.
3. Run seed/dev pain-point analysis on `seed_dev_labeled`.
4. Generate first candidates under `artifacts/registry_experiments/gap_closure_lab/`.
5. Run static/schema/runtime validation before any ToolSandbox run.
6. Run `pilot_20`, then `expanded_60` before parking any non-safety-failed family.
7. Scale only confirmation-positive approaches to `confirm_100` and then `validate_250`.

## Decision
`BLOCKED: missing_openai_api_key_prevents_fair_live_campaign_execution`
