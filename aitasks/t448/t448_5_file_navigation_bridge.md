---
priority: medium
effort: low
depends: [t448_4]
issue_type: feature
status: Implementing
labels: [aitask_board, task-archive]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-24 09:00
updated_at: 2026-03-24 21:44
---

## Context

This is child task 5 of t448 (Completed Tasks History View in Codebrowser). It implements the navigation bridge so that selecting an affected file in the history detail pane returns to the main codebrowser view with that file opened and focused.

Depends on t448_4 (screen integration) which provides the screen infrastructure and the `_on_history_dismiss` callback stub.

## Key Files to Modify
- `.aitask-scripts/codebrowser/codebrowser_app.py` — add `_open_file_by_path()` method, complete the dismiss callback
- `.aitask-scripts/codebrowser/file_tree.py` — possibly add `select_path()` method to `ProjectFileTree`

## Reference Files
- `.aitask-scripts/codebrowser/codebrowser_app.py` — existing `on_directory_tree_file_selected()` handler (the pattern to reuse for programmatic file opening)
- `.aitask-scripts/codebrowser/file_tree.py` — `ProjectFileTree(DirectoryTree)` class
- Textual `DirectoryTree` API docs for programmatic node selection

## Implementation

### CodeBrowserApp._open_file_by_path(file_path: str)

This method programmatically opens a file in the code viewer, replicating the behavior of clicking a file in the tree:

1. Resolve `file_path` relative to `self._project_root`
2. Check if the file exists:
   - If not: show a Textual notification "File not found: {path}" and return
3. If the file tree has focus, try to expand and select the node:
   - Use `ProjectFileTree.select_path(path)` (may need to be added)
   - Or use Textual's `DirectoryTree` API to walk and select the node
4. Trigger the file loading flow (same as `on_directory_tree_file_selected`):
   - Set `self._current_file_path`
   - Load file content into `CodeViewer`
   - Load explain data if available
   - Update info bar

### ProjectFileTree.select_path(path: Path) (if needed)

Textual's `DirectoryTree` provides `select_node()` but requires the node reference. To select by path:
1. Walk the tree nodes from root
2. Expand directories as needed to reach the target
3. Call `self.select_node(node)` when found
4. If the path is not in the tree (file not git-tracked), log a warning

### State Preservation Details

When `HistoryScreen.dismiss(result=file_path)` is called:
1. The history screen is popped from the stack (but the cached instance on `CodeBrowserApp` is preserved)
2. The codebrowser's compose is still intact (it was never destroyed)
3. `_on_history_dismiss(result)` is called with the file path
4. `_open_file_by_path(result)` opens the file
5. Pressing `h` again pushes the same `HistoryScreen` instance back — same state as before

### Edge Cases
- File no longer exists (deleted since task was completed): show notification, do not crash
- File exists but is not git-tracked (was tracked at the time but since removed from git): show notification
- File is in a deep directory that the tree has not expanded yet: expand parent directories first

## Verification

1. Open history, select a task with known affected files
2. Click/Enter on an affected file
3. Codebrowser returns with that file open in the code viewer
4. File tree shows the file selected/highlighted
5. Press `h` again — history screen returns with same state
6. Test with a file that no longer exists — notification shown, no crash
7. Test with a file in a deep directory — tree expands to show it
