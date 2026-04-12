---
Task: t524_tab_to_switch_to_codeagent.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# t524: Tab to switch minimonitor focus to sibling codeagent pane

## Context

The `ait minimonitor` TUI runs as a narrow side-column pane in the same tmux window as a code agent. The full `ait monitor` already uses `Tab` to cycle between its internal zones (pane list ↔ preview). The minimonitor has no internal preview — it relies on the live codeagent pane sitting next to it. Currently, once the user's terminal focus is on the minimonitor pane, there is no keyboard way back to the adjacent agent pane without reaching for the mouse or a tmux prefix binding.

This task adds a `Tab` keyboard shortcut inside the minimonitor that moves tmux focus to the sibling pane in the same tmux window (typically the codeagent). Only the minimonitor → codeagent direction is required (the reverse would need Textual-side cooperation from the code agent, which we don't control).

## Approach

Add a Tab binding in `MiniMonitorApp` that runs `tmux select-pane` on the first non-self pane in the minimonitor's own tmux window. Mirror the pattern used by `monitor_app.py` (Binding + no-op action + handling in `on_key`) to ensure Tab isn't swallowed by Textual's default focus-chain cycling.

## Files to modify

- `.aitask-scripts/monitor/minimonitor_app.py` (single file)

## Relevant existing code

- `.aitask-scripts/monitor/minimonitor_app.py:93-99` — `BINDINGS` list
- `.aitask-scripts/monitor/minimonitor_app.py:119-126` — `__init__` already stores `self._own_window_id` and `self._own_window_index`
- `.aitask-scripts/monitor/minimonitor_app.py:127-133` — `compose()`, including the `#mini-key-hints` footer text
- `.aitask-scripts/monitor/minimonitor_app.py:144-159` — `on_mount` populates `_own_window_id` from `tmux display-message`
- `.aitask-scripts/monitor/minimonitor_app.py:334-349` — `on_key()` — current handler for up/down inside the card list
- `.aitask-scripts/monitor/monitor_app.py:321,694-695,735-745` — reference pattern for binding-plus-on_key Tab handling
- `.aitask-scripts/monitor/tmux_monitor.py:307-330` — existing `find_companion_pane_id`; not directly reused (we want the non-companion pane here), but confirms the shape of `tmux list-panes` parsing

## Implementation steps

### 1. Add `Tab` to `BINDINGS` (line ~93)

Add a new binding entry so the key is registered with Textual and doesn't fall through to the default focus-chain handler:

```python
BINDINGS = [
    Binding("tab", "focus_sibling_pane", "Focus agent", show=False),
    Binding("j", "tui_switcher", "Jump TUI", show=False),
    Binding("q", "quit", "Quit", show=False),
    Binding("s", "switch_to", "Switch", show=False),
    Binding("i", "show_task_info", "Task Info", show=False),
    Binding("r", "refresh", "Refresh", show=False),
]
```

### 2. Add a no-op `action_focus_sibling_pane` method

Needed because Textual requires the action to exist when a binding references it. The real logic lives in `on_key` (matches `monitor_app.py:694-695` pattern so Tab is consumed before Textual's default focus cycling).

```python
def action_focus_sibling_pane(self) -> None:
    """No-op — Tab is handled in on_key. Exists for Binding registration."""
```

Place this alongside the other `action_*` methods (near `action_switch_to` at line ~381).

### 3. Handle Tab in `on_key` (line ~334)

Insert a Tab branch right after the modal-screen guard and before the up/down handling:

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

    # Up/Down navigate within pane list
    if key == "up":
        ...
```

### 4. Add the `_focus_sibling_pane` helper method

New method on `MiniMonitorApp`. Placed near the other `_*` helpers (e.g. after `_nav` around line ~363). Logic:

1. Read own pane id from `os.environ.get("TMUX_PANE", "")`.
2. If empty or `self._own_window_id` is missing → `self.notify("Not inside tmux", severity="warning")` and return.
3. Run `tmux list-panes -t <own_window_id> -F "#{pane_id}"` with a 5s timeout.
4. On any subprocess exception → `self.notify("tmux error", severity="error")` and return.
5. On non-zero exit → `self.notify("tmux list-panes failed", severity="error")` and return.
6. Parse stdout lines; filter out blanks and the own pane id.
7. If list is empty → `self.notify("No other pane in this window", severity="warning")` and return.
8. Run `tmux select-pane -t <first_other_pane>` with a 5s timeout, wrapped in the same try/except.
9. On failure notify `"select-pane failed"` severity=error.

No additional imports needed — `os`, `subprocess` are already imported at lines 14-15.

The selection deliberately picks the first non-self pane rather than using a companion-detection heuristic: the minimonitor's own window typically contains exactly two panes (minimonitor + code agent), and using a simple non-self filter keeps behavior predictable even in unusual layouts. If future windows carry more than one sibling, `tmux select-pane -t` of the first one is still a sensible default.

### 5. Convert the key hints footer to a custom multi-line layout

Rather than squeezing every binding onto a single 40-column line, turn the existing `#mini-key-hints` Static into a multi-line custom footer that shows **all** minimonitor keybindings (including the new `tab`). These bindings all use `show=False`, so Textual's standard `Footer` would not render them — this custom block is the only place users see them.

**CSS change** (inside the `CSS = """..."""` block, line ~60):
```css
#mini-key-hints {
    dock: bottom;
    height: auto;     /* was: height: 1; */
    background: $surface;
    color: $text-muted;
    padding: 0 1;
}
```
`height: auto` lets the Static grow to the number of lines it contains.

**Text change** (inside `compose`, line ~131):

Replace the single-line string with a multi-line layout. Two lines comfortably fit in a ~40-column column and cover every binding:

```python
yield Static(
    "tab:agent  s/\u2191\u2193:switch  i:info\n"
    "j:jump     r:refresh  q:quit",
    id="mini-key-hints",
)
```

(The exact alignment is cosmetic — what matters is that every binding the user can press is visible.)

## Edge cases covered

- Modal screen active (e.g. `TaskDetailDialog`): early return in `on_key` leaves Tab to the modal.
- Not inside tmux: `on_mount` already shows "Not inside tmux"; the Tab handler also guards on `TMUX_PANE`/`_own_window_id`.
- Only the minimonitor pane in the window: user notification, no action taken.
- tmux subprocess failure: user notification, no crash.

## Verification

Manual test inside an `aitasks` tmux session:

1. Start a code agent window that also spawns a minimonitor side pane (the standard setup). Confirm the layout: one wide code-agent pane plus a narrow minimonitor pane in the same window.
2. Focus the minimonitor pane (click or use a tmux keybind). Press `Tab`. Expected: tmux focus moves to the sibling code-agent pane.
3. Focus the minimonitor pane again. Press `i`, `j`, `s`, `r`, `q` to confirm the other bindings still behave as before (regression check).
4. Open a modal via `i` (Task Info). Press `Tab`. Expected: Tab reaches the modal (closes it or moves focus within it — not our switcher).
5. Lint the changed file:
   ```bash
   python -m py_compile .aitask-scripts/monitor/minimonitor_app.py
   ```

## Follow-up task to create after implementation

After this task is implemented and we have observed the real-world behavior of the new `Tab` binding — specifically any edge cases, tmux quirks, or sibling-pane detection gotchas — create a follow-up task for an analogous `Enter` binding in the minimonitor. The intent: while the minimonitor TUI is active, pressing `Enter` should send an `Enter` keystroke to the **sibling codeagent pane that is visible next to the minimonitor** in the same tmux window — NOT to whichever agent card happens to be focused in the minimonitor's card list. This is distinct from `monitor_app.py:751-755`, which targets the focused pane inside the full monitor's own card list; here the target is always the pane physically adjacent to the minimonitor (the same pane that `Tab` from t524 will jump focus to).

The follow-up needs to incorporate whatever lessons `Tab` taught us (e.g. how to reliably identify the "agent" pane when there are multiple siblings, how to scope the binding when a modal is open, whether `on_key` handling is required vs. Binding alone, etc.).

**After the code change is committed and reviewed (Step 8, before Step 9 archival), create the follow-up task via:**

```bash
./.aitask-scripts/aitask_create.sh --batch \
  --name "enter_to_send_enter_to_codeagent" \
  --priority medium \
  --effort low \
  --issue-type feature \
  --labels aitask_monitormini \
  --depends 524 \
  --desc-file - <<'TASK_DESC'
In `ait minimonitor`, add an `Enter` keyboard shortcut that sends an `Enter` keystroke to the **sibling codeagent pane that sits next to the minimonitor in the same tmux window** — i.e. the same target pane that t524's `Tab` binding switches focus to. The Enter is NOT routed to whichever MiniPaneCard happens to be focused in the minimonitor's card list. The card selection in the minimonitor is irrelevant to this action; the target is always the physically adjacent pane.

This is a follow-up to t524 (Tab to switch focus to the sibling codeagent pane). Before implementing, read the archived plan/notes for t524 (`aiplans/archived/p524_*.md`) to pick up any edge cases, tmux quirks, or sibling-pane detection gotchas learned while wiring up the Tab binding — reuse the same "find the non-minimonitor pane in the current tmux window" helper that t524 introduces.

Implementation sketch:
- Add `Binding("enter", "send_enter_to_sibling", ...)` + `on_key` handler (same pattern as t524's Tab binding).
- When triggered, resolve the sibling pane id (reuse the helper from t524 — do NOT duplicate the lookup logic), then run `tmux send-keys -t <sibling_pane_id> Enter`.
- The binding must NOT fire when a modal screen is active (e.g. TaskDetailDialog) — carry the same modal guard used for Tab.
- Reference for the keystroke mechanic (but NOT the targeting logic): `monitor_app.py:751-755`, which sends Enter to a focused agent pane. In the minimonitor case the target is fixed (the sibling), not derived from card focus.

Key files:
- `.aitask-scripts/monitor/minimonitor_app.py` — the minimonitor TUI (add new binding + handler, reuse t524's sibling-pane helper)
- `.aitask-scripts/monitor/monitor_app.py:751-755` — reference for the send-keys mechanic only

Update the custom multi-line footer introduced in t524 to include an `enter:send` hint.
TASK_DESC
```

The exact task metadata (priority, description) can be fine-tuned at Step 8 once we know the shape of the gotchas, but the above gives a sensible default.

## Step 9 reference

After implementation, user review (Step 8), and creation of the follow-up task above, follow task-workflow Step 9 (Post-Implementation) for commit, archive via `./.aitask-scripts/aitask_archive.sh 524`, and push.

## Final Implementation Notes

- **Actual work done:** All five plan steps implemented exactly as designed in a single file, `.aitask-scripts/monitor/minimonitor_app.py`:
  1. Added `Binding("tab", "focus_sibling_pane", "Focus agent", show=False)` at the top of `BINDINGS`.
  2. Added no-op `action_focus_sibling_pane` in the Actions section (satisfies the Binding; real logic lives in `on_key`).
  3. Inserted a `tab` branch in `on_key` immediately after the modal-screen guard; the branch calls `_focus_sibling_pane()` and stops/prevents the event so Textual's default focus-chain cycling can't swallow it.
  4. Added `_focus_sibling_pane()` helper: reads `TMUX_PANE`, runs `tmux list-panes -t <own_window_id> -F "#{pane_id}"`, filters out own pane, and calls `tmux select-pane -t <first_other>`. Guards against missing tmux env, subprocess failures, and "only one pane in the window" via `self.notify(...)` with appropriate severity. Also explicitly checks the `select-pane` return code.
  5. Converted the `#mini-key-hints` Static to a two-line layout (`"tab:agent  s/\u2191\u2193:switch  i:info\nj:jump     r:refresh  q:quit"`) and switched the CSS rule from `height: 1` to `height: auto` so all bindings are visible in the narrow side column.
- **Deviations from plan:** None of substance. The only addition beyond the plan was an explicit non-zero exit-code check on the `tmux select-pane` call (the plan only mentioned catching subprocess exceptions; I added a return-code notification too for symmetry with the `list-panes` check).
- **Issues encountered:** None during implementation. `python -m py_compile` passed on the first attempt.
- **Key decisions:**
  - Followed the `monitor_app.py` Binding + no-op action + `on_key` pattern rather than a pure Binding/action. This matches the precedent set by the full monitor for Tab handling and sidesteps Textual's default focus-chain cycling being triggered before the app-level binding.
  - Chose "first non-self pane in the window" as the targeting strategy (rather than reusing `find_companion_pane_id` inverted, or using tmux directional `select-pane -L/-R`). The minimonitor's own window almost always has exactly one sibling — the code agent — so the simple approach is robust to either left or right placement of the minimonitor column.
  - Multi-line footer uses a plain string with `\n` and `height: auto` rather than stacking multiple `Static` widgets. Simpler, and keeps all binding hints in one place.
- **Notes for follow-up task (Enter → sibling codeagent):**
  - The `_focus_sibling_pane` helper is the natural reuse point for the follow-up: the Enter handler should call the same "find first non-self pane in my window" logic but then use `tmux send-keys -t <sibling> Enter` instead of `select-pane`. Consider refactoring the pane-id resolution into its own method (e.g. `_find_sibling_pane_id() -> str | None`) during the follow-up so both handlers share it without duplication.
  - The `Binding + on_key` pattern used here should be reused for Enter as well — Textual also treats Enter as an activation key, so the same defensive pattern avoids surprises.
  - Error-handling shape (`self.notify(...)` with severity warning/error) is a good template to copy for the follow-up.
  - The modal guard at the top of `on_key` is critical: Enter inside `TaskDetailDialog` must keep working, so the follow-up's branch must live after the modal check too.
  - The multi-line footer introduced in step 5 has room for one more hint: adding `enter:send` to the end of the second line keeps both lines comparable in width.
