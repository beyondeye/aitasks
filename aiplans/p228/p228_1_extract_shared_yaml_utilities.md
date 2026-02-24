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
