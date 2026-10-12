---
priority: medium
effort: high
depends: []
issue_type: enhancement
status: Ready
labels: [git, sync, concurrency, robustness]
gates: [risk_evaluated]
anchor: 1599
created_at: 2026-10-12 16:42
updated_at: 2026-10-12 16:42
---

## Problem

The task-data pull at the start of every pick almost never succeeds on a box where
several agents share one checkout. `aitask_pick_own.sh` (~L200) calls `task_sync()`
(`lib/task_utils.sh` ~L801). That runs `_task_pull_rebase`, i.e.
`git pull --rebase`, which refuses on **any** unstaged tracked change. The shared
`.aitask-data` worktree is dirty almost all the time, because live sessions hold
modified task files. So the pull fails with
`data worktree has unstaged changes blocking rebase; reconcile with 'ait syncer'`,
and the pick goes ahead on stale task data. That message was seen live on the t1696
pick (2026-10-12).

`./ait sync` already recovers both shapes safely:
- **Behind only** (t1725_3): fast-forward (`merge --ff-only`), deferring only when an
  incoming commit touches a protected file.
- **Diverged** (t1731): a guarded merge. It merges only if the two sides changed
  disjoint files, and refuses whenever safety cannot be proven.

`ait sync` has to be run by hand, though, and nothing in an ordinary pick uses that
logic.

## Goal

Make the pick-time task-data pull recover automatically in the cases that are
provably safe, using the **same guarded-merge logic** as `ait sync`, not a copy of it:

1. **Extract** the guarded merge from `aitask_sync.sh` into a shared helper both
   callers use. Today that is `_guarded_merge_prepare` (~L1649),
   `_converge_by_guarded_merge` (~L1760), and the behind-only fast-forward in
   `main` (~L2252). The helper must take the **protected path set as input**
   rather than reading the sweep's `PROT_*` globals, which only `ait sync`'s sweep
   builds from the lock branch.
2. **Wire it into `task_sync()`**:
   - behind-only → fast-forward;
   - diverged → guarded merge;
   - anything unsafe → decline and keep today's best-effort failure and hint.
   `task_sync()` never commits other sessions' files, so for this caller **every
   modified or untracked path in the worktree is protected**. That is stricter than
   sync, so it can only decline more often, never merge more.
3. **Preserve every unfinished edit.** Protected bytes stay identical, are never
   staged or committed, and there is no stash or autostash. Keep sync's
   `--no-autostash --no-overwrite-ignore` advance (see t1792).
4. **Publish.** After a successful merge, the merge commit must be pushed, or the
   divergence comes back. Decide whether `task_sync()` pushes or leaves it to the
   pick's existing `task_push`, and pin the choice.

**`task_data_converge()` is in scope only if it still has callers when this task is
planned.** Today its only callers are the stats writers (`verified_update_lib.sh`
~L231, ~L288). t1912 moves those writers off `aitask-data` and plans to remove that
converge. Check with
`grep -rn task_data_converge .aitask-scripts | grep -v '^\s*#'` at planning time.

## Non-goals

- Changing when `ait sync` itself defers, or its sweep / commit-on-behalf behaviour.
- Making the pull block or die: `task_sync()` stays best-effort and must never abort
  a pick (see its header comment).
- Task frontmatter conflict auto-merge (t1727, landed; t1459).

## Acceptance criteria

- **Behind only**, live-held dirty file, incoming commits disjoint from it: the pick's
  pull fast-forwards; the dirty file is byte-identical, still dirty, and in no commit.
- **Diverged**, disjoint sides: the pull converges with a guarded merge and the
  result reaches origin (0 ahead / 0 behind); protected bytes are preserved.
- **Every decline case keeps today's outcome**, with nothing changed (HEAD, index and
  worktree identical) and the refusing guard named:
  - an incoming commit touches a dirty path;
  - the sides overlap;
  - multiple merge bases;
  - an ignored file would be written;
  - a ref moves mid-run;
  - the worktree is mid-rebase.
- **One implementation:** `ait sync` and `task_sync()` call the same helper.
  `tests/test_sync_guarded_merge.sh` passes unchanged, apart from call-site seams.
- **Mutants:** one per recovery path (fast-forward, guarded merge), each turning only
  its own cell red, plus a "recovery exits non-zero after doing the work" mutant.
- `tests/test_metadata_partial_sync_recovery.sh` (t1696) still passes. If
  `task_data_converge()` is still wired in at planning time, update its Cell B: it
  currently expects the second update to stay `UPDATED_REMOTE_ONLY` / `[diverged]`.
  Change that to the self-healed outcome, and keep a cell where the merge must
  decline.

## Related

- **Trail:** `art:trail-parallel-git-and-sync` (owner t1725). Trail membership is an
  explicit list, so this task joins it on the next trail refresh (`/aitask-trail`).
  Suggested placement: after wave 4 (t1912), alongside wave 8's shared helpers.
- **t1912** (stats off the data branch, wave 4): removes the stats-driven divergence
  and likely the only callers of `task_data_converge()`. Plan this task against
  t1912's landed state if it lands first. It does not cover divergence from other
  machines' task commits, which is what this task handles.
- **t1731** (landed `e2f12c499`): the guarded merge being extracted.
  **t1725_3** (landed): sync's behind-only fast-forward.
- **t1792**: enforce `--no-autostash` / `--no-overwrite-ignore` in sync. The
  extracted helper must keep both flags. Coordinate if t1792 lands first, since it
  edits the same functions.
- **t1678** (data-index lock adoption): `task_sync()` writes the shared index/HEAD.
  If t1678 lands first, the new merge path must take that lock too.
- **t1715** (stale-lock reaping): affects only `ait sync`'s protected set. This
  task's caller treats all dirty paths as protected, so stale locks do not widen
  or narrow it.
- **t1696** (archived): pinned that the `./ait sync` hint recovers. Its test is the
  regression baseline above.
