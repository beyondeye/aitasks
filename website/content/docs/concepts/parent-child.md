---
title: "Parent and child tasks"
linkTitle: "Parent and child tasks"
weight: 30
description: "How a complex task is decomposed into siblings that share planning context."
depth: [main-concept]
---

## What it is

A **parent task** is a regular task whose work has been split into smaller **child tasks**. Each child is a task file of its own, kept in a folder named after the parent's number: the children of `aitasks/t130_add_login.md` are files such as `aitasks/t130/t130_1_add_login_form.md`. The parent keeps track of which children still need work. By default each child depends on the one before it, so the children are done in number order, and when the last child is archived (moved out of the list of open tasks) the parent is archived too.

## Why it exists

Many real tasks are too large for one conversation with a coding agent: the conversation fills up with detail, the plan drifts, and the review gets too big to follow. Splitting the work lets the agent that plans the parent describe the whole problem once, then hand each child to a fresh conversation that gets only the background it needs. When a child is archived, its **plan**, the step-by-step description of the work that the agent wrote and you approved before coding (see [Plans]({{< relref "/docs/concepts/plans" >}})), becomes the first thing the agents working on the next children read, so they inherit the problems, patterns and decisions found earlier instead of working them out again.

## How to use

When you pick a large task with `/aitask-pick`, the agent can offer to split it into children while it plans; you can also ask for a split in the task's description. The [Task decomposition workflow]({{< relref "/docs/workflows/task-decomposition" >}}) walks through it. You start work on a child the same way as on any other task, by typing `/aitask-pick 130_2` (the parent's number, then the child's) into your coding agent. In the [board]({{< relref "/docs/tuis/board" >}}), the task board that `ait board` opens in your terminal, a parent's card shows how many children it has, and opening it lets you pick a specific child. The file and field rules are in the [Task File Format reference]({{< relref "/docs/development/task-format" >}}#parent-child-hierarchies).

## See also

- [Tasks]({{< relref "/docs/concepts/tasks" >}}) — the underlying file format
- [Plans]({{< relref "/docs/concepts/plans" >}}) — sibling plans become primary context
- [Folded tasks]({{< relref "/docs/concepts/folded-tasks" >}}) — the alternative pattern: merge instead of split
- [Agent memory]({{< relref "/docs/concepts/agent-memory" >}}) — how sibling context propagates

---

**Next:** [Topic anchoring]({{< relref "/docs/concepts/topic-anchoring" >}})
