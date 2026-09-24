---
title: "Concepts"
linkTitle: "Concepts"
weight: 25
description: "Conceptual reference for the aitasks framework — what each building block is and why it exists."
---

What each building block of the framework *is* and *why* it exists. For *how* to use them, see [Workflows]({{< relref "/docs/workflows" >}}), [Skills]({{< relref "/docs/skills" >}}), and [Commands]({{< relref "/docs/commands" >}}).

## Data model

The files and structures that make up the framework's primary state.

- **[Tasks]({{< relref "/docs/concepts/tasks" >}})** — Markdown files with YAML frontmatter, one per unit of work.
- **[Plans]({{< relref "/docs/concepts/plans" >}})** — The implementation contract for a task, written and approved before code changes.
- **[Parent and child tasks]({{< relref "/docs/concepts/parent-child" >}})** — How a complex task is decomposed into siblings that share context.
- **[Topic anchoring]({{< relref "/docs/concepts/topic-anchoring" >}})** — How loosely related follow-up tasks cluster around a shared subject.
- **[Folded tasks]({{< relref "/docs/concepts/folded-tasks" >}})** — How related tasks are merged into a single primary task.
- **[Task notes]({{< relref "/docs/concepts/task-notes" >}})** — Context sent between tasks, untrusted by construction, and what its provenance can and cannot prove.
- **[Review guides]({{< relref "/docs/concepts/review-guides" >}})** — Structured prompts that drive batched code review.
- **[Attachments]({{< relref "/docs/concepts/attachments" >}})** — Content-addressed files attached to a task, identified by their hash rather than a path.

## Workflow primitives

The building blocks that shape how skills and code agents behave.

- **[Execution profiles]({{< relref "/docs/concepts/execution-profiles" >}})** — Pre-answered workflow questions that switch a skill from interactive to automated.
- **[Skill templating]({{< relref "/docs/concepts/skill-templating" >}})** — How profile-aware skills materialize per-(skill, profile, agent) variants on demand via templated dispatch.
- **[Verified scores]({{< relref "/docs/concepts/verified-scores" >}})** — How user satisfaction ratings accumulate into per-model, per-operation reliability scores.
- **[Agent attribution]({{< relref "/docs/concepts/agent-attribution" >}})** — How each task records which code agent and model implemented it.
- **[Agentcrews]({{< relref "/docs/concepts/agentcrews" >}})** — The multi-agent orchestration engine that runs a team of agents as a dependency-ordered crew; the foundation under flows like brainstorm.
- **[Gates]({{< relref "/docs/concepts/gates" >}})** — Named checks a task must satisfy before it archives, and why the enforced set is fixed when the task is picked.
- **[Locks]({{< relref "/docs/concepts/locks" >}})** — How concurrent agents avoid stepping on each other's tasks.
- **[Shadow agent]({{< relref "/docs/concepts/shadow-agent" >}})** — A companion agent bound to the agent it follows, and what keeps it advisory.

## Lifecycle and infrastructure

How tasks move through the system and how the repository is laid out.

- **[Task lifecycle]({{< relref "/docs/concepts/task-lifecycle" >}})** — The status transitions a task moves through from creation to archival.
- **[Implementation trails]({{< relref "/docs/concepts/implementation-trails" >}})** — Why a sequencing recommendation is kept as a versioned, task-owned artifact instead of being recomputed.
- **[Git branching model]({{< relref "/docs/concepts/git-branching-model" >}})** — The dedicated branches that hold task data, locks, and IDs, and the `./ait git` wrapper that routes to them.
- **[Cross-repo references]({{< relref "/docs/concepts/cross-repo-references" >}})** — Why cross-repo work is identified by a logical project name resolved at call time, never by a path.
- **[The IDE model]({{< relref "/docs/concepts/ide-model" >}})** — How `ait ide` turns tmux into a navigable agentic IDE around the monitor TUI.
- **[Framework session]({{< relref "/docs/concepts/framework-session" >}})** — The machine-wide record of every code agent's pane, session and freeze state, behind freezing an agent and restoring it.
- **[Agent memory]({{< relref "/docs/concepts/agent-memory" >}})** — How archived tasks and plans become long-term, queryable context for future agent sessions.
