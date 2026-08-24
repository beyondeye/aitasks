---
title: "Locks"
linkTitle: "Locks"
weight: 90
description: "How concurrent agents avoid stepping on each other's tasks."
depth: [main-concept]
---

## What it is

aitasks uses two locks, and they exclude different things. The **task lock** answers "who owns this task ID". The **merge mutex** answers a narrower question — which task may run its end-of-task merge right now — because that merge, unlike the rest of a task's work, runs in the shared repository root.

A **task lock** is an atomic claim on a single task ID, recorded on a dedicated `aitask-locks` git branch. When a skill picks a task it acquires the lock — recording the owner email, hostname, timestamp, and the agent session's own process — and only releases it on archival, abort, or explicit unlock. Stale locks can be force-unlocked, optionally with a confirmation prompt.

### What the lock actually excludes

The lock excludes **sessions**, not just people. Running several agent panes against one checkout under a single email is a normal way to use aitasks, so "same user" is not treated as "same worker". A competing `/aitask-pick` on a locked task ID resolves like this:

| Who holds it | Outcome |
|---|---|
| A **different owner** (any host) | Refused — `LOCK_FAILED`, naming the owner |
| **You**, from **this same session** | Refreshed silently — this is what makes resume, re-pick and the ownership guard idempotent |
| **You**, from **another session on this host**, still running | **Refused** — nothing is claimed, and you are asked whether to leave it alone or force-claim |
| **You**, from **another session on this host**, whose liveness cannot be established | **Refused** — "cannot tell" is its own answer, never rounded up to "go ahead" |
| **You**, from a session that is **provably gone** | Claimed, with a [crash-recovery]({{< relref "/docs/workflows/crash-recovery" >}}) prompt |
| **You**, from **another host** | Claimed, with a multi-PC reclaim prompt |
| **You**, via a lock that **never recorded a session process** (a pre-anchor lock, or a claim made outside tmux) | Claimed, with the anomaly prompt — there is no holder to verify |

The two refusals happen *before* the lock, the status change, and the commit, so a refused pick leaves the task exactly as it was. Both are overridable: choose the force option at the prompt, or run `ait lock --unlock <task_id>` in the session that is holding it.

The last row is the boundary of the guarantee: a lock that never named a process cannot be checked, so it stays reclaimable rather than becoming permanently stuck.

## The merge mutex

The **merge mutex** serializes the end-of-task merge — the step where a finished task branch is merged into its output branch. That merge runs in the shared repository root, not in the task's worktree, so every concurrently-merging task drives one HEAD, one index and one working tree.

> **Note:** Only the task workflow's end-of-task merge participates in this mutex. [`/aitask-web-merge`]({{< relref "/docs/skills/aitask-web-merge" >}}) does not, and neither does a `git checkout` or `git merge` you run by hand. The mutex serializes the merges that take it; it does not police the repository.

### What the merge mutex excludes

It is **one global lock per repository**, not one per branch. Two tasks merging into different output branches still drive the same HEAD, the same index and the same working tree, so a per-branch lock would not exclude them.

| Who holds it | Outcome |
|---|---|
| No one | Claimed — the merge proceeds |
| **Another task**, whose session is still running | **Queued** — you are told which task you are waiting on, both in the merge-approval prompt and in the progress reported while waiting. If the wait budget runs out the merge is refused, and you choose whether to keep waiting or stop |
| **Another task**, from a session that is **provably gone** | Reclaimed, and the merge proceeds |
| **Another task**, whose liveness cannot be established | **Left alone** — "cannot tell" is its own answer, never rounded up to "go ahead". Clearing it is a deliberate human act, never something the next task does on its own |

The last two rows apply the same rule as the task lock, with one difference that matters during recovery: the automatic path displaces only a holder that is *provably* gone, while the manual recovery below can also clear one that cannot be verified either way.

### The reservation outlives the command

Taking the mutex, merging, and releasing it are three separate short-lived commands. The reservation is therefore anchored to the **agent session** rather than to the process that took it — anchored to the process, it would evaporate the moment the first command returned.

It is deliberately held across the whole critical section: through conflict resolution, through the post-merge verification run, and through cleanup. That is what makes a conflict-parked merge safe — nothing else can move the tree while a human resolves it — and what makes a verification result attributable to the task that produced it.

The consequence is that **nothing releases this lock automatically**. Every merge that takes it ends by releasing it, and a session that dies mid-merge leaves it held. That is what the recovery ladder below is for.

### Before a merge can start: the session anchor

Because the reservation is anchored to the agent session, a merge cannot begin unless that session can be identified. When it cannot, the merge is refused **before anything is acquired** (`NO_SESSION_ANCHOR`) — the merge does not start, and no lock is left behind. There are two ways to supply the anchor:

- **Run inside a tmux pane.** This is the standard route: each agent is launched as its pane's own process, so the anchor lives and dies exactly with the agent.
- **Set `AIT_AGENT_PID`**, for launchers that start an agent outside tmux. It must name the process that **represents and outlives the whole agent session** — normally the launcher or session process — not merely a process that happens to be alive.

That second requirement is worth stating plainly, because it is not enforced: the framework checks only that `AIT_AGENT_PID` is a positive integer naming a process that exists right now. A wrong-but-live PID is accepted silently, and then fails in one of two directions:

- A PID that **outlives the session** — an unrelated long-running process — leaves the holder looking permanently alive. The automatic reclaim never fires, and the manual recovery below refuses to break a live holder, so the reservation stays stranded until that process stops.
- A PID that **dies early** — a short-lived child — makes the holder look gone while the merge is still running, so another task can reclaim the tree mid-merge. That is precisely the failure the session anchor exists to prevent.

### Recovering a stuck merge mutex

If a session died mid-merge, the reservation is still held and no other task can merge until it is cleared. `ait lock` does not manage it — that command covers task locks only. Use the merge broker directly:

1. **See who holds it.**

   ```bash
   ./.aitask-scripts/aitask_merge_task.sh status
   ```

   It reports the holding task, its anchor process, that process's liveness verdict, the output branch, and when the reservation was taken.

2. **Clear a leaked guard, if `status` reports one.** Remove it with `rmdir`, never `rm -rf`: the guard is a directory whose *emptiness* is the proof that no reclaim is in progress.

3. **Dry-run the release.** With no flags, `force-release` changes nothing:

   ```bash
   ./.aitask-scripts/aitask_merge_task.sh force-release
   ```

   It prints the holder, its liveness, the working-tree residue it found, the remedy that residue requires, and a ready-to-copy armed command pinned to this exact holder.

4. **Run the armed command it printed, verbatim.** It carries a token pinning the holder, so if the holder changed in the meantime the command is refused rather than silently overriding someone else's reservation.

Three properties make this ladder terminate rather than loop:

- **A provably live holder is never broken.** `force-release` refuses it (`REFUSED_LIVE_HOLDER`) and names the process. The remedy is to let that session finish or to stop it — not to force harder.
- **The two residue states have two distinct remedies, and a mismatched flag is refused rather than attempted.** A merge parked at a conflict (`MERGE_HEAD` present) is cleared with `--abort-merge`. An unmerged index or dirty tree with *no* `MERGE_HEAD` needs `--reset-hard`, which **discards tracked working-tree changes** and prints exactly what it is about to discard first. Take the flag from the dry run, never from memory.
- **Failure is reported, not silent.** If the tree cannot be brought to a verified-clean state the lock is deliberately **kept** and the reason is named. Either the mutex is released, or the tool tells you precisely why it will not act on it.

Because the Claude Web merge path does not take this mutex, do not run `/aitask-web-merge` while a task is at its merge step.

## Why it exists

aitasks is designed to be used by multiple PCs, multiple developers, and multiple parallel agent sessions against the same shared repository. Without locks, two sessions could pick the same task at the same time and produce conflicting branches, commits, or archival records — and because parallel sessions usually share one email, matching on owner alone would not have caught it. Routing the lock through git rather than a backend service keeps the framework backend-free: the same `git push` / `git fetch` plumbing that distributes tasks also distributes the lock state, and force-unlock is just another commit.

The merge mutex exists because the end-of-task merge is the one mutating step that runs in the shared repository root rather than in the task's own worktree. Worktree isolation keeps concurrent tasks out of each other's files right up to that point and then stops applying: two tasks merging at the same time race on one index, and a merge parked at a conflict can have its half-resolved work absorbed into the next task's merge commit. Serializing the merge is what carries the isolation across that last step.

## How to use

Locks are normally invisible — `/aitask-pick` and the board TUI acquire and release them automatically. The [`ait lock`]({{< relref "/docs/commands/lock" >}}) command exposes the underlying operations: list current locks, check a specific task, force-release a stale lock, and clean up stuck locks.

The merge mutex is likewise invisible in normal use: the task workflow takes it before the merge and releases it after cleanup. It is *not* covered by `ait lock`. Inspect it, and clear it when a session died holding it, with `./.aitask-scripts/aitask_merge_task.sh status` and `force-release` — see [Recovering a stuck merge mutex](#recovering-a-stuck-merge-mutex).

## See also

- [Tasks]({{< relref "/docs/concepts/tasks" >}}) — the unit a lock applies to
- [Git branching model]({{< relref "/docs/concepts/git-branching-model" >}}) — the `aitask-locks` branch
- [`ait lock`]({{< relref "/docs/commands/lock" >}}) — the CLI for inspecting and managing locks
- [Workflows: Crash Recovery]({{< relref "/docs/workflows/crash-recovery" >}}) — reclaim a task whose prior agent crashed mid-implementation
- [Workflows: Parallel development]({{< relref "/docs/workflows/parallel-development" >}}) — how both locks fit into running several tasks at once

---

**Next:** [Task lifecycle]({{< relref "/docs/concepts/task-lifecycle" >}})
