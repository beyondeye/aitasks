---
Task: t992_board_resolve_archived_tasks_in_verifies_dialog.md
Worktree: /home/ddt/Work/aitasks
Branch: main
Base branch: main
---

# Resolve Archived Tasks in Board Verifies/Depends Dialogs

## Summary

Fix `ait board` relation dialogs so archived tasks referenced by `verifies:` or
`depends:` resolve to task information instead of `(not found)`. Archived hits
must open read-only; true misses must keep the removal prompt behavior.

## Implementation Plan

1. Add a targeted archived-task markdown resolver to
   `.aitask-scripts/lib/archive_iter.py`.
   - Check loose archived parent and child files first.
   - Use `archive_path_for_id()` to inspect only the numbered archive bundle for
     the parent ID.
   - Fall back to legacy `old.tar.zst` / `old.tar.gz`.
   - Return `None` for invalid or genuinely missing IDs.
2. Add archived-aware board task lookup in
   `.aitask-scripts/board/aitask_board.py`.
   - Preserve `TaskManager.find_task_by_id()` as active-only.
   - Add `TaskManager.find_task_including_archived()` with active-first lookup
     and lazy per-session cache for archived hits and misses.
   - Add in-memory `Task.from_text()` construction for archived tar entries.
   - Mark archived-loaded tasks with `task.archived = True`.
3. Update relation navigation.
   - Make `DependsField` and `VerifiesField` use archived-aware lookup.
   - Open archived hits with `TaskDetailScreen(..., read_only=True)`.
   - Leave `None` results as the only path that shows `(not found)` and offers
     removal.
4. Add focused regression tests.
   - Cover loose, numbered, and legacy archive lookup in `archive_iter`.
   - Cover active-over-archived precedence and board relation lookup for
     archived `depends:` and `verifies:` refs.

## Verification

- `python3 -m py_compile .aitask-scripts/lib/archive_iter.py .aitask-scripts/board/aitask_board.py`
- `python3 tests/test_archive_iter_consolidated.py`
- `python3 tests/test_board_archived_relation_lookup.py`
- `python3 tests/test_board_detail_collapsible.py`
- `python3 tests/test_board_picker_tab_nav.py`
- `python3 tests/test_board_view_filter.py`
- `python3 tests/test_task_dir_module_constants.py`
- `bash tests/run_all_python_tests.sh` (1165 tests, OK)

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes

- **Actual work done:** Added `find_archived_markdown_by_id()` for targeted
  archived task lookup, added lazy archived resolution to `TaskManager`, and
  updated `DependsField` / `VerifiesField` plus picker item navigation to open
  archived relation hits read-only.
- **Deviations from plan:** None. The helper was added in `archive_iter.py`
  rather than a board-only private function so the targeted lookup can be reused
  by future Python code.
- **Issues encountered:** The local Python environment has no `pytest`; direct
  `unittest` execution and `tests/run_all_python_tests.sh` both worked.
- **Key decisions:** Kept `find_task_by_id()` active-only to avoid changing
  unrelated board call sites; archived-aware lookup is opt-in via
  `find_task_including_archived()`. Cached misses as well as hits to avoid
  repeated legacy archive scans for a genuinely missing relation.
- **Upstream defects identified:** None.
