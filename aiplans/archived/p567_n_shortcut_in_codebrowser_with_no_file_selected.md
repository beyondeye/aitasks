---
Task: t567_n_shortcut_in_codebrowser_with_no_file_selected.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Implementation Plan: Fix `n` shortcut in codebrowser (t567)

## Context

The codebrowser `n` shortcut creates a new task with a file reference. Three behaviors need fixing:
1. If no file is open, pressing `n` shows "No file selected" warning and does nothing — should allow creating a task without file reference
2. If a file is open but no line range is selected, it defaults to cursor line — should default to the full file range
3. Tmux spawning defaults to a new window — should default to splitting the SAME window where codebrowser is running, so the user can see the file during `ait create`

## Changes

### File 1: `.aitask-scripts/codebrowser/codebrowser_app.py`

**A. Add `_detect_tmux_window()` method** (next to `_detect_tmux_session()` at line 200):
```python
@staticmethod
def _detect_tmux_window() -> str | None:
    """Return the current tmux window index, or None if not in tmux."""
    if not os.environ.get("TMUX"):
        return None
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#{window_index}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None
```

**B. Store window in `__init__`** (after line 194):
```python
self._tmux_window: str | None = self._detect_tmux_window()
```

**C. Rewrite `action_create_task()`** (lines 1033-1076):

Three branches:
1. **No file selected** → no `--file-ref`, title = "Create task", no `window_name` suffix
2. **File selected, line range selected** → `--file-ref path:start-end` (unchanged)
3. **File selected, no line range** → `--file-ref path:1-{total_lines}` (full file)

Also pass `default_tmux_window=self._tmux_window` to `AgentCommandScreen`.

**D. Update `_run_create_from_selection()`** (lines 1078-1094):

Accept `ref_arg: str | None`. When `None`, call create script without `--file-ref`.

### File 2: `.aitask-scripts/lib/agent_command_screen.py`

**A. Add `default_tmux_window` parameter** to `__init__` (line 195):
```python
def __init__(self, ..., default_tmux_window: str | None = None):
    ...
    self._default_tmux_window = default_tmux_window
```

**B. Update `_update_window_options()`** (lines 362-382):

If `self._default_tmux_window` is set and matches a window in the list, pre-select it instead of `_NEW_WINDOW_SENTINEL`. This triggers `_on_window_changed()` which shows the split direction UI.

```python
def _update_window_options(self, session: str) -> None:
    ...
    # Default to the specified window if it exists, otherwise new window
    if self._default_tmux_window:
        matching = [idx for idx, name in windows if idx == self._default_tmux_window]
        if matching:
            win_select.value = matching[0]
        else:
            win_select.value = _NEW_WINDOW_SENTINEL
    else:
        win_select.value = _NEW_WINDOW_SENTINEL

    self._on_window_changed(win_select.value)
```

## Verification

1. Open codebrowser with a file loaded, press `n` with no selection → should show full file range in file reference
2. Open codebrowser, navigate away from files (no file open), press `n` → should open create dialog without file reference
3. Open codebrowser in tmux, press `n` → tmux tab should default to current window (split pane), not "New window"
4. Select a line range, press `n` → should still work as before with the selected range

## Post-implementation: Step 9 (archival, push)

## Final Implementation Notes
- **Actual work done:** All three changes implemented as planned — no file guard removal, full-file default range, and tmux same-window defaulting.
- **Deviations from plan:** None — implementation matched the plan exactly.
- **Issues encountered:** None.
- **Key decisions:** Used `code_viewer._total_lines` for full-file range (already tracked by CodeViewer). For tmux window detection, mirrored the existing `_detect_tmux_session()` pattern using `#{window_index}` format string.
