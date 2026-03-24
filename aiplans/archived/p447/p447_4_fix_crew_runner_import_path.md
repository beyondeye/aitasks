---
Task: t447_4_fix_crew_runner_import_path.md
Parent Task: aitasks/t447_add_crew_runner_control_to_brainstorm_tui.md
Sibling Tasks: aitasks/t447/t447_5_disable_runner_buttons_after_press.md
Archived Sibling Plans: aiplans/archived/p447/p447_1_*.md, aiplans/archived/p447/p447_2_*.md, aiplans/archived/p447/p447_3_*.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

## Context

`agentcrew_runner.py` uses package-style imports (`from agentcrew.agentcrew_utils import ...`) but when invoked via `aitask_crew_runner.sh`, Python's sys.path doesn't include `.aitask-scripts/`, causing `ModuleNotFoundError`.

## Plan

### Step 1: Add sys.path setup

In `.aitask-scripts/agentcrew/agentcrew_runner.py`, after stdlib imports and before `from agentcrew.agentcrew_utils import`, add:

```python
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

Same pattern as `agentcrew_runner_control.py:10-11` but using `.parent.parent` for package root.

### Step 2: Verify

```bash
cd .aitask-scripts && python -c "from agentcrew.agentcrew_runner import *; print('OK')"
```

## Final Implementation Notes
- **Actual work done:** Added `from pathlib import Path` and `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` between stdlib imports and package imports in `agentcrew_runner.py`
- **Deviations from plan:** None
- **Issues encountered:** None — straightforward fix
- **Key decisions:** Used `.parent.parent` to reach `.aitask-scripts/` (grandparent of the script file) since the import is package-style (`from agentcrew.xxx`)
- **Notes for sibling tasks:** The runner now starts correctly. User confirmed it launches, identifies agents, and begins processing. t447_5 (button disable) can proceed independently.
