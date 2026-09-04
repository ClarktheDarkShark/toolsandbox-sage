# Phase C.3 — reminder optional-location handling

> **SUPERSEDED — ARCHIVAL EXECUTION PROMPT.** Do not execute these instructions;
> use the current publication protocol in `../current_state.md`.

Objective:
Upgrade the reminder helper lane only where it creates decisive value.

Starting point:
`prepare_reminder_creation_args` is kept from Phase B.

Decision:
Either:
- extend `prepare_reminder_creation_args` only if the extension stays narrow, or
- create companion helper `handle_optional_location_for_reminder` if cleaner.

Do not create a broad workflow macro.
