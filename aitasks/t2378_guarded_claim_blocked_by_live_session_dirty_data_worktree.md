---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_pick, sync, concurrency, robustness, task_workflow]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
followup_kind: upstream_defect
created_at: 2026-11-27 08:40
updated_at: 2026-11-28 18:39
---

## Origin

Reported from the `animeless` project while picking its task t13 with
`/aitask-pick 13` (profile `fast`, framework 0.42.1) on 2026-11-27. Not spawned
from a Step 8b review: the defect was hit before the task could be claimed.

## Upstream defect

- `.aitask-scripts/aitask_pick_own.sh` `verify_expected_status()` (~L477-487):
  with `--expect-status`, a failed `task_sync` is a hard refusal
  (`STATUS_UNVERIFIED:<reason>`, lock released). When the reason is
  `dirty_worktree`, the cause is any unstaged tracked change in the shared
  `.aitask-data` worktree, including files of an unrelated task that another
  live session is editing. The claim of an unrelated task then cannot succeed
  until that other session commits.
- `.aitask-scripts/lib/task_utils.sh` `_task_push_reason_hint()` (~L2407-2408):
  the `dirty_worktree` hint says "reconcile with 'ait syncer'". In this
  situation the user opened `ait syncer` and it reported no issue in the data
  branch (user's observation; the syncer view was not inspected by the agent),
  so the hint names a remedy that does not apply.
- `task-workflow` `SKILL.md` Step 4, `STATUS_UNVERIFIED:<reason>` branch: for a
  sync classifier code the question text is "`ait syncer` reconciles a stuck
  sync" and the only options are "Retry" and "Pick a different task". Neither
  names the session holding the dirty files or the one command that addresses
  it (`./ait sync --commit-for-task <id>`).
- Minor: each failed attempt printed the same warning line twice.

## Diagnostic context

Sequence observed (all on one host, one user, two agent sessions sharing one
checkout):

1. Step 3 Check 7 (premise staleness) returned `ASK_STALE`; the user answered
   "Review & replan". A pending premise answer makes Step 4 append
   `--expect-status Ready` to the claim.
2. `./.aitask-scripts/aitask_pick_own.sh 13 --email <email> --expect-status Ready`
   exited 1 with:

   ```
   Warning: task data sync failed — data worktree has unstaged changes blocking rebase; reconcile with 'ait syncer'
   Warning: task data sync failed — data worktree has unstaged changes blocking rebase; reconcile with 'ait syncer'
   STATUS_UNVERIFIED:dirty_worktree
   ```

3. `git -C .aitask-data status --short` at that moment showed only another
   task's files modified (its task file and its plan file) plus one untracked
   metadata file. `aitask_lock.sh --check` for that other task showed a lock held
   by the same user on the same host with a live pid. Nothing of t13 was dirty.
   `git status -sb` showed no ahead/behind marker against the upstream ref as of
   the last fetch.
4. "Retry" produced the identical refusal. A background wait of 30 minutes for
   the worktree to become clean timed out.
5. After the other session's edits were committed, the same command returned
   `OWNED:13` with no other change.

So a pick that needs the guarded claim is blocked for as long as any other live
session has uncommitted task or plan edits, which on a multi-session box is most
of the time. An unguarded claim (no pending premise answer) is not blocked: it
proceeds on the best-effort sync, which is the case t1956 describes.

The same code is present at aitasks `main` `dfafd6c6c` (verified by reading
`verify_expected_status()` and the hint there).

## Relation to existing work

- **t1956** (`pick_pull_guarded_merge_recovery`, Ready) addresses the root cause
  in `task_sync()`: the pull is refused on any unstaged tracked change. Its
  problem statement says the pick "goes ahead on stale task data" and its
  non-goals keep `task_sync()` best-effort. It does not mention the
  `--expect-status` caller, where the same failure is a hard stop rather than a
  stale read. If t1956 makes `task_sync()` report `synced` / `up-to-date` when
  the incoming commits are disjoint from the dirty paths (or there are none),
  the first bullet above is resolved by it. The hint and prompt bullets are not
  in its scope. Fold this task into t1956 if that is the better home.

## Suggested fix

Directions, not a decided design:

- The guard needs a current read of ONE task file's status, not a rebased
  worktree. After a successful fetch, the status could be verified against the
  upstream ref's copy of that file (and refuse only when the fetch fails, the
  two copies disagree, or the target task's own file is dirty) — or simply rely
  on t1956's recovery so the sync no longer fails here.
- For `dirty_worktree`, name the dirty paths and their holder instead of
  pointing at `ait syncer`: the sync sweep already derives the holder
  (self / other / remote) and the action `./ait sync --commit-for-task <id>`.
  Carry that into the `STATUS_UNVERIFIED` prompt text in the `task-workflow`
  skill template.
- Print the sync warning once per attempt.

## Acceptance criteria

- With another live session holding uncommitted edits to a different task's
  files, and no incoming commit touching the target task file, a claim with
  `--expect-status Ready` succeeds, or refuses with a message that names the
  dirty paths, their holder and a remedy that works.
- The other session's dirty files stay byte-identical, unstaged and in no commit.
- The guard still refuses when the target task's status cannot be made current
  (fetch failure, incoming change to the target file that cannot be applied).
- A test pins the scenario (two sessions, one shared data worktree).
