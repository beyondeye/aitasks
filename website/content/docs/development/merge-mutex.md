---
title: "Merge Mutex"
linkTitle: "Merge Mutex"
weight: 55
description: "What the merge mutex serializes, what the next task does while it is held, the session anchor it needs, and how to clear one that a dead session left held"
depth: [advanced]
---

The merge mutex is the lock that lets only one task at a time run the task workflow's end-of-task merge; [Locks]({{< relref "/docs/concepts/locks" >}}) explains what it is for next to the task lock.

## What it serializes

The end-of-task merge is the step where a finished task branch is merged into its output branch (see [Git Worktrees for Isolation]({{< relref "/docs/workflows/parallel-development" >}}#git-worktrees-for-isolation)). That merge runs in the shared repository root, not in the task's worktree, so every task merging at the same time drives one HEAD, one index and one working tree.

Only the task workflow's end-of-task merge takes the mutex. [`/aitask-web-merge`]({{< relref "/docs/skills/aitask-web-merge" >}}) does not take it, and neither does a `git checkout` or `git merge` you run by hand, so neither is held back while a task merges.

There is one mutex per repository, not one per output branch, so two tasks merging into different output branches still wait for each other: they drive the same HEAD, index and working tree.

The mutex is a directory named `merge` on the local machine, not a git branch. It sits in a lock base directory: by default `${TMPDIR:-/tmp}/aitask-locks-<uid>-<checksum of the repository root>/`, so the mutex is that directory's `merge/`; when `AITASKS_LOCK_DIR` is set, the mutex is `$AITASKS_LOCK_DIR/merge`. Task locks, by contrast, travel through git.

Because the default base contains your operating-system user id, the mutex serializes the merges that one user runs in this checkout. Two different users merging in the same checkout get different mutexes and do not wait for each other, unless both set `AITASKS_LOCK_DIR` to the same shared directory, created for them by an administrator.

## What the next task does

A task that reaches its merge finds the mutex in one of these states:

| Who holds it | Outcome |
|---|---|
| No one | Claimed, and the merge proceeds |
| Another task, whose session is still running | Queued. You are told which task you are waiting on, both in the merge-approval prompt and in the progress reported while waiting. If the wait budget runs out the merge is refused, and you choose whether to keep waiting or stop |
| Another task, from a session that is provably gone | Reclaimed, and the merge proceeds |
| Another task, whose liveness cannot be established | Left alone. Clearing it is a deliberate human act, never something the next task does on its own |

The last two rows apply the same rule as the [task lock]({{< relref "/docs/commands/lock" >}}#when-a-pick-meets-a-held-lock), with one difference that matters during recovery: the automatic path displaces only a holder that is provably gone, while the [manual recovery](#recovering-a-stuck-merge-mutex) can also clear one that cannot be verified either way.

## The reservation lasts the whole merge

Taking the mutex, merging and releasing it are three separate short-lived commands, and each one's process exits as soon as it returns, so the reservation is anchored to the **agent session** (the running agent that owns the task), which lasts through all three.

The reservation is held across the whole critical section: through conflict resolution, through the post-merge verification run, and through cleanup. While a merge is parked at a conflict, nothing else can move the tree as a human resolves it, and a verification result belongs to the task that produced it.

Only the holder releases the mutex: every merge that takes it ends by releasing it, and no timeout or background job releases it on the holder's behalf. A session that dies mid-merge therefore leaves it held until the next task finds it provably gone or you [clear it](#recovering-a-stuck-merge-mutex).

## The session anchor

Because the reservation is anchored to the agent session, a merge cannot begin unless that session can be identified. When it cannot, the merge is refused before anything is acquired (`NO_SESSION_ANCHOR`): the merge does not start, and no lock is left behind. There are two ways to supply the anchor:

- **Run inside a tmux pane.** This is the standard route. Each agent is launched as its pane's own process, so the anchor lives and dies exactly with the agent.
- **Set `AIT_AGENT_PID`**, for launchers that start an agent outside tmux. It must name the process that represents and outlives the whole agent session, normally the launcher or session process. A process that merely happens to be alive is not enough.

The framework cannot check that the PID represents the whole session. It checks only that `AIT_AGENT_PID` is an integer greater than 1 naming a process that is alive right now. A value that fails that check is ignored with a warning, and the anchor falls back to the tmux pane. A wrong but live PID is accepted silently and then fails in one of two directions:

- A PID that outlives the session, such as an unrelated long-running process, leaves the holder looking permanently alive. The automatic reclaim never fires, and the manual recovery refuses to break a live holder, so the reservation stays stranded until that process stops.
- A PID that dies early, such as a short-lived child, makes the holder look gone while the merge is still running, so another task can reclaim the tree mid-merge. That is the failure the session anchor exists to prevent.

## Recovering a stuck merge mutex

If a session died mid-merge, the reservation is still held and no other task can merge until it is cleared. [`ait lock`]({{< relref "/docs/commands/lock" >}}) does not manage it, because that command covers task locks only. Use the merge broker directly:

1. **See who holds it.**

   ```bash
   ./.aitask-scripts/aitask_merge_task.sh status
   ```

   It reports the holding task, its anchor process, that process's liveness verdict, the output branch, and when the reservation was taken.

2. **Clear a leaked guard, if `status` reports one.** The guard is a directory a reclaim holds while it runs; one left behind blocks recovery. `status` prints the `rmdir` command that removes it. Run that command only when no reclaim is in progress, and never use `rm -rf`.

3. **Dry-run the release.** With no flags, `force-release` changes nothing:

   ```bash
   ./.aitask-scripts/aitask_merge_task.sh force-release
   ```

   It prints the holder, its liveness, the working-tree residue it found, the remedy that residue requires, and a ready-to-copy armed command pinned to this exact holder.

4. **Run the armed command it printed, verbatim.** It carries a token pinning the holder, so if the holder changed in the meantime the command is refused and someone else's reservation is left alone.

Three rules make `force-release` safe to run:

- **A provably live holder is never broken.** `force-release` refuses it (`REFUSED_LIVE_HOLDER`) and names the process. The only remedy is to let that session finish or to stop it.
- **Each residue state has its own remedy, and a mismatched flag is refused without being attempted.** A merge parked at a conflict (`MERGE_HEAD` present) is cleared with `--abort-merge`. An unmerged index or dirty tree with no `MERGE_HEAD` needs `--reset-hard`, which discards tracked working-tree changes and first prints exactly what it is about to discard. Take the flag from the dry run, never from memory.
- **Failure is reported.** If the tree cannot be brought to a verified-clean state, the lock is kept and the reason is named.

Every run therefore ends with the mutex released or with the reason the tool will not act on it named.

Because the Claude Web merge path does not take this mutex, do not run `/aitask-web-merge` while a task is at its merge step.
