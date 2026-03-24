---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [agentcrew]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-24 10:50
updated_at: 2026-03-24 11:04
---

## Summary

Fix `ait crew runner` command failing with `ModuleNotFoundError: No module named 'agentcrew'`.

## Context

The runner script `.aitask-scripts/agentcrew/agentcrew_runner.py` uses package-style imports (`from agentcrew.agentcrew_utils import ...`) but when invoked via `aitask_crew_runner.sh`, the Python path does not include `.aitask-scripts/`, causing the import to fail.

Discovered during t447_2 (runner UI in brainstorm TUI) — clicking "Start Runner" spawns the process but it exits immediately with the import error.

## Key Files to Modify

- `.aitask-scripts/agentcrew/agentcrew_runner.py` — Add `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` near the top, before the `from agentcrew.agentcrew_utils import` line. This is the same pattern used by `agentcrew_runner_control.py` (which adds the parent dir) but needs the grandparent (`.aitask-scripts/`) for package-style imports.

## Reference Files for Patterns

- `.aitask-scripts/agentcrew/agentcrew_runner_control.py` lines 10-11 — `sys.path.insert` pattern for sibling module imports
- `.aitask-scripts/aitask_crew_runner.sh` line 39 — how the shell wrapper invokes the Python script

## Implementation Plan

### Step 1: Add sys.path setup

In `agentcrew_runner.py`, after the existing imports (line 12) and before line 14 (`from agentcrew.agentcrew_utils import`), add:

```python
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

### Step 2: Verify

```bash
cd /path/to/repo && ait crew runner --crew brainstorm-427 --check
```

Should no longer crash with ModuleNotFoundError.

## Verification Steps

1. Run `ait crew runner --crew <any_crew_id> --dry-run` — should not crash
2. Import test: `cd .aitask-scripts && python -c "import sys; sys.path.insert(0, '.'); from agentcrew.agentcrew_runner import *; print('OK')"`
