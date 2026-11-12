---
title: "Tasks"
linkTitle: "Tasks"
weight: 10
description: "Markdown files with YAML frontmatter — the core unit of work in aitasks."
depth: [main-concept]
---

## What it is

A **task** is one piece of work, written down as a markdown file in your
repository's `aitasks/` directory, for example `aitasks/t130_add_login.md`. The
top of the file holds its **frontmatter**: a block of `name: value` lines in
YAML, between two `---` lines, that records facts about the task such as its
priority, its status and the tasks it waits for. Below the frontmatter, ordinary
markdown describes the work.

Tasks are committed to git like source code. Every part of aitasks reads and
writes these files directly: the `ait` command line, its full-screen terminal
apps (TUIs) such as the board, and the **skills**, the instructions a coding
agent such as Claude Code follows when you type a command like `/aitask-pick`.

## Why it exists

Keeping tasks in git means every change to a task is in its git history, and
a coding agent can read
and edit tasks with the same tools it uses for code. The frontmatter is small
enough for an agent to keep in mind, and still enough to sort tasks by priority,
order them by what they wait for, and lay them out as cards in the columns of a
board.

## How to use

The usual way to make a task is
[`ait create`]({{< relref "/docs/commands/task-management" >}}#ait-create),
typically started from the [board]({{< relref "/docs/tuis/board" >}}). A coding agent can also write tasks for you:
[`/aitask-explore`]({{< relref "/docs/skills/aitask-explore" >}}) and
[`/aitask-wrap`]({{< relref "/docs/skills/aitask-wrap" >}}) create them from the
code you are working on, and
[`/aitask-pr-import`]({{< relref "/docs/skills/aitask-pr-import" >}}) turns a pull
request into one. All of them just write a file into `aitasks/`. The
[Capturing ideas]({{< relref "/docs/workflows/capturing-ideas" >}}) and
[Create tasks from code]({{< relref "/docs/workflows/create-tasks-from-code" >}})
workflows walk through the common ways.

Every frontmatter field, including the ones the workflow writes for itself, is
listed in the [Task File Format reference]({{< relref "/docs/development/task-format" >}}).

## See also

- [Plans]({{< relref "/docs/concepts/plans" >}}) — the implementation contract written for an approved task
- [Parent and child tasks]({{< relref "/docs/concepts/parent-child" >}}) — how complex tasks are decomposed
- [Task lifecycle]({{< relref "/docs/concepts/task-lifecycle" >}}) — the statuses a task moves through
- [Locks]({{< relref "/docs/concepts/locks" >}}) — how only one agent works a task at a time

---

**Next:** [Plans]({{< relref "/docs/concepts/plans" >}})
