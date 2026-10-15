---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts, robustness, syncer]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-14 17:46
updated_at: 2026-10-15 15:26
---

## Origin

Spawned from t1792 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/task_utils.sh:1316`: `_task_pull_rebase` (the pick-time
  pull) runs `pull --rebase` without `--no-autostash`. This is owned by t1956,
  and was handed over by note `2026-10-14T14:40:28Z.d9b39599…`.
- `.aitask-scripts/lib/task_utils.sh:1646`: `task_data_converge`'s
  `merge --ff-only` has neither `--no-autostash` nor `--no-overwrite-ignore`.
  Also owned by t1956, same note.
- `tests/test_sync.sh`, `tests/test_sync_branch_mode_automerge.sh` and
  `tests/test_task_push.sh` run `aitask_sync.sh` through their own fixtures.
  Those fixtures still inherit the developer's global and system git config,
  the same leak t1792 fixed in `sync_fixture.sh`.
- `tests/test_linked_trail_jump_live.sh:164` runs `cd` without first calling
  `enter_scratch_cwd`, so `tests/test_cd_guard_lint.sh` fails on the live
  tree. This predates t1792; it came in with commit aa6b5fb2a.

Line numbers are as of commit 02e4a1bad. Re-derive them before editing.

## Diagnostic context

t1792 made `ait sync` ignore a user's `rebase.autoStash` / `merge.autoStash`.
It also made the behind-only fast-forward refuse to overwrite ignored files
(`--no-overwrite-ignore`, pinned target, no rebase fallback). Probes on git
2.55.0 confirmed four things:
- `merge --ff-only` with `merge.autoStash=true` rewrites an unrelated dirty
  tracked file (its inode/ctime change);
- `pull --rebase` with `rebase.autoStash=true` stashes and re-applies a dirty
  tracked file;
- `merge --ff-only` and a behind-only `pull --rebase` both silently overwrite an
  ignored file that an incoming commit writes;
- with `--no-overwrite-ignore`, git refuses at write time and leaves HEAD, the
  index and the worktree unchanged.

The pick-time pull and `task_data_converge` in `lib/task_utils.sh` were outside
t1792's scope (sync only). They have the same gaps.

t1792 added a `sync_isolate_git_config` helper to `tests/lib/sync_fixture.sh`
(`GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1`, exported inside the
subshell that runs the script). Fixtures that do not source `sync_fixture.sh`
did not get it.

The cd-guard lint failure was seen while running t1792's regression suites. It
is unrelated to t1792's changes.

## Suggested fix

- **The task_utils.sh items:** coordinate with t1956. It is extracting sync's
  convergence into a shared helper, and its goal 3 already requires "no stash
  or autostash". Fix them here only if t1956 does not cover them.
- **The fixtures:** isolate global and system git config wherever the
  aitask_sync.sh runs happen. Keep per-repo `user.*`.
- **The cd-guard lint failure:** add `enter_scratch_cwd` to
  `test_linked_trail_jump_live.sh` (see `tests/lib/scratch_cwd.sh`).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T12:26:32Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-15T12:39:57Z status=pass attempt=1 type=human
