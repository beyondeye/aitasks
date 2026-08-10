---
title: "Locks"
linkTitle: "Locks"
weight: 90
description: "How concurrent agents avoid stepping on each other's tasks."
depth: [main-concept]
---

## What it is

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

## Why it exists

aitasks is designed to be used by multiple PCs, multiple developers, and multiple parallel agent sessions against the same shared repository. Without locks, two sessions could pick the same task at the same time and produce conflicting branches, commits, or archival records — and because parallel sessions usually share one email, matching on owner alone would not have caught it. Routing the lock through git rather than a backend service keeps the framework backend-free: the same `git push` / `git fetch` plumbing that distributes tasks also distributes the lock state, and force-unlock is just another commit.

## How to use

Locks are normally invisible — `/aitask-pick` and the board TUI acquire and release them automatically. The [`ait lock`]({{< relref "/docs/commands/lock" >}}) command exposes the underlying operations: list current locks, check a specific task, force-release a stale lock, and clean up stuck locks.

## See also

- [Tasks]({{< relref "/docs/concepts/tasks" >}}) — the unit a lock applies to
- [Git branching model]({{< relref "/docs/concepts/git-branching-model" >}}) — the `aitask-locks` branch
- [`ait lock`]({{< relref "/docs/commands/lock" >}}) — the CLI for inspecting and managing locks
- [Workflows: Crash Recovery]({{< relref "/docs/workflows/crash-recovery" >}}) — reclaim a task whose prior agent crashed mid-implementation

---

**Next:** [Task lifecycle]({{< relref "/docs/concepts/task-lifecycle" >}})
