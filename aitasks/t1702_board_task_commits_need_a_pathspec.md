---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [git, task_metadata, robustness]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1710]
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-03 12:12
updated_at: 2026-09-04 15:53
---

## Origin

Spawned from t1677 during Step 8b review.

## Upstream defect

- `.aitask-scripts/board/aitask_board.py:14164` — `_do_git_commit_tasks` runs
  `git commit -m <msg>` with **no pathspec**, committing the whole shared
  `.aitask-data` index; the delete (`:14029`) and rename (`:14126-14141`)
  paths do the same. These commit task files, so they are outside t1677's
  metadata scope, but they can carry another session's staged work under this
  board's message — the same defect class t1599 addressed for `ait sync`,
  `aitask_pick_own.sh`, `aitask_create.sh` and `aitask_fold_mark.sh`.

Re-derive the call-site list before starting; do not trust this one.

## Diagnostic context

t1677 wrapped the existing shell seam (`task_git_commit_scoped`) from Python
rather than adding a second scoped-commit implementation, precisely because
**every pre-existing Python commit site in the tree is a pathspec-less `git
commit`** — copying one would have re-created the index-wide swallow t1599
exists to eliminate. `settings_app._commit_profile` was one of them and was
deleted by t1677. The board's three sites are the ones that remain.

This is not hypothetical. While t1677 was being implemented, a concurrent
session (t1675) held uncommitted work across seven files in the same worktree,
and new foreign entries (`.claude/settings.json`, `.claude/hooks/`,
`tests/test_guard_live_tmux.sh`) appeared mid-session. That is exactly the
condition under which a pathspec-less commit publishes another session's work
under an unrelated message.

## Suggested fix

Route all three sites through `task_git_commit_scoped` (`lib/task_utils.sh`),
which uses `commit -o -- <paths>` and therefore takes worktree content for the
named paths only, bypassing the shared index. Each site already knows the task
file(s) it is acting on, so the pathspec is available at every call.

## Verification

- a bystander control: a file staged by a simulated concurrent session must not
  appear in the board's commit, for each of the create / delete / rename paths
- negative control: each assertion must fail against today's pathspec-less
  `git commit`

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-03T20:26:42Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-04T10:02:02Z status=pass attempt=1 type=human
