---
title: "Locks"
linkTitle: "Locks"
weight: 90
description: "How concurrent agents avoid stepping on each other's tasks."
depth: [main-concept]
---

## What it is

A **task lock** is an atomic claim on a single task ID, recorded on a dedicated `aitask-locks` git branch. When a skill picks a task it acquires the lock — recording the owner email, hostname, and timestamp — and only releases it on archival, abort, or explicit unlock. While a lock is held, other PCs and agents see the task as unavailable: a competing `/aitask-pick` that targets the same ID will fail with a structured `LOCK_FAILED` outcome that includes the current owner. Stale locks (held by a hostname/agent no longer working the task) can be force-unlocked, optionally with a confirmation prompt.

## Why it exists

aitasks is designed to be used by multiple PCs, multiple developers, and multiple parallel agent sessions against the same shared repository. Without locks, two sessions could pick the same task at the same time and produce conflicting branches, commits, or archival records. Routing the lock through git rather than a backend service keeps the framework backend-free: the same `git push` / `git fetch` plumbing that distributes tasks also distributes the lock state, and force-unlock is just another commit.

## How to use

Locks are normally invisible — `/aitask-pick` and the board TUI acquire and release them automatically. The [`ait lock`]({{< relref "/docs/commands/lock" >}}) command exposes the underlying operations: list current locks, check a specific task, force-release a stale lock, and clean up stuck locks.

## See also

- [Tasks]({{< relref "/docs/concepts/tasks" >}}) — the unit a lock applies to
- [Git branching model]({{< relref "/docs/concepts/git-branching-model" >}}) — the `aitask-locks` branch
- [`ait lock`]({{< relref "/docs/commands/lock" >}}) — the CLI for inspecting and managing locks

---

**Next:** [Task lifecycle]({{< relref "/docs/concepts/task-lifecycle" >}})
