---
priority: medium
effort: low
depends: []
issue_type: refactor
status: Ready
labels: [review]
created_at: 2026-02-17 18:23
updated_at: 2026-02-17 18:23
---

## Code Review Finding: Outdated Typing Imports

**Mode:** Python Best Practices
**Severity:** Medium
**Location:** `aiscripts/board/aitask_board.py:12`

### Description

The file uses `from typing import List, Dict` and then uses `List[...]` and `Dict[...]` type annotations throughout. Since Python 3.9+, the built-in `list` and `dict` types support subscripting directly, making the `typing` imports unnecessary.

### Affected Lines

- Line 12: `from typing import List, Dict`
- Line 211: `self.task_datas: Dict[str, Task] = {}`
- Line 212: `self.child_task_datas: Dict[str, Task] = {}`
- Line 213: `self.columns: List[Dict] = []`
- Line 214: `self.column_order: List[str] = []`
- Line 266: `-> List[Task]`
- Line 280: `-> List[Task]`
- Line 311: `-> List[Task]`
- Line 1363: `tasks_to_commit: List[Task]`
- Line 2369: `tasks: List[Task]`

### Suggested Fix

1. Remove `from typing import List, Dict` import
2. Replace all `List[...]` with `list[...]` and `Dict[...]` with `dict[...]`
