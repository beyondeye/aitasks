---
title: "Complex Task Decomposition"
linkTitle: "Task Decomposition"
weight: 20
description: "Breaking complex tasks into manageable child subtasks"
---

For tasks that are too large or risky for a single implementation run, the aitasks framework supports decomposition into child subtasks. This gives you controlled, disciplined execution of complex features while maintaining full context across all subtasks.

## How It Works

- During the planning phase of [`/aitask-pick`](../../skills/aitask-pick/), if a task is assessed as high complexity, the skill automatically offers to break it into child subtasks
- You can also force decomposition by adding a line like "this is a complex task: please decompose in child tasks" in the task description
- Each child task is created with detailed context: key files to modify, reference patterns, step-by-step implementation instructions, and verification steps. This ensures each child can be executed independently in a fresh Claude Code context

## Context Propagation Between Siblings

When implementing a child task, [`/aitask-pick`](../../skills/aitask-pick/) automatically gathers context from previously completed siblings. The primary reference is the archived plan files in `aiplans/archived/p<parent>/`, which contain the full implementation record including a "Final Implementation Notes" section with patterns established, gotchas discovered, and shared code created. This means each successive child task benefits from the experience of earlier ones.

## Typical Decomposition Flow

1. Create a parent task describing the full feature
2. Run `/aitask-pick <parent_number>` — during planning, choose to decompose
3. Define child tasks with descriptions and dependencies
4. Implement children one at a time with `/aitask-pick <parent>_<child>` (e.g., `/aitask-pick 16_1`, `/aitask-pick 16_2`)
5. When all children are complete, the parent is automatically archived
