---
Task: t460_arrows_navigation_in_task_history.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The Task History screen in the codebrowser TUI has two panes: a left task list and a right detail/metadata pane. Currently, up/down arrows navigate within each pane, and Tab toggles focus between them. The user wants left/right arrow keys for more intuitive pane switching, and wants to restrict focusable fields in the right pane to only those with an "enter" action (removing focus from purely static metadata fields).

## Plan

### Change 1: Make `MetadataField` non-focusable (`history_detail.py`)

`MetadataField` (priority, effort, type, labels, commit date) is purely display — no enter action. Make it non-focusable:

- Set `can_focus = False`
- Remove the `on_key` handler (won't receive key events)
- Remove the `:focus` CSS rule

Fields that remain focusable (all have enter actions):
- `_BackButton` → go back
- `IssueLinkField` → open URL
- `PullRequestLinkField` → open URL
- `CommitLinkField` → open commit URL
- `ChildTaskField` → navigate to child
- `SiblingCountField` → open sibling picker
- `AffectedFileField` → open file in codebrowser

### Change 2: Add left/right arrow navigation (`history_screen.py`)

Add bindings and actions to `HistoryScreen`:

- Add `Binding("left", "focus_left", "Focus list")` and `Binding("right", "focus_right", "Focus detail")` to `BINDINGS` so they appear in the footer
- `action_focus_right`: Move focus to first focusable field in detail pane
- `action_focus_left`: Cycling behavior:
  - From detail pane → focus current task in task list (or recent list)
  - From task list → remember last focused item, switch to recent list
  - From recent list → restore last focused item in task list
  - No focus → focus task list

### Change 3: Load more scroll fix (`history_list.py`)

After loading a chunk via "Load more", defer `scroll_visible()` with `set_timer(0.05)` so the layout recalculates before scrolling.

## Post-Review Changes

### Change Request 1 (2026-03-25)
- **Requested by user:** Left/right arrows should appear in footer bindings
- **Changes made:** Added `Binding("left", ...)` and `Binding("right", ...)` to `BINDINGS`
- **Files affected:** `history_screen.py`

### Change Request 2 (2026-03-25)
- **Requested by user:** First left arrow press should focus full task list (not recent list); left arrow should work when detail pane is empty
- **Changes made:** Redesigned `action_focus_left` with cycling: detail→task list→recent list→task list. Removed `detail.has_focus_within` guard for no-focus state. `action_focus_right` no longer requires left pane focus.
- **Files affected:** `history_screen.py`

### Change Request 3 (2026-03-25)
- **Requested by user:** Load more doesn't scroll; left arrow from detail should focus current task (not top visible)
- **Changes made:** Added deferred `scroll_visible()` in `_load_chunk()`. Updated `action_focus_left` to search both task list and recent list for current task ID.
- **Files affected:** `history_list.py`, `history_screen.py`

### Change Request 4 (2026-03-25)
- **Requested by user:** When cycling recent→task list, restore last focused task instead of top visible
- **Changes made:** Added `_last_task_list_focus_id` tracking — remembered when leaving task list, restored when returning
- **Files affected:** `history_screen.py`

## Final Implementation Notes
- **Actual work done:** Made `MetadataField` non-focusable, added left/right arrow bindings with cycling focus between detail pane, full task list, and recent list. Fixed load more scroll issue.
- **Deviations from plan:** Original plan had simpler left/right behavior; iterated through 4 review rounds to refine cycling logic and scroll behavior.
- **Key decisions:** Used `set_timer(0.05)` for deferred scroll after load more (layout needs time to recalculate). Used `_last_task_list_focus_id` to remember last focused task when cycling between lists.
