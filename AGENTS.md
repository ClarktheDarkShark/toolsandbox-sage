# AGENTS.md: Orchestration Guide for Scheduled & Remote Agents

This file contains guidance for background and scheduled agents executing SAGE phases or recurring tasks.

## 1. Phase Execution for Remote Agents

- Remote agents can execute an entire phase if provided with the phase protocol file (`docs/sage_protocol/<phase_N>_*.md`).
- Include the phase file in the agent's context.
- Agent must read and acknowledge the global working agreement (`docs/sage_protocol/00_global_working_agreement.md`) before proceeding.
- Agent must verify all entry conditions before starting work (e.g., prior phase report complete).

## 2. Scheduled Tasks (Recurring)

If a task is scheduled to run on a cadence (e.g., "check registry health weekly"):

- Define the task as a cron entry or `schedule` skill call.
- Include the command to run (e.g., `python scripts/migrate_registry.py --check-only`).
- Log output to a file (e.g., `artifacts/weekly_registry_health_<date>.log`).
- If health check fails, escalate to human review (do not auto-patch).

Example:
```bash
# Weekly registry health check
schedule --cron "0 9 * * 1" \
  --prompt "Run registry health check and report blockers"
```

## 3. Dashboard Availability

- After each phase run, dashboard is available at `outputs/<run_id>/dashboard.html`.
- Remote agents can parse the run manifest to extract dashboard URL:
  ```bash
  python -c "
  import json
  manifest = json.load(open('outputs/<run_id>/manifest.json'))
  print(manifest['dashboard_url'])
  "
  ```
- Verify the dashboard exists and contains expected data (scores, routes, transcripts).

## 4. Registry Lock and Promotion

- The active registry is locked when a phase run is in progress.
- Lock file: `artifacts/registry_lock.json` (contains timestamp, process ID, phase).
- Remote agents must check the lock before modifying the registry:
  ```bash
  python -c "
  import json
  try:
    lock = json.load(open('artifacts/registry_lock.json'))
    print(f'Registry locked by {lock[\"process_id\"]} in phase {lock[\"phase\"]}')
  except FileNotFoundError:
    print('Registry unlocked')
  "
  ```
- If locked, wait or skip the modification; do not force.

## 5. Report Writing and Approval

- After a phase completes, the agent writes the phase report to `docs/sage_protocol/<phase_N>_completion_report.md`.
- The report must include a clear **decision label** at the end:
  - `READY_FOR_PHASE_<N+1>`
  - `BLOCKED: <specific reason>`
  - `NEEDS_REVISION: <specific change>`
- Human review is required before proceeding to the next phase.

## 6. Error Handling

- If a command fails (e.g., test, registry check, run export), capture stderr and stdout.
- Log the failure to `artifacts/<phase>_errors_<timestamp>.log`.
- Escalate to human review; do not auto-retry silently.

## 7. Artifact Preservation

- All phase outputs (runs, reports, logs) must be preserved in `artifacts/` or `outputs/`.
- Do not delete or overwrite prior phase artifacts.
- Use timestamped directories to avoid collisions: `outputs/phase_<N>_<timestamp>/`.

## 8. Communication

- After each task, output a summary to stdout (human-readable).
- Example:
  ```
  Phase A Baseline Control Run
  ============================
  Status: SUCCESS
  Canonical score: 78.3%
  Final-task success: 62.5%
  Dashboard: outputs/phase_A_baseline_control_20260502_123456/dashboard.html

  Report: docs/sage_protocol/phase_A_completion_report.md
  Decision: READY_FOR_PHASE_B

  Next step: Human review and approval
  ```

---

**Last updated:** 2026-05-02
**Scope:** Scheduled agents, remote orchestration, phase automation
