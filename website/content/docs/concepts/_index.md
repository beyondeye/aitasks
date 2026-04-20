---
title: "Concepts"
linkTitle: "Concepts"
weight: 25
description: "Conceptual reference for the aitasks framework — what each building block is and why it exists."
---

What each building block of the framework *is* and *why* it exists. For *how* to use them, see [Workflows]({{< relref "/docs/workflows" >}}), [Skills]({{< relref "/docs/skills" >}}), and [Commands]({{< relref "/docs/commands" >}}).

## Data model

The files and structures that make up the framework's primary state.

- **[Tasks]({{< relref "/docs/concepts/tasks" >}})** *(Main concepts)* — Markdown files with YAML frontmatter, one per unit of work.
- **[Plans]({{< relref "/docs/concepts/plans" >}})** *(Main concepts)* — The implementation contract for a task, written and approved before code changes.
- **[Parent and child tasks]({{< relref "/docs/concepts/parent-child" >}})** *(Main concepts)* — How a complex task is decomposed into siblings that share context.
- **[Folded tasks]({{< relref "/docs/concepts/folded-tasks" >}})** — How related tasks are merged into a single primary task.
- **[Review guides]({{< relref "/docs/concepts/review-guides" >}})** — Structured prompts that drive batched code review.

## Workflow primitives

The building blocks that shape how skills and code agents behave.

- **[Execution profiles]({{< relref "/docs/concepts/execution-profiles" >}})** — Pre-answered workflow questions that switch a skill from interactive to automated.
- **[Verified scores]({{< relref "/docs/concepts/verified-scores" >}})** — How user satisfaction ratings accumulate into per-model, per-operation reliability scores.
- **[Agent attribution]({{< relref "/docs/concepts/agent-attribution" >}})** — How each task records which code agent and model implemented it.
- **[Locks]({{< relref "/docs/concepts/locks" >}})** *(Main concepts)* — How concurrent agents avoid stepping on each other's tasks.

## Lifecycle and infrastructure

How tasks move through the system and how the repository is laid out.

- **[Task lifecycle]({{< relref "/docs/concepts/task-lifecycle" >}})** *(Main concepts)* — The status transitions a task moves through from creation to archival.
- **[Git branching model]({{< relref "/docs/concepts/git-branching-model" >}})** — The dedicated branches that hold task data, locks, and IDs, and the `./ait git` wrapper that routes to them.
- **[The IDE model]({{< relref "/docs/concepts/ide-model" >}})** — How `ait ide` turns tmux into a navigable agentic IDE around the monitor TUI.
- **[Agent memory]({{< relref "/docs/concepts/agent-memory" >}})** — How archived tasks and plans become long-term, queryable context for future agent sessions.
