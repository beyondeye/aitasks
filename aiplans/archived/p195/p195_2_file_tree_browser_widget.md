---
Task: t195_2_file_tree_browser_widget.md
Parent Task: aitasks/t195_python_codebrowser.md
Sibling Tasks: aitasks/t195/t195_1_*.md, aitasks/t195/t195_3_*.md
Archived Sibling Plans: aiplans/archived/p195/p195_1_core_scaffold_and_launcher.md
Branch: main
Base branch: main
---

# Plan: t195_2 — File Tree Browser Widget (Verified)

## Steps

### 1. Create `aiscripts/codebrowser/file_tree.py`
- `ProjectFileTree(DirectoryTree)` subclass:
  - `__init__(path, **kwargs)`: run `git ls-files` to build `self._tracked_files: set[str]` (relative paths) and `self._tracked_dirs: set[str]` (all parent directories of tracked files). Call `super().__init__(path, **kwargs)`.
  - `filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]`: for each path, skip if hidden (name starts with `.`), or name in (`__pycache__`, `node_modules`, `.git`); for dirs include if relative path in `_tracked_dirs`; for files include if relative path in `_tracked_files`
- Helper: `get_project_root() -> Path` — runs `git rev-parse --show-toplevel`

### 2. Update `codebrowser_app.py`
- Import `ProjectFileTree` from `.file_tree` and `subprocess`
- Get project root at app level via `subprocess.run(["git", "rev-parse", "--show-toplevel"])`
- Replace left pane `Container(id="file_tree_pane")` + placeholder with `ProjectFileTree(project_root, id="file_tree")`
- Add `on_directory_tree_file_selected(self, event)` handler — log selected path
- Update CSS: replace `#file_tree_pane` with `#file_tree { width: 35; border-right: thick $primary; background: $surface; }`
- Update `action_toggle_focus` to use `#file_tree` instead of `#file_tree_pane`

### 3. Handle edge cases
- Not in a git repo: catch subprocess error, show Static error message
- Empty repo: tree renders empty naturally

## Key API (Verified against Textual source)
- `DirectoryTree.__init__(self, path: str | Path, *, name=None, id=None, classes=None, disabled=False)`
- `filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]`
- Emits `DirectoryTree.FileSelected(node, path)` → handler `on_directory_tree_file_selected`

## Verification
- `./ait codebrowser` — file tree on left with project files
- Arrow keys navigate, Enter expands/collapses
- `.git/`, `__pycache__`, `node_modules/`, hidden files excluded
- Only git-tracked files visible
- Selecting a file triggers handler (Textual log)

## Final Implementation Notes
- **Actual work done:** Created `file_tree.py` with `ProjectFileTree(DirectoryTree)` subclass and `get_project_root()` helper. Updated `codebrowser_app.py` to replace placeholder container with the file tree widget, added `FileSelected` handler, updated CSS and focus toggle.
- **Deviations from plan:** Used direct import (`from file_tree import ...`) instead of relative import (`from .file_tree import ...`) because the launcher script runs `codebrowser_app.py` directly (not as a module), which doesn't support relative imports. Removed unused `subprocess` import from `codebrowser_app.py` since git operations are handled in `file_tree.py`.
- **Issues encountered:** Initial implementation used relative import which caused `ImportError: attempted relative import with no known parent package` when launched via `ait codebrowser`. Fixed by switching to direct import (Python adds script directory to sys.path automatically).
- **Key decisions:** Filtering uses pre-built sets (`_tracked_files`, `_tracked_dirs`) populated from `git ls-files` at construction time for O(1) lookups. Hidden files (starting with `.`) are excluded from the tree even if git-tracked (e.g., `.claude/` is hidden).
- **Notes for sibling tasks:** `ProjectFileTree` is imported from `file_tree` (not `.file_tree`). The `on_directory_tree_file_selected` handler currently only logs — t195_3 should wire it to update the code viewer pane. The `action_toggle_focus` now targets `#file_tree` (the widget ID) not a wrapper container. Use direct imports (not relative) for all codebrowser modules since the launcher runs scripts directly.
