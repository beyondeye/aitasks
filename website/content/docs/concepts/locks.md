---
title: "Locks"
linkTitle: "Locks"
weight: 90
description: "How concurrent agents avoid stepping on each other's tasks."
depth: [main-concept]
---

## What it is

aitasks lets several coding agents work in one git repository at the same time,
on one machine or on several. Each agent works on a **task**, a markdown file in
the repository that describes one piece of work. A lock marks something as in
use by one agent, so other agents leave it alone. There are two:

- When an agent starts work on a task, aitasks takes a **task lock** on it, so
  no other agent can take the same task.
- When a task that has its own branch is finished, that branch is merged back into the branch the work started from. A second lock, the **merge mutex**, lets only one finished task
  at a time do that merge.

aitasks takes and releases both locks on its own. You do not need to do anything
with them; [`ait lock`]({{< relref "/docs/commands/lock" >}}) shows the task
locks when you want to look, or when a task seems stuck.

## Why it exists

Without the task lock, two agents could start the same task at once and produce
conflicting branches, commits and archive records. Each task lock belongs to one **agent
session**, a single running coding agent in its own terminal, so several agents
in one checkout under the same email still exclude each other. Task locks are kept in git, so the same push and fetch that share tasks between machines also share them, with no server to run.

While it is being worked on, a task can have its own **worktree**, a separate
working folder on its own branch, so agents running at the same time never edit
each other's files. The final merge runs in the main copy of the repository,
which every agent shares. Two merges at once would mix their changes in that one
copy. The merge mutex keeps that last step to one
task at a time.

## How to use

You start work on a task with `/aitask-pick`, a skill (a command you type into
your coding agent), or from the board, the task board that `ait board` opens in
your terminal; either one takes the task lock. The agent releases it when the
task is finished and archived (moved out of the list of open tasks), when the
task is given up, or when you release it yourself with `ait lock`. The merge mutex is taken
just before a finished task merges and released once the merge and its checks
are done.

An agent that crashes leaves its locks behind.
[Crash recovery]({{< relref "/docs/workflows/crash-recovery" >}}) shows how the next
agent takes over a task lock, and
[Merge mutex]({{< relref "/docs/development/merge-mutex" >}}#recovering-a-stuck-merge-mutex)
shows how to clear a stuck merge mutex.

## See also

- [Tasks]({{< relref "/docs/concepts/tasks" >}}) — the unit a task lock applies to
- [Git branching model]({{< relref "/docs/concepts/git-branching-model" >}}) — the branch the task locks live on
- [`ait lock`]({{< relref "/docs/commands/lock" >}}) — inspect and manage task locks, what a lock records, and what happens when a pick meets a held lock
- [Merge mutex]({{< relref "/docs/development/merge-mutex" >}}) — what the merge mutex serializes, queueing, the session anchor, and recovering a stuck one
- [`ait note`]({{< relref "/docs/commands/note" >}}) — sends a note to a task, and to the agent working on it
- [Workflows: Crash Recovery]({{< relref "/docs/workflows/crash-recovery" >}}) — reclaim a task whose prior agent crashed mid-implementation
- [Workflows: Parallel development]({{< relref "/docs/workflows/parallel-development" >}}) — how both locks fit into running several tasks at once

---

**Next:** [Shadow agent]({{< relref "/docs/concepts/shadow-agent" >}})
