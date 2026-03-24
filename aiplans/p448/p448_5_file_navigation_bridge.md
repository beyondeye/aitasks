---
Task: t448_5_file_navigation_bridge.md
Parent Task: aitasks/t448_archived_tasks_in_board.md
Sibling Tasks: aitasks/t448/t448_4_*.md, aitasks/t448/t448_6_*.md
Archived Sibling Plans: aiplans/archived/p448/p448_*_*.md
Worktree: (none)
Branch: main
Base branch: main
---

# Plan: File navigation bridge

## Step 1: Implement `_open_file_by_path()` in `codebrowser_app.py`

File: `.aitask-scripts/codebrowser/codebrowser_app.py`

Replace the stub from t448_4:

```python
def _open_file_by_path(self, file_path: str):
    """Programmatically open a file in the code viewer."""
    full_path = self._project_root / file_path
    if not full_path.exists():
        self.notify(f"File not found: {file_path}", severity="warning")
        return

    # Set the file as current and load it
    self._current_file_path = full_path
    viewer = self.query_one("#code_viewer", CodeViewer)
    viewer.load_file(full_path)  # reuse existing method
    self._update_info_bar()

    # Try to select in file tree
    tree = self.query_one("#file_tree", ProjectFileTree)
    tree.select_path(full_path)
```

## Step 2: Add `select_path()` to `ProjectFileTree`

File: `.aitask-scripts/codebrowser/file_tree.py`

```python
class ProjectFileTree(DirectoryTree):
    def select_path(self, target: Path):
        """Expand tree to target file and select it."""
        # Walk from root, expanding directories as needed
        # Use Textual's DirectoryTree.reload_node() for expansion
        # Then select_node() when target is found
        # If not found (not git-tracked), just log
```

The implementation needs to:
1. Resolve the target path relative to the tree root
2. Walk the tree node hierarchy, expanding intermediate directories
3. Select the final node
4. Scroll to make it visible

Note: Textual's `DirectoryTree` stores nodes lazily — directories are only populated when expanded. May need to trigger expansion first, then select after the expansion completes.

## Step 3: State preservation verification

The dismiss/push cycle must work correctly:
1. History screen `dismiss(result=file_path)` → pops history from stack
2. Codebrowser receives callback → opens file
3. User presses `h` → same `HistoryScreen` instance pushed again
4. History shows same state (selected task, loaded chunks, nav stack)

## Verification

1. Open history → select task → click affected file → codebrowser opens that file
2. File tree highlights the correct file
3. Press `h` → history returns with same state
4. Test with non-existent file → notification shown
5. Test with deeply nested file → tree expands correctly

## Final Implementation Notes

- **Actual work done:** Replaced `_open_file_by_path()` stub in `codebrowser_app.py` with full implementation that replicates `on_directory_tree_file_selected` pattern (load file, clear detail pane, reset info bar, load explain data, select in tree). Added `select_path()` method to `ProjectFileTree` in `file_tree.py` using async `@work` decorator to handle lazy-loaded tree expansion.
- **Deviations from plan:**
  - `_open_file_by_path` also clears cursor/annotation info and detail pane (matching the full `on_directory_tree_file_selected` pattern), which the original plan snippet didn't include.
  - `select_path()` required async implementation with `@work` decorator and `reload_node()` awaiting, because Textual's DirectoryTree lazily loads directory children. A sync walk fails when the tree is collapsed.
- **Issues encountered:**
  - **Sync tree walking failed for collapsed trees:** Initial sync implementation with `expand()` worked only when the tree was already expanded. Children aren't available immediately after `expand()` because loading is async.
  - **Race condition between expand() and reload_node():** Calling both on the same node caused a race where `_populate_node` could run twice (from the NodeExpanded message handler and from reload_node), with `remove_children()` in one interfering with the other. Fixed by using `reload_node()` exclusively for unloaded directories (it handles both loading AND expanding via `_populate_node → expand()`), and `expand()` only for already-loaded but collapsed directories.
- **Key decisions:** Using Textual's `@work(exclusive=True, group="select_path")` ensures only one select_path operation runs at a time and integrates properly with the event loop. The `reload_node` awaitable ensures children are fully populated before traversal continues.
- **Notes for sibling tasks:**
  - `_open_file_by_path` accepts a string relative path (from `NavigateToFile.file_path` emitted by `history_detail.py`) and converts to Path via `self._project_root / file_path`.
  - The `select_path` method is reusable for any programmatic file selection in the tree.

## Step 9: Post-Implementation

Archive child task, update plan, push.
