# Praxis Methodology Delta

Status: draft for final-hardening review.

This supplement prepares Chapter 3 material only if Praxis validates cleanly.
It does not state a protected claim.

## What Praxis Tests

Praxis is currently under review as a frozen candidate registry copied from the
experimental gap-closure branch. The first validation isolates registry value by
using the protected-base final-hardening runtime and not importing the
experimental actor/router bridge policy.

If a later ablation imports the actor/router bridge policy, the methodology must
describe Praxis as a combined registry plus actor/router bridge treatment.

## Matched-Arm Controls

All formal review arms must share:

- identical formal manifest and scenario order;
- identical agent/user model settings;
- identical base tool policy;
- generation off;
- OpenAI response cache disabled;
- candidate task cache off;
- same control-cache policy and cache manifest/hash;
- same routing-evidence policy;
- no diagnostic force-call environment variables;
- no code or registry changes between arms.

## Cache Policy

The review branch uses task-level control-baseline caching only for baseline
controls. Cache eligibility requires the same task name, agent model, user
model, and base tool policy, with at least three valid completed control
records. Candidate/SAGE arms remain fresh.

This cache policy can affect run-vs-control lift estimates, so Chapter 3 should
separate candidate-vs-candidate comparisons from run-vs-control comparisons and
state the cache manifest/hash used.

## Routing Policy

Routing evidence is disabled for formal review runs. Existing retained-tool
visibility still uses registry metadata and scenario names as part of the
current SAGE runtime. That behavior is shared across best3, V2.6, and Praxis in
the initial matched set and should be described as a runtime routing dependency,
not hidden-label access.

## Safety Policy

Side-effecting original ToolSandbox calls remain authoritative. Generated tools
must be side-effect-free helpers unless the original ToolSandbox tool performs
the side effect. Side-effect preservation reports, helper runtime incidents,
runtime exceptions, and failed helper calls must be included in the locked
analysis.

## Force-Call Exclusion

Diagnostic force-call paths are prohibited in final-hardening evidence runs.
Preflight fails if diagnostic force-call environment variables are active.
Force-call diagnostics can explain earlier experimental development but cannot
count as promotion evidence.

## Statistical Plan

Outcome/task completion is primary. Canonical/reference and exact success are
secondary. The locked report should include paired differences, gain/regression
counts, paired bootstrap intervals, permutation/randomization tests, helper
visibility/call/VNC summaries, called-subset contribution, route mismatch
accounting, and a conservative cache statement.

## Limitations And Non-Claims

- Praxis is not final protected evidence until this review completes.
- Registry-only value must not be claimed if branch-only bridge policy is
  required to reproduce the result.
- Cached controls reduce cost but do not create fresh baseline traces for every
  task.
- Scenario-name-based routing is a current runtime dependency and should be
  reported transparently.
- The development assistant is not SAGE. SAGE is the research system being
  evaluated.
