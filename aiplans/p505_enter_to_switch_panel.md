---
Task: t505_enter_to_switch_panel.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

In the ait monitor TUI, users often want to quickly confirm an agent's question (send Enter) without switching to the preview panel first. Currently, Enter in the agent list does nothing useful — users must Tab to preview, press Enter, then Tab back. This task adds a shortcut: pressing Enter in the agent list sends Enter directly to the agent's tmux pane, staying in the agent list.

## Implementation Plan

**File:** `.aitask-scripts/monitor/monitor_app.py`

### 1. Add Enter binding for footer display (line ~269)

Add to `BINDINGS` list:
```python
Binding("enter", "send_enter", "Send ↵", show=True),
```

### 2. Add no-op action method (after `action_switch_zone` at line ~571)

```python
def action_send_enter(self) -> None:
    """No-op — Enter is handled in on_key. Exists for Footer display only."""
```

This mirrors the pattern used for `action_switch_zone` (Tab).

### 3. Handle Enter in `on_key()` for PANE_LIST zone (after line 618, before the PREVIEW forwarding block)

```python
# In pane-list zone: Enter sends Enter to the focused agent's tmux pane
if key == "enter" and self._active_zone == Zone.PANE_LIST:
    if self._focused_pane_id and self._monitor:
        self._monitor.send_keys(self._focused_pane_id, "Enter")
        self.call_later(self._fast_preview_refresh)
    event.stop()
    event.prevent_default()
    return
```

### 4. Footer visibility — no changes needed

The existing `check_action()` logic already handles this correctly:
- PANE_LIST zone: `action != "switch_zone"` → True for `send_enter` → **shown**
- PREVIEW zone: `action == "switch_zone"` → False for `send_enter` → **hidden** (Enter is already forwarded as part of all-keys-to-tmux in preview mode)

## Verification

1. Run `shellcheck` on any modified shell scripts (none expected)
2. Manual test: launch `ait monitor`, verify Enter in agent list sends Enter to the agent's tmux pane
3. Verify footer shows "Send ↵" when in agent list, hidden when in preview
4. Verify Tab switching still works normally
5. Verify Enter still works normally in preview mode (forwarded to tmux)

## Final Implementation Notes
- **Actual work done:** Added Enter key shortcut in monitor TUI pane list that sends Enter directly to the focused agent's tmux pane without switching panels. Added footer binding display, no-op action method, and key handler in `on_key()`.
- **Deviations from plan:** None — implementation matched the plan exactly.
- **Issues encountered:** None.
- **Key decisions:** Followed the existing Tab key pattern (binding + no-op action + on_key handler) for consistency. Existing `check_action()` logic already handles zone-aware footer visibility correctly without modification.
