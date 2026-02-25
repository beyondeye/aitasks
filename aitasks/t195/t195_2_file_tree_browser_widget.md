---
priority: high
effort: medium
depends: [t195_1, t195_1]
issue_type: feature
status: Implementing
labels: [codebrowser]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-25 12:18
updated_at: 2026-02-25 14:53
---

## Context

This is child task 2 of t195 (Python Code Browser TUI). It implements the file tree browser widget in the left pane of the codebrowser. The tree shows the project's source files organized by directory, with collapsible/expandable folders. Selecting a file will trigger code display in the right pane (wired in t195_3).

Textual provides a `DirectoryTree` widget that handles most tree rendering and navigation. We subclass it to filter to git-tracked files only and exclude common noise directories.

## Key Files to Modify

- **`aiscripts/codebrowser/file_tree.py`** (NEW): `ProjectFileTree(DirectoryTree)` subclass with:
  - Constructor receives project root path (detected via `git rev-parse --show-toplevel`)
  - Pre-built `set[str]` of all git-tracked files (from `git ls-files`) for O(1) membership checks
  - `filter_paths(paths)` override: exclude `.git/`, `__pycache__/`, `node_modules/`, hidden files (starting with `.`), and paths not in the git-tracked set
  - For directories: include only if at least one tracked file has it as a prefix
- **`aiscripts/codebrowser/codebrowser_app.py`** (MODIFY):
  - Replace left pane placeholder `Container` with `ProjectFileTree` widget
  - Add `on_directory_tree_file_selected()` handler (initially just updates info bar or prints to log)
  - Update CSS: file tree pane styling (fixed width ~30-35 cols, border-right, scrollable)

## Reference Files for Patterns

- Textual `DirectoryTree` API: Provides `filter_paths()` for path filtering, emits `FileSelected` and `DirectorySelected` messages
- `aiscripts/board/aitask_board.py` (lines 553-594): `KanbanColumn(VerticalScroll)` — pattern for custom scrollable container with CSS
- `aiscripts/board/aitask_board.py` (lines 1990-2121): CSS patterns for width, border, overflow styling

## Implementation Plan

1. Create `file_tree.py`:
   - Import: `from textual.widgets import DirectoryTree` and `subprocess`, `pathlib`
   - In `__init__`: run `git rev-parse --show-toplevel` to get project root, run `git ls-files` to build `self._tracked_files: set[str]`
   - Override `filter_paths(paths)`: for each path, check if it's a directory (include if any tracked file starts with its relative path) or a file (include if in tracked set); exclude `.git`, `__pycache__`, `node_modules`, hidden paths
2. Update `codebrowser_app.py`:
   - Import `ProjectFileTree` from `file_tree`
   - In `compose()`, replace left pane placeholder with `ProjectFileTree(project_root, id="file_tree")`
   - Add handler: `def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected)` — for now, log the selected path
   - Update CSS: `#file_tree { width: 35; border-right: tall $surface-lighten-2; }` and similar

## Verification Steps

1. Run `./ait codebrowser` — should show file tree on the left with project files
2. Arrow keys navigate the tree, Enter expands/collapses directories
3. `.git/`, `__pycache__/`, `node_modules/` should not appear
4. Only git-tracked files should be visible (untracked files excluded)
5. Selecting a file should trigger the handler (check via Textual console log or print)
