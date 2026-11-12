---
title: "Complex Task Decomposition"
linkTitle: "Task Decomposition"
weight: 20
description: "Breaking complex tasks into manageable child subtasks"
depth: [intermediate]
---

For tasks that are too large or risky for a single implementation run, the aitasks framework supports decomposition into child subtasks. Each child is implemented in its own run, and later children receive the context of the ones finished before them.

Two other skills cover nearby jobs. [`/aitask-explore`]({{< relref "/docs/skills/aitask-explore" >}}) creates tasks (often several) from codebase exploration, which helps when you need to find the shape of the work before decomposing it. [`/aitask-fold`]({{< relref "/docs/skills/aitask-fold" >}}) goes the other way and merges overlapping tasks into one (see [Task Consolidation]({{< relref "/docs/workflows/task-consolidation" >}})).

## How It Works

- During the planning phase of [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}), if a task is assessed as high complexity, the skill automatically offers to break it into child subtasks
- You can also ask for decomposition in the task description, with a line like "this is a complex task: please decompose in child tasks". The agent reads the description while it plans and takes the request into account
- Each child task is created with detailed context: key files to modify, reference patterns, step-by-step implementation instructions, and verification steps, so each child can be implemented on its own in a fresh code agent context

## Context Propagation Between Siblings

When implementing a child task, [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}) automatically gathers context from previously completed siblings. The primary reference is the archived plans of the finished siblings, which contain the full implementation record, including a "Final Implementation Notes" section with the patterns established, gotchas discovered, and shared code created.

## Typical Decomposition Flow

1. Create a parent task describing the full feature
2. Run `/aitask-pick <parent_number>` and choose to decompose during planning
3. Define child tasks with descriptions and dependencies
4. Implement children one at a time with `/aitask-pick <parent>_<child>` (e.g., `/aitask-pick 16_1`, `/aitask-pick 16_2`)
5. When all children are complete, the parent is automatically archived

**See also:** [Concepts: Parent and child tasks]({{< relref "/docs/concepts/parent-child" >}})

---

**Next:** [Task Consolidation]({{< relref "/docs/workflows/task-consolidation" >}}): merging overlapping or duplicate tasks into a single actionable task.
