---
Task: t216_3_update_docs_for_ait_sync.md
Parent Task: aitasks/t216_ait_board_out_of_sync_if_changes_from_other_pc.md
Sibling Tasks: aitasks/t216/t216_1_*.md, aitasks/t216/t216_2_*.md, aitasks/t216/t216_4_*.md
Archived Sibling Plans: aiplans/archived/p216/p216_*_*.md
---

# Implementation Plan: t216_3 — Documentation Updates

## Overview

Update all user-facing documentation to cover the new `ait sync` command and board sync integration.

## Step 1: `website/content/docs/commands/_index.md`

Add `ait sync` row to the commands table.

## Step 2: `website/content/docs/commands/board-stats.md` (or new file)

Add `## ait sync` section: usage, batch output protocol, interactive mode, conflict resolution, network handling.

## Step 3: `website/content/docs/board/reference.md`

- Add `s` to keyboard shortcuts table
- Add "Sync with Remote" to command palette list
- Add `sync_on_refresh` to settings/config section
- Add `SyncConflictScreen` to modal dialogs reference

## Step 4: `website/content/docs/board/how-to.md`

New section: "How to Sync with Remote" — manual sync, auto-sync setting, conflict handling, no-network behavior.

## Step 5: `website/content/docs/board/_index.md`

Brief mention of sync in features overview.

## Verification

- [ ] `cd website && hugo build --gc --minify` — builds without errors
- [ ] Review all updated pages for accuracy

## Post-Implementation (Step 9)

Archive t216_3, update parent children_to_implement.
