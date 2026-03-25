---
Task: t448_6_documentation_for_history_view.md
Parent Task: aitasks/t448_archived_tasks_in_board.md (archived)
Sibling Tasks: all archived (t448_1 through t448_5, t448_7)
Archived Sibling Plans: aiplans/archived/p448/p448_*_*.md
Worktree: (none)
Branch: main
Base branch: main
---

# Plan: Documentation for History View

## Context

The Completed Tasks History feature was implemented across t448_1 through t448_5 (plus t448_7 for a bug fix). The feature allows users to browse archived/completed tasks directly within the codebrowser TUI. All code is complete — this task adds website documentation to cover the feature.

## Step 1: Update `_index.md` — Add "Viewing Completed Task History" section

File: `website/content/docs/tuis/codebrowser/_index.md`

Add a new section after "Using the Detail Pane" (before "Launching an Explain Session") covering:

- How to open: press `h` to toggle the history screen
- Two-pane layout: task list (left) + task details (right)
- Key features:
  - Reverse-chronological task list ordered by commit history
  - Progressive loading with "Load more" button for older tasks
  - Recently opened tasks section (persistent across sessions)
  - Task details: metadata fields, commit links (clickable), affected files, issue/PR links
  - Sibling task browsing via modal (for child tasks) — press `s` or Enter on sibling field
  - Task/plan content toggle with `v`
  - Label filtering with `l`
  - File navigation: select affected file to open in codebrowser
  - State preservation when switching between history and codebrowser views
  - Left/Right arrow keys for pane navigation

## Step 2: Update `reference.md` — Add History Screen keyboard shortcuts

File: `website/content/docs/tuis/codebrowser/reference.md`

Add a new "History Screen" section after the "Application" shortcuts table:

| Key | Action | Context |
|-----|--------|---------|
| `h` | Toggle completed tasks history view | Global |
| `h` / `Escape` | Return to code browser | History screen |
| `v` | Toggle task/plan content view | History screen |
| `l` | Open label filter dialog | History screen |
| `s` | Open sibling task picker (on child tasks) | History detail |
| `Tab` | Cycle focus between list and detail panes | History screen |
| `Left` | Move focus to list pane (cycles task list / recently opened) | History screen |
| `Right` | Move focus to detail pane | History screen |
| `Enter` | Open link/file or select task (context-dependent) | History detail |
| `Up` / `Down` | Navigate between focusable fields | History detail |

Also add label filter modal and sibling picker modal shortcuts.

## Step 3: Update `how-to.md` — Add "How to Browse Completed Tasks" section

File: `website/content/docs/tuis/codebrowser/how-to.md`

Add a new section at the end covering step-by-step instructions for:
1. Opening history
2. Browsing and loading more tasks
3. Viewing task details
4. Opening commits/issues/PRs in browser
5. Navigating to affected files
6. Browsing sibling tasks
7. Filtering by labels
8. Returning to codebrowser

## Step 4: Verification

1. Run `cd website && hugo build --gc --minify` — verify build succeeds
2. Check internal `relref` links resolve
3. Verify keybinding docs match actual implementation (cross-reference `history_screen.py` bindings)

## Post-Review Changes

### Change Request 1 (2026-03-25 12:20)
- **Requested by user:** Add screenshot (`codebrowser_task_history.svg`) to the history section, and update the TUIs overview page with the new history feature
- **Changes made:** Copied SVG to `website/static/imgs/`, added `static-img` shortcode at the top of the history section in `_index.md`, updated the codebrowser description in `website/content/docs/tuis/_index.md` to mention the completed tasks history feature
- **Files affected:** `website/static/imgs/codebrowser_task_history.svg`, `website/content/docs/tuis/codebrowser/_index.md`, `website/content/docs/tuis/_index.md`

## Final Implementation Notes
- **Actual work done:** Added documentation for the completed tasks history feature across 4 files: codebrowser `_index.md` (new section with screenshot), `reference.md` (keyboard shortcuts for history screen, label filter, sibling picker), `how-to.md` (step-by-step guide for all history operations), and TUIs `_index.md` (updated codebrowser description). Also added screenshot SVG to static files.
- **Deviations from plan:** Added screenshot and TUIs overview update per user review feedback (not in original plan).
- **Issues encountered:** None.
- **Key decisions:** Placed the history section after "Using the Detail Pane" and before "Launching an Explain Session" to maintain the logical flow of the tutorial. Organized keyboard shortcuts into separate tables for History Screen, Label Filter Dialog, and Sibling Picker Dialog.
- **Notes for sibling tasks:** All t448 siblings are already archived — no further sibling work expected.

## Step 9: Post-Implementation

Archive child task, update plan, push.
