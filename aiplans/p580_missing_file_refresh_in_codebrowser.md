---
Task: t580_missing_file_refresh_in_codebrowser.md
Base branch: main
plan_verified: []
---

# t580 — File tree refresh in codebrowser

## Context

The codebrowser TUI's file tree (`.aitask-scripts/codebrowser/file_tree.py`) caches the set of git-tracked files in `ProjectFileTree.__init__` via a one-shot `git ls-files` call. It is never refreshed, so files added or deleted from the filesystem while the TUI is running are invisible to the tree. Additionally, Textual's `DirectoryTree` caches each directory's children after the first expansion (`node.data.loaded = True`), so collapsing and re-expanding a directory does NOT re-read its contents.

Fix:
1. On re-expansion of a directory (collapse → expand), force a refresh of git-tracked files and reload that directory's children.
2. Add a `R` (shift+r) shortcut that fully resets the file tree: re-runs `git ls-files`, clears all cached children/expansion state, and reloads the root.

## Files to modify

- `.aitask-scripts/codebrowser/file_tree.py` — core refresh logic
- `.aitask-scripts/codebrowser/codebrowser_app.py` — new binding + message handler to keep the file-search widget in sync

## Implementation

### 1. `file_tree.py` changes

**Imports** — add `DirEntry` and `Message`:

```python
from textual.message import Message  # already imported
from textual.widgets._directory_tree import DirEntry
```

**New message class** at module level:

```python
class TrackedFilesRefreshed(Message):
    """Posted by ProjectFileTree after re-running git ls-files."""
    pass
```

**Extract the git-to-sets logic** as a module-level helper (pure function, no `self`) so it can be unit-tested in isolation:

```python
def compute_tracked_sets(root: Path) -> tuple[set[str], set[str]]:
    """Run `git ls-files` at root; return (tracked_files, tracked_dirs).

    Both sets contain project-root-relative POSIX paths. Tracked dirs are all
    parent directories of tracked files (excluding ".").
    """
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        cwd=root,
    )
    files: set[str] = set()
    dirs: set[str] = set()
    if result.returncode == 0:
        for line in result.stdout.strip().splitlines():
            if line:
                files.add(line)
                p = Path(line)
                for parent in p.parents:
                    parent_str = str(parent)
                    if parent_str == ".":
                        break
                    dirs.add(parent_str)
    return files, dirs
```

Update `__init__` to use the helper:

```python
def __init__(self, path: str | Path, **kwargs) -> None:
    root = Path(path)
    self._tracked_files, self._tracked_dirs = compute_tracked_sets(root)
    super().__init__(path, **kwargs)
```

**Public refresh method** that also notifies subscribers:

```python
def refresh_tracked_files(self) -> None:
    """Re-run git ls-files and emit TrackedFilesRefreshed."""
    self._tracked_files, self._tracked_dirs = compute_tracked_sets(Path(self.path))
    self.post_message(TrackedFilesRefreshed())
```

**Override `_populate_node`** to avoid a refresh-loop — the base implementation unconditionally calls `node.expand()` after adding children, which re-fires `NodeExpanded` and would cause our refresh handler to recurse:

```python
def _populate_node(self, node, content):
    """Populate children; skip re-firing NodeExpanded if already expanded.

    The base DirectoryTree._populate_node calls node.expand() unconditionally,
    which posts NodeExpanded even when the node was already expanded by the
    user's click. That redundant event triggers this class's expand handler,
    which would call _add_to_load_queue again → infinite loop. Skipping the
    redundant expand is safe: node.add() already invalidates the tree so the
    new children render.
    """
    node.remove_children()
    for path in content:
        node.add(
            path.name,
            data=DirEntry(path),
            allow_expand=self._safe_is_dir(path),
        )
    if not node.is_expanded:
        node.expand()
```

**Override `_on_tree_node_expanded`** to refresh on re-expansion:

```python
async def _on_tree_node_expanded(self, event):
    """Force a refresh when a previously-loaded directory is re-expanded.

    First-time expansion: dir_entry.loaded is False → fall through to the
    normal load path. Second time (user collapsed then re-expanded): loaded
    is True → re-run git ls-files, clear cached children, mark unloaded,
    and re-queue the load. Picks up files added/deleted from disk.
    """
    event.stop()
    dir_entry = event.node.data
    if dir_entry is None:
        return
    if not await asyncio.to_thread(self._safe_is_dir, dir_entry.path):
        if event.node.data is not None:
            self.post_message(self.FileSelected(event.node, dir_entry.path))
        return
    if dir_entry.loaded:
        self.refresh_tracked_files()
        event.node.remove_children()
        dir_entry.loaded = False
    await self._add_to_load_queue(event.node)
```

Requires adding `import asyncio` at the top of the file.

**Adjust `_do_select_path`** to stop using `reload_node` (which goes through `_reload` → explicit `reopening.expand()` → would re-fire NodeExpanded after our refactor). Replace both `await self.reload_node(...)` calls with `await self._add_to_load_queue(...)`:

```python
@work(exclusive=True, group="select_path")
async def _do_select_path(self, target: Path) -> None:
    try:
        rel_parts = target.relative_to(Path(self.path)).parts
    except ValueError:
        return

    node = self.root
    for i, part in enumerate(rel_parts):
        if node.data and not node.data.loaded:
            await self._add_to_load_queue(node)

        found = None
        for child in node.children:
            if child.data and child.data.path.name == part:
                found = child
                break
        if found is None:
            return

        if i < len(rel_parts) - 1:
            if found.data and not found.data.loaded:
                await self._add_to_load_queue(found)
                if not found.is_expanded:
                    found.expand()
            elif not found.is_expanded:
                found.expand()
        node = found

    self.select_node(node)
    self.scroll_to_node(node)
```

**`action_reset_tree`** — the public reset action (called from the app binding):

```python
async def action_reset_tree(self) -> None:
    """Refresh git ls-files, clear all cached children, reload root."""
    self.refresh_tracked_files()
    self.root.remove_children()
    if self.root.data:
        self.root.data.loaded = False
    self.cursor_line = 0
    await self._add_to_load_queue(self.root)
```

Notes:
- Keeps the root expanded (user immediately sees refreshed top-level items).
- All descendants' expansion/loaded state is discarded because their nodes no longer exist.

### 2. `codebrowser_app.py` changes

**Import the new message**:

```python
from file_tree import (
    LeftSidebar,
    ProjectFileTree,
    RecentFileSelected,
    RecentFilesList,
    TrackedFilesRefreshed,  # new
    get_project_root,
)
```

**Add the binding** to `CodeBrowserApp.BINDINGS` (after the existing `r` refresh line is a natural spot):

```python
Binding("R", "reset_file_tree", "Reset file tree"),
```

**Action method** on the app:

```python
async def action_reset_file_tree(self) -> None:
    """Refresh the file tree's git-tracked cache and reload the root."""
    try:
        tree = self.query_one("#file_tree", ProjectFileTree)
    except Exception:
        return
    await tree.action_reset_tree()
    self.notify("File tree refreshed", timeout=2)
```

**Keep the file-search widget in sync** — the app's `on_mount` seeds `FileSearchWidget.set_files(...)` from `tree._tracked_files`. Update it whenever the tree emits `TrackedFilesRefreshed`:

```python
def on_tracked_files_refreshed(self, event: TrackedFilesRefreshed) -> None:
    try:
        tree = self.query_one("#file_tree", ProjectFileTree)
        search = self.query_one("#file_search", FileSearchWidget)
        search.set_files(sorted(tree._tracked_files))
    except Exception:
        pass
```

## Tests (semi-automated)

Add `tests/test_file_tree_refresh.py` — unittest-based, same style as `tests/test_history_data.py`. Runs via `python3 -m pytest tests/test_file_tree_refresh.py -v`.

The tests exercise the pure `compute_tracked_sets` helper against a real temp git repo, which is the piece of logic that actually changes when the filesystem mutates. No Textual harness needed.

```python
"""Tests for codebrowser/file_tree.py tracked-files refresh logic."""

from __future__ import annotations
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_scripts = Path(__file__).resolve().parents[1] / ".aitask-scripts"
sys.path.insert(0, str(_scripts / "codebrowser"))

from file_tree import compute_tracked_sets


def _git(cwd, *args):
    result = subprocess.run(
        ["git"] + list(args), capture_output=True, text=True, cwd=cwd,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


class ComputeTrackedSetsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _git(self.root, "init", "-q")
        _git(self.root, "config", "user.email", "t@x")
        _git(self.root, "config", "user.name", "t")
        (self.root / "a.txt").write_text("a")
        (self.root / "sub").mkdir()
        (self.root / "sub" / "b.txt").write_text("b")
        (self.root / "sub" / "deep").mkdir()
        (self.root / "sub" / "deep" / "c.txt").write_text("c")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "init")

    def tearDown(self):
        self._tmp.cleanup()

    def test_initial_scan(self):
        files, dirs = compute_tracked_sets(self.root)
        self.assertEqual(files, {"a.txt", "sub/b.txt", "sub/deep/c.txt"})
        self.assertEqual(dirs, {"sub", "sub/deep"})

    def test_untracked_files_excluded(self):
        (self.root / "untracked.txt").write_text("u")
        (self.root / "sub" / "untracked2.txt").write_text("u")
        files, _ = compute_tracked_sets(self.root)
        self.assertNotIn("untracked.txt", files)
        self.assertNotIn("sub/untracked2.txt", files)

    def test_refresh_picks_up_new_file(self):
        files_before, _ = compute_tracked_sets(self.root)
        self.assertNotIn("NEW.md", files_before)
        (self.root / "NEW.md").write_text("new")
        (self.root / "newdir").mkdir()
        (self.root / "newdir" / "n.txt").write_text("n")
        _git(self.root, "add", "NEW.md", "newdir/n.txt")
        files_after, dirs_after = compute_tracked_sets(self.root)
        self.assertIn("NEW.md", files_after)
        self.assertIn("newdir/n.txt", files_after)
        self.assertIn("newdir", dirs_after)

    def test_refresh_picks_up_deleted_file(self):
        _git(self.root, "rm", "-q", "sub/b.txt")
        files_after, dirs_after = compute_tracked_sets(self.root)
        self.assertNotIn("sub/b.txt", files_after)
        # sub/deep/c.txt still there, so sub and sub/deep remain
        self.assertIn("sub", dirs_after)
        self.assertIn("sub/deep", dirs_after)

    def test_empty_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git(root, "init", "-q")
            files, dirs = compute_tracked_sets(root)
            self.assertEqual(files, set())
            self.assertEqual(dirs, set())


if __name__ == "__main__":
    unittest.main()
```

Add to the project's Python test runner (`tests/run_all_python_tests.sh`) if that file enumerates tests explicitly; otherwise the `pytest` auto-discovery will pick it up.

## Verification

1. Start the codebrowser in a running session: `./ait codebrowser` (or from tmux the usual way).
2. **Add-file case**: in another terminal, `touch NEW_FILE.md && git add NEW_FILE.md`. In the TUI, collapse the project root (or any directory that should contain it), then re-expand. The new file should appear.
3. **Delete-file case**: `git rm some_tracked_file.md && rm some_tracked_file.md`. Collapse/re-expand the containing directory. The file should disappear.
4. **Reset shortcut**: with several subdirectories expanded, press `R`. All subdirectories collapse; the root shows its freshly-read children; the notification "File tree refreshed" appears.
5. **Search sync**: after pressing `R`, open the fuzzy file-search box (focus the input at the top of the code pane) and type a substring of a newly-added file — it should appear in the results.
6. **Regression check**: open a file from the Recent Files pane or via fuzzy search — the `select_path` navigation still expands the correct intermediate directories and highlights the target file.
7. **Linting**: `shellcheck` is irrelevant (Python-only change). Run `python3 -c "import ast, pathlib; ast.parse(pathlib.Path('.aitask-scripts/codebrowser/file_tree.py').read_text()); ast.parse(pathlib.Path('.aitask-scripts/codebrowser/codebrowser_app.py').read_text())"` to confirm no syntax errors before launching.
8. **Automated tests**: `python3 -m pytest tests/test_file_tree_refresh.py -v` — all cases green.

## Step 9 (Post-Implementation)

Standard archival via `aitask_archive.sh 580` after review + commit; commit message `bug: Add file tree refresh in codebrowser (t580)`.
