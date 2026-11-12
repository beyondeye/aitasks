---
title: "Parallel Development"
linkTitle: "Parallel Development"
weight: 40
description: "Working on multiple tasks simultaneously with concurrency safety"
depth: [intermediate]
---

Several developers, or several code agents, can work on different tasks of the same repository at the same time. aitasks keeps them from taking the same task, from colliding on task numbers and, with worktrees, from editing each other's files.

## How Concurrency Is Managed

- Task status is shared through git. When [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}) starts work on a task, it sets the task to `Implementing`, records your email in `assigned_to`, and commits and pushes the change, so anyone who syncs sees who is working on what.
- A task lock stops two agents taking the same task, even from different machines. See [Concepts: Locks]({{< relref "/docs/concepts/locks" >}}); how the lock is stored is on [`ait lock`]({{< relref "/docs/commands/lock" >}}#how-it-works).
- Task numbers come from a shared counter in the repository (on its own [branch]({{< relref "/docs/concepts/git-branching-model" >}})), so tasks created on different machines never get the same number.
- Task and plan files can live on their own branch, synced with `./ait git push` and `./ait git pull`, so task bookkeeping stays out of your code history. See [Concepts: Git branching model]({{< relref "/docs/concepts/git-branching-model" >}}).

When you run many agents at once, you also collect agents that have finished. Rather than killing one and losing its summary, [freeze it]({{< relref "/docs/workflows/freeze-and-restore-agents" >}}): the process ends, its output stays readable in its own pane, and the agent can be restored, or its task picked again, later.

## Git Worktrees for Isolation

To keep parallel tasks out of each other's files, choose the worktree option in [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}) (the `create_worktree` profile key). The task then gets its own working directory at `aiwork/<task_name>/` on a separate branch. The worktree is created after the plan is approved and the remote drift check has passed, so the branch is cut from an up-to-date base. After implementation, the branch is merged into the profile's `output_branch`, which defaults to the base branch the worktree was cut from, and the worktree is removed.

`aiwork/` is in `.gitignore`, so a worktree never shows up as untracked files in the main checkout, where a broad `git add` in another session would pick it up. When task data lives on its own branch, the worktree gets the same `aitasks/` and `aiplans/` links as the main checkout, so `ait` commands behave the same inside it.

## Serialized Merge-Back

Worktrees keep concurrent tasks out of each other's files, but the merge back runs in the shared repository root, not in the worktree, so every task that reaches it uses the same HEAD, index and working tree. The merge mutex serializes that step: one task merges at a time.

In practice:

- A queued agent is told what it is waiting for. The merge-approval prompt names the task currently holding the merge mutex, so you can tell a waiting agent from a stuck one.
- A merge stopped on a conflict keeps the merge mutex held until the person resolving it is done. Otherwise the next task's merge would take the half-resolved conflict into its own merge commit.
- The merge mutex is held through post-merge verification and cleanup, so a build or test result belongs to the task that produced it, not to whatever else landed in the meantime.
- A session that dies mid-merge leaves the merge mutex held. It stays held until the next task finds that session provably gone, or until you clear it; see [Recovering a stuck merge mutex]({{< relref "/docs/development/merge-mutex" >}}#recovering-a-stuck-merge-mutex).

With `create_worktree: false` none of this applies: there is no task branch, no merge step runs, and work in the shared checkout is not held back.

For what the merge mutex covers and what it does not, see [Merge mutex]({{< relref "/docs/development/merge-mutex" >}}).

## Choosing What to Run Alongside

A worktree does not tell you which task is sensible to start now. Two tools help:

- The [parallel-admission preflight]({{< relref "/docs/skills/aitask-pick/parallel-admission" >}}) of `/aitask-pick` checks the task you picked against the files that work already in flight touches. It runs before implementation when the `parallel_admission` profile key enables it. All three shipped profiles set that key to `"off"`; a profile that leaves the key out gets `warn`, which runs the preflight. A separate key, `parallel_assessment`, adds a check before the task is claimed, based on what the in-flight tasks' descriptions say they touch. It is off unless a profile sets it to `show` or `ask`.
- [`/aitask-backlog-roadmap`]({{< relref "/docs/skills/aitask-backlog-roadmap" >}}) ranks the background-work backlog into lanes that are safe to run in parallel and lanes that need coordinating, so you can choose before you pick a task at all.

Neither reserves anything. Both look at the state at the moment they run, and overlapping work can start right after either one passes. Read a clear result as "no known conflict when checked", never as a promise that a file will still be free when you reach it.

## Best Practices

- `/aitask-pick` syncs task data with the remote before it lists tasks, so you see current statuses and assignments. Pull your code branch yourself before you start, as usual.
- Use worktrees when several developers work in parallel, or when several agent sessions work on tasks that touch the same files.
- Working on the current branch without worktrees is fine when you alone hand tasks to several agent sessions and the tasks do not touch the same files.

## Parallel Planning

Planning and decomposing a complex task writes only task and plan files and changes no source code, so it can run alongside any other work. See [Parallel Task Planning]({{< relref "/docs/workflows/parallel-planning" >}}).

## Parallel Exploration

`/aitask-explore` reads and searches code but never changes source files, so you can run it in another terminal while an agent implements a task, and create new tasks from what you find while builds, tests or implementations run.

**See also:** [Concepts: Git branching model]({{< relref "/docs/concepts/git-branching-model" >}}), [Concepts: Locks]({{< relref "/docs/concepts/locks" >}})
