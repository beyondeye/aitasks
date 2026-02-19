---
title: "Parallel Development"
linkTitle: "Parallel Development"
weight: 40
description: "Working on multiple tasks simultaneously with concurrency safety"
---

The aitasks framework supports multiple developers (or multiple AI agent instances) working on different tasks simultaneously.

## How Concurrency Is Managed

- **Status tracking via git:** When [`/aitask-pick`](../../skills/aitask-pick/) starts work on a task, it sets the status to "Implementing", records the developer's email in `assigned_to`, and commits + pushes the change. This makes the assignment visible to anyone who pulls the latest state
- **Atomic task locking:** The atomic lock system prevents two PCs from picking the same task simultaneously. Locks are stored on a separate `aitask-locks` git branch using compare-and-swap semantics
- **Atomic ID counter:** The atomic ID counter on the `aitask-ids` branch ensures globally unique task numbers even when multiple PCs create tasks against the same repo

## Git Worktrees for Isolation

When working on multiple tasks in parallel, use the git worktree option in [`/aitask-pick`](../../skills/aitask-pick/). This creates an isolated working directory at `aiwork/<task_name>/` on a separate branch, so each task's changes don't interfere with each other. After implementation, the branch is merged back to main and the worktree is cleaned up.

## Best Practices

- Run `git pull` before starting `/aitask-pick` to see the latest task status and assignments
- Use git worktrees when multiple developers work in parallel, or when running multiple Claude Code instances on tasks that touch overlapping files
- Working on the current branch (without worktrees) is safe when you are a single developer giving work to multiple Claude Code instances on tasks that don't touch the same files

## Parallel Exploration

`/aitask-explore` is read-only — it searches and reads code but never modifies source files. This makes it safe to run in a separate terminal tab while another Claude Code instance implements a task. Use this pattern to stay productive: explore and create new tasks while waiting for builds, tests, or ongoing implementations to complete.
