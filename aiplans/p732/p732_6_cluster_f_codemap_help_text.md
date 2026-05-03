---
Task: t732_6_cluster_f_codemap_help_text.md
Parent Task: aitasks/t732_fix_failing_pre_existing_test_suite.md
Sibling Tasks: aitasks/t732/t732_*.md
Archived Sibling Plans: aiplans/archived/p732/p732_*.md
Worktree: (current branch — fast profile sets create_worktree:false)
Branch: (current branch)
Base branch: main
---

# p732_6 — Cluster F: codemap help text drift

## Goal

Resolve the single failing assertion in `tests/test_contribute.sh:558` (1 of 123 — smallest scope).

## Confirmed failure (today)

```
FAIL: codemap help mentions shared venv (expected output containing 'shared aitasks Python')
```

## Steps

1. Read `aitasks/t732/t732_6_cluster_f_codemap_help_text.md` for context.
2. Read `tests/test_contribute.sh` lines 540-565 (test block + sibling assertions).
3. Read `.aitask-scripts/aitask_codemap.sh` help/usage function.
4. `git log --follow -p .aitask-scripts/aitask_codemap.sh | grep -B5 'shared aitasks Python'` to see if the string ever existed.
5. Decide source-of-truth:
   - String was removed → update test assertion to match current help.
   - String was never added → add to help text (consistent with surrounding documentation that uses "shared aitasks Python").
6. Apply the one-line fix.
7. `bash tests/test_contribute.sh` reports 123 passed / 0 failed.

## Verification

- `bash tests/test_contribute.sh` passes.
- Manual: `./.aitask-scripts/aitask_codemap.sh --help` shows consistent venv-naming string.

## Step 9

Archive via `./.aitask-scripts/aitask_archive.sh 732_6`.
