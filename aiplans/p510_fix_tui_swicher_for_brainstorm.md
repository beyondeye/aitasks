---
Task: t510_fix_tui_swicher_for_brainstorm.md
Worktree: (current branch)
Branch: main
Base branch: main
Folded: t498_brainstorming_session_switcher_for_monitor.md
---

## Context

Brainstorm TUI windows are created with names like `brainstorm-{task_num}`, but the TUI switcher and monitor use exact-match against `"brainstorm"`. Additionally, existing brainstorm sessions (stored in `.aitask-crews/crew-brainstorm-*/`) should be discoverable and launchable from the TUI switcher, even when no tmux window is running for them.

**Bugs to fix:**
1. TUI switcher shows a static "Brainstorm" entry (no task number) that never matches any running window
2. Running `brainstorm-*` windows appear in "Other" section instead of TUI section
3. Monitor TUI shows `brainstorm-*` windows in "OTHER" agent list — should be hidden entirely
4. Brainstorm app's `current_tui_name = "brainstorm"` doesn't match window name `brainstorm-{num}`

**Feature from t498:**
5. Detect existing brainstorm sessions from `.aitask-crews/crew-brainstorm-*/` and show them in TUI switcher as launchable entries (with running/not-running indicator)

## Plan

### 1. Fix TUI Switcher — `.aitask-scripts/lib/tui_switcher.py`

**a) Remove static brainstorm entry from `KNOWN_TUIS` (line 62)**
Delete: `("brainstorm", "Brainstorm", "ait brainstorm")`

**b) Add brainstorm prefix constant and session discovery (near line 70)**
```python
_BRAINSTORM_PREFIX = "brainstorm-"

def _discover_brainstorm_sessions() -> list[str]:
    """Scan .aitask-crews/crew-brainstorm-*/ for existing brainstorm sessions.
    Returns list of task numbers with existing sessions."""
    crews_dir = Path(".aitask-crews")
    if not crews_dir.is_dir():
        return []
    prefix = "crew-brainstorm-"
    sessions = []
    for entry in sorted(crews_dir.iterdir()):
        if entry.is_dir() and entry.name.startswith(prefix):
            session_file = entry / "br_session.yaml"
            if session_file.is_file():
                sessions.append(entry.name[len(prefix):])
    return sessions
```
This avoids importing the brainstorm module (which has heavy dependencies). Uses the same logic as `brainstorm_session.list_sessions()` but lightweight — just checks for `br_session.yaml` existence.

**c) Update `_classify_window()` (line 82-89)**
Add before the `return "other"` fallback:
```python
if name.startswith(_BRAINSTORM_PREFIX):
    return "tui"
```

**d) Update `on_mount()` — add dynamic brainstorm entries to TUI group**
After the `KNOWN_TUIS` loop (after line 249):
1. Discover existing brainstorm sessions from disk
2. Merge with running brainstorm windows (running windows may or may not have a session on disk)
3. Add each as a `_TuiListItem` with running/not-running status

```python
# Dynamic brainstorm session entries
brainstorm_sessions = _discover_brainstorm_sessions()
running_brainstorm = {
    name: running_by_name[name]
    for name in self._running_names
    if name.startswith(_BRAINSTORM_PREFIX)
}
# Collect all brainstorm task nums: from sessions + running windows
all_brainstorm_nums = set(brainstorm_sessions)
for name in running_brainstorm:
    all_brainstorm_nums.add(name[len(_BRAINSTORM_PREFIX):])

for task_num in sorted(all_brainstorm_nums):
    win_name = f"{_BRAINSTORM_PREFIX}{task_num}"
    label = f"Brainstorm (t{task_num})"
    running = win_name in self._running_names
    is_current = win_name == self._current_tui
    item = _TuiListItem(win_name, label, running, is_current)
    if is_current:
        item.disabled = True
    elif first_selectable_idx is None:
        first_selectable_idx = item_idx
    list_view.append(item)
    item_idx += 1
```

**e) Update `_get_launch_command()` (lines 365-370)**
Add brainstorm handling before the fallback:
```python
@staticmethod
def _get_launch_command(name: str) -> str:
    for tui_name, _, cmd in KNOWN_TUIS:
        if tui_name == name:
            return cmd
    if name.startswith(_BRAINSTORM_PREFIX):
        task_num = name[len(_BRAINSTORM_PREFIX):]
        return f"ait brainstorm {task_num}"
    return f"ait {name}"
```

**f) Update `action_shortcut_brainstorm()` (lines 325-326)**
Switch to first running brainstorm window; if none running, notify:
```python
def action_shortcut_brainstorm(self) -> None:
    for name in sorted(self._running_names):
        if name.startswith(_BRAINSTORM_PREFIX):
            self._switch_to(name, True)
            return
    self.app.notify("No brainstorm session running", severity="warning")
```

**g) Keep the `r` binding** — shortcut still works, targets running brainstorm windows dynamically.

### 2. Fix Monitor TUI — `.aitask-scripts/monitor/tmux_monitor.py`

**Update `classify_pane()` (lines 76-82)**
Add before the `return PaneCategory.OTHER` fallback:
```python
if window_name.startswith("brainstorm-"):
    return PaneCategory.TUI
```
Since `_rebuild_pane_list()` in `monitor_app.py` only shows AGENT and OTHER, TUI-classified panes are automatically excluded.

### 3. Fix brainstorm app current_tui_name — `.aitask-scripts/brainstorm/brainstorm_app.py`

**Update line 921:**
```python
self.current_tui_name = f"brainstorm-{task_num}"
```
Ensures the switcher correctly marks the current brainstorm window as active when opened from within brainstorm.

### 4. No changes needed to:
- `monitor_app.py` — already filters out TUI panes
- `project_config.yaml` — prefix check is hardcoded, no config change needed

## Verification

1. Open `ait board`, launch a brainstorm session for a task
2. Open TUI switcher (`j`):
   - Running brainstorm shows as green dot with "Brainstorm (tN)" in TUI section
   - Existing but non-running brainstorm sessions show as dim circle with "Brainstorm (tN)"
   - No generic "Brainstorm" entry without task number
   - No brainstorm entries in "Other" section
3. Select a non-running brainstorm entry → launches `ait brainstorm N` in new tmux window
4. Press `r` in switcher → switches to running brainstorm window
5. From within brainstorm app, open switcher: current brainstorm marked as current (cyan arrow, disabled)
6. Open `ait monitor`: brainstorm-N does NOT appear in the agent list at all
7. Run: `bash tests/test_terminal_compat.sh`

## Final Implementation Notes
- **Actual work done:** Implemented all 5 items as planned — removed static brainstorm TUI entry, added dynamic session discovery from `.aitask-crews/`, classified `brainstorm-*` windows as TUI in both switcher and monitor, fixed brainstorm app's `current_tui_name`, and updated launch command resolution.
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Used lightweight disk scan (`_discover_brainstorm_sessions()`) instead of importing brainstorm module to avoid heavy dependencies in the switcher. The `r` shortcut now targets the first running brainstorm window (sorted) rather than a static name.
