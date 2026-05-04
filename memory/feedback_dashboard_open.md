---
name: Always open dashboards after runs
description: Do not suppress dashboard opening after protocol runs; user wants dashboards visible
type: feedback
---

Do not pass `--no-dashboard-open` to `run_sage_protocol.py`. After each run completes, export dashboard data and open both `index.html` and `task_focus.html` via `open_dashboard`.

**Why:** User explicitly requested that runs open dashboards.

**How to apply:** Remove `--no-dashboard-open` from run commands. After the run script exits, call `scripts/export_dashboard_data.py --protocol-run-root <run_dir>` and then `open_dashboard` for both dashboard pages.
