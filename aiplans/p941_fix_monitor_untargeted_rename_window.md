---
Task: t941_fix_monitor_untargeted_rename_window.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
---

# Plan: Fix untargeted `rename-window` mislabeling board window as `monitor`

## Context

`ait ide` (and other monitor-launch paths) can leave the session with a **board
TUI running in a tmux window named `monitor`**, plus a duplicate `monitor`
window. Reproduced live in session `aitasks_go`: two windows named `monitor`
existed, one of which was actually a board TUI ("Esc to return to board"). The
mislabeled window was **persistent** (the user had to close it manually), not a
transient flicker.

### Root cause

`monitor_app.py` `on_mount` (line ~673-679) renames its window with **no target**:

```python
subprocess.run(["tmux", "rename-window", "monitor"], capture_output=True, timeout=5)
```

This is the **only** code in the repo that names a window `monitor` (`grep -rn
"rename-window"` confirms; `aitask_ide.sh` and `tmux_bootstrap.sh` create the
window with `-n monitor`; the board never renames itself).

Because the call passes no `-t`, tmux resolves it against the **attached
client's active window** rather than the pane the monitor process actually runs
in. `on_mount` fires a few hundred ms after the monitor TUI boots — by then the
active window can be a *different* window (a board the user is viewing, or
another window made active by `ait ide`'s `ensure_syncer_window`/`select-window`
sequence). The rename then lands on that board window. Since these windows have
`automatic-rename off` (verified live: `auto_rename=0`), the wrong name **sticks
permanently**.

The live forensics confirm the untargeted form does *not* reliably honor
`TMUX_PANE`: monitor's own window was correctly named `monitor` (created with
`-n monitor`), yet a *separate* board window also ended up named `monitor` —
i.e. the rename hit the active window, not monitor's pane.

### Knock-on effect

The TUI switcher identifies running TUIs **by window name** (`_running_names` in
`tui_switcher.py`). Once a board is mislabeled `monitor`, the switcher treats it
*as* monitor, and a subsequent genuine monitor launch creates a **second**
`monitor` window — the observed duplicate.

### Intended outcome

The monitor window-rename must only ever affect **monitor's own pane's window**,
regardless of which window is currently active or how many clients are attached.

## Approach

Pin the rename to monitor's own pane via `-t "$TMUX_PANE"`, falling back to the
current untargeted behavior only when `TMUX_PANE` is unset (it is essentially
always set for a process running inside a tmux pane — `tmux_monitor.py:200`
already relies on it).

### File: `.aitask-scripts/monitor/monitor_app.py` (`on_mount`, ~line 670-679)

Replace the untargeted `subprocess.run` with a pane-targeted argv built by a
small module-level pure helper (so the targeting logic is unit-testable without
booting Textual or tmux):

Add near the top of the module (module scope, after imports):

```python
def _rename_window_argv(pane: str | None) -> list[str]:
    """Build the `tmux rename-window monitor` argv, pinned to *pane* when known.

    Targeting the monitor's own pane (via $TMUX_PANE) prevents tmux from
    resolving the untargeted default to the attached client's *active* window —
    which, with automatic-rename off, would permanently mislabel an unrelated
    window (e.g. a board) as `monitor`. See t941.
    """
    argv = ["tmux", "rename-window"]
    if pane:
        argv += ["-t", pane]
    argv.append("monitor")
    return argv
```

In `on_mount`, replace:

```python
        try:
            subprocess.run(
                ["tmux", "rename-window", "monitor"],
                capture_output=True, timeout=5,
            )
        except Exception:
            pass
```

with:

```python
        try:
            subprocess.run(
                _rename_window_argv(os.environ.get("TMUX_PANE")),
                capture_output=True, timeout=5,
            )
        except Exception:
            pass
```

(`os` is already imported; the comment at the call site explaining the
pre-`_start_monitoring` raw-subprocess constraint stays.)

## Blast radius / safety

- **Single behavior change, narrow scope.** The only observable difference: the
  rename now targets monitor's own pane instead of the ambiguous "current
  window". For the common case (monitor launched into its own freshly-created
  `monitor` window and immediately active) behavior is identical. The change
  only *prevents* the misfire onto an unrelated active window.
- **No caller changes.** `on_mount` signature and surrounding flow are
  untouched; the helper is additive.
- **Fallback preserves old behavior** when `TMUX_PANE` is missing, so no
  regression in any environment that previously worked.
- **Editor-unaware-edit risk:** the helper is self-documenting with a t941
  reference; someone later removing `-t` would reintroduce the bug, mitigated by
  the unit test below asserting the pane target is present.

## Other untargeted tmux mutations (checked — out of scope)

`grep -rn "rename-window\|respawn"` shows `rename-window` is unique to this site.
Other `new-window` calls already pass explicit `-t`/`-n`. The session-rename
(`monitor_app.py:237`) and `tmux_monitor.py:636` `select-window` already pass
explicit targets. No sibling fixes needed.

## Testing / Verification

### Unit test (deterministic, no tmux/Textual needed)

Add `tests/test_monitor_rename_window_target.sh` mirroring the Tier-1 Python
pattern in `tests/test_tmux_exact_session_targeting.sh` (uses
`tests/lib/asserts.sh`; `require_no_tmux` not required since the helper is pure).
Import the helper with `PYTHONPATH` set to `.aitask-scripts` and assert:

- `_rename_window_argv("%7")` → `["tmux","rename-window","-t","%7","monitor"]`
  (pane target present, in the right position).
- `_rename_window_argv(None)` → `["tmux","rename-window","monitor"]`
  (graceful fallback).
- `_rename_window_argv("")` → `["tmux","rename-window","monitor"]`
  (empty env var treated as unset).

Import shape (monitor_app imports `from monitor.tmux_monitor import ...`, so add
both `.aitask-scripts` and `.aitask-scripts/monitor` to `sys.path`, or import via
`PYTHONPATH=".aitask-scripts:.aitask-scripts/monitor"`):

```bash
out=$(PYTHONPATH="$PROJECT_DIR/.aitask-scripts:$PROJECT_DIR/.aitask-scripts/monitor" \
  python3 -c "
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location(
    'monitor_app', '$PROJECT_DIR/.aitask-scripts/monitor/monitor_app.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print(m._rename_window_argv('%7'))
print(m._rename_window_argv(None))
print(m._rename_window_argv(''))
")
```

If module import pulls Textual and it is unavailable in the test environment,
fall back to asserting the helper in isolation by `exec`-ing only the function
definition — but Textual is a TUI dependency already present in this repo's test
env (other `tests/test_*.py` import board/monitor modules), so a direct import is
expected to work. Confirm during implementation.

### Manual verification (the real-world repro)

`grep`-confirmed there is no automated coverage for the live multi-client repro;
queue this as a manual check (Step 8c offers a manual-verification follow-up):

1. `tmux kill-server`; `ait ide` in the project → confirm one `monitor` window.
2. Open a board (`j` → board in the switcher) and make it the active window.
3. From another terminal/client attached to the same session, launch a second
   `ait monitor` (or trigger a monitor relaunch) while the board stays active.
4. **Expected:** no board window is ever renamed `monitor`; no duplicate
   `monitor` window appears. `tmux list-windows` shows board windows keep the
   `board` name and only monitor's own pane's window is named `monitor`.

### Lint

`shellcheck tests/test_monitor_rename_window_target.sh` (new test).
Python: no project-wide linter for `.aitask-scripts/monitor/*.py` beyond the
existing style; keep the helper consistent with surrounding code.

## Risk

### Code-health risk: low
- None identified. Single-site change in `monitor_app.py` `on_mount`; the new
  `_rename_window_argv` helper is pure and additive; the `TMUX_PANE`-unset
  fallback preserves prior behavior; a deterministic unit test pins the
  targeting. No callers change, no shared contracts touched.

### Goal-achievement risk: low
- tmux "current window" / `-t $TMUX_PANE` resolution could in principle differ
  across tmux versions, so the fix can't be proven by an automated test alone ·
  severity: low · → mitigation: covered by the manual-verification follow-up in
  Step 8c (live multi-client repro), no separate task warranted.

## Step 9 (Post-Implementation)

Standard task-workflow archival: commit code (`bug: ... (t941)`) and plan
separately, then archive t941 via `aitask_archive.sh 941`. No folded tasks.

## Final Implementation Notes

- **Actual work done:** Added module-level pure helper `_rename_window_argv(pane)`
  to `.aitask-scripts/monitor/monitor_app.py` (after imports, before the Zone
  model) and changed `on_mount` to call
  `_rename_window_argv(os.environ.get("TMUX_PANE"))` instead of the untargeted
  `["tmux", "rename-window", "monitor"]`. Added
  `tests/test_monitor_rename_window_target.sh` (3 assertions: pane→targeted,
  None→fallback, ""→fallback). Exactly matches the approved plan.
- **Deviations from plan:** None of substance. Test exit line uses bare
  `[[ $FAIL -eq 0 ]]` instead of `exit $(...)` to avoid shellcheck SC2046 —
  cleaner than the `test_tmux_exact_session_targeting.sh` reference, which trips
  SC2046/SC2329.
- **Issues encountered:** None. Helper imports cleanly via file-path load
  (monitor_app self-bootstraps its sys.path); `py_compile` passes; test passes
  3/3; shellcheck emits only the benign SC1091 (sourced file not followed),
  same as existing tests.
- **Upstream defects identified:** None. The defect was in the task's own target
  (`monitor_app.py` `on_mount`); diagnosis explicitly checked other tmux
  window/pane mutations (`grep -rn "rename-window\|respawn"`, `new-window`,
  `select-window`, the session-rename at `monitor_app.py:237`) and all already
  pass explicit targets — no separate pre-existing bug surfaced.
