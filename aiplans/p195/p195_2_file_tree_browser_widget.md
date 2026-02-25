---
Task: t195_2_file_tree_browser_widget.md
Parent Task: aitasks/t195_python_codebrowser.md
Sibling Tasks: aitasks/t195/t195_1_*.md, aitasks/t195/t195_3_*.md
Branch: main
Base branch: main
---

# Plan: t195_2 — File Tree Browser Widget

## Steps

### 1. Create `aiscripts/codebrowser/file_tree.py`
- `ProjectFileTree(DirectoryTree)`:
  - `__init__(path, **kwargs)`: run `git rev-parse --show-toplevel` for root, `git ls-files` for tracked files set
  - `_tracked_files: set[str]` — all git-tracked file paths (relative to root)
  - `_tracked_dirs: set[str]` — all parent directories of tracked files
  - `filter_paths(paths) -> Iterable[Path]`: filter to tracked files/dirs, exclude `.git`, `__pycache__`, `node_modules`, hidden paths (starting with `.`)

### 2. Update `codebrowser_app.py`
- Import `ProjectFileTree`
- Replace left pane placeholder with `ProjectFileTree(project_root, id="file_tree")`
- Get project root via `subprocess.run(["git", "rev-parse", "--show-toplevel"])`
- Add `on_directory_tree_file_selected()` handler — log the path for now
- CSS: `#file_tree { width: 35; border-right: tall $surface-lighten-2; }`

### 3. Handle edge cases
- Not in a git repo: show error message in tree pane
- Empty repo: show empty tree

## Verification
- Tree shows project files organized by directory
- Hidden dirs, `__pycache__`, `.git` excluded
- Only git-tracked files visible
- Arrow keys navigate, Enter expands/collapses
