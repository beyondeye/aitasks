---
Task: t160_board_outdated_typing_imports.md
---

## Context

Code review found that `aiscripts/board/aitask_board.py` uses `from typing import List, Dict` which is outdated since Python 3.9+. Built-in `list` and `dict` now support subscripting directly.

## Plan

### Step 1: Replace typing imports and usages in `aiscripts/board/aitask_board.py`

1. Remove `from typing import List, Dict` (line 12)
2. Replace all occurrences:
   - `Dict[str, Task]` → `dict[str, Task]` (lines 211, 212)
   - `List[Dict]` → `list[dict]` (line 213)
   - `List[str]` → `list[str]` (line 214)
   - `List[Task]` → `list[Task]` (lines 266, 280, 311, 1363, 2369)

## Verification

- Run `python -c "import ast; ast.parse(open('aiscripts/board/aitask_board.py').read())"` to verify syntax
- Grep for remaining `List[` or `Dict[` to confirm none were missed

## Final Implementation Notes
- **Actual work done:** Removed `from typing import List, Dict` import and replaced all 9 usages of `List[...]` and `Dict[...]` with built-in `list[...]` and `dict[...]`
- **Deviations from plan:** Initial bulk replace of `Dict[` missed `list[Dict]` (no opening bracket after Dict). Fixed with a targeted edit.
- **Issues encountered:** None
- **Key decisions:** Used `replace_all` for bulk replacement, then caught the edge case where `Dict` appeared as a subscript inside `list[Dict]` without its own bracket
