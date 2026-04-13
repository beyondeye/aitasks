---
Task: t536_interactive_agent_agentcrew_import_error.md
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
---

# Plan: Fix agentcrew_status.py package import from any cwd (t536)

## Context

When an interactive agent inside a brainstorm crew (e.g. `detailer_001` in
`brainstorm-427`) calls `./ait crew status ...`, the Python script fails with:

```
ModuleNotFoundError: No module named 'agentcrew'
```

The error is at `.aitask-scripts/agentcrew/agentcrew_status.py:15`:

```python
from agentcrew.agentcrew_utils import (...)
```

### Root cause (verified)

`from agentcrew.agentcrew_utils import ...` requires `.aitask-scripts/` to be
on `sys.path` so that the `agentcrew/` directory is discoverable as a package
(it has `__init__.py`). When Python runs `python3 .aitask-scripts/agentcrew/agentcrew_status.py`,
it adds only the *script's* directory (`.aitask-scripts/agentcrew/`) to
`sys.path[0]`, not its parent. Result: `import agentcrew` fails no matter what
the cwd is.

I verified this directly: `./ait crew status --crew foo list` fails identically
when run from the repo root, from `/`, and from a temp directory. The task
description speculated "running from repo root happens to work", but that's not
accurate — `--help` exits in the bash wrapper before Python runs, which may
have masked the issue during casual testing. Anything that reaches the Python
script fails.

### Why only `agentcrew_status.py` is broken

Of the four agentcrew scripts invoked via shell wrappers:

| Script | Import style | Status |
|---|---|---|
| `agentcrew_runner.py` | `from agentcrew.agentcrew_utils import ...` | **Already has** `sys.path.insert(0, parent)` at line 16 |
| `agentcrew_status.py` | `from agentcrew.agentcrew_utils import ...` | **Broken — missing sys.path fix** |
| `agentcrew_dashboard.py` | `from agentcrew_utils import ...` (sibling-style) | Works — script dir is auto-added |
| `agentcrew_report.py` | `from agentcrew_utils import ...` (sibling-style) | Works — script dir is auto-added |

The fix is to mirror the pattern already in `agentcrew_runner.py:16`.

## Approach

**Option chosen: sys.path insert in the Python script** (not PYTHONPATH in the
bash wrapper).

Why:
- Matches the pattern already used in `agentcrew_runner.py:16` — consistency.
- Localized to the file that has the problem.
- Works regardless of how the script is invoked (wrapper, direct `python3`, or
  subprocess).

Alternative considered: `export PYTHONPATH="$SCRIPT_DIR"` in
`aitask_crew_status.sh`. Rejected because it would introduce a second,
inconsistent fix style and wouldn't help if the script were ever invoked
directly (e.g. during debugging).

## Changes

### 0. Create follow-up refactor task (before committing the fix)

The user requested a follow-up task to refactor `agentcrew_dashboard.py` and
`agentcrew_report.py` so their imports are consistent with
`agentcrew_runner.py` and the fixed `agentcrew_status.py`.

Create via batch mode (draft, then finalize+commit):

```bash
./.aitask-scripts/aitask_create.sh --batch \
  --name "unify_agentcrew_package_imports" \
  --type refactor \
  --priority low \
  --effort low \
  --labels "agentcrew" \
  --desc-file - --commit <<'EOF'
Refactor agentcrew_dashboard.py and agentcrew_report.py to use the package-style
import pattern (`from agentcrew.agentcrew_utils import ...` with a
`sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` prelude) for
consistency with agentcrew_runner.py and agentcrew_status.py.

Context: t536 fixed a ModuleNotFoundError in agentcrew_status.py by adding the
sys.path insert that agentcrew_runner.py already uses. agentcrew_dashboard.py
and agentcrew_report.py currently use sibling-style imports
(`from agentcrew_utils import ...`), which only work because Python auto-adds
the script's directory to sys.path when the script is launched directly. These
work today but are inconsistent with the rest of the package and fragile if the
scripts are ever imported as modules.

Files to update:
- .aitask-scripts/agentcrew/agentcrew_dashboard.py
- .aitask-scripts/agentcrew/agentcrew_report.py

For each file:
- Add `from pathlib import Path` to imports
- Add `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` before
  the first agentcrew package import
- Change `from agentcrew_utils import ...` to `from agentcrew.agentcrew_utils import ...`
- Any other sibling-style imports of agentcrew_* modules: change to
  `from agentcrew.agentcrew_<name> import ...`

Verification:
- ./ait crew dashboard --help (runs without ModuleNotFoundError)
- ./ait crew report --help (runs without ModuleNotFoundError)
- Run each command from a tempdir cwd to confirm cwd-independence
EOF
```

This creates and commits the task file. Use the resulting task number in
the main fix's commit body if appropriate ("follow-up: t<N>").

### 1. Fix the import in `agentcrew_status.py`

File: `.aitask-scripts/agentcrew/agentcrew_status.py`

Insert a `sys.path` prepend *before* the `from agentcrew.agentcrew_utils` line,
mirroring `agentcrew_runner.py:16` exactly:

```python
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentcrew.agentcrew_utils import (
    ...
)
```

Two edits needed:
- Add `from pathlib import Path` to the imports block (currently missing).
- Add the `sys.path.insert` line between the stdlib imports and the `agentcrew`
  package import.

The existing `# noqa: E402` isn't present on the runner either — the file is
short enough that linters won't complain about the import order inside the
stdlib block. But since the `from agentcrew.agentcrew_utils` comes after
`sys.path.insert`, it *is* technically out of order. `agentcrew_runner.py` gets
away with it without a noqa; we'll match that.

### 2. Add regression test

File: `tests/test_agentcrew_pythonpath.sh` (new)

A small bash test that:
1. Sets up a temp directory as cwd.
2. Invokes `./ait crew status --crew nonexistent-crew-id list` via absolute path
   from the temp dir.
3. Asserts the output does **not** contain `ModuleNotFoundError` or
   `No module named 'agentcrew'`.
4. Asserts a sensible error about the crew not existing (so we know the Python
   body actually executed, not just exited at import time).
5. Also runs the same command from the repo root to confirm it still works.

Follow the test-file conventions from `tests/test_crew_setmode.sh`:
- `#!/usr/bin/env bash`, `set -e`
- File-based PASS/FAIL counters via `mktemp`
- `assert_contains` / `assert_not_contains` helpers
- Final PASS/FAIL summary with exit code

Keep it focused on the import — don't try to set up a real crew.

### 3. Update CLAUDE.md testing list

File: `CLAUDE.md`

Add the new test file to the testing list (lines 10-30 area). One new line:
`bash tests/test_agentcrew_pythonpath.sh`

## Verification

Run after implementation:

```bash
# 1. Repo-root invocation — existing behavior, should still work
./ait crew status --crew nonexistent list 2>&1
# Expect: "Error: Crew 'nonexistent' not found" (from resolve_crew)
# Must NOT contain: "ModuleNotFoundError"

# 2. From a tempdir — previously broken
cd /tmp && /home/ddt/Work/aitasks/ait crew status --crew nonexistent list 2>&1
# Expect: same as above — crew-not-found error, not ModuleNotFoundError

# 3. Run the new regression test
cd /home/ddt/Work/aitasks && bash tests/test_agentcrew_pythonpath.sh
# Expect: PASS summary

# 4. Also verify agentcrew_runner still works (shouldn't be affected, but sanity)
./ait crew runner --help 2>&1 | head -5
```

## Out of scope (handled via follow-up task — see Step 0)

- Refactoring `agentcrew_dashboard.py` and `agentcrew_report.py` to use the
  same package-style imports is tracked in the follow-up task created in
  Step 0, not done inline in this fix.
- The bash wrappers don't need changes.

## Step 9 Post-Implementation reference

Standard archival flow per task-workflow SKILL.md Step 9.
