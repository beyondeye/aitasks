---
Task: t216_3_update_docs_for_ait_sync.md
Parent Task: aitasks/t216_ait_board_out_of_sync_if_changes_from_other_pc.md
Sibling Tasks: aitasks/t216/t216_1_*.md, aitasks/t216/t216_2_*.md, aitasks/t216/t216_4_*.md
Archived Sibling Plans: aiplans/archived/p216/p216_*_*.md
---

# Implementation Plan: t216_3 — Documentation Updates

## Overview

Update all user-facing documentation to cover the new `ait sync` command and board sync integration. Also fix stale Settings keybinding reference (`S` → `O`) from t216_2.

## Step 1: `website/content/docs/commands/_index.md`

- [x] Add `ait sync` row to commands table
- [x] Add usage examples

## Step 2: Create `website/content/docs/commands/sync.md`

- [x] New command doc page: overview, usage, options, batch protocol, interactive mode, how it works

## Step 3: `website/content/docs/board/reference.md`

- [x] Add `s` sync keybinding to keyboard shortcuts table
- [x] Fix `S` → `O` for Settings/Options keybinding
- [x] Add SyncConflictScreen to modal dialogs table
- [x] Fix Settings modal trigger `S` → `O`
- [x] Add `sync_on_refresh` to board_config.json example and settings description

## Step 4: `website/content/docs/board/how-to.md`

- [x] New section: "How to Sync with Remote"
- [x] Fix Settings reference `S` → `O`

## Step 5: `website/content/docs/board/_index.md`

- [x] Brief mention of sync in tutorial section

## Verification

- [x] `cd website && hugo build --gc --minify` — builds without errors (68 pages)
- [x] Review all updated pages for accuracy

## Final Implementation Notes

- **Actual work done:** All 5 steps implemented as planned. Created new `website/content/docs/commands/sync.md` command doc. Updated 4 existing doc files: commands/_index.md (table + examples), board/reference.md (keybindings, modals, settings), board/how-to.md (new sync how-to section + S→O fix), board/_index.md (sync overview mention).
- **Deviations from plan:** Also fixed stale Settings keybinding references (`S` → `O`) in reference.md and how-to.md — this was from t216_2 changing Settings to Options but docs not being updated at the time.
- **Issues encountered:** None — all doc files matched expected structure.
- **Key decisions:** Created a standalone `sync.md` command doc rather than adding to `board-stats.md`, since sync is a distinct command with enough content to warrant its own page.
- **Notes for sibling tasks:**
  - t216_4 (macOS portability): No documentation-relevant findings. The sync command docs accurately describe the portable timeout fallback mechanism.

## Post-Implementation (Step 9)

Archive t216_3, update parent children_to_implement.
