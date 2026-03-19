---
priority: medium
effort: medium
depends: [t417_10]
issue_type: feature
status: Ready
labels: [tui, brainstorming]
created_at: 2026-03-19 12:03
updated_at: 2026-03-19 12:03
---

## Context

Add an edit mode to the diff viewer that allows the user to directly edit the main plan file within the TUI, then refresh the diff to see updated changes. Currently the diff viewer is read-only — the user must exit to an external editor to make changes. This feature enables a tight edit-diff feedback loop, especially useful during brainstorming plan refinement.

Only the main plan file should be editable (not comparison plans). After saving edits, the diff is recomputed automatically.

## Key Files to Create

- `.aitask-scripts/diffviewer/edit_screen.py` — Edit screen with Textual `TextArea(language="markdown")` widget

## Key Files to Modify

- `.aitask-scripts/diffviewer/diff_viewer_screen.py` — Add keybinding to enter edit mode, handle return from edit screen with diff refresh
- `.aitask-scripts/diffviewer/diffviewer_app.py` — Register CSS for edit screen if needed

## Key Files for Reference

- `.aitask-scripts/board/aitask_board.py` — `CommitMessageScreen(ModalScreen)` pattern for modal with text input
- `.aitask-scripts/diffviewer/diff_display.py` — DiffDisplay widget that needs refreshing after edit

## Implementation Plan

1. Create `edit_screen.py` with `EditScreen(Screen)`:
   - Constructor takes: `file_path: str` (the main plan path)
   - Layout: `Header` + `TextArea(language="markdown", show_line_numbers=True)` + `Footer`
   - On mount: read the file content and load into TextArea
   - Keybindings:
     - `ctrl+s` → save file to disk, dismiss screen with result `True` (indicating changes saved)
     - `escape` → dismiss with result `False` (no save)
   - Save writes TextArea content back to the file path
   - Show notification on save: "Saved: <filename>"

2. Add edit keybinding to `DiffViewerScreen`:
   - `Binding("e", "edit_main", "Edit")` in BINDINGS list
   - `action_edit_main()`: push `EditScreen(self._main_path)` with a callback

3. Implement the callback in `DiffViewerScreen`:
   - On return from EditScreen with `True`: recompute diffs by calling `self._compute_diffs()` (already a background worker)
   - On return with `False`: do nothing (no changes)
   - The existing `_on_diffs_ready()` → `_load_current_view()` pipeline handles the refresh

4. Add CSS for EditScreen in `diffviewer_app.py` if needed (TextArea is mostly self-styling).

## Verification

- From DiffViewerScreen, press `e`: EditScreen opens with main plan content and markdown syntax highlighting
- Edit text, press `ctrl+s`: file saved, returns to diff view, diff is recomputed and display refreshes
- Verify the changes appear in the diff (new lines show as inserts, removed lines as deletes)
- Press `escape` without saving: returns to diff view unchanged
- Original file on disk matches what was saved
- Edit mode works from both interleaved and side-by-side layouts
