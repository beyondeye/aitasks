---
Task: t951_fix_tmux_test_bitrot.md
Worktree: (none — working on current branch, profile 'fast')
Branch: main
Base branch: main
---

# Plan: Fix tmux test bitrot (t951)

## Context

t936 relaxed the tmux-test guard so the 8 tmux/multi-session tests run alongside
a live tmux session. Once actually runnable, two of them surfaced **pre-existing**
failures (reproduce identically on HEAD, independent of the t936 guard):

1. `tests/test_multi_session_monitor.sh` — every Python invocation does
   `import tmux_monitor as tm` with `PYTHONPATH="$LIB_DIR:$MONITOR_DIR"` (top-level
   import). But `.aitask-scripts/monitor/tmux_monitor.py:42` is the module's **lone**
   relative import — `from .prompt_patterns import PromptPattern, all_patterns`.
   Every *other* runtime sibling import in that module (lines 33–40: `tui_registry`,
   `agent_launch_utils`) is top-level, bootstrapped by the module's own
   `sys.path.insert` at lines 30–32. Line 42 is an oversight that never got the same
   top-level treatment, so a top-level import raises
   `ImportError: attempted relative import with no known parent package`. Reproduced.

2. `tests/test_multi_session_primitives.sh:55` pins the old 3-field shape
   `FIELDS:project_name,project_root,session`, but `AitasksSession` (in
   `.aitask-scripts/lib/agent_launch_utils.py:74-96`) now also has `is_live` and
   `is_stale` (sorted: `is_live,is_stale,project_name,project_root,session`).
   19/20 sub-checks pass; only this stale assertion fails. Reproduced.

## Approach (and why)

**Fix 1 — make the import robust in `tmux_monitor.py` (not the test).**
The task offers two options: rework the test's invocation to the package path
(`from monitor.tmux_monitor import ...` with `PYTHONPATH=.aitask-scripts`, as
`test_tmux_run_parity.sh` / `test_tmux_control.sh` do) **or** make the import
robust. The sibling tests import only one monitor module, so package-path works
cleanly for them. `test_multi_session_monitor.sh`, by contrast, imports lib
modules directly too (`agent_launch_utils`, `monitor_app`, `monitor_shared`) across
~10 invocations; converting all of them to package paths is invasive and brittle
(lib/ is reached via sys.path insertion in production, not a package path).

The robust-import fix is the lowest-blast-radius option and also removes the
module's internal inconsistency — line 42 is the only relative runtime import in a
module otherwise designed for dual-mode import. Production imports it as
`monitor.tmux_monitor` (minimonitor_app.py:26, monitor_app.py:27,
monitor_shared.py:20), where the relative import succeeds first and behavior is
**unchanged**; only the top-level case (tests) takes the fallback.

Change `.aitask-scripts/monitor/tmux_monitor.py:42` from:
```python
from .prompt_patterns import PromptPattern, all_patterns
```
to:
```python
try:
    from .prompt_patterns import PromptPattern, all_patterns
except ImportError:  # imported top-level (tests put MONITOR_DIR on PYTHONPATH)
    from prompt_patterns import PromptPattern, all_patterns  # noqa: E402
```

**Fix 2 — update the stale assertion in `test_multi_session_primitives.sh:55`.**
Update the expected FIELDS string to the current 5-field shape:
```bash
assert_eq "AitasksSession fields" "FIELDS:is_live,is_stale,project_name,project_root,session" "${lines[0]:-}"
```
Keep it an **exact-match** assertion (not a subset). The test's stated purpose
(header line 6: "AitasksSession dataclass shape") is to pin the full shape — the
exact match is a deliberate canary that reminds a future editor to revisit this
test when the dataclass grows. Subset-matching would silence that signal.

## Files to modify

- `.aitask-scripts/monitor/tmux_monitor.py` (line 42) — robust import.
- `tests/test_multi_session_primitives.sh` (line 55) — updated expected FIELDS.

## Verification

```bash
bash tests/test_multi_session_monitor.sh      # was: ImportError → expect all PASS
bash tests/test_multi_session_primitives.sh   # was: 19/20 → expect 20/20
```
Also sanity-check production package-mode import is unbroken:
```bash
PYTHONPATH=.aitask-scripts python3 -c "from monitor.tmux_monitor import TmuxMonitor; print('OK')"
```
And run shellcheck on the touched test (no new findings expected):
```bash
shellcheck tests/test_multi_session_primitives.sh
```

See **Step 9 (Post-Implementation)** of the shared task-workflow for archival.

## Risk

### Code-health risk: low
- None identified. Fix 1 is a 3-line try/except that leaves the production
  (package-mode) import path untouched and only adds a top-level fallback; Fix 2
  is a single test-assertion string update. Blast radius is one runtime module
  line (guarded) and one test line.

### Goal-achievement risk: low
- None identified. The two changes map one-to-one onto the two reproduced
  failures and are directly verifiable by re-running both tests to green.
