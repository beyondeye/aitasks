---
title: "Parent and child tasks"
linkTitle: "Parent and child tasks"
weight: 30
description: "How a complex task is decomposed into siblings that share planning context."
depth: [main-concept]
---

## What it is

A **parent task** is a regular task whose work has been split into smaller **child tasks**. The parent file lives at the usual location (`aitasks/t<N>_<name>.md`); its children live in a sibling subdirectory `aitasks/t<N>/` named `t<N>_<M>_<name>.md` — for example `aitasks/t130/t130_1_add_login_form.md`. The parent's `children_to_implement` frontmatter field lists the child IDs that still need work. Children automatically depend on each other in order, and when the last child is archived the parent is archived too.

## Why it exists

Many real-world tasks are too large for a single agent session — context gets cluttered, plans drift, and review becomes unwieldy. Decomposition lets the planning agent capture the whole problem once, then hand each child off to a fresh context with only the relevant slice of background. Archived child plans flow back as primary context for subsequent siblings, so later children inherit the gotchas, patterns, and decisions established earlier — without re-deriving them.

## How to use

The [Task decomposition workflow]({{< relref "/docs/workflows/task-decomposition" >}}) walks through creating a parent with children. Picking a child task is the same as picking a regular task — `/aitask-pick 130_2`. The board TUI shows parents with pending children as **Has children**, and drilling in lets you pick a specific child.

## See also

- [Tasks]({{< relref "/docs/concepts/tasks" >}}) — the underlying file format
- [Plans]({{< relref "/docs/concepts/plans" >}}) — sibling plans become primary context
- [Folded tasks]({{< relref "/docs/concepts/folded-tasks" >}}) — the alternative pattern: merge instead of split
- [Agent memory]({{< relref "/docs/concepts/agent-memory" >}}) — how sibling context propagates

---

**Next:** [Folded tasks]({{< relref "/docs/concepts/folded-tasks" >}})
