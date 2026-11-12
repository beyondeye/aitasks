---
title: "Folded tasks"
linkTitle: "Folded tasks"
weight: 40
description: "How related tasks are merged into a single primary task."
depth: [intermediate]
---

## What it is

A **folded task** is a task whose content has been merged into another task, the
*primary* task. Its wording is copied into the primary's description, and the
folded file stays on disk only as a reference until the primary is archived,
when it is deleted. The fields folding writes are in the
[Task File Format reference]({{< relref "/docs/development/task-format" >}}#frontmatter-fields).

## Why it exists

When two or more pending tasks turn out to describe the same work, splitting it
across separate plans wastes context and produces redundant commits. Folding
turns them into one task and keeps each original task's wording inside the
primary's description, so reviewers can see what was merged in.

## How to use

Use [`/aitask-fold`]({{< relref "/docs/skills/aitask-fold" >}}) to merge two or
more existing tasks. Folding can also happen while
[`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}) plans a task: when the
task's description or you ask for other tasks to be folded in, the workflow folds
them before planning continues. Both standalone tasks and child tasks can be folded; a parent task that still has children cannot.

## See also

- [Parent and child tasks]({{< relref "/docs/concepts/parent-child" >}}) — the alternative pattern: split instead of merge
- [Task lifecycle]({{< relref "/docs/concepts/task-lifecycle" >}}) — `Folded` is a terminal status
- [Task consolidation workflow]({{< relref "/docs/workflows/task-consolidation" >}}) — when and why to fold

---

**Next:** [Task notes]({{< relref "/docs/concepts/task-notes" >}})
