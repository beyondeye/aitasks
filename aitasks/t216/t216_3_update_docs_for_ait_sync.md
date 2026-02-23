---
priority: medium
effort: low
depends: [t216_2, t216_1, t216_2]
issue_type: documentation
status: Implementing
labels: [aitask_board]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-23 15:51
updated_at: 2026-02-23 22:44
---

## Context

Parent task t216 adds a new `ait sync` command and board sync integration. This child task updates all user-facing documentation to cover the new functionality.

Depends on t216_1 (sync script) and t216_2 (board integration) — needs to document what was actually implemented.

## Key Files to Modify

1. **`website/content/docs/commands/_index.md`** — Add `ait sync` to the command table
2. **`website/content/docs/commands/board-stats.md`** — Add `ait sync` section (or create new `sync.md`)
3. **`website/content/docs/board/reference.md`** — Keyboard shortcuts, command palette, settings, modal reference
4. **`website/content/docs/board/how-to.md`** — How-to guide for syncing
5. **`website/content/docs/board/_index.md`** — Brief mention in board overview

## Implementation Plan

### 1. `website/content/docs/commands/_index.md`

Add row to the commands table:
```
| `ait sync`         | Sync task data with remote (push/pull)           |
```

### 2. `website/content/docs/commands/board-stats.md` (or new `sync.md`)

Add `## ait sync` section documenting:
- Purpose and overview
- Usage: `ait sync` (interactive) / `ait sync --batch` (for scripting/automation)
- Batch output protocol: SYNCED, PUSHED, PULLED, NOTHING, CONFLICT, NO_NETWORK, NO_REMOTE, ERROR
- Interactive mode: progress display, conflict resolution flow
- How it works: auto-commit → fetch → rebase → push
- Network handling: 10s timeout per operation, graceful NO_NETWORK fallback
- Works in both data-branch mode and legacy mode

### 3. `website/content/docs/board/reference.md`

- Add `s` → "Sync with Remote" to keyboard shortcuts table
- Add "Sync with Remote" to command palette commands list
- Add `sync_on_refresh` to configuration/settings section
- Add `SyncConflictScreen` to modal dialogs reference

### 4. `website/content/docs/board/how-to.md`

Add new section "How to Sync with Remote" covering:
- Manual sync: press `s` or use command palette
- Auto-sync: enable in Settings (S → Sync on refresh → yes)
- What the sync does (auto-commit, push, pull with rebase)
- Handling conflicts: dialog appears → resolve interactively or dismiss
- No network: warning notification, board continues with local data
- Subtitle indicator: shows "+ sync" when enabled

### 5. `website/content/docs/board/_index.md`

Add brief mention of sync in the features/overview section.

## Verification Steps

1. Review all doc files for accuracy against actual implementation
2. `cd website && hugo build --gc --minify` — verify docs build without errors
3. `cd website && ./serve.sh` — verify pages render correctly (optional, if Hugo is available)
