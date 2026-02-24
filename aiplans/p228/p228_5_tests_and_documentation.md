---
Task: t228_5_tests_and_documentation.md
Parent Task: aitasks/t228_improved_task_merge_for_board.md
Sibling Tasks: aitasks/t228/t228_1_*.md, aitasks/t228/t228_2_*.md, aitasks/t228/t228_3_*.md, aitasks/t228/t228_4_*.md
Branch: (current branch - no worktree)
Base branch: main
---

# Plan: t228_5 — Tests and Documentation

## Goal

Add comprehensive tests for the merge script and sync integration, plus documentation.

## Steps

### 1. Python Unit Tests (`tests/test_aitask_merge.py`)

Use `unittest`. Test structure:

```python
import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'aiscripts', 'board'))
from aitask_merge import parse_conflict_file, merge_frontmatter, merge_body

class TestConflictParser(unittest.TestCase):
    def test_full_file_conflict(self): ...
    def test_frontmatter_only_conflict(self): ...
    def test_body_only_conflict(self): ...
    def test_no_conflict_markers(self): ...
    def test_no_frontmatter(self): ...

class TestMergeRules(unittest.TestCase):
    def test_boardcol_keeps_local(self): ...
    def test_boardidx_keeps_local(self): ...
    def test_updated_at_keeps_newer(self): ...
    def test_labels_union(self): ...
    def test_depends_union(self): ...
    def test_priority_keeps_remote_batch(self): ...
    def test_effort_keeps_remote_batch(self): ...
    def test_status_implementing_wins(self): ...
    def test_status_both_non_implementing_unresolved(self): ...
    def test_field_only_in_local(self): ...
    def test_field_only_in_remote(self): ...
    def test_field_same_both_sides(self): ...
    def test_empty_labels_merge(self): ...

class TestBodyMerge(unittest.TestCase):
    def test_identical_bodies(self): ...
    def test_different_bodies(self): ...
```

### 2. Bash Integration Tests (`tests/test_sync_merge.sh`)

Follow `test_sync.sh` pattern:

```bash
#!/usr/bin/env bash
set -euo pipefail
# ... source test helpers, setup_sync_repos ...

test_automerge_boardcol_conflict() {
    # Clone A: change boardcol to "next"
    # Clone B: change boardcol to "now"
    # Sync B → AUTOMERGED, boardcol = "now" (local)
}

test_automerge_labels_merge() {
    # Clone A: add label "api"
    # Clone B: add label "backend"
    # Sync B → AUTOMERGED, labels = [api, backend, original...]
}

test_unresolvable_status() {
    # Clone A: set status "Done"
    # Clone B: set status "Postponed"
    # Sync B → CONFLICT (neither is Implementing)
}

test_implementing_status_wins() {
    # Clone A: set status "Ready"
    # Clone B: set status "Implementing"
    # Sync on A → AUTOMERGED, status = "Implementing"
}

test_no_python_fallback() {
    # Temporarily hide Python
    # Create conflict → CONFLICT (fallback to manual)
}
```

### 3. Documentation

Add to website docs:
- Auto-merge rules reference table
- `AUTOMERGED` batch status in sync protocol docs
- Troubleshooting section for manual conflict resolution
