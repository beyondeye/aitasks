---
title: "Parallel Development"
linkTitle: "Parallel Development"
weight: 40
description: "Working on multiple tasks simultaneously with concurrency safety"
depth: [advanced]
---

The aitasks framework supports multiple developers (or multiple AI agent instances) working on different tasks simultaneously.

## How Concurrency Is Managed

- **Status tracking via git:** When [`/aitask-pick`](../../skills/aitask-pick/) starts work on a task, it sets the status to "Implementing", records the developer's email in `assigned_to`, and commits + pushes the change. This makes the assignment visible to anyone who pulls the latest state
- **Atomic task locking:** The atomic lock system prevents two PCs from picking the same task simultaneously. Locks are stored on a separate `aitask-locks` git branch using compare-and-swap semantics
- **Atomic ID counter:** The atomic ID counter on the `aitask-ids` branch ensures globally unique task numbers even when multiple PCs create tasks against the same repo
- **Task data branch (optional):** When enabled, task/plan files live on a separate `aitask-data` branch accessed via a worktree at `.aitask-data/`. This keeps task management commits off the main branch and allows independent sync via `./ait git push`/`./ait git pull`

## Git Worktrees for Isolation

When working on multiple tasks in parallel, use the git worktree option in [`/aitask-pick`](../../skills/aitask-pick/). The worktree is an isolated working directory at `aiwork/<task_name>/` on a separate branch, so each task's changes don't interfere with each other. It is created once the plan is approved and the remote drift check has passed — not when the branch is chosen — so the branch is cut from an up-to-date base. After implementation, the branch is merged back into the profile's `output_branch`, which defaults to the base branch the worktree was cut from, and the worktree is cleaned up.

`aiwork/` is gitignored, so a worktree never shows up as untracked state in the main checkout — which matters when a broad `git add` runs in another session. On projects that keep task data on a separate branch, the worktree is also given the same `aitasks/` and `aiplans/` links as the main checkout, so `ait` commands and the test suite behave identically inside it.

## Serialized Merge-Back

Worktrees keep concurrent tasks out of each other's files, but the merge back is different: it runs in the shared repository root, not in the worktree, so every task reaching it drives the same HEAD, index and working tree. That step is therefore **serialized** — one task merges at a time.

What this means in practice:

- **A queued agent is told what it is waiting on.** The merge-approval prompt names the task currently holding the merge, so a queue looks like a queue rather than a hang.
- **A conflict-parked merge keeps the shared tree reserved** until the human resolving it is done. Without that, the next task's merge would absorb the half-resolved conflict work into its own merge commit.
- **The reservation is held through post-merge verification and cleanup**, so a build or test result belongs to the task that produced it rather than to whatever else landed in the meantime.
- **A session that dies mid-merge leaves the reservation held.** It is cleared deliberately, not automatically — see [Recovering a stuck merge mutex]({{< relref "/docs/concepts/locks#recovering-a-stuck-merge-mutex" >}}).

Under `create_worktree: false` none of this applies: there is no task branch, the merge step does not run at all, and shared-checkout mode is unaffected.

For what the mutex does and does not cover, see [Concepts: The merge mutex]({{< relref "/docs/concepts/locks#the-merge-mutex" >}}).

## Best Practices

- Run `git pull` before starting `/aitask-pick` to see the latest task status and assignments
- Use git worktrees when multiple developers work in parallel, or when running multiple code agent sessions on tasks that touch overlapping files
- Working on the current branch (without worktrees) is safe when you are a single developer giving work to multiple code agent sessions on tasks that don't touch the same files

## Parallel Planning

Complex tasks that need [child decomposition](../task-decomposition/) can have their planning and decomposition phase run in parallel with any other work. Since only task and plan files are created — no source code is touched — there's zero risk of conflicts. See [Parallel Task Planning](../parallel-planning/) for the full workflow.

## Parallel Exploration

`/aitask-explore` is read-only — it searches and reads code but never modifies source files. This makes it safe to run in a separate terminal tab while another agent session implements a task. Use this pattern to stay productive: explore and create new tasks while waiting for builds, tests, or ongoing implementations to complete.

**See also:** [Concepts: Git branching model]({{< relref "/docs/concepts/git-branching-model" >}}), [Concepts: Locks]({{< relref "/docs/concepts/locks" >}})
