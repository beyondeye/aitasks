---
Task: t53_4_create_aitask_import_interactive_mode.md
Parent Task: aitasks/t53_import_gh_issue_as_task.md
Sibling Tasks: aitasks/t53/t53_2_*.md, aitasks/t53/t53_5_*.md
Archived Sibling Plans: aiplans/archived/p53/p53_*_*.md
Branch: main
Base branch: main
---

# Plan: Add interactive mode to aitask_import.sh (t53_4)

## Context

The `aitask_import.sh` script (created by t53_3) currently only supports batch mode. Line 365 has a placeholder: `die "Interactive mode not yet implemented."`. This task adds `run_interactive_mode()` with 4 sub-modes for importing GitHub issues interactively using fzf.

## File to Modify

- `aitask_import.sh` (370 lines currently)

## Implementation Steps

### Step 1: Add `run_interactive_mode()` entry point (~insert after line 279, before argument parsing)

### Step 2: Add `interactive_import_issue()` — shared function for all sub-modes

This wraps the batch mode logic with user interaction: duplicate confirmation, preview, name editing, label editing, priority/effort selection.

### Step 3: Add `interactive_specific_issue()` sub-mode

Simple: `read -rp` for issue number, validate, call `interactive_import_issue`.

### Step 4: Add `interactive_fetch_and_choose()` sub-mode

Fetch open issues, format for fzf with multi-select and preview, call `interactive_import_issue` for each.

### Step 5: Add `interactive_range()` sub-mode

`read -rp` for start/end numbers, validate, loop calling `interactive_import_issue`.

### Step 6: Add `interactive_all_open()` sub-mode

Fetch all, show count, fzf confirmation, then loop.

### Step 7: Update entry point (line 365) — replace `die` with `run_interactive_mode`

### Step 8: Update `show_help()` to document interactive mode

## Function Insertion Order

All new functions go between `run_batch_mode()` (line 279) and argument parsing (line 281):

1. `interactive_import_issue()` — shared core
2. `interactive_specific_issue()`
3. `interactive_fetch_and_choose()`
4. `interactive_range()`
5. `interactive_all_open()`
6. `run_interactive_mode()` — entry point

## Verification

1. `./aitask_import.sh` — launches interactive mode with fzf menu
2. Test all 4 sub-modes
3. Test task name/label editing
4. Test duplicate detection
5. Clean up test tasks

## Post-Review Changes

### Change Request 1 (2026-02-10)
- **Requested by user:** Fix silent exit when using "Fetch open issues and choose" mode
- **Changes made:** Added `< /dev/tty` to all `read` commands in interactive functions to ensure terminal access when stdin is redirected by while-loop herestrings or pipes
- **Files affected:** `aitask_import.sh`

### Change Request 2 (2026-02-10)
- **Requested by user:** Improve label editing with per-label review from GitHub + aitask_create-style add loop
- **Changes made:** Replaced simple comma-separated label input with: (1) per-label Yes/No fzf prompt for each GitHub issue label, (2) loop to add more labels from `labels.txt` or create new ones, following `aitask_create.sh` pattern
- **Files affected:** `aitask_import.sh`

### Change Request 3 (2026-02-10)
- **Requested by user:** Show "No labels kept!" when all GitHub labels are declined
- **Changes made:** Added warning message after the per-label review loop when no labels are kept
- **Files affected:** `aitask_import.sh`

### Change Request 4 (2026-02-10)
- **Requested by user:** Fetch and include issue comments in task description, with author, date/time, and separator
- **Changes made:** Updated `github_fetch_issue` to include `comments` field. Added `github_format_comments()` and `source_format_comments()` dispatcher. Both batch and interactive modes now include formatted comments. Added `--no-comments` batch flag.
- **Files affected:** `aitask_import.sh`

### Change Request 5 (2026-02-10)
- **Requested by user:** Use local timezone for comment timestamps instead of UTC
- **Changes made:** Restructured `github_format_comments` to iterate in bash and use `date -d` for UTC-to-local conversion. Added `utc_to_local()` helper.
- **Files affected:** `aitask_import.sh`

### Change Request 6 (2026-02-10)
- **Requested by user:** Prefix task description with issue created/updated timestamps in local timezone
- **Changes made:** Added `createdAt`/`updatedAt` to `github_fetch_issue`. Both modes now prepend "Issue created: ..., last updated: ..." line to task description (only shows "last updated" if different from created).
- **Files affected:** `aitask_import.sh`

### Change Request 7 (2026-02-10)
- **Requested by user:** Move comment separator to between comments instead of before each
- **Changes made:** Separator `-------` now appears between comments, not before first or after last
- **Files affected:** `aitask_import.sh`

## Final Implementation Notes
- **Actual work done:** Implemented interactive mode with 4 sub-modes (specific issue, fetch & choose, range, all open) plus significant enhancements beyond the original plan: improved label editing with per-label review, issue comment fetching with local timezone conversion, and issue timestamp display.
- **Deviations from plan:** The label editing was substantially enhanced from a simple text input to a two-phase interactive flow. Comment fetching was added as a new feature not in the original task scope.
- **Issues encountered:** `read -erp` fails silently when stdin is redirected (herestrings/pipes in while loops), causing script exit under `set -e`. Fixed by adding `< /dev/tty` to all `read` commands. Also used `set +e`/`set -e` around fzf label selection loops.
- **Key decisions:** Used `utc_to_local()` helper with `date -d` for timezone conversion. Comments included by default in both modes, with `--no-comments` opt-out for batch. Label helpers (`ensure_labels_file`, `get_existing_labels`) duplicated from `aitask_create.sh` rather than sourcing, to keep scripts independent.
- **Notes for sibling tasks:** The `github_fetch_issue` now fetches `comments`, `createdAt`, `updatedAt` fields in addition to the original set. The `source_format_comments()` dispatcher is available for other code to use. The `utc_to_local()` helper converts ISO 8601 UTC timestamps to local timezone.

## Post-Implementation

Follow Step 9 of aitask-pick workflow for archival.
