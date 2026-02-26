---
Task: t252_currently_codebrowser_tui_does_not_show_in_the_tree_for_brow.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

The codebrowser TUI filters out all files/directories whose names start with `.` (dotfiles), including `.claude/` which is git-tracked and contains important skill definitions. This is overly aggressive — the `git ls-files` check already ensures only tracked files appear, so the dotfile blanket exclusion is unnecessary. Additionally, binary files show in the tree but only display a commit count — the actual commit details (hashes, messages, task IDs) should be visible.

## Plan

### 1. Remove blanket dotfile exclusion from file tree

**File:** `aiscripts/codebrowser/file_tree.py:54`

Change:
```python
if path.name.startswith(".") or path.name in EXCLUDED_NAMES:
```
To:
```python
if path.name in EXCLUDED_NAMES:
```

This is safe because:
- `.git` is already in `EXCLUDED_NAMES` and stays hidden
- `git ls-files` only returns tracked files, so untracked dotfiles (`.env`, etc.) won't appear
- `__pycache__` and `node_modules` remain excluded via `EXCLUDED_NAMES`

### 2. Show commit timeline for binary files in code viewer

**File:** `aiscripts/codebrowser/code_viewer.py`

Add a `show_binary_info()` method that displays the commit timeline in the code area when a binary file is selected. Instead of just "Binary file — cannot display", show:
```
Binary file — cannot display text content

Commit history (N commits):
  abc1234  bug: Fix logo (t42)
  def5678  feature: Add dark theme (t50)
  ...
```

**File:** `aiscripts/codebrowser/codebrowser_app.py` (around line 258)

When a binary file is detected in `_update_code_annotations()`, pass the `commit_timeline` to the code viewer so it can display the list. Call `code_viewer.show_binary_info(file_data.commit_timeline)` instead of just `set_annotations([])`.

### 3. Fix root directory annotation generation

**File:** `aiscripts/codebrowser/explain_manager.py` (line 70-79)

The `generate_explain_data()` method has a bug for root-level files: when `rel_dir` is `Path(".")`, the filter `os.path.dirname(f) == str(rel_dir)` compares against `"."`, but `os.path.dirname("ait")` returns `""`. Root-level files never match.

Fix by using `""` as the dirname comparison target when the directory is root.

## Verification

1. Launch the codebrowser: `./ait codebrowser`
2. Verify `.claude/` directory appears in the tree
3. Verify `.claude/skills/` subdirectories are browsable
4. Verify `.gitignore` and other tracked dotfiles appear
5. Verify `.git/` directory does NOT appear (still in EXCLUDED_NAMES)
6. Verify `__pycache__` and `node_modules` don't appear
7. Select a binary file (if any) and verify commit timeline is displayed
8. Verify root-level files have annotations

## Final Implementation Notes
- **Actual work done:** Three issues fixed: (1) dotfile exclusion removed from file tree, (2) binary file commit timeline display added, (3) root directory annotation bug fixed
- **Deviations from plan:** The root directory bug (#3) was discovered during user testing — not part of the original plan. The `os.path.dirname()` returns `""` for root-level files, but the code compared against `"."` from `str(Path("."))`.
- **Issues encountered:** The root directory annotation bug was pre-existing but became more visible once dotfiles were shown in the tree.
- **Key decisions:** Used Rich `Text` objects for styled binary file commit display to match the existing code viewer patterns.
