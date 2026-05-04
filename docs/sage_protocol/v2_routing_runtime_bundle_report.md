# V2 Routing and Runtime Bundle Audit Report

## Objective
Audit whether runtime exposure can support a broader candidate library without exposing every helper or relying on manual tool-name routes.

## Current Strengths
- Runtime logs visible, called, visible-not-called, failed-attempt states.
- Active helpers can be hidden on many negatives.
- Trigger-based visibility fallback exists.

## Remaining Gaps
- `toolsandbox_integration.py` still contains many tool-name-specific routing branches.
- Some visibility decisions are tied to scenario-name tokens rather than task-state or generic trigger matching.
- A larger candidate library would likely require generic scoring/routing to avoid context pollution.
- Accepted-but-uncalled service candidate evidence shows adoption/routing remains a core bottleneck.

## Highest-Priority Issue
Move routing toward a bounded generic relevance scorer using spec fields:
- positive triggers
- negative triggers
- applicable task families
- preserved downstream tools
- required input availability
- context budget

Hardcoded tool-name branches should become compatibility overrides, not the primary routing mechanism.

## Decision Label
runtime bundle needs repair
