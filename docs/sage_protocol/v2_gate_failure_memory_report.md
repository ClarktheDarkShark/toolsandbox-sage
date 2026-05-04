# V2 Gate, Failure Memory, and Promotion Audit Report

## Objective
Audit whether candidate gating and failure memory can prevent invalid, idle, or harmful tools from becoming claim-grade runtime tools.

## Current Strengths
- Candidate gate rejects many unsafe/thin specs.
- Registry validation requires held-out checks, negative applicability where applicable, runtime smoke pass, code hash verification, and current gate pass.
- Failure memory artifact is mechanism-level rather than name-only.
- Recent gate repair rejected invalid service/contact candidates instead of promoting them.

## Remaining Gaps
- Registry lifecycle roles are not first-class schema fields. Candidate, active, and frozen are mostly path conventions.
- Failure memory is not mechanically consulted by generation, gating, or promotion.
- Promotion does not yet require later-task adoption evidence, called-subset contribution, visible-not-called acceptability, or unresolved-harm clearance.
- Diagnostic candidates can still be proof-passing; the system needs a separate promotion gate to keep them out of claim registries until adoption/value evidence exists.

## Repair Completed In This Audit
- Generated specs now include `diagnostic_only`, `shortfall_cluster_evidence`, and `known_failure_mechanisms_addressed`.
- Candidate gate now rejects decisive non-diagnostic specs missing cluster/failure-mechanism evidence.

## Required Next Repair
Implement a promotion evidence gate that reads candidate-run summaries and failure memory before a tool can move from candidate registry to active/frozen registry.

Minimum promotion requirements:
- validation proof pass
- diagnostic_only false or diagnostic promoted only after later evidence
- safe abstention/negative applicability
- no side-effect/runtime harm
- actual calls in later tasks
- positive or neutral-positive called-subset contribution
- acceptable visible-not-called behavior
- no active unresolved failure-memory mechanism

## Decision Label
gating needs repair
