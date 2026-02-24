---
Task: t228_5_tests_and_documentation.md
Parent Task: aitasks/t228_improved_task_merge_for_board.md
Sibling Tasks: aitasks/t228/t228_1_*.md, aitasks/t228/t228_2_*.md, aitasks/t228/t228_3_*.md, aitasks/t228/t228_4_*.md
Branch: (current branch - no worktree)
Base branch: main
---

# Plan: t228_5 — Tests and Documentation (Verified)

## Goal

Add Python unit tests for merge functions, a test runner script, and documentation for auto-merge rules.

## Verification Notes (vs original plan)

- **`tests/test_sync_merge.sh` — DROPPED.** Redundant: `test_sync.sh` already has 3 auto-merge integration tests (Tests 12-14) and `test_aitask_merge.sh` has 10 merge CLI tests.
- **Python unit tests — still needed.** No `tests/test_aitask_merge.py` exists.
- **Documentation — still needed.** `sync.md` is missing `AUTOMERGED` status.

## Steps

### 1. Create Python Unit Tests (`tests/test_aitask_merge.py`)

Use `unittest` (no external deps). Import functions via sys.path:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'aiscripts', 'board'))
from aitask_merge import parse_conflict_file, merge_frontmatter, merge_body
```

Test classes: TestConflictParser (5 tests), TestMergeRules (16 tests), TestBodyMerge (2 tests).

### 2. Create Test Runner Script (`tests/run_all_python_tests.sh`)

Bash wrapper for python3 -m pytest with PYTHONPATH setup.

### 3. Update Website Documentation (`website/content/docs/commands/sync.md`)

- Add `AUTOMERGED` to batch output protocol table
- Add "Auto-Merge Conflict Resolution" section with rules table
- Update "How It Works" to mention auto-merge

### 4. Verification

1. `bash tests/run_all_python_tests.sh`
2. `bash tests/test_aitask_merge.sh`
3. `bash tests/test_sync.sh`
