---
Task: t228_1_extract_shared_yaml_utilities.md
Parent Task: aitasks/t228_improved_task_merge_for_board.md
Sibling Tasks: aitasks/t228/t228_2_*.md, aitasks/t228/t228_3_*.md, aitasks/t228/t228_4_*.md, aitasks/t228/t228_5_*.md
Branch: (current branch - no worktree)
Base branch: main
---

# Plan: t228_1 — Extract Shared YAML Utilities

## Goal

Extract `_TaskSafeLoader`, `_FlowListDumper`, `_normalize_task_ids`, `FRONTMATTER_RE`, and create `parse_frontmatter()` / `serialize_frontmatter()` from `aitask_board.py` into a new shared module `aiscripts/board/task_yaml.py`.

## Steps

### 1. Create `aiscripts/board/task_yaml.py`

Extract from `aitask_board.py`:

- **`_TaskSafeLoader`** (lines 63-78): Custom YAML loader preserving `\d+_\d+` as strings
- **`_FlowListDumper`** (lines 150-155): Lists in flow style, dicts in block style. NOTE: currently nested inside `Task` class — move to module level
- **`_normalize_task_ids(ids_list)`** (lines 81-90): Ensure child task refs have `t` prefix
- **`FRONTMATTER_RE`** (line 118): `re.compile(r'\A---\n(.*?)\n---\n(.*)', re.DOTALL)`

Add new helper functions:

- **`parse_frontmatter(raw_text: str) -> tuple[dict, str, list]`**:
  - Match `FRONTMATTER_RE` against `raw_text`
  - Parse YAML with `_TaskSafeLoader`
  - Normalize task IDs in `depends`, `children_to_implement`, `folded_tasks`
  - Return `(metadata, body, original_key_order)`

- **`serialize_frontmatter(metadata: dict, body: str, original_key_order: list) -> str`**:
  - Order keys: original order first, then new non-board keys, board keys (`boardcol`, `boardidx`) last
  - Dump with `_FlowListDumper`, `default_flow_style=False`, `sort_keys=False`
  - Return `"---\n{frontmatter}---\n{body}"`

### 2. Update `aitask_board.py`

- Add import: `from task_yaml import _TaskSafeLoader, _FlowListDumper, _normalize_task_ids, FRONTMATTER_RE, parse_frontmatter, serialize_frontmatter`
- Remove inline definitions of `_TaskSafeLoader` (lines 63-78), `_normalize_task_ids` (lines 81-90)
- Move `_FlowListDumper` out of `Task` class — use the one from `task_yaml`
- Update `Task.load()` to use `parse_frontmatter()`:
  ```python
  def load(self):
      with open(self.filepath, "r", encoding="utf-8") as f:
          raw = f.read()
      result = parse_frontmatter(raw)
      if result:
          self.metadata, self.content, self._original_key_order = result
      else:
          self.metadata, self.content, self._original_key_order = {}, raw, []
  ```
- Update `Task.save()` to use `serialize_frontmatter()`:
  ```python
  def save(self):
      content = serialize_frontmatter(self.metadata, self.content, self._original_key_order)
      with open(self.filepath, "w", encoding="utf-8") as f:
          f.write(content)
  ```

### 3. Verify

- Run `./ait board` — tasks load, display, and save correctly
- Verify key order preservation on save
- Verify child task IDs like `85_2` remain strings
- Run `bash tests/test_sync.sh`

## Key Design Decisions

- `_FlowListDumper` is currently nested inside `Task` class — moving it to module level is safe since it has no instance dependencies
- `parse_frontmatter` returns `None` (not a tuple) when no frontmatter found, to distinguish from empty frontmatter
- Board keys constant (`_BOARD_KEYS = ("boardcol", "boardidx")`) is defined in `task_yaml.py` as `BOARD_KEYS`

## Final Implementation Notes

- **Actual work done:** Extracted all YAML utilities from `aitask_board.py` into `task_yaml.py` as planned. Created `parse_frontmatter()` and `serialize_frontmatter()` helper functions that encapsulate the full load/save logic. Updated `Task.load()` and `Task.save()` to delegate to these new functions. Removed `_ordered_metadata()` method (absorbed into `serialize_frontmatter`). Removed unused `copy` import.
- **Deviations from plan:** None significant. The plan's `Task.load()` pseudocode showed `{}, raw, []` for no-frontmatter case; actual implementation kept the existing try/except error handling wrapper around it.
- **Issues encountered:** None. Exact roundtrip match confirmed on real task files.
- **Key decisions:** `parse_frontmatter()` returns `None` (not a tuple) when no frontmatter found, matching the plan. `BOARD_KEYS` is a module-level constant in `task_yaml.py`; `Task._BOARD_KEYS` is aliased to it for backward compatibility within the board.
- **Notes for sibling tasks:** The `task_yaml` module is ready for import by `aitask_merge.py` (t228_2). Import pattern: `from task_yaml import parse_frontmatter, serialize_frontmatter, _TaskSafeLoader, _FlowListDumper, BOARD_KEYS`. The module lives in `aiscripts/board/` — sibling scripts in the same directory can import directly. Scripts outside that directory will need `sys.path` adjustment or package-style imports.
