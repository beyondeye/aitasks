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
