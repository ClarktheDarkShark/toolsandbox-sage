# Gap-Closure Lab Code Reduction Plan

Planning only. Do not execute these reductions until the Praxis result is protected by golden tests and final-hardening review.

## Goal

Reduce experimental branch code size and duplication without changing the Praxis formal500 result. The current priority is preservation, not cleanup.

## Read-Only Size Scan

| Area | Lines | Notes |
| --- | ---: | --- |
| `src/sage_ts/adapters/openai_toolsandbox_roles.py` | 2420 | Actor bridge, routing, policy, and execution-name compatibility are concentrated here. |
| `src/sage_ts/dashboard/exporters.py` | 1840 | Dashboard data extraction, task focus payloads, comparison payloads, and server helpers are in one module. |
| `scripts/run_sage_protocol.py` | 1601 | Orchestration mixes cache planning, run execution, dashboard writing, artifact manifests, and protocol gates. |
| `scripts/build_gap_closure_action_precondition_loop.py` | 1559 | One large campaign builder plus many one-off pack variants. |
| `src/sage_ts/evaluation/control_baseline_cache.py` | 749 | Cache policy is central and should remain explicit. |
| `src/sage_ts/dashboard/task_focus_template.py` | 701 | Static dashboard template. |
| `src/sage_ts/dashboard/task_compare_template.py` | 534 | New comparison-first dashboard template. |
| `scripts/build_gap_closure*.py` | 40 files | Many campaign-specific builders could become declarative specs. |

## Preservation First

Before reducing code, create golden tests around:

- `praxis_formal500_locked_summary.json` metrics and hashes.
- Registry digest preservation before/after runs.
- Per-task control cache eligibility and `500 cached / 0 fresh` formal500 planning.
- Actor bridge behavior on scrambled tool names.
- Final-answer retention after user acknowledgements.
- Search-required/no-op side-effect accounting.
- Task Focus and Task Compare payload shape.

## Reduction Opportunities

1. Split `openai_toolsandbox_roles.py` into:
   - tool exposure and routing policy
   - actor bridge action normalization
   - final-answer retention policy
   - execution-name translation
   - side-effect preservation accounting

2. Replace one-off `build_gap_closure*.py` scripts with declarative pack specs:
   - registry source list
   - included helpers
   - route triggers
   - split source
   - validation command

3. Move protocol-run manifest writing out of `scripts/run_sage_protocol.py`:
   - cache report writer
   - dashboard URL writer
   - gate report writer
   - campaign artifact copier

4. Extract dashboard payload builders:
   - base run payload
   - task focus payload
   - task compare tool summary
   - scenario table rows

5. Consolidate validation commands:
   - registry check
   - schema/runtime smoke
   - side-effect smoke
   - dashboard smoke
   - summary hash creation

6. Archive old exploratory builders and run-only scripts after freezing their artifacts:
   - keep machine-readable manifests and reports
   - move old scripts to a clearly marked legacy directory only after final-hardening review

## Do Not Change During Reduction

- Protected best3/V2.6 reference hashes.
- Frozen Praxis registry contents.
- Per-task control cache rule.
- Candidate/SAGE cache-off policy for evidence runs.
- Actor/router bridge semantics until covered by golden tests.
- Dashboard data fields used by feedback packets and reports.

## Execution Order Later

1. Add golden tests.
2. Extract pure helpers with no behavior changes.
3. Run unit tests and dashboard smoke.
4. Rerun a narrow deterministic smoke, not formal500.
5. Compare output payload hashes where deterministic.
6. Only then consider a formal verification rerun.
