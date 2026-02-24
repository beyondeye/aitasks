---
Task: t228_4_update_board_tui_integration.md
Parent Task: aitasks/t228_improved_task_merge_for_board.md
Sibling Tasks: aitasks/t228/t228_1_*.md, aitasks/t228/t228_2_*.md, aitasks/t228/t228_3_*.md, aitasks/t228/t228_5_*.md
Branch: (current branch - no worktree)
Base branch: main
---

# Plan: t228_4 — Update Board TUI Integration

## Goal

Update `_run_sync()` in the board to handle the new `AUTOMERGED` batch status from `ait sync`.

## Steps

### 1. Add `AUTOMERGED` Status Handling

In `_run_sync()` (around line 2278), add a new elif branch:

```python
elif status_line == "AUTOMERGED":
    if show_notification:
        self.notify("Sync: Auto-merged conflicts", severity="information")
```

This should be placed before the `CONFLICT:` check so it's tested first (or after — order doesn't matter since they're distinct strings).

### 2. Verify Existing `CONFLICT:` Behavior

The `CONFLICT:` output from sync now only contains truly unresolvable files (auto-mergeable files have already been resolved). No changes needed to `SyncConflictScreen` — it already works correctly with the reduced conflict list.

## Scope

This is a minimal change — just one `elif` branch. The heavy lifting is in t228_3.
