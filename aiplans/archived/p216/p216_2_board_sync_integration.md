---
Task: t216_2_board_sync_integration.md
Parent Task: aitasks/t216_ait_board_out_of_sync_if_changes_from_other_pc.md
Sibling Tasks: aitasks/t216/t216_1_*.md, aitasks/t216/t216_3_*.md, aitasks/t216/t216_4_*.md
Archived Sibling Plans: aiplans/archived/p216/p216_*_*.md
---

# Implementation Plan: t216_2 — Board Sync Integration

## Overview

Integrate `ait sync --batch` into the board TUI: add SyncConflictScreen modal, periodic sync on auto-refresh, manual sync via `s` key and command palette, settings toggle.

## All changes in `aiscripts/board/aitask_board.py`

### Step 1: Add `SyncConflictScreen` modal (~line 1660)

New `ModalScreen` subclass showing conflicted files with "Resolve Interactively" / "Dismiss" buttons. Reuse existing CSS IDs for consistent styling.

### Step 2: Add sync worker methods to `KanbanApp`

**`_run_sync(show_notification=True)`** — `@work(exclusive=True)`:
- `subprocess.run(["./aiscripts/aitask_sync.sh", "--batch"], capture_output=True, text=True, timeout=30)`
- Parse output, handle CONFLICT (show dialog via `call_from_thread`), NO_NETWORK, errors
- Refresh board after sync

**`_show_conflict_dialog(files)`** — main thread callback:
- Push `SyncConflictScreen`, on dismiss launch interactive sync or just refresh

**`_run_interactive_sync()`** — `@work(exclusive=True)`:
- Pattern from `run_aitask_pick`: `_find_terminal()` → `Popen` or `suspend()` fallback

### Step 3: Add `action_sync_remote()` and `s` keybinding

- Action method: check modal, call `_run_sync(show_notification=True)`
- Add `Binding("s", "sync_remote", "Sync")` to BINDINGS list

### Step 4: Modify `_auto_refresh_tick()` (line 1977)

If `sync_on_refresh` setting True AND `DATA_WORKTREE.exists()` → `_run_sync(False)` instead of `action_refresh_board()`

### Step 5: Command palette entries

Add "Sync with Remote" to both `discover()` and `search()` in `KanbanCommandProvider`.

### Step 6: Settings screen toggle

Add `sync_on_refresh` CycleField ("no"/"yes") to `SettingsScreen.compose()`. Update `save_settings()` to include it in the dismiss result.

### Step 7: Update subtitle

Modify `_update_subtitle()` to append " + sync" when `sync_on_refresh` is enabled.

## Verification

- [x] Press `s` → sync notification appears
- [x] Command palette → "Sync with Remote" available
- [x] Settings → "Sync on refresh" toggle → subtitle updates
- [ ] Auto-refresh with sync → runs silently
- [ ] Conflict scenario → dialog appears → resolve option works

## Post-Review Changes

### Change Request 1 (2026-02-23)
- **Requested by user:** Add "Syncing..." progress notification when sync starts
- **Changes made:** Added `self.notify("Syncing...", ...)` at start of `_run_sync()` — then removed it because it overlapped with the result toast
- **Files affected:** `aiscripts/board/aitask_board.py`

### Change Request 2 (2026-02-23)
- **Requested by user:** Change Settings keybinding from `S` to avoid confusion with `s` (Sync)
- **Changes made:** Changed Settings binding from `S` to `O` (Options)
- **Files affected:** `aiscripts/board/aitask_board.py`

### Change Request 3 (2026-02-23)
- **Requested by user:** Move Sync shortcut in footer bar to appear right after Refresh
- **Changes made:** Moved `Binding("s", "sync_remote", "Sync")` in BINDINGS list to be right after the Refresh binding
- **Files affected:** `aiscripts/board/aitask_board.py`

## Final Implementation Notes

- **Actual work done:** All 7 plan steps implemented in `aiscripts/board/aitask_board.py` — SyncConflictScreen modal, sync worker methods (_run_sync, _show_conflict_dialog, _run_interactive_sync), action_sync_remote with `s` keybinding, auto-refresh sync integration, command palette entries, settings toggle, subtitle update.
- **Deviations from plan:** (1) Settings keybinding changed from `S` to `O` (Options) to avoid confusion with `s` (Sync). (2) Initial "Syncing..." progress toast was added then removed because it overlapped with the result toast when sync completed quickly. (3) Sync binding placed right after Refresh in BINDINGS for logical footer grouping.
- **Issues encountered:** None — all plan references matched the codebase exactly. Syntax verification passed on every edit.
- **Key decisions:** No progress indicator beyond result toast — Textual doesn't support updating notifications, and the sync typically completes fast enough that a start toast overlaps. Silent sync during auto-refresh shows no notifications at all.
- **Notes for sibling tasks:**
  - t216_3 (docs): Document the new `s` key, `O` for Options, command palette "Sync with Remote" entry, and the "Sync on refresh" setting toggle
  - t216_4 (macOS portability): The board changes are pure Python/Textual with no platform-specific code. The sync subprocess call uses `./aiscripts/aitask_sync.sh --batch` which is already tested for portability in t216_1.

## Post-Implementation (Step 9)

Archive t216_2, update parent children_to_implement.
