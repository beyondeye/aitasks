---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [stats_ui, textual, tui]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-10-26 15:58
updated_at: 2026-10-26 16:19
---

## Origin

Reported from the `aitasks_go` project (the Go / Bubble Tea port of the aitasks TUIs). It came from its t13_5 review (Go port of the stats modals) and was carried by aitasks_go t26. Both defects live in the framework-owned `.aitask-scripts/stats/` code. The Go port deliberately implements the *intended* behaviour, and does not patch its vendored copy of the scripts.

## Defect 1 — PaneSelector: Enter on the focused Cancel button saves

**Where:** `.aitask-scripts/stats/modals/pane_selector.py` (`PaneSelectorModal.on_key`, around lines 129-133 as of framework v0.40.0):

```python
def on_key(self, event) -> None:
    if event.key == "enter":
        self.dismiss(self._selected_pane_ids())
        event.stop()
```

The screen-level `on_key` intercepts **every** Enter before the focused Button's own binding runs. So pressing Enter while the **Cancel** button is focused dismisses the modal *with* the current selection (it saves) instead of cancelling.

**Repro:**
1. `ait stats` → layouts panel → `n` (new custom). Type a name and press Enter.
2. In the PaneSelector, toggle a pane (space), then press Tab until **Cancel** is focused.
3. Press Enter. Expected: the modal cancels, and no layout is saved or changed. Actual: the layout is saved with the selection.

aitasks_go confirmed it with a Textual Pilot probe of the real `PaneSelectorModal`: Enter with Cancel focused dismisses with the selection.

**Proposed fix:** only treat Enter as the save shortcut when focus is not on a Button, so the Button binding handles Save/Cancel:

```python
def on_key(self, event) -> None:
    if event.key == "enter" and not isinstance(self.focused, Button):
        self.dismiss(self._selected_pane_ids())
        event.stop()
```

(`Button` is already imported for `on_button_pressed`.) Equivalently, check `isinstance(self.focused, SelectionList)`.

## Defect 2 — `StatsApp._cycle_focus`: the guard is always true, so the panel cycle never runs

**Where:** `.aitask-scripts/stats/stats_app.py` (`_cycle_focus`, around lines 646-648 as of v0.40.0):

```python
def _cycle_focus(self, forward: bool) -> None:
    if self.screen is not self:
        # A modal is on top — let its own bindings handle Tab.
        return
```

`self` is the `App`, and an App is never its own screen, so `self.screen is not self` is **always** true. The method returns immediately on every call, so the `tab` / `shift+tab` bindings (`action_focus_next_panel` / `action_focus_prev_panel`) never do what they were written to do. That means no session_list → sidebar → layouts cycle order and no `_apply_focus_hint()` refresh. It only *appears* to work because the Screen's default Tab focus_next happens to move through the same ListViews.

**Repro:** in a multi-session `ait stats`, press Tab repeatedly and watch the `.focused_panel` left-border hint. It is not refreshed by the action, and the order follows the default focus chain rather than the documented cycle. A breakpoint or print after the guard never fires.

**Proposed fix:** detect a modal by the screen stack instead:

```python
if len(self.screen_stack) > 1:
    # A modal is on top — let its own bindings handle Tab.
    return
```

(or `if isinstance(self.screen, ModalScreen): return`).

**Note:** fixing the guard *activates* the intended cycle order and `_apply_focus_hint()` for the first time. Check that the `.focused_panel` styling and the Tab order behave as intended, since they have effectively never run.

## Reference

The aitasks_go Go port (`demos/stats/go/` in that repo) already implements both intended behaviours: Enter on a focused Cancel cancels, and Tab cycles session → sidebar → layouts with the focus hint. It's documented in its `aidocs/porting/stats.md`.
