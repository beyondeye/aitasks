---
Task: t198_doc_settings_screen.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

Task t198: The auto-refresh feature and settings screen were just added to `ait board` (t193). The website documentation needs to be updated to cover these new features.

## Files to modify

1. `website/content/docs/board/how-to.md` — Add a new how-to guide for configuring auto-refresh
2. `website/content/docs/board/reference.md` — Add `S` keybinding, Settings modal, update config section

## Changes

### 1. `how-to.md` — Add "How to Configure Auto-Refresh"

Add a new section at the end of the file (after "How to Open Linked Issues").

### 2. `reference.md` — Multiple updates

- Keyboard Shortcuts: Add `S` row
- Modal Dialogs: Add Settings modal row
- Column Configuration: Update JSON example with `settings` key
- Configuration Files: Update description

## Verification

1. `cd website && hugo build --gc --minify` — should build without errors

## Final Implementation Notes

- **Actual work done:** Updated `how-to.md` with a new "How to Configure Auto-Refresh" section (+21 lines) and updated `reference.md` with keyboard shortcut, modal dialog, config JSON, and config files table entries (+8 lines, -2 lines). Hugo build passes.
- **Deviations from plan:** Skipped documenting the subtitle display per user request (too subtle to be visible).
- **Issues encountered:** None.
- **Key decisions:** Placed the auto-refresh how-to as the last section since it's a less frequently used feature. Kept descriptions concise and consistent with existing documentation style.
