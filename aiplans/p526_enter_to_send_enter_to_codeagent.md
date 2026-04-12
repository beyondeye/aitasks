---
Task: t526_enter_to_send_enter_to_codeagent.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# t526: Enter to send Enter keystroke to sibling codeagent pane

## Context

t524 added a `Tab` binding in `ait minimonitor` that shifts tmux focus from the
minimonitor pane to the sibling code-agent pane in the same tmux window. The
natural follow-up is an `Enter` binding that — while the minimonitor TUI keeps
terminal focus — sends a literal `Enter` keystroke into that same sibling pane.
This lets a user "poke" an idle code agent (send a newline, retry a prompt, etc.)
without leaving the minimonitor or reaching for the mouse.

Key invariant from the task description: the target is **always** the physically
adjacent pane (same target as `Tab`), **not** whichever `MiniPaneCard` happens
to be focused in the card list. The card selection is irrelevant to this action.

The archived t524 plan (`aiplans/archived/p524_tab_to_switch_to_codeagent.md`,
"Notes for follow-up task" section) already lays out the exact pattern to
follow, including the recommendation to extract the sibling-pane lookup into a
shared helper so both handlers reuse it.

## Approach

1. **Refactor** `_focus_sibling_pane()` to split off a `_find_sibling_pane_id()`
   helper that returns the sibling's `pane_id` (or `None` with a user
   notification on failure). Both the existing Tab handler and the new Enter
   handler call this helper so the "find the non-self pane in my tmux window"
   logic lives in exactly one place.
2. **Add** an `Enter` binding using the same Binding + no-op action + `on_key`
   handling pattern t524 established, so Textual's default activation doesn't
   swallow the key. The new branch sits after the modal-screen guard (so
   `TaskDetailDialog` keeps working) and after the `tab` branch.
3. **Send** the keystroke via `self._monitor.send_keys(pane_id, "Enter")` —
   the `TmuxMonitor.send_keys` helper already exists at
   `.aitask-scripts/monitor/tmux_monitor.py:268` and is what `monitor_app.py:754`
   uses. This avoids duplicating another `subprocess.run(["tmux", "send-keys",
   ...])` call in this file.
4. **Extend** the custom multi-line footer introduced in t524 to include an
   `enter:send` hint at the end of the second line (the plan explicitly notes
   there is room for one more entry there).

## Files to modify

- `.aitask-scripts/monitor/minimonitor_app.py` (single file)

## Relevant existing code

- `.aitask-scripts/monitor/minimonitor_app.py:93-100` — `BINDINGS` list
  (add `enter` binding here)
- `.aitask-scripts/monitor/minimonitor_app.py:131-135` — `compose()` renders
  `#mini-key-hints` footer (update second line)
- `.aitask-scripts/monitor/minimonitor_app.py:336-357` — `on_key()` (add
  `enter` branch after the existing modal guard and `tab` branch)
- `.aitask-scripts/monitor/minimonitor_app.py:373-407` — existing
  `_focus_sibling_pane()` (refactor to use `_find_sibling_pane_id()`)
- `.aitask-scripts/monitor/minimonitor_app.py:425-426` — existing
  `action_focus_sibling_pane` no-op (add sibling `action_send_enter_to_sibling`)
- `.aitask-scripts/monitor/tmux_monitor.py:268` — `TmuxMonitor.send_keys()` to
  reuse (same method `monitor_app.py:754` uses)
- `.aitask-scripts/monitor/monitor_app.py:751-755` — reference for the
  send-keys mechanic only (targeting logic is different — minimonitor's target
  is fixed to the sibling, not derived from card focus)

## Implementation steps

### 1. Extract `_find_sibling_pane_id()` helper (refactor)

Replace the body of `_focus_sibling_pane()` with a call to a new helper that
returns the sibling pane id or `None`. Notifications for the "not in tmux"
and "no other pane" cases move into the helper so both callers get consistent
UX.

```python
def _find_sibling_pane_id(self) -> str | None:
    """Return the pane_id of the first non-minimonitor pane in our tmux window.

    Notifies the user and returns None on any failure (not in tmux, tmux
    subprocess error, no sibling pane). Used by both the Tab focus handler
    and the Enter send-keys handler.
    """
    own_pane = os.environ.get("TMUX_PANE", "")
    if not own_pane or not self._own_window_id:
        self.notify("Not inside tmux", severity="warning")
        return None
    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-t", self._own_window_id,
             "-F", "#{pane_id}"],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        self.notify("tmux error", severity="error")
        return None
    if result.returncode != 0:
        self.notify("tmux list-panes failed", severity="error")
        return None
    other_panes = [
        line.strip() for line in result.stdout.strip().splitlines()
        if line.strip() and line.strip() != own_pane
    ]
    if not other_panes:
        self.notify("No other pane in this window", severity="warning")
        return None
    return other_panes[0]

def _focus_sibling_pane(self) -> None:
    """Move tmux focus to the sibling pane in the minimonitor's window."""
    sibling = self._find_sibling_pane_id()
    if sibling is None:
        return
    try:
        sel = subprocess.run(
            ["tmux", "select-pane", "-t", sibling],
            capture_output=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        self.notify("select-pane failed", severity="error")
        return
    if sel.returncode != 0:
        self.notify("select-pane failed", severity="error")
```

This is an internal refactor — external behavior of Tab is unchanged (same
notifications, same outcome).

### 2. Add `_send_enter_to_sibling()` method

New method next to `_focus_sibling_pane`. Uses `self._monitor.send_keys`
(the same helper `monitor_app.py:754` uses) rather than another direct
`subprocess.run` call.

```python
def _send_enter_to_sibling(self) -> None:
    """Send an Enter keystroke to the sibling pane in our tmux window."""
    if self._monitor is None:
        self.notify("Monitor not ready", severity="warning")
        return
    sibling = self._find_sibling_pane_id()
    if sibling is None:
        return
    if not self._monitor.send_keys(sibling, "Enter"):
        self.notify("send-keys failed", severity="error")
```

### 3. Add `Enter` binding to `BINDINGS`

Insert immediately after the Tab binding so the two pane-targeting bindings
stay adjacent:

```python
BINDINGS = [
    Binding("tab", "focus_sibling_pane", "Focus agent", show=False),
    Binding("enter", "send_enter_to_sibling", "Send Enter", show=False),
    Binding("j", "tui_switcher", "Jump TUI", show=False),
    Binding("q", "quit", "Quit", show=False),
    Binding("s", "switch_to", "Switch", show=False),
    Binding("i", "show_task_info", "Task Info", show=False),
    Binding("r", "refresh", "Refresh", show=False),
]
```

### 4. Add no-op `action_send_enter_to_sibling`

Needed because Textual requires the action to exist when a binding references
it; real logic lives in `on_key`. Place alongside the existing
`action_focus_sibling_pane`:

```python
def action_send_enter_to_sibling(self) -> None:
    """No-op — Enter is handled in on_key. Exists for Binding registration."""
```

### 5. Handle `Enter` in `on_key`

Insert the `enter` branch after the existing `tab` branch (both live after the
modal-screen guard). The modal guard above it ensures `TaskDetailDialog`'s own
Enter handling is not intercepted.

```python
def on_key(self, event) -> None:
    key = event.key

    # Let modal screens handle their own keys
    if isinstance(self.screen, ModalScreen):
        return

    if key == "tab":
        self._focus_sibling_pane()
        event.stop()
        event.prevent_default()
        return

    if key == "enter":
        self._send_enter_to_sibling()
        event.stop()
        event.prevent_default()
        return

    # Up/Down navigate within pane list
    if key == "up":
        ...
```

### 6. Update the `#mini-key-hints` footer text

The plan in t524 explicitly notes there is room for one more entry at the end
of the second line. Append `enter:send`:

```python
yield Static(
    "tab:agent  s/\u2191\u2193:switch  i:info\n"
    "j:jump     r:refresh  q:quit  enter:send",
    id="mini-key-hints",
)
```

`height: auto` is already set on `#mini-key-hints` from t524, so no CSS change
is needed.

## Edge cases covered

- **Modal screen active** (e.g. `TaskDetailDialog`): early return in `on_key`
  leaves Enter to the modal, so Task Info's dialog still handles Enter.
- **Not inside tmux**: `_find_sibling_pane_id()` notifies and returns None.
- **Only the minimonitor pane in the window**: user notification, no action.
- **Monitor not yet initialized**: `_send_enter_to_sibling()` guards on
  `self._monitor is None`.
- **tmux subprocess failure** (either `list-panes` in the helper or
  `send_keys` in `TmuxMonitor`): user notification, no crash — `send_keys`
  already returns `False` on failure.
- **Tab behavior unchanged**: the refactor keeps `_focus_sibling_pane`
  externally identical (same notification strings, same targeting).

## Verification

Manual test inside an `aitasks` tmux session (same setup as t524):

1. Start a code-agent window that also spawns a minimonitor side pane. Confirm
   the layout: one wide code-agent pane + a narrow minimonitor pane.
2. Focus the minimonitor pane. Press `Tab`. Expected: tmux focus moves to the
   sibling code-agent pane (regression check — t524 behavior must still work).
3. Focus the minimonitor pane again. Press `Enter`. Expected: an Enter
   keystroke is delivered to the sibling code-agent pane, **without** the
   minimonitor losing focus. The minimonitor's card selection is irrelevant.
4. Open the Task Info modal via `i`. Press `Enter`. Expected: the modal
   handles Enter (closes/selects), **not** the new sibling sender.
5. Regression check: press `i`, `j`, `s`, `r`, `q` — all existing bindings
   still behave as before.
6. Visually confirm the footer shows `enter:send` at the end of the second
   line and still fits in a 40-column column.
7. Lint-compile:
   ```bash
   python -m py_compile .aitask-scripts/monitor/minimonitor_app.py
   ```

## Step 9 reference

After implementation and user review (Step 8), follow task-workflow Step 9:
commit code changes separately from the plan file, archive via
`./.aitask-scripts/aitask_archive.sh 526`, and push.
