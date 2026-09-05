---
name: Always open dashboards after runs
description: Do not suppress dashboard opening after protocol runs; user wants dashboards visible
type: feedback
---

Use the canonical publication launcher for every live run. It must generate and
serve the run's `dashboard/task_compare.html`, verify the served root and bytes,
and open that exact Task Compare page in the external/default browser before
the first model request.

**Why:** User explicitly requested that runs open dashboards.

**How to apply:** Run through `scripts/run_native_action_4omini_ab.sh` (or the
guarded Make targets that invoke it) and preserve its dashboard-launch receipt.
