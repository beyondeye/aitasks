---
title: "Workflow Guides"
linkTitle: "Workflows"
weight: 40
description: "End-to-end workflow guides for common aitasks operations"
---

This section describes common usage patterns that combine the CLI tools and code agent skills into end-to-end development workflows.

<!-- t594_7 note: these four groupings (Tasks / Parallel / Review & Quality / Git) are candidate source data for a `workflow_category` Hugo taxonomy. When t594_7 adds Docsy label/taxonomy support, this manual grouping can be replaced by taxonomy-driven rendering. -->

## Tasks

The full task lifecycle — capturing ideas quickly, wrapping ad-hoc work into tracked tasks, decomposing large items into children, and consolidating overlap.

- [Capturing Ideas](capturing-ideas/) — Quickly capture task ideas without breaking your flow.
- [Retroactive Tracking](retroactive-tracking/) — Wrap ad-hoc changes into the aitasks framework after the fact.
- [Follow-Up Tasks](follow-up-tasks/) — Creating follow-up tasks, querying existing tasks, and updating them with new findings.
- [Creating Tasks from Code](create-tasks-from-code/) — Browse source files, select a line range, and spawn a task pre-seeded with a file reference.
- [Task Decomposition](task-decomposition/) — Breaking complex tasks into manageable child subtasks.
- [Task Consolidation](task-consolidation/) — Merging overlapping or duplicate tasks into a single actionable task.
- [Exploration-Driven](exploration-driven/) — Start with codebase exploration, create tasks from findings.

## Parallel

Running multiple tasks side by side, front-loading planning work, and farming out execution to remote web sandboxes.

- [Parallel Development](parallel-development/) — Working on multiple tasks simultaneously with concurrency safety.
- [Crash Recovery](crash-recovery/) — Resume a task whose prior agent died mid-implementation, with a survey of leftover work before deciding to reclaim or drop.
- [Parallel Planning](parallel-planning/) — Front-load complex task design work while other implementations run in parallel.
- [Claude Code Web](claude-web/) — Running tasks on Claude Code Web with sandboxed branch access.

## Review & Quality

Keeping the codebase correct and understandable — structured code review, test coverage analysis, and tracing why existing code exists.

- [Code Review](code-review/) — Systematic code review using review guides, separate from implementation.
- [QA and Testing](qa-testing/) — Systematic test coverage analysis and follow-up task creation.
- [Upstream Defect Follow-up](upstream-defect-followup/) — Automatic prompt to spawn a follow-up bug task when diagnosis surfaces a separate, pre-existing defect.
- [Manual Verification](manual-verification/) — Human-checked verification items (TUI flows, live agent launches, artifact inspection) as first-class gated tasks.
- [Explain](explain/) — Use code evolution history to rebuild understanding of why code exists.

## Git

Round-tripping with issue trackers, pull requests, upstream contributions, releases, and reverts — the flows that cross aitasks' boundary with the wider git ecosystem.

- [Issue Tracker](issue-tracker/) — Round-trip workflow between issue trackers (GitHub, GitLab, Bitbucket) and aitasks.
- [PR Import](pr-workflow/) — End-to-end guide for creating aitasks from pull requests.
- [Contributions](contribute-and-manage/) — Sharing changes back upstream and managing incoming contributions with aitasks.
- [Releases](releases/) — Automated changelog generation and release pipeline from task data.
- [Revert Changes](revert-changes/) — Reverting features or changes that are no longer needed.

---

**Next:** [Code Agent Skills]({{< relref "/docs/skills" >}})
