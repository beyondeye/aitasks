---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [crew]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-17 12:59
updated_at: 2026-03-17 13:00
---

# Fix crew script permissions and add missing help text

## Problem
Two `ait crew` scripts are missing the executable permission bit, causing "Permission denied" errors:
- `.aitask-scripts/aitask_crew_init.sh` — `-rw-r--r--` (should be `-rwxr-xr-x`)
- `.aitask-scripts/aitask_crew_addwork.sh` — `-rw-r--r--` (should be `-rwxr-xr-x`)

## Required Changes

### 1. Fix file permissions
Add execute permission to:
- `aitask_crew_init.sh`
- `aitask_crew_addwork.sh`

### 2. Add --help support to crew subcommands missing it
These subcommands have no `--help|-h` handler:
- `aitask_crew_runner.sh`
- `aitask_crew_status.sh`
- `aitask_crew_report.sh`
- `aitask_crew_dashboard.sh`

Add basic usage/help text matching the pattern used in `aitask_crew_command.sh` and `aitask_crew_cleanup.sh`.

### 3. Handle bare `ait crew` (no subcommand)
When `ait crew` is run with no subcommand, show the available subcommands list instead of an error about "unknown subcommand ''".
