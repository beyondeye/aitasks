---
title: "Parallel Task Planning"
linkTitle: "Parallel Planning"
weight: 45
description: "Front-load complex task design work while other implementations run in parallel"
depth: [intermediate]
---

When a feature is complex enough to need [child task decomposition]({{< relref "/docs/workflows/task-decomposition" >}}), you can run only its planning and decomposition, without writing any code. The result is a set of child tasks, each with an implementation plan, and you can produce it while other work is running.

## Why this is safe

Planning changes no source code: it writes only task files and plan files, so it cannot conflict with an implementation running in another terminal or on another machine.

A plan is checked again when its child is picked for implementation, so it can wait. How it is checked depends on the [execution profile]({{< relref "/docs/skills/aitask-pick/execution-profiles" >}}). The `fast` profile verifies a plan against the current code when it has never been verified, and asks you when its last verification is more than 24 hours old. The default profile asks whether to use the plan, verify it or write a new one. With the shipped profiles, the workflow also tells you before implementation starts when the branch you are building on has moved on the remote.

## When to use it

- A complex feature waiting its turn. The task needs decomposition, but implementation is queued behind other work, so you do the design while you wait.
- Preparing parallel work. A decomposition often produces children that do not depend on each other. With their plans written, you can hand several of them to separate agents at once.
- Design sessions. You want to iterate on child scopes, dependencies and splits with the agent before committing to any implementation.

## Steps

1. Create the parent task. Describe the full scope of the feature, and end the description with a line such as *"this is a complex task that requires decomposition into child tasks"*, so the agent expects to decompose it.
2. Pick it with `/aitask-pick <N>`. During planning, the agent assesses the task's complexity and offers to break it into child tasks.
3. Refine the decomposition. Review the proposed children and ask for changes to their scopes and dependencies. The agent writes an implementation plan for every child.
4. Stop after planning. At the checkpoint, choose **Stop here**. The parent goes back to `Ready`, the child tasks and their plans are committed, and no code has changed.
5. Implement later. Pick each child with `/aitask-pick <parent>_<child>` when you are ready.

After the session you have:

- child task files in `aitasks/t<N>/`, each with its context, the files to change and how to verify the result;
- implementation plans in `aiplans/p<N>/`, written so that an agent with a fresh context can follow them;
- the parent task, which tracks progress and is archived automatically when its last child is archived.

You can implement the children one at a time or [in parallel using worktrees]({{< relref "/docs/workflows/parallel-development" >}}).

## Deferring a single task's implementation

A task that needs no decomposition can be planned ahead the same way. Pick it, let the agent plan it, and at the checkpoint choose **Approve and stop here**. The plan is committed, the task's [lock]({{< relref "/docs/concepts/locks" >}}) is released, and the task returns to `Ready` with no code written. Planning uses little of the agent's context, so you can plan several tasks this way one after another and implement them later.

The task then carries a marker saying its plan was approved and its implementation deferred, which sets it apart from a task nobody has looked at yet:

```bash
ait ls --plan-approved 20      # tasks with an approved plan awaiting implementation
ait ls -v 20                   # shows "Plan: approved <YYYY-MM-DD HH:MM>" on each
```

The board shows the marker in three places: the task card's status reads `📋 Ready · Planned`, the In-Flight view gathers these tasks in a **Planned** lane, and the task detail dialog shows the approval time as `Plan approved:` under Tracking & provenance. In the Planned lane only **p** (pick) works; resuming directly is refused there, so picking the task always goes back through the planning checkpoint. See [In-Flight Lanes and Workflow Phases]({{< relref "/docs/tuis/board/reference" >}}#in-flight-lanes-and-workflow-phases).

Pick it again with `/aitask-pick <N>` when you are ready. The agent tells you an approved plan is waiting, and the profile's plan preference (or your answer, when the profile sets none) decides whether the plan is used as it is, verified first or replaced. With the shipped profiles, before any code is written, the workflow checks whether the branch you are building on has moved on the remote. If you choose to stop there and re-verify the plan, the marker is cleared, so the task no longer shows a plan that needs checking.

When the work spans two registered projects, [Cross-Project Dependencies]({{< relref "/docs/workflows/cross_project_dependencies" >}}#planning-paired-work-across-two-repos) extends this decomposition into a paired plan: one parent per repository, joined by cross-repo dependencies.
