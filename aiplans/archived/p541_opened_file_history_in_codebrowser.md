---
Task: t541_opened_file_history_in_codebrowser.md
Base branch: main
---

# t541 — Opened file history in codebrowser

## Context

The `ait codebrowser` TUI currently shows only the project file tree in the
left sidebar — there is no history of previously opened files within the
current or past sessions. Re-locating a file you were working on minutes ago
means walking the tree again. The history screen already has a "Recently
Opened" tasks pane as reference (see `history_list.py:273` `RecentlyOpenedList`
and `.aitask-history/recently_opened.json`), and the same idea transfers
naturally to the main codebrowser view.

The task also asks for two small follow-ups on the history screen:

1. Tab does not actually switch panes in the history screen (even though a
   `tab → toggle_focus` binding exists at `history_screen.py:32`), because
   `HistoryTaskItem` widgets are focusable and Textual's default focus-next
   behavior consumes the Tab key before the screen binding fires.
2. Tab is not documented in the history screen footer (same root cause as
   above — the binding exists but in practice is shadowed).

## Scope

1. Split the main codebrowser left sidebar into two panes: a new
   **Recently Opened Files** pane (top) + the existing project file tree
   (bottom). Opened files persist to
   `.aitask-history/recently_opened_files.json`.
2. Fix Tab pane-switching in the history screen and ensure it is visible in
   the footer.

## Files to modify

1. `.aitask-scripts/codebrowser/file_tree.py`
   - Add a new `RecentFilesList(VerticalScroll)` widget and a
     `FileSelected` message (distinct from `DirectoryTree.FileSelected` to
     avoid confusing handlers).
   - Add `RecentFilesStore` helper that loads/saves
     `.aitask-history/recently_opened_files.json` — mirrors the pattern in
     `history_list.py:273` (`RecentlyOpenedList._load_history` / `_save_history`).
   - Add a `LeftSidebar(Container)` widget that composes a section header,
     the `RecentFilesList`, a "Project Files" header, and the existing
     `ProjectFileTree`. This keeps `codebrowser_app.py:compose` tidy.

2. `.aitask-scripts/codebrowser/codebrowser_app.py`
   - Replace the direct `ProjectFileTree(..., id="file_tree")` yield in
     `compose()` (line 390) with `LeftSidebar(..., id="left_sidebar")` that
     wraps the recent-files pane + the tree. Keep the existing `#file_tree`
     id on the inner tree so the rest of the app (`_apply_detail_width`,
     `_open_file_by_path`, focus handling, `on_resize`) keeps working.
   - Update CSS: the `#file_tree` block becomes `#left_sidebar` for the
     border/width/background; the inner tree gets a smaller ruleset so it
     shares space with the recent-files pane. Recent files pane gets
     `max-height: 10` (same cap pattern as `RecentlyOpenedList`) and a
     section header.
   - Update `on_resize()` (line 400) to target `#left_sidebar` instead of
     `#file_tree`.
   - Update `_apply_detail_width()` (line 416) to read width from
     `#left_sidebar`.
   - In `on_directory_tree_file_selected` (line 462) and
     `_apply_focus` (line 294) / `_open_file_by_path` (line 853): call
     `self.query_one("#recent_files", RecentFilesList).record(path)` so
     programmatic opens and user clicks both update history.
   - Extend `action_toggle_focus()` (line 767) to cycle
     `recent_files → file_tree → code_viewer → detail_pane (if visible) → recent_files`.
     Handle the `#recent_files` case first.
   - Add a `FileSelected` handler (`on_recent_files_list_file_selected`) that
     calls `_open_file_by_path(path)`.

3. `.aitask-scripts/codebrowser/history_screen.py`
   - Change line 32 from
     `Binding("tab", "toggle_focus", "Toggle Focus")` to
     `Binding("tab", "toggle_focus", "Toggle Focus", priority=True)`.
     This ensures the screen binding fires before Textual's default
     focus-next traversal (which currently swallows Tab inside
     `HistoryTaskItem` focusable rows).
   - No `show=` change is needed — once `priority=True` is set, the binding
     correctly appears in the `Footer` widget's bindings list.
   - Extend `action_toggle_focus()` (line 323) to cycle three pane groups
     instead of two: `history_list → recent_list → detail → history_list`.
     Today it only toggles `left ↔ detail`, which is awkward because the
     left pane contains two sub-lists (recent tasks + full task list).

## Persistence format

`.aitask-history/recently_opened_files.json` (gitignored via the existing
`.aitask-history/` entry in `.gitignore`):

```json
[
  {"path": "relative/path.py", "timestamp": "2026-04-14T12:00:00.000"},
  ...
]
```

Cap at 15 entries. Dedup on `path` (project-root-relative). Move-to-top on
re-open. `timestamp` is cosmetic metadata that may feed a tooltip later —
ordering relies only on list position, matching how
`RecentlyOpenedList.add_to_history` works at `history_list.py:318`.

**On-load validation (required):** `RecentFilesStore.load()` MUST check each
entry with `(project_root / path).is_file()` and drop any entries whose file
no longer exists (deleted, renamed, or moved outside the project). The
filtered list is then persisted back to disk so stale entries do not
accumulate. This runs once at widget mount time, and again whenever the
codebrowser re-opens. A malformed JSON file (missing keys, not a list,
decode error) is treated as an empty history and overwritten on next save —
matching the defensive pattern at `history_list.py:306`.

## RecentFilesList widget shape

```python
class FileSelectedMessage(Message):
    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path

class RecentFileItem(Static):
    can_focus = True
    # render: "  relative/path/file.py" with truncation similar to
    # HistoryTaskItem.render at history_list.py:108
    # on_key: enter -> post FileSelectedMessage; up/down -> _focus_neighbor
    # on_click -> post FileSelectedMessage

class RecentFilesList(VerticalScroll):
    # DEFAULT_CSS: max-height: 10
    # __init__(project_root) -> creates store; does NOT load yet
    # on_mount() -> store.load_and_prune() drops non-existent files,
    #               persists pruned list, then refresh_display()
    # record(abs_path) -> moves path to top, saves, refreshes display
    # refresh_display() -> re-mounts items
```

Reuse the existing `_focus_neighbor` helper from `history_list.py:65` by
exporting it (or duplicating the 15-line function — the task file for this
is dedicated so duplication is acceptable; I'll export it to keep one
definition).

## Footer keybinding visibility

The codebrowser main screen footer already documents "Toggle Focus" via the
existing `Binding("tab", "toggle_focus", "Toggle Focus")` at
`codebrowser_app.py:150`. For the history screen, making the tab binding
`priority=True` is sufficient — Textual's `Footer` widget renders it
automatically because `show` defaults to `True`.

## Verification

1. **Install dependency** (none new — Textual is already a dep).
2. **Syntax check:** `python -m py_compile .aitask-scripts/codebrowser/codebrowser_app.py .aitask-scripts/codebrowser/file_tree.py .aitask-scripts/codebrowser/history_screen.py`
3. **Shellcheck:** not applicable (pure Python).
4. **Load-time validation check:**
   - Edit `.aitask-history/recently_opened_files.json` to add a bogus entry
     (`{"path": "does/not/exist.xyz", "timestamp": "..."}`).
   - Re-launch `./ait codebrowser`.
   - Confirm the bogus entry does not appear in the recent files pane.
   - Confirm the JSON file on disk has been rewritten without the bogus
     entry.

5. **Manual TUI check** (primary verification):
   - Run `./ait codebrowser`.
   - Confirm the left sidebar now shows a "Recently Opened Files" pane above
     "Project Files" with the file tree.
   - Click a file in the tree → it loads and appears in the recent-files
     pane.
   - Click another file → both appear, most recent at top.
   - Quit (`q`) and re-open: the recent files persist.
   - Press Tab repeatedly from the file tree: focus should cycle
     recent files → tree → code → (detail if visible) → recent files.
   - Press Enter on a recent file row: it opens in the code viewer and moves
     to the top of the recent list.
   - Press `h` to enter the history screen, then Tab: focus should
     successfully cycle task list → recent tasks → detail → task list.
     Before the fix, Tab traverses individual `HistoryTaskItem`s.
   - Confirm the history screen footer shows `TAB Toggle Focus`.
6. **Regression spot check:**
   - Detail pane toggle (`d`), expand (`D`), annotations (`t`, `r`), go-to
     line (`g`), and launch agent (`e`) still work.
   - File-tree width still adapts on terminal resize (rule moved from
     `#file_tree` to `#left_sidebar`).
   - Focus mechanism: run `./ait codebrowser --focus README.md:1-5` and
     confirm focus handoff still works and the file appears in the recent
     list.

## Step 9 — Post-Implementation

Per the task-workflow, after user approval in Step 8 the task will be
committed with message `feature: Add opened-file history pane to codebrowser (t541)`
and archived via `./.aitask-scripts/aitask_archive.sh 541`. No branch/merge
step because the `fast` profile set `create_worktree: false`.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. New widgets in
  `file_tree.py`: `RecentFilesStore`, `RecentFileSelected` message,
  `_focus_neighbor` helper, `RecentFileItem`, `RecentFilesList`, and
  `LeftSidebar`. `codebrowser_app.py` swapped the bare `ProjectFileTree`
  for `LeftSidebar`, renamed the `#file_tree` CSS block to `#left_sidebar`,
  updated `on_resize`/`_apply_detail_width`/`_open_file_by_path`/
  `_apply_focus`/`on_directory_tree_file_selected` to call
  `recent.record(path)`, and rewrote `action_toggle_focus` to cycle
  `recent → tree → code → detail (if visible) → recent`. A new
  `on_recent_file_selected` handler opens files when a recent row is
  activated. `history_screen.py` got `priority=True` on the tab binding
  plus a three-group `action_toggle_focus` (task_list → recent_list →
  detail).
- **Deviations from plan:** None of substance. Named the message
  `RecentFileSelected` (not `FileSelectedMessage`) so Textual's
  snake_case handler convention maps to `on_recent_file_selected` — this
  avoids colliding with `on_directory_tree_file_selected`. The
  `_focus_neighbor` helper was duplicated inside `file_tree.py` rather
  than exported from `history_list.py`; the two copies are 15 lines each
  and splitting a shared utilities module felt heavier than the code
  duplication saved.
- **Issues encountered:** The on-load validation kept being moved later
  in the plan after the user flagged that non-existent entries must be
  dropped on load. The final shape is: `RecentFilesList` calls
  `store.load_and_prune()` in `on_mount`, which filters missing files
  and rewrites the JSON in one pass. Malformed JSON is treated as an
  empty list. `Textual.run_test`-based pilot initially failed on the
  history screen's cached-index fast path (`#history_list` not mounted
  yet); polling for the widget with `pilot.pause(delay=0.1)` got past
  the race. Not a real-app bug.
- **Key decisions:**
  - Reused `.aitask-history/` (already gitignored) for the new
    `recently_opened_files.json` — zero new ignore rules.
  - Capped recent files at 15 (vs. 10 for the history screen's recent
    tasks) because filenames are shorter and the main sidebar can fit
    more rows comfortably.
  - Used `\u2026` left-ellipsis truncation for deep paths so the
    basename stays visible.
  - Preserved the `#file_tree` id on the inner `ProjectFileTree` so all
    existing queries (`_apply_focus`, `_open_file_by_path`,
    `action_toggle_focus`) continue to work without churn.
- **Verification performed:** headless Textual pilot tests covering:
  store pruning (valid/missing/duplicate/malformed), app mounting with
  `LeftSidebar`, `_open_file_by_path` recording and move-to-top,
  three-way focus cycling in the main app, three-way focus cycling in
  the history screen (via push_screen + polling), tab binding metadata
  (`priority=True`, `show=True`), injected-bogus-entry pruning with
  rewrite-to-disk, and the `--focus README.md:1-5` regression path.
  Full interactive TUI (click/keypress) was not exercised in this
  session.
