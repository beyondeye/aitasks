---
Task: t976_remove_dead_find_terminal_in_agent_utils.md
Worktree: (current branch — profile 'fast')
Branch: (current branch — profile 'fast')
Base branch: main
---

# Plan: Remove dead `find_terminal()` from codebrowser/agent_utils.py (t976)

## Context

t976 was spawned from t974 (Step 8b review). While tracing every
terminal-spawn site during t974, the diagnosis found that
`.aitask-scripts/codebrowser/agent_utils.py::find_terminal()` is a stale
duplicate of `agent_launch_utils.find_terminal`. Both codebrowser consumers
(`codebrowser_app.py`, `history_screen.py`) import `find_terminal` (aliased
`_find_terminal`) from `agent_launch_utils`, not from the local module. The
local copy has no importers — it is dead code.

The goal is to delete the dead function (and its now-orphaned imports) while
keeping `resolve_agent_binary`, which is still imported by both consumers.

## Verification of the diagnostic (done during planning)

- `grep -rn "agent_utils import.*find_terminal\|agent_utils.find_terminal\|_find_terminal" .aitask-scripts/`
  → all `_find_terminal` references resolve to `from agent_launch_utils import find_terminal as _find_terminal`
  (`codebrowser_app.py:32`, `history_screen.py:12`); call sites at
  `codebrowser_app.py:1424,1502` and `history_screen.py:455`.
- `grep -rn "from agent_utils import\|import agent_utils" .aitask-scripts/ tests/`
  → only `from agent_utils import resolve_agent_binary`
  (`codebrowser_app.py:54`, `history_screen.py:414`). Nothing imports the
  local `find_terminal`.
- Within `agent_utils.py`, the `os` and `shutil` imports are used **only** by
  `find_terminal()`. `resolve_agent_binary()` uses `subprocess` and `Path`.
  So removing the function orphans `import os` and `import shutil`.

## Implementation

Single file: `.aitask-scripts/codebrowser/agent_utils.py`

1. Delete the `find_terminal()` function (lines 9–21, plus the trailing blank
   line separating it from `resolve_agent_binary`).
2. Delete the now-unused `import os` and `import shutil` lines (lines 3–4).
   Keep `import subprocess` and `from pathlib import Path`.

Resulting file header becomes:
```python
"""Shared utilities for launching code agents from TUI screens."""

import subprocess
from pathlib import Path


def resolve_agent_binary(
    ...
```

No other files change — no consumer imports the removed symbol.

## Verification

- `grep -rn "find_terminal" .aitask-scripts/codebrowser/agent_utils.py`
  → no matches (function gone).
- `grep -rn "agent_utils import.*find_terminal\|agent_utils.find_terminal" .aitask-scripts/ tests/`
  → no matches (no importers, confirming nothing broke).
- Compile check: `python3 -m py_compile .aitask-scripts/codebrowser/agent_utils.py`.
- Import smoke-check from the codebrowser dir:
  `cd .aitask-scripts/codebrowser && python3 -c "import agent_utils; agent_utils.resolve_agent_binary"`
  (confirms the surviving symbol still imports cleanly).
- `pyflakes`/lint, if available, reports no unused-import warnings for the file.

## Risk

### Code-health risk: low
- Pure dead-code deletion with zero importers; surviving symbol untouched and
  re-verified by grep. · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- Task is fully specified (remove `find_terminal`, keep `resolve_agent_binary`);
  diagnostic re-confirmed by grep during planning. · severity: low · → mitigation: none needed

## Post-Implementation (Step 9)

Work is on the current branch (profile 'fast'), so no worktree/merge cleanup.
Archive via `./.aitask-scripts/aitask_archive.sh 976` after commit/review.
