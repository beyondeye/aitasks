---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [core]
created_at: 2026-03-25 22:10
updated_at: 2026-03-25 22:10
---

## Bug: `archived-task` subcommand fails for child task IDs

### Symptom
`/aitask-qa 465_2` (and `/aitask-revert`) fail to find archived child tasks. The `aitask_query_files.sh archived-task 465_2` call exits with code 1.

### Root Cause
`cmd_archived_task()` in `aitask_query_files.sh:126-149` only accepts plain numeric task IDs via `validate_num` (regex `^[0-9]+$`). Child task IDs like `465_2` contain an underscore, causing `validate_num` to `die()`.

Even if validation passed, the function only looks for parent-level files (`$ARCHIVED_DIR/t${num}_*.md`), not child files in subdirectories (`$ARCHIVED_DIR/t${parent}/t${parent}_${child}_*.md`).

### Required Fix
Extend `cmd_archived_task` to handle `<parent>_<child>` format:

1. **Parse the ID:** If the input matches `^[0-9]+_[0-9]+$`, split into parent and child numbers
2. **Filesystem lookup:** Check `$ARCHIVED_DIR/t${parent}/t${parent}_${child}_*.md`
3. **tar.gz fallback:** Call `search_archived_task` with the parent ID for bucket computation, but use pattern `(^|/)t${parent}_${child}_.*\.md$` to match only the specific child

### Files to modify
- `.aitask-scripts/aitask_query_files.sh` — `cmd_archived_task()` function (primary fix)
- `.aitask-scripts/lib/archive_scan.sh` — optionally extend `search_archived_task()` to accept a custom pattern parameter, or build the pattern in the caller

### Affected callers
- `.claude/skills/aitask-qa/task-selection.md:43` — calls `archived-task <parent>_<child>`
- `.claude/skills/aitask-revert/SKILL.md:41` — same pattern

### Test scenario
```bash
# Should find the archived child task file (or tar.gz entry)
./.aitask-scripts/aitask_query_files.sh archived-task 465_2
# Expected: ARCHIVED_TASK:<path> or ARCHIVED_TASK_TAR_GZ:<archive>:<entry>
# Current:  Exit code 1 (die from validate_num)
```
