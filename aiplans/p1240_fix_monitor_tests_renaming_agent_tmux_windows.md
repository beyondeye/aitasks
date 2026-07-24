---
Task: t1240_fix_monitor_tests_renaming_agent_tmux_windows.md
Worktree: (none — fast profile, current branch)
Branch: main
Base branch: main
---

# Plan: t1240 — Stop monitor TUI tests renaming the invoking agent's tmux window

## Context

Agent tmux windows in the `aitasks` session get randomly renamed to `monitor`,
many times a day, and revert to `monitor` even after manual renames.

**Root cause (confirmed by live reproduction during exploration):**
`MonitorApp.on_mount` (`.aitask-scripts/monitor/monitor_app.py:489-497`) runs
`tmux rename-window -t $TMUX_PANE monitor`, guarded only by `$TMUX` being set.
Five test files mount the **real** `MonitorApp` via Textual `app.run_test()`,
which fires `on_mount` in-process with no env scrubbing or subprocess stubbing:

- `tests/test_monitor_preview_offload.py` (7 mounts)
- `tests/test_monitor_finalize_offload.py`
- `tests/test_monitor_focus_switch.py` (3 mounts)
- `tests/test_monitor_refresh_no_sync_tmux.py` (2 mounts)
- `tests/test_monitor_shadow_status.py`

When a coding agent runs these tests inside its tmux pane, the test inherits the
agent's `TMUX`/`TMUX_PANE`, so the rename relabels the **agent's own window** on
the live tmux server. Reproduced: running one test renamed `agent-explore-1` →
`monitor`. The t941/t1130 pinned-rename fix targets the right pane for a real
monitor process but cannot help when a test-mounted instance inherits an agent
pane's env. Sibling repos' aitasks versions are unrelated (fix present there).

**Approach: structural (make the bad path impossible)** — the mount-time rename
becomes opt-in from the production CLI entry point only, so a test mount can
never rename anything, regardless of env. Env scrubbing in the affected tests is
added as belt-and-braces (it also makes `on_mount` take the deterministic
not-inside-tmux early-return path everywhere, instead of behaving differently
inside vs outside tmux).

## Implementation Steps

### 1. Gate the rename behind a constructor flag — `.aitask-scripts/monitor/monitor_app.py`

- `MonitorApp.__init__` (line 412): add parameter `rename_window: bool = False`
  (after `compare_mode_default`), store `self._rename_window = rename_window`.
  Brief comment: only the production launcher (`main()`) passes `True`; test
  mounts default to `False` so `on_mount` can never touch the live tmux server
  (t1240).
- `on_mount` (lines 489-497): wrap the rename block in
  `if self._rename_window:` (keep the existing `_rename_window_argv` +
  `subprocess.run` body unchanged).
- `main()` (line 2044): add `rename_window=True` to the `MonitorApp(...)` call.
  This is the **only** production constructor call site (verified by grep), so
  TUI-switcher discovery by window name is preserved.

### 2. Scrub ambient tmux env in the five affected test files

In each of the 5 test files listed above, right after the `sys.path` bootstrap /
imports (pattern at `tests/test_monitor_preview_offload.py:22-26`), add:

```python
import os  # (only if not already imported)

# Belt-and-braces for t1240: rename_window now defaults to False, but scrub the
# ambient tmux env too so MonitorApp.on_mount takes the deterministic
# not-inside-tmux path regardless of where the suite runs.
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)
```

(MiniMonitorApp mounts — e.g. in `test_monitor_shadow_status.py` — have no
rename path; verified during exploration.)

### 3. New guard test — `tests/test_monitor_rename_gate.py`

`unittest.IsolatedAsyncioTestCase`, same sys.path bootstrap as the other monitor
tests (auto-discovered by `tests/run_all_python_tests.sh` via `test_*.py` glob).
Common fixture per test:

- `unittest.mock.patch.dict(os.environ, {"TMUX": "/tmp/fake,1,0", "TMUX_PANE": "%99"})`
- patch `monitor.monitor_app.subprocess.run` with a recorder (no real tmux call)
- `patch.object(MonitorApp, "_start_monitoring", lambda self: None)` so the
  mount stays inert (the surface under test is only the rename gate)

Tests:

1. **Guard:** default construction (`MonitorApp(session="demo",
   project_root=REPO_ROOT)`) → `run_test()` mount → assert **no** recorded argv
   contains `rename-window`. This is the regression pin: it fails on the old
   unconditional-rename behavior (verified as the negative control during
   implementation by temporarily reverting the gate).
2. **Production pin:** same but `rename_window=True` → assert exactly one
   recorded call with argv `["tmux", "rename-window", "-t", "%99", "monitor"]`
   — proves the real `ait monitor` launch path still renames its own window.
3. **Fail-safe pin:** `rename_window=True` but `TMUX_PANE` absent from env →
   assert no rename call (mount-level pin of the existing `_rename_window_argv`
   empty-argv guard from t941/t1130).

Existing `tests/test_monitor_rename_window_target.sh` (pure-function argv test)
stays valid and untouched.

## Verification

- `python3 tests/test_monitor_rename_gate.py` — all 3 pass; temporarily
  reverting the `if self._rename_window:` gate makes test 1 fail (prove the
  guard can fail), then restore.
- Re-run the original live repro **inside a tmux pane**:
  `tmux display-message -p '#W'` before/after
  `python3 tests/test_monitor_preview_offload.py` → window name unchanged.
- Run the 5 modified test files individually — all pass.
- `ait monitor` manual smoke (production path still renames its own window) —
  cheap to verify by launching monitor in a scratch tmux window; its window
  should become `monitor`.

## Post-Implementation

Step 9 (task-workflow): gates run (`risk_evaluated` is orchestrator-recorded),
archival via `aitask_archive.sh 1240`. No worktree/branch cleanup (fast profile,
current branch). No user-facing doc updates needed (behavior is internal;
aidocs/framework TUI docs do not document the mount-time rename).

## Risk

### Code-health risk: low
- A future production entry point constructing `MonitorApp` without
  `rename_window=True` would silently lose switcher-discovery renaming ·
  severity: low · → mitigation: covered in-task (guard test #2 pins the
  production rename behavior; `main()` is the single production call site)

### Goal-achievement risk: low
- If some observed renames come from a source other than test mounts, the
  symptom could partially persist · severity: low · → mitigation: covered
  in-task (live repro matched the reported symptom exactly; sibling-repo
  installs verified to carry the pinned-rename fix; verification re-runs the
  repro end-to-end)
