---
priority: medium
effort: low
depends: []
issue_type: refactor
status: Done
labels: [aitask_board]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-24 09:14
updated_at: 2026-02-24 09:30
completed_at: 2026-02-24 09:30
---

## Extract shared YAML utilities into `task_yaml.py`

### Context

The board TUI (`aiscripts/board/aitask_board.py`) contains YAML loading/dumping utilities that will be needed by the new auto-merge script (`aitask_merge.py`). To avoid duplication and ensure consistent YAML handling, these utilities need to be extracted into a shared module.

This is a foundation task for the t228 parent task "Improved Task Merge for ait sync". The extracted module will be imported by both the board and the merge script.

### Key Files to Modify

- `aiscripts/board/task_yaml.py` (NEW) — Shared YAML utilities module
- `aiscripts/board/aitask_board.py` — Update imports to use new module

### Reference Files for Patterns

- `aiscripts/board/aitask_board.py` lines 63-78: `_TaskSafeLoader` class — custom YAML loader that preserves `\d+_\d+` patterns as strings
- `aiscripts/board/aitask_board.py` lines 150-155: `_FlowListDumper` class — writes lists in flow style `[a, b]` but dicts in block style
- `aiscripts/board/aitask_board.py` lines 81-90: `_normalize_task_ids()` function
- `aiscripts/board/aitask_board.py` line 118: `_FRONTMATTER_RE` regex pattern
- `aiscripts/board/aitask_board.py` lines 120-148: `Task.load()` method — frontmatter parsing logic
- `aiscripts/board/aitask_board.py` lines 157-203: `Task._ordered_metadata()` and `Task.save()` — frontmatter serialization

### Implementation Plan

1. **Create `aiscripts/board/task_yaml.py`** with:
   - `_TaskSafeLoader` class (exact copy from board lines 63-78)
   - `_FlowListDumper` class (exact copy from board lines 150-155)
   - `_normalize_task_ids(ids_list)` function (from board lines 81-90)
   - `FRONTMATTER_RE` compiled regex (from board line 118)
   - `parse_frontmatter(raw_text: str) -> tuple[dict, str, list]` — returns `(metadata, body, original_key_order)`. Implements the parsing logic from `Task.load()` including task ID normalization for `depends`, `children_to_implement`, and `folded_tasks`
   - `serialize_frontmatter(metadata: dict, body: str, original_key_order: list) -> str` — returns the complete file content with frontmatter. Implements the serialization logic from `Task._ordered_metadata()` and `Task.save()`, with `_BOARD_KEYS` always last

2. **Update `aiscripts/board/aitask_board.py`**:
   - Add `from task_yaml import _TaskSafeLoader, _FlowListDumper, _normalize_task_ids, FRONTMATTER_RE, parse_frontmatter, serialize_frontmatter` at the top
   - Remove the inline definitions of `_TaskSafeLoader`, `_FlowListDumper`, `_normalize_task_ids`
   - Update `Task.load()` to call `parse_frontmatter()` instead of inline parsing
   - Update `Task.save()` to call `serialize_frontmatter()` instead of inline serialization
   - Keep `Task._ordered_metadata()` if still needed for intermediate operations, or delegate to `serialize_frontmatter()`

### Verification Steps

1. Run the board TUI (`./ait board`) and verify:
   - Tasks load correctly with proper metadata
   - Board column assignment and drag-and-drop still work
   - Task saving preserves key order and formatting
   - Child task IDs with underscore patterns (e.g., `85_2`) are preserved as strings
2. Run `python3 -c "from aiscripts.board.task_yaml import parse_frontmatter, serialize_frontmatter; print('OK')"` to verify import works
3. Run existing tests: `bash tests/test_sync.sh`
