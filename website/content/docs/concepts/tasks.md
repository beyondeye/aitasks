---
title: "Tasks"
linkTitle: "Tasks"
weight: 10
description: "Markdown files with YAML frontmatter — the core unit of work in aitasks."
---

## What it is

A **task** is a single markdown file in `aitasks/` named `t<N>_<short_name>.md` (for example `aitasks/t130_add_login.md`). The file has a YAML frontmatter block — fields like `priority`, `effort`, `depends`, `status`, `labels`, `assigned_to`, `issue_type`, `boardcol` — and a free-form markdown body that describes the work. Tasks persist exactly the same way source code does: as files committed to git. Every CLI command, TUI, and code agent skill operates on those files directly.

## Why it exists

Treating task tracking as a problem that belongs in version control means the full history of every task is visible in `git log`, branches and worktrees can carry their own task state, and a code agent can read, write, and reason about tasks with the same tools it uses for source code. The frontmatter schema is intentionally small enough for an LLM to keep in context, but expressive enough to drive prioritization, dependency resolution, and Kanban-style triage.

## How to use

The complete frontmatter schema and worked examples live in the [Task File Format reference]({{< relref "/docs/development/task-format" >}}).

There are many ways to produce a task — they all just write a file into `aitasks/`. The most common entry points are [`ait create`]({{< relref "/docs/commands/task-management" >}}#ait-create) (typically launched from inside a TUI like [Board]({{< relref "/docs/tuis/board" >}}) or Brainstorm), code-aware capture from [`/aitask-explore`]({{< relref "/docs/skills/aitask-explore" >}}) and [`/aitask-wrap`]({{< relref "/docs/skills/aitask-wrap" >}}), and import flows like [`/aitask-pr-import`]({{< relref "/docs/skills/aitask-pr-import" >}}). The [Capturing ideas]({{< relref "/docs/workflows/capturing-ideas" >}}) and [Create tasks from code]({{< relref "/docs/workflows/create-tasks-from-code" >}}) workflows walk through the recommended patterns.

## See also

- [Plans]({{< relref "/docs/concepts/plans" >}}) — the implementation contract written for an approved task
- [Parent and child tasks]({{< relref "/docs/concepts/parent-child" >}}) — how complex tasks are decomposed
- [Task lifecycle]({{< relref "/docs/concepts/task-lifecycle" >}}) — the statuses a task moves through
- [Locks]({{< relref "/docs/concepts/locks" >}}) — how only one agent works a task at a time
