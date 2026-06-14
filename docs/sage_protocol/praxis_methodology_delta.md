# Praxis Methodology Delta

Status: non-claim methodology supplement. This file preserves the original
registry-only final-hardening interpretation and adds the later combined-policy
methodology boundary.

## Current Combined-Policy Boundary

After the registry-only safety repair, the project restored the general Praxis
actor/checker bridge policy as a first-class SAGE component. The high-lift
Praxis candidate should now be described as a combined treatment when
`SAGE_PRAXIS_BRIDGE_POLICY=combined` is enabled:

- frozen Praxis helper registry;
- bounded helper routing;
- general actor bridge policy for natural helper adoption, scalar arguments,
  final-answer retention, and original ToolSandbox side-effect preservation;
- side-effect checker support using execution trace events plus
  conversation-visible assistant tool calls.

This is not cheating if it is stated transparently. It is not force calling,
does not inspect labels or expected answers, does not select scenarios, and
does not change the scorer. It is a runtime treatment component that must be
included in matched validation and documented in Chapter 3.

Protected-claim language must therefore distinguish:

- registry-only Praxis repair v2: clean safety, positive formal500 outcome,
  lower canonical lift than the prior high-lift run;
- Praxis combined treatment: under validation, intended to recover high
  natural-adoption lift by restoring the bridge policy as part of SAGE.

See `docs/sage_protocol/praxis_bridge_policy_methodology.md`.

## Original Registry-Only Review Context

Praxis did not validate cleanly in the first registry-only review because the
frozen experimental registry produced helper side-effect preservation failures.

## What Praxis Tested

Praxis was tested as a frozen candidate registry copied from the experimental
gap-closure branch. The formal500 review intentionally isolated registry value
by using the protected-base final-hardening runtime and not importing the
experimental actor/router bridge policy or side-effect checker changes.

The result should be described as:

- registry-only outcome lift reproduced under protected-base runtime;
- not protected-claim ready because safety failed;
- possible future combined registry plus actor/router bridge treatment, but
  only if separately audited and validated.

## Matched-Arm Controls

All formal review arms shared:

- identical formal manifest and scenario order;
- identical agent/user model settings;
- identical base tool policy;
- generation off;
- OpenAI response cache disabled;
- candidate task cache off;
- same control-cache policy and cache manifest/hash;
- routing evidence disabled;
- no diagnostic force-call environment variables;
- no code or registry changes between arms.

## Cache Policy

The review branch used task-level control-baseline caching only for baseline
controls. Cache eligibility required the same task name, agent model, user
model, and base tool policy, with at least three valid completed control
records. Candidate/SAGE arms remained fresh.

Controls were cached for all 500 tasks in all arms. Chapter 3 should therefore
separate run-vs-control lift from candidate-vs-candidate comparisons and state
the cache manifest hash:
`00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`.

## Routing Policy

Routing evidence was disabled for formal review runs. Existing retained-tool
visibility still uses registry metadata and scenario names as part of the
current SAGE runtime. That behavior was shared across best3, V2.6, and Praxis
in the initial matched set and should be described as a runtime routing
dependency, not hidden-label access.

## Safety Policy

Side-effecting original ToolSandbox calls remain authoritative. Generated tools
must be side-effect-free helpers unless the original ToolSandbox tool performs
the side effect. Side-effect preservation reports, helper runtime incidents,
runtime exceptions, and failed helper calls must be included in the locked
analysis.

Praxis failed this policy in registry-only form with 13 helper side-effect
preservation failures. That failure blocks protected-claim promotion even though
the outcome lift was positive.

## Force-Call Exclusion

Diagnostic force-call paths were prohibited in final-hardening evidence runs.
Preflight failed if diagnostic force-call environment variables were active.
Force-call diagnostics can explain earlier experimental development but cannot
count as promotion evidence.

## Statistical Plan And Result

Outcome/task completion was primary. Canonical/reference and exact success were
secondary. The locked report includes paired differences, gain/regression
counts, paired bootstrap intervals, permutation/randomization tests, helper
visibility/call/VNC summaries, and a conservative cache statement.

Praxis-vs-best3 showed a positive paired outcome difference with a positive
bootstrap interval. Praxis-vs-V2.6 was positive in mean outcome but the interval
crossed zero. Canonical/reference behavior was mixed.

## Limitations And Non-Claims

- Praxis is not final protected evidence.
- No protected final-claim update is recommended from this review.
- Registry-only value must not be claimed as protected-claim ready because the
  safety gate failed.
- Cached controls reduce cost but do not create fresh baseline traces for every
  task.
- Scenario-name-based routing is a current runtime dependency and should be
  reported transparently.

## Future Methodology Option

If a future review imports actor/router bridge or side-effect checker changes,
the method must label Praxis as a combined treatment, audit those code paths for
leakage, rerun preflight, and rerun the full matched formal validation from
scratch with zero helper side-effect incidents.
