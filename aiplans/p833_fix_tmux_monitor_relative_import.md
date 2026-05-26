---
Task: t833_fix_tmux_monitor_relative_import.md
Worktree: (none — fast profile, current branch)
Branch: main
Base branch: main
---

## Context

`tests/test_git_tui_config.py` reports 3 ERRORs when run in isolation. The
traceback bottoms out at `.aitask-scripts/monitor/tmux_monitor.py:42`:

```
from .prompt_patterns import PromptPattern, all_patterns
ImportError: attempted relative import with no known parent package
```

The test loads `tmux_monitor` by prepending `.aitask-scripts/monitor/` to
`sys.path` and importing the module as a top-level name. With no package
context, the relative `from .prompt_patterns import …` has no parent to
resolve against.

The task description proposed **Option 1** — change the relative import to
an absolute `from prompt_patterns import …`. I verified empirically that
this fix is **incomplete**: it lets the test pass but breaks every consumer
that imports via the `monitor` package (the production path used by
`monitor_app.py`, `minimonitor_app.py`, `tests/test_prompt_detection.py`,
`tests/test_idle_compare_modes.py`, etc.). Those consumers put
`.aitask-scripts/` (the package parent) on `sys.path`, not
`.aitask-scripts/monitor/`, so plain `prompt_patterns` is unfindable from
`monitor.tmux_monitor`.

Reproducer of the regression (after applying the proposed Option 1):
```
ModuleNotFoundError: No module named 'prompt_patterns'
  File ".aitask-scripts/monitor/tmux_monitor.py", line 42, in <module>
    from prompt_patterns import PromptPattern, all_patterns
```

### Why fix the test, not the production module

The two peer tests for the same `monitor` package already follow the
canonical pattern: prepend `.aitask-scripts/` to `sys.path` and import as
`from monitor.tmux_monitor import …`. `test_git_tui_config.py` is the odd
one out — its sys.path setup is what breaks the package context. Aligning
it with the peer tests is the smallest, lowest-risk fix:

- No production code changes — `tmux_monitor.py`'s relative import is
  correct for its package and stays untouched.
- Matches the working pattern already established at
  `tests/test_prompt_detection.py:22-24` and
  `tests/test_idle_compare_modes.py:19-21`.
- Single file edit, no risk of double-loading
  `monitor.prompt_patterns` vs. `prompt_patterns` (the hazard introduced by
  any sys.path-injection-in-source variant of Option 1).

`.aitask-scripts/monitor/__init__.py` already exists, so the package is
already proper — there is nothing to restructure (the task's Option 2
"heavier refactor" framing turns out to be moot).

## Implementation

### Single change: `tests/test_git_tui_config.py`

**Edit 1** — replace the sys.path setup at lines 13-15:

```python
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "monitor"))
```

with the peer-test pattern:

```python
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
```

Rationale: `.aitask-scripts/` enables `from monitor.tmux_monitor import …`
(package-style); `.aitask-scripts/lib/` keeps bare imports of
`agent_launch_utils`, `tui_switcher`, and `tui_registry` working
unchanged.

**Edit 2** — change the three `from tmux_monitor import …` statements to
the package-qualified form:

- Line 115: `from tmux_monitor import DEFAULT_TUI_NAMES` →
  `from monitor.tmux_monitor import DEFAULT_TUI_NAMES`
- Line 125: `from tmux_monitor import DEFAULT_TUI_NAMES` →
  `from monitor.tmux_monitor import DEFAULT_TUI_NAMES`
- Line 177: `from tmux_monitor import load_monitor_config` →
  `from monitor.tmux_monitor import load_monitor_config`

The other imports in the file (`agent_launch_utils`, `tui_switcher`,
`tui_registry`) stay as bare imports — they live in
`.aitask-scripts/lib/` and that directory is still on `sys.path`.

### Files NOT touched

- `.aitask-scripts/monitor/tmux_monitor.py` — relative import is correct
  and must stay.
- `.aitask-scripts/monitor/prompt_patterns.py` — unaffected.
- Other tests under `tests/` — already follow the peer pattern.

## Verification

1. Before:
   ```
   python3 tests/test_git_tui_config.py
   # FAILED (errors=3)
   ```

2. After:
   ```
   python3 tests/test_git_tui_config.py
   # Expected: Ran 17 tests in ~0.05s, OK
   ```

3. Confirm no regression elsewhere:
   ```
   bash tests/run_all_python_tests.sh
   ```
   No new failures, especially in `test_prompt_detection.py` and
   `test_idle_compare_modes.py` (which exercise the same modules).

4. Spot-check the production import path stays valid:
   ```
   python3 -c "
   import sys
   sys.path.insert(0, '.aitask-scripts')
   from monitor.tmux_monitor import TmuxMonitor
   print('OK')"
   ```

## Step 9 — Post-Implementation

- Commit code change with subject `bug: Align test_git_tui_config sys.path with peer tests (t833)`.
- Update plan with Final Implementation Notes.
- Run `aitask_archive.sh 833` to archive task + plan.
- Push via `./ait git push`.

## Final Implementation Notes

- **Actual work done:** Realigned `tests/test_git_tui_config.py` with the
  sys.path pattern already used by `tests/test_prompt_detection.py` and
  `tests/test_idle_compare_modes.py`. Replaced
  `sys.path.insert(.aitask-scripts/monitor)` with
  `sys.path.insert(.aitask-scripts)`, and rewrote three
  `from tmux_monitor import …` statements (lines 115, 125, 177) as
  `from monitor.tmux_monitor import …`. The other imports
  (`agent_launch_utils`, `tui_switcher`, `tui_registry`) remained bare,
  served by the still-present `.aitask-scripts/lib/` sys.path entry.

- **Deviations from plan:** The task description proposed editing
  `.aitask-scripts/monitor/tmux_monitor.py:42` to drop the relative import.
  Empirical verification (see Context) showed that change breaks every
  consumer that imports via `monitor.tmux_monitor` — i.e., `monitor_app.py`,
  `minimonitor_app.py`, `test_prompt_detection.py`, and
  `test_idle_compare_modes.py`. Fixed the test instead. No production code
  was touched.

- **Issues encountered:** None during implementation. The pre-edit
  exploration spent most of the time verifying the regression hazard of
  the task author's suggested fix.

- **Key decisions:** Chose test-side alignment over a sys.path-injection
  variant in `tmux_monitor.py`. The latter would have created a real risk
  of two distinct `prompt_patterns` module instances (one as
  `monitor.prompt_patterns`, one as bare `prompt_patterns`), undermining
  class identity for `PromptPattern`.

- **Upstream defects identified:** None.

## Verification (after fix)

- `python3 tests/test_git_tui_config.py` → `Ran 17 tests in 0.063s … OK`
- `bash tests/run_all_python_tests.sh` → `Ran 777 tests in 18.371s … OK`
- Production import path still works:
  ```
  python3 -c "import sys; sys.path.insert(0, '.aitask-scripts'); from monitor.tmux_monitor import TmuxMonitor; print('OK')"
  # OK
  ```
