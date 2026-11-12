---
title: "Capturing Ideas Fast"
linkTitle: "Capturing Ideas"
weight: 10
description: "Quickly capture task ideas without breaking your flow"
depth: [intermediate]
---

When a new task idea comes to mind, capture it before the thought fades. The [`ait create`]({{< relref "/docs/commands/task-management#ait-create" >}}) command is built for this: you can write a task description as a raw stream of consciousness without worrying about structure, grammar, or completeness.

In interactive mode, `ait create` walks you through metadata selection (priority, effort, labels) in fzf menus, lists you filter by typing a few letters and pick from with the arrow keys, then lets you enter the description as one or more blocks of text. There is no need to open an external editor or write a polished specification: the planning workflow turns rough, unstructured descriptions into implementation plans when the task is picked.

A useful setup is a terminal tab with `ait create` ready to launch at all times. When an idea strikes, even mid-implementation on another task, switch to that tab, type the idea, assign basic metadata, and get back to work. You can save the task as a local draft that is not committed (no network needed) and finalize it later.

From there, a task is refined in three stages:

1. **Capture.** Create the task with [`ait create`]({{< relref "/docs/commands/task-management#ait-create" >}}) or [`/aitask-create`]({{< relref "/docs/skills/aitask-create" >}}), or use [`/aitask-explore`]({{< relref "/docs/skills/aitask-explore" >}}) to explore the codebase first and create a task from your findings. Write whatever comes to mind, even multiple paragraphs of loosely connected ideas
2. **Organize.** Use [`ait board`]({{< relref "/docs/commands/board-stats#ait-board" >}}) to triage: move tasks between kanban columns, adjust priority and effort, add labels. See the [Board documentation]({{< relref "/docs/tuis/board" >}}) for detailed how-to guides
3. **Refine.** When the task is picked for implementation with [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}), the planning phase explores the codebase and produces a structured implementation plan from your raw intent

---

**Next:** [Retroactive Tracking]({{< relref "/docs/workflows/retroactive-tracking" >}}): wrap ad-hoc changes into the aitasks framework after the fact.
