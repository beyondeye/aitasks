---
Task: t260_8_board_integration_view_filter.md
Parent Task: aitasks/t260_taskfrompullrequest.md
Sibling Tasks: aitasks/t260/t260_1_*.md through t260_7_*.md
Archived Sibling Plans: aiplans/archived/p260/p260_1_*.md, aiplans/archived/p260/p260_2_*.md
Worktree: (none — current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Board Integration View Filter (t260_8)

## Overview

Add a toggle-based "Integration view" to the board TUI that filters tasks to show only those linked to GitHub/GitLab/Bitbucket issues or pull requests. Also ensure all URL fields (issue, pull_request) are fully clickable in the task detail dialog.

## Steps

### 1. Add filter state to `KanbanApp.__init__()`

```python
self.integration_filter_active = False
```

Optionally load persisted state:
```python
self.integration_filter_active = self.manager.settings.get("integration_view_active", False)
```

### 2. Add keybinding `g` for "Git View"

In `BINDINGS` list:
```python
Binding("g", "toggle_integration_view", "Git View"),
```

### 3. Implement `action_toggle_integration_view()`

Toggle the filter, update UI, call `apply_filter()`, show notification.

### 4. Extend `apply_filter()` with integration filter

After existing search filter logic, add:
```python
if visible and self.integration_filter_active:
    meta = card.task_data.metadata
    has_issue = bool(meta.get("issue", ""))
    has_pr = bool(meta.get("pull_request", ""))
    if not (has_issue or has_pr):
        visible = False
```

### 5. Update search box placeholder when filter is active

Change placeholder to indicate integration view: `"🔗 Integration view — issues/PRs only (g to toggle)"`.

### 6. Enhanced card display in integration view

When integration view is active, show full URLs on task cards (not just badges).

### 7. Verify PullRequestField clickability

Ensure `PullRequestField` (from t260_2) has:
- `can_focus = True`
- `on_key()` with Enter → `webbrowser.open()`
- `(Enter to open)` hint in render
- Same pattern as `IssueField` at line 1026

### 8. Persist filter state (optional)

Save to `manager.settings["integration_view_active"]` and reload on startup.

## Verification

1. Toggle integration view with `g` — only issue/PR-linked tasks shown
2. Combine with search filter — both filters work as intersection
3. Enter on IssueField opens URL in browser
4. Enter on PullRequestField opens URL in browser
5. Visual feedback when filter is active (placeholder, notification)
6. Empty board handled gracefully when no integration tasks exist

## Final Implementation Notes

- **Actual work done:** Added dynamic search box placeholder text that updates when switching between view modes (All/Git/Implementing) in the board TUI. Also created the missing child task file required for the archival workflow.
- **Deviations from plan:** The original plan described implementing the full integration view from scratch (filter state, keybinding, toggle action, apply_filter logic, PullRequestField). However, all of this was already implemented by t273 (view modes) and t260_2 (PullRequestField). The actual remaining work was limited to: (1) mode-specific search placeholders, (2) creating the missing child task file. Plan steps 6 (enhanced card display with full URLs) and 8 (persist filter state) were dropped per user decision.
- **Key decisions:** View mode persistence was explicitly declined by the user. Enhanced card display (showing full URLs instead of badges) was not implemented — the existing badge indicators (GH, GL, BB, PR:GH, etc.) are sufficient.
- **Notes for sibling tasks:** This was the last child of t260. The entire PR import workflow is now complete across all 8 children.

## Step 9 Reference

Post-implementation: archive child task via `./aiscripts/aitask_archive.sh 260_8`
