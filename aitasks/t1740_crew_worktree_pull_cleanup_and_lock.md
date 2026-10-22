---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness]
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-09-08 12:46
updated_at: 2026-09-08 12:46
---

## Origin

Risk-mitigation ("after") follow-up for t1725_1, created at Step 8d after implementation landed.

## Risk addressed

Code-health / goal — crew worktrees abort unconditionally with no serialization.

From t1725_1's `## Risk`:
> The deferred gateway/crew/sync paths still leave wedges after this lands, so the
> parent's "any framework-driven pull" wording is not yet fully met · severity: low

## Goal

Two crew pull sites run `git pull --rebase --quiet 2>/dev/null || true`, which
leaves a conflicted rebase behind in the crew worktree:

- `.aitask-scripts/aitask_crew_setmode.sh:125`
- `.aitask-scripts/aitask_crew_addwork.sh:328`

Apply the ownership-checked cleanup t1725_1 built, and add serialization.

### The "private worktree" assumption is false — check it before relying on it

An earlier draft of t1725_1 justified skipping the lock with "a crew worktree has
exactly one writer by construction". That was asserted, not verified, and it does
not hold:

- there is **no lock anywhere in the crew family** — `aitask_crew_setmode.sh`,
  `aitask_crew_addwork.sh` and `lib/agentcrew_utils.sh` contain no
  `stale_lock_acquire` / `registry_lock_acquire` / `ait_lock_dir` call and no `trap`;
- `.aitask-scripts/brainstorm/brainstorm_session.py` invokes both scripts
  programmatically, so two runs against one crew worktree are plausible rather than
  theoretical, and they would start from the same HEAD and produce matching
  `orig-head` evidence — the one case the ownership helper cannot decide.

Also note a crew worktree is private to one *crew*, not to one *invocation*: an
interrupted earlier run or a manual recovery can leave a rebase behind, so an
unconditional `rebase --abort` can discard work it did not start.

### Shape

`ait_rebase_abort_if_ours` is already repo-agnostic — it takes a runner, so it works
with plain `git` inside the crew worktree. The pull mutex is currently hard-wired to
the data git-dir (`ait_pull_mutex_acquire` derives it from `_data_wedge_gitdir`);
generalize it to take a git-dir so the crew window can hold its own lock.

Consequences to design for, found while planning t1725_1:

- the depth/token bookkeeping must become **per lock dir**, since one process can
  legitimately hold the data lock and a crew lock at once — a single global counter
  would break;
- both crew commit blocks run inside a `( cd "$WT_PATH" … )` **subshell**, which a
  parent-level `EXIT` trap does not cover, so the release must be explicit with a
  subshell-scoped trap as the backstop;
- the crew scripts do **not** currently source `lib/task_utils.sh` (only
  `terminal_compat.sh`, `launch_modes_sh.sh`, `agentcrew_utils.sh`), so the helpers
  have to be made reachable — sourcing it is load-inert (data-worktree detection is
  lazy) but is a decision worth recording.

## Key files

- `.aitask-scripts/aitask_crew_setmode.sh` (~119-127, the commit block)
- `.aitask-scripts/aitask_crew_addwork.sh` (~320-330, the commit block)
- `.aitask-scripts/lib/task_utils.sh` — `ait_pull_mutex_acquire` /
  `ait_pull_mutex_release`, `ait_rebase_abort_if_ours`, `_ait_inprogress_state_at`
- `.aitask-scripts/brainstorm/brainstorm_session.py` — the programmatic caller

## Verification

- Two concurrent `aitask_crew_addwork.sh` runs against one crew worktree: the second
  reports the skipped-pull outcome, starts no rebase, and does not touch the first's
  state. Release, re-run → it proceeds (the control proving it was the lock, not a
  broken fixture).
- A crew worktree left mid-rebase by a killed earlier run → the next invocation
  leaves it in place and says so, rather than aborting it.
- A conflicted crew pull that IS this invocation's own → aborted, no `rebase-merge`
  left, and the following crew commit succeeds.
- Per-dir independence: holding a crew-git-dir lock and a data-git-dir lock in one
  process both succeed, and releasing one leaves the other held (this is what a
  single global depth counter fails).
- After every path, the crew lock dir is gone (subshell-exit release).
- Mutation-test both directions, as t1725_1 did: neuter the abort and confirm the
  cleanup assertions fail; neuter the ownership check and confirm the
  "left in place" assertions fail. Cheap, and it caught a vacuous lock assertion
  in t1725_1.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1747_3** id=2026-09-11T12:10:57Z.b79db71fa293b319a9a596d6 from=t1747_3 from_verified=yes at=2026-09-11T12:10:57Z base=c78deab369254f559285e8ab2bdf73878049e808 base_branch=main dirty=no host=omg16
>
> | Context for the planned ait_pull_mutex_acquire generalization. Line numbers are as of c78deab36, the base t1747_3 was cut from; re-resolve them by function name.
> | 
> | lib/task_utils.sh::ait_pull_mutex_acquire:1071 derives its git-dir from _data_wedge_gitdir, and `[[ -z "$gitdir" ]] && return 0` (:1076) runs WITHOUT the mutex when that git-dir cannot be resolved. The comment calls this "the pre-existing behaviour". t1747_3 measured the condition as reachable: from linked and crew worktrees, a failing `git -C .aitask-data rev-parse --absolute-git-dir` leaves the data git-dir unresolvable. In its A10 fixture, that path published a withheld commit through ait sync.
> | 
> | The unlocked fallback is half of the upstream defect now tracked as t1796 (_ait_inprogress_state_at reads an empty git-dir as "clean"). When you change the mutex to take a git-dir, give the empty/unresolvable case an explicit disposition rather than carrying the silent unlocked return forward, and coordinate with t1796 so the two tasks do not choose different answers for the same helper. The rule and dispositions are in aidocs/framework/failopen_git_probes.md.

> **✉ note:t2024** id=2026-10-16T05:02:54Z.3d3d8b0b9f8cb4064f579145 from=t2024 from_verified=yes at=2026-10-16T05:02:54Z base=989687394d156e04d8cd8a58ae71735104b56ab6 base_branch=main dirty=no host=omg16
>
> | t2024 (commit ae0074ab7) rewrote the two crew pull sites your task targets. Line refs as of that commit:
> | 
> | - `aitask_crew_setmode.sh:125` and `aitask_crew_addwork.sh:328` no longer run `git pull --rebase`. Both call `crew_pull_rebase` in `lib/agentcrew_utils.sh:170`: a bounded fetch of the tracked branch (`git fetch --quiet -- <remote> <merge_ref>` via `lib/bounded_run.py`, limited to `AIT_CREW_GIT_TIMEOUT` seconds, default 10), then a local `git rebase --no-autostash --quiet`, but only when the fetch succeeded. `crew_push` (line 137) is bounded the same way. So the shared lib now holds crew pull/push helpers, the natural place for any lock you add.
> | - In addwork the publish steps now run in the MAIN shell after the commit subshell (`aitask_crew_addwork.sh:342-350`), each guarded by `_AIT_CREW_STOP` (a TERM stop request, line 29). setmode still calls `crew_pull_rebase .` inside its subshell (line 127).
> | - Still true as of that commit: the crew family has no lock. t2024 added time bounds, not serialization.
> | 
> | Advisory context only.

> **✉ note:t2028** id=2026-10-22T07:40:54Z.4f08732ea6e076631b6138fc from=t2028 from_verified=yes at=2026-10-22T07:40:54Z base=8083796bcfdf13e8941f7f04d3daba1ef17a5b45 base_branch=main dirty=yes host=omg16
>
> | t2028 (code commit 8083796bc) rewrote the crew pull and commit paths your task targets. The line refs below are as of that commit, so re-derive them before editing.
> | 
> | - addwork and setmode no longer run `git add`/`git commit` themselves. Both call `crew_commit_paths` (`lib/agentcrew_utils.sh`). It refuses while a merge or rebase is unfinished, re-checks before committing, and commits with plumbing: `write-tree` → `commit-tree -p <pre>` → compare-and-swap `update-ref <branch> <new> <pre>`, retrying up to 3x when the branch moved. It can never conclude a merge or commit onto a rebase's detached HEAD.
> | - Both scripts refuse up front (`crew_require_clean`, right after `resolve_crew`) when the worktree has an unfinished merge or rebase.
> | - `crew_pull_rebase` now opens the rebase only when `git merge-tree --write-tree` proves it clean. A proven conflict leaves the branch as it is with a warning; git < 2.38 (exit 129) rebases as before. A rebase that stops anyway is LEFT IN PLACE AND REPORTED, NEVER ABORTED, with return 2. On 2, addwork/setmode skip the push and exit non-zero.
> | - Design decision you may want to weigh: plan review showed that an abort-if-ours guard cannot be proven safe in the shared crew worktree. `rebase --abort` is a hard reset, and another process's *staged* write makes worktree == index, so a worktree-vs-index foreign-write check sees nothing while the abort discards it. Your planned `ait_rebase_abort_if_ours` recovery would conflict with that choice.
> | - Python `git_commit_push_if_changes` uses the same plumbing (`_commit_index`) and skips, with a stderr warning, while an operation is unfinished.
> | - A shell twin of `crew_merge_state` now exists in `lib/agentcrew_utils.sh`.
> | 
> | There is still no lock in the crew family; t2028 did not add one. The architecture doc's "Concurrent Write Strategy" section describes the current writer rules.
> | 
> | This is advisory context only. Whether a lock is still worth adding is your decision.
