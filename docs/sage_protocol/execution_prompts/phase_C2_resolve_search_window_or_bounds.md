# Phase C.2 — resolve_search_window_or_bounds

> **SUPERSEDED — ARCHIVAL EXECUTION PROMPT.** Do not execute these instructions;
> use the current publication protocol in `../current_state.md`.

Objective:
Implement `resolve_search_window_or_bounds` as the next decisive tool.

Purpose:
Prepare bounded search kwargs for reminder/message search tasks from natural time phrases.

Why this is decisive:
It compresses:
`get_current_timestamp -> infer search window -> construct bounds -> avoid no-criteria search -> call search tool`
into:
`resolve_search_window_or_bounds -> original search tool`

Target failures:
- no-criteria search calls
- repeated failed search calls
- `yesterday` / `today` / `later today` / `upcoming` mishandled
- incorrect timestamp bounds
- unnecessary clarification before search
- broad manual retries

Tool must:
- never call search itself
- never create/modify/send anything
- return `target_tool_name` and `search_kwargs`
- preserve downstream original search tool
- abstain if phrase is ambiguous or `current_timestamp` is missing
- avoid no-criteria search calls
- support reminder and message search when feasible

Suggested input:
- `current_timestamp`
- `phrase`
- `target_domain: reminder | message`
- `timestamp_intent: creation | reminder | message_creation`
- `direction: yesterday | today | later_today | upcoming | recent | latest | oldest | custom`
- `content_keyword` optional
- `lookback_days` optional
- `timezone_offset` optional

Suggested output:
- `target_tool_name`
- `search_kwargs`
- `should_call_search`
- `abstain_reason`
- `interpretation`
- `bounds_source`

Tests:
- yesterday reminder creation bounds
- today reminder scheduled bounds
- later_today reminder bounds
- upcoming reminder bounds
- recent/latest message bounds
- content keyword pass-through
- missing `current_timestamp` -> abstain
- ambiguous phrase -> abstain
- unrelated reminder creation/contact/service negatives
- no-criteria search avoided

Replay:
4–8 scenarios:
- yesterday reminders
- upcoming reminders
- later today reminders
- most recent message
- oldest/latest message
- 2 negatives

Focused cohort:
12–20 diverse search-window scenarios across reminder and message search.

Pass gate:
- registry proof PASS
- helper called in relevant positives
- hidden in negatives
- no no-criteria search calls caused by SAGE
- failed search calls decrease
- unnecessary clarification decreases
- outcome_similarity positive
- gains exceed regressions
- side-effect violations = 0
- runtime exceptions = 0

Report:
`docs/sage_protocol/phase_C_resolve_search_window_or_bounds_report.md`

Decision:
- `pass`
- `needs one general repair`
- `suppress/retire candidate`
- `blocked by evaluation or claim-safety issue`
