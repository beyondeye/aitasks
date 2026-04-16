---
Task: t576_wrong_codeangent_preview_shown_on_refresh.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Fix monitor TUI preview content desync on refresh (t576)

## Context

In the monitor TUI (`ait monitor`), the agent list and preview pane get out of sync after a 3s refresh. The user selects an agent (e.g., agent-pick 575) with arrow keys — the preview correctly shows 575's output. When the refresh timer fires, the preview content switches to the first agent's content, but the selection highlight stays on 575.

**Regression introduced by t545** (`df85ef9f`, Apr 14). That commit added a guard in `_restore_focus()` that returns early if a PaneCard is already focused (to prevent overriding user arrow key navigation). The guard correctly restores `_focused_pane_id`, but **never calls `_update_content_preview()`** afterward — leaving the preview stale. Before t545, `_restore_focus` always called `card.focus()` → `on_descendant_focus` → `_update_content_preview()`, which self-corrected any stale preview.

## Root Cause

In `_refresh_data()` (monitor_app.py:682-688), the preview is updated **before** focus is restored:

```python
self._rebuild_pane_list()          # line 682: may disrupt focus state via DOM events
self._update_content_preview()     # line 683: renders preview using _focused_pane_id
self.call_after_refresh(           # line 688: restores correct focus LATER
    self._restore_focus, saved_pane_id, saved_zone
)
```

`_restore_focus()` (line 776) can change `_focused_pane_id` (via the guard at line 788-793, or via the find-and-focus fallback at line 796-803), but it **never calls `_update_content_preview()`**. The preview stays showing whatever was rendered at line 683.

The slow path in `_rebuild_pane_list()` (full DOM rebuild when pane set changes — e.g. companion panes fluctuating with active agents) can trigger focus events that change `_focused_pane_id` to a different card before line 683 executes. Then `_restore_focus` fixes `_focused_pane_id` back but doesn't re-render.

## Fix

**File:** `.aitask-scripts/monitor/monitor_app.py`

### Step 1: Add `_update_content_preview()` to `_restore_focus()`

Add a single `self._update_content_preview()` call at the **end** of `_restore_focus()` (after the existing return paths). Restructure the method to fall through to a single exit point instead of having multiple `return` statements:

**Current structure (line 776-803):**
```python
def _restore_focus(self, pane_id, zone):
    if zone == Zone.PREVIEW:
        ...focus preview...
        return                  # ← no preview update
    if focused is valid PaneCard:
        self._focused_pane_id = focused.pane_id
        return                  # ← no preview update
    if pane_id is None:
        return                  # ← no preview update
    for card matching pane_id:
        card.focus()
        self._focused_pane_id = card.pane_id
        return                  # ← no preview update
```

**New structure:** Replace each early `return` with fall-through logic, add a single `_update_content_preview()` call at the end. The Preview zone path keeps its early return since the preview panel is being focused (not the pane list).

```python
def _restore_focus(self, pane_id, zone):
    if zone == Zone.PREVIEW:
        ...focus preview...
        self._update_content_preview()
        return
    focused = self.focused
    if isinstance(focused, PaneCard) and focused.pane_id in self._snapshots:
        self._focused_pane_id = focused.pane_id
    elif pane_id is not None:
        for card in self.query("#pane-list PaneCard"):
            if hasattr(card, "pane_id") and card.pane_id == pane_id:
                card.focus()
                self._focused_pane_id = card.pane_id
                break
    self._update_content_preview()
```

### Step 2: No changes to line 683

Keep `_update_content_preview()` at line 683. On the fast path (most common), it renders correctly with unchanged `_focused_pane_id`. The second call from `_restore_focus` is cheap — `same_pane` is True and the frozen-branch check (line 972) short-circuits unless scrolling. On the slow path, the second render corrects the stale preview.

## Verification

1. Open the monitor TUI with multiple agents: `ait monitor`
2. Use arrow keys to select a non-first agent in the list
3. Wait for the 3s refresh to fire
4. **Expected:** Preview content stays showing the selected agent's output
5. Test with structural changes (open/close a tmux window) to exercise the slow path
6. Test enabling auto-switch (press `a`) — ensure preview follows correctly
7. Test arrow key navigation during refresh — ensure user selection is not lost (t545 regression)

## Final Implementation Notes

- **Actual work done:** Restructured `_restore_focus()` in `monitor_app.py` to call `_update_content_preview()` after determining the final focus state. Converted the guard and find-and-focus paths from separate early `return` statements to `if/elif` fall-through with a single `_update_content_preview()` at the end.
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Kept the existing `_update_content_preview()` at line 683 in `_refresh_data()` for immediate preview update on the fast path. The second call from `_restore_focus` is cheap (same_pane short-circuits) but necessary to correct the slow path.

## Step 9 (Post-Implementation)

After approval and commit, archive t576 and push.
