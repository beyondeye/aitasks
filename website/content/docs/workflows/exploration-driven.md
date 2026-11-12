---
title: "Exploration-Driven Development"
linkTitle: "Exploration-Driven"
weight: 75
description: "Start with codebase exploration, create tasks from findings"
depth: [intermediate]
---

Sometimes you don't know what the task should be. You have a vague symptom, an unfamiliar module to understand, or a hunch that something could be improved, but you can't write a task description yet because you haven't explored enough to know what needs doing. The [`/aitask-explore`]({{< relref "/docs/skills/aitask-explore" >}}) skill is for this situation: you explore first and define the task from what you find.

The usual aitasks flow is *define task → pick task → implement*. Here you follow *explore → discover → define task → implement*. The exploration runs in rounds: you direct the agent's investigation, review findings after each round, and decide when you've learned enough to write the task.

## When to Use Exploration-Driven Development

- **Debugging a vague symptom.** "Something is slow" or "users report occasional errors", and you need to investigate before you can define a fix
- **Understanding unfamiliar code.** Onboarding to a new module or reviewing code you haven't touched in months
- **Looking for improvement opportunities.** You suspect there's technical debt or duplication but need to map it out first
- **Scoping a feature idea.** You have a rough idea but need to discover which files, modules, and patterns are involved before estimating effort
- **Documentation gaps.** You want to find where docs are missing or outdated but don't know the full scope yet

## Walkthrough: Investigating a Performance Issue

A user reports that "the order history page is slow." You don't know where the bottleneck is, so you start with exploration.

**1. Launch the skill**

```
/aitask-explore
```

Select "Investigate a problem" when prompted. Describe the symptom: "The backend's `list_orders` endpoint is slow for customers with many orders."

**2. First exploration round**

The skill traces the data flow in `list_orders`: how orders are loaded, filtered, and sorted. Findings: the handler loads every order for the customer, even when the request filters by status. With thousands of orders, this adds up.

You're shown a summary and asked how to proceed. Select "Continue exploring" and redirect: "Check if there's any caching or if the order serialization could be optimized."

**3. Second exploration round**

The skill examines the order serializer, finds it runs one database query per order to load its line items, and identifies that a single joined query could replace them. It also finds that cancelled orders are excluded early, but the sort happens in application code after all orders are loaded (a possible improvement: sort in the query).

The findings are clear enough. Select "Create a task."

**4. Task creation**

The skill summarizes the exploration:
- Focus: Performance of `list_orders` for customers with many orders
- Key findings: one query per order, load-then-sort pattern
- Suggested task: "Optimize list_orders queries for large order histories"

The task is created with metadata pre-filled from the exploration mode (`issue_type: bug`, `priority: high`). You confirm and select "Continue to implementation" to hand off to the standard [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}) workflow.

## Exploration Modes

Each mode sets a different investigation strategy and task defaults:

| Mode | Best for | Default task type |
|------|----------|-------------------|
| **Investigate a problem** | Bugs, performance issues, error tracing | `bug` (high priority) |
| **Explore codebase area** | Understanding modules, mapping dependencies | `feature` (medium priority) |
| **Scope an idea** | Estimating how many files and modules a proposed change would touch | `feature` (medium priority) |
| **Explore documentation** | Finding doc gaps, outdated content, missing help text | `documentation` (medium priority) |

You can also type a goal of your own instead of choosing a mode. The agent then explores from your description, and the task defaults to `feature` (medium priority).

## Consolidating Related Work

During task creation, `/aitask-explore` scans pending tasks for overlap with your findings. If it finds existing tasks that your new task would fully cover, you can fold them in: their content is incorporated into the new task description, and the originals are removed when the new task is archived.

This prevents duplicate tasks from accumulating when multiple exploration sessions or different team members discover the same issues. For folding tasks outside of the explore workflow, use [`/aitask-fold`]({{< relref "/docs/skills/aitask-fold" >}}).

## Tips

- **Redirect freely.** After each exploration round, you can shift focus. Start broad, then narrow in on what matters
- **Don't over-explore.** Two or three rounds is usually enough. Create the task when you have a clear picture, even if some details remain; the planning phase fills in the rest
- **Use profiles.** The `explore_auto_continue` profile key controls whether you're prompted to continue to implementation or save the task for later. Set it to `true` in your profile if you always want to implement immediately
