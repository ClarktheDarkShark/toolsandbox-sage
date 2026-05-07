# V2.6 Feedback Mode Experiment Report

## Objective
Compare the practical value of existing feedback versus enriched structured feedback for future tool generation.

## Modes Compared
- Mode A: existing shortfall/contribution evidence.
- Mode B: enriched structured feedback packets with trace summaries, helper calls, missing deterministic step, no-current-helper-fit, safety incidents, route decisions, and sufficiency flags.
- Mode C: execution-aware feedback from live candidate validation and micro-runs when available.
- Mode D: repair feedback from rejection reasons, force-call results, and repair category when available.

## Evidence
- Mode A was enough to discover the contact pack, but it did not reliably explain why smaller runs looked better than 250 or why insufficient-information tools could be harmful even when called.
- Mode B reduced feedback-insufficient share to `0.0%` on both V2.6 contact rerun100 packet sets and preserved the formal 100/250/500/1032 no-fit distribution for cross-run atlas work.
- Mode B captured actual helper arguments/outputs and route decisions needed to diagnose VNC/adoption issues.
- Mode C/D fields are now represented when artifacts contain them, but no new controlled generation run has yet shown that they beat Mode B for candidate birth.

## Result
Use Mode B as the default V2.6 tool-birth context. Add Mode C/D details opportunistically after each micro-run or force-call diagnostic.

## Decision Label
`feedback mode B wins`

## Exact Next Action
Generate cross-task abstraction packets from Mode B packets, then use Mode C/D details only for candidate repair and callability validation.
