---
Task: t539_unify_agentcrew_package_imports.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Unify agentcrew package-style imports (t539)

## Context

`agentcrew_dashboard.py` and `agentcrew_report.py` import sibling `agentcrew_*` modules with flat `from agentcrew_utils import ...` syntax. This only works because Python auto-prepends the script's directory to `sys.path` when the script is run directly. It's inconsistent with `agentcrew_runner.py` and `agentcrew_status.py` (which use `from agentcrew.agentcrew_utils import ...` after a `sys.path.insert(0, parent.parent)` prelude), and it would break if either script were imported as a module. Task t536 already applied this fix to `agentcrew_status.py`; t539 brings the remaining two scripts in line.

## Reference pattern (from `agentcrew_runner.py` / `agentcrew_status.py`)

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentcrew.agentcrew_utils import (
    ...,
)
```

Note: `parent.parent` — not `parent` — because we want `.aitask-scripts/` on `sys.path` so `import agentcrew` resolves the package directory.

## File 1: `.aitask-scripts/agentcrew/agentcrew_dashboard.py`

Current state (lines 1–46):
- Line 8: `from pathlib import Path` ✅ already present
- Line 11: `sys.path.insert(0, str(Path(__file__).resolve().parent))` ⚠️ uses `parent`, must be `parent.parent`
- Line 13: `from agentcrew_utils import (` → sibling style
- Line 26: `from agentcrew_log_utils import (` → sibling style
- Line 32: `from agentcrew_runner_control import (` → sibling style
- Line 42: `from agentcrew_process_stats import (` → sibling style

Changes:
1. Update line 11 from `parent` to `parent.parent`:
   ```python
   sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
   ```
2. Also drop the `# Ensure agentcrew package is importable` comment's preceding context (keep the comment, it's still accurate).
3. Rewrite the four sibling imports to package-style:
   - `from agentcrew_utils import (` → `from agentcrew.agentcrew_utils import (`
   - `from agentcrew_log_utils import (` → `from agentcrew.agentcrew_log_utils import (`
   - `from agentcrew_runner_control import (` → `from agentcrew.agentcrew_runner_control import (`
   - `from agentcrew_process_stats import (` → `from agentcrew.agentcrew_process_stats import (`

## File 2: `.aitask-scripts/agentcrew/agentcrew_report.py`

Current state (lines 1–22):
- No `pathlib` import
- No `sys.path.insert(...)` prelude
- Line 10: `from agentcrew_utils import (` — only sibling-style import in this file

Changes:
1. Add `from pathlib import Path` to the imports block (after the existing `from datetime import ...`).
2. Add a blank line + `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` before the first agentcrew package import.
3. Rewrite the sibling import:
   - `from agentcrew_utils import (` → `from agentcrew.agentcrew_utils import (`

## Verification

Task description mandates three checks:

```bash
./ait crew dashboard --help   # must run without ModuleNotFoundError
./ait crew report --help      # must run without ModuleNotFoundError
```

Plus a cwd-independence check (both scripts must work when launched from an unrelated directory, same as the t536 regression):

```bash
(cd /tmp && /home/ddt/Work/aitasks/ait crew dashboard --help)
(cd /tmp && /home/ddt/Work/aitasks/ait crew report --help)
```

All four commands must exit 0 with no `ModuleNotFoundError`.

## Step 9: Post-implementation

- No separate branch was created (profile `fast` → `create_worktree: false`), so no merge/worktree-cleanup.
- Run `./.aitask-scripts/aitask_archive.sh 539` to archive the task after user approval.

## Final Implementation Notes

- **Actual work done:** Rewrote sibling-style imports in `agentcrew_dashboard.py` (4 imports: `agentcrew_utils`, `agentcrew_log_utils`, `agentcrew_runner_control`, `agentcrew_process_stats`) and `agentcrew_report.py` (1 import: `agentcrew_utils`) to package-style `from agentcrew.<module> import ...`. Fixed dashboard's existing `sys.path.insert(..., parent)` to `parent.parent`. Added a fresh `from pathlib import Path` + `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` prelude to `agentcrew_report.py`, which previously had neither.
- **Deviations from plan:** None. Changes matched the plan 1:1.
- **Issues encountered:** None.
- **Key decisions:** `agentcrew_dashboard.py` already had a `# Ensure agentcrew package is importable` comment; kept it since the corrected `parent.parent` version matches the comment's intent. No new comment added to `agentcrew_report.py` to keep the prelude consistent with `agentcrew_runner.py` / `agentcrew_status.py`, which also don't have one.
- **Verification:** All four checks passed — `./ait crew dashboard --help` and `./ait crew report --help`, both from repo root and from `/tmp` cwd, exit 0 and print the expected usage banner. No `ModuleNotFoundError`.
