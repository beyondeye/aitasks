---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness, syncer]
gates: [risk_evaluated]
anchor: 1599
followup_kind: upstream_defect
created_at: 2026-10-15 15:42
updated_at: 2026-10-15 15:42
---

## Origin

Spawned from t1987 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/task_utils.sh:1319` — a behind-only `pull --rebase` in
  `_task_pull_rebase` still overwrites an ignored local file that an incoming
  commit writes (`pull --rebase` has no `--no-overwrite-ignore`). This is
  t1956's scope: its goal 2 routes behind-only through the fast-forward. It
  was handed over by note, not as a new task.
- `.aitask-scripts/aitask_crew_addwork.sh:328` and
  `.aitask-scripts/aitask_crew_setmode.sh:125` run a raw
  `git pull --rebase --quiet 2>/dev/null || true` without `--no-autostash`.
  That is the same class t1792 and t1987 fixed for sync, the pick pull and
  converge. Found by code reading; not reproduced.

Line numbers are as of commit d931e10c3. Re-derive them before editing.

## Diagnostic context

t1987 added `--no-autostash` to `_task_pull_rebase` (`task_utils.sh`, the
pick-time pull and `task_push`'s retry). It added `--no-autostash
--no-overwrite-ignore` to `task_data_converge`'s fast-forward, with a new
reason `ff_ignored`. Pins: `tests/test_task_push.sh` Tests 11b, 18b, 28b, 29b.

The probes (t1792, re-confirmed on git 2.55 in t1987) show:
- with `rebase.autoStash=true`, `pull --rebase` stashes a dirty tracked file and
  re-applies it (inode and ctime change). The pull then succeeds where git's
  default would refuse;
- `merge --ff-only` and a behind-only `pull --rebase` both silently overwrite an
  ignored file that an incoming commit writes. With `--no-overwrite-ignore`,
  `merge` instead refuses with "The following untracked working tree files would
  be overwritten by merge" and changes nothing.

For the crew scripts, it is **not verified** that crew worktrees ever hold
another live session's uncommitted edits. If they never do, autostash cannot
touch someone else's work, and the item reduces to determinism under a user's
`rebase.autoStash`.

## Suggested fix

- **Crew pulls:** confirm whether the crew worktree pulled at those lines can
  be dirty with someone else's files. Either way, add `--no-autostash` so a
  user's config cannot change behaviour, and pin it with a cell that sets
  per-repo `rebase.autoStash=true` (the pattern of t1987's Test 18b).
- **The `task_utils.sh` item:** do not fix it here. Close it as covered once
  t1956 lands, or fold it into t1956 if that task is still open when this one
  is picked.
