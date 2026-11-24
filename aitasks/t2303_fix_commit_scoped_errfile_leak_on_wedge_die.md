---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tests, tmp_cleanup]
assigned_to: dario-e@beyond-eye.com
anchor: 2290
followup_kind: upstream_defect
created_at: 2026-11-15 17:26
updated_at: 2026-11-24 18:02
---

## Origin

Spawned from t2290 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/task_utils.sh:1017` — `task_git_commit_scoped`
  creates `ait_commit_scoped_err.*` before `assert_data_worktree_clean`,
  which `die`s on a wedged data worktree, so every wedge-die leaks one empty
  temp file.

## Diagnostic context

t2290 ran every shell test under a per-run TMPDIR guard
(`tests/run_shell_test.sh`). `ait_commit_scoped_err.*` was left by
test_task_commit_scoped.sh, test_issue_update_ledger.sh and
test_task_data_writer_guard.sh, which drive the wedge-die path on purpose.
The helper allocates the error file (`mktemp`, line ~1017), then calls
`assert_data_worktree_clean add -- "$@"` (stage path) and later
`assert_data_worktree_clean commit -- "$@"`. Both run in the current shell
on purpose (a `die` inside `$( )` would only exit the subshell; see the
comment above the add), so a wedge exits the whole process with the file
still on disk. The removals at the `return 2` and the final return are never
reached. In production that is one empty file in `/tmp` per wedge-die; the
test-side redirect for the three tests is in t2302.

## Suggested fix

Allocate the error file only after each `assert_data_worktree_clean` call
(after the add-assert for the stage step; remove it before the commit-assert
and allocate again after it), or create it lazily at its first use. Keep the
asserts in the current shell and keep their labels (`add` / `commit`)
unchanged; tests pin those messages.
