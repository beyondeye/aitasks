---
title: "Parallel Task Planning"
linkTitle: "Parallel Planning"
weight: 45
description: "Front-load complex task design work while other implementations run in parallel"
---

When you know a feature is complex enough to need [child task decomposition](../task-decomposition/), you can run just the planning and decomposition phase — without writing any code. This produces a full set of child tasks with ready-to-use implementation plans, and it can safely happen in parallel with any other ongoing work.

## Why This Is Safe

This workflow is pure design work. No source code is modified — only task definitions and implementation plans are created. That means there's no risk of conflicts with whatever implementation is happening in other terminals or on other machines.

And the plans don't go stale. When a child task is later picked for implementation, the existing plan is automatically verified against the current codebase before any code is written. If the code has changed since the plan was created, the plan gets updated first. This double verification — once during decomposition, once at implementation time — means the upfront design work stays reliable even if weeks pass before implementation begins.

## When to Use This

- **Complex features you want to think through** — You know the task needs decomposition, but implementation is queued behind other work. Use the waiting time productively by doing the design
- **Preparing parallel workloads** — Child task decompositions often produce independent subtasks that can be safely executed in parallel. Doing the decomposition upfront means you can hand multiple children to multiple agents simultaneously
- **Design sessions** — You want to iterate on the architecture with the AI agent (refining child scopes, adjusting dependencies, splitting or merging subtasks) without committing to implementation yet

## How It Works

1. **Create the parent task** — Write the task description covering the full feature scope. End the description with a line like *"this is a complex task that requires decomposition into child tasks"* to signal that decomposition is expected

2. **Pick the task** — Run `/aitask-pick <N>`. During the planning phase, the agent will assess complexity and offer to break the task into child subtasks

3. **Iterate on the decomposition** — This is the interactive part. Review the proposed child tasks, ask for changes, adjust scopes and dependencies. The agent writes detailed implementation plans for every child task during this phase

4. **Stop after planning** — At the checkpoint, select "Stop here." The parent task reverts to Ready status, and all child tasks and their plans are committed. No code has been touched

5. **Implement later** — Pick individual children with `/aitask-pick <parent>_<child>` whenever you're ready. Each child's plan is verified against the current codebase before implementation begins

## What You Get

After the planning session, you have:

- Child task files in `aitasks/t<N>/` — each with full context, key files to modify, and verification steps
- Implementation plans in `aiplans/p<N>/` — detailed step-by-step plans ready for a fresh agent context to execute
- A parent task that tracks overall progress and auto-archives when all children complete

The children can then be implemented one at a time or [in parallel using worktrees](../parallel-development/).
