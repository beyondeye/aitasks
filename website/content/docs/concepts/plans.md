---
title: "Plans"
linkTitle: "Plans"
weight: 20
description: "The implementation contract written and approved before a task is coded."
depth: [main-concept]
---

## What it is

A **plan** is the step-by-step description of how a task will be done. A coding
agent writes it while it plans the task, and you approve it before any code
changes. The agent writes plans when you run a **skill**, the instructions a
coding agent follows when you type a command, such as
[`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}).

A plan is a markdown file in your repository's `aiplans/` directory, named after
its task: the plan for `aitasks/t130_add_login.md` is
`aiplans/p130_add_login.md`. It gives a summary of the context, the
implementation steps, the files that will change and how to check the result.

## Why it exists

A plan keeps deciding what to do apart from doing it. You approve the approach
once, in plain words, and the agent then has a fixed plan to follow. As it
works, it adds to the plan what it did differently, what you asked it to change
at review, and its final notes.

When a task is finished and archived (moved out of the list of open tasks), its
plan stays as the long-term record of how the task was built. When the task is a child task, the agents that work on its sibling tasks, split from the same parent (see [Parent and child tasks]({{< relref "/docs/concepts/parent-child" >}})), read its plan first, and the [Code Browser]({{< relref "/docs/tuis/codebrowser" >}}), a
terminal app for reading the project's code, shows it beside the code it
explains.

## How to use

Running [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}) or
[`/aitask-explore`]({{< relref "/docs/skills/aitask-explore" >}}) produces a plan;
you do not normally write the file by hand. The file's header and where child
tasks' plans are stored are in the
[Task File Format reference]({{< relref "/docs/development/task-format" >}}#plan-files).

## See also

- [Tasks]({{< relref "/docs/concepts/tasks" >}}) — the work item a plan implements
- [Agent memory]({{< relref "/docs/concepts/agent-memory" >}}) — how archived plans become long-term context
- [Parent and child tasks]({{< relref "/docs/concepts/parent-child" >}}) — sibling plans share archived context
- [Verified scores]({{< relref "/docs/concepts/verified-scores" >}}) — how your rating at the end of a skill run becomes a per-model reliability score

---

**Next:** [Parent and child tasks]({{< relref "/docs/concepts/parent-child" >}})
