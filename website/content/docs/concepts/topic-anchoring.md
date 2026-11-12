---
title: "Topic anchoring"
linkTitle: "Topic anchoring"
weight: 35
description: "How loose follow-up work is grouped around a shared task topic without forcing a parent-child tree."
depth: [main-concept]
---

## What it is

A **task** in aitasks is a markdown file that describes one piece of work,
kept in your repository and committed to git. A **topic** is a group of loosely
related tasks about one subject. The subject is named after one of them, the
**topic root**: usually the task the others came from, such as a feature whose
work turned up a few smaller fixes. Other tasks join the topic by recording
the root's task number in a field called its **anchor**; a child task is in its
parent's topic without one. That number is how aitasks keeps the group
together.

A topic does not tie its tasks together in any other way. Each one is still
planned, picked up, implemented and archived on its own. Archiving moves a
finished task out of the active task list, and an archived task stays a valid
topic root, so a topic can keep collecting new tasks after its root is done.

## Why it exists

Work on one task often turns up more: a follow-up fix, a related cleanup, an
idea for later. Those tasks belong near the task they came from when you sort
and review your backlog, but they are not steps of it and do not have to wait
for it. Without a topic they scatter across your task list, and the link back
to their origin lives only in your memory.

aitasks has other ways to relate tasks, and you pick by what the tasks need:

- Use a topic when tasks should sit near each other for sorting and review but
  can each be done independently.
- Use **child tasks** when one larger task is split into ordered parts that are
  finished as a set; a child task is one of those parts, and its parent is
  done when all of them are. A parent and its children share one topic.
- Use a **dependency** when a task cannot start until another one is done.
- Use a **label**, a tag such as `ui` or `docs`, to filter across many
  unrelated subjects.

These combine: a follow-up can belong to a feature's topic and also depend on
a bug fix that must land first.

## How to use

Most tasks join a topic without your help. A follow-up task that aitasks
itself creates from another task joins that task's topic, and a child task
joins its parent's topic.

To put a new task in a topic yourself, create it with `ait create` in batch mode and give it either the root's task number or the task it follows up; for a follow-up it finds the root for you. `ait update` moves an existing task to another topic or makes it a
root of its own. You can also edit the anchor on the task detail screen of the board, the terminal view that `ait board` opens, which shows your tasks as cards in columns.

To see your topics, press `y` in the board for the By-Topic view. Each
topic with at least two tasks gets its own column, headed by its root task,
and the tasks that are alone in their topic share one last column.

## See also

- [Tasks]({{< relref "/docs/concepts/tasks" >}}) — the base task file model
- [Parent and child tasks]({{< relref "/docs/concepts/parent-child" >}}) — the stricter decomposition relationship
- [Task Management]({{< relref "/docs/commands/task-management" >}}#ait-create) — the `ait create` and `ait update` options that set an anchor
- [Task File Format]({{< relref "/docs/development/task-format" >}}#topic-anchoring) — how the anchor is stored, inherited by children and cleared
- [Board reference]({{< relref "/docs/tuis/board/reference" >}}#base-filters-radio) — how the By-Topic view builds and labels its columns
- [Implementation Trails]({{< relref "/docs/workflows/implementation-trails" >}}) — recommended landing order across tasks, projected separately from topics
- [Implementation trails (concept)]({{< relref "/docs/concepts/implementation-trails" >}}) — what a trail is and why it is kept

---

**Next:** [Folded tasks]({{< relref "/docs/concepts/folded-tasks" >}})
