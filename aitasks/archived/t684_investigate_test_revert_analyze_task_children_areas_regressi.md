---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [testing, bash_scripts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-27 17:26
updated_at: 2026-04-28 13:47
completed_at: 2026-04-28 13:47
boardcol: now
boardidx: 10
---

The macOS audit (t658) baseline run revealed `tests/test_revert_analyze.sh` failing with 17/60 assertions failing. Two distinct failure patterns:

## Pattern 1: `--task-commits` doesn't see child commits

```
=== Test: --task-commits parent includes children ===
  FAIL: parent commits include child 50_1
    expected to contain: |50_1
    actual: COMMIT|...|bug: Fix auth validation (t50)|...
COMMIT|...|feature: Add auth module (t50)|...
  FAIL: parent commits include child 50_2
    ...
```

The script returns parent commits (`(t50)`) but not child commits (`(t50_1)`, `(t50_2)`). The test fixture creates child-tagged commits that the script's parsing logic seems to be filtering out.

## Pattern 2: `--task-children-areas` returns NO_CHILDREN

```
=== Test: --task-children-areas for parent with children ===
  FAIL: children-areas has CHILD_HEADER 50_1
    expected to contain: CHILD_HEADER|50_1|
    actual: NO_CHILDREN
  FAIL: 50_1 child name is login
    actual: NO_CHILDREN
  FAIL: 50_1 has 2 commits
    actual: NO_CHILDREN
  ...
```

Every `--task-children-areas` test case for the parent task returns `NO_CHILDREN`, even though the test setup creates a parent task with two children plus child commits. The discovery logic appears broken — possibly the script looks for child tasks via the wrong path (active vs. archived), or via a frontmatter field that the test fixture doesn't set, or the regex/parsing has drifted.

## Failure summary

`Results: 43 passed, 17 failed, 60 total`. The basic `--help`, `--recent-tasks`, `--task-files`, `--find-task` paths all pass. The two child-aware features are broken.

This test is **not** macOS-specific — the bugs are in the production script's logic. Out of scope for the macOS audit.

## Suggested approach

1. Read `.aitask-scripts/aitask_revert_analyze.sh` for the `--task-commits` and `--task-children-areas` subcommand handlers.
2. Reproduce against the test fixture in isolation (the test creates a synthetic git history under `/tmp` with parent task `t50` and children `t50_1`/`t50_2` — replay that and run the script).
3. Identify whether the regression is in:
   - the regex that extracts task IDs from commit messages (does it match `(t50_1)` correctly?), or
   - the child-discovery path (does it look in `aitasks/t50/` or `aitasks/archived/t50/` correctly?), or
   - a field that the script depends on but the fixture doesn't set up.
4. Fix; re-run the test until 60/60 pass.

## Verification

`bash tests/test_revert_analyze.sh` reports `Results: 60 passed, 0 failed, 60 total`.
