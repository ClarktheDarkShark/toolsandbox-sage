# Praxis Treatment Dependency Audit

Status: review setup complete; matched validation pending.

This is a final-hardening review artifact only. It does not modify protected
best3 evidence, locked formal evidence, final-package claim artifacts, or the
protected best3 registry.

## Branch Lineage

- Review branch: `review/praxis-final-hardening`
- Base commit: `2898c7e502ec75ad5e1fc65c5ffe7a80f5605f4a`
- Experimental source commit: `7793c8ca29ab4e121d302c777c4e4ad273226470`
- Lineage manifest: `artifacts/praxis_final_hardening/lineage_manifest.json`

## Imported Review Inputs

| Input | Review path | SHA-256 |
| --- | --- | --- |
| best3 reference copy | `artifacts/praxis_final_hardening/registries/best3_reference/registry_manifest.json` | `76de726d25f7f959744704d18a5cf69ff807ca3e3daa7616876e5699ce783caf` |
| V2.6 reference copy | `artifacts/praxis_final_hardening/registries/v2_6_reference/registry_manifest.json` | `ab5f5c369717ce4a5bf0d0a7262a4f44f7f13bab1bf69eb38041392986b0e582` |
| Praxis frozen candidate | `artifacts/praxis_final_hardening/registries/praxis_bridgepack_frozen_candidate/registry_manifest.json` | `7867cde8c8709f31efb02006e8c0743bbf890f2ede1519de99155e4631614349` |
| Locked experimental summary | `artifacts/praxis_final_hardening/source_summaries/praxis_formal500_locked_summary.json` | `41db7fed0e0997cfb691791abca59d47941a2f076951153382b17df3242e2dcc` |

The review branch also imports the task-level control-baseline cache policy from
the experimental source. This is a cache/harness dependency, not a candidate
tool treatment. It is control-arm-only, requires at least three valid completed
control records per task, and matches on task name, agent model, user model, and
base tool policy.

## Intentionally Not Imported For Initial Validation

- Experimental `scripts/run_sage_protocol.py` changes. The experimental diff
  removes final-hardening safeguards that already exist on the protected base,
  including explicit routing-evidence controls and diagnostic-force checks.
- Experimental actor/router bridge policy in
  `src/sage_ts/adapters/openai_toolsandbox_roles.py`. The first matched
  validation tests registry-only value under the final-hardening runtime. If
  Praxis does not reproduce as registry-only, a second audited import may test
  the combined registry plus bridge-policy treatment.
- Experimental scoring changes in `src/sage_ts/evaluation/outcome_score.py`.
- Experimental routing-scorer changes that weaken or remove mtime/routing
  evidence safeguards.
- Experimental dashboard/export changes, unless later imported as reporting-only
  artifacts after validation code is frozen.

## Diff Audit Findings

- Praxis registry contents: 13 generated tools, including best3/V2.6 inherited
  tools plus recency, scheduling, device-state, send-message precondition, and
  contact bridge helpers.
- Actor/router bridge changes exist in the experimental source. They add
  domain-specific actor policy text, scrambled tool-name compatibility, device
  state bridge completions, CRUD bridge behavior, and final-response retention
  behavior. These are not present in the initial review branch treatment.
- Side-effect preservation checker changes exist in the experimental source,
  mostly around trace-based follow-up validation and selection-only bridges.
  These are not imported for the initial registry-only validation.
- Cache/scoring changes: the review branch imports only the task-level
  control-cache change. Candidate/SAGE task caching remains off for evidence
  arms; OpenAI response cache must be disabled.
- Routing evidence: final validation uses `--routing-evidence-mode disabled`.
  No mtime-selected routing evidence is allowed.
- Diagnostic force-call path: preflight fails when diagnostic force-call env vars
  are active. No force-call flags are used in formal review runs.

## Leakage Review

The frozen registries contain provenance fields such as `birth_scenario` and
task-family labels. The runtime uses scenario names for existing retained-tool
visibility heuristics in the same way for best3, V2.6, and Praxis. This is not
truth-label or expected-answer access, but it is recorded as a routing
dependency and limitation. No tool code was found to contain expected answers,
hidden truth labels, or prior SAGE trace outcomes. The formal comparison will
use the same frozen manifest and scenario order for all arms, with no scenario
selection based on cache availability.

## Current Treatment Classification Before Runs

The initial review treatment is:

1. Frozen registry under review.
2. Existing final-hardening runtime from the protected base.
3. Imported control-arm-only task-level baseline cache policy.
4. No imported Praxis actor/router bridge policy.

If the frozen registry does not reproduce under this treatment, the next review
step is an explicitly separated registry-plus-bridge-policy ablation.
