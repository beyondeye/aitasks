---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
anchor: 1599
followup_kind: upstream_defect
created_at: 2026-09-02 09:01
updated_at: 2026-09-02 09:01
---

## Origin

Spawned from t1599_3 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_sync.sh:1078` — the interactive conflict-resolution
  loop runs `task_git add "$f" 2>/dev/null || true` while the data worktree is
  mid-rebase. `add` is on neither `_ait_git_subcmd_is_readonly` nor
  `_ait_git_subcmd_is_recovery`, so `assert_data_worktree_clean` calls `die`,
  which is `exit 1` (`lib/terminal_compat.sh`). That exits the
  `echo "$remaining" | while IFS= read -r f` subshell, so the loop **stops after
  the first file**, and `2>/dev/null` swallows the diagnostic entirely. The user
  sees the editor open for one file, then the rebase fail for reasons never
  printed.

The sibling site at `.aitask-scripts/aitask_sync.sh:940` gets this right:

```bash
add_err="$(AIT_GIT_SKIP_STATE_CHECK=1 task_git add "$f" 2>&1)" || add_rc=$?
```

## Diagnostic context

Found while implementing t1599_3 (per-task scoping of the pre-sync sweep). That
task rewrote `auto_commit` and did not touch the conflict path, so the defect was
recorded rather than fixed — it needs its own regression test, and mixing it into
an already large change would have left it untested.

The same class of bug bit t1599_3 itself in a different place: `check_remote`
runs `task_git remote get-url origin &>/dev/null`, and `remote` is likewise on
neither allowlist, so on a wedged worktree the script exited 1 with **empty
stdout and empty stderr** — which every consumer of the batch protocol reads as
`ERROR: empty output from sync script`, and which the syncer escalates into an
offer to spawn a code agent. t1599_3 fixed that by probing the six git-dir
sentinels at the top of `main()` and emitting `DEFERRED:worktree_wedged`.

## Suggested fix

Mirror `:940`: capture the output, use `AIT_GIT_SKIP_STATE_CHECK=1` (this code
path owns the rebase it is resolving, which is exactly the documented bypass),
and route on the exit status instead of `|| true` so a failed stage is reported
rather than silently downgraded to "resolved". Restructure the `while` loop so
it does not run in a pipeline subshell, or the early-exit failure mode survives
the fix.

Regression test: drive the interactive path with two conflicted files and assert
both are offered and both are staged — `tests/test_sync_branch_mode_automerge.sh`
already exercises this area and documents the authorization/swallowed-failure
class in its header.
