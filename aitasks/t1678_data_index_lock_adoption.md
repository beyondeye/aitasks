---
priority: high
effort: high
depends: [1676, 1677]
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness, crash_recovery]
gates: [risk_evaluated]
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-09-02 09:02
updated_at: 2026-09-02 09:45
---

## Origin

Risk-mitigation ("after") follow-up for t1599_3, created at Step 8d after implementation landed.

## Risk addressed

`addresses: code-health + goal-achievement — the `data_index` mutex introduced
in t1599_3 Step 3a is respected only by that sweep, leaving mutual exclusion
incomplete`

From p1599_3's `## Risk`:

> Residual TOCTOU: the `data_index` mutex is respected only by this sweep, and
> the claim path's acquire → write → commit sequence (`aitask_pick_own.sh`) is
> outside this child's ownership, so mutual exclusion is incomplete. Steps 5a.1-4
> reduce the window to a sub-millisecond one that cannot publish, but do not
> eliminate it · severity: medium

## Goal

`.aitask-data` is **one worktree with one index**, shared by every session on the
machine — `aitask_init_data.sh` refuses a second checkout of `aitask-data`, and
per-task worktrees symlink to the same directory (`lib/data_symlinks.sh`). Yet
`task_git()` (`lib/task_utils.sh`) does no locking at all, and
`assert_data_worktree_clean` is a *state* check for six git-dir sentinels — it
says nothing about another session's staged entries or about `index.lock`
contention.

t1599_3 introduced a named machine-local mutex, `ait_lock_dir data_index`
(via `lib/registry_lock.sh` over `lib/stale_lock.sh`), and made `ait sync`'s
sweep hold it across its whole classify → commit phase. That serializes sync
against **other syncs** — a real and frequent case, since the CLI, the board and
the syncer all invoke it — and it establishes the lock other writers migrate to.

It does **not** serialize sync against anything else. Complete the adoption:

- `.aitask-scripts/aitask_pick_own.sh` — the important one. It acquires the task
  lock, writes the task file via `aitask_update.sh`, and only then commits; that
  window is hundreds of milliseconds and is precisely the TOCTOU t1599_3 could
  only narrow. The lock must be held across acquire → write → commit, which is
  why it could not be done from t1599_3 (exclusive script ownership).
- `.aitask-scripts/aitask_gate.sh` — ledger appends + path-scoped commits.
- `lib/attachment_lock.sh` — attach/artifact transactions already take a mutex,
  but a *different* one (`.aitask-data/attachments/.attach.lock`), so they are
  serialized against each other and not against sync. Decide whether to fold it
  into `data_index` or to nest.

Audit for others with `grep -rn "task_git \(add\|reset\|commit\)" .aitask-scripts/`.

## Constraints

- **Fail closed.** Every adopting call site must treat a failed acquisition as
  "do not write", never as "proceed unlocked" — the rule t1599_3's sweep follows.
- Do not hold the mutex across an unbounded operation (a network fetch, an
  editor, an agent turn). `lib/merge_lock.sh` documents why: `stale_lock.sh`'s
  guard reclaim assumes guarded sections are short.
- `registry_lock_acquire` installs an EXIT trap, so a holder that exits normally
  releases; `stale_lock.sh` reclaims a dead PID. A sequence spanning multiple
  processes needs `merge_lock.sh`'s no-trap treatment instead.

## Verification

Drive two concurrent writers deterministically (the `pre_commit_phase` /
`pre_group_commit` marker-gated seams in `aitask_sync.sh` are the existing
precedent, gated on `<lock_base>/.ait_sync_test_seams`) and assert the second
blocks rather than interleaving. Include the fail-closed case: hold the lock
from another process past the acquire budget and assert the writer commits
nothing and reports the contention.

## Dependencies — why, not just what

`depends: [1676, 1677]`. Both edges are real; neither is bookkeeping.

- **t1677 is an ORDERING dependency, not a file collision.** t1677's whole job is
  to *create new index-writing call sites* — the settings TUI, the board and the
  stats surface committing their own `aitasks/metadata/*` writes. This task's job
  is to make every index writer take the `data_index` lock. Run before or
  alongside t1677, this task's audit cannot see writers that do not exist yet, so
  the adoption lands incomplete — and **this task's own tests would still pass**,
  because nothing here knows those call sites were coming. Re-run the audit after
  t1677 has landed:

  ```bash
  grep -rn "task_git \(add\|reset\|commit\)" .aitask-scripts/
  ```

- **t1676 is a file collision.** It edits the interactive conflict loop in
  `.aitask-scripts/aitask_sync.sh`, which this task's audit also covers (5
  `task_git add|reset|commit` sites there today). `.aitask-data` is a single
  shared worktree, so two agents editing that file concurrently is the hazard
  t1599 exists to remove.

Sibling note: `t1599_4` is unblocked and sweeps `aitask_create.sh`,
`aitask_update.sh`, `aitask_archive.sh`, `aitask_zip_old.sh` and
`aitask_issue_import.sh` for unscoped commits. It does **not** collide on files
with this task, but its tripwire scans every script and will report on
`aitask_pick_own.sh` / `aitask_gate.sh` while this task is mid-flight — by
design; it is instructed to report rather than edit across the boundary.
